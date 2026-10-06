"""La escalera de modelos de la fase 7, con datos sintéticos."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.investigacion import fase7


def _xy(n: int = 360, semilla: int = 3):
    rng = np.random.default_rng(semilla)
    idx = pd.date_range("1980-01-31", periods=n, freq="ME")
    X = pd.DataFrame(rng.uniform(size=(n, 3)), index=idx, columns=["a", "b", "c"])
    y = pd.Series(0.3 * (X["b"] - 0.5) + rng.normal(0, 0.05, n), index=idx)
    return X, y


def test_el_pronostico_no_usa_retornos_que_no_han_terminado():
    X, y = _xy()
    base = fase7.walk_forward(X, y, fase7.ajuste_ridge, h=12, minimo=120, cada=12)
    t = base.first_valid_index()
    pos = X.index.get_loc(t)
    alterado = y.copy()
    alterado.iloc[pos - 11:] = 50.0        # pares cuyo retorno de 12 meses no había terminado en t
    otro = fase7.walk_forward(X, alterado, fase7.ajuste_ridge, h=12, minimo=120, cada=12)
    assert otro.loc[t] == pytest.approx(base.loc[t])
    # El primer pronóstico llega cuando hay 120 pares terminados: 120 + 12 − 1 meses.
    assert pos == 120 + 12 - 1


@pytest.mark.parametrize("nombre", ["mejor señal sola", "compuesto", "ridge", "árboles"])
def test_cada_peldano_aprende_una_relacion_real(nombre):
    X, y = _xy()
    if nombre == "compuesto":
        X = X.assign(a=X["b"], c=X["b"])   # el compuesto solo sirve si todas apuntan igual
    p = fase7.walk_forward(X, y, fase7.AJUSTES[nombre], h=1, minimo=120, cada=12)
    ok = p.notna()
    assert np.corrcoef(p[ok], y[ok])[0, 1] > 0.5


def test_la_mejor_senal_sola_escoge_la_que_predice():
    X, y = _xy()
    predecir = fase7.ajuste_mejor_senal(X, y)
    assert np.corrcoef(predecir(X), X["b"])[0, 1] == pytest.approx(1.0)


def test_la_exposicion_sale_solo_si_el_pronostico_es_negativo():
    p = pd.Series([np.nan, 0.05, -0.01, 0.0])
    assert fase7.exposicion_de_pronostico(p).tolist() == [1.0, 1.0, 0.0, 0.0]


def test_la_escalera_se_queda_con_el_ultimo_que_mejora():
    ev = pd.DataFrame({"senal": list(fase7.PELDANOS), "mejora_rebalanceo": [0.001, 0.003, 0.002, 0.004, -0.01]})
    quedan, candidato = fase7.escalera(ev)
    assert quedan == ["mejor señal sola", "compuesto", "árboles"] and candidato == "árboles"
    ev["mejora_rebalanceo"] = -0.001
    assert fase7.escalera(ev) == ([], "")


def test_los_regimenes_ven_el_regimen_malo_con_el_pasado():
    rng = np.random.default_rng(1)
    r = np.r_[rng.normal(0.012, 0.025, 160), rng.normal(-0.04, 0.09, 24), rng.normal(0.012, 0.025, 40)]
    idx = pd.date_range("1990-01-31", periods=len(r), freq="ME")
    x = pd.DataFrame({"retorno_total": r, "efectivo": 0.0}, index=idx)
    rg = fase7.regimenes(x, minimo=120, cada=24)
    malo = rg["p_malo"].iloc[165:184].mean()
    bueno = rg["p_malo"].iloc[130:160].mean()
    assert malo > 0.5 > bueno
