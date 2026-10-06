"""La investigación sobre cuándo entrar a los REITs, en PDF.

Mismo papel, tipografía y tablas que los otros estudios (``pdf_estudio``). Las cifras salen
de los resultados guardados (``investigacion.resultados``), las conclusiones de
``investigacion.conclusiones`` y las gráficas de ``investigacion.graficas``: la página y el
impreso dicen lo mismo, y el PDF no vuelve a abrir la prueba final.
"""

from __future__ import annotations

import datetime as dt
import html
from pathlib import Path

import pandas as pd

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
from src.investigacion import conclusiones, vistas
from src.investigacion import graficas as gi

TITULO = "¿Cuándo entrar a los REITs?"


def _pb(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{int(v):+,d}" if int(v) else "0"


def _p0(v) -> str:
    return pct(v, 0)


def _p1(v) -> str:
    return pct(v, 1)


def _p2(v) -> str:
    return pct(v, 2)


def _r2(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v * 100:+.1f}%"


def _p_valor(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:.2f}"


def _portada(res: dict) -> str:
    f = vistas.fases(res)
    filas = [[_e(r["fase"]), _e(r["que"]), _e(r["detalle"]), f"<b>{_e(r['resultado'])}</b>"] for _, r in f.iterrows()]
    return f"""
    <section class='portada'>
      <div class='marca'>SPREAD <span>TRADING CLUB</span></div>
      <div style='flex-grow:1;display:flex;flex-direction:column;justify-content:center'>
        <div class='rotulo'>Investigación pre-registrada · REITs de EE. UU. desde 1972 y ocho mercados más</div>
        <h1>{_e(TITULO)}</h1>
        <p style='font-size:12.5pt;max-width:150mm'>La pregunta: ¿existe una manera eficiente de saber cuándo
        estar en REITs y cuándo en efectivo? La respuesta, después de 22 reglas, 5 modelos y una prueba final en
        ocho mercados que nunca se habían visto: <b>no se encontró</b>. Aportar siempre le ganó a todo lo que se
        probó, con los impuestos y las comisiones de un inversionista mexicano por el SIC.</p>
        {tabla(filas, ["Fase", "Qué", "Detalle", "Resultado"], alinear="llll")}
      </div>
      <div class='gris chico'>Generado el {dt.date.today():%d-%m-%Y}. Herramienta de análisis, no asesoría de
      inversión. Los cálculos fiscales son indicativos.</div>
    </section>"""


def _conclusiones(res: dict) -> str:
    bloques = []
    for c in conclusiones.conclusiones(res):
        glifo, color = GLIFO.get(c.tono, GLIFO["neutral"])
        bloques.append(f"<div class='conclusion' style='border-left-color:{color}'>"
                       f"<b><span style='color:{color}'>{glifo}</span> {_e(c.titulo)}</b><p>{_e(c.texto)}</p></div>")
    return "<h2 class='salto'>Lo que se encontró</h2>" + "".join(bloques)


def _metodo() -> str:
    return (
        "<h2 class='salto'>Cómo se hizo</h2>"
        "<p>El error más caro en una investigación así es encontrar un patrón que solo existe en los datos con los "
        "que se buscó. Para evitarlo:</p><ul>"
        "<li><b>Las reglas del juego, antes de tocar datos</b> (fase 0): la métrica —TIR money-weighted después de "
        "impuestos, aportando 1,000 dólares al mes, contra aportar siempre al mismo activo—, las muestras y los "
        "criterios de éxito, congelados en código y en una prueba.</li>"
        "<li><b>Los datos partidos antes de verlos</b>: desarrollo de 1972 a 2015; validación de 2016 en adelante; "
        "prueba final con ocho mercados de otros países (Japón, Australia, Singapur, Hong Kong, Reino Unido, Europa "
        "continental, Canadá y FIBRAs) sellados con su huella digital. El código no deja abrir lo que el diseño "
        "todavía no permite.</li>"
        "<li><b>Cada hipótesis en un commit antes de correrla</b> (fases 4 y 7), con lo que se esperaba.</li>"
        "<li><b>Una bitácora de cada prueba</b>: el Sharpe deflactado y la probabilidad de sobreajuste usan el "
        "número real de intentos.</li></ul>"
        "<div class='bloque'><h3>Los criterios de éxito (fase 0)</h3>"
        + tabla([["Le gana a aportar siempre", "+50 pb al año de TIR, o 30% menos de caída máxima con costo de a lo "
                  "más 25 pb"],
                 ["Aguanta afuera", "En el conjunto de la prueba final y en al menos dos de cada tres mercados"],
                 ["Predice fuera de muestra", "R² fuera de muestra positivo y Clark-West con p < 0.05"],
                 ["Pruebas múltiples", "Sharpe deflactado ≥ 0.95 y probabilidad de sobreajuste ≤ 0.20"],
                 ["Suficientes decisiones", "Al menos 100 apuestas efectivas (P7)"],
                 ["Robustez", "Sigue cumpliendo con un mes de retraso y con el doble de comisión"]],
                ["Criterio", "Qué pide"], alinear="ll") + "</div>"
        "<div class='bloque'><h3>Lo que dice la literatura (fase 1)</h3><ul class='chico'>"
        "<li>El yield de los REITs predice el retorno dentro de muestra y falla fuera: R² fuera de muestra de "
        "−0.7% mensual y −15% semestral (Ghysels, Plazzi, Torous y Valkanov, 2013).</li>"
        "<li>Fuera de muestra el retorno es mucho menos predecible, y con costos la ganancia del timing desaparece "
        "en gran parte (Ling, Naranjo y Ryngaert, 2000).</li>"
        "<li>El filtro de tendencia reduce las caídas grandes, sin subir el retorno, y su desempeño publicado "
        "trae sesgo de minería de datos (Faber, 2007; Glabadanidis, 2014; Zakamulin, 2014).</li>"
        "<li>Las 99 fuentes, con la evidencia a favor y en contra, están en docs/investigacion/literatura.md.</li>"
        "</ul></div>")


def _techo(res: dict, fig: Figuras) -> str:
    return ("<h2 class='salto'>1. El techo: cuánto valdría conocer el futuro</h2>"
            "<p>Antes de buscar señales, la pregunta es cuánto podría valer acertar. Un oráculo que conoce el "
            "futuro marca el máximo; una regla real captura una fracción.</p>"
            + fig(gi.techo, res, pie="Aportando 1,000 dólares al mes de 1972 a 2015, contra aportar siempre. "
                  "Escala logarítmica.")
            + "<div class='bloque'><h3>Las caídas de 20% o más, 1972-2015</h3>"
            + _tabla_vista(vistas.caidas(res), ["Máximo", "Mínimo", "Caída", "Meses cayendo", "Meses para recuperar"],
                           [None, None, _p0, num, lambda v: "—" if pd.isna(v) else str(int(v))]) + "</div>"
            + "<div class='bloque'><h3>¿Qué tan seguido le ganó el efectivo a los REITs?</h3>"
            + _tabla_vista(vistas.frecuencia(res), ["Meses hacia adelante", "El efectivo ganó", "Ventanas independientes",
                                                   "REITs (mediana anual)", "Efectivo (mediana anual)"],
                           [num, _p0, num, _p1, _p1]) + "</div>"
            + "<div class='bloque'><h3>De dónde salió el retorno del sector</h3>"
            + _tabla_vista(vistas.descomposicion(res), ["Periodo", "REITs", "Del ingreso", "Del precio", "Efectivo",
                                                       "Inflación", "Bolsa", "Volatilidad", "Correlación con bolsa"],
                           [None, _p1, _p1, _p1, _p1, _p1, _p1, _p1, lambda v: f"{v:.2f}"]) + "</div>")


def _senales(res: dict, fig: Figuras) -> str:
    r = res["fase5"]["resumen"]
    return ("<h2 class='salto'>2. Las señales de entrada (fase 5)</h2>"
            f"<p>Once señales con respaldo en la literatura —valuación, crédito, condiciones financieras, la bolsa del "
            f"mes y tendencia—, convertidas en {r['intentos']} reglas fijadas antes de correr. Para pasar a la "
            f"validación una regla tenía que ganarle a aportar siempre, también con un mes de retraso y con el doble "
            f"de comisión, en 1972-1992 y en 1993-2015, y predecir el retorno a 12 meses. <b>Pasaron "
            f"{r['pasan']}.</b> Probabilidad de sobreajuste de las {r['intentos']}: {r['pbo']:.2f}.</p>"
            + fig(gi.reglas, res, pie="Cada regla contra aportar siempre, rebalanceando, 1972-2015. El círculo vacío: "
                  "la misma regla ejecutada un mes después. La línea roja punteada es el criterio de +50 pb.")
            + _tabla_vista(vistas.reglas(res), ["Señal", "Regla", "Solo dinero nuevo (pb)", "Rebalanceando (pb)",
                                                "Contra mezcla fija (pb)", "Caída máxima", "Exposición",
                                                "Con un mes de retraso (pb)", "R² a 12 meses", "Clark-West p", "Pasa"],
                           [None, None, _pb, _pb, _pb, _p0, _p0, _pb, _r2, _p_valor, None]))


def _escalera(res: dict, fig: Figuras) -> str:
    return ("<h2 class='salto'>3. La escalera de modelos (fase 7)</h2>"
            "<p>Si ninguna señal sola sirve, ¿las combinadas? Cinco modelos, del más simple al aprendizaje "
            "automático, estimados siempre con el pasado y con la misma regla: salir solo si pronostican que el "
            "efectivo ganará en los 12 meses siguientes. <b>Ninguno le ganó a aportar siempre.</b> El compuesto "
            "distingue años mejores de peores, pero nunca pronosticó que el efectivo fuera a ganar.</p>"
            + fig(gi.escalera, res, pie="Mejora contra aportar siempre y caída máxima de cada modelo, 1972-2015.")
            + _tabla_vista(vistas.escalera(res), ["Modelo", "Rebalanceando (pb)", "Solo dinero nuevo (pb)",
                                                  "Contra mezcla fija (pb)", "Caída máxima", "Exposición", "Cambios",
                                                  "Con un mes de retraso (pb)", "R² del modelo", "Clark-West p"],
                           [None, _pb, _pb, _pb, _p0, _p0, num, _pb, _r2, _p_valor]))


def _prueba_final(res: dict, fig: Figuras) -> str:
    rf = res["fase8"]["resumen"]
    return (f"<h2 class='salto'>4. La prueba final: protección por tendencia (fase 8) — {_e(rf['veredicto'])}</h2>"
            "<p>Dentro si el precio está arriba de su promedio de 10 meses; si no, en efectivo. En 1972-2015 bajaba "
            "la caída máxima de −69% a −21% casi sin costo, aunque con un mes de retraso costaba 110 pb al año. Se "
            "llevó a la prueba final <b>declarada como escogida después de ver el desarrollo</b>, se congeló en la "
            "bitácora y se abrió una sola vez la validación de EE. UU. y los ocho mercados sellados.</p>"
            + fig(gi.prueba_final, res, pie="Cada mercado: cuánto bajó la caída máxima contra cuánto costó en TIR. "
                  "El criterio pide caer en el área verde.")
            + fig(gi.tendencia_eeuu, res, pie="El índice de REITs de EE. UU.; en gris, los meses en que la tendencia "
                  "estaba en efectivo.")
            + _tabla_vista(vistas.prueba_final(res), ["Mercado", "Serie", "Periodo", "TIR aportando siempre",
                                                      "Tendencia contra aportar (pb)", "Caída aportando siempre",
                                                      "Caída con tendencia", "Reducción de caída", "Exposición",
                                                      "Con un mes de retraso (pb)", "Cumple"],
                           [None, None, None, _p2, _pb, _p0, _p0, _p0, _p0, _pb, None])
            + "<p class='chico gris'>Cada mercado en su moneda, con su tasa corta como efectivo (Singapur y Hong "
              "Kong, la de EE. UU.) y la misma contabilidad. Las canastas de Singapur, Hong Kong y las FIBRAs son "
              "de los REITs que cotizan hoy.</p>")


def _pendiente() -> str:
    return ("<h2 class='salto'>Lo que falta</h2>"
            "<p><b>En cuáles REITs (fase 6).</b> Es la pregunta donde la literatura sí encuentra señales con "
            "evidencia media —calidad del balance, menor riesgo de quiebra, momentum— y donde los estudios de este "
            "proyecto ya vieron que la valuación sirve para escoger entre REITs de calidad. Necesita los estados "
            "financieros de todo el universo, incluidos los que desaparecieron, que la SEC entrega con la "
            "identificación del inversionista.</p>"
            "<p class='chico gris'>Código: src/investigacion/. Datos y bitácora: data/investigacion/. Documentos de "
            "cada fase: docs/investigacion/. Para regenerar: python scripts/investigacion.py exploracion, fase5, "
            "fase7, fase8 y pdf.</p>")


def html_de_investigacion(res: dict, *, fuentes_css: str | None = None) -> str:
    import plotly.offline

    fig = Figuras()     # llama a cada gráfica con el tema claro del impreso
    cuerpo = (_portada(res) + _conclusiones(res) + _metodo() + _techo(res, fig) + _senales(res, fig)
              + _escalera(res, fig) + _prueba_final(res, fig) + _pendiente())
    css = _css(css_de_fuentes() if fuentes_css is None else fuentes_css)
    return ("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            f"<title>{_e(TITULO)}</title><style>{css}</style>"
            f"<script>{plotly.offline.get_plotlyjs()}</script></head>"
            f"<body>{cuerpo}{fig.script()}</body></html>")


def generar_pdf(res: dict, destino: Path) -> Path:
    from playwright.sync_api import sync_playwright

    documento = html_de_investigacion(res)
    destino.parent.mkdir(parents=True, exist_ok=True)
    pie = ("<div style='width:100%;font-family:monospace;font-size:7px;color:#6B6B66;"
           "padding:0 15mm;display:flex;justify-content:space-between'>"
           f"<span>SPREAD TRADING CLUB · {html.escape(TITULO)}</span>"
           "<span><span class='pageNumber'></span> / <span class='totalPages'></span></span></div>")
    with sync_playwright() as p:
        navegador = _lanzar_chromium(p)
        pagina = navegador.new_page()
        pagina.set_content(documento, wait_until="load")
        pagina.wait_for_selector("body[data-listo='1']", timeout=180_000)
        pagina.pdf(path=str(destino), print_background=True, prefer_css_page_size=True,
                   display_header_footer=True, header_template="<div></div>", footer_template=pie)
        navegador.close()
    return destino
