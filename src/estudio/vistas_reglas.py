"""Las tablas del backtest de reglas tal como se muestran en pantalla.

Como en ``vistas``: la aplicación decide la unidad de cada columna por su nombre
(``app/comun.familia_de_columna``), así que aquí cada vista declara sus columnas y la
prueba 52 verifica que ninguna columna de fracciones caiga fuera de «porcentaje».
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.estudio.graficas import mes
from src.estudio.reglas import ResultadoReglas, Variante

COLUMNAS: dict[str, tuple[str, ...]] = {
    "variantes": (
        "variante", "tir_usd", "tir_mxn", "ventaja_tir_bps", "multiplo_de_lo_aportado",
        "fraccion_en_el_papel", "caida_maxima", "ventas", "impuestos_usd", "valor_final_usd",
    ),
    "ventas": (
        "venta", "disparador", "precio", "rendimiento_papel_1_anio", "rendimiento_papel_3_anios",
        "primera_compra_despues", "lo_vendido_vuelve", "precio_al_volver", "meses_fuera",
        "rendimiento_papel_mientras_fuera",
    ),
    "por_decision": (
        "decision", "meses", "fraccion_del_tiempo", "rendimiento_12m_mediana", "rendimiento_12m_peor",
        "rendimiento_12m_mejor", "ventanas_independientes",
    ),
    "criterios": ("puerta", "criterio", "meses", "fraccion_del_tiempo"),
    "sensibilidad": ("fraccion_comprar_menos", "tir_usd", "ventaja_tir_bps", "multiplo_de_lo_aportado"),
    "comparativo": (
        "emisor", "desde", "tir_modelo", "tir_sin_reglas", "ventaja_tir_bps", "ventas",
        "fraccion_en_el_papel", "apuestas_efectivas", "dictamen", "decision_hoy",
    ),
}


def _con(df: pd.DataFrame, clave: str) -> pd.DataFrame:
    faltan = [c for c in COLUMNAS[clave] if c not in df.columns]
    if faltan:
        raise KeyError(f"La vista «{clave}» perdió columnas: {faltan}")
    return df[list(COLUMNAS[clave])].reset_index(drop=True)


def variantes(r: ResultadoReglas) -> pd.DataFrame:
    t = r.tabla.reset_index()
    return _con(pd.DataFrame({
        "variante": t["variante"],
        "tir_usd": t["tir_usd"], "tir_mxn": t["tir_mxn"],
        "ventaja_tir_bps": (t["ventaja_tir_usd"] * 1e4).round(0),
        "multiplo_de_lo_aportado": t["multiplo"],
        "fraccion_en_el_papel": t["exposicion_promedio"],
        "caida_maxima": t["caida_maxima"],
        "ventas": t["ventas"].astype(int),
        "impuestos_usd": t["impuestos"],
        "valor_final_usd": t["valor_final_neto"],
    }), "variantes")


def ventas(r: ResultadoReglas) -> pd.DataFrame:
    v = r.ventas
    if v.empty:
        return pd.DataFrame(columns=COLUMNAS["ventas"])
    def col(c):
        return v[c] if c in v else pd.Series(np.nan, index=v.index)
    return _con(pd.DataFrame({
        "venta": [mes(f) for f in v["fecha"]],
        "disparador": v["disparadores"],
        "precio": v["precio"],
        "rendimiento_papel_1_anio": col("papel_1a"),
        "rendimiento_papel_3_anios": col("papel_3a"),
        "primera_compra_despues": [mes(f) if pd.notna(f) else "—" for f in col("recompra")],
        "lo_vendido_vuelve": [mes(f) if pd.notna(f) else "no ha vuelto" for f in col("reinversion")],
        "precio_al_volver": col("precio_reinversion"),
        "meses_fuera": col("meses_fuera").round(0),
        "rendimiento_papel_mientras_fuera": col("papel_mientras_fuera"),
    }), "ventas")


def por_decision(r: ResultadoReglas) -> pd.DataFrame:
    p = r.por_decision.reset_index()
    total = p["meses"].sum()
    return _con(pd.DataFrame({
        "decision": p["decision"],
        "meses": p["meses"].astype(int),
        "fraccion_del_tiempo": p["meses"] / total if total else np.nan,
        "rendimiento_12m_mediana": p["mediana_12m"],
        "rendimiento_12m_peor": p["peor_12m"],
        "rendimiento_12m_mejor": p["mejor_12m"],
        "ventanas_independientes": p["independientes"],
    }), "por_decision")


def criterios(r: ResultadoReglas) -> pd.DataFrame:
    c = r.criterios
    if c.empty:
        return pd.DataFrame(columns=COLUMNAS["criterios"])
    return _con(c.rename(columns={"fraccion": "fraccion_del_tiempo"}), "criterios")


def sensibilidad(r: ResultadoReglas) -> pd.DataFrame:
    s = r.sensibilidad
    return _con(pd.DataFrame({
        "fraccion_comprar_menos": s["fraccion_comprar_menos"],
        "tir_usd": s["tir_usd"],
        "ventaja_tir_bps": (s["ventaja_tir_usd"] * 1e4).round(0),
        "multiplo_de_lo_aportado": s["multiplo"],
    }), "sensibilidad")


def comparativo(resultados: list[ResultadoReglas]) -> pd.DataFrame:
    filas = []
    for r in resultados:
        filas.append({
            "emisor": r.ticker,
            "desde": mes(r.desde),
            "tir_modelo": r.tabla.loc[Variante.MODELO.value, "tir_usd"],
            "tir_sin_reglas": r.tabla.loc[Variante.BENCHMARK.value, "tir_usd"],
            "ventaja_tir_bps": round(r.tabla.loc[Variante.MODELO.value, "ventaja_tir_usd"] * 1e4),
            "ventas": int(r.tabla.loc[Variante.MODELO.value, "ventas"]),
            "fraccion_en_el_papel": r.tabla.loc[Variante.MODELO.value, "exposicion_promedio"],
            "apuestas_efectivas": int(r.apuestas.episodios),
            "dictamen": r.dictamen.veredicto.value,
            "decision_hoy": r.decision_hoy["decision"],
        })
    return _con(pd.DataFrame(filas), "comparativo")


VISTAS = {"variantes": variantes, "ventas": ventas, "por_decision": por_decision,
          "criterios": criterios, "sensibilidad": sensibilidad}
