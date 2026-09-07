"""Prueba 21 — Seis descuadres de 2024, y las cuatro causas detrás.

Seis periodos de 2024 no cuadraban: dos de Agree Realty, dos de Extra Space y dos
de W. P. Carey. Se veían como un mismo síntoma —"el subtotal reportado no coincide
con la suma de sus partidas"— y no tenían una sola causa, sino cuatro, de dos
naturalezas distintas.

Una es del PARSER, y era la peor de las cuatro porque no perdía datos: los movía.
Las otras tres son de TAXONOMÍA: partidas reales del puente que ninguna ficha
declaraba, cada una con un nombre que solo usa su emisor.

1. **El espacio de ancho cero.** Agree Realty maqueta su conciliación con `&#8203;`
   en las celdas vacías. `str.strip()` no lo quita —no es espacio en blanco para
   Python— así que una celda que se ve vacía llega como celda NO vacía y ocupa una
   posición. Las filas que traen "$" gastan una celda en el símbolo y las demás la
   gastan en un ancho cero, de modo que las filas de una MISMA tabla salían de
   largos distintos y "columna i → periodo i" le ponía a cada periodo la cifra del
   vecino. El trimestre de 2024 se quedaba con el FFO de 2025.

2. **La pérdida por activos mantenidos para la venta** (Extra Space). No es una
   venta: es la baja a valor razonable de un activo reclasificado, o sea un
   deterioro, que Nareit suma de vuelta al FFO.

3. **La ganancia por cambio de control** (W. P. Carey). Tampoco es una venta: es la
   remedición de una participación cuando cambia el control. Nareit la excluye
   igual, y por eso hay que restarla.

4. **La nota al pie entre corchetes.** Global Net Lease renumera sus notas en cada
   reporte —``[2]``, ``[3]``, ``[4]``—, y la canonización quitaba el corchete pero
   dejaba el número, así que la misma línea cambiaba de identidad cada trimestre.
   Su ficha había acumulado cuatro variantes de un solo renglón persiguiéndolas.

La prueba 21 fija las cuatro contra los documentos reales.
"""

from __future__ import annotations

import datetime as dt

import pytest
from bs4 import BeautifulSoup

from src.ingesta.parser_affo import (
    _tabla_a_matriz,
    _texto_celda,
    parsear_conciliacion,
    resolver_etiqueta,
)
from src.ingesta.taxonomia import canonizar
from src.validacion.cuadre import cuadrar_conciliacion, elegir_mejor_conciliacion

ANCHO_CERO = "​"


# --------------------------------------------------------------------------------------
# 21.1 El espacio de ancho cero: una celda que se ve vacía y no lo está
# --------------------------------------------------------------------------------------


def test_la_celda_de_ancho_cero_queda_vacia():
    """`str.strip()` no lo quita, y por eso hay que quitarlo aparte."""
    assert not ANCHO_CERO.isspace(), (
        "si Python empezara a considerarlo espacio, esta defensa sobra"
    )
    assert ANCHO_CERO.strip() == ANCHO_CERO

    celda = BeautifulSoup(f"<td>{ANCHO_CERO}</td>", "lxml").td
    assert _texto_celda(celda) == ""


def test_las_filas_de_una_tabla_salen_todas_del_mismo_largo():
    """El defecto real de Agree Realty, en miniatura.

    Una fila gasta una celda en el "$" y la siguiente la gasta en un ancho cero.
    Si el ancho cero cuenta, las dos filas quedan de largos distintos y repartir
    "columna i → periodo i" le da a cada periodo la cifra del vecino — sin que
    ninguna suma proteste, porque cada número por separado sigue siendo plausible.
    """
    html = f"""
    <table>
      <tr><td>Net income</td><td>{ANCHO_CERO}</td><td>$</td><td>52,279</td>
          <td>{ANCHO_CERO}</td><td>$</td><td>44,528</td></tr>
      <tr><td>Depreciation</td><td>{ANCHO_CERO}</td><td>{ANCHO_CERO}</td><td>40,867</td>
          <td>{ANCHO_CERO}</td><td>{ANCHO_CERO}</td><td>33,941</td></tr>
    </table>
    """
    matriz = _tabla_a_matriz(BeautifulSoup(html, "lxml").table)
    from src.ingesta.parser_affo import _valores_alineados

    largos = {len(_valores_alineados(fila)) for fila in matriz}
    assert len(largos) == 1, f"filas desparejas: {largos}"
    assert [_valores_alineados(f) for f in matriz] == [
        [52279.0, 44528.0],
        [40867.0, 33941.0],
    ]


