"""Prueba 20 — La conciliación que no viene en una tabla.

Prologis presenta su suplemento trimestral como **imágenes**: 46 archivos `.jpg`,
una por diapositiva. Junto a cada imagen, el agente de presentación incrusta el
texto completo de esa página en un ``<font>`` blanco de 1 punto —la capa de texto
buscable del PDF—. La conciliación entera está ahí, cifra por cifra, con sus
cuatro columnas y sus cuatro subtotales.

Para un parser que recorre ``<table>``, ese documento está vacío. No levanta
excepción, no descuadra nada, no aparece en ningún error: simplemente devuelve
cero. Así es como la única emisora industrial del universo pasó meses sin llegar
a la pantalla, y así es como el diagnóstico se fue por el camino equivocado
—"el localizador de exhibits no encuentra su comunicado"—, cuando el localizador
los encontraba los dos y era el parser el que no sabía leerlos.

El texto plano SÍ tiene estructura, y es la que estas pruebas fijan: cada partida
es una etiqueta seguida de exactamente tantos importes como columnas tenga la
página. Con ese invariante se reconstruye la matriz y de ahí en adelante corre el
mismo camino que cualquier tabla.

**Lo que se descarta importa tanto como lo que se lee.** Un suplemento trae
decenas de páginas y varias mencionan el FFO sin conciliar nada. La más peligrosa
es el resumen de "Company Performance Highlights", porque sus cifras se parecen a
las buenas: 1,323 millones donde la conciliación dice 1,322,967 miles. Leerla
como conciliación no rompe ninguna suma —redondea— y mete a la base una cifra que
no es la que el emisor concilió.
"""

from __future__ import annotations

import datetime as dt

import pytest
from bs4 import BeautifulSoup

from src.ingesta.parser_affo import (
    _encabezado_de_pagina,
    _es_ranura,
    _etiqueta_de_partida,
    _matriz_de_texto_plano,
    _paginas_de_texto_plano,
    detectar_periodos,
    parsear_conciliacion,
)
from src.validacion.cuadre import cuadrar_conciliacion, elegir_mejor_conciliacion

PUBLICACION = dt.date(2026, 7, 16)


@pytest.fixture
def html_suplemento_prologis(request) -> str:
    """Extracto real del Exhibit 99.1 del 8-K de Prologis del 2026-07-16.

    Conserva la capa de texto de cuatro páginas: la conciliación y tres señuelos
    —el resumen de desempeño, la guía y el estado de resultados—, que es lo que
    hace de esto una prueba y no una demostración.
    """
    ruta = request.path.parent / "fixtures" / "pld_8k_q2_2026_ex99_1.html"
    if not ruta.exists():
        pytest.skip("Falta el fixture del suplemento de Prologis.")
    return ruta.read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------
# 20.1 La reconstrucción de renglones desde un párrafo corrido
# --------------------------------------------------------------------------------------


def test_una_partida_es_una_etiqueta_y_sus_columnas():
    """El invariante del que cuelga todo: N importes cierran un renglón."""
    filas = _matriz_de_texto_plano(
        "Net earnings attributable to common stockholders $ 1,060,844 $ 569,724 "
        "$ 2,041,320 $ 1,161,225 "
        "Real estate related depreciation and amortization 663,658 638,199 1,369,208 1,270,885",
        4,
    )
    assert filas == [
        ["Net earnings attributable to common stockholders",
         "1,060,844", "569,724", "2,041,320", "1,161,225"],
        ["Real estate related depreciation and amortization",
         "663,658", "638,199", "1,369,208", "1,270,885"],
    ]


def test_el_guion_ocupa_columna():
    """Un guion es una celda vacía, no texto.

    Tratarlo como parte de la etiqueta corre todos los importes de ese renglón una
    posición a la izquierda: el segundo trimestre se queda con la cifra del tercero
    y nadie lo nota, porque cada número por separado sigue siendo plausible.
    """
    filas = _matriz_de_texto_plano("Venture formation costs 6,049 – 6,049 –", 4)
    assert filas == [["Venture formation costs", "6,049", "–", "6,049", "–"]]

    assert _es_ranura("–") and _es_ranura("(215)") and _es_ranura("1,060,844")


