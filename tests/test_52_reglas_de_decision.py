"""Reglas de decisión y su backtest (``src/estudio/reglas.py``).

Dos familias de pruebas:

* El motor, sobre escenarios sintéticos cuyo resultado se calcula a mano: qué se
  compra, cuándo, a qué precio y cuánto impuesto se paga. Un motor de backtest que
  «se ve razonable» no está probado; uno que reproduce centavos, sí.
* Las señales, sobre la historia versionada: que el semáforo de cada fin de mes use
  solo lo publicado a esa fecha (P1), que el payout compare periodos iguales y que la
  persistencia de la Puerta 3 se cuente en reportes.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
for ruta in (str(RAIZ), str(RAIZ / "app")):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from src.estudio import mercado, reglas  # noqa: E402
from src.estudio.mercado import EventoDeCapital  # noqa: E402
from src.estudio.reglas import Decision, Parametros, Variante  # noqa: E402

D = dt.date
SIN_FRICCION = Parametros(impuesto_dividendo=0.0, impuesto_ganancia=0.0, impuesto_intereses=0.0, comision=0.0)


# --------------------------------------------------------------------------------------
# Escenarios sintéticos
# --------------------------------------------------------------------------------------


def _escenario(precios: list[float], decisiones: list[str], *, dividendos=(), escisiones=(),
               inicio: str = "2020-01-01"):
    """Un papel que cotiza el primer y el último día hábil de cada mes.

    ``precios`` va por sesión (dos por mes); ``decisiones``, una por fin de mes.
    """
    meses = pd.period_range(inicio, periods=len(decisiones) + 1, freq="M")
    sesiones = []
    for m in meses:
        sesiones += [m.start_time.normalize(), (m.end_time - pd.Timedelta(days=1)).normalize()]
    sesiones = pd.DatetimeIndex(sesiones[: len(precios)])
    tabla = pd.DataFrame({"precio_base": precios, "usdmxn": 20.0, "rt_usd_neto": np.nan}, index=sesiones)
    div = pd.DataFrame([{"fecha_ex": pd.Timestamp(f), "monto_base": m, "monto_pagado": m, "tipo": "regular"}
                        for f, m in dividendos], columns=["fecha_ex", "monto_base", "monto_pagado", "tipo"])
    hm = SimpleNamespace(dividendos=div, escisiones=tuple(escisiones))
    e = SimpleNamespace(tabla=tabla, historia_mercado=hm)
    fines = reglas.fines_de_mes(sesiones)[: len(decisiones)]
    sen = reglas.Senales("ZZ", pd.DataFrame({"decision": decisiones, "disparadores": ""}, index=fines),
                        pd.DataFrame())
    return e, sen


def test_la_decision_de_fin_de_mes_se_ejecuta_en_la_sesion_siguiente():
    """Lag de ejecución: la señal usa el cierre del último día; nadie opera a ese cierre."""
    e, sen = _escenario([10, 99, 20, 99], ["SIN SEÑAL"])
    s = reglas.simular(e, sen, pd.Series(dtype=float), variante=Variante.MODELO, parametros=SIN_FRICCION)
    assert list(s.ejecuciones.index) == [e.tabla.index[2]]
    assert s.diaria["acciones"].iloc[-1] == pytest.approx(1_000 / 20)


def test_comprar_menos_invierte_la_mitad_y_comprar_toda_la_reserva():
    e, sen = _escenario([10] * 8, ["COMPRAR MENOS", "NO COMPRAR", "COMPRAR"])
    s = reglas.simular(e, sen, pd.Series(dtype=float), variante=Variante.MODELO, parametros=SIN_FRICCION)
    comprado = s.ejecuciones["comprado"].tolist()
    assert comprado == pytest.approx([500, 0, 2_500])   # la mitad; nada; 1,000 + 1,500 de reserva
    assert s.diaria["reserva"].iloc[-1] == pytest.approx(0)
    assert s.ejecuciones["intensidad"].tolist() == pytest.approx([0.5, 0.0, 2.5])


def test_vender_paga_el_impuesto_sobre_la_ganancia_y_deja_todo_en_la_reserva():
    e, sen = _escenario([10, 10, 10, 10, 20, 20, 20, 20], ["SIN SEÑAL", "SIN SEÑAL", "VENDER"])
    p = Parametros(impuesto_dividendo=0.0, impuesto_intereses=0.0, comision=0.0, impuesto_ganancia=0.10)
    s = reglas.simular(e, sen, pd.Series(dtype=float), variante=Variante.MODELO, parametros=p)
    (v,) = s.ventas.to_dict("records")
    # 100 acciones a 10 y 50 a 20; se venden las 150 a 20.
    assert v["valor"] == pytest.approx(150 * 20)
    assert v["impuesto"] == pytest.approx(0.10 * (3_000 - 2_000))
    assert s.diaria["acciones"].iloc[-1] == 0
    # La aportación del mes de la venta también va a la reserva.
    assert s.diaria["reserva"].iloc[-1] == pytest.approx(3_000 - 100 + 1_000)
    assert s.valor_final_neto == pytest.approx(3_900)


def test_el_benchmark_nunca_vende_y_siempre_invierte_todo():
    e, sen = _escenario([10, 10, 10, 10, 20, 20, 20, 20], ["NO COMPRAR", "COMPRAR MENOS", "VENDER"])
    s = reglas.simular(e, sen, pd.Series(dtype=float), variante=Variante.BENCHMARK, parametros=SIN_FRICCION)
    assert s.ventas.empty
    assert s.ejecuciones["comprado"].tolist() == pytest.approx([1_000, 1_000, 1_000])
    assert s.valor_final_neto == pytest.approx((100 + 50 + 50) * 20)


def test_solo_tesis_recompra_todo_en_cuanto_deja_de_disparar():
    e, sen = _escenario([10] * 8, ["SIN SEÑAL", "VENDER", "NO COMPRAR"])
    s = reglas.simular(e, sen, pd.Series(dtype=float), variante=Variante.SOLO_TESIS, parametros=SIN_FRICCION)
    assert len(s.ventas) == 1
    assert s.ejecuciones["comprado"].tolist() == pytest.approx([1_000, 0, 3_000])


def test_solo_valuacion_nunca_vende():
    e, sen = _escenario([10] * 6, ["SIN SEÑAL", "VENDER"])
    s = reglas.simular(e, sen, pd.Series(dtype=float), variante=Variante.SOLO_VALUACION, parametros=SIN_FRICCION)
    assert s.ventas.empty
    assert s.ejecuciones["decision"].tolist() == ["SIN SEÑAL", "NO COMPRAR"]


def test_el_dividendo_paga_impuesto_y_espera_la_siguiente_ejecucion():
    e, sen = _escenario([10] * 6, ["SIN SEÑAL", "SIN SEÑAL"], dividendos=[("2020-02-15", 1.0)])
    p = replace_param(impuesto_dividendo=0.20)
    s = reglas.simular(e, sen, pd.Series(dtype=float), variante=Variante.MODELO, parametros=p)
    # 100 acciones × 1 dólar × 80% entran con la aportación del mes siguiente.
    assert s.ejecuciones["dinero_nuevo"].tolist() == pytest.approx([1_000, 1_080])
    assert s.impuestos["dividendos"] == pytest.approx(20)
    # Lo que se paga de impuesto no se queda en la reserva: todo lo neto se invirtió.
    assert s.diaria["reserva"].iloc[-1] == pytest.approx(0)


def test_la_reserva_rinde_el_tbill_despues_de_impuestos():
    e, sen = _escenario([10] * 4, ["NO COMPRAR"])
    tasa = pd.Series(0.0365, index=e.tabla.index)
    p = replace_param(impuesto_intereses=0.20)
    s = reglas.simular(e, sen, tasa, variante=Variante.MODELO, parametros=p)
    dias = (e.tabla.index[-1] - e.tabla.index[2]).days
    assert s.diaria["reserva"].iloc[-1] == pytest.approx(1_000 * (1 + 0.0365 * 0.8 * dias / 365))


def test_la_escision_entra_como_efectivo_y_el_benchmark_la_reinvierte():
    """NLOP y Orion: el accionista recibió acciones de otra empresa, no perdió valor."""
    ev = EventoDeCapital(D(2020, 2, 15), 1.05, "escision", "prueba", "prueba")
    e, sen = _escenario([10, 10, 10, 10, 10, 10], ["SIN SEÑAL", "SIN SEÑAL"], escisiones=[ev])
    s = reglas.simular(e, sen, pd.Series(dtype=float), variante=Variante.BENCHMARK, parametros=SIN_FRICCION)
    assert s.ejecuciones["dinero_nuevo"].tolist() == pytest.approx([1_000, 1_000 + 100 * 10 * 0.05])


def test_la_liquidacion_final_paga_el_impuesto_de_la_ganancia_no_realizada():
    e, sen = _escenario([10, 10, 10, 30], ["SIN SEÑAL"])
    p = replace_param(impuesto_ganancia=0.10)
    s = reglas.simular(e, sen, pd.Series(dtype=float), variante=Variante.BENCHMARK, parametros=p)
    assert s.valor_final == pytest.approx(3_000)
    assert s.valor_final_neto == pytest.approx(3_000 - 0.10 * 2_000)
    # Un solo flujo de ida y uno de vuelta: la TIR es la de la tabla de flujos.
    assert list(s.flujos_usd.values) == pytest.approx([-1_000, 2_800])


def replace_param(**cambios) -> Parametros:
    from dataclasses import replace

    return replace(SIN_FRICCION, **cambios)


def test_el_grado_de_inversion_se_conoce_desde_el_documento():
    cal = pd.DataFrame([
        {"ticker": "ZZ", "fecha": pd.Timestamp("2014-01-15"), "agencia": "S&P", "grado_inversion": "si",
         "fecha_publicacion": pd.Timestamp("2014-01-20")},
        {"ticker": "ZZ", "fecha": pd.Timestamp("2020-05-01"), "agencia": "S&P", "grado_inversion": "no",
         "fecha_publicacion": pd.Timestamp("2020-05-01")},
    ])
    g = reglas.grado_de_inversion(cal, pd.DatetimeIndex(["2013-12-31", "2014-01-17", "2014-01-31", "2020-06-30"]))
    assert pd.isna(g["vigente"].iloc[0]) and pd.isna(g["vigente"].iloc[1])   # el documento es del 20
    assert g["vigente"].iloc[2] is True and g["perdido"].iloc[2] is False
    assert g["vigente"].iloc[3] is False and g["perdido"].iloc[3] is True


def test_no_tener_calificacion_no_es_perderla():
    cal = pd.DataFrame([{"ticker": "ZZ", "fecha": pd.Timestamp("2005-01-01"), "agencia": "—",
                         "grado_inversion": "sin_calificacion", "fecha_publicacion": pd.Timestamp("2005-01-01")}])
    g = reglas.grado_de_inversion(cal, pd.DatetimeIndex(["2006-01-01"]))
    assert g["vigente"].iloc[0] is False and g["perdido"].iloc[0] is False


# --------------------------------------------------------------------------------------
# Señales sobre la historia versionada
# --------------------------------------------------------------------------------------


def _armar(repo, ticker: str, asof: dt.date):
    if not mercado.hay_estudio(ticker):
        pytest.skip(f"No está versionado el estudio de {ticker}.")
    from src.estudio import estudio

    return estudio.armar(repo, ticker, asof=asof)


@pytest.fixture
def estudio_o(repo_sembrado):
    return _armar(repo_sembrado, "O", D(2026, 6, 30))


def test_el_payout_compara_el_dividendo_del_mismo_periodo(estudio_o):
    """O subió el dividendo 15% en 2013 con la compra de ARCT. A fines de 2013 el AFFO
    conocido era el de 2012 (2.06): dividirlo entre el dividendo de HOY daba 106% y
    vendía. El del mismo periodo —los pagos de 2012— da ~86%."""
    sen = reglas.senales(estudio_o, calificaciones=pd.DataFrame())
    fila = sen.mensual.loc[sen.mensual.index[sen.mensual.index <= "2013-12-31"][-1]]
    assert fila["medida_calidad"] == "AFFO"
    assert fila["periodo_flujo"] == pd.Timestamp("2012-12-31")
    assert fila["payout"] == pytest.approx(1.77 / 2.06, abs=0.02)
    assert not (sen.mensual.loc["2013":"2014", "decision"] == "VENDER").any()


def test_la_persistencia_se_cuenta_en_reportes_no_en_trimestres(estudio_o):
    """Antes de 2019 el flujo es anual: un solo año malo aparecía en dos cierres de
    trimestre y la Puerta 3 lo leía como dos trimestres seguidos."""
    por_reporte = reglas.senales(estudio_o, calificaciones=pd.DataFrame())
    por_fecha = reglas.senales(estudio_o, calificaciones=pd.DataFrame(),
                               parametros=Parametros(persistencia_por_reporte=False))
    anuales = por_reporte.trimestral.loc[:"2018"]
    assert anuales.index.year.is_unique, "antes de 2019, un renglón por reporte anual"
    assert len(por_fecha.trimestral.loc[:"2018"]) > 3 * len(anuales)
    assert (por_fecha.mensual["decision"] == "VENDER").sum() >= (por_reporte.mensual["decision"] == "VENDER").sum()


def test_las_senales_no_miran_al_futuro(repo_sembrado):
    """Las decisiones hasta 2015 no cambian si el estudio se arma en 2015 (P1)."""
    tarde = _armar(repo_sembrado, "O", D(2026, 6, 30))
    temprano = _armar(repo_sembrado, "O", D(2015, 6, 30))
    a = reglas.senales(tarde, calificaciones=pd.DataFrame()).mensual.loc[:"2015-05-31"]
    b = reglas.senales(temprano, calificaciones=pd.DataFrame()).mensual.loc[:"2015-05-31"]
    columnas = ["prima", "percentil", "payout", "crecimiento", "decision"]
    pd.testing.assert_frame_equal(a[columnas], b[columnas])


def test_el_backtest_trae_sus_salvaguardas(estudio_o):
    r = reglas.backtest(estudio_o, calificaciones=pd.DataFrame())
    assert set(r.variantes) == set(Variante)
    assert r.dictamen.veredicto.value == "INCONCLUSO", "decenas de apuestas, no cientos (P7)"
    assert r.apuestas.episodios < 100
    assert r.tabla.loc[Variante.BENCHMARK.value, "ventaja_tir_usd"] == 0
    assert list(r.sensibilidad["fraccion_comprar_menos"]) == [0.0, 0.5, 1.0]
    # Las cuatro rutas reciben exactamente el mismo dinero.
    aportado = {v: s.aportado for v, s in r.variantes.items()}
    assert len(set(aportado.values())) == 1
    assert Decision(r.decision_hoy["decision"]) in set(Decision)


def test_sin_friccion_el_benchmark_reproduce_el_retorno_total_del_estudio(estudio_o):
    """Aportar cada mes al mismo papel sin impuestos ni comisiones vale lo que cada aportación
    multiplicada por el índice de retorno total del estudio. La diferencia —menos de 1% en 32
    años— es que el motor reinvierte el dividendo en la compra del mes siguiente y el índice
    el día de la fecha ex."""
    from dataclasses import replace

    sen = reglas.senales(estudio_o, calificaciones=pd.DataFrame())
    p = replace(SIN_FRICCION, aportacion=1_000.0)
    b = reglas.simular(estudio_o, sen, pd.Series(dtype=float), variante=Variante.BENCHMARK, parametros=p)
    rt = estudio_o.tabla["rt_usd"]
    esperado = sum(1_000 * rt.iloc[-1] / rt.loc[f] for f in b.ejecuciones.index)
    assert b.valor_final / esperado - 1 == pytest.approx(0, abs=0.01)


def test_las_vistas_ponen_cada_fraccion_en_porcentaje(estudio_o):
    from comun import familia_de_columna

    from src.estudio import vistas_reglas

    r = reglas.backtest(estudio_o, calificaciones=pd.DataFrame())
    problemas = []
    for nombre, construir in vistas_reglas.VISTAS.items():
        tabla = construir(r)
        if list(tabla.columns) != list(vistas_reglas.COLUMNAS[nombre]):
            problemas.append(f"{nombre}: columnas {list(tabla.columns)}")
        for columna in tabla.columns:
            serie = pd.to_numeric(tabla[columna], errors="coerce").dropna()
            # Un conteo en cero —O nunca vendió— no es una fracción.
            if serie.empty or tabla[columna].dtype == object or pd.api.types.is_integer_dtype(tabla[columna]):
                continue
            if serie.abs().max() < 1 and familia_de_columna(columna, serie) != "porcentaje":
                problemas.append(f"{nombre}.{columna}: fracción en «{familia_de_columna(columna, serie)}»")
    comparativo = vistas_reglas.comparativo([r])
    assert list(comparativo.columns) == list(vistas_reglas.COLUMNAS["comparativo"])
    assert not problemas, "\n".join(problemas)


def test_calificaciones_versionadas():
    """WPC no tenía grado de inversión en 2012 (8-K del 4-ene-2012) y lo obtuvo en enero de
    2014; O desde dic-1996 y NNN desde 1998. Ninguno lo perdió."""
    fechas = pd.DatetimeIndex(["2011-06-30", "2012-06-30", "2014-06-30", "2026-06-30"])
    wpc = reglas.grado_de_inversion(reglas.cargar_calificaciones("WPC"), fechas)
    if wpc["vigente"].isna().all():
        pytest.skip("Sin historia de calificaciones versionada.")
    assert pd.isna(wpc["vigente"].iloc[0]), "antes de 2012 no hay documento: sin dato, no reprobado"
    assert wpc["vigente"].iloc[1] is False and wpc["perdido"].iloc[1] is False
    assert wpc["vigente"].iloc[2] is True and wpc["vigente"].iloc[3] is True
    for t, antes, despues in (("O", "1997-03-25", "1997-03-27"), ("NNN", "1998-05-14", "1998-05-16")):
        g = reglas.grado_de_inversion(reglas.cargar_calificaciones(t), pd.DatetimeIndex([antes, despues, "2026-06-30"]))
        assert pd.isna(g["vigente"].iloc[0]) and g["vigente"].iloc[1] is True and g["vigente"].iloc[2] is True
        assert not g["perdido"].fillna(False).any()


def test_la_tabla_de_decisiones_es_la_del_diseno():
    """La traducción del semáforo a qué hacer con el dinero, tal como se fijó antes del backtest."""
    from src.modelo.senal import Accion

    assert reglas.DE_SEMAFORO == {
        Accion.COMPRAR: Decision.COMPRAR,
        Accion.MANTENER: Decision.COMPRAR_MENOS,
        Accion.NO_COMPRAR_MAS: Decision.NO_COMPRAR,
        Accion.DESCARTADO: Decision.NO_COMPRAR,
        Accion.VENDER: Decision.VENDER,
        Accion.INCONCLUSO: Decision.SIN_SENAL,
    }
    assert reglas.PARAMETROS.fraccion_comprar_menos == 0.5


def test_el_estudio_armado_a_una_fecha_no_ve_cifras_posteriores(repo_sembrado):
    """P1 en el estudio mismo: armado a 2015, no puede tener el cap rate de 2016 ni el AFFO
    de 2017 aunque estén en el archivo de cifras primarias."""
    e = _armar(repo_sembrado, "O", D(2015, 6, 30))
    assert e.primarios["fecha_publicacion"].max() <= pd.Timestamp("2015-06-30")
    assert e.anual.loc[e.anual.index >= 2015, "cap_rate_adquisicion"].isna().all()
    assert e.anual.loc[e.anual.index >= 2015, "affo_por_accion"].isna().all()


def test_fallidos_con_un_criterio_sin_datos():
    """Con un ``None`` entre booleanos la columna es ``object`` y ``~True`` vale −2: el filtro
    de criterios reprobados tronaba en cuanto un criterio no se podía medir."""
    from src.modelo.senal import Luz, ResultadoPuerta

    criterios = pd.DataFrame({"criterio": ["a", "b", "c"], "cumple": [True, None, False]})
    assert criterios["cumple"].dtype == object
    assert ResultadoPuerta("Calidad", False, Luz.ROJO, criterios).fallidos == ["c"]


def test_anual_corta_por_fecha_aunque_le_pasen_todas_las_cifras(repo_sembrado):
    """La defensa también está en ``fundamentales.anual``, no solo en ``armar``."""
    from src.estudio import fundamentales as fund

    if not mercado.hay_estudio("O"):
        pytest.skip("No está versionado el estudio de O.")
    h = mercado.cargar("O", asof=D(2015, 6, 30))
    t = fund.anual(repo_sembrado, "O", asof=D(2015, 6, 30), historia=h,
                   primarios=fund.cargar_primarios("O", h.eventos))
    assert t.loc[t.index >= 2015, "cap_rate_adquisicion"].isna().all()
