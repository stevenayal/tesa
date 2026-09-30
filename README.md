# TESA

> *Tesa* — "ojo" en guaraní.

Sistema de detección explicable de **riesgos de conflicto de interés en las compras públicas del Paraguay**, a partir del cruce de datos abiertos de la **nómina de funcionarios públicos** y de las **contrataciones de la DNCP**.

Proyecto de tesis — Licenciatura en Análisis de Sistemas, UCOM.

---

## ⚠️ Aviso

TESA **no detecta corrupción ni señala culpables**. Detecta **coincidencias y patrones de riesgo** en datos públicos para priorizar la revisión humana. Una coincidencia (por ejemplo, un funcionario que además es proveedor del Estado) **no implica un hecho ilícito**: puede tener explicaciones legítimas.

Los datos personales **nunca se suben a este repositorio** (ver `.gitignore`).

---

## Alcance

El estudio se limita a tres rubros (categorías de nivel 1) del catálogo de la DNCP:

| Código | Rubro |
|---:|---|
| 4 | Capacitaciones y Adiestramientos |
| 5 | Consultorías, Asesorías e Investigaciones. Estudios y Proyectos de inversión |
| 24 | Equipos, accesorios y programas computacionales, de oficina, educativos, de imprenta, de comunicación y señalamiento |

El CLI filtra por estos rubros por defecto (`--rubros 4,5,24`). Para analizar todo, usar `--todos-los-rubros`.

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

### 1. Descargar los proveedores (automático)

```bash
python -m tesa.proveedores_dncp --salida data/raw/proveedores.csv
# prueba corta: python -m tesa.proveedores_dncp --rubros 5 --max-paginas 3
```

Recorre el [buscador de proveedores de la DNCP](https://www.contrataciones.gov.py/buscador/proveedores.html) para los rubros 4, 5 y 24 (IDs internos del buscador: 20, 21 y 40). Espera 1 s entre páginas, reintenta ante errores y, si se corta, **se reanuda** al volver a ejecutarlo. Guarda solo RUC, razón social, nombre de fantasía, enlace y rubro: descarta representante, dirección, teléfono y correo.

⚠️ Son proveedores **inscriptos** en el rubro, no **adjudicados**. Sirve para la fase 1; el cruce final va contra adjudicaciones.

### 1b. Descargar la nómina y adjudicaciones (manual)

Los portales bloquean descargas automatizadas o cambian sus URLs, así que la descarga es manual y los archivos van a `data/raw/`:

- **Nómina de funcionarios** → [datos.sfp.gov.py](https://datos.sfp.gov.py/data/funcionarios/download) (CSV mensual). Guardar como `data/raw/nomina.csv`.
- **Adjudicaciones DNCP** (fase siguiente) → [contrataciones.gov.py/datos](https://www.contrataciones.gov.py/datos/data) (sección *Adjudicaciones*, CSV por año).

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
  --proveedores data/raw/proveedores.csv --col-proveedores ruc \
  --col-categoria categoria
```

La columna de categoría acepta el código (`24`, `24 - Equipos…`) o el nombre del rubro.

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
│   ├── alcance.py         # rubros del estudio (4, 5, 24) y filtro
│   ├── proveedores_dncp.py # extractor del buscador de proveedores
│   └── factibilidad.py    # cruce nómina × proveedores + reporte
├── tests/
├── data/                  # ignorado por git
└── reports/
```
