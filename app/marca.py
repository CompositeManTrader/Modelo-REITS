"""Sistema de marca — Spread Trading Club · "Terminal Pro".

Fuente única de los tokens visuales. Todo lo que dibuja la aplicación —HTML
propio, gráficas de Plotly, tablas de Streamlit— sale de aquí, para que no haya
dos negros ni dos ámbares distintos en la misma pantalla.

Las tres reglas de la guía que este módulo hace cumplir por construcción:

1. **Un solo acento.** El ámbar es el único color de marca. No hay azul, ni
   menta, ni oro. El verde y el rojo existen únicamente como ganancia y pérdida,
   y solo en gráficas y estados de dato.
2. **Nunca solo por color.** Toda ganancia o pérdida va acompañada de ``▲``/``▼``
   —regla daltónica de la guía, §8—. Por eso `GLIFO_LUZ` vive junto a `COLOR_LUZ`
   y no separado: quien tome uno tiene el otro a la mano.
3. **Sin emojis.** La versión anterior semaforizaba con 🟢🟡🔴, que la guía
   prohíbe explícitamente. Los sustituyen glifos geométricos, que además se
   alinean en monoespaciada.

La tipografía reparte tres papeles: **Space Grotesk** titula, **Inter** lee y
**JetBrains Mono** cifra. Toda cifra va en mono con dígitos tabulares: en una
columna de números proporcionales las unidades no se alinean, y comparar dos
renglones deja de ser instantáneo.
"""

from __future__ import annotations

import streamlit as st

# --------------------------------------------------------------------------------------
# Color — tokens "Terminal Pro"
# --------------------------------------------------------------------------------------

NEGRO = "#0A0B0D"        # fondo base
SUPERFICIE = "#15171A"   # tarjetas
SUPERFICIE_2 = "#1F2630"  # superficie elevada
LINEA = "#262A30"        # bordes
AMBAR = "#F5A623"        # ÚNICO acento de marca
AMBAR_TENUE = "#C9821A"  # hover / pressed
BLANCO = "#F4F5F6"       # texto
GRIS = "#9AA1A9"         # texto secundario
GRIS_TENUE = "#6B6B66"   # texto terciario / descriptor
PAPEL = "#F7F6F3"        # fondo claro (piezas impresas)
PAPEL_TINTA = "#14130F"  # texto sobre claro
PROFIT = "#16C784"       # ganancia — solo gráficas y estados de dato
LOSS = "#EA3943"         # pérdida — solo gráficas y estados de dato

# El relleno de la zona de profit es un token FIJO de la guía: 14% sobre oscuro.
# Estaba en 32% en piezas viejas y se leía como marrón sucio.
RELLENO_PROFIT = "rgba(245,166,35,0.14)"
# El mismo ámbar, aún más tenue: para las mil trayectorias de fondo de un Monte
# Carlo, donde el trazo individual no es el dato —lo es la nube— y compite con
# los percentiles si tiene peso propio.
TRAZO_TENUE = "rgba(245,166,35,0.10)"

# --------------------------------------------------------------------------------------
# Semáforo de las tres puertas
# --------------------------------------------------------------------------------------
#
# El semáforo es SIGNIFICADO, no decoración: el código y las pruebas lo tratan
# como tal. Se mapea a los tokens de marca en vez de inventar colores nuevos, y
# cada luz viaja con su glifo para no depender del color.

COLOR_LUZ = {
    "VERDE": PROFIT,
    "AMARILLO": AMBAR,
    "ROJO": LOSS,
    "SIN DATOS": GRIS,
}
GLIFO_LUZ = {
    "VERDE": "▲",
    "AMARILLO": "◆",
    "ROJO": "▼",
    "SIN DATOS": "·",
}
# Nombre heredado. Se conserva porque varias páginas lo importan, pero ya no
# devuelve emojis: la guía los prohíbe.
ICONO_LUZ = GLIFO_LUZ

# --------------------------------------------------------------------------------------
# Tipografía y forma
# --------------------------------------------------------------------------------------

DISPLAY = "'Space Grotesk', Inter, system-ui, sans-serif"
TEXTO = "Inter, system-ui, -apple-system, sans-serif"
MONO = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

RADIO_TARJETA = "10px"
RADIO_CONTENEDOR = "14px"
RADIO_PILDORA = "4px"

# Motion de terminal: preciso y contenido, sin rebotes.
DUR_MICRO, DUR_BASE, DUR_ENTRADA, DUR_TRAZO = "120ms", "200ms", "320ms", "600ms"
EASE = "cubic-bezier(0.4,0,0.2,1)"

TAGLINE = "Donde el riesgo se define."


