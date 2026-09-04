"""Prueba 10 — La conciliación de W. P. Carey, y los cuatro defectos que la escondían.

W. P. Carey no cuadraba en ningún periodo. Las cuatro causas resultaron ser
distintas y solo una era de W. P. Carey: las otras tres afectaban a todos los
emisores y estaban tapadas porque el descuadre aparecía siempre en el AFFO,
lejos de donde se originaba.

La peor no era un descuadre. Era un **corrimiento de columnas**: el parser le
ponía al primer trimestre las cifras del segundo. Eso no rompe ninguna suma —los
números son internamente consistentes— así que ninguna validación aritmética lo
habría cazado nunca. Se ve comparando el encabezado contra lo extraído, y por eso
esta prueba lo hace explícito.

El fixture es un extracto del Exhibit 99.1 que la SEC publicó el 2026-07-28.
Ninguna prueba de este archivo toca la red.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from src.ingesta.parser_affo import (
    detectar_periodos,
    normalizar_etiqueta,
    parsear_conciliacion,
)
from src.validacion.cuadre import cuadrar_conciliacion

FIXTURE = Path(__file__).parent / "fixtures" / "wpc_8k_q2_2026_ex99_1.html"
PUBLICACION = dt.date(2026, 7, 28)


@pytest.fixture
def extracciones():
    return parsear_conciliacion(FIXTURE.read_text(), "WPC", PUBLICACION, "fixture")


# --------------------------------------------------------------------------------------
# 10.1 El corrimiento de columnas: el error que ninguna suma delata
# --------------------------------------------------------------------------------------


def test_tres_columnas_con_dos_del_mismo_anio_no_se_colapsan():
    """El encabezado de W. P. Carey trae tres trimestres y dos son de 2026.

    El código deduplicaba las fechas por AÑO para resolver el idioma común
    "June 30, 2026 and 2025", donde una fecha completa va seguida de años sueltos.
    Con tres columnas eso colapsaba el 30 de junio y el 31 de marzo de 2026 en una
    sola, y el corrimiento resultante le asignaba al primer trimestre las cifras
    del segundo. Números correctos, periodo equivocado: la conciliación seguía
    cuadrando consigo misma.
    """
    periodos = detectar_periodos(
        "Three Months Ended June 30, 2026 March 31, 2026 June 30, 2025"
    )
    assert [(p.tipo, p.fin) for p in periodos] == [
        ("Q", dt.date(2026, 6, 30)),
        ("Q", dt.date(2026, 3, 31)),
        ("Q", dt.date(2025, 6, 30)),
    ]


def test_el_orden_de_las_columnas_se_respeta_tal_cual():
    """El orden del encabezado ES el orden de las columnas; ordenarlo por fecha lo rompe."""
    ascendente = detectar_periodos("Three Months Ended March 31, 2025 June 30, 2025")
    assert [p.fin for p in ascendente] == [dt.date(2025, 3, 31), dt.date(2025, 6, 30)], (
        "Si la tabla lista de más viejo a más nuevo, así se tienen que devolver: el "
        "índice de columna se mapea posicionalmente contra esta lista."
    )


def test_el_idioma_de_anios_sueltos_sigue_funcionando():
    """Control: la razón por la que existía la deduplicación no se perdió."""
    periodos = detectar_periodos("Three Months Ended June 30, 2026 and 2025")
    assert [p.fin for p in periodos] == [dt.date(2026, 6, 30), dt.date(2025, 6, 30)]


def test_el_trimestre_mas_reciente_del_filing_aparece(extracciones):
    """Con el corrimiento, el trimestre que el filing viene a reportar se perdía."""
    fines = {(x.periodo.tipo, x.periodo.fin) for x in extracciones}
    assert ("Q", dt.date(2026, 6, 30)) in fines, (
        "El 8-K del 28 de julio de 2026 reporta el trimestre cerrado el 30 de junio. "
        "Si ese periodo no está, las columnas se corrieron."
    )


def test_cada_periodo_recibe_las_cifras_de_su_propia_columna(extracciones):
    """Ancla contra el filing: estas cifras están impresas en el documento."""
    por_periodo = {(x.periodo.tipo, x.periodo.fin): x.lineas for x in extracciones}

    # Columna 1 del encabezado: Three Months Ended June 30, 2026.
    q2 = por_periodo[("Q", dt.date(2026, 6, 30))]
    assert q2["utilidad_neta"] == pytest.approx(185_389_000)
    assert q2["ffo"] == pytest.approx(342_495_000)
    assert q2["affo"] == pytest.approx(305_444_000)

    # Columna 2: Three Months Ended March 31, 2026. Es la que recibía las cifras
    # de la columna 1 antes del arreglo.
    q1 = por_periodo[("Q", dt.date(2026, 3, 31))]
    assert q1["utilidad_neta"] == pytest.approx(176_302_000)
    assert q1["affo"] == pytest.approx(288_657_000)


# --------------------------------------------------------------------------------------
# 10.2 La acumulación por segmento
# --------------------------------------------------------------------------------------


def test_un_concepto_repetido_dentro_del_segundo_tramo_se_acumula(extracciones):
    """El sufijo de segmento rompía la pregunta "¿es acumulable?".

    Al entrar a un tramo posterior al primero, la clave se vuelve
    ``otros_ajustes_no_efectivo#1``, que por construcción nunca está en el conjunto
    de claves acumulables. Así que de la segunda fila en adelante, todo concepto
    repetido se descartaba **en silencio**. W. P. Carey mete cuatro filas de otros
    ajustes y dos de participación proporcional en el tramo del AFFO: sobrevivía
    una de cada una.
    """
    q2 = next(
        x.lineas for x in extracciones
        if (x.periodo.tipo, x.periodo.fin) == ("Q", dt.date(2026, 6, 30))
    )

    # Cuatro filas: (48,558) + 3,706 + 2,617 + 548 = (41,687)
    assert q2["otros_ajustes_no_efectivo#1"] == pytest.approx(-41_687_000)
    # Dos filas: 303 + (22) = 281
    assert q2["no_consolidadas_y_minoritarios#1"] == pytest.approx(281_000)
    # Y el tramo del FFO conserva las suyas, sin mezclarse: (50,133) + (26)
    assert q2["no_consolidadas_y_minoritarios"] == pytest.approx(-50_159_000)


# --------------------------------------------------------------------------------------
# 10.3 Las etiquetas
# --------------------------------------------------------------------------------------


def test_el_subtotal_de_ffo_admite_un_parentesis_intermedio():
    """Sin este subtotal no hay frontera de tramo y todo cae en uno solo.

    Por eso el descuadre aparecía en el AFFO aunque la causa estuviera antes: sin
    FFO reconocido, el tramo del AFFO empezaba en la utilidad neta.
    """
    assert normalizar_etiqueta("FFO (as defined by NAREIT) Attributable to W. P. Carey (d)") == "ffo"
    assert normalizar_etiqueta("AFFO Attributable to W. P. Carey (d)") == "affo"


def test_el_subtotal_no_se_come_las_partidas_que_lo_mencionan():
    """Control: el patrón se amplió sin volverlo indiscriminado."""
    assert normalizar_etiqueta("FFO adjustments allocable to noncontrolling interests") == (
        "no_consolidadas_y_minoritarios"
    )
    assert normalizar_etiqueta("Cumulative adjustments to calculate Normalized FFO") == (
        "ajustes_acumulados_ffo_normalizado"
    )


@pytest.mark.parametrize(
    "etiqueta",
    [
        "Tax expense – deferred and other",
        "Tax expense (benefit) – deferred and other",
        "Tax (benefit) expense – deferred and other",
    ],
)
def test_el_mismo_emisor_escribe_la_linea_de_impuestos_de_tres_formas(etiqueta):
    """Tres trimestres consecutivos, tres redacciones. Se descubre leyendo varios filings."""
    assert normalizar_etiqueta(etiqueta) == "otros_ajustes_no_efectivo"


def test_el_impuesto_del_estado_de_resultados_no_es_un_ajuste_de_affo():
    """Control: el patrón de impuestos es específico, no atrapa cualquier línea fiscal."""
    assert normalizar_etiqueta("Income tax expense") is None
    assert normalizar_etiqueta("Provision for income taxes") is None


@pytest.mark.parametrize(
    "etiqueta,esperada",
    [
        ("Straight-line and other leasing and financing adjustments", "renta_linea_recta"),
        ("Above- and below-market rent intangible lease amortization, net",
         "otros_ajustes_no_efectivo"),
        ("Other (gains) and losses (e)", "otros_ajustes_no_efectivo"),
        ("Other amortization and non-cash items", "otros_ajustes_no_efectivo"),
    ],
)
def test_las_partidas_del_tramo_del_affo_se_reconocen(etiqueta, esperada):
    assert normalizar_etiqueta(etiqueta) == esperada


def test_los_encabezados_internos_no_se_toman_por_partidas():
    """`Adjustments:` y `Total adjustments` son estructura, no montos."""
    assert normalizar_etiqueta("Adjustments:") is None
    assert normalizar_etiqueta("Total adjustments") is None


# --------------------------------------------------------------------------------------
# 10.4 El resultado: cuadra contra los subtotales del propio emisor
# --------------------------------------------------------------------------------------


def test_los_cinco_periodos_del_filing_cuadran_exacto(extracciones):
    assert len(extracciones) == 5
    for x in extracciones:
        resultado = cuadrar_conciliacion(x.lineas, x.orden)
        assert resultado.cuadra, f"{x.periodo.etiqueta}: {resultado.detalle}"
        for tramo in resultado.tramos:
            if tramo.verificable:
                assert tramo.diferencia == pytest.approx(0.0, abs=1.0), (
                    f"{x.periodo.etiqueta} / {tramo.subtotal}: diferencia {tramo.diferencia:,.0f}"
                )


def test_los_dos_tramos_tienen_partidas_itemizadas(extracciones):
    """Un cuadre sobre tramos vacíos pasaría siempre y no probaría nada."""
    for x in extracciones:
        resultado = cuadrar_conciliacion(x.lineas, x.orden)
        verificables = [t for t in resultado.tramos if t.verificable]
        assert {t.subtotal for t in verificables} == {"ffo", "affo"}
        for tramo in verificables:
            assert len(tramo.partidas) >= 5


def test_control_alterar_una_partida_rompe_el_cuadre(extracciones):
    """Si el cuadre no pudiera fallar, no estaría comprobando nada."""
    x = extracciones[0]
    alteradas = dict(x.lineas)
    # Las partidas del segundo tramo llevan sufijo de segmento: es la compensación
    # en acciones que W. P. Carey reporta entre el FFO y el AFFO.
    alteradas["compensacion_en_acciones#1"] += 1_000_000
    resultado = cuadrar_conciliacion(alteradas, x.orden)
    assert not resultado.cuadra
