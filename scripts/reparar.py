#!/usr/bin/env python3
"""Repara datos DERIVADOS que una fórmula equivocada dejó mal en la base.

    python scripts/reparar.py            # dice qué haría, sin tocar nada
    python scripts/reparar.py --aplicar  # borra y deja que la ingesta rehaga

La base es *append-only* a propósito: una reexpresión entra como fila nueva y la
vieja se conserva, porque una consulta con corte anterior tiene que seguir viendo
lo que se sabía entonces (P1). Eso vale para los datos de FUENTE. No vale para
los DERIVADOS: si la fórmula que los generó estaba mal, la fila no es un dato
histórico, es un error de cálculo, y conservarla no preserva nada —solo mantiene
el error—. Peor: la llave única incluye la fuente, así que volver a correr la
ingesta con la fórmula corregida NO la reemplaza, la descarta por duplicada.

De ahí este script. Solo toca filas con fuente derivada, nunca primarias, y deja
constancia en la bitácora de qué borró y por qué. Después hay que correr la
ingesta para que se vuelvan a generar bien.

Reparación 1 — conteos de acciones no positivos
-----------------------------------------------
El acumulado de acciones básicas y diluidas es el PROMEDIO del periodo, no la
suma. Derivar ``Q4 = FY − 9M`` sobre dos promedios da aproximadamente −1 × el
promedio, y así los diez emisores acabaron con un cuarto trimestre de 2025 con
acciones NEGATIVAS. Un conteo negativo le voltea el signo a todo lo que se divide
entre él: AFFO por acción, NAV por acción, P/AFFO. Ninguna suma lo delata.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from src.config import FUENTES_PRIMARIAS, RUTA_BD, Estado  # noqa: E402
from src.datos import esquema  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402

CONCEPTOS_ACCIONES = ("acciones_basicas", "acciones_diluidas")


def acciones_no_positivas(repo: Repositorio) -> pd.DataFrame:
    """Filas de conteo de acciones que no pueden ser un dato. Ninguna es primaria."""
    with repo.motor.begin() as cx:
        filas = pd.read_sql(
            select(esquema.hechos).where(
                esquema.hechos.c.concepto.in_(CONCEPTOS_ACCIONES),
                esquema.hechos.c.valor <= 0,
            ),
            cx,
        )
    return filas


def reparar(repo: Repositorio, *, aplicar: bool) -> int:
    filas = acciones_no_positivas(repo)
    if filas.empty:
        print("No hay conteos de acciones no positivos. Nada que reparar.")
        return 0

    primarias = filas[filas["fuente"].isin(FUENTES_PRIMARIAS)]
    if not primarias.empty:
        # No debería pasar nunca: significaría que la SEC publicó un conteo
        # negativo. Si pasa, es un problema de lectura, no de derivación, y este
        # script no es el lugar para resolverlo.
        print(f"ALTO: {len(primarias)} fila(s) NO derivadas con acciones ≤ 0.")
        print(primarias[["ticker", "concepto", "fecha_dato", "valor", "fuente"]].to_string())
        return 1

    print(f"{len(filas)} fila(s) derivadas con conteo de acciones no positivo:\n")
    resumen = (
        filas.groupby(["ticker", "concepto"])
        .agg(n=("valor", "size"), peor=("valor", "min"))
        .reset_index()
    )
    for _, r in resumen.iterrows():
        print(f"  {r['ticker']:5s} {r['concepto']:18s} {int(r['n'])} fila(s), la peor {r['peor']:,.0f}")

    if not aplicar:
        print("\nEn seco. Corre con --aplicar para borrarlas.")
        return 0

    with repo.motor.begin() as cx:
        resultado = cx.execute(
            delete(esquema.hechos).where(
                esquema.hechos.c.concepto.in_(CONCEPTOS_ACCIONES),
                esquema.hechos.c.valor <= 0,
            )
        )
    borradas = resultado.rowcount or 0
    repo.registrar_bitacora(
        "reparacion",
        f"Se borraron {borradas} conteos de acciones derivados con valor no positivo. "
        "Venían de restar promedios de periodo como si fueran sumas. "
        "Hay que correr la ingesta para regenerarlos con la fórmula corregida.",
    )
    print(f"\nBorradas {borradas} fila(s). Corre `python scripts/ingesta.py` para regenerarlas.")
    return 0


def olvidar_sospechosos(repo: Repositorio, *, tickers: list[str] | None, aplicar: bool) -> int:
    """Borra los registros ``sospechoso`` para que un parser corregido los rehaga.

    La llave única de ``hechos`` es (ticker, concepto, tipo, fecha, publicación,
    fuente). **No incluye el estado**, y con razón: el estado es un juicio del
    validador, no parte de la identidad del hecho. La consecuencia es que un
    registro marcado ``sospechoso`` NO puede ascender a ``valido`` volviendo a
    correr la ingesta: la fila corregida entra con la misma llave y se descarta
    por duplicada, en silencio.

    Un registro sospechoso es evidencia de que el PARSER falló, no un dato de
    fuente: se vuelve a derivar leyendo otra vez el mismo filing. Por eso, cuando
    se corrige una ficha o el parser, hay que olvidarlos para que la corrección
    llegue a la base. Es lo que le pasó a EPRT y GNL: sus fichas nuevas cuadraban
    los cinco y catorce periodos, y la base seguía mostrándolos en blanco.
    """
    condiciones = [esquema.hechos.c.estado == Estado.SOSPECHOSO]
    if tickers:
        condiciones.append(esquema.hechos.c.ticker.in_(tickers))

    with repo.motor.begin() as cx:
        filas = pd.read_sql(select(esquema.hechos).where(*condiciones), cx)
    if filas.empty:
        print("No hay registros sospechosos. Nada que olvidar.")
        return 0

    print(f"{len(filas)} registro(s) sospechosos:\n")
    for _, r in (
        filas.groupby("ticker").size().reset_index(name="n").sort_values("n", ascending=False)
    ).iterrows():
        print(f"  {r['ticker']:5s} {int(r['n']):>4d}")

    if not aplicar:
        print("\nEn seco. Corre con --aplicar para borrarlos.")
        return 0

    with repo.motor.begin() as cx:
        borradas = cx.execute(delete(esquema.hechos).where(*condiciones)).rowcount or 0
    repo.registrar_bitacora(
        "reparacion",
        f"Se olvidaron {borradas} registros sospechosos"
        + (f" de {', '.join(tickers)}" if tickers else "")
        + ". Eran evidencia de un parser anterior, no datos de fuente. "
        "Hay que correr la ingesta para volver a leerlos.",
    )
    print(f"\nBorrados {borradas}. Corre `python scripts/ingesta.py` para volver a leerlos.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bd", default=str(RUTA_BD))
    p.add_argument("--aplicar", action="store_true", help="Sin esto, solo reporta.")
    p.add_argument(
        "--olvidar-sospechosos",
        action="store_true",
        help="Borra los registros sospechosos para que un parser corregido los rehaga.",
    )
    p.add_argument("--tickers", help="Solo estos emisores, separados por comas.")
    args = p.parse_args()

    repo = Repositorio(ruta=Path(args.bd))
    if args.olvidar_sospechosos:
        tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None
        return olvidar_sospechosos(repo, tickers=tickers, aplicar=args.aplicar)
    return reparar(repo, aplicar=args.aplicar)


if __name__ == "__main__":
    raise SystemExit(main())
