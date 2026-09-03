"""Tasas y macro: UST 10 años, Udibono, Mbono, Cetes, INPC, CPI y USD/MXN.

Dos anclas distintas del modelo:

* **UST 10 años** es la tasa libre de riesgo contra la que se mide la prima de un
  REIT estadounidense (P4). La comparación válida no es de niveles de yield entre
  emisores, sino de la prima de cada emisor sobre su propia libre de riesgo.
* **Udibono** es el benchmark real del inversionista mexicano (P10). Paga tasa real
  fija garantizada. Cualquier REIT tiene que superarla después de impuestos para
  justificar su riesgo.

Las series macro también se publican con rezago (el INPC de un mes sale a mediados
del siguiente). Por eso ``fecha_publicacion`` no se copia de ``fecha_dato`` cuando
el rezago es conocido.
"""

from __future__ import annotations

import datetime as dt
import io
import os

import pandas as pd
import requests

from src.config import (
    SERIE_CETES28,
    SERIE_CPI,
    SERIE_INPC,
    SERIE_MBONO10,
    SERIE_UDIBONO10,
    SERIE_UDIBONO30,
    SERIE_USDMXN,
    SERIE_UST10,
    Fuente,
)


class ErrorTasas(RuntimeError):
    pass


# --------------------------------------------------------------------------------------
# FRED (Reserva Federal de St. Louis) — no requiere llave para el CSV público
# --------------------------------------------------------------------------------------

SERIES_FRED: dict[str, tuple[str, str, int]] = {
    # nombre interno -> (id FRED, unidad, rezago de publicación en días)
    SERIE_UST10: ("DGS10", "porcentaje", 1),
    SERIE_CPI: ("CPIAUCSL", "indice", 14),  # el CPI de un mes se publica a mediados del siguiente
    SERIE_USDMXN: ("DEXMXUS", "tipo_cambio", 1),
}


