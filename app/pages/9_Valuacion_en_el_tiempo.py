"""Métodos de valuación en el tiempo: qué decía cada uno cada trimestre y qué pasó después.

Siete maneras de decir «caro o barato» —más su consenso—, evaluadas trimestre por
trimestre con lo que se sabía ese día, sobre los emisores con estudio de largo plazo.
Todo sale de ``src.estudio.metodos.estudiar``, el mismo objeto del PDF y del Excel.
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
from src.estudio import graficas_metodos as gm  # noqa: E402
from src.estudio import (
    intrinsecos,  # noqa: E402
    mercado,  # noqa: E402
    metodos,  # noqa: E402
    vistas_intrinsecos,  # noqa: E402
    vistas_metodos,  # noqa: E402
)

configurar("Valuación en el tiempo", "🧮")
inyectar_estilos()
encabezado("Valuación en el tiempo")
st.title("Métodos de valuación en el tiempo")

repo = exigir_base()
asof = selector_de_corte()

con_estudio = [t for t in sorted(repo.emisores()["ticker"]) if mercado.hay_estudio(t)]
if len(con_estudio) < 2:
    st.error("Hacen falta al menos dos emisores con estudio de largo plazo para comparar métodos entre ellos.")
    st.stop()


@st.cache_data(show_spinner="Evaluando los métodos trimestre por trimestre…", max_entries=4)
def _resultado(_repo, tickers: tuple[str, ...], asof, firma: tuple):
    from src.estudio import ampliacion

    return metodos.estudiar({t: mod_estudio.armar(_repo, t, asof=asof) for t in tickers},
                            asignar_entre=ampliacion.asignar_entre(tickers))


r = _resultado(repo, tuple(con_estudio), asof, firma_de_la_base())


def grafica(nombre: str, *args) -> None:
    st.plotly_chart(gm.FIGURAS[nombre](r, *args, t=g.OSCURO), width="stretch", config={"displayModeBar": False})


st.markdown(
    "Cada fin de mes, con lo que se había publicado ese día, cada método da un número donde más alto "
    "es más barato, y ese número se compara contra **la propia historia del emisor** hasta esa fecha: "
    "barato en el percentil 70 o más, caro abajo del 30, como el semáforo. Luego se mide qué rindió el "
    "papel en los 1, 3 y 5 años siguientes."
)
with st.expander("Los ocho métodos"):
    mostrar_tabla(vistas_metodos.metodos())

for c in metodos.conclusiones(r):
    with st.container(border=True):
        st.markdown(f"**{c.titulo}.** {c.texto}")

st.header("Qué dice cada método hoy")
mostrar_tabla(vistas_metodos.hoy(r), fijar_primera=True)
st.caption(f"Señal y percentil contra la historia propia, al {r.hasta:%d-%m-%Y}.")

st.header("¿Cuánto esperar ganar según qué tan caro está?")
st.markdown(
    "La investigación encontró que la valuación **no sirve para decidir cuándo entrar**, pero sí dice **cuánto "
    "esperar**. Cada fin de trimestre, el consenso de los siete métodos ubica a cada emisor en un tramo contra su "
    "propia historia; la gráfica muestra lo que de verdad rindieron los emisores en los 5 años siguientes desde cada "
    "tramo, **neto con un broker de EE. UU.** (marginal de 35%: 44% al dividendo y 35% al efectivo). «Caro» casi "
    "nunca quiso decir perder: quiso decir esperar menos, y aun así casi siempre más que el efectivo."
)
grafica("esperado")
mostrar_tabla(vistas_metodos.esperado_hoy(r), fijar_primera=True)
mostrar_tabla(vistas_metodos.esperado(r))
st.caption(
    "La caja va del percentil 25 al 75 de los retornos; los bigotes, del 10 al 90 (8 de cada 10 casos). Las "
    "ventanas de 5 años se enciman: las independientes son trimestres entre 20, y en los tramos extremos no llegan "
    "a dos. Es un rango de lo que pasó, no una promesa; con marginal de 30% el rango sube unas décimas."
)
suficiencia(int(r.esperado.loc[r.esperado["alcance"] == "juntos", "trimestres"].sum() // 20),
            "ventanas de 5 años independientes")

st.header("¿Predicen?")
st.plotly_chart(gm.barato_caro(r, g.OSCURO), width="stretch", config={"displayModeBar": False})
mostrar_tabla(vistas_metodos.juntos(r))
st.caption(
    "Los emisores juntos, un renglón por fin de trimestre. La correlación es de rangos (Spearman) "
    "entre el percentil y el retorno total neto de impuesto de los años siguientes. Las ventanas de 5 "
    "años se enciman: las independientes son una por cada 20 trimestres."
)

st.header("A cuál va la aportación")
_fuera = [t for t in r.paneles if t not in r.en_asignacion]
st.markdown(
    "Toda la aportación del mes —más los dividendos netos de todos— al emisor con el percentil más "
    "alto contra su propia historia. Sin guardar efectivo y sin vender: solo cambia a cuál va el dinero. "
    "El benchmark es repartirla en partes iguales, cada emisor reinvirtiendo sus propios dividendos. "
    f"Entran {', '.join(r.en_asignacion)}."
    + (f" {', '.join(_fuera)} no: su percentil empieza después de 2008 y acortaría la ventana de todos."
       if _fuera else "")
)
grafica("asignacion")
st.caption("Cuánta más riqueza tendría quien aportó con el consenso que quien repartió en partes iguales, "
           "con el mismo dinero aportado.")
mostrar_tabla(vistas_metodos.asignacion(r))
grafica("azar")
st.caption(
    "El espejo manda todo al MÁS caro: si el método sirve, debe salir peor que partes iguales. Las "
    "elecciones al azar conservan las rachas del consenso (cuántos meses se queda en un emisor y cuántas "
    "veces cambia) y solo sortean a cuál."
)
a = next(x for x in r.asignaciones if x.clave == "consenso")
suficiencia(a.cambios, "cambios de emisor")

st.subheader("Cada trimestre: a cuál iría la aportación")
mostrar_tabla(vistas_metodos.asignacion_trimestral(r), fijar_primera=True, height=360)

st.header("Emisor por emisor")
ticker = st.sidebar.selectbox("Emisor", list(r.paneles))
st.subheader(f"{r.nombres[ticker]} ({ticker})")
grafica("mapa", ticker)
grafica("dispersion", ticker)
mostrar_tabla(vistas_metodos.por_emisor(r, ticker))

st.subheader("¿Convenía esperar cuando decía caro?")
mostrar_tabla(vistas_metodos.esperar(r, ticker))
st.caption(
    "«Efectivo» es el T-bill de esos mismos 5 años, neto del 20% de impuesto. La TIR es de aportar "
    "1,000 dólares al mes a este papel solo: comprar todo y la reserva cuando dice barato, la mitad en "
    "medio, nada cuando dice caro, sin vender nunca, y nada espera más de 12 meses."
)

st.subheader("Los valores de cada trimestre")
mostrar_tabla(vistas_metodos.trimestres(r, ticker), fijar_primera=True, height=420)
st.caption(
    "Del más reciente al más viejo. El flujo es el FFO por acción de los últimos 12 meses conocido a "
    "esa fecha (o la medida con que se valúa cada emisor); el percentil sale de los fines de mes, con al "
    "menos 36 de historia. El libro de Excel `docs/estudios/valuacion_trimestral.xlsx` trae esta tabla "
    "completa para cada emisor."
)

ri = r.intrinsecos
if ri is not None:
    st.header("Modelos de valor: DDM, DCF y NAV")
    st.markdown(
        "Los siete métodos de arriba miden caro o barato contra la historia propia. Estos cuatro estiman "
        "cuánto **vale** la acción y lo comparan contra el precio: un DDM de Gordon sobre el dividendo, un "
        "DCF del AFFO en dos etapas, el crecimiento que descuenta el precio contra el que el emisor "
        "entregó, y un NAV armado desde los estados XBRL. Se prueban con su señal absoluta —comprar si "
        "vale 15% más que el precio— y contra su propia historia, igual que los otros. Las reglas y las "
        "hipótesis se fijaron en un commit antes de correr nada."
    )
    with st.expander("Los cuatro modelos"):
        mostrar_tabla(vistas_intrinsecos.modelos())
    for c in intrinsecos.conclusiones(ri, r):
        with st.container(border=True):
            st.markdown(f"**{c.titulo}.** {c.texto}")

    st.subheader("Qué dicen hoy")
    mostrar_tabla(vistas_intrinsecos.hoy(ri))
    st.caption("«Descuento del precio» es valor ÷ precio − 1: positivo, el precio está abajo del valor. En "
               "crecimiento es el entregado menos el implícito.")

    st.subheader(f"Precio contra valor: {ticker}")
    st.plotly_chart(gm.valores(ri, ticker, g.OSCURO), width="stretch", config={"displayModeBar": False})

    st.subheader("¿Predicen?")
    mostrar_tabla(vistas_intrinsecos.evaluacion(ri))
    st.caption("Los emisores juntos, por fin de trimestre. «Absoluta»: la correlación usa el valor contra "
               "el precio y la señal el margen de 15%. «Contra su historia»: el percentil, como los otros métodos.")

    st.subheader("Sensibilidad a la prima de riesgo")
    mostrar_tabla(vistas_intrinsecos.sensibilidad(ri))
    st.caption("Qué fracción de los meses la señal absoluta dijo «barato» y qué le hizo al backtest de "
               "aportación, con 2%, 3% y 4% sobre el Treasury.")

    st.subheader("A cuál, con los modelos de valor")
    mostrar_tabla(vistas_intrinsecos.asignacion(ri))

    st.subheader(f"Backtest de aportación: {ticker}")
    mostrar_tabla(vistas_intrinsecos.backtest(ri, ticker))

    st.subheader(f"Los modelos cada trimestre: {ticker}")
    mostrar_tabla(vistas_intrinsecos.trimestres(ri, ticker), fijar_primera=True, height=420)

    with st.expander("Validación del NAV contra el apalancamiento reportado"):
        mostrar_tabla(vistas_intrinsecos.validacion(ri))
        st.caption("Deuda neta ÷ (NOI − administración) armada desde XBRL contra la deuda neta ÷ EBITDAre que "
                   "reportó el emisor. Donde se aleja por razones de estructura, el NAV no se usa.")

with st.expander("Metodología"):
    for texto in metodos.NOTAS_DE_METODO:
        st.markdown(f"- {texto}")
    if ri is not None:
        st.markdown("**Modelos de valor**")
        for texto in intrinsecos.NOTAS_DE_METODO:
            st.markdown(f"- {texto}")

descargo()
