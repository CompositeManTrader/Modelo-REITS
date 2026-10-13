"""El análisis de poder: errores estándar, placebos y ventajas inyectadas."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.investigacion import estadistica, resultados
from src.investigacion import poder as po
from src.investigacion.simulacion import Mercado


def test_el_error_estandar_nw_sin_rezago_es_el_de_libro():
    rng = np.random.default_rng(1)
    x = rng.normal(0.01, 0.05, 300)
    assert estadistica.error_estandar_nw(x, 0) == pytest.approx(x.std(ddof=0) / math.sqrt(len(x)))
    assert estadistica.newey_west_t(x, 4) == pytest.approx(x.mean() / estadistica.error_estandar_nw(x, 4))
    assert np.isnan(estadistica.error_estandar_nw(np.array([1.0, 2.0]), 1))


def test_la_lectura_de_una_nula_normal():
    rng = np.random.default_rng(2)
    nula = rng.normal(-0.002, 0.01, 20_000)
    fila, curva = po.resumir_nula("p", "m", 0.0, nula, criterio=0.005)
    assert fila["ee"] == pytest.approx(0.01, rel=0.03)
    assert fila["mde"] == pytest.approx(po.Z_DETECCION * 0.01, rel=0.03)
    assert fila["nula_media"] == pytest.approx(-0.002, abs=5e-4)
    potencias = [c["potencia_deteccion"] for c in curva]
    assert potencias == sorted(potencias)
    # Con una habilidad igual al MDE, la potencia es ~80%.
    _, c = po.resumir_nula("p", "m", 0.0, nula, criterio=0.005, deltas=(fila["mde"],))
    assert c[0]["potencia_deteccion"] == pytest.approx(0.80, abs=0.03)
    assert c[0]["inadvertida"] == pytest.approx(0.20, abs=0.03)


def _mercado(n=240, semilla=4):
    rng = np.random.default_rng(semilla)
    fechas = pd.date_range("1990-01-31", periods=n, freq="ME")
    return Mercado(fechas, rng.normal(0.006, 0.04, n), np.full(n, 0.004), np.full(n, 0.003))


def test_una_regla_que_conoce_el_futuro_sale_del_placebo_y_una_constante_no_tiene_ruido():
    m = _mercado()
    sabe = (np.r_[m.retorno_precio[1:], 0.0] > 0).astype(float)          # dentro si el mes siguiente sube
    observado, nula = po.nula_desplazada(m, sabe, n=60)
    assert observado > np.quantile(nula, 0.99)
    observado, nula = po.nula_desplazada(m, np.ones(len(m.fechas)), n=20)
    assert observado == pytest.approx(0.0, abs=1e-12) and np.allclose(nula, 0.0, atol=1e-12)
    with pytest.raises(ValueError):
        po.desplazamientos(30, 5, np.random.default_rng(0), minimo=24)


def test_el_sharpe_necesario_sube_con_los_intentos():
    rng = np.random.default_rng(5)
    r = rng.normal(0.01, 0.05, 200)
    pocos = po.sharpe_necesario(r, intentos=2, varianza_de_sharpes=0.01)
    muchos = po.sharpe_necesario(r, intentos=200, varianza_de_sharpes=0.01)
    assert 0 < pocos < muchos


def test_una_ventaja_inyectada_se_recupera():
    rng = np.random.default_rng(6)
    idx = pd.date_range("1975-01-31", periods=360, freq="ME")
    x = pd.DataFrame({"retorno_precio": rng.normal(0.006, 0.04, 360), "retorno_ingreso": 0.004, "efectivo": 0.003},
                     index=idx)
    # Persistente, como la tendencia: rachas de un año dentro o fuera.
    e = pd.Series(np.repeat((rng.random(30) < 0.7).astype(float), 12), index=idx)
    r = po.inyeccion(x, e, deltas=(0.06,), n=25, semilla=1)
    sin, con = r.iloc[0], r.iloc[1]
    assert con["mejora_mediana"] - sin["mejora_mediana"] == pytest.approx(0.06, abs=0.03)
    assert con["pasa_50pb"] > sin["pasa_50pb"]
    assert con["pasa_criterios_de_retorno"] >= sin["pasa_criterios_de_retorno"]


@pytest.mark.skipif("fase5" not in resultados.cargar(), reason="sin resultados guardados")
def test_la_tendencia_observada_es_la_de_la_fase5():
    from src.investigacion import exploracion

    x = exploracion.sector()
    filas, _ = po.timing_desarrollo(x, exploracion.indicadores(x), n=30)
    g = resultados.cargar()["fase5"]["desarrollo"].set_index(["senal", "regla"])["mejora_rebalanceo"]
    for f, (senal, regla) in zip(filas, po.REGLAS_TIMING, strict=True):
        assert f["observado"] == pytest.approx(g.loc[(senal, regla)], abs=1e-8)
