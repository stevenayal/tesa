"""Padrón nacional de RUC (DNIT): frecuencia poblacional de nombres de personas físicas.

Sirve para no tomar como identificación un nombre que es único en la nómina de la
SFP pero común en el país. La DNIT publica el padrón completo como ruc0.zip … ruc9.zip:
https://www.dnit.gov.py/web/portal-institucional/listado-de-ruc-con-sus-equivalencias

Formato de cada línea (UTF-8)::

    RUC|NOMBRE|DV|RUC_ANTERIOR|ESTADO|

Las personas físicas tienen el NOMBRE como ``APELLIDOS, NOMBRES``. Las personas
jurídicas no suelen tener coma, pero algunas sí ("COOPERATIVA … DE AHORRO, CRÉDITO …",
"PEREZ, JUAN EIRL"), así que además se descartan los RUC del rango de personas
jurídicas (8 dígitos que empiezan en 80). Se cuentan todos los estados (activo,
cancelado, suspendido…): un RUC cancelado sigue siendo una persona con ese nombre.

Algunos RUC llevan una letra al final ("1132310A") y repiten a la persona de otro
RUC; se cuenta una vez cada par (número de RUC, nombre).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path

from tesa.nombres import clave, normalizar_nombre

DIRECTORIO_PADRON = Path("data/raw/ruc")
PATRON_ARCHIVOS = "ruc*.txt"
RUC_MIN_PERSONA_JURIDICA = 80_000_000

_DIGITOS = re.compile(r"\d+")


def clave_persona_fisica(ruc: str, nombre: str) -> str | None:
    """Clave de nombre (``tesa.nombres.clave``) si el registro es de una persona física.

    >>> clave_persona_fisica("1000001", "QUINTANA DE VERA, ARIEL TOMAS")
    'ARIEL QUINTANA TOMAS VERA'
    >>> clave_persona_fisica("80000011", "PEREZ, JUAN EIRL") is None
    True
    """
    if "," not in nombre:
        return None
    numero = _DIGITOS.match(ruc.strip())
    if numero is None or int(numero.group()) >= RUC_MIN_PERSONA_JURIDICA:
        return None
    apellidos, nombres = nombre.split(",", 1)
    k = clave(normalizar_nombre(nombres, apellidos))
    return k or None


def _registros(lineas: Iterable[str]) -> Iterator[tuple[str, str]]:
    """(RUC, NOMBRE) de cada línea; tolera un '|' dentro del nombre."""
    for linea in lineas:
        partes = linea.rstrip("\r\n").split("|")
        if len(partes) < 5:
            continue
        # RUC | NOMBRE (puede contener '|') | DV | RUC_ANTERIOR | ESTADO | ''
        fin_nombre = len(partes) - 4 if partes[-1] == "" else len(partes) - 3
        yield partes[0], "|".join(partes[1:fin_nombre])


def frecuencia_lineas(lineas: Iterable[str]) -> Counter[str]:
    """Cuántas personas físicas distintas del padrón tienen cada clave de nombre."""
    frecuencia: Counter[str] = Counter()
    vistos: set[tuple[str, str]] = set()
    for ruc, nombre in _registros(lineas):
        k = clave_persona_fisica(ruc, nombre)
        if k is None:
            continue
        numero = _DIGITOS.match(ruc.strip())
        par = (numero.group() if numero else ruc, k)
        if par in vistos:
            continue
        vistos.add(par)
        frecuencia[k] += 1
    return frecuencia


def archivos_padron(directorio: str | Path = DIRECTORIO_PADRON) -> list[Path]:
    """Archivos ruc*.txt descomprimidos del padrón (lista vacía si no están)."""
    return sorted(Path(directorio).glob(PATRON_ARCHIVOS))


def cargar_frecuencia_nombres(directorio: str | Path = DIRECTORIO_PADRON) -> Counter[str]:
    """Frecuencia de claves de nombre de personas físicas en todo el padrón de RUC."""
    archivos = archivos_padron(directorio)
    if not archivos:
        raise FileNotFoundError(
            f"No hay {PATRON_ARCHIVOS} en {directorio}: descargar ruc0.zip … ruc9.zip de la DNIT y descomprimir"
        )

    def lineas() -> Iterator[str]:
        for archivo in archivos:
            with open(archivo, encoding="utf-8", errors="replace") as f:
                yield from f

    return frecuencia_lineas(lineas())
