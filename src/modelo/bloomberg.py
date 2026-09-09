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

El molde es DATO, no código
---------------------------
La primera versión de este módulo escribía los renglones a mano y se quedó en
**89 de 186**: faltaba más de la mitad del estado de resultados, casi la mitad del
balance y todos los ratios —los tres payout, los márgenes, el book value por
acción, la deuda a capital—. Un molde "de Bloomberg" al que le faltan noventa y
seis renglones no es el molde de Bloomberg; es una selección con su nombre.

Así que el molde dejó de vivir en el código. ``molde_bloomberg.json`` tiene los
186 renglones con su orden, su nivel de sangría y su signo, extraídos del export
real, y este módulo los LEE. El orden y la jerarquía ya no se pueden desviar
escribiendo: para que se desvíen hay que editar el molde, y hay una prueba que
cuenta los renglones.

El archivo guarda la ESTRUCTURA —etiqueta, nivel, signo y el mnemónico del campo
de Bloomberg— y ninguna de sus cifras. La forma de un estado financiero es
pública; los datos de la terminal son de quien paga la terminal.

Lo que se mantiene a mano es el MAPEO: qué renglón nuestro alimenta cada renglón
de Bloomberg. Eso sí es criterio y tiene que estar a la vista.

Lo que NO se puede llenar, y no se inventa
------------------------------------------
Bloomberg trae renglones que no salen de un filing —número de propiedades, área
rentable, empleados, ventas por empleado— y otros que salen de la cascada del
8-K, no del estado. Esos quedan vacíos, y **quedan**: un renglón en blanco dice
"esto no lo tenemos"; un renglón ausente hace creer que Bloomberg tampoco lo
tiene. La pantalla declara la cobertura para que el hueco se cuente, no se
adivine.

Y el aviso que vale por sí solo: **el "AFFO" de Bloomberg no es el AFFO.** Su
cascada va FFO → "Adjusted Funds from Operations" → FAD, y el AFFO que reporta
Realty Income —el que usa el modelo— coincide con el FAD de Bloomberg, no con su
renglón de AFFO. Aquí se respeta el nombre de Bloomberg en la etiqueta y se pone
nuestro AFFO donde Bloomberg pone el FAD, que es donde va.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

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

RUTA_MOLDE = Path(__file__).with_name("molde_bloomberg.json")


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

NOTA_SIN_FILING = "No sale de un filing de la SEC."
NOTA_CASCADA = (
    "Vive en la conciliación del AFFO del 8-K, no en el estado financiero. "
    "Está en la pestaña «Evidencia», renglón por renglón."
)
NOTA_NO_APLICA = "Renglón del molde de Bloomberg que no aplica a un REIT de EE. UU."


@dataclass(frozen=True)
class Formula:
    """Un cálculo expresado sobre OTROS RENGLONES del mismo estado.

    Existe para que el cálculo viva en UN solo lugar y sirva a los dos destinos.
    La pantalla lo evalúa en Python; el libro de Excel lo traduce a una fórmula
    que apunta a las celdas de esos renglones, así que el usuario puede cambiar
    un renglón del estado y ver moverse el payout, el margen y el apalancamiento.

    Escribir el número dos veces —una en Python para la pantalla y otra a mano en
    el generador de Excel— es la forma segura de que se separen sin que nadie se
    entere. Por eso se declara sobre ETIQUETAS y no sobre celdas: la etiqueta es
    la misma en los dos mundos.

    ``suma`` son los sumandos con su signo; ``entre`` es el denominador, con la
    misma forma. ``ttm`` suma los cuatro periodos hasta el actual —es lo que hace
    Bloomberg con sus márgenes de doce meses—. ``yoy`` divide entre el valor de
    la MISMA etiqueta un año antes y resta uno.
    """

    suma: tuple[tuple[int, str], ...] = ()
    entre: tuple[tuple[int, str], ...] = ()
    ttm: bool = False
    yoy: str = ""


@dataclass(frozen=True)
class LineaBBG:
    """Un renglón del molde, ya resuelto: la estructura del JSON más el mapeo."""

    etiqueta: str
    nivel: int
    signo_texto: str
    campo_bbg: str
    clave: str | None = None
    componentes: tuple[str, ...] = ()
    signo: int = 1
    derivada: str = ""
    formula: Formula | None = None
    formato: str = "monto"
    ajuste: str = ""
    nota: str = ""

    @property
    def seccion(self) -> bool:
        """Un encabezado de sección, según el propio export: sin campo de Bloomberg.

        Definirlo como "nivel cero y sin dato" —que fue el primer intento— es
        circular y halagador: convertía en encabezado a todo renglón que no
        supiéramos llenar. «Number of Employees» y «Sales per Employee» pasaban a
        contar como títulos y **salían del denominador de la cobertura**, así que
        la vista se veía más completa cuanto menos supiera llenar.

        El export tiene la señal buena: «Reference Items» y «Assets» no traen
        mnemónico de campo porque no son un dato; «Number of Employees» trae
        ``NUM_OF_EMPLOYEE`` porque sí lo es, aunque nosotros no lo tengamos.
        """
        return not self.campo_bbg

    @property
    def rinde_cifra(self) -> bool:
        return bool(self.clave or self.componentes or self.derivada or self.formula)


