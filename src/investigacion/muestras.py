"""El candado de las muestras: el código no deja usar datos que el diseño todavía no abre.

* **Desarrollo** (por omisión): todo se recorta a diciembre de 2015 ANTES de calcular nada,
  así que un retorno «siguiente» calculado en desarrollo nunca mira 2016.
* **Validación**: EE. UU. completo; abrirla pide un motivo y queda en la bitácora.
* **Prueba final**: los mercados no vistos y los emisores sellados. Se guardan con su
  huella digital al bajarlos (``sellar``) y ``abrir_sellado`` se niega a entregarlos si
  no hay un modelo congelado en la bitácora, o si el archivo cambió desde que se selló.

Los emisores sellados son un tercio de EE. UU., escogidos por una función de dispersión
del ticker con una semilla fija: la misma lista hoy y dentro de un año, sin depender del
orden en que se bajaron ni de lo que rindieron.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path

import pandas as pd

from src.config import DIR_DATOS
from src.investigacion import bitacora
from src.investigacion.diseno import MUESTRAS

DIR_SELLADO = DIR_DATOS / "investigacion" / "sellado"
ARCHIVO_DE_HUELLAS = "huellas.json"


class Muestra(StrEnum):
    DESARROLLO = "desarrollo"
    VALIDACION = "validacion"
    FINAL = "final"


class MuestraCerrada(PermissionError):
    """Se pidió una muestra que el diseño todavía no permite abrir."""


# --------------------------------------------------------------------------------------
# Series de tiempo de EE. UU.
# --------------------------------------------------------------------------------------


def recortar(datos: pd.DataFrame | pd.Series, muestra: Muestra | str = Muestra.DESARROLLO, *,
             columna: str | None = None, motivo: str = "", ruta_bitacora: Path | None = None):
    """Los datos de EE. UU. que la muestra permite ver.

    ``columna`` es la columna de fecha; sin ella se usa el índice.
    """
    muestra = Muestra(muestra)
    if muestra is Muestra.FINAL:
        raise MuestraCerrada("La prueba final no se recorta de EE. UU.: se abre con `abrir_sellado`.")
    fechas = pd.to_datetime(datos[columna] if columna else datos.index)
    if muestra is Muestra.DESARROLLO:
        return datos[(fechas <= MUESTRAS.desarrollo_hasta)]
    if not motivo.strip():
        raise MuestraCerrada("Abrir la validación pide un motivo: queda en la bitácora.")
    bitacora.registrar(fase="validacion", familia="apertura", prueba="abrir validacion", muestra="validacion",
                       parametros={"motivo": motivo}, ruta=ruta_bitacora)
    return datos


# --------------------------------------------------------------------------------------
# Emisores sellados
# --------------------------------------------------------------------------------------


def esta_sellado(ticker: str) -> bool:
    """Un tercio de los tickers, siempre el mismo: depende solo del ticker y la semilla."""
    h = hashlib.sha256(f"{MUESTRAS.semilla_de_emisores}:{ticker.upper().strip()}".encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64 < MUESTRAS.fraccion_de_emisores_sellados


def sin_sellados(datos: pd.DataFrame, columna: str = "ticker") -> pd.DataFrame:
    """Quita a los emisores de la prueba final: lo que se usa en desarrollo y validación."""
    return datos[~datos[columna].map(esta_sellado)]


# --------------------------------------------------------------------------------------
# Archivos sellados: los mercados de la prueba final
# --------------------------------------------------------------------------------------


def _huella(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _huellas(raiz: Path) -> dict:
    archivo = raiz / ARCHIVO_DE_HUELLAS
    return json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else {}


def sellar(datos: pd.DataFrame, nombre: str, *, raiz: Path | None = None, fuente: str = "") -> Path:
    """Guarda un archivo de la prueba final sin mirarlo y anota su huella digital.

    Solo se reporta cuántos renglones tiene: ni fechas, ni cifras.
    """
    destino = raiz or DIR_SELLADO
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / f"{nombre}.csv.gz"
    datos.to_csv(ruta, index=False, compression={"method": "gzip", "mtime": 0}, float_format="%.8g")
    huellas = _huellas(destino)
    huellas[nombre] = {"sha256": _huella(ruta), "renglones": int(len(datos)), "fuente": fuente}
    (destino / ARCHIVO_DE_HUELLAS).write_text(json.dumps(huellas, ensure_ascii=False, indent=2, sort_keys=True),
                                              encoding="utf-8")
    return ruta


def abrir_sellado(nombre: str, *, modelo_congelado: str, raiz: Path | None = None,
                  ruta_bitacora: Path | None = None) -> pd.DataFrame:
    """Entrega un archivo de la prueba final solo con un modelo congelado y el archivo intacto."""
    origen = raiz or DIR_SELLADO
    if modelo_congelado not in bitacora.modelos_congelados(ruta_bitacora):
        raise MuestraCerrada(f"No hay un modelo congelado «{modelo_congelado}» en la bitácora: la prueba "
                             "final no se abre antes.")
    huellas = _huellas(origen)
    ruta = origen / f"{nombre}.csv.gz"
    if nombre not in huellas or not ruta.exists():
        raise FileNotFoundError(f"No hay un archivo sellado «{nombre}».")
    if _huella(ruta) != huellas[nombre]["sha256"]:
        raise MuestraCerrada(f"«{nombre}» cambió desde que se selló: la prueba final ya no es limpia.")
    bitacora.registrar(fase="final", familia="apertura", prueba=f"abrir {nombre}", muestra="final",
                       parametros={"modelo": modelo_congelado}, ruta=ruta_bitacora)
    return pd.read_csv(ruta)


def congelar(identificador: str, descripcion: dict, *, ruta_bitacora: Path | None = None) -> None:
    """Registra un modelo congelado: a partir de aquí puede abrir la prueba final."""
    bitacora.registrar(fase="congelado", familia="congelado", prueba=identificador, muestra="final",
                       parametros=descripcion, ruta=ruta_bitacora)
