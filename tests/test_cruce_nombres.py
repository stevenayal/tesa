"""Datos 100 % ficticios: ningún nombre ni documento corresponde a personas reales."""

import pandas as pd
import pytest

from tesa.cruce_nombres import cruzar_por_nombre
from tesa.nombres import clave, normalizar_nombre
from tesa.padron_ruc import cargar_frecuencia_nombres, frecuencia_lineas


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


# --- frecuencia poblacional (padrón de RUC) ------------------------------------------------------

_PADRON_FICTICIO = [
    # RUC|NOMBRE|DV|RUC_ANTERIOR|ESTADO|  (personas y empresas inventadas)
    "1000001|QUINTANA DE VERA, ARIEL TOMAS|1|QUVA0000001|ACTIVO|",
    "9000001|OZUNA PERALTA, LUCIA BEATRIZ|2|OZPL0000001|ACTIVO|",
    "9000002|OZUNA  PERALTA, LUCÍA BEATRIZ|3|OZPL0000002|CANCELADO|",      # otra persona, mismo nombre
    "9000002A|OZUNA PERALTA, LUCIA BEATRIZ|3|OZPL0000002|CANCELADO|",     # mismo RUC con letra: no suma
    "80000099|OZUNA PERALTA, LUCIA BEATRIZ EIRL|4|EIRL0000001|ACTIVO|",   # persona jurídica con coma
    "80000098|FICTICIA SOCIEDAD ANONIMA|5|FSAX0000001|ACTIVO|",            # persona jurídica sin coma
    "80000097|COOPERATIVA FICTICIA DE AHORRO, CREDITO Y SERVICIOS|6|CFAC0000001|ACTIVO|",
    "9000003|M|LLER RODA, TEO ANSELMO|7|MRTA0000001|ACTIVO|",               # '|' dentro del nombre
]


def test_padron_cuenta_solo_personas_fisicas_distintas():
    frecuencia = frecuencia_lineas(linea + "\n" for linea in _PADRON_FICTICIO)
    assert frecuencia[clave(normalizar_nombre("LUCIA BEATRIZ", "OZUNA PERALTA"))] == 2
    assert frecuencia[clave(normalizar_nombre("ARIEL TOMAS", "QUINTANA DE VERA"))] == 1
    assert frecuencia[clave(normalizar_nombre("TEO ANSELMO", "LLER RODA"))] == 1
    assert sum(frecuencia.values()) == 4
    assert not any("COOPERATIVA" in k or "SOCIEDAD" in k or "EIRL" in k for k in frecuencia)


def test_cargar_frecuencia_desde_directorio(tmp_path):
    (tmp_path / "ruc0.txt").write_text("\n".join(_PADRON_FICTICIO[:3]) + "\n", encoding="utf-8")
    (tmp_path / "ruc1.txt").write_text("\n".join(_PADRON_FICTICIO[3:]) + "\n", encoding="utf-8")
    assert sum(cargar_frecuencia_nombres(tmp_path).values()) == 4


def test_cargar_frecuencia_sin_archivos(tmp_path):
    with pytest.raises(FileNotFoundError):
        cargar_frecuencia_nombres(tmp_path)


def test_homonimo_poblacional_pasa_a_ambigua():
    adjudicaciones = pd.DataFrame({"ruc": ["80000011-1"], "entidad": ["Ministerio Ficticio Uno"]})
    frecuencia = frecuencia_lineas(_PADRON_FICTICIO)
    resumen, detalle = cruzar_por_nombre(
        _nomina(), _proveedores(),
        col_doc="documento", col_nombres="nombres", col_apellidos="apellidos",
        col_entidad_nomina="entidad", adjudicaciones=adjudicaciones,
        frecuencia_poblacional=frecuencia,
    )
    filas = detalle.set_index("ruc_empresa")
    assert filas["nivel"].to_dict() == {
        "80000011-1": "alta",      # 1 persona en el país: se mantiene
        "80000022-2": "ambigua",   # única en la nómina, pero 2 personas en el país
        "80000033-3": "ambigua",   # aproximada: se evalúa el nombre de la nómina que coincidió
        "80000044-4": "ambigua",   # homónimos en la nómina (tiene prioridad)
    }
    assert filas["homonimos_pais"].to_dict() == {
        "80000011-1": 1, "80000022-2": 2, "80000033-3": 2, "80000044-4": 0,
    }
    assert filas.loc["80000022-2", "motivo"] == "homónimo poblacional"
    assert filas.loc["80000044-4", "motivo"] == "homónimos en la nómina"
    assert filas.loc["80000011-1", "motivo"] == ""
    assert resumen.coincidencias_por_nivel == {"alta": 1, "media": 0, "baja": 0, "ambigua": 3}
    assert resumen.alertas == 1


def test_nombre_ausente_del_padron_no_cambia_el_nivel():
    resumen, detalle = cruzar_por_nombre(
        _nomina(), _proveedores(),
        col_doc="documento", col_nombres="nombres", col_apellidos="apellidos",
        frecuencia_poblacional={},
    )
    assert resumen.coincidencias_por_nivel == {"alta": 0, "media": 2, "baja": 1, "ambigua": 1}
    assert (detalle["homonimos_pais"] == 0).all()


def test_sin_frecuencia_poblacional_columna_vacia():
    _, detalle = cruzar_por_nombre(
        _nomina(), _proveedores(),
        col_doc="documento", col_nombres="nombres", col_apellidos="apellidos",
    )
    assert "homonimos_pais" in detalle.columns
    assert detalle["homonimos_pais"].isna().all()
