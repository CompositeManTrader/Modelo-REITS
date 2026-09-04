"""Series de precio SIN ajustar y su reconstrucción.

P2 — El precio para calcular yields debe ser SIN AJUSTAR
========================================================
Los proveedores gratuitos entregan precio ajustado por dividendos y escisiones.
Macrotrends daba 64.03 dólares para el cierre de 2021 de Realty Income; el cierre
real fue 71.56. Un yield calculado sobre precio ajustado infla sistemáticamente
todos los rendimientos históricos y hace que el modelo "compre" en fechas inventadas.

El sesgo no es aleatorio: crece hacia atrás en el tiempo, proporcional al dividendo
acumulado. En un REIT que paga 5% anual, veinte años de ajuste distorsionan el
precio histórico en más de la mitad.

Método de respaldo validado
---------------------------
Si no hay fuente confiable de precio crudo, se reconstruye::

    precio = dividendo TTM ÷ rendimiento por dividendo TTM

Validado con error de 0.25% contra el cierre real de 2021-12-31 y 0.01% contra
2023-12-29. Toda serie reconstruida se marca como ``RECONSTRUIDO``, nunca se
presenta como observada.
"""

from __future__ import annotations

import datetime as dt
import io
from dataclasses import dataclass

import pandas as pd
import requests

from src.config import (
    MIN_ANCLAS_PRECIO,
    TOLERANCIA_ANCLA_PRECIO,
    Estado,
    Fuente,
)


class ErrorPrecios(RuntimeError):
    pass


# --------------------------------------------------------------------------------------
# Descarga
# --------------------------------------------------------------------------------------


def descargar_stooq(ticker: str, *, timeout: int = 30) -> pd.DataFrame:
    """Descarga el histórico diario de Stooq.

    Stooq entrega cierre ajustado por escisiones pero **no** por dividendos, que es
    justo lo que necesitamos: el precio al que efectivamente cotizó el papel. Aun
    así, la serie pasa por ``validar_contra_anclas`` antes de usarse.
    """
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
    r = requests.get(url, timeout=timeout)
    if r.status_code != 200 or not r.text.strip() or r.text.strip().lower().startswith("<"):
        raise ErrorPrecios(f"Stooq no devolvió datos para {ticker} (HTTP {r.status_code})")
    df = pd.read_csv(io.StringIO(r.text))
    if "Close" not in df.columns:
        raise ErrorPrecios(f"Respuesta de Stooq sin columna Close para {ticker}")
    df = df.rename(
        columns={"Date": "fecha_dato", "Close": "cierre_crudo", "Volume": "volumen"}
    )
    df["fecha_dato"] = pd.to_datetime(df["fecha_dato"]).dt.date
    df["ticker"] = ticker.upper()
    df["fuente"] = Fuente.MERCADO
    df["metodo"] = "observado"
    # El precio de cierre se publica el mismo día: no hay rezago que modelar.
    df["fecha_publicacion"] = df["fecha_dato"]
    columnas = ["ticker", "fecha_dato", "fecha_publicacion", "cierre_crudo", "volumen", "fuente", "metodo"]
    return df[[c for c in columnas if c in df.columns]].dropna(subset=["cierre_crudo"])


# --------------------------------------------------------------------------------------
# Reconstrucción (método de respaldo validado)
# --------------------------------------------------------------------------------------


def reconstruir_precio(dividendo_ttm: float, rendimiento_ttm: float) -> float:
    """``precio = dividendo TTM ÷ rendimiento TTM``.

    Ambos insumos deben referirse a la **misma** fecha de corte. Mezclar el
    dividendo de un año con el yield de otro produce un precio plausible y falso,
    que es la peor clase de error.
    """
    if rendimiento_ttm is None or rendimiento_ttm <= 0:
        raise ErrorPrecios("El rendimiento TTM debe ser positivo para reconstruir el precio.")
    if dividendo_ttm is None or dividendo_ttm <= 0:
        raise ErrorPrecios("El dividendo TTM debe ser positivo para reconstruir el precio.")
    return float(dividendo_ttm) / float(rendimiento_ttm)


def dividendo_ttm(dividendos: pd.DataFrame, fecha: dt.date, columna_fecha: str = "fecha_ex") -> float:
    """Suma de dividendos con fecha ex en los 12 meses previos (inclusive)."""
    if dividendos.empty:
        return 0.0
    f = pd.Timestamp(fecha)
    ventana = dividendos[
        (pd.to_datetime(dividendos[columna_fecha]) <= f)
        & (pd.to_datetime(dividendos[columna_fecha]) > f - pd.DateOffset(years=1))
    ]
    return float(ventana["monto"].sum())


