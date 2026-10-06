"""Fase 5: el banco de pruebas de las señales de entrada al sector.

Una señal es una serie mensual, conocida al cierre de cada mes (P1), en la que **más alto
quiere decir más retorno esperado de los REITs contra el efectivo**. El banco la convierte
en exposición con una de las reglas fijadas en la fase 4, la simula con la misma máquina
que el benchmark y mide todo lo que piden los criterios de la fase 0:

* si predice el retorno siguiente mejor que el promedio histórico (R² fuera de muestra y
  Clark-West, a 1, 3 y 12 meses);
* cuánto le gana a aportar siempre, decidiendo solo el dinero nuevo y rebalanceando;
* contra una mezcla fija con la misma exposición promedio (P8): si la regla gana solo por
  estar menos invertida, no es timing;
* con un mes de retraso y con el doble de comisión;
* cuántas apuestas efectivas tiene (P7).

Cada evaluación queda en la bitácora.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.investigacion import bitacora, estadistica
from src.investigacion.exploracion import _adelante, mercado
from src.investigacion.simulacion import Modo, benchmark, simular
from src.modelo.senal import percentil_expandible


@dataclass(frozen=True)
class Senal:
    nombre: str
    familia: str
    calcular: Callable[[pd.DataFrame, pd.DataFrame], pd.Series]   # (sector, indicadores) -> serie
    descripcion: str
    fuente: str = ""


# --------------------------------------------------------------------------------------
# De señal a exposición
# --------------------------------------------------------------------------------------


def exposicion_binaria_por_percentil(s: pd.Series, umbral: float, *, minimo: int = 60) -> pd.Series:
    """Dentro (1) si la señal está en su percentil ``umbral`` o arriba contra su propia historia."""
    p = percentil_expandible(s.dropna(), min_observaciones=minimo).reindex(s.index)
    return (p >= umbral).astype(float).where(p.notna(), 1.0)


def exposicion_por_signo(s: pd.Series) -> pd.Series:
    """Dentro si la señal es positiva (tendencia, momentum). Sin dato, dentro."""
    return (s > 0).astype(float).where(s.notna(), 1.0)


def exposicion_continua(s: pd.Series, *, minimo: int = 60, piso: float = 0.0) -> pd.Series:
    """La exposición es el percentil expandible de la señal, con un piso."""
    p = percentil_expandible(s.dropna(), min_observaciones=minimo).reindex(s.index)
    return (piso + (1 - piso) * p).where(p.notna(), 1.0)


# --------------------------------------------------------------------------------------
# Evaluación
# --------------------------------------------------------------------------------------


def predictibilidad(s: pd.Series, x: pd.DataFrame, horizontes=(1, 3, 12), minimo: int = 120,
                    desde: pd.Timestamp | None = None) -> pd.DataFrame:
    """R² fuera de muestra y Clark-West del retorno en exceso siguiente contra la señal.

    El pronóstico de cada mes se estima con toda la historia anterior; ``desde`` solo limita
    los meses que se califican (la validación califica 2016 en adelante).
    """
    filas = []
    for h in horizontes:
        exceso = _adelante(x["retorno_total"], h) - _adelante(x["efectivo"], h)
        # Las señales están orientadas (más alto = mejor): la pendiente teórica es positiva.
        p = estadistica.pronostico_expandible(s, exceso, minimo=minimo, horizonte=h, signo=+1)
        if desde is not None:
            p = p.loc[desde:]
        t, valor_p = estadistica.clark_west(p["real"], p["pronostico"], p["promedio"], rezago=h)
        filas.append({"horizonte_meses": h, "r2_fuera_de_muestra":
                      estadistica.r2_fuera_de_muestra(p["real"], p["pronostico"], p["promedio"]),
                      "clark_west_t": t, "clark_west_p": valor_p,
                      "meses_evaluados": int(p[["real", "pronostico"]].notna().all(axis=1).sum())})
    return pd.DataFrame(filas)


def evaluar(senal: Senal, regla: str, exposicion: pd.Series, x: pd.DataFrame, ind: pd.DataFrame, *,
            muestra: str, parametros: dict | None = None, registrar: bool = True, desde: pd.Timestamp | None = None,
            ruta_bitacora=None) -> dict:
    """Todas las métricas de una regla de exposición sobre el sector ``x``.

    Con ``desde``, la simulación empieza ese mes (la señal ya trae su historia) y la
    predictibilidad se califica desde ahí con pronósticos estimados con todo lo anterior.
    """
    completo = x
    if desde is not None:
        x = x.loc[desde:]
    m = mercado(x)
    e = exposicion.reindex(x.index).to_numpy(dtype=float)
    base = benchmark(m)
    salida = {"senal": senal.nombre, "familia": senal.familia, "regla": regla, "muestra": muestra,
              "desde": x.index.min(), "hasta": x.index.max(), "tir_aportar_siempre": base.tir,
              "caida_aportar_siempre": base.caida_maxima}
    for modo in (Modo.APORTACION, Modo.EXPOSICION):
        clave = "nuevo" if modo is Modo.APORTACION else "rebalanceo"
        r = simular(m, e, modo=modo)
        salida[f"tir_{clave}"] = r.tir
        salida[f"mejora_{clave}"] = r.tir - base.tir
        salida[f"caida_{clave}"] = r.caida_maxima
        salida[f"exposicion_{clave}"] = r.exposicion_promedio
        salida[f"cambios_{clave}"] = r.cambios
        if modo is Modo.EXPOSICION:
            fija = simular(m, r.exposicion_promedio, modo=Modo.EXPOSICION)
            salida["tir_mezcla_fija"] = fija.tir
            salida["mejora_contra_mezcla_fija"] = r.tir - fija.tir
            salida["caida_mezcla_fija"] = fija.caida_maxima
            con_rezago = simular(m, e, modo=modo, rezago=1)
            salida["mejora_rebalanceo_con_rezago"] = con_rezago.tir - base.tir
            caro = simular(m, e, modo=modo, multiplicador_de_costos=2.0)
            salida["mejora_rebalanceo_doble_costo"] = caro.tir - base.tir
            salida["apuestas_efectivas"] = estadistica.apuestas_efectivas(len(x), 12, r.cambios)
    s = senal.calcular(completo, ind).reindex(completo.index)
    pr = predictibilidad(s, completo, desde=desde).set_index("horizonte_meses")
    for h, f in pr.iterrows():
        salida[f"r2_{h}m"] = f["r2_fuera_de_muestra"]
        salida[f"clark_west_p_{h}m"] = f["clark_west_p"]
    if registrar:
        bitacora.registrar(fase="5", familia=senal.familia, prueba=f"{senal.nombre} | {regla}", muestra=muestra,
                           parametros=parametros or {}, metrica="mejora_rebalanceo",
                           valor=round(float(salida["mejora_rebalanceo"]), 6), ruta=ruta_bitacora)
    return salida


def retornos_de_la_regla(exposicion: pd.Series, x: pd.DataFrame) -> pd.Series:
    """Retorno mensual en exceso del efectivo de la cartera que sigue la regla (para PBO y Sharpe).

    La exposición decidida al cierre de ``t`` gana el retorno de ``t + 1``.
    """
    e = exposicion.reindex(x.index).shift(1)
    return (e * (x["retorno_total"] - x["efectivo"])).dropna()


def resumen(evaluaciones: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(evaluaciones).replace([np.inf, -np.inf], np.nan)
