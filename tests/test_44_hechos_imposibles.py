"""Prueba 44 — Hechos que no pueden ser lo que dicen ser.

Las gráficas destaparon lo que la tabla escondía. En una tabla de setenta
columnas nadie escanea buscando un valor imposible; en una serie dibujada, un
apalancamiento de 766x salta a la cara. De ahí salieron cuatro defectos, y
ninguno lo cazaba una prueba existente porque los tres detectores que había
—cuadre, escala, conciliación— buscan otra cosa.

**Un saldo que se hunde un corte y regresa.** La deuda total de Prologis al
cierre de 2021 vale 17,715 millones en cinco filings consecutivos y 215 en el
sexto, publicado dos años después. El modelo toma la versión más reciente —que
es lo correcto para una reexpresión— y esa cifra desplaza a cinco observaciones
que concuerdan. No es una reexpresión: es un instrumento suelto que cayó en la
misma cadena de etiquetas.

`escala.py` no lo caza y no debe: busca potencias limpias de mil, porque el error
que persigue es un cambio de unidad. Aquí los factores son 82x, 22x y 6x.

**Un gasto negativo.** El gasto por intereses de Agree Realty aparece en
−1,071,858 en tres trimestres de 2011 y positivo desde 2012: los filings de 2012
lo etiquetaron con el signo de una deducción. Un gasto negativo no es un gasto
chico, y producía un costo implícito de la deuda de −46.6%.

**Un EBITDAre imposible, con la fórmula bien.** En Public Storage, tercer
trimestre de 2022, la utilidad neta salta a 2,712 millones por la venta de PS
Business Parks pero `ganancia_venta_inmuebles` solo alcanza 1.5 de esos
millones. El EBITDAre sale en 2,965 contra 1,088 de ingresos: 2.7 veces el
ingreso, en una medida que EXCLUYE la ganancia por definición.

**Y dos implementaciones que se habían separado.** El EBITDAre se calcula en dos
lugares —`_derivar_ebitdare` para el modelo, la declaración `@ebitdare` para la
tabla, las gráficas y el libro de Excel— y la guarda entró primero en una sola.
Es exactamente el defecto que las declaraciones existen para evitar, y por eso
aquí se prueba la coincidencia sobre las diez emisoras y no sobre un ejemplo.

Lo que se ganó y lo que costó
-----------------------------
Paneles ilegibles 17 → 11 de 150; ratios imposibles 23 → 15; 10 hechos marcados
y 14 celdas de dato menos. Lo que se pierde es a propósito: `Repositorio.hechos`
filtra por estado antes de elegir la versión vigente, así que la celda cae a la
observación anterior cuando existe y queda vacía cuando no.
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
from src.servicio import (  # noqa: E402
    INSUMO_POR_CLAVE,
    TECHO_EBITDARE_SOBRE_INGRESO,
    _derivar_ebitdare,
    panel_de_conceptos,
    serie_de_insumo,
)
from src.validacion.imposibles import (  # noqa: E402
    FACTOR_HUNDIMIENTO,
    SALDOS_ESTRUCTURALES,
    detectar_imposibles,
)

HOY = dt.date.today()


@pytest.fixture(scope="module")
def repo():
    r = Repositorio()
    if r.hechos(asof=HOY, tickers="O", conceptos=["ingresos_totales"]).empty:
        pytest.skip("No hay base cargada.")
    return r


def _hechos(filas: list[dict]) -> pd.DataFrame:
    base = {
        "id": 0, "ticker": "XX", "concepto": "deuda_total", "periodo_tipo": "PUNTUAL",
        "fecha_publicacion": dt.date(2026, 1, 1), "unidad": "USD", "accession": "a",
    }
    return pd.DataFrame([{**base, **f, "id": i} for i, f in enumerate(filas)])


def _serie(valores: list[float], concepto: str = "deuda_total") -> pd.DataFrame:
    return _hechos([
        {"concepto": concepto, "fecha_dato": dt.date(2018 + i // 4, 3 * (i % 4) + 3, 28),
         "valor": v}
        for i, v in enumerate(valores)
    ])


# --------------------------------------------------------------------------------------
# 44.1 · El hundimiento aislado de un saldo
# --------------------------------------------------------------------------------------


def test_un_saldo_que_se_hunde_un_corte_y_regresa_se_marca():
    """La forma que ningún balance puede tener."""
    hallazgos = detectar_imposibles(_serie([100.0, 102.0, 1.5, 104.0, 103.0]))
    assert len(hallazgos) == 1
    assert hallazgos[0].valor == pytest.approx(1.5)
    assert hallazgos[0].motivo == "saldo"


def test_un_cambio_real_de_nivel_no_se_marca():
    """Un desapalancamiento mueve el saldo y lo DEJA movido.

    Es la condición que hace verificable la regla: se exige que los vecinos
    concuerden ENTRE SÍ. Aquí no concuerdan —los de antes valen 100, los de
    después 40— así que el que se movió es la serie, no el corte.
    """
    assert detectar_imposibles(_serie([100.0, 102.0, 40.0, 41.0, 40.5])) == []


def test_el_efectivo_no_esta_sujeto_a_la_regla():
    """El efectivo se mueve tres veces entre trimestres sin que nada esté mal.

    La suavidad es una propiedad de un TOTAL del balance, no de cualquier saldo.
    Exigírsela al efectivo, a los residuales o a la escalera de vencimientos
    marcaría datos buenos: lo que este trimestre vence en el año 3, el siguiente
    vence en el año 2.
    """
    assert "efectivo" not in SALDOS_ESTRUCTURALES
    assert detectar_imposibles(_serie([100.0, 102.0, 1.5, 104.0, 103.0], "efectivo")) == []


def test_un_movimiento_menor_al_factor_no_alcanza():
    """El listón está donde ningún trimestre de financiamiento llega."""
    apenas = 100.0 / (FACTOR_HUNDIMIENTO * 0.95)
    assert detectar_imposibles(_serie([100.0, 100.0, apenas, 100.0, 100.0])) == []


def test_solo_se_juzgan_los_saldos_puntuales():
    """Un FLUJO sí puede brincar: una venta grande, un trimestre malo."""
    flujos = _serie([100.0, 102.0, 1.5, 104.0, 103.0], "activos_totales")
    flujos["periodo_tipo"] = "Q"
    assert detectar_imposibles(flujos) == []


# --------------------------------------------------------------------------------------
# 44.2 · Sobre datos reales
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ticker,fecha,malo,bueno",
    [("PLD", "2021-12-31", 215_300_000, 17_000_000_000),
     ("WELL", "2020-12-31", 2_378_073_000, 13_000_000_000)],
)
def test_la_deuda_hundida_cae_a_la_version_anterior(repo, ticker, fecha, malo, bueno):
    """Marcar no borra: `Repositorio.hechos` filtra por estado ANTES de elegir
    la versión vigente, así que la celda cae sola a la observación previa."""
    h = repo.hechos(asof=HOY, tickers=ticker, conceptos=["deuda_total"], periodo_tipo="PUNTUAL")
    fila = h[pd.to_datetime(h["fecha_dato"]).dt.strftime("%Y-%m-%d") == fecha]
    assert not fila.empty, f"{ticker} perdió el corte entero, no solo la versión mala"
    valor = float(fila["valor"].iloc[0])
    assert valor != pytest.approx(malo), f"{ticker} sigue usando la cifra imposible"
    assert valor > bueno, f"{ticker} cayó a {valor:,.0f}, que tampoco es su deuda"


def test_ninguna_emisora_tiene_un_gasto_por_intereses_negativo(repo):
    """Un gasto negativo no es un gasto chico: es un signo al revés."""
    negativos = []
    for e in UNIVERSO_INICIAL:
        h = repo.hechos(asof=HOY, tickers=e.ticker, conceptos=["gasto_intereses"])
        if h.empty:
            continue
        malos = h[h["valor"] < 0]
        negativos += [(e.ticker, str(pd.Timestamp(f).date())) for f in malos["fecha_dato"]]
    assert negativos == [], f"gasto por intereses negativo en {negativos[:5]}"


def test_el_costo_implicito_de_la_deuda_ya_no_sale_negativo(repo):
    """Era el síntoma en pantalla: −46.6% en Agree Realty."""
    from src.servicio import series_de_graficas

    for e in UNIVERSO_INICIAL:
        panel = panel_de_conceptos(repo, e.ticker, asof=HOY, periodo_tipo="Q", n_periodos=None)
        if panel.empty:
            continue
        serie = series_de_graficas(panel).get("costo_deuda")
        if serie is None:
            continue
        malos = serie.dropna()
        malos = malos[malos < 0]
        assert malos.empty, f"{e.ticker} tiene costo de deuda negativo en {list(malos.index)[:3]}"


# --------------------------------------------------------------------------------------
# 44.3 · El EBITDAre imposible
# --------------------------------------------------------------------------------------


def test_el_ebitdare_no_puede_superar_al_ingreso_del_que_sale(repo):
    """La medida EXCLUYE la ganancia por venta, así que no puede pasarse del ingreso.

    Cuando se pasa es que la ganancia no se alcanzó a restar —Public Storage
    registró la venta de PS Business Parks como venta de una participación, no de
    un inmueble— y ese EBITDAre infla el TTM cuatro trimestres, con él el
    apalancamiento, y con él la Puerta 1.
    """
    for e in UNIVERSO_INICIAL:
        panel = panel_de_conceptos(repo, e.ticker, asof=HOY, periodo_tipo="Q", n_periodos=None)
        if panel.empty or "ebitdare" not in panel:
            continue
        eb = pd.to_numeric(panel["ebitdare"], errors="coerce")
        ing = pd.to_numeric(panel.get("ingresos_totales"), errors="coerce")
        con_ambos = eb.notna() & ing.notna() & (ing > 0)
        exceso = (eb / ing)[con_ambos]
        malos = exceso[exceso > TECHO_EBITDARE_SOBRE_INGRESO]
        assert malos.empty, f"{e.ticker}: EBITDAre sobre ingreso de {malos.round(2).to_dict()}"


def test_el_ebitdare_nunca_es_negativo_ni_cero(repo):
    """Una emisora en operación no lo tiene: lo que falla es un insumo."""
    for e in UNIVERSO_INICIAL:
        panel = panel_de_conceptos(repo, e.ticker, asof=HOY, periodo_tipo="Q", n_periodos=None)
        if panel.empty or "ebitdare" not in panel:
            continue
        eb = pd.to_numeric(panel["ebitdare"], errors="coerce").dropna()
        assert (eb > 0).all(), f"{e.ticker}: EBITDAre <= 0 en {list(eb[eb <= 0].index)[:3]}"


def test_psa_pierde_el_trimestre_de_la_venta_y_no_lo_falsea(repo):
    """El hueco es el resultado correcto: el dato de ese trimestre no se puede armar."""
    panel = panel_de_conceptos(repo, "PSA", asof=HOY, periodo_tipo="Q", n_periodos=None)
    if panel.empty:
        pytest.skip("No hay base de PSA.")
    f = pd.Timestamp("2022-09-30")
    if f not in panel.index:
        pytest.skip("El corte no está en el panel.")
    assert pd.isna(panel.loc[f, "ebitdare"])
    # Y el trimestre sigue existiendo con sus demás renglones: no se borró la columna.
    assert pd.notna(panel.loc[f, "ingresos_totales"])


# --------------------------------------------------------------------------------------
# 44.4 · Las dos implementaciones no se pueden separar
# --------------------------------------------------------------------------------------


def test_las_dos_implementaciones_del_ebitdare_coinciden(repo):
    """`_derivar_ebitdare` alimenta al modelo; `@ebitdare` a la tabla, la gráfica
    y el libro de Excel. La guarda entró primero en una sola, y eso es justo el
    defecto que las declaraciones existen para evitar."""
    insumo = INSUMO_POR_CLAVE["@ebitdare"]
    comparados = diferencias = 0
    for e in UNIVERSO_INICIAL:
        panel = panel_de_conceptos(repo, e.ticker, asof=HOY, periodo_tipo="Q", n_periodos=None)
        if panel.empty:
            continue
        funcion, declaracion = _derivar_ebitdare(panel), serie_de_insumo(panel, insumo)
        comparados += int((funcion.notna() | declaracion.notna()).sum())
        distinto = (funcion.notna() != declaracion.notna()) | (
            funcion.notna() & declaracion.notna() & ((funcion - declaracion).abs() > 1)
        )
        diferencias += int(distinto.sum())
    assert comparados > 400, "la comparación se quedó sin datos"
    assert diferencias == 0, f"{diferencias} de {comparados} celdas difieren"


def test_el_techo_de_la_declaracion_es_el_mismo_que_el_de_la_funcion():
    """Un número repetido en dos lugares es dos números esperando separarse."""
    assert INSUMO_POR_CLAVE["@ebitdare"].techo == (
        TECHO_EBITDARE_SOBRE_INGRESO, ("ingresos_totales",)
    )
    assert INSUMO_POR_CLAVE["@ebitdare"].resultado_positivo is True


# --------------------------------------------------------------------------------------
# 44.5 · Lo que se perdió está acotado
# --------------------------------------------------------------------------------------


def test_la_cobertura_de_las_graficas_no_se_desploma(repo):
    """Un piso medido: marcar de más borra datos buenos y no deja rastro."""
    from src.servicio import METRICAS_DE_GRAFICA, series_de_graficas

    celdas = 0
    for e in UNIVERSO_INICIAL:
        panel = panel_de_conceptos(repo, e.ticker, asof=HOY, periodo_tipo="Q", n_periodos=None)
        if panel.empty:
            continue
        series = series_de_graficas(panel)
        celdas += sum(
            int(series[m.clave].notna().sum())
            for m in METRICAS_DE_GRAFICA if m.clave in series.columns
        )
    assert celdas >= 7_500, f"las gráficas cayeron a {celdas:,} celdas con dato"
