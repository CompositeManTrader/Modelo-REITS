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
from dataclasses import dataclass, field
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
    # Las tres vistas de los estados. Opcional a propósito: un libro sin ellas
    # sigue siendo válido —es el que existía antes— y las pruebas que solo miran
    # el modelo no tienen que armar nueve tablas para correr.
    estados: EstadosParaLibro | None = None


def exportar(datos: DatosExportacion, ruta: Path | str) -> Path:
    """Genera el libro completo con fórmulas vivas y lo guarda.

    Cuando ``datos.estados`` viene, el libro deja de ser dos cosas pegadas: los
    estados entran como hojas y los insumos que salen de ellos dejan de ser un
    número escrito para volverse una fórmula que apunta a su renglón. Cambiar la
    deuda en el balance mueve el apalancamiento, el LTV y el NAV.
    """
    wb = Workbook()
    wb.remove(wb.active)

    _hoja_leeme(wb, datos)
    ws_inputs = _hoja_inputs(wb, datos)
    if datos.estados is not None and datos.estados.hay_propia:
        # El volcado va ANTES del cableado: las fórmulas se escriben apuntando a
        # hojas que ya existen, y si alguna vista viene vacía el cableado la ve
        # vacía y deja el input como estaba, en vez de dejar una referencia rota.
        _volcar_estados(wb, datos.estados)
        _cablear_inputs(ws_inputs, datos.estados, datos.escala)
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




# --------------------------------------------------------------------------------------
# Las tres vistas de los estados, y su cableado al modelo
# --------------------------------------------------------------------------------------
#
# Antes eran dos libros: uno con los estados y otro con el modelo de valuación. Se
# podían leer los dos, pero cambiar un renglón del balance no movía nada del
# modelo, así que el estado era una lámina y no un insumo. Aquí son uno solo, y
# los insumos que SALEN de un estado dejan de ser un número escrito para volverse
# una fórmula que apunta a su renglón.
#
# Lo que NO se cableó, a propósito: el precio, el cap rate, las tasas, el yield de
# adquisiciones y el peso de la deuda marginal siguen en azul sobre amarillo. No
# salen de un estado financiero: son supuestos, y volverlos fórmula habría
# escondido la única parte del modelo que de verdad es del usuario.

# Nombres cortos a propósito: Excel corta el nombre de una hoja en 31 caracteres,
# y dos hojas truncadas al mismo prefijo se vuelven indistinguibles y rompen
# cualquier fórmula que las referencie por nombre.
_HOJAS = {
    "resultados": "Resultados",
    "balance": "Balance",
    "flujo": "Flujo",
    "estado_resultados": "Resultados",
    "flujo_efectivo": "Flujo",
}

HOJA_PROPIA = {
    "estado_resultados": "Propia Resultados",
    "balance": "Propia Balance",
    "flujo_efectivo": "Propia Flujo",
}

# Cuántos trimestres son un TTM. Cuatro, y el libro lo dice en la fórmula en vez
# de traer el resultado ya sumado: un TTM pegado como número no se puede auditar.
TRIMESTRES_TTM = 4


@dataclass
class EstadosParaLibro:
    """Las tres vistas ya armadas, listas para volcarse y para ser referenciadas."""

    propia: dict[str, pd.DataFrame]
    bloomberg: dict[str, pd.DataFrame]
    reportados: dict[str, pd.DataFrame]
    ratios: pd.DataFrame
    # El AFFO, el FFO y el AFFO por acción no son renglón de ningún estado: viven
    # en el Exhibit 99.1 del 8-K. Van aparte porque tres ratios los necesitan y
    # sin ellos esos tres quedaban vacíos en el libro y con número en la
    # pantalla, que es la peor de las dos formas de estar mal.
    no_gaap: pd.DataFrame = field(default_factory=pd.DataFrame)
    periodo_tipo: str = "Q"

    @property
    def hay_propia(self) -> bool:
        return any(not t.empty for t in self.propia.values())


def _hoja_ref(nombre: str) -> str:
    """El nombre de una hoja como se cita en una fórmula."""
    return f"'{nombre}'" if " " in nombre or "-" in nombre else nombre


def _columnas_de_periodo(tabla: pd.DataFrame) -> list[str]:
    """Las letras de columna de los periodos, en el orden en que se escriben.

    La columna A es «Renglón»; los periodos empiezan en B. El orden es el del
    DataFrame, que viene del más viejo al más reciente, así que la ÚLTIMA es el
    periodo vigente.
    """
    return [get_column_letter(i) for i in range(2, len(tabla.columns) + 1)]


