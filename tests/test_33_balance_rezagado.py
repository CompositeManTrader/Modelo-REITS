"""Prueba 33 — El balance que `companyfacts` todavía no publica.

La prueba 32 dejó a Prologis y Welltower con un aviso: su balance era de marzo y
sus resultados de junio, porque `companyfacts` se atrasa POR EMISOR y sin avisar.
Al 8 de septiembre de 2026 seguía dando marzo como su último corte, más de un mes
después de que las dos presentaran su 10-Q de junio.

Avisar del hueco era mejor que taparlo en silencio, pero no era cerrarlo. Esto lo
cierra yendo por el balance al documento XBRL del propio filing —el mismo camino
que ya se usaba para las etiquetas de extensión de Extra Space y Realty Income—.

Lo que vuelve peligroso ese atraso es que es PARCIAL: el AFFO y la utilidad del
trimestre entran igual porque vienen del 8-K. Así que el apalancamiento combinaba
una deuda de marzo con un flujo de junio, y el ratio salía perfectamente
plausible. Con el balance completo, Welltower pasa de 2.97x a 3.53x — no porque
subiera su deuda, que bajó, sino porque su efectivo cayó de 4,704 MM a 1,965.

Y el camino caro tiene que seguir siendo caro solo donde hace falta: la decisión
de bajar algo se toma con el índice de filings, que es barato, y no se paga una
sola petición cuando la API está al día (33.2).
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

from src.config import UNIVERSO_INICIAL  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta.edgar import Filing  # noqa: E402
from src.ingesta.estados import COLUMNAS_CRUDOS, etiquetas_de_balance  # noqa: E402
from src.ingesta.instancia import (  # noqa: E402
    _ultima_publicacion,
    rellenar_balance_rezagado,
)
from src.servicio import _corte_de_balance, _saldos_de_balance, construir_panel  # noqa: E402

# Balance al 30 de junio de 2026 según el documento XBRL del 10-Q, en millones.
DIEZ_Q = {
    "PLD": {"pasivos_totales": 42_892.4, "deuda_total": 36_442.1, "efectivo": 1_765.0},
    "WELL": {"pasivos_totales": 22_211.6, "deuda_total": 17_726.3, "efectivo": 1_965.2},
}

_INSTANCIA = """<?xml version="1.0"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2026">
  <context id="c1">
    <entity><identifier>0001045609</identifier></entity>
    <period><instant>2026-06-30</instant></period>
  </context>
  <us-gaap:Liabilities contextRef="c1" unitRef="usd">42892400000</us-gaap:Liabilities>
  <us-gaap:LongTermDebt contextRef="c1" unitRef="usd">36442100000</us-gaap:LongTermDebt>
