"""El estudio en PDF: la misma sustancia que la página, para leer en papel.

Cómo se arma
------------
Un HTML con las MISMAS figuras de ``src.estudio.graficas`` —en su tema claro— y
Chromium lo imprime a PDF. No hay un segundo juego de gráficas para el papel: si
lo hubiera, tarde o temprano el impreso tendría una mediana que la pantalla no, o
al revés, y el lector que compara los dos encontraría dos estudios.

Las figuras se dibujan con plotly.js dentro de la página, así que salen VECTORIALES:
se pueden ampliar sin pixelar. Las tipografías de marca se incrustan en el HTML
para que el PDF no dependa de la red al abrirse ni al generarse dos veces.

Requiere Chromium vía Playwright. En Streamlit Cloud no hay navegador, así que el
PDF se genera con ``scripts/estudio.py pdf TICKER`` y se versiona; la página lo
ofrece como descarga tal cual.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import json
import re
from pathlib import Path

import pandas as pd
import requests

from src.config import DIR_CACHE
from src.estudio import graficas as g
from src.estudio import historia as hist
from src.estudio import vistas

TINTA = g.CLARO.texto
ACENTO = g.CLARO.principal
GRIS = g.CLARO.texto_2
PAPEL = g.CLARO.fondo
LINEA = g.CLARO.rejilla

FUENTES_GOOGLE = (
    "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&"
    "family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;600&display=swap"
)
# Google entrega woff2 solo si el cliente dice ser un navegador moderno; con el
# agente de requests responde TTF en otra estructura. El UA no suplanta a nadie en
# particular: es la condición del servicio para elegir formato.
UA_NAVEGADOR = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


# --------------------------------------------------------------------------------------
# Tipografía incrustada
# --------------------------------------------------------------------------------------


def css_de_fuentes(dir_cache: Path | None = None) -> str:
    """@font-face con las fuentes de marca en base64, o cadena vacía si no hay red.

    Se cachea en disco: generar el PDF dos veces no vuelve a pedir nada. Sin red
    ni caché, el PDF sale con las fuentes del sistema, que es peor pero no es un
    error: el contenido es el mismo.
    """
    destino = (dir_cache or DIR_CACHE) / "fuentes"
    cache = destino / "marca.css"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    try:
        css = requests.get(FUENTES_GOOGLE, headers={"User-Agent": UA_NAVEGADOR}, timeout=20).text
        def incrustar(m: re.Match) -> str:
            datos = requests.get(m.group(1), timeout=30).content
            return f"url(data:font/woff2;base64,{base64.b64encode(datos).decode()}) format('woff2')"
        # Solo los subconjuntos latinos: el español no necesita cirílico ni vietnamita.
        bloques = re.findall(r"/\* ([a-z\-]+) \*/\s*(@font-face \{.*?\})", css, flags=re.S)
        latinos = [b for sub, b in bloques if sub in ("latin", "latin-ext")]
        salida = "\n".join(re.sub(r"url\((https://[^)]+)\) format\('woff2'\)", incrustar, b) for b in latinos)
    except requests.RequestException:
        return ""
    destino.mkdir(parents=True, exist_ok=True)
    cache.write_text(salida, encoding="utf-8")
    return salida


# --------------------------------------------------------------------------------------
# Formato
# --------------------------------------------------------------------------------------


def _e(texto) -> str:
    return html.escape(str(texto), quote=False)


def pct(v, d: int = 1) -> str:
    return "—" if v is None or pd.isna(v) else f"{v * 100:,.{d}f}%"


def veces(v, d: int = 1) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.{d}f}x"


def usd(v, d: int = 2) -> str:
    return "—" if v is None or pd.isna(v) else f"${v:,.{d}f}"


def num(v, d: int = 0) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.{d}f}"


def tabla(filas: list[list[str]], encabezado: list[str], *, alinear: str | None = None, clase: str = "") -> str:
    """Tabla HTML. ``alinear`` = una letra por columna: 'l' texto, 'r' cifra."""
    alinear = alinear or "l" + "r" * (len(encabezado) - 1)
    th = "".join(f"<th class='{a}'>{_e(h)}</th>" for h, a in zip(encabezado, alinear, strict=True))
    cuerpo = "".join(
        "<tr>" + "".join(f"<td class='{a}'>{c}</td>" for c, a in zip(f, alinear, strict=True)) + "</tr>"
        for f in filas
    )
    return f"<table class='{clase}'><thead><tr>{th}</tr></thead><tbody>{cuerpo}</tbody></table>"


GLIFO = {"favorable": ("▲", "#0E9F66"), "desfavorable": ("▼", "#C62F38"), "neutral": ("◆", ACENTO)}


# --------------------------------------------------------------------------------------
# Figuras
# --------------------------------------------------------------------------------------


class Figuras:
    """Junta las figuras del documento y las entrega como divs para plotly.js."""

    def __init__(self, e) -> None:
        self.e = e
        self.specs: list[tuple[str, str]] = []

    def __call__(self, nombre: str, *, pie: str = "") -> str:
        fig = g.FIGURAS[nombre](self.e, g.CLARO)
        # En papel, un 12% más bajas: caben dos por página sin perder lectura.
        fig.update_layout(width=700, height=int((fig.layout.height or 360) * 0.88), hovermode=False)
        if nombre == "eras":
            # La leyenda arriba se parte en tres renglones al ancho de la hoja y tapa la
            # primera era; abajo no tapa nada.
            fig.update_layout(legend={"orientation": "h", "y": -0.12, "x": 0},
                              margin={"t": 10, "b": 90})
        ident = f"fig_{len(self.specs)}"
        self.specs.append((ident, fig.to_json()))
        pie_html = f"<div class='pie'>{_e(pie)}</div>" if pie else ""
        return f"<figure><div id='{ident}' class='grafica'></div>{pie_html}</figure>"

    def script(self) -> str:
        llamadas = "\n".join(
            f"pend.push(Plotly.newPlot('{i}', (f={s}).data, f.layout, "
            "{staticPlot:true, displayModeBar:false}));"
            for i, s in self.specs
        )
        return (
            "<script>var f; var pend=[];\n" + llamadas +
            "\nPromise.all(pend).then(()=>{document.body.dataset.listo='1';});</script>"
        )


# --------------------------------------------------------------------------------------
# Documento
# --------------------------------------------------------------------------------------


def _css(fuentes: str) -> str:
    return fuentes + f"""
    @page {{ size: Letter; margin: 16mm 15mm 18mm 15mm; background: {PAPEL}; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: Inter, system-ui, sans-serif; color: {TINTA}; background: {PAPEL};
           font-size: 10.2pt; line-height: 1.45; margin: 0; }}
    h1, h2, h3 {{ font-family: 'Space Grotesk', Inter, sans-serif; letter-spacing: -0.01em;
                 line-height: 1.15; }}
    h1 {{ font-size: 30pt; margin: 0 0 6pt; }}
    h2 {{ font-size: 17pt; margin: 22pt 0 8pt; padding-top: 6pt; border-top: 1.5pt solid {TINTA};
          break-after: avoid; }}
    h3 {{ font-size: 12pt; margin: 14pt 0 4pt; break-after: avoid; }}
    p {{ margin: 0 0 7pt; }}
    .rotulo {{ font-family: 'JetBrains Mono', monospace; font-size: 7.5pt; font-weight: 600;
              letter-spacing: 0.16em; text-transform: uppercase; color: {ACENTO}; }}
    .gris {{ color: {GRIS}; }}
    .cifra, td.r {{ font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; }}
    .portada {{ min-height: 235mm; display: flex; flex-direction: column; break-after: page; }}
    .portada .marca {{ font-family: 'JetBrains Mono', monospace; font-size: 8.5pt; font-weight: 600;
                      letter-spacing: 0.18em; }}
    .portada .marca span {{ color: {GRIS}; }}
    .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8pt; margin: 14pt 0; }}
    .kpi {{ border-top: 1pt solid {LINEA}; padding-top: 6pt; }}
    .kpi .v {{ font-family: 'JetBrains Mono', monospace; font-size: 17pt; font-weight: 600; }}
    .kpi .l {{ font-size: 7.8pt; color: {GRIS}; }}
    .conclusion {{ border-left: 2.5pt solid {LINEA}; padding: 4pt 0 4pt 10pt; margin: 0 0 10pt;
                  break-inside: avoid; }}
    .conclusion b {{ font-family: 'Space Grotesk', Inter, sans-serif; font-size: 11pt; }}
    figure {{ margin: 6pt 0 12pt; break-inside: avoid; }}
    .grafica {{ width: 700px; max-width: 100%; }}
    .pie {{ font-size: 8pt; color: {GRIS}; margin-top: 2pt; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 8.4pt; margin: 4pt 0 12pt;
            break-inside: avoid; }}
    th {{ font-weight: 600; color: {GRIS}; border-bottom: 1pt solid {TINTA}; padding: 3pt 4pt;
         text-align: left; }}
    th.r {{ text-align: right; }}
    td {{ padding: 2.6pt 4pt; border-bottom: 0.5pt solid {LINEA}; vertical-align: top; }}
    td.r {{ text-align: right; white-space: nowrap; }}
    .hito {{ break-inside: avoid; margin: 0 0 6pt; }}
    .hito .f {{ font-family: 'JetBrains Mono', monospace; font-size: 8pt; color: {GRIS}; }}
    .hito .fuente {{ font-size: 7.6pt; color: {GRIS}; }}
    .caja {{ border: 1pt solid {LINEA}; padding: 8pt 10pt; margin: 6pt 0 12pt; break-inside: avoid; }}
    .aviso {{ border-left: 2.5pt solid {ACENTO}; padding: 6pt 10pt; background: #EFEBE3;
             margin: 6pt 0 12pt; break-inside: avoid; }}
    .salto {{ break-before: page; }}
    .bloque {{ break-inside: avoid; }}
    .dos {{ columns: 2; column-gap: 18pt; }}
    .chico {{ font-size: 8.4pt; }}
    a {{ color: {ACENTO}; text-decoration: none; }}
    """


def _portada(e) -> str:
    n = e.narrativa
    h = e.hoy
    t0 = e.tabla.index[0]
    rt_mxn = e.tabla["rt_mxn"].dropna()
    anios_mxn = (rt_mxn.index[-1] - rt_mxn.index[0]).days / 365.25
    mxn = (rt_mxn.iloc[-1] / rt_mxn.iloc[0]) ** (1 / anios_mxn) - 1
    kpis = [
        (pct(e.total.retorno_total), f"retorno anual en dólares desde {t0:%Y}, dividendos reinvertidos"),
        (pct(mxn), "lo mismo, en pesos"),
        (pct(h.yield_actual, 2), "dividendo al precio de hoy"),
        (veces(h.p_ffo), f"P/FFO hoy · mediana histórica {veces(e.tabla['p_ffo'].median())}"),
    ]
    kpi_html = "".join(f"<div class='kpi'><div class='v'>{v}</div><div class='l'>{_e(leyenda)}</div></div>" for v, leyenda in kpis)
    return f"""
    <section class='portada'>
      <div class='marca'>SPREAD <span>TRADING CLUB</span></div>
      <div style='flex-grow:1;display:flex;flex-direction:column;justify-content:center'>
        <div class='rotulo'>Estudio de largo plazo · {_e(e.ticker)}</div>
        <h1>{_e(n.nombre if n else e.ticker)}</h1>
        <p style='font-size:12.5pt;max-width:150mm'>Qué le ha pasado al REIT desde que cotiza,
        de dónde salió lo que rindió, cuándo hubiera convenido entrar y si lo que paga hoy
        compensa el riesgo.</p>
        <div class='kpis'>{kpi_html}</div>
        <p class='gris chico' style='max-width:150mm'>{_e(n.perfil) if n else ''}</p>
      </div>
      <div class='gris chico'>Datos al {h.fecha:%d-%m-%Y} · generado el {dt.date.today():%d-%m-%Y}.
      Herramienta de análisis, no asesoría de inversión. Los cálculos fiscales son indicativos.</div>
    </section>"""


def _conclusiones(e) -> str:
    bloques = []
    for c in e.conclusiones:
        glifo, color = GLIFO.get(c.tono, GLIFO["neutral"])
        bloques.append(
            f"<div class='conclusion' style='border-left-color:{color}'>"
            f"<b><span style='color:{color}'>{glifo}</span> {_e(c.titulo)}</b>"
            f"<p>{_e(c.texto)}</p></div>"
        )
    return "<h2>Lo que dice el estudio</h2>" + "".join(bloques)


def _historia(e) -> str:
    n = e.narrativa
    if n is None:
        return ""
    hitos = sorted([*n.hitos, *hist.INDUSTRIA], key=lambda h: h.fecha)
    hitos = [h for h in hitos if h.fecha <= e.asof]
    items = []
    for h in hitos:
        marca = " · <i>industria</i>" if h.categoria == "industria" else ""
        fuente = f"<a href='{_e(h.url)}'>{_e(h.fuente)}</a>" if h.url else _e(h.fuente)
        items.append(
            f"<div class='hito'><span class='f'>{_e(h.fecha_texto)}</span>{marca}<br>"
            f"<b>{_e(h.titulo)}.</b> {_e(h.detalle)} <span class='fuente'>— {fuente}</span></div>"
        )
    return (
        "<h2 class='salto'>La historia</h2>"
        f"<p>{_e(n.modelo_de_negocio)}</p>"
        "<h3>Línea de tiempo</h3>"
        f"<div class='dos chico'>{''.join(items)}</div>"
    )


def _negocio(e, fig) -> str:
    si = e.spread_inversion
    filas = [[str(a), pct(r.cap_rate), pct(r.costo_acciones), _e(r.medida),
              pct(r.get("costo_deuda")), pct(r.get("peso_deuda"), 0), pct(r.get("costo_ponderado")),
              f"{r.spread_contra_acciones * 1e4:+,.0f}",
              "—" if pd.isna(r.get("spread_contra_ponderado")) else f"{r.spread_contra_ponderado * 1e4:+,.0f}",
              usd(r.inversion / 1e6, 0)]
             for a, r in si.iterrows()] if not si.empty else []
    return (
        "<h2 class='salto'>El negocio en el tiempo</h2>"
        "<h3>Flujo y dividendo por acción</h3>"
        "<p>Todo en acciones de hoy: lo anterior al split de 2005 va dividido entre dos. FFO y "
        "AFFO son los que publicó el emisor —10-K y comunicados antes de 2019, 8-K después—.</p>"
        + fig("por_accion", pie="Fuente: 10-K y 8-K de la SEC; dividendos del proveedor de mercado, corregidos contra los 10-K.")
        + "<div class='bloque'><h3>El negocio creció mucho más que la acción</h3>"
        "<p>O crece emitiendo acciones para comprar inmuebles. Lo que le importa al accionista no "
        "es cuánto crece la empresa sino cuánto crece su parte.</p>"
        + fig("escala") + "</div>"
        + "<div class='bloque'><h3>El motor: comprar por encima de lo que cuesta el capital</h3>"
        "<p>Si O compra a un yield mayor que el que rinde su propia acción, cada compra con "
        "acciones suma por acción; si compra por debajo, resta aunque la empresa crezca.</p>"
        + fig("spread_inversion", pie="Yield de compra: el que reporta el emisor. Costo de las acciones: AFFO yield promedio del año (FFO antes de 2010). Costo ponderado: acciones y deuda por su peso de mercado; la deuda a su costo promedio en libros.")
        + tabla(filas, ["Año", "Compra a", "Costo acciones", "Medida", "Costo deuda", "Peso deuda",
                        "Costo ponderado", "Margen vs acciones (pb)", "Margen vs ponderado (pb)", "Invertido (MM USD)"],
                alinear="lrrlrrrrrr") + "</div>"
        + "<div class='bloque'><h3>Apalancamiento en libros</h3>"
        + fig("apalancamiento", pie="Deuda ÷ activos totales en libros. La deuda neta ÷ EBITDAre se "
              "mide desde 2015: antes, las ventas de inmuebles iban a operaciones discontinuadas y el "
              "EBITDAre derivado de XBRL no es confiable. El emisor reporta 5.4x pro forma al cierre de 2025.")
        + "</div>"
    )


def _valuacion(e, fig) -> str:
    return (
        "<h2>Qué tan caro ha estado</h2>"
        "<p><b>Contra su propia historia.</b> Precio ÷ FFO por acción conocido ese día: cada fecha "
        "usa solo lo que se había publicado entonces. La franja es el 60% central de la historia; "
        "la línea punteada, la mediana.</p>"
        + fig("multiplo")
        + "<div class='bloque'><p><b>Contra el bono.</b> Un REIT de arrendamiento neto compite con "
        "el Treasury por el mismo ahorrador. Cuando el bono paga más, al REIT le exigen más yield y "
        "su precio baja.</p>" + fig("yield_bono") + "</div>" + fig("spread")
    )


def _retorno(e, fig) -> str:
    filas = [[_e(d.nombre), f"{d.inicio:%Y}–{d.fin:%Y}", num(d.anios, 1), pct(d.retorno_total),
              pct(d.ingreso), pct(d.crecimiento_dividendo), pct(d.revaluacion), pct(d.escision),
              f"{pct(d.yield_inicio)} → {pct(d.yield_fin)}",
              "—" if d.p_ffo_inicio is None else f"{veces(d.p_ffo_inicio)} → {veces(d.p_ffo_fin)}"]
             for d in [*e.eras, e.total]]
    narrativa = ""
    if e.narrativa:
        narrativa = "".join(
            f"<div class='hito'><b>{_e(era.nombre)}</b> <span class='f'>{era.inicio:%Y}–{(era.fin or e.asof):%Y}</span>"
            f"<br>{_e(era.resumen)}</div>"
            for era in e.narrativa.eras if pd.Timestamp(era.inicio) < e.tabla.index[-1]
        )
    return (
        "<h2 class='salto'>De dónde salió el retorno</h2>"
        "<p>Un dólar invertido el día del listado, reinvirtiendo cada dividendo (escala logarítmica).</p>"
        + fig("retorno_total", pie="Incluye la escisión de Orion (2021) como distribución en especie reinvertida. Validado contra el índice ajustado del proveedor: desviación máxima de "
              + pct(e.serie.validacion_rt, 2) + " en toda la historia." if e.serie.validacion_rt is not None else "")
        + "<div class='bloque'><p><b>Negocio contra mercado.</b> El precio es el dividendo ÷ el yield, así que el retorno "
        "se reparte exacto —sin residuo— en el dividendo cobrado, el crecimiento del dividendo por "
        "acción y el cambio de valuación: <span class='cifra'>(1 + RT) = (1 + ingreso) × (1 + "
        "crecimiento) × (1 + revaluación)</span>. Las dos primeras las produce el negocio; la "
        "tercera, el mercado.</p>"
        + fig("eras") + "</div>"
        + tabla(filas, ["Era", "Periodo", "Años", "Retorno anual", "Dividendo cobrado", "Crecimiento div.",
                        "Revaluación", "Escisión", "Yield", "P/FFO"], alinear="llrrrrrrrr")
        + "<h3>Qué pasó en cada era</h3>" + narrativa
    )


def _entradas(e, fig) -> str:
    ent = e.entradas
    q = ent.quintiles
    filas_q = [[_e(i), f"{veces(r.desde)} – {veces(r.hasta)}", pct(r.rt_5a_mediana), pct(r.rt_5a_peor),
                pct(r.rt_5a_mejor), num(r.meses)] for i, r in q.iterrows()] if not q.empty else []

    def momentos(df: pd.DataFrame) -> str:
        filas = [[g.mes(f), usd(r.precio), veces(r.p_ffo), pct(r.yield_ttm), pct(r.rt_5a), pct(r.rt_10a),
                  pct(r.rt_a_hoy_usd), pct(r.yield_sobre_costo)] for f, r in df.iterrows()]
        return tabla(filas, ["Compra", "Precio", "P/FFO", "Yield", "A 5 años", "A 10 años", "Hasta hoy",
                             "Yield sobre costo"])

    cortes = vistas.cortes_de_compra(e)
    yoc = [[g.mes(f), usd(ent.tabla.loc[f, "precio"]), veces(ent.tabla.loc[f, "p_ffo"]),
            pct(ent.tabla.loc[f, "rt_a_hoy_usd"]), pct(ent.tabla.loc[f, "rt_a_hoy_mxn"]),
            veces(ent.tabla.loc[f, "multiplo_a_hoy"]), pct(ent.tabla.loc[f, "yield_sobre_costo"])]
           for f in cortes]
    corr = " · ".join(f"{_e(k)}: {v:+.2f}" for k, v in ent.correlaciones.items())
    return (
        "<h2 class='salto'>¿Cuándo hubiera convenido entrar?</h2>"
        "<p>Cada punto es un fin de mes: qué tan caro estaba O ese día —con el FFO que se "
        "conocía— y cuánto rindió al año en los cinco años siguientes. Los rombos son la mediana "
        "de cada quinto de la historia.</p>"
        + fig("entradas")
        + tabla(filas_q, ["Quinto de la historia", "P/FFO al comprar", "Mediana a 5 años", "Peor", "Mejor", "Meses"],
                alinear="lrrrrr")
        + f"<div class='aviso'><b>Por qué esto no es una regla de compra.</b> {_e(ent.veredicto_p7)}"
          f"<br><span class='chico gris'>Correlaciones de rangos (Spearman): {corr}</span></div>"
        + "<div class='bloque'><h3>Los cinco mejores momentos</h3><p class='chico gris'>Por retorno "
          "a 5 años, separados al menos 18 meses para no contar el mismo episodio varias veces.</p>"
        + momentos(ent.mejores) + "</div>"
        + "<div class='bloque'><h3>Los cinco peores</h3>" + momentos(ent.peores) + "</div>"
        + "<div class='bloque'><h3>Si hubieras comprado en cualquier mes</h3><p>Retorno anual desde "
          "la compra hasta hoy. El «yield sobre costo» es el dividendo de hoy entre lo que pagaste: "
          "cuánto te paga HOY lo que compraste entonces.</p>"
        + fig("retorno_a_hoy") + "</div>"
        + tabla(yoc, ["Compra", "Precio", "P/FFO", "Anual hasta hoy (USD)", "(MXN)", "Veces lo invertido",
                      "Yield sobre costo"])
    )


def _hoy(e, fig) -> str:
    h = e.hoy
    kpis = [
        (pct(h.yield_actual, 2), f"dividendo (mensualidad × 12 = {usd(h.dividendo_anualizado, 3)})"),
        (pct(h.affo_yield, 2), f"AFFO yield · P/AFFO {veces(h.p_affo)}"),
        (pct(h.spread, 2), f"spread vs Treasury · percentil {pct(h.percentil_spread, 0)}"),
        (pct(h.udibono_real, 2), "Udibono 10 años, real"),
    ]
    kpi_html = "".join(f"<div class='kpi'><div class='v'>{v}</div><div class='l'>{_e(leyenda)}</div></div>" for v, leyenda in kpis)
    filas = [[_e(s.nombre), pct(s.crecimiento), pct(s.retorno_usd), pct(s.retorno_con_reversion),
              pct(s.retorno_reversion_multiplo), pct(s.real_neto), pct(s.real_neto_reversion_spread),
              pct(s.real_neto_reversion_multiplo)] for s in h.escenarios]
    return (
        "<h2 class='salto'>¿Paga buen retorno hoy?</h2>"
        f"<div class='kpis'>{kpi_html}</div>"
        + fig("escenarios", pie="Retorno real anual, neto de impuestos, con el crecimiento del AFFO por acción de los últimos diez años.")
        + tabla(filas, ["Crecimiento supuesto", "g", "USD, múltiplo constante", "USD, vuelve el spread",
                        "USD, vuelve el P/FFO", "Real neto", "Real neto, spread", "Real neto, P/FFO"],
                alinear="lrrrrrrr")
        + "".join(f"<p class='chico gris'>{_e(s)}</p>" for s in h.supuestos)
    )


def _riesgos(e) -> str:
    if e.narrativa is None:
        return ""
    return "<h2>Riesgos</h2>" + "".join(
        f"<div class='caja'><b>{_e(r.titulo)}.</b> {_e(r.texto)}</div>" for r in e.narrativa.riesgos
    )


def _metodologia(e) -> str:
    man = e.historia_mercado.manifiesto
    v = man.get("validacion", {})
    anclas = "".join(
        f"<li>Cierre NYSE {a['fecha']}: real {usd(a['real'])}, reconstruido {usd(a['reconstruido'])} "
        f"({a['error']:+.3%}).</li>" for a in v.get("anclas", [])
    )
    correcciones = "".join(f"<li>{_e(c)}</li>" for c in man.get("correcciones_de_dividendos", []))
    d = e.diagnostico_ffo.tabla
    filas_d = [[str(a), usd(r.derivado), usd(r.reportado), pct(r.error)] for a, r in d.iterrows()]
    fuentes = ""
    if e.narrativa:
        fuentes = "".join(f"<li><b>{_e(t)}.</b> {_e(x)}</li>" for t, x in e.narrativa.fuentes_extra)
    avisos = "".join(f"<li>{_e(a)}</li>" for a in e.avisos)
    return (
        "<h2 class='salto'>Metodología, validaciones y fuentes</h2>"
        "<h3>Precio y dividendos desde el listado</h3>"
        f"<p>{num(man['precios']['n'])} cierres desde {man['precios']['desde']}. El proveedor entrega el "
        "cierre ajustado por el split de 2005 y —como si fuera split— por la escisión de Orion de "
        "2021; aquí se desajusta para obtener el precio al que de verdad cotizó (P2). Cada evento de "
        "capital está en un catálogo verificado: un evento que el proveedor reporte y no esté "
        "catalogado detiene la descarga.</p>"
        f"<ul class='chico'><li>Contra el precio crudo del proveedor diario: {num(v.get('traslape_n'))} "
        f"días de traslape, error máximo {pct(v.get('traslape_error_max'), 4)}.</li>{anclas}</ul>"
        "<h3>Dividendos corregidos contra el reporte del emisor</h3>"
        f"<ul class='chico'>{correcciones}</ul>"
        "<p class='chico'>La suma anual cuadra con los 10-K dentro de 0.8% de 1997 a 2007. El dividendo "
        "anualizado del último comunicado (3.252 dólares) coincide con la serie.</p>"
        "<h3>Por qué el FFO no se deriva de la contabilidad</h3>"
        "<p class='chico'>La fórmula de Nareit aplicada a XBRL cuadra con lo reportado en los años "
        "recientes y falla por más de 15% antes de 2015, cuando las ventas de inmuebles iban a "
        "operaciones discontinuadas. El estudio usa solo cifras reportadas por el emisor.</p>"
        + tabla(filas_d, ["Año", "FFO por acción derivado", "Reportado", "Error"], clase="chico")
        + "<h3>Lo que se sabía en cada fecha</h3>"
        "<p class='chico'>Toda señal de valuación usa solo lo publicado a esa fecha (P1): el FFO de un "
        "trimestre entra al cálculo el día en que se publicó, no el día en que cerró el trimestre.</p>"
        f"<ul class='chico'>{avisos}</ul>"
        "<h3>Fuentes</h3>"
        f"<ul class='chico'>{fuentes}</ul>"
        "<p class='chico gris'>Esto es una herramienta de análisis, no asesoría de inversión. Toda "
        "métrica de desempeño va acompañada de su conteo de apuestas efectivas; cuando las "
        "observaciones son insuficientes el veredicto es INCONCLUSO. Los cálculos fiscales son "
        "indicativos: confirma con tu casa de bolsa y con un contador.</p>"
    )


def html_del_estudio(e, *, fuentes_css: str | None = None) -> str:
    import plotly.offline

    fig = Figuras(e)
    cuerpo = (
        _portada(e) + _conclusiones(e) + _historia(e) + _negocio(e, fig) + _valuacion(e, fig)
        + _retorno(e, fig) + _entradas(e, fig) + _hoy(e, fig) + _riesgos(e) + _metodologia(e)
    )
    css = _css(css_de_fuentes() if fuentes_css is None else fuentes_css)
    return (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        f"<title>Estudio de largo plazo · {_e(e.ticker)}</title>"
        f"<style>{css}</style>"
        f"<script>{plotly.offline.get_plotlyjs()}</script></head>"
        f"<body>{cuerpo}{fig.script()}</body></html>"
    )


def _lanzar_chromium(p):
    """El Chromium de Playwright, o uno ya instalado si la versión no coincide.

    La biblioteca de Python espera la compilación exacta de navegador con la que se
    publicó; si el sistema trae otra, ``launch()`` falla aunque haya un Chromium
    perfectamente usable. En ese caso se usa el que haya —``REIT_CHROMIUM`` manda—
    en vez de descargar otro navegador.
    """
    import glob
    import os

    candidatos = [os.environ.get("REIT_CHROMIUM"), "/opt/pw-browsers/chromium",
                  *sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"), reverse=True)]
    try:
        return p.chromium.launch()
    except Exception as primero:  # noqa: BLE001 — se reintenta con un ejecutable explícito
        for ruta in candidatos:
            if ruta and Path(ruta).is_file():
                return p.chromium.launch(executable_path=ruta)
        raise primero


def generar_pdf(e, destino: Path, *, html_destino: Path | None = None) -> Path:
    """Imprime el estudio a PDF con Chromium. Devuelve la ruta del PDF."""
    from playwright.sync_api import sync_playwright

    documento = html_del_estudio(e)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if html_destino is not None:
        html_destino.write_text(documento, encoding="utf-8")
    pie = (
        "<div style='width:100%;font-family:monospace;font-size:7px;color:#6B6B66;"
        "padding:0 15mm;display:flex;justify-content:space-between'>"
        f"<span>SPREAD TRADING CLUB · Estudio de largo plazo · {html.escape(e.ticker)}</span>"
        "<span><span class='pageNumber'></span> / <span class='totalPages'></span></span></div>"
    )
    with sync_playwright() as p:
        navegador = _lanzar_chromium(p)
        pagina = navegador.new_page()
        pagina.set_content(documento, wait_until="load")
        pagina.wait_for_selector("body[data-listo='1']", timeout=120_000)
        pagina.pdf(
            path=str(destino), print_background=True, prefer_css_page_size=True,
            display_header_footer=True, header_template="<div></div>", footer_template=pie,
        )
        navegador.close()
    return destino


def resumen_json(e) -> str:
    """Las cifras clave en JSON, para comparar dos generaciones del PDF."""
    return json.dumps({
        "asof": str(e.asof), "retorno_anual": e.total.retorno_total,
        "yield": e.hoy.yield_actual, "p_ffo": e.hoy.p_ffo, "spread": e.hoy.spread,
    }, ensure_ascii=False, indent=2)