def _referencia(hoja: str, etiqueta: str, columna: str) -> str:
    """Una celda de un estado, buscada POR SU ETIQUETA y no por su número de fila.

    Es la decisión que hace que el cableado sobreviva a la próxima exportación.
    Un estado financiero no tiene una forma fija: si la emisora empieza a reportar
    un renglón que antes no tenía, todo lo que va debajo se recorre una fila. Con
    una referencia dura —``'Propia Balance'!G14``— la fórmula sigue apuntando a la
    fila 14, que ahora es otra partida, y el modelo cambia de insumo sin que nada
    lo diga: ni un error, ni una celda vacía, solo un número distinto.

    ``INDEX``/``MATCH`` sobre la etiqueta apunta al RENGLÓN, no al lugar. Si el
    renglón desaparece la fórmula da ``#N/A``, que es exactamente lo que se
    quiere: un error visible es infinitamente mejor que un insumo equivocado.
    """
    ref = _hoja_ref(hoja)
    etiqueta_segura = etiqueta.replace('"', '""')
    return f'INDEX({ref}!{columna}:{columna},MATCH("{etiqueta_segura}",{ref}!A:A,0))'


def _suma_ttm(hoja: str, etiqueta: str, columnas: list[str]) -> str:
    """La suma de los últimos cuatro trimestres de un renglón, por su etiqueta."""
    ultimas = columnas[-TRIMESTRES_TTM:]
    partes = [_referencia(hoja, etiqueta, c) for c in ultimas]
    return "+".join(partes)


def _formula_ebitdare(hoja_res: str, columnas: list[str], escala: float) -> str:
    """El EBITDAre TTM armado renglón por renglón, con su guarda.

    La guarda existe por la prueba 36. En Python, sumar con la depreciación
    ausente daba un EBITDAre que no lo era —en Welltower, 608.7 en vez de
    1,320.7— y de ahí un apalancamiento de 3.84x cuando el real es 3.27x. En
    Excel el riesgo es peor, porque ``SUM`` de una celda vacía **es cero** y no
    avisa: el mismo error, una capa más afuera y sin traza en el código.

    Por eso la fórmula cuenta primero cuántos de los cuatro trimestres traen
    depreciación. Si falta alguno devuelve vacío, que es lo que la pantalla
    muestra como SIN DATOS, en vez de un número más chico y creíble.
    """
    from src.ingesta.estados import LINEA_POR_CLAVE

    def eti(clave: str) -> str:
        return LINEA_POR_CLAVE[clave].etiqueta

    ultimas = columnas[-TRIMESTRES_TTM:]
    sumandos = []
    for columna in ultimas:
        piezas = [
            _referencia(hoja_res, eti("utilidad_neta"), columna),
            _referencia(hoja_res, eti("gasto_intereses"), columna),
            f'N({_referencia(hoja_res, eti("impuestos"), columna)})',
            _referencia(hoja_res, eti("depreciacion_amortizacion"), columna),
            f'N({_referencia(hoja_res, eti("deterioro"), columna)})',
            f'-N({_referencia(hoja_res, eti("ganancia_venta_inmuebles"), columna)})',
        ]
        sumandos.append("(" + "+".join(piezas).replace("+-", "-") + ")")
    cuenta = "+".join(
        f'N(ISNUMBER({_referencia(hoja_res, eti("depreciacion_amortizacion"), c)}))'
        for c in ultimas
    )
    suma = "+".join(sumandos)
    return f"=IF(({cuenta})<{len(ultimas)},\"\",({suma})/{escala:.0f})"


def _formula_deuda(hoja_bal: str, tabla: pd.DataFrame, columna: str, escala: float) -> str:
    """La deuda como la calcula el modelo: los TRAMOS, no el total declarado.

    Este renglón es el que costó el error. Cablearlo al renglón «Deuda total» del
    balance parecía lo obvio y revertía en silencio la corrección del PR #22: en
    Realty Income el total declarado son 25,091.6 millones —viene de una sola
    etiqueta, que son sus notas senior— mientras que sus cuatro tramos suman
    30,651.7. Con el cableado ingenuo el libro devolvía la cifra vieja y el
    apalancamiento bajaba de 5.68x a 4.63x, sin que nada lo dijera.

    Lo cazó recalcular el libro con LibreOffice y compararlo contra el modelo. Un
    cableado que no se recalcula no está verificado: está escrito.

    Así que la fórmula reproduce la regla del servicio —``TRAMOS_DE_DEUDA`` con
    ``MARGEN_DE_TRAMOS``—: gana la suma de los tramos cuando le saca al total
    declarado más que el margen, y el resultado se topa con los pasivos totales,
    porque la deuda no puede exceder lo que el balance declara deber.
    """
    from src.ingesta.estados import LINEA_POR_CLAVE
    from src.servicio import MARGEN_DE_TRAMOS, TRAMOS_DE_DEUDA

    presentes = set(tabla["Renglón"])

    def ref(clave: str) -> str | None:
        etiqueta = LINEA_POR_CLAVE[clave].etiqueta if clave in LINEA_POR_CLAVE else None
        if etiqueta is None or etiqueta not in presentes:
            return None
        return f"N({_referencia(hoja_bal, etiqueta, columna)})"

    tramos = [r for r in (ref(c) for c in TRAMOS_DE_DEUDA) if r]
    declarado = ref("deuda_total")
    if not tramos:
        return f'=IFERROR({declarado}/{escala:.0f},"")' if declarado else ""
    suma = "+".join(tramos)
    if declarado is None:
        bruto = f"({suma})"
    else:
        # La suma gana solo si supera al declarado por MÁS que el margen. Igual
        # que en el servicio: una diferencia de redondeo no cambia la fuente.
        bruto = f"IF(({suma})>{declarado}*{1 + MARGEN_DE_TRAMOS},({suma}),{declarado})"
    pasivos = ref("pasivos_totales")
    if pasivos:
        bruto = f"IF({pasivos}>0,MIN({bruto},{pasivos}),{bruto})"
    return f'=IFERROR({bruto}/{escala:.0f},"")'


