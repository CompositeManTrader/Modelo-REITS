"""Núcleo y satélite contra SCHH: la exploratoria y la prueba en papel, con datos sintéticos."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.estudio import satelite as sa
from src.investigacion import bitacora, muestras
from tests.test_72_investigacion_fase6 import _panel


def _mensual(desde: str, hasta: str, semilla: int, ingreso: float = 0.003) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    idx = pd.date_range(desde, hasta, freq="ME")
    precio = rng.normal(0.005, 0.04, len(idx))
    return pd.DataFrame({"retorno_total": precio + ingreso, "retorno_ingreso": ingreso}, index=idx)


def _ficha(panel: pd.DataFrame) -> pd.DataFrame:
    ciks = sorted(panel["cik"].unique())
    return pd.DataFrame({"cik": ciks, "nombre": [f"REIT {i}" for i in range(len(ciks))],
                         "tickers": [f"T{i}|T{i}PR" for i in range(len(ciks))]})


def test_de_mensual_a_trimestral():
    m = pd.DataFrame({"retorno_total": [0.01, 0.02, -0.01, 0.03, 0.0], "retorno_ingreso": 0.002},
                     index=pd.date_range("2020-01-31", periods=5, freq="ME"))
    t = sa.trimestral(m)
    assert list(t.index) == [pd.Timestamp("2020-03-31")]          # el segundo trimestre está incompleto
    assert t["retorno"].iloc[0] == pytest.approx(1.01 * 1.02 * 0.99 - 1)
    assert t["dividendo"].iloc[0] == pytest.approx(0.006)
    con_costo = sa.trimestral(m, costo_anual=0.012)
    assert con_costo["retorno"].iloc[0] == pytest.approx(1.009 * 1.019 * 0.989 - 1)


def test_la_exploratoria_registra_cada_satelite_y_no_abre_los_sellados(monkeypatch, tmp_path):
    def prohibido(*a, **k):
        raise AssertionError("abrió un sellado")

    monkeypatch.setattr(muestras, "abrir_sellado", prohibido)
    fechas = pd.date_range("2009-03-31", "2015-12-31", freq="QE")
    panel = _panel(60, fechas=fechas)
    ruta = tmp_path / "bitacora.csv"
    t, anios = sa.explorar(panel, _mensual("2010-01-31", "2016-03-31", 1), _mensual("2010-01-31", "2016-03-31", 2),
                           ruta_bitacora=ruta)
    assert len(t) == len(sa.SATELITES) * len(sa.REFERENCIAS)
    assert bitacora.intentos(sa.FAMILIA, ruta=ruta) == len(t)
    assert (pd.to_datetime(t["hasta"]) == pd.Timestamp("2015-12-31")).all()
    # La cartera 85/15 queda entre el satélite y la referencia.
    bajo = np.minimum(t["tir_satelite"], t["tir_referencia"]) - 1e-9
    alto = np.maximum(t["tir_satelite"], t["tir_referencia"]) + 1e-9
    assert ((t["tir_cartera"] >= bajo) & (t["tir_cartera"] <= alto)).all()
    assert {"exceso_2011_2015"} <= set(t.columns)
    assert set(anios.columns) >= {"anio", "momentum", "SCHH real"}
    sa.explorar(panel, _mensual("2010-01-31", "2016-03-31", 1), _mensual("2010-01-31", "2016-03-31", 2),
                registrar=False, ruta_bitacora=tmp_path / "otra.csv")
    assert not (tmp_path / "otra.csv").exists()


def test_el_calendario_pre_registrado():
    c = sa.calendario()
    assert len(c) == sa.APORTACIONES == 12
    assert c[0] == pd.Timestamp("2026-11-30") and c[-1] == pd.Timestamp("2029-08-31")
    assert {f.month for f in c} == set(sa.MESES_DE_APORTACION)
    assert sa.trimestre_del_panel(pd.Timestamp("2026-11-30")) == pd.Timestamp("2026-09-30")
    assert sa.trimestre_del_panel(pd.Timestamp("2027-02-28")) == pd.Timestamp("2026-12-31")
    assert sa.aportacion_que_toca(pd.Timestamp("2026-11-16")) == pd.Timestamp("2026-11-30")
    assert sa.aportacion_que_toca(pd.Timestamp("2026-10-16")) is None


def test_elegir_escoge_el_tercil_de_momentum_y_anotar_lo_hace_una_vez(tmp_path):
    panel = _panel(45, fechas=pd.date_range("2022-03-31", "2026-09-30", freq="QE"))
    ficha = _ficha(panel)
    f = pd.Timestamp("2026-11-30")
    filas = sa.elegir(panel, ficha, f)
    sat, nuc = filas[filas["cartera"] == "satelite"], filas[filas["cartera"] == "nucleo"]
    assert 13 <= len(sat) <= 16                                   # un tercio de 45
    assert sat["monto"].sum() == pytest.approx(sa.APORTACION)
    assert nuc["ticker"].tolist() == [sa.NUCLEO] and nuc["monto"].iloc[0] == sa.APORTACION
    assert (filas["trimestre_del_panel"] == pd.Timestamp("2026-09-30")).all()
    assert sat["ticker"].str.match(r"^T\d+$").all()               # el primer ticker de la ficha
    assert sat["momentum"].is_monotonic_decreasing

    with pytest.raises(sa.PanelAtrasado):
        sa.elegir(panel[panel["fecha"] <= "2026-06-30"], ficha, f)

    ruta = tmp_path / "papel.csv"
    sa.anotar(filas, hoy=pd.Timestamp("2026-11-16"), ruta=ruta)
    guardado = sa.leer_papel(ruta)
    assert len(guardado) == len(filas) and guardado["commit"].notna().all()
    with pytest.raises(sa.FueraDeCalendario):
        sa.anotar(filas, hoy=pd.Timestamp("2026-11-20"), ruta=ruta)      # ya está
    with pytest.raises(sa.FueraDeCalendario):
        sa.anotar(filas, hoy=pd.Timestamp("2026-12-01"), ruta=tmp_path / "otro.csv")   # ya pasó
    fuera = filas.assign(fecha_aportacion=pd.Timestamp("2026-10-31"))
    with pytest.raises(sa.FueraDeCalendario):
        sa.anotar(fuera, hoy=pd.Timestamp("2026-10-16"), ruta=tmp_path / "otro.csv")


def _papel(fechas, tickers=("AAA", "BBB")) -> pd.DataFrame:
    filas = []
    for f in fechas:
        for t in tickers:
            filas.append({"fecha_aportacion": f, "cartera": "satelite", "ticker": t, "monto": sa.APORTACION / len(tickers)})
        filas.append({"fecha_aportacion": f, "cartera": "nucleo", "ticker": sa.NUCLEO, "monto": sa.APORTACION})
    p = pd.DataFrame(filas)
    p["trimestre_del_panel"] = p["fecha_aportacion"].map(sa.trimestre_del_panel)
    return p.assign(cik="", nombre="", momentum=np.nan)


def _retornos(tickers, desde="2026-12-31", hasta="2027-08-31", semilla=3) -> pd.DataFrame:
    base = _mensual(desde, hasta, semilla)
    return pd.concat([pd.DataFrame({"ticker": t, "fecha": base.index, "retorno_total": base["retorno_total"].to_numpy(),
                                    "retorno_precio": (base["retorno_total"] - base["retorno_ingreso"]).to_numpy()})
                      for t in tickers], ignore_index=True)


def test_en_papel_un_satelite_igual_a_schh_rinde_lo_mismo_y_uno_que_deja_de_cotizar_se_vende():
    cal = sa.calendario()
    papel = _papel(cal[:3])
    r = _retornos(["AAA", "BBB", sa.NUCLEO])
    e = sa.evaluar(papel, r, ultimo_mes=pd.Timestamp("2027-08-31"))
    s = e["resumen"].set_index("cartera")
    assert s.loc["satelite", "tir_neta"] == pytest.approx(s.loc["nucleo", "tir_neta"], abs=1e-9)
    assert e.notas["evaluado_hasta"] == "2027-08-31" and e.notas["estado"].startswith("en curso")
    assert len(e["periodos"]) == 4

    sin_bbb = r[~((r["ticker"] == "BBB") & (r["fecha"] > "2027-03-31"))]
    x = sa.panel_en_papel(sin_bbb, cal[:4])
    bbb = x[x["cik"] == "BBB"].set_index("fecha")
    assert bool(bbb.loc[pd.Timestamp("2027-05-31"), "salida"]) and pd.Timestamp("2027-08-31") not in bbb.index
    e2 = sa.evaluar(papel, sin_bbb, ultimo_mes=pd.Timestamp("2027-08-31"))
    assert np.isfinite(e2["resumen"].set_index("cartera").loc["satelite", "tir_neta"])


def test_sin_aportaciones_no_hay_cuenta():
    e = sa.evaluar(sa.leer_papel(Path("/no/existe.csv")), _retornos([sa.NUCLEO]))
    assert e.notas["estado"] == "sin aportaciones todavía" and e["resumen"].empty
    assert "Estado:" in sa.informe_papel(e)


def test_los_retornos_nuevos_mandan_y_los_viejos_se_quedan():
    viejo = pd.DataFrame({"ticker": ["A", "A", "B"], "fecha": pd.to_datetime(["2027-01-31", "2027-02-28", "2027-01-31"]),
                          "retorno_total": [0.01, 0.02, 0.03], "retorno_precio": [0.0, 0.01, 0.02]})
    nuevo = pd.DataFrame({"ticker": ["A", "A"], "fecha": pd.to_datetime(["2027-02-28", "2027-03-31"]),
                          "retorno_total": [0.05, 0.04], "retorno_precio": [0.04, 0.03]})
    j = sa.combinar_retornos(viejo, nuevo).set_index(["ticker", "fecha"])
    assert j.loc[("A", pd.Timestamp("2027-02-28")), "retorno_total"] == 0.05
    assert ("B", pd.Timestamp("2027-01-31")) in j.index and len(j) == 4
