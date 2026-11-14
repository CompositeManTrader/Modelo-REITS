"""Prueba 56 — Los estados financieros a una fecha no miran al futuro (P1).

`src/ingesta/estados.py` arma estados «al corte» y prometía ser point-in-time, pero
dos piezas decidían con TODA la historia a la vista. Se vieron al construir el NAV
de `src/estudio/intrinsecos.py`, que las esquivaba con código propio:

* **La cadena de etiquetas de cada renglón** se elegía con todos los hechos,
  incluidos los posteriores al corte. Con los datos de hoy la línea de crédito de
  NNN se lee de `LinesOfCreditCurrent`, que la emisora usa desde 2022; en 2012 la
  reportaba como `LineOfCredit` —142.6 millones al 30 de junio— y ese balance,
  armado con todo, salía sin ella. Armado con lo publicado hasta 2019, sí la tenía.

* **El trimestre derivado** (Q4 = año − 9M, Q2 = semestre − Q1) se calculaba con la
  mejor pareja de versiones de toda la historia y se fechaba con la más tardía de
  sus dos componentes. Si un componente se reexpresaba un año después, el
  trimestre quedaba fechado en la reexpresión: el flujo de operación del Q2-2012 de
  NNN, deducible desde el 3 de agosto de 2012, aparecía hasta el 1 de agosto de
  2013.

La prueba de que quedó resuelto es la del NAV (prueba 54,
``test_el_nav_no_mira_al_futuro``) aplicada a los estados: armar el mismo corte con
toda la historia y solo con lo publicado hasta el corte da exactamente lo mismo.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.datos import almacen
from src.ingesta import estados as es

CORTES = (dt.date(2019, 12, 31), dt.date(2022, 12, 31))
ESTADOS_A_PROBAR = (
    (es.ESTADO_RESULTADOS, "Q"),
    (es.ESTADO_RESULTADOS, "FY"),
    (es.BALANCE, "Q"),
    (es.FLUJO_EFECTIVO, "Q"),
)


def _crudos(ticker: str) -> pd.DataFrame:
    try:
        c = almacen.leer_crudos(ticker)
    except (FileNotFoundError, OSError):
        pytest.skip(f"No están versionados los hechos XBRL de {ticker}.")
    if c.empty:
        pytest.skip(f"No están versionados los hechos XBRL de {ticker}.")
    return c


def _hasta(crudos: pd.DataFrame, corte: dt.date) -> pd.DataFrame:
    return crudos[pd.to_datetime(crudos["fecha_publicacion"]).dt.date <= corte]


def _candidatas(ticker: str) -> dict[str, tuple[str, ...]]:
    """Las etiquetas del catálogo: no dependen de ningún dato, así que tampoco del corte."""
    return {ln.clave: es.tags_de(ticker, ln.clave) for ln in es.LINEAS}


def _estados(crudos: pd.DataFrame, ticker: str, corte: dt.date) -> dict:
    completos = es.derivar_trimestres_faltantes(crudos, _candidatas(ticker))
    return {
        (estado, tipo): es.armar_estado(completos, ticker, estado, asof=corte, periodo_tipo=tipo)
        for estado, tipo in ESTADOS_A_PROBAR
    }


def _base_al(hechos: pd.DataFrame, corte: dt.date) -> pd.Series:
    """Lo que la base contesta al corte: la última versión de cada celda."""
    h = hechos[pd.to_datetime(hechos["fecha_publicacion"]).dt.date <= corte]
    h = h.sort_values("fecha_publicacion", kind="stable").drop_duplicates(
        ["concepto", "periodo_tipo", "fecha_dato"], keep="last"
    )
    return h.set_index(["concepto", "periodo_tipo", "fecha_dato"])["valor"].sort_index()


# --------------------------------------------------------------------------------------
# 56.1 · La prueba de terminado, sobre el almacén versionado
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("corte", CORTES, ids=str)
@pytest.mark.parametrize("ticker", ["NNN", "O"])
def test_los_estados_no_miran_al_futuro(ticker, corte):
    """Con todos los hechos o solo con los publicados hasta el corte: el mismo estado.

    El estado de resultados (trimestral y anual), el balance y el flujo, con los
    trimestres derivados incluidos. Es ``test_el_nav_no_mira_al_futuro`` aplicado a
    los estados que alimentan la pantalla.
    """
    c = _crudos(ticker)
    hasta = _hasta(c, corte)
    if hasta.empty:
        pytest.skip(f"El almacén de {ticker} no tiene nada publicado hasta {corte}.")
    completo, cortado = _estados(c, ticker, corte), _estados(hasta, ticker, corte)
    assert any(not t.empty for t in completo.values()), "el corte no armó ningún estado"
    for llave in completo:
        pd.testing.assert_frame_equal(completo[llave], cortado[llave], obj=str(llave))


@pytest.mark.parametrize("corte", CORTES, ids=str)
@pytest.mark.parametrize("ticker", ["NNN", "O"])
def test_con_la_cadena_fija_la_base_no_mira_al_futuro(ticker, corte):
    """El camino de la pantalla: los hechos que ``hechos_de_crudos`` guarda en la base.

    La base elige la cadena con todo lo que recibe —es lo único suyo que todavía no
    es point-in-time; ver el comentario en ``hechos_de_crudos``—. Con la cadena fija,
    lo demás sí lo es: la derivación y el empalme versión por versión hacen que
    filtrar la base por fecha de publicación dé lo mismo que haberla armado solo
    con lo que existía a esa fecha.
    """
    c = _crudos(ticker)
    hasta = _hasta(c, corte)
    if hasta.empty:
        pytest.skip(f"El almacén de {ticker} no tiene nada publicado hasta {corte}.")
    cadenas = es.elegir_cadenas(c, ticker)
    completo = _base_al(es.hechos_de_crudos(c, ticker, cadenas=cadenas), corte)
    cortado = _base_al(es.hechos_de_crudos(hasta, ticker, cadenas=cadenas), corte)
    assert len(completo) > 100
    pd.testing.assert_series_equal(completo, cortado)


def test_la_eleccion_al_corte_es_la_de_lo_publicado_hasta_el_corte():
    c = _crudos("NNN")
    for corte in CORTES:
        assert es.elegir_cadenas(c, "NNN", asof=corte) == es.elegir_cadenas(_hasta(c, corte), "NNN")


# --------------------------------------------------------------------------------------
# 56.2 · La etiqueta vieja sigue alimentando su corte
# --------------------------------------------------------------------------------------


def _saldo(tag: str, fin: str, pub: str, valor: float) -> dict:
    return {
        "ticker": "NNN", "taxonomia": "us-gaap", "tag": tag, "unidad": "USD",
        "periodo_tipo": "PUNTUAL", "fecha_inicio": None,
        "fecha_dato": dt.date.fromisoformat(fin),
        "fecha_publicacion": dt.date.fromisoformat(pub), "valor": valor,
        "formulario": "10-Q", "accession": f"a-{pub}", "marco": "",
    }


def _linea_de_credito_de_nnn() -> pd.DataFrame:
    """La línea de crédito de NNN, reducida a lo esencial.

    `LineOfCredit` hasta 2021 y `LinesOfCreditCurrent` desde 2022, sin traslape: la
    emisora nunca reportó las dos para el mismo corte. El activo total ancla cada
    corte del balance.
    """
    filas = []
    for anio in range(2012, 2025):
        fin, pub = f"{anio}-06-30", f"{anio}-08-03"
        filas.append(_saldo("Assets", fin, pub, 5_000e6 + anio))
        if anio <= 2021:
            filas.append(_saldo("LineOfCredit", fin, pub, 142.6e6 if anio == 2012 else 100e6))
        else:
            filas.append(_saldo("LinesOfCreditCurrent", fin, pub, 28.5e6))
    return pd.DataFrame(filas)


def test_la_linea_de_credito_de_2012_no_depende_de_lo_que_se_publico_en_2022():
    crudos = _linea_de_credito_de_nnn()
    junio_2012 = dt.date(2012, 6, 30)
    al_2019 = dt.date(2019, 12, 31)

    # Con todo a la vista, la cadena es la etiqueta nueva, que no trae 2012...
    assert es.elegir_cadenas(crudos, "NNN")["linea_de_credito"] == ("LinesOfCreditCurrent",)
    # ...pero al cierre de 2019 la nueva no existía, y la elección al corte no la ve.
    assert es.elegir_cadenas(crudos, "NNN", asof=al_2019)["linea_de_credito"] == (
        "LineOfCredit",
    )

    completo = es.armar_estado(crudos, "NNN", es.BALANCE, asof=al_2019)
    cortado = es.armar_estado(_hasta(crudos, al_2019), "NNN", es.BALANCE, asof=al_2019)
    pd.testing.assert_frame_equal(completo, cortado)
    assert completo.loc["linea_de_credito", junio_2012] == pytest.approx(142.6e6)
    assert completo.loc["linea_de_credito", "tag_gaap"] == "LineOfCredit"

    # El reporte por reporte del mismo corte lee las mismas etiquetas.
    por_reporte = es.balance_por_reporte(crudos, "NNN", asof=al_2019)
    del_2012 = por_reporte[(por_reporte["linea"] == "linea_de_credito")
                           & (por_reporte["fecha_dato"] == junio_2012)]
    assert list(del_2012["valor"]) == [pytest.approx(142.6e6)]


def test_hoy_la_base_y_el_estado_armado_dicen_lo_mismo():
    """Para el corte de hoy, las dos rutas —el estado armado y la base que lee la
    pantalla— eligen la misma cadena y tienen que coincidir celda por celda."""
    crudos = _linea_de_credito_de_nnn()
    hoy = dt.date(2026, 11, 14)
    estado = es.armar_estado(crudos, "NNN", es.BALANCE, asof=hoy)
    base = _base_al(es.hechos_de_crudos(crudos, "NNN"), hoy)
    for fecha in (c for c in estado.columns if isinstance(c, dt.date)):
        valor = estado.loc["linea_de_credito", fecha]
        if pd.isna(valor):
            assert ("linea_de_credito", "PUNTUAL", fecha) not in base.index
        else:
            assert base[("linea_de_credito", "PUNTUAL", fecha)] == valor


def test_al_corte_manda_la_cadena_del_corte():
    """Un cambio de etiqueta sin traslape, visto desde dos cortes.

    La etiqueta nueva no entra a la cadena hasta que la vieja deja de estar vigente
    —dieciocho meses—: antes, la elección prefiere la vieja por cobertura y lo que
    la nueva publicó no se lee. Al salir de la ventana entra, y el mismo trimestre
    ya aparece: el corte se arma con la cadena que se conocía AL CORTE, no con la
    de hoy ni con la del día en que salió cada hecho.
    """
    def trimestre(tag, fin, pub, valor):
        fila = _saldo(tag, fin, pub, valor)
        fin_ = pd.Timestamp(fin)
        fila.update({"periodo_tipo": "Q", "ticker": "X",
                     "fecha_inicio": (fin_ - pd.offsets.QuarterBegin(1, startingMonth=1)).date()})
        return fila

    filas = [trimestre("GainLossOnSaleOfProperties", f"{a}-{m}", f"{a}-{p}", 10.0)
             for a in range(2018, 2024) for m, p in (("03-31", "05-01"), ("06-30", "08-01"),
                                                     ("09-30", "11-01"))]
    filas += [trimestre("GainsLossesOnSalesOfInvestmentRealEstate", "2024-03-31", "2024-05-01", 7.0),
              trimestre("GainsLossesOnSalesOfInvestmentRealEstate", "2025-06-30", "2025-08-01", 9.0)]
    crudos = pd.DataFrame(filas)
    marzo_2024 = dt.date(2024, 3, 31)

    dentro = es.armar_estado(crudos, "X", es.ESTADO_RESULTADOS, asof=dt.date(2024, 6, 30))
    assert dentro.loc["ganancia_venta_inmuebles", "tag_gaap"] == "GainLossOnSaleOfProperties"
    assert marzo_2024 not in dentro.columns
    despues = es.armar_estado(crudos, "X", es.ESTADO_RESULTADOS, asof=dt.date(2025, 8, 1))
    assert despues.loc["ganancia_venta_inmuebles", marzo_2024] == 7.0


def test_el_empalme_no_borra_lo_que_se_sabia_antes_de_la_etiqueta_principal():
    """La empalmada traía el periodo; la principal lo publicó años después.

    Con todas las versiones a la vista, la principal «ganaba» el periodo y las
    versiones de la empalmada se borraban, así que en los cortes de en medio el
    periodo salía vacío aunque se conociera. Ahora la base dice lo que se sabía.
    """
    def saldo(tag, fin, pub, valor):
        fila = _saldo(tag, fin, pub, valor)
        fila["ticker"] = "X"
        return fila

    crudos = pd.DataFrame([
        saldo("Assets", "2020-12-31", "2021-02-20", 900.0),
        saldo("LongTermDebt", "2020-12-31", "2021-02-20", 500.0),
        saldo("Assets", "2022-12-31", "2023-02-20", 1000.0),
        saldo("DebtLongtermAndShorttermCombinedAmount", "2022-12-31", "2023-02-20", 600.0),
        # La principal publica, como comparativo, el corte de 2020.
        saldo("DebtLongtermAndShorttermCombinedAmount", "2020-12-31", "2023-02-20", 505.0),
    ])
    cadenas = {"deuda_total": ("DebtLongtermAndShorttermCombinedAmount", "LongTermDebt")}
    hechos = es.hechos_de_crudos(crudos, "X", cadenas=cadenas)
    dic_2020 = ("deuda_total", "PUNTUAL", dt.date(2020, 12, 31))
    assert _base_al(hechos, dt.date(2022, 6, 30))[dic_2020] == 500.0
    assert _base_al(hechos, dt.date(2026, 11, 14))[dic_2020] == 505.0


# --------------------------------------------------------------------------------------
# 56.3 · El trimestre derivado, versión por versión
# --------------------------------------------------------------------------------------


def _flujo(tipo: str, inicio: str, fin: str, pub: str, valor: float) -> dict:
    return {
        "ticker": "NNN", "taxonomia": "us-gaap",
        "tag": "NetCashProvidedByUsedInOperatingActivities", "unidad": "USD",
        "periodo_tipo": tipo, "fecha_inicio": dt.date.fromisoformat(inicio),
        "fecha_dato": dt.date.fromisoformat(fin),
        "fecha_publicacion": dt.date.fromisoformat(pub), "valor": valor,
        "formulario": "10-Q", "accession": f"a-{pub}", "marco": "",
    }


TAGS_FLUJO = {"flujo_operacion": "NetCashProvidedByUsedInOperatingActivities"}


def test_el_trimestre_derivado_se_sabe_desde_que_era_deducible():
    """El Q2-2012 de NNN: el flujo solo se publica acumulado, así que Q2 = H1 − Q1.

    Los dos componentes salieron juntos en 2012 y se reexpresaron juntos en 2013.
    Las dos parejas son igual de co-vintage; con toda la historia ganaba la de
    2013 y el trimestre quedaba fechado ahí, desconocido durante un año en que ya
    era deducible. Ahora cada versión lleva su valor y su fecha.
    """
    crudos = pd.DataFrame([
        _flujo("Q", "2012-01-01", "2012-03-31", "2012-05-04", 40.0),
        _flujo("H1", "2012-01-01", "2012-06-30", "2012-08-03", 90.0),
        _flujo("Q", "2012-01-01", "2012-03-31", "2013-05-02", 41.0),
        _flujo("H1", "2012-01-01", "2012-06-30", "2013-08-01", 92.0),
    ])
    salida = es.derivar_trimestres_faltantes(crudos, TAGS_FLUJO)
    derivados = salida[salida["formulario"] == "DERIVADO"]
    assert [(f, v) for f, v in zip(derivados["fecha_publicacion"], derivados["valor"], strict=True)] == [
        (dt.date(2012, 8, 3), 50.0),
        (dt.date(2013, 8, 1), 51.0),
    ]
    # Y el estado de 2012 lo tiene, igual que si se armara solo con lo de 2012.
    corte = dt.date(2012, 12, 31)
    completo = es.armar_estado(salida, "NNN", es.FLUJO_EFECTIVO, asof=corte, tags=TAGS_FLUJO)
    cortado = es.armar_estado(
        es.derivar_trimestres_faltantes(_hasta(crudos, corte), TAGS_FLUJO),
        "NNN", es.FLUJO_EFECTIVO, asof=corte, tags=TAGS_FLUJO,
    )
    pd.testing.assert_frame_equal(completo, cortado)
    assert completo.loc["flujo_operacion", dt.date(2012, 6, 30)] == 50.0


def test_el_trimestre_publicado_manda_desde_que_se_publica():
    """Antes de que la emisora publique el trimestre, se deriva; desde ahí, no.

    Antes no se derivaba NADA si el trimestre aparecía publicado en algún momento,
    aunque fuera años después: con toda la historia el hueco no existía, y con lo
    publicado hasta el corte sí. Ese era otro camino por donde el corte miraba al
    futuro.
    """
    crudos = pd.DataFrame([
        _flujo("Q", "2012-01-01", "2012-03-31", "2012-05-04", 40.0),
        _flujo("H1", "2012-01-01", "2012-06-30", "2012-08-03", 90.0),
        # El trimestre aparece publicado, como comparativo, un año después.
        _flujo("Q", "2012-04-01", "2012-06-30", "2013-08-01", 49.0),
    ])
    salida = es.derivar_trimestres_faltantes(crudos, TAGS_FLUJO)
    derivados = salida[salida["formulario"] == "DERIVADO"]
    assert list(derivados["fecha_publicacion"]) == [dt.date(2012, 8, 3)]
    assert list(derivados["valor"]) == [50.0]

    junio = dt.date(2012, 6, 30)
    for corte, esperado in ((dt.date(2012, 12, 31), 50.0), (dt.date(2013, 12, 31), 49.0)):
        estado = es.armar_estado(salida, "NNN", es.FLUJO_EFECTIVO, asof=corte, tags=TAGS_FLUJO)
        assert estado.loc["flujo_operacion", junio] == esperado, corte
