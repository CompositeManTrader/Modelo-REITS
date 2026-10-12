"""La sensibilidad fiscal: los perfiles del broker de EE. UU. y su paso por los simuladores."""

from __future__ import annotations

from dataclasses import fields, replace

import numpy as np
import pandas as pd
import pytest

from src.investigacion import (
    bitacora,
    datos,
    exploracion,
    fase6,
    fase8,
    muestras,
    resultados,
    timing,
)
from src.investigacion import sensibilidad as sb
from src.investigacion.diseno import OBJETIVO, PERFILES, impuesto_dividendo_broker, perfil_broker
from src.investigacion.simulacion import Mercado, benchmark, simular
from tests.test_69_investigacion_fase8 import _mercado_sintetico
from tests.test_72_investigacion_fase6 import FECHAS, _panel

# --------------------------------------------------------------------------------------
# Los perfiles
# --------------------------------------------------------------------------------------


def test_el_sic_sigue_siendo_la_linea_base():
    assert PERFILES["sic"] is OBJETIVO
    assert (OBJETIVO.impuesto_dividendo, OBJETIVO.impuesto_intereses, OBJETIVO.impuesto_ganancia,
            OBJETIVO.comision) == pytest.approx((0.20, 0.20, 0.10, 0.0025))


@pytest.mark.parametrize(("clave", "marginal", "dividendo"), [("broker_30", 0.30, 0.39), ("broker_35", 0.35, 0.44)])
def test_las_tasas_del_broker(clave, marginal, dividendo):
    o = PERFILES[clave]
    assert o.impuesto_dividendo == pytest.approx(dividendo)          # marginal + 10% × (1 − 10% retenido)
    assert o.impuesto_intereses == pytest.approx(marginal)
    assert o.impuesto_ganancia == pytest.approx(0.10)                # Art. 129, Criterio 37/ISR/N
    assert o.comision == 0.0
    cambian = {"impuesto_dividendo", "impuesto_intereses", "impuesto_ganancia", "comision"}
    for f in fields(OBJETIVO):
        if f.name not in cambian:
            assert getattr(o, f.name) == getattr(OBJETIVO, f.name), f.name


def test_el_dividendo_paga_la_marginal_mas_nueve_puntos():
    for m in (0.25, 0.30, 0.35):
        assert impuesto_dividendo_broker(m) == pytest.approx(m + 0.09)
    assert perfil_broker(0.30) == PERFILES["broker_30"]


def test_los_parametros_de_los_estudios_salen_del_mismo_perfil():
    from src.estudio import reglas

    assert sb.parametros_de(OBJETIVO) == reglas.PARAMETROS
    p = sb.parametros_de(PERFILES["broker_35"])
    assert (p.impuesto_dividendo, p.impuesto_intereses, p.impuesto_ganancia, p.comision) == pytest.approx(
        (0.44, 0.35, 0.10, 0.0))


# --------------------------------------------------------------------------------------
# El perfil pasa por los simuladores
# --------------------------------------------------------------------------------------


def _mercado(n=120, precio=0.004, ingreso=0.005, efectivo=0.003) -> Mercado:
    return Mercado(pd.date_range("2000-01-31", periods=n, freq="ME"), np.full(n, precio), np.full(n, ingreso),
                   np.full(n, efectivo))


def test_el_broker_le_quita_al_que_cobra_dividendo():
    m = _mercado()
    sic, b30, b35 = (benchmark(m, objetivo=PERFILES[k]).tir for k in ("sic", "broker_30", "broker_35"))
    assert sic > b30 > b35


def test_en_efectivo_rinde_la_tasa_menos_la_marginal():
    o = replace(PERFILES["broker_30"], comision=0.0)
    r = simular(_mercado(efectivo=0.005), 0.0, objetivo=o)
    assert r.tir == pytest.approx((1 + 0.005 * 0.70) ** 12 - 1, abs=2e-4)


def test_timing_evaluar_usa_el_perfil_y_por_omision_el_sic():
    idx = pd.date_range("1990-01-31", periods=180, freq="ME")
    rng = np.random.default_rng(3)
    x = pd.DataFrame({"retorno_total": rng.normal(0.008, 0.04, len(idx)), "retorno_ingreso": 0.005,
                      "efectivo": 0.003}, index=idx)
    x["retorno_precio"] = x["retorno_total"] - x["retorno_ingreso"]
    e = pd.Series((rng.random(len(idx)) > 0.3).astype(float), index=idx)
    senal = timing.Senal("prueba", "prueba", lambda x_, i_: e, "")
    kw = {"muestra": "prueba", "registrar": False, "con_prediccion": False}
    omision = timing.evaluar(senal, "regla", e, x, x, **kw)
    sic = timing.evaluar(senal, "regla", e, x, x, objetivo=OBJETIVO, **kw)
    broker = timing.evaluar(senal, "regla", e, x, x, objetivo=PERFILES["broker_35"], **kw)
    assert omision["mejora_rebalanceo"] == sic["mejora_rebalanceo"]
    assert broker["tir_aportar_siempre"] < sic["tir_aportar_siempre"]
    # Sin comisión, el doble costo no cambia nada.
    assert broker["mejora_rebalanceo_doble_costo"] == pytest.approx(broker["mejora_rebalanceo"])
    assert "r2_12m" not in broker


