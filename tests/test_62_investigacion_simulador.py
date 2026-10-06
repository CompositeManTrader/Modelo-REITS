"""El simulador de la investigación, contra escenarios hechos a mano."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from src.investigacion.diseno import OBJETIVO
from src.investigacion.simulacion import Mercado, Modo, benchmark, simular

SIN_COSTOS = replace(OBJETIVO, comision=0.0, impuesto_dividendo=0.0, impuesto_intereses=0.0, impuesto_ganancia=0.0)


def _mercado(n=120, precio=0.01, ingreso=0.0, efectivo=0.002) -> Mercado:
    return Mercado(pd.date_range("2000-01-31", periods=n, freq="ME"), np.full(n, precio), np.full(n, ingreso),
                   np.full(n, efectivo))


def test_aportar_siempre_a_un_activo_que_rinde_fijo_da_esa_tir():
    r = benchmark(_mercado(precio=0.01), objetivo=SIN_COSTOS)
    assert r.tir == pytest.approx(1.01 ** 12 - 1, abs=2e-4)
    assert r.exposicion_promedio == pytest.approx(1.0)
    assert r.caida_maxima == pytest.approx(0.0)
    assert r.aportado == pytest.approx(119 * 1_000)      # el último mes solo se liquida


def test_todo_en_efectivo_rinde_la_tasa_menos_su_impuesto():
    obj = replace(SIN_COSTOS, impuesto_intereses=0.20)
    r = simular(_mercado(efectivo=0.005), 0.0, objetivo=obj)
    assert r.tir == pytest.approx(1.004 ** 12 - 1, abs=2e-4)
    assert r.exposicion_promedio == pytest.approx(0.0)


def test_el_dividendo_paga_20_por_ciento_y_se_reinvierte():
    obj = replace(SIN_COSTOS, impuesto_dividendo=0.20)
    r = benchmark(_mercado(precio=0.0, ingreso=0.01), objetivo=obj)
    assert r.tir == pytest.approx(1.008 ** 12 - 1, abs=2e-4)


def test_la_ganancia_paga_10_por_ciento_al_vender_y_la_comision_cobra_dos_veces():
    """Una sola aportación de 100 que se duplica: vende en 200, paga 10% de 100 de ganancia."""
    n = 3
    m = Mercado(pd.date_range("2000-01-31", periods=n, freq="ME"), np.array([0.0, 1.0, 0.0]), np.zeros(n), np.zeros(n))
    obj = replace(SIN_COSTOS, impuesto_ganancia=0.10)
    r = simular(m, 1.0, objetivo=obj, aportaciones=np.array([100.0, 0.0, 0.0]))
    assert r.valor_final == pytest.approx(190.0)
    assert r.impuestos == pytest.approx(10.0)
    obj = replace(SIN_COSTOS, comision=0.01)
    r = simular(m, 1.0, objetivo=obj, aportaciones=np.array([100.0, 0.0, 0.0]))
    # Compra 100 con 1 de comisión: 99 que se duplican a 198; vende con 1% de comisión.
    assert r.valor_final == pytest.approx(198 * 0.99)


def test_una_perdida_compensa_la_ganancia_siguiente():
    """Exposición: baja 50% y se vende todo (pérdida de 50); vuelve a comprar y gana 50: no paga."""
    m = Mercado(pd.date_range("2000-01-31", periods=5, freq="ME"), np.array([0, -0.5, 0, 1.0, 0]),
                np.zeros(5), np.zeros(5))
    obj = replace(SIN_COSTOS, impuesto_ganancia=0.10)
    r = simular(m, np.array([1, 0, 1, 1, 1.0]), modo=Modo.EXPOSICION, objetivo=obj,
                aportaciones=np.array([100.0, 0, 0, 0, 0]))
    # 100 → 50, vende (pérdida 50); recompra 50 → 100, vende al final (ganancia 50, compensada).
    assert r.valor_final == pytest.approx(100.0)
    assert r.impuestos == pytest.approx(0.0)


def test_la_exposicion_rebalancea_y_la_aportacion_nunca_vende():
    m = _mercado(n=24, precio=0.02)
    ex = simular(m, 0.5, modo=Modo.EXPOSICION, objetivo=SIN_COSTOS)
    assert ex.mensual["exposicion"].iloc[:-1].to_numpy() == pytest.approx(0.5)
    ap = simular(m, np.r_[np.ones(12), np.zeros(12)], modo=Modo.APORTACION, objetivo=SIN_COSTOS)
    activo = ap.mensual["activo"].iloc[:-1]
    assert (activo.diff().dropna() >= -1e-9).all()     # el activo nunca baja por ventas (el precio sube)


def test_el_rezago_ejecuta_la_decision_un_mes_despues():
    m = _mercado(n=6, precio=0.0, efectivo=0.0)
    e = np.array([1, 1, 0, 0, 1, 1.0])
    r0 = simular(m, e, modo=Modo.EXPOSICION, objetivo=SIN_COSTOS)
    r1 = simular(m, e, modo=Modo.EXPOSICION, objetivo=SIN_COSTOS, rezago=1)
    assert r0.mensual["exposicion"].iloc[:5].round(6).tolist() == [1, 1, 0, 0, 1]
    assert r1.mensual["exposicion"].iloc[:5].round(6).tolist() == [0, 1, 1, 0, 0]


def test_esquivar_la_caida_baja_la_caida_maxima():
    precio = np.r_[np.full(12, 0.01), np.full(6, -0.08), np.full(12, 0.01)]
    m = Mercado(pd.date_range("2000-01-31", periods=30, freq="ME"), precio, np.zeros(30), np.full(30, 0.001))
    siempre = simular(m, 1.0, modo=Modo.EXPOSICION, objetivo=SIN_COSTOS)
    fuera = simular(m, np.r_[np.ones(11), np.zeros(7), np.ones(12)], modo=Modo.EXPOSICION, objetivo=SIN_COSTOS)
    assert siempre.caida_maxima == pytest.approx(0.92 ** 6 - 1, abs=1e-9)
    assert fuera.caida_maxima > -0.01 and fuera.tir > siempre.tir


def test_la_exposicion_sin_decision_es_un_error():
    with pytest.raises(ValueError):
        simular(_mercado(n=5), np.array([1, np.nan, 1, 1, 1]))
