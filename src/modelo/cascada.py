"""Cascada NOI → FFO → FFO Normalizado → AFFO.

P3 — El AFFO es el número, no la utilidad neta ni el FFO
========================================================
Realty Income Q2 2026: utilidad neta por acción 0.37 dólares, AFFO por acción 1.09.
Razón de 2.97x. El payout sobre utilidad neta da 222% y sobre AFFO da 73%. Los
sitios financieros publican el primero y está mal.

Este módulo define la cascada línea por línea y la evalúa. La estructura es
declarativa a propósito: la interfaz la recorre para mostrar la conciliación tal
como la publica el emisor, y la validación la recorre para recalcular el AFFO
desde componentes y atarlo contra el reportado.

Las tres trampas
----------------
1. **Renta en línea recta.** La contabilidad promedia toda la renta del contrato,
   así que reconoce ingreso que aún no se cobra. Se resta.
2. **Revaluación a valor razonable.** Bajo IFRS entra al estado de resultados y es
   100% no-efectivo. Se elimina.
3. **CapEx de mantenimiento vs desarrollo.** Donde más se manipula. En portafolio
   estabilizado corre entre 10% y 20% del NOI; bajo en industrial y net lease, alto
   en oficinas y comercial. En net lease puro puede ser legítimamente cero porque lo
   paga el inquilino. Bandera si un REIT de oficinas reporta menos de 5%.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.config import (
    CAPEX_ESPERADO_POR_SECTOR,
    MEDIDA_AFFO,
    SECTORES_SIN_RENTA_EN_LINEA_RECTA,
)

SEPARADOR_SEGMENTO = "#"


def clave_base(clave: str) -> str:
    """Quita el sufijo de segmento: ``otros_ajustes_no_efectivo#1`` → la clave base.

    Un mismo concepto puede aparecer en dos tramos distintos de la conciliación de
    un emisor. El parser los guarda con sufijo para no mezclarlos; todo lo que
    razona sobre el concepto usa la clave base.
    """
    return clave.split(SEPARADOR_SEGMENTO, 1)[0]


def valor_del_concepto(componentes: dict[str, float], clave: str) -> float | None:
    """Suma TODOS los segmentos de un concepto. ``None`` si el emisor no lo reporta.

    Es la forma correcta de preguntar «¿este emisor reporta X?», y la única. Un
    ``componentes.get("renta_linea_recta")`` a secas devuelve ``None`` en cuanto el
    emisor pone ese ajuste después de su primer subtotal —que es donde va siempre,
    porque el puente al AFFO viene después del FFO—. El resultado es una alarma que
    se dispara con los seis emisores que sí lo reportan: ruido puro, y peor que
    ruido, porque tapa el caso en que de verdad falte.
    """
    partes = [
        v for k, v in componentes.items()
        if clave_base(k) == clave and v is not None
    ]
    return float(sum(partes)) if partes else None


class Bloque:
    NOI = "NOI"
    FFO = "FFO"
    FFO_NORMALIZADO = "FFO_NORMALIZADO"
    AFFO = "AFFO"


@dataclass(frozen=True)
class Linea:
    """Una línea de la conciliación.

    ``signo`` es el signo con el que la línea entra al subtotal de su bloque:
    +1 suma, −1 resta, 0 es un subtotal calculado.
    """

    clave: str
    etiqueta: str
    signo: int
    bloque: str
    patrones: tuple[str, ...] = ()
    es_trampa: bool = False
    explicacion: str = ""
    opcional: bool = True


# --------------------------------------------------------------------------------------
# Bloque 1: NOI
# --------------------------------------------------------------------------------------

LINEAS_NOI: tuple[Linea, ...] = (
    Linea(
        "ingreso_rentas",
        "Ingreso por rentas (incluye reembolsos)",
        +1,
        Bloque.NOI,
        patrones=(
            r"rental\s+(?:income|revenue)",
            r"total\s+revenues?",
            r"lease\s+revenues?",
            r"tenant\s+reimbursements?",
        ),
        opcional=False,
        explicacion=(
            "Renta contractual más reembolsos de gastos que paga el inquilino "
            "(predial, seguro, mantenimiento de áreas comunes)."
        ),
    ),
    Linea(
        "gastos_operativos_inmueble",
        "Gastos operativos del inmueble",
        -1,
        Bloque.NOI,
        patrones=(r"property\s+(?:operating\s+)?expenses?", r"rental\s+expenses?", r"operating\s+expenses?"),
        opcional=False,
        explicacion=(
            "Gasto directo del inmueble: predial, seguro, administración de la propiedad. "
            "No incluye corporativo, depreciación ni intereses."
        ),
    ),
)

# --------------------------------------------------------------------------------------
# Bloque 2: FFO (definición Nareit)
# --------------------------------------------------------------------------------------

LINEAS_FFO: tuple[Linea, ...] = (
    Linea(
        "utilidad_neta",
        "Utilidad neta",
        +1,
        Bloque.FFO,
        patrones=(
            r"net\s+income(?:\s+\(loss\))?(?:\s+available)?",
            r"net\s+(?:income|loss)",
            # NNN encabeza su conciliación con "Net earnings". Sin este patrón la
            # utilidad neta no entraba y el FFO descuadraba por su monto exacto.
            r"^\s*net\s+earnings\b",
        ),
        opcional=False,
        explicacion="Punto de partida GAAP. Está deprimida por depreciación no-efectiva.",
    ),
    Linea(
        "depreciacion_inmuebles",
        "Depreciación y amortización de inmuebles",
        +1,
        Bloque.FFO,
        patrones=(
            # "Depreciation and amortization, net of furniture, fixtures and equipment"
            # ES la depreciación de inmuebles: el "net of" ya excluyó el mobiliario.
            r"^depreciation\s+and\s+amortization",
            r"real\s+estate\s+depreciation",
            r"depreciation.*real\s+estate",
        ),
        opcional=False,
        explicacion=(
            "El ajuste central de Nareit: el inmueble no se deprecia económicamente como "
            "lo hace en libros, así que se suma de vuelta."
        ),
    ),
    Linea(
        "depreciacion_mobiliario",
        "Depreciación de mobiliario y equipo",
        -1,
        Bloque.FFO,
        patrones=(
            r"(?:non[- ]real\s+estate|corporate)\s+(?:depreciation|amortization)",
            # Solo cuando la línea ES la depreciación del mobiliario, no cuando dice
            # "net of furniture, fixtures and equipment", que es lo contrario.
            r"(?:depreciation|amortization)\s+of\s+furniture",
        ),
        explicacion=(
            "Esta sí es un gasto económico real: el mobiliario y el equipo de cómputo "
            "efectivamente se agotan. Se resta del ajuste anterior."
        ),
    ),
    Linea(
        "deterioro",
        "Provisiones por deterioro",
        +1,
        Bloque.FFO,
        patrones=(r"impairment", r"provision\s+for\s+impairment"),
        explicacion="Cargo no-efectivo por deterioro de valor. Se suma de vuelta.",
    ),
    Linea(
        "ganancia_venta_inmuebles",
        "Ganancias por venta de inmuebles",
        -1,
        Bloque.FFO,
        patrones=(r"gain[s]?\s+on\s+(?:sale|disposition)", r"\(gain\)\s*loss\s+on\s+sale"),
        explicacion=(
            "El FFO mide el flujo del negocio de rentar, no el de vender. La utilidad de "
            "venta se elimina."
        ),
    ),
    Linea(
        "dividendos_preferentes",
        "Dividendos de acciones preferentes",
        -1,
        Bloque.FFO,
        patrones=(r"preferred\s+(?:stock\s+)?dividends?", r"preferred\s+unit\s+distributions?"),
        explicacion=(
            "Puente de la utilidad neta total a la que corresponde al accionista común. "
            "Sin esta línea, la conciliación de varios emisores no cierra."
        ),
    ),
    Linea(
        "no_consolidadas_y_minoritarios",
        "Participación en no consolidadas y minoritarios",
        +1,
        Bloque.FFO,
        patrones=(
            # Esta va primero y es específica: "FFO adjustments allocable to
            # noncontrolling interests" es un ajuste, NO el subtotal de FFO.
            # Ojo: "AFFO allocable to dilutive noncontrolling interests" NO entra
            # aquí — está DEBAJO del subtotal de AFFO, es el puente al AFFO diluido.
            r"(?:ffo|affo)\s+adjustments?\s+allocable",
            r"proportionate\s+share\s+of\s+adjustments",
            r"unconsolidated\s+(?:entities|joint\s+ventures)",
            r"noncontrolling\s+interests?",
            r"equity\s+in\s+(?:earnings|income)",
        ),
        explicacion=(
            "Ajustes para reflejar la parte proporcional del REIT en coinversiones y "
            "para excluir lo que corresponde a terceros."
        ),
    ),
)

# --------------------------------------------------------------------------------------
# Bloque 3: FFO Normalizado
# --------------------------------------------------------------------------------------

LINEAS_FFO_NORMALIZADO: tuple[Linea, ...] = (
    Linea(
        "ajustes_acumulados_ffo_normalizado",
        "Ajustes acumulados para llegar al FFO Normalizado",
        +1,
        Bloque.FFO_NORMALIZADO,
        patrones=(r"cumulative\s+adjustments?\s+to\s+calculate\s+normalized",),
        explicacion=(
            "Algunos emisores presentan el puente de utilidad neta a FFO normalizado como "
            "una sola línea agregada en vez de itemizarlo. Cuando es así, el detalle vive "
            "en el suplemento y aquí solo entra el total."
        ),
    ),
    Linea(
        "partidas_no_recurrentes",
        "Partidas no recurrentes",
        +1,
        Bloque.FFO_NORMALIZADO,
        patrones=(
            r"merger.*(?:costs?|expenses?)",
            r"transaction\s+costs?",
            r"(?:loss|gain)\s+on\s+extinguishment",
            r"severance",
            r"litigation",
        ),
        explicacion=(
            "Costos de fusión, litigios, indemnizaciones, extinción de deuda. Se "
            "normalizan para que la serie sea comparable trimestre a trimestre. "
            "Ojo: si aparecen todos los trimestres, no son no-recurrentes."
        ),
    ),
)

# --------------------------------------------------------------------------------------
# Bloque 4: AFFO
# --------------------------------------------------------------------------------------

LINEAS_AFFO: tuple[Linea, ...] = (
    Linea(
        "amortizacion_costos_financieros",
        "Amortización de descuentos de deuda y costos financieros",
        +1,
        Bloque.AFFO,
        patrones=(
            # "Amortization of net debt discounts and deferred financing costs":
            # el "net" en medio rompía el patrón y la línea se perdía completa.
            r"amortization\s+of\s+(?:net\s+)?(?:deferred\s+)?(?:debt\s+)?(?:discounts?|premiums?)",
            r"amortization\s+of\s+(?:deferred\s+)?financing\s+costs?",
            r"deferred\s+financing\s+costs?",
        ),
        explicacion="Cargo contable sin salida de efectivo. Se suma.",
    ),
    Linea(
        "comisiones_arrendamiento",
        "Comisiones de arrendamiento y mejoras al inquilino",
        -1,
        Bloque.AFFO,
        patrones=(r"leasing\s+(?:costs?|commissions?)", r"tenant\s+improvements?"),
        es_trampa=True,
        explicacion=(
            "Desembolso real y recurrente para mantener ocupado el inmueble. Si el REIT "
            "no lo resta, su AFFO está inflado."
        ),
    ),
    Linea(
        "capex_mantenimiento",
        "CapEx recurrente de mantenimiento",
        -1,
        Bloque.AFFO,
        patrones=(
            r"recurring\s+capital\s+expenditures?",
            r"maintenance\s+cap(?:ital\s+)?ex",
            r"capital\s+expenditures?.*recurring",
        ),
        es_trampa=True,
        explicacion=(
            "TRAMPA. Donde más se manipula: reclasificar mantenimiento como desarrollo "
            "sube el AFFO sin que nada cambie en el inmueble. Regla de olfato: 10%–20% "
            "del NOI en portafolio estabilizado; cero es legítimo solo en net lease puro."
        ),
    ),
    Linea(
        "renta_linea_recta",
        "Ajuste de renta en línea recta",
        -1,
        Bloque.AFFO,
        patrones=(
            r"straight[- ]line\s+(?:\w+\s+){0,2}rent",
            r"straight\s*line\s+rental",
            # "Straight-line and other leasing and financing adjustments" (W. P.
            # Carey) no contiene la palabra "rent" en ningún lado.
            r"^\s*straight[- ]line\b",
        ),
        es_trampa=True,
        explicacion=(
            "TRAMPA. La contabilidad promedia toda la renta del contrato, así que "
            "reconoce ingreso que aún no se cobra. Es papel, no efectivo. Se resta."
        ),
    ),
    Linea(
        "revaluacion_valor_razonable",
        "Revaluación a valor razonable",
        -1,
        Bloque.AFFO,
        patrones=(r"fair\s+value\s+(?:adjustment|remeasurement)", r"change\s+in\s+fair\s+value"),
        es_trampa=True,
        explicacion=(
            "TRAMPA. Bajo IFRS entra al estado de resultados y es 100% no-efectivo. "
            "Se elimina por completo."
        ),
    ),
    Linea(
        "compensacion_en_acciones",
        "Compensación basada en acciones",
        +1,
        Bloque.AFFO,
        patrones=(r"stock[- ]based\s+compensation", r"share[- ]based\s+compensation"),
        explicacion=(
            "No sale efectivo, pero sí diluye. Casi todos los REITs la suman de vuelta; "
            "el costo real aparece en el conteo de acciones, no en el flujo."
        ),
    ),
    Linea(
        "otros_ajustes_no_efectivo",
        "Otros ajustes no-efectivo",
        +1,
        Bloque.AFFO,
        patrones=(
            r"other\s+(?:non[- ]cash|adjustments)",
            # "Other amortization and non-cash items": la palabra "amortization"
            # entre "other" y "non-cash" rompía el patrón de arriba.
            r"^\s*other\s+amortization",
            # "Other (gains) and losses": no es la ganancia por venta de inmuebles
            # —esa vive en el tramo del FFO— sino el saldo de partidas no operativas.
            r"^\s*other\s+\(?gains?\)?\s+and\s+\(?losses?\)?",
            # W. P. Carey escribe esta misma línea de tres formas según el trimestre
            # —"Tax expense –", "Tax expense (benefit) –", "Tax (benefit) expense –"—
            # así que el paréntesis se admite a cualquiera de los dos lados. Es la
            # clase de variación que no se descubre leyendo un solo filing.
            r"tax\s+(?:\([^)]*\)\s*)?(?:expense|benefit)s?\s*(?:\([^)]*\)\s*)?[-–—]\s*deferred",
            # "Amortization of above (below) market lease intangibles, net": el
            # paréntesis en medio rompía el patrón. Y "Above- and below-market rent
            # intangible lease amortization" mete un guion inmediatamente tras
            # "above", que el patrón tampoco admitía.
            r"above[-\s]*\(?\s*(?:and\s+|/)?\s*below\)?[- ]?\s*market",
            r"(?:above|below)[- ]market\s+lease",
            # "Below-market rent amortization": el patrón de arriba exigía la
            # palabra "lease", que NNN no usa.
            r"(?:above|below)[- ]market\s+rent",
            r"^\s*net\s+capital\s+lease\s+rent",
            # Es la bolsa general de la cascada, no una afirmación sobre el
            # carácter no-efectivo de la partida: el interés capitalizado sí es
            # salida de caja, y el AFFO lo resta por eso mismo.
            r"^\s*capitalized\s+interest",
            r"amortization\s+of\s+(?:\w+\s+){0,3}intangibles",
            r"interest\s+rate\s+swap",
            r"provisions?\s+for\s+credit\s+losses",
            r"deferred\s+tax\s+(?:expense|benefit)",
        ),
        explicacion="Amortización de rentas sobre y bajo mercado, y demás partidas de papel.",
    ),
)

SUBTOTALES: tuple[Linea, ...] = (
    Linea("noi", "NOI (Net Operating Income)", 0, Bloque.NOI, patrones=(r"net\s+operating\s+income",)),
    Linea(
        "ffo",
        "FFO (definición Nareit)",
        0,
        Bloque.FFO,
        # Solo el subtotal: "FFO available to common stockholders", "FFO per share",
        # o "FFO" a secas. Nunca "FFO adjustments allocable to ...".
        patrones=(
            r"^\s*ffo\s*$",
            # W. P. Carey escribe "FFO (as defined by NAREIT) Attributable to
            # W. P. Carey": el paréntesis se mete entre la sigla y el calificador y
            # tumbaba el subtotal entero. Sin subtotal de FFO no hay frontera de
            # tramo, así que TODA la conciliación quedaba en un solo tramo y el
            # descuadre aparecía en el AFFO, lejos de su causa.
            r"^\s*(?:total\s+)?ffo\s*(?:\([^)]*\)\s*)?(?:available|attributable|per|[-–—])\b",
            r"^\s*funds\s+from\s+operations\s*(?:\([^)]*\)\s*)?(?:available|attributable|per|[-–—])",
            r"^\s*funds\s+from\s+operations\s*$",
        ),
    ),
    Linea(
        "ffo_normalizado",
        "FFO Normalizado",
        0,
        Bloque.FFO_NORMALIZADO,
        patrones=(
            r"normalized\s+ffo\b",
            r"normalized\s+funds\s+from\s+operations",
            r"^\s*core\s+ffo\b",
            r"^\s*core\s+funds\s+from\s+operations",
        ),
    ),
    Linea(
        "affo",
        "AFFO",
        0,
        Bloque.AFFO,
        patrones=(
            r"^\s*affo\s*$",
            r"^\s*affo\s*(?:\([^)]*\)\s*)?(?:available|attributable|per|[-–—])\b",
            r"^\s*adjusted\s+funds\s+from\s+operations\s*(?:\([^)]*\)\s*)?"
            r"(?:available|attributable|per|[-–—])",
            r"^\s*adjusted\s+funds\s+from\s+operations\s*$",
        ),
    ),
)

TODAS_LAS_LINEAS: tuple[Linea, ...] = (
    LINEAS_NOI + LINEAS_FFO + LINEAS_FFO_NORMALIZADO + LINEAS_AFFO + SUBTOTALES
)
LINEA_POR_CLAVE: dict[str, Linea] = {ln.clave: ln for ln in TODAS_LAS_LINEAS}
CLAVES_TRAMPA: frozenset[str] = frozenset(ln.clave for ln in TODAS_LAS_LINEAS if ln.es_trampa)


# --------------------------------------------------------------------------------------
# Evaluación de la cascada
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoCascada:
    """Subtotales calculados y el detalle línea por línea que los produjo."""

    noi: float | None
    ffo: float | None
    ffo_normalizado: float | None
    affo: float | None
    detalle: pd.DataFrame
    faltantes: list[str] = field(default_factory=list)
    banderas: list[str] = field(default_factory=list)

    def como_dict(self) -> dict[str, float | None]:
        return {
            "noi": self.noi,
            "ffo": self.ffo,
            "ffo_normalizado": self.ffo_normalizado,
            "affo": self.affo,
        }


MAGNITUD = "magnitud"
REPORTE = "reporte"


def calcular_cascada(
    componentes: dict[str, float],
    *,
    sector: str | None = None,
    acciones_diluidas: float | None = None,
    signos: str = MAGNITUD,
) -> ResultadoCascada:
    """Recalcula NOI, FFO, FFO normalizado y AFFO desde los componentes.

    Hay dos convenciones de signo en circulación y confundirlas produce un error
    de exactamente el doble de la partida, que además cuadra consigo mismo:

    ``signos="magnitud"`` (por omisión)
        Los valores son magnitudes positivas y el signo de la línea decide si suma
        o resta. ``renta_linea_recta: 25.0`` significa "25 millones de renta en
        línea recta", que la cascada resta. Es lo que teclea un analista en la hoja
        de Inputs del Excel.

    ``signos="reporte"``
        Los valores vienen **como los presenta el emisor**, ya listos para sumarse:
        la ganancia por venta viene en −38,260 porque en el reporte está entre
        paréntesis. Es lo que entrega el parser del Exhibit 99.1, y sumarlos tal
        cual es la única forma de reproducir el subtotal que el emisor publica.
    """
    if signos not in (MAGNITUD, REPORTE):
        raise ValueError(f"Convención de signo desconocida: {signos!r}")

    filas: list[dict] = []
    faltantes: list[str] = []
    banderas: list[str] = []

    def acumular(lineas: tuple[Linea, ...], base: float | None = None) -> float | None:
        total = 0.0 if base is None else base
        hubo = base is not None
        for linea in lineas:
            # Se suman todos los segmentos del mismo concepto: 'otros_ajustes' y
            # 'otros_ajustes#1' son la misma línea de la cascada, repartida por el
            # emisor en dos tramos de su tabla.
            partes = [
                v for k, v in componentes.items()
                if clave_base(k) == linea.clave and v is not None
            ]
            if not partes:
                if not linea.opcional:
                    faltantes.append(linea.clave)
                continue
            valor = float(sum(partes))
            aporte = valor if signos == REPORTE else linea.signo * valor
            total += aporte
            hubo = True
            filas.append(
                {
                    "clave": linea.clave,
                    "etiqueta": linea.etiqueta,
                    "bloque": linea.bloque,
                    "signo": linea.signo,
                    "valor_reportado": valor,
                    "aporte": aporte,
                    "es_trampa": linea.es_trampa,
                    "explicacion": linea.explicacion,
                }
            )
        return total if hubo else None

    noi = acumular(LINEAS_NOI)
    if noi is not None:
        filas.append(_fila_subtotal("noi", "NOI (Net Operating Income)", Bloque.NOI, noi))

    ffo = acumular(LINEAS_FFO)
    if ffo is not None:
        filas.append(_fila_subtotal("ffo", "FFO (definición Nareit)", Bloque.FFO, ffo))

    ffo_norm = acumular(LINEAS_FFO_NORMALIZADO, base=ffo) if ffo is not None else None
    if ffo_norm is not None:
        filas.append(
            _fila_subtotal("ffo_normalizado", "FFO Normalizado", Bloque.FFO_NORMALIZADO, ffo_norm)
        )

    affo = acumular(LINEAS_AFFO, base=ffo_norm) if ffo_norm is not None else None
    if affo is not None:
        filas.append(_fila_subtotal("affo", "AFFO", Bloque.AFFO, affo))

    detalle = pd.DataFrame(filas)

    banderas.extend(_banderas_capex(componentes, noi, sector))
    if (
        valor_del_concepto(componentes, "renta_linea_recta") is None
        and sector not in SECTORES_SIN_RENTA_EN_LINEA_RECTA
    ):
        banderas.append(
            "No se encontró el ajuste de renta en línea recta. En un REIT con contratos "
            "con escalador, ese ajuste existe: si no aparece, el AFFO puede estar inflado."
        )

    if acciones_diluidas and affo is not None and acciones_diluidas > 0:
        filas.append(
            _fila_subtotal(
                "affo_por_accion", "AFFO por acción (diluida)", Bloque.AFFO, affo / acciones_diluidas
            )
        )
        detalle = pd.DataFrame(filas)

    return ResultadoCascada(
        noi=noi,
        ffo=ffo,
        ffo_normalizado=ffo_norm,
        affo=affo,
        detalle=detalle,
        faltantes=sorted(set(faltantes)),
        banderas=banderas,
    )


def _fila_subtotal(clave: str, etiqueta: str, bloque: str, valor: float) -> dict:
    return {
        "clave": clave,
        "etiqueta": etiqueta,
        "bloque": bloque,
        "signo": 0,
        "valor_reportado": valor,
        "aporte": valor,
        "es_trampa": False,
        "explicacion": "Subtotal calculado por la cascada.",
    }


def _banderas_capex(componentes: dict[str, float], noi: float | None, sector: str | None) -> list[str]:
    """Aplica la regla de olfato del CapEx recurrente contra el NOI."""
    if noi is None or noi <= 0:
        return []
    capex = valor_del_concepto(componentes, "capex_mantenimiento")
    if capex is None:
        return [
            "El emisor no reporta CapEx recurrente de mantenimiento por separado. "
            "En cualquier sector distinto de net lease puro eso amerita revisión manual."
        ]
    razon = float(capex) / noi
    banderas = []
    if sector:
        piso, techo = CAPEX_ESPERADO_POR_SECTOR.get(sector, (0.05, 0.20))
        if razon < piso:
            banderas.append(
                f"CapEx de mantenimiento en {razon:.1%} del NOI, por debajo del piso "
                f"esperado de {piso:.0%} para {sector}. Posible reclasificación a desarrollo."
            )
        elif razon > techo:
            banderas.append(
                f"CapEx de mantenimiento en {razon:.1%} del NOI, arriba del techo esperado "
                f"de {techo:.0%} para {sector}. El inmueble puede estar consumiendo capital."
            )
    if sector == "Oficinas" and razon < 0.05:
        banderas.append(
            "Un REIT de oficinas con CapEx de mantenimiento bajo 5% del NOI es una bandera "
            "roja: las oficinas requieren reinversión constante para retener inquilinos."
        )
    return banderas


def razon_utilidad_neta_a_affo(utilidad_neta: float, affo: float) -> float | None:
    """Cuántas veces cabe la utilidad neta en el AFFO. Muestra el tamaño del error."""
    if not utilidad_neta:
        return None
    return affo / utilidad_neta


def coherencia_temporal(por_trimestre: dict[str, float]) -> dict[str, float | bool]:
    """Verifica H1 = Q1 + Q2 y FY = Q1 + Q2 + Q3 + Q4 (prueba obligatoria 3)."""
    salida: dict[str, float | bool] = {}
    q1, q2, q3, q4 = (por_trimestre.get(k) for k in ("Q1", "Q2", "Q3", "Q4"))
    h1, fy = por_trimestre.get("H1"), por_trimestre.get("FY")
    if None not in (q1, q2, h1):
        salida["dif_h1"] = h1 - (q1 + q2)
        salida["cuadra_h1"] = abs(salida["dif_h1"]) <= max(0.01, abs(h1) * 1e-4)
    if None not in (q1, q2, q3, q4, fy):
        salida["dif_fy"] = fy - (q1 + q2 + q3 + q4)
        salida["cuadra_fy"] = abs(salida["dif_fy"]) <= max(0.01, abs(fy) * 1e-4)
    return salida


# --------------------------------------------------------------------------------------
# Los escalones que la pantalla dibuja
# --------------------------------------------------------------------------------------

# El puente se nombra por el PAR de subtotales que une, nunca por su posición en la
# cascada. No todo emisor publica los cuatro escalones: Realty Income salta el FFO
# Nareit y va de la utilidad neta al FFO normalizado en un solo brinco; W. P. Carey
# no normaliza y va del FFO Nareit directo al AFFO. Con etiquetas por posición, ese
# salto quedaba rotulado con los ajustes del escalón ausente —"depreciación" sobre
# un puente que también trae las partidas no recurrentes—, que es afirmar sobre la
# cifra del emisor algo que el emisor no dijo.
PUENTES_DE_CASCADA: dict[tuple[str, str], str] = {
    ("utilidad_neta", "ffo"): "depreciación<br>y deterioro",
    ("utilidad_neta", "ffo_normalizado"): "depreciación y<br>no recurrentes",
    ("utilidad_neta", "affo"): "todos los<br>ajustes",
    ("ffo", "ffo_normalizado"): "partidas no<br>recurrentes",
    ("ffo", "affo"): "no recurrentes,<br>renta y CapEx",
    ("ffo_normalizado", "affo"): "renta lineal<br>y CapEx",
}


def escalones_de_cascada(
    componentes: dict[str, float], *, medida_flujo: str = MEDIDA_AFFO
) -> list[tuple[str, float, bool]]:
    """Subtotales y puentes de la cascada, en el orden en que se dibujan.

    Devuelve ``(etiqueta, valor, es_subtotal)``. Un escalón que el emisor no publica
    se omite, y el puente que lo cruza se nombra por los dos subtotales que quedan
    unidos, no por la posición que ocupa.

    ``medida_flujo`` decide el último escalón: quien reporta Core FFO no publica un
    AFFO debajo —el FFO normalizado ES su medida final—, y dibujarlo dos veces con
    dos nombres sugeriría un puente que ese emisor nunca cruzó.
    """
    escalera = [("Utilidad neta", "utilidad_neta"), ("FFO Nareit", "ffo")]
    if medida_flujo == MEDIDA_AFFO:
        escalera += [("FFO normalizado", "ffo_normalizado"), (MEDIDA_AFFO, "affo")]
    else:
        escalera.append((medida_flujo, "ffo_normalizado"))

    presentes = [
        (nombre, clave, valor)
        for nombre, clave in escalera
        # Por clave base: el parser le pone sufijo de segmento (`ffo#2`) a todo
        # concepto que aparece en más de un tramo, y un `.get("ffo")` a secas se
        # queda en blanco justo en las conciliaciones más completas.
        if (valor := valor_del_concepto(componentes, clave)) is not None
    ]

    pasos: list[tuple[str, float, bool]] = []
    for i, (nombre, clave, valor) in enumerate(presentes):
        if i:
            _, clave_previa, anterior = presentes[i - 1]
            pasos.append((
                PUENTES_DE_CASCADA.get((clave_previa, clave), "ajustes"),
                valor - anterior,
                False,
            ))
        pasos.append((nombre, valor, True))
    return pasos