def test_el_dia_del_encabezado_no_es_un_importe():
    """"June 30," lleva coma al final: es una fecha, no una cifra.

    Sin esta distinción el encabezado consume columnas y desplaza el renglón de
    los años, que es de donde salen los periodos.
    """
    assert not _es_ranura("30,")
    assert not _es_ranura("June")
    assert _es_ranura("30")


def test_el_encabezado_de_tramo_no_se_come_la_partida():
    """En texto plano no hay renglón que los separe, así que llegan pegados."""
    pegadas = ["Add", "(deduct)", "AFFO", "defined", "adjustments:", "Property", "improvements"]
    assert _etiqueta_de_partida(pegadas) == "Property improvements"
    # Y una etiqueta sin dos puntos se queda entera.
    assert _etiqueta_de_partida(["Turnover", "costs"]) == "Turnover costs"


def test_un_anio_suelto_en_los_datos_no_agrega_una_columna():
    """Los periodos se cuentan en el encabezado, no en toda la página.

    El número de columnas gobierna la reconstrucción entera: si se cuenta uno de
    más, cada renglón se cierra un importe más tarde y TODA la tabla se desalinea
    a la vez. Un año suelto en una etiqueta —"Senior notes due 2031"— basta para
    provocarlo si los periodos se detectan sobre el texto completo, y el resultado
    no levanta excepción ni descuadra ninguna suma por sí solo.
    """
    pagina = (
        "Reconciliations of Net Earnings to FFO Three Months Ended June 30, "
        "in thousands 2026 2025 "
        "Net earnings 1,000 900 "
        "Loss on redemption of the senior notes due 2031 50 40 "
        "FFO 1,050 940"
    )
    assert len(detectar_periodos(_encabezado_de_pagina(pagina))) == 2
    assert len(detectar_periodos(pagina)) != 2, (
        "sin el corte, el año de la etiqueta se cuenta como un periodo más"
    )

    filas = _matriz_de_texto_plano(pagina, len(detectar_periodos(_encabezado_de_pagina(pagina))))
    assert ["Net earnings", "1,000", "900"] in filas
    assert ["FFO", "1,050", "940"] in filas


def test_un_renglon_incompleto_no_arrastra_su_desfase():
    """Si faltan columnas, el renglón se cierra donde está y el siguiente arranca limpio."""
    filas = _matriz_de_texto_plano("Partida corta 10 20 Partida completa 1 2 3", 3)
    assert filas == [["Partida corta", "10", "20"], ["Partida completa", "1", "2", "3"]]


# --------------------------------------------------------------------------------------
# 20.2 Contra el documento real
# --------------------------------------------------------------------------------------


def test_prologis_cuadra_en_sus_cuatro_periodos(html_suplemento_prologis):
    """La prueba que importa: el suplemento real, sin una sola tabla HTML."""
    assert "<table" not in html_suplemento_prologis.lower(), (
        "el fixture dejó de ser el caso que esta prueba cubre"
    )

    extracciones = parsear_conciliacion(
        html_suplemento_prologis, "PLD", PUBLICACION, "fixture"
    )
    assert extracciones, "el documento se leyó como vacío, que es el defecto original"

    mejores = elegir_mejor_conciliacion(extracciones)
    fallidos = [
        f"{e.periodo.etiqueta}: {cuadrar_conciliacion(e.lineas, e.orden).motivo}"
        for e in mejores
        if not cuadrar_conciliacion(e.lineas, e.orden).cuadra
    ]
    assert not fallidos, "Periodos que no cuadran:\n" + "\n".join(fallidos)
    assert {e.periodo.etiqueta for e in mejores} == {
        "Q 2026-06-30", "Q 2025-06-30", "H1 2026-06-30", "H1 2025-06-30",
    }


