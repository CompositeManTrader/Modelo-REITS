"""Fase 6: el panel trimestral de REITs de EE. UU., vivos y muertos, sin sesgo de supervivencia.

Junta lo que bajan ``sec``, ``trece_f`` y ``fundamentales``:

* **Precio** de cada emisor al cierre de cada trimestre: el de su CUSIP con más tenedores
  en los 13F (los CUSIP del emisor salen de los 13G; los que comparten sus seis primeros
  caracteres son el mismo emisor después de un split inverso o un cambio de clase).
* **Splits**: los 13F no ajustan. Un split se reconoce porque el precio y las acciones
  que reportan los administradores se mueven en sentidos opuestos por la misma razón.
* **Retorno total trimestral**: precio más el dividendo por acción del trimestre (XBRL),
  entre el precio anterior.
* **Salida**: el trimestre en que el emisor deja de aparecer, su retorno es 0% si lo
  compraron y el de una quiebra si presentó un 8-K de quiebra (punto 1.03).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import DIR_DATOS
from src.investigacion.datos import DIR_INVESTIGACION
from src.investigacion.muestras import esta_sellado

RAZONES_DE_SPLIT = np.array([1 / 20, 1 / 15, 1 / 12, 1 / 10, 1 / 8, 1 / 6, 1 / 5, 1 / 4, 1 / 3, 1 / 2, 2 / 3, 3 / 2,
                             2, 3, 4, 5, 10])
CAMBIO_MINIMO_DE_SPLIT = 1.6     # el precio se movió al menos 60% (o 1/1.6) en el trimestre...
DESCUADRE_MAXIMO_DE_SPLIT = 1.3  # ...y las acciones de los 13F lo compensaron con a lo más 30% de error
RETORNO_MAXIMO_CREIBLE = 2.0     # +200% en un trimestre sin split detectado: error, no dato


def identificador(cik: str, tickers: str | float) -> str:
    """Con qué se decide si un emisor está sellado: su ticker si cotiza hoy; si no, su CIK."""
    t = str(tickers).split("|")[0].strip() if isinstance(tickers, str) and tickers else ""
    return t.upper() if t else f"CIK{str(cik).zfill(10)}"


def sellado(cik: str, tickers: str | float) -> bool:
    return esta_sellado(identificador(cik, tickers))


def asignar_cusips(resumen: pd.DataFrame) -> pd.DataFrame:
    """Cada CUSIP a un solo emisor: al que más 13G lo citan. Columnas cik, cusip, citas."""
    filas = []
    for r in resumen.itertuples():
        try:
            c = json.loads(r.cusips) if isinstance(r.cusips, str) else {}
        except json.JSONDecodeError:
            c = {}
        for cusip, (_, _, n) in c.items():
            filas.append((r.cik, cusip, n))
    d = pd.DataFrame(filas, columns=["cik", "cusip", "citas"])
    d = d.sort_values("citas", ascending=False).drop_duplicates("cusip")
    return d.reset_index(drop=True)


GENERICAS = frozenset("""
INC CORP CORPORATION CO COMPANY TRUST TR REIT REITS REALTY RLTY PROPERTIES PROPERTY PPTYS PPTY PROP PROPS GROUP GRP
HOLDINGS HLDGS HOLDING HLDG THE OF AND AMERICA AMERICAN AMERN AMER INVESTMENT INVESTMENTS INVT INVTS INVS CAPITAL CAP
REAL ESTATE EST NEW COM FUND INCOME LP LTD SHS BEN INT CL CLASS COMMON STOCK PARTNERS PARTNERSHIP OPERATING NATIONAL
NATL USA FIRST GLOBAL INTERNATIONAL INTL DEL MD MARYLAND COS CORPORATE ENTERPRISES ENTERPRISE
""".split())  # noqa: SIM905 - una lista de palabras se lee mejor así
DISPERSION_MAXIMA = 0.10    # (p75 − p25) / precio: más que eso, los administradores no reportan el mismo precio


def fichas(nombre: str) -> set[str]:
    """Las palabras que distinguen un nombre de emisor (sin «Inc», «Realty», «Trust»...)."""
    limpio = "".join(ch if ch.isalnum() else " " for ch in str(nombre).upper())
    return {p for p in limpio.split() if len(p) >= 3 and p not in GENERICAS}


def precios(agregado: pd.DataFrame, cusips: pd.DataFrame, nombres: dict[str, set[str]] | None = None, *,
            min_tenedores: int = 3) -> pd.DataFrame:
    """El precio de cada emisor en cada trimestre: su CUSIP con más tenedores.

    Se buscan los CUSIP del emisor y los que comparten con ellos los seis primeros
    caracteres (mismo emisor, otra emisión), siempre que esa raíz sea de un solo emisor.
    Con ``nombres`` (las palabras distintivas de los nombres actual y anteriores de cada
    emisor), una raíz cuenta solo si en los 13F con nombre alguna vez se llamó parecido: un
    13D que el propio REIT presenta sobre otra empresa (Vornado sobre J. C. Penney) trae el
    CUSIP de la otra.
    """
    raiz = cusips.assign(r6=cusips["cusip"].str[:6]).groupby(["r6", "cik"], as_index=False)["citas"].sum()
    # Solo acciones: en los bonos y pagarés la emisión (caracteres 7 y 8) lleva letras.
    a = agregado[agregado["cusip"].str[6:8].str.isdigit()]
    a = a.assign(r6=a["cusip"].str[:6]).merge(raiz, on="r6")
    if nombres is not None:
        con_nombre = a[a["nombre"].fillna("").str.len() > 0]
        cuadra = [bool(fichas(n) & nombres.get(c, set())) for n, c in zip(con_nombre["nombre"], con_nombre["cik"], strict=True)]
        buenas = set(zip(con_nombre.loc[cuadra, "cik"], con_nombre.loc[cuadra, "r6"], strict=True))
        vistas = set(zip(con_nombre["cik"], con_nombre["r6"], strict=True))
        par = list(zip(a["cik"], a["r6"], strict=True))
        a = a[[p in buenas or p not in vistas for p in par]]
    # Una raíz que todavía queda en dos emisores es del que más 13G la citan.
    duenio = a.drop_duplicates(["r6", "cik"]).sort_values("citas", ascending=False).drop_duplicates("r6")
    a = a.merge(duenio[["r6", "cik"]], on=["r6", "cik"])
    dispersion = (a["p75"] - a["p25"]) / a["precio"]
    a = a[(a["tenedores"] >= min_tenedores) & (dispersion <= DISPERSION_MAXIMA)]
    # Si el CUSIP exacto de un 13G está, gana; si no, el de la misma raíz con más tenedores.
    exacto = a["cusip"].isin(set(cusips["cusip"]))
    a = a.assign(exacto=exacto).sort_values(["cik", "fecha", "tenedores", "exacto"], ascending=[True, True, False, False])
    p = a.drop_duplicates(["cik", "fecha"])
    return p[["cik", "fecha", "cusip", "precio", "tenedores", "acciones_13f", "p25", "p75", "nombre", "clase"]] \
        .reset_index(drop=True)


def _razon_cercana(x: float, tolerancia: float) -> float | None:
    i = int(np.argmin(np.abs(np.log(RAZONES_DE_SPLIT) - np.log(x))))
    r = RAZONES_DE_SPLIT[i]
    return float(r) if abs(np.log(r / x)) < np.log(tolerancia) else None


def splits(p: pd.DataFrame) -> pd.DataFrame:
    """Los splits que delatan los 13F: columnas cik, fecha, factor (acciones nuevas por vieja).

    Dos evidencias, cualquiera basta: (a) el precio se movió al menos 60% y las acciones que
    reportan los administradores lo compensaron (el producto queda a menos de 30% de 1); la
    razón puede alejarse hasta 35% de una redonda porque el mercado también se movió; o (b)
    el CUSIP cambió en el trimestre (los splits inversos casi siempre cambian el CUSIP) y el
    precio se movió por una razón redonda, a menos de 10%. La (b) atrapa el split inverso que
    coincide con una fusión, cuando las acciones no compensan.
    """
    filas = []
    for cik, g in p.sort_values("fecha").groupby("cik"):
        g = g.reset_index(drop=True)
        for i in range(1, len(g)):
            rp = g["precio"].iat[i] / g["precio"].iat[i - 1]
            if abs(np.log(rp)) < np.log(CAMBIO_MINIMO_DE_SPLIT):
                continue
            ra = g["acciones_13f"].iat[i] / g["acciones_13f"].iat[i - 1]
            factor = None
            if abs(np.log(rp * ra)) <= np.log(DESCUADRE_MAXIMO_DE_SPLIT):
                factor = _razon_cercana(1 / rp, 1.35)
            if factor is None and g["cusip"].iat[i] != g["cusip"].iat[i - 1]:
                factor = _razon_cercana(1 / rp, 1.10)
            if factor is not None and factor != 1:
                filas.append((cik, g["fecha"].iat[i], factor))
    return pd.DataFrame(filas, columns=["cik", "fecha", "factor"])


def quitar_picos(p: pd.DataFrame, sp: pd.DataFrame, *, salto: float = 2.5) -> pd.DataFrame:
    """Un precio que salta más de 2.5 veces y regresa el trimestre siguiente, sin split, es un
    error de captura: se quita (los dos retornos que lo tocan quedan sin dato)."""
    marcados = set(zip(sp["cik"], sp["fecha"], strict=True))
    malos = []
    for cik, g in p.sort_values("fecha").groupby("cik"):
        pr, fs = g["precio"].to_numpy(), g["fecha"].to_numpy()
        for i in range(1, len(g) - 1):
            a, b = pr[i] / pr[i - 1], pr[i + 1] / pr[i]
            if (cik, fs[i]) in marcados or (cik, fs[i + 1]) in marcados:
                continue
            if (a > salto and b < 1 / salto) or (a < 1 / salto and b > salto):
                malos.append(g.index[i])
    return p.drop(index=malos)


def retornos(p: pd.DataFrame, dps: pd.DataFrame, salidas: pd.DataFrame, *, retorno_quiebra: float = -0.30,
             fechas: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    """Retorno total trimestral de cada emisor, del cierre anterior al de ``fecha``.

    ``dps`` trae (cik, fecha, dps) con el dividendo por acción de cada trimestre calendario;
    ``salidas`` trae (cik, quiebra) con True si su salida fue por quiebra. Un trimestre sin
    precio entre dos con precio no tiene retorno (no se inventa). El trimestre siguiente al
    último precio es la salida, si el emisor no vuelve a aparecer.
    """
    sp = splits(p).set_index(["cik", "fecha"])["factor"]
    d = dps.set_index(["cik", "fecha"])["dps"]
    quiebra = salidas.set_index("cik")["quiebra"] if len(salidas) else pd.Series(dtype=bool)
    todas = fechas if fechas is not None else pd.DatetimeIndex(sorted(p["fecha"].unique()))
    ultima_global = todas.max()
    filas = []
    for cik, g in p.sort_values("fecha").groupby("cik"):
        g = g.set_index("fecha")
        fs = g.index
        for i in range(1, len(fs)):
            f0, f1 = fs[i - 1], fs[i]
            if todas.get_loc(f1) - todas.get_loc(f0) != 1:
                continue  # hueco: no hay retorno de un trimestre
            factor = sp.get((cik, f1), 1.0)
            div = d.get((cik, f1), np.nan)
            div = 0.0 if pd.isna(div) else div
            r = (g["precio"].iat[i] * factor + div) / g["precio"].iat[i - 1] - 1
            if r > RETORNO_MAXIMO_CREIBLE:
                continue  # un split que no se detectó o un error de captura: sin dato
            filas.append((cik, f1, r, div / g["precio"].iat[i - 1], factor != 1.0, False))
        if fs[-1] < ultima_global:
            sig = todas[todas.get_loc(fs[-1]) + 1]
            r = retorno_quiebra if bool(quiebra.get(cik, False)) else 0.0
            filas.append((cik, sig, r, 0.0, False, True))
    return pd.DataFrame(filas, columns=["cik", "fecha", "retorno", "dividendo", "split", "salida"])


def trimestre_calendario(fin: pd.Series) -> pd.Series:
    """El cierre de trimestre calendario en que cae cada fecha (para años fiscales que no cierran en diciembre)."""
    return fin.dt.to_period("Q").dt.end_time.dt.normalize()


def dividendos_por_trimestre(dq: pd.DataFrame, p: pd.DataFrame,
                             series_: pd.DataFrame | None = None) -> pd.DataFrame:
    """El dividendo por acción de cada trimestre calendario con precio, limpio de errores de captura.

    Un dividendo negativo, o de más de 10% del precio en un trimestre, es casi siempre una
    etiqueta mal usada (el de las preferentes, un acumulado sin restar). Se sustituye por la
    mediana de los dividendos del emisor en los dos trimestres de antes y los dos de después.
    Un trimestre sin dividendo trimestral en XBRL toma la cuarta parte del de 12 meses que
    cierra ahí: el año cuadra aunque el trimestre no. La columna ``fuente`` dice de dónde salió.
    """
    d = dq.assign(fecha=trimestre_calendario(pd.to_datetime(dq["fin"])))
    d = d.groupby(["cik", "fecha"], as_index=False)["dps"].sum()
    # Todos los trimestres con precio, tengan o no dividendo trimestral en XBRL.
    d = p[["cik", "fecha", "precio"]].merge(d, on=["cik", "fecha"], how="left").sort_values(["cik", "fecha"])
    previo = d.groupby("cik")["precio"].shift(1).fillna(d["precio"])
    malo = (d["dps"] < 0) | (d["dps"] > 0.10 * previo)
    limpio = d["dps"].where(~malo)
    d["fuente"] = np.where(limpio.notna(), "trimestral", "")
    d["dps"] = limpio.fillna(limpio.groupby(d["cik"]).transform(
        lambda s: s.rolling(5, center=True, min_periods=1).median()).where(malo))
    d.loc[malo & d["dps"].notna(), "fuente"] = "corregido"
    if series_ is not None:
        # Sin el trimestre en XBRL: la cuarta parte del dividendo de 12 meses que cierra en ese trimestre.
        s = series_[series_["partida"].isin(["dps_12m", "dividendos_12m", "acciones_promedio_12m"])]
        s = s.assign(fecha=trimestre_calendario(pd.to_datetime(s["fin"])))
        s = s.pivot_table(index=["cik", "fecha"], columns="partida", values="valor", aggfunc="last")
        for c in ("dps_12m", "dividendos_12m", "acciones_promedio_12m"):
            if c not in s:
                s[c] = np.nan
        s = s.astype(float)
        doce = s["dps_12m"].fillna(s["dividendos_12m"] / s["acciones_promedio_12m"].where(s["acciones_promedio_12m"] > 0)) / 4
        cuarto = pd.Series(doce.reindex(pd.MultiIndex.from_frame(d[["cik", "fecha"]])).to_numpy(), index=d.index)
        cuarto = cuarto.where(cuarto < 0.10 * previo)
        llenar = d["dps"].isna() & cuarto.notna()
        d.loc[llenar, "dps"] = cuarto[llenar]
        d.loc[llenar, "fuente"] = "doce_meses"
    d.loc[d["dps"].isna(), "fuente"] = "sin_dato"
    return d[["cik", "fecha", "dps", "fuente"]].fillna({"dps": 0.0})


SOCIEDADES = r"\bL\.?P\.?\b|LIMITED PARTNERSHIP|OPERATING PARTNERSHIP|PARTNERSHIP"
PRIMER_TRIMESTRE = pd.Timestamp("2008-12-31")  # el primer 13F en texto que se baja; antes solo hay rezagados


def nombres_de(resumen: pd.DataFrame) -> dict[str, set[str]]:
    """Las palabras distintivas del nombre actual y de los anteriores de cada emisor."""
    salida = {}
    for r in resumen.itertuples():
        previos = [x.split("@")[0] for x in str(r.nombres_previos).split("|")] if isinstance(r.nombres_previos, str) else []
        salida[r.cik] = fichas(r.nombre).union(*[fichas(n) for n in previos])
    return salida


def es_reit(cik: pd.Series, fecha: pd.Series, fts: pd.DataFrame, sic: pd.Series, *, meses: int = 24) -> pd.Series:
    """¿Era REIT al cierre del trimestre? Si un 10-K presentado en los 24 meses anteriores dice que
    califica o tributa como REIT. Un emisor 6798 que la búsqueda de texto nunca encontró, sí."""
    f = fts.assign(fecha_10k=pd.to_datetime(fts["fecha"]))[["cik", "fecha_10k"]].sort_values("fecha_10k")
    base = pd.DataFrame({"cik": cik.to_numpy(), "fecha": pd.to_datetime(fecha).to_numpy(), "i": np.arange(len(cik))})
    m = pd.merge_asof(base.sort_values("fecha"), f, left_on="fecha", right_on="fecha_10k", by="cik")
    m = m.sort_values("i")
    reciente = (m["fecha"] - m["fecha_10k"]).dt.days <= meses * 30.44
    nunca = ~cik.isin(set(fts["cik"])).to_numpy()
    return pd.Series(reciente.to_numpy() | (nunca & (sic.to_numpy() == "6798")), index=cik.index)


def armar(resumen: pd.DataFrame, fts: pd.DataFrame, agregado: pd.DataFrame, series_: pd.DataFrame,
          dividendos_q: pd.DataFrame, etiquetas: pd.DataFrame, manual: pd.DataFrame | None = None, *,
          min_tenedores: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """El panel trimestral (cik, fecha) y la ficha de cada emisor.

    El panel trae precio, tenedores, capitalización, el retorno del trimestre que termina en
    la fecha, y cada partida de los estados financieros como se conocía a esa fecha.
    """
    from src.investigacion import fundamentales as fu

    r = resumen[~resumen["nombre"].str.contains(SOCIEDADES, case=False, regex=True)].copy()
    series_ = series_.assign(valor=pd.to_numeric(series_["valor"], errors="coerce"))
    agregado = agregado[pd.to_datetime(agregado["fecha"]) >= PRIMER_TRIMESTRE]
    cus = asignar_cusips(r)
    p = precios(agregado, cus, nombres_de(r), min_tenedores=min_tenedores)
    sp = splits(p)
    p = quitar_picos(p, sp)
    fechas = pd.DatetimeIndex(sorted(agregado["fecha"].unique()))
    dv = dividendos_por_trimestre(dividendos_q, p, series_)
    ultimo = p.groupby("cik")["fecha"].max()
    q8k = pd.to_datetime(r.set_index("cik")["quiebra_8k"])
    quiebra = (q8k.reindex(ultimo.index) >= ultimo - pd.Timedelta(days=365)).fillna(False)
    ret = retornos(p, dv, pd.DataFrame({"cik": quiebra.index, "quiebra": quiebra.to_numpy()}), fechas=fechas)
    clas = clasificar(series_)
    partes = []
    for cik, g in series_.groupby("cik"):
        if cik not in ultimo.index:
            continue
        x = fu.a_la_fecha(g, fechas)
        x.index.name = "fecha"
        partes.append(x.reset_index().assign(cik=cik))
    f = pd.concat(partes, ignore_index=True)
    panel = p.merge(f, on=["cik", "fecha"], how="left").merge(ret, on=["cik", "fecha"], how="outer")
    panel = panel.sort_values(["cik", "fecha"], ignore_index=True)
    # La fila de salida no tiene precio: hereda lo demás del trimestre anterior para no perderse.
    panel["salida"] = panel["salida"].fillna(False).astype(bool)
    panel["split"] = panel["split"].fillna(False).astype(bool)
    panel["ffo_12m"] = fu.ffo(panel)
    por_accion = panel["dividendos_12m"] / panel["acciones_promedio_12m"].where(panel["acciones_promedio_12m"] > 0)
    panel["dps_12m_total"] = panel["dps_12m"].fillna(por_accion) if "dps_12m" in panel else por_accion
    panel["capitalizacion"] = panel["precio"] * panel["acciones"]
    ficha = r.merge(clas, on="cik", how="left")
    ficha["clase_final"] = ficha["cik"].map(clase_final(clas, etiquetas, manual))
    ficha["identificador"] = [identificador(c, t) for c, t in zip(ficha["cik"], ficha["tickers"], strict=True)]
    ficha["sellado"] = [sellado(c, t) for c, t in zip(ficha["cik"], ficha["tickers"], strict=True)]
    ficha["con_precio"] = ficha["cik"].isin(ultimo.index)
    sic = panel["cik"].map(ficha.set_index("cik")["sic"].astype(str))
    panel["es_reit"] = es_reit(panel["cik"], panel["fecha"], fts, sic.fillna(""))
    panel["de_capital"] = panel["cik"].map(ficha.set_index("cik")["clase_final"]).eq("capital")
    return panel, ficha


def clasificar(series: pd.DataFrame) -> pd.DataFrame:
    """REIT de capital, hipotecario o sin clasificar, por la mediana de su historia en XBRL.

    Hipotecario si los préstamos y valores pesan al menos la mitad de los activos, si los
    reportos pesan al menos 15%, o si con pocos inmuebles los intereses que cobra son al menos
    la mitad de sus ingresos. De capital si no es hipotecario y los inmuebles (o el equipo:
    torres, centros de datos) pesan al menos una cuarta parte. Lo demás queda sin clasificar
    y se revisa a mano. Contra las etiquetas de stockanalysis de los REITs que cotizan hoy,
    la regla falla con los hipotecarios comerciales que consolidan sus bursatilizaciones; por
    eso para ellos manda la etiqueta (``clase_final``).
    """
    s = series.pivot_table(index=["cik", "fin"], columns="partida", values="valor", aggfunc="first")
    for c in ("inmuebles", "ppe", "prestamos_y_valores", "repos", "activos", "ingreso_intereses_12m", "ingresos_12m"):
        if c not in s:
            s[c] = np.nan
    fisicos = s["inmuebles"].fillna(0) + s["ppe"].fillna(0)
    r = pd.DataFrame({
        "peso_inmuebles": fisicos / s["activos"],
        "peso_prestamos": s["prestamos_y_valores"] / s["activos"],
        "peso_repos": s["repos"] / s["activos"],
        "peso_intereses": s["ingreso_intereses_12m"] / s["ingresos_12m"],
    }).replace([np.inf, -np.inf], np.nan).groupby(level="cik").median()
    inm = r["peso_inmuebles"].fillna(0)
    hipotecario = ((r["peso_prestamos"] >= 0.5) | (r["peso_repos"] >= 0.15)
                   | ((inm < 0.25) & (r["peso_intereses"] >= 0.5)))
    r["clase"] = np.select([hipotecario, inm >= 0.25], ["hipotecario", "capital"], "sin_clasificar")
    return r.reset_index()


def clase_final(clas: pd.DataFrame, etiquetas: pd.DataFrame, manual: pd.DataFrame | None = None) -> pd.Series:
    """La clase que se usa: la revisión a mano si existe; si no, la etiqueta de stockanalysis
    para los que cotizan hoy; si no, la regla de XBRL. Índice: cik."""
    c = clas.set_index("cik")["clase"].copy()
    e = etiquetas.dropna(subset=["cik"]).drop_duplicates("cik").set_index("cik")["es_reit_de_capital"]
    c.loc[c.index.intersection(e.index)] = np.where(e.reindex(c.index.intersection(e.index)), "capital", "otro")
    if manual is not None and len(manual):
        m = manual.set_index("cik")["clase"]
        c = m.combine_first(c)
    return c


# --------------------------------------------------------------------------------------
# Bajar, validar y guardar
# --------------------------------------------------------------------------------------

DIR_EMISORES = DIR_INVESTIGACION / "emisores"
ARCHIVO_SELLADO = "emisores_eeuu"
ETIQUETAS = DIR_DATOS / "estudios" / "universo" / "lista.csv"


def bajar(cliente, sesion, *, hilos: int = 8, registro=print, usar_cache: bool = True) -> dict[str, pd.DataFrame]:
    """Todo lo que la fase 6 necesita de la SEC. Tarda una o dos horas la primera vez; lo
    bajado queda en ``data/cache/`` (fuera del repositorio) y una segunda corrida no toca la red."""
    import subprocess
    from concurrent.futures import ThreadPoolExecutor

    from src.investigacion import fundamentales as fu
    from src.investigacion import sec

    cache = DIR_DATOS / "cache" / "emisores_insumos.pkl"
    if usar_cache and cache.exists():
        return pd.read_pickle(cache)
    lista = sec.lista_sic(cliente)
    fts = sec.buscar_texto(sesion)
    registro(f"SIC 6798: {len(lista)} emisores; búsqueda de texto: {fts['cik'].nunique()}")

    def metadatos(cik: str) -> dict:
        d, f = sec.presentaciones(cliente, cik)
        r = sec.resumen(d, f)
        citas: dict[str, list] = {}
        for _, g in sec.filings_13g(f[f["filingDate"] >= "2008-01-01"], por_anio=1).iterrows():
            if not g["primaryDocument"]:
                continue
            try:
                texto = cliente.obtener(sec.url_documento(cik, g["accessionNumber"], g["primaryDocument"]))
            except Exception:  # noqa: BLE001 - un 13G que no baja no detiene al emisor
                continue
            for c in sec.cusips_en_texto(texto)[:2]:
                citas.setdefault(c, []).append(g["filingDate"])
        r["cusips"] = json.dumps({c: [min(v), max(v), len(v)] for c, v in citas.items()})
        return r

    candidatos = sorted(set(lista["cik"]) | set(fts.loc[fts["sic"].isin(sec.SIC_POSIBLES), "cik"]))
    with ThreadPoolExecutor(hilos) as ex:
        resumen = pd.DataFrame(list(ex.map(metadatos, candidatos)))
    resumen = resumen[resumen["ultimo_10k"].fillna("") >= "2009-01-01"]
    registro(f"candidatos con 10-K desde 2009: {len(resumen)}")

    def estados(cik: str):
        try:
            cf = cliente.companyfacts(cik)
        except Exception:  # noqa: BLE001 - sin XBRL (desapareció antes de 2011): sin estados
            return None, None
        return fu.series(cf).assign(cik=cik), fu.dividendo_trimestral(cf).assign(cik=cik)

    con_cusip = resumen.loc[resumen["cusips"] != "{}", "cik"]
    with ThreadPoolExecutor(4) as ex:
        pares = [x for x in ex.map(estados, con_cusip) if x[0] is not None]
    series_ = pd.concat([a for a, _ in pares], ignore_index=True)
    dividendos = pd.concat([b for _, b in pares], ignore_index=True)

    from src.investigacion import trece_f as tf

    (tf.DIR_13F / "zips").mkdir(parents=True, exist_ok=True)
    estructurados = []
    for url in tf.urls_conjuntos(cliente.obtener(tf.URL_PAGINA)):
        z = tf.DIR_13F / "zips" / url.rsplit("/", 1)[-1]
        hecho = tf.DIR_13F / "agregado" / z.name.replace(".zip", ".csv.gz")
        if hecho.exists():
            estructurados.append(pd.read_csv(hecho, dtype={"cusip": str}))
            continue
        if not z.exists():
            subprocess.run(["curl", "-sS", "-f", "-A", cliente.sesion.headers["User-Agent"], "-o", str(z), url],
                           check=True)
        a = tf.leer_conjunto(z)
        hecho.parent.mkdir(parents=True, exist_ok=True)
        a.to_csv(hecho, index=False, float_format="%.6g")
        estructurados.append(a)
    texto = tf.agregar_texto(bajar_13f_texto(cliente, registro=registro))
    agregado = tf.combinar(estructurados, texto)
    registro(f"13F: {agregado['fecha'].nunique()} trimestres")
    insumos = {"resumen": resumen, "fts": fts, "series": series_, "dividendos": dividendos, "agregado": agregado}
    pd.to_pickle(insumos, cache)
    return insumos


# Los administradores más grandes de 2009 a 2013 (índices, bancos custodios, fondos de REITs):
# juntos tienen a casi todos los REITs que cotizan. Escogidos por cuántas emisoras reportaban en
# el primer conjunto estructurado completo (2014).
GESTORES_13F_TEXTO = (
    "0000102909", "0000093751", "0000073124", "0001390777", "0001214717", "0000354204", "0000919079", "0000913414",
    "0001006249", "0001086364", "0001305227", "0001364742", "0000895421", "0000072971", "0000070858", "0001114446",
    "0000886982", "0000019617", "0000948046", "0000914208", "0000820027", "0000831001", "0001000275", "0000824468",
    "0000312069", "0000036104", "0000713676", "0000887793", "0000932859", "0001109448", "0001097218", "0000928047",
)


def bajar_13f_texto(cliente, *, desde: str = "2008-12-31", hasta: str = "2013-09-30", registro=print) -> pd.DataFrame:
    """Las tenencias de los 13F en texto de los gestores grandes, de 2009 a 2013."""
    from src.investigacion import sec
    from src.investigacion import trece_f as tf

    destino = tf.DIR_13F / "texto"
    destino.mkdir(parents=True, exist_ok=True)
    for cik in GESTORES_13F_TEXTO:
        _, f = sec.presentaciones(cliente, cik)
        g = f[(f["form"] == "13F-HR") & (f["reportDate"] >= desde) & (f["reportDate"] <= hasta)]
        for r in g.itertuples():
            ruta = destino / f"{cik}_{r.reportDate}_{r.accessionNumber}.csv.gz"
            if ruta.exists():
                continue
            t = cliente.obtener(sec.url_documento(cik, r.accessionNumber, r.accessionNumber + ".txt"))
            p = tf.documento_xml_tabla(t)
            if p is None or p.empty:
                p = tf.parsear_texto(t)
            p.assign(fecha=r.reportDate, filing=r.accessionNumber, gestor=cik).to_csv(ruta, index=False)
        registro(f"13F en texto: {cik} ({len(g)})")
    partes = []
    for f in sorted(destino.glob("*.csv.gz")):
        try:
            d = pd.read_csv(f, dtype={"cusip": str})
        except pd.errors.EmptyDataError:
            continue
        if len(d):
            partes.append(d)
    return pd.concat(partes, ignore_index=True)


def etiquetas_actuales(resumen_cik: dict[str, str] | None = None) -> pd.DataFrame:
    """La lista de REITs que cotizan hoy (estudio del universo) con su CIK de la SEC."""
    e = pd.read_csv(ETIQUETAS)
    if resumen_cik is not None:
        e["cik"] = e["ticker"].map(lambda t: resumen_cik.get(t.replace(".", "-")) or resumen_cik.get(t))
    return e


def validar_contra_yahoo(panel: pd.DataFrame, ficha: pd.DataFrame, etiquetas: pd.DataFrame,
                         yahoo: pd.DataFrame) -> dict:
    """Retornos trimestrales de los 13F contra Yahoo, solo con emisores que cotizan hoy y NO
    están sellados. HR se excluye: su historia en Yahoo antes de 2022 es de otro emisor."""
    abiertos = etiquetas[etiquetas["es_reit_de_capital"]].merge(ficha[["cik", "sellado"]], on="cik")
    abiertos = abiertos[~abiertos["sellado"] & (abiertos["ticker"] != "HR")]
    y = yahoo[yahoo["fecha"].dt.month % 3 == 0].copy()
    y["fecha"] = trimestre_calendario(y["fecha"])
    y = y.sort_values(["ticker", "fecha"])
    y["ry"] = y.groupby("ticker")["ajustado"].pct_change()
    m = panel[panel["retorno"].notna() & ~panel["salida"]].merge(abiertos[["cik", "ticker"]], on="cik")
    m = m.merge(y[["ticker", "fecha", "ry"]], on=["ticker", "fecha"]).dropna(subset=["ry"])
    dif = m["retorno"] - m["ry"]
    anual = m.assign(a=m["fecha"].dt.year).groupby(["ticker", "a"]).agg(
        r=("retorno", lambda s: np.prod(1 + s) - 1), ry=("ry", lambda s: np.prod(1 + s) - 1), n=("retorno", "size"))
    anual = anual[anual["n"] == 4]
    return {
        "trimestres": int(len(m)), "emisores": int(m["ticker"].nunique()),
        "correlacion": round(float(m[["retorno", "ry"]].corr().iat[0, 1]), 4),
        "diferencia_mediana_absoluta": round(float(dif.abs().median()), 5),
        "fraccion_a_mas_de_2_puntos": round(float((dif.abs() > 0.02).mean()), 4),
        "fraccion_a_mas_de_10_puntos": round(float((dif.abs() > 0.10).mean()), 4),
        "diferencia_media_anual": round(float((anual["r"] - anual["ry"]).mean()), 5),
        "diferencia_mediana_absoluta_anual": round(float((anual["r"] - anual["ry"]).abs().median()), 5),
    }


def guardar(panel: pd.DataFrame, ficha: pd.DataFrame, manifiesto: dict, *, raiz: Path | None = None,
            raiz_sellado: Path | None = None) -> Path:
    """El panel de los emisores abiertos va a ``emisores/``; el de los sellados, sellado con su
    huella digital, sin mirarlo: solo se reporta cuántos renglones tiene."""
    from src.investigacion.muestras import sellar

    destino = raiz or DIR_EMISORES
    destino.mkdir(parents=True, exist_ok=True)
    cerrados = set(ficha.loc[ficha["sellado"], "cik"])
    abierto = panel[~panel["cik"].isin(cerrados)]
    abierto.to_csv(destino / "panel.csv.gz", index=False, float_format="%.8g",
                   compression={"method": "gzip", "mtime": 0})
    columnas = ["cik", "nombre", "sic", "tickers", "identificador", "sellado", "clase", "clase_final", "con_precio",
                "primer_10k", "ultimo_10k", "quiebra_8k", "cambio_de_control_8k", "baja_registro", "peso_inmuebles",
                "peso_prestamos", "peso_repos", "peso_intereses"]
    ficha[[c for c in columnas if c in ficha]].to_csv(destino / "universo.csv", index=False)
    sellar(panel[panel["cik"].isin(cerrados)], ARCHIVO_SELLADO, raiz=raiz_sellado,
           fuente="SEC: 13F, XBRL y submissions; emisores sellados de la fase 6")
    manifiesto = {**manifiesto, "renglones_abiertos": int(len(abierto)),
                  "renglones_sellados": int(panel["cik"].isin(cerrados).sum()),
                  "emisores_abiertos": int(abierto["cik"].nunique()), "emisores_sellados": len(cerrados)}
    (destino / "manifiesto.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2, default=str),
                                             encoding="utf-8")
    return destino


def cargar(raiz: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """El panel de los emisores abiertos y la ficha de todos."""
    origen = raiz or DIR_EMISORES
    panel = pd.read_csv(origen / "panel.csv.gz", dtype={"cik": str}, parse_dates=["fecha"])
    for c in ("salida", "split", "es_reit", "de_capital"):
        if c in panel:
            panel[c] = panel[c].astype(bool)
    ficha = pd.read_csv(origen / "universo.csv", dtype={"cik": str, "sic": str})
    return panel, ficha


EMISORAS_CON_FFO_PUBLICADO = {"O": "0000726728", "NNN": "0000751364", "WPC": "0001025378"}


def validar_ffo(series_: pd.DataFrame, *, raiz_emisoras: Path | None = None) -> dict:
    """El FFO armado con XBRL contra el FFO de 12 meses que publican O, NNN y WPC en sus 8-K."""
    from src.investigacion import fundamentales as fu

    origen = raiz_emisoras or DIR_DATOS / "emisoras"
    salida = {}
    for ticker, cik in EMISORAS_CON_FFO_PUBLICADO.items():
        s = series_[series_["cik"] == cik]
        armado = fu.ffo(s.pivot_table(index="fin", columns="partida", values="valor", aggfunc="first"))
        c = pd.read_csv(origen / ticker / "conciliacion.csv.gz")
        c = c[c["linea"] == "ffo"].assign(fecha_dato=lambda t: pd.to_datetime(t["fecha_dato"]))
        anual = c[c["periodo_tipo"] == "FY"].drop_duplicates("fecha_dato").set_index("fecha_dato")["valor"]
        trimestral = c[c["periodo_tipo"] == "Q"].drop_duplicates("fecha_dato").set_index("fecha_dato")["valor"]
        publicado = anual.combine_first(trimestral.sort_index().rolling(4).sum())
        m = pd.DataFrame({"armado": armado, "publicado": publicado}).dropna()
        error = m["armado"] / m["publicado"] - 1
        salida[ticker] = {"periodos": int(len(m)), "error_mediano": round(float(error.median()), 4),
                          "error_absoluto_maximo": round(float(error.abs().max()), 4)}
    return salida
