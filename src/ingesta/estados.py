"""Estados financieros completos: balance, resultados y flujo de efectivo.

Este módulo es la mitad **GAAP** de la ingesta. La otra mitad —el AFFO, el FFO
normalizado, el NOI— es no-GAAP, no está en XBRL y vive en ``parser_affo``. Aquí
solo entra lo que la emisora le declaró a la SEC con una etiqueta de la taxonomía.

Tres capas, y la distinción entre ellas es lo que hace auditable el resultado:

1. **Hechos crudos.** *Todo* lo que trae ``companyfacts``, sin interpretar: cada
   etiqueta us-gaap con su periodo, su unidad, su ``filed`` y el ``accession`` del
   documento donde apareció. Es la fuente de verdad y se versiona tal cual. Si
   mañana mejora la taxonomía, se rearman los estados sin volver a bajar nada.

2. **Líneas canónicas.** El catálogo de renglones que un estado financiero de un
   REIT tiene, con las etiquetas GAAP que le corresponden en orden de preferencia.
   Es compartido, y por eso cada emisora puede sobrescribirlo: el mismo renglón
   —"deuda"— lo etiqueta cada quien a su manera, y forzar un patrón común es
   exactamente el error que la taxonomía por emisora del AFFO ya resolvió.

3. **Estados armados.** La tabla ancha —renglones por periodos— a una fecha de
   corte, respetando point-in-time.

Sobre el punto 1 hay una decisión que conviene explicar. ``companyfacts`` devuelve
**todas las versiones publicadas** de cada periodo: cuando la emisora reexpresa,
el mismo trimestre reaparece con otro ``filed``. Se guardan todas. Quedarse con la
última destruiría la posibilidad de responder "¿qué se sabía en marzo de 2024?",
que es P1.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import pandas as pd

from src.config import Fuente
from src.ingesta.xbrl import clasificar_periodo

# --------------------------------------------------------------------------------------
# Los tres estados
# --------------------------------------------------------------------------------------

ESTADO_RESULTADOS = "estado_resultados"
BALANCE = "balance"
FLUJO_EFECTIVO = "flujo_efectivo"

ESTADOS = (ESTADO_RESULTADOS, BALANCE, FLUJO_EFECTIVO)

NOMBRE_ESTADO = {
    ESTADO_RESULTADOS: "Estado de resultados",
    BALANCE: "Balance general",
    FLUJO_EFECTIVO: "Estado de flujos de efectivo",
}

# El balance es un CORTE a una fecha; los otros dos son un PERIODO. Confundirlos
# es lo que hace que alguien sume cuatro balances trimestrales para armar el año.
ESTADOS_DE_SALDO = frozenset({BALANCE})


@dataclass(frozen=True)
class LineaEstado:
    """Un renglón del estado financiero y las etiquetas GAAP que lo alimentan.

    ``tags`` va en orden de preferencia: se toma la primera que la emisora haya
    reportado. Es el mismo criterio que en ``CONCEPTOS_GAAP``, y existe porque dos
    emisoras usan etiquetas distintas para el mismo renglón sin que ninguna esté
    mal: la taxonomía de la SEC admite varias.
    """

    clave: str
    etiqueta: str
    estado: str
    orden: int
    tags: tuple[str, ...] = ()
    subtotal: bool = False
    nota: str = ""


def _l(clave, etiqueta, estado, orden, tags=(), subtotal=False, nota="") -> LineaEstado:
    return LineaEstado(clave, etiqueta, estado, orden, tuple(tags), subtotal, nota)


# --------------------------------------------------------------------------------------
# Catálogo de líneas — Estado de resultados
# --------------------------------------------------------------------------------------

_RESULTADOS: tuple[LineaEstado, ...] = (
    _l("ingreso_rentas", "Ingresos por arrendamiento", ESTADO_RESULTADOS, 10, (
        # `LeaseIncome` es la que usa Realty Income, y no estaba: su renglón de
        # renta —el ingreso principal del emisor más grande del universo— salía
        # vacío mientras el resto del estado se armaba bien.
        "LeaseIncome",
        "OperatingLeaseLeaseIncome",
        "OperatingLeasesIncomeStatementLeaseRevenue",
        "OperatingLeaseLeaseIncomeExcludingVariableLeasePayment",
    )),
    _l("ingreso_renta_variable", "Renta variable sobre ventas", ESTADO_RESULTADOS, 15, (
        "OperatingLeaseVariableLeaseIncome",
    )),
    _l("ingreso_reembolsos", "Reembolsos de inquilinos", ESTADO_RESULTADOS, 20, (
        "TenantReimbursementsRevenue",
        "OperatingLeasesIncomeStatementMinimumLeaseRevenue",
    )),
    _l("ingreso_gestion", "Comisiones por administración", ESTADO_RESULTADOS, 30, (
        "ManagementFeesRevenue",
        "AssetManagementCosts",
    )),
    _l("ingreso_otros", "Otros ingresos", ESTADO_RESULTADOS, 40, (
        "OtherOperatingIncome",
        "OtherIncome",
    )),
    _l("ingresos_totales", "Ingresos totales", ESTADO_RESULTADOS, 50, (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ), subtotal=True),

    _l("gasto_operacion_inmueble", "Gastos de operación de inmuebles", ESTADO_RESULTADOS, 110, (
        "DirectCostsOfLeasedAndRentedPropertyOrEquipment",
        "CostOfRealEstateRevenue",
        "OperatingCostsAndExpenses",
    )),
    _l("gasto_predial_seguro", "Predial y seguros", ESTADO_RESULTADOS, 120, (
        "RealEstateTaxExpense",
        "RealEstateTaxesAndInsurance",
    )),
    _l("depreciacion_amortizacion", "Depreciación y amortización", ESTADO_RESULTADOS, 130, (
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "DepreciationNonproduction",
    )),
    _l("gasto_administracion", "Gastos generales y de administración", ESTADO_RESULTADOS, 140, (
        "GeneralAndAdministrativeExpense",
        "SellingGeneralAndAdministrativeExpense",
    )),
    _l("deterioro", "Deterioro de activos", ESTADO_RESULTADOS, 150, (
        "AssetImpairmentCharges",
        "ImpairmentOfRealEstate",
        "TangibleAssetImpairmentCharges",
    )),
    _l("gasto_otros", "Otros gastos de operación", ESTADO_RESULTADOS, 160, (
        "OtherCostAndExpenseOperating",
    )),
    _l("gastos_totales", "Gastos totales", ESTADO_RESULTADOS, 170, (
        "CostsAndExpenses",
        "OperatingExpenses",
    ), subtotal=True),

    _l("utilidad_operativa", "Utilidad de operación", ESTADO_RESULTADOS, 200, (
        "OperatingIncomeLoss",
    ), subtotal=True),

    _l("gasto_intereses", "Gasto por intereses", ESTADO_RESULTADOS, 210, (
        "InterestExpenseDebt",
        "InterestExpense",
        "InterestAndDebtExpense",
        "InterestExpenseNonoperating",
        "InterestExpenseOperating",
    )),
    _l("ingreso_intereses", "Ingreso por intereses", ESTADO_RESULTADOS, 220, (
        "InvestmentIncomeInterest",
        "InterestIncomeOperating",
    )),
    _l("ganancia_venta_inmuebles", "Ganancia por venta de inmuebles", ESTADO_RESULTADOS, 230, (
        "GainLossOnSaleOfProperties",
        "GainsLossesOnSalesOfInvestmentRealEstate",
        "GainLossOnDispositionOfAssets1",
        "GainLossOnSaleOfPropertiesNetOfApplicableIncomeTaxes",
    )),
    _l("resultado_no_consolidadas", "Participación en no consolidadas", ESTADO_RESULTADOS, 240, (
        "IncomeLossFromEquityMethodInvestments",
    )),
    _l("otros_no_operativos", "Otros resultados no operativos", ESTADO_RESULTADOS, 250, (
        "OtherNonoperatingIncomeExpense",
        "NonoperatingIncomeExpense",
    )),
    _l("utilidad_antes_impuestos", "Utilidad antes de impuestos", ESTADO_RESULTADOS, 260, (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ), subtotal=True),
    _l("impuestos", "Impuesto a la utilidad", ESTADO_RESULTADOS, 270, (
        "IncomeTaxExpenseBenefit",
        "CurrentIncomeTaxExpenseBenefit",
    )),
    _l("utilidad_neta", "Utilidad neta", ESTADO_RESULTADOS, 280, (
        "ProfitLoss",
        "NetIncomeLoss",
    ), subtotal=True),
    _l("utilidad_minoritarios", "Participación no controladora", ESTADO_RESULTADOS, 290, (
        "NetIncomeLossAttributableToNoncontrollingInterest",
        "MinorityInterestInNetIncomeLossOperatingPartnerships",
    )),
    _l("dividendos_preferentes", "Dividendos preferentes", ESTADO_RESULTADOS, 300, (
        "PreferredStockDividendsAndOtherAdjustments",
        "DividendsPreferredStock",
    )),
    _l("utilidad_neta_comun", "Utilidad neta atribuible a comunes", ESTADO_RESULTADOS, 310, (
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "NetIncomeLoss",
    ), subtotal=True),

    _l("utilidad_por_accion_basica", "Utilidad por acción, básica", ESTADO_RESULTADOS, 400, (
        "EarningsPerShareBasic",
        "EarningsPerShareBasicAndDiluted",
    )),
    _l("utilidad_por_accion_diluida", "Utilidad por acción, diluida", ESTADO_RESULTADOS, 410, (
        "EarningsPerShareDiluted",
        "EarningsPerShareBasicAndDiluted",
    )),
    _l("acciones_basicas", "Acciones promedio, básicas", ESTADO_RESULTADOS, 420, (
        "WeightedAverageNumberOfSharesOutstandingBasic",
    )),
    _l("acciones_diluidas", "Acciones promedio, diluidas", ESTADO_RESULTADOS, 430, (
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasicAndDiluted",
    )),
    _l("dividendo_declarado_por_accion", "Dividendo declarado por acción", ESTADO_RESULTADOS, 440, (
        "CommonStockDividendsPerShareDeclared",
        "CommonStockDividendsPerShareCashPaid",
    )),
)


# --------------------------------------------------------------------------------------
# Catálogo de líneas — Balance general
# --------------------------------------------------------------------------------------

_BALANCE: tuple[LineaEstado, ...] = (
    _l("inmuebles_bruto", "Inmuebles, costo", BALANCE, 10, (
        "RealEstateInvestmentPropertyAtCost",
        "RealEstateGrossAtCarryingValue",
    )),
    _l("depreciacion_acumulada", "Depreciación acumulada", BALANCE, 20, (
        "RealEstateInvestmentPropertyAccumulatedDepreciation",
        "AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
    )),
    _l("inmuebles_neto", "Inmuebles, neto", BALANCE, 30, (
        "RealEstateInvestmentPropertyNet",
        "RealEstateInvestmentsNet",
    ), subtotal=True),
    _l("efectivo", "Efectivo y equivalentes", BALANCE, 40, (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    )),
    _l("efectivo_restringido", "Efectivo restringido", BALANCE, 50, (
        "RestrictedCashAndCashEquivalents",
        "RestrictedCashAndInvestmentsCurrent",
    )),
    _l("cuentas_por_cobrar", "Cuentas por cobrar", BALANCE, 60, (
        "AccountsReceivableNetNoncurrent",
        "AccountsReceivableNet",
        "ReceivablesNetCurrent",
    )),
    _l("renta_linea_recta_por_cobrar", "Rentas por cobrar en línea recta", BALANCE, 70, (
        "DeferredRentReceivablesNet",
        "StraightLineRentAdjustments",
    )),
    _l("intangibles_arrendamiento", "Intangibles de arrendamiento", BALANCE, 80, (
        "FiniteLivedIntangibleAssetsNet",
        "IntangibleAssetsNetExcludingGoodwill",
    )),
    _l("goodwill", "Crédito mercantil", BALANCE, 90, ("Goodwill",)),
    _l("inversiones_no_consolidadas", "Inversiones en no consolidadas", BALANCE, 100, (
        "EquityMethodInvestments",
    )),
    _l("prestamos_por_cobrar", "Préstamos por cobrar", BALANCE, 110, (
        "NotesReceivableNet",
        "FinancingReceivableExcludingAccruedInterestAfterAllowanceForCreditLoss",
    )),
    _l("activos_mantenidos_venta", "Activos mantenidos para la venta", BALANCE, 120, (
        "AssetsHeldForSaleNotPartOfDisposalGroup",
        "DisposalGroupIncludingDiscontinuedOperationAssets",
    )),
    _l("activos_otros", "Otros activos", BALANCE, 130, (
        "OtherAssets",
        "OtherAssetsNoncurrent",
    )),
    _l("activos_totales", "Activos totales", BALANCE, 140, ("Assets",), subtotal=True),

    _l("deuda_hipotecaria", "Deuda hipotecaria", BALANCE, 210, (
        "SecuredDebt",
        "SecuredDebtOther",
    )),
    _l("notas_senior", "Notas senior no garantizadas", BALANCE, 220, (
        "UnsecuredDebt",
        "SeniorNotes",
        "UnsecuredLongTermDebt",
    )),
    _l("linea_de_credito", "Línea de crédito revolvente", BALANCE, 230, (
        "LineOfCredit",
        "LongTermLineOfCredit",
    )),
    _l("deuda_total", "Deuda total", BALANCE, 240, (
        "DebtLongtermAndShorttermCombinedAmount",
        "LongTermDebt",
        "LongTermDebtNoncurrent",
        "DebtInstrumentCarryingAmount",
    ), subtotal=True),
    _l("cuentas_por_pagar", "Cuentas por pagar y acumulados", BALANCE, 250, (
        "AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent",
        "AccountsPayableAndAccruedLiabilitiesCurrent",
    )),
    _l("intangibles_pasivo", "Intangibles de arrendamiento, pasivo", BALANCE, 260, (
        "OffMarketLeaseUnfavorable",
    )),
    _l("pasivos_otros", "Otros pasivos", BALANCE, 270, (
        "OtherLiabilities",
        "OtherLiabilitiesNoncurrent",
    )),
    _l("pasivos_totales", "Pasivos totales", BALANCE, 280, ("Liabilities",), subtotal=True),

    _l("capital_preferente", "Capital preferente", BALANCE, 310, (
        "PreferredStockValue",
        "PreferredStockValueOutstanding",
    )),
    _l("capital_comun", "Capital social", BALANCE, 320, ("CommonStockValue",)),
    _l("prima_en_acciones", "Prima en colocación de acciones", BALANCE, 330, (
        "AdditionalPaidInCapital",
        "AdditionalPaidInCapitalCommonStock",
    )),
    _l("utilidades_retenidas", "Utilidades retenidas (déficit)", BALANCE, 340, (
        "RetainedEarningsAccumulatedDeficit",
    )),
    _l("otro_resultado_integral", "Otro resultado integral acumulado", BALANCE, 350, (
        "AccumulatedOtherComprehensiveIncomeLossNetOfTax",
    )),
    _l("participacion_no_controladora", "Participación no controladora", BALANCE, 360, (
        "MinorityInterest",
    )),
    _l("capital_contable", "Capital contable de la controladora", BALANCE, 370, (
        "StockholdersEquity",
    ), subtotal=True,
        nota="Solo la parte de los accionistas comunes y preferentes de la matriz."),
    # La identidad del balance cierra contra el capital TOTAL, no contra el de la
    # controladora. Confundirlos deja un descuadre del tamaño exacto del interés
    # minoritario, que en Welltower son 1,100 millones de dólares y en Prologis
    # 4,600: cifras que hacen ver rota una lectura que está bien.
    # Capital TEMPORAL, o "mezzanine": participaciones redimibles y preferentes
    # rescatables. No es pasivo ni capital permanente, va en medio, y la identidad
    # del balance es Activo = Pasivo + temporal + permanente. En Realty Income son
    # 167 millones exactos: sin este renglón el balance descuadra por esa cifra y
    # parece un error de lectura de las otras líneas.
    _l("capital_temporal", "Capital temporal (mezzanine)", BALANCE, 372, (
        "TemporaryEquityCarryingAmountAttributableToParent",
        "TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests",
        "RedeemableNoncontrollingInterestEquityCarryingAmount",
        "RedeemableNoncontrollingInterestEquityFairValue",
        "RedeemableNoncontrollingInterestEquityOtherFairValue",
    )),
    _l("capital_total", "Capital contable total", BALANCE, 375, (
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ), subtotal=True,
        nota="Incluye la participación no controladora. Es el que cierra el balance."),
    _l("pasivo_mas_capital", "Pasivo más capital", BALANCE, 380, (
        "LiabilitiesAndStockholdersEquity",
    ), subtotal=True),
    _l("acciones_en_circulacion", "Acciones en circulación", BALANCE, 390, (
        "CommonStockSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
    )),
)


# --------------------------------------------------------------------------------------
# Catálogo de líneas — Flujo de efectivo
# --------------------------------------------------------------------------------------

_FLUJO: tuple[LineaEstado, ...] = (
    _l("flujo_operacion", "Flujo de efectivo de operación", FLUJO_EFECTIVO, 10, (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ), subtotal=True),
    _l("compensacion_en_acciones", "Compensación basada en acciones", FLUJO_EFECTIVO, 20, (
        "ShareBasedCompensation",
    )),
    _l("adquisicion_inmuebles", "Adquisición de inmuebles", FLUJO_EFECTIVO, 110, (
        "PaymentsToAcquireRealEstate",
        "PaymentsToAcquireCommercialRealEstate",
        "PaymentsToAcquireProductiveAssets",
    )),
    _l("desarrollo_inmuebles", "Desarrollo y mejoras", FLUJO_EFECTIVO, 120, (
        "PaymentsToDevelopRealEstateAssets",
        "PaymentsForCapitalImprovements",
    )),
    _l("venta_inmuebles", "Producto de venta de inmuebles", FLUJO_EFECTIVO, 130, (
        "ProceedsFromSaleOfRealEstateHeldforinvestment",
        "ProceedsFromSaleOfProductiveAssets",
        "ProceedsFromDivestitureOfBusinesses",
    )),
    _l("flujo_inversion", "Flujo de efectivo de inversión", FLUJO_EFECTIVO, 140, (
        "NetCashProvidedByUsedInInvestingActivities",
        "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations",
    ), subtotal=True),
    _l("emision_deuda", "Disposición de deuda", FLUJO_EFECTIVO, 210, (
        "ProceedsFromIssuanceOfLongTermDebt",
        "ProceedsFromNotesPayable",
        "ProceedsFromLinesOfCredit",
    )),
    _l("pago_deuda", "Amortización de deuda", FLUJO_EFECTIVO, 220, (
        "RepaymentsOfLongTermDebt",
        "RepaymentsOfNotesPayable",
        "RepaymentsOfLinesOfCredit",
    )),
    _l("emision_acciones", "Emisión de acciones", FLUJO_EFECTIVO, 230, (
        "ProceedsFromIssuanceOfCommonStock",
        "ProceedsFromIssuanceOrSaleOfEquity",
    )),
    _l("dividendos_pagados", "Dividendos pagados", FLUJO_EFECTIVO, 240, (
        "PaymentsOfDividendsCommonStock",
        "PaymentsOfDividends",
        "PaymentsOfDividendsMinorityInterest",
    )),
    _l("flujo_financiamiento", "Flujo de efectivo de financiamiento", FLUJO_EFECTIVO, 250, (
        "NetCashProvidedByUsedInFinancingActivities",
        "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
    ), subtotal=True),
    _l("cambio_neto_efectivo", "Variación neta de efectivo", FLUJO_EFECTIVO, 300, (
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
        "CashAndCashEquivalentsPeriodIncreaseDecrease",
    ), subtotal=True),
)


LINEAS: tuple[LineaEstado, ...] = _RESULTADOS + _BALANCE + _FLUJO
LINEA_POR_CLAVE: dict[str, LineaEstado] = {ln.clave: ln for ln in LINEAS}


def lineas_de(estado: str) -> tuple[LineaEstado, ...]:
    """Las líneas de un estado, en el orden en que se presentan."""
    return tuple(sorted((ln for ln in LINEAS if ln.estado == estado), key=lambda ln: ln.orden))


# --------------------------------------------------------------------------------------
# Taxonomía POR EMISORA
# --------------------------------------------------------------------------------------
#
# El mismo renglón lo etiqueta cada emisora a su manera, y ninguna está mal: la
# taxonomía de la SEC admite varias etiquetas para el mismo concepto y cada equipo
# de reporte eligió la suya. Forzar un patrón común es exactamente el error que la
# ficha del AFFO ya resolvió, así que aquí se aplica la misma regla: **la emisora
# declara SUS etiquetas y ganan sobre las compartidas**.
#
# Lo que se pone aquí NO es una corrección: es la etiqueta que ESA emisora usa.

@dataclass(frozen=True)
class FichaEstados:
    """Etiquetas propias de una emisora, por línea del estado."""

    ticker: str
    tags: dict[str, tuple[str, ...]] = field(default_factory=dict)
    nota: str = ""


FICHAS_ESTADOS: dict[str, FichaEstados] = {}


def registrar_estados(ficha: FichaEstados) -> FichaEstados:
    FICHAS_ESTADOS[ficha.ticker] = ficha
    return ficha


registrar_estados(FichaEstados(
    "O",
    {
        # Realty Income reporta el arrendamiento con la etiqueta larga que separa
        # el pago variable; la corta no existe en su taxonomía.
        "ingreso_rentas": ("OperatingLeaseLeaseIncome",),
        "deuda_total": ("DebtLongtermAndShorttermCombinedAmount", "LongTermDebt"),
    },
    nota="Concilia a nivel de la sociedad, no de la Operating Partnership.",
))

registrar_estados(FichaEstados(
    "WPC",
    {
        # W. P. Carey conserva un negocio de administración de inversiones además
        # del portafolio: sus comisiones son ingreso de operación, no otro ingreso.
        "ingreso_gestion": ("ManagementFeesRevenue", "AssetManagementCosts"),
        "prestamos_por_cobrar": ("FinancingReceivableExcludingAccruedInterestAfterAllowanceForCreditLoss",),
    },
    nota="Tiene brazo de administración de inversiones: la comisión es ingreso recurrente.",
))

registrar_estados(FichaEstados(
    "PSA",
    {
        # Public Storage consolida su participación en Shurgard: el minoritario es
        # material y va explícito.
        "participacion_no_controladora": ("MinorityInterest",),
        "utilidad_minoritarios": ("NetIncomeLossAttributableToNoncontrollingInterest",),
    },
    nota="Consolida Shurgard: el minoritario pesa y no se puede ignorar.",
))

registrar_estados(FichaEstados(
    "WELL",
    {
        # Welltower opera bajo RIDEA: buena parte del ingreso es de operación de
        # comunidades, no arrendamiento, y va en ingresos totales.
        "ingreso_rentas": ("OperatingLeaseLeaseIncome", "HealthCareOrganizationRevenue"),
        "ingresos_totales": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        # Su participación redimible va con la variante "Other" de la etiqueta. Sin
        # ella el balance descuadra por 196 millones, que es exactamente su monto.
        "capital_temporal": ("RedeemableNoncontrollingInterestEquityOtherFairValue",),
    },
    nota="Estructura RIDEA: parte del ingreso es operativo, no renta contratada.",
))

registrar_estados(FichaEstados(
    "PLD",
    {
        "ingreso_gestion": ("ManagementFeesRevenue",),
        "resultado_no_consolidadas": ("IncomeLossFromEquityMethodInvestments",),
    },
    nota="Coinversiones con terceros: el método de participación es material.",
))


def tags_de(ticker: str, clave: str) -> tuple[str, ...]:
    """Etiquetas GAAP a probar para esta línea, con las de la emisora al frente."""
    compartidas = LINEA_POR_CLAVE[clave].tags if clave in LINEA_POR_CLAVE else ()
    ficha = FICHAS_ESTADOS.get(ticker)
    propias = ficha.tags.get(clave, ()) if ficha else ()
    # `dict.fromkeys` conserva el orden y quita repetidas.
    return tuple(dict.fromkeys((*propias, *compartidas)))


# --------------------------------------------------------------------------------------
# Capa 1 — Hechos crudos
# --------------------------------------------------------------------------------------

TAXONOMIAS = ("us-gaap", "dei", "srt", "ifrs-full")

COLUMNAS_CRUDOS = (
    "ticker", "taxonomia", "tag", "unidad", "periodo_tipo",
    "fecha_inicio", "fecha_dato", "fecha_publicacion", "valor",
    "formulario", "accession", "marco",
)


def hechos_crudos(
    companyfacts: dict,
    ticker: str,
    *,
    desde: dt.date | None = None,
) -> pd.DataFrame:
    """TODO lo que la emisora declaró, sin interpretar y sin filtrar por concepto.

    Es a propósito exhaustivo. Guardar solo las etiquetas que hoy sabemos mapear
    obliga a volver a bajar todo cada vez que se amplía la taxonomía, y con el
    límite de la SEC eso son horas. Guardar el crudo hace que mejorar el mapa sea
    un `git diff` y no una re-descarga.

    Se conservan **todas las versiones** de cada periodo: cuando la emisora
    reexpresa, el mismo trimestre reaparece con otro ``filed``. Quedarse con la
    última rompería P1.
    """
    facts = companyfacts.get("facts", {})
    filas: list[dict] = []

    for taxonomia in TAXONOMIAS:
        for tag, bloque in facts.get(taxonomia, {}).items():
            for unidad, observaciones in bloque.get("units", {}).items():
                for obs in observaciones:
                    fin = _fecha(obs.get("end"))
                    filed = _fecha(obs.get("filed"))
                    if fin is None or filed is None:
                        continue
                    if desde is not None and fin < desde:
                        continue
                    inicio = _fecha(obs.get("start"))
                    filas.append(
                        {
                            "ticker": ticker,
                            "taxonomia": taxonomia,
                            "tag": tag,
                            "unidad": unidad,
                            "periodo_tipo": clasificar_periodo(inicio, fin),
                            "fecha_inicio": inicio,
                            "fecha_dato": fin,
                            "fecha_publicacion": filed,
                            "valor": float(obs["val"]),
                            "formulario": obs.get("form") or "",
                            "accession": obs.get("accn") or "",
                            "marco": obs.get("frame") or "",
                        }
                    )

    if not filas:
        return pd.DataFrame(columns=list(COLUMNAS_CRUDOS))

    df = pd.DataFrame(filas, columns=list(COLUMNAS_CRUDOS))
    # Una misma observación puede venir repetida entre documentos. La identidad de
    # un hecho es (tag, unidad, periodo, publicación): si coincide todo eso, es la
    # misma fila, no una reexpresión.
    df = df.drop_duplicates(
        ["taxonomia", "tag", "unidad", "fecha_inicio", "fecha_dato", "fecha_publicacion"]
    )
    return _ordenar(df)


def _ordenar(df: pd.DataFrame) -> pd.DataFrame:
    """Orden determinista. Sin esto, dos corridas producen diffs de git distintos."""
    columnas = ["taxonomia", "tag", "unidad", "fecha_dato", "fecha_publicacion", "fecha_inicio"]
    return df.sort_values([c for c in columnas if c in df]).reset_index(drop=True)


def _fecha(valor) -> dt.date | None:
    if not valor:
        return None
    try:
        return dt.date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


# --------------------------------------------------------------------------------------
# Capa 3 — Estados armados
# --------------------------------------------------------------------------------------

# Un balance es un CORTE; los otros dos, un PERIODO. La clasificación de XBRL los
# distingue por la duración, y aquí se respeta.
TIPOS_DE_PERIODO = ("Q", "H1", "9M", "FY")


# En Estados Unidos no se presenta un 10-Q del cuarto trimestre: el año se cierra
# con el 10-K. Por eso el Q4 no existe en XBRL de ninguna emisora, y sin él la serie
# trimestral tiene un hueco anual que rompe cualquier TTM y cualquier comparación
# contra el mismo trimestre del año pasado.
#
# Se deriva. Y la fórmula NO es la misma para toda partida:
#
# * Un FLUJO acumula, así que `Q4 = FY − 9M`.
# * Un PROMEDIO PONDERADO —el conteo de acciones— no acumula: el acumulado es el
#   promedio del periodo. Ahí la identidad es `Q4 = 4·FY − 3·9M`. Restarlos como
#   si fueran flujos da un conteo de acciones negativo, que es el defecto que ya
#   costó caro en la otra mitad de la ingesta.
# * Una cifra POR ACCIÓN sí es aditiva —el año es aproximadamente la suma de los
#   cuatro trimestres— así que va con la primera fórmula.
LINEAS_PROMEDIO = frozenset({"acciones_basicas", "acciones_diluidas"})

# Un saldo de balance no se deriva de nada: ya viene a la fecha de corte.
LINEAS_NO_DERIVABLES = frozenset(
    ln.clave for ln in _BALANCE
) | frozenset({"utilidad_por_accion_basica", "utilidad_por_accion_diluida"})


def derivar_cuarto_trimestre(
    crudos: pd.DataFrame, tags: dict[str, str]
) -> pd.DataFrame:
    """Agrega el Q4 que la SEC nunca recibe, derivándolo del año y los nueve meses.

    La ``fecha_publicacion`` del trimestre derivado es la **más tardía** de sus dos
    componentes: antes de esa fecha el número no era deducible ni con lápiz, y
    fecharlo antes sería fabricar lookahead (P1).

    Se marca con formulario ``DERIVADO`` para que en el archivo se distinga de lo
    que la emisora publicó.
    """
    if crudos.empty:
        return crudos

    usados = {t: c for c, t in tags.items() if c not in LINEAS_NO_DERIVABLES}
    vista = crudos[crudos["tag"].isin(usados)].copy()
    if vista.empty:
        return crudos
    vista["anio"] = pd.to_datetime(vista["fecha_dato"]).dt.year

    nuevas: list[dict] = []
    for (tag, anio), grupo in vista.groupby(["tag", "anio"], sort=True):
        ultimo = grupo.sort_values("fecha_publicacion").drop_duplicates(
            ["periodo_tipo", "fecha_dato"], keep="last"
        )
        anual = ultimo[ultimo["periodo_tipo"] == "FY"]
        nueve = ultimo[ultimo["periodo_tipo"] == "9M"]
        cierre = dt.date(int(anio), 12, 31)
        ya_esta = (
            (ultimo["periodo_tipo"] == "Q")
            & (pd.to_datetime(ultimo["fecha_dato"]).dt.date == cierre)
        ).any()
        if anual.empty or nueve.empty or ya_esta:
            continue

        fila_anual, fila_nueve = anual.iloc[0], nueve.iloc[0]
        clave = usados[tag]
        if clave in LINEAS_PROMEDIO:
            valor = 4 * float(fila_anual["valor"]) - 3 * float(fila_nueve["valor"])
            if valor <= 0:
                continue  # un conteo de acciones no positivo no es un dato
        else:
            valor = float(fila_anual["valor"]) - float(fila_nueve["valor"])

        nuevas.append({
            "ticker": fila_anual["ticker"],
            "taxonomia": fila_anual["taxonomia"],
            "tag": tag,
            "unidad": fila_anual["unidad"],
            "periodo_tipo": "Q",
            "fecha_inicio": dt.date(int(anio), 10, 1),
            "fecha_dato": cierre,
            "fecha_publicacion": max(
                pd.Timestamp(fila_anual["fecha_publicacion"]).date(),
                pd.Timestamp(fila_nueve["fecha_publicacion"]).date(),
            ),
            "valor": valor,
            "formulario": "DERIVADO",
            "accession": fila_anual["accession"],
            "marco": "",
        })

    if not nuevas:
        return crudos
    return _ordenar(pd.concat([crudos, pd.DataFrame(nuevas)], ignore_index=True))


def elegir_tags(crudos: pd.DataFrame, ticker: str) -> dict[str, str]:
    """Decide UNA etiqueta GAAP por renglón, para toda la emisora.

    La decisión tiene que tomarse una sola vez y sobre el conjunto completo de
    hechos, no dentro de cada tabla. Si el estado trimestral elige
    ``NetIncomeLossAvailableToCommonStockholdersBasic`` y el anual elige
    ``NetIncomeLoss`` —porque en su propio subconjunto cada uno tenía más
    cobertura—, las dos series dejan de ser comparables: "los cuatro trimestres
    suman el año" pasa a comparar dos conceptos distintos y reprueba por 16% sin
    que ninguna de las dos cifras esté mal.

    El criterio es la cobertura total: cuántos periodos distintos cubre la etiqueta
    contando trimestres, semestres y años juntos.
    """
    if crudos.empty:
        return {}
    cobertura = (
        crudos.groupby("tag")
        .apply(lambda g: len(set(zip(g["periodo_tipo"], g["fecha_dato"], strict=True))),
               include_groups=False)
        .to_dict()
    )
    elegidas: dict[str, str] = {}
    for linea in LINEAS:
        candidatas = [(cobertura.get(t, 0), t) for t in tags_de(ticker, linea.clave)]
        candidatas = [(n, t) for n, t in candidatas if n]
        if candidatas:
            # A igualdad de cobertura manda el orden de preferencia declarado, así
            # que se rompe el empate por posición y no por nombre.
            orden = {t: i for i, t in enumerate(tags_de(ticker, linea.clave))}
            elegidas[linea.clave] = max(candidatas, key=lambda c: (c[0], -orden[c[1]]))[1]
    return elegidas


def armar_estado(
    crudos: pd.DataFrame,
    ticker: str,
    estado: str,
    *,
    asof: dt.date,
    periodo_tipo: str = "Q",
    tags: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Arma un estado financiero al corte, en formato ancho: líneas × periodos.

    ``asof`` no es decorativo: solo entran hechos cuya ``fecha_publicacion`` sea
    anterior o igual al corte, y de cada periodo se toma la versión **más reciente
    conocida a esa fecha**. Es la reconstrucción point-in-time (P1), y es lo que
    permite responder "¿qué decía el balance de este emisor en marzo de 2024?" con
    lo que se sabía entonces, no con la reexpresión de después.
    """
    if crudos.empty:
        return pd.DataFrame()

    tags = elegir_tags(crudos, ticker) if tags is None else tags
    tipo_buscado = "PUNTUAL" if estado in ESTADOS_DE_SALDO else periodo_tipo
    vista = crudos.copy()
    vista["fecha_publicacion"] = pd.to_datetime(vista["fecha_publicacion"]).dt.date
    vista["fecha_dato"] = pd.to_datetime(vista["fecha_dato"]).dt.date
    vista = vista[
        (vista["fecha_publicacion"] <= asof) & (vista["periodo_tipo"] == tipo_buscado)
    ]
    if vista.empty:
        return pd.DataFrame()

    if estado in ESTADOS_DE_SALDO:
        vista = vista[vista["fecha_dato"].isin(_fechas_de_balance(vista, tags))]
        if vista.empty:
            return pd.DataFrame()

    columnas: dict[str, dict[str, float]] = {}
    procedencia: dict[str, str] = {}

    for linea in lineas_de(estado):
        tag = tags.get(linea.clave)
        if not tag:
            continue
        serie = _serie_de_linea(vista, tag)
        if serie is None:
            continue
        columnas[linea.clave] = serie
        procedencia[linea.clave] = tag

    if not columnas:
        return pd.DataFrame()

    tabla = pd.DataFrame(columnas).T
    tabla.index.name = "linea"
    tabla = tabla.reindex([ln.clave for ln in lineas_de(estado) if ln.clave in tabla.index])
    tabla.insert(0, "etiqueta", [LINEA_POR_CLAVE[c].etiqueta for c in tabla.index])
    tabla.insert(1, "tag_gaap", [procedencia[c] for c in tabla.index])
    tabla.insert(2, "subtotal", [LINEA_POR_CLAVE[c].subtotal for c in tabla.index])
    # Las columnas de periodo, de la más reciente a la más vieja.
    periodos = sorted((c for c in tabla.columns if isinstance(c, dt.date)), reverse=True)
    return tabla[["etiqueta", "tag_gaap", "subtotal", *periodos]]


