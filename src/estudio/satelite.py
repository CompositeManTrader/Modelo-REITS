"""Núcleo y satélite: SCHH más un satélite de REITs escogidos con una regla de la fase 6.

Pre-registro: ``docs/estudios/satelite_preregistro.md``, en el mismo commit que este archivo y
antes de correrlo con datos reales.

A. **Exploratoria** (``correr_exploratoria``): con el panel de la fase 6, que ya se vio, cuatro
   satélites contra SCHH real y contra el índice que SCHH sigue hoy. No confirma nada.
B. **En papel** (``elegir``, ``anotar`` y ``evaluar``): momentum congelado, aportaciones teóricas
   cada trimestre desde noviembre de 2026 contra SCHH. Es la única prueba con datos que nadie
   ha visto.

Toda la contabilidad es la de la fase 6 (``fase6.simular``): las referencias entran al
simulador como un emisor más, así que satélite y referencia nunca difieren por las cuentas.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import DIR_ESTUDIOS
from src.investigacion import bitacora, exploracion, fase6, muestras
from src.investigacion.diseno import CRITERIOS, PERFILES
from src.investigacion.muestras import Muestra

DIR_SATELITE = DIR_ESTUDIOS / "satelite"
FAMILIA = "satelite"
MOTIVO = "núcleo y satélite contra SCHH (16-oct-2026), exploratoria: el panel de la fase 6 ya se vio"
PERFIL = "broker_35"
NUCLEO = "SCHH"
PESO_SATELITE = 0.15
SATELITES = ("todos", "momentum", "calidad", "calidad y barato contra su historia")
REFERENCIAS = {"SCHH": "SCHH real", "indice": "Índice que sigue SCHH hoy"}
COSTO_DEL_INDICE = 0.0007          # lo que cobra SCHH al año
DESDE = pd.Timestamp("2011-03-31")  # el primer trimestre completo de SCHH
TRAMOS = (pd.Timestamp("2015-12-31"), pd.Timestamp("2020-12-31"))
APORTACION = fase6.DISENO6.aportacion_trimestral

# La prueba en papel, congelada en el pre-registro.
REGLA_EN_PAPEL = "momentum"
MESES_DE_APORTACION = (2, 5, 8, 11)
PRIMERA_APORTACION = pd.Timestamp("2026-11-30")
APORTACIONES = 12
APORTACIONES_ANTES_DE_ABANDONAR = 8
UMBRAL_DE_ABANDONO = -0.02
VEREDICTO_EN = pd.Timestamp("2029-11-30")
MEJORA_MINIMA = CRITERIOS.mejora_minima_de_tir


class PanelAtrasado(RuntimeError):
    """El panel de emisores todavía no llega al trimestre que toca."""


class FueraDeCalendario(ValueError):
    """La aportación no está en el calendario o ya pasó su fecha."""


# --------------------------------------------------------------------------------------
# Series trimestrales y referencias como emisores
# --------------------------------------------------------------------------------------


def trimestral(m: pd.DataFrame, *, costo_anual: float = 0.0) -> pd.DataFrame:
    """De mensual (``retorno_total`` y ``retorno_ingreso``) a trimestral: retorno compuesto y dividendo.

    Solo trimestres con sus tres meses. ``costo_anual`` se resta al retorno de cada mes.
    """
    d = pd.DataFrame({"r": (m["retorno_total"] - costo_anual / 12).to_numpy(), "i": m["retorno_ingreso"].to_numpy(),
                      "q": (m.index + pd.offsets.QuarterEnd(0)).normalize()}).dropna()
    g = d.groupby("q")
    t = pd.DataFrame({"retorno": g["r"].apply(lambda s: float((1 + s).prod() - 1)), "dividendo": g["i"].sum(),
                      "meses": g.size()})
    t.index = pd.DatetimeIndex(t.index)
    return t[t["meses"] == 3].drop(columns="meses")


def como_emisor(t: pd.DataFrame, cik: str) -> pd.DataFrame:
    """Una serie trimestral con las columnas que lee ``fase6.simular``."""
    return pd.DataFrame({"cik": cik, "fecha": t.index, "retorno": t["retorno"].to_numpy(),
                         "dividendo": t["dividendo"].to_numpy(), "salida": False})


def _seudo(clave: str) -> str:
    return f"__{clave}__"


def tir_combinada(nucleo: fase6.Simulacion, satelite: fase6.Simulacion, peso_satelite: float = PESO_SATELITE
                  ) -> float:
    """La TIR de aportar ``1 − peso`` al núcleo y ``peso`` al satélite cada periodo (cuentas separadas)."""
    flujos = np.full(len(nucleo.serie), -APORTACION, dtype=float)
    flujos[-1] += (1 - peso_satelite) * nucleo.riqueza_final + peso_satelite * satelite.riqueza_final
    q = fase6._tir(flujos)
    return (1 + q) ** 4 - 1 if np.isfinite(q) else np.nan


def _por_anio(r: pd.Series) -> pd.Series:
    """Retorno de cada año calendario con sus cuatro trimestres."""
    r = r.dropna()
    g = r.groupby(r.index.year)
    return g.apply(lambda s: float((1 + s).prod() - 1))[g.size() == 4]


# --------------------------------------------------------------------------------------
# A. Exploratoria
# --------------------------------------------------------------------------------------


def explorar(panel: pd.DataFrame, schh_mensual: pd.DataFrame, indice_mensual: pd.DataFrame, *,
             registrar: bool = True, ruta_bitacora=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cada satélite contra cada referencia: TIR neta, cartera 85/15, exceso bruto y su estabilidad."""
    x = fase6.senales(panel)
    refs = {"SCHH": trimestral(schh_mensual), "indice": trimestral(indice_mensual, costo_anual=COSTO_DEL_INDICE)}
    hasta = min(x["fecha"].max(), *(t.index.max() for t in refs.values()))
    e = x[fase6.elegibles(x) & (x["fecha"] >= DESDE) & (x["fecha"] < hasta)]
    todos = e[["fecha", "cik"]]
    xs = pd.concat([x, *(como_emisor(t, _seudo(k)) for k, t in refs.items())], ignore_index=True)
    fechas = sorted(f for f in x["fecha"].unique() if DESDE <= f < hasta)
    kw = {"desde": DESDE, "hasta": hasta, "objetivo": PERFILES[PERFIL], "respaldo": todos}
    sim_ref = {k: fase6.simular(pd.DataFrame({"fecha": fechas, "cik": _seudo(k)}), xs, **kw) for k in refs}
    R = fase6.matriz_de_retornos(x[x["fecha"] <= hasta])
    cortes = (DESDE, *TRAMOS, hasta)
    filas, anios = [], {f"{REFERENCIAS[k]}": _por_anio(t["retorno"][(t.index > DESDE) & (t.index <= hasta)])
                        for k, t in refs.items()}
    for s in SATELITES:
        sel = e.loc[fase6.miembros(e, s), ["fecha", "cik"]]
        sim = fase6.simular(sel, xs, **kw)
        gr = fase6.retorno_de_grupo(sel, R)
        anios[s] = _por_anio(gr[(gr.index > DESDE) & (gr.index <= hasta)])
        for k, t in refs.items():
            ref = t["retorno"].reindex(gr.index)
            comun = gr.notna() & ref.notna() & (gr.index > DESDE) & (gr.index <= hasta)
            por_anio = _por_anio(gr[comun]) - _por_anio(ref[comun])
            fila = {"satelite": s, "referencia": k, "desde": DESDE, "hasta": hasta, "trimestres": int(comun.sum()),
                    "escogidos_promedio": float(sel.groupby("fecha").size().mean()) if len(sel) else 0.0,
                    "tir_satelite": sim.tir, "tir_referencia": sim_ref[k].tir, "mejora": sim.tir - sim_ref[k].tir,
                    "tir_cartera": tir_combinada(sim_ref[k], sim), "mejora_cartera": tir_combinada(sim_ref[k], sim)
                    - sim_ref[k].tir, "exceso_anual": fase6._anual(gr[comun]) - fase6._anual(ref[comun]),
                    "anios_ganados": int((por_anio > 0).sum()), "anios": int(por_anio.notna().sum()),
                    "caida_satelite": sim.caida_maxima, "caida_referencia": sim_ref[k].caida_maxima}
            for i in range(len(cortes) - 1):
                a, b = cortes[i], cortes[i + 1]
                tramo = comun & (gr.index > a) & (gr.index <= b)
                fila[f"exceso_{(a + pd.Timedelta(days=1)):%Y}_{b:%Y}"] = (fase6._anual(gr[tramo])
                                                                          - fase6._anual(ref[tramo]))
            filas.append(fila)
            if registrar:
                bitacora.registrar(fase="estudio", familia=FAMILIA, prueba=f"{s} contra {k}", muestra="exploratoria",
                                   parametros={"desde": f"{DESDE:%Y-%m-%d}", "hasta": f"{hasta:%Y-%m-%d}",
                                               "peso_satelite": PESO_SATELITE, "perfil": PERFIL},
                                   metrica="mejora_aportacion", valor=round(float(fila["mejora"]), 6),
                                   ruta=ruta_bitacora)
    a = pd.DataFrame(anios)
    a.index.name = "anio"
    return pd.DataFrame(filas), a.reset_index()


