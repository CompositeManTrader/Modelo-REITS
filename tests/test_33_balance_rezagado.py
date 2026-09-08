"""Prueba 33 — El filing que `companyfacts` todavía no publica.

La prueba 32 dejó a Prologis y Welltower con un aviso: su balance era de marzo y
sus resultados de junio, porque `companyfacts` se atrasa POR EMISOR y sin avisar.
Al 8 de septiembre de 2026 seguía dando marzo como su último corte, más de un mes
después de que las dos presentaran su 10-Q de junio.

Avisar del hueco era mejor que taparlo en silencio, pero no era cerrarlo. Esto lo
cierra yendo al documento XBRL del propio filing —el mismo camino que ya se usaba
para las etiquetas de extensión de Extra Space y Realty Income—.

Lo que vuelve peligroso ese atraso es que es PARCIAL ENTRE FUENTES: el AFFO y la
utilidad del trimestre entran igual porque vienen del 8-K. Así que el
apalancamiento combinaba una deuda de marzo con un flujo de junio, y el ratio
salía perfectamente plausible. Con el balance completo, Welltower pasa de 2.97x a
3.53x — no porque subiera su deuda, que bajó, sino porque su efectivo cayó de
4,704 MM a 1,965.

Lo que NO es parcial es el filing dentro de la API. La primera versión de esto
pedía solo las etiquetas de balance, porque el balance fue donde se vio el
problema, y con eso cerró un tercio del hueco creyendo que lo cerraba entero: a
Prologis y a Welltower les faltaba de su 10-Q de junio el estado de resultados y
el de flujo completos. Entre lo que faltaba estaban las acciones diluidas, que
son el denominador de todo lo que se mide por acción, y por eso Prologis se
quedaba sin veredicto de la Puerta 2 (33.4).

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
from src.ingesta.estados import COLUMNAS_CRUDOS, etiquetas_del_catalogo  # noqa: E402
from src.ingesta.instancia import (  # noqa: E402
    _accesiones,
    rellenar_filing_rezagado,
)
from src.servicio import _corte_de_balance, _saldos_de_balance, construir_panel  # noqa: E402

# Balance al 30 de junio de 2026 según el documento XBRL del 10-Q, en millones.
DIEZ_Q = {
    "PLD": {"pasivos_totales": 42_892.4, "deuda_total": 36_442.1, "efectivo": 1_765.0},
    "WELL": {"pasivos_totales": 22_211.6, "deuda_total": 17_726.3, "efectivo": 1_965.2},
}

ACCESSION = "0001193125-26-323746"

_INSTANCIA = """<?xml version="1.0"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2026">
  <context id="c1">
    <entity><identifier>0001045609</identifier></entity>
    <period><instant>2026-06-30</instant></period>
  </context>
  <context id="c2">
    <entity><identifier>0001045609</identifier></entity>
    <period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period>
  </context>
  <us-gaap:Liabilities contextRef="c1" unitRef="usd">42892400000</us-gaap:Liabilities>
  <us-gaap:LongTermDebt contextRef="c1" unitRef="usd">36442100000</us-gaap:LongTermDebt>
  <us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding contextRef="c2" unitRef="shares"
    >930500000</us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding>
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


def _filing(fecha: dt.date, accession: str = ACCESSION) -> Filing:
    return Filing(
        cik="0001045609", ticker="PLD", formulario="10-Q", accession=accession,
        fecha_presentacion=fecha, fecha_reporte=fecha, documento_principal="x.htm",
    )


def _crudos(accession: str | None, publicado: dt.date | None = None) -> pd.DataFrame:
    """Lo que devolvió `companyfacts`, con o sin el filing que se está probando."""
    if accession is None:
        return pd.DataFrame(columns=list(COLUMNAS_CRUDOS))
    return pd.DataFrame(
        [{**dict.fromkeys(COLUMNAS_CRUDOS), "tag": "Liabilities",
          "accession": accession, "valor": 1.0,
          "fecha_publicacion": publicado or dt.date(2026, 4, 30)}]
    )


# --------------------------------------------------------------------------------------
# 33.1 · Las etiquetas se arman del catálogo, no a mano
# --------------------------------------------------------------------------------------


