"""¿Cuándo entrar a los REITs y en cuáles? La investigación pre-registrada (``docs/investigacion/``).

Lee los resultados guardados en ``data/investigacion/resultados``: no recalcula ni abre los
mercados sellados de la prueba final, que se abren una sola vez desde
``scripts/investigacion.py``. Esta pantalla no toca la red.
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
from src.investigacion import conclusiones, resultados, vistas  # noqa: E402
from src.investigacion import graficas as gi  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent.parent
PDF = RAIZ / "docs" / "investigacion" / "investigacion_cuando_entrar.pdf"

configurar("Investigación", "🔬")
inyectar_estilos()
encabezado("Investigación")
st.title("¿Cuándo entrar a los REITs y en cuáles?")

if not resultados.hay_resultados():
    st.error("No están guardados los resultados. Corre `python scripts/investigacion.py exploracion`, `fase5`, "
             "`fase7`, `fase8` y, con la identificación ante la SEC, `emisores` y `fase6`.")
    st.stop()


@st.cache_data(show_spinner=False, max_entries=2)
def _resultados(marca: float) -> dict:
    return resultados.cargar()


res = _resultados(max(p.stat().st_mtime for p in resultados.DIR_RESULTADOS.rglob("*") if p.is_file()))


def grafica(nombre: str) -> None:
    st.plotly_chart(gi.FIGURAS[nombre](res, t=g.OSCURO), width="stretch", config={"displayModeBar": False})


st.markdown(
    "Una investigación hecha para poder contestar «no existe»: cada hipótesis, señal y criterio se guardó en el "
    "repositorio **antes** de correrla; los datos se partieron antes de verlos —desarrollo hasta 2015, validación "
    "desde 2016— y ocho mercados de otros países se sellaron sin mirarlos para una prueba final que se abre una "
    "sola vez. Todo con la contabilidad de un inversionista mexicano que aporta cada mes por el SIC: 20% al "
    "dividendo, 10% a la ganancia, 0.25% de comisión."
)
if PDF.exists():
    st.download_button("Descargar el informe en PDF", PDF.read_bytes(), file_name=PDF.name, mime="application/pdf")

for c in conclusiones.conclusiones(res):
    with st.container(border=True):
        st.markdown(f"**{c.titulo}.** {c.texto}")

st.header("Las fases")
mostrar_tabla(vistas.fases(res))

st.header("1. El techo: cuánto valdría conocer el futuro")
grafica("techo")
st.caption("Aportando 1,000 dólares al mes de 1972 a 2015. «Solo decide el dinero nuevo» nunca vende; «puede vender» "
           "rebalancea toda la riqueza, pagando 10% sobre la ganancia. Escala logarítmica.")
col1, col2 = st.columns(2)
with col1:
    st.subheader("Las caídas de 20% o más")
    mostrar_tabla(vistas.caidas(res))
with col2:
    st.subheader("¿Qué tan seguido ganó el efectivo?")
    mostrar_tabla(vistas.frecuencia(res))
with st.expander("De dónde salió el retorno del sector, 1972-2015"):
    mostrar_tabla(vistas.descomposicion(res))
    mostrar_tabla(vistas.techo(res))

st.header("2. Las señales de entrada")
grafica("reglas")
st.caption("Cada regla contra aportar siempre, rebalanceando, en la muestra de desarrollo. El círculo vacío es la "
           "misma regla ejecutada un mes después de la señal. La línea roja es el criterio de +50 pb.")
mostrar_tabla(vistas.reglas(res), fijar_primera=True)

st.header("3. La escalera de modelos")
grafica("escalera")
st.caption("Cinco modelos estimados siempre con el pasado (ventana creciente, re-estimación anual). Salen del "
           "mercado solo si pronostican que el efectivo ganará en los 12 meses siguientes.")
mostrar_tabla(vistas.escalera(res))

st.header("4. La prueba final: protección por tendencia")
st.markdown("Dentro si el precio está arriba de su promedio de 10 meses; si no, en efectivo. Se escogió **después** "
            "de ver el desarrollo, y así se declaró antes de abrir la prueba.")
grafica("prueba_final")
st.caption("Cada punto es un mercado: cuánto bajó la caída máxima contra cuánto costó en TIR. El criterio pide caer "
           "en el área verde.")
grafica("tendencia_eeuu")
st.caption("El índice de REITs de EE. UU. desde 1972; en gris, los meses en que la tendencia estaba en efectivo.")
mostrar_tabla(vistas.prueba_final(res), fijar_primera=True)

if "fase6" in res:
    st.header("5. En cuáles REITs")
    st.markdown("Todos los REITs de capital de EE. UU. desde 2011, **incluidos los que quebraron o fueron comprados** "
                "(precios de los formularios 13F de la SEC y estados financieros de XBRL conocidos a su fecha). Cada "
                "trimestre, cada regla escoge a un tercio de los elegibles y la aportación va a ellos, sin vender "
                "nunca, contra repartirla entre todos. Un tercio de los emisores se selló sin mirarlo para la prueba "
                "final.")
    grafica("seleccion")
    st.caption("Cada regla en desarrollo (2011-2015) y las que siguieron, en validación (2016-2026) y en los emisores "
               "sellados. La línea roja es el criterio de +50 pb. «Recortes»: fracción que recortó el dividendo o "
               "quebró en el año siguiente.")
    mostrar_tabla(vistas.seleccion(res), fijar_primera=True)

with st.expander("Cómo se hizo"):
    st.markdown(
        "* **Plan y reglas del juego** (`docs/investigacion/PLAN.md`): objetivo, muestras y criterios de éxito, "
        "fijados antes de tocar los datos y congelados en código.\n"
        "* **El candado** (`src/investigacion/muestras.py`): el código no deja ver 2016 en adelante sin dejar "
        "constancia, y no abre los mercados sellados sin un modelo congelado ni si sus archivos cambiaron.\n"
        "* **La bitácora** (`data/investigacion/bitacora.csv`): cada configuración probada, con su commit; el "
        "Sharpe deflactado y la probabilidad de sobreajuste usan ese conteo.\n"
        "* **La literatura** (`docs/investigacion/literatura.md`): 99 fuentes con la evidencia a favor y en contra.\n"
        "* **Los resultados de cada fase**: `docs/investigacion/fase3_exploracion.md`, `fase5_resultados.md`, "
        "`fase7_resultados.md`, `fase8_resultados.md` y `fase6_resultados.md` (con la corrección declarada).\n"
        "* **Los datos de la SEC** (`data/investigacion/emisores/`): el universo, el panel y su validación contra "
        "Yahoo y contra el FFO publicado; los emisores sellados, con su huella digital."
    )

descargo()
