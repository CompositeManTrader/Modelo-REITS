"""Análisis de poder: qué tan grande tenía que ser una ventaja para que las pruebas la vieran.

Pre-registro: ``docs/investigacion/poder_preregistro.md``. No prueba reglas nuevas ni escribe
en la bitácora (salvo la apertura de la validación de EE. UU., que el candado anota siempre).

Para cada prueba de cabecera se arma una distribución nula con placebos: reglas sin habilidad
que conservan lo demás de la regla real (cuánto tiempo pasa dentro y cómo cambia, o cuántos
escoge). Su desviación estándar es el error estándar (EE) de la prueba; con una cola al 5% y
potencia de 80%, el efecto mínimo detectable es MDE ≈ 2.49 × EE. Las curvas de potencia
suponen que la habilidad corre la nula (corrimiento de ubicación); una ventaja inyectada en la
tendencia de 10 meses con bootstrap por bloques verifica esa aproximación.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize, stats

from src.investigacion import estadistica, exploracion, fase5, fase6, fase8, muestras
from src.investigacion.diseno import CRITERIOS, MUESTRAS, OBJETIVO, Objetivo
from src.investigacion.muestras import Muestra
from src.investigacion.simulacion import Mercado, Modo, benchmark, simular
from src.simulacion.montecarlo import bootstrap_bloques_multivariado

Z_DETECCION = float(stats.norm.ppf(0.95) + stats.norm.ppf(0.80))      # ≈ 2.49
DELTAS = (0.0025, 0.005, 0.01, 0.015, 0.02, 0.03)
N_PLACEBOS = 500
N_PLACEBOS_SELECCION = 300
N_BOOTSTRAP = 200
SEMILLA = 7
DESPLAZAMIENTO_MINIMO = 24
DELTAS_INYECTADOS = (0.01, 0.02)
REGLAS_TIMING = (("tendencia de 10 meses", "signo"),
                 ("condiciones financieras", "fuera en el quintil peor (20%)"),
                 ("yield contra el Treasury", "fuera en el quintil peor (20%)"))
MOTIVO = "análisis de poder (13-oct-2026): placebos de las mismas reglas, sin probar reglas nuevas"


# --------------------------------------------------------------------------------------
# La nula y su lectura
# --------------------------------------------------------------------------------------


def resumir_nula(prueba: str, muestra: str, observado: float, nula: np.ndarray, *, criterio: float,
                 deltas: tuple[float, ...] = DELTAS) -> tuple[dict, list[dict]]:
    """EE, MDE y curvas de potencia de una prueba a partir de su nula por placebo."""
    nula = np.asarray(nula, dtype=float)
    nula = nula[np.isfinite(nula)]
    ee = float(nula.std(ddof=1))
    centro = float(nula.mean())
    q95 = float(np.quantile(nula - centro, 0.95))
    fila = {"prueba": prueba, "muestra": muestra, "observado": float(observado), "nula_media": centro, "ee": ee,
            "mde": Z_DETECCION * ee, "criterio": criterio, "placebos": int(len(nula)),
            "p_placebo": float((nula >= observado).mean()),
            "habilidad_observada": float(observado) - centro}
    curva = [{"prueba": prueba, "muestra": muestra, "delta": d,
              "potencia_criterio": float((nula + d >= criterio).mean()),
              "potencia_deteccion": float((nula - centro + d > q95).mean())} for d in deltas]
    for c in curva:
        c["inadvertida"] = 1 - c["potencia_deteccion"]
    return fila, curva


def desplazamientos(n: int, k: int, rng: np.random.Generator, minimo: int = DESPLAZAMIENTO_MINIMO) -> np.ndarray:
    if n <= 2 * minimo:
        raise ValueError(f"Con {n} periodos no caben desplazamientos de al menos {minimo}.")
    return rng.integers(minimo, n - minimo + 1, size=k)


def nula_desplazada(m: Mercado, e: np.ndarray, *, objetivo: Objetivo = OBJETIVO, n: int = N_PLACEBOS,
                    semilla: int = SEMILLA) -> tuple[float, np.ndarray]:
    """La mejora de la regla y la de sus placebos: la misma exposición desplazada en el tiempo."""
    e = np.asarray(e, dtype=float)
    base = benchmark(m, objetivo=objetivo).tir
    observado = simular(m, e, modo=Modo.EXPOSICION, objetivo=objetivo).tir - base
    rng = np.random.default_rng(semilla)
    nula = np.array([simular(m, np.roll(e, k), modo=Modo.EXPOSICION, objetivo=objetivo).tir - base
                     for k in desplazamientos(len(e), n, rng)])
    return float(observado), nula


# --------------------------------------------------------------------------------------
# Las pruebas de cabecera
# --------------------------------------------------------------------------------------


def timing_desarrollo(x: pd.DataFrame, ind: pd.DataFrame, *, n: int = N_PLACEBOS, objetivo: Objetivo = OBJETIVO
                      ) -> tuple[list[dict], list[dict]]:
    reglas = {(s.nombre, nombre): e for s, nombre, e in fase5.reglas_del_catalogo(x, ind)}
    m = exploracion.mercado(x)
    filas, curvas = [], []
    for senal, regla in REGLAS_TIMING:
        e = reglas[(senal, regla)].reindex(x.index).to_numpy(dtype=float)
        observado, nula = nula_desplazada(m, e, objetivo=objetivo, n=n)
        f, c = resumir_nula(f"Timing: {senal} | {regla}", "1972-2015", observado, nula,
                            criterio=CRITERIOS.mejora_minima_de_tir)
        f["exposicion"] = float(e.mean())
        filas.append(f)
        curvas += c
    return filas, curvas


def proteccion_validacion(completo: pd.DataFrame, *, n: int = N_PLACEBOS, objetivo: Objetivo = OBJETIVO
                          ) -> tuple[dict, list[dict]]:
    e = fase8.exposicion_tendencia(completo["indice_precio"])
    desde = MUESTRAS.validacion_desde
    x = completo.loc[desde:]
    observado, nula = nula_desplazada(exploracion.mercado(x), e.loc[desde:].to_numpy(dtype=float), objetivo=objetivo,
                                      n=n)
    f, c = resumir_nula("Protección por tendencia, EE. UU.", "2016 en adelante", observado, nula,
                        criterio=-CRITERIOS.costo_maximo_de_la_proteccion)
    f["exposicion"] = float(e.loc[desde:].mean())
    return f, c


def seleccion(panel: pd.DataFrame, *, muestra: str, desde: pd.Timestamp | None = None,
              hasta: pd.Timestamp | None = None, n: int = N_PLACEBOS_SELECCION, objetivo: Objetivo = OBJETIVO,
              semilla: int = SEMILLA) -> tuple[dict, list[dict]]:
    """Momentum contra un tercio de los elegibles escogido al azar cada trimestre."""
    d = fase6.DISENO6
    x = fase6.senales(panel, d)
    desde = desde if desde is not None else fase6.primera_fecha(x, d)
    hasta = hasta if hasta is not None else pd.Timestamp(x["fecha"].max())
    e = x[fase6.elegibles(x, d) & (x["fecha"] >= desde) & (x["fecha"] < hasta)]
    todos = e[["fecha", "cik"]]
    kw = {"desde": desde, "hasta": hasta, "d": d, "respaldo": todos, "objetivo": objetivo}
    tir_todos = fase6.simular(todos, x, **kw).tir
    f = fase6.evaluar("momentum", x, desde=desde, hasta=hasta, muestra=muestra, d=d, registrar=False,
                      objetivo=objetivo)
    rng = np.random.default_rng(semilla)
    nula = np.array([fase6.simular(todos.groupby("fecha").sample(frac=1 / d.grupos,
                                                                 random_state=int(rng.integers(2**31))),
                                   x, **kw).tir - tir_todos for _ in range(n)])
    fila, curva = resumir_nula("Selección: momentum", muestra, f["mejora"], nula, criterio=CRITERIOS.mejora_minima_de_tir)
    exceso = f["_exceso_trimestral"]
    fila.update({"exceso_anual": f["exceso_anual"], "trimestres": int(len(exceso)),
                 "ee_exceso_nw": 4 * estadistica.error_estandar_nw(exceso.to_numpy(), d.rezago_nw)})
    fila["mde_exceso_nw"] = Z_DETECCION * fila["ee_exceso_nw"]
    return fila, curva


def asignacion(construidos: dict, *, n: int = N_PLACEBOS, parametros=None) -> tuple[dict, list[dict]]:
    """La nula de la asignación entre O, NNN y WPC: elecciones al azar con las rachas del consenso."""
    from src.estudio import macro, metodos
    from src.estudio import reglas as rg

    parametros = parametros or rg.PARAMETROS
    tbill, baa, cpi = rg.cargar_tbill(), macro.cargar("baa"), macro.cargar("cpi")
    paneles = {t: metodos.panel(e, baa=baa, cpi=cpi, tbill=tbill) for t, e in construidos.items()}
    m = metodos.mercado_comun(construidos)
    a = metodos.asignar(m, paneles, "consenso", n_azar=n, semilla=SEMILLA, parametros=parametros)
    return resumir_nula("Asignación entre O, NNN y WPC: consenso", f"{a.desde:%Y}-{a.hasta:%Y}", a.ventaja, a.azar,
                        criterio=0.0)


def sharpe_necesario(r: np.ndarray, *, intentos: int, varianza_de_sharpes: float, objetivo: float = 0.95) -> float:
    """El Sharpe por periodo que habría llevado el Sharpe deflactado a ``objetivo`` con la misma
    asimetría, curtosis y largo de la serie."""
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    n = len(r)
    sr0 = estadistica.sharpe_maximo_esperado(intentos, varianza_de_sharpes)
    g3, g4 = float(stats.skew(r)), float(stats.kurtosis(r, fisher=False))

    def falta(sr: float) -> float:
        denominador = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr**2))
        return stats.norm.cdf((sr - sr0) * math.sqrt(n - 1) / denominador) - objetivo

    try:
        return float(optimize.brentq(falta, sr0, sr0 + 20))
    except ValueError:
        return np.nan


def dsr_fase5(x: pd.DataFrame, ind: pd.DataFrame) -> dict:
    from src.investigacion import timing

    matriz = pd.DataFrame({f"{s.nombre} | {nombre}": timing.retornos_de_la_regla(e, x)
                           for s, nombre, e in fase5.reglas_del_catalogo(x, ind)})
    return _dsr("Fase 5: la mejor regla de entrada", matriz, intentos=len(matriz.columns), por_anio=12)


def dsr_fase6(panel_desarrollo: pd.DataFrame, *, intentos: int) -> dict:
    d = fase6.DISENO6
    x = fase6.senales(panel_desarrollo, d)
    desde, hasta = fase6.primera_fecha(x, d), MUESTRAS.desarrollo_hasta
    matriz = pd.DataFrame({r: fase6.evaluar(r, x, desde=desde, hasta=hasta, muestra="desarrollo", d=d,
                                            registrar=False)["_exceso_trimestral"] for r in fase6.REGLAS})
    return _dsr("Fase 6: la mejor regla de selección", matriz, intentos=intentos, por_anio=4)


def _dsr(prueba: str, matriz: pd.DataFrame, *, intentos: int, por_anio: int) -> dict:
    sharpes = matriz.apply(lambda c: estadistica.sharpe(c.dropna().to_numpy()))
    mejor = str(sharpes.idxmax())
    r = matriz[mejor].dropna().to_numpy()
    varianza = float(sharpes.var())
    necesario = sharpe_necesario(r, intentos=intentos, varianza_de_sharpes=varianza)
    return {"prueba": prueba, "mejor": mejor, "periodos": int(len(r)), "intentos": intentos,
            "sharpe_observado_anual": float(sharpes[mejor] * math.sqrt(por_anio)),
            "sharpe_necesario_anual": float(necesario * math.sqrt(por_anio)),
            "sharpe_deflactado": estadistica.sharpe_deflactado(r, intentos=intentos, varianza_de_sharpes=varianza)}


# --------------------------------------------------------------------------------------
# Verificación con ventaja inyectada
# --------------------------------------------------------------------------------------


def inyeccion(x: pd.DataFrame, e: pd.Series, *, deltas: tuple[float, ...] = DELTAS_INYECTADOS, n: int = N_BOOTSTRAP,
              semilla: int = SEMILLA, objetivo: Objetivo = OBJETIVO, bloque: int = 12) -> pd.DataFrame:
    """Qué fracción de las muestras con una habilidad conocida pasa los criterios de retorno.

    La ventaja se suma al retorno de cada mes según la exposición decidida el mes anterior,
    centrada: a·(e[t−1] − ē). Así aportar siempre no la cobra y la habilidad contra una regla
    sin habilidad con la misma exposición es ≈ 12·a·var(e) al año, que se fija en δ.
    """
    df = pd.DataFrame({"precio": x["retorno_precio"], "ingreso": x["retorno_ingreso"], "efectivo": x["efectivo"],
                       "e": e.reindex(x.index)}).dropna()
    fechas = df.index
    ebar, var = float(df["e"].mean()), float(df["e"].var())
    mitad = len(fechas) // 2
    rng = np.random.default_rng(semilla)
    filas = []
    for delta in (0.0, *deltas):
        a = delta / (12 * var)
        mejoras, filtro, cincuenta = [], [], []
        for _ in range(n):
            b = bootstrap_bloques_multivariado(df, len(df), tamano_bloque=bloque, rng=rng)
            eb = b["e"].to_numpy()
            previa = np.r_[ebar, eb[:-1]]
            m = Mercado(fechas, b["precio"].to_numpy() + a * (previa - ebar), b["ingreso"].to_numpy(),
                        b["efectivo"].to_numpy())
            base = benchmark(m, objetivo=objetivo).tir
            r = simular(m, eb, modo=Modo.EXPOSICION, objetivo=objetivo)
            fija = simular(m, r.exposicion_promedio, modo=Modo.EXPOSICION, objetivo=objetivo).tir
            rezago = simular(m, eb, modo=Modo.EXPOSICION, rezago=1, objetivo=objetivo).tir
            caro = simular(m, eb, modo=Modo.EXPOSICION, multiplicador_de_costos=CRITERIOS.multiplicador_de_costos,
                           objetivo=objetivo).tir
            mitades = []
            for tramo, ex in ((m.tramo(hasta=fechas[mitad - 1]), eb[:mitad]), (m.tramo(desde=fechas[mitad]), eb[mitad:])):
                mitades.append(simular(tramo, ex, modo=Modo.EXPOSICION, objetivo=objetivo).tir
                               - benchmark(tramo, objetivo=objetivo).tir)
            mejora = r.tir - base
            mejoras.append(mejora)
            filtro.append(mejora > 0 and r.tir > fija and rezago > base and caro > base and min(mitades) > 0)
            cincuenta.append(mejora >= CRITERIOS.mejora_minima_de_tir)
        filas.append({"delta": delta, "muestras": n, "mejora_mediana": float(np.median(mejoras)),
                      "pasa_criterios_de_retorno": float(np.mean(filtro)), "pasa_50pb": float(np.mean(cincuenta)),
                      "pasa_ambos": float(np.mean(np.array(filtro) & np.array(cincuenta)))})
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# Todo junto
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoPoder:
    tablas: dict[str, pd.DataFrame]
    notas: dict = field(default_factory=dict)

    def __getitem__(self, nombre: str) -> pd.DataFrame:
        return self.tablas.get(nombre, pd.DataFrame())


def correr(*, ruta_bitacora=None, construidos: dict | None = None, panel: pd.DataFrame | None = None,
           n: int = N_PLACEBOS, n_seleccion: int = N_PLACEBOS_SELECCION, n_bootstrap: int = N_BOOTSTRAP,
           intentos_fase6: int | None = None) -> ResultadoPoder:
    from src.estudio import estudio
    from src.investigacion import emisores, resultados

    filas, curvas = [], []
    x = exploracion.sector(Muestra.DESARROLLO)
    ind = exploracion.indicadores(x)
    f, c = timing_desarrollo(x, ind, n=n)
    filas += f
    curvas += c
    completo = exploracion.sector(Muestra.VALIDACION, motivo=f"{MOTIVO} (fase 8)", ruta_bitacora=ruta_bitacora)
    f, c = proteccion_validacion(completo, n=n)
    filas.append(f)
    curvas += c
    if panel is None:
        panel, _ = emisores.cargar()
    dev = muestras.recortar(panel, Muestra.DESARROLLO, columna="fecha")
    val = muestras.recortar(panel, Muestra.VALIDACION, columna="fecha", motivo=f"{MOTIVO} (fase 6)",
                            ruta_bitacora=ruta_bitacora)
    for p, muestra, desde, hasta in ((dev, "desarrollo", None, MUESTRAS.desarrollo_hasta),
                                     (val, "validacion", MUESTRAS.desarrollo_hasta, None)):
        f, c = seleccion(p, muestra=muestra, desde=desde, hasta=hasta, n=n_seleccion)
        filas.append(f)
        curvas += c
    construidos = construidos or {t: estudio.armar_versionado(t) for t in ("NNN", "O", "WPC")}
    f, c = asignacion(construidos, n=n)
    filas.append(f)
    curvas += c
    if intentos_fase6 is None:
        r6 = resultados.cargar().get("fase6", {}).get("resumen", {})
        intentos_fase6 = int(r6.get("intentos", len(fase6.REGLAS)))
    dsr = pd.DataFrame([dsr_fase5(x, ind), dsr_fase6(dev, intentos=intentos_fase6)])
    tendencia = {(s.nombre, nombre): e for s, nombre, e in fase5.reglas_del_catalogo(x, ind)}[REGLAS_TIMING[0]]
    t = {"errores": pd.DataFrame(filas), "curvas": pd.DataFrame(curvas), "dsr": dsr,
         "inyeccion": inyeccion(x, tendencia, n=n_bootstrap)}
    techo = resultados.cargar().get("fase3", {}).get("techo")
    notas = {"z_deteccion": Z_DETECCION, "semilla": SEMILLA}
    if techo is not None:
        o = techo[(techo["regla"] == "oráculo de los 12 meses siguientes") & (techo["modo"] == "rebalancea")]
        notas["techo_oraculo_12m_pb"] = int(o["contra_aportar_siempre_bps"].iloc[0]) if len(o) else None
    return ResultadoPoder(t, notas)


def guardar(r: ResultadoPoder, *, raiz: Path | None = None) -> Path:
    from src.investigacion.resultados import DIR_RESULTADOS, _csv, _json

    d = (raiz or DIR_RESULTADOS) / "poder"
    for nombre, tabla in r.tablas.items():
        if not tabla.empty:
            _csv(tabla, d / f"{nombre}.csv")
    _json(r.notas, d / "notas.json")
    return d


def cargar(raiz: Path | None = None) -> ResultadoPoder | None:
    from src.investigacion.resultados import DIR_RESULTADOS

    d = (raiz or DIR_RESULTADOS) / "poder"
    if not d.exists():
        return None
    notas = json.loads((d / "notas.json").read_text(encoding="utf-8")) if (d / "notas.json").exists() else {}
    return ResultadoPoder({a.stem: pd.read_csv(a) for a in sorted(d.glob("*.csv"))}, notas)


# --------------------------------------------------------------------------------------
# El informe
# --------------------------------------------------------------------------------------


def _pb(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    x = round(float(v) * 1e4)
    return f"{x:+,d}" if x else "0"


def _pba(v) -> str:
    """Puntos base sin signo (un error estándar, un MDE)."""
    return "—" if v is None or pd.isna(v) else f"{abs(round(float(v) * 1e4)):,d}"


def _p(v, d: int = 0) -> str:
    return "—" if v is None or pd.isna(v) else f"{float(v) * 100:.{d}f}%"


def _md(filas: list[list[str]], encabezado: list[str]) -> str:
    return ("\n| " + " | ".join(encabezado) + " |\n|" + "|".join("---" for _ in encabezado) + "|\n"
            + "".join("| " + " | ".join(str(c) for c in f) + " |\n" for f in filas) + "\n")


def inadvertida(r: ResultadoPoder, prueba: str, muestra: str, delta: float) -> float:
    c = r["curvas"]
    f = c[(c["prueba"] == prueba) & (c["muestra"] == muestra) & np.isclose(c["delta"], delta)]
    return float(f["inadvertida"].iloc[0]) if len(f) else np.nan


def informe(r: ResultadoPoder) -> str:
    e = r["errores"]
    o = ["# Análisis de poder. Resultados\n\n",
         "Pre-registro: `poder_preregistro.md` (commit anterior a esta corrida). ¿Las pruebas podían ver una ventaja "
         "real? Para cada prueba de cabecera, una distribución nula con placebos —reglas sin habilidad con el mismo "
         "perfil— da su error estándar (EE) y su efecto mínimo detectable (MDE ≈ 2.49 × EE, una cola al 5% y potencia "
         "de 80%). Generado por `python scripts/investigacion.py poder`.\n\n"]
    o.append("## Veredicto\n\n")
    filas = []
    for _, f in e.iterrows():
        filas.append([f["prueba"], f["muestra"], _pb(f["observado"]), _pb(f["nula_media"]), _pba(f["ee"]),
                      _pba(f["mde"]), _pb(f["habilidad_observada"]),
                      _p(inadvertida(r, f["prueba"], f["muestra"], 0.01)),
                      _p(inadvertida(r, f["prueba"], f["muestra"], 0.02))])
    o.append(_md(filas, ["Prueba", "Muestra", "Observado (pb)", "Placebo promedio (pb)", "EE (pb)", "MDE (pb)",
                         "Observado − placebo (pb)", "100 pb pasarían inadvertidos", "200 pb pasarían inadvertidos"]))
    techo = r.notas.get("techo_oraculo_12m_pb")
    if techo:
        o.append(f"El oráculo que conoce los 12 meses siguientes ganó +{techo} pb al año rebalanceando (fase 3): es el "
                 "techo de cualquier regla de timing. Un MDE cerca de ese techo quiere decir que la prueba solo podía "
                 "ver ventajas casi imposibles.\n\n")
    o.append(_curvas_md(r))
    o.append(_dsr_md(r["dsr"]))
    o.append(_inyeccion_md(r["inyeccion"]))
    o.append(_hipotesis_md(r))
    o.append("## Cómo se lee\n\n"
             "* «Observado − placebo» es la habilidad que mostró la regla real contra reglas sin habilidad con el mismo "
             "perfil; el «placebo promedio» es lo que cuesta, en promedio, estar fuera o escoger a ciegas.\n"
             "* Un resultado negativo de una prueba con un MDE de 300 pb no descarta una ventaja de 100 pb: solo "
             "descarta una ventaja grande y confiable.\n"
             "* Las curvas suponen que la habilidad corre la nula sin cambiar su forma. La verificación con ventaja "
             "inyectada en la tendencia de 10 meses dice qué tan buena es esa aproximación.\n"
             "* Los placebos usan la contabilidad del SIC (la línea base); con el broker el ruido es casi el mismo.\n")
    return "".join(o)


def _curvas_md(r: ResultadoPoder) -> str:
    c = r["curvas"]
    if c.empty:
        return ""
    filas = []
    for (prueba, muestra), g in c.groupby(["prueba", "muestra"], sort=False):
        g = g.set_index("delta")
        filas.append([prueba, muestra, *[_p(g.loc[d, "potencia_deteccion"]) for d in DELTAS]])
    return ("## Curvas de potencia\n\nProbabilidad de distinguir del azar, al 5%, una regla con una habilidad "
            "verdadera de δ al año sobre una regla sin habilidad con el mismo perfil.\n"
            + _md(filas, ["Prueba", "Muestra", *[f"δ = {round(d * 1e4)} pb" for d in DELTAS]]))


def _dsr_md(d: pd.DataFrame) -> str:
    if d.empty:
        return ""
    filas = [[f["prueba"], f["mejor"], str(f["periodos"]), str(f["intentos"]), f"{f['sharpe_observado_anual']:.2f}",
              f"{f['sharpe_necesario_anual']:.2f}", f"{f['sharpe_deflactado']:.2f}"] for _, f in d.iterrows()]
    return ("## El Sharpe deflactado\n\nEl Sharpe anual de la mejor regla contra el que habría hecho falta para un "
            "Sharpe deflactado de 0.95, con los mismos intentos, la misma varianza de Sharpes y la misma forma de la "
            "serie.\n"
            + _md(filas, ["Prueba", "Mejor regla", "Periodos", "Intentos", "Sharpe observado", "Sharpe necesario",
                          "Sharpe deflactado"]))


def _inyeccion_md(d: pd.DataFrame) -> str:
    if d.empty:
        return ""
    filas = [[f"{round(f['delta'] * 1e4)}", _pb(f["mejora_mediana"]), _p(f["pasa_criterios_de_retorno"]),
              _p(f["pasa_50pb"]), _p(f["pasa_ambos"])] for _, f in d.iterrows()]
    return ("## Verificación: una ventaja inyectada en la tendencia de 10 meses\n\nSe le suma a la tendencia una "
            "habilidad conocida y se remuestrea 1972-2015 con bootstrap por bloques de 12 meses. ¿Qué fracción de las "
            "muestras pasa los criterios de retorno del filtro de la fase 5 (le gana a aportar siempre y a la mezcla "
            "fija, con un mes de retraso, con doble costo y en las dos mitades) y el +50 pb? La predictibilidad queda "
            "fuera: es un techo de la potencia real.\n"
            + _md(filas, ["Habilidad inyectada (pb)", "Mejora mediana (pb)", "Pasa los criterios de retorno",
                          "Pasa +50 pb", "Pasa los dos"]))


def _si(c: bool) -> str:
    return "Se cumple" if c else "No se cumple"


def _hipotesis_md(r: ResultadoPoder) -> str:
    e = r["errores"]
    o = ["## Lo que se escribió antes de correr\n\n"]
    t = e[e["prueba"].str.startswith("Timing")]
    if not t.empty:
        o.append(f"* **H-P1** (EE del timing entre 50 y 150 pb): {_si(bool(t['ee'].between(0.005, 0.015).all()))}: "
                 + ", ".join(f"{_pba(x)} pb" for x in t["ee"]) + ".\n")
    s = e[e["prueba"].str.startswith("Selección")]
    if not s.empty:
        o.append(f"* **H-P2** (EE de la selección entre 100 y 250 pb y MDE de más de 250 pb): "
                 f"{_si(bool(s['ee'].between(0.01, 0.025).all() and (s['mde'] > 0.025).all()))}: EE de "
                 + " y ".join(f"{_pba(x)} pb" for x in s["ee"]) + ".\n")
    a = e[e["prueba"].str.startswith("Asignación")]
    if not a.empty:
        ee = float(a["ee"].iloc[0])
        minimo = bool(ee <= e["ee"].min() + 1e-12)
        o.append(f"* **H-P3** (EE de la asignación entre 20 y 60 pb, el más fino de todos): "
                 f"{_si(0.002 <= ee <= 0.006 and minimo)}: {_pba(ee)} pb.\n")
    d = r["dsr"]
    if not d.empty and d["prueba"].str.contains("Fase 6").any():
        f = d[d["prueba"].str.contains("Fase 6")].iloc[0]
        o.append(f"* **H-P4** (el Sharpe necesario en la fase 6 está muy arriba del observado): "
                 f"{_si(f['sharpe_necesario_anual'] > 2 * f['sharpe_observado_anual'])}: hacía falta "
                 f"{f['sharpe_necesario_anual']:.2f} y se observó {f['sharpe_observado_anual']:.2f}.\n")
    return "".join(o) + "\n"
