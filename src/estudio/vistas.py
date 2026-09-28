"""Las tablas del estudio tal como se muestran en pantalla.

Por qué viven aquí y no en la página
------------------------------------
La aplicación decide la UNIDAD de cada columna —y con ella si la escala a
porcentaje— por las palabras de su nombre (``app/comun.familia_de_columna``).
Con los nombres crudos del modelo, la pantalla dibujaba un costo de capital de
7.4% como «$0.07» y un P/FFO de 20 como «$20.01». Y al revés: si alguien renombra
una columna aquí y no en la lista de columnas a mostrar, la columna no se formatea
mal, DESAPARECE, sin error.

Armadas en la página no se podían probar. Aquí cada vista declara sus columnas y
la prueba 51 verifica dos cosas sobre todas: que ninguna declarada falte, y que
ninguna columna de fracciones caiga en una unidad que no sea porcentaje.
"""

from __future__ import annotations

import pandas as pd

from src.estudio.graficas import mes

COLUMNAS: dict[str, tuple[str, ...]] = {
    "spread_inversion": (
        "anio", "cap_rate", "tasa_costo_acciones", "medida", "tasa_costo_deuda", "peso_deuda",
        "tasa_costo_ponderado", "spread_contra_acciones", "spread_contra_ponderado", "monto_invertido_usd",
    ),
    "eras": (
        "era", "desde", "hasta", "años", "rendimiento_anual", "aporte_dividendo_cobrado",
        "aporte_crecimiento_dividendo", "aporte_revaluacion", "aporte_escision", "yield_inicio",
        "yield_fin", "multiplo_ffo_inicio", "multiplo_ffo_fin",
    ),
    "quintiles": (
        "quintil", "multiplo_ffo_desde", "multiplo_ffo_hasta", "rendimiento_5a_mediana",
        "rendimiento_5a_peor", "rendimiento_5a_mejor", "meses",
    ),
    "momentos": (
        "compra", "precio", "multiplo_ffo", "yield_ttm", "rendimiento_5a", "rendimiento_10a",
        "rendimiento_a_hoy", "yield_sobre_costo",
    ),
    "yield_sobre_costo": (
        "compra", "precio", "multiplo_ffo", "rendimiento_a_hoy_en_dólares", "rendimiento_a_hoy_en_pesos",
        "multiplo_de_lo_invertido", "yield_sobre_costo",
    ),
    "escenarios": (
        "supuesto_de_crecimiento", "crecimiento", "rendimiento_usd_multiplo_constante",
        "rendimiento_usd_si_vuelve_el_spread", "rendimiento_usd_si_vuelve_el_multiplo",
        "rendimiento_real_neto", "rendimiento_real_neto_si_vuelve_el_spread",
        "rendimiento_real_neto_si_vuelve_el_multiplo",
    ),
    "diagnostico_ffo": ("anio", "ffo_por_accion_derivado", "ffo_por_accion_reportado", "error"),
}

# La tabla anual lleva todas sus columnas; solo se renombran las que el nombre
# del modelo mandaría a la unidad equivocada.
RENOMBRES_ANUAL = {
    "deuda_sobre_activos": "ltv_en_libros", "costo_deuda": "tasa_costo_deuda",
    "gya_sobre_ingresos": "fraccion_gya_de_ingresos", "ebitdare": "ebitda_re_usd",
    "deuda_neta_ebitdare": "multiplo_deuda_neta_ebitdare",
}


def _con(df: pd.DataFrame, clave: str) -> pd.DataFrame:
    """Devuelve exactamente las columnas declaradas; si falta una, truena aquí."""
    faltan = [c for c in COLUMNAS[clave] if c not in df.columns]
    if faltan:
        raise KeyError(f"La vista «{clave}» perdió columnas: {faltan}")
    return df[list(COLUMNAS[clave])].reset_index(drop=True)


def spread_inversion(e) -> pd.DataFrame:
    si = e.spread_inversion.reset_index()
    if si.empty:
        return pd.DataFrame(columns=COLUMNAS["spread_inversion"])
    si["anio"] = si["anio"].astype(str)
    for c in ("costo_deuda", "peso_deuda", "costo_ponderado", "spread_contra_ponderado"):
        if c not in si:
            si[c] = float("nan")
    si = si.rename(columns={
        "costo_acciones": "tasa_costo_acciones", "costo_deuda": "tasa_costo_deuda",
        "costo_ponderado": "tasa_costo_ponderado", "inversion": "monto_invertido_usd",
    })
    return _con(si, "spread_inversion")


def anual(e) -> pd.DataFrame:
    t = e.anual.reset_index()
    t.attrs = {}   # guardan la tabla de fuentes; Streamlit intentaría serializarlos
    t["anio"] = t["anio"].astype(str)
    return t.rename(columns=RENOMBRES_ANUAL)


