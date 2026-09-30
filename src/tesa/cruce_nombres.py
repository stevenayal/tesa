"""Cruce por nombre: representante legal de empresas proveedoras × funcionarios.

Complementa el cruce por cédula (personas físicas). Cada coincidencia recibe un
nivel de confianza, porque un nombre no identifica a una persona como una cédula:

    alta     nombre completo idéntico, único en la nómina y el funcionario trabaja
             en una entidad que adjudicó contratos a la empresa
    media    nombre completo idéntico y único en la nómina
    baja     nombre casi idéntico (posible error de tipeo) y único en la nómina
    ambigua  el nombre corresponde a 2 o más funcionarios distintos (homónimos):
             se informa pero NO se usa como alerta

Solo se consideran nombres de al menos 3 palabras (sin partículas), porque con
menos la probabilidad de homónimos es demasiado alta.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import pandas as pd

from tesa.normalizacion import normalizar_cedula
from tesa.nombres import clave, normalizar_nombre, similitud

UMBRAL_APROXIMADA = 0.93
MIN_PALABRAS = 3
NIVELES = ("alta", "media", "baja", "ambigua")


@dataclass(frozen=True)
class ResultadoNombres:
    empresas_con_representante: int
    representantes_validos: int
    coincidencias_por_nivel: dict[str, int]

    @property
    def alertas(self) -> int:
        """Coincidencias utilizables (excluye las ambiguas)."""
        return sum(v for k, v in self.coincidencias_por_nivel.items() if k != "ambigua")


def _indice_nomina(
    nomina: pd.DataFrame, col_doc: str, col_nombres: str, col_apellidos: str, col_entidad: str | None
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]]]:
    """clave -> documentos; palabra -> claves; documento -> entidades."""
    documentos_por_clave: dict[str, set[str]] = defaultdict(set)
    entidades_por_doc: dict[str, set[str]] = defaultdict(set)
    entidades = nomina[col_entidad] if col_entidad else [None] * len(nomina)
    for documento, nombres, apellidos, entidad in zip(
        nomina[col_doc], nomina[col_nombres], nomina[col_apellidos], entidades
    ):
        documento = normalizar_cedula(documento)
        if documento is None:  # vacantes y documentos anonimizados
            continue
        nombre = normalizar_nombre(nombres, apellidos)
        if len(nombre.split()) < MIN_PALABRAS:
            continue
        documentos_por_clave[clave(nombre)].add(documento)
        if col_entidad:
            entidades_por_doc[documento].add(normalizar_nombre(entidad))
    claves_por_palabra: dict[str, set[str]] = defaultdict(set)
    for k in documentos_por_clave:
        for palabra in k.split():
            claves_por_palabra[palabra].add(k)
    return documentos_por_clave, claves_por_palabra, entidades_por_doc


def _candidatas(k: str, claves_por_palabra: dict[str, set[str]]) -> set[str]:
    """Claves de la nómina que comparten todas las palabras menos una."""
    palabras = k.split()
    conteo: dict[str, int] = defaultdict(int)
    for palabra in palabras:
        for otra in claves_por_palabra.get(palabra, ()):
            conteo[otra] += 1
    minimo = max(len(palabras) - 1, 2)
    return {c for c, n in conteo.items() if n >= minimo}


def cruzar_por_nombre(
    nomina: pd.DataFrame,
    proveedores: pd.DataFrame,
    *,
    col_doc: str,
    col_nombres: str,
    col_apellidos: str,
    col_ruc: str = "ruc",
    col_representante: str = "representante_legal",
    col_entidad_nomina: str | None = None,
    adjudicaciones: pd.DataFrame | None = None,
    col_adj_ruc: str = "ruc",
    col_adj_entidad: str = "entidad",
) -> tuple[ResultadoNombres, pd.DataFrame]:
    """Devuelve el resumen y el detalle (uso privado) de coincidencias por nombre."""
    por_clave, por_palabra, entidades_doc = _indice_nomina(
        nomina, col_doc, col_nombres, col_apellidos, col_entidad_nomina
    )

    entidades_empresa: dict[str, set[str]] = defaultdict(set)
    if adjudicaciones is not None:
        for ruc, entidad in zip(adjudicaciones[col_adj_ruc], adjudicaciones[col_adj_entidad]):
            entidades_empresa[str(ruc)].add(normalizar_nombre(entidad))

    con_repr = proveedores[proveedores[col_representante].fillna("").str.strip() != ""]
    con_repr = con_repr.drop_duplicates(subset=[col_ruc])
    filas = []
    validos = 0
    for ruc, representante in zip(con_repr[col_ruc], con_repr[col_representante]):
        nombre = normalizar_nombre(representante)
        if len(nombre.split()) < MIN_PALABRAS:
            continue
        validos += 1
        k = clave(nombre)
        if k in por_clave:
            tipo, clave_nomina, sim = "exacta", k, 1.0
        else:
            mejor = max(
                ((c, similitud(k, c)) for c in _candidatas(k, por_palabra)),
                key=lambda x: x[1],
                default=(None, 0.0),
            )
            if mejor[0] is None or mejor[1] < UMBRAL_APROXIMADA:
                continue
            tipo, clave_nomina, sim = "aproximada", mejor[0], mejor[1]

        documentos = por_clave[clave_nomina]
        if len(documentos) > 1:
            nivel = "ambigua"
        elif tipo == "aproximada":
            nivel = "baja"
        else:
            documento = next(iter(documentos))
            comun = entidades_doc.get(documento, set()) & entidades_empresa.get(str(ruc), set())
            nivel = "alta" if comun else "media"
        filas.append(
            {
                "ruc_empresa": ruc,
                "tipo": tipo,
                "similitud": round(sim, 3),
                "funcionarios_con_ese_nombre": len(documentos),
                "documentos": ";".join(sorted(documentos)),
                "nivel": nivel,
            }
        )

    detalle = pd.DataFrame(
        filas,
        columns=["ruc_empresa", "tipo", "similitud", "funcionarios_con_ese_nombre", "documentos", "nivel"],
    )
    por_nivel = {n: int((detalle["nivel"] == n).sum()) for n in NIVELES}
    resumen = ResultadoNombres(
        empresas_con_representante=int(len(con_repr)),
        representantes_validos=validos,
        coincidencias_por_nivel=por_nivel,
    )
    return resumen, detalle
