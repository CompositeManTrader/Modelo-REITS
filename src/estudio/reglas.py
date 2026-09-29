"""Reglas de decisión —comprar, comprar menos, no comprar, vender por tesis rota— y su backtest.

El modelo es el semáforo de la aplicación, no uno nuevo
=======================================================
Cada fin de mes se evalúa ``senal.evaluar_semaforo`` —la MISMA función que pinta la
pantalla de valuación— con lo que se había publicado a esa fecha (P1), y su acción se
traduce a qué hacer con el dinero del mes:

==========================  ==================  ==============================================
Semáforo                    Decisión            Dinero del mes (aportación + dividendos netos)
==========================  ==================  ==============================================
COMPRAR (prima ≥ pctl 70)   COMPRAR             todo, más toda la reserva acumulada
MANTENER (pctl 30–70)       COMPRAR MENOS       la mitad; la otra mitad a la reserva
NO COMPRAR MÁS (< pctl 30)  NO COMPRAR          todo a la reserva
DESCARTADO (Puerta 1)       NO COMPRAR          todo a la reserva
VENDER (Puerta 3)           VENDER              se vende toda la posición; todo a la reserva
INCONCLUSO (faltan datos)   SIN SEÑAL           todo, como el benchmark
==========================  ==================  ==============================================

La reserva es efectivo en dólares que rinde el T-bill a 3 meses. Después de vender no
hay regla de recompra aparte: lo vendido vuelve al papel cuando el semáforo dice
COMPRAR —la Puerta 3 dejó de disparar, la calidad pasa y está barato—; mientras
tanto, lo que entra cada mes sigue la tabla.

Los umbrales son los de ``config.UMBRALES`` —payout 90% y 100%, 6.5x de deuda,
percentiles 70 y 30, dos trimestres seguidos— y se fijaron para la pantalla, antes de
este backtest. Lo único nuevo es la mitad de COMPRAR MENOS, y por eso la sensibilidad
se reporta completa (0%, 50% y 100%), sin escoger la que mejor salió.

Regla de reinversión en 12 meses (probada aparte, escrita antes de correrla)
===========================================================================
Ningún dólar espera más de 12 meses en la reserva mientras la tesis esté en pie:

1. Lo vendido por tesis rota —y todo lo que llegó a la reserva mientras la Puerta 3
   disparaba— vuelve al papel en 12 partes iguales, una por mes, a partir del primer
   mes en que la Puerta 3 deja de disparar, esté caro o barato.
2. Lo que COMPRAR MENOS y NO COMPRAR mandan a la reserva (y sus intereses) se compra a
   más tardar 12 meses después.
3. Si la Puerta 3 vuelve a disparar, todo se detiene; COMPRAR sigue llevándose la
   reserva completa en cuanto aparece.

Lo que el backtest NO puede hacer
=================================
Con 30 años y una señal lenta hay decenas de decisiones independientes por emisor, no
cientos. El dictamen pasa por las salvaguardas del proyecto (``simulacion.backtest``):
benchmark del mismo activo (P6), apuestas efectivas (P7), beta neutralizada (P8) y
TIR money-weighted (P9). Debajo de 100 apuestas el veredicto es INCONCLUSO aunque el
modelo haya ganado: sirve para ver cómo se hubiera comportado, no para probar que
funciona.

Adaptaciones a la historia larga, declaradas
============================================
* La prima de la Puerta 2 usa la medida de valuación del estudio de cada emisor (FFO
  de Nareit para O y NNN, AFFO para WPC): el percentil necesita la MISMA medida en
  toda la historia, y el AFFO de O y NNN empieza en 2012-2013.
* Los criterios de las Puertas 1 y 3 —payout, crecimiento por acción, spread de
  inversión— usan el AFFO donde el emisor ya lo publicaba y el FFO antes; el
  crecimiento se mide siempre dentro de la misma medida.
* El spread de inversión es el de ``modelo.valuacion``: cap rate de compra menos el
  costo marginal de capital, 35% deuda a su costo en libros y 65% acciones a su
  yield de flujo.
* Deuda neta ÷ EBITDA: la que reporta el emisor, y si no, la derivada de XBRL desde el
  año en que la derivación es confiable. Una cifra anual vale 18 meses después del
  cierre de su año; más vieja no se usa.
* Grado de inversión: ``data/estudios/calificaciones.csv``, con fuente. No tener
  calificación reprueba la Puerta 1, pero no es una PÉRDIDA del grado de inversión:
  la Puerta 3 solo dispara si lo tuvo y lo perdió.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    DIR_ESTUDIOS,
    ISR_ADICIONAL_MEXICO_DIVIDENDO_EXTRANJERO,
    RETENCION_EEUU_W8BEN,
    TASA_CEDULAR_GANANCIAS_SIC,
    UMBRALES,
)
from src.estudio import macro
from src.estudio.mercado import dividendo_ttm
from src.modelo.senal import Accion, Luz, evaluar_semaforo, percentil_expandible
from src.portafolio.metricas import tir
from src.simulacion.backtest import (
    ConteoApuestas,
    DictamenBacktest,
    ResultadoBacktest,
    ResultadoNeutralizacion,
    TipoRegla,
    contar_apuestas,
    dictaminar,
    neutralizar_beta,
)

ARCHIVO_CALIFICACIONES = "calificaciones.csv"


# --------------------------------------------------------------------------------------
# Decisiones y parámetros
# --------------------------------------------------------------------------------------


class Decision(StrEnum):
    COMPRAR = "COMPRAR"
    COMPRAR_MENOS = "COMPRAR MENOS"
    NO_COMPRAR = "NO COMPRAR"
    VENDER = "VENDER"
    SIN_SENAL = "SIN SEÑAL"


DE_SEMAFORO: dict[Accion, Decision] = {
    Accion.COMPRAR: Decision.COMPRAR,
    Accion.MANTENER: Decision.COMPRAR_MENOS,
    Accion.NO_COMPRAR_MAS: Decision.NO_COMPRAR,
    Accion.DESCARTADO: Decision.NO_COMPRAR,
    Accion.VENDER: Decision.VENDER,
    Accion.INCONCLUSO: Decision.SIN_SENAL,
}


class Variante(StrEnum):
    """El modelo completo, sus dos mitades por separado y el benchmark del mismo activo."""

    MODELO = "Modelo completo"
    MODELO_12M = "Modelo, reinversión en 12 meses"
    SOLO_VALUACION = "Solo compras (nunca vende)"
    SOLO_VALUACION_12M = "Solo compras, reinversión en 12 meses"
    SOLO_TESIS = "Solo tesis rota (compra fija)"
    BENCHMARK = "Aportación fija, sin reglas"


@dataclass(frozen=True)
class Parametros:
    aportacion: float = 1_000.0            # dólares al mes; la escala no cambia ninguna tasa
    fraccion_comprar_menos: float = 0.5    # lo único que no viene del semáforo: ver la sensibilidad
    # Impuestos de un residente mexicano que compra vía SIC (``src.fiscal.mexico``).
    impuesto_dividendo: float = RETENCION_EEUU_W8BEN + ISR_ADICIONAL_MEXICO_DIVIDENDO_EXTRANJERO
    impuesto_ganancia: float = TASA_CEDULAR_GANANCIAS_SIC
    # El proyecto no modela el ISR de los intereses. Se les cobra lo mismo que al
    # dividendo: conservador EN CONTRA del modelo, que es el que tiene reserva.
    impuesto_intereses: float = RETENCION_EEUU_W8BEN + ISR_ADICIONAL_MEXICO_DIVIDENDO_EXTRANJERO
    comision: float = 0.0025               # por compra y por venta, a los dos por igual
    peso_deuda_cmc: float = 0.35           # el de ``modelo.valuacion.costo_marginal_de_capital``
    vigencia_anual_meses: int = 18
    rezago_anual_dias: int = 90            # 10-K: la cifra del año se conoce ~90 días después
    min_meses_percentil: int = 3 * UMBRALES.valuacion.min_observaciones   # 12 trimestres
    # La persistencia de la Puerta 3 se cuenta en reportes nuevos (ver ``senales``).
    # False la cuenta por trimestre de calendario: solo para mostrar la diferencia.
    persistencia_por_reporte: bool = True
    # Meses máximos que un dólar espera en la reserva con la tesis en pie (ver el
    # docstring del módulo). Lo usan solo las variantes «reinversión en 12 meses».
    reinversion_meses: int = 12


PARAMETROS = Parametros()

# Lo que el lector necesita saber para creerle al backtest, en el orden en que importa.
NOTAS_DE_METODO: tuple[str, ...] = (
    "Cada fin de mes se evalúa `senal.evaluar_semaforo` —la misma función de la pantalla de "
    "valuación— con lo publicado a esa fecha (P1), y la decisión se ejecuta al cierre de la "
    "sesión siguiente: nadie opera al mismo cierre con el que se calcula la señal.",
    "La prima de la Puerta 2 usa la medida de valuación del estudio de cada emisor (FFO para O y "
    "NNN, AFFO para WPC): el percentil necesita la misma medida en toda la historia, y el AFFO de "
    "O y NNN empieza en 2012-2013. El percentil es expandible (P5) y pide 36 meses de historia.",
    "Payout, crecimiento por acción y spread de inversión usan el AFFO donde el emisor ya lo "
    "publicaba y el FFO antes. El spread es el de la pantalla: cap rate de compra menos 35% del "
    "costo de la deuda y 65% del yield de flujo. Una cifra anual vale 18 meses después de su "
    "cierre; más vieja no se usa.",
    "Grado de inversión: sin calificación reprueba la calidad, pero no es PERDER el grado de "
    "inversión, que es lo que vende la Puerta 3.",
    "Tres correcciones de mecánica, hechas después de la primera corrida y sin tocar un "
    "umbral: (1) el payout divide el dividendo del mismo periodo que cubre el flujo —con el "
    "dividendo de hoy y el AFFO anual del año pasado, O salía con 106% en 2013 y vendía—; (2) "
    "los «dos trimestres seguidos» de la Puerta 3 se cuentan en reportes nuevos: antes de 2019 "
    "la cifra es anual y un solo año malo aparecía en dos cierres de trimestre; (3) la variante "
    "«solo tesis rota» nunca recompraba lo vendido: ahora vuelve a invertir todo en cuanto la "
    "Puerta 3 deja de disparar.",
    "Revisión con lupa, después de la segunda corrida: (4) el crecimiento compara el periodo contra "
    "el mismo periodo un año antes; antes comparaba «lo sabido hoy» contra «lo sabido hace 365 días», "
    "y cuando la fecha de publicación se movía unos días comparaba, por ejemplo, 2001 contra 1999; (5) "
    "cuando dos años se publicaron el mismo día, el anterior se perdía y el crecimiento no se podía "
    "medir; (6) la deuda neta ÷ EBITDA de WPC de 2012 (6.7x) no se usa: la nota del mismo suplemento "
    "dice que el EBITDA junta 9 meses sin CPA:15 contra la deuda de fin de año que ya la incluye. El "
    "motor se concilió al centavo contra precio, dividendos, intereses, comisiones e impuestos, y el "
    "Treasury contra FRED día por día.",
    "Impuestos de un residente mexicano vía SIC: 20% al dividendo (10% de retención con W-8BEN y "
    "10% de ISR adicional), 10% cedular a la ganancia al vender, medida en dólares, y 20% a los "
    "intereses de la reserva —el proyecto no modela ese ISR; 20% es conservador en contra del "
    "modelo—. Comisión de 0.25% por compra y por venta, a todas las variantes por igual.",
    "La reserva rinde el T-bill a 3 meses de FRED (DTB3), versionado en data/estudios/macro.",
    "La escisión (Orion en O, NLOP en WPC) entra como efectivo al valor que le da el proveedor, "
    "sin impuesto; sin reglas se reinvierte en el papel, como en el retorno total del estudio.",
)


# --------------------------------------------------------------------------------------
# Datos: T-bill a 3 meses y calificaciones
# --------------------------------------------------------------------------------------


def descargar_tbill() -> pd.DataFrame:
    """El T-bill a 3 meses de FRED (DTB3), en porcentaje anual. Toca la red."""
    return macro.descargar("tbill_3m")


def guardar_tbill(df: pd.DataFrame, raiz: Path | None = None) -> Path:
    return macro.guardar("tbill_3m", df, raiz)


def cargar_tbill(raiz: Path | None = None) -> pd.Series:
    """Tasa anual en fracción, por día hábil."""
    return (macro.cargar("tbill_3m", raiz) / 100).rename("tbill")


def cargar_calificaciones(ticker: str, raiz: Path | None = None) -> pd.DataFrame:
    ruta = (raiz or DIR_ESTUDIOS) / ARCHIVO_CALIFICACIONES
    if not ruta.exists():
        return pd.DataFrame(columns=["ticker", "fecha", "agencia", "grado_inversion", "fecha_publicacion"])
    d = pd.read_csv(ruta, parse_dates=["fecha", "fecha_publicacion"])
    return d[d["ticker"] == ticker].sort_values("fecha").reset_index(drop=True)


def grado_de_inversion(calificaciones: pd.DataFrame, fechas: pd.DatetimeIndex) -> pd.DataFrame:
    """Por fecha: si tiene grado de inversión (``vigente``) y si lo PERDIÓ (``perdido``).

    Se conoce desde la fecha del documento que lo dice, no desde la fecha que el
    documento reporta: un prospecto de 1997 que cuenta la calificación de 1995 no dice
    nada de lo que se sabía en 1995 por este medio.

    ``vigente``: alguna agencia lo califica con grado de inversión (True), ninguna
    (False) o todavía no hay documento (NaN). ``perdido``: lo tuvo y dejó de tenerlo.
    """
    salida = pd.DataFrame(index=fechas, columns=["vigente", "perdido"], dtype=object)
    if calificaciones.empty:
        return salida
    c = calificaciones.copy()
    c["conocido"] = c[["fecha", "fecha_publicacion"]].max(axis=1)
    for f in fechas:
        vistos = c[c["conocido"] <= f]
        if vistos.empty:
            continue
        ultima = vistos.sort_values(["fecha", "conocido"]).groupby("agencia").tail(1)
        vigente = bool((ultima["grado_inversion"] == "si").any())
        lo_tuvo = bool((vistos["grado_inversion"] == "si").any())
        salida.loc[f, "vigente"] = vigente
        salida.loc[f, "perdido"] = lo_tuvo and not vigente
    return salida


# --------------------------------------------------------------------------------------
# Señales: el semáforo cada fin de mes, con lo que se sabía ese día
# --------------------------------------------------------------------------------------


@dataclass
class Senales:
    ticker: str
    mensual: pd.DataFrame        # un renglón por fin de mes
    trimestral: pd.DataFrame     # el panel que lee la Puerta 3


def fines_de_mes(sesiones: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(sesiones, index=sesiones)
    return pd.DatetimeIndex(s.groupby(sesiones.to_period("M")).last().values)


def crecimiento_por_periodo(e, concepto: str, fechas: pd.DatetimeIndex) -> pd.Series:
    """Crecimiento de la última cifra conocida contra la del MISMO periodo un año antes.

    Comparar «lo que se sabía hoy» contra «lo que se sabía hace 365 días» falla en
    cuanto la fecha de publicación se mueve unos días: NNN publicó el FFO de 2000 el
    30-mar-2001 y el de 2001 el 27-mar-2002, así que el 28-mar-2002 «hace un año» todavía
    era el FFO de 1999, y la resta comparaba 2001 contra 1999 (−7.1% en vez de −2.7%).
    Aquí se compara periodo contra periodo: el año contra el año anterior, el TTM de un
    trimestre contra el TTM del mismo trimestre un año antes, con lo conocido a la fecha.
    """
    flujo = e.flujos.get(concepto)
    salida = pd.Series(np.nan, index=fechas, dtype=float)
    if flujo is None or flujo.empty:
        return salida
    tabla = flujo.attrs.get("versiones")
    if tabla is None or tabla.empty:
        return salida
    tabla = tabla.sort_index(kind="stable")
    for f in fechas:
        conocido = tabla[tabla.index <= f]
        if conocido.empty:
            continue
        actual = conocido.iloc[-1]
        objetivo = actual["periodo"] - pd.DateOffset(years=1)
        previo = conocido[(conocido["periodo"] - objetivo).abs() <= pd.Timedelta(days=7)]
        if not previo.empty and previo["valor"].iloc[-1] > 0:
            salida.loc[f] = actual["valor"] / previo["valor"].iloc[-1] - 1
    return salida


def _anual_vigente(
    valores: pd.Series, conocido: pd.Series, fechas: pd.DatetimeIndex, *, vigencia_meses: int
) -> pd.Series:
    """El último valor anual ya publicado a cada fecha, si su año no es demasiado viejo.

    ``valores`` y ``conocido`` van indexados por año.
    """
    salida = pd.Series(np.nan, index=fechas, dtype=float)
    v = valores.dropna()
    if v.empty:
        return salida
    tabla = pd.DataFrame({"valor": v.astype(float),
                          "conocido": pd.to_datetime(conocido.reindex(v.index))}).dropna()
    tabla["cierre"] = [pd.Timestamp(int(a), 12, 31) for a in tabla.index]
    for f in fechas:
        ok = tabla[(tabla["conocido"] <= f) & (tabla["cierre"] >= f - pd.DateOffset(months=vigencia_meses))]
        if not ok.empty:
            salida.loc[f] = ok.sort_index()["valor"].iloc[-1]
    return salida


def _primaria(primarios: pd.DataFrame, concepto: str) -> tuple[pd.Series, pd.Series]:
    p = primarios[primarios["concepto"] == concepto].sort_values("fecha_publicacion")
    p = p.groupby("anio").first()
    return p["valor_actual"].astype(float), pd.to_datetime(p["fecha_publicacion"])


def senales(e, *, calificaciones: pd.DataFrame | None = None,
            parametros: Parametros = PARAMETROS) -> Senales:
    """El semáforo evaluado cada fin de mes con la información de ese día."""
    t = e.tabla
    fechas = fines_de_mes(t.index)
    m = pd.DataFrame(index=fechas)
    m.index.name = "fecha"
    precio = t["precio_base"].reindex(fechas)
    m["precio"] = precio

    # Prima de la Puerta 2: siempre la medida de valuación del emisor.
    flujo_medida = t["affo_ttm" if e.medida.concepto == "affo_por_accion" else "ffo_ttm"].reindex(fechas)
    m["prima"] = flujo_medida / precio - t["ust10"].reindex(fechas)
    m["percentil"] = percentil_expandible(m["prima"].dropna(),
                                          min_observaciones=parametros.min_meses_percentil).reindex(fechas)
    m["n_meses_prima"] = m["prima"].notna().cumsum()

    # Criterios de las Puertas 1 y 3: el AFFO donde ya existía, el FFO antes.
    affo, ffo = t["affo_ttm"], t["ffo_ttm"]
    affo_m, ffo_m = affo.reindex(fechas), ffo.reindex(fechas)
    m["medida_calidad"] = np.where(affo_m.notna(), "AFFO", np.where(ffo_m.notna(), "FFO", None))
    flujo = affo_m.where(affo_m.notna(), ffo_m)
    # El payout divide el dividendo del MISMO periodo que cubre el flujo, no el de hoy.
    div_affo = _dividendo_del_periodo(e, "affo_por_accion", fechas)
    div_ffo = _dividendo_del_periodo(e, "ffo_por_accion", fechas)
    m["payout"] = div_affo.where(affo_m.notna(), div_ffo) / flujo
    crec_affo = crecimiento_por_periodo(e, "affo_por_accion", fechas)
    crec_ffo = crecimiento_por_periodo(e, "ffo_por_accion", fechas)
    # El AFFO donde ya existe con su año anterior; si no, el FFO.
    m["crecimiento"] = crec_affo.where(crec_affo.notna(), crec_ffo)

    # Anuales: deuda neta ÷ EBITDA, costo de la deuda, cap rate de compra.
    fin_mas_rezago = pd.Series({a: pd.Timestamp(int(a), 12, 31) + pd.Timedelta(days=parametros.rezago_anual_dias)
                                for a in e.anual.index})
    rep_v, rep_f = _primaria(e.primarios, "deuda_neta_ebitdare_proforma")
    der = e.anual["deuda_neta_ebitdare"].dropna() if "deuda_neta_ebitdare" in e.anual else pd.Series(dtype=float)
    apal = pd.concat([rep_v, der[~der.index.isin(rep_v.index)]]).sort_index()
    apal_f = pd.concat([rep_f, fin_mas_rezago.reindex(der.index[~der.index.isin(rep_v.index)])]).sort_index()
    m["deuda_neta_ebitda"] = _anual_vigente(apal, apal_f, fechas, vigencia_meses=parametros.vigencia_anual_meses)
    m["deuda_neta_ebitda_origen"] = np.where(
        m["deuda_neta_ebitda"].isna(), None, "reportada o derivada de XBRL")
    kd = e.anual["costo_deuda"] if "costo_deuda" in e.anual else pd.Series(dtype=float)
    m["costo_deuda"] = _anual_vigente(kd, fin_mas_rezago, fechas, vigencia_meses=parametros.vigencia_anual_meses)
    cap_v, cap_f = _primaria(e.primarios, "cap_rate_adquisicion")
    m["cap_rate"] = _anual_vigente(cap_v, cap_f, fechas, vigencia_meses=parametros.vigencia_anual_meses)
    ke = flujo / precio
    w = parametros.peso_deuda_cmc
    m["spread_inversion"] = m["cap_rate"] - (w * m["costo_deuda"] + (1 - w) * ke)

    gi = grado_de_inversion(calificaciones if calificaciones is not None else
                            cargar_calificaciones(e.ticker), fechas)
    m["grado_inversion"] = gi["vigente"]
    m["perdio_grado"] = gi["perdido"]

    # El periodo que cubre la cifra de flujo con que se evalúa cada fecha.
    per_affo = _periodo_en(e, "affo_por_accion", fechas)
    per_ffo = _periodo_en(e, "ffo_por_accion", fechas)
    m["periodo_flujo"] = per_affo.where(affo_m.notna(), per_ffo)

    # El panel de la Puerta 3, con los nombres que lee ``modelo.kill``. Un renglón por
    # REPORTE nuevo, no por trimestre de calendario: «dos trimestres seguidos» quiere
    # decir dos observaciones, y antes de 2019 la cifra es anual. Contado por
    # calendario, un solo año malo aparecía en dos cierres de trimestre y vendía.
    trimestral = pd.DataFrame({
        "fecha_dato": m.index,
        "payout_affo": m["payout"],
        "spread_inversion": m["spread_inversion"],
        "crecimiento_affo_por_accion_yoy": m["crecimiento"],
        "deuda_neta_ebitdare": m["deuda_neta_ebitda"],
        # La Puerta 3 vende por PERDER el grado de inversión, no por no haberlo tenido.
        "grado_inversion": m["perdio_grado"].map({True: False, False: True}),
    }, index=m.index)
    trimestral = trimestral[trimestral.index.month.isin([3, 6, 9, 12])]
    if parametros.persistencia_por_reporte:
        periodos = m["periodo_flujo"].reindex(trimestral.index)
        nuevo_reporte = periodos.notna() & (periodos != periodos.shift(1))
        trimestral = trimestral[nuevo_reporte]

    filas = []
    for f in fechas:
        r = m.loc[f]
        metricas = {
            "payout_affo": _num(r["payout"]),
            "deuda_neta_ebitdare": _num(r["deuda_neta_ebitda"]),
            "crecimiento_affo_por_accion_yoy": _num(r["crecimiento"]),
            "spread_inversion": _num(r["spread_inversion"]),
            "grado_inversion": None if pd.isna(r["grado_inversion"]) else bool(r["grado_inversion"]),
        }
        historial = trimestral[trimestral.index <= f]
        # Una columna sin dato en el último trimestre no se evalúa: ``kill`` leería
        # el hueco como «no dispara» y lo contaría como criterio medido.
        historial = historial[[c for c in historial.columns
                               if c == "fecha_dato" or (not historial.empty and pd.notna(historial[c].iloc[-1]))]]
        sem = evaluar_semaforo(e.ticker, f, metricas, _num(r["percentil"]),
                               int(r["n_meses_prima"]) // 3, historial)
        disparadores = (sem.deterioro.criterios.loc[sem.deterioro.criterios["dispara"] == True, "criterio"]  # noqa: E712
                        .tolist() if not sem.deterioro.criterios.empty else [])
        # Los criterios se llaman «AFFO» en la pantalla; antes de que el emisor
        # publicara AFFO, lo que se midió fue el FFO, y así se nombra.
        medida = r["medida_calidad"] if r["medida_calidad"] in ("AFFO", "FFO") else "AFFO"
        filas.append({
            "accion": sem.accion.value,
            "decision": DE_SEMAFORO[sem.accion].value,
            "luz_calidad": sem.calidad.luz.value,
            "luz_valuacion": sem.valuacion.luz.value,
            "luz_deterioro": sem.deterioro.luz.value,
            "reprobados": "; ".join(sem.calidad.fallidos).replace("AFFO", medida),
            "disparadores": "; ".join(disparadores).replace("AFFO", medida),
        })
    m = m.join(pd.DataFrame(filas, index=fechas))
    return Senales(e.ticker, m, trimestral)


def _periodo_en(e, concepto: str, fechas: pd.DatetimeIndex) -> pd.Series:
    flujo = e.flujos.get(concepto)
    periodo = None if flujo is None else flujo.attrs.get("periodo")
    if periodo is None or periodo.empty:
        return pd.Series(pd.NaT, index=fechas)
    per = periodo.sort_index()
    per = per[~per.index.duplicated(keep="last")]
    return per.reindex(per.index.union(fechas)).ffill().reindex(fechas)


def _dividendo_del_periodo(e, concepto: str, fechas: pd.DatetimeIndex) -> pd.Series:
    """El dividendo de los doce meses que cubre la última cifra de flujo conocida a cada fecha.

    Sin el periodo —un ``Estudio`` armado sin ``flujos``— cae al dividendo TTM de hoy,
    que es lo que hace la pantalla con datos trimestrales.
    """
    flujo = e.flujos.get(concepto)
    periodo = None if flujo is None else flujo.attrs.get("periodo")
    if periodo is None or periodo.empty:
        return e.tabla["dividendo_ttm"].reindex(fechas)
    per = periodo.sort_index()
    per = per[~per.index.duplicated(keep="last")]
    en_fecha = per.reindex(per.index.union(fechas)).ffill().reindex(fechas)
    unicos = pd.DatetimeIndex(en_fecha.dropna().unique()).sort_values()
    div = dividendo_ttm(e.historia_mercado.dividendos, unicos)
    div.index = unicos
    return pd.Series([div.get(p, np.nan) if pd.notna(p) else np.nan for p in en_fecha], index=fechas)


def _num(x) -> float | None:
    return None if x is None or pd.isna(x) else float(x)


# --------------------------------------------------------------------------------------
# Simulación
# --------------------------------------------------------------------------------------


@dataclass
class Simulacion:
    variante: Variante
    diaria: pd.DataFrame          # acciones, valor_posicion, reserva, riqueza
    ejecuciones: pd.DataFrame     # un renglón por mes: decisión, dinero nuevo, comprado, a la reserva
    ventas: pd.DataFrame
    flujos_usd: pd.Series
    flujos_mxn: pd.Series
    aportado: float
    valor_final: float            # antes de liquidar
    valor_final_neto: float       # vendiendo todo al final y pagando el impuesto
    impuestos: dict[str, float]
    comisiones: float

    @property
    def tir_usd(self) -> float | None:
        return tir(self.flujos_usd)

    @property
    def tir_mxn(self) -> float | None:
        return tir(self.flujos_mxn)


def _decision_de_variante(d: Decision, variante: Variante) -> Decision:
    if variante is Variante.BENCHMARK:
        return Decision.SIN_SENAL
    if variante in (Variante.SOLO_VALUACION, Variante.SOLO_VALUACION_12M):
        return Decision.NO_COMPRAR if d is Decision.VENDER else d
    if variante is Variante.SOLO_TESIS:
        return Decision.VENDER if d is Decision.VENDER else Decision.SIN_SENAL
    return d


def simular(
    e,
    sen: Senales,
    tbill: pd.Series,
    *,
    variante: Variante = Variante.MODELO,
    parametros: Parametros = PARAMETROS,
) -> Simulacion:
    """Aportación mensual con las reglas, día por día.

    La decisión de un fin de mes se ejecuta al cierre de la SIGUIENTE sesión (lag de
    un día, ``simulacion.backtest.aplicar_lag``): la señal se calcula con el cierre y
    nadie puede operar a ese mismo cierre.
    """
    hm = e.historia_mercado
    t = e.tabla
    sesiones = t.index
    precio = t["precio_base"].astype(float)
    fx = t["usdmxn"].ffill().bfill()

    div = hm.dividendos.copy()
    pos = sesiones.searchsorted(pd.DatetimeIndex(div["fecha_ex"]), side="left")
    div["sesion"] = sesiones[np.clip(pos, 0, len(sesiones) - 1)]
    div_por_sesion = div.groupby("sesion")["monto_base"].sum()
    escision = {}
    for ev in hm.escisiones:
        s = sesiones[min(sesiones.searchsorted(pd.Timestamp(ev.fecha), side="left"), len(sesiones) - 1)]
        escision[s] = escision.get(s, 1.0) * ev.factor

    tasa = tbill.reindex(sesiones.union(tbill.index)).ffill().reindex(sesiones).fillna(0.0)

    # Decisión de cada fin de mes → sesión en que se ejecuta.
    ejec = {}
    for f, d in sen.mensual["decision"].items():
        i = sesiones.searchsorted(f, side="right")
        if i < len(sesiones):
            ejec[sesiones[i]] = (f, Decision(d))

    p = parametros
    con_plazo = variante in (Variante.MODELO_12M, Variante.SOLO_VALUACION_12M)
    plazo = pd.DateOffset(months=p.reinversion_meses)
    espera: list[list] = []          # [fecha en que entró a la reserva, monto]
    calendario = {"restante": 0.0, "meses": 0}   # lo vendido, en partes iguales
    en_tesis_rota = False
    interes_del_mes = 0.0
    acciones = costo = reserva = nuevo = 0.0
    imp = {"dividendos": 0.0, "intereses": 0.0, "ventas": 0.0, "liquidacion": 0.0}
    comisiones = 0.0
    flujos: dict[pd.Timestamp, float] = {}
    diario, filas, ventas = [], [], []
    anterior = None
    for s in sesiones:
        px = float(precio.loc[s])
        if anterior is not None and reserva > 0:
            dias = (s - anterior).days
            interes = reserva * float(tasa.loc[anterior]) * dias / 365
            imp["intereses"] += interes * p.impuesto_intereses
            reserva += interes * (1 - p.impuesto_intereses)
            interes_del_mes += interes * (1 - p.impuesto_intereses)
        if acciones > 0 and s in div_por_sesion.index:
            bruto = acciones * float(div_por_sesion.loc[s])
            imp["dividendos"] += bruto * p.impuesto_dividendo
            reserva += bruto * (1 - p.impuesto_dividendo)
            nuevo += bruto * (1 - p.impuesto_dividendo)
        if acciones > 0 and s in escision:
            # El valor de lo escindido: el accionista recibe acciones de otra empresa.
            valor = acciones * px * (escision[s] - 1)
            reserva += valor
            nuevo += valor
        if s in ejec:
            fecha_senal, d0 = ejec[s]
            d = _decision_de_variante(d0, variante)
            reserva += p.aportacion
            nuevo += p.aportacion
            flujos[s] = flujos.get(s, 0.0) - p.aportacion
            venta = 0.0
            if d is Decision.VENDER and acciones > 0:
                bruto = acciones * px
                com = bruto * p.comision
                ganancia = bruto - com - costo
                impuesto = max(ganancia, 0.0) * p.impuesto_ganancia
                ventas.append({"fecha": s, "fecha_senal": fecha_senal, "precio": px, "acciones": acciones,
                               "valor": bruto, "ganancia": ganancia, "impuesto": impuesto,
                               "disparadores": sen.mensual.loc[fecha_senal, "disparadores"]})
                imp["ventas"] += impuesto
                comisiones += com
                reserva += bruto - com - impuesto
                venta = bruto
                acciones = costo = 0.0
            # Sin reglas de valuación —el benchmark y «solo tesis rota»— todo el efectivo
            # vuelve al papel en cuanto no hay VENTA: es lo que separa el efecto de vender.
            sin_valuacion = variante in (Variante.BENCHMARK, Variante.SOLO_TESIS)
            if (sin_valuacion and d is not Decision.VENDER) or d is Decision.COMPRAR:
                monto = reserva
            elif d is Decision.SIN_SENAL:
                monto = nuevo
            elif d is Decision.COMPRAR_MENOS:
                monto = nuevo * p.fraccion_comprar_menos
            else:
                monto = 0.0
            if con_plazo:
                if d is Decision.VENDER:
                    # Con la tesis rota no se compra nada; al restablecerse, todo lo que
                    # haya en la reserva entra al calendario de 12 partes.
                    en_tesis_rota = True
                    espera, calendario = [], {"restante": 0.0, "meses": 0}
                elif d is Decision.COMPRAR:
                    espera, calendario = [], {"restante": 0.0, "meses": 0}
                else:
                    if en_tesis_rota:
                        en_tesis_rota = False
                        calendario = {"restante": reserva - nuevo, "meses": p.reinversion_meses}
                        espera = []
                    if interes_del_mes > 0:
                        espera.append([s, interes_del_mes])
                    if nuevo > monto:
                        espera.append([s, nuevo - monto])
                    vencido = sum(x[1] for x in espera if x[0] <= s - plazo)
                    espera = [x for x in espera if x[0] > s - plazo]
                    cuota = 0.0
                    if calendario["meses"] > 0:
                        cuota = calendario["restante"] / calendario["meses"]
                        calendario = {"restante": calendario["restante"] - cuota,
                                      "meses": calendario["meses"] - 1}
                    monto += vencido + cuota
            interes_del_mes = 0.0
            monto = min(monto, reserva)
            if monto > 0:
                com = monto * p.comision
                comisiones += com
                acciones += (monto - com) / px
                costo += monto
                reserva -= monto
            filas.append({"fecha": s, "fecha_senal": fecha_senal, "decision_semaforo": d0.value,
                          "decision": d.value, "dinero_nuevo": nuevo, "comprado": monto,
                          "vendido": venta, "reserva": reserva, "intensidad": monto / nuevo if nuevo else np.nan})
            nuevo = 0.0
        diario.append((s, acciones, acciones * px, reserva))
        anterior = s

    d = pd.DataFrame(diario, columns=["fecha", "acciones", "valor_posicion", "reserva"]).set_index("fecha")
    d["riqueza"] = d["valor_posicion"] + d["reserva"]
    fin = sesiones[-1]
    bruto = acciones * float(precio.loc[fin])
    com = bruto * p.comision
    imp["liquidacion"] = max(bruto - com - costo, 0.0) * p.impuesto_ganancia
    valor_neto = bruto - com - imp["liquidacion"] + reserva
    f_usd = pd.Series(flujos, dtype=float)
    f_usd.loc[fin] = f_usd.get(fin, 0.0) + valor_neto
    f_usd = f_usd.sort_index()
    f_mxn = f_usd * fx.reindex(f_usd.index)
    return Simulacion(
        variante=variante,
        diaria=d,
        ejecuciones=pd.DataFrame(filas).set_index("fecha") if filas else pd.DataFrame(),
        ventas=pd.DataFrame(ventas),
        flujos_usd=f_usd,
        flujos_mxn=f_mxn,
        aportado=p.aportacion * len(filas),
        valor_final=float(d["riqueza"].iloc[-1]),
        valor_final_neto=float(valor_neto),
        impuestos=imp,
        comisiones=comisiones,
    )


# --------------------------------------------------------------------------------------
# Métricas y dictamen
# --------------------------------------------------------------------------------------


def _mensual(sim: Simulacion) -> pd.DataFrame:
    """Riqueza a cada ejecución y el dinero que entró ese mes."""
    ej = sim.ejecuciones
    riqueza = sim.diaria["riqueza"].reindex(ej.index)
    return pd.DataFrame({"riqueza": riqueza, "aportacion": -sim.flujos_usd.reindex(ej.index).clip(upper=0)})


def rendimiento_ponderado_en_tiempo(sim: Simulacion) -> pd.Series:
    """Retorno de cada mes quitando la aportación: para volatilidad y caída máxima.

    La riqueza de cada ejecución ya incluye la aportación de ese día, así que el mes
    rindió ``(W_t − C_t) / W_{t−1} − 1``.
    """
    m = _mensual(sim)
    previa = m["riqueza"].shift(1)
    return ((m["riqueza"] - m["aportacion"]) / previa.where(previa > 0) - 1).dropna()


def caida_maxima(r: pd.Series) -> float:
    indice = (1 + r.fillna(0)).cumprod()
    return float((indice / indice.cummax() - 1).min()) if not indice.empty else float("nan")


def retorno_activo(sim: Simulacion, bench: Simulacion) -> pd.Series:
    """(P&L del modelo − P&L del benchmark) ÷ capital del benchmark, por mes (P8)."""
    me, mb = _mensual(sim), _mensual(bench)
    pnl_e = me["riqueza"] - me["riqueza"].shift(1) - me["aportacion"]
    pnl_b = mb["riqueza"] - mb["riqueza"].shift(1) - mb["aportacion"]
    base = mb["riqueza"].shift(1) + mb["aportacion"]
    return ((pnl_e - pnl_b) / base.where(base > 0)).dropna()


def retorno_del_papel(e, fechas: pd.DatetimeIndex) -> pd.Series:
    rt = e.tabla["rt_usd_neto"].reindex(fechas)
    return (rt / rt.shift(1) - 1).dropna()


def metricas(sim: Simulacion) -> dict:
    r = rendimiento_ponderado_en_tiempo(sim)
    ej = sim.ejecuciones
    exposicion = (sim.diaria["valor_posicion"] / sim.diaria["riqueza"].where(sim.diaria["riqueza"] > 0)).mean()
    return {
        "variante": sim.variante.value,
        "tir_usd": sim.tir_usd,
        "tir_mxn": sim.tir_mxn,
        "aportado": sim.aportado,
        "valor_final_neto": sim.valor_final_neto,
        "multiplo": sim.valor_final_neto / sim.aportado if sim.aportado else np.nan,
        "volatilidad": float(r.std() * np.sqrt(12)) if len(r) > 2 else np.nan,
        "caida_maxima": caida_maxima(r),
        "exposicion_promedio": float(exposicion),
        "reserva_final": float(sim.diaria["reserva"].iloc[-1]),
        "ventas": int(len(sim.ventas)),
        "impuestos": float(sum(sim.impuestos.values())),
        "comisiones": sim.comisiones,
        "meses_comprando": int((ej["comprado"] > 0).sum()) if not ej.empty else 0,
    }


@dataclass
class ResultadoReglas:
    ticker: str
    medida: str
    desde: pd.Timestamp
    hasta: pd.Timestamp
    senales: Senales
    variantes: dict[Variante, Simulacion]
    tabla: pd.DataFrame
    apuestas: ConteoApuestas
    neutralizacion: ResultadoNeutralizacion | None
    dictamen: DictamenBacktest
    ventas: pd.DataFrame
    por_decision: pd.DataFrame
    tiempo_en_decision: pd.DataFrame
    criterios: pd.DataFrame
    sensibilidad: pd.DataFrame
    decision_hoy: pd.Series
    ventas_por_calendario: int = 0   # las que habría con la persistencia contada por trimestre
    # Cada vez que la Puerta 3 empezó a disparar, y qué hizo el papel antes y después.
    eventos: pd.DataFrame = field(default_factory=pd.DataFrame)
    precio: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))   # por acción de hoy
    nombre: str = ""
    parametros: Parametros = field(default_factory=Parametros)
    avisos: list[str] = field(default_factory=list)

    @property
    def modelo(self) -> Simulacion:
        return self.variantes[Variante.MODELO]

    @property
    def benchmark(self) -> Simulacion:
        return self.variantes[Variante.BENCHMARK]


def _ventas_con_desenlace(e, sim: Simulacion, tbill: pd.Series, parametros: Parametros) -> pd.DataFrame:
    """Cada venta y qué pasó después: ¿se evitó una caída o se perdió un rebote?"""
    if sim.ventas.empty:
        return pd.DataFrame()
    rt = e.tabla["rt_usd_neto"]
    ej = sim.ejecuciones
    filas = []
    for _, v in sim.ventas.iterrows():
        f = pd.Timestamp(v["fecha"])
        fila = {"fecha": f, "precio": v["precio"], "disparadores": v["disparadores"],
                "impuesto_pct": v["impuesto"] / v["valor"] if v["valor"] else np.nan}
        for anios in (1, 3):
            g = f + pd.DateOffset(years=anios)
            if g <= rt.index[-1]:
                fila[f"papel_{anios}a"] = float(rt.asof(g) / rt.loc[f] - 1)
        despues = ej[(ej.index > f) & (ej["comprado"] > 0)]
        if not despues.empty:
            fila["recompra"] = despues.index[0]
        # Lo que importa no es la primera compra —puede ser media aportación— sino cuándo
        # lo vendido vuelve al papel: la primera compra que se lleva la reserva completa.
        vuelve = despues[despues["reserva"] <= 0.05 * despues["comprado"].clip(lower=1)]
        vuelve = vuelve[vuelve["comprado"] > vuelve["dinero_nuevo"] + 1]
        if not vuelve.empty:
            r0 = vuelve.index[0]
            fila["reinversion"] = r0
            fila["precio_reinversion"] = float(e.tabla["precio_base"].loc[r0])
            fila["meses_fuera"] = (r0 - f).days / 30.44
            fila["papel_mientras_fuera"] = float(rt.loc[r0] / rt.loc[f] - 1)
        filas.append(fila)
    return pd.DataFrame(filas)


def eventos_de_tesis_rota(e, sen: Senales, conteo: str) -> pd.DataFrame:
    """Cada vez que la Puerta 3 empieza a disparar: qué había hecho el papel y qué hizo después.

    Es la prueba directa de si «vender por tesis rota» llega a tiempo. Si en la mayoría
    de los casos el papel ya había caído y en el año siguiente sube, la señal no anticipa
    el deterioro: lo confirma cuando el mercado ya lo descontó.
    """
    rt, px = e.tabla["rt_usd_neto"], e.tabla["precio_base"]
    m = sen.mensual
    v = m["decision"] == Decision.VENDER.value
    filas = []
    for f in m.index[v & ~v.shift(1, fill_value=False)]:
        fila = {"emisor": e.ticker, "conteo": conteo, "fecha": f, "disparadores": m.loc[f, "disparadores"],
                "papel_12m_antes": float(rt.asof(f) / rt.asof(f - pd.DateOffset(years=1)) - 1),
                "caida_desde_maximo_24m": float(px.asof(f) / px.loc[f - pd.DateOffset(years=2):f].max() - 1)}
        for anios in (1, 3):
            g = f + pd.DateOffset(years=anios)
            fila[f"papel_{anios}a_despues"] = float(rt.asof(g) / rt.asof(f) - 1) if g <= rt.index[-1] else np.nan
        filas.append(fila)
    cifras = ["papel_12m_antes", "caida_desde_maximo_24m", "papel_1a_despues", "papel_3a_despues"]
    # Sin eventos el marco sale vacío y de tipo «object»; al concatenarlo con uno que sí
    # tiene, las cifras quedaban como texto y la pantalla las dibujaba sin escalar.
    return pd.DataFrame(filas, columns=["emisor", "conteo", "fecha", "disparadores", *cifras]).astype(
        dict.fromkeys(cifras, float))


def _por_decision(e, sen: Senales) -> pd.DataFrame:
    """Qué rindió el papel en los 12 meses siguientes a cada decisión.

    Ventanas que se enciman: cada fin de mes comparte 11 de sus 12 meses con el
    siguiente, así que las observaciones independientes son ~meses ÷ 12.
    """
    rt = e.tabla["rt_usd_neto"]
    m = sen.mensual
    fechas = m.index
    adelante = fechas + pd.DateOffset(years=1)
    ok = adelante <= rt.index[-1]
    r12 = pd.Series(np.nan, index=fechas)
    r12[ok] = [float(rt.asof(g) / rt.asof(f) - 1) for f, g in zip(fechas[ok], adelante[ok], strict=True)]
    df = pd.DataFrame({"decision": m["decision"], "r12": r12})
    g = df.groupby("decision")
    salida = pd.DataFrame({
        "meses": g.size(),
        "con_12m": g["r12"].count(),
        "mediana_12m": g["r12"].median(),
        "peor_12m": g["r12"].min(),
        "mejor_12m": g["r12"].max(),
    })
    salida["independientes"] = (salida["con_12m"] / 12).round(1)
    orden = [d.value for d in Decision]
    return salida.reindex([o for o in orden if o in salida.index])


def _criterios(sen: Senales) -> pd.DataFrame:
    """Cuántos meses reprobó cada criterio de calidad y cuántos disparó cada uno de deterioro."""
    m = sen.mensual
    filas = []
    for columna, tipo in (("reprobados", "Puerta 1: reprobó"), ("disparadores", "Puerta 3: disparó")):
        conteo: dict[str, int] = {}
        for texto in m[columna].fillna(""):
            for c in filter(None, (x.strip() for x in texto.split(";"))):
                conteo[c] = conteo.get(c, 0) + 1
        filas += [{"puerta": tipo, "criterio": c, "meses": n, "fraccion": n / len(m)} for c, n in conteo.items()]
    return pd.DataFrame(filas).sort_values(["puerta", "meses"], ascending=[True, False]) if filas else pd.DataFrame(
        columns=["puerta", "criterio", "meses", "fraccion"])


def backtest(
    e,
    *,
    tbill: pd.Series | None = None,
    calificaciones: pd.DataFrame | None = None,
    parametros: Parametros = PARAMETROS,
) -> ResultadoReglas:
    tbill = cargar_tbill() if tbill is None else tbill
    avisos = []
    if tbill.empty:
        avisos.append("Sin serie de T-bill versionada: la reserva no rinde nada. Corre "
                      "`python scripts/estudio.py tbill`.")
    cal = cargar_calificaciones(e.ticker) if calificaciones is None else calificaciones
    if cal.empty:
        avisos.append(f"Sin historia de calificaciones de {e.ticker}: el grado de inversión no se evalúa.")
    sen = senales(e, calificaciones=cal, parametros=parametros)
    variantes = {v: simular(e, sen, tbill, variante=v, parametros=parametros) for v in Variante}
    tabla = pd.DataFrame([metricas(s) for s in variantes.values()]).set_index("variante")
    tabla["ventaja_tir_usd"] = tabla["tir_usd"] - tabla.loc[Variante.BENCHMARK.value, "tir_usd"]

    mod, bench = variantes[Variante.MODELO], variantes[Variante.BENCHMARK]
    activo = retorno_activo(mod, bench)
    papel = retorno_del_papel(e, mod.ejecuciones.index)
    neu = neutralizar_beta(activo, papel.reindex(activo.index))
    apuestas = contar_apuestas(mod.ejecuciones["intensidad"].fillna(1.0), 1.0)
    rb = ResultadoBacktest(
        tipo=TipoRegla.APORTACION,
        riqueza_estrategia=mod.diaria["riqueza"],
        riqueza_benchmark=bench.diaria["riqueza"],
        retorno_activo=activo,
        flujos_estrategia=mod.flujos_usd,
        flujos_benchmark=bench.flujos_usd,
        tir_estrategia=mod.tir_usd,
        tir_benchmark=bench.tir_usd,
        apuestas=apuestas,
        neutralizacion=neu,
        descripcion_benchmark="Aportación fija al MISMO papel, reinvirtiendo dividendos (P6).",
    )

    sensibilidad = []
    for fr in (0.0, 0.5, 1.0):
        pr = replace(parametros, fraccion_comprar_menos=fr)
        s = variantes[Variante.MODELO] if fr == parametros.fraccion_comprar_menos else \
            simular(e, sen, tbill, variante=Variante.MODELO, parametros=pr)
        sensibilidad.append({"fraccion_comprar_menos": fr, "tir_usd": s.tir_usd,
                             "ventaja_tir_usd": (s.tir_usd or np.nan) - (bench.tir_usd or np.nan),
                             "multiplo": s.valor_final_neto / s.aportado})
    sen_calendario = senales(e, calificaciones=cal, parametros=replace(parametros, persistencia_por_reporte=False))
    por_calendario = simular(e, sen_calendario, tbill, variante=Variante.SOLO_TESIS, parametros=parametros)
    eventos = pd.concat([eventos_de_tesis_rota(e, sen, "por reporte"),
                         eventos_de_tesis_rota(e, sen_calendario, "por calendario")], ignore_index=True)
    m = sen.mensual
    tiempo = m["decision"].value_counts().rename("meses").to_frame()
    tiempo["fraccion"] = tiempo["meses"] / len(m)
    tiempo = tiempo.reindex([d.value for d in Decision if d.value in tiempo.index])
    return ResultadoReglas(
        ticker=e.ticker,
        medida=e.medida.etiqueta,
        desde=mod.ejecuciones.index[0],
        hasta=e.tabla.index[-1],
        senales=sen,
        variantes=variantes,
        tabla=tabla,
        apuestas=apuestas,
        neutralizacion=neu,
        dictamen=dictaminar(rb),
        ventas=_ventas_con_desenlace(e, mod, tbill, parametros),
        por_decision=_por_decision(e, sen),
        tiempo_en_decision=tiempo,
        criterios=_criterios(sen),
        sensibilidad=pd.DataFrame(sensibilidad),
        decision_hoy=m.iloc[-1],
        ventas_por_calendario=int(len(por_calendario.ventas)),
        eventos=eventos,
        precio=e.tabla["precio_base"],
        nombre=e.narrativa.nombre if getattr(e, "narrativa", None) else e.ticker,
        parametros=parametros,
        avisos=avisos,
    )


@dataclass
class Conclusion:
    titulo: str
    texto: str
    tono: str = "neutral"   # "favorable" | "desfavorable" | "neutral"


def _pb(x: float) -> str:
    return f"{x * 1e4:+,.0f} puntos base"


def conclusiones(r: ResultadoReglas) -> list[Conclusion]:
    """Lo que dice el backtest, en frases armadas con sus cifras."""
    t = r.tabla
    mod, ben = t.loc[Variante.MODELO.value], t.loc[Variante.BENCHMARK.value]
    val, tes = t.loc[Variante.SOLO_VALUACION.value], t.loc[Variante.SOLO_TESIS.value]
    c: list[Conclusion] = []
    ventaja = mod["ventaja_tir_usd"]
    c.append(Conclusion(
        "Qué hubiera pasado",
        f"Aportando {r.parametros.aportacion:,.0f} dólares cada mes desde {r.desde:%m-%Y}, el modelo "
        f"termina con una TIR de {mod['tir_usd']:.1%} en dólares ({mod['tir_mxn']:.1%} en pesos), "
        f"contra {ben['tir_usd']:.1%} de aportar lo mismo sin reglas: {_pb(ventaja)} al año. Lo "
        f"aportado se multiplicó {mod['multiplo']:.1f} veces, contra {ben['multiplo']:.1f}, ya con "
        "impuestos y comisiones y vendiendo todo al final.",
        "favorable" if ventaja > 0.001 else ("desfavorable" if ventaja < -0.001 else "neutral"),
    ))
    m12 = t.loc[Variante.MODELO_12M.value]
    v12 = t.loc[Variante.SOLO_VALUACION_12M.value]
    c.append(Conclusion(
        "Con la reinversión en 12 meses",
        f"Si nada espera más de 12 meses en la reserva, el modelo da {_pb(m12['ventaja_tir_usd'])} contra "
        f"aportar sin reglas, y sin vender nunca {_pb(v12['ventaja_tir_usd'])}.",
        "favorable" if max(m12["ventaja_tir_usd"], v12["ventaja_tir_usd"]) > 0.001 else "neutral",
    ))
    c.append(Conclusion(
        "De dónde sale la diferencia",
        f"Las reglas de compra solas —comprar más barato, menos caro, nunca vender— dan "
        f"{_pb(val['ventaja_tir_usd'])}; las ventas por tesis rota solas, con compra fija, "
        f"{_pb(tes['ventaja_tir_usd'])}. En promedio el modelo tuvo {mod['exposicion_promedio']:.0%} de "
        f"lo acumulado en el papel; el resto esperó en T-bills"
        + (f", y al final quedan {mod['reserva_final']:,.0f} dólares sin invertir." if mod["reserva_final"] > 1 else "."),
    ))
    v = r.ventas
    if v.empty:
        texto = (f"El modelo nunca vendió: en {(r.hasta - r.desde).days / 365.25:.0f} años la Puerta 3 no "
                 "encontró un deterioro que durara dos reportes seguidos.")
        tono = "neutral"
    else:
        subio = int((v.get("papel_1a", pd.Series(dtype=float)) > 0).sum())
        con_1a = int(v.get("papel_1a", pd.Series(dtype=float)).notna().sum())
        sin_regreso = int(v["reinversion"].isna().sum()) if "reinversion" in v else len(v)
        texto = (f"{len(v)} venta{'s' if len(v) > 1 else ''} por tesis rota"
                 + (f"; en {subio} de {con_1a} el papel subió en el año siguiente" if con_1a else "")
                 + ". " + " ".join(
                     f"{f['fecha']:%m-%Y} ({f['disparadores']})" + (
                         f": lo vendido esperó {f['meses_fuera']:.0f} meses en T-bills, mientras el papel "
                         f"rendía {f['papel_mientras_fuera']:+.0%}." if pd.notna(f.get("reinversion")) else
                         ": lo vendido no ha vuelto al papel.")
                     for _, f in v.iterrows())
                 + (" Lo vendido solo vuelve cuando el semáforo dice COMPRAR; mientras tanto el dinero "
                    "nuevo sigue la tabla." if sin_regreso or len(v) else ""))
        tono = "desfavorable" if tes["ventaja_tir_usd"] < 0 else "favorable"
    c.append(Conclusion("Las ventas por tesis rota", texto, tono))
    ev = r.eventos
    if not ev.empty:
        con = ev.dropna(subset=["papel_1a_despues"])
        subio = int((con["papel_1a_despues"] > 0).sum())
        c.append(Conclusion(
            "¿La tesis rota llega a tiempo?",
            f"La Puerta 3 empezó a disparar {len(ev)} veces contando por reporte y por calendario. "
            f"Para entonces el papel ya estaba {abs(ev['caida_desde_maximo_24m'].median()):.0%} abajo de su "
            f"máximo de dos años (mediana), y en el año siguiente subió en {subio} de {len(con)} casos "
            f"(mediana {con['papel_1a_despues'].median():+.0%}). La señal confirma con datos contables lo "
            "que el precio ya descontó: vende tarde.",
            "desfavorable" if len(con) and subio > len(con) / 2 else "neutral",
        ))
    neu = r.neutralizacion
    c.append(Conclusion(
        "Qué tanto se le puede creer",
        f"{r.dictamen.veredicto.value}. {r.apuestas.episodios} "
        f"{'cambio' if r.apuestas.episodios == 1 else 'cambios'} de postura en "
        f"{r.apuestas.observaciones} meses; el proyecto pide {r.apuestas.umbral} para afirmar una regla (P7)."
        + (f" Quitando el efecto de estar más o menos invertido en un papel que sube (P8), la ventaja "
           f"que queda no es distinguible de cero (p = {neu.p_valor_alfa:.2f})." if neu is not None
           and neu.p_valor_alfa > 0.01 else "")
        + " Sirve para ver cómo se hubiera comportado, no para probar que funciona.",
    ))
    h = r.decision_hoy
    motivo = h["disparadores"] or h["reprobados"]
    c.append(Conclusion(
        "Qué dice hoy",
        f"{h['decision']}: el semáforo dice {h['accion']}"
        + (f" con la prima en el percentil {h['percentil']:.0%} de su historia" if pd.notna(h["percentil"]) else "")
        + (f"; {'dispara' if h['disparadores'] else 'reprueba'}: {motivo}" if motivo else "") + ".",
    ))
    return c


def resumen_en_texto(r: ResultadoReglas) -> str:
    lineas = [f"{r.ticker}: {r.desde:%Y-%m} a {r.hasta:%Y-%m}, prima sobre {r.medida}"]
    t = r.tabla
    for v, fila in t.iterrows():
        lineas.append(
            f"  {v:32s} TIR USD {fila['tir_usd']:.2%}  MXN {fila['tir_mxn']:.2%}  múltiplo {fila['multiplo']:.2f}x  "
            f"exposición {fila['exposicion_promedio']:.0%}  caída máx {fila['caida_maxima']:.0%}  "
            f"ventas {fila['ventas']}  vs benchmark {fila['ventaja_tir_usd'] * 1e4:+.0f} pb")
    lineas.append("  tiempo por decisión: " + ", ".join(f"{d} {f:.0%}" for d, f in r.tiempo_en_decision["fraccion"].items()))
    lineas.append(f"  {r.apuestas.como_texto()}")
    if r.neutralizacion is not None:
        lineas.append(f"  {r.neutralizacion.como_texto()}")
    lineas.append(f"  Dictamen: {r.dictamen.como_texto()}")
    if not r.ventas.empty:
        lineas.append("  Ventas por tesis rota:")
        for _, v in r.ventas.iterrows():
            regreso = (f"lo vendido vuelve {v['reinversion']:%Y-%m} a {v['precio_reinversion']:.2f}"
                       if pd.notna(v.get("reinversion")) else "lo vendido no ha vuelto")
            lineas.append(f"    {v['fecha']:%Y-%m-%d} a {v['precio']:.2f}: {v['disparadores']}; "
                          f"papel a 1 año {v.get('papel_1a', np.nan):+.1%}; {regreso}")
    for c in conclusiones(r):
        lineas.append(f"  [{c.tono}] {c.titulo}: {c.texto}")
    for a in r.avisos:
        lineas.append(f"  aviso: {a}")
    return "\n".join(lineas)


__all__ = ["Decision", "Variante", "Parametros", "PARAMETROS", "Senales", "Simulacion",
           "ResultadoReglas", "senales", "simular", "backtest", "resumen_en_texto",
           "cargar_tbill", "guardar_tbill", "descargar_tbill", "cargar_calificaciones",
           "grado_de_inversion", "fines_de_mes", "Luz"]
