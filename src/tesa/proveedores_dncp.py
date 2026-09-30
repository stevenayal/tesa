"""Extractor de proveedores del buscador público de la DNCP, por rubro.

Fuente: https://www.contrataciones.gov.py/buscador/proveedores.html
(robots.txt de contrataciones.gov.py: "Allow: all").

El buscador devuelve HTML renderizado en el servidor, 10 proveedores por página.
El filtro usa IDs internos distintos del código visible de la categoría:

    código visible 4  -> ID interno 20   (Capacitaciones y Adiestramientos)
    código visible 5  -> ID interno 21   (Consultorías, Asesorías e Investigaciones)
    código visible 24 -> ID interno 40   (Equipos, accesorios y programas computacionales)

Minimización de datos: solo se guardan RUC, razón social, nombre de fantasía,
enlace al perfil y rubro. Se descartan representante legal, dirección, teléfono
y correo, porque no hacen falta para el cruce.

IMPORTANTE: esta lista contiene proveedores *inscriptos* en cada rubro, no
proveedores *adjudicados*. Sirve para la fase 1; el cruce final debe hacerse
contra adjudicaciones.

Uso:
    python -m tesa.proveedores_dncp --salida data/raw/proveedores.csv
    python -m tesa.proveedores_dncp --rubros 5 --max-paginas 3   # prueba corta
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from tesa.alcance import RUBROS, RUBROS_POR_DEFECTO, parsear_rubros

URL_BASE = "https://www.contrataciones.gov.py"
URL_BUSCADOR = URL_BASE + "/buscador/proveedores.html"

# código visible de la categoría -> ID interno del filtro del buscador
ID_INTERNO: dict[int, int] = {4: 20, 5: 21, 24: 40}

POR_PAGINA = 10
USER_AGENT = "TESA/0.1 (tesis academica UCOM; datos abiertos DNCP)"

_TOTAL = re.compile(r"Se muestran del \d+ al \d+ de ([\d.]+) resultados")
CAMPOS = ["ruc", "razon_social", "nombre_fantasia", "perfil_url", "categoria", "categoria_nombre"]


@dataclass(frozen=True)
class Proveedor:
    ruc: str
    razon_social: str
    nombre_fantasia: str
    perfil_url: str
    categoria: int
    categoria_nombre: str


def _limpiar(texto: str | None) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def total_resultados(html: str) -> int | None:
    """Lee 'Se muestran del 1 al 10 de 7601 resultados'."""
    m = _TOTAL.search(html)
    return int(m.group(1).replace(".", "")) if m else None


def parsear_pagina(html: str, categoria: int) -> list[Proveedor]:
    """Extrae los proveedores de una página de resultados."""
    soup = BeautifulSoup(html, "html.parser")
    proveedores: list[Proveedor] = []
    for articulo in soup.find_all("article"):
        enlace = articulo.select_one("header h3 a") or articulo.find("a")
        if enlace is None:
            continue
        campos: dict[str, str] = {}
        for etiqueta in articulo.select("span.info-label"):
            valor = etiqueta.find_next_sibling("em")
            if valor is not None:
                campos[_limpiar(etiqueta.get_text()).lower()] = _limpiar(valor.get_text())
        ruc = campos.get("ruc", "")
        if not ruc:
            continue
        proveedores.append(
            Proveedor(
                ruc=ruc,
                razon_social=_limpiar(enlace.get_text()),
                nombre_fantasia=campos.get("nombre de fantasía", ""),
                perfil_url=urljoin(URL_BASE, enlace.get("href", "")),
                categoria=categoria,
                categoria_nombre=RUBROS.get(categoria, ""),
            )
        )
    return proveedores


def url_pagina(categoria: int, pagina: int) -> str:
    if categoria not in ID_INTERNO:
        raise ValueError(
            f"Rubro {categoria} sin ID interno conocido. Rubros disponibles: {sorted(ID_INTERNO)}"
        )
    return (
        f"{URL_BUSCADOR}?proveedor=&categorias_proveedor%5B%5D={ID_INTERNO[categoria]}"
        f"&page={pagina}"
    )


def _descargar(sesion, url: str, reintentos: int = 3, pausa: float = 1.0) -> str:
    ultimo: Exception | None = None
    for intento in range(1, reintentos + 1):
        try:
            respuesta = sesion.get(url, timeout=30)
            if respuesta.status_code == 200:
                return respuesta.text
            ultimo = RuntimeError(f"HTTP {respuesta.status_code}")
        except Exception as e:  # red inestable: reintentar
            ultimo = e
        time.sleep(pausa * 2**intento)
    raise RuntimeError(f"No se pudo descargar {url}: {ultimo}")


def _progreso_previo(salida: Path) -> dict[int, int]:
    """Para reanudar: cuántos proveedores ya hay guardados por rubro."""
    if not salida.exists():
        return {}
    conteo: dict[int, int] = {}
    with salida.open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            cat = int(fila["categoria"])
            conteo[cat] = conteo.get(cat, 0) + 1
    return conteo


def extraer(
    rubros: tuple[int, ...],
    salida: Path,
    pausa: float = 1.0,
    max_paginas: int | None = None,
    sesion=None,
) -> dict[int, int]:
    """Recorre el buscador y agrega filas a `salida`. Devuelve filas nuevas por rubro."""
    if sesion is None:
        import requests

        sesion = requests.Session()
        sesion.headers["User-Agent"] = USER_AGENT

    salida.parent.mkdir(parents=True, exist_ok=True)
    previo = _progreso_previo(salida)
    nuevo_archivo = not salida.exists()
    nuevas: dict[int, int] = {}

    with salida.open("a", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS)
        if nuevo_archivo:
            escritor.writeheader()

        for categoria in rubros:
            html = _descargar(sesion, url_pagina(categoria, 1), pausa=pausa)
            total = total_resultados(html) or 0
            paginas = math.ceil(total / POR_PAGINA)
            if max_paginas is not None:
                paginas = min(paginas, max_paginas)
            ya_guardados = previo.get(categoria, 0)
            nuevas[categoria] = 0
            if total and ya_guardados >= total:
                print(f"Rubro {categoria}: completo ({ya_guardados:,}), se omite", file=sys.stderr)
                continue
            inicio = ya_guardados // POR_PAGINA + 1
            print(
                f"Rubro {categoria}: {total:,} proveedores, {paginas} páginas "
                f"(desde la página {inicio})",
                file=sys.stderr,
            )
            for pagina in range(inicio, paginas + 1):
                if pagina > 1:
                    time.sleep(pausa)
                    html = _descargar(sesion, url_pagina(categoria, pagina), pausa=pausa)
                filas = parsear_pagina(html, categoria)
                if not filas:
                    break
                escritor.writerows(asdict(p) for p in filas)
                f.flush()
                nuevas[categoria] += len(filas)
                if pagina % 50 == 0:
                    print(f"  página {pagina}/{paginas}", file=sys.stderr)
    return nuevas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--salida", default="data/raw/proveedores.csv")
    parser.add_argument(
        "--rubros", default=",".join(str(c) for c in RUBROS_POR_DEFECTO),
        help="Códigos visibles de categoría (por defecto: 4,5,24)",
    )
    parser.add_argument("--pausa", type=float, default=1.0, help="Segundos entre páginas")
    parser.add_argument("--max-paginas", type=int, help="Límite de páginas por rubro (pruebas)")
    args = parser.parse_args(argv)

    nuevas = extraer(parsear_rubros(args.rubros), Path(args.salida), args.pausa, args.max_paginas)
    for categoria, n in nuevas.items():
        print(f"Rubro {categoria}: {n:,} filas nuevas")
    print(f"Archivo: {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