def test_las_cifras_son_las_del_filing(html_suplemento_prologis):
    """Contra el documento, no contra lo que el parser produjo la última vez."""
    q2 = next(
        e for e in elegir_mejor_conciliacion(
            parsear_conciliacion(html_suplemento_prologis, "PLD", PUBLICACION, "fixture")
        )
        if e.periodo.etiqueta == "Q 2026-06-30"
    )
    assert q2.lineas["utilidad_neta"] == pytest.approx(1_060_844_000)
    assert q2.lineas["ffo"] == pytest.approx(1_632_356_000)
    assert q2.lineas["ffo_normalizado"] == pytest.approx(1_559_127_000)
    assert q2.lineas["affo"] == pytest.approx(1_322_967_000)


def test_prologis_publica_las_tres_trampas(html_suplemento_prologis):
    """Renta en línea recta, CapEx de mantenimiento y comisiones de arrendamiento.

    Prologis las llama "Straight-lined rents", "Property improvements" y "Turnover
    costs". Sin la ficha, las tres se pierden en el genérico de otros ajustes y el
    puente al AFFO deja de ser auditable justo donde más se manipula.
    """
    from src.modelo.cascada import valor_del_concepto

    q2 = next(
        e for e in elegir_mejor_conciliacion(
            parsear_conciliacion(html_suplemento_prologis, "PLD", PUBLICACION, "fixture")
        )
        if e.periodo.etiqueta == "Q 2026-06-30"
    )
    assert valor_del_concepto(q2.lineas, "renta_linea_recta") == pytest.approx(-161_152_000)
    assert valor_del_concepto(q2.lineas, "capex_mantenimiento") == pytest.approx(-71_218_000)
    assert valor_del_concepto(q2.lineas, "comisiones_arrendamiento") == pytest.approx(
        -133_959_000
    )


def test_el_subtotal_intermedio_de_prologis_no_parte_el_tramo(html_suplemento_prologis):
    """Prologis publica CUATRO subtotales; la cascada tiene tres escalones.

    "FFO, as modified by Prologis" va entre el FFO de Nareit y el Core FFO. Se
    declara IGNORAR a propósito: así las partidas de los dos puentes se acumulan en
    un solo tramo, que cierra exacto contra el Core FFO que el emisor publica.
    Meterlo a la fuerza partiría el tramo en dos y ninguna de las mitades cuadraría.
    """
    q2 = next(
        e for e in elegir_mejor_conciliacion(
            parsear_conciliacion(html_suplemento_prologis, "PLD", PUBLICACION, "fixture")
        )
        if e.periodo.etiqueta == "Q 2026-06-30"
    )
    assert not [k for k in q2.lineas if "modified" in k.lower()]
    assert cuadrar_conciliacion(q2.lineas, q2.orden).cuadra


# --------------------------------------------------------------------------------------
# 20.3 Lo que NO se lee
# --------------------------------------------------------------------------------------


def test_solo_se_lee_la_pagina_que_se_anuncia_como_conciliacion(html_suplemento_prologis):
    """El fixture trae cinco páginas y solo una concilia algo."""
    sopa = BeautifulSoup(html_suplemento_prologis, "lxml")
    paginas = _paginas_de_texto_plano(sopa)
    assert len(paginas) == 1, [p[:60] for p in paginas]
    assert paginas[0].startswith("Reconciliations of Net Earnings to FFO")