def test_fase6_simular_cobra_el_dividendo_y_la_comision_del_perfil():
    x = _panel(1)
    x["retorno"], x["dividendo"] = 0.0, 0.0
    sel = x[["fecha", "cik"]]
    sin_comision = fase6.simular(sel, x, desde=FECHAS[0], hasta=FECHAS[-1], objetivo=PERFILES["broker_30"])
    assert sin_comision.tir == pytest.approx(0.0, abs=1e-9)          # nada se mueve y no hay comisión
    x["retorno"], x["dividendo"] = 0.02, 0.02
    sic = fase6.simular(sel, x, desde=FECHAS[0], hasta=FECHAS[-1])
    b44 = fase6.simular(sel, x, desde=FECHAS[0], hasta=FECHAS[-1], objetivo=PERFILES["broker_35"])
    assert b44.tir < sic.tir


def test_fase8_evalua_cada_perfil(tmp_path):
    raiz, ruta = tmp_path / "sellado", tmp_path / "bitacora.csv"
    _mercado_sintetico(raiz, "japon")
    muestras.congelar(fase8.MODELO, fase8.DESCRIPCION, ruta_bitacora=ruta)
    x, _ = fase8.serie_de_mercado("japon", raiz=raiz, ruta_bitacora=ruta)
    omision, b35 = fase8.evaluar_mercado(x, "japon"), fase8.evaluar_mercado(x, "japon", objetivo=PERFILES["broker_35"])
    assert omision == fase8.evaluar_mercado(x, "japon", objetivo=OBJETIVO)
    assert b35["tir_aportar_siempre"] != omision["tir_aportar_siempre"]
    assert b35["mejora_doble_costo"] == pytest.approx(b35["mejora"])      # sin comisión no hay doble costo
    assert omision["mejora_doble_costo"] < omision["mejora"]


# --------------------------------------------------------------------------------------
# Los sellados se abren una vez por corrida y todo queda en la bitácora
# --------------------------------------------------------------------------------------


def test_la_fase8_abre_cada_mercado_una_vez_para_los_tres_perfiles(tmp_path):
    raiz, ruta = tmp_path / "sellado", tmp_path / "bitacora.csv"
    for n in datos.MERCADOS_FINALES:
        _mercado_sintetico(raiz, n)
    v, m, c = sb.fase8_(abrir=True, ruta_bitacora=ruta, raiz=raiz)
    b = bitacora.leer(ruta)
    congelados = b[b["familia"] == "congelado"]["prueba"].tolist()
    assert congelados == [sb.MODELO_FASE8]
    aperturas = b[(b["familia"] == "apertura") & (b["prueba"] != "abrir validacion")]
    assert len(aperturas) == 3 * len(datos.MERCADOS_FINALES)        # precios, dividendos y tasas, una vez
    assert set(aperturas["parametros"].map(lambda p: p.split('"modelo": ')[1])) == {f'"{sb.MODELO_FASE8}"}}'}
    assert len(m) == 3 * len(datos.MERCADOS_FINALES) and set(c["perfil"]) == set(PERFILES)
    s = b[b["familia"] == sb.FAMILIA]
    assert len(s) == 3 + 3 * len(datos.MERCADOS_FINALES)            # validación y cada mercado, por perfil
    assert s["parametros"].str.contains('"perfil"').all()


def test_sin_abrir_no_toca_los_sellados(tmp_path):
    ruta = tmp_path / "bitacora.csv"
    v, m, c = sb.fase8_(abrir=False, ruta_bitacora=ruta, raiz=tmp_path / "no_existe")
    b = bitacora.leer(ruta)
    assert m.empty and c.empty and len(v) == len(PERFILES)
    assert (b["familia"] != "congelado").all()
    assert set(b.loc[b["familia"] == "apertura", "prueba"]) == {"abrir validacion"}


def test_las_reevaluaciones_no_cuentan_como_intentos(tmp_path):
    ruta = tmp_path / "bitacora.csv"
    bitacora.registrar(fase="5", familia="tendencia", prueba="a", muestra="desarrollo", ruta=ruta)
    bitacora.registrar(fase="5", familia=sb.FAMILIA, prueba="a", muestra="desarrollo",
                       parametros={"perfil": "broker_30"}, ruta=ruta)
    assert bitacora.intentos(ruta=ruta) == 2
    assert bitacora.intentos(ruta=ruta, excluir=(sb.FAMILIA,)) == 1
    assert bitacora.intentos(sb.FAMILIA, ruta=ruta) == 1


