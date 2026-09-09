"""Prueba 37 — El mismo trimestre, en las tres formas de verlo.

Por qué tres vistas y no una
----------------------------
Un estado financiero admite tres lecturas y las tres son legítimas:

* **As reported** — lo que la emisora imprimió, con sus renglones y su orden. Es
  la referencia y no se discute; también es incomparable entre emisoras, porque
  cada una nombra y agrupa distinto.
* **Bloomberg** — el molde estandarizado, que sí compara, a cambio de aplicar
  ajustes que se alejan del filing.
* **Propia** — nuestro catálogo de setenta y cinco renglones, el que alimenta el
  modelo.

Tenerlas juntas es lo que permite contestar "¿por qué tu deuda no es la de mi
terminal?" señalando el renglón, en vez de discutiendo.

Las tres trampas que costaron trabajo
-------------------------------------
**El resultado integral (37.1).** Welltower publica UN estado, "STATEMENTS OF
COMPREHENSIVE INCOME", y ese ES su estado de resultados. Public Storage y Global
Net Lease publican ese estado ADEMÁS del suyo, y ahí es la conciliación corta del
ORI. Buscarlo por nombre les daría a PSA y GNL una tabla de cinco renglones con
el título correcto encima.

**La columna corrida (37.2).** El balance de Prologis mete una celda de nota al
pie entre la etiqueta y los números. Contando las columnas desde la izquierda,
esa celda ocupaba el lugar del primer periodo y TODO el estado se recorría uno:
el efectivo de junio de 2026 aparecía bajo diciembre de 2025. Y se recorría
PAREJO, así que el balance seguía cuadrando consigo mismo y se leía impecable,
solo que fechado mal.

**La escala de la UPA (37.3).** El encabezado dice "$ in Thousands" una vez para
todo el estado y no aplica a los renglones por acción. La renta se imprime
``$ 1,426,467`` y son miles; la utilidad por acción se imprime ``$ 0.37`` y son
dólares. Escalar a ciegas convertía 37 centavos en 370 dólares por acción.
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
from src.datos.almacen import leer_reportados  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402
from src.export.excel import libro_de_estados  # noqa: E402
from src.ingesta import reportados as R  # noqa: E402
from src.modelo import bloomberg as B  # noqa: E402
from src.servicio import (  # noqa: E402
    RATIOS_PROPIOS,
    estados_reportados,
    panel_de_conceptos,
    ratios_propios,
)

# --------------------------------------------------------------------------------------
# 37.1 · El resultado integral es un RESPALDO, no un sinónimo
# --------------------------------------------------------------------------------------


def _reporte(nombre, archivo, categoria="Statements"):
    return {"nombre": nombre, "archivo": archivo, "categoria": categoria}


def test_welltower_usa_su_estado_de_resultado_integral():
    """Fusiona los dos estados en uno, así que ahí sí es su estado de resultados."""
    elegidos = R.clasificar_reportes([
        _reporte("CONSOLIDATED BALANCE SHEETS", "R2.htm"),
        _reporte("CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME (UNAUDITED)", "R3.htm"),
        _reporte("CONSOLIDATED STATEMENTS OF EQUITY (UNAUDITED)", "R4.htm"),
        _reporte("CONSOLIDATED STATEMENTS OF CASH FLOWS (UNAUDITED)", "R5.htm"),
    ])
    assert elegidos[R.ESTADO_RESULTADOS]["archivo"] == "R3.htm"
    assert elegidos[R.ESTADO_BALANCE]["archivo"] == "R2.htm"
    assert elegidos[R.ESTADO_FLUJO]["archivo"] == "R5.htm"


def test_public_storage_no_confunde_el_ori_con_su_estado_de_resultados():
    """La trampa: publica los DOS, y el integral es la conciliación corta del ORI.

    Si ganara por nombre, la vista as reported de PSA sería una tabla de cinco
    renglones —«otro resultado integral», «total»— con el encabezado correcto
    arriba. Se vería como un estado de resultados muy escueto, no como un error.
    """
    elegidos = R.clasificar_reportes([
        _reporte("CONSOLIDATED BALANCE SHEETS", "R2.htm"),
        _reporte("CONSOLIDATED BALANCE SHEETS (Parenthetical)", "R3.htm"),
        _reporte("CONSOLIDATED STATEMENTS OF INCOME", "R4.htm"),
        _reporte("CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME", "R5.htm"),
        _reporte("CONSOLIDATED STATEMENTS OF CASH FLOWS", "R8.htm"),
    ])
    assert elegidos[R.ESTADO_RESULTADOS]["archivo"] == "R4.htm", "ganó el ORI"


def test_el_ori_pierde_aunque_venga_primero_en_el_resumen():
    """El orden del `FilingSummary` no puede ser lo que decide.

    En los filings reales el estado de resultados aparece antes que el integral,
    así que una regla equivocada —que el integral cuente como estado de
    resultados— pasa desapercibida: gana el correcto por venir primero. Invertir
    el orden es lo único que distingue "la regla es buena" de "tuvimos suerte".
    """
    elegidos = R.clasificar_reportes([
        _reporte("CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME", "R5.htm"),
        _reporte("CONSOLIDATED STATEMENTS OF OPERATIONS", "R4.htm"),
    ])
    assert elegidos[R.ESTADO_RESULTADOS]["archivo"] == "R4.htm", "ganó el ORI por ir primero"


def test_el_parentetico_nunca_es_un_estado():
    """Es la nota al pie —valor par, acciones autorizadas—, no el balance."""
    elegidos = R.clasificar_reportes([
        _reporte("CONSOLIDATED BALANCE SHEETS (Parenthetical)", "R3.htm"),
        _reporte("CONSOLIDATED BALANCE SHEETS", "R2.htm"),
    ])
    assert elegidos[R.ESTADO_BALANCE]["archivo"] == "R2.htm"


def test_lo_que_no_es_un_estado_no_entra():
    """Las notas van en otra categoría y no deben clasificarse como estado."""
    elegidos = R.clasificar_reportes([
        _reporte("Income Taxes", "R30.htm", categoria="Notes"),
        _reporte("STATEMENTS OF INCOME TAXES PAYABLE", "R31.htm", categoria="Notes"),
    ])
    assert elegidos == {}


# --------------------------------------------------------------------------------------
# 37.2 · Las columnas se cuentan desde la derecha
# --------------------------------------------------------------------------------------

# Reproduce el balance de Prologis: la esquina declara `colspan=2` y cada renglón
# mete un `<td class="th"><sup>` de nota al pie entre la etiqueta y los números.
_BALANCE_CON_RELLENO = """
<table class="report">
<tr>
<th class="tl" colspan="2" rowspan="1"><div><strong>Consolidated Balance Sheets - USD ($)<br>
 $ in Thousands</strong></div></th>
