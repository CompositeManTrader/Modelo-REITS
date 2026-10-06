"""Fase 8: la serie mensual de cada mercado de la prueba final, armada igual que la de EE. UU.

Se escribe antes de abrir los archivos sellados y se prueba con datos sintéticos.

* **La serie principal** de cada mercado es su ETF del índice local si tiene al menos
  ``MESES_MINIMOS_ETF`` meses; si no, la canasta de pesos iguales de los REITs listados
  (con sesgo de supervivencia, declarado en la fase 0).
* **Retorno total** del cierre ajustado por dividendos; **de precio**, del cierre; el de
  **ingreso** es la diferencia. **Yield**: dividendos de los últimos 12 meses entre el
  precio (en la canasta, el promedio de los yields de sus miembros).
* **Efectivo**: la tasa corta local del mes anterior, a un mes; **tasa larga**: la de 10
  años local, conocida al cierre (rezago de un día; son promedios mensuales de la OCDE, así
  que se usa la del mes anterior).
* **Indicadores portables**: los que se pueden calcular con datos locales (yield, yield
  contra la tasa larga local, tendencia, momentum) y los de EE. UU. que se aplican sin
  cambios como indicadores de riesgo global (spread de crédito, NFCI, Treasury, Fed).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.investigacion import datos

MESES_MINIMOS_ETF = 120
PORTABLES_LOCALES = ("yield_reit", "spread_10a", "tendencia_10m", "momentum_12m")
GLOBALES_DE_EEUU = ("spread_credito", "cambio_credito_12m", "nfci", "cambio_treasury_12m", "curva",
                    "fed_cambio_12m", "desempleo_cambio_12m")


def _mensual(precios: pd.DataFrame, dividendos: pd.DataFrame, ticker: str, hoy: pd.Timestamp) -> pd.DataFrame:
    p = precios[precios["ticker"] == ticker][["ticker", "fecha", "cierre", "ajustado"]]
    r = datos.retornos_mensuales(p, hoy=hoy).set_index("fecha")
    d = dividendos[dividendos["ticker"] == ticker]
    div = d.set_index("fecha_ex")["monto"].sort_index() if len(d) else pd.Series(dtype=float)
    acumulado = div.cumsum()

    def hasta(f):
        x = acumulado[acumulado.index <= f]
        return float(x.iloc[-1]) if len(x) else 0.0

    ttm = pd.Series([hasta(f) - hasta(f - pd.DateOffset(months=12)) for f in r.index], index=r.index)
    meses = np.arange(1, len(r) + 1)
    r["yield_dividendo"] = (ttm / r["cierre"]).where(meses >= 12)
    r["retorno_ingreso"] = r["retorno_total"] - r["retorno_precio"]
    return r


def serie_principal(precios: pd.DataFrame, dividendos: pd.DataFrame, etfs: list[str], canasta: list[str], *,
                    hoy: pd.Timestamp | None = None) -> tuple[pd.DataFrame, str]:
    """La serie del mercado y de dónde salió («etf: X» o «canasta de N»)."""
    hoy = hoy or pd.Timestamp.today()
    for t in etfs:
        if t in set(precios["ticker"]):
            m = _mensual(precios, dividendos, t, hoy)
            if m["retorno_total"].notna().sum() >= MESES_MINIMOS_ETF and m["yield_dividendo"].notna().any():
                return m[["retorno_total", "retorno_precio", "retorno_ingreso", "yield_dividendo"]], f"etf: {t}"
    miembros = [_mensual(precios, dividendos, t, hoy) for t in canasta if t in set(precios["ticker"])]
    if not miembros:
        raise ValueError("El mercado no tiene ni ETF suficiente ni miembros en la canasta.")
    panel = {c: pd.concat([m[c] for m in miembros], axis=1) for c in ("retorno_total", "retorno_precio",
                                                                     "yield_dividendo")}
    # Pesos iguales entre los que tienen retorno ese mes.
    x = pd.DataFrame({"retorno_total": panel["retorno_total"].mean(axis=1),
                      "retorno_precio": panel["retorno_precio"].mean(axis=1),
                      "yield_dividendo": panel["yield_dividendo"].mean(axis=1)})
    x["retorno_ingreso"] = x["retorno_total"] - x["retorno_precio"]
    x["miembros"] = panel["retorno_total"].notna().sum(axis=1)
    return x.dropna(subset=["retorno_total"]), f"canasta de {len(miembros)}"


def armar(x: pd.DataFrame, tasas: pd.DataFrame, tasa_corta: str, tasa_larga: str) -> pd.DataFrame:
    """Agrega índices, efectivo y tasa larga local a la serie del mercado."""
    x = x.copy()
    x["indice_total"] = (1 + x["retorno_total"].fillna(0)).cumprod()
    x["indice_precio"] = (1 + x["retorno_precio"].fillna(0)).cumprod()

    def mensual(sid: str) -> pd.Series:
        s = tasas[tasas["serie"] == sid].set_index("fecha")["valor"].sort_index()
        s.index = pd.to_datetime(s.index) + pd.offsets.MonthEnd(0)
        return s

    corta, larga = mensual(tasa_corta), mensual(tasa_larga)
    x["efectivo"] = (corta.shift(1).reindex(x.index) / 100) / 12
    x["tasa_larga"] = larga.shift(1).reindex(x.index) / 100
    return x


def indicadores_portables(x: pd.DataFrame, indicadores_eeuu: pd.DataFrame) -> pd.DataFrame:
    """Los indicadores que se pueden probar fuera de EE. UU., con las mismas definiciones."""
    d = pd.DataFrame(index=x.index)
    d["yield_reit"] = x["yield_dividendo"]
    d["spread_10a"] = x["yield_dividendo"] - x["tasa_larga"]
    d["tendencia_10m"] = x["indice_precio"] / x["indice_precio"].rolling(10).mean() - 1
    d["momentum_12m"] = (1 + x["retorno_total"]).rolling(12).apply(np.prod, raw=True) - 1
    for c in GLOBALES_DE_EEUU:
        if c in indicadores_eeuu:
            d[c] = indicadores_eeuu[c].reindex(x.index)
    return d
