-- Marts: dim_comuna — dimensión de comuna (25 filas), clave surrogate para relacionar con fct_arriendos. 
-- Fuente: comunas distintas presentes en staging.stg_arriendos (ya normalizadas).

CREATE OR REPLACE TABLE `{project}.{dataset_marts}.dim_comuna` AS

SELECT
  ROW_NUMBER() OVER (ORDER BY comuna) AS comuna_id,
  comuna,
  ANY_VALUE(region) AS region
FROM `{project}.{dataset_staging}.stg_arriendos`
WHERE comuna IS NOT NULL
GROUP BY comuna;