</xbrl>
"""


class _ClienteFalso:
    """Cliente mínimo que cuenta cuántas peticiones caras se hacen."""

    def __init__(self, filings, *, xml=_INSTANCIA):
        self.filings = filings
        self.xml = xml
        self.peticiones: list[str] = []

    def listar_filings(self, cik, ticker, *, formularios=(), limite=None):
        return self.filings[: limite or len(self.filings)]

    def obtener(self, url):
        self.peticiones.append(url)
        if url.endswith("index.json"):
            return '{"directory": {"item": [{"name": "x-20260630_htm.xml"}]}}'
        return self.xml


def _filing(fecha: dt.date) -> Filing:
    return Filing(
        cik="0001045609", ticker="PLD", formulario="10-Q", accession="0001-26-0001",
        fecha_presentacion=fecha, fecha_reporte=fecha, documento_principal="x.htm",
    )


def _crudos(publicado: dt.date | None) -> pd.DataFrame:
    if publicado is None:
        return pd.DataFrame(columns=list(COLUMNAS_CRUDOS))
    return pd.DataFrame(
        [{**dict.fromkeys(COLUMNAS_CRUDOS), "tag": "Liabilities",
          "fecha_publicacion": publicado, "valor": 1.0}]
    )


# --------------------------------------------------------------------------------------
# 33.1 · Las etiquetas se arman del catálogo, no a mano
# --------------------------------------------------------------------------------------


def test_las_etiquetas_de_balance_salen_del_catalogo():
    """Listarlas a mano las habría desincronizado en el primer renglón nuevo."""
    tags = etiquetas_de_balance("PLD")
    assert {"Assets", "Liabilities", "CashAndCashEquivalentsAtCarryingValue"} <= tags
    # Y NO trae renglones de resultados ni de flujo: el rezago que se rellena es
    # el del balance, y bajar el resto multiplicaría el costo sin motivo.
    assert "NetIncomeLoss" not in tags
    assert "NetCashProvidedByUsedInOperatingActivities" not in tags


def test_las_etiquetas_de_la_ficha_entran_con_las_compartidas():
    """Lo que la emisora declara para sí misma cuenta como renglón de balance.

    Si no entrara, la revolvente de Realty Income —que solo existe en su ficha—
    quedaría fuera justo del camino que se inventó para ir por ella.
    """
    assert "RevolvingCreditFacilityAndCommercialPaper" in etiquetas_de_balance("O")
    assert "RevolvingCreditFacilityAndCommercialPaper" not in etiquetas_de_balance("PLD")
    assert "LinesOfCreditCurrent" in etiquetas_de_balance("NNN")


# --------------------------------------------------------------------------------------
# 33.2 · El camino caro solo se paga donde hace falta
# --------------------------------------------------------------------------------------


def test_no_baja_nada_cuando_la_api_ya_esta_al_dia():
    """La guarda que hace sostenible esto en las diez emisoras.

    El documento XBRL pesa de uno a cinco megabytes. Bajarlo siempre habría
    multiplicado por diez el costo de exportar para arreglar a dos. La decisión se
    toma con el índice de filings, que es barato: si el crudo ya tiene la fecha de
    publicación del reporte más reciente, no hay nada que traer.
    """
    cli = _ClienteFalso([_filing(dt.date(2026, 7, 29))])
    salida = rellenar_balance_rezagado(
        cli, "PLD", "0001045609", _crudos(dt.date(2026, 7, 29)), {"Liabilities"}
    )
    assert salida.empty
    assert cli.peticiones == [], "bajó el documento XBRL sin necesitarlo"


def test_baja_el_balance_cuando_hay_un_filing_que_la_api_no_tiene():
    cli = _ClienteFalso([_filing(dt.date(2026, 7, 29))])
    salida = rellenar_balance_rezagado(
        cli, "PLD", "0001045609", _crudos(dt.date(2026, 4, 30)),
        {"Liabilities", "LongTermDebt"},
    )
    assert len(salida) == 2
    assert set(salida["tag"]) == {"Liabilities", "LongTermDebt"}
    assert set(salida["fecha_dato"]) == {dt.date(2026, 6, 30)}
    # La fecha de publicación es la del FILING, no la de hoy: sin eso el hecho
    # entraría al futuro y rompería el corte point-in-time de P1.
    assert set(salida["fecha_publicacion"]) == {dt.date(2026, 7, 29)}
    assert cli.peticiones, "no bajó nada teniendo un filing pendiente"


def test_sin_etiquetas_declaradas_no_hace_una_sola_peticion():
    cli = _ClienteFalso([_filing(dt.date(2026, 7, 29))])
    assert rellenar_balance_rezagado(
        cli, "PLD", "0001045609", _crudos(dt.date(2026, 4, 30)), set()
    ).empty
    assert cli.peticiones == []


def test_un_crudo_vacio_no_impide_rellenar():
    """La primera ingesta de una emisora nueva no tiene contra qué comparar."""
    assert _ultima_publicacion(pd.DataFrame(columns=list(COLUMNAS_CRUDOS))) is None
    cli = _ClienteFalso([_filing(dt.date(2026, 7, 29))])
    assert not rellenar_balance_rezagado(
        cli, "PLD", "0001045609", _crudos(None), {"Liabilities"}
    ).empty


def test_un_filing_ilegible_no_tumba_la_exportacion():
    cli = _ClienteFalso([_filing(dt.date(2026, 7, 29))], xml="no es xml")
    assert rellenar_balance_rezagado(
        cli, "PLD", "0001045609", _crudos(dt.date(2026, 4, 30)), {"Liabilities"}
    ).empty


# --------------------------------------------------------------------------------------
# 33.3 · Sobre datos reales: el hueco quedó cerrado
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("ticker", sorted(DIEZ_Q))
def test_el_balance_de_junio_de_pld_y_well_ya_esta_en_la_base(ticker):
    """Y cuadra con su 10-Q renglón por renglón, no solo en el total."""
    repo = Repositorio()
    saldos = _saldos_de_balance(repo, ticker, asof=dt.date.today())
    if not saldos:
        pytest.skip("No hay base cargada.")
    assert _corte_de_balance(repo, ticker, asof=dt.date.today()) >= dt.date(2026, 6, 30)
    for concepto, esperado in DIEZ_Q[ticker].items():
        assert saldos[concepto] / 1e6 == pytest.approx(esperado, rel=0.001), concepto


def test_ninguna_emisora_sigue_con_el_balance_atrasado():
    """El aviso de la prueba 32 ya no tiene a quién señalar.

    Se conserva igual: la API se volverá a atrasar, y el aviso es la red que
    atrapa el caso que este camino no alcance a cubrir.
    """
    repo = Repositorio()
    hoy = dt.date.today()
    con_aviso = []
    for e in UNIVERSO_INICIAL:
        panel = construir_panel(repo, e.ticker, asof=hoy)
        if panel.trimestral.empty:
            pytest.skip("No hay base cargada.")
        if any("un trimestre de diferencia" in a for a in panel.avisos):
            con_aviso.append(e.ticker)
    assert con_aviso == [], f"siguen con el balance atrasado: {con_aviso}"


def test_el_efectivo_de_welltower_explica_su_apalancamiento():
    """Por qué su apalancamiento SUBIÓ aunque su deuda bajara.

    Es la comprobación de que el número nuevo describe un hecho del emisor y no
    un artefacto del arreglo: la deuda cayó de 17,934 a 17,726 MM, pero el
    efectivo cayó de 4,704 a 1,965, así que la deuda NETA subió 2,531.
    """
    repo = Repositorio()
    saldos = _saldos_de_balance(repo, "WELL", asof=dt.date.today())
    if not saldos:
        pytest.skip("No hay base cargada.")
    neta = (saldos["deuda_total"] - saldos["efectivo"]) / 1e6
    assert neta == pytest.approx(17_726.3 - 1_965.2, rel=0.001)
    assert neta > 15_000, "la deuda neta de junio no puede ser la de marzo"
