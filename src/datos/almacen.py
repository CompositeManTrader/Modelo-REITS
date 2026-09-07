"""Almacén versionado de estados financieros, dentro del repositorio.

La base SQLite no se versiona: es grande, binaria y cambia entera con cada
corrida. Los **estados financieros sí**, y por una razón concreta: son el insumo
de todo lo demás, y quererlos auditables significa poder ver en un `git diff`
exactamente qué cambió entre dos corridas y por qué. Una reexpresión de la
emisora tiene que verse como lo que es —una línea nueva— y no como un archivo
binario distinto.

Eso impone tres reglas al formato:

* **Determinista.** Mismo dato de entrada, mismos bytes de salida. Sin orden fijo
  y sin marca de tiempo en el gzip, dos corridas idénticas producen un diff, y un
  diff que siempre aparece deja de leerse.
* **Append-only en el contenido.** El crudo conserva todas las versiones
  publicadas de cada periodo. Nunca se reescribe una cifra: se agrega la nueva
  con su propia ``fecha_publicacion``.
* **Legible.** Los estados armados van en CSV plano, no comprimido. Son los que
  un humano abre para verificar un número contra el 10-Q.

El manifiesto (`manifiesto.json`) es el que gobierna **cuándo** se baja: guarda,
por emisora, el último filing visto. Mientras la SEC no publique uno nuevo, no hay
nada que descargar, y el proceso es idempotente por construcción.
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import io
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from src.config import RAIZ

DIR_EMISORAS = RAIZ / "data" / "emisoras"
RUTA_MANIFIESTO = DIR_EMISORAS / "manifiesto.json"

ARCHIVO_CRUDOS = "hechos.csv.gz"
ARCHIVO_COBERTURA = "cobertura.csv"

# Formulario que marca un reporte periódico. Un 8-K de resultados adelanta las
# cifras, pero el que trae los estados completos etiquetados es el 10-Q o el 10-K.
FORMULARIOS_PERIODICOS = ("10-Q", "10-K", "10-K/A", "10-Q/A")


def nombre_estado(estado: str, periodo_tipo: str | None) -> str:
    """Nombre del archivo de un estado. El balance no lleva sufijo: es un saldo."""
    if periodo_tipo is None:
        return f"{estado}.csv"
    sufijo = {"Q": "trimestral", "FY": "anual"}.get(periodo_tipo, periodo_tipo.lower())
    return f"{estado}_{sufijo}.csv"


# --------------------------------------------------------------------------------------
# Manifiesto
# --------------------------------------------------------------------------------------


@dataclass
class RegistroEmisora:
    """Qué se sabe de una emisora en el almacén, y de cuándo."""

    ticker: str
    cik: str = ""
    nombre: str = ""
    # El filing que disparó la última descarga. Es la llave de idempotencia.
    ultimo_accession: str = ""
    ultimo_formulario: str = ""
    ultima_fecha_presentacion: str = ""
    # Cuándo corrió la ingesta, para distinguir "no había nada nuevo" de "no corrió".
    descargado_en: str = ""
    n_hechos_crudos: int = 0
    periodos_trimestrales: int = 0
    periodos_anuales: int = 0
    lineas_encontradas: int = 0
    lineas_totales: int = 0
    # Huella de cada archivo escrito. Detecta corrupción y cambios fuera de proceso.
    huellas: dict[str, str] = field(default_factory=dict)
    incidencias: list[str] = field(default_factory=list)

    @property
    def cobertura(self) -> float:
        return self.lineas_encontradas / self.lineas_totales if self.lineas_totales else 0.0


@dataclass
class Manifiesto:
    """Índice del almacén. Es lo primero que lee la ingesta y lo último que escribe."""

    version: int = 1
    actualizado_en: str = ""
    emisoras: dict[str, RegistroEmisora] = field(default_factory=dict)

    @classmethod
    def cargar(cls, ruta: Path | None = None) -> Manifiesto:
        ruta = ruta or RUTA_MANIFIESTO
        if not ruta.exists():
            return cls()
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        emisoras = {
            t: RegistroEmisora(**r) for t, r in datos.get("emisoras", {}).items()
        }
        return cls(
            version=datos.get("version", 1),
            actualizado_en=datos.get("actualizado_en", ""),
            emisoras=emisoras,
        )

    def guardar(self, ruta: Path | None = None) -> Path:
        ruta = ruta or RUTA_MANIFIESTO
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.actualizado_en = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        cuerpo = {
            "version": self.version,
            "actualizado_en": self.actualizado_en,
            # Ordenado por ticker: sin esto el JSON cambia de orden entre corridas
            # y el diff de git deja de decir nada.
            "emisoras": {t: asdict(self.emisoras[t]) for t in sorted(self.emisoras)},
        }
        ruta.write_text(json.dumps(cuerpo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return ruta

    def registro(self, ticker: str) -> RegistroEmisora:
        return self.emisoras.setdefault(ticker, RegistroEmisora(ticker=ticker))


# --------------------------------------------------------------------------------------
# La decisión de descargar
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Veredicto:
    """Si toca bajar, y por qué. El 'por qué' se registra en la bitácora."""

    descargar: bool
    motivo: str
    accession: str = ""
    formulario: str = ""
    fecha_presentacion: dt.date | None = None


def decidir_descarga(
    registro: RegistroEmisora,
    filings: list,
    *,
    forzar: bool = False,
) -> Veredicto:
    """¿Hay un reporte periódico nuevo desde la última descarga?

    Esta es la pieza que hace que el proceso sea **idempotente y barato**: la SEC
    publica los estados completos con el 10-Q y el 10-K, así que mientras no haya
    uno nuevo no hay nada que bajar. Correr la ingesta diez veces el mismo día
    baja los datos una vez.

    Se compara contra el ``accession`` guardado, no contra una fecha. Dos filings
    del mismo día son dos documentos distintos, y comparar por fecha se salta el
    segundo en silencio.
    """
    periodicos = [f for f in filings if f.formulario in FORMULARIOS_PERIODICOS]
    if not periodicos:
        return Veredicto(False, "La emisora no tiene reportes periódicos en la ventana.")

    ultimo = max(periodicos, key=lambda f: (f.fecha_presentacion, f.accession))
    datos = {
        "accession": ultimo.accession,
        "formulario": ultimo.formulario,
        "fecha_presentacion": ultimo.fecha_presentacion,
    }

    if forzar:
        return Veredicto(True, "Descarga forzada por quien la corre.", **datos)
    if not registro.ultimo_accession:
        return Veredicto(True, "Primera descarga de esta emisora.", **datos)
    if ultimo.accession == registro.ultimo_accession:
        return Veredicto(
            False,
            f"Sin novedades: el último reporte sigue siendo el {ultimo.formulario} "
            f"del {ultimo.fecha_presentacion} ({ultimo.accession}).",
            **datos,
        )
    return Veredicto(
        True,
        f"Reporte nuevo: {ultimo.formulario} del {ultimo.fecha_presentacion} "
        f"({ultimo.accession}); el anterior era {registro.ultimo_accession}.",
        **datos,
    )


# --------------------------------------------------------------------------------------
# Escritura determinista
# --------------------------------------------------------------------------------------


def _huella(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()[:16]


def _csv_bytes(df: pd.DataFrame, *, indice: bool = False) -> bytes:
    """CSV en bytes, con final de línea fijo. Sin esto el diff depende del sistema.

    **Sin `float_format`, a propósito.** Un formato de seis cifras significativas
    convierte un activo total de 30,637,336,000 en 30,637,300,000: pierde 36 mil
    dólares y, peor, hace que el balance deje de cuadrar por esa diferencia. Pandas
    sin formato escribe la representación más corta que **regresa exactamente al
    mismo float**, que es justo lo que hace falta aquí: legible y sin pérdida.
    """
    buffer = io.StringIO()
    df.to_csv(buffer, index=indice, lineterminator="\n")
    return buffer.getvalue().encode("utf-8")


def _gzip_bytes(crudo: bytes) -> bytes:
    """Gzip SIN marca de tiempo.

    Por omisión gzip escribe la hora en el encabezado, así que comprimir dos veces
    el mismo contenido da bytes distintos y git ve un cambio en cada corrida.
    ``mtime=0`` lo vuelve reproducible.
    """
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as gz:
        gz.write(crudo)
    return buffer.getvalue()


def _escribir(ruta: Path, contenido: bytes) -> str:
    """Escribe solo si el contenido cambió, y devuelve su huella.

    No reescribir lo idéntico mantiene limpias las marcas de tiempo del árbol y
    hace evidente, al mirar el directorio, qué tocó la última corrida.
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if ruta.exists() and ruta.read_bytes() == contenido:
        return _huella(contenido)
    ruta.write_bytes(contenido)
    return _huella(contenido)


