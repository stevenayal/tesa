"""Normalización de cédulas y RUC paraguayos.

En Paraguay el RUC de una persona física es su número de cédula más un dígito
verificador (DV) calculado con módulo 11 (algoritmo de la SET/DNIT). Los RUC de
personas jurídicas usan números base a partir de 80.000.000.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

BASE_PERSONA_JURIDICA = 80_000_000

_PREFIJOS_OCDS = re.compile(r"^\s*PY-RUC-", re.IGNORECASE)
_SOLO_DIGITOS = re.compile(r"\D")


class TipoContribuyente(str, Enum):
    FISICA = "fisica"
    JURIDICA = "juridica"
    INVALIDO = "invalido"


@dataclass(frozen=True)
class RucNormalizado:
    base: str | None  # número sin DV, sin puntos ni ceros a la izquierda
    dv: int | None  # dígito verificador informado (None si no vino)
    tipo: TipoContribuyente
    dv_valido: bool | None  # None si no se pudo verificar


def calcular_dv(numero: str, base_max: int = 11) -> int:
    """Calcula el dígito verificador del RUC (módulo 11, pesos 2..base_max)."""
    if not numero or not numero.isdigit():
        raise ValueError(f"Número inválido para DV: {numero!r}")
    total = 0
    peso = 2
    for caracter in reversed(numero):
        if peso > base_max:
            peso = 2
        total += int(caracter) * peso
        peso += 1
    resto = total % 11
    return 11 - resto if resto > 1 else 0


def _a_texto(valor: object) -> str | None:
    """Convierte ints, floats ('1234567.0'), NaN y strings a texto limpio."""
    if valor is None:
        return None
    if isinstance(valor, float):
        if math.isnan(valor):
            return None
        if valor.is_integer():
            return str(int(valor))
    texto = str(valor).strip()
    if not texto or texto.lower() in {"nan", "none", "null"}:
        return None
    # "1234567.0" leído como texto desde un CSV
    if re.fullmatch(r"\d+\.0+", texto):
        texto = texto.split(".")[0]
    return texto


def normalizar_cedula(valor: object) -> str | None:
    """Devuelve la cédula solo con dígitos y sin ceros a la izquierda, o None."""
    texto = _a_texto(valor)
    if texto is None:
        return None
    if re.search(r"[A-Za-z]", texto):  # "ANON…", "VAC…": anonimizados o vacantes
        return None
    digitos = _SOLO_DIGITOS.sub("", texto).lstrip("0")
    if not digitos or len(digitos) > 9:
        return None
    return digitos


def normalizar_ruc(valor: object) -> RucNormalizado:
    """Separa base y DV de un RUC en cualquiera de los formatos habituales.

    Acepta: '1234567-9', '1.234.567-9', 'PY-RUC-1234567-9', '1234567' (sin DV).
    Un RUC sin guion se interpreta como base sin DV, porque no hay forma segura
    de distinguir '12345679' (base+DV) de una cédula de 8 dígitos.
    """
    invalido = RucNormalizado(None, None, TipoContribuyente.INVALIDO, None)
    texto = _a_texto(valor)
    if texto is None:
        return invalido
    texto = _PREFIJOS_OCDS.sub("", texto)

    if "-" in texto:
        parte_base, _, parte_dv = texto.rpartition("-")
        base = _SOLO_DIGITOS.sub("", parte_base).lstrip("0")
        dv_txt = _SOLO_DIGITOS.sub("", parte_dv)
        dv = int(dv_txt) if len(dv_txt) == 1 else None
    else:
        base = _SOLO_DIGITOS.sub("", texto).lstrip("0")
        dv = None

    if not base or len(base) > 9:
        return invalido

    tipo = (
        TipoContribuyente.JURIDICA
        if int(base) >= BASE_PERSONA_JURIDICA
        else TipoContribuyente.FISICA
    )
    dv_valido = (calcular_dv(base) == dv) if dv is not None else None
    return RucNormalizado(base, dv, tipo, dv_valido)
