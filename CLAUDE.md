# Pipeline Captación Inmobiliaria

Pipeline de datos end-to-end (ELT) en Google Cloud Platform: extrae datos inmobiliarios sucios (Toctoc + PortalInmobiliario) y la serie histórica de la UF (API mindicador.cl), los carga crudos a BigQuery, y los transforma con SQL por capas (staging → marts) para responder preguntas de mercado y captación de propietarios, visualizadas en un dashboard de Power BI. 

## Objetivo

Problema: La información de arriendo de departamentos en la Región Metropolitana está dispersa entre distintas plataformas (Toctoc, PortalInmobiliario), sin estandarizar ni expresar los precios en una unidad reajustable (UF), lo que dificulta comparar precios de forma confiable en el tiempo o identificar qué comunas ofrecen mejores oportunidades de captación.

**Preguntas de negocio**

Se busca responder las siguientes preguntas de negocio:

*Mercado*
- ¿Cómo evolucionó el precio de arriendo de departamentos entre 2023 y 2024?
- ¿Qué comunas aumentaron más sus precios?
- ¿Cómo evolucionó el precio de arriendo por m²?
- ¿Cómo cambió la oferta de departamentos en arriendo?
- ¿Cómo cambia el análisis al utilizar UF además de CLP?

*Captación*
- ¿Qué comunas son más atractivas para captar propietarios?
- ¿Dónde se concentran las mejores oportunidades de captación de propietarios directos?
- ¿Qué propiedades son más atractivas para contactar?

*Fuentes*
- ¿Qué diferencias existen entre PortalInmobiliario y Toctoc?

*Data Engineering (adicional)*
- ¿Qué problemas de calidad presenta el proceso de scraping?
- ¿Qué transformaciones deben realizarse para obtener datos analíticos confiables?

**Resultado esperado:** modelo analítico en BigQuery (staging → marts) y dashboard en Power BI que responda las preguntas anteriores.

## Stack

- Lenguaje: Python 3.11+
- Cloud: Google Cloud Platform (Cloud Storage, BigQuery)
- SQL: BigQuery Standard SQL
- Visualización: Power BI / DAX
- API: mindicador.cl para histórico en UF

## Fuente de datos

- `data/raw/toctoc/` — 24 archivos mensuales (2023-2024)
- `data/raw/portal_inmobiliario/` — 24 archivos mensuales (2023-2024)
- API mindicador.cl — serie histórica de la UF

Es una carga historica cerrada, en este versión no se recibiran archivos nuevos a futuro. 

## Variables de entorno

Las variables de entorno se gestionan mediante `.env`. Variables requeridas:

- `GCP_PROJECT_ID` — ID del proyecto de Google Cloud.
- `GCS_BUCKET_NAME` — nombre del bucket de Cloud Storage.
- `BQ_DATASET_RAW` — dataset de BigQuery para la capa raw.
- `BQ_DATASET_STAGING` — dataset de BigQuery para la capa staging.
- `BQ_DATASET_MARTS` — dataset de BigQuery para la capa marts.
- `GOOGLE_APPLICATION_CREDENTIALS` — ruta al archivo de credenciales de la service account.
- `MINDICADOR_API_URL` — URL base de la API de mindicador.cl.

Las variables que contengan credenciales, tokens, claves API u otra información sensible deben almacenarse exclusivamente en `.env`.
No incluir valores reales de variables de entorno en el código, `CLAUDE.md` ni documentación.
Mantener un `.env.example` con los nombres de las variables requeridas,pero sin valores sensibles reales.

## Arquitectura

data/raw → src → Cloud Storage → BigQuery raw → staging → marts → Power BI

## Convenciones de datos

- Las operaciones de extracción y carga deben ser idempotentes: ejecutar el proceso más de una vez no debe duplicar registros ni producir estados inconsistentes.
- Raw es inmutable.
- Cada fuente tiene su propia tabla raw.
- La limpieza ocurre en staging.
- La integración entre fuentes ocurre en staging.
- Los marts contienen datos orientados al análisis.
- Power BI consume exclusivamente marts.
- Usar `snake_case` en nombres de archivos, columnas y tablas.
- Archivos SQL con prefijo según capa: `stg_` (staging), `fct_`/`dim_` (marts).

## Calidad de datos

Antes de considerar un dataset como válido, comprobar problemas conocidos de scraping, en todas las fuentes en `data/raw`:

- Duplicados exactos
- Nulos inesperados
- Errores de formato
- Outliers y anomalías de scraping
- Volumen variable entre archivos
- Consistencia de Schema entre TocToc y PortalInmobiliario
- Unicidad de claves según la granularidad de cada fuente
- Consistencia de métricas después de las transformaciones
- No eliminar registros únicamente para hacer desaparecer problemas de calidad; identificar primero la causa y justificar cualquier exclusión
- No asumir que id es único entre fuentes.
- No asumir que una transformación es correcta únicamente porque aumenta la cantidad de datos válidos; verificar que preserve la integridad y el significado de los datos.

