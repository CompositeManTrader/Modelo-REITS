"""La valuación como retorno esperado: tramos del percentil y el rango de lo que rindió después."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config import MARGINAL_DEL_INVERSIONISTA
from src.estudio import metodos
from src.fiscal.mexico import tasa_dividendo_via_broker


def test_los_tramos_y_sus_orillas():
    assert metodos.tramo_de(0.0) == "muy caro"
    assert metodos.tramo_de(0.0999) == "muy caro"
    assert metodos.tramo_de(0.10) == "caro"
    assert metodos.tramo_de(metodos.CARO) == "medio"
    assert metodos.tramo_de(metodos.BARATO) == "barato"
    assert metodos.tramo_de(0.90) == "muy barato"
    assert metodos.tramo_de(1.0) == "muy barato"
    assert metodos.tramo_de(np.nan) is None and metodos.tramo_de(None) is None


def test_el_broker_al_35_cobra_44_al_dividendo():
    assert MARGINAL_DEL_INVERSIONISTA == pytest.approx(0.35)
    assert tasa_dividendo_via_broker(MARGINAL_DEL_INVERSIONISTA) == pytest.approx(0.44)


def _panel(percentiles: np.ndarray, retornos: np.ndarray) -> pd.DataFrame:
    """Un panel mensual: cada fin de trimestre lleva el percentil y el retorno de 5 años que se le da."""
    meses = pd.date_range("2000-01-31", periods=3 * len(percentiles), freq="ME")
    p = pd.DataFrame(index=meses, columns=["p_consenso", "adelante_5a", "efectivo_5a"], dtype=float)
    fines = meses[meses.month.isin([3, 6, 9, 12])][: len(percentiles)]
    p.loc[fines, "p_consenso"] = percentiles
    p.loc[fines, "adelante_5a"] = retornos
    p.loc[fines, "efectivo_5a"] = 0.01
    return p


def test_el_rango_por_tramo_sale_de_los_trimestres_de_ese_tramo():
    # 20 trimestres baratos que rinden 20% y 20 caros que rinden 5%; 2 muy caros (pocos para dar rango).
    pct = np.r_[np.full(20, 0.8), np.full(20, 0.2), [0.05, 0.02]]
    ret = np.r_[np.linspace(0.15, 0.25, 20), np.linspace(0.0, 0.10, 20), [0.03, 0.03]]
    t = metodos.retorno_esperado({"A": _panel(pct, ret)})
    j = t[t["alcance"] == "juntos"].set_index("tramo")
    assert j.loc["barato", "trimestres"] == 20 and j.loc["barato", "mediana"] == pytest.approx(0.20)
    assert j.loc["caro", "mediana"] == pytest.approx(0.05)
    assert j.loc["barato", "p10"] < j.loc["barato", "mediana"] < j.loc["barato", "p90"]
    assert j.loc["barato", "ventanas_independientes"] == pytest.approx(1.0)
    assert j.loc["muy caro", "trimestres"] == 2 and np.isnan(j.loc["muy caro", "mediana"])
    assert j.loc["medio", "trimestres"] == 0
    assert set(t["alcance"]) == {"juntos", "A"}


def test_hoy_toma_el_ultimo_percentil_y_el_rango_de_su_tramo():
    pct = np.r_[np.full(20, 0.8), np.full(20, 0.2)]
    ret = np.r_[np.full(20, 0.20), np.full(20, 0.05)]
    paneles = {"A": _panel(pct, ret), "B": _panel(pct[::-1], ret[::-1])}
    tabla = metodos.retorno_esperado(paneles)
    hoy = metodos.esperado_hoy(paneles, tabla).set_index("emisor")
    assert hoy.loc["A", "tramo"] == "caro" and hoy.loc["A", "mediana"] == pytest.approx(0.05)
    assert hoy.loc["B", "tramo"] == "barato" and hoy.loc["B", "mediana"] == pytest.approx(0.20)
    frase = metodos.frase_esperado(hoy.reset_index().iloc[1])
    assert "«barato»" in frase and "20.0%" in frase
    assert "Sin suficientes" in metodos.frase_esperado(pd.Series({"tramo": None, "mediana": np.nan}))