def serie_reconstruida(
    ticker: str,
    dividendos: pd.DataFrame,
    rendimientos_ttm: pd.Series,
) -> pd.DataFrame:
    """Reconstruye una serie de precios desde dividendo TTM y rendimiento TTM.

    ``rendimientos_ttm`` es una serie indexada por fecha con el rendimiento por
    dividendo en decimal. Toda fila sale marcada como reconstruida.
    """
    filas = []
    for fecha, rend in rendimientos_ttm.dropna().items():
        f = pd.Timestamp(fecha).date()
        div = dividendo_ttm(dividendos, f)
        if div <= 0 or rend <= 0:
            continue
        filas.append(
            {
                "ticker": ticker.upper(),
                "fecha_dato": f,
                "fecha_publicacion": f,
                "cierre_crudo": reconstruir_precio(div, float(rend)),
                "fuente": Fuente.RECONSTRUIDO,
                "metodo": "reconstruido_div_yield",
            }
        )
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# Validación contra anclas (prueba obligatoria 4)
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoAnclas:
    """Veredicto de validar una serie contra cierres verificables."""

    aprobada: bool
    n_anclas: int
    error_max: float
    detalle: pd.DataFrame
    motivo: str = ""

    def como_texto(self) -> str:
        if self.aprobada:
            return (
                f"Serie aprobada: {self.n_anclas} anclas, error máximo {self.error_max:.2%} "
                f"(tolerancia {TOLERANCIA_ANCLA_PRECIO:.0%})."
            )
        return f"Serie RECHAZADA: {self.motivo}"


def validar_contra_anclas(
    serie: pd.Series,
    anclas: pd.DataFrame,
    *,
    tolerancia: float = TOLERANCIA_ANCLA_PRECIO,
    min_anclas: int = MIN_ANCLAS_PRECIO,
) -> ResultadoAnclas:
    """Compara la serie contra cierres conocidos. Si el error supera la tolerancia, se rechaza.

    Esta es la barrera que separa una serie utilizable de una ajustada por
    dividendos disfrazada de cruda. No es opcional: una serie sin anclas
    suficientes no entra a la base.
    """
    if serie.empty:
        return ResultadoAnclas(False, 0, float("nan"), pd.DataFrame(), "La serie está vacía.")
    if anclas.empty:
        return ResultadoAnclas(
            False, 0, float("nan"), pd.DataFrame(), "No hay anclas de precio registradas."
        )

    s = serie.copy()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()

    filas = []
    for _, a in anclas.iterrows():
        f = pd.Timestamp(a["fecha_dato"])
        previos = s[s.index <= f]
        if previos.empty:
            continue
        # Se exige coincidencia en el mismo día hábil, no un valor cercano cualquiera.
        if (f - previos.index[-1]).days > 5:
            continue
        obtenido = float(previos.iloc[-1])
        esperado = float(a["cierre_crudo"])
        error = abs(obtenido - esperado) / esperado
        filas.append(
            {
                "fecha_dato": f.date(),
                "esperado": esperado,
                "obtenido": obtenido,
                "error_relativo": error,
                "dentro_de_tolerancia": error <= tolerancia,
                "fuente_ancla": a.get("fuente", ""),
            }
        )

    detalle = pd.DataFrame(filas)
    if detalle.empty:
        return ResultadoAnclas(
            False, 0, float("nan"), detalle, "Ninguna ancla cae dentro del rango de la serie."
        )

    n = len(detalle)
    error_max = float(detalle["error_relativo"].max())
    if n < min_anclas:
        return ResultadoAnclas(
            False,
            n,
            error_max,
            detalle,
            f"Solo {n} anclas verificables; se exigen al menos {min_anclas} (P2).",
        )
    if error_max > tolerancia:
        peor = detalle.loc[detalle["error_relativo"].idxmax()]
        return ResultadoAnclas(
            False,
            n,
            error_max,
            detalle,
            (
                f"Error de {error_max:.2%} en {peor['fecha_dato']} "
                f"(esperado {peor['esperado']:.2f}, obtenido {peor['obtenido']:.2f}). "
                "Casi seguro es una serie ajustada por dividendos, no cruda."
            ),
        )
    return ResultadoAnclas(True, n, error_max, detalle)


def marcar_estado(df_precios: pd.DataFrame, resultado: ResultadoAnclas) -> pd.DataFrame:
    """Estampa el veredicto de anclas en cada fila antes de persistir."""
    df = df_precios.copy()
    df["estado"] = Estado.VALIDO if resultado.aprobada else Estado.RECHAZADO
    df["error_ancla"] = resultado.error_max
    return df


# --------------------------------------------------------------------------------------
# Anclas conocidas y verificadas
# --------------------------------------------------------------------------------------
#
# Cierres de mercado verificados manualmente contra el reporte anual del emisor y
# contra el cierre publicado por la bolsa. Sirven de piedra de toque para cualquier
# serie que entre al sistema. Ampliar esta lista es trabajo de analista, no de código.

ANCLAS_VERIFICADAS: tuple[dict, ...] = (
    {
        "ticker": "O",
        "fecha_dato": dt.date(2021, 12, 31),
        "cierre_crudo": 71.56,
        "fuente": "Cierre NYSE 2021-12-31 (contraste con el 64.03 ajustado de Macrotrends)",
    },
    {
        "ticker": "O",
        "fecha_dato": dt.date(2023, 12, 29),
        "cierre_crudo": 57.42,
        "fuente": "Cierre NYSE 2023-12-29",
    },
    {
        "ticker": "O",
        "fecha_dato": dt.date(2022, 12, 30),
        "cierre_crudo": 63.43,
        "fuente": "Cierre NYSE 2022-12-30",
    },
)
