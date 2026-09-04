"""Prueba 12 — Dos duraciones en un mismo encabezado, y el paréntesis pegado.

NNN publica cuatro columnas bajo un solo encabezado, con **dos duraciones
distintas**::

    Quarter Ended June 30,        Six Months Ended June 30,
         2026   |   2025               2026   |   2025

El parser detectaba una sola duración por encabezado, así que las cuatro columnas
salían etiquetadas igual. Y como ``Quarter Ended`` ni siquiera figuraba entre los
patrones de duración, la que ganaba era la del semestre: los dos trimestres
entraban a la base como semestres. De ahí salían etiquetas imposibles —un
"semestre" que cierra el 31 de marzo— que ninguna suma podía delatar, porque cada
columna es internamente consistente.

Ninguna prueba de este archivo toca la red.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from src.ingesta.parser_affo import (
    _valores_alineados,
    detectar_periodos,
    normalizar_etiqueta,
    parsear_conciliacion,
)
from src.validacion.cuadre import cuadrar_conciliacion

FIXTURE = Path(__file__).parent / "fixtures" / "nnn_8k_q2_2026_ex99_1.html"
PUBLICACION = dt.date(2026, 8, 5)


@pytest.fixture
def extracciones():
    return parsear_conciliacion(FIXTURE.read_text(), "NNN", PUBLICACION, "fixture")


# --------------------------------------------------------------------------------------
# 12.1 Dos duraciones bajo el mismo encabezado
# --------------------------------------------------------------------------------------


def test_un_encabezado_con_dos_duraciones_produce_los_dos_tipos():
    """Las columnas van por grupo: primero los trimestres, luego los semestres."""
    periodos = detectar_periodos(
        "Quarter Ended June 30, Six Months Ended June 30, 2026 2025 2026 2025"
    )
    assert [(p.tipo, p.fin) for p in periodos] == [
        ("Q", dt.date(2026, 6, 30)),
        ("Q", dt.date(2025, 6, 30)),
        ("H1", dt.date(2026, 6, 30)),
        ("H1", dt.date(2025, 6, 30)),
    ]


def test_quarter_ended_es_una_duracion_trimestral():
    """`Quarter Ended` no estaba entre los patrones y es tan común como `Three Months`."""
    periodos = detectar_periodos("Quarter Ended June 30, 2026 and 2025")
    assert [p.tipo for p in periodos] == ["Q", "Q"]


def test_la_misma_duracion_repetida_no_se_cuenta_dos_veces():
    """Control: repetir la frase no inventa un segundo grupo de columnas."""
    periodos = detectar_periodos(
        "three months ended June 30, 2026 and three months ended June 30, 2025"
    )
    assert [(p.tipo, p.fin) for p in periodos] == [
        ("Q", dt.date(2026, 6, 30)),
        ("Q", dt.date(2025, 6, 30)),
    ]


def test_una_sola_duracion_se_comporta_igual_que_antes():
    """Control de no regresión sobre el formato de W. P. Carey."""
    periodos = detectar_periodos("Three Months Ended June 30, 2026 March 31, 2026 June 30, 2025")
    assert [(p.tipo, p.fin) for p in periodos] == [
        ("Q", dt.date(2026, 6, 30)),
        ("Q", dt.date(2026, 3, 31)),
        ("Q", dt.date(2025, 6, 30)),
    ]


def test_el_dia_y_el_mes_pueden_venir_separados_de_los_anios():
    """El encabezado se parte en dos filas y ninguna fecha queda completa.

    "Quarter Ended June 30," arriba, "2026 2025 2026 2025" abajo. Sin casar el
    mes y el día con la lista de años, la tabla entera se descartaba en silencio.
    """
    periodos = detectar_periodos("Quarter Ended June 30, 2026 2025")
    assert [(p.tipo, p.fin) for p in periodos] == [
        ("Q", dt.date(2026, 6, 30)),
        ("Q", dt.date(2025, 6, 30)),
    ]


def test_un_encabezado_sin_duracion_ni_fechas_no_inventa_periodos():
    assert detectar_periodos("(dollars in thousands, except per share data)") == []
    assert detectar_periodos("") == []


# --------------------------------------------------------------------------------------
# 12.2 El paréntesis pegado al número
# --------------------------------------------------------------------------------------


def test_el_parentesis_de_apertura_pegado_al_numero_es_negativo():
    """Tercera variante del mismo problema, y la que faltaba.

    NNN maqueta sus negativos como ``"(9,105"`` y ``")"`` en celdas contiguas: el
    paréntesis de apertura va pegado al número y solo el de cierre queda solo.
    Leerlo en positivo desplaza el subtotal por el DOBLE de la partida.
    """
    fila = ["Gain on disposition of real estate", "", "", "(9,105", ")", "", "", "(16,198", ")"]
    assert _valores_alineados(fila) == [-9105.0, -16198.0]


def test_las_otras_dos_variantes_del_parentesis_siguen_funcionando():
    # Paréntesis completo dentro de una celda.
    assert _valores_alineados(["Etiqueta", "(1,234)"]) == [-1234.0]
    # Paréntesis de apertura en su propia celda (el formato de Realty Income).
    assert _valores_alineados(["Etiqueta", "(", "38,260", ")"]) == [-38260.0]
    # Y un positivo sigue siendo positivo.
    assert _valores_alineados(["Etiqueta", "70,933"]) == [70933.0]


# --------------------------------------------------------------------------------------
# 12.3 Etiquetas
# --------------------------------------------------------------------------------------


def test_net_earnings_es_utilidad_neta():
    """Sin esto el FFO descuadraba por el monto exacto de la utilidad neta."""
    assert normalizar_etiqueta("Net earnings") == "utilidad_neta"


@pytest.mark.parametrize(
    "etiqueta",
    [
        "Net capital lease rent adjustment",
        "Below-market rent amortization",
        "Capitalized interest expense",
    ],
)
def test_las_partidas_del_tramo_del_affo_de_nnn_se_reconocen(etiqueta):
    assert normalizar_etiqueta(etiqueta) == "otros_ajustes_no_efectivo"


def test_las_lineas_de_ingreso_no_se_confunden_con_la_conciliacion():
    """Control: la tabla resumen trae `Revenues`, que no es parte de la cascada de FFO."""
    assert normalizar_etiqueta("Net earnings per share") == "utilidad_neta"


# --------------------------------------------------------------------------------------
# 12.4 El resultado sobre el filing real
# --------------------------------------------------------------------------------------


def test_los_cuatro_periodos_llevan_su_tipo_correcto(extracciones):
    """Dos trimestres y dos semestres, no cuatro semestres."""
    etiquetas = {(x.periodo.tipo, x.periodo.fin) for x in extracciones}
    assert ("Q", dt.date(2026, 6, 30)) in etiquetas
    assert ("Q", dt.date(2025, 6, 30)) in etiquetas
    assert ("H1", dt.date(2026, 6, 30)) in etiquetas
    assert ("H1", dt.date(2025, 6, 30)) in etiquetas


def test_el_semestre_es_aproximadamente_el_doble_del_trimestre(extracciones):
    """Prueba de coherencia que solo pasa si los tipos están bien asignados.

    Es el control que le da fuerza a la prueba anterior: aunque alguien volviera a
    etiquetar los cuatro periodos igual, esta comparación lo delataría.
    """
    por = {(x.periodo.tipo, x.periodo.fin): x.lineas for x in extracciones}
    q2 = por[("Q", dt.date(2026, 6, 30))]["affo"]
    h1 = por[("H1", dt.date(2026, 6, 30))]["affo"]
    assert 1.7 < h1 / q2 < 2.3, (
        f"El semestre ({h1:,.0f}) debería andar cerca del doble del trimestre "
        f"({q2:,.0f}); si son casi iguales, los dos son el mismo periodo mal tipado."
    )


def test_las_cifras_son_las_del_filing(extracciones):
    """Anclas contra el documento: estas cifras están impresas en el Exhibit 99.1."""
    por = {(x.periodo.tipo, x.periodo.fin): x.lineas for x in extracciones}
    q2 = por[("Q", dt.date(2026, 6, 30))]
    assert q2["utilidad_neta"] == pytest.approx(97_924_000)
    assert q2["ffo"] == pytest.approx(167_819_000)
    assert q2["ffo_normalizado"] == pytest.approx(168_187_000)
    assert q2["affo"] == pytest.approx(170_020_000)
    # La ganancia por venta entra en NEGATIVO: es lo que el paréntesis significa.
    assert q2["ganancia_venta_inmuebles"] == pytest.approx(-9_105_000)


def test_los_cuatro_periodos_cuadran_exacto(extracciones):
    assert len(extracciones) == 4
    for x in extracciones:
        resultado = cuadrar_conciliacion(x.lineas, x.orden)
        assert resultado.cuadra, f"{x.periodo.etiqueta}: {resultado.detalle}"
        for tramo in resultado.tramos:
            if tramo.verificable:
                assert tramo.diferencia == pytest.approx(0.0, abs=1.0)


def test_los_tres_subtotales_de_nnn_se_verifican(extracciones):
    """NNN publica FFO, Core FFO y AFFO: los tres tramos deben tener partidas."""
    for x in extracciones:
        resultado = cuadrar_conciliacion(x.lineas, x.orden)
        verificables = {t.subtotal for t in resultado.tramos if t.verificable}
        assert verificables == {"ffo", "ffo_normalizado", "affo"}


def test_control_alterar_una_partida_rompe_el_cuadre(extracciones):
    x = extracciones[0]
    alteradas = dict(x.lineas)
    alteradas["depreciacion_inmuebles"] += 1_000_000
    assert not cuadrar_conciliacion(alteradas, x.orden).cuadra
