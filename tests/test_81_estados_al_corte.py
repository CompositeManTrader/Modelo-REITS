"""Prueba 81 — Los estados al corte solo saben lo que se había publicado (P1).

Filtrar los hechos por ``fecha_publicacion`` no basta. Dos decisiones del armado se
tomaban con TODA la historia a la vista, y con ellas el balance de 2012 dependía de
lo que la emisora publicó diez años después:

* **La etiqueta de cada renglón.** ``elegir_cadenas`` decide por vigencia,
  cobertura y empalme, y los tres cambian con cada filing. Con los datos de hoy la
  línea de crédito de NNN sale de ``LinesOfCreditCurrent``, que no existía antes de
  2022, y su balance de 2012 se quedaba sin la revolvente que entonces reportaba
  como ``LineOfCredit`` (81.1).

* **El trimestre derivado.** Se elegía una sola pareja de componentes entre todas
  sus versiones y se fechaba en la más tardía. Si el emisor reexpresaba los dos un
  año después, el trimestre aparecía hasta la reexpresión: desconocido durante el
  año en que ya se podía calcular (81.2).

La tabla persistida tenía la misma falla en pequeño: de cada periodo conservaba
solo la etiqueta que ganaba en toda la historia (81.3).

La prueba de cierre es la misma que la del NAV: armar los estados al corte con todo
el crudo y con lo publicado hasta el corte, y exigir que sean idénticos (81.4).
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

from src.datos import almacen  # noqa: E402
from src.ingesta.estados import (  # noqa: E402
    BALANCE,
    ESTADO_RESULTADOS,
    armar_estado,
    balance_por_reporte,
    derivar_trimestres_faltantes,
    elegir_cadenas,
    elegir_tags,
    hechos_de_crudos,
)

D = dt.date


def _crudos(filas: list[dict]) -> pd.DataFrame:
    base = {
        "ticker": "X", "taxonomia": "us-gaap", "unidad": "USD",
        "periodo_tipo": "PUNTUAL", "fecha_inicio": None,
        "formulario": "10-Q", "accession": "a-1", "marco": "",
    }
    df = pd.DataFrame([{**base, **f} for f in filas])
    for columna in ("fecha_inicio", "fecha_dato", "fecha_publicacion"):
        fechas = pd.to_datetime(df[columna]).dt.date
        df[columna] = fechas.astype(object).where(fechas.notna(), None)
    return df


def _publicado_hasta(crudos: pd.DataFrame, asof: dt.date) -> pd.DataFrame:
    return crudos[pd.to_datetime(crudos["fecha_publicacion"]).dt.date <= asof]


# --------------------------------------------------------------------------------------
# 81.1 · La etiqueta se elige con lo publicado al corte
# --------------------------------------------------------------------------------------


def _linea_de_credito_de_nnn() -> pd.DataFrame:
    """La revolvente de NNN, reducida: una etiqueta hasta 2020 y otra desde 2021.

    No se traslapan, así que el empalme no puede verificarse y la vieja no entra
    detrás de la nueva. Ese rechazo es correcto; lo que no era correcto es que
    alcanzara a los cortes en que la nueva todavía no existía.
    """
    filas = []
    for fin in pd.date_range("2010-03-31", "2020-12-31", freq="QE"):
        valor = 142_600_000.0 if fin == pd.Timestamp("2012-06-30") else 50_000_000.0
        filas.append({"tag": "LineOfCredit", "fecha_dato": fin,
                      "fecha_publicacion": fin + pd.Timedelta(days=40), "valor": valor})
    for fin in pd.date_range("2021-03-31", "2026-06-30", freq="QE"):
        filas.append({"tag": "LinesOfCreditCurrent", "fecha_dato": fin,
                      "fecha_publicacion": fin + pd.Timedelta(days=40), "valor": 30_000_000.0})
    return _crudos(filas)


def test_con_todo_el_crudo_la_linea_de_credito_de_nnn_es_la_etiqueta_nueva():
    """El punto de partida: la vista de HOY elige la etiqueta vigente, y está bien."""
    assert elegir_cadenas(_linea_de_credito_de_nnn(), "NNN")["linea_de_credito"] == (
        "LinesOfCreditCurrent",
    )


def test_al_corte_la_etiqueta_es_la_que_se_usaba_entonces():
    crudos = _linea_de_credito_de_nnn()
    asof = D(2019, 12, 31)
    assert elegir_cadenas(crudos, "NNN", asof=asof)["linea_de_credito"] == ("LineOfCredit",)
    assert elegir_tags(crudos, "NNN", asof=asof)["linea_de_credito"] == "LineOfCredit"
    assert elegir_cadenas(crudos, "NNN", asof=asof) == elegir_cadenas(
        _publicado_hasta(crudos, asof), "NNN"
    ), "al corte, el crudo posterior no puede pesar en la decisión"


def test_el_balance_de_2012_trae_la_revolvente_que_se_conocia_en_2019():
    crudos = _linea_de_credito_de_nnn()
    asof = D(2019, 12, 31)
    balance = armar_estado(crudos, "NNN", BALANCE, asof=asof)
    assert balance.loc["linea_de_credito", D(2012, 6, 30)] == pytest.approx(142_600_000.0)
    assert balance.loc["linea_de_credito", "tag_gaap"] == "LineOfCredit"
    pd.testing.assert_frame_equal(
        balance, armar_estado(_publicado_hasta(crudos, asof), "NNN", BALANCE, asof=asof)
    )


def test_el_balance_por_reporte_tambien_elige_al_corte():
    crudos = _linea_de_credito_de_nnn()
    asof = D(2019, 12, 31)
    por_reporte = balance_por_reporte(crudos, "NNN", asof=asof)
    revolvente = por_reporte[por_reporte["linea"] == "linea_de_credito"]
    # Del 1T-2010 al 3T-2019: el cierre de 2019 se publica en 2020.
    assert len(revolvente) == 39
    pd.testing.assert_frame_equal(
        por_reporte, balance_por_reporte(_publicado_hasta(crudos, asof), "NNN", asof=asof)
    )


def test_quien_pasa_la_cadena_decide_con_que_datos_se_eligio():
    """Con ``tags`` explícitos no se vuelve a elegir: es el contrato de siempre."""
    crudos = _linea_de_credito_de_nnn()
    hoy = elegir_cadenas(crudos, "NNN")
    balance = armar_estado(crudos, "NNN", BALANCE, asof=D(2019, 12, 31), tags=hoy)
    assert "linea_de_credito" not in balance.index


# --------------------------------------------------------------------------------------
# 81.2 · El trimestre derivado, versión por versión
# --------------------------------------------------------------------------------------


def _hecho_de_flujo(tipo, inicio, fin, pub, valor, tag="Revenues", formulario="10-Q"):
    return {"tag": tag, "periodo_tipo": tipo, "fecha_inicio": inicio, "fecha_dato": fin,
            "fecha_publicacion": pub, "valor": valor, "formulario": formulario}


def _segundo_trimestre_reexpresado() -> pd.DataFrame:
    """El Q2-2012 de NNN, reducido: se despeja del semestre menos el Q1, y los dos
    componentes se reexpresan un año después, en los comparativos de 2013."""
    return _crudos([
        _hecho_de_flujo("Q", "2012-01-01", "2012-03-31", "2012-05-08", 50.0),
        _hecho_de_flujo("H1", "2012-01-01", "2012-06-30", "2012-08-08", 110.0),
        _hecho_de_flujo("Q", "2012-01-01", "2012-03-31", "2013-05-07", 52.0),
        _hecho_de_flujo("H1", "2012-01-01", "2012-06-30", "2013-08-07", 115.0),
    ])


def test_el_trimestre_derivado_existe_desde_que_fue_deducible():
    """Antes salía UNA versión, la de 2013, y el Q2-2012 no existía durante 2012."""
    salida = derivar_trimestres_faltantes(_segundo_trimestre_reexpresado(),
                                          {"ingresos_totales": "Revenues"})
    derivados = salida[salida["formulario"] == "DERIVADO"].sort_values("fecha_publicacion")
    assert list(derivados["fecha_dato"]) == [D(2012, 6, 30)] * 2
    assert list(derivados["fecha_publicacion"]) == [D(2012, 8, 8), D(2013, 8, 7)]
    assert list(derivados["valor"]) == pytest.approx([60.0, 63.0])


def test_una_version_intermedia_sin_pareja_no_produce_un_trimestre():
    """El 7 de mayo de 2013 se conoce el Q1 reexpresado pero no el semestre: restarlo
    del semestre viejo mezclaría dos bases (el caso de Agree Realty). No hay versión."""
    salida = derivar_trimestres_faltantes(_segundo_trimestre_reexpresado(),
                                          {"ingresos_totales": "Revenues"})
    derivados = salida[salida["formulario"] == "DERIVADO"]
    assert D(2013, 5, 7) not in set(derivados["fecha_publicacion"])


def test_el_trimestre_derivado_al_corte_es_el_que_se_podia_calcular_entonces():
    crudos = _segundo_trimestre_reexpresado()
    tags = {"ingresos_totales": "Revenues"}
    completos = derivar_trimestres_faltantes(crudos, tags)
    for asof, esperado in ((D(2012, 12, 31), 60.0), (D(2013, 12, 31), 63.0)):
        estado = armar_estado(completos, "X", ESTADO_RESULTADOS, asof=asof, tags=tags)
        assert estado.loc["ingresos_totales", D(2012, 6, 30)] == pytest.approx(esperado)
        cortado = derivar_trimestres_faltantes(_publicado_hasta(crudos, asof), tags)
        pd.testing.assert_frame_equal(
            estado, armar_estado(cortado, "X", ESTADO_RESULTADOS, asof=asof, tags=tags)
        )


def test_el_trimestre_que_la_emisora_publica_despues_no_borra_el_derivado_de_antes():
    """El Q4 se despeja con el 10-K; un año después la emisora lo publica directo,
    de comparativo. Antes eso bastaba para no derivarlo nunca, y el Q4 desaparecía
    también en el año en que solo se podía conocer restando. Ahora el publicado
    manda desde que se publica, y después ya no se deriva nada."""
    crudos = _crudos([
        _hecho_de_flujo("9M", "2018-01-01", "2018-09-30", "2018-11-05", 300.0),
        _hecho_de_flujo("FY", "2018-01-01", "2018-12-31", "2019-02-12", 410.0, formulario="10-K"),
        _hecho_de_flujo("Q", "2018-10-01", "2018-12-31", "2020-02-11", 111.0, formulario="10-K"),
        _hecho_de_flujo("FY", "2018-01-01", "2018-12-31", "2021-02-11", 420.0, formulario="10-K"),
    ])
    tags = {"ingresos_totales": "Revenues"}
    completos = derivar_trimestres_faltantes(crudos, tags)
    derivados = completos[completos["formulario"] == "DERIVADO"]
    assert list(derivados["fecha_publicacion"]) == [D(2019, 2, 12)]
    assert float(derivados["valor"].iloc[0]) == pytest.approx(110.0)

    def q4(asof):
        estado = armar_estado(completos, "X", ESTADO_RESULTADOS, asof=asof, tags=tags)
        return estado.loc["ingresos_totales", D(2018, 12, 31)]

    assert q4(D(2019, 6, 30)) == pytest.approx(110.0)
    assert q4(D(2026, 6, 30)) == pytest.approx(111.0), "una versión derivada posterior le ganó"


# --------------------------------------------------------------------------------------
# 81.3 · La tabla persistida conserva la versión que ganaba en su fecha
# --------------------------------------------------------------------------------------


def _intereses_con_comparativo_tardio() -> pd.DataFrame:
    """Dos nombres del mismo gasto que coinciden donde se traslapan.

    La principal, ``InterestExpenseDebt``, cubre el 3T-2016 solo porque el 10-Q de
    un año después lo trae de comparativo. Hasta entonces ese trimestre se conocía
    por la empalmada.
    """
    filas = []
    for fin in pd.date_range("2015-03-31", "2018-12-31", freq="QE"):
        filas.append(_hecho_de_flujo("Q", fin - pd.offsets.QuarterBegin(startingMonth=1), fin,
                                     fin + pd.Timedelta(days=35), 10.0, tag="InterestExpense"))
    for fin in [pd.Timestamp("2016-09-30"), *pd.date_range("2017-03-31", "2020-12-31", freq="QE")]:
        tardio = fin.year == 2016
        # El comparativo difiere medio punto: dentro de la tolerancia del empalme, y
        # suficiente para saber cuál de las dos versiones se leyó.
        filas.append(_hecho_de_flujo(
            "Q", fin - pd.offsets.QuarterBegin(startingMonth=1), fin,
            pd.Timestamp("2017-11-01") if tardio else fin + pd.Timedelta(days=35),
            10.05 if tardio else 10.0, tag="InterestExpenseDebt",
        ))
    return _crudos(filas)


def test_la_tabla_persistida_leida_al_corte_dice_lo_mismo_que_el_estado():
    crudos = _intereses_con_comparativo_tardio()
    cadena = elegir_cadenas(crudos, "X")
    assert cadena["gasto_intereses"] == ("InterestExpenseDebt", "InterestExpense")

    hechos = hechos_de_crudos(crudos, "X")
    hechos = hechos[(hechos["concepto"] == "gasto_intereses")
                    & (hechos["fecha_dato"] == D(2016, 9, 30))].sort_values("fecha_publicacion")

    for asof, esperado in ((D(2017, 6, 30), 10.0), (D(2018, 6, 30), 10.05)):
        conocido = hechos[pd.to_datetime(hechos["fecha_publicacion"]).dt.date <= asof]
        assert not conocido.empty, f"al {asof} el 3T-2016 ya se conocía y la tabla lo perdió"
        estado = armar_estado(crudos, "X", ESTADO_RESULTADOS, asof=asof, tags=cadena)
        assert float(conocido["valor"].iloc[-1]) == pytest.approx(esperado)
        assert estado.loc["gasto_intereses", D(2016, 9, 30)] == pytest.approx(esperado)


# --------------------------------------------------------------------------------------
# 81.4 · La prueba de cierre: NNN y Realty Income con lo publicado al 2019-12-31
# --------------------------------------------------------------------------------------

CORTE = D(2019, 12, 31)


def _estados_al_corte(crudos: pd.DataFrame, ticker: str, asof: dt.date) -> dict:
    """La ruta completa al corte: etiquetas, trimestres derivados y estados."""
    cadenas = elegir_cadenas(crudos, ticker, asof=asof)
    completos = derivar_trimestres_faltantes(crudos, cadenas)
    salida = {
        (estado, tipo): armar_estado(completos, ticker, estado, asof=asof, periodo_tipo=tipo)
        for estado, tipo in ((ESTADO_RESULTADOS, "Q"), (ESTADO_RESULTADOS, "FY"), (BALANCE, "Q"))
    }
    salida["balance_por_reporte"] = (
        balance_por_reporte(completos, ticker, asof=asof)
        .sort_values(["linea", "fecha_dato", "fecha_publicacion", "valor"])
        .reset_index(drop=True)
    )
    return salida


@pytest.mark.parametrize("ticker", ["NNN", "O"])
def test_los_estados_al_corte_no_miran_al_futuro(ticker):
    """Con los hechos publicados hasta 2019, los estados de 2019 hacia atrás son los
    mismos que con todo el crudo, renglón por renglón y etiqueta por etiqueta."""
    crudos = almacen.leer_crudos(ticker)
    if crudos.empty:
        pytest.skip(f"No están versionados los hechos XBRL de {ticker}.")
    cortado = _publicado_hasta(crudos, CORTE)
    if cortado.empty:
        pytest.skip(f"El crudo versionado de {ticker} no trae nada publicado al corte.")

    completo, al_corte = _estados_al_corte(crudos, ticker, CORTE), _estados_al_corte(
        cortado, ticker, CORTE)
    assert not completo[(BALANCE, "Q")].empty and not completo[(ESTADO_RESULTADOS, "Q")].empty
    for clave in completo:
        pd.testing.assert_frame_equal(completo[clave], al_corte[clave], obj=str(clave))
