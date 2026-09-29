"""¿La valuación sabe escoger REITs? La prueba sobre el universo de REITs que cotizan hoy.

Las pruebas con O, NNN y WPC dijeron que la valuación no sirve para esperar pero sí para
escoger entre esos tres. Tres emisores de calidad, escogidos hoy, no dicen si un modelo
separa una oportunidad de una trampa. Aquí se prueba con todos los REITs de capital que
cotizan hoy en Estados Unidos, incluidos los que se desplomaron y siguen cotizando.

Diseño fijado antes de correr (commit «Diseño de la prueba del universo»)
------------------------------------------------------------------------
**Universo.** REITs de capital que cotizan hoy en NYSE o Nasdaq: industria «Real Estate
Investment Trusts» en el listado de Nasdaq o en las listas de REITs de stockanalysis, con
industria «REIT - …» distinta de «REIT - Mortgage» en stockanalysis; sin preferentes, notas
ni warrants. Precio y dividendos de Yahoo desde que cotizan (el mismo proveedor del estudio
largo), con el Treasury a 10 años de FRED y el ETF VNQ como referencia externa.

**Sesgo declarado.** No están los REITs que quebraron o fueron comprados: ninguno de los
datos disponibles aquí trae su precio. Los que se desplomaron y siguen cotizando (GNL, MPW,
SVC…) sí están. La dirección del sesgo no se puede firmar: los quebrados seguramente se veían
baratos antes de caer (su ausencia favorece a «barato»), y los comprados a menudo eran baratos
y recibieron una prima (su ausencia lo perjudica). Como indicio se compara el universo contra
VNQ, que sí los tuvo mientras existieron.

**Elegibles cada fin de mes.** Al menos 60 meses de precio, dividendo de los últimos 12 meses
mayor que cero, yield de hasta 25% (arriba es error de datos o un dividendo que ya no existe) y
precio de al menos 1 dólar. Un mes con un salto de precio de más de 50% sin evento que lo
explique se marca como error de datos y ese emisor sale ese mes.

**Tres señales, todas con precio y dividendos conocidos a esa fecha (P1):**

1. *Yield contra su propia historia*: percentil expandible del yield de dividendo de 12 meses
   del emisor contra sus propios meses anteriores (P4, P5). Es el método que funcionó con O,
   NNN y WPC.
2. *Yield contra su sector*: el yield entre la mediana del yield de su sector ese mes (industria
   de stockanalysis; sector con menos de 5 elegibles, sin señal). Pone a prueba la premisa de P4:
   si comparar yields entre emisores, aun dentro del sector, informa o engaña.
3. *DDM entre emisores*: valor de Gordon entre precio menos uno, con el dividendo de 12 meses, g
   = crecimiento del dividendo de 5 años acotado entre 0% y 4% y a r − g ≥ 2%, y r = Treasury a
   10 años + la prima del sector de la aplicación (``PRIMA_RIESGO_POR_SECTOR``; net lease para
   los emisores que la aplicación ya clasifica así).

**Grupos y carteras.** Cada fin de mes, terciles de cada señal entre los elegibles: barato,
medio y caro. Cada tercil es una cartera de pesos iguales que se mantiene 12 meses, con 12
cohortes encimadas (una formada cada mes), y el benchmark es lo mismo con TODOS los elegibles:
comprar el universo completo por partes iguales. Retorno total con dividendos reinvertidos
(precio ajustado de Yahoo), antes de impuestos, igual para todos.

**Qué se mide.**

* Retorno anual de cada tercil contra el universo, y barato menos caro, con error estándar
  Newey-West (rezago 12, por las cohortes encimadas).
* Correlación de rangos, cada mes, entre la señal y el retorno de los 12 meses siguientes: su
  promedio, qué fracción de los meses es positiva y su t de Newey-West.
* Trampas: de cada tercil, qué fracción recortó su dividendo en los 12 meses siguientes (los
  dividendos de esos 12 meses menos de 90% de los 12 anteriores) y qué fracción se desplomó
  (retorno total de 12 meses de −30% o peor).
* Variante con filtro de calidad mínimo: fuera los que recortaron el dividendo en los 12 meses
  previos. Es lo más parecido a la Puerta 1 que permiten precio y dividendos.
* Aportación mensual de 1,000 dólares repartida entre los baratos, sin vender nunca, contra la
  misma aportación repartida entre todos los elegibles: TIR money-weighted (P9).

**Controles.** 200 sorteos que reparten a los elegibles de cada mes en tres grupos del mismo
tamaño (semilla fija) para ver qué tan raro es el barato menos caro; cada mitad del periodo por
separado; la correlación dentro de cada sector.

Hipótesis escritas antes de correr
----------------------------------
1. El yield contra su propia historia predice en el universo como predijo en O, NNN y WPC:
   correlación positiva y el tercil barato arriba del universo.
2. El yield contra su sector tiene más trampas en su tercil barato —recortes y desplomes— que
   los otros grupos; si le gana al universo, le gana por menos que la señal 1.
3. El DDM entre emisores se porta como el yield contra su sector: es yield más crecimiento.
4. El filtro de dividendo intacto ayuda más a las señales 2 y 3 que a la 1.
5. El universo de pesos iguales le gana a VNQ en el periodo común: el sesgo de supervivencia
   existe, y las cifras de las señales 2 y 3 hay que leerlas como un techo.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from src.config import PRIMA_RIESGO_POR_SECTOR


@dataclass(frozen=True)
class Diseno:
    meses_minimos: int = 60
    yield_maximo: float = 0.25
    precio_minimo: float = 1.0
    salto_de_datos: float = 0.50         # un mes con +50% o −50% sin evento: error de datos
    minimo_por_sector: int = 5
    g_dividendo: tuple[float, float] = (0.0, 0.04)
    anios_crecimiento: int = 5
    margen_r_menos_g: float = 0.02
    grupos: int = 3                      # terciles
    meses_de_cohorte: int = 12
    recorte: float = 0.90                # dividendos de 12 meses < 90% de los 12 previos
    desplome: float = -0.30
    aportacion: float = 1_000.0
    sorteos: int = 200
    semilla: int = 11
    rezago_newey_west: int = 12


DISENO = Diseno()

# Industria de stockanalysis → sector de la aplicación, para la prima del DDM.
SECTOR_DE_INDUSTRIA: dict[str, str] = {
    "REIT - Retail": "Comercial",
    "REIT - Residential": "Residencial",
    "REIT - Industrial": "Industrial",
    "REIT - Office": "Oficinas",
    "REIT - Healthcare Facilities": "Salud",
    "REIT - Hotel & Motel": "Hoteles",
    "REIT - Diversified": "Diversificado",
    "REIT - Specialty": "Especializado",
}


def prima_de(industria: str, sector_aplicacion: str | None = None) -> float:
    """La prima de la aplicación: la del sector con que ya clasifica al emisor, o la de su industria."""
    if sector_aplicacion in PRIMA_RIESGO_POR_SECTOR:
        return PRIMA_RIESGO_POR_SECTOR[sector_aplicacion]
    return PRIMA_RIESGO_POR_SECTOR[SECTOR_DE_INDUSTRIA[industria]]


# --------------------------------------------------------------------------------------
# Panel mensual: un renglón por emisor y fin de mes
# --------------------------------------------------------------------------------------


SENALES = {
    "historia": "Yield contra su propia historia",
    "sector": "Yield contra su sector",
    "ddm": "DDM entre emisores",
}
GRUPOS = ("barato", "medio", "caro")


def _suma_dividendos(div: pd.DataFrame, fechas: pd.DatetimeIndex, desde_meses: int, hasta_meses: int) -> pd.Series:
    """Por fecha t: la suma de dividendos con fecha ex en (t + desde, t + hasta] meses."""
    if div.empty:
        return pd.Series(0.0, index=fechas)
    acumulado = div.set_index("fecha_ex")["monto"].sort_index().cumsum()

    def hasta(f: pd.Timestamp) -> float:
        x = acumulado[acumulado.index <= f]
        return float(x.iloc[-1]) if len(x) else 0.0

    salida = []
    for f in fechas:
        salida.append(hasta(f + pd.DateOffset(months=hasta_meses)) - hasta(f + pd.DateOffset(months=desde_meses)))
    return pd.Series(salida, index=fechas)


def panel(u: dict[str, pd.DataFrame], ust10: pd.Series, diseno: Diseno = DISENO) -> pd.DataFrame:
    """Cada emisor y fin de mes: precio, retorno, dividendos, señales y lo que pasó después."""
    from src.estudio import macro
    from src.modelo.senal import percentil_expandible

    d = diseno
    lista = u["lista"]
    capital = lista[lista["es_reit_de_capital"].astype(str).str.lower() == "true"].set_index("ticker")
    precios = u["precios"][u["precios"]["ticker"].isin(capital.index)].copy()
    precios["mes"] = precios["fecha"] + pd.offsets.MonthEnd(0)
    splits = u["splits"]
    partes = []
    for t, g in precios.groupby("ticker"):
        g = g.drop_duplicates("mes", keep="last").set_index("mes").sort_index()
        meses = g.index
        p = pd.DataFrame(index=meses)
        p["ticker"] = t
        p["industria"] = capital.loc[t, "industria"]
        p["sector_aplicacion"] = capital.loc[t, "sector_aplicacion"]
        p["precio"] = g["cierre"]
        p["retorno"] = g["ajustado"].pct_change()
        p["meses_de_historia"] = np.arange(1, len(g) + 1)
        cambio = g["cierre"].pct_change()
        con_split = set((splits.loc[splits["ticker"] == t, "fecha"] + pd.offsets.MonthEnd(0)).tolist())
        p["salto"] = ((cambio > d.salto_de_datos) | (cambio < -d.salto_de_datos)) & ~p.index.isin(con_split)
        div = u["dividendos"][u["dividendos"]["ticker"] == t]
        p["dividendo_12m"] = _suma_dividendos(div, meses, -12, 0).values
        p["dividendo_12m_previo"] = _suma_dividendos(div, meses, -24, -12).values
        p["dividendo_12m_siguiente"] = _suma_dividendos(div, meses, 0, 12).values
        p["dividendo_hace_5a"] = _suma_dividendos(div, meses, -12 * (d.anios_crecimiento + 1),
                                                   -12 * d.anios_crecimiento).values
        p["yield"] = p["dividendo_12m"] / p["precio"]
        valido = p["yield"].where((p["dividendo_12m"] > 0) & (p["yield"] <= d.yield_maximo))
        p["percentil_historia"] = percentil_expandible(valido.dropna(), min_observaciones=36).reindex(meses)
        fin = g["ajustado"].shift(-d.meses_de_cohorte)
        p["retorno_12m_siguiente"] = (fin / g["ajustado"] - 1).values
        # El último mes publicado de cada emisor no tiene 12 meses por delante: queda vacío.
        p["recorto_despues"] = np.where(p["retorno_12m_siguiente"].notna(),
                                        p["dividendo_12m_siguiente"] < d.recorte * p["dividendo_12m"], np.nan)
        p["recorto_antes"] = (p["dividendo_12m_previo"] > 0) & (p["dividendo_12m"] < d.recorte * p["dividendo_12m_previo"])
        partes.append(p)
    x = pd.concat(partes)
    x.index.name = "fecha"
    x = x.reset_index()
    x["elegible"] = ((x["meses_de_historia"] >= d.meses_minimos) & (x["dividendo_12m"] > 0)
                     & (x["yield"] <= d.yield_maximo) & (x["precio"] >= d.precio_minimo) & ~x["salto"])
    # Señal 2: contra la mediana de su sector entre los elegibles de ese mes.
    elegibles = x[x["elegible"]]
    mediana = elegibles.groupby(["fecha", "industria"])["yield"].transform("median")
    cuantos = elegibles.groupby(["fecha", "industria"])["yield"].transform("size")
    x.loc[elegibles.index, "yield_sector"] = (elegibles["yield"] / mediana).where(cuantos >= d.minimo_por_sector)
    # Señal 3: DDM con la prima de la aplicación.
    r = macro.conocido_en("ust10", ust10, pd.DatetimeIndex(x["fecha"])).to_numpy() / 100
    prima = np.array([prima_de(i, s or None) for i, s in zip(x["industria"], x["sector_aplicacion"], strict=True)])
    x["tasa"] = r + prima
    crec = (x["dividendo_12m"] / x["dividendo_hace_5a"]) ** (1 / d.anios_crecimiento) - 1
    crec = crec.where(x["dividendo_hace_5a"] > 0)
    g = np.minimum(np.clip(crec, *d.g_dividendo), x["tasa"] - d.margen_r_menos_g)
    x["g_ddm"] = g
    x["valor_ddm"] = x["dividendo_12m"] * (1 + g) / (x["tasa"] - g)
    x["ddm"] = x["valor_ddm"] / x["precio"] - 1
    x["historia"] = x["percentil_historia"]
    x["sector"] = x["yield_sector"]
    return x


def grupos(x: pd.DataFrame, senal: str, *, filtro: bool = False, diseno: Diseno = DISENO) -> pd.Series:
    """Tercil de cada emisor-mes elegible: barato (señal más alta), medio o caro."""
    base = x["elegible"] & x[senal].notna()
    if filtro:
        base &= ~x["recorto_antes"].astype(bool)
    rango = x.loc[base].groupby("fecha")[senal].rank(pct=True, method="first")
    salida = pd.Series(None, index=x.index, dtype=object)
    salida.loc[rango.index] = np.where(rango > 2 / 3, "barato", np.where(rango <= 1 / 3, "caro", "medio"))
    return salida


# --------------------------------------------------------------------------------------
# Carteras de cohortes de 12 meses
# --------------------------------------------------------------------------------------


def _matrices(x: pd.DataFrame) -> tuple[pd.DatetimeIndex, list[str], np.ndarray]:
    meses = pd.DatetimeIndex(sorted(x["fecha"].unique()))
    tickers = sorted(x["ticker"].unique())
    r = x.pivot(index="fecha", columns="ticker", values="retorno").reindex(index=meses, columns=tickers)
    return meses, tickers, r.to_numpy(float)


def _pesos(miembros: np.ndarray, cohorte: int) -> np.ndarray:
    """Meses × emisores: el peso de cada emisor en el mes SIGUIENTE a cada formación, promedio
    de las ``cohorte`` carteras vivas (cada una de pesos iguales entre sus miembros)."""
    n = miembros.sum(axis=1, keepdims=True)
    por_cohorte = np.divide(miembros, n, out=np.zeros_like(miembros, dtype=float), where=n > 0)
    vivas = np.zeros_like(por_cohorte)
    for k in range(cohorte):
        vivas[k:] += por_cohorte[: len(por_cohorte) - k]
    return vivas / cohorte


def retornos_de_grupo(miembros: np.ndarray, r: np.ndarray, cohorte: int) -> np.ndarray:
    """El retorno de cada mes de la cartera de cohortes: pesos de fin del mes anterior × retornos del mes.

    Un emisor sin retorno ese mes (no debería pasar: todos cotizan hoy) sale y su peso se reparte.
    """
    w = _pesos(miembros, cohorte)[:-1]
    rr = r[1:]
    valido = ~np.isnan(rr)
    w = np.where(valido, w, 0.0)
    total = w.sum(axis=1)
    ret = np.divide((w * np.nan_to_num(rr)).sum(axis=1), total, out=np.full(len(total), np.nan), where=total > 0)
    return np.concatenate([[np.nan], ret])


def _anual(r: pd.Series) -> float:
    r = r.dropna()
    return float((1 + r).prod() ** (12 / len(r)) - 1) if len(r) else np.nan


def _caida_maxima(r: pd.Series) -> float:
    v = (1 + r.dropna()).cumprod()
    return float((v / v.cummax() - 1).min()) if len(v) else np.nan


def _t_newey_west(serie: pd.Series, rezago: int) -> float:
    s = serie.dropna().to_numpy(float)
    n = len(s)
    if n < rezago + 5:
        return np.nan
    e = s - s.mean()
    var = e @ e / n
    for k in range(1, rezago + 1):
        var += 2 * (1 - k / (rezago + 1)) * (e[k:] @ e[:-k]) / n
    return float(s.mean() / np.sqrt(var / n)) if var > 0 else np.nan


@dataclass
class Carteras:
    senal: str
    filtro: bool
    mensual: pd.DataFrame       # retornos mensuales de barato, medio, caro y todos
    resumen: pd.DataFrame       # por grupo: retorno anual, volatilidad, caída máxima, contra todos


def carteras(x: pd.DataFrame, senal: str, *, filtro: bool = False, diseno: Diseno = DISENO) -> Carteras:
    meses, tickers, r = _matrices(x)
    g = grupos(x, senal, filtro=filtro, diseno=diseno)
    idx = {t: j for j, t in enumerate(tickers)}
    pos_mes = {m: i for i, m in enumerate(meses)}
    series = {}
    for nombre in (*GRUPOS, "todos"):
        miembros = np.zeros((len(meses), len(tickers)))
        sel = (g == nombre) if nombre != "todos" else (x["elegible"] & g.notna())
        for f, t in zip(x.loc[sel, "fecha"], x.loc[sel, "ticker"], strict=True):
            miembros[pos_mes[f], idx[t]] = 1.0
        series[nombre] = retornos_de_grupo(miembros, r, diseno.meses_de_cohorte)
    m = pd.DataFrame(series, index=meses)
    # Desde el primer mes con las 12 cohortes vivas.
    primero = g.dropna().index.map(x["fecha"]).min() if g.notna().any() else meses[-1]
    m = m[m.index > primero + pd.DateOffset(months=diseno.meses_de_cohorte)]
    filas = []
    for nombre in (*GRUPOS, "todos"):
        s = m[nombre]
        filas.append({"grupo": nombre, "retorno_anual": _anual(s), "volatilidad": float(s.std() * np.sqrt(12)),
                      "caida_maxima": _caida_maxima(s),
                      "contra_todos": _anual(s) - _anual(m["todos"]),
                      "t_contra_todos": _t_newey_west(s - m["todos"], diseno.rezago_newey_west)})
    resumen = pd.DataFrame(filas).set_index("grupo")
    resumen.loc["barato menos caro", "retorno_anual"] = _anual(m["barato"]) - _anual(m["caro"])
    resumen.loc["barato menos caro", "t_contra_todos"] = _t_newey_west(m["barato"] - m["caro"],
                                                                        diseno.rezago_newey_west)
    return Carteras(senal, filtro, m, resumen)


# --------------------------------------------------------------------------------------
# Correlación, trampas, aportación y controles
# --------------------------------------------------------------------------------------


def correlacion(x: pd.DataFrame, senal: str, diseno: Diseno = DISENO) -> pd.Series:
    """Cada mes: correlación de rangos entre la señal y el retorno de los 12 meses siguientes."""
    base = x[x["elegible"] & x[senal].notna() & x["retorno_12m_siguiente"].notna()]
    salida = {}
    for f, g in base.groupby("fecha"):
        if len(g) >= 10:
            salida[f] = float(stats.spearmanr(g[senal], g["retorno_12m_siguiente"]).statistic)
    return pd.Series(salida, dtype=float)


def trampas(x: pd.DataFrame, senal: str, *, filtro: bool = False) -> pd.DataFrame:
    g = grupos(x, senal, filtro=filtro)
    base = x.assign(grupo=g)[g.notna() & x["retorno_12m_siguiente"].notna()]
    filas = []
    for nombre, b in [*base.groupby("grupo"), ("todos", base)]:
        filas.append({"grupo": nombre, "observaciones": int(len(b)),
                      "recorto_despues": float(b["recorto_despues"].astype(float).mean()),
                      "se_desplomo": float((b["retorno_12m_siguiente"] <= DISENO.desplome).mean()),
                      "retorno_12m_mediana": float(b["retorno_12m_siguiente"].median())})
    return pd.DataFrame(filas).set_index("grupo").reindex([*GRUPOS, "todos"])


def aportacion(x: pd.DataFrame, senal: str | None, *, filtro: bool = False, diseno: Diseno = DISENO) -> dict:
    """1,000 dólares al mes repartidos entre los baratos (o entre todos los elegibles), sin vender.

    Cada compra crece con el precio ajustado del emisor hasta el último mes (todos cotizan hoy).
    """
    from src.portafolio.metricas import tir

    ajustado = (1 + x.pivot(index="fecha", columns="ticker", values="retorno").fillna(0)).cumprod()
    fin = ajustado.iloc[-1]
    if senal is None:
        sel = x["elegible"]
    else:
        sel = grupos(x, senal, filtro=filtro, diseno=diseno) == "barato"
    compras = x.loc[sel, ["fecha", "ticker"]]
    valor, flujos = 0.0, {}
    for f, g in compras.groupby("fecha"):
        monto = diseno.aportacion / len(g)
        valor += float((monto * fin[g["ticker"]] / ajustado.loc[f, g["ticker"]]).sum())
        flujos[f] = -diseno.aportacion
    s = pd.Series(flujos, dtype=float)
    if s.empty:
        return {"tir": np.nan, "aportado": 0.0, "valor": 0.0}
    s.loc[ajustado.index[-1]] = s.get(ajustado.index[-1], 0.0) + valor
    return {"tir": tir(s.sort_index()), "aportado": float(-s[s < 0].sum()), "valor": valor}


def sorteos(x: pd.DataFrame, senal: str, diseno: Diseno = DISENO) -> np.ndarray:
    """Barato menos caro con grupos al azar del mismo tamaño cada mes."""
    meses, tickers, r = _matrices(x)
    g = grupos(x, senal)
    base = x.loc[g.notna(), ["fecha", "ticker"]].assign(grupo=g[g.notna()])
    idx = {t: j for j, t in enumerate(tickers)}
    pos_mes = {m: i for i, m in enumerate(meses)}
    rng = np.random.default_rng(diseno.semilla)
    por_mes = [(pos_mes[f], np.array([idx[t] for t in b["ticker"]]), b["grupo"].to_numpy())
               for f, b in base.groupby("fecha")]
    primero = min(i for i, _, _ in por_mes) + diseno.meses_de_cohorte + 1
    salida = []
    for _ in range(diseno.sorteos):
        mb, mc = np.zeros((len(meses), len(tickers))), np.zeros((len(meses), len(tickers)))
        for i, cols, etiquetas in por_mes:
            barajadas = rng.permutation(etiquetas)
            mb[i, cols[barajadas == "barato"]] = 1.0
            mc[i, cols[barajadas == "caro"]] = 1.0
        rb = pd.Series(retornos_de_grupo(mb, r, diseno.meses_de_cohorte)[primero:])
        rc = pd.Series(retornos_de_grupo(mc, r, diseno.meses_de_cohorte)[primero:])
        salida.append(_anual(rb) - _anual(rc))
    return np.array(salida)


def referencia(u: dict[str, pd.DataFrame], mensual_todos: pd.Series) -> dict:
    """El universo de pesos iguales contra VNQ en el periodo común: el indicio del sesgo."""
    from src.estudio.universo import REFERENCIA

    p = u["precios"][u["precios"]["ticker"] == REFERENCIA].copy()
    if p.empty:
        return {"desde": None, "universo": np.nan, "vnq": np.nan}
    p["mes"] = p["fecha"] + pd.offsets.MonthEnd(0)
    v = p.drop_duplicates("mes", keep="last").set_index("mes")["ajustado"].pct_change()
    comun = mensual_todos.dropna().index.intersection(v.dropna().index)
    return {"desde": comun.min(), "universo": _anual(mensual_todos[comun]), "vnq": _anual(v[comun])}


# --------------------------------------------------------------------------------------
# Todo junto
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoSeleccion:
    panel: pd.DataFrame
    carteras: dict[tuple[str, bool], Carteras]
    correlaciones: dict[str, pd.Series]
    resumen_correlacion: pd.DataFrame
    trampas: dict[tuple[str, bool], pd.DataFrame]
    aportaciones: pd.DataFrame
    sorteos: dict[str, np.ndarray]
    mitades: pd.DataFrame
    por_sector: pd.DataFrame
    referencia: dict
    universo: pd.DataFrame          # la lista, con cuántos meses elegibles tuvo cada uno
    hasta: pd.Timestamp

    def hoy(self) -> pd.DataFrame:
        """Cada REIT elegible en el último mes: su yield, sus tres señales y su tercil."""
        x = self.panel
        ultimo = x["fecha"].max()
        h = x[(x["fecha"] == ultimo) & x["elegible"]].copy()
        for s in SENALES:
            h[f"grupo_{s}"] = grupos(x, s).loc[h.index]
        return h.sort_values("historia", ascending=False)


def _resumen_correlacion(cor: dict[str, pd.Series], diseno: Diseno) -> pd.DataFrame:
    filas = []
    for s, c in cor.items():
        filas.append({"senal": s, "meses": int(c.notna().sum()), "promedio": float(c.mean()),
                      "meses_positivos": float((c > 0).mean()), "t_newey_west": _t_newey_west(c, diseno.rezago_newey_west)})
    return pd.DataFrame(filas).set_index("senal")


def _mitades(x: pd.DataFrame, cor: dict[str, pd.Series], carteras_: dict, diseno: Diseno) -> pd.DataFrame:
    filas = []
    for s in SENALES:
        c = cor[s].dropna()
        m = carteras_[(s, False)].mensual
        corte_c, corte_m = c.index[len(c) // 2], m.index[len(m) // 2]
        for nombre, sel_c, sel_m in (("primera mitad", c.index < corte_c, m.index < corte_m),
                                     ("segunda mitad", c.index >= corte_c, m.index >= corte_m)):
            mm = m[sel_m]
            filas.append({"senal": s, "mitad": nombre, "desde": mm.index.min(), "hasta": mm.index.max(),
                          "correlacion": float(c[sel_c].mean()),
                          "barato_contra_todos": _anual(mm["barato"]) - _anual(mm["todos"]),
                          "barato_menos_caro": _anual(mm["barato"]) - _anual(mm["caro"])})
    return pd.DataFrame(filas)


def _por_sector(x: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for industria, g in x.groupby("industria"):
        for s in ("historia", "ddm"):
            c = correlacion(g, s)
            filas.append({"industria": industria, "senal": s, "meses": int(c.notna().sum()),
                          "correlacion": float(c.mean()) if len(c) else np.nan,
                          "emisores": int(g.loc[g["elegible"], "ticker"].nunique())})
    return pd.DataFrame(filas)


def estudiar(u: dict[str, pd.DataFrame] | None = None, ust10: pd.Series | None = None,
             diseno: Diseno = DISENO, *, con_sorteos: bool = True) -> ResultadoSeleccion:
    from src.estudio import macro
    from src.estudio import universo as uv

    u = uv.cargar() if u is None else u
    ust10 = macro.cargar("ust10") if ust10 is None else ust10
    x = panel(u, ust10, diseno)
    carteras_ = {(s, f): carteras(x, s, filtro=f, diseno=diseno) for s in SENALES for f in (False, True)}
    cor = {s: correlacion(x, s, diseno) for s in SENALES}
    tramp = {(s, f): trampas(x, s, filtro=f) for s in SENALES for f in (False, True)}
    filas = [{"cartera": "Todos los elegibles", "senal": None, "filtro": False, **aportacion(x, None, diseno=diseno)}]
    for s in SENALES:
        for f in (False, True):
            filas.append({"cartera": SENALES[s] + (", con dividendo intacto" if f else ""), "senal": s, "filtro": f,
                          **aportacion(x, s, filtro=f, diseno=diseno)})
    aport = pd.DataFrame(filas)
    aport["contra_todos"] = aport["tir"] - aport.loc[0, "tir"]
    lista = u["lista"].copy()
    meses_eleg = x[x["elegible"]].groupby("ticker").size()
    lista["meses_elegible"] = lista["ticker"].map(meses_eleg).fillna(0).astype(int)
    return ResultadoSeleccion(
        panel=x, carteras=carteras_, correlaciones=cor, resumen_correlacion=_resumen_correlacion(cor, diseno),
        trampas=tramp, aportaciones=aport,
        sorteos={s: sorteos(x, s, diseno) for s in SENALES} if con_sorteos else {},
        mitades=_mitades(x, cor, carteras_, diseno), por_sector=_por_sector(x),
        referencia=referencia(u, carteras_[("historia", False)].mensual["todos"]),
        universo=lista, hasta=x["fecha"].max(),
    )
