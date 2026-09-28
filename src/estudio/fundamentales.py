"""El negocio año por año, y lo que se sabía de él en cada fecha (P1).

Tres fuentes, y cuál manda
--------------------------
* ``anuales_primarios.csv`` — cifras de los 10-K y comunicados de 1994 a 2018,
  capturadas una por una con su documento. Cubre lo que XBRL no alcanza.
* XBRL (``SEC-XBRL`` en la base) — estados financieros de 2008 en adelante.
* 8-K (``SEC-8K-EX99.1`` en la base) — FFO y AFFO reportados, de 2019 en adelante.

Para FFO y AFFO **solo se usan cifras reportadas por el emisor**. Derivar el FFO
desde GAAP —utilidad + depreciación + deterioro − ganancia por venta— cuadra
dentro de 0.4% de 2019 a 2023, pero antes de 2015 falla por más de 20%: 224.6
millones contra 185.5 reportados en 2008, 2.88 por acción contra 2.34 en 2013.
En esos años O clasificaba las ventas de inmuebles como operaciones
discontinuadas, y ni sus ganancias ni su depreciación pasan por las líneas que
la fórmula toca. Un FFO con 20% de error hace ver barata a la acción en toda la
década de 2010. La derivación queda como diagnóstico visible, no como insumo.

Base por acción
---------------
Todo va en **acciones de hoy**: lo publicado antes del split de 2005 se divide
entre 2 (el catálogo de eventos de ``mercado`` dice cuánto y desde cuándo). La
escisión de 2021 no toca esta base porque no cambió el número de acciones.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.datos.repositorio import Repositorio
from src.estudio.mercado import EventoDeCapital, HistoriaMercado, dir_de, dividendo_ttm
from src.servicio import _derivar_ebitdare, deuda_por_periodo

ARCHIVO_PRIMARIOS = "anuales_primarios.csv"

CONCEPTOS_ANUALES = (
    "ingresos_totales", "ingresos", "ingreso_rentas", "utilidad_neta", "utilidad_neta_comun",
    "gasto_intereses", "impuestos", "depreciacion_amortizacion", "deterioro",
    "ganancia_venta_inmuebles", "gasto_administracion", "acciones_diluidas",
    "ffo", "ffo_por_accion", "affo", "affo_por_accion", "adquisicion_inmuebles",
)
CONCEPTOS_SALDO = (
    "activos_totales", "deuda_total", "efectivo", "inmuebles_bruto", "capital_contable",
    "deuda_hipotecaria", "notas_senior", "linea_de_credito", "deuda_no_garantizada",
    "otras_notas_por_pagar", "prestamos_a_plazo", "acciones_en_circulacion",
)

# Desde qué año el EBITDAre derivado de XBRL es confiable para el apalancamiento.
# Por la misma razón que el FFO: antes de 2015 las ventas iban a discontinuadas.
# Medido con el FFO, que usa las mismas partidas: +4% en 2015-2016, dentro de
# 0.4% desde 2018.
PRIMER_ANIO_EBITDARE = 2015


# --------------------------------------------------------------------------------------
# Cifras de fuente primaria anteriores a XBRL
# --------------------------------------------------------------------------------------


def factor_de_base(anio_o_fecha, eventos: tuple[EventoDeCapital, ...]) -> float:
    """Entre cuánto dividir una cifra por acción publicada en esa época.

    Solo cuentan los splits: una escisión no cambia el número de acciones.
    """
    fecha = (
        pd.Timestamp(dt.date(int(anio_o_fecha), 12, 31))
        if isinstance(anio_o_fecha, (int, np.integer)) else pd.Timestamp(anio_o_fecha)
    )
    factor = 1.0
    for e in eventos:
        if e.tipo == "split" and pd.Timestamp(e.fecha) > fecha:
            factor *= e.factor
    return factor


def cargar_primarios(
    ticker: str, eventos: tuple[EventoDeCapital, ...], raiz: Path | None = None
) -> pd.DataFrame:
    """Las cifras capturadas a mano, con el valor ya en acciones de hoy."""
    ruta = dir_de(ticker, raiz) / ARCHIVO_PRIMARIOS
    if not ruta.exists():
        return pd.DataFrame(columns=["anio", "concepto", "valor", "valor_actual", "base",
                                     "metodo", "fuente", "fecha_publicacion"])
    d = pd.read_csv(ruta, parse_dates=["fecha_publicacion"])
    d["valor_actual"] = [
        v / factor_de_base(a, eventos) if b == "pre_split" else v
        for a, v, b in zip(d["anio"], d["valor"], d["base"], strict=True)
    ]
    return d


# --------------------------------------------------------------------------------------
# El negocio por año
# --------------------------------------------------------------------------------------


def _numerico(df: pd.DataFrame) -> pd.DataFrame:
    return df.apply(pd.to_numeric, errors="coerce").astype(float)


def _por_anio(df: pd.DataFrame) -> pd.DataFrame:
    """Reindexa un panel fechado por su año, quedándose con el cierre de diciembre."""
    if df.empty:
        return df
    df = _numerico(df)
    idx = pd.to_datetime(df.index)
    df = df[(idx.month == 12) & (idx.day == 31)]
    df.index = pd.to_datetime(df.index).year
    return df


def _suma_de_trimestres(repo: Repositorio, ticker: str, concepto: str, asof: dt.date) -> pd.Series:
    """Año completo como suma de sus cuatro trimestres, solo si están los cuatro."""
    q = repo.serie(ticker, concepto, asof=asof, periodo_tipo="Q")
    if q.empty:
        return pd.Series(dtype=float)
    q.index = pd.to_datetime(q.index)
    anios = {}
    for anio, grupo in q.groupby(q.index.year):
        if len(grupo) == 4 and set(grupo.index.quarter) == {1, 2, 3, 4}:
            anios[anio] = float(grupo.sum())
    return pd.Series(anios, dtype=float)


def dividendos_por_anio(historia: HistoriaMercado, *, asof: dt.date) -> pd.Series:
    """Dividendo REGULAR por acción de hoy: los doce pagos más recientes al 31-dic.

    Por conteo (ver ``mercado.dividendo_ttm``): sumar por año de fecha ex le daba
    a O once pagos en 2024 y trece en 2025 por el cambio a T+1. Solo años
    cerrados: ocho mensualidades de un año en curso no son un año.
    """
    d = historia.dividendos
    if d.empty:
        return pd.Series(dtype=float)
    anios = range(int(d["fecha_ex"].dt.year.min()), asof.year)
    cierres = pd.DatetimeIndex([pd.Timestamp(a, 12, 31) for a in anios])
    ttm = dividendo_ttm(d, cierres)
    ttm.index = list(anios)
    return ttm.dropna()


def anual(
    repo: Repositorio, ticker: str, *, asof: dt.date, historia: HistoriaMercado,
    primarios: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Una fila por año con todo lo que el estudio grafica. Cada celda, su fuente."""
    primarios = primarios if primarios is not None else cargar_primarios(ticker, historia.eventos)

    fy = repo.panel(ticker, CONCEPTOS_ANUALES, asof=asof, periodo_tipo="FY")
    fy = _por_anio(fy) if not fy.empty else pd.DataFrame()
    saldos = repo.panel(ticker, CONCEPTOS_SALDO, asof=asof, periodo_tipo="PUNTUAL")
    saldos = _por_anio(saldos) if not saldos.empty else pd.DataFrame()
    if not saldos.empty:
        deuda = deuda_por_periodo(saldos)
        if deuda is not None:
            saldos["deuda_total"] = deuda.fillna(saldos.get("deuda_total"))

    anios = sorted(set(primarios["anio"]) | set(fy.index) | set(saldos.index)
                   | set(dividendos_por_anio(historia, asof=asof).index))
    tabla = pd.DataFrame(index=pd.Index(anios, name="anio"))
    fuente = pd.DataFrame(index=tabla.index)

    def poner(col: str, serie: pd.Series, etiqueta: str) -> None:
        serie = serie.dropna()
        if serie.empty:
            return
        if col not in tabla:
            tabla[col] = np.nan
            fuente[col] = None
        vacias = tabla[col].isna() & tabla.index.isin(serie.index)
        tabla.loc[vacias, col] = serie.reindex(tabla.index[vacias]).values
        fuente.loc[vacias, col] = etiqueta

    # Lo reportado primero; lo demás solo llena huecos.
    for c in ("ffo_por_accion", "affo_por_accion"):
        if c in fy:
            poner(c, fy[c], "8-K del emisor")
        poner(c, _suma_de_trimestres(repo, ticker, c, asof), "suma de los 4 trimestres del 8-K")
        p = primarios[primarios["concepto"] == c].set_index("anio")
        for metodo in ("reportado", "calculado"):
            sub = p[p["metodo"] == metodo]["valor_actual"]
            poner(c, sub, "10-K / comunicado del emisor" + ("" if metodo == "reportado"
                                                              else " (total ÷ acciones)"))

    for c in ("ingresos_totales", "acciones_diluidas", "utilidad_neta", "gasto_intereses",
              "depreciacion_amortizacion", "gasto_administracion"):
        if c in fy:
            poner(c, fy[c], "XBRL")
    for c in ("activos_totales", "deuda_total", "efectivo", "inmuebles_bruto", "capital_contable",
              "acciones_en_circulacion"):
        if c in saldos:
            poner(c, saldos[c], "XBRL (saldo al 31-dic)")
    for c in ("ingresos_totales", "activos_totales", "deuda_total", "propiedades", "ocupacion",
              "inversion_en_adquisiciones", "cap_rate_adquisicion", "ffo"):
        p = primarios[primarios["concepto"] == c].set_index("anio")["valor_actual"]
        poner(c, p, "10-K / comunicado del emisor")

    # Acciones antes de XBRL: implícitas en FFO ÷ FFO por acción, ya en base de hoy.
    if "ffo" in tabla and "ffo_por_accion" in tabla:
        implicitas = tabla["ffo"] / tabla["ffo_por_accion"]
        poner("acciones_diluidas", implicitas, "implícitas: FFO ÷ FFO por acción")

    poner("dividendo_por_accion", dividendos_por_anio(historia, asof=asof),
          "doce mensualidades regulares al 31-dic")

    # EBITDAre solo donde es confiable (ver PRIMER_ANIO_EBITDARE).
    if not fy.empty and {"utilidad_neta", "gasto_intereses"} <= set(fy.columns):
        ebitdare = _derivar_ebitdare(fy)
        poner("ebitdare", ebitdare[ebitdare.index >= PRIMER_ANIO_EBITDARE], "derivado de XBRL")

    # Razones.
    tabla["payout_ffo"] = tabla.get("dividendo_por_accion") / tabla.get("ffo_por_accion")
    if "affo_por_accion" in tabla:
        tabla["payout_affo"] = tabla["dividendo_por_accion"] / tabla["affo_por_accion"]
    if {"deuda_total", "activos_totales"} <= set(tabla.columns):
        tabla["deuda_sobre_activos"] = tabla["deuda_total"] / tabla["activos_totales"]
    if {"deuda_total", "ebitdare"} <= set(tabla.columns):
        neta = tabla["deuda_total"] - tabla.get("efectivo", 0).fillna(0)
        tabla["deuda_neta_ebitdare"] = neta / tabla["ebitdare"]
    if {"gasto_intereses", "deuda_total"} <= set(tabla.columns):
        promedio = (tabla["deuda_total"] + tabla["deuda_total"].shift(1)) / 2
        tabla["costo_deuda"] = tabla["gasto_intereses"] / promedio
    if {"gasto_administracion", "ingresos_totales"} <= set(tabla.columns):
        tabla["gya_sobre_ingresos"] = tabla["gasto_administracion"] / tabla["ingresos_totales"]
    tabla.attrs["fuentes"] = fuente
    return tabla


