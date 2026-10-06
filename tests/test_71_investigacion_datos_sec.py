"""Fase 6, los datos de la SEC: CUSIP, 13F y estados financieros conocidos a su fecha."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.investigacion import emisores as em
from src.investigacion import fundamentales as fu
from src.investigacion import sec
from src.investigacion import trece_f as tf

# ------------------------------------------------------------------------------- CUSIP


@pytest.mark.parametrize("cusip", ["756109104", "264411505", "828806109", "88579Y101", "00081T108"])
def test_cusips_reales_pasan_el_digito_verificador(cusip):
    assert tf.es_cusip(cusip)


@pytest.mark.parametrize("cusip", ["756109105", "264411500", "ABCDEFGHI", "12345678", "000000000"[:8] + "X"])
def test_cusips_mal_escritos_no_pasan(cusip):
    assert not tf.es_cusip(cusip)


def test_cusip_en_la_portada_de_un_13g():
    texto = """<p>SCHEDULE 13G</p><p>DUKE REALTY CORP</p><p>(Title of Class of Securities) Common Stock</p>
    <p>264411 50 5</p><p>(CUSIP Number)</p><p>Telephone 610-669-1000 Date 12/31/2021</p>"""
    assert sec.cusips_en_texto(texto) == ["264411505"]


def test_un_numero_lejos_de_la_palabra_cusip_no_cuenta():
    texto = "CUSIP No. 756109104" + " relleno" * 200 + " 264411505"
    assert sec.cusips_en_texto(texto) == ["756109104"]


# ------------------------------------------------------------------------------- 13F


def test_13f_en_texto_lee_cusip_valor_y_acciones():
    texto = """
