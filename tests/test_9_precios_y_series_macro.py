"""Prueba 9 — La serie de precios es cruda y las series macro son el instrumento correcto.

Dos errores distintos, ambos silenciosos, ambos cubiertos aquí:

**El precio ajustado disfrazado de crudo (P2).** Es el error original del proyecto:
Macrotrends daba 64.03 para el cierre de 2021 de Realty Income cuando el cierre real
fue 71.56. Hasta ahora solo se podía atrapar con anclas capturadas a mano, y solo
existen para un emisor. La prueba de coherencia del ajuste lo detecta en cualquiera,
usando la aritmética de la propia respuesta del proveedor.

**El identificador equivocado en Banxico (P10).** Un identificador del SIE que apunta
a otro instrumento no falla: entrega una serie válida de otra cosa. Tres de los
identificadores de este proyecto estaban mal y el peor traía la TIIE a 91 días bajo
el nombre de Udibono. 6.8% es creíble para las dos, así que ningún dato lo delata:
hay que preguntarle al catálogo qué es cada serie.

Ninguna prueba de este archivo toca la red.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

from src.config import Estado, Fuente
from src.ingesta import precios as mp
from src.ingesta import tasas as mt

FIXTURES = Path(__file__).parent / "fixtures"


# --------------------------------------------------------------------------------------
# Utilidades: una serie sintética con aritmética verificable a mano
# --------------------------------------------------------------------------------------


def _serie_sintetica(
    *,
    n_dias: int = 400,
    precio0: float = 100.0,
    dividendo: float = 1.0,
    cada: int = 90,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Construye una serie CRUDA con su ajustada exacta y sus dividendos.

    El precio crudo se deja plano a propósito: así el cociente ajustado/crudo es
    exactamente el producto de los factores y cualquiera puede verificar el número
    con una calculadora, sin depender de datos de mercado.
    """
    inicio = dt.date(2022, 1, 3)
    fechas = [inicio + dt.timedelta(days=i) for i in range(n_dias)]
    ex = [f for i, f in enumerate(fechas) if i > 0 and i % cada == 0]

    # El ajuste va hacia atrás: el factor de una fecha es el producto de
    # (1 - div/precio) sobre los dividendos POSTERIORES a ella.
    ajustados = []
    for f in fechas:
        factor = 1.0
        for e in ex:
            if e > f:
                factor *= 1.0 - dividendo / precio0
        ajustados.append(precio0 * factor)

    precios = pd.DataFrame(
        {
            "ticker": "TEST",
            "fecha_dato": fechas,
            "fecha_publicacion": fechas,
            "cierre_crudo": precio0,
            "cierre_ajustado": ajustados,
            "volumen": 1_000.0,
            "fuente": Fuente.MERCADO,
            "metodo": "observado",
        }
    )
    dividendos = pd.DataFrame(
        {
            "ticker": "TEST",
            "fecha_ex": ex,
            "fecha_declaracion": [None] * len(ex),
            "fecha_registro": ex,
            "fecha_pago": [e + dt.timedelta(days=14) for e in ex],
            "monto": dividendo,
            "fuente": Fuente.MERCADO,
            "fecha_publicacion": ex,
        }
    )
    return precios, dividendos


# --------------------------------------------------------------------------------------
# 9.1 La identidad del ajuste confirma que la columna cruda es cruda
# --------------------------------------------------------------------------------------


def test_serie_cruda_legitima_queda_confirmada():
    precios, dividendos = _serie_sintetica()
    r = mp.prueba_coherencia_ajuste(precios, dividendos)
    assert r.verificable
    assert r.coherente
    assert not r.distribucion_no_listada
    assert r.error_max < 1e-9, "La identidad es exacta por construcción."


def test_el_cociente_teorico_es_el_producto_que_uno_calcula_a_mano():
    """Con cuatro dividendos de 1.00 sobre precio 100, la primera fecha evaluable ve tres.

    La ventana empieza en el primer dividendo conocido —antes de él faltarían
    factores— y el producto corre sobre los ESTRICTAMENTE posteriores. Así que la
    primera fecha ve tres: 0.99³ = 0.970299.
    """
    precios, dividendos = _serie_sintetica(n_dias=400, precio0=100.0, dividendo=1.0, cada=90)
    r = mp.prueba_coherencia_ajuste(precios, dividendos)
    primera = r.detalle.iloc[0]
    assert primera["n_dividendos"] == 3
    assert primera["cociente_teorico"] == pytest.approx(0.970299, abs=1e-9)
    assert primera["cociente_observado"] == pytest.approx(0.970299, abs=1e-9)


