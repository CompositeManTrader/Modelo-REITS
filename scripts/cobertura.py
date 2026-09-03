#!/usr/bin/env python3
"""Mide cuántos periodos parsea y valida el sistema por emisor, contra la SEC en vivo.

    python scripts/cobertura.py [--desde 2026-01-01] [--max-filings 2]

Existe porque la cobertura del parser es la limitación real de esta plataforma y
conviene medirla, no estimarla. Cada emisor reporta su conciliación de AFFO con
etiquetas ligeramente distintas; lo que no cuadra queda marcado ``sospechoso`` y
no entra a los cálculos, que es el comportamiento diseñado, pero significa que
ampliar la cobertura es trabajo de taxonomía por emisor.

Requiere red y respeta el límite de 10 solicitudes por segundo de la SEC.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import UNIVERSO_INICIAL  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta.edgar import ClienteEdgar  # noqa: E402
from src.ingesta.orquestador import ingestar_fundamentales  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Mide la cobertura del parser por emisor.")
    p.add_argument("--desde", default="2026-01-01", help="Fecha mínima de presentación.")
    p.add_argument("--max-filings", type=int, default=2)
    p.add_argument("--tickers", help="Lista separada por comas.")
    args = p.parse_args()

    desde = dt.date.fromisoformat(args.desde)
    filtro = set(args.tickers.split(",")) if args.tickers else None
    emisores = [e for e in UNIVERSO_INICIAL if filtro is None or e.ticker in filtro]

    with tempfile.TemporaryDirectory() as tmp:
        repo = Repositorio(ruta=Path(tmp) / "cobertura.db")
        cliente = ClienteEdgar()

        print(f"Cobertura del parser desde {desde}, hasta {args.max_filings} filings por emisor.\n")
        print(f"{'Emisor':8s} {'sector':16s} {'periodos':>9s} {'validos':>8s} {'sospech':>8s}  motivo")
        print("-" * 118)

        total_v = total_s = 0
        for e in emisores:
            r = ingestar_fundamentales(
                repo, cliente, e.ticker, e.cik, desde=desde,
                max_filings=args.max_filings, sector=e.sector,
            )
            total_v += r.validos
            total_s += r.sospechosos
            motivo = r.errores[0].split(": ", 1)[-1][:62] if r.errores else ""
            print(
                f"{e.ticker:8s} {e.sector:16s} {r.periodos_extraidos:>9d} "
                f"{r.validos:>8d} {r.sospechosos:>8d}  {motivo}"
            )

        print("-" * 118)
        print(f"{'TOTAL':8s} {'':16s} {'':>9s} {total_v:>8d} {total_s:>8d}")
        print(
            "\nUn periodo VÁLIDO es uno cuya conciliación cuadra contra los subtotales que el\n"
            "propio emisor publica. Los SOSPECHOSOS se guardan marcados y no participan en\n"
            "ningún cálculo: el sistema prefiere no tener el dato a tenerlo mal."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
