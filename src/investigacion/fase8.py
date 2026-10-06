"""Fase 8: la prueba final, abierta una sola vez con el modelo congelado.

Lo único que llegó aquí es la **protección por tendencia** (dentro si el precio está arriba
de su promedio de 10 meses), escogida después de ver la fase 5 en desarrollo y declarada así
(``fase7_preregistro.md``): la escalera de la fase 7 no dejó candidato.

Se evalúa en la validación de EE. UU. (2016 en adelante) y en los ocho mercados sellados,
con la misma contabilidad de la fase 0, y se aplica el criterio de protección: al menos 30%
menos de caída máxima con un costo de a lo más 25 pb al año contra aportar siempre.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.investigacion import datos, exploracion, mercados, muestras
from src.investigacion.diseno import CRITERIOS, MUESTRAS
from src.investigacion.exploracion import mercado
from src.investigacion.muestras import Muestra
from src.investigacion.simulacion import Modo, benchmark, simular

MODELO = "proteccion-tendencia-10m"
DESCRIPCION = {
    "regla": "dentro si el precio de fin de mes está arriba de su promedio de 10 meses; si no, en efectivo",
    "modo": "rebalancea toda la riqueza cada mes (aportando 1,000 al mes)",
    "parametros_estimados": "ninguno",
    "origen": "escogida después de ver la fase 5 en desarrollo (declarado en fase7_preregistro.md)",
}


def exposicion_tendencia(indice_precio: pd.Series) -> pd.Series:
    t = indice_precio / indice_precio.rolling(10).mean() - 1
    return (t > 0).astype(float).where(t.notna())


def evaluar_mercado(x: pd.DataFrame, nombre: str) -> dict:
    """La regla contra aportar siempre en un mercado, desde que la tendencia tiene historia."""
    e = exposicion_tendencia(x["indice_precio"])
    x = x[e.notna() & x["efectivo"].notna() & x["retorno_total"].notna()]
    e = e.loc[x.index]
    m = mercado(x)
    base = benchmark(m)
    r = simular(m, e.to_numpy(), modo=Modo.EXPOSICION)
    rezago = simular(m, e.to_numpy(), modo=Modo.EXPOSICION, rezago=CRITERIOS.rezago_de_ejecucion_meses)
    caro = simular(m, e.to_numpy(), modo=Modo.EXPOSICION, multiplicador_de_costos=CRITERIOS.multiplicador_de_costos)

    def protege(regla) -> bool:
        reduccion = 1 - regla.caida_maxima / base.caida_maxima if base.caida_maxima < 0 else 0.0
        return bool(reduccion >= CRITERIOS.reduccion_minima_de_caida
                    and regla.tir - base.tir >= -CRITERIOS.costo_maximo_de_la_proteccion)

    return {"mercado": nombre, "desde": x.index.min(), "hasta": x.index.max(), "meses": len(x),
            "tir_aportar_siempre": base.tir, "tir_regla": r.tir, "mejora": r.tir - base.tir,
            "caida_aportar_siempre": base.caida_maxima, "caida_regla": r.caida_maxima,
            "reduccion_de_caida": 1 - r.caida_maxima / base.caida_maxima if base.caida_maxima < 0 else np.nan,
            "exposicion": r.exposicion_promedio, "cambios": r.cambios,
            "mejora_con_rezago": rezago.tir - base.tir, "caida_con_rezago": rezago.caida_maxima,
            "mejora_doble_costo": caro.tir - base.tir,
            "protege": protege(r), "protege_con_rezago": protege(rezago), "protege_doble_costo": protege(caro),
            "cuenta": len(x) >= MUESTRAS.meses_minimos_por_mercado}


def serie_de_mercado(nombre: str, *, raiz=None, ruta_bitacora=None) -> tuple[pd.DataFrame, str]:
    spec = datos.MERCADOS_FINALES[nombre]
    abrir = lambda parte: muestras.abrir_sellado(f"{nombre}_{parte}", modelo_congelado=MODELO,  # noqa: E731
                                                 raiz=raiz, ruta_bitacora=ruta_bitacora)
    precios = abrir("precios")
    precios["fecha"] = pd.to_datetime(precios["fecha"])
    dividendos = abrir("dividendos")
    dividendos["fecha_ex"] = pd.to_datetime(dividendos["fecha_ex"])
    tasas = abrir("tasas")
    tasas["fecha"] = pd.to_datetime(tasas["fecha"])
    x, origen = mercados.serie_principal(precios, dividendos, spec["etf"], spec["canasta"])
    return mercados.armar(x, tasas, spec["tasa_corta"], spec["tasa_larga"]), origen


@dataclass
class ResultadoFase8:
    validacion: dict
    mercados: pd.DataFrame
    conjunto: dict
    veredicto: str
    apuestas: int
    serie_eeuu: pd.DataFrame = None     # el índice de EE. UU. y la exposición de la tendencia, 1972 en adelante


def correr(*, ruta_bitacora=None, raiz=None) -> ResultadoFase8:
    if MODELO not in muestras.bitacora.modelos_congelados(ruta_bitacora):
        muestras.congelar(MODELO, DESCRIPCION, ruta_bitacora=ruta_bitacora)
    # Validación de EE. UU.: la regla con toda la historia, simulada desde 2016.
    completo = exploracion.sector(Muestra.VALIDACION, motivo="fase 8: protección por tendencia congelada",
                                  ruta_bitacora=ruta_bitacora)
    # La tendencia trae su historia de antes de 2016; la simulación empieza en 2016.
    validacion = _desde(completo, MUESTRAS.validacion_desde, "EE. UU. (validación, 2016 en adelante)")
    filas = []
    for nombre in datos.MERCADOS_FINALES:
        x, origen = serie_de_mercado(nombre, raiz=raiz, ruta_bitacora=ruta_bitacora)
        r = evaluar_mercado(x, nombre)
        r["serie"] = origen
        filas.append(r)
    d = pd.DataFrame(filas)
    cuentan = d[d["cuenta"]]
    conjunto = {"mejora": float(cuentan["mejora"].mean()),
                "reduccion_de_caida": float(cuentan["reduccion_de_caida"].mean()),
                "mejora_con_rezago": float(cuentan["mejora_con_rezago"].mean()),
                "mejora_doble_costo": float(cuentan["mejora_doble_costo"].mean()),
                "mercados": int(len(cuentan)),
                "fraccion_protege": float(cuentan["protege"].mean()),
                "fraccion_protege_con_rezago": float(cuentan["protege_con_rezago"].mean()),
                "fraccion_protege_doble_costo": float(cuentan["protege_doble_costo"].mean())}

    def cumple(mejora, reduccion) -> bool:
        return reduccion >= CRITERIOS.reduccion_minima_de_caida and mejora >= -CRITERIOS.costo_maximo_de_la_proteccion

    apuestas = int(cuentan["cambios"].sum()) + int(validacion["cambios"])
    todo = (cumple(conjunto["mejora"], conjunto["reduccion_de_caida"])
            and conjunto["fraccion_protege"] >= CRITERIOS.fraccion_de_mercados_a_favor
            and conjunto["fraccion_protege_con_rezago"] >= CRITERIOS.fraccion_de_mercados_a_favor
            and conjunto["fraccion_protege_doble_costo"] >= CRITERIOS.fraccion_de_mercados_a_favor
            and apuestas >= CRITERIOS.apuestas_efectivas_minimas)
    # «Le gana a aportar siempre en desarrollo y validación»: en desarrollo la tendencia ganó +15 pb (fase 5).
    gana_dev_y_val = validacion["mejora"] > 0
    from src.investigacion.diseno import veredicto

    serie = pd.DataFrame({"fecha": completo.index, "indice_precio": completo["indice_precio"].to_numpy(),
                          "indice_total": completo["indice_total"].to_numpy(),
                          "exposicion": exposicion_tendencia(completo["indice_precio"]).to_numpy()})
    return ResultadoFase8(validacion, d, conjunto,
                          veredicto(le_gana_en_desarrollo_y_validacion=gana_dev_y_val, cumple_todo_en_la_final=todo),
                          apuestas, serie)


def _desde(completo: pd.DataFrame, desde: pd.Timestamp, nombre: str) -> dict:
    e = exposicion_tendencia(completo["indice_precio"])
    x = completo.loc[desde:]
    m = mercado(x)
    ex = e.loc[desde:].to_numpy()
    base = benchmark(m)
    r = simular(m, ex, modo=Modo.EXPOSICION)
    rezago = simular(m, ex, modo=Modo.EXPOSICION, rezago=CRITERIOS.rezago_de_ejecucion_meses)
    caro = simular(m, ex, modo=Modo.EXPOSICION, multiplicador_de_costos=CRITERIOS.multiplicador_de_costos)
    return {"mercado": nombre, "desde": x.index.min(), "hasta": x.index.max(), "meses": len(x),
            "tir_aportar_siempre": base.tir, "tir_regla": r.tir, "mejora": r.tir - base.tir,
            "caida_aportar_siempre": base.caida_maxima, "caida_regla": r.caida_maxima,
            "reduccion_de_caida": 1 - r.caida_maxima / base.caida_maxima if base.caida_maxima < 0 else np.nan,
            "exposicion": r.exposicion_promedio, "cambios": r.cambios,
            "mejora_con_rezago": rezago.tir - base.tir, "caida_con_rezago": rezago.caida_maxima,
            "mejora_doble_costo": caro.tir - base.tir}



NOMBRES = {"japon": "Japón", "australia": "Australia", "singapur": "Singapur", "hong_kong": "Hong Kong",
           "reino_unido": "Reino Unido", "europa_continental": "Europa continental", "canada": "Canadá",
           "mexico_fibras": "FIBRAs (México)"}


def informe(r: ResultadoFase8) -> str:
    from src.investigacion.fase5 import _p, _pb, _tabla

    v, c = r.validacion, r.conjunto
    o = ["# Fase 8: la prueba final. Resultados\n\n",
         "Modelo congelado en la bitácora antes de abrir nada: **protección por tendencia** (dentro si el precio "
         "está arriba de su promedio de 10 meses; si no, en efectivo), escogido después de ver la fase 5 en "
         "desarrollo, como declara `fase7_preregistro.md`. La escalera de la fase 7 no dejó candidato. Cada "
         "mercado en su moneda y con su tasa corta como efectivo; misma contabilidad que la fase 0 (aportación "
         "mensual, impuestos del SIC, comisiones). Generado por `python scripts/investigacion.py fase8`.\n\n",
         f"## Veredicto: **{r.veredicto}**\n\n"]
    o.append(f"El criterio de protección pide al menos 30% menos de caída máxima con un costo de a lo más 25 pb al "
             f"año. En el conjunto de los {c['mercados']} mercados la caída bajó {_p(c['reduccion_de_caida'], 0)} en "
             f"promedio, pero la TIR quedó {_pb(c['mejora'])} pb al año contra aportar siempre; solo "
             f"{c['fraccion_protege']:.0%} de los mercados cumplió el criterio, y con un mes de retraso, "
             f"{c['fraccion_protege_con_rezago']:.0%}. En la validación de EE. UU. (2016 en adelante) la caída bajó "
             f"de {_p(v['caida_aportar_siempre'], 0)} a {_p(v['caida_regla'], 0)}, a un costo de {_pb(v['mejora'])} pb "
             "al año. **La tendencia sí reduce las caídas, pero fuera de la muestra en la que se escogió cuesta "
             "mucho más de lo que el criterio tolera**: sale tarde, después de la caída, y vuelve tarde, después "
             "del rebote; y cada salida paga impuesto sobre la ganancia.\n\n")
    filas = [[v["mercado"], f"{v['desde']:%m-%Y} a {v['hasta']:%m-%Y}", _p(v["tir_aportar_siempre"], 2), _pb(v["mejora"]),
              _p(v["caida_aportar_siempre"], 0), _p(v["caida_regla"], 0), _p(v["reduccion_de_caida"], 0),
              _p(v["exposicion"], 0), _pb(v["mejora_con_rezago"]), "—"]]
    for _, f in r.mercados.iterrows():
        filas.append([f"{NOMBRES.get(f['mercado'], f['mercado'])} ({f['serie']})", f"{f['desde']:%m-%Y} a {f['hasta']:%m-%Y}",
                      _p(f["tir_aportar_siempre"], 2), _pb(f["mejora"]), _p(f["caida_aportar_siempre"], 0),
                      _p(f["caida_regla"], 0), _p(f["reduccion_de_caida"], 0), _p(f["exposicion"], 0),
                      _pb(f["mejora_con_rezago"]), "sí" if f["protege"] else "no"])
    o.append(_tabla(filas, ["Mercado", "Periodo", "TIR aportando siempre", "Tendencia contra aportar (pb/año)",
                            "Caída aportando siempre", "Caída con tendencia", "Reducción de caída", "Exposición",
                            "Con un mes de retraso (pb)", "Cumple protección"]))
    o.append(f"Apuestas efectivas (cambios de postura sumados): {r.apuestas}. Las canastas de Singapur, Hong Kong y "
             "las FIBRAs son de los REITs que cotizan hoy (sesgo de supervivencia, declarado en la fase 0).\n")
    return "".join(o)
