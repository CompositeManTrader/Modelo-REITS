"""Fase 6, los datos de la SEC: todos los REITs de EE. UU. desde 2009, vivos y muertos.

El universo se arma con dos listas que se complementan:

* **Código SIC 6798** («Real Estate Investment Trusts») en EDGAR. Deja fuera a uno de cada
  ocho REITs de capital que cotizan hoy, porque la SEC les puso otro código (hoteles,
  operadores de inmuebles, telecomunicaciones).
* **Búsqueda de texto completo** en los 10-K de cada año: quién dice que califica, eligió
  o tributa como REIT. Un emisor con otro código entra solo en los años en que su 10-K lo
  dice: así entran las conversiones (Equinix, Iron Mountain) desde que se convirtieron.

Para cada emisor se bajan sus metadatos (``submissions``), los CUSIP de su acción común
(de los 13G que otros presentan sobre él: el CUSIP viene en la portada y su dígito
verificador lo confirma) y sus estados financieros en XBRL (``companyfacts``).

Ningún archivo versionado lleva la identificación del inversionista ante la SEC.
"""

from __future__ import annotations

import html as html_lib
import re
import time

import pandas as pd

from src.investigacion.datos import DIR_INVESTIGACION
from src.investigacion.trece_f import es_cusip

DIR_EMISORES = DIR_INVESTIGACION / "emisores"
URL_FTS = "https://efts.sec.gov/LATEST/search-index"
SIC_REIT = "6798"
FRASES_REIT = (
    '"qualify as a REIT"', '"qualified as a REIT"', '"elected to be taxed as a REIT"', '"taxed as a REIT"',
    '"qualify as a real estate investment trust"', '"taxed as a real estate investment trust"',
)
# Códigos con los que la SEC registra REITs que no son 6798: inmobiliarios, hoteles,
# telecomunicaciones (torres y fibra), electricidad (infraestructura), salud, asesoría
# de inversiones (DigitalBridge) y financieros de hipotecas (que se van después, por no ser
# de capital). Un banco o una farmacéutica que menciona a su filial REIT no entra.
SIC_POSIBLES = {
    "6798", "6500", "6510", "6512", "6513", "6519", "6531", "6532", "6552", "6799", "7011", "4813", "4911",
    "4900", "6282", "8050", "8051", "8062", "6162", "6199", "6770",
}
FORMAS_10K = ("10-K", "10-K405", "10-KT")
FORMAS_13G = ("SC 13G", "SC 13G/A", "SC 13D", "SC 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A", "SCHEDULE 13D",
              "SCHEDULE 13D/A")


# --------------------------------------------------------------------------------------
# Listas
# --------------------------------------------------------------------------------------


def lista_sic(cliente, sic: str = SIC_REIT) -> pd.DataFrame:
    """Todas las empresas con ese código SIC que alguna vez presentaron un 10-K."""
    filas = []
    for inicio in range(0, 20_000, 100):
        t = cliente.obtener(
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            f"&SIC={sic}&owner=include&count=100&start={inicio}&type=10-K")
        pagina = re.findall(r'CIK=(\d{10})[^>]*>\d+</a></td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>', t, re.S)
        for cik, nombre, estado in pagina:
            nombre = html_lib.unescape(re.sub("<[^>]+>", " ", nombre)).split(" SIC:")[0].strip()
            filas.append((cik, nombre, re.sub("<[^>]+>", "", estado).strip()))
        if len(pagina) < 100:
            break
    return pd.DataFrame(filas, columns=["cik", "nombre", "estado"]).drop_duplicates("cik", ignore_index=True)


def buscar_texto(sesion, desde: int = 2009, hasta: int = 2026, *, pausa: float = 0.15) -> pd.DataFrame:
    """Los 10-K de cada año que traen alguna de las frases de REIT: (cik, sic, fecha)."""
    filas = []
    for anio in range(desde, hasta + 1):
        for frase in FRASES_REIT:
            inicio = 0
            while True:
                j = _fts(sesion, {"q": frase, "forms": "10-K", "dateRange": "custom", "startdt": f"{anio}-01-01",
                                  "enddt": f"{anio}-12-31", "from": inicio})
                time.sleep(pausa)
                hits = j["hits"]["hits"]
                for h in hits:
                    s = h["_source"]
                    for i, cik in enumerate(s["ciks"]):
                        nombre = s["display_names"][i] if i < len(s["display_names"]) else ""
                        filas.append((cik.zfill(10), re.sub(r"\s*\(CIK \d+\)$", "", nombre), (s.get("sics") or [""])[0],
                                      s["file_date"], s["adsh"]))
                inicio += len(hits)
                if not hits or inicio >= min(j["hits"]["total"]["value"], 9_900):
                    break
    d = pd.DataFrame(filas, columns=["cik", "nombre", "sic", "fecha", "accession"])
    return d.drop_duplicates(["cik", "accession"], ignore_index=True)


