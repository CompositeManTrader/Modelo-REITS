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
    MEDIDA_AFFO,
    MEDIDA_CORE_FFO,
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
    # Con qué medida se está valuando: "AFFO" o "Core FFO". No todos los emisores
    # publican AFFO, y presentar las dos bajo la misma etiqueta sería mentir.
    medida_flujo: str = "AFFO"
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
    medida = MEDIDA_AFFO
    if not trimestral.empty:
        trimestral = trimestral.astype(float, errors="ignore")
        medida = _elegir_medida_de_flujo(trimestral)
        if medida == MEDIDA_CORE_FFO:
            avisos.append(
                f"{ticker} no publica AFFO: su conciliación termina en el Core FFO, y eso es "
                "lo que se está usando como medida de flujo. **No son lo mismo**: el AFFO "
                "resta además el CapEx recurrente y la renta en línea recta, así que el Core "
                "FFO queda por arriba del flujo realmente distribuible."
            )
        trimestral["affo_por_accion_ttm"] = _ttm(trimestral, "affo_por_accion")
        trimestral["affo_ttm"] = _ttm(trimestral, "affo")
        # Si al AFFO por acción le falta un trimestre pero el monto sí está
        # completo, el TTM por acción se deduce del monto y del conteo de acciones.
        # Antes, un solo hueco en la serie por acción borraba al emisor de la
        # pantalla aunque toda la información necesaria estuviera en la base.
        acciones = pd.to_numeric(trimestral.get("acciones_diluidas"), errors="coerce")
        if acciones is not None:
            deducido = trimestral["affo_ttm"] / acciones.where(acciones > 0)
            trimestral["affo_por_accion_ttm"] = trimestral["affo_por_accion_ttm"].fillna(deducido)
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
        medida_flujo=medida,
        metricas=metricas,
        prima=prima,
        percentil=percentil,
        fuentes=fuentes,
        avisos=avisos,
    )


def _elegir_medida_de_flujo(trimestral: pd.DataFrame) -> str:
    """Decide con qué medida de flujo se valúa a este emisor, y lo dice.

    No todos los REITs publican AFFO. El self storage y buena parte de salud
    terminan su conciliación en el **Core FFO**, y Public Storage, Extra Space y
    Welltower son de ese grupo: el suplemento no trae la línea.

    Ante eso hay dos salidas malas y una buena. Dejar al emisor en blanco borra a
    un sector entero de la pantalla. Copiar el Core FFO a la casilla del AFFO
    **miente**: el AFFO resta además el CapEx recurrente y la renta en línea recta,
    así que el Core FFO queda por arriba del flujo distribuible. La buena es usar
    el Core FFO y decir en la pantalla que es Core FFO.

    Cuando se sustituye se copia también la serie por acción, para que el TTM y el
    crecimiento se calculen sobre la misma medida y no sobre dos distintas.
    """
    hay_affo = "affo" in trimestral and pd.to_numeric(
        trimestral["affo"], errors="coerce"
    ).notna().any()
    if hay_affo:
        return MEDIDA_AFFO

    hay_core = "ffo_normalizado" in trimestral and pd.to_numeric(
        trimestral["ffo_normalizado"], errors="coerce"
    ).notna().any()
    if not hay_core:
        return MEDIDA_AFFO  # no hay ninguna de las dos: se queda como está, en blanco

    trimestral["affo"] = pd.to_numeric(trimestral["ffo_normalizado"], errors="coerce")
    if "ffo_normalizado_por_accion" in trimestral:
        trimestral["affo_por_accion"] = pd.to_numeric(
            trimestral["ffo_normalizado_por_accion"], errors="coerce"
        )
    return MEDIDA_CORE_FFO


def _ttm(trimestral: pd.DataFrame, concepto: str) -> pd.Series:
    """Suma los últimos doce meses, exigiendo que sean CUATRO TRIMESTRES SEGUIDOS.

    Un ``rolling(4)`` cuenta filas, no calendario. Si al panel le falta un
    trimestre, la ventana abarca cinco trimestres de calendario y devuelve un
    "TTM" que no son doce meses. No hay nada en el resultado que lo delate: la
    suma cuadra, el número se ve razonable, y el yield que sale de ahí está mal.

    Aquí la ventana se valida contra las fechas: solo se emite el TTM cuando los
    cuatro trimestres del periodo existen y son consecutivos.
    """
    if concepto not in trimestral:
        return pd.Series(index=trimestral.index, dtype="float64")
    serie = pd.to_numeric(trimestral[concepto], errors="coerce")
    fechas = pd.PeriodIndex(pd.to_datetime(trimestral.index), freq="Q")
    salida = pd.Series(index=trimestral.index, dtype="float64")
    for i in range(3, len(serie)):
        ventana = serie.iloc[i - 3 : i + 1]
        # Cuatro trimestres seguidos abarcan exactamente tres saltos de trimestre.
        if (fechas[i] - fechas[i - 3]).n != 3 or ventana.isna().any():
            continue
        salida.iloc[i] = float(ventana.sum())
    return salida


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
    # Basta con tener el TTM por acción O el TTM del monto: `panel_valuacion` sabe
    # dividir el segundo entre las acciones. Exigir el primero borraba al emisor
    # entero de la pantalla por un hueco de un trimestre en una sola serie.
    con_ttm = trimestral.dropna(subset=["affo_por_accion_ttm", "affo_ttm"], how="all")
    if con_ttm.empty:
        return {}
    # El renglón que se usa tiene que traer con qué dividir. Sin el flujo POR ACCIÓN
    # hace falta el conteo de acciones, y a Welltower le faltaba justo en el último
    # trimestre: el respaldo de "acciones = 1" convertía un flujo de 4,000 millones
    # en 4,000 millones POR ACCIÓN, y el yield salía en 17 millones por ciento. Un
    # número absurdo es peor que ningún número; se retrocede al último renglón
    # completo en vez de inventar el denominador.
    utilizable = con_ttm[
        con_ttm["affo_por_accion_ttm"].notna()
        | (pd.to_numeric(con_ttm.get("acciones_diluidas"), errors="coerce") > 0)
    ]
    ultima = (utilizable if not utilizable.empty else con_ttm).tail(1)
    fila = ultima.iloc[0]
    balance = balance or {}
    # Un conteo de acciones no positivo no es un dato: es una fórmula equivocada
    # aguas arriba. Dividir entre él le voltea el signo a toda métrica por acción.
    acciones_reportadas = _f(fila.get("acciones_diluidas"))
    if (acciones_reportadas or 0) <= 0 and _f(fila.get("affo_por_accion_ttm")) is None:
        return {}
    acciones = acciones_reportadas if (acciones_reportadas or 0) > 0 else 1.0

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
                # Qué medida de flujo está detrás del yield de ESTE renglón. Sin
                # esta columna, un Core FFO y un AFFO se leerían como lo mismo.
                "medida": panel.medida_flujo,
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