@dataclass
class Resultado:
    tablas: dict[str, pd.DataFrame]
    notas: dict = field(default_factory=dict)

    def __getitem__(self, nombre: str) -> pd.DataFrame:
        return self.tablas.get(nombre, pd.DataFrame())


def correr_exploratoria(*, ruta_bitacora=None) -> Resultado:
    """Carga el panel abierto, SCHH y el índice (registra las aperturas) y explora."""
    from src.estudio import etfs
    from src.investigacion import emisores

    panel, _ = emisores.cargar()
    panel = muestras.recortar(panel, Muestra.VALIDACION, columna="fecha", motivo=f"{MOTIVO} (emisores)",
                              ruta_bitacora=ruta_bitacora)
    indice = exploracion.sector(Muestra.VALIDACION, motivo=f"{MOTIVO} (índice)", ruta_bitacora=ruta_bitacora)
    guardados = etfs.cargar_datos()
    if guardados is None:
        raise RuntimeError("Faltan los datos de los ETFs: corre `python scripts/estudio.py etfs` primero.")
    schh = etfs.series(*guardados)[NUCLEO]
    tabla, anios = explorar(panel, schh, indice, ruta_bitacora=ruta_bitacora)
    return Resultado({"exploratoria": tabla, "anios": anios},
                     {"perfil": PERFIL, "peso_satelite": PESO_SATELITE, "emisores": int(panel["cik"].nunique()),
                      "intentos_satelite": bitacora.intentos(FAMILIA, ruta=ruta_bitacora)})


