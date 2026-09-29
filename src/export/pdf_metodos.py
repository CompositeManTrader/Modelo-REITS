"""Los métodos de valuación en el tiempo, en PDF.

Mismo papel, tipografía y tablas que el estudio de largo plazo (``pdf_estudio``); las
gráficas son las de ``estudio.graficas_metodos`` y las cifras las de
``estudio.metodos.estudiar``, así que la pantalla, el Excel y el impreso dicen lo mismo.
"""

from __future__ import annotations

import datetime as dt
import html
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from src.estudio import graficas as g
from src.estudio import graficas_metodos as gm
from src.estudio import metodos
from src.estudio import vistas_metodos as vm
from src.estudio.metodos import METODOS, ResultadoMetodos
from src.export.pdf_estudio import (
    GLIFO,
    _css,
    _e,
    _lanzar_chromium,
    css_de_fuentes,
    num,
    pct,
    tabla,
)
from src.export.pdf_reglas import _codigo


class Figuras:
    def __init__(self) -> None:
        self.specs: list[tuple[str, str]] = []

    def __call__(self, hacer: Callable, *args, pie: str = "") -> str:
        fig = hacer(*args, t=g.CLARO)
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


def _rho(x) -> str:
    return "—" if x is None or pd.isna(x) else f"{x:+.2f}"


def _portada(r: ResultadoMetodos) -> str:
    j, a = r.juntos, r.asignacion()
    filas = [[_e(m.nombre), _rho(j.loc[m.clave, "rho_5a"]), pct(j.loc[m.clave, "r5_barato"]),
              pct(j.loc[m.clave, "r5_caro"]), _pb(a.loc[m.clave, "ventaja"]), _e(a.loc[m.clave, "eleccion_hoy"])]
             for m in METODOS]
    return f"""
    <section class='portada'>
      <div class='marca'>SPREAD <span>TRADING CLUB</span></div>
      <div style='flex-grow:1;display:flex;flex-direction:column;justify-content:center'>
        <div class='rotulo'>Métodos de valuación en el tiempo · {_e(", ".join(r.paneles))}</div>
        <h1>¿Caro o barato? Siete maneras de medirlo, trimestre por trimestre</h1>
        <p style='font-size:12.5pt;max-width:150mm'>Qué decía cada método en cada trimestre con lo que se
        sabía ese día, qué rindió el papel después, y para qué sirve saberlo: para esperar, no; para
        escoger a cuál de los tres REITs va la aportación del mes, sí.</p>
        {tabla(filas, ["Método", "Correlación con los 5 años siguientes", "5 años si decía barato",
                       "5 años si decía caro", "A cuál de los tres (pb/año)", "Hoy iría a"], alinear="lrrrrl")}
      </div>
      <div class='gris chico'>Datos al {r.hasta:%d-%m-%Y} · generado el {dt.date.today():%d-%m-%Y}.
      Herramienta de análisis, no asesoría de inversión. Los cálculos fiscales son indicativos.</div>
    </section>"""


def _conclusiones(r: ResultadoMetodos) -> str:
    bloques = []
    for c in metodos.conclusiones(r):
        glifo, color = GLIFO.get(c.tono, GLIFO["neutral"])
        bloques.append(f"<div class='conclusion' style='border-left-color:{color}'>"
                       f"<b><span style='color:{color}'>{glifo}</span> {_e(c.titulo)}</b><p>{_e(c.texto)}</p></div>")
    return "<h2 class='salto'>Lo que se encontró</h2>" + "".join(bloques)


def _metodos_y_hoy(r: ResultadoMetodos) -> str:
    desc = tabla([[f"<b>{_e(m.nombre)}</b>", _e(m.descripcion)] for m in METODOS], ["Método", "Qué mide"],
                 alinear="ll")
    h = vm.hoy(r)
    hoy = tabla([[_e(x) for x in fila] for fila in h.itertuples(index=False)], ["Método", *h.columns[1:]],
                alinear="l" + "l" * (len(h.columns) - 1))
    return ("<h2 class='salto'>Los métodos</h2><p>En todos, el número se construye para que más alto sea más "
            "barato, y se compara contra la historia propia del emisor hasta esa fecha: barato en el percentil "
            "70 o más, caro abajo del 30.</p>" + desc
            + f"<div class='bloque'><h3>Qué dice cada uno hoy ({r.hasta:%d-%m-%Y})</h3>" + hoy + "</div>")