<th class="th"><div>Jun. 30, 2026</div></th>
<th class="th"><div>Dec. 31, 2025</div></th>
</tr>
<tr class="ro">
<td class="pl" valign="top"><a class="a" onclick="Show.showAR( this,
 'defref_us-gaap_CashAndCashEquivalentsAtCarryingValue', window );">Cash and cash
 equivalents</a></td>
<td class="th"><sup></sup></td>
<td class="nump">1,765,043<span></span></td>
<td class="nump">1,145,647<span></span></td>
</tr>
</table>
"""


def test_la_celda_de_relleno_no_corre_las_columnas():
    """El error que dejaba el balance entero fechado un periodo antes.

    Junio tiene que traer 1,765 millones y diciembre 1,146. Al revés —o junio en
    blanco— es exactamente el síntoma que se vio, y no rompe ningún total.
    """
    df = R.parsear_reporte(
        _BALANCE_CON_RELLENO, "PLD", R.ESTADO_BALANCE,
        fecha_publicacion=dt.date(2026, 7, 29),
    )
    por_fecha = {f.fecha_dato: f.valor for f in df.itertuples()}
    assert por_fecha[dt.date(2026, 6, 30)] == pytest.approx(1_765_043_000)
    assert por_fecha[dt.date(2025, 12, 31)] == pytest.approx(1_145_647_000)


def test_un_balance_no_tiene_periodo_de_duracion():
    """Un saldo no dura: sus columnas son PUNTUAL y sin fecha de inicio."""
    df = R.parsear_reporte(
        _BALANCE_CON_RELLENO, "PLD", R.ESTADO_BALANCE,
        fecha_publicacion=dt.date(2026, 7, 29),
    )
    assert set(df["periodo_tipo"]) == {"PUNTUAL"}
    assert df["periodo_inicio"].isna().all()


# --------------------------------------------------------------------------------------
# 37.3 · La escala del encabezado no aplica a los renglones por acción
# --------------------------------------------------------------------------------------

_RESULTADOS = """
<table class="report">
<tr>
<th class="tl" colspan="1" rowspan="2"><div><strong>CONSOLIDATED STATEMENTS OF INCOME
 - USD ($)<br> shares in Thousands, $ in Thousands</strong></div></th>