# --------------------------------------------------------------------------------------
# El mapeo — lo único que se mantiene a mano
# --------------------------------------------------------------------------------------
#
# Llave: la etiqueta EXACTA del molde. Valor: de dónde sale.
#   clave        — un renglón de nuestro catálogo
#   componentes  — varios que se suman
#   derivada     — un cálculo con nombre, abajo en `_derivar`
#   formato      — "monto" | "por_accion" | "pct" | "veces" | "conteo"
#
# Un renglón que no aparece aquí sale en blanco, y sale. Ver la docstring.

_MAPEO_RESULTADOS: dict[str, dict] = {
    "Revenue": {"clave": "ingresos_totales"},
    "Rental Income": {"clave": "ingreso_rentas"},
    "Recoveries from Tenants": {"clave": "ingreso_reembolsos"},
    "Percentage Rent": {"clave": "ingreso_renta_variable"},
    "Com & Fee Earn/Inc from REO": {"clave": "ingreso_gestion"},
    "Mortgage Income": {"clave": "ingreso_intereses"},
    "Other Operating Income": {"clave": "ingreso_otros"},
    "Operating Expenses": {"derivada": "gastos_operativos", "ajuste": AJUSTE_INTERESES},
    "Property Operating Expenses": {"clave": "gasto_operacion_inmueble"},
    "General & Administrative": {"clave": "gasto_administracion"},
    "Depreciation & Amortization": {"clave": "depreciacion_amortizacion"},
    "Provision for Loan Losses": {"clave": "provision_perdidas_crediticias"},
    "Other Operating Expenses": {"clave": "gasto_otros"},
    "Operating Income (Loss)": {
        "formula": Formula(suma=((1, "Revenue"), (-1, "Operating Expenses"))),
        "ajuste": AJUSTE_INTERESES,
    },
    "Non-Operating (Income) Loss": {"derivada": "no_operativo"},
    "Interest Expense": {"clave": "gasto_intereses", "ajuste": AJUSTE_INTERESES},
    "(Income) Loss from Affiliates": {"clave": "resultado_no_consolidadas", "signo": -1},
    "Other Non-Op (Income) Loss": {"clave": "otros_no_operativos", "signo": -1},
    "Pretax Income": {"clave": "utilidad_antes_impuestos"},
    "Income Tax Expense (Benefit)": {"clave": "impuestos"},
    "Income (Loss) from Cont Ops": {"derivada": "utilidad_continuas"},
    "Discontinued Operations": {"clave": "operaciones_discontinuadas"},
    "Income (Loss) Incl. MI": {"derivada": "utilidad_con_minoritarios"},
    "Minority Interest": {"clave": "utilidad_minoritarios"},
    "Net Income, GAAP": {"clave": "utilidad_neta"},
    "Preferred Dividends": {"clave": "dividendos_preferentes"},
    "Net Income Avail to Common, GAAP": {"derivada": "utilidad_comun"},
    "Basic Weighted Avg Shares": {"clave": "acciones_basicas", "formato": "conteo"},
    "Basic EPS, GAAP": {"clave": "utilidad_por_accion_basica", "formato": "por_accion"},
    "Diluted Weighted Avg Shares": {"clave": "acciones_diluidas", "formato": "conteo"},
    "Basic EPS from Cont Ops, GAAP": {
        "clave": "utilidad_por_accion_basica_continuas", "formato": "por_accion",
    },
    "Diluted EPS, GAAP": {"clave": "utilidad_por_accion_diluida", "formato": "por_accion"},
    "Diluted EPS from Cont Ops, GAAP": {
        "clave": "utilidad_por_accion_diluida_continuas", "formato": "por_accion",
    },
    # La cascada del FFO vive en el 8-K, no en el estado. Los subtotales sí los
    # tenemos porque son los que el modelo consume.
    "Funds from Operations": {"derivada": "ffo_monto"},
    "Adjusted Funds from Operations": {
        "clave": "ffo_normalizado",
        "nota": "Bloomberg llama AFFO a este paso intermedio. El AFFO del emisor es el FAD.",
    },
    "Stock-Based Compensation": {"clave": "compensacion_en_acciones", "nota": NOTA_CASCADA},
    "Funds Available For Distribution": {"clave": "affo", "ajuste": AJUSTE_FAD},
    "AFFO Per Diluted Share": {"derivada": "affo_bbg_por_accion", "formato": "por_accion"},
    "FAD Per Diluted Share": {
        "clave": "affo_por_accion", "formato": "por_accion", "ajuste": AJUSTE_FAD,
    },
    "Dividend Per Share": {"clave": "dividendo_declarado_por_accion", "formato": "por_accion"},
    "AFFO Payout Ratio": {
        "formula": Formula(suma=((1, "Dividend Per Share"),),
                           entre=((1, "AFFO Per Diluted Share"),)),
        "formato": "pct",
    },
    "FAD Payout Ratio": {
        "formula": Formula(suma=((1, "Dividend Per Share"),),
                           entre=((1, "FAD Per Diluted Share"),)),
        "formato": "pct", "ajuste": AJUSTE_FAD,
    },
    "FFO Payout Ratio": {
        "formula": Formula(suma=((1, "Dividend Per Share"),),
                           entre=((1, "FFO Per Share - Fully Diluted"),)),
        "formato": "pct",
    },
    "EBITDA": {
        "clave": "ebitdare",
        "nota": "EBITDAre de Nareit, que resta la ganancia por venta.",
    },
    "EBITDA Margin (T12M)": {
        "formula": Formula(suma=((1, "EBITDA"),), entre=((1, "Revenue"),), ttm=True),
        "formato": "pct",
    },
    "Operating Margin": {
        "formula": Formula(suma=((1, "Operating Income (Loss)"),),
                           entre=((1, "Revenue"),)),
        "formato": "pct",
    },
    "Dividends/Distributions per Share/Unit": {
        "clave": "dividendo_declarado_por_accion", "formato": "por_accion",
    },
    "Total Cash Common Dividends": {"clave": "dividendos_pagados"},
    "FFO Per Share - Fully Diluted": {"clave": "ffo_por_accion", "formato": "por_accion"},
    "FFO per Share Growth": {
        "formula": Formula(yoy="FFO Per Share - Fully Diluted"), "formato": "pct",
    },
    "FFO to Diluted Shares - 1 Yr Growth": {
        "formula": Formula(yoy="FFO Per Share - Fully Diluted"), "formato": "pct",
    },
    "FAD per Share Diluted": {
        "clave": "affo_por_accion", "formato": "por_accion", "ajuste": AJUSTE_FAD,
    },
    "Real Estate Tax Expense": {"clave": "gasto_predial_seguro"},
    "Real Estate Write-Downs": {"clave": "deterioro"},
    # Los que no salen de ningún lado, dichos por su nombre.
    "Base Rent": {"nota": "El catálogo no separa la renta base de la total."},
    "Other Rental Income": {"nota": "El catálogo no separa la renta base de la total."},
    "Real Estate Sales": {"nota": "Nuestro catálogo lo lleva como ganancia, no como ingreso."},
    "Cost of Real Estate Sold": {"nota": "Nuestro catálogo lo lleva neto, en la ganancia."},
    "Net Extraordinary Losses (Gains)": {"nota": NOTA_NO_APLICA},
    "XO & Accounting Changes": {"nota": NOTA_NO_APLICA},
    "Other Adjustments": {"nota": NOTA_CASCADA},
    "Net Income Avail to Common, Adj": {"nota": "Ajuste propio de Bloomberg."},
    "Net Abnormal Losses (Gains)": {"nota": "Ajuste propio de Bloomberg."},
    "Basic EPS from Cont Ops, Adjusted": {"nota": "Ajuste propio de Bloomberg."},
    "Diluted EPS from Cont Ops, Adjusted": {"nota": "Ajuste propio de Bloomberg."},
    "D&A of Con Real Estate": {"nota": NOTA_CASCADA},
    "D&A of Uncon Real Estate": {"nota": NOTA_CASCADA},
    "D&A from Disc Ops": {"nota": NOTA_CASCADA},
    "Impairment of Assets": {"nota": NOTA_CASCADA},
    "Disposal of Con Assets": {"nota": NOTA_CASCADA},
    "Disposal of Assets from Disc Ops": {"nota": NOTA_CASCADA},
    "Abnormal Losses/(Gains)": {"nota": NOTA_CASCADA},
    "Other FFO Adjustments": {"nota": NOTA_CASCADA},
    "Other Abnormal Gains/(Losses)": {"nota": NOTA_CASCADA},
    "Straight-Line Rent": {"nota": NOTA_CASCADA},
    "Amortization of Financing Costs": {"nota": NOTA_CASCADA},
    "Recurring Capital Expenditure": {"nota": NOTA_CASCADA},
    "Accounting Adjustments": {"nota": NOTA_CASCADA},
    "Tenant Improv & Leasing Com": {"nota": NOTA_CASCADA},
    "Accounting Standard": {"nota": "Siempre US GAAP en este universo."},
    "Current Profit": {"nota": "Concepto de la contabilidad japonesa."},
    "Sales per Employee": {"nota": NOTA_SIN_FILING},
    "FFO Return": {"nota": "Ratio propio de Bloomberg sobre su base de activos."},
    "Maintenance Expense (REITS)": {"nota": NOTA_SIN_FILING},
    "Number of Properties Owned": {"nota": NOTA_SIN_FILING},
    "Gross Leaseable Area (Sq Ft)": {"nota": NOTA_SIN_FILING},
}

