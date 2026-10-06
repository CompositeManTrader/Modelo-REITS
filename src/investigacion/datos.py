"""Los datos de la investigación (fase 2): bajarlos, validarlos y versionarlos.

Todo queda en ``data/investigacion/`` con su manifiesto, como los estudios anteriores: una
prueba corre sin red y dos corridas del mismo commit dan lo mismo. Solo tocan la red las
funciones ``bajar_*``.

* **Sector, sin sesgo de supervivencia.** La serie FTSE Nareit de Nareit, mensual desde
  diciembre de 1971: retorno total, de precio y de ingreso, y yield de dividendo, de seis
  índices (todos los REITs, el compuesto, Real Estate 50, All Equity REITs, Equity REITs
  e hipotecarios). Los índices tuvieron a los REITs que quebraron o fueron comprados
  mientras existieron. La página de Nareit pide un navegador real, así que se baja con
  Chromium; el almacén de certificados del navegador necesita las autoridades del
  sistema (``scripts/investigacion.py`` explica cómo).
* **Fondos para validar el índice**, de Yahoo: Cohen & Steers Realty Shares (CSRSX, desde
  1991), Vanguard REIT Index (VGSIX, 1996), Fidelity Real Estate (FRESX), VNQ (2004) e
  IYR (2000). Si el índice y los fondos no se mueven juntos, uno de los dos está mal.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import DIR_DATOS

DIR_INVESTIGACION = DIR_DATOS / "investigacion"
DIR_SECTOR = DIR_INVESTIGACION / "sector"

URL_NAREIT_PAGINA = "https://www.reit.com/data-research/reit-indexes/monthly-index-values-returns"
URL_NAREIT_HISTORICO = "https://www.reit.com/sites/default/files/returns/MonthlyHistoricalReturns.xls"

# El orden de los bloques del archivo de Nareit, de izquierda a derecha, y cómo se llaman aquí.
INDICES_NAREIT = {
    "All REITs": "todos",
    "Composite": "compuesto",
    "Real Estate 50TM": "real_estate_50",
    "All Equity REITs": "all_equity",
    "Equity REITs": "equity",
    "Mortgage REITs": "hipotecarios",
}
CAMPOS_NAREIT = ("retorno_total", "indice_total", "retorno_precio", "indice_precio", "retorno_ingreso",
                 "yield_dividendo")
FONDOS = ("CSRSX", "VGSIX", "FRESX", "VNQ", "IYR")


class ErrorDeDatos(RuntimeError):
    pass


# --------------------------------------------------------------------------------------
# Nareit
# --------------------------------------------------------------------------------------


def leer_nareit(ruta: Path) -> pd.DataFrame:
    """El archivo histórico de Nareit, en formato largo: un renglón por índice y mes.

    Los retornos y el yield vienen en porcentaje en el archivo; aquí van como fracción. La
    fecha es el fin de mes.
    """
    import xlrd

    hoja = xlrd.open_workbook(str(ruta)).sheet_by_name("Index Data")
    if "percent" not in str(hoja.cell_value(3, 0)).lower():
        raise ErrorDeDatos("El archivo de Nareit ya no dice que viene en porcentaje: revisar las unidades.")
    # Los bloques empiezan donde el renglón 6 trae el nombre del índice.
    inicios = {str(hoja.cell_value(5, c)).strip(): c for c in range(hoja.ncols) if str(hoja.cell_value(5, c)).strip()}
    faltan = set(INDICES_NAREIT) - set(inicios)
    if faltan:
        raise ErrorDeDatos(f"El archivo de Nareit cambió de forma: faltan los bloques {sorted(faltan)}")
    filas = []
    for r in range(8, hoja.nrows):
        serial = hoja.cell_value(r, 0)
        if not isinstance(serial, float):
            continue
        fecha = pd.Timestamp(xlrd.xldate_as_datetime(serial, 0)) + pd.offsets.MonthEnd(0)
        for nombre, clave in INDICES_NAREIT.items():
            c0 = inicios[nombre]
            valores = []
            for k in range(len(CAMPOS_NAREIT)):
                v = hoja.cell_value(r, c0 + k) if c0 + k < hoja.ncols else ""
                valores.append(float(v) if isinstance(v, float) else np.nan)
            if all(np.isnan(valores)):
                continue
            fila = dict(zip(CAMPOS_NAREIT, valores, strict=True))
            for campo in ("retorno_total", "retorno_precio", "retorno_ingreso", "yield_dividendo"):
                fila[campo] = fila[campo] / 100
            filas.append({"fecha": fecha, "indice": clave, **fila})
    d = pd.DataFrame(filas).sort_values(["indice", "fecha"]).reset_index(drop=True)
    if d.empty:
        raise ErrorDeDatos("El archivo de Nareit no trajo ningún mes.")
    return d


def revisar_nareit(d: pd.DataFrame) -> dict:
    """Coherencia interna de cada índice. Devuelve, por índice, el peor error de cada revisión.

    * El índice total es el producto acumulado del retorno total (y el de precio, igual).
    * El retorno total es el de precio más el de ingreso.
    * El yield de dividendo está entre 0% y 30%, y no hay meses faltantes en medio.
    """
    salida = {}
    for clave, x in d.groupby("indice"):
        x = x.set_index("fecha").sort_index()
        meses = pd.date_range(x.index.min(), x.index.max(), freq="ME")
        r = {}
        for tipo in ("total", "precio"):
            ret = x[f"retorno_{tipo}"]
            idx = x[f"indice_{tipo}"]
            implicito = idx.shift(1) * (1 + ret)
            r[f"indice_{tipo}"] = float((implicito / idx - 1).abs().max())
        r["suma"] = float((x["retorno_total"] - x["retorno_precio"] - x["retorno_ingreso"]).abs().max())
        y = x["yield_dividendo"].dropna()
        r["yield_fuera_de_rango"] = int(((y < 0) | (y > 0.30)).sum())
        r["meses_faltantes"] = int(len(meses.difference(x.index)))
        r["desde"] = f"{x.index.min():%Y-%m}"
        r["hasta"] = f"{x.index.max():%Y-%m}"
        salida[clave] = r
    return salida


def bajar_nareit(destino: Path) -> Path:
    """Toca la red: baja el archivo histórico de Nareit con Chromium (la página pide JavaScript)."""
    from playwright.sync_api import sync_playwright

    destino.parent.mkdir(parents=True, exist_ok=True)
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    navegador = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=navegador if Path(navegador).exists() else None,
                              proxy={"server": proxy} if proxy else None)
        ctx = b.new_context(accept_downloads=True, user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"))
        pagina = ctx.new_page()
        pagina.goto(URL_NAREIT_PAGINA, timeout=120_000)
        pagina.wait_for_timeout(10_000)
        with pagina.expect_download(timeout=120_000) as descarga:
            pagina.evaluate(f"location.href='{URL_NAREIT_HISTORICO}'")
        descarga.value.save_as(str(destino))
        b.close()
    return destino


# --------------------------------------------------------------------------------------
# Fondos y series de Yahoo, a fin de mes
# --------------------------------------------------------------------------------------


def retornos_mensuales(precios: pd.DataFrame, hoy: pd.Timestamp | None = None) -> pd.DataFrame:
    """De los cierres de fin de mes de ``universo.bajar_historias``: retorno total y de precio.

    El mes en curso no ha cerrado: su «cierre» es el de hoy y no entra.
    """
    p = precios.copy()
    p["fecha"] = p["fecha"] + pd.offsets.MonthEnd(0)
    p = p[p["fecha"] <= (hoy or pd.Timestamp.today()).normalize()]
    p = p.drop_duplicates(["ticker", "fecha"], keep="last").sort_values(["ticker", "fecha"])
    p["retorno_total"] = p.groupby("ticker")["ajustado"].pct_change()
    p["retorno_precio"] = p.groupby("ticker")["cierre"].pct_change()
    # Un mes faltante en medio no es un retorno de un mes.
    hueco = p.groupby("ticker")["fecha"].diff() > pd.Timedelta(days=32)
    p.loc[hueco, ["retorno_total", "retorno_precio"]] = np.nan
    return p[["ticker", "fecha", "cierre", "ajustado", "retorno_total", "retorno_precio"]].reset_index(drop=True)


def validar_contra_fondos(nareit: pd.DataFrame, fondos: pd.DataFrame, indice: str = "all_equity") -> pd.DataFrame:
    """Qué tanto se mueven juntos el índice y cada fondo, en los meses que comparten.

    Un fondo cobra comisiones y no replica exacto (salvo los indexados), así que se reporta
    la correlación, el retorno anual de cada uno y la diferencia; la validación pide que
    la correlación sea alta, no que coincidan.
    """
    idx = nareit[nareit["indice"] == indice].set_index("fecha")["retorno_total"]
    filas = []
    for t, f in fondos.groupby("ticker"):
        r = f.set_index("fecha")["retorno_total"].dropna()
        comun = r.index.intersection(idx.dropna().index)
        if len(comun) < 24:
            continue
        a, b = idx[comun], r[comun]
        anual = lambda s: float((1 + s).prod() ** (12 / len(s)) - 1)  # noqa: E731
        filas.append({"fondo": t, "desde": comun.min(), "hasta": comun.max(), "meses": len(comun),
                      "correlacion": float(np.corrcoef(a, b)[0, 1]), "rendimiento_indice": anual(a),
                      "rendimiento_fondo": anual(b), "diferencia_anual": anual(b) - anual(a),
                      "error_de_seguimiento": float((b - a).std() * np.sqrt(12))})
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# Versionado
# --------------------------------------------------------------------------------------


def _escribir(d: pd.DataFrame, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(ruta, index=False, compression={"method": "gzip", "mtime": 0}, float_format="%.10g")


def guardar_sector(nareit: pd.DataFrame, fondos: pd.DataFrame, *, revision: dict, validacion: pd.DataFrame,
                   raiz: Path | None = None) -> Path:
    destino = raiz or DIR_SECTOR
    _escribir(nareit, destino / "nareit_mensual.csv.gz")
    _escribir(fondos, destino / "fondos_mensual.csv.gz")
    (destino / "manifiesto.json").write_text(json.dumps({
        "descargado_en": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "fuentes": {
            "nareit": f"FTSE Nareit U.S. Real Estate Index Series, {URL_NAREIT_HISTORICO}",
            "fondos": "Yahoo Finance, chart v8: cierre y cierre ajustado de fin de mes",
        },
        "indices": sorted(nareit["indice"].unique()),
        "fondos": sorted(fondos["ticker"].unique()),
        "coherencia_interna": revision,
        "contra_fondos": json.loads(validacion.to_json(orient="records", date_format="iso")),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def cargar_sector(raiz: Path | None = None) -> dict[str, pd.DataFrame]:
    d = raiz or DIR_SECTOR
    if not (d / "nareit_mensual.csv.gz").exists():
        return {}
    return {"nareit": pd.read_csv(d / "nareit_mensual.csv.gz", parse_dates=["fecha"]),
            "fondos": pd.read_csv(d / "fondos_mensual.csv.gz", parse_dates=["fecha"])}


# --------------------------------------------------------------------------------------
# Macro: FRED
# --------------------------------------------------------------------------------------

DIR_MACRO = DIR_INVESTIGACION / "macro"

# id de FRED: (qué es, días después del fin del periodo en que se conoce, si se revisa).
# El rezago hace la serie point-in-time (P1). Las revisadas se usan con el dato de hoy:
# FRED no guarda aquí la primera versión (para eso está ALFRED), y se declara.
SERIES_FRED: dict[str, tuple[str, int, bool]] = {
    "DGS10": ("Treasury a 10 años, diario", 1, False),
    "GS10": ("Treasury a 10 años, promedio mensual", 1, False),
    "DGS2": ("Treasury a 2 años, diario", 1, False),
    "GS1": ("Treasury a 1 año, promedio mensual", 1, False),
    "DTB3": ("T-bill a 3 meses, diario", 1, False),
    "TB3MS": ("T-bill a 3 meses, promedio mensual", 1, False),
    "DFII10": ("Treasury a 10 años indexado a inflación (TIPS), diario", 1, False),
    "T10YIE": ("Inflación implícita a 10 años, diario", 1, False),
    "BAA": ("Bonos corporativos Baa de Moody's, promedio mensual", 1, False),
    "AAA": ("Bonos corporativos Aaa de Moody's, promedio mensual", 1, False),
    "FEDFUNDS": ("Tasa de fondos federales, promedio mensual", 1, False),
    "MORTGAGE30US": ("Hipoteca a 30 años, semanal", 1, False),
    "CPIAUCSL": ("Índice de precios al consumidor", 45, True),
    "CPILFESL": ("Índice de precios al consumidor, subyacente", 45, True),
    "UNRATE": ("Tasa de desempleo", 10, True),
    "PAYEMS": ("Empleo no agrícola", 10, True),
    "INDPRO": ("Producción industrial", 20, True),
    "UMCSENT": ("Confianza del consumidor (Universidad de Michigan)", 1, True),
    "NFCI": ("Índice de condiciones financieras de la Fed de Chicago, semanal", 7, True),
    "VIXCLS": ("VIX, diario", 1, False),
    "CSUSHPINSA": ("Precios de casas Case-Shiller", 60, True),
    "COMREPUSQ159N": ("Precios de inmuebles comerciales (BIS), trimestral", 90, True),
    "RRVRUSQ156N": ("Vacancia de vivienda en renta, trimestral", 30, True),
    # Encuesta de la Fed a los bancos (SLOOS), trimestral. La serie agregada de inmuebles
    # comerciales se descontinuó en 2013 y se partió en tres; se empalman en la fase 3.
    "DRTSCREL": ("Bancos que endurecen el crédito a inmuebles comerciales (SLOOS), 1990-2013", 40, False),
    "SUBLPDRCSC": ("Bancos que endurecen el crédito a construcción y terrenos (SLOOS), desde 2013", 40, False),
    "SUBLPDRCSN": ("Bancos que endurecen el crédito a inmuebles no residenciales (SLOOS), desde 2013", 40, False),
    "SUBLPDRCSM": ("Bancos que endurecen el crédito multifamiliar (SLOOS), desde 2013", 40, False),
    # Solo para describir: el NBER anuncia las recesiones con meses o años de retraso, así
    # que nunca puede ser una señal.
    "USREC": ("Recesiones del NBER (solo descriptivo, nunca señal)", 365, True),
}


def bajar_fred(series: dict[str, tuple[str, int, bool]] | None = None) -> tuple[pd.DataFrame, list]:
    """Toca la red. Formato largo: serie, fecha, valor."""
    from src.ingesta.tasas import descargar_fred

    partes, fallas = [], []
    for sid in (series or SERIES_FRED):
        try:
            d = descargar_fred(sid, timeout=60).rename(columns={"fecha_dato": "fecha"})
        except Exception as exc:  # noqa: BLE001 — se anota y se sigue con las demás
            fallas.append((sid, str(exc)[:120]))
            continue
        partes.append(d.assign(serie=sid)[["serie", "fecha", "valor"]])
    x = pd.concat(partes, ignore_index=True)
    x["fecha"] = pd.to_datetime(x["fecha"])
    return x, fallas


def guardar_macro(x: pd.DataFrame, fallas: list, raiz: Path | None = None) -> Path:
    destino = raiz or DIR_MACRO
    _escribir(x, destino / "fred.csv.gz")
    resumen = x.groupby("serie")["fecha"].agg(["min", "max", "count"])
    (destino / "manifiesto.json").write_text(json.dumps({
        "descargado_en": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "fuente": "FRED, Federal Reserve Bank of St. Louis (fredgraph.csv)",
        "series": {s: {"descripcion": SERIES_FRED[s][0], "rezago_dias": SERIES_FRED[s][1],
                       "se_revisa": SERIES_FRED[s][2], "desde": f"{resumen.loc[s, 'min']:%Y-%m-%d}",
                       "hasta": f"{resumen.loc[s, 'max']:%Y-%m-%d}", "datos": int(resumen.loc[s, "count"])}
                   for s in resumen.index},
        "fallas": [{"serie": s, "motivo": m} for s, m in fallas],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def cargar_macro(raiz: Path | None = None) -> pd.DataFrame:
    d = raiz or DIR_MACRO
    if not (d / "fred.csv.gz").exists():
        return pd.DataFrame(columns=["serie", "fecha", "valor"])
    return pd.read_csv(d / "fred.csv.gz", parse_dates=["fecha"])


def conocida_en(x: pd.DataFrame, serie: str, fechas: pd.DatetimeIndex) -> pd.Series:
    """El último valor de la serie que ya se conocía en cada fecha (P1).

    La fecha de FRED es el inicio del periodo para las mensuales y trimestrales: el dato de
    marzo se conoce el fin de marzo más el rezago de publicación.
    """
    descripcion, rezago, _ = SERIES_FRED[serie]
    s = x[x["serie"] == serie].set_index("fecha")["valor"].sort_index()
    if s.empty:
        return pd.Series(np.nan, index=fechas)
    paso = pd.infer_freq(s.index[-24:]) if len(s) > 24 else None
    if paso and paso.startswith(("M", "Q")):
        fin = s.index + (pd.offsets.MonthEnd(0) if paso.startswith("M") else pd.offsets.QuarterEnd(0))
    else:
        fin = s.index
    conocido = pd.Series(s.to_numpy(), index=fin + pd.Timedelta(days=rezago)).sort_index()
    conocido = conocido[~conocido.index.duplicated(keep="last")]
    return conocido.reindex(conocido.index.union(fechas)).ffill().reindex(fechas)


# --------------------------------------------------------------------------------------
# Factores conocidos (Kenneth French) y valuación del mercado (Shiller)
# --------------------------------------------------------------------------------------

DIR_FACTORES = DIR_INVESTIGACION / "factores"
URL_FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{archivo}_CSV.zip"
ARCHIVOS_FRENCH = {
    "F-F_Research_Data_Factors": "mercado, tamaño, valor y tasa libre de riesgo (desde 1926)",
    "F-F_Momentum_Factor": "momentum (desde 1927)",
    "F-F_Research_Data_5_Factors_2x3": "cinco factores: agrega rentabilidad e inversión (desde 1963)",
}
URL_SHILLER = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
ENCABEZADOS_WEB = {"User-Agent": "Mozilla/5.0 (compatible; Modelo-REITS/1.0)"}


def leer_french(contenido: bytes) -> pd.DataFrame:
    """La sección mensual de un archivo de French, en fracción. Formato largo: factor, fecha, valor."""
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        texto = z.read(z.namelist()[0]).decode("latin-1")
    filas, encabezado = [], None
    for linea in texto.splitlines():
        partes = [p.strip() for p in linea.split(",")]
        if encabezado is None and len(partes) > 1 and partes[0] == "" and partes[1]:
            encabezado = partes[1:]
            continue
        if encabezado is not None and partes[0].isdigit() and len(partes[0]) == 6:
            fecha = pd.Timestamp(f"{partes[0][:4]}-{partes[0][4:]}-01") + pd.offsets.MonthEnd(0)
            for nombre, v in zip(encabezado, partes[1:], strict=False):
                filas.append({"factor": nombre, "fecha": fecha, "valor": float(v) / 100})
        elif encabezado is not None and filas and not partes[0]:
            break   # termina la sección mensual; sigue la anual
    if not filas:
        raise ErrorDeDatos("El archivo de French no trajo la sección mensual.")
    return pd.DataFrame(filas)


def bajar_french() -> pd.DataFrame:
    """Toca la red."""
    import requests

    partes = []
    for archivo in ARCHIVOS_FRENCH:
        r = requests.get(URL_FRENCH.format(archivo=archivo), headers=ENCABEZADOS_WEB, timeout=120)
        r.raise_for_status()
        partes.append(leer_french(r.content).assign(archivo=archivo))
    x = pd.concat(partes, ignore_index=True)
    # Mercado, tamaño, valor y RF vienen en dos archivos; se queda el de tres factores.
    return x.drop_duplicates(["factor", "fecha"], keep="first").reset_index(drop=True)


def leer_shiller(contenido: bytes) -> pd.DataFrame:
    """La hoja «Data» de Shiller: precio, dividendo y utilidad del S&P, CPI, tasa y CAPE."""
    import io

    crudo = pd.read_excel(io.BytesIO(contenido), sheet_name="Data", header=None, engine="xlrd")
    fila = next(i for i in range(20) if str(crudo.iloc[i, 0]).strip() == "Date")
    nombres = [str(c).strip() for c in crudo.iloc[fila]]
    d = crudo.iloc[fila + 1:].copy()
    d.columns = nombres
    d = d[pd.to_numeric(d["Date"], errors="coerce").notna()]
    fecha = pd.to_numeric(d["Date"])
    anio = fecha.astype(int)
    mes = ((fecha - anio) * 100).round().astype(int)
    salida = pd.DataFrame({"fecha": pd.to_datetime({"year": anio, "month": mes, "day": 1}) + pd.offsets.MonthEnd(0)})
    for origen, destino in (("P", "precio"), ("D", "dividendo"), ("E", "utilidad"), ("CPI", "cpi"),
                            ("Rate GS10", "tasa_10a"), ("CAPE", "cape")):
        if origen in d.columns:
            salida[destino] = pd.to_numeric(d[origen], errors="coerce").to_numpy()
    return salida.dropna(subset=["precio"]).reset_index(drop=True)


def bajar_shiller() -> pd.DataFrame:
    """Toca la red."""
    import requests

    r = requests.get(URL_SHILLER, headers=ENCABEZADOS_WEB, timeout=120)
    r.raise_for_status()
    return leer_shiller(r.content)


def guardar_factores(french: pd.DataFrame, shiller: pd.DataFrame, raiz: Path | None = None) -> Path:
    destino = raiz or DIR_FACTORES
    _escribir(french, destino / "french.csv.gz")
    _escribir(shiller, destino / "shiller.csv.gz")
    (destino / "manifiesto.json").write_text(json.dumps({
        "descargado_en": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "fuentes": {"french": "Kenneth R. French Data Library: " + "; ".join(f"{k} ({v})" for k, v in
                                                                              ARCHIVOS_FRENCH.items()),
                    "shiller": URL_SHILLER},
        "factores": sorted(french["factor"].unique()),
        "french_desde": f"{french['fecha'].min():%Y-%m}", "french_hasta": f"{french['fecha'].max():%Y-%m}",
        "shiller_desde": f"{shiller['fecha'].min():%Y-%m}", "shiller_hasta": f"{shiller['fecha'].max():%Y-%m}",
        "nota": "Los datos de Shiller de los meses recientes son preliminares: él los revisa.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def cargar_factores(raiz: Path | None = None) -> dict[str, pd.DataFrame]:
    d = raiz or DIR_FACTORES
    if not (d / "french.csv.gz").exists():
        return {}
    return {"french": pd.read_csv(d / "french.csv.gz", parse_dates=["fecha"]),
            "shiller": pd.read_csv(d / "shiller.csv.gz", parse_dates=["fecha"])}


# --------------------------------------------------------------------------------------
# Mercados de la prueba final: se bajan, se sellan y no se miran
# --------------------------------------------------------------------------------------

# Escogidos por cuánta historia tienen, no por lo que rindieron (no se miró). La serie
# principal de cada mercado es el ETF del índice local; donde no hay uno anterior a 2010,
# la canasta de pesos iguales de los REITs listados (con sesgo de supervivencia: son los
# que cotizan hoy). La fase 4 fija cuál se usa en cada prueba.
MERCADOS_FINALES: dict[str, dict] = {
    "japon": {"etf": ["1343.T", "1345.T"], "canasta": ["8951.T", "8952.T", "8953.T", "8954.T", "8955.T",
                                                       "8956.T", "8957.T", "8958.T", "8960.T", "8961.T"],
              "tasa_corta": "IR3TIB01JPM156N", "tasa_larga": "IRLTLT01JPM156N"},
    "australia": {"etf": ["SLF.AX", "^AXPJ", "VAP.AX"],
                  "canasta": ["GMG.AX", "SCG.AX", "SGP.AX", "GPT.AX", "MGR.AX", "VCX.AX", "CHC.AX", "DXS.AX",
                              "CQR.AX", "BWP.AX", "CLW.AX", "ABP.AX"],
                  "tasa_corta": "IR3TIB01AUM156N", "tasa_larga": "IRLTLT01AUM156N"},
    "singapur": {"etf": ["CLR.SI"], "canasta": ["C38U.SI", "A17U.SI", "M44U.SI", "N2IU.SI", "ME8U.SI", "K71U.SI",
                                                 "T82U.SI", "J69U.SI", "BUOU.SI", "AJBU.SI"],
                 # Sin tasas locales en FRED: se usa la de EE. UU. (declarado en la fase 0).
                 "tasa_corta": "TB3MS", "tasa_larga": "GS10"},
    "hong_kong": {"etf": [], "canasta": ["0823.HK", "0778.HK", "0405.HK", "2778.HK", "0435.HK", "0808.HK", "1881.HK"],
                  # El dólar de Hong Kong está atado al de EE. UU.: su tasa es la referencia natural.
                  "tasa_corta": "TB3MS", "tasa_larga": "GS10"},
    "reino_unido": {"etf": ["IUKP.L"], "canasta": ["BLND.L", "LAND.L", "SGRO.L", "BBOX.L", "DLN.L", "GPE.L",
                                                   "BYG.L", "SAFE.L", "UTG.L", "LMP.L", "HMSO.L"],
                    "tasa_corta": "IR3TIB01GBM156N", "tasa_larga": "IRLTLT01GBM156N"},
    "europa_continental": {"etf": ["IPRP.AS", "IQQ6.DE"],
                           "canasta": ["LI.PA", "GFC.PA", "COV.PA", "URW.PA", "ICAD.PA", "MRL.MC", "WDP.BR",
                                       "COFB.BR", "AED.BR", "ECMPA.AS", "WHA.AS"],
                           "tasa_corta": "IR3TIB01EZM156N", "tasa_larga": "IRLTLT01EZM156N"},
    "canada": {"etf": ["XRE.TO", "ZRE.TO"],
               "canasta": ["REI-UN.TO", "CAR-UN.TO", "HR-UN.TO", "AP-UN.TO", "GRT-UN.TO", "CHP-UN.TO", "SRU-UN.TO",
                           "IIP-UN.TO", "DIR-UN.TO", "CRT-UN.TO"],
               "tasa_corta": "IR3TIB01CAM156N", "tasa_larga": "IRLTLT01CAM156N"},
    "mexico_fibras": {"etf": [], "canasta": ["FUNO11.MX", "FIBRAPL14.MX", "FMTY14.MX", "DANHOS13.MX",
                                             "FIBRAMQ12.MX", "FIHO12.MX", "FINN13.MX", "FSHOP13.MX", "FNOVA17.MX",
                                             "FIBRAHD15.MX", "FPLUS16.MX", "TERRA13.MX"],
                      "tasa_corta": "IR3TIB01MXM156N", "tasa_larga": "IRLTLT01MXM156N"},
}


def sellar_mercados(*, raiz: Path | None = None) -> dict:
    """Toca la red. Baja cada mercado y lo sella sin mostrar cifras; devuelve solo conteos."""
    from src.estudio import universo
    from src.investigacion import muestras

    resumen = {}
    for mercado, spec in MERCADOS_FINALES.items():
        tickers = spec["etf"] + spec["canasta"]
        precios, dividendos, splits, fallas = universo.bajar_historias(tickers, pausa=1.0)
        tasas, fallas_tasas = bajar_fred(dict.fromkeys((spec["tasa_corta"], spec["tasa_larga"]), ("tasa local", 1, False)))
        fuente = "Yahoo Finance chart v8 (precios y dividendos) y FRED/OCDE (tasas)"
        muestras.sellar(precios.assign(tipo=precios["ticker"].map(
            lambda t, s=spec: "etf" if t in s["etf"] else "canasta")), f"{mercado}_precios", raiz=raiz, fuente=fuente)
        muestras.sellar(dividendos, f"{mercado}_dividendos", raiz=raiz, fuente=fuente)
        muestras.sellar(splits, f"{mercado}_splits", raiz=raiz, fuente=fuente)
        muestras.sellar(tasas, f"{mercado}_tasas", raiz=raiz, fuente=fuente)
        resumen[mercado] = {"tickers_con_datos": int(precios["ticker"].nunique()) if len(precios) else 0,
                            "fallas": [t for t, _ in fallas] + [s for s, _ in fallas_tasas]}
    return resumen
