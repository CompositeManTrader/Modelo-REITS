"""Cliente de SEC EDGAR: submissions, filings y documentos.

Ruta obligatoria del proyecto: los fundamentales vienen de EDGAR, no de un
agregador. El AFFO no está en XBRL porque es una medida no-GAAP, así que hay que
bajar el Exhibit 99.1 del 8-K de resultados y parsear la conciliación.

Reglas de la SEC que este módulo respeta:
* User-Agent identificable con correo de contacto.
* Máximo 10 solicitudes por segundo (se aplica un regulador de paso local).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import requests

from src.config import (
    DIR_CACHE,
    SEC_MAX_RPS,
    SEC_REINTENTOS,
    SEC_TIMEOUT,
    SEC_USER_AGENT,
    asegurar_directorios,
)

BASE_DATOS_SEC = "https://data.sec.gov"
BASE_WWW_SEC = "https://www.sec.gov"


class ErrorEdgar(RuntimeError):
    """Fallo al hablar con EDGAR. Nunca se silencia: un dato faltante no se inventa."""


# --------------------------------------------------------------------------------------
# Regulador de paso: 10 req/s duro, compartido entre hilos
# --------------------------------------------------------------------------------------


class LimitadorTasa:
    def __init__(self, rps: float = SEC_MAX_RPS):
        self._intervalo = 1.0 / float(rps)
        self._ultimo = 0.0
        self._candado = threading.Lock()

    def esperar(self) -> None:
        with self._candado:
            ahora = time.monotonic()
            faltante = self._intervalo - (ahora - self._ultimo)
            if faltante > 0:
                time.sleep(faltante)
            self._ultimo = time.monotonic()


_LIMITADOR = LimitadorTasa()


# --------------------------------------------------------------------------------------
# Cliente
# --------------------------------------------------------------------------------------


@dataclass
class Filing:
    """Un documento presentado ante la SEC."""

    cik: str
    ticker: str
    formulario: str
    accession: str
    fecha_presentacion: dt.date  # ESTA es la fecha_publicacion point-in-time
    fecha_reporte: dt.date | None
    documento_principal: str
    descripcion: str = ""

    @property
    def url_carpeta(self) -> str:
        acc = self.accession.replace("-", "")
        return f"{BASE_WWW_SEC}/Archives/edgar/data/{int(self.cik)}/{acc}"

    @property
    def url_documento(self) -> str:
        return f"{self.url_carpeta}/{self.documento_principal}"


class ClienteEdgar:
    """Cliente con caché en disco, reintentos y respeto al límite de la SEC."""

    def __init__(
        self,
        user_agent: str = SEC_USER_AGENT,
        *,
        usar_cache: bool = True,
        dir_cache: Path | None = None,
    ):
        if "@" not in user_agent:
            raise ValueError(
                "La SEC exige un User-Agent con correo de contacto. Configura SEC_USER_AGENT."
            )
        self.sesion = requests.Session()
        self.sesion.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": "data.sec.gov",
            }
        )
        self.usar_cache = usar_cache
        asegurar_directorios()
        self.dir_cache = dir_cache or (DIR_CACHE / "edgar")
        self.dir_cache.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ bajo nivel

    def _ruta_cache(self, url: str) -> Path:
        import hashlib

        h = hashlib.sha256(url.encode()).hexdigest()[:24]
        return self.dir_cache / f"{h}.cache"

    def obtener(self, url: str, *, binario: bool = False) -> str:
        """GET con caché, reintentos exponenciales y limitador de tasa."""
        ruta = self._ruta_cache(url)
        if self.usar_cache and ruta.exists():
            return ruta.read_text(encoding="utf-8", errors="replace")

        ultimo_error: Exception | None = None
        for intento in range(SEC_REINTENTOS):
            _LIMITADOR.esperar()
            try:
                host = "data.sec.gov" if url.startswith(BASE_DATOS_SEC) else "www.sec.gov"
                r = self.sesion.get(url, timeout=SEC_TIMEOUT, headers={"Host": host})
                if r.status_code == 200:
                    texto = r.text
                    if self.usar_cache:
                        ruta.write_text(texto, encoding="utf-8", errors="replace")
                    return texto
                if r.status_code in (403, 429, 500, 502, 503, 504):
                    ultimo_error = ErrorEdgar(f"HTTP {r.status_code} en {url}")
                    time.sleep(2**intento)
                    continue
                raise ErrorEdgar(f"HTTP {r.status_code} en {url}")
            except requests.RequestException as exc:
                ultimo_error = exc
                time.sleep(2**intento)
        raise ErrorEdgar(f"No se pudo obtener {url}: {ultimo_error}")

    def obtener_json(self, url: str) -> dict:
        try:
            return json.loads(self.obtener(url))
        except json.JSONDecodeError as exc:
            raise ErrorEdgar(f"Respuesta no es JSON válido: {url}") from exc

    # ------------------------------------------------------------------ alto nivel

    def submissions(self, cik: str) -> dict:
        """Metadatos e índice de presentaciones recientes del emisor."""
        cik10 = str(cik).zfill(10)
        return self.obtener_json(f"{BASE_DATOS_SEC}/submissions/CIK{cik10}.json")

    def companyfacts(self, cik: str) -> dict:
        """Todas las partidas XBRL reportadas por el emisor (API companyfacts)."""
        cik10 = str(cik).zfill(10)
        return self.obtener_json(f"{BASE_DATOS_SEC}/api/xbrl/companyfacts/CIK{cik10}.json")

    def listar_filings(
        self,
        cik: str,
        ticker: str,
        *,
        formularios: Iterable[str] = ("8-K",),
        desde: dt.date | None = None,
        limite: int | None = None,
    ) -> list[Filing]:
        """Lista presentaciones del emisor filtrando por tipo de formulario.

        La ``fecha_presentacion`` que devuelve EDGAR es la fecha de publicación
        point-in-time: antes de ella nadie podía ver ese número.
        """
        datos = self.submissions(cik)
        recientes = datos.get("filings", {}).get("recent", {})
        formularios = {f.upper() for f in formularios}
        campos = (
            "form",
            "accessionNumber",
            "filingDate",
            "reportDate",
            "primaryDocument",
            "primaryDocDescription",
        )
        columnas = {c: recientes.get(c, []) for c in campos}
        n = len(columnas["form"])
        salida: list[Filing] = []
        for i in range(n):
            form = str(columnas["form"][i]).upper()
            if form not in formularios:
                continue
            fpres = _fecha(columnas["filingDate"][i])
            if desde is not None and fpres < desde:
                continue
            salida.append(
                Filing(
                    cik=str(cik),
                    ticker=ticker,
                    formulario=form,
                    accession=str(columnas["accessionNumber"][i]),
                    fecha_presentacion=fpres,
                    fecha_reporte=_fecha(columnas["reportDate"][i]),
                    documento_principal=str(columnas["primaryDocument"][i] or ""),
                    descripcion=str(columnas["primaryDocDescription"][i] or ""),
                )
            )
            if limite is not None and len(salida) >= limite:
                break
        return salida

    def indice_filing(self, filing: Filing) -> list[dict]:
        """Contenido de la carpeta del filing (para localizar el Exhibit 99.1)."""
        url = f"{filing.url_carpeta}/index.json"
        datos = self.obtener_json(url)
        return datos.get("directory", {}).get("item", [])

    def exhibits_declarados(self, filing: Filing) -> list[dict]:
        """Lee el índice del filing y devuelve los exhibits con su **tipo declarado**.

        Hay que ir al índice y no adivinar por el nombre del archivo. Realty Income
        nombra su Exhibit 99.1 ``o-991q22026.htm``, sin la cadena "ex99" en ningún
        lado; una heurística basada en el nombre lo pierde en silencio, que es la
        peor forma de perder un dato. El índice sí declara ``EX-99.1``.
        """
        url = f"{filing.url_carpeta}/{filing.accession}-index.html"
        try:
            html = self.obtener(url)
        except ErrorEdgar:
            return []

        from bs4 import BeautifulSoup

        sopa = BeautifulSoup(html, "lxml")
        salida: list[dict] = []
        for tabla in sopa.find_all("table"):
            encabezado = " ".join(th.get_text(" ", strip=True).lower() for th in tabla.find_all("th"))
            if "type" not in encabezado or "document" not in encabezado:
                continue
            columnas = [th.get_text(" ", strip=True).lower() for th in tabla.find_all("th")]
            try:
                i_doc, i_tipo = columnas.index("document"), columnas.index("type")
            except ValueError:
                continue
            i_desc = columnas.index("description") if "description" in columnas else None
            for tr in tabla.find_all("tr"):
                celdas = tr.find_all("td")
                if len(celdas) <= max(i_doc, i_tipo):
                    continue
                enlace = celdas[i_doc].find("a")
                if enlace is None or not enlace.get("href"):
                    continue
                nombre = enlace.get_text(" ", strip=True)
                salida.append(
                    {
                        "nombre": nombre,
                        "tipo": celdas[i_tipo].get_text(" ", strip=True).upper(),
                        "descripcion": (
                            celdas[i_desc].get_text(" ", strip=True) if i_desc is not None else ""
                        ),
                        # El href de EDGAR trae el parámetro de "iXBRL viewer"; se limpia.
                        "url": f"{filing.url_carpeta}/{nombre.split('/')[-1]}",
                    }
                )
        return salida

    def documentos_resultados(self, filing: Filing) -> list[tuple[str, str]]:
        """Todos los exhibits EX-99 del filing que parecen comunicado de resultados.

        Se devuelven **todos** porque el 99.1 trae el comunicado y el 99.2 suele traer
        el paquete suplementario con las tablas "HISTORICAL FFO AND AFFO" de cinco
        años, que es de donde salen los trimestres reconstruidos.
        """
        exhibits = self.exhibits_declarados(filing)
        candidatos = [
            e for e in exhibits
            if e["tipo"].startswith("EX-99") and e["nombre"].lower().endswith((".htm", ".html"))
        ]
        if not candidatos:
            # Respaldo por nombre, para filings viejos sin índice bien formado.
            try:
                items = self.indice_filing(filing)
            except ErrorEdgar:
                return []
            candidatos = [
                {"nombre": it["name"], "url": f"{filing.url_carpeta}/{it['name']}", "tipo": "?"}
                for it in items
                if isinstance(it, dict)
                and str(it.get("name", "")).lower().endswith((".htm", ".html"))
                and re.search(r"(ex-?99|99\d|press|earnings|suppl)", str(it.get("name", "")), re.I)
            ]

        candidatos.sort(key=lambda e: (e.get("tipo", ""), e["nombre"]))
        salida: list[tuple[str, str]] = []
        for e in candidatos:
            try:
                html = self.obtener(e["url"])
            except ErrorEdgar:
                continue
            if _parece_comunicado_resultados(html):
                salida.append((e["url"], html))
        return salida

    def documento_resultados(self, filing: Filing) -> tuple[str, str] | None:
        """El primer exhibit de resultados del filing, o ``None`` si no hay."""
        docs = self.documentos_resultados(filing)
        return docs[0] if docs else None


# --------------------------------------------------------------------------------------
# Auxiliares
# --------------------------------------------------------------------------------------


def _fecha(valor) -> dt.date | None:
    if not valor:
        return None
    try:
        return dt.date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def _parece_comunicado_resultados(html: str) -> bool:
    bajo = html.lower()
    señales = ("ffo", "funds from operations")
    return any(s in bajo for s in señales)


def es_8k_de_resultados(filing: Filing) -> bool:
    """Heurística barata sobre metadatos para no bajar todos los 8-K.

    Los 8-K de resultados llevan el Item 2.02 ("Results of Operations"). Cuando la
    descripción no lo dice, el llamador debe confirmar bajando el exhibit.
    """
    texto = f"{filing.descripcion} {filing.documento_principal}".lower()
    return any(p in texto for p in ("earnings", "results", "ex99", "ex-99", "2.02"))