<th class="th" colspan="1">3 Months Ended</th>
</tr>
<tr><th class="th"><div>Jun. 30, 2026</div></th></tr>
<tr class="re">
<td class="pl" valign="top"><a class="a" onclick="Show.showAR( this,
 'defref_us-gaap_RevenuesAbstract', window );"><strong>REVENUE</strong></a></td>
<td class="text">&#160;<span></span></td>
</tr>
<tr class="ro">
<td class="pl" valign="top"><a class="a" onclick="Show.showAR( this,
 'defref_us-gaap_LeaseIncome', window );">Rental (including reimbursements)</a></td>
<td class="nump">$ 1,426,467<span></span></td>
</tr>
<tr class="re">
<td class="pl" valign="top"><a class="a" onclick="Show.showAR( this,
 'defref_us-gaap_EarningsPerShareBasic', window );">Net income, basic (in dollars per
 share)</a></td>
<td class="nump">$ 0.37<span></span></td>
</tr>
<tr class="ro">
<td class="pl" valign="top"><a class="a" onclick="Show.showAR( this,
 'defref_us-gaap_WeightedAverageNumberOfSharesOutstandingBasic', window );">Basic (in
 shares)</a></td>
<td class="nump">932,307<span></span></td>
</tr>
<tr class="re">
<td class="pl" valign="top"><a class="a" onclick="Show.showAR( this,
 'defref_us-gaap_PaymentsOfDividends', window );">Distributions paid</a></td>