def signo(valor: float | None) -> str:
    """``▲`` / ``▼`` / ``·`` según el signo. La regla daltónica de la guía, §8.

    Ganancia y pérdida **nunca** se distinguen solo por color: el glifo va
    siempre, y es lo que sobrevive a una captura en blanco y negro o a un lector
    que no distingue el rojo del verde.
    """
    if valor is None:
        return "·"
    return "▲" if valor > 0 else ("▼" if valor < 0 else "·")


def color_signo(valor: float | None) -> str:
    if valor is None or valor == 0:
        return GRIS
    return PROFIT if valor > 0 else LOSS


# --------------------------------------------------------------------------------------
# El símbolo
# --------------------------------------------------------------------------------------


def marca_svg(alto: int = 30) -> str:
    """El símbolo: la curva de distribución con los dos strikes del spread.

    Se dibuja en línea en vez de cargar un archivo porque la aplicación corre en
    Streamlit Cloud, donde el sistema de archivos es efímero y un recurso que
    falta se dibuja como un cuadro roto en el encabezado.
    """
    ancho = int(alto * 1.55)
    return f"""
<svg width="{ancho}" height="{alto}" viewBox="0 0 62 40" fill="none"
     xmlns="http://www.w3.org/2000/svg" aria-label="Spread Trading Club">
  <path d="M2 34 C 12 34, 14 8, 31 8 C 48 8, 50 34, 60 34"
        stroke="{AMBAR}" stroke-width="2.4" stroke-linecap="round" fill="none"/>
  <path d="M20 34 C 20 34, 22 12.5, 31 12.5 C 40 12.5, 42 34, 42 34 Z"
        fill="{RELLENO_PROFIT}"/>
  <line x1="20" y1="12" x2="20" y2="36" stroke="{BLANCO}" stroke-width="1.8"
        stroke-linecap="round"/>
  <line x1="42" y1="12" x2="42" y2="36" stroke="{BLANCO}" stroke-width="1.8"
        stroke-linecap="round"/>
  <circle cx="20" cy="12" r="2.6" fill="{BLANCO}"/>
  <circle cx="42" cy="12" r="2.6" fill="{BLANCO}"/>
</svg>"""


# --------------------------------------------------------------------------------------
# Estilos globales
# --------------------------------------------------------------------------------------


def encabezado(seccion: str) -> None:
    """El lockup horizontal de marca, arriba de cada pantalla.

    Va en todas y no solo en una: una aplicación de siete pantallas donde el
    logotipo aparece en una sola no está marcada, está decorada. El descriptor
    «TRADING CLUB» va en gris acero, sin excepciones, y el nombre de la sección
    a la derecha ubica sin competir con la marca.
    """
    st.markdown(
        " ".join(f"""
        <div style="display:flex;align-items:center;gap:14px;padding:4px 0 14px">
          {marca_svg(30)}
          <div style="display:flex;flex-direction:column;gap:2px">
            <div style="font-family:{MONO};font-size:12px;font-weight:600;
                        letter-spacing:0.18em;text-transform:uppercase;color:{BLANCO}">
              SPREAD <span style="color:{GRIS}">TRADING CLUB</span>
            </div>
            <div style="font-size:11px;color:{GRIS_TENUE}">{TAGLINE}</div>
          </div>
          <div style="flex-grow:1;height:1px;background:{LINEA}"></div>
          <div style="font-family:{MONO};font-size:11px;letter-spacing:0.14em;
                      color:{GRIS}">{seccion.upper()}</div>
        </div>
        """.split()),
        unsafe_allow_html=True,
    )


