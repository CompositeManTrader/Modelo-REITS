"""La prueba del universo de REITs, en PDF.

Mismo papel, tipografía y tablas que los otros estudios (``pdf_estudio``); las gráficas son
las de ``estudio.graficas_seleccion``, las tablas las de ``estudio.vistas_seleccion`` y las
cifras las de ``estudio.seleccion.estudiar``: la pantalla y el impreso dicen lo mismo.
"""

from __future__ import annotations

import datetime as dt
import html
import re
from pathlib import Path

import pandas as pd

from src.estudio import graficas_seleccion as gs
from src.estudio import seleccion
from src.estudio import vistas_seleccion as vs
from src.estudio.seleccion import SENALES, ResultadoSeleccion
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
from src.export.pdf_metodos import Figuras, _tabla_vista

TITULO = "¿La valuación sabe escoger REITs?"


def _pts(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v * 100:+.1f}"


def _rho(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:+.3f}"


def _t(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:+.2f}"


def _pb(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:+,.0f}"


def _usd(v) -> str:
    return "—" if v is None or pd.isna(v) else f"${v:,.0f}"


def _p0(v) -> str:
    return pct(v, 0)


def _p1(v) -> str:
    return pct(v, 1)


def _p2(v) -> str:
    return pct(v, 2)


def _elegibles(r: ResultadoSeleccion) -> int:
    return int((r.universo["meses_elegible"] > 0).sum())


def _portada(r: ResultadoSeleccion) -> str:
    a = r.aportaciones.set_index("cartera")
    filas = []
    for s, nombre in SENALES.items():
        c, t = r.carteras[(s, False)].resumen, r.trampas[(s, False)]
        tir = a.loc[nombre, "contra_todos"] if nombre in a.index else float("nan")
        filas.append([_e(nombre), _pts(c.loc["barato", "contra_todos"]), _t(c.loc["barato", "t_contra_todos"]),
                      _rho(r.resumen_correlacion.loc[s, "promedio"]), _p0(t.loc["barato", "recorto_despues"]),
                      _p0(t.loc["caro", "recorto_despues"]), _pb(tir * 1e4)])
    capital = int(r.universo["es_reit_de_capital"].astype(str).eq("True").sum())
    return f"""
    <section class='portada'>
      <div class='marca'>SPREAD <span>TRADING CLUB</span></div>
      <div style='flex-grow:1;display:flex;flex-direction:column;justify-content:center'>
        <div class='rotulo'>Prueba del universo · {capital} REITs de capital que cotizan hoy</div>
        <h1>{_e(TITULO)}</h1>
        <p style='font-size:12.5pt;max-width:150mm'>Con O, NNN y WPC la valuación no sirvió para esperar,
        pero sí para escoger entre los tres. Aquí la misma pregunta se hace con todos los REITs de capital
        que cotizan hoy en Estados Unidos —{_elegibles(r)} con al menos cinco años de historia—: cada fin de
        mes se reparten en tres grupos según una señal de valuación y se mide si «barato» le gana a comprar
        todos, y cuántos baratos eran trampa. El diseño y las hipótesis se fijaron en un commit antes de
        correr nada.</p>
        {tabla(filas, ["Señal", "Barato contra todos (puntos/año)", "t", "Correlación con 12 meses",
                       "Barato que recortó", "Caro que recortó", "Aportando (pb/año)"], alinear="lrrrrrr")}
        <p class='chico gris'>Sin los REITs que quebraron o fueron comprados: ninguna fuente disponible
        trae su precio. Las cifras de las señales que comparan emisores entre sí son un techo.</p>
      </div>
      <div class='gris chico'>Datos a {r.hasta:%m-%Y} · generado el {dt.date.today():%d-%m-%Y}.
      Herramienta de análisis, no asesoría de inversión.</div>
    </section>"""


def _conclusiones(r: ResultadoSeleccion) -> str:
    bloques = []
    for c in seleccion.conclusiones(r):
        glifo, color = GLIFO.get(c.tono, GLIFO["neutral"])
        bloques.append(f"<div class='conclusion' style='border-left-color:{color}'>"
                       f"<b><span style='color:{color}'>{glifo}</span> {_e(c.titulo)}</b><p>{_e(c.texto)}</p></div>")
    return "<h2 class='salto'>Lo que se encontró</h2>" + "".join(bloques)


