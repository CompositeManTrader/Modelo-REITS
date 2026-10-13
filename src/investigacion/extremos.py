"""Exploratoria: ¿qué pasa cuando la valuación está en su extremo?

Pre-registro: ``docs/investigacion/extremos_preregistro.md``. Se decidió después de ver todas
las fases, así que nada de lo que salga se adopta: lo que salga a favor queda como pista para
una prueba nueva con datos nuevos.

Tres niveles: el sector (Nareit desde 1972), O, NNN y WPC, y el corte transversal de todos los
REITs de capital de EE. UU. (fase 6). En el sector y en los emisores, el extremo es el percentil
expandible de la señal contra su propia historia; en el corte transversal, el decil entre
emisores de cada trimestre. Todas las señales están orientadas para que alto = barato.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.investigacion import bitacora, estadistica, exploracion, fase6, muestras, senales, timing
from src.investigacion.diseno import CRITERIOS, MUESTRAS, PERFILES
from src.investigacion.exploracion import _adelante
from src.investigacion.muestras import Muestra
from src.modelo.senal import percentil_expandible

FAMILIA = "extremos"
MOTIVO = "exploratoria de los extremos de valuación (13-oct-2026), declarada posterior a todas las fases"

# Percentil (alto = barato). Los de los extremos incluyen la orilla.
CORTES: dict[str, tuple[float, float]] = {
    "caro 5%": (0.0, 0.05), "caro 10%": (0.0, 0.10), "centro": (0.10, 0.90),
    "barato 10%": (0.90, 1.0), "barato 5%": (0.95, 1.0),
}
EXTREMOS = ("caro 5%", "caro 10%", "barato 10%", "barato 5%")
UMBRALES_DE_SALIDA = (0.05, 0.10)
HORIZONTES_SECTOR = (12, 60)
SEPARACION_MESES = 12
PERFILES_REGLAS = ("sic", "broker_35")
EMISORES = ("NNN", "O", "WPC")
SENALES_EMISOR = {"consenso": "pc_consenso", "prima_treasury": "p_prima_treasury"}
SENALES_TRANSVERSAL = ("rendimiento_del_dividendo", "rendimiento_ffo", "rendimiento_de_la_empresa",
                       "yield_contra_su_historia")
DECILES = replace(fase6.DISENO6, grupos=10)
T_MINIMA = 2.0


def senales_de_valuacion() -> list[timing.Senal]:
    return [s for s in senales.CATALOGO if s.familia == "valuacion"]


def en_corte(p: pd.Series, corte: str) -> pd.Series:
    bajo, alto = CORTES[corte]
    if bajo == 0.0:
        return p <= alto
    if alto == 1.0:
        return p >= bajo
    return (p > bajo) & (p < alto)


def episodios(mascara: pd.Series | np.ndarray, separacion: int = SEPARACION_MESES) -> int:
    """Rachas de periodos en la condición; dos rachas a menos de ``separacion`` periodos son la misma."""
    pos = np.flatnonzero(np.asarray(mascara, dtype=bool))
    if len(pos) == 0:
        return 0
    return int(1 + (np.diff(pos) > separacion).sum())


def diferencia_hac(y: pd.Series, d: pd.Series, rezago: int) -> tuple[float, float]:
    """Promedio de ``y`` con ``d`` verdadero menos el resto, con su t de Newey-West."""
    ok = y.notna() & d.notna()
    y, d = y[ok].astype(float), d[ok].astype(float)
    if d.sum() < 2 or (1 - d).sum() < 2:
        return np.nan, np.nan
    modelo = sm.OLS(y.to_numpy(), sm.add_constant(d.to_numpy())).fit(cov_type="HAC", cov_kwds={"maxlags": rezago})
    return float(modelo.params[1]), float(modelo.tvalues[1])


def _anualizar(r: pd.Series, meses: int) -> pd.Series:
    return (1 + r) ** (12 / meses) - 1


def percentil_de(s: pd.Series, minimo: int) -> pd.Series:
    return percentil_expandible(s.dropna(), min_observaciones=minimo).reindex(s.index)


# --------------------------------------------------------------------------------------
# 1. El sector
# --------------------------------------------------------------------------------------


def tabla_sector(x: pd.DataFrame, ind: pd.DataFrame, *, muestra: str, desde: pd.Timestamp | None = None
                 ) -> pd.DataFrame:
    """Retorno siguiente de los REITs y del efectivo en cada corte de cada señal de valuación."""
    filas = []
    for senal in senales_de_valuacion():
        p = percentil_de(senales.calcular(senal, x, ind), senales.MINIMO_DE_HISTORIA)
        for h in HORIZONTES_SECTOR:
            reit = _anualizar(_adelante(x["retorno_total"], h), h)
            cash = _anualizar(_adelante(x["efectivo"], h), h)
            valido = reit.notna() & cash.notna() & p.notna() & pd.Series(np.arange(len(x)) < len(x) - h, x.index)
            if desde is not None:
                valido &= x.index >= desde
            exceso = reit - cash
            for corte in CORTES:
                m = en_corte(p, corte) & valido
                dif, t = diferencia_hac(exceso[valido], m[valido], h)
                filas.append({
                    "nivel": "sector", "senal": senal.nombre, "muestra": muestra, "horizonte_meses": h, "corte": corte,
                    "meses": int(m.sum()), "frecuencia": float(m.sum() / valido.sum()) if valido.sum() else np.nan,
                    "episodios": episodios(m), "reits_mediana": float(reit[m].median()) if m.any() else np.nan,
                    "efectivo_mediana": float(cash[m].median()) if m.any() else np.nan,
                    "exceso_mediana": float(exceso[m].median()) if m.any() else np.nan,
                    "efectivo_gana": float((cash[m] > reit[m]).mean()) if m.any() else np.nan,
                    "diferencia_contra_el_resto": dif, "t": t})
    return pd.DataFrame(filas)


def reglas_sector(x: pd.DataFrame, ind: pd.DataFrame, *, muestra: str, desde: pd.Timestamp | None = None,
                  perfiles: tuple[str, ...] = PERFILES_REGLAS, registrar: bool = True, ruta_bitacora=None
                  ) -> pd.DataFrame:
    """«Fuera solo en el 5% (o 10%) más caro»: la regla de la fase 5 con un umbral extremo."""
    filas = []
    for senal in senales_de_valuacion():
        s = senales.calcular(senal, x, ind)
        for umbral in UMBRALES_DE_SALIDA:
            e = timing.exposicion_binaria_por_percentil(s, umbral, minimo=senales.MINIMO_DE_HISTORIA)
            nombre = f"fuera en el {umbral:.0%} más caro"
            for k in perfiles:
                r = timing.evaluar(senal, nombre, e, x, ind, muestra=muestra, desde=desde, registrar=False,
                                   objetivo=PERFILES[k], con_prediccion=False)
                r["perfil"] = k
                filas.append(r)
                if registrar:
                    bitacora.registrar(fase="extremos", familia=FAMILIA, prueba=f"{senal.nombre} | {nombre}",
                                       muestra=muestra, parametros={"perfil": k}, metrica="mejora_rebalanceo",
                                       valor=round(float(r["mejora_rebalanceo"]), 6), ruta=ruta_bitacora)
    return timing.resumen(filas)


# --------------------------------------------------------------------------------------
# 2. O, NNN y WPC
# --------------------------------------------------------------------------------------


def paneles_emisores(construidos: dict | None = None, *, tasa_dividendo: float, tasa_efectivo: float
                     ) -> dict[str, pd.DataFrame]:
    """Los paneles de métodos con el dividendo y el efectivo netos de esas tasas, más el percentil
    expandible del propio consenso (el promedio de percentiles casi nunca llega a las colas)."""
    from src.estudio import estudio, macro, metodos
    from src.estudio import reglas as rg

    construidos = construidos or {t: estudio.armar_versionado(t) for t in EMISORES}
    tbill, baa, cpi = rg.cargar_tbill(), macro.cargar("baa"), macro.cargar("cpi")
    parametros = replace(rg.PARAMETROS, impuesto_intereses=tasa_efectivo)
    salida = {}
    for t, e in construidos.items():
        p = metodos.panel(estudio.con_dividendo_neto(e, tasa_dividendo), baa=baa, cpi=cpi, tbill=tbill,
                          parametros=parametros)
        p["pc_consenso"] = percentil_de(p["v_consenso"], metodos.MIN_MESES)
        salida[t] = p
    return salida


def _por_corte(d: pd.DataFrame, columna: str, anios: int, etiqueta: dict) -> list[dict]:
    filas = []
    y = d[f"adelante_{anios}a"]
    for corte in CORTES:
        m = en_corte(d[columna], corte) & y.notna() & d[columna].notna()
        v = y[m]
        filas.append({**etiqueta, "anios": anios, "corte": corte, "trimestres": int(m.sum()),
                      "ventanas_independientes": float(m.sum() / (4 * anios)),
                      "episodios": int(sum(episodios(m[d["emisor"] == t], 4) for t in d["emisor"].unique())),
                      "mediana": float(v.median()) if len(v) else np.nan,
                      "p10": float(v.quantile(0.10)) if len(v) else np.nan,
                      "p90": float(v.quantile(0.90)) if len(v) else np.nan,
                      "efectivo_5a": float(d.loc[m, "efectivo_5a"].median()) if anios == 5 and m.any() else np.nan})
    return filas


def tabla_emisores(paneles: dict[str, pd.DataFrame]) -> pd.DataFrame:
    from src.estudio import metodos

    filas = []
    trimestres = {t: metodos.trimestral(p).assign(emisor=t) for t, p in paneles.items()}
    for senal, columna in SENALES_EMISOR.items():
        alcances = [("juntos", list(trimestres))] + [(t, [t]) for t in trimestres]
        for alcance, tickers in alcances:
            d = pd.concat([trimestres[t] for t in tickers])
            for anios in (1, 3, 5):
                filas += _por_corte(d, columna, anios, {"nivel": "emisores", "senal": senal, "alcance": alcance,
                                                        "mitad": "completo"})
                # Las dos mitades de cada emisor (por fechas con retorno a ese plazo).
                for nombre, primera in (("primera mitad", True), ("segunda mitad", False)):
                    partes = []
                    for t in tickers:
                        q = trimestres[t]
                        fechas = q.index[q[f"adelante_{anios}a"].notna() & q[columna].notna()]
                        if len(fechas) < 2:
                            continue
                        corte = fechas[len(fechas) // 2]
                        partes.append(q[q.index < corte] if primera else q[q.index >= corte])
                    if partes:
                        filas += _por_corte(pd.concat(partes), columna, anios,
                                            {"nivel": "emisores", "senal": senal, "alcance": alcance, "mitad": nombre})
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# 3. El corte transversal (fase 6)
# --------------------------------------------------------------------------------------


def tabla_transversal(panel: pd.DataFrame, *, muestra: str, desde: pd.Timestamp | None = None,
                      hasta: pd.Timestamp | None = None, perfil: str = "broker_35", registrar: bool = True,
                      ruta_bitacora=None) -> pd.DataFrame:
    """El decil más barato y el más caro de cada señal de valuación contra todos los elegibles."""
    d = DECILES
    x = fase6.senales(panel, d)
    desde = desde if desde is not None else fase6.primera_fecha(x, d)
    hasta = hasta if hasta is not None else pd.Timestamp(x["fecha"].max())
    e = x[fase6.elegibles(x, d) & (x["fecha"] >= desde) & (x["fecha"] < hasta)]
    R = fase6.matriz_de_retornos(x[x["fecha"] <= hasta])
    gu = fase6.retorno_de_grupo(e[["fecha", "cik"]], R, d)
    adelante = fase6._adelante(R, d).stack().rename("r12").reset_index()
    todos = e.merge(adelante, on=["fecha", "cik"], how="left")
    filas = []
    for senal in SENALES_TRANSVERSAL:
        g = fase6.grupos_de_senal(e, senal, d)
        tir = fase6.evaluar(senal, x, desde=desde, hasta=hasta, muestra=muestra, d=d, registrar=False,
                            objetivo=PERFILES[perfil])
        for lado, grupo in (("barato 10%", 1), ("caro 10%", d.grupos)):
            m = g == grupo
            sel = e.loc[m, ["fecha", "cik"]]
            gr = fase6.retorno_de_grupo(sel, R, d)
            ventana = (gr.index > desde) & (gr.index <= hasta)
            comun = ventana & gr.notna().to_numpy() & gu.notna().to_numpy()
            exceso = (gr - gu)[comun]
            r12 = sel.merge(adelante, on=["fecha", "cik"], how="left")["r12"]
            fila = {"nivel": "transversal", "senal": senal, "muestra": muestra, "corte": lado,
                    "trimestres": int(len(exceso)), "escogidos_promedio": float(sel.groupby("fecha").size().mean()),
                    "exceso_anual": fase6._anual(gr[comun]) - fase6._anual(gu[comun]),
                    "t": estadistica.newey_west_t(exceso.to_numpy(), d.rezago_nw) if len(exceso) > 8 else np.nan,
                    "recortes": float(e.loc[m, "recorte_siguiente"].mean()),
                    "recortes_todos": float(e["recorte_siguiente"].mean()),
                    "desplomes": float((r12 <= d.desplome).mean()),
                    "desplomes_todos": float((todos["r12"] <= d.desplome).mean()),
                    "mejora_tir": tir["mejora"] if grupo == 1 else np.nan, "perfil_tir": perfil}
            filas.append(fila)
            if registrar:
                bitacora.registrar(fase="extremos", familia=FAMILIA, prueba=f"decil {lado} | {senal}", muestra=muestra,
                                   parametros={"grupos": d.grupos}, metrica="exceso_anual",
                                   valor=round(float(fila["exceso_anual"]), 6), ruta=ruta_bitacora)
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# Hoy, pistas y todo junto
# --------------------------------------------------------------------------------------


def hoy_sector(x: pd.DataFrame, ind: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for senal in senales_de_valuacion():
        s = senales.calcular(senal, x, ind)
        p = percentil_de(s, senales.MINIMO_DE_HISTORIA).dropna()
        corte = next((c for c in CORTES if bool(en_corte(p.iloc[-1:], c).iloc[0])), "")
        filas.append({"nivel": "sector", "senal": senal.nombre, "fecha": p.index[-1], "percentil": float(p.iloc[-1]),
                      "corte": corte})
    return pd.DataFrame(filas)


def hoy_emisores(paneles: dict[str, pd.DataFrame]) -> pd.DataFrame:
    filas = []
    for t, p in paneles.items():
        for senal, columna in SENALES_EMISOR.items():
            v = p[columna].dropna()
            if v.empty:
                continue
            corte = next((c for c in CORTES if bool(en_corte(v.iloc[-1:], c).iloc[0])), "")
            filas.append({"nivel": "emisores", "senal": f"{t} · {senal}", "fecha": v.index[-1],
                          "percentil": float(v.iloc[-1]), "corte": corte})
    return pd.DataFrame(filas)


def pistas(sector: pd.DataFrame, reglas: pd.DataFrame, transversal: pd.DataFrame) -> pd.DataFrame:
    """Lo que cumple la regla de lectura pre-registrada: mismo signo y |t| ≥ 2 en las dos muestras
    (o, en las reglas, +50 pb y positiva con un mes de retraso en las dos)."""
    filas = []
    if not sector.empty:
        s = sector[sector["corte"].isin(EXTREMOS)]
        for (senal, h, corte), g in s.groupby(["senal", "horizonte_meses", "corte"]):
            g = g.set_index("muestra")
            if not {"desarrollo", "validacion"} <= set(g.index):
                continue
            a, b = g.loc["desarrollo"], g.loc["validacion"]
            ok = (np.sign(a["diferencia_contra_el_resto"]) == np.sign(b["diferencia_contra_el_resto"])
                  and abs(a["t"]) >= T_MINIMA and abs(b["t"]) >= T_MINIMA)
            filas.append({"nivel": "sector", "prueba": f"{senal} · {corte} · {h} meses",
                          "desarrollo": a["diferencia_contra_el_resto"], "t_desarrollo": a["t"],
                          "validacion": b["diferencia_contra_el_resto"], "t_validacion": b["t"],
                          "episodios_desarrollo": a["episodios"], "episodios_validacion": b["episodios"],
                          "meses_desarrollo": a["meses"], "meses_validacion": b["meses"], "pista": bool(ok)})
    if not reglas.empty:
        for (senal, regla, perfil), g in reglas.groupby(["senal", "regla", "perfil"]):
            g = g.set_index("muestra")
            if not {"desarrollo", "validacion"} <= set(g.index):
                continue
            a, b = g.loc["desarrollo"], g.loc["validacion"]
            ok = all(f["mejora_rebalanceo"] >= CRITERIOS.mejora_minima_de_tir and f["mejora_rebalanceo_con_rezago"] > 0
                     for f in (a, b))
            filas.append({"nivel": "regla", "prueba": f"{senal} · {regla} · {perfil}",
                          "desarrollo": a["mejora_rebalanceo"], "t_desarrollo": np.nan,
                          "validacion": b["mejora_rebalanceo"], "t_validacion": np.nan, "pista": bool(ok)})
    if not transversal.empty:
        for (senal, corte), g in transversal.groupby(["senal", "corte"]):
            g = g.set_index("muestra")
            if not {"desarrollo", "validacion"} <= set(g.index):
                continue
            a, b = g.loc["desarrollo"], g.loc["validacion"]
            ok = (np.sign(a["exceso_anual"]) == np.sign(b["exceso_anual"])
                  and abs(a["t"]) >= T_MINIMA and abs(b["t"]) >= T_MINIMA)
            filas.append({"nivel": "transversal", "prueba": f"{senal} · {corte}", "desarrollo": a["exceso_anual"],
                          "t_desarrollo": a["t"], "validacion": b["exceso_anual"], "t_validacion": b["t"],
                          "pista": bool(ok)})
    return pd.DataFrame(filas)


@dataclass
class ResultadoExtremos:
    tablas: dict[str, pd.DataFrame]
    notas: dict = field(default_factory=dict)

    def __getitem__(self, nombre: str) -> pd.DataFrame:
        return self.tablas.get(nombre, pd.DataFrame())


def correr(*, registrar: bool = True, ruta_bitacora=None, construidos: dict | None = None,
           panel: pd.DataFrame | None = None) -> ResultadoExtremos:
    from src.investigacion import emisores

    inicio = len(bitacora.leer(ruta_bitacora))
    t: dict[str, pd.DataFrame] = {}
    dev = exploracion.sector(Muestra.DESARROLLO)
    ind = exploracion.indicadores(dev)
    val = exploracion.sector(Muestra.VALIDACION, motivo=f"{MOTIVO} (sector)", ruta_bitacora=ruta_bitacora)
    indv = exploracion.indicadores(val)
    desde_v = MUESTRAS.validacion_desde
    t["sector"] = pd.concat([tabla_sector(dev, ind, muestra="desarrollo"),
                             tabla_sector(val, indv, muestra="validacion", desde=desde_v)], ignore_index=True)
    t["reglas"] = pd.concat([
        reglas_sector(dev, ind, muestra="desarrollo", registrar=registrar, ruta_bitacora=ruta_bitacora),
        reglas_sector(val, indv, muestra="validacion", desde=desde_v, registrar=registrar, ruta_bitacora=ruta_bitacora),
    ], ignore_index=True)
    b35 = PERFILES["broker_35"]
    paneles = paneles_emisores(construidos, tasa_dividendo=b35.impuesto_dividendo, tasa_efectivo=b35.impuesto_intereses)
    t["emisores"] = tabla_emisores(paneles)
    if panel is None:
        panel, _ = emisores.cargar()
    pd_ = muestras.recortar(panel, Muestra.DESARROLLO, columna="fecha")
    pv = muestras.recortar(panel, Muestra.VALIDACION, columna="fecha", motivo=f"{MOTIVO} (corte transversal)",
                           ruta_bitacora=ruta_bitacora)
    t["transversal"] = pd.concat([
        tabla_transversal(pd_, muestra="desarrollo", hasta=MUESTRAS.desarrollo_hasta, registrar=registrar,
                          ruta_bitacora=ruta_bitacora),
        tabla_transversal(pv, muestra="validacion", desde=MUESTRAS.desarrollo_hasta, registrar=registrar,
                          ruta_bitacora=ruta_bitacora),
    ], ignore_index=True)
    t["hoy"] = pd.concat([hoy_sector(val, indv), hoy_emisores(paneles)], ignore_index=True)
    t["pistas"] = pistas(t["sector"], t["reglas"], t["transversal"])
    b = bitacora.leer(ruta_bitacora).iloc[inicio:]
    notas = {"aperturas_validacion": int((b["prueba"] == "abrir validacion").sum()),
             "intentos_nuevos": int((b["familia"] == FAMILIA).sum()),
             "intentos_extremos": bitacora.intentos(FAMILIA, ruta=ruta_bitacora)}
    return ResultadoExtremos(t, notas)


def guardar(r: ResultadoExtremos, *, raiz: Path | None = None) -> Path:
    from src.investigacion.resultados import DIR_RESULTADOS, _csv, _json

    d = (raiz or DIR_RESULTADOS) / "extremos"
    for nombre, tabla in r.tablas.items():
        if not tabla.empty:
            _csv(tabla, d / f"{nombre}.csv")
    _json(r.notas, d / "notas.json")
    return d


def cargar(raiz: Path | None = None) -> ResultadoExtremos | None:
    from src.investigacion.resultados import DIR_RESULTADOS

    d = (raiz or DIR_RESULTADOS) / "extremos"
    if not d.exists():
        return None
    notas = json.loads((d / "notas.json").read_text(encoding="utf-8")) if (d / "notas.json").exists() else {}
    return ResultadoExtremos({a.stem: pd.read_csv(a) for a in sorted(d.glob("*.csv"))}, notas)


# --------------------------------------------------------------------------------------
# El informe
# --------------------------------------------------------------------------------------


def _pb(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    x = round(float(v) * 1e4)
    return f"{x:+,d}" if x else "0"


def _p(v, d: int = 1) -> str:
    return "—" if v is None or pd.isna(v) else f"{float(v) * 100:.{d}f}%"


def _t(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{float(v):+.2f}"


def _md(filas: list[list[str]], encabezado: list[str]) -> str:
    return ("\n| " + " | ".join(encabezado) + " |\n|" + "|".join("---" for _ in encabezado) + "|\n"
            + "".join("| " + " | ".join(str(c) for c in f) + " |\n" for f in filas) + "\n")


ETIQUETA_MUESTRA = {"desarrollo": "1972-2015", "validacion": "2016 en adelante"}


def informe(r: ResultadoExtremos) -> str:
    o = ["# Los extremos de valuación. Resultados (exploratorio)\n\n",
         "Pre-registro: `extremos_preregistro.md` (commit anterior a esta corrida). Se decidió después de ver todas "
         "las fases: nada de lo que sale aquí se adopta como regla. Generado por "
         "`python scripts/investigacion.py extremos`.\n\n"]
    p = r["pistas"]
    n_pistas = int(p["pista"].sum()) if not p.empty else 0
    o.append(f"## Veredicto\n\n**{n_pistas} de {len(p)} combinaciones** cumplen la regla de lectura pre-registrada "
             "(mismo signo y |t| ≥ 2 en desarrollo y validación; en las reglas, +50 pb y positiva con un mes de "
             "retraso en las dos).")
    if n_pistas:
        o.append(" Las pistas, que solo una prueba nueva con datos nuevos podría confirmar:\n\n"
                 + "".join(f"* {f['prueba']} ({f['nivel']}): {_valor_pista(f)}\n" for _, f in p[p["pista"]].iterrows()))
    elegidas = p[p["pista"]] if n_pistas else p
    if n_pistas and (elegidas["nivel"] == "sector").all() and elegidas["prueba"].str.contains("barato").all():
        o.append("\nCómo leerlas: una t de Newey-West con uno o dos episodios no mide la incertidumbre real —cada "
                 "episodio es una sola crisis que se ve muchos meses seguidos—. Lo que sí dicen es que, en las pocas "
                 "veces en que los REITs llegaron a su 5% más barato contra los bonos (1998-99, 2001-03 y 2008-09 en "
                 "desarrollo, y uno después de 2016), los 12 meses siguientes fueron muy buenos. Eso no se puede "
                 "convertir en una regla de timing "
                 "para quien aporta siempre, porque ya está 100% invertido: a lo más dice que esos son los peores "
                 "momentos para dejar de aportar y los mejores para meter dinero extra.\n")
    o.append("\n\n")
    o.append(_hoy_md(r["hoy"]))
    o.append(_sector_md(r["sector"]))
    o.append(_reglas_md(r["reglas"]))
    o.append(_emisores_md(r["emisores"]))
    o.append(_transversal_md(r["transversal"]))
    o.append(_hipotesis_md(r))
    o.append("## Bitácora y límites\n\n"
             f"Esta corrida abrió la validación {r.notas.get('aperturas_validacion', 0)} veces (sector y corte "
             f"transversal) y agregó {r.notas.get('intentos_nuevos', 0)} evaluaciones con la familia `{FAMILIA}`, que "
             "sí cuentan como intentos. Límites: con percentiles expandibles, el yield del sector, que bajó con los "
             "años, pasa más tiempo en su «extremo caro» que la frecuencia nominal; los extremos del sector son pocos "
             "episodios; en O, NNN y WPC las ventanas de 5 años se enciman y los tres emisores sobrevivieron; en el "
             "corte transversal, un decil son unos 9 emisores por trimestre (unos 4 en el yield contra su historia).\n")
    return "".join(o)


def _valor_pista(f: pd.Series) -> str:
    if f["nivel"] == "regla":
        return f"{_pb(f['desarrollo'])} pb en desarrollo y {_pb(f['validacion'])} pb en validación"
    texto = (f"{_p(f['desarrollo'])} (t {_t(f['t_desarrollo'])}) en desarrollo y {_p(f['validacion'])} "
             f"(t {_t(f['t_validacion'])}) en validación")
    if pd.notna(f.get("episodios_desarrollo", np.nan)):
        texto += (f"; detrás hay {int(f['meses_desarrollo'])} meses en {int(f['episodios_desarrollo'])} episodios en "
                  f"desarrollo y {int(f['meses_validacion'])} meses en {int(f['episodios_validacion'])} episodio(s) en "
                  "validación")
    return texto


def _hoy_md(h: pd.DataFrame) -> str:
    if h.empty:
        return ""
    filas = [[f["senal"], f"{pd.Timestamp(f['fecha']):%m-%Y}", _p(f["percentil"], 0), f["corte"]] for _, f in h.iterrows()]
    return ("## Dónde está hoy\n\nPercentil contra la propia historia (alto = barato).\n"
            + _md(filas, ["Señal", "Fecha", "Percentil", "Corte"]))


def _sector_md(s: pd.DataFrame) -> str:
    if s.empty:
        return ""
    o = ["## 1. El sector\n\nRetorno anualizado de los 60 meses siguientes, antes de impuestos. «Diferencia» es el "
         "exceso sobre el efectivo en el corte menos el del resto de los meses, con su t de Newey-West.\n"]
    for muestra in ("desarrollo", "validacion"):
        d = s[(s["muestra"] == muestra) & (s["horizonte_meses"] == 60)]
        if d.empty:
            continue
        filas = [[f["senal"], f["corte"], str(f["meses"]), _p(f["frecuencia"], 0), str(f["episodios"]),
                  _p(f["reits_mediana"]), _p(f["efectivo_mediana"]), _p(f["efectivo_gana"], 0),
                  _pb(f["diferencia_contra_el_resto"]), _t(f["t"])] for _, f in d.iterrows()]
        o.append(f"\n**{ETIQUETA_MUESTRA[muestra]}**\n"
                 + _md(filas, ["Señal", "Corte", "Meses", "Frecuencia", "Episodios", "REITs", "Efectivo",
                               "Ganó el efectivo", "Diferencia (pb)", "t"]))
    d12 = s[(s["horizonte_meses"] == 12) & s["corte"].isin(EXTREMOS)]
    if not d12.empty:
        filas = [[f["senal"], f["corte"], ETIQUETA_MUESTRA[f["muestra"]], str(f["meses"]), _p(f["reits_mediana"]),
                  _p(f["efectivo_gana"], 0), _pb(f["diferencia_contra_el_resto"]), _t(f["t"])]
                 for _, f in d12.iterrows()]
        o.append("\nA 12 meses, solo los extremos:\n"
                 + _md(filas, ["Señal", "Corte", "Muestra", "Meses", "REITs", "Ganó el efectivo", "Diferencia (pb)",
                               "t"]))
    return "".join(o)


def _reglas_md(rg: pd.DataFrame) -> str:
    if rg.empty:
        return ""
    filas = []
    for (senal, regla, perfil), g in rg.groupby(["senal", "regla", "perfil"], sort=False):
        g = g.set_index("muestra")
        fila = [senal, regla, "SIC" if perfil == "sic" else "Broker 35%"]
        for m in ("desarrollo", "validacion"):
            if m in g.index:
                f = g.loc[m]
                fila += [_pb(f["mejora_rebalanceo"]), _pb(f["mejora_rebalanceo_con_rezago"]),
                         _p(1 - f["exposicion_rebalanceo"], 0)]
            else:
                fila += ["—", "—", "—"]
        filas.append(fila)
    return ("## Las reglas: salir solo en el extremo caro\n\nMejora de TIR contra aportar siempre, rebalanceando, en "
            "pb al año. El criterio de la investigación es +50 pb.\n"
            + _md(filas, ["Señal", "Regla", "Impuestos", "1972-2015 (pb)", "Con retraso (pb)", "Tiempo fuera",
                          "2016+ (pb)", "Con retraso (pb)", "Tiempo fuera"]))


def _emisores_md(e: pd.DataFrame) -> str:
    if e.empty:
        return ""
    o = ["## 2. O, NNN y WPC\n\nRetorno total anualizado de los 5 años siguientes, neto del broker al 35% (44% al "
         "dividendo), en fines de trimestre. Las ventanas independientes son trimestres entre 20.\n"]
    for senal in SENALES_EMISOR:
        d = e[(e["senal"] == senal) & (e["anios"] == 5) & (e["mitad"] == "completo")]
        filas = [[f["alcance"], f["corte"], str(f["trimestres"]), f"{f['ventanas_independientes']:.1f}",
                  _p(f["mediana"]), f"{_p(f['p10'])} a {_p(f['p90'])}", _p(f["efectivo_5a"])]
                 for _, f in d.iterrows()]
        o.append(f"\n**Señal: {'consenso de los siete métodos' if senal == 'consenso' else 'prima sobre el Treasury'}**\n"
                 + _md(filas, ["Emisores", "Corte", "Trimestres", "Ventanas", "Mediana", "p10 a p90",
                               "Efectivo"]))
    d = e[(e["senal"] == "consenso") & (e["anios"] == 5) & (e["alcance"] == "juntos") & (e["mitad"] != "completo")]
    if not d.empty:
        filas = [[f["mitad"], f["corte"], str(f["trimestres"]), _p(f["mediana"])] for _, f in d.iterrows()]
        o.append("\nLas dos mitades (consenso, los tres juntos):\n"
                 + _md(filas, ["Mitad", "Corte", "Trimestres", "Mediana"]))
    return "".join(o)


def _transversal_md(t: pd.DataFrame) -> str:
    if t.empty:
        return ""
    filas = []
    for (senal, corte), g in t.groupby(["senal", "corte"], sort=False):
        g = g.set_index("muestra")
        fila = [fase6.NOMBRES.get(senal, senal), corte]
        for m in ("desarrollo", "validacion"):
            if m in g.index:
                f = g.loc[m]
                fila += [f"{_p(f['exceso_anual'])} (t {_t(f['t'])})",
                         f"{_p(f['recortes'], 0)} / {_p(f['recortes_todos'], 0)}", _pb(f["mejora_tir"])]
            else:
                fila += ["—", "—", "—"]
        filas.append(fila)
    return ("## 3. Todos los REITs de capital: el decil más barato y el más caro\n\nExceso anual bruto contra todos "
            "los elegibles (cohortes de 4 trimestres), recortes del grupo contra los de todos, y la TIR del decil "
            "barato contra aportar a todos con el broker al 35%.\n"
            + _md(filas, ["Señal", "Decil", "Exceso 2011-2015", "Recortes", "TIR (pb)", "Exceso 2016+", "Recortes",
                          "TIR (pb)"]))


def _si(c: bool) -> str:
    return "Se cumple" if c else "No se cumple"


def _hipotesis_md(r: ResultadoExtremos) -> str:
    s, rg, e, t, p = r["sector"], r["reglas"], r["emisores"], r["transversal"], r["pistas"]
    o = ["## Lo que se escribió antes de correr\n\n"]
    if not s.empty:
        c = s[(s["corte"] == "caro 10%") & (s["horizonte_meses"] == 60) & (s["muestra"] == "desarrollo")]
        menor = bool((c["diferencia_contra_el_resto"] < 0).all())
        gana = bool((c["efectivo_gana"] < 0.5).all())
        r10 = rg[rg["regla"] == "fuera en el 10% más caro"]
        sin_50 = not bool(r10.groupby(["senal", "perfil"])["mejora_rebalanceo"].min().ge(CRITERIOS.mejora_minima_de_tir)
                          .any()) if not r10.empty else True
        o.append(f"* **H-E1** (el 10% más caro rinde menos, pero los REITs siguen ganándole al efectivo y salir no llega "
                 f"a +50 pb): {_si(menor and gana and sin_50)}. Rinde menos que el resto con las cuatro señales: "
                 f"{'sí' if menor else 'no'}; el efectivo gana menos de la mitad de las veces: {'sí' if gana else 'no'}; "
                 f"ninguna regla llega a +50 pb en las dos muestras: {'sí' if sin_50 else 'no'}.\n")
        b = s[(s["corte"] == "barato 10%") & (s["horizonte_meses"] == 60) & (s["muestra"] == "desarrollo")]
        mayor = bool((b["diferencia_contra_el_resto"] > 0).all())
        pocos = bool(b["episodios"].between(1, 5).all())
        sin_pista = not bool(p[(p["nivel"] == "sector") & p["prueba"].str.contains("barato 10%")]["pista"].any()) \
            if not p.empty else True
        o.append(f"* **H-E2** (el 10% más barato rinde más, con pocos episodios y sin |t| ≥ 2 en las dos muestras): "
                 f"{_si(mayor and pocos and sin_pista)}. Episodios en desarrollo: "
                 f"{', '.join(str(int(x)) for x in b['episodios'])}.\n")
    if not e.empty:
        j = e[(e["senal"] == "consenso") & (e["anios"] == 5) & (e["alcance"] == "juntos") & (e["mitad"] == "completo")]
        j = j.set_index("corte")
        brecha = j.loc["barato 10%", "mediana"] - j.loc["caro 10%", "mediana"]
        pocas = bool(j.loc[["barato 10%", "caro 10%"], "ventanas_independientes"].lt(5).all())
        o.append(f"* **H-E3** (en O, NNN y WPC el 10% más barato rinde varios puntos más que el 10% más caro, con menos "
                 f"de 5 ventanas): {_si(brecha > 0.02 and pocas)}: {_p(j.loc['barato 10%', 'mediana'])} contra "
                 f"{_p(j.loc['caro 10%', 'mediana'])} al año.\n")
    if not t.empty:
        dv = t[t["senal"] == "rendimiento_del_dividendo"]
        b = dv[dv["corte"] == "barato 10%"].set_index("muestra")
        c = dv[dv["corte"] == "caro 10%"].set_index("muestra")
        recorta = bool((b["recortes"] > b["recortes_todos"]).all())
        no_gana = not bool((b["exceso_anual"] > 0).all())
        caro_pierde = bool(((c["exceso_anual"] < 0) & (c["t"].abs() >= T_MINIMA)).all())
        o.append(f"* **H-E4** (el decil de yield más alto recorta más y no le gana; el más caro no pierde de forma "
                 f"consistente): {_si(recorta and no_gana and not caro_pierde)}.\n")
    if not p.empty:
        n = int(p[p["nivel"].isin(["sector", "transversal"])]["pista"].sum())
        o.append(f"* **H-E5** (ninguna pista en el sector ni en el corte transversal): {_si(n == 0)} ({n} pistas).\n")
    return "".join(o) + "\n"
