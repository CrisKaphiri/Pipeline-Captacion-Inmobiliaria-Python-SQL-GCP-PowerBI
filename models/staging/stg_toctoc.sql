-- Staging: Toctoc — limpieza y normalización de raw.toctoc.
-- Esquema de salida idéntico a stg_portal_inmobiliario.sql para permitir UNION ALL en stg_arriendos.
-- Evidencia y decisiones detalladas: notebooks/03_validate_staging.ipynb

CREATE OR REPLACE TABLE `{project}.{dataset_staging}.stg_toctoc` AS

WITH raw_dedup AS (
  -- Dedup: colapsa duplicados exactos (mismo id + fecha_scraping + resto de columnas), copias
  -- dentro de un mismo archivo mensual. Detalle: notebooks/03_validate_staging.ipynb
  SELECT DISTINCT
    id,
    fuente,
    comuna,
    region,
    precio,
    divisa,
    superficie_m2,
    fecha_publicacion,
    fecha_scraping,
    tipo_propiedad,
    tipo_operacion,
    contact_type
  FROM `{project}.{dataset_raw}.toctoc`
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
    CAST(precio AS FLOAT64) AS precio,
    divisa,
    CAST(superficie_m2 AS FLOAT64) AS superficie_m2_original,
    DATE(SUBSTR(fecha_publicacion, 1, 10)) AS fecha_publicacion,
    DATE(SUBSTR(fecha_scraping, 1, 10)) AS fecha_scraping
  FROM raw_dedup
),

uf_diaria AS (
  SELECT
    DATE(SUBSTR(fecha, 1, 10)) AS fecha_dt,
    CAST(valor AS FLOAT64) AS valor_uf
  FROM `{project}.{dataset_raw}.uf`
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

  -- Centinela (1,2,250,400,650,999,1200): no son áreas reales, se anula para métricas.
  -- Habitación (5,8,10,12): área real pero de un espacio no residencial estándar, se conserva.
  -- Detalle: notebooks/03_validate_staging.ipynb
  IF(t.superficie_m2_original IN (1, 2, 250, 400, 650, 999, 1200), NULL, t.superficie_m2_original)
    AS superficie_m2,
  t.superficie_m2_original,
  CASE
    WHEN t.superficie_m2_original IN (1, 2, 250, 400, 650, 999, 1200) THEN 'centinela'
    WHEN t.superficie_m2_original IN (5, 8, 10, 12) THEN 'habitacion'
    ELSE 'valida'
  END AS superficie_categoria,

  t.fecha_publicacion,
  t.fecha_scraping,

  -- Completa la moneda faltante con el UF oficial de fecha_scraping (Toctoc trae una sola
  -- moneda por fila). Detalle: notebooks/03_validate_staging.ipynb
  CASE WHEN t.divisa = 'CLP' THEN CAST(ROUND(t.precio) AS INT64)
       WHEN t.divisa = 'UF' THEN CAST(ROUND(t.precio * u.valor_uf) AS INT64)
  END AS precio_clp,

  CASE WHEN t.divisa = 'UF' THEN t.precio
       WHEN t.divisa = 'CLP' THEN ROUND(t.precio / u.valor_uf, 2)
  END AS precio_uf,

  t.divisa = 'UF' AS precio_clp_es_calculado,
  t.divisa = 'CLP' AS precio_uf_es_calculado,
  u.valor_uf AS valor_uf_referencia

FROM tipado AS t
LEFT JOIN uf_diaria AS u
  ON t.fecha_scraping = u.fecha_dt;
