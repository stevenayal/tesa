# Caso ueno bank — scripts de investigación

Aplicación de TESA a un caso concreto: riesgos de conflicto de intereses alrededor de ueno bank (intervenido por
el BCP en noviembre de 2026), las contrataciones públicas de su grupo económico y los fondos públicos depositados.

> **Solo se versiona el código y datos agregados.** La matriz de riesgo, el plan de investigación, los pedidos de
> acceso a la información y las cartas de réplica nombran a personas, por lo que quedan fuera del repositorio
> (ver `.gitignore`). Los datos descargados van a `data/`, que tampoco se versiona.
>
> TESA mide **riesgos**, no culpabilidad.

## Scripts

Se corren desde la raíz del repositorio, con el entorno de TESA activado.

| Script | Etapa | Qué hace | Entradas | Salida |
|---|---|---|---|---|
| `etapa0_dncp.py` | 0 | Baja ficha, adjudicaciones y datos de contrato de cada proveedor del buscador de la DNCP y marca el período (antes o desde el 15-08-2023) | `data/interim/ueno_proveedores.csv` (slug, grupo; privado) | `data/raw/ueno/adjudicaciones_enriquecidas.csv` |
| `consolidar_nomina.py` | 1 | Une las nóminas mensuales de la SFP en una tabla de cargos con su período | `data/raw/sfp/funcionarios_*.csv.zip` | `data/interim/nomina_2023_2026.csv.gz` |
| `cruce_c2.py` | 3 | Personas vinculadas al grupo × nómina pública (cruce por nombre de TESA y control de homónimos con el padrón de RUC) | universo de personas, nómina, adjudicaciones, `data/raw/ruc/` | `data/output/ueno_c2_detalle.csv` |
| `etapa2_ocds.py` | 2 | Baja el record OCDS de cada licitación (API v3 de la DNCP, sin token) y calcula indicadores: oferente único, empresas vinculadas compitiendo, plazos, precio frente al estimado, ampliaciones y protestas | `data/raw/ueno/adjudicaciones_enriquecidas.csv` | `data/interim/ueno_licitaciones.csv` |
| `cruce_c3_c4.py` | 3 | Imputados × nómina; decisores × apellidos poco frecuentes del grupo; administradores de contrato × universo | universo de personas, nómina, decisores, `data/raw/ruc/` | `data/output/ueno_c3*.csv`, `ueno_c4*.csv` |
| `etapa4_mef.py` | 4 | Baja los "Informes de Bancos" mensuales del MEF y arma la serie de fondos públicos en ueno | página de entidades depositarias del MEF | `serie_fondos_publicos_ueno.csv` |

## Datos públicos usados

- DNCP: buscador de proveedores y API OCDS v3 (`/datos/api/v3/doc/ocds/record/{ocid}`).
- SFP: nómina mensual de funcionarios (`datos.sfp.gov.py/data/funcionarios_AAAA_M.csv.zip`).
- DNIT: padrón de RUC con sus equivalencias (`ruc0.zip` … `ruc9.zip`).
- MEF: Informe de Bancos de la Dirección General del Tesoro Público.

## `serie_fondos_publicos_ueno.csv`

Saldos mensuales de los Organismos y Entidades del Estado en ueno bank (06-2023 a 09-2026), por moneda e instrumento
(cuenta corriente, depósito a la vista, CDA), su participación en el total del sistema y la calificación de riesgo
publicada por el MEF. Son montos institucionales agregados, sin datos personales.
