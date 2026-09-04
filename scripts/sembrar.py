#!/usr/bin/env python3
"""Siembra la base con datos de demostración para poder recorrer la aplicación.

    python scripts/sembrar.py [--tickers O,PLD] [--sin-fundamentales]

Todo lo que entra por aquí queda marcado ``DEMO`` y la interfaz lo señala. Para
datos de fuente primaria, corre ``scripts/ingesta.py``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import RUTA_BD, asegurar_directorios  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402
from src.datos.semilla import sembrar  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Siembra datos de demostración.")
    p.add_argument("--tickers", help="Lista separada por comas. Por omisión, todo el universo.")
    p.add_argument("--bd", default=str(RUTA_BD), help="Ruta de la base SQLite.")
    p.add_argument(
        "--sin-fundamentales",
        action="store_true",
        help="No genera AFFO de demostración (útil si ya corriste la ingesta de EDGAR).",
    )
    args = p.parse_args()

    asegurar_directorios()
    repo = Repositorio(ruta=args.bd)
    tickers = args.tickers.split(",") if args.tickers else None

    conteo = sembrar(repo, tickers=tickers, con_fundamentales=not args.sin_fundamentales)
    print(f"Base sembrada en {args.bd}")
    for k, v in conteo.items():
        print(f"  {k:14s} {v:>8,}")
    print(
        "\nRECORDATORIO: estos datos son de DEMOSTRACIÓN y están marcados como tales. "
        "No sirven para decidir. Corre scripts/ingesta.py para traer datos de la SEC."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
