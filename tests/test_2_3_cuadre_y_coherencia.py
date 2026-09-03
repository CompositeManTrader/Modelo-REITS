"""Pruebas obligatorias 2 y 3 — Cuadre del AFFO y coherencia temporal.

2. El AFFO recalculado desde los componentes tiene que atar contra el reportado.
3. ``H1 = Q1 + Q2`` y ``FY = Q1 + Q2 + Q3 + Q4``.

La prueba de cuadre corre contra el **Exhibit 99.1 real** de Realty Income, no
contra una maqueta. Una maqueta confirma lo que el parser ya hace; un documento
que la SEC efectivamente publicó es lo que encuentra los errores.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.ingesta.parser_affo import parsear_conciliacion, reconstruir_trimestres
from src.modelo.cascada import MAGNITUD, REPORTE, calcular_cascada, coherencia_temporal
from src.validacion.cuadre import (
    cuadrar_affo,
    cuadrar_conciliacion,
    elegir_mejor_conciliacion,
    prueba_suavidad_consenso,
    validar_coherencia_temporal,
    validar_rangos,
)

# --------------------------------------------------------------------------------------
# Prueba 2 — Cuadre contra el filing real
# --------------------------------------------------------------------------------------


def test_cuadre_contra_el_8k_real(html_8k_realty, fecha_publicacion_8k):
    """Cada periodo del Exhibit 99.1 cuadra contra los subtotales del emisor.

    No se compara contra un número que nosotros elegimos: se compara la suma de
    las partidas contra el subtotal que Realty Income publicó. Si el parser
    pierde una fila o le cambia el signo, esto falla.
    """
    extracciones = elegir_mejor_conciliacion(
        parsear_conciliacion(html_8k_realty, "O", fecha_publicacion_8k, "fixture")
    )
    assert extracciones, "El parser no extrajo ningún periodo del filing real."

    fallidos = []
    for e in extracciones:
        resultado = cuadrar_conciliacion(e.lineas, e.orden)
        if not resultado.cuadra:
            fallidos.append(f"{e.periodo.etiqueta}: {resultado.motivo}")
    assert not fallidos, "Periodos que no cuadran:\n" + "\n".join(fallidos)


def test_el_cuadre_verifica_algo_de_verdad(html_8k_realty, fecha_publicacion_8k):
    """Un cuadre sin partidas verificables no es un cuadre.

    Sin esta prueba, ``cuadrar_conciliacion`` podría pasar siempre simplemente
    porque ningún tramo tiene partidas que sumar.
    """
    extracciones = elegir_mejor_conciliacion(
        parsear_conciliacion(html_8k_realty, "O", fecha_publicacion_8k, "fixture")
    )
    verificados = 0
    for e in extracciones:
        resultado = cuadrar_conciliacion(e.lineas, e.orden)
        verificados += len(resultado.tramos_verificados)
    assert verificados >= len(extracciones), (
        "Cada periodo debe tener al menos un tramo con partidas itemizadas; "
        "si no, el cuadre está pasando en vacío."
    )


def test_el_cuadre_detecta_una_linea_alterada(html_8k_realty, fecha_publicacion_8k):
    """Control positivo del cuadre: si se altera una partida, tiene que fallar."""
    extracciones = elegir_mejor_conciliacion(
        parsear_conciliacion(html_8k_realty, "O", fecha_publicacion_8k, "fixture")
    )
    objetivo = next(
        e for e in extracciones
        if cuadrar_conciliacion(e.lineas, e.orden).tramos_verificados
    )
    tramo = cuadrar_conciliacion(objetivo.lineas, objetivo.orden).tramos_verificados[0]
    partida = tramo.partidas[0]

    alteradas = dict(objetivo.lineas)
    alteradas[partida] = alteradas[partida] * 1.5 + 1_000_000.0
    resultado = cuadrar_conciliacion(alteradas, objetivo.orden)
    assert not resultado.cuadra, (
        f"Alterar '{partida}' no rompió el cuadre: la validación no está verificando nada."
    )


def test_razon_affo_contra_utilidad_neta_del_filing_real(html_8k_realty, fecha_publicacion_8k):
    """P3 con números reales: Q2 2026 da AFFO 1.09 contra utilidad neta 0.37.

    Es la razón de 2.97x documentada. Si el parser confundiera el trimestre con el
    semestre, o la utilidad neta con la del año, este número se movería.
    """
    extracciones = elegir_mejor_conciliacion(
        parsear_conciliacion(html_8k_realty, "O", fecha_publicacion_8k, "fixture")
    )
    q2 = [
        e for e in extracciones
        if e.periodo.tipo == "Q" and e.periodo.fin == dt.date(2026, 6, 30)
        and "affo_por_accion" in e.lineas and "utilidad_neta_por_accion" in e.lineas
    ]
    assert q2, "No se encontró el trimestre con magnitudes por acción."
    e = q2[0]
    assert e.lineas["affo_por_accion"] == pytest.approx(1.09, abs=0.01)
    assert e.lineas["utilidad_neta_por_accion"] == pytest.approx(0.37, abs=0.01)
    razon = e.lineas["affo_por_accion"] / e.lineas["utilidad_neta_por_accion"]
    assert razon == pytest.approx(2.95, abs=0.10), (
        f"La razón AFFO/utilidad neta salió {razon:.2f}; se esperaba ~2.97x."
    )


def test_cuadre_por_taxonomia_con_convenciones_de_signo():
    """Las dos convenciones de signo dan el mismo AFFO cuando se usan bien.

    Y dan resultados distintos cuando se confunden, que es el punto: el error es
    de exactamente el doble de cada partida negativa.
    """
    magnitudes = {
        "utilidad_neta": 100.0,
        "depreciacion_inmuebles": 250.0,
        "ganancia_venta_inmuebles": 40.0,      # magnitud positiva; la cascada resta
        "renta_linea_recta": 30.0,             # magnitud positiva; la cascada resta
        "amortizacion_costos_financieros": 10.0,
    }
    reporte = {
        "utilidad_neta": 100.0,
        "depreciacion_inmuebles": 250.0,
        "ganancia_venta_inmuebles": -40.0,     # como lo presenta el emisor
        "renta_linea_recta": -30.0,
        "amortizacion_costos_financieros": 10.0,
    }
    esperado = 100 + 250 - 40 - 30 + 10  # 290

    assert calcular_cascada(magnitudes, signos=MAGNITUD).affo == pytest.approx(esperado)
    assert calcular_cascada(reporte, signos=REPORTE).affo == pytest.approx(esperado)

    # Confundirlas: cada partida negativa se cuenta al revés.
    confundido = calcular_cascada(reporte, signos=MAGNITUD).affo
    assert confundido == pytest.approx(esperado + 2 * (40 + 30))


def test_registro_que_no_cuadra_queda_sospechoso():
    componentes = {
        "utilidad_neta": 100.0,
        "depreciacion_inmuebles": 250.0,
        "renta_linea_recta": 30.0,
    }
    resultado = cuadrar_affo(componentes, affo_reportado=999.0, signos=MAGNITUD)
    assert not resultado.cuadra
    assert resultado.estado == "sospechoso"
    assert "Diferencia" in resultado.motivo


def test_cuadre_tolera_el_redondeo_del_emisor():
    """En cifras de millones, el emisor redondea cada línea antes de sumar."""
    componentes = {"utilidad_neta": 100_000_000.0, "depreciacion_inmuebles": 250_000_000.0}
    resultado = cuadrar_affo(componentes, affo_reportado=350_050_000.0, signos=MAGNITUD)
    assert resultado.cuadra, "Una diferencia de 0.014% es redondeo, no un error."


# --------------------------------------------------------------------------------------
# Prueba 3 — Coherencia temporal
# --------------------------------------------------------------------------------------


def test_h1_igual_a_q1_mas_q2_y_fy_igual_a_la_suma():
    serie = pd.Series(
        [1.00, 1.05, 1.08, 1.12],
        index=pd.to_datetime(["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"]),
    )
    acumulados = {"2024-H1": 2.05, "2024-FY": 4.25}
    resultado = validar_coherencia_temporal(serie, acumulados)
    assert resultado.coherente, resultado.motivo
    assert len(resultado.verificaciones) == 2


def test_incoherencia_temporal_se_detecta():
    serie = pd.Series(
        [1.00, 1.05, 1.08, 1.12],
        index=pd.to_datetime(["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"]),
    )
    resultado = validar_coherencia_temporal(serie, {"2024-H1": 2.40})
    assert not resultado.coherente
    assert "Incoherencia temporal" in resultado.motivo


def test_coherencia_temporal_directa():
    salida = coherencia_temporal({"Q1": 1.0, "Q2": 1.1, "Q3": 1.2, "Q4": 1.3,
                                  "H1": 2.1, "FY": 4.6})
    assert salida["cuadra_h1"] and salida["cuadra_fy"]

    mala = coherencia_temporal({"Q1": 1.0, "Q2": 1.1, "H1": 2.5})
    assert not mala["cuadra_h1"]


# --------------------------------------------------------------------------------------
# Reconstrucción de trimestres
# --------------------------------------------------------------------------------------


def test_reconstruccion_q1_y_q3():
    """``Q1 = H1 − Q2`` y ``Q3 = FY − H1 − Q4``, con fecha de publicación máxima."""
    obs = {
        "Q2": (1.05, dt.date(2024, 8, 5)),
        "H1": (2.05, dt.date(2024, 8, 5)),
        "Q4": (1.12, dt.date(2025, 2, 20)),
        "FY": (4.25, dt.date(2025, 2, 20)),
    }
    salida = reconstruir_trimestres(obs)

    assert salida["Q1"][0] == pytest.approx(1.00)
    assert salida["Q1"][1] == dt.date(2024, 8, 5)
    assert salida["Q3"][0] == pytest.approx(4.25 - 2.05 - 1.12)
    assert salida["Q3"][1] == dt.date(2025, 2, 20)


def test_reconstruccion_usa_la_publicacion_mas_tardia():
    """Antes de la publicación más tardía, el trimestre derivado no era deducible."""
    obs = {"Q2": (1.05, dt.date(2024, 8, 5)), "H1": (2.05, dt.date(2024, 11, 30))}
    salida = reconstruir_trimestres(obs)
    assert salida["Q1"][1] == dt.date(2024, 11, 30)


def test_no_reconstruye_lo_que_ya_existe():
    obs = {"Q1": (0.99, dt.date(2024, 5, 5)), "Q2": (1.05, dt.date(2024, 8, 5)),
           "H1": (2.05, dt.date(2024, 8, 5))}
    assert "Q1" not in reconstruir_trimestres(obs)


# --------------------------------------------------------------------------------------
# Rangos razonables y suavidad del consenso
# --------------------------------------------------------------------------------------


def test_rangos_razonables():
    assert validar_rangos({"payout_affo": 0.73, "ocupacion": 0.98, "ltv": 0.42}) == []
    problemas = validar_rangos({"payout_affo": 2.5, "ocupacion": 1.4, "ltv": -0.1})
    assert len(problemas) == 3


def test_serie_de_consenso_sospechosamente_lisa():
    """Una serie de consenso real salta en las fechas de reporte. Si no, es la reexpresada.

    Lo que se mide es concentración: si los cambios en las fechas de reporte no
    son mayores que los de cualquier otro día, la serie no distingue el evento
    que debería moverla.
    """
    fechas = pd.date_range("2020-01-31", periods=48, freq="ME")
    reportes = pd.to_datetime(
        ["2020-05-31", "2020-08-31", "2020-11-30", "2021-02-28",
         "2021-05-31", "2021-08-31", "2021-11-30", "2022-02-28"]
    )

    # Tendencia perfectamente uniforme: no distingue los reportes de nada.
    lisa = pd.Series([3.0 + 0.01 * i for i in range(48)], index=fechas)
    resultado = prueba_suavidad_consenso(lisa, reportes)
    assert resultado.sospechosa, resultado.motivo
    assert resultado.razon_concentracion < 2.0

    # Serie realista: casi plana entre reportes, con revisión al publicarse.
    con_saltos = pd.Series(3.0, index=fechas)
    for f in reportes:
        idx = con_saltos.index.get_indexer([f], method="nearest")[0]
        con_saltos.iloc[idx:] += 0.06
    con_saltos = con_saltos + pd.Series(
        [0.0005 * ((-1) ** i) for i in range(48)], index=fechas
    )
    resultado = prueba_suavidad_consenso(con_saltos, reportes)
    assert not resultado.sospechosa, resultado.motivo
    assert resultado.razon_concentracion >= 2.0
