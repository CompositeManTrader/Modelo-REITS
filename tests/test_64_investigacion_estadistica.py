"""Las pruebas estadísticas de la investigación, contra casos con respuesta conocida."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.investigacion import estadistica as es


def test_newey_west_sin_rezago_es_la_t_de_siempre():
    rng = np.random.default_rng(1)
    x = rng.normal(0.1, 1, 500)
    t_clasica = x.mean() / (x.std(ddof=0) / np.sqrt(len(x)))
    assert es.newey_west_t(x, 0) == pytest.approx(t_clasica)
    # Con autocorrelación positiva, Newey-West agranda el error y baja la t.
    y = np.convolve(rng.normal(0.1, 1, 520), np.ones(12) / 12, mode="valid")[:500]
    assert abs(es.newey_west_t(y, 12)) < abs(es.newey_west_t(y, 0))


def test_r2_fuera_de_muestra_y_clark_west():
    rng = np.random.default_rng(2)
    n = 600
    s = rng.normal(0, 1, n)
    idx = pd.date_range("1970-01-31", periods=n, freq="ME")
    # El retorno del mes siguiente (guardado en t, como lo usa todo el proyecto) depende de la señal de hoy.
    objetivo = pd.Series(0.5 * s + rng.normal(0, 1, n), index=idx)
    p = es.pronostico_expandible(pd.Series(s, index=idx), objetivo, minimo=60, horizonte=1)
    r2 = es.r2_fuera_de_muestra(p["real"], p["pronostico"], p["promedio"])
    assert 0.10 < r2 < 0.30
    t, valor_p = es.clark_west(p["real"], p["pronostico"], p["promedio"])
    assert valor_p < 0.001
    # Una señal sin información no mejora al promedio.
    ruido = pd.Series(rng.normal(0, 1, n), index=idx)
    q = es.pronostico_expandible(ruido, objetivo, minimo=60, horizonte=1)
    assert es.r2_fuera_de_muestra(q["real"], q["pronostico"], q["promedio"]) < 0.01


def test_el_pronostico_solo_usa_retornos_ya_terminados():
    """Con horizonte de 12, el pronóstico de t no puede depender del retorno que termina después de t."""
    n = 200
    idx = pd.date_range("1990-01-31", periods=n, freq="ME")
    rng = np.random.default_rng(3)
    s = pd.Series(rng.normal(size=n), index=idx)
    y = pd.Series(rng.normal(size=n), index=idx)
    base = es.pronostico_expandible(s, y, minimo=36, horizonte=12)
    t = 120
    alterado = y.copy()
    alterado.iloc[t - 11:] = 99.0           # pares cuyo retorno de 12 meses aún no terminaba en t
    p2 = es.pronostico_expandible(s, alterado, minimo=36, horizonte=12)
    assert p2["pronostico"].iloc[t] == pytest.approx(base["pronostico"].iloc[t])


def test_el_mejor_de_muchos_intentos_se_deflacta():
    rng = np.random.default_rng(4)
    r = rng.normal(0.004, 0.04, 360)        # Sharpe mensual ~0.1
    uno = es.sharpe_deflactado(r, intentos=1, varianza_de_sharpes=0.002)
    cien = es.sharpe_deflactado(r, intentos=100, varianza_de_sharpes=0.002)
    assert cien < uno
    assert es.sharpe_maximo_esperado(1, 0.002) == 0.0
    assert es.sharpe_maximo_esperado(1000, 0.002) > es.sharpe_maximo_esperado(10, 0.002) > 0


def test_pbo_distingue_ruido_de_habilidad():
    rng = np.random.default_rng(5)
    ruido = pd.DataFrame(rng.normal(0, 0.04, (480, 20)))
    assert es.pbo(ruido, bloques=8) > 0.3
    habil = ruido.copy()
    habil[0] = habil[0] + 0.02             # una configuración con ventaja real y grande
    assert es.pbo(habil, bloques=8) < 0.1


def test_apuestas_efectivas():
    assert es.apuestas_efectivas(528, 12) == 44
    assert es.apuestas_efectivas(528, 12, cambios=30) == 30


def test_una_senal_constante_pronostica_el_promedio():
    idx = pd.date_range("1990-01-31", periods=100, freq="ME")
    s = pd.Series(1.0, index=idx)
    y = pd.Series(np.random.default_rng(0).normal(size=100), index=idx)
    p = es.pronostico_expandible(s, y, minimo=36, horizonte=1).dropna()
    assert (p["pronostico"] == p["promedio"]).all()
