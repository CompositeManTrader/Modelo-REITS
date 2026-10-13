"""Los ETFs amplios de REITs contra el índice que midió la investigación.

La investigación concluyó que lo que ninguna regla superó fue aportar siempre al FTSE Nareit
All Equity REITs. Un ETF amplio es la manera práctica de comprar ese índice; aquí se mide qué
tanto se le parece cada uno: cuánto rinde, cuánto cae, qué tanto se desvía y cuánto queda
aportando cada mes con el broker de EE. UU. al 35%.

Es descriptivo: no prueba reglas ni suma intentos. Sí mira el índice después de 2016, así que
esa apertura queda en la bitácora de la investigación.

Tres ventanas: la común (desde que existen los tres), la propia (cada ETF desde su inicio) y
la de su índice actual (desde que cada uno cambió al índice que sigue hoy).
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import DIR_ESTUDIOS
from src.investigacion import datos, exploracion, muestras
from src.investigacion.diseno import PERFILES
from src.investigacion.mercados import _mensual
from src.investigacion.muestras import Muestra
from src.investigacion.simulacion import Mercado, benchmark

DIR_ETFS = DIR_ESTUDIOS / "etfs"
ETFS = ("USRT", "SCHH", "VNQ")
INDICE = "Índice"
MOTIVO = "comparación descriptiva de ETFs de REITs contra el índice (13-oct-2026); no prueba reglas"
PERFIL = "broker_35"

# Costo anual publicado por cada emisor (consulta de octubre de 2026). Solo es contexto: lo que
# cuesta de verdad se ve en la diferencia contra el índice, que además incluye no replicarlo.
COSTOS_PUBLICADOS = {"USRT": 0.0008, "SCHH": 0.0007, "VNQ": 0.0013}

# Desde qué mes sigue cada ETF el índice que sigue hoy (el primer mes completo después del cambio):
# * USRT era el iShares Real Estate 50 (FTY, FTSE Nareit Real Estate 50) hasta noviembre de 2016;
#   desde entonces sigue el FTSE Nareit Equity REITs (desde junio de 2025, su versión con topes).
# * VNQ pasó del MSCI US REIT al MSCI US IMI Real Estate 25/50, que también tiene inmobiliarias
#   que no son REITs, en febrero de 2018 (la transición terminó en el tercer trimestre).
# * SCHH pasó del Dow Jones U.S. Select REIT al Dow Jones Equity All REIT Capped en junio de 2020.
INDICE_ACTUAL_DESDE = {"USRT": pd.Timestamp("2016-12-31"), "VNQ": pd.Timestamp("2018-03-31"),
                       "SCHH": pd.Timestamp("2020-07-31")}
INDICE_QUE_SIGUE = {"USRT": "FTSE Nareit Equity REITs (con topes)", "SCHH": "Dow Jones Equity All REIT Capped",
                    "VNQ": "MSCI US IMI Real Estate 25/50"}
# Los ETFs cuyo índice propio también está en la serie de Nareit: el FTSE Nareit Equity REITs es el
# All Equity sin los REITs de infraestructura (torres de telecomunicaciones) ni de madera.
INDICE_PROPIO_NAREIT = {"USRT": "equity"}
DESCRIPCION_PROPIO = {"equity": "deja fuera los REITs de torres de telecomunicaciones y de madera"}


# --------------------------------------------------------------------------------------
# Datos
# --------------------------------------------------------------------------------------


def bajar(tickers: tuple[str, ...] = ETFS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Toca la red: cierres de fin de mes y dividendos de Yahoo."""
    from src.estudio import universo

    precios, dividendos, _, fallas = universo.bajar_historias(list(tickers))
    if fallas:
        raise RuntimeError(f"No se pudieron bajar: {fallas}")
    return precios, dividendos


