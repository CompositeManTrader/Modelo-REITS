"""La ampliación del estudio: las conclusiones de O, NNN y WPC, fuera de muestra en siete emisores más.

Pre-registro: ``docs/estudios/ampliacion_preregistro.md``. Este módulo no tiene parámetros propios:
corre el código del estudio tal como quedó congelado y evalúa las siete hipótesis con el criterio
escrito antes de ver resultados. Cada una se mide como se midió la conclusión original:

* H1, H1b, H2 y H7: el retorno de los 5 años siguientes neto con broker de EE. UU. al 35%, en fines
  de trimestre (``metodos.paneles_netos``), como el retorno esperado de la app.
* H3: el semáforo completo contra aportar siempre (``reglas.backtest``), como en el PDF de reglas.
* H4: el consenso solo, para decidir cuándo comprar (``metodos.backtest_metodos``).
* H5: la asignación entre emisores con el consenso (``metodos.asignar``), entre los que la regla de
  elegibilidad deja entrar, con 500 elecciones al azar como en el análisis de poder.
* H6: la correlación de rangos a 5 años de los modelos de valor contra la de los siete métodos
  simples, los emisores juntos (``evaluar_juntos``), como en el PDF de métodos.

    python scripts/estudio.py ampliacion
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.estudio import metodos as mt
from src.estudio import reglas as rg

ORIGINALES = ("NNN", "O", "WPC")
NUEVOS = ("ADC", "EPRT", "EXR", "GNL", "PLD", "PSA", "WELL")
# Quiénes entran a la asignación, con nombre, como los fija el pre-registro (decisión 3). EXR tiene
# percentil desde feb-2009, dos meses después del corte de 2008: «si a alguno le falta percentil en
# 2008, se reporta con la ventana que haya, sin sustituirlo».
ASIGNACION = {
    "originales": ORIGINALES,
    "siete": ("ADC", "EXR", "PLD", "PSA", "WELL"),
    "siete_nareit": ("ADC", "EXR", "PLD", "PSA", "WELL"),
    "diez": ("ADC", "EXR", "NNN", "O", "PLD", "PSA", "WELL", "WPC"),
}


def asignar_entre(tickers) -> tuple[str, ...] | None:
    """Para el PDF y la página con todos los emisores: los de «los diez» que haya; si solo están los
    originales, los originales; si no, la regla general de ``metodos.para_asignar``."""
    t = set(tickers)
    if t <= set(ORIGINALES):
        return None
    return tuple(x for x in ASIGNACION["diez"] if x in t)
MIN_TRIMESTRES = 40            # 2 ventanas independientes de 5 años (pre-registro, decisión 4)
MEJORA_MINIMA = 0.005          # +50 pb
DIFERENCIA_BARATO_CARO = 0.03  # 3 puntos al año
AZAR_MAXIMO = 0.05
N_AZAR = 500

RAIZ = Path(__file__).resolve().parents[2]
DIR_RESULTADOS = RAIZ / "data" / "estudios" / "ampliacion"
INFORME = RAIZ / "docs" / "estudios" / "ampliacion_resultados.md"


@dataclass
class Hipotesis:
    clave: str
    conclusion: str
    criterio: str
    se_repite: bool | None        # None: no hay datos para decidir
    cifras: str
    detalle: pd.DataFrame = field(default_factory=pd.DataFrame)


def _trimestres(paneles: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Los emisores juntos, un renglón por fin de trimestre con percentil del consenso y retorno a 5 años."""
    return pd.concat([mt.trimestral(p).assign(emisor=t) for t, p in paneles.items()]).dropna(
        subset=["p_consenso", "adelante_5a"])