# --------------------------------------------------------------------------------------
# Lo que se sabía en cada fecha
# --------------------------------------------------------------------------------------


# Cuándo se supo un dato que la base aprendió de un documento POSTERIOR.
#
# La ingesta de 8-K de este modelo empezó con los comunicados de 2024; los
# trimestres de 2019 a 2023 llegaron como comparativas de esos comunicados, así
# que su `fecha_publicacion` dice 2024-2026. Usarla tal cual haría creer que en
# 2023 solo se conocía el AFFO de 2018, y el P/AFFO de esos cinco años saldría
# inflado cerca de 25%. Es un sesgo, solo que hacia el otro lado.
#
# Cuando la fecha de la base está a más de un año del periodo, se estima la
# publicación original como cierre + 60 días. O publica entre 35 y 55 días
# después del cierre, así que 60 es conservador: nunca adelanta un dato. El
# riesgo que queda es una reexpresión, que se filtraría hacia atrás; se revisó
# contra los comunicados de la época y el AFFO anual de O no se reexpresó.
REZAGO_ORIGINAL = pd.Timedelta(days=60)
UMBRAL_COMPARATIVA = pd.Timedelta(days=365)


def fecha_efectiva(versiones: pd.DataFrame) -> pd.Series:
    """La fecha en que se supo cada versión, estimada si vino de una comparativa."""
    tarde = (versiones["fecha_publicacion"] - versiones["fecha_dato"]) > UMBRAL_COMPARATIVA
    return versiones["fecha_publicacion"].where(~tarde, versiones["fecha_dato"] + REZAGO_ORIGINAL)