def guardar_datos(precios: pd.DataFrame, dividendos: pd.DataFrame, *, raiz: Path | None = None) -> Path:
    d = raiz or DIR_ETFS
    datos._escribir(precios, d / "precios_mensuales.csv.gz")
    datos._escribir(dividendos, d / "dividendos.csv.gz")
    (d / "manifiesto.json").write_text(json.dumps({
        "descargado_en": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "fuente": "Yahoo Finance, chart v8: cierre (ajustado por splits) y cierre ajustado de fin de mes; "
                  "dividendos con fecha ex",
        "meses": {t: int(n) for t, n in precios.groupby("ticker").size().items()},
        "desde": {t: str(f.date()) for t, f in pd.to_datetime(precios["fecha"]).groupby(precios["ticker"]).min().items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def cargar_datos(raiz: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    d = raiz or DIR_ETFS
    if not (d / "precios_mensuales.csv.gz").exists():
        return None
    return (pd.read_csv(d / "precios_mensuales.csv.gz", parse_dates=["fecha"]),
            pd.read_csv(d / "dividendos.csv.gz", parse_dates=["fecha_ex"]))


def series(precios: pd.DataFrame, dividendos: pd.DataFrame, *, hoy: pd.Timestamp | None = None
           ) -> dict[str, pd.DataFrame]:
    """Cada ETF mes a mes: retorno total, de precio, de ingreso y yield de 12 meses."""
    hoy = hoy or pd.Timestamp.today()
    dividendos = dividendos.assign(fecha_ex=pd.to_datetime(dividendos["fecha_ex"]))
    return {t: _mensual(precios, dividendos, t, hoy).dropna(subset=["retorno_total", "retorno_precio"])
            for t in ETFS if t in set(precios["ticker"])}


def indice(*, ruta_bitacora=None) -> pd.DataFrame:
    """El FTSE Nareit All Equity REITs y el T-bill, de 1972 al último mes (registra la apertura)."""
    return exploracion.sector(Muestra.VALIDACION, motivo=MOTIVO, ruta_bitacora=ruta_bitacora)


def indices_propios(*, ruta_bitacora=None) -> pd.DataFrame:
    """Los índices de Nareit que siguen los ETFs (registra su propia apertura)."""
    n = datos.cargar_sector()["nareit"]
    n = n[n["indice"].isin(set(INDICE_PROPIO_NAREIT.values()))]
    return muestras.recortar(n, Muestra.VALIDACION, columna="fecha", motivo=f"{MOTIVO} (índices propios de los ETFs)",
                             ruta_bitacora=ruta_bitacora)


# --------------------------------------------------------------------------------------
# Métricas
# --------------------------------------------------------------------------------------


def anual(r: pd.Series) -> float:
    return float((1 + r).prod() ** (12 / len(r)) - 1) if len(r) else np.nan


def caida(r: pd.Series) -> dict:
    """La peor caída del retorno total: cuánto, cuándo fue el pico y el fondo, y cuánto tardó en recuperarse."""
    nivel = (1 + r.fillna(0)).cumprod()
    base = pd.Series([1.0], index=[r.index[0] - pd.offsets.MonthEnd(1)])
    nivel = pd.concat([base, nivel])
    tramo = nivel / nivel.cummax() - 1
    valle = tramo.idxmin()
    pico = nivel.loc[:valle].idxmax()
    despues = nivel.loc[valle:]
    recupera = despues[despues >= nivel[pico]]
    meses = None
    if len(recupera):
        meses = (recupera.index[0].year - valle.year) * 12 + recupera.index[0].month - valle.month
    return {"caida_maxima": float(tramo.min()), "pico": pico, "fondo": valle, "meses_para_recuperarse": meses}


def peor_anio(r: pd.Series) -> tuple[float, int | None]:
    """El peor año calendario completo dentro de la serie."""
    anios = r.groupby(r.index.year)
    completos = {a: float((1 + g).prod() - 1) for a, g in anios if len(g) == 12}
    if not completos:
        return np.nan, None
    a = min(completos, key=completos.get)
    return completos[a], a


def tir_aportando(x: pd.DataFrame, efectivo: pd.Series, perfil: str = PERFIL) -> float:
    """La TIR neta de aportar cada mes sin vender nunca, como el «aportar siempre» de la investigación."""
    m = Mercado(x.index, x["retorno_precio"].to_numpy(), (x["retorno_total"] - x["retorno_precio"]).to_numpy(),
                efectivo.reindex(x.index).fillna(0).to_numpy())
    return benchmark(m, objetivo=PERFILES[perfil]).tir


def pagos_por_anio(dividendos: pd.DataFrame, ticker: str, anio: int) -> int:
    d = dividendos[dividendos["ticker"] == ticker]
    return int((pd.to_datetime(d["fecha_ex"]).dt.year == anio).sum())


def metricas(r: pd.Series, efectivo: pd.Series, *, ingreso: pd.Series | None = None) -> dict:
    """Lo que se reporta de una serie mensual de retorno total en una ventana."""
    c = caida(r)
    pa, cual = peor_anio(r)
    doce = (1 + r).rolling(12).apply(np.prod, raw=True) - 1
    x = pd.DataFrame({"retorno_total": r, "retorno_precio": r - (ingreso if ingreso is not None else 0.0)})
    return {"desde": r.index.min(), "hasta": r.index.max(), "meses": len(r), "rendimiento_anual": anual(r),
            "crecimiento_de_1": float((1 + r).prod()), "volatilidad": float(r.std() * np.sqrt(12)),
            **c, "peor_anio": pa, "cual_peor_anio": cual, "peores_12_meses": float(doce.min()),
            "tir_neta_aportando": tir_aportando(x, efectivo)}


def comparar(etfs: dict[str, pd.DataFrame], x_indice: pd.DataFrame, dividendos: pd.DataFrame, *,
             desde: dict[str, pd.Timestamp] | pd.Timestamp | None = None, hasta: pd.Timestamp | None = None
             ) -> pd.DataFrame:
    """Una fila por ETF y su índice en los mismos meses: rendimiento, seguimiento, caídas y TIR neta."""
    filas = []
    for t, s in etfs.items():
        inicio = desde.get(t) if isinstance(desde, dict) else desde
        s = s.loc[inicio:hasta]
        comun = s.index.intersection(x_indice["retorno_total"].dropna().index)
        s, xi = s.loc[comun], x_indice.loc[comun]
        if len(comun) < 24:
            continue
        # El seguimiento sale de la misma función que validó los fondos al bajar el índice.
        v = datos.validar_contra_fondos(xi.reset_index().assign(indice="all_equity"),
                                        s.reset_index().assign(ticker=t)).iloc[0]
        ultimo_anio_completo = comun.max().year - 1
        fila_etf = {"serie": t, **metricas(s["retorno_total"], xi["efectivo"], ingreso=s["retorno_ingreso"]),
                    "diferencia_anual": v["diferencia_anual"], "error_de_seguimiento": v["error_de_seguimiento"],
                    "correlacion": v["correlacion"], "yield_12m": float(s["yield_dividendo"].iloc[-1]),
                    "pagos_por_anio": pagos_por_anio(dividendos, t, ultimo_anio_completo),
                    "costo_publicado": COSTOS_PUBLICADOS.get(t)}
        fila_indice = {"serie": f"{INDICE} (meses de {t})",
                       **metricas(xi["retorno_total"], xi["efectivo"], ingreso=xi["retorno_ingreso"]),
                       "yield_12m": float(xi["yield_dividendo"].iloc[-1])}
        filas += [fila_etf, fila_indice]
    return pd.DataFrame(filas)


def contra_su_indice(etfs: dict[str, pd.DataFrame], nareit: pd.DataFrame, *, desde: dict[str, pd.Timestamp],
                     hasta: pd.Timestamp) -> pd.DataFrame:
    """El seguimiento de cada ETF contra su propio índice, cuando ese índice está en la serie de Nareit."""
    filas = []
    for t, ind in INDICE_PROPIO_NAREIT.items():
        if t in etfs:
            s = etfs[t].loc[desde.get(t):hasta]
            v = datos.validar_contra_fondos(nareit, s.reset_index().assign(ticker=t), indice=ind)
            filas += [v.assign(indice=ind)] if not v.empty else []
    return pd.concat(filas, ignore_index=True) if filas else pd.DataFrame()


def anio_por_anio(etfs: dict[str, pd.DataFrame], x_indice: pd.DataFrame, desde: pd.Timestamp) -> pd.DataFrame:
    """Retorno total de cada año calendario: el índice y los ETFs (el último año, hasta donde hay datos)."""
    cols = {INDICE: x_indice["retorno_total"]} | {t: s["retorno_total"] for t, s in etfs.items()}
    panel = pd.DataFrame(cols).loc[desde:].dropna()
    t = panel.groupby(panel.index.year).apply(lambda g: (1 + g).prod() - 1)
    t["meses"] = panel.groupby(panel.index.year).size()
    t.index.name = "anio"
    return t.reset_index()


# --------------------------------------------------------------------------------------
# Corrida
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoETFs:
    tablas: dict[str, pd.DataFrame]
    notas: dict = field(default_factory=dict)

    def __getitem__(self, nombre: str) -> pd.DataFrame:
        return self.tablas.get(nombre, pd.DataFrame())


def correr(precios: pd.DataFrame, dividendos: pd.DataFrame, x_indice: pd.DataFrame | None = None, *,
           nareit_propios: pd.DataFrame | None = None, hoy: pd.Timestamp | None = None,
           ruta_bitacora=None) -> ResultadoETFs:
    """Sin ``x_indice``, carga el índice y los índices propios de Nareit (y registra las aperturas)."""
    if x_indice is None:
        x_indice = indice(ruta_bitacora=ruta_bitacora)
        nareit_propios = indices_propios(ruta_bitacora=ruta_bitacora)
    s = series(precios, dividendos, hoy=hoy)
    hasta = min(x_indice.index.max(), *(v.index.max() for v in s.values()))
    inicio_comun = max(v.index.min() for v in s.values())
    t = {"comun": comparar(s, x_indice, dividendos, desde=inicio_comun, hasta=hasta),
         "propia": comparar(s, x_indice, dividendos, hasta=hasta),
         "indice_actual": comparar(s, x_indice, dividendos, desde=INDICE_ACTUAL_DESDE, hasta=hasta),
         "anios": anio_por_anio(s, x_indice.loc[:hasta], inicio_comun)}
    if nareit_propios is not None:
        t["su_indice"] = contra_su_indice(s, nareit_propios, desde=INDICE_ACTUAL_DESDE, hasta=hasta)
    notas = {"perfil": PERFIL, "inicio_comun": str(inicio_comun.date()), "hasta": str(hasta.date()),
             "aportacion_mensual": float(PERFILES[PERFIL].aportacion_mensual)}
    return ResultadoETFs(t, notas)


def guardar(r: ResultadoETFs, *, raiz: Path | None = None) -> Path:
    d = (raiz or DIR_ETFS) / "resultados"
    d.mkdir(parents=True, exist_ok=True)
    for nombre, tabla in r.tablas.items():
        if not tabla.empty:
            tabla.to_csv(d / f"{nombre}.csv", index=False, float_format="%.10g")
    (d / "notas.json").write_text(json.dumps(r.notas, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def cargar(raiz: Path | None = None) -> ResultadoETFs | None:
    d = (raiz or DIR_ETFS) / "resultados"
    if not d.exists():
        return None
    notas = json.loads((d / "notas.json").read_text(encoding="utf-8")) if (d / "notas.json").exists() else {}
    return ResultadoETFs({a.stem: pd.read_csv(a) for a in sorted(d.glob("*.csv"))}, notas)


# --------------------------------------------------------------------------------------
# El informe
# --------------------------------------------------------------------------------------


def _p(v, d: int = 1) -> str:
    return "—" if v is None or pd.isna(v) else f"{float(v) * 100:.{d}f}%"


def _pb(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    x = round(float(v) * 1e4)
    return f"{x:+,d}" if x else "0"


def _mes(f) -> str:
    return "—" if f is None or pd.isna(f) else pd.Timestamp(f).strftime("%Y-%m")


def _md(filas: list[list[str]], encabezado: list[str]) -> str:
    return ("\n| " + " | ".join(encabezado) + " |\n|" + "|".join("---" for _ in encabezado) + "|\n"
            + "".join("| " + " | ".join(str(c) for c in f) + " |\n" for f in filas) + "\n")


def _recupera(v) -> str:
    return "sin recuperarse" if v is None or pd.isna(v) else f"{int(v)} meses"


def _tabla(c: pd.DataFrame) -> str:
    filas = []
    for _, f in c.iterrows():
        es_etf = f["serie"] in ETFS
        filas.append([f"**{f['serie']}**" if es_etf else f["serie"], f"{_mes(f['desde'])} a {_mes(f['hasta'])}",
                      _p(f["rendimiento_anual"]), _pb(f.get("diferencia_anual")) if es_etf else "—",
                      _p(f.get("error_de_seguimiento"), 2) if es_etf else "—",
                      f"{f['correlacion']:.4f}" if es_etf else "—",
                      f"{_p(f['caida_maxima'])} ({_mes(f['pico'])} a {_mes(f['fondo'])})",
                      _recupera(f["meses_para_recuperarse"]),
                      f"{_p(f['peor_anio'])} ({int(f['cual_peor_anio'])})" if pd.notna(f["cual_peor_anio"]) else "—",
                      _p(f["volatilidad"]), _p(f["tir_neta_aportando"]), _p(f["yield_12m"], 2)])
    return _md(filas, ["Serie", "Meses", "Rendimiento anual", "Contra el índice (pb al año)",
                       "Error de seguimiento", "Correlación", "Caída máxima", "Recuperación", "Peor año",
                       "Volatilidad", "TIR neta aportando", "Yield 12m"])


def _etfs(c: pd.DataFrame) -> pd.DataFrame:
    return c[c["serie"].isin(ETFS)].set_index("serie")


def _indice_de(c: pd.DataFrame, t: str) -> pd.Series:
    return c[c["serie"] == f"{INDICE} (meses de {t})"].iloc[0]


def lectura(r: ResultadoETFs) -> str:
    c, e, ea, ep = r["comun"], _etfs(r["comun"]), _etfs(r["indice_actual"]), _etfs(r["propia"])
    i = c[~c["serie"].isin(ETFS)].iloc[0]
    fiel = ea["error_de_seguimiento"].idxmin()
    lista = lambda col, d=1, x=e: ", ".join(f"{_p(x.loc[t, col], d)} {t}" for t in x.index)  # noqa: E731
    o = [f"* **El más parecido al índice de la investigación es {fiel}.** Desde que sigue su índice actual "
         f"({_mes(ea.loc[fiel, 'desde'])}) se desvía {_p(ea.loc[fiel, 'error_de_seguimiento'], 2)} al año, con una "
         f"diferencia de {_pb(ea.loc[fiel, 'diferencia_anual'])} pb al año y correlación de "
         f"{ea.loc[fiel, 'correlacion']:.4f}. "
         + "; ".join(f"{t} se desvía {_p(ea.loc[t, 'error_de_seguimiento'], 2)} ({_pb(ea.loc[t, 'diferencia_anual'])} "
                     f"pb al año desde {_mes(ea.loc[t, 'desde'])})" for t in ea.index if t != fiel) + ".\n"]
    for _, f in r["su_indice"].iterrows():
        if f["fondo"] == fiel:
            continue
        o.append(f"* **{f['fondo']} se desvía más porque su índice {DESCRIPCION_PROPIO[f['indice']]}.** Contra su "
                 f"propio índice se desvía solo {_p(f['error_de_seguimiento'], 2)} al año (correlación "
                 f"{f['correlacion']:.4f}).\n")
    o.append(f"* **Antes de impuestos rinden casi lo mismo que el índice:** desde {_mes(i['desde'])}, "
             f"{_p(i['rendimiento_anual'])} al año el índice contra {lista('rendimiento_anual')}. Parte de la "
             "diferencia viene de los índices que seguían antes.\n")
    o.append("* **Ninguno te quita las caídas.** La peor de cada uno desde su inicio: "
             + "; ".join(f"{t} {_p(ep.loc[t, 'caida_maxima'])} ({_mes(ep.loc[t, 'pico'])} a {_mes(ep.loc[t, 'fondo'])}"
                         f", el índice {_p(_indice_de(r['propia'], t)['caida_maxima'])})" for t in ep.index) + ".\n")
    o.append(f"* **Aportando {r.notas.get('aportacion_mensual', 1000):,.0f} dólares cada mes con el broker al 35%**, "
             f"desde {_mes(i['desde'])}, la TIR neta fue de {_p(i['tir_neta_aportando'])} en el índice contra "
             f"{lista('tir_neta_aportando')}. La TIR pesa más los últimos años, cuando ya hay más dinero invertido, "
             "así que favorece al que mejor le fue al final.\n")
    pagos = sorted(set(e["pagos_por_anio"].astype(int)))
    o.append(f"* **Pagan {', '.join(map(str, pagos))} veces al año** (cada trimestre), con un yield de "
             f"{lista('yield_12m', 2)} en los últimos 12 meses.\n")
    return "".join(o)


def informe(r: ResultadoETFs) -> str:
    n = r.notas
    o = ["# ETFs de REITs contra el índice de la investigación\n\n",
         "Generado por `python scripts/estudio.py etfs`. Compara USRT, SCHH y VNQ contra el FTSE Nareit All "
         "Equity REITs, el índice sobre el que la investigación midió «aportar siempre». Es descriptivo: no prueba "
         "reglas. Retornos totales (con dividendos reinvertidos) en dólares, antes de impuestos, salvo la TIR "
         f"neta, que aporta {n.get('aportacion_mensual', 1000):,.0f} dólares cada mes sin vender nunca con el perfil "
         "del broker de EE. UU. al 35% (dividendo 44%, intereses 35%, ganancia 10%, sin comisión), igual que en la "
         "investigación.\n\n## En corto\n\n", lectura(r), "\n"]
    o.append(f"## Ventana común ({n.get('inicio_comun', '')[:7]} a {n.get('hasta', '')[:7]})\n\n"
             "Los tres ETFs y el índice en los mismos meses: la comparación pareja.\n")
    o.append(_tabla(r["comun"]))
    o.append("## Con el índice que sigue hoy cada ETF\n\nCada uno cambió de índice al menos una vez; desde el "
             "cambio, la desviación contra el índice de la investigación es la mejor guía de lo que se puede esperar.\n\n"
             + "".join(f"* **{t}** sigue el {INDICE_QUE_SIGUE[t]} desde {_mes(INDICE_ACTUAL_DESDE[t])}.\n"
                       for t in ETFS))
    o.append(_tabla(r["indice_actual"]))
    su = r["su_indice"]
    if not su.empty:
        o.append("Contra su propio índice, cuando ese índice también lo publica Nareit:\n")
        o.append(_md([[f["fondo"], f"FTSE Nareit {'Equity REITs' if f['indice'] == 'equity' else f['indice']}",
                       f"{_mes(f['desde'])} a {_mes(f['hasta'])}", f"{f['correlacion']:.4f}",
                       _pb(f["diferencia_anual"]), _p(f["error_de_seguimiento"], 2)] for _, f in su.iterrows()],
                     ["ETF", "Su índice", "Meses", "Correlación", "Diferencia (pb al año)", "Error de seguimiento"]))
    o.append("## Desde el inicio de cada ETF\n\nMás historia (VNQ y USRT pasaron por 2008-2009), pero con índices "
             "distintos al de hoy: USRT seguía a los 50 REITs más grandes hasta 2016 y VNQ solo REITs hasta 2018.\n")
    o.append(_tabla(r["propia"]))
    a = r["anios"]
    if not a.empty:
        cols = [INDICE, *[t for t in ETFS if t in a.columns]]
        filas = [[f"{int(f['anio'])}" + (f" (a {int(f['meses'])} meses)" if f["meses"] < 12 else ""),
                  *[_p(f[c]) for c in cols]] for _, f in a.iterrows()]
        o.append("## Año por año\n")
        o.append(_md(filas, ["Año", *cols]))
    costos = ", ".join(f"{t} {_p(v, 2)}" for t, v in COSTOS_PUBLICADOS.items())
    o.append("## Qué no mide y límites\n\n"
             f"* El costo publicado por cada emisor (consulta de octubre de 2026) es {costos} al año; la diferencia "
             "contra el índice ya lo incluye, junto con lo que el fondo no replica.\n"
             "* Precios y dividendos de Yahoo Finance (cierre ajustado de fin de mes). El índice no tiene costos, así "
             "que parte de la diferencia es por construcción.\n"
             "* Los impuestos son los del modelo de la investigación; la retención real del broker y el acreditamiento "
             "en México los confirma un contador.\n"
             "* No incluye el impuesto sucesorio de EE. UU. (activos de EE. UU. arriba de 60 mil dólares): los tres "
             "ETFs son de EE. UU.; los UCITS domiciliados en Irlanda quedan fuera de ese impuesto.\n"
             "* Esta comparación mira los datos del índice posteriores a 2016 y lo deja en la bitácora de la "
             "investigación; no suma intentos porque no prueba reglas.\n")
    return "".join(o)
