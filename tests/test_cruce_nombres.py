"""Datos 100 % ficticios: ningún nombre ni documento corresponde a personas reales."""

import pandas as pd

from tesa.cruce_nombres import cruzar_por_nombre


def _nomina():
    return pd.DataFrame(
        {
            "documento": ["1000001", "1000002", "1000003", "1000004", "ANON999", "VAC1"],
            "nombres": ["ARIEL TOMAS", "LUCIA BEATRIZ", "MARCO ANTONIO", "MARCO ANTONIO",
                        "NOMBRES DEL FUNCIONARIO", "VACANTE"],
            "apellidos": ["QUINTANA DE VERA", "OZUNA PERALTA", "SALDIVAR MENA", "SALDIVAR MENA",
                          "APELLIDOS DEL FUNCIONARIO", "VACANTE"],
            "entidad": ["MINISTERIO FICTICIO UNO", "MINISTERIO FICTICIO DOS",
                        "ENTE FICTICIO", "OTRO ENTE", "DEFENSA", ""],
        }
    )


def _proveedores():
    return pd.DataFrame(
        {
            "ruc": ["80000011-1", "80000022-2", "80000033-3", "80000044-4", "80000055-5", "80000066-6"],
            "representante_legal": [
                "Ariel Tomás Quintana de Vera",   # exacta, única, misma entidad -> alta
                "LUCIA BEATRIZ OZUNA PERALTA",    # exacta, única -> media
                "LUCIA BEATRIS OZUNA PERALTA",    # tipeo -> baja
                "MARCO ANTONIO SALDIVAR MENA",    # homónimos -> ambigua
                "JUAN PEREZ",                     # < 3 palabras -> se descarta
                "PERSONA INEXISTENTE EN NOMINA",  # sin coincidencia
            ],
        }
    )


def test_niveles_de_confianza():
    adjudicaciones = pd.DataFrame({"ruc": ["80000011-1"], "entidad": ["Ministerio Ficticio Uno"]})
    resumen, detalle = cruzar_por_nombre(
        _nomina(), _proveedores(),
        col_doc="documento", col_nombres="nombres", col_apellidos="apellidos",
        col_entidad_nomina="entidad", adjudicaciones=adjudicaciones,
    )
    niveles = dict(zip(detalle["ruc_empresa"], detalle["nivel"]))
    assert niveles == {
        "80000011-1": "alta",
        "80000022-2": "media",
        "80000033-3": "baja",
        "80000044-4": "ambigua",
    }
    assert resumen.representantes_validos == 5
    assert resumen.coincidencias_por_nivel == {"alta": 1, "media": 1, "baja": 1, "ambigua": 1}
    assert resumen.alertas == 3


def test_sin_adjudicaciones_no_hay_confianza_alta():
    resumen, _ = cruzar_por_nombre(
        _nomina(), _proveedores(),
        col_doc="documento", col_nombres="nombres", col_apellidos="apellidos",
        col_entidad_nomina="entidad",
    )
    assert resumen.coincidencias_por_nivel["alta"] == 0
    assert resumen.coincidencias_por_nivel["media"] == 2


def test_ignora_documentos_anonimizados_y_vacantes():
    proveedores = pd.DataFrame(
        {"ruc": ["80000077-7"], "representante_legal": ["NOMBRES DEL FUNCIONARIO APELLIDOS DEL FUNCIONARIO"]}
    )
    _, detalle = cruzar_por_nombre(
        _nomina(), proveedores, col_doc="documento", col_nombres="nombres", col_apellidos="apellidos",
    )
    assert detalle.empty
