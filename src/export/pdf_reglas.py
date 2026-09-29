"""El backtest de las reglas de compra y venta, en PDF, para todos los emisores con estudio.

Mismo papel, tipografía y tablas que el estudio de largo plazo (``pdf_estudio``); las
gráficas son las de ``estudio.graficas_reglas`` y las cifras las de
``estudio.reglas.backtest``, así que la pantalla y el impreso dicen lo mismo.
"""

from __future__ import annotations

import datetime as dt
import html
import re
from pathlib import Path

import pandas as pd

from src.estudio import graficas as g
from src.estudio import graficas_reglas as gr
from src.estudio import reglas
from src.estudio.reglas import ResultadoReglas, Variante
from src.export.pdf_estudio import (
    GLIFO,
    _css,
    _e,
    _lanzar_chromium,
    css_de_fuentes,
    num,
    pct,
    tabla,
    usd,
)


class Figuras:
    def __init__(self) -> None:
        self.specs: list[tuple[str, str]] = []

    def __call__(self, nombre: str, r: ResultadoReglas, *, pie: str = "") -> str:
        fig = gr.FIGURAS[nombre](r, g.CLARO)
        fig.update_layout(width=700, height=int((fig.layout.height or 360) * 0.88), hovermode=False)
        ident = f"fig_{len(self.specs)}"
        self.specs.append((ident, fig.to_json()))
        pie_html = f"<div class='pie'>{_e(pie)}</div>" if pie else ""
        return f"<figure><div id='{ident}' class='grafica'></div>{pie_html}</figure>"

    def script(self) -> str:
        llamadas = "\n".join(
            f"pend.push(Plotly.newPlot('{i}', (f={s}).data, f.layout, {{staticPlot:true, displayModeBar:false}}));"
            for i, s in self.specs
        )
        return ("<script>var f; var pend=[];\n" + llamadas +
                "\nPromise.all(pend).then(()=>{document.body.dataset.listo='1';});</script>")


def _pb(x) -> str:
    return "—" if x is None or pd.isna(x) else f"{x * 1e4:+,.0f}"


def _portada(resultados: list[ResultadoReglas]) -> str:
    emisores = ", ".join(r.ticker for r in resultados)
    hasta = max(r.hasta for r in resultados)
    return f"""
    <section class='portada'>
      <div class='marca'>SPREAD <span>TRADING CLUB</span></div>
      <div style='flex-grow:1;display:flex;flex-direction:column;justify-content:center'>
        <div class='rotulo'>Reglas de compra y venta · {_e(emisores)}</div>
        <h1>¿Comprar, comprar menos o vender?</h1>
        <p style='font-size:12.5pt;max-width:150mm'>El semáforo de la aplicación, evaluado cada mes con
        lo que se sabía ese día y puesto a prueba en toda la historia de cada REIT: qué hubiera decidido,
        cuándo hubiera vendido por tesis rota y cuánto hubiera rendido contra aportar lo mismo sin reglas.</p>
        {_tabla_comparativa(resultados)}
      </div>
      <div class='gris chico'>Datos al {hasta:%d-%m-%Y} · generado el {dt.date.today():%d-%m-%Y}.
      Herramienta de análisis, no asesoría de inversión. Los cálculos fiscales son indicativos.</div>
    </section>"""


def _tabla_comparativa(resultados: list[ResultadoReglas]) -> str:
    filas = []
    for r in resultados:
        m, b = r.tabla.loc[Variante.MODELO.value], r.tabla.loc[Variante.BENCHMARK.value]
        filas.append([_e(r.ticker), f"{r.desde:%Y}", pct(m["tir_usd"]), pct(b["tir_usd"]),
                      _pb(m["ventaja_tir_usd"]), num(m["ventas"]), pct(m["exposicion_promedio"], 0),
                      num(r.apuestas.episodios), _e(r.dictamen.veredicto.value), _e(r.decision_hoy["decision"])])
    return tabla(filas, ["Emisor", "Desde", "TIR modelo", "TIR sin reglas", "Diferencia (pb/año)", "Ventas",
                         "En el papel", "Cambios de postura", "Dictamen", "Hoy"], alinear="llrrrrrrll")