def descargar_fred(id_serie: str, *, timeout: int = 30) -> pd.DataFrame:
    """Descarga una serie de FRED como CSV público."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={id_serie}"
    r = requests.get(url, timeout=timeout)
    if r.status_code != 200:
        raise ErrorTasas(f"FRED devolvió HTTP {r.status_code} para {id_serie}")
    df = pd.read_csv(io.StringIO(r.text))
    col_fecha = next((c for c in df.columns if c.lower() in ("date", "observation_date")), None)
    if col_fecha is None or id_serie not in df.columns:
        raise ErrorTasas(f"Formato inesperado de FRED para {id_serie}: {list(df.columns)}")
    df = df.rename(columns={col_fecha: "fecha_dato", id_serie: "valor"})
    df["fecha_dato"] = pd.to_datetime(df["fecha_dato"]).dt.date
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df[["fecha_dato", "valor"]].dropna()


def ingestar_fred(nombre_interno: str) -> list[dict]:
    """Devuelve filas listas para la tabla ``tasas``, con rezago de publicación aplicado."""
    if nombre_interno not in SERIES_FRED:
        raise ErrorTasas(f"Serie desconocida: {nombre_interno}")
    id_fred, unidad, rezago = SERIES_FRED[nombre_interno]
    df = descargar_fred(id_fred)
    filas = []
    for _, r in df.iterrows():
        valor = float(r["valor"])
        if unidad == "porcentaje":
            valor /= 100.0  # el modelo trabaja en decimales, nunca en puntos porcentuales
        filas.append(
            {
                "serie": nombre_interno,
                "fecha_dato": r["fecha_dato"],
                "fecha_publicacion": r["fecha_dato"] + dt.timedelta(days=rezago),
                "valor": valor,
                "unidad": "decimal" if unidad == "porcentaje" else unidad,
                "fuente": Fuente.FRED,
            }
        )
    return filas


# --------------------------------------------------------------------------------------
# Banxico SIE — requiere token gratuito (variable de entorno BANXICO_TOKEN)
# --------------------------------------------------------------------------------------
#
# Los identificadores del SIE cambian con el tiempo y hay varias series parecidas
# (mercado primario vs secundario, promedio vs cierre). Se dejan configurables y el
# ingestor valida que la respuesta tenga forma de serie antes de escribir nada.
# Verificar contra el catálogo del SIE antes de confiar en un identificador nuevo.

SERIES_BANXICO: dict[str, tuple[str, str, int]] = {
    SERIE_INPC: (os.environ.get("BANXICO_ID_INPC", "SP1"), "indice", 9),
    SERIE_CETES28: (os.environ.get("BANXICO_ID_CETES28", "SF43936"), "porcentaje", 1),
    SERIE_MBONO10: (os.environ.get("BANXICO_ID_MBONO10", "SF43881"), "porcentaje", 1),
    SERIE_UDIBONO10: (os.environ.get("BANXICO_ID_UDIBONO10", "SF43878"), "porcentaje", 1),
    SERIE_UDIBONO30: (os.environ.get("BANXICO_ID_UDIBONO30", "SF43880"), "porcentaje", 1),
}

URL_SIE = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/{ids}/datos"


def descargar_banxico(id_serie: str, token: str | None = None, *, timeout: int = 30) -> pd.DataFrame:
    """Descarga una serie del SIE de Banxico."""
    token = token or os.environ.get("BANXICO_TOKEN", "")
    if not token:
        raise ErrorTasas(
            "Falta BANXICO_TOKEN. Se obtiene gratis en el portal del SIE. "
            "Sin él, las series mexicanas se cargan desde la semilla y se marcan como tales."
        )
    r = requests.get(
        URL_SIE.format(ids=id_serie), headers={"Bmx-Token": token}, timeout=timeout
    )
    if r.status_code != 200:
        raise ErrorTasas(f"Banxico devolvió HTTP {r.status_code} para {id_serie}")
    datos = r.json()
    try:
        serie = datos["bmx"]["series"][0]["datos"]
    except (KeyError, IndexError) as exc:
        raise ErrorTasas(f"Respuesta del SIE sin datos para {id_serie}") from exc
    df = pd.DataFrame(serie)
    df["fecha_dato"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y").dt.date
    df["valor"] = pd.to_numeric(df["dato"].str.replace(",", ""), errors="coerce")
    return df[["fecha_dato", "valor"]].dropna()


def ingestar_banxico(nombre_interno: str, token: str | None = None) -> list[dict]:
    if nombre_interno not in SERIES_BANXICO:
        raise ErrorTasas(f"Serie desconocida: {nombre_interno}")
    id_sie, unidad, rezago = SERIES_BANXICO[nombre_interno]
    df = descargar_banxico(id_sie, token)
    filas = []
    for _, r in df.iterrows():
        valor = float(r["valor"])
        if unidad == "porcentaje":
            valor /= 100.0
        filas.append(
            {
                "serie": nombre_interno,
                "fecha_dato": r["fecha_dato"],
                "fecha_publicacion": r["fecha_dato"] + dt.timedelta(days=rezago),
                "valor": valor,
                "unidad": "decimal" if unidad == "porcentaje" else unidad,
                "fuente": Fuente.BANXICO,
            }
        )
    return filas


# --------------------------------------------------------------------------------------
# Utilidades de conversión real/nominal
# --------------------------------------------------------------------------------------


def tasa_real(nominal: float, inflacion: float) -> float:
    """Fisher exacta: ``(1+n)/(1+i) − 1``.

    La aproximación ``n − i`` se equivoca por decenas de puntos base a niveles de
    inflación mexicanos, y esos puntos base son justo el margen que se está midiendo.
    """
    return (1.0 + nominal) / (1.0 + inflacion) - 1.0


def tasa_nominal(real: float, inflacion: float) -> float:
    return (1.0 + real) * (1.0 + inflacion) - 1.0


def deflactar(serie: pd.Series, indice_precios: pd.Series, base: pd.Timestamp | None = None) -> pd.Series:
    """Convierte una serie nominal a términos reales usando un índice de precios.

    Es la operación que casi nadie hace y que cambia conclusiones: Realty Income
    creció su dividendo 3.2% anual de 2021 a 2025 contra inflación de ~3.3%. El
    ingreso quedó plano en poder adquisitivo.
    """
    if serie.empty or indice_precios.empty:
        return pd.Series(dtype="float64", index=serie.index)
    s = serie.copy()
    s.index = pd.to_datetime(s.index)
    ipc = indice_precios.copy()
    ipc.index = pd.to_datetime(ipc.index)
    ipc = ipc.sort_index()
    alineado = ipc.reindex(ipc.index.union(s.index)).ffill().reindex(s.index)
    base_ts = pd.Timestamp(base) if base is not None else s.index.max()
    ipc_base = ipc[ipc.index <= base_ts]
    if ipc_base.empty:
        return pd.Series(dtype="float64", index=s.index)
    factor = float(ipc_base.iloc[-1]) / alineado
    real = s * factor
    real.name = f"{serie.name}_real" if serie.name else "real"
    return real


def inflacion_anual(indice_precios: pd.Series) -> pd.Series:
    """Variación anual del índice de precios."""
    ipc = indice_precios.copy()
    ipc.index = pd.to_datetime(ipc.index)
    ipc = ipc.sort_index()
    return ipc.pct_change(periods=12).dropna()
