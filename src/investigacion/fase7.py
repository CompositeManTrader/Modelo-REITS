"""Fase 7: la escalera de modelos para decidir cuándo estar en REITs, estimados siempre con el pasado.

Cinco peldaños, del más simple al más complejo. Todos pronostican lo mismo —el retorno de
los REITs menos el del efectivo en los 12 meses siguientes— con los mismos insumos, y todos
se convierten en exposición con la misma regla: **dentro si el pronóstico es positivo, en
efectivo si es negativo** (salir solo cuando el modelo espera que el efectivo gane).

1. **La mejor señal sola**, escogida cada año con el pasado (la de mayor correlación de
   rangos con el retorno siguiente), en una regresión simple.
2. **Compuesto**: el promedio de las ocho señales, en una regresión simple.
3. **Ridge**: regresión con las ocho señales y penalización escogida por validación cruzada
   temporal dentro del pasado.
4. **Árboles** (gradient boosting) con hiperparámetros fijos y pequeños.
5. **Regímenes** (Markov de dos estados sobre el retorno en exceso mensual, como Bianchi y
   Guidolin 2014): fuera si la probabilidad filtrada del régimen malo pasa de 50%.

**Insumos**: los percentiles expandibles (60 meses mínimo) de las ocho señales portables
(se pueden calcular en otros mercados), orientadas para que más alto sea mejor.

**Estimación** (``diseno.WALK_FORWARD``): ventana creciente, re-estimación cada 12 meses,
al menos 120 meses de pares (señal, retorno siguiente) ya terminados. Un par cuyo retorno de
12 meses todavía no termina en la fecha de estimación no entra.

La escalera: un peldaño se queda solo si le gana al último que se quedó (mejora de TIR
rebalanceando contra aportar siempre). El último que se queda es el candidato.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.investigacion import estadistica, timing
from src.investigacion.diseno import WALK_FORWARD
from src.investigacion.exploracion import _adelante
from src.modelo.senal import percentil_expandible

HORIZONTE = 12
MINIMO_DE_HISTORIA = 60
# nombre: (columna de ``indicadores``, signo para que más alto sea mejor)
SENALES_PORTABLES: dict[str, tuple[str, int]] = {
    "yield": ("yield_reit", +1),
    "yield contra la tasa larga": ("spread_10a", +1),
    "tendencia de 10 meses": ("tendencia_10m", +1),
    "momentum contra el efectivo": ("momentum_exceso_12m", +1),
    "spread de default": ("spread_default", +1),
    "cambio del spread de crédito": ("cambio_credito_12m", -1),
    "condiciones financieras": ("nfci", -1),
    "bolsa del mes": ("bolsa_mes", +1),
}
ALPHAS_RIDGE = (0.1, 1.0, 10.0, 100.0, 1000.0)
ARBOLES = {"max_depth": 2, "n_estimators": 150, "learning_rate": 0.03, "subsample": 0.7, "random_state": 7}
PELDANOS = ("mejor señal sola", "compuesto", "ridge", "árboles", "regímenes")
SEMILLA_REGIMENES = 7


# --------------------------------------------------------------------------------------
# Insumos
# --------------------------------------------------------------------------------------


def matriz(ind: pd.DataFrame, minimo: int = MINIMO_DE_HISTORIA) -> pd.DataFrame:
    """Los percentiles expandibles de las señales portables, orientadas."""
    columnas = {}
    for nombre, (col, signo) in SENALES_PORTABLES.items():
        s = (signo * ind[col]).dropna() if col in ind else pd.Series(dtype=float)
        columnas[nombre] = percentil_expandible(s, min_observaciones=minimo).reindex(ind.index) if len(s) else np.nan
    return pd.DataFrame(columnas, index=ind.index)


def objetivo(x: pd.DataFrame, h: int = HORIZONTE) -> pd.Series:
    """El retorno de los REITs menos el del efectivo en los ``h`` meses siguientes, guardado en ``t``."""
    return _adelante(x["retorno_total"], h) - _adelante(x["efectivo"], h)


# --------------------------------------------------------------------------------------
# Los ajustes: cada uno recibe el pasado y devuelve una función que pronostica
# --------------------------------------------------------------------------------------

Ajuste = Callable[[pd.DataFrame, pd.Series], Callable[[pd.DataFrame], np.ndarray]]


def _ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    if np.unique(x).size < 3:
        return float(y.mean()), 0.0
    b, a = np.polyfit(x, y, 1)
    return float(a), float(b)


def ajuste_mejor_senal(X: pd.DataFrame, y: pd.Series):
    corr = X.apply(lambda c: c.corr(y, method="spearman"))
    if corr.dropna().empty or corr.max() <= 0:
        media = float(y.mean())
        return lambda Z: np.full(len(Z), media)
    mejor = str(corr.idxmax())
    a, b = _ols(X[mejor].to_numpy(), y.to_numpy())
    b = max(b, 0.0)   # restricción de signo: la señal está orientada
    return lambda Z: a + b * Z[mejor].to_numpy()


def ajuste_compuesto(X: pd.DataFrame, y: pd.Series):
    c = X.mean(axis=1)
    a, b = _ols(c.to_numpy(), y.to_numpy())
    if b < 0:
        media = float(y.mean())
        return lambda Z: np.full(len(Z), media)
    return lambda Z: a + b * Z.mean(axis=1).to_numpy()


def _ridge(X: np.ndarray, y: np.ndarray, alpha: float) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    Z = (X - mu) / sd
    beta = np.linalg.solve(Z.T @ Z + alpha * np.eye(Z.shape[1]), Z.T @ (y - y.mean()))
    return beta, float(y.mean()), mu, sd


def ajuste_ridge(X: pd.DataFrame, y: pd.Series, h: int = HORIZONTE):
    Xv, yv = X.to_numpy(), y.to_numpy()
    n = len(yv)
    # Validación cruzada temporal: tres cortes; entre estimar y validar, un hueco de h meses.
    errores = {}
    for alpha in ALPHAS_RIDGE:
        e = []
        for k in (0.55, 0.70, 0.85):
            corte = int(n * k)
            fin_val = min(n, int(n * (k + 0.15)))
            if corte - h < 30 or fin_val <= corte:
                continue
            beta, m, mu, sd = _ridge(Xv[: corte - h], yv[: corte - h], alpha)
            p = m + ((Xv[corte:fin_val] - mu) / sd) @ beta
            e.append(float(((yv[corte:fin_val] - p) ** 2).mean()))
        errores[alpha] = np.mean(e) if e else np.inf
    alpha = min(errores, key=errores.get)
    beta, m, mu, sd = _ridge(Xv, yv, alpha)
    return lambda Z: m + ((Z.to_numpy() - mu) / sd) @ beta


def ajuste_arboles(X: pd.DataFrame, y: pd.Series):
    from sklearn.ensemble import GradientBoostingRegressor

    modelo = GradientBoostingRegressor(**ARBOLES).fit(X.to_numpy(), y.to_numpy())
    return lambda Z: modelo.predict(Z.to_numpy())


AJUSTES: dict[str, Ajuste] = {"mejor señal sola": ajuste_mejor_senal, "compuesto": ajuste_compuesto,
                              "ridge": ajuste_ridge, "árboles": ajuste_arboles}


# --------------------------------------------------------------------------------------
# Estimación hacia adelante
# --------------------------------------------------------------------------------------


def walk_forward(X: pd.DataFrame, y: pd.Series, ajuste: Ajuste, *, h: int = HORIZONTE,
                 minimo: int = WALK_FORWARD.meses_minimos_para_estimar,
                 cada: int = WALK_FORWARD.reestimar_cada_meses) -> pd.Series:
    """Pronóstico de cada mes con un modelo estimado solo con pares ya terminados."""
    n = len(X)
    pron = np.full(n, np.nan)
    completos = X.notna().all(axis=1).to_numpy()
    t = 0
    while t < n:
        fin = t - h + 1                                   # pares s ≤ t − h
        ok = completos[:max(fin, 0)] & y.iloc[:max(fin, 0)].notna().to_numpy()
        if fin > 0 and ok.sum() >= minimo:
            idx = np.flatnonzero(ok)
            predecir = ajuste(X.iloc[idx], y.iloc[idx])
            hasta = min(n, t + cada)
            Z = X.iloc[t:hasta]
            filas = Z.notna().all(axis=1).to_numpy()
            if filas.any():
                bloque = np.full(len(Z), np.nan)
                bloque[filas] = predecir(Z[filas])
                pron[t:hasta] = bloque
            t = hasta
        else:
            t += 1
    return pd.Series(pron, index=X.index)


def regimenes(x: pd.DataFrame, *, minimo: int = WALK_FORWARD.meses_minimos_para_estimar,
              cada: int = WALK_FORWARD.reestimar_cada_meses) -> pd.DataFrame:
    """Probabilidad FILTRADA (solo con el pasado) del régimen malo y el retorno esperado del mes siguiente."""
    from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

    r = (x["retorno_total"] - x["efectivo"]).to_numpy()
    n = len(r)
    p_malo, esperado = np.full(n, np.nan), np.full(n, np.nan)
    t = minimo
    while t < n:
        modelo = MarkovRegression(r[:t], k_regimes=2, trend="c", switching_variance=True)
        estado = np.random.get_state()
        np.random.seed(SEMILLA_REGIMENES)    # la búsqueda de arranque es aleatoria: se fija para repetir
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ajuste = modelo.fit(disp=False, search_reps=5)
        except Exception:  # noqa: BLE001 — si no converge, ese año no hay decisión del modelo
            t += cada
            continue
        finally:
            np.random.set_state(estado)
        params = ajuste.params
        medias = np.asarray(ajuste.params[[i for i in range(len(params)) if "const" in str(modelo.param_names[i])]])
        malo = int(np.argmin(medias))
        hasta = min(n, t + cada)
        for k in range(t, hasta):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                filtrado = MarkovRegression(r[:k + 1], k_regimes=2, trend="c", switching_variance=True).filter(params)
            prob = filtrado.filtered_marginal_probabilities[-1]
            transicion = filtrado.regime_transition[:, :, -1] if filtrado.regime_transition.ndim == 3 \
                else filtrado.regime_transition
            siguiente = transicion @ prob
            p_malo[k] = float(prob[malo])
            esperado[k] = float(siguiente @ medias)
        t = hasta
    return pd.DataFrame({"p_malo": p_malo, "esperado_1m": esperado}, index=x.index)


# --------------------------------------------------------------------------------------
# La escalera
# --------------------------------------------------------------------------------------


def exposicion_de_pronostico(p: pd.Series) -> pd.Series:
    """Dentro si el pronóstico es positivo; sin pronóstico, dentro (como aportar siempre)."""
    return (p > 0).astype(float).where(p.notna(), 1.0)


def predictivo(pron: pd.Series, y: pd.Series, h: int = HORIZONTE, desde: pd.Timestamp | None = None) -> dict:
    """R² fuera de muestra y Clark-West del pronóstico del modelo contra el promedio histórico."""
    yv = y.to_numpy()
    prom = np.full(len(y), np.nan)
    for t in range(len(y)):
        fin = t - h + 1
        if fin > 0:
            v = yv[:fin]
            v = v[~np.isnan(v)]
            if len(v):
                prom[t] = v.mean()
    d = pd.DataFrame({"real": yv, "pronostico": pron.to_numpy(), "promedio": prom}, index=y.index)
    if desde is not None:
        d = d.loc[desde:]
    t_cw, p_cw = estadistica.clark_west(d["real"], d["pronostico"], d["promedio"], rezago=h)
    return {"r2": estadistica.r2_fuera_de_muestra(d["real"], d["pronostico"], d["promedio"]),
            "clark_west_p": p_cw, "meses": int(d[["real", "pronostico"]].notna().all(axis=1).sum())}


@dataclass
class Peldano:
    nombre: str
    pronostico: pd.Series
    exposicion: pd.Series
    horizonte: int
    evaluacion: dict = field(default_factory=dict)


def construir(x: pd.DataFrame, ind: pd.DataFrame) -> list[Peldano]:
    """Los cinco peldaños sobre el sector ``x`` (pronósticos y exposiciones, sin evaluar)."""
    X = matriz(ind)
    y = objetivo(x)
    salida = []
    for nombre, ajuste in AJUSTES.items():
        p = walk_forward(X, y, ajuste)
        salida.append(Peldano(nombre, p, exposicion_de_pronostico(p), HORIZONTE))
    rg = regimenes(x)
    exp_rg = (rg["p_malo"] < 0.5).astype(float).where(rg["p_malo"].notna(), 1.0)
    salida.append(Peldano("regímenes", rg["esperado_1m"], exp_rg, 1))
    return salida


def evaluar(peldanos: list[Peldano], x: pd.DataFrame, ind: pd.DataFrame, *, muestra: str,
            desde: pd.Timestamp | None = None, registrar: bool = True, ruta_bitacora=None) -> pd.DataFrame:
    filas = []
    for p in peldanos:
        senal = timing.Senal(p.nombre, "fase7", lambda x_, i_, s=p.pronostico: s, f"Peldaño «{p.nombre}» de la escalera")
        r = timing.evaluar(senal, "dentro si el pronóstico es positivo", p.exposicion, x, ind, muestra=muestra,
                           desde=desde, registrar=registrar, ruta_bitacora=ruta_bitacora)
        y = objetivo(x, p.horizonte)
        pr = predictivo(p.pronostico, y, p.horizonte, desde)
        r[f"r2_{p.horizonte}m_modelo"], r["clark_west_p_modelo"] = pr["r2"], pr["clark_west_p"]
        # El filtro de la fase 5 pide predecir a 12 meses: para los peldaños de 12 meses se usa el pronóstico
        # del propio modelo; el de regímenes pronostica a un mes.
        r["r2_12m"] = pr["r2"] if p.horizonte == 12 else np.nan
        r["clark_west_p_12m"] = pr["clark_west_p"] if p.horizonte == 12 else np.nan
        r["r2_1m_modelo"] = pr["r2"] if p.horizonte == 1 else np.nan
        filas.append(r)
        p.evaluacion = r
    return timing.resumen(filas)


def escalera(evaluacion: pd.DataFrame) -> tuple[list[str], str]:
    """Los peldaños que se quedan y el candidato (el último que se quedó)."""
    se_quedan, mejor = [], 0.0          # el punto de partida es aportar siempre (mejora 0)
    for nombre in PELDANOS:
        m = float(evaluacion.set_index("senal").loc[nombre, "mejora_rebalanceo"])
        if m > mejor:
            se_quedan.append(nombre)
            mejor = m
    return se_quedan, (se_quedan[-1] if se_quedan else "")
