"""Los tres estados en el molde de Bloomberg, con sus convenciones.

Qué es esta vista y qué NO es
------------------------------
No son los datos de Bloomberg. No hay terminal aquí y no la va a haber: son
**nuestros datos, de EDGAR, puestos en la forma en que Bloomberg los presenta**,
con los ajustes que Bloomberg aplica y con los renglones que Bloomberg usa, en su
orden y con sus nombres.

Sirve para dos cosas concretas. La primera es comparar: quien lee la terminal
todo el día puede poner las dos pantallas lado a lado y ver si cuadran, renglón
por renglón, sin traducir en la cabeza. La segunda es más importante: **hace
visible el ajuste**. Cada renglón que Bloomberg cambia respecto de lo que dice el
filing queda marcado, con su monto, en vez de quedar sepultado en un número
distinto sin explicación.

El molde sale del export real
-----------------------------
Los renglones, su orden y su jerarquía no se inventaron: se leyeron del histórico
trimestral que se bajó de Bloomberg para Realty Income —"Income - GAAP",
"Bal Sheet - Standardized" y "Cash Flow - Standardized"—. Es la plantilla REIT
estándar de Bloomberg, así que aplica a las diez, pero **solo está verificada
contra O**, que es la única emisora de la que hay un export. Donde se dice
"cuadra con Bloomberg" hay que leer "cuadra con Bloomberg en Realty Income".

Lo que NO se puede llenar, y no se inventa
------------------------------------------
Bloomberg trae renglones que no salen de un filing: número de propiedades, área
rentable, número de empleados, ventas por empleado. Esos quedan vacíos. Un guion
en la pantalla es información —"esto no lo tenemos"—; un cero o una estimación
sería una mentira con formato de dato.

Y el aviso que vale por sí solo: **el "AFFO" de Bloomberg no es el AFFO.** Su
cascada va FFO → "Adjusted Funds from Operations" → FAD, y el AFFO que reporta
Realty Income —el que usa el modelo— coincide con el FAD de Bloomberg, no con su
renglón de AFFO. Aquí se respeta el nombre de Bloomberg en la etiqueta y se pone
nuestro AFFO donde Bloomberg pone el FAD, que es donde va.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

RESULTADOS = "resultados"
BALANCE = "balance"
FLUJO = "flujo"
ESTADOS = (RESULTADOS, BALANCE, FLUJO)

NOMBRE_ESTADO = {
    RESULTADOS: "Income — GAAP",
    BALANCE: "Balance Sheet — Standardized",
    FLUJO: "Cash Flow — Standardized",
}


@dataclass(frozen=True)
class LineaBBG:
    """Un renglón del molde de Bloomberg.

    ``clave`` es nuestra clave de catálogo cuando el renglón sale directo de él.
    ``componentes`` suma varias claves nuestras en un renglón de Bloomberg.
    ``ajuste`` nombra la convención de Bloomberg que mueve el número respecto del
    filing, y es lo que la pantalla marca.
    """

    etiqueta: str
    nivel: int = 0
    clave: str | None = None
    componentes: tuple[str, ...] = ()
    signo: int = 1
    total: bool = False
    seccion: bool = False
    ajuste: str = ""
    nota: str = ""
    derivada: str = ""


def _l(etiqueta, nivel=0, **kw) -> LineaBBG:
    return LineaBBG(etiqueta=etiqueta, nivel=nivel, **kw)


# --------------------------------------------------------------------------------------
# Las convenciones de Bloomberg, nombradas
# --------------------------------------------------------------------------------------
#
# Se descubrieron comparando el export de Realty Income contra su 10-Q, renglón
# por renglón (prueba 31). No son errores de nadie: son la capa de
# estandarización que Bloomberg aplica para que dos emisoras con contabilidades
# distintas se puedan comparar. Aquí se aplican para reproducir su vista, y se
# marcan para que nunca se confundan con lo que dice el filing.

AJUSTE_ARRENDAMIENTOS = (
    "Bloomberg mete los arrendamientos capitalizados —operativos y financieros— "
    "DENTRO de la deuda, y su contraparte del activo dentro de los inmuebles. Es "
    "lo que hacen las calificadoras. No es lo que dice el balance."
)
AJUSTE_INTERESES = (
    "Bloomberg saca el gasto por intereses de los gastos de operación para llegar "
    "a un EBIT comparable. Realty Income lo reporta DENTRO de «Total expenses»."
)
AJUSTE_DIVIDENDOS = (
    "Bloomberg suma los dividendos por pagar a las cuentas por pagar."
)
AJUSTE_FAD = (
    "El renglón que Bloomberg llama FAD es el que Realty Income llama AFFO. Su "
    "«Adjusted Funds from Operations» es un paso intermedio y NO es el AFFO."
)


# --------------------------------------------------------------------------------------
# Estado de resultados — "Income - GAAP"
# --------------------------------------------------------------------------------------

_RESULTADOS: tuple[LineaBBG, ...] = (
    _l("Revenue", seccion=True, total=True, clave="ingresos_totales"),
    _l("+ Rental Income", 1, clave="ingreso_rentas"),
    _l("+ Recoveries from Tenants", 2, clave="ingreso_reembolsos"),
    _l("+ Other Operating Income", 1, clave="ingreso_otros"),
    _l("- Operating Expenses", 1, total=True, derivada="gastos_operativos_bbg",
       ajuste=AJUSTE_INTERESES),
    _l("+ Property Operating Expenses", 2, clave="gasto_operacion_inmueble"),
    _l("+ General & Administrative", 2, clave="gasto_administracion"),
    _l("+ Depreciation & Amortization", 2, clave="depreciacion_amortizacion"),
    _l("+ Provision for Loan Losses", 2, clave="deterioro"),
    _l("Operating Income (Loss)", seccion=True, total=True, derivada="utilidad_operativa_bbg",
       ajuste=AJUSTE_INTERESES),
    _l("- Non-Operating (Income) Loss", 1, total=True, derivada="no_operativo_bbg"),
    _l("+ Interest Expense", 2, clave="gasto_intereses", ajuste=AJUSTE_INTERESES),
    _l("+ (Income) Loss from Affiliates", 2, clave="resultado_no_consolidadas", signo=-1),
    _l("+ Other Non-Op (Income) Loss", 2, clave="otros_no_operativos", signo=-1),
    _l("Pretax Income", seccion=True, total=True, clave="utilidad_antes_impuestos"),
    _l("- Income Tax Expense (Benefit)", 1, clave="impuestos"),
    _l("Income (Loss) Incl. MI", seccion=True, total=True, clave="utilidad_neta"),
    _l("- Minority Interest", 1, clave="utilidad_minoritarios"),
    _l("Net Income, GAAP", seccion=True, total=True, clave="utilidad_neta"),
    _l("- Preferred Dividends", 1, clave="dividendos_preferentes"),
    _l("Net Income Avail to Common, GAAP", seccion=True, total=True, clave="utilidad_neta_comun"),
    _l("Basic Weighted Avg Shares", clave="acciones_basicas"),
    _l("Basic EPS, GAAP", clave="utilidad_por_accion_basica"),
    _l("Diluted Weighted Avg Shares", clave="acciones_diluidas"),
    _l("Diluted EPS, GAAP", clave="utilidad_por_accion_diluida"),
    _l("FFO Reconciliation", seccion=True),
    _l("Funds from Operations", 1, total=True, clave="ffo"),
    _l("Adjusted Funds from Operations", 1, clave="ffo_normalizado",
       nota="Bloomberg llama AFFO a un paso intermedio. El AFFO del emisor está abajo."),
    _l("Funds Available For Distribution", 1, total=True, clave="affo", ajuste=AJUSTE_FAD),
    _l("FAD Per Diluted Share", 1, clave="affo_por_accion", ajuste=AJUSTE_FAD),
    _l("FFO Per Share - Fully Diluted", 1, clave="ffo_por_accion"),
    _l("Dividend Per Share", 1, clave="dividendo_declarado_por_accion"),
    _l("Reference Items", seccion=True),
    _l("EBITDA", 1, clave="ebitdare", nota="EBITDAre de Nareit, que resta la ganancia por venta."),
    _l("Real Estate Tax Expense", 1, clave="gasto_predial_seguro"),
    _l("Number of Properties Owned", 1, nota="No sale de un filing de la SEC."),
    _l("Gross Leaseable Area (Sq Ft)", 1, nota="No sale de un filing de la SEC."),
)


# --------------------------------------------------------------------------------------
# Balance — "Bal Sheet - Standardized"
# --------------------------------------------------------------------------------------

_BALANCE: tuple[LineaBBG, ...] = (
    _l("Assets", seccion=True),
    _l("+ Real Estate Held for Sale", 1, clave="activos_mantenidos_venta"),
    _l("+ Real Estate Equity Interests", 1, clave="inversiones_no_consolidadas"),
    _l("+ Net Real Estate Property", 1, total=True, derivada="inmuebles_bbg",
       ajuste=AJUSTE_ARRENDAMIENTOS),
    _l("+ Gross Real Estate Property", 2, clave="inmuebles_bruto"),
    _l("- Accumulated Depreciation", 2, clave="depreciacion_acumulada"),
    _l("+ Net Mortgages & Notes", 1, clave="prestamos_por_cobrar"),
    _l("Total Real Estate Investments", seccion=True, total=True, derivada="inversion_total_bbg"),
    _l("+ Cash & Near Cash Items", 1, clave="efectivo"),
    _l("+ Accounts Receivable", 1, componentes=("cuentas_por_cobrar",
                                                "renta_linea_recta_por_cobrar")),
    _l("+ Other Assets", 1, clave="activos_otros"),
    _l("+ Restricted Assets", 1, clave="efectivo_restringido"),
    _l("Total Assets", seccion=True, total=True, clave="activos_totales"),
    _l("Liabilities & Shareholders' Equity", seccion=True),
    _l("+ Accounts Payable", 1, clave="cuentas_por_pagar", ajuste=AJUSTE_DIVIDENDOS),
    _l("+ Secured & Unsecured Debt", 1, total=True, derivada="deuda_bbg",
       ajuste=AJUSTE_ARRENDAMIENTOS),
    _l("+ Unsecured Debt", 2, componentes=("notas_senior", "linea_de_credito",
                                           "prestamos_a_plazo", "deuda_no_garantizada")),
    _l("+ Secured Debt", 2, clave="deuda_hipotecaria"),
    _l("+ Other Long-Term Liabilities", 1, clave="pasivos_otros"),
    _l("Total Liabilities", seccion=True, total=True, clave="pasivos_totales"),
    _l("+ Total Preferred Equity", 1, clave="capital_preferente"),
    _l("+ Minority Interest", 1, clave="participacion_no_controladora"),
    _l("+ Share Capital & APIC", 1, componentes=("capital_comun", "prima_en_acciones")),
    _l("+ Retained Earnings & Other Equity", 1, componentes=("utilidades_retenidas",
                                                             "otro_resultado_integral")),
    _l("Total Equity", seccion=True, total=True, clave="capital_total"),
    _l("Total Liabilities & Equity", seccion=True, total=True, clave="pasivo_mas_capital"),
    _l("Reference Items", seccion=True),
    _l("Shares Outstanding", 1, clave="acciones_en_circulacion"),
    _l("Operating Leases", 1, clave="pasivo_arrendamiento"),
    _l("Net Debt", 1, derivada="deuda_neta_bbg", ajuste=AJUSTE_ARRENDAMIENTOS),
    _l("Number of Employees", 1, nota="No sale de un filing de la SEC."),
)


# --------------------------------------------------------------------------------------
# Flujo — "Cash Flow - Standardized"
# --------------------------------------------------------------------------------------

_FLUJO: tuple[LineaBBG, ...] = (
    _l("Cash From Operating Activities", seccion=True),
    _l("Net Income", 1, clave="utilidad_neta"),
    _l("+ Depreciation & Amortization", 1, clave="depreciacion_amortizacion"),
    _l("+ Other Non-Cash Adjustments", 1, clave="compensacion_en_acciones"),
    _l("Cash From Operating Activities", seccion=True, total=True, clave="flujo_operacion"),
    _l("Cash From Investing Activities", seccion=True),
    _l("+ Disposal of Fixed Assets", 1, clave="venta_inmuebles"),
    _l("+ Property Additions", 1, clave="adquisicion_inmuebles", signo=-1),
    _l("+ Property Improvements", 1, clave="desarrollo_inmuebles", signo=-1),
    _l("Cash from Investing Activities", seccion=True, total=True, clave="flujo_inversion"),
    _l("Cash from Financing Activities", seccion=True),
    _l("+ Dividends Paid", 1, clave="dividendos_pagados", signo=-1),
    _l("+ Proceeds from Repayments of Borrowings", 1, componentes=("emision_deuda", "pago_deuda")),
    _l("+ Increase in Capital Stocks", 1, clave="emision_acciones"),
    _l("Cash from Financing Activities", seccion=True, total=True, clave="flujo_financiamiento"),
    _l("Net Changes in Cash", seccion=True, total=True, clave="cambio_neto_efectivo"),
    _l("Reference Items", seccion=True),
    _l("EBITDA", 1, clave="ebitdare"),
    _l("Funds From Operations", 1, clave="ffo"),
    _l("FFO Per Share", 1, clave="ffo_por_accion"),
    _l("Cash Paid for Interest", 1, clave="gasto_intereses"),
)

PLANTILLA: dict[str, tuple[LineaBBG, ...]] = {
    RESULTADOS: _RESULTADOS,
    BALANCE: _BALANCE,
    FLUJO: _FLUJO,
}


# --------------------------------------------------------------------------------------
# Los renglones que Bloomberg construye y nosotros no teníamos
# --------------------------------------------------------------------------------------

# Los tramos que suman la deuda de Bloomberg. Los mismos que usa el servicio para
# el apalancamiento, más los arrendamientos que Bloomberg mete adentro.
_TRAMOS_DEUDA = ("notas_senior", "linea_de_credito", "prestamos_a_plazo",
                 "deuda_no_garantizada", "deuda_hipotecaria", "otras_notas_por_pagar")
_ARRENDAMIENTOS = ("pasivo_arrendamiento",)


def _suma(fila: pd.Series, claves) -> float | None:
    valores = [fila.get(c) for c in claves]
    vivos = [float(v) for v in valores if v is not None and pd.notna(v)]
    return sum(vivos) if vivos else None


def _derivar(nombre: str, fila: pd.Series) -> float | None:
    """Los renglones que Bloomberg arma y que no existen como tal en el filing."""
    def v(clave):
        x = fila.get(clave)
        return float(x) if x is not None and pd.notna(x) else None

    if nombre == "gastos_operativos_bbg":
        # Bloomberg saca los intereses de los gastos de operación.
        totales, intereses = v("gastos_totales"), v("gasto_intereses")
        if totales is None:
            return None
        return totales - (intereses or 0.0)
    if nombre == "utilidad_operativa_bbg":
        ingresos = v("ingresos_totales")
        gastos = _derivar("gastos_operativos_bbg", fila)
        return None if ingresos is None or gastos is None else ingresos - gastos
    if nombre == "no_operativo_bbg":
        partes = [v("gasto_intereses"),
                  None if v("resultado_no_consolidadas") is None else -v("resultado_no_consolidadas"),
                  None if v("otros_no_operativos") is None else -v("otros_no_operativos")]
        vivos = [p for p in partes if p is not None]
        return sum(vivos) if vivos else None
    if nombre == "inmuebles_bbg":
        # El activo por derecho de uso entra a inmuebles, que es la contraparte
        # de meter el arrendamiento a la deuda.
        return _suma(fila, ("inmuebles_neto", "activo_arrendamiento"))
    if nombre == "inversion_total_bbg":
        return _suma(fila, ("inmuebles_neto", "activo_arrendamiento",
                            "activos_mantenidos_venta", "inversiones_no_consolidadas",
                            "prestamos_por_cobrar"))
    if nombre == "deuda_bbg":
        return _suma(fila, (*_TRAMOS_DEUDA, *_ARRENDAMIENTOS))
    if nombre == "deuda_neta_bbg":
        deuda = _derivar("deuda_bbg", fila)
        if deuda is None:
            return None
        return deuda - (v("efectivo") or 0.0)
    return None


def armar(panel: pd.DataFrame, estado: str, *, n_periodos: int = 8) -> pd.DataFrame:
    """El estado en el molde de Bloomberg, ancho: renglones × periodos.

    ``panel`` es el cuadro trimestral o anual del servicio —una fila por periodo,
    una columna por concepto del catálogo—. De ahí sale todo: esta función no
    consulta nada, solo reordena y aplica las convenciones.

    Devuelve columnas ``Renglón``, ``nivel``, ``ajuste``, ``nota`` y una por
    periodo. Los renglones que no se pueden llenar salen en blanco: ver la
    docstring del módulo sobre por qué no se estiman.
    """
    plantilla = PLANTILLA.get(estado)
    if plantilla is None or panel is None or panel.empty:
        return pd.DataFrame()

    periodos = list(panel.index)[-n_periodos:]
    filas = []
    for linea in plantilla:
        fila = {
            "Renglón": ("    " * linea.nivel) + linea.etiqueta,
            "nivel": linea.nivel,
            "seccion": linea.seccion,
            "total": linea.total,
            "ajuste": linea.ajuste,
            "nota": linea.nota,
        }
        for periodo in periodos:
            datos = panel.loc[periodo]
            if linea.derivada:
                valor = _derivar(linea.derivada, datos)
            elif linea.componentes:
                valor = _suma(datos, linea.componentes)
            elif linea.clave:
                bruto = datos.get(linea.clave)
                valor = float(bruto) if bruto is not None and pd.notna(bruto) else None
            else:
                valor = None
            etiqueta_periodo = (
                periodo.date().isoformat() if hasattr(periodo, "date") else str(periodo)
            )
            fila[etiqueta_periodo] = None if valor is None else valor * linea.signo
        filas.append(fila)
    return pd.DataFrame(filas)


def cobertura(panel: pd.DataFrame, estado: str) -> tuple[int, int]:
    """(renglones con dato, renglones que piden dato) del molde para este panel.

    Es lo que la pantalla usa para decir de frente cuánto del molde se puede
    llenar, en vez de dejar que el usuario lo cuente a ojo.
    """
    tabla = armar(panel, estado, n_periodos=1)
    if tabla.empty:
        return (0, 0)
    columnas = [c for c in tabla.columns
                if c not in ("Renglón", "nivel", "seccion", "total", "ajuste", "nota")]
    piden = tabla[~tabla["seccion"] | tabla["total"]]
    con_dato = piden[columnas].notna().any(axis=1).sum() if columnas else 0
    return (int(con_dato), int(len(piden)))


AJUSTES = {
    "arrendamientos": AJUSTE_ARRENDAMIENTOS,
    "intereses": AJUSTE_INTERESES,
    "dividendos": AJUSTE_DIVIDENDOS,
    "fad": AJUSTE_FAD,
}

__all__ = [
    "AJUSTES", "BALANCE", "ESTADOS", "FLUJO", "NOMBRE_ESTADO", "PLANTILLA",
    "RESULTADOS", "LineaBBG", "armar", "cobertura",
]
