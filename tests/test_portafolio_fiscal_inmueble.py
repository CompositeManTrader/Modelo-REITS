"""Pruebas del portafolio, la capa fiscal y el comparativo inmobiliario."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.fiscal.mexico import (
    UMBRAL_ESTATE_TAX_USD,
    ViaDeCompra,
    alerta_estate_tax,
    impuesto_dividendo,
    impuesto_ganancia_capital,
    isr_arrendamiento,
    tasa_efectiva_isr,
    tasa_marginal_isr,
)
from src.portafolio.metricas import (
    atribuir_retorno,
    crecimiento_real_anualizado,
    drawdown_maximo,
    tir,
    twr,
    twr_acumulado,
)
from src.portafolio.rebalanceo import (
    Restricciones,
    capital_requerido,
    destino_de_aportacion,
    proponer_asignacion,
    simular_aportaciones,
)
from src.portafolio.transacciones import TipoTx, flujos_de_caja, procesar_libro
from src.simulacion.inmueble_cdmx import (
    SupuestosInmueble,
    comparar_con_reits,
    diagnosticar_carry,
    escenario_inquilino_moroso,
    evaluar_inmueble,
    operacion_anual,
    plusvalia_necesaria_para_empatar,
)

# --------------------------------------------------------------------------------------
# Libro de transacciones
# --------------------------------------------------------------------------------------


def _libro() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"id": 1, "fecha": dt.date(2023, 1, 10), "ticker": "O", "tipo": TipoTx.COMPRA,
             "cantidad": 100.0, "precio": 60.0, "comision": 10.0, "tipo_cambio": 18.0,
             "retencion_eeuu": 0.0},
            {"id": 2, "fecha": dt.date(2023, 7, 10), "ticker": "O", "tipo": TipoTx.COMPRA,
             "cantidad": 100.0, "precio": 55.0, "comision": 10.0, "tipo_cambio": 17.5,
             "retencion_eeuu": 0.0},
            {"id": 3, "fecha": dt.date(2024, 1, 15), "ticker": "O", "tipo": TipoTx.DIVIDENDO,
             "cantidad": 200.0, "precio": 0.26, "comision": 0.0, "tipo_cambio": 17.0,
             "retencion_eeuu": 5.2},
            {"id": 4, "fecha": dt.date(2024, 6, 20), "ticker": "O", "tipo": TipoTx.VENTA,
             "cantidad": 50.0, "precio": 65.0, "comision": 10.0, "tipo_cambio": 18.5,
             "retencion_eeuu": 0.0},
        ]
    )


def test_costo_promedio_y_ganancia_realizada():
    estado = procesar_libro(_libro())
    posicion = estado.posiciones["O"]

    assert posicion.cantidad == pytest.approx(150.0)
    # Costo promedio de 200 títulos: (100x60+10 + 100x55+10) / 200 = 57.60
    assert posicion.costo_promedio == pytest.approx(57.60, abs=0.01)
    # Venta de 50 a 65 menos 10 de comisión, contra un costo de 50 x 57.60.
    assert posicion.ganancia_realizada == pytest.approx(50 * 65 - 10 - 50 * 57.60, abs=0.01)
    assert posicion.dividendos_cobrados == pytest.approx(52.0)
    assert posicion.retencion_pagada == pytest.approx(5.2)


def test_no_se_puede_vender_lo_que_no_se_tiene():
    libro = _libro()
    libro.loc[3, "cantidad"] = 500.0
    with pytest.raises(ValueError, match="Venta de"):
        procesar_libro(libro)


def test_yield_sobre_costo_usa_el_costo_no_el_precio():
    estado = procesar_libro(_libro())
    posicion = estado.posiciones["O"]
    yoc = posicion.yield_sobre_costo(3.12)
    assert yoc == pytest.approx(3.12 / posicion.costo_promedio, rel=1e-9)
    assert yoc > 3.12 / 65.0, "El yield sobre costo supera al de mercado si el papel subió."


def test_flujos_del_inversionista():
    flujos = flujos_de_caja(_libro())
    assert flujos.iloc[0] == pytest.approx(-(100 * 60 + 10))
    assert flujos.loc[pd.Timestamp("2024-01-15")] == pytest.approx(52.0 - 5.2)


# --------------------------------------------------------------------------------------
# TWR y TIR
# --------------------------------------------------------------------------------------


def test_twr_ignora_el_timing_de_las_aportaciones():
    """El TWR mide la selección de activos: aportar más o menos no debe moverlo.

    Convención: el flujo entra al FINAL del subperiodo, así que el retorno del
    periodo i es (V_i − F_i)/V_(i−1) − 1. El activo rinde 10% en los tres
    periodos y en el segundo entran 100 de aportación.
    """
    fechas = pd.date_range("2023-01-31", periods=4, freq="ME")
    #       100 → 110 → 121 + 100 de aportación = 221 → 243.1
    valores = pd.Series([100.0, 110.0, 221.0, 243.1], index=fechas)
    flujos = pd.Series([0.0, 0.0, 100.0, 0.0], index=fechas)

    retornos = twr(valores, flujos)
    assert all(r == pytest.approx(0.10, abs=1e-9) for r in retornos), (
        "La aportación no puede leerse como rendimiento."
    )
    assert twr_acumulado(valores, flujos) == pytest.approx(1.10**3 - 1, abs=1e-9)


def test_tir_y_twr_difieren_cuando_el_timing_importa():
    """La distinción que la interfaz explica: son dos preguntas distintas.

    El portafolio cae 50% y luego duplica: el TWR es exactamente 0%, porque el
    activo terminó donde empezó. Pero el inversionista aportó 100 más JUSTO en el
    fondo, así que su resultado real fue muy bueno. La TIR lo captura y el TWR no,
    y ninguno de los dos está mal: miden cosas distintas.
    """
    fechas = pd.to_datetime(["2023-12-31", "2024-12-31", "2025-12-31"])
    #        100 → 50 tras la caída, +100 de aportación = 150 → 300
    valores = pd.Series([100.0, 150.0, 300.0], index=fechas)
    flujos_externos = pd.Series([0.0, 100.0, 0.0], index=fechas)

    twr_total = twr_acumulado(valores, flujos_externos)
    assert twr_total == pytest.approx(0.0, abs=1e-9), "El activo terminó donde empezó."

    flujos_inversionista = pd.Series([-100.0, -100.0, 300.0], index=fechas)
    tir_usuario = tir(flujos_inversionista)
    assert tir_usuario is not None
    assert tir_usuario == pytest.approx(0.3028, abs=0.005)
    assert tir_usuario > twr_total, (
        "Comprar en el fondo mejora el resultado del inversionista sin cambiar el "
        "rendimiento del activo. Confundir ambos números es el error más común."
    )


def test_tir_requiere_flujos_de_ambos_signos():
    solo_negativos = pd.Series([-100.0, -50.0], index=pd.to_datetime(["2023-01-01", "2024-01-01"]))
    assert tir(solo_negativos) is None, (
        "Sin un flujo positivo no hay tasa que iguale el valor presente a cero. "
        "Devolver un número sería inventarlo."
    )


def test_drawdown_maximo():
    valores = pd.Series(
        [100.0, 120.0, 80.0, 90.0, 130.0],
        index=pd.date_range("2023-01-31", periods=5, freq="ME"),
    )
    assert drawdown_maximo(valores) == pytest.approx(80 / 120 - 1)


# --------------------------------------------------------------------------------------
# Atribución en tres componentes
# --------------------------------------------------------------------------------------


def test_atribucion_cierra_exacto():
    """La suma de los componentes tiene que dar el retorno total, sin residuo escondido."""
    a = atribuir_retorno(
        precio_inicial=50.0, precio_final=60.0,
        affo_por_accion_inicial=2.50, affo_por_accion_final=2.75,
        dividendos_cobrados_por_accion=2.00,
    )
    assert a is not None
    suma = a.yield_cobrado + a.crecimiento_affo + a.cambio_multiplo + a.termino_cruzado
    assert suma == pytest.approx(a.retorno_total, abs=1e-12)
    assert a.crecimiento_affo == pytest.approx(0.10)
    assert a.yield_cobrado == pytest.approx(0.04)


def test_atribucion_separa_negocio_de_revaluacion():
    """Todo el retorno por expansión de múltiplo es prestado: se devuelve."""
    solo_multiplo = atribuir_retorno(50.0, 60.0, 2.50, 2.50, 0.0)
    assert solo_multiplo.crecimiento_affo == pytest.approx(0.0)
    assert solo_multiplo.cambio_multiplo == pytest.approx(0.20)

    solo_negocio = atribuir_retorno(50.0, 60.0, 2.50, 3.00, 0.0)
    assert solo_negocio.crecimiento_affo == pytest.approx(0.20)
    assert solo_negocio.cambio_multiplo == pytest.approx(0.0)


def test_ingreso_real_contra_ingreso_nominal():
    """El caso documentado: dividendo creciendo 3.2% contra inflación de 3.3%."""
    anios = pd.date_range("2021-12-31", periods=5, freq="YE")
    dividendo = pd.Series([1.0 * (1.032**i) for i in range(5)], index=anios)
    ipc = pd.Series([100.0 * (1.033**i) for i in range(5)], index=anios)

    resultado = crecimiento_real_anualizado(dividendo, ipc)
    assert resultado["nominal"] == pytest.approx(0.032, abs=0.001)
    assert resultado["inflacion"] == pytest.approx(0.033, abs=0.001)
    assert resultado["real"] == pytest.approx(-0.001, abs=0.002), (
        "El ingreso quedó plano en poder adquisitivo mientras el dividendo nominal subía."
    )


# --------------------------------------------------------------------------------------
# Meta de ingreso y asignación
# --------------------------------------------------------------------------------------


def test_capital_requerido_usa_la_tasa_real():
    meta = capital_requerido(600_000.0, tasa_retiro_real=0.042, inflacion=0.045)
    assert meta.capital_requerido_real == pytest.approx(600_000 / 0.042)
    assert meta.capital_requerido_real > meta.capital_requerido_nominal, (
        "Planear con la tasa nominal subestima el capital necesario."
    )
    assert "poder adquisitivo" in meta.explicacion()


def test_simulador_de_aportaciones_alcanza_la_meta():
    plan = simular_aportaciones(1_500_000.0, 25_000.0, 0.042, 14_285_714.0)
    assert plan.meses_necesarios is not None
    assert 0 < plan.meses_necesarios <= 600
    assert "poder adquisitivo de hoy" in plan.como_texto()


def test_asignacion_respeta_los_topes_y_excluye_lo_que_falla_calidad():
    candidatos = pd.DataFrame(
        [
            {"ticker": "A", "sector": "Net Lease", "percentil_prima": 0.95, "pasa_calidad": True},
            {"ticker": "B", "sector": "Net Lease", "percentil_prima": 0.90, "pasa_calidad": True},
            {"ticker": "C", "sector": "Net Lease", "percentil_prima": 0.85, "pasa_calidad": True},
            {"ticker": "D", "sector": "Industrial", "percentil_prima": 0.60, "pasa_calidad": True},
            {"ticker": "E", "sector": "Self Storage", "percentil_prima": 0.55, "pasa_calidad": True},
            {"ticker": "F", "sector": "Salud", "percentil_prima": 0.50, "pasa_calidad": True},
            {"ticker": "MALO", "sector": "Oficinas", "percentil_prima": 0.99, "pasa_calidad": False},
        ]
    )
    asignacion = proponer_asignacion(candidatos, restricciones=Restricciones(0.25, 0.40, 6, True))

    assert "MALO" not in asignacion.pesos.index, (
        "Percentil de 99 y aun así excluido: lo que falla calidad no compite por peso."
    )
    assert asignacion.pesos.sum() == pytest.approx(1.0, abs=1e-9)
    assert asignacion.pesos.max() <= 0.25 + 1e-9
    por_sector = asignacion.pesos.groupby(candidatos.set_index("ticker")["sector"]).sum()
    assert por_sector.max() <= 0.40 + 1e-9


def test_destino_de_aportacion_prefiere_lo_barato_que_pasa_calidad():
    candidatos = pd.DataFrame(
        [
            {"ticker": "BARATO", "sector": "Net Lease", "percentil_prima": 0.92, "pasa_calidad": True},
            {"ticker": "CARO", "sector": "Net Lease", "percentil_prima": 0.10, "pasa_calidad": True},
            {"ticker": "ROTO", "sector": "Oficinas", "percentil_prima": 0.99, "pasa_calidad": False},
        ]
    )
    destinos = destino_de_aportacion(candidatos, 10_000.0, max_destinos=2)
    tickers = [d.ticker for d in destinos]
    assert "ROTO" not in tickers
    assert tickers[0] == "BARATO"
    assert sum(d.monto for d in destinos) == pytest.approx(10_000.0)


# --------------------------------------------------------------------------------------
# Capa fiscal
# --------------------------------------------------------------------------------------


def test_retencion_combinada_ronda_veinte_por_ciento():
    resultado = impuesto_dividendo(10_000.0, tiene_w8ben=True)
    assert resultado.retencion_eeuu == pytest.approx(1_000.0)
    assert resultado.isr_mexico == pytest.approx(1_000.0)
    assert resultado.tasa_efectiva == pytest.approx(0.20)
    assert any("tratado" in a for a in resultado.advertencias)


def test_sin_w8ben_la_retencion_sube_a_treinta():
    resultado = impuesto_dividendo(10_000.0, tiene_w8ben=False)
    assert resultado.retencion_eeuu == pytest.approx(3_000.0)
    assert any("W-8BEN" in a for a in resultado.advertencias)


def test_la_via_de_compra_cambia_el_impuesto_mas_que_el_activo():
    ganancia = 500_000.0
    sic = impuesto_ganancia_capital(ganancia, via=ViaDeCompra.SIC)
    extranjero = impuesto_ganancia_capital(
        ganancia, via=ViaDeCompra.BROKER_EXTRANJERO, ingreso_acumulable_previo=1_200_000.0
    )
    assert sic.tasa_efectiva == pytest.approx(0.10)
    assert extranjero.tasa_efectiva > 0.28
    assert extranjero.impuesto > sic.impuesto * 2.5


def test_alerta_de_estate_tax():
    debajo = alerta_estate_tax(50_000.0)
    assert not debajo.activa

    arriba = alerta_estate_tax(500_000.0)
    assert arriba.activa
    assert arriba.exposicion_estimada == pytest.approx((500_000 - UMBRAL_ESTATE_TAX_USD) * 0.40)
    assert "sin tratado sucesorio" in arriba.mensaje


def test_isr_de_arrendamiento_en_los_dos_casos():
    """La renta como único ingreso paga ~5%; apilada sobre sueldo, marginal de 30–35%."""
    renta = 264_000.0
    solo = isr_arrendamiento(renta, predial_anual=9_000.0)
    apilada = isr_arrendamiento(renta, predial_anual=9_000.0, ingreso_por_sueldo=900_000.0)

    assert solo.tasa_efectiva < 0.08, f"Tasa efectiva {solo.tasa_efectiva:.2%}, se esperaba ~5%."
    assert apilada.tasa_efectiva > solo.tasa_efectiva * 2.5
    assert apilada.detalle["marginal_aplicable"] >= 0.30
    assert "único ingreso" in solo.modalidad
    assert "apilada sobre sueldo" in apilada.modalidad


def test_deduccion_ciega_del_treinta_y_cinco():
    resultado = isr_arrendamiento(100_000.0, predial_anual=5_000.0)
    assert resultado.deducciones == pytest.approx(40_000.0)
    assert resultado.base_gravable == pytest.approx(60_000.0)


def test_tarifa_isr_es_progresiva():
    assert tasa_efectiva_isr(100_000.0) < tasa_efectiva_isr(1_000_000.0)
    assert tasa_marginal_isr(5_000_000.0) == pytest.approx(0.35)


# --------------------------------------------------------------------------------------
# Inmueble CDMX
# --------------------------------------------------------------------------------------


def _inmueble() -> SupuestosInmueble:
    return SupuestosInmueble(precio=4_500_000.0, renta_mensual=22_000.0)


def test_los_gastos_se_comen_un_tercio_de_la_renta():
    """13% mantenimiento + 4% vacancia + 3% predial y seguro + 13% CapEx = 33%."""
    sup = _inmueble()
    assert sup.gastos_pct_renta == pytest.approx(0.33)
    operacion = operacion_anual(sup)
    assert operacion.noi_antes_isr / operacion.renta_bruta == pytest.approx(0.67)


def test_el_rendimiento_neto_cae_al_rango_documentado():
    """Bruto 5–7%, neto antes de ISR ≈4% sobre el precio."""
    sup = _inmueble()
    assert 0.05 <= sup.rendimiento_bruto <= 0.07
    operacion = operacion_anual(sup)
    neto_antes_isr = operacion.noi_antes_isr / sup.precio
    assert neto_antes_isr == pytest.approx(0.040, abs=0.005)


def test_los_costos_de_entrada_estan_en_el_rango():
    sup = _inmueble()
    assert 0.06 <= sup.costos_entrada_pct <= 0.08


def test_la_friccion_de_transaccion_ronda_doce_por_ciento():
    resultado = evaluar_inmueble(_inmueble())
    assert 0.09 <= resultado.friccion_transaccion <= 0.14
    assert resultado.isr_salida_pct > 0, "El ISR sobre la ganancia se reporta por separado."


def test_el_carry_apalancado_es_negativo():
    sup = SupuestosInmueble(
        precio=4_500_000.0, renta_mensual=22_000.0,
        monto_hipoteca=2_500_000.0, tasa_hipoteca=0.115,
    )
    carry = diagnosticar_carry(sup)
    assert carry.es_negativo
    assert carry.carry < -0.04
    assert "posición corta en pesos nominales" not in carry.mensaje  # el texto usa otra redacción
    assert "apuesta a la inflación" in carry.mensaje
    assert carry.valor_presente_erosion > 0, (
        "El único argumento del apalancamiento es la erosión de la deuda: hay que cuantificarla."
    )


def test_el_escenario_de_inquilino_moroso_se_cuantifica():
    escenario = escenario_inquilino_moroso(_inmueble(), meses_sin_ingreso=18)
    assert escenario.impacto_flujo < 0
    # 18 meses de renta más gastos y costos legales.
    assert abs(escenario.impacto_flujo) > 22_000 * 18
    assert "años de renta bruta" in escenario.descripcion


def test_el_solver_de_plusvalia_encuentra_el_empate():
    sup = _inmueble()
    plusvalia = plusvalia_necesaria_para_empatar(sup, yield_neto_reits=0.042)
    assert plusvalia is not None

    ajustado = SupuestosInmueble(**{**sup.__dict__, "plusvalia_anual": plusvalia})
    comparativo = comparar_con_reits(ajustado, yield_neto_reits=0.042)
    assert comparativo.npv_inmueble == pytest.approx(comparativo.npv_reits, rel=1e-3), (
        "A la plusvalía de empate, ambos NPV tienen que coincidir."
    )


def test_las_horas_propias_van_a_costo_cero_y_se_declara():
    resultado = evaluar_inmueble(_inmueble())
    assert any("costo cero" in a for a in resultado.advertencias)
    assert any("precios de anuncio" in a for a in resultado.advertencias)
