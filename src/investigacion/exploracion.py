"""Fase 3: exploración, solo con la muestra de desarrollo (EE. UU. hasta diciembre de 2015).

Antes de buscar señales hay que saber tres cosas:

1. **De dónde salió el retorno del sector**: ingreso contra precio, contra el efectivo, la
   inflación y la bolsa.
2. **La anatomía de cada caída grande**: cuánto cayó, cuánto duró y qué decía cada
   indicador en el máximo anterior, con lo que se sabía ese día (P1).
3. **El techo teórico**: qué tan seguido el efectivo le ganó a los REITs y cuánto valdría
   saberlo de antemano. Un oráculo que conoce el futuro marca el máximo que cualquier
   regla de entrada podría agregar; si ese máximo es chico, no vale la pena buscar.

Todo se recorta a la muestra de desarrollo ANTES de calcular (``muestras.recortar``), así
que ningún retorno «siguiente» mira 2016.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.investigacion import datos, muestras
from src.investigacion.muestras import Muestra
from src.investigacion.simulacion import Mercado, Modo, benchmark, simular
from src.modelo.senal import percentil_expandible

INDICE = "all_equity"
CORTE_DE_ERAS = pd.Timestamp("1992-12-31")   # la era moderna de los REITs empieza con las OPIs de 1993


# --------------------------------------------------------------------------------------
# Insumos
# --------------------------------------------------------------------------------------


def _fin_de_mes(x: pd.Series) -> pd.Series:
    return x.groupby(x.index + pd.offsets.MonthEnd(0)).last()


def sector(muestra: Muestra | str = Muestra.DESARROLLO, *, motivo: str = "") -> pd.DataFrame:
    """El índice de REITs de capital y el efectivo, mes por mes."""
    n = datos.cargar_sector()["nareit"]
    n = muestras.recortar(n[n["indice"] == INDICE], muestra, columna="fecha", motivo=motivo)
    x = n.set_index("fecha")[["retorno_total", "retorno_precio", "retorno_ingreso", "indice_total", "indice_precio",
                              "yield_dividendo"]].sort_index()
    macro = datos.cargar_macro()
    tb = macro[macro["serie"] == "TB3MS"].set_index("fecha")["valor"]
    tb.index = tb.index + pd.offsets.MonthEnd(0)
    # El T-bill que se gana en el mes t es la tasa del mes anterior, a un mes.
    x["efectivo"] = (tb.shift(1).reindex(x.index) / 100) / 12
    return x.iloc[1:]   # diciembre de 1971 es la base del índice, sin retorno


def mercado(x: pd.DataFrame) -> Mercado:
    return Mercado(x.index, x["retorno_precio"].to_numpy(), x["retorno_ingreso"].to_numpy(), x["efectivo"].to_numpy())


def indicadores(x: pd.DataFrame) -> pd.DataFrame:
    """Los indicadores candidatos al cierre de cada mes, con lo que ya se conocía (P1).

    No son todavía señales: son lo que la literatura y el sentido común sugieren mirar.
    Cuáles se prueban, y cómo, se fija en la fase 4.
    """
    f = x.index
    macro = muestras.recortar(datos.cargar_macro(), columna="fecha") if f.max() <= pd.Timestamp("2015-12-31") \
        else datos.cargar_macro()
    c = lambda s: datos.conocida_en(macro, s, f)  # noqa: E731
    cpi = c("CPIAUCSL")
    # Inflación de 12 meses con lo publicado: el CPI conocido hoy contra el conocido hace un año.
    inflacion = cpi / cpi.shift(12) - 1
    y = x["yield_dividendo"]
    tendencia = x["indice_precio"] / x["indice_precio"].rolling(10).mean() - 1
    d = pd.DataFrame(index=f)
    d["yield_reit"] = y
    d["percentil_yield"] = percentil_expandible(y.dropna(), min_observaciones=36).reindex(f)
    d["treasury_10a"] = c("DGS10") / 100
    d["spread_10a"] = y - d["treasury_10a"]
    d["baa"] = c("BAA") / 100
    d["spread_baa"] = y - d["baa"]
    d["inflacion_12m"] = inflacion
    d["tasa_real"] = d["treasury_10a"] - inflacion
    d["spread_credito"] = d["baa"] - c("GS10") / 100
    d["curva"] = (c("GS10") - c("GS1")) / 100
    d["fed_cambio_12m"] = (c("FEDFUNDS") - c("FEDFUNDS").shift(12)) / 100
    d["desempleo_cambio_12m"] = (c("UNRATE") - c("UNRATE").shift(12)) / 100
    d["nfci"] = c("NFCI")
    # La encuesta de crédito de la Fed: la serie agregada termina en 2013 y se parte en tres
    # (construcción, no residencial y multifamiliar); desde entonces, su promedio.
    sucesoras = pd.concat([c(s) for s in ("SUBLPDRCSC", "SUBLPDRCSN", "SUBLPDRCSM")], axis=1).mean(axis=1)
    agregada = c("DRTSCREL")
    ultima = macro.loc[macro["serie"] == "DRTSCREL", "fecha"].max()
    d["credito_inmuebles"] = (agregada.where(f <= ultima + pd.offsets.QuarterEnd(0) + pd.Timedelta(days=40))
                              .fillna(sucesoras.where(f > ultima + pd.offsets.QuarterEnd(0)))) / 100
    d["tendencia_10m"] = tendencia
    d["momentum_12m"] = (1 + x["retorno_total"]).rolling(12).apply(np.prod, raw=True) - 1
    d["caida_desde_maximo"] = x["indice_total"] / x["indice_total"].cummax() - 1
    d["cambio_treasury_12m"] = d["treasury_10a"] - d["treasury_10a"].shift(12)
    d["spread_default"] = (c("BAA") - c("AAA")) / 100
    efectivo_12m = (1 + x["efectivo"]).rolling(12).apply(np.prod, raw=True) - 1
    d["momentum_exceso_12m"] = d["momentum_12m"] - efectivo_12m
    fr = datos.cargar_factores()
    if fr:
        b = fr["french"].pivot(index="fecha", columns="factor", values="valor")
        d["bolsa_mes"] = (b["Mkt-RF"] + b["RF"]).reindex(f)
    d["cambio_credito_12m"] = d["spread_credito"] - d["spread_credito"].shift(12)
    d["spread_real"] = y - d["tasa_real"]
    return d


# --------------------------------------------------------------------------------------
# 1. De dónde salió el retorno
# --------------------------------------------------------------------------------------


def _anual(r: pd.Series) -> float:
    r = r.dropna()
    return float((1 + r).prod() ** (12 / len(r)) - 1) if len(r) else np.nan


def descomposicion(x: pd.DataFrame) -> pd.DataFrame:
    """Retorno anual de los REITs, su ingreso y su precio, contra efectivo, inflación y bolsa, por era."""
    fr = datos.cargar_factores()["french"]
    bolsa = fr.pivot(index="fecha", columns="factor", values="valor")
    bolsa = (bolsa["Mkt-RF"] + bolsa["RF"]).reindex(x.index)
    macro = datos.cargar_macro()
    cpi = macro[macro["serie"] == "CPIAUCSL"].set_index("fecha")["valor"]
    cpi.index = cpi.index + pd.offsets.MonthEnd(0)
    inflacion = cpi.pct_change().reindex(x.index)
    eras = {"completo": (x.index.min(), x.index.max()), "1972-1992": (x.index.min(), CORTE_DE_ERAS),
            "1993-2015": (CORTE_DE_ERAS + pd.offsets.MonthEnd(1), x.index.max())}
    filas = []
    for nombre, (a, b) in eras.items():
        s = slice(a, b)
        r = x.loc[s]
        filas.append({"periodo": nombre, "desde": a, "hasta": b,
                      "rendimiento_reits": _anual(r["retorno_total"]), "rendimiento_precio": _anual(r["retorno_precio"]),
                      "rendimiento_ingreso": float(r["retorno_ingreso"].mean() * 12),
                      "rendimiento_efectivo": _anual(r["efectivo"]), "inflacion": _anual(inflacion.loc[s]),
                      "rendimiento_bolsa": _anual(bolsa.loc[s]),
                      "volatilidad_reits": float(r["retorno_total"].std() * np.sqrt(12)),
                      "volatilidad_bolsa": float(bolsa.loc[s].std() * np.sqrt(12)),
                      "correlacion_con_bolsa": float(r["retorno_total"].corr(bolsa.loc[s]))})
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# 2. Las caídas grandes
# --------------------------------------------------------------------------------------


def caidas(x: pd.DataFrame, umbral: float = -0.20) -> pd.DataFrame:
    """Cada caída del retorno total de al menos ``umbral`` desde su máximo previo."""
    v = x["indice_total"]
    maximo = v.cummax()
    dd = v / maximo - 1
    filas, en_caida, pico = [], False, None
    for fecha, valor in dd.items():
        if not en_caida and valor < 0:
            en_caida, pico = True, maximo.loc[:fecha].idxmax()
        if en_caida and valor == 0:
            tramo = dd.loc[pico:fecha]
            if tramo.min() <= umbral:
                filas.append({"maximo": pico, "minimo": tramo.idxmin(), "recuperado": fecha, "caida": float(tramo.min())})
            en_caida = False
    if en_caida:
        tramo = dd.loc[pico:]
        if tramo.min() <= umbral:
            filas.append({"maximo": pico, "minimo": tramo.idxmin(), "recuperado": pd.NaT, "caida": float(tramo.min())})
    d = pd.DataFrame(filas)
    if d.empty:
        return d
    meses = lambda a, b: (b.year - a.year) * 12 + b.month - a.month  # noqa: E731
    d["meses_de_caida"] = [meses(a, b) for a, b in zip(d["maximo"], d["minimo"], strict=True)]
    d["meses_para_recuperar"] = [meses(b, c) if pd.notna(c) else np.nan for b, c in
                                 zip(d["minimo"], d["recuperado"], strict=True)]
    return d


def anatomia(x: pd.DataFrame, ind: pd.DataFrame, cd: pd.DataFrame, meses_antes: int = 0) -> pd.DataFrame:
    """Qué decía cada indicador en el máximo (o ``meses_antes``) de cada caída, y su percentil
    contra la historia hasta ese día."""
    filas = []
    for _, c in cd.iterrows():
        fecha = c["maximo"] - pd.offsets.MonthEnd(meses_antes) if meses_antes else c["maximo"]
        fila = {"maximo": c["maximo"], "caida": c["caida"], "fecha_de_lectura": fecha}
        for col in ind.columns:
            historia = ind[col].loc[:fecha].dropna()
            if historia.empty:
                continue
            v = historia.iloc[-1]
            fila[col] = v
            fila[f"{col}_percentil"] = float((historia < v).mean()) if len(historia) >= 36 else np.nan
        filas.append(fila)
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# 3. El techo teórico
# --------------------------------------------------------------------------------------


def _adelante(r: pd.Series, h: int) -> pd.Series:
    """Retorno compuesto de los ``h`` meses siguientes (t+1 … t+h). Vacío donde no alcanza."""
    acumulado = (1 + r.fillna(0)).cumprod()
    return acumulado.shift(-h) / acumulado - 1


def frecuencia_efectivo_gana(x: pd.DataFrame, horizontes=(1, 3, 12, 36, 60)) -> pd.DataFrame:
    filas = []
    for h in horizontes:
        reit, cash = _adelante(x["retorno_total"], h), _adelante(x["efectivo"], h)
        ok = reit.notna() & cash.notna() & (np.arange(len(x)) < len(x) - h)
        filas.append({"horizonte_meses": h, "ventanas": int(ok.sum()), "independientes": int(ok.sum() // h),
                      "fraccion_efectivo_gana": float((cash[ok] > reit[ok]).mean()),
                      "rendimiento_reits_mediana": float(((1 + reit[ok]) ** (12 / h) - 1).median()),
                      "rendimiento_efectivo_mediana": float(((1 + cash[ok]) ** (12 / h) - 1).median())})
    return pd.DataFrame(filas)


@dataclass
class Techo:
    tabla: pd.DataFrame
    resultados: dict


def techo(x: pd.DataFrame) -> Techo:
    """Oráculos que conocen el futuro, contra aportar siempre. Marcan el máximo alcanzable."""
    m = mercado(x)
    n = len(x)
    reit, cash = x["retorno_total"].to_numpy(), x["efectivo"].to_numpy()
    siguiente = np.r_[(reit[1:] > cash[1:]).astype(float), 1.0]
    r12, c12 = _adelante(x["retorno_total"], 12).to_numpy(), _adelante(x["efectivo"], 12).to_numpy()
    doce = np.where(np.isnan(r12) | np.isnan(c12), 1.0, (r12 > c12).astype(float))
    fuera = np.ones(n)
    for _, c in caidas(x).iterrows():
        fin = c["minimo"]
        fuera[(x.index >= c["maximo"]) & (x.index < fin)] = 0.0
    reglas = {"aportar siempre": None,
              "oráculo del mes siguiente": siguiente,
              "oráculo de los 12 meses siguientes": doce,
              "fuera en cada caída de 20% o más (del máximo al mínimo)": fuera,
              "anti-oráculo de 12 meses": 1 - doce}
    filas, resultados = [], {}
    base = benchmark(m)
    for nombre, e in reglas.items():
        for modo in (Modo.APORTACION, Modo.EXPOSICION):
            if e is None and modo is Modo.EXPOSICION:
                continue
            r = base if e is None else simular(m, e, modo=modo)
            resultados[(nombre, modo)] = r
            filas.append({"regla": nombre, "modo": "nunca vende" if modo is Modo.APORTACION else "rebalancea",
                          "tir": r.tir, "contra_aportar_siempre_bps": round((r.tir - base.tir) * 1e4),
                          "caida_maxima": r.caida_maxima, "exposicion_promedio": r.exposicion_promedio,
                          "cambios": r.cambios})
    return Techo(pd.DataFrame(filas), resultados)


# --------------------------------------------------------------------------------------
# El informe de la fase 3
# --------------------------------------------------------------------------------------

CONDICIONES = {
    "yield del REIT abajo del Treasury a 10 años": lambda i: i["spread_10a"] < 0,
    "yield en el 10% más bajo de su propia historia": lambda i: i["percentil_yield"] < 0.10,
    "precio abajo de su promedio de 10 meses": lambda i: i["tendencia_10m"] < 0,
    "retorno de los últimos 12 meses negativo": lambda i: i["momentum_12m"] < 0,
}


def _p(v, d=1) -> str:
    return "—" if pd.isna(v) else f"{v * 100:.{d}f}%"


def _tabla(filas: list[list[str]], encabezado: list[str]) -> str:
    linea = "| " + " | ".join(encabezado) + " |\n|" + "|".join("---" for _ in encabezado) + "|\n"
    return linea + "".join("| " + " | ".join(f) + " |\n" for f in filas)


def informe(x: pd.DataFrame | None = None, *, registrar: bool = True) -> str:
    """El informe de la fase 3, en Markdown. Anota en la bitácora lo que se exploró."""
    from src.investigacion import bitacora

    x = sector() if x is None else x
    ind = indicadores(x)
    dsc = descomposicion(x)
    cd = caidas(x)
    fr = frecuencia_efectivo_gana(x)
    te = techo(x)
    an0, an6 = anatomia(x, ind, cd, 0), anatomia(x, ind, cd, 6)
    if registrar:
        for col in ind.columns:
            bitacora.registrar(fase="3", familia="exploracion", prueba=f"anatomia de caidas: {col}",
                               muestra="desarrollo", parametros={"meses_antes": [0, 6]})
        for nombre in CONDICIONES:
            bitacora.registrar(fase="3", familia="exploracion", prueba=f"frecuencia: {nombre}", muestra="desarrollo")
        for _, f in te.tabla.iterrows():
            bitacora.registrar(fase="3", familia="exploracion-oraculo", prueba=f"{f['regla']} ({f['modo']})",
                               muestra="desarrollo", metrica="tir", valor=round(float(f["tir"]), 6))

    o = [f"# Fase 3: exploración de la muestra de desarrollo\n\nFTSE Nareit All Equity REITs, "
         f"{x.index.min():%m-%Y} a {x.index.max():%m-%Y} ({len(x)} meses), contra el T-bill a 3 meses. "
         "Nada de esto mira 2016 en adelante. Generado por `python scripts/investigacion.py exploracion`.\n"]
    o.append("## 1. De dónde salió el retorno\n")
    o.append(_tabla([[f["periodo"], _p(f["rendimiento_reits"]), _p(f["rendimiento_ingreso"]),
                      _p(f["rendimiento_precio"]), _p(f["rendimiento_efectivo"]), _p(f["inflacion"]),
                      _p(f["rendimiento_bolsa"]), _p(f["volatilidad_reits"]), f"{f['correlacion_con_bolsa']:.2f}"]
                     for _, f in dsc.iterrows()],
                    ["Periodo", "REITs", "del ingreso", "del precio", "Efectivo", "Inflación", "Bolsa (EE. UU.)",
                     "Volatilidad REITs", "Correlación con bolsa"]))
    era1 = dsc.set_index("periodo").loc["1972-1992"]
    o.append("\nEl ingreso (el dividendo) explica más de la mitad del retorno; el precio, el resto. "
             f"El T-bill de 1972-1992 rindió {_p(era1['rendimiento_efectivo'])} al año: en esa era el efectivo sí "
             "era una alternativa seria.\n")
    o.append("## 2. Las caídas de 20% o más\n")
    o.append(_tabla([[f"{c['maximo']:%m-%Y}", f"{c['minimo']:%m-%Y}", _p(c["caida"], 0), str(int(c["meses_de_caida"])),
                      "—" if pd.isna(c["meses_para_recuperar"]) else str(int(c["meses_para_recuperar"]))]
                     for _, c in cd.iterrows()],
                    ["Máximo", "Mínimo", "Caída", "Meses cayendo", "Meses para recuperar"]))
    o.append(f"\n{len(cd)} caídas en {len(x) // 12} años. **Cualquier regla para esquivarlas se apoya en muy "
             "pocos eventos**: con tres o cuatro casos es fácil encontrar algo que «los hubiera visto venir» "
             "por casualidad. Por eso la prueba final usa mercados que no se han visto.\n")
    o.append("### Qué decía cada indicador en el máximo y seis meses antes\n\nPercentil contra su propia "
             "historia hasta ese día (0% = el valor más bajo visto hasta entonces). La caída de 1972 no tiene "
             "historia previa suficiente.\n")
    nombres = {"percentil_yield": None, "caida_desde_maximo": None}
    cols = [c for c in ind.columns if c not in nombres]
    enc = ["Indicador"] + [f"{m:%m-%Y} ({k})" for m in cd["maximo"].iloc[1:] for k in ("máximo", "6 meses antes")]
    filas = []
    for col in cols:
        fila = [col.replace("_", " ")]
        for m in cd["maximo"].iloc[1:]:
            for a in (an0, an6):
                v = a.loc[a["maximo"] == m, f"{col}_percentil"]
                fila.append(_p(v.iloc[0], 0) if len(v) else "—")
        filas.append(fila)
    o.append(_tabla(filas, enc))
    o.append("\nLo que se ve: en 1997 y 2007 el yield de los REITs estaba en el mínimo de su historia (caros) y "
             "la tendencia y el momentum, arriba (por definición, cerca de un máximo). En 1989 no había ninguna "
             "alarma de valuación. Tres casos no alcanzan para concluir nada.\n")
    o.append("### Qué tan seguido sonaría cada alarma\n")
    filas = []
    base = ind[ind.index >= "1975-01-31"]
    for nombre, f in CONDICIONES.items():
        v = f(base)
        filas.append([nombre, _p(v.mean(), 0), f"{int(v.sum())} de {len(v)}"])
    o.append(_tabla(filas, ["Condición", "Meses", "Conteo"]))
    abajo = CONDICIONES["yield del REIT abajo del Treasury a 10 años"](base).mean()
    o.append(f"\nEl yield de los REITs estuvo abajo del Treasury {_p(abajo, 0)} de los meses —casi toda la década de 1980, "
             "cuando las tasas eran altísimas y los REITs rindieron bien—. Una alarma que suena tanto no puede "
             "ser una regla de salida tal cual; tendría que medirse contra su propia historia.\n")
    o.append("## 3. El techo teórico\n### ¿Qué tan seguido le ganó el efectivo a los REITs?\n")
    o.append(_tabla([[str(int(f["horizonte_meses"])), _p(f["fraccion_efectivo_gana"], 0), str(int(f["independientes"])),
                      _p(f["rendimiento_reits_mediana"]), _p(f["rendimiento_efectivo_mediana"])]
                     for _, f in fr.iterrows()],
                    ["Meses hacia adelante", "El efectivo ganó", "Ventanas independientes", "REITs (mediana anual)",
                     "Efectivo (mediana anual)"]))
    o.append("\n### Cuánto valdría conocer el futuro\n\nAportando 1,000 dólares al mes, con impuestos de "
             "residente mexicano vía SIC y comisiones. «Nunca vende» solo decide a dónde va el dinero nuevo; "
             "«rebalancea» puede vender y volver a comprar (pagando 10% sobre la ganancia).\n")
    o.append(_tabla([[f["regla"], f["modo"], _p(f["tir"], 2), f"{f['contra_aportar_siempre_bps']:+,d}",
                      _p(f["caida_maxima"], 0), _p(f["exposicion_promedio"], 0), str(int(f["cambios"]))]
                     for _, f in te.tabla.iterrows()],
                    ["Regla", "Modo", "TIR", "Contra aportar siempre (pb/año)", "Caída máxima", "Exposición",
                     "Cambios"]))
    nunca = te.tabla[(te.tabla["modo"] == "nunca vende") & (te.tabla["regla"] != "aportar siempre")]
    mejor_nunca = int(nunca["contra_aportar_siempre_bps"].max())
    o.append(f"\n**La conclusión más importante de esta fase.** Si solo se decide a dónde va el dinero nuevo, "
             f"ni un oráculo perfecto agrega más de {mejor_nunca:+d} pb al año: la riqueza ya invertida pesa "
             "mucho más que la aportación de un mes. Una regla real captura una fracción del oráculo, así que "
             "por esa vía no se llega al criterio de +50 pb. **Si existe valor en saber cuándo entrar, está en "
             "poder salir**: vender antes de una caída grande y volver a entrar. Con esa libertad, el oráculo de "
             "12 meses agrega cientos de puntos base y esquivar las cuatro caídas reduce la caída máxima de "
             "−69% a −18%, aun pagando impuestos. La fase 5 se concentra ahí, sin perder de vista que son muy "
             "pocas caídas para aprender de ellas.\n")
    import re

    texto = re.sub(r"\n(#+ )", r"\n\n\1", "".join(o))
    texto = re.sub(r"([^\n|])\n\|", r"\1\n\n|", texto)
    return re.sub(r"\n{3,}", "\n\n", texto)
