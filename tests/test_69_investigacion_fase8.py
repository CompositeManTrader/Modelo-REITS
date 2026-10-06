"""La fase 8 con mercados sintéticos sellados (los reales se abren una sola vez, en el informe)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.investigacion import datos, fase8, muestras


def _mercado_sintetico(raiz, nombre: str, meses: int = 180, caida: bool = True):
    spec = datos.MERCADOS_FINALES[nombre]
    t = (spec["etf"] or spec["canasta"])[0]
    fechas = pd.date_range("2005-01-31", periods=meses, freq="ME")
    r = np.full(meses, 0.008)
    if caida:
        r[100:118] = -0.05                       # una caída larga que la tendencia puede esquivar
    cierre = 100 * np.cumprod(1 + r)
    precios = pd.DataFrame({"ticker": t, "fecha": fechas, "cierre": cierre, "ajustado": cierre * 1.0, "tipo": "etf"})
    dividendos = pd.DataFrame({"ticker": t, "fecha_ex": fechas[2::3], "monto": cierre[2::3] * 0.01})
    tasas = pd.concat([pd.DataFrame({"serie": s, "fecha": pd.date_range("2000-01-01", periods=400, freq="MS"),
                                     "valor": 2.0}) for s in (spec["tasa_corta"], spec["tasa_larga"])])
    for parte, d in (("precios", precios), ("dividendos", dividendos), ("tasas", tasas),
                     ("splits", pd.DataFrame(columns=["ticker", "fecha", "factor"]))):
        muestras.sellar(d, f"{nombre}_{parte}", raiz=raiz)


def test_la_tendencia_esquiva_una_caida_larga_en_un_mercado_sellado(tmp_path):
    raiz, ruta = tmp_path / "sellado", tmp_path / "bitacora.csv"
    _mercado_sintetico(raiz, "japon")
    with pytest.raises(muestras.MuestraCerrada):
        fase8.serie_de_mercado("japon", raiz=raiz, ruta_bitacora=ruta)
    muestras.congelar(fase8.MODELO, fase8.DESCRIPCION, ruta_bitacora=ruta)
    x, origen = fase8.serie_de_mercado("japon", raiz=raiz, ruta_bitacora=ruta)
    assert origen.startswith("etf")
    r = fase8.evaluar_mercado(x, "japon")
    assert r["caida_regla"] > r["caida_aportar_siempre"]          # cae menos
    assert r["reduccion_de_caida"] > 0.3 and r["cuenta"]
    assert np.isfinite([r["mejora"], r["mejora_con_rezago"], r["mejora_doble_costo"]]).all()


def test_la_exposicion_de_tendencia_necesita_10_meses():
    p = pd.Series(np.arange(1.0, 15.0), index=pd.date_range("2000-01-31", periods=14, freq="ME"))
    e = fase8.exposicion_tendencia(p)
    assert e.iloc[:9].isna().all() and (e.iloc[9:] == 1.0).all()