def dir_emisora(ticker: str, *, base: Path | None = None) -> Path:
    return (base or DIR_EMISORAS) / ticker


def escribir_crudos(ticker: str, crudos: pd.DataFrame, *, base: Path | None = None) -> str:
    """Guarda los hechos crudos comprimidos. Es el archivo grande y el importante."""
    ruta = dir_emisora(ticker, base=base) / ARCHIVO_CRUDOS
    return _escribir(ruta, _gzip_bytes(_csv_bytes(crudos)))


def leer_crudos(ticker: str, *, base: Path | None = None) -> pd.DataFrame:
    """Lee los hechos crudos del almacén. No toca la red."""
    ruta = dir_emisora(ticker, base=base) / ARCHIVO_CRUDOS
    if not ruta.exists():
        return pd.DataFrame()
    df = pd.read_csv(ruta, compression="gzip", dtype={"accession": str, "marco": str})
    for columna in ("fecha_inicio", "fecha_dato", "fecha_publicacion"):
        if columna in df:
            df[columna] = pd.to_datetime(df[columna], errors="coerce").dt.date
    return df


def escribir_estado(
    ticker: str,
    estado: str,
    tabla: pd.DataFrame,
    *,
    periodo_tipo: str | None,
    base: Path | None = None,
) -> str:
    """Guarda un estado armado en CSV plano: es el que un humano abre a verificar."""
    ruta = dir_emisora(ticker, base=base) / nombre_estado(estado, periodo_tipo)
    return _escribir(ruta, _csv_bytes(tabla, indice=True))


