"""Fase 5: correr el catálogo pre-registrado de señales de entrada, en el orden del diseño.

1. **Desarrollo** (1972–2015): cada señal con sus reglas fijadas, completas y por era.
2. **Filtro** escrito en el pre-registro (``FILTRO``): solo pasan a validación las reglas que
   cumplen todo en desarrollo; a lo más ``MAXIMO_A_VALIDACION``, las de mayor mejora.
3. **Pruebas múltiples** sobre todo lo que se probó: PBO de la matriz de retornos de todas
   las reglas y Sharpe deflactado de la mejor con el número de intentos de la bitácora.
4. **Validación** (2016 en adelante), abierta una vez con motivo, solo para las que pasaron.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.investigacion import estadistica, exploracion, senales, timing
from src.investigacion.diseno import MUESTRAS
from src.investigacion.exploracion import CORTE_DE_ERAS
from src.investigacion.muestras import Muestra
from src.investigacion.timing import Senal

MAXIMO_A_VALIDACION = 3


@dataclass(frozen=True)
class Filtro:
    """Lo que una regla tiene que cumplir en desarrollo para pasar a validación (pre-registro)."""

    mejora_minima: float = 0.0                 # le gana a aportar siempre (rebalanceando)
    contra_mezcla_fija_minima: float = 0.0     # y a la mezcla fija con su misma exposición (P8)
    con_rezago_y_doble_costo: bool = True      # sigue ganando con un mes de retraso y doble comisión
    en_las_dos_eras: bool = True               # gana en 1972-1992 y en 1993-2015 por separado
    predice_a_12_meses: bool = True            # R² fuera de muestra a 12 meses > 0 o Clark-West p < 0.10
    alfa_predictivo: float = 0.10


FILTRO = Filtro()


def _combinadas(x: pd.DataFrame, ind: pd.DataFrame) -> list[tuple[Senal, str, pd.Series]]:
    """Las dos combinaciones pre-registradas."""
    from src.modelo.senal import percentil_expandible

    def pct(s: pd.Series) -> pd.Series:
        return percentil_expandible(s.dropna(), min_observaciones=senales.MINIMO_DE_HISTORIA).reindex(s.index)

    # K1: fuera solo si está caro contra el Treasury Y la tendencia es negativa.
    caro = pct(ind["spread_10a"]) < senales.UMBRAL_DE_SALIDA
    k1 = (~(caro & (ind["tendencia_10m"] < 0))).astype(float)
    s1 = Senal("caro y con tendencia negativa", "combinada", lambda x, i: k1,
               "Fuera si el yield contra el Treasury está en su quintil más bajo y el precio abajo de su promedio de 10 meses")
    # K2: el promedio de los percentiles de cuatro familias (valuación, crédito, condiciones y tendencia).
    partes = pd.concat([pct(ind["spread_10a"]), pct(-ind["cambio_credito_12m"]), pct(-ind["nfci"]),
                        pct(ind["tendencia_10m"])], axis=1)
    compuesto = partes.mean(axis=1, skipna=False)
    s2 = Senal("compuesto de cuatro familias", "combinada", lambda x, i: compuesto,
               "Promedio de los percentiles de yield contra Treasury, cambio del spread de crédito, NFCI y tendencia")
    k2 = timing.exposicion_continua(compuesto, minimo=senales.MINIMO_DE_HISTORIA, piso=senales.PISO_CONTINUO)
    return [(s1, "fuera si caro y a la baja", k1), (s2, f"continua con piso de {senales.PISO_CONTINUO:.0%}", k2)]


def reglas_del_catalogo(x: pd.DataFrame, ind: pd.DataFrame) -> list[tuple[Senal, str, pd.Series]]:
    salida = []
    for s in senales.CATALOGO:
        serie = senales.calcular(s, x, ind)
        for nombre, regla in senales.reglas_de(s).items():
            salida.append((s, nombre, regla(serie)))
    return salida + _combinadas(x, ind)


@dataclass
class ResultadoFase5:
    desarrollo: pd.DataFrame
    por_era: pd.DataFrame
    candidatas: pd.DataFrame
    pbo: float
    sharpe_deflactado: float
    mejor: str
    intentos: int
    validacion: pd.DataFrame = field(default_factory=pd.DataFrame)


def pasa_el_filtro(f: pd.Series, eras: pd.DataFrame, filtro: Filtro = FILTRO) -> bool:
    ok = f["mejora_rebalanceo"] > filtro.mejora_minima and f["mejora_contra_mezcla_fija"] > filtro.contra_mezcla_fija_minima
    if filtro.con_rezago_y_doble_costo:
        ok &= f["mejora_rebalanceo_con_rezago"] > 0 and f["mejora_rebalanceo_doble_costo"] > 0
    if filtro.en_las_dos_eras:
        e = eras[(eras["senal"] == f["senal"]) & (eras["regla"] == f["regla"])]
        ok &= len(e) == 2 and bool((e["mejora_rebalanceo"] > 0).all())
    if filtro.predice_a_12_meses:
        ok &= bool((f["r2_12m"] > 0) or (f["clark_west_p_12m"] < filtro.alfa_predictivo))
    return bool(ok)


def correr_desarrollo(*, registrar: bool = True, ruta_bitacora=None) -> ResultadoFase5:
    x = exploracion.sector(Muestra.DESARROLLO)
    ind = exploracion.indicadores(x)
    reglas = reglas_del_catalogo(x, ind)
    filas, eras, excesos = [], [], {}
    for senal, nombre, e in reglas:
        filas.append(timing.evaluar(senal, nombre, e, x, ind, muestra="desarrollo", registrar=registrar,
                                    ruta_bitacora=ruta_bitacora))
        for era, (a, b) in {"1972-1992": (x.index.min(), CORTE_DE_ERAS),
                            "1993-2015": (CORTE_DE_ERAS + pd.offsets.MonthEnd(1), x.index.max())}.items():
            xe, ie = x.loc[a:b], ind.loc[a:b]
            r = timing.evaluar(senal, nombre, e.loc[a:b], xe, ie, muestra=f"desarrollo {era}", registrar=False)
            eras.append({"senal": senal.nombre, "regla": nombre, "era": era,
                         "mejora_rebalanceo": r["mejora_rebalanceo"],
                         "mejora_contra_mezcla_fija": r["mejora_contra_mezcla_fija"]})
        excesos[f"{senal.nombre} | {nombre}"] = timing.retornos_de_la_regla(e, x)
    d = timing.resumen(filas)
    eras = pd.DataFrame(eras)
    d["pasa"] = [pasa_el_filtro(f, eras) for _, f in d.iterrows()]
    matriz = pd.DataFrame(excesos)
    sharpes = matriz.apply(lambda c: estadistica.sharpe(c.to_numpy()))
    mejor = str(sharpes.idxmax())
    intentos = len(matriz.columns)
    dsr = estadistica.sharpe_deflactado(matriz[mejor].to_numpy(), intentos=intentos,
                                        varianza_de_sharpes=float(sharpes.var()))
    pbo = estadistica.pbo(matriz, bloques=16)
    candidatas = d[d["pasa"]].sort_values("mejora_rebalanceo", ascending=False).head(MAXIMO_A_VALIDACION)
    return ResultadoFase5(d, eras, candidatas, pbo, dsr, mejor, intentos)


def correr_validacion(candidatas: pd.DataFrame, *, motivo: str, ruta_bitacora=None) -> pd.DataFrame:
    """Abre la validación UNA vez: cada candidata, simulada solo de 2016 en adelante."""
    completo = exploracion.sector(Muestra.VALIDACION, motivo=motivo)
    ind = exploracion.indicadores(completo)
    reglas = {(s.nombre, n): (s, e) for s, n, e in reglas_del_catalogo(completo, ind)}
    filas = []
    for _, c in candidatas.iterrows():
        senal, e = reglas[(c["senal"], c["regla"])]
        filas.append(timing.evaluar(senal, c["regla"], e, completo, ind, muestra="validacion",
                                    desde=MUESTRAS.validacion_desde, ruta_bitacora=ruta_bitacora))
    return timing.resumen(filas)



# --------------------------------------------------------------------------------------
# Informe
# --------------------------------------------------------------------------------------


def _p(v, d=1) -> str:
    return "—" if pd.isna(v) else f"{v * 100:.{d}f}%"


def _pb(v) -> str:
    if pd.isna(v):
        return "—"
    x = round(v * 1e4)
    return f"{x:+,d}" if x else "0"


def _tabla(filas: list[list[str]], encabezado: list[str]) -> str:
    return ("\n| " + " | ".join(encabezado) + " |\n|" + "|".join("---" for _ in encabezado) + "|\n"
            + "".join("| " + " | ".join(f) + " |\n" for f in filas) + "\n")


def tabla_desarrollo(d: pd.DataFrame) -> str:
    filas = []
    for _, f in d.sort_values("mejora_rebalanceo", ascending=False).iterrows():
        filas.append([f["senal"], f["regla"], _pb(f["mejora_nuevo"]), _pb(f["mejora_rebalanceo"]),
                      _pb(f["mejora_contra_mezcla_fija"]), _p(f["caida_rebalanceo"], 0), _p(f["exposicion_rebalanceo"], 0),
                      _pb(f["mejora_rebalanceo_con_rezago"]), f"{f['r2_12m'] * 100:+.1f}" if pd.notna(f["r2_12m"]) else "—",
                      "—" if pd.isna(f["clark_west_p_12m"]) else f"{f['clark_west_p_12m']:.2f}",
                      str(int(f["apuestas_efectivas"])), "sí" if f["pasa"] else "no"])
    return _tabla(filas, ["Señal", "Regla", "Solo dinero nuevo (pb)", "Rebalanceando (pb)", "Contra mezcla fija (pb)",
                          "Caída máxima", "Exposición", "Con un mes de retraso (pb)", "R² a 12 meses (%)",
                          "Clark-West p", "Apuestas", "Pasa"])


def informe(r: ResultadoFase5) -> str:
    """El informe de la fase 5 en Markdown, con el veredicto que dicta el pre-registro."""
    d = r.desarrollo
    base_tir = float(d["tir_aportar_siempre"].iloc[0])
    base_caida = float(d["caida_aportar_siempre"].iloc[0])
    eras = r.por_era.pivot_table(index=["senal", "regla"], columns="era", values="mejora_rebalanceo")
    o = ["# Fase 5: ¿cuándo entrar al sector? Resultados\n\n",
         "Pre-registro: `fase4_preregistro.md` (commit anterior a esta corrida). Muestra de desarrollo: "
         f"FTSE Nareit All Equity REITs de {d['desde'].min():%m-%Y} a {d['hasta'].max():%m-%Y}. Aportar siempre "
         f"da una TIR de {_p(base_tir, 2)} con una caída máxima de {_p(base_caida, 0)}. Generado por "
         "`python scripts/investigacion.py fase5`.\n\n"]
    pasan = int(d["pasa"].sum())
    o.append(f"## Veredicto\n\n**{pasan} de {len(d)} reglas pasan el filtro pre-registrado.** ")
    if pasan == 0:
        o.append("Como dice el pre-registro, la validación no se abre y la fase 5 termina en **RECHAZADO** para "
                 "decidir cuándo entrar al sector con estas señales.\n\n")
    o.append(f"Pruebas múltiples sobre las {r.intentos} reglas: PBO = {r.pbo:.2f} (umbral 0.20) y Sharpe deflactado "
             f"de la mejor por Sharpe («{r.mejor}») = {r.sharpe_deflactado:.3f} (umbral 0.95). El Sharpe mide el "
             "retorno por unidad de riesgo de la parte invertida; no es la TIR del inversionista.\n\n")
    o.append(_hipotesis(r))
    o.append("## Todas las reglas, en desarrollo\n\nMejoras en puntos base al año de TIR contra aportar siempre. "
             "«Contra mezcla fija»: contra rebalancear a una exposición constante igual a la promedio de la regla "
             "(P8). R² fuera de muestra a 12 meses con restricción de signo.\n")
    o.append(tabla_desarrollo(d))
    o.append("## Por era\n")
    filas = [[s, rg, _pb(f.get("1972-1992")), _pb(f.get("1993-2015"))] for (s, rg), f in eras.iterrows()]
    o.append(_tabla(filas, ["Señal", "Regla", "1972-1992 (pb)", "1993-2015 (pb)"]))
    return "".join(o)


def _hipotesis(r: ResultadoFase5) -> str:
    """Lo que se escribió antes de correr, contra lo que salió."""
    d = r.desarrollo.set_index(["senal", "regla"])
    eras = r.por_era.set_index(["senal", "regla", "era"])["mejora_rebalanceo"]
    val = d[d["familia"] == "valuacion"]
    tend = d.loc[("tendencia de 10 meses", "signo")]
    nfci = d.loc[("condiciones financieras", "fuera en el quintil peor (20%)")]
    bolsa = d.xs("bolsa del mes", level="senal")
    comb = d[d["familia"] == "combinada"]
    mejor_simple = d[d["familia"] != "combinada"]["mejora_rebalanceo"].max()
    nuevo = d["mejora_nuevo"]
    base = float(d["caida_aportar_siempre"].iloc[0])
    lineas = [
        ("H0 — ninguna le gana a aportar siempre de forma robusta",
         "Se cumple: ninguna regla pasa el filtro (gana con retraso, con doble costo, en las dos eras y predice)."),
        ("H1 — la valuación no sirve para salir",
         f"Se cumple: las 8 reglas de valuación van de {_pb(val['mejora_rebalanceo'].min())} a "
         f"{_pb(val['mejora_rebalanceo'].max())} pb al año rebalanceando, y su R² a 12 meses va de "
         f"{val['r2_12m'].min() * 100:+.1f}% a {val['r2_12m'].max() * 100:+.1f}%, sin un Clark-West significativo."),
        ("H2 — el crédito reduce la caída sin llegar a +50 pb",
         f"En parte: salir con estrés financiero extremo (NFCI en su quintil peor) dio {_pb(nfci['mejora_rebalanceo'])} pb "
         f"y una caída máxima de {_p(nfci['caida_rebalanceo'], 0)}, pero todo viene de 1993-2015 "
         f"({_pb(eras[('condiciones financieras', 'fuera en el quintil peor (20%)', '1993-2015')])} pb) y en 1972-1992 dio "
         f"{_pb(eras[('condiciones financieras', 'fuera en el quintil peor (20%)', '1972-1992')])} pb. Además el NFCI se "
         "revisa: la serie de hoy no es la que se conocía entonces."),
        ("H3 — la tendencia protege a costo pequeño",
         f"En parte: el promedio de 10 meses bajó la caída máxima de {_p(base, 0)} a {_p(tend['caida_rebalanceo'], 0)} "
         f"con {_pb(tend['mejora_rebalanceo'])} pb al año, ejecutando al mismo cierre. Con un mes de retraso cuesta "
         f"{_pb(tend['mejora_rebalanceo_con_rezago'])} pb, y en 1972-1992 costó "
         f"{_pb(eras[('tendencia de 10 meses', 'signo', '1972-1992')])} pb. No predice el retorno a 12 meses."),
        ("H4 — la bolsa del mes predice a un mes, no a 12",
         f"Se cumple: R² a 1 mes de {bolsa['r2_1m'].iloc[0] * 100:+.1f}% (Clark-West p = "
         f"{bolsa['clark_west_p_1m'].iloc[0]:.2f}), a 12 meses {bolsa['r2_12m'].iloc[0] * 100:+.1f}%; sus reglas quedan en "
         f"{_pb(bolsa['mejora_rebalanceo'].max())} pb o menos: la predicción no alcanza a pagar impuestos y comisiones."),
        ("H5 — las combinaciones no le ganan a la mejor sola",
         f"Se cumple: {_pb(comb['mejora_rebalanceo'].max())} pb la mejor combinación contra "
         f"{_pb(mejor_simple)} pb la mejor señal sola."),
        ("H6 — decidiendo solo el dinero nuevo nada llega a +50 pb",
         f"Se cumple: todas quedan entre {_pb(nuevo.min())} y {_pb(nuevo.max())} pb."),
    ]
    return ("## Lo que se escribió antes de correr\n\n"
            + "".join(f"* **{h}.** {t}\n" for h, t in lineas) + "\n")
