"""Las tablas de la investigación, como se muestran en la página y en el PDF.

La unidad de cada columna sale de su nombre (``app/comun.familia_de_columna``): las mejoras
van en ``*_bps`` (ya en puntos base), las fracciones con un nombre de porcentaje. La prueba
70 verifica que ninguna fracción caiga fuera de «porcentaje».
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.investigacion.graficas import NOMBRES_MERCADO

COLUMNAS: dict[str, tuple[str, ...]] = {
    "fases": ("fase", "que", "detalle", "resultado"),
    "descomposicion": ("periodo", "rendimiento_reits", "rendimiento_ingreso", "rendimiento_precio",
                       "rendimiento_efectivo", "inflacion", "rendimiento_bolsa", "volatilidad_reits",
                       "correlacion_con_bolsa"),
    "caidas": ("maximo", "minimo", "caida", "meses_cayendo", "meses_para_recuperar"),
    "frecuencia": ("meses_hacia_adelante", "fraccion_efectivo_gana", "ventanas_independientes",
                   "rendimiento_reits_mediana", "rendimiento_efectivo_mediana"),
    "techo": ("regla", "modo", "tir", "contra_aportar_siempre_bps", "caida_maxima", "exposicion_pct", "cambios"),
    "reglas": ("senal", "regla", "solo_dinero_nuevo_bps", "rebalanceando_bps", "contra_mezcla_fija_bps",
               "caida_maxima", "exposicion_pct", "con_un_mes_de_retraso_bps", "r2_12m_pct", "clark_west_p", "pasa"),
    "escalera": ("peldano", "rebalanceando_bps", "solo_dinero_nuevo_bps", "contra_mezcla_fija_bps", "caida_maxima",
                 "exposicion_pct", "cambios", "con_un_mes_de_retraso_bps", "r2_del_modelo_pct", "clark_west_p"),
    "prueba_final": ("mercado", "serie", "periodo", "tir_aportando_siempre", "tendencia_contra_aportar_bps",
                     "caida_aportando_siempre", "caida_con_tendencia", "reduccion_de_caida_pct", "exposicion_pct",
                     "con_un_mes_de_retraso_bps", "cumple"),
    "seleccion": ("regla", "hipotesis", "desarrollo_bps", "con_un_trimestre_de_retraso_bps", "exceso_bruto_pct",
                  "recortes_regla_pct", "recortes_universo_pct", "escogidos", "pasa_desarrollo", "validacion_bps",
                  "prueba_final_bps"),
}


def _con(d: pd.DataFrame, clave: str) -> pd.DataFrame:
    faltan = [c for c in COLUMNAS[clave] if c not in d.columns]
    if faltan:
        raise KeyError(f"La vista «{clave}» perdió columnas: {faltan}")
    return d[list(COLUMNAS[clave])].reset_index(drop=True)


def _bps(s) -> pd.Series:
    return (pd.Series(s, dtype=float) * 1e4).round().astype("Int64")


def _mes(f) -> str:
    return "—" if pd.isna(f) else f"{pd.Timestamp(f):%m-%Y}"


def fases(res: dict) -> pd.DataFrame:
    from src.investigacion.conclusiones import fases as f

    return _con(f(res), "fases")


def descomposicion(res: dict) -> pd.DataFrame:
    return _con(res["fase3"]["descomposicion"], "descomposicion")


def caidas(res: dict) -> pd.DataFrame:
    c = res["fase3"]["caidas"]
    return _con(pd.DataFrame({"maximo": c["maximo"].map(_mes), "minimo": c["minimo"].map(_mes), "caida": c["caida"],
                              "meses_cayendo": c["meses_de_caida"].astype(int),
                              "meses_para_recuperar": c["meses_para_recuperar"].astype("Int64")}), "caidas")


def frecuencia(res: dict) -> pd.DataFrame:
    f = res["fase3"]["frecuencia"]
    return _con(pd.DataFrame({"meses_hacia_adelante": f["horizonte_meses"].astype(int),
                              "fraccion_efectivo_gana": f["fraccion_efectivo_gana"],
                              "ventanas_independientes": f["independientes"].astype(int),
                              "rendimiento_reits_mediana": f["rendimiento_reits_mediana"],
                              "rendimiento_efectivo_mediana": f["rendimiento_efectivo_mediana"]}), "frecuencia")


def techo(res: dict) -> pd.DataFrame:
    t = res["fase3"]["techo"]
    return _con(pd.DataFrame({"regla": t["regla"], "modo": t["modo"], "tir": t["tir"],
                              "contra_aportar_siempre_bps": t["contra_aportar_siempre_bps"].astype(int),
                              "caida_maxima": t["caida_maxima"], "exposicion_pct": t["exposicion_promedio"],
                              "cambios": t["cambios"].astype(int)}), "techo")


REGLAS_CORTAS = {"signo": "por signo", "fuera en el quintil peor (20%)": "fuera en el peor quintil",
                 "continua con piso de 50%": "continua 50-100%", "fuera si caro y a la baja": "caro y a la baja"}


def reglas(res: dict) -> pd.DataFrame:
    d = res["fase5"]["desarrollo"].sort_values("mejora_rebalanceo", ascending=False)
    return _con(pd.DataFrame({
        "senal": d["senal"], "regla": d["regla"].map(lambda r: REGLAS_CORTAS.get(r, r)), "solo_dinero_nuevo_bps": _bps(d["mejora_nuevo"]),
        "rebalanceando_bps": _bps(d["mejora_rebalanceo"]), "contra_mezcla_fija_bps": _bps(d["mejora_contra_mezcla_fija"]),
        "caida_maxima": d["caida_rebalanceo"].to_numpy(), "exposicion_pct": d["exposicion_rebalanceo"].to_numpy(),
        "con_un_mes_de_retraso_bps": _bps(d["mejora_rebalanceo_con_rezago"]), "r2_12m_pct": d["r2_12m"].to_numpy(),
        "clark_west_p": d["clark_west_p_12m"].round(2).to_numpy(),
        "pasa": np.where(d["pasa"].astype(bool), "sí", "no")}), "reglas")


def escalera(res: dict) -> pd.DataFrame:
    e = res["fase7"]["evaluacion"]
    r2 = e["r2_12m"].where(e["r2_12m"].notna(), e.get("r2_1m_modelo"))
    cw = e["clark_west_p_12m"].where(e["clark_west_p_12m"].notna(), e.get("clark_west_p_modelo"))
    return _con(pd.DataFrame({
        "peldano": e["senal"], "rebalanceando_bps": _bps(e["mejora_rebalanceo"]),
        "solo_dinero_nuevo_bps": _bps(e["mejora_nuevo"]), "contra_mezcla_fija_bps": _bps(e["mejora_contra_mezcla_fija"]),
        "caida_maxima": e["caida_rebalanceo"], "exposicion_pct": e["exposicion_rebalanceo"],
        "cambios": e["cambios_rebalanceo"].astype(int), "con_un_mes_de_retraso_bps": _bps(e["mejora_rebalanceo_con_rezago"]),
        "r2_del_modelo_pct": r2, "clark_west_p": cw.round(2)}), "escalera")


def prueba_final(res: dict) -> pd.DataFrame:
    m = res["fase8"]["mercados"]
    v = res["fase8"]["resumen"]["validacion"]
    filas = [{"mercado": "EE. UU. (validación)", "serie": "Nareit",
              "periodo": f"{pd.Timestamp(v['desde']):%Y}-{pd.Timestamp(v['hasta']):%Y}",
              "tir_aportando_siempre": v["tir_aportar_siempre"],
              "mejora": v["mejora"], "caida_aportando_siempre": v["caida_aportar_siempre"],
              "caida_con_tendencia": v["caida_regla"], "reduccion_de_caida_pct": v["reduccion_de_caida"],
              "exposicion_pct": v["exposicion"], "rezago": v["mejora_con_rezago"], "cumple": "—"}]
    for _, f in m.iterrows():
        filas.append({"mercado": NOMBRES_MERCADO.get(f["mercado"], f["mercado"]),
                      "serie": f["serie"].replace("etf: ", "ETF ").replace("canasta de ", "canasta, "),
                      "periodo": f"{pd.Timestamp(f['desde']):%Y}-{pd.Timestamp(f['hasta']):%Y}",
                      "tir_aportando_siempre": f["tir_aportar_siempre"], "mejora": f["mejora"],
                      "caida_aportando_siempre": f["caida_aportar_siempre"], "caida_con_tendencia": f["caida_regla"],
                      "reduccion_de_caida_pct": f["reduccion_de_caida"], "exposicion_pct": f["exposicion"],
                      "rezago": f["mejora_con_rezago"], "cumple": "sí" if f["protege"] else "no"})
    d = pd.DataFrame(filas)
    d["tendencia_contra_aportar_bps"] = _bps(d["mejora"])
    d["con_un_mes_de_retraso_bps"] = _bps(d["rezago"])
    return _con(d, "prueba_final")


def seleccion(res: dict) -> pd.DataFrame:
    """Las reglas de la fase 6: desarrollo, y lo que siguió en validación y en los sellados."""
    from src.investigacion.fase6 import DETECTOR, NOMBRES

    f6 = res["fase6"]
    d = f6["desarrollo"].sort_values("mejora", ascending=False)
    v = f6["validacion"].set_index("regla")["mejora"]
    fin = f6["final"].set_index("regla")["mejora"] if "final" in f6 else pd.Series(dtype=float)
    det = f6["validacion"][f6["validacion"]["regla"] == DETECTOR]
    filas = pd.DataFrame({
        "regla": d["regla"].map(lambda r: NOMBRES.get(r, r)), "hipotesis": d["hipotesis"],
        "desarrollo_bps": _bps(d["mejora"]), "con_un_trimestre_de_retraso_bps": _bps(d["mejora_con_rezago"]),
        "exceso_bruto_pct": d["exceso_anual"].to_numpy(), "recortes_regla_pct": d["recortes"].to_numpy(),
        "recortes_universo_pct": d["recortes_todos"].to_numpy(), "escogidos": d["escogidos_promedio"].round().astype(int),
        "pasa_desarrollo": np.where(d["pasa"].astype(bool), "sí", "no"),
        "validacion_bps": _bps(d["regla"].map(v)), "prueba_final_bps": _bps(d["regla"].map(fin))})
    if len(det):
        f = det.iloc[0]
        filas = pd.concat([filas, pd.DataFrame([{
            "regla": NOMBRES[DETECTOR], "hipotesis": "D1", "desarrollo_bps": pd.NA, "con_un_trimestre_de_retraso_bps": pd.NA,
            "exceso_bruto_pct": np.nan, "recortes_regla_pct": f["recortes"], "recortes_universo_pct": f["recortes_todos"],
            "escogidos": int(round(f["escogidos_promedio"])), "pasa_desarrollo": "—",
            "validacion_bps": int(round(f["mejora"] * 1e4)), "prueba_final_bps": pd.NA}])], ignore_index=True)
        for c in ("desarrollo_bps", "con_un_trimestre_de_retraso_bps", "validacion_bps", "prueba_final_bps"):
            filas[c] = filas[c].astype("Int64")
    return _con(filas, "seleccion")


VISTAS = {"fases": fases, "descomposicion": descomposicion, "caidas": caidas, "frecuencia": frecuencia,
          "techo": techo, "reglas": reglas, "escalera": escalera, "prueba_final": prueba_final,
          "seleccion": seleccion}
