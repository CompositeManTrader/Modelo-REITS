#!/usr/bin/env python3
"""Descarga, arma y verifica los estados financieros completos de cada emisora.

    python scripts/estados.py                    # solo lo que tenga reporte nuevo
    python scripts/estados.py --forzar           # baja todo, haya novedad o no
    python scripts/estados.py --tickers O,NNN
    python scripts/estados.py --revisar          # no toca la red: verifica lo guardado
    python scripts/estados.py --pendientes       # qué etiquetas faltan por mapear

El proceso completo, en orden:

1. **Decidir.** Se consulta la lista de filings de la emisora y se compara el
   último 10-Q/10-K contra el ``accession`` que guarda el manifiesto. Si es el
   mismo, no se baja nada. Correr esto diez veces el mismo día baja los datos una
   vez, y esa es la propiedad que hace que se pueda correr en automático.

2. **Bajar.** ``companyfacts`` completo, sin filtrar por concepto: todas las
   etiquetas, todas las unidades y **todas las versiones publicadas** de cada
   periodo, con su ``filed``. Es el crudo, y se guarda tal cual.

3. **Armar.** Los tres estados —resultados, balance y flujo— trimestrales y
   anuales, mapeando las etiquetas GAAP a las líneas canónicas con la ficha de la
   emisora por delante de las compartidas.

4. **Verificar.** El balance cuadra, los cuatro trimestres suman el año, nadie
   publicó un periodo antes de que terminara, ningún activo total es negativo.

5. **Escribir.** CSV determinista en ``data/emisoras/<TICKER>/``, con su huella en
   el manifiesto. Si el contenido no cambió, el archivo no se toca.

Solo el paso 2 usa red, y solo si el paso 1 lo autorizó.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.config import EMISOR_POR_TICKER, UNIVERSO_INICIAL  # noqa: E402
from src.datos.almacen import (  # noqa: E402
    ARCHIVO_COBERTURA,
    ARCHIVO_CRUDOS,
    DIR_EMISORAS,
    Manifiesto,
    decidir_descarga,
    escribir_cobertura,
    escribir_crudos,
    escribir_estado,
    leer_crudos,
    nombre_estado,
    verificar_huellas,
)
from src.ingesta.edgar import ClienteEdgar, ErrorEdgar  # noqa: E402
from src.ingesta.estados import (  # noqa: E402
    BALANCE,
    ESTADOS,
    LINEAS,
    NOMBRE_ESTADO,
    armar_estado,
    cobertura_de_lineas,
    conceptos_no_mapeados,
    derivar_cuarto_trimestre,
    elegir_tags,
    hechos_crudos,
    periodos_disponibles,
)
from src.validacion.estados import ERROR, verificar_todo  # noqa: E402

# Qué combinaciones se guardan. El balance es un saldo: no lleva tipo de periodo.
COMBINACIONES: tuple[tuple[str, str | None], ...] = tuple(
    (estado, None) if estado == BALANCE else (estado, tipo)
    for estado in ESTADOS
    for tipo in (("Q", "FY") if estado != BALANCE else (None,))
)


def armar_y_verificar(ticker: str, crudos: pd.DataFrame, *, asof: dt.date):
    """Arma los cinco cortes y corre las comprobaciones. Sin red.

    La elección de etiqueta se hace UNA vez para toda la emisora y se reparte a
    los cinco cortes: si el trimestral y el anual eligieran por su cuenta, podrían
    quedarse con etiquetas distintas y dejarían de ser comparables entre sí.

    El Q4 se deriva antes de armar nada, porque en Estados Unidos no existe un
    10-Q del cuarto trimestre y sin él la serie trimestral tiene un hueco anual.
    """
    tags = elegir_tags(crudos, ticker)
    completos = derivar_cuarto_trimestre(crudos, tags)
    estados = {}
    for estado, tipo in COMBINACIONES:
        estados[(estado, tipo)] = armar_estado(
            completos, ticker, estado, asof=asof, periodo_tipo=tipo or "Q", tags=tags
        )
    incidencias = verificar_todo(ticker, completos, estados)
    return estados, incidencias


def procesar(
    cliente: ClienteEdgar,
    manifiesto: Manifiesto,
    ticker: str,
    cik: str,
    *,
    desde: dt.date | None,
    forzar: bool,
    asof: dt.date,
) -> tuple[str, list]:
    """Un ciclo completo para una emisora. Devuelve (mensaje, incidencias)."""
    registro = manifiesto.registro(ticker)
    registro.cik = cik
    registro.nombre = EMISOR_POR_TICKER[ticker].nombre if ticker in EMISOR_POR_TICKER else ticker

    try:
        filings = cliente.listar_filings(cik, ticker, formularios=("10-Q", "10-K"), desde=desde)
    except ErrorEdgar as exc:
        return f"{ticker}: no se pudo listar filings ({exc})", []

    veredicto = decidir_descarga(registro, filings, forzar=forzar)
    if not veredicto.descargar:
        return f"{ticker}: {veredicto.motivo}", []

    try:
        datos = cliente.companyfacts(cik)
    except ErrorEdgar as exc:
        return f"{ticker}: falló companyfacts ({exc})", []

    crudos = hechos_crudos(datos, ticker, desde=desde)
    if crudos.empty:
        return f"{ticker}: companyfacts no devolvió hechos en la ventana.", []

    estados, incidencias = armar_y_verificar(ticker, crudos, asof=asof)
    cobertura = cobertura_de_lineas(crudos, ticker)

    huellas = {ARCHIVO_CRUDOS: escribir_crudos(ticker, crudos)}
    for (estado, tipo), tabla in estados.items():
        if tabla.empty:
            continue
        huellas[nombre_estado(estado, tipo)] = escribir_estado(
            ticker, estado, tabla, periodo_tipo=tipo
        )
    huellas[ARCHIVO_COBERTURA] = escribir_cobertura(ticker, cobertura)

    registro.ultimo_accession = veredicto.accession
    registro.ultimo_formulario = veredicto.formulario
    registro.ultima_fecha_presentacion = str(veredicto.fecha_presentacion or "")
    registro.descargado_en = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    registro.n_hechos_crudos = int(len(crudos))
    registro.periodos_trimestrales = len(periodos_disponibles(crudos, periodo_tipo="Q"))
    registro.periodos_anuales = len(periodos_disponibles(crudos, periodo_tipo="FY"))
    registro.lineas_encontradas = int(cobertura["encontrada"].sum())
    registro.lineas_totales = int(len(cobertura))
    registro.huellas = huellas
    registro.incidencias = [i.como_texto() for i in incidencias]

    errores = sum(1 for i in incidencias if i.severidad == ERROR)
    mensaje = (
        f"{ticker}: {veredicto.motivo} → {len(crudos):,} hechos, "
        f"{registro.periodos_trimestrales} trimestres y {registro.periodos_anuales} años, "
        f"{registro.lineas_encontradas}/{registro.lineas_totales} líneas mapeadas"
    )
    if incidencias:
        mensaje += f", {errores} error(es) y {len(incidencias) - errores} aviso(s)"
    return mensaje, incidencias


# --------------------------------------------------------------------------------------
# Modos que no tocan la red
# --------------------------------------------------------------------------------------


def revisar(manifiesto: Manifiesto, tickers: list[str], *, asof: dt.date) -> int:
    """Verifica lo que ya está guardado, sin bajar nada.

    Sirve para dos cosas: correrlo en integración continua sin depender de la SEC,
    y comprobar que nadie editó los archivos a mano después de la descarga.
    """
    fallos = 0
    for ticker in tickers:
        crudos = leer_crudos(ticker)
        if crudos.empty:
            print(f"  {ticker:5s} sin datos guardados")
            continue
        _estados, incidencias = armar_y_verificar(ticker, crudos, asof=asof)
        desajustes = verificar_huellas(manifiesto.registro(ticker))
        errores = [i for i in incidencias if i.severidad == ERROR]
        marca = "FALLA" if (errores or desajustes) else "OK  "
        print(f"  {marca} {ticker:5s} {len(crudos):>7,} hechos · {len(incidencias)} incidencia(s)")
        for d in desajustes:
            print(f"        huella: {d}")
            fallos += 1
        for i in incidencias[:6]:
            print(f"        {i.como_texto()}")
        fallos += len(errores)
    return fallos


def pendientes(tickers: list[str], *, limite: int = 12) -> None:
    """Etiquetas frecuentes que el catálogo todavía no mapea, por emisora.

    Es la lista de trabajo para ampliar la ficha: una etiqueta que la emisora
    publica en veinte periodos y que no cae en ningún renglón probablemente sea un
    renglón que falta, no ruido.
    """
    for ticker in tickers:
        crudos = leer_crudos(ticker)
        if crudos.empty:
            continue
        faltan = conceptos_no_mapeados(crudos, ticker)
        if faltan.empty:
            print(f"\n{ticker}: sin etiquetas frecuentes fuera del catálogo.")
            continue
        print(f"\n{ticker}: {len(faltan)} etiqueta(s) frecuentes fuera del catálogo")
        for r in faltan.head(limite).itertuples():
            print(f"   {r.n_periodos:>3} periodos · {r.unidad:12s} {r.tag}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tickers", help="Lista separada por comas. Por omisión, el universo.")
    p.add_argument("--desde", default="2019-01-01", help="Fecha mínima de cierre (AAAA-MM-DD).")
    p.add_argument("--forzar", action="store_true", help="Baja aunque no haya reporte nuevo.")
    p.add_argument("--revisar", action="store_true", help="Solo verifica lo guardado, sin red.")
    p.add_argument("--pendientes", action="store_true", help="Etiquetas por mapear, sin red.")
    args = p.parse_args()

    tickers = (
        [t.strip().upper() for t in args.tickers.split(",")]
        if args.tickers
        else [e.ticker for e in UNIVERSO_INICIAL]
    )
    desde = dt.date.fromisoformat(args.desde) if args.desde else None
    asof = dt.date.today()
    manifiesto = Manifiesto.cargar()

    if args.pendientes:
        pendientes(tickers)
        return 0

    if args.revisar:
        print(f"Revisión de {len(tickers)} emisora(s), sin red.\n")
        fallos = revisar(manifiesto, tickers, asof=asof)
        print(f"\n{'Todo cuadra.' if not fallos else f'{fallos} problema(s).'}")
        return 1 if fallos else 0

    print(f"Estados financieros: {len(tickers)} emisora(s), cierres desde {desde}.\n")
    total_errores = 0
    for ticker in tickers:
        cik = EMISOR_POR_TICKER[ticker].cik if ticker in EMISOR_POR_TICKER else None
        if not cik:
            print(f"  {ticker}: no está en el universo, sin CIK.")
            continue
        mensaje, incidencias = procesar(
            ClienteEdgar(), manifiesto, ticker, cik,
            desde=desde, forzar=args.forzar, asof=asof,
        )
        print(f"  {mensaje}")
        for i in incidencias:
            if i.severidad == ERROR:
                print(f"      {i.como_texto()}")
                total_errores += 1

    manifiesto.guardar()
    print(f"\nManifiesto actualizado. Archivos en {DIR_EMISORAS.relative_to(Path.cwd())}/")
    print(f"Catálogo: {len(LINEAS)} líneas en {len(ESTADOS)} estados "
          f"({', '.join(NOMBRE_ESTADO[e].lower() for e in ESTADOS)}).")
    if total_errores:
        print(f"\n{total_errores} error(es) de verificación. Revísalos antes de usar los datos.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