def _predicen(r: ResultadoMetodos, fig: Figuras) -> str:
    j = r.juntos
    filas = [[_e(j.loc[m.clave, "metodo"]), _rho(j.loc[m.clave, "rho_1a"]), _rho(j.loc[m.clave, "rho_5a"]),
              pct(j.loc[m.clave, "r5_barato"]), pct(j.loc[m.clave, "r5_caro"]),
              pct(j.loc[m.clave, "r5_barato_menos_caro"]),
              f"{int(j.loc[m.clave, 'emisores_con_rho_5a_positiva'])} de {len(r.paneles)}",
              num(j.loc[m.clave, "ventanas_5a"], 0)] for m in METODOS]
    return ("<h2 class='salto'>¿Predicen?</h2>"
            + fig(gm.barato_caro, r, pie="Mediana del retorno anual de los 5 años siguientes, los tres emisores juntos.")
            + tabla(filas, ["Método", "Correlación 1 año", "5 años", "5 años si barato", "Si caro", "Brecha",
                            "Emisores a favor", "Ventanas independientes"], alinear="lrrrrrrr")
            + "<p class='chico gris'>Correlación de rangos (Spearman) entre el percentil y el retorno total neto "
              "de los años siguientes, un renglón por fin de trimestre.</p>")


def _esperar(r: ResultadoMetodos) -> str:
    partes = ["<h2 class='salto'>¿Convenía esperar cuando decía caro?</h2>"
              "<p>Si «caro» fuera una señal para guardar el dinero, el papel tendría que rendir menos que el "
              "efectivo después de decir caro. No pasa: rinde menos que de costumbre, pero más que el T-bill. "
              "Por eso comprar menos cuando está caro no le gana a aportar siempre.</p>"]
    for t in r.paneles:
        e, b = r.evaluaciones[t], r.backtests[t]
        filas = [[_e(e.loc[m.clave, "metodo"]), pct(e.loc[m.clave, "r5_caro"]),
                  pct(e.loc[m.clave, "caro_contra_efectivo"]), pct(e.loc[m.clave, "caro_le_gana_al_efectivo"], 0),
                  pct(b.loc[m.clave, "tir_usd"], 2), pct(b.loc[m.clave, "tir_sin_reglas"], 2),
                  _pb(b.loc[m.clave, "ventaja_tir"])] for m in METODOS]
        partes.append(f"<div class='bloque'><h3>{_e(r.nombres[t])} ({_e(t)})</h3>"
                      + tabla(filas, ["Método", "5 años si caro", "Contra el efectivo", "Veces que le ganó",
                                      "TIR con el método", "Sin reglas", "Diferencia (pb/año)"], alinear="lrrrrrr")
                      + "</div>")
    return "".join(partes)


def _asignacion(r: ResultadoMetodos, fig: Figuras) -> str:
    a = r.asignacion()
    filas = [[_e(a.loc[m.clave, "metodo"]), f"{a.loc[m.clave, 'desde']:%Y}", pct(a.loc[m.clave, "tir_usd"], 2),
              pct(a.loc[m.clave, "tir_partes_iguales"], 2), _pb(a.loc[m.clave, "ventaja"]),
              _pb(a.loc[m.clave, "ventaja_el_mas_caro"]), _pb(a.loc[m.clave, "ventaja_primera_mitad"]),
              _pb(a.loc[m.clave, "ventaja_segunda_mitad"]), pct(a.loc[m.clave, "azar_que_le_gana"], 1),
              num(a.loc[m.clave, "cambios"]), _e(a.loc[m.clave, "eleccion_hoy"])] for m in METODOS]
    q = vm.asignacion_trimestral(r).head(12)
    filas_q = [[_e(f["trimestre"]), *[pct(f[c], 0) for c in q.columns[1:-1]], _e(f["la_aportacion_va_a"])]
               for _, f in q.iterrows()]
    return ("<h2 class='salto'>A cuál de los tres va la aportación</h2>"
            "<p>Toda la aportación del mes —más los dividendos netos de los tres— al emisor con el percentil más "
            "alto contra su propia historia. Sin guardar efectivo y sin vender: solo cambia a cuál va el dinero. "
            "El benchmark reparte en tercios y cada emisor reinvierte sus propios dividendos.</p>"
            + fig(gm.asignacion, r, pie="Cuánta más riqueza tendría quien aportó 1,000 dólares al mes con el "
                  "consenso de los siete que quien repartió en partes iguales, con el mismo dinero aportado.")
            + tabla(filas, ["Método", "Desde", "TIR", "Partes iguales", "Ventaja (pb/año)", "Al más caro",
                            "1ª mitad", "2ª mitad", "Azar que la iguala", "Cambios", "Hoy"],
                    alinear="lrrrrrrrrrl")
            + fig(gm.azar, r, pie="200 elecciones al azar con las mismas rachas que el consenso, y dónde caen "
                  "el consenso y su espejo.")
            + "<div class='bloque'><h3>Los últimos 12 trimestres</h3>"
            + tabla(filas_q, ["Trimestre", *[f"Consenso {t}" for t in r.paneles], "La aportación va a"],
                    alinear="l" + "r" * len(r.paneles) + "l") + "</div>")


