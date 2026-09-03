"""Pruebas obligatorias 7 y 8 — Control negativo y lag de ejecución.

7. Correr la señal sobre datos sintéticos **sin edge plantado**. Si la maquinaria
   reporta edge, está alucinando y el build falla.
8. La señal de ``t`` se ejecuta en ``t+1``, verificado por igualdad con la serie
   desplazada.

Sobre la prueba 7
-----------------
Se usan semillas fijas, así que el resultado es determinista y reproducible. La
prueba mide dos cosas distintas:

* Que ninguna corrida sobre ruido puro produzca GO.
* Que el control **positivo** — con un edge genuinamente plantado — sí lo
  produzca. Sin esa segunda mitad, un sistema que siempre dijera NO-GO pasaría
  la prueba pareciendo riguroso cuando en realidad solo está roto.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config import MIN_APUESTAS_EFECTIVAS
from src.portafolio.metricas import tir
from src.simulacion.backtest import (
    Veredicto,
    aplicar_lag,
    backtest_regla_de_aportacion,
    backtest_regla_de_posicion,
    contar_apuestas,
    contar_episodios,
    dictaminar,
    generar_serie_con_edge,
    generar_serie_sin_edge,
    neutralizar_beta,
    verificar_lag,
)

SEMILLAS = tuple(range(30))


# --------------------------------------------------------------------------------------
# Prueba 7 — Control negativo
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("motor", [backtest_regla_de_aportacion, backtest_regla_de_posicion])
def test_control_negativo_nunca_reporta_edge(motor):
    """Sobre ruido puro, la maquinaria no puede decir GO en ninguna semilla."""
    veredictos = []
    for semilla in SEMILLAS:
        retornos, senal = generar_serie_sin_edge(240, semilla=semilla)
        veredictos.append(dictaminar(motor(retornos, senal)).veredicto)

    gos = [v for v in veredictos if v == Veredicto.GO]
    assert not gos, (
        f"{len(gos)} de {len(SEMILLAS)} corridas sobre datos SIN edge reportaron GO. "
        "La maquinaria está alucinando un edge que no existe."
    )


def test_control_positivo_si_detecta_un_edge_plantado():
    """La contraparte obligatoria: si nunca dice GO, la prueba anterior no vale nada."""
    gos = 0
    for semilla in range(10):
        retornos, senal = generar_serie_con_edge(240, semilla=semilla, fuerza=0.6)
        if dictaminar(backtest_regla_de_posicion(retornos, senal)).veredicto == Veredicto.GO:
            gos += 1
    assert gos >= 7, (
        f"Solo {gos} de 10 corridas con edge PLANTADO dieron GO. Un sistema que no detecta "
        "lo que sí está ahí no es riguroso: está roto."
    )


def test_el_control_negativo_es_determinista():
    """Mismas semillas, mismo resultado. Si no, la prueba no significa nada en CI."""
    def correr():
        retornos, senal = generar_serie_sin_edge(240, semilla=7)
        resultado = backtest_regla_de_posicion(retornos, senal)
        return (resultado.apuestas.episodios, round(resultado.neutralizacion.beta, 10))

    assert correr() == correr()


def test_sin_apuestas_suficientes_el_veredicto_es_inconcluso_nunca_go():
    """Una señal lenta produce pocos episodios: el veredicto tiene que ser INCONCLUSO."""
    fechas = pd.date_range("2005-01-31", periods=240, freq="ME")
    rng = np.random.default_rng(3)
    retornos = pd.Series(rng.normal(0.008, 0.05, 240), index=fechas)

    # Señal de valuación lenta: cambia de régimen unas pocas veces en veinte años.
    senal = pd.Series(0.2, index=fechas)
    senal.iloc[60:100] = 0.9
    senal.iloc[150:190] = 0.9

    resultado = backtest_regla_de_posicion(retornos, senal)
    assert resultado.apuestas.episodios < MIN_APUESTAS_EFECTIVAS
    dictamen = dictaminar(resultado)
    assert dictamen.veredicto == Veredicto.INCONCLUSO
    assert "INCONCLUSO" in dictamen.como_texto()


def test_conteo_de_episodios_no_cuenta_observaciones():
    """Entrar sobreponderado y quedarse doce meses es UNA apuesta, no doce."""
    fechas = pd.date_range("2020-01-31", periods=36, freq="ME")
    posicion = pd.Series(0.5, index=fechas)
    posicion.iloc[6:18] = 1.0     # un episodio sobreponderado de doce meses
    posicion.iloc[24:30] = 0.1    # un episodio subponderado de seis meses

    assert contar_episodios(posicion, 0.5) == 2

    conteo = contar_apuestas(posicion, 0.5)
    assert conteo.episodios == 2
    assert conteo.observaciones == 36
    assert not conteo.suficiente
    assert "INCONCLUSO" in conteo.como_texto()


def test_ruido_si_produce_muchos_episodios():
    """El conteo no es un filtro contra el ruido: para eso está la neutralización de beta.

    Una señal que cambia de lado cada mes SÍ hace muchas apuestas. Quien tiene que
    atraparla es P8, no P7. Confundir las dos defensas deja un hueco.
    """
    _, senal = generar_serie_sin_edge(240, semilla=1)
    ejecutada = aplicar_lag(senal).fillna(0.5)
    assert contar_apuestas(ejecutada, "mediana").episodios > 80


# --------------------------------------------------------------------------------------
# P8 — Neutralización de beta
# --------------------------------------------------------------------------------------


def test_neutralizar_beta_baja_el_sharpe_de_una_regla_sin_senal():
    """Desplegar más capital en un activo con deriva da Sharpe positivo sin señal alguna.

    Se construye el caso puro: la posición es una función del retorno REZAGADO del
    propio activo, sin ninguna información. El Sharpe crudo se ve bien; el
    neutralizado se desploma.
    """
    fechas = pd.date_range("2005-01-31", periods=240, freq="ME")
    rng = np.random.default_rng(11)
    retornos = pd.Series(rng.normal(0.010, 0.045, 240), index=fechas)

    # Regla puramente direccional: más exposición tras un mes bueno.
    posicion = (retornos.shift(1) > 0).astype(float) * 2.0
    activo = (posicion * retornos).dropna()

    resultado = neutralizar_beta(activo, retornos.reindex(activo.index))
    assert resultado is not None
    assert resultado.beta > 0.5, "La regla es direccional: su beta tiene que ser alta."
    assert resultado.sharpe_neutralizado < resultado.sharpe_crudo, (
        "Neutralizar tiene que quitarle al Sharpe lo que venía de la exposición direccional."
    )


def test_neutralizacion_usa_errores_hac():
    """El retorno activo es autocorrelado; con errores OLS simples el alfa se infla."""
    fechas = pd.date_range("2005-01-31", periods=240, freq="ME")
    rng = np.random.default_rng(5)
    subyacente = pd.Series(rng.normal(0.008, 0.04, 240), index=fechas)
    # Retorno activo muy persistente y de media cero.
    ruido = rng.normal(0, 0.01, 240)
    persistente = pd.Series(ruido, index=fechas).rolling(12, min_periods=1).mean()

    resultado = neutralizar_beta(persistente, subyacente)
    assert resultado is not None
    assert resultado.p_valor_alfa > 0.01, (
        "Con errores HAC, un alfa de media cero y muy autocorrelada no debe salir "
        "significativa al 1%."
    )


# --------------------------------------------------------------------------------------
# Prueba 8 — Lag de ejecución
# --------------------------------------------------------------------------------------


def test_la_senal_de_t_se_ejecuta_en_t_mas_uno():
    fechas = pd.date_range("2020-01-31", periods=24, freq="ME")
    senal = pd.Series(np.arange(24, dtype=float), index=fechas)
    ejecutada = aplicar_lag(senal)

    pd.testing.assert_series_equal(ejecutada, senal.shift(1))
    assert pd.isna(ejecutada.iloc[0]), "El primer periodo no puede tener señal ejecutada."
    assert ejecutada.iloc[5] == senal.iloc[4]
    assert verificar_lag(senal, ejecutada)


def test_ejecutar_sin_lag_se_detecta():
    fechas = pd.date_range("2020-01-31", periods=24, freq="ME")
    senal = pd.Series(np.arange(24, dtype=float), index=fechas)
    assert not verificar_lag(senal, senal), "Ejecutar la señal el mismo día es lookahead."


def test_lag_cero_o_negativo_es_un_error():
    senal = pd.Series([1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="al menos un periodo"):
        aplicar_lag(senal, 0)


def test_el_backtest_aplica_el_lag_internamente():
    """La posición ejecutada del backtest tiene que ser la señal desplazada, no la señal."""
    retornos, senal = generar_serie_sin_edge(120, semilla=2)
    resultado = backtest_regla_de_posicion(retornos, senal, posicion_max=1.0)

    esperada = aplicar_lag(senal.clip(0, 1)).fillna(0.0)
    reconstruida = (resultado.riqueza_estrategia.pct_change() / retornos).dropna()
    comun = reconstruida.index.intersection(esperada.index)
    # Se compara la exposición implícita periodo a periodo contra la señal desplazada.
    diferencias = (reconstruida.reindex(comun) - esperada.reindex(comun)).abs()
    assert float(diferencias.max()) < 1e-6, (
        "La exposición implícita del backtest no coincide con la señal desplazada un periodo."
    )


# --------------------------------------------------------------------------------------
# P6 y P9 — Benchmark y TIR
# --------------------------------------------------------------------------------------


def test_el_benchmark_es_el_mismo_activo():
    retornos, senal = generar_serie_sin_edge(120, semilla=4)

    posicion = backtest_regla_de_posicion(retornos, senal)
    assert "MISMO papel" in posicion.descripcion_benchmark
    esperado = (1.0 + retornos).cumprod()
    pd.testing.assert_series_equal(
        posicion.riqueza_benchmark, esperado, check_names=False,
        obj="El benchmark de una regla de posición es comprar y mantener el mismo papel.",
    )

    aportacion = backtest_regla_de_aportacion(retornos, senal)
    assert "constante al MISMO papel" in aportacion.descripcion_benchmark


def test_la_tir_compara_estrategias_con_distinto_despliegue_de_capital():
    """Comparar riqueza final entre flujos desiguales es incorrecto; la TIR sí sirve (P9)."""
    fechas = pd.to_datetime(["2020-01-01", "2021-01-01", "2022-01-01"])

    # Despliega el doble de capital y termina con más riqueza, pero al mismo rendimiento.
    chica = pd.Series([-1_000.0, 0.0, 1_210.0], index=fechas)
    grande = pd.Series([-2_000.0, 0.0, 2_420.0], index=fechas)

    assert grande.iloc[-1] > chica.iloc[-1], "La grande termina con más dinero."
    assert tir(chica) == pytest.approx(tir(grande), abs=1e-6), (
        "Pero rinden lo mismo. Por eso el veredicto se decide por TIR y no por riqueza final."
    )


def test_la_tir_penaliza_el_mal_timing():
    """Dos estrategias con el mismo capital total y distinto timing dan TIR distinta."""
    fechas = pd.to_datetime(["2020-01-01", "2021-01-01", "2022-01-01"])
    temprano = pd.Series([-2_000.0, 0.0, 2_420.0], index=fechas)
    tardio = pd.Series([-1_000.0, -1_000.0, 2_320.0], index=fechas)

    assert tir(temprano) != pytest.approx(tir(tardio), abs=1e-4)
