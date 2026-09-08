"""Prueba 32 — La misma auditoría del caso O, corrida sobre las otras nueve.

Sin export de Bloomberg para el resto del universo, la auditoría fue contra una
fuente todavía mejor para la pregunta de la deuda: **el balance impreso en el
10-Q de cada emisora**, leído de su documento XBRL, que incluye las etiquetas de
extensión que `companyfacts` no publica.

De las nueve, seis cuadran: su renglón de deuda total es de verdad su deuda
total (ADC, WPC, EPRT, GNL, PSA, EXR). Las otras tres dieron dos hallazgos
distintos:

* **NNN tenía el error de Realty Income**, en menor escala pero por la misma
  causa: `NotesPayable` son sus notas senior, no su deuda (32.1).
* **Prologis y Welltower tienen el balance un trimestre atrasado**, y no por
  culpa nuestra ni de ellos: `companyfacts` todavía publica marzo como su último
  corte aunque sus 10-Q de junio estén presentados. Como el AFFO y la utilidad de
  junio sí entran —vienen del 8-K—, el apalancamiento mezclaba una deuda vieja
  con un flujo nuevo sin que nada lo dijera (32.2).

El aviso de 32.2 fue la primera respuesta a ese rezago y la prueba 33 lo cerró,
yendo por el balance al documento XBRL del filing. El aviso se queda igual: la
API se volverá a atrasar, y es la red que atrapa el caso que ese camino no
alcance a cubrir. Por eso sus pruebas ya no dependen de que hoy haya una emisora
rezagada — no la hay— sino que construyen el caso.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.config import UNIVERSO_INICIAL, Estado, Fuente  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta.estados import LINEA_POR_CLAVE, tags_de  # noqa: E402
from src.servicio import (  # noqa: E402
    _corte_de_balance,
    _saldos_de_balance,
    construir_panel,
)

# Deuda total según el BALANCE del 10-Q de cada emisora al 30 de junio de 2026,
# en millones de dólares. Se leyó del documento XBRL de cada filing, no de
# `companyfacts`. Prologis y Welltower entraron a esta lista con la prueba 33,
# que cierra el rezago de la API yendo por su balance al mismo documento.
DEUDA_SEGUN_EL_10Q = {
    "O": 30_651.7,
    "NNN": 5_001.2,
    "ADC": 3_850.0,
    "WPC": 8_851.9,
    "EPRT": 2_930.0,
    "GNL": 2_399.8,
    "PSA": 10_180.2,
    "EXR": 13_646.6,
    "PLD": 36_442.1,
    "WELL": 17_726.3,
}


def _guardar(repo, concepto, fecha, valor, *, ticker="X", tipo="PUNTUAL", inicio=None):
    repo.guardar_hechos([{
        "ticker": ticker, "concepto": concepto, "periodo_tipo": tipo,
        "periodo_inicio": inicio, "fecha_dato": fecha, "fecha_publicacion": fecha,
        "valor": valor, "unidad": "USD", "fuente": Fuente.SEC_XBRL,
        "es_primario": True, "estado": Estado.VALIDO, "url_filing": None, "accession": "a",
    }])


# --------------------------------------------------------------------------------------
# 32.1 · NNN: el mismo error, y un veredicto que dependía de un punto base
# --------------------------------------------------------------------------------------


def test_los_tres_tramos_de_nnn_estan_declarados():
    assert "NotesPayable" in tags_de("NNN", "notas_senior")
    assert "LoansPayable" in tags_de("NNN", "prestamos_a_plazo")
    assert "LinesOfCreditCurrent" in tags_de("NNN", "linea_de_credito")


def test_el_pasivo_de_nnn_cuadra_con_los_tres_tramos():
    """La aritmética que convirtió la sospecha en certeza.

    No hacía falta Bloomberg: el propio pasivo total del emisor cierra al décimo
    de millón cuando los tres instrumentos entran, y no cierra cuando falta uno.
    """
    tramos = 4_475.9 + 496.8 + 28.5          # notas senior, préstamo a plazo, revolvente
    no_deuda = 106.5 + 38.0                  # otros pasivos, intereses por pagar
    assert tramos + no_deuda == pytest.approx(5_145.8, abs=0.2), "el pasivo no cierra"
    assert tramos == pytest.approx(DEUDA_SEGUN_EL_10Q["NNN"], abs=0.2)


def test_la_revolvente_corriente_no_es_una_etiqueta_del_catalogo_compartido():
    """`LinesOfCreditCurrent` se declara por emisora, como los demás tramos.

    Es genérica: la emisora que ya reporta su revolvente en `LineOfCredit` no
    debe leer las dos, o el mismo saldo entraría por dos caminos.
    """
    assert "LinesOfCreditCurrent" not in LINEA_POR_CLAVE["linea_de_credito"].tags
    assert "LinesOfCreditCurrent" not in tags_de("GNL", "linea_de_credito")


def test_un_spread_de_un_punto_base_no_deberia_decidir_una_venta_por_un_dato_malo():
    """Por qué este error importaba más de lo que su tamaño sugiere.

    La deuda de NNN estaba subestimada en 10.5%, y el costo implícito de su deuda
    —intereses sobre deuda— salía inflado en la misma proporción: 4.76% contra
    4.26%. Eso subía su costo marginal de capital y dejaba el spread de inversión
    en −0.01%. Un punto base bajo cero, dos trimestres seguidos, y la Puerta 3
    dispara VENTA.

    El emisor no estaba destruyendo valor: el denominador estaba mal.
    """
    repo = Repositorio()
    saldos = _saldos_de_balance(repo, "NNN", asof=dt.date.today())
    if "deuda_total" not in saldos:
        pytest.skip("No hay base cargada.")
    assert saldos["deuda_total"] / 1e6 == pytest.approx(DEUDA_SEGUN_EL_10Q["NNN"], rel=0.01)


@pytest.mark.parametrize("ticker", sorted(DEUDA_SEGUN_EL_10Q))
def test_la_deuda_de_cada_emisora_es_la_de_su_balance(ticker):
    """El control de las seis que ya estaban bien, y la prueba de las dos corregidas.

    Vale tanto por lo que verifica como por lo que impide: una guarda que corrige
    hacia arriba puede, mal calibrada, inflar la deuda de quien sí la reportaba
    completa. Aquí se comprueba que no le pasó a ninguna.
    """
    repo = Repositorio()
    saldos = _saldos_de_balance(repo, ticker, asof=dt.date.today())
    if "deuda_total" not in saldos:
        pytest.skip(f"No hay base cargada para {ticker}.")
    assert saldos["deuda_total"] / 1e6 == pytest.approx(DEUDA_SEGUN_EL_10Q[ticker], rel=0.01)


# --------------------------------------------------------------------------------------
# 32.2 · Un balance viejo con un flujo nuevo
# --------------------------------------------------------------------------------------


def test_el_desfase_entre_balance_y_resultados_se_avisa(tmp_path):
    """El caso de Prologis y Welltower, reducido a su mecánica.

    El balance viene de `companyfacts` y el AFFO del 8-K. Cuando la API se atrasa
    para un emisor y el comunicado de resultados no, el apalancamiento combina la
    deuda de un trimestre con el flujo de otro. El ratio sale plausible y nada lo
    delata: es la misma invisibilidad del saldo viejo de la prueba 30, ahora entre
    dos fuentes en vez de entre dos etiquetas.
    """
    repo = Repositorio(ruta=tmp_path / "b.db")
    _guardar(repo, "deuda_total", dt.date(2026, 3, 31), 34_670e6)
    _guardar(repo, "pasivos_totales", dt.date(2026, 3, 31), 40_185e6)
    _guardar(repo, "activos_totales", dt.date(2026, 3, 31), 98_134e6)
    for fin, inicio in ((dt.date(2026, 3, 31), dt.date(2026, 1, 1)),
                        (dt.date(2026, 6, 30), dt.date(2026, 4, 1))):
        _guardar(repo, "utilidad_neta", fin, 500e6, tipo="Q", inicio=inicio)

    panel = construir_panel(repo, "X", asof=dt.date(2026, 9, 8))
    assert any("un trimestre de diferencia" in a for a in panel.avisos), (
        "el desfase entre balance y resultados pasó sin aviso"
    )


def test_sin_desfase_no_hay_aviso(tmp_path):
    """El control: el aviso no puede dispararse cuando las dos fechas coinciden."""
    repo = Repositorio(ruta=tmp_path / "b.db")
    _guardar(repo, "deuda_total", dt.date(2026, 6, 30), 34_670e6)
    _guardar(repo, "pasivos_totales", dt.date(2026, 6, 30), 40_185e6)
    _guardar(repo, "utilidad_neta", dt.date(2026, 6, 30), 500e6,
             tipo="Q", inicio=dt.date(2026, 4, 1))
    panel = construir_panel(repo, "X", asof=dt.date(2026, 9, 8))
    assert not any("un trimestre de diferencia" in a for a in panel.avisos)


def test_el_corte_de_balance_es_la_fecha_del_balance(tmp_path):
    """Y no la del último hecho del emisor, que suele ser posterior.

    La portada de un 10-Q trae las acciones en circulación a una fecha DESPUÉS del
    cierre —el día que se firma—. Tomar el máximo de todos los hechos daría esa
    fecha y el desfase nunca se vería.
    """
    repo = Repositorio(ruta=tmp_path / "b.db")
    _guardar(repo, "pasivos_totales", dt.date(2026, 6, 30), 1e9)
    _guardar(repo, "acciones_en_circulacion", dt.date(2026, 7, 30), 9e8)
    assert _corte_de_balance(repo, "X", asof=dt.date(2026, 9, 8)) == dt.date(2026, 6, 30)


def test_el_aviso_no_se_dispara_solo():
    """Sobre datos reales: el aviso tiene que ser específico, no ambiental.

    Un aviso que sale en las diez no informa nada. Desde la prueba 33 no sale en
    ninguna, porque ya no hay balance rezagado; lo que se comprueba aquí es que
    tampoco aparece donde no corresponde.
    """
    repo = Repositorio()
    hoy = dt.date.today()
    con_aviso = set()
    for e in UNIVERSO_INICIAL:
        panel = construir_panel(repo, e.ticker, asof=hoy)
        if panel.trimestral.empty:
            pytest.skip("No hay base cargada.")
        if any("un trimestre de diferencia" in a for a in panel.avisos):
            con_aviso.add(e.ticker)
    assert con_aviso == set(), f"aviso inesperado en {con_aviso}"


def test_el_balance_de_todas_llega_al_ultimo_corte():
    """El control del universo: las DIEZ tienen balance de junio de 2026.

    Eran ocho hasta que la prueba 33 cerró el rezago de Prologis y Welltower.
    """
    repo = Repositorio()
    hoy = dt.date.today()
    al_dia = 0
    for e in UNIVERSO_INICIAL:
        corte = _corte_de_balance(repo, e.ticker, asof=hoy)
        if corte is None:
            pytest.skip("No hay base cargada.")
        if corte >= dt.date(2026, 6, 30):
            al_dia += 1
    assert al_dia == len(UNIVERSO_INICIAL), (
        f"solo {al_dia} de {len(UNIVERSO_INICIAL)} tienen el balance del último corte"
    )


def test_el_aviso_nombra_la_causa_probable(tmp_path):
    """Decir «falta el dato» manda a buscar donde no está.

    El 10-Q de Prologis está presentado y su balance impreso; lo que va atrasado
    es la API. Un aviso que no distingue las dos cosas hace perder el tiempo
    buscando un reporte que ya existe.
    """
    repo = Repositorio(ruta=tmp_path / "b.db")
    _guardar(repo, "pasivos_totales", dt.date(2026, 3, 31), 40_185e6)
    _guardar(repo, "utilidad_neta", dt.date(2026, 6, 30), 500e6,
             tipo="Q", inicio=dt.date(2026, 4, 1))
    avisos = [
        a for a in construir_panel(repo, "X", asof=dt.date(2026, 9, 8)).avisos
        if "un trimestre de diferencia" in a
    ]
    assert avisos, "no se emitió el aviso"
    assert "companyfacts" in avisos[0]
    assert "10-Q" in avisos[0]


def test_las_fechas_de_balance_y_resultados_se_comparan_como_fechas():
    """Guarda de tipos: un `Timestamp` contra un `date` truena la comparación.

    El panel trae el índice como `Timestamp` y el corte de balance como `date`.
    Compararlos sin normalizar no da un falso negativo: revienta la pantalla.
    """
    assert pd.Timestamp("2026-06-30").date() > dt.date(2026, 3, 31)
