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
    "sensibilidad": ("fase", "prueba", "sic_bps", "broker_30_bps", "broker_35_bps", "criterio", "veredicto"),
    "perfiles_fiscales": ("perfil", "dividendo_pct", "intereses_pct", "ganancia_pct", "comision_pct"),
    "bases_fiscales": ("muestra", "tir_sic", "tir_broker_30", "tir_broker_35", "broker_30_contra_sic_bps",
                       "broker_35_contra_sic_bps"),
    "extremos_sector": ("senal", "corte", "muestra", "meses", "episodios", "rendimiento_reits",
                        "rendimiento_efectivo", "fraccion_efectivo_gana", "diferencia_contra_el_resto_bps", "t"),
    "extremos_emisores": ("corte", "trimestres", "ventanas_independientes", "rendimiento_5a_mediana",
                          "rendimiento_5a_p10", "rendimiento_5a_p90"),
    "pistas": ("nivel", "prueba", "desarrollo", "validacion", "pista"),
    "poder": ("prueba", "muestra", "observado_bps", "placebo_promedio_bps", "error_estandar_bps",
              "efecto_minimo_detectable_bps", "inadvertida_con_100_pb_pct", "inadvertida_con_200_pb_pct"),
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


PERFILES_EN_ORDEN = ("sic", "broker_30", "broker_35")


def sensibilidad(res: dict) -> pd.DataFrame:
    """Las pruebas que deciden cada conclusión, con el SIC y con el broker de EE. UU."""
    d = res["sensibilidad_broker"]["resumen"].copy()
    for k in PERFILES_EN_ORDEN:
        d[f"{k}_bps"] = (d[f"{k}_pb"] if f"{k}_pb" in d else pd.Series(np.nan, index=d.index)).round().astype("Int64")
    vered = [c for c in (f"veredicto_{k}" for k in PERFILES_EN_ORDEN) if c in d]
    d["veredicto"] = [" / ".join(str(f[c]) for c in vered if pd.notna(f[c])) or "—" for _, f in d.iterrows()]
    return _con(d, "sensibilidad")


def perfiles_fiscales(res: dict) -> pd.DataFrame:
    p = res["sensibilidad_broker"]["perfiles"]
    return _con(pd.DataFrame({"perfil": p["nombre"], "dividendo_pct": p["tasa_dividendo"],
                              "intereses_pct": p["tasa_intereses"], "ganancia_pct": p["tasa_ganancia"],
                              "comision_pct": p["comision_pct"]}), "perfiles_fiscales")


def bases_fiscales(res: dict) -> pd.DataFrame:
    b = res["sensibilidad_broker"]["bases"]
    d = pd.DataFrame({"muestra": b["muestra"], **{f"tir_{k}": b[k] for k in PERFILES_EN_ORDEN}})
    for k in ("broker_30", "broker_35"):
        d[f"{k}_contra_sic_bps"] = _bps(b[k] - b["sic"])
    return _con(d, "bases_fiscales")


ORDEN_CORTES = ("caro 5%", "caro 10%", "centro", "barato 10%", "barato 5%")
MUESTRA_LEGIBLE = {"desarrollo": "1972-2015", "validacion": "2016 en adelante"}


def extremos_sector(res: dict) -> pd.DataFrame:
    """El retorno de los 60 meses siguientes en el 10% más caro, el centro y el 10% más barato de cada señal."""
    d = res["extremos"]["sector"]
    d = d[(d["horizonte_meses"] == 60) & d["corte"].isin(["caro 10%", "centro", "barato 10%"]) & (d["meses"] > 0)]
    return _con(pd.DataFrame({
        "senal": d["senal"], "corte": d["corte"], "muestra": d["muestra"].map(MUESTRA_LEGIBLE),
        "meses": d["meses"].astype(int), "episodios": d["episodios"].astype(int),
        "rendimiento_reits": d["reits_mediana"], "rendimiento_efectivo": d["efectivo_mediana"],
        "fraccion_efectivo_gana": d["efectivo_gana"], "diferencia_contra_el_resto_bps": _bps(d["diferencia_contra_el_resto"]),
        "t": d["t"].round(2)}), "extremos_sector")