def test_agree_realty_2024_cuadra_y_no_hereda_las_cifras_de_2025(html_8k_agree_q3):
    """Contra el filing real: cuatro periodos, cada uno con lo suyo.

    Antes salían solo dos extracciones de esta tabla y las dos con la etiqueta de
    2024: una traía las cifras de 2025 y la otra las de 2024. El trimestre de 2025
    no es que estuviera mal — es que no existía.
    """
    extracciones = elegir_mejor_conciliacion(
        parsear_conciliacion(html_8k_agree_q3, "ADC", dt.date(2025, 10, 21), "fixture")
    )
    por_periodo = {e.periodo.etiqueta: e for e in extracciones}
    assert set(por_periodo) == {
        "Q 2025-09-30", "Q 2024-09-30", "9M 2025-09-30", "9M 2024-09-30",
    }

    # Las cifras que publica el emisor, cada una en su columna.
    assert por_periodo["Q 2025-09-30"].lineas["ffo"] == pytest.approx(112_926_000)
    assert por_periodo["Q 2024-09-30"].lineas["ffo"] == pytest.approx(94_566_000)
    assert por_periodo["9M 2025-09-30"].lineas["ffo"] == pytest.approx(324_321_000)
    assert por_periodo["9M 2024-09-30"].lineas["ffo"] == pytest.approx(284_004_000)

    fallidos = [
        f"{etq}: {cuadrar_conciliacion(e.lineas, e.orden).motivo}"
        for etq, e in por_periodo.items()
        if not cuadrar_conciliacion(e.lineas, e.orden).cuadra
    ]
    assert not fallidos, "\n".join(fallidos)


# --------------------------------------------------------------------------------------
# 21.2 Dos partidas que no son ventas, y una que cambió de nombre
# --------------------------------------------------------------------------------------


def test_la_perdida_por_activos_mantenidos_para_la_venta_es_deterioro():
    """Extra Space: 8,961 miles en el trimestre y 63,620 en los nueve meses.

    Reclasificar un activo a "mantenido para la venta" lo lleva al menor entre su
    valor en libros y su valor razonable menos costos de venta. Esa baja es un
    deterioro —no hay venta todavía— y Nareit la suma de vuelta al FFO.
    """
    clave, declarada = resolver_etiqueta("EXR", "Loss on real estate assets held for sale")
    assert (clave, declarada) == ("deterioro", True)

    # Y no se confunde con la que SÍ es una venta, que va con signo contrario.
    vendidos, _ = resolver_etiqueta(
        "EXR", "(Gain) loss on real estate assets held for sale and sold, net"
    )
    assert vendidos == "ganancia_venta_inmuebles"


def test_la_ganancia_por_cambio_de_control_no_es_una_venta():
    """W. P. Carey: 31,849 miles, y solo en el tercer trimestre de 2024.

    Cuando una participación pasa de método de participación a consolidada, la
    remedición produce una ganancia. No se vendió nada, pero es igual de
    irrepetible, y Nareit la excluye del FFO igual que a una ganancia por venta.
    """
    clave, declarada = resolver_etiqueta("WPC", "Gain on change in control of interests (a)")
    assert (clave, declarada) == ("ganancia_venta_inmuebles", True)


def test_global_net_lease_renombro_su_renglon_de_costos():
    """"Merger" en 2025, "Acquisition" en 2026, la misma partida del puente."""
    for redaccion in (
        "Merger, transaction and other costs",
        "Acquisition, transaction and other costs",
    ):
        clave, declarada = resolver_etiqueta("GNL", redaccion)
        assert (clave, declarada) == ("partidas_no_recurrentes", True), redaccion


def test_public_storage_declara_sus_partidas_de_una_sola_vez():
    """Las cuatro que le faltaban, cada una con su descuadre exacto detrás."""
    esperado = {
        "Hiring bonus for a new senior executive": "partidas_no_recurrentes",
        "Contingency reserve": "partidas_no_recurrentes",
        "Income tax provision (benefit)": "partidas_no_recurrentes",
        "CEO transition costs": "partidas_no_recurrentes",
    }
    for etiqueta, clave in esperado.items():
        assert resolver_etiqueta("PSA", etiqueta) == (clave, True), etiqueta


# --------------------------------------------------------------------------------------
# 21.3 La nota al pie entre corchetes
# --------------------------------------------------------------------------------------


