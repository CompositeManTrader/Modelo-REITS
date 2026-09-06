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
from src.modelo.cascada import MAGNITUD, calcular_cascada, clave_base


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
    signos: str = MAGNITUD,
) -> ResultadoCuadre:
    """Recalcula el AFFO sumando la conciliación y lo compara contra el reportado.

    ``signos`` tiene que coincidir con la convención de los componentes: los que
    salen del parser del Exhibit 99.1 vienen en convención ``"reporte"`` (ya
    signados para sumarse), y los que teclea el usuario en ``"magnitud"``. Cuadrar
    con la convención equivocada produce un descuadre de exactamente el doble de
    cada partida negativa, que es fácil de confundir con una línea faltante.

    La tolerancia es doble a propósito: absoluta para cifras chicas y relativa
    para cifras en millones, donde el emisor redondea cada línea antes de sumarla
    y el total legítimamente difiere en unos cuantos miles.
    """
    componentes = {
        k: v
        for k, v in componentes.items()
        if k not in ("affo", "affo_por_accion") and not k.endswith("_por_accion")
    }
    resultado = calcular_cascada(componentes, sector=sector, signos=signos)
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
    razon_concentracion: float
    cambio_en_reportes: float
    cambio_fuera_de_reportes: float
    n_reportes: int
    motivo: str = ""