# --------------------------------------------------------------------------------------
# 9.2 CONTROL: la serie ajustada entregada como cruda TIENE que ser rechazada
# --------------------------------------------------------------------------------------


def test_control_la_serie_ajustada_como_cruda_se_detecta():
    """Es el error de Macrotrends. Sin este control, la prueba 9.1 no prueba nada."""
    precios, dividendos = _serie_sintetica()
    falsa = precios.copy()
    falsa["cierre_crudo"] = falsa["cierre_ajustado"]  # el proveedor nos da la ajustada

    r = mp.prueba_coherencia_ajuste(falsa, dividendos)
    assert r.verificable, "Hay datos suficientes: el veredicto debe ser un juicio, no un 'no sé'."
    assert not r.coherente
    assert not r.distribucion_no_listada
    assert "no se comporta como cruda" in r.motivo
    # El cociente delator: si crudo == ajustado, vale 1.00 en todas partes.
    assert r.detalle["cociente_observado"].max() == pytest.approx(1.0)


def test_control_el_sesgo_crece_hacia_atras_en_el_tiempo():
    """La firma de una serie ajustada no es un error constante: crece hacia el pasado."""
    precios, dividendos = _serie_sintetica()
    falsa = precios.copy()
    falsa["cierre_crudo"] = falsa["cierre_ajustado"]

    r = mp.prueba_coherencia_ajuste(falsa, dividendos)
    desviaciones = r.detalle.sort_values("fecha_dato")["desviacion_relativa"]
    assert desviaciones.iloc[0] > desviaciones.iloc[-1], (
        "El error de una serie ajustada es máximo en el pasado remoto y se desvanece "
        "hacia el presente. Si fuera parejo, sería otra cosa."
    )


# --------------------------------------------------------------------------------------
# 9.3 Distinguir "no pude verificarlo" de "está mal"
# --------------------------------------------------------------------------------------


def test_una_escision_no_acusa_a_la_columna_cruda():
    """Más ajuste del que explican los dividendos = reparto no listado, no serie sucia.

    Es el caso real de Realty Income (escisión de Orion, 2021) y W. P. Carey (NLOP,
    2023). Confundirlo con una serie ajustada tiraría datos buenos.
    """
    precios, dividendos = _serie_sintetica()
    # Se borra un dividendo INTERMEDIO del historial: la serie ajustada sigue
    # descontándolo, así que las fechas previas a él quedan con menos factores de
    # los que el precio ajustado refleja. Tiene que ser intermedio: uno anterior a
    # la ventana evaluable nunca entra al producto y no probaría nada.
    incompletos = dividendos.drop(index=2).reset_index(drop=True)

    r = mp.prueba_coherencia_ajuste(precios, incompletos)
    assert r.verificable
    assert r.coherente, "El cierre crudo sigue siendo utilizable para yields."
    assert r.distribucion_no_listada
    assert "escisión" in r.motivo or "extraordinario" in r.motivo


def test_sin_columna_ajustada_el_veredicto_es_no_verificable():
    precios, dividendos = _serie_sintetica()
    sin = precios.copy()
    sin["cierre_ajustado"] = pd.NA
    r = mp.prueba_coherencia_ajuste(sin, dividendos)
    assert not r.verificable
    assert not r.coherente, "No verificable jamás debe leerse como aprobado."


def test_sin_dividendos_el_veredicto_es_no_verificable():
    precios, _ = _serie_sintetica()
    r = mp.prueba_coherencia_ajuste(precios, pd.DataFrame())
    assert not r.verificable
    assert "dividendos" in r.motivo


# --------------------------------------------------------------------------------------
# 9.4 REGRESIÓN: un dividendo con fecha ex futura desplazaba TODAS las fechas
# --------------------------------------------------------------------------------------


def test_regresion_dividendo_futuro_no_desplaza_la_identidad():
    """Un dividendo ya declarado pero aún no ex no está en la serie ajustada.

    Contarlo movía el factor teórico de todas las fechas por la misma proporción y
    hacía ver como sospechosos a emisores sanos. La firma era delatora: desviación
    idéntica en cada fecha, que no es como se ve ningún sesgo de ajuste real.
    """
    precios, dividendos = _serie_sintetica()
    ultima_sesion = max(precios["fecha_dato"])
    futuro = pd.DataFrame(
        [
            {
                "ticker": "TEST",
                "fecha_ex": ultima_sesion + dt.timedelta(days=20),
                "fecha_declaracion": None,
                "fecha_registro": None,
                "fecha_pago": None,
                "monto": 1.0,
                "fuente": Fuente.MERCADO,
                "fecha_publicacion": ultima_sesion,
            }
        ]
    )
    con_futuro = pd.concat([dividendos, futuro], ignore_index=True)

    r = mp.prueba_coherencia_ajuste(precios, con_futuro)
    assert r.coherente, "El dividendo futuro debe quedar fuera del producto."
    assert r.error_max < 1e-9


