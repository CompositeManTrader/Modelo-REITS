#!/usr/bin/env python3
"""Estudio de largo plazo de un emisor.

    python scripts/estudio.py mercado O     # baja, valida y versiona precio y dividendos desde el IPO
    python scripts/estudio.py resumen O     # imprime las cifras del estudio
    python scripts/estudio.py pdf O         # genera el entregable en PDF

``mercado`` es lo único que toca la red. Se niega a guardar si la serie no cuadra
contra el proveedor diario y las anclas NYSE: una historia larga que no coincide
con la corta en el traslape no es historia, es otro instrumento.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.datos.repositorio import Repositorio  # noqa: E402
from src.estudio import mercado  # noqa: E402


def cmd_mercado(ticker: str) -> int:
    repo = Repositorio()
    hoy = dt.date.today()
    print(f"Descargando la historia de {ticker} desde el primer día de cotización…")
    crudo = mercado.descargar(ticker)
    print(f"  {len(crudo.precios):,} cierres, {len(crudo.dividendos):,} dividendos, "
          f"eventos reportados: {[(str(f), round(x, 4)) for f, x in crudo.eventos]}")
    precios, dividendos, eventos = mercado.desajustar(crudo)
    for e in eventos:
        print(f"  {e.fecha}  {e.tipo:9s} ×{e.factor}  {e.descripcion}")
    dividendos, correcciones = mercado.aplicar_correcciones(ticker, dividendos)
    if correcciones:
        print("\nCorrecciones contra el reporte del emisor:")
        for c in correcciones:
            print(f"  {c[:150]}")

    validacion = mercado.validar(
        precios,
        dividendos,
        crudo_diario=repo.serie_precio(ticker, asof=hoy),
        dividendos_diarios=repo.dividendos(ticker, asof=hoy),
        anclas=repo.anclas(ticker),
    )
    print("\nValidación contra fuentes que no dependen de este proveedor:")
    print(f"  traslape con el precio crudo diario: {validacion.traslape_n:,} días, "
          f"error máximo {validacion.traslape_error_max:.4%}")
    for a in validacion.anclas:
        print(f"  ancla NYSE {a['fecha']}: real {a['real']:.2f}, reconstruido "
              f"{a['reconstruido']:.2f}, error {a['error']:+.3%}")
    if validacion.dividendos_traslape_n:
        print(f"  dividendos en traslape: {validacion.dividendos_traslape_n}, "
              f"error máximo {validacion.dividendos_error_max:.4%}")
    if not validacion.aprobada:
        print("\nNO SE GUARDA: la serie no cuadra.")
        return 1
    destino = mercado.guardar(
        ticker, precios, dividendos, eventos, validacion,
        primera_cotizacion=crudo.primera_cotizacion, correcciones=correcciones,
    )
    print(f"\nGuardado en {destino.relative_to(RAIZ)}")
    return 0


def _armar(ticker: str):
    import pandas as pd

    from src.estudio import estudio

    ajustado = pd.read_csv(
        mercado.dir_de(ticker) / mercado.ARCHIVO_PRECIOS, parse_dates=["fecha"]
    ).set_index("fecha")["ajustado_proveedor"]
    return estudio.armar(Repositorio(), ticker, asof=dt.date.today(), ajustado_proveedor=ajustado)


def cmd_resumen(ticker: str) -> int:
    e = _armar(ticker)
    print(f"{e.ticker} al {e.hoy.fecha:%Y-%m-%d}\n")
    for c in e.conclusiones:
        print(f"[{c.tono}] {c.titulo}\n  {c.texto}\n")
    for a in e.avisos:
        print(f"aviso: {a}")
    return 0


def cmd_pdf(ticker: str) -> int:
    from src.export.pdf_estudio import generar_pdf

    e = _armar(ticker)
    destino = RAIZ / "docs" / "estudios" / f"estudio_{ticker}.pdf"
    generar_pdf(e, destino)
    print(f"PDF: {destino.relative_to(RAIZ)} ({destino.stat().st_size / 1024:,.0f} KB)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)
    for nombre in ("mercado", "resumen", "pdf"):
        s = sub.add_parser(nombre)
        s.add_argument("ticker")
    args = p.parse_args()
    ticker = args.ticker.upper()
    if args.comando == "mercado":
        return cmd_mercado(ticker)
    if args.comando == "resumen":
        return cmd_resumen(ticker)
    return cmd_pdf(ticker)


if __name__ == "__main__":
    raise SystemExit(main())