# --------------------------------------------------------------------------------------
# B. En papel
# --------------------------------------------------------------------------------------


def calendario() -> list[pd.Timestamp]:
    meses = pd.date_range(PRIMERA_APORTACION, periods=APORTACIONES * 3, freq="ME")
    return [f for f in meses if f.month in MESES_DE_APORTACION][:APORTACIONES]


def trimestre_del_panel(fecha_aportacion: pd.Timestamp) -> pd.Timestamp:
    """El trimestre que cerró dos meses antes de la aportación: sus 13F ya se presentaron."""
    return (pd.Timestamp(fecha_aportacion) - pd.DateOffset(months=2)) + pd.offsets.MonthEnd(0)


def aportacion_que_toca(hoy: dt.date | pd.Timestamp) -> pd.Timestamp | None:
    """La aportación del mes en curso, si este mes toca."""
    fin = pd.Timestamp(hoy).normalize() + pd.offsets.MonthEnd(0)
    return fin if fin in calendario() else None


def _primer_ticker(t) -> str | None:
    if not isinstance(t, str) or not t.strip():
        return None
    return t.split("|")[0].strip() or None


def elegir(panel: pd.DataFrame, ficha: pd.DataFrame, fecha_aportacion: pd.Timestamp) -> pd.DataFrame:
    """Lo que la regla congelada compra en una aportación: los escogidos y la aportación a SCHH."""
    q = trimestre_del_panel(fecha_aportacion)
    if panel["fecha"].max() < q:
        raise PanelAtrasado(f"El panel llega a {panel['fecha'].max():%Y-%m-%d} y esta aportación usa {q:%Y-%m-%d}: "
                            "actualízalo con `python scripts/investigacion.py emisores`.")
    x = fase6.senales(panel[panel["fecha"] <= q])
    e = x[fase6.elegibles(x) & (x["fecha"] == q)]
    esc = e.loc[fase6.miembros(e, REGLA_EN_PAPEL), ["cik", "momentum"]]
    esc = esc.merge(ficha[["cik", "nombre", "tickers"]], on="cik", how="left")
    esc["ticker"] = esc["tickers"].map(_primer_ticker)
    sin_ticker = esc.loc[esc["ticker"].isna(), "nombre"].fillna(esc["cik"]).tolist()
    esc = esc.dropna(subset=["ticker"]).sort_values("momentum", ascending=False)
    if esc.empty:
        raise ValueError(f"La regla no escogió a nadie en {q:%Y-%m-%d}.")
    satelite = esc.assign(cartera="satelite", monto=APORTACION / len(esc))
    nucleo = pd.DataFrame([{"cik": "", "nombre": "Schwab U.S. REIT ETF", "ticker": NUCLEO, "momentum": np.nan,
                            "cartera": "nucleo", "monto": APORTACION}])
    filas = pd.concat([satelite, nucleo], ignore_index=True)
    filas.insert(0, "trimestre_del_panel", q)
    filas.insert(0, "fecha_aportacion", pd.Timestamp(fecha_aportacion))
    filas = filas[["fecha_aportacion", "trimestre_del_panel", "cartera", "ticker", "cik", "nombre", "momentum", "monto"]]
    filas.attrs["sin_ticker"] = sin_ticker
    return filas