_MAPEO_BALANCE: dict[str, dict] = {
    "Real Estate Held for Sale": {"clave": "activos_mantenidos_venta"},
    "Real Estate Equity Interests": {"clave": "inversiones_no_consolidadas"},
    "Net Real Estate Property": {"derivada": "inmuebles", "ajuste": AJUSTE_ARRENDAMIENTOS},
    "Gross Real Estate Property": {"clave": "inmuebles_bruto"},
    "Accumulated Depreciation": {"clave": "depreciacion_acumulada"},
    "Net Mortgages & Notes": {"clave": "prestamos_por_cobrar"},
    "Total Real Estate Investments": {"formula": Formula(suma=(
        (1, "Real Estate Held for Sale"), (1, "Real Estate Equity Interests"),
        (1, "Net Real Estate Property"), (1, "Net Mortgages & Notes"),
    ))},
    "Cash & Near Cash Items": {"clave": "efectivo"},
    "Accounts Receivable": {
        "componentes": ("cuentas_por_cobrar", "renta_linea_recta_por_cobrar"),
    },
    "Other Assets": {"clave": "activos_otros"},
    "Restricted Assets": {"clave": "efectivo_restringido"},
    "Total Assets": {"clave": "activos_totales"},
    "Accounts Payable": {"clave": "cuentas_por_pagar", "ajuste": AJUSTE_DIVIDENDOS},
    "Secured & Unsecured Debt": {
        "formula": Formula(suma=((1, "Unsecured Debt"), (1, "Secured Debt"),
                                 (1, "Operating Leases"))),
        "ajuste": AJUSTE_ARRENDAMIENTOS,
    },
    "Unsecured Debt": {
        "componentes": ("notas_senior", "linea_de_credito", "prestamos_a_plazo",
                        "deuda_no_garantizada", "otras_notas_por_pagar"),
    },
    "Secured Debt": {"clave": "deuda_hipotecaria"},
    "Other Long-Term Liabilities": {"clave": "pasivos_otros"},
    "Total Liabilities": {"clave": "pasivos_totales"},
    "Total Preferred Equity": {"clave": "capital_preferente"},
    "Minority Interest": {"clave": "participacion_no_controladora"},
    "Share Capital & APIC": {"componentes": ("capital_comun", "prima_en_acciones")},
    "Retained Earnings & Other Equity": {
        "componentes": ("utilidades_retenidas", "otro_resultado_integral"),
    },
    "Total Equity": {"clave": "capital_total"},
    "Total Liabilities & Equity": {"clave": "pasivo_mas_capital"},
    "Shares Outstanding": {"clave": "acciones_en_circulacion", "formato": "conteo"},
    "Operating Leases": {"clave": "pasivo_arrendamiento"},
    "Net Debt": {
        "formula": Formula(suma=((1, "Secured & Unsecured Debt"),
                                 (-1, "Cash & Near Cash Items"))),
        "ajuste": AJUSTE_ARRENDAMIENTOS,
    },
    "Book Value per Share": {
        "formula": Formula(
            suma=((1, "Total Equity"), (-1, "Total Preferred Equity"),
                  (-1, "Minority Interest")),
            entre=((1, "Shares Outstanding"),)),
        "formato": "por_accion",
    },
    "Projects Under Development": {"clave": "desarrollo_en_proceso"},
    "Non-Depreciable Real Estate": {"clave": "terreno"},
    "Debt to Real-Estate Investment": {
        "formula": Formula(suma=((1, "Secured & Unsecured Debt"),),
                           entre=((1, "Total Real Estate Investments"),)),
        "formato": "pct",
    },
    "Total Debt to Total Capital": {
        "formula": Formula(suma=((1, "Secured & Unsecured Debt"),),
                           entre=((1, "Secured & Unsecured Debt"), (1, "Total Equity"))),
        "formato": "pct",
    },
    "Total Liabilities to Total Common Equity": {
        "formula": Formula(
            suma=((1, "Total Liabilities"),),
            entre=((1, "Total Equity"), (-1, "Total Preferred Equity"),
                   (-1, "Minority Interest"))),
        "formato": "veces",
    },
    "Tangible Common Equity Ratio": {"derivada": "capital_tangible", "formato": "pct"},
    # Sin fuente en un filing de la SEC, o sin renglón en el catálogo.
    "Mortgage Loan (REIT)": {"nota": "El catálogo lleva los préstamos por cobrar netos."},
    "Notes Receivable": {"nota": "El catálogo lleva los préstamos por cobrar netos."},
    "Allowance for Loan Losses": {"nota": "El catálogo lleva los préstamos por cobrar netos."},
    "Mortgage Backed Invt": {"nota": NOTA_NO_APLICA},
    "Other Investments": {"nota": "El catálogo no separa esta partida de otros activos."},
    "ST Liabilities & Deposits": {"nota": "El catálogo no separa el pasivo por vencimiento."},
    "Security Deposits": {"nota": "El catálogo no separa el pasivo por vencimiento."},
    "Other ST Liabilities": {"nota": "El catálogo no separa el pasivo por vencimiento."},
    "Accounting Standard": {"nota": "Siempre US GAAP en este universo."},
    "Number of Treasury Shares": {"nota": NOTA_SIN_FILING},
    "Amount of Treasury Shares": {"nota": NOTA_SIN_FILING},
    "Pension Obligations": {"nota": NOTA_NO_APLICA},
    "Capital Leases - Short Term": {"nota": "El catálogo no separa el arrendamiento financiero."},
    "Capital Leases - Long Term": {"nota": "El catálogo no separa el arrendamiento financiero."},
    "Capital Leases - Total": {"nota": "El catálogo no separa el arrendamiento financiero."},
    "Variable Rate Debt": {"nota": "Vive en las notas del 10-K, no en el balance."},
    "Fixed Rate Debt": {"nota": "Vive en las notas del 10-K, no en el balance."},
    "Number of Employees": {"nota": NOTA_SIN_FILING},
}

