-- Staging: Arriendos unificados (Toctoc + PortalInmobiliario)
--
-- Integración entre fuentes: UNION ALL de stg_toctoc y stg_portal_inmobiliario, que ya comparten
-- el mismo esquema de salida (mismas columnas, mismos tipos, mismas reglas de normalización).
-- No se aplica ninguna transformación adicional acá — la columna `fuente` se conserva para poder
-- responder la pregunta de negocio sobre diferencias entre fuentes.
--
-- Depende de que stg_toctoc.sql y stg_portal_inmobiliario.sql ya se hayan ejecutado.

CREATE OR REPLACE TABLE `{project}.{dataset_staging}.stg_arriendos` AS

SELECT * FROM `{project}.{dataset_staging}.stg_toctoc`
UNION ALL
SELECT * FROM `{project}.{dataset_staging}.stg_portal_inmobiliario`;
