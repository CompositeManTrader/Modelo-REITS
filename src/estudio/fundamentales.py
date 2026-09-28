"""El negocio año por año, y lo que se sabía de él en cada fecha (P1).

Tres fuentes, y cuál manda
--------------------------
* ``anuales_primarios.csv`` — cifras de los 10-K, prospectos y comunicados,
  capturadas una por una con su documento y su cita. MANDA: es lo único que se
  leyó en el documento del emisor, cifra por cifra.
* XBRL (``SEC-XBRL`` en la base) — estados financieros de 2008 en adelante.
* 8-K (``SEC-8K-EX99.1`` en la base) — FFO y AFFO leídos automáticamente de los
  comunicados. Llenan huecos y dan la actualización trimestral, pero solo si no
  contradicen a lo reportado (ver ``contra_lo_reportado``).

Para FFO y AFFO **solo se usan cifras reportadas por el emisor**. Derivar el FFO
desde GAAP —utilidad + depreciación + deterioro − ganancia por venta— cuadra
con lo reportado en los años recientes, pero falla por más de 20% cuando el
emisor clasificaba las ventas de inmuebles como operaciones discontinuadas: en O,
224.6 millones contra 185.5 reportados en 2008. Ni esas ganancias ni esa
depreciación pasan por las líneas que la fórmula toca. La derivación queda como
diagnóstico visible, no como insumo.

Base por acción
---------------
Todo va en **acciones de hoy**: lo publicado antes de un split se divide entre su
factor (el catálogo de eventos de ``mercado`` dice cuánto y desde cuándo). Una
escisión no toca esta base porque no cambia el número de acciones.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.datos.repositorio import Repositorio
from src.estudio.mercado import (
    EventoDeCapital,
    HistoriaMercado,
    dir_de,
    dividendo_ttm,
    pagos_por_anio,
)
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
# Usa las mismas partidas que el FFO derivado, así que se mide con él: el primer
# año desde el cual la derivación del FFO cuadra con lo reportado dentro de esta
# tolerancia, ese año y todos los siguientes. En O da 2015 (+4% en 2015-2016,
# dentro de 0.4% desde 2018); antes, las ventas iban a operaciones discontinuadas.
TOLERANCIA_DERIVACION = 0.05


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


# Cuánto puede separarse una cifra por acción leída de la base de lo que el emisor
# reportó para ese año (un cuarto de lo anual, si es trimestral) antes de
# descartarla. Holgado a propósito: un trimestre con una partida extraordinaria
# se aparta 15-20% y es un dato legítimo. Lo que atrapa es otra cosa: el −1.00
# que sale de leer la llamada de nota «(1)» como negativo, o un trimestre (0.79)
# guardado en el lugar del año (3.32). Eso pasó con los 8-K de NNN.
TOLERANCIA_CONTRA_REPORTADO = 0.35
# Si el año no tiene cifra primaria, la referencia es la del año más cercano,
# hasta esta distancia.
ANIOS_DE_REFERENCIA = 3


def contra_lo_reportado(
    versiones: pd.DataFrame, reportado: pd.Series
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa las cifras de la base que contradicen a lo reportado por el emisor.

    ``versiones`` trae ``fecha_dato``, ``periodo_tipo`` («Q» o «FY») y ``valor``;
    ``reportado`` es la cifra ANUAL primaria, indexada por año. Devuelve lo que se
    queda y lo que se descarta, con lo que se esperaba.
    """
    if versiones.empty or reportado.dropna().empty:
        return versiones, versiones.iloc[0:0].assign(esperado=pd.Series(dtype=float))
    ref = reportado.dropna()
    ref.index = ref.index.astype(int)
    esperado = []
    for f, tipo in zip(pd.to_datetime(versiones["fecha_dato"]), versiones["periodo_tipo"], strict=True):
        cercanos = ref[(ref.index - f.year).map(abs) <= ANIOS_DE_REFERENCIA]
        if cercanos.empty:
            esperado.append(np.nan)
            continue
        anual = float(cercanos.iloc[(cercanos.index - f.year).map(abs).argmin()])
        esperado.append(anual / 4 if tipo == "Q" else anual)
    esperado = pd.Series(esperado, index=versiones.index, dtype=float)
    valor = pd.to_numeric(versiones["valor"], errors="coerce")
    malo = esperado.gt(0) & ((valor / esperado - 1).abs() > TOLERANCIA_CONTRA_REPORTADO)
    return versiones[~malo], versiones[malo].assign(esperado=esperado[malo])


