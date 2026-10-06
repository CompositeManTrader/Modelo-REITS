"""Fase 4: el catálogo de señales de entrada al sector, fijado antes de evaluarlas.

Cada señal está orientada para que **más alto sea mejor para los REITs** (más retorno
esperado contra el efectivo). Se calculan con ``exploracion.indicadores``, que solo usa lo
que se conocía al cierre de cada mes (P1). Cada una lleva la regla con la que se convierte
en exposición; no se prueban otras reglas sobre la misma señal. El porqué de cada una, con
su fuente, está en ``docs/investigacion/fase4_preregistro.md``.
"""

from __future__ import annotations

import pandas as pd

from src.investigacion.timing import (
    Senal,
    exposicion_binaria_por_percentil,
    exposicion_continua,
    exposicion_por_signo,
)

# Las dos reglas para señales de nivel: fuera solo en el quintil más desfavorable de su
# propia historia, o exposición continua entre 50% y 100% según su percentil.
UMBRAL_DE_SALIDA = 0.20
PISO_CONTINUO = 0.50
MINIMO_DE_HISTORIA = 60     # meses antes de que un percentil cuente


def _col(nombre: str, signo: float = 1.0):
    return lambda x, i: signo * i[nombre]


CATALOGO: tuple[Senal, ...] = (
    # Valuación: el yield de los REITs contra su historia y contra las alternativas.
    Senal("yield de los REITs", "valuacion", _col("yield_reit"), "Yield de dividendo del índice"),
    Senal("yield contra el Treasury", "valuacion", _col("spread_10a"), "Yield menos Treasury a 10 años"),
    Senal("yield contra la tasa real", "valuacion", _col("spread_real"),
          "Yield menos (Treasury a 10 años menos inflación de 12 meses)"),
    Senal("yield contra bonos Baa", "valuacion", _col("spread_baa"), "Yield menos bonos corporativos Baa"),
    # Crédito y tasas.
    Senal("spread de crédito", "credito", _col("spread_credito", -1), "Baa menos Treasury a 10 años (más ancho, peor)"),
    Senal("cambio del spread de crédito", "credito", _col("cambio_credito_12m", -1),
          "Cambio de 12 meses del spread Baa (si se abre, peor)"),
    Senal("cambio del Treasury", "tasas", _col("cambio_treasury_12m", -1), "Cambio de 12 meses del Treasury a 10 años"),
    Senal("pendiente de la curva", "tasas", _col("curva"), "Treasury a 10 años menos el de 1 año"),
    Senal("cambio de la tasa de la Fed", "tasas", _col("fed_cambio_12m", -1), "Cambio de 12 meses de los fondos federales"),
    Senal("condiciones financieras", "credito", _col("nfci", -1), "Índice de condiciones financieras de Chicago (NFCI)"),
    Senal("crédito bancario a inmuebles", "credito", _col("credito_inmuebles", -1),
          "Bancos que endurecen el crédito a inmuebles comerciales (SLOOS); desde 1990"),
    Senal("cambio del desempleo", "macro", _col("desempleo_cambio_12m", -1), "Cambio de 12 meses de la tasa de desempleo"),
    # Tendencia.
    Senal("tendencia de 10 meses", "tendencia", _col("tendencia_10m"), "Precio contra su promedio de 10 meses"),
    Senal("momentum de 12 meses", "tendencia", _col("momentum_12m"), "Retorno total de los últimos 12 meses"),
)

TENDENCIA = {"tendencia", }


def reglas_de(senal: Senal) -> dict[str, callable]:
    """Las reglas fijadas para una señal: la tendencia va por signo; las de nivel, por percentil."""
    if senal.familia in TENDENCIA:
        return {"signo": exposicion_por_signo}
    return {
        f"fuera en el quintil peor ({UMBRAL_DE_SALIDA:.0%})":
            lambda s: exposicion_binaria_por_percentil(s, UMBRAL_DE_SALIDA, minimo=MINIMO_DE_HISTORIA),
        f"continua con piso de {PISO_CONTINUO:.0%}":
            lambda s: exposicion_continua(s, minimo=MINIMO_DE_HISTORIA, piso=PISO_CONTINUO),
    }


def por_nombre(nombre: str) -> Senal:
    return next(s for s in CATALOGO if s.nombre == nombre)


def calcular(senal: Senal, x: pd.DataFrame, ind: pd.DataFrame) -> pd.Series:
    return senal.calcular(x, ind).reindex(x.index)
