-- Marts: fct_arriendos — grano: 1 fila por publicación ANALÍTICAMENTE UTILIZABLE (Toctoc + PortalInmobiliario unidos).
-- Se relaciona con dim_comuna (comuna_id) y con dim_calendario (fecha_publicacion / fecha_scraping).
-- Población incluida: superficie_categoria = 'valida', y precio_clp_por_m2 dentro del percentil 99 de su propia fuente
-- columnas: id, fuente, comuna_id, contact_type, superficie_m2, fecha_publicacion, fecha_scraping, precio_clp, precio_uf_oficial.
-- Evidencia, conteos y ejemplos: notebooks/04_validate_marts.ipynb y la sesión de diseño de marts.

CREATE OR REPLACE TABLE `{project}.{dataset_marts}.fct_arriendos` AS

WITH base AS (
  SELECT
    s.id,
    s.fuente,
    s.comuna,
    s.contact_type,
    s.superficie_m2,
    s.fecha_publicacion,
    s.fecha_scraping,
    s.precio_clp,
    SAFE_DIVIDE(s.precio_clp, s.superficie_m2) AS precio_clp_por_m2
  FROM `{project}.{dataset_staging}.stg_arriendos` AS s
  WHERE s.superficie_categoria = 'valida'
),

umbral_p99_por_fuente AS (
  SELECT DISTINCT
    fuente,
    PERCENTILE_CONT(precio_clp_por_m2, 0.99) OVER (PARTITION BY fuente) AS p99_precio_clp_por_m2
  FROM base
),

uf_diaria AS (
  SELECT
    DATE(SUBSTR(fecha, 1, 10)) AS fecha_dt,
    CAST(valor AS FLOAT64) AS valor_uf
  FROM `{project}.{dataset_raw}.uf`
)

SELECT
  b.id,
  b.fuente,
  c.comuna_id,
  b.contact_type,
  b.superficie_m2,
  b.fecha_publicacion,
  b.fecha_scraping,
  b.precio_clp,
  SAFE_DIVIDE(b.precio_clp, uf.valor_uf) AS precio_uf_oficial
FROM base AS b
JOIN umbral_p99_por_fuente AS u ON b.fuente = u.fuente
LEFT JOIN `{project}.{dataset_marts}.dim_comuna` AS c ON b.comuna = c.comuna
LEFT JOIN uf_diaria AS uf ON b.fecha_scraping = uf.fecha_dt
WHERE b.precio_clp_por_m2 <= u.p99_precio_clp_por_m2;
