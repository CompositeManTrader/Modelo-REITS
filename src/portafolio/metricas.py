"""Métricas de desempeño: TWR, TIR, atribución, drawdown y riesgo.

Dos retornos que **no** son el mismo número y que se confunden todo el tiempo:

* **TWR (ponderado por tiempo)** quita el efecto del timing de las aportaciones.
  Mide la selección de activos: es el número con el que se juzga al gestor.
* **TIR (ponderado por dinero)** incluye el timing. Mide el resultado del usuario:
  es el número que efectivamente ganó su bolsillo.

Se muestran siempre los dos. Si el TWR es mayor que la TIR, el usuario aportó más
dinero antes de los periodos malos; si es menor, tuvo buen timing.

P9 — Para flujos desiguales, usa TIR money-weighted
===================================================
Cuando dos estrategias despliegan distinto capital o en distintos momentos,
comparar riqueza final es incorrecto. Normalizar por capital total tampoco sirve
porque no corrige el timing. La TIR maneja ambas cosas de forma nativa.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import optimize

DIAS_ANIO = 365.25
PERIODOS_ANIO_DIARIO = 252


# --------------------------------------------------------------------------------------
# Retorno ponderado por tiempo
# --------------------------------------------------------------------------------------


def twr(valores: pd.Series, flujos_externos: pd.Series | None = None) -> pd.Series:
    """Retorno ponderado por tiempo, encadenando subperiodos entre flujos.

    Convención: los flujos ocurren al **final** del subperiodo, así que el retorno
    del periodo ``i`` es ``(V_i − F_i)/V_{i−1} − 1``. Es la convención GIPS más
    común y la que no le regala al gestor el rendimiento del dinero que entró hoy.
    """
    if valores.empty:
        return pd.Series(dtype="float64")
    v = valores.astype(float).copy()
    v.index = pd.to_datetime(v.index)
    v = v.sort_index()
    f = (
        flujos_externos.astype(float).reindex(v.index).fillna(0.0)
        if flujos_externos is not None
        else pd.Series(0.0, index=v.index)
    )

    retornos = []
    for i in range(1, len(v)):
        v0 = v.iloc[i - 1]
        if v0 <= 0:
            retornos.append(0.0)
            continue
        retornos.append((v.iloc[i] - f.iloc[i]) / v0 - 1.0)
    s = pd.Series(retornos, index=v.index[1:], name="retorno_periodo")
    return s


def twr_acumulado(valores: pd.Series, flujos_externos: pd.Series | None = None) -> float:
    r = twr(valores, flujos_externos)
    return float((1.0 + r).prod() - 1.0) if not r.empty else 0.0


def twr_anualizado(valores: pd.Series, flujos_externos: pd.Series | None = None) -> float | None:
    if valores.empty or len(valores) < 2:
        return None
    total = twr_acumulado(valores, flujos_externos)
    idx = pd.to_datetime(valores.index)
    anios = (idx.max() - idx.min()).days / DIAS_ANIO
    if anios <= 0:
        return None
    return (1.0 + total) ** (1.0 / anios) - 1.0


# --------------------------------------------------------------------------------------
# Retorno ponderado por dinero (TIR / XIRR)
# --------------------------------------------------------------------------------------


def vpn(tasa: float, flujos: pd.Series) -> float:
    """Valor presente neto de flujos fechados, en base anual de 365.25 días."""
    idx = pd.to_datetime(flujos.index)
    t0 = idx.min()
    anios = np.array([(f - t0).days / DIAS_ANIO for f in idx])
    if tasa <= -1.0:
        return float("inf")
    return float(np.sum(flujos.to_numpy() / (1.0 + tasa) ** anios))


def tir(flujos: pd.Series, *, minimo: float = -0.9999, maximo: float = 10.0) -> float | None:
    """TIR de flujos irregulares (XIRR). ``None`` si no hay una raíz en el rango.

    Requiere al menos un flujo negativo y uno positivo: sin ambos, no hay tasa que
    iguale el valor presente a cero, y devolver un número sería inventarlo.
    """
    if flujos is None or flujos.empty:
        return None
    f = flujos.astype(float).copy()
    f.index = pd.to_datetime(f.index)
    f = f.groupby(level=0).sum().sort_index()
    if not ((f < 0).any() and (f > 0).any()):
        return None

    def objetivo(r):
        return vpn(r, f)

    try:
        v_min, v_max = objetivo(minimo), objetivo(maximo)
    except (OverflowError, ZeroDivisionError):
        return None
    if not np.isfinite(v_min) or not np.isfinite(v_max) or v_min * v_max > 0:
        # Sin cambio de signo en el rango: se intenta Newton desde una semilla razonable.
        try:
            r = optimize.newton(objetivo, 0.08, maxiter=200, tol=1e-10)
            return float(r) if np.isfinite(r) and r > minimo else None
        except (RuntimeError, OverflowError):
            return None
    try:
        return float(optimize.brentq(objetivo, minimo, maximo, xtol=1e-10, maxiter=500))
    except ValueError:
        return None


def tir_con_valor_final(
    flujos: pd.Series, valor_final: float, fecha_final: dt.date | pd.Timestamp
) -> float | None:
    """TIR agregando el valor de mercado actual como flujo terminal.

    Es la forma correcta de medir la TIR de una posición viva: se simula venderla
    hoy al precio de mercado.
    """
    f = flujos.astype(float).copy()
    f.index = pd.to_datetime(f.index)
    ts = pd.Timestamp(fecha_final)
    f.loc[ts] = f.get(ts, 0.0) + float(valor_final)
    return tir(f.groupby(level=0).sum().sort_index())


# --------------------------------------------------------------------------------------
# Riesgo
# --------------------------------------------------------------------------------------


def drawdown(valores: pd.Series) -> pd.DataFrame:
    """Serie de caída desde el máximo previo, con máximo y actual."""
    if valores.empty:
        return pd.DataFrame(columns=["valor", "maximo_previo", "drawdown"])
    v = valores.astype(float).copy()
    v.index = pd.to_datetime(v.index)
    v = v.sort_index()
    maximo = v.cummax()
    return pd.DataFrame({"valor": v, "maximo_previo": maximo, "drawdown": v / maximo - 1.0})


def drawdown_maximo(valores: pd.Series) -> float:
    d = drawdown(valores)
    return float(d["drawdown"].min()) if not d.empty else 0.0


def drawdown_actual(valores: pd.Series) -> float:
    d = drawdown(valores)
    return float(d["drawdown"].iloc[-1]) if not d.empty else 0.0


def volatilidad(retornos: pd.Series, *, periodos_por_anio: int = PERIODOS_ANIO_DIARIO) -> float | None:
    r = pd.Series(retornos).dropna()
    if len(r) < 2:
        return None
    return float(r.std(ddof=1) * np.sqrt(periodos_por_anio))


def sharpe(
    retornos: pd.Series,
    tasa_libre_riesgo: float = 0.0,
    *,
    periodos_por_anio: int = PERIODOS_ANIO_DIARIO,
) -> float | None:
    """Sharpe anualizado. ``tasa_libre_riesgo`` es anual y se convierte por periodo."""
    r = pd.Series(retornos).dropna()
    if len(r) < 2:
        return None
    rf_periodo = (1.0 + tasa_libre_riesgo) ** (1.0 / periodos_por_anio) - 1.0
    exceso = r - rf_periodo
    sd = exceso.std(ddof=1)
    if sd == 0:
        return None
    return float(exceso.mean() / sd * np.sqrt(periodos_por_anio))


def sortino(
    retornos: pd.Series,
    tasa_libre_riesgo: float = 0.0,
    *,
    periodos_por_anio: int = PERIODOS_ANIO_DIARIO,
) -> float | None:
    """Sortino: penaliza solo la desviación a la baja, que es la que duele."""
    r = pd.Series(retornos).dropna()
    if len(r) < 2:
        return None
    rf_periodo = (1.0 + tasa_libre_riesgo) ** (1.0 / periodos_por_anio) - 1.0
    exceso = r - rf_periodo
    abajo = exceso[exceso < 0]
    if abajo.empty:
        return None
    dd = np.sqrt((abajo**2).mean())
    if dd == 0:
        return None
    return float(exceso.mean() / dd * np.sqrt(periodos_por_anio))


def beta(retornos: pd.Series, retornos_indice: pd.Series) -> float | None:
    """Beta contra el índice de referencia (por omisión, el Nareit All Equity)."""
    a = pd.Series(retornos).dropna()
    b = pd.Series(retornos_indice).dropna()
    comun = a.index.intersection(b.index)
    if len(comun) < 3:
        return None
    a, b = a.reindex(comun), b.reindex(comun)
    var = b.var(ddof=1)
    if var == 0:
        return None
    return float(a.cov(b) / var)


def alfa_anualizado(
    retornos: pd.Series,
    retornos_indice: pd.Series,
    *,
    periodos_por_anio: int = PERIODOS_ANIO_DIARIO,
) -> float | None:
    b = beta(retornos, retornos_indice)
    if b is None:
        return None
    a = pd.Series(retornos).dropna()
    i = pd.Series(retornos_indice).dropna()
    comun = a.index.intersection(i.index)
    a, i = a.reindex(comun), i.reindex(comun)
    return float((a.mean() - b * i.mean()) * periodos_por_anio)


# --------------------------------------------------------------------------------------
# Atribución del retorno en tres componentes
# --------------------------------------------------------------------------------------


@dataclass
class Atribucion:
    """Descomposición del retorno total en sus tres motores.

    Esta descomposición es la que revela si el resultado vino del negocio o de la
    revaluación. Un retorno que vino todo de expansión de múltiplo es prestado: se
    devuelve cuando el múltiplo se normaliza.
    """

    yield_cobrado: float
    crecimiento_affo: float
    cambio_multiplo: float
    termino_cruzado: float
    retorno_total: float
    retorno_precio: float

    def como_tabla(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"componente": "Dividendo cobrado", "aporte": self.yield_cobrado,
                 "explicacion": "Efectivo que entró a la cuenta. Es el único componente que no se devuelve."},
                {"componente": "Crecimiento del AFFO por acción", "aporte": self.crecimiento_affo,
                 "explicacion": "Lo que creció el negocio por acción. Es el motor sostenible."},
                {"componente": "Cambio de múltiplo", "aporte": self.cambio_multiplo,
                 "explicacion": "Revaluación. Prestado: se devuelve cuando el múltiplo se normaliza."},
                {"componente": "Término cruzado", "aporte": self.termino_cruzado,
                 "explicacion": "Interacción entre crecimiento y múltiplo. Chico salvo en movimientos grandes."},
                {"componente": "TOTAL", "aporte": self.retorno_total, "explicacion": ""},
            ]
        )


def atribuir_retorno(
    precio_inicial: float,
    precio_final: float,
    affo_por_accion_inicial: float,
    affo_por_accion_final: float,
    dividendos_cobrados_por_accion: float,
) -> Atribucion | None:
    """Descompone el retorno en yield, crecimiento del AFFO y cambio de múltiplo.

    Identidad de partida: ``precio = múltiplo × AFFO por acción``. De ahí,
    ``(1 + r_precio) = (1 + g_múltiplo)(1 + g_AFFO)``. El término cruzado se
    reporta por separado en vez de repartirlo, para que la suma cierre exacto.
    """
    if precio_inicial <= 0 or affo_por_accion_inicial == 0 or affo_por_accion_final == 0:
        return None

    m0 = precio_inicial / affo_por_accion_inicial
    m1 = precio_final / affo_por_accion_final
    g_affo = affo_por_accion_final / affo_por_accion_inicial - 1.0
    g_mult = m1 / m0 - 1.0
    r_precio = precio_final / precio_inicial - 1.0
    y = dividendos_cobrados_por_accion / precio_inicial
    cruzado = r_precio - g_affo - g_mult

    return Atribucion(
        yield_cobrado=y,
        crecimiento_affo=g_affo,
        cambio_multiplo=g_mult,
        termino_cruzado=cruzado,
        retorno_total=r_precio + y,
        retorno_precio=r_precio,
    )


@dataclass
class AtribucionMonetaria:
    """Atribución en pesos o dólares, no en porcentaje.

    Reproduce el tipo de descomposición que revela de dónde vino el dinero. Sobre
    Realty Income 2019–2026: dividendos +31,792 dólares, cambio de precio −7,041,
    efecto de reinversión +6,982. Todo el retorno vino del dividendo y el precio restó.
    """

    dividendos: float
    cambio_de_precio: float
    efecto_reinversion: float
    total: float

    def como_tabla(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"componente": "Dividendos cobrados", "monto": self.dividendos},
                {"componente": "Cambio de precio", "monto": self.cambio_de_precio},
                {"componente": "Efecto de reinversión", "monto": self.efecto_reinversion},
                {"componente": "TOTAL", "monto": self.total},
            ]
        )


def atribuir_monetario(
    aportado: float,
    valor_final: float,
    dividendos_cobrados: float,
    dividendos_reinvertidos: float = 0.0,
    *,
    titulos_comprados_con_aportaciones: float | None = None,
    precio_inicial: float | None = None,
    precio_final: float | None = None,
) -> AtribucionMonetaria:
    """Descompone la ganancia en dinero: dividendos, precio y reinversión.

    El **efecto de reinversión** es lo que aportaron los títulos comprados con
    dividendos: su valor de mercado actual menos lo que costaron. Se separa porque
    responde una pregunta distinta — si reinvertir valió la pena — de la de si el
    papel subió.
    """
    ganancia_total = valor_final + (dividendos_cobrados - dividendos_reinvertidos) - aportado

    if (
        titulos_comprados_con_aportaciones is not None
        and precio_inicial is not None
        and precio_final is not None
        and precio_inicial > 0
    ):
        cambio_precio = titulos_comprados_con_aportaciones * (precio_final - precio_inicial)
        reinversion = ganancia_total - dividendos_cobrados - cambio_precio
    else:
        cambio_precio = ganancia_total - dividendos_cobrados
        reinversion = 0.0

    return AtribucionMonetaria(
        dividendos=dividendos_cobrados,
        cambio_de_precio=cambio_precio,
        efecto_reinversion=reinversion,
        total=ganancia_total,
    )


# --------------------------------------------------------------------------------------
# Ingreso en términos reales
# --------------------------------------------------------------------------------------


def ingreso_real(
    ingreso_nominal: pd.Series, indice_precios: pd.Series, base: pd.Timestamp | None = None
) -> pd.Series:
    """Deflacta el ingreso por dividendos. Es la métrica que importa para vivir de rentas."""
    from src.ingesta.tasas import deflactar

    return deflactar(ingreso_nominal, indice_precios, base=base)


def crecimiento_real_anualizado(
    serie_nominal: pd.Series, indice_precios: pd.Series
) -> dict[str, float | None]:
    """Crecimiento nominal, inflación y crecimiento real de una serie de ingreso.

    Realty Income creció su dividendo 3.2% anual de 2021 a 2025 contra inflación de
    ~3.3%: el ingreso quedó plano en poder adquisitivo. Ese es el número que casi
    nadie mira y el que decide si el plan de retiro funciona.
    """
    s = pd.Series(serie_nominal).dropna()
    if len(s) < 2:
        return {"nominal": None, "inflacion": None, "real": None}
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    anios = (s.index.max() - s.index.min()).days / DIAS_ANIO
    if anios <= 0 or s.iloc[0] <= 0:
        return {"nominal": None, "inflacion": None, "real": None}
    nominal = (s.iloc[-1] / s.iloc[0]) ** (1.0 / anios) - 1.0

    ipc = pd.Series(indice_precios).dropna()
    if ipc.empty:
        return {"nominal": nominal, "inflacion": None, "real": None}
    ipc.index = pd.to_datetime(ipc.index)
    ipc = ipc.sort_index()
    ipc_ini = ipc[ipc.index <= s.index.min()]
    ipc_fin = ipc[ipc.index <= s.index.max()]
    if ipc_ini.empty or ipc_fin.empty or ipc_ini.iloc[-1] <= 0:
        return {"nominal": nominal, "inflacion": None, "real": None}
    inflacion = (ipc_fin.iloc[-1] / ipc_ini.iloc[-1]) ** (1.0 / anios) - 1.0
    real = (1.0 + nominal) / (1.0 + inflacion) - 1.0
    return {"nominal": float(nominal), "inflacion": float(inflacion), "real": float(real)}


# --------------------------------------------------------------------------------------
# Resumen
# --------------------------------------------------------------------------------------


def resumen_desempeno(
    valores: pd.Series,
    flujos_externos: pd.Series,
    flujos_inversionista: pd.Series,
    *,
    valor_final: float | None = None,
    retornos_indice: pd.Series | None = None,
    tasa_libre_riesgo: float = 0.0,
    periodos_por_anio: int = PERIODOS_ANIO_DIARIO,
) -> dict[str, float | None]:
    """Panel completo de desempeño, con TWR y TIR lado a lado."""
    r = twr(valores, flujos_externos)
    fecha_final = pd.to_datetime(valores.index).max() if not valores.empty else None
    salida: dict[str, float | None] = {
        "twr_acumulado": twr_acumulado(valores, flujos_externos),
        "twr_anualizado": twr_anualizado(valores, flujos_externos),
        "tir": (
            tir_con_valor_final(flujos_inversionista, valor_final, fecha_final)
            if valor_final is not None and fecha_final is not None
            else tir(flujos_inversionista)
        ),
        "volatilidad": volatilidad(r, periodos_por_anio=periodos_por_anio),
        "sharpe": sharpe(r, tasa_libre_riesgo, periodos_por_anio=periodos_por_anio),
        "sortino": sortino(r, tasa_libre_riesgo, periodos_por_anio=periodos_por_anio),
        "drawdown_maximo": drawdown_maximo(valores),
        "drawdown_actual": drawdown_actual(valores),
    }
    if retornos_indice is not None:
        salida["beta"] = beta(r, retornos_indice)
        salida["alfa_anualizado"] = alfa_anualizado(r, retornos_indice, periodos_por_anio=periodos_por_anio)
    if salida["twr_anualizado"] is not None and salida["tir"] is not None:
        salida["brecha_twr_tir"] = salida["twr_anualizado"] - salida["tir"]
    return salida


EXPLICACION_TWR_VS_TIR = (
    "El TWR ponderado por tiempo mide la selección de activos: quita el efecto de "
    "cuándo metiste dinero. La TIR ponderada por dinero mide tu resultado real: lo "
    "incluye. Si el TWR es mayor que la TIR, aportaste más antes de los periodos malos. "
    "Si la TIR es mayor, tu timing ayudó. Confundirlos es el error más común al "
    "evaluar un portafolio propio."
)