def _emisor(r: ResultadoMetodos, t: str, fig: Figuras) -> str:
    e = r.evaluaciones[t]
    filas = [[_e(e.loc[m.clave, "metodo"]), num(e.loc[m.clave, "trimestres"]), _rho(e.loc[m.clave, "rho_1a"]),
              _rho(e.loc[m.clave, "rho_3a"]), _rho(e.loc[m.clave, "rho_5a"]), pct(e.loc[m.clave, "r5_barato"]),
              pct(e.loc[m.clave, "r5_medio"]), pct(e.loc[m.clave, "r5_caro"]),
              _rho(e.loc[m.clave, "rho_5a_primera_mitad"]), _rho(e.loc[m.clave, "rho_5a_segunda_mitad"])]
             for m in METODOS]
    return (f"<h2 class='salto'>{_e(r.nombres[t])} ({_e(t)})</h2>"
            + fig(gm.mapa, r, t, pie="Percentil de cada método cada trimestre: ámbar, barato; gris, caro.")
            + fig(gm.dispersion, r, t, pie="Cada trimestre: el percentil del consenso contra el retorno anual "
                  "de los 5 años siguientes.")
            + tabla(filas, ["Método", "Trimestres", "Correlación 1 año", "3 años", "5 años", "5 años si barato",
                            "Medio", "Caro", "5 años, 1ª mitad", "2ª mitad"], alinear="lrrrrrrrrr"))


def _metodologia() -> str:
    notas = "".join(f"<li>{_codigo(_e(n))}</li>" for n in metodos.NOTAS_DE_METODO)
    return ("<h2 class='salto'>Metodología</h2>" f"<ul class='chico'>{notas}</ul>"
            "<p class='chico gris'>Los valores de cada trimestre de cada emisor, con los ocho percentiles, "
            "están en <span class='cifra'>docs/estudios/valuacion_trimestral.xlsx</span>. Toda métrica de "
            "desempeño va con su conteo de apuestas efectivas; debajo de 100 el veredicto es INCONCLUSO.</p>")


def html_de_metodos(r: ResultadoMetodos, *, fuentes_css: str | None = None) -> str:
    import plotly.offline

    fig = Figuras()
    cuerpo = (_portada(r) + _conclusiones(r) + _metodos_y_hoy(r) + _predicen(r, fig) + _esperar(r)
              + _asignacion(r, fig) + "".join(_emisor(r, t, fig) for t in r.paneles) + _metodologia())
    css = _css(css_de_fuentes() if fuentes_css is None else fuentes_css)
    return (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<title>Métodos de valuación en el tiempo</title>"
        f"<style>{css}</style>"
        f"<script>{plotly.offline.get_plotlyjs()}</script></head>"
        f"<body>{cuerpo}{fig.script()}</body></html>"
    )


def generar_pdf(r: ResultadoMetodos, destino: Path) -> Path:
    from playwright.sync_api import sync_playwright

    documento = html_de_metodos(r)
    destino.parent.mkdir(parents=True, exist_ok=True)
    pie = (
        "<div style='width:100%;font-family:monospace;font-size:7px;color:#6B6B66;"
        "padding:0 15mm;display:flex;justify-content:space-between'>"
        f"<span>SPREAD TRADING CLUB · Métodos de valuación en el tiempo · {html.escape(', '.join(r.paneles))}</span>"
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
