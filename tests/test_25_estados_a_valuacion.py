"""Prueba 25 — De los estados financieros a la valuación, sin huecos inventados.

La pantalla decía **INCONCLUSO para nueve de diez emisoras**, y no porque el
modelo fuera prudente: porque le faltaban datos que la ingesta ya sabía traer y
nadie guardaba. El orquestador llamaba a `xbrl.py`, que mapea quince conceptos, y
**nunca a `estados.py`**, que define setenta y cinco renglones de estado de
resultados, balance y flujo de efectivo. Sesenta de esos setenta y cinco no
tenían ni un dato en la base.

Sin ellos faltaban las tres piezas que sostienen la Puerta 1: el gasto por
intereses, la deuda total y los impuestos. Sin las tres no hay EBITDAre, ni costo
de la deuda, ni apalancamiento — y la puerta se quedaba con dos criterios
medibles de cinco cuando exige tres.

Estas pruebas cubren las cuatro cosas que hubo que arreglar, y las tres guardas
que hicieron falta para que cerrar el hueco no produjera números peores que el
hueco:

* **25.1** La elección de etiqueta GAAP exige vigencia, no solo cobertura.
* **25.2** Los tres estados se persisten y se leen point-in-time.
* **25.3** El NOI y el EBITDAre se derivan con su definición, y se niegan a
  publicarse cuando la derivación no ve el negocio.
* **25.4** Lo que no se sabe no se publica: deuda desconocida no es deuda cero.
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

from src.ingesta.estados import (  # noqa: E402
    COLUMNAS_HECHOS,
    LINEAS,
    VENTANA_DE_VIGENCIA,
    elegir_tags,
    hechos_de_estados,
    tags_de,
)
from src.servicio import (  # noqa: E402
    CONCEPTOS_BALANCE,
    CONCEPTOS_PANEL,
    ORIGEN_DE_INSUMOS,
    PISO_NOI_SOBRE_INGRESO,
    _derivar_ebitdare,
    _derivar_noi,
    estado_financiero,
)


def _crudos(filas: list[dict]) -> pd.DataFrame:
    base = {
        "ticker": "X", "taxonomia": "us-gaap", "unidad": "USD",
        "periodo_tipo": "Q", "fecha_inicio": None, "fecha_publicacion": dt.date(2026, 8, 1),
        "formulario": "10-Q", "accession": "0000-00", "marco": "",
    }
    return pd.DataFrame([{**base, **f} for f in filas])


# --------------------------------------------------------------------------------------
# 25.1 · Una etiqueta que la emisora abandonó no sirve para valuar hoy
# --------------------------------------------------------------------------------------


def test_se_prefiere_la_etiqueta_vigente_sobre_la_de_mas_historia():
    """El caso real de Realty Income, con sus dos etiquetas de intereses.

    Reportó en ``InterestExpense`` de 2015 a 2024 —138 observaciones— y pasó a
    ``InterestExpenseOperating``, con 22. Por cobertura total ganaba la muerta, y
    la serie que alimenta el EBITDAre se quedaba sin los últimos dos años. Sin
    dato reciente no hay apalancamiento, y sin apalancamiento la Puerta 1 no
    junta los tres criterios medibles que exige.
    """
    filas = []
    for i in range(40):  # muchísima historia, pero termina en 2024
        filas.append({"tag": "InterestExpense", "fecha_dato": dt.date(2015, 3, 31)
                      + pd.Timedelta(days=90 * i), "valor": 100.0})
    for i in range(6):   # poca historia, pero llega a hoy
        filas.append({"tag": "InterestExpenseOperating",
                      "fecha_dato": dt.date(2025, 3, 31) + pd.Timedelta(days=90 * i),
                      "valor": 110.0})
    crudos = _crudos(filas)
    crudos["fecha_dato"] = pd.to_datetime(crudos["fecha_dato"]).dt.date

    elegidas = elegir_tags(crudos, "O")
    assert elegidas["gasto_intereses"] == "InterestExpenseOperating", (
        "eligió la etiqueta con más historia aunque la emisora dejó de usarla"
    )


def test_si_ninguna_esta_vigente_se_conserva_la_de_mas_cobertura():
    """Una serie que termina en 2017 es preferible a ninguna, mientras se diga."""
    filas = [
        {"tag": "InterestExpense", "fecha_dato": dt.date(2016, 3, 31) + pd.Timedelta(days=90 * i),
         "valor": 100.0} for i in range(8)
    ]
    filas.append({"tag": "InterestExpenseNonoperating", "fecha_dato": dt.date(2015, 3, 31),
                  "valor": 50.0})
    crudos = _crudos(filas)
    crudos["fecha_dato"] = pd.to_datetime(crudos["fecha_dato"]).dt.date
    assert elegir_tags(crudos, "O")["gasto_intereses"] == "InterestExpense"


def test_la_ventana_de_vigencia_deja_pasar_una_serie_anual():
    """Un renglón que solo se publica al cierre lleva hasta catorce meses de rezago."""
    assert VENTANA_DE_VIGENCIA.months >= 15, (
        "una ventana más corta descartaría las líneas que solo se reportan al cierre del año"
    )


def test_la_deuda_total_conoce_la_etiqueta_que_usan_las_emisoras_de_hoy():
    """`LongTermDebt` es la canónica y casi nadie la usa; O reporta `NotesPayable`."""
    assert "NotesPayable" in tags_de("O", "deuda_total")
    assert "DebtLongtermAndShorttermCombinedAmount" in tags_de("O", "deuda_total")


# --------------------------------------------------------------------------------------
# 25.2 · Los tres estados llegan a la base y se leen al corte
# --------------------------------------------------------------------------------------


def test_los_estados_se_convierten_en_filas_de_hechos():
    """El módulo sabía armar los estados; lo que faltaba era escribirlos."""
    companyfacts = {
        "facts": {
            "us-gaap": {
                "InterestExpenseOperating": {"units": {"USD": [
                    {"start": "2026-04-01", "end": "2026-06-30", "val": 312e6,
                     "filed": "2026-08-05", "form": "10-Q", "accn": "0001-26-000001"},
                ]}},
                "NotesPayable": {"units": {"USD": [
                    {"end": "2026-06-30", "val": 25_092e6,
                     "filed": "2026-08-05", "form": "10-Q", "accn": "0001-26-000001"},
                ]}},
            }
        }
    }
    df = hechos_de_estados(companyfacts, "O", "726728")
    assert list(df.columns) == list(COLUMNAS_HECHOS)
    por_concepto = df.set_index("concepto")

    intereses = por_concepto.loc["gasto_intereses"]
    assert intereses["valor"] == pytest.approx(312e6)
    assert intereses["periodo_tipo"] == "Q"
    assert bool(intereses["es_primario"])

    deuda = por_concepto.loc["deuda_total"]
    assert deuda["valor"] == pytest.approx(25_092e6)
    # Un saldo de balance es PUNTUAL. Guardarlo como trimestral es la razón por la
    # que la consulta del panel, que pide `periodo_tipo="Q"`, no lo veía nunca.
    assert deuda["periodo_tipo"] == "PUNTUAL"
    assert "sec.gov/Archives" in str(deuda["url_filing"])


def test_el_cuarto_trimestre_derivado_no_se_marca_como_primario():
    """Q4 = FY − 9M es una cuenta nuestra, no un dato que la SEC recibió.

    En Estados Unidos no se presenta un 10-Q del cuarto trimestre, así que el Q4
    no existe en XBRL de ninguna emisora. Se deriva —sin él la serie tiene un
    hueco anual que rompe cualquier TTM— pero decir que es primario sería
    presentar una resta propia como si viniera del emisor.
    """
    companyfacts = {
        "facts": {"us-gaap": {"InterestExpenseOperating": {"units": {"USD": [
            {"start": "2025-01-01", "end": "2025-09-30", "val": 900e6,
             "filed": "2025-11-01", "form": "10-Q", "accn": "a"},
            {"start": "2025-01-01", "end": "2025-12-31", "val": 1_200e6,
             "filed": "2026-02-20", "form": "10-K", "accn": "b"},
        ]}}}}
    }
    df = hechos_de_estados(companyfacts, "O", "726728")
    q4 = df[(df["periodo_tipo"] == "Q") & (df["fecha_dato"] == dt.date(2025, 12, 31))]
    assert len(q4) == 1
    assert q4.iloc[0]["valor"] == pytest.approx(300e6)
    assert not bool(q4.iloc[0]["es_primario"])
    # La fecha de publicación es la MÁS TARDÍA de sus componentes: antes de esa
    # fecha el número no era deducible ni con lápiz (P1).
    assert q4.iloc[0]["fecha_publicacion"] == dt.date(2026, 2, 20)


def test_el_estado_financiero_respeta_el_corte(repo_vacio):
    """Point-in-time: lo que se sabía al corte, no la reexpresión posterior."""
    repo_vacio.registrar_emisores([type("E", (), {
        "ticker": "X", "cik": "1", "nombre": "X", "sector": "Net Lease"})()])
    repo_vacio.guardar_hechos([
        {"ticker": "X", "concepto": "ingreso_rentas", "periodo_tipo": "Q",
         "fecha_dato": dt.date(2026, 6, 30), "fecha_publicacion": dt.date(2026, 8, 5),
         "valor": 1426e6, "unidad": "USD", "fuente": "SEC-XBRL", "es_primario": True,
         "estado": "valido"},
    ])
    antes = estado_financiero(repo_vacio, "X", "estado_resultados", asof=dt.date(2026, 8, 1))
    despues = estado_financiero(repo_vacio, "X", "estado_resultados", asof=dt.date(2026, 9, 7))
    assert antes.empty, "mostró un dato que aún no se había publicado"
    assert not despues.empty


def test_la_fecha_de_portada_no_abre_una_columna_de_balance(repo_vacio):
    """El conteo de acciones se fecha en la PORTADA del 10-Q, no en el balance.

    Abría una columna con un solo renglón lleno junto al balance de verdad, que
    se lee como si al trimestre le faltara todo lo demás.
    """
    repo_vacio.registrar_emisores([type("E", (), {
        "ticker": "X", "cik": "1", "nombre": "X", "sector": "Net Lease"})()])
    comunes = {"ticker": "X", "periodo_tipo": "PUNTUAL", "unidad": "USD",
               "fecha_publicacion": dt.date(2026, 8, 5), "fuente": "SEC-XBRL",
               "es_primario": True, "estado": "valido"}
    filas = [
        {**comunes, "concepto": c, "fecha_dato": dt.date(2026, 6, 30), "valor": v}
        for c, v in (("activos_totales", 76_441e6), ("deuda_total", 25_092e6),
                     ("efectivo", 553e6), ("inmuebles_neto", 55_112e6))
    ]
    # La portada: una sola línea a una fecha que no es cierre de trimestre.
    filas.append({**comunes, "concepto": "acciones_en_circulacion",
                  "fecha_dato": dt.date(2026, 7, 30), "valor": 946e6})
    repo_vacio.guardar_hechos(filas)

    balance = estado_financiero(repo_vacio, "X", "balance", asof=dt.date(2026, 9, 7))
    assert "2026-07-30" not in balance.columns, "la fecha de portada abrió una columna"
    assert "2026-06-30" in balance.columns


# --------------------------------------------------------------------------------------
# 25.3 · El NOI y el EBITDAre, con su definición y sus límites
# --------------------------------------------------------------------------------------


def _panel(valores: dict[str, list[float]], n: int = 6) -> pd.DataFrame:
    return pd.DataFrame(valores, index=pd.date_range("2025-03-31", periods=n, freq="QE"))


def test_el_noi_se_deriva_de_sus_dos_piernas():
    panel = _panel({
        "ingreso_rentas": [1000.0] * 6,
        "gasto_operacion_inmueble": [300.0] * 6,
        "gasto_predial_seguro": [50.0] * 6,
    })
    assert _derivar_noi(panel).iloc[-1] == pytest.approx(650.0)


def test_el_noi_reportado_por_la_emisora_manda_sobre_el_derivado():
    """Se reconstruye solo cuando falta: XBRL no tiene etiqueta de NOI."""
    panel = _panel({
        "noi": [700.0, 700.0, None, None, None, None],
        "ingreso_rentas": [1000.0] * 6,
        "gasto_operacion_inmueble": [300.0] * 6,
    })
    noi = _derivar_noi(panel)
    assert noi.iloc[0] == pytest.approx(700.0), "pisó el NOI que publicó la emisora"
    assert noi.iloc[-1] == pytest.approx(700.0), "no derivó donde faltaba"


def test_sin_la_pierna_de_gastos_no_hay_noi():
    """Sin ella el NOI sale igual al ingreso —margen de 100%— y el NAV se dispara."""
    panel = _panel({"ingreso_rentas": [1000.0] * 6})
    assert _derivar_noi(panel).isna().all()


def test_el_noi_que_no_ve_el_negocio_no_se_publica():
    """El caso de Welltower, que factura por operación y no por renta triple neta.

    Derivar su NOI de la línea de renta captura una astilla del negocio: daba un
    cap rate implícito de 0.89% y un NAV de 19 dólares para una acción que cotiza
    arriba de 150. La aritmética es correcta; el alcance no, y ninguno de los dos
    números levanta una excepción.
    """
    panel = _panel({
        "ingresos": [2000.0] * 6,          # el negocio completo
        "ingreso_rentas": [200.0] * 6,     # solo la parte de renta
        "gasto_operacion_inmueble": [60.0] * 6,
    })
    # 140 sobre 2000 es 7%: muy por debajo del piso.
    assert 140 / 2000 < PISO_NOI_SOBRE_INGRESO
    assert _derivar_noi(panel).isna().all(), "publicó un NOI que no cubre el negocio"


def test_el_ebitdare_sigue_la_definicion_de_nareit():
    """Las dos últimas partidas son las que lo separan del EBITDA común."""
    panel = _panel({
        "utilidad_neta": [300.0] * 6,
        "gasto_intereses": [100.0] * 6,
        "impuestos": [20.0] * 6,
        "depreciacion_amortizacion": [600.0] * 6,
        "deterioro": [50.0] * 6,
        "ganancia_venta_inmuebles": [40.0] * 6,
    })
    assert _derivar_ebitdare(panel).iloc[-1] == pytest.approx(
        300 + 100 + 20 + 600 + 50 - 40
    )


def test_sin_intereses_no_es_ebitdare():
    """Sería utilidad operativa con otro nombre, y el apalancamiento saldría bajo."""
    panel = _panel({
        "utilidad_neta": [300.0] * 6,
        "depreciacion_amortizacion": [600.0] * 6,
    })
    assert _derivar_ebitdare(panel).isna().all()


def test_un_trimestre_sin_deterioro_no_borra_el_ebitdare():
    """El trimestre NORMAL no tiene deterioro, y ese hueco tumbaba el TTM entero.

    `NaN` en una partida que suma hacía nulo el EBITDAre de ese trimestre, y con
    él se caía la ventana de cuatro trimestres seguidos. Media docena de emisoras
    se quedaban sin apalancamiento por un renglón que no tuvieron que reportar.
    """
    panel = _panel({
        "utilidad_neta": [300.0] * 6,
        "gasto_intereses": [100.0] * 6,
        "depreciacion_amortizacion": [600.0] * 6,
        "deterioro": [None, None, 50.0, None, None, None],
    })
    ebitdare = _derivar_ebitdare(panel)
    assert ebitdare.notna().all(), "un trimestre sin deterioro dejó un hueco"
    assert ebitdare.iloc[0] == pytest.approx(1000.0)
    assert ebitdare.iloc[2] == pytest.approx(1050.0)


# --------------------------------------------------------------------------------------
# 25.4 · Lo que no se sabe no se publica
# --------------------------------------------------------------------------------------


def test_una_deuda_de_cero_no_es_un_balance_desapalancado(repo_vacio):
    """Un REIT con deuda cero no existe: es una etiqueta GAAP mal elegida.

    Con deuda cero y efectivo positivo la deuda NETA sale negativa y el
    apalancamiento se dibuja en −0.87x, que se lee como «menos que
    desapalancado» justo en el emisor más endeudado del universo.
    """
    from src.servicio import _saldos_de_balance

    repo_vacio.registrar_emisores([type("E", (), {
        "ticker": "X", "cik": "1", "nombre": "X", "sector": "Net Lease"})()])
    comunes = {"ticker": "X", "periodo_tipo": "PUNTUAL", "unidad": "USD",
               "fecha_dato": dt.date(2026, 6, 30), "fecha_publicacion": dt.date(2026, 8, 5),
               "fuente": "SEC-XBRL", "es_primario": True, "estado": "valido"}
    repo_vacio.guardar_hechos([
        {**comunes, "concepto": "deuda_total", "valor": 0.0},
        {**comunes, "concepto": "efectivo", "valor": 154e6},
    ])
    saldos = _saldos_de_balance(repo_vacio, "X", asof=dt.date(2026, 9, 7))
    assert "deuda_total" not in saldos
    assert saldos["efectivo"] == pytest.approx(154e6)


# --------------------------------------------------------------------------------------
# 25.5 · El cableado: la cadena completa llega a la pantalla
# --------------------------------------------------------------------------------------


def test_el_panel_pide_los_conceptos_que_necesita_para_derivar():
    """Faltaban en la consulta, que es la razón por la que nunca llegaban."""
    for concepto in ("gasto_intereses", "impuestos", "depreciacion_amortizacion",
                     "deterioro", "ganancia_venta_inmuebles", "gasto_operacion_inmueble"):
        assert concepto in CONCEPTOS_PANEL, f"{concepto} no se pide al repositorio"
    # Y los del balance van aparte, porque son PUNTUAL y no trimestrales.
    assert "deuda_total" in CONCEPTOS_BALANCE
    assert "deuda_total" not in CONCEPTOS_PANEL, (
        "pedirlo con periodo_tipo='Q' devuelve cero filas: un saldo no es un trimestre"
    )


def test_el_orquestador_ingesta_los_estados():
    """El módulo existía y funcionaba; lo que faltaba era la llamada."""
    fuente = (RAIZ / "src" / "ingesta" / "orquestador.py").read_text(encoding="utf-8")
    assert "def ingestar_estados(" in fuente
    assert "r_est = ingestar_estados(" in fuente, (
        "la función existe pero el bucle de ingesta no la llama"
    )


def test_la_pantalla_muestra_la_cadena_de_estados_a_modelo():
    pagina = (RAIZ / "app" / "pages" / "1_Valuacion.py").read_text(encoding="utf-8")
    assert "estado_financiero(" in pagina
    assert "ORIGEN_DE_INSUMOS" in pagina
    # Los tres estados, no solo uno.
    for estado in ("estado_resultados", "balance", "flujo_efectivo"):
        assert estado in pagina


def test_el_origen_de_cada_insumo_esta_declarado():
    """La tabla que contesta «¿de dónde salió este número?» sin abrir el código."""
    insumos = {a for a, _, _ in ORIGEN_DE_INSUMOS}
    for esperado in ("NOI trimestral", "EBITDAre TTM", "Deuda neta"):
        assert esperado in insumos
    for _, formula, porque in ORIGEN_DE_INSUMOS:
        assert formula.strip(), "un insumo sin fórmula no se puede rastrear"
        assert len(porque) > 40, "un insumo sin explicación no se puede juzgar"


def test_la_taxonomia_de_estados_sigue_completa():
    """Setenta y cinco renglones repartidos en los tres estados."""
    assert len(LINEAS) >= 75
    assert len({ln.clave for ln in LINEAS}) == len(LINEAS), "hay claves repetidas"