def h1(netos: dict[str, pd.DataFrame]) -> tuple[Hipotesis, Hipotesis]:
    q = _trimestres(netos)
    barato = q.loc[q["p_consenso"] >= mt.BARATO, "adelante_5a"]
    caro = q.loc[q["p_consenso"] < mt.CARO, "adelante_5a"]
    dif = float(barato.median() - caro.median()) if len(barato) and len(caro) else np.nan
    rho = mt._spearman(q["p_consenso"], q["adelante_5a"])
    filas = []
    for t, p in netos.items():
        d = mt.trimestral(p).dropna(subset=["p_consenso", "adelante_5a"])
        filas.append({"emisor": t, "trimestres": len(d), "ventanas": len(d) / 20,
                      "elegible": len(d) >= MIN_TRIMESTRES, "rho_5a": mt._spearman(d["p_consenso"], d["adelante_5a"])})
    por = pd.DataFrame(filas).set_index("emisor")
    eleg = por[por["elegible"]]
    positivos = int((eleg["rho_5a"] > 0).sum())
    a = Hipotesis(
        "H1", "La valuación predice el retorno de 5 años: lo barato rindió más que lo caro.",
        "Juntos: mediana de barato (≥ 70) − mediana de caro (< 30) ≥ 3 puntos al año y ρ a 5 años positiva.",
        None if np.isnan(dif) or np.isnan(rho) else bool(dif >= DIFERENCIA_BARATO_CARO and rho > 0),
        f"barato {barato.median():.1%} ({len(barato)} trimestres) contra caro {caro.median():.1%} "
        f"({len(caro)}): {dif * 100:+.1f} puntos; ρ = {rho:+.2f} con {len(q)} trimestres "
        f"({len(q) / 20:.0f} ventanas independientes)." if not np.isnan(dif) else "sin datos suficientes",
    )
    b = Hipotesis(
        "H1b", "Lo mismo, emisor por emisor.",
        f"ρ a 5 años positiva en la mayoría de los emisores con al menos {MIN_TRIMESTRES} trimestres.",
        None if eleg.empty else bool(positivos > len(eleg) / 2),
        f"{positivos} de {len(eleg)} emisores elegibles con ρ positiva"
        + (f" ({', '.join(f'{t} {r:+.2f}' for t, r in eleg['rho_5a'].items())})." if len(eleg) else "."),
        por,
    )
    return a, b


def h2(netos: dict[str, pd.DataFrame]) -> Hipotesis:
    q = _trimestres(netos).dropna(subset=["efectivo_5a"])
    caro = q[q["p_consenso"] < mt.CARO]
    gana = float((caro["adelante_5a"] > caro["efectivo_5a"]).mean()) if len(caro) else np.nan
    return Hipotesis(
        "H2", "Aun desde «caro», el REIT le ganó al efectivo la mayoría de las veces: esperar no paga.",
        "Juntos, en caro + muy caro, el REIT le gana al T-bill neto en más de 50% de los trimestres.",
        None if np.isnan(gana) else bool(gana > 0.5),
        f"le ganó en {gana:.0%} de {len(caro)} trimestres." if len(caro) else "sin trimestres caros",
    )


def h3(reglas: dict[str, object]) -> Hipotesis:
    filas = []
    for t, r in reglas.items():
        filas.append({"emisor": t, "ventaja_tir_usd": float(r.tabla.loc[rg.Variante.MODELO.value, "ventaja_tir_usd"])})
    d = pd.DataFrame(filas).set_index("emisor")
    ganan = int((d["ventaja_tir_usd"] >= MEJORA_MINIMA).sum())
    return Hipotesis(
        "H3", "El semáforo completo no le gana a aportar siempre.",
        "El semáforo le gana a aportar siempre por +50 pb o más en a lo sumo 1 emisor.",
        None if d.empty else bool(ganan <= 1),
        f"le gana por +50 pb en {ganan} de {len(d)}: "
        + ", ".join(f"{t} {v * 1e4:+.0f} pb" for t, v in d["ventaja_tir_usd"].items()) + ".",
        d,
    )


def h4(r: mt.ResultadoMetodos) -> Hipotesis:
    d = pd.DataFrame({t: {"ventaja_tir": b.loc["consenso", "ventaja_tir"]} for t, b in r.backtests.items()}).T
    abajo = int((d["ventaja_tir"] < MEJORA_MINIMA).sum())
    return Hipotesis(
        "H4", "Ningún método solo, usado para decidir cuándo comprar, le gana a aportar siempre.",
        "Con el consenso, la ventaja contra aportar siempre es menor a +50 pb en la mayoría.",
        None if d.empty else bool(abajo > len(d) / 2),
        f"menor a +50 pb en {abajo} de {len(d)}: "
        + ", ".join(f"{t} {v * 1e4:+.0f} pb" for t, v in d["ventaja_tir"].items()) + ".",
        d,
    )


