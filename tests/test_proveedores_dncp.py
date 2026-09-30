"""Tests del extractor con HTML sintético (misma estructura que el buscador, datos ficticios)."""

import csv

import pytest

from tesa.proveedores_dncp import extraer, parsear_pagina, total_resultados, url_pagina


def _articulo(nombre: str, slug: str, ruc: str) -> str:
    return f"""
    <article>
      <header><h3><a href="/proveedor/{slug}.html">{nombre}</a><span class="tags"></span></h3></header>
      <div class="row info vcenter">
        <div class="row"><div><span class="info-label">Nombre de Fantasía</span> <em>{nombre} FANTASIA</em></div></div>
        <div class="row"><div><span class="info-label">RUC</span> <em>{ruc}</em></div></div>
        <div class="row"><div><span class="info-label">Representante Legal</span> <em>PERSONA FICTICIA</em></div></div>
        <div class="row"><div><span class="info-label">Teléfono</span> <em>000000</em></div></div>
        <div class="row"><div><span class="info-label">Correo Electrónico</span> <em>x@ejemplo.test</em></div></div>
      </div>
    </article>"""


def _pagina(total: int, articulos: list[str]) -> str:
    return f"<html><body><p>Se muestran del 1 al 10 de {total} resultados</p>{''.join(articulos)}</body></html>"


def test_total_resultados():
    assert total_resultados("Se muestran del 1 al 10 de 7601 resultados") == 7601
    assert total_resultados("Se muestran del 1 al 10 de 10.811 resultados") == 10811
    assert total_resultados("sin resultados") is None


def test_parsear_pagina_minimiza_datos():
    html = _pagina(2, [_articulo("EMPRESA UNO S.A.", "empresa-uno", "80000001-1"),
                       _articulo("PERSONA DOS", "persona-dos", "1234567-8")])
    filas = parsear_pagina(html, 5)
    assert [f.ruc for f in filas] == ["80000001-1", "1234567-8"]
    assert filas[0].perfil_url == "https://www.contrataciones.gov.py/proveedor/empresa-uno.html"
    assert filas[0].nombre_fantasia == "EMPRESA UNO S.A. FANTASIA"
    assert filas[0].categoria == 5
    # representante legal: solo para personas jurídicas
    assert filas[0].representante_legal == "PERSONA FICTICIA"
    assert filas[1].representante_legal == ""
    # no se guardan datos de contacto
    assert not hasattr(filas[0], "telefono")
    assert "x@ejemplo.test" not in repr(filas)


def test_url_pagina_usa_id_interno():
    assert "categorias_proveedor%5B%5D=21" in url_pagina(5, 3)
    assert url_pagina(5, 3).endswith("page=3")
    with pytest.raises(ValueError):
        url_pagina(99, 1)


class _Respuesta:
    def __init__(self, texto: str):
        self.status_code = 200
        self.text = texto


class _SesionFalsa:
    """Simula el buscador: 12 proveedores del rubro 4 -> 2 páginas."""

    def __init__(self):
        self.urls: list[str] = []

    def get(self, url, timeout=None):
        self.urls.append(url)
        pagina = int(url.rsplit("page=", 1)[1])
        n = 10 if pagina == 1 else 2
        arts = [_articulo(f"P{pagina}-{i}", f"p{pagina}-{i}", f"{1000000 + pagina * 100 + i}-0")
                for i in range(n)]
        return _Respuesta(_pagina(12, arts))


def test_extraer_y_reanudar(tmp_path):
    salida = tmp_path / "proveedores.csv"
    sesion = _SesionFalsa()
    nuevas = extraer((4,), salida, pausa=0, sesion=sesion)
    assert nuevas == {4: 12}
    with salida.open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 12
    assert set(filas[0]) == {"ruc", "razon_social", "nombre_fantasia", "representante_legal",
                             "perfil_url", "categoria", "categoria_nombre"}

    # segunda corrida: ya está completo, no agrega nada
    nuevas = extraer((4,), salida, pausa=0, sesion=_SesionFalsa())
    assert nuevas == {4: 0}
