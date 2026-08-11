-- Marts: dim_calendario — generada en BigQuery
-- Cobertura 2022-01-01 a 2024-12-31: incluye fecha_publicacion (empieza antes, en 2022-04) y fecha_scraping completo.
-- dia_semana usa convención ISO: 1 = Lunes ... 7 = Domingo (EXTRACT(DAYOFWEEK) de BigQuery
-- empieza en Domingo=1, por eso se recalcula).

CREATE OR REPLACE TABLE `{project}.{dataset_marts}.dim_calendario` AS

WITH calendario_base AS (
  SELECT
    fecha,
    MOD(EXTRACT(DAYOFWEEK FROM fecha) + 5, 7) + 1 AS dia_semana
  FROM UNNEST(GENERATE_DATE_ARRAY('2022-01-01', '2024-12-31')) AS fecha
)

SELECT
  fecha,
  EXTRACT(YEAR FROM fecha) AS anio,
  EXTRACT(MONTH FROM fecha) AS mes,
  EXTRACT(DAY FROM fecha) AS dia,
  EXTRACT(QUARTER FROM fecha) AS trimestre,
  EXTRACT(ISOWEEK FROM fecha) AS semana_anio,
  dia_semana,
  CASE EXTRACT(MONTH FROM fecha)
    WHEN 1 THEN 'Enero' WHEN 2 THEN 'Febrero' WHEN 3 THEN 'Marzo' WHEN 4 THEN 'Abril'
    WHEN 5 THEN 'Mayo' WHEN 6 THEN 'Junio' WHEN 7 THEN 'Julio' WHEN 8 THEN 'Agosto'
    WHEN 9 THEN 'Septiembre' WHEN 10 THEN 'Octubre' WHEN 11 THEN 'Noviembre' WHEN 12 THEN 'Diciembre'
  END AS nombre_mes,
  CASE dia_semana
    WHEN 1 THEN 'Lunes' WHEN 2 THEN 'Martes' WHEN 3 THEN 'Miércoles' WHEN 4 THEN 'Jueves'
    WHEN 5 THEN 'Viernes' WHEN 6 THEN 'Sábado' WHEN 7 THEN 'Domingo'
  END AS nombre_dia,
  dia_semana IN (6, 7) AS es_fin_de_semana
FROM calendario_base;