def test_lo_que_solo_pasa_con_el_broker_es_posterior():
    assert sb.veredicto_con_perfil("RECHAZADO", "RECHAZADO") == "RECHAZADO"
    assert sb.veredicto_con_perfil("RECHAZADO", "APROBADO") == "INCONCLUSO (posterior)"
    assert sb.veredicto_con_perfil("RECHAZADO", "INCONCLUSO") == "INCONCLUSO (posterior)"
    assert sb.veredicto_con_perfil("INCONCLUSO", "RECHAZADO") == "RECHAZADO"
    assert sb.veredicto_con_perfil("APROBADO", "APROBADO") == "APROBADO"


# --------------------------------------------------------------------------------------
# Con el perfil SIC se reproduce lo guardado
# --------------------------------------------------------------------------------------

_GUARDADO = resultados.cargar()
pide_resultados = pytest.mark.skipif(not {"fase3", "fase5"} <= set(_GUARDADO), reason="sin resultados guardados")


@pide_resultados
def test_el_techo_con_el_sic_es_el_guardado():
    t = exploracion.techo(exploracion.sector()).tabla
    g = _GUARDADO["fase3"]["techo"]
    assert np.allclose(t["tir"].to_numpy(), g["tir"].to_numpy(), atol=1e-8)


@pide_resultados
def test_la_tendencia_de_la_fase5_con_el_sic_es_la_guardada():
    from src.investigacion import fase5

    x = exploracion.sector()
    ind = exploracion.indicadores(x)
    senal, nombre, e = next(r for r in fase5.reglas_del_catalogo(x, ind)
                            if r[0].nombre == "tendencia de 10 meses" and r[1] == "signo")
    r = timing.evaluar(senal, nombre, e, x, ind, muestra="desarrollo", registrar=False, con_prediccion=False)
    g = _GUARDADO["fase5"]["desarrollo"].set_index(["senal", "regla"]).loc[(senal.nombre, nombre)]
    assert r["mejora_rebalanceo"] == pytest.approx(g["mejora_rebalanceo"], abs=1e-8)


def test_la_columna_sic_de_la_sensibilidad_es_la_de_cada_fase():
    s = sb.cargar()
    if s is None or "fase5" not in _GUARDADO:
        pytest.skip("sin la sensibilidad guardada")
    d5 = s["fase5_desarrollo"]
    a = d5[d5["perfil"] == "sic"].set_index(["senal", "regla"])["mejora_rebalanceo"]
    b = _GUARDADO["fase5"]["desarrollo"].set_index(["senal", "regla"])["mejora_rebalanceo"].reindex(a.index)
    assert np.allclose(a.to_numpy(), b.to_numpy(), atol=1e-8)
    d6 = s["fase6_desarrollo"]
    a = d6[d6["perfil"] == "sic"].set_index("regla")["mejora"]
    b = _GUARDADO["fase6"]["desarrollo"].set_index("regla")["mejora"].reindex(a.index)
    assert np.allclose(a.to_numpy(), b.to_numpy(), atol=1e-8)
    t3 = s["fase3_techo"]
    assert np.allclose(t3[t3["perfil"] == "sic"]["tir"].to_numpy(), _GUARDADO["fase3"]["techo"]["tir"].to_numpy(),
                       atol=1e-8)
    if not s["fase8_validacion"].empty:
        v = s["fase8_validacion"].set_index("perfil").loc["sic", "mejora"]
        assert v == pytest.approx(_GUARDADO["fase8"]["resumen"]["validacion"]["mejora"], abs=1e-8)
    assert set(s["perfiles"]["perfil"]) == set(PERFILES)


def test_los_emisores_sellados_se_abren_una_vez_para_los_tres_perfiles(tmp_path):
    from src.investigacion import emisores

    raiz, ruta = tmp_path / "sellado", tmp_path / "bitacora.csv"
    fechas = pd.date_range("2010-03-31", periods=40, freq="QE")
    muestras.sellar(_panel(40, fechas=fechas), emisores.ARCHIVO_SELLADO, raiz=raiz)
    f = sb.fase6_final(pbo=0.04, dsr=0.39, ruta_bitacora=ruta, raiz_sellado=raiz)
    b = bitacora.leer(ruta)
    assert b.loc[b["familia"] == "congelado", "prueba"].tolist() == [sb.MODELO_FASE6]
    assert (b["familia"] == "apertura").sum() == 1
    assert list(f["perfil"]) == list(PERFILES)
    assert set(f["veredicto_declarado"]) <= {"RECHAZADO", "INCONCLUSO", "APROBADO", "INCONCLUSO (posterior)"}
    assert (f["tir_todos"].iloc[1:] < f["tir_todos"].iloc[0]).all()   # el dividendo paga más con el broker