_MAPEO_FLUJO: dict[str, dict] = {
    "Net Income": {"clave": "utilidad_neta"},
    "Depreciation & Amortization": {"clave": "depreciacion_amortizacion"},
    "Other Non-Cash Adjustments": {"clave": "compensacion_en_acciones"},
    "Cash From Operating Activities": {"clave": "flujo_operacion"},
    "Disposal of Fixed Assets": {"clave": "venta_inmuebles"},
    "Property Additions": {"clave": "adquisicion_inmuebles", "signo": -1},
    "Property Improvements": {"clave": "desarrollo_inmuebles", "signo": -1},
    "Cash from Investing Activities": {"clave": "flujo_inversion"},
    "Dividends Paid": {"clave": "dividendos_pagados", "signo": -1},
    "Proceeds from Repayments of Borrowings": {"componentes": ("emision_deuda", "pago_deuda")},
    "Increase in Capital Stocks": {"clave": "emision_acciones"},
    "Cash from Financing Activities": {"clave": "flujo_financiamiento"},
    "Net Changes in Cash": {"clave": "cambio_neto_efectivo"},
    "EBITDA": {"clave": "ebitdare"},
    "Trailing 12M EBITDA Margin": {"derivada": "margen_ebitda", "formato": "pct",
        "nota": "El ingreso vive en el estado de resultados, no en este estado."},
    "Funds From Operations": {"derivada": "ffo_monto"},
    "FFO Per Share": {"clave": "ffo_por_accion", "formato": "por_accion"},
    "Cash Paid for Interest": {"clave": "gasto_intereses"},
    "Cash Paid for Taxes": {"clave": "impuestos"},
    "Free Cash Flow to Equity": {"formula": Formula(suma=(
        (1, "Cash From Operating Activities"), (1, "Property Additions"),
        (1, "Property Improvements"),
    ))},
    "Capital Expenditures to Real-Estate Investment": {
        "derivada": "capex_sobre_inmuebles", "formato": "pct",
    },
    "Capital Expenditures to FFO": {
        "formula": Formula(suma=((-1, "Property Additions"), (-1, "Property Improvements")),
                           entre=((1, "Funds From Operations"),)),
        "formato": "pct",
    },
    "Provision for Doubtful Accounts": {"nota": "El catálogo no separa esta partida."},
    "Changes in Non-Cash Capital": {"nota": "El catálogo no separa el capital de trabajo."},
    "Change in Investments": {"nota": "El catálogo no separa esta partida de inversión."},
    "Change in Notes": {"nota": "El catálogo no separa esta partida de inversión."},
    "Change in Mortgages": {"nota": "El catálogo no separa esta partida de inversión."},
    "Change in Real Estate Interest": {"nota": "El catálogo no separa esta partida."},
    "Other Investing Activities": {"nota": "El catálogo no separa esta partida."},
    "Preferred Dividends Other Distributions": {"nota": "El catálogo no separa esta partida."},
    "Change in Unsecured Debt": {"nota": "El catálogo no separa la emisión por tipo de deuda."},
    "Change in Secured Debt": {"nota": "El catálogo no separa la emisión por tipo de deuda."},
    "Decrease in Capital Stocks": {"nota": "El catálogo no separa la recompra."},
    "Other Financing Activities": {"nota": "El catálogo no separa esta partida."},
    "Net Cash Paid for Acquisitions": {"nota": "El catálogo lo lleva en adquisición de inmuebles."},
}

