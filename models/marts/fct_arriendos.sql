-- Marts: fct_arriendos — grano: 1 fila por publicación ANALÍTICAMENTE UTILIZABLE (Toctoc + PortalInmobiliario unidos).
-- Se relaciona con dim_comuna (comuna_id) y con dim_calendario (fecha_publicacion / fecha_scraping).
--
-- Población incluida: superficie_categoria = 'valida', y precio_clp_por_m2 dentro del percentil 99 de su propia fuente
-- (precio_clp_por_m2 se usa solo internamente para filtrar; no se expone como columna de salida).
--
-- Población excluida (permanece intacta en staging.stg_arriendos, solo se filtra acá):
--   1. superficie_categoria = 'centinela' (1,2,250,400,650,999,1200 — no son áreas reales).
--   2. superficie_categoria = 'habitacion' (5,8,10,12 — población distinta, no departamento).
--   3. El 1% superior de precio_clp_por_m2, calculado POR FUENTE. Es una regla de representatividad analítica, NO una corrección de datos erróneos.
-- Evidencia, conteos y ejemplos: notebooks/03_validate_staging.ipynb y la sesión de diseño de marts.

CREATE OR REPLACE TABLE `{project}.{dataset_marts}.fct_arriendos` AS

WITH base AS (
  SELECT
    s.id,
    s.fuente,
    s.comuna,
    s.tipo_propiedad,
    s.tipo_operacion,
    s.contact_type,
    s.superficie_m2,
    s.fecha_publicacion,
    s.fecha_scraping,
    s.precio_clp,
    s.precio_uf,
    SAFE_DIVIDE(s.precio_clp, s.superficie_m2) AS precio_clp_por_m2
  FROM `{project}.{dataset_staging}.stg_arriendos` AS s
  WHERE s.superficie_categoria = 'valida'
),

umbral_p99_por_fuente AS (
  SELECT DISTINCT
    fuente,
    PERCENTILE_CONT(precio_clp_por_m2, 0.99) OVER (PARTITION BY fuente) AS p99_precio_clp_por_m2
  FROM base
)

SELECT
  b.id,
  b.fuente,
  c.comuna_id,
  b.tipo_propiedad,
  b.tipo_operacion,
  b.contact_type,
  b.superficie_m2,
  b.fecha_publicacion,
  b.fecha_scraping,
  b.precio_clp,
  b.precio_uf
FROM base AS b
JOIN umbral_p99_por_fuente AS u ON b.fuente = u.fuente
LEFT JOIN `{project}.{dataset_marts}.dim_comuna` AS c ON b.comuna = c.comuna
WHERE b.precio_clp_por_m2 <= u.p99_precio_clp_por_m2;