def eras(e) -> pd.DataFrame:
    filas = [{
        "era": d.nombre, "desde": str(d.inicio.date()), "hasta": str(d.fin.date()),
        "años": round(d.anios, 1), "rendimiento_anual": d.retorno_total,
        "aporte_dividendo_cobrado": d.ingreso, "aporte_crecimiento_dividendo": d.crecimiento_dividendo,
        "aporte_revaluacion": d.revaluacion, "aporte_escision": d.escision,
        "yield_inicio": d.yield_inicio, "yield_fin": d.yield_fin,
        "multiplo_ffo_inicio": d.p_ffo_inicio, "multiplo_ffo_fin": d.p_ffo_fin,
    } for d in [*e.eras, e.total]]
    return _con(pd.DataFrame(filas), "eras")


def quintiles(e) -> pd.DataFrame:
    q = e.entradas.quintiles
    if q.empty:
        return pd.DataFrame(columns=COLUMNAS["quintiles"])
    return _con(q.reset_index().rename(columns={
        "desde": "multiplo_ffo_desde", "hasta": "multiplo_ffo_hasta",
        "rt_5a_mediana": "rendimiento_5a_mediana", "rt_5a_peor": "rendimiento_5a_peor",
        "rt_5a_mejor": "rendimiento_5a_mejor",
    }), "quintiles")


def momentos(df: pd.DataFrame) -> pd.DataFrame:
    v = df[["precio", "p_ffo", "yield_ttm", "rt_5a", "rt_10a", "rt_a_hoy_usd", "yield_sobre_costo"]].copy()
    v.insert(0, "compra", [mes(f) for f in v.index])
    return _con(v.rename(columns={
        "p_ffo": "multiplo_ffo", "rt_5a": "rendimiento_5a", "rt_10a": "rendimiento_10a",
        "rt_a_hoy_usd": "rendimiento_a_hoy",
    }), "momentos")


def cortes_de_compra(e) -> list[pd.Timestamp]:
    """Fines de año cada cinco años y el mes de hace un año, solo con al menos un año de historia.

    Anualizar nueve meses exagera cualquier movimiento: un -5% de seis meses se
    lee como -10% al año.
    """
    t = e.entradas.tabla
    cortes = [f for f in t.index if f.month == 12 and f.year % 5 == 0]
    if len(t) > 13:
        cortes.append(t.index[-13])
    return sorted({f for f in cortes if t.loc[f, "anios_a_hoy"] >= 1})


def yield_sobre_costo(e) -> pd.DataFrame:
    t = e.entradas.tabla
    v = t.loc[cortes_de_compra(e), ["precio", "p_ffo", "rt_a_hoy_usd", "rt_a_hoy_mxn",
                                    "multiplo_a_hoy", "yield_sobre_costo"]].copy()
    v.insert(0, "compra", [mes(f) for f in v.index])
    return _con(v.rename(columns={
        "p_ffo": "multiplo_ffo", "rt_a_hoy_usd": "rendimiento_a_hoy_en_dólares",
        "rt_a_hoy_mxn": "rendimiento_a_hoy_en_pesos", "multiplo_a_hoy": "multiplo_de_lo_invertido",
    }), "yield_sobre_costo")


def escenarios(e) -> pd.DataFrame:
    return _con(pd.DataFrame([{
        "supuesto_de_crecimiento": s.nombre, "crecimiento": s.crecimiento,
        "rendimiento_usd_multiplo_constante": s.retorno_usd,
        "rendimiento_usd_si_vuelve_el_spread": s.retorno_con_reversion,
        "rendimiento_usd_si_vuelve_el_multiplo": s.retorno_reversion_multiplo,
        "rendimiento_real_neto": s.real_neto,
        "rendimiento_real_neto_si_vuelve_el_spread": s.real_neto_reversion_spread,
        "rendimiento_real_neto_si_vuelve_el_multiplo": s.real_neto_reversion_multiplo,
    } for s in e.hoy.escenarios], columns=list(COLUMNAS["escenarios"])), "escenarios")


def diagnostico_ffo(e) -> pd.DataFrame:
    d = e.diagnostico_ffo.tabla.reset_index().rename(columns={
        "fecha_dato": "anio", "index": "anio", "derivado": "ffo_por_accion_derivado",
        "reportado": "ffo_por_accion_reportado",
    })
    if d.empty:
        return pd.DataFrame(columns=COLUMNAS["diagnostico_ffo"])
    d["anio"] = d["anio"].astype(str)
    return _con(d, "diagnostico_ffo")


VISTAS = {
    "spread_inversion": spread_inversion, "anual": anual, "eras": eras, "quintiles": quintiles,
    "mejores": lambda e: momentos(e.entradas.mejores), "peores": lambda e: momentos(e.entradas.peores),
    "yield_sobre_costo": yield_sobre_costo, "escenarios": escenarios, "diagnostico_ffo": diagnostico_ffo,
}