MAPEO: dict[str, dict[str, dict]] = {
    RESULTADOS: _MAPEO_RESULTADOS,
    BALANCE: _MAPEO_BALANCE,
    FLUJO: _MAPEO_FLUJO,
}


def _cargar_molde() -> dict[str, tuple[LineaBBG, ...]]:
    """El molde del JSON, ya casado con el mapeo. Es la plantilla que se usa."""
    crudo = json.loads(RUTA_MOLDE.read_text(encoding="utf-8"))
    salida: dict[str, tuple[LineaBBG, ...]] = {}
    for estado, filas in crudo.items():
        mapeo = MAPEO.get(estado, {})
        lineas = []
        for fila in filas:
            # El mapeo NO se aplica a los encabezados. El flujo de efectivo repite
            # «Cash From Operating Activities» dos veces —el título de la sección
            # y su total— y buscarlo por etiqueta le ponía la cifra también al
            # título: el mismo número dos veces, arriba y abajo del bloque, como
            # si el estado sumara dos.
            extra = ({} if not fila.get("campo_bbg")
                     else dict(mapeo.get(fila["etiqueta"], {})))
            lineas.append(LineaBBG(
                etiqueta=fila["etiqueta"],
                nivel=int(fila["nivel"]),
                signo_texto=fila.get("signo", ""),
                campo_bbg=fila.get("campo_bbg", ""),
                clave=extra.pop("clave", None),
                componentes=tuple(extra.pop("componentes", ())),
                signo=int(extra.pop("signo", 1)),
                derivada=extra.pop("derivada", ""),
                formula=extra.pop("formula", None),
                formato=extra.pop("formato", "monto"),
                ajuste=extra.pop("ajuste", ""),
                nota=extra.pop("nota", ""),
            ))
        salida[estado] = tuple(lineas)
    return salida


PLANTILLA: dict[str, tuple[LineaBBG, ...]] = _cargar_molde()


# --------------------------------------------------------------------------------------
# Los renglones que Bloomberg construye y nosotros no teníamos
# --------------------------------------------------------------------------------------

_TRAMOS_DEUDA = ("notas_senior", "linea_de_credito", "prestamos_a_plazo",
                 "deuda_no_garantizada", "deuda_hipotecaria", "otras_notas_por_pagar")
_ARRENDAMIENTOS = ("pasivo_arrendamiento",)
TRIMESTRES_TTM = 4


