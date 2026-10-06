"""Las reglas del juego de la investigación (fase 0): congeladas y cumplidas por el código."""

from __future__ import annotations

import pandas as pd
import pytest

from src.investigacion import bitacora, diseno, muestras
from src.investigacion.muestras import Muestra, MuestraCerrada


def test_el_diseno_quedo_fijado():
    """Los números escritos antes de tocar los datos. Moverlos después de ver resultados sería
    ajustar la prueba al pasado: si cambian, el cambio va en el historial con su motivo."""
    o, m, c, w = diseno.OBJETIVO, diseno.MUESTRAS, diseno.CRITERIOS, diseno.WALK_FORWARD
    assert (o.aportacion_mensual, o.exposicion_minima, o.exposicion_maxima, o.comision,
            o.horizontes_meses) == (1_000.0, 0.0, 1.0, 0.0025, (1, 3, 12, 36, 60))
    assert (o.impuesto_dividendo, o.impuesto_intereses, o.impuesto_ganancia) == pytest.approx((0.20, 0.20, 0.10))
    assert (m.desarrollo_hasta, m.validacion_desde) == (pd.Timestamp("2015-12-31"), pd.Timestamp("2016-01-01"))
    assert m.mercados_finales == ("japon", "australia", "singapur", "hong_kong", "reino_unido",
                                  "europa_continental", "canada", "mexico_fibras")
    assert (m.meses_minimos_por_mercado, m.fraccion_de_emisores_sellados) == (60, pytest.approx(1 / 3))
    assert m.semilla_de_emisores == "modelo-reits-investigacion-2026-10-06"
    assert (c.mejora_minima_de_tir, c.reduccion_minima_de_caida, c.costo_maximo_de_la_proteccion,
            c.fraccion_de_mercados_a_favor, c.r2_fuera_de_muestra_minimo, c.alfa_clark_west,
            c.sharpe_deflactado_minimo, c.pbo_maximo, c.apuestas_efectivas_minimas,
            c.rezago_de_ejecucion_meses, c.multiplicador_de_costos) == (
        0.0050, 0.30, 0.0025, pytest.approx(2 / 3), 0.0, 0.05, 0.95, 0.20, 100, 1, 2.0)
    assert (w.meses_minimos_para_estimar, w.reestimar_cada_meses, w.ventana) == (120, 12, "creciente")


def test_el_veredicto_sigue_la_regla_de_la_fase_0():
    assert diseno.veredicto(le_gana_en_desarrollo_y_validacion=True, cumple_todo_en_la_final=True) == "APROBADO"
    assert diseno.veredicto(le_gana_en_desarrollo_y_validacion=True, cumple_todo_en_la_final=False) == "INCONCLUSO"
    assert diseno.veredicto(le_gana_en_desarrollo_y_validacion=False, cumple_todo_en_la_final=False) == "RECHAZADO"


def _serie() -> pd.DataFrame:
    fechas = pd.date_range("2014-01-31", "2017-12-31", freq="ME")
    return pd.DataFrame({"fecha": fechas, "valor": range(len(fechas))})


def test_desarrollo_no_ve_2016(tmp_path):
    x = _serie()
    d = muestras.recortar(x, columna="fecha")
    assert d["fecha"].max() == pd.Timestamp("2015-12-31")
    # Con índice de fechas, igual; y una serie también.
    s = x.set_index("fecha")["valor"]
    assert muestras.recortar(s).index.max() == pd.Timestamp("2015-12-31")
    # Un retorno «siguiente» calculado sobre lo recortado no puede mirar 2016.
    adelante = d["valor"].shift(-1)
    assert pd.isna(adelante.iloc[-1])


def test_la_validacion_pide_motivo_y_queda_en_la_bitacora(tmp_path):
    ruta = tmp_path / "bitacora.csv"
    with pytest.raises(MuestraCerrada):
        muestras.recortar(_serie(), Muestra.VALIDACION, columna="fecha", ruta_bitacora=ruta)
    v = muestras.recortar(_serie(), "validacion", columna="fecha", motivo="escoger entre dos candidatos",
                          ruta_bitacora=ruta)
    assert v["fecha"].max() == pd.Timestamp("2017-12-31")
    b = bitacora.leer(ruta)
    assert list(b["familia"]) == ["apertura"] and "escoger" in b["parametros"].iloc[0]
    with pytest.raises(MuestraCerrada):
        muestras.recortar(_serie(), Muestra.FINAL, columna="fecha")


def test_los_emisores_sellados_son_un_tercio_y_siempre_los_mismos():
    tickers = [f"T{i:04d}" for i in range(3_000)]
    sellados = [t for t in tickers if muestras.esta_sellado(t)]
    assert 0.30 < len(sellados) / len(tickers) < 0.37
    assert muestras.esta_sellado("o") == muestras.esta_sellado(" O ")
    x = pd.DataFrame({"ticker": tickers})
    assert len(muestras.sin_sellados(x)) == len(tickers) - len(sellados)


def test_la_prueba_final_no_se_abre_sin_modelo_congelado_ni_si_el_archivo_cambio(tmp_path):
    raiz, ruta = tmp_path / "sellado", tmp_path / "bitacora.csv"
    datos = pd.DataFrame({"fecha": ["2010-01-31", "2010-02-28"], "retorno": [0.01, -0.02]})
    archivo = muestras.sellar(datos, "japon", raiz=raiz, fuente="prueba")
    with pytest.raises(MuestraCerrada):
        muestras.abrir_sellado("japon", modelo_congelado="m1", raiz=raiz, ruta_bitacora=ruta)
    muestras.congelar("m1", {"senal": "x"}, ruta_bitacora=ruta)
    assert muestras.abrir_sellado("japon", modelo_congelado="m1", raiz=raiz, ruta_bitacora=ruta)["retorno"].tolist() \
        == [0.01, -0.02]
    # Un archivo tocado después de sellarlo ya no es una prueba limpia.
    datos.assign(retorno=[0.05, 0.05]).to_csv(archivo, index=False, compression="gzip")
    with pytest.raises(MuestraCerrada):
        muestras.abrir_sellado("japon", modelo_congelado="m1", raiz=raiz, ruta_bitacora=ruta)


def test_la_bitacora_cuenta_intentos_distintos(tmp_path):
    ruta = tmp_path / "bitacora.csv"
    for p in ({"meses": 10}, {"meses": 12}, {"meses": 10}):
        bitacora.registrar(fase="5", familia="tendencia", prueba="promedio movil", muestra="desarrollo",
                           parametros=p, metrica="tir", valor=0.08, ruta=ruta)
    bitacora.registrar(fase="5", familia="valuacion", prueba="yield", muestra="desarrollo", ruta=ruta)
    muestras.congelar("m1", {}, ruta_bitacora=ruta)
    assert bitacora.intentos("tendencia", ruta=ruta) == 2
    assert bitacora.intentos(ruta=ruta) == 3
    assert bitacora.modelos_congelados(ruta) == {"m1"}