def inyectar_estilos() -> None:
    """Carga tipografías y reglas base. Una vez por sesión."""
    if st.session_state.get("_estilos_marca"):
        return
    st.session_state["_estilos_marca"] = True
    st.markdown(
        # `@import` y no `<link>`: Streamlit descarta las etiquetas de enlace del
        # markdown, y la fuente no cargaría sin decir por qué.
        "<style>"
        "@import url('https://fonts.googleapis.com/css2?"
        "family=Space+Grotesk:wght@500;700&"
        "family=Inter:wght@400;500;600&"
        "family=JetBrains+Mono:wght@500;600&display=swap');"
        f"[data-testid='stAppViewContainer'],[data-testid='stSidebar']{{font-family:{TEXTO};}}"
        f"h1,h2,h3,h4{{font-family:{DISPLAY};letter-spacing:-.02em;line-height:1.12;}}"
        # Streamlit dibuja sus flechas y chevrones con una fuente de ÍCONOS cuyo
        # glifo se elige por ligadura: el texto del elemento es literalmente
        # "keyboard_arrow_right". Si la regla de arriba le cambia la familia, la
        # ligadura no existe y el nombre del ícono se dibuja como texto.
        "[data-testid='stIconMaterial'],.material-icons,.material-icons-outlined,"
        "[class*='material-symbols']"
        "{font-family:'Material Symbols Rounded','Material Icons'!important;}"
        f".cifra{{font-family:{MONO};font-variant-numeric:tabular-nums;}}"
        # Label de marca: mono, mayúsculas, tracking 0.18em, ámbar.
        ".rotulo{font-size:10px;font-weight:600;letter-spacing:0.18em;"
        f"text-transform:uppercase;color:{AMBAR};font-family:{MONO};}}"
        f".rotulo-gris{{color:{GRIS};}}"
        # Streamlit deja un hueco fijo entre bloques. Con secciones que ya traen
        # su propio marco, ese hueco duplica la separación y afloja la retícula.
        "div[data-testid='stVerticalBlock']{gap:0.6rem;}"
        # El dato entra, no salta: fundido + subida de 8px, nunca escalando.
        f"@keyframes entra{{from{{opacity:0;transform:translateY(8px);}}"
        "to{opacity:1;transform:none;}}"
        f"[data-testid='stMetric'],[data-testid='stPlotlyChart']"
        f"{{animation:entra {DUR_ENTRADA} {EASE} both;}}"
        "@media (prefers-reduced-motion:reduce){"
        "*{animation-duration:.01ms!important;transition-duration:.01ms!important;}}"
        "</style>",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------------------
# Plotly
# --------------------------------------------------------------------------------------


def plantilla_plotly() -> dict:
    """Estilo de gráfica de marca, listo para ``figura.update_layout(**...)``.

    Los gráficos SON la marca: fondo de la superficie, rejilla gris discreta, y
    el ámbar reservado para lo que importa. Sin esto, Plotly entra con su azul
    de fábrica, que es exactamente el color que la guía prohíbe.
    """
    ejes = {
        "gridcolor": LINEA,
        "zerolinecolor": SUPERFICIE_2,
        "linecolor": LINEA,
        "tickfont": {"color": GRIS, "size": 10, "family": MONO},
        "title": {"font": {"color": GRIS, "size": 11, "family": TEXTO}},
    }
    return {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": BLANCO, "family": TEXTO, "size": 12},
        "colorway": [AMBAR, GRIS, AMBAR_TENUE, GRIS_TENUE],
        "xaxis": dict(ejes),
        "yaxis": dict(ejes),
        "hoverlabel": {
            "bgcolor": SUPERFICIE_2,
            "bordercolor": LINEA,
            "font": {"color": BLANCO, "family": MONO, "size": 11},
        },
        "margin": {"t": 20, "b": 20, "l": 10, "r": 10},
    }


def escala_ambar() -> list[list]:
    """Escala divergente de marca para mapas de calor.

    Sustituye a ``RdYlGn``, que mete un amarillo y un verde de fábrica que no son
    de la paleta. Aquí los extremos son los tokens de pérdida y de ámbar, y el
    centro es la superficie elevada: lo neutro se ve neutro, no verde pálido.
    """
    return [
        [0.00, LOSS], [0.25, "#7A2B2E"], [0.45, SUPERFICIE_2],
        [0.55, "#5C4520"], [0.75, AMBAR_TENUE], [1.00, AMBAR],
    ]


def registrar_plantilla_plotly() -> None:
    """Hace de la marca la plantilla POR OMISIÓN de Plotly, para toda la aplicación.

    Se registra al importar este módulo, y no dentro de cada página, por una
    razón práctica: la aplicación tiene siete pantallas y unas veinte gráficas.
    Teñirlas una por una deja siempre alguna con el azul de fábrica de Plotly
    —el color que la guía prohíbe— y es justo la que se nota.
    """
    import plotly.graph_objects as go
    import plotly.io as pio

    if "stc" in pio.templates:
        return
    base = plantilla_plotly()
    pio.templates["stc"] = go.layout.Template(
        layout={
            "paper_bgcolor": base["paper_bgcolor"],
            "plot_bgcolor": base["plot_bgcolor"],
            "font": base["font"],
            "colorway": base["colorway"],
            "xaxis": base["xaxis"],
            "yaxis": base["yaxis"],
            "hoverlabel": base["hoverlabel"],
            "colorscale": {"sequential": escala_ambar(), "diverging": escala_ambar()},
            "legend": {"font": {"color": GRIS, "size": 11}},
            "title": {"font": {"color": BLANCO, "family": DISPLAY}},
        }
    )
    pio.templates.default = "stc"


registrar_plantilla_plotly()
