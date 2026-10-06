"""Los estados financieros de cada REIT, trimestre por trimestre y como se conocían entonces.

De ``companyfacts`` (XBRL de la SEC) se arma, para cada emisor, una serie por partida con
la fecha en que el número se hizo público (``conocido``). Reglas:

* **La primera versión publicada** de cada periodo: una reexpresión posterior no existía
  en la fecha en que se habría tomado la decisión.
* **Varias etiquetas por partida, en orden de preferencia, periodo por periodo.** Los
  emisores cambian de etiqueta con los años (Realty Income reportó el dividendo por acción
  como «declarado» en 2011-2012 y como «pagado» desde 2019); quedarse con una sola
  etiqueta para toda la historia deja huecos.
* **Flujos a 12 meses (TTM)**: el año fiscal si el trimestre lo cierra; si no, la suma de
  los cuatro trimestres, cada uno reportado directo o derivado de acumulados (el 10-Q de
  junio trae el semestre; el trimestre es semestre menos primer trimestre). Se conoce
  cuando se conoció la última de sus piezas.
* **Saldos** (activos, pasivos, acciones): el valor al cierre, conocido al presentarse.

El FFO es una medida no-GAAP que no viene en XBRL. Se arma con la definición de Nareit:
utilidad de los comunes + depreciación y amortización − ganancia por venta de inmuebles +
deterioros. La depreciación de XBRL incluye la de activos que no son inmuebles, así que
el FFO armado queda un poco arriba del publicado; se mide contra el publicado de O, NNN y
WPC (``validar_ffo``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FLUJO, SALDO, PROMEDIO = "flujo", "saldo", "promedio"

# partida -> (tipo, [(taxonomía, etiqueta), ...] en orden de preferencia, unidad)
CONCEPTOS: dict[str, tuple[str, list[tuple[str, str]], str]] = {
    "dps": (FLUJO, [("us-gaap", "CommonStockDividendsPerShareDeclared"),
                    ("us-gaap", "CommonStockDividendsPerShareCashPaid")], "USD/shares"),
    "dividendos": (FLUJO, [("us-gaap", "DividendsCommonStock"), ("us-gaap", "DividendsCommonStockCash"),
                           ("us-gaap", "PaymentsOfDividendsCommonStock"), ("us-gaap", "PaymentsOfDividends"),
                           ("us-gaap", "PaymentsOfOrdinaryDividends")], "USD"),
    "utilidad_comun": (FLUJO, [("us-gaap", "NetIncomeLossAvailableToCommonStockholdersBasic"),
                               ("us-gaap", "NetIncomeLoss"), ("us-gaap", "ProfitLoss")], "USD"),
    "depreciacion": (FLUJO, [("us-gaap", "DepreciationDepletionAndAmortization"),
                             ("us-gaap", "DepreciationAndAmortization"),
                             ("us-gaap", "DepreciationAmortizationAndAccretionNet"),
                             ("us-gaap", "Depreciation")], "USD"),
    "ganancia_venta": (FLUJO, [("us-gaap", "GainLossOnSaleOfPropertiesNetOfApplicableIncomeTaxes"),
                               ("us-gaap", "GainsLossesOnSalesOfInvestmentRealEstate"),
                               ("us-gaap", "GainLossOnSaleOfProperties"),
                               ("us-gaap", "GainLossOnSaleOfRealEstateInvestmentProperty"),
                               ("us-gaap", "GainLossOnDispositionOfAssets1"),
                               ("us-gaap", "GainLossOnDispositionOfAssets"),
                               ("us-gaap", "GainLossOnSaleOfPropertyPlantEquipment")], "USD"),
    "deterioro": (FLUJO, [("us-gaap", "ImpairmentOfRealEstate"), ("us-gaap", "AssetImpairmentCharges"),
                          ("us-gaap", "ImpairmentOfLongLivedAssetsHeldForUse"),
                          ("us-gaap", "TangibleAssetImpairmentCharges")], "USD"),
    "ingresos": (FLUJO, [("us-gaap", "Revenues"), ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
                         ("us-gaap", "OperatingLeaseLeaseIncome"),
                         ("us-gaap", "OperatingLeasesIncomeStatementLeaseRevenue"),
                         ("us-gaap", "RealEstateRevenueNet")], "USD"),
    "intereses": (FLUJO, [("us-gaap", "InterestExpense"), ("us-gaap", "InterestExpenseDebt"),
                          ("us-gaap", "InterestAndDebtExpense"), ("us-gaap", "InterestExpenseNonoperating")], "USD"),
    "ingreso_intereses": (FLUJO, [("us-gaap", "InterestAndDividendIncomeOperating"),
                                  ("us-gaap", "InterestIncomeOperating"),
                                  ("us-gaap", "InterestAndFeeIncomeLoansAndLeases")], "USD"),
    "activos": (SALDO, [("us-gaap", "Assets")], "USD"),
    "pasivos": (SALDO, [("us-gaap", "Liabilities")], "USD"),
    "capital_total": (SALDO, [("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
                              ("us-gaap", "StockholdersEquity")], "USD"),
    "inmuebles": (SALDO, [("us-gaap", "RealEstateInvestmentPropertyNet"),
                          ("us-gaap", "RealEstateInvestmentPropertyAtCost")], "USD"),
    "ppe": (SALDO, [("us-gaap", "PropertyPlantAndEquipmentNet")], "USD"),
    "prestamos_y_valores": (SALDO, [("us-gaap", t) for t in (
        "LoansAndLeasesReceivableNetReportedAmount", "MortgageLoansOnRealEstateCommercialAndConsumerNet",
        "LoansReceivableNet", "FinancingReceivableExcludingAccruedInterestAfterAllowanceForCreditLoss",
        "LoansAndLeasesReceivableNetOfDeferredIncome", "LoansHeldForSaleMortgages", "LoansReceivableHeldForSaleNet",
        "AvailableForSaleSecuritiesDebtSecurities", "DebtSecuritiesAvailableForSaleExcludingAccruedInterest",
        "AvailableForSaleSecurities", "MortgageBackedSecuritiesAvailableForSaleFairValueDisclosure",
        "TradingSecuritiesDebt", "TradingSecurities", "HeldToMaturitySecurities")], "USD"),
    # Los reportos financian valores: un REIT de capital casi nunca los usa.
    "repos": (SALDO, [("us-gaap", "SecuritiesSoldUnderAgreementsToRepurchase"),
                      ("us-gaap", "SecuritiesSoldUnderAgreementsToRepurchaseFairValueDisclosure")], "USD"),
    "acciones": (SALDO, [("dei", "EntityCommonStockSharesOutstanding"),
                         ("us-gaap", "CommonStockSharesOutstanding")], "shares"),
    # El promedio ponderado del periodo: el acumulado es un promedio, no una suma.
    "acciones_promedio": (PROMEDIO, [("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic"),
                                     ("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding")], "shares"),
}


SIN_SIGNO = frozenset({"dividendos", "dps"})


def _meses(inicio: pd.Series, fin: pd.Series) -> pd.Series:
    dias = (fin - inicio).dt.days
    return pd.Series(np.select([dias.between(80, 100), dias.between(170, 200), dias.between(260, 290),
                                dias.between(350, 380)], [3, 6, 9, 12], 0), index=inicio.index)


def hechos(cf: dict, partida: str) -> pd.DataFrame:
    """Todos los hechos de una partida, la primera versión publicada de cada periodo.

    Columnas: inicio (NaT en saldos), fin, valor, conocido, forma, rango (0 = etiqueta
    preferida). Si un periodo trae varias etiquetas, gana la de menor rango.
    """
    tipo, etiquetas, unidad = CONCEPTOS[partida]
    filas = []
    for rango, (tax, etiqueta) in enumerate(etiquetas):
        bloque = cf.get("facts", {}).get(tax, {}).get(etiqueta)
        if not bloque:
            continue
        for u, obs in bloque.get("units", {}).items():
            if u != unidad:
                continue
            for o in obs:
                filas.append((o.get("start"), o["end"], float(o["val"]), o["filed"], o.get("form", ""), rango))
    d = pd.DataFrame(filas, columns=["inicio", "fin", "valor", "conocido", "forma", "rango"])
    if partida in SIN_SIGNO:
        d["valor"] = d["valor"].abs()  # en el estado de capital el dividendo a veces va con signo negativo
    if d.empty:
        return d
    for c in ("inicio", "fin", "conocido"):
        d[c] = pd.to_datetime(d[c])
    if tipo == SALDO:
        d = d[d["inicio"].isna()] if partida != "acciones" else d
        d = d.assign(meses=0)
    else:
        d = d[d["inicio"].notna()]
        d = d.assign(meses=_meses(d["inicio"], d["fin"]))
        d = d[d["meses"] > 0]
    d = d.sort_values(["inicio", "fin", "rango", "conocido"], na_position="first")
    claves = ["fin"] if tipo == SALDO else ["inicio", "fin"]
    # Primero la etiqueta preferida del periodo; de esa, la primera versión publicada.
    mejor = d.groupby(claves, dropna=False)["rango"].transform("min")
    d = d[d["rango"] == mejor].drop_duplicates(claves, keep="first")
    return d.reset_index(drop=True)


def trimestres(h: pd.DataFrame) -> pd.DataFrame:
    """Flujos de tres meses: los reportados y los derivados restando acumulados del mismo año.

    Columnas: fin, valor, conocido. Un acumulado de n meses menos el de n−3 con el mismo
    inicio es el trimestre que cierra en el fin del primero.
    """
    if h.empty:
        return pd.DataFrame(columns=["fin", "valor", "conocido"])
    q = {r.fin: (r.valor, r.conocido) for r in h[h["meses"] == 3].itertuples()}
    acum = h[h["meses"].isin([3, 6, 9, 12])].set_index(["inicio", "meses"])
    for r in h[h["meses"].isin([6, 9, 12])].itertuples():
        if r.fin in q:
            continue
        clave = (r.inicio, r.meses - 3)
        if clave in acum.index:
            previo = acum.loc[clave]
            if isinstance(previo, pd.DataFrame):
                previo = previo.iloc[0]
            q[r.fin] = (r.valor - previo["valor"], max(r.conocido, previo["conocido"]))
    # Sin el acumulado de nueve meses: el año menos los tres trimestres que caen dentro.
    for r in h[h["meses"] == 12].itertuples():
        dentro = [(f, v) for f, v in q.items() if r.inicio < f < r.fin]
        if r.fin not in q and len(dentro) == 3:
            q[r.fin] = (r.valor - sum(v[0] for _, v in dentro), max([r.conocido] + [v[1] for _, v in dentro]))
    t = pd.DataFrame([(f, v, c) for f, (v, c) in q.items()], columns=["fin", "valor", "conocido"])
    return t.sort_values("fin", ignore_index=True)


def doce_meses(h: pd.DataFrame) -> pd.DataFrame:
    """El flujo de los últimos 12 meses a cada cierre de trimestre: fin, valor, conocido."""
    if h.empty:
        return pd.DataFrame(columns=["fin", "valor", "conocido"])
    anual = {r.fin: (r.valor, r.conocido) for r in h[h["meses"] == 12].itertuples()}
    q = trimestres(h)
    fines = q["fin"].tolist()
    for i in range(3, len(fines)):
        ventana = q.iloc[i - 3: i + 1]
        dias = (ventana["fin"].iloc[-1] - ventana["fin"].iloc[0]).days
        if not 250 <= dias <= 300 or fines[i] in anual:
            continue  # cuatro trimestres seguidos, sin huecos
        anual[fines[i]] = (ventana["valor"].sum(), ventana["conocido"].max())
    t = pd.DataFrame([(f, v, c) for f, (v, c) in anual.items()], columns=["fin", "valor", "conocido"])
    return t.sort_values("fin", ignore_index=True)


def promedio_trimestral(h: pd.DataFrame) -> pd.DataFrame:
    """El promedio de cada trimestre de un conteo de acciones. El cuarto casi nunca se
    reporta solo: es cuatro veces el promedio del año menos los otros tres."""
    if h.empty:
        return pd.DataFrame(columns=["fin", "valor", "conocido"])
    q = {r.fin: (r.valor, r.conocido) for r in h[h["meses"] == 3].itertuples()}
    for r in h[h["meses"] == 12].itertuples():
        previos = [(f, v) for f, v in q.items() if r.inicio < f < r.fin]
        if r.fin not in q and len(previos) == 3:
            resto = 4 * r.valor - sum(v[0] for _, v in previos)
            if resto > 0:
                q[r.fin] = (resto, max([r.conocido] + [v[1] for _, v in previos]))
    t = pd.DataFrame([(f, v, c) for f, (v, c) in q.items()], columns=["fin", "valor", "conocido"])
    return t.sort_values("fin", ignore_index=True)


def promedio_doce_meses(h: pd.DataFrame) -> pd.DataFrame:
    """El promedio de 12 meses de un conteo de acciones: el del año fiscal, o el promedio
    de los cuatro trimestres."""
    if h.empty:
        return pd.DataFrame(columns=["fin", "valor", "conocido"])
    t = promedio_trimestral(h)
    salida = {r.fin: (r.valor, r.conocido) for r in h[h["meses"] == 12].itertuples()}
    for i in range(3, len(t)):
        ventana = t.iloc[i - 3: i + 1]
        if 250 <= (ventana["fin"].iloc[-1] - ventana["fin"].iloc[0]).days <= 300 and t["fin"].iat[i] not in salida:
            salida[t["fin"].iat[i]] = (ventana["valor"].mean(), ventana["conocido"].max())
    s = pd.DataFrame([(f, v, c) for f, (v, c) in salida.items()], columns=["fin", "valor", "conocido"])
    return s.sort_values("fin", ignore_index=True)


def series(cf: dict) -> pd.DataFrame:
    """Todas las partidas de un emisor en formato largo: partida, fin, valor, conocido.

    Los flujos y promedios van a 12 meses (sufijo ``_12m``); los saldos, al cierre.
    """
    partes = []
    for partida, (tipo, _, _) in CONCEPTOS.items():
        h = hechos(cf, partida)
        if h.empty:
            continue
        if tipo == PROMEDIO:
            s = promedio_doce_meses(h).assign(partida=f"{partida}_12m")
        elif tipo == FLUJO:
            s = doce_meses(h).assign(partida=f"{partida}_12m")
        else:
            s = h[["fin", "valor", "conocido"]].assign(partida=partida)
        partes.append(s)
    if not partes:
        return pd.DataFrame(columns=["partida", "fin", "valor", "conocido"])
    return pd.concat(partes, ignore_index=True)[["partida", "fin", "valor", "conocido"]]


def a_la_fecha(s: pd.DataFrame, fechas: pd.DatetimeIndex, *, vigencia_dias: int = 460) -> pd.DataFrame:
    """Lo que se sabía de cada partida en cada fecha: el último dato publicado hasta entonces.

    Un dato cuyo periodo cerró hace más de ``vigencia_dias`` ya no cuenta (el emisor dejó
    de reportar). Devuelve una fila por fecha y una columna por partida.
    """
    salida = pd.DataFrame(index=fechas)
    base = pd.DataFrame({"fecha": fechas}).sort_values("fecha")
    for partida, g in s.groupby("partida"):
        # Recorriendo en orden de publicación, el periodo más reciente publicado hasta ahí.
        g = g.sort_values(["conocido", "fin"])
        escalon, mejor = [], None
        for r in g.itertuples():
            if mejor is None or r.fin >= mejor[0]:
                mejor = (r.fin, r.valor)
            escalon.append((r.conocido, mejor[0], mejor[1]))
        e = pd.DataFrame(escalon, columns=["conocido", "fin", "valor"]).drop_duplicates("conocido", keep="last")
        m = pd.merge_asof(base, e, left_on="fecha", right_on="conocido")
        vigente = (m["fecha"] - m["fin"]).dt.days <= vigencia_dias
        salida[partida] = m["valor"].where(vigente).to_numpy()
    return salida


def dividendo_trimestral(cf: dict) -> pd.DataFrame:
    """El dividendo por acción de cada trimestre fiscal: fin, dps, fuente.

    El declarado o pagado por acción si el emisor lo reporta; si no, el total pagado a los
    comunes entre el promedio de acciones del trimestre.
    """
    directo = trimestres(hechos(cf, "dps")).assign(fuente="por_accion")
    total = trimestres(hechos(cf, "dividendos"))
    acciones = promedio_trimestral(hechos(cf, "acciones_promedio"))
    if not total.empty and not acciones.empty:
        derivado = total.merge(acciones, on="fin", suffixes=("", "_acc"))
        derivado = derivado.assign(valor=derivado["valor"] / derivado["valor_acc"], fuente="total_entre_acciones")
        derivado = derivado[~derivado["fin"].isin(directo["fin"])][["fin", "valor", "conocido", "fuente"]]
        directo = pd.concat([directo, derivado], ignore_index=True)
    return directo.rename(columns={"valor": "dps"}).sort_values("fin", ignore_index=True)


def ffo(x: pd.DataFrame) -> pd.Series:
    """FFO de 12 meses con la definición de Nareit, de las partidas a la fecha."""
    def o_cero(c: str) -> pd.Series:
        return x[c].fillna(0.0) if c in x else pd.Series(0.0, index=x.index)

    return x["utilidad_comun_12m"] + x["depreciacion_12m"] - o_cero("ganancia_venta_12m") + o_cero("deterioro_12m")
