"""Cuánto rindió, de dónde salió, y cuándo convenía entrar.

Tres preguntas, tres herramientas
---------------------------------
1. **Retorno total**: el índice que sigue a quien compró una acción y reinvirtió
   cada dividendo el día que cotizó sin él. Incluye la escisión de Orion como
   distribución en especie reinvertida.
2. **Descomposición**: ``precio = dividendo ÷ yield``, así que todo el retorno se
   reparte, exacto y sin residuo inexplicado, en tres fuentes:

   ``(1 + RT) = (1 + ingreso) × (1 + crecimiento del dividendo) × (1 + revaluación)``

   El ingreso es lo cobrado y reinvertido; el crecimiento, cuánto subió el
   dividendo por acción; la revaluación, cuánto cambió lo que el mercado paga por
   cada dólar de dividendo. Las dos primeras las produce el negocio; la tercera,
   el humor del mercado. Distinguirlas es la diferencia entre «el REIT fue buena
   inversión» y «tuve suerte con la fecha».
3. **Retorno por fecha de entrada**: para cada fin de mes desde 1995, qué tan
   caro estaba —con lo que se sabía ESE día (P1)— y cuánto rindió después.

Lo que este módulo NO afirma
----------------------------
Que la valuación al entrar prediga el retorno. Con 30 años de historia hay unas
cinco ventanas de cinco años que no se enciman: la relación puede verse clarísima
y seguir siendo ruido. El módulo cuenta las apuestas efectivas y lo dice (P7).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import MIN_APUESTAS_EFECTIVAS, SERIE_USDMXN, SERIE_UST10
from src.estudio.fundamentales import en_fechas
from src.estudio.mercado import HistoriaMercado, dividendo_anualizado, dividendo_ttm

# --------------------------------------------------------------------------------------
# Serie diaria
# --------------------------------------------------------------------------------------


def _alinear_a_sesiones(fechas: pd.Series, sesiones: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Lleva cada fecha a la primera sesión igual o posterior (fecha ex en día inhábil)."""
    pos = sesiones.searchsorted(pd.DatetimeIndex(fechas), side="left")
    pos = np.clip(pos, 0, len(sesiones) - 1)
    return sesiones[pos]


def indice_retorno_total(historia: HistoriaMercado, *, fraccion_neta: float = 1.0) -> pd.Series:
    """Valor de una acción comprada el primer día, reinvirtiendo todo, base 1.

    ``fraccion_neta`` < 1 descuenta impuestos del dividendo antes de reinvertirlo
    (0.80 para un residente mexicano con W-8BEN, ver ``src.fiscal.mexico``).

    En la fecha de un evento de capital el precio crudo brinca —a la mitad en el
    split, 3.2% abajo en la escisión— y el accionista no perdió nada: tiene el
    doble de acciones, o acciones de Orion. Multiplicar por el factor del evento
    reconoce eso; en la escisión equivale a reinvertir el valor de Orion en O.
    """
    p = historia.precios["cierre_crudo"].astype(float)
    sesiones = p.index
    d = historia.dividendos.copy()
    d["sesion"] = _alinear_a_sesiones(d["fecha_ex"], sesiones)
    div = d.groupby("sesion")["monto_pagado"].sum().reindex(sesiones, fill_value=0.0) * fraccion_neta

    factor = pd.Series(1.0, index=sesiones)
    for e in historia.eventos:
        s = _alinear_a_sesiones(pd.Series([pd.Timestamp(e.fecha)]), sesiones)[0]
        factor.loc[s] *= e.factor

    r = (p * factor + div) / p.shift(1)
    r.iloc[0] = 1.0
    return r.cumprod().rename("retorno_total")


@dataclass
class SerieDiaria:
    tabla: pd.DataFrame       # índice sesión
    validacion_rt: float | None  # desviación máxima contra el ajustado del proveedor


