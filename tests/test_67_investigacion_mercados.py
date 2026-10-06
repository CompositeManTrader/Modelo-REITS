"""La serie de cada mercado de la prueba final, con datos sintéticos (los sellados no se abren)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.investigacion import mercados


def _ticker(t: str, meses: int, crecimiento: float, dividendo: float, inicio="2005-01-31"):
    fechas = pd.date_range(inicio, periods=meses, freq="ME")
    cierre = 100 * (1 + crecimiento) ** np.arange(meses)
    # Ajustado: reinvierte un dividendo trimestral del precio; el cierre no.
    factor = np.cumprod([1 + (dividendo / 4 if (k % 3 == 2) else 0) for k in range(meses)])
    precios = pd.DataFrame({"ticker": t, "fecha": fechas, "cierre": cierre, "ajustado": cierre * factor})
    divs = pd.DataFrame({"ticker": t, "fecha_ex": [f for k, f in enumerate(fechas) if k % 3 == 2],
                         "monto": [cierre[k] * dividendo / 4 for k in range(meses) if k % 3 == 2]})
    return precios, divs


def test_el_etf_largo_es_la_serie_principal():
    p1, d1 = _ticker("ETF", 150, 0.005, 0.06)
    p2, d2 = _ticker("A", 150, 0.01, 0.04)
    x, origen = mercados.serie_principal(pd.concat([p1, p2]), pd.concat([d1, d2]), ["ETF"], ["A"],
                                         hoy=pd.Timestamp("2030-01-01"))
    assert origen == "etf: ETF"
    assert x["retorno_precio"].dropna().to_numpy() == pytest.approx(0.005)
    assert x["yield_dividendo"].dropna().between(0.05, 0.065).all()


def test_sin_etf_suficiente_se_usa_la_canasta_de_pesos_iguales():
    p1, d1 = _ticker("ETF", 60, 0.0, 0.05, inicio="2015-01-31")
    pa, da = _ticker("A", 150, 0.01, 0.04)
    pb, db = _ticker("B", 150, 0.02, 0.04)
    x, origen = mercados.serie_principal(pd.concat([p1, pa, pb]), pd.concat([d1, da, db]), ["ETF"], ["A", "B"],
                                         hoy=pd.Timestamp("2030-01-01"))
    assert origen == "canasta de 2"
    assert x["retorno_precio"].iloc[5] == pytest.approx(0.015)
    assert (x["miembros"] == 2).all()


def test_el_efectivo_y_la_tasa_larga_son_del_mes_anterior():
    p, d = _ticker("ETF", 130, 0.0, 0.05)
    x, _ = mercados.serie_principal(p, d, ["ETF"], [], hoy=pd.Timestamp("2030-01-01"))
    fechas = pd.date_range("2004-01-01", periods=150, freq="MS")
    tasas = pd.concat([pd.DataFrame({"serie": "CORTA", "fecha": fechas, "valor": np.arange(150) * 0.1}),
                       pd.DataFrame({"serie": "LARGA", "fecha": fechas, "valor": 4.0})])
    m = mercados.armar(x, tasas, "CORTA", "LARGA")
    feb = m.loc["2005-02-28"]
    # La tasa de enero de 2005 es la observación 12 (0.1 × 12 = 1.2% anual).
    assert feb["efectivo"] == pytest.approx(0.012 / 12)
    assert feb["tasa_larga"] == pytest.approx(0.04)
    ind = mercados.indicadores_portables(m, pd.DataFrame({"nfci": 0.5}, index=m.index))
    assert set(mercados.PORTABLES_LOCALES) <= set(ind.columns) and "nfci" in ind
    assert (ind["spread_10a"] - (m["yield_dividendo"] - 0.04)).abs().max() < 1e-12
