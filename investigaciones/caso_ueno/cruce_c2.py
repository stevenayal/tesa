"""Cruce C2 del caso ueno: personas vinculadas al grupo × nómina pública 2023–2026.

Reutiliza el cruce por nombre de TESA (tesa.cruce_nombres) con sus niveles de confianza. Una persona del
universo hace de "representante" y su empresa aporta las entidades que le adjudicaron contratos, para
detectar el nivel "alta" (el funcionario trabaja en una entidad que contrató con esa empresa).

Si está el padrón de RUC de la DNIT descomprimido en data/raw/ruc/ruc*.txt, un nombre que corresponde a
más de una persona física en el país pasa a "ambigua" (homónimo poblacional), aunque sea único en la nómina.

Uso:
    python investigaciones/caso_ueno/cruce_c2.py

Entradas (privadas): data/interim/universo_personas.csv, data/interim/nomina_2023_2026.csv.gz,
                     data/raw/ueno/adjudicaciones_enriquecidas.csv
                     data/raw/ruc/ruc*.txt (opcional, padrón de RUC de la DNIT)
Salida (privada):    data/output/ueno_c2_detalle.csv
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from tesa.cruce_nombres import MIN_PALABRAS, cruzar_por_nombre
from tesa.nombres import normalizar_nombre
from tesa.padron_ruc import archivos_padron, cargar_frecuencia_nombres

SALIDA = Path("data/output/ueno_c2_detalle.csv")


def _entidad(texto: str) -> str:
    """'Instituto de Previsión Social (IPS)' / 'X / Ministerio Y' -> nombre comparable con la SFP."""
    texto = re.sub(r"\(.*?\)", " ", str(texto)).split("/")[0]
    return normalizar_nombre(texto)


def main() -> None:
    personas = pd.read_csv("data/interim/universo_personas.csv", dtype=str)
    personas["id"] = "P" + personas.index.astype(str)
    personas["ruc_empresa"] = personas["empresa_o_entidad"].str.extract(r"RUC (\S+)")[0]

    nomina = pd.read_csv("data/interim/nomina_2023_2026.csv.gz", dtype=str)
    nomina["entidad_norm"] = nomina["descripcion_entidad"].map(_entidad)

    adj = pd.read_csv("data/raw/ueno/adjudicaciones_enriquecidas.csv", dtype=str)
    adj["entidad"] = adj["convocante"].map(_entidad)
    # cada persona hereda las entidades que contrataron con su empresa
    adj_personas = personas.dropna(subset=["ruc_empresa"]).merge(
        adj[["ruc", "entidad"]], left_on="ruc_empresa", right_on="ruc"
    )[["id", "entidad"]].rename(columns={"id": "ruc"})

    frecuencia = None
    if archivos_padron():
        frecuencia = cargar_frecuencia_nombres()
        print(f"Padrón de RUC: {sum(frecuencia.values())} personas físicas, {len(frecuencia)} nombres distintos")
    else:
        print("Padrón de RUC no encontrado en data/raw/ruc/: sin control de homónimos poblacionales")

    resumen, detalle = cruzar_por_nombre(
        nomina, personas,
        col_doc="documento", col_nombres="nombres", col_apellidos="apellidos",
        col_ruc="id", col_representante="nombre", col_entidad_nomina="entidad_norm",
        adjudicaciones=adj_personas, col_adj_ruc="ruc", col_adj_entidad="entidad",
        frecuencia_poblacional=frecuencia,
    )

    cortos = personas[personas["nombre"].map(lambda n: len(normalizar_nombre(n).split()) < MIN_PALABRAS)]
    print(f"Personas en el universo: {personas['nombre'].str.lower().nunique()}")
    print(f"Sin cruzar por tener menos de {MIN_PALABRAS} palabras: {cortos['nombre'].nunique()} "
          f"({', '.join(sorted(cortos['nombre'].unique()))})")
    print(f"Cruzables: {resumen.representantes_validos} · coincidencias por nivel: {resumen.coincidencias_por_nivel}")

    # detalle con los cargos de cada documento coincidente
    detalle = detalle.rename(columns={"ruc_empresa": "id"}).merge(personas, on="id")
    filas = []
    for _, d in detalle.iterrows():
        for doc in d["documentos"].split(";"):
            for _, c in nomina[nomina["documento"] == doc].iterrows():
                filas.append({**d.to_dict(), "documento": doc,
                              "nombre_en_nomina": f"{c['nombres']} {c['apellidos']}",
                              "entidad": c["descripcion_entidad"], "oee": c["descripcion_oee"],
                              "cargo": c["cargo"], "funcion": c["funcion"], "estado": c["estado"],
                              "desde": c["primer_mes"], "hasta": c["ultimo_mes"],
                              "max_mensual": c["max_mensual"]})
    salida = pd.DataFrame(filas).drop(columns=["documentos"], errors="ignore")
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    salida.to_csv(SALIDA, index=False)
    print(f"→ {SALIDA}: {len(salida)} filas (privado)")


if __name__ == "__main__":
    main()
