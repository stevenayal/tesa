"""Fase 1 — prueba de factibilidad del cruce nómina × proveedores del Estado.

Pregunta que responde: ¿cuántos proveedores del Estado (personas físicas)
aparecen también en la nómina de funcionarios públicos?

Uso:
    python -m tesa.factibilidad --nomina data/raw/nomina.csv \
        --proveedores data/raw/proveedores.csv
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from tesa.alcance import (
    CANDIDATAS_CATEGORIA,
    RUBROS,
    RUBROS_POR_DEFECTO,
    filtrar_por_rubros,
    parsear_rubros,
)
from tesa.ingesta import (
    CANDIDATAS_NOMINA,
    CANDIDATAS_PROVEEDORES,
    detectar_columna,
    leer_csv,
)
from tesa.normalizacion import TipoContribuyente, normalizar_cedula, normalizar_ruc


@dataclass(frozen=True)
class ResultadoFactibilidad:
    funcionarios_unicos: int
    registros_nomina_invalidos: int
    proveedores_unicos: int
    proveedores_fisicos: int
    proveedores_juridicos: int
    proveedores_invalidos: int
    proveedores_dv_incorrecto: int
    coincidencias: int

    @property
    def tasa_sobre_fisicos(self) -> float:
        return self.coincidencias / self.proveedores_fisicos if self.proveedores_fisicos else 0.0

    @property
    def tasa_sobre_funcionarios(self) -> float:
        return (
            self.coincidencias / self.funcionarios_unicos if self.funcionarios_unicos else 0.0
        )

    @property
    def proporcion_juridicos(self) -> float:
        return self.proveedores_juridicos / self.proveedores_unicos if self.proveedores_unicos else 0.0


def cruzar(
    nomina: pd.DataFrame,
    col_nomina: str,
    proveedores: pd.DataFrame,
    col_proveedores: str,
) -> tuple[ResultadoFactibilidad, pd.DataFrame]:
    """Cruza cédulas de la nómina con RUC de personas físicas proveedoras."""
    cedulas = nomina[col_nomina].map(normalizar_cedula)
    invalidos_nomina = int(cedulas.isna().sum())
    conteo_nomina = cedulas.dropna().value_counts()

    rucs = proveedores[col_proveedores].map(normalizar_ruc)
    prov = pd.DataFrame(
        {
            "base": [r.base for r in rucs],
            "tipo": [r.tipo.value for r in rucs],
            "dv_valido": [r.dv_valido for r in rucs],
        }
    )
    validos = prov[prov["tipo"] != TipoContribuyente.INVALIDO.value]
    unicos = validos.drop_duplicates("base")
    fisicos = unicos[unicos["tipo"] == TipoContribuyente.FISICA.value]
    conteo_prov = validos[validos["tipo"] == TipoContribuyente.FISICA.value]["base"].value_counts()

    comunes = sorted(set(fisicos["base"]) & set(conteo_nomina.index))
    detalle = pd.DataFrame(
        {
            "documento": comunes,
            "registros_en_nomina": [int(conteo_nomina[c]) for c in comunes],
            "registros_como_proveedor": [int(conteo_prov[c]) for c in comunes],
        }
    )

    resultado = ResultadoFactibilidad(
        funcionarios_unicos=int(conteo_nomina.size),
        registros_nomina_invalidos=invalidos_nomina,
        proveedores_unicos=int(len(unicos)),
        proveedores_fisicos=int(len(fisicos)),
        proveedores_juridicos=int((unicos["tipo"] == TipoContribuyente.JURIDICA.value).sum()),
        proveedores_invalidos=int((prov["tipo"] == TipoContribuyente.INVALIDO.value).sum()),
        proveedores_dv_incorrecto=int((unicos["dv_valido"] == False).sum()),  # noqa: E712
        coincidencias=len(comunes),
    )
    return resultado, detalle


def _veredicto(r: ResultadoFactibilidad) -> str:
    if r.coincidencias == 0:
        return (
            "**Sin coincidencias.** El cruce directo no sustenta la tesis tal como está "
            "planteada: revisar la calidad de los datos o replantear el alcance."
        )
    if r.coincidencias < 30:
        return (
            f"**Pocas coincidencias ({r.coincidencias}).** Alcanza para estudios de caso, "
            "no para entrenar un modelo. Considerar ampliar años o sumar otras señales."
        )
    return (
        f"**{r.coincidencias} coincidencias.** El cruce tiene volumen suficiente para "
        "continuar con la fase 2 (indicadores de riesgo)."
    )


def _describir_rubros(rubros: tuple[int, ...] | None) -> str:
    if rubros is None:
        return "todos los rubros"
    return "; ".join(f"{c} – {RUBROS.get(c, 'rubro sin nombre registrado')}" for c in rubros)


def generar_reporte(
    r: ResultadoFactibilidad,
    fuente_nomina: str,
    fuente_proveedores: str,
    rubros: tuple[int, ...] | None = RUBROS_POR_DEFECTO,
) -> str:
    """Reporte con números agregados únicamente (sin documentos)."""
    return f"""# Reporte de factibilidad — cruce nómina × proveedores

