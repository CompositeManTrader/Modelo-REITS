"""El compilado: todo el análisis, explicado por las preguntas que se fueron haciendo.

Seis PDFs y un Excel en ``docs/compilado/``. Cada PDF agrupa preguntas del mismo tema, las
cita tal como se hicieron, da la respuesta corta y luego el porqué con sus cifras; al final
dice qué documento detallado lo amplía. El Excel junta las cifras y trae una calculadora del
plan de aportación con fórmulas vivas.

Las cifras salen de los resultados guardados (investigación, ETFs, satélite), de los datos
versionados (descomposición del retorno de O y NNN) y de la bitácora. Lo que solo existe como
cifra ya reportada en un informe —los estudios de O, NNN y WPC, el retorno esperado por tramo,
el catálogo de edges— va en constantes con su fuente al lado.

    python scripts/compilado.py            # los seis PDFs y el Excel
"""

from __future__ import annotations

import datetime as dt
import html
from pathlib import Path

import numpy as np
import pandas as pd

from src.estudio import graficas as g
from src.export.pdf_estudio import GLIFO, _css, _e, _lanzar_chromium, css_de_fuentes, tabla

RAIZ = Path(__file__).resolve().parents[2]
DIR_COMPILADO = RAIZ / "docs" / "compilado"
T = g.CLARO
MARCA = "SPREAD TRADING CLUB"

# --------------------------------------------------------------------------------------
# Cifras ya reportadas (con su fuente)
# --------------------------------------------------------------------------------------

# O, NNN y WPC juntos, retorno anual de los 5 años siguientes según el tramo del percentil del
# consenso, neto con broker de EE. UU. al 35% (metodos.retorno_esperado; página Valuación en el
# tiempo). La mediana del tramo medio va de 9.7% a 10.0% según el emisor.
RETORNO_ESPERADO = [
    ("Muy caro", "menos de 10%", 0.052, -0.004, 0.147),
    ("Caro", "10% a 30%", 0.063, -0.024, 0.126),
    ("Medio", "30% a 70%", 0.097, 0.022, 0.162),
    ("Barato", "70% a 90%", 0.160, 0.056, 0.236),
    ("Muy barato", "90% o más", 0.197, 0.125, 0.235),
]
EFECTIVO_5A = 0.014

# El catálogo de edges (docs/estudios/edges/): veredicto del adversario y puntaje del priorizador.
EDGES = [
    ("f6", "UCITS irlandés de acumulación en vez de SCHH", "−20 a +55", "Catálogo (1º)", 3.95),
    ("f3", "Rebote después de un recorte de dividendo", "−20 a +55", "Catálogo (2º), en escrutinio", 2.75),
    ("f4", "Eficiencia operativa dentro del sector", "−40 a +90", "Catálogo (3º), en escrutinio", 2.55),
    ("f3", "Momentum residual sin reversión", "−10 a +50", "Sobrevivió; cortada", 2.40),
    ("f4", "Descuento contra NAV dentro del sector", "−60 a +80", "Sobrevivió; cortada", 2.35),
    ("f1", "Comprar antes del cambio de mes (ciclo de liquidación)", "−1 a +5", "Muerta", None),
    ("f1", "Comprar antes de los días de pago de dividendos", "−1 a +3", "Muerta", None),
    ("f2", "Excluir REITs tipo lotería (volatilidad idiosincrática)", "−15 a +30", "Muerta", None),
    ("f2", "Excluir los de beta alta", "−40 a +40", "Muerta", None),
    ("f3", "Cercanía al máximo de 52 semanas", "−15 a +40", "Muerta", None),
    ("f4", "Rotar al tipo de propiedad más barato", "−80 a +100", "Muerta", None),
    ("f5", "Compras oportunistas de insiders", "−40 a +60", "Muerta", None),
    ("f5", "Recompra neta como señal de descuento", "−60 a +75", "Muerta", None),
    ("f6", "Comprar SCHH después de la fecha ex", "0 a +6", "Muerta", None),
]
FAMILIAS = {"f1": "Calendario", "f2": "Volatilidad", "f3": "Momentum", "f4": "Valor relativo",
            "f5": "Eventos", "f6": "Fiscal y canal"}

# Perfiles fiscales del modelo (src/investigacion/diseno.py) y la corrección que propone la
# búsqueda de edges (LISR Art. 142 fr. V: el dividendo extranjero se acumula sin importar el canal).
PERFILES = [
    ("SIC (casa de bolsa mexicana), como lo modela el repo", "20%", "20%", "10%", "0.25%"),
    ("Broker de EE. UU., tasa marginal 30%", "39%", "30%", "10%", "0%"),
    ("Broker de EE. UU., tasa marginal 35%", "44%", "35%", "10%", "0%"),
    ("SIC según el Art. 142 fr. V (por confirmar con contador)", "~44%", "—", "10%", "0.25%"),
]

PREGUNTAS_CONTADOR = [
    "¿El dividendo de un ETF o acción extranjera comprado por el SIC también se acumula a mi tasa "
    "marginal más 10% (Art. 142 fr. V LISR), o paga 20% en total?",
    "¿SCHH está listado en el SIC? Si no, ¿qué tasa pagaría su ganancia si lo vendo por mi broker?",
    "Un ETF UCITS irlandés de acumulación comprado por una persona física, ¿cae en el régimen de "
    "regímenes fiscales preferentes (Arts. 176 a 178 LISR)? ¿Tengo que presentar declaración informativa?",
    "¿La ganancia de IUSIN (iShares US Property Yield, en el SIC) paga 10% al venderse (Art. 129)?",
    "¿Cómo se tratan estas posiciones en una herencia? (impuesto sucesorio de EE. UU. arriba de 60 mil dólares)",
]

# --------------------------------------------------------------------------------------
# Datos guardados
# --------------------------------------------------------------------------------------


def _resultados() -> dict:
    from src.investigacion import resultados

    return resultados.cargar()


def _etfs():
    from src.estudio import etfs

    return etfs.cargar()


def _satelite() -> pd.DataFrame:
    ruta = RAIZ / "data" / "estudios" / "satelite" / "exploratoria" / "exploratoria.csv"
    return pd.read_csv(ruta) if ruta.exists() else pd.DataFrame()


def descomposicion(ticker: str) -> dict:
    """De dónde salió el retorno: dividendo, crecimiento del dividendo y revaluación (datos versionados).

    ``(1 + RT) = (1 + ingreso)(1 + crecimiento)(1 + revaluación)``, con la revaluación como el
    cambio del yield (precio contra dividendo de 12 meses) y el ingreso como el resto.
    """
    d = RAIZ / "data" / "estudios" / ticker
    p = pd.read_csv(d / "precios.csv.gz", parse_dates=["fecha"]).set_index("fecha").sort_index()
    v = pd.read_csv(d / "dividendos.csv.gz", parse_dates=["fecha_ex"]).sort_values("fecha_ex")
    a = p.index[p.index >= p.index[0] + pd.DateOffset(years=1)][0]
    b = p.index[-1]
    n = (b - a).days / 365.25

    def ttm(f):
        return v[(v["fecha_ex"] > f - pd.DateOffset(years=1)) & (v["fecha_ex"] <= f)]["monto_base"].sum()

    ya, yb = ttm(a) / p.loc[a, "cierre_base"], ttm(b) / p.loc[b, "cierre_base"]
    rt = (p.loc[b, "ajustado_proveedor"] / p.loc[a, "ajustado_proveedor"]) ** (1 / n) - 1
    crec = (ttm(b) / ttm(a)) ** (1 / n) - 1
    rev = (ya / yb) ** (1 / n) - 1
    ingreso = (1 + rt) / ((1 + crec) * (1 + rev)) - 1
    return {"ticker": ticker, "desde": a, "hasta": b, "retorno": rt, "dividendo": ingreso, "crecimiento": crec,
            "revaluacion": rev, "yield_inicio": ya, "yield_hoy": yb}


def intentos() -> dict:
    """Lo que dice la bitácora de la investigación."""
    from src.investigacion import bitacora

    b = bitacora.leer()
    b = b[b["familia"] != "apertura"]
    return {"registros": int(len(b)), "intentos": bitacora.intentos(),
            "sin_sensibilidad": bitacora.intentos(excluir=("sensibilidad-fiscal",))}


# --------------------------------------------------------------------------------------
# Formato
# --------------------------------------------------------------------------------------


def p(v, d: int = 1) -> str:
    return "—" if v is None or pd.isna(v) else f"{float(v) * 100:.{d}f}%"