def test_las_etiquetas_salen_del_catalogo_y_cubren_los_tres_estados():
    """Listarlas a mano las habría desincronizado en el primer renglón nuevo.

    Y tienen que ser los TRES estados. Pedir solo el balance fue el error de la
    primera versión: el rezago de `companyfacts` no es de un estado, es del
    filing entero, así que cerraba un tercio del hueco pareciendo cerrarlo todo.
    """
    tags = etiquetas_del_catalogo("PLD")
    assert {"Assets", "Liabilities", "CashAndCashEquivalentsAtCarryingValue"} <= tags
    assert "NetIncomeLoss" in tags
    assert "NetCashProvidedByUsedInOperatingActivities" in tags
    # El denominador de todo lo que se mide por acción, que es lo que dejaba a
    # Prologis sin veredicto.
    assert "WeightedAverageNumberOfDilutedSharesOutstanding" in tags


def test_las_etiquetas_de_la_ficha_entran_con_las_compartidas():
    """Lo que la emisora declara para sí misma cuenta igual que un renglón común.

    Si no entrara, la revolvente de Realty Income —que solo existe en su ficha—
    quedaría fuera justo del camino que se inventó para ir por ella.
    """
    assert "RevolvingCreditFacilityAndCommercialPaper" in etiquetas_del_catalogo("O")
    assert "RevolvingCreditFacilityAndCommercialPaper" not in etiquetas_del_catalogo("PLD")
    assert "LinesOfCreditCurrent" in etiquetas_del_catalogo("NNN")


# --------------------------------------------------------------------------------------
# 33.2 · El camino caro solo se paga donde hace falta
# --------------------------------------------------------------------------------------


def test_no_baja_nada_cuando_la_api_ya_esta_al_dia():
    """La guarda que hace sostenible esto en las diez emisoras.

    El documento XBRL pesa de uno a cinco megabytes. Bajarlo siempre habría
    multiplicado por diez el costo de exportar para arreglar a dos. La decisión se
    toma con el índice de filings, que es barato: si la API ya ingirió ESE filing,
    no hay nada que traer.
    """
    cli = _ClienteFalso([_filing(dt.date(2026, 7, 29))])
    salida = rellenar_filing_rezagado(
        cli, "PLD", "0001045609", _crudos(ACCESSION), {"Liabilities"}
    )
    assert salida.empty
    assert cli.peticiones == [], "bajó el documento XBRL sin necesitarlo"


@pytest.mark.parametrize("guiones_en_el_indice", [True, False])
def test_el_guion_del_accession_no_decide_si_se_baja_un_documento(guiones_en_el_indice):
    """La API los da con guiones y el índice de filings también, pero no se
    depende de eso: el formato no es parte de la identidad del filing.

    Se prueban los DOS lados. Normalizar uno solo deja el mismo agujero de
    siempre —un documento de cinco megabytes bajándose otra vez por una
    diferencia de puntuación— y ninguna prueba que compare un solo sentido lo
    ve.
    """
    del_indice = ACCESSION if guiones_en_el_indice else ACCESSION.replace("-", "")
    del_api = ACCESSION.replace("-", "") if guiones_en_el_indice else ACCESSION
    cli = _ClienteFalso([_filing(dt.date(2026, 7, 29), accession=del_indice)])
    assert rellenar_filing_rezagado(
        cli, "PLD", "0001045609", _crudos(del_api), {"Liabilities"}
    ).empty
    assert cli.peticiones == []


def test_baja_el_filing_cuando_la_api_no_lo_tiene():
    cli = _ClienteFalso([_filing(dt.date(2026, 7, 29))])
    salida = rellenar_filing_rezagado(
        cli, "PLD", "0001045609", _crudos("0001193125-26-197850"),
        {"Liabilities", "LongTermDebt"},
    )
    assert len(salida) == 2
    assert set(salida["tag"]) == {"Liabilities", "LongTermDebt"}
    assert set(salida["fecha_dato"]) == {dt.date(2026, 6, 30)}
    # La fecha de publicación es la del FILING, no la de hoy: sin eso el hecho
    # entraría al futuro y rompería el corte point-in-time de P1.
    assert set(salida["fecha_publicacion"]) == {dt.date(2026, 7, 29)}
    assert cli.peticiones, "no bajó nada teniendo un filing pendiente"


def test_trae_tambien_los_renglones_de_duracion():
    """La razón de existir de este cambio.

    Un hecho de balance es PUNTUAL y uno de resultados dura un trimestre. Si el
    camino solo supiera leer los primeros, las acciones diluidas de junio —que es
    lo que le faltaba a Prologis— seguirían sin llegar.
    """
    cli = _ClienteFalso([_filing(dt.date(2026, 7, 29))])
    salida = rellenar_filing_rezagado(
        cli, "PLD", "0001045609", _crudos("0001193125-26-197850"),
        {"Liabilities", "WeightedAverageNumberOfDilutedSharesOutstanding"},
    )
    acciones = salida[salida["tag"] == "WeightedAverageNumberOfDilutedSharesOutstanding"]
    assert len(acciones) == 1
    assert acciones.iloc[0]["periodo_tipo"] == "Q"
    assert acciones.iloc[0]["fecha_inicio"] == dt.date(2026, 4, 1)
    assert acciones.iloc[0]["valor"] == 930_500_000


