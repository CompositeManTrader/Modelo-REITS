"""Estudio de largo plazo: qué le ha pasado al REIT, cuánto pagó y cuándo convenía.

La página de valuación contesta «¿está caro hoy?». Esta contesta las preguntas
lentas: qué le pasó al negocio desde que cotiza, de dónde salió lo que rindió,
en qué momentos hubiera convenido entrar —con lo que se sabía ese día— y si lo
que paga hoy compensa el riesgo contra el Udibono.

Todo lo que se ve sale de ``src.estudio.estudio.armar``, el mismo objeto con el
que se genera el PDF: la pantalla y el impreso no pueden decir cifras distintas.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from comun import (  # noqa: E402
    configurar,
    descargo,
    exigir_base,
    explicar,
    firma_de_la_base,
    mostrar_tabla,
    selector_de_corte,
    suficiencia,
)

from marca import COLOR_LUZ, GLIFO_LUZ, encabezado, inyectar_estilos  # noqa: E402
from src.estudio import estudio as mod_estudio  # noqa: E402
from src.estudio import graficas as g  # noqa: E402
from src.estudio import historia as hist  # noqa: E402
from src.estudio import (
    mercado,  # noqa: E402
    vistas,  # noqa: E402
)

RAIZ = Path(__file__).resolve().parent.parent.parent
DIR_PDF = RAIZ / "docs" / "estudios"

configurar("Estudio", "📚")
inyectar_estilos()
encabezado("Estudio")
st.title("Estudio de largo plazo")

repo = exigir_base()
asof = selector_de_corte()

con_estudio = [t for t in sorted(repo.emisores()["ticker"]) if mercado.hay_historia(t)]
if not con_estudio:
    st.error(
        "Ningún emisor tiene todavía su historia de mercado larga. Se arma con "
        "`python scripts/estudio.py mercado TICKER`."
    )
    st.stop()
ticker = st.sidebar.selectbox("Emisor", con_estudio, help=(
    "Solo aparecen los emisores con historia de mercado desde su listado. Para agregar uno: "
    "`python scripts/estudio.py mercado TICKER`, y su narrativa en `src/estudio/historia.py`."
))


@st.cache_data(show_spinner="Armando el estudio…", max_entries=8)
def _estudio(_repo, ticker: str, asof, firma: tuple):
    return mod_estudio.armar(_repo, ticker, asof=asof)


e = _estudio(repo, ticker, asof, firma_de_la_base())
n = e.narrativa
t0 = e.tabla.index[0]


def grafica(nombre: str) -> None:
    st.plotly_chart(g.FIGURAS[nombre](e, g.OSCURO), width="stretch", config={"displayModeBar": False})


# --------------------------------------------------------------------------------------
# Encabezado
# --------------------------------------------------------------------------------------

st.subheader(n.nombre if n else ticker)
if n:
    st.markdown(n.perfil)

anios = (e.tabla.index[-1] - t0).days / 365.25
rt_mxn = e.tabla["rt_mxn"].dropna()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Retorno anual, USD", f"{e.total.retorno_total:.1%}",
          help=f"Desde el listado en {t0:%Y}, con los dividendos reinvertidos y la escisión de "
               "Orion incluida.")
if len(rt_mxn) > 1:
    anios_mxn = (rt_mxn.index[-1] - rt_mxn.index[0]).days / 365.25
    k2.metric("Retorno anual, MXN", f"{(rt_mxn.iloc[-1] / rt_mxn.iloc[0]) ** (1 / anios_mxn) - 1:.1%}",
              help="Incluye la devaluación de 1994-95, que coincidió con el listado.")
k3.metric("Dividendo hoy", f"{e.hoy.yield_actual:.2%}",
          help=f"Mensualidad vigente × 12 = {e.hoy.dividendo_anualizado:.3f} dólares por acción.")
if e.hoy.p_ffo is not None:
    # La mediana va en la etiqueta y no como «delta»: Streamlit le pone flecha al
    # delta, y una flecha hacia arriba junto a un múltiplo se lee «subió».
    k4.metric(f"P/FFO hoy · mediana {e.tabla['p_ffo'].median():.1f}x", f"{e.hoy.p_ffo:.1f}x")

for aviso in e.avisos:
    st.caption(aviso)

# --------------------------------------------------------------------------------------
# Lo que dice el estudio
# --------------------------------------------------------------------------------------

st.header("Lo que dice el estudio")
LUZ = {"favorable": "VERDE", "desfavorable": "ROJO", "neutral": "AMARILLO"}
for c in e.conclusiones:
    luz = LUZ.get(c.tono, "AMARILLO")
    with st.container(border=True):
        st.markdown(
            f"<span style='color:{COLOR_LUZ[luz]};font-size:18px'>{GLIFO_LUZ[luz]}</span> "
            f"**{c.titulo}**", unsafe_allow_html=True,
        )
        st.markdown(c.texto)

pdf = DIR_PDF / f"estudio_{ticker}.pdf"
if pdf.exists():
    st.download_button(
        "Descargar el estudio en PDF", data=pdf.read_bytes(), file_name=pdf.name,
        mime="application/pdf",
        help="Generado con `python scripts/estudio.py pdf TICKER`. Las cifras son las del día "
             "en que se generó; las de esta pantalla se actualizan con la base.",
    )

# --------------------------------------------------------------------------------------
# Historia
# --------------------------------------------------------------------------------------

st.header("La historia")
if n:
    st.markdown(n.modelo_de_negocio)
    incluir_industria = st.toggle("Incluir los cambios de la industria REIT", value=True)
    hitos = list(n.hitos) + (list(hist.INDUSTRIA) if incluir_industria else [])
    hitos = sorted((h for h in hitos if h.fecha <= asof), key=lambda h: h.fecha)
    # Lista y no tabla: el detalle de cada hito es un párrafo, y en una celda se
    # trunca justo donde empieza a decir algo.
    for h in hitos:
        fuente = f"[{h.fuente}]({h.url})" if h.url else h.fuente
        marca_industria = " · *industria*" if h.categoria == "industria" else ""
        st.markdown(
            f"<span class='cifra rotulo-gris'>{h.fecha_texto}</span>{marca_industria}  \n"
            f"**{h.titulo}.** {h.detalle} <span style='font-size:12px;opacity:.7'>— {fuente}</span>",
            unsafe_allow_html=True,
        )
else:
    st.info(f"{ticker} todavía no tiene narrativa escrita; se muestran solo las cifras.")

# --------------------------------------------------------------------------------------
# El negocio
# --------------------------------------------------------------------------------------

st.header("El negocio en el tiempo")
explicar("FFO", "AFFO")
st.markdown(
    "**Por acción.** Todo en acciones de hoy: lo anterior al split de 2005 va dividido entre "
    "dos. El FFO y el AFFO son los que publicó el emisor —10-K y comunicados antes de 2019, "
    "8-K después—; no se derivan desde la contabilidad, por la razón que explica la sección "
    "de metodología."
)
grafica("por_accion")

st.markdown(
    "**El negocio creció mucho más que la acción.** O crece emitiendo acciones para comprar "
    "inmuebles. Lo que le importa al accionista no es cuánto crece la empresa sino cuánto "
    "crece su parte: el FFO **por acción**."
)
grafica("escala")

st.markdown(
    "**El motor: comprar por encima de lo que cuesta el capital.** Si O compra a un yield "
    "mayor que el que rinde su propia acción, cada compra con acciones suma por acción; si "
    "compra por debajo, resta aunque la empresa crezca."
)
grafica("spread_inversion")
if not e.spread_inversion.empty:
    # Las vistas eligen nombres que `mostrar_tabla` interpreta en la unidad correcta.
    mostrar_tabla(vistas.spread_inversion(e))

with st.expander("Apalancamiento en libros"):
    grafica("apalancamiento")
    st.caption(
        "Deuda ÷ activos totales en libros. La deuda neta ÷ EBITDAre se calcula desde 2015: "
        "antes, las ventas de inmuebles iban a operaciones discontinuadas y el EBITDAre "
        "derivado de XBRL no es confiable. En 2021 el cociente salta porque la deuda al cierre "
        "ya incluye a VEREIT y el EBITDAre solo dos meses de ella; el emisor reporta 5.3x pro forma."
    )

with st.expander("La tabla anual completa, con la fuente de cada cifra"):
    mostrar_tabla(vistas.anual(e), fijar_primera=True)
    fuentes = e.anual.attrs.get("fuentes")
    if fuentes is not None:
        st.caption("De dónde salió cada celda:")
        st.dataframe(fuentes.reset_index(), hide_index=True, width="stretch")

# --------------------------------------------------------------------------------------
# Valuación
# --------------------------------------------------------------------------------------

st.header("Qué tan caro ha estado")
st.markdown(
    "**Contra su propia historia.** Precio ÷ FFO por acción **conocido ese día**: el de cada "
    "fecha usa solo lo que se había publicado entonces. La franja gris es el 60% central de "
    "la historia; la línea punteada, la mediana."
)
grafica("multiplo")
st.markdown(
    "**Contra el bono.** Un REIT de arrendamiento neto compite con el Treasury por el mismo "
    "ahorrador: contratos largos, renta que sube poco a poco. Cuando el bono paga más, al "
    "REIT le exigen más yield y su precio baja."
)
grafica("yield_bono")
grafica("spread")

# --------------------------------------------------------------------------------------
# De dónde salió el retorno
# --------------------------------------------------------------------------------------

st.header("De dónde salió el retorno")
st.markdown(
    "Un dólar invertido el día del listado, reinvirtiendo cada dividendo. La escala es "
    "logarítmica: la misma distancia vertical es el mismo porcentaje."
)
grafica("retorno_total")
st.markdown(
    "**Negocio contra mercado.** El precio es el dividendo ÷ el yield, así que el retorno se "
    "reparte exacto en lo que produjo el negocio —el dividendo cobrado y su crecimiento— y lo "
    "que puso o quitó el mercado al cambiar lo que paga por cada dólar de dividendo."
)
if e.eras:
    grafica("eras")
    mostrar_tabla(vistas.eras(e))
    if n:
        for era in n.eras:
            if pd.Timestamp(era.inicio) < e.tabla.index[-1]:
                with st.expander(f"{era.nombre} · {era.inicio:%Y}–{(era.fin or asof):%Y}"):
                    st.markdown(era.resumen)

# --------------------------------------------------------------------------------------
# Cuándo convenía entrar
# --------------------------------------------------------------------------------------

st.header("¿Cuándo hubiera convenido entrar?")
st.markdown(
    "Cada punto es un fin de mes: qué tan caro estaba O ese día —con el FFO que se conocía— y "
    "cuánto rindió al año en los cinco años siguientes. Los rombos son la mediana de cada "
    "quinto de la historia, del más caro al más barato."
)
grafica("entradas")
ent = e.entradas
if not ent.quintiles.empty:
    mostrar_tabla(vistas.quintiles(e))
suficiencia(ent.apuestas_efectivas.get("5 años", 0), "ventanas de cinco años que no se enciman")
st.caption(" · ".join(f"Correlación de rangos, {k}: {v:+.2f}" for k, v in ent.correlaciones.items()))

st.markdown("**Los cinco mejores momentos para comprar** (por retorno a 5 años, separados al "
            "menos 18 meses para no contar el mismo episodio cinco veces)")
mostrar_tabla(vistas.momentos(ent.mejores))
st.markdown("**Los cinco peores**")
mostrar_tabla(vistas.momentos(ent.peores))

st.markdown(
    "**Y si hubieras comprado en cualquier mes, ¿cuánto llevarías al año hasta hoy?** El "
    "«yield sobre costo» es el dividendo de hoy dividido entre lo que pagaste: cuánto te paga "
    "HOY lo que compraste entonces."
)
grafica("retorno_a_hoy")
mostrar_tabla(vistas.yield_sobre_costo(e))

# --------------------------------------------------------------------------------------
# Lo que paga hoy
# --------------------------------------------------------------------------------------

st.header("¿Paga buen retorno hoy?")
h = e.hoy
m1, m2, m3, m4 = st.columns(4)
m1.metric("Dividendo", f"{h.yield_actual:.2%}")
if h.p_affo is not None:
    m2.metric("AFFO yield", f"{h.affo_yield:.2%}", help=f"P/AFFO {h.p_affo:.1f}x")
if h.spread is not None:
    m3.metric(f"Spread vs bono · pctl {h.percentil_spread:.0%}", f"{h.spread:.2%}",
              help="Yield de O menos el Treasury a 10 años, y en qué percentil de su historia está.")
if h.udibono_real is not None:
    m4.metric("Udibono 10a (real)", f"{h.udibono_real:.2%}")
grafica("escenarios")
mostrar_tabla(vistas.escenarios(e))
for s in h.supuestos:
    st.caption(s)

# --------------------------------------------------------------------------------------
# Riesgos
# --------------------------------------------------------------------------------------

if n:
    st.header("Riesgos")
    for r in n.riesgos:
        with st.container(border=True):
            st.markdown(f"**{r.titulo}.** {r.texto}")

# --------------------------------------------------------------------------------------
# Metodología
# --------------------------------------------------------------------------------------

with st.expander("Metodología, validaciones y fuentes"):
    man = e.historia_mercado.manifiesto
    v = man.get("validacion", {})
    st.markdown(
        f"**Precio desde {man['precios']['desde']}** ({man['precios']['n']:,} cierres). El "
        "proveedor entrega el cierre ajustado por split y por la escisión de Orion; aquí se "
        "desajusta para tener el precio al que de verdad cotizó (P2). Contra el precio crudo del "
        f"proveedor diario: {v.get('traslape_n', 0):,} días de traslape, error máximo "
        f"{(v.get('traslape_error_max') or 0):.4%}."
    )
    for a in v.get("anclas", []):
        st.caption(f"Ancla NYSE {a['fecha']}: real {a['real']:.2f}, reconstruido "
                   f"{a['reconstruido']:.2f} ({a['error']:+.3%}).")
    if e.serie.validacion_rt is not None:
        st.markdown(f"**Retorno total** contra el índice ajustado del proveedor: desviación "
                    f"máxima de {e.serie.validacion_rt:.2%} en toda la historia.")
    if man.get("correcciones_de_dividendos"):
        st.markdown("**Dividendos corregidos contra el reporte del emisor:**")
        for c in man["correcciones_de_dividendos"]:
            st.caption(c)
    st.markdown(
        "**Por qué el FFO no se deriva de la contabilidad.** La fórmula de Nareit aplicada a "
        "XBRL cuadra con lo reportado en los años recientes y falla por más de 15% antes de "
        "2015, cuando las ventas de inmuebles iban a operaciones discontinuadas:"
    )
    mostrar_tabla(vistas.diagnostico_ffo(e))
    st.markdown("**Fuentes**")
    if n:
        for titulo, texto in n.fuentes_extra:
            st.caption(f"{titulo}: {texto}")
    prim = e.primarios[["anio", "concepto", "valor", "base", "metodo", "fuente", "fecha_publicacion"]]
    st.dataframe(prim, hide_index=True, width="stretch")

descargo()
