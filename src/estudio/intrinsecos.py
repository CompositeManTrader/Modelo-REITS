"""Modelos de valor intrínseco en el tiempo: DDM, DCF, crecimiento implícito y NAV.

Complementa a ``metodos``. Aquellos siete miden «caro o barato» contra la historia
propia; estos cuatro estiman cuánto VALE la acción y lo comparan contra el precio. Se
prueban igual que los otros —percentil contra su historia, backtest de aportación y
asignación entre emisores, con los mismos controles— y además con su señal ABSOLUTA,
que es como se usan en la práctica: comprar si el valor supera al precio.

Diseño fijado antes de correr (commit «Diseño de los modelos intrínsecos»)
---------------------------------------------------------------------------
Todo con lo publicado a cada fin de mes (P1). La tasa de descuento es la de la
aplicación: ``r = Treasury a 10 años + prima del sector`` (``PRIMA_RIESGO_POR_SECTOR``;
3.0% en net lease). Ningún parámetro se mueve después de ver resultados; la prima se
reporta además con 2% y 4% para la señal absoluta, completa.

1. **DDM (Gordon sobre el dividendo).** ``V = D₀(1+g)/(r−g)``. ``D₀`` es el dividendo
   regular vigente anualizado; ``g`` es el crecimiento anual del dividendo en los 5
   años previos, acotado entre 0% y 4% (no hay crecimiento perpetuo por encima del
   nominal de la economía) y a que ``r − g`` sea al menos 2%.
2. **DCF del flujo en dos etapas.** El flujo es el AFFO por acción de 12 meses (FFO
   donde no hay AFFO), como flujo libre al accionista. Cinco años al crecimiento del
   flujo por acción de los 5 años previos, acotado entre 0% y 8%; después, 2% perpetuo
   (la meta de inflación de la Fed), también con ``r − g ≥ 2%``.
3. **Crecimiento implícito contra el entregado.** El crecimiento perpetuo del flujo
   que justifica el precio (Gordon despejado, ``modelo.valuacion.crecimiento_implicito``)
   contra el que el emisor entregó en los 5 años previos, acotado entre −5% y 10%. La
   señal es la diferencia: el mercado descuenta menos de lo que el emisor ha hecho.
4. **NAV aproximado.** ``(NOI anualizado ÷ cap rate − deuda neta − preferentes) ÷
   acciones``, de los estados XBRL versionados (``data/emisoras``), cada cifra con la
   fecha en que se publicó:

   * NOI anualizado = el último trimestre conocido × 4, con NOI = ingresos totales −
     gastos de inmuebles − ingresos por administración de fondos (WPC hasta 2017). En
     net lease el inquilino paga casi todo; la diferencia contra el NOI del suplemento
     es de unos puntos.
   * Cap rate = el de las adquisiciones del propio emisor en su último año reportado
     (cifra primaria, vigente 18 meses): lo que el mercado privado cobró por inmuebles
     parecidos. Existe desde 2006 (NNN), 2009 (O) y 2014 (WPC).
   * Deuda = la mayor entre la deuda total etiquetada y la suma de sus componentes
     (XBRL a veces etiqueta como total solo los bonos); menos el efectivo.
   * Acciones = las de la portada del último reporte (``dei``), o las del balance.

   Antes de mirar retornos, el NAV se valida contra el apalancamiento que reportó cada
   emisor: deuda neta ÷ (NOI − gastos de administración) contra su deuda neta ÷ EBITDAre.

Señales
-------
* **Absoluta.** DDM, DCF y NAV: barato si el valor supera al precio en 15% o más, caro
  si el precio supera al valor en 15% o más (``V/P − 1 ≤ −15%``), medio en medio.
  Crecimiento: barato si el entregado supera al implícito por 1 punto o más, caro si
  queda 1 punto o más abajo.
* **Percentil** contra la historia propia, como los otros métodos (≥ 70 barato, < 30 caro).

Cada una se prueba con el backtest de aportación de ``metodos`` (barato compra todo y la
reserva, medio la mitad, caro nada; nunca vende; nada espera más de 12 meses) y con la
asignación entre emisores: por percentil, y por la señal absoluta, que en un modelo de
valor sí se puede comparar entre emisores (el crecimiento ya está en el valor).

Hipótesis escritas antes de correr
----------------------------------
* El DDM y el DCF en percentil se parecerán mucho a la prima sobre el Treasury y al
  yield de dividendo, porque con ``r`` = Treasury + prima fija el valor entre el precio
  depende casi solo del yield contra la tasa; lo nuevo es ``g``, y ``g`` es ruido.
* En absoluto, el DDM y el DCF dirán «barato» la mayor parte del tiempo en O y NNN
  (crecieron rápido): una señal que casi siempre compra es aportar sin reglas.
* El NAV y el crecimiento implícito son los que podrían aportar información nueva. El
  NAV tiene poca historia: la asignación por NAV con los tres empieza en 2015.
* La regla recomendada sigue siendo el consenso de los siete de ``metodos``: si un modelo
  de valor sale mejor, se reporta, pero adoptarlo sería escoger por resultado.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.config import PRIMA_RIESGO_POR_SECTOR
from src.estudio.metodos import Metodo
from src.modelo.valuacion import crecimiento_implicito


@dataclass(frozen=True)
class Supuestos:
    prima: float = PRIMA_RIESGO_POR_SECTOR["Net Lease"]
    anios_historia: int = 5              # de dónde sale el crecimiento «entregado»
    g_dividendo: tuple[float, float] = (0.0, 0.04)
    g_flujo: tuple[float, float] = (0.0, 0.08)
    g_terminal: float = 0.02
    anios_etapa_1: int = 5
    margen_r_menos_g: float = 0.02
    g_entregado: tuple[float, float] = (-0.05, 0.10)
    umbral_valor: float = 0.15           # V/P − 1 para barato (≥) y caro (≤ −)
    umbral_crecimiento: float = 0.01     # entregado − implícito
    vigencia_cap_rate_meses: int = 18
    primas_de_sensibilidad: tuple[float, ...] = (0.02, 0.03, 0.04)


SUPUESTOS = Supuestos()

NOTAS_DE_METODO: tuple[str, ...] = (
    "Diseño fijado antes de correr, en su propio commit: supuestos, umbrales de la señal absoluta e "
    "hipótesis. La prueba 54 los congela.",
    "Tasa de descuento: Treasury a 10 años + 3% (la prima de net lease de la aplicación). La señal "
    "absoluta se reporta también con 2% y 4%.",
    "DDM: dividendo vigente anualizado; crecimiento del dividendo de los 5 años previos, entre 0% y 4% y "
    "con r − g de al menos 2%. DCF: AFFO por acción (FFO donde no hay) 5 años a su crecimiento de los 5 "
    "previos (0% a 8%) y 2% perpetuo después.",
    "Crecimiento implícito: el crecimiento perpetuo que justifica el precio con la misma r; se compara "
    "contra el entregado en 5 años, entre −5% y 10%.",
    "NAV: NOI del último trimestre × 4 ÷ el cap rate de las compras del propio emisor (vigente 18 meses), "
    "menos deuda neta y preferentes, entre las acciones. NOI, balance y acciones salen del MISMO trimestre "
    "de los estados XBRL versionados, cada cifra con su fecha de publicación.",
    "Cambio de construcción hecho antes de ver retornos: NNN y WPC reportan sus gastos de inmuebles con "
    "etiquetas propias desde 2019, así que su NOI sale de los totales (ingresos − gastos totales + "
    "depreciación + deterioros + administración). Realty Income mete los intereses en sus gastos totales, "
    "así que el suyo sale de ingresos − gastos de inmuebles.",
    "Deuda: la mayor entre la etiquetada como total y la suma de sus componentes; si no llega al 60% del "
    "pasivo, faltan etiquetas y el mes queda vacío (O, de fines de 2017 a mediados de 2018).",
    "El NAV de WPC se usa desde 2019: antes, su negocio de administración de fondos dejaba el "
    "apalancamiento armado 20–50% arriba del reportado. Validación completa en la tabla del NAV.",
    "Señal absoluta: barato si el valor supera al precio en 15% o más, caro si queda 15% o más abajo; en "
    "crecimiento, ±1 punto. Contra su historia: percentil expandible ≥ 70 barato, < 30 caro.",
)

INTRINSECOS: tuple[Metodo, ...] = (
    Metodo("ddm", "DDM (Gordon sobre el dividendo)",
           "Dividendo vigente × (1 + g) ÷ (r − g); g = crecimiento del dividendo de los 5 años previos, "
           "entre 0% y 4%; r = Treasury a 10 años + 3%. La señal es valor ÷ precio − 1."),
    Metodo("dcf", "DCF del flujo en dos etapas",
           "AFFO por acción (FFO donde no hay) creciendo 5 años a su ritmo de los 5 previos (0% a 8%) "
           "y después 2% perpetuo, descontado a r. La señal es valor ÷ precio − 1."),
    Metodo("crecimiento", "Crecimiento entregado contra implícito",
           "El crecimiento del flujo por acción de los 5 años previos menos el crecimiento perpetuo "
           "que justifica el precio con r. Positivo: el mercado descuenta menos de lo que el emisor ha hecho."),
    Metodo("nav", "NAV aproximado",
           "NOI anualizado del último trimestre ÷ el cap rate de las compras del propio emisor, menos "
           "deuda neta y preferentes, por acción. La señal es NAV ÷ precio − 1."),
)
CLAVES = tuple(m.clave for m in INTRINSECOS)


# --------------------------------------------------------------------------------------
# Fórmulas
# --------------------------------------------------------------------------------------


def acotar(g: float, limites: tuple[float, float], r: float | None = None, margen: float = 0.0) -> float:
    """``g`` dentro de ``limites`` y, si se da ``r``, con ``r − g ≥ margen``."""
    if g is None or pd.isna(g):
        return np.nan
    x = min(max(float(g), limites[0]), limites[1])
    if r is not None and not pd.isna(r):
        x = min(x, float(r) - margen)
    return x


def ddm(dividendo: float, g: float, r: float) -> float:
    """Gordon: ``D₀(1+g)/(r−g)``. NaN si falta algo o ``r ≤ g``."""
    if any(pd.isna(x) for x in (dividendo, g, r)) or dividendo <= 0 or r <= g:
        return np.nan
    return dividendo * (1 + g) / (r - g)


def dcf_dos_etapas(flujo: float, g1: float, g2: float, r: float, anios: int = 5) -> float:
    """Valor presente de ``anios`` flujos creciendo a ``g1`` y un terminal de Gordon a ``g2``."""
    if any(pd.isna(x) for x in (flujo, g1, g2, r)) or flujo <= 0 or r <= g2:
        return np.nan
    k = np.arange(1, anios + 1)
    flujos = flujo * (1 + g1) ** k
    presente = float(np.sum(flujos / (1 + r) ** k))
    terminal = flujos[-1] * (1 + g2) / (r - g2)
    return presente + terminal / (1 + r) ** anios


def crecimiento_anual(serie: pd.Series, fechas: pd.DatetimeIndex, anios: int) -> pd.Series:
    """Crecimiento anual compuesto de ``serie`` en los ``anios`` previos a cada fecha."""
    s = serie.dropna()
    if s.empty:
        return pd.Series(np.nan, index=fechas)
    hoy = s.reindex(s.index.union(fechas)).ffill().reindex(fechas)
    antes = s.reindex(s.index.union(fechas - pd.DateOffset(years=anios))).ffill().reindex(
        fechas - pd.DateOffset(years=anios))
    antes.index = fechas
    positivo = (hoy > 0) & (antes > 0)
    return ((hoy / antes) ** (1 / anios) - 1).where(positivo)


def senal_absoluta(valor: float, umbral: float) -> str:
    if valor is None or pd.isna(valor):
        return "sin dato"
    return "barato" if valor >= umbral else ("caro" if valor <= -umbral else "medio")


def crecimiento_implicito_seguro(precio: float, flujo: float, r: float) -> float:
    if any(pd.isna(x) for x in (precio, flujo, r)):
        return np.nan
    g = crecimiento_implicito(float(precio), float(flujo), float(r))
    return np.nan if g is None else g


# --------------------------------------------------------------------------------------
# Insumos del NAV desde XBRL, con la fecha de publicación de cada cifra
# --------------------------------------------------------------------------------------
#
# Cambio de construcción hecho ANTES de ver retornos, al revisar los datos: después de
# 2018 NNN y WPC reportan sus gastos de inmuebles con etiquetas propias que no vienen en
# us-gaap, así que «ingresos − gastos de inmuebles» dejaba el NOI inflado desde ese año.
# El NOI se reconstruye entonces desde los totales, que sí están etiquetados igual toda
# la historia: ingresos − (gastos totales − depreciación − deterioros − administración).
# Realty Income no sirve con esa receta —mete el gasto por intereses dentro de sus
# gastos totales— pero sí etiqueta sus gastos de inmuebles toda la historia, salvo
# 2013–2017, donde se usan los reembolsos de inquilinos, que en net lease son casi el
# mismo gasto. Los ingresos de manejo de fondos de WPC (hasta 2017) quedan dentro:
# su costo ya está en los gastos totales.

RECETAS_NOI: dict[str, dict] = {
    "O": {"ingresos": ("Revenues", "RealEstateRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax"),
          "gastos_inmuebles": ("DirectCostsOfLeasedAndRentedPropertyOrEquipment", "TenantReimbursements")},
    "NNN": {"ingresos": ("Revenues",), "gastos_totales": ("OperatingExpenses", "CostsAndExpenses"),
            "depreciacion": ("DepreciationAndAmortization", "DepreciationDepletionAndAmortization"),
            "deterioro": ("ImpairmentOfRealEstate",), "administracion": ("GeneralAndAdministrativeExpense",)},
    "WPC": {"ingresos": ("Revenues",), "gastos_totales": ("CostsAndExpenses", "OperatingExpenses"),
            "depreciacion": ("DepreciationAndAmortization", "DepreciationDepletionAndAmortization"),
            "deterioro": ("ImpairmentOfRealEstate",), "administracion": ("GeneralAndAdministrativeExpense",)},
}
# Un NOI de hace más de un año no describe el portafolio de hoy.
ANTIGUEDAD_MAXIMA_NOI = pd.DateOffset(months=12)
ADMINISTRACION = ("GeneralAndAdministrativeExpense",)
# Conceptos que valen cero si el emisor no los reporta ese trimestre (no hubo deterioro).
OPCIONALES = ("deterioro", "gastos_inmuebles")
COMPONENTES_DEUDA = ("deuda_hipotecaria", "notas_senior", "linea_de_credito", "prestamos_a_plazo",
                     "otras_notas_por_pagar")
# Etiquetas fijas por renglón del balance, en orden de preferencia: en cada fecha gana la
# primera que traiga dato. No se usa la elección de etiquetas del módulo de estados, que
# se hace con TODA la historia a la vista: con los datos de hoy escoge para la línea de
# crédito de NNN una etiqueta que en 2012 no existía y el NAV de 2012 cambiaba según lo
# que se publicó después (P1).
ETIQUETAS_BALANCE: dict[str, tuple[str, ...]] = {
    "deuda_total": ("DebtLongtermAndShorttermCombinedAmount", "LongTermDebt"),
    "deuda_hipotecaria": ("SecuredDebt", "SecuredLongTermDebt"),
    "notas_senior": ("NotesPayable", "SeniorNotes", "SeniorLongTermNotes"),
    "linea_de_credito": ("RevolvingCreditFacilityAndCommercialPaper", "LineOfCredit", "LinesOfCreditCurrent",
                         "LongTermLineOfCredit"),
    "prestamos_a_plazo": ("LoansPayable", "UnsecuredDebt"),
    "otras_notas_por_pagar": ("OtherNotesPayable",),
    "efectivo": ("CashAndCashEquivalentsAtCarryingValue", "Cash"),
    "pasivos_totales": ("Liabilities",),
    "capital_preferente": ("PreferredStockValue",),
    "acciones_en_circulacion": ("CommonStockSharesOutstanding",),
}


def _trimestres(crudos: pd.DataFrame, tags: tuple[str, ...]) -> pd.DataFrame:
    """Cada trimestre de ``tags`` como se conocía en cada fecha de publicación.

    Un trimestre se publica directo (Q) o se deduce del acumulado del año: el Q4 es el
    año menos los nueve meses, el Q2 el semestre menos el Q1. La deducción se hace con las
    versiones conocidas en CADA fecha, no con las mejores de toda la historia: así una
    reexpresión de 2013 no cambia lo que se sabía en 2012 (P1). Los tres emisores cierran
    su año fiscal en diciembre.
    """
    columnas = ["tag", "fecha_dato", "fecha_publicacion", "valor"]
    c = crudos[(crudos["tag"].isin(tags)) & (crudos["unidad"] == "USD")
               & crudos["periodo_tipo"].isin(["Q", "H1", "9M", "FY"])].copy()
    if c.empty:
        return pd.DataFrame(columns=columnas)
    c["fecha_dato"] = pd.to_datetime(c["fecha_dato"])
    c["fecha_inicio"] = pd.to_datetime(c["fecha_inicio"])
    c["fecha_publicacion"] = pd.to_datetime(c["fecha_publicacion"])
    acumulado = (c["fecha_inicio"].dt.month == 1) & (c["fecha_inicio"].dt.day == 1)
    filas = []
    for tag, g in c.groupby("tag"):
        directos = g[g["periodo_tipo"] == "Q"]
        acum = g[acumulado.loc[g.index]]
        for fin in sorted(set(g["fecha_dato"])):
            if fin.month not in (3, 6, 9, 12) or not fin.is_month_end:
                continue
            previo = fin - pd.offsets.QuarterEnd(1) if fin.month != 3 else None
            d = directos[directos["fecha_dato"] == fin]
            a = acum[acum["fecha_dato"] == fin]
            b = acum[acum["fecha_dato"] == previo] if previo is not None else acum.iloc[0:0]
            fechas = sorted(set(d["fecha_publicacion"]) | set(a["fecha_publicacion"]) | set(b["fecha_publicacion"]))
            anterior = None
            for v in fechas:
                dv = d[d["fecha_publicacion"] <= v]
                if not dv.empty:
                    valor = float(dv.sort_values("fecha_publicacion")["valor"].iloc[-1])
                else:
                    av, bv = a[a["fecha_publicacion"] <= v], b[b["fecha_publicacion"] <= v]
                    if av.empty or (previo is not None and bv.empty):
                        continue
                    valor = float(av.sort_values("fecha_publicacion")["valor"].iloc[-1])
                    if previo is not None:
                        valor -= float(bv.sort_values("fecha_publicacion")["valor"].iloc[-1])
                if valor != anterior:
                    filas.append({"tag": tag, "fecha_dato": fin, "fecha_publicacion": v, "valor": valor})
                    anterior = valor
    return pd.DataFrame(filas, columns=columnas)


def _conocido(versiones: pd.DataFrame, cadena: tuple[str, ...], periodo: pd.Timestamp,
              fecha: pd.Timestamp) -> float:
    """El valor de ``periodo`` publicado a ``fecha``: la primera etiqueta de la cadena que lo
    traiga, y de ella la versión más reciente conocida."""
    v = versiones[(versiones["fecha_dato"] == periodo) & (versiones["fecha_publicacion"] <= fecha)]
    for tag in cadena:
        x = v[v["tag"] == tag]
        if not x.empty:
            return float(x.sort_values("fecha_publicacion")["valor"].iloc[-1])
    return np.nan


def _noi_de(versiones: pd.DataFrame, receta: dict, periodo: pd.Timestamp, fecha: pd.Timestamp):
    """NOI y administración del trimestre ``periodo`` con lo publicado a ``fecha``, o None si falta algo."""
    valores = {}
    for concepto, cadena in receta.items():
        x = _conocido(versiones, cadena, periodo, fecha)
        valores[concepto] = 0.0 if (np.isnan(x) and concepto in OPCIONALES) else x
    if any(np.isnan(x) for x in valores.values()):
        return None
    if "gastos_totales" in receta:
        operativos = (valores["gastos_totales"] - valores["depreciacion"] - valores["deterioro"]
                      - valores["administracion"])
        noi = valores["ingresos"] - operativos
    else:
        noi = valores["ingresos"] - valores["gastos_inmuebles"]
    return noi, _conocido(versiones, ADMINISTRACION, periodo, fecha)


def _balance_versiones(crudos: pd.DataFrame) -> pd.DataFrame:
    """Todas las versiones de los saldos que usa el NAV: renglón, corte, publicación, etiqueta, valor."""
    todas = {t: linea for linea, cadena in ETIQUETAS_BALANCE.items() for t in cadena}
    c = crudos[crudos["tag"].isin(todas) & (crudos["periodo_tipo"] == "PUNTUAL")].copy()
    if c.empty:
        return pd.DataFrame(columns=["linea", "tag", "fecha_dato", "fecha_publicacion", "valor"])
    c["linea"] = c["tag"].map(todas)
    c["fecha_dato"] = pd.to_datetime(c["fecha_dato"])
    c["fecha_publicacion"] = pd.to_datetime(c["fecha_publicacion"])
    return c[["linea", "tag", "fecha_dato", "fecha_publicacion", "valor"]]


def _balance_de(conocido: pd.DataFrame, corte: pd.Timestamp) -> dict | None:
    """Deuda, efectivo, preferentes y acciones del balance ``corte``, o None si la deuda no es creíble."""
    del_corte = conocido[conocido["fecha_dato"] == corte]
    ultimo = {}
    for linea, cadena in ETIQUETAS_BALANCE.items():
        for tag in cadena:
            x = del_corte[del_corte["tag"] == tag]
            if not x.empty:
                ultimo[linea] = float(x.sort_values("fecha_publicacion")["valor"].iloc[-1])
                break
    ultimo = pd.Series(ultimo, dtype=float)
    componentes = float(ultimo.reindex(list(COMPONENTES_DEUDA)).fillna(0.0).sum())
    total = float(ultimo["deuda_total"]) if pd.notna(ultimo.get("deuda_total")) else 0.0
    deuda = max(total, componentes)
    pasivos = ultimo.get("pasivos_totales")
    # Si lo armado no llega ni al 60% del pasivo, faltan etiquetas (O etiquetó sus bonos
    # de 2017 a mediados de 2018 con una etiqueta propia): se deja vacío, no se inventa.
    if deuda <= 0 or (pd.notna(pasivos) and deuda < PISO_DEUDA_SOBRE_PASIVO * float(pasivos)):
        return None
    return {"deuda": deuda, "efectivo": float(ultimo.get("efectivo", 0.0) or 0.0),
            "preferentes": float(ultimo.get("capital_preferente", 0.0) or 0.0),
            "acciones": float(ultimo["acciones_en_circulacion"]) if pd.notna(ultimo.get("acciones_en_circulacion"))
            else np.nan}


PISO_DEUDA_SOBRE_PASIVO = 0.60
# Desde qué trimestre sirve el NAV de cada emisor. WPC tuvo hasta la fusión con CPA:17
# (oct-2018) un negocio de administración de fondos cuyas utilidades y participaciones no
# pasan por los ingresos: antes de 2019 su apalancamiento armado sale 25–35% arriba del
# que reportó. Se decidió con esa validación, antes de ver retornos.
NAV_DESDE: dict[str, pd.Timestamp] = {"WPC": pd.Timestamp("2019-03-31")}
DIAS_PORTADA = 150    # la portada del 10-Q/10-K del trimestre sale dentro de ~5 meses


def nav_conocido(crudos: pd.DataFrame, ticker: str, fechas: pd.DatetimeIndex) -> pd.DataFrame:
    """A cada fecha: el último trimestre con NOI Y balance publicados, los dos del MISMO corte.

    Mezclar el NOI de un trimestre con el balance del siguiente rompe el NAV justo cuando
    importa: después de la compra de VEREIT (nov-2021) O traía la deuda nueva con el NOI
    viejo y el NAV salía a la mitad.
    """
    columnas = ["trimestre", "noi", "administracion", "deuda", "efectivo", "preferentes", "acciones"]
    salida = pd.DataFrame(np.nan, index=fechas, columns=columnas)
    receta = RECETAS_NOI.get(ticker)
    if receta is None or crudos is None or crudos.empty:
        return salida
    todos = tuple(dict.fromkeys(t for cadena in receta.values() for t in cadena)) + ADMINISTRACION
    versiones = _trimestres(crudos, tuple(dict.fromkeys(todos)))
    ingresos = versiones[versiones["tag"].isin(receta["ingresos"])]
    b = _balance_versiones(crudos)
    if b.empty or ingresos.empty:
        return salida
    portada = crudos[crudos["tag"] == "EntityCommonStockSharesOutstanding"].copy()
    portada["fecha_dato"] = pd.to_datetime(portada["fecha_dato"])
    portada["fecha_publicacion"] = pd.to_datetime(portada["fecha_publicacion"])
    for f in fechas:
        periodos = ingresos.loc[ingresos["fecha_publicacion"] <= f, "fecha_dato"]
        conocido = b[b["fecha_publicacion"] <= f]
        if periodos.empty or conocido.empty:
            continue
        cortes = set(conocido.loc[conocido["linea"].isin(["deuda_total", *COMPONENTES_DEUDA]), "fecha_dato"])
        reciente = periodos.max()
        for periodo in sorted(periodos.unique(), reverse=True):
            periodo = pd.Timestamp(periodo)
            if periodo < reciente - ANTIGUEDAD_MAXIMA_NOI:
                break
            if periodo not in cortes:
                continue
            noi = _noi_de(versiones, receta, periodo, f)
            bal = _balance_de(conocido, periodo) if noi else None
            if not bal:
                continue
            if np.isnan(bal["acciones"]):
                p = portada[(portada["fecha_publicacion"] <= f) & (portada["fecha_dato"] > periodo)
                            & (portada["fecha_dato"] <= periodo + pd.Timedelta(days=DIAS_PORTADA))]
                if not p.empty:
                    bal["acciones"] = float(p.sort_values(["fecha_dato", "fecha_publicacion"])["valor"].iloc[-1])
            salida.loc[f] = [periodo.value, noi[0], noi[1], bal["deuda"], bal["efectivo"], bal["preferentes"],
                             bal["acciones"]]
            break
    salida["trimestre"] = pd.to_datetime(salida["trimestre"])
    return salida


def insumos_nav(e, fechas: pd.DatetimeIndex, crudos: pd.DataFrame | None = None,
                supuestos: Supuestos = SUPUESTOS) -> pd.DataFrame:
    """NOI anualizado, deuda neta, preferentes, acciones y cap rate conocidos a cada fecha."""
    from src.datos import almacen
    from src.estudio import reglas as rg

    if crudos is None:
        try:
            crudos = almacen.leer_crudos(e.ticker)
        except (FileNotFoundError, OSError):
            crudos = pd.DataFrame()
    n = nav_conocido(crudos, e.ticker, fechas)
    d = pd.DataFrame(index=fechas)
    d["trimestre_nav"] = n["trimestre"]
    d["noi_anualizado"] = n["noi"].astype(float) * 4
    d["administracion_anualizada"] = n["administracion"].astype(float) * 4
    d["deuda_neta"] = n["deuda"].astype(float) - n["efectivo"].astype(float).fillna(0.0)
    d["preferentes"] = n["preferentes"].astype(float).fillna(0.0)
    d["acciones"] = n["acciones"].astype(float)
    primarios = getattr(e, "primarios", None)
    if primarios is not None and not primarios.empty and "cap_rate_adquisicion" in set(primarios["concepto"]):
        v, conocido = rg._primaria(primarios, "cap_rate_adquisicion")
        d["cap_rate"] = rg._anual_vigente(v, conocido, fechas, vigencia_meses=supuestos.vigencia_cap_rate_meses)
    else:
        d["cap_rate"] = np.nan
    d["nav"] = ((d["noi_anualizado"] / d["cap_rate"] - d["deuda_neta"] - d["preferentes"]) / d["acciones"])
    desde = NAV_DESDE.get(e.ticker)
    if desde is not None:
        d.loc[~(d["trimestre_nav"] >= desde), "nav"] = np.nan
    # El apalancamiento con el que se valida contra lo que reporta el emisor.
    ebitda = d["noi_anualizado"] - d["administracion_anualizada"]
    d["deuda_neta_ebitda"] = d["deuda_neta"] / ebitda.where(ebitda > 0)
    return d



def validacion_nav(e, d: pd.DataFrame) -> pd.DataFrame:
    """Cada año: el apalancamiento armado desde XBRL contra el que reportó el emisor."""
    from src.estudio import reglas as rg

    primarios = getattr(e, "primarios", None)
    if primarios is None or primarios.empty or "deuda_neta_ebitdare_proforma" not in set(primarios["concepto"]):
        return pd.DataFrame(columns=["emisor", "anio", "armado", "reportado", "diferencia", "se_usa"])
    v, _ = rg._primaria(primarios, "deuda_neta_ebitdare_proforma")
    filas = []
    for anio, rep in v.dropna().items():
        corte = pd.Timestamp(int(anio), 12, 31)
        # Los meses cuyo NAV sale de algún trimestre de ese año: la mediana de lo armado.
        del_anio = d["trimestre_nav"].dt.year == int(anio)
        x = d.loc[del_anio, "deuda_neta_ebitda"].dropna()
        if x.empty:
            continue
        armado = float(x.median())
        # Se usa si ese año hubo NAV: hace falta además el cap rate, y WPC solo desde 2019.
        filas.append({"emisor": e.ticker, "anio": int(anio), "armado": armado, "reportado": float(rep),
                      "diferencia": armado / float(rep) - 1,
                      "se_usa": bool(d.loc[del_anio, "nav"].notna().any()
                                     and corte >= NAV_DESDE.get(e.ticker, pd.Timestamp.min))})
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# El panel de los cuatro modelos, sobre el panel de ``metodos``
# --------------------------------------------------------------------------------------


def _valores(p: pd.DataFrame, g_div: pd.Series, g_flujo: pd.Series, prima: float,
             s: Supuestos) -> dict[str, pd.Series]:
    r = p["treasury_10a"] + prima
    g_d = pd.Series([acotar(g, s.g_dividendo, rr, s.margen_r_menos_g) for g, rr in zip(g_div, r, strict=True)],
                    index=p.index)
    g_1 = g_flujo.clip(*s.g_flujo)
    g_2 = pd.Series([min(s.g_terminal, rr - s.margen_r_menos_g) if pd.notna(rr) else np.nan for rr in r],
                    index=p.index)
    valor_ddm = pd.Series([ddm(d, g, rr) for d, g, rr in zip(p["dividendo"], g_d, r, strict=True)], index=p.index)
    valor_dcf = pd.Series([dcf_dos_etapas(f, a, b, rr, s.anios_etapa_1)
                           for f, a, b, rr in zip(p["flujo"], g_1, g_2, r, strict=True)], index=p.index)
    implicito = pd.Series([crecimiento_implicito_seguro(px, f, rr)
                           for px, f, rr in zip(p["precio"], p["flujo"], r, strict=True)], index=p.index)
    return {"r": r, "g_ddm": g_d, "g_flujo_5a": g_1, "g_implicito": implicito, "valor_ddm": valor_ddm,
            "valor_dcf": valor_dcf, "ddm": valor_ddm / p["precio"] - 1, "dcf": valor_dcf / p["precio"] - 1,
            "crecimiento": g_flujo.clip(*s.g_entregado) - implicito}


def agregar(p: pd.DataFrame, e, *, supuestos: Supuestos = SUPUESTOS, crudos: pd.DataFrame | None = None,
            nav: pd.DataFrame | None = None) -> pd.DataFrame:
    """Agrega al panel de ``metodos`` los cuatro modelos: valor, percentil y señal absoluta."""
    from src.estudio.metodos import MIN_MESES, senal
    from src.modelo.senal import percentil_expandible

    s = supuestos
    p = p.copy()
    t = e.tabla
    g_div = crecimiento_anual(t["dividendo_anualizado"], p.index, s.anios_historia)
    columna = "affo_ttm" if e.medida.concepto == "affo_por_accion" else "ffo_ttm"
    g_flujo = crecimiento_anual(t[columna], p.index, s.anios_historia)
    base = _valores(p, g_div, g_flujo, s.prima, s)
    for k in ("r", "g_ddm", "g_flujo_5a", "g_implicito", "valor_ddm", "valor_dcf"):
        p[k] = base[k]
    p["g_dividendo_5a"] = g_div
    p["g_flujo_5a_bruto"] = g_flujo
    n = insumos_nav(e, p.index, crudos, s) if nav is None else nav.reindex(p.index)
    for k in ("noi_anualizado", "deuda_neta", "preferentes", "acciones", "cap_rate", "nav", "trimestre_nav",
              "deuda_neta_ebitda"):
        p[k] = n[k]
    valores = {"ddm": base["ddm"], "dcf": base["dcf"], "crecimiento": base["crecimiento"],
               "nav": p["nav"] / p["precio"] - 1}
    for clave, v in valores.items():
        p[f"v_{clave}"] = v
        p[f"p_{clave}"] = percentil_expandible(v.dropna(), min_observaciones=MIN_MESES).reindex(p.index)
        p[f"s_{clave}"] = [senal(x) for x in p[f"p_{clave}"]]
        umbral = s.umbral_crecimiento if clave == "crecimiento" else s.umbral_valor
        p[f"a_{clave}"] = [senal_absoluta(x, umbral) for x in v]
    # La señal absoluta con otras primas: la sensibilidad que se reporta completa.
    for prima in s.primas_de_sensibilidad:
        otra = _valores(p, g_div, g_flujo, prima, s)
        for clave in ("ddm", "dcf", "crecimiento"):
            umbral = s.umbral_crecimiento if clave == "crecimiento" else s.umbral_valor
            p[f"a_{clave}_prima_{round(prima * 1e4)}"] = [senal_absoluta(x, umbral) for x in otra[clave]]
        p[f"a_nav_prima_{round(prima * 1e4)}"] = p["a_nav"]
    return p



# --------------------------------------------------------------------------------------
# Todo junto
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoIntrinsecos:
    paneles: dict[str, pd.DataFrame]
    percentil: dict[str, pd.DataFrame]          # evaluación por emisor, con el percentil
    absoluta: dict[str, pd.DataFrame]           # evaluación por emisor, con la señal absoluta
    juntos_percentil: pd.DataFrame
    juntos_absoluta: pd.DataFrame
    backtest_percentil: dict[str, pd.DataFrame]
    backtest_absoluta: dict[str, pd.DataFrame]
    sensibilidad: pd.DataFrame                  # la señal absoluta con primas de 2%, 3% y 4%
    asignaciones_percentil: list
    asignaciones_absoluta: list
    validacion: pd.DataFrame
    hasta: pd.Timestamp

    def hoy(self) -> pd.DataFrame:
        filas = []
        for t, p in self.paneles.items():
            u = p.iloc[-1]
            for m in INTRINSECOS:
                valor = {"ddm": u["valor_ddm"], "dcf": u["valor_dcf"], "nav": u["nav"]}.get(m.clave, np.nan)
                filas.append({"emisor": t, "metodo": m.nombre, "clave": m.clave, "precio": u["precio"],
                              "valor_por_accion": valor, "valor_contra_precio": u[f"v_{m.clave}"],
                              "senal_absoluta": u[f"a_{m.clave}"], "percentil": u[f"p_{m.clave}"],
                              "senal_percentil": u[f"s_{m.clave}"]})
        return pd.DataFrame(filas)


def _asignar_o_nada(m, paneles, clave, **kw):
    from src.estudio.metodos import asignar

    try:
        return asignar(m, paneles, clave, **kw)
    except ValueError:
        return None


def estudiar(estudios: dict, paneles_metodos: dict[str, pd.DataFrame], *, n_azar: int = 200,
             supuestos: Supuestos = SUPUESTOS, tbill: pd.Series | None = None) -> ResultadoIntrinsecos:
    from src.estudio import metodos as mt
    from src.estudio import reglas as rg

    tbill = rg.cargar_tbill() if tbill is None else tbill
    paneles, validaciones = {}, []
    for t, e in estudios.items():
        paneles[t] = agregar(paneles_metodos[t], e, supuestos=supuestos)
        validaciones.append(validacion_nav(e, paneles[t]))
    percentil = {t: mt.evaluar(p, INTRINSECOS) for t, p in paneles.items()}
    absoluta = {t: mt.evaluar(p, INTRINSECOS, valor="v_", senal="a_") for t, p in paneles.items()}
    bt_p = {t: mt.backtest_metodos(e, paneles[t], tbill, INTRINSECOS) for t, e in estudios.items()}
    bt_a = {t: mt.backtest_metodos(e, paneles[t], tbill, INTRINSECOS, senal="a_") for t, e in estudios.items()}
    filas = []
    for prima in supuestos.primas_de_sensibilidad:
        sufijo = f"_prima_{round(prima * 1e4)}"
        variantes = tuple(Metodo(f"{m.clave}{sufijo}", m.nombre, "") for m in INTRINSECOS)
        for t, e in estudios.items():
            b = bt_a[t] if prima == supuestos.prima else mt.backtest_metodos(e, paneles[t], tbill, variantes,
                                                                             senal="a_")
            for m, fila in zip(INTRINSECOS, b.itertuples(), strict=True):
                a = paneles[t][f"a_{m.clave}{sufijo}"]
                a = a[a != "sin dato"]
                filas.append({"prima": prima, "emisor": t, "clave": m.clave, "metodo": m.nombre,
                              "fraccion_barato": float((a == "barato").mean()) if len(a) else np.nan,
                              "fraccion_caro": float((a == "caro").mean()) if len(a) else np.nan,
                              "ventaja_tir": fila.ventaja_tir})
    mercado = mt.mercado_comun(estudios)
    comun = {"n_azar": n_azar}
    asig_p = [_asignar_o_nada(mercado, paneles, m.clave, nombre=m.nombre, **comun) for m in INTRINSECOS]
    asig_a = [_asignar_o_nada(mercado, paneles, m.clave, prefijo="v_", nombre=m.nombre, **comun)
              for m in INTRINSECOS]
    return ResultadoIntrinsecos(
        paneles=paneles, percentil=percentil, absoluta=absoluta,
        juntos_percentil=mt.evaluar_juntos(paneles, INTRINSECOS),
        juntos_absoluta=mt.evaluar_juntos(paneles, INTRINSECOS, valor="v_", senal="a_"),
        backtest_percentil=bt_p, backtest_absoluta=bt_a, sensibilidad=pd.DataFrame(filas),
        asignaciones_percentil=[a for a in asig_p if a is not None],
        asignaciones_absoluta=[a for a in asig_a if a is not None],
        validacion=pd.concat(validaciones, ignore_index=True),
        hasta=max(e.tabla.index[-1] for e in estudios.values()),
    )


# --------------------------------------------------------------------------------------
# Conclusiones en texto
# --------------------------------------------------------------------------------------


def _pct(x, d: int = 0) -> str:
    return "—" if x is None or pd.isna(x) else f"{x:.{d}%}"


def _pb(x) -> str:
    return "—" if x is None or pd.isna(x) else f"{x * 1e4:+,.0f} pb"


def _rango(serie: pd.Series, formato) -> str:
    s = serie.dropna()
    if s.empty:
        return "—"
    return formato(s.min()) if s.min() == s.max() else f"entre {formato(s.min())} y {formato(s.max())}"


def _controles(f: pd.Series) -> dict[str, bool]:
    return {"gana": f["ventaja"] > 0, "el espejo pierde": f["ventaja_el_mas_caro"] < 0,
            "el azar casi nunca la iguala": f["azar_que_le_gana"] <= 0.05,
            "gana en las dos mitades": f["ventaja_primera_mitad"] > 0 and f["ventaja_segunda_mitad"] > 0}


FALLA = {"gana": "no le gana a partes iguales", "el espejo pierde": "el espejo no pierde",
         "el azar casi nunca la iguala": "el azar la iguala con frecuencia",
         "gana en las dos mitades": "no gana en las dos mitades"}


def conclusiones(ri: ResultadoIntrinsecos, rm) -> list:
    """Lo que salió de los cuatro modelos, contra lo que se escribió antes de correr."""
    from src.estudio.metodos import tabla_asignaciones
    from src.estudio.reglas import Conclusion

    c = []
    n = len(ri.paneles)
    sens = ri.sensibilidad
    base = sens[sens["prima"] == SUPUESTOS.prima]
    de_flujo = ["ddm", "dcf", "crecimiento"]
    flujo = base[base["clave"].isin(de_flujo)]
    alta = sens[(sens["prima"] == max(SUPUESTOS.primas_de_sensibilidad)) & sens["clave"].isin(de_flujo)]
    nav = base[base["clave"] == "nav"]
    casi_siempre = bool((flujo["fraccion_barato"] >= 0.6).all())
    c.append(Conclusion(
        "En absoluto, el DDM y el DCF casi siempre dicen «comprar»" if casi_siempre else
        "En absoluto, el DDM y el DCF",
        f"Con la tasa de la aplicación (Treasury + 3%), el DDM, el DCF y el crecimiento dijeron «barato» "
        f"{_rango(flujo['fraccion_barato'], _pct)} de los meses, según el modelo y el emisor; con 4% de prima, "
        f"{_rango(alta['fraccion_barato'], _pct)}. Con el crecimiento que estos emisores entregaron, el valor "
        f"de Gordon queda casi siempre arriba del precio. Una regla que casi siempre compra es aportar sin "
        f"reglas, y por eso su diferencia contra aportar siempre queda "
        f"{_rango(sens.loc[sens['clave'] != 'nav', 'ventaja_tir'], _pb)} al año con cualquiera de las tres "
        f"primas. El NAV es lo contrario: con el cap rate de sus propias compras, los emisores casi nunca "
        f"cotizaron abajo de su NAV —«barato» {_rango(nav['fraccion_barato'], _pct)} de los meses— y el modelo "
        f"dijo «caro» {_rango(nav['fraccion_caro'], _pct)}.",
        "desfavorable"))

    jp, ja = ri.juntos_percentil, ri.juntos_absoluta
    div = rm.juntos.loc["dividendo"]
    ddm_ok = jp.loc["ddm", "rho_5a"] > 0 and jp.loc["ddm", "emisores_con_rho_5a_positiva"] == n
    ddm_peor = (jp.loc["ddm", "rho_5a"] < div["rho_5a"]
                and jp.loc["ddm", "r5_barato_menos_caro"] < div["r5_barato_menos_caro"])
    malos = [k for k in ("dcf", "crecimiento") if not jp.loc[k, "rho_5a"] > 0.1]
    inicio_nav = min(p["nav"].first_valid_index() for p in ri.paneles.values() if p["nav"].notna().any())
    fin_nav = max(p["nav"].first_valid_index() for p in ri.paneles.values() if p["nav"].notna().any())
    if pd.isna(jp.loc["ddm", "rho_5a"]):
        texto = "El DDM en percentil todavía no tiene 5 años siguientes que medir."
    else:
        texto = (f"El DDM en percentil {'predice en los ' + _cuantos(n) + ' emisores' if ddm_ok else 'no predice en todos los emisores'}"
                 f"{', pero menos que' if ddm_peor else '; contra'} el yield de dividendo solo: correlación con "
                 f"los 5 años siguientes de {_signo(jp.loc['ddm', 'rho_5a'])} contra {_signo(div['rho_5a'])}, y "
                 f"{_puntos(jp.loc['ddm', 'r5_barato_menos_caro'])} al año entre barato y caro contra "
                 f"{_puntos(div['r5_barato_menos_caro'])}.")
    if ddm_peor:
        texto += " Agregarle un crecimiento estimado le quitó información en vez de dársela."
    if malos:
        texto += (" " + " y ".join(NOMBRES[k] for k in malos) + (" no predice" if len(malos) == 1 else " no predicen")
                  + ": correlación de " + " y ".join(_signo(jp.loc[k, "rho_5a"]) for k in malos)
                  + ", a favor en " + " y ".join(str(int(jp.loc[k, "emisores_con_rho_5a_positiva"])) for k in malos)
                  + f" de los {_cuantos(n)} emisores.")
    texto += (f" El NAV tiene {_signo(jp.loc['nav', 'rho_5a'])} de correlación en percentil y "
              f"{_signo(ja.loc['nav', 'rho_5a'])} en absoluto, con {jp.loc['nav', 'ventanas_5a']:.0f} ventanas "
              f"de 5 años independientes: el NAV armado empieza entre {inicio_nav:%Y} y {fin_nav:%Y} según el "
              f"emisor y no alcanza para concluir nada.")
    c.append(Conclusion(
        "Contra su propia historia, ninguno supera a los métodos simples" if ddm_peor and malos else
        "Contra su propia historia", texto, "desfavorable" if ddm_peor and malos else "neutral"))

    tablas = {"por percentil": tabla_asignaciones(ri.asignaciones_percentil) if ri.asignaciones_percentil
              else pd.DataFrame(),
              "por valor absoluto": tabla_asignaciones(ri.asignaciones_absoluta) if ri.asignaciones_absoluta
              else pd.DataFrame()}
    cons = rm.asignacion().loc["consenso"]
    todos = [(k, forma, f, _controles(f)) for forma, t in tablas.items() for k, f in t.iterrows()]
    pasan = [f"{NOMBRES[k]} {forma}" for k, forma, _, ok in todos if all(ok.values())]
    texto = ("Ningún modelo de valor pasa los cuatro controles: gana, el espejo pierde, el azar casi nunca "
             "la iguala y gana en las dos mitades." if not pasan else
             f"Pasan los cuatro controles: {', '.join(pasan)}.")
    if todos:
        k, forma, f, ok = max(todos, key=lambda x: x[2]["ventaja"])
        if not all(ok.values()):
            fallan = [FALLA[nombre] for nombre, bien in ok.items() if not bien]
            texto += (f" La mejor cifra es la del {NOMBRES[k]} {forma}, {_pb(f['ventaja'])} al año desde "
                      f"{f['desde']:%Y}, pero {' y '.join(fallan)}: "
                      f"{_pb(f['ventaja_primera_mitad'])} en la primera mitad y "
                      f"{_pb(f['ventaja_segunda_mitad'])} en la segunda.")
            meses = {x: int(f[f"meses_{x}"]) for x in ri.paneles if f"meses_{x}" in f}
            dominante = max(meses, key=meses.get)
            if forma == "por valor absoluto" and k != "nav" and meses[dominante] > 0.6 * sum(meses.values()):
                texto += (f" Además manda {meses[dominante]} de {sum(meses.values())} meses a {dominante}: entre "
                          f"emisores, un valor de Gordon termina comparando yields, que es lo que P4 prohíbe.")
    cons_ok = all(_controles(cons).values())
    texto += (f" El consenso de los siete métodos simples sigue arriba: {_pb(cons['ventaja'])} al año"
              + (", con los cuatro controles a favor." if cons_ok else "."))
    c.append(Conclusion(f"Para escoger a cuál de los {_cuantos(n)}, tampoco" if not pasan else
                        f"Para escoger a cuál de los {_cuantos(n)}", texto,
                        "desfavorable" if not pasan else "neutral"))

    h = ri.hoy()
    partes, dcf_barato, nav_barato = [], [], []
    for t in ri.paneles:
        x = h[h["emisor"] == t].set_index("clave")
        partes.append(f"{t}: NAV {x.loc['nav', 'valor_por_accion']:.2f} dólares contra un precio de "
                      f"{x.loc['nav', 'precio']:.2f} ({x.loc['nav', 'senal_absoluta']}), DDM "
                      f"{x.loc['ddm', 'valor_por_accion']:.2f} ({x.loc['ddm', 'senal_absoluta']})")
        if x.loc["dcf", "senal_absoluta"] == "barato":
            dcf_barato.append(t)
        if x.loc["nav", "senal_absoluta"] == "barato":
            nav_barato.append(t)
    dcf = (f"El DCF dice «barato» en los {_cuantos(n)}" if len(dcf_barato) == n else
           f"El DCF dice «barato» en {', '.join(dcf_barato) or 'ninguno'}")
    lectura = ("ninguno cotiza con descuento claro contra el valor de sus inmuebles al cap rate al que el "
               "propio emisor está comprando" if not nav_barato else
               f"{', '.join(nav_barato)} cotiza con descuento de 15% o más contra su NAV")
    c.append(Conclusion("Qué dicen hoy", "; ".join(partes) + f". {dcf}. La lectura más útil es la del NAV: "
                        f"{lectura}.", "neutral"))

    h1 = ddm_peor and bool(malos)
    h2 = casi_siempre
    h3 = jp.loc["nav", "ventanas_5a"] < 5
    cumplidas = sum([h1, h2, h3])
    c.append(Conclusion(
        "Lo que se escribió antes de correr",
        f"Se cumplieron {cumplidas} de las 3 hipótesis del diseño. "
        f"(1) El DDM y el DCF en percentil no agregan a los métodos simples: {'sí' if h1 else 'no'}. "
        f"(2) En absoluto casi siempre compran: {'sí' if h2 else 'no'}. "
        f"(3) El NAV podría aportar algo, pero con poca historia: {'sí' if h3 else 'no'}. "
        "La regla recomendada sigue siendo el consenso de los siete. Para que el NAV sirva hace falta el NOI "
        "del suplemento de cada trimestre —el que se armó aquí sale de totales XBRL y se valida contra el "
        "apalancamiento reportado— y más años.",
        "neutral"))
    return c


def _cuantos(n: int) -> str:
    return {2: "dos", 3: "tres", 4: "cuatro"}.get(n, str(n))


def _signo(x) -> str:
    return "sin dato" if x is None or pd.isna(x) else f"{x:+.2f}"


def _puntos(x) -> str:
    return "sin dato" if x is None or pd.isna(x) else f"{x * 100:.1f} puntos"


NOMBRES = {"ddm": "DDM", "dcf": "DCF", "crecimiento": "crecimiento implícito", "nav": "NAV"}
