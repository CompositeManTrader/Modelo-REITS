"""El universo de REITs de capital que cotizan hoy: lista, precios mensuales y dividendos.

Se baja una vez con ``python scripts/estudio.py universo`` y se versiona en
``data/estudios/universo/`` con su manifiesto, como la historia de mercado de cada estudio:
una prueba en CI corre sin red y dos corridas del mismo commit dan lo mismo.

* **Lista.** El listado de Nasdaq (industria «Real Estate Investment Trusts») unido a las
  listas de REITs de stockanalysis; de cada candidato, la industria de su página en
  stockanalysis. Se quedan los «REIT - …» que no son «REIT - Mortgage», sin preferentes,
  notas ni warrants.
* **Precios.** Yahoo, el mismo proveedor del estudio largo (``mercado.descargar``): el cierre
  ajustado por splits y el ajustado por dividendos, al último día hábil de cada mes.
* **Dividendos.** Los eventos de Yahoo, ajustados por splits como el cierre.

Solo toca la red ``construir``. Los que dejaron de cotizar no están: ninguna de estas fuentes
los trae (ver ``seleccion``).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
from pathlib import Path

import pandas as pd

from src.config import DIR_ESTUDIOS, UNIVERSO_INICIAL

DIR_UNIVERSO = DIR_ESTUDIOS / "universo"
REFERENCIA = "VNQ"      # Vanguard Real Estate ETF: el índice de mercado que sí tuvo a los que desaparecieron
INDUSTRIAS_SA = ("reit-retail", "reit-diversified", "reit-industrial", "reit-office", "reit-residential",
                 "reit-healthcare-facilities", "reit-hotel-and-motel", "reit-specialty")
NO_ACCIONES = re.compile(r"preferred|depositary|notes|warrant|rights|units|%| due ", re.I)
ENCABEZADOS = {"User-Agent": "Modelo-REITS/1.0 (plataforma de valuacion de REITs)"}
ENCABEZADOS_NASDAQ = {"User-Agent": "Mozilla/5.0 (compatible; Modelo-REITS/1.0)", "Accept": "application/json"}


# --------------------------------------------------------------------------------------
# Red
# --------------------------------------------------------------------------------------


def _candidatos() -> pd.DataFrame:
    import requests

    filas = []
    r = requests.get("https://api.nasdaq.com/api/screener/stocks",
                     params={"tableonly": "true", "limit": "10000", "download": "true"},
                     headers=ENCABEZADOS_NASDAQ, timeout=60)
    r.raise_for_status()
    for x in r.json()["data"]["rows"]:
        if "Real Estate Investment Trust" in (x.get("industry") or ""):
            filas.append({"ticker": x["symbol"].strip().upper(), "nombre": x.get("name", ""), "fuente_lista": "nasdaq"})
    for industria in INDUSTRIAS_SA:
        r = requests.get(f"https://stockanalysis.com/stocks/industry/{industria}/", headers=ENCABEZADOS, timeout=30)
        if r.status_code != 200:
            continue
        for t in set(re.findall(r'/stocks/([a-z\.\-]+)/"', r.text)) - {"compare", "earnings-calendar", "industry",
                                                                         "screener"}:
            filas.append({"ticker": t.upper(), "nombre": "", "fuente_lista": "stockanalysis"})
    d = pd.DataFrame(filas)
    d = d[~d["ticker"].str.contains(r"[\^/ ]") & ~d["nombre"].fillna("").str.contains(NO_ACCIONES)]
    return (d.groupby("ticker").agg(nombre=("nombre", "max"), fuente_lista=("fuente_lista", lambda s: "+".join(sorted(set(s)))))
            .reset_index())


def _industria(ticker: str) -> tuple[str | None, str]:
    """La industria de la página del emisor en stockanalysis, y su nombre."""
    import requests

    r = requests.get(f"https://stockanalysis.com/stocks/{ticker.lower()}/company/", headers=ENCABEZADOS, timeout=30)
    if r.status_code != 200:
        return None, ""
    industrias = re.findall(r"REIT - [A-Za-z &;]+", r.text)
    nombre = re.search(r"<title>([^<(]+)", r.text)
    return (industrias[0].replace("&amp;", "&").strip() if industrias else None,
            nombre.group(1).strip() if nombre else "")


def construir_lista(pausa: float = 0.3) -> pd.DataFrame:
    """Toca la red."""
    sectores = {e.ticker: e.sector for e in UNIVERSO_INICIAL}
    c = _candidatos()
    filas = []
    for fila in c.itertuples(index=False):
        industria, nombre = _industria(fila.ticker)
        time.sleep(pausa)
        filas.append({"ticker": fila.ticker, "nombre": fila.nombre or nombre, "industria": industria or "",
                      "sector_aplicacion": sectores.get(fila.ticker, ""), "fuente_lista": fila.fuente_lista})
    d = pd.DataFrame(filas)
    d["es_reit_de_capital"] = d["industria"].str.startswith("REIT - ") & (d["industria"] != "REIT - Mortgage")
    return d.sort_values("ticker").reset_index(drop=True)


def bajar_historias(tickers: list[str], pausa: float = 0.5) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list]:
    """Toca la red: precios de fin de mes, dividendos y splits de cada ticker."""
    from src.estudio import mercado

    precios, dividendos, eventos, fallas = [], [], [], []
    for t in tickers:
        crudo = None
        for intento in range(4):
            try:
                crudo = mercado.descargar(t)
                break
            except Exception as exc:  # noqa: BLE001 — se reporta y se sigue con los demás
                # Yahoo limita la tasa (HTTP 429): se espera y se reintenta.
                if "429" in str(exc) and intento < 3:
                    time.sleep(30 * (intento + 1))
                    continue
                fallas.append((t, str(exc)[:120]))
                break
            finally:
                time.sleep(pausa)
        if crudo is None:
            continue
        p = crudo.precios.set_index("fecha")
        mes = p.index.to_period("M")
        fin = p.groupby(mes).tail(1)
        precios.append(pd.DataFrame({"ticker": t, "fecha": fin.index, "cierre": fin["cierre_proveedor"].values,
                                     "ajustado": fin["ajustado_proveedor"].values}))
        dv = crudo.dividendos.rename(columns={"monto_proveedor": "monto"})
        dividendos.append(dv.assign(ticker=t)[["ticker", "fecha_ex", "monto"]])
        for fecha, factor in crudo.eventos:
            eventos.append({"ticker": t, "fecha": pd.Timestamp(fecha), "factor": float(factor)})
    return (pd.concat(precios, ignore_index=True), pd.concat(dividendos, ignore_index=True),
            pd.DataFrame(eventos, columns=["ticker", "fecha", "factor"]), fallas)


# --------------------------------------------------------------------------------------
# Versionado
# --------------------------------------------------------------------------------------


def guardar(lista: pd.DataFrame, precios: pd.DataFrame, dividendos: pd.DataFrame, eventos: pd.DataFrame,
            fallas: list, raiz: Path | None = None) -> Path:
    destino = raiz or DIR_UNIVERSO
    destino.mkdir(parents=True, exist_ok=True)
    lista.to_csv(destino / "lista.csv", index=False)
    precios.sort_values(["ticker", "fecha"]).to_csv(destino / "precios_mensuales.csv.gz", index=False,
                                                     compression="gzip", float_format="%.6g")
    dividendos.sort_values(["ticker", "fecha_ex"]).to_csv(destino / "dividendos.csv.gz", index=False,
                                                         compression="gzip", float_format="%.6g")
    eventos.sort_values(["ticker", "fecha"]).to_csv(destino / "splits.csv", index=False)
    (destino / "manifiesto.json").write_text(json.dumps({
        "descargado_en": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "fuentes": {
            "lista": "api.nasdaq.com (screener, industria «Real Estate Investment Trusts») y stockanalysis.com "
                     "(listas por industria y página de cada emisor)",
            "precios_y_dividendos": "Yahoo Finance, chart v8 (mismo proveedor que el estudio largo)",
        },
        "candidatos": int(len(lista)),
        "reits_de_capital": int(lista["es_reit_de_capital"].sum()),
        "con_precios": int(precios["ticker"].nunique()),
        "fallas": [{"ticker": t, "motivo": m} for t, m in fallas],
        "referencia": REFERENCIA,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def cargar(raiz: Path | None = None) -> dict[str, pd.DataFrame]:
    d = raiz or DIR_UNIVERSO
    if not (d / "lista.csv").exists():
        return {}
    return {
        "lista": pd.read_csv(d / "lista.csv", keep_default_na=False),
        "precios": pd.read_csv(d / "precios_mensuales.csv.gz", parse_dates=["fecha"]),
        "dividendos": pd.read_csv(d / "dividendos.csv.gz", parse_dates=["fecha_ex"]),
        "splits": pd.read_csv(d / "splits.csv", parse_dates=["fecha"]),
    }


def hay_universo(raiz: Path | None = None) -> bool:
    return ((raiz or DIR_UNIVERSO) / "lista.csv").exists()


def completar(pausa: float = 2.0, raiz: Path | None = None) -> list:
    """Toca la red: baja lo que falló la vez anterior y lo agrega a lo versionado."""
    destino = raiz or DIR_UNIVERSO
    u = cargar(destino)
    manifiesto = json.loads((destino / "manifiesto.json").read_text(encoding="utf-8"))
    faltan = [f["ticker"] for f in manifiesto.get("fallas", [])]
    if not faltan:
        return []
    p, d, s, fallas = bajar_historias(faltan, pausa=pausa)
    guardar(u["lista"], pd.concat([u["precios"], p], ignore_index=True),
            pd.concat([u["dividendos"], d], ignore_index=True),
            pd.concat([u["splits"], s], ignore_index=True), fallas, destino)
    return fallas