def _ttm_por_publicacion(versiones: pd.DataFrame) -> pd.Series:
    """TTM por acción tal como se conocía en cada fecha de publicación.

    Para cada fecha en que se publicó algo, se toma la última versión conocida de
    cada trimestre y se suman los cuatro más recientes, **solo si son cuatro
    trimestres seguidos**. Un hueco no se rellena: se espera al siguiente.
    """
    if versiones.empty:
        return pd.Series(dtype=float)
    v = versiones.copy()
    v["trimestre"] = pd.PeriodIndex(v["fecha_dato"], freq="Q")
    # Desempate: dos versiones con la misma fecha efectiva —pasa cuando las dos
    # vinieron de comparativas y se les estimó la misma— se ordenan por cuándo
    # llegaron de verdad. La posterior es la corrección y es la que gana.
    orden = ["fecha_publicacion", "_llegada"] if "_llegada" in v else ["fecha_publicacion"]
    salida = {}
    for pub in sorted(v["fecha_publicacion"].unique()):
        conocido = (
            v[v["fecha_publicacion"] <= pub]
            .sort_values(orden, kind="mergesort")   # estable: el desempate no depende del azar
            .groupby("trimestre")["valor"].last()
            .sort_index()
        )
        if len(conocido) < 4:
            continue
        ult = conocido.iloc[-4:]
        if (ult.index[-1] - ult.index[0]).n != 3:
            continue
        salida[pd.Timestamp(pub)] = float(ult.sum())
    return pd.Series(salida, dtype=float).sort_index()