def extremos_emisores(res: dict) -> pd.DataFrame:
    """O, NNN y WPC juntos: el retorno de los 5 años siguientes según el tramo del consenso, neto del broker."""
    e = res["extremos"]["emisores"]
    e = e[(e["senal"] == "consenso") & (e["anios"] == 5) & (e["alcance"] == "juntos") & (e["mitad"] == "completo")]
    e = e.set_index("corte").reindex(list(ORDEN_CORTES)).reset_index()
    return _con(pd.DataFrame({
        "corte": e["corte"], "trimestres": e["trimestres"].astype(int),
        "ventanas_independientes": [f"{v:.1f}" for v in e["ventanas_independientes"]],
        "rendimiento_5a_mediana": e["mediana"], "rendimiento_5a_p10": e["p10"], "rendimiento_5a_p90": e["p90"]}),
        "extremos_emisores")


def pistas(res: dict) -> pd.DataFrame:
    """Las combinaciones que cumplen la regla de lectura, y las que más se le acercaron."""
    p = res["extremos"]["pistas"]
    p = p[p["nivel"] != "regla"].copy()
    p["t_minima"] = p[["t_desarrollo", "t_validacion"]].abs().min(axis=1)
    p = p.sort_values(["pista", "t_minima"], ascending=False).head(8)

    def lado(v, t, ep, meses) -> str:
        texto = "—" if pd.isna(v) else f"{v * 100:+.1f}% (t {t:+.2f})" if pd.notna(t) else f"{v * 100:+.1f}%"
        if pd.notna(ep):
            texto += f", {int(meses)} meses en {int(ep)} episodio{'s' if int(ep) != 1 else ''}"
        return texto

    def ep(f, k):
        return f.get(f"episodios_{k}", np.nan), f.get(f"meses_{k}", np.nan)

    return _con(pd.DataFrame({
        "nivel": p["nivel"], "prueba": p["prueba"],
        "desarrollo": [lado(f["desarrollo"], f["t_desarrollo"], *ep(f, "desarrollo")) for _, f in p.iterrows()],
        "validacion": [lado(f["validacion"], f["t_validacion"], *ep(f, "validacion")) for _, f in p.iterrows()],
        "pista": np.where(p["pista"].astype(bool), "sí", "no")}), "pistas")


def poder(res: dict) -> pd.DataFrame:
    """Qué tan grande tenía que ser una ventaja para que cada prueba la viera."""
    e = res["poder"]["errores"]
    c = res["poder"]["curvas"]

    def inadvertida(f, delta):
        x = c[(c["prueba"] == f["prueba"]) & (c["muestra"] == f["muestra"]) & np.isclose(c["delta"], delta)]
        return float(x["inadvertida"].iloc[0]) if len(x) else np.nan

    return _con(pd.DataFrame({
        "prueba": e["prueba"].str.replace(" | ", " · ", regex=False),
        # En el análisis de poder, «desarrollo» y «validación» son las de la selección (fase 6).
        "muestra": e["muestra"].map(lambda m: {"desarrollo": "2011-2015", "validacion": "2016 en adelante"}.get(m, m)),
        "observado_bps": _bps(e["observado"]), "placebo_promedio_bps": _bps(e["nula_media"]),
        "error_estandar_bps": _bps(e["ee"]), "efecto_minimo_detectable_bps": _bps(e["mde"]),
        "inadvertida_con_100_pb_pct": [inadvertida(f, 0.01) for _, f in e.iterrows()],
        "inadvertida_con_200_pb_pct": [inadvertida(f, 0.02) for _, f in e.iterrows()]}), "poder")


VISTAS = {"fases": fases, "descomposicion": descomposicion, "caidas": caidas, "frecuencia": frecuencia,
          "techo": techo, "reglas": reglas, "escalera": escalera, "prueba_final": prueba_final,
          "seleccion": seleccion, "sensibilidad": sensibilidad, "perfiles_fiscales": perfiles_fiscales,
          "bases_fiscales": bases_fiscales, "extremos_sector": extremos_sector,
          "extremos_emisores": extremos_emisores, "pistas": pistas, "poder": poder}
# Las que dependen de una fase opcional: sin sus resultados guardados, la página y el PDF no las piden.
REQUIERE = {"seleccion": "fase6", "sensibilidad": "sensibilidad_broker", "perfiles_fiscales": "sensibilidad_broker",
            "bases_fiscales": "sensibilidad_broker", "extremos_sector": "extremos", "extremos_emisores": "extremos",
            "pistas": "extremos", "poder": "poder"}
