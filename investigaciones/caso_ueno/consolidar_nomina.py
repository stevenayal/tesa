"""Consolida las nóminas mensuales de la SFP en una tabla de cargos con período.

Lee los ZIP mensuales de data/raw/sfp/ (agosto 2023 – noviembre 2026), sin descomprimir a disco, y deja una
fila por persona × entidad × cargo con el primer y el último mes en que figura.

Uso:
    python investigaciones/caso_ueno/consolidar_nomina.py

Salida (privada, ignorada por git): data/interim/nomina_2023_2026.csv.gz
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd

ENTRADA = Path("data/raw/sfp")
SALIDA = Path("data/interim/nomina_2023_2026.csv.gz")
COLUMNAS = ["anho", "mes", "descripcion_entidad", "descripcion_oee", "documento", "nombres", "apellidos",
            "cargo", "funcion", "estado", "presupuestado"]
CLAVE = ["documento", "descripcion_entidad", "descripcion_oee", "cargo"]


def _periodo(archivo: Path) -> int:
    anho, mes = map(int, re.findall(r"(\d{4})_(\d{1,2})", archivo.name)[0])
    return anho * 100 + mes


def consolidar() -> pd.DataFrame:
    acumulado: pd.DataFrame | None = None
    for archivo in sorted(ENTRADA.glob("funcionarios_*.csv.zip"), key=_periodo):
        with zipfile.ZipFile(archivo) as z, z.open(z.namelist()[0]) as fh:
            for trozo in pd.read_csv(fh, usecols=COLUMNAS, dtype=str, encoding="latin-1",
                                     chunksize=500_000, on_bad_lines="skip"):
                trozo["periodo"] = trozo["anho"].astype(int) * 100 + trozo["mes"].astype(int)
                trozo["presupuestado"] = pd.to_numeric(trozo["presupuestado"], errors="coerce")
                # una persona cobra varias líneas por cargo: se suma el mes y se agrupa
                trozo = (trozo.groupby(CLAVE + ["periodo"], dropna=False)
                         .agg(nombres=("nombres", "first"), apellidos=("apellidos", "first"),
                              funcion=("funcion", "first"), estado=("estado", "first"),
                              presupuestado=("presupuestado", "sum"))
                         .reset_index())
                trozo = (trozo.groupby(CLAVE, dropna=False)
                         .agg(nombres=("nombres", "first"), apellidos=("apellidos", "first"),
                              funcion=("funcion", "first"), estado=("estado", "last"),
                              primer_mes=("periodo", "min"), ultimo_mes=("periodo", "max"),
                              max_mensual=("presupuestado", "max"))
                         .reset_index())
                acumulado = trozo if acumulado is None else _fusionar(acumulado, trozo)
        print(f"{archivo.name}: {len(acumulado):,} cargos acumulados", flush=True)
    return acumulado


def _fusionar(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    return (pd.concat([a, b]).groupby(CLAVE, dropna=False)
            .agg(nombres=("nombres", "first"), apellidos=("apellidos", "first"),
                 funcion=("funcion", "first"), estado=("estado", "last"),
                 primer_mes=("primer_mes", "min"), ultimo_mes=("ultimo_mes", "max"),
                 max_mensual=("max_mensual", "max"))
            .reset_index())


if __name__ == "__main__":
    tabla = consolidar()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(SALIDA, index=False, compression="gzip")
    print(f"→ {SALIDA}: {len(tabla):,} cargos, {tabla['documento'].nunique():,} personas")
