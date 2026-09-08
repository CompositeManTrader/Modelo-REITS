"""Mis propiedades contra un REIT que yo elijo.

La pantalla anterior contestaba una pregunta que nadie hizo. Estaba construida
alrededor de un departamento HIPOTÉTICO —precio y renta en dos deslizadores de la
barra lateral— y las propiedades reales del usuario aparecían al final, en un
formulario escondido dentro de un acordeón. La alternativa contra la que se
comparaba no era una emisora sino un número inventado a mano: "yield neto de
impuestos del portafolio de REITs, 4.2%".

Eso tiene tres problemas y el tercero es el grave:

1. Obliga a capturar de nuevo, en deslizadores, algo que ya está en la base.
2. El rival no existe. Un yield tecleado no tiene emisora, ni historia, ni
   dividendo verificable contra un filing.
3. Y sobre todo: el 4.2% ya venía neto de impuestos mientras el rendimiento del
   inmueble se miraba bruto. Comparar el bruto de un lado contra el neto del otro
   es el error que hace ganar al ladrillo en casi todos los análisis que circulan,
   y aquí estaba metido en el valor por omisión de un deslizador.

Esta versión invierte el orden. El sujeto son TUS propiedades, el rival es una
emisora concreta del universo con su dividendo real, y los dos lados llegan al
mismo punto: pesos en el bolsillo después de impuestos, sobre el valor de mercado
de hoy.

    01 TUS PROPIEDADES  el inventario, editable en la tabla. Agregar es un renglón.
    02 CONTRA QUIÉN     la emisora, con su dividendo real y su historia.
    03 EL DUELO         el veredicto y las dos cascadas, del bruto al bolsillo.
    04 UNA POR UNA      cuáles de tus propiedades le ganan y cuáles no.
    05 QUÉ FALTARÍA     cuánta plusvalía necesita el ladrillo para empatar.
    06 LO QUE EL FLUJO NO DICE  fricción, iliquidez, concentración, riesgos.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from comun import (  # noqa: E402
    bps,
    configurar,
    descargo,
    dinero,
    exigir_base,
    mostrar_tabla,
    panel_veredicto,
    pct,
    rejilla_cifras,
    selector_de_corte,
    selector_de_emisor,
    tarjeta_abre,
    tarjeta_cierra,
    zona,
)

from marca import (  # noqa: E402
    AMBAR,
    COLOR_LUZ,
    GRIS,
    LINEA,
    LOSS,
    MONO,
    PROFIT,
    encabezado,
    inyectar_estilos,
    plantilla_plotly,
)
from src.servicio import construir_panel, contexto_macro  # noqa: E402
from src.simulacion.inmueble_cdmx import (  # noqa: E402
    AVISO_INDICES,
    RIESGOS_CUALITATIVOS,
    SupuestosInmueble,
    comparar_portafolio_propio,
    duelo_portafolio_contra_emisora,
    evaluar_inmueble,
)

configurar("Inmueble vs REITs", "🏘️")
inyectar_estilos()
encabezado("Inmueble vs REITs")

repo = exigir_base()
asof = selector_de_corte()
macro = contexto_macro(repo, asof=asof)
INFLACION = float(macro.inflacion_mx) if macro.inflacion_mx else 0.045

# ══════════════════════════════════════════════════════════════════════════════
# 01 · Tus propiedades
# ══════════════════════════════════════════════════════════════════════════════

zona("01", "Tus propiedades", "Agregar una es escribir un renglón. Se guarda al pulsar.")

COLUMNAS = [
    "nombre", "tipo", "fecha_compra", "precio_compra", "valor_actual",
    "renta_mensual", "mantenimiento_mensual", "predial_anual", "seguro_anual",
    "saldo_hipoteca",
]
NUMERICAS = [c for c in COLUMNAS if c not in ("nombre", "tipo", "fecha_compra")]

guardados = repo.inmuebles()
if guardados.empty:
    st.info(
        "**Todavía no hay propiedades.** Escribe una en el último renglón de la tabla —basta "
        "el nombre, el valor de hoy y la renta— y pulsa **Guardar**. Lo demás puede quedar en "
        "cero y se afina después."
    )
    editable = pd.DataFrame(columns=COLUMNAS)
else:
    editable = guardados.reindex(columns=COLUMNAS)

editable = editable.copy()
editable["fecha_compra"] = pd.to_datetime(editable["fecha_compra"], errors="coerce")
for columna in NUMERICAS:
    editable[columna] = pd.to_numeric(editable[columna], errors="coerce")

# `data_editor` con `num_rows="dynamic"` es todo lo que hacía falta para el punto 2
# del encargo: alta, edición y baja en el mismo lugar y sin un formulario aparte.
# El formulario anterior tenía nueve campos, vivía dentro de un acordeón y solo
# sabía dar de alta: para corregir una renta había que borrar la base.
propuesta = st.data_editor(
    editable,
    num_rows="dynamic",
    width="stretch",
    key="editor_inmuebles",
    column_config={
        "nombre": st.column_config.TextColumn("Propiedad", required=True, width="medium"),
        "tipo": st.column_config.SelectboxColumn(
            "Tipo", options=["departamento", "casa", "local", "bodega", "terreno"],
            default="departamento",
        ),
        "fecha_compra": st.column_config.DateColumn("Compra", format="YYYY-MM-DD"),
        "precio_compra": st.column_config.NumberColumn("Precio pagado", format="$%,.0f"),
        "valor_actual": st.column_config.NumberColumn(
            "Valor hoy", format="$%,.0f",
            help="El que manda para la comparación: la pregunta es hacia adelante.",
        ),
        "renta_mensual": st.column_config.NumberColumn("Renta / mes", format="$%,.0f"),
        "mantenimiento_mensual": st.column_config.NumberColumn("Mantto / mes", format="$%,.0f"),
        "predial_anual": st.column_config.NumberColumn("Predial / año", format="$%,.0f"),
        "seguro_anual": st.column_config.NumberColumn("Seguro / año", format="$%,.0f"),
        "saldo_hipoteca": st.column_config.NumberColumn("Saldo hipoteca", format="$%,.0f"),
    },
)

izq, der = st.columns([1, 4])
if izq.button("Guardar", type="primary", width="stretch"):
    filas = propuesta.dropna(subset=["nombre"])
    filas = filas[filas["nombre"].astype(str).str.strip() != ""]
    listas = []
    for _, r in filas.iterrows():
        fila = {c: r.get(c) for c in COLUMNAS}
        fila["tipo"] = fila.get("tipo") or "departamento"
        fecha = pd.to_datetime(fila.get("fecha_compra"), errors="coerce")
        fila["fecha_compra"] = (
            fecha.date() if pd.notna(fecha) else dt.date.today()
        )
        for columna in NUMERICAS:
            valor = pd.to_numeric(fila.get(columna), errors="coerce")
            fila[columna] = 0.0 if pd.isna(valor) else float(valor)
        # Sin valor de hoy la comparación no tiene denominador; el precio pagado
        # es la mejor aproximación disponible y se dice cuál se usó.
        if not fila["valor_actual"]:
            fila["valor_actual"] = fila["precio_compra"]
        listas.append(fila)
    repo.reemplazar_inmuebles(listas)
    st.success(f"{len(listas)} propiedad(es) guardadas.")
    st.rerun()

der.caption(
    "La tabla se edita directo: cambia una renta, borra un renglón con la papelera, o escribe "
    "uno nuevo al final. Nada se guarda hasta que pulses el botón."
)

inmuebles = repo.inmuebles()

# ══════════════════════════════════════════════════════════════════════════════
# 02 · Contra quién
# ══════════════════════════════════════════════════════════════════════════════

zona("02", "Contra quién los comparas", "Una emisora del universo, con su dividendo real.")

ticker = selector_de_emisor(repo, clave="ticker_inmueble")
if ticker is None:
    st.stop()

panel = construir_panel(repo, ticker, asof=asof)
metricas = panel.metricas
yield_bruto = metricas.get("dividend_yield")
crecimiento = metricas.get("crecimiento_affo_por_accion_yoy")

st.sidebar.divider()
st.sidebar.markdown("**Tu situación fiscal**")
sueldo = st.sidebar.number_input(
    "Tu ingreso por sueldo (MXN/año)", 0.0, value=0.0, step=100_000.0,
    help=(
        "El parámetro que más mueve el resultado del lado del ladrillo. La renta como único "
        "ingreso paga una tasa efectiva cercana a 5%; apilada sobre un sueldo entra en "
        "marginal de 30–35%."
    ),
)
tiene_w8ben = st.sidebar.checkbox(
    "Tengo W-8BEN firmado", value=True,
    help="Sin W-8BEN la retención de EE. UU. sube de 10% a 30% sobre el dividendo.",
)
plusvalia = st.sidebar.slider(
    "Plusvalía anual que esperas del ladrillo", -0.02, 0.12, 0.04, 0.005, format="%.3f"
)

if yield_bruto is None:
    st.error(
        f"**{ticker} no tiene dividendo calculable al corte.** Sin él no hay con qué comparar. "
        "Elige otra emisora o revisa su cobertura en la pantalla de Valuación."
    )
    st.stop()

rejilla_cifras([
    ("Emisora", ticker, panel.sector, AMBAR),
    ("Dividendo bruto", pct(yield_bruto), "sobre precio de cierre", ""),
    ("Precio", dinero(panel.precio), str(panel.precio_fecha or "—"), ""),
    (
        "Crecimiento del flujo",
        pct(crecimiento) if crecimiento is not None else "—",
        "AFFO por acción, año contra año",
        PROFIT if (crecimiento or 0) > 0 else GRIS,
    ),
])

# ══════════════════════════════════════════════════════════════════════════════
# 03 · El duelo
# ══════════════════════════════════════════════════════════════════════════════

zona("03", "El duelo", "Los dos lados al mismo punto: al bolsillo, después de impuestos.")

duelo = duelo_portafolio_contra_emisora(
    inmuebles,
    ticker=ticker,
    yield_bruto_emisora=float(yield_bruto),
    crecimiento_emisora=crecimiento,
    plusvalia_esperada=plusvalia,
    ingreso_por_sueldo=sueldo,
    tiene_w8ben=tiene_w8ben,
)

if not duelo.hay_inmuebles:
    st.info(
        "Captura al menos una propiedad arriba para ver el duelo. Mientras tanto, "
        f"{ticker} paga **{pct(duelo.emisora.yield_neto)} neto** de impuestos "
        f"({pct(duelo.emisora.yield_bruto)} bruto)."
    )
    st.stop()

gana_ladrillo = duelo.ganador == "Tus inmuebles"
izq, der = st.columns([1.4, 1], gap="medium")
with izq:
    panel_veredicto(
        accion=duelo.ganador.upper(),
        color=PROFIT if gana_ladrillo else COLOR_LUZ["AMARILLO"],
        explicacion=duelo.mensaje,
        coda="Es el flujo del próximo año. No incluye plusvalía ni la fricción de salir.",
    )
with der:
    rejilla_cifras([
        (
            "Tus inmuebles, neto",
            pct(duelo.inmuebles.yield_neto),
            f"{pct(duelo.inmuebles.yield_bruto)} bruto",
            PROFIT if gana_ladrillo else "",
        ),
        (
            f"{ticker}, neto",
            pct(duelo.emisora.yield_neto),
            f"{pct(duelo.emisora.yield_bruto)} bruto",
            "" if gana_ladrillo else COLOR_LUZ["AMARILLO"],
        ),
    ])
    rejilla_cifras([
        (
            "Brecha",
            bps(duelo.brecha_bps / 10_000),
            "a favor del ladrillo" if gana_ladrillo else f"a favor de {ticker}",
            PROFIT if gana_ladrillo else LOSS,
        ),
        (
            "Sobre tu valor de mercado",
            dinero(duelo.inmuebles.valor_mercado, "MXN", 0),
            f"{duelo.inmuebles.n_propiedades} propiedad(es)",
            "",
        ),
    ])

st.markdown("###### Del bruto al bolsillo, los dos lados")
c1, c2 = st.columns(2, gap="medium")
with c1:
    tarjeta_abre(
        f"Tus {duelo.inmuebles.n_propiedades} propiedades",
        "La renta bruta no es lo que te queda: hay gastos y hay ISR.",
    )
    cascada_inm = duelo.inmuebles.como_tabla()
    cascada_inm["pct"] = cascada_inm["monto"] / duelo.inmuebles.valor_mercado
    mostrar_tabla(
        cascada_inm,
        column_config={
            "concepto": "Concepto",
            "monto": st.column_config.NumberColumn("MXN al año", format="$%,.0f"),
            "pct": st.column_config.NumberColumn("Sobre el valor", format="%.2f%%"),
        },
    )
    tarjeta_cierra(
        f"ISR efectivo sobre la renta: <strong>{pct(duelo.inmuebles.tasa_efectiva_isr)}</strong>. "
        + (
            "Con sueldo declarado, la renta se apila y entra en tasa marginal."
            if sueldo > 0
            else "Sin sueldo declarado. Si lo agregas en la barra lateral, esta tasa sube fuerte."
        )
    )
with c2:
    tarjeta_abre(
        f"{ticker}",
        "El dividendo tampoco llega entero: hay retención allá e ISR aquí.",
    )
    cascada_reit = duelo.emisora.como_tabla()
    cascada_reit["mxn"] = cascada_reit["monto"] * duelo.inmuebles.valor_mercado
    mostrar_tabla(
        cascada_reit,
        column_config={
            "concepto": "Concepto",
            "monto": st.column_config.NumberColumn("Sobre el valor", format="%.2f%%"),
            "mxn": st.column_config.NumberColumn(
                "MXN al año", format="$%,.0f",
                help="Lo que pagaría si movieras el mismo capital a esta emisora.",
            ),
        },
    )
    tarjeta_cierra(
        "Retención de EE. UU. al "
        + ("<strong>10%</strong> con W-8BEN. " if tiene_w8ben else "<strong>30%</strong> sin W-8BEN. ")
        + "El ISR mexicano adicional no depende de cuánto ganes: es tasa fija sobre dividendo "
        "extranjero."
    )

# ══════════════════════════════════════════════════════════════════════════════
# 04 · Una por una
# ══════════════════════════════════════════════════════════════════════════════

zona("04", "Una por una", "El portafolio puede ganar y aun así tener una propiedad que pierde.")

detalle = comparar_portafolio_propio(
    inmuebles, yield_neto_reits=duelo.emisora.yield_neto, inflacion=INFLACION
)
vista = detalle.copy()
for col in ("rendimiento_corriente", "tir_nominal", "tir_real", "plusvalia_anualizada",
            "yield_neto_reits", "brecha_vs_reits"):
    vista[col] = pd.to_numeric(vista[col], errors="coerce")
vista = vista.sort_values("brecha_vs_reits", ascending=False)

figura = go.Figure()
figura.add_bar(
    x=vista["brecha_vs_reits"] * 10_000,
    y=vista["nombre"],
    orientation="h",
    marker_color=[PROFIT if v > 0 else LOSS for v in vista["brecha_vs_reits"].fillna(0)],
)
figura.add_vline(x=0, line_color=GRIS, line_width=1)
figura.update_layout(**plantilla_plotly())
figura.update_layout(
    height=max(160, 46 * len(vista) + 60),
    margin={"t": 10, "b": 30, "l": 4, "r": 4},
    xaxis={
        "title": f"Puntos base contra {ticker}, sobre el flujo corriente",
        "gridcolor": LINEA, "tickfont": {"size": 10, "color": GRIS, "family": MONO},
    },
    yaxis={"tickfont": {"size": 11, "color": GRIS}},
)
st.plotly_chart(figura, key="brecha_por_inmueble")

mostrar_tabla(
    vista,
    column_config={
        "nombre": "Propiedad",
        "valor_actual": st.column_config.NumberColumn("Valor hoy", format="$%,.0f"),
        "rendimiento_corriente": st.column_config.NumberColumn("Flujo corriente", format="%.2f%%"),
        "tir_nominal": st.column_config.NumberColumn("TIR nominal", format="%.2f%%"),
        "tir_real": st.column_config.NumberColumn("TIR REAL", format="%.2f%%"),
        "plusvalia_anualizada": st.column_config.NumberColumn("Plusvalía anualizada", format="%.2f%%"),
        "yield_neto_reits": st.column_config.NumberColumn(f"{ticker} neto", format="%.2f%%"),
        "brecha_vs_reits": st.column_config.NumberColumn("Brecha", format="%.2f%%"),
    },
)

negativas = detalle[pd.to_numeric(detalle["tir_real"], errors="coerce") < 0]
if not negativas.empty:
    st.error(
        "**TIR real negativa** —pierden poder adquisitivo, no solo rinden poco—: "
        + ", ".join(negativas["nombre"])
    )
st.caption(
    "El flujo corriente de cada propiedad se mide **bruto de ISR**, porque el impuesto de "
    "arrendamiento se calcula sobre el total y no se puede repartir entre propiedades sin "
    "inventar una regla. La comparación agregada de la zona 03 sí lo descuenta, y es la que "
    "manda para decidir. Aquí lo que interesa es el orden entre las tuyas."
)

# ══════════════════════════════════════════════════════════════════════════════
# 05 · Qué faltaría
# ══════════════════════════════════════════════════════════════════════════════

zona("05", "Qué tendría que pasar", "Si el REIT gana en flujo, el ladrillo necesita plusvalía.")

if duelo.plusvalia_necesaria is not None:
    brecha_plus = duelo.plusvalia_necesaria - plusvalia
    c1, c2, c3 = st.columns(3)
    c1.metric("Plusvalía anual para empatar", pct(duelo.plusvalia_necesaria))
    c2.metric("La que esperas", pct(plusvalia))
    c3.metric(
        "Distancia", bps(brecha_plus),
        delta=f"{'falta' if brecha_plus > 0 else 'sobra'}",
        delta_color="inverse" if brecha_plus > 0 else "normal",
    )
    st.caption(
        f"Inflación al corte: **{pct(INFLACION)}**. Cuando la plusvalía necesaria sale muy por "
        "encima de la inflación, la tesis del inmueble deja de ser la renta y pasa a ser una "
        "apuesta direccional a la apreciación. Es legítima, pero es otra tesis, con otro "
        "riesgo y sin flujo que la sostenga mientras esperas."
    )

# ══════════════════════════════════════════════════════════════════════════════
# 06 · Lo que el flujo no dice
# ══════════════════════════════════════════════════════════════════════════════

zona("06", "Lo que el flujo no dice", "El duelo compara rendimiento. Falta lo demás.")

referencia = SupuestosInmueble(
    precio=duelo.inmuebles.valor_mercado or 1.0,
    renta_mensual=duelo.inmuebles.renta_bruta_anual / 12.0 if duelo.inmuebles.renta_bruta_anual else 0.0,
    anios=10,
    plusvalia_anual=plusvalia,
    inflacion=INFLACION,
    ingreso_por_sueldo=sueldo,
)
resultado = evaluar_inmueble(referencia, tasa_descuento=0.09)

c1, c2, c3 = st.columns(3)
c1.metric(
    "Fricción de salir, ida y vuelta", pct(resultado.friccion_transaccion),
    help="ISAI, notario y comisión. Se paga aunque el inmueble no suba un peso.",
)
c2.metric("ISR sobre la ganancia al vender", pct(resultado.isr_salida_pct))
c3.metric(
    "Concentración", f"{duelo.inmuebles.n_propiedades}",
    help="Número de activos. Un REIT del universo tiene cientos de inquilinos.",
)

with st.expander("Riesgos que no entran en el rendimiento"):
    mostrar_tabla(pd.DataFrame(RIESGOS_CUALITATIVOS))
    st.warning(AVISO_INDICES)

st.info(
    "**Restricción de modelación explícita.** Las horas propias de administración van a costo "
    "cero: esto mide retorno sobre capital, no sobre tiempo. Si valoras tu tiempo, el lado del "
    "ladrillo es peor que el que aquí se muestra. El REIT no te cobra horas."
)
descargo()
