"""Runner de staging: ejecuta los SQL de models/staging/ contra BigQuery en orden de
dependencia (stg_toctoc, stg_portal_inmobiliario, luego stg_arriendos, que depende de los
dos anteriores). La transformación vive en los .sql; este script solo los orquesta.
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STAGING_DIR = PROJECT_ROOT / "models" / "staging"

# Orden de ejecución: stg_arriendos lee de stg_toctoc/stg_portal_inmobiliario, no de raw.
ARCHIVOS_EN_ORDEN = [
    "stg_toctoc.sql",
    "stg_portal_inmobiliario.sql",
    "stg_arriendos.sql",
]


def validar_configuracion() -> None:
    faltantes = [
        nombre
        for nombre, valor in {
            "GCP_PROJECT_ID": GCP_PROJECT_ID,
            "BQ_DATASET_RAW": BQ_DATASET_RAW,
            "BQ_DATASET_STAGING": BQ_DATASET_STAGING,
        }.items()
        if not valor
    ]
    if faltantes:
        raise RuntimeError(f"Faltan variables de entorno requeridas: {faltantes}")

    archivos_faltantes = [
        nombre for nombre in ARCHIVOS_EN_ORDEN if not (STAGING_DIR / nombre).exists()
    ]
    if archivos_faltantes:
        raise RuntimeError(
            f"Faltan archivos SQL en {STAGING_DIR}: {archivos_faltantes}"
        )


def ejecutar_modelo(bq_client: bigquery.Client, nombre_archivo: str) -> None:
    sql = (STAGING_DIR / nombre_archivo).read_text(encoding="utf-8")
    sql = sql.format(
        project=GCP_PROJECT_ID,
        dataset_raw=BQ_DATASET_RAW,
        dataset_staging=BQ_DATASET_STAGING,
    )
    bq_client.query(sql).result()
    print(f"[{nombre_archivo}] ejecutado.")


def validar_resultado(bq_client: bigquery.Client) -> None:
    """Validación liviana: cada tabla tiene filas, y arriendos = toctoc + portal.

    No reemplaza notebooks/03_validate_staging.ipynb, que valida las reglas de negocio
    (superficie centinela, precio conservado, tipos) en profundidad.
    """
    conteos = {}
    for tabla in ["stg_toctoc", "stg_portal_inmobiliario", "stg_arriendos"]:
        query = (
            f"SELECT COUNT(*) AS n FROM `{GCP_PROJECT_ID}.{BQ_DATASET_STAGING}.{tabla}`"
        )
        n = next(iter(bq_client.query(query).result())).n
        if n == 0:
            raise RuntimeError(f"{tabla} quedó vacía tras la ejecución.")
        conteos[tabla] = n

    suma_fuentes = conteos["stg_toctoc"] + conteos["stg_portal_inmobiliario"]
    if conteos["stg_arriendos"] != suma_fuentes:
        raise RuntimeError(
            f"stg_arriendos ({conteos['stg_arriendos']}) no coincide con "
            f"stg_toctoc + stg_portal_inmobiliario ({suma_fuentes})."
        )

    print(
        f"Validación OK: stg_toctoc={conteos['stg_toctoc']}, "
        f"stg_portal_inmobiliario={conteos['stg_portal_inmobiliario']}, "
        f"stg_arriendos={conteos['stg_arriendos']}."
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