def leer_papel(ruta: Path | None = None) -> pd.DataFrame:
    origen = ruta or DIR_SATELITE / "papel.csv"
    if not origen.exists():
        return pd.DataFrame(columns=["fecha_aportacion", "trimestre_del_panel", "cartera", "ticker", "cik", "nombre",
                                     "momentum", "monto", "anotado_en", "commit"])
    return pd.read_csv(origen, dtype={"cik": str}, parse_dates=["fecha_aportacion", "trimestre_del_panel"])


def anotar(filas: pd.DataFrame, *, hoy: dt.date | pd.Timestamp | None = None, ruta: Path | None = None) -> Path:
    """Agrega una aportación a la bitácora en papel. Solo en su mes, antes de su cierre, una vez."""
    destino = ruta or DIR_SATELITE / "papel.csv"
    f = pd.Timestamp(filas["fecha_aportacion"].iloc[0])
    hoy = pd.Timestamp(hoy or dt.date.today()).normalize()
    if f not in calendario():
        raise FueraDeCalendario(f"{f:%Y-%m-%d} no está en el calendario pre-registrado.")
    if not (f - pd.offsets.MonthBegin(1) <= hoy <= f):
        raise FueraDeCalendario(f"La aportación del {f:%Y-%m-%d} se anota en su mes y antes de su cierre "
                                f"(hoy es {hoy:%Y-%m-%d}); una que ya pasó se salta.")
    previas = leer_papel(destino)
    if (pd.to_datetime(previas["fecha_aportacion"]) == f).any():
        raise FueraDeCalendario(f"La aportación del {f:%Y-%m-%d} ya está anotada.")
    nuevas = filas.assign(anotado_en=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                          commit=bitacora._commit())
    destino.parent.mkdir(parents=True, exist_ok=True)
    nuevas.to_csv(destino, mode="a", header=not destino.exists(), index=False, date_format="%Y-%m-%d",
                  float_format="%.10g")
    return destino


