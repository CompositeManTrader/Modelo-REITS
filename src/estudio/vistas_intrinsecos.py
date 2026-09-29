"""Las tablas de los modelos de valor intrínseco (DDM, DCF, crecimiento implícito, NAV).

Como en las otras vistas: la unidad de cada columna sale de su nombre
(``app/comun.familia_de_columna``), y la prueba 54 verifica que ninguna fracción caiga
fuera de «porcentaje».
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.estudio.graficas import mes
from src.estudio.intrinsecos import INTRINSECOS, NOMBRES, SUPUESTOS, ResultadoIntrinsecos
from src.estudio.metodos import tabla_asignaciones, trimestral

COLUMNAS: dict[str, tuple[str, ...]] = {
    "modelos": ("metodo", "descripcion"),
    "hoy": ("emisor", "metodo", "precio", "valor_por_accion", "descuento_del_precio", "senal_absoluta",
            "percentil", "senal_contra_su_historia"),
    "evaluacion": ("metodo", "senal", "correlacion_1_anio", "correlacion_5_anios", "rendimiento_5a_barato",
                   "rendimiento_5a_caro", "brecha_barato_caro", "fraccion_barato", "fraccion_caro",
                   "emisores_a_favor", "ventanas_independientes"),
    "backtest": ("metodo", "tir_con_percentil", "tir_con_senal_absoluta", "tir_sin_reglas",
                 "ventaja_percentil_bps", "ventaja_absoluta_bps"),
    "sensibilidad": ("emisor", "metodo", "fraccion_barato_prima_2", "fraccion_barato_prima_3",
                     "fraccion_barato_prima_4", "ventaja_prima_2_bps", "ventaja_prima_3_bps", "ventaja_prima_4_bps"),
    "asignacion": ("metodo", "senal", "desde", "tir_con_el_metodo", "tir_partes_iguales", "ventaja_tir_bps",
                   "ventaja_al_mas_caro_bps", "ventaja_primera_mitad_bps", "ventaja_segunda_mitad_bps",
                   "fraccion_del_azar_que_la_iguala", "meses_en_cada_uno"),
    "validacion": ("emisor", "anio", "veces_deuda_neta_armada", "veces_reportadas", "diferencia_relativa",
                   "se_usa"),
    "trimestres": ("trimestre", "precio", "tasa_de_descuento", "crecimiento_dividendo_5a", "valor_ddm_por_accion",
                   "crecimiento_flujo_5a", "valor_dcf_por_accion", "crecimiento_implicito",
                   "noi_anualizado_millones", "cap_rate", "deuda_neta_millones", "nav_por_accion",
                   "descuento_ddm", "descuento_dcf", "brecha_de_crecimiento", "descuento_nav"),
}


def _con(df: pd.DataFrame, clave: str) -> pd.DataFrame:
    faltan = [c for c in COLUMNAS[clave] if c not in df.columns]
    if faltan:
        raise KeyError(f"La vista «{clave}» perdió columnas: {faltan}")
    return df[list(COLUMNAS[clave])].reset_index(drop=True)


def _bps(x) -> float:
    return round(float(x) * 1e4) if pd.notna(x) else np.nan


def modelos() -> pd.DataFrame:
    return _con(pd.DataFrame({"metodo": [m.nombre for m in INTRINSECOS],
                              "descripcion": [m.descripcion for m in INTRINSECOS]}), "modelos")


def hoy(ri: ResultadoIntrinsecos) -> pd.DataFrame:
    h = ri.hoy()
    return _con(h.rename(columns={"valor_contra_precio": "descuento_del_precio",
                                  "senal_percentil": "senal_contra_su_historia"}), "hoy")


def evaluacion(ri: ResultadoIntrinsecos) -> pd.DataFrame:
    filas = []
    for senal, j in (("contra su historia", ri.juntos_percentil), ("absoluta", ri.juntos_absoluta)):
        for clave, f in j.iterrows():
            fr = pd.concat({t: (ri.percentil if senal != "absoluta" else ri.absoluta)[t].loc[clave]
                            for t in ri.paneles}, axis=1).T
            filas.append({
                "metodo": NOMBRES[clave], "senal": senal,
                "correlacion_1_anio": round(float(f["rho_1a"]), 2) if pd.notna(f["rho_1a"]) else np.nan,
                "correlacion_5_anios": round(float(f["rho_5a"]), 2) if pd.notna(f["rho_5a"]) else np.nan,
                "rendimiento_5a_barato": f["r5_barato"], "rendimiento_5a_caro": f["r5_caro"],
                "brecha_barato_caro": f["r5_barato_menos_caro"],
                "fraccion_barato": float(fr["fraccion_barato"].astype(float).mean()),
                "fraccion_caro": float(fr["fraccion_caro"].astype(float).mean()),
                "emisores_a_favor": f"{int(f['emisores_con_rho_5a_positiva'])} de {len(ri.paneles)}",
                "ventanas_independientes": f["ventanas_5a"],
            })
    return _con(pd.DataFrame(filas), "evaluacion")


def backtest(ri: ResultadoIntrinsecos, ticker: str) -> pd.DataFrame:
    p, a = ri.backtest_percentil[ticker], ri.backtest_absoluta[ticker]
    return _con(pd.DataFrame({
        "metodo": [NOMBRES[k] for k in p.index],
        "tir_con_percentil": p["tir_usd"].to_numpy(), "tir_con_senal_absoluta": a["tir_usd"].to_numpy(),
        "tir_sin_reglas": p["tir_sin_reglas"].to_numpy(),
        "ventaja_percentil_bps": [_bps(x) for x in p["ventaja_tir"]],
        "ventaja_absoluta_bps": [_bps(x) for x in a["ventaja_tir"]],
    }), "backtest")


def sensibilidad(ri: ResultadoIntrinsecos) -> pd.DataFrame:
    s = ri.sensibilidad
    filas = []
    for (t, clave), g in s.groupby(["emisor", "clave"], sort=False):
        g = g.set_index("prima")
        fila = {"emisor": t, "metodo": NOMBRES[clave]}
        for prima in SUPUESTOS.primas_de_sensibilidad:
            n = round(prima * 100)
            fila[f"fraccion_barato_prima_{n}"] = g.loc[prima, "fraccion_barato"]
            fila[f"ventaja_prima_{n}_bps"] = _bps(g.loc[prima, "ventaja_tir"])
        filas.append(fila)
    return _con(pd.DataFrame(filas), "sensibilidad")


def asignacion(ri: ResultadoIntrinsecos) -> pd.DataFrame:
    partes = []
    for senal, lista in (("contra su historia", ri.asignaciones_percentil), ("absoluta", ri.asignaciones_absoluta)):
        if not lista:
            continue
        t = tabla_asignaciones(lista)
        partes.append(pd.DataFrame({
            "metodo": [NOMBRES[k] for k in t.index], "senal": senal, "desde": [mes(f) for f in t["desde"]],
            "tir_con_el_metodo": t["tir_usd"].to_numpy(), "tir_partes_iguales": t["tir_partes_iguales"].to_numpy(),
            "ventaja_tir_bps": [_bps(x) for x in t["ventaja"]],
            "ventaja_al_mas_caro_bps": [_bps(x) for x in t["ventaja_el_mas_caro"]],
            "ventaja_primera_mitad_bps": [_bps(x) for x in t["ventaja_primera_mitad"]],
            "ventaja_segunda_mitad_bps": [_bps(x) for x in t["ventaja_segunda_mitad"]],
            "fraccion_del_azar_que_la_iguala": t["azar_que_le_gana"].to_numpy(),
            "meses_en_cada_uno": [" · ".join(f"{x} {int(t.loc[c, f'meses_{x}'])}" for x in ri.paneles)
                                  for c in t.index],
        }))
    if not partes:
        return pd.DataFrame(columns=COLUMNAS["asignacion"])
    return _con(pd.concat(partes, ignore_index=True), "asignacion")


def validacion(ri: ResultadoIntrinsecos) -> pd.DataFrame:
    v = ri.validacion
    if v.empty:
        return pd.DataFrame(columns=COLUMNAS["validacion"])
    return _con(pd.DataFrame({
        "emisor": v["emisor"], "anio": v["anio"].astype(int), "veces_deuda_neta_armada": v["armado"].round(2),
        "veces_reportadas": v["reportado"], "diferencia_relativa": v["diferencia"],
        "se_usa": np.where(v["se_usa"], "sí", "no"),
    }), "validacion")


def trimestres(ri: ResultadoIntrinsecos, ticker: str) -> pd.DataFrame:
    q = trimestral(ri.paneles[ticker]).dropna(subset=["precio"])
    q = q[q["r"].notna()]
    d = pd.DataFrame({
        "trimestre": [f"{f.year}-T{(f.month - 1) // 3 + 1}" for f in q.index],
        "precio": q["precio"], "tasa_de_descuento": q["r"], "crecimiento_dividendo_5a": q["g_ddm"],
        "valor_ddm_por_accion": q["valor_ddm"], "crecimiento_flujo_5a": q["g_flujo_5a"],
        "valor_dcf_por_accion": q["valor_dcf"], "crecimiento_implicito": q["g_implicito"],
        "noi_anualizado_millones": (q["noi_anualizado"] / 1e6).round(1), "cap_rate": q["cap_rate"],
        "deuda_neta_millones": (q["deuda_neta"] / 1e6).round(1), "nav_por_accion": q["nav"],
        "descuento_ddm": q["v_ddm"], "descuento_dcf": q["v_dcf"], "brecha_de_crecimiento": q["v_crecimiento"],
        "descuento_nav": q["v_nav"],
    }, index=q.index)
    return _con(d.iloc[::-1], "trimestres")


VISTAS = {"trimestres": trimestres, "backtest": backtest}