# Los insumos que SÍ salen de un estado, con el renglón del catálogo del que
# salen. Lo que no está aquí sigue siendo un input del usuario. `deuda_total` no
# está: no es un renglón, es una regla — ver `_formula_deuda`.
CABLEADOS_DE_BALANCE: tuple[tuple[str, str], ...] = (
    ("efectivo", "efectivo"),
    ("prestamos_por_cobrar", "prestamos_por_cobrar"),
    ("inversiones_no_consolidadas", "inversiones_no_consolidadas"),
    ("goodwill", "goodwill"),
)
CABLEADOS_TTM: tuple[tuple[str, str], ...] = (
    ("intereses_ttm", "gasto_intereses"),
)


def _cablear_inputs(ws: Worksheet, estados: EstadosParaLibro, escala: float) -> list[str]:
    """Sustituye por fórmulas los inputs que salen de un estado. Devuelve cuáles.

    Sigue siendo una celda editable: quien quiera probar otro supuesto escribe
    encima y Excel reemplaza la fórmula, igual que siempre. Lo que cambia es el
    punto de partida —deja de ser una foto— y que el origen queda a la vista.
    """
    from src.ingesta.estados import LINEA_POR_CLAVE

    cableados: list[str] = []
    balance = estados.propia.get("balance", pd.DataFrame())
    resultados = estados.propia.get("estado_resultados", pd.DataFrame())

    if not balance.empty:
        columnas = _columnas_de_periodo(balance)
        if columnas:
            ultima = columnas[-1]
            formula_deuda = _formula_deuda(
                HOJA_PROPIA["balance"], balance, ultima, escala
            )
            if formula_deuda and "deuda_total" in CELDAS_INPUT:
                celda = ws[CELDAS_INPUT["deuda_total"]]
                celda.value = formula_deuda
                celda.font = FUENTE_ENLACE
                celda.fill = PatternFill(fill_type=None)
                celda.number_format = FMT_MILES
                ws[_desplazar(CELDAS_INPUT["deuda_total"], columnas=1)] = (
                    "Suma de los TRAMOS, no el renglón «Deuda total»: en varias "
                    "emisoras ese renglón trae una sola etiqueta y subestima. Ver "
                    "TRAMOS_DE_DEUDA en el servicio."
                )
                ws[_desplazar(CELDAS_INPUT["deuda_total"], columnas=1)].font = Font(
                    italic=True, size=9, color=VERDE
                )
                cableados.append("deuda_total")
            for clave_input, clave_linea in CABLEADOS_DE_BALANCE:
                if clave_input not in CELDAS_INPUT or clave_linea not in LINEA_POR_CLAVE:
                    continue
                etiqueta = LINEA_POR_CLAVE[clave_linea].etiqueta
                if etiqueta not in set(balance["Renglón"]):
                    continue
                celda = ws[CELDAS_INPUT[clave_input]]
                celda.value = (
                    f"=IFERROR({_referencia(HOJA_PROPIA['balance'], etiqueta, ultima)}"
                    f"/{escala:.0f},\"\")"
                )
                celda.font = FUENTE_ENLACE
                celda.fill = PatternFill(fill_type=None)
                celda.number_format = FMT_MILES
                cableados.append(clave_input)

    if not resultados.empty:
        columnas = _columnas_de_periodo(resultados)
        etiquetas = set(resultados["Renglón"])
        if len(columnas) >= TRIMESTRES_TTM:
            for clave_input, clave_linea in CABLEADOS_TTM:
                etiqueta = LINEA_POR_CLAVE[clave_linea].etiqueta
                if clave_input not in CELDAS_INPUT or etiqueta not in etiquetas:
                    continue
                celda = ws[CELDAS_INPUT[clave_input]]
                suma = _suma_ttm(HOJA_PROPIA["estado_resultados"], etiqueta, columnas)
                celda.value = f'=IFERROR(({suma})/{escala:.0f},"")'
                celda.font = FUENTE_ENLACE
                celda.fill = PatternFill(fill_type=None)
                celda.number_format = FMT_MILES
                cableados.append(clave_input)

            necesarias = {
                LINEA_POR_CLAVE[c].etiqueta for c in
                ("utilidad_neta", "gasto_intereses", "depreciacion_amortizacion")
            }
            if necesarias <= etiquetas and "ebitdare_ttm" in CELDAS_INPUT:
                celda = ws[CELDAS_INPUT["ebitdare_ttm"]]
                celda.value = _formula_ebitdare(
                    HOJA_PROPIA["estado_resultados"], columnas, escala
                )
                celda.font = FUENTE_ENLACE
                celda.fill = PatternFill(fill_type=None)
                celda.number_format = FMT_MILES
                cableados.append("ebitdare_ttm")

    if cableados:
        ws["C2"] = (
            "Verde = sale de un estado financiero de este libro, por fórmula. "
            "Escribe encima si quieres probar otro supuesto."
        )
        ws["C2"].font = Font(italic=True, size=9, color=VERDE)
    return cableados


