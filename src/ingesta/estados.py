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

    ``alternativas_excluyentes`` marca los renglones cuyas etiquetas son NOMBRES
    distintos de la misma partida, no partidas distintas: la emisora reporta una
    sola de ellas en cada corte. Solo ahí se permite empalmar dos etiquetas que
    nunca coinciden en un periodo —el empalme normal exige traslape para poder
    comprobarlo—, y aun así el resultado tiene que sostenerse contra una prueba
    independiente. Ver ``elegir_cadenas``.
    """

    clave: str
    etiqueta: str
    estado: str
    orden: int
    tags: tuple[str, ...] = ()
    subtotal: bool = False
    nota: str = ""
    alternativas_excluyentes: bool = False


def _l(
    clave, etiqueta, estado, orden, tags=(), subtotal=False, nota="",
    alternativas_excluyentes=False,
) -> LineaEstado:
    return LineaEstado(
        clave, etiqueta, estado, orden, tuple(tags), subtotal, nota,
        alternativas_excluyentes,
    )


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
        # Welltower se cambió a esta en el cuarto trimestre de 2024 y nadie la
        # seguía: `InterestExpenseDebt` se detiene el 30 de septiembre de 2024 y
        # `InterestExpenseBorrowings` continúa hasta hoy, en la MISMA taxonomía
        # estándar y dentro de `companyfacts`. Su ausencia dejaba a la emisora
        # más grande del universo sin EBITDAre, sin costo de deuda y sin spread
        # —dos criterios medibles de cinco— por una etiqueta no mapeada.
        "InterestExpenseBorrowings",
        "InterestExpenseDebtExcludingAmortization",
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
        # Le pega DIRECTO al flujo de los comunes: es lo que se paga antes que
        # ellos. Cinco de diez emisoras lo publican con esta etiqueta.
        "PreferredStockDividendsIncomeStatementImpact",
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
    _l("terreno", "Terreno", BALANCE, 12, (
        "Land",
        "LandAndLandImprovements",
    )),
    _l("edificios", "Edificios y mejoras", BALANCE, 14, (
        "InvestmentBuildingAndBuildingImprovements",
        "BuildingsAndImprovementsGross",
    )),
    _l("desarrollo_en_proceso", "Desarrollo en proceso", BALANCE, 16, (
        "DevelopmentInProcess",
        "ConstructionInProgressGross",
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
        # La etiqueta corta la usan seis de las diez y no estaba: el renglón
        # aparecía en UNA emisora de diez.
        "RestrictedCash",
    )),
    _l("cuentas_por_cobrar", "Cuentas por cobrar", BALANCE, 60, (
        "AccountsReceivableNetNoncurrent",
        "AccountsReceivableNet",
        "ReceivablesNetCurrent",
    )),
    _l("renta_linea_recta_por_cobrar", "Rentas por cobrar en línea recta", BALANCE, 70, (
        "DeferredRentReceivablesNet",
        "StraightLineRentAdjustments",
        "StraightLineRent",
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
    # Dos tramos más, para el emisor que no publica ningún total de deuda.
    #
    # Extra Space no tiene UN renglón de deuda total: ni estándar ni de extensión.
    # Lo que publica son cuatro instrumentos por separado —notas senior 9,461 MM,
    # revolvente 1,617, no garantizada 1,495 y otras notas 1,073— y sumar solo los
    # dos primeros dejaba fuera 2,568 MM, un 19% de su deuda. En un ratio de
    # apalancamiento ese error va en la dirección peligrosa: la emisora se ve más
    # sana de lo que está.
    #
    # `deuda_no_garantizada` nace SIN etiquetas por omisión a propósito. Su
    # candidata natural, `UnsecuredDebt`, ya alimenta a `notas_senior`, y en las
    # emisoras que la usan para eso —Welltower— tener las dos líneas leyendo la
    # misma etiqueta contaría la deuda dos veces. Solo la declara quien la reporta
    # aparte de sus notas senior.
    _l("deuda_no_garantizada", "Deuda no garantizada", BALANCE, 235, ()),
    _l("otras_notas_por_pagar", "Otras notas por pagar", BALANCE, 236, (
        "OtherNotesPayable",
    )),
    _l("deuda_total", "Deuda total", BALANCE, 240, (
        # `DebtLongtermAndShorttermCombinedAmount` es la etiqueta canónica y casi
        # nadie la usa. `NotesPayable` es la que Realty Income reporta hoy, y sin
        # ella su deuda se quedaba en 2017: no había apalancamiento ni NAV para el
        # emisor más grande del universo.
        "DebtLongtermAndShorttermCombinedAmount",
        "NotesPayable",
        "LongTermDebt",
        "LongTermDebtNoncurrent",
        "DebtInstrumentCarryingAmount",
        "DebtAndCapitalLeaseObligations",
        "LiabilitiesSubjectToCompromiseDebt",
    ), subtotal=True),
    _l("cuentas_por_pagar", "Cuentas por pagar y acumulados", BALANCE, 250, (
        "AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent",
        "AccountsPayableAndAccruedLiabilitiesCurrent",
    )),
    _l("intangibles_pasivo", "Intangibles de arrendamiento, pasivo", BALANCE, 260, (
        "OffMarketLeaseUnfavorable",
        # El arrendamiento por debajo de mercado es un pasivo intangible que se
        # amortiza CONTRA la renta: infla el ingreso reportado sin efectivo
        # detrás. Siete de diez emisoras lo publican y no se estaba leyendo.
        "BelowMarketLeaseNet",
    )),
    # La ESCALERA DE VENCIMIENTOS. No es un renglón del balance sino una nota,
    # y es la que dice cuánta deuda hay que refinanciar y cuándo. Para un REIT
    # apalancado es la diferencia entre un balance sano y uno que depende de que
    # el mercado de crédito siga abierto el año que entra: el apalancamiento
    # total no distingue entre deber a doce meses y deber a diez años. Seis de
    # las diez emisoras la publican y no se estaba leyendo ninguna.
    _l("vencimiento_12m", "Vencimientos a 12 meses", BALANCE, 241, (
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths",
        "LongTermDebtMaturitiesRepaymentsOfPrincipalRemainderOfFiscalYear",
    )),
    _l("vencimiento_ano_2", "Vencimientos al año 2", BALANCE, 242, (
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo",
    )),
    _l("vencimiento_ano_3", "Vencimientos al año 3", BALANCE, 243, (
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree",
    )),
    _l("vencimiento_ano_4", "Vencimientos al año 4", BALANCE, 244, (
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour",
    )),
    _l("vencimiento_ano_5", "Vencimientos al año 5", BALANCE, 245, (
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive",
    )),
    _l("vencimiento_despues", "Vencimientos posteriores", BALANCE, 246, (
        "LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive",
    )),
    # El arrendamiento operativo es deuda por otro nombre: obliga a pagar renta
    # de un terreno durante décadas. Siete de diez lo publican.
    _l("pasivo_arrendamiento", "Pasivo por arrendamiento operativo", BALANCE, 250, (
        "OperatingLeaseLiability",
        "OperatingLeaseLiabilityNoncurrent",
    )),
    _l("activo_arrendamiento", "Activo por derecho de uso", BALANCE, 95, (
        "OperatingLeaseRightOfUseAsset",
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
    # El capital mezzanine es el renglón con MÁS nombres de toda la taxonomía, y
    # es el que rompía veintiséis de los treinta y cinco descuadres del almacén.
    # Va entre el pasivo y el capital permanente, así que si no se lee, el balance
    # no cierra por su tamaño exacto — y eso es justo lo que pasaba: 12.3 MM en
    # Public Storage, 7.7 MM en W. P. Carey.
    #
    # Las etiquetas son alternativas EXCLUYENTES: la emisora publica una sola por
    # corte y va cambiando de nombre con los años. La prueba de que son la misma
    # partida está en los periodos donde W. P. Carey reportó dos a la vez, y
    # coinciden al peso: `TemporaryEquityCarryingAmount` = 7.7 MM y
    # `TemporaryEquityRedemptionValue` = 7.7 MM en el cierre de 2009.
    #
    # El orden importa: primero el importe EN LIBROS, que es lo que suma al
    # balance, y el valor de redención solo cuando la emisora no publicó otro.
    _l("capital_temporal", "Capital temporal (mezzanine)", BALANCE, 372, (
        "TemporaryEquityCarryingAmountAttributableToParent",
        "TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests",
        # La etiqueta canónica y más corta, la que usaban las dos emisoras antes
        # de 2012, no estaba mapeada.
        "TemporaryEquityCarryingAmount",
        "RedeemableNoncontrollingInterestEquityCarryingAmount",
        "RedeemableNoncontrollingInterestEquityOtherCarryingAmount",
        "RedeemableNoncontrollingInterestEquityCommonCarryingAmount",
        "RedeemableNoncontrollingInterestEquityFairValue",
        "RedeemableNoncontrollingInterestEquityOtherFairValue",
        "TemporaryEquityRedemptionValue",
    ), alternativas_excluyentes=True),
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
    """Etiquetas propias de una emisora, por línea del estado.

    ``tags_de_instancia`` nombra las etiquetas que hay que ir a buscar al
    documento XBRL del filing porque `companyfacts` no las expone: esa API solo
    publica taxonomías estándar y deja fuera las EXTENSIONES que cada emisora
    define para sí misma. Es un camino más caro —uno a tres megabytes por
    filing— así que se declara por emisora y solo donde el dato no existe de
    otra forma. Ver ``src/ingesta/instancia.py``.
    """

    ticker: str
    tags: dict[str, tuple[str, ...]] = field(default_factory=dict)
    nota: str = ""
    tags_de_instancia: tuple[str, ...] = ()


def etiquetas_de_instancia(ticker: str) -> set[str]:
    """Las etiquetas de extensión declaradas para esta emisora, o vacío."""
    ficha = FICHAS_ESTADOS.get(ticker)
    return set(ficha.tags_de_instancia) if ficha else set()


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
    "EXR",
    {
        # Extra Space etiqueta su gasto por intereses con una extensión PROPIA, y
        # `companyfacts` solo publica taxonomías estándar: el dato no está ahí.
        # `InterestExpense` de la taxonomía estándar se detiene en el primer
        # trimestre de 2024 y a partir de ahí la emisora se quedaba sin EBITDAre,
        # sin costo de deuda y sin spread — dos criterios medibles de cinco.
        #
        # El número está impreso en su estado de resultados y sale del documento
        # XBRL del propio filing: 146.7 millones en el segundo trimestre de 2026.
        "gasto_intereses": (
            "InterestExpenseExcludingAmortizationOfDebtDiscountPremium",
            "InterestExpense",
        ),
        # Reporta la no garantizada aparte de sus notas senior, así que aquí las
        # dos líneas son dos instrumentos distintos y no un doble conteo.
        "deuda_no_garantizada": ("UnsecuredDebt",),
    },
    tags_de_instancia=("InterestExpenseExcludingAmortizationOfDebtDiscountPremium",),
    nota="Su gasto por intereses vive en una etiqueta de extensión, fuera de companyfacts.",
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
    """Orden determinista. Sin esto, dos corridas producen diffs de git distintos.

    ``concepto`` entra al orden desde que un mismo `tag` puede alimentar dos
    renglones: sin él las dos filas quedan empatadas en todas las llaves y el
    desempate lo decide el orden de llegada, que no es estable.
    """
    columnas = ["taxonomia", "tag", "concepto", "unidad",
                "fecha_dato", "fecha_publicacion", "fecha_inicio"]
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
# El Q4 es el hueco SEGURO, pero no es el único. NNN publicó su 10-Q del segundo
# trimestre de 2026 con la columna del semestre y la del trimestre, y el primer
# trimestre no aparece en `companyfacts` por ninguna etiqueta: el hueco queda a
# mitad de la serie y mata el TTM de los dos cortes siguientes. La aritmética que
# rescata el Q4 lo rescata igual —`Q1 = H1 − Q2`—, así que se generaliza: de un
# acumulado y los trimestres que lo componen, se deriva el que falte cuando falta
# EXACTAMENTE uno. Nunca se fabrica un semestre ni un acumulado: solo trimestres.
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


def _trimestres(inicio, fin) -> int | None:
    """Cuántos trimestres calendario cubre el periodo. ``None`` si no es exacto.

    Devolver ``None`` ante cualquier duda es lo que hace segura la derivación: un
    ejercicio de 52/53 semanas no cae en frontera de mes, y ahí no se resta nada.
    """
    if inicio is None or fin is None:
        return None
    try:
        i = pd.Timestamp(inicio)
        f = pd.Timestamp(fin) + pd.Timedelta(days=1)
    except (TypeError, ValueError):
        return None
    if pd.isna(i) or pd.isna(f) or f.day != i.day:
        return None
    meses = (f.year - i.year) * 12 + (f.month - i.month)
    if meses <= 0 or meses % 3:
        return None
    return meses // 3


# Cuántos trimestres cubre cada tipo de periodo. Sirve para reconstruir el inicio
# cuando el hecho no lo trae: `companyfacts` siempre manda `start`, pero un hecho
# derivado o armado a mano puede no tenerlo, y ahí la duración la da el tipo.
TRIMESTRES_POR_TIPO = {"Q": 1, "H1": 2, "9M": 3, "FY": 4}


def _span(fila) -> tuple[dt.date, dt.date, int] | None:
    """Inicio, fin y número de trimestres del periodo. ``None`` si no se puede.

    El inicio REAL manda siempre que el hecho lo traiga —y `companyfacts` siempre
    lo trae—. Solo cuando falta se reconstruye a partir del tipo de periodo. La
    distinción no es cosmética: sustituir la frontera real por una calculada
    convierte un ejercicio de 52/53 semanas en uno de meses cerrados sin avisar, y
    entonces la resta despeja un "trimestre" cuyas fechas no son las de nadie.
    """
    fin = fila["fecha_dato"]
    if fin is None or pd.isna(fin):
        return None
    fin = pd.Timestamp(fin).date()
    inicio = fila["fecha_inicio"]
    if inicio is not None and not pd.isna(inicio):
        inicio = pd.Timestamp(inicio).date()
        # La duración se toma del calendario; si el periodo no cae en trimestres
        # cerrados, el conteo lo presta el tipo, pero las FECHAS siguen siendo las
        # reales y el hueco que salga tendrá que probar por su cuenta que es un
        # trimestre.
        n = _trimestres(inicio, fin) or TRIMESTRES_POR_TIPO.get(fila["periodo_tipo"])
        return (inicio, fin, n) if n else None
    n = TRIMESTRES_POR_TIPO.get(fila["periodo_tipo"])
    if not n:
        return None
    inicio = (pd.Timestamp(fin) + pd.Timedelta(days=1) - pd.DateOffset(months=3 * n)).date()
    return inicio, fin, n


def derivar_trimestres_faltantes(
    crudos: pd.DataFrame,
    tags: dict[str, str | tuple[str, ...]],
    *,
    por: str = "tag",
) -> pd.DataFrame:
    """Agrega los trimestres que la SEC nunca recibe, restándolos de un acumulado.

    El caso conocido es el Q4 —no hay 10-Q de cierre, así que ``Q4 = FY − 9M``—,
    pero la identidad es general: de un acumulado de *n* trimestres y un tramo
    contiguo de *k*, sale el trimestre que falta si y solo si ``n − k == 1``. Eso
    cubre el Q4 (``FY − 9M``) y también el hueco a media serie (``Q1 = H1 − Q2``),
    que es el que dejó a NNN sin EBITDAre en los dos últimos cortes.

    Solo se acepta el tramo que empieza o termina junto con el acumulado: un hueco
    en medio no se puede despejar con una sola resta, y adivinarlo sería inventar.
    Nunca se emite algo que no sea un trimestre.

    La ``fecha_publicacion`` del trimestre derivado es la **más tardía** de sus dos
    componentes: antes de esa fecha el número no era deducible ni con lápiz, y
    fecharlo antes sería fabricar lookahead (P1).

    Se marca con formulario ``DERIVADO`` para que en el archivo se distinga de lo
    que la emisora publicó.
    """
    if crudos.empty or por not in crudos.columns:
        return crudos

    clave_de: dict[str, str] = {}
    for clave, valor in tags.items():
        if clave in LINEAS_NO_DERIVABLES:
            continue
        for tag in (valor,) if isinstance(valor, str) else valor:
            clave_de[clave if por != "tag" else tag] = clave

    vista = crudos[crudos[por].isin(clave_de)]
    if vista.empty:
        return crudos

    nuevas: list[dict] = []
    for grupo, filas in vista.groupby(por, sort=True):
        # La identidad de un hecho es su periodo, no su fecha de inicio: dos hechos
        # pueden traer `start` vacío y el mismo cierre —el Q4 y el año— sin ser el
        # mismo dato. Deduplicar por el inicio se comía el trimestre publicado y
        # luego lo "derivaba", que es exactamente lo que no debe pasar.
        conocidas = (
            filas.sort_values("fecha_publicacion")
            .drop_duplicates(["periodo_tipo", "fecha_dato"], keep="last")
        )
        # `tramos` clasifica cada periodo por su duración real, no por su etiqueta:
        # es lo que permite tratar al FY y al H1 con la misma aritmética.
        tramos = {}
        for fila in conocidas.to_dict("records"):
            span = _span(fila)
            if span:
                tramos[span[:2]] = (span[2], fila)
        promedio = clave_de[grupo] in LINEAS_PROMEDIO

        # Punto fijo: derivar el Q1 de un semestre puede habilitar el Q3 de los
        # nueve meses, y ese el Q4 del año. Se repite hasta que no salga nada nuevo.
        while True:
            derivada = _un_trimestre_faltante(tramos, promedio)
            if derivada is None:
                break
            span, n_fila = derivada
            tramos[span] = n_fila
            nuevas.append(n_fila[1])

    if not nuevas:
        return crudos
    return _ordenar(pd.concat([crudos, pd.DataFrame(nuevas)], ignore_index=True))


def _un_trimestre_faltante(tramos: dict, promedio: bool):
    """El primer trimestre despejable de un acumulado, o ``None`` si no hay."""
    for (ini_c, fin_c), (n, fila_c) in sorted(tramos.items(), key=lambda kv: kv[1][0]):
        if n < 2:
            continue
        for (ini_s, fin_s), (k, fila_s) in tramos.items():
            if k >= n:
                continue
            if ini_s == ini_c and fin_s < fin_c:      # tramo inicial: falta la cola
                hueco = (pd.Timestamp(fin_s) + pd.Timedelta(days=1)).date(), fin_c
            elif fin_s == fin_c and ini_s > ini_c:    # tramo final: falta la cabeza
                hueco = ini_c, (pd.Timestamp(ini_s) - pd.Timedelta(days=1)).date()
            else:
                continue
            if _trimestres(*hueco) != 1 or hueco in tramos:
                continue
            if promedio:
                # El acumulado de un promedio ponderado no suma: es el promedio del
                # periodo. La identidad correcta pesa cada tramo por su duración.
                valor = n * float(fila_c["valor"]) - k * float(fila_s["valor"])
                if valor <= 0:
                    continue  # un conteo de acciones no positivo no es un dato
            else:
                valor = float(fila_c["valor"]) - float(fila_s["valor"])
            fila = dict(fila_c)
            fila.update({
                "periodo_tipo": "Q",
                "fecha_inicio": hueco[0],
                "fecha_dato": hueco[1],
                "fecha_publicacion": max(
                    pd.Timestamp(fila_c["fecha_publicacion"]).date(),
                    pd.Timestamp(fila_s["fecha_publicacion"]).date(),
                ),
                "valor": valor,
                "formulario": "DERIVADO",
                "marco": "",
            })
            return hueco, (1, fila)
    return None


# Cuánto puede llevar una etiqueta sin reportarse y seguir contando como vigente.
# Una serie trimestral viva tiene su última observación a tres o cuatro meses del
# corte; una que solo se publica al cierre del año, a catorce. Dieciocho meses deja
# pasar la segunda sin admitir una etiqueta abandonada hace años.
VENTANA_DE_VIGENCIA = pd.DateOffset(months=18)

# Cuánto se pueden separar dos etiquetas en los periodos que ambas reportan para
# aceptar que son el MISMO renglón con otro nombre. Un 1% cubre el redondeo del
# emisor sin dejar pasar dos conceptos distintos: Extra Space etiquetó el mismo
# trimestre como `InterestExpenseDebt` = 5.7 MM y `InterestExpense` = 46.9 MM, y
# empalmarlas habría cosido una serie que no es de nadie.
TOLERANCIA_EMPALME = 0.01


def _series_por_tag(crudos: pd.DataFrame) -> dict[str, pd.Series]:
    """Por etiqueta, el último valor publicado de cada periodo."""
    orden = crudos.sort_values("fecha_publicacion")
    return {
        tag: grupo.drop_duplicates(["periodo_tipo", "fecha_dato"], keep="last")
        .set_index(["periodo_tipo", "fecha_dato"])["valor"]
        .astype(float)
        for tag, grupo in orden.groupby("tag", sort=False)
    }


def _empalma(cubierto: pd.Series, otra: pd.Series, *, excluyentes: bool = False) -> bool:
    """¿La segunda etiqueta es el mismo renglón que la primera?

    La prueba es empírica y se corre con los datos de la propia emisora: donde las
    dos reportan el mismo periodo, tienen que coincidir. Si se traslapan y difieren
    son conceptos distintos y no se pegan.

    Sin traslape no hay con qué comprobarlo, y por omisión se rechaza: callar la
    duda sale más caro que el hueco. La excepción son los renglones declarados de
    ``alternativas_excluyentes`` —el capital mezzanine, que la taxonomía escribe
    de nueve maneras—, donde la emisora publica un solo nombre por corte y el
    traslape no puede existir por construcción. Ahí exigir traslape no protege de
    nada: solo garantiza el hueco.

    Y esos renglones no quedan sin verificar. Son de balance, así que tienen un
    juez independiente y más duro que cualquier traslape: la partida doble. Si el
    empalme estuviera mal, el activo dejaría de igualar al pasivo más el capital,
    y hay una prueba que lo exige.
    """
    comunes = cubierto.index.intersection(otra.index)
    if comunes.empty:
        return excluyentes
    referencia = cubierto.loc[comunes]
    escala = referencia.abs()
    medibles = escala > 0
    if not medibles.any():
        return False
    diferencia = (referencia[medibles] - otra.loc[comunes][medibles]).abs() / escala[medibles]
    return bool(diferencia.max() <= TOLERANCIA_EMPALME)


def elegir_cadenas(crudos: pd.DataFrame, ticker: str) -> dict[str, tuple[str, ...]]:
    """Por renglón: la etiqueta principal y las que se le pueden EMPALMAR detrás.

    Elegir UNA etiqueta por renglón —lo que hacía este módulo— deja fuera la mitad
    de la serie cuando la emisora se cambia de etiqueta a media historia. Prologis
    reportó su gasto por intereses en ``InterestExpense`` hasta el segundo trimestre
    de 2024 y pasó a ``InterestExpenseNonoperating``; por cobertura ganaba la vieja
    y la valuación se quedaba sin los ocho trimestres más recientes, que son
    justamente los que importan.

    Pegar series distintas, sin embargo, es peor que el hueco: produce un número
    que no es de nadie y nadie lo nota. Por eso el empalme se **verifica** contra
    los periodos en que las dos etiquetas coexisten (``_empalma``). En el universo
    esa prueba acepta 46 empalmes y rechaza 57, y los que rechaza son los que hay
    que rechazar: los intereses de Extra Space difieren 100% entre etiquetas.

    La cadena va en orden de uso: la primera que tenga el periodo lo alimenta. La
    principal se elige con el criterio de siempre —vigencia, cobertura, preferencia
    declarada—; las demás solo rellenan lo que la principal no cubre.
    """
    if crudos.empty:
        return {}
    resumen = crudos.groupby("tag").agg(
        cobertura=("fecha_dato", lambda s: len(set(zip(
            crudos.loc[s.index, "periodo_tipo"], s, strict=True)))),
        ultima=("fecha_dato", "max"),
    )
    if resumen.empty:
        return {}
    corte = pd.Timestamp(resumen["ultima"].max()) - VENTANA_DE_VIGENCIA
    vigente = {t: pd.Timestamp(r.ultima) >= corte for t, r in resumen.iterrows()}
    cobertura = resumen["cobertura"].to_dict()
    series = _series_por_tag(crudos)

    cadenas: dict[str, tuple[str, ...]] = {}
    for linea in LINEAS:
        preferencia = tags_de(ticker, linea.clave)
        orden = {t: i for i, t in enumerate(preferencia)}
        candidatas = [t for t in preferencia if cobertura.get(t, 0)]
        if not candidatas:
            continue
        # Primero las vigentes; entre iguales, la de más cobertura; y a igualdad
        # de cobertura manda el orden de preferencia declarado, para que el
        # desempate sea por criterio y no por nombre.
        candidatas.sort(key=lambda t: (vigente[t], cobertura[t], -orden[t]), reverse=True)

        cadena = [candidatas[0]]
        cubierto = series[candidatas[0]]
        for tag in candidatas[1:]:
            otra = series[tag]
            nuevos = otra.index.difference(cubierto.index)
            if nuevos.empty:
                continue
            if not _empalma(cubierto, otra, excluyentes=linea.alternativas_excluyentes):
                continue
            cadena.append(tag)
            cubierto = pd.concat([cubierto, otra.loc[nuevos]])
        cadenas[linea.clave] = tuple(cadena)
    return cadenas


def elegir_tags(crudos: pd.DataFrame, ticker: str) -> dict[str, str]:
    """Decide UNA etiqueta GAAP por renglón, para toda la emisora.

    La decisión tiene que tomarse una sola vez y sobre el conjunto completo de
    hechos, no dentro de cada tabla. Si el estado trimestral elige
    ``NetIncomeLossAvailableToCommonStockholdersBasic`` y el anual elige
    ``NetIncomeLoss`` —porque en su propio subconjunto cada uno tenía más
    cobertura—, las dos series dejan de ser comparables: "los cuatro trimestres
    suman el año" pasa a comparar dos conceptos distintos y reprueba por 16% sin
    que ninguna de las dos cifras esté mal.

    El criterio es la cobertura, **entre las etiquetas todavía vigentes**. Esa
    segunda mitad no estaba y costaba caro: las emisoras cambian de etiqueta y la
    vieja se queda en el archivo con toda su historia acumulada. Realty Income
    reportó su gasto por intereses en ``InterestExpense`` de 2015 a 2024 y pasó a
    ``InterestExpenseOperating``; por cobertura total ganaba la muerta, con 138
    observaciones contra 22, y la serie que alimenta la valuación se quedaba sin
    los últimos dos años. Lo mismo con la deuda total, que se detenía en 2017.

    Sin dato reciente no hay EBITDAre, ni costo de la deuda, ni apalancamiento —y
    sin esos tres la Puerta 1 no alcanza los criterios medibles que exige y el
    veredicto es INCONCLUSO para todo el universo. Una etiqueta que la emisora
    dejó de usar no sirve para valuar hoy, por mucha historia que tenga.

    Si ninguna candidata está vigente se conserva la de más cobertura: es
    preferible una serie que termina en 2017 a ninguna, siempre que la pantalla
    diga hasta cuándo llega — y lo dice, en la sección de procedencia.

    Es la **cabeza** de la cadena de ``elegir_cadenas``, que además rellena con las
    etiquetas que pasan la prueba de empalme. Quien necesite la serie completa pide
    la cadena; quien solo necesita saber de dónde sale el renglón, pide esto.
    """
    return {clave: cadena[0] for clave, cadena in elegir_cadenas(crudos, ticker).items()}


def armar_estado(
    crudos: pd.DataFrame,
    ticker: str,
    estado: str,
    *,
    asof: dt.date,
    periodo_tipo: str = "Q",
    tags: dict[str, str] | None = None,
    campo: str = "valor",
) -> pd.DataFrame:
    """Arma un estado financiero al corte, en formato ancho: líneas × periodos.

    ``asof`` no es decorativo: solo entran hechos cuya ``fecha_publicacion`` sea
    anterior o igual al corte, y de cada periodo se toma la versión **más reciente
    conocida a esa fecha**. Es la reconstrucción point-in-time (P1), y es lo que
    permite responder "¿qué decía el balance de este emisor en marzo de 2024?" con
    lo que se sabía entonces, no con la reexpresión de después.

    ``tags`` admite una etiqueta por renglón o la cadena completa de
    ``elegir_cadenas``. Con la cadena, la columna ``tag_gaap`` nombra a TODAS las
    que alimentaron el renglón, separadas por ``+``: si un renglón está empalmado,
    la tabla lo dice en lugar de esconderlo.

    ``campo="fecha_publicacion"`` arma la MISMA tabla pero con el filing del que
    salió cada celda en vez del número. Sirve para una pregunta que el valor solo
    no contesta: si los renglones de un corte vienen todos del mismo reporte.
    """
    if crudos.empty:
        return pd.DataFrame()

    cadenas = elegir_cadenas(crudos, ticker) if tags is None else {
        c: (v,) if isinstance(v, str) else tuple(v) for c, v in tags.items()
    }
    tags = {c: cadena[0] for c, cadena in cadenas.items() if cadena}
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
        cadena = cadenas.get(linea.clave, ())
        serie: dict = {}
        usadas: list[str] = []
        for tag in cadena:
            parcial = _serie_de_linea(vista, tag, campo)
            if parcial is None:
                continue
            # La cadena va en orden de uso: la etiqueta principal manda y las
            # empalmadas solo rellenan el periodo que ella no trae.
            nuevos = {f: v for f, v in parcial.items() if f not in serie}
            if not nuevos:
                continue
            serie.update(nuevos)
            usadas.append(tag)
        if not serie:
            continue
        columnas[linea.clave] = serie
        procedencia[linea.clave] = " + ".join(usadas)

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


def balance_por_reporte(
    crudos: pd.DataFrame,
    ticker: str,
    *,
    asof: dt.date,
    tags: dict | None = None,
) -> pd.DataFrame:
    """El balance SIN colapsar: una fila por renglón, corte y filing.

    ``armar_estado`` se queda con la versión más reciente de cada renglón, que es
    lo correcto para saber qué se sabe hoy. Pero la identidad contable no vive en
    esa vista: vive dentro de CADA reporte. Una emisora reexpresa un renglón en el
    10-Q del año siguiente y no vuelve a etiquetar los demás, y entonces el corte
    colapsado mezcla dos balances —el activo de una reexpresión con el pasivo del
    original— y deja de cuadrar sin que nadie haya leído mal nada.

    Con esta tabla la pregunta se puede hacer bien: no "¿cuadra la vista de hoy?"
    sino "¿hubo alguna vez un balance publicado que cuadre?". Si lo hubo, las
    etiquetas están bien leídas.
    """
    if crudos.empty:
        return pd.DataFrame(columns=["linea", "fecha_dato", "fecha_publicacion", "valor"])
    cadenas = elegir_cadenas(crudos, ticker) if tags is None else {
        c: (v,) if isinstance(v, str) else tuple(v) for c, v in tags.items()
    }
    vista = crudos.copy()
    vista["fecha_publicacion"] = pd.to_datetime(vista["fecha_publicacion"]).dt.date
    vista["fecha_dato"] = pd.to_datetime(vista["fecha_dato"]).dt.date
    vista = vista[
        (vista["fecha_publicacion"] <= asof) & (vista["periodo_tipo"] == "PUNTUAL")
    ]
    if vista.empty:
        return pd.DataFrame(columns=["linea", "fecha_dato", "fecha_publicacion", "valor"])

    filas = []
    for linea in lineas_de(BALANCE):
        cadena = cadenas.get(linea.clave, ())
        sub = vista[vista["tag"].isin(cadena)]
        if sub.empty:
            continue
        rango = sub["tag"].map({t: i for i, t in enumerate(cadena)})
        gana = rango.groupby(
            [sub["fecha_dato"], sub["fecha_publicacion"]], sort=False
        ).transform("min")
        sub = sub[rango == gana]
        for r in sub.to_dict("records"):
            filas.append({
                "linea": linea.clave,
                "fecha_dato": r["fecha_dato"],
                "fecha_publicacion": r["fecha_publicacion"],
                "valor": float(r["valor"]),
            })
    return pd.DataFrame(filas, columns=["linea", "fecha_dato", "fecha_publicacion", "valor"])


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


def _serie_de_linea(vista: pd.DataFrame, tag: str, campo: str = "valor") -> dict | None:
    """Valores por periodo de una etiqueta, en versión point-in-time.

    De cada periodo se toma la versión publicada más reciente **dentro del corte**.
    No se mezclan etiquetas dentro de un renglón: si una emisora reportó
    ``LongTermDebt`` hasta 2023 y otra etiqueta desde 2024, pegar las dos series
    produce un salto que parece un evento de crédito y es un cambio de taxonomía.
    Cuál se usó queda declarado en la columna ``tag_gaap`` de cada estado.

    Con ``campo="fecha_publicacion"`` devuelve, en vez del número, el filing del
    que salió. Es lo que permite preguntarle a un balance si sus renglones vienen
    todos del MISMO reporte, que no es lo mismo que preguntarle si cuadra.
    """
    sub = vista[vista["tag"] == tag]
    if sub.empty:
        return None
    sub = sub.sort_values("fecha_publicacion").drop_duplicates("fecha_dato", keep="last")
    columna = "fecha_publicacion" if campo == "fecha_publicacion" else "valor"
    valores = sub[columna] if columna == "fecha_publicacion" else sub[columna].astype(float)
    return dict(zip(sub["fecha_dato"], valores, strict=True))


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


# --------------------------------------------------------------------------------------
# Persistencia: de las tres tablas a la base de hechos
# --------------------------------------------------------------------------------------


def _coalescer(crudos: pd.DataFrame, cadenas: dict[str, tuple[str, ...]]) -> pd.DataFrame:
    """De hechos por etiqueta a hechos por renglón, resolviendo el empalme.

    Por cada periodo gana la etiqueta de mayor prioridad de la cadena que lo tenga,
    y se conservan TODAS sus versiones publicadas: quedarse con la última rompería
    P1. Una misma etiqueta puede alimentar dos renglones —los ingresos totales y su
    subtotal—, así que la fila se emite una vez por renglón.
    """
    partes: list[pd.DataFrame] = []
    for clave, cadena in cadenas.items():
        vista = crudos[crudos["tag"].isin(cadena)]
        if vista.empty:
            continue
        rango = vista["tag"].map({t: i for i, t in enumerate(cadena)})
        gana = rango.groupby(
            [vista["periodo_tipo"], vista["fecha_dato"]], sort=False
        ).transform("min")
        partes.append(vista[rango == gana].assign(concepto=clave))
    if not partes:
        return pd.DataFrame(columns=[*crudos.columns, "concepto"])
    return pd.concat(partes, ignore_index=True)


def hechos_de_estados(
    companyfacts: dict,
    ticker: str,
    cik: str = "",
    *,
    desde: dt.date | None = None,
) -> pd.DataFrame:
    """Las tres tablas convertidas a filas de ``hechos``, listas para persistir.

    Este módulo sabía **armar** los estados desde 2024 y nadie los guardaba: el
    orquestador solo llamaba a `xbrl.py`, que mapea quince conceptos. El resultado
    era que sesenta de los setenta y cinco renglones definidos aquí no tenían ni un
    dato en la base, y con ellos faltaban las tres piezas que la valuación necesita
    para dejar de decir INCONCLUSO:

    * el **gasto por intereses** del estado de resultados —no el pagado del flujo
      de efectivo, que muchas emisoras solo publican al cierre del año—, sin el
      cual no hay EBITDAre ni costo de la deuda;
    * la **deuda total** del balance, sin la cual no hay apalancamiento ni NAV;
    * los **impuestos**, que entran al EBITDAre.

    Las tres aparecen en las diez emisoras del universo cuando se leen desde aquí.

    La etiqueta GAAP se elige UNA vez por emisora sobre el conjunto completo de
    hechos —no por tabla— para que el trimestre y el año hablen del mismo concepto,
    y se derivan los trimestres que la SEC nunca recibe. Ambas cosas ya las hacía
    este módulo; lo único que faltaba era escribir el resultado.

    Sobre la etiqueta única hay una corrección posterior: cuando la emisora se
    cambia de etiqueta a media serie, la principal no alcanza y las que pasan la
    prueba de empalme rellenan el resto (``elegir_cadenas``). El orden de las tres
    operaciones importa: primero se deriva por etiqueta, luego se empalma, y luego
    se vuelve a derivar sobre el renglón ya empalmado. Esa última pasada es la que
    despeja un trimestre cuyo acumulado quedó en una etiqueta y su tramo en otra.
    """
    return hechos_de_crudos(hechos_crudos(companyfacts, ticker, desde=desde), ticker, cik)


def hechos_de_crudos(crudos: pd.DataFrame, ticker: str, cik: str = "") -> pd.DataFrame:
    """Lo mismo, pero partiendo de los hechos crudos YA leídos, sin tocar la red.

    Es la mitad que hacía falta para cumplir la promesa del encabezado de este
    módulo: "si mañana mejora la taxonomía, se rearman los estados sin volver a
    bajar nada". El crudo está versionado en ``data/emisoras/<TICKER>/`` desde
    hace tiempo, pero la única forma de rearmar era volver a pedirle a la SEC los
    128 MB de `companyfacts` que ya estaban en el repositorio en 1.5 MB.

    Separarlo tiene una segunda consecuencia, más importante que el ahorro:
    ampliar el catálogo deja de depender de la red y de que la SEC esté arriba,
    así que se puede probar un cambio de taxonomía contra el universo entero en
    segundos y de forma reproducible.
    """
    if crudos.empty:
        return pd.DataFrame(columns=list(COLUMNAS_HECHOS))

    cadenas = elegir_cadenas(crudos, ticker)
    if not cadenas:
        return pd.DataFrame(columns=list(COLUMNAS_HECHOS))
    crudos = derivar_trimestres_faltantes(crudos, cadenas)

    vista = _coalescer(crudos, cadenas)
    vista = vista[vista["periodo_tipo"].isin([*TIPOS_DE_PERIODO, "PUNTUAL"])]
    if vista.empty:
        return pd.DataFrame(columns=list(COLUMNAS_HECHOS))
    vista = derivar_trimestres_faltantes(vista, cadenas, por="concepto")

    filas: list[dict] = []
    for r in vista.to_dict("records"):
        derivado = r["formulario"] == "DERIVADO"
        filas.append(
            {
                "ticker": ticker,
                "concepto": r["concepto"],
                "periodo_tipo": r["periodo_tipo"],
                "periodo_inicio": r["fecha_inicio"],
                "fecha_dato": r["fecha_dato"],
                "fecha_publicacion": r["fecha_publicacion"],
                "valor": float(r["valor"]),
                "unidad": r["unidad"],
                # Un trimestre derivado NO es primario: se calculó restándole a un
                # acumulado el tramo que sí se publicó, y hereda el error de sus
                # dos componentes. Decirlo es lo que separa un dato de la SEC de
                # una cuenta nuestra.
                "fuente": Fuente.DERIVADO if derivado else Fuente.SEC_XBRL,
                "es_primario": not derivado,
                "accession": r["accession"],
                "url_filing": _url_de_filing(cik, r["accession"]),
            }
        )
    return pd.DataFrame(filas, columns=list(COLUMNAS_HECHOS))


COLUMNAS_HECHOS = (
    "ticker", "concepto", "periodo_tipo", "periodo_inicio", "fecha_dato",
    "fecha_publicacion", "valor", "unidad", "fuente", "es_primario",
    "accession", "url_filing",
)


def _url_de_filing(cik, accession) -> str | None:
    if not cik or not accession:
        return None
    try:
        return (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{str(accession).replace('-', '')}/"
        )
    except (TypeError, ValueError):
        return None


__all__ = [
    "BALANCE",
    "COLUMNAS_HECHOS",
    "ESTADOS",
    "ESTADO_RESULTADOS",
    "FLUJO_EFECTIVO",
    "FichaEstados",
    "LINEAS",
    "LINEA_POR_CLAVE",
    "NOMBRE_ESTADO",
    "Fuente",
    "armar_estado",
    "balance_por_reporte",
    "cobertura_de_lineas",
    "conceptos_no_mapeados",
    "derivar_trimestres_faltantes",
    "elegir_cadenas",
    "etiquetas_de_instancia",
    "elegir_tags",
    "hechos_crudos",
    "hechos_de_crudos",
    "hechos_de_estados",
    "lineas_de",
    "periodos_disponibles",
    "tags_de",
]