# --- Precios de lo anotado: se guardan los retornos para no perder a los que dejan de cotizar.


def retornos_de(precios: pd.DataFrame, *, hoy: pd.Timestamp | None = None) -> pd.DataFrame:
    """Retornos mensuales (total y de precio) de los cierres de fin de mes de Yahoo."""
    from src.investigacion import datos

    r = datos.retornos_mensuales(precios[["ticker", "fecha", "cierre", "ajustado"]], hoy=hoy)
    return r.dropna(subset=["retorno_total", "retorno_precio"])[["ticker", "fecha", "retorno_total", "retorno_precio"]]


def combinar_retornos(guardados: pd.DataFrame, nuevos: pd.DataFrame) -> pd.DataFrame:
    """Lo nuevo manda donde se encima; lo guardado se queda donde Yahoo ya no tiene nada."""
    junto = pd.concat([guardados.assign(_orden=0), nuevos.assign(_orden=1)], ignore_index=True)
    junto["fecha"] = pd.to_datetime(junto["fecha"])
    junto = junto.sort_values(["ticker", "fecha", "_orden"]).drop_duplicates(["ticker", "fecha"], keep="last")
    return junto.drop(columns="_orden").reset_index(drop=True)


def cargar_retornos(raiz: Path | None = None) -> pd.DataFrame:
    ruta = (raiz or DIR_SATELITE) / "retornos_papel.csv.gz"
    if not ruta.exists():
        return pd.DataFrame(columns=["ticker", "fecha", "retorno_total", "retorno_precio"])
    return pd.read_csv(ruta, parse_dates=["fecha"])


def actualizar_retornos(papel: pd.DataFrame, *, raiz: Path | None = None) -> tuple[pd.DataFrame, list]:
    """Toca la red: baja de Yahoo lo anotado (y SCHH), lo junta con lo guardado y lo versiona."""
    from src.estudio import universo
    from src.investigacion import datos

    tickers = sorted(set(papel["ticker"]) | {NUCLEO})
    precios, _, _, fallas = universo.bajar_historias(tickers)
    junto = combinar_retornos(cargar_retornos(raiz), retornos_de(precios))
    datos._escribir(junto, (raiz or DIR_SATELITE) / "retornos_papel.csv.gz")
    return junto, fallas


def panel_en_papel(retornos: pd.DataFrame, fechas: list[pd.Timestamp]) -> pd.DataFrame:
    """Cada ticker en cada periodo entre aportaciones: retorno compuesto, dividendo y si dejó de cotizar."""
    filas = []
    for t, g in retornos.groupby("ticker"):
        g = g.set_index("fecha").sort_index()
        ultimo = g.index.max()
        for a, b in zip(fechas[:-1], fechas[1:], strict=True):
            m = g[(g.index > a) & (g.index <= b)]
            if m.empty:
                continue
            filas.append({"cik": t, "fecha": b, "retorno": float((1 + m["retorno_total"]).prod() - 1),
                          "dividendo": float((m["retorno_total"] - m["retorno_precio"]).sum()),
                          "salida": bool(ultimo < b)})
    return pd.DataFrame(filas, columns=["cik", "fecha", "retorno", "dividendo", "salida"])