def _volcar_estados(wb: Workbook, estados: EstadosParaLibro) -> None:
    """Las nueve hojas de estados más los ratios, en el orden de las tres vistas."""
    for clave, tabla in estados.propia.items():
        if not tabla.empty:
            dataframe_a_hoja(wb, HOJA_PROPIA[clave], tabla)
    for clave, tabla in estados.bloomberg.items():
        if not tabla.empty:
            # Con `_hoja_bloomberg` y no con el volcado genérico: los ratios y los
            # subtotales entran como FÓRMULA que apunta a los renglones de arriba,
            # no como número pegado. El campo de Bloomberg, el ajuste y la nota
            # viajan en columnas al final: quien abra el libro fuera de la pantalla
            # no tiene otra forma de saber qué ajuste se aplicó.
            _hoja_bloomberg(wb, f"BBG {_HOJAS[clave]}", clave, tabla)
    for clave, tabla in estados.reportados.items():
        if not tabla.empty:
            dataframe_a_hoja(wb, f"Reportado {_HOJAS[clave]}", tabla)
    if not estados.ratios.empty:
        _hoja_ratios(wb, estados)


def estados_para_libro(
    repo,
    ticker: str,
    *,
    asof: dt.date,
    periodo_tipo: str = "Q",
    n_periodos: int | None = None,
) -> EstadosParaLibro:
    """Arma las tres vistas una sola vez, para el libro y para el cableado."""
    from src.ingesta import reportados as mod_reportados
    from src.ingesta.estados import ESTADOS as ESTADOS_DEL_CATALOGO
    from src.modelo import bloomberg as mod_bloomberg
    from src.servicio import (
        estado_financiero,
        estados_reportados,
        insumos_no_gaap,
        panel_de_conceptos,
        ratios_propios,
    )

    panel = panel_de_conceptos(
        repo, ticker, asof=asof, periodo_tipo=periodo_tipo, n_periodos=n_periodos
    )
    formulario = "10-K" if periodo_tipo == "FY" else "10-Q"
    return EstadosParaLibro(
        propia={
            estado: estado_financiero(
                repo, ticker, estado, asof=asof, periodo_tipo=periodo_tipo,
                n_periodos=n_periodos,
            )
            for estado in ESTADOS_DEL_CATALOGO
        },
        bloomberg={
            estado: mod_bloomberg.armar(panel, estado, n_periodos=n_periodos)
            for estado in mod_bloomberg.ESTADOS
        },
        reportados={
            estado: estados_reportados(ticker, estado, asof=asof, formulario=formulario)
            for estado in mod_reportados.ESTADOS
        },
        ratios=ratios_propios(panel),
        no_gaap=insumos_no_gaap(panel),
        periodo_tipo=periodo_tipo,
    )


def libro_de_estados(
    repo,
    ticker: str,
    *,
    asof: dt.date,
    periodo_tipo: str = "Q",
    n_periodos: int | None = None,
) -> bytes:
    """Solo los estados, en BYTES, para el botón de descarga de la pantalla.

    Devuelve bytes y no una ruta porque en Streamlit Cloud el disco es efímero:
    escribir un archivo para leerlo enseguida es un rodeo que además se puede
    quedar a medias. El libro COMPLETO —con el modelo cableado— lo arma
    ``exportar``.
    """
    import io

    estados = estados_para_libro(
        repo, ticker, asof=asof, periodo_tipo=periodo_tipo, n_periodos=n_periodos
    )
    wb = Workbook()
    wb.remove(wb.active)
    _volcar_estados(wb, estados)
    if not wb.sheetnames:
        dataframe_a_hoja(
            wb, "Sin datos",
            pd.DataFrame([{"Aviso": f"No hay estados de {ticker} al corte del {asof}."}]),
        )
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# --------------------------------------------------------------------------------------
# Las hojas de Bloomberg, con fórmulas vivas
# --------------------------------------------------------------------------------------
#
# El molde declara cada ratio y cada subtotal como una `Formula` sobre OTROS
# renglones —«FAD Payout Ratio = Dividend Per Share ÷ FAD Per Diluted Share»—.
# La pantalla la evalúa en Python; aquí se traduce a celdas. Es el mismo cálculo
# leído dos veces, no escrito dos veces: cambiar el dividendo en el estado mueve
# el payout, y cambiar la deuda mueve el apalancamiento.
#
# Los renglones que NO son fórmula —los que salen directo de un renglón nuestro—
# van como valor. Son el dato; no hay nada vivo que poner ahí.

