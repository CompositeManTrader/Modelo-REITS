"""Extracción de partidas GAAP desde la API ``companyfacts`` de XBRL.

Qué sí está en XBRL: ingresos, utilidad neta, deuda, efectivo, acciones en
circulación, activos, depreciación, deterioros, ganancias por venta.

Qué **no** está: el AFFO, el FFO normalizado, el NOI de gestión y el CapEx
recurrente de mantenimiento. Son medidas no-GAAP y viven en el Exhibit 99.1 del
8-K de resultados (ver ``parser_affo``). Confundir "no está en XBRL" con "no
existe" es como terminan los modelos usando utilidad neta en lugar de AFFO.

Point-in-time: cada hecho de companyfacts trae ``filed``, la fecha en que ese
número se volvió público. Ese campo es la ``fecha_publicacion``. Un mismo
periodo aparece varias veces con distintos ``filed`` cuando hay reexpresión:
guardamos todas las versiones, nunca sobrescribimos.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence

import pandas as pd

from src.config import Fuente
from src.ingesta.edgar import ClienteEdgar

# --------------------------------------------------------------------------------------
# Mapa de conceptos: nombre normalizado -> etiquetas GAAP en orden de preferencia
# --------------------------------------------------------------------------------------

CONCEPTOS_GAAP: dict[str, tuple[str, ...]] = {
    "ingresos": (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "OperatingLeaseLeaseIncome",
    ),
    "ingreso_rentas": (
        "OperatingLeaseLeaseIncome",
        "OperatingLeasesIncomeStatementLeaseRevenue",
    ),
    "utilidad_neta": (
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ),
    "utilidad_neta_por_accion": (
        "EarningsPerShareDiluted",
        "EarningsPerShareBasicAndDiluted",
        "EarningsPerShareBasic",
    ),
    "depreciacion_amortizacion": (
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "DepreciationNonproduction",
    ),
    "deterioro": (
        "AssetImpairmentCharges",
        "ImpairmentOfRealEstate",
        "TangibleAssetImpairmentCharges",
    ),
    "ganancia_venta_inmuebles": (
        "GainLossOnSaleOfProperties",
        "GainsLossesOnSalesOfInvestmentRealEstate",
        "GainLossOnDispositionOfAssets1",
        "GainLossOnSaleOfPropertiesNetOfApplicableIncomeTaxes",
    ),
    "gastos_operativos_inmueble": (
        "OperatingExpenses",
        "DirectCostsOfLeasedAndRentedPropertyOrEquipment",
        "RealEstateTaxesAndInsurance",
    ),
    "efectivo": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "deuda_total": (
        "DebtLongtermAndShorttermCombinedAmount",
        "LongTermDebt",
        "LongTermDebtNoncurrent",
        "DebtInstrumentCarryingAmount",
    ),
    "activos_totales": ("Assets",),
    "capital_contable": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    "acciones_diluidas": (
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasicAndDiluted",
    ),
    "acciones_basicas": ("WeightedAverageNumberOfSharesOutstandingBasic", "CommonStockSharesOutstanding"),
    "acciones_en_circulacion": ("CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"),
    "intereses_pagados": ("InterestExpenseDebt", "InterestExpense", "InterestAndDebtExpense"),
    "dividendos_declarados_por_accion": (
        "CommonStockDividendsPerShareDeclared",
        "CommonStockDividendsPerShareCashPaid",
    ),
    "goodwill": ("Goodwill",),
    "inversiones_no_consolidadas": (
        "EquityMethodInvestments",
        "EquityMethodInvestmentSummarizedFinancialInformationAssets",
    ),
    "prestamos_por_cobrar": (
        "NotesReceivableNet",
        "FinancingReceivableExcludingAccruedInterestAfterAllowanceForCreditLoss",
    ),
}

CONCEPTOS_PUNTUALES = frozenset(
    {
        "efectivo",
        "deuda_total",
        "activos_totales",
        "capital_contable",
        "acciones_en_circulacion",
        "goodwill",
        "inversiones_no_consolidadas",
        "prestamos_por_cobrar",
    }
)


def clasificar_periodo(inicio: dt.date | None, fin: dt.date) -> str:
    """Clasifica la duración de un hecho XBRL en Q, H1, 9M, FY o PUNTUAL.

    XBRL no etiqueta el tipo de periodo de forma confiable: hay que medirlo.
    Un 10-Q puede traer la partida del trimestre y la acumulada del año en el
    mismo documento; tratarlas como iguales revuelve toda la serie.
    """
    if inicio is None:
        return "PUNTUAL"
    dias = (fin - inicio).days
    if 80 <= dias <= 100:
        return "Q"
    if 170 <= dias <= 200:
        return "H1"
    if 260 <= dias <= 290:
        return "9M"
    if 350 <= dias <= 380:
        return "FY"
    return "OTRO"


def extraer_hechos(
    companyfacts: dict,
    ticker: str,
    *,
    conceptos: Iterable[str] | None = None,
    desde: dt.date | None = None,
) -> pd.DataFrame:
    """Convierte el JSON de companyfacts en filas listas para la tabla ``hechos``.

    Devuelve **todas** las versiones publicadas de cada periodo. La deduplicación
    point-in-time se hace al consultar, no al guardar: guardar solo la última
    versión destruiría la posibilidad de reconstruir qué se sabía en el pasado.
    """
    facts = companyfacts.get("facts", {})
    conceptos = list(conceptos) if conceptos else list(CONCEPTOS_GAAP)
    filas: list[dict] = []

    for concepto in conceptos:
        etiquetas = CONCEPTOS_GAAP.get(concepto, (concepto,))
        for etiqueta in etiquetas:
            bloque = None
            for taxonomia in ("us-gaap", "dei", "ifrs-full"):
                if etiqueta in facts.get(taxonomia, {}):
                    bloque = facts[taxonomia][etiqueta]
                    break
            if bloque is None:
                continue
            for unidad, observaciones in bloque.get("units", {}).items():
                for obs in observaciones:
                    fin = _fecha(obs.get("end"))
                    filed = _fecha(obs.get("filed"))
                    if fin is None or filed is None:
                        continue
                    if desde is not None and fin < desde:
                        continue
                    inicio = _fecha(obs.get("start"))
                    tipo = clasificar_periodo(inicio, fin)
                    if tipo == "OTRO":
                        continue
                    if concepto in CONCEPTOS_PUNTUALES and tipo != "PUNTUAL":
                        continue
                    if concepto not in CONCEPTOS_PUNTUALES and tipo == "PUNTUAL":
                        continue
                    filas.append(
                        {
                            "ticker": ticker,
                            "concepto": concepto,
                            "periodo_tipo": tipo,
                            "periodo_inicio": inicio,
                            "fecha_dato": fin,
                            "fecha_publicacion": filed,
                            "valor": float(obs["val"]),
                            "unidad": unidad,
                            "fuente": Fuente.SEC_XBRL,
                            "es_primario": True,
                            "accession": obs.get("accn"),
                            "url_filing": _url_filing(companyfacts.get("cik"), obs.get("accn")),
                            "etiqueta_gaap": etiqueta,
                        }
                    )
            if filas and any(f["concepto"] == concepto for f in filas):
                break  # se usó la primera etiqueta disponible del orden de preferencia

    if not filas:
        return pd.DataFrame(
            columns=[
                "ticker",
                "concepto",
                "periodo_tipo",
                "periodo_inicio",
                "fecha_dato",
                "fecha_publicacion",
                "valor",
                "unidad",
                "fuente",
                "es_primario",
                "accession",
                "url_filing",
            ]
        )
    df = pd.DataFrame(filas)
    # Un mismo (concepto, periodo, filed) puede venir duplicado entre unidades; el
    # criterio es quedarse con USD y con la primera etiqueta preferida.
    df = df.sort_values(["ticker", "concepto", "fecha_dato", "fecha_publicacion"])
    return df.drop_duplicates(
        ["ticker", "concepto", "periodo_tipo", "fecha_dato", "fecha_publicacion"], keep="first"
    ).reset_index(drop=True)


def derivar_trimestres_desde_acumulados(df: pd.DataFrame, concepto: str) -> pd.DataFrame:
    """Deriva Q2/Q3/Q4 restando acumulados cuando el emisor solo reporta YTD.

    ``Q2 = H1 − Q1``, ``Q3 = 9M − H1``, ``Q4 = FY − 9M``. Se hace por año fiscal
    y por ``fecha_publicacion``: solo se combinan cifras que fueron observables al
    mismo tiempo, para no fabricar un trimestre con mitad de información futura.
    """
    sub = df[df["concepto"] == concepto].copy()
    if sub.empty:
        return pd.DataFrame(columns=df.columns)
    sub["anio"] = pd.to_datetime(sub["fecha_dato"]).dt.year
    salida: list[dict] = []
    orden = {"Q": 1, "H1": 2, "9M": 3, "FY": 4}
    for (_ticker, _anio), grupo in sub.groupby(["ticker", "anio"]):
        acumulados = {}
        for tipo in ("H1", "9M", "FY"):
            g = grupo[grupo["periodo_tipo"] == tipo]
            if not g.empty:
                acumulados[tipo] = g.sort_values("fecha_publicacion").iloc[-1]
        trimestres = grupo[grupo["periodo_tipo"] == "Q"].sort_values("fecha_dato")
        vistos = {pd.Timestamp(r["fecha_dato"]).quarter: r for _, r in trimestres.iterrows()}
        pares = (("H1", 2, [1]), ("9M", 3, [1, 2]), ("FY", 4, [1, 2, 3]))
        for tipo, trimestre, previos in pares:
            if tipo not in acumulados or trimestre in vistos:
                continue
            if not all(p in vistos for p in previos):
                continue
            base = acumulados[tipo]
            resta = sum(float(vistos[p]["valor"]) for p in previos)
            publicaciones = [pd.Timestamp(base["fecha_publicacion"])] + [
                pd.Timestamp(vistos[p]["fecha_publicacion"]) for p in previos
            ]
            fila = dict(base)
            fila.update(
                {
                    "periodo_tipo": "Q",
                    "valor": float(base["valor"]) - resta,
                    "fecha_publicacion": max(publicaciones).date(),
                    "fuente": Fuente.RECONSTRUIDO,
                    "es_primario": False,
                }
            )
            fila.pop("anio", None)
            salida.append(fila)
            vistos[trimestre] = fila
        _ = orden  # documenta el orden lógico de los acumulados
    return pd.DataFrame(salida) if salida else pd.DataFrame(columns=df.columns)


def ingestar_emisor(
    cliente: ClienteEdgar,
    ticker: str,
    cik: str,
    *,
    conceptos: Sequence[str] | None = None,
    desde: dt.date | None = None,
) -> pd.DataFrame:
    """Descarga companyfacts y devuelve las filas listas para persistir."""
    datos = cliente.companyfacts(cik)
    df = extraer_hechos(datos, ticker, conceptos=conceptos, desde=desde)
    derivados = [
        derivar_trimestres_desde_acumulados(df, c)
        for c in df["concepto"].unique()
        if c not in CONCEPTOS_PUNTUALES
    ]
    derivados = [d for d in derivados if not d.empty]
    if derivados:
        df = pd.concat([df, *derivados], ignore_index=True)
    columnas = [
        "ticker",
        "concepto",
        "periodo_tipo",
        "periodo_inicio",
        "fecha_dato",
        "fecha_publicacion",
        "valor",
        "unidad",
        "fuente",
        "es_primario",
        "accession",
        "url_filing",
    ]
    return df[[c for c in columnas if c in df.columns]]


def _fecha(valor) -> dt.date | None:
    if not valor:
        return None
    try:
        return dt.date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def _url_filing(cik, accn) -> str | None:
    if not cik or not accn:
        return None
    acc = str(accn).replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/"