def test_sin_etiquetas_declaradas_no_hace_una_sola_peticion():
    cli = _ClienteFalso([_filing(dt.date(2026, 7, 29))])
    assert rellenar_filing_rezagado(
        cli, "PLD", "0001045609", _crudos("0001193125-26-197850"), set()
    ).empty
    assert cli.peticiones == []


def test_un_crudo_vacio_no_impide_rellenar():
    """La primera ingesta de una emisora nueva no tiene contra qué comparar."""
    assert _accesiones(pd.DataFrame(columns=list(COLUMNAS_CRUDOS))) == set()
    cli = _ClienteFalso([_filing(dt.date(2026, 7, 29))])
    assert not rellenar_filing_rezagado(
        cli, "PLD", "0001045609", _crudos(None), {"Liabilities"}
    ).empty


def test_un_filing_ilegible_no_tumba_la_exportacion():
    cli = _ClienteFalso([_filing(dt.date(2026, 7, 29))], xml="no es xml")
    assert rellenar_filing_rezagado(
        cli, "PLD", "0001045609", _crudos("0001193125-26-197850"), {"Liabilities"}
    ).empty


# --------------------------------------------------------------------------------------
# 33.3 · El camino de las extensiones no puede contestar la guarda del rezago
# --------------------------------------------------------------------------------------

_INSTANCIA_O = """<?xml version="1.0"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance"
      xmlns:us-gaap="http://fasb.org/us-gaap/2026"
      xmlns:o="http://www.realtyincome.com/20260630">
  <context id="c1">
    <entity><identifier>0000726728</identifier></entity>
    <period><instant>2026-06-30</instant></period>
  </context>
  <o:RevolvingCreditFacilityAndCommercialPaper contextRef="c1" unitRef="usd"
    >1234000000</o:RevolvingCreditFacilityAndCommercialPaper>
  <us-gaap:Liabilities contextRef="c1" unitRef="usd">30000000000</us-gaap:Liabilities>
</xbrl>
"""


class _ClienteDeExportacion(_ClienteFalso):
    """Como el anterior, más el `companyfacts` que `armar_crudos` necesita."""

    def __init__(self, filings, hechos_api, *, xml):
        super().__init__(filings, xml=xml)
        self.hechos_api = hechos_api

    def companyfacts(self, cik):
        return self.hechos_api


def _companyfacts(accession: str, publicado: str) -> dict:
    """Un `companyfacts` mínimo con un solo hecho, del filing que se le diga."""
    return {"facts": {"us-gaap": {"Assets": {"units": {"USD": [{
        "end": "2026-03-31", "val": 1.0, "accn": accession, "filed": publicado,
        "form": "10-Q", "fy": 2026, "fp": "Q1",
    }]}}}}}


def test_las_extensiones_no_tapan_el_rezago_de_la_api():
    """El agujero que tenía la guarda anterior, y que la nueva cierra.

    `descargar_instancias` lee el documento XBRL del filing más reciente para
    traer las etiquetas propias de O y de EXR. Si la guarda del rezago se
    contestara con el crudo ya concatenado —o con su última fecha de
    publicación—, esas mismas filas marcarían el filing como presente y el resto
    del reporte no se bajaría nunca. En silencio, y solo en las dos emisoras que
    más caminos usan.
    """
    from scripts.instantanea import armar_crudos

    pendiente = "0000726728-26-000048"
    cli = _ClienteDeExportacion(
        [_filing(dt.date(2026, 8, 6), accession=pendiente)],
        _companyfacts("0000726728-26-000030", "2026-05-05"),
        xml=_INSTANCIA_O,
    )
    crudos = armar_crudos(cli, "O", "0000726728")

    # La etiqueta de extensión llega una sola vez aunque los dos caminos la lean.
    revolvente = crudos[crudos["tag"] == "RevolvingCreditFacilityAndCommercialPaper"]
    assert len(revolvente) == 1

    # Y lo que prueba el punto: el renglón que SOLO puede venir del relleno.
    assert "Liabilities" in set(crudos["tag"]), "el rezago quedó tapado por las extensiones"


# --------------------------------------------------------------------------------------
# 33.4 · Sobre datos reales: el hueco quedó cerrado
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
