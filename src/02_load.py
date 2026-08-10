"""Carga cruda: sube los CSV de data/raw a Cloud Storage y los carga a BigQuery raw
(raw.toctoc, raw.portal_inmobiliario, raw.uf), una tabla por fuente. Todas las columnas
se cargan como STRING — sin interpretar tipos ni transformar valores; el cast y la limpieza
ocurren en staging.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery, storage

load_dotenv()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
BQ_DATASET_RAW = os.getenv("BQ_DATASET_RAW")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"

# fuente -> (carpeta local en data/raw, patrón de archivos a subir)
FUENTES = {
    "toctoc": RAW_DIR / "toctoc",
    "portal_inmobiliario": RAW_DIR / "portal_inmobiliario",
    "uf": RAW_DIR / "uf",
}


def validar_configuracion() -> None:
    faltantes = [
        nombre
        for nombre, valor in {
            "GCP_PROJECT_ID": GCP_PROJECT_ID,
            "GCS_BUCKET_NAME": GCS_BUCKET_NAME,
            "BQ_DATASET_RAW": BQ_DATASET_RAW,
        }.items()
        if not valor
    ]
    if faltantes:
        raise RuntimeError(f"Faltan variables de entorno requeridas: {faltantes}")


def validar_bucket_y_dataset(storage_client: storage.Client, bq_client: bigquery.Client) -> None:
    if not storage_client.bucket(GCS_BUCKET_NAME).exists():
        raise RuntimeError(f"El bucket '{GCS_BUCKET_NAME}' no existe o no es accesible.")

    dataset_ref = f"{GCP_PROJECT_ID}.{BQ_DATASET_RAW}"
    try:
        bq_client.get_dataset(dataset_ref)
    except Exception as exc:
        raise RuntimeError(f"El dataset '{dataset_ref}' no existe o no es accesible.") from exc


def obtener_archivos_locales(fuente_dir: Path) -> list[Path]:
    archivos = sorted(fuente_dir.glob("**/*.csv"))
    if not archivos:
        raise RuntimeError(f"No se encontraron archivos CSV en {fuente_dir}")
    return archivos


def subir_archivos_a_gcs(bucket: storage.Bucket, fuente: str, archivos: list[Path]) -> str:
    """Sube los CSV de una fuente a gs://bucket/raw/{fuente}/... y retorna el URI wildcard."""
    for archivo in archivos:
        ruta_relativa = archivo.relative_to(FUENTES[fuente])
        blob_name = f"raw/{fuente}/{ruta_relativa.as_posix()}"
        bucket.blob(blob_name).upload_from_filename(str(archivo))

    print(f"[{fuente}] {len(archivos)} archivo(s) subido(s) a gs://{GCS_BUCKET_NAME}/raw/{fuente}/")
    return f"gs://{GCS_BUCKET_NAME}/raw/{fuente}/*.csv"


def cargar_a_bigquery(bq_client: bigquery.Client, fuente: str, gcs_uri: str) -> None:
    """Carga todos los CSV de una fuente a raw.{fuente}, todas las columnas como STRING.

    WRITE_TRUNCATE: cada corrida reemplaza la tabla completa, sin duplicar filas al reprocesar.
    """
    tabla_id = f"{GCP_PROJECT_ID}.{BQ_DATASET_RAW}.{fuente}"

    columnas = obtener_columnas_csv(FUENTES[fuente])
    schema = [bigquery.SchemaField(col, "STRING") for col in columnas]

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    job = bq_client.load_table_from_uri(gcs_uri, tabla_id, job_config=job_config)
    job.result()  # espera a que termine y levanta excepción si falla

    tabla = bq_client.get_table(tabla_id)
    print(f"[{fuente}] cargado en {tabla_id}: {tabla.num_rows} filas.")


def obtener_columnas_csv(fuente_dir: Path) -> list[str]:
    """Lee el encabezado del primer CSV de la fuente para definir el schema STRING."""
    primer_archivo = sorted(fuente_dir.glob("**/*.csv"))[0]
    with open(primer_archivo, encoding="utf-8") as fh:
        encabezado = fh.readline().strip()
    return encabezado.split(",")


def main() -> None:
    validar_configuracion()

    storage_client = storage.Client(project=GCP_PROJECT_ID)
    bq_client = bigquery.Client(project=GCP_PROJECT_ID)

    validar_bucket_y_dataset(storage_client, bq_client)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)

    for fuente, fuente_dir in FUENTES.items():
        archivos = obtener_archivos_locales(fuente_dir)
        gcs_uri = subir_archivos_a_gcs(bucket, fuente, archivos)
        cargar_a_bigquery(bq_client, fuente, gcs_uri)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