def _modelo() -> str:
    return (
        "<h2>El modelo</h2>"
        "<p>Es el <b>semáforo de la pantalla de valuación</b>, evaluado cada fin de mes con lo publicado a "
        "esa fecha. Su acción decide qué hacer con el dinero del mes —la aportación y los dividendos "
        "netos—; la decisión se ejecuta al cierre de la sesión siguiente.</p>"
        + tabla([
            ["COMPRAR — prima en el percentil ≥ 70 de su propia historia", "<b>Comprar</b>",
             "todo, más toda la reserva acumulada"],
            ["MANTENER — percentil 30 a 70", "<b>Comprar menos</b>", "la mitad; la otra mitad a la reserva"],
            ["NO COMPRAR MÁS (&lt; 30) o DESCARTADO por calidad", "<b>No comprar</b>", "todo a la reserva"],
            ["VENDER — Puerta 3: deterioro en dos reportes seguidos", "<b>Vender por tesis rota</b>",
             "se vende todo; nada se compra"],
            ["INCONCLUSO — faltan datos", "Sin señal", "todo, como sin reglas"],
        ], ["Semáforo", "Decisión", "Dinero del mes"], alinear="lll")
        + "<p><b>Calidad (Puerta 1)</b>: payout sobre AFFO menor a 90%, AFFO por acción creciendo, deuda "
        "neta ÷ EBITDA menor a 6.5x, spread de inversión positivo y grado de inversión; con menos de tres "
        "criterios medibles no dice nada. <b>Deterioro (Puerta 3)</b>: payout arriba de 100%, AFFO por acción "
        "cayendo o spread negativo en dos reportes seguidos, deuda arriba de 6.5x, o pérdida del grado de "
        "inversión. <b>Valuación (Puerta 2)</b>: percentil expandible de la prima —yield de flujo menos el "
        "Treasury a 10 años— contra la propia historia del emisor; nunca vende.</p>"
        "<p>Los umbrales son los de la pantalla (<span class='cifra'>config.UMBRALES</span>), fijados antes "
        "de este backtest. Lo único nuevo es la mitad de «comprar menos», y por eso cada emisor trae la "
        "sensibilidad completa. La reserva es efectivo en dólares que rinde el T-bill a 3 meses.</p>"
        "<div class='aviso'><b>Cómo leer los resultados.</b> Con 30 años y una señal lenta, cada emisor da "
        "decenas de decisiones independientes, no cientos. El proyecto pide 100 para afirmar que una regla "
        "funciona (P7); debajo de eso el dictamen es INCONCLUSO aunque la regla haya ganado. Esto muestra cómo "
        "se hubiera comportado el modelo, no prueba que funcione.</div>"
    )