def _suma(fila: pd.Series, claves) -> float | None:
    vivos = [float(fila.get(c)) for c in claves
             if fila.get(c) is not None and pd.notna(fila.get(c))]
    return sum(vivos) if vivos else None


def _division(numerador, denominador) -> float | None:
    if numerador is None or denominador in (None, 0) or pd.isna(denominador):
        return None
    return float(numerador) / float(denominador)


def _multiplica(a, b) -> float | None:
    if a is None or b is None or pd.isna(a) or pd.isna(b):
        return None
    return float(a) * float(b)


def _derivar(nombre: str, fila: pd.Series, panel: pd.DataFrame, periodo) -> float | None:
    """Los renglones que Bloomberg arma y que no existen como tal en el filing.

    Recibe el panel y el periodo, además de la fila, porque algunos renglones no
    se pueden calcular con un solo corte: el crecimiento del FFO por acción
    necesita el mismo trimestre del año anterior, y el margen de EBITDA que
    Bloomberg publica es de doce meses.
    """
    def v(clave):
        x = fila.get(clave)
        return float(x) if x is not None and pd.notna(x) else None

    def ttm(clave) -> float | None:
        """Los cuatro periodos hasta el actual. Sin los cuatro, no hay TTM."""
        if clave not in panel.columns:
            return None
        serie = pd.to_numeric(panel[clave], errors="coerce")
        hasta = serie.loc[:periodo].tail(TRIMESTRES_TTM)
        return float(hasta.sum()) if len(hasta) == TRIMESTRES_TTM and hasta.notna().all() else None

    if nombre == "gastos_operativos":
        totales, intereses = v("gastos_totales"), v("gasto_intereses")
        return None if totales is None else totales - (intereses or 0.0)
    if nombre == "utilidad_operativa":
        ingresos = v("ingresos_totales")
        gastos = _derivar("gastos_operativos", fila, panel, periodo)
        return None if ingresos is None or gastos is None else ingresos - gastos
    if nombre == "no_operativo":
        partes = [v("gasto_intereses")]
        for clave in ("resultado_no_consolidadas", "otros_no_operativos"):
            valor = v(clave)
            partes.append(None if valor is None else -valor)
        vivos = [p for p in partes if p is not None]
        return sum(vivos) if vivos else None
    if nombre == "utilidad_continuas":
        # El reportado manda. Siete de las diez emisoras publican este renglón, y
        # es el que cuadra con el EPS de operaciones continuas del mismo filing;
        # derivarlo teniendo el dato es reemplazar una cifra por una cuenta.
        reportado = v("utilidad_operaciones_continuas")
        if reportado is not None:
            return reportado
        antes, impuestos = v("utilidad_antes_impuestos"), v("impuestos")
        return None if antes is None else antes - (impuestos or 0.0)
    if nombre == "utilidad_con_minoritarios":
        # Bloomberg parte de la utilidad ANTES de restar el minoritario y lo baja
        # en el renglón siguiente. Nuestro `utilidad_neta` sale de `NetIncomeLoss`,
        # que en us-gaap ya es la atribuible a la controladora: son 344.0 millones
        # en Realty Income, no 370.5. Sin sumarlo de vuelta, este renglón y el de
        # abajo salían idénticos y el minoritario aparecía restándose de la nada.
        neta = v("utilidad_neta")
        if neta is None:
            return None
        return neta + (v("utilidad_minoritarios") or 0.0)
    if nombre == "utilidad_comun":
        comun = v("utilidad_neta_comun")
        if comun is not None:
            return comun
        neta = v("utilidad_neta")
        return None if neta is None else neta - (v("dividendos_preferentes") or 0.0)
    if nombre == "ffo_monto":
        # El monto del FFO cuando la emisora solo publicó su cifra POR ACCIÓN.
        # Es la misma deducción que ya hace el panel al revés —monto entre
        # acciones— y sin ella el renglón salía vacío teniendo el dato.
        monto = v("ffo")
        if monto is not None:
            return monto
        return _multiplica(v("ffo_por_accion"), v("acciones_diluidas"))
    if nombre == "inmuebles":
        return _suma(fila, ("inmuebles_neto", "activo_arrendamiento"))
    if nombre == "inversion_total":
        return _suma(fila, ("inmuebles_neto", "activo_arrendamiento",
                            "activos_mantenidos_venta", "inversiones_no_consolidadas",
                            "prestamos_por_cobrar"))
    if nombre == "deuda":
        return _suma(fila, (*_TRAMOS_DEUDA, *_ARRENDAMIENTOS))
    if nombre == "deuda_neta":
        deuda = _derivar("deuda", fila, panel, periodo)
        return None if deuda is None else deuda - (v("efectivo") or 0.0)

    # ── Cifras por acción y payout ────────────────────────────────────────────
    if nombre == "affo_bbg_por_accion":
        # El "AFFO" de Bloomberg es nuestro FFO normalizado, no nuestro AFFO.
        return _division(v("ffo_normalizado"), v("acciones_diluidas"))
    if nombre == "payout_affo_bbg":
        return _division(v("dividendo_declarado_por_accion"),
                         _derivar("affo_bbg_por_accion", fila, panel, periodo))
    if nombre == "payout_fad":
        return _division(v("dividendo_declarado_por_accion"), v("affo_por_accion"))
    if nombre == "payout_ffo":
        return _division(v("dividendo_declarado_por_accion"), v("ffo_por_accion"))
    if nombre == "crecimiento_ffo_por_accion":
        if "ffo_por_accion" not in panel.columns:
            return None
        serie = pd.to_numeric(panel["ffo_por_accion"], errors="coerce").dropna()
        previos = serie.loc[: periodo - pd.DateOffset(years=1)]
        actual = serie.get(periodo)
        if actual is None or pd.isna(actual) or previos.empty or previos.iloc[-1] <= 0:
            return None
        return float(actual / previos.iloc[-1] - 1.0)

    # ── Márgenes ──────────────────────────────────────────────────────────────
    if nombre == "margen_ebitda":
        # Bloomberg lo publica a doce meses; con menos de cuatro trimestres no se
        # devuelve el del trimestre disfrazado de anual.
        return _division(ttm("ebitdare"), ttm("ingresos_totales"))
    if nombre == "margen_operativo":
        return _division(_derivar("utilidad_operativa", fila, panel, periodo),
                         v("ingresos_totales"))

    # ── Ratios de balance ─────────────────────────────────────────────────────
    if nombre == "valor_libros_por_accion":
        capital = v("capital_contable")
        if capital is None:
            total = v("capital_total")
            if total is None:
                return None
            capital = total - (v("capital_preferente") or 0.0) - (
                v("participacion_no_controladora") or 0.0)
        return _division(capital, v("acciones_en_circulacion"))
    if nombre == "deuda_sobre_inmuebles":
        return _division(_derivar("deuda", fila, panel, periodo),
                         _derivar("inversion_total", fila, panel, periodo))
    if nombre == "deuda_sobre_capital":
        deuda = _derivar("deuda", fila, panel, periodo)
        capital = v("capital_total")
        return None if deuda is None or capital is None else _division(deuda, deuda + capital)
    if nombre == "pasivos_sobre_capital_comun":
        capital = v("capital_contable") or v("capital_total")
        return _division(v("pasivos_totales"), capital)
    if nombre == "capital_tangible":
        capital = v("capital_contable") or v("capital_total")
        activos = v("activos_totales")
        if capital is None or activos is None:
            return None
        intangibles = (v("goodwill") or 0.0) + (v("intangibles_arrendamiento") or 0.0)
        return _division(capital - intangibles, activos - intangibles)

    # ── Ratios de flujo ───────────────────────────────────────────────────────
    if nombre == "flujo_libre_al_capital":
        operacion = v("flujo_operacion")
        if operacion is None:
            return None
        capex = (v("adquisicion_inmuebles") or 0.0) + (v("desarrollo_inmuebles") or 0.0)
        return operacion - capex
    if nombre == "capex_sobre_inmuebles":
        capex = (v("adquisicion_inmuebles") or 0.0) + (v("desarrollo_inmuebles") or 0.0)
        return _division(capex or None, _derivar("inversion_total", fila, panel, periodo))
    if nombre == "capex_sobre_ffo":
        capex = (v("adquisicion_inmuebles") or 0.0) + (v("desarrollo_inmuebles") or 0.0)
        return _division(capex or None, v("ffo"))
    return None