def serie_diaria(
    historia: HistoriaMercado,
    *,
    ust10: pd.Series,
    usdmxn: pd.Series,
    ffo_conocido: pd.Series,
    affo_conocido: pd.Series,
    ajustado_proveedor: pd.Series | None = None,
    fraccion_neta: float = 0.80,
) -> SerieDiaria:
    """Todo lo que varía día con día, con lo que se sabía ese día."""
    sesiones = historia.precios.index
    t = pd.DataFrame(index=sesiones)
    t["precio"] = historia.precios["cierre_crudo"]
    t["precio_base"] = historia.precios["cierre_base"]
    t["rt_usd"] = indice_retorno_total(historia)
    t["rt_usd_neto"] = indice_retorno_total(historia, fraccion_neta=fraccion_neta)
    fx = pd.Series(usdmxn).sort_index()
    fx.index = pd.to_datetime(fx.index)
    t["usdmxn"] = en_fechas(fx, sesiones)
    t["rt_mxn"] = t["rt_usd"] * t["usdmxn"]
    t["rt_mxn_neto"] = t["rt_usd_neto"] * t["usdmxn"]

    t["dividendo_ttm"] = dividendo_ttm(historia.dividendos, sesiones).values
    t["dividendo_anualizado"] = dividendo_anualizado(historia.dividendos, sesiones).values
    t["yield_ttm"] = t["dividendo_ttm"] / t["precio_base"]
    tasa = pd.Series(ust10).sort_index()
    tasa.index = pd.to_datetime(tasa.index)
    t["ust10"] = en_fechas(tasa, sesiones)
    t["spread"] = t["yield_ttm"] - t["ust10"]
    t["ffo_ttm"] = en_fechas(ffo_conocido, sesiones)
    t["affo_ttm"] = en_fechas(affo_conocido, sesiones)
    t["p_ffo"] = t["precio_base"] / t["ffo_ttm"]
    t["p_affo"] = t["precio_base"] / t["affo_ttm"]
    t["affo_yield"] = 1 / t["p_affo"]

    validacion = None
    if ajustado_proveedor is not None:
        a = pd.Series(ajustado_proveedor).reindex(sesiones).dropna()
        if len(a) > 250:
            cociente = (t["rt_usd"].reindex(a.index) / a)
            cociente = cociente / cociente.iloc[0]
            validacion = float((cociente - 1).abs().max())
    return SerieDiaria(t, validacion)


# --------------------------------------------------------------------------------------
# Descomposición
# --------------------------------------------------------------------------------------


@dataclass
class Descomposicion:
    nombre: str
    inicio: pd.Timestamp
    fin: pd.Timestamp
    anios: float
    retorno_total: float          # anualizado
    ingreso: float                # anualizado
    crecimiento_dividendo: float  # anualizado
    revaluacion: float            # anualizado
    escision: float               # anualizado
    yield_inicio: float
    yield_fin: float
    crecimiento_ffo: float | None = None
    revaluacion_ffo: float | None = None
    p_ffo_inicio: float | None = None
    p_ffo_fin: float | None = None

    @property
    def identidad(self) -> float:
        """Debe ser cero: los factores reconstruyen el retorno total."""
        prod = ((1 + self.ingreso) * (1 + self.crecimiento_dividendo)
                * (1 + self.revaluacion) * (1 + self.escision))
        return prod - (1 + self.retorno_total)


def _sesion_en(t: pd.DataFrame, fecha) -> pd.Timestamp:
    idx = t.index.searchsorted(pd.Timestamp(fecha), side="right") - 1
    return t.index[max(idx, 0)]


