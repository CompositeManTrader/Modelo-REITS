"""Los datos de la investigación (fase 2): lectores, validaciones y lo versionado."""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import pytest

from src.investigacion import datos, muestras

# --------------------------------------------------------------------------------------
# Lectores, sobre casos hechos a mano
# --------------------------------------------------------------------------------------


def test_un_dato_mensual_se_conoce_hasta_que_se_publica():
    """P1: el CPI de marzo (fecha FRED 1 de marzo) se conoce el 31 de marzo más 45 días."""
    x = pd.DataFrame({"serie": "CPIAUCSL", "fecha": pd.date_range("2010-01-01", periods=30, freq="MS"),
                      "valor": range(30)})
    fechas = pd.DatetimeIndex(["2010-04-30", "2010-05-14", "2010-05-15", "2010-05-31"])
    v = datos.conocida_en(x, "CPIAUCSL", fechas)
    # El 30 de abril solo se conoce febrero (31-mar + 45 = 15-may para marzo).
    assert v.tolist() == [1, 1, 2, 2]


def test_un_dato_diario_se_conoce_al_dia_siguiente():
    x = pd.DataFrame({"serie": "DGS10", "fecha": pd.to_datetime(["2015-06-29", "2015-06-30", "2015-07-01"]),
                      "valor": [2.0, 2.1, 2.2]})
    v = datos.conocida_en(x, "DGS10", pd.DatetimeIndex(["2015-06-30", "2015-07-01"]))
    assert v.tolist() == [2.0, 2.1]


def test_french_lee_solo_la_seccion_mensual():
    texto = ("Encabezado\n\n,Mkt-RF,SMB,HML,RF\n192607,    2.96,   -2.56,   -2.43,    0.22\n"
             "192608,    2.64,   -1.17,    3.82,    0.25\n\n Annual Factors: January-December \n"
             ",Mkt-RF,SMB,HML,RF\n1927,   29.47,   -2.04,   -4.54,    3.12\n")
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("F-F.csv", texto)
    d = datos.leer_french(z.getvalue())
    assert len(d) == 8 and d["fecha"].max() == pd.Timestamp("1926-08-31")
    assert d.loc[(d["factor"] == "RF") & (d["fecha"] == "1926-07-31"), "valor"].iloc[0] == pytest.approx(0.0022)


def test_los_retornos_mensuales_no_saltan_huecos_ni_cuentan_el_mes_en_curso():
    p = pd.DataFrame({"ticker": "X", "fecha": pd.to_datetime(["2020-01-31", "2020-02-28", "2020-04-30", "2020-05-20"]),
                      "cierre": [10.0, 11.0, 12.0, 13.0], "ajustado": [10.0, 11.0, 12.0, 13.0]})
    r = datos.retornos_mensuales(p, hoy=pd.Timestamp("2020-05-20"))
    assert r["fecha"].max() == pd.Timestamp("2020-04-30")          # mayo no ha cerrado
    assert r["retorno_total"].iloc[1] == pytest.approx(0.10)
    assert pd.isna(r["retorno_total"].iloc[2])                     # falta marzo


# --------------------------------------------------------------------------------------
# Lo versionado
# --------------------------------------------------------------------------------------

requiere_sector = pytest.mark.skipif(not (datos.DIR_SECTOR / "nareit_mensual.csv.gz").exists(),
                                     reason="No está versionado el sector.")


@requiere_sector
def test_nareit_es_coherente_y_cuadra_con_los_fondos():
    s = datos.cargar_sector()
    n = s["nareit"]
    assert set(n["indice"]) == set(datos.INDICES_NAREIT.values())
    eq = n[n["indice"] == "all_equity"]
    assert eq["fecha"].min() == pd.Timestamp("1971-12-31") and eq["fecha"].dt.is_month_end.all()
    for clave, r in datos.revisar_nareit(n).items():
        assert r["indice_total"] < 1e-3 and r["suma"] < 1e-5, clave
        assert r["meses_faltantes"] == 0 and r["yield_fuera_de_rango"] == 0, clave
    # El yield viene en fracción: el de los REITs de capital siempre estuvo entre 1% y 25%.
    assert eq["yield_dividendo"].dropna().between(0.01, 0.25).all()
    v = datos.validar_contra_fondos(n, s["fondos"]).set_index("fondo")
    assert (v["correlacion"] > 0.98).all()
    assert v.loc[["VGSIX", "VNQ"], "error_de_seguimiento"].max() < 0.02   # los indexados siguen de cerca


@requiere_sector
def test_el_archivo_fuente_de_nareit_reproduce_lo_versionado():
    xls = datos.DIR_SECTOR / "fuente" / "MonthlyHistoricalReturns.xls"
    pd.testing.assert_frame_equal(datos.leer_nareit(xls).reset_index(drop=True),
                                  datos.cargar_sector()["nareit"].reset_index(drop=True), check_exact=False,
                                  rtol=1e-8)


def test_la_macro_trae_todas_sus_series_con_rezago():
    x = datos.cargar_macro()
    if x.empty:
        pytest.skip("No está versionada la macro.")
    assert set(datos.SERIES_FRED) <= set(x["serie"])
    m = json.loads((datos.DIR_MACRO / "manifiesto.json").read_text(encoding="utf-8"))
    assert all(v["rezago_dias"] >= 1 for v in m["series"].values())
    assert m["series"]["DGS10"]["desde"] <= "1962-01-02" and m["series"]["BAA"]["desde"] <= "1919-01-01"


def test_los_mercados_sellados_estan_intactos_y_cerrados():
    huellas = muestras._huellas(muestras.DIR_SELLADO)
    if not huellas:
        pytest.skip("No están sellados los mercados de la prueba final.")
    for mercado in datos.MERCADOS_FINALES:
        for parte in ("precios", "dividendos", "tasas"):
            nombre = f"{mercado}_{parte}"
            assert nombre in huellas, nombre
            assert muestras._huella(muestras.DIR_SELLADO / f"{nombre}.csv.gz") == huellas[nombre]["sha256"], nombre
    with pytest.raises(muestras.MuestraCerrada):
        muestras.abrir_sellado("japon_precios", modelo_congelado="no-existe")
