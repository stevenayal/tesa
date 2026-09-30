"""Tests con datos 100% sintéticos (ninguna cédula real)."""

import pandas as pd

from tesa.factibilidad import cruzar, generar_reporte, main
from tesa.normalizacion import calcular_dv


def _ruc(base: str) -> str:
    return f"{base}-{calcular_dv(base)}"


def _datos():
    nomina = pd.DataFrame(
        {"documento": ["1.111.111", "2222222", "3333333", "3333333", "", "4444444"]}
    )
    proveedores = pd.DataFrame(
        {
            "ruc": [
                _ruc("1111111"),  # funcionario y proveedor
                _ruc("1111111"),  # repetido (otra adjudicación)
                f"PY-RUC-{_ruc('3333333')}",  # funcionario y proveedor
                _ruc("5555555"),  # proveedor que no es funcionario
                _ruc("80012345"),  # persona jurídica
                "basura",
            ]
        }
    )
    return nomina, proveedores


def test_cruce_cuenta_coincidencias():
    nomina, proveedores = _datos()
    r, detalle = cruzar(nomina, "documento", proveedores, "ruc")

    assert r.funcionarios_unicos == 4
    assert r.registros_nomina_invalidos == 1
    assert r.proveedores_unicos == 4
    assert r.proveedores_fisicos == 3
    assert r.proveedores_juridicos == 1
    assert r.proveedores_invalidos == 1
    assert r.coincidencias == 2
    assert list(detalle["documento"]) == ["1111111", "3333333"]
    assert detalle.set_index("documento").loc["1111111", "registros_como_proveedor"] == 2
    assert detalle.set_index("documento").loc["3333333", "registros_en_nomina"] == 2


def test_juridicas_nunca_cruzan():
    nomina = pd.DataFrame({"documento": ["80012345"]})
    proveedores = pd.DataFrame({"ruc": [_ruc("80012345")]})
    r, _ = cruzar(nomina, "documento", proveedores, "ruc")
    assert r.coincidencias == 0


def test_reporte_no_expone_documentos():
    nomina, proveedores = _datos()
    r, _ = cruzar(nomina, "documento", proveedores, "ruc")
    reporte = generar_reporte(r, "nomina.csv", "proveedores.csv")
    assert "1111111" not in reporte
    assert "3333333" not in reporte
    assert "Funcionarios que también son proveedores" in reporte


def test_cli_extremo_a_extremo(tmp_path):
    nomina, proveedores = _datos()
    ruta_n = tmp_path / "nomina.csv"
    ruta_p = tmp_path / "proveedores.csv"
    nomina.to_csv(ruta_n, index=False, sep=";", encoding="latin-1")
    proveedores.to_csv(ruta_p, index=False)
    reporte = tmp_path / "reporte.md"
    detalle = tmp_path / "out" / "detalle.csv"

    codigo = main(
        [
            "--nomina", str(ruta_n),
            "--proveedores", str(ruta_p),
            "--reporte", str(reporte),
            "--detalle", str(detalle),
            "--todos-los-rubros",
        ]
    )

    assert codigo == 0
    assert reporte.exists()
    assert len(pd.read_csv(detalle, dtype=str)) == 2


def test_cli_filtra_por_rubros_por_defecto(tmp_path):
    nomina = pd.DataFrame({"documento": ["1111111", "3333333"]})
    proveedores = pd.DataFrame(
        {
            "ruc": [_ruc("1111111"), _ruc("3333333")],
            "categoria": ["5 - Consultorías, Asesorías e Investigaciones", "20 - Minerales"],
        }
    )
    ruta_n = tmp_path / "nomina.csv"
    ruta_p = tmp_path / "proveedores.csv"
    nomina.to_csv(ruta_n, index=False)
    proveedores.to_csv(ruta_p, index=False)
    reporte = tmp_path / "reporte.md"
    detalle = tmp_path / "detalle.csv"

    main(["--nomina", str(ruta_n), "--proveedores", str(ruta_p),
          "--reporte", str(reporte), "--detalle", str(detalle)])

    # solo la consultoría (rubro 5) queda dentro del alcance
    assert list(pd.read_csv(detalle, dtype=str)["documento"]) == ["1111111"]
    assert "Alcance: 4 – Capacitaciones" in reporte.read_text(encoding="utf-8")


def test_cli_sin_columna_de_categoria_falla_con_mensaje_claro(tmp_path):
    import pytest

    nomina, proveedores = _datos()
    ruta_n = tmp_path / "nomina.csv"
    ruta_p = tmp_path / "proveedores.csv"
    nomina.to_csv(ruta_n, index=False)
    proveedores.to_csv(ruta_p, index=False)
    with pytest.raises(KeyError, match="--col-categoria"):
        main(["--nomina", str(ruta_n), "--proveedores", str(ruta_p),
              "--reporte", str(tmp_path / "r.md"), "--detalle", str(tmp_path / "d.csv")])
