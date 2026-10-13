"""Los ETFs de REITs contra el índice: seguimiento, caídas, TIR y el informe, con datos sintéticos."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.estudio import etfs, reglas
from src.investigacion import exploracion

HOY = pd.Timestamp("2025-06-30")


def _indice(semilla: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    idx = pd.date_range("2004-01-31", "2024-12-31", freq="ME", name="fecha")
    ingreso = np.full(len(idx), 0.003)
    precio = rng.normal(0.004, 0.05, len(idx))
    return pd.DataFrame({"retorno_total": precio + ingreso, "retorno_precio": precio, "retorno_ingreso": ingreso,
                         "yield_dividendo": 0.04, "efectivo": 0.002}, index=idx)


def _etf(ticker: str, x: pd.DataFrame, desde: str, costo: float = 0.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Los cierres de fin de mes y los dividendos de un ETF que replica ``x`` menos un costo mensual."""
    x = x.loc[desde:]
    total = (1 + x["retorno_total"]) * (1 - costo) - 1
    precio = total - x["retorno_ingreso"]
    base = pd.Series([1.0], index=[x.index[0] - pd.offsets.MonthEnd(1)])
    precios = pd.DataFrame({"ticker": ticker,
                            "cierre": 50 * pd.concat([base, (1 + precio).cumprod()]),
                            "ajustado": 50 * pd.concat([base, (1 + total).cumprod()])})
    precios = precios.rename_axis("fecha").reset_index()
    trimestres = pd.date_range(desde, x.index[-1], freq="QE") - pd.Timedelta(days=15)
    dividendos = pd.DataFrame({"ticker": ticker, "fecha_ex": trimestres, "monto": 0.5})
    return precios, dividendos


