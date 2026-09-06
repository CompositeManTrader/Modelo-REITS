"""Taxonomía por emisor: cada uno declara SUS etiquetas y SU estructura de tramos.

Por qué existe
==============
La primera versión resolvía las etiquetas con un solo juego de expresiones
regulares compartido por los diez emisores, ordenado por prioridad. Funciona
hasta que dos emisores usan palabras parecidas para cosas distintas, y entonces
cada arreglo es un riesgo para los demás. La lista de choques reales es larga:

* ``Non-real estate depreciation`` contiene ``real estate depreciation`` como
  subcadena, así que la depreciación de mobiliario se sumaba como si fuera de
  inmuebles: mal en un tramo y faltante en el siguiente, dos veces.
* ``FFO adjustments allocable to noncontrolling interests`` empieza con ``FFO`` y
  se resolvía al subtotal en vez de a la partida.
* ``Amortization of lease intangibles`` es un ajuste no-efectivo en un emisor y
  una comisión de arrendamiento efectivamente pagada en otro.
* W. P. Carey escribe la misma línea de impuestos de tres formas en tres
  trimestres consecutivos, moviendo un paréntesis de lugar.

Cada vez, ampliar un patrón para que cubra a un emisor podía romper a otro sin
que nada lo avisara: la conciliación del otro seguía cuadrando, con las cifras en
la línea equivocada. Es el juego del topo, y no escala a más emisores.

Cómo funciona
=============
Una **ficha** por emisor declara, en su propio vocabulario, qué es cada línea de
su conciliación. La ficha manda; los patrones compartidos quedan solo como red
para etiquetas que la ficha aún no declara, y esas se reportan como hueco.

Las etiquetas se comparan en **forma canónica**, no literal, porque el mismo
emisor cambia la redacción entre trimestres. La canonización quita lo que nunca
distingue una línea de otra —notas al pie, paréntesis aclaratorios, tipo de
guion, puntuación— y deja lo que sí. Las tres redacciones de la línea de
impuestos de W. P. Carey colapsan a la misma cadena, que es justo el punto.

Agregar un emisor es llenar una ficha, no tocar expresiones regulares. Y
``scripts/ficha.py`` genera el borrador leyendo su filing real.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# --------------------------------------------------------------------------------------
# Forma canónica de una etiqueta
# --------------------------------------------------------------------------------------

_RE_PARENTESIS = re.compile(r"\([^)]*\)")
_RE_NOTA_INICIAL = re.compile(r"^\(?\d+\)?[.)]\s*")
_RE_NO_ALFANUM = re.compile(r"[^a-z0-9\s-]")
_RE_ESPACIOS = re.compile(r"\s+")


def canonizar(etiqueta: str) -> str:
    """Reduce una etiqueta a la forma con la que se compara contra la ficha.

    Quita solo lo que nunca distingue una línea de otra:

    * notas al pie —``(a)``, ``(d)``, ``(b) (c)``— y cualquier otro paréntesis
      aclaratorio, que es de donde vienen casi todas las variantes de redacción;
    * el tipo de guion, que los emisores alternan entre ``-``, ``–`` y ``—``;
    * acentos, mayúsculas, puntuación y espacios repetidos.

    Lo que queda sí distingue. Ejemplos de colapso deliberado, los tres del mismo
    emisor en trimestres consecutivos::

        Tax expense - deferred and other            ┐
        Tax expense (benefit) - deferred and other  ├─→ "tax expense - deferred and other"
        Tax (benefit) expense - deferred and other  ┘
    """
    if not etiqueta:
        return ""
    # Los guiones se normalizan ANTES de transliterar a ASCII: el guion largo no
    # tiene equivalente ASCII, así que `encode("ascii", "ignore")` lo BORRA en vez
    # de convertirlo, y "Tax expense – deferred" y "Tax expense - deferred" dejan
    # de colapsar por una diferencia que es puramente tipográfica.
    t = str(etiqueta).replace("–", "-").replace("—", "-").replace("‒", "-").replace("―", "-")
    t = unicodedata.normalize("NFKD", t)
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    t = _RE_ESPACIOS.sub(" ", t).strip()
    t = _RE_NOTA_INICIAL.sub("", t)
    t = _RE_PARENTESIS.sub(" ", t)
    t = t.replace("&", " and ").replace("/", " ")
    t = _RE_NO_ALFANUM.sub(" ", t)
    t = _RE_ESPACIOS.sub(" ", t).strip()
    return t.strip(" -,")


# --------------------------------------------------------------------------------------
# La ficha
# --------------------------------------------------------------------------------------

# Marca para declarar que una etiqueta NO es un monto de la cascada: encabezados
# internos, subtotales de ajustes, filas de estructura. Declararlo es distinto de
# no declararlo: lo primero dice "ya lo miré y no va"; lo segundo, "no lo he visto".
IGNORAR = "__ignorar__"


@dataclass(frozen=True)
class FichaEmisor:
    """Cómo lee este emisor su propia conciliación.

    ``lineas`` mapea la forma canónica de cada etiqueta a la clave de la cascada.
    ``subtotales`` declara qué subtotales publica y en qué orden, que es la
    estructura de tramos contra la que se valida.
    """

    ticker: str
    nombre: str
    lineas: dict[str, str] = field(default_factory=dict)
    subtotales: tuple[str, ...] = ()
    nota: str = ""

    def resolver(self, etiqueta: str) -> tuple[str | None, bool]:
        """Devuelve ``(clave, declarada)``.

        ``declarada`` distingue "la ficha dice que esto no va" de "la ficha no
        sabe qué es esto". La segunda es un hueco que hay que reportar, no un
        veredicto.
        """
        clave = self.lineas.get(canonizar(etiqueta))
        if clave is None:
            return None, False
        return (None if clave == IGNORAR else clave), True


def _ficha(ticker: str, nombre: str, subtotales: tuple[str, ...], lineas: dict[str, str],
           nota: str = "") -> FichaEmisor:
    """Construye la ficha canonizando las etiquetas tal como vienen del filing.

    Se escriben con la redacción original a propósito: así la ficha se lee contra
    el documento y se puede auditar sin ejecutar nada.
    """
    return FichaEmisor(
        ticker=ticker,
        nombre=nombre,
        lineas={canonizar(k): v for k, v in lineas.items()},
        subtotales=subtotales,
        nota=nota,
    )


# --------------------------------------------------------------------------------------
# Fichas
# --------------------------------------------------------------------------------------

FICHAS: dict[str, FichaEmisor] = {}


def registrar(ficha: FichaEmisor) -> None:
    FICHAS[ficha.ticker.upper()] = ficha


def ficha_de(ticker: str) -> FichaEmisor | None:
    return FICHAS.get((ticker or "").upper())


# --------------------------------------------------------------------------------------
# O — Realty Income
# --------------------------------------------------------------------------------------
#
# Publica los tres subtotales y separa la depreciación de mobiliario de la de
# inmuebles en dos líneas cuyos nombres se contienen uno al otro. Su tabla trae,
# DEBAJO del subtotal de AFFO, el puente al AFFO diluido: esas filas no son
# partidas de la conciliación y la ficha lo dice.

registrar(_ficha(
    "O",
    "Realty Income Corporation",
    subtotales=("ffo", "ffo_normalizado", "affo"),
    lineas={
        # Tramo del FFO
        "Net income available to common stockholders": "utilidad_neta",
        "Net income": "utilidad_neta",
        "Depreciation and amortization, net of furniture, fixtures and equipment": "depreciacion_inmuebles",
        "Depreciation and amortization": "depreciacion_inmuebles",
        "Depreciation of furniture, fixtures and equipment": "depreciacion_mobiliario",
        "Provisions for impairment of real estate": "deterioro",
        "Provisions for impairment": "deterioro",
        "Gain on sales of real estate": "ganancia_venta_inmuebles",
        "Proportionate share of adjustments for unconsolidated entities": "no_consolidadas_y_minoritarios",
        "FFO adjustments allocable to noncontrolling interests": "no_consolidadas_y_minoritarios",
        "FFO available to common stockholders": "ffo",
        "Funds from operations available to common stockholders (FFO) (2)": "ffo",
        # Tramo del FFO normalizado
        "Cumulative adjustments to calculate Normalized FFO (1)": "ajustes_acumulados_ffo_normalizado",
        "Merger, transaction, and other costs, net": "partidas_no_recurrentes",
        "Executive severance charge (3)": "partidas_no_recurrentes",
        "Normalized FFO available to common stockholders": "ffo_normalizado",
        "Normalized funds from operations available to common stockholders (Normalized FFO) (2)": "ffo_normalizado",
        # Tramo del AFFO
        "Amortization of net debt discounts and deferred financing costs": "amortizacion_costos_financieros",
        "Amortization of acquired interest rate swap value (2)": "otros_ajustes_no_efectivo",
        "Leasing costs and commissions": "comisiones_arrendamiento",
        "Recurring capital expenditures": "capex_mantenimiento",
        "Amortization of share-based compensation": "compensacion_en_acciones",
        "Straight-line rent and expenses, net": "renta_linea_recta",
        "Amortization of above and below-market leases, net": "otros_ajustes_no_efectivo",
        "Provisions for credit losses on loans and financing receivables": "otros_ajustes_no_efectivo",
        "Non-cash change in allowance for credit losses": "otros_ajustes_no_efectivo",
        "Deferred tax expense": "otros_ajustes_no_efectivo",
        "Other adjustments (4)": "otros_ajustes_no_efectivo",
        "AFFO available to common stockholders": "affo",
        "Adjusted funds from operations available to common stockholders (AFFO) (2)": "affo",
        "Other non-cash items:": "otros_ajustes_no_efectivo",
        # Por acción: el parser las manda a su propia clave. Declararlas cierra el
        # último hueco de la ficha, que la prueba de completitud mide contra el filing.
        "Net income per share": "utilidad_neta",
        "Net income per common share, basic and diluted": "utilidad_neta",
        "FFO per share": "ffo",
        "FFO per diluted share": "ffo",
        "Normalized FFO per share": "ffo_normalizado",
        "Normalized FFO per diluted share": "ffo_normalizado",
        "AFFO per share": "affo",
        "AFFO per common share:": "affo",
        "AFFO per diluted share": "affo",
        "Real estate depreciation per share": "depreciacion_inmuebles",
        "Other adjustments per share (3)": "otros_ajustes_no_efectivo",
        # Estado de resultados: sí son conceptos de la cascada, en su bloque de NOI.
        "Total revenue": "ingreso_rentas",
        "Rental (including reimbursements) (1)": "ingreso_rentas",
        "Property (including reimbursements)": "gastos_operativos_inmueble",
        # DEBAJO del subtotal de AFFO: puente al diluido y cobertura del dividendo.
        # Tomarlas por partidas las sumaría dos veces al mismo tramo.
        "FFO allocable to dilutive noncontrolling interests": IGNORAR,
        "Normalized FFO allocable to dilutive noncontrolling interests": IGNORAR,
        "AFFO allocable to dilutive noncontrolling interests": IGNORAR,
        "Diluted FFO": IGNORAR,
        "Diluted Normalized FFO": IGNORAR,
        "Diluted AFFO": IGNORAR,
        "FFO after distributions": IGNORAR,
        "Normalized FFO after distributions": IGNORAR,
        "AFFO after distributions": IGNORAR,
        "Distributions paid to common stockholders": IGNORAR,
        "Cash dividends paid per common share": IGNORAR,
        "Weighted average diluted shares outstanding - FFO, Normalized FFO, and AFFO": IGNORAR,
        # Métricas operativas y del estado de resultados que no son de la cascada.
        "Basic": IGNORAR,
        "Diluted": IGNORAR,
        "Same store rent growth": IGNORAR,
        "Occupancy": IGNORAR,
        "Investment volume (at 100%)": IGNORAR,
        "Lease termination income": IGNORAR,
        "Interest income on financing receivables": IGNORAR,
        "Interest and dividend income on loans and preferred equity investments": IGNORAR,
        "Interest": IGNORAR,
        "General and administrative": IGNORAR,
        "Total expenses": IGNORAR,
        "Foreign currency and derivative loss, net": IGNORAR,
        "Equity in earnings of unconsolidated entities": IGNORAR,
        "Other income, net": IGNORAR,
        "Income before income taxes": IGNORAR,
        "Income taxes": IGNORAR,
        "Income tax expenses": IGNORAR,
        "Net income attributable to noncontrolling interests": IGNORAR,
        "Other": IGNORAR,
    },
    nota="Los tres subtotales. La conciliación va de utilidad neta a AFFO en un solo bloque.",
))


# --------------------------------------------------------------------------------------
# NNN — NNN REIT
# --------------------------------------------------------------------------------------
#
# Publica los tres subtotales en una tabla compacta, con CUATRO columnas bajo un
# encabezado de dos duraciones. Su tabla de guía repite nombres parecidos a los de
# la conciliación —"Core FFO per share", "AFFO per share"— y por eso conviene que
# la ficha diga explícitamente cuáles son de la cascada y cuáles no.

registrar(_ficha(
    "NNN",
    "NNN REIT, Inc.",
    subtotales=("ffo", "ffo_normalizado", "affo"),
    lineas={
        "Net earnings": "utilidad_neta",
        "Real estate depreciation and amortization": "depreciacion_inmuebles",
        "Gain on disposition of real estate": "ganancia_venta_inmuebles",
        "Impairment losses – depreciable real estate, net of recoveries": "deterioro",
        "FFO": "ffo",
        "Retirement and severance costs": "partidas_no_recurrentes",
        "Core FFO": "ffo_normalizado",
        "Straight-line accrued rent, net of reserves": "renta_linea_recta",
        "Net capital lease rent adjustment": "otros_ajustes_no_efectivo",
        "Below-market rent amortization": "otros_ajustes_no_efectivo",
        "Stock based compensation expense": "compensacion_en_acciones",
        "Capitalized interest expense": "otros_ajustes_no_efectivo",
        "AFFO": "affo",
        # Por acción: el parser las manda a su propia clave, pero declararlas evita
        # que caigan en los patrones compartidos.
        "Net earnings per share": "utilidad_neta",
        "FFO per share": "ffo",
        "Core FFO per share": "ffo_normalizado",
        "AFFO per share": "affo",
        "Basic": IGNORAR,
        "Diluted": IGNORAR,
        # Estado de resultados y tabla de guía.
        "Revenues": "ingreso_rentas",
        "Real estate expenses, net of tenant reimbursements": "gastos_operativos_inmueble",
        "General and administrative expenses": IGNORAR,
        "Acquisition volume": IGNORAR,
        "Disposition volume": IGNORAR,
        "Dividend per share": IGNORAR,
        "AFFO payout ratio (1)": IGNORAR,
        "Net earnings per share excluding any gains on disposition of real estate, "
        "impairment losses and retirement and severance costs": IGNORAR,
        "Real estate depreciation and amortization per share": IGNORAR,
    },
    nota="Cuatro columnas bajo un encabezado con dos duraciones: trimestre y semestre.",
))


# --------------------------------------------------------------------------------------
# ADC — Agree Realty
# --------------------------------------------------------------------------------------
#
# Concilia a nivel de la Operating Partnership, no de la acción común, así que su
# punto de partida pasa por los dividendos preferentes. Amortiza intangibles de
# arrendamiento antes del FFO y rentas sobre y bajo mercado antes del Core FFO:
# dos partidas del mismo concepto en tramos distintos.

registrar(_ficha(
    "ADC",
    "Agree Realty Corporation",
    subtotales=("ffo", "ffo_normalizado", "affo"),
    lineas={
        "Net income": "utilidad_neta",
        "Less Series A preferred stock dividends": "dividendos_preferentes",
        "Net income attributable to Operating Partnership common unitholders": "utilidad_neta",
        "Depreciation of rental real estate assets": "depreciacion_inmuebles",
        "Amortization of lease intangibles - in-place leases and leasing costs":
            "otros_ajustes_no_efectivo",
        "Provision for impairment": "deterioro",
        "Gain on sale or involuntary conversion of assets, net": "ganancia_venta_inmuebles",
        "Funds from Operations - Operating Partnership common unitholders": "ffo",
        "Amortization of above (below) market lease intangibles, net and assumed "
        "mortgage debt discount, net": "otros_ajustes_no_efectivo",
        "Core Funds from Operations - Operating Partnership common unitholders": "ffo_normalizado",
        "Straight-line accrued rent": "renta_linea_recta",
        "Stock-based compensation expense": "compensacion_en_acciones",
        "Amortization of financing costs and original issue discounts":
            "amortizacion_costos_financieros",
        "Non-real estate depreciation": "depreciacion_mobiliario",
        "Adjusted Funds from Operations - Operating Partnership common unitholders": "affo",
        "Funds from Operations per common share and partnership unit - diluted": "ffo",
        "Core Funds from Operations per common share and partnership unit - diluted":
            "ffo_normalizado",
        "Adjusted Funds from Operations per common share and partnership unit - diluted": "affo",
        "AFFO per share (1)(2)": "affo",
        "Basic": IGNORAR,
        "Diluted": IGNORAR,
        # El CapEx de ADC va en su propia tabla, no dentro de la conciliación.
        "Scheduled principal repayments": IGNORAR,
        "Capitalized interest": IGNORAR,
        "Capitalized building improvements": IGNORAR,
        "Investment volume": IGNORAR,
        "Disposition volume": IGNORAR,
        "Income and other tax expense": IGNORAR,
        "Treasury stock method dilution (5)": IGNORAR,
    },
    nota="Concilia a nivel de Operating Partnership: los preferentes entran en el puente.",
))


# --------------------------------------------------------------------------------------
# WPC — W. P. Carey
# --------------------------------------------------------------------------------------
#
# Solo dos subtotales: no publica FFO normalizado. Mete un paréntesis aclaratorio
# entre la sigla y el calificador del subtotal, y escribe su línea de impuestos de
# tres formas distintas en trimestres consecutivos — las tres colapsan a la misma
# forma canónica, así que una sola entrada las cubre.

registrar(_ficha(
    "WPC",
    "W. P. Carey Inc.",
    subtotales=("ffo", "affo"),
    lineas={
        "Net income attributable to W. P. Carey": "utilidad_neta",
        "Depreciation and amortization of real property": "depreciacion_inmuebles",
        "Impairment charges — real estate": "deterioro",
        "Gain on sale of real estate, net": "ganancia_venta_inmuebles",
        "Proportionate share of adjustments to earnings from equity method investments (a)":
            "no_consolidadas_y_minoritarios",
        "Proportionate share of adjustments for noncontrolling interests (b)":
            "no_consolidadas_y_minoritarios",
        "FFO (as defined by NAREIT) Attributable to W. P. Carey (d)": "ffo",
        "Other (gains) and losses (e)": "otros_ajustes_no_efectivo",
        "Straight-line and other leasing and financing adjustments": "renta_linea_recta",
        "Stock-based compensation": "compensacion_en_acciones",
        "Amortization of deferred financing costs": "amortizacion_costos_financieros",
        "Above- and below-market rent intangible lease amortization, net":
            "otros_ajustes_no_efectivo",
        # Una sola entrada cubre "Tax expense –", "Tax expense (benefit) –" y
        # "Tax (benefit) expense –": el paréntesis desaparece al canonizar.
        "Tax expense – deferred and other": "otros_ajustes_no_efectivo",
        "Merger and other expenses": "partidas_no_recurrentes",
        "Other amortization and non-cash items": "otros_ajustes_no_efectivo",
        "AFFO Attributable to W. P. Carey (d)": "affo",
        "FFO (as defined by NAREIT) attributable to W. P. Carey per diluted share (d)": "ffo",
        "AFFO attributable to W. P. Carey per diluted share (d)": "affo",
        "Total adjustments": IGNORAR,
        "Diluted weighted-average shares outstanding": IGNORAR,
        "Diluted earnings per share": IGNORAR,
        "Net income attributable to W. P. Carey per diluted share": IGNORAR,
        "Lease revenues": "ingreso_rentas",
        "Property expenses, excluding reimbursable tenant costs": "gastos_operativos_inmueble",
        "Operating property expenses": "gastos_operativos_inmueble",
    },
    nota="No publica FFO normalizado: su cascada va de utilidad neta a FFO y de FFO a AFFO.",
))


# --------------------------------------------------------------------------------------
# EXR — Extra Space Storage
# --------------------------------------------------------------------------------------
#
# Self storage, y se nota en la estructura: NO publica AFFO. Su cascada llega
# hasta el Core FFO y ahí termina, así que declarar dos subtotales en vez de tres
# es la lectura correcta, no una carencia.
#
# Su ganancia por venta se llama "gain on real estate assets held for sale and
# sold", que no contiene "gain on sale": el patrón compartido nunca la vio, y esa
# línea faltante era todo el descuadre del tramo del FFO.

registrar(_ficha(
    "EXR",
    "Extra Space Storage Inc.",
    subtotales=("ffo", "ffo_normalizado"),
    lineas={
        "Net income attributable to common stockholders": "utilidad_neta",
        "Net income attributable to common stockholders for diluted computations": "utilidad_neta",
        "Real estate depreciation": "depreciacion_inmuebles",
        "Amortization of intangibles": "depreciacion_inmuebles",
        "Unconsolidated joint venture real estate depreciation and amortization":
            "depreciacion_inmuebles",
        # La redacción que el patrón compartido no reconocía.
        "Gain on real estate assets held for sale and sold, net": "ganancia_venta_inmuebles",
        "(Gain) loss on real estate assets held for sale and sold, net": "ganancia_venta_inmuebles",
        "Equity in earnings of unconsolidated joint venture gain on sale of a joint venture "
        "interest": "no_consolidadas_y_minoritarios",
        "Income allocated to Operating Partnership and other noncontrolling interests":
            "no_consolidadas_y_minoritarios",
        "Income allocated to noncontrolling interest - Preferred Operating Partnership and "
        "Operating Partnership": "no_consolidadas_y_minoritarios",
        "FFO": "ffo",
        "Funds from operations attributable to common stockholders": "ffo",
        # Tramo del Core FFO
        "Non-cash interest expense related to amortization of discount on unsecured senior "
        "notes, net": "amortizacion_costos_financieros",
        "Amortization of other intangibles related to the Life Storage Merger, net of tax "
        "benefit": "otros_ajustes_no_efectivo",
        "Other adjustments (4)": "otros_ajustes_no_efectivo",
        "CORE FFO": "ffo_normalizado",
        "Core funds from operations attributable to common stockholders": "ffo_normalizado",
        # Conteos de acciones y magnitudes por acción.
        "Net income attributable to common stockholders per diluted share": "utilidad_neta",
        "Weighted average number of shares – diluted 3": IGNORAR,
        "Impact of the difference in weighted average number of shares – diluted 2": IGNORAR,
    },
    nota="No publica AFFO: su cascada termina en el Core FFO.",
))