def _linea_por_etiqueta(estado: str) -> dict[str, LineaBBG]:
    """La primera línea que RINDE CIFRA para cada etiqueta.

    El molde repite etiquetas: «Cash From Operating Activities» es el título de
    la sección y también su total, y «EBITDA» aparece en resultados y en flujo.
    Una fórmula que apunte a la etiqueta tiene que dar con la que trae el número,
    no con el encabezado que la precede.
    """
    salida: dict[str, LineaBBG] = {}
    for linea in PLANTILLA.get(estado, ()):
        if linea.rinde_cifra and linea.etiqueta not in salida:
            salida[linea.etiqueta] = linea
    return salida


def _valor(
    linea: LineaBBG, estado: str, panel: pd.DataFrame, periodo, memo: dict
) -> float | None:
    """El valor de un renglón en un periodo, resolviendo fórmulas hacia adentro.

    La memoria se indexa por la IDENTIDAD del renglón, no por su etiqueta. El
    molde repite nombres —«Cash From Operating Activities» es el título de la
    sección y también su total— y con la etiqueta por llave el encabezado, que va
    primero y no vale nada, dejaba memorizado un `None` que el total heredaba: el
    renglón salía vacío teniendo 1,145 millones.

    Y no es solo por velocidad: es la que corta un ciclo si algún día una fórmula
    se declara en términos de sí misma. Sin ella, «Net Debt = Deuda − Efectivo»
    con «Deuda» mal declarada colgaría el proceso en vez de fallar.
    """
    llave = (estado, id(linea), periodo)
    if llave in memo:
        return memo[llave]
    memo[llave] = None  # corta el ciclo mientras se resuelve

    fila = panel.loc[periodo]
    valor: float | None
    if linea.formula is not None:
        valor = _evaluar(linea.formula, estado, panel, periodo, memo)
    elif linea.derivada:
        valor = _derivar(linea.derivada, fila, panel, periodo)
    elif linea.componentes:
        valor = _suma(fila, linea.componentes)
    elif linea.clave:
        bruto = fila.get(linea.clave)
        valor = float(bruto) if bruto is not None and pd.notna(bruto) else None
    else:
        valor = None
    if valor is not None:
        valor *= linea.signo
    memo[llave] = valor
    return valor


