"""Validación de series de precio contra cierres verificables (P2).

Puerta de entrada obligatoria: ninguna serie de precios se usa sin comprobarla
contra al menos tres cierres conocidos. Si el error supera 2%, la serie se
rechaza — no se "ajusta", no se usa "con cuidado": se rechaza.

El objetivo específico es cachar series ajustadas por dividendos disfrazadas de
crudas. Ese error tiene una firma reconocible: el error crece hacia atrás en el
tiempo, proporcional al dividendo acumulado desde la fecha hasta hoy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.config import MIN_ANCLAS_PRECIO, TOLERANCIA_ANCLA_PRECIO
from src.ingesta.precios import ResultadoAnclas, validar_contra_anclas


@dataclass
class DiagnosticoAjuste:
    """Diagnóstico de si el patrón de error delata una serie ajustada."""

    parece_ajustada: bool
    correlacion_error_antiguedad: float
    sesgo_medio: float
    explicacion: str


def diagnosticar_ajuste_por_dividendos(detalle_anclas: pd.DataFrame) -> DiagnosticoAjuste:
    """Distingue ruido de una serie sistemáticamente ajustada.

    Firma del ajuste por dividendos: el precio de la serie queda **por debajo** del
    cierre real, y la brecha se ensancha entre más antigua es la fecha. Un error de
    captura aislado no tiene esa estructura.
    """
    if detalle_anclas.empty or len(detalle_anclas) < 2:
        return DiagnosticoAjuste(False, float("nan"), float("nan"), "Muy pocas anclas para diagnosticar.")

    d = detalle_anclas.copy()
    d["fecha_dato"] = pd.to_datetime(d["fecha_dato"])
    antiguedad = (d["fecha_dato"].max() - d["fecha_dato"]).dt.days.astype(float)
    # Error con signo: negativo = la serie está por debajo del cierre real.
    sesgo = (d["obtenido"] - d["esperado"]) / d["esperado"]

    if antiguedad.std() == 0 or sesgo.std() == 0:
        corr = float("nan")
    else:
        corr = float(np.corrcoef(antiguedad, sesgo)[0, 1])

    sesgo_medio = float(sesgo.mean())
    parece = bool(sesgo_medio < -0.01 and (np.isnan(corr) or corr < -0.5))

    if parece:
        explicacion = (
            f"La serie queda {abs(sesgo_medio):.2%} por debajo del cierre real en promedio y la "
            f"brecha se ensancha hacia atrás (correlación {corr:.2f} con la antigüedad). "
            "Esa es la firma de un precio ajustado por dividendos. No sirve para calcular yields."
        )
    else:
        explicacion = (
            f"Sesgo medio {sesgo_medio:+.2%}, correlación con la antigüedad {corr:.2f}. "
            "No hay patrón de ajuste por dividendos; las diferencias parecen ruido de captura."
        )
    return DiagnosticoAjuste(parece, corr, sesgo_medio, explicacion)


@dataclass
class ReporteAnclas:
    resultado: ResultadoAnclas
    diagnostico: DiagnosticoAjuste

    @property
    def aprobada(self) -> bool:
        return self.resultado.aprobada and not self.diagnostico.parece_ajustada

    def como_texto(self) -> str:
        partes = [self.resultado.como_texto()]
        if not np.isnan(self.diagnostico.sesgo_medio):
            partes.append(self.diagnostico.explicacion)
        return " ".join(partes)


def auditar_serie(
    serie: pd.Series,
    anclas: pd.DataFrame,
    *,
    tolerancia: float = TOLERANCIA_ANCLA_PRECIO,
    min_anclas: int = MIN_ANCLAS_PRECIO,
) -> ReporteAnclas:
    """Valida y diagnostica una serie de precios en un solo paso."""
    resultado = validar_contra_anclas(serie, anclas, tolerancia=tolerancia, min_anclas=min_anclas)
    diagnostico = diagnosticar_ajuste_por_dividendos(resultado.detalle)
    return ReporteAnclas(resultado, diagnostico)


def comparar_series(cruda: pd.Series, ajustada: pd.Series) -> pd.DataFrame:
    """Cuantifica cuánto distorsiona usar la serie ajustada en lugar de la cruda.

    Sirve para mostrarle al usuario el tamaño del error en su propio caso, en vez
    de pedirle que lo acepte como principio.
    """
    a, b = cruda.copy(), ajustada.copy()
    a.index, b.index = pd.to_datetime(a.index), pd.to_datetime(b.index)
    comun = a.index.intersection(b.index)
    if len(comun) == 0:
        return pd.DataFrame()
    df = pd.DataFrame({"cruda": a.reindex(comun), "ajustada": b.reindex(comun)})
    df["diferencia_relativa"] = (df["ajustada"] - df["cruda"]) / df["cruda"]
    # El yield es inversamente proporcional al precio: sobreestimación del yield.
    df["sesgo_yield"] = df["cruda"] / df["ajustada"] - 1.0
    return df