def _emisor(r: ResultadoReglas, fig: Figuras) -> str:
    bloques = []
    for c in reglas.conclusiones(r):
        glifo, color = GLIFO.get(c.tono, GLIFO["neutral"])
        bloques.append(f"<div class='conclusion' style='border-left-color:{color}'>"
                       f"<b><span style='color:{color}'>{glifo}</span> {_e(c.titulo)}</b><p>{_e(c.texto)}</p></div>")
    pd_ = r.por_decision
    filas_dec = [[_e(d), num(f["meses"]), pct(f["mediana_12m"]), pct(f["peor_12m"]), pct(f["mejor_12m"]),
                  num(f["independientes"], 1)] for d, f in pd_.iterrows()]
    t = r.tabla
    filas_var = [[_e(v), pct(f["tir_usd"]), pct(f["tir_mxn"]), _pb(f["ventaja_tir_usd"]), f"{f['multiplo']:.2f}x",
                  pct(f["exposicion_promedio"], 0), pct(f["caida_maxima"], 0), num(f["ventas"]),
                  usd(f["impuestos"] / 1e3, 0)] for v, f in t.iterrows()]
    v = r.ventas
    ventas = "<p>El modelo nunca vendió.</p>"
    if not v.empty:
        filas_v = [[g.mes(f["fecha"]), _e(f["disparadores"]), usd(f["precio"]), pct(f.get("papel_1a")),
                    pct(f.get("papel_3a")),
                    g.mes(f["recompra"]) if pd.notna(f.get("recompra")) else "—",
                    g.mes(f["reinversion"]) if pd.notna(f.get("reinversion")) else "no ha vuelto",
                    usd(f.get("precio_reinversion")), num(f.get("meses_fuera")),
                    pct(f.get("papel_mientras_fuera"))]
                   for _, f in v.iterrows()]
        ventas = tabla(filas_v, ["Venta", "Disparador", "Precio", "Papel 1 año después", "3 años",
                                 "Primera compra después", "Lo vendido vuelve", "Precio", "Meses fuera",
                                 "Papel mientras fuera"], alinear="llrrrllrrr")
    c = r.criterios
    filas_c = [[_e(f["puerta"]), _e(f["criterio"]), num(f["meses"]), pct(f["fraccion"], 0)] for _, f in c.iterrows()]
    s = r.sensibilidad
    filas_s = [[pct(f["fraccion_comprar_menos"], 0), pct(f["tir_usd"]), _pb(f["ventaja_tir_usd"]),
                f"{f['multiplo']:.2f}x"] for _, f in s.iterrows()]
    return (
        f"<h2 class='salto'>{_e(r.nombre)} ({_e(r.ticker)})</h2>"
        f"<p class='gris chico'>{r.desde:%m-%Y} a {r.hasta:%m-%Y} · prima sobre {_e(r.medida)}.</p>"
        + "".join(bloques)
        + "<div class='bloque'><h3>Qué decía el modelo cada mes</h3>"
        + fig("decisiones", r, pie="Precio por acción de hoy. Las bandas son la decisión de cada mes; ▼ venta por "
              "tesis rota, ▲ cuando lo vendido vuelve al papel.")
        + tabla(filas_dec, ["Decisión", "Meses", "Papel 12 meses después: mediana", "Peor", "Mejor",
                            "Ventanas independientes"], alinear="lrrrrr") + "</div>"
        + "<div class='bloque'><h3>Cuánto valdría lo aportado</h3>"
        + fig("riqueza", r, pie="1,000 dólares al mes. Sin reglas: lo mismo al mismo papel, reinvirtiendo "
              "dividendos (P6).") + "</div>"
        + fig("exposicion", r, pie="Parte de lo acumulado que estaba en el papel; el resto, en la reserva.")
        + tabla(filas_var, ["Variante", "TIR USD", "TIR MXN", "vs sin reglas (pb)", "Múltiplo", "En el papel",
                            "Caída máx.", "Ventas", "Impuestos (miles USD)"], alinear="lrrrrrrrr")
        + "<div class='bloque'><h3>Las ventas por tesis rota</h3>" + ventas + "</div>"
        + "<div class='bloque'><h3>Qué criterio movió al semáforo</h3>"
        + (tabla(filas_c, ["Puerta", "Criterio", "Meses", "Del tiempo"], alinear="llrr") if filas_c else
           "<p>Ningún criterio reprobó ni disparó.</p>") + "</div>"
        + "<div class='bloque'><h3>Sensibilidad a «comprar menos»</h3>"
        + tabla(filas_s, ["Fracción que se compra en «comprar menos»", "TIR USD", "vs sin reglas (pb)", "Múltiplo"],
                alinear="rrrr")
        + "<p class='chico gris'>Las tres, completas: ninguna se escogió por cómo salió.</p></div>"
        + f"<div class='aviso'><b>{_e(r.dictamen.veredicto.value)}.</b> {_e(r.apuestas.como_texto())}"
        + (f"<br><span class='chico gris'>{_e(r.neutralizacion.como_texto())}</span>" if r.neutralizacion else "")
        + "</div>"
    )


