"""Valuación individual, en cinco zonas de jerarquía descendente.

Antes esta pantalla eran diez secciones del mismo peso visual, apiladas en un
scroll lineal. Eso obliga a leerlo todo para saber cualquier cosa, y para un
operador que abre la pantalla entre dos llamadas es lo mismo que no tener nada.

El orden ahora es el de una decisión, no el del código que la produce:

    01 VEREDICTO   una palabra y su razón. Tres segundos.
    02 EVIDENCIA   tres preguntas en paralelo. Ninguna se contesta con las otras.
    03 CASCADA     el mecanismo: de dónde sale el AFFO y si cuadra.
    04 MÉTODOS     qué se puede valuar y qué le falta al que no, con nombre.
    05 AUDITORÍA   cerrado por omisión, rastreable hasta el filing.

No se quitó nada de lo que la pantalla ya hacía: lo que era una sección propia y
resultó ser detalle —la venta por valuación, el sesgo de la ventana completa, el
perfil sectorial, la exportación— vive en la Zona 5, a un clic.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from comun import (  # noqa: E402
    AZUL,
    BORDE_2,
    COLOR_LUZ,
    TINTA_3,
    avisar_procedencia,
    avisos,
    banda_emisor,
    barra_comparativa,
    bps,
    cascada_html,
    configurar,
    descargo,
    dinero,
    exigir_base,
    explicar,
    filas_metodo,
    inyectar_estilos,
    mostrar_tabla,
    numero,
    panel_veredicto,
    pct,
    positivo,
    puertas_html,
    rejilla_cifras,
    selector_de_corte,
    selector_de_emisor,
    tarjeta_abre,
    tarjeta_cierra,
    veces,
    zona,
)

from src.config import DIR_EXPORTES, UMBRALES  # noqa: E402
from src.export.excel import DatosExportacion, exportar  # noqa: E402
from src.modelo.cascada import (  # noqa: E402
    CLAVES_TRAMPA,
    REPORTE,
    calcular_cascada,
    clave_base,
    escalones_de_cascada,
)
from src.modelo.kill import tabla_liston_friccion, venta_parcial_sugerida  # noqa: E402
from src.modelo.sectorial import metricas_especificas, perfil  # noqa: E402
from src.modelo.senal import sesgo_por_ventana_completa  # noqa: E402
from src.modelo.valuacion import (  # noqa: E402
    InsumosValuacion,
    diagnosticar,
    rango_cap_rate,
    sensibilidad_nav_sectorial,
    valuar_por_crecimiento,
)
from src.servicio import MEDIDA_AFFO, construir_panel, contexto_macro, evaluar  # noqa: E402
from src.validacion.cuadre import cuadrar_conciliacion  # noqa: E402

configurar("Valuación", "📊")
inyectar_estilos()

repo = exigir_base()
asof = selector_de_corte()
ticker = selector_de_emisor(repo)
if ticker is None:
    st.stop()

sector_del_emisor = repo.sector_de(ticker)
cr_min, cr_base, cr_max = rango_cap_rate(sector_del_emisor)

st.sidebar.divider()
st.sidebar.markdown("**Supuestos del modelo**")
st.sidebar.caption(
    f"Sector: **{sector_del_emisor}**. El cap rate arranca en el rango de SU sector "
    f"({cr_min:.2%}–{cr_max:.2%}), no en uno solo para todos."
)
cap_rate = st.sidebar.slider(
    "Cap rate de mercado para el NAV",
    min_value=round(cr_min - 0.01, 4), max_value=round(cr_max + 0.01, 4),
    value=round(cr_base, 4), step=0.0025, format="%.4f",
    help=(
        "La palanca MÁS sensible del modelo, y la que NO puede ser la misma para todos: "
        "un self storage se capitaliza cerca de 5.5% y una oficina arriba de 8.5%. "
        "Aplicarle a un storage el cap rate de una oficina le quita un tercio del valor "
        "sin que ningún número se vea raro."
    ),
)
yield_adq = st.sidebar.slider(
    "Yield de adquisiciones del emisor", 0.03, 0.12, 0.074, 0.0025, format="%.4f",
    help="A qué cap rate está comprando activos. Contra el costo del capital da el spread de inversión.",
)

panel = construir_panel(
    repo, ticker, asof=asof, cap_rate_mercado=cap_rate, yield_adquisiciones=yield_adq
)
macro = contexto_macro(repo, asof=asof)
semaforo = evaluar(panel)
m = panel.metricas

emisores = repo.emisores()
fila_emisor = emisores.loc[emisores["ticker"] == ticker, "nombre"]
nombre_emisor = str(fila_emisor.iloc[0]) if not fila_emisor.empty else ticker

banda_emisor(
    ticker=ticker,
    nombre=nombre_emisor,
    etiquetas=(panel.sector, panel.medida_flujo),
    precio=panel.precio,
    fecha_precio=panel.precio_fecha,
    corte=asof,
    nota_derecha=f"{panel.n_observaciones} observaciones",
)

if panel.trimestral.empty:
    st.error("No hay fundamentales para este emisor al corte elegido.")
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# 01 · EL VEREDICTO
# ══════════════════════════════════════════════════════════════════════════════

zona("01", "El veredicto", "Tres puertas independientes. Solo la tercera vende.")

_COLOR_ACCION = {
    "COMPRAR": COLOR_LUZ["VERDE"],
    "MANTENER": COLOR_LUZ["VERDE"],
    "NO COMPRAR MÁS": COLOR_LUZ["AMARILLO"],
    "INCONCLUSO": COLOR_LUZ["AMARILLO"],
    "VENDER": COLOR_LUZ["ROJO"],
    "DESCARTADO": COLOR_LUZ["ROJO"],
}
_CODA = {
    "INCONCLUSO": "no es lo mismo que MANTENER",
    "DESCARTADO": "lo que falla no está barato: está descartado",
    "VENDER": "tesis rota, no precio caro",
    "NO COMPRAR MÁS": "modula compras nuevas, no dispara venta",
}

minimo_obs = UMBRALES.valuacion.min_observaciones
izq, der = st.columns([2, 1], gap="medium")
with izq:
    panel_veredicto(
        accion=semaforo.accion.value,
        color=_COLOR_ACCION.get(semaforo.accion.value, COLOR_LUZ["SIN DATOS"]),
        explicacion=semaforo.explicacion,
        coda=_CODA.get(semaforo.accion.value, ""),
        avance=(
            (panel.n_observaciones, minimo_obs)
            if panel.n_observaciones < minimo_obs else None
        ),
    )
with der:
    percentil_txt = (
        f"{panel.percentil_actual:.0%}" if panel.percentil_actual is not None else "—"
    )
    disparos = 0
    if not semaforo.deterioro.criterios.empty and "dispara" in semaforo.deterioro.criterios:
        disparos = int(semaforo.deterioro.criterios["dispara"].sum())
    puertas_html(
        [
            ("1 · Calidad", semaforo.calidad.luz.value, semaforo.calidad.mensaje[:52], ""),
            ("2 · Valuación", semaforo.valuacion.luz.value,
             semaforo.valuacion.mensaje[:52], percentil_txt),
            ("3 · Deterioro", semaforo.deterioro.luz.value,
             semaforo.deterioro.mensaje[:52], f"{disparos}/5"),
        ],
        pie="La Puerta 2 modula compras nuevas. <strong>Nunca dispara venta por sí sola.</strong>",
    )

# Las salvedades van DEBAJO del veredicto, no encima. Encima empujan hacia abajo
# lo único que se lee siempre; debajo lo califican, que es su trabajo. La latencia
# del precio ya está en la banda del emisor y no se repite aquí.
avisar_procedencia(panel.fuentes)
avisos(panel.avisos)

prima_actual = panel.prima.dropna().iloc[-1] if not panel.prima.dropna().empty else None
payout = m.get("payout_affo")
etiqueta_flujo = panel.medida_flujo
rejilla_cifras([
    ("Yield de flujo", pct(m.get("affo_yield")),
     f"{etiqueta_flujo} TTM ÷ precio crudo", ""),
    ("Prima sobre UST 10a", bps(prima_actual),
     f"contra {pct(macro.ust10)} libre de riesgo", ""),
    ("Payout", pct(payout),
     f"el listón son {UMBRALES.calidad.payout_affo_max:.0%}",
     "" if payout is None else
     (COLOR_LUZ["VERDE"] if payout < UMBRALES.calidad.payout_affo_max else COLOR_LUZ["ROJO"])),
    ("Precio / flujo", veces(m.get("p_affo")), f"veces el {etiqueta_flujo} TTM", ""),
    ("Dividendo TTM", pct(m.get("dividend_yield")),
     f"{dinero(panel.dividendo_ttm)} por acción", ""),
])

# ══════════════════════════════════════════════════════════════════════════════
# 02 · LA EVIDENCIA
# ══════════════════════════════════════════════════════════════════════════════

zona("02", "La evidencia", "Tres preguntas distintas. Ninguna se contesta con las otras.")

affo_ps_ttm = positivo(m.get("affo_por_accion_ttm"))
if affo_ps_ttm is None and "affo_por_accion_ttm" in panel.trimestral:
    serie_ps = panel.trimestral["affo_por_accion_ttm"].dropna()
    affo_ps_ttm = positivo(serie_ps.iloc[-1]) if not serie_ps.empty else None

crec_serie = panel.trimestral.get("crecimiento_affo_por_accion_yoy")
crec_hist = (
    float(pd.to_numeric(crec_serie, errors="coerce").dropna().tail(4).mean())
    if crec_serie is not None and pd.to_numeric(crec_serie, errors="coerce").notna().any()
    else None
)
valuacion_g = valuar_por_crecimiento(
    panel.precio, affo_ps_ttm, macro.ust10, panel.sector, crec_hist
)

ev_a, ev_b, ev_c = st.columns(3, gap="medium")

# A · ¿Barato contra su propia historia?
with ev_a:
    tarjeta_abre(
        "¿Barato contra sí mismo?",
        "Percentil de la prima en ventana expandible, nunca contra otros emisores.",
    )
    serie_prima = panel.prima.dropna()
    if serie_prima.empty:
        st.caption("Sin historia de prima al corte.")
    else:
        figura = go.Figure()
        figura.add_bar(
            x=serie_prima.index, y=serie_prima * 10_000,
            marker_color=["#cfccc5"] * (len(serie_prima) - 1) + [
                COLOR_LUZ["ROJO"] if (panel.percentil_actual or 1) < 0.5 else COLOR_LUZ["VERDE"]
            ],
        )
        figura.update_layout(
            height=150, margin={"t": 6, "b": 6, "l": 4, "r": 4},
            showlegend=False, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
            xaxis={"showgrid": False, "showticklabels": False},
            yaxis={"showgrid": False, "title": None, "tickfont": {"size": 9}},
            bargap=0.25,
        )
        st.plotly_chart(figura, key="prima_sparkline")
    tarjeta_cierra(
        f"<strong>{percentil_txt}</strong> de su propia historia estuvo <em>más</em> barato. "
        f"{panel.n_observaciones} observaciones; el umbral para opinar son {minimo_obs}."
    )

# B · ¿Alcanza el flujo?
with ev_b:
    tarjeta_abre(
        "¿Alcanza el flujo?",
        f"El mismo dividendo, tres respuestas. La única que importa es la del {etiqueta_flujo}.",
    )
    p_affo = m.get("payout_affo")
    p_ffo = m.get("payout_ffo")
    p_neta = m.get("payout_utilidad_neta")
    barra_comparativa(
        [
            (f"sobre {etiqueta_flujo}", p_affo, pct(p_affo),
             COLOR_LUZ["VERDE"] if (p_affo or 0) < UMBRALES.calidad.payout_affo_max
             else COLOR_LUZ["ROJO"], True),
            ("sobre FFO", p_ffo, pct(p_ffo), "#cfccc5", False),
            ("sobre utilidad neta", p_neta, pct(p_neta),
             COLOR_LUZ["ROJO"] if (p_neta or 0) > 1 else "#cfccc5", False),
        ],
        maximo=1.2,
        marca=UMBRALES.calidad.payout_affo_max,
    )
    razon_txt = ""
    if p_neta and p_affo:
        razon_txt = (
            f" Aquí es <strong>{p_neta / p_affo:.1f} veces</strong> el correcto: ese es el "
            "tamaño del error que comete quien usa el número equivocado."
        )
    tarjeta_cierra(
        "El payout sobre utilidad neta pasa de 100% en casi todo REIT sano: la depreciación "
        "contable no sale de la caja." + razon_txt
    )

# C · ¿Qué descuenta el precio?
with ev_c:
    tarjeta_abre(
        "¿Qué descuenta el precio?",
        "Gordon despejado. Es aritmética, no un pronóstico.",
    )
    if valuacion_g is None:
        st.caption(
            "Falta un insumo. En la Zona 04 dice cuál: casi siempre el flujo por "
            "acción TTM, que necesita cuatro trimestres válidos seguidos."
        )
        tarjeta_cierra()
    else:
        c_izq, c_der = st.columns(2)
        c_izq.metric("El precio pide", pct(valuacion_g.crecimiento_implicito))
        c_der.metric("Ha entregado", pct(valuacion_g.crecimiento_historico))
        tarjeta_cierra(valuacion_g.como_texto())

# ══════════════════════════════════════════════════════════════════════════════
# 03 · LA CASCADA
# ══════════════════════════════════════════════════════════════════════════════

# Los trimestres que se pueden ofrecer son los de la medida que este emisor sí
# publica: pedir siempre "affo" dejaba sin cascada a PSA, EXR y WELL, que reportan
# Core FFO y nunca un AFFO, aunque su conciliación esté completa en la base.
concepto_flujo = "affo" if panel.medida_flujo == MEDIDA_AFFO else "ffo_normalizado"
periodos = repo.hechos(asof=asof, tickers=ticker, conceptos=concepto_flujo, periodo_tipo="Q")
opciones = (
    sorted(pd.to_datetime(periodos["fecha_dato"]).dt.date.unique(), reverse=True)
    if not periodos.empty else []
)
fecha_cascada = opciones[0] if opciones else None

zona(
    "03", "La cascada",
    "De dónde sale el flujo, y si cuadra contra el subtotal que publica el emisor.",
)
if opciones:
    fecha_cascada = st.selectbox(
        "Trimestre", opciones, format_func=str, label_visibility="collapsed"
    )

conciliacion = (
    repo.conciliacion(ticker, fecha_cascada, asof=asof) if fecha_cascada else pd.DataFrame()
)

if conciliacion.empty:
    st.info(
        "No hay conciliación línea por línea para este trimestre. Se extrae del Exhibit 99.1 "
        "de los 8-K de resultados: corre `python scripts/ingesta.py` para traerla."
    )
else:
    lineas = {r["linea"]: float(r["valor"]) for _, r in conciliacion.iterrows()}
    orden_lineas = {r["linea"]: int(r["orden"]) for _, r in conciliacion.iterrows()}
    resultado = calcular_cascada(lineas, sector=panel.sector, signos=REPORTE)
    # Dos preguntas distintas, y confundirlas fue un error mío del rediseño: el
    # CUADRE es aritmético —¿las partidas reproducen el subtotal que el emisor
    # publica?— y las BANDERAS son cualitativas —¿falta una de las tres trampas,
    # el CapEx se ve raro contra el NOI?—. Poner el conteo de banderas bajo la
    # etiqueta "tramos sin cuadrar" decía que una conciliación exacta no cuadraba.
    veredicto = cuadrar_conciliacion(lineas, orden_lineas)

    pasos = escalones_de_cascada(lineas, medida_flujo=panel.medida_flujo)

    verificables = [t for t in veredicto.tramos if t.verificable]
    cuadrando = sum(1 for t in verificables if t.cuadra)
    cascada_html(
        pasos,
        pie=(
            f"La conciliación cuadra en sus {cuadrando} tramo(s) verificables, contra los "
            "subtotales que el propio emisor publica"
            if veredicto.cuadra else
            f"{len(verificables) - cuadrando} de {len(verificables)} tramo(s) no cuadran"
        ),
        color_pie=COLOR_LUZ["VERDE"] if veredicto.cuadra else COLOR_LUZ["ROJO"],
        unidad=f"millones de USD · {len(conciliacion)} renglones",
    )
    if not veredicto.cuadra:
        st.error(veredicto.motivo)
    for bandera in resultado.banderas:
        st.warning(bandera)

    with st.expander("Ver la conciliación renglón por renglón"):
        detalle = conciliacion.copy()
        # Con la clave base: el ajuste de renta en línea recta vive DESPUÉS del
        # primer subtotal y llega con sufijo de segmento, así que compararlo tal
        # cual contra el catálogo nunca lo marcaba.
        detalle["trampa"] = detalle["linea"].map(lambda k: clave_base(k) in CLAVES_TRAMPA)
        detalle["Línea"] = detalle.apply(
            lambda r: ("⚠️ " if r["trampa"] else "") + str(r["etiqueta"]), axis=1
        )
        mostrar_tabla(
            detalle[["Línea", "valor", "linea"]].rename(
                columns={"valor": "Monto (USD)", "linea": "Concepto normalizado"}
            ),
            column_config={"Monto (USD)": st.column_config.NumberColumn(format="$%,.0f")},
        )
        st.caption(
            "⚠️ marca las tres trampas del AFFO: renta en línea recta, CapEx de mantenimiento y "
            "revaluación a valor razonable. Los montos vienen con el signo del reporte, listos "
            "para sumarse: así se reproduce exactamente el subtotal que publica el emisor."
        )
        explicar("NOI", "FFO", "renta en línea recta", "CapEx de mantenimiento")

# ══════════════════════════════════════════════════════════════════════════════
# 04 · QUÉ SE PUEDE VALUAR
# ══════════════════════════════════════════════════════════════════════════════

zona("04", "Qué se puede valuar, y qué falta", "Un hueco tiene nombre, no es un cero.")

fila_ultima = (
    panel.trimestral.tail(1).iloc[0] if not panel.trimestral.empty else pd.Series(dtype="float64")
)
insumos_diag = InsumosValuacion(
    ticker=ticker,
    precio=numero(panel.precio, 0.0),
    acciones_diluidas=positivo(fila_ultima.get("acciones_diluidas"), 1.0),
    affo_por_accion_ttm=affo_ps_ttm,
    noi_trimestral=positivo(fila_ultima.get("noi")),
    deuda_total=positivo(fila_ultima.get("deuda_total"), 0.0),
    sector=panel.sector,
)
diagnostico = diagnosticar(insumos_diag, tasa_libre_riesgo=macro.ust10)

_CIFRA_METODO = {
    "Múltiplos (AFFO yield, P/AFFO)": f"{pct(m.get('affo_yield'))} · {veces(m.get('p_affo'))}",
    "Crecimiento implícito en el precio": (
        pct(valuacion_g.crecimiento_implicito) if valuacion_g else "—"
    ),
    "NAV (NOI ÷ cap rate del sector)": (
        f"{dinero(m.get('nav_por_accion'))} · {pct(m.get('premio_descuento_nav'), 1)}"
    ),
}

met_izq, met_der = st.columns([1.35, 1], gap="medium")
with met_izq:
    filas_metodo([
        (
            met.nombre,
            met.explicacion,
            met.disponible,
            _CIFRA_METODO.get(met.nombre, "—") if met.disponible
            else f"Le falta <strong>{', '.join(met.faltantes)}</strong>. "
                 "Es una medida no-GAAP: no está en XBRL, vive en el suplemento y hay que "
                 "extraerla emisora por emisora, como el AFFO.",
        )
        for met in diagnostico
    ])

with met_der:
    tarjeta_abre(
        f"Cap rate de {panel.sector}",
        "No es una constante universal: es la tasa a la que el mercado privado capitaliza "
        "<em>esta</em> renta.",
    )
    ultima_completa = panel.trimestral.dropna(subset=["affo_por_accion_ttm"]).tail(1)
    tabla_sens = pd.DataFrame()
    if not ultima_completa.empty:
        fila = ultima_completa.iloc[0]
        ins_sens = InsumosValuacion(
            ticker=ticker,
            precio=numero(panel.precio, 0.0),
            acciones_diluidas=positivo(fila.get("acciones_diluidas"), 1.0),
            noi_trimestral=positivo(fila.get("noi")),
            affo_por_accion_ttm=positivo(fila.get("affo_por_accion_ttm")),
            dividendo_ttm_por_accion=panel.dividendo_ttm,
            sector=panel.sector,
        )
        tabla_sens = sensibilidad_nav_sectorial(ins_sens, panel.sector)

    if tabla_sens.empty:
        st.caption(
            f"El rango de {panel.sector} va de {cr_min:.2%} a {cr_max:.2%}, con base en "
            f"{cr_base:.2%}. La curva de sensibilidad necesita el NOI, que todavía falta."
        )
    else:
        figura = go.Figure()
        figura.add_scatter(
            x=tabla_sens["cap_rate"], y=tabla_sens["nav_por_accion"],
            line={"color": AZUL, "width": 2.5}, name="NAV por acción",
        )
        if panel.precio:
            figura.add_hline(
                y=panel.precio, line_dash="dash", line_color=COLOR_LUZ["ROJO"],
                annotation_text="Precio", annotation_position="right",
            )
        figura.update_layout(
            height=190, margin={"t": 8, "b": 8, "l": 4, "r": 4}, showlegend=False,
            plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
            xaxis={"tickformat": ".2%", "gridcolor": BORDE_2, "tickfont": {"size": 9}},
            yaxis={"gridcolor": BORDE_2, "tickfont": {"size": 9}},
        )
        st.plotly_chart(figura, key="sensibilidad_nav")
    tarjeta_cierra(
        "Valuar un self storage al cap rate de net lease le borra <strong>más de una quinta "
        "parte del valor</strong> sin que ningún número se vea raro: la aritmética sigue "
        "cuadrando, solo el supuesto está mal."
    )

if valuacion_g is not None:
    with st.expander("Escenarios de crecimiento y su valor por acción"):
        escenarios = pd.DataFrame([
            {
                "escenario": etiqueta,
                "crecimiento": g,
                "valor_por_accion": valuacion_g.valor_con(g),
                "premio_descuento": (
                    None if not valuacion_g.valor_con(g)
                    else panel.precio / valuacion_g.valor_con(g) - 1.0
                ),
            }
            for etiqueta, g in (
                ("Sin crecimiento", 0.0),
                ("Mitad del entregado", (crec_hist or 0.0) / 2),
                ("El que ha entregado", crec_hist or 0.0),
                ("Implícito en el precio", valuacion_g.crecimiento_implicito),
            )
            if g is not None
        ])
        mostrar_tabla(escenarios)
        st.caption(
            f"Tasa de descuento: UST 10 años {valuacion_g.tasa_libre_riesgo:.2%} más la prima "
            f"de {panel.sector}, {valuacion_g.prima_riesgo:.2%}. El premio/descuento se lee "
            "contra el precio actual: negativo significa que el precio está **por debajo** "
            "del valor que implica ese crecimiento."
        )

# ══════════════════════════════════════════════════════════════════════════════
# 05 · AUDITORÍA
# ══════════════════════════════════════════════════════════════════════════════

zona("05", "Auditoría", "Cerrado por omisión. Cada cifra rastreable hasta su documento.")

with st.expander("Las tres puertas, criterio por criterio"):
    for puerta, titulo in (
        (semaforo.calidad, "Puerta 1 — Calidad"),
        (semaforo.valuacion, "Puerta 2 — Valuación"),
        (semaforo.deterioro, "Puerta 3 — Deterioro"),
    ):
        st.markdown(f"**{titulo}** — {puerta.mensaje}")
        if not puerta.criterios.empty:
            mostrar_tabla(
                puerta.criterios[[
                    c for c in ("criterio", "valor", "umbral", "persistencia",
                                "cumple", "racha", "dispara")
                    if c in puerta.criterios
                ]],
            )
    explicar("AFFO", "prima", "percentil expandible", "spread de inversión")

with st.expander("Por qué el percentil usa ventana expandible y no la muestra completa"):
    if panel.prima.dropna().empty:
        st.caption("Sin serie de prima al corte.")
    else:
        sesgo = sesgo_por_ventana_completa(panel.prima.dropna())
        fig2 = go.Figure()
        fig2.add_scatter(x=sesgo.index, y=sesgo["expandible"], name="Expandible (lo correcto)",
                         line={"color": COLOR_LUZ["VERDE"]})
        fig2.add_scatter(x=sesgo.index, y=sesgo["muestra_completa"],
                         name="Muestra completa (usa el futuro)",
                         line={"color": COLOR_LUZ["ROJO"], "dash": "dash"})
        fig2.update_layout(height=260, yaxis_tickformat=".0%",
                           margin={"t": 20, "b": 20, "l": 10, "r": 10},
                           plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                           legend={"orientation": "h", "y": 1.15})
        st.plotly_chart(fig2, key="sesgo_ventana")
        brecha = sesgo["diferencia"].abs().mean()
        st.markdown(
            f"La diferencia media entre ambas es de **{brecha:.0%} de percentil**. La curva roja "
            "sabe, en 2019, que el yield iba a llegar a su máximo en 2023. Nadie lo sabía. "
            "Fijar umbrales con esa curva es fijarlos con información del futuro."
        )

with st.expander("Quiero vender por valuación de todos modos"):
    st.caption(
        "Vender por precio caro es distinto de vender por tesis rota. La Puerta 2 nunca "
        "dispara venta por sí sola. Si aun así quieres, este es el costo."
    )
    valor_posicion = st.number_input("Valor de tu posición (USD)", 0.0, value=100_000.0, step=5_000.0)
    ganancia = st.slider("Ganancia acumulada sobre el costo", 0.0, 3.0, 0.40, 0.05, format="%.2f")
    sugerencia = venta_parcial_sugerida(valor_posicion, ganancia_acumulada=ganancia)
    a, b, c = st.columns(3)
    a.metric("Venta parcial sugerida", f"{sugerencia['fraccion_sugerida']:.0%}")
    b.metric("Costo fiscal estimado", dinero(sugerencia["costo_fiscal_estimado"]))
    c.metric("Ventaja anual necesaria", f"{sugerencia['ventaja_anual_necesaria_bps']:,.0f} bps",
             help="Cuánto más tiene que rendir el destino, al año, para recuperar el costo fiscal en dos años.")
    st.warning(sugerencia["advertencia"])
    mostrar_tabla(tabla_liston_friccion())

with st.expander(f"Qué mirar en un REIT de {panel.sector}"):
    perfil_sector = perfil(panel.sector)
    if perfil_sector:
        s1, s2 = st.columns(2)
        s1.markdown(
            f"- **Duración de contrato:** {perfil_sector.duracion_contrato}\n"
            f"- **Tipo de inquilino:** {perfil_sector.tipo_inquilino}\n"
            f"- **Intensidad de CapEx:** {perfil_sector.intensidad_capex}\n"
            f"- **Quién paga los gastos:** {perfil_sector.quien_paga_gastos}"
        )
        s2.info(perfil_sector.nota)
    for metrica, explicacion in metricas_especificas(panel.sector).items():
        st.markdown(f"- **{metrica}** — {explicacion}")

with st.expander("Serie trimestral completa"):
    mostrar_tabla(panel.trimestral.tail(20))

with st.expander("Procedencia de cada cifra"):
    st.caption(
        "Primario significa que viene directo de la SEC o de un banco central. Derivado o "
        "reconstruido significa que lo calculó el modelo y hereda el error de sus componentes."
    )
    if not panel.fuentes.empty:
        mostrar_tabla(panel.fuentes.head(60))

with st.expander("Exportar a Excel con fórmulas vivas"):
    st.caption(
        "El libro sale con **fórmulas vivas**, no valores pegados: cambia el cap rate o el precio "
        "en la hoja de Inputs y todo recalcula. Azul sobre amarillo es tuyo; negro es fórmula."
    )
    if st.button("Generar libro de Excel", type="primary"):
        ultima = panel.trimestral.dropna(subset=["affo_por_accion_ttm"]).tail(1)
        if ultima.empty:
            st.error("No hay un trimestre completo para exportar.")
        else:
            fila = ultima.iloc[0]
            # Anualizar el trimestre por cuatro es una aproximación, y se marca como
            # tal: solo se usa para el contraste entre AFFO, FFO y utilidad neta, no
            # para valuar. Si el trimestre falta, el resultado es faltante, no cero.
            ffo_trimestral = positivo(fila.get("ffo"))
            utilidad_trimestral = positivo(fila.get("utilidad_neta"))
            ins = InsumosValuacion(
                ticker=ticker,
                precio=numero(panel.precio, 0.0),
                acciones_diluidas=positivo(fila.get("acciones_diluidas"), 1.0),
                noi_trimestral=positivo(fila.get("noi")),
                affo_ttm=positivo(fila.get("affo_ttm")),
                affo_por_accion_ttm=positivo(fila.get("affo_por_accion_ttm")),
                ffo_ttm=None if ffo_trimestral is None else ffo_trimestral * 4,
                utilidad_neta_ttm=None if utilidad_trimestral is None else utilidad_trimestral * 4,
                dividendo_ttm_por_accion=panel.dividendo_ttm,
                sector=panel.sector,
            )
            componentes = (
                {r["linea"]: float(r["valor"]) for _, r in conciliacion.iterrows()}
                if not conciliacion.empty
                else {}
            )
            datos = DatosExportacion(
                ticker=ticker,
                nombre=nombre_emisor,
                sector=panel.sector,
                fecha_corte=asof,
                insumos=ins,
                componentes_cascada=componentes,
                cap_rate_mercado=cap_rate,
                tasa_libre_riesgo=panel.tasa_libre_riesgo or 0.042,
                yield_adquisiciones=yield_adq,
                fuentes=panel.fuentes.head(200).to_dict("records") if not panel.fuentes.empty else [],
            )
            ruta = exportar(datos, DIR_EXPORTES / f"{ticker}_{asof}.xlsx")
            st.success(f"Libro generado: `{ruta}`")
            with open(ruta, "rb") as fh:
                st.download_button(
                    "Descargar", fh.read(), file_name=ruta.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

st.markdown(
    f"<div style='font-size:11px;line-height:1.6;color:{TINTA_3};margin-top:18px'>"
    "Esto es una herramienta de análisis, no asesoría de inversión. Toda métrica de desempeño "
    "va acompañada de su conteo de apuestas efectivas. Cuando las observaciones son "
    "insuficientes el veredicto es <strong>INCONCLUSO</strong>, nunca GO.</div>",
    unsafe_allow_html=True,
)
descargo()
