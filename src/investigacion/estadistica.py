"""Las pruebas estadísticas que pide la fase 0, escritas una vez y probadas contra casos conocidos.

* **R² fuera de muestra** (Campbell y Thompson, 2008): qué tanto mejor predice una señal que
  el promedio histórico, cada uno estimado solo con el pasado. Positivo = mejor.
* **Clark y West** (2007): si esa mejora es distinguible de cero cuando el modelo de la señal
  anida al del promedio. Errores estándar de Newey-West por los horizontes encimados.
* **Sharpe deflactado** (Bailey y López de Prado, 2014): la probabilidad de que el Sharpe
  verdadero sea positivo, descontando que se escogió el mejor de N intentos, con la
  asimetría y la curtosis de los retornos.
* **PBO** (Bailey, Borwein, López de Prado y Zhu, 2017): con la validación cruzada
  combinatoria simétrica, qué tan seguido la configuración que gana dentro de muestra queda
  en la mitad de abajo fuera de muestra.
* **Apuestas efectivas** (P7): meses entre el horizonte, o cambios de postura, lo que sea menor.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
from scipy import stats

EULER = 0.5772156649015329


# --------------------------------------------------------------------------------------
# Predicción fuera de muestra
# --------------------------------------------------------------------------------------


def newey_west_t(serie: np.ndarray, rezago: int) -> float:
    """t del promedio de una serie con errores de Newey-West (Bartlett)."""
    x = np.asarray(serie, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 3:
        return np.nan
    u = x - x.mean()
    var = u @ u / n
    for k in range(1, min(rezago, n - 1) + 1):
        var += 2 * (1 - k / (rezago + 1)) * (u[k:] @ u[:-k]) / n
    return float(x.mean() / math.sqrt(var / n)) if var > 0 else np.nan


def r2_fuera_de_muestra(real: np.ndarray, pronostico: np.ndarray, promedio: np.ndarray) -> float:
    """1 − ECM(señal) / ECM(promedio histórico), en los meses con los tres datos."""
    r, p, m = (np.asarray(v, dtype=float) for v in (real, pronostico, promedio))
    ok = ~(np.isnan(r) | np.isnan(p) | np.isnan(m))
    if ok.sum() < 3:
        return np.nan
    return float(1 - ((r[ok] - p[ok]) ** 2).sum() / ((r[ok] - m[ok]) ** 2).sum())


def clark_west(real: np.ndarray, pronostico: np.ndarray, promedio: np.ndarray, *, rezago: int = 0) -> tuple[float, float]:
    """Estadístico de Clark-West y su valor p de una cola (la señal mejora al promedio)."""
    r, p, m = (np.asarray(v, dtype=float) for v in (real, pronostico, promedio))
    ok = ~(np.isnan(r) | np.isnan(p) | np.isnan(m))
    r, p, m = r[ok], p[ok], m[ok]
    f = (r - m) ** 2 - ((r - p) ** 2 - (m - p) ** 2)
    t = newey_west_t(f, rezago)
    return t, float(1 - stats.norm.cdf(t)) if np.isfinite(t) else np.nan


def pronostico_expandible(senal: pd.Series, objetivo: pd.Series, *, minimo: int, horizonte: int,
                          signo: int | None = None) -> pd.DataFrame:
    """Regresión del retorno siguiente contra la señal, estimada cada mes solo con el pasado.

    En el mes ``t`` se usan los pares (señal ``s``, retorno de ``s+1 … s+h``) cuyo retorno ya
    terminó: ``s + h ≤ t``. Devuelve el pronóstico de la señal y el del promedio histórico.

    Con ``signo`` (restricción de Campbell y Thompson, 2008): si la pendiente estimada tiene
    el signo contrario al que dice la teoría, el pronóstico es el promedio histórico.
    """
    s = senal.astype(float)
    y = objetivo.astype(float)
    fechas = s.index
    pron, prom = np.full(len(s), np.nan), np.full(len(s), np.nan)
    sv, yv = s.to_numpy(), y.to_numpy()
    for t in range(len(s)):
        fin = t - horizonte + 1        # pares s ≤ t − h
        if fin <= 0:
            continue
        xs, ys = sv[:fin], yv[:fin]
        ok = ~(np.isnan(xs) | np.isnan(ys))
        if ok.sum() < minimo or np.isnan(sv[t]):
            continue
        prom[t] = ys[ok].mean()
        b, a = np.polyfit(xs[ok], ys[ok], 1)
        pron[t] = prom[t] if (signo is not None and b * signo < 0) else a + b * sv[t]
    return pd.DataFrame({"pronostico": pron, "promedio": prom, "real": yv}, index=fechas)


# --------------------------------------------------------------------------------------
# Pruebas múltiples
# --------------------------------------------------------------------------------------


def sharpe(r: np.ndarray) -> float:
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    return float(r.mean() / r.std(ddof=1)) if len(r) > 2 and r.std(ddof=1) > 0 else np.nan


def sharpe_maximo_esperado(intentos: int, varianza_de_sharpes: float) -> float:
    """El Sharpe que se esperaría del mejor de N intentos sin habilidad (Bailey-López de Prado)."""
    if intentos <= 1:
        return 0.0
    z1 = stats.norm.ppf(1 - 1 / intentos)
    z2 = stats.norm.ppf(1 - 1 / (intentos * math.e))
    return float(math.sqrt(varianza_de_sharpes) * ((1 - EULER) * z1 + EULER * z2))


def sharpe_deflactado(r: np.ndarray, *, intentos: int, varianza_de_sharpes: float) -> float:
    """Probabilidad de que el Sharpe verdadero supere al máximo esperado por azar (por periodo)."""
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    n = len(r)
    sr = sharpe(r)
    if n < 10 or not np.isfinite(sr):
        return np.nan
    sr0 = sharpe_maximo_esperado(intentos, varianza_de_sharpes)
    g3 = float(stats.skew(r))
    g4 = float(stats.kurtosis(r, fisher=False))
    denominador = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr**2))
    return float(stats.norm.cdf((sr - sr0) * math.sqrt(n - 1) / denominador))


def pbo(rendimientos: pd.DataFrame, *, bloques: int = 16, metrica=sharpe) -> float:
    """Probabilidad de sobreajuste por validación cruzada combinatoria simétrica (CSCV).

    ``rendimientos``: una columna por configuración probada, un renglón por periodo. Se parte en
    ``bloques`` pedazos contiguos; para cada mitad de los bloques como «dentro de muestra», se
    escoge la mejor configuración y se ve su lugar en la otra mitad.
    """
    m = rendimientos.dropna(how="any").to_numpy()
    if m.shape[1] < 2:
        return np.nan
    partes = np.array_split(np.arange(len(m)), bloques)
    logits = []
    for dentro in itertools.combinations(range(bloques), bloques // 2):
        idx_d = np.concatenate([partes[i] for i in dentro])
        idx_f = np.concatenate([partes[i] for i in range(bloques) if i not in dentro])
        d = np.array([metrica(m[idx_d, j]) for j in range(m.shape[1])])
        f = np.array([metrica(m[idx_f, j]) for j in range(m.shape[1])])
        mejor = int(np.nanargmax(d))
        lugar = (stats.rankdata(f)[mejor]) / (len(f) + 1)
        logits.append(math.log(lugar / (1 - lugar)))
    return float(np.mean(np.array(logits) <= 0))


def apuestas_efectivas(meses: int, horizonte: int, cambios: int | None = None) -> int:
    """P7: ventanas que no se enciman, o cambios de postura si son menos."""
    por_ventanas = meses // max(1, horizonte)
    return int(min(por_ventanas, cambios)) if cambios is not None else int(por_ventanas)
