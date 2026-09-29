"""Las gráficas de la prueba del universo, para la pantalla y para el PDF.

El ámbar marca al tercil barato, el gris al resto; el rojo solo aparece para las trampas.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.estudio.graficas import OSCURO, Tema, _base, _etiquetas_finales, _rango_x
from src.estudio.seleccion import SENALES, ResultadoSeleccion


def riqueza(r: ResultadoSeleccion, senal: str = "historia", filtro: bool = False, t: Tema = OSCURO) -> go.Figure:
    """Cuánto valdría un dólar en cada tercil y en el universo completo."""
    m = r.carteras[(senal, filtro)].mensual
    estilos = {"barato": (t.principal, 2.4, "solid"), "medio": (t.contexto_2, 1.4, "dot"),
               "caro": (t.contexto, 1.6, "dash"), "todos": (t.texto, 1.6, "solid")}
    fig = go.Figure()
    items = []
    for g, (color, ancho, trazo) in estilos.items():
        v = (1 + m[g].fillna(0)).cumprod()
        fig.add_scatter(x=v.index, y=v, name=g.capitalize() if g != "todos" else "Todos (universo)",
                        line={"color": color, "width": ancho, "dash": trazo},
                        hovertemplate=f"{g}: %{{y:.2f}}<extra></extra>")
        items.append((v.index[-1], float(v.iloc[-1]), g, color))
    _etiquetas_finales(fig, t, items, log=True)
    fig = _base(fig, t, alto=360, eje_y="1 dólar invertido (escala log)", log_y=True, leyenda=True)
    fig.update_layout(legend={"y": 1.14})
    fig.update_xaxes(type="date")
    _rango_x(fig, m.index[0], m.index[-1])
    return fig


def trampas(r: ResultadoSeleccion, filtro: bool = False, t: Tema = OSCURO) -> go.Figure:
    """Qué fracción de cada tercil recortó su dividendo en los 12 meses siguientes."""
    fig = go.Figure()
    for g, color in (("barato", t.principal), ("medio", t.contexto_2), ("caro", t.contexto), ("todos", t.texto_2)):
        y = [float(r.trampas[(s, filtro)].loc[g, "recorto_despues"]) for s in SENALES]
        fig.add_bar(x=list(SENALES.values()), y=y, name=g, marker_color=color,
                    hovertemplate=f"%{{x}}<br>{g}: %{{y:.1%}} recortó<extra></extra>")
    fig = _base(fig, t, alto=320, eje_y="recortó su dividendo en los 12 meses siguientes", formato_y=".0%",
                leyenda=True)
    fig.update_layout(barmode="group", legend={"y": 1.14})
    return fig


def correlacion_anual(r: ResultadoSeleccion, t: Tema = OSCURO) -> go.Figure:
    """La correlación de cada señal con los 12 meses siguientes, promedio de cada año."""
    fig = go.Figure()
    colores = {"historia": t.principal, "sector": t.contexto, "ddm": t.contexto_2}
    for s, c in r.correlaciones.items():
        a = c.groupby(c.index.year).mean()
        fig.add_bar(x=a.index, y=a, name=SENALES[s], marker_color=colores[s],
                    hovertemplate=f"{SENALES[s]} %{{x}}: %{{y:+.2f}}<extra></extra>")
    fig = _base(fig, t, alto=320, eje_y="correlación con los 12 meses siguientes", leyenda=True)
    fig.update_layout(barmode="group", legend={"y": 1.14}, hovermode="closest")
    fig.add_hline(y=0, line={"color": t.contexto, "width": 1})
    return fig


def sorteos(r: ResultadoSeleccion, senal: str = "historia", t: Tema = OSCURO) -> go.Figure:
    """Barato menos caro de 200 repartos al azar, y dónde cae la señal."""
    x = r.sorteos.get(senal)
    real = r.carteras[(senal, False)].resumen.loc["barato menos caro", "retorno_anual"]
    fig = go.Figure()
    if x is not None and len(x):
        fig.add_histogram(x=pd.Series(x) * 100, nbinsx=30, marker_color=t.contexto_2, name="al azar",
                          hovertemplate="%{x:+.1f} puntos: %{y}<extra></extra>")
    fig.add_vline(x=real * 100, line={"color": t.principal, "width": 2})
    fig.add_annotation(x=real * 100, y=1, yref="paper", text=f"{SENALES[senal]}: {real * 100:+.1f}",
                       showarrow=False, font={"color": t.principal, "size": 11}, yanchor="bottom")
    fig = _base(fig, t, alto=260, eje_y="repartos al azar")
    fig.update_layout(hovermode="closest", margin={"t": 40})
    fig.update_xaxes(title={"text": "barato menos caro (puntos al año)"})
    return fig


FIGURAS = {"riqueza": riqueza, "trampas": trampas, "correlacion_anual": correlacion_anual, "sorteos": sorteos}
