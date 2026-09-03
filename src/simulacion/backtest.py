"""Backtest con las cuatro salvaguardas que separan un edge de una ilusión.

P6 — En backtests, el benchmark es el MISMO activo
==================================================
Si mides una regla de aportación, el benchmark es aportación constante al mismo
papel. Si mides una regla de posición, es comprar y mantener el mismo papel.
Contra cualquier otra cosa estarías midiendo qué tan bueno fue el activo, no qué
aportó la regla.

P7 — Suficiencia estadística: cuenta apuestas efectivas, no observaciones
=========================================================================
Una señal de valuación lenta produce del orden de 10 a 20 episodios de posición en
veinte años, no 240. El umbral para declarar edge es ~100 apuestas efectivas.
Debajo de eso el veredicto es INCONCLUSO, nunca GO.

P8 — Neutraliza beta antes de evaluar cualquier overlay
=======================================================
Una regla que despliega más capital en un activo con deriva alcista tiene Sharpe
positivo aunque la señal sea ruido puro. En pruebas sobre datos sintéticos sin
señal, el Sharpe crudo dio 0.95 con beta de 2.08; neutralizado cayó a 0.31. Se
evalúa el residual de regresar el retorno activo contra el del subyacente.

P9 — Para flujos desiguales, usa TIR money-weighted
====================================================
Comparar riqueza final entre estrategias que despliegan distinto capital es
incorrecto, y normalizar por capital total no corrige el timing. La TIR sí.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.config import MIN_APUESTAS_EFECTIVAS
from src.portafolio.metricas import sharpe, tir

# --------------------------------------------------------------------------------------
# Lag de ejecución (prueba obligatoria 8)
# --------------------------------------------------------------------------------------


def aplicar_lag(senal: pd.Series, periodos: int = 1) -> pd.Series:
    """La señal de ``t`` se ejecuta en ``t+1``.

    No es una cortesía conservadora: la señal de un trimestre se conoce cuando se
    publica el reporte, y ejecutar al precio del mismo día del cierre contable es
    comprar con información que nadie tenía. Todo backtest del proyecto pasa por aquí.
    """
    if periodos < 1:
        raise ValueError("El lag de ejecución debe ser de al menos un periodo.")
    return pd.Series(senal).shift(periodos)


def verificar_lag(senal: pd.Series, posicion_ejecutada: pd.Series, periodos: int = 1) -> bool:
    """Comprueba que la posición ejecutada es exactamente la señal desplazada."""
    esperada = aplicar_lag(senal, periodos)
    a = pd.Series(posicion_ejecutada).astype(float)
    b = esperada.astype(float)
    comun = a.index.intersection(b.index)
    if len(comun) == 0:
        return False
    return bool(np.allclose(a.reindex(comun).fillna(0), b.reindex(comun).fillna(0), atol=1e-12))


# --------------------------------------------------------------------------------------
# Apuestas efectivas (P7)
# --------------------------------------------------------------------------------------


@dataclass
class ConteoApuestas:
    """Cuántas decisiones independientes hay realmente detrás de una métrica."""

    episodios: int
    observaciones: int
    n_efectivo_autocorrelacion: float | None
    suficiente: bool
    umbral: int = MIN_APUESTAS_EFECTIVAS

    def como_texto(self) -> str:
        base = (
            f"{self.episodios} episodios de posición sobre {self.observaciones} observaciones"
        )
        if self.n_efectivo_autocorrelacion is not None:
            base += f"; N efectivo por autocorrelación ≈ {self.n_efectivo_autocorrelacion:.0f}"
        if self.suficiente:
            return base + f". Supera el umbral de {self.umbral} apuestas efectivas."
        return (
            base
            + f". Debajo del umbral de {self.umbral} apuestas efectivas: cualquier métrica de "
            "desempeño aquí es ruido con decimales. El veredicto correcto es INCONCLUSO."
        )


def contar_episodios(
    posicion: pd.Series, benchmark: pd.Series | float = 1.0, *, tolerancia: float = 1e-9
) -> int:
    """Cuenta episodios: rachas contiguas con el mismo **signo** de desvío del benchmark.

    Un episodio es una apuesta. Entrar sobreponderado y quedarse doce meses no son
    doce decisiones, es una; por eso lo que se cuenta es la entrada a un régimen
    (sobreponderado o subponderado), no cada observación dentro de él.

    La distinción importa en las dos direcciones. Una señal de valuación lenta
    produce del orden de 10 a 20 episodios en veinte años, no 240: contar
    observaciones fabricaría significancia estadística que no existe. Y una señal
    de ruido que cambia de lado cada mes sí produce ~120 episodios: ahí la
    suficiencia se cumple y quien tiene que atrapar el ruido es la neutralización
    de beta (P8), no el conteo.
    """
    p = pd.Series(posicion).astype(float).fillna(0.0)
    b = (
        pd.Series(benchmark).astype(float).reindex(p.index).fillna(0.0)
        if isinstance(benchmark, pd.Series)
        else pd.Series(float(benchmark), index=p.index)
    )
    if p.empty:
        return 0
    desvio = (p - b).to_numpy()
    regimen = np.sign(np.where(np.abs(desvio) <= tolerancia, 0.0, desvio))
    episodios = 0
    anterior = 0.0
    for actual in regimen:
        if actual != 0.0 and actual != anterior:
            episodios += 1
        anterior = actual
    return episodios


def n_efectivo_por_autocorrelacion(serie: pd.Series) -> float | None:
    """Tamaño de muestra efectivo ajustado por autocorrelación de primer orden.

    ``N_eff ≈ N (1−ρ)/(1+ρ)``. Es un contraste rápido contra el conteo de episodios:
    una serie muy persistente tiene muchísimas menos observaciones independientes
    de las que aparenta.
    """
    s = pd.Series(serie).dropna().astype(float)
    n = len(s)
    if n < 3:
        return None
    rho = float(s.autocorr(lag=1)) if s.std() > 0 else 0.0
    if np.isnan(rho):
        return float(n)
    rho = min(max(rho, -0.999), 0.999)
    return float(n * (1 - rho) / (1 + rho))


def contar_apuestas(
    posicion: pd.Series,
    referencia: pd.Series | float | str = "mediana",
    *,
    umbral: int = MIN_APUESTAS_EFECTIVAS,
) -> ConteoApuestas:
    """Cuenta las decisiones independientes que hay detrás de la regla.

    Ojo con la distinción, que es sutil y decide el veredicto:

    * El benchmark de **desempeño** es el mismo activo comprado y mantenido (P6).
    * La referencia para **contar decisiones** es el nivel neutral de la propia
      regla, por omisión su mediana.

    No son lo mismo. Una regla que sostiene entre 0% y 100% de posición está casi
    siempre por debajo de un buy-and-hold al 100%: medida contra él sería un solo
    episodio eterno, cuando en realidad estuvo cambiando de opinión decenas de
    veces. Lo que cuenta como apuesta es cambiar de opinión, no quedar
    permanentemente subponderado.
    """
    p = pd.Series(posicion).astype(float)
    if isinstance(referencia, str):
        if referencia != "mediana":
            raise ValueError("La referencia textual admitida es 'mediana'.")
        ref: pd.Series | float = float(p.median()) if p.notna().any() else 0.0
    else:
        ref = referencia
    episodios = contar_episodios(p, ref)
    return ConteoApuestas(
        episodios=episodios,
        observaciones=int(p.notna().sum()),
        n_efectivo_autocorrelacion=n_efectivo_por_autocorrelacion(p),
        suficiente=episodios >= umbral,
        umbral=umbral,
    )


# --------------------------------------------------------------------------------------
# Neutralización de beta (P8)
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoNeutralizacion:
    """Regresión del retorno activo contra el del subyacente."""

    alfa: float
    beta: float
    p_valor_alfa: float
    r2: float
    residuales: pd.Series
    sharpe_crudo: float | None
    sharpe_neutralizado: float | None
    n: int

    def como_texto(self) -> str:
        return (
            f"Beta contra el subyacente: {self.beta:.2f}. Sharpe crudo "
            f"{_fmt(self.sharpe_crudo)} → neutralizado {_fmt(self.sharpe_neutralizado)}. "
            f"Alfa {self.alfa:.4%} por periodo (p={self.p_valor_alfa:.3f}), R²={self.r2:.2f}."
        )


def neutralizar_beta(
    retorno_activo: pd.Series,
    retorno_subyacente: pd.Series,
    *,
    periodos_por_anio: int = 12,
) -> ResultadoNeutralizacion | None:
    """Regresa el retorno de la estrategia contra el del subyacente y evalúa el residual.

    Lo que importa no es el retorno activo crudo sino lo que queda después de quitar
    la exposición direccional. Una regla que simplemente despliega más capital
    cuando el activo sube tiene Sharpe positivo sin ninguna señal detrás.
    """
    a = pd.Series(retorno_activo).dropna().astype(float)
    b = pd.Series(retorno_subyacente).dropna().astype(float)
    comun = a.index.intersection(b.index)
    if len(comun) < 10:
        return None
    a, b = a.reindex(comun), b.reindex(comun)

    X = sm.add_constant(b.to_numpy())
    # Errores estándar HAC (Newey-West). El retorno activo de una regla de
    # aportación es autocorrelado por construcción — el capital desplegado es
    # persistente — y con errores OLS simples eso infla la significancia del alfa.
    # Es exactamente el mecanismo por el que un backtest sin señal reporta edge.
    rezagos = max(1, int(4 * (len(comun) / 100.0) ** (2.0 / 9.0)))
    modelo = sm.OLS(a.to_numpy(), X).fit(cov_type="HAC", cov_kwds={"maxlags": rezagos})
    alfa, beta = float(modelo.params[0]), float(modelo.params[1])
    residuales = pd.Series(modelo.resid, index=comun, name="residual")

    return ResultadoNeutralizacion(
        alfa=alfa,
        beta=beta,
        p_valor_alfa=float(modelo.pvalues[0]),
        r2=float(modelo.rsquared),
        residuales=residuales,
        sharpe_crudo=sharpe(a, periodos_por_anio=periodos_por_anio),
        sharpe_neutralizado=sharpe(residuales + alfa, periodos_por_anio=periodos_por_anio),
        n=len(comun),
    )


# --------------------------------------------------------------------------------------
# Motor de backtest
# --------------------------------------------------------------------------------------


class TipoRegla(StrEnum):
    APORTACION = "aportacion"  # cuánto dinero nuevo se destina
    POSICION = "posicion"  # qué tamaño de posición se sostiene


@dataclass
class ResultadoBacktest:
    """Resultado con su benchmark del mismo activo y su conteo de apuestas."""

    tipo: TipoRegla
    riqueza_estrategia: pd.Series
    riqueza_benchmark: pd.Series
    retorno_activo: pd.Series
    flujos_estrategia: pd.Series
    flujos_benchmark: pd.Series
    tir_estrategia: float | None
    tir_benchmark: float | None
    apuestas: ConteoApuestas
    neutralizacion: ResultadoNeutralizacion | None
    descripcion_benchmark: str

    @property
    def ventaja_tir(self) -> float | None:
        if self.tir_estrategia is None or self.tir_benchmark is None:
            return None
        return self.tir_estrategia - self.tir_benchmark


class Veredicto(StrEnum):
    GO = "GO"
    NO_GO = "NO-GO"
    INCONCLUSO = "INCONCLUSO"


@dataclass
class DictamenBacktest:
    veredicto: Veredicto
    motivos: list[str] = field(default_factory=list)
    metricas: dict[str, float | None] = field(default_factory=dict)

    def como_texto(self) -> str:
        return f"{self.veredicto.value}. " + " ".join(self.motivos)


def backtest_regla_de_aportacion(
    retornos: pd.Series,
    senal: pd.Series,
    *,
    aportacion_base: float = 1.0,
    multiplicador_max: float = 2.0,
    lag: int = 1,
) -> ResultadoBacktest:
    """Regla que modula el tamaño de la aportación periódica según la señal.

    **Benchmark: aportación constante al mismo papel** (P6). Cualquier otro punto de
    comparación mediría qué tan bueno fue el activo, no qué aportó la regla.

    ``senal`` en [0,1] (típicamente el percentil expandible de la prima) se traduce
    a un multiplicador entre 0 y ``multiplicador_max`` centrado en 1.
    """
    r = pd.Series(retornos).dropna().astype(float)
    s = pd.Series(senal).astype(float).reindex(r.index)
    multiplicador = (2.0 * s).clip(0.0, multiplicador_max)
    ejecutado = aplicar_lag(multiplicador, lag).fillna(1.0)

    aportes_estrategia = aportacion_base * ejecutado
    aportes_benchmark = pd.Series(aportacion_base, index=r.index)

    riqueza_e = _acumular_con_aportes(r, aportes_estrategia)
    riqueza_b = _acumular_con_aportes(r, aportes_benchmark)

    flujos_e = _flujos(aportes_estrategia, riqueza_e)
    flujos_b = _flujos(aportes_benchmark, riqueza_b)

    # Retorno activo de una regla de aportación.
    #
    # El retorno POR PERIODO de ambas rutas es idéntico: es el mismo papel. Lo que
    # cambia es cuánto capital había desplegado en cada momento. Así que el activo es
    # la diferencia de P&L en dinero, normalizada por el capital del benchmark:
    #
    #     activo_t = (P&L_e,t − P&L_b,t) / K_b,t−1 = r_t × sobrepeso relativo_t−1
    #
    # Esa identidad es justo lo que P8 quiere ver: si la regla despliega más capital
    # cuando el activo tiene deriva alcista, la regresión contra r_t lo delata como beta.
    activo = _retorno_activo_por_capital(r, riqueza_e, aportes_estrategia, riqueza_b, aportes_benchmark)

    return ResultadoBacktest(
        tipo=TipoRegla.APORTACION,
        riqueza_estrategia=riqueza_e,
        riqueza_benchmark=riqueza_b,
        retorno_activo=activo,
        flujos_estrategia=flujos_e,
        flujos_benchmark=flujos_b,
        tir_estrategia=tir(flujos_e),
        tir_benchmark=tir(flujos_b),
        apuestas=contar_apuestas(ejecutado, 1.0),
        neutralizacion=neutralizar_beta(activo, r.reindex(activo.index)),
        descripcion_benchmark="Aportación constante al MISMO papel (P6).",
    )


def backtest_regla_de_posicion(
    retornos: pd.Series,
    senal: pd.Series,
    *,
    posicion_max: float = 1.0,
    lag: int = 1,
    capital_inicial: float = 1.0,
) -> ResultadoBacktest:
    """Regla que modula el tamaño de la posición sostenida.

    **Benchmark: comprar y mantener el mismo papel** (P6).
    """
    r = pd.Series(retornos).dropna().astype(float)
    s = pd.Series(senal).astype(float).reindex(r.index).clip(0.0, 1.0)
    posicion = (s * posicion_max).fillna(0.0)
    ejecutada = aplicar_lag(posicion, lag).fillna(0.0)

    ret_e = ejecutada * r
    ret_b = r

    riqueza_e = capital_inicial * (1.0 + ret_e).cumprod()
    riqueza_b = capital_inicial * (1.0 + ret_b).cumprod()

    fecha_ini = r.index[0]
    flujos_e = pd.Series(
        [-capital_inicial, float(riqueza_e.iloc[-1])], index=[fecha_ini, r.index[-1]]
    )
    flujos_b = pd.Series(
        [-capital_inicial, float(riqueza_b.iloc[-1])], index=[fecha_ini, r.index[-1]]
    )

    activo = (ret_e - ret_b).dropna()

    return ResultadoBacktest(
        tipo=TipoRegla.POSICION,
        riqueza_estrategia=riqueza_e,
        riqueza_benchmark=riqueza_b,
        retorno_activo=activo,
        flujos_estrategia=flujos_e,
        flujos_benchmark=flujos_b,
        tir_estrategia=tir(flujos_e),
        tir_benchmark=tir(flujos_b),
        # Referencia de conteo: el nivel neutral de la propia regla. El benchmark de
        # desempeño sigue siendo comprar y mantener (P6), pero una regla que sostiene
        # entre 0% y 100% está casi siempre por debajo de un 100% fijo: medida contra
        # él sería un solo episodio eterno en vez de las decenas de veces que cambió.
        apuestas=contar_apuestas(ejecutada, "mediana"),
        neutralizacion=neutralizar_beta(activo, r.reindex(activo.index)),
        descripcion_benchmark="Comprar y mantener el MISMO papel (P6).",
    )


def dictaminar(
    resultado: ResultadoBacktest,
    *,
    p_valor_maximo: float = 0.01,
    sharpe_minimo: float = 0.30,
) -> DictamenBacktest:
    """Emite GO, NO-GO o INCONCLUSO con las salvaguardas del proyecto.

    El orden importa: **primero** se revisa suficiencia. Sin apuestas efectivas
    suficientes no hay veredicto que dar, por bonitas que se vean las métricas.

    El umbral de significancia es 1%, no el 5% de costumbre, y es deliberado. Un
    analista prueba muchas señales antes de quedarse con una; al 5% nominal, una de
    cada veinte señales de ruido puro pasa. El 1% no elimina el problema de las
    comparaciones múltiples, pero lo reduce a un nivel donde el resto de las
    salvaguardas alcanza a atraparlo.
    """
    motivos: list[str] = []
    metricas: dict[str, float | None] = {
        "episodios": float(resultado.apuestas.episodios),
        "tir_estrategia": resultado.tir_estrategia,
        "tir_benchmark": resultado.tir_benchmark,
        "ventaja_tir": resultado.ventaja_tir,
    }

    if not resultado.apuestas.suficiente:
        motivos.append(resultado.apuestas.como_texto())
        return DictamenBacktest(Veredicto.INCONCLUSO, motivos, metricas)

    neu = resultado.neutralizacion
    if neu is None:
        motivos.append(
            "No hay observaciones suficientes para regresar el retorno activo contra el "
            "subyacente. Sin neutralización de beta no se puede distinguir señal de deriva (P8)."
        )
        return DictamenBacktest(Veredicto.INCONCLUSO, motivos, metricas)

    metricas.update(
        {
            "beta": neu.beta,
            "alfa": neu.alfa,
            "p_valor_alfa": neu.p_valor_alfa,
            "sharpe_crudo": neu.sharpe_crudo,
            "sharpe_neutralizado": neu.sharpe_neutralizado,
        }
    )

    if neu.p_valor_alfa > p_valor_maximo:
        motivos.append(
            f"El alfa neutralizada por beta no es distinguible de cero (p={neu.p_valor_alfa:.3f}). "
            + neu.como_texto()
        )
        return DictamenBacktest(Veredicto.NO_GO, motivos, metricas)

    if neu.sharpe_neutralizado is None or neu.sharpe_neutralizado < sharpe_minimo:
        motivos.append(
            f"El Sharpe neutralizado ({_fmt(neu.sharpe_neutralizado)}) queda debajo del mínimo "
            f"de {sharpe_minimo:.2f}. " + neu.como_texto()
        )
        return DictamenBacktest(Veredicto.NO_GO, motivos, metricas)

    if resultado.ventaja_tir is not None and resultado.ventaja_tir <= 0:
        motivos.append(
            f"La TIR de la estrategia ({_fmt(resultado.tir_estrategia)}) no supera la del "
            f"benchmark del mismo activo ({_fmt(resultado.tir_benchmark)}). "
            + resultado.descripcion_benchmark
        )
        return DictamenBacktest(Veredicto.NO_GO, motivos, metricas)

    motivos.append(
        f"{resultado.apuestas.episodios} episodios, alfa significativa (p={neu.p_valor_alfa:.3f}) "
        f"y Sharpe neutralizado de {_fmt(neu.sharpe_neutralizado)}. "
        + resultado.descripcion_benchmark
    )
    return DictamenBacktest(Veredicto.GO, motivos, metricas)


# --------------------------------------------------------------------------------------
# Control negativo (prueba obligatoria 7)
# --------------------------------------------------------------------------------------


def generar_serie_sin_edge(
    n: int = 240,
    *,
    semilla: int = 0,
    deriva_anual: float = 0.08,
    volatilidad_anual: float = 0.18,
    periodos_por_anio: int = 12,
    inicio: str = "2005-01-31",
) -> tuple[pd.Series, pd.Series]:
    """Genera retornos y una "señal" que es ruido puro, sin edge plantado.

    Sirve de control negativo: si la maquinaria reporta edge sobre esto, está
    alucinando. La deriva alcista es deliberada — es justo lo que hace que un
    Sharpe crudo se vea bien sin ninguna señal detrás (P8).
    """
    rng = np.random.default_rng(semilla)
    mu = deriva_anual / periodos_por_anio
    sigma = volatilidad_anual / np.sqrt(periodos_por_anio)
    fechas = pd.date_range(inicio, periods=n, freq="ME")
    retornos = pd.Series(rng.normal(mu, sigma, n), index=fechas, name="retorno")
    senal = pd.Series(rng.uniform(0.0, 1.0, n), index=fechas, name="senal_ruido")
    return retornos, senal


def generar_serie_con_edge(
    n: int = 240,
    *,
    semilla: int = 0,
    fuerza: float = 0.6,
    deriva_anual: float = 0.08,
    volatilidad_anual: float = 0.18,
    periodos_por_anio: int = 12,
    inicio: str = "2005-01-31",
) -> tuple[pd.Series, pd.Series]:
    """Genera una serie con un edge **plantado**: la señal predice el retorno siguiente.

    Es el control positivo. Sin él, un sistema que siempre dice NO-GO parecería
    riguroso cuando en realidad solo está roto: comprobar que la maquinaria rechaza
    el ruido no sirve de nada si tampoco detecta lo que sí está ahí.

    ``fuerza`` es la fracción de la volatilidad del periodo que la señal explica.
    """
    rng = np.random.default_rng(semilla)
    mu = deriva_anual / periodos_por_anio
    sigma = volatilidad_anual / np.sqrt(periodos_por_anio)
    fechas = pd.date_range(inicio, periods=n, freq="ME")

    senal = pd.Series(rng.uniform(0.0, 1.0, n), index=fechas, name="senal_con_edge")
    ruido = rng.normal(0.0, sigma, n)
    # La señal de t predice el retorno de t+1: centrada en 0.5 para no meter deriva.
    predicho = fuerza * sigma * (senal.to_numpy() - 0.5) * 2.0
    retornos = pd.Series(mu + np.roll(predicho, 1) + ruido, index=fechas, name="retorno")
    retornos.iloc[0] = mu + ruido[0]
    return retornos, senal


# --------------------------------------------------------------------------------------
# Auxiliares
# --------------------------------------------------------------------------------------


def _acumular_con_aportes(retornos: pd.Series, aportes: pd.Series) -> pd.Series:
    """Riqueza cuando se aporta al inicio de cada periodo y se aplica el retorno."""
    saldo = 0.0
    valores = []
    ap = aportes.reindex(retornos.index).fillna(0.0)
    for fecha, r in retornos.items():
        saldo = (saldo + float(ap.loc[fecha])) * (1.0 + float(r))
        valores.append(saldo)
    return pd.Series(valores, index=retornos.index, name="riqueza")


def _flujos(aportes: pd.Series, riqueza: pd.Series) -> pd.Series:
    """Flujos del inversionista: aportaciones negativas y valor terminal positivo."""
    f = -aportes.astype(float).copy()
    ultima = riqueza.index[-1]
    f.loc[ultima] = f.get(ultima, 0.0) + float(riqueza.iloc[-1])
    return f.groupby(level=0).sum().sort_index()


def _capital_desplegado(riqueza: pd.Series, aportes: pd.Series) -> pd.Series:
    """Capital expuesto al mercado durante el periodo: saldo previo más el aporte del periodo."""
    ap = aportes.reindex(riqueza.index).fillna(0.0)
    return riqueza.shift(1).fillna(0.0) + ap


def _retorno_activo_por_capital(
    retornos: pd.Series,
    riqueza_e: pd.Series,
    aportes_e: pd.Series,
    riqueza_b: pd.Series,
    aportes_b: pd.Series,
) -> pd.Series:
    """Diferencia de P&L entre estrategia y benchmark, normalizada por el capital del benchmark.

    Equivale a ``r_t × (K_e,t − K_b,t) / K_b,t``: el retorno del papel multiplicado
    por el sobrepeso relativo de capital que la regla tenía desplegado.
    """
    k_e = _capital_desplegado(riqueza_e, aportes_e)
    k_b = _capital_desplegado(riqueza_b, aportes_b)
    sobrepeso = (k_e - k_b) / k_b.replace(0.0, np.nan)
    return (retornos * sobrepeso).dropna()


def _fmt(x: float | None) -> str:
    return "n/d" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.2f}"
