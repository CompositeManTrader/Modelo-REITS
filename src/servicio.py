"""Capa de servicio: arma los paneles que consume la interfaz.

Todo lo que la aplicación muestra pasa por aquí, y todo lo que pasa por aquí
recibe una fecha de corte. Es la última barrera antes de la pantalla: si una
página pudiera consultar el repositorio directamente sin corte, tarde o temprano
alguna lo haría.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import (
    SERIE_CPI,
    SERIE_INPC,
    SERIE_UDIBONO10,
    SERIE_UST10,
    UMBRALES,
    Fuente,
)
from src.datos.repositorio import Repositorio
from src.modelo import senal as mod_senal
from src.modelo.valuacion import InsumosValuacion, panel_valuacion

CONCEPTOS_PANEL = (
    "affo",
    "affo_por_accion",
    "ffo",
    "ffo_normalizado",
    "noi",
    "utilidad_neta",
    "acciones_diluidas",
    "ingreso_rentas",
)


# --------------------------------------------------------------------------------------
# Panel trimestral por emisor
# --------------------------------------------------------------------------------------


@dataclass
class PanelEmisor:
    """Todo lo que la página de valuación necesita de un emisor a una fecha."""

    ticker: str
    sector: str
    asof: dt.date
    trimestral: pd.DataFrame
    precio: float | None
    precio_fecha: dt.date | None
    dividendo_ttm: float | None
    tasa_libre_riesgo: float | None
    metricas: dict[str, float | None] = field(default_factory=dict)
    prima: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))
    percentil: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))
    fuentes: pd.DataFrame = field(default_factory=pd.DataFrame)
    avisos: list[str] = field(default_factory=list)

    @property
    def percentil_actual(self) -> float | None:
        s = self.percentil.dropna()
        return float(s.iloc[-1]) if not s.empty else None

    @property
    def n_observaciones(self) -> int:
        return int(self.prima.dropna().shape[0])

    @property
    def solo_demo(self) -> bool:
        if self.fuentes.empty or "fuente" not in self.fuentes:
            return True
        return bool((self.fuentes["fuente"] == Fuente.DEMO).all())


def construir_panel(
    repo: Repositorio,
    ticker: str,
    *,
    asof: dt.date,
    cap_rate_mercado: float = 0.065,
    yield_adquisiciones: float | None = None,
    balance: dict[str, float] | None = None,
) -> PanelEmisor:
    """Arma el panel trimestral, la prima y su percentil expandible.

    El AFFO por acción se lleva a TTM antes de calcular el yield: un yield sobre
    un trimestre anualizado por cuatro es mucho más ruidoso, y en negocios con
    estacionalidad simplemente está mal.
    """
    avisos: list[str] = []
    sector = repo.sector_de(ticker) or "Diversificado"

    trimestral = repo.panel(ticker, CONCEPTOS_PANEL, asof=asof, periodo_tipo="Q")
    if not trimestral.empty:
        trimestral = trimestral.astype(float, errors="ignore")
        trimestral["affo_por_accion_ttm"] = (
            pd.to_numeric(trimestral["affo_por_accion"], errors="coerce").rolling(4).sum()
        )
        trimestral["affo_ttm"] = pd.to_numeric(trimestral["affo"], errors="coerce").rolling(4).sum()
        trimestral["crecimiento_affo_por_accion_yoy"] = (
            pd.to_numeric(trimestral["affo_por_accion"], errors="coerce").pct_change(4)
        )

    precios = repo.serie_precio(ticker, asof=asof)
    precio = float(precios.iloc[-1]) if not precios.empty else None
    precio_fecha = precios.index[-1].date() if not precios.empty else None
    if precio_fecha is not None and (asof - precio_fecha).days > 5:
        avisos.append(
            f"El precio más reciente disponible es del {precio_fecha}, "
            f"{(asof - precio_fecha).days} días antes del corte. Latencia del dato, no dato en vivo."
        )

    dividendos = repo.dividendos(ticker, asof=asof)
    div_ttm = None
    if not dividendos.empty:
        corte = pd.Timestamp(asof)
        ventana = dividendos[
            (dividendos["fecha_ex"] <= corte)
            & (dividendos["fecha_ex"] > corte - pd.DateOffset(years=1))
        ]
        div_ttm = float(ventana["monto"].sum()) if not ventana.empty else None

    rf = repo.valor_tasa(SERIE_UST10, asof=asof)

    # Serie histórica de AFFO yield sobre precio CRUDO (P2), para la prima y su percentil.
    prima = pd.Series(dtype="float64")
    percentil = pd.Series(dtype="float64")
    if not trimestral.empty and not precios.empty:
        yield_hist = _serie_affo_yield(trimestral, precios)
        tasa_hist = repo.tasa(SERIE_UST10, asof=asof)
        if not yield_hist.empty and not tasa_hist.empty:
            prima = mod_senal.calcular_prima(yield_hist, tasa_hist)
            percentil = mod_senal.percentil_expandible(
                prima, min_observaciones=UMBRALES.valuacion.min_observaciones
            )

    metricas = _metricas(
        trimestral, precio, div_ttm, rf, cap_rate_mercado, yield_adquisiciones, balance, ticker, sector
    )

    fuentes = repo.hechos(asof=asof, tickers=ticker, conceptos=list(CONCEPTOS_PANEL))
    if not fuentes.empty:
        fuentes = fuentes[
            ["concepto", "periodo_tipo", "fecha_dato", "fecha_publicacion", "valor",
             "fuente", "es_primario", "url_filing", "estado"]
        ].sort_values(["fecha_dato", "concepto"], ascending=[False, True])
        if (fuentes["fuente"] == Fuente.DEMO).all():
            avisos.append(
                "Todos los fundamentales de este emisor son de DEMOSTRACIÓN. No decidas con "
                "esta pantalla: corre la ingesta de EDGAR para traer datos de fuente primaria."
            )

    sospechosos = repo.hechos(
        asof=asof, tickers=ticker, conceptos=list(CONCEPTOS_PANEL), incluir_sospechosos=True
    )
    if not sospechosos.empty and "estado" in sospechosos:
        n = int((sospechosos["estado"] != "valido").sum())
        if n:
            avisos.append(
                f"{n} registro(s) de este emisor están marcados SOSPECHOSOS por no cuadrar "
                "su conciliación. No participan en ningún cálculo de esta pantalla."
            )

    return PanelEmisor(
        ticker=ticker,
        sector=sector,
        asof=asof,
        trimestral=trimestral,
        precio=precio,
        precio_fecha=precio_fecha,
        dividendo_ttm=div_ttm,
        tasa_libre_riesgo=rf,
        metricas=metricas,
        prima=prima,
        percentil=percentil,
        fuentes=fuentes,
        avisos=avisos,
    )


def _serie_affo_yield(trimestral: pd.DataFrame, precios: pd.Series) -> pd.Series:
    """AFFO yield TTM por fecha de trimestre, sobre precio de cierre **sin ajustar**."""
    if "affo_por_accion_ttm" not in trimestral:
        return pd.Series(dtype="float64")
    affo = pd.to_numeric(trimestral["affo_por_accion_ttm"], errors="coerce").dropna()
    if affo.empty:
        return pd.Series(dtype="float64")
    px = precios.copy()
    px.index = pd.to_datetime(px.index)
    alineado = px.reindex(px.index.union(pd.to_datetime(affo.index))).ffill().reindex(
        pd.to_datetime(affo.index)
    )
    y = affo.to_numpy() / alineado.to_numpy()
    serie = pd.Series(y, index=pd.to_datetime(affo.index), name="affo_yield")
    return serie.replace([np.inf, -np.inf], np.nan).dropna()


def _metricas(
    trimestral: pd.DataFrame,
    precio: float | None,
    div_ttm: float | None,
    rf: float | None,
    cap_rate: float,
    yield_adq: float | None,
    balance: dict[str, float] | None,
    ticker: str,
    sector: str,
) -> dict[str, float | None]:
    if trimestral.empty or precio is None:
        return {}
    ultima = trimestral.dropna(subset=["affo_por_accion_ttm"]).tail(1)
    if ultima.empty:
        return {}
    fila = ultima.iloc[0]
    balance = balance or {}
    acciones = float(fila.get("acciones_diluidas") or 0) or 1.0

    ins = InsumosValuacion(
        ticker=ticker,
        precio=precio,
        acciones_diluidas=acciones,
        noi_trimestral=_f(fila.get("noi")),
        affo_ttm=_f(fila.get("affo_ttm")),
        affo_por_accion_ttm=_f(fila.get("affo_por_accion_ttm")),
        ffo_ttm=_f(fila.get("ffo")) * 4 if _f(fila.get("ffo")) else None,
        utilidad_neta_ttm=_f(fila.get("utilidad_neta")) * 4 if _f(fila.get("utilidad_neta")) else None,
        dividendo_ttm_por_accion=div_ttm,
        sector=sector,
        **{k: v for k, v in balance.items() if k in InsumosValuacion.__dataclass_fields__},
    )
    metricas = panel_valuacion(
        ins, cap_rate_mercado=cap_rate, yield_adquisiciones=yield_adq, tasa_libre_riesgo=rf
    )
    metricas["crecimiento_affo_por_accion_yoy"] = _f(fila.get("crecimiento_affo_por_accion_yoy"))
    return metricas


def _f(v) -> float | None:
    if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
        return None
    return float(v)


# --------------------------------------------------------------------------------------
# Semáforo
# --------------------------------------------------------------------------------------


def evaluar(panel: PanelEmisor) -> mod_senal.Semaforo:
    """Corre las tres puertas sobre el panel."""
    historial = panel.trimestral.copy()
    if not historial.empty:
        historial = historial.reset_index().rename(columns={"index": "fecha_dato"})
        for col in ("payout_affo", "spread_inversion", "deuda_neta_ebitdare"):
            if col not in historial and panel.metricas.get(col) is not None:
                historial[col] = panel.metricas[col]
    return mod_senal.evaluar_semaforo(
        panel.ticker,
        panel.asof,
        panel.metricas,
        panel.percentil_actual,
        panel.n_observaciones,
        historial,
    )


# --------------------------------------------------------------------------------------
# Comparativa sectorial
# --------------------------------------------------------------------------------------


def tabla_universo(
    repo: Repositorio,
    *,
    asof: dt.date,
    tickers: list[str] | None = None,
    cap_rate_mercado: float = 0.065,
) -> pd.DataFrame:
    """Una fila por emisor con su percentil de prima y el resultado de las tres puertas."""
    emisores = repo.emisores()
    if emisores.empty:
        return pd.DataFrame()
    if tickers:
        emisores = emisores[emisores["ticker"].isin(tickers)]

    filas = []
    for _, e in emisores.iterrows():
        panel = construir_panel(repo, e["ticker"], asof=asof, cap_rate_mercado=cap_rate_mercado)
        sem = evaluar(panel)
        filas.append(
            {
                "ticker": e["ticker"],
                "nombre": e["nombre"],
                "sector": e["sector"],
                "precio": panel.precio,
                "affo_yield": panel.metricas.get("affo_yield"),
                "prima_bps": (panel.prima.dropna().iloc[-1] * 10_000) if not panel.prima.dropna().empty else None,
                "percentil_prima": panel.percentil_actual,
                "n_observaciones": panel.n_observaciones,
                "payout_affo": panel.metricas.get("payout_affo"),
                "p_affo": panel.metricas.get("p_affo"),
                "dividend_yield": panel.metricas.get("dividend_yield"),
                "pasa_calidad": sem.calidad.pasa,
                "luz_calidad": sem.calidad.luz.value,
                "luz_valuacion": sem.valuacion.luz.value,
                "luz_deterioro": sem.deterioro.luz.value,
                "accion": sem.accion.value,
                "solo_demo": panel.solo_demo,
            }
        )
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# Contexto macro
# --------------------------------------------------------------------------------------


@dataclass
class ContextoMacro:
    ust10: float | None
    udibono10: float | None
    inpc: pd.Series
    cpi: pd.Series
    inflacion_mx: float | None
    inflacion_us: float | None
    asof: dt.date


def contexto_macro(repo: Repositorio, *, asof: dt.date) -> ContextoMacro:
    inpc = repo.tasa(SERIE_INPC, asof=asof)
    cpi = repo.tasa(SERIE_CPI, asof=asof)
    return ContextoMacro(
        ust10=repo.valor_tasa(SERIE_UST10, asof=asof),
        udibono10=repo.valor_tasa(SERIE_UDIBONO10, asof=asof),
        inpc=inpc,
        cpi=cpi,
        inflacion_mx=_inflacion_anual(inpc),
        inflacion_us=_inflacion_anual(cpi),
        asof=asof,
    )


def _inflacion_anual(indice: pd.Series) -> float | None:
    s = pd.Series(indice).dropna()
    if len(s) < 13:
        return None
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    previo = s[s.index <= s.index[-1] - pd.DateOffset(years=1)]
    if previo.empty or previo.iloc[-1] <= 0:
        return None
    return float(s.iloc[-1] / previo.iloc[-1] - 1.0)
