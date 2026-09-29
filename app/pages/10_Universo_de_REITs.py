"""¿La valuación sabe escoger REITs? La prueba sobre todos los REITs de capital que cotizan hoy.

Todo sale de ``src.estudio.seleccion.estudiar``, el mismo objeto del PDF. Los datos están
versionados en ``data/estudios/universo``; esta pantalla no toca la red.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from comun import configurar, descargo, mostrar_tabla  # noqa: E402

from marca import encabezado, inyectar_estilos  # noqa: E402
from src.estudio import graficas as g  # noqa: E402
from src.estudio import graficas_seleccion as gs  # noqa: E402
from src.estudio import (
    seleccion,  # noqa: E402
    universo,  # noqa: E402
    vistas_seleccion,  # noqa: E402
)

configurar("Universo de REITs", "🌐")
inyectar_estilos()
encabezado("Universo de REITs")
st.title("¿La valuación sabe escoger REITs?")

if not universo.hay_universo():
    st.error("No está versionado el universo. Corre `python scripts/estudio.py universo`.")
    st.stop()


@st.cache_data(show_spinner="Corriendo la prueba sobre el universo…", max_entries=2)
def _resultado(marca: float):
    return seleccion.estudiar()


r = _resultado((universo.DIR_UNIVERSO / "manifiesto.json").stat().st_mtime)


def grafica(nombre: str, *args) -> None:
    st.plotly_chart(gs.FIGURAS[nombre](r, *args, t=g.OSCURO), width="stretch", config={"displayModeBar": False})


n = int((r.universo["meses_elegible"] > 0).sum())
st.markdown(
    f"Todos los REITs de capital que cotizan hoy en Estados Unidos —{n} con al menos cinco años de historia— "
    "puestos a la misma pregunta: cada fin de mes se reparten en tres grupos según una señal de valuación "
    "y se mide qué rindió cada grupo contra comprar **todos** por partes iguales, y qué fracción de los "
    "«baratos» resultó trampa (recortó su dividendo o se desplomó)."
)
st.warning(
    "**Sesgo de supervivencia.** Aquí no están los REITs que quebraron o fueron comprados: ninguna fuente "
    "disponible trae su precio. Sí están los que se desplomaron y siguen cotizando. Las cifras de las "
    "señales que comparan emisores entre sí hay que leerlas como un techo."
)

for c in seleccion.conclusiones(r):
    with st.container(border=True):
        st.markdown(f"**{c.titulo}.** {c.texto}")

st.header("Las tres señales")
senal = st.sidebar.radio("Señal", list(seleccion.SENALES), format_func=seleccion.SENALES.get)
filtro = st.sidebar.toggle("Solo con dividendo intacto", value=False,
                           help="Fuera los que recortaron el dividendo en los 12 meses previos.")
grafica("riqueza", senal, filtro)
mostrar_tabla(vistas_seleccion.grupos(r, filtro=filtro))
st.caption("Carteras de pesos iguales de cada tercil, con 12 cohortes encimadas de 12 meses. «Brecha contra "
           "todos»: retorno anual del tercil menos el del universo completo con el mismo método. La t es de "
           "Newey-West; arriba de 2 es difícil de atribuir al azar.")

st.subheader("¿Predicen?")
grafica("correlacion_anual")
mostrar_tabla(vistas_seleccion.correlacion(r))
grafica("sorteos", senal)

st.subheader("¿Cuántos baratos eran trampa?")
grafica("trampas", filtro)
mostrar_tabla(vistas_seleccion.trampas(r))

st.subheader("Aportando cada mes")
mostrar_tabla(vistas_seleccion.aportacion(r))
st.caption("1,000 dólares al mes repartidos entre los baratos de esa señal, sin vender nunca, contra lo mismo "
           "repartido entre todos los elegibles. Antes de impuestos y comisiones, iguales para todas.")

st.subheader("¿Y a plazos más largos?")
mostrar_tabla(vistas_seleccion.plazos(r))
st.caption("Exploratorio, no estaba en el diseño: la mediana del retorno anualizado de cada REIT de cada "
           "tercil a 1, 3 y 5 años. A plazos largos es donde más pesa el sesgo: los baratos que no aguantaron "
           "cinco años no están.")

st.subheader("¿Aguanta en cada mitad y en cada sector?")
mostrar_tabla(vistas_seleccion.mitades(r))
mostrar_tabla(vistas_seleccion.sectores(r))

st.subheader("¿Y sin los dividendos especiales?")
mostrar_tabla(vistas_seleccion.robustez(r))
st.caption("Yahoo no marca los dividendos especiales. Aquí se quitan los pagos de más del doble de la mediana "
           "de los cuatro anteriores del mismo emisor y se repite todo.")

st.header("Qué dice hoy cada REIT")
mostrar_tabla(vistas_seleccion.hoy(r), fijar_primera=True, height=480)
st.caption(f"Los elegibles al {r.hasta:%m-%Y}. «Percentil historia»: su yield contra sus propios meses anteriores. "
           "«Razón contra sector»: su yield entre la mediana de su sector (1.2x es 20% más). «Descuento DDM»: valor de Gordon entre "
           "precio menos uno; sin DDM quien no pagaba dividendo hace cinco años (los hoteles lo suspendieron en 2020).")

with st.expander("Diseño y datos"):
    st.markdown(seleccion.__doc__ or "")

descargo()
