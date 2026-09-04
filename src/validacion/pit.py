"""Prueba de truncamiento anti-lookahead (P1, prueba obligatoria 1).

La idea es sencilla y despiadada: si una función es genuinamente point-in-time,
su respuesta para el corte ``t`` es una función pura de lo publicado hasta ``t``.
Entonces:

1. Evaluarla con corte ``t`` hoy y evaluarla con corte ``t`` después de que llegó
   información nueva debe dar **exactamente** lo mismo.
2. Evaluarla con cortes crecientes ``t1 < t2 < …`` debe dar series encajadas: el
   prefijo hasta ``t1`` de la evaluación en ``t2`` debe coincidir con la evaluación
   en ``t1``.

La excepción legítima al punto 2 es la reexpresión: si entre ``t1`` y ``t2`` el
emisor republicó una cifra vieja, el prefijo *debe* cambiar. Este módulo distingue
ese caso — consultando si existe una publicación intermedia — de un lookahead real.
Confundirlos es cómo un modelo "point-in-time" acaba usando el futuro.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

Evaluador = Callable[[dt.date], pd.Series]


@dataclass
class Divergencia:
    fecha_dato: pd.Timestamp
    corte_previo: dt.date
    corte_posterior: dt.date
    valor_previo: float
    valor_posterior: float
    explicada_por_reexpresion: bool
    detalle: str = ""

    @property
    def es_lookahead(self) -> bool:
        return not self.explicada_por_reexpresion


@dataclass
class ResultadoPIT:
    sin_lookahead: bool
    cortes: list[dt.date]
    divergencias: list[Divergencia] = field(default_factory=list)
    n_comparaciones: int = 0
    motivo: str = ""

    @property
    def lookaheads(self) -> list[Divergencia]:
        return [d for d in self.divergencias if d.es_lookahead]

    @property
    def reexpresiones(self) -> list[Divergencia]:
        return [d for d in self.divergencias if d.explicada_por_reexpresion]

    def como_texto(self) -> str:
        if self.sin_lookahead:
            return (
                f"Sin lookahead: {self.n_comparaciones} comparaciones sobre {len(self.cortes)} "
                f"cortes; {len(self.reexpresiones)} diferencias explicadas por reexpresión."
            )
        primera = self.lookaheads[0]
        return (
            f"LOOKAHEAD detectado: el valor de {primera.fecha_dato.date()} cambió de "
            f"{primera.valor_previo:.6g} (corte {primera.corte_previo}) a "
            f"{primera.valor_posterior:.6g} (corte {primera.corte_posterior}) "
            "sin reexpresión que lo justifique."
        )

    def tabla(self) -> pd.DataFrame:
        if not self.divergencias:
            return pd.DataFrame(
                columns=[
                    "fecha_dato",
                    "corte_previo",
                    "corte_posterior",
                    "valor_previo",
                    "valor_posterior",
                    "explicada_por_reexpresion",
                    "detalle",
                ]
            )
        return pd.DataFrame([d.__dict__ for d in self.divergencias])


def prueba_truncamiento(
    evaluador: Evaluador,
    cortes: Sequence[dt.date],
    *,
    tolerancia: float = 1e-9,
    hubo_reexpresion: Callable[[pd.Timestamp, dt.date, dt.date], bool] | None = None,
) -> ResultadoPIT:
    """Trunca la serie en varios cortes y verifica que el pasado no se mueva.

    ``evaluador(corte)`` devuelve la serie que el sistema produciría ese día,
    indexada por ``fecha_dato``. ``hubo_reexpresion(fecha_dato, c1, c2)`` responde
    si existe una publicación entre ambos cortes que reexprese ese dato; cuando no
    se proporciona, **toda** diferencia se cuenta como lookahead, que es la postura
    conservadora correcta.
    """
    cortes = sorted({_a_fecha(c) for c in cortes})
    if len(cortes) < 2:
        raise ValueError("Se requieren al menos dos cortes para probar truncamiento.")

    series: dict[dt.date, pd.Series] = {}
    for c in cortes:
        s = evaluador(c)
        if s is None:
            s = pd.Series(dtype="float64")
        s = pd.Series(s).copy()
        if not s.empty:
            s.index = pd.to_datetime(s.index)
            s = s.sort_index()
        series[c] = s

    divergencias: list[Divergencia] = []
    comparaciones = 0

    for i in range(len(cortes) - 1):
        c1, c2 = cortes[i], cortes[i + 1]
        s1, s2 = series[c1], series[c2]
        if s1.empty:
            continue
        # El prefijo que ambas evaluaciones debían poder ver.
        limite = pd.Timestamp(c1)
        idx = s1.index[s1.index <= limite].intersection(s2.index)
        for fecha in idx:
            v1, v2 = s1.loc[fecha], s2.loc[fecha]
            if isinstance(v1, pd.Series):
                v1 = v1.iloc[-1]
            if isinstance(v2, pd.Series):
                v2 = v2.iloc[-1]
            comparaciones += 1
            if _iguales(v1, v2, tolerancia):
                continue
            explicada = bool(hubo_reexpresion(fecha, c1, c2)) if hubo_reexpresion else False
            divergencias.append(
                Divergencia(
                    fecha_dato=fecha,
                    corte_previo=c1,
                    corte_posterior=c2,
                    valor_previo=float(v1) if v1 is not None and not pd.isna(v1) else np.nan,
                    valor_posterior=float(v2) if v2 is not None and not pd.isna(v2) else np.nan,
                    explicada_por_reexpresion=explicada,
                    detalle=(
                        "Reexpresión publicada entre ambos cortes."
                        if explicada
                        else "Sin publicación intermedia que justifique el cambio."
                    ),
                )
            )

    lookaheads = [d for d in divergencias if d.es_lookahead]
    return ResultadoPIT(
        sin_lookahead=not lookaheads,
        cortes=cortes,
        divergencias=divergencias,
        n_comparaciones=comparaciones,
        motivo="" if not lookaheads else f"{len(lookaheads)} valores del pasado cambiaron.",
    )


def prueba_pureza(
    evaluador: Evaluador,
    corte: dt.date,
    agregar_datos: Callable[[], None],
) -> ResultadoPIT:
    """Verifica que la respuesta a un corte no cambie cuando llega información nueva.

    Es la prueba más directa de que la consulta filtra por ``fecha_publicacion``:
    se evalúa el corte, se inyectan datos publicados **después** de ese corte, y se
    vuelve a evaluar. Cualquier diferencia significa que la consulta está leyendo
    filas que no debía ver.
    """
    corte = _a_fecha(corte)
    antes = pd.Series(evaluador(corte)).copy()
    agregar_datos()
    despues = pd.Series(evaluador(corte)).copy()

    if not antes.empty:
        antes.index = pd.to_datetime(antes.index)
    if not despues.empty:
        despues.index = pd.to_datetime(despues.index)

    divergencias: list[Divergencia] = []
    idx = antes.index.union(despues.index)
    for fecha in idx:
        v1 = antes.get(fecha, np.nan)
        v2 = despues.get(fecha, np.nan)
        if isinstance(v1, pd.Series):
            v1 = v1.iloc[-1]
        if isinstance(v2, pd.Series):
            v2 = v2.iloc[-1]
        if _iguales(v1, v2, 1e-9):
            continue
        divergencias.append(
            Divergencia(
                fecha_dato=pd.Timestamp(fecha),
                corte_previo=corte,
                corte_posterior=corte,
                valor_previo=float(v1) if not pd.isna(v1) else np.nan,
                valor_posterior=float(v2) if not pd.isna(v2) else np.nan,
                explicada_por_reexpresion=False,
                detalle="Datos publicados después del corte alteraron la respuesta al corte.",
            )
        )

    return ResultadoPIT(
        sin_lookahead=not divergencias,
        cortes=[corte],
        divergencias=divergencias,
        n_comparaciones=len(idx),
        motivo="" if not divergencias else "La consulta ve datos posteriores al corte.",
    )


def cortes_uniformes(inicio: dt.date, fin: dt.date, n: int = 4) -> list[dt.date]:
    """Genera ``n`` cortes repartidos en el periodo. La prueba obligatoria pide cuatro."""
    inicio, fin = _a_fecha(inicio), _a_fecha(fin)
    if fin <= inicio:
        raise ValueError("El fin debe ser posterior al inicio.")
    total = (fin - inicio).days
    return [inicio + dt.timedelta(days=int(round(total * (k + 1) / (n + 1)))) for k in range(n)]


def constructor_reexpresion(repositorio, ticker: str, concepto: str):
    """Devuelve un ``hubo_reexpresion`` atado al historial real de la base.

    Con esto, la prueba de truncamiento deja de castigar reexpresiones legítimas
    sin dejar de castigar lookahead.
    """

    def _hubo(fecha_dato: pd.Timestamp, c1: dt.date, c2: dt.date) -> bool:
        historial = repositorio.revisiones(ticker, concepto, fecha_dato.date())
        if historial.empty:
            return False
        pub = pd.to_datetime(historial["fecha_publicacion"]).dt.date
        return bool(((pub > c1) & (pub <= c2)).any())

    return _hubo


def _iguales(a, b, tol: float) -> bool:
    a_na = a is None or (isinstance(a, float) and np.isnan(a)) or pd.isna(a)
    b_na = b is None or (isinstance(b, float) and np.isnan(b)) or pd.isna(b)
    if a_na and b_na:
        return True
    if a_na or b_na:
        return False
    try:
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)))
    except (TypeError, ValueError):
        return a == b


def _a_fecha(v) -> dt.date:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return pd.Timestamp(v).date()
