"""La bitácora de pruebas: cada evaluación que se corre queda anotada.

Con cien intentos alguno siempre sale bien por azar. Las correcciones por pruebas
múltiples (Sharpe deflactado, PBO) necesitan saber cuántos intentos hubo, y el número
que uno recuerda siempre es menor que el real. Por eso cada evaluación de una señal, una
variante o un parámetro se anota aquí al correrse, con su commit, y el conteo sale de
este archivo.

También quedan aquí las aperturas de muestra: cada vez que se abre la validación o la
prueba final, y cada modelo que se congela.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import subprocess
from pathlib import Path

import pandas as pd

from src.config import DIR_DATOS

RUTA = DIR_DATOS / "investigacion" / "bitacora.csv"
COLUMNAS = ("momento", "fase", "familia", "prueba", "muestra", "parametros", "metrica", "valor", "commit")
TIPOS_DE_EVENTO = ("prueba", "apertura", "congelado")


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).resolve().parent, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def registrar(*, fase: str, familia: str, prueba: str, muestra: str, parametros: dict | None = None,
              metrica: str = "", valor: float | str | None = None, ruta: Path | None = None) -> None:
    """Anota una evaluación. ``familia`` agrupa los intentos que compiten entre sí."""
    destino = ruta or RUTA
    destino.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not destino.exists()
    with destino.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(COLUMNAS)
        w.writerow([dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), fase, familia, prueba, muestra,
                    json.dumps(parametros or {}, sort_keys=True, ensure_ascii=False), metrica,
                    "" if valor is None else valor, _commit()])


def leer(ruta: Path | None = None) -> pd.DataFrame:
    origen = ruta or RUTA
    if not origen.exists():
        return pd.DataFrame(columns=COLUMNAS)
    return pd.read_csv(origen, dtype=str, keep_default_na=False)


def intentos(familia: str | None = None, *, ruta: Path | None = None) -> int:
    """Cuántas configuraciones distintas se probaron (prueba + parámetros), sin contar repeticiones.

    Las aperturas y los congelados no son intentos.
    """
    b = leer(ruta)
    b = b[~b["familia"].isin(["apertura", "congelado"])]
    if familia is not None:
        b = b[b["familia"] == familia]
    return int(b[["prueba", "parametros"]].drop_duplicates().shape[0])


def modelos_congelados(ruta: Path | None = None) -> set[str]:
    b = leer(ruta)
    return set(b.loc[b["familia"] == "congelado", "prueba"])
