"""Prueba 13 — La ficha de un emisor lo aísla de los patrones de los demás.

El parser resolvía las etiquetas con un solo juego de expresiones regulares
compartido por los diez emisores. Cada vez que había que ampliar un patrón para
cubrir a uno, el riesgo era romper a otro **sin que nada lo avisara**: la
conciliación del otro seguía cuadrando, con las cifras en la línea equivocada.

La prueba central de este archivo es esa: se corrompe un patrón compartido a
propósito y se verifica que el emisor con ficha no se entera. Sin ella, la ficha
sería documentación; con ella, es aislamiento.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from src.ingesta import parser_affo
from src.ingesta.parser_affo import parsear_conciliacion, resolver_etiqueta
from src.ingesta.taxonomia import (
    FICHAS,
    IGNORAR,
    FichaEmisor,
    canonizar,
    ficha_de,
)
from src.validacion.cuadre import cuadrar_conciliacion

FIXTURES = Path(__file__).parent / "fixtures"


# --------------------------------------------------------------------------------------
# 13.1 La forma canónica
# --------------------------------------------------------------------------------------


def test_las_tres_redacciones_de_la_misma_linea_colapsan():
    """W. P. Carey mueve un paréntesis de lugar entre trimestres consecutivos.

    Antes hacían falta tres variantes en la expresión regular. Con la forma
    canónica, una sola entrada en la ficha cubre las tres.
    """
    formas = [
        "Tax expense – deferred and other",
        "Tax expense (benefit) – deferred and other",
        "Tax (benefit) expense – deferred and other",
    ]
    canonicas = {canonizar(f) for f in formas}
    assert len(canonicas) == 1, f"No colapsaron: {canonicas}"
    assert canonicas.pop() == "tax expense - deferred and other"


def test_la_nota_al_pie_no_cambia_la_identidad_de_la_linea():
    assert canonizar("AFFO Attributable to W. P. Carey (d)") == canonizar(
        "AFFO attributable to W. P. Carey"
    )
    assert canonizar("Other adjustments (4)") == canonizar("Other adjustments")


def test_el_tipo_de_guion_no_cambia_la_identidad():
    assert canonizar("Impairment losses – depreciable real estate") == canonizar(
        "Impairment losses - depreciable real estate"
    )


def test_la_canonizacion_no_borra_lo_que_si_distingue():
    """Control: si colapsara de más, la ficha confundiría líneas distintas."""
    distintas = [
        "Real estate depreciation and amortization",
        "Non-real estate depreciation",
        "Depreciation of furniture, fixtures and equipment",
        "Net income",
        "Net income attributable to noncontrolling interests",
    ]
    assert len({canonizar(d) for d in distintas}) == len(distintas)


def test_una_etiqueta_vacia_da_forma_vacia():
    assert canonizar("") == ""
    assert canonizar(None) == ""


# --------------------------------------------------------------------------------------
# 13.2 La ficha manda sobre los patrones compartidos
# --------------------------------------------------------------------------------------


def test_la_ficha_gana_sobre_el_patron_compartido(monkeypatch):
    """El caso de uso entero: la ficha decide, aunque el patrón diga otra cosa."""
    ficha = FichaEmisor(
        ticker="PRUEBA",
        nombre="Emisor de prueba",
        lineas={canonizar("Net income"): "deterioro"},  # a propósito, distinto
    )
    monkeypatch.setitem(FICHAS, "PRUEBA", ficha)

    assert resolver_etiqueta("PRUEBA", "Net income") == ("deterioro", True)
    # Y el mismo texto, para un emisor sin ficha, sigue resolviéndose como siempre.
    assert resolver_etiqueta("SINFICHA", "Net income") == ("utilidad_neta", False)


def test_la_ficha_puede_declarar_que_una_etiqueta_no_va(monkeypatch):
    """`IGNORAR` dice "ya lo miré y no es de la cascada", que no es lo mismo que callar."""
    ficha = FichaEmisor(
        ticker="PRUEBA", nombre="x", lineas={canonizar("Net income"): IGNORAR}
    )
    monkeypatch.setitem(FICHAS, "PRUEBA", ficha)
    clave, declarada = resolver_etiqueta("PRUEBA", "Net income")
    assert clave is None
    assert declarada is True, (
        "Declarado-como-no-va y no-declarado se ven igual en la clave, pero son "
        "cosas distintas: solo el segundo es un hueco que hay que llenar."
    )


def test_lo_no_declarado_cae_a_los_patrones_y_se_marca_como_hueco(monkeypatch):
    ficha = FichaEmisor(ticker="PRUEBA", nombre="x", lineas={})
    monkeypatch.setitem(FICHAS, "PRUEBA", ficha)
    clave, declarada = resolver_etiqueta("PRUEBA", "Net income")
    assert clave == "utilidad_neta"
    assert declarada is False


# --------------------------------------------------------------------------------------
# 13.3 EL AISLAMIENTO — la razón de ser de todo esto
# --------------------------------------------------------------------------------------


def _cuadran_todos(extracciones) -> bool:
    return bool(extracciones) and all(
        cuadrar_conciliacion(x.lineas, x.orden).cuadra for x in extracciones
    )


def test_corromper_un_patron_compartido_no_toca_al_emisor_con_ficha(monkeypatch):
    """Se rompe a propósito el patrón compartido de la utilidad neta.

    Es el escenario real que motivó la ficha: alguien amplía un patrón para
    cubrir a un emisor y desconfigura a otro. Con ficha, W. P. Carey no se entera.
    """
    html = (FIXTURES / "wpc_8k_q2_2026_ex99_1.html").read_text()

    # Control primero: con todo en su lugar, cuadra.
    assert _cuadran_todos(parsear_conciliacion(html, "WPC", dt.date(2026, 7, 28), "f"))

    # Ahora se sabotean TODOS los patrones compartidos: cualquier etiqueta que
    # llegue a ellos se resolverá a "deterioro".
    import re

    monkeypatch.setattr(
        parser_affo, "_PATRONES", [("deterioro", re.compile(r".*", re.I))]
    )

    # El emisor con ficha sigue cuadrando exactamente igual.
    assert _cuadran_todos(parsear_conciliacion(html, "WPC", dt.date(2026, 7, 28), "f")), (
        "La ficha no está aislando: los patrones compartidos siguen decidiendo."
    )


def test_control_sin_ficha_el_mismo_sabotaje_si_rompe(monkeypatch):
    """Contraprueba: si la prueba anterior no pudiera fallar, no probaría nada."""
    import re

    html = (FIXTURES / "wpc_8k_q2_2026_ex99_1.html").read_text()
    monkeypatch.delitem(FICHAS, "WPC")
    monkeypatch.setattr(
        parser_affo, "_PATRONES", [("deterioro", re.compile(r".*", re.I))]
    )
    assert not _cuadran_todos(parsear_conciliacion(html, "WPC", dt.date(2026, 7, 28), "f"))


# --------------------------------------------------------------------------------------
# 13.4 Las fichas declaradas son coherentes y cubren sus filings
# --------------------------------------------------------------------------------------


def test_las_fichas_declaran_subtotales_que_existen_en_la_cascada():
    from src.modelo.cascada import TODAS_LAS_LINEAS

    validas = {ln.clave for ln in TODAS_LAS_LINEAS}
    for ticker, ficha in FICHAS.items():
        assert ficha.subtotales, f"{ticker} no declara su estructura de tramos."
        for subtotal in ficha.subtotales:
            assert subtotal in validas, f"{ticker} declara un subtotal inexistente: {subtotal}"
        for etiqueta, clave in ficha.lineas.items():
            assert clave == IGNORAR or clave in validas, (
                f"{ticker} mapea «{etiqueta}» a una clave inexistente: {clave}"
            )


def test_las_etiquetas_de_una_ficha_no_se_repiten_al_canonizar():
    """Dos redacciones que colapsan a la misma forma tienen que decir lo mismo.

    Si colapsan y dicen cosas distintas, una pisa a la otra según el orden del
    diccionario, que es justo la clase de ambigüedad que la ficha viene a eliminar.
    """
    for ticker, ficha in FICHAS.items():
        assert len(ficha.lineas) == len(set(ficha.lineas)), f"{ticker} tiene colisiones."


@pytest.mark.parametrize(
    "ticker,fixture,publicacion",
    [
        ("WPC", "wpc_8k_q2_2026_ex99_1.html", dt.date(2026, 7, 28)),
        ("NNN", "nnn_8k_q2_2026_ex99_1.html", dt.date(2026, 8, 5)),
        ("O", "o_8k_q2_2026_ex99_1.html", dt.date(2026, 8, 5)),
    ],
)
def test_la_ficha_cubre_su_propio_filing_sin_recurrir_a_los_patrones(
    ticker, fixture, publicacion
):
    """Una ficha completa no deja huecos: si los deja, el parser lo advierte.

    Es la métrica de completitud de la ficha, y se mide contra el documento real
    del emisor, no contra una lista escrita a mano.
    """
    extracciones = parsear_conciliacion(
        (FIXTURES / fixture).read_text(), ticker, publicacion, "f"
    )
    assert extracciones, f"El fixture de {ticker} no produjo extracciones."
    huecos = [a for x in extracciones for a in x.advertencias if "no declara" in a]
    assert not huecos, f"La ficha de {ticker} está incompleta: {huecos[0]}"


def test_las_fichas_cubren_a_los_emisores_que_cuadran():
    """Los cuatro emisores que validan completo tienen ficha; es su estado esperado."""
    assert {"O", "NNN", "ADC", "WPC"} <= set(FICHAS)
    assert ficha_de("wpc") is not None, "La búsqueda no debe depender de mayúsculas."
    assert ficha_de("NOEXISTE") is None
