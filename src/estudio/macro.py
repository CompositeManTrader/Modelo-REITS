"""Series macro de FRED versionadas para los estudios: T-bill, bonos Baa e inflación.

Igual que la historia de mercado: se bajan una vez con ``scripts/estudio.py macro``, se
guardan en ``data/estudios/macro/`` con su manifiesto, y el estudio las lee del archivo.
Así una prueba en CI corre sin red y dos corridas del mismo commit dan lo mismo.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.config import DIR_ESTUDIOS

DIR_MACRO = DIR_ESTUDIOS / "macro"


@dataclass(frozen=True)
class SerieMacro:
    nombre: str          # archivo: <nombre>.csv.gz
    fred: str
    descripcion: str
    unidad: str
    # Días entre la fecha del dato y su publicación. El CPI de un mes (fechado el día 1)
    # sale a mediados del mes siguiente: ~45 días.
    rezago_dias: int = 1


SERIES: dict[str, SerieMacro] = {
    "tbill_3m": SerieMacro("tbill_3m", "DTB3", "3-Month Treasury Bill Secondary Market Rate, Discount Basis",
                           "porcentaje anual, base descuento"),
    "baa": SerieMacro("baa", "DBAA", "Moody's Seasoned Baa Corporate Bond Yield", "porcentaje anual"),
    "cpi": SerieMacro("cpi", "CPIAUCSL", "Consumer Price Index for All Urban Consumers: All Items",
                      "índice 1982-84 = 100", rezago_dias=45),
}


def descargar(nombre: str) -> pd.DataFrame:
    """Toca la red."""
    from src.ingesta.tasas import descargar_fred

    return descargar_fred(SERIES[nombre].fred).rename(columns={"fecha_dato": "fecha", "valor": "valor"})


def guardar(nombre: str, df: pd.DataFrame, raiz: Path | None = None) -> Path:
    serie = SERIES[nombre]
    destino = raiz or DIR_MACRO
    destino.mkdir(parents=True, exist_ok=True)
    df = df.dropna().sort_values("fecha")
    df[["fecha", "valor"]].to_csv(destino / f"{nombre}.csv.gz", index=False, compression="gzip")
    (destino / f"{nombre}.json").write_text(json.dumps({
        "serie": serie.fred,
        "fuente": f"FRED, Reserva Federal de St. Louis: {serie.descripcion} "
                  f"(https://fred.stlouisfed.org/series/{serie.fred})",
        "unidad": serie.unidad,
        "rezago_de_publicacion_dias": serie.rezago_dias,
        "descargado_en": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "desde": str(pd.Timestamp(df["fecha"].min()).date()),
        "hasta": str(pd.Timestamp(df["fecha"].max()).date()),
        "n": int(len(df)),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino / f"{nombre}.csv.gz"


def cargar(nombre: str, raiz: Path | None = None) -> pd.Series:
    """La serie tal como se guardó (porcentajes en porcentaje, índices en índice)."""
    ruta = (raiz or DIR_MACRO) / f"{nombre}.csv.gz"
    if not ruta.exists():
        return pd.Series(dtype=float, name=nombre)
    d = pd.read_csv(ruta, parse_dates=["fecha"])
    columna = "valor" if "valor" in d else "tasa"   # el T-bill se versionó primero con «tasa»
    return d.set_index("fecha")[columna].astype(float).rename(nombre)


def conocido_en(nombre: str, serie: pd.Series, fechas: pd.DatetimeIndex) -> pd.Series:
    """El último valor ya PUBLICADO a cada fecha (P1)."""
    if serie.empty:
        return pd.Series(float("nan"), index=fechas)
    s = serie.copy()
    s.index = s.index + pd.Timedelta(days=SERIES[nombre].rezago_dias)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.reindex(s.index.union(fechas)).ffill().reindex(fechas)