<td class="num">(801,394)<span></span></td>
</tr>
</table>
"""


def _parseado():
    df = R.parsear_reporte(
        _RESULTADOS, "O", R.ESTADO_RESULTADOS, fecha_publicacion=dt.date(2026, 8, 6),
    )
    return {f.etiqueta: f for f in df.itertuples()}


def test_el_monto_si_lleva_la_escala_del_encabezado():
    assert _parseado()["Rental (including reimbursements)"].valor == pytest.approx(1_426_467_000)


def test_la_cifra_por_accion_no_lleva_la_escala():
    """37 centavos, no 370 dólares. Las dos celdas traen el signo de pesos."""
    fila = _parseado()["Net income, basic (in dollars per share)"]
    assert fila.valor == pytest.approx(0.37)
    assert fila.escala == 1.0


def test_el_conteo_de_acciones_lleva_su_propia_escala():
    """«shares in Thousands» es una escala aparte de «$ in Thousands»."""
    assert _parseado()["Basic (in shares)"].valor == pytest.approx(932_307_000)


def test_el_parentesis_contable_es_un_signo_negativo():
    assert _parseado()["Distributions paid"].valor == pytest.approx(-801_394_000)


def test_el_renglon_de_seccion_se_conserva_sin_cifras():
    """La sangría y los títulos SON el estado tanto como los números."""
    fila = _parseado()["REVENUE"]
    assert fila.abstracta
    assert pd.isna(fila.valor) or fila.valor is None


def test_la_verificacion_corrige_la_escala_y_respeta_el_signo():
    """La regla completa: la magnitud se cuadra, el signo se deja.

    XBRL guarda ``PaymentsOfDividends`` en positivo porque el elemento ya
    significa una salida; el estado la imprime entre paréntesis porque ahí resta.
    Corregir el signo para que cuadre daría un estado de flujos donde los
    dividendos suman, que no es el de la emisora.
    """
    crudos = pd.DataFrame([
        {"tag": "PaymentsOfDividends", "periodo_tipo": "Q",
         "fecha_dato": dt.date(2026, 6, 30), "valor": 801_394_000.0,
         "fecha_publicacion": dt.date(2026, 8, 6)},
    ])
    df = R.parsear_reporte(
        _RESULTADOS, "O", R.ESTADO_RESULTADOS, fecha_publicacion=dt.date(2026, 8, 6),
    )
    verificado = R.verificar_escala(df, crudos)
    fila = verificado[verificado["etiqueta"] == "Distributions paid"].iloc[0]
    assert fila["verificado"] is True or bool(fila["verificado"])
    assert fila["valor"] == pytest.approx(-801_394_000), "le cambió el signo al reportado"


def test_lo_que_no_cuadra_se_marca_pero_no_se_tira():
    """Una etiqueta de extensión no está en `companyfacts` y aun así vale."""
    df = R.parsear_reporte(
        _RESULTADOS, "O", R.ESTADO_RESULTADOS, fecha_publicacion=dt.date(2026, 8, 6),
    )
    verificado = R.verificar_escala(df, pd.DataFrame(columns=["tag", "periodo_tipo",
                                                             "fecha_dato", "valor",
                                                             "fecha_publicacion"]))
    assert len(verificado) == len(df)
    assert not verificado["verificado"].any()


# --------------------------------------------------------------------------------------
# 37.4 · El panel: anual y trimestral, y todo el catálogo
# --------------------------------------------------------------------------------------


def _panel(ticker="O", tipo="Q"):
    return panel_de_conceptos(
        Repositorio(), ticker, asof=dt.date.today(), periodo_tipo=tipo, n_periodos=6
    )


def test_el_panel_trae_balance_y_flujo_juntos():
    """El panel del modelo no servía: carga lo que la valuación consume y ningún
    renglón de balance, así que la vista de Bloomberg salía con cero de
    veintiocho renglones de balance."""
    panel = _panel()
    if panel.empty:
        pytest.skip("No hay base cargada.")
    assert {"activos_totales", "ingresos_totales", "flujo_operacion"} <= set(panel.columns)
    # Y los no-GAAP del 8-K, que no son renglón de ningún estado.
    assert {"affo", "ffo_normalizado"} & set(panel.columns)


def test_el_panel_anual_termina_en_un_cierre_de_ejercicio():
    """Manda la frecuencia del FLUJO.

    El balance se pide siempre PUNTUAL y trae los cuatro cortes del año. Sin
    recortarlo, el panel anual terminaba el 30 de junio —un corte de balance sin
    ejercicio— y el estado de resultados salía vacío justo en la última columna,
    que es la que se mira.
    """
    panel = _panel(tipo="FY")
    if panel.empty:
        pytest.skip("No hay base cargada.")
    assert panel.index[-1].month == 12


# --------------------------------------------------------------------------------------
# 37.5 · El molde de Bloomberg
# --------------------------------------------------------------------------------------


def test_el_molde_tiene_los_tres_estados_y_sus_secciones():
    for estado in B.ESTADOS:
        plantilla = B.PLANTILLA[estado]
        assert plantilla, estado
        assert any(linea.seccion for linea in plantilla), estado


def test_el_fad_de_bloomberg_es_el_affo_del_emisor():
    """El aviso que vale por sí solo.

    La cascada de Bloomberg va FFO → «Adjusted Funds from Operations» → FAD, y el
    AFFO que reporta Realty Income coincide con el FAD, no con el renglón que
    Bloomberg llama AFFO. Tomarlo por su nombre metía un múltiplo equivocado con
    una etiqueta convincente.
    """
    por_etiqueta = {ln.etiqueta: ln for ln in B.PLANTILLA[B.RESULTADOS]}
    assert por_etiqueta["Funds Available For Distribution"].clave == "affo"
    assert por_etiqueta["Adjusted Funds from Operations"].clave != "affo"
    assert por_etiqueta["FAD Per Diluted Share"].clave == "affo_por_accion"


def test_los_renglones_que_no_salen_de_un_filing_quedan_vacios():
    """Un cero ahí sería una cifra inventada con formato de dato."""
    panel = _panel()
    if panel.empty:
        pytest.skip("No hay base cargada.")
    tabla = B.armar(panel, B.RESULTADOS, n_periodos=1)
    columnas = [c for c in tabla.columns
                if c not in ("Renglón", *B.COLUMNAS_DE_APOYO)]
    for etiqueta in ("Number of Properties Owned", "Gross Leaseable Area (Sq Ft)"):
        fila = tabla[tabla["Renglón"].str.strip() == etiqueta]
        assert not fila.empty
        assert fila[columnas].isna().all(axis=None), etiqueta


def test_los_ajustes_de_bloomberg_estan_nombrados_en_los_renglones_que_toca():
    """El ajuste no se aplica en silencio: el renglón lo declara."""
    # La etiqueta del molde NO lleva el signo: el «+» es presentación y vive
    # aparte, en `signo_texto`. Buscarlo dentro del nombre era acoplarse a cómo
    # se dibuja el renglón, no a cuál es.
    por_etiqueta = {ln.etiqueta: ln for ln in B.PLANTILLA[B.BALANCE]}
    assert por_etiqueta["Secured & Unsecured Debt"].ajuste
    assert "arrendamientos" in por_etiqueta["Secured & Unsecured Debt"].ajuste.lower()
    assert por_etiqueta["Accounts Payable"].ajuste


def test_la_deuda_de_bloomberg_mete_el_arrendamiento_adentro():
    """Contra el export real: 30,651.7 reportados + 414.2 de arrendamiento.

    Bloomberg publica 31,180.19 e incluye además 114.3 de arrendamiento
    FINANCIERO, que el catálogo no tiene como renglón aparte. La diferencia es
    conocida y está medida; lo que no se vale es taparla con una estimación.
    """
    panel = _panel()
    if panel.empty or "deuda_total" not in panel.columns:
        pytest.skip("No hay base cargada.")
    tabla = B.armar(panel, B.BALANCE, n_periodos=1)
    columnas = [c for c in tabla.columns
                if c not in ("Renglón", *B.COLUMNAS_DE_APOYO)]
    fila = tabla[tabla["Renglón"].str.strip() == "+ Secured & Unsecured Debt"]
    deuda = float(fila[columnas].iloc[0, -1]) / 1e6
    assert deuda == pytest.approx(31_065.9, rel=0.002)
    assert deuda > 30_651.7, "no metió el arrendamiento operativo"


def test_la_cobertura_se_declara_en_vez_de_estimarse():
    panel = _panel()
    if panel.empty:
        pytest.skip("No hay base cargada.")
    for estado in B.ESTADOS:
        con, piden = B.cobertura(panel, estado)
        assert 0 < con <= piden, estado


# --------------------------------------------------------------------------------------
# 37.6 · Los ratios de la vista propia
# --------------------------------------------------------------------------------------


def test_los_ratios_salen_sobre_el_periodo_que_se_ve():
    panel = _panel()
    if panel.empty:
        pytest.skip("No hay base cargada.")
    tabla = ratios_propios(panel)
    assert len(tabla) == len(RATIOS_PROPIOS)
    columnas = [c for c in tabla.columns if c not in ("Ratio", "formato", "explicacion")]
    assert columnas, "los ratios salieron sin periodos"
    # Al menos la mitad tiene que poder calcularse, o el panel no sirve.
    llenos = tabla[columnas].notna().any(axis=1).sum()
    assert llenos >= len(RATIOS_PROPIOS) // 2


def test_cada_ratio_dice_de_que_renglones_sale():
    """Sin la explicación, un ratio es un número que hay que creerle."""
    for etiqueta, _clave, formato, explicacion in RATIOS_PROPIOS:
        assert etiqueta and explicacion, etiqueta
        assert formato in ("pct", "x"), etiqueta


def test_el_ebitdare_de_los_ratios_usa_la_misma_regla_que_el_modelo():
    """Sin depreciación no hay EBITDAre, aquí tampoco (prueba 36).

    Si esta vista lo calculara con la depreciación en cero, la pantalla mostraría
    dos apalancamientos distintos para el mismo trimestre y ninguno diría cuál.
    """
    panel = pd.DataFrame(
        [{"utilidad_neta": 463e6, "gasto_intereses": 182e6, "impuestos": -62e6,
          "depreciacion_amortizacion": None, "ingresos_totales": 3_545e6,
          "deuda_total": 17_726e6, "efectivo": 1_965e6}],
        index=pd.DatetimeIndex([dt.date(2026, 6, 30)]),
    )
    tabla = ratios_propios(panel)
    fila = tabla[tabla["Ratio"] == "Margen EBITDAre"].iloc[0]
    assert pd.isna(fila["2026-06-30"])


# --------------------------------------------------------------------------------------
# 37.7 · Sobre datos reales: las tres vistas y su descarga
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("ticker", [e.ticker for e in UNIVERSO_INICIAL])
def test_cada_emisora_tiene_sus_tres_estados_as_reported(ticker):
    datos = leer_reportados(ticker)
    if datos.empty:
        pytest.skip("No hay instantánea de estados as reported.")
    assert set(datos["estado"]) == set(R.ESTADOS), ticker


def test_el_as_reported_no_mezcla_dos_filings_en_una_tabla():
    """Cada filing es un documento con su propia versión de las cifras.

    Pegar columnas de dos daría un estado que nadie publicó, y no habría forma de
    saber cuál renglón vino de cuál.
    """
    if leer_reportados("O").empty:
        pytest.skip("No hay instantánea de estados as reported.")
    tabla = estados_reportados("O", R.ESTADO_BALANCE, asof=dt.date.today(), formulario="10-Q")
    assert not tabla.empty
    columnas = [c for c in tabla.columns if c not in ("Renglón", "sangria", "tag", "verificado")]
    assert 1 <= len(columnas) <= 4, columnas


def test_el_as_reported_respeta_el_corte_point_in_time():
    """Con un corte viejo tiene que salir el filing viejo, no el de hoy."""
    if leer_reportados("O").empty:
        pytest.skip("No hay instantánea de estados as reported.")
    hoy = estados_reportados("O", R.ESTADO_BALANCE, asof=dt.date.today(), formulario="10-Q")
    antes = estados_reportados("O", R.ESTADO_BALANCE, asof=dt.date(2026, 1, 1),
                               formulario="10-Q")
    if antes.empty:
        pytest.skip("La instantánea no llega tan atrás.")
    columnas_hoy = [c for c in hoy.columns if c[:2] == "20"]
    columnas_antes = [c for c in antes.columns if c[:2] == "20"]
    assert max(columnas_antes) < max(columnas_hoy)


def test_el_libro_de_excel_trae_las_tres_vistas():
    repo = Repositorio()
    if panel_de_conceptos(repo, "O", asof=dt.date.today()).empty:
        pytest.skip("No hay base cargada.")
    import io

    from openpyxl import load_workbook

    crudo = libro_de_estados(repo, "O", asof=dt.date.today())
    wb = load_workbook(io.BytesIO(crudo))
    nombres = wb.sheetnames
    assert any(n.startswith("BBG") for n in nombres), nombres
    assert any(n.startswith("Propia") for n in nombres), nombres
    assert "Ratios" in nombres, nombres
    # Y ninguna hoja truncada a 31 caracteres, que se confundiría con otra.
    assert len(set(nombres)) == len(nombres)
    assert all(len(n) <= 31 for n in nombres)


# --------------------------------------------------------------------------------------
# 37.8 · El molde de Bloomberg está COMPLETO
# --------------------------------------------------------------------------------------
#
# La primera versión de la vista escribía los renglones a mano y se quedó en 89 de
# 186: faltaba más de la mitad del estado de resultados, casi la mitad del balance
# y TODOS los ratios —los tres payout, los márgenes, el book value por acción, la
# deuda a capital—. Un molde "de Bloomberg" al que le faltan noventa y seis
# renglones no es el molde de Bloomberg; es una selección con su nombre.
#
# Lo peor es cómo se veía: la tabla salía ordenada, con encabezados correctos y
# cifras correctas. Nada gritaba "aquí falta la mitad". Por eso el molde dejó de
# escribirse y pasó a leerse de `molde_bloomberg.json`, y por eso estas pruebas
# cuentan renglones en vez de mirar unos cuantos.

RENGLONES_DEL_MOLDE = {"resultados": 92, "balance": 55, "flujo": 39}


def test_el_molde_tiene_los_186_renglones_del_export():
    """El conteo exacto, por estado. Si alguien recorta el molde, esto lo dice."""
    for estado, esperados in RENGLONES_DEL_MOLDE.items():
        assert len(B.PLANTILLA[estado]) == esperados, estado
    assert sum(len(v) for v in B.PLANTILLA.values()) == 186


def test_el_molde_conserva_el_orden_y_la_jerarquia_del_export():
    """Tres anclas por estado: el primero, el último y un renglón anidado.

    Reordenar el molde cambia el estado financiero, aunque los renglones sigan
    todos ahí: en un estado el orden ES parte del significado.
    """
    resultados = B.PLANTILLA[B.RESULTADOS]
    assert resultados[0].etiqueta == "Revenue" and resultados[0].nivel == 0
    assert resultados[-1].etiqueta == "Gross Leaseable Area (Sq Ft)"
    # «Base Rent» cuelga de «Rental Income», que cuelga de «Revenue».
    base = next(ln for ln in resultados if ln.etiqueta == "Base Rent")
    assert base.nivel == 2

    balance = B.PLANTILLA[B.BALANCE]
    assert balance[0].etiqueta == "Assets"
    assert balance[-1].etiqueta == "Number of Employees"
    unsecured = next(ln for ln in balance if ln.etiqueta == "Unsecured Debt")
    assert unsecured.nivel == 2

    flujo = B.PLANTILLA[B.FLUJO]
    assert flujo[0].etiqueta == "Cash From Operating Activities"
    assert flujo[-1].etiqueta == "Capital Expenditures to FFO"


def test_los_ratios_del_molde_estan_todos_mapeados():
    """La otra mitad de lo que faltaba: Bloomberg publica ratios, no solo montos.

    Se enumeran a propósito en vez de contarlos: un conteo pasa aunque se cambie
    un ratio por otro, y estos son los que un tenedor de REIT mira.
    """
    esperados = {
        B.RESULTADOS: ("AFFO Payout Ratio", "FAD Payout Ratio", "FFO Payout Ratio",
                       "EBITDA Margin (T12M)", "Operating Margin", "FFO per Share Growth"),
        B.BALANCE: ("Book Value per Share", "Net Debt", "Total Debt to Total Capital",
                    "Debt to Real-Estate Investment", "Tangible Common Equity Ratio",
                    "Total Liabilities to Total Common Equity"),
        B.FLUJO: ("Trailing 12M EBITDA Margin", "Capital Expenditures to FFO",
                  "Capital Expenditures to Real-Estate Investment"),
    }
    for estado, etiquetas in esperados.items():
        por_etiqueta = {ln.etiqueta: ln for ln in B.PLANTILLA[estado]}
        for etiqueta in etiquetas:
            linea = por_etiqueta.get(etiqueta)
            assert linea is not None, f"{estado}: falta {etiqueta} en el molde"
            assert linea.rinde_cifra, f"{estado}: {etiqueta} está en el molde y no se calcula"


def test_el_mapeo_no_nombra_renglones_que_no_existen():
    """Un mapeo huérfano es una etiqueta mal escrita que nunca se va a llenar.

    Sin esto, cambiar «Net Debt» por «Net debt» en el mapeo no rompe nada: el
    renglón simplemente sale vacío para siempre, como si no tuviéramos el dato.
    """
    for estado, mapeo in B.MAPEO.items():
        del_molde = {ln.etiqueta for ln in B.PLANTILLA[estado]}
        huerfanas = sorted(set(mapeo) - del_molde)
        assert huerfanas == [], f"{estado}: {huerfanas}"


def test_cada_renglon_sin_dato_dice_por_que():
    """Un hueco tiene nombre. Es el principio de la pantalla, aplicado al molde.

    Un renglón que ni se calcula ni explica por qué es un olvido disfrazado de
    dato faltante, y desde afuera los dos se ven igual.
    """
    mudos = []
    for estado, plantilla in B.PLANTILLA.items():
        for linea in plantilla:
            if linea.seccion or linea.rinde_cifra or linea.nota:
                continue
            mudos.append(f"{estado}: {linea.etiqueta}")
    assert mudos == [], "renglones sin dato y sin explicación:\n" + "\n".join(mudos)


def test_la_utilidad_antes_y_despues_del_minoritario_no_son_la_misma():
    """Salían idénticas, y el minoritario aparecía restándose de la nada.

    Bloomberg parte de la utilidad CON minoritario y lo baja en el renglón
    siguiente; nuestro `utilidad_neta` sale de `NetIncomeLoss`, que en us-gaap ya
    es la atribuible a la controladora. Mapear los dos renglones a la misma clave
    daba una cascada que no cerraba: 344.0, menos 26.6, igual a 344.0.
    """
    panel = _panel()
    if panel.empty:
        pytest.skip("No hay base cargada.")
    tabla = B.armar(panel, B.RESULTADOS, n_periodos=1)
    columna = [c for c in tabla.columns
               if c not in ("Renglón", *B.COLUMNAS_DE_APOYO)][0]

    def valor(etiqueta):
        fila = tabla[tabla["Renglón"].str.strip().str.lstrip("+- ") == etiqueta]
        return None if fila.empty else fila[columna].iloc[0]

    con_mi = valor("Income (Loss) Incl. MI")
    sin_mi = valor("Net Income, GAAP")
    minoritario = valor("Minority Interest")
    if con_mi is None or sin_mi is None or pd.isna(con_mi) or pd.isna(sin_mi):
        pytest.skip("La emisora no reporta las dos cifras al corte.")
    assert con_mi != sin_mi, "los dos renglones volvieron a la misma clave"
    assert con_mi - minoritario == pytest.approx(sin_mi, rel=0.001), "la cascada no cierra"


def test_el_encabezado_de_seccion_no_lleva_cifra():
    """El flujo repite «Cash From Operating Activities»: título y total.

    Mapeando por etiqueta, el título se llevaba también la cifra del total y el
    bloque salía con el mismo número arriba y abajo, como si el estado sumara
    dos veces. Un encabezado es un encabezado aunque se llame igual que su total.
    """
    flujo = B.PLANTILLA[B.FLUJO]
    titulo = flujo[0]
    assert titulo.etiqueta == "Cash From Operating Activities"
    assert titulo.seccion and not titulo.rinde_cifra, "el título se llevó la cifra"
    total = next(ln for ln in flujo[1:] if ln.etiqueta == "Cash From Operating Activities")
    assert total.rinde_cifra, "el total se quedó sin cifra"


def test_un_renglon_que_no_llenamos_sigue_contando_en_la_cobertura():
    """La cobertura no puede mejorar por ignorar lo que no sabemos llenar.

    La primera regla decía que un renglón de nivel cero sin dato era un
    encabezado, así que «Number of Employees» y «Sales per Employee» salían del
    denominador: la vista se veía más completa cuanto MENOS supiera llenar. Los
    encabezados de verdad son los que el propio export deja sin mnemónico.
    """
    for estado in B.ESTADOS:
        secciones = [ln for ln in B.PLANTILLA[estado] if ln.seccion]
        assert len(secciones) <= 4, f"{estado}: {len(secciones)} encabezados es demasiado"
        for linea in secciones:
            assert not linea.campo_bbg, f"{estado}: {linea.etiqueta} sí es un dato"
    por_etiqueta = {ln.etiqueta: ln for ln in B.PLANTILLA[B.BALANCE]}
    assert not por_etiqueta["Number of Employees"].seccion