# --------------------------------------------------------------------------------------
# 9.5 El parser de la respuesta real del proveedor
# --------------------------------------------------------------------------------------


@pytest.fixture
def respuesta_precios() -> dict:
    return json.loads((FIXTURES / "precios_eprt.json").read_text())


@pytest.fixture
def respuesta_dividendos() -> dict:
    return json.loads((FIXTURES / "dividendos_eprt.json").read_text())


def test_descarga_precios_sobre_respuesta_real(monkeypatch, respuesta_precios):
    monkeypatch.setattr(mp, "_pedir_json", lambda *a, **k: respuesta_precios)
    df = mp.descargar_historico("EPRT")

    assert len(df) > 1_000
    assert list(df["fecha_dato"]) == sorted(df["fecha_dato"]), "Debe venir en orden ascendente."
    assert (df["cierre_crudo"] > 0).all()
    assert df["cierre_ajustado"].notna().any(), "Sin ajustado no hay verificación posible."
    assert (df["fecha_publicacion"] == df["fecha_dato"]).all(), (
        "El cierre se publica el mismo día; inventar rezago falsearía el point-in-time."
    )
    assert set(df["fuente"]) == {Fuente.MERCADO}


def test_descarga_dividendos_sobre_respuesta_real(monkeypatch, respuesta_dividendos):
    monkeypatch.setattr(mp, "_pedir_json", lambda *a, **k: respuesta_dividendos)
    df = mp.descargar_dividendos("EPRT")

    assert len(df) >= 15
    assert (df["monto"] > 0).all(), "El símbolo de moneda debe quedar fuera del número."
    assert df["fecha_ex"].notna().all()
    # El proveedor manda 'n/a' en la fecha de declaración de este emisor.
    assert df["fecha_declaracion"].isna().all()
    assert (df["fecha_publicacion"] == df["fecha_ex"]).all(), (
        "Sin fecha de declaración, la ex es la cota superior defendible."
    )


def test_la_respuesta_real_pasa_la_prueba_de_coherencia(
    monkeypatch, respuesta_precios, respuesta_dividendos
):
    """La verificación corre sobre datos que el proveedor efectivamente entregó."""
    monkeypatch.setattr(mp, "_pedir_json", lambda *a, **k: respuesta_precios)
    px = mp.descargar_historico("EPRT")
    monkeypatch.setattr(mp, "_pedir_json", lambda *a, **k: respuesta_dividendos)
    dv = mp.descargar_dividendos("EPRT")

    r = mp.prueba_coherencia_ajuste(px, dv)
    assert r.verificable and r.coherente
    assert r.error_max < 0.01
    assert r.n_fechas >= 3


def test_un_muro_de_verificacion_no_se_confunde_con_datos(monkeypatch):
    """Stooq murió así: HTTP 200 con HTML. Un parser ingenuo lo toma por datos."""

    class RespuestaHtml:
        status_code = 200
        text = "<!DOCTYPE html><html><body>This site requires JavaScript</body></html>"

        def json(self):  # pragma: no cover - no debe llegar aquí
            raise AssertionError("No se debe intentar interpretar HTML como JSON.")

    monkeypatch.setattr(mp.requests, "get", lambda *a, **k: RespuestaHtml())
    with pytest.raises(mp.ErrorPrecios, match="HTML"):
        mp.descargar_historico("EPRT")


# --------------------------------------------------------------------------------------
# 9.6 Banxico: el identificador tiene que ser del instrumento que decimos
# --------------------------------------------------------------------------------------


