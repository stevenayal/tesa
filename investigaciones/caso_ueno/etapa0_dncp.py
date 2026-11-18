"""Etapa 0 del caso ueno: perfiles, adjudicaciones y contratos de proveedores en el buscador de la DNCP.

Para cada proveedor de la lista (slug del buscador y grupo de vínculo) baja su ficha (RUC, representante legal),
todas sus adjudicaciones y, por cada contrato, la fecha de resolución, montos, pagos y administrador. Después
normaliza montos y fechas y marca el período (antes o desde el 15-08-2023).

Uso:
    python investigaciones/caso_ueno/etapa0_dncp.py

Entrada (privada): data/interim/ueno_proveedores.csv con columnas slug,grupo
Salidas (privadas): data/raw/ueno/perfiles.json, adjudicaciones.csv y adjudicaciones_enriquecidas.csv
"""

from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = "https://www.contrataciones.gov.py"
ENTRADA = Path("data/interim/ueno_proveedores.csv")
SALIDA = Path("data/raw/ueno")
CAMBIO_DE_GOBIERNO = pd.Timestamp("2023-08-15")
ETIQUETAS_CONTRATO = [
    "Administrador del Contrato", "Fecha de la Resolución", "Código de Contratación (CC)", "Emisión del CC",
    "Monto Adjudicado", "Número de Contrato", "Monto Total de Contratación", "Fecha de Firma del Contrato",
    "Vigencia del Contrato", "Fecha de Inicio de Ejecución", "Fecha de Fin de Ejecución",
    "Total Pagado por el Contrato", "Total Pagado (transferencia/cheque) al Proveedor", "Datos de la Licitación",
]


def _get(sesion: requests.Session, url: str) -> str:
    for intento in range(4):
        try:
            r = sesion.get(url, timeout=60)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass
        time.sleep(2 ** intento)
    raise RuntimeError(f"No se pudo descargar {url}")


def _texto(html: str) -> str:
    return " ".join(BeautifulSoup(html, "html.parser").get_text(" ").split())


def _campo(texto: str, etiqueta: str, siguientes: list[str]) -> str:
    m = re.search(re.escape(etiqueta) + r" (.*?) (?:" + "|".join(map(re.escape, siguientes)) + ")", texto)
    return m.group(1).strip() if m else ""


def perfil(sesion: requests.Session, slug: str) -> dict:
    t = _texto(_get(sesion, f"{BASE}/proveedor/{slug}.html"))
    return {
        "slug": slug,
        "nombre": _campo(t, "Proveedor", ["RUC"]).split("Proveedor ")[-1].strip(),
        "ruc": _campo(t, "RUC", ["Nombre de Fantasía"]),
        "representante_legal": _campo(t, "Representante Legal", ["Tipo de Proveedor"]),
        "fecha_inscripcion": _campo(t, "Fecha de Inscripción", ["Fecha de Activación"]),
    }


def adjudicaciones(sesion: requests.Session, slug: str) -> list[dict]:
    filas, pagina = [], 1
    while True:
        s = BeautifulSoup(_get(sesion, f"{BASE}/proveedor/{slug}/adjudicaciones.html?page={pagina}"), "html.parser")
        nuevas = 0
        for tr in s.select("table tr")[1:]:
            td = [" ".join(c.get_text(" ").split()) for c in tr.select("td")]
            if len(td) < 7:
                continue
            enlaces = [a.get("href") for a in tr.select("a") if a.get("href")]
            filas.append({
                "id_licitacion": td[0], "nombre": td[1], "categoria": td[2], "procedimiento": td[3],
                "convocante": td[4], "monto_adjudicado": td[5], "estado": td[6],
                "url_contrato": next((h for h in enlaces if "/contrato/" in h), ""),
            })
            nuevas += 1
        if not nuevas or not s.select(f'a[href$="page={pagina + 1}"]'):
            return filas
        pagina += 1
        time.sleep(0.7)


def contrato(sesion: requests.Session, url: str) -> dict:
    t = _texto(_get(sesion, BASE + url))
    datos = {k: _campo(t, k, [e for e in ETIQUETAS_CONTRATO if e != k])
             for k in ["Fecha de la Resolución", "Monto Total de Contratación", "Fecha de Firma del Contrato",
                       "Fecha de Fin de Ejecución", "Total Pagado por el Contrato", "Administrador del Contrato"]}
    datos["sistema_adjudicacion"] = _campo(t, "Sistema de Adjudicación", ["Compartir"])
    return datos


def _guaranies(valor: str) -> float | None:
    valor = str(valor).strip()
    return float(re.sub(r"[^\d]", "", valor) or 0) if valor.startswith("₲") else None


def enriquecer(df: pd.DataFrame) -> pd.DataFrame:
    df["moneda"] = df["monto_adjudicado"].str.extract(r"^(\S+)")[0]
    df["monto_gs"] = df["monto_adjudicado"].map(_guaranies)
    df["fecha"] = pd.to_datetime(df["Fecha de la Resolución"].str[:10], format="%d-%m-%Y", errors="coerce")
    df["periodo"] = df["fecha"].map(
        lambda f: "sin_fecha" if pd.isna(f) else ("1_antes_08-2023" if f < CAMBIO_DE_GOBIERNO else "2_desde_08-2023"))
    return df


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    sesion = requests.Session()
    sesion.headers["User-Agent"] = "TESA-tesis-UCOM (investigacion academica)"
    proveedores = list(csv.DictReader(ENTRADA.open()))
    perfiles, todas = [], []
    for p in proveedores:
        pf = {**perfil(sesion, p["slug"]), "grupo": p["grupo"]}
        perfiles.append(pf)
        filas = adjudicaciones(sesion, p["slug"])
        print(f"{pf['nombre']} ({pf['ruc']}): {len(filas)} adjudicaciones", flush=True)
        for f in filas:
            f.update(slug=p["slug"], proveedor=pf["nombre"], ruc=pf["ruc"], grupo=p["grupo"])
            if f["url_contrato"]:
                f.update(contrato(sesion, f["url_contrato"]))
                time.sleep(0.5)
            todas.append(f)
        time.sleep(1)
    (SALIDA / "perfiles.json").write_text(json.dumps(perfiles, ensure_ascii=False, indent=1))
    df = pd.DataFrame(todas).fillna("")
    df.to_csv(SALIDA / "adjudicaciones.csv", index=False)
    enriquecer(df).to_csv(SALIDA / "adjudicaciones_enriquecidas.csv", index=False)
    print(f"→ {SALIDA}: {len(df)} adjudicaciones de {len(perfiles)} proveedores")


if __name__ == "__main__":
    main()
