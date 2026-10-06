"""Fase 6: ¿en cuáles REITs? Selección entre todos los REITs de capital de EE. UU., vivos y muertos.

Pre-registro: ``docs/investigacion/fase6_preregistro.md``, en el mismo commit que este
archivo y antes de correrlo. El panel trimestral lo arma ``emisores.py`` con precios de los
13F, dividendos y estados financieros de XBRL, todo conocido a su fecha.

Qué se prueba, en este orden:

1. **Desarrollo** (carteras formadas hasta 2014, retornos hasta 2015, emisores no sellados):
   13 señales de la literatura (S1–S13) y tres reglas compuestas: calidad (S8), «barato
   entre los de calidad» y «barato contra su historia entre los de calidad» (S12).
2. **Filtro** escrito en el pre-registro; a validación pasan a lo más tres, más el detector
   de recortes, que en desarrollo no tiene historia suficiente para calificarse.
3. **Validación** (2016 en adelante, no sellados), abierta una vez con motivo.
4. **Prueba final** (emisores sellados, 2012 en adelante) solo si una regla pasa la
   validación, con el modelo congelado antes.

La métrica principal es la de la fase 0: TIR después de impuestos del SIC aportando 1,000
dólares al mes (3,000 por trimestre) sin vender nunca, contra aportar lo mismo a todos los
elegibles por partes iguales.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.investigacion import bitacora, estadistica
from src.investigacion.diseno import CRITERIOS, MUESTRAS, OBJETIVO


@dataclass(frozen=True)
class Diseno6:
    capitalizacion_minima: float = 250e6       # dólares nominales: lo que se puede comprar con liquidez
    precio_minimo: float = 5.0
    tenedores_texto: int = 10                   # 13F en texto (hasta marzo de 2013): de ~25 administradores
    tenedores_estructurado: int = 20            # 13F estructurados: de miles de administradores
    ultimo_trimestre_texto: pd.Timestamp = pd.Timestamp("2013-03-31")
    elegibles_minimos: int = 30                 # un trimestre con menos no forma carteras
    horizonte: int = 4                          # trimestres que se mantiene cada cohorte
    grupos: int = 3                             # terciles
    payout_maximo: float = 0.90                 # dividendos entre FFO
    caida_de_recorte: float = 0.10              # el dividendo de 12 meses cae más de 10%
    quintil_excluido: float = 0.20              # calidad: fuera el peor quintil de distancia al default y de momentum
    retorno_de_quiebra: float = -0.30           # Shumway (1997); sensibilidad con −100%
    desplome: float = -0.30                     # un retorno de 12 meses de −30% o peor es «trampa»
    aportacion_trimestral: float = 3 * OBJETIVO.aportacion_mensual
    trimestres_de_volatilidad: int = 12
    minimo_de_volatilidad: int = 8
    trimestres_de_historia_yield: int = 20
    minimo_de_historia_yield: int = 12
    trimestres_de_crecimiento_del_dividendo: int = 12
    minimo_para_estimar_recortes: int = 8       # trimestres con resultado conocido antes de pronosticar
    riesgo_excluido: float = 0.20               # D1: fuera el quintil con más probabilidad de recorte
    auc_minima: float = 0.70
    bloques_pbo: int = 8
    maximo_a_validacion: int = 3
    rezago_nw: int = 4                          # cohortes encimadas de cuatro trimestres


DISENO6 = Diseno6()

# Señal -> (dirección, hipótesis de la literatura). Dirección +1: más alto es mejor.
SENALES: dict[str, tuple[int, str]] = {
    "momentum": (+1, "S1"),
    "apalancamiento": (-1, "S2"),
    "distancia_al_default": (+1, "S3"),
    "volatilidad": (-1, "S4"),
    "rendimiento_de_la_empresa": (+1, "S5"),
    "rendimiento_ffo": (+1, "S6"),
    "rendimiento_del_dividendo": (+1, "S7"),
    "crecimiento_de_activos": (-1, "S10"),
    "rentabilidad": (+1, "S10"),
    "tamano": (+1, "S11"),
    "yield_contra_su_historia": (+1, "S12"),
    "crecimiento_del_dividendo": (+1, "S13"),
    "payout": (-1, "S8"),
}
COMPUESTAS = ("calidad", "calidad y barato", "calidad y barato contra su historia")
DETECTOR = "sin riesgo de recorte"
REGLAS = (*SENALES, *COMPUESTAS)
VARIABLES_DE_RECORTE = ("payout", "apalancamiento", "distancia_al_default", "momentum", "yield_relativo", "tamano",
                        "volatilidad", "recorte_previo", "crecimiento_ffo")


# --------------------------------------------------------------------------------------
# Señales, con lo que se sabía al cierre de cada trimestre
# --------------------------------------------------------------------------------------


def _cuadricula(x: pd.DataFrame) -> pd.DataFrame:
    """Cada emisor en todos los trimestres entre su primero y su último: los desplazamientos de
    cuatro trimestres tienen que ser de cuatro trimestres aunque falte un precio."""
    fechas = pd.date_range(x["fecha"].min(), x["fecha"].max(), freq="QE")
    partes = []
    for cik, g in x.groupby("cik"):
        rango = fechas[(fechas >= g["fecha"].min()) & (fechas <= g["fecha"].max())]
        partes.append(pd.DataFrame({"cik": cik, "fecha": rango}))
    return pd.concat(partes, ignore_index=True).merge(x, on=["cik", "fecha"], how="left")


def senales(x: pd.DataFrame, d: Diseno6 = DISENO6) -> pd.DataFrame:
    """Agrega al panel las señales y las variables del detector de recortes.

    ``x`` trae una fila por (cik, fecha) con precio, retorno (del trimestre que termina en
    fecha), salida, capitalización y las partidas conocidas a la fecha.
    """
    x = _cuadricula(x).sort_values(["cik", "fecha"], ignore_index=True)
    x["salida"] = x["salida"].fillna(False).astype(bool)
    g = x.groupby("cik")
    r = x["retorno"].where(~x["salida"])
    log1p = np.log1p(r)
    # S1: retorno de los meses 12 a 3 (los tres trimestres anteriores al último).
    x["momentum"] = np.expm1(log1p.groupby(x["cik"]).transform(lambda s: s.shift(1).rolling(3, min_periods=3).sum()))
    x["retorno_12m"] = np.expm1(log1p.groupby(x["cik"]).transform(lambda s: s.rolling(4, min_periods=4).sum()))
    x["volatilidad"] = r.groupby(x["cik"]).transform(
        lambda s: s.rolling(d.trimestres_de_volatilidad, min_periods=d.minimo_de_volatilidad).std()) * 2.0
    pasivos = x["pasivos"].fillna(x["activos"] - x["capital_total"])
    cap = x["capitalizacion"]
    x["apalancamiento"] = pasivos / (pasivos + cap)
    # S3: distancia al default ingenua (Bharath y Shumway 2008), a un año.
    sig_e = x["volatilidad"]
    sig_d = 0.05 + 0.25 * sig_e
    sig_v = cap / (cap + pasivos) * sig_e + pasivos / (cap + pasivos) * sig_d
    x["distancia_al_default"] = (np.log((cap + pasivos) / pasivos) + x["retorno_12m"] - sig_v**2 / 2) / sig_v
    ffo = x["ffo_12m"]
    x["rendimiento_de_la_empresa"] = (ffo + x["intereses_12m"].fillna(0)) / (cap + pasivos)
    x["rendimiento_ffo"] = ffo / cap
    dps = x["dps_12m_total"]
    x["rendimiento_del_dividendo"] = dps / x["precio"]
    x["crecimiento_de_activos"] = x["activos"] / g["activos"].shift(4) - 1
    x["rentabilidad"] = ffo / x["activos"]
    x["tamano"] = np.log(cap)
    yld = x["rendimiento_del_dividendo"]
    ventana = {"window": d.trimestres_de_historia_yield, "min_periods": d.minimo_de_historia_yield}
    media = yld.groupby(x["cik"]).transform(lambda s: s.shift(1).rolling(**ventana).mean())
    desv = yld.groupby(x["cik"]).transform(lambda s: s.shift(1).rolling(**ventana).std())
    x["yield_contra_su_historia"] = (yld - media) / desv
    antes = g["dps_12m_total"].shift(d.trimestres_de_crecimiento_del_dividendo)
    anios = d.trimestres_de_crecimiento_del_dividendo / 4
    x["crecimiento_del_dividendo"] = np.where(antes > 0, (dps / antes).clip(lower=0) ** (1 / anios) - 1, np.nan)
    acciones = x["acciones_promedio_12m"].fillna(x["acciones"])
    pagado = (dps * acciones).fillna(x["dividendos_12m"])
    # Sin FFO positivo el payout no es un número: se trata como el peor (10 veces el FFO).
    x["payout"] = np.where(ffo > 0, pagado / ffo, np.where(ffo <= 0, 10.0, np.nan))
    un_anio = g["dps_12m_total"].shift(4)
    x["recorte_previo"] = np.where(un_anio.notna() & dps.notna(), (dps < (1 - d.caida_de_recorte) * un_anio), np.nan)
    x["crecimiento_ffo"] = ffo / g["ffo_12m"].shift(4) - 1
    x["yield_relativo"] = yld / x.groupby("fecha")["rendimiento_del_dividendo"].transform("median")
    # El resultado del detector: el dividendo de 12 meses que se conocía un año después cayó más de
    # 10%, o el emisor quebró en ese año.
    despues = g["dps_12m_total"].shift(-4)
    quiebra = (x["salida"] & (x["retorno"] <= d.retorno_de_quiebra + 1e-9)).astype(float)
    quiebra_pronto = quiebra.groupby(x["cik"]).transform(lambda s: s[::-1].rolling(4, min_periods=1).max()[::-1]
                                                         .shift(-1))
    corte = np.where(despues.notna() & (dps > 0), (despues < (1 - d.caida_de_recorte) * dps), np.nan)
    x["recorte_siguiente"] = np.where(quiebra_pronto == 1, 1.0, corte)
    return x.replace([np.inf, -np.inf], np.nan)


def elegibles(x: pd.DataFrame, d: Diseno6 = DISENO6) -> pd.Series:
    """Quién se puede comprar al cierre de cada trimestre: REIT de capital listado y de tamaño
    comprable. No pide estados financieros: quien no los tiene sigue en el universo contra el
    que se compara, solo que ninguna señal lo puede escoger."""
    tenedores = np.where(x["fecha"] <= d.ultimo_trimestre_texto, d.tenedores_texto, d.tenedores_estructurado)
    e = (x["de_capital"].fillna(False).astype(bool) & x["es_reit"].fillna(False).astype(bool)
         & (x["precio"] >= d.precio_minimo) & (x["tenedores"] >= tenedores)
         & (x["capitalizacion"] >= d.capitalizacion_minima))
    cuantos = e.groupby(x["fecha"]).transform("sum")
    return e & (cuantos >= d.elegibles_minimos)


# --------------------------------------------------------------------------------------
# Grupos
# --------------------------------------------------------------------------------------


def _tercil(valores: pd.Series, direccion: int, grupos: int) -> pd.Series:
    """1 = el mejor grupo, ``grupos`` = el peor; NaN sin señal."""
    v = valores * direccion
    rango = v.rank(pct=True, method="first")
    return pd.Series(np.ceil((1 - rango) * grupos).clip(1, grupos), index=valores.index).where(v.notna())


def grupos_de_senal(x: pd.DataFrame, senal: str, d: Diseno6 = DISENO6) -> pd.Series:
    """El tercil de cada elegible según la señal (``x`` ya filtrado a elegibles)."""
    direccion = SENALES[senal][0]
    return x.groupby("fecha", group_keys=False)[senal].apply(lambda s: _tercil(s, direccion, d.grupos))


def calidad(x: pd.DataFrame, d: Diseno6 = DISENO6) -> pd.Series:
    """S8: el filtro de calidad, con los umbrales fijados antes de ver los datos."""
    por_fecha = x.groupby("fecha")
    mediana_apal = por_fecha["apalancamiento"].transform("median")
    q_dd = por_fecha["distancia_al_default"].transform(lambda s: s.quantile(d.quintil_excluido))
    q_mom = por_fecha["momentum"].transform(lambda s: s.quantile(d.quintil_excluido))
    return (
        (x["ffo_12m"] > 0) & (x["payout"] <= d.payout_maximo)
        & (x["apalancamiento"] <= mediana_apal)
        & (x["recorte_previo"] == 0)
        & (x["distancia_al_default"] > q_dd) & (x["momentum"] > q_mom)
    )


def miembros(x: pd.DataFrame, regla: str, d: Diseno6 = DISENO6, *, riesgo: pd.Series | None = None) -> pd.Series:
    """True para los elegibles que la regla escoge en cada trimestre (``x`` ya filtrado a elegibles)."""
    if regla == "todos":
        return pd.Series(True, index=x.index)
    if regla in SENALES:
        return grupos_de_senal(x, regla, d) == 1
    q = calidad(x, d)
    if regla == "calidad":
        return q
    if regla in ("calidad y barato", "calidad y barato contra su historia"):
        senal = "rendimiento_ffo" if regla == "calidad y barato" else "yield_contra_su_historia"
        t = x[q].groupby("fecha", group_keys=False)[senal].apply(lambda s: _tercil(s, +1, d.grupos))
        return (t == 1).reindex(x.index, fill_value=False)
    if regla == DETECTOR:
        if riesgo is None:
            raise ValueError("«sin riesgo de recorte» necesita las probabilidades del detector.")
        r = riesgo.reindex(x.index)
        corte = r.groupby(x["fecha"]).transform(lambda s: s.quantile(1 - d.riesgo_excluido))
        return r.notna() & (r < corte)
    raise KeyError(regla)


# --------------------------------------------------------------------------------------
# Retornos de los grupos (antes de impuestos) y el inversionista (después)
# --------------------------------------------------------------------------------------


def matriz_de_retornos(x: pd.DataFrame) -> pd.DataFrame:
    """Retorno total de cada emisor (columna) en cada trimestre (renglón)."""
    r = x.dropna(subset=["retorno"])
    return r.pivot_table(index="fecha", columns="cik", values="retorno", aggfunc="first").reindex(
        sorted(x["fecha"].unique()))


def retorno_de_grupo(sel: pd.DataFrame, R: pd.DataFrame, d: Diseno6 = DISENO6) -> pd.Series:
    """Retorno trimestral de mantener cada cohorte ``horizonte`` trimestres, cohortes encimadas.

    ``sel`` trae (fecha, cik) de los escogidos. Cada cohorte pone partes iguales en sus
    miembros y deja correr los pesos (comprar y mantener). Un miembro sin retorno en un
    trimestre (salió, o hay un hueco en los 13F) no pesa ese trimestre: lo suyo se reparte.
    """
    fechas = R.index
    cohortes = sel.groupby("fecha")["cik"].apply(list)
    suma, n = np.zeros(len(fechas)), np.zeros(len(fechas))
    for f, ciks in cohortes.items():
        if f not in fechas:
            continue
        i = fechas.get_loc(f)
        ciks = [c for c in ciks if c in R.columns]
        if not ciks:
            continue
        w = pd.Series(1.0, index=ciks)
        for k in range(1, d.horizonte + 1):
            if i + k >= len(fechas):
                break
            r = R.iloc[i + k][ciks]
            vivos = r.notna()
            if not vivos.any():
                break
            suma[i + k] += float((w[vivos] * r[vivos]).sum() / w[vivos].sum())
            n[i + k] += 1
            w = w * (1 + r.fillna(0.0))
    return pd.Series(np.where(n > 0, suma / np.maximum(n, 1), np.nan), index=fechas)


@dataclass
class Simulacion:
    tir: float
    caida_maxima: float
    riqueza_final: float
    aportado: float
    serie: pd.Series = field(default_factory=pd.Series)


def _tir(flujos: np.ndarray) -> float:
    """TIR por periodo (bisección): aportaciones negativas, el último flujo trae el valor final."""
    def vpn(t):
        return float(np.sum(flujos / (1 + t) ** np.arange(len(flujos))))
    a, b = -0.5, 1.0
    fa = vpn(a)
    if np.sign(fa) == np.sign(vpn(b)):
        return np.nan
    for _ in range(200):
        m = (a + b) / 2
        fm = vpn(m)
        if np.sign(fm) == np.sign(fa):
            a, fa = m, fm
        else:
            b = m
    return (a + b) / 2


def simular(sel: pd.DataFrame, x: pd.DataFrame, *, desde: pd.Timestamp, hasta: pd.Timestamp,
            d: Diseno6 = DISENO6, rezago: int = 0, multiplicador_de_costos: float = 1.0,
            rotar_cada: int | None = None) -> Simulacion:
    """El inversionista: 3,000 dólares por trimestre a los escogidos, por partes iguales.

    Sin vender nunca (``rotar_cada=None``): los dividendos pagan 20% y se reinvierten con la
    siguiente aportación; si un emisor sale (compra o quiebra), lo que se recibe paga 10% sobre
    la ganancia (con pérdidas acumuladas) y se reinvierte. Con ``rotar_cada=4``, cada año se
    venden los que ya no están escogidos. Al final se vende todo y se paga el 10%.
    """
    imp_div, imp_gan = OBJETIVO.impuesto_dividendo, OBJETIVO.impuesto_ganancia
    comision = OBJETIVO.comision * multiplicador_de_costos
    R = x.dropna(subset=["retorno"]).set_index(["fecha", "cik"])[["retorno", "dividendo", "salida"]]
    R = R[~R.index.duplicated()]
    escogidos = sel.groupby("fecha")["cik"].apply(list)
    fechas = [f for f in sorted(x["fecha"].unique()) if desde <= f <= hasta]
    valor: dict[str, float] = {}
    base: dict[str, float] = {}
    efectivo, perdidas, flujos, indice, nivel = 0.0, 0.0, [], [], 1.0

    def vender(cik: str) -> float:
        nonlocal perdidas
        v, b = valor.pop(cik), base.pop(cik)
        ganancia = v - b
        if ganancia < 0:
            perdidas += -ganancia
            return v
        aplicable = min(perdidas, ganancia)
        perdidas -= aplicable
        return v - imp_gan * (ganancia - aplicable)

    for k, f in enumerate(fechas):
        if k > 0:
            antes = sum(valor.values()) + efectivo
            for cik in list(valor):
                if (f, cik) in R.index:
                    fila = R.loc[(f, cik)]
                    r, div, sale = float(fila["retorno"]), float(fila["dividendo"] or 0.0), bool(fila["salida"])
                else:
                    r, div, sale = 0.0, 0.0, False
                div = 0.0 if not np.isfinite(div) else div
                efectivo += valor[cik] * div * (1 - imp_div)
                valor[cik] *= 1 + (r - div)
                if sale:
                    efectivo += vender(cik)
            despues = sum(valor.values()) + efectivo
            nivel *= despues / antes if antes > 0 else 1.0
        indice.append(nivel)
        fuente = fechas[k - rezago] if k - rezago >= 0 else None
        hoy = list(escogidos.get(fuente, [])) if fuente is not None else []
        if rotar_cada and k % rotar_cada == 0 and hoy:
            for cik in [c for c in valor if c not in hoy]:
                efectivo += vender(cik) * (1 - comision)
        efectivo += d.aportacion_trimestral
        flujos.append(-d.aportacion_trimestral)
        if hoy:
            monto = efectivo / len(hoy)
            for cik in hoy:
                valor[cik] = valor.get(cik, 0.0) + monto * (1 - comision)
                base[cik] = base.get(cik, 0.0) + monto
            efectivo = 0.0
    final = efectivo + sum(vender(c) * (1 - comision) for c in list(valor))
    flujos[-1] += final
    q = _tir(np.array(flujos))
    s = pd.Series(indice, index=fechas)
    caida = float((s / s.cummax() - 1).min())
    return Simulacion((1 + q) ** 4 - 1 if np.isfinite(q) else np.nan, caida, final,
                      d.aportacion_trimestral * len(fechas), s)


# --------------------------------------------------------------------------------------
# Estadística
# --------------------------------------------------------------------------------------


def _adelante(R: pd.DataFrame, d: Diseno6) -> pd.DataFrame:
    """Retorno de los cuatro trimestres siguientes a cada fecha (comprar y mantener)."""
    return np.expm1(np.log1p(R.fillna(0.0)).rolling(d.horizonte).sum().shift(-d.horizonte)).where(
        R.notna().rolling(d.horizonte).sum().shift(-d.horizonte) > 0)


def correlacion_de_rangos(x: pd.DataFrame, senal: str, adelante: pd.DataFrame) -> pd.Series:
    """Cada trimestre, la correlación de rangos entre la señal (orientada) y el retorno de los
    12 meses siguientes."""
    salida = {}
    direccion = SENALES[senal][0]
    for f, g in x.groupby("fecha"):
        if f not in adelante.index:
            continue
        y = adelante.loc[f].reindex(g["cik"]).to_numpy()
        s = g[senal].to_numpy() * direccion
        ok = np.isfinite(y) & np.isfinite(s)
        if ok.sum() >= 10:
            salida[f] = pd.Series(s[ok]).rank().corr(pd.Series(y[ok]).rank())
    return pd.Series(salida, dtype=float)


def apuestas_efectivas(sel: pd.DataFrame, R: pd.DataFrame, universo: pd.Series, d: Diseno6 = DISENO6) -> float:
    """P7 para una cartera de muchos emisores: por cada año que no se encima, los escogidos
    entre (1 + (n−1)·ρ), con ρ la correlación promedio de sus excesos contra el universo."""
    exceso = R.sub(universo, axis=0)
    fechas = sorted(sel["fecha"].unique())[:: d.horizonte]
    total = 0.0
    for f in fechas:
        ciks = [c for c in sel.loc[sel["fecha"] == f, "cik"] if c in exceso.columns]
        n = len(ciks)
        if n < 2:
            total += n
            continue
        with np.errstate(invalid="ignore", divide="ignore"):
            c = exceso[ciks].corr(min_periods=8).to_numpy()
        rho = np.nanmean(c[np.triu_indices(n, 1)]) if np.isfinite(c[np.triu_indices(n, 1)]).any() else 0.0
        total += n / (1 + (n - 1) * max(float(rho), 0.0))
    return total


def auc(y: np.ndarray, p: np.ndarray) -> float:
    """Área bajo la curva ROC (Mann-Whitney)."""
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    ok = np.isfinite(y) & np.isfinite(p)
    y, p = y[ok], p[ok]
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    rangos = pd.Series(np.concatenate([pos, neg])).rank().to_numpy()
    return float((rangos[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def riesgo_de_recorte(x: pd.DataFrame, d: Diseno6 = DISENO6, *, entrenar_con: pd.DataFrame | None = None
                      ) -> pd.Series:
    """D1: probabilidad de recorte en 12 meses, estimada en cada trimestre solo con el pasado.

    Logit (L2, C=1) sobre las variables pre-registradas, recortadas al 1% y 99% y
    estandarizadas con el pasado; los faltantes se llenan con la mediana del pasado. En el
    trimestre t solo se usan pares formados en t−4 o antes (su resultado ya se conocía).
    ``entrenar_con`` permite estimar con otros emisores (los abiertos) y pronosticar a ``x``
    (los sellados): el modelo nunca ve a los sellados.
    """
    from sklearn.linear_model import LogisticRegression

    variables = list(VARIABLES_DE_RECORTE)
    base = x if entrenar_con is None else entrenar_con
    fechas = sorted(x["fecha"].unique())
    salida = pd.Series(np.nan, index=x.index)
    for f in fechas:
        limite = f - pd.offsets.QuarterEnd(d.horizonte)
        pasado = base[base["fecha"] <= limite]
        entrenar = pasado[pasado["recorte_siguiente"].notna()]
        if entrenar["fecha"].nunique() < d.minimo_para_estimar_recortes or entrenar["recorte_siguiente"].nunique() < 2:
            continue
        escala = _escala(pasado[variables].astype(float))
        modelo = LogisticRegression(C=1.0, max_iter=1000).fit(_preparar(entrenar, escala),
                                                               entrenar["recorte_siguiente"].astype(int))
        hoy = x["fecha"] == f
        salida[hoy] = modelo.predict_proba(_preparar(x[hoy], escala))[:, 1]
    return salida


def _escala(datos: pd.DataFrame) -> dict:
    """Recorte al 1% y 99%, mediana para los faltantes, media y desviación: todo del pasado."""
    bajo, alto, mediana = datos.quantile(0.01), datos.quantile(0.99), datos.median()
    lleno = datos.clip(lower=bajo, upper=alto, axis=1).fillna(mediana)
    return {"bajo": bajo, "alto": alto, "mediana": mediana, "media": lleno.mean(),
            "desv": lleno.std().replace(0, 1)}


def _preparar(t: pd.DataFrame, e: dict) -> np.ndarray:
    z = t[list(VARIABLES_DE_RECORTE)].astype(float).clip(lower=e["bajo"], upper=e["alto"], axis=1).fillna(e["mediana"])
    return ((z - e["media"]) / e["desv"]).to_numpy()


def despues_del_recorte(x: pd.DataFrame, adelante: pd.DataFrame, universo_12m: pd.Series) -> pd.Series:
    """D3: retorno de los 12 meses siguientes de quien acaba de recortar, menos el del universo."""
    previo = x.groupby("cik")["recorte_previo"].shift(1)
    nuevo = x[(x["recorte_previo"] == 1) & (previo != 1)]
    filas = {}
    for r in nuevo.itertuples():
        if r.fecha in adelante.index and r.cik in adelante.columns and np.isfinite(adelante.at[r.fecha, r.cik]):
            filas[(r.cik, r.fecha)] = adelante.at[r.fecha, r.cik] - universo_12m.get(r.fecha, np.nan)
    return pd.Series(filas, dtype=float)


# --------------------------------------------------------------------------------------
# Evaluación de una regla
# --------------------------------------------------------------------------------------


def _anual(r: pd.Series) -> float:
    r = r.dropna()
    return float(np.expm1(np.log1p(r).mean() * 4)) if len(r) else np.nan


def evaluar(regla: str, x: pd.DataFrame, *, desde: pd.Timestamp, hasta: pd.Timestamp, muestra: str,
            d: Diseno6 = DISENO6, riesgo: pd.Series | None = None, registrar: bool = True, ruta_bitacora=None,
            mitades: tuple[pd.Timestamp, ...] = ()) -> dict:
    """Todas las métricas de una regla entre ``desde`` (primera cartera) y ``hasta`` (último retorno).

    ``x`` trae las señales calculadas sobre lo que la muestra deja ver.
    """
    e = x[elegibles(x, d) & (x["fecha"] >= desde) & (x["fecha"] < hasta)]
    sel_todos = e[["fecha", "cik"]]
    m = miembros(e, regla, d, riesgo=riesgo)
    sel = e.loc[m, ["fecha", "cik"]]
    R = matriz_de_retornos(x[x["fecha"] <= hasta])
    gr, gu = retorno_de_grupo(sel, R, d), retorno_de_grupo(sel_todos, R, d)
    ventana = (gr.index > desde) & (gr.index <= hasta)
    exceso = (gr - gu)[ventana].dropna()
    sims = {
        "base": (simular(sel, x, desde=desde, hasta=hasta, d=d), simular(sel_todos, x, desde=desde, hasta=hasta, d=d)),
        "rezago": (simular(sel, x, desde=desde, hasta=hasta, d=d, rezago=1),
                   simular(sel_todos, x, desde=desde, hasta=hasta, d=d, rezago=1)),
        "doble_costo": (simular(sel, x, desde=desde, hasta=hasta, d=d, multiplicador_de_costos=2.0),
                        simular(sel_todos, x, desde=desde, hasta=hasta, d=d, multiplicador_de_costos=2.0)),
        "rotando": (simular(sel, x, desde=desde, hasta=hasta, d=d, rotar_cada=d.horizonte),
                    simular(sel_todos, x, desde=desde, hasta=hasta, d=d)),
    }
    adelante = _adelante(R, d)
    trampa = e.loc[m].merge(adelante.stack().rename("r12").reset_index(), on=["fecha", "cik"], how="left")
    trampa_u = e.merge(adelante.stack().rename("r12").reset_index(), on=["fecha", "cik"], how="left")
    salida = {
        "regla": regla, "hipotesis": SENALES.get(regla, (0, "S8" if regla in COMPUESTAS else "D1"))[1],
        "muestra": muestra, "trimestres": int(len(exceso)),
        "escogidos_promedio": float(sel.groupby("fecha").size().mean()) if len(sel) else 0.0,
        "elegibles_promedio": float(sel_todos.groupby("fecha").size().mean()),
        "tir": sims["base"][0].tir, "tir_todos": sims["base"][1].tir,
        "mejora": sims["base"][0].tir - sims["base"][1].tir,
        "mejora_con_rezago": sims["rezago"][0].tir - sims["rezago"][1].tir,
        "mejora_doble_costo": sims["doble_costo"][0].tir - sims["doble_costo"][1].tir,
        "mejora_rotando": sims["rotando"][0].tir - sims["rotando"][1].tir,
        "caida_maxima": sims["base"][0].caida_maxima, "caida_maxima_todos": sims["base"][1].caida_maxima,
        "exceso_anual": _anual(gr[ventana]) - _anual(gu[ventana]),
        "t_newey_west": estadistica.newey_west_t(exceso.to_numpy(), d.rezago_nw) if len(exceso) > 8 else np.nan,
        "recortes": float(e.loc[m, "recorte_siguiente"].mean()),
        "recortes_todos": float(e["recorte_siguiente"].mean()),
        "desplomes": float((trampa["r12"] <= d.desplome).mean()),
        "desplomes_todos": float((trampa_u["r12"] <= d.desplome).mean()),
        "apuestas": apuestas_efectivas(sel, R, gu, d),
    }
    if regla in SENALES:
        ic = correlacion_de_rangos(e, regla, adelante)
        ic = ic[(ic.index >= desde) & (ic.index <= hasta - pd.offsets.QuarterEnd(d.horizonte))]
        salida.update({"ic_medio": float(ic.mean()), "ic_positivos": float((ic > 0).mean())})
    else:
        salida.update({"ic_medio": np.nan, "ic_positivos": np.nan})
    cortes = (desde, *mitades, hasta)
    for i in range(len(cortes) - 1):
        a, b = cortes[i], cortes[i + 1]
        tramo = (gr.index > a) & (gr.index <= b)
        salida[f"exceso_{a:%Y}_{b:%Y}"] = _anual(gr[tramo]) - _anual(gu[tramo])
    salida["_exceso_trimestral"] = exceso
    if registrar:
        bitacora.registrar(fase="6", familia="seleccion", prueba=regla, muestra=muestra,
                           parametros={"desde": f"{desde:%Y-%m-%d}", "hasta": f"{hasta:%Y-%m-%d}"},
                           metrica="mejora_aportacion", valor=round(float(salida["mejora"]), 6), ruta=ruta_bitacora)
    return salida


# --------------------------------------------------------------------------------------
# El orden de la fase: desarrollo, filtro, validación y prueba final
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Filtro6:
    """Lo que una regla tiene que cumplir en desarrollo para pasar a validación (pre-registro)."""

    mejora_minima: float = 0.0              # le gana a aportar a todos, después de impuestos
    con_rezago_y_doble_costo: bool = True   # y sigue ganando con un trimestre de retraso y doble comisión
    en_las_dos_mitades: bool = True         # exceso bruto positivo en 2012-2013 y en 2014-2015
    ic_positivo: bool = True                # para las señales: correlación de rangos promedio positiva


FILTRO6 = Filtro6()
MITAD_DE_DESARROLLO = pd.Timestamp("2013-12-31")
MITAD_DE_VALIDACION = pd.Timestamp("2020-12-31")


def pasa_el_filtro(f: dict, filtro: Filtro6 = FILTRO6) -> bool:
    ok = f["mejora"] > filtro.mejora_minima
    if filtro.con_rezago_y_doble_costo:
        ok &= f["mejora_con_rezago"] > 0 and f["mejora_doble_costo"] > 0
    if filtro.en_las_dos_mitades:
        mitades = [v for k, v in f.items() if k.startswith("exceso_") and k[7:11].isdigit()]
        ok &= len(mitades) >= 2 and all(np.isfinite(v) and v > 0 for v in mitades)
    if filtro.ic_positivo and np.isfinite(f.get("ic_medio", np.nan)):
        ok &= f["ic_medio"] > 0
    return bool(ok)


def pasa_la_validacion(f: dict) -> bool:
    """Criterio 1 de la fase 0 en validación, con retraso y doble costo, y exceso bruto positivo."""
    return bool(f["mejora"] >= CRITERIOS.mejora_minima_de_tir and f["mejora_con_rezago"] > 0
                and f["mejora_doble_costo"] > 0 and f["exceso_anual"] > 0)


@dataclass
class ResultadoFase6:
    desarrollo: pd.DataFrame
    candidatas: list[str]
    pbo: float
    sharpe_deflactado: float
    mejor: str
    intentos: int
    recortes: dict = field(default_factory=dict)
    despues_del_recorte: dict = field(default_factory=dict)
    validacion: pd.DataFrame = field(default_factory=pd.DataFrame)
    final: pd.DataFrame = field(default_factory=pd.DataFrame)
    veredicto: str = ""


def primera_fecha(x: pd.DataFrame, d: Diseno6 = DISENO6) -> pd.Timestamp:
    """El primer trimestre con suficientes elegibles con estados financieros para formar carteras."""
    e = x[elegibles(x, d) & x["ffo_12m"].notna()]
    cuenta = e.groupby("fecha").size()
    return pd.Timestamp(cuenta[cuenta >= d.elegibles_minimos].index.min())


def _tabla(filas: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{k: v for k, v in f.items() if not k.startswith("_")} for f in filas])


def correr_desarrollo(panel: pd.DataFrame, *, d: Diseno6 = DISENO6, registrar: bool = True,
                      ruta_bitacora=None) -> ResultadoFase6:
    """Las 16 reglas en desarrollo (panel ya recortado a 2015), el filtro y las pruebas múltiples."""
    x = senales(panel, d)
    desde, hasta = primera_fecha(x, d), MUESTRAS.desarrollo_hasta
    filas = [evaluar(r, x, desde=desde, hasta=hasta, muestra="desarrollo", d=d, registrar=registrar,
                     ruta_bitacora=ruta_bitacora, mitades=(MITAD_DE_DESARROLLO,)) for r in REGLAS]
    tabla = _tabla(filas)
    tabla["pasa"] = [pasa_el_filtro(f) for f in filas]
    matriz = pd.DataFrame({f["regla"]: f["_exceso_trimestral"] for f in filas})
    sharpes = matriz.apply(lambda c: estadistica.sharpe(c.dropna().to_numpy()))
    mejor = str(sharpes.idxmax())
    intentos = bitacora.intentos("seleccion", ruta=ruta_bitacora) if registrar else len(REGLAS)
    dsr = estadistica.sharpe_deflactado(matriz[mejor].dropna().to_numpy(), intentos=max(intentos, len(REGLAS)),
                                        varianza_de_sharpes=float(sharpes.var()))
    pbo = estadistica.pbo(matriz, bloques=d.bloques_pbo)
    candidatas = tabla[tabla["pasa"]].sort_values("mejora", ascending=False)["regla"].head(d.maximo_a_validacion)
    adelante = _adelante(matriz_de_retornos(x), d)
    e = x[elegibles(x, d)]
    univ = e.merge(adelante.stack().rename("r12").reset_index(), on=["fecha", "cik"]).groupby("fecha")["r12"].mean()
    d3 = despues_del_recorte(e, adelante, univ)
    return ResultadoFase6(tabla, list(candidatas), pbo, dsr, mejor, intentos,
                          despues_del_recorte=_resumen_d3(d3))


def _resumen_d3(d3: pd.Series) -> dict:
    if d3.empty:
        return {"recortes": 0}
    por_fecha = d3.groupby(level=1).mean()
    return {"recortes": int(len(d3)), "exceso_12m_promedio": float(d3.mean()),
            "exceso_12m_mediano": float(d3.median()),
            "t_newey_west": estadistica.newey_west_t(por_fecha.to_numpy(), 4) if len(por_fecha) > 8 else np.nan}


def evaluar_detector(x: pd.DataFrame, riesgo: pd.Series, *, desde: pd.Timestamp, hasta: pd.Timestamp,
                     d: Diseno6 = DISENO6) -> dict:
    """D1 fuera de muestra: AUC y Brier contra la frecuencia histórica de recortes."""
    e = x[elegibles(x, d) & (x["fecha"] >= desde) & (x["fecha"] <= hasta - pd.offsets.QuarterEnd(d.horizonte))]
    y, p = e["recorte_siguiente"], riesgo.reindex(e.index)
    ok = y.notna() & p.notna()
    y, p, f = y[ok].astype(float), p[ok], e.loc[ok, "fecha"]
    if ok.sum() == 0:
        return {"pronosticos": 0}
    # La referencia: la frecuencia de recortes de todo lo anterior cuyo resultado ya se conocía.
    todos = x[elegibles(x, d) & x["recorte_siguiente"].notna()]
    base = f.map(lambda t: todos.loc[todos["fecha"] <= t - pd.offsets.QuarterEnd(d.horizonte),
                                     "recorte_siguiente"].mean())
    brier, brier_base = float(((p - y) ** 2).mean()), float(((base - y) ** 2).mean())
    variables = {}
    for v in VARIABLES_DE_RECORTE:
        s = e.loc[ok, v]
        signo = -1 if v in ("distancia_al_default", "momentum", "tamano", "crecimiento_ffo") else 1
        variables[v] = auc(y.to_numpy(), signo * s.to_numpy())
    return {"pronosticos": int(ok.sum()), "recortes": int(y.sum()), "auc": auc(y.to_numpy(), p.to_numpy()),
            "brier": brier, "brier_base": brier_base, "habilidad_brier": 1 - brier / brier_base,
            "auc_por_variable": variables}


def correr_validacion(panel_completo: pd.DataFrame, candidatas: list[str], *, d: Diseno6 = DISENO6,
                      ruta_bitacora=None) -> tuple[pd.DataFrame, dict, dict]:
    """La validación, una vez: las candidatas y el detector, de 2016 en adelante, emisores abiertos."""
    x = senales(panel_completo, d)
    desde = MUESTRAS.desarrollo_hasta
    hasta = pd.Timestamp(x["fecha"].max())
    riesgo = riesgo_de_recorte(x, d)
    filas = [evaluar(r, x, desde=desde, hasta=hasta, muestra="validacion", d=d, riesgo=riesgo,
                     ruta_bitacora=ruta_bitacora, mitades=(MITAD_DE_VALIDACION,))
             for r in [*candidatas, DETECTOR]]
    tabla = _tabla(filas)
    tabla["pasa"] = [pasa_la_validacion(f) for f in filas]
    detector = evaluar_detector(x, riesgo, desde=desde, hasta=hasta, d=d)
    adelante = _adelante(matriz_de_retornos(x), d)
    e = x[elegibles(x, d) & (x["fecha"] >= desde)]
    univ = e.merge(adelante.stack().rename("r12").reset_index(), on=["fecha", "cik"]).groupby("fecha")["r12"].mean()
    return tabla, detector, _resumen_d3(despues_del_recorte(e, adelante, univ))


def veredicto_final(f: dict, *, pbo: float, dsr: float, d: Diseno6 = DISENO6) -> str:
    """APROBADO solo si cumple todo en los sellados; INCONCLUSO si gana pero falla otra cosa."""
    gana = f["mejora"] >= CRITERIOS.mejora_minima_de_tir
    if not gana:
        return "RECHAZADO"
    mitades = [v for k, v in f.items() if k.startswith("exceso_") and k[7:11].isdigit()]
    todo = (gana and f["mejora_con_rezago"] > 0 and f["mejora_doble_costo"] > 0
            and all(v > 0 for v in mitades) and dsr >= CRITERIOS.sharpe_deflactado_minimo
            and pbo <= CRITERIOS.pbo_maximo and f["apuestas"] >= CRITERIOS.apuestas_efectivas_minimas)
    return "APROBADO" if todo else "INCONCLUSO"


MODELO_FINAL = "seleccion-fase6"


def correr_final(panel_abierto: pd.DataFrame, regla: str, *, d: Diseno6 = DISENO6, pbo: float, dsr: float,
                 ruta_bitacora=None, raiz_sellado=None) -> tuple[dict, str]:
    """La prueba final, una vez: congela la regla, abre los sellados y la evalúa de 2012 en adelante.

    El detector, si es la regla, se estima solo con los emisores abiertos y pronostica a los
    sellados: nunca ve a quien va a calificar.
    """
    from src.investigacion import emisores
    from src.investigacion.muestras import abrir_sellado, congelar

    congelar(f"{MODELO_FINAL}: {regla}", {"regla": regla, "diseno": repr(d)}, ruta_bitacora=ruta_bitacora)
    sellado = abrir_sellado(emisores.ARCHIVO_SELLADO, modelo_congelado=f"{MODELO_FINAL}: {regla}",
                            raiz=raiz_sellado, ruta_bitacora=ruta_bitacora)
    sellado = sellado.assign(cik=sellado["cik"].astype(str).str.zfill(10), fecha=pd.to_datetime(sellado["fecha"]))
    for c in ("salida", "split", "es_reit", "de_capital"):
        if c in sellado:
            sellado[c] = sellado[c].astype(bool)
    x = senales(sellado, d)
    riesgo = None
    if regla == DETECTOR:
        riesgo = riesgo_de_recorte(x, d, entrenar_con=senales(panel_abierto, d))
    desde, hasta = primera_fecha(x, d), pd.Timestamp(x["fecha"].max())
    f = evaluar(regla, x, desde=desde, hasta=hasta, muestra="final", d=d, riesgo=riesgo, ruta_bitacora=ruta_bitacora,
                mitades=(MUESTRAS.desarrollo_hasta,))
    return f, veredicto_final(f, pbo=pbo, dsr=dsr, d=d)


def pasa_la_validacion_el_detector(f: dict, detector: dict, d: Diseno6 = DISENO6) -> bool:
    return pasa_la_validacion(f) and np.isfinite(detector.get("auc", np.nan)) and detector["auc"] >= d.auc_minima


def correr(panel: pd.DataFrame, *, d: Diseno6 = DISENO6, ruta_bitacora=None, raiz_sellado=None) -> ResultadoFase6:
    """La fase completa en el orden del pre-registro: desarrollo, filtro, validación y, solo si
    una regla la pasa, la prueba final con los sellados."""
    from src.investigacion.muestras import Muestra, recortar

    desarrollo = recortar(panel, Muestra.DESARROLLO, columna="fecha")
    r = correr_desarrollo(desarrollo, d=d, ruta_bitacora=ruta_bitacora)
    completo = recortar(panel, Muestra.VALIDACION, columna="fecha", ruta_bitacora=ruta_bitacora,
                        motivo="fase 6: candidatas del filtro de desarrollo y el detector de recortes, según el "
                               "pre-registro")
    tabla, detector, d3 = correr_validacion(completo, r.candidatas, d=d, ruta_bitacora=ruta_bitacora)
    pasa = [f["pasa"] and (f["regla"] != DETECTOR or pasa_la_validacion_el_detector(f, detector, d))
            for _, f in tabla.iterrows()]
    tabla["pasa"] = pasa
    r.validacion, r.recortes = tabla, detector
    r.despues_del_recorte = {"desarrollo": r.despues_del_recorte, "validacion": d3}
    if not any(pasa):
        r.veredicto = "RECHAZADO"
        return r
    elegida = str(tabla[tabla["pasa"]].sort_values("mejora", ascending=False)["regla"].iloc[0])
    f, veredicto = correr_final(panel, elegida, d=d, pbo=r.pbo, dsr=r.sharpe_deflactado, ruta_bitacora=ruta_bitacora,
                                raiz_sellado=raiz_sellado)
    r.final, r.veredicto = _tabla([f]), veredicto
    return r


# --------------------------------------------------------------------------------------
# Informe
# --------------------------------------------------------------------------------------

NOMBRES = {
    "momentum": "Momentum (meses 12 a 3)", "apalancamiento": "Apalancamiento bajo",
    "distancia_al_default": "Lejos del default", "volatilidad": "Volatilidad baja",
    "rendimiento_de_la_empresa": "Rendimiento de la empresa (cap rate)", "rendimiento_ffo": "Rendimiento FFO alto",
    "rendimiento_del_dividendo": "Yield de dividendo alto", "crecimiento_de_activos": "Crecimiento de activos bajo",
    "rentabilidad": "Rentabilidad (FFO / activos)", "tamano": "Tamaño grande",
    "yield_contra_su_historia": "Yield alto contra su historia", "crecimiento_del_dividendo": "Crecimiento del dividendo",
    "payout": "Payout bajo", "calidad": "Calidad", "calidad y barato": "Calidad y barato (FFO)",
    "calidad y barato contra su historia": "Calidad y barato contra su historia", DETECTOR: "Sin riesgo de recorte",
}


def _p(v, d: int = 1) -> str:
    return "—" if pd.isna(v) else f"{v * 100:.{d}f}%"


def _pb(v) -> str:
    if pd.isna(v):
        return "—"
    x = round(v * 1e4)
    return f"{x:+,d}" if x else "0"


def _md(filas: list[list[str]], encabezado: list[str]) -> str:
    return ("\n| " + " | ".join(encabezado) + " |\n|" + "|".join("---" for _ in encabezado) + "|\n"
            + "".join("| " + " | ".join(f) + " |\n" for f in filas) + "\n")


def tabla_de_reglas(t: pd.DataFrame, *, con_pasa: bool = True) -> str:
    mitades = [c for c in t.columns if c.startswith("exceso_") and c[7:11].isdigit()]
    filas = []
    for _, f in t.sort_values("mejora", ascending=False).iterrows():
        fila = [NOMBRES.get(f["regla"], f["regla"]), f["hipotesis"], _pb(f["mejora"]), _pb(f["mejora_con_rezago"]),
                _pb(f["mejora_doble_costo"]), _pb(f["mejora_rotando"]), _p(f["exceso_anual"]),
                "—" if pd.isna(f["t_newey_west"]) else f"{f['t_newey_west']:+.2f}",
                *[_p(f[m]) for m in mitades],
                "—" if pd.isna(f["ic_medio"]) else f"{f['ic_medio']:+.3f}",
                f"{_p(f['recortes'], 0)} / {_p(f['recortes_todos'], 0)}",
                f"{_p(f['desplomes'], 0)} / {_p(f['desplomes_todos'], 0)}", f"{f['escogidos_promedio']:.0f}"]
        if con_pasa:
            fila.append("sí" if f["pasa"] else "no")
        filas.append(fila)
    encabezado = ["Regla", "Hip.", "Mejora TIR (pb)", "Con retraso (pb)", "Doble costo (pb)", "Rotando (pb)",
                  "Exceso bruto", "t NW", *[f"Exceso {m[7:11]}-{m[12:16]}" for m in mitades], "Corr. rangos",
                  "Recortes (regla / todos)", "Desplomes (regla / todos)", "Escogidos"]
    return _md(filas, encabezado + (["Pasa"] if con_pasa else []))


def informe(r: ResultadoFase6) -> str:
    """El informe de la fase 6 en Markdown, con el veredicto que dicta el pre-registro."""
    d = r.desarrollo
    o = ["# Fase 6: ¿en cuáles REITs? Resultados\n\n",
         "Pre-registro: `fase6_preregistro.md` (commit anterior a esta corrida). Generado por "
         "`python scripts/investigacion.py fase6`. Mejoras en puntos base al año de TIR después de impuestos del "
         "SIC, aportando 3,000 dólares por trimestre a los escogidos sin vender nunca, contra lo mismo a todos los "
         "elegibles. «Exceso bruto»: antes de impuestos, cohortes de 12 meses encimadas. «Recortes»: fracción que "
         "recortó el dividendo o quebró en los 12 meses siguientes. «Desplomes»: fracción que perdió 30% o más.\n\n"]
    o.append(f"## Veredicto: {r.veredicto}\n\n")
    o.append(f"**Desarrollo: {int(d['pasa'].sum())} de {len(d)} reglas pasan el filtro**"
             + (f" (a validación: {', '.join(NOMBRES.get(c, c) for c in r.candidatas)})" if r.candidatas else "")
             + f". PBO = {r.pbo:.2f} (umbral 0.20); Sharpe deflactado de la mejor por Sharpe («"
             f"{NOMBRES.get(r.mejor, r.mejor)}») = {r.sharpe_deflactado:.3f} (umbral 0.95), con {r.intentos} intentos "
             "en la bitácora.\n\n")
    if len(r.validacion):
        o.append("## Validación (2016 en adelante, emisores no sellados)\n")
        o.append(tabla_de_reglas(r.validacion))
    det = r.recortes or {}
    if det.get("pronosticos"):
        o.append("## El detector de recortes, fuera de muestra (validación)\n\n"
                 f"{det['pronosticos']:,} pronósticos, {det['recortes']:,} recortes o quiebras. AUC = {det['auc']:.3f} "
                 f"(umbral 0.70); Brier {det['brier']:.4f} contra {det['brier_base']:.4f} de la frecuencia histórica "
                 f"(habilidad {det['habilidad_brier'] * 100:+.1f}%). AUC de cada variable sola: "
                 + ", ".join(f"{k} {v:.2f}" for k, v in det["auc_por_variable"].items() if pd.notna(v)) + ".\n\n")
    d3 = r.despues_del_recorte or {}
    if d3:
        o.append("## ¿Vender después de un recorte? (D3)\n\n")
        for muestra, v in d3.items():
            if v.get("recortes"):
                o.append(f"* {muestra.capitalize()}: {v['recortes']} recortes nuevos; en los 12 meses siguientes "
                         f"rindieron {_p(v['exceso_12m_promedio'])} contra el universo en promedio (mediana "
                         f"{_p(v['exceso_12m_mediano'])}, t = {v['t_newey_west']:+.2f}).\n")
        o.append("\n")
    if len(r.final):
        o.append("## Prueba final (emisores sellados)\n")
        o.append(tabla_de_reglas(r.final, con_pasa=False))
    o.append("## Todas las reglas, en desarrollo\n")
    o.append(tabla_de_reglas(d))
    return "".join(o)
