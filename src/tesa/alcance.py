"""Alcance del estudio: rubros (categorías de nivel 1) del catálogo de la DNCP.

La tesis se limita a tres categorías:

- 4  Capacitaciones y Adiestramientos
- 5  Consultorías, Asesorías e Investigaciones. Estudios y Proyectos de inversión
- 24 Equipos, accesorios y programas computacionales, de oficina, educativos,
     de imprenta, de comunicación y señalamiento

El filtro acepta el código ("24", "24.0", "24 - Equipos...") o el nombre de la
categoría (sin distinguir mayúsculas ni tildes), porque los CSV y los JSON OCDS
de la DNCP no siempre traen el mismo formato.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

RUBROS: dict[int, str] = {
    4: "Capacitaciones y Adiestramientos",
    5: "Consultorías, Asesorías e Investigaciones. Estudios y Proyectos de inversión",
    24: (
        "Equipos, accesorios y programas computacionales, de oficina, educativos, "
        "de imprenta, de comunicación y señalamiento"
    ),
}
RUBROS_POR_DEFECTO: tuple[int, ...] = tuple(RUBROS)

CANDIDATAS_CATEGORIA = [
    "categoria",
    "categoria_codigo",
    "categoria_id",
    "codigo_categoria",
    "tender/mainProcurementCategoryDetails",
    "compiledRelease/tender/mainProcurementCategoryDetails",
    "mainProcurementCategoryDetails",
]

_CODIGO_INICIAL = re.compile(r"^\s*(\d{1,3})(?:\.0+)?(?:\s*[-–:]|\s*$)")


def _sin_tildes(texto: str) -> str:
    forma = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in forma if not unicodedata.combining(c)).lower().strip()


_NOMBRES = {_sin_tildes(nombre): codigo for codigo, nombre in RUBROS.items()}


def codigo_de_categoria(valor: object) -> int | None:
    """Devuelve el código de rubro si se reconoce, o None."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor)
    coincidencia = _CODIGO_INICIAL.match(texto)
    if coincidencia:
        return int(coincidencia.group(1))
    normalizado = _sin_tildes(texto)
    for nombre, codigo in _NOMBRES.items():
        # prefijo: tolera nombres truncados en algunos exports
        if normalizado and (normalizado.startswith(nombre[:40]) or nombre.startswith(normalizado)):
            return codigo
    return None


def filtrar_por_rubros(
    df: pd.DataFrame, columna: str, rubros: tuple[int, ...] = RUBROS_POR_DEFECTO
) -> pd.DataFrame:
    """Conserva solo las filas cuya categoría pertenece a los rubros indicados."""
    codigos = df[columna].map(codigo_de_categoria)
    return df[codigos.isin(set(rubros))]


def parsear_rubros(texto: str) -> tuple[int, ...]:
    """'4,5,24' -> (4, 5, 24)."""
    try:
        rubros = tuple(int(x) for x in texto.split(",") if x.strip())
    except ValueError as e:
        raise ValueError(f"Rubros inválidos: {texto!r}. Usar códigos separados por coma.") from e
    if not rubros:
        raise ValueError("Se debe indicar al menos un rubro.")
    return rubros
