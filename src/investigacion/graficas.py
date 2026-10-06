"""Las gráficas de la investigación, para la página y el PDF. Leen los resultados guardados.

El ámbar marca lo que se está juzgando; el gris, el contexto; el rojo solo aparece para el
umbral del criterio.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.estudio.graficas import OSCURO, Tema, _base, _rango_x
from src.investigacion.diseno import CRITERIOS, MUESTRAS

NOMBRES_MERCADO = {"japon": "Japón", "australia": "Australia", "singapur": "Singapur", "hong_kong": "Hong Kong",
                   "reino_unido": "Reino Unido", "europa_continental": "Europa", "canada": "Canadá",
                   "mexico_fibras": "FIBRAs"}


def _pb(v: float) -> str:
    x = int(round(v))
    return f"{x:+,d} pb" if x else "0 pb"


def techo(res: dict, t: Tema = OSCURO) -> go.Figure:
    """Cuánto valdría conocer el futuro, decidiendo solo el dinero nuevo o pudiendo vender."""
    d = res["fase3"]["techo"]
    d = d[d["regla"] != "aportar siempre"]
    reglas = ["oráculo de los 12 meses siguientes", "fuera en cada caída de 20% o más (del máximo al mínimo)",
              "oráculo del mes siguiente"]
    etiquetas = ["Sabe los 12 meses siguientes", "Sabe cuándo viene cada caída", "Sabe el mes siguiente"]
    fig = go.Figure()
    for modo, color, nombre in (("nunca vende", t.contexto, "Solo decide el dinero nuevo"),
                                ("rebalancea", t.principal, "Puede vender y volver a entrar")):
        x = [float(d[(d["regla"] == r) & (d["modo"] == modo)]["contra_aportar_siempre_bps"].iloc[0]) for r in reglas]
        fig.add_bar(y=etiquetas, x=x, orientation="h", name=nombre, marker_color=color,
                    text=[f"{v:+,.0f}" for v in x], textposition="outside", textfont={"family": t.mono, "size": 11},
                    hovertemplate="%{y}: %{x:+,.0f} pb al año<extra>" + nombre + "</extra>")
    fig = _base(fig, t, alto=300, leyenda=True)
    fig.update_layout(barmode="group", hovermode="closest", legend={"y": 1.18}, margin={"l": 210, "r": 40})
    fig.update_xaxes(title={"text": "contra aportar siempre (pb al año de TIR)"}, type="log",
                     tickvals=[10, 30, 100, 300, 1000, 3000], range=[1, 3.75])
    return fig


def reglas(res: dict, t: Tema = OSCURO) -> go.Figure:
    """Las 22 reglas de la fase 5: lo que ganan rebalanceando y con un mes de retraso."""
    d = res["fase5"]["desarrollo"].sort_values("mejora_rebalanceo")
    etiqueta = [f"{s} · {'por signo' if r == 'signo' else r.split(' ')[0]}" for s, r in zip(d["senal"], d["regla"],
                                                                                           strict=True)]
    etiqueta = [e.replace("· fuera", "· fuera en el peor quintil").replace("· continua", "· continua 50-100%")
                for e in etiqueta]
    fig = go.Figure()
    fig.add_scatter(x=d["mejora_rebalanceo_con_rezago"] * 1e4, y=etiqueta, mode="markers", name="con un mes de retraso",
                    marker={"color": t.contexto, "size": 8, "symbol": "circle-open"},
                    hovertemplate="%{y}<br>con retraso: %{x:+,.0f} pb<extra></extra>")
    fig.add_scatter(x=d["mejora_rebalanceo"] * 1e4, y=etiqueta, mode="markers", name="ejecutando al cierre",
                    marker={"color": t.principal, "size": 9},
                    hovertemplate="%{y}<br>%{x:+,.0f} pb al año<extra></extra>")
    fig.add_vline(x=0, line={"color": t.contexto, "width": 1})
    fig.add_vline(x=CRITERIOS.mejora_minima_de_tir * 1e4, line={"color": t.perdida, "width": 1, "dash": "dot"})
    fig = _base(fig, t, alto=560, leyenda=True)
    fig.update_layout(hovermode="closest", legend={"y": 1.06, "x": 0}, margin={"l": 330, "r": 30, "b": 48})
    fig.update_xaxes(title={"text": "contra aportar siempre, rebalanceando (pb al año), 1972-2015"})
    fig.update_yaxes(tickfont={"family": "Inter, system-ui, sans-serif", "size": 10})
    return fig


def escalera(res: dict, t: Tema = OSCURO) -> go.Figure:
    """Los cinco peldaños de la fase 7."""
    d = res["fase7"]["evaluacion"]
    fig = go.Figure()
    y = d["mejora_rebalanceo"] * 1e4
    fig.add_bar(x=d["senal"], y=y, marker_color=[t.principal if v > 0 else t.contexto for v in y],
                text=[f"{_pb(v)}<br>caída {c:.0%}" for v, c in zip(y, d["caida_rebalanceo"], strict=True)],
                textposition="outside", textfont={"family": t.mono, "size": 10},
                hovertemplate="%{x}: %{y:+,.0f} pb al año<extra></extra>")
    fig.add_hline(y=0, line={"color": t.contexto, "width": 1})
    fig = _base(fig, t, alto=320, eje_y="contra aportar siempre (pb al año)")
    fig.update_layout(hovermode="closest")
    fig.update_yaxes(range=[min(-450, float(y.min()) * 1.3), 120])
    return fig


def prueba_final(res: dict, t: Tema = OSCURO) -> go.Figure:
    """Cada mercado: cuánto bajó la caída y cuánto costó. El rectángulo es lo que pide el criterio."""
    m = res["fase8"]["mercados"]
    v = res["fase8"]["resumen"]["validacion"]
    x = list(m["reduccion_de_caida"] * 100) + [v["reduccion_de_caida"] * 100]
    y = list(m["mejora"] * 1e4) + [v["mejora"] * 1e4]
    nombres = [NOMBRES_MERCADO.get(n, n) for n in m["mercado"]] + ["EE. UU. 2016+"]
    fig = go.Figure()
    fig.add_shape(type="rect", x0=CRITERIOS.reduccion_minima_de_caida * 100, x1=80,
                  y0=-CRITERIOS.costo_maximo_de_la_proteccion * 1e4, y1=450,
                  fillcolor="rgba(22,199,132,0.10)", line={"width": 0}, layer="below")
    fig.add_annotation(x=79, y=-CRITERIOS.costo_maximo_de_la_proteccion * 1e4 + 8, text="lo que pide el criterio",
                       showarrow=False, xanchor="right", yanchor="bottom", font={"color": t.ganancia, "size": 10})
    colores = [t.principal] * len(m) + [t.texto]
    fig.add_scatter(x=x, y=y, mode="markers+text", text=nombres, textposition="top center",
                    marker={"color": colores, "size": 10}, textfont={"size": 10, "color": t.texto_2},
                    hovertemplate="%{text}<br>caída %{x:.0f}% menor<br>%{y:+,.0f} pb al año<extra></extra>")
    fig.add_hline(y=0, line={"color": t.contexto, "width": 1})
    fig = _base(fig, t, alto=400)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(title={"text": "cuánto bajó la caída máxima (%)"}, range=[-20, 80])
    fig.update_yaxes(title={"text": "tendencia contra aportar siempre (pb al año)"}, range=[-560, 450])
    return fig


def tendencia_eeuu(res: dict, t: Tema = OSCURO) -> go.Figure:
    """El índice de REITs de EE. UU. y los meses en que la tendencia estaba fuera (en efectivo)."""
    s = res["fase8"]["tendencia_eeuu"].copy()
    s["fecha"] = pd.to_datetime(s["fecha"])
    fig = go.Figure()
    fuera = (s["exposicion"] == 0).to_numpy()
    inicio = None
    for i, f in enumerate(fuera):
        if f and inicio is None:
            inicio = s["fecha"].iloc[i]
        if (not f or i == len(fuera) - 1) and inicio is not None:
            fin = s["fecha"].iloc[i]
            fig.add_vrect(x0=inicio, x1=fin, fillcolor=t.contexto_2, opacity=0.25, line_width=0, layer="below")
            inicio = None
    fig.add_scatter(x=s["fecha"], y=s["indice_total"], name="FTSE Nareit All Equity (retorno total)",
                    line={"color": t.principal, "width": 1.8}, hovertemplate="%{x|%m-%Y}: %{y:,.0f}<extra></extra>")
    fig.add_vline(x=MUESTRAS.validacion_desde, line={"color": t.texto_2, "width": 1, "dash": "dot"})
    fig.add_annotation(x=MUESTRAS.validacion_desde, y=1.0, yref="paper", text="validación →", showarrow=False,
                       xanchor="left", font={"color": t.texto_2, "size": 10})
    fig = _base(fig, t, alto=360, eje_y="retorno total, escala log (dic-1971 = 100)", log_y=True)
    marcas = [100, 300, 1_000, 3_000, 10_000, 30_000, 100_000]
    fig.update_yaxes(tickvals=marcas, ticktext=[f"{m:,}" for m in marcas])
    _rango_x(fig, s["fecha"].min(), s["fecha"].max())
    return fig


def seleccion(res: dict, t: Tema = OSCURO) -> go.Figure:
    """Las 16 reglas de la fase 6 en desarrollo, y las que siguieron, en validación y en los sellados."""
    from src.investigacion.fase6 import DETECTOR, NOMBRES

    f6 = res["fase6"]
    d = f6["desarrollo"].sort_values("mejora")
    etiqueta = [NOMBRES.get(r, r) for r in d["regla"]]
    fig = go.Figure()
    fig.add_scatter(x=d["mejora"] * 1e4, y=etiqueta, mode="markers", name="desarrollo 2011-2015",
                    marker={"color": t.principal, "size": 9},
                    hovertemplate="%{y}<br>desarrollo: %{x:+,.0f} pb al año<extra></extra>")
    v = f6["validacion"]
    v = v[v["regla"] != DETECTOR]
    fig.add_scatter(x=v["mejora"] * 1e4, y=[NOMBRES.get(r, r) for r in v["regla"]], mode="markers",
                    name="validación 2016-2026", marker={"color": t.contexto, "size": 11, "symbol": "diamond-open"},
                    hovertemplate="%{y}<br>validación: %{x:+,.0f} pb al año<extra></extra>")
    if "final" in f6:
        fin = f6["final"]
        fig.add_scatter(x=fin["mejora"] * 1e4, y=[NOMBRES.get(r, r) for r in fin["regla"]], mode="markers",
                        name="prueba final (sellados)", marker={"color": t.perdida, "size": 12, "symbol": "x"},
                        hovertemplate="%{y}<br>prueba final: %{x:+,.0f} pb al año<extra></extra>")
    fig.add_vline(x=0, line={"color": t.contexto, "width": 1})
    fig.add_vline(x=CRITERIOS.mejora_minima_de_tir * 1e4, line={"color": t.perdida, "width": 1, "dash": "dot"})
    fig = _base(fig, t, alto=480, leyenda=True)
    fig.update_layout(hovermode="closest", legend={"y": 1.08, "x": 0}, margin={"l": 270, "r": 30, "b": 48})
    fig.update_xaxes(title={"text": "TIR contra aportar a todos los elegibles (pb al año, después de impuestos)"})
    fig.update_yaxes(tickfont={"family": "Inter, system-ui, sans-serif", "size": 10})
    return fig


FIGURAS = {"techo": techo, "reglas": reglas, "escalera": escalera, "prueba_final": prueba_final,
           "seleccion": seleccion,
           "tendencia_eeuu": tendencia_eeuu}