def evaluar(papel: pd.DataFrame, retornos: pd.DataFrame, *, ultimo_mes: pd.Timestamp | None = None) -> Resultado:
    """La cuenta en papel del satélite contra la de SCHH hasta la última fecha del calendario con datos."""
    hoy = ultimo_mes or (pd.to_datetime(retornos["fecha"]).max() if len(retornos) else pd.NaT)
    papel = papel.assign(fecha_aportacion=pd.to_datetime(papel["fecha_aportacion"]))
    fechas = [f for f in calendario() if pd.notna(hoy) and f <= hoy]
    notas = {"aportaciones_anotadas": int(papel["fecha_aportacion"].nunique()), "primera": f"{PRIMERA_APORTACION:%Y-%m-%d}",
             "veredicto_en": f"{VEREDICTO_EN:%Y-%m-%d}", "evaluado_hasta": None, "estado": "sin aportaciones todavía"}
    aport = (papel[papel["cartera"] == "satelite"].groupby("fecha_aportacion")["ticker"]
             .agg(escogidos="count", tickers=lambda s: ", ".join(s)).reset_index())
    if papel.empty or len(fechas) < 2:
        if not papel.empty:
            notas["estado"] = "todavía no hay un periodo completo entre aportaciones"
        return Resultado({"aportaciones": aport}, notas)
    x = panel_en_papel(retornos, fechas)
    # El simulador toma sus fechas del panel: cada fecha del calendario tiene que estar.
    x = pd.concat([x, pd.DataFrame({"cik": "__calendario__", "fecha": fechas, "retorno": 0.0, "dividendo": 0.0,
                                    "salida": False})], ignore_index=True)
    sel = papel[["fecha_aportacion", "ticker", "cartera"]].rename(columns={"fecha_aportacion": "fecha",
                                                                         "ticker": "cik"})
    kw = {"desde": fechas[0], "hasta": fechas[-1]}
    sin_impuestos = replace(PERFILES[PERFIL], impuesto_dividendo=0.0, impuesto_intereses=0.0, impuesto_ganancia=0.0)
    sims = {}
    for cartera in ("satelite", "nucleo"):
        s = sel[sel["cartera"] == cartera][["fecha", "cik"]]
        sims[cartera] = (fase6.simular(s, x, objetivo=PERFILES[PERFIL], **kw),
                         fase6.simular(s, x, objetivo=sin_impuestos, **kw))
    sat, nuc = sims["satelite"][0], sims["nucleo"][0]
    mejora = sat.tir - nuc.tir
    n = notas["aportaciones_anotadas"]
    if fechas[-1] >= VEREDICTO_EN:
        bruto = sims["satelite"][1].tir - sims["nucleo"][1].tir
        notas["estado"] = ("ÉXITO: el satélite le ganó a SCHH por el criterio" if mejora >= MEJORA_MINIMA and bruto > 0
                           else "SIN ÉXITO: todo en SCHH")
    elif n >= APORTACIONES_ANTES_DE_ABANDONAR and mejora <= UMBRAL_DE_ABANDONO:
        notas["estado"] = "ABANDONO: el satélite va 200 pb al año o más abajo de SCHH"
    else:
        notas["estado"] = "en curso (informativo: el veredicto es en la fecha pre-registrada)"
    notas["evaluado_hasta"] = f"{fechas[-1]:%Y-%m-%d}"
    resumen = pd.DataFrame([{"cartera": c, "tir_neta": sims[c][0].tir, "tir_antes_de_impuestos": sims[c][1].tir,
                             "aportado": sims[c][0].aportado, "valor_final_neto": sims[c][0].riqueza_final,
                             "caida_maxima": sims[c][0].caida_maxima} for c in ("satelite", "nucleo")])
    resumen.attrs["mejora"] = mejora
    notas["mejora"] = float(mejora)
    periodos = pd.DataFrame({"fecha": fechas, "indice_satelite": sat.serie.to_numpy(),
                             "indice_nucleo": nuc.serie.to_numpy()})
    return Resultado({"aportaciones": aport, "resumen": resumen, "periodos": periodos}, notas)


# --------------------------------------------------------------------------------------
# Guardado e informes
# --------------------------------------------------------------------------------------