def _metodologia(resultados: list[ResultadoReglas]) -> str:
    notas = "".join(f"<li>{_codigo(_e(n))}</li>" for n in reglas.NOTAS_DE_METODO)
    por_calendario = "".join(
        f"<li>{_e(r.ticker)}: la regla de tesis rota sola habría vendido {_veces(r.ventas_por_calendario)} con "
        f"la persistencia contada por trimestre de calendario, contra "
        f"{_veces(len(r.variantes[Variante.SOLO_TESIS].ventas))} contada en reportes.</li>" for r in resultados)
    avisos = "".join(f"<li>{_e(a)}</li>" for r in resultados for a in r.avisos)
    return (
        "<h2 class='salto'>Metodología</h2>"
        f"<ul class='chico'>{notas}{por_calendario}</ul>"
        + (f"<h3>Avisos</h3><ul class='chico'>{avisos}</ul>" if avisos else "")
        + "<h3>Variantes</h3><p class='chico'><b>Modelo completo</b>: la tabla de decisiones. <b>Solo compras</b>: "
        "las mismas compras, pero nunca vende (VENDER se vuelve NO COMPRAR). <b>Solo tesis rota</b>: aportación "
        "fija; vende todo cuando dispara la Puerta 3 y vuelve a invertir todo en cuanto deja de disparar. "
        "<b>Sin reglas</b>: aportación fija al mismo papel, reinvirtiendo dividendos —el benchmark (P6)—.</p>"
        "<p class='chico'>La diferencia se mide en TIR money-weighted (P9), vendiendo todo al final y pagando el "
        "impuesto. El retorno activo se regresa contra el del papel para quitar el efecto de estar más o menos "
        "invertido en un activo que sube (P8), con errores estándar Newey-West. Los cambios de postura se "
        "cuentan como en <span class='cifra'>simulacion.backtest</span>: rachas contiguas con la misma dirección frente a invertir "
        "todo el dinero del mes.</p>"
        "<p class='chico gris'>Toda métrica de desempeño va acompañada de su conteo de apuestas efectivas; "
        "cuando son insuficientes el veredicto es INCONCLUSO. Los cálculos fiscales son indicativos: confirma "
        "con tu casa de bolsa y con un contador.</p>"
    )


def _codigo(texto: str) -> str:
    """`nombre` → nombre en monoespaciada: en el PDF las comillas invertidas se leen literales."""
    return re.sub(r"`([^`]+)`", r"<span class='cifra'>\1</span>", texto)


def _veces(n: int) -> str:
    return "una vez" if n == 1 else f"{n} veces"


def html_de_reglas(resultados: list[ResultadoReglas], *, fuentes_css: str | None = None) -> str:
    import plotly.offline

    fig = Figuras()
    cuerpo = (_portada(resultados) + _modelo() + "".join(_emisor(r, fig) for r in resultados)
              + _metodologia(resultados))
    css = _css(css_de_fuentes() if fuentes_css is None else fuentes_css)
    return (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<title>Reglas de compra y venta</title>"
        f"<style>{css}</style>"
        f"<script>{plotly.offline.get_plotlyjs()}</script></head>"
        f"<body>{cuerpo}{fig.script()}</body></html>"
    )


def generar_pdf(resultados: list[ResultadoReglas], destino: Path) -> Path:
    from playwright.sync_api import sync_playwright

    documento = html_de_reglas(resultados)
    destino.parent.mkdir(parents=True, exist_ok=True)
    pie = (
        "<div style='width:100%;font-family:monospace;font-size:7px;color:#6B6B66;"
        "padding:0 15mm;display:flex;justify-content:space-between'>"
        f"<span>SPREAD TRADING CLUB · Reglas de compra y venta · {html.escape(', '.join(r.ticker for r in resultados))}</span>"
        "<span><span class='pageNumber'></span> / <span class='totalPages'></span></span></div>"
    )
    with sync_playwright() as p:
        navegador = _lanzar_chromium(p)
        pagina = navegador.new_page()
        pagina.set_content(documento, wait_until="load")
        pagina.wait_for_selector("body[data-listo='1']", timeout=180_000)
        pagina.pdf(path=str(destino), print_background=True, prefer_css_page_size=True,
                   display_header_footer=True, header_template="<div></div>", footer_template=pie)
        navegador.close()
    return destino
