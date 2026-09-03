"""Replay histórico, solvers inversos y las herramientas de honestidad del usuario.

Aquí viven las funciones que responden preguntas distintas de "¿cuánto rinde?":

* **Replay histórico** — no es Monte Carlo. Son secuencias que efectivamente
  ocurrieron, aplicadas al portafolio actual del usuario.
* **Solver inverso** — en vez de "¿cuánto rinde?", responde "¿qué tiene que pasar
  para que esto funcione?", y si ese número es plausible contra la historia.
* **Detector de sesgos** — registra las decisiones del usuario contra la regla del
  sistema y cuantifica cuánto le costó desviarse. Es el espejo que casi ninguna
  plataforma ofrece.
* **Tracker de dividendo real** — alerta cuando una posición lleva N trimestres con
  dividendo real estancado. Es una razón legítima de venta, distinta de la
  valuación y del deterioro: "dejó de servir a tu objetivo".
* **Modo ¿qué hubiera pasado?** — reconstruye qué habría dicho el sistema en una
  fecha pasada, con la información disponible entonces. Es la prueba más honesta
  de que el modelo no hace trampa.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd
from scipy import optimize

# --------------------------------------------------------------------------------------
# Replay histórico
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EpisodioHistorico:
    """Un tramo de mercado que efectivamente ocurrió."""

    nombre: str
    inicio: dt.date
    fin: dt.date
    caida_reits: float
    caida_sp500: float
    descripcion: str
    duracion_recuperacion_meses: int | None = None


EPISODIOS: tuple[EpisodioHistorico, ...] = (
    EpisodioHistorico(
        "Crisis financiera 2008",
        dt.date(2007, 2, 1),
        dt.date(2009, 3, 6),
        -0.68,
        -0.57,
        "El peor drawdown de la historia del índice Nareit. Los REITs cayeron más que el "
        "S&P porque el apalancamiento y el crédito eran el problema. Varios emisores "
        "emitieron acciones al fondo del mercado y diluyeron a los tenedores para sobrevivir.",
        duracion_recuperacion_meses=52,
    ),
    EpisodioHistorico(
        "Marzo 2020 (COVID)",
        dt.date(2020, 2, 20),
        dt.date(2020, 3, 23),
        -0.42,
        -0.34,
        "Caída de 42% en cinco semanas. Los sectores se separaron por completo: hoteles y "
        "comercial se desplomaron, data centers e industrial casi no se movieron. Ilustra "
        "por qué el promedio del índice no describe a ningún emisor en particular.",
        duracion_recuperacion_meses=17,
    ),
    EpisodioHistorico(
        "Alza de tasas 2022–2023",
        dt.date(2021, 12, 31),
        dt.date(2023, 10, 27),
        -0.35,
        -0.25,
        "El bono a 10 años pasó de 1.5% a 5%. La caída fue casi toda compresión de múltiplo, "
        "no deterioro del AFFO: el flujo de la mayoría de los emisores siguió creciendo. Es "
        "el episodio que mejor separa 'barato' de 'roto'.",
        duracion_recuperacion_meses=None,
    ),
    EpisodioHistorico(
        "Taper tantrum 2013",
        dt.date(2013, 5, 21),
        dt.date(2013, 12, 31),
        -0.17,
        0.10,
        "El anuncio de reducción de compras de la Fed golpeó a los REITs mientras el S&P "
        "subía. Recordatorio de que el REIT cotiza como instrumento de duración.",
        duracion_recuperacion_meses=14,
    ),
)


@dataclass
class ResultadoReplay:
    episodio: EpisodioHistorico
    valor_inicial: float
    valor_minimo: float
    caida: float
    perdida_absoluta: float
    ingreso_anual_estimado: float
    por_posicion: pd.DataFrame
    mensaje: str


def replay_historico(
    posiciones: pd.DataFrame,
    episodio: EpisodioHistorico,
    *,
    betas_por_sector: dict[str, float] | None = None,
    yield_actual: float = 0.05,
) -> ResultadoReplay:
    """Aplica al portafolio actual la caída real de un episodio histórico.

    ``posiciones`` requiere ``ticker``, ``valor_mercado`` y ``sector``. Cada
    posición se golpea con la caída del episodio ajustada por la beta sectorial:
    en marzo de 2020, hoteles y data centers no se movieron igual, y promediarlos
    esconde justo el riesgo que interesa.

    Esto **no** es Monte Carlo. Es una secuencia que ocurrió.
    """
    if posiciones.empty:
        raise ValueError("No hay posiciones para el replay.")

    betas = betas_por_sector or BETAS_SECTORIALES_ESTRES
    df = posiciones.copy()
    df["beta_estres"] = df["sector"].map(betas).fillna(1.0)
    df["caida_aplicada"] = episodio.caida_reits * df["beta_estres"]
    df["valor_en_el_fondo"] = df["valor_mercado"] * (1.0 + df["caida_aplicada"])
    df["perdida"] = df["valor_en_el_fondo"] - df["valor_mercado"]

    valor_inicial = float(df["valor_mercado"].sum())
    valor_minimo = float(df["valor_en_el_fondo"].sum())
    caida = valor_minimo / valor_inicial - 1.0 if valor_inicial else 0.0
    ingreso = valor_inicial * yield_actual

    mensaje = (
        f"{episodio.nombre}: tu portafolio de {valor_inicial:,.0f} habría caído a "
        f"{valor_minimo:,.0f} ({caida:.1%}), una pérdida de {abs(valor_inicial - valor_minimo):,.0f}. "
        f"Tu ingreso anual por dividendos es de {ingreso:,.0f}: la caída equivale a "
        f"{abs(valor_inicial - valor_minimo) / ingreso:.1f} años de ingreso. "
    )
    if episodio.duracion_recuperacion_meses:
        mensaje += (
            f"La recuperación al nivel previo tomó {episodio.duracion_recuperacion_meses} meses "
            f"({episodio.duracion_recuperacion_meses / 12:.1f} años). "
        )
    else:
        mensaje += "El índice aún no recuperaba el nivel previo al cierre del episodio. "
    mensaje += (
        "La pregunta útil no es si aguantarías la caída, sino si seguirías aportando durante ella."
    )

    return ResultadoReplay(
        episodio=episodio,
        valor_inicial=valor_inicial,
        valor_minimo=valor_minimo,
        caida=caida,
        perdida_absoluta=valor_minimo - valor_inicial,
        ingreso_anual_estimado=ingreso,
        por_posicion=df,
        mensaje=mensaje,
    )


# Beta de estrés por sector: cuánto amplifica o amortigua cada sector la caída del índice.
# Calibradas cualitativamente contra el comportamiento observado en 2008 y marzo de 2020.
BETAS_SECTORIALES_ESTRES: dict[str, float] = {
    "Hoteles": 1.6,
    "Oficinas": 1.4,
    "Comercial": 1.3,
    "Diversificado": 1.1,
    "Salud": 1.0,
    "Residencial": 1.0,
    "Net Lease": 0.9,
    "Industrial": 0.85,
    "Self Storage": 0.8,
    "Data Centers": 0.7,
    "Torres": 0.7,
    "Vivienda Prefabricada": 0.7,
    "Bosques": 1.0,
    "Especializado": 1.1,
}


def replay_todos(
    posiciones: pd.DataFrame, *, yield_actual: float = 0.05
) -> pd.DataFrame:
    """Corre los cuatro episodios y devuelve la tabla comparativa."""
    filas = []
    for ep in EPISODIOS:
        r = replay_historico(posiciones, ep, yield_actual=yield_actual)
        filas.append(
            {
                "episodio": ep.nombre,
                "periodo": f"{ep.inicio} a {ep.fin}",
                "caida_portafolio": r.caida,
                "valor_en_el_fondo": r.valor_minimo,
                "perdida": r.perdida_absoluta,
                "anios_de_ingreso_perdidos": abs(r.perdida_absoluta) / r.ingreso_anual_estimado
                if r.ingreso_anual_estimado
                else None,
                "meses_de_recuperacion": ep.duracion_recuperacion_meses,
            }
        )
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# Solver inverso de supuestos
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoSolver:
    variable: str
    valor_requerido: float | None
    valor_historico_mediano: float | None
    plausible: bool | None
    mensaje: str


def crecimiento_affo_requerido(
    capital_actual: float,
    aportacion_anual: float,
    meta_ingreso_anual: float,
    anios: int,
    yield_inicial: float,
    *,
    historico_crecimiento: pd.Series | None = None,
) -> ResultadoSolver:
    """¿Qué crecimiento del AFFO se requiere para llegar a la meta, y es plausible?

    Da vuelta a la pregunta: en vez de proyectar un rendimiento y ver a dónde
    llega, se fija la meta y se despeja el supuesto necesario. Después se contrasta
    contra la historia. Si el número requerido está en el percentil 95 de lo que el
    sector ha logrado, el plan no es ambicioso: es improbable.
    """

    def brecha(g: float) -> float:
        capital = capital_actual
        for _ in range(anios):
            capital = capital * (1.0 + g) + aportacion_anual
        return capital * yield_inicial - meta_ingreso_anual

    try:
        requerido = float(optimize.brentq(brecha, -0.5, 1.0, xtol=1e-8, maxiter=300))
    except ValueError:
        requerido = None

    mediano = (
        float(pd.Series(historico_crecimiento).dropna().median())
        if historico_crecimiento is not None and not pd.Series(historico_crecimiento).dropna().empty
        else None
    )
    percentil = None
    if requerido is not None and historico_crecimiento is not None:
        h = pd.Series(historico_crecimiento).dropna()
        if not h.empty:
            percentil = float((h < requerido).mean())

    if requerido is None:
        return ResultadoSolver(
            "crecimiento_total_anual", None, mediano, None,
            "No existe una tasa de crecimiento en el rango razonable que alcance la meta. "
            "Hay que subir la aportación, extender el horizonte o bajar la meta.",
        )

    plausible = None if percentil is None else bool(percentil < 0.75)
    mensaje = (
        f"Para llegar a un ingreso de {meta_ingreso_anual:,.0f} en {anios} años con "
        f"{capital_actual:,.0f} de capital y {aportacion_anual:,.0f} de aportación anual, "
        f"el portafolio tiene que crecer {requerido:.2%} al año."
    )
    if mediano is not None:
        mensaje += f" La mediana histórica del crecimiento observado es {mediano:.2%}."
    if percentil is not None:
        mensaje += f" El número requerido está en el percentil {percentil:.0%} de la historia."
        if percentil >= 0.75:
            mensaje += (
                " Eso no es un plan ambicioso: es un plan que depende de que ocurra el cuartil "
                "superior de la historia. Ajusta la aportación o el horizonte."
            )
    return ResultadoSolver("crecimiento_total_anual", requerido, mediano, plausible, mensaje)


def aportacion_requerida(
    capital_actual: float,
    meta_capital: float,
    anios: int,
    rendimiento_real: float,
) -> float:
    """Aportación anual necesaria para llegar a una meta de capital, en términos reales."""
    if rendimiento_real == 0:
        return (meta_capital - capital_actual) / anios
    factor = (1.0 + rendimiento_real) ** anios
    return (meta_capital - capital_actual * factor) * rendimiento_real / (factor - 1.0)


def resolver_supuesto(
    funcion_objetivo: Callable[[float], float],
    *,
    minimo: float = -0.5,
    maximo: float = 1.0,
) -> float | None:
    """Solver genérico: encuentra el valor del supuesto que hace cero la brecha."""
    try:
        return float(optimize.brentq(funcion_objetivo, minimo, maximo, xtol=1e-8, maxiter=300))
    except ValueError:
        return None


# --------------------------------------------------------------------------------------
# Tracker de dividendo real por posición (innovación 3.3.d)
# --------------------------------------------------------------------------------------


@dataclass
class AlertaDividendoReal:
    ticker: str
    trimestres_estancados: int
    crecimiento_real_anualizado: float | None
    dispara_alerta: bool
    mensaje: str


def rastrear_dividendo_real(
    ticker: str,
    dividendos_por_accion: pd.Series,
    indice_precios: pd.Series,
    *,
    trimestres_umbral: int = 8,
) -> AlertaDividendoReal:
    """Serie del dividendo deflactado y alerta por estancamiento real.

    Es una razón de venta **distinta** de la valuación y del deterioro: la posición
    puede tener balance impecable y cotizar barata, y aun así haber dejado de
    servir al objetivo si su dividendo real lleva años sin crecer. Realty Income
    creció su dividendo 3.2% anual de 2021 a 2025 contra inflación de ~3.3%: el
    ingreso quedó plano en poder adquisitivo mientras el papel se veía sano.
    """
    from src.ingesta.tasas import deflactar

    s = pd.Series(dividendos_por_accion).dropna()
    if len(s) < 4:
        return AlertaDividendoReal(
            ticker, 0, None, False, "Serie demasiado corta para evaluar el dividendo real."
        )
    real = deflactar(s, indice_precios)
    if real.empty or real.isna().all():
        return AlertaDividendoReal(
            ticker, 0, None, False, "No hay índice de precios suficiente para deflactar."
        )
    real = real.dropna()

    # Trimestres consecutivos, contando hacia atrás, sin superar el máximo previo.
    estancados = 0
    maximo = real.cummax()
    for i in range(len(real) - 1, -1, -1):
        if real.iloc[i] < maximo.iloc[i] * 0.999:
            estancados += 1
        else:
            break

    anios = max(0.25, (real.index[-1] - real.index[0]).days / 365.25)
    crecimiento = (
        (real.iloc[-1] / real.iloc[0]) ** (1.0 / anios) - 1.0 if real.iloc[0] > 0 else None
    )

    dispara = estancados >= trimestres_umbral
    if dispara:
        mensaje = (
            f"{ticker}: el dividendo REAL lleva {estancados} trimestres sin superar su máximo "
            f"previo (crecimiento real anualizado {crecimiento:.2%}). El dividendo nominal puede "
            "estar subiendo y aun así perder contra la inflación. Esta es una razón legítima de "
            "venta — la posición dejó de servir a tu objetivo — distinta de la valuación y del "
            "deterioro del balance."
        )
    else:
        mensaje = (
            f"{ticker}: dividendo real creciendo {crecimiento:.2%} anualizado; "
            f"{estancados} trimestres desde el último máximo real."
        )
    return AlertaDividendoReal(ticker, estancados, crecimiento, dispara, mensaje)


# --------------------------------------------------------------------------------------
# Detector de sesgos del usuario (innovación 3.3.e)
# --------------------------------------------------------------------------------------


@dataclass
class ReporteSesgos:
    n_decisiones: int
    n_desviaciones: int
    tasa_desviacion: float
    costo_estimado: float
    por_tipo: pd.DataFrame
    mensaje: str


def detectar_sesgos(decisiones: pd.DataFrame, precios_posteriores: pd.DataFrame | None = None) -> ReporteSesgos:
    """Compara las decisiones del usuario contra lo que dijo el sistema y cuantifica el costo.

    ``decisiones`` requiere ``fecha``, ``ticker``, ``senal_sistema``, ``accion_usuario``
    y ``monto``. Con ``precios_posteriores`` (panel ``fecha × ticker``) se estima
    cuánto costó cada desviación a 12 meses.

    El objetivo no es regañar: es que el usuario vea el patrón. Los sesgos son
    sistemáticos — casi siempre en la misma dirección — y verlos cuantificados es lo
    único que los mueve.
    """
    if decisiones.empty:
        return ReporteSesgos(0, 0, 0.0, 0.0, pd.DataFrame(), "Sin decisiones registradas todavía.")

    d = decisiones.copy()
    d["fecha"] = pd.to_datetime(d["fecha"])
    d["coincide"] = [
        _coincide(s, a) for s, a in zip(d["senal_sistema"], d["accion_usuario"], strict=False)
    ]
    d["costo"] = 0.0

    if precios_posteriores is not None and not precios_posteriores.empty:
        px = precios_posteriores.copy()
        px.index = pd.to_datetime(px.index)
        for i, r in d.iterrows():
            if r["coincide"] or r["ticker"] not in px.columns:
                continue
            serie = px[r["ticker"]].dropna()
            antes = serie[serie.index <= r["fecha"]]
            despues = serie[serie.index <= r["fecha"] + pd.DateOffset(years=1)]
            if antes.empty or despues.empty:
                continue
            retorno = float(despues.iloc[-1]) / float(antes.iloc[-1]) - 1.0
            signo = 1.0 if str(r["senal_sistema"]).upper().startswith("COMPRA") else -1.0
            d.loc[i, "costo"] = -signo * retorno * float(r.get("monto") or 0.0)

    n = len(d)
    desviaciones = int((~d["coincide"]).sum())
    por_tipo = (
        d.groupby(["senal_sistema", "accion_usuario"])
        .agg(veces=("coincide", "size"), costo_total=("costo", "sum"))
        .reset_index()
        .sort_values("costo_total")
    )
    costo = float(d["costo"].sum())

    mensaje = (
        f"De {n} decisiones registradas, te desviaste de la regla del sistema en {desviaciones} "
        f"({desviaciones / n:.0%})."
    )
    if abs(costo) > 0:
        if costo > 0:
            mensaje += (
                f" Esas desviaciones te costaron aproximadamente {costo:,.0f} a doce meses. "
                "El punto no es que el sistema tenga razón siempre: es que el patrón sea visible."
            )
        else:
            mensaje += (
                f" Esas desviaciones te AGREGARON aproximadamente {abs(costo):,.0f} a doce meses. "
                "Vale la pena revisar si el sistema está mal calibrado en algún criterio."
            )
    return ReporteSesgos(n, desviaciones, desviaciones / n, costo, por_tipo, mensaje)


def _coincide(senal: str, accion: str) -> bool:
    s, a = str(senal).upper(), str(accion).upper()
    equivalencias = {
        "COMPRAR": {"COMPRAR", "COMPRA", "APORTAR"},
        "MANTENER": {"MANTENER", "NADA", "SIN CAMBIO"},
        "NO COMPRAR MÁS": {"MANTENER", "NADA", "SIN CAMBIO", "NO COMPRAR MÁS"},
        "VENDER": {"VENDER", "VENTA", "VENTA PARCIAL"},
        "DESCARTADO": {"VENDER", "NADA", "NO COMPRAR"},
    }
    return a in equivalencias.get(s, {s})


# --------------------------------------------------------------------------------------
# Modo "¿qué hubiera pasado?" (innovación 3.3.g)
# --------------------------------------------------------------------------------------


@dataclass
class Retrospectiva:
    fecha_corte: dt.date
    dictamen: dict
    datos_disponibles: pd.DataFrame
    datos_ocultos: pd.DataFrame
    mensaje: str = ""

    def como_texto(self) -> str:
        return (
            f"Al {self.fecha_corte}, el sistema veía {len(self.datos_disponibles)} registros y "
            f"tenía OCULTOS {len(self.datos_ocultos)} que aún no se publicaban. "
            + self.mensaje
        )


def que_hubiera_pasado(
    repositorio,
    ticker: str,
    fecha_corte: dt.date,
    evaluador: Callable[[dt.date], dict],
    *,
    concepto: str = "affo",
) -> Retrospectiva:
    """Reconstruye qué habría dicho el sistema en una fecha pasada.

    Punto crítico: respeta point-in-time por construcción, porque todo pasa por el
    repositorio, que exige corte. Además devuelve explícitamente los registros que
    **existían en la base pero aún no se habían publicado** a esa fecha, para que se
    vea que el sistema los tenía a la mano y no los usó. Es la prueba más honesta
    de que el modelo no hace trampa.
    """
    disponibles = repositorio.hechos(asof=fecha_corte, tickers=ticker, conceptos=concepto)
    todos = repositorio.hechos(asof=dt.date.today(), tickers=ticker, conceptos=concepto)
    if todos.empty:
        ocultos = todos
    else:
        ocultos = todos[pd.to_datetime(todos["fecha_publicacion"]).dt.date > fecha_corte]

    dictamen = evaluador(fecha_corte)

    mensaje = ""
    if not ocultos.empty:
        prox = ocultos.sort_values("fecha_publicacion").iloc[0]
        mensaje = (
            f"El siguiente dato se publicó el {pd.Timestamp(prox['fecha_publicacion']).date()}, "
            f"{(pd.Timestamp(prox['fecha_publicacion']).date() - fecha_corte).days} días después "
            "del corte. El dictamen de arriba no lo usó."
        )
    return Retrospectiva(fecha_corte, dictamen, disponibles, ocultos, mensaje)


# --------------------------------------------------------------------------------------
# Comparación contra el Udibono (P10)
# --------------------------------------------------------------------------------------


@dataclass
class ComparacionUdibono:
    real_reits_despues_impuestos: float
    real_udibono: float
    brecha: float
    el_sin_riesgo_gana: bool
    mensaje: str


def comparar_contra_udibono(
    yield_reits_bruto: float,
    crecimiento_esperado: float,
    inflacion_esperada: float,
    tasa_udibono_real: float,
    *,
    tiene_w8ben: bool = True,
) -> ComparacionUdibono:
    """La comparación que debe estar siempre en la pantalla principal (P10).

    El Udibono paga tasa real fija garantizada. Cualquier REIT tiene que superar
    esa tasa real **después de impuestos** para justificar su riesgo de mercado,
    divisa y emisor. Si el activo sin riesgo paga más que el activo con riesgo, el
    modelo lo dice con esas palabras.
    """
    from src.fiscal.mexico import rendimiento_real_despues_de_impuestos

    r = rendimiento_real_despues_de_impuestos(
        yield_reits_bruto, crecimiento_esperado, inflacion_esperada, tiene_w8ben=tiene_w8ben
    )
    real_reits = r["real_despues_de_impuestos"]
    brecha = real_reits - tasa_udibono_real
    gana_sin_riesgo = brecha <= 0

    if gana_sin_riesgo:
        mensaje = (
            f"EL ACTIVO SIN RIESGO PAGA MÁS QUE EL ACTIVO CON RIESGO. El Udibono a 10 años "
            f"paga {tasa_udibono_real:.2%} real garantizado. Tu portafolio de REITs ofrece "
            f"{real_reits:.2%} real esperado después de impuestos, con riesgo de mercado, de "
            f"divisa y de emisor. La brecha es de {brecha * 10_000:,.0f} puntos base EN CONTRA. "
            "Eso no significa que no debas tener REITs, pero sí que la tesis tiene que ser el "
            "crecimiento futuro del flujo, no el rendimiento de hoy."
        )
    else:
        mensaje = (
            f"El portafolio de REITs ofrece {real_reits:.2%} real esperado después de impuestos "
            f"contra {tasa_udibono_real:.2%} real garantizado del Udibono a 10 años: una prima "
            f"de {brecha * 10_000:,.0f} puntos base por asumir riesgo de mercado, divisa y emisor. "
            "Juzga si esa prima compensa el riesgo, no si el número es grande."
        )
    return ComparacionUdibono(real_reits, tasa_udibono_real, brecha, gana_sin_riesgo, mensaje)


# --------------------------------------------------------------------------------------
# Contexto histórico de rendimientos
# --------------------------------------------------------------------------------------


def tabla_contexto_nareit() -> pd.DataFrame:
    """Rendimientos históricos del índice FTSE Nareit All Equity, nominal y real."""
    from src.config import RENDIMIENTOS_NAREIT_HISTORICOS

    return pd.DataFrame(
        [
            {"periodo": p, "nominal": n, "real": r}
            for p, n, r in RENDIMIENTOS_NAREIT_HISTORICOS
        ]
    )