def _fts(sesion, params: dict) -> dict:
    ultimo = None
    for intento in range(8):
        try:
            r = sesion.get(URL_FTS, params=params, timeout=60)
            j = r.json()
            if "hits" in j:
                return j
            ultimo = f"HTTP {r.status_code}"
        except Exception as exc:  # noqa: BLE001 - la búsqueda de la SEC falla seguido con 500
            ultimo = str(exc)
        time.sleep(2**intento)
    raise RuntimeError(f"La búsqueda de texto de la SEC no respondió: {ultimo}")


# --------------------------------------------------------------------------------------
# Metadatos de cada emisor
# --------------------------------------------------------------------------------------


def presentaciones(cliente, cik: str) -> tuple[dict, pd.DataFrame]:
    """Metadatos y todas las presentaciones del emisor (las recientes y las páginas viejas)."""
    d = cliente.submissions(cik)
    campos = ("form", "filingDate", "reportDate", "accessionNumber", "primaryDocument", "items")
    partes = [pd.DataFrame({k: d["filings"]["recent"].get(k, []) for k in campos})]
    for archivo in d["filings"].get("files", []):
        viejo = cliente.obtener_json(f"https://data.sec.gov/submissions/{archivo['name']}")
        partes.append(pd.DataFrame({k: viejo.get(k, []) for k in campos}))
    f = pd.concat(partes, ignore_index=True)
    return d, f


def resumen(d: dict, f: pd.DataFrame) -> dict:
    """Lo que hace falta de cada emisor: nombres, tickers, 10-K y cómo terminó."""
    k = f[f["form"].isin(FORMAS_10K)]
    ochok = f[f["form"].isin(["8-K", "8-K/A"])]
    items = ochok["items"].fillna("")
    quiebra = ochok[items.str.contains(r"\b1\.03\b")]["filingDate"]
    control = ochok[items.str.contains(r"\b5\.01\b")]["filingDate"]
    baja = f[f["form"].isin(["15-12B", "15-12G", "15-15D", "25-NSE", "25"])]["filingDate"]
    return {
        "cik": str(d["cik"]).zfill(10),
        "nombre": d.get("name"),
        "sic": str(d.get("sic") or ""),
        "tickers": "|".join(d.get("tickers") or []),
        "bolsas": "|".join(x or "" for x in (d.get("exchanges") or [])),
        "nombres_previos": "|".join(f"{x['name']}@{str(x.get('from', ''))[:10]}" for x in d.get("formerNames", [])),
        "primer_10k": k["filingDate"].min() if len(k) else None,
        "ultimo_10k": k["filingDate"].max() if len(k) else None,
        "n_10k": len(k),
        "ultima_presentacion": f["filingDate"].max() if len(f) else None,
        "quiebra_8k": quiebra.min() if len(quiebra) else None,
        "cambio_de_control_8k": control.max() if len(control) else None,
        "baja_registro": baja.max() if len(baja) else None,
    }


# --------------------------------------------------------------------------------------
# CUSIP de la acción común
# --------------------------------------------------------------------------------------

_RE_CUSIP_CERCA = re.compile(r"CUSIP", re.I)
_RE_CANDIDATO = re.compile(r"(?<![0-9A-Z])([0-9A-Z]{6})[\s\-]{0,2}([0-9A-Z]{2})[\s\-]{0,2}([0-9])(?![0-9A-Z])")


def cusips_en_texto(texto: str, ventana: int = 300) -> list[str]:
    """Los CUSIP válidos que aparecen cerca de la palabra «CUSIP» en un documento."""
    plano = html_lib.unescape(re.sub(r"<[^>]+>", " ", texto)).upper()
    vistos: dict[str, int] = {}
    for m in _RE_CUSIP_CERCA.finditer(plano):
        tramo = plano[max(0, m.start() - ventana): m.end() + ventana]
        for c in _RE_CANDIDATO.finditer(tramo):
            cusip = "".join(c.groups())
            if es_cusip(cusip):
                vistos[cusip] = vistos.get(cusip, 0) + 1
    return sorted(vistos, key=lambda c: -vistos[c])


def filings_13g(f: pd.DataFrame, por_anio: int = 2) -> pd.DataFrame:
    """Unos cuantos 13G o 13D por año: el CUSIP cambia poco, pero cambia (splits inversos, fusiones)."""
    g = f[f["form"].isin(FORMAS_13G)].copy()
    if g.empty:
        return g
    g["anio"] = g["filingDate"].str[:4]
    return g.sort_values("filingDate").groupby("anio").head(por_anio)


def url_documento(cik: str, accession: str, documento: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{documento}"