def guardar(r: Resultado, nombre: str, *, raiz: Path | None = None) -> Path:
    d = (raiz or DIR_SATELITE) / nombre
    d.mkdir(parents=True, exist_ok=True)
    for t, tabla in r.tablas.items():
        if not tabla.empty:
            tabla.to_csv(d / f"{t}.csv", index=False, float_format="%.10g", date_format="%Y-%m-%d")
    (d / "notas.json").write_text(json.dumps(r.notas, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return d


def _p(v, d: int = 1) -> str:
    return "—" if v is None or pd.isna(v) else f"{float(v) * 100:.{d}f}%"


def _pb(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    x = round(float(v) * 1e4)
    return f"{x:+,d}" if x else "0"


def _md(filas: list[list[str]], encabezado: list[str]) -> str:
    return ("\n| " + " | ".join(encabezado) + " |\n|" + "|".join("---" for _ in encabezado) + "|\n"
            + "".join("| " + " | ".join(str(c) for c in f) + " |\n" for f in filas) + "\n")


NOMBRES = {"todos": "Todos por partes iguales", "momentum": "Momentum (meses 12 a 3)", "calidad": "Calidad",
           "calidad y barato contra su historia": "Calidad y barato contra su historia"}


def lectura_exploratoria(r: Resultado) -> str:
    t = r["exploratoria"]
    s = t[t["referencia"] == "indice"].set_index("satelite")
    mejor = s["mejora_cartera"].idxmax()
    o = [f"* **Contra el índice que sigue SCHH hoy, ningún satélite cambia mucho la cartera completa:** con "
         f"{PESO_SATELITE:.0%} en el satélite, la TIR neta de la cartera se mueve entre "
         f"{_pb(s['mejora_cartera'].min())} y {_pb(s['mejora_cartera'].max())} pb al año. El mejor fue "
         f"{NOMBRES[mejor].lower()}.\n"]
    for sat, f in s.iterrows():
        o.append(f"* **{NOMBRES[sat]}:** el satélite solo, {_pb(f['mejora'])} pb al año de TIR neta contra el índice; "
                 f"ganó {int(f['anios_ganados'])} de {int(f['anios'])} años; exceso bruto "
                 f"{_p(f['exceso_2011_2015'])} en 2011-2015, {_p(f['exceso_2016_2020'])} en 2016-2020 y "
                 f"{_p(f[[c for c in s.columns if c.startswith('exceso_2021')][0]])} desde 2021.\n")
    return "".join(o)


def informe_exploratorio(r: Resultado) -> str:
    t = r["exploratoria"]
    hasta = pd.Timestamp(t["hasta"].iloc[0])
    ultima = [c for c in t.columns if c.startswith("exceso_2021")][0]
    o = ["# Núcleo y satélite contra SCHH: exploratoria\n\n",
         "Pre-registro: `satelite_preregistro.md` (commit anterior a esta corrida). Generado por "
         "`python scripts/estudio.py satelite explorar`. **No confirma nada**: el panel de la fase 6 ya se usó para "
         "escoger momentum. La prueba que vale es la de papel (`satelite_en_papel.md`).\n\n",
         f"Emisores abiertos de la fase 6 ({r.notas.get('emisores', '—')} emisores, vivos y muertos), carteras de "
         f"{DESDE:%Y-%m} a {hasta:%Y-%m}, 3,000 dólares por trimestre sin vender nunca, impuestos del broker de EE. UU. "
         f"al 35%. «Cartera» es {1 - PESO_SATELITE:.0%} en la referencia y {PESO_SATELITE:.0%} en el satélite.\n\n",
         "## En corto\n\n", lectura_exploratoria(r), "\n"]
    for k, nombre in REFERENCIAS.items():
        s = t[t["referencia"] == k]
        o.append(f"## Contra {nombre}\n")
        o.append(_md([[NOMBRES[f["satelite"]], f"{f['escogidos_promedio']:.0f}", _p(f["tir_satelite"]),
                       _p(f["tir_referencia"]), _pb(f["mejora"]), _pb(f["mejora_cartera"]), _p(f["exceso_anual"]),
                       _p(f["exceso_2011_2015"]), _p(f["exceso_2016_2020"]), _p(f[ultima]),
                       f"{int(f['anios_ganados'])} de {int(f['anios'])}", _p(f["caida_satelite"]),
                       _p(f["caida_referencia"])] for _, f in s.iterrows()],
                     ["Satélite", "Escogidos", "TIR neta satélite", "TIR neta referencia", "Satélite contra referencia (pb)",
                      f"Cartera {1 - PESO_SATELITE:.0%}/{PESO_SATELITE:.0%} contra referencia (pb)", "Exceso bruto anual",
                      "2011-2015", "2016-2020", f"2021-{hasta:%Y}", "Años ganados", "Caída satélite",
                      "Caída referencia"]))
    a = r["anios"]
    if not a.empty:
        cols = [c for c in a.columns if c != "anio"]
        o.append("## Año por año (retorno bruto)\n")
        o.append(_md([[int(f["anio"]), *[_p(f[c]) for c in cols]] for _, f in a.iterrows()],
                     ["Año", *[NOMBRES.get(c, c) for c in cols]]))
    o.append("## Límites\n\n"
             "* Datos ya vistos: momentum se escogió en la fase 6 con este mismo panel.\n"
             "* SCHH siguió otro índice hasta 2020, con 1.45 puntos al año menos que el índice de la investigación; por "
             "eso también se compara contra el índice que sigue hoy (FTSE Nareit All Equity menos 0.07%).\n"
             "* Los satélites pesan igual a sus escogidos y SCHH pesa por tamaño: parte de la diferencia es pesar "
             "igual, que es lo que mide «todos por partes iguales».\n"
             "* Precios de los 13F (fin de trimestre) y dividendos de XBRL, conocidos a su fecha; los sellados no "
             "entran.\n"
             f"* Bitácora: {len(t)} intentos con la familia `{FAMILIA}` (total de la familia: "
             f"{r.notas.get('intentos_satelite', '—')}), más las aperturas de los datos posteriores a 2016.\n")
    return "".join(o)


def informe_papel(r: Resultado) -> str:
    n = r.notas
    cal = calendario()
    o = ["# Núcleo y satélite en papel\n\n",
         "La prueba hacia adelante del pre-registro (`satelite_preregistro.md`): momentum congelado contra SCHH, "
         "3,000 dólares teóricos a cada cuenta al cierre de febrero, mayo, agosto y noviembre, impuestos del broker "
         "al 35%. Generado por `python scripts/estudio.py satelite evaluar`.\n\n",
         f"* **Estado:** {n.get('estado')}.\n",
         f"* **Aportaciones anotadas:** {n.get('aportaciones_anotadas', 0)} de {APORTACIONES} "
         f"(de {cal[0]:%Y-%m-%d} a {cal[-1]:%Y-%m-%d}).\n",
         f"* **Veredicto:** el {VEREDICTO_EN:%Y-%m-%d}. Éxito si el satélite queda {MEJORA_MINIMA * 1e4:.0f} pb al año "
         "o más arriba de SCHH en TIR neta, con exceso bruto positivo. Abandono si después de "
         f"{APORTACIONES_ANTES_DE_ABANDONAR} aportaciones va {-UMBRAL_DE_ABANDONO * 1e4:.0f} pb o más abajo.\n"]
    if n.get("evaluado_hasta"):
        o.append(f"* **Evaluado hasta:** {n['evaluado_hasta']}; satélite contra SCHH: {_pb(n.get('mejora'))} pb al año "
                 "de TIR neta.\n")
    s = r["resumen"]
    if not s.empty:
        o.append(_md([["Satélite (momentum)" if f["cartera"] == "satelite" else "SCHH", _p(f["tir_neta"]),
                       _p(f["tir_antes_de_impuestos"]), f"{f['aportado']:,.0f}", f"{f['valor_final_neto']:,.0f}",
                       _p(f["caida_maxima"])] for _, f in s.iterrows()],
                     ["Cuenta", "TIR neta", "TIR antes de impuestos", "Aportado (dólares)", "Valor neto (dólares)",
                      "Caída máxima"]))
    a = r["aportaciones"]
    if not a.empty:
        o.append("## Lo que compró el satélite en cada aportación\n")
        o.append(_md([[f"{pd.Timestamp(f['fecha_aportacion']):%Y-%m-%d}", int(f["escogidos"]), f["tickers"]]
                      for _, f in a.iterrows()], ["Aportación", "Escogidos", "Tickers"]))
    return "".join(o)