def _fechas_de_balance(vista: pd.DataFrame, tags: dict[str, str]) -> set:
    """Fechas que de verdad son un corte de balance.

    XBRL trae saldos puntuales con fechas que no son cierre de nada: la portada
    del 10-Q declara las acciones en circulación a la fecha de firma —27 de octubre,
    por ejemplo—, y a veces con valor cero. Metidas al balance producen una columna
    fantasma con un solo renglón, y ese cero dispara una alarma que no corresponde
    a ningún estado financiero.

    El corte real es donde la emisora reportó su activo total.
    """
    ancla = tags.get("activos_totales")
    if not ancla:
        return set(vista["fecha_dato"])
    fechas = set(vista.loc[vista["tag"] == ancla, "fecha_dato"])
    return fechas or set(vista["fecha_dato"])


def _serie_de_linea(vista: pd.DataFrame, tag: str) -> dict | None:
    """Valores por periodo de una etiqueta, en versión point-in-time.

    De cada periodo se toma la versión publicada más reciente **dentro del corte**.
    No se mezclan etiquetas dentro de un renglón: si una emisora reportó
    ``LongTermDebt`` hasta 2023 y otra etiqueta desde 2024, pegar las dos series
    produce un salto que parece un evento de crédito y es un cambio de taxonomía.
    Cuál se usó queda declarado en la columna ``tag_gaap`` de cada estado.
    """
    sub = vista[vista["tag"] == tag]
    if sub.empty:
        return None
    sub = sub.sort_values("fecha_publicacion").drop_duplicates("fecha_dato", keep="last")
    return dict(zip(sub["fecha_dato"], sub["valor"].astype(float), strict=True))


