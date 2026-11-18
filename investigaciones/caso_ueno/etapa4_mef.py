"""Etapa 4 del caso ueno: serie mensual de fondos públicos en ueno bank (Informe de Bancos del MEF).

El MEF (Dirección General del Tesoro Público) publica cada mes un "Informe de Bancos" con los saldos de los
Organismos y Entidades del Estado (OEE, incluye fondos de seguridad social como el IPS) por banco y por
instrumento (cuenta corriente, depósito a la vista y CDA), en guaraníes y en dólares, y la calificación de riesgo
de cada banco. Este script baja todos los informes publicados y extrae la fila de UENO BANK y los totales.

Uso:
    python investigaciones/caso_ueno/etapa4_mef.py
Salidas: data/raw/mef/*.pdf (públicos, ignorados por git) y investigaciones/caso_ueno/serie_fondos_publicos_ueno.csv
(solo agregados institucionales, sin datos personales).
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import requests
from pypdf import PdfReader

PAGINA = ("https://www.mef.gov.py/es/dependencias/viceministerio-de-administracion-financiera/"
          "gerencia-de-gestion-financiera-del-estado/direccion-general-del-tesoro-publico/entidades-depositarias-fondos")
BASE = "https://www.mef.gov.py"
CACHE = Path("data/raw/mef")
SALIDA = Path("investigaciones/caso_ueno/serie_fondos_publicos_ueno.csv")
MESES = {m: i for i, m in enumerate(["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
                                     "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"], 1)}


def _numero(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def bajar(sesion: requests.Session) -> list[Path]:
    html = sesion.get(PAGINA, timeout=60).text
    rutas = []
    for href in sorted(set(re.findall(r'href="(/sites/default/files/[^"]+\.pdf)"', html))):
        destino = CACHE / unquote(href.split("/files/")[1]).replace("/", "_").replace(" ", "_")
        if not destino.exists():
            destino.write_bytes(sesion.get(BASE + href, timeout=120).content)
            time.sleep(1)
        rutas.append(destino)
    return rutas


def _seccion(texto: str, titulo: str) -> str:
    """Texto desde `titulo` hasta el siguiente 'TOTAL'."""
    i = texto.find(titulo)
    if i < 0:
        return ""
    j = texto.find("TOTAL", i)
    return texto[i:j + 40]


def _fila(seccion: str, banco: str = "UENO BANK") -> float | None:
    m = re.search(banco + r"\s+([\d.]+)\s+[\d,]+%", seccion)
    return _numero(m.group(1)) if m else None


def _total(seccion: str) -> float | None:
    m = re.search(r"TOTAL\s+([\d.]+)", seccion)
    return _numero(m.group(1)) if m else None


def extraer(ruta: Path) -> dict | None:
    paginas = [p.extract_text() or "" for p in PdfReader(ruta).pages]
    texto = "\n".join(paginas)
    # "al 28 de Febrero de 2026" (hasta 04-2026) o "al cierre de Septiembre de 2026" (desde 05-2026)
    m = re.search(r"Entidad Bancaria\s+al (?:\d{1,2}|cierre) de (\w+) de (\d{4})", texto, re.IGNORECASE)
    if not m or m.group(1).upper() not in MESES:
        return None
    fila = {"periodo": f"{m.group(2)}-{MESES[m.group(1).upper()]:02d}", "archivo": ruta.name}

    def pagina_con(*claves: str) -> str:
        return next((p for p in paginas if all(c.lower() in p.lower() for c in claves)), "")

    for instrumento, claves in [("total", ("Clasificación por Entidad Bancaria",)),
                                ("cuenta_corriente", ("Cuenta Corriente en USD",)),
                                ("vista", ("Depósitos a la Vista en USD",)),
                                ("cda", ("Certificado de Depósito de Ahorro",))]:
        pg = pagina_con(*claves)
        usd, pyg = _seccion(pg, "En Dólares"), _seccion(pg, "En Guaraníes")
        fila[f"ueno_{instrumento}_usd"] = _fila(usd) or 0.0 if pg else None
        fila[f"ueno_{instrumento}_pyg"] = _fila(pyg) or 0.0 if pg else None
        if instrumento == "total":
            fila["sistema_total_usd"], fila["sistema_total_pyg"] = _total(usd), _total(pyg)
    cal = re.search(r"UENO BANK\s+([A-D]{1,3}[+-]?py)\s+(\w+)\s+([^\n]+)", pagina_con("CALIFICACIÓN DE RIESGO"))
    if cal:
        fila["ueno_calificacion"], fila["ueno_tendencia"], fila["calificadora"] = cal.groups()
    return fila


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    sesion = requests.Session()
    sesion.headers["User-Agent"] = "Mozilla/5.0 TESA-tesis-UCOM (investigacion academica)"
    filas = [f for f in (extraer(r) for r in bajar(sesion)) if f]
    serie = pd.DataFrame(filas).sort_values("periodo").drop_duplicates("periodo", keep="last")
    serie["ueno_pct_usd"] = (100 * serie["ueno_total_usd"] / serie["sistema_total_usd"]).round(1)
    serie["ueno_pct_pyg"] = (100 * serie["ueno_total_pyg"] / serie["sistema_total_pyg"]).round(1)
    serie.to_csv(SALIDA, index=False)
    print(f"→ {SALIDA}: {len(serie)} meses ({serie['periodo'].min()} a {serie['periodo'].max()})")


if __name__ == "__main__":
    main()
