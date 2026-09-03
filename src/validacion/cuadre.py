"""Cuadre del AFFO: recalcular desde componentes y atar contra el reportado.

Un AFFO que no cuadra contra su propia conciliación significa una de tres cosas:
el parser leyó mal una fila, el emisor tiene una línea que no está en nuestra
taxonomía, o el número reportado no se sostiene. Ninguna de las tres justifica
usar el dato. El registro se marca ``sospechoso`` y no participa en cálculos
hasta revisión manual.

Esta es la prueba obligatoria 2 del proyecto.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.config import (
    RANGO_LTV,
    RANGO_OCUPACION,
    RANGO_PAYOUT_AFFO,
    TOLERANCIA_CUADRE_AFFO,
    TOLERANCIA_CUADRE_RELATIVA,
    Estado,
)
from src.modelo.cascada import calcular_cascada


@dataclass
class ResultadoCuadre:
    """Veredicto del cuadre de una conciliación."""

    cuadra: bool
    affo_reportado: float | None
    affo_recalculado: float | None
    diferencia: float | None
    diferencia_relativa: float | None
    estado: str
    motivo: str = ""
    detalle: pd.DataFrame = field(default_factory=pd.DataFrame)
    banderas: list[str] = field(default_factory=list)

    def como_texto(self) -> str:
        if self.cuadra:
            return f"Cuadra: reportado {self.affo_reportado:,.0f} = recalculado {self.affo_recalculado:,.0f}."
        return f"NO cuadra ({self.estado}): {self.motivo}"


def cuadrar_affo(
    componentes: dict[str, float],
    affo_reportado: float | None,
    *,
    sector: str | None = None,
    tolerancia_absoluta: float = TOLERANCIA_CUADRE_AFFO,
    tolerancia_relativa: float = TOLERANCIA_CUADRE_RELATIVA,
) -> ResultadoCuadre:
    """Recalcula el AFFO sumando la conciliación y lo compara contra el reportado.

    La tolerancia es doble a propósito: absoluta para cifras chicas y relativa
    para cifras en millones, donde el emisor redondea cada línea antes de sumarla
    y el total legítimamente difiere en unos cuantos miles.
    """
    componentes = {k: v for k, v in componentes.items() if k not in ("affo", "affo_por_accion")}
    resultado = calcular_cascada(componentes, sector=sector)
    recalculado = resultado.affo

    if recalculado is None:
        return ResultadoCuadre(
            cuadra=False,
            affo_reportado=affo_reportado,
            affo_recalculado=None,
            diferencia=None,
            diferencia_relativa=None,
            estado=Estado.SOSPECHOSO,
            motivo=(
                "No se pudo recalcular el AFFO: faltan líneas obligatorias "
                f"({', '.join(resultado.faltantes) or 'utilidad neta o depreciación'})."
            ),
            detalle=resultado.detalle,
            banderas=resultado.banderas,
        )

    if affo_reportado is None:
        return ResultadoCuadre(
            cuadra=False,
            affo_reportado=None,
            affo_recalculado=recalculado,
            diferencia=None,
            diferencia_relativa=None,
            estado=Estado.SOSPECHOSO,
            motivo="El emisor no reporta un AFFO contra el cual atar el recálculo.",
            detalle=resultado.detalle,
            banderas=resultado.banderas,
        )

    diferencia = recalculado - affo_reportado
    denominador = abs(affo_reportado) if affo_reportado else 1.0
    relativa = abs(diferencia) / denominador
    cuadra = abs(diferencia) <= tolerancia_absoluta or relativa <= tolerancia_relativa

    return ResultadoCuadre(
        cuadra=cuadra,
        affo_reportado=affo_reportado,
        affo_recalculado=recalculado,
        diferencia=diferencia,
        diferencia_relativa=relativa,
        estado=Estado.VALIDO if cuadra else Estado.SOSPECHOSO,
        motivo=(
            ""
            if cuadra
            else (
                f"Diferencia de {diferencia:,.2f} ({relativa:.3%}) entre el AFFO reportado "
                f"({affo_reportado:,.2f}) y el recalculado ({recalculado:,.2f}). "
                "O falta una línea de la conciliación o el parser leyó mal una fila."
            )
        ),
        detalle=resultado.detalle,
        banderas=resultado.banderas,
    )


# --------------------------------------------------------------------------------------
# Coherencia temporal (prueba obligatoria 3)
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoCoherencia:
    coherente: bool
    verificaciones: pd.DataFrame
    motivo: str = ""


def validar_coherencia_temporal(
    serie_trimestral: pd.Series,
    acumulados: dict[str, float] | None = None,
    *,
    tolerancia_relativa: float = 1e-3,
) -> ResultadoCoherencia:
    """Verifica ``H1 = Q1 + Q2`` y ``FY = Q1 + Q2 + Q3 + Q4`` por año.

    ``serie_trimestral`` está indexada por fin de trimestre. ``acumulados`` es un
    mapa opcional ``{'2024-H1': valor, '2024-FY': valor}`` con los acumulados
    reportados por el emisor.
    """
    if serie_trimestral.empty:
        return ResultadoCoherencia(True, pd.DataFrame(), "Serie vacía: nada que verificar.")

    s = serie_trimestral.copy()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    acumulados = acumulados or {}

    filas = []
    for anio, grupo in s.groupby(s.index.year):
        por_q = {ts.quarter: float(v) for ts, v in grupo.items()}
        clave_h1, clave_fy = f"{anio}-H1", f"{anio}-FY"

        if clave_h1 in acumulados and {1, 2} <= por_q.keys():
            suma = por_q[1] + por_q[2]
            rep = float(acumulados[clave_h1])
            filas.append(_fila_coherencia(anio, "H1 = Q1 + Q2", rep, suma, tolerancia_relativa))

        if clave_fy in acumulados and {1, 2, 3, 4} <= por_q.keys():
            suma = sum(por_q[q] for q in (1, 2, 3, 4))
            rep = float(acumulados[clave_fy])
            filas.append(
                _fila_coherencia(anio, "FY = Q1 + Q2 + Q3 + Q4", rep, suma, tolerancia_relativa)
            )

    verificaciones = pd.DataFrame(filas)
    if verificaciones.empty:
        return ResultadoCoherencia(
            True, verificaciones, "No hay acumulados reportados contra los cuales verificar."
        )
    fallas = verificaciones[~verificaciones["cuadra"]]
    if fallas.empty:
        return ResultadoCoherencia(True, verificaciones)
    detalle = "; ".join(
        f"{r['anio']} {r['regla']}: reportado {r['reportado']:,.2f} vs suma {r['suma']:,.2f}"
        for _, r in fallas.iterrows()
    )
    return ResultadoCoherencia(False, verificaciones, f"Incoherencia temporal: {detalle}")


def _fila_coherencia(anio, regla, reportado, suma, tol) -> dict:
    dif = reportado - suma
    rel = abs(dif) / (abs(reportado) if reportado else 1.0)
    return {
        "anio": anio,
        "regla": regla,
        "reportado": reportado,
        "suma": suma,
        "diferencia": dif,
        "diferencia_relativa": rel,
        "cuadra": rel <= tol,
    }


# --------------------------------------------------------------------------------------
# Rangos razonables
# --------------------------------------------------------------------------------------


REGLAS_RANGO: dict[str, tuple[float, float]] = {
    "payout_affo": RANGO_PAYOUT_AFFO,
    "payout_ffo": RANGO_PAYOUT_AFFO,
    "ocupacion": RANGO_OCUPACION,
    "ltv": RANGO_LTV,
}


def validar_rangos(valores: dict[str, float | None]) -> list[str]:
    """Devuelve la lista de violaciones de rango. Vacía significa aprobado."""
    problemas = []
    for clave, valor in valores.items():
        if valor is None or clave not in REGLAS_RANGO:
            continue
        piso, techo = REGLAS_RANGO[clave]
        if not (piso <= float(valor) <= techo):
            problemas.append(
                f"{clave} = {valor:.4f} fuera del rango razonable [{piso}, {techo}]."
            )
    return problemas


# --------------------------------------------------------------------------------------
# Prueba de suavidad del consenso
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoSuavidad:
    sospechosa: bool
    proporcion_saltos: float
    saltos_esperados: int
    saltos_observados: int
    motivo: str = ""


def prueba_suavidad_consenso(
    serie: pd.Series,
    fechas_reporte: pd.DatetimeIndex | list,
    *,
    umbral_salto: float = 0.002,
    proporcion_minima: float = 0.5,
) -> ResultadoSuavidad:
    """Detecta una serie de consenso sospechosamente lisa.

    Una serie de AFFO consenso **real** salta en las fechas de reporte: los
    analistas actualizan sus estimados cuando sale el número. Si la serie es
    suave a través de esas fechas, casi seguro es la serie reexpresada — es decir,
    el consenso de hoy proyectado hacia atrás, que es lookahead puro.
    """
    if serie.empty or len(serie) < 4:
        return ResultadoSuavidad(False, 0.0, 0, 0, "Serie demasiado corta para evaluar.")

    s = serie.copy()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    cambios = s.pct_change().abs().dropna()
    fechas = pd.DatetimeIndex(pd.to_datetime(list(fechas_reporte)))

    if len(fechas) == 0:
        return ResultadoSuavidad(False, 0.0, 0, 0, "Sin fechas de reporte para contrastar.")

    saltos_en_reporte = 0
    for f in fechas:
        ventana = cambios[(cambios.index >= f - pd.Timedelta(days=3)) & (cambios.index <= f + pd.Timedelta(days=3))]
        if not ventana.empty and float(ventana.max()) >= umbral_salto:
            saltos_en_reporte += 1

    esperados = len(fechas)
    proporcion = saltos_en_reporte / esperados if esperados else 0.0
    sospechosa = proporcion < proporcion_minima
    return ResultadoSuavidad(
        sospechosa=sospechosa,
        proporcion_saltos=proporcion,
        saltos_esperados=esperados,
        saltos_observados=saltos_en_reporte,
        motivo=(
            ""
            if not sospechosa
            else (
                f"Solo {saltos_en_reporte} de {esperados} fechas de reporte muestran un salto "
                f"en la serie. Una serie de consenso real salta cuando sale el número; esta no. "
                "Probablemente es la serie reexpresada y usarla sería lookahead."
            )
        ),
    )


# --------------------------------------------------------------------------------------
# Orquestador de la validación bloqueante
# --------------------------------------------------------------------------------------


@dataclass
class Veredicto:
    """Resultado consolidado. ``aprobado=False`` significa que el dato NO entra."""

    aprobado: bool
    estado: str
    motivos: list[str] = field(default_factory=list)
    banderas: list[str] = field(default_factory=list)
    cuadre: ResultadoCuadre | None = None

    def como_texto(self) -> str:
        cabeza = "APROBADO" if self.aprobado else f"RECHAZADO ({self.estado})"
        cuerpo = " ".join(self.motivos) if self.motivos else ""
        return f"{cabeza}. {cuerpo}".strip()


def validar_registro(
    componentes: dict[str, float],
    affo_reportado: float | None,
    *,
    sector: str | None = None,
    metricas: dict[str, float | None] | None = None,
) -> Veredicto:
    """Corre toda la validación bloqueante sobre un registro trimestral."""
    motivos: list[str] = []
    banderas: list[str] = []

    res_cuadre = cuadrar_affo(componentes, affo_reportado, sector=sector)
    if not res_cuadre.cuadra:
        motivos.append(res_cuadre.motivo)
    banderas.extend(res_cuadre.banderas)

    if metricas:
        problemas = validar_rangos(metricas)
        motivos.extend(problemas)

    aprobado = not motivos
    return Veredicto(
        aprobado=aprobado,
        estado=Estado.VALIDO if aprobado else Estado.SOSPECHOSO,
        motivos=motivos,
        banderas=banderas,
        cuadre=res_cuadre,
    )
