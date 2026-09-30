"""Lectura tolerante de los CSV de la SFP y la DNCP."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

# Nombres de columna habituales, en orden de preferencia.
CANDIDATAS_NOMINA = ["documento", "cedula", "nro_documento", "ci", "numero_documento"]
CANDIDATAS_PROVEEDORES = [
    "ruc",
    "proveedor_ruc",
    "ruc_proveedor",
    "awards/0/suppliers/0/id",
    "suppliers/0/id",
    "id",
]

_ENCODINGS = ("utf-8-sig", "latin-1")


def _detectar_separador(ruta: Path, encoding: str) -> str:
    with ruta.open("r", encoding=encoding, errors="replace") as f:
        muestra = f.read(64_000)
    try:
        return csv.Sniffer().sniff(muestra, delimiters=",;|\t").delimiter
    except csv.Error:
        return ","


def leer_csv(ruta: str | Path, columnas: list[str] | None = None) -> pd.DataFrame:
    """Lee un CSV probando encodings y separadores; todo como texto."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")
    ultimo_error: Exception | None = None
    for encoding in _ENCODINGS:
        try:
            sep = _detectar_separador(ruta, encoding)
            return pd.read_csv(
                ruta,
                sep=sep,
                encoding=encoding,
                dtype=str,
                usecols=columnas,
                low_memory=False,
            )
        except UnicodeDecodeError as e:
            ultimo_error = e
    raise ValueError(f"No se pudo leer {ruta}: {ultimo_error}")


def detectar_columna(df: pd.DataFrame, candidatas: list[str]) -> str:
    """Busca la primera columna que coincida (sin distinguir mayúsculas)."""
    por_minuscula = {c.lower().strip(): c for c in df.columns}
    for candidata in candidatas:
        if candidata.lower() in por_minuscula:
            return por_minuscula[candidata.lower()]
    raise KeyError(
        f"No se encontró ninguna de las columnas {candidatas}. Columnas disponibles: "
        f"{list(df.columns)}. Indicala con --col-nomina, --col-proveedores o --col-categoria."
    )
