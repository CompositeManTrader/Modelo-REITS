"""Las gráficas del estudio, una sola vez, para la pantalla y para el papel.

La página y el PDF dibujan con estas mismas funciones. Si cada uno tuviera las
suyas, tarde o temprano una tendría la mediana y la otra no, y el lector que
compara pantalla contra impreso encontraría dos estudios distintos.

Color
-----
La marca tiene UN acento (ámbar) y el gris es contexto. Validado con el revisor de
paletas: ámbar y gris se separan bien para daltonismo y visión normal, pero el
gris no tiene croma, y eso es deliberado. Por eso ninguna gráfica pide cuatro
colores de categoría: cada una tiene una serie protagonista en ámbar, el contexto
en gris, y etiquetas directas sobre las líneas para que la identidad nunca dependa
solo del color.

En papel, el ámbar de pantalla no llega a 3:1 de contraste sobre el fondo claro
(2.9). El tema claro usa #B87414, que sí pasa, y conserva el mismo tono.

Los valores repiten los tokens de ``app/marca.py`` porque ``src`` no importa de
``app``; una prueba verifica que no se separen.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go


@dataclass(frozen=True)
class Tema:
    nombre: str
    fondo: str
    texto: str
    texto_2: str
    rejilla: str
    principal: str
    contexto: str
    contexto_2: str
    ganancia: str
    perdida: str
    mascara: str = "#0A0B0D"   # fondo opaco detrás de una etiqueta que cae sobre una línea
    texto_fuente: str = "Inter, system-ui, sans-serif"
    mono: str = "'JetBrains Mono', ui-monospace, monospace"


OSCURO = Tema(
    nombre="oscuro", fondo="rgba(0,0,0,0)", texto="#F4F5F6", texto_2="#9AA1A9",
    rejilla="#262A30", principal="#F5A623", contexto="#9AA1A9", contexto_2="#6B6B66",
    ganancia="#16C784", perdida="#EA3943",
)
CLARO = Tema(
    nombre="claro", fondo="#F7F6F3", texto="#14130F", texto_2="#6B6B66",
    rejilla="#E4E2DD", principal="#B87414", contexto="#6B6B66", contexto_2="#9AA1A9",
    ganancia="#16C784", perdida="#EA3943", mascara="#F7F6F3",
)

MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def mes(fecha) -> str:
    """«feb-2009», no «Feb-2009»: ``strftime`` escribe el mes en inglés."""
    return f"{MESES[fecha.month - 1]}-{fecha.year}"


def _base(fig: go.Figure, t: Tema, *, alto: int = 360, eje_y: str = "", formato_y: str | None = None,
          log_y: bool = False, leyenda: bool = False) -> go.Figure:
    ejes = {
        "gridcolor": t.rejilla, "zerolinecolor": t.rejilla, "linecolor": t.rejilla,
        "tickfont": {"color": t.texto_2, "size": 10, "family": t.mono},
        "title": {"font": {"color": t.texto_2, "size": 11, "family": t.texto_fuente}},
    }
    fig.update_layout(
        height=alto, paper_bgcolor=t.fondo, plot_bgcolor=t.fondo,
        font={"color": t.texto, "family": t.texto_fuente, "size": 12},
        # El margen derecho es de las etiquetas finales: si ya se ensanchó para que
        # quepan («Yield NNN 5.9%» es más largo que «Yield O 5.9%»), no se encoge.
        margin={"t": 24, "b": 36, "l": 56, "r": max(90, fig.layout.margin.r or 0)}, showlegend=leyenda,
        legend={"orientation": "h", "y": 1.08, "x": 0, "font": {"color": t.texto_2, "size": 11}},
        hovermode="x unified",
        hoverlabel={"bgcolor": "#1F2630" if t.nombre == "oscuro" else "#FFFFFF",
                        "bordercolor": t.rejilla, "font": {"family": t.mono, "size": 11,
                                                         "color": t.texto}},
        xaxis=ejes, yaxis={**ejes, "title": {"text": eje_y, "font": ejes["title"]["font"]}},
    )
    if formato_y:
        fig.update_yaxes(tickformat=formato_y)
    if log_y:
        fig.update_yaxes(type="log")
    return fig


def _etiquetas_finales(fig: go.Figure, t: Tema, items: list[tuple], *, log: bool = False,
                       separacion: float = 0.06) -> None:
    """Etiquetas directas al final de cada línea, sin encimarse.

    ``items`` = [(x, y, texto, color), ...]. Si dos quedan más cerca que
    ``separacion`` del rango vertical, se abren en pixeles hacia arriba y abajo.
    Dos series que terminan casi en el mismo valor —el FFO y el AFFO de O en
    2025— producían «AFF0044237», que no se lee como ninguna de las dos.

    En un eje logarítmico Plotly espera la posición de la anotación en log10: con
    el valor lineal, una etiqueta en 46 se dibuja en 10^46 y arrastra el eje.
    """
    vivos = [(x, float(y), txt, c) for x, y, txt, c in items
             if y is not None and not (isinstance(y, float) and np.isnan(y))]
    if not vivos:
        return
    pos = [np.log10(y) if log else y for _, y, _, _ in vivos]
    # La cercanía se mide contra el rango del EJE, no contra el de las etiquetas.
    # Con dos etiquetas casi iguales, su propio rango es su diferencia, y la
    # cercanía relativa siempre daba 100%: nunca se separaban.
    datos = []
    for traza in fig.data:
        ys = getattr(traza, "y", None)
        if ys is None:
            continue
        v = pd.to_numeric(pd.Series(list(ys)), errors="coerce").dropna()
        v = v[v > 0] if log else v
        datos.extend(np.log10(v) if log else v)
    todos = [*pos, *datos]
    rango = (max(todos) - min(todos)) or 1.0
    orden = sorted(range(len(vivos)), key=lambda i: pos[i])
    desplazamiento = [0.0] * len(vivos)
    for a, b in zip(orden, orden[1:], strict=False):
        if (pos[b] - pos[a]) / rango < separacion:
            desplazamiento[a] -= 8
            desplazamiento[b] += 8
    for (x, _, texto, color), y, dy in zip(vivos, pos, desplazamiento, strict=True):
        fig.add_annotation(x=x, y=y, text=texto, showarrow=False, xanchor="left", xshift=6,
                           yshift=dy, font={"color": color, "size": 11, "family": t.mono})
    # Que la etiqueta más larga quepa: ~6.8 px por carácter en la mono de 11 pt, más
    # el desplazamiento. Sin esto «Dividendo 2.36» se cortaba en «Dividendo 2.3».
    necesario = int(14 + 6.8 * max(len(txt) for _, _, txt, _ in vivos))
    fig.update_layout(margin={"r": max(necesario, fig.layout.margin.r or 0)})


def _rango_x(fig: go.Figure, x0, x1) -> None:
    """El eje termina donde termina el dato; el margen derecho es para las etiquetas."""
    fig.update_xaxes(range=[x0, x1])


def _ultimo(s: pd.Series):
    s = s.dropna()
    return (s.index[-1], float(s.iloc[-1])) if not s.empty else (None, None)


# --------------------------------------------------------------------------------------
# Retorno total
# --------------------------------------------------------------------------------------


def retorno_total(e, t: Tema = OSCURO) -> go.Figure:
    """Valor de 1 dólar (o 1 peso) invertido al listarse, dividendos reinvertidos."""
    # Semanal: en treinta años el trazo diario es indistinguible y pesa diez veces más.
    s = e.tabla[["rt_usd", "rt_mxn"]].resample("W").last()
    usd = s["rt_usd"] / s["rt_usd"].dropna().iloc[0]
    mxn = s["rt_mxn"] / s["rt_mxn"].dropna().iloc[0]
    fig = go.Figure()
    fig.add_scatter(x=mxn.index, y=mxn, name="En pesos", line={"color": t.contexto, "width": 1.6},
                    hovertemplate="En pesos: ×%{y:,.1f}<extra></extra>")
    fig.add_scatter(x=usd.index, y=usd, name="En dólares", line={"color": t.principal, "width": 2},
                    hovertemplate="En dólares: ×%{y:,.1f}<extra></extra>")
    items = []
    for serie, nombre, color in ((usd, "Dólares", t.principal), (mxn, "Pesos", t.contexto)):
        x, y = _ultimo(serie)
        items.append((x, y, f"{nombre} ×{y:,.0f}", color))
    _etiquetas_finales(fig, t, items, log=True)
    fig = _base(fig, t, alto=380, eje_y="veces lo invertido (escala log)", log_y=True)
    fig.update_yaxes(tickvals=[1, 2, 5, 10, 20, 50, 100, 200, 500],
                     ticktext=["1", "2", "5", "10", "20", "50", "100", "200", "500"])
    _rango_x(fig, s.index[0], s.index[-1])
    return fig


def eras(e, t: Tema = OSCURO) -> go.Figure:
    """Por era: lo que produjo el negocio contra lo que puso o quitó el mercado."""
    filas = []
    for d in e.eras:
        negocio = (1 + d.ingreso) * (1 + d.crecimiento_dividendo) - 1
        filas.append((d.nombre, negocio, d.revaluacion, d.retorno_total,
                      f"{d.inicio:%Y}–{d.fin:%Y}"))
    df = pd.DataFrame(filas, columns=["era", "negocio", "revaluacion", "total", "periodo"])
    etiquetas = [f"{a}<br><span style='font-size:10px'>{p}</span>" for a, p in zip(df["era"], df["periodo"], strict=True)]
    fig = go.Figure()
    fig.add_bar(y=etiquetas, x=df["negocio"], orientation="h", name="Negocio: dividendo cobrado + crecimiento",
                marker_color=t.principal, hovertemplate="Negocio: %{x:.1%}<extra></extra>")
    fig.add_bar(y=etiquetas, x=df["revaluacion"], orientation="h", name="Mercado: cambio de valuación",
                marker_color=t.contexto, hovertemplate="Revaluación: %{x:.1%}<extra></extra>")
    fig.add_scatter(y=etiquetas, x=df["total"], mode="markers", name="Retorno total anual",
                    marker={"symbol": "diamond", "size": 10, "color": t.texto, "line": {"color": t.fondo, "width": 2}},
                    hovertemplate="Total: %{x:.1%}<extra></extra>")
    # La cifra va a la derecha de lo que esté más a la derecha en su renglón —barra o
    # rombo—, no junto al rombo: con un total cerca de cero (WPC, 1998-1999) quedaba
    # encima de la barra del negocio.
    extremos = [*df["negocio"], *df["revaluacion"], *df["total"]]
    rango = (max(extremos) - min(extremos)) or 0.1
    fig.add_scatter(y=etiquetas, x=df[["negocio", "revaluacion", "total"]].max(axis=1).clip(lower=0) + 0.015 * rango,
                    mode="text", text=[f"{v:+.1%}" for v in df["total"]], textposition="middle right",
                    textfont={"family": t.mono, "size": 11, "color": t.texto}, showlegend=False, hoverinfo="skip")
    fig = _base(fig, t, alto=60 + 52 * len(df), formato_y=None, leyenda=True)
    fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08, hovermode="closest",
                      yaxis={"autorange": "reversed"}, margin={"l": 210, "r": 60, "t": 40, "b": 30})
    fig.update_xaxes(tickformat=".0%", zeroline=True, zerolinecolor=t.texto_2)
    # Espacio para la etiqueta del total a la derecha del rombo más alejado.
    # Proporcional al rango: con un total de +40.7% (NNN, 2009-2013) un margen fijo de
    # 10 puntos dejaba la etiqueta cortada en el borde.
    fig.update_xaxes(range=[min(extremos) - 0.06 * rango, max(extremos) + 0.24 * rango])
    return fig


# --------------------------------------------------------------------------------------
# El negocio
# --------------------------------------------------------------------------------------


def por_accion(e, t: Tema = OSCURO) -> go.Figure:
    a = e.anual
    fig = go.Figure()
    series = (
        ("ffo_por_accion", "FFO", t.contexto, "solid"),
        ("affo_por_accion", "AFFO", t.contexto, "dot"),
        ("dividendo_por_accion", "Dividendo", t.principal, "solid"),
    )
    items = []
    for col, nombre, color, trazo in series:
        s = a[col].dropna() if col in a else pd.Series(dtype=float)
        if s.empty:
            continue
        fig.add_scatter(x=s.index, y=s, name=nombre, mode="lines+markers",
                        line={"color": color, "width": 2, "dash": trazo}, marker={"size": 5},
                        hovertemplate=f"{nombre}: %{{y:$.2f}}<extra></extra>")
        x, y = _ultimo(s)
        items.append((x, y, f"{nombre} {y:.2f}", color))
    _etiquetas_finales(fig, t, items)
    fig = _base(fig, t, eje_y="dólares por acción de hoy", formato_y="$.2f")
    fig.update_xaxes(dtick=4)
    _rango_x(fig, min(a.index) - 0.5, max(x for x, *_ in items) + 0.5)
    return fig


def escala_contra_accion(e, t: Tema = OSCURO) -> go.Figure:
    """El negocio creció muchas veces; la acción, bastantes menos. Base 100."""
    a = e.anual
    m = e.medida
    base = next((y for y in a.index if pd.notna(a.get("acciones_diluidas", pd.Series()).get(y))
                 and pd.notna(a.get(m.concepto, pd.Series()).get(y))), None)
    fig = go.Figure()
    if base is None:
        return _base(fig, t)
    items = []
    for col, nombre, color in (("acciones_diluidas", "Acciones en circulación", t.contexto),
                               (m.concepto, f"{m.etiqueta} por acción", t.principal)):
        s = (a[col] / a.loc[base, col] * 100).dropna()
        s = s[s.index >= base]
        fig.add_scatter(x=s.index, y=s, name=nombre, mode="lines", line={"color": color, "width": 2},
                        hovertemplate=f"{nombre}: %{{y:,.0f}}<extra></extra>")
        x, y = _ultimo(s)
        items.append((x, y, f"{nombre.split()[0]} ×{y / 100:,.{0 if y >= 10_000 else 1}f}", color))
    _etiquetas_finales(fig, t, items, log=True)
    fig = _base(fig, t, eje_y=f"índice, {base} = 100 (escala log)", log_y=True)
    fig.update_yaxes(tickvals=[100, 200, 500, 1000, 2000, 5000, 10_000, 20_000],
                     ticktext=["100", "200", "500", "1,000", "2,000", "5,000", "10,000", "20,000"])
    fig.update_xaxes(dtick=4)
    _rango_x(fig, base - 0.5, max(x for x, *_ in items) + 0.5)
    return fig


def spread_de_inversion(e, t: Tema = OSCURO) -> go.Figure:
    si = e.spread_inversion
    fig = go.Figure()
    if si.empty:
        return _base(fig, t)
    series = (("cap_rate", "Yield de compra", t.principal, "solid"),
              ("costo_acciones", "Costo acciones", t.contexto, "solid"),
              ("costo_ponderado", "Costo ponderado", t.contexto, "dot"))
    items = []
    for col, nombre, color, trazo in series:
        if col not in si:
            continue
        # Todos los años del rango, con hueco donde no hay dato: una línea recta de
        # 2006 a 2013 dibujaría siete años que el emisor no reportó.
        s = si[col].reindex(range(int(si.index.min()), int(si.index.max()) + 1))
        fig.add_scatter(x=s.index, y=s, name=nombre, mode="lines+markers", connectgaps=False,
                        line={"color": color, "width": 2, "dash": trazo}, marker={"size": 6},
                        hovertemplate=f"{nombre}: %{{y:.2%}}<extra></extra>")
        x, y = _ultimo(s)
        items.append((x, y, nombre.split(" (")[0], color))
    _etiquetas_finales(fig, t, items, separacion=0.10)
    fig = _base(fig, t, eje_y="yield anual", formato_y=".1%")
    fig.update_layout(margin={"r": max(120, fig.layout.margin.r or 0)})
    # Años enteros: con dos o tres años el eje ponía «2,024.5».
    fig.update_xaxes(tickformat="d", dtick=1 if si.index.max() - si.index.min() <= 6 else None)
    _rango_x(fig, si.index.min() - 0.5, si.index.max() + 0.5)
    return fig


def apalancamiento(e, t: Tema = OSCURO) -> go.Figure:
    a = e.anual
    fig = go.Figure()
    if "deuda_sobre_activos" in a:
        s = a["deuda_sobre_activos"].dropna()
        fig.add_bar(x=s.index, y=s, name="Deuda / activos", marker_color=t.principal,
                    hovertemplate="Deuda / activos: %{y:.0%}<extra></extra>")
    return _base(fig, t, alto=280, eje_y="deuda ÷ activos (en libros)", formato_y=".0%")


# --------------------------------------------------------------------------------------
# Valuación
# --------------------------------------------------------------------------------------


def multiplo(e, t: Tema = OSCURO) -> go.Figure:
    s = e.tabla["p_ffo"].dropna()
    s = s.resample("W").last().dropna()
    mediana = float(e.tabla["p_ffo"].median())
    p20, p80 = e.tabla["p_ffo"].quantile(0.2), e.tabla["p_ffo"].quantile(0.8)
    fig = go.Figure()
    fig.add_hrect(y0=p20, y1=p80, fillcolor=t.contexto, opacity=0.10, line_width=0)
    fig.add_hline(y=mediana, line={"color": t.contexto, "width": 1, "dash": "dash"})
    m = e.medida.etiqueta
    fig.add_scatter(x=s.index, y=s, name=f"P/{m}", line={"color": t.principal, "width": 1.8},
                    hovertemplate=f"P/{m}: %{{y:.1f}}x<extra></extra>")
    fig.add_annotation(x=s.index[0], y=mediana, text=f"mediana {mediana:.1f}x", showarrow=False,
                       yshift=10, xanchor="left", bgcolor=t.mascara,
                       font={"color": t.texto_2, "size": 10, "family": t.mono})
    x, y = _ultimo(s)
    _etiquetas_finales(fig, t, [(x, y, f"hoy {y:.1f}x", t.principal)])
    fig = _base(fig, t, eje_y=f"precio ÷ {m} por acción conocido ese día")
    _rango_x(fig, s.index[0], s.index[-1])
    return fig


def yield_contra_bono(e, t: Tema = OSCURO) -> go.Figure:
    s = e.tabla[["yield_ttm", "ust10"]].resample("W").last().dropna(how="all")
    fig = go.Figure()
    fig.add_scatter(x=s.index, y=s["ust10"], name="Treasury 10 años", line={"color": t.contexto, "width": 1.6},
                    hovertemplate="Treasury: %{y:.2%}<extra></extra>")
    fig.add_scatter(x=s.index, y=s["yield_ttm"], name=f"Yield de {e.ticker}", line={"color": t.principal, "width": 1.8},
                    hovertemplate=f"Yield {e.ticker}: %{{y:.2%}}<extra></extra>")
    items = []
    for col, nombre, color in (("yield_ttm", f"Yield {e.ticker}", t.principal), ("ust10", "Treasury", t.contexto)):
        x, y = _ultimo(s[col])
        items.append((x, y, f"{nombre} {y:.1%}", color))
    _etiquetas_finales(fig, t, items)
    fig = _base(fig, t, eje_y="rendimiento anual", formato_y=".0%")
    _rango_x(fig, s.index[0], s.index[-1])
    return fig


def spread(e, t: Tema = OSCURO) -> go.Figure:
    s = e.tabla["spread"].resample("W").last().dropna()
    mediana = float(e.tabla["spread"].median())
    fig = go.Figure()
    fig.add_hline(y=mediana, line={"color": t.contexto, "width": 1, "dash": "dash"})
    fig.add_hline(y=0, line={"color": t.texto_2, "width": 1})
    fig.add_scatter(x=s.index, y=s, name="Spread", line={"color": t.principal, "width": 1.6},
                    fill="tozeroy", fillcolor="rgba(245,166,35,0.10)" if t.nombre == "oscuro" else "rgba(184,116,20,0.10)",
                    hovertemplate="Spread: %{y:.2%}<extra></extra>")
    fig.add_annotation(x=s.index[0], y=mediana, text=f"mediana {mediana:.1%}", showarrow=False,
                       yshift=10, xanchor="left", bgcolor=t.mascara,
                       font={"color": t.texto_2, "size": 10, "family": t.mono})
    x, y = _ultimo(s)
    _etiquetas_finales(fig, t, [(x, y, f"hoy {y:.1%}", t.principal)])
    fig = _base(fig, t, alto=280, eje_y=f"yield de {e.ticker} − Treasury", formato_y=".1%")
    _rango_x(fig, s.index[0], s.index[-1])
    return fig


# --------------------------------------------------------------------------------------
# Momentos de entrada
# --------------------------------------------------------------------------------------


def entradas(e, t: Tema = OSCURO) -> go.Figure:
    en = e.entradas.tabla.dropna(subset=["p_ffo", "rt_5a"])
    fig = go.Figure()
    fig.add_hline(y=0, line={"color": t.texto_2, "width": 1})
    fig.add_scatter(
        x=en["p_ffo"], y=en["rt_5a"], mode="markers", name="Cada fin de mes",
        marker={"size": 7, "color": t.principal, "opacity": 0.55, "line": {"color": t.fondo, "width": 1}},
        customdata=np.array([mes(d) for d in en.index]),
        hovertemplate="%{customdata}<br>P/" + e.medida.etiqueta + " %{x:.1f}x → %{y:.1%} anual a 5 años<extra></extra>",
    )
    q = e.entradas.quintiles
    if not q.empty:
        centro = (q["desde"] + q["hasta"]) / 2
        fig.add_scatter(x=centro, y=q["rt_5a_mediana"], mode="lines+markers", name="Mediana por quintil",
                        line={"color": t.texto, "width": 1.5, "dash": "dot"},
                        marker={"size": 10, "symbol": "diamond", "color": t.texto},
                        hovertemplate="Mediana del quintil: %{y:.1%}<extra></extra>")
    # Los dos mejores y los dos peores, con la flecha hacia lados opuestos: en NNN los dos
    # mejores meses (dic-1999 y feb-2009) caen casi en el mismo punto, y con la misma
    # flecha sus etiquetas se leían «dic-1feb-2009».
    for grupo, (arriba, abajo) in ((e.entradas.mejores, (-22, 26)), (e.entradas.peores, (-20, 24))):
        for (_, fila), (ax, ay) in zip(grupo.head(2).iterrows(), ((30, arriba), (-34, abajo)), strict=False):
            if pd.notna(fila["p_ffo"]):
                fig.add_annotation(x=fila["p_ffo"], y=fila["rt_5a"], text=mes(fila.name),
                                   showarrow=True, arrowhead=0, arrowcolor=t.texto_2, ax=ax, ay=ay,
                                   font={"size": 10, "color": t.texto_2, "family": t.mono})
    fig = _base(fig, t, alto=420, eje_y="retorno anual en los 5 años siguientes", formato_y=".0%", leyenda=True)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(title_text=f"P/{e.medida.etiqueta} el día de la compra", ticksuffix="x")
    return fig


def retorno_a_hoy(e, t: Tema = OSCURO) -> go.Figure:
    en = e.entradas.tabla
    s = en["rt_a_hoy_usd"].dropna()
    s = s[en.loc[s.index, "anios_a_hoy"] >= 3]
    fig = go.Figure()
    fig.add_hline(y=0, line={"color": t.texto_2, "width": 1})
    fig.add_scatter(x=s.index, y=s, name="En dólares", line={"color": t.principal, "width": 1.8},
                    hovertemplate="Comprando ese mes: %{y:.1%} anual hasta hoy<extra></extra>")
    m = en["rt_a_hoy_mxn"].dropna()
    m = m[en.loc[m.index, "anios_a_hoy"] >= 3]
    fig.add_scatter(x=m.index, y=m, name="En pesos", line={"color": t.contexto, "width": 1.4},
                    hovertemplate="En pesos: %{y:.1%}<extra></extra>")
    items = []
    for serie, nombre, color in ((s, "Dólares", t.principal), (m, "Pesos", t.contexto)):
        x, y = _ultimo(serie)
        items.append((x, y, nombre, color))
    _etiquetas_finales(fig, t, items, separacion=0.12)
    fig = _base(fig, t, eje_y="retorno anual desde la compra hasta hoy", formato_y=".0%")
    _rango_x(fig, min(s.index[0], m.index[0]), max(s.index[-1], m.index[-1]))
    return fig


def escenarios(e, t: Tema = OSCURO) -> go.Figure:
    h = e.hoy
    base = next((s for s in h.escenarios if s.nombre.startswith("AFFO por acción, 10")), None) \
        or (h.escenarios[0] if h.escenarios else None)
    fig = go.Figure()
    if base is None:
        return _base(fig, t)
    nombres = ["Si el spread vuelve<br>a su mediana", "Múltiplo constante",
               f"Si el P/{e.medida.etiqueta} vuelve<br>a su mediana"]
    valores = [base.real_neto_reversion_spread, base.real_neto, base.real_neto_reversion_multiplo]
    colores = [t.contexto, t.principal, t.contexto]
    fig.add_bar(x=nombres, y=valores, marker_color=colores, text=[f"{v:.1%}" for v in valores],
                textposition="outside", textfont={"family": t.mono, "color": t.texto},
                hovertemplate="%{y:.2%} real, neto de impuestos<extra></extra>", width=0.55)
    if h.udibono_real is not None:
        fig.add_hline(y=h.udibono_real, line={"color": t.texto, "width": 1.4, "dash": "dash"},
                      annotation_text=f"Udibono 10a: {h.udibono_real:.2%} real garantizado",
                      annotation_position="top left",
                      annotation_font={"color": t.texto, "size": 11, "family": t.mono})
    fig = _base(fig, t, alto=340, eje_y="retorno real anual, neto de impuestos", formato_y=".0%")
    fig.update_layout(hovermode="closest")
    return fig


FIGURAS = {
    "retorno_total": retorno_total, "eras": eras, "por_accion": por_accion,
    "escala": escala_contra_accion, "spread_inversion": spread_de_inversion,
    "apalancamiento": apalancamiento, "multiplo": multiplo, "yield_bono": yield_contra_bono,
    "spread": spread, "entradas": entradas, "retorno_a_hoy": retorno_a_hoy, "escenarios": escenarios,
}