def descomponer(
    serie: SerieDiaria, historia: HistoriaMercado, inicio, fin, nombre: str = ""
) -> Descomposicion:
    t = serie.tabla
    a, b = _sesion_en(t, inicio), _sesion_en(t, fin)
    # Al listado todavía no hay dividendo con fecha ex: O cotizó el 18 de octubre
    # de 1994 y su primera fecha ex fue el 26. Se arranca en la primera sesión con
    # dividendo conocido, ocho días después; no mover el inicio dejaba la era
    # entera sin descomponer.
    if pd.isna(t.loc[a, "dividendo_anualizado"]):
        conocidos = t.index[(t.index >= a) & t["dividendo_anualizado"].notna()]
        if len(conocidos):
            a = conocidos[0]
    n = (b - a).days / 365.25
    ra, rb = t.loc[a], t.loc[b]

    def anual(x: float) -> float:
        return float(x ** (1 / n) - 1) if n > 0 and x > 0 else float("nan")

    # El dividendo ANUALIZADO (mensualidad vigente × 12) en los dos extremos, no el
    # TTM: al IPO todavía no hay doce pagos, y un TTM rezaga los aumentos un año.
    # Lo que importa es que los dos extremos se midan igual.
    ya = ra["dividendo_anualizado"] / ra["precio_base"]
    yb = rb["dividendo_anualizado"] / rb["precio_base"]
    rt = rb["rt_usd"] / ra["rt_usd"]
    crec = rb["dividendo_anualizado"] / ra["dividendo_anualizado"]
    reval = ya / yb
    esc = float(np.prod([e.factor for e in historia.escisiones
                         if a < pd.Timestamp(e.fecha) <= b])) if historia.escisiones else 1.0
    # El precio BASE cae en la escisión (el valor se fue a Orion); el retorno total
    # no. Por eso la escisión es un factor aparte y no se confunde con revaluación.
    ingreso = rt / (crec * reval * esc)
    d = Descomposicion(
        nombre=nombre, inicio=a, fin=b, anios=n,
        retorno_total=anual(rt), ingreso=anual(ingreso),
        crecimiento_dividendo=anual(crec), revaluacion=anual(reval), escision=anual(esc),
        yield_inicio=float(ya), yield_fin=float(yb),
    )
    if pd.notna(ra["p_ffo"]) and pd.notna(rb["p_ffo"]):
        d.crecimiento_ffo = anual(rb["ffo_ttm"] / ra["ffo_ttm"])
        d.revaluacion_ffo = anual(rb["p_ffo"] / ra["p_ffo"])
        d.p_ffo_inicio, d.p_ffo_fin = float(ra["p_ffo"]), float(rb["p_ffo"])
    return d


# --------------------------------------------------------------------------------------
# Retorno por fecha de entrada
# --------------------------------------------------------------------------------------


@dataclass
class AnalisisEntradas:
    tabla: pd.DataFrame                  # una fila por fin de mes
    quintiles: pd.DataFrame              # retorno a 5 años por quintil del P/FFO al entrar
    quintiles_spread: pd.DataFrame       # lo mismo, por spread contra el Treasury
    correlaciones: dict[str, float]      # Spearman spread → retorno futuro
    apuestas_efectivas: dict[str, int]   # por horizonte
    mejores: pd.DataFrame
    peores: pd.DataFrame
    veredicto_p7: str = ""
    notas: list[str] = field(default_factory=list)


def _anualizado(cociente: pd.Series, anios: pd.Series) -> pd.Series:
    return cociente.where(cociente > 0) ** (1 / anios) - 1


def _extremos_separados(t: pd.DataFrame, columna: str, n: int, *, mayores: bool, meses: int = 18) -> pd.DataFrame:
    """Los n extremos, separados al menos ``meses`` entre sí.

    Sin la separación, los cinco mejores meses son cinco meses seguidos de marzo de
    2009: un solo episodio contado cinco veces.
    """
    orden = t[columna].dropna().sort_values(ascending=not mayores)
    elegidos: list[pd.Timestamp] = []
    for fecha in orden.index:
        if all(abs((fecha - e).days) > meses * 30 for e in elegidos):
            elegidos.append(fecha)
        if len(elegidos) == n:
            break
    return t.loc[elegidos]