def _termino(estado: str, etiqueta: str, panel: pd.DataFrame, periodo, memo) -> float | None:
    linea = _linea_por_etiqueta(estado).get(etiqueta)
    return None if linea is None else _valor(linea, estado, panel, periodo, memo)


def _evaluar(
    formula: Formula, estado: str, panel: pd.DataFrame, periodo, memo: dict
) -> float | None:
    """Evalúa una `Formula` sobre el panel. Es la mitad Python del cálculo único."""
    if formula.yoy:
        serie_actual = _termino(estado, formula.yoy, panel, periodo, memo)
        anteriores = [p for p in panel.index if p <= periodo - pd.DateOffset(years=1)]
        if serie_actual is None or not anteriores:
            return None
        previo = _termino(estado, formula.yoy, panel, anteriores[-1], memo)
        if previo is None or previo <= 0:
            return None
        return serie_actual / previo - 1.0

    def suma_de(terminos) -> float | None:
        if not terminos:
            return None
        if formula.ttm:
            # Doce meses: los cuatro periodos hasta el actual, y los cuatro o nada.
            hasta = [p for p in panel.index if p <= periodo][-TRIMESTRES_TTM:]
            if len(hasta) < TRIMESTRES_TTM:
                return None
            total = 0.0
            for cada in hasta:
                parcial = suma_simple(terminos, cada)
                if parcial is None:
                    return None
                total += parcial
            return total
        return suma_simple(terminos, periodo)

    def suma_simple(terminos, cuando) -> float | None:
        vivos = []
        for signo, etiqueta in terminos:
            valor = _termino(estado, etiqueta, panel, cuando, memo)
            if valor is not None:
                vivos.append(signo * valor)
        return sum(vivos) if vivos else None

    numerador = suma_de(formula.suma)
    if not formula.entre:
        return numerador
    denominador = suma_de(formula.entre)
    if numerador is None or denominador in (None, 0):
        return None
    return numerador / denominador


def armar(panel: pd.DataFrame, estado: str, *, n_periodos: int | None = None) -> pd.DataFrame:
    """El estado en el molde de Bloomberg, ancho: renglones × periodos.

    ``panel`` es el cuadro trimestral o anual del servicio —una fila por periodo,
    una columna por concepto—. De ahí sale todo: esta función no consulta nada,
    solo reordena, deriva y aplica las convenciones.

    Salen los 186 renglones del molde, se puedan llenar o no. Un renglón en
    blanco dice "esto no lo tenemos"; un renglón ausente hace creer que Bloomberg
    tampoco lo tiene.
    """
    plantilla = PLANTILLA.get(estado)
    if plantilla is None or panel is None or panel.empty:
        return pd.DataFrame()

    # `n_periodos=None` es TODA la historia, y es lo que se quiere por omisión.
    # Recortar por omisión era una decisión de pantalla metida en la capa de
    # datos: el libro de Excel se llevaba ocho trimestres de setenta y el
    # usuario no tenía cómo pedir el resto.
    periodos = list(panel.index) if n_periodos is None else list(panel.index)[-n_periodos:]
    memo: dict = {}
    filas = []
    for linea in plantilla:
        prefijo = f"{linea.signo_texto} " if linea.signo_texto else ""
        fila = {
            "Renglón": ("    " * linea.nivel) + prefijo + linea.etiqueta,
            "nivel": linea.nivel,
            "seccion": linea.seccion,
            "formato": linea.formato,
            "campo_bbg": linea.campo_bbg,
            "ajuste": linea.ajuste,
            "nota": linea.nota,
        }
        for periodo in periodos:
            etiqueta = periodo.date().isoformat() if hasattr(periodo, "date") else str(periodo)
            fila[etiqueta] = _valor(linea, estado, panel, periodo, memo)
        filas.append(fila)
    return pd.DataFrame(filas)


def cobertura(panel: pd.DataFrame, estado: str) -> tuple[int, int]:
    """(renglones con dato, renglones que piden dato) del molde para este panel.

    Los encabezados de sección no cuentan: no piden dato. Lo que se cuenta es lo
    que Bloomberg llena y nosotros podríamos llenar.
    """
    plantilla = PLANTILLA.get(estado, ())
    piden = [ln for ln in plantilla if not ln.seccion]
    if not piden or panel is None or panel.empty:
        return (0, len(piden))
    tabla = armar(panel, estado, n_periodos=1)
    columnas = [c for c in tabla.columns
                if c not in ("Renglón", "nivel", "seccion", "formato", "campo_bbg",
                             "ajuste", "nota")]
    if not columnas:
        return (0, len(piden))
    con_dato = tabla.loc[~tabla["seccion"], columnas].notna().any(axis=1).sum()
    return (int(con_dato), len(piden))


AJUSTES = {
    "arrendamientos": AJUSTE_ARRENDAMIENTOS,
    "intereses": AJUSTE_INTERESES,
    "dividendos": AJUSTE_DIVIDENDOS,
    "fad": AJUSTE_FAD,
}

COLUMNAS_DE_APOYO = ("nivel", "seccion", "formato", "campo_bbg", "ajuste", "nota")

__all__ = [
    "AJUSTES", "BALANCE", "COLUMNAS_DE_APOYO", "ESTADOS", "FLUJO", "MAPEO",
    "NOMBRE_ESTADO", "PLANTILLA", "RESULTADOS", "RUTA_MOLDE", "LineaBBG",
    "armar", "cobertura",
]
