"""El banco de pruebas de las señales de entrada (fase 5), con señales sintéticas."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.investigacion import bitacora, timing


def _sector(n: int = 360, semilla: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    idx = pd.date_range("1980-01-31", periods=n, freq="ME")
    regimen = np.sign(np.sin(np.arange(n) / 9))                 # rachas buenas y malas
    precio = 0.004 + 0.03 * regimen + rng.normal(0, 0.03, n)
    return pd.DataFrame({"retorno_precio": precio, "retorno_ingreso": np.full(n, 0.004),
                         "retorno_total": precio + 0.004, "efectivo": np.full(n, 0.003)}, index=idx)


def test_las_reglas_de_exposicion():
    s = pd.Series(np.r_[np.full(60, np.nan), np.arange(100.0)], index=pd.date_range("2000-01-31", periods=160, freq="ME"))
    b = timing.exposicion_binaria_por_percentil(s, 0.5, minimo=10)
    assert b.iloc[:60].eq(1.0).all()                   # sin historia, dentro
    assert b.iloc[-1] == 1.0                           # el valor más alto visto
    assert timing.exposicion_por_signo(pd.Series([-1.0, 0.0, 2.0, np.nan])).tolist() == [0.0, 0.0, 1.0, 1.0]
    c = timing.exposicion_continua(s, minimo=10, piso=0.2)
    assert c.dropna().between(0.2, 1.0).all()


def test_una_senal_que_ve_el_regimen_gana_y_una_al_azar_no(tmp_path):
    x = _sector()
    ruta = tmp_path / "bitacora.csv"
    exceso_siguiente = (x["retorno_total"] - x["efectivo"]).shift(-1)
    buena = timing.Senal("sabe", "prueba", lambda x, i: exceso_siguiente.fillna(0), "conoce el mes siguiente")
    rng = np.random.default_rng(1)
    azar = pd.Series(rng.normal(size=len(x)), index=x.index)
    mala = timing.Senal("azar", "prueba", lambda x, i: azar, "ruido")
    ind = pd.DataFrame(index=x.index)
    rb = timing.evaluar(buena, "signo", timing.exposicion_por_signo(buena.calcular(x, ind)), x, ind,
                        muestra="desarrollo", ruta_bitacora=ruta)
    rm = timing.evaluar(mala, "signo", timing.exposicion_por_signo(azar), x, ind, muestra="desarrollo",
                        ruta_bitacora=ruta)
    assert rb["mejora_rebalanceo"] > 0.05 and rb["mejora_contra_mezcla_fija"] > 0.05
    assert rb["r2_1m"] > 0.2 and rb["clark_west_p_1m"] < 0.01
    assert rm["mejora_contra_mezcla_fija"] < rb["mejora_contra_mezcla_fija"]
    assert rm["clark_west_p_1m"] > 0.01
    # Las dos quedaron anotadas como intentos de la misma familia.
    assert bitacora.intentos("prueba", ruta=ruta) == 2


def test_los_retornos_de_la_regla_usan_la_decision_del_mes_anterior():
    x = _sector(n=4)
    e = pd.Series([1.0, 0.0, 1.0, 0.0], index=x.index)
    r = timing.retornos_de_la_regla(e, x)
    exceso = x["retorno_total"] - x["efectivo"]
    assert r.tolist() == pytest.approx([exceso.iloc[1], 0.0, exceso.iloc[3]])
