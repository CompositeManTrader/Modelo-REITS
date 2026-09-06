"""Prueba 16 — Un acumulado no siempre es una suma, y restarlo mal no truena.

Hay TRES clases de partida, no dos, y el modelo confundía dos de ellas:

* **Puntual** — saldo de balance. No se deriva de nada.
* **Flujo** — importe del periodo. El acumulado es la suma, así que ``Q4 = FY − 9M``
  es exacto. Vale también para las cifras POR ACCIÓN.
* **Promedio ponderado** — el conteo de acciones básicas y diluidas. El acumulado
  es el **promedio** del periodo, no la suma.

Restar promedios como si fueran sumas dejó a los **diez** emisores con un cuarto
trimestre de 2025 con acciones NEGATIVAS. Es el peor tipo de defecto que hay en
este proyecto: un conteo negativo le voltea el signo a todo lo que se divide entre
él —AFFO por acción, NAV por acción, P/AFFO— y **ninguna suma lo delata**, porque
la aritmética del renglón cuadra. Lo que está mal es la fórmula, no el renglón.

El segundo bloque cubre lo que ese defecto dejó ver: un hueco de un solo trimestre
en una serie borraba al emisor completo de la pantalla, aunque toda la información
necesaria estuviera en la base. Agree Realty salía en blanco teniendo siete
trimestres de AFFO.

Las cifras son las que Agree Realty (ADC) le reportó a la SEC en 2025.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.ingesta.parser_affo import (
    ConciliacionExtraida,
    Periodo,
    reconstruir_trimestres,
)
from src.ingesta.xbrl import (
    CONCEPTOS_PROMEDIO,
    TRIMESTRES_POR_ACUMULADO,
    derivar_trimestres_desde_acumulados,
)
from src.servicio import _metricas, _ttm
from src.validacion.cuadre import cuadrar_conciliacion, elegir_mejor_conciliacion

# Acciones diluidas de ADC, tal como aparecen en companyfacts.
ADC_Q1, ADC_Q2, ADC_Q3 = 107_547_193.0, 110_377_221.0, 111_511_615.0
ADC_9M, ADC_FY = 109_875_336.0, 111_200_645.0
ADC_Q1_2026 = 120_375_633.0


def _filas(concepto: str, valores: dict[tuple[str, str], float]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "ADC",
                "concepto": concepto,
                "periodo_tipo": tipo,
                "fecha_dato": fecha,
                "fecha_publicacion": fecha,
                "valor": valor,
                "unidad": "USD",
                "fuente": "SEC-XBRL",
                "es_primario": True,
            }
            for (tipo, fecha), valor in valores.items()
        ]
    )


# --------------------------------------------------------------------------------------
# 16.1 El promedio se lleva a total antes de restar
# --------------------------------------------------------------------------------------


def test_el_conteo_de_acciones_derivado_es_positivo_y_plausible():
    """La prueba que el defecto habría reprobado.

    Con la resta simple daba −218 millones. Con la fórmula correcta tiene que
    caer **entre** el trimestre anterior y el siguiente, porque ADC estuvo
    emitiendo acciones todo el año.
    """
    derivado = derivar_trimestres_desde_acumulados(
        _filas(
            "acciones_diluidas",
            {
                ("Q", "2025-03-31"): ADC_Q1,
                ("Q", "2025-06-30"): ADC_Q2,
                ("Q", "2025-09-30"): ADC_Q3,
                ("9M", "2025-09-30"): ADC_9M,
                ("FY", "2025-12-31"): ADC_FY,
            },
        ),
        "acciones_diluidas",
    )
    assert len(derivado) == 1
    q4 = float(derivado["valor"].iloc[0])

    assert q4 > 0, f"conteo de acciones negativo: {q4:,.0f}"
    assert ADC_Q3 < q4 < ADC_Q1_2026, (
        f"el Q4 derivado ({q4:,.0f}) no cae entre el Q3 real ({ADC_Q3:,.0f}) y el "
        f"Q1 del año siguiente ({ADC_Q1_2026:,.0f})"
    )
    # La identidad: Q4 = 4·FY − (Q1+Q2+Q3).
    assert q4 == pytest.approx(4 * ADC_FY - (ADC_Q1 + ADC_Q2 + ADC_Q3))


def test_la_resta_simple_habria_dado_negativo():
    """El control. Sin él, la prueba anterior no demuestra que el arreglo hacía falta."""
    ingenuo = ADC_FY - (ADC_Q1 + ADC_Q2 + ADC_Q3)
    assert ingenuo < 0, "si la resta simple no da negativo, esta prueba no prueba nada"


def test_el_promedio_del_semestre_reproduce_el_segundo_trimestre():
    """Control independiente contra un trimestre que ADC sí reportó.

    Q2 = 2·H1 − Q1. Si la fórmula del promedio es la correcta, tiene que dar el
    Q2 publicado, no un número parecido por casualidad.
    """
    h1 = 108_996_422.0
    derivado = derivar_trimestres_desde_acumulados(
        _filas(
            "acciones_diluidas",
            {("Q", "2025-03-31"): ADC_Q1, ("H1", "2025-06-30"): h1},
        ),
        "acciones_diluidas",
    )
    q2 = float(derivado["valor"].iloc[0])
    # 0.1% de tolerancia: el promedio del emisor pondera por días, no por trimestres.
    assert q2 == pytest.approx(ADC_Q2, rel=0.001)


def test_el_flujo_se_sigue_restando_sin_factor():
    """Un importe sí es aditivo. Multiplicarlo por los trimestres lo cuadruplicaría."""
    derivado = derivar_trimestres_desde_acumulados(
        _filas(
            "affo",
            {
                ("Q", "2025-03-31"): 113_965_000.0,
                ("Q", "2025-06-30"): 117_677_000.0,
                ("Q", "2025-09-30"): 123_115_000.0,
                ("FY", "2025-12-31"): 482_804_000.0,
            },
        ),
        "affo",
    )
    q4 = float(derivado["valor"].iloc[0])
    assert q4 == pytest.approx(482_804_000.0 - (113_965_000 + 117_677_000 + 123_115_000))
    assert q4 == pytest.approx(128_047_000.0)


def test_la_cifra_por_accion_es_un_flujo_no_un_promedio():
    """El AFFO por acción del año es la suma de los cuatro trimestres.

    Es exactamente el trimestre que le faltaba a ADC. Se verifica contra el dato
    del emisor: el Q3 reconstruido tiene que coincidir con el AFFO del trimestre
    dividido entre las acciones de ese trimestre, que es otra ruta al mismo número.
    """
    assert not any(c.endswith("_por_accion") for c in CONCEPTOS_PROMEDIO)
    derivado = reconstruir_trimestres(
        {
            "Q2": (1.06, dt.date(2025, 7, 22)),
            "Q4": (1.11, dt.date(2026, 2, 18)),
            "H1": (2.12, dt.date(2025, 7, 22)),
            "FY": (4.33, dt.date(2026, 2, 18)),
        }
    )
    valor, publicacion, formula = derivado["Q3"]
    assert valor == pytest.approx(123_115_000.0 / ADC_Q3, abs=0.02)
    assert formula == "Q3 = FY − H1 − Q4"
    # P1: el trimestre derivado no es deducible antes de su último componente.
    assert publicacion == dt.date(2026, 2, 18)


def test_reconstruir_por_resta_se_niega_a_tocar_un_promedio():
    """La misma trampa, en la otra ruta de reconstrucción.

    `reconstruir_trimestres` también resta acumulados, y también daría un conteo
    de acciones negativo si alguien le pasara uno. Hoy nadie lo hace; el punto de
    esta prueba es que mañana tampoco se pueda.
    """
    from src.datos.repositorio import Repositorio
    from src.ingesta.orquestador import reconstruir_desde_acumulados

    with pytest.raises(ValueError, match="promedio"):
        reconstruir_desde_acumulados(
            Repositorio(ruta=":memory:"), "ADC", "acciones_diluidas", asof=dt.date(2026, 6, 30)
        )


def test_los_factores_de_acumulado_son_los_trimestres_que_abarca():
    assert TRIMESTRES_POR_ACUMULADO == {"H1": 2, "9M": 3, "FY": 4}


# --------------------------------------------------------------------------------------
# 16.2 El TTM son doce meses, no cuatro renglones
# --------------------------------------------------------------------------------------


def _panel(fechas: list[str], valores: list[float | None], columna: str = "affo") -> pd.DataFrame:
    return pd.DataFrame({columna: valores}, index=pd.to_datetime(fechas))


def test_el_ttm_suma_cuatro_trimestres_seguidos():
    panel = _panel(
        ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"], [1.0, 2.0, 3.0, 4.0]
    )
    ttm = _ttm(panel, "affo")
    assert np.isnan(ttm.iloc[2])  # aún no hay cuatro
    assert ttm.iloc[3] == pytest.approx(10.0)


def test_el_ttm_se_niega_cuando_la_ventana_abarca_mas_de_un_ano():
    """El defecto latente: `rolling(4)` cuenta RENGLONES, no calendario.

    Si al panel le falta un trimestre, la ventana de cuatro renglones abarca cinco
    trimestres de calendario y devuelve un "TTM" que no son doce meses. La suma
    cuadra y el número se ve razonable: nada en el resultado lo delata.
    """
    con_hueco = _panel(
        ["2025-03-31", "2025-06-30", "2025-12-31", "2026-03-31"], [1.0, 2.0, 4.0, 5.0]
    )
    ttm = _ttm(con_hueco, "affo")
    assert ttm.isna().all(), "sumó cuatro renglones que abarcan cinco trimestres"


def test_el_ttm_se_niega_cuando_falta_un_valor_en_la_ventana():
    panel = _panel(
        ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"], [1.0, None, 3.0, 4.0]
    )
    assert _ttm(panel, "affo").isna().all()


def test_el_ttm_de_un_concepto_ausente_no_truena():
    assert _ttm(_panel(["2025-03-31"], [1.0]), "no_existe").isna().all()


# --------------------------------------------------------------------------------------
# 16.3 Un hueco en una serie no borra al emisor
# --------------------------------------------------------------------------------------


def _panel_adc(affo_ps_q3: float | None) -> pd.DataFrame:
    """El panel de ADC, con y sin el trimestre que le faltaba por acción."""
    return pd.DataFrame(
        {
            "affo": [113_965_000.0, 117_677_000.0, 123_115_000.0, 128_048_000.0],
            "affo_por_accion": [1.06, 1.06, affo_ps_q3, 1.11],
            "acciones_diluidas": [107_547_193.0, 110_377_221.0, 111_511_615.0, 115_366_551.0],
            "affo_ttm": [None, None, None, 482_805_000.0],
            "affo_por_accion_ttm": [None, None, None, None if affo_ps_q3 is None else 4.33],
        },
        index=pd.to_datetime(["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]),
    )


def test_un_hueco_de_un_trimestre_ya_no_borra_al_emisor():
    """Agree Realty salía en blanco teniendo siete trimestres de AFFO en la base.

    Le faltaba UN valor de AFFO por acción. Como el TTM por acción se caía, y las
    métricas exigían justo ese TTM, el emisor entero desaparecía de la pantalla
    aunque el monto y el conteo de acciones estuvieran completos.
    """
    metricas = _metricas(
        _panel_adc(affo_ps_q3=None), precio=72.62, div_ttm=3.16, rf=0.0477,
        cap_rate=0.0675, yield_adq=None, balance=None, ticker="ADC", sector="Net Lease",
    )
    assert metricas, "el emisor se volvió a borrar por un hueco de un trimestre"
    assert metricas["affo_yield"] is not None
    # 482.8M sobre 115.4M acciones ≈ 4.18 por acción, sobre 72.62 ≈ 5.8%.
    assert 0.04 < metricas["affo_yield"] < 0.08


def test_con_la_serie_completa_manda_el_dato_del_emisor_no_el_deducido():
    """El deducido es un respaldo, no un reemplazo: 4.33 es lo que ADC publicó."""
    metricas = _metricas(
        _panel_adc(affo_ps_q3=1.10), precio=72.62, div_ttm=3.16, rf=0.0477,
        cap_rate=0.0675, yield_adq=None, balance=None, ticker="ADC", sector="Net Lease",
    )
    assert metricas["affo_yield"] == pytest.approx(4.33 / 72.62)


def test_un_conteo_de_acciones_no_positivo_nunca_entra_a_una_metrica():
    """Defensa en profundidad: aunque otra ruta vuelva a producir un negativo."""
    panel = _panel_adc(affo_ps_q3=None)
    panel.loc[panel.index[-1], "acciones_diluidas"] = -115_366_551.0

    metricas = _metricas(
        panel, precio=72.62, div_ttm=3.16, rf=0.0477, cap_rate=0.0675,
        yield_adq=None, balance=None, ticker="ADC", sector="Net Lease",
    )
    for nombre, valor in metricas.items():
        if valor is not None and isinstance(valor, (int, float)) and not pd.isna(valor):
            assert valor > -1e12, f"{nombre} salió absurdo con acciones negativas: {valor}"
    assert (metricas.get("affo_yield") or 0) >= 0, "el yield salió negativo"


# --------------------------------------------------------------------------------------
# 16.4 Contra la base real
# --------------------------------------------------------------------------------------


def test_la_base_no_tiene_conteos_de_acciones_no_positivos(repo_sembrado):
    """Lo que la reparación dejó, y lo que la ingesta ya no debe volver a escribir."""
    hechos = repo_sembrado.hechos(asof=dt.date(2026, 12, 31))
    if hechos.empty:
        pytest.skip("la semilla no trae conteos de acciones")
    acciones = hechos[hechos["concepto"].isin(["acciones_basicas", "acciones_diluidas"])]
    malas = acciones[acciones["valor"] <= 0]
    assert malas.empty, f"conteos de acciones no positivos:\n{malas.to_string()}"


# --------------------------------------------------------------------------------------
# 16.5 Entre dos tablas del mismo periodo, gana la que se puede VERIFICAR
# --------------------------------------------------------------------------------------


def _extraccion(lineas: dict[str, float]) -> ConciliacionExtraida:
    return ConciliacionExtraida(
        ticker="GNL",
        periodo=Periodo("Q", dt.date(2026, 6, 30)),
        lineas=dict(lineas),
        etiquetas={k: k for k in lineas},
        fecha_publicacion=dt.date(2026, 8, 5),
        url_filing="https://example.invalid/ex99-1.htm",
        orden={k: i for i, k in enumerate(lineas)},
    )


# El resumen de resultados: subtotales sin ninguna partida entre ellos. No hay nada
# que verificar, así que no cierra ningún tramo y tampoco falla ninguno.
_RESUMEN = {"ffo": 13_934_000.0, "affo": 45_702_000.0, "affo_por_accion": 0.19}

# La conciliación de verdad, con el puente completo. Cierra el tramo del FFO y el
# del Core FFO, y falla el del AFFO por una partida que el parser no mapeó.
_COMPLETA = {
    "utilidad_neta": -7_450_000.0,
    "deterioro": 3_695_000.0,
    "depreciacion_inmuebles": 41_512_000.0,
    "ganancia_venta_inmuebles": -23_250_000.0,
    "otros_ajustes_no_efectivo": -573_000.0,
    "ffo": 13_934_000.0,
    "partidas_no_recurrentes": 18_472_000.0,
    "ffo_normalizado": 32_406_000.0,
    "compensacion_en_acciones": 3_942_000.0,
    "amortizacion_costos_financieros": 10_956_000.0,
    "affo": 45_702_000.0,
}


def test_el_resumen_sin_partidas_no_verifica_ningun_tramo():
    """El presupuesto de la prueba siguiente, comprobado en vez de supuesto."""
    resumen = _extraccion(_RESUMEN)
    tramos = cuadrar_conciliacion(resumen.lineas, resumen.orden).tramos
    assert not [t for t in tramos if t.verificable], (
        "si el resumen sí verificara algo, el empate que se está arreglando no existe"
    )


def test_una_tabla_sin_verificar_no_le_gana_a_una_verificada_a_medias():
    """Una tabla que no se puede comprobar no es la más confiable: es la más ciega.

    El criterio original ordenaba por «que no falle ningún tramo» ANTES que por
    «cuántos verifica». Con eso, el resumen —que no falla nada porque no comprueba
    nada— le ganaba a la conciliación completa en cuanto esta fallara un tramo, y
    el sistema se quedaba sin el puente entero.

    Es un defecto latente: hoy ningún emisor del universo llega a ese empate. La
    prueba está para que siga sin llegar.
    """
    completa = _extraccion(_COMPLETA)
    fallidos = sum(
        1 for t in cuadrar_conciliacion(completa.lineas, completa.orden).tramos
        if t.verificable and not t.cuadra
    )
    assert fallidos >= 1, "la tabla completa tiene que fallar algo para que haya empate"

    elegida = elegir_mejor_conciliacion([_extraccion(_RESUMEN), completa])
    assert len(elegida) == 1
    assert "depreciacion_inmuebles" in elegida[0].lineas, (
        "se quedó con el resumen y perdió el puente completo"
    )


def test_entre_dos_verificables_gana_la_que_cierra_mas_tramos():
    """Y el detalle desempata al final: la tabla histórica trae filas sin desglose."""
    completa = _extraccion(_COMPLETA)
    parcial = _extraccion(
        {
            "utilidad_neta": -7_450_000.0,
            "deterioro": 3_695_000.0,
            "depreciacion_inmuebles": 41_512_000.0,
            "ganancia_venta_inmuebles": -23_250_000.0,
            "otros_ajustes_no_efectivo": -573_000.0,
            "ffo": 13_934_000.0,
            "affo": 45_702_000.0,
        }
    )
    elegida = elegir_mejor_conciliacion([parcial, completa])
    assert "ffo_normalizado" in elegida[0].lineas
