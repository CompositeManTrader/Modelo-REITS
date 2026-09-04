"""Monte Carlo con bootstrap por bloques y tres procesos separados.

Por qué bloques y no i.i.d.
---------------------------
Remuestrear observaciones sueltas destruye la autocorrelación, y con ella el
riesgo que de verdad quiebra un plan de retiro: las malas rachas. Una simulación
i.i.d. produce trayectorias demasiado amables y una probabilidad de ruina
sistemáticamente subestimada. El bootstrap por bloques conserva la estructura.

Por qué tres procesos
---------------------
El retorno de un REIT tiene tres motores con dinámicas distintas:

* **Yield** — persistente, acotado, tirado por la política de dividendos.
* **Crecimiento del AFFO por acción** — ligado al ciclo del inmueble y a la dilución.
* **Cambio de múltiplo** — el más volátil y el más ligado a la tasa de 10 años.

Modelarlos juntos como "retorno total" pierde justo lo que interesa: que el
múltiplo puede comerse cinco años de crecimiento en seis meses.

Riesgo de secuencia
-------------------
La misma media con distinto orden quiebra o no el plan. Con retiros, los años
malos al principio son cualitativamente peores que al final. Por eso se reporta
P(quedarse sin capital) y la distribución de riqueza terminal, no solo el promedio.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------
# Bootstrap por bloques
# --------------------------------------------------------------------------------------


def bootstrap_bloques(
    serie: np.ndarray | pd.Series,
    n_periodos: int,
    *,
    tamano_bloque: int = 12,
    rng: np.random.Generator | None = None,
    circular: bool = True,
) -> np.ndarray:
    """Remuestrea bloques contiguos para preservar la autocorrelación.

    ``tamano_bloque`` debe cubrir el horizonte de la dependencia que interesa
    conservar. Para series mensuales de REITs, 12 meses captura el ciclo de tasas;
    bloques de 1 equivalen a i.i.d. y no deberían usarse.
    """
    datos = np.asarray(pd.Series(serie).dropna(), dtype=float)
    if datos.size == 0:
        raise ValueError("La serie está vacía.")
    if tamano_bloque < 1:
        raise ValueError("El tamaño de bloque debe ser al menos 1.")
    rng = rng or np.random.default_rng()

    n_bloques = int(np.ceil(n_periodos / tamano_bloque))
    if circular:
        inicios = rng.integers(0, len(datos), size=n_bloques)
        piezas = [np.take(datos, range(i, i + tamano_bloque), mode="wrap") for i in inicios]
    else:
        maximo = max(1, len(datos) - tamano_bloque + 1)
        inicios = rng.integers(0, maximo, size=n_bloques)
        piezas = [datos[i : i + tamano_bloque] for i in inicios]
    return np.concatenate(piezas)[:n_periodos]


def bootstrap_bloques_multivariado(
    panel: pd.DataFrame,
    n_periodos: int,
    *,
    tamano_bloque: int = 12,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """Remuestrea bloques del panel completo, preservando la correlación **entre** series.

    Es la diferencia entre simular yield y múltiplo por separado — que produce
    combinaciones que nunca ocurrieron — y remuestrear filas completas, que
    conserva el hecho de que el múltiplo se comprime cuando las tasas suben.
    """
    df = panel.dropna()
    if df.empty:
        raise ValueError("El panel está vacío tras eliminar faltantes.")
    rng = rng or np.random.default_rng()
    n_bloques = int(np.ceil(n_periodos / tamano_bloque))
    inicios = rng.integers(0, len(df), size=n_bloques)
    filas = np.concatenate([np.arange(i, i + tamano_bloque) % len(df) for i in inicios])[:n_periodos]
    return df.iloc[filas].reset_index(drop=True)


# --------------------------------------------------------------------------------------
# Simulación de retiro
# --------------------------------------------------------------------------------------


@dataclass
class SupuestosSimulacion:
    """Supuestos de la simulación. Todos son inputs del usuario, no verdades."""

    capital_inicial: float
    retiro_anual_real: float
    anios: int = 30
    n_trayectorias: int = 5_000
    tamano_bloque: int = 12
    periodos_por_anio: int = 12
    inflacion_media: float = 0.04
    semilla: int = 42


@dataclass
class ResultadoMonteCarlo:
    trayectorias: np.ndarray  # (n_trayectorias, n_periodos+1)
    riqueza_terminal: np.ndarray
    prob_ruina: float
    supuestos: SupuestosSimulacion
    percentiles: dict[str, float] = field(default_factory=dict)
    anio_ruina_mediano: float | None = None

    def como_texto(self) -> str:
        p = self.percentiles
        base = (
            f"Sobre {self.supuestos.n_trayectorias:,} trayectorias a {self.supuestos.anios} años: "
            f"probabilidad de quedarse sin capital {self.prob_ruina:.1%}. "
            f"Riqueza terminal real — P10 {p.get('p10', 0):,.0f}, mediana {p.get('p50', 0):,.0f}, "
            f"P90 {p.get('p90', 0):,.0f}."
        )
        if self.anio_ruina_mediano is not None:
            base += f" En las trayectorias que se agotan, el capital dura {self.anio_ruina_mediano:.0f} años."
        return base

    def tabla_percentiles(self) -> pd.DataFrame:
        return pd.DataFrame(
            [{"percentil": k, "riqueza_terminal_real": v} for k, v in self.percentiles.items()]
        )


def simular_retiro(
    retornos_historicos: pd.Series,
    supuestos: SupuestosSimulacion,
) -> ResultadoMonteCarlo:
    """Simula el plan de retiro con bootstrap por bloques y retiros reales.

    Los retiros son **reales**: se mantiene constante el poder adquisitivo, que es
    lo que el usuario efectivamente necesita gastar. Como los retornos también se
    trabajan en términos reales, no hace falta inflar el retiro cada año.
    """
    rng = np.random.default_rng(supuestos.semilla)
    n_periodos = supuestos.anios * supuestos.periodos_por_anio
    retiro_periodo = supuestos.retiro_anual_real / supuestos.periodos_por_anio

    trayectorias = np.zeros((supuestos.n_trayectorias, n_periodos + 1))
    trayectorias[:, 0] = supuestos.capital_inicial
    periodo_ruina = np.full(supuestos.n_trayectorias, np.nan)

    for i in range(supuestos.n_trayectorias):
        camino = bootstrap_bloques(
            retornos_historicos, n_periodos, tamano_bloque=supuestos.tamano_bloque, rng=rng
        )
        saldo = supuestos.capital_inicial
        for t, r in enumerate(camino, start=1):
            saldo = saldo * (1.0 + r) - retiro_periodo
            if saldo <= 0:
                saldo = 0.0
                if np.isnan(periodo_ruina[i]):
                    periodo_ruina[i] = t
            trayectorias[i, t] = saldo

    terminal = trayectorias[:, -1]
    prob_ruina = float(np.mean(terminal <= 0))
    percentiles = {
        f"p{q}": float(np.percentile(terminal, q)) for q in (5, 10, 25, 50, 75, 90, 95)
    }
    ruinas = periodo_ruina[~np.isnan(periodo_ruina)]
    anio_mediano = (
        float(np.median(ruinas) / supuestos.periodos_por_anio) if ruinas.size else None
    )

    return ResultadoMonteCarlo(
        trayectorias=trayectorias,
        riqueza_terminal=terminal,
        prob_ruina=prob_ruina,
        supuestos=supuestos,
        percentiles=percentiles,
        anio_ruina_mediano=anio_mediano,
    )


# --------------------------------------------------------------------------------------
# Descomposición en tres procesos
# --------------------------------------------------------------------------------------


@dataclass
class ProcesosREIT:
    """Los tres motores del retorno, como series históricas mensuales o trimestrales."""

    yield_periodo: pd.Series
    crecimiento_affo: pd.Series
    cambio_multiplo: pd.Series

    def panel(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "yield": self.yield_periodo,
                "crecimiento_affo": self.crecimiento_affo,
                "cambio_multiplo": self.cambio_multiplo,
            }
        ).dropna()

    def correlaciones(self) -> pd.DataFrame:
        return self.panel().corr()


def simular_por_componentes(
    procesos: ProcesosREIT,
    n_periodos: int,
    n_trayectorias: int = 1_000,
    *,
    tamano_bloque: int = 12,
    semilla: int = 42,
) -> dict[str, np.ndarray]:
    """Simula los tres procesos conjuntamente, preservando su correlación.

    Devuelve las tres componentes por separado además del retorno total, para que
    la interfaz pueda mostrar de dónde viene cada escenario: no es lo mismo un
    escenario malo por compresión de múltiplo (recuperable) que por caída del AFFO
    (estructural).
    """
    rng = np.random.default_rng(semilla)
    panel = procesos.panel()
    salida = {
        k: np.zeros((n_trayectorias, n_periodos))
        for k in ("yield", "crecimiento_affo", "cambio_multiplo", "total")
    }
    for i in range(n_trayectorias):
        muestra = bootstrap_bloques_multivariado(
            panel, n_periodos, tamano_bloque=tamano_bloque, rng=rng
        )
        y = muestra["yield"].to_numpy()
        g = muestra["crecimiento_affo"].to_numpy()
        m = muestra["cambio_multiplo"].to_numpy()
        salida["yield"][i] = y
        salida["crecimiento_affo"][i] = g
        salida["cambio_multiplo"][i] = m
        # (1+r) = (1+g)(1+m) + yield: el precio es múltiplo por AFFO, más el cupón.
        salida["total"][i] = (1.0 + g) * (1.0 + m) - 1.0 + y
    return salida


# --------------------------------------------------------------------------------------
# Sensibilidad a tasas
# --------------------------------------------------------------------------------------


def impacto_shock_de_tasas(
    multiplo_actual: float,
    shock_bps: float,
    *,
    duracion_implicita: float = 6.0,
    correlacion: float = 0.7,
) -> dict[str, float]:
    """Estima el impacto de un shock del bono a 10 años sobre el múltiplo.

    El REIT cotiza como instrumento de duración: su múltiplo es aproximadamente el
    recíproco de una tasa de capitalización, así que un alza de tasas lo comprime.
    ``duracion_implicita`` es la sensibilidad del múltiplo en porcentaje por cada
    100 puntos base, y ``correlacion`` reconoce que el traspaso no es de uno a uno:
    cuando las tasas suben por crecimiento, el AFFO también sube.
    """
    cambio_pct = -duracion_implicita * (shock_bps / 100.0) / 100.0 * correlacion
    nuevo = multiplo_actual * (1.0 + cambio_pct)
    return {
        "shock_bps": float(shock_bps),
        "multiplo_actual": float(multiplo_actual),
        "multiplo_estimado": float(nuevo),
        "cambio_pct": float(cambio_pct),
        "impacto_precio_pct": float(cambio_pct),
    }


def tabla_sensibilidad_tasas(
    multiplo_actual: float, shocks_bps: tuple[float, ...] = (-200, -100, -50, 0, 50, 100, 200, 300)
) -> pd.DataFrame:
    return pd.DataFrame([impacto_shock_de_tasas(multiplo_actual, s) for s in shocks_bps])


# --------------------------------------------------------------------------------------
# Divisa
# --------------------------------------------------------------------------------------


def simular_tipo_de_cambio(
    historico_usdmxn: pd.Series,
    n_periodos: int,
    n_trayectorias: int = 1_000,
    *,
    tamano_bloque: int = 12,
    semilla: int = 42,
) -> np.ndarray:
    """Proceso separado para USD/MXN, porque el gasto del usuario es en pesos.

    Un portafolio de REITs estadounidenses tiene dos fuentes de riesgo que se
    confunden todo el tiempo: el activo y la divisa. Modelarlas juntas esconde que
    parte del "buen rendimiento" de algunos años fue depreciación del peso.
    """
    rng = np.random.default_rng(semilla)
    variaciones = pd.Series(historico_usdmxn).pct_change().dropna()
    if variaciones.empty:
        raise ValueError("El histórico de tipo de cambio no tiene variaciones.")
    caminos = np.zeros((n_trayectorias, n_periodos))
    for i in range(n_trayectorias):
        caminos[i] = bootstrap_bloques(
            variaciones, n_periodos, tamano_bloque=tamano_bloque, rng=rng
        )
    return caminos


def combinar_activo_y_divisa(
    retornos_usd: np.ndarray, variaciones_fx: np.ndarray
) -> np.ndarray:
    """``(1+r_mxn) = (1+r_usd)(1+Δfx)``. El peso débil ayuda; el peso fuerte resta."""
    return (1.0 + retornos_usd) * (1.0 + variaciones_fx) - 1.0


# --------------------------------------------------------------------------------------
# Riesgo de secuencia
# --------------------------------------------------------------------------------------


def riesgo_de_secuencia(
    retornos: pd.Series,
    capital_inicial: float,
    retiro_anual: float,
    *,
    periodos_por_anio: int = 12,
    n_permutaciones: int = 1_000,
    semilla: int = 42,
) -> dict[str, float]:
    """Demuestra que la **misma** media con distinto orden cambia el desenlace.

    Se permuta la serie histórica — misma media, misma varianza, misma distribución
    marginal — y se mide la dispersión de la riqueza terminal. Todo lo que aparezca
    ahí es riesgo de secuencia puro.
    """
    rng = np.random.default_rng(semilla)
    datos = np.asarray(pd.Series(retornos).dropna(), dtype=float)
    if datos.size == 0:
        raise ValueError("La serie está vacía.")
    retiro_periodo = retiro_anual / periodos_por_anio

    terminales = np.zeros(n_permutaciones)
    for i in range(n_permutaciones):
        orden = rng.permutation(datos)
        saldo = capital_inicial
        for r in orden:
            saldo = max(0.0, saldo * (1.0 + r) - retiro_periodo)
        terminales[i] = saldo

    return {
        "media": float(np.mean(terminales)),
        "mediana": float(np.median(terminales)),
        "p5": float(np.percentile(terminales, 5)),
        "p95": float(np.percentile(terminales, 95)),
        "prob_ruina": float(np.mean(terminales <= 0)),
        "dispersion_relativa": float(
            (np.percentile(terminales, 95) - np.percentile(terminales, 5))
            / max(1.0, np.median(terminales))
        ),
    }