def prueba_suavidad_consenso(
    serie: pd.Series,
    fechas_reporte: pd.DatetimeIndex | list,
    *,
    dias_ventana: int = 3,
    razon_minima: float = 2.0,
) -> ResultadoSuavidad:
    """Detecta una serie de consenso sospechosamente lisa.

    Una serie de AFFO consenso **real** salta en las fechas de reporte: los
    analistas actualizan sus estimados cuando sale el número, y entre reportes
    la serie apenas se mueve. Si la serie no distingue las fechas de reporte del
    resto del calendario, casi seguro es la serie reexpresada — el consenso de hoy
    proyectado hacia atrás, que es lookahead puro.

    Lo que se mide es **concentración**, no magnitud absoluta. Preguntar si hay un
    salto mayor a cierto umbral cerca de cada reporte no sirve: una serie con
    tendencia suave supera cualquier umbral fijo en todas partes y pasaría la
    prueba sin tener un solo salto informativo. La pregunta correcta es si los
    cambios en las fechas de reporte son **más grandes que los de cualquier otro
    día**, y por cuánto.
    """
    if serie.empty or len(serie) < 8:
        return ResultadoSuavidad(False, float("nan"), 0.0, 0.0, 0,
                                 "Serie demasiado corta para evaluar.")

    s = serie.copy()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    cambios = s.pct_change().abs().dropna()
    fechas = pd.DatetimeIndex(pd.to_datetime(list(fechas_reporte)))
    if len(fechas) == 0 or cambios.empty:
        return ResultadoSuavidad(False, float("nan"), 0.0, 0.0, 0,
                                 "Sin fechas de reporte para contrastar.")

    ventana = pd.Timedelta(days=dias_ventana)
    en_reporte = pd.Series(False, index=cambios.index)
    for f in fechas:
        en_reporte |= (cambios.index >= f - ventana) & (cambios.index <= f + ventana)

    dentro = cambios[en_reporte]
    fuera = cambios[~en_reporte]
    if dentro.empty or fuera.empty:
        return ResultadoSuavidad(False, float("nan"), 0.0, 0.0, len(fechas),
                                 "No hay observaciones dentro y fuera de las ventanas de reporte.")

    m_dentro, m_fuera = float(dentro.median()), float(fuera.median())
    razon = m_dentro / m_fuera if m_fuera > 0 else float("inf")
    sospechosa = razon < razon_minima

    return ResultadoSuavidad(
        sospechosa=sospechosa,
        razon_concentracion=razon,
        cambio_en_reportes=m_dentro,
        cambio_fuera_de_reportes=m_fuera,
        n_reportes=len(fechas),
        motivo=(
            ""
            if not sospechosa
            else (
                f"Los cambios en las fechas de reporte son solo {razon:.1f} veces los de "
                f"cualquier otro día (mínimo esperado {razon_minima:.1f}). Una serie de consenso "
                "real se mueve cuando sale el número y casi no se mueve entre reportes. Esta no "
                "los distingue: probablemente es la serie reexpresada, y usarla sería lookahead."
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
    signos: str = MAGNITUD,
) -> Veredicto:
    """Corre toda la validación bloqueante sobre un registro trimestral."""
    motivos: list[str] = []
    banderas: list[str] = []

    res_cuadre = cuadrar_affo(componentes, affo_reportado, sector=sector, signos=signos)
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


# --------------------------------------------------------------------------------------
# Cuadre respetando la estructura de la tabla del emisor
# --------------------------------------------------------------------------------------


@dataclass
class TramoConciliacion:
    """Un tramo entre dos subtotales de la conciliación tal como la publica el emisor."""

    subtotal: str
    base: str | None
    valor_base: float | None
    partidas: list[str]
    suma_partidas: float
    esperado: float
    reportado: float
    diferencia: float
    diferencia_relativa: float
    cuadra: bool
    # Un tramo sin partidas itemizadas NO se puede verificar. Marcarlo como
    # "no cuadra" confundiría "no pude comprobarlo" con "está mal", que son cosas
    # distintas: la tabla histórica de cinco años salta del FFO normalizado al AFFO
    # sin desglosar el tramo, y eso no hace falso al AFFO que el emisor reporta.
    verificable: bool = True


@dataclass
class ResultadoConciliacion:
    """Veredicto tramo por tramo. ``cuadra`` exige que TODOS los tramos cuadren."""

    cuadra: bool
    tramos: list[TramoConciliacion] = field(default_factory=list)
    partidas_ignoradas: list[str] = field(default_factory=list)
    motivo: str = ""

    @property
    def tramos_verificados(self) -> list[TramoConciliacion]:
        return [t for t in self.tramos if t.verificable]

    @property
    def tramos_no_verificables(self) -> list[TramoConciliacion]:
        return [t for t in self.tramos if not t.verificable]

    def como_tabla(self) -> pd.DataFrame:
        return pd.DataFrame([t.__dict__ for t in self.tramos])

    def como_texto(self) -> str:
        if not self.tramos:
            return "No hay subtotales reportados contra los cuales cuadrar."
        if self.cuadra:
            texto = (
                f"Cuadra: {len(self.tramos_verificados)} tramo(s) verificados contra los "
                "subtotales que el propio emisor publica."
            )
            faltantes = self.tramos_no_verificables
            if faltantes:
                texto += (
                    " Sin verificar: "
                    + ", ".join(t.subtotal for t in faltantes)
                    + " (la tabla no desglosa ese tramo; el subtotal se toma como lo reporta "
                    "el emisor y se marca como no verificado)."
                )
            return texto
        return self.motivo


ORDEN_SUBTOTALES = ("noi", "ffo", "ffo_normalizado", "affo")


def cuadrar_conciliacion(
    lineas: dict[str, float],
    orden: dict[str, int],
    *,
    tolerancia_relativa: float = TOLERANCIA_CUADRE_RELATIVA,
    tolerancia_absoluta: float = TOLERANCIA_CUADRE_AFFO,
) -> ResultadoConciliacion:
    """Cuadra la conciliación usando el **orden de las filas del emisor**.

    Es una verificación más fuerte y más honesta que imponer nuestros bloques a
    priori. Los emisores no siguen todos la misma estructura: Realty Income
    presenta el puente de utilidad neta a FFO normalizado como una sola línea
    agregada, y luego itemiza el tramo de FFO normalizado a AFFO — con la
    participación en no consolidadas y la severancia ejecutiva **dentro** de ese
    tramo, no del anterior. Nuestra taxonomía las clasifica en bloques distintos,
    y cuadrar con esa clasificación fallaría por la suma de esas dos partidas.

    Aquí, en cambio, cada tramo se define por lo que hay entre dos subtotales
    reportados. La aritmética que se verifica es la que el emisor afirma.

    Los valores deben venir en convención de **reporte** (ya signados para
    sumarse), que es como los entrega el parser del Exhibit 99.1.
    """
    presentes = [
        (s, orden[s]) for s in ORDEN_SUBTOTALES if s in lineas and s in orden
    ]
    presentes.sort(key=lambda x: x[1])
    if not presentes:
        return ResultadoConciliacion(
            False, [], [], "La tabla no reporta ningún subtotal (NOI, FFO, FFO normalizado o AFFO)."
        )

    ignoradas: list[str] = []
    tramos: list[TramoConciliacion] = []
    subtotales = {s for s, _ in presentes}
    # Ingresos y gastos del inmueble son insumos del NOI, no del puente hacia el FFO.
    # Si la tabla no reporta un subtotal de NOI, esas filas están ahí de contexto y
    # sumarlas al tramo del FFO mete el ingreso trimestral completo en la ecuación.
    contexto_noi = set() if "noi" in subtotales else {"ingreso_rentas", "gastos_operativos_inmueble"}
    base_clave: str | None = None
    base_valor: float | None = None
    inicio = -1

    for subtotal, fila_subtotal in presentes:
        partidas = [
            c
            for c, f in orden.items()
            if inicio < f < fila_subtotal
            and clave_base(c) not in subtotales
            and clave_base(c) not in contexto_noi
            and not c.endswith("_por_accion")
        ]
        suma = sum(float(lineas[c]) for c in partidas)
        esperado = suma + (base_valor or 0.0)
        reportado = float(lineas[subtotal])
        dif = esperado - reportado
        rel = abs(dif) / (abs(reportado) if reportado else 1.0)
        verificable = bool(partidas)
        tramos.append(
            TramoConciliacion(
                subtotal=subtotal,
                base=base_clave,
                valor_base=base_valor,
                partidas=partidas,
                suma_partidas=suma,
                esperado=esperado,
                reportado=reportado,
                diferencia=dif,
                diferencia_relativa=rel,
                cuadra=verificable
                and (abs(dif) <= tolerancia_absoluta or rel <= tolerancia_relativa),
                verificable=verificable,
            )
        )
        base_clave, base_valor, inicio = subtotal, reportado, fila_subtotal

    # Partidas que quedaron después del último subtotal: no participan en ningún tramo.
    ignoradas = [
        c
        for c, f in orden.items()
        if f > presentes[-1][1]
        and clave_base(c) not in subtotales
        and clave_base(c) not in contexto_noi
        and not c.endswith("_por_accion")
    ]

    fallidos = [t for t in tramos if t.verificable and not t.cuadra]
    if not fallidos:
        if not any(t.verificable for t in tramos):
            return ResultadoConciliacion(
                False,
                tramos,
                ignoradas,
                "Ningún tramo de la conciliación es verificable: la tabla reporta subtotales "
                "pero no desglosa ninguna partida. El registro no puede validarse.",
            )
        return ResultadoConciliacion(True, tramos, ignoradas)

    detalle = "; ".join(
        f"{t.subtotal}: reportado {t.reportado:,.0f} contra "
        f"{'' if t.base is None else t.base + ' + '}partidas = {t.esperado:,.0f} "
        f"(diferencia {t.diferencia:,.0f}, {t.diferencia_relativa:.2%})"
        for t in fallidos
    )
    return ResultadoConciliacion(
        False,
        tramos,
        ignoradas,
        f"La conciliación del emisor no cuadra en {len(fallidos)} tramo(s): {detalle}. "
        "O el parser perdió una fila o el reporte tiene una partida fuera de la taxonomía.",
    )


def elegir_mejor_conciliacion(extracciones: list) -> list:
    """Entre varias tablas del mismo periodo, se queda con la que **cuadra**.

    Un comunicado repite las mismas cifras en tablas con estructuras distintas: un
    resumen, la conciliación completa y la tabla histórica de cinco años. Elegir
    "la que tenga más filas" no basta, porque la tabla histórica tiene muchas filas
    y salta del FFO normalizado al AFFO sin itemizar el tramo intermedio.

    El criterio correcto es el único objetivo disponible: cuántos tramos de la
    conciliación cierran contra los subtotales que el propio emisor publica. Una
    tabla que cuadra en tres de tres tramos es la conciliación de verdad; una que
    cuadra en dos de tres tiene un tramo sin itemizar.

    Las magnitudes por acción se recogen de las demás tablas del mismo periodo,
    porque ahí sí viven.
    """
    if not extracciones:
        return []

    from dataclasses import replace

    por_periodo: dict[tuple, list] = {}
    for e in extracciones:
        por_periodo.setdefault((e.periodo.tipo, e.periodo.fin), []).append(e)

    salida = []
    for candidatas in por_periodo.values():
        def puntaje(e):
            r = cuadrar_conciliacion(e.lineas, e.orden)
            cuadrando = sum(1 for tr in r.tramos if tr.cuadra)
            fallidos = sum(1 for tr in r.tramos if tr.verificable and not tr.cuadra)
            detalle = sum(
                1 for k in e.lineas
                if clave_base(k) not in ORDEN_SUBTOTALES and not k.endswith("_por_accion")
            )
            # Tramos verificados NETOS, luego brutos, y al final el detalle.
            #
            # La primera versión ordenaba por `(-fallidos, cuadrando, detalle)`, que
            # le da prioridad ABSOLUTA a no fallar. Con eso, una tabla que no
            # verifica nada —cero tramos que cierren y cero que fallen, porque no
            # tiene ninguna partida entre subtotales— le gana a la conciliación de
            # verdad en cuanto esta falla un solo tramo. Un comunicado trae tablas
            # así: el resumen de resultados lista utilidad neta y AFFO sin el puente.
            #
            # Y una tabla que no se puede verificar no es mejor que una verificada a
            # medias: es peor, porque no hay evidencia de nada. Contar tramos
            # totales tampoco sirve, porque premiaría a la que declara muchos
            # subtotales sin desglosar ninguno.
            #
            # Hoy ningún emisor del universo llega a ese empate —se corrigió como
            # defecto latente, no porque estuviera eligiendo mal una tabla ahora—,
            # y la prueba 16 fija el caso.
            return (cuadrando - fallidos, cuadrando, detalle)

        mejor = max(candidatas, key=puntaje)
        lineas = dict(mejor.lineas)
        etiquetas = dict(mejor.etiquetas)
        orden = dict(mejor.orden)
        for otra in candidatas:
            if otra is mejor:
                continue
            for clave, valor in otra.lineas.items():
                if clave.endswith("_por_accion") and clave not in lineas:
                    lineas[clave] = valor
                    etiquetas[clave] = otra.etiquetas.get(clave, clave)
                    orden[clave] = 10_000 + otra.orden.get(clave, 0)
        salida.append(replace(mejor, lineas=lineas, etiquetas=etiquetas, orden=orden))
    return sorted(salida, key=lambda e: (e.periodo.fin, e.periodo.tipo))
