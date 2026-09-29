"""Las tablas de los métodos de valuación tal como se muestran en pantalla y en el PDF.

Como en ``vistas_reglas``: la aplicación decide la unidad de cada columna por su nombre
(``app/comun.familia_de_columna``), así que cada vista declara sus columnas y la prueba 53
verifica que ninguna columna de fracciones caiga fuera de «porcentaje».
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.estudio.graficas import mes
from src.estudio.metodos import METODOS, NOMBRE, ResultadoMetodos, trimestral

COLUMNAS: dict[str, tuple[str, ...]] = {
    "metodos": ("metodo", "descripcion"),
    "juntos": (
        "metodo", "correlacion_1_anio", "correlacion_5_anios", "rendimiento_5a_barato",
        "rendimiento_5a_caro", "brecha_barato_caro", "emisores_a_favor", "ventanas_independientes",
    ),
    "por_emisor": (
        "metodo", "trimestres", "correlacion_1_anio", "correlacion_3_anios", "correlacion_5_anios",
        "rendimiento_5a_barato", "rendimiento_5a_medio", "rendimiento_5a_caro", "brecha_barato_caro",
        "correlacion_5a_primera_mitad", "correlacion_5a_segunda_mitad",
    ),
    "esperar": (
        "metodo", "rendimiento_5a_caro", "brecha_caro_vs_efectivo", "fraccion_caro_arriba_del_efectivo",
        "tir_con_el_metodo", "tir_sin_reglas", "ventaja_tir_bps", "fraccion_en_el_papel",
    ),
    "asignacion": (
        "metodo", "desde", "tir_con_el_metodo", "tir_partes_iguales", "ventaja_tir_bps",
        "ventaja_al_mas_caro_bps", "ventaja_primera_mitad_bps", "ventaja_segunda_mitad_bps",
        "fraccion_del_azar_que_la_iguala", "cambios_de_emisor", "meses_en_cada_uno", "hoy_va_a",
    ),
    "trimestres": (
        "trimestre", "precio", "flujo_por_accion", "multiplo_flujo", "yield_flujo", "yield_dividendo",
        "tasa_treasury_10a", "inflacion_12m", "tasa_real", "tasa_baa",
        *(f"percentil_{m.clave}" for m in METODOS),
        "senal_consenso", "rendimiento_1a_despues", "rendimiento_5a_despues",
    ),
}
ENCABEZADOS = {f"percentil_{m.clave}": f"Percentil: {m.nombre}" for m in METODOS}


def _con(df: pd.DataFrame, clave: str) -> pd.DataFrame:
    faltan = [c for c in COLUMNAS[clave] if c not in df.columns]
    if faltan:
        raise KeyError(f"La vista «{clave}» perdió columnas: {faltan}")
    return df[list(COLUMNAS[clave])].reset_index(drop=True)


def _bps(x) -> float:
    return round(float(x) * 1e4) if pd.notna(x) else np.nan


def metodos() -> pd.DataFrame:
    return _con(pd.DataFrame({"metodo": [m.nombre for m in METODOS],
                              "descripcion": [m.descripcion for m in METODOS]}), "metodos")


def juntos(r: ResultadoMetodos) -> pd.DataFrame:
    j = r.juntos
    return _con(pd.DataFrame({
        "metodo": j["metodo"],
        "correlacion_1_anio": j["rho_1a"].round(2), "correlacion_5_anios": j["rho_5a"].round(2),
        "rendimiento_5a_barato": j["r5_barato"], "rendimiento_5a_caro": j["r5_caro"],
        "brecha_barato_caro": j["r5_barato_menos_caro"],
        "emisores_a_favor": [f"{int(x)} de {len(r.paneles)}" for x in j["emisores_con_rho_5a_positiva"]],
        "ventanas_independientes": j["ventanas_5a"],
    }), "juntos")


def por_emisor(r: ResultadoMetodos, ticker: str) -> pd.DataFrame:
    e = r.evaluaciones[ticker]
    return _con(pd.DataFrame({
        "metodo": e["metodo"], "trimestres": e["trimestres"].astype(int),
        "correlacion_1_anio": e["rho_1a"].round(2), "correlacion_3_anios": e["rho_3a"].round(2),
        "correlacion_5_anios": e["rho_5a"].round(2),
        "rendimiento_5a_barato": e["r5_barato"], "rendimiento_5a_medio": e["r5_medio"],
        "rendimiento_5a_caro": e["r5_caro"], "brecha_barato_caro": e["r5_barato_menos_caro"],
        "correlacion_5a_primera_mitad": e["rho_5a_primera_mitad"].round(2),
        "correlacion_5a_segunda_mitad": e["rho_5a_segunda_mitad"].round(2),
    }), "por_emisor")


def esperar(r: ResultadoMetodos, ticker: str) -> pd.DataFrame:
    e, b = r.evaluaciones[ticker], r.backtests[ticker]
    return _con(pd.DataFrame({
        "metodo": e["metodo"], "rendimiento_5a_caro": e["r5_caro"],
        "brecha_caro_vs_efectivo": e["caro_contra_efectivo"],
        "fraccion_caro_arriba_del_efectivo": e["caro_le_gana_al_efectivo"],
        "tir_con_el_metodo": b["tir_usd"], "tir_sin_reglas": b["tir_sin_reglas"],
        "ventaja_tir_bps": [_bps(x) for x in b["ventaja_tir"]],
        "fraccion_en_el_papel": b["exposicion"],
    }), "esperar")


def asignacion(r: ResultadoMetodos) -> pd.DataFrame:
    t = r.asignacion()
    meses = [" · ".join(f"{k} {int(t.loc[c, f'meses_{k}'])}" for k in r.paneles) for c in t.index]
    return _con(pd.DataFrame({
        "metodo": t["metodo"], "desde": [mes(f) for f in t["desde"]],
        "tir_con_el_metodo": t["tir_usd"], "tir_partes_iguales": t["tir_partes_iguales"],
        "ventaja_tir_bps": [_bps(x) for x in t["ventaja"]],
        "ventaja_al_mas_caro_bps": [_bps(x) for x in t["ventaja_el_mas_caro"]],
        "ventaja_primera_mitad_bps": [_bps(x) for x in t["ventaja_primera_mitad"]],
        "ventaja_segunda_mitad_bps": [_bps(x) for x in t["ventaja_segunda_mitad"]],
        "fraccion_del_azar_que_la_iguala": t["azar_que_le_gana"],
        "cambios_de_emisor": t["cambios"].astype(int),
        "meses_en_cada_uno": meses, "hoy_va_a": t["eleccion_hoy"],
    }), "asignacion")


def hoy(r: ResultadoMetodos) -> pd.DataFrame:
    """Método × emisor: la señal y el percentil de hoy, en texto."""
    h = r.hoy()
    tabla = pd.DataFrame({"metodo": [m.nombre for m in METODOS]})
    for t in r.paneles:
        x = h[h["emisor"] == t].set_index("clave")
        tabla[t] = [f"{x.loc[m.clave, 'senal']} · {x.loc[m.clave, 'percentil']:.0%}"
                    if pd.notna(x.loc[m.clave, "percentil"]) else "sin dato" for m in METODOS]
    return tabla


def trimestres(r: ResultadoMetodos, ticker: str) -> pd.DataFrame:
    """El panel de cada fin de trimestre, del más reciente al más viejo."""
    q = trimestral(r.paneles[ticker]).dropna(subset=["precio"])
    d = pd.DataFrame({
        "trimestre": [f"{f.year}-T{(f.month - 1) // 3 + 1}" for f in q.index],
        "precio": q["precio"], "flujo_por_accion": q["flujo"], "multiplo_flujo": q["multiplo_flujo"],
        "yield_flujo": q["yield_flujo"], "yield_dividendo": q["yield_dividendo"],
        "tasa_treasury_10a": q["treasury_10a"], "inflacion_12m": q["inflacion_12m"],
        "tasa_real": q["tasa_real"], "tasa_baa": q["baa"],
        **{f"percentil_{m.clave}": q[f"p_{m.clave}"] for m in METODOS},
        "senal_consenso": q["s_consenso"],
        "rendimiento_1a_despues": q["adelante_1a"], "rendimiento_5a_despues": q["adelante_5a"],
    }, index=q.index)
    return _con(d.iloc[::-1], "trimestres")


def asignacion_trimestral(r: ResultadoMetodos) -> pd.DataFrame:
    """Cada fin de trimestre: el consenso de cada emisor y a cuál iría la aportación."""
    pcs = pd.DataFrame({t: trimestral(p)["p_consenso"] for t, p in r.paneles.items()}).dropna(how="all")
    elegido = pcs.idxmax(axis=1)
    d = pd.DataFrame({"trimestre": [f"{f.year}-T{(f.month - 1) // 3 + 1}" for f in pcs.index]}, index=pcs.index)
    for t in pcs.columns:
        d[f"percentil_{t.lower()}"] = pcs[t]
    d["la_aportacion_va_a"] = elegido.where(pcs.notna().all(axis=1), "—")
    return d.iloc[::-1].reset_index(drop=True)


VISTAS = {"por_emisor": por_emisor, "esperar": esperar, "trimestres": trimestres}
NOMBRE_METODO = NOMBRE
