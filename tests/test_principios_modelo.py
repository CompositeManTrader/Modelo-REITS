"""Pruebas de los principios restantes: P3, P4, P5, P10 y las tres puertas.

Cada principio no negociable tiene aquí una prueba que falla si se viola.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.config import UMBRALES
from src.modelo.cascada import CLAVES_TRAMPA, calcular_cascada, razon_utilidad_neta_a_affo
from src.modelo.kill import (
    BRECHA_PERCENTIL_MINIMA,
    evaluar_kill,
    evaluar_rotacion,
    liston_de_friccion,
    tabla_liston_friccion,
)
from src.modelo.senal import (
    Accion,
    ComparacionInvalida,
    Luz,
    calcular_prima,
    comparar_emisores,
    comparar_yields_crudos,
    evaluar_semaforo,
    percentil_expandible,
    puerta_calidad,
    puerta_valuacion,
)
from src.modelo.valuacion import (
    InsumosValuacion,
    calcular_nav,
    cap_rate_implicito,
    payout_affo,
    payout_utilidad_neta,
    spread_de_inversion,
    valor_empresa_ajustado,
)

M = 1_000_000.0


# --------------------------------------------------------------------------------------
# P3 — El AFFO es el número
# --------------------------------------------------------------------------------------


def test_el_payout_sobre_utilidad_neta_y_sobre_affo_dan_respuestas_opuestas():
    """El caso documentado de Realty Income Q2 2026, con sus cifras.

    Utilidad neta por acción 0.37, AFFO por acción 1.09. Payout sobre utilidad
    neta 222%, sobre AFFO 73%. Mismo dividendo, dos conclusiones opuestas: una
    dice que el dividendo es insostenible y la otra que está bien cubierto.
    """
    ins = InsumosValuacion(
        ticker="O", precio=57.42, acciones_diluidas=900 * M,
        affo_por_accion_ttm=4.36,          # 1.09 x 4
        utilidad_neta_ttm=0.37 * 4 * 900 * M,
        dividendo_ttm_por_accion=3.24,
    )
    p_affo = payout_affo(ins)
    p_neta = payout_utilidad_neta(ins)

    assert p_affo == pytest.approx(0.743, abs=0.01)
    assert p_neta == pytest.approx(2.19, abs=0.05)
    assert p_affo < UMBRALES.calidad.payout_affo_max < p_neta, (
        "Sobre AFFO el dividendo pasa la Puerta 1; sobre utilidad neta la reprobaría. "
        "Esa es la diferencia entre usar el número correcto y el que publican los sitios."
    )
    assert razon_utilidad_neta_a_affo(0.37, 1.09) == pytest.approx(2.95, abs=0.05)


def test_las_tres_trampas_estan_marcadas():
    """Renta en línea recta, CapEx de mantenimiento y revaluación a valor razonable."""
    assert CLAVES_TRAMPA == frozenset(
        {"renta_linea_recta", "capex_mantenimiento", "revaluacion_valor_razonable",
         "comisiones_arrendamiento"}
    )
    assert "renta_linea_recta" in CLAVES_TRAMPA
    assert "capex_mantenimiento" in CLAVES_TRAMPA
    assert "revaluacion_valor_razonable" in CLAVES_TRAMPA


def test_bandera_de_capex_bajo_en_oficinas():
    """Un REIT de oficinas con CapEx bajo 5% del NOI es bandera roja."""
    componentes = {
        "ingreso_rentas": 1_000.0,
        "gastos_operativos_inmueble": 400.0,
        "utilidad_neta": 100.0,
        "depreciacion_inmuebles": 200.0,
        "capex_mantenimiento": 15.0,  # 2.5% de un NOI de 600
    }
    resultado = calcular_cascada(componentes, sector="Oficinas")
    assert any("oficinas" in b.lower() for b in resultado.banderas), resultado.banderas


def test_capex_cero_es_legitimo_en_net_lease():
    """En net lease puro el CapEx lo paga el inquilino: cero no es bandera."""
    componentes = {
        "ingreso_rentas": 1_000.0,
        "gastos_operativos_inmueble": 100.0,
        "utilidad_neta": 300.0,
        "depreciacion_inmuebles": 400.0,
        "capex_mantenimiento": 0.0,
    }
    resultado = calcular_cascada(componentes, sector="Net Lease")
    assert not any("por debajo del piso" in b for b in resultado.banderas)


# --------------------------------------------------------------------------------------
# P4 — Nunca compares niveles de yield entre emisores
# --------------------------------------------------------------------------------------


def test_comparar_niveles_de_yield_es_un_error_de_programa():
    """No es una mala práctica documentada: es una excepción."""
    with pytest.raises(ComparacionInvalida, match="P4"):
        comparar_yields_crudos({"O": 0.055, "GNL": 0.12})


def test_el_percentil_bajo_gana_al_yield_alto():
    """Data centers con 2.5% en el percentil 95 está más barato que oficinas con 9% en el 20."""
    ranking = comparar_emisores(
        {"DATACENTER": 0.95, "OFICINAS": 0.20},
        sectores={"DATACENTER": "Data Centers", "OFICINAS": "Oficinas"},
    )
    assert ranking.iloc[0]["ticker"] == "DATACENTER"
    assert "advertencia" in ranking.attrs


def test_la_prima_se_alinea_hacia_adelante_nunca_hacia_atras():
    """Rellenar la tasa hacia atrás sería meter el futuro por la puerta de servicio."""
    yields = pd.Series(
        [0.06, 0.065],
        index=pd.to_datetime(["2024-03-31", "2024-06-30"]),
    )
    tasas = pd.Series(
        [0.040, 0.045],
        index=pd.to_datetime(["2024-03-15", "2024-06-15"]),
    )
    prima = calcular_prima(yields, tasas)
    assert prima.iloc[0] == pytest.approx(0.06 - 0.040)
    assert prima.iloc[1] == pytest.approx(0.065 - 0.045)

    with pytest.raises(ValueError, match="lookahead"):
        calcular_prima(yields, tasas, metodo="bfill")


# --------------------------------------------------------------------------------------
# P5 — Ventana expandible
# --------------------------------------------------------------------------------------


def test_percentil_expandible_solo_usa_el_pasado():
    serie = pd.Series(
        [0.01] * 12 + [0.10],
        index=pd.date_range("2020-03-31", periods=13, freq="QE"),
    )
    percentil = percentil_expandible(serie, min_observaciones=12)
    # El valor 0.10 es el máximo de su propia historia: percentil máximo.
    assert percentil.iloc[-1] == pytest.approx(1.0 - 0.5 / 13, abs=0.05)


def test_percentil_exige_observaciones_minimas():
    serie = pd.Series(np.arange(8, dtype=float), index=pd.date_range("2020-03-31", periods=8, freq="QE"))
    percentil = percentil_expandible(serie, min_observaciones=12)
    assert percentil.isna().all(), (
        "Un percentil calculado sobre ocho trimestres no es un percentil, es una opinión."
    )


# --------------------------------------------------------------------------------------
# Las tres puertas
# --------------------------------------------------------------------------------------


def _metricas_sanas() -> dict:
    return {
        "payout_affo": 0.73,
        "deuda_neta_ebitdare": 5.4,
        "crecimiento_affo_por_accion_yoy": 0.03,
        "spread_inversion": 0.02,
        "grado_inversion": True,
    }


def test_puerta_de_calidad_es_binaria():
    assert puerta_calidad(_metricas_sanas()).pasa is True

    malas = _metricas_sanas() | {"payout_affo": 0.95}
    resultado = puerta_calidad(malas)
    assert resultado.pasa is False
    assert resultado.luz == Luz.ROJO
    assert "DESCARTADO" in resultado.mensaje


def test_lo_que_falla_calidad_esta_descartado_no_barato():
    """Ningún descuento de valuación rescata a un emisor que reprueba la Puerta 1."""
    malas = _metricas_sanas() | {"deuda_neta_ebitdare": 8.0}
    semaforo = evaluar_semaforo("MAL", dt.date(2026, 6, 30), malas, 0.99, 40, pd.DataFrame())
    assert semaforo.accion == Accion.DESCARTADO, (
        "Percentil de prima en 99 y aun así descartado: eso es lo que significa binaria."
    )


def test_la_puerta_de_valuacion_nunca_vende():
    """Cara contra su propia historia significa NO COMPRAR MÁS, no VENDER."""
    semaforo = evaluar_semaforo(
        "CARO", dt.date(2026, 6, 30), _metricas_sanas(), 0.05, 40, pd.DataFrame()
    )
    assert semaforo.accion == Accion.NO_COMPRAR_MAS
    assert semaforo.accion != Accion.VENDER
    assert "NO justifica vender" in semaforo.explicacion


def test_solo_la_puerta_de_deterioro_vende():
    historial = pd.DataFrame(
        {
            "fecha_dato": pd.date_range("2025-03-31", periods=4, freq="QE"),
            "payout_affo": [0.85, 0.92, 1.04, 1.08],
            "spread_inversion": [0.02, 0.01, -0.005, -0.01],
            "crecimiento_affo_por_accion_yoy": [0.02, 0.00, -0.01, -0.03],
            "deuda_neta_ebitdare": [5.5, 5.8, 6.1, 6.3],
            "grado_inversion": [True, True, True, True],
        }
    )
    resultado = evaluar_kill(historial)
    assert resultado.dispara_venta
    assert "Payout sobre AFFO > 100%" in resultado.disparadores

    semaforo = evaluar_semaforo(
        "ROTO", dt.date(2026, 6, 30), _metricas_sanas(), 0.95, 40, historial
    )
    assert semaforo.accion == Accion.VENDER
    assert "tesis está rota" in semaforo.explicacion


def test_un_solo_trimestre_malo_no_dispara_venta():
    """Los recortes se anuncian después de un patrón, no después de un dato."""
    historial = pd.DataFrame(
        {
            "fecha_dato": pd.date_range("2025-03-31", periods=4, freq="QE"),
            "payout_affo": [0.80, 0.82, 1.05, 0.88],
            "grado_inversion": [True] * 4,
        }
    )
    assert not evaluar_kill(historial).dispara_venta


def test_sin_historia_suficiente_el_veredicto_es_inconcluso():
    resultado = puerta_valuacion(0.9, n_observaciones=6)
    assert resultado.luz == Luz.SIN_DATOS
    assert "INCONCLUSO" in resultado.mensaje

    semaforo = evaluar_semaforo("NUEVO", dt.date(2026, 6, 30), _metricas_sanas(), 0.9, 6, pd.DataFrame())
    assert semaforo.accion == Accion.INCONCLUSO


# --------------------------------------------------------------------------------------
# Valuación: cap rate, NAV y dilución
# --------------------------------------------------------------------------------------


def test_el_ev_resta_los_activos_que_no_generan_renta():
    """Si no se restan, el cap rate implícito sale sesgado a la baja."""
    base = {
        "ticker": "X", "precio": 50.0, "acciones_diluidas": 1_000 * M,
        "noi_anualizado": 4_000 * M, "deuda_total": 20_000 * M, "efectivo": 1_000 * M,
    }
    sin_ajuste = InsumosValuacion(**base)
    con_activos = InsumosValuacion(
        **base, prestamos_por_cobrar=3_000 * M, inversiones_no_consolidadas=1_000 * M
    )
    assert valor_empresa_ajustado(con_activos) < valor_empresa_ajustado(sin_ajuste)
    assert cap_rate_implicito(con_activos) > cap_rate_implicito(sin_ajuste), (
        "Depurar el EV sube el cap rate: el REIT está más barato de lo que parecía."
    )


def test_el_nav_excluye_el_goodwill():
    ins = InsumosValuacion(
        ticker="X", precio=50.0, acciones_diluidas=1_000 * M,
        noi_anualizado=4_000 * M, deuda_total=20_000 * M, efectivo=1_000 * M,
        goodwill=5_000 * M,
    )
    nav = calcular_nav(ins, 0.065)
    esperado = 4_000 * M / 0.065 + 1_000 * M - 20_000 * M
    assert nav.nav_total == pytest.approx(esperado, rel=1e-9)
    assert nav.componentes["goodwill_excluido"] == 0.0


def test_las_unidades_de_op_diluyen():
    """En estructuras UPREIT, ignorarlas sobrestima el AFFO por acción."""
    from src.modelo.valuacion import acciones_totalmente_diluidas

    assert acciones_totalmente_diluidas(900 * M, 100 * M) == 1_000 * M


def test_spread_de_inversion_negativo_destruye_valor():
    assert spread_de_inversion(0.06, 0.07) == pytest.approx(-0.01)
    assert spread_de_inversion(None, 0.07) is None


# --------------------------------------------------------------------------------------
# Fricción de rotación
# --------------------------------------------------------------------------------------


def test_la_tabla_de_friccion_reproduce_los_numeros_del_proyecto():
    """20% de ganancia cuesta 2.0% y exige 100 bps; 100% cuesta 10% y exige 500 bps."""
    tabla = tabla_liston_friccion()
    columna_bps = [c for c in tabla.columns if "bps" in c][0]
    esperados = {0.20: 100, 0.40: 200, 0.60: 300, 1.00: 500}
    for ganancia, bps_esperados in esperados.items():
        fila = tabla[tabla["Ganancia acumulada"] == ganancia].iloc[0]
        assert fila[columna_bps] == bps_esperados


def test_liston_de_friccion_con_comisiones():
    liston = liston_de_friccion(0.40, tasa_impuesto=0.10, comisiones=0.005)
    assert liston.costo_fiscal == pytest.approx(0.045)
    assert liston.ventaja_anual_necesaria == pytest.approx(0.0225)


def test_no_rotar_si_la_brecha_de_percentil_es_chica():
    corta = evaluar_rotacion(0.30, 0.55, ganancia_acumulada=0.40)
    assert not corta.conviene
    assert "No rotar" in corta.mensaje

    amplia = evaluar_rotacion(0.20, 0.85, ganancia_acumulada=0.40)
    assert amplia.conviene
    assert amplia.brecha_percentil >= BRECHA_PERCENTIL_MINIMA
    assert "próxima aportación" in amplia.mensaje, (
        "Aun cuando conviene rotar, hay que recordar que el dinero nuevo no paga impuestos."
    )


# --------------------------------------------------------------------------------------
# P10 — El benchmark es el Udibono
# --------------------------------------------------------------------------------------


def test_el_modelo_dice_cuando_el_sin_riesgo_gana():
    from src.simulacion.escenarios import comparar_contra_udibono

    comparacion = comparar_contra_udibono(
        yield_reits_bruto=0.055, crecimiento_esperado=0.020,
        inflacion_esperada=0.045, tasa_udibono_real=0.047,
    )
    assert comparacion.el_sin_riesgo_gana
    assert "EL ACTIVO SIN RIESGO PAGA MÁS QUE EL ACTIVO CON RIESGO" in comparacion.mensaje


def test_con_prima_suficiente_el_mensaje_cambia():
    from src.simulacion.escenarios import comparar_contra_udibono

    comparacion = comparar_contra_udibono(
        yield_reits_bruto=0.085, crecimiento_esperado=0.035,
        inflacion_esperada=0.040, tasa_udibono_real=0.040,
    )
    assert not comparacion.el_sin_riesgo_gana
    assert comparacion.brecha > 0
    assert "prima" in comparacion.mensaje


def test_la_comparacion_es_despues_de_impuestos():
    """Comparar un yield bruto contra una tasa de bono es comparar peras con manzanas."""
    from src.fiscal.mexico import rendimiento_real_despues_de_impuestos

    detalle = rendimiento_real_despues_de_impuestos(0.055, 0.02, 0.045)
    assert detalle["yield_neto"] == pytest.approx(0.055 * 0.80)
    assert detalle["real_despues_de_impuestos"] < detalle["nominal_despues_de_impuestos"]


def test_la_puerta_de_calidad_no_aprueba_por_falta_de_datos():
    """Un criterio que no falla porque no se pudo medir no es un criterio aprobado.

    Es la tentación más fácil del sistema: con tres de cinco criterios en blanco,
    los dos que quedan pasan y la puerta diría VERDE. Eso convertiría «no sé» en
    «aprobado», que es lo contrario de lo que el proyecto exige en todos lados.
    """
    casi_vacio = {"payout_affo": 0.73, "deuda_neta_ebitdare": 5.4}
    resultado = puerta_calidad(casi_vacio)
    assert resultado.pasa is None
    assert resultado.luz == Luz.SIN_DATOS
    assert "INCONCLUSO" in resultado.mensaje

    semaforo = evaluar_semaforo("SINDATOS", dt.date(2026, 6, 30), casi_vacio, 0.95, 40, pd.DataFrame())
    assert semaforo.accion == Accion.INCONCLUSO, (
        "Percentil de prima en 95 y aun así INCONCLUSO: sin calidad verificable no hay compra."
    )


def test_con_datos_suficientes_la_puerta_si_dictamina():
    """El umbral no puede volver la puerta inservible: con tres criterios ya opina."""
    con_tres = {
        "payout_affo": 0.73,
        "deuda_neta_ebitdare": 5.4,
        "crecimiento_affo_por_accion_yoy": 0.03,
    }
    resultado = puerta_calidad(con_tres)
    assert resultado.pasa is True
    assert resultado.luz == Luz.VERDE

    reprobado = con_tres | {"payout_affo": 0.97}
    assert puerta_calidad(reprobado).pasa is False, (
        "Un solo criterio reprobado descarta, aunque los demás pasen."
    )