def h5(r: mt.ResultadoMetodos) -> Hipotesis:
    a = next((x for x in r.asignaciones if x.clave == "consenso"), None)
    if a is None:
        return Hipotesis("H5", "Mandar la aportación al más barato contra su propia historia le ganó a repartir parejo.",
                         "Ventaja ≥ +50 pb, a lo sumo 5% del azar le gana y el espejo queda abajo.", None,
                         f"sin asignación: entran {', '.join(r.asignables) or 'ninguno'}")
    ok = a.ventaja >= MEJORA_MINIMA and a.azar_que_le_gana <= AZAR_MAXIMO and a.ventaja_el_mas_caro < 0
    return Hipotesis(
        "H5", "Mandar la aportación al más barato contra su propia historia le ganó a repartir parejo.",
        "Ventaja del consenso ≥ +50 pb, a lo sumo 5% de las elecciones al azar le gana y el espejo (todo al "
        "más caro) queda abajo de partes iguales.",
        bool(ok),
        f"entre {', '.join(r.asignables)} desde {a.desde:%Y-%m}: ventaja {a.ventaja * 1e4:+.0f} pb; el azar le gana "
        f"{a.azar_que_le_gana:.0%} de las veces; el espejo {a.ventaja_el_mas_caro * 1e4:+.0f} pb; "
        + "; ".join(f"{n}: {v * 1e4:+.0f} pb" for n, v in a.mitades) + ".",
    )


def h6(r: mt.ResultadoMetodos) -> Hipotesis:
    simples = r.juntos.loc[[c for c in mt.SIETE if c in r.juntos.index], "rho_5a"]
    valor = r.intrinsecos.juntos_percentil["rho_5a"] if r.intrinsecos is not None else pd.Series(dtype=float)
    mejor = float(simples.max())
    arriba = valor[valor > mejor]
    return Hipotesis(
        "H6", "DDM, DCF, crecimiento implícito y NAV no predicen mejor que los métodos simples.",
        "Juntos, ningún modelo de valor tiene ρ a 5 años mayor que la del mejor método simple.",
        None if valor.dropna().empty else bool(arriba.empty),
        f"mejor simple: {r.juntos.loc[simples.idxmax(), 'metodo']} ρ = {mejor:+.2f}; modelos de valor: "
        + ", ".join(f"{k} {v:+.2f}" if pd.notna(v) else f"{k} sin datos suficientes" for k, v in valor.items())
        + ".",
    )


def h7(netos: dict[str, pd.DataFrame]) -> Hipotesis:
    t = mt.retorno_esperado(netos)
    j = t[t["alcance"] == "juntos"].set_index("tramo")
    mb, mc = j.loc["muy barato", "mediana"], j.loc["muy caro", "mediana"]
    return Hipotesis(
        "H7", "En los extremos la valuación separa: el 10% más barato rindió mucho más que el 10% más caro.",
        "Juntos, la mediana de muy barato (≥ 90) supera a la de muy caro (< 10).",
        None if pd.isna(mb) or pd.isna(mc) else bool(mb > mc),
        f"muy barato {mb:.1%} ({int(j.loc['muy barato', 'trimestres'])} trimestres) contra muy caro {mc:.1%} "
        f"({int(j.loc['muy caro', 'trimestres'])})." if not (pd.isna(mb) or pd.isna(mc)) else
        f"sin datos: muy barato {int(j.loc['muy barato', 'trimestres'])} trimestres, muy caro "
        f"{int(j.loc['muy caro', 'trimestres'])} (se piden {mt.MIN_TRIMESTRES_TRAMO}).",
        t,
    )


@dataclass
class Grupo:
    nombre: str
    tickers: tuple[str, ...]
    metodos: mt.ResultadoMetodos
    hipotesis: list[Hipotesis]


