"""Extracción: valida la disponibilidad de los 48 CSV crudos (Toctoc + PortalInmobiliario,
2023-2024) y obtiene la serie histórica de la UF desde la API de mindicador.cl, guardándola
en data/raw/uf/. 
"""

import os
import sys
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

MINDICADOR_API_URL = os.getenv("MINDICADOR_API_URL")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
TOCTOC_DIR = RAW_DIR / "toctoc"
PORTAL_DIR = RAW_DIR / "portal_inmobiliario"
UF_OUTPUT_PATH = RAW_DIR / "uf" / "uf_2023_2024.csv"

# Carga histórica cerrada: el período del proyecto es 2023-2024.
ANIOS_ESPERADOS = {2023, 2024}
MESES = [f"{m:02d}" for m in range(1, 13)]


def obtener_anios_disponibles(fuente_dir: Path) -> set[int]:
    return {int(p.name) for p in fuente_dir.iterdir() if p.is_dir() and p.name.isdigit()}


def validar_fuentes_raw() -> list[int]:
    """Valida que los años esperados y los 48 CSV mensuales existan en data/raw.

    Retorna los años a consultar en la API, derivados de las carpetas presentes,
    una vez confirmado que cubren el período esperado.
    """
    anios_toctoc = obtener_anios_disponibles(TOCTOC_DIR)
    anios_portal = obtener_anios_disponibles(PORTAL_DIR)
    anios_presentes = anios_toctoc | anios_portal

    anios_faltantes = ANIOS_ESPERADOS - anios_presentes
    if anios_faltantes:
        raise RuntimeError(
            f"Faltan años esperados en data/raw: {sorted(anios_faltantes)}. "
            f"toctoc: {sorted(anios_toctoc)}, portal_inmobiliario: {sorted(anios_portal)}."
        )

    archivos_faltantes = [
        str(fuente_dir / str(anio) / f"{anio}-{mes}.csv")
        for anio in sorted(ANIOS_ESPERADOS)
        for mes in MESES
        for fuente_dir in (TOCTOC_DIR, PORTAL_DIR)
        if not (fuente_dir / str(anio) / f"{anio}-{mes}.csv").exists()
    ]
    if archivos_faltantes:
        raise RuntimeError(
            f"Faltan {len(archivos_faltantes)} archivo(s) CSV esperados:\n"
            + "\n".join(archivos_faltantes)
        )

    total_esperado = len(ANIOS_ESPERADOS) * len(MESES) * 2
    print(
        f"Validación OK: {total_esperado} archivos CSV disponibles "
        f"({sorted(ANIOS_ESPERADOS)}, Toctoc + PortalInmobiliario)."
    )
    return sorted(anios_presentes)


def extraer_serie_uf_anio(anio: int) -> pd.DataFrame:
    """Obtiene la serie UF de un año desde mindicador.cl, validando la respuesta."""
    url = f"{MINDICADOR_API_URL}/uf/{anio}"
    response = requests.get(url, timeout=15)
    response.raise_for_status()  # HTTP correcto

    payload = response.json()
    if "serie" not in payload:
        raise RuntimeError(f"Respuesta de la API para {anio} no contiene la clave 'serie'.")

    serie = payload["serie"]
    if not serie:
        raise RuntimeError(f"La serie UF de {anio} llegó vacía.")

    df = pd.DataFrame(serie)[["fecha", "valor"]]
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    if df["fecha"].isna().any():
        raise RuntimeError(f"La serie UF de {anio} tiene fechas no parseables.")
    if df["valor"].isna().any():
        raise RuntimeError(f"La serie UF de {anio} tiene valores nulos.")

    return df


def validar_cobertura(df: pd.DataFrame, anios: list[int]) -> None:
    """Verifica que cada año tenga una cobertura de días cercana al calendario completo."""
    resumen = []
    for anio in anios:
        dias_anio = (df["fecha"].dt.year == anio).sum()
        dias_esperados = 366 if anio % 4 == 0 else 365
        if dias_anio < dias_esperados * 0.95:
            raise RuntimeError(
                f"Cobertura insuficiente para {anio}: {dias_anio} de {dias_esperados} días esperados."
            )
        resumen.append(f"{anio}={dias_anio} días")
    print("Cobertura OK: " + ", ".join(resumen))


def main() -> None:
    if not MINDICADOR_API_URL:
        raise RuntimeError("MINDICADOR_API_URL no está definido en .env")

    anios_a_consultar = validar_fuentes_raw()

    series = [extraer_serie_uf_anio(anio) for anio in anios_a_consultar]
    df_uf = pd.concat(series, ignore_index=True).sort_values("fecha").reset_index(drop=True)

    validar_cobertura(df_uf, anios_a_consultar)

    UF_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_uf.to_csv(UF_OUTPUT_PATH, index=False)
    print(f"Serie UF guardada en {UF_OUTPUT_PATH} ({len(df_uf)} filas).")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
