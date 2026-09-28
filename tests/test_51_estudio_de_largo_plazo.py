"""Prueba 51 — El estudio de largo plazo: historia de mercado, lo sabido en cada fecha y retornos.

Qué se protege
--------------
* **P2 en la historia larga.** El proveedor entrega el cierre ajustado por un
  split y por una escisión que registra como split. Deshacerlos mal cambia el
  P/FFO histórico 3.2% o a la mitad sin que nada se vea raro.
* **Catálogos que se niegan.** Un evento de capital o una corrección de
  dividendo que ya no coincide con el proveedor detiene la descarga.
* **El TTM por conteo.** El cambio a liquidación T+1 dejó a mayo de 2024 sin
  fecha ex; sumar por calendario fabrica un recorte y un aumento.
* **P1 en las señales.** El flujo conocido a una fecha no usa nada publicado
  después, y una comparativa aprendida años más tarde no deja congelado el dato.
* **La identidad de la descomposición.** ingreso × crecimiento × revaluación ×
  escisión reconstruyen el retorno total, sin residuo.
* **P7.** El análisis de entradas cuenta ventanas que no se enciman y dice
  INCONCLUSO debajo del umbral.
* **Tres defectos que solo se vieron al mirar la página**: un eje logarítmico que
  llegaba a 10^224, etiquetas que se enciman, y tasas dibujadas como dólares.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
for ruta in (str(RAIZ), str(RAIZ / "app")):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from src.config import MIN_APUESTAS_EFECTIVAS  # noqa: E402
from src.estudio import fundamentales as fund  # noqa: E402
from src.estudio import graficas as g  # noqa: E402
from src.estudio import historia as hist  # noqa: E402
from src.estudio import mercado, retornos  # noqa: E402
from src.estudio.mercado import CorreccionDividendo, CrudoProveedor, EventoDeCapital  # noqa: E402

D = dt.date


# --------------------------------------------------------------------------------------
# Utilidades sintéticas
# --------------------------------------------------------------------------------------


def _crudo(eventos=((D(2005, 1, 3), 2.0), (D(2021, 11, 15), 1.032))) -> CrudoProveedor:
    fechas = pd.to_datetime(["2004-12-30", "2005-01-03", "2021-11-12", "2021-11-15"])
    return CrudoProveedor(
        ticker="ZZ",
        precios=pd.DataFrame({"fecha": fechas, "cierre_proveedor": [10.0, 10.0, 50.0, 50.0],
                              "ajustado_proveedor": np.nan}),
        dividendos=pd.DataFrame({"fecha_ex": pd.to_datetime(["2004-11-26", "2021-10-29"]),
                                 "monto_proveedor": [0.1, 0.2]}),
        eventos=list(eventos),
        primera_cotizacion=D(1994, 10, 18),
    )


CATALOGO_ZZ = (
    EventoDeCapital(D(2005, 1, 3), 2.0, "split", "split", "prueba"),
    EventoDeCapital(D(2021, 11, 15), 1.032, "escision", "escisión", "prueba"),
)


def _historia(precios: pd.Series, dividendos: list[tuple], eventos=()) -> mercado.HistoriaMercado:
    p = pd.DataFrame({"cierre_crudo": precios.values, "cierre_base": precios.values}, index=precios.index)
    d = pd.DataFrame(dividendos, columns=["fecha_ex", "monto_pagado", "tipo"])
    d["fecha_ex"] = pd.to_datetime(d["fecha_ex"])
    d["monto_base"] = d["monto_pagado"]
    return mercado.HistoriaMercado("ZZ", p, d[["fecha_ex", "monto_pagado", "monto_base", "tipo"]],
                                   tuple(eventos), {})


# --------------------------------------------------------------------------------------
# P2: desajuste, catálogo de eventos y correcciones
# --------------------------------------------------------------------------------------


def test_desajuste_distingue_split_de_escision(monkeypatch):
    """El split se deshace para el precio crudo; la escisión, en las dos bases."""
    monkeypatch.setitem(mercado.EVENTOS_DE_CAPITAL, "ZZ", CATALOGO_ZZ)
    p, d, eventos = mercado.desajustar(_crudo())
    fila = p.set_index("fecha")
    # Antes del split: el proveedor lo dividió entre 2 × 1.032.
    assert fila.loc["2004-12-30", "cierre_crudo"] == pytest.approx(10.0 * 2 * 1.032)
    # En acciones de hoy el split se CONSERVA; solo se deshace la escisión.
    assert fila.loc["2004-12-30", "cierre_base"] == pytest.approx(10.0 * 1.032)
    # Entre split y escisión solo cuenta la escisión; después, nada.
    assert fila.loc["2021-11-12", "cierre_crudo"] == pytest.approx(50.0 * 1.032)
    assert fila.loc["2021-11-15", "cierre_crudo"] == pytest.approx(50.0)
    assert d.set_index("fecha_ex").loc["2004-11-26", "monto_pagado"] == pytest.approx(0.1 * 2 * 1.032)
    assert [e.tipo for e in eventos] == ["split", "escision"]


def test_evento_no_catalogado_detiene_la_descarga(monkeypatch):
    monkeypatch.setitem(mercado.EVENTOS_DE_CAPITAL, "ZZ", CATALOGO_ZZ)
    crudo = _crudo(eventos=((D(2005, 1, 3), 2.0), (D(2021, 11, 15), 1.032), (D(2025, 6, 2), 1.05)))
    with pytest.raises(mercado.ErrorMercadoLargo, match="no está en el catálogo"):
        mercado.desajustar(crudo)


def test_evento_catalogado_que_el_proveedor_ya_no_reporta_detiene_la_descarga(monkeypatch):
    """Aplicarlo de todos modos duplicaría la corrección si el proveedor la quitó."""
    monkeypatch.setitem(mercado.EVENTOS_DE_CAPITAL, "ZZ", CATALOGO_ZZ)
    with pytest.raises(mercado.ErrorMercadoLargo, match="no reporta"):
        mercado.desajustar(_crudo(eventos=((D(2005, 1, 3), 2.0),)))


def _dividendos_zz():
    return pd.DataFrame({
        "fecha_ex": pd.to_datetime(["1995-11-29", "1995-12-21"]),
        "monto_proveedor": [0.155, 0.54], "monto_pagado": [0.155, 0.54], "monto_base": [0.0775, 0.27],
    })


def test_correccion_parte_el_registro_y_marca_la_especial(monkeypatch):
    correccion = CorreccionDividendo(D(1995, 12, 21), 0.54,
                                     ((0.155, "regular"), (0.155, "regular"), (0.23, "especial")), "10-K")
    monkeypatch.setitem(mercado.CORRECCIONES_DE_DIVIDENDOS, "ZZ", (correccion,))
    d, bitacora = mercado.aplicar_correcciones("ZZ", _dividendos_zz())
    diciembre = d[d["fecha_ex"] == "1995-12-21"]
    assert sorted(diciembre["tipo"]) == ["especial", "regular", "regular"]
    assert diciembre["monto_pagado"].sum() == pytest.approx(0.54)
    # La base «acciones de hoy» conserva el cociente del registro original.
    assert diciembre["monto_base"].sum() == pytest.approx(0.27)
    assert len(bitacora) == 1


def test_correccion_se_niega_si_el_proveedor_cambio_su_dato(monkeypatch):
    correccion = CorreccionDividendo(D(1995, 12, 21), 0.31, ((0.155, "regular"),), "10-K")
    monkeypatch.setitem(mercado.CORRECCIONES_DE_DIVIDENDOS, "ZZ", (correccion,))
    with pytest.raises(mercado.ErrorMercadoLargo, match="ya no dice"):
        mercado.aplicar_correcciones("ZZ", _dividendos_zz())


# --------------------------------------------------------------------------------------
# El dividendo TTM por conteo
# --------------------------------------------------------------------------------------


def _mensuales_con_brinco_t1() -> pd.DataFrame:
    """Ex-dates al último día hábil del mes hasta abril de 2024 y al primero desde junio.

    Es exactamente lo que le pasó a O: mayo de 2024 no tiene fecha ex.
    """
    antes = pd.date_range("2022-01-31", "2024-04-30", freq="BME")
    despues = pd.date_range("2024-06-01", "2025-12-01", freq="BMS")
    fechas = antes.append(despues)
    return pd.DataFrame({"fecha_ex": fechas, "monto_pagado": 0.25, "monto_base": 0.25, "tipo": "regular"})


def test_dividendo_ttm_por_conteo_sobrevive_al_cambio_a_t_mas_1():
    d = _mensuales_con_brinco_t1()
    cierres = pd.DatetimeIndex(["2024-12-31", "2025-06-30"])
    ttm = mercado.dividendo_ttm(d, cierres)
    assert mercado.pagos_por_anio(d) == 12
    assert ttm.tolist() == pytest.approx([3.0, 3.0])
    # La suma por calendario, que es lo que esto reemplaza, sí se rompe:
    por_calendario = d[d["fecha_ex"].dt.year == 2024]["monto_base"].sum()
    assert por_calendario == pytest.approx(0.25 * 11)


def test_la_distribucion_especial_no_entra_al_yield():
    d = _mensuales_con_brinco_t1()
    d = pd.concat([d, pd.DataFrame({"fecha_ex": [pd.Timestamp("2025-03-15")], "monto_pagado": [5.0],
                                    "monto_base": [5.0], "tipo": ["especial"]})], ignore_index=True)
    assert mercado.dividendo_ttm(d, pd.DatetimeIndex(["2025-06-30"])).iloc[0] == pytest.approx(3.0)


# --------------------------------------------------------------------------------------
# La historia versionada de O contra anclas externas
# --------------------------------------------------------------------------------------


@pytest.fixture
def historia_o():
    if not mercado.hay_historia("O"):
        pytest.skip("No está versionada la historia larga de O.")
    return mercado.cargar("O", asof=D(2026, 9, 28))


def test_historia_versionada_de_o_cuadra_con_sus_anclas(historia_o):
    man = historia_o.manifiesto
    v = man["validacion"]
    assert v["traslape_n"] > 2000
    assert v["traslape_error_max"] < 0.001
    assert all(abs(a["error"]) < 0.005 for a in v["anclas"])
    # El primer día: 16.00 dólares y una mensualidad de 0.15, cifras del listado.
    primero = historia_o.precios.iloc[0]
    assert primero["cierre_crudo"] == pytest.approx(16.0, abs=0.01)
    assert historia_o.dividendos.iloc[0]["monto_pagado"] == pytest.approx(0.15, abs=0.001)
    # Ningún recorte en base de acciones de hoy, más allá del redondeo del proveedor.
    r = historia_o.dividendos[historia_o.dividendos["tipo"] == "regular"]
    assert (r["monto_base"].pct_change().dropna() >= -mercado.TOLERANCIA_RECORTE).all()


def test_dividendo_anualizado_coincide_con_el_8k_del_segundo_trimestre_de_2026(historia_o):
    """Ancla externa: el 8-K del 2T-2026 reporta un dividendo anualizado de 3.252."""
    anualizado = mercado.dividendo_anualizado(historia_o.dividendos, pd.DatetimeIndex(["2026-06-30"]))
    assert anualizado.iloc[0] == pytest.approx(3.252, abs=0.001)


# --------------------------------------------------------------------------------------
# P1: lo que se sabía en cada fecha
# --------------------------------------------------------------------------------------


def test_fecha_efectiva_estima_solo_las_comparativas():
    v = pd.DataFrame({
        "fecha_dato": pd.to_datetime(["2020-03-31", "2024-03-31"]),
        "fecha_publicacion": pd.to_datetime(["2024-05-06", "2024-05-06"]),
    })
    efectiva = fund.fecha_efectiva(v)
    assert efectiva.iloc[0] == pd.Timestamp("2020-03-31") + fund.REZAGO_ORIGINAL
    assert efectiva.iloc[1] == pd.Timestamp("2024-05-06")


def test_ttm_por_publicacion_prefiere_la_correccion():
    """Dos versiones con la misma fecha estimada: gana la que llegó después.

    El 4T-2022 de O llegó primero con la cifra ANUAL (4.00) y después corregido
    (1.00). Con el desempate al revés, el TTM de 2023 salía en 7.16.
    """
    # La corrección va PRIMERO en los datos, a propósito: si el desempate no mira
    # la llegada, el orden de entrada deja ganar a la versión mala. Con la
    # corrección al final, la prueba pasaba por accidente aunque el desempate faltara.
    filas = [{"fecha_dato": "2022-12-31", "fecha_publicacion": "2024-02-20", "valor": 1.0,
              "_llegada": "2025-02-24"}]
    for q, valor in (("2022-12-31", 4.00), ("2023-03-31", 1.0), ("2023-06-30", 1.0), ("2023-09-30", 1.0)):
        filas.append({"fecha_dato": q, "fecha_publicacion": "2024-02-20", "valor": valor, "_llegada": "2024-02-20"})
    v = pd.DataFrame(filas)
    for c in ("fecha_dato", "fecha_publicacion", "_llegada"):
        v[c] = pd.to_datetime(v[c])
    ttm = fund._ttm_por_publicacion(v)
    assert ttm.iloc[-1] == pytest.approx(4.0)


def _hecho(concepto, tipo, fecha_dato, publicado, valor):
    return {"ticker": "ZZ", "concepto": concepto, "periodo_tipo": tipo, "fecha_dato": D.fromisoformat(fecha_dato),
            "fecha_publicacion": D.fromisoformat(publicado), "valor": valor, "unidad": "USD/acc",
            "fuente": "SEC-8K-EX99.1", "es_primario": True, "estado": "valido"}


def _primarios(*anios_valor_pub):
    return pd.DataFrame([{"anio": a, "concepto": "ffo_por_accion", "valor": v, "valor_actual": v,
                          "base": "actual", "metodo": "reportado", "fuente": "prueba",
                          "fecha_publicacion": pd.Timestamp(p)} for a, v, p in anios_valor_pub])


def test_flujo_conocido_no_mira_al_futuro(repo_vacio):
    repo_vacio.guardar_hechos([
        _hecho("ffo_por_accion", "Q", "2019-03-31", "2019-05-06", 0.80),
        _hecho("ffo_por_accion", "Q", "2019-06-30", "2019-08-05", 0.81),
        _hecho("ffo_por_accion", "Q", "2019-09-30", "2019-11-04", 0.82),
        _hecho("ffo_por_accion", "Q", "2019-12-31", "2020-02-24", 0.83),
    ])
    primarios = _primarios((2018, 3.12, "2019-02-20"))
    s = fund.flujo_conocido(repo_vacio, "ZZ", "ffo_por_accion", asof=D(2026, 1, 1), primarios=primarios)
    en = fund.en_fechas(s, pd.DatetimeIndex(["2019-12-31", "2020-02-23", "2020-02-24"]))
    # Un día antes del comunicado del 4T se sigue sabiendo el FFO de 2018.
    assert en.iloc[0] == pytest.approx(3.12)
    assert en.iloc[1] == pytest.approx(3.12)
    assert en.iloc[2] == pytest.approx(0.80 + 0.81 + 0.82 + 0.83)


def test_la_precedencia_primaria_es_por_anio(repo_vacio):
    """Capturar a mano el FFO de 2025 no puede borrar los TTM de 2020 a 2024.

    Pasó: con un corte por la última fecha primaria, el FFO se quedó en el de
    2018 durante siete años y el crecimiento de esas eras salió en 0.0%.
    """
    filas = []
    for anio in range(2020, 2025):
        for q, mes in ((1, 5), (2, 8), (3, 11)):
            fin = pd.Timestamp(anio, 3 * q, 1) + pd.offsets.MonthEnd(0)
            filas.append(_hecho("ffo_por_accion", "Q", str(fin.date()), f"{anio}-{mes:02d}-06", 1.0 + anio - 2020))
        filas.append(_hecho("ffo_por_accion", "Q", f"{anio}-12-31", f"{anio + 1}-02-20", 1.0 + anio - 2020))
    repo_vacio.guardar_hechos(filas)
    primarios = _primarios((2018, 3.12, "2019-02-20"), (2025, 9.99, "2026-02-24"))
    s = fund.flujo_conocido(repo_vacio, "ZZ", "ffo_por_accion", asof=D(2026, 6, 1), primarios=primarios)
    en_2023 = fund.en_fechas(s, pd.DatetimeIndex(["2023-12-01"])).iloc[0]
    assert en_2023 != pytest.approx(3.12), "el TTM de 2023 quedó tapado por el primario de 2018"
    assert en_2023 == pytest.approx(4.0 * 3 + 3.0)


def test_factor_de_base_solo_cuenta_splits():
    assert fund.factor_de_base(2003, CATALOGO_ZZ) == 2.0
    assert fund.factor_de_base(2010, CATALOGO_ZZ) == 1.0


# --------------------------------------------------------------------------------------
# Retorno total y descomposición
# --------------------------------------------------------------------------------------


def test_retorno_total_no_cambia_por_split_ni_escision():
    fechas = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"])
    # Split 2:1 el día 3 (el precio cae a la mitad) y escisión el día 6 (cae 3.1%).
    precios = pd.Series([10.0, 5.0, 5.0 / 1.032, 5.0 / 1.032], index=fechas)
    eventos = (EventoDeCapital(D(2020, 1, 3), 2.0, "split", "", ""),
               EventoDeCapital(D(2020, 1, 6), 1.032, "escision", "", ""))
    h = _historia(precios, [("2020-01-07", 0.5 / 1.032, "regular")], eventos)
    rt = retornos.indice_retorno_total(h)
    assert rt.iloc[1] == pytest.approx(1.0)
    assert rt.iloc[2] == pytest.approx(1.0)
    # El dividendo reinvertido sí suma: 0.5/1.032 sobre un precio de 5/1.032 = 10%.
    assert rt.iloc[3] == pytest.approx(1.10)


def _serie_sintetica(anios: int = 30):
    fechas = pd.bdate_range("1995-01-02", periods=anios * 252)
    t = np.arange(len(fechas)) / 252
    precio = pd.Series(20 * np.exp(0.05 * t + 0.15 * np.sin(t)), index=fechas)
    meses = pd.date_range(fechas[0], fechas[-1], freq="BME")
    divs = [(f, 0.1 * np.exp(0.04 * (f - fechas[0]).days / 365.25), "regular") for f in meses]
    h = _historia(precio, divs)
    ffo = pd.Series(1.5 * np.exp(0.04 * np.arange(anios)), index=pd.to_datetime([f"{1995 + i}-03-01" for i in range(anios)]))
    ust = pd.Series(0.04, index=fechas)
    fx = pd.Series(10.0, index=fechas)
    return h, retornos.serie_diaria(h, ust10=ust, usdmxn=fx, ffo_conocido=ffo, affo_conocido=ffo)


def test_descomposicion_reconstruye_el_retorno_sin_residuo():
    """La identidad sola es tautológica —el ingreso es el residuo—, así que además
    se exige que el ingreso se parezca a lo que de verdad se cobró: el yield
    promedio del periodo. Una descomposición mal planteada lo desplaza."""
    h, s = _serie_sintetica()
    for inicio, fin in (("1996-06-01", "2004-06-01"), ("2004-06-01", "2020-01-01"), ("1995-03-01", "2024-06-01")):
        d = retornos.descomponer(s, h, inicio, fin)
        assert abs(d.identidad) < 1e-12
        yield_medio = s.tabla.loc[inicio:fin, "yield_ttm"].mean()
        assert abs(d.ingreso - yield_medio) < 0.015, (d.ingreso, yield_medio)


def test_entradas_cuentan_apuestas_efectivas_y_dicen_inconcluso():
    _, s = _serie_sintetica()
    e = retornos.analizar_entradas(s, asof=D(2025, 1, 1))
    con_5 = e.tabla["rt_5a"].dropna()
    esperado = int(((con_5.index[-1] - con_5.index[0]).days / 365.25 + 5) // 5)
    assert e.apuestas_efectivas["5 años"] == esperado
    assert esperado < MIN_APUESTAS_EFECTIVAS
    assert e.veredicto_p7.startswith("INCONCLUSO")
    # Los extremos no repiten episodio: separados más de 18 meses entre sí.
    fechas = sorted(e.mejores.index)
    assert all((b - a).days > 18 * 30 for a, b in zip(fechas, fechas[1:], strict=False))


# --------------------------------------------------------------------------------------
# Gráficas: marca y los dos defectos que se vieron en pantalla
# --------------------------------------------------------------------------------------


def test_tokens_de_graficas_coinciden_con_la_marca():
    import marca

    assert g.OSCURO.principal == marca.AMBAR
    assert g.OSCURO.contexto == marca.GRIS
    assert g.OSCURO.contexto_2 == marca.GRIS_TENUE
    assert g.OSCURO.texto == marca.BLANCO
    assert g.OSCURO.rejilla == marca.LINEA
    assert g.OSCURO.ganancia == marca.PROFIT and g.OSCURO.perdida == marca.LOSS
    assert g.CLARO.fondo == marca.PAPEL and g.CLARO.texto == marca.PAPEL_TINTA


def test_etiquetas_en_eje_logaritmico_van_en_log10():
    """Con el valor lineal, una etiqueta en 46 se dibujaba en 10^46 y el eje llegaba a 10^224."""
    import plotly.graph_objects as go

    fig = go.Figure(go.Scatter(x=[1, 2], y=[1, 46]))
    g._etiquetas_finales(fig, g.OSCURO, [(2, 46.0, "x46", "#fff")], log=True)
    assert fig.layout.annotations[0].y == pytest.approx(np.log10(46))


def test_dos_etiquetas_casi_iguales_se_separan():
    """Pesos y Dólares terminaban a medio punto: la separación medía contra su propio rango."""
    import plotly.graph_objects as go

    fig = go.Figure([go.Scatter(x=[1, 2], y=[-0.05, 0.052]), go.Scatter(x=[1, 2], y=[0.15, 0.055])])
    g._etiquetas_finales(fig, g.OSCURO, [(2, 0.052, "A", "#fff"), (2, 0.055, "B", "#fff")])
    corrimientos = sorted(a.yshift for a in fig.layout.annotations)
    assert corrimientos[0] < 0 < corrimientos[1]


# (La prueba de las unidades de las tablas vive más abajo, sobre el estudio armado:
# necesita las vistas con datos reales para saber qué columnas traen fracciones.)


# --------------------------------------------------------------------------------------
# La narrativa
# --------------------------------------------------------------------------------------


def test_cada_hito_tiene_fuente_y_las_eras_son_contiguas():
    for h in [*hist.HISTORIA_O.hitos, *hist.INDUSTRIA]:
        assert h.fuente.strip(), f"«{h.titulo}» no dice de dónde salió"
        assert h.precision in ("dia", "mes", "anio")
    eras = hist.HISTORIA_O.eras
    for a, b in zip(eras, eras[1:], strict=False):
        assert a.fin == b.inicio, f"hueco o encime entre «{a.nombre}» y «{b.nombre}»"
    assert eras[-1].fin is None


# --------------------------------------------------------------------------------------
# De punta a punta sobre la base de demostración (corre en CI)
# --------------------------------------------------------------------------------------


@pytest.fixture
def estudio_demo(repo_sembrado):
    if not mercado.hay_historia("O"):
        pytest.skip("No está versionada la historia larga de O.")
    from src.estudio import estudio

    return estudio.armar(repo_sembrado, "O", asof=D(2026, 6, 30))


def test_estudio_de_punta_a_punta(estudio_demo):
    e = estudio_demo
    assert e.eras and all(abs(d.identidad) < 1e-9 for d in e.eras)
    assert abs(e.total.identidad) < 1e-9
    assert e.conclusiones
    assert e.entradas.veredicto_p7.startswith("INCONCLUSO")
    for tema in (g.OSCURO, g.CLARO):
        for figura in g.FIGURAS.values():
            figura(e, tema)  # no truena en ningún tema


def test_el_html_del_pdf_no_filtra_huecos(estudio_demo):
    """Un «nan%» en el impreso es un número que no se calculó y se imprimió igual."""
    from src.export.pdf_estudio import html_del_estudio

    documento = html_del_estudio(estudio_demo, fuentes_css="")
    for seccion in ("Lo que dice el estudio", "La historia", "El negocio en el tiempo",
                    "De dónde salió el retorno", "Cuándo hubiera convenido entrar",
                    "Paga buen retorno hoy", "Metodología"):
        assert seccion in documento
    cuerpo = documento.split("<body>", 1)[1].split("<script>", 1)[0]
    for hueco in ("nan%", "nanx", "$nan", ">nan<", "None"):
        assert hueco not in cuerpo, f"el PDF imprime «{hueco}»"
    assert documento.count("class='grafica'") == 12


def test_ninguna_tabla_pierde_columnas_ni_dibuja_fracciones_como_otra_unidad(estudio_demo):
    """Las dos formas en que un nombre de columna rompe una tabla sin error.

    1. Fracción en la unidad equivocada: un costo de capital de 0.074 en la
       familia «moneda» se dibuja «$0.07»; en «número», «0.07». Solo en
       «porcentaje» se escala a 7.4%.
    2. Columna desaparecida: renombrar en un lado y no en la lista de columnas a
       mostrar hacía que la columna se filtrara en silencio.
    """
    from comun import familia_de_columna

    from src.estudio import vistas

    problemas = []
    for nombre, construir in vistas.VISTAS.items():
        tabla = construir(estudio_demo)
        clave = "momentos" if nombre in ("mejores", "peores") else nombre
        if clave in vistas.COLUMNAS and list(tabla.columns) != list(vistas.COLUMNAS[clave]):
            problemas.append(f"{nombre}: columnas {list(tabla.columns)}")
        for columna in tabla.columns:
            serie = pd.to_numeric(tabla[columna], errors="coerce").dropna()
            if serie.empty or tabla[columna].dtype == object:
                continue
            if serie.abs().max() < 1 and familia_de_columna(columna, serie) != "porcentaje":
                problemas.append(f"{nombre}.{columna}: fracción en «{familia_de_columna(columna, serie)}»")
    assert not problemas, "\n".join(problemas)
    pagina = (RAIZ / "app" / "pages" / "7_Estudio.py").read_text(encoding="utf-8")
    for nombre in ("spread_inversion", "anual", "eras", "quintiles", "momentos", "yield_sobre_costo",
                   "escenarios", "diagnostico_ffo"):
        assert f"vistas.{nombre}(" in pagina, f"la página ya no usa la vista «{nombre}»"


def test_el_manifiesto_versionado_es_json_valido():
    ruta = mercado.dir_de("O") / mercado.ARCHIVO_MANIFIESTO
    if not ruta.exists():
        pytest.skip("No está versionada la historia larga de O.")
    man = json.loads(ruta.read_text(encoding="utf-8"))
    assert {e["tipo"] for e in man["eventos"]} == {"split", "escision"}
    assert len(man["correcciones_de_dividendos"]) == len(mercado.CORRECCIONES_DE_DIVIDENDOS["O"])