FMT_POR_FORMATO = {
    "monto": FMT_MILES,
    "por_accion": FMT_MONEDA,
    "pct": FMT_PCT,
    "veces": FMT_VECES,
    "conteo": FMT_MILES,
}


def _fila_por_etiqueta(plantilla) -> dict[str, int]:
    """Etiqueta → número de fila en la hoja, para la PRIMERA que rinde cifra.

    El molde repite nombres: «Cash From Operating Activities» es el título de la
    sección y también su total. Una fórmula tiene que apuntar al renglón que
    trae el número, no al encabezado que lo precede.
    """
    salida: dict[str, int] = {}
    for i, linea in enumerate(plantilla, start=2):
        if linea.rinde_cifra and linea.etiqueta not in salida:
            salida[linea.etiqueta] = i
    return salida


def _terminos_excel(
    terminos, filas: dict[str, int], columna: str
) -> tuple[str, str] | None:
    """Los sumandos de una `Formula`: (expresión, celdas para contar).

    Devuelve las dos cosas porque hacen falta las dos. `N()` de una celda vacía
    **es cero**, así que una suma de puros vacíos da 0 y no se distingue de un
    cero real: «Total Real Estate Investments = 0» se lee como "no tienen
    inmuebles", no como "no lo sabemos". La segunda pieza es la lista de celdas
    que el `COUNT` de arriba usa para decidir si hay algo que sumar.
    """
    partes, celdas = [], []
    for signo, etiqueta in terminos:
        fila = filas.get(etiqueta)
        if fila is None:
            return None
        partes.append(f"{'-' if signo < 0 else '+'}N({columna}{fila})")
        celdas.append(f"{columna}{fila}")
    if not partes:
        return None
    expresion = "".join(partes)
    return (expresion[1:] if expresion.startswith("+") else expresion, ",".join(celdas))


def _formula_excel(
    formula, filas: dict[str, int], columnas: list[str], indice: int,
    columna_previa: str | None = None,
) -> str | None:
    """Traduce una `Formula` del molde a una fórmula de Excel para una columna.

    Devuelve ``None`` cuando algún renglón que la fórmula necesita no existe en
    el molde: es preferible dejar la celda vacía a escribir una referencia rota.
    """
    columna = columnas[indice]
    if formula.yoy:
        fila = filas.get(formula.yoy)
        # El periodo de hace un año se ubica por su POSICIÓN real, que la pasa
        # quien llama: asumir "cuatro columnas atrás" da un número equivocado en
        # cuanto falta un trimestre, y da uno creíble.
        previo = columna_previa
        if fila is None or previo is None:
            return None
        # La base tiene que ser POSITIVA. Un crecimiento medido contra un FFO
        # negativo o cero da −183% y no significa nada: parece un desplome y es
        # una división sin sentido. Python ya lo exigía; esta es la otra mitad.
        return (f'=IF(OR(NOT(ISNUMBER({columna}{fila})),N({previo}{fila})<=0),"",'
                f'{columna}{fila}/{previo}{fila}-1)')

    def bloque(terminos) -> tuple[str, str] | None:
        if not terminos:
            return None
        if formula.ttm:
            if indice < TRIMESTRES_TTM - 1:
                return None
            ventana = columnas[indice - TRIMESTRES_TTM + 1: indice + 1]
            partes, rangos = [], []
            for signo, etiqueta in terminos:
                fila = filas.get(etiqueta)
                if fila is None:
                    return None
                rango = f"{ventana[0]}{fila}:{ventana[-1]}{fila}"
                partes.append(f"{'-' if signo < 0 else '+'}SUM({rango})")
                rangos.append(rango)
            expresion = "".join(partes)
            return (expresion[1:] if expresion.startswith("+") else expresion,
                    ",".join(rangos))
        return _terminos_excel(terminos, filas, columna)

    arriba = bloque(formula.suma)
    if arriba is None:
        return None
    numerador, celdas_arriba = arriba

    def guarda(celdas: str) -> str:
        """Cuándo la celda NO tiene derecho a dar número.

        Con ``ttm`` la ventana tiene que estar COMPLETA en los dos lados: doce
        meses son doce meses. Excel sumaba lo que hubiera y con dos trimestres de
        EBITDA contra cuatro de ingresos daba márgenes de 376% —un número que
        nadie revisa dos veces si el resto del estado cuadra—. Python ya exigía
        los cuatro; esta es la mitad que faltaba.
        """
        if formula.ttm:
            rangos = celdas.split(",")
            return "OR(" + ",".join(f"COUNT({r})<{TRIMESTRES_TTM}" for r in rangos) + ")"
        return f"COUNT({celdas})=0"

    if not formula.entre:
        return f'=IF({guarda(celdas_arriba)},"",({numerador}))'
    abajo = bloque(formula.entre)
    if abajo is None:
        return None
    denominador, celdas_abajo = abajo
    return (f'=IF(OR({guarda(celdas_arriba)},{guarda(celdas_abajo)}),"",'
            f'IFERROR(({numerador})/({denominador}),""))')


