"""La prueba de los extremos de valuación (exploratoria), con datos sintéticos."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.investigacion import bitacora, muestras
from src.investigacion import extremos as ex
from tests.test_72_investigacion_fase6 import _panel


def test_los_cortes_incluyen_la_orilla_de_los_extremos():
    p = pd.Series([0.0, 0.05, 0.06, 0.10, 0.5, 0.90, 0.95, 1.0])
    assert ex.en_corte(p, "caro 5%").tolist() == [True, True, False, False, False, False, False, False]
    assert ex.en_corte(p, "caro 10%").tolist() == [True, True, True, True, False, False, False, False]
    assert ex.en_corte(p, "centro").tolist() == [False, False, False, False, True, False, False, False]
    assert ex.en_corte(p, "barato 10%").tolist() == [False] * 5 + [True, True, True]
    assert ex.en_corte(p, "barato 5%").tolist() == [False] * 6 + [True, True]


def test_los_episodios_juntan_rachas_cercanas():
    m = np.zeros(60, dtype=bool)
    m[[3, 4, 5]] = True            # una racha
    m[[10, 11]] = True             # a 5 meses: la misma
    m[[40]] = True                 # a 29 meses: otra
    assert ex.episodios(m, 12) == 2
    assert ex.episodios(m, 3) == 3
    assert ex.episodios(np.zeros(5, dtype=bool)) == 0


def test_la_diferencia_hac_encuentra_un_corrimiento():
    rng = np.random.default_rng(3)
    d = pd.Series(rng.random(400) < 0.1)
    y = pd.Series(rng.normal(0, 0.01, 400)) + 0.02 * d
    dif, t = ex.diferencia_hac(y, d, rezago=4)
    assert dif == pytest.approx(0.02, abs=0.005)
    assert t > 5
    assert np.isnan(ex.diferencia_hac(y, pd.Series(False, index=y.index), 4)[0])


def _sector_sintetico(n: int = 400, semilla: int = 5):
    """Una señal de valuación que, cuando está en su extremo caro, anuncia un año malo."""
    rng = np.random.default_rng(semilla)
    idx = pd.date_range("1975-01-31", periods=n, freq="ME")
    senal = pd.Series(rng.normal(size=n), index=idx).rolling(6, min_periods=1).mean()
    caro = (senal < senal.quantile(0.10)).astype(float)
    malo = caro.rolling(12, min_periods=1).max().shift(1).fillna(0)       # los 12 meses siguientes
    precio = 0.006 - 0.03 * malo + rng.normal(0, 0.02, n)
    x = pd.DataFrame({"retorno_precio": precio, "retorno_ingreso": 0.004, "efectivo": 0.003}, index=idx)
    x["retorno_total"] = x["retorno_precio"] + x["retorno_ingreso"]
    ind = pd.DataFrame(dict.fromkeys(("yield_reit", "spread_10a", "spread_real", "spread_baa"), senal), index=idx)
    return x, ind


def test_el_sector_ve_un_extremo_que_anuncia_un_mal_anio():
    x, ind = _sector_sintetico()
    s = ex.tabla_sector(x, ind, muestra="desarrollo")
    assert len(s) == 4 * len(ex.HORIZONTES_SECTOR) * len(ex.CORTES)
    f = s[(s["corte"] == "caro 10%") & (s["horizonte_meses"] == 12)].iloc[0]
    assert f["diferencia_contra_el_resto"] < 0 and f["t"] < -2
    assert 0 < f["frecuencia"] < 0.5 and f["episodios"] >= 1


def test_las_reglas_del_extremo_van_a_la_bitacora_con_su_familia(tmp_path):
    x, ind = _sector_sintetico()
    ruta = tmp_path / "bitacora.csv"
    r = ex.reglas_sector(x, ind, muestra="desarrollo", ruta_bitacora=ruta)
    assert len(r) == 4 * len(ex.UMBRALES_DE_SALIDA) * len(ex.PERFILES_REGLAS)
    b = bitacora.leer(ruta)
    assert set(b["familia"]) == {ex.FAMILIA} and len(b) == len(r)
    assert bitacora.intentos(ex.FAMILIA, ruta=ruta) == len(r)
    ex.reglas_sector(x, ind, muestra="desarrollo", ruta_bitacora=tmp_path / "otra.csv", registrar=False)
    assert not (tmp_path / "otra.csv").exists()


def test_el_corte_transversal_no_abre_los_sellados(tmp_path, monkeypatch):
    def prohibido(*a, **k):
        raise AssertionError("abrió un sellado")

    monkeypatch.setattr(muestras, "abrir_sellado", prohibido)
    fechas = pd.date_range("2010-03-31", periods=28, freq="QE")
    t = ex.tabla_transversal(_panel(60, fechas=fechas), muestra="desarrollo", ruta_bitacora=tmp_path / "b.csv")
    assert set(t["corte"]) == {"barato 10%", "caro 10%"}
    assert len(t) == 2 * len(ex.SENALES_TRANSVERSAL)
    assert t.loc[t["corte"] == "caro 10%", "mejora_tir"].isna().all()
    assert t.loc[t["corte"] == "barato 10%", "escogidos_promedio"].between(4, 8).all()


def test_una_pista_pide_lo_mismo_en_las_dos_muestras():
    s = pd.DataFrame({"senal": "a", "horizonte_meses": 60, "corte": "caro 10%", "muestra": ["desarrollo", "validacion"],
                      "diferencia_contra_el_resto": [-0.02, -0.03], "t": [-2.5, -2.1]})
    p = ex.pistas(s, pd.DataFrame(), pd.DataFrame())
    assert p["pista"].tolist() == [True]
    s.loc[1, "t"] = -1.5
    assert ex.pistas(s, pd.DataFrame(), pd.DataFrame())["pista"].tolist() == [False]
    s.loc[1, ["t", "diferencia_contra_el_resto"]] = [2.5, 0.02]
    assert ex.pistas(s, pd.DataFrame(), pd.DataFrame())["pista"].tolist() == [False]
    r = pd.DataFrame({"senal": "a", "regla": "fuera en el 10% más caro", "perfil": "sic",
                      "muestra": ["desarrollo", "validacion"], "mejora_rebalanceo": [0.006, 0.007],
                      "mejora_rebalanceo_con_rezago": [0.001, -0.001]})
    assert ex.pistas(pd.DataFrame(), r, pd.DataFrame())["pista"].tolist() == [False]
