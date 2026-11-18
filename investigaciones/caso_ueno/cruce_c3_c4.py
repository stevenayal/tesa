"""Cruces C3 y C4 del caso ueno (etapa 3).

C3a  Imputados de la causa 89/2026 (directivos de ueno y de empresas vinculadas) × nómina pública 2023–2026:
     ¿alguno fue a la vez funcionario? (puerta giratoria o doble rol).
C3b  Decisores de las entidades clave (BCP, IPS, MEF, DNIT, Conatel, Mitic, ANDE, BNF, Presidencia) ×
     apellidos poco frecuentes del universo del grupo: posible parentesco (indicio débil, solo para revisión).
C4   Administradores de los contratos del grupo × universo de personas; y concentración de contratos del
     grupo en un mismo administrador.

Toda coincidencia por nombre se controla contra el padrón de RUC de la DNIT (homónimos en el país) y requiere
revisión humana. Detalle privado en data/output/.

Uso:
    python investigaciones/caso_ueno/cruce_c3_c4.py
"""

from __future__ import annotations

import glob
from collections import Counter
from pathlib import Path

import pandas as pd

from tesa.cruce_nombres import cruzar_por_nombre
from tesa.nombres import clave, normalizar_nombre

SALIDA = Path("data/output")
# apellidos del universo que son poco frecuentes en Paraguay (los comunes como VAZQUEZ o GOMEZ no sirven)
UMBRAL_APELLIDO_RARO = 300


def padron_personas() -> tuple[Counter, Counter]:
    """Frecuencia de nombres completos y de apellidos entre las personas físicas del padrón de RUC."""
    nombres, apellidos = Counter(), Counter()
    for archivo in glob.glob("data/raw/ruc/ruc*.txt"):
        with open(archivo, encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                partes = linea.split("|")
                if len(partes) < 2 or "," not in partes[1]:
                    continue
                ap, no = partes[1].split(",", 1)
                nombres[clave(normalizar_nombre(no, ap))] += 1
                for a in normalizar_nombre(ap).split():
                    apellidos[a] += 1
    return nombres, apellidos


def c3a_imputados(nomina: pd.DataFrame, personas: pd.DataFrame, frec: Counter) -> pd.DataFrame:
    imp = personas[personas["rol"].str.startswith("imputado")].copy()
    imp["id"] = "I" + imp.index.astype(str)
    _, det = cruzar_por_nombre(nomina, imp, col_doc="documento", col_nombres="nombres",
                               col_apellidos="apellidos", col_ruc="id", col_representante="nombre")
    det = det.rename(columns={"ruc_empresa": "id"}).merge(imp, on="id")
    det["homonimos_pais"] = det["nombre"].map(lambda n: frec.get(clave(normalizar_nombre(n)), 0))
    filas = []
    for _, d in det.iterrows():
        for doc in d["documentos"].split(";"):
            for _, c in nomina[nomina["documento"] == doc].iterrows():
                filas.append({"nombre": d["nombre"], "rol": d["rol"], "empresa": d["empresa_o_entidad"],
                              "nivel": d["nivel"], "homonimos_pais": d["homonimos_pais"],
                              "entidad": c["descripcion_entidad"], "cargo": c["cargo"], "funcion": c["funcion"],
                              "desde": c["primer_mes"], "hasta": c["ultimo_mes"]})
    print(f"C3a · imputados cruzables: {len(imp)} · coincidencias: {det['nivel'].value_counts().to_dict()}")
    return pd.DataFrame(filas)


def c3b_apellidos(decisores: pd.DataFrame, personas: pd.DataFrame, frec_ap: Counter) -> pd.DataFrame:
    raros = {}
    for _, p in personas.iterrows():
        for a in normalizar_nombre(p["nombre"]).split():
            if len(a) > 3 and 0 < frec_ap.get(a, 0) <= UMBRAL_APELLIDO_RARO:
                raros.setdefault(a, set()).add(p["nombre"])
    filas = []
    for _, d in decisores.iterrows():
        for a in set(normalizar_nombre(d["apellidos"]).split()) & set(raros):
            filas.append({"decisor": f"{d['nombres']} {d['apellidos']}", "entidad": d["descripcion_entidad"],
                          "cargo": d["funcion"] or d["cargo"], "desde": d["primer_mes"], "hasta": d["ultimo_mes"],
                          "apellido": a, "personas_por_pais_con_ese_apellido": frec_ap[a],
                          "comparte_con": "; ".join(sorted(raros[a]))})
    print(f"C3b · apellidos raros en el universo: {len(raros)} · decisores que comparten alguno: "
          f"{len({f['decisor'] for f in filas})}")
    return pd.DataFrame(filas).drop_duplicates()


def c4_administradores(nomina: pd.DataFrame, personas: pd.DataFrame, frec: Counter) -> pd.DataFrame:
    adj = pd.read_csv("data/raw/ueno/adjudicaciones_enriquecidas.csv", dtype=str, parse_dates=["fecha"])
    adj = adj[adj["grupo"].str.match(r"A_grupo|B_familia|C_") & (adj["fecha"] >= "2019-01-01")]
    adm = adj[adj["Administrador del Contrato"].fillna("").str.strip() != ""].copy()
    adm["clave"] = adm["Administrador del Contrato"].map(lambda n: clave(normalizar_nombre(n)))
    conc = (adm.groupby(["clave", "convocante"])
            .agg(administrador=("Administrador del Contrato", "first"), contratos=("id_licitacion", "nunique"),
                 proveedores=("proveedor", lambda s: ", ".join(sorted(set(s)))),
                 monto_M=("monto_gs", lambda s: round(pd.to_numeric(s).sum() / 1e6)))
            .reset_index().sort_values("contratos", ascending=False))
    claves_universo = {clave(normalizar_nombre(n)): n for n in personas["nombre"]}
    conc["coincide_con_universo"] = conc["clave"].map(claves_universo)
    print(f"C4 · contratos del grupo con administrador: {adm['id_licitacion'].nunique()} · administradores: "
          f"{conc['clave'].nunique()} · que coinciden con el universo: {conc['coincide_con_universo'].notna().sum()}")
    return conc.drop(columns=["clave"])


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    nomina = pd.read_csv("data/interim/nomina_2023_2026.csv.gz", dtype=str)
    personas = pd.read_csv("data/interim/universo_personas.csv", dtype=str)
    decisores = pd.read_csv("data/interim/ueno_decisores.csv", dtype=str)
    frec, frec_ap = padron_personas()
    c3a_imputados(nomina, personas, frec).to_csv(SALIDA / "ueno_c3a_imputados.csv", index=False)
    c3b_apellidos(decisores, personas, frec_ap).to_csv(SALIDA / "ueno_c3b_apellidos.csv", index=False)
    c4_administradores(nomina, personas, frec).to_csv(SALIDA / "ueno_c4_administradores.csv", index=False)
    print(f"→ {SALIDA}/ueno_c3a_imputados.csv, ueno_c3b_apellidos.csv, ueno_c4_administradores.csv (privados)")


if __name__ == "__main__":
    main()