def _todos(x: pd.DataFrame, costos: dict[str, float] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    costos = costos or {}
    inicios = {"VNQ": "2004-10-31", "USRT": "2007-06-30", "SCHH": "2011-02-28"}
    partes = [_etf(t, x, d, costos.get(t, 0.0)) for t, d in inicios.items()]
    return pd.concat([p for p, _ in partes], ignore_index=True), pd.concat([d for _, d in partes], ignore_index=True)


def test_un_etf_igual_al_indice_no_se_desvia_y_rinde_lo_mismo():
    x = _indice()
    precios, dividendos = _todos(x)
    s = etfs.series(precios, dividendos, hoy=HOY)
    c = etfs.comparar(s, x, dividendos, desde=pd.Timestamp("2011-02-28"))
    e = c[c["serie"].isin(etfs.ETFS)].set_index("serie")
    i = c[~c["serie"].isin(etfs.ETFS)].iloc[0]
    assert set(e.index) == set(etfs.ETFS)
    assert e["diferencia_anual"].abs().max() < 1e-10
    assert e["error_de_seguimiento"].max() < 1e-10
    assert e["correlacion"].min() == pytest.approx(1.0)
    assert e["tir_neta_aportando"].to_numpy() == pytest.approx(np.full(3, i["tir_neta_aportando"]), abs=1e-9)
    assert e["caida_maxima"].to_numpy() == pytest.approx(np.full(3, i["caida_maxima"]))


def test_un_costo_mensual_constante_se_ve_en_la_diferencia_anual():
    x = _indice()
    c = 0.0005
    precios, dividendos = _todos(x, {"VNQ": c})
    s = etfs.series(precios, dividendos, hoy=HOY)
    t = etfs.comparar(s, x, dividendos, desde=pd.Timestamp("2011-02-28"))
    vnq = t[t["serie"] == "VNQ"].iloc[0]
    indice = t[t["serie"] == f"{etfs.INDICE} (meses de VNQ)"].iloc[0]
    # Retorno compuesto: (1 + r)(1 − c) cada mes = el anual del índice por (1 − c)^12.
    esperado = (1 + indice["rendimiento_anual"]) * ((1 - c) ** 12 - 1)
    assert vnq["diferencia_anual"] == pytest.approx(esperado, rel=1e-6)
    assert vnq["tir_neta_aportando"] < indice["tir_neta_aportando"]


def test_la_caida_maxima_su_pico_su_fondo_y_la_recuperacion():
    idx = pd.date_range("2020-01-31", periods=5, freq="ME")
    r = pd.Series([0.10, -0.20, -0.10, 0.05, 0.50], index=idx)
    c = etfs.caida(r)
    assert c["caida_maxima"] == pytest.approx(0.792 / 1.1 - 1)
    assert c["caida_maxima"] == pytest.approx(reglas.caida_maxima(r))
    assert c["pico"] == idx[0] and c["fondo"] == idx[2]
    assert c["meses_para_recuperarse"] == 2
    # Una caída desde el primer mes también cuenta (se parte de 1 antes de la serie).
    assert etfs.caida(pd.Series([-0.10, 0.05], index=idx[:2]))["caida_maxima"] == pytest.approx(-0.10)
    assert etfs.caida(pd.Series([0.10, -0.05], index=idx[:2]))["meses_para_recuperarse"] is None


def test_el_peor_anio_solo_cuenta_anios_completos():
    idx = pd.date_range("2019-07-31", "2021-12-31", freq="ME")
    r = pd.Series(0.01, index=idx)
    r["2019-08-31"] = -0.50                # 2019 está incompleto: no cuenta
    r["2021-03-31"] = -0.10
    valor, anio = etfs.peor_anio(r)
    assert anio == 2021
    assert valor == pytest.approx(1.01 ** 11 * 0.90 - 1)


def test_cuenta_los_pagos_de_cada_anio():
    d = pd.DataFrame({"ticker": "SCHH", "fecha_ex": pd.to_datetime(
        ["2020-03-20", "2020-06-20", "2020-09-20", "2020-12-01", "2020-12-20", "2021-03-20"]), "monto": 0.1})
    assert etfs.pagos_por_anio(d, "SCHH", 2020) == 5
    assert etfs.pagos_por_anio(d, "SCHH", 2021) == 1
    assert etfs.pagos_por_anio(d, "USRT", 2020) == 0


def test_la_corrida_arma_las_ventanas_sin_tocar_la_bitacora(monkeypatch, tmp_path):
    def prohibido(*a, **k):
        raise AssertionError("abrió la validación")

    monkeypatch.setattr(exploracion, "sector", prohibido)
    x = _indice()
    precios, dividendos = _todos(x, {"USRT": 0.0002})
    propio = x.reset_index().assign(indice="equity")
    r = etfs.correr(precios, dividendos, x, nareit_propios=propio, hoy=HOY)
    comun = r["comun"]
    assert (pd.to_datetime(comun["desde"]) == pd.Timestamp("2011-02-28")).all()
    a = r["indice_actual"].set_index("serie")
    for t, desde in etfs.INDICE_ACTUAL_DESDE.items():
        assert pd.Timestamp(a.loc[t, "desde"]) == desde
    p = r["propia"].set_index("serie")
    assert pd.Timestamp(p.loc["VNQ", "desde"]) == pd.Timestamp("2004-10-31")
    assert pd.Timestamp(p.loc["USRT", "desde"]) == pd.Timestamp("2007-06-30")
    assert r["su_indice"].iloc[0]["fondo"] == "USRT" and r["su_indice"].iloc[0]["indice"] == "equity"
    assert (r["anios"]["anio"].min(), r["anios"]["meses"].iloc[0]) == (2011, 11)
    assert (r["comun"].dropna(subset=["pagos_por_anio"])["pagos_por_anio"] == 4).all()

    # Se guarda, se carga y el informe sale igual desde lo guardado.
    texto = etfs.informe(r)
    etfs.guardar(r, raiz=tmp_path)
    cargado = etfs.cargar(raiz=tmp_path)
    assert set(cargado.tablas) == set(r.tablas)
    assert etfs.informe(cargado) == texto
    assert "El más parecido al índice" in texto and "Contra su propio índice" in texto
