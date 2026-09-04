"""Simulación: Monte Carlo, replay histórico, solvers inversos y detector de sesgos."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from comun import (  # noqa: E402
    configurar,
    descargo,
    dinero,
    exigir_base,
    explicar,
    pct,
    selector_de_corte,
    suficiencia,
    veces,
)

from src.portafolio.transacciones import procesar_libro  # noqa: E402
from src.servicio import contexto_macro, tabla_universo  # noqa: E402
from src.simulacion.backtest import (  # noqa: E402
    backtest_regla_de_aportacion,
    backtest_regla_de_posicion,
    dictaminar,
    generar_serie_con_edge,
    generar_serie_sin_edge,
)
from src.simulacion.escenarios import (  # noqa: E402
    EPISODIOS,
    crecimiento_affo_requerido,
    detectar_sesgos,
    replay_todos,
)
from src.simulacion.montecarlo import (  # noqa: E402
    SupuestosSimulacion,
    riesgo_de_secuencia,
    simular_retiro,
    tabla_sensibilidad_tasas,
)

configurar("Simulación", "🎲")
st.title("Simulación")

repo = exigir_base()
asof = selector_de_corte()
macro = contexto_macro(repo, asof=asof)
universo = tabla_universo(repo, asof=asof)

pestanas = st.tabs(
    ["Monte Carlo", "Replay histórico", "Solver inverso", "Sensibilidad a tasas",
     "Backtest honesto", "Detector de sesgos"]
)

# --------------------------------------------------------------------------------------
# 1. Monte Carlo
# --------------------------------------------------------------------------------------

with pestanas[0]:
    st.header("Monte Carlo con bootstrap por bloques")
    st.caption(
        "Bloques y no observaciones sueltas: remuestrear i.i.d. destruye la autocorrelación y "
        "con ella el riesgo que de verdad quiebra un plan de retiro, que son las malas rachas. "
        "Una simulación i.i.d. produce trayectorias demasiado amables."
    )

    c1, c2 = st.columns([1, 2])
    with c1:
        capital = st.number_input("Capital inicial (USD)", 0.0, value=1_000_000.0, step=50_000.0)
        retiro = st.number_input("Retiro anual REAL (USD)", 0.0, value=42_000.0, step=1_000.0)
        anios = st.slider("Horizonte (años)", 5, 50, 30)
        bloque = st.slider("Tamaño de bloque (meses)", 1, 36, 12,
                           help="Debe cubrir el horizonte de la dependencia. 1 equivale a i.i.d.")
        n_tray = st.select_slider("Trayectorias", [500, 1000, 2000, 5000], value=1000)
        ticker_base = st.selectbox(
            "Serie histórica de referencia",
            sorted(universo["ticker"]) if not universo.empty else ["O"],
        )

    serie_precio = repo.serie_precio(ticker_base, asof=asof)
    if len(serie_precio) < 60:
        with c2:
            st.warning("No hay suficiente historia de precios para simular.")
    else:
        mensuales = serie_precio.resample("ME").last().pct_change().dropna()
        inflacion_mensual = (1.0 + (macro.inflacion_us or 0.03)) ** (1 / 12) - 1.0
        reales = (1.0 + mensuales) / (1.0 + inflacion_mensual) - 1.0

        supuestos = SupuestosSimulacion(
            capital_inicial=capital, retiro_anual_real=retiro, anios=anios,
            n_trayectorias=int(n_tray), tamano_bloque=bloque,
        )
        with st.spinner("Simulando…"):
            resultado = simular_retiro(reales, supuestos)

        with c2:
            (st.error if resultado.prob_ruina > 0.10 else st.success)(resultado.como_texto())
            m1, m2, m3 = st.columns(3)
            m1.metric("P(quedarse sin capital)", pct(resultado.prob_ruina, 1))
            m2.metric("Riqueza terminal, mediana", dinero(resultado.percentiles["p50"], "USD", 0))
            m3.metric("Percentil 10", dinero(resultado.percentiles["p10"], "USD", 0))

            muestra = resultado.trayectorias[:: max(1, len(resultado.trayectorias) // 120)]
            figura = go.Figure()
            eje = np.arange(resultado.trayectorias.shape[1]) / 12
            for camino in muestra:
                figura.add_scatter(x=eje, y=camino, line={"width": 0.5, "color": "rgba(9,105,218,0.15)"},
                                   showlegend=False, hoverinfo="skip")
            for q, color in ((10, "#b42318"), (50, "#0969da"), (90, "#1a7f37")):
                figura.add_scatter(
                    x=eje, y=np.percentile(resultado.trayectorias, q, axis=0),
                    name=f"P{q}", line={"color": color, "width": 2.5},
                )
            figura.update_layout(height=380, xaxis_title="Años",
                                 yaxis_title="Capital real (USD de hoy)",
                                 margin={"t": 20, "b": 20, "l": 10, "r": 10},
                                 legend={"orientation": "h", "y": 1.1})
            st.plotly_chart(figura, width="stretch")

        st.subheader("Riesgo de secuencia: la misma media, distinto orden")
        st.caption(
            "Se permuta la serie histórica — misma media, misma varianza, misma distribución "
            "marginal — y se mide la dispersión de la riqueza terminal. Todo lo que aparezca "
            "ahí es riesgo de secuencia puro."
        )
        secuencia = riesgo_de_secuencia(reales, capital, retiro, n_permutaciones=400)
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Mediana", dinero(secuencia["mediana"], "USD", 0))
        s2.metric("Percentil 5", dinero(secuencia["p5"], "USD", 0))
        s3.metric("Percentil 95", dinero(secuencia["p95"], "USD", 0))
        s4.metric("P(ruina)", pct(secuencia["prob_ruina"], 1))
        st.caption(
            f"La dispersión entre el percentil 5 y el 95 es de "
            f"{secuencia['dispersion_relativa']:.1f} veces la mediana, y viene **solo del orden** "
            "en que ocurren los mismos rendimientos. Con retiros, los años malos al principio "
            "son cualitativamente peores que al final."
        )

# --------------------------------------------------------------------------------------
# 2. Replay histórico
# --------------------------------------------------------------------------------------

with pestanas[1]:
    st.header("Replay histórico")
    st.info(
        "**Esto no es Monte Carlo.** Son secuencias que efectivamente ocurrieron, aplicadas a "
        "tu portafolio actual con la beta de estrés de cada sector: en marzo de 2020, hoteles y "
        "data centers no se movieron igual, y promediarlos esconde justo el riesgo que interesa."
    )

    transacciones = repo.transacciones(asof=asof)
    posiciones = pd.DataFrame()
    if not transacciones.empty:
        estado = procesar_libro(transacciones, hasta=asof)
        filas = []
        for t, p in estado.posiciones.items():
            if p.cantidad <= 0:
                continue
            serie = repo.serie_precio(t, asof=asof)
            if serie.empty:
                continue
            filas.append(
                {"ticker": t, "valor_mercado": p.cantidad * float(serie.iloc[-1]),
                 "sector": repo.sector_de(t) or "Diversificado"}
            )
        posiciones = pd.DataFrame(filas)

    if posiciones.empty:
        st.warning(
            "No tienes posiciones registradas. Se muestra el replay sobre un portafolio de "
            "ejemplo equiponderado del universo, solo para ilustrar la mecánica."
        )
        posiciones = pd.DataFrame(
            [
                {"ticker": r["ticker"], "valor_mercado": 100_000.0, "sector": r["sector"]}
                for _, r in universo.iterrows()
            ]
        )

    if not posiciones.empty:
        yield_actual = st.slider("Yield actual de tu cartera", 0.01, 0.12, 0.05, 0.0025, format="%.4f")
        tabla = replay_todos(posiciones, yield_actual=yield_actual)
        vista = tabla.copy()
        vista["caida_portafolio"] = vista["caida_portafolio"] * 100.0
        st.dataframe(
            vista, hide_index=True, width="stretch",
            column_config={
                "episodio": "Episodio",
                "periodo": "Periodo",
                "caida_portafolio": st.column_config.NumberColumn("Caída", format="%.1f%%"),
                "valor_en_el_fondo": st.column_config.NumberColumn("Valor en el fondo", format="$%,.0f"),
                "perdida": st.column_config.NumberColumn("Pérdida", format="$%,.0f"),
                "anios_de_ingreso_perdidos": st.column_config.NumberColumn(
                    "Años de ingreso", format="%.1f"),
                "meses_de_recuperacion": st.column_config.NumberColumn("Meses a recuperar", format="%d"),
            },
        )
        for ep in EPISODIOS:
            with st.expander(ep.nombre):
                st.markdown(ep.descripcion)
        st.warning(
            "La pregunta útil no es si aguantarías la caída, sino **si seguirías aportando "
            "durante ella**. Los episodios en que el sistema dice COMPRAR son exactamente estos."
        )

# --------------------------------------------------------------------------------------
# 3. Solver inverso
# --------------------------------------------------------------------------------------

with pestanas[2]:
    st.header("Solver inverso: ¿qué tiene que pasar para que esto funcione?")
    st.caption(
        "En vez de proyectar un rendimiento y ver a dónde llega, se fija la meta y se despeja "
        "el supuesto necesario. Después se contrasta contra la historia."
    )

    c1, c2 = st.columns([1, 2])
    with c1:
        capital_actual = st.number_input("Capital actual (USD)", 0.0, value=300_000.0, step=25_000.0)
        aportacion_anual = st.number_input("Aportación anual (USD)", 0.0, value=24_000.0, step=2_000.0)
        meta_ingreso = st.number_input("Meta de ingreso anual (USD)", 0.0, value=60_000.0, step=5_000.0)
        horizonte = st.slider("Años", 1, 40, 15, key="solver_anios")
        yield_inicial = st.slider("Yield del portafolio", 0.02, 0.10, 0.05, 0.0025, format="%.4f")
    with c2:
        historico_crecimiento = pd.Series(dtype="float64")
        if not universo.empty:
            valores = []
            for t in universo["ticker"]:
                s = repo.serie(t, "affo_por_accion", asof=asof, periodo_tipo="Q")
                if len(s) > 5:
                    valores.extend(s.pct_change(4).dropna().tolist())
            historico_crecimiento = pd.Series(valores)

        resultado = crecimiento_affo_requerido(
            capital_actual, aportacion_anual, meta_ingreso, horizonte, yield_inicial,
            historico_crecimiento=historico_crecimiento if not historico_crecimiento.empty else None,
        )
        if resultado.valor_requerido is None:
            st.error(resultado.mensaje)
        else:
            st.metric("Crecimiento total anual requerido", pct(resultado.valor_requerido))
            (st.warning if resultado.plausible is False else st.info)(resultado.mensaje)

            if not historico_crecimiento.empty:
                figura = go.Figure()
                figura.add_histogram(x=historico_crecimiento.clip(-0.5, 0.5), nbinsx=60,
                                     marker_color="#57606a", name="Historia del universo")
                figura.add_vline(x=resultado.valor_requerido, line_color="#b42318", line_width=3,
                                 annotation_text="Requerido")
                figura.update_layout(height=300, xaxis_tickformat=".0%",
                                     xaxis_title="Crecimiento del AFFO por acción (YoY)",
                                     margin={"t": 20, "b": 20, "l": 10, "r": 10}, showlegend=False)
                st.plotly_chart(figura, width="stretch")

# --------------------------------------------------------------------------------------
# 4. Sensibilidad a tasas
# --------------------------------------------------------------------------------------

with pestanas[3]:
    st.header("Sensibilidad a tasas: el REIT cotiza como instrumento de duración")
    st.caption(
        "Su múltiplo es aproximadamente el recíproco de una tasa de capitalización, así que un "
        "alza de tasas lo comprime. El traspaso no es de uno a uno: cuando las tasas suben por "
        "crecimiento, el AFFO también sube."
    )
    multiplo = st.slider("Múltiplo P/AFFO actual", 5.0, 45.0, 18.0, 0.5)
    tabla = tabla_sensibilidad_tasas(multiplo)
    vista = tabla.copy()
    vista["cambio_pct"] = vista["cambio_pct"] * 100.0
    st.dataframe(
        vista[["shock_bps", "multiplo_estimado", "cambio_pct"]],
        hide_index=True, width="stretch",
        column_config={
            "shock_bps": st.column_config.NumberColumn("Shock del bono 10a (bps)", format="%d"),
            "multiplo_estimado": st.column_config.NumberColumn("Múltiplo estimado", format="%.1fx"),
            "cambio_pct": st.column_config.NumberColumn("Impacto en precio", format="%.1f%%"),
        },
    )
    figura = go.Figure()
    figura.add_bar(x=tabla["shock_bps"], y=tabla["cambio_pct"],
                   marker_color=["#b42318" if v < 0 else "#1a7f37" for v in tabla["cambio_pct"]])
    figura.update_layout(height=300, yaxis_tickformat=".0%",
                         xaxis_title="Shock del UST 10 años (bps)", yaxis_title="Impacto en precio",
                         margin={"t": 20, "b": 20, "l": 10, "r": 10}, showlegend=False)
    st.plotly_chart(figura, width="stretch")
    st.caption(
        "El ciclo 2022–2023 fue exactamente esto: el bono a 10 años pasó de 1.5% a 5% y la caída "
        "fue casi toda compresión de múltiplo, no deterioro del AFFO. Es el episodio que mejor "
        "separa «barato» de «roto»."
    )

# --------------------------------------------------------------------------------------
# 5. Backtest honesto
# --------------------------------------------------------------------------------------

with pestanas[4]:
    st.header("Backtest con las cuatro salvaguardas")
    st.markdown(
        "- **El benchmark es el MISMO activo.** Contra cualquier otra cosa medirías qué tan "
        "bueno fue el activo, no qué aportó la regla.\n"
        "- **Se cuentan apuestas efectivas, no observaciones.** Una señal lenta produce 10 a 20 "
        "episodios en veinte años, no 240.\n"
        "- **Se neutraliza beta.** Una regla que despliega más capital en un activo con deriva "
        "alcista tiene Sharpe positivo aunque la señal sea ruido puro.\n"
        "- **Se compara por TIR**, no por riqueza final, porque las estrategias despliegan "
        "distinto capital en distintos momentos."
    )
    explicar("apuestas efectivas")

    c1, c2 = st.columns([1, 1])
    with c1:
        tipo_regla = st.radio("Tipo de regla", ["Aportación", "Posición"], horizontal=True)
        control = st.radio(
            "Datos", ["Control negativo (sin edge)", "Control positivo (edge plantado)"],
            help=(
                "El control negativo prueba que la maquinaria rechaza el ruido. El positivo "
                "prueba que sí detecta lo que está ahí: un sistema que siempre dice NO-GO "
                "parecería riguroso cuando en realidad solo está roto."
            ),
        )
        semilla = st.number_input("Semilla", 0, 9999, 0, 1)
    with c2:
        generador = generar_serie_sin_edge if control.startswith("Control negativo") else generar_serie_con_edge
        retornos, sen = generador(240, semilla=int(semilla))
        motor = backtest_regla_de_aportacion if tipo_regla == "Aportación" else backtest_regla_de_posicion
        resultado = motor(retornos, sen)
        dictamen = dictaminar(resultado)

        estilo = {"GO": st.success, "NO-GO": st.error, "INCONCLUSO": st.warning}[dictamen.veredicto.value]
        estilo(f"### Veredicto: {dictamen.veredicto.value}\n\n" + " ".join(dictamen.motivos))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Episodios efectivos", f"{resultado.apuestas.episodios}")
    m2.metric("TIR de la estrategia", pct(resultado.tir_estrategia) if resultado.tir_estrategia else "—")
    m3.metric("TIR del benchmark", pct(resultado.tir_benchmark) if resultado.tir_benchmark else "—")
    m4.metric("Ventaja", pct(resultado.ventaja_tir) if resultado.ventaja_tir else "—")
    suficiencia(resultado.apuestas.episodios)
    st.caption(f"Benchmark: {resultado.descripcion_benchmark}")

    if resultado.neutralizacion:
        n = resultado.neutralizacion
        st.subheader("Neutralización de beta")
        b1, b2, b3 = st.columns(3)
        b1.metric("Beta contra el subyacente", veces(n.beta))
        b2.metric("Sharpe crudo", veces(n.sharpe_crudo))
        b3.metric("Sharpe neutralizado", veces(n.sharpe_neutralizado),
                  delta=veces((n.sharpe_neutralizado or 0) - (n.sharpe_crudo or 0)))
        st.caption(n.como_texto())
        st.caption(
            "Los errores estándar son HAC (Newey-West): el retorno activo de una regla de "
            "aportación es autocorrelado por construcción, y con errores simples eso infla la "
            "significancia del alfa. Es el mecanismo por el que un backtest sin señal reporta edge."
        )

    figura = go.Figure()
    figura.add_scatter(x=resultado.riqueza_estrategia.index, y=resultado.riqueza_estrategia,
                       name="Estrategia", line={"color": "#0969da"})
    figura.add_scatter(x=resultado.riqueza_benchmark.index, y=resultado.riqueza_benchmark,
                       name="Benchmark (mismo activo)", line={"color": "#57606a", "dash": "dash"})
    figura.update_layout(height=320, margin={"t": 20, "b": 20, "l": 10, "r": 10},
                         legend={"orientation": "h", "y": 1.12})
    st.plotly_chart(figura, width="stretch")
    st.warning(
        "Comparar riqueza final entre estas dos curvas sería incorrecto: despliegan distinto "
        "capital en distintos momentos. Por eso el veredicto se decide por TIR, no por dónde "
        "termina la línea azul."
    )

# --------------------------------------------------------------------------------------
# 6. Detector de sesgos
# --------------------------------------------------------------------------------------

with pestanas[5]:
    st.header("Detector de sesgos: el espejo")
    st.caption(
        "Registra qué dijo el sistema y qué hiciste tú, y cuantifica cuánto costó desviarse. "
        "El objetivo no es regañar: los sesgos son sistemáticos, casi siempre en la misma "
        "dirección, y verlos cuantificados es lo único que los mueve."
    )

    with st.form("registrar_decision"):
        c1, c2, c3, c4 = st.columns(4)
        fecha = c1.date_input("Fecha", value=asof, max_value=asof)
        ticker_d = c2.selectbox("Emisor", sorted(universo["ticker"]) if not universo.empty else ["O"])
        senal = c3.selectbox("Lo que dijo el sistema",
                             ["COMPRAR", "MANTENER", "NO COMPRAR MÁS", "VENDER", "DESCARTADO"])
        accion = c4.selectbox("Lo que hiciste",
                              ["COMPRAR", "MANTENER", "VENDER", "VENTA PARCIAL", "NADA"])
        monto = st.number_input("Monto involucrado (USD)", 0.0, value=10_000.0, step=1_000.0)
        nota = st.text_input("Por qué lo hiciste")
        if st.form_submit_button("Registrar decisión"):
            repo.guardar_decisiones([{
                "fecha": fecha, "ticker": ticker_d, "senal_sistema": senal,
                "accion_usuario": accion, "monto": monto, "nota": nota,
            }])
            st.success("Decisión registrada.")
            st.rerun()

    decisiones = repo.decisiones()
    if decisiones.empty:
        st.info("Aún no hay decisiones registradas. El espejo se llena con el tiempo.")
    else:
        panel_precios = pd.DataFrame(
            {t: repo.serie_precio(t, asof=asof) for t in decisiones["ticker"].unique()}
        ).ffill()
        reporte = detectar_sesgos(decisiones, panel_precios if not panel_precios.empty else None)
        c1, c2, c3 = st.columns(3)
        c1.metric("Decisiones registradas", reporte.n_decisiones)
        c2.metric("Desviaciones de la regla", reporte.n_desviaciones)
        c3.metric("Tasa de desviación", pct(reporte.tasa_desviacion, 0))
        (st.error if reporte.costo_estimado > 0 else st.info)(reporte.mensaje)
        if not reporte.por_tipo.empty:
            st.dataframe(reporte.por_tipo, hide_index=True, width="stretch")
        st.dataframe(decisiones, hide_index=True, width="stretch")

st.divider()
descargo()