def periodos_disponibles(crudos: pd.DataFrame, *, periodo_tipo: str = "Q") -> list[dt.date]:
    """Fechas de corte con datos, de la más reciente a la más vieja."""
    if crudos.empty:
        return []
    sub = crudos[crudos["periodo_tipo"] == periodo_tipo]
    return sorted({pd.Timestamp(f).date() for f in sub["fecha_dato"]}, reverse=True)


def cobertura_de_lineas(crudos: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Qué líneas del catálogo encontró esta emisora y con qué etiqueta.

    Es el reporte que dice si a una emisora le falta ficha: una línea sin etiqueta
    no es un cero, es un renglón que el mapa no supo encontrar.
    """
    filas = []
    tags_vistos = set(crudos["tag"]) if not crudos.empty else set()
    for linea in LINEAS:
        candidatas = tags_de(ticker, linea.clave)
        encontrada = next((t for t in candidatas if t in tags_vistos), "")
        filas.append(
            {
                "estado": linea.estado,
                "linea": linea.clave,
                "etiqueta": linea.etiqueta,
                "subtotal": linea.subtotal,
                "tag_gaap": encontrada,
                "encontrada": bool(encontrada),
                "propia_de_la_emisora": bool(
                    encontrada and encontrada in (FICHAS_ESTADOS.get(ticker).tags.get(linea.clave, ())
                                                  if ticker in FICHAS_ESTADOS else ())
                ),
            }
        )
    return pd.DataFrame(filas)


def conceptos_no_mapeados(crudos: pd.DataFrame, ticker: str, *, minimo: int = 4) -> pd.DataFrame:
    """Etiquetas que la emisora reporta con frecuencia y el catálogo ignora.

    Es la lista de trabajo para ampliar la ficha: si una emisora publica una
    etiqueta en veinte periodos y no está en ningún renglón, probablemente sea un
    renglón que falta, no ruido.
    """
    if crudos.empty:
        return pd.DataFrame(columns=["tag", "n_periodos", "unidad"])
    conocidas = {t for ln in LINEAS for t in tags_de(ticker, ln.clave)}
    sub = crudos[
        (~crudos["tag"].isin(conocidas))
        & (crudos["taxonomia"] == "us-gaap")
        & (crudos["periodo_tipo"] != "OTRO")
    ]
    if sub.empty:
        return pd.DataFrame(columns=["tag", "n_periodos", "unidad"])
    resumen = (
        sub.groupby(["tag", "unidad"])["fecha_dato"]
        .nunique()
        .reset_index(name="n_periodos")
        .sort_values("n_periodos", ascending=False)
    )
    return resumen[resumen["n_periodos"] >= minimo].reset_index(drop=True)


__all__ = [
    "BALANCE",
    "ESTADOS",
    "ESTADO_RESULTADOS",
    "FLUJO_EFECTIVO",
    "FichaEstados",
    "LINEAS",
    "LINEA_POR_CLAVE",
    "NOMBRE_ESTADO",
    "Fuente",
    "armar_estado",
    "cobertura_de_lineas",
    "conceptos_no_mapeados",
    "hechos_crudos",
    "lineas_de",
    "periodos_disponibles",
    "tags_de",
]
