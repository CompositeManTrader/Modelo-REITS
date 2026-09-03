"""Valuación individual: la cascada línea por línea y las tres puertas."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from comun import (  # noqa: E402
    avisar_latencia,
    avisar_procedencia,
    avisos,
    bps,
    configurar,
    descargo,
    dinero,
    exigir_base,
    explicar,
    pct,
    selector_de_corte,
    selector_de_emisor,
    semaforo_html,
    veces,
)

from src.config import DIR_EXPORTES  # noqa: E402
from src.export.excel import DatosExportacion, exportar  # noqa: E402
from src.modelo.cascada import CLAVES_TRAMPA, REPORTE, calcular_cascada  # noqa: E402
from src.modelo.kill import tabla_liston_friccion, venta_parcial_sugerida  # noqa: E402
from src.modelo.sectorial import metricas_especificas, perfil  # noqa: E402
from src.modelo.senal import sesgo_por_ventana_completa  # noqa: E402
from src.modelo.valuacion import InsumosValuacion, sensibilidad_nav  # noqa: E402
from src.servicio import construir_panel, evaluar  # noqa: E402

configurar("Valuación", "📊")
st.title("Valuación individual")

repo = exigir_base()
asof = selector_de_corte()
ticker = selector_de_emisor(repo)
if ticker is None:
    st.stop()

st.sidebar.divider()
st.sidebar.markdown("**Supuestos del modelo**")
cap_rate = st.sidebar.slider(
    "Cap rate de mercado para el NAV", 0.045, 0.100, 0.065, 0.0025, format="%.4f",
    help="La palanca MÁS sensible del modelo. Por eso es tuya y viene con tabla de sensibilidad.",
)
yield_adq = st.sidebar.slider(
    "Yield de adquisiciones del emisor", 0.03, 0.12, 0.074, 0.0025, format="%.4f",
    help="A qué cap rate está comprando activos. Contra el costo del capital da el spread de inversión.",
)

panel = construir_panel(
    repo, ticker, asof=asof, cap_rate_mercado=cap_rate, yield_adquisiciones=yield_adq
)
semaforo = evaluar(panel)

st.subheader(f"{ticker} — {panel.sector}")
avisar_procedencia(panel.fuentes)
avisar_latencia(panel.precio_fecha, asof, "precio de cierre sin ajustar")
avisos(panel.avisos)

if panel.trimestral.empty:
    st.error("No hay fundamentales para este emisor al corte elegido.")
    st.stop()

# --------------------------------------------------------------------------------------
# Las tres puertas
# --------------------------------------------------------------------------------------

st.header("Semáforo: las tres puertas, por separado")
st.markdown(
    f"### Acción: `{semaforo.accion.value}`\n\n{semaforo.explicacion}"
)

c1, c2, c3 = st.columns(3)
for columna, puerta, titulo in (
    (c1, semaforo.calidad, "Puerta 1 — Calidad"),
    (c2, semaforo.valuacion, "Puerta 2 — Valuación"),
    (c3, semaforo.deterioro, "Puerta 3 — Deterioro"),
):
    with columna:
        st.markdown(f"**{titulo}**")
        st.markdown(semaforo_html(puerta.luz.value, puerta.mensaje), unsafe_allow_html=True)
        if not puerta.criterios.empty:
            st.dataframe(
                puerta.criterios[[c for c in ("criterio", "valor", "umbral", "cumple", "racha", "dispara")
                                  if c in puerta.criterios]],
                hide_index=True, width="stretch",
            )

st.info(
    "**Regla de venta.** Vender por precio caro es distinto de vender por tesis rota. "
    "La Puerta 2 nunca dispara venta por sí sola: modula compras nuevas. **Solo la Puerta 3 "
    "vende.** Si quieres vender por valuación de todos modos, abajo está el costo."
)

with st.expander("Quiero vender por valuación de todos modos"):
    valor_posicion = st.number_input("Valor de tu posición (USD)", 0.0, value=100_000.0, step=5_000.0)
    ganancia = st.slider("Ganancia acumulada sobre el costo", 0.0, 3.0, 0.40, 0.05, format="%.2f")
    sugerencia = venta_parcial_sugerida(valor_posicion, ganancia_acumulada=ganancia)
    a, b, c = st.columns(3)
    a.metric("Venta parcial sugerida", f"{sugerencia['fraccion_sugerida']:.0%}")
    b.metric("Costo fiscal estimado", dinero(sugerencia["costo_fiscal_estimado"]))
    c.metric("Ventaja anual necesaria", f"{sugerencia['ventaja_anual_necesaria_bps']:,.0f} bps",
             help="Cuánto más tiene que rendir el destino, al año, para recuperar el costo fiscal en dos años.")
    st.warning(sugerencia["advertencia"])
    st.markdown("**El listón de fricción según cuánto llevas ganado:**")
    st.dataframe(tabla_liston_friccion(), hide_index=True, width="stretch")

explicar("AFFO", "prima", "percentil expandible", "spread de inversión")

st.divider()

# --------------------------------------------------------------------------------------
# Cascada
# --------------------------------------------------------------------------------------

st.header("La cascada: NOI → FFO → FFO Normalizado → AFFO")
st.caption(
    "Esta es la razón por la que el AFFO es el número y no la utilidad neta. Realty Income "
    "Q2 2026: utilidad neta por acción 0.37 dólares contra AFFO de 1.09, una razón de 2.97x. "
    "El payout sobre utilidad neta da 222% y sobre AFFO da 73%."
)

periodos = repo.hechos(asof=asof, tickers=ticker, conceptos="affo", periodo_tipo="Q")
fecha_cascada = None
if not periodos.empty:
    opciones = sorted(pd.to_datetime(periodos["fecha_dato"]).dt.date.unique(), reverse=True)
    fecha_cascada = st.selectbox("Trimestre", opciones, format_func=str)

conciliacion = (
    repo.conciliacion(ticker, fecha_cascada, asof=asof) if fecha_cascada else pd.DataFrame()
)

if not conciliacion.empty:
    detalle = conciliacion.copy()
    detalle["trampa"] = detalle["linea"].isin(CLAVES_TRAMPA)
    detalle["Línea"] = detalle.apply(
        lambda r: ("⚠️ " if r["trampa"] else "") + str(r["etiqueta"]), axis=1
    )
    st.dataframe(
        detalle[["Línea", "valor", "linea"]].rename(
            columns={"valor": "Monto (USD)", "linea": "Concepto normalizado"}
        ),
        hide_index=True,
        width="stretch",
        column_config={"Monto (USD)": st.column_config.NumberColumn(format="$%,.0f")},
    )
    st.caption(
        "⚠️ marca las tres trampas del AFFO: renta en línea recta, CapEx de mantenimiento y "
        "revaluación a valor razonable. Los montos vienen con el signo del reporte, listos "
        "para sumarse: así se reproduce exactamente el subtotal que publica el emisor."
    )

    lineas = {r["linea"]: float(r["valor"]) for _, r in conciliacion.iterrows()}
    resultado = calcular_cascada(lineas, sector=panel.sector, signos=REPORTE)
    for bandera in resultado.banderas:
        st.warning(bandera)
    explicar("NOI", "FFO", "renta en línea recta", "CapEx de mantenimiento")
else:
    st.info(
        "No hay conciliación línea por línea para este trimestre. La conciliación se extrae del "
        "Exhibit 99.1 de los 8-K de resultados: corre `python scripts/ingesta.py` para traerla."
    )

st.divider()

# --------------------------------------------------------------------------------------
# Métricas
# --------------------------------------------------------------------------------------

st.header("Panel de valuación")
m = panel.metricas

f1, f2, f3, f4 = st.columns(4)
f1.metric("AFFO yield", pct(m.get("affo_yield")))
f2.metric("P / AFFO", veces(m.get("p_affo")))
f3.metric("Dividend yield", pct(m.get("dividend_yield")))
f4.metric("Cap rate implícito", pct(m.get("cap_rate_implicito")))

st.subheader("Cobertura del dividendo: el mismo dividendo, tres respuestas")
g1, g2, g3 = st.columns(3)
g1.metric("Payout sobre AFFO", pct(m.get("payout_affo")),
          help="La única cobertura que significa algo. Umbral de la Puerta 1: menor a 90%.")
g2.metric("Payout sobre FFO", pct(m.get("payout_ffo")))
g3.metric("Payout sobre utilidad neta", pct(m.get("payout_utilidad_neta")),
          help="El número que publican los sitios financieros. Está mal. Se muestra para que veas el tamaño del error.")
if m.get("payout_utilidad_neta") and m.get("payout_affo"):
    razon = m["payout_utilidad_neta"] / m["payout_affo"]
    st.caption(
        f"El payout sobre utilidad neta es **{razon:.1f} veces** el payout sobre AFFO. "
        "Esa es exactamente la magnitud del error que comete quien usa el número equivocado."
    )

st.subheader("Prima sobre la tasa libre de riesgo")
p1, p2, p3 = st.columns(3)
prima_actual = panel.prima.dropna().iloc[-1] if not panel.prima.dropna().empty else None
p1.metric("Prima", bps(prima_actual))
p2.metric("Percentil de su propia historia",
          pct(panel.percentil_actual, 0) if panel.percentil_actual is not None else "INCONCLUSO")
p3.metric("Observaciones", f"{panel.n_observaciones}")

if not panel.prima.dropna().empty:
    figura = go.Figure()
    figura.add_scatter(
        x=panel.prima.index, y=panel.prima * 10_000, name="Prima (bps)",
        line={"color": "#0969da"},
    )
    figura.update_layout(
        height=280, margin={"t": 20, "b": 20, "l": 10, "r": 10},
        yaxis_title="Puntos base sobre UST 10 años", showlegend=False,
    )
    st.plotly_chart(figura, width="stretch")

    with st.expander("Por qué el percentil usa ventana expandible y no la muestra completa"):
        sesgo = sesgo_por_ventana_completa(panel.prima.dropna())
        fig2 = go.Figure()
        fig2.add_scatter(x=sesgo.index, y=sesgo["expandible"], name="Expandible (lo correcto)",
                         line={"color": "#1a7f37"})
        fig2.add_scatter(x=sesgo.index, y=sesgo["muestra_completa"], name="Muestra completa (usa el futuro)",
                         line={"color": "#b42318", "dash": "dash"})
        fig2.update_layout(height=280, yaxis_tickformat=".0%",
                           margin={"t": 20, "b": 20, "l": 10, "r": 10},
                           legend={"orientation": "h", "y": 1.15})
        st.plotly_chart(fig2, width="stretch")
        brecha = sesgo["diferencia"].abs().mean()
        st.markdown(
            f"La diferencia media entre ambas es de **{brecha:.0%} de percentil**. La curva roja "
            "sabe, en 2019, que el yield iba a llegar a su máximo en 2023. Nadie lo sabía. "
            "Fijar umbrales con esa curva es fijarlos con información del futuro."
        )

st.divider()

# --------------------------------------------------------------------------------------
# NAV y sensibilidad
# --------------------------------------------------------------------------------------

st.header("NAV y su sensibilidad al cap rate")
explicar("NAV", "cap rate implícito", "dilución oculta")

n1, n2 = st.columns([1, 2])
with n1:
    st.metric("NAV por acción", dinero(m.get("nav_por_accion")))
    st.metric("Premio (+) / descuento (−) del precio", pct(m.get("premio_descuento_nav"), 1))
    st.metric("Cap rate que descuenta el mercado", pct(m.get("cap_rate_descontado_por_el_mercado")),
              help="Da vuelta a la pregunta: en vez de suponer un cap rate, muestra el que el precio implica.")
with n2:
    ultima = panel.trimestral.dropna(subset=["affo_por_accion_ttm"]).tail(1)
    if not ultima.empty:
        fila = ultima.iloc[0]
        ins = InsumosValuacion(
            ticker=ticker,
            precio=panel.precio or 0.0,
            acciones_diluidas=float(fila.get("acciones_diluidas") or 1.0),
            noi_trimestral=float(fila.get("noi") or 0.0) or None,
            affo_por_accion_ttm=float(fila.get("affo_por_accion_ttm") or 0.0) or None,
            dividendo_ttm_por_accion=panel.dividendo_ttm,
            sector=panel.sector,
        )
        tabla = sensibilidad_nav(ins)
        if not tabla.empty:
            figura = go.Figure()
            figura.add_scatter(x=tabla["cap_rate"], y=tabla["nav_por_accion"],
                               name="NAV por acción", line={"color": "#0969da"})
            figura.add_hline(y=panel.precio, line_dash="dash", line_color="#b42318",
                             annotation_text="Precio de mercado")
            figura.update_layout(height=300, xaxis_tickformat=".2%",
                                 xaxis_title="Cap rate de mercado", yaxis_title="NAV por acción (USD)",
                                 margin={"t": 20, "b": 20, "l": 10, "r": 10}, showlegend=False)
            st.plotly_chart(figura, width="stretch")
            st.caption(
                "Mira esta curva antes de creerte un NAV puntual: 50 puntos base de cap rate "
                "cambian el NAV más que casi cualquier otro supuesto del modelo."
            )

st.divider()

# --------------------------------------------------------------------------------------
# Contexto sectorial
# --------------------------------------------------------------------------------------

st.header(f"Qué mirar en un REIT de {panel.sector}")
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

st.divider()

# --------------------------------------------------------------------------------------
# Serie trimestral y fuentes
# --------------------------------------------------------------------------------------

st.header("Serie trimestral")
st.dataframe(panel.trimestral.tail(20), width="stretch")

st.header("Fuentes y procedencia")
st.caption(
    "Primario significa que viene directo de la SEC o de un banco central. Derivado o "
    "reconstruido significa que lo calculó el modelo y hereda el error de sus componentes."
)
if not panel.fuentes.empty:
    st.dataframe(panel.fuentes.head(60), width="stretch", hide_index=True)

# --------------------------------------------------------------------------------------
# Exportación
# --------------------------------------------------------------------------------------

st.divider()
st.header("Exportar a Excel")
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
        ins = InsumosValuacion(
            ticker=ticker,
            precio=panel.precio or 0.0,
            acciones_diluidas=float(fila.get("acciones_diluidas") or 1.0),
            noi_trimestral=float(fila.get("noi") or 0.0) or None,
            affo_ttm=float(fila.get("affo_ttm") or 0.0) or None,
            affo_por_accion_ttm=float(fila.get("affo_por_accion_ttm") or 0.0) or None,
            ffo_ttm=float(fila.get("ffo") or 0.0) * 4 or None,
            utilidad_neta_ttm=float(fila.get("utilidad_neta") or 0.0) * 4 or None,
            dividendo_ttm_por_accion=panel.dividendo_ttm,
            sector=panel.sector,
        )
        componentes = (
            {r["linea"]: float(r["valor"]) for _, r in conciliacion.iterrows()}
            if not conciliacion.empty
            else {}
        )
        emisores = repo.emisores()
        nombre = emisores.loc[emisores["ticker"] == ticker, "nombre"]
        datos = DatosExportacion(
            ticker=ticker,
            nombre=str(nombre.iloc[0]) if not nombre.empty else ticker,
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

st.divider()
descargo()
