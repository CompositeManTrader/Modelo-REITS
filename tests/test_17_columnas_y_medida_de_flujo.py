"""Prueba 17 — Una columna que no es un periodo, y un flujo que no es AFFO.

Cuatro defectos distintos tenían el mismo síntoma —el emisor salía en blanco— y
la misma firma: **cifras internamente consistentes en el renglón equivocado**.
Ninguno levanta excepción, ninguno descuadra una suma por sí solo, y los cuatro
salieron de mirar la tabla real que el emisor publicó.

1. **La columna de % de cambio.** Public Storage intercala el cambio porcentual
   entre las columnas de periodo, y **solo en los renglones de subtotal**. Con las
   filas así de desparejas, repartir "columna *i* → periodo *i*" le daba al
   semestre un FFO de 22.9 —el porcentaje— en lugar de 1,515 millones.

2. **La columna por acción pegada a la del monto.** Extra Space Storage publica
   monto y cifra por acción del mismo periodo en columnas contiguas. Al segundo
   periodo le tocaba el POR ACCIÓN del primero, multiplicado por la escala del
   documento: un FFO de 457 millones entraba como 2,070.

3. **La tabla que está toda en dólares por acción.** El resumen de Public Storage
   —"Metric (per share)"— se leía como una conciliación en miles.

4. **La tabla de guía.** Va en el mismo comunicado, con la misma forma y las
   mismas etiquetas. La defensa que ya existía —un periodo que termina después de
   la fecha del filing no puede estar realizado— no alcanza, porque a la guía se
   le asignaba una fecha PASADA heredada de la sección anterior.

El último bloque cubre la otra mitad del problema: **no todos los REITs publican
AFFO.** Public Storage, Extra Space y Welltower terminan su conciliación en el
Core FFO. Copiarlo a la casilla del AFFO sería mentir; dejarlos en blanco borra a
dos sectores de la pantalla. Se usa el Core FFO y se dice que es Core FFO.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.ingesta.parser_affo import (
    Periodo,
    _declara_guia,
    _es_tabla_toda_por_accion,
    _mapear_columnas,
    _valores_alineados,
)
from src.servicio import MEDIDA_AFFO, MEDIDA_CORE_FFO, _elegir_medida_de_flujo, _metricas

# --------------------------------------------------------------------------------------
# 17.1 El porcentaje de cambio no es una columna de datos
# --------------------------------------------------------------------------------------

# Renglón real de Public Storage: monto, monto, %, monto, monto, %.
_FILA_PSA_SUBTOTAL = [
    "FFO allocable to common shares (a)",
    "$", "742,935", "$", "604,494", "22.9", "%", "$", "1,515,661", "$", "1,290,393", "17.5", "%",
]
# Las partidas de detalle NO traen el porcentaje: por eso las filas quedan desparejas.
_FILA_PSA_DETALLE = [
    "Real estate-related depreciation and amortization",
    "284,729", "280,221", "572,495", "560,230",
]


def test_el_porcentaje_de_cambio_no_cuenta_como_columna():
    valores = _valores_alineados(_FILA_PSA_SUBTOTAL)
    assert valores == [742_935.0, 604_494.0, 1_515_661.0, 1_290_393.0]
    assert 22.9 not in valores, "el porcentaje de cambio entró como si fuera un monto"


def test_el_subtotal_y_el_detalle_quedan_con_el_mismo_ancho():
    """Si no coinciden, el reparto por posición asigna cifras al periodo equivocado."""
    assert len(_valores_alineados(_FILA_PSA_SUBTOTAL)) == len(
        _valores_alineados(_FILA_PSA_DETALLE)
    )


def test_el_porcentaje_pegado_al_numero_tambien_se_descarta():
    fila = ["Revenue growth", "1,234", "(0.7)%", "5,678", "0.3%"]
    assert _valores_alineados(fila) == [1_234.0, 5_678.0]


def test_el_parentesis_del_negativo_sigue_funcionando():
    """Control de no-regresión: el filtro del porcentaje no puede comerse el signo."""
    assert _valores_alineados(["Gains on sale", "35", "(163)", "(344)", "(208)"]) == [
        35.0, -163.0, -344.0, -208.0
    ]
    assert _valores_alineados(["Ganancia", "(", "38,260", ")"]) == [-38_260.0]


# --------------------------------------------------------------------------------------
# 17.2 La columna por acción no es la del periodo siguiente
# --------------------------------------------------------------------------------------


def _periodos(n: int) -> list[Periodo]:
    fines = [dt.date(2026, 6, 30), dt.date(2025, 6, 30), dt.date(2026, 6, 30), dt.date(2025, 6, 30)]
    return [Periodo("Q" if i < 2 else "H1", fines[i]) for i in range(n)]


def test_con_columnas_alternadas_solo_las_pares_son_montos():
    """La conciliación de Extra Space: monto, por acción, monto, por acción…"""
    matriz = [
        ["", "For the Three Months Ended June 30,", "For the Six Months Ended June 30,"],
        ["", "2026", "2025", "2026", "2025"],
        ["", "(per share) 1", "(per share) 1", "(per share) 1", "(per share) 1"],
        ["Real estate depreciation",
         "171,249", "0.77", "164,707", "0.74", "342,144", "1.55", "329,414", "1.48"],
        ["FFO", "457,305", "2.07", "439,253", "1.98", "896,000", "4.06", "860,000", "3.88"],
    ]
    columnas = _mapear_columnas(matriz, _periodos(4))

    assert sorted(columnas) == [0, 2, 4, 6], (
        "mapeó columnas impares, que son las de POR ACCIÓN, como si fueran periodos"
    )


def test_sin_marca_por_accion_el_reparto_sigue_siendo_el_de_siempre():
    """Control: la mayoría de los emisores no intercala, y no deben verse afectados."""
    matriz = [
        ["", "Three Months Ended June 30,"],
        ["", "2026", "2025"],
        ["Depreciation", "171,249", "164,707"],
    ]
    assert _mapear_columnas(matriz, _periodos(2)) == {0: _periodos(2)[0], 1: _periodos(2)[1]}


# --------------------------------------------------------------------------------------
# 17.3 Una tabla toda por acción no es una conciliación
# --------------------------------------------------------------------------------------

# El resumen con el que Public Storage abre su comunicado.
_RESUMEN_PSA = [
    [],
    ["", "Three Months Ended June 30,", "Change", "Six Months Ended June 30, 2026", "Change"],
    ["Metric (per share)", "2026", "2025", "$", "%", "2026", "2025", "$", "%"],
    ["Net Income", "$2.55", "$1.76", "$0.79", "44.9%", "$5.26", "$3.79", "$1.47", "38.8%"],
    ["Core FFO", "$4.17", "$4.28", "$(0.11)", "(2.6)%", "$8.38", "$8.39", "$(0.01)", "(0.1)%"],
]


def test_la_tabla_toda_por_accion_se_reconoce():
    assert _es_tabla_toda_por_accion(_RESUMEN_PSA)


def test_el_ano_del_encabezado_no_la_disfraza_de_importes():
    """El defecto dentro del defecto: un "2026" de encabezado es numérico.

    Con el año contando como importe, el mayor valor de la tabla pasaba de 44.9 a
    2,026 y la tabla se colaba como si trajera montos.
    """
    valores = [
        v for fila in _RESUMEN_PSA for v in _valores_alineados(fila) if v is not None
    ]
    assert 2026.0 in valores, "si el año ya no se lee, esta prueba no prueba nada"
    assert _es_tabla_toda_por_accion(_RESUMEN_PSA)


def test_la_conciliacion_con_montos_al_lado_no_se_descarta():
    """Extra Space también dice "per share" y sí trae los montos. No es lo mismo."""
    matriz = [
        ["", "(per share) 1", "(per share) 1"],
        ["Real estate depreciation", "171,249", "0.77", "164,707", "0.74"],
        ["FFO", "457,305", "2.07", "439,253", "1.98"],
    ]
    assert not _es_tabla_toda_por_accion(matriz)


def test_una_tabla_sin_mencion_de_por_accion_nunca_se_descarta():
    matriz = [["", "2026"], ["Net income", "1.25"], ["FFO", "2.07"]]
    assert not _es_tabla_toda_por_accion(matriz)


# --------------------------------------------------------------------------------------
# 17.4 "Ended" es pasado; "ending" es futuro
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "encabezado",
    [
        "For the Year Ending December 31, 2026",
        "Outlook Reconciliation: Year Ending December 31, 2026",
        "2026 Guidance",
        "Current Ranges for 2026 Annual Assumptions",
        "For the Three Months Ending September 30, 2026",
    ],
)
def test_el_encabezado_de_guia_se_reconoce(encabezado):
    assert _declara_guia(encabezado)


@pytest.mark.parametrize(
    "encabezado",
    [
        "For the Three Months Ended June 30, 2026",
        "For the Six Months Ended June 30,",
        "Year Ended December 31, 2025",
        "Quarter Ended June 30,",
    ],
)
def test_el_encabezado_de_un_periodo_cerrado_no_es_guia(encabezado):
    assert not _declara_guia(encabezado)


# --------------------------------------------------------------------------------------
# 17.5 No todos los REITs publican AFFO, y la pantalla lo dice
# --------------------------------------------------------------------------------------


def _panel(**columnas) -> pd.DataFrame:
    n = len(next(iter(columnas.values())))
    fechas = pd.date_range("2025-09-30", periods=n, freq="QE")
    return pd.DataFrame(columnas, index=fechas)


def test_con_affo_publicado_se_usa_el_affo():
    panel = _panel(affo=[100.0] * 4, ffo_normalizado=[130.0] * 4)
    assert _elegir_medida_de_flujo(panel) == MEDIDA_AFFO
    assert panel["affo"].iloc[-1] == 100.0, "pisó el AFFO del emisor con su Core FFO"


def test_sin_affo_se_usa_el_core_ffo_y_se_declara():
    """Public Storage, Extra Space y Welltower no publican AFFO."""
    panel = _panel(affo=[None] * 4, ffo_normalizado=[130.0] * 4)
    assert _elegir_medida_de_flujo(panel) == MEDIDA_CORE_FFO
    assert panel["affo"].iloc[-1] == 130.0


def test_sin_ninguna_de_las_dos_no_se_inventa_una_medida():
    panel = _panel(affo=[None] * 4, ffo_normalizado=[None] * 4)
    assert _elegir_medida_de_flujo(panel) == MEDIDA_AFFO
    assert panel["affo"].isna().all()


def test_el_core_ffo_no_se_presenta_como_affo():
    """La regla que hace honesta la sustitución: la etiqueta cambia con el dato."""
    assert MEDIDA_CORE_FFO != MEDIDA_AFFO
    assert "FFO" in MEDIDA_CORE_FFO and "AFFO" not in MEDIDA_CORE_FFO


# --------------------------------------------------------------------------------------
# 17.6 Sin denominador no hay métrica por acción
# --------------------------------------------------------------------------------------


def test_sin_conteo_de_acciones_se_retrocede_al_ultimo_renglon_completo():
    """A Welltower le faltaba el conteo justo en el último trimestre.

    El respaldo de "acciones = 1" convertía un flujo de 4,000 millones en 4,000
    millones POR ACCIÓN, y el yield salía en 17 millones por ciento. Un número
    absurdo es peor que ningún número.
    """
    panel = pd.DataFrame(
        {
            "affo": [1.0e9, 1.05e9, 1.07e9, 1.18e9],
            "affo_por_accion": [None, None, None, None],
            "acciones_diluidas": [685_399_000.0, 710_750_000.0, 726_255_000.0, None],
            "affo_ttm": [None, None, 4.19e9, 4.30e9],
            "affo_por_accion_ttm": [None, None, None, None],
        },
        index=pd.to_datetime(["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]),
    )
    metricas = _metricas(
        panel, precio=236.17, div_ttm=3.06, rf=0.0477, cap_rate=0.0675,
        yield_adq=None, balance=None, ticker="WELL", sector="Salud",
    )
    assert metricas, "descartó al emisor teniendo un renglón completo"
    # 4.19e9 sobre 726 millones ≈ 5.77 por acción, sobre 236.17 ≈ 2.4%.
    assert 0.01 < metricas["affo_yield"] < 0.06, (
        f"yield absurdo: {metricas['affo_yield']:.4f}"
    )


def test_sin_acciones_en_ningun_renglon_no_se_devuelve_metrica():
    panel = pd.DataFrame(
        {
            "affo": [1.0e9] * 4,
            "affo_por_accion": [None] * 4,
            "acciones_diluidas": [None] * 4,
            "affo_ttm": [None, None, None, 4.0e9],
            "affo_por_accion_ttm": [None] * 4,
        },
        index=pd.to_datetime(["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]),
    )
    assert _metricas(
        panel, precio=236.17, div_ttm=3.06, rf=0.0477, cap_rate=0.0675,
        yield_adq=None, balance=None, ticker="X", sector="Salud",
    ) == {}
