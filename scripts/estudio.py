#!/usr/bin/env python3
"""Estudio de largo plazo de un emisor.

    python scripts/estudio.py mercado O     # baja, valida y versiona precio y dividendos desde el IPO
    python scripts/estudio.py resumen O     # imprime las cifras del estudio
    python scripts/estudio.py pdf O         # genera el entregable en PDF
    python scripts/estudio.py tbill         # baja y versiona el T-bill a 3 meses (reserva del backtest)
    python scripts/estudio.py macro         # T-bill, bonos Baa e inflación de FRED (métodos de valuación)
    python scripts/estudio.py reglas O      # backtest de las reglas de decisión de un emisor
    python scripts/estudio.py reglas-pdf    # entregable del backtest de todos los emisores con estudio
    python scripts/estudio.py metodos       # métodos de valuación en el tiempo: PDF y Excel trimestral

``mercado`` y ``tbill`` son lo único que toca la red. Se niega a guardar si la serie no cuadra
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
    precios, dividendos, inicio = mercado.recortar_al_inicio(ticker, precios, dividendos)
    if inicio:
        print(f"\nSe corta al {inicio.fecha}: {inicio.motivo}")
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
        anclas=mercado.anclas_del_estudio(ticker, repo.anclas(ticker)),
        rangos=mercado.RANGOS_TRIMESTRALES.get(ticker, ()),
        excepciones=mercado.EXCEPCIONES_DE_RANGO.get(ticker, {}),
        excepciones_anclas=mercado.EXCEPCIONES_DE_ANCLA.get(ticker, {}),
    )
    print("\nValidación contra fuentes que no dependen de este proveedor:")
    print(f"  traslape con el precio crudo diario: {validacion.traslape_n:,} días, "
          f"error máximo {validacion.traslape_error_max:.4%}")
    for a in validacion.anclas:
        print(f"  ancla NYSE {a['fecha']}: real {a['real']:.2f}, reconstruido "
              f"{a['reconstruido']:.2f}, error {a['error']:+.3%}")
    for a in validacion.anclas_aceptadas:
        print(f"  ancla aceptada {a['fecha']}: real {a['real']:.2f}, reconstruido "
              f"{a['reconstruido']:.2f}, error {a['error']:+.3%}; {a['explicacion'][:90]}…")
    if validacion.rangos_n:
        print(f"  rangos trimestrales del emisor: {validacion.rangos_n} revisados, "
              f"{len(validacion.rangos_fuera)} con cierres fuera")
        for r in validacion.rangos_fuera:
            print(f"    {r}")
        for r in validacion.rangos_aceptados:
            print(f"    aceptado {r['trimestre']}: {r['explicacion'][:110]}…")
    if validacion.dividendos_traslape_n:
        print(f"  dividendos en traslape: {validacion.dividendos_traslape_n}, "
              f"error máximo {validacion.dividendos_error_max:.4%}")
    if not validacion.aprobada:
        print("\nNO SE GUARDA: la serie no cuadra.")
        return 1
    destino = mercado.guardar(
        ticker, precios, dividendos, eventos, validacion,
        primera_cotizacion=crudo.primera_cotizacion, correcciones=correcciones, inicio=inicio,
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


def cmd_tbill() -> int:
    from src.estudio import reglas

    destino = reglas.guardar_tbill(reglas.descargar_tbill())
    t = reglas.cargar_tbill()
    print(f"T-bill 3M: {len(t):,} días, {t.index.min():%Y-%m-%d} a {t.index.max():%Y-%m-%d} → "
          f"{destino.relative_to(RAIZ)}")
    return 0


def cmd_macro() -> int:
    from src.estudio import macro

    for nombre in macro.SERIES:
        destino = macro.guardar(nombre, macro.descargar(nombre))
        s = macro.cargar(nombre)
        print(f"{nombre}: {len(s):,} datos, {s.index.min():%Y-%m-%d} a {s.index.max():%Y-%m-%d} → "
              f"{destino.relative_to(RAIZ)}")
    return 0


def cmd_reglas(ticker: str) -> int:
    from src.estudio import reglas

    r = reglas.backtest(_armar(ticker))
    print(reglas.resumen_en_texto(r))
    return 0


def cmd_reglas_pdf() -> int:
    from src.estudio import reglas
    from src.export.pdf_reglas import generar_pdf

    resultados = [reglas.backtest(_armar(t)) for t in mercado.con_estudio()]
    destino = RAIZ / "docs" / "estudios" / "reglas_de_decision.pdf"
    generar_pdf(resultados, destino)
    print(f"PDF: {destino.relative_to(RAIZ)} ({destino.stat().st_size / 1024:,.0f} KB)")
    return 0


def cmd_metodos() -> int:
    from src.estudio import metodos
    from src.export import excel_metodos
    from src.export.pdf_metodos import generar_pdf

    r = metodos.estudiar({t: _armar(t) for t in mercado.con_estudio()})
    for c in metodos.conclusiones(r):
        print(f"\n{c.titulo}\n  {c.texto}")
    carpeta = RAIZ / "docs" / "estudios"
    for destino in (generar_pdf(r, carpeta / "metodos_de_valuacion.pdf"),
                    excel_metodos.exportar(r, carpeta / "valuacion_trimestral.xlsx")):
        print(f"\n{destino.relative_to(RAIZ)} ({destino.stat().st_size / 1024:,.0f} KB)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)
    for nombre in ("mercado", "resumen", "pdf", "reglas"):
        s = sub.add_parser(nombre)
        s.add_argument("ticker")
    sub.add_parser("tbill")
    sub.add_parser("macro")
    sub.add_parser("reglas-pdf")
    sub.add_parser("metodos")
    args = p.parse_args()
    if args.comando == "tbill":
        return cmd_tbill()
    if args.comando == "macro":
        return cmd_macro()
    if args.comando == "reglas-pdf":
        return cmd_reglas_pdf()
    if args.comando == "metodos":
        return cmd_metodos()
    ticker = args.ticker.upper()
    if args.comando == "mercado":
        return cmd_mercado(ticker)
    if args.comando == "resumen":
        return cmd_resumen(ticker)
    if args.comando == "reglas":
        return cmd_reglas(ticker)
    return cmd_pdf(ticker)


if __name__ == "__main__":
    raise SystemExit(main())
