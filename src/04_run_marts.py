"""Runner de marts: ejecuta los SQL de models/marts/ contra BigQuery en orden de dependencia
(dim_comuna y dim_calendario primero, luego fct_arriendos, que hace JOIN contra dim_comuna).
La transformación vive en los .sql; este script solo los orquesta.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
BQ_DATASET_RAW = os.getenv("BQ_DATASET_RAW")
BQ_DATASET_STAGING = os.getenv("BQ_DATASET_STAGING")
BQ_DATASET_MARTS = os.getenv("BQ_DATASET_MARTS")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MARTS_DIR = PROJECT_ROOT / "models" / "marts"

# Orden de ejecución: fct_arriendos hace JOIN contra dim_comuna, por lo que las dimensiones
# deben existir primero.
ARCHIVOS_EN_ORDEN = [
    "dim_comuna.sql",
    "dim_calendario.sql",
    "fct_arriendos.sql",
]


def validar_configuracion() -> None:
    faltantes = [
        nombre
        for nombre, valor in {
            "GCP_PROJECT_ID": GCP_PROJECT_ID,
            "BQ_DATASET_RAW": BQ_DATASET_RAW,
            "BQ_DATASET_STAGING": BQ_DATASET_STAGING,
            "BQ_DATASET_MARTS": BQ_DATASET_MARTS,
        }.items()
        if not valor
    ]
    if faltantes:
        raise RuntimeError(f"Faltan variables de entorno requeridas: {faltantes}")

    archivos_faltantes = [
        nombre for nombre in ARCHIVOS_EN_ORDEN if not (MARTS_DIR / nombre).exists()
    ]
    if archivos_faltantes:
        raise RuntimeError(f"Faltan archivos SQL en {MARTS_DIR}: {archivos_faltantes}")


def ejecutar_modelo(bq_client: bigquery.Client, nombre_archivo: str) -> None:
    sql = (MARTS_DIR / nombre_archivo).read_text(encoding="utf-8")
    sql = sql.format(
        project=GCP_PROJECT_ID,
        dataset_raw=BQ_DATASET_RAW,
        dataset_staging=BQ_DATASET_STAGING,
        dataset_marts=BQ_DATASET_MARTS,
    )
    bq_client.query(sql).result()
    print(f"[{nombre_archivo}] ejecutado.")


def validar_resultado(bq_client: bigquery.Client) -> None:
    """Validación liviana: cada tabla tiene filas, y fct_arriendos no supera a stg_arriendos.

    No reemplaza notebooks/04_validate_marts.ipynb, que valida las reglas de negocio
    (reclasificación de superficie, regla de exclusión P99, dimensiones) en profundidad.
    """
    conteos = {}
    for tabla in ["dim_comuna", "dim_calendario", "fct_arriendos"]:
        query = (
            f"SELECT COUNT(*) AS n FROM `{GCP_PROJECT_ID}.{BQ_DATASET_MARTS}.{tabla}`"
        )
        n = next(iter(bq_client.query(query).result())).n
        if n == 0:
            raise RuntimeError(f"{tabla} quedó vacía tras la ejecución.")
        conteos[tabla] = n

    query_staging = f"SELECT COUNT(*) AS n FROM `{GCP_PROJECT_ID}.{BQ_DATASET_STAGING}.stg_arriendos`"
    n_staging = next(iter(bq_client.query(query_staging).result())).n

    if conteos["fct_arriendos"] > n_staging:
        raise RuntimeError(
            f"fct_arriendos ({conteos['fct_arriendos']}) tiene más filas que "
            f"stg_arriendos ({n_staging}) — la exclusión de marts nunca debería aumentar filas."
        )

    query_nulos = (
        f"SELECT COUNTIF(precio_clp IS NULL) AS n_clp_nulo, "
        f"COUNTIF(precio_uf IS NULL) AS n_uf_nulo "
        f"FROM `{GCP_PROJECT_ID}.{BQ_DATASET_MARTS}.fct_arriendos`"
    )
    nulos = next(iter(bq_client.query(query_nulos).result()))
    if nulos.n_clp_nulo or nulos.n_uf_nulo:
        raise RuntimeError(
            f"fct_arriendos tiene precios nulos: precio_clp={nulos.n_clp_nulo}, "
            f"precio_uf={nulos.n_uf_nulo}."
        )

    print(
        f"Validación OK: dim_comuna={conteos['dim_comuna']}, "
        f"dim_calendario={conteos['dim_calendario']}, "
        f"fct_arriendos={conteos['fct_arriendos']} (de {n_staging} en stg_arriendos)."
    )


def main() -> None:
    validar_configuracion()

    bq_client = bigquery.Client(project=GCP_PROJECT_ID)

    for nombre_archivo in ARCHIVOS_EN_ORDEN:
        ejecutar_modelo(bq_client, nombre_archivo)

    validar_resultado(bq_client)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