def _senales(r: ResultadoSeleccion, fig: Figuras) -> str:
    g = vs.grupos(r, filtro=False)
    return ("<h2 class='salto'>Las tres señales</h2>"
            "<p>Cada fin de mes, terciles de cada señal entre los elegibles. Cada tercil es una cartera de "
            "pesos iguales que se mantiene 12 meses, con 12 cohortes encimadas; el benchmark es lo mismo con "
            "todos los elegibles.</p>"
            + fig(gs.riqueza, r, "historia", False, pie="Un dólar en cada tercil del yield contra su propia "
                  "historia —el método que funcionó con O, NNN y WPC— y en el universo completo.")
            + fig(gs.riqueza, r, "ddm", False, pie="Lo mismo con el DDM entre emisores.")
            + _tabla_vista(g.drop(columns="variante"),
                           ["Señal", "Grupo", "Retorno anual", "Contra todos", "t Newey-West", "Volatilidad",
                            "Caída máxima"], [None, None, _p1, _p1, _t, _p1, _p0])
            + "<p class='chico gris'>La t es de Newey-West con rezago 12 por las cohortes encimadas; arriba de 2 "
              "es difícil de atribuir al azar.</p>")


def _predicen(r: ResultadoSeleccion, fig: Figuras) -> str:
    return ("<h2 class='salto'>¿Predicen?</h2>"
            + fig(gs.correlacion_anual, r, pie="Correlación de rangos de cada mes entre la señal y el retorno de "
                  "los 12 meses siguientes, promedio de cada año.")
            + _tabla_vista(vs.correlacion(r), ["Señal", "Meses", "Correlación promedio", "Meses positivos",
                                               "t Newey-West"], [None, num, _rho, _p0, _t])
            + fig(gs.sorteos, r, "historia", pie="Barato menos caro de 200 repartos al azar y dónde cae el yield "
                  "contra su propia historia. El reparto al azar cambia cada mes y queda más diversificado que "
                  "una señal persistente: este control es débil y la t de Newey-West pesa más."))


def _trampas(r: ResultadoSeleccion, fig: Figuras) -> str:
    t = vs.trampas(r)
    return ("<h2 class='salto'>¿Cuántos baratos eran trampa?</h2>"
            "<p>Trampa: recortó su dividendo en los 12 meses siguientes (menos de 90% de lo que pagó en los 12 "
            "anteriores) o se desplomó (−30% o peor en un año). La variante «con dividendo intacto» quita a los "
            "que ya habían recortado en los 12 meses previos.</p>"
            + fig(gs.trampas, r, False, pie="Qué fracción de cada grupo recortó su dividendo en los 12 meses "
                  "siguientes.")
            + _tabla_vista(t, ["Señal", "Variante", "Grupo", "Observaciones", "Recortó", "Se desplomó",
                               "Retorno 12 meses (mediana)"], [None, None, None, num, _p1, _p1, _p1]))


def _aportando(r: ResultadoSeleccion) -> str:
    return ("<h2 class='salto'>Aportando cada mes y a plazos largos</h2>"
            "<p>1,000 dólares al mes repartidos entre los baratos de cada señal, sin vender nunca, contra lo "
            "mismo repartido entre todos los elegibles. TIR money-weighted (P9), antes de impuestos.</p>"
            + _tabla_vista(vs.aportacion(r), ["Cartera", "TIR", "Contra todos (pb/año)", "Aportado", "Valor final"],
                           [None, _p2, _pb, _usd, _usd])
            + "<div class='bloque'><h3>La mediana a 1, 3 y 5 años (exploratorio)</h3>"
            + _tabla_vista(vs.plazos(r), ["Señal", "Años", "Barato", "Medio", "Caro", "Todos", "Barato contra todos"],
                           [None, num, _p1, _p1, _p1, _p1, _p1])
            + "<p class='chico gris'>No estaba en el diseño. Mediana del retorno anualizado de cada REIT de cada "
              "tercil. A plazos largos es donde más pesa el sesgo: los baratos que no aguantaron cinco años no "
              "están.</p></div>")


def _aguanta(r: ResultadoSeleccion) -> str:
    ref = r.referencia
    vnq = (f"<p>Desde {ref['desde']:%m-%Y}, el universo de pesos iguales rindió {pct(ref['universo'])} al año y "
           f"VNQ —que sí tuvo a los que desaparecieron— {pct(ref['vnq'])}.</p>") if ref.get("desde") is not None else ""
    return ("<h2 class='salto'>¿Aguanta?</h2>"
            "<div class='bloque'><h3>Contra un índice que sí tuvo a los que desaparecieron</h3>" + vnq + "</div>"
            "<div class='bloque'><h3>En cada mitad del periodo</h3>"
            + _tabla_vista(vs.mitades(r), ["Señal", "Mitad", "Desde", "Hasta", "Correlación", "Barato contra todos",
                                           "Barato menos caro"], [None, None, None, None, _rho, _p1, _p1])
            + "</div><div class='bloque'><h3>Dentro de cada sector</h3>"
            + _tabla_vista(vs.sectores(r), ["Industria", "Emisores", "Correlación historia", "Correlación DDM",
                                            "Meses"], [None, num, _rho, _rho, num])
            + "</div><div class='bloque'><h3>Sin los dividendos especiales</h3>"
            + _tabla_vista(vs.robustez(r), ["Señal", "Muestra", "Barato contra todos", "Barato menos caro",
                                            "Correlación", "Barato que recortó", "Todos", "Caro"],
                           [None, None, _p1, _p1, _rho, _p1, _p1, _p1])
            + "<p class='chico gris'>Yahoo no marca los dividendos especiales: aquí se quitan los pagos de más del "
              "doble de la mediana de los cuatro anteriores del mismo emisor y se repite todo.</p></div>")