def escribir_cobertura(ticker: str, cobertura: pd.DataFrame, *, base: Path | None = None) -> str:
    ruta = dir_emisora(ticker, base=base) / ARCHIVO_COBERTURA
    return _escribir(ruta, _csv_bytes(cobertura))


def archivos_de(ticker: str, *, base: Path | None = None) -> list[Path]:
    carpeta = dir_emisora(ticker, base=base)
    return sorted(carpeta.glob("*")) if carpeta.exists() else []


def verificar_huellas(registro: RegistroEmisora, *, base: Path | None = None) -> list[str]:
    """¿Los archivos en disco siguen siendo los que el manifiesto dice?

    Detecta dos cosas distintas: corrupción, y edición a mano. La segunda no es
    necesariamente un error —alguien puede estar corrigiendo algo— pero tiene que
    ser visible, porque a partir de ahí el archivo dejó de ser reproducible desde
    la fuente.
    """
    problemas = []
    carpeta = dir_emisora(registro.ticker, base=base)
    for nombre, huella in sorted(registro.huellas.items()):
        ruta = carpeta / nombre
        if not ruta.exists():
            problemas.append(f"falta {nombre}, que el manifiesto sí registra")
            continue
        actual = _huella(ruta.read_bytes())
        if actual != huella:
            problemas.append(
                f"{nombre} cambió fuera del proceso de ingesta "
                f"(manifiesto {huella}, disco {actual})"
            )
    return problemas