### Calidad y perfilado

Antes de implementar transformaciones importantes en staging, revisar cada columna y, cuando corresponda, sus relaciones con otras columnas. Determinar:

- calidad y distribución de los valores;
- significado de los campos;
- tipos y unidades;
- nulos;
- duplicados;
- valores extremos;
- patrones sospechosos o valores centinela;
- relaciones entre variables que puedan revelar anomalías.

No asumir que un valor extremo es incorrecto únicamente por su magnitud. Investigar su contexto antes de excluirlo.

No eliminar registros completos para corregir un problema localizado en una columna. Cuando sea posible, conservar el valor original y representar el valor no confiable mediante NULL + un indicador de trazabilidad.

No implementar una transformación importante ni definir reglas de exclusión sin haber verificado previamente los datos y documentado el criterio utilizado.

## SQL

- Utilizar SQL Legible y con formato consistente, para ser revisado
- Evitar escanear columnas o datos innecesarios para controlar el costo de BigQuery
- No usar `SELECT *` en transformaciones definitivas
- Utilizar nombres descriptivos para CTEs y alias
- Documentar lógica de negocio no evidente y reglas de transformación relevantes
- Separar consultas exploratorias de las transformaciones definitivas del pipeline (`models/`)

## Notebooks

- Antes de escribir `01_extract.py`/`02_load.py`, perfilar ambas fuentes en `notebooks/` (columnas, nulos, tipos, duplicados) — no asumir el esquema de PortalInmobiliario sin haberlo revisado.
- La lógica reutilizable no debe vivir únicamente en notebooks.
- Cada notebook debe indicar claramente su objetivo.
- No utilizar notebooks como almacenamiento de datos intermedios.

## Análisis

- Separar exploración de conclusiones.
- Explicitar los supuestos relevantes (ej. criterios para definir una comuna "atractiva para captación").
- Diferenciar correlación de causalidad.
- Las métricas usadas en Power BI/DAX deben tener una definición clara y documentada.

## Pipeline

El flujo es ELT, no ETL — la carga ocurre antes que la limpieza:
 
1. Paso inicial (`notebooks/`) — entender columnas, nulos y tipos de ambas fuentes
2. Extracción (`01_extract.py`) — serie UF vía API + validación de que los 48 CSV están disponibles
3. Carga cruda a BigQuery (`02_load.py`) — Cloud Storage → `raw.toctoc` / `raw.portal_inmobiliario`
4. Transformación staging (SQL) — limpieza, normalización, unificación de esquemas entre fuentes
5. Transformación marts (SQL) — modelo analítico, métricas de negocio
6. Consumo — Power BI conectado a `marts`

## Rol de la IA

Claude actúa como asistente de implementación y revisión técnica.

Las decisiones de arquitectura, modelo de datos, reglas de negocio, criterios de calidad y alcance del proyecto corresponden al autor.

Claude puede:
- proponer implementaciones
- escribir o modificar código
- detectar errores y problemas potenciales
- sugerir mejoras
- ejecutar validaciones disponibles

Claude no debe:
- cambiar la arquitectura sin aprobación
- introducir nuevas reglas de negocio por iniciativa propia
- modificar preguntas de negocio sin aprobación
- asumir características de los datos que no hayan sido verificadas
- reemplazar decisiones técnicas o de negocio con suposiciones

Todo cambio debe ser revisado por el autor antes de considerarse parte definitiva del proyecto.

## No hagas

- No hardcodees IDs de proyecto, nombres de bucket/datasets, ni ningún valor de configuración directamente en el código — todos las credenciales o valores sensibles deben venir de las variables de entorno (`.env`).
- No dejes visible o ID de GCP ni archivos `.json` de service account, usa variables de entorno.
- No cargues datos ya limpios a la capa `raw` — el dato crudo entra tal cual.
- No uses `SELECT *` sin filtrar columnas.
- Nunca definir una clave de `MERGE` basándose únicamente en intuición sobre nombres de columnas. Antes de implementar la carga, verificar que la clave identifica correctamente los registros según la granularidad de cada fuente.
- No modifiques los CSV originales en `data/raw/`.
- No asumas el esquema de una fuente sin haberla perfilado primero.
- No muevas lógica de transformación importante solo a un notebook — la transformación vive en `models/`.

## Flujo de trabajo

- Antes de implementar un cambio, propone un plan indicando qué vas a modificar, qué supuestos vas a usar y qué validaciones vas a ejecutar — y espera mi OK antes de ejecutarlo.- No considerar una implementación correcta únicamente porque el código se ejecuta; verificar también que cumple las reglas de datos y negocio definidas en este documento.
- Una tarea a la vez; al terminar, dime qué cambiaste para que lo revise.
- Si no estás seguro al 80%, pregunta. No inventes.