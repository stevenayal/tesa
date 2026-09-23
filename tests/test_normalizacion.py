import math

import pytest

from tesa.normalizacion import (
    TipoContribuyente,
    calcular_dv,
    normalizar_cedula,
    normalizar_ruc,
)


def _con_dv(base: str) -> str:
    return f"{base}-{calcular_dv(base)}"


class TestCalcularDv:
    def test_resultado_es_un_digito(self):
        for base in ["1", "123", "1234567", "80012345", "999999999"]:
            assert 0 <= calcular_dv(base) <= 9

    def test_resto_0_o_1_da_cero(self):
        # 11 -> 1*2 + 1*3 = 5 ; 5 % 11 = 5 -> 6 (control)
        assert calcular_dv("11") == 6
        # "0" -> total 0 -> resto 0 -> DV 0
        assert calcular_dv("0") == 0

    def test_rechaza_no_numericos(self):
        with pytest.raises(ValueError):
            calcular_dv("12a4")


class TestNormalizarCedula:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("1.234.567", "1234567"),
            ("1234567", "1234567"),
            (1234567, "1234567"),
            (1234567.0, "1234567"),
            ("1234567.0", "1234567"),
            ("  0001234567 ", "1234567"),
        ],
    )
    def test_formatos(self, entrada, esperado):
        assert normalizar_cedula(entrada) == esperado

    @pytest.mark.parametrize("entrada", [None, "", "nan", math.nan, "abc", "1234567890123"])
    def test_invalidos(self, entrada):
        assert normalizar_cedula(entrada) is None


class TestNormalizarRuc:
    def test_persona_fisica_con_dv_valido(self):
        r = normalizar_ruc(_con_dv("1234567"))
        assert r.base == "1234567"
        assert r.tipo is TipoContribuyente.FISICA
        assert r.dv_valido is True

    def test_prefijo_ocds_y_puntos(self):
        ruc = _con_dv("1234567")
        r = normalizar_ruc(f"PY-RUC-1.234.567-{ruc[-1]}")
        assert r.base == "1234567"
        assert r.dv_valido is True

    def test_dv_incorrecto(self):
        dv_malo = (calcular_dv("1234567") + 1) % 10
        r = normalizar_ruc(f"1234567-{dv_malo}")
        assert r.base == "1234567"
        assert r.dv_valido is False

    def test_persona_juridica(self):
        r = normalizar_ruc(_con_dv("80012345"))
        assert r.tipo is TipoContribuyente.JURIDICA

    def test_sin_dv(self):
        r = normalizar_ruc("1234567")
        assert r.base == "1234567"
        assert r.dv is None
        assert r.dv_valido is None

    @pytest.mark.parametrize("entrada", [None, "", "-", "PY-RUC-", "abc-1"])
    def test_invalidos(self, entrada):
        assert normalizar_ruc(entrada).tipo is TipoContribuyente.INVALIDO