def evaluar_grupo(nombre: str, estudios: dict, *, n_azar: int = N_AZAR) -> Grupo:
    r = mt.estudiar(estudios, n_azar=n_azar, asignar_entre=ASIGNACION.get(nombre))
    netos = mt.paneles_netos(estudios)
    reglas = {t: rg.backtest(e) for t, e in estudios.items()}
    a, b = h1(netos)
    return Grupo(nombre, tuple(sorted(estudios)), r, [a, b, h2(netos), h3(reglas), h4(r), h5(r), h6(r), h7(netos)])


def correr(estudios: dict, *, n_azar: int = N_AZAR) -> dict[str, Grupo]:
    """Los tres grupos del pre-registro: los originales (control), los siete y los diez."""
    grupos = {"originales": [t for t in ORIGINALES if t in estudios],
              "siete": [t for t in NUEVOS if t in estudios],
              "diez": [t for t in (*ORIGINALES, *NUEVOS) if t in estudios]}
    return {g: evaluar_grupo(g, {t: estudios[t] for t in ts}, n_azar=n_azar) for g, ts in grupos.items() if ts}


def tabla(grupos: dict[str, Grupo]) -> pd.DataFrame:
    filas = []
    for g in grupos.values():
        for h in g.hipotesis:
            filas.append({"grupo": g.nombre, "hipotesis": h.clave, "se_repite": h.se_repite, "cifras": h.cifras,
                          "criterio": h.criterio, "conclusion": h.conclusion})
    return pd.DataFrame(filas)


def guardar(grupos: dict[str, Grupo], destino: Path | None = None) -> Path:
    destino = destino or DIR_RESULTADOS
    destino.mkdir(parents=True, exist_ok=True)
    tabla(grupos).to_csv(destino / "hipotesis.csv", index=False)
    for g in grupos.values():
        g.metodos.esperado.to_csv(destino / f"esperado_{g.nombre}.csv", index=False)
        g.metodos.asignacion().to_csv(destino / f"asignacion_{g.nombre}.csv")
        g.metodos.juntos.to_csv(destino / f"juntos_{g.nombre}.csv")
        for h in g.hipotesis:
            if not h.detalle.empty:
                h.detalle.to_csv(destino / f"{h.clave.lower()}_{g.nombre}.csv")
    (destino / "grupos.json").write_text(json.dumps(
        {g.nombre: {"tickers": list(g.tickers), "asignables": g.metodos.asignables} for g in grupos.values()},
        ensure_ascii=False, indent=1))
    return destino


def _veredicto(v: bool | None) -> str:
    return {True: "**se repite**", False: "**no se repite**", None: "sin datos para decidir"}[v]


def informe(grupos: dict[str, Grupo]) -> str:
    lineas = ["# Ampliación del estudio: ¿se repiten las conclusiones de O, NNN y WPC?", "",
              "Resultado de la prueba fuera de muestra pre-registrada en "
              "`docs/estudios/ampliacion_preregistro.md`. Generado con `python scripts/estudio.py ampliacion`.", ""]
    nuevos = grupos.get("siete")
    if nuevos is not None:
        lineas += ["## Los siete emisores nuevos", "",
                   "| # | Conclusión de los tres | Criterio | Resultado | Cifras |", "|---|---|---|---|---|"]
        for h in nuevos.hipotesis:
            lineas.append(f"| {h.clave} | {h.conclusion} | {h.criterio} | {_veredicto(h.se_repite)} | {h.cifras} |")
        lineas.append("")
    for nombre, titulo in (("siete_nareit", "Sensibilidad: los siete con FFO de Nareit, sin excepciones de medida"),
                           ("originales", "Control: los tres originales con el mismo código"),
                           ("diez", "Los diez juntos")):
        g = grupos.get(nombre)
        if g is None:
            continue
        lineas += [f"## {titulo}", "", "| # | Resultado | Cifras |", "|---|---|---|"]
        for h in g.hipotesis:
            lineas.append(f"| {h.clave} | {_veredicto(h.se_repite)} | {h.cifras} |")
        lineas.append("")
    return "\n".join(lineas)
