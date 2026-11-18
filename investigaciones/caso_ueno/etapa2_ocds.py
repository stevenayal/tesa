"""Etapa 2 del caso ueno: indicadores de riesgo por licitación a partir de OCDS (API v3 de la DNCP).

Para cada licitación adjudicada desde 2019 a un proveedor del universo, baja el record OCDS
(sin token: /datos/api/v3/doc/ocds/record/{ocid}) y calcula:

- oferentes: cantidad y nombres; oferente único
- vinculados_compitiendo: dos o más oferentes del mismo grupo en la misma licitación (competencia aparente)
- plazo_dias: días entre la publicación del llamado y el cierre de ofertas
- ampliacion_pct: ampliaciones de monto / monto del contrato
- protestas: cantidad de protestas
- ratio_estimado: monto adjudicado al proveedor / monto estimado del llamado

Uso:
    python investigaciones/caso_ueno/etapa2_ocds.py           # descarga (con caché) y calcula
Salidas (privadas): data/raw/ueno/ocds/*.json, data/interim/ueno_licitaciones.csv
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from tesa.nombres import normalizar_nombre

API = "https://www.contrataciones.gov.py/datos/api/v3/doc/ocds/record/ocds-03ad3f-{}"
CACHE = Path("data/raw/ueno/ocds")
SALIDA = Path("data/interim/ueno_licitaciones.csv")
DESDE = "2019-01-01"

# nombres normalizados de oferentes por grupo de vínculo (para detectar competencia entre vinculadas)
GRUPOS = {
    "grupo_vazquez": ["TECHNOMA", "ITTI", "UENO SEGUROS", "ALFA SEGUROS", "DISCOVER PARAGUAY",
                      "IMPRESION DISTRIBUCION LOGISTICA", "OFFICE DESIGN", "FLEISCHMAN", "KONECTITTI",
                      "CONSORCIO MONITOREOS", "DATA MEC", "PARASUR TECHNOMA", "IDL JF"],
    "wels": ["WELS", "WELSAN", "WASTE SOLUTIONS", "PRO VERDE", "GREEN GARDEN", "ECO NORTE"],
    "seguridad": ["TSV", "DOBRESTEC", "PARAGUAY SECURITY", "URBIS", "CONSORCIO TRACK", "CONSORCIO TIC"],
}


def _grupo_de(nombre: str) -> str | None:
    n = normalizar_nombre(nombre)
    for grupo, claves in GRUPOS.items():
        if any(all(p in n.split() for p in c.split()) for c in claves):
            return grupo
    return None


def _fecha(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def bajar(id_licitacion: str, sesion: requests.Session) -> dict | None:
    ruta = CACHE / f"{id_licitacion}.json"
    if ruta.exists():
        return json.loads(ruta.read_text())
    for intento in range(4):
        try:
            r = sesion.get(API.format(id_licitacion), timeout=90)
            if r.status_code == 200:
                ruta.write_text(r.text)
                time.sleep(0.5)
                return r.json()
            if r.status_code == 404:
                return None
        except requests.RequestException:
            pass
        time.sleep(2 ** intento)
    return None


def indicadores(rec: dict, ruc_proveedor: str, nombre_proveedor: str) -> dict:
    cr = rec["records"][0]["compiledRelease"]
    t = cr.get("tender", {})
    oferentes = [o.get("name", "") for o in t.get("tenderers", [])]
    n_ofer = t.get("numberOfTenderers") or len(oferentes)
    grupos = [g for g in map(_grupo_de, oferentes) if g]
    vinculados = sorted({g for g in grupos if grupos.count(g) >= 2})

    publicado, cierre = _fecha(t.get("datePublished")), _fecha((t.get("tenderPeriod") or {}).get("endDate"))
    plazo = (cierre - publicado).days if publicado and cierre else None

    # adjudicaciones y contratos del proveedor (por nombre normalizado o RUC en parties)
    ids_prov = {p["id"] for p in cr.get("parties", [])
                if ruc_proveedor.split("-")[0] in json.dumps(p.get("identifier", {}))
                or normalizar_nombre(p.get("name", "")) == normalizar_nombre(nombre_proveedor)}
    awards = [a for a in cr.get("awards", []) if {s.get("id") for s in a.get("suppliers", [])} & ids_prov
              and a.get("status") != "unsuccessful"]
    monto_adj = sum((a.get("value") or {}).get("amount") or 0 for a in awards)
    award_ids = {a["id"] for a in awards}
    contratos = [c for c in cr.get("contracts", []) if c.get("awardID") in award_ids]
    monto_contr = sum((c.get("value") or {}).get("amount") or 0 for c in contratos)
    ampliado = sum(((m.get("amendsAmount") or {}).get("amount") or 0)
                   for c in contratos for m in c.get("amendments", []) or [])
    estimado = (t.get("value") or {}).get("amount")

    return {
        "titulo": t.get("title"),
        "metodo": t.get("procurementMethodDetails"),
        "convocante": (cr.get("buyer") or {}).get("name"),
        "publicado": publicado.date().isoformat() if publicado else None,
        "plazo_dias": plazo,
        "n_oferentes": n_ofer,
        "oferente_unico": n_ofer == 1,
        "oferentes": "; ".join(oferentes),
        "vinculados_compitiendo": ", ".join(vinculados),
        "protestas": len(cr.get("complaints", []) or []),
        "estimado": estimado,
        "monto_adj_ocds": monto_adj,
        "ratio_estimado": round(monto_adj / estimado, 3) if estimado and monto_adj else None,
        "monto_contratos": monto_contr,
        "ampliado": ampliado,
        "ampliacion_pct": round(100 * ampliado / monto_contr, 1) if monto_contr else None,
    }


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    adj = pd.read_csv("data/raw/ueno/adjudicaciones_enriquecidas.csv", dtype=str, parse_dates=["fecha"])
    adj = adj[adj["fecha"] >= DESDE].drop_duplicates(["id_licitacion", "ruc"])
    sesion = requests.Session()
    sesion.headers["User-Agent"] = "TESA-tesis-UCOM (investigacion academica)"
    filas = []
    for i, f in enumerate(adj.itertuples(), 1):
        rec = bajar(f.id_licitacion, sesion)
        base = {"id_licitacion": f.id_licitacion, "ruc": f.ruc, "proveedor": f.proveedor, "grupo": f.grupo,
                "fecha_resolucion": f.fecha.date().isoformat(), "monto_gs": f.monto_gs,
                "periodo": f.periodo, "procedimiento": f.procedimiento}
        filas.append({**base, **(indicadores(rec, f.ruc, f.proveedor) if rec else {"error": "sin record"})})
        if i % 50 == 0:
            print(f"{i}/{len(adj)}", flush=True)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(filas).to_csv(SALIDA, index=False)
    print(f"→ {SALIDA}: {len(filas)} filas")


if __name__ == "__main__":
    main()
