"""Exportación a Excel con fórmulas **vivas**, no valores pegados.

El usuario tiene que poder cambiar el cap rate o el precio en la hoja de Inputs y
ver todo recalcularse. Un libro con valores pegados es una fotografía; uno con
fórmulas es un modelo.

Convención de color (la de mesa, no la de reporte)
--------------------------------------------------
* **Azul sobre amarillo** — input del usuario, editable.
* **Negro** — fórmula. No se toca.
* **Verde** — referencia a otra hoja.

Cuidado con las unidades
------------------------
Una celda con formato ``#,##0 "bps"`` **no multiplica por 10,000**: el formato
solo pega el texto "bps" al número que ya está en la celda. Guardar 0.0409 con
ese formato muestra "0 bps" en vez de "409 bps". Este error ya se cometió en este
proyecto. Por eso ``escribir_bps`` escribe la fórmula de escalamiento explícita y
existe una prueba automatizada dedicada.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from src.modelo.cascada import TODAS_LAS_LINEAS
from src.modelo.valuacion import InsumosValuacion

# --------------------------------------------------------------------------------------
# Estilos
# --------------------------------------------------------------------------------------

AZUL = "FF0000FF"
NEGRO = "FF000000"
VERDE = "FF008000"
AMARILLO = "FFFFFF99"
GRIS = "FFF2F2F2"
ROJO = "FFC00000"

FUENTE_INPUT = Font(color=AZUL, bold=True, name="Calibri", size=11)
FUENTE_FORMULA = Font(color=NEGRO, name="Calibri", size=11)
FUENTE_ENLACE = Font(color=VERDE, name="Calibri", size=11)
FUENTE_TITULO = Font(bold=True, size=14, name="Calibri")
FUENTE_SECCION = Font(bold=True, size=11, name="Calibri")
FUENTE_TRAMPA = Font(color=ROJO, bold=True, name="Calibri", size=11)

RELLENO_INPUT = PatternFill("solid", fgColor=AMARILLO)
RELLENO_SECCION = PatternFill("solid", fgColor=GRIS)

BORDE_INFERIOR = Border(bottom=Side(style="thin"))
BORDE_TOTAL = Border(top=Side(style="thin"), bottom=Side(style="double"))

# Formatos numéricos
FMT_MONEDA = '#,##0.00'
FMT_MILES = '#,##0'
FMT_PCT = '0.00%'
FMT_PCT1 = '0.0%'
FMT_VECES = '0.00"x"'
# El formato bps NO escala: el número guardado ya tiene que venir en puntos base.
FMT_BPS = '#,##0" bps"'


# --------------------------------------------------------------------------------------
# Escritura con unidades correctas
# --------------------------------------------------------------------------------------


def escribir_input(ws: Worksheet, celda: str, valor, formato: str = FMT_MONEDA, nota: str = ""):
    """Celda editable por el usuario: azul sobre amarillo."""
    c = ws[celda]
    c.value = valor
    c.font = FUENTE_INPUT
    c.fill = RELLENO_INPUT
    c.number_format = formato
    if nota:
        ws[_desplazar(celda, columnas=1)] = nota
        ws[_desplazar(celda, columnas=1)].font = Font(italic=True, size=9, color="FF808080")
    return c


def escribir_formula(ws: Worksheet, celda: str, formula: str, formato: str = FMT_MONEDA):
    """Celda calculada: negro, fórmula viva."""
    c = ws[celda]
    c.value = formula if formula.startswith("=") else f"={formula}"
    c.font = FUENTE_FORMULA
    c.number_format = formato
    return c


def escribir_bps(ws: Worksheet, celda: str, referencia_decimal: str):
    """Escribe una celda en puntos base a partir de una referencia en decimal.

    ``referencia_decimal`` apunta a una celda que contiene el valor en decimal
    (por ejemplo 0.0409). Aquí se escribe ``=ROUND(ref*10000,0)`` para que la celda
    contenga 409, y **luego** se aplica el formato de bps.

    Poner el formato ``#,##0" bps"`` sobre 0.0409 mostraría "0 bps": el formato
    pega texto, no escala. Este es exactamente el error que costó una prima de
    409 bps mostrada como "0 bps".
    """
    c = ws[celda]
    c.value = f"=ROUND({referencia_decimal}*10000,0)"
    c.font = FUENTE_FORMULA
    c.number_format = FMT_BPS
    return c


def escribir_etiqueta(ws: Worksheet, celda: str, texto: str, *, seccion: bool = False, trampa: bool = False):
    c = ws[celda]
    c.value = texto
    if trampa:
        c.font = FUENTE_TRAMPA
    elif seccion:
        c.font = FUENTE_SECCION
        c.fill = RELLENO_SECCION
    else:
        c.font = FUENTE_FORMULA
    return c


def _desplazar(celda: str, filas: int = 0, columnas: int = 0) -> str:
    from openpyxl.utils.cell import column_index_from_string, coordinate_from_string

    col, fila = coordinate_from_string(celda)
    return f"{get_column_letter(column_index_from_string(col) + columnas)}{fila + filas}"


def _ancho(ws: Worksheet, anchos: dict[str, int]) -> None:
    for col, w in anchos.items():
        ws.column_dimensions[col].width = w


# --------------------------------------------------------------------------------------
# Construcción del libro
# --------------------------------------------------------------------------------------


@dataclass
class DatosExportacion:
    """Todo lo que necesita el libro. Los componentes van con su signo de reporte."""

    ticker: str
    nombre: str
    sector: str
    fecha_corte: dt.date
    insumos: InsumosValuacion
    componentes_cascada: dict[str, float]
    cap_rate_mercado: float = 0.065
    tasa_libre_riesgo: float = 0.042
    tasa_udibono_real: float = 0.047
    yield_adquisiciones: float | None = None
    fuentes: list[dict] | None = None
    escala: float = 1_000_000.0
    etiqueta_escala: str = "millones de USD"


def exportar(datos: DatosExportacion, ruta: Path | str) -> Path:
    """Genera el libro completo con fórmulas vivas y lo guarda."""
    wb = Workbook()
    wb.remove(wb.active)

    _hoja_leeme(wb, datos)
    _hoja_inputs(wb, datos)
    _hoja_cascada(wb, datos)
    _hoja_valuacion(wb, datos)
    _hoja_sensibilidad(wb, datos)
    _hoja_fuentes(wb, datos)

    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta)
    return ruta


# --------------------------------------------------------------------------------------
# Hoja: Léeme
# --------------------------------------------------------------------------------------

GLOSARIO: tuple[tuple[str, str], ...] = (
    ("NOI", "Net Operating Income. Ingreso por rentas menos gastos operativos del inmueble. No incluye corporativo, depreciación ni intereses."),
    ("FFO", "Funds From Operations. Utilidad neta más depreciación de inmuebles, menos ganancias por venta. Definición Nareit."),
    ("FFO Normalizado", "FFO ajustado por partidas no recurrentes, para que la serie sea comparable trimestre a trimestre."),
    ("AFFO", "Adjusted FFO. FFO normalizado menos CapEx de mantenimiento, comisiones de arrendamiento y renta en línea recta. Es el número que paga el dividendo."),
    ("Renta en línea recta", "TRAMPA. La contabilidad promedia la renta de todo el contrato, reconociendo ingreso que aún no se cobra. Es papel, no efectivo. Se resta."),
    ("CapEx de mantenimiento", "TRAMPA. Donde más se manipula: reclasificarlo como desarrollo sube el AFFO sin que nada cambie. 10%–20% del NOI en portafolio estabilizado; cero solo en net lease puro."),
    ("Revaluación a valor razonable", "TRAMPA. Bajo IFRS entra al estado de resultados y es 100% no-efectivo. Se elimina."),
    ("Cap rate implícito", "NOI anualizado entre EV ajustado. El EV se depura de activos que no generan renta inmobiliaria; si no, el cap rate sale sesgado a la baja."),
    ("NAV", "Valor de los inmuebles al cap rate de mercado, más efectivo, préstamos y coinversiones, menos deuda total. EXCLUYE goodwill: no genera renta."),
    ("Payout sobre AFFO", "Dividendo entre AFFO por acción. Es la única cobertura que significa algo. El payout sobre utilidad neta que publican los sitios financieros está mal."),
    ("Prima", "AFFO yield menos tasa libre de riesgo. Se compara como percentil de la propia historia del emisor, nunca como nivel contra otro emisor."),
    ("Percentil expandible", "Percentil calculado usando solo la historia hasta esa fecha. Usar la muestra completa sería fijar umbrales con información del futuro."),
    ("Spread de inversión", "Yield de adquisiciones menos costo marginal de capital. Negativo significa que cada compra destruye valor por acción."),
    ("Dilución oculta", "En estructuras UPREIT el REIT paga con unidades de la sociedad operativa que no aparecen en el conteo de acciones hasta convertirse."),
    ("Udibono", "Bono mexicano indizado a la inflación. Paga tasa real fija garantizada: es el benchmark real del inversionista mexicano."),
)


def _hoja_leeme(wb: Workbook, datos: DatosExportacion) -> Worksheet:
    ws = wb.create_sheet("Léeme")
    _ancho(ws, {"A": 30, "B": 110})

    ws["A1"] = f"Modelo de valuación — {datos.nombre} ({datos.ticker})"
    ws["A1"].font = FUENTE_TITULO
    ws["A2"] = f"Sector: {datos.sector}   |   Fecha de corte: {datos.fecha_corte}"
    ws["A3"] = f"Cifras en {datos.etiqueta_escala}, salvo las que van por acción."

    ws["A5"] = "CÓMO USAR ESTE LIBRO"
    ws["A5"].font = FUENTE_SECCION
    instrucciones = [
        "Las celdas AZULES SOBRE AMARILLO son tuyas: cámbialas y todo el libro recalcula.",
        "Las celdas en NEGRO son fórmulas. No las sobrescribas o rompes el modelo.",
        "El cap rate de mercado (hoja Inputs) es la palanca más sensible: mueve el NAV más que",
        "cualquier otro supuesto. Por eso la hoja Sensibilidad existe: úsala antes de creerte un NAV puntual.",
        "",
        "ADVERTENCIA: esto es una herramienta de análisis, no asesoría de inversión.",
        "Los datos marcados como derivados o reconstruidos no son de fuente primaria. Ver hoja Fuentes.",
    ]
    for i, texto in enumerate(instrucciones, start=6):
        ws[f"A{i}"] = texto
        ws[f"A{i}"].alignment = Alignment(wrap_text=False)

    fila = 6 + len(instrucciones) + 1
    ws[f"A{fila}"] = "GLOSARIO"
    ws[f"A{fila}"].font = FUENTE_SECCION
    fila += 1
    ws[f"A{fila}"], ws[f"B{fila}"] = "Término", "Qué significa y por qué importa"
    ws[f"A{fila}"].font = FUENTE_SECCION
    ws[f"B{fila}"].font = FUENTE_SECCION
    fila += 1
    for termino, definicion in GLOSARIO:
        ws[f"A{fila}"] = termino
        ws[f"B{fila}"] = definicion
        if definicion.startswith("TRAMPA"):
            ws[f"A{fila}"].font = FUENTE_TRAMPA
        fila += 1
    return ws


# --------------------------------------------------------------------------------------
# Hoja: Inputs
# --------------------------------------------------------------------------------------

# Mapa de nombre lógico -> celda, para que las demás hojas referencien sin magia.
CELDAS_INPUT: dict[str, str] = {
    "precio": "B4",
    "acciones_diluidas": "B5",
    "unidades_op": "B6",
    "cap_rate_mercado": "B7",
    "tasa_libre_riesgo": "B8",
    "tasa_udibono_real": "B9",
    "yield_adquisiciones": "B10",
    "peso_deuda_marginal": "B11",
    "deuda_total": "B14",
    "efectivo": "B15",
    "prestamos_por_cobrar": "B16",
    "inversiones_no_consolidadas": "B17",
    "goodwill": "B18",
    "ebitdare_ttm": "B19",
    "intereses_ttm": "B20",
    "dividendo_ttm": "B21",
    "noi_anualizado": "B22",
}


def _hoja_inputs(wb: Workbook, datos: DatosExportacion) -> Worksheet:
    ws = wb.create_sheet("Inputs")
    _ancho(ws, {"A": 42, "B": 18, "C": 80})
    ins = datos.insumos
    e = datos.escala

    ws["A1"] = "INPUTS DEL USUARIO"
    ws["A1"].font = FUENTE_TITULO
    ws["A2"] = "Azul sobre amarillo = editable. Cambia y el libro recalcula."
    ws["A2"].font = Font(italic=True, size=9, color="FF808080")

    escribir_etiqueta(ws, "A3", "Mercado y supuestos", seccion=True)
    escribir_etiqueta(ws, "A4", "Precio por acción (USD)")
    escribir_input(ws, "B4", ins.precio, FMT_MONEDA)
    escribir_etiqueta(ws, "A5", f"Acciones comunes diluidas ({datos.etiqueta_escala})")
    escribir_input(ws, "B5", ins.acciones_diluidas / e, FMT_MONEDA)
    escribir_etiqueta(ws, "A6", f"Unidades de Operating Partnership ({datos.etiqueta_escala})")
    escribir_input(ws, "B6", ins.unidades_op / e, FMT_MONEDA,
                   nota="Dilución oculta: se suman al conteo. Ver Léeme.")
    escribir_etiqueta(ws, "A7", "Cap rate de mercado para el NAV")
    escribir_input(ws, "B7", datos.cap_rate_mercado, FMT_PCT,
                   nota="LA PALANCA MÁS SENSIBLE DEL MODELO. Ver hoja Sensibilidad.")
    escribir_etiqueta(ws, "A8", "Tasa libre de riesgo (UST 10 años)")
    escribir_input(ws, "B8", datos.tasa_libre_riesgo, FMT_PCT)
    escribir_etiqueta(ws, "A9", "Udibono 10 años (tasa REAL)")
    escribir_input(ws, "B9", datos.tasa_udibono_real, FMT_PCT,
                   nota="El benchmark real del inversionista mexicano.")
    escribir_etiqueta(ws, "A10", "Yield de adquisiciones del emisor")
    escribir_input(ws, "B10", datos.yield_adquisiciones or 0.07, FMT_PCT)
    escribir_etiqueta(ws, "A11", "Peso de deuda en el capital marginal")
    escribir_input(ws, "B11", 0.35, FMT_PCT)

    escribir_etiqueta(ws, "A13", f"Balance ({datos.etiqueta_escala})", seccion=True)
    for etiqueta, clave, valor in (
        ("Deuda total", "deuda_total", ins.deuda_total),
        ("Efectivo", "efectivo", ins.efectivo),
        ("Préstamos por cobrar", "prestamos_por_cobrar", ins.prestamos_por_cobrar),
        ("Inversiones en no consolidadas", "inversiones_no_consolidadas", ins.inversiones_no_consolidadas),
        ("Goodwill (se EXCLUYE del NAV)", "goodwill", ins.goodwill),
        ("EBITDAre TTM", "ebitdare_ttm", ins.ebitdare_ttm or 0.0),
        ("Intereses TTM", "intereses_ttm", ins.intereses_ttm or 0.0),
    ):
        celda = CELDAS_INPUT[clave]
        fila = int(celda[1:])
        escribir_etiqueta(ws, f"A{fila}", etiqueta)
        escribir_input(ws, celda, (valor or 0.0) / e, FMT_MILES)

    escribir_etiqueta(ws, "A21", "Dividendo TTM por acción (USD)")
    escribir_input(ws, "B21", ins.dividendo_ttm_por_accion or 0.0, FMT_MONEDA)
    escribir_etiqueta(ws, "A22", f"NOI anualizado ({datos.etiqueta_escala})")
    escribir_input(ws, "B22", (ins.noi or 0.0) / e, FMT_MILES)

    escribir_etiqueta(ws, "A24", "Acciones totalmente diluidas (calculado)")
    escribir_formula(ws, "B24", f"{CELDAS_INPUT['acciones_diluidas']}+{CELDAS_INPUT['unidades_op']}", FMT_MONEDA)
    ws["C24"] = "Comunes más unidades de OP. Es el conteo que reparte el flujo de verdad."
    ws["C24"].font = Font(italic=True, size=9, color="FF808080")
    return ws


def _ref(clave: str) -> str:
    return f"Inputs!{CELDAS_INPUT[clave]}"


REF_ACCIONES_DILUIDAS = "Inputs!B24"


# --------------------------------------------------------------------------------------
# Hoja: Cascada del AFFO
# --------------------------------------------------------------------------------------


def _hoja_cascada(wb: Workbook, datos: DatosExportacion) -> Worksheet:
    ws = wb.create_sheet("Cascada AFFO")
    _ancho(ws, {"A": 52, "B": 8, "C": 18, "D": 18, "E": 90})
    comp = datos.componentes_cascada
    e = datos.escala

    ws["A1"] = "CASCADA: NOI → FFO → FFO NORMALIZADO → AFFO"
    ws["A1"].font = FUENTE_TITULO
    ws["A2"] = f"Cifras en {datos.etiqueta_escala}. Rojo = las tres trampas del AFFO."
    ws["A2"].font = Font(italic=True, size=9, color="FF808080")

    fila = 4
    for col, titulo in (("A", "Línea"), ("B", "Signo"), ("C", "Reportado"), ("D", "Aporte"), ("E", "Por qué")):
        escribir_etiqueta(ws, f"{col}{fila}", titulo, seccion=True)
    fila += 1

    bloques = {
        "NOI": ("NOI (Net Operating Income)", "noi"),
        "FFO": ("FFO (definición Nareit)", "ffo"),
        "FFO_NORMALIZADO": ("FFO Normalizado", "ffo_normalizado"),
        "AFFO": ("AFFO", "affo"),
    }
    subtotales: dict[str, str] = {}
    filas_bloque: dict[str, list[int]] = {b: [] for b in bloques}

    for linea in TODAS_LAS_LINEAS:
        if linea.signo == 0:  # los subtotales se escriben al cerrar cada bloque
            continue
        if linea.clave not in comp:
            continue
        escribir_etiqueta(ws, f"A{fila}", linea.etiqueta, trampa=linea.es_trampa)
        ws[f"B{fila}"] = "+" if linea.signo > 0 else "−"
        ws[f"B{fila}"].alignment = Alignment(horizontal="center")
        escribir_input(ws, f"C{fila}", float(comp[linea.clave]) / e, FMT_MILES)
        escribir_formula(ws, f"D{fila}", f"{linea.signo}*C{fila}", FMT_MILES)
        ws[f"E{fila}"] = linea.explicacion
        ws[f"E{fila}"].font = Font(italic=True, size=9, color="FF808080")
        filas_bloque[linea.bloque].append(fila)
        fila += 1

    # Subtotales encadenados
    fila += 1
    for bloque, (etiqueta, clave) in bloques.items():
        filas = filas_bloque[bloque]
        if not filas:
            continue
        escribir_etiqueta(ws, f"A{fila}", etiqueta, seccion=True)
        suma = "+".join(f"D{f}" for f in filas)
        if clave in ("noi", "ffo"):
            formula = suma
        elif clave == "ffo_normalizado":
            formula = f"{subtotales.get('ffo', '0')}+{suma}" if "ffo" in subtotales else suma
        else:  # affo
            base = subtotales.get("ffo_normalizado") or subtotales.get("ffo") or "0"
            formula = f"{base}+{suma}"
        escribir_formula(ws, f"D{fila}", formula, FMT_MILES)
        ws[f"D{fila}"].border = BORDE_TOTAL
        ws[f"D{fila}"].font = Font(bold=True)
        subtotales[clave] = f"D{fila}"
        fila += 1

    if "affo" in subtotales:
        escribir_etiqueta(ws, f"A{fila}", "AFFO por acción (diluida)", seccion=True)
        escribir_formula(ws, f"D{fila}", f"{subtotales['affo']}/{REF_ACCIONES_DILUIDAS}", FMT_MONEDA)
        subtotales["affo_por_accion"] = f"D{fila}"
        fila += 2

    # Contraste con la utilidad neta: el número que publican los sitios y está mal.
    if "utilidad_neta" in comp and "affo" in subtotales:
        escribir_etiqueta(ws, f"A{fila}", "CONTRASTE: por qué el AFFO y no la utilidad neta", seccion=True)
        fila += 1
        escribir_etiqueta(ws, f"A{fila}", "Razón AFFO / Utilidad neta")
        fila_un = next(
            (f for f in filas_bloque["FFO"] if ws[f"A{f}"].value == "Utilidad neta"), None
        )
        if fila_un:
            escribir_formula(ws, f"D{fila}", f"{subtotales['affo']}/C{fila_un}", FMT_VECES)
            ws[f"E{fila}"] = (
                "Realty Income Q2 2026: utilidad neta 0.37 por acción contra AFFO de 1.09, razón "
                "de 2.97x. El payout sobre utilidad neta da 222% y sobre AFFO da 73%."
            )
            ws[f"E{fila}"].font = Font(italic=True, size=9, color="FF808080")
    ws.freeze_panes = "A5"
    _guardar_referencias(ws, subtotales)
    return ws


_REFERENCIAS: dict[str, dict[str, str]] = {}


def _guardar_referencias(ws: Worksheet, refs: dict[str, str]) -> None:
    _REFERENCIAS[ws.title] = {k: f"'{ws.title}'!{v}" for k, v in refs.items()}


def _ref_cascada(clave: str) -> str:
    return _REFERENCIAS.get("Cascada AFFO", {}).get(clave, "0")


# --------------------------------------------------------------------------------------
# Hoja: Valuación
# --------------------------------------------------------------------------------------


def _hoja_valuacion(wb: Workbook, datos: DatosExportacion) -> Worksheet:
    ws = wb.create_sheet("Valuación")
    _ancho(ws, {"A": 46, "B": 18, "C": 92})

    ws["A1"] = "VALUACIÓN"
    ws["A1"].font = FUENTE_TITULO
    ws["A2"] = f"Cifras en {datos.etiqueta_escala}. Todo son fórmulas: cambia los Inputs y esto se mueve."
    ws["A2"].font = Font(italic=True, size=9, color="FF808080")

    affo_pa = _ref_cascada("affo_por_accion")
    ffo = _ref_cascada("ffo")

    f = 4
    escribir_etiqueta(ws, f"A{f}", "Capitalización y valor empresa", seccion=True)
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Capitalización de mercado")
    escribir_formula(ws, f"B{f}", f"{_ref('precio')}*{REF_ACCIONES_DILUIDAS}", FMT_MILES)
    ws[f"C{f}"] = "Precio por acciones TOTALMENTE diluidas, incluyendo unidades de OP."
    cap = f"B{f}"
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Deuda neta")
    escribir_formula(ws, f"B{f}", f"{_ref('deuda_total')}-{_ref('efectivo')}", FMT_MILES)
    deuda_neta = f"B{f}"
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Activos que NO generan renta inmobiliaria")
    escribir_formula(
        ws, f"B{f}", f"{_ref('prestamos_por_cobrar')}+{_ref('inversiones_no_consolidadas')}", FMT_MILES
    )
    ws[f"C{f}"] = (
        "Cartera de préstamos y coinversiones. Se RESTAN del EV: si no, el denominador se infla "
        "y el cap rate implícito sale sesgado a la baja."
    )
    sin_renta = f"B{f}"
    f += 1

    escribir_etiqueta(ws, f"A{f}", "EV ajustado")
    escribir_formula(ws, f"B{f}", f"{cap}+{deuda_neta}-{sin_renta}", FMT_MILES)
    ev = f"B{f}"
    f += 2

    escribir_etiqueta(ws, f"A{f}", "Múltiplos y rendimientos", seccion=True)
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Cap rate implícito")
    escribir_formula(ws, f"B{f}", f"IF({ev}=0,\"\",{_ref('noi_anualizado')}/{ev})", FMT_PCT)
    f += 1

    escribir_etiqueta(ws, f"A{f}", "AFFO yield")
    escribir_formula(ws, f"B{f}", f"IF({_ref('precio')}=0,\"\",{affo_pa}/{_ref('precio')})", FMT_PCT)
    affo_yield = f"B{f}"
    f += 1

    escribir_etiqueta(ws, f"A{f}", "P / AFFO")
    escribir_formula(ws, f"B{f}", f"IF({affo_pa}=0,\"\",{_ref('precio')}/{affo_pa})", FMT_VECES)
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Dividend yield")
    escribir_formula(ws, f"B{f}", f"IF({_ref('precio')}=0,\"\",{_ref('dividendo_ttm')}/{_ref('precio')})", FMT_PCT)
    f += 2

    escribir_etiqueta(ws, f"A{f}", "Cobertura del dividendo", seccion=True)
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Payout sobre AFFO")
    escribir_formula(ws, f"B{f}", f"IF({affo_pa}=0,\"\",{_ref('dividendo_ttm')}/{affo_pa})", FMT_PCT)
    ws[f"C{f}"] = "La ÚNICA cobertura que significa algo. Umbral de la Puerta 1: menor a 90%."
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Payout sobre FFO")
    escribir_formula(
        ws, f"B{f}",
        f"IF({ffo}=0,\"\",{_ref('dividendo_ttm')}/({ffo}/{REF_ACCIONES_DILUIDAS}))", FMT_PCT,
    )
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Payout sobre utilidad neta (para contrastar)")
    fila_un = _fila_utilidad_neta(wb)
    if fila_un:
        un = f"'Cascada AFFO'!C{fila_un}"
        escribir_formula(
            ws, f"B{f}", f"IF({un}=0,\"\",{_ref('dividendo_ttm')}/({un}/{REF_ACCIONES_DILUIDAS}))", FMT_PCT
        )
    ws[f"C{f}"] = (
        "Este es el número que publican los sitios financieros y está mal. Se muestra solo para "
        "que veas el tamaño del error."
    )
    ws[f"C{f}"].font = FUENTE_TRAMPA
    f += 2

    escribir_etiqueta(ws, f"A{f}", "Balance", seccion=True)
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Deuda neta / EBITDAre")
    escribir_formula(
        ws, f"B{f}", f"IF({_ref('ebitdare_ttm')}=0,\"\",{deuda_neta}/{_ref('ebitdare_ttm')})", FMT_VECES
    )
    ws[f"C{f}"] = "Umbral de la Puerta 1 y de la Puerta 3: 6.5x."
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Costo implícito de la deuda")
    escribir_formula(
        ws, f"B{f}", f"IF({_ref('deuda_total')}=0,\"\",{_ref('intereses_ttm')}/{_ref('deuda_total')})", FMT_PCT
    )
    costo_deuda = f"B{f}"
    f += 2

    escribir_etiqueta(ws, f"A{f}", "Motor de valor", seccion=True)
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Costo marginal de capital")
    escribir_formula(
        ws, f"B{f}",
        f"{_ref('peso_deuda_marginal')}*{costo_deuda}+(1-{_ref('peso_deuda_marginal')})*{affo_yield}",
        FMT_PCT,
    )
    ws[f"C{f}"] = (
        "El costo del capital accionario de un REIT es su AFFO yield: emitir una acción a 6% "
        "de AFFO yield cuesta 6%."
    )
    cmc = f"B{f}"
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Spread de inversión")
    escribir_formula(ws, f"B{f}", f"{_ref('yield_adquisiciones')}-{cmc}", FMT_PCT)
    ws[f"C{f}"] = (
        "Yield de adquisiciones menos costo marginal de capital. Negativo = cada compra destruye "
        "valor por acción aunque suba el AFFO agregado."
    )
    spread = f"B{f}"
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Spread de inversión (en bps)")
    escribir_bps(ws, f"B{f}", spread)
    ws[f"C{f}"] = (
        "OJO CON LAS UNIDADES: el formato \"bps\" NO escala. La celda contiene "
        "=ROUND(valor*10000,0) para que 0.0409 se muestre como 409 bps y no como 0 bps."
    )
    f += 2

    escribir_etiqueta(ws, f"A{f}", "NAV", seccion=True)
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Valor de los inmuebles (NOI / cap rate)")
    escribir_formula(
        ws, f"B{f}", f"IF({_ref('cap_rate_mercado')}=0,\"\",{_ref('noi_anualizado')}/{_ref('cap_rate_mercado')})", FMT_MILES
    )
    valor_inm = f"B{f}"
    f += 1

    escribir_etiqueta(ws, f"A{f}", "NAV total")
    escribir_formula(
        ws, f"B{f}",
        f"{valor_inm}+{_ref('efectivo')}+{_ref('prestamos_por_cobrar')}"
        f"+{_ref('inversiones_no_consolidadas')}-{_ref('deuda_total')}",
        FMT_MILES,
    )
    ws[f"C{f}"] = "El GOODWILL se excluye deliberadamente: no genera renta."
    ws[f"C{f}"].font = FUENTE_TRAMPA
    nav = f"B{f}"
    f += 1

    escribir_etiqueta(ws, f"A{f}", "NAV por acción")
    escribir_formula(ws, f"B{f}", f"{nav}/{REF_ACCIONES_DILUIDAS}", FMT_MONEDA)
    nav_pa = f"B{f}"
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Premio (+) o descuento (−) a NAV")
    escribir_formula(ws, f"B{f}", f"IF({nav_pa}=0,\"\",{_ref('precio')}/{nav_pa}-1)", FMT_PCT1)
    f += 2

    escribir_etiqueta(ws, f"A{f}", "Prima y benchmark mexicano", seccion=True)
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Prima sobre la tasa libre de riesgo")
    escribir_formula(ws, f"B{f}", f"{affo_yield}-{_ref('tasa_libre_riesgo')}", FMT_PCT)
    prima = f"B{f}"
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Prima (en bps)")
    escribir_bps(ws, f"B{f}", prima)
    ws[f"C{f}"] = (
        "Compara esta prima contra su PROPIO percentil histórico, nunca contra el nivel de "
        "yield de otro emisor (P4)."
    )
    f += 1

    escribir_etiqueta(ws, f"A{f}", "AFFO yield neto de impuestos mexicanos")
    escribir_formula(ws, f"B{f}", f"{affo_yield}*0.8", FMT_PCT)
    ws[f"C{f}"] = (
        "Retención de 10% en EE. UU. con W-8BEN más 10% adicional en México: ~20% combinado. "
        "Confirma la tasa efectiva con tu casa de bolsa."
    )
    yield_neto = f"B{f}"
    f += 1

    escribir_etiqueta(ws, f"A{f}", "Brecha contra el Udibono real")
    escribir_formula(ws, f"B{f}", f"{yield_neto}-{_ref('tasa_udibono_real')}", FMT_PCT)
    ws[f"C{f}"] = (
        "Si es negativa, el activo SIN riesgo paga más que el activo CON riesgo. La tesis "
        "tendría que ser el crecimiento futuro del flujo, no el rendimiento de hoy."
    )
    f += 1
    escribir_etiqueta(ws, f"A{f}", "Brecha contra el Udibono (en bps)")
    escribir_bps(ws, f"B{f}", f"B{f - 1}")

    for fila in range(4, f + 1):
        c = ws[f"C{fila}"]
        if c.value and c.font.color is None:
            c.font = Font(italic=True, size=9, color="FF808080")
    ws.freeze_panes = "A4"
    return ws


def _fila_utilidad_neta(wb: Workbook) -> int | None:
    ws = wb["Cascada AFFO"]
    for fila in range(1, ws.max_row + 1):
        if ws[f"A{fila}"].value == "Utilidad neta":
            return fila
    return None


# --------------------------------------------------------------------------------------
# Hoja: Sensibilidad
# --------------------------------------------------------------------------------------


def _hoja_sensibilidad(wb: Workbook, datos: DatosExportacion) -> Worksheet:
    ws = wb.create_sheet("Sensibilidad")
    _ancho(ws, {"A": 16, "B": 20, "C": 20, "D": 22, "E": 60})

    ws["A1"] = "SENSIBILIDAD DEL NAV AL CAP RATE"
    ws["A1"].font = FUENTE_TITULO
    ws["A2"] = (
        "El cap rate es la palanca más sensible del modelo. Mira esta tabla ANTES de creerte "
        "un NAV puntual: 50 puntos base cambian el NAV más que casi cualquier otro supuesto."
    )
    ws["A2"].font = Font(italic=True, size=9, color="FF808080")

    fila = 4
    for col, titulo in (
        ("A", "Cap rate"),
        ("B", "Valor inmuebles"),
        ("C", "NAV total"),
        ("D", "NAV por acción"),
        ("E", "Premio (+) / descuento (−) del precio"),
    ):
        escribir_etiqueta(ws, f"{col}{fila}", titulo, seccion=True)
    fila += 1

    cap_rate = 0.055
    while cap_rate <= 0.08001:
        escribir_input(ws, f"A{fila}", round(cap_rate, 4), FMT_PCT)
        escribir_formula(ws, f"B{fila}", f"IF(A{fila}=0,\"\",{_ref('noi_anualizado')}/A{fila})", FMT_MILES)
        escribir_formula(
            ws, f"C{fila}",
            f"B{fila}+{_ref('efectivo')}+{_ref('prestamos_por_cobrar')}"
            f"+{_ref('inversiones_no_consolidadas')}-{_ref('deuda_total')}",
            FMT_MILES,
        )
        escribir_formula(ws, f"D{fila}", f"C{fila}/{REF_ACCIONES_DILUIDAS}", FMT_MONEDA)
        escribir_formula(ws, f"E{fila}", f"IF(D{fila}=0,\"\",{_ref('precio')}/D{fila}-1)", FMT_PCT1)
        cap_rate += 0.0025
        fila += 1

    fila += 1
    ws[f"A{fila}"] = (
        "La fila que corresponde al cap rate de la hoja Inputs es la que alimenta la hoja de "
        "Valuación. Las demás muestran qué pasaría si el mercado repreciara el portafolio."
    )
    ws[f"A{fila}"].font = Font(italic=True, size=9, color="FF808080")
    ws.freeze_panes = "A5"
    return ws


# --------------------------------------------------------------------------------------
# Hoja: Fuentes
# --------------------------------------------------------------------------------------


def _hoja_fuentes(wb: Workbook, datos: DatosExportacion) -> Worksheet:
    ws = wb.create_sheet("Fuentes")
    _ancho(ws, {"A": 28, "B": 16, "C": 18, "D": 18, "E": 22, "F": 80})

    ws["A1"] = "FUENTES Y PROCEDENCIA DE CADA DATO"
    ws["A1"].font = FUENTE_TITULO
    ws["A2"] = (
        "Primario = viene directo de la SEC o del banco central. Derivado o reconstruido = "
        "calculado por el modelo. La distinción importa: un dato reconstruido hereda el error "
        "de sus componentes."
    )
    ws["A2"].font = Font(italic=True, size=9, color="FF808080")

    fila = 4
    encabezados = ("Concepto", "Periodo", "Fecha del dato", "Fecha de publicación", "Fuente", "URL del filing")
    for i, titulo in enumerate(encabezados):
        escribir_etiqueta(ws, f"{get_column_letter(i + 1)}{fila}", titulo, seccion=True)
    fila += 1

    for f_ in (datos.fuentes or []):
        ws[f"A{fila}"] = f_.get("concepto", "")
        ws[f"B{fila}"] = f_.get("periodo_tipo", "")
        ws[f"C{fila}"] = str(f_.get("fecha_dato", ""))
        ws[f"D{fila}"] = str(f_.get("fecha_publicacion", ""))
        ws[f"E{fila}"] = f_.get("fuente", "")
        ws[f"F{fila}"] = f_.get("url_filing", "")
        if f_.get("url_filing"):
            ws[f"F{fila}"].font = FUENTE_ENLACE
        if not f_.get("es_primario", False):
            ws[f"E{fila}"].font = FUENTE_TRAMPA
        fila += 1

    fila += 1
    ws[f"A{fila}"] = f"Libro generado el {dt.datetime.now():%Y-%m-%d %H:%M} con corte al {datos.fecha_corte}."
    fila += 1
    ws[f"A{fila}"] = (
        "Esto es una herramienta de análisis, no asesoría de inversión."
    )
    ws[f"A{fila}"].font = FUENTE_TRAMPA
    ws.freeze_panes = "A5"
    return ws


# --------------------------------------------------------------------------------------
# Validación del libro generado
# --------------------------------------------------------------------------------------

ERRORES_EXCEL = ("#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#N/A", "#NULL!", "#NUM!", "Err:")


def buscar_errores(ruta: Path | str) -> list[dict]:
    """Recorre el libro recalculado y devuelve toda celda con error de fórmula."""
    from openpyxl import load_workbook

    wb = load_workbook(ruta, data_only=True)
    errores = []
    for ws in wb.worksheets:
        for fila in ws.iter_rows():
            for celda in fila:
                v = celda.value
                if isinstance(v, str) and any(e in v for e in ERRORES_EXCEL):
                    errores.append({"hoja": ws.title, "celda": celda.coordinate, "valor": v})
    return errores


def leer_valores(ruta: Path | str) -> dict[str, dict[str, object]]:
    """Lee los valores calculados del libro. Requiere que se haya recalculado."""
    from openpyxl import load_workbook

    wb = load_workbook(ruta, data_only=True)
    return {
        ws.title: {c.coordinate: c.value for f in ws.iter_rows() for c in f if c.value is not None}
        for ws in wb.worksheets
    }


def celdas_con_formato_bps(ruta: Path | str) -> list[dict]:
    """Localiza las celdas con formato de puntos base y su valor calculado.

    Existe para que la prueba de unidades pueda verificar que una prima de 409 bps
    aparece como 409 y no como 0.
    """
    from openpyxl import load_workbook

    wb_f = load_workbook(ruta, data_only=False)
    wb_v = load_workbook(ruta, data_only=True)
    salida = []
    for ws in wb_f.worksheets:
        hoja_v = wb_v[ws.title]
        for fila in ws.iter_rows():
            for celda in fila:
                if celda.number_format == FMT_BPS:
                    salida.append(
                        {
                            "hoja": ws.title,
                            "celda": celda.coordinate,
                            "formula": celda.value,
                            "valor": hoja_v[celda.coordinate].value,
                        }
                    )
    return salida


def dataframe_a_hoja(wb: Workbook, nombre: str, df: pd.DataFrame) -> Worksheet:
    """Vuelca un DataFrame como hoja de apoyo (valores, no fórmulas)."""
    ws = wb.create_sheet(nombre[:31])
    for j, col in enumerate(df.columns, start=1):
        c = ws.cell(row=1, column=j, value=str(col))
        c.font = FUENTE_SECCION
        c.fill = RELLENO_SECCION
    for i, (_, fila) in enumerate(df.iterrows(), start=2):
        for j, col in enumerate(df.columns, start=1):
            valor = fila[col]
            ws.cell(row=i, column=j, value=None if pd.isna(valor) else valor)
    ws.freeze_panes = "A2"
    return ws
