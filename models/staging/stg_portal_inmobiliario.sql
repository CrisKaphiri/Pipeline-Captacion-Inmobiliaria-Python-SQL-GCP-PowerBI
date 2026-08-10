-- Staging: PortalInmobiliario — limpieza y normalización de raw.portal_inmobiliario.
-- Esquema de salida idéntico a stg_toctoc.sql para permitir UNION ALL en stg_arriendos.
-- Evidencia y decisiones detalladas: notebooks/03_validate_staging.ipynb

CREATE OR REPLACE TABLE `{project}.{dataset_staging}.stg_portal_inmobiliario` AS

WITH raw_dedup AS (
  -- Dedup: colapsa duplicados exactos (mismo id + fecha_scraping + resto de columnas), copias
  -- dentro de un mismo archivo mensual. Detalle: notebooks/03_validate_staging.ipynb
  SELECT DISTINCT
    id,
    fuente,
    comuna,
    region,
    precio_clp,
    precio_uf,
    superficie_total_m2,
    fecha_publicacion,
    fecha_scraping,
    tipo_propiedad,
    tipo_operacion,
    contact_type
  FROM `{project}.{dataset_raw}.portal_inmobiliario`
),

tipado AS (
  SELECT
    id,
    fuente,
    -- Dataset cerrado (sin datos nuevos futuros): comuna se capitaliza genéricamente en vez de
    -- mapearse contra una whitelist fija. Detalle: notebooks/03_validate_staging.ipynb
    IF(
      comuna IS NULL OR TRIM(comuna) = '',
      NULL,
      ARRAY_TO_STRING(
        ARRAY(
          SELECT CONCAT(UPPER(SUBSTR(palabra, 1, 1)), LOWER(SUBSTR(palabra, 2)))
          FROM UNNEST(SPLIT(LOWER(TRIM(comuna)), ' ')) AS palabra
          WHERE palabra != ''
        ),
        ' '
      )
    ) AS comuna,
    region,
    UPPER(TRIM(tipo_propiedad)) AS tipo_propiedad_clave,
    TRIM(tipo_propiedad) AS tipo_propiedad_original,
    UPPER(TRIM(tipo_operacion)) AS tipo_operacion_clave,
    TRIM(tipo_operacion) AS tipo_operacion_original,
    contact_type,
    CAST(precio_clp AS FLOAT64) AS precio_clp,
    CAST(precio_uf AS FLOAT64) AS precio_uf,
    CAST(superficie_total_m2 AS FLOAT64) AS superficie_m2_original,
    DATE(SUBSTR(fecha_publicacion, 1, 10)) AS fecha_publicacion,
    DATE(SUBSTR(fecha_scraping, 1, 10)) AS fecha_scraping
  FROM raw_dedup
)

SELECT
  t.id,
  t.fuente,
  t.comuna,
  t.region,

  CASE WHEN t.tipo_propiedad_clave = 'DEPARTAMENTO' THEN 'Departamento'
       ELSE t.tipo_propiedad_original -- valor inesperado: se conserva tal cual, no se inventa
  END AS tipo_propiedad,

  CASE WHEN t.tipo_operacion_clave = 'ARRIENDO' THEN 'Arriendo'
       ELSE t.tipo_operacion_original
  END AS tipo_operacion,

  t.contact_type,

  -- Superficie centinela (1,2,5,250,400,650,999,1200): no son áreas reales, se anulan para
  -- métricas y se flaguea; el original se conserva. Detalle: notebooks/03_validate_staging.ipynb
  IF(t.superficie_m2_original IN (1, 2, 5, 250, 400, 650, 999, 1200), NULL, t.superficie_m2_original)
    AS superficie_m2,
  t.superficie_m2_original,
  t.superficie_m2_original IN (1, 2, 5, 250, 400, 650, 999, 1200) AS superficie_es_centinela,

  t.fecha_publicacion,
  t.fecha_scraping,

  CAST(ROUND(t.precio_clp) AS INT64) AS precio_clp,
  -- No se imputa: el precio_uf nativo de esta fuente no reconcilia con el UF oficial diaria.
  -- Detalle: notebooks/03_validate_staging.ipynb
  t.precio_uf,

  FALSE AS precio_clp_es_calculado,
  FALSE AS precio_uf_es_calculado,
  CAST(NULL AS FLOAT64) AS valor_uf_referencia

FROM tipado AS t;