def pb(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    x = round(float(v) * 1e4)
    return f"{x:+,d}".replace("-", "−") if x else "0"


CSS_EXTRA = f"""
.pregunta {{ border-left: 3pt solid {T.principal}; background: #F1ECE2; padding: 7pt 11pt; margin: 10pt 0 8pt;
            break-inside: avoid; }}
.pregunta .q {{ font-family: 'Space Grotesk', Inter, sans-serif; font-size: 11.5pt; font-weight: 600; }}
.pregunta .q::before {{ content: '« '; color: {T.principal}; }}
.pregunta .q::after {{ content: ' »'; color: {T.principal}; }}
.pregunta .r {{ margin-top: 5pt; }}
.pregunta .r b.etq {{ font-family: 'JetBrains Mono', monospace; font-size: 7.5pt; letter-spacing: 0.14em;
                     text-transform: uppercase; color: {T.principal}; margin-right: 4pt; }}
ul {{ margin: 0 0 8pt; padding-left: 16pt; }}
li {{ margin: 0 0 3pt; }}
table.indice {{ break-inside: auto; font-size: 8.2pt; }}
table.indice tr {{ break-inside: avoid; }}
table.indice td {{ padding: 2.2pt 4pt; }}
.conclusion {{ margin: 0 0 7pt; }}
.conclusion p {{ margin: 1pt 0 0; }}
.num {{ font-family: 'JetBrains Mono', monospace; }}
"""


class Figs:
    """Las gráficas del documento, para plotly.js en Chromium (estáticas, tema claro del impreso)."""

    def __init__(self) -> None:
        self.specs: list[tuple[str, str]] = []

    def __call__(self, fig, *, pie: str = "", alto: int = 320) -> str:
        # El margen de la gráfica manda sobre el de base (p. ej. espacio para un rótulo a la derecha).
        margen = {"l": 10, "r": 20, "t": 30, "b": 40} | {k: v for k, v in fig.layout.margin.to_plotly_json().items()
                                                       if v is not None}
        fig.update_layout(width=700, height=alto, hovermode=False, paper_bgcolor=T.fondo, plot_bgcolor=T.fondo,
                          font={"family": T.texto_fuente, "size": 11, "color": T.texto},
                          margin=margen, showlegend=fig.layout.showlegend)
        fig.update_xaxes(gridcolor=T.rejilla, zerolinecolor=T.texto_2, linecolor=T.rejilla, automargin=True)
        fig.update_yaxes(gridcolor=T.rejilla, zerolinecolor=T.texto_2, linecolor=T.rejilla, automargin=True)
        ident = f"fig_{len(self.specs)}"
        self.specs.append((ident, fig.to_json()))
        pie_html = f"<div class='pie'>{_e(pie)}</div>" if pie else ""
        return f"<figure><div id='{ident}' class='grafica'></div>{pie_html}</figure>"

    def script(self) -> str:
        llamadas = "\n".join(f"pend.push(Plotly.newPlot('{i}', (f={s}).data, f.layout, "
                             "{staticPlot:true, displayModeBar:false}));" for i, s in self.specs)
        return ("<script>var f; var pend=[];\n" + llamadas
                + "\nPromise.all(pend).then(()=>{document.body.dataset.listo='1';});</script>")


def _portada(rotulo: str, titulo: str, bajada: str, kpis: list[tuple[str, str]], preguntas: list[str]) -> str:
    k = "".join(f"<div class='kpi'><div class='v'>{v}</div><div class='l'>{_e(leyenda)}</div></div>"
                for v, leyenda in kpis)
    q = "".join(f"<li>«{_e(x)}»</li>" for x in preguntas)
    lista = f"<p class='rotulo' style='margin-top:10pt'>Las preguntas que responde</p><ul>{q}</ul>" if q else ""
    return f"""
    <section class='portada'>
      <div class='marca'>SPREAD <span>TRADING CLUB</span></div>
      <div style='flex-grow:1;display:flex;flex-direction:column;justify-content:center'>
        <div class='rotulo'>{_e(rotulo)}</div>
        <h1>{_e(titulo)}</h1>
        <p style='font-size:12.5pt;max-width:160mm'>{bajada}</p>
        <div class='kpis'>{k}</div>
        {lista}
      </div>
      <div class='gris chico'>Compilado del análisis, generado el {dt.date.today():%d-%m-%Y}. Herramienta de
      análisis, no asesoría de inversión ni fiscal: las reglas fiscales se confirman con un contador.</div>
    </section>"""


def _pregunta(q: str, corta: str) -> str:
    return (f"<div class='pregunta'><div class='q'>{_e(q)}</div>"
            f"<div class='r'><b class='etq'>Respuesta corta</b>{corta}</div></div>")


def _conclusion(titulo: str, texto: str, tono: str = "neutral") -> str:
    glifo, color = GLIFO.get(tono, GLIFO["neutral"])
    return (f"<div class='conclusion' style='border-left-color:{color}'><b><span style='color:{color}'>{glifo}"
            f"</span> {_e(titulo)}</b><p>{texto}</p></div>")


def _anexos(filas: list[tuple[str, str]]) -> str:
    return ("<h2>Para profundizar</h2>"
            + tabla([[f"<span class='num'>{_e(r)}</span>", _e(q)] for r, q in filas], ["Documento", "Qué trae"],
                    alinear="ll"))


def _documento(titulo: str, cuerpo: str, figs: Figs) -> str:
    import plotly.offline

    css = _css(css_de_fuentes()) + CSS_EXTRA
    return ("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            f"<title>{_e(titulo)}</title><style>{css}</style>"
            f"<script>{plotly.offline.get_plotlyjs()}</script></head>"
            f"<body>{cuerpo}{figs.script()}</body></html>")


def a_pdf(documento: str, destino: Path, titulo: str) -> Path:
    from playwright.sync_api import sync_playwright

    destino.parent.mkdir(parents=True, exist_ok=True)
    pie = ("<div style='width:100%;font-family:monospace;font-size:7px;color:#6B6B66;"
           "padding:0 15mm;display:flex;justify-content:space-between'>"
           f"<span>{MARCA} · {html.escape(titulo)}</span>"
           "<span><span class='pageNumber'></span> / <span class='totalPages'></span></span></div>")
    with sync_playwright() as pw:
        navegador = _lanzar_chromium(pw)
        pagina = navegador.new_page()
        pagina.set_content(documento, wait_until="load")
        pagina.wait_for_selector("body[data-listo='1']", timeout=180_000)
        pagina.pdf(path=str(destino), print_background=True, prefer_css_page_size=True, display_header_footer=True,
                   header_template="<div></div>", footer_template=pie)
        navegador.close()
    return destino


# --------------------------------------------------------------------------------------
# Gráficas
# --------------------------------------------------------------------------------------


def _barras_h(etiquetas: list[str], valores: list[float], *, titulo: str, formato: str = "pb", alto: int = 360):
    """Barras horizontales con el signo en el color y la cifra escrita al lado (no solo color)."""
    import plotly.graph_objects as go

    colores = [T.ganancia if v > 0 else T.perdida for v in valores]
    texto = [pb(v) + " pb" if formato == "pb" else p(v) for v in valores]
    fig = go.Figure(go.Bar(x=valores, y=etiquetas, orientation="h", marker={"color": colores, "line": {"width": 0}},
                           text=texto, textposition="outside", cliponaxis=False,
                           textfont={"family": T.mono, "size": 10, "color": T.texto}))
    lo, hi = min(min(valores), 0.0), max(max(valores), 0.0)
    holgura = 0.22 * (hi - lo or 1.0)
    fig.update_layout(title={"text": titulo, "font": {"size": 12}, "x": 0}, showlegend=False, bargap=0.35)
    fig.update_xaxes(tickformat=".1%" if formato != "pb" else None, zeroline=True, zerolinewidth=1.5,
                     showticklabels=formato != "pb", range=[lo - (holgura if lo < 0 else 0), hi + holgura])
    fig.update_yaxes(autorange="reversed")
    return fig, alto


def g_retorno_esperado():
    import plotly.graph_objects as go

    nombres = [r[0] for r in RETORNO_ESPERADO]
    med = [r[2] for r in RETORNO_ESPERADO]
    fig = go.Figure(go.Bar(
        x=nombres, y=med, marker={"color": T.principal, "line": {"width": 0}}, width=0.55,
        error_y={"type": "data", "symmetric": False, "array": [r[4] - r[2] for r in RETORNO_ESPERADO],
                 "arrayminus": [r[2] - r[3] for r in RETORNO_ESPERADO], "color": T.texto_2, "thickness": 1.2, "width": 6},
        text=[p(v) for v in med], textposition="inside", insidetextanchor="end",
        textfont={"family": T.mono, "size": 10, "color": "#FFFFFF"}))
    fig.add_hline(y=EFECTIVO_5A, line={"color": T.texto_2, "dash": "dot", "width": 1.5},
                  annotation_text=f"efectivo<br>{p(EFECTIVO_5A)}", annotation_position="right",
                  annotation_font={"size": 10, "color": T.texto_2, "family": T.mono})
    fig.update_layout(margin={"r": 70})
    fig.update_layout(title={"text": "Retorno anual de los 5 años siguientes, según qué tan caro estaba (mediana y "
                                     "rango de 10% a 90%)", "font": {"size": 12}, "x": 0}, showlegend=False)
    fig.update_yaxes(tickformat=".0%")
    return fig


def g_descomposicion(partes: list[dict]):
    import plotly.graph_objects as go

    fig = go.Figure()
    for col, nombre, color in (("dividendo", "Dividendo (reinvertido)", T.principal),
                               ("crecimiento", "Crecimiento del dividendo", T.contexto),
                               ("revaluacion", "Revaluación (cambio del yield)", T.contexto_2)):
        fig.add_bar(y=[f"{d['ticker']} ({d['desde']:%Y}-{d['hasta']:%Y})" for d in partes], x=[d[col] for d in partes],
                    name=nombre, orientation="h", marker={"color": color, "line": {"color": T.fondo, "width": 2}},
                    text=[p(d[col]) for d in partes], textposition="inside",
                    textfont={"family": T.mono, "size": 10, "color": "#FFFFFF"})
    fig.update_layout(barmode="stack", title={"text": "De dónde salió el rendimiento anual", "font": {"size": 12}, "x": 0},
                      legend={"orientation": "h", "y": -0.25, "x": 0, "traceorder": "normal"}, showlegend=True)
    fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(autorange="reversed")
    return fig


def g_embudo():
    import plotly.graph_objects as go

    etapas = ["Ideas consideradas", "Cards escritas", "Sobrevivieron al adversario", "Catálogo final"]
    valores = [285, 14, 5, 3]
    fig = go.Figure(go.Bar(x=valores, y=etapas, orientation="h", text=[str(v) for v in valores], textposition="outside",
                           marker={"color": [T.contexto_2, T.contexto, T.contexto, T.principal], "line": {"width": 0}},
                           cliponaxis=False, textfont={"family": T.mono, "size": 11, "color": T.texto}))
    fig.update_layout(title={"text": "La búsqueda de estrategias contra SCHH", "font": {"size": 12}, "x": 0},
                      showlegend=False, bargap=0.35)
    fig.update_xaxes(type="log", showticklabels=False, showgrid=False)
    fig.update_yaxes(autorange="reversed")
    return fig


def g_etfs_anios(anios: pd.DataFrame):
    import plotly.graph_objects as go

    a = anios[anios["meses"] == 12]
    fig = go.Figure()
    estilos = {"Índice": (T.texto, 2.2, "solid"), "SCHH": (T.principal, 2.6, "solid"),
               "USRT": (T.contexto, 1.4, "dot"), "VNQ": (T.contexto_2, 1.4, "dash")}
    for col, (color, ancho, guion) in estilos.items():
        if col in a:
            fig.add_scatter(x=a["anio"].astype(str), y=a[col], name=col, mode="lines+markers",
                            line={"color": color, "width": ancho, "dash": guion}, marker={"size": 6})
    fig.update_layout(title={"text": "Retorno total de cada año: el índice de la investigación y los tres ETFs",
                             "font": {"size": 12}, "x": 0}, legend={"orientation": "h", "y": -0.2, "x": 0},
                      showlegend=True)
    fig.update_yaxes(tickformat=".0%")
    return fig


# --------------------------------------------------------------------------------------
# 00. Mapa del análisis
# --------------------------------------------------------------------------------------

PREGUNTAS = [
    # (tema, pregunta tal como se hizo, respuesta corta, documento)
    ("Valuación", "¿Por qué no hiciste modelos de DCF, DDM, NAV para valuar las REITs y con base en esos modelos "
     "tomar decisiones?", "Se agregaron y se probaron. Ninguno supera a los métodos simples, y ninguno le gana a "
     "aportar siempre cuando se usa para decidir cuándo comprar.", "01"),
    ("Valuación", "¿Cómo es que ningún método de valoración le gana a la compra simple? ¿De qué sirven entonces?",
     "Sirven para saber cuánto esperar ganar y para escoger entre REITs de calidad; no para decidir cuándo comprar, "
     "porque esperar en efectivo cuesta más de lo que se gana comprando más barato.", "01"),
    ("Valuación", "¿Contra quién compararíamos estos modelos para saber si son buenos?",
     "Contra aportar lo mismo al mismo papel cada mes, sin reglas, con los mismos impuestos.", "01"),
    ("Cuándo entrar", "Debe existir un modelo óptimo que nos diga de forma eficiente cuándo entrar en el mercado: "
     "arma un plan de investigación completo.", "Se hizo, con 54 años de datos y 8 mercados más. No se encontró: "
     "ninguna regla ni modelo le ganó a aportar siempre.", "02"),
    ("Cuándo entrar", "Esa conclusión hace inválida la valuación de las REITs, ya que no importa realmente.",
     "No la invalida: la valuación sí predice cuánto vas a ganar (barato ~20% al año, caro ~8%); lo que no hace es "
     "decirte cuándo esperar.", "02"),
    ("Cuándo entrar", "Hay personas que dedican su vida a la valuación... siento que es como tirar una moneda al "
     "aire para saber cuál acción se va a desempeñar mejor.", "Escoger UNA es como una moneda; tener muchas la "
     "elimina. Y en los extremos la valuación sí dice algo, aunque no cuándo salir.", "02"),
    ("En cuáles", "¿La estrategia que mejor funciona es simplemente comprar cada mes en el REIT que yo quiera y ya?",
     "Cada mes sí; «el que yo quiera» no: ninguna regla le ganó a tener a todos, y uno solo trae mucho más riesgo.",
     "03"),
    ("En cuáles", "¿Cómo haríamos una estrategia de over y unders contra SCHH para ganarle de forma consistente?",
     "Con un núcleo de SCHH y un satélite. En la historia ningún satélite le ganó; la prueba limpia corre en papel "
     "desde noviembre de 2026.", "03"),
    ("En cuáles", "Quiero que busques alguna estrategia que le gane.",
     "Se buscó en seis familias: 14 ideas, 9 muertas, 3 en el catálogo. Ninguna de selección llega con margen a +50 pb; "
     "lo único fuerte es fiscal.", "03"),
    ("Impuestos", "Yo no voy a operar por el SIC; voy directo con broker estadounidense.",
     "Con broker el dividendo paga 39% a 44% y aportar rinde menos, pero ningún veredicto cambia. Además, el 20% "
     "que el modelo le daba al SIC probablemente está mal.", "04"),
    ("Qué comprar", "¿No existe algún ETF que tenga a todos los REITs juntos y me dé la distribución mensual?",
     "Sí existen ETFs amplios (SCHH, USRT, VNQ), pero pagan cada trimestre. Los que pagan cada mes escogen por yield "
     "alto, que es la trampa.", "05"),
    ("Qué comprar", "¿Cuánto debería comprar de SCHH cada mes?",
     "Primero el fondo de emergencia. Después, unos 800 de cada 4,000 pesos de ahorro (~20%) a SCHH y el resto a "
     "acciones amplias.", "05"),
    ("Qué comprar", "¿La valuación solo sirve para value investing? Si el objetivo es ganar de las distribuciones, "
     "¿no nos interesa?", "Al revés: el precio al que compras decide cuánta renta te da cada peso. Lo que no "
     "funcionó fue escoger «lo barato» para ganarle al mercado.", "05"),
    ("Qué comprar", "¿No hay una incongruencia: desconfiar de una renta demasiado alta, pero la valuación dice que "
     "comprando más barato la renta porcentual es más alta?", "No: la misma renta alta puede venir de un precio "
     "que bajó con la renta segura (bueno) o de una renta a punto de caerse (trampa). Se distinguen comparando contra "
     "su propia historia y exigiendo calidad.", "05"),
]

DOCUMENTOS = [
    ("00", "Mapa del análisis", "00_mapa_del_analisis.pdf", "Este documento: todas las preguntas, las conclusiones y qué hacer."),
    ("01", "La plataforma y la valuación", "01_plataforma_y_valuacion.pdf",
     "Qué construimos, los métodos de valuación (DCF, DDM, NAV y simples), los estudios de O, NNN y WPC y el retorno "
     "esperado por tramo."),
    ("02", "¿Cuándo entrar?", "02_cuando_entrar.pdf",
     "La investigación pre-registrada de timing: fases, resultados, extremos y qué tan finas eran las pruebas."),
    ("03", "¿En cuáles REITs?", "03_en_cuales_reits.pdf",
     "Selección entre REITs, el núcleo y satélite contra SCHH y la búsqueda de estrategias que le ganen."),
    ("04", "Impuestos y canal", "04_impuestos_y_canal.pdf",
     "Broker contra SIC, lo que cambia con la ley, el ETF irlandés y las preguntas para el contador."),
    ("05", "Qué comprar y cuánto", "05_que_comprar_y_cuanto.pdf",
     "Los ETFs, cuánto aportar, la valuación y las distribuciones, y el calendario de cada trimestre."),
    ("XL", "Cifras y calculadora", "compilado_cifras.xlsx",
     "Las preguntas, las cifras de cada análisis y una calculadora de tu plan con fórmulas vivas."),
]


def html_mapa(res: dict) -> str:
    figs = Figs()
    n = intentos()
    kpis = [("54 años", "de datos del sector (FTSE Nareit, 1972-2026) y 8 mercados más"),
            (f"{n['intentos']}", "configuraciones registradas en la bitácora (la mayoría, impuestos y timing)"),
            ("266", "emisores de EE. UU. en el panel de selección, vivos y muertos"),
            ("0", "reglas que le ganaron de forma robusta a aportar siempre")]
    cuerpo = _portada("Compilado · guía", "Mapa del análisis",
                      "Qué preguntamos, qué encontramos y qué hacer. Este documento es la puerta de entrada: cada "
                      "pregunta lleva su respuesta corta y el número del documento que la explica completa.",
                      kpis, [])
    cuerpo += "<h2>Cómo leer el compilado</h2>"
    cuerpo += tabla([[f"<b>{d}</b>", _e(t), f"<span class='num'>{_e(a)}</span>", _e(q)] for d, t, a, q in DOCUMENTOS],
                    ["#", "Documento", "Archivo", "Qué responde"], alinear="llll")
    cuerpo += ("<p class='gris chico'>Los documentos detallados que ya existían (estudios por emisor, métodos de "
               "valuación, reglas de decisión, universo de REITs, investigación completa, ETFs, núcleo y satélite y "
               "catálogo de edges) siguen en <span class='num'>docs/</span>; cada documento del compilado dice cuáles "
               "amplían su tema.</p>")
    cuerpo += "<h2>El camino, en orden</h2>" + tabla([
        ["Septiembre 2026", "La plataforma", "Estados financieros de 10 REITs desde la SEC, valuación por FFO/AFFO, "
         "semáforo de tres puertas, portafolio, ISR, calendario y la app con sus páginas."],
        ["Septiembre-octubre", "Estudios de largo plazo", "O, NNN y WPC desde su salida a bolsa: de dónde salió el "
         "rendimiento, el semáforo puesto a prueba y 7 métodos de valuación en el tiempo (con DCF, DDM y NAV)."],
        ["Octubre", "La prueba del universo", "¿La valuación sabe escoger entre todos los REITs que cotizan? No: lo "
         "barato concentra recortes."],
        ["Octubre", "La investigación pre-registrada", "Fases 0 a 8: cuándo entrar (54 años, 8 mercados) y en cuáles "
         "(todos los REITs de EE. UU. desde 2011, vivos y muertos)."],
        ["Octubre", "Broker de EE. UU.", "Todo otra vez con los impuestos de un broker de EE. UU.: ningún veredicto "
         "cambia."],
        ["Octubre", "Extremos, poder y retorno esperado", "¿La valuación sirve en sus extremos? ¿Las pruebas podían ver "
         "una ventaja? El retorno esperado por tramo llega a la app."],
        ["Octubre", "Qué comprar", "Los ETFs contra el índice (SCHH, USRT, VNQ), cuánto aportar, valuación y "
         "distribuciones."],
        ["Octubre", "Ganarle a SCHH", "Núcleo y satélite (exploratoria y prueba en papel) y la búsqueda de edges en "
         "seis familias."],
    ], ["Cuándo", "Qué", "Para qué"], alinear="lll")
    cuerpo += "<h2 class='salto'>Todas las preguntas, con su respuesta corta</h2>"
    cuerpo += tabla([[_e(t), f"«{_e(q)}»", _e(r), f"<b>{d}</b>"] for t, q, r, d in PREGUNTAS],
                    ["Tema", "La pregunta", "Respuesta corta", "Doc."], alinear="llll", clase="indice")
    cuerpo += "<h2 class='salto'>Las diez conclusiones</h2>"
    cuerpo += "".join(_conclusion(t, x, tono) for t, x, tono in CONCLUSIONES)
    cuerpo += "<h2 class='salto'>Qué hacer</h2>" + QUE_HACER
    cuerpo += "<h2>Glosario</h2>" + tabla([[f"<b>{_e(a)}</b>", _e(b)] for a, b in GLOSARIO], ["Término", "Qué es"],
                                          alinear="ll")
    return _documento("Mapa del análisis", cuerpo, figs)


CONCLUSIONES = [
    ("No hay regla para saber cuándo entrar", "Ninguna de 22 reglas ni 5 modelos le ganó a aportar siempre en 54 años, y "
     "la mejor protección contra caídas (salir bajo la tendencia de 10 meses) costó 127 pb al año en 8 mercados.",
     "desfavorable"),
    ("Esperar no paga", "El efectivo le ganó a los REITs solo en 27% de los periodos de 12 meses y en 16% de los de 5 años "
     "(1972-2015). Mientras esperas, dejas de cobrar.", "desfavorable"),
    ("Tampoco hay regla para escoger en cuáles", "Ninguna de 16 reglas de selección le ganó a repartir entre todos "
     "por +50 pb. Momentum fue lo más cercano: +38 pb en la prueba final.", "desfavorable"),
    ("Lo barato es trampa si no hay calidad", "El yield alto recortó el dividendo el doble de veces (21% contra 10%) y "
     "perdió 86 pb al año. «Barato entre los de calidad» fue la peor regla: −211 pb.", "desfavorable"),
    ("La valuación sí dice cuánto esperar ganar", "En O, NNN y WPC, desde «barato» se rindió ~20% al año a 5 años y desde "
     "«caro» ~8%. En su 10% más barato, 19.4%; en su 10% más caro, 4.7%.", "favorable"),
    ("La valuación sí ayuda a repartir entre REITs de calidad", "Mandar la aportación del mes al más barato contra su "
     "propia historia ganó +72 pb al año entre O, NNN y WPC, más que cada una de 500 elecciones al azar. Inconcluso por "
     "sesgo de supervivencia.", "favorable"),
    ("Con broker de EE. UU. nada cambia", "El dividendo paga 39% a 44% y aportar rinde 145 a 184 pb menos que el SIC "
     "modelado, pero ningún veredicto se mueve. Esa ventaja del SIC probablemente es un error del modelo.", "neutral"),
    ("Un ETF amplio resuelve la diversificación", "SCHH se desvía solo 0.43% al año del índice de la investigación desde "
     "2020 y cuesta 0.07%. Paga cada trimestre; ninguno quita las caídas (el sector cayó 68% en 2007-2009).", "favorable"),
    ("No encontramos cómo ganarle a SCHH escogiendo REITs", "Ningún satélite le ganó en la historia, y de 14 ideas nuevas "
     "ninguna de selección llega con margen a +50 pb. Lo único con mecanismo sólido es fiscal (ETF irlandés de "
     "acumulación), sujeto a confirmar con un contador.", "neutral"),
    ("Qué tan sólido es", "Todo se pre-registró en un commit antes de correrlo, con datos separados antes de verlos y la "
     "cuenta de cada intento. Límites: pocas crisis en la muestra, sesgo de supervivencia en los estudios de tres "
     "emisores y supuestos fiscales por confirmar.", "neutral"),
]

QUE_HACER = """
<ol>
<li><b>Arma primero tu fondo de emergencia</b> (3 meses de gastos, en CETES). Sin él, la primera emergencia te obliga a
vender, casi siempre cuando el mercado está abajo.</li>
<li><b>Después, aporta cada mes sin esperar el momento</b>, todo el monto, el mismo día (el de tu pago).</li>
<li><b>Reparte:</b> alrededor de 80% en acciones amplias y 20% en un ETF amplio de REITs (SCHH). Entre 10% y 25% de
REITs es defendible; el porcentaje es criterio, no resultado de la investigación.</li>
<li><b>Reinvierte las distribuciones</b> y revisa una vez al año: si SCHH pasa de 25% o baja de 15% de tu total, manda
las aportaciones nuevas al que quedó abajo, sin vender.</li>
<li><b>Nunca vendas por valuación ni por un recorte</b>: en la historia, salirse costó más de lo que protegió.</li>
<li><b>Lleva al contador las cinco preguntas</b> del documento 04. Es lo de mayor valor de todo el análisis: puede
cambiar en qué vehículo conviene aportar.</li>
<li><b>Sigue la prueba en papel</b> cada trimestre (documento 05): es la única manera limpia de saber si una regla le
gana a SCHH.</li>
</ol>"""

GLOSARIO = [
    ("REIT", "Empresa dueña de inmuebles que renta y que debe repartir la mayor parte de su utilidad como dividendo."),
    ("ETF", "Fondo que cotiza en bolsa; un ETF de REITs trae decenas o cientos de REITs en una sola compra."),
    ("SCHH, USRT, VNQ", "ETFs amplios de REITs de EE. UU. de Schwab, iShares y Vanguard."),
    ("FFO / AFFO", "Flujo de operación de un REIT (utilidad sin depreciación de inmuebles); el AFFO resta el "
     "mantenimiento. Es lo que se usa para valuarlos."),
    ("Percentil contra su propia historia", "Qué tan barato está hoy comparado con todo su pasado: 90% = más barato "
     "que 9 de cada 10 días de su historia."),
    ("Aportar siempre", "La referencia de todo el análisis: meter el mismo dinero cada mes, sin reglas, y nunca vender."),
    ("TIR neta", "El rendimiento anual de todas tus aportaciones, después de impuestos y comisiones."),
    ("Punto base (pb)", "Una centésima de punto porcentual: +50 pb al año es medio punto de rendimiento extra."),
    ("Pre-registro", "Escribir y guardar en un commit las hipótesis y los criterios ANTES de correr la prueba, para no "
     "acomodarlos al resultado."),
    ("Desarrollo / validación / sellado", "Datos para diseñar (1972-2015), para comprobar (2016 en adelante) y para la "
     "prueba final (mercados y emisores que nadie vio antes)."),
    ("Mínimo detectable", "La ventaja más chica que una prueba puede distinguir del azar con estos datos."),
    ("Núcleo y satélite", "Tener casi todo en el ETF (núcleo) y una parte chica (satélite) en REITs escogidos por una regla."),
    ("UCITS de acumulación", "ETF europeo (aquí, irlandés) que reinvierte los dividendos dentro del fondo en lugar de "
     "repartirlos."),
]


# --------------------------------------------------------------------------------------
# 01. La plataforma y la valuación
# --------------------------------------------------------------------------------------


def html_plataforma() -> str:
    figs = Figs()
    partes = [descomposicion("O"), descomposicion("NNN")]
    kpis = [("10", "REITs con estados financieros leídos de la SEC"),
            ("3", "estudios de largo plazo: O, NNN y WPC desde su salida a bolsa"),
            ("7", "métodos de valuación más el consenso, probados en el tiempo"),
            ("+72 pb", "al año por repartir entre los tres según la valuación (inconcluso)")]
    preguntas = [q for t, q, _, d in PREGUNTAS if d == "01"]
    c = _portada("Compilado · 01", "La plataforma y la valuación",
                 "Qué construimos para valuar REITs, qué métodos usa, y qué dijeron los estudios de largo plazo de O, "
                 "NNN y WPC sobre para qué sirve —y para qué no— la valuación.", kpis, preguntas)
    c += "<h2>1. Qué construimos</h2>"
    c += ("<p>Una plataforma que lee los estados financieros de cada REIT directamente de la SEC, los concilia contra lo "
          "que el emisor publica y los convierte en una valuación por FFO/AFFO, con su historia point-in-time (lo que "
          "se sabía en cada fecha). La app tiene once páginas:</p>")
    c += tabla([[_e(a), _e(b)] for a, b in PAGINAS], ["Página", "Para qué sirve"], alinear="ll")
    c += "<h3>El semáforo: tres puertas</h3>"
    c += tabla([["1. Calidad", "Binaria: payout menor a 90% del AFFO, AFFO por acción creciendo, deuda neta/EBITDAre "
                 "bajo 6.5x, grado de inversión y spread positivo. Lo que falla no está barato: está descartado."],
                ["2. Valuación", "Percentil de la prima contra su propia historia. Alto = comprar, medio = mantener, bajo = "
                 "no comprar más. Nunca vende por sí sola."],
                ["3. Deterioro", "La única que vende: payout arriba de 100%, spread negativo o AFFO cayendo dos trimestres "
                 "seguidos, apalancamiento arriba de 6.5x o pérdida del grado de inversión."]],
               ["Puerta", "Qué revisa"], alinear="ll")
    c += "<h2 class='salto'>2. Los métodos de valuación</h2>"
    c += _pregunta(PREGUNTAS[0][1], "Se agregaron DDM, DCF, crecimiento implícito y NAV aproximado y se probaron igual "
                   "que los métodos simples. Ninguno los superó.")
    c += tabla([["DDM", "Gordon sobre el dividendo vigente con el crecimiento de 5 años (0% a 4%)",
                 "En absoluto casi siempre dice comprar; contra su historia predice menos que el yield solo"],
                ["DCF", "AFFO por acción 5 años a su crecimiento y 2% perpetuo", "No predice contra su historia"],
                ["Crecimiento implícito", "El crecimiento que justifica el precio contra el que entregó", "No predice"],
                ["NAV aproximado", "NOI × 4 ÷ cap rate de sus compras − deuda neta", "El que más correlación muestra, con "
                 "solo dos ventanas de 5 años: no alcanza para concluir"],
                ["Simples (yield, P/FFO, primas)", "Contra su propia historia", "Los siete predicen el retorno de 5 años"],
                ["Consenso de los siete", "El percentil promedio", "La regla recomendada para repartir entre emisores"]],
               ["Método", "Cómo", "Qué salió"], alinear="lll")
    c += _pregunta(PREGUNTAS[1][1], "Le «ganan» en lo que importa: predicen cuánto vas a ganar. Lo que no logran es "
                   "superar a aportar siempre cuando se usan para decidir cuándo comprar.")
    c += ("<p>La razón es aritmética, no de los modelos: cuando un método dice «caro» y esperas en efectivo, ese dinero "
          "deja de cobrar renta y de crecer. Aun desde «caro», el REIT le ganó al T-bill la mayoría de las veces. Comprar "
          "menos cuando está caro quedó cerca de cero o abajo contra aportar siempre, con cualquier método. Por eso el "
          "semáforo completo, contra aportar siempre, dio −560 pb al año en NNN, −58 en O y +1 en WPC.</p>")
    c += _pregunta(PREGUNTAS[2][1], "Contra aportar lo mismo al mismo papel cada mes, sin reglas, con los mismos "
                   "impuestos y comisiones. Una regla vale si le gana a eso.")
    c += "<h2 class='salto'>3. Para qué sí sirve la valuación</h2>"
    c += ("<p><b>Para saber cuánto esperar ganar.</b> Con O, NNN y WPC juntos, el retorno de los 5 años siguientes "
          "dependió mucho de qué tan caro estaba el papel al comprar (neto con broker al 35%):</p>")
    c += figs(g_retorno_esperado(), pie="Fuente: estudios de O, NNN y WPC (metodos.retorno_esperado), neto con broker "
              "de EE. UU. al 35%. Las ventanas de 5 años se enciman y los tres emisores sobrevivieron: es una guía, no "
              "una promesa.", alto=340)
    c += tabla([[_e(n), _e(r), p(m), f"{p(a)} a {p(b)}"] for n, r, m, a, b in RETORNO_ESPERADO],
               ["Tramo", "Percentil del consenso", "Mediana anual", "Rango 10% a 90%"])
    c += ("<p><b>Para escoger entre REITs de calidad.</b> Mandar toda la aportación del mes al de percentil más alto contra "
          "su propia historia le ganó a repartir en partes iguales: +72 pb al año, más que cada una de 500 elecciones al "
          "azar con las mismas rachas. Sigue <b>inconcluso</b>: son decenas de cambios, no cientos, y los tres "
          "emisores sobrevivieron.</p>")
    c += "<h3>De dónde sale el rendimiento de un REIT</h3>"
    c += figs(g_descomposicion(partes), pie="Fuente: precios y dividendos versionados de cada emisor "
              "(data/estudios/). (1 + retorno) = (1 + dividendo) × (1 + crecimiento) × (1 + revaluación).", alto=260)
    c += tabla([[d["ticker"], f"{d['desde']:%Y}-{d['hasta']:%Y}", p(d["retorno"]), p(d["dividendo"]),
                 p(d["crecimiento"]), p(d["revaluacion"]), f"{p(d['yield_inicio'])} → {p(d['yield_hoy'])}"]
                for d in partes],
               ["Emisor", "Periodo", "Retorno anual", "Dividendo", "Crecimiento", "Revaluación", "Yield al inicio → hoy"])
    c += ("<p>Más de la mitad del rendimiento vino del dividendo, y la valuación (el yield al que compras) decide cuánto "
          "dividendo te toca por cada peso. Por eso la valuación importa a quien busca renta, aunque no sirva para "
          "escoger el momento (documento 05).</p>")
    c += "<h2>4. La prueba del universo</h2>"
    c += ("<p>Lo que funcionó con tres REITs de calidad, ¿funciona escogiendo entre todos los que cotizan? Con 128 REITs "
          "de 1999 a 2026: <b>no</b>. «Barato» no le ganó a comprar todos con ninguna señal (−1.4, −1.2 y −0.6 puntos al "
          "año), y los baratos concentraron las trampas: 23% recortó el dividendo al año siguiente, contra 12% de todos. "
          "La lección: la valuación sirve para escoger <b>entre</b> REITs que ya pasaron la puerta de calidad, no en "
          "todo el mercado.</p>")
    c += _anexos(ANEXOS_01)
    return _documento("La plataforma y la valuación", c, figs)


PAGINAS = [
    ("1 · Valuación", "La valuación de un REIT hoy, el semáforo y cuánto esperar ganar según qué tan caro está."),
    ("2 · Sectorial", "Cómo se compara contra su sector y los cap rates."),
    ("3 · Portafolio", "Tus posiciones, su rendimiento y su riesgo."),
    ("4 · Calendario", "Fechas de dividendos y reportes."),
    ("5 · Simulación", "Qué pasa con tu dinero en distintos escenarios, con ISR."),
    ("6 · Inmueble vs REITs", "Comprar un inmueble para rentar contra comprar REITs."),
    ("7 · Estudio", "El estudio de largo plazo de O, NNN o WPC."),
    ("8 · Reglas", "El semáforo puesto a prueba en toda la historia."),
    ("9 · Valuación en el tiempo", "Los métodos de valuación mes a mes y su retorno esperado."),
    ("10 · Universo de REITs", "La prueba con todos los REITs que cotizan."),
    ("11 · Investigación", "La investigación pre-registrada de cuándo entrar y en cuáles."),
]

ANEXOS_01 = [
    ("docs/estudios/estudio_O.pdf, estudio_NNN.pdf, estudio_WPC.pdf", "Cada emisor desde su salida a bolsa: historia, "
     "eras, de dónde salió el retorno, entradas y riesgos."),
    ("docs/estudios/metodos_de_valuacion.pdf", "Los siete métodos y el consenso en el tiempo; DDM, DCF y NAV."),
    ("docs/estudios/valuacion_trimestral.xlsx", "Cada trimestre de cada emisor con fórmulas vivas."),
    ("docs/estudios/reglas_de_decision.pdf", "El semáforo puesto a prueba contra aportar siempre."),
    ("docs/estudios/universo_de_reits.pdf", "La prueba con todos los REITs que cotizan hoy."),
]


# --------------------------------------------------------------------------------------
# 02. ¿Cuándo entrar?
# --------------------------------------------------------------------------------------


def html_cuando(res: dict) -> str:
    from src.investigacion import conclusiones as concl

    figs = Figs()
    kpis = [("22 + 5", "reglas de entrada y modelos probados (1972-2015)"),
            ("0", "pasaron el filtro en desarrollo"),
            ("−127 pb", "al año costó la protección por tendencia en 8 mercados"),
            ("195-432 pb", "lo mínimo que las pruebas de timing podían ver")]
    preguntas = [q for t, q, _, d in PREGUNTAS if d == "02"]
    c = _portada("Compilado · 02", "¿Cuándo entrar?",
                 "La investigación pre-registrada sobre si existe una manera eficiente de saber cuándo estar en REITs y "
                 "cuándo en efectivo, y lo que se hizo después para entender por qué no se encontró.", kpis, preguntas)
    c += _pregunta(PREGUNTAS[3][1], "Se armó y se corrió un plan de 9 fases con 54 años de datos de EE. UU. y 8 mercados "
                   "más. No se encontró ese modelo: ninguna regla ni modelo le ganó a aportar siempre de forma robusta.")
    c += "<h2>1. Cómo se hizo</h2>" + tabla([[_e(a), _e(b)] for a, b in METODO_INVESTIGACION], ["Pieza", "Qué es"],
                                            alinear="ll")
    c += "<h2 class='salto'>2. Lo que se encontró</h2>"
    for x in concl.conclusiones(res)[:5]:
        c += _conclusion(x.titulo, _e(x.texto), x.tono)
    f5 = res["fase5"]["desarrollo"].copy()
    f5["etq"] = f5["senal"] + " · " + f5["regla"]
    f5 = f5.sort_values("mejora_rebalanceo", ascending=False)
    fig, alto = _barras_h(f5["etq"].tolist(), f5["mejora_rebalanceo"].tolist(),
                          titulo="Las 22 reglas de entrada contra aportar siempre (desarrollo 1972-2015, pb al año)",
                          alto=620)
    c += figs(fig, pie="Fuente: data/investigacion/resultados/fase5. Ninguna pasó el filtro pre-registrado (+50 pb "
              "robusto a ejecutar un mes tarde, al doble de comisión y en las dos eras). La de arriba, salir con estrés "
              "financiero extremo (+92 pb), vino toda de 1993-2015 (en 1972-1992 dio −15 pb) y usa una serie que se "
              "revisa; la tendencia (+15 pb) costaba −110 pb ejecutando un mes tarde.", alto=alto)
    t = res["fase3"]["frecuencia"]
    c += "<h3>Esperar en efectivo casi nunca gana</h3>" + tabla(
        [[f"{int(r.horizonte_meses)} meses", f"{int(r.independientes)}", p(r.fraccion_efectivo_gana, 0),
          p(r.rendimiento_reits_mediana), p(r.rendimiento_efectivo_mediana)] for r in t.itertuples()],
        ["Horizonte", "Ventanas independientes", "El efectivo ganó", "REITs (mediana anual)", "Efectivo (mediana anual)"])
    techo = res["fase3"]["techo"]
    c += "<h3>Ni conociendo el futuro: decidir solo el dinero nuevo casi no vale</h3>" + tabla(
        [[_e(r.regla), _e(r.modo), p(r.tir), pb(r.contra_aportar_siempre_bps / 1e4), p(r.caida_maxima)]
         for r in techo.itertuples()], ["Regla (con información perfecta)", "Modo", "TIR", "Contra aportar (pb)",
                                        "Caída máxima"])
    c += ("<p>Si solo decides a dónde va la aportación nueva, ni un oráculo pasa de +79 pb al año: la riqueza ya invertida "
          "sigue expuesta. El valor teórico está en vender antes de cada caída (+589 pb), y eso nadie lo logró anticipar.</p>")
    c += "<h2>3. «Esto invalida la valuación»</h2>"
    c += _pregunta(PREGUNTAS[4][1], "No: la valuación sí predice cuánto vas a ganar; lo que no hace es decir cuándo "
                   "esperar. Para comprobarlo se hicieron tres análisis más.")
    for x in concl.conclusiones(res)[7:9]:
        c += _conclusion(x.titulo, _e(x.texto), x.tono)
    c += _pregunta(PREGUNTAS[5][1], "Escoger una sola acción sí se parece a una moneda; tener muchas la elimina. Y la "
                   "valuación no es una moneda: en sus extremos separa 19.4% de 4.7% al año.")
    c += tabla([["10% más barato del consenso (O, NNN, WPC)", "19.4%"], ["Centro", "9.3%"],
                ["10% más caro", "4.7%"]], ["Dónde estaba al comprar", "Retorno anual a 5 años (neto broker 35%)"])
    c += ("<p>En el sector, las pocas veces que los REITs quedaron en su 5% más barato contra los bonos (1998-99, 2001-03, "
          "2008-09 y una vez después de 2016) los 12 meses siguientes fueron muy buenos. Son 2 pistas de 56 combinaciones "
          "y no se convierten en regla de timing para quien aporta siempre: dicen que esos son los peores momentos para "
          "dejar de aportar y los mejores para meter dinero extra. Salirse solo en el extremo caro nunca ganó +50 pb.</p>")
    c += "<h3>¿Las pruebas podían ver una ventaja?</h3>" + tabla([
        ["Cuándo entrar", "195 a 432 pb al año", "Una ventaja de 100 pb habría pasado inadvertida entre 45% y 82% de las veces"],
        ["En cuáles REITs", "59 a 110 pb al año", "Momentum se distingue del azar, pero se queda corto"],
        ["Escoger entre O, NNN y WPC", "54 pb al año", "+72 pb observado, más que 500 elecciones al azar"],
    ], ["Pregunta", "Mínimo detectable", "Qué se vio"], alinear="lll")
    c += ("<p>Que no se encontrara una regla de timing no prueba que no exista una ventaja de 1 punto al año; lo que sí "
          "descarta es una ventaja grande y confiable. Además, salirse a ciegas cuesta de 86 a 302 pb al año: cualquier "
          "regla tiene que ganar eso solo para empatar.</p>")
    c += _anexos([("docs/investigacion/investigacion_cuando_entrar.pdf", "La investigación completa en PDF."),
                  ("docs/investigacion/RESUMEN.md y fase*_resultados.md", "Cada fase con sus tablas y su pre-registro."),
                  ("docs/investigacion/extremos_resultados.md, poder_resultados.md", "Extremos y análisis de poder."),
                  ("docs/investigacion/sensibilidad_broker.md", "Todo otra vez con los impuestos del broker.")])
    return _documento("¿Cuándo entrar?", c, figs)


METODO_INVESTIGACION = [
    ("Pregunta", "¿Existe una manera eficiente de saber cuándo estar en REITs y cuándo en efectivo?"),
    ("Datos", "FTSE Nareit All Equity REITs desde 1972, 29 series macro de FRED con su rezago de publicación, factores "
     "de Kenneth French y Shiller, y 8 mercados más (Japón, Australia, Singapur, Hong Kong, Reino Unido, Europa, Canadá "
     "y FIBRAs) sellados sin mirarlos."),
    ("Pre-registro", "Cada hipótesis, señal y criterio se guardó en un commit antes de correrla."),
    ("Muestras", "Desarrollo 1972-2015 para diseñar; validación 2016 en adelante para comprobar; mercados sellados para la "
     "prueba final, abiertos una sola vez con el modelo congelado."),
    ("Criterio de éxito", "+50 pb al año de TIR contra aportar siempre, robusto a ejecutar un mes tarde y al doble de "
     "comisión; o proteger 30% de la caída costando a lo más 25 pb."),
    ("Contra el azar", "Bitácora de cada intento, PBO y Sharpe deflactado por el número de pruebas."),
    ("Fases", "0 reglas, 1 literatura, 2 datos, 3 exploración, 4 pre-registro, 5 señales, 6 en cuáles, 7 escalera de "
     "modelos (hasta árboles y regímenes de Markov), 8 prueba final."),
]


# --------------------------------------------------------------------------------------
# 03. ¿En cuáles REITs?
# --------------------------------------------------------------------------------------


def html_cuales(res: dict) -> str:
    from src.investigacion import conclusiones as concl
    from src.investigacion import fase6

    figs = Figs()
    sat = _satelite()
    kpis = [("16", "reglas de selección con todos los REITs de EE. UU. desde 2011"),
            ("+38 pb", "lo más que llegó una regla en la prueba final (momentum)"),
            ("−3 a −19 pb", "le restó cada satélite a la cartera contra lo que sigue SCHH"),
            ("14 → 3", "ideas nuevas que sobrevivieron al catálogo")]
    preguntas = [q for t, q, _, d in PREGUNTAS if d == "03"]
    c = _portada("Compilado · 03", "¿En cuáles REITs?",
                 "Si no hay un cuándo, ¿hay un en cuáles? Las reglas para escoger REITs, el núcleo y satélite contra "
                 "SCHH y la búsqueda de estrategias que le ganen.", kpis, preguntas)
    c += "<h2>1. Escoger REITs con reglas (fase 6)</h2>"
    for x in concl.conclusiones(res)[4:6]:
        c += _conclusion(x.titulo, _e(x.texto), x.tono)
    d6 = res["fase6"]["desarrollo"].copy()
    d6["nombre"] = d6["regla"].map(lambda r: fase6.NOMBRES.get(r, r))
    d6 = d6.sort_values("mejora", ascending=False)
    fig, alto = _barras_h(d6["nombre"].tolist(), d6["mejora"].tolist(),
                          titulo="Las 16 reglas contra repartir entre todos (desarrollo 2011-2015, pb al año)", alto=480)
    c += figs(fig, pie="Fuente: data/investigacion/resultados/fase6. Tres pasaron de +190 pb en desarrollo, pero el "
              "filtro también pide que gane en los dos tramos (2011-2013 y 2014-2015) y que sea significativa: solo "
              "«yield alto contra su historia» y momentum lo cumplieron. En validación la primera perdió 28 pb y momentum "
              "ganó +57; en los emisores sellados, +38, debajo del criterio de +50.", alto=alto)
    c += _pregunta(PREGUNTAS[6][1], "Comprar cada mes, sí. «El que yo quiera», no: lo que ninguna regla superó fue tener "
                   "a TODOS, no tener uno cualquiera.")
    c += ("<p>Un REIT escogido al azar rinde en promedio lo mismo que todos juntos, pero con mucho más riesgo: cada año, "
          "entre 10% y 14% de los REITs recortaron el dividendo o quebraron, y desde 2016 cerca de 1 de cada 11 perdió 30% "
          "o más en un año. Escoger uno es la moneda al aire; tenerlos todos la elimina. La calidad no sube el rendimiento "
          "(+68 pb, sin pasar el filtro) pero quitó los recortes (0% contra 10%).</p>")
    c += "<h2>2. Núcleo y satélite contra SCHH</h2>"
    c += _pregunta(PREGUNTAS[7][1], "Con 85% en SCHH y 15% en un satélite de REITs escogidos por una regla, solo con "
                   "dinero nuevo y sin vender. En la historia ningún satélite le ganó a lo que sigue SCHH hoy.")
    if not sat.empty:
        s = sat[sat["referencia"] == "indice"].copy()
        s["nombre"] = s["satelite"].map(lambda r: {"todos": "Todos por partes iguales"}.get(r, fase6.NOMBRES.get(r, r)))
        fig, alto = _barras_h(s["nombre"].tolist(), s["mejora"].tolist(),
                              titulo="El satélite solo contra el índice que sigue SCHH (TIR neta, pb al año, 2011-2026)",
                              alto=260)
        c += figs(fig, pie="Fuente: docs/estudios/satelite_exploratorio.md. Exploratoria con datos ya vistos: no confirma "
                  "nada.", alto=alto)
        c += tabla([[_e(f.nombre), f"{f.escogidos_promedio:.0f}", pb(f.mejora), pb(f.mejora_cartera),
                     f"{int(f.anios_ganados)} de {int(f.anios)}"] for f in s.itertuples()],
                   ["Satélite", "Escogidos", "Satélite contra índice (pb)", "Cartera 85/15 contra índice (pb)",
                    "Años que ganó"])
    c += ("<p><b>La prueba que vale corre en papel.</b> Momentum quedó congelado en un pre-registro y se sigue sin dinero "
          "real contra SCHH: aportaciones teóricas de 3,000 dólares al cierre de febrero, mayo, agosto y noviembre, de "
          "noviembre de 2026 a agosto de 2029. Veredicto el 30 de noviembre de 2029: éxito solo con +50 pb al año de TIR "
          "neta y exceso bruto positivo; abandono si después de 8 aportaciones va 200 pb abajo.</p>")
    c += "<h2>3. La búsqueda de una estrategia que le gane</h2>"
    c += _pregunta(PREGUNTAS[8][1], "Seis investigadores propusieron 14 ideas con mecanismo y fuentes; un adversario mató "
                   "9 y quedaron 3 en el catálogo. Ninguna de selección llega con margen a +50 pb; lo único con mecanismo "
                   "sólido es fiscal.")
    c += figs(g_embudo(), pie="285 combinaciones consideradas en la sesión (2 con retornos vistos, 283 conceptuales); "
              "en total van 41 pruebas con retornos vistos en este universo.", alto=230)
    c += tabla([[FAMILIAS[f], _e(n), _e(r), _e(v), "—" if s is None else f"{s:.2f}"] for f, n, r, v, s in EDGES],
               ["Familia", "Idea", "Rango propio (pb al año)", "Veredicto", "Puntaje (de 5)"], alinear="llrlr")
    c += ("<p><b>Por qué las de selección no alcanzan:</b> sus centros van de 0 a +30 pb al año y el panel solo distingue "
          "efectos de 59 a 110 pb; con la historia solo pueden morir, y la confirmación tendría que ser en papel. "
          "<b>La única fuerte es fiscal:</b> un ETF irlandés de acumulación paga 15% dentro del fondo en lugar de 44% sobre "
          "cada dividendo (documento 04).</p>")
    c += _anexos([("docs/investigacion/fase6_resultados.md", "Las 16 reglas, la validación y la prueba final."),
                  ("docs/estudios/satelite_exploratorio.md, satelite_preregistro.md", "Núcleo y satélite y su prueba en papel."),
                  ("docs/estudios/satelite_en_papel.md", "Cómo va la cuenta en papel (se actualiza cada trimestre)."),
                  ("docs/estudios/edges/catalogo_edges_contra_schh.docx", "El catálogo de edges con su auditoría.")])
    return _documento("¿En cuáles REITs?", c, figs)


# --------------------------------------------------------------------------------------
# 04. Impuestos y canal
# --------------------------------------------------------------------------------------


def html_impuestos(res: dict) -> str:
    figs = Figs()
    kpis = [("44%", "paga el dividendo con broker de EE. UU. y marginal de 35%"),
            ("10%", "paga la ganancia al vender (en el modelo; por confirmar)"),
            ("15%", "retiene EE. UU. dentro de un ETF irlandés"),
            ("60 mil USD", "umbral del impuesto sucesorio de EE. UU.")]
    preguntas = [q for t, q, _, d in PREGUNTAS if d == "04"]
    c = _portada("Compilado · 04", "Impuestos y canal",
                 "Cómo cambian los números por comprar con un broker de EE. UU. en lugar del SIC, qué encontró la "
                 "búsqueda sobre la ley, y qué preguntarle al contador.", kpis, preguntas)
    c += _pregunta(PREGUNTAS[9][1], "Se repitió toda la investigación con los impuestos de un broker de EE. UU.: el "
                   "dividendo paga 39% a 44%, aportar siempre rinde 145 a 184 pb menos al año, y ningún veredicto cambia.")
    c += "<h2>1. Los perfiles fiscales del modelo</h2>"
    c += tabla([[_e(a), b, c_, d, e] for a, b, c_, d, e in PERFILES],
               ["Canal", "Dividendo", "Intereses", "Ganancia", "Comisión"], alinear="lrrrr")
    c += ("<p>Con broker de EE. UU., el dividendo paga tu tasa marginal más 9 puntos: EE. UU. retiene 10% por el tratado, "
          "México lo acumula a tu tarifa anual con crédito por esa retención, y además cobra 10% sobre lo que te llega (9 "
          "de cada 100). Como no sabías tu tasa, se corrió con 30% y con 35%.</p>")
    c += tabla([["Aportar siempre", "−145 a −184 pb al año", "Es el costo del canal, no de una estrategia"],
                ["Tendencia de 10 meses (8 mercados)", "−49 a −54 pb", "Cuesta menos, sigue RECHAZADA"],
                ["Tendencia en EE. UU. desde 2016", "−386 a −387 pb", "Sigue RECHAZADA"],
                ["Momentum en los sellados", "+41 / +42 pb", "Sigue debajo de +50"],
                ["Consenso entre O, NNN y WPC", "+60 / +63 pb", "Sigue inconcluso"],
                ["Yield alto", "−125 pb", "Peor que con el SIC"]],
               ["Qué", "Con broker de EE. UU.", "Lectura"], alinear="lll")
    c += "<h2 class='salto'>2. Lo que encontró la búsqueda sobre la ley</h2>"
    c += _conclusion("El 20% del SIC probablemente está mal", "El Art. 142 fr. V de la LISR acumula el dividendo de una "
                     "sociedad extranjera a la tarifa anual, más 10% adicional, sin distinguir el canal. Por el SIC "
                     "también pagaría ~44%, y además 0.25% de comisión. Si se confirma, la ventaja del SIC es casi toda un "
                     "error del modelo. Ningún veredicto cambia, porque la sensibilidad ya corrió con 44%.", "desfavorable")
    c += _conclusion("SCHH probablemente no está en el SIC", "USRT, VNQ, XLRE, IYR y RWR sí cotizan en la BMV. El 10% de "
                     "la ganancia (Art. 129 y Criterio 37/ISR/N) exige que el valor esté listado; si SCHH no lo está, su "
                     "ganancia al venderse podría pagar la tarifa general. Mientras no vendas no importa.", "neutral")
    c += ("<p><b>Distribución o ganancia.</b> Con broker, cada dólar que reparte un REIT paga 44% y cada dólar que sube "
          "su precio paga 10% solo al vender, que con la regla de nunca vender es casi nunca. Por eso conviene que lo "
          "que compras reparta poco: SCHH ya es el ETF de REITs que menos reparte (76% del ingreso de su índice). Mientras "
          "acumulas, reinvierte las distribuciones.</p>")
    c += "<h2>3. La idea fiscal: un ETF irlandés de acumulación</h2>"
    c += ("<p>Dentro de un fondo irlandés, EE. UU. retiene 15% sobre los dividendos de REIT (tratado EE. UU.-Irlanda, "
          "enmienda de 1999) y el fondo los reinvierte; México no grava mientras no vendas, si el fondo no cae en el "
          "régimen de regímenes fiscales preferentes. Además, queda fuera del impuesto sucesorio de EE. UU.</p>")
    c += tabla([["IUSI (iShares, físico; en la BMV como IUSIN)", "+21 a +25 pb", "+6 a +11 pb", "−58 pb"],
                ["XRES (Invesco, sintético; no está en la BMV)", "+57 a +59 pb", "−38 a −53 pb", "—"]],
               ["Vehículo", "Sin vender nunca", "Vendiendo todo al final", "Si el SAT aplicara REFIPRE"], alinear="lrrr")
    c += ("<p>No es alfa: antes de impuestos pierde contra SCHH. Solo le gana a SCHH comprado por broker después de "
          "impuestos, y su composición (el índice de IUSI filtra por yield) puede mover el resultado más que la ventaja "
          "fiscal. <b>Nada de esto se hace sin la opinión del contador.</b></p>")
    c += "<h2>4. El impuesto sucesorio de EE. UU.</h2>"
    c += ("<p>Arriba de 60 mil dólares en activos de EE. UU. (SCHH y tus acciones de EE. UU. juntas), tus herederos "
          "pagarían hasta 40%. Con lo que aportas hoy falta mucho; cuando te acerques, conviene revisarlo (el ETF "
          "irlandés queda fuera).</p>")
    c += tabla([[f"{m:,} dólares", f"{a5:.0f}", f"{a7:.0f}"] for m, a5, a7 in ANIOS_60K],
               ["Aportación mensual", "Años para llegar a 60 mil (5% anual)", "Años (7% anual)"])
    c += "<h2>5. Las cinco preguntas para el contador</h2><ol>" + "".join(
        f"<li>{_e(x)}</li>" for x in PREGUNTAS_CONTADOR) + "</ol>"
    c += ("<p>Es lo de mayor valor esperado de todo el análisis: las respuestas deciden en qué vehículo conviene aportar "
          "y si los números del SIC del modelo hay que corregirlos.</p>")
    c += _anexos([("docs/investigacion/sensibilidad_broker.md", "Toda la investigación con los impuestos del broker."),
                  ("docs/estudios/edges/catalogo/f6_ucits_acumulacion_irlanda.yaml", "La card del ETF irlandés con sus "
                   "fuentes y criterios para descartarla."),
                  ("src/fiscal/mexico.py, src/investigacion/diseno.py", "Cómo calcula los impuestos el modelo.")])
    return _documento("Impuestos y canal", c, figs)


def _anios_para(monto: float, meta: float, anual: float) -> float:
    i = (1 + anual) ** (1 / 12) - 1
    return float(np.log(1 + meta * i / monto) / np.log(1 + i) / 12)


ANIOS_60K = [(m, _anios_para(m, 60_000, 0.05), _anios_para(m, 60_000, 0.07)) for m in (100, 250, 500, 1000, 2000)]


# --------------------------------------------------------------------------------------
# 05. Qué comprar y cuánto
# --------------------------------------------------------------------------------------


def html_comprar() -> str:
    figs = Figs()
    r = _etfs()
    kpis = [("SCHH", "el ETF más parecido al índice de la investigación desde 2020"),
            ("0.07%", "lo que cuesta al año"),
            ("4", "pagos al año (cada trimestre) en los tres ETFs amplios"),
            ("~20%", "de tu ahorro a REITs, después del fondo de emergencia")]
    preguntas = [q for t, q, _, d in PREGUNTAS if d == "05"]
    c = _portada("Compilado · 05", "Qué comprar y cuánto",
                 "De la investigación a la práctica: qué ETF comprar, cuánto aportar, cómo pensar en la valuación si lo "
                 "que buscas es renta, y qué hacer cada trimestre.", kpis, preguntas)
    c += _pregunta(PREGUNTAS[10][1], "Sí hay ETFs con casi todos los REITs (SCHH, USRT, VNQ), pero pagan cada trimestre. "
                   "Los que pagan cada mes (KBWY, SRET) escogen por yield alto: justo la trampa de la investigación.")
    if r is not None:
        a = r.tablas["indice_actual"]
        e = a[a["serie"].isin(["SCHH", "USRT", "VNQ"])]
        c += "<h2>1. Los tres ETFs contra el índice de la investigación</h2>"
        c += tabla([[f"<b>{f.serie}</b>", f"{pd.Timestamp(f.desde):%Y-%m}", p(f.rendimiento_anual), pb(f.diferencia_anual),
                     p(f.error_de_seguimiento, 2), p(f.caida_maxima), p(f.yield_12m, 2),
                     p(f.costo_publicado, 2)] for f in e.itertuples()],
                   ["ETF", "Con su índice desde", "Rendimiento anual", "Contra el índice (pb)", "Se desvía al año",
                    "Peor caída (en ese periodo)", "Yield 12m", "Costo"])
        c += ("<p><b>SCHH</b> es prácticamente el índice de la investigación desde que cambió de índice en 2020 (−2 pb al año, "
              "se desvía 0.43%) y es el más barato. <b>USRT</b> se desvía más porque su índice deja fuera torres y madera "
              "(contra su propio índice solo 0.38%). <b>VNQ</b> trae inmobiliarias que no son REITs y le ha costado medio "
              "punto al año. Ninguno quita las caídas: USRT cayó 66% y VNQ 68% en 2007-2009 (SCHH aún no existía), y los "
              "tres cerca de 30% en 2022-2023.</p>")
        c += figs(g_etfs_anios(r.tablas["anios"]), pie="Fuente: docs/estudios/etfs_de_reits.md (Yahoo, retorno total). Solo años "
                  "completos.", alto=320)
    c += "<h2 class='salto'>2. Cuánto comprar cada mes</h2>"
    c += _pregunta(PREGUNTAS[11][1], "Depende de tus finanzas, no del mercado. Con lo que nos dijiste (menos de 5,000 "
                   "pesos de ahorro al mes, sin fondo de emergencia todavía y con acciones amplias), primero el fondo y "
                   "después ~20% del ahorro a SCHH.")
    c += tabla([["1. Ahora", "Fondo de emergencia: 3 meses de gastos en CETES", "Todo el ahorro (si quieres el hábito, "
                 "hasta 1,000 pesos a inversión)", "Con 15,000 de gastos y 4,000 al mes: 12 meses (15 si mandas 1,000 a inversión)"],
                ["2. Con el fondo completo", "Invertir todo el ahorro", "~80% acciones amplias y ~20% SCHH",
                 "De 4,000 pesos: 3,200 y 800 (unas 2 acciones de SCHH)"],
                ["Siempre", "El mismo día cada mes, dividendos reinvertidos", "Si convertir pesos cuesta, compra cada 2 o 3 "
                 "meses", "Una vez al año, rebalancea con dinero nuevo"]],
               ["Etapa", "Qué", "Cuánto", "Ejemplo"], alinear="llll")
    c += ("<p>¿Por qué 20% y no más? Los REITs son un solo sector y cayeron 68% en 2007-2009; con 20% esa caída le pega a "
          "una quinta parte de tu dinero. Entre 10% y 25% es defendible: es criterio, no resultado de la investigación, "
          "que nunca comparó REITs contra acciones amplias.</p>")
    c += "<h2>3. La valuación cuando lo que buscas es renta</h2>"
    c += _pregunta(PREGUNTAS[12][1], "Al revés: el precio al que compras ES tu renta. Lo que no funcionó fue escoger «lo "
                   "barato» para ganarle al mercado.")
    c += ("<p><b>El departamento.</b> Un departamento que renta 10,000 pesos al año, comprado en 100,000, te da 10%; "
          "comprado en 200,000, 5%. Mismo departamento, misma renta: lo único que cambia es lo que pagaste. Eso es la "
          "valuación. En 1995 O pagaba 8.9% sobre su precio y hoy 5.9%: quien compra hoy recibe un tercio menos de renta "
          "por cada dólar. Lo que esperas ganar es, más o menos, el yield al que compras más lo que crezca el dividendo.</p>")
    c += _pregunta(PREGUNTAS[13][1], "No hay contradicción: la misma renta alta puede tener una causa buena o una mala.")
    c += tabla([["Caso 1: el precio bajó y la renta sigue segura", "El mismo departamento con el mismo inquilino, vendido "
                 "barato porque el dueño tiene prisa", "Bueno: cobras más por cada peso"],
                ["Caso 2: la renta está por caerse", "Un departamento que renta mucho más que los de la cuadra porque el "
                 "inquilino ya avisó que se va", "Trampa: el yield alto recortó el doble (21% contra 10%)"]],
               ["Caso", "El departamento", "Qué pasa"], alinear="lll")
    c += ("<p><b>Cómo distinguirlos:</b> compáralo contra su propia historia (no contra los demás) y exige calidad (poca "
          "deuda, reparte una parte razonable de lo que gana). Con SCHH el problema casi desaparece: si un edificio pierde "
          "a su inquilino, tienes cientos más. Y no esperes el precio perfecto: mientras esperas no cobras.</p>")
    c += "<h2>4. Cada trimestre: la prueba en papel</h2>"
    c += tabla([["Después del 15 de feb, may, ago y nov", "Actualizar los datos de la SEC",
                 "python scripts/investigacion.py emisores"],
                ["En ese mismo mes, antes de su cierre", "Anotar la aportación en papel", "python scripts/estudio.py satelite elegir"],
                ["Cuando quieras", "Ver cómo va contra SCHH", "python scripts/estudio.py satelite evaluar"]],
               ["Cuándo", "Qué", "Comando"], alinear="lll")
    c += ("<p>El calendario: 30-nov-2026, 28-feb-2027, 31-may-2027, 31-ago-2027 y así hasta 31-ago-2029; veredicto el "
          "30-nov-2029. Si un trimestre se pasa sin anotar, esa aportación se pierde (el programa se niega a anotar fuera "
          "de fecha).</p>")
    c += _anexos([("docs/estudios/etfs_de_reits.md", "USRT, SCHH y VNQ contra el índice, con todas las ventanas."),
                  ("docs/estudios/satelite_en_papel.md", "La cuenta en papel contra SCHH."),
                  ("compilado_cifras.xlsx (hoja «Mi plan»)", "La calculadora de tu plan con tus números.")])
    return _documento("Qué comprar y cuánto", c, figs)


# --------------------------------------------------------------------------------------
# Todo
# --------------------------------------------------------------------------------------


def generar(destino: Path | None = None) -> list[Path]:
    destino = destino or DIR_COMPILADO
    res = _resultados()
    docs = [("00_mapa_del_analisis.pdf", "Mapa del análisis", lambda: html_mapa(res)),
            ("01_plataforma_y_valuacion.pdf", "La plataforma y la valuación", html_plataforma),
            ("02_cuando_entrar.pdf", "¿Cuándo entrar?", lambda: html_cuando(res)),
            ("03_en_cuales_reits.pdf", "¿En cuáles REITs?", lambda: html_cuales(res)),
            ("04_impuestos_y_canal.pdf", "Impuestos y canal", lambda: html_impuestos(res)),
            ("05_que_comprar_y_cuanto.pdf", "Qué comprar y cuánto", html_comprar)]
    salidas = [a_pdf(armar(), destino / archivo, titulo) for archivo, titulo, armar in docs]
    from src.export import excel_compilado

    salidas.append(excel_compilado.exportar(destino / "compilado_cifras.xlsx", res))
    return salidas