def _quintiles(e: pd.DataFrame, columna: str, *, barato_es_alto: bool) -> pd.DataFrame:
    """Retorno a cinco años según qué tan cara estaba la acción al entrar."""
    sub = e[[columna, "rt_5a"]].dropna() if "rt_5a" in e else pd.DataFrame()
    if len(sub) < 25:
        return pd.DataFrame()
    etiquetas = ["1 · más caro", "2", "3", "4", "5 · más barato"]
    if not barato_es_alto:
        etiquetas = etiquetas[::-1]
    sub = sub.assign(quintil=pd.qcut(sub[columna], 5, labels=etiquetas))
    q = sub.groupby("quintil", observed=True).agg(
        desde=(columna, "min"), hasta=(columna, "max"),
        rt_5a_mediana=("rt_5a", "median"), rt_5a_peor=("rt_5a", "min"),
        rt_5a_mejor=("rt_5a", "max"), meses=("rt_5a", "size"),
    )
    return q.reindex(["1 · más caro", "2", "3", "4", "5 · más barato"])


def analizar_entradas(serie: SerieDiaria, *, asof: dt.date, horizontes=(5, 10)) -> AnalisisEntradas:
    t = serie.tabla
    fin_de_mes = t.groupby([t.index.year, t.index.month]).tail(1).index
    e = t.loc[fin_de_mes, ["precio", "precio_base", "yield_ttm", "ust10", "spread", "p_ffo",
                           "p_affo", "rt_usd", "rt_mxn", "rt_usd_neto", "dividendo_ttm"]].copy()
    e = e[e["yield_ttm"].notna()]
    hoy = t.iloc[-1]
    anios_a_hoy = (t.index[-1] - e.index).days / 365.25
    e["rt_a_hoy_usd"] = _anualizado(hoy["rt_usd"] / e["rt_usd"], anios_a_hoy)
    e["rt_a_hoy_mxn"] = _anualizado(hoy["rt_mxn"] / e["rt_mxn"], anios_a_hoy)
    e["rt_a_hoy_neto_usd"] = _anualizado(hoy["rt_usd_neto"] / e["rt_usd_neto"], anios_a_hoy)
    e["multiplo_a_hoy"] = hoy["rt_usd"] / e["rt_usd"]
    e["yield_sobre_costo"] = hoy["dividendo_anualizado"] / e["precio_base"]
    e["anios_a_hoy"] = anios_a_hoy

    for h in horizontes:
        destino = [_sesion_en(t, f + pd.DateOffset(years=h)) for f in e.index]
        vale = [(f + pd.DateOffset(years=h)) <= t.index[-1] for f in e.index]
        futuro = t.loc[destino, "rt_usd"].to_numpy()
        e[f"rt_{h}a"] = np.where(vale, (futuro / e["rt_usd"].to_numpy()) ** (1 / h) - 1, np.nan)

    corr = {}
    for h in horizontes:
        sub = e[["spread", f"rt_{h}a"]].dropna()
        if len(sub) > 10:
            corr[f"{h} años"] = float(sub["spread"].rank().corr(sub[f"rt_{h}a"].rank()))
        sub = e[["p_ffo", f"rt_{h}a"]].dropna()
        if len(sub) > 10:
            corr[f"{h} años (P/FFO)"] = float(sub["p_ffo"].rank().corr(sub[f"rt_{h}a"].rank()))

    # Apuestas efectivas (P7): ventanas que no se enciman dentro del periodo con
    # retorno futuro observado. Meses consecutivos comparten casi todo su futuro;
    # contarlos como observaciones independientes es inventarse la muestra.
    efectivas = {}
    for h in horizontes:
        con = e[f"rt_{h}a"].dropna()
        if con.empty:
            efectivas[f"{h} años"] = 0
            continue
        extension = (con.index[-1] - con.index[0]).days / 365.25 + h
        efectivas[f"{h} años"] = int(extension // h)

    for h in horizontes:
        sub = e[["yield_ttm", f"rt_{h}a"]].dropna()
        if len(sub) > 10:
            corr[f"{h} años (yield)"] = float(sub["yield_ttm"].rank().corr(sub[f"rt_{h}a"].rank()))

    q = _quintiles(e, "p_ffo", barato_es_alto=False)
    q_spread = _quintiles(e, "spread", barato_es_alto=True)

    ef5 = efectivas.get("5 años", 0)
    veredicto = (
        f"INCONCLUSO como regla de compra. La relación entre la valuación al entrar y el "
        f"retorno a cinco años se apoya en {ef5} ventanas que no se enciman; el mínimo del "
        f"modelo para afirmar una regla es {MIN_APUESTAS_EFECTIVAS}. Sirve para entender la "
        "historia, no para decidir con ella."
    )
    return AnalisisEntradas(
        tabla=e, quintiles=q, quintiles_spread=q_spread, correlaciones=corr,
        apuestas_efectivas=efectivas,
        mejores=_extremos_separados(e, "rt_5a", 5, mayores=True) if "rt_5a" in e else pd.DataFrame(),
        peores=_extremos_separados(e, "rt_5a", 5, mayores=False) if "rt_5a" in e else pd.DataFrame(),
        veredicto_p7=veredicto,
    )


# --------------------------------------------------------------------------------------
# Lo que paga hoy
# --------------------------------------------------------------------------------------


@dataclass
class Escenario:
    nombre: str
    crecimiento: float        # nominal en dólares, por acción
    origen: str
    retorno_usd: float        # yield + crecimiento, múltiplo constante
    retorno_con_reversion: float           # si el SPREAD contra el bono vuelve a su mediana
    real_neto: float          # después de impuestos, en términos reales
    retorno_reversion_multiplo: float = float("nan")  # si el P/FFO vuelve a su mediana
    real_neto_reversion_spread: float = float("nan")
    real_neto_reversion_multiplo: float = float("nan")


@dataclass
class RetornoHoy:
    fecha: pd.Timestamp
    precio: float
    dividendo_anualizado: float
    yield_actual: float
    yield_ttm: float
    ust10: float | None
    spread: float | None
    percentil_spread: float | None   # contra toda la historia hasta hoy
    spread_mediano: float | None
    p_ffo: float | None
    p_affo: float | None
    affo_yield: float | None
    payout_affo: float | None
    escenarios: list[Escenario]
    inflacion_us: float | None
    udibono_real: float | None
    cetes: float | None
    tasa_impuesto_dividendo: float
    supuestos: list[str]


def cagr(serie: pd.Series, anios: int) -> float | None:
    s = serie.dropna()
    if len(s) < 2:
        return None
    ultimo = s.index.max()
    inicio = ultimo - anios
    if inicio not in s.index or s.loc[inicio] <= 0:
        return None
    return float((s.loc[ultimo] / s.loc[inicio]) ** (1 / anios) - 1)


def retorno_hoy(
    serie: SerieDiaria,
    anual: pd.DataFrame,
    *,
    inflacion_us: float | None,
    udibono_real: float | None,
    cetes: float | None,
    tasa_impuesto_dividendo: float,
    anios_reversion: int = 5,
) -> RetornoHoy:
    t = serie.tabla
    hoy = t.iloc[-1]
    y = float(hoy["dividendo_anualizado"] / hoy["precio_base"])
    spread_hist = t["spread"].dropna()
    spread_hoy = float(hoy["spread"]) if pd.notna(hoy["spread"]) else None
    pct = float((spread_hist <= spread_hoy).mean()) if spread_hoy is not None else None
    mediana = float(spread_hist.median()) if not spread_hist.empty else None

    # Las dos lentes de valuación discrepan hoy, así que se modelan las dos
    # reversiones y no solo la que conviene. Contra el bono: el spread vuelve a su
    # mediana con la tasa de hoy. Contra su propia historia: el P/FFO vuelve a la
    # suya. Mostrar solo una sería escoger la conclusión antes de ver el dato.
    reversion = 0.0
    if mediana is not None and pd.notna(hoy["ust10"]):
        y_objetivo = float(hoy["ust10"]) + mediana
        if y_objetivo > 0:
            reversion = (y / y_objetivo) ** (1 / anios_reversion) - 1
    reversion_multiplo = 0.0
    pffo_mediana = float(t["p_ffo"].median()) if t["p_ffo"].notna().any() else None
    if pffo_mediana and pd.notna(hoy["p_ffo"]) and hoy["p_ffo"] > 0:
        reversion_multiplo = (pffo_mediana / float(hoy["p_ffo"])) ** (1 / anios_reversion) - 1

    fuentes_g = [
        ("AFFO por acción, 5 años", cagr(anual.get("affo_por_accion", pd.Series(dtype=float)), 5)),
        ("AFFO por acción, 10 años", cagr(anual.get("affo_por_accion", pd.Series(dtype=float)), 10)),
        ("Dividendo por acción, 10 años", cagr(anual["dividendo_por_accion"], 10)),
        ("Dividendo por acción, 20 años", cagr(anual["dividendo_por_accion"], 20)),
        ("FFO por acción, 20 años", cagr(anual.get("ffo_por_accion", pd.Series(dtype=float)), 20)),
    ]
    pi = inflacion_us if inflacion_us is not None else 0.025
    escenarios = []
    for nombre, g in fuentes_g:
        if g is None:
            continue
        r = y + g
        neto = y * (1 - tasa_impuesto_dividendo) + g

        def real(nominal_neto: float) -> float:
            return (1 + nominal_neto) / (1 + pi) - 1

        escenarios.append(Escenario(
            nombre=nombre, crecimiento=g, origen=nombre,
            retorno_usd=r, retorno_con_reversion=(1 + r) * (1 + reversion) - 1,
            real_neto=real(neto),
            retorno_reversion_multiplo=(1 + r) * (1 + reversion_multiplo) - 1,
            real_neto_reversion_spread=real((1 + neto) * (1 + reversion) - 1),
            real_neto_reversion_multiplo=real((1 + neto) * (1 + reversion_multiplo) - 1),
        ))

    affo = hoy.get("affo_ttm")
    return RetornoHoy(
        fecha=t.index[-1], precio=float(hoy["precio"]),
        dividendo_anualizado=float(hoy["dividendo_anualizado"]),
        yield_actual=y, yield_ttm=float(hoy["yield_ttm"]),
        ust10=float(hoy["ust10"]) if pd.notna(hoy["ust10"]) else None,
        spread=spread_hoy, percentil_spread=pct, spread_mediano=mediana,
        p_ffo=float(hoy["p_ffo"]) if pd.notna(hoy["p_ffo"]) else None,
        p_affo=float(hoy["p_affo"]) if pd.notna(hoy["p_affo"]) else None,
        affo_yield=float(hoy["affo_yield"]) if pd.notna(hoy["affo_yield"]) else None,
        payout_affo=float(hoy["dividendo_anualizado"] / affo) if affo and pd.notna(affo) else None,
        escenarios=escenarios, inflacion_us=inflacion_us, udibono_real=udibono_real, cetes=cetes,
        tasa_impuesto_dividendo=tasa_impuesto_dividendo,
        supuestos=[
            "Retorno esperado = yield de hoy + crecimiento del flujo por acción: supone que el "
            "múltiplo no cambia. La columna «con reversión» agrega el efecto de que el spread "
            f"contra el bono vuelva a su mediana histórica en {anios_reversion} años.",
            "El crecimiento es NOMINAL en dólares y se deflacta con la inflación de EE. UU. "
            "Bajo paridad relativa, el retorno real en pesos se parece al real en dólares, que "
            "es lo que hace comparable el número con el Udibono.",
            f"Impuesto al dividendo de {tasa_impuesto_dividendo:.0%} (retención de EE. UU. con "
            "W-8BEN más ISR adicional en México, sin acreditamiento). La ganancia de capital no "
            "se grava hasta vender y aquí no se descuenta.",
        ],
    )


__all__ = [
    "SERIE_UST10", "SERIE_USDMXN", "indice_retorno_total", "serie_diaria", "descomponer",
    "analizar_entradas", "retorno_hoy", "cagr",
]