Generado: {date.today().isoformat()}

Fuentes: `{Path(fuente_nomina).name}` × `{Path(fuente_proveedores).name}`

Alcance: {_describir_rubros(rubros)}

## Resultado

{_veredicto(r)}

| Métrica | Valor |
|---|---:|
| Funcionarios únicos en nómina | {r.funcionarios_unicos:,} |
| Registros de nómina con documento inválido | {r.registros_nomina_invalidos:,} |
| Proveedores únicos | {r.proveedores_unicos:,} |
| — personas físicas (cruzables) | {r.proveedores_fisicos:,} |
| — personas jurídicas (no cruzables sin datos de socios) | {r.proveedores_juridicos:,} ({r.proporcion_juridicos:.1%}) |
| Registros de proveedor inválidos | {r.proveedores_invalidos:,} |
| Proveedores con DV incorrecto | {r.proveedores_dv_incorrecto:,} |
| **Funcionarios que también son proveedores** | **{r.coincidencias:,}** |
| Tasa sobre proveedores físicos | {r.tasa_sobre_fisicos:.2%} |
| Tasa sobre funcionarios | {r.tasa_sobre_funcionarios:.2%} |

## Aviso

Una coincidencia **no implica irregularidad**: la ley permite ciertos casos y
puede haber explicaciones legítimas. El detalle por documento queda en
`data/output/` y no se versiona.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nomina", required=True, help="CSV de la nómina (SFP)")
    parser.add_argument("--proveedores", required=True, help="CSV de proveedores (DNCP)")
    parser.add_argument("--col-nomina", help="Columna con la cédula en la nómina")
    parser.add_argument("--col-proveedores", help="Columna con el RUC en proveedores")
    parser.add_argument(
        "--rubros",
        default=",".join(str(c) for c in RUBROS_POR_DEFECTO),
        help="Códigos de categoría DNCP separados por coma (por defecto: 4,5,24)",
    )
    parser.add_argument(
        "--todos-los-rubros", action="store_true", help="No filtrar por rubro"
    )
    parser.add_argument("--col-categoria", help="Columna con la categoría en proveedores")
    parser.add_argument("--reporte", default="reports/factibilidad.md")
    parser.add_argument("--detalle", default="data/output/coincidencias.csv")
    args = parser.parse_args(argv)

    nomina = leer_csv(args.nomina)
    proveedores = leer_csv(args.proveedores)
    col_n = args.col_nomina or detectar_columna(nomina, CANDIDATAS_NOMINA)
    col_p = args.col_proveedores or detectar_columna(proveedores, CANDIDATAS_PROVEEDORES)
    print(f"Nómina: {len(nomina):,} filas, columna '{col_n}'")
    print(f"Proveedores: {len(proveedores):,} filas, columna '{col_p}'")

    rubros: tuple[int, ...] | None = None
    if not args.todos_los_rubros:
        rubros = parsear_rubros(args.rubros)
        col_c = args.col_categoria or detectar_columna(proveedores, CANDIDATAS_CATEGORIA)
        proveedores = filtrar_por_rubros(proveedores, col_c, rubros)
        print(f"Filtro por rubros {rubros} (columna '{col_c}'): {len(proveedores):,} filas")

    resultado, detalle = cruzar(nomina, col_n, proveedores, col_p)

    Path(args.reporte).parent.mkdir(parents=True, exist_ok=True)
    Path(args.reporte).write_text(
        generar_reporte(resultado, args.nomina, args.proveedores, rubros), encoding="utf-8"
    )
    Path(args.detalle).parent.mkdir(parents=True, exist_ok=True)
    detalle.to_csv(args.detalle, index=False)

    print(f"\nCoincidencias: {resultado.coincidencias:,}")
    print(f"Reporte agregado: {args.reporte}")
    print(f"Detalle privado:  {args.detalle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