def test_la_nota_al_pie_entre_corchetes_no_distingue_una_linea_de_otra():
    """Un corchete es una nota al pie igual que un paréntesis, y se quita igual.

    `[^a-z0-9\\s-]` borraba el corchete pero dejaba el número dentro, así que la
    misma línea con la nota renumerada quedaba como dos etiquetas distintas.
    """
    base = "Eliminate losses related to multi-tenant disposition receivable"
    formas = {canonizar(f"{base} [{n}]") for n in (2, 3, 4, 5, 11)}
    assert len(formas) == 1, formas
    assert canonizar(base) in formas


def test_global_net_lease_resuelve_su_renglon_con_cualquier_nota():
    """El caso que obligó a la ficha a cargar cuatro variantes del mismo renglón."""
    for n in (2, 3, 4, 5):
        clave, declarada = resolver_etiqueta(
            "GNL", f"Eliminate (gains) losses related to multi-tenant disposition receivable [{n}]"
        )
        assert (clave, declarada) == ("partidas_no_recurrentes", True), n


def test_quitar_la_nota_no_borra_lo_que_si_distingue():
    """Control: dos líneas distintas del mismo emisor siguen siendo distintas."""
    a = canonizar("Eliminate losses related to multi-tenant disposition receivable [4]")
    b = canonizar("Eliminate deferred tax expense related to the disposition of the "
                  "McLaren Campus [2]")
    assert a != b
    # Y un paréntesis con contenido real tampoco se lleva la etiqueta por delante.
    assert canonizar("Net income (loss) attributable to common stockholders").startswith(
        "net income"
    )


# --------------------------------------------------------------------------------------
# 21.4 Contra el repositorio entero
# --------------------------------------------------------------------------------------


# Un documento real por emisor, con su fecha de publicación. La semilla de pruebas
# no trae conciliaciones —es una base sintética de precios y hechos—, así que una
# prueba "contra el repositorio" apoyada en ella se salta siempre y da una
# tranquilidad falsa. Estos filings sí los publicó la SEC.
FILINGS = [
    ("O", "o_8k_q2_2026_ex99_1.html", dt.date(2026, 8, 5)),
    ("NNN", "nnn_8k_q2_2026_ex99_1.html", dt.date(2026, 8, 4)),
    ("WPC", "wpc_8k_q2_2026_ex99_1.html", dt.date(2026, 7, 29)),
    ("ADC", "adc_8k_q3_2025_ex99_1.html", dt.date(2025, 10, 21)),
    ("PLD", "pld_8k_q2_2026_ex99_1.html", dt.date(2026, 7, 16)),
]


@pytest.mark.parametrize(("ticker", "archivo", "publicacion"), FILINGS)
def test_todo_periodo_de_todo_filing_cuadra(request, ticker, archivo, publicacion):
    """La condición de salida, medida contra los documentos y no estimada.

    Cada periodo que el parser extrae tiene que reproducir los subtotales que el
    propio emisor publica. No se compara contra una cifra que elegimos nosotros.
    """
    ruta = request.path.parent / "fixtures" / archivo
    if not ruta.exists():
        pytest.skip(f"Falta el fixture {archivo}.")

    extracciones = elegir_mejor_conciliacion(
        parsear_conciliacion(ruta.read_text(encoding="utf-8"), ticker, publicacion, "fixture")
    )
    assert extracciones, f"{ticker}: el documento se leyó como vacío"

    fallidos = [
        f"{e.periodo.etiqueta}: {cuadrar_conciliacion(e.lineas, e.orden).motivo}"
        for e in extracciones
        if not cuadrar_conciliacion(e.lineas, e.orden).cuadra
    ]
    assert not fallidos, f"{ticker} no cuadra en:\n" + "\n".join(fallidos)


@pytest.mark.parametrize(("ticker", "archivo", "publicacion"), FILINGS)
def test_el_cuadre_de_cada_filing_verifica_algo(request, ticker, archivo, publicacion):
    """Control: un cuadre sin partidas que sumar pasa siempre y no prueba nada."""
    ruta = request.path.parent / "fixtures" / archivo
    if not ruta.exists():
        pytest.skip(f"Falta el fixture {archivo}.")

    extracciones = elegir_mejor_conciliacion(
        parsear_conciliacion(ruta.read_text(encoding="utf-8"), ticker, publicacion, "fixture")
    )
    verificados = sum(
        len(cuadrar_conciliacion(e.lineas, e.orden).tramos_verificados) for e in extracciones
    )
    assert verificados >= len(extracciones), (
        f"{ticker}: {verificados} tramos verificados para {len(extracciones)} periodos; "
        "el cuadre está pasando en vacío"
    )