def flujo_conocido(
    repo: Repositorio, ticker: str, concepto: str, *, asof: dt.date, primarios: pd.DataFrame,
) -> pd.Series:
    """El flujo por acción (anual o TTM) vigente en cada fecha, SIN mirar al futuro.

    Índice: la fecha en que el dato se publicó. Para usarlo en una fecha
    cualquiera se toma el último valor con índice menor o igual — ``asof`` de
    pandas. Antes de 2019 son cifras anuales con la fecha del comunicado; desde
    2019, TTM de los 8-K trimestrales con su fecha de presentación real.
    """
    p = primarios[primarios["concepto"] == concepto]
    anual_pub = pd.Series(p["valor_actual"].values, index=pd.to_datetime(p["fecha_publicacion"]))

    estimadas = 0
    versiones = repo.hechos(asof=asof, tickers=ticker, conceptos=concepto,
                            periodo_tipo="Q", vigentes=False)
    ttm = pd.Series(dtype=float)
    if not versiones.empty:
        efectiva = fecha_efectiva(versiones)
        estimadas += int((efectiva != versiones["fecha_publicacion"]).sum())
        ttm = _ttm_por_publicacion(
            versiones.assign(fecha_publicacion=efectiva, _llegada=versiones["fecha_publicacion"])
        )

    fy = repo.hechos(asof=asof, tickers=ticker, conceptos=concepto, periodo_tipo="FY", vigentes=False)
    fy_pub = pd.Series(dtype=float)
    por_anio = pd.DataFrame(columns=["efectiva", "valor"])
    if not fy.empty:
        efectiva = fecha_efectiva(fy)
        estimadas += int((efectiva != fy["fecha_publicacion"]).sum())
        # Por año: la fecha es la primera en que se supo; el valor, la última
        # versión —la que corrigió a las anteriores—.
        fy = fy.assign(efectiva=efectiva).sort_values("fecha_publicacion")
        por_anio = fy.groupby("fecha_dato").agg(efectiva=("efectiva", "min"), valor=("valor", "last"))
        fy_pub = pd.Series(por_anio["valor"].astype(float).values, index=pd.to_datetime(por_anio["efectiva"].values))
    # La precedencia es POR AÑO, no por fecha. Si la cifra primaria y el 8-K
    # traen el mismo año fiscal, manda la primaria, porque su fecha es la del
    # documento de la época y la del 8-K puede ser una comparativa estimada. Los
    # TTM trimestrales se conservan todos: son actualizaciones entre un año y otro.
    #
    # Antes esto se resolvía cortando todo lo del 8-K anterior a la ÚLTIMA fecha
    # primaria, y en cuanto se capturó el FFO de 2025 a mano ese corte borró los
    # TTM de 2019 a 2025: el FFO se quedó en el de 2018 durante siete años y el
    # crecimiento de esas eras salía en 0.0%.
    anios_primarios = set(p["anio"].astype(int))
    if not fy_pub.empty:
        anio_fy = pd.Series(sorted(por_anio.index), dtype="datetime64[ns]").dt.year.values
        fy_pub = fy_pub[[a not in anios_primarios for a in anio_fy]]
    todo = pd.concat([anual_pub, fy_pub, ttm]).sort_index()
    # Si dos cosas se publicaron el mismo día (el FY y el TTM del 4T), gana la
    # última en llegar a la concatenación: el TTM, que es el que se sigue usando.
    todo = todo[~todo.index.duplicated(keep="last")]
    todo = todo[todo.index <= pd.Timestamp(asof)]
    todo.attrs["fechas_estimadas"] = estimadas
    return todo


