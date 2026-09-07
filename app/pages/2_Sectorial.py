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
from marca import (  # noqa: E402
    AMBAR,
    GRIS,
    LOSS,
    PROFIT,
    encabezado,
    escala_ambar,
    inyectar_estilos,
)

from src.modelo.sectorial import (  # noqa: E402
    CONTEXTO_HISTORICO,
    DISPERSION_SECTORIAL,
    FORMATO_PERCENTIL_TABLA,
    MIN_OBSERVACIONES_PERCENTIL,
    cobertura_del_percentil,
    cuantizar_percentil,
    huecos_del_ranking,
    mapa_de_calor,
    metricas_especificas,
    muestrear_columnas,
    percentil_contra_sector,
    ranking_dentro_del_sector,
    reloj_de_prima,
    tabla_perfiles,
    texto_percentil,
    validar_comparacion,
)
from src.modelo.senal import (  # noqa: E402
    ComparacionInvalida,
    comparar_emisores,
    comparar_yields_crudos,
)
from src.servicio import construir_panel, tabla_universo  # noqa: E402

configurar("Sectorial", "🗺️")
inyectar_estilos()
encabezado("Sectorial")
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
con_percentil = universo.dropna(subset=["percentil_prima"])
ranking = ranking_dentro_del_sector(con_percentil)

# Un hueco tiene nombre. El respaldo de abajo solo se dispara cuando el ranking
# queda ENTERAMENTE vacío, y el caso normal no es ese: es que la mayoría de las
# emisoras todavía no junta historia. Sin este aviso, la pantalla decía "ranking
# dentro de cada sector" y dibujaba un sector con dos nombres, sin explicar dónde
# quedaron los otros ocho ni los otros tres sectores.
sin_historia, sectores_ausentes = huecos_del_ranking(universo)
if sin_historia:
    st.info(
        f"**{len(sin_historia)} de {len(universo)} emisoras no aparecen todavía**: "
        f"{', '.join(sin_historia)}. Les falta historia para emitir un percentil de "
        f"prima, que exige {MIN_OBSERVACIONES_PERCENTIL} observaciones. "
        + (f"Con ellas quedan fuera sectores completos: {', '.join(sectores_ausentes)}."
           if sectores_ausentes else "")
    )

if ranking.empty:
    st.info("Ningún emisor tiene historia suficiente para emitir percentil de prima.")
else:
    for sector, grupo in ranking.groupby("sector"):
        st.subheader(sector)
        vista = grupo[
            ["ranking_en_sector", "ticker", "nombre", "percentil_prima", "affo_yield",
             "p_affo", "payout_affo", "accion"]
        ].copy()
        # El percentil se redondea en Python antes de dibujarlo. Streamlit formatea
        # en JavaScript, que en el empate redondea hacia arriba, y la gráfica de
        # abajo lo formatea en Python, que redondea al par: el mismo 0.125 salía
        # "13%" aquí y "12%" allá, a dos dedos de distancia. Entregando el dato ya
        # cuantizado, ninguno de los dos tiene un empate que romper.
        vista["percentil_prima"] = cuantizar_percentil(vista["percentil_prima"])
        mostrar_tabla(
            vista,
            column_config={
                "ranking_en_sector": st.column_config.NumberColumn("#", format="%d"),
                "ticker": "Emisor",
                "nombre": "Nombre",
                "percentil_prima": st.column_config.ProgressColumn(
                    "Percentil de prima", min_value=0.0, max_value=100.0,
                    format=FORMATO_PERCENTIL_TABLA),
                "p_affo": st.column_config.NumberColumn("P/AFFO", format="%.1fx"),
                "accion": "Acción",
            },
        )
        # Todas las métricas del sector, no las tres primeras: net lease y self
        # storage tienen cuatro, y la cuarta se ocultaba sin decirlo.
        for metrica, texto in metricas_especificas(sector).items():
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
        r["ticker"]: cuantizar_percentil(r["percentil_prima"])
        for _, r in sub.iterrows()
        if pd.notna(r["percentil_prima"])
    }
    # Elegir cuatro emisoras y recibir dos barras, sin explicación, es peor que
    # recibir ninguna: quien lee cuenta las barras y supone que eligió mal.
    sin_percentil, _ = huecos_del_ranking(sub)
    if sin_percentil and percentiles:
        st.caption(
            f"No se dibujan {', '.join(sin_percentil)}: todavía no tienen las "
            f"{MIN_OBSERVACIONES_PERCENTIL} observaciones que exige el percentil."
        )
    if percentiles:
        comparacion = comparar_emisores(
            percentiles, sectores=dict(zip(sub["ticker"], sub["sector"], strict=False))
        )
        figura = go.Figure()
        figura.add_bar(
            x=comparacion["ticker"], y=comparacion["percentil_prima"],
            marker_color=[PROFIT if v >= 0.7 else AMBAR if v >= 0.3 else LOSS
                          for v in comparacion["percentil_prima"]],
            # Los mismos decimales que la tabla de arriba, y sobre el mismo dato ya
            # cuantizado: es lo que impide que el mismo percentil salga 12% aquí
            # y 13% allá.
            text=[texto_percentil(v) for v in comparacion["percentil_prima"]],
            textposition="outside",
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
    panel_bruto = pd.concat(historico, ignore_index=True)
    panel_historico = percentil_contra_sector(panel_bruto)

    # Qué sectores no alcanzan y por qué. El umbral es correcto —un percentil sobre
    # ocho trimestres es una opinión— pero aplicarlo en silencio deja un mapa de
    # calor SECTORIAL con una sola fila, bajo una leyenda que habla de comparar
    # filas entre sí. Quien lo lee no puede saber si falta el dato o falta el sector.
    cobertura = cobertura_del_percentil(panel_bruto)
    cortos = cobertura[~cobertura["alcanza"]]
    if not cortos.empty:
        detalle = ", ".join(
            f"{r['sector']} ({int(r['fechas'])} de {MIN_OBSERVACIONES_PERCENTIL})"
            for _, r in cortos.iterrows()
        )
        st.info(
            f"**Faltan {len(cortos)} de {len(cobertura)} sectores** en el mapa y en el reloj: "
            f"{detalle}. El percentil necesita {MIN_OBSERVACIONES_PERCENTIL} observaciones; "
            "con menos no es un percentil, es una opinión."
        )

    matriz = mapa_de_calor(panel_historico)
    if not matriz.empty:
        # El muestreo se ancla en la ÚLTIMA columna, no en la primera: un salto
        # posicional desde el inicio descartaba el trimestre más reciente, que es
        # justo lo que este gráfico existe para decir.
        matriz = muestrear_columnas(matriz)
        figura = px.imshow(
            matriz, aspect="auto", color_continuous_scale=escala_ambar(), zmin=0, zmax=1,
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
        figura.add_hline(y=0.5, line_dash="dot", line_color=GRIS)
        figura.add_vline(x=0.0, line_dash="dot", line_color=GRIS)
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