def _hoy(r: ResultadoSeleccion) -> str:
    h = vs.hoy(r).sort_values("descuento_ddm", ascending=False, na_position="last")
    h = h.assign(industria=h["industria"].str.replace("REIT - ", "", regex=False))
    return (f"<h2 class='salto'>Qué dice hoy cada REIT ({r.hasta:%m-%Y})</h2>"
            "<p>Los elegibles del último mes, del mayor descuento DDM al menor. Leer con lo que se encontró: en "
            "el universo, «barato» no es una recomendación; un yield alto muchas veces es el aviso de un recorte. "
            "Sin DDM quien no pagaba dividendo hace cinco años —los hoteles lo suspendieron en 2020—: no hay "
            "crecimiento que medir.</p>"
            + "<div class='chico'>"
            + _tabla_vista(h.drop(columns="nombre"),
                           ["Ticker", "Industria", "Precio", "Yield", "Percentil historia", "Razón contra sector",
                            "Descuento DDM", "Historia", "Sector", "DDM", "Recortó en 12 meses"],
                           [None, None, lambda v: f"${v:,.2f}", _p1, _p0, lambda v: "—" if pd.isna(v) else f"{v:.2f}x",
                            _p0, None, None, None, None])
            + "</div>")


def _md(texto: str) -> str:
    """El docstring del diseño (markdown sencillo) como HTML del PDF."""
    def enlinea(s: str) -> str:
        s = _e(s)
        s = re.sub(r"``(.+?)``", r"<span class='cifra'>\1</span>", s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        return re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)

    vineta = re.compile(r"^\s*(?:\* |\d+\. )")
    partes = []
    for bloque in re.split(r"\n\s*\n", texto.strip()):
        lineas = bloque.splitlines()
        if len(lineas) >= 2 and set(lineas[1].strip()) == {"-"}:
            partes.append(f"<h3>{enlinea(lineas[0].strip())}</h3>")
            bloque = "\n".join(lineas[2:])
            if not bloque.strip():
                continue
        items = re.split(r"\n(?=\s*(?:\* |\d+\. ))", bloque)
        if re.match(r"\s*(?:\* |\d+\. )", items[0]):
            etiqueta = "ol" if re.match(r"\s*\d+\. ", items[0]) else "ul"
            lis = "".join(f"<li>{enlinea(' '.join(vineta.sub('', i).split()))}</li>" for i in items)
            partes.append(f"<{etiqueta}>{lis}</{etiqueta}>")
        else:
            partes.append(f"<p>{enlinea(' '.join(bloque.split()))}</p>")
    return "".join(partes)


def _diseno() -> str:
    return "<h2 class='salto'>Diseño y datos</h2><div class='chico'>" + _md(seleccion.__doc__ or "") + "</div>"


def html_de_seleccion(r: ResultadoSeleccion, *, fuentes_css: str | None = None) -> str:
    import plotly.offline

    fig = Figuras()
    cuerpo = (_portada(r) + _conclusiones(r) + _senales(r, fig) + _predicen(r, fig) + _trampas(r, fig)
              + _aportando(r) + _aguanta(r) + _hoy(r) + _diseno())
    css = _css(css_de_fuentes() if fuentes_css is None else fuentes_css)
    return (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        f"<title>{_e(TITULO)}</title>"
        f"<style>{css}</style>"
        f"<script>{plotly.offline.get_plotlyjs()}</script></head>"
        f"<body>{cuerpo}{fig.script()}</body></html>"
    )


def generar_pdf(r: ResultadoSeleccion, destino: Path) -> Path:
    from playwright.sync_api import sync_playwright

    documento = html_de_seleccion(r)
    destino.parent.mkdir(parents=True, exist_ok=True)
    pie = (
        "<div style='width:100%;font-family:monospace;font-size:7px;color:#6B6B66;"
        "padding:0 15mm;display:flex;justify-content:space-between'>"
        f"<span>SPREAD TRADING CLUB · {html.escape(TITULO)}</span>"
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
