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
    # Valuación (literatura T2 y T3): el yield de los REITs contra su historia y sus alternativas.
    Senal("yield de los REITs", "valuacion", _col("yield_reit"), "Yield de dividendo del índice",
          "Chiang (2015); Liu y Mei (1992). En contra: Ghysels et al. (2013)"),
    Senal("yield contra el Treasury", "valuacion", _col("spread_10a"), "Yield menos Treasury a 10 años",
          "Nareit, Case (2017a)"),
    Senal("yield contra la tasa real", "valuacion", _col("spread_real"),
          "Yield menos (Treasury a 10 años menos inflación de 12 meses)", "Nareit, Case (2017a), variante real"),
    Senal("yield contra bonos Baa", "valuacion", _col("spread_baa"), "Yield menos bonos corporativos Baa",
          "Nareit, Case (2018)"),
    # Crédito (literatura T4 y T5).
    Senal("spread de default", "credito", _col("spread_default"), "Bonos Baa menos Aaa (más ancho, más prima)",
          "Leow y Lindenthal (2024)"),
    Senal("cambio del spread de crédito", "credito", _col("cambio_credito_12m", -1),
          "Cambio de 12 meses del spread Baa contra el Treasury (si se abre, peor)",
          "Leow y Lindenthal (2024); Swanson, Theis y Casey (2002)"),
    Senal("condiciones financieras", "credito", _col("nfci", -1),
          "Índice de condiciones financieras de la Fed de Chicago (más estrés, peor)",
          "Leow y Lindenthal (2024), volatilidad y crédito"),
    Senal("crédito bancario a inmuebles", "credito", _col("credito_inmuebles", -1),
          "Bancos que endurecen el crédito a inmuebles comerciales (SLOOS); desde 1990",
          "Ling, Naranjo y Scheick (2016)"),
    # Bolsa del mes (literatura T6): el único predictor con R² fuera de muestra positivo en Ghysels et al.
    Senal("bolsa del mes", "bolsa", _col("bolsa_mes"), "Retorno total de la bolsa de EE. UU. en el mes",
          "Ghysels, Plazzi, Torous y Valkanov (2013)"),
    # Tendencia (literatura T1 y T1b).
    Senal("tendencia de 10 meses", "tendencia", _col("tendencia_10m"), "Precio contra su promedio de 10 meses",
          "Faber (2007); Glabadanidis (2014). En contra: Zakamulin (2014)"),
    Senal("momentum contra el efectivo", "tendencia", _col("momentum_exceso_12m"),
          "Retorno total de 12 meses menos el del T-bill", "Moskowitz, Ooi y Pedersen (2012); Moss et al. (2015)"),
)

# Descartadas ANTES de correr porque la literatura ya las contradice o no tienen respaldo;
# no son intentos de la bitácora (ver el pre-registro).
DESCARTADAS = {
    "cambio del Treasury": "Nareit, Pierzak (2026): REITs positivos en 77% de los periodos de alza y 79% de baja",
    "pendiente de la curva": "Ghysels et al. (2013): R² fuera de muestra de −0.49% mensual",
    "cambio de la tasa de la Fed": "Solo cuatro ciclos y la última alza se conoce después (Pierzak 2023)",
    "cambio del desempleo": "Sin respaldo en la literatura revisada",
    "spread de crédito (nivel, con signo negativo)": "Sustituida por el spread de default con el signo de la literatura",
}

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
