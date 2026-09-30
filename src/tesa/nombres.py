"""Normalización y comparación de nombres de personas.

Se usa para cruzar el nombre del representante legal de una empresa (DNCP)
con el nombre de un funcionario (nómina SFP), que llegan en formatos distintos:

    DNCP: "AIDA GALILA BENITEZ DE RIVAS"          (un solo campo)
    SFP:  nombres="AIDA GALILA", apellidos="BENITEZ DE RIVAS"

La comparación trabaja sobre el *conjunto* de palabras, así el orden
(nombres primero o apellidos primero) no importa.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# Partículas que no identifican a la persona y varían entre registros.
PARTICULAS = frozenset({"DE", "DEL", "LA", "LAS", "LOS", "Y", "VDA", "VIUDA"})

_NO_LETRAS = re.compile(r"[^A-Z ]+")


def normalizar_nombre(*partes: object) -> str:
    """Une, pasa a mayúsculas, quita tildes, signos y partículas.

    >>> normalizar_nombre("Aída Galila", "Benítez de Rivas")
    'AIDA GALILA BENITEZ RIVAS'
    """
    texto = " ".join(str(p) for p in partes if p is not None and str(p).lower() != "nan")
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c)).upper()
    texto = _NO_LETRAS.sub(" ", texto)
    return " ".join(t for t in texto.split() if t not in PARTICULAS and len(t) > 1)


def clave(nombre_normalizado: str) -> str:
    """Clave independiente del orden: palabras ordenadas alfabéticamente."""
    return " ".join(sorted(nombre_normalizado.split()))


def similitud(clave_a: str, clave_b: str) -> float:
    """Similitud entre 0 y 1 de dos claves (tolera errores de tipeo)."""
    return SequenceMatcher(None, clave_a, clave_b).ratio()
