"""Las gráficas de los métodos de valuación, para la pantalla y para el PDF.

Mismo criterio de color que ``graficas``: el ámbar marca lo barato y lo que se recomienda,
el gris es contexto; el rojo solo aparece para una pérdida.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.estudio.graficas import OSCURO, Tema, _base, _etiquetas_finales, _rango_x
from src.estudio.metodos import METODOS, ResultadoMetodos, trimestral, ventaja_acumulada


def mapa(r: ResultadoMetodos, ticker: str, t: Tema = OSCURO) -> go.Figure:
    """Cada trimestre, el percentil de cada método: ámbar = barato, gris = caro."""
    q = trimestral(r.paneles[ticker])
    z = np.array([q[f"p_{m.clave}"].to_numpy(float) for m in METODOS])
    fig = go.Figure(go.Heatmap(
        x=q.index, y=[m.nombre for m in METODOS], z=z, zmin=0, zmax=1,
        colorscale=[[0, t.rejilla], [0.3, t.contexto_2], [0.7, "rgba(245,166,35,0.45)"], [1, t.principal]],
        colorbar={"title": {"text": "percentil", "font": {"color": t.texto_2, "size": 10}},
                  "tickformat": ".0%", "tickfont": {"color": t.texto_2, "size": 9}, "thickness": 10},
        hovertemplate="%{y}<br>%{x|%b-%Y}: percentil %{z:.0%}<extra></extra>", xgap=0, ygap=2,
    ))
    fig = _base(fig, t, alto=320)
    fig.update_layout(hovermode="closest", margin={"l": 210, "r": 20})
    fig.update_yaxes(autorange="reversed", tickfont={"size": 10})
    return fig


def barato_caro(r: ResultadoMetodos, t: Tema = OSCURO) -> go.Figure:
    """Retorno anual de los 5 años siguientes cuando cada método decía barato, medio o caro."""
    todos = pd.concat([trimestral(p) for p in r.paneles.values()])
    fig = go.Figure()
    for nivel, color in (("barato", t.principal), ("medio", t.contexto_2), ("caro", t.contexto)):
        y = [float(todos.loc[todos[f"s_{m.clave}"] == nivel, "adelante_5a"].median()) for m in METODOS]
        fig.add_bar(x=[m.nombre for m in METODOS], y=y, name=f"decía {nivel}", marker_color=color,
                    hovertemplate=f"%{{x}}<br>{nivel}: %{{y:.1%}} al año<extra></extra>")
    fig = _base(fig, t, alto=340, eje_y="retorno anual, 5 años siguientes (mediana)", formato_y=".0%",
                leyenda=True)
    fig.update_layout(barmode="group", legend={"y": 1.14})
    fig.update_xaxes(tickangle=-20, tickfont={"size": 9})
    return fig


def dispersion(r: ResultadoMetodos, ticker: str, clave: str = "consenso", t: Tema = OSCURO) -> go.Figure:
    """Cada trimestre: el percentil del método contra lo que rindió el papel los 5 años siguientes."""
    q = trimestral(r.paneles[ticker]).dropna(subset=[f"p_{clave}", "adelante_5a"])
    fig = go.Figure()
    fig.add_vrect(x0=0.7, x1=1.0, fillcolor=t.principal, opacity=0.08, line_width=0, layer="below")
    fig.add_vrect(x0=0.0, x1=0.3, fillcolor=t.contexto, opacity=0.08, line_width=0, layer="below")
    fig.add_scatter(x=q[f"p_{clave}"], y=q["adelante_5a"], mode="markers",
                    marker={"color": t.principal, "size": 7, "opacity": 0.8},
                    customdata=[f"{f.year}-T{(f.month - 1) // 3 + 1}" for f in q.index],
                    hovertemplate="%{customdata}: percentil %{x:.0%} → %{y:.1%} al año<extra></extra>")
    fig = _base(fig, t, alto=320, eje_y="retorno anual, 5 años siguientes", formato_y=".0%")
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(range=[0, 1], tickformat=".0%", title={"text": "percentil ese trimestre (← caro · barato →)"})
    return fig


def asignacion(r: ResultadoMetodos, clave: str = "consenso", t: Tema = OSCURO) -> go.Figure:
    """Cuánta más riqueza con el método que con partes iguales, con el mismo dinero aportado."""
    ventaja = ventaja_acumulada(next(x for x in r.asignaciones if x.clave == clave))
    fig = go.Figure()
    fig.add_hline(y=0, line={"color": t.contexto, "width": 1})
    fig.add_scatter(x=ventaja.index, y=ventaja, name="Ventaja acumulada", line={"color": t.principal, "width": 2},
                    fill="tozeroy",
                    fillcolor="rgba(245,166,35,0.15)" if t.nombre == "oscuro" else "rgba(184,116,20,0.15)",
                    hovertemplate="%{x|%b-%Y}: %{y:+.1%} de riqueza<extra></extra>")
    _etiquetas_finales(fig, t, [(ventaja.index[-1], float(ventaja.iloc[-1]),
                                 f"{ventaja.iloc[-1]:+.1%}", t.principal)])
    fig = _base(fig, t, alto=300, eje_y="riqueza contra partes iguales", formato_y="+.0%")
    fig.update_xaxes(type="date")
    _rango_x(fig, ventaja.index[0], ventaja.index[-1])
    return fig


def azar(r: ResultadoMetodos, clave: str = "consenso", t: Tema = OSCURO) -> go.Figure:
    """Las elecciones al azar con las mismas rachas, y dónde cae el método y su espejo."""
    a = next(x for x in r.asignaciones if x.clave == clave)
    fig = go.Figure()
    fig.add_histogram(x=a.azar * 1e4, nbinsx=30, marker_color=t.contexto_2, name="al azar",
                      hovertemplate="%{x:+.0f} pb: %{y} elecciones<extra></extra>")
    for x, texto, color in ((a.ventaja, "el método", t.principal), (a.ventaja_el_mas_caro, "al más caro", t.perdida)):
        fig.add_vline(x=x * 1e4, line={"color": color, "width": 2})
        fig.add_annotation(x=x * 1e4, y=1, yref="paper", text=f"{texto}: {x * 1e4:+.0f} pb", showarrow=False,
                           font={"color": color, "size": 11}, yanchor="bottom")
    fig = _base(fig, t, alto=280, eje_y="elecciones al azar")
    fig.update_layout(hovermode="closest", margin={"t": 40})
    fig.update_xaxes(title={"text": "ventaja de TIR contra partes iguales (pb al año)"})
    return fig


FIGURAS = {"mapa": mapa, "barato_caro": barato_caro, "dispersion": dispersion,
           "asignacion": asignacion, "azar": azar}


def valores(ri, ticker: str, t: Tema = OSCURO) -> go.Figure:
    """El precio contra lo que decía valer cada modelo, cada fin de mes."""
    p = ri.paneles[ticker]
    fig = go.Figure()
    items = []
    series = (("precio", "Precio", t.texto, 1.6, "solid"), ("nav", "NAV aproximado", t.principal, 2.2, "solid"),
              ("valor_ddm", "DDM", t.contexto, 1.4, "dot"), ("valor_dcf", "DCF", t.contexto_2, 1.4, "dash"))
    for columna, nombre, color, ancho, trazo in series:
        s = p[columna].dropna()
        s = s[s > 0]
        if s.empty:
            continue
        fig.add_scatter(x=s.index, y=s, name=nombre, line={"color": color, "width": ancho, "dash": trazo},
                        hovertemplate=f"{nombre}: %{{y:$,.2f}}<extra></extra>")
        items.append((s.index[-1], float(s.iloc[-1]), nombre.split(" ")[0], color))
    _etiquetas_finales(fig, t, items, log=True)
    fig = _base(fig, t, alto=360, eje_y="dólares por acción (escala log)", log_y=True, leyenda=True)
    fig.update_layout(legend={"y": 1.14})
    fig.update_xaxes(type="date")
    inicio = p["valor_ddm"].first_valid_index() or p.index[0]
    _rango_x(fig, inicio, p.index[-1])
    return fig


FIGURAS["valores"] = valores
