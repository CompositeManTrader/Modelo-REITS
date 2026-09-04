#!/usr/bin/env python3
"""Ingesta desde fuente primaria: SEC EDGAR y tasas.

    python scripts/ingesta.py --tickers O,NNN --desde 2020-01-01
    python scripts/ingesta.py --solo-tasas

Respeta el límite de 10 solicitudes por segundo de la SEC y exige un User-Agent
identificable. Configúralo con la variable de entorno ``SEC_USER_AGENT``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import RUTA_BD, SERIE_UST10, asegurar_directorios  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta import tasas as mod_tasas  # noqa: E402
from src.ingesta.orquestador import correr_ingesta  # noqa: E402


def ingestar_tasas(repo: Repositorio) -> int:
    """Trae las series macro que sí tienen fuente pública sin llave."""
    total = 0
    for serie in mod_tasas.SERIES_FRED:
        try:
            filas = mod_tasas.ingestar_fred(serie)
            n = repo.guardar_tasas(filas)
            total += n
            print(f"  {serie:10s} {n:>7,} observaciones nuevas (FRED)")
        except mod_tasas.ErrorTasas as exc:
            print(f"  {serie:10s} ERROR: {exc}")

    for serie in mod_tasas.SERIES_BANXICO:
        try:
            filas = mod_tasas.ingestar_banxico(serie)
            n = repo.guardar_tasas(filas)
            total += n
            print(f"  {serie:10s} {n:>7,} observaciones nuevas (Banxico)")
        except mod_tasas.ErrorTasas as exc:
            print(f"  {serie:10s} omitida: {str(exc)[:90]}")
    return total


def main() -> int:
    p = argparse.ArgumentParser(description="Ingesta desde SEC EDGAR y fuentes de tasas.")
    p.add_argument("--tickers", help="Lista separada por comas. Por omisión, todo el universo.")
    p.add_argument("--desde", help="Fecha mínima de presentación (AAAA-MM-DD).")
    p.add_argument("--bd", default=str(RUTA_BD))
    p.add_argument("--max-filings", type=int, default=8, help="Máximo de 8-K por emisor.")
    p.add_argument("--sin-xbrl", action="store_true", help="Omite companyfacts (es lo más pesado).")
    p.add_argument("--solo-tasas", action="store_true")
    args = p.parse_args()

    asegurar_directorios()
    repo = Repositorio(ruta=args.bd)
    desde = dt.date.fromisoformat(args.desde) if args.desde else None

    print("Tasas y macro:")
    n_tasas = ingestar_tasas(repo)
    if args.solo_tasas:
        print(f"\nListo: {n_tasas:,} observaciones de tasas.")
        return 0

    print("\nFundamentales desde EDGAR:")
    resumenes = correr_ingesta(
        repo,
        tickers=args.tickers.split(",") if args.tickers else None,
        desde=desde,
        max_filings=args.max_filings,
        con_xbrl=not args.sin_xbrl,
    )

    sospechosos = 0
    for r in resumenes:
        print(f"  {r.como_texto()}")
        sospechosos += r.sospechosos
        for n in r.novedades:
            print(f"      · {n}")
        for e in r.errores[:5]:
            print(f"      ! {e[:160]}")

    ust = repo.valor_tasa(SERIE_UST10, asof=dt.date.today())
    if ust is not None:
        print(f"\nUST 10 años al corte: {ust:.2%}")
    if sospechosos:
        print(
            f"\n{sospechosos} registro(s) quedaron marcados SOSPECHOSOS y no se usan en "
            "cálculos hasta revisión manual. Revísalos en la página de Valuación."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
