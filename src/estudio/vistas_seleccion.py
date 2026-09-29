"""Las tablas de la prueba del universo, como se muestran en pantalla y en el PDF.

La unidad de cada columna sale de su nombre (``app/comun.familia_de_columna``); la prueba 55
verifica que ninguna fracción caiga fuera de «porcentaje».
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.estudio.graficas import mes
from src.estudio.seleccion import GRUPOS, SENALES, ResultadoSeleccion

COLUMNAS: dict[str, tuple[str, ...]] = {
    "grupos": ("senal", "variante", "grupo", "rendimiento_anual", "brecha_contra_todos", "t_newey_west",
               "volatilidad", "caida_maxima"),
    "correlacion": ("senal", "meses", "correlacion_promedio", "fraccion_de_meses_positiva", "t_newey_west"),
    "trampas": ("senal", "variante", "grupo", "observaciones", "fraccion_que_recorto", "fraccion_que_se_desplomo",
                "rendimiento_12m_mediana"),
    "aportacion": ("cartera", "tir", "brecha_contra_todos_bps", "monto_aportado", "valor_final"),
    "mitades": ("senal", "mitad", "desde", "hasta", "correlacion", "brecha_barato_contra_todos",
                "brecha_barato_menos_caro"),
    "sectores": ("industria", "emisores", "correlacion_historia", "correlacion_ddm", "meses"),
    "plazos": ("senal", "horizonte_anios", "rendimiento_barato", "rendimiento_medio", "rendimiento_caro",
               "rendimiento_todos", "brecha_barato_contra_todos"),
    "robustez": ("senal", "muestra", "brecha_barato_contra_todos", "brecha_barato_menos_caro", "correlacion",
                 "fraccion_que_recorto_barato", "fraccion_que_recorto_todos", "fraccion_que_recorto_caro"),
    "hoy": ("ticker", "nombre", "industria", "precio", "yield_dividendo", "percentil_historia",
            "razon_contra_sector", "descuento_ddm", "grupo_historia", "grupo_sector", "grupo_ddm",
            "recorto_en_12m"),
}


def _con(df: pd.DataFrame, clave: str) -> pd.DataFrame:
    faltan = [c for c in COLUMNAS[clave] if c not in df.columns]
    if faltan:
        raise KeyError(f"La vista «{clave}» perdió columnas: {faltan}")
    return df[list(COLUMNAS[clave])].reset_index(drop=True)


def _variante(filtro: bool) -> str:
    return "con dividendo intacto" if filtro else "todas"


def grupos(r: ResultadoSeleccion, *, filtro: bool | None = None) -> pd.DataFrame:
    filas = []
    for (s, f), c in r.carteras.items():
        if filtro is not None and f != filtro:
            continue
        for grupo, x in c.resumen.iterrows():
            filas.append({"senal": SENALES[s], "variante": _variante(f), "grupo": grupo,
                          "rendimiento_anual": x["retorno_anual"],
                          "brecha_contra_todos": x["contra_todos"] if grupo in GRUPOS else np.nan,
                          "t_newey_west": round(float(x["t_contra_todos"]), 2) if pd.notna(x["t_contra_todos"]) else np.nan,
                          "volatilidad": x["volatilidad"], "caida_maxima": x["caida_maxima"]})
    return _con(pd.DataFrame(filas), "grupos")


def correlacion(r: ResultadoSeleccion) -> pd.DataFrame:
    c = r.resumen_correlacion
    return _con(pd.DataFrame({
        "senal": [SENALES[s] for s in c.index], "meses": c["meses"].astype(int),
        "correlacion_promedio": c["promedio"].round(3), "fraccion_de_meses_positiva": c["meses_positivos"],
        "t_newey_west": c["t_newey_west"].round(2)}), "correlacion")


def trampas(r: ResultadoSeleccion) -> pd.DataFrame:
    filas = []
    for (s, f), t in r.trampas.items():
        for grupo, x in t.iterrows():
            filas.append({"senal": SENALES[s], "variante": _variante(f), "grupo": grupo,
                          "observaciones": int(x["observaciones"]), "fraccion_que_recorto": x["recorto_despues"],
                          "fraccion_que_se_desplomo": x["se_desplomo"],
                          "rendimiento_12m_mediana": x["retorno_12m_mediana"]})
    return _con(pd.DataFrame(filas), "trampas")


def aportacion(r: ResultadoSeleccion) -> pd.DataFrame:
    a = r.aportaciones
    return _con(pd.DataFrame({
        "cartera": a["cartera"], "tir": a["tir"],
        "brecha_contra_todos_bps": [round(float(x) * 1e4) if pd.notna(x) else np.nan for x in a["contra_todos"]],
        "monto_aportado": a["aportado"], "valor_final": a["valor"]}), "aportacion")


def mitades(r: ResultadoSeleccion) -> pd.DataFrame:
    m = r.mitades
    return _con(pd.DataFrame({
        "senal": [SENALES[s] for s in m["senal"]], "mitad": m["mitad"],
        "desde": [mes(f) for f in m["desde"]], "hasta": [mes(f) for f in m["hasta"]],
        "correlacion": m["correlacion"].round(3), "brecha_barato_contra_todos": m["barato_contra_todos"],
        "brecha_barato_menos_caro": m["barato_menos_caro"]}), "mitades")


def sectores(r: ResultadoSeleccion) -> pd.DataFrame:
    p = r.por_sector.pivot_table(index="industria", columns="senal", values="correlacion")
    n = r.por_sector.groupby("industria")[["emisores", "meses"]].max()
    d = pd.DataFrame({"industria": p.index, "emisores": n.loc[p.index, "emisores"].astype(int).to_numpy(),
                      "correlacion_historia": p["historia"].round(3).to_numpy(),
                      "correlacion_ddm": p["ddm"].round(3).to_numpy(),
                      "meses": n.loc[p.index, "meses"].astype(int).to_numpy()})
    return _con(d.sort_values("emisores", ascending=False), "sectores")


def plazos(r: ResultadoSeleccion) -> pd.DataFrame:
    """Exploratorio: la mediana del retorno anualizado de cada tercil a 1, 3 y 5 años."""
    p = r.plazos
    return _con(pd.DataFrame({
        "senal": [SENALES[s] for s in p["senal"]], "horizonte_anios": (p["horizonte_meses"] // 12).astype(int),
        "rendimiento_barato": p["barato"], "rendimiento_medio": p["medio"], "rendimiento_caro": p["caro"],
        "rendimiento_todos": p["todos"], "brecha_barato_contra_todos": p["barato"] - p["todos"]}), "plazos")


def robustez(r: ResultadoSeleccion) -> pd.DataFrame:
    """Las cifras centrales con todos los dividendos y sin los que parecen especiales."""
    filas = []
    for s in SENALES:
        c, t = r.carteras[(s, False)].resumen, r.trampas[(s, False)]
        filas.append({"senal": SENALES[s], "muestra": "todos los dividendos",
                      "brecha_barato_contra_todos": c.loc["barato", "contra_todos"],
                      "brecha_barato_menos_caro": c.loc["barato menos caro", "retorno_anual"],
                      "correlacion": round(float(r.resumen_correlacion.loc[s, "promedio"]), 3),
                      "fraccion_que_recorto_barato": t.loc["barato", "recorto_despues"],
                      "fraccion_que_recorto_todos": t.loc["todos", "recorto_despues"],
                      "fraccion_que_recorto_caro": t.loc["caro", "recorto_despues"]})
        e = r.sin_especiales.loc[s]
        filas.append({"senal": SENALES[s], "muestra": f"sin {r.especiales} especiales",
                      "brecha_barato_contra_todos": e["barato_contra_todos"],
                      "brecha_barato_menos_caro": e["barato_menos_caro"], "correlacion": round(float(e["correlacion"]), 3),
                      "fraccion_que_recorto_barato": e["recorte_barato"],
                      "fraccion_que_recorto_todos": e["recorte_todos"],
                      "fraccion_que_recorto_caro": e["recorte_caro"]})
    return _con(pd.DataFrame(filas), "robustez")


def hoy(r: ResultadoSeleccion) -> pd.DataFrame:
    h = r.hoy()
    nombres = r.universo.set_index("ticker")["nombre"]
    return _con(pd.DataFrame({
        "ticker": h["ticker"], "nombre": h["ticker"].map(nombres).fillna(""), "industria": h["industria"],
        "precio": h["precio"], "yield_dividendo": h["yield"], "percentil_historia": h["historia"],
        "razon_contra_sector": h["sector"].round(2), "descuento_ddm": h["ddm"],
        "grupo_historia": h["grupo_historia"].fillna("—"), "grupo_sector": h["grupo_sector"].fillna("—"),
        "grupo_ddm": h["grupo_ddm"].fillna("—"),
        "recorto_en_12m": np.where(h["recorto_antes"].astype(bool), "sí", "no")}), "hoy")


VISTAS = {"grupos": grupos, "correlacion": correlacion, "trampas": trampas, "aportacion": aportacion,
          "mitades": mitades, "sectores": sectores, "plazos": plazos, "robustez": robustez, "hoy": hoy}