def _hoja_bloomberg(wb: Workbook, nombre: str, estado: str, tabla: pd.DataFrame) -> Worksheet:
    """Una vista de Bloomberg como hoja, con sus cálculos vivos."""
    from src.modelo import bloomberg as mod_bloomberg

    plantilla = mod_bloomberg.PLANTILLA[estado]
    periodos = [c for c in tabla.columns
                if c != "Renglón" and c not in mod_bloomberg.COLUMNAS_DE_APOYO]
    filas = _fila_por_etiqueta(plantilla)
    columnas = [get_column_letter(2 + i) for i in range(len(periodos))]

    ws = wb.create_sheet(nombre[:31])
    ws.cell(row=1, column=1, value="Renglón").font = FUENTE_SECCION
    for j, periodo in enumerate(periodos, start=2):
        celda = ws.cell(row=1, column=j, value=str(periodo))
        celda.font = FUENTE_SECCION
        celda.fill = RELLENO_SECCION
    col_extra = len(periodos) + 2
    for k, titulo in enumerate(("Campo Bloomberg", "Ajuste de Bloomberg", "Nota")):
        ws.cell(row=1, column=col_extra + k, value=titulo).font = FUENTE_SECCION

    for i, linea in enumerate(plantilla, start=2):
        prefijo = f"{linea.signo_texto} " if linea.signo_texto else ""
        escribir_etiqueta(
            ws, f"A{i}", ("    " * linea.nivel) + prefijo + linea.etiqueta,
            seccion=linea.seccion,
        )
        formato = FMT_POR_FORMATO.get(linea.formato, FMT_MILES)
        for j, periodo in enumerate(periodos):
            celda = ws.cell(row=i, column=2 + j)
            celda.number_format = formato
            formula = None
            if linea.formula is not None:
                # El periodo de hace un año, por su fecha real y no por posición.
                previo = None
                if linea.formula.yoy:
                    objetivo = pd.Timestamp(periodo) - pd.DateOffset(years=1)
                    candidatas = [k for k, p in enumerate(periodos)
                                  if pd.Timestamp(p) <= objetivo]
                    previo = columnas[candidatas[-1]] if candidatas else None
                formula = _formula_excel(
                    linea.formula, filas, columnas, j, columna_previa=previo,
                )
            if formula:
                celda.value = formula
                celda.font = FUENTE_FORMULA
            else:
                valor = tabla.iloc[i - 2].get(periodo)
                celda.value = None if valor is None or pd.isna(valor) else float(valor)
                celda.font = FUENTE_ENLACE if linea.rinde_cifra else FUENTE_FORMULA
        ws.cell(row=i, column=col_extra, value=linea.campo_bbg or None)
        ws.cell(row=i, column=col_extra + 1, value=linea.ajuste or None)
        ws.cell(row=i, column=col_extra + 2, value=linea.nota or None)

    ws.column_dimensions["A"].width = 46
    ws.freeze_panes = "B2"
    return ws



# --------------------------------------------------------------------------------------
# La hoja de Ratios, también viva
# --------------------------------------------------------------------------------------


