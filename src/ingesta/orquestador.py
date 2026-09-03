"""Orquestador de ingesta: EDGAR → validación → base.

Ningún dato entra a la base sin pasar la capa de validación. Lo que no cuadra se
guarda igual, pero marcado ``sospechoso``, y las consultas lo excluyen por
omisión. Se guarda en vez de descartarse porque un registro sospechoso es
evidencia: sirve para revisar a mano qué falló el parser.

La ``fecha_publicacion`` de todo lo que entra por aquí es la fecha de
presentación del filing ante la SEC. Nunca la fecha de hoy, nunca la fecha del
periodo contable.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field

import pandas as pd

from src.config import EMISOR_POR_TICKER, UNIVERSO_INICIAL, Estado, Fuente
from src.datos.repositorio import Repositorio
from src.ingesta import xbrl
from src.ingesta.edgar import ClienteEdgar, ErrorEdgar
from src.ingesta.parser_affo import (
    fin_de_trimestre,
    parsear_conciliacion,
    reconstruir_trimestres,
)
from src.validacion.cuadre import cuadrar_conciliacion, elegir_mejor_conciliacion


@dataclass
class ResumenIngesta:
    """Qué entró, qué se rechazó y qué cambió respecto al trimestre anterior."""

    ticker: str
    filings_revisados: int = 0
    periodos_extraidos: int = 0
    hechos_guardados: int = 0
    lineas_guardadas: int = 0
    validos: int = 0
    sospechosos: int = 0
    errores: list[str] = field(default_factory=list)
    novedades: list[str] = field(default_factory=list)

    def como_texto(self) -> str:
        base = (
            f"{self.ticker}: {self.filings_revisados} filing(s) revisados, "
            f"{self.periodos_extraidos} periodo(s) extraídos, "
            f"{self.hechos_guardados} hecho(s) nuevos "
            f"({self.validos} válidos, {self.sospechosos} sospechosos)."
        )
        if self.errores:
            base += f" {len(self.errores)} error(es)."
        return base


def ingestar_fundamentales(
    repo: Repositorio,
    cliente: ClienteEdgar,
    ticker: str,
    cik: str,
    *,
    desde: dt.date | None = None,
    max_filings: int = 8,
    sector: str | None = None,
) -> ResumenIngesta:
    """Descarga y valida las conciliaciones de AFFO de los 8-K de resultados."""
    resumen = ResumenIngesta(ticker=ticker)
    sector = sector or (EMISOR_POR_TICKER.get(ticker).sector if ticker in EMISOR_POR_TICKER else None)

    try:
        filings = cliente.listar_filings(cik, ticker, formularios=("8-K",), desde=desde)
    except ErrorEdgar as exc:
        resumen.errores.append(f"No se pudo listar filings: {exc}")
        return resumen

    revisados = 0
    for filing in filings:
        if revisados >= max_filings:
            break
        try:
            documentos = cliente.documentos_resultados(filing)
        except ErrorEdgar as exc:
            resumen.errores.append(f"{filing.accession}: {exc}")
            continue
        if not documentos:
            continue
        revisados += 1
        resumen.filings_revisados += 1

        extracciones = []
        for url, html in documentos:
            try:
                extracciones.extend(
                    parsear_conciliacion(html, ticker, filing.fecha_presentacion, url)
                )
            except Exception as exc:  # noqa: BLE001 - un documento malformado no tumba la corrida
                resumen.errores.append(f"{filing.accession} ({url.split('/')[-1]}): {exc}")

        for extraccion in elegir_mejor_conciliacion(extracciones):
            resumen.periodos_extraidos += 1
            _guardar_extraccion(repo, extraccion, resumen, sector)

    return resumen


def _guardar_extraccion(repo: Repositorio, extraccion, resumen: ResumenIngesta, sector: str | None) -> None:
    """Valida una extracción y la persiste con su estado."""
    veredicto = cuadrar_conciliacion(extraccion.lineas, extraccion.orden)
    estado = Estado.VALIDO if veredicto.cuadra else Estado.SOSPECHOSO
    nota = veredicto.como_texto()

    if veredicto.cuadra:
        resumen.validos += 1
    else:
        resumen.sospechosos += 1
        resumen.errores.append(
            f"{extraccion.ticker} {extraccion.periodo.etiqueta}: {veredicto.motivo[:180]}"
        )

    filas_hechos = []
    for clave in ("noi", "ffo", "ffo_normalizado", "affo",
                  "affo_por_accion", "ffo_por_accion", "utilidad_neta",
                  "utilidad_neta_por_accion", "ingreso_rentas"):
        if clave not in extraccion.lineas:
            continue
        filas_hechos.append(
            {
                "ticker": extraccion.ticker,
                "concepto": clave,
                "periodo_tipo": extraccion.periodo.tipo,
                "fecha_dato": extraccion.periodo.fin,
                "fecha_publicacion": extraccion.fecha_publicacion,
                "valor": float(extraccion.lineas[clave]),
                "unidad": "USD",
                "fuente": Fuente.SEC_8K,
                "es_primario": True,
                "url_filing": extraccion.url_filing,
                "estado": estado,
                "nota_validacion": nota[:500],
            }
        )
    resumen.hechos_guardados += repo.guardar_hechos(filas_hechos)
    resumen.lineas_guardadas += repo.guardar_conciliacion(extraccion.filas_conciliacion())
    _ = sector


def ingestar_xbrl(
    repo: Repositorio,
    cliente: ClienteEdgar,
    ticker: str,
    cik: str,
    *,
    desde: dt.date | None = None,
) -> ResumenIngesta:
    """Descarga las partidas GAAP de companyfacts y las persiste con su ``filed``."""
    resumen = ResumenIngesta(ticker=ticker)
    try:
        df = xbrl.ingestar_emisor(cliente, ticker, cik, desde=desde)
    except ErrorEdgar as exc:
        resumen.errores.append(f"companyfacts: {exc}")
        return resumen
    if df.empty:
        return resumen
    filas = df.to_dict("records")
    for f in filas:
        f["estado"] = Estado.VALIDO
    resumen.hechos_guardados = repo.guardar_hechos(filas)
    resumen.validos = resumen.hechos_guardados
    return resumen


# --------------------------------------------------------------------------------------
# Reconstrucción de trimestres desde acumulados
# --------------------------------------------------------------------------------------


def reconstruir_desde_acumulados(
    repo: Repositorio, ticker: str, concepto: str, *, asof: dt.date
) -> int:
    """Deriva Q1 y Q3 de los acumulados ya guardados y los persiste como reconstruidos.

    ``Q1 = H1 − Q2`` y ``Q3 = FY − H1 − Q4``. La fecha de publicación del
    trimestre derivado es la **más tardía** de sus componentes: antes de esa fecha
    el número no era deducible ni con lápiz.
    """
    hechos = repo.hechos(asof=asof, tickers=ticker, conceptos=concepto)
    if hechos.empty:
        return 0

    hechos["anio"] = pd.to_datetime(hechos["fecha_dato"]).dt.year
    guardados = 0
    for anio, grupo in hechos.groupby("anio"):
        observaciones: dict[str, tuple[float, dt.date]] = {}
        for _, r in grupo.iterrows():
            fecha = pd.Timestamp(r["fecha_dato"]).date()
            pub = pd.Timestamp(r["fecha_publicacion"]).date()
            if r["periodo_tipo"] == "Q":
                observaciones[f"Q{pd.Timestamp(fecha).quarter}"] = (float(r["valor"]), pub)
            elif r["periodo_tipo"] in ("H1", "FY"):
                observaciones[r["periodo_tipo"]] = (float(r["valor"]), pub)

        derivados = reconstruir_trimestres(observaciones)
        for etiqueta, (valor, publicacion, formula) in derivados.items():
            guardados += repo.guardar_hechos(
                [
                    {
                        "ticker": ticker,
                        "concepto": concepto,
                        "periodo_tipo": "Q",
                        "fecha_dato": fin_de_trimestre(int(anio), int(etiqueta[1])),
                        "fecha_publicacion": publicacion,
                        "valor": valor,
                        "unidad": "USD",
                        "fuente": Fuente.RECONSTRUIDO,
                        "es_primario": False,
                        "estado": Estado.VALIDO,
                        "nota_validacion": formula,
                    }
                ]
            )
    return guardados


# --------------------------------------------------------------------------------------
# Detección de novedades
# --------------------------------------------------------------------------------------


def detectar_novedades(repo: Repositorio, ticker: str, *, asof: dt.date) -> list[str]:
    """Compara el último trimestre contra el anterior y describe qué cambió.

    Es lo que la aplicación muestra cuando entra un dato nuevo: no "hay datos
    nuevos", sino qué se movió y en qué dirección.
    """
    mensajes: list[str] = []
    for concepto, etiqueta, formato in (
        ("affo_por_accion", "AFFO por acción", "{:.3f}"),
        ("affo", "AFFO", "{:,.0f}"),
        ("ffo_normalizado", "FFO normalizado", "{:,.0f}"),
    ):
        serie = repo.serie(ticker, concepto, asof=asof, periodo_tipo="Q")
        if len(serie) < 2:
            continue
        actual, previo = float(serie.iloc[-1]), float(serie.iloc[-2])
        if previo == 0:
            continue
        cambio = actual / previo - 1.0
        direccion = "subió" if cambio > 0 else "bajó"
        mensajes.append(
            f"{etiqueta} {direccion} {abs(cambio):.1%} contra el trimestre anterior: "
            f"{formato.format(previo)} → {formato.format(actual)} "
            f"({pd.Timestamp(serie.index[-1]).date()})."
        )

        # Comparación año contra año, que es la que importa en un negocio estacional.
        if len(serie) >= 5:
            hace_un_anio = float(serie.iloc[-5])
            if hace_un_anio:
                yoy = actual / hace_un_anio - 1.0
                mensajes.append(
                    f"{etiqueta} contra el mismo trimestre del año pasado: {yoy:+.1%}."
                )
    return mensajes


# --------------------------------------------------------------------------------------
# Corrida completa
# --------------------------------------------------------------------------------------


def correr_ingesta(
    repo: Repositorio,
    *,
    tickers: Sequence[str] | None = None,
    desde: dt.date | None = None,
    max_filings: int = 8,
    con_xbrl: bool = True,
    cliente: ClienteEdgar | None = None,
) -> list[ResumenIngesta]:
    """Corre la ingesta completa del universo. Es lo que llama la GitHub Action."""
    cliente = cliente or ClienteEdgar()
    emisores = [e for e in UNIVERSO_INICIAL if tickers is None or e.ticker in set(tickers)]
    repo.registrar_emisores(emisores)

    resumenes: list[ResumenIngesta] = []
    for e in emisores:
        resumen = ingestar_fundamentales(
            repo, cliente, e.ticker, e.cik, desde=desde, max_filings=max_filings, sector=e.sector
        )
        if con_xbrl:
            r_xbrl = ingestar_xbrl(repo, cliente, e.ticker, e.cik, desde=desde)
            resumen.hechos_guardados += r_xbrl.hechos_guardados
            resumen.errores.extend(r_xbrl.errores)

        hoy = dt.date.today()
        for concepto in ("affo", "ffo_normalizado", "utilidad_neta"):
            reconstruir_desde_acumulados(repo, e.ticker, concepto, asof=hoy)

        resumen.novedades = detectar_novedades(repo, e.ticker, asof=hoy)
        for nota in resumen.novedades:
            repo.registrar_bitacora("dato_nuevo", nota, ticker=e.ticker)
        repo.registrar_bitacora("ingesta", resumen.como_texto(), ticker=e.ticker)
        resumenes.append(resumen)

    return resumenes
