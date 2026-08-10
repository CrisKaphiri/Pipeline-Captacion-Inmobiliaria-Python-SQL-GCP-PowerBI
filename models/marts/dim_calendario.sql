-- Marts: dim_calendario — generada en BigQuery
-- Cobertura 2022-01-01 a 2024-12-31: incluye fecha_publicacion (empieza antes, en 2022-04) y fecha_scraping completo.

CREATE OR REPLACE TABLE `{project}.{dataset_marts}.dim_calendario` AS

SELECT
  fecha,
  EXTRACT(YEAR FROM fecha) AS anio,
  EXTRACT(MONTH FROM fecha) AS mes,
  EXTRACT(DAY FROM fecha) AS dia,
  EXTRACT(QUARTER FROM fecha) AS trimestre,
  EXTRACT(ISOWEEK FROM fecha) AS semana_anio,
  EXTRACT(DAYOFWEEK FROM fecha) AS dia_semana,
  CASE EXTRACT(MONTH FROM fecha)
    WHEN 1 THEN 'Enero' WHEN 2 THEN 'Febrero' WHEN 3 THEN 'Marzo' WHEN 4 THEN 'Abril'
    WHEN 5 THEN 'Mayo' WHEN 6 THEN 'Junio' WHEN 7 THEN 'Julio' WHEN 8 THEN 'Agosto'
    WHEN 9 THEN 'Septiembre' WHEN 10 THEN 'Octubre' WHEN 11 THEN 'Noviembre' WHEN 12 THEN 'Diciembre'
  END AS nombre_mes,
  CASE EXTRACT(DAYOFWEEK FROM fecha)
    WHEN 1 THEN 'Domingo' WHEN 2 THEN 'Lunes' WHEN 3 THEN 'Martes' WHEN 4 THEN 'Miércoles'
    WHEN 5 THEN 'Jueves' WHEN 6 THEN 'Viernes' WHEN 7 THEN 'Sábado'
  END AS nombre_dia,
  EXTRACT(DAYOFWEEK FROM fecha) IN (1, 7) AS es_fin_de_semana
FROM UNNEST(GENERATE_DATE_ARRAY('2022-01-01', '2024-12-31')) AS fecha;