def _hoja_ratios(wb: Workbook, estados: EstadosParaLibro) -> Worksheet:
    """Los ratios de la vista propia, como fórmulas sobre las hojas del estado.

    Cada ratio se declara una sola vez —`FormulaRatio`, sobre CLAVES del
    catálogo— y de ahí salen los dos: el valor que dibuja la pantalla y la
    fórmula que apunta a los renglones del estado en el libro. Cambiar la
    depreciación en «Propia Resultados» mueve el margen de EBITDAre, la cobertura
    de intereses y el apalancamiento, aquí abajo.

    Arriba van los insumos derivados —el NOI y el EBITDAre del periodo— con su
    propia fórmula y sus propias guardas. No es adorno: el EBITDAre alimenta tres
    ratios y lleva la guarda de la prueba 36, y tenerlo como renglón permite
    verlo en vez de deducirlo de tres divisiones.

    Traducir la declaración en vez de reescribirla es lo que hace que el libro no
    pueda dar otro número que la pantalla. La primera versión de esta hoja sí la
    reescribió —el NOI salía del ingreso TOTAL en vez del de renta, el EBITDAre
    exigía impuestos, el apalancamiento no anualizaba— y 356 de 923 celdas de
    Realty Income no cuadraban con Python. Ninguna daba error.
    """
    from src.ingesta.estados import ESTADOS as ESTADOS_DEL_CATALOGO
    from src.ingesta.estados import ESTADOS_DE_SALDO, LINEA_POR_CLAVE, lineas_de
    from src.servicio import (
        ETIQUETA_NO_GAAP,
        FORMULA_RATIO,
        INSUMOS_DE_RATIOS,
        RATIOS_PROPIOS,
    )

    # En qué hoja vive cada clave del catálogo, y en qué COLUMNA de esa hoja cae
    # cada periodo. Lo segundo no se puede suponer igual entre las tres hojas: el
    # balance se pide PUNTUAL y trae cortes que el estado de resultados no tiene.
    # Con una sola letra para las tres, la deuda de un ratio salía del trimestre
    # de al lado —sin error, con número—.
    hoja_de_clave: dict[str, str] = {}
    columna_de: dict[tuple[str, str], str] = {}
    periodos: list[str] = []
    for estado in ESTADOS_DEL_CATALOGO:
        tabla = estados.propia.get(estado, pd.DataFrame())
        if tabla.empty:
            continue
        hoja = HOJA_PROPIA[estado]
        presentes = set(tabla["Renglón"])
        for linea in lineas_de(estado):
            etiqueta = LINEA_POR_CLAVE[linea.clave].etiqueta
            # La PRIMERA hoja que traiga la clave, que es la que gana también en
            # el panel de Python: `pd.concat` conserva la primera duplicada.
            if etiqueta in presentes:
                hoja_de_clave.setdefault(linea.clave, hoja)
        for i, columna in enumerate(c for c in tabla.columns if c != "Renglón"):
            columna_de[(hoja, str(columna))] = get_column_letter(2 + i)
            # Las columnas de la hoja son las del FLUJO. El balance aporta cortes
            # que ningún estado de resultados acompaña, y una columna de ratios
            # sobre un periodo que no tiene resultados es una columna con la
            # deuda sola: se lee como si al trimestre le faltara todo lo demás.
            if estado not in ESTADOS_DE_SALDO and str(columna) not in periodos:
                periodos.append(str(columna))
    periodos.sort()

    ws = wb.create_sheet("Ratios")
    ws.cell(row=1, column=1, value="Ratio").font = FUENTE_SECCION
    for j, periodo in enumerate(periodos, start=2):
        celda = ws.cell(row=1, column=j, value=periodo)
        celda.font = FUENTE_SECCION
        celda.fill = RELLENO_SECCION
    ws.cell(row=1, column=len(periodos) + 2, value="Se calcula así").font = FUENTE_SECCION

    def celda_de(nombres, periodo: str) -> str | None:
        """La celda del primer renglón de la cadena que exista, en ese periodo.

        La cadena es la misma que recorre `serie_de_insumo` en Python: unas
        emisoras etiquetan el gasto del inmueble de una forma y otras de otra.
        """
        if isinstance(nombres, str):
            nombres = (nombres,)
        for clave in nombres:
            hoja = hoja_de_clave.get(clave)
            if hoja is None or clave not in LINEA_POR_CLAVE:
                continue
            columna = columna_de.get((hoja, periodo))
            if columna is None:
                continue
            return _referencia(hoja, LINEA_POR_CLAVE[clave].etiqueta, columna)
        return None

    def monto(ref: str) -> str:
        """El valor de la celda, con el hueco como cero."""
        return f"N(IFERROR({ref},0))"

    def es_numero(ref: str) -> str:
        return f'ISNUMBER(IFERROR({ref},""))'

    def suma(terminos) -> str:
        partes = "".join(
            f"{'-' if signo < 0 else '+'}{monto(ref)}" for signo, ref in terminos
        )
        return partes[1:] if partes.startswith("+") else partes

    # ------------------------------------------------------- el no-GAAP del 8-K
    # Van como VALOR y no como fórmula porque son dato, no cálculo: el AFFO lo
    # publica la emisora en su comunicado, no sale de sumar renglones del 10-Q.
    # Escribirlos aquí es lo que permite que los ratios que los usan sí sean
    # fórmula, y que quien quiera probar otro AFFO lo escriba encima y vea moverse
    # el payout.
    fila_directa: dict[str, int] = {}
    renglon = 2
    no_gaap = estados.no_gaap if estados.no_gaap is not None else pd.DataFrame()
    if not no_gaap.empty:
        escribir_etiqueta(ws, f"A{renglon}", "Del comunicado (no-GAAP)", seccion=True)
        renglon += 1
        etiqueta_a_clave = {v: k for k, v in ETIQUETA_NO_GAAP.items()}
        for _, fila in no_gaap.iterrows():
            etiqueta = str(fila["Renglón"])
            escribir_etiqueta(ws, f"A{renglon}", etiqueta)
            clave = etiqueta_a_clave.get(etiqueta)
            if clave:
                fila_directa[clave] = renglon
            for j, periodo in enumerate(periodos):
                valor = fila.get(periodo)
                celda = ws.cell(row=renglon, column=2 + j)
                celda.number_format = FMT_MILES
                if valor is not None and not pd.isna(valor):
                    celda.value = float(valor)
            renglon += 1
        renglon += 1

    # ---------------------------------------------------------------- insumos
    fila_insumo: dict[str, int] = {}
    escribir_etiqueta(ws, f"A{renglon}", "Insumos derivados", seccion=True)
    renglon += 1
    for insumo in INSUMOS_DE_RATIOS:
        escribir_etiqueta(ws, f"A{renglon}", insumo.etiqueta)
        fila_insumo[insumo.clave] = renglon
        fila_directa[insumo.clave] = renglon
        for j, periodo in enumerate(periodos):
            celda = ws.cell(row=renglon, column=2 + j)
            celda.number_format = FMT_MILES
            terminos, exigidas, falta = [], [], False
            for signo, nombres in insumo.exigidos:
                ref = celda_de(nombres, periodo)
                if ref is None:
                    falta = True
                    break
                terminos.append((signo, ref))
                exigidas.append(ref)
            if falta:
                continue
            for signo, nombres in insumo.opcionales:
                ref = celda_de(nombres, periodo)
                if ref is not None:
                    terminos.append((signo, ref))
            expresion = suma(terminos)

            condiciones = []
            if insumo.por_celda:
                # La guarda de la prueba 36, en Excel: sin depreciación no hay
                # EBITDAre. `N()` de una celda vacía es cero y no avisa.
                condiciones += [f"NOT({es_numero(ref)})" for ref in exigidas]
            for nombres in insumo.positivos:
                ref = celda_de(nombres, periodo)
                if ref is None:
                    falta = True
                    break
                condiciones.append(f"{monto(ref)}<=0")
            if falta:
                continue
            if insumo.resultado_positivo:
                condiciones.append(f"({expresion})<=0")
            if insumo.piso is not None:
                minimo, nombres = insumo.piso
                ref = celda_de(nombres, periodo)
                if ref is not None:
                    condiciones.append(
                        f"AND({monto(ref)}>0,({expresion})/{monto(ref)}<{minimo})"
                    )
            celda.value = (
                f'=IF(OR({",".join(condiciones)}),"",{expresion})'
                if condiciones else f"={expresion}"
            )
            celda.font = FUENTE_FORMULA
        renglon += 1

    # ----------------------------------------------------------------- ratios
    renglon += 1
    escribir_etiqueta(ws, f"A{renglon}", "Ratios", seccion=True)
    renglon += 1
    for etiqueta, clave, formato, explicacion in RATIOS_PROPIOS:
        escribir_etiqueta(ws, f"A{renglon}", etiqueta)
        ws.cell(row=renglon, column=len(periodos) + 2, value=explicacion)
        formula = FORMULA_RATIO.get(clave)
        for j, periodo in enumerate(periodos):
            celda = ws.cell(row=renglon, column=2 + j)
            celda.number_format = FMT_PCT if formato == "pct" else FMT_VECES
            if formula is None:
                continue
            columna = get_column_letter(2 + j)

            def lado(terminos, periodo=periodo, columna=columna, formula=formula):
                """Los términos de un lado, con su signo; `None` si falta uno."""
                partes, exigidas = [], []
                for signo, clave_termino in terminos:
                    if clave_termino in fila_directa:
                        ref = f"{columna}{fila_directa[clave_termino]}"
                    else:
                        ref = celda_de(clave_termino, periodo)
                    if ref is None:
                        return None
                    partes.append((signo, ref))
                    if clave_termino not in formula.opcionales:
                        exigidas.append(ref)
                return partes, exigidas

            arriba, abajo = lado(formula.numerador), lado(formula.denominador)
            if arriba is None or abajo is None:
                continue
            num = f"({suma(arriba[0])})"
            den = f"({suma(abajo[0])})"
            if formula.anualiza_numerador != 1:
                num = f"({num}*{formula.anualiza_numerador})"
            # Con el paréntesis. Sin él, `(a)/(b)*4` es `a/b*4` y no `a/(b*4)`:
            # el apalancamiento salía dieciséis veces el que es, y en Excel un
            # 74.7x no se distingue a simple vista de un 4.67x mal puesto.
            if formula.anualiza_denominador != 1:
                den = f"({den}*{formula.anualiza_denominador})"
            condiciones = [f"NOT({es_numero(ref)})" for ref in arriba[1] + abajo[1]]
            condiciones.append(f"{den}=0")
            celda.value = f'=IF(OR({",".join(condiciones)}),"",{num}/{den})'
            celda.font = FUENTE_FORMULA
        renglon += 1

    ws.column_dimensions["A"].width = 34
    ws.freeze_panes = "B2"
    return ws