def test_el_pie_de_pagina_no_hace_de_una_pagina_una_conciliacion(html_suplemento_prologis):
    """Casi toda página de un suplemento remite a "Please see reconciliations".

    El resumen de desempeño de 2024 lo pone justo detrás de un título de dos
    palabras —"Company Performance * This is a non-GAAP financial measure. Please
    see reconciliations..."—, así que la palabra cae en la décima posición. Con una
    ventana ancha ese resumen vuelve a entrar, y con él sus cifras redondeadas: es
    exactamente cómo el cuarto trimestre de 2023 dejó de cuadrar.
    """
    sopa = BeautifulSoup(html_suplemento_prologis, "lxml")
    resumen = next(
        " ".join(b.get_text(" ", strip=True).split())
        for b in sopa.find_all(["p", "font"])
        if b.get_text(" ", strip=True).strip().startswith("Company Performance *")
    )
    # La palabra cae fuera del título pero dentro de una ventana ancha: ahí está
    # todo el filo de esta prueba.
    posicion = resumen.split().index("reconciliations")
    assert 6 <= posicion < 12, f"el señuelo cambió de forma: la palabra va en {posicion}"

    assert not [p for p in _paginas_de_texto_plano(sopa) if p.startswith("Company Performance")]


def test_el_resumen_redondeado_no_entra(html_suplemento_prologis):
    """El señuelo peligroso: cifras plausibles, en millones, que nadie concilió.

    "Company Performance Highlights" publica el mismo Core FFO redondeado a
    millones junto a cifras por acción. Si se colara, entraría 1,323,000,000 donde
    el emisor concilió 1,322,967,000, sin que ninguna suma protestara.
    """
    assert "Company Performance Highlights" in html_suplemento_prologis
    valores = {
        v
        for e in parsear_conciliacion(html_suplemento_prologis, "PLD", PUBLICACION, "fixture")
        for v in e.lineas.values()
    }
    assert 1_323_000_000 not in valores
    assert 1_322_967_000 in valores


def test_la_guia_no_entra(html_suplemento_prologis):
    """La guía proyecta un periodo, no concilia uno: tiene su propia tabla en la base."""
    assert "Guidance" in html_suplemento_prologis
    extracciones = parsear_conciliacion(
        html_suplemento_prologis, "PLD", PUBLICACION, "fixture"
    )
    # Las cifras de guía son por acción ($6.07 a $6.23): ninguna puede haber entrado
    # como un importe de la conciliación.
    for e in extracciones:
        for clave, valor in e.lineas.items():
            if not clave.endswith("_por_accion"):
                assert abs(valor) > 1_000, f"{clave}={valor} parece una cifra por acción"


def test_el_texto_plano_es_respaldo_y_no_segunda_opinion():
    """Si el documento trae tablas legibles, la vía de texto plano no corre.

    Releer por texto plano un documento que ya se leyó por tablas duplicaría
    renglones por una vía más frágil. La condición es que el camino normal no haya
    encontrado NADA.
    """
    parrafo = (
        "Reconciliations of Net Earnings to FFO Three Months Ended June 30, in thousands "
        "2026 Net income 999 Depreciation of real estate 999 FFO 1,998 Straight-line rent "
        "(99) AFFO 1,899. " + "Relleno para superar el umbral de longitud del bloque. " * 8
    )
    html = f"""
    <html><body>
    <table>
      <tr><td>Three Months Ended June 30, 2026</td><td>2026</td></tr>
      <tr><td>Net income</td><td>100</td></tr>
      <tr><td>Depreciation of real estate</td><td>250</td></tr>
      <tr><td>FFO</td><td>350</td></tr>
      <tr><td>Straight-line rent</td><td>(30)</td></tr>
      <tr><td>AFFO</td><td>320</td></tr>
    </table>
    <p>{parrafo}</p>
    </body></html>
    """
    # El párrafo pasa por sí solo todas las puertas de la vía de texto plano: si
    # esta prueba lo dejara corto, pasaría por el motivo equivocado.
    assert len(_paginas_de_texto_plano(BeautifulSoup(f"<p>{parrafo}</p>", "lxml"))) == 1

    extracciones = parsear_conciliacion(html, "NNN", PUBLICACION, "fixture")
    valores = {v for e in extracciones for v in e.lineas.values()}
    # Las cifras van escaladas por el "in thousands" del documento.
    assert 350_000 in valores, "no se leyó la tabla, que es el camino normal"
    assert 1_998_000 not in valores, "se leyó además el texto plano y duplicó el documento"