def en_fechas(conocido: pd.Series, fechas: pd.DatetimeIndex) -> pd.Series:
    """El último valor publicado a cada fecha (o NaN si todavía no había nada)."""
    if conocido.empty:
        return pd.Series(np.nan, index=fechas)
    return conocido.sort_index().reindex(fechas.union(conocido.index)).ffill().reindex(fechas)


# --------------------------------------------------------------------------------------
# Diagnóstico: por qué no se deriva el FFO
# --------------------------------------------------------------------------------------


@dataclass
class DiagnosticoFFO:
    tabla: pd.DataFrame        # anio, derivado, reportado, error

    @property
    def error_max_reciente(self) -> float | None:
        r = self.tabla[self.tabla.index >= 2019]["error"].dropna()
        return float(r.abs().max()) if not r.empty else None

    @property
    def error_max_antiguo(self) -> float | None:
        r = self.tabla[self.tabla.index < 2015]["error"].dropna()
        return float(r.abs().max()) if not r.empty else None


def diagnostico_ffo(repo: Repositorio, ticker: str, *, asof: dt.date, tabla_anual: pd.DataFrame) -> DiagnosticoFFO:
    fy = repo.panel(ticker, CONCEPTOS_ANUALES, asof=asof, periodo_tipo="FY")
    if fy.empty:
        return DiagnosticoFFO(pd.DataFrame(columns=["derivado", "reportado", "error"]))
    fy = _por_anio(fy)
    necesarios = {"utilidad_neta_comun", "depreciacion_amortizacion", "acciones_diluidas"}
    if not necesarios <= set(fy.columns):
        return DiagnosticoFFO(pd.DataFrame(columns=["derivado", "reportado", "error"]))
    derivado = (
        fy["utilidad_neta_comun"] + fy["depreciacion_amortizacion"]
        + fy.get("deterioro", 0).fillna(0) - fy.get("ganancia_venta_inmuebles", 0).fillna(0)
    ) / fy["acciones_diluidas"]
    reportado = tabla_anual.get("ffo_por_accion", pd.Series(dtype=float))
    t = pd.DataFrame({"derivado": derivado, "reportado": reportado.reindex(derivado.index)})
    t["error"] = t["derivado"] / t["reportado"] - 1
    return DiagnosticoFFO(t.dropna(subset=["derivado"]))
