"""Comparativa sectorial: rankings válidos, mapa de calor y reloj de prima."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from comun import (  # noqa: E402
    configurar,
    descargo,
    exigir_base,
    explicar,
    mostrar_tabla,
    selector_de_corte,
)

from src.modelo.sectorial import (  # noqa: E402
    CONTEXTO_HISTORICO,
    DISPERSION_SECTORIAL,
    mapa_de_calor,
    metricas_especificas,
    percentil_contra_sector,
    ranking_dentro_del_sector,
    reloj_de_prima,
    tabla_perfiles,
    validar_comparacion,
)
from src.modelo.senal import (  # noqa: E402
    ComparacionInvalida,
    comparar_emisores,
    comparar_yields_crudos,
)
from src.servicio import construir_panel, tabla_universo  # noqa: E402

configurar("Sectorial", "🗺️")
st.title("Valuación sectorial y comparativa")

repo = exigir_base()
asof = selector_de_corte()

st.warning(
    "**Los trece sectores de Nareit tienen economías completamente distintas.** Una torre de "
    "telecomunicaciones firma a veinte años y no consume CapEx; una oficina se renegocia cada "
    "cinco y devora mejoras al inquilino. Los rankings de múltiplos solo son válidos **dentro "
    "del mismo sector**. Lo único que sí cruza sectores es el percentil de la prima, porque "
    "cada emisor se mide contra sí mismo."
)

universo = tabla_universo(repo, asof=asof)
if universo.empty:
    st.error("No hay emisores con datos al corte elegido.")
    st.stop()

# --------------------------------------------------------------------------------------
# Ranking dentro del sector
# --------------------------------------------------------------------------------------

st.header("Ranking dentro de cada sector")
ranking = ranking_dentro_del_sector(universo.dropna(subset=["percentil_prima"]))
if ranking.empty:
    st.info("Ningún emisor tiene historia suficiente para emitir percentil de prima.")
else:
    for sector, grupo in ranking.groupby("sector"):
        st.subheader(sector)
        vista = grupo[
            ["ranking_en_sector", "ticker", "nombre", "percentil_prima", "affo_yield",
             "p_affo", "payout_affo", "accion"]
        ].copy()
        mostrar_tabla(
            vista,
            column_config={
                "ranking_en_sector": st.column_config.NumberColumn("#", format="%d"),
                "ticker": "Emisor",
                "nombre": "Nombre",
                "percentil_prima": st.column_config.ProgressColumn(
                    "Percentil de prima", min_value=0.0, max_value=100.0, format="%.0f%%"),
                "p_affo": st.column_config.NumberColumn("P/AFFO", format="%.1fx"),
                "accion": "Acción",
            },
        )
        for metrica, texto in list(metricas_especificas(sector).items())[:3]:
            st.caption(f"**{metrica}** — {texto}")

# --------------------------------------------------------------------------------------
# Comparación entre sectores
# --------------------------------------------------------------------------------------

st.divider()
st.header("Comparar emisores de sectores distintos")

seleccion = st.multiselect(
    "Elige emisores", sorted(universo["ticker"]), default=list(universo["ticker"].head(4))
)
if seleccion:
    sub = universo[universo["ticker"].isin(seleccion)]
    advertencia = validar_comparacion(list(sub["sector"]))
    if advertencia:
        st.warning(advertencia)

    percentiles = {
        r["ticker"]: r["percentil_prima"]
        for _, r in sub.iterrows()
        if pd.notna(r["percentil_prima"])
    }
    if percentiles:
        comparacion = comparar_emisores(
            percentiles, sectores=dict(zip(sub["ticker"], sub["sector"], strict=False))
        )
        figura = go.Figure()
        figura.add_bar(
            x=comparacion["ticker"], y=comparacion["percentil_prima"],
            marker_color=["#1a7f37" if v >= 0.7 else "#9a6700" if v >= 0.3 else "#b42318"
                          for v in comparacion["percentil_prima"]],
            text=[f"{v:.0%}" for v in comparacion["percentil_prima"]], textposition="outside",
            customdata=comparacion["sector"],
            hovertemplate="%{x} (%{customdata})<br>Percentil: %{y:.0%}<extra></extra>",
        )
        figura.update_layout(
            height=320, yaxis_tickformat=".0%", yaxis_range=[0, 1.1],
            yaxis_title="Percentil de la prima contra su propia historia",
            margin={"t": 20, "b": 20, "l": 10, "r": 10}, showlegend=False,
        )
        st.plotly_chart(figura)
        st.caption(
            "Un REIT de data centers con 2.5% de prima en el percentil 95 de su historia está "
            "**más barato** que uno de oficinas con 9% en el percentil 20 de la suya. El nivel "
            "de yield no dice nada; el percentil contra la propia historia sí."
        )
    else:
        st.info("Ninguno de los emisores elegidos tiene historia suficiente para su percentil.")

with st.expander("Por qué la aplicación se niega a ordenar por nivel de yield"):
    st.markdown(
        "Rotar hacia «el que paga más» es rotar hacia el deterioro. El yield tiene el precio "
        "en el denominador, así que un precio que se desploma lo infla mecánicamente. Así se "
        "llega a W. P. Carey justo antes de que recorte, o a Global Net Lease en plena dilución.\n\n"
        "El código lo hace imposible por construcción: existe una función cuyo único propósito "
        "es fallar si alguien la llama."
    )
    if st.button("Intentar ordenar por nivel de yield"):
        try:
            comparar_yields_crudos(universo)
        except ComparacionInvalida as exc:
            st.error(f"`ComparacionInvalida`: {exc}")

# --------------------------------------------------------------------------------------
# Mapa de calor y reloj de prima
# --------------------------------------------------------------------------------------

st.divider()
st.header("Mapa de calor: percentil de prima por sector en el tiempo")

historico = []
for _, e in universo.iterrows():
    panel = construir_panel(repo, e["ticker"], asof=asof)
    if panel.prima.dropna().empty:
        continue
    df = pd.DataFrame({"prima": panel.prima.dropna()})
    df["ticker"] = e["ticker"]
    df["sector"] = e["sector"]
    df["fecha_dato"] = df.index
    crecimiento = panel.trimestral.get("crecimiento_affo_por_accion_yoy")
    if crecimiento is not None:
        df["crecimiento_affo_por_accion_yoy"] = pd.to_numeric(
            crecimiento, errors="coerce"
        ).reindex(df.index)
    historico.append(df.reset_index(drop=True))

if historico:
    panel_historico = percentil_contra_sector(pd.concat(historico, ignore_index=True))
    matriz = mapa_de_calor(panel_historico)
    if not matriz.empty:
        # Se muestrea a fin de trimestre para que el eje sea legible.
        matriz = matriz.loc[:, ::max(1, len(matriz.columns) // 40)]
        figura = px.imshow(
            matriz, aspect="auto", color_continuous_scale="RdYlGn", zmin=0, zmax=1,
            labels={"color": "Percentil de prima"},
        )
        figura.update_layout(height=340, margin={"t": 20, "b": 20, "l": 10, "r": 10})
        st.plotly_chart(figura)
        st.caption(
            "Verde = el sector paga más prima que en su propia historia (barato). "
            "Rojo = paga menos (caro). Cada fila se mide contra sí misma, no contra las otras."
        )

    st.subheader("Reloj de prima sectorial")
    st.caption(
        "Percentil de prima contra crecimiento del AFFO. Muestra dónde ha estado el dinero "
        "barato y dónde está hoy."
    )
    reloj = reloj_de_prima(panel_historico)
    if not reloj.empty:
        reloj["anio"] = pd.to_datetime(reloj["fecha_dato"]).dt.year
        figura = px.scatter(
            reloj, x="crecimiento_affo_por_accion_yoy", y="percentil_sector",
            color="sector", animation_frame="anio", size_max=20,
            hover_name="sector", range_y=[0, 1],
            labels={
                "crecimiento_affo_por_accion_yoy": "Crecimiento del AFFO por acción (YoY)",
                "percentil_sector": "Percentil de prima del sector",
            },
        )
        figura.add_hline(y=0.5, line_dash="dot", line_color="#57606a")
        figura.add_vline(x=0.0, line_dash="dot", line_color="#57606a")
        figura.update_layout(height=460, xaxis_tickformat=".0%", yaxis_tickformat=".0%")
        st.plotly_chart(figura)
        st.markdown(
            "**Los cuatro cuadrantes:** arriba a la derecha, barato y creciendo — donde uno "
            "quiere estar. Arriba a la izquierda, barato y encogiendo: trampa de valor, el "
            "mercado suele tener razón. Abajo a la derecha, caro y creciendo: se paga por el "
            "crecimiento, funciona hasta que deja de crecer. Abajo a la izquierda, lo peor de "
            "ambos mundos."
        )
    else:
        st.info("No hay suficiente historia de crecimiento del AFFO para armar el reloj.")
else:
    st.info("No hay historia de prima suficiente para el mapa de calor.")

# --------------------------------------------------------------------------------------
# Contexto y perfiles
# --------------------------------------------------------------------------------------

st.divider()
st.header("Dispersión sectorial: por qué no extrapolar de un solo nombre")
c1, c2 = st.columns([1, 1])
with c1:
    mostrar_tabla(
        DISPERSION_SECTORIAL,
        column_config={
            "sector": st.column_config.TextColumn("Sector"),
            "periodo": st.column_config.TextColumn("Periodo"),
            "rendimiento": st.column_config.NumberColumn("Rendimiento", format="%.1f%%"),
            "lugar": st.column_config.TextColumn("Nota"),
        },
    )
with c2:
    for item in CONTEXTO_HISTORICO:
        st.markdown(f"**{item['hecho']}**")
        st.caption(item["leccion"])

with st.expander("Perfil económico de los trece sectores"):
    mostrar_tabla(tabla_perfiles())

explicar("prima", "percentil expandible")
st.divider()
descargo()