REALPAGE INC                  COM                75606N109         5830      210250SH      SOLE          210250
REALTY INCOME CORP            COM                756109104       410027    11731825SH      SOLE        11731825
DUKE REALTY CORP              COM NEW            264411 50 5     27,557   1,832,242 SH   SOLE        1832242
ALGO MAL                      COM                756109105          100        1000SH      SOLE            1000
OPCION                        PUT                756109104          100        1000PRN     SOLE            1000
"""
    p = tf.parsear_texto(texto)
    assert p["cusip"].tolist() == ["75606N109", "756109104", "264411505"]
    assert p.loc[p["cusip"] == "264411505", "valor_miles"].iat[0] == 27557
    assert p.loc[p["cusip"] == "264411505", "acciones"].iat[0] == 1832242


def test_13f_xml_de_transicion():
    texto = """<informationTable><infoTable><nameOfIssuer>REALTY INCOME</nameOfIssuer><cusip>756109104</cusip>
    <value>500</value><shrsOrPrnAmt><sshPrnamt>10000</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
    </infoTable><infoTable><cusip>756109104</cusip><value>5</value><shrsOrPrnAmt><sshPrnamt>100</sshPrnamt>
    <sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt><putCall>Put</putCall></infoTable></informationTable>"""
    p = tf.documento_xml_tabla(texto)
    assert len(p) == 1 and p["valor_miles"].iat[0] == 500 and p["acciones"].iat[0] == 10000


def _conjunto(filas, presentado="15-FEB-2014", periodo="31-DEC-2013"):
    tabla = pd.DataFrame(filas, columns=["ACCESSION_NUMBER", "NAMEOFISSUER", "TITLEOFCLASS", "CUSIP", "VALUE",
                                         "SSHPRNAMT", "SSHPRNAMTTYPE", "PUTCALL"])
    acc = tabla["ACCESSION_NUMBER"].unique()
    envios = pd.DataFrame({"ACCESSION_NUMBER": acc, "SUBMISSIONTYPE": "13F-HR", "FILING_DATE": presentado,
                           "PERIODOFREPORT": periodo})
    return tabla, envios


def test_el_precio_es_la_mediana_entre_administradores_y_resiste_un_error_de_captura():
    filas = [
        ("a1", "DUKE REALTY CORP", "COM", "264411505", "15040", "1000000", "SH", None),
        ("a2", "DUKE REALTY CORP", "COM", "264411505", "1504", "100000", "SH", None),
        ("a3", "DUKE REALTY CORP", "COM", "264411505", "15040000", "1000000", "SH", None),  # en dólares por error
        ("a4", "DUKE REALTY CORP", "COM", "264411505", "151", "10000", "SH", None),
        ("a4", "DUKE REALTY CORP", "COM", "264411505", "1", "100", "SH", "PUT"),
    ]
    a = tf.agregar(*_conjunto(filas))
    assert len(a) == 1
    assert a["tenedores"].iat[0] == 4
    assert a["precio"].iat[0] == pytest.approx(15.04, abs=0.05)


def test_desde_2023_el_valor_viene_en_dolares():
    filas = [("a1", "X", "COM", "756109104", "5500000", "100000", "SH", None)]
    a = tf.agregar(*_conjunto(filas, presentado="14-FEB-2023", periodo="31-DEC-2022"))
    assert a["precio"].iat[0] == pytest.approx(55.0)
    b = tf.agregar(*_conjunto(filas, presentado="14-NOV-2022", periodo="30-SEP-2022"))
    assert b["precio"].iat[0] == pytest.approx(55_000.0)


# ------------------------------------------------------------------------------- XBRL


def _cf(etiqueta, hechos, tax="us-gaap", unidad="USD"):
    return {"facts": {tax: {etiqueta: {"units": {unidad: hechos}}}}}


def _h(inicio, fin, val, filed, form="10-Q"):
    return {"start": inicio, "end": fin, "val": val, "filed": filed, "form": form}


def test_el_trimestre_que_falta_se_deriva_del_acumulado():
    cf = _cf("NetIncomeLoss", [
        _h("2020-01-01", "2020-03-31", 10, "2020-05-01"),
        _h("2020-01-01", "2020-06-30", 25, "2020-08-01"),  # solo el semestre
        _h("2020-07-01", "2020-09-30", 12, "2020-11-01"),
        _h("2020-01-01", "2020-12-31", 50, "2021-02-20", "10-K"),
    ])
    q = fu.trimestres(fu.hechos(cf, "utilidad_comun")).set_index("fin")["valor"]
    assert q[pd.Timestamp("2020-06-30")] == 15
    assert fu.doce_meses(fu.hechos(cf, "utilidad_comun")).set_index("fin")["valor"].iat[-1] == 50


def test_doce_meses_se_conoce_cuando_se_conoce_su_ultima_pieza():
    hechos = [_h("2020-01-01", "2020-12-31", 40, "2021-02-20", "10-K"),
              _h("2021-01-01", "2021-03-31", 11, "2021-05-01"), _h("2020-01-01", "2020-03-31", 9, "2020-05-01"),
              _h("2020-04-01", "2020-06-30", 10, "2020-08-01"), _h("2020-07-01", "2020-09-30", 10, "2020-11-01")]
    d = fu.doce_meses(fu.hechos(_cf("NetIncomeLoss", hechos), "utilidad_comun")).set_index("fin")
    # TTM a marzo 2021 = Q2+Q3+Q4 de 2020 + Q1 2021; Q4 = 40 − (9+10+10) = 11.
    assert d.loc[pd.Timestamp("2021-03-31"), "valor"] == pytest.approx(10 + 10 + 11 + 11)
    assert d.loc[pd.Timestamp("2021-03-31"), "conocido"] == pd.Timestamp("2021-05-01")


def test_la_primera_version_publicada_gana_a_la_reexpresion():
    cf = _cf("Assets", [{"end": "2020-12-31", "val": 100, "filed": "2021-02-20", "form": "10-K"},
                        {"end": "2020-12-31", "val": 130, "filed": "2022-02-20", "form": "10-K"}])
    h = fu.hechos(cf, "activos")
    assert h["valor"].tolist() == [100]


def test_la_etiqueta_preferida_gana_periodo_por_periodo():
    cf = {"facts": {"us-gaap": {
        "CommonStockDividendsPerShareDeclared": {"units": {"USD/shares": [_h("2012-01-01", "2012-12-31", 1.7, "2013-02-20")]}},
        "CommonStockDividendsPerShareCashPaid": {"units": {"USD/shares": [
            _h("2012-01-01", "2012-12-31", 1.6, "2013-02-20"), _h("2019-01-01", "2019-12-31", 2.7, "2020-02-20")]}},
    }}}
    h = fu.hechos(cf, "dps").set_index("fin")["valor"]
    assert h[pd.Timestamp("2012-12-31")] == 1.7 and h[pd.Timestamp("2019-12-31")] == 2.7


def test_promedio_de_acciones_del_cuarto_trimestre():
    hechos = [_h("2020-01-01", "2020-03-31", 100, "2020-05-01"), _h("2020-04-01", "2020-06-30", 100, "2020-08-01"),
              _h("2020-07-01", "2020-09-30", 100, "2020-11-01"), _h("2020-01-01", "2020-12-31", 110, "2021-02-20")]
    cf = _cf("WeightedAverageNumberOfSharesOutstandingBasic", hechos, unidad="shares")
    s = fu.promedio_doce_meses(fu.hechos(cf, "acciones_promedio")).set_index("fin")["valor"]
    assert s[pd.Timestamp("2020-12-31")] == 110  # el del año, no una suma


def test_a_la_fecha_no_usa_lo_que_todavia_no_se_publicaba():
    s = pd.DataFrame({"partida": "activos", "fin": pd.to_datetime(["2020-12-31", "2021-03-31"]),
                      "valor": [100.0, 120.0], "conocido": pd.to_datetime(["2021-02-20", "2021-05-05"])})
    x = fu.a_la_fecha(s, pd.DatetimeIndex(["2021-01-31", "2021-03-31", "2021-06-30", "2023-06-30"]))
    assert pd.isna(x["activos"].iat[0])
    assert x["activos"].iat[1] == 100.0 and x["activos"].iat[2] == 120.0
    assert pd.isna(x["activos"].iat[3])  # dejó de reportar: ya no vale


def test_ffo_con_la_definicion_de_nareit():
    x = pd.DataFrame({"utilidad_comun_12m": [100.0], "depreciacion_12m": [50.0], "ganancia_venta_12m": [20.0],
                      "deterioro_12m": [5.0]})
    assert fu.ffo(x).iat[0] == 135.0
    assert fu.ffo(x.drop(columns=["ganancia_venta_12m", "deterioro_12m"])).iat[0] == 150.0


# ------------------------------------------------------------------------------- limpieza



def test_un_13d_que_el_reit_presenta_sobre_otra_empresa_no_le_presta_su_cusip():
    cusips = pd.DataFrame({"cik": ["vno", "vno"], "cusip": ["929042109", "708160106"], "citas": [17, 1]})
    agregado = pd.DataFrame({
        "fecha": pd.to_datetime(["2013-06-30"] * 2), "cusip": ["929042109", "708160106"], "precio": [82.85, 17.08],
        "tenedores": [306, 260], "acciones_13f": [1.6e8, 2.1e8], "p25": [82.84, 17.07], "p75": [82.86, 17.09],
        "nombre": ["VORNADO RLTY TR", "PENNEY J C INC"], "clase": ["SH BEN INT", "COM"]})
    p = em.precios(agregado, cusips, {"vno": em.fichas("VORNADO REALTY TRUST")})
    assert p["cusip"].tolist() == ["929042109"]


def test_un_bono_del_emisor_no_es_su_precio():
    cusips = pd.DataFrame({"cik": ["x"], "cusip": ["92339V100"], "citas": [5]})
    agregado = pd.DataFrame({
        "fecha": pd.to_datetime(["2017-12-31"] * 2), "cusip": ["92339V100", "92339VAA2"], "precio": [7.79, 1.0],
        "tenedores": [357, 900], "acciones_13f": [8e8, 8e7], "p25": [7.78, 1.0], "p75": [7.80, 1.0],
        "nombre": ["VEREIT INC", "VEREIT INC"], "clase": ["COM", "NOTE"]})
    assert em.precios(agregado, cusips)["precio"].tolist() == [7.79]


def test_split_inverso_con_fusion_se_reconoce_por_el_cambio_de_cusip():
    # Kite Realty, 2014: split inverso 1 a 4 el mismo trimestre que una fusión que duplicó las acciones.
    p = pd.DataFrame({"cik": "krg", "fecha": pd.to_datetime(["2014-06-30", "2014-09-30"]),
                      "cusip": ["49803T102", "49803T300"], "precio": [6.14, 24.24], "acciones_13f": [1.27e8, 6.2e7]})
    sp = em.splits(p)
    assert sp["factor"].tolist() == [0.25]


def test_un_pico_que_regresa_es_un_error():
    p = pd.DataFrame({"cik": "x", "fecha": pd.date_range("2015-03-31", periods=4, freq="QE"),
                      "cusip": "000000000", "precio": [10.0, 40.0, 10.5, 11.0], "acciones_13f": 1e6})
    limpio = em.quitar_picos(p, em.splits(p))
    assert limpio["precio"].tolist() == [10.0, 10.5, 11.0]


def test_quien_reporto_en_miles_cuando_eran_dolares_se_corrige():
    t = pd.DataFrame({"fecha": ["2022-12-31"] * 4, "cusip": ["756109104"] * 4, "acciones": [1e6, 5e5, 1000, 2000],
                      "precio": [57.0, 57.1, 0.057, 0.0571], "nombre": "X", "clase": "COM"})
    assert sorted(tf.corregir_escala(t)["precio"].round(2).tolist()) == [57.0, 57.0, 57.1, 57.1]


def test_la_clase_a_mano_gana_a_la_etiqueta_y_la_etiqueta_a_la_regla():
    clas = pd.DataFrame({"cik": ["a", "b", "c"], "clase": ["capital", "capital", "sin_clasificar"]})
    etiquetas = pd.DataFrame({"cik": ["b"], "es_reit_de_capital": [False]})
    manual = pd.DataFrame({"cik": ["c"], "clase": ["hipotecario"]})
    c = em.clase_final(clas, etiquetas, manual)
    assert c.to_dict() == {"a": "capital", "b": "otro", "c": "hipotecario"}


def test_es_reit_solo_si_un_10k_reciente_lo_dice():
    fts = pd.DataFrame({"cik": ["conv"], "fecha": ["2015-02-27"]})
    cik = pd.Series(["conv", "conv", "conv", "viejo"])
    fecha = pd.Series(pd.to_datetime(["2014-12-31", "2015-03-31", "2018-03-31", "2012-03-31"]))
    sic = pd.Series(["6500", "6500", "6500", "6798"])
    assert em.es_reit(cik, fecha, fts, sic).tolist() == [False, True, False, True]


def test_sin_dividendo_trimestral_se_usa_la_cuarta_parte_del_anual():
    p = pd.DataFrame({"cik": "x", "fecha": pd.to_datetime(["2015-03-31", "2015-06-30"]), "precio": [20.0, 20.0]})
    dq = pd.DataFrame({"cik": "x", "fin": pd.to_datetime(["2015-03-31"]), "dps": [0.30]})
    series_ = pd.DataFrame({"cik": "x", "partida": "dps_12m", "fin": pd.to_datetime(["2015-06-30"]), "valor": [1.20]})
    d = em.dividendos_por_trimestre(dq, p, series_).set_index("fecha")
    assert d.loc["2015-03-31", "dps"] == pytest.approx(0.30) and d.loc["2015-03-31", "fuente"] == "trimestral"
    assert d.loc["2015-06-30", "dps"] == pytest.approx(0.30) and d.loc["2015-06-30", "fuente"] == "doce_meses"


def test_el_sellado_de_un_emisor_que_ya_no_cotiza_usa_su_cik():
    assert em.identificador("0000783280", np.nan) == "CIK0000783280"
    assert em.identificador("0000726728", "O|O-PR") == "O"