def test_los_identificadores_declarados_pasan_su_propia_verificacion(monkeypatch):
    """Con los títulos reales del catálogo, los cinco identificadores aprueban."""
    reales = {
        "SP1": "IPC Por objeto del gasto Nacional I n d i c e G e n e r a l",
        "SF43936": (
            "Valores gubernamentales Resultados de la subasta semanal "
            "Tasa de rendimiento Cetes a 28 días"
        ),
        "SF44071": (
            "Valores Gubernamentales Resultados de la subasta semanal "
            "Tasa de rendimiento Bono tasa fija 10 años"
        ),
        "SF43924": (
            "Valores gubernamentales Resultados de la subasta semanal "
            "Tasa de rendimiento Udibonos a 10 años (real)"
        ),
        "SF60639": (
            "Valores gubernamentales, Resultados de la subasta semanal "
            "Udibonos a 30 años - Tasa de rendimiento real -"
        ),
    }
    monkeypatch.setattr(mt, "titulos_banxico", lambda ids, token=None, **k: reales)
    veredicto = mt.verificar_series_banxico(token="prueba")
    malos = {n for n, (ok, _) in veredicto.items() if not ok}
    assert not malos, f"Identificadores que no corresponden a su instrumento: {malos}"


def test_control_la_tiie_no_pasa_por_udibono(monkeypatch):
    """El error real que se encontró: SF43878 es TIIE a 91 días, no el Udibono.

    Es el control que le da valor a la prueba anterior. Sin él, `verificar_series_
    banxico` podría estar devolviendo OK a todo.
    """
    suplantado = {
        cfg[0]: "Tasas de interés interbancarias Por ciento anual TIIE a 91 días"
        for cfg in mt.SERIES_BANXICO.values()
    }
    monkeypatch.setattr(mt, "titulos_banxico", lambda ids, token=None, **k: suplantado)
    veredicto = mt.verificar_series_banxico(token="prueba")

    ok_udibono, titulo = veredicto[mt.SERIE_UDIBONO10]
    assert not ok_udibono, "Una TIIE bajo el nombre de Udibono debe reprobar."
    assert "TIIE" in titulo, "El veredicto debe decir qué es realmente la serie."


def test_un_identificador_inexistente_reprueba(monkeypatch):
    monkeypatch.setattr(mt, "titulos_banxico", lambda ids, token=None, **k: {})
    veredicto = mt.verificar_series_banxico(token="prueba")
    assert all(not ok for ok, _ in veredicto.values())


# --------------------------------------------------------------------------------------
# 9.7 Nada que no se haya verificado entra a los cálculos
# --------------------------------------------------------------------------------------


def test_una_serie_rechazada_se_guarda_marcada_y_sin_dividendos(repo_vacio, monkeypatch):
    """Prefiere no tener el dato a tenerlo mal — pero conserva la evidencia."""
    from src.ingesta import orquestador

    precios, dividendos = _serie_sintetica()
    sucia = precios.copy()
    sucia["cierre_crudo"] = sucia["cierre_ajustado"]  # ajustada disfrazada de cruda

    monkeypatch.setattr(orquestador.precios, "descargar_historico", lambda t, **k: sucia)
    monkeypatch.setattr(orquestador.precios, "descargar_dividendos", lambda t, **k: dividendos)

    resumen = orquestador.ingestar_precios(repo_vacio, "TEST")

    assert resumen.precios_guardados > 0, "El registro rechazado es evidencia, no basura."
    assert resumen.dividendos_guardados == 0, (
        "Sin precio confiable no hay yield, así que el dividendo no aporta y no entra."
    )
    assert resumen.errores

    # Por omisión la consulta solo devuelve válidos: lo rechazado existe en la base
    # pero es invisible para cualquier cálculo. Hay que pedirlo explícitamente.
    assert repo_vacio.precios("TEST", asof=dt.date(2023, 12, 31)).empty
    guardados = repo_vacio.precios("TEST", asof=dt.date(2023, 12, 31), solo_validos=False)
    assert not guardados.empty
    assert set(guardados["estado"]) == {Estado.RECHAZADO}


def test_una_serie_limpia_entra_completa(repo_vacio, monkeypatch):
    from src.ingesta import orquestador

    precios, dividendos = _serie_sintetica()
    monkeypatch.setattr(orquestador.precios, "descargar_historico", lambda t, **k: precios)
    monkeypatch.setattr(orquestador.precios, "descargar_dividendos", lambda t, **k: dividendos)

    resumen = orquestador.ingestar_precios(repo_vacio, "TEST")

    assert resumen.precios_guardados == len(precios)
    assert resumen.dividendos_guardados == len(dividendos)
    assert not resumen.errores

    guardados = repo_vacio.precios("TEST", asof=dt.date(2023, 12, 31))
    assert set(guardados["estado"]) == {Estado.VALIDO}
