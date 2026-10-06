"""Precios trimestrales de todas las acciones, vivas y muertas, a partir de los 13F de la SEC.

Yahoo borra a los emisores que dejan de cotizar, así que con Yahoo el universo de REITs
solo tiene a los que sobrevivieron. Los 13F no tienen ese sesgo: cada administrador de
fondos con más de 100 millones de dólares reporta cada trimestre cuántas acciones tiene
de cada emisora y cuánto valen al cierre del trimestre. Valor entre acciones es el precio
de cierre; la mediana entre todos los que la tienen es robusta a los errores de captura
de uno solo.

Dos fuentes:

* **Conjuntos estructurados** de la SEC (``form-13f-data-sets``): todos los 13F desde
  los presentados en el segundo trimestre de 2013 (el trimestre de marzo de 2013).
  El valor viene en miles de dólares hasta el 2 de enero de 2023 y en dólares desde el 3.
* **Texto de antes**: de 2009 a 2012 no hay conjunto estructurado; se leen los 13F en
  texto de los administradores más grandes (índices y fondos de REITs), que juntos
  tienen a casi todos los REITs que cotizan.

Ninguna de las dos fuentes trae dividendos ni ajusta por splits: eso se arma aparte.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import DIR_CACHE

URL_PAGINA = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
CAMBIO_A_DOLARES = pd.Timestamp("2023-01-03")
MIN_ACCIONES = 1_000  # con el valor en miles, abajo de esto el redondeo pesa demasiado
DIR_13F = DIR_CACHE / "13f"


# --------------------------------------------------------------------------------------
# CUSIP
# --------------------------------------------------------------------------------------


def digito_cusip(base: str) -> int:
    """El dígito verificador de los primeros ocho caracteres de un CUSIP."""
    total = 0
    for i, ch in enumerate(base.upper()):
        if ch.isdigit():
            v = int(ch)
        elif ch.isalpha():
            v = ord(ch) - ord("A") + 10
        elif ch == "*":
            v = 36
        elif ch == "@":
            v = 37
        elif ch == "#":
            v = 38
        else:
            raise ValueError(ch)
        if i % 2 == 1:
            v *= 2
        total += v // 10 + v % 10
    return (10 - total % 10) % 10


def es_cusip(c: str) -> bool:
    c = str(c).strip().upper()
    if not re.fullmatch(r"[0-9A-Z*@#]{8}[0-9]", c) or not re.search(r"\d", c[:6]):
        return False
    try:
        return digito_cusip(c[:8]) == int(c[8])
    except ValueError:
        return False


# --------------------------------------------------------------------------------------
# Conjuntos estructurados (2013 en adelante)
# --------------------------------------------------------------------------------------


def urls_conjuntos(html: str) -> list[str]:
    rutas = re.findall(r'href="([^"]+form13f[^"]*\.zip)"', html)
    return [r if r.startswith("http") else f"https://www.sec.gov{r}" for r in dict.fromkeys(rutas)]


def agregar(tabla: pd.DataFrame, envios: pd.DataFrame) -> pd.DataFrame:
    """Una fila por (CUSIP, trimestre): precio mediano y cuántos administradores lo tienen.

    ``tabla`` es el INFOTABLE y ``envios`` el SUBMISSION de un conjunto. Solo cuentan los
    13F-HR originales (las enmiendas repiten o corrigen tenencias) con acciones, no
    principal de bonos ni opciones.
    """
    e = envios[envios["SUBMISSIONTYPE"] == "13F-HR"][["ACCESSION_NUMBER", "FILING_DATE", "PERIODOFREPORT"]].copy()
    e["presentado"] = pd.to_datetime(e["FILING_DATE"], format="%d-%b-%Y")
    e["fecha"] = pd.to_datetime(e["PERIODOFREPORT"], format="%d-%b-%Y")
    e = e[e["fecha"].dt.is_quarter_end]
    t = tabla[(tabla["SSHPRNAMTTYPE"] == "SH") & tabla["PUTCALL"].isna()]
    t = t.merge(e[["ACCESSION_NUMBER", "presentado", "fecha"]], on="ACCESSION_NUMBER")
    acciones = pd.to_numeric(t["SSHPRNAMT"], errors="coerce")
    valor = pd.to_numeric(t["VALUE"], errors="coerce")
    valor = np.where(t["presentado"] < CAMBIO_A_DOLARES, valor * 1000.0, valor)
    t = t.assign(cusip=t["CUSIP"].str.upper().str.strip(), acciones=acciones, precio=valor / acciones)
    t = t[(t["acciones"] >= MIN_ACCIONES) & (t["precio"] > 0) & np.isfinite(t["precio"])]
    # Un administrador que reporta la misma emisora en varias líneas (por subcuenta) cuenta una vez.
    t = t.groupby(["fecha", "cusip", "ACCESSION_NUMBER"], as_index=False).agg(
        acciones=("acciones", "sum"), precio=("precio", "median"),
        nombre=("NAMEOFISSUER", "first"), clase=("TITLEOFCLASS", "first"))
    return _por_cusip(corregir_escala(t))


def corregir_escala(t: pd.DataFrame) -> pd.DataFrame:
    """Lleva a la escala de los tenedores grandes a quien reportó en miles cuando eran dólares
    (o al revés). En el cambio de enero de 2023 muchos administradores chicos siguieron en
    miles: su precio sale mil veces menor. El ancla es la mediana ponderada por acciones, que
    dominan Vanguard, BlackRock y State Street."""
    t = t.sort_values(["fecha", "cusip", "precio"]).reset_index(drop=True)
    g = t.groupby(["fecha", "cusip"], sort=False)
    acum = g["acciones"].cumsum()
    mitad = g["acciones"].transform("sum") / 2
    candidato = t["precio"].where(acum >= mitad)
    ancla = candidato.groupby([t["fecha"], t["cusip"]]).transform("first")
    razon = t["precio"] / ancla
    t.loc[razon.between(1 / 2000, 1 / 500), "precio"] *= 1000
    t.loc[razon.between(500, 2000), "precio"] /= 1000
    return t


def _por_cusip(t: pd.DataFrame) -> pd.DataFrame:
    # El nombre y la clase, los del tenedor más grande: es el que menos se equivoca al capturar.
    t = t.sort_values("acciones", ascending=False)
    g = t.groupby(["fecha", "cusip"], sort=False)
    salida = g.agg(
        precio=("precio", "median"),
        tenedores=("precio", "size"),
        acciones_13f=("acciones", "sum"),
        nombre=("nombre", "first"),
        clase=("clase", "first"),
    )
    salida["p25"] = g["precio"].quantile(0.25)
    salida["p75"] = g["precio"].quantile(0.75)
    return salida.reset_index().sort_values(["fecha", "cusip"], ignore_index=True)


def leer_conjunto(ruta: Path, cusips: set[str] | None = None) -> pd.DataFrame:
    """Lee un zip estructurado; con ``cusips`` se queda solo con esos (por los 6 primeros)."""
    with zipfile.ZipFile(ruta) as z:
        # Desde 2024 los archivos vienen dentro de una carpeta con el nombre del periodo.
        def abrir(nombre: str):
            return z.open(next(n for n in z.namelist() if n.upper().endswith(nombre)))

        envios = pd.read_csv(abrir("SUBMISSION.TSV"), sep="\t", dtype=str)
        columnas = ["ACCESSION_NUMBER", "NAMEOFISSUER", "TITLEOFCLASS", "CUSIP", "VALUE", "SSHPRNAMT",
                    "SSHPRNAMTTYPE", "PUTCALL"]
        partes = []
        for trozo in pd.read_csv(abrir("INFOTABLE.TSV"), sep="\t", dtype=str, usecols=columnas,
                                 chunksize=1_000_000, quoting=3, on_bad_lines="skip"):
            if cusips is not None:
                trozo = trozo[trozo["CUSIP"].str.upper().str[:6].isin({c[:6] for c in cusips})]
            partes.append(trozo)
    return agregar(pd.concat(partes, ignore_index=True), envios)


# --------------------------------------------------------------------------------------
# 13F en texto (2009 a 2012)
# --------------------------------------------------------------------------------------

_NUM = r"\$?\s*([\d,]+(?:\.\d+)?)"
_RE_LINEA = re.compile(
    r"(?<![0-9A-Z])([0-9A-Z]{6}\s?[0-9A-Z]{2}\s?[0-9])(?![0-9A-Z])\s*[|,;]?\s*" + _NUM + r"\s*[|,;]?\s*" + _NUM
    + r"\s*[|,;]?\s*(SH|PRN)\b", re.I)


def parsear_texto(texto: str) -> pd.DataFrame:
    """Las tenencias de un 13F en texto: CUSIP, valor en miles y acciones.

    Los formatos cambian de un administrador a otro (columnas fijas, tabuladores, comas,
    el CUSIP partido en tres pedazos); lo que no cambia es el orden CUSIP, valor,
    acciones, «SH». Un CUSIP solo cuenta si su dígito verificador cuadra.
    """
    filas = []
    for m in _RE_LINEA.finditer(texto):
        cusip = re.sub(r"\s", "", m.group(1)).upper()
        if not es_cusip(cusip) or m.group(4).upper() != "SH":
            continue
        try:
            valor = float(m.group(2).replace(",", ""))
            acciones = float(m.group(3).replace(",", ""))
        except ValueError:
            continue
        filas.append((cusip, valor, acciones))
    return pd.DataFrame(filas, columns=["cusip", "valor_miles", "acciones"])


def documento_xml_tabla(texto: str) -> pd.DataFrame | None:
    """Los 13F de 2013 en adelante traen la tabla en XML; por si un texto de transición la trae."""
    if "<infoTable" not in texto and "<ns1:infoTable" not in texto:
        return None
    filas = []
    def campo(bloque: str, n: str) -> str | None:
        m = re.search(rf"<(?:\w+:)?{n}>(.*?)</(?:\w+:)?{n}>", bloque, re.S)
        return m.group(1).strip() if m else None

    for bloque in re.findall(r"<(?:\w+:)?infoTable>(.*?)</(?:\w+:)?infoTable>", texto, re.S):
        if (campo(bloque, "sshPrnamtType") or "").upper() != "SH" or campo(bloque, "putCall"):
            continue
        try:
            filas.append(((campo(bloque, "cusip") or "").upper(), float(campo(bloque, "value")),
                          float(campo(bloque, "sshPrnamt"))))
        except (TypeError, ValueError):
            continue
    return pd.DataFrame(filas, columns=["cusip", "valor_miles", "acciones"])


def combinar(estructurados: list[pd.DataFrame], texto: pd.DataFrame | None) -> pd.DataFrame:
    """Un solo precio por (CUSIP, trimestre). Un trimestre aparece en varios conjuntos (los
    13F que llegan tarde); gana la fuente con más tenedores."""
    partes = [d.assign(fuente="estructurado") for d in estructurados]
    if texto is not None and len(texto):
        partes.append(texto.assign(fuente="texto"))
    d = pd.concat(partes, ignore_index=True)
    d["fecha"] = pd.to_datetime(d["fecha"])
    d = d.sort_values("tenedores", ascending=False).drop_duplicates(["fecha", "cusip"])
    return d.sort_values(["fecha", "cusip"], ignore_index=True)


def agregar_texto(tenencias: pd.DataFrame) -> pd.DataFrame:
    """De muchas tenencias en texto (columnas cusip, valor_miles, acciones, fecha, filing) a
    una fila por (CUSIP, trimestre), con el mismo formato que los conjuntos estructurados."""
    t = tenencias[(tenencias["acciones"] >= MIN_ACCIONES) & (tenencias["valor_miles"] > 0)].copy()
    t["precio"] = t["valor_miles"] * 1000.0 / t["acciones"]
    t = t.groupby(["fecha", "cusip", "filing"], as_index=False).agg(
        acciones=("acciones", "sum"), precio=("precio", "median"))
    t["nombre"], t["clase"] = "", ""
    return _por_cusip(t)
