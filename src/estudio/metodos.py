"""Métodos de valuación en el tiempo: qué decía cada uno cada trimestre y qué pasó después.

La pregunta es práctica: ¿qué medida de «caro o barato» le hubiera servido a quien
compra O, NNN o WPC? Para cada método se arma, cada fin de mes y con lo publicado a esa
fecha (P1):

* un **valor** donde más alto es más barato (un yield o una prima);
* su **percentil expandible** contra la propia historia del emisor (P5): barato en el 70
  o más, caro abajo del 30, como el semáforo;
* lo que rindió el papel —retorno total neto de impuesto al dividendo— en los 1, 3 y 5
  años siguientes.

Y se evalúa de tres maneras, las tres reportadas completas para todos los métodos: la
correlación de rangos entre el percentil y el retorno siguiente; el retorno a 5 años
cuando el método decía barato contra cuando decía caro; y el backtest de aportación con
ese método (comprar, comprar menos, no comprar, sin vender y con la reinversión en 12
meses), contra aportar sin reglas al mismo papel (P6).

Hay una cuarta prueba, la que resultó útil: con los tres emisores a la vez, mandar la
aportación del mes al que está más barato contra su propia historia, sin guardar efectivo.

Siete métodos probados sobre tres emisores son 21 intentos: el mejor va a verse bien por
azar. Por eso cuenta más que un método funcione en los TRES emisores y en las dos mitades
de la historia que su cifra en uno solo; por eso la regla que se recomienda es el
consenso de los siete y no el que mejor salió; y por eso el veredicto formal sigue siendo
el de P7: con decenas de ventanas independientes, no cientos, INCONCLUSO.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import optimize, stats

from src.config import UMBRALES
from src.estudio import macro
from src.estudio import reglas as rg
from src.modelo.senal import percentil_expandible
from src.portafolio.metricas import DIAS_ANIO, tir
from src.simulacion.backtest import contar_apuestas

MIN_MESES = 3 * UMBRALES.valuacion.min_observaciones          # 36 meses = 12 trimestres
BARATO, CARO = UMBRALES.valuacion.percentil_compra, UMBRALES.valuacion.percentil_mantener


@dataclass(frozen=True)
class Metodo:
    clave: str
    nombre: str
    descripcion: str


METODOS: tuple[Metodo, ...] = (
    Metodo("multiplo", "Múltiplo P/FFO",
           "Precio ÷ flujo por acción conocido (FFO de Nareit; AFFO en WPC). Barato = múltiplo bajo "
           "contra su propia historia."),
    Metodo("prima_treasury", "Prima sobre el Treasury",
           "Yield de flujo menos el Treasury a 10 años. Es la Puerta 2 del semáforo."),
    Metodo("prima_real", "Prima sobre la tasa real",
           "Yield de flujo menos la tasa real: Treasury a 10 años menos la inflación de 12 meses. El "
           "flujo de un REIT crece con la inflación; compararlo contra una tasa nominal castiga los "
           "años de inflación alta."),
    Metodo("prima_baa", "Prima sobre bonos Baa",
           "Yield de flujo menos el rendimiento de los bonos corporativos Baa (Moody's): contra la "
           "alternativa de crédito, no contra la libre de riesgo."),
    Metodo("dividendo", "Yield de dividendo",
           "Dividendo regular vigente anualizado ÷ precio, contra su propia historia."),
    Metodo("spread_dividendo", "Dividendo sobre el Treasury",
           "Yield de dividendo menos el Treasury a 10 años: la lente «contra el bono» del estudio."),
    Metodo("multiplo_5a", "Múltiplo contra sus últimos 5 años",
           "Yield de flujo entre su mediana de los cinco años previos. No compara contra toda la "
           "historia sino contra el régimen reciente de tasas."),
    Metodo("consenso", "Consenso de los siete",
           "El promedio de los percentiles de los siete métodos (con al menos cuatro disponibles). Es "
           "la regla que se recomienda: no se escoge el método que mejor salió, porque con 21 "
           "intentos el mejor siempre sale bien por azar."),
)
NOMBRE = {m.clave: m.nombre for m in METODOS}
SIETE = tuple(m.clave for m in METODOS if m.clave != "consenso")


NOTAS_DE_METODO: tuple[str, ...] = (
    "Point-in-time (P1): el flujo por acción es el de los últimos 12 meses conocido a cada fecha, con "
    "la fecha real de publicación de cada cifra; el Treasury y los bonos Baa, el dato del día hábil "
    "anterior; el CPI de un mes, 45 días después de su fecha, que es cuando se publica.",
    "Percentil expandible (P5): cada fin de mes contra todos los fines de mes anteriores del mismo "
    "emisor, con al menos 36. Nunca contra otro emisor (P4): un yield de 7% puede ser caro en uno y "
    "barato en otro.",
    "Retornos siguientes: retorno total en dólares con el dividendo neto del 20% de impuesto, "
    "anualizado. La alternativa de esperar es el T-bill a 3 meses de esos mismos años, neto del 20%.",
    "La evaluación usa fines de trimestre para no contar tres veces casi el mismo mes. Aun así las "
    "ventanas de 5 años se enciman: las independientes son una por cada 20 trimestres.",
    "Backtest por emisor: la regla de «solo compras, reinversión en 12 meses» del estudio de reglas, "
    "con el percentil del método en lugar de la prima del semáforo y sin las puertas de calidad ni de "
    "deterioro: barato compra todo y la reserva, medio la mitad, caro nada; nunca vende.",
    "Asignación entre emisores: desde el primer mes en que los tres tienen percentil del método; la "
    "decisión de fin de mes se ejecuta al cierre de la sesión siguiente; 0.25% de comisión, 20% al "
    "dividendo y 10% a la ganancia al vender todo al final. El benchmark reparte en tercios y cada "
    "emisor reinvierte sus propios dividendos (P6 llevado a tres papeles).",
    "Controles: el espejo (todo al más caro) y cada mitad del periodo por separado, con su propia TIR, "
    "se fijaron antes de ver el resultado. El azar se endureció después: la primera versión sorteaba "
    "el emisor cada mes, reparte sola el dinero entre los tres y cualquier método le ganaba; la que "
    "queda conserva las rachas del método (200 sorteos, semilla fija, reproducible).",
    "Pruebas múltiples: siete métodos en tres emisores son 21 intentos. Por eso se recomienda el "
    "consenso y no el mejor, y por eso se exige que el resultado aparezca en los tres emisores y en "
    "las dos mitades. El consenso se definió después de ver los siete: no escoge por resultado, pero "
    "tampoco es una prueba a ciegas.",
    "Sesgo de supervivencia: O, NNN y WPC existen hoy y se escogieron hoy. La reversión a la media que "
    "aprovecha la asignación es la de emisores que sobrevivieron; en uno que se está muriendo, "
    "«barato» es una trampa. La regla solo debe repartir entre emisores que pasan la Puerta 1.",
)


def senal(percentil: float | None) -> str:
    if percentil is None or pd.isna(percentil):
        return "sin dato"
    return "barato" if percentil >= BARATO else ("caro" if percentil < CARO else "medio")


# --------------------------------------------------------------------------------------
# Panel mensual
# --------------------------------------------------------------------------------------


def _adelante(rt: pd.Series, fechas: pd.DatetimeIndex, anios: int) -> pd.Series:
    """Retorno total ANUALIZADO de los ``anios`` siguientes; vacío si todavía no pasan."""
    fin = rt.index[-1]
    salida = []
    for f in fechas:
        g = f + pd.DateOffset(years=anios)
        salida.append(float((rt.asof(g) / rt.asof(f)) ** (1 / anios) - 1) if g <= fin else np.nan)
    return pd.Series(salida, index=fechas)


def _efectivo(tbill: pd.Series, impuesto: float) -> pd.Series:
    """Valor acumulado de un dólar en T-bills, con el impuesto a los intereses."""
    t = tbill.dropna().sort_index()
    dias = t.index.to_series().diff().dt.days.fillna(0).to_numpy()
    crece = 1 + t.shift(1).fillna(0).to_numpy() * dias / 365 * (1 - impuesto)
    return pd.Series(np.cumprod(crece), index=t.index)


def panel(e, *, baa: pd.Series | None = None, cpi: pd.Series | None = None,
          tbill: pd.Series | None = None, parametros: rg.Parametros = rg.PARAMETROS) -> pd.DataFrame:
    """Cada fin de mes: los insumos, el valor y el percentil de cada método, y lo que pasó después."""
    t = e.tabla
    fechas = rg.fines_de_mes(t.index)
    baa = macro.cargar("baa") if baa is None else baa
    cpi = macro.cargar("cpi") if cpi is None else cpi
    tbill = rg.cargar_tbill() if tbill is None else tbill
    p = pd.DataFrame(index=fechas)
    p.index.name = "fecha"
    p["precio"] = t["precio_base"].reindex(fechas)
    columna = "affo_ttm" if e.medida.concepto == "affo_por_accion" else "ffo_ttm"
    p["flujo"] = t[columna].reindex(fechas)
    p["multiplo_flujo"] = p["precio"] / p["flujo"]
    p["yield_flujo"] = p["flujo"] / p["precio"]
    p["dividendo"] = t["dividendo_anualizado"].reindex(fechas)
    p["yield_dividendo"] = p["dividendo"] / p["precio"]
    p["treasury_10a"] = t["ust10"].reindex(fechas)
    precios = macro.conocido_en("cpi", cpi, fechas)
    hace_un_anio = macro.conocido_en("cpi", cpi, fechas - pd.DateOffset(years=1))
    p["inflacion_12m"] = precios.values / hace_un_anio.values - 1
    p["tasa_real"] = p["treasury_10a"] - p["inflacion_12m"]
    p["baa"] = macro.conocido_en("baa", baa, fechas) / 100

    # Valor de cada método: más alto = más barato.
    p["v_multiplo"] = p["yield_flujo"]
    p["v_prima_treasury"] = p["yield_flujo"] - p["treasury_10a"]
    p["v_prima_real"] = p["yield_flujo"] - p["tasa_real"]
    p["v_prima_baa"] = p["yield_flujo"] - p["baa"]
    p["v_dividendo"] = p["yield_dividendo"]
    p["v_spread_dividendo"] = p["yield_dividendo"] - p["treasury_10a"]
    # Mediana de los 60 meses PREVIOS (sin el actual), con al menos 36.
    previa = p["yield_flujo"].shift(1).rolling(60, min_periods=MIN_MESES).median()
    p["v_multiplo_5a"] = p["yield_flujo"] / previa - 1

    for clave in SIETE:
        v = p[f"v_{clave}"].dropna()
        p[f"p_{clave}"] = percentil_expandible(v, min_observaciones=MIN_MESES).reindex(fechas)
    percentiles = p[[f"p_{c}" for c in SIETE]]
    p["v_consenso"] = percentiles.mean(axis=1).where(percentiles.notna().sum(axis=1) >= 4)
    p["p_consenso"] = p["v_consenso"]
    for m in METODOS:
        p[f"s_{m.clave}"] = [senal(x) for x in p[f"p_{m.clave}"]]

    rt = t["rt_usd_neto"]
    p["retorno_total"] = rt.reindex(fechas)
    for anios in (1, 3, 5):
        p[f"adelante_{anios}a"] = _adelante(rt, fechas, anios)
    # La alternativa de esperar: el T-bill de esos mismos 5 años, neto de impuesto.
    efectivo = _efectivo(tbill, parametros.impuesto_intereses)
    p["efectivo_5a"] = (_adelante(efectivo, fechas, 5) if not efectivo.empty
                        else pd.Series(np.nan, index=fechas))
    p.loc[p.index + pd.DateOffset(years=5) > rt.index[-1], "efectivo_5a"] = np.nan
    return p


def trimestral(p: pd.DataFrame) -> pd.DataFrame:
    return p[p.index.month.isin([3, 6, 9, 12])]


# --------------------------------------------------------------------------------------
# Evaluación
# --------------------------------------------------------------------------------------


def _spearman(x: pd.Series, y: pd.Series) -> float:
    d = pd.concat([x, y], axis=1).dropna()
    if len(d) < 8:
        return np.nan
    return float(stats.spearmanr(d.iloc[:, 0], d.iloc[:, 1]).statistic)


def evaluar(p: pd.DataFrame, metodos: tuple[Metodo, ...] = METODOS, *, valor: str = "p_",
            senal: str = "s_") -> pd.DataFrame:
    """Por método: correlación con el retorno siguiente y el retorno cuando decía barato o caro.

    Sobre fines de trimestre, para no contar tres veces casi el mismo mes. Aun así las
    ventanas de 5 años se enciman: las independientes son ~trimestres ÷ 20. ``valor`` y
    ``senal`` son los prefijos de columna: el percentil y su señal, o —en los modelos de
    valor— el valor contra el precio y su señal absoluta.
    """
    q = trimestral(p)
    filas = []
    for m in metodos:
        pc, s = q[f"{valor}{m.clave}"], q[f"{senal}{m.clave}"]
        fila = {"metodo": m.nombre, "clave": m.clave,
                "trimestres": int(pc.notna().sum())}
        for anios in (1, 3, 5):
            fila[f"rho_{anios}a"] = _spearman(pc, q[f"adelante_{anios}a"])
        r5 = q["adelante_5a"]
        for nivel in ("barato", "medio", "caro"):
            sel = r5[(s == nivel) & r5.notna()]
            fila[f"r5_{nivel}"] = float(sel.median()) if len(sel) else np.nan
            fila[f"n_{nivel}"] = int(len(sel))
        fila["r5_barato_menos_caro"] = fila["r5_barato"] - fila["r5_caro"]
        # ¿Esperar en efectivo cuando dice caro hubiera convenido?
        caro = (s == "caro") & r5.notna() & q["efectivo_5a"].notna()
        exceso = (r5 - q["efectivo_5a"])[caro]
        fila["caro_contra_efectivo"] = float(exceso.median()) if len(exceso) else np.nan
        fila["caro_le_gana_al_efectivo"] = float((exceso > 0).mean()) if len(exceso) else np.nan
        con5 = pd.concat([pc, r5], axis=1).dropna()
        fila["ventanas_5a"] = round(len(con5) / 20, 1)
        mitad = len(con5) // 2
        fila["rho_5a_primera_mitad"] = _spearman(con5.iloc[:mitad, 0], con5.iloc[:mitad, 1])
        fila["rho_5a_segunda_mitad"] = _spearman(con5.iloc[mitad:, 0], con5.iloc[mitad:, 1])
        con_senal = s[s != "sin dato"]
        for nivel in ("barato", "medio", "caro"):
            fila[f"fraccion_{nivel}"] = float((con_senal == nivel).mean()) if len(con_senal) else np.nan
        filas.append(fila)
    return pd.DataFrame(filas).set_index("clave")


def evaluar_juntos(paneles: dict[str, pd.DataFrame], metodos: tuple[Metodo, ...] = METODOS, *,
                   valor: str = "p_", senal: str = "s_") -> pd.DataFrame:
    """Los tres emisores juntos. Vale porque cada percentil es contra la historia propia (P4)."""
    todos = pd.concat([trimestral(p).assign(emisor=t) for t, p in paneles.items()])
    filas = []
    for m in metodos:
        pc, s, r5 = todos[f"{valor}{m.clave}"], todos[f"{senal}{m.clave}"], todos["adelante_5a"]
        emisores_a_favor = sum(
            1 for t, p in paneles.items()
            if _spearman(trimestral(p)[f"{valor}{m.clave}"], trimestral(p)["adelante_5a"]) > 0
        )
        filas.append({
            "metodo": m.nombre, "clave": m.clave,
            "rho_1a": _spearman(pc, todos["adelante_1a"]),
            "rho_5a": _spearman(pc, r5),
            "r5_barato": float(r5[(s == "barato")].median()),
            "r5_caro": float(r5[(s == "caro")].median()),
            "emisores_con_rho_5a_positiva": emisores_a_favor,
            "ventanas_5a": round(pd.concat([pc, r5], axis=1).dropna().shape[0] / 20, 1),
        })
    t = pd.DataFrame(filas).set_index("clave")
    t["r5_barato_menos_caro"] = t["r5_barato"] - t["r5_caro"]
    return t


# --------------------------------------------------------------------------------------
# Backtest de aportación por método
# --------------------------------------------------------------------------------------


DECISION_DE_SENAL = {"barato": rg.Decision.COMPRAR.value, "medio": rg.Decision.COMPRAR_MENOS.value,
                     "caro": rg.Decision.NO_COMPRAR.value, "sin dato": rg.Decision.SIN_SENAL.value}


def senales_de_metodo(p: pd.DataFrame, clave: str, ticker: str, *, senal: str | None = None) -> rg.Senales:
    """Las decisiones de un método solo, sin puertas de calidad ni de deterioro.

    Por omisión, del percentil; con ``senal`` (p. ej. ``"a_"``), de esa columna de señal.
    """
    if senal is not None:
        decision = p[f"{senal}{clave}"].map(DECISION_DE_SENAL).fillna(rg.Decision.SIN_SENAL.value).to_numpy()
        return rg.Senales(ticker, pd.DataFrame({"decision": decision, "disparadores": ""}, index=p.index),
                          pd.DataFrame())
    pc = p[f"p_{clave}"]
    decision = np.where(pc.isna(), rg.Decision.SIN_SENAL.value,
                        np.where(pc >= BARATO, rg.Decision.COMPRAR.value,
                                 np.where(pc < CARO, rg.Decision.NO_COMPRAR.value, rg.Decision.COMPRAR_MENOS.value)))
    m = pd.DataFrame({"decision": decision, "disparadores": ""}, index=p.index)
    return rg.Senales(ticker, m, pd.DataFrame())


def backtest_metodos(e, p: pd.DataFrame, tbill: pd.Series | None = None,
                     metodos: tuple[Metodo, ...] = METODOS, *, senal: str | None = None,
                     parametros: rg.Parametros = rg.PARAMETROS) -> pd.DataFrame:
    """Cada método con la regla que mejor se portó en el backtest del semáforo: comprar,
    comprar menos o no comprar, nunca vender, y nada espera más de 12 meses."""
    tbill = rg.cargar_tbill() if tbill is None else tbill
    sen0 = rg.Senales(e.ticker, pd.DataFrame({"decision": rg.Decision.SIN_SENAL.value, "disparadores": ""},
                                              index=p.index), pd.DataFrame())
    bench = rg.simular(e, sen0, tbill, variante=rg.Variante.BENCHMARK, parametros=parametros)
    filas = []
    for m in metodos:
        sen = senales_de_metodo(p, m.clave, e.ticker, senal=senal)
        s = rg.simular(e, sen, tbill, variante=rg.Variante.SOLO_VALUACION_12M, parametros=parametros)
        cambios = contar_apuestas(s.ejecuciones["intensidad"].fillna(1.0), 1.0)
        filas.append({
            "metodo": m.nombre, "clave": m.clave,
            "tir_usd": s.tir_usd, "tir_sin_reglas": bench.tir_usd,
            "ventaja_tir": (s.tir_usd or np.nan) - (bench.tir_usd or np.nan),
            "multiplo": s.valor_final_neto / s.aportado,
            "exposicion": float((s.diaria["valor_posicion"] / s.diaria["riqueza"].where(s.diaria["riqueza"] > 0)).mean()),
            "cambios_de_postura": int(cambios.episodios),
        })
    return pd.DataFrame(filas).set_index("clave")




# --------------------------------------------------------------------------------------
# ¿A cuál de los tres? Asignación de la aportación entre emisores
# --------------------------------------------------------------------------------------


@dataclass
class Mercado:
    """Los tres papeles en sesiones comunes, en arreglos, para simular rápido."""

    tickers: list[str]
    sesiones: pd.DatetimeIndex
    precio: np.ndarray        # sesiones × emisores
    dividendo: np.ndarray     # por acción, en su fecha ex
    escision: np.ndarray      # factor; 1 si no hubo
    fines: pd.DatetimeIndex   # fines de mes de las sesiones comunes
    ejecucion: np.ndarray     # índice de la sesión en que se ejecuta cada fin de mes


def mercado_comun(estudios: dict) -> Mercado:
    tickers = sorted(estudios)
    sesiones = estudios[tickers[0]].tabla.index
    for t in tickers[1:]:
        sesiones = sesiones.intersection(estudios[t].tabla.index)
    n, k = len(sesiones), len(tickers)
    precio = np.column_stack([estudios[t].tabla["precio_base"].reindex(sesiones).ffill().to_numpy(float)
                              for t in tickers])
    dividendo, escision = np.zeros((n, k)), np.ones((n, k))
    for j, t in enumerate(tickers):
        hm = estudios[t].historia_mercado
        pos = sesiones.searchsorted(pd.DatetimeIndex(hm.dividendos["fecha_ex"]), side="left")
        ok = pos < n
        np.add.at(dividendo[:, j], pos[ok], hm.dividendos["monto_base"].to_numpy(float)[ok])
        for ev in hm.escisiones:
            i = sesiones.searchsorted(pd.Timestamp(ev.fecha), side="left")
            if i < n:
                escision[i, j] *= ev.factor
    fines = rg.fines_de_mes(sesiones)
    ejec = sesiones.searchsorted(fines, side="right")
    fines, ejec = fines[ejec < n], ejec[ejec < n]
    return Mercado(tickers, sesiones, precio, dividendo, escision, fines, ejec)


def tir_rapida(fechas: pd.DatetimeIndex, montos: np.ndarray) -> float | None:
    """La misma TIR que ``portafolio.metricas.tir`` (365.25 días, raíz entre −99.99% y
    1,000%), sin pandas en el ciclo: las 200 elecciones al azar la llaman 1,600 veces.
    La prueba 53 verifica que den lo mismo."""
    if not ((montos < 0).any() and (montos > 0).any()):
        return None
    anios = (fechas - fechas.min()).days.to_numpy(float) / DIAS_ANIO

    def vpn(r: float) -> float:
        return float(np.sum(montos / (1.0 + r) ** anios))

    try:
        return float(optimize.brentq(vpn, -0.9999, 10.0, xtol=1e-10, maxiter=500))
    except ValueError:
        return tir(pd.Series(montos, index=fechas))


@dataclass
class Corrida:
    valor_neto: float
    aportado: float
    tir_usd: float | None
    riqueza: pd.Series


def correr(m: Mercado, meses: np.ndarray, eleccion: np.ndarray, *, fin: int | None = None,
           propio: bool = False, parametros: rg.Parametros = rg.PARAMETROS) -> Corrida:
    """Aportación de ``meses`` (posiciones en ``m.fines``) al emisor ``eleccion`` (−1 = partes iguales).

    Con ``propio=True`` cada emisor reinvierte sus propios dividendos (el benchmark de P6
    llevado a tres papeles); si no, los dividendos de los tres se suman al dinero del mes
    y siguen la misma elección. Nunca se vende antes del final ni se guarda efectivo.
    """
    p = parametros
    k = len(m.tickers)
    fin = len(m.sesiones) - 1 if fin is None else fin
    ejec = m.ejecucion[meses]
    elige = dict(zip(ejec.tolist(), eleccion.tolist(), strict=True))
    inicio = int(ejec[0])
    eventos = np.unique(np.concatenate([
        ejec, np.nonzero(m.dividendo.any(axis=1))[0], np.nonzero((m.escision != 1).any(axis=1))[0]]))
    eventos = eventos[(eventos >= inicio) & (eventos <= fin)]
    acciones, costo, pendiente = np.zeros(k), np.zeros(k), np.zeros(k)
    guardado_acc, guardado_pend = np.zeros((len(eventos), k)), np.zeros((len(eventos), k))
    neto = 1 - p.impuesto_dividendo
    for n, i in enumerate(eventos):
        px = m.precio[i]
        pendiente += acciones * m.dividendo[i] * neto + acciones * px * (m.escision[i] - 1)
        if i in elige:
            j = elige[i]
            if propio or j < 0:
                pendiente += p.aportacion / k
                monto = pendiente if propio else np.full(k, pendiente.sum() / k)
            else:
                monto = np.zeros(k)
                monto[j] = pendiente.sum() + p.aportacion
            acciones += monto * (1 - p.comision) / px
            costo += monto
            pendiente = np.zeros(k)
        guardado_acc[n], guardado_pend[n] = acciones, pendiente
    ses = np.arange(inicio, fin + 1)
    ultimo = np.searchsorted(eventos, ses, side="right") - 1
    riqueza = (guardado_acc[ultimo] * m.precio[ses]).sum(axis=1) + guardado_pend[ultimo].sum(axis=1)
    bruto = acciones * m.precio[fin]
    com = bruto * p.comision
    valor = float((bruto - com - np.maximum(bruto - com - costo, 0.0) * p.impuesto_ganancia).sum()
                  + pendiente.sum())
    ejecutadas = ejec[ejec <= fin]
    fechas = m.sesiones[np.append(ejecutadas, fin)]
    montos = np.append(np.full(len(ejecutadas), -p.aportacion), valor)
    return Corrida(valor, p.aportacion * len(ejecutadas), tir_rapida(fechas, montos),
                   pd.Series(riqueza, index=m.sesiones[ses]))


def percentiles_en(m: Mercado, paneles: dict[str, pd.DataFrame], clave: str, prefijo: str = "p_") -> np.ndarray:
    """Meses × emisores: el percentil de cada uno (o la columna ``prefijo``) a cada fin de mes común."""
    return np.column_stack([paneles[t][f"{prefijo}{clave}"].reindex(m.fines).to_numpy(float) for t in m.tickers])


@dataclass
class Asignacion:
    metodo: str
    clave: str
    desde: pd.Timestamp
    hasta: pd.Timestamp
    tir_usd: float | None
    tir_partes_iguales: float | None
    tir_el_mas_caro: float | None
    multiplo: float
    multiplo_partes_iguales: float
    meses_por_emisor: dict[str, int]
    cambios: int
    azar: np.ndarray                 # ventaja de TIR de elecciones al azar
    mitades: list[tuple[str, float]]
    eleccion_hoy: str
    riqueza: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    riqueza_partes_iguales: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))

    @property
    def ventaja(self) -> float:
        return (self.tir_usd or np.nan) - (self.tir_partes_iguales or np.nan)

    @property
    def ventaja_el_mas_caro(self) -> float:
        return (self.tir_el_mas_caro or np.nan) - (self.tir_partes_iguales or np.nan)

    @property
    def azar_que_le_gana(self) -> float:
        """Qué fracción de las elecciones al azar le ganó al método."""
        return float(np.mean(self.azar >= self.ventaja)) if len(self.azar) else np.nan


def _al_azar(rachas: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    """Un emisor al azar por racha, distinto del de la racha anterior."""
    elegidos = [int(rng.integers(0, k))]
    for _ in rachas[1:]:
        otro = int(rng.integers(0, k - 1))
        elegidos.append(otro + (otro >= elegidos[-1]))
    return np.repeat(elegidos, rachas)


def asignar(m: Mercado, paneles: dict[str, pd.DataFrame], clave: str, *, n_azar: int = 200,
            semilla: int = 7, parametros: rg.Parametros = rg.PARAMETROS, prefijo: str = "p_",
            nombre: str | None = None) -> Asignacion:
    """Toda la aportación del mes al emisor más barato CONTRA SU PROPIA HISTORIA (P4).

    Tres controles: partes iguales (el benchmark), el espejo —al más caro— que debería
    salir peor si el método sirve, y ``n_azar`` elecciones al azar entre los mismos tres,
    para ver qué tan raro es el resultado.
    Las elecciones al azar conservan las RACHAS del método (cuántos meses seguidos se
    queda en un emisor y cuántas veces cambia) y solo sortean a cuál: un azar que cambia
    cada mes reparte solo el dinero entre los tres y es demasiado fácil de vencer.
    Además se corre por separado en cada mitad del periodo.
    """
    pc = percentiles_en(m, paneles, clave, prefijo)
    meses = np.nonzero(~np.isnan(pc).any(axis=1))[0]
    if len(meses) < 24:
        raise ValueError(f"{clave}: menos de dos años con percentil en los tres emisores")
    pcm = pc[meses]
    barato = np.argmax(pcm, axis=1)
    caro = np.argmin(pcm, axis=1)
    iguales = np.full(len(meses), -1)
    r = correr(m, meses, barato, parametros=parametros)
    b = correr(m, meses, iguales, propio=True, parametros=parametros)
    c = correr(m, meses, caro, parametros=parametros)
    rng = np.random.default_rng(semilla)
    k = len(m.tickers)
    cortes = np.flatnonzero(np.diff(barato) != 0) + 1
    rachas = np.diff(np.concatenate([[0], cortes, [len(barato)]]))
    azar = np.array([(correr(m, meses, _al_azar(rachas, k, rng), parametros=parametros).tir_usd or np.nan)
                     - (b.tir_usd or np.nan) for _ in range(n_azar)])
    mitades = []
    corte = len(meses) // 2
    for mitad, sel in (("primera mitad", slice(0, corte)), ("segunda mitad", slice(corte, None))):
        ms = meses[sel]
        fin = int(m.ejecucion[meses[corte]]) if mitad == "primera mitad" else None
        rm = correr(m, ms, barato[sel], fin=fin, parametros=parametros)
        bm = correr(m, ms, iguales[sel], fin=fin, propio=True, parametros=parametros)
        etiqueta = f"{mitad} ({m.fines[ms[0]]:%Y-%m} a {m.fines[ms[-1]]:%Y-%m})"
        mitades.append((etiqueta, (rm.tir_usd or np.nan) - (bm.tir_usd or np.nan)))
    hoy = pc[-1]
    return Asignacion(
        metodo=nombre or NOMBRE[clave], clave=clave,
        desde=m.sesiones[m.ejecucion[meses[0]]], hasta=m.sesiones[-1],
        tir_usd=r.tir_usd, tir_partes_iguales=b.tir_usd, tir_el_mas_caro=c.tir_usd,
        multiplo=r.valor_neto / r.aportado, multiplo_partes_iguales=b.valor_neto / b.aportado,
        meses_por_emisor={t: int((barato == j).sum()) for j, t in enumerate(m.tickers)},
        cambios=int((np.diff(barato) != 0).sum()),
        azar=azar, mitades=mitades,
        eleccion_hoy=m.tickers[int(np.nanargmax(hoy))] if not np.isnan(hoy).all() else "sin dato",
        riqueza=r.riqueza, riqueza_partes_iguales=b.riqueza,
    )


def tabla_asignaciones(asignaciones: list[Asignacion]) -> pd.DataFrame:
    return pd.DataFrame([{
        "metodo": a.metodo, "clave": a.clave, "desde": a.desde,
        "tir_usd": a.tir_usd, "tir_partes_iguales": a.tir_partes_iguales, "ventaja": a.ventaja,
        "ventaja_el_mas_caro": a.ventaja_el_mas_caro, "azar_que_le_gana": a.azar_que_le_gana,
        **{f"ventaja_{n.split(' (')[0].replace(' ', '_')}": v for n, v in a.mitades},
        "cambios": a.cambios, **{f"meses_{t}": n for t, n in a.meses_por_emisor.items()},
        "eleccion_hoy": a.eleccion_hoy,
    } for a in asignaciones]).set_index("clave")


# --------------------------------------------------------------------------------------
# Todo junto
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoMetodos:
    paneles: dict[str, pd.DataFrame]
    evaluaciones: dict[str, pd.DataFrame]
    juntos: pd.DataFrame
    backtests: dict[str, pd.DataFrame]
    asignaciones: list[Asignacion]
    nombres: dict[str, str]
    hasta: pd.Timestamp
    intrinsecos: object = None      # ``intrinsecos.ResultadoIntrinsecos``

    def hoy(self) -> pd.DataFrame:
        """Qué dice cada método hoy para cada emisor."""
        filas = []
        for t, p in self.paneles.items():
            ultimo = p.iloc[-1]
            for m in METODOS:
                filas.append({"emisor": t, "metodo": m.nombre, "clave": m.clave,
                              "valor": ultimo[f"v_{m.clave}"], "percentil": ultimo[f"p_{m.clave}"],
                              "senal": ultimo[f"s_{m.clave}"]})
        return pd.DataFrame(filas)

    def asignacion(self) -> pd.DataFrame:
        return tabla_asignaciones(self.asignaciones)


def estudiar(estudios: dict, *, n_azar: int = 200, intrinsecos: bool = True) -> ResultadoMetodos:
    baa, cpi, tbill = macro.cargar("baa"), macro.cargar("cpi"), rg.cargar_tbill()
    paneles = {t: panel(e, baa=baa, cpi=cpi, tbill=tbill) for t, e in estudios.items()}
    evaluaciones = {t: evaluar(p) for t, p in paneles.items()}
    backtests = {t: backtest_metodos(e, paneles[t], tbill) for t, e in estudios.items()}
    m = mercado_comun(estudios)
    r = ResultadoMetodos(
        paneles=paneles, evaluaciones=evaluaciones, juntos=evaluar_juntos(paneles), backtests=backtests,
        asignaciones=[asignar(m, paneles, x.clave, n_azar=n_azar) for x in METODOS],
        nombres={t: (e.narrativa.nombre if e.narrativa else t) for t, e in estudios.items()},
        hasta=max(e.tabla.index[-1] for e in estudios.values()),
    )
    if intrinsecos:
        from src.estudio import intrinsecos as it

        r.intrinsecos = it.estudiar(estudios, paneles, n_azar=n_azar, tbill=tbill)
    return r


# --------------------------------------------------------------------------------------
# Conclusiones en texto
# --------------------------------------------------------------------------------------


def _pct(x: float, decimales: int = 1) -> str:
    return "—" if x is None or pd.isna(x) else f"{x:.{decimales}%}"


def _pb(x: float) -> str:
    return "—" if x is None or pd.isna(x) else f"{x * 1e4:+,.0f} pb"


def _cuantos(n: int) -> str:
    return {2: "dos", 3: "tres", 4: "cuatro", 5: "cinco"}.get(n, str(n))


def ventaja_acumulada(a: Asignacion) -> pd.Series:
    """Riqueza con el método entre riqueza con partes iguales, menos uno, cada fin de mes."""
    base = a.riqueza_partes_iguales.resample("ME").last()
    return (a.riqueza.resample("ME").last() / base.where(base > 0) - 1).dropna()


def _como_llego(a: Asignacion) -> str:
    """La ventaja no llega pareja: en qué años se hizo y qué pasó en los últimos cinco."""
    v = ventaja_acumulada(a)
    if len(v) < 72:
        return ""
    salto = (v - v.shift(12)).dropna()
    anio = salto.idxmax().year
    hace5 = v.asof(v.index[-1] - pd.DateOffset(years=5))
    return (f"La ventaja no llegó pareja: el salto más grande fue en {anio - 1}–{anio}, y en los últimos "
            f"5 años la riqueza relativa pasó de {hace5:+.1%} a {v.iloc[-1]:+.1%}.")


def conclusiones(r: ResultadoMetodos) -> list[rg.Conclusion]:
    c: list[rg.Conclusion] = []
    j = r.juntos
    siete = j.loc[list(SIETE)]
    n = len(r.paneles)
    a_favor = int((siete["emisores_con_rho_5a_positiva"] == n).sum())
    cons = j.loc["consenso"]
    orden = (siete["rho_5a"].rank() + siete["r5_barato_menos_caro"].rank()).sort_values(ascending=False)
    mejores, peores = [NOMBRE[x] for x in orden.index[:2]], [NOMBRE[x] for x in orden.index[-2:]]
    quienes = "Los siete métodos tienen" if a_favor == len(SIETE) else f"{a_favor} de los siete métodos tienen"
    predicen = cons["r5_barato_menos_caro"] > 0
    arranque = ("Sí, y de forma consistente." if predicen and a_favor == len(SIETE) else
                "En general sí, pero no en todos los casos." if predicen and a_favor >= 4 else
                "No de forma consistente.")
    c.append(rg.Conclusion(
        "¿Los métodos de valuación predicen?",
        f"{arranque} {quienes} correlación positiva entre su percentil y el retorno "
        f"de los 5 años siguientes en los {_cuantos(n)} emisores. Con el consenso de los siete, los trimestres "
        f"en que decía «barato» rindieron después {_pct(cons['r5_barato'])} al año (mediana a 5 años) "
        f"y los que decía «caro», {_pct(cons['r5_caro'])}: {cons['r5_barato_menos_caro'] * 100:.1f} "
        f"puntos al año de diferencia. Los que mejor separan: {mejores[0]} y {mejores[1]}; los más "
        f"débiles: {peores[0]} y {peores[1]}.",
        "favorable" if predicen and a_favor >= 4 else "desfavorable"))

    ganan = [float(ev.loc["consenso", "caro_le_gana_al_efectivo"]) for ev in r.evaluaciones.values()]
    bt = pd.concat(r.backtests)
    mejor_bt = float(bt["ventaja_tir"].max())
    c.append(rg.Conclusion(
        "Entonces, ¿por qué esperar a que esté barato no paga?",
        f"Porque «caro» en un REIT de calidad no quiere decir «mal negocio»: quiere decir «menos bueno "
        f"que de costumbre». Cuando el consenso decía caro, el papel igual le ganó al T-bill en los 5 "
        f"años siguientes entre {min(ganan):.0%} y {max(ganan):.0%} de las veces, según el emisor. "
        f"Guardar la aportación en efectivo esperando lo barato cambia un retorno alto por uno bajo, "
        f"y la regla de 12 meses no alcanza a compensarlo: con cualquiera de los ocho métodos, comprar "
        f"menos o no comprar cuando está caro queda entre {_pb(float(bt['ventaja_tir'].min()))} y "
        f"{_pb(mejor_bt)} al año contra aportar siempre al mismo papel. Es la misma razón por la que "
        f"el semáforo completo salió mediocre.",
        "desfavorable"))

    tabla = r.asignacion()
    ca = tabla.loc["consenso"]
    siete_a = tabla.loc[list(SIETE)]
    a = next(x for x in r.asignaciones if x.clave == "consenso")
    iguales = int(round(ca["azar_que_le_gana"] * len(a.azar)))
    azar = ("ninguna igualó al consenso" if iguales == 0 else
            f"solo {iguales} ({ca['azar_que_le_gana']:.1%}) igualaron al consenso")
    pierden = int((tabla["ventaja_el_mas_caro"] < 0).sum())
    espejo = "los ocho" if pierden == len(tabla) else f"{pierden} de los ocho"
    ganan_a = int((siete_a["ventaja"] > 0).sum())
    quienes_a = ("con cada uno de los siete métodos" if ganan_a == len(SIETE) else
                 f"con {ganan_a} de los siete métodos")
    mitades_ok = ca["ventaja_primera_mitad"] > 0 and ca["ventaja_segunda_mitad"] > 0
    solido = pierden == len(tabla) and ca["azar_que_le_gana"] <= 0.05 and mitades_ok and ca["ventaja"] > 0
    controles = (
        f"el espejo —mandarla al más caro— pierde con {espejo}; de {len(a.azar)} elecciones al azar "
        f"con las mismas rachas, {azar}; y en cada mitad de la historia la ventaja es "
        f"{_pb(ca['ventaja_primera_mitad'])} y {_pb(ca['ventaja_segunda_mitad'])}")
    c.append(rg.Conclusion(
        f"Donde sí sirve: a cuál de los {_cuantos(n)} va la aportación",
        f"Con los {_cuantos(n)} emisores, mandar TODA la aportación del mes al que está más barato contra "
        f"su propia historia —sin guardar efectivo y sin vender— le ganó a repartirla en partes iguales "
        f"{quienes_a} (de {_pb(float(siete_a['ventaja'].min()))} a {_pb(float(siete_a['ventaja'].max()))} "
        f"al año); con el consenso, {_pb(ca['ventaja'])} (TIR {_pct(ca['tir_usd'], 2)} contra "
        f"{_pct(ca['tir_partes_iguales'], 2)}, desde {ca['desde']:%Y}). "
        + (f"Tres controles lo respaldan: {controles}." if solido else
           f"Los controles no alcanzan para respaldarlo: {controles}."),
        "favorable" if solido else "neutral"))

    hoy = r.hoy()
    ch = hoy[hoy["clave"] == "consenso"].set_index("emisor")
    texto_hoy = "; ".join(f"{t} en el percentil {ch.loc[t, 'percentil']:.0%} ({ch.loc[t, 'senal']})"
                          for t in ch.index if pd.notna(ch.loc[t, "percentil"]))
    votos = tabla["eleccion_hoy"].value_counts()
    baratos = [t for t in ch.index if ch.loc[t, "senal"] == "barato"]
    cierre = (f"{', '.join(baratos)} está barato contra su historia." if baratos else
              "Ninguno de los tres está barato contra su historia, pero la evidencia dice que eso no "
              "es razón para dejar de aportar: el dinero entra completo, solo cambia a cuál.")
    c.append(rg.Conclusion(
        "Qué hacer hoy",
        f"Con el consenso al {r.hasta:%d-%m-%Y}: {texto_hoy}. La aportación de este mes iría a "
        f"{ca['eleccion_hoy']} ({votos.get(ca['eleccion_hoy'], 0)} de los ocho métodos coinciden). "
        f"{cierre}",
        "neutral"))

    c.append(rg.Conclusion(
        "Qué tanto se le puede creer",
        f"Son {int(ca['cambios'])} cambios de emisor en {ca['desde']:%Y}–{r.hasta:%Y} y unas "
        f"{float(cons['ventanas_5a']):.0f} ventanas de 5 años independientes: lejos de las 100 apuestas "
        f"que pide P7, así que el dictamen formal es INCONCLUSO. {_como_llego(a)} Además los tres emisores sobrevivieron "
        f"y se escogieron hoy: un REIT barato porque se estaba muriendo no está en la muestra, y en ese "
        f"caso comprar lo más barato duele. Por eso la regla solo debe repartir entre emisores que "
        f"pasan la Puerta 1 de calidad.",
        "neutral"))
    return c
