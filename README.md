# TESA

> *Tesa* — "ojo" en guaraní.

Sistema de detección explicable de **riesgos de conflicto de interés en las compras públicas del Paraguay**, a partir del cruce de datos abiertos de la **nómina de funcionarios públicos** y de las **contrataciones de la DNCP**.

Proyecto de tesis — Licenciatura en Análisis de Sistemas, UCOM.

---

## ⚠️ Aviso

TESA **no detecta corrupción ni señala culpables**. Detecta **coincidencias y patrones de riesgo** en datos públicos para priorizar la revisión humana. Una coincidencia (por ejemplo, un funcionario que además es proveedor del Estado) **no implica un hecho ilícito**: puede tener explicaciones legítimas.

Los datos personales **nunca se suben a este repositorio** (ver `.gitignore`).

---

## Fases

| Fase | Objetivo | Estado |
|---|---|---|
| **1. Factibilidad** | Medir cuántos proveedores del Estado aparecen en la nómina pública. Si la tasa es ~0, se replantea el alcance. | 🚧 En curso |
| 2. Indicadores | Red flags sobre contrataciones (oferente único, plazos cortos, adjudicaciones repetidas, etc.) | ⏳ |
| 3. Modelo | Score de riesgo con ML + explicabilidad (SHAP). Línea base: [DSSG19-DNCP](https://github.com/alan-turing-institute/DSSG19-DNCP-PUBLIC) y Cardinal (OCP). | ⏳ |
| 4. Asistente RAG | Explica en lenguaje natural por qué un proceso tiene riesgo, citando datos y normativa. | ⏳ |

---

## Fase 1: prueba de factibilidad

### 1. Descargar los datos (manual)

Los portales bloquean descargas automatizadas o cambian sus URLs, así que la descarga es manual y los archivos van a `data/raw/`:

- **Nómina de funcionarios** → [datos.sfp.gov.py](https://datos.sfp.gov.py/data/funcionarios/download) (CSV mensual). Guardar como `data/raw/nomina.csv`.
- **Proveedores / adjudicaciones DNCP** → [contrataciones.gov.py/datos](https://www.contrataciones.gov.py/datos/data) (sección *Procesos completos* o *Adjudicaciones*, CSV por año). Guardar como `data/raw/proveedores.csv`.

Alternativa para OCDS completo: [OCP Data Registry – Paraguay DNCP](https://data.open-contracting.org/en/publication/63).

### 2. Instalar

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 3. Correr el cruce

```bash
python -m tesa.factibilidad \
  --nomina data/raw/nomina.csv \
  --proveedores data/raw/proveedores.csv
```

Si las columnas no se detectan solas, indicarlas:

```bash
python -m tesa.factibilidad \
  --nomina data/raw/nomina.csv --col-nomina documento \
  --proveedores data/raw/proveedores.csv --col-proveedores ruc
```

**Salidas**
- `reports/factibilidad.md` → solo **números agregados** (se puede compartir).
- `data/output/coincidencias.csv` → el detalle con documentos (**privado**, ignorado por git).

### 4. Tests

```bash
pytest
```

---

## Cómo funciona el cruce

- En Paraguay, el **RUC de una persona física es su cédula + un dígito verificador** (`1234567-9`).
- Los RUC de **personas jurídicas** empiezan en `80000000` y **no se pueden cruzar** con la nómina sin datos de socios o beneficiarios finales. La fase 1 mide también qué proporción de proveedores quedan fuera del cruce por esta razón.

---

## Estructura

```
tesa/
├── src/tesa/
│   ├── normalizacion.py   # cédulas, RUC, dígito verificador
│   ├── ingesta.py         # lectura de CSV y detección de columnas
│   └── factibilidad.py    # cruce nómina × proveedores + reporte
├── tests/
├── data/                  # ignorado por git
└── reports/
```
