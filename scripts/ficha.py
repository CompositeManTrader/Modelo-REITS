#!/usr/bin/env python3
"""Genera el borrador de la ficha de un emisor leyendo sus filings reales.

    python scripts/ficha.py --ticker EXR [--desde 2026-01-01] [--max-filings 4]

Recorre las tablas de conciliación que el emisor publicó, junta TODAS las
etiquetas que aparecen y dice qué resuelve cada una hoy. Lo que sale es un bloque
``_ficha(...)`` listo para pegar en ``src/ingesta/taxonomia.py``, con las
etiquetas sin resolver marcadas para que un humano las llene.

Existe para que agregar un emisor sea llenar una ficha contra su documento, en
vez de escribir expresiones regulares y ver a quién más rompen. Requiere red.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup  # noqa: E402

from src.config import EMISOR_POR_TICKER  # noqa: E402
from src.ingesta.edgar import ClienteEdgar  # noqa: E402
from src.ingesta.parser_affo import (  # noqa: E402
    _es_tabla_de_conciliacion,
    _tabla_a_matriz,
    normalizar_etiqueta,
)
from src.ingesta.taxonomia import IGNORAR, canonizar, ficha_de

# Filas que son estructura de la tabla, no partidas. Se proponen como IGNORAR
# para que la ficha lo diga explícitamente en vez de dejarlas sin declarar.
_ESTRUCTURA = (
    "adjustments",
    "total adjustments",
    "summary",
    "reconciliation",
    "less",
    "add",
    "per share",
    "per diluted share",
)


_SUBTOTALES = {"ffo", "ffo_normalizado", "affo", "noi"}


def _parece_conciliacion(filas: list[list[str]]) -> bool:
    """¿Esta tabla es una conciliación, o solo menciona el AFFO?

    El suplemento de un emisor grande trae cientos de tablas —índice, deuda,
    vencimientos, diversificación por inquilino— y muchas mencionan FFO o AFFO de
    pasada. Meterlas a la ficha la llena de etiquetas que no son de la cascada y
    la vuelve ilegible, que es lo contrario de para qué existe.

    Una conciliación de verdad tiene las dos cosas: al menos un subtotal y varias
    partidas que suman hacia él.
    """
    claves = [normalizar_etiqueta(f[0]) for f in filas]
    claves = [c for c in claves if c]
    tiene_subtotal = any(c in _SUBTOTALES for c in claves)
    partidas = sum(1 for c in claves if c not in _SUBTOTALES)
    return tiene_subtotal and partidas >= 3


def etiquetas_del_emisor(cliente: ClienteEdgar, ticker: str, cik: str, *,
                         desde: dt.date, max_filings: int) -> list[tuple[str, int]]:
    """Todas las etiquetas de fila de sus tablas de conciliación, con su frecuencia."""
    conteo: Counter[str] = Counter()
    revisados = 0
    for filing in cliente.listar_filings(cik, ticker, formularios=("8-K",), desde=desde):
        if revisados >= max_filings:
            break
        try:
            documentos = cliente.documentos_resultados(filing)
        except Exception as exc:  # noqa: BLE001 - un filing ilegible no detiene el barrido
            print(f"  (no se pudo leer {filing.fecha_presentacion}: {exc})", file=sys.stderr)
            continue
        if not documentos:
            continue
        revisados += 1
        for _url, html in documentos:
            for tabla in BeautifulSoup(html, "lxml").find_all("table"):
                matriz = _tabla_a_matriz(tabla)
                if len(matriz) < 3 or not _es_tabla_de_conciliacion(matriz):
                    continue
                filas = [
                    f for f in matriz
                    if f and f[0].strip()
                    # Solo filas con algún número: un encabezado sin cifras no es
                    # una línea de la conciliación.
                    and any(any(c.isdigit() for c in celda) for celda in f[1:])
                ]
                if not _parece_conciliacion(filas):
                    continue
                for fila in filas:
                    conteo[fila[0].strip()] += 1
    return conteo.most_common()


def main() -> int:
    p = argparse.ArgumentParser(description="Borrador de ficha de un emisor.")
    p.add_argument("--ticker", required=True)
    p.add_argument("--desde", default="2026-01-01")
    p.add_argument("--max-filings", type=int, default=4)
    args = p.parse_args()

    ticker = args.ticker.upper()
    emisor = EMISOR_POR_TICKER.get(ticker)
    if emisor is None:
        print(f"{ticker} no está en el universo.", file=sys.stderr)
        return 1

    cliente = ClienteEdgar()
    etiquetas = etiquetas_del_emisor(
        cliente, ticker, emisor.cik,
        desde=dt.date.fromisoformat(args.desde), max_filings=args.max_filings,
    )
    if not etiquetas:
        print(f"No se encontraron tablas de conciliación para {ticker}.", file=sys.stderr)
        return 1

    ficha = ficha_de(ticker)
    vistas: set[str] = set()
    filas: list[tuple[str, str, str, bool]] = []
    for etiqueta, _veces in etiquetas:
        canon = canonizar(etiqueta)
        if not canon or canon in vistas:
            continue
        vistas.add(canon)
        declarada = ficha is not None and canon in ficha.lineas
        if declarada:
            clave = ficha.lineas[canon]
        else:
            clave = normalizar_etiqueta(etiqueta) or ""
            if not clave and any(e in canon for e in _ESTRUCTURA):
                clave = IGNORAR
        filas.append((etiqueta, canon, clave, declarada))

    sin_resolver = [f for f in filas if not f[2]]
    print(f"\n{ticker} — {len(filas)} etiquetas distintas, "
          f"{len(sin_resolver)} sin resolver.\n")

    print("# " + "-" * 84)
    print(f"# {ticker} — {emisor.nombre}")
    print("# Etiquetas tomadas de sus 8-K. Revisa las marcadas SIN RESOLVER.")
    print("# " + "-" * 84)
    print("registrar(_ficha(")
    print(f'    "{ticker}",')
    print(f'    "{emisor.nombre}",')
    print('    subtotales=("ffo", "affo"),  # <- declara los que ESTE emisor publica')
    print("    lineas={")
    for etiqueta, _canon, clave, declarada in filas:
        limpia = etiqueta.replace('"', "'")
        if clave:
            marca = "" if declarada else "  # heredada de los patrones compartidos"
            valor = "IGNORAR" if clave == IGNORAR else f'"{clave}"'
            print(f'        "{limpia}": {valor},{marca}')
        else:
            print(f'        "{limpia}": "",  # <<< SIN RESOLVER')
    print("    },")
    print("))")

    if sin_resolver:
        print(f"\nFaltan {len(sin_resolver)} por decidir:", file=sys.stderr)
        for etiqueta, canon, _c, _d in sin_resolver:
            print(f"  · {etiqueta[:78]}\n      canónica: {canon[:78]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
