"""Las reglas del juego de la investigación, fijadas antes de tocar los datos (fase 0).

El texto completo, con su porqué, está en ``docs/investigacion/PLAN.md``. Aquí viven los
números, para que el código no pueda usar otros: la prueba 60 los congela. Si uno tiene
que cambiar, el cambio va en el historial con su motivo y antes de correr lo que afecta.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.config import (
    ISR_ADICIONAL_MEXICO_DIVIDENDO_EXTRANJERO,
    RETENCION_EEUU_W8BEN,
    TASA_CEDULAR_GANANCIAS_SIC,
)

FECHA_DEL_DISENO = pd.Timestamp("2026-10-06")


@dataclass(frozen=True)
class Objetivo:
    """Qué se optimiza y contra qué se compara (decisiones del inversionista, 6-oct-2026)."""

    metrica_principal: str = "TIR money-weighted después de impuestos, aportando cada mes (P9)"
    metrica_secundaria: str = "caída máxima de la riqueza"
    benchmark: str = "aportar siempre la misma cantidad al mismo activo (P6)"
    alternativa: str = "T-bill a 3 meses en dólares (FRED DTB3)"
    aportacion_mensual: float = 1_000.0
    exposicion_minima: float = 0.0          # sin apalancamiento ni cortos
    exposicion_maxima: float = 1.0
    impuesto_dividendo: float = RETENCION_EEUU_W8BEN + ISR_ADICIONAL_MEXICO_DIVIDENDO_EXTRANJERO
    impuesto_intereses: float = RETENCION_EEUU_W8BEN + ISR_ADICIONAL_MEXICO_DIVIDENDO_EXTRANJERO
    impuesto_ganancia: float = TASA_CEDULAR_GANANCIAS_SIC
    comision: float = 0.0025                # por compra y por venta
    horizontes_meses: tuple[int, ...] = (1, 3, 12, 36, 60)


@dataclass(frozen=True)
class Muestras:
    """Cómo se parten los datos antes de verlos. ``muestras.py`` lo hace cumplir."""

    desarrollo_hasta: pd.Timestamp = pd.Timestamp("2015-12-31")
    validacion_desde: pd.Timestamp = pd.Timestamp("2016-01-01")
    # Prueba final: mercados que no se han visto y un tercio de los emisores de EE. UU.
    mercados_finales: tuple[str, ...] = ("japon", "australia", "singapur", "hong_kong", "reino_unido",
                                         "europa_continental", "canada", "mexico_fibras")
    meses_minimos_por_mercado: int = 60
    fraccion_de_emisores_sellados: float = 1 / 3
    semilla_de_emisores: str = "modelo-reits-investigacion-2026-10-06"


@dataclass(frozen=True)
class Criterios:
    """Lo que tiene que cumplir un modelo en la prueba final para declararse APROBADO."""

    mejora_minima_de_tir: float = 0.0050             # +50 pb al año contra aportar siempre
    reduccion_minima_de_caida: float = 0.30          # o 30% menos de caída máxima (relativa)...
    costo_maximo_de_la_proteccion: float = 0.0025    # ...costando a lo más 25 pb al año
    fraccion_de_mercados_a_favor: float = 2 / 3
    r2_fuera_de_muestra_minimo: float = 0.0          # contra el promedio histórico
    alfa_clark_west: float = 0.05
    sharpe_deflactado_minimo: float = 0.95
    pbo_maximo: float = 0.20
    apuestas_efectivas_minimas: int = 100            # P7, sumando mercados
    rezago_de_ejecucion_meses: int = 1               # robustez: decidir un mes y ejecutar el siguiente
    multiplicador_de_costos: float = 2.0             # robustez: el doble de comisión


@dataclass(frozen=True)
class WalkForward:
    """Cómo se estima un modelo sin mirar el futuro (fase 7)."""

    meses_minimos_para_estimar: int = 120
    reestimar_cada_meses: int = 12
    ventana: str = "creciente"
    hiperparametros: str = "escogidos con validación cruzada temporal dentro del pasado"


OBJETIVO = Objetivo()
MUESTRAS = Muestras()
CRITERIOS = Criterios()
WALK_FORWARD = WalkForward()

VEREDICTOS = ("APROBADO", "INCONCLUSO", "RECHAZADO")


def veredicto(*, le_gana_en_desarrollo_y_validacion: bool, cumple_todo_en_la_final: bool) -> str:
    """La regla de la fase 0: APROBADO solo si cumple todo en la prueba final."""
    if cumple_todo_en_la_final:
        return "APROBADO"
    return "INCONCLUSO" if le_gana_en_desarrollo_y_validacion else "RECHAZADO"
