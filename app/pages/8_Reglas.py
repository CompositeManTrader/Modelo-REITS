"""Reglas de compra y venta: el semáforo de la aplicación puesto a prueba en toda la historia.

Cada fin de mes se evalúa el mismo semáforo de la pantalla de valuación con lo que se
había publicado ese día, y su acción decide qué hacer con la aportación del mes:
comprar, comprar menos, no comprar o vender por tesis rota. Todo sale de
``src.estudio.reglas.backtest``, el mismo objeto del PDF.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from comun import (  # noqa: E402
    configurar,
    descargo,
    exigir_base,
    firma_de_la_base,
    mostrar_tabla,
    selector_de_corte,
    suficiencia,
)

from marca import encabezado, inyectar_estilos  # noqa: E402
from src.estudio import estudio as mod_estudio  # noqa: E402
from src.estudio import graficas as g  # noqa: E402
from src.estudio import graficas_reglas as gr  # noqa: E402
from src.estudio import (
    mercado,  # noqa: E402
    reglas,  # noqa: E402
    vistas_reglas,  # noqa: E402
)

RAIZ = Path(__file__).resolve().parent.parent.parent

configurar("Reglas", "🧭")
inyectar_estilos()
encabezado("Reglas")
st.title("Reglas de compra y venta")

repo = exigir_base()
asof = selector_de_corte()

con_estudio = [t for t in sorted(repo.emisores()["ticker"]) if mercado.hay_estudio(t)]
if not con_estudio:
    st.error("Ningún emisor tiene todavía su estudio de largo plazo: el backtest corre sobre esa historia.")
    st.stop()


@st.cache_data(show_spinner="Corriendo el backtest…", max_entries=8)
def _resultado(_repo, ticker: str, asof, firma: tuple):
    return reglas.backtest(mod_estudio.armar(_repo, ticker, asof=asof))


resultados = {t: _resultado(repo, t, asof, firma_de_la_base()) for t in con_estudio}

st.markdown(
    "El modelo es el **semáforo de la pantalla de valuación**, evaluado cada fin de mes con lo que se "
    "había publicado ese día. Su acción decide qué hacer con el dinero del mes —la aportación y los "
    "dividendos netos—:"
)
st.markdown(
    "| Semáforo | Decisión | Dinero del mes |\n|---|---|---|\n"
    "| COMPRAR — prima en el percentil ≥ 70 de su historia | **Comprar** | todo, más toda la reserva |\n"
    "| MANTENER — percentil 30 a 70 | **Comprar menos** | la mitad; la otra mitad a la reserva |\n"
    "| NO COMPRAR MÁS (< 30) o DESCARTADO por calidad | **No comprar** | todo a la reserva |\n"
    "| VENDER — Puerta 3, deterioro sostenido | **Vender por tesis rota** | se vende todo; nada se compra |\n"
    "| INCONCLUSO — faltan datos | Sin señal | todo, como sin reglas |"
)
st.caption(
    "La reserva es efectivo en dólares que rinde el T-bill a 3 meses. Los umbrales son los del semáforo "
    "(`config.UMBRALES`), fijados antes de este backtest; lo único nuevo es la mitad de «comprar menos», "
    "y por eso abajo va la sensibilidad completa. Impuestos de un residente mexicano vía SIC: 20% al "
    "dividendo y a los intereses, 10% a la ganancia al vender; 0.25% de comisión por operación."
)

st.header("Los tres emisores")
mostrar_tabla(vistas_reglas.comparativo(list(resultados.values())))
st.caption(
    "TIR money-weighted de aportar 1,000 dólares al mes, vendiendo todo al final y pagando el impuesto "
    "(P9). «Sin reglas» es aportar lo mismo al MISMO papel cada mes (P6)."
)

ticker = st.sidebar.selectbox("Emisor", con_estudio)
r = resultados[ticker]


def grafica(nombre: str) -> None:
    st.plotly_chart(gr.FIGURAS[nombre](r, g.OSCURO), width="stretch", config={"displayModeBar": False})


st.header(f"{r.nombre} ({ticker})")
mod = r.tabla.loc[reglas.Variante.MODELO.value]
ben = r.tabla.loc[reglas.Variante.BENCHMARK.value]
k1, k2, k3, k4 = st.columns(4)
k1.metric("TIR del modelo, USD", f"{mod['tir_usd']:.2%}", help=f"En pesos: {mod['tir_mxn']:.2%}.")
k2.metric("Sin reglas, USD", f"{ben['tir_usd']:.2%}", help=f"En pesos: {ben['tir_mxn']:.2%}.")
k3.metric("Ventaja al año", f"{mod['ventaja_tir_usd'] * 1e4:+,.0f} pb")
k4.metric("Hoy", r.decision_hoy["decision"], help=f"Semáforo: {r.decision_hoy['accion']}.")

for c in reglas.conclusiones(r):
    with st.container(border=True):
        st.markdown(f"**{c.titulo}.** {c.texto}")

st.subheader("Qué decía el modelo cada mes")
grafica("decisiones")
mostrar_tabla(vistas_reglas.por_decision(r))
st.caption(
    "Lo que rindió el papel en los 12 meses siguientes a cada decisión. Las ventanas se enciman: "
    "las independientes son una por año."
)

st.subheader("Cuánto valdría lo aportado")
grafica("riqueza")
grafica("exposicion")
mostrar_tabla(vistas_reglas.variantes(r))

st.subheader("Las ventas por tesis rota")
ventas = vistas_reglas.ventas(r)
if ventas.empty:
    st.markdown("El modelo nunca vendió.")
else:
    mostrar_tabla(ventas)

st.subheader("¿La tesis rota llega a tiempo?")
st.markdown(
    "Cada vez que la Puerta 3 empezó a disparar —contando por reporte, como el modelo, y por "
    "trimestre de calendario—: qué había hecho el papel y qué hizo después."
)
eventos = vistas_reglas.eventos(r)
if eventos.empty:
    st.markdown("La Puerta 3 nunca disparó.")
else:
    mostrar_tabla(eventos)

st.subheader("Qué criterio movió al semáforo")
mostrar_tabla(vistas_reglas.criterios(r))

st.subheader("Sensibilidad a «comprar menos»")
mostrar_tabla(vistas_reglas.sensibilidad(r))
st.caption("Las tres, reportadas completas: ninguna se escogió por cómo salió.")

st.subheader("Qué tanto se le puede creer")
suficiencia(r.apuestas.episodios, "cambios de postura")
st.markdown(r.dictamen.como_texto())
if r.neutralizacion is not None:
    st.caption(r.neutralizacion.como_texto())

with st.expander("Metodología"):
    for texto in reglas.NOTAS_DE_METODO:
        st.markdown(f"- {texto}")
    st.markdown(
        f"- Con la persistencia contada por trimestre de calendario, la regla de tesis rota sola habría "
        f"vendido {ticker} {r.ventas_por_calendario} veces, contra "
        f"{len(r.variantes[reglas.Variante.SOLO_TESIS].ventas)} contada en reportes."
    )
    for a in r.avisos:
        st.caption(a)

descargo()
