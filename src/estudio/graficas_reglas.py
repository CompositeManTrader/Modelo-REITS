"""Las gráficas del backtest de reglas, para la pantalla y para el PDF.

Mismo criterio de color que ``graficas``: un acento (ámbar) y el gris de contexto.
Las cuatro decisiones no piden cuatro colores: COMPRAR y COMPRAR MENOS son el ámbar
en dos intensidades, NO COMPRAR es gris, y VENDER lleva el rojo semántico de pérdida.
Cada banda va además rotulada en la leyenda, para no depender solo del color.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.estudio.graficas import OSCURO, Tema, _base, _etiquetas_finales, _rango_x
from src.estudio.reglas import Decision, ResultadoReglas, Variante


def _color_banda(d: Decision, t: Tema) -> tuple[str, float] | None:
    return {
        Decision.COMPRAR: (t.principal, 0.30),
        Decision.COMPRAR_MENOS: (t.principal, 0.12),
        Decision.NO_COMPRAR: (t.contexto, 0.18),
        Decision.VENDER: (t.perdida, 0.28),
    }.get(d)


def tramos(decisiones: pd.Series) -> pd.DataFrame:
    """Meses seguidos con la misma decisión, como tramos [inicio, fin)."""
    if decisiones.empty:
        return pd.DataFrame(columns=["decision", "inicio", "fin"])
    cambio = decisiones != decisiones.shift(1)
    grupo = cambio.cumsum()
    filas = []
    fechas = list(decisiones.index)
    for _, bloque in decisiones.groupby(grupo):
        i0 = fechas.index(bloque.index[0])
        i1 = fechas.index(bloque.index[-1])
        fin = fechas[i1 + 1] if i1 + 1 < len(fechas) else bloque.index[-1] + pd.offsets.MonthEnd(1)
        filas.append({"decision": bloque.iloc[0], "inicio": fechas[i0], "fin": fin})
    return pd.DataFrame(filas)


def decisiones(r: ResultadoReglas, t: Tema = OSCURO) -> go.Figure:
    """El precio con la decisión de cada mes detrás, y cada venta y recompra marcada."""
    precio = r.precio.resample("W").last().dropna()
    fig = go.Figure()
    vistos = set()
    for _, tr in tramos(r.senales.mensual["decision"]).iterrows():
        d = Decision(tr["decision"])
        estilo = _color_banda(d, t)
        if estilo is None:
            continue
        color, opacidad = estilo
        fig.add_vrect(x0=tr["inicio"], x1=tr["fin"], fillcolor=color, opacity=opacidad, line_width=0, layer="below")
        if d not in vistos:
            vistos.add(d)
            # Entrada de leyenda para la banda (las formas no tienen leyenda propia).
            fig.add_scatter(x=[None], y=[None], mode="markers", name=d.value,
                            marker={"symbol": "square", "size": 12, "color": color, "opacity": min(1, opacidad * 2.5)})
    fig.add_scatter(x=precio.index, y=precio, name="Precio", line={"color": t.texto, "width": 1.4},
                    hovertemplate="%{y:$.2f}<extra></extra>", showlegend=False)
    v = r.ventas
    if not v.empty:
        fig.add_scatter(x=v["fecha"], y=v["precio"], mode="markers", name="Venta por tesis rota",
                        marker={"symbol": "triangle-down", "size": 12, "color": t.perdida,
                                "line": {"color": t.texto, "width": 1}},
                        customdata=v["disparadores"],
                        hovertemplate="Venta %{x|%b-%Y} a %{y:$.2f}<br>%{customdata}<extra></extra>")
        rec = v.dropna(subset=["reinversion"]) if "reinversion" in v else pd.DataFrame()
        if not rec.empty:
            fig.add_scatter(x=rec["reinversion"], y=rec["precio_reinversion"], mode="markers",
                            name="Lo vendido vuelve al papel",
                            marker={"symbol": "triangle-up", "size": 12, "color": t.ganancia,
                                    "line": {"color": t.texto, "width": 1}},
                            hovertemplate="Reinvierte %{x|%b-%Y} a %{y:$.2f}<extra></extra>")
    fig = _base(fig, t, alto=380, eje_y="precio por acción de hoy (escala log)", log_y=True, leyenda=True)
    fig.update_layout(legend={"y": 1.14})
    # La primera traza es la de la leyenda, sin datos: sin esto Plotly deduce un eje
    # numérico y el precio no se dibuja.
    fig.update_xaxes(type="date")
    _rango_x(fig, precio.index[0], precio.index[-1])
    return fig


def riqueza(r: ResultadoReglas, t: Tema = OSCURO) -> go.Figure:
    """Cuánto valdría lo aportado con cada variante, contra el benchmark del mismo papel."""
    fig = go.Figure()
    items = []
    estilos = {
        Variante.MODELO: (t.principal, 2.2, "solid"),
        Variante.MODELO_12M: (t.principal, 1.4, "dash"),
        Variante.BENCHMARK: (t.contexto, 2.0, "solid"),
        Variante.SOLO_VALUACION_12M: (t.contexto_2, 1.2, "dot"),
    }
    for v, (color, ancho, trazo) in estilos.items():
        s = r.variantes[v].diaria["riqueza"].resample("ME").last().dropna()
        s = s[s > 0]
        fig.add_scatter(x=s.index, y=s, name=v.value, line={"color": color, "width": ancho, "dash": trazo},
                        hovertemplate=f"{v.value}: %{{y:$,.0f}}<extra></extra>")
        if v in (Variante.MODELO, Variante.BENCHMARK):
            items.append((s.index[-1], float(s.iloc[-1]), "Modelo" if v is Variante.MODELO else "Sin reglas", color))
    aportado = (-r.benchmark.flujos_usd.clip(upper=0)).cumsum()
    aportado = aportado[aportado > 0]
    fig.add_scatter(x=aportado.index, y=aportado, name="Aportado", line={"color": t.contexto, "width": 1, "dash": "dot"},
                    hovertemplate="Aportado: %{y:$,.0f}<extra></extra>")
    _etiquetas_finales(fig, t, items, log=True)
    fig = _base(fig, t, alto=380, eje_y="dólares (escala log)", log_y=True, leyenda=True)
    fig.update_layout(legend={"y": 1.14})
    fig.update_xaxes(type="date")
    _rango_x(fig, aportado.index[0], r.hasta)
    return fig


def exposicion(r: ResultadoReglas, t: Tema = OSCURO) -> go.Figure:
    """Qué parte de lo acumulado estaba en el papel; el resto, en la reserva."""
    d = r.modelo.diaria
    f = (d["valor_posicion"] / d["riqueza"].where(d["riqueza"] > 0)).resample("ME").last().dropna()
    fig = go.Figure()
    fig.add_scatter(x=f.index, y=f, fill="tozeroy", line={"color": t.principal, "width": 1.6},
                    fillcolor="rgba(245,166,35,0.15)" if t.nombre == "oscuro" else "rgba(184,116,20,0.15)",
                    hovertemplate="En el papel: %{y:.0%}<extra></extra>")
    fig = _base(fig, t, alto=240, eje_y="en el papel (resto: reserva)", formato_y=".0%")
    fig.update_yaxes(range=[0, 1.02])
    _rango_x(fig, f.index[0], f.index[-1])
    return fig


FIGURAS = {"decisiones": decisiones, "riqueza": riqueza, "exposicion": exposicion}