def dividendos_por_anio(historia: HistoriaMercado, *, asof: dt.date) -> pd.Series:
    """Dividendo REGULAR por acción de hoy: los pagos de un año más recientes al 31-dic.

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

    # Lo capturado del documento primero; lo leído de la base solo llena huecos, y
    # solo si no contradice a lo reportado en los años vecinos.
    descartadas = []
    for c in ("ffo_por_accion", "affo_por_accion"):
        p = primarios[primarios["concepto"] == c].set_index("anio")
        for metodo in ("reportado", "calculado"):
            sub = p[p["metodo"] == metodo]["valor_actual"]
            poner(c, sub, "10-K / comunicado del emisor" + ("" if metodo == "reportado"
                                                              else " (total ÷ acciones)"))
        referencia = p["valor_actual"].groupby(level=0).last()
        if c in fy:
            base = fy[c].dropna()
            versiones = pd.DataFrame({"fecha_dato": [pd.Timestamp(a, 12, 31) for a in base.index],
                                      "periodo_tipo": "FY", "valor": base.values}, index=base.index)
            quedan, fuera = contra_lo_reportado(versiones, referencia)
            poner(c, quedan["valor"], "8-K del emisor")
            descartadas.append(fuera.assign(concepto=c))
        poner(c, _suma_de_trimestres(repo, ticker, c, asof), "suma de los 4 trimestres del 8-K")

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
          f"{pagos_por_anio(historia.dividendos)} pagos regulares al 31-dic")

    # EBITDAre solo donde es confiable (ver TOLERANCIA_DERIVACION).
    primer_anio = primer_anio_confiable(
        ffo_derivado(fy), tabla.get("ffo_por_accion", pd.Series(dtype=float))
    )
    if primer_anio is not None and {"utilidad_neta", "gasto_intereses"} <= set(fy.columns):
        ebitdare = _derivar_ebitdare(fy)
        poner("ebitdare", ebitdare[ebitdare.index >= primer_anio], "derivado de XBRL")

    # Razones.
    if "ffo_por_accion" not in tabla:
        tabla["ffo_por_accion"] = np.nan
    tabla["payout_ffo"] = tabla["dividendo_por_accion"] / tabla["ffo_por_accion"]
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
    tabla.attrs["primer_anio_ebitdare"] = primer_anio
    tabla.attrs["descartadas"] = pd.concat(descartadas) if descartadas else pd.DataFrame()
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
    referencia = p.groupby("anio")["valor_actual"].last()

    estimadas = 0
    versiones = repo.hechos(asof=asof, tickers=ticker, conceptos=concepto,
                            periodo_tipo="Q", vigentes=False)
    # Una versión que contradice a lo reportado no entra: con la regla de «gana la
    # última», una comparativa mal leída pisaría a la cifra buena original.
    versiones, fuera_q = contra_lo_reportado(versiones, referencia)
    ttm = pd.Series(dtype=float)
    anios_estimados: set[int] = set()
    if not versiones.empty:
        efectiva = fecha_efectiva(versiones)
        cambiadas = efectiva != versiones["fecha_publicacion"]
        estimadas += int(cambiadas.sum())
        anios_estimados |= set(pd.to_datetime(versiones.loc[cambiadas, "fecha_dato"]).dt.year)
        ttm = _ttm_por_publicacion(
            versiones.assign(fecha_publicacion=efectiva, _llegada=versiones["fecha_publicacion"])
        )

    fy = repo.hechos(asof=asof, tickers=ticker, conceptos=concepto, periodo_tipo="FY", vigentes=False)
    fy, fuera_fy = contra_lo_reportado(fy, referencia)
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
    todo.attrs["anios_estimados"] = (min(anios_estimados), max(anios_estimados)) if anios_estimados else None
    todo.attrs["descartadas"] = pd.concat([fuera_q, fuera_fy]).assign(concepto=concepto)
    todo.attrs["rezago_dias"] = _rezago_observado(pd.concat([versiones, fy]))
    return todo


def _rezago_observado(versiones: pd.DataFrame) -> tuple[int, int] | None:
    """Entre cuántos días después del cierre publica el emisor, medido y no supuesto.

    Solo cuentan las versiones con su fecha real (no las comparativas de un
    documento posterior): son las que dicen cuándo se supo el dato por primera vez.
    """
    if versiones.empty:
        return None
    v = versiones.reset_index(drop=True)
    v = v.assign(rezago=(pd.to_datetime(v["fecha_publicacion"]) - pd.to_datetime(v["fecha_dato"])).dt.days)
    propias = v[v["rezago"].between(0, UMBRAL_COMPARATIVA.days)]
    if propias.empty:
        return None
    primeras = propias.groupby("fecha_dato")["rezago"].min()
    return int(primeras.min()), int(primeras.max())


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
    primer_anio_confiable: int | None = None

    @property
    def error_max_reciente(self) -> float | None:
        """El peor error desde el primer año confiable."""
        if self.primer_anio_confiable is None:
            return None
        r = self.tabla[self.tabla.index >= self.primer_anio_confiable]["error"].dropna()
        return float(r.abs().max()) if not r.empty else None

    @property
    def error_max_antiguo(self) -> float | None:
        """El peor error antes del primer año confiable (o en toda la tabla si no lo hay)."""
        t = self.tabla if self.primer_anio_confiable is None else \
            self.tabla[self.tabla.index < self.primer_anio_confiable]
        r = t["error"].dropna()
        return float(r.abs().max()) if not r.empty else None


def ffo_derivado(fy: pd.DataFrame) -> pd.Series:
    """FFO por acción con la fórmula de Nareit sobre XBRL, por año. Diagnóstico, no insumo."""
    necesarios = {"utilidad_neta_comun", "depreciacion_amortizacion", "acciones_diluidas"}
    if fy.empty or not necesarios <= set(fy.columns):
        return pd.Series(dtype=float)
    return ((
        fy["utilidad_neta_comun"] + fy["depreciacion_amortizacion"]
        + fy.get("deterioro", 0).fillna(0) - fy.get("ganancia_venta_inmuebles", 0).fillna(0)
    ) / fy["acciones_diluidas"]).dropna()


def primer_anio_confiable(
    derivado: pd.Series, reportado: pd.Series, *, tolerancia: float = TOLERANCIA_DERIVACION
) -> int | None:
    """El primer año desde el cual la derivación cuadra con lo reportado, sin excepción.

    «Desde el cual» es literal: ese año y TODOS los posteriores con los dos datos
    tienen que caber en la tolerancia. Un año bueno aislado entre años malos no
    vuelve confiable a la fórmula.
    """
    err = (derivado / reportado.reindex(derivado.index) - 1).dropna().sort_index()
    if err.empty:
        return None
    malos = err.index[err.abs() > tolerancia]
    posteriores = err.index[err.index > malos.max()] if len(malos) else err.index
    return int(posteriores.min()) if len(posteriores) else None


def diagnostico_ffo(repo: Repositorio, ticker: str, *, asof: dt.date, tabla_anual: pd.DataFrame) -> DiagnosticoFFO:
    fy = repo.panel(ticker, CONCEPTOS_ANUALES, asof=asof, periodo_tipo="FY")
    derivado = ffo_derivado(_por_anio(fy)) if not fy.empty else pd.Series(dtype=float)
    if derivado.empty:
        return DiagnosticoFFO(pd.DataFrame(columns=["derivado", "reportado", "error"]))
    reportado = tabla_anual.get("ffo_por_accion", pd.Series(dtype=float))
    t = pd.DataFrame({"derivado": derivado, "reportado": reportado.reindex(derivado.index)})
    t["error"] = t["derivado"] / t["reportado"] - 1
    return DiagnosticoFFO(t, primer_anio_confiable=primer_anio_confiable(derivado, reportado))
