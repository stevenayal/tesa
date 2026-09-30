import math

import pandas as pd
import pytest

from tesa.alcance import codigo_de_categoria, filtrar_por_rubros, parsear_rubros


@pytest.mark.parametrize(
    "valor,esperado",
    [
        ("24", 24),
        ("24.0", 24),
        (24, 24),
        (5.0, 5),
        ("4 - Capacitaciones y Adiestramientos", 4),
        ("Capacitaciones y Adiestramientos", 4),
        ("CONSULTORÍAS, ASESORÍAS E INVESTIGACIONES. ESTUDIOS Y PROYECTOS DE INVERSIÓN", 5),
        ("Consultorias, Asesorias e Investigaciones", 5),
        ("Equipos, accesorios y programas computacionales, de oficina, educativos", 24),
        ("20 - Minerales", 20),
    ],
)
def test_codigo_de_categoria(valor, esperado):
    assert codigo_de_categoria(valor) == esperado


@pytest.mark.parametrize("valor", [None, math.nan, "", "Minerales", "Equipos médicos"])
def test_categoria_no_reconocida(valor):
    assert codigo_de_categoria(valor) is None


def test_filtrar_por_rubros():
    df = pd.DataFrame({"categoria": ["4", "5 - Consultorías", "24", "20 - Minerales", None]})
    assert len(filtrar_por_rubros(df, "categoria")) == 3
    assert len(filtrar_por_rubros(df, "categoria", (24,))) == 1


def test_parsear_rubros():
    assert parsear_rubros("4, 5,24") == (4, 5, 24)
    with pytest.raises(ValueError):
        parsear_rubros("a,b")
    with pytest.raises(ValueError):
        parsear_rubros(" , ")
