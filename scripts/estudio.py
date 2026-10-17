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
    python scripts/estudio.py universo      # baja y versiona la lista, precios y dividendos del universo de REITs
    python scripts/estudio.py seleccion     # la prueba del universo: ¿la valuación sabe escoger REITs? (PDF)
    python scripts/estudio.py etfs          # USRT, SCHH y VNQ contra el índice de la investigación
    python scripts/estudio.py etfs --sin-descarga   # lo mismo con los datos ya versionados
    python scripts/estudio.py satelite explorar     # núcleo y satélite contra SCHH con la fase 6 (exploratoria)
    python scripts/estudio.py satelite elegir       # anota la aportación en papel del mes (feb, may, ago, nov)
    python scripts/estudio.py satelite elegir --vista-previa   # qué compraría hoy, sin anotar nada
    python scripts/estudio.py satelite evaluar      # la cuenta en papel contra SCHH (baja de Yahoo)
    python scripts/estudio.py ampliacion            # ¿se repiten las conclusiones de O, NNN y WPC en los otros siete?
    python scripts/estudio.py ampliacion-pdf        # el informe de la ampliación en PDF (después de ``ampliacion``)

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
    # El traslape compara al proveedor contra la base diaria, otro proveedor: va SIN las correcciones,
    # que no arreglan datos sino cómo se cuenta un pago (p. ej. uno partido en dos, EXR 2023).
    sin_corregir = dividendos
    dividendos, correcciones = mercado.aplicar_correcciones(ticker, dividendos)
    if correcciones:
        print("\nCorrecciones contra el reporte del emisor:")
        for c in correcciones:
            print(f"  {c[:150]}")

    validacion = mercado.validar(
        precios,
        sin_corregir,
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
    from src.estudio import estudio

    return estudio.armar_versionado(ticker)


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


def cmd_universo() -> int:
    from src.estudio import macro, universo

    print("Serie macro del Treasury a 10 años…")
    macro.guardar("ust10", macro.descargar("ust10"))
    print("Lista del universo (Nasdaq + stockanalysis)…")
    lista = universo.construir_lista()
    capital = lista[lista["es_reit_de_capital"]]
    print(f"  {len(lista)} candidatos, {len(capital)} REITs de capital")
    tickers = sorted(capital["ticker"]) + [universo.REFERENCIA]
    print(f"Precios y dividendos de {len(tickers)} tickers (Yahoo)…")
    precios, dividendos, splits, fallas = universo.bajar_historias(tickers)
    destino = universo.guardar(lista, precios, dividendos, splits, fallas)
    print(f"  {precios['ticker'].nunique()} con precios, {len(fallas)} fallas → {destino.relative_to(RAIZ)}")
    for t, m in fallas:
        print(f"    {t}: {m}")
    return 0


def cmd_metodos() -> int:
    from src.estudio import ampliacion, metodos
    from src.export import excel_metodos
    from src.export.pdf_metodos import generar_pdf

    tickers = mercado.con_estudio()
    r = metodos.estudiar({t: _armar(t) for t in tickers}, asignar_entre=ampliacion.asignar_entre(tickers))
    for c in metodos.conclusiones(r):
        print(f"\n{c.titulo}\n  {c.texto}")
    carpeta = RAIZ / "docs" / "estudios"
    for destino in (generar_pdf(r, carpeta / "metodos_de_valuacion.pdf"),
                    excel_metodos.exportar(r, carpeta / "valuacion_trimestral.xlsx")):
        print(f"\n{destino.relative_to(RAIZ)} ({destino.stat().st_size / 1024:,.0f} KB)")
    return 0


def cmd_seleccion() -> int:
    from src.estudio import seleccion
    from src.export.pdf_seleccion import generar_pdf

    r = seleccion.estudiar()
    for c in seleccion.conclusiones(r):
        print(f"\n{c.titulo}\n  {c.texto}")
    destino = generar_pdf(r, RAIZ / "docs" / "estudios" / "universo_de_reits.pdf")
    print(f"\n{destino.relative_to(RAIZ)} ({destino.stat().st_size / 1024:,.0f} KB)")
    return 0


def cmd_etfs(sin_descarga: bool = False) -> int:
    from src.estudio import etfs

    if sin_descarga:
        guardados = etfs.cargar_datos()
        if guardados is None:
            print("No hay datos versionados de los ETFs; corre sin --sin-descarga.")
            return 1
        precios, dividendos = guardados
    else:
        print(f"Precios y dividendos de {', '.join(etfs.ETFS)} (Yahoo)…")
        precios, dividendos = etfs.bajar()
        print(f"  → {etfs.guardar_datos(precios, dividendos).relative_to(RAIZ)}")
    r = etfs.correr(precios, dividendos)
    print(f"Tablas → {etfs.guardar(r).relative_to(RAIZ)}")
    destino = RAIZ / "docs" / "estudios" / "etfs_de_reits.md"
    destino.write_text(etfs.informe(r), encoding="utf-8")
    print(f"Informe → {destino.relative_to(RAIZ)}\n")
    print(etfs.lectura(r))
    return 0


def cmd_satelite(accion: str, vista_previa: bool = False) -> int:
    import pandas as pd

    from src.estudio import satelite as sa

    carpeta = RAIZ / "docs" / "estudios"
    if accion == "explorar":
        r = sa.correr_exploratoria()
        print(f"Tablas → {sa.guardar(r, 'exploratoria').relative_to(RAIZ)}")
        destino = carpeta / "satelite_exploratorio.md"
        destino.write_text(sa.informe_exploratorio(r), encoding="utf-8")
        print(f"Informe → {destino.relative_to(RAIZ)}\n")
        print(sa.lectura_exploratoria(r))
        return 0
    if accion == "elegir":
        from src.investigacion import emisores

        panel, ficha = emisores.cargar()
        if vista_previa:
            q = panel["fecha"].max()
            filas = sa.elegir(panel, ficha, q + pd.DateOffset(months=2) + pd.offsets.MonthEnd(0))
            esc = filas[filas["cartera"] == "satelite"]
            print(f"Vista previa, sin anotar: con el panel al {q:%Y-%m-%d} la regla compraría {len(esc)} REITs "
                  f"({sa.APORTACION / len(esc):,.0f} dólares a cada uno):")
            print("  " + ", ".join(esc["ticker"]))
            return 0
        f = sa.aportacion_que_toca(dt.date.today())
        if f is None:
            print("Este mes no toca aportar. Calendario: " + ", ".join(f"{c:%Y-%m-%d}" for c in sa.calendario()))
            return 1
        filas = sa.elegir(panel, ficha, f)
        destino = sa.anotar(filas)
        esc = filas[filas["cartera"] == "satelite"]
        print(f"Aportación del {f:%Y-%m-%d} anotada en {destino.relative_to(RAIZ)}: {len(esc)} REITs y SCHH.")
        if filas.attrs.get("sin_ticker"):
            print(f"  Sin ticker (no entran): {', '.join(filas.attrs['sin_ticker'])}")
        return 0
    papel = sa.leer_papel()
    retornos = sa.cargar_retornos()
    if not papel.empty:
        retornos, fallas = sa.actualizar_retornos(papel)
        for t, m in fallas:
            print(f"  Yahoo no tiene {t}: {m}")
    r = sa.evaluar(papel, retornos)
    print(f"Tablas → {sa.guardar(r, 'papel').relative_to(RAIZ)}")
    destino = carpeta / "satelite_en_papel.md"
    destino.write_text(sa.informe_papel(r), encoding="utf-8")
    print(f"Informe → {destino.relative_to(RAIZ)}\nEstado: {r.notas['estado']}")
    return 0


def cmd_ampliacion() -> int:
    from src.estudio import ampliacion

    estudios = {t: _armar(t) for t in mercado.con_estudio() if t in (*ampliacion.ORIGINALES, *ampliacion.NUEVOS)}
    print(f"Emisores con estudio: {', '.join(sorted(estudios))}")
    grupos = ampliacion.correr(estudios)
    # Sensibilidad obligatoria del pre-registro: los siete con el FFO de Nareit, sin excepciones de medida.
    from src.estudio import fundamentales

    with fundamentales.con_medida(fundamentales.FFO):
        nareit = {t: _armar(t) for t in ampliacion.NUEVOS if t in estudios}
    if nareit:
        grupos["siete_nareit"] = ampliacion.evaluar_grupo("siete_nareit", nareit)
    destino = ampliacion.guardar(grupos)
    ampliacion.INFORME.write_text(ampliacion.informe(grupos) + "\n", encoding="utf-8")
    print(ampliacion.tabla(grupos)[["grupo", "hipotesis", "se_repite", "cifras"]].to_string(index=False))
    print(f"\nResultados en {destino.relative_to(RAIZ)} y {ampliacion.INFORME.relative_to(RAIZ)}")
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
    sub.add_parser("universo")
    sub.add_parser("seleccion")
    e = sub.add_parser("etfs")
    e.add_argument("--sin-descarga", action="store_true", help="usa los datos ya versionados")
    s_ = sub.add_parser("satelite")
    s_.add_argument("accion", choices=["explorar", "elegir", "evaluar"])
    s_.add_argument("--vista-previa", action="store_true", help="con elegir: muestra lo que compraría, sin anotar")
    sub.add_parser("ampliacion")
    sub.add_parser("ampliacion-pdf")
    args = p.parse_args()
    if args.comando == "ampliacion":
        return cmd_ampliacion()
    if args.comando == "ampliacion-pdf":
        from src.export import pdf_ampliacion

        ruta = pdf_ampliacion.generar()
        print(f"PDF: {ruta.relative_to(RAIZ)} ({ruta.stat().st_size / 1024:,.0f} KB)")
        return 0
    if args.comando == "tbill":
        return cmd_tbill()
    if args.comando == "macro":
        return cmd_macro()
    if args.comando == "reglas-pdf":
        return cmd_reglas_pdf()
    if args.comando == "metodos":
        return cmd_metodos()
    if args.comando == "universo":
        return cmd_universo()
    if args.comando == "seleccion":
        return cmd_seleccion()
    if args.comando == "etfs":
        return cmd_etfs(args.sin_descarga)
    if args.comando == "satelite":
        return cmd_satelite(args.accion, args.vista_previa)
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
