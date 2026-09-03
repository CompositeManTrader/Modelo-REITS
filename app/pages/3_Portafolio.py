"""Portafolio: meta, transacciones, métricas, fiscal y benchmarks."""

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

from src.fiscal.mexico import (  # noqa: E402
    DESCARGO_FISCAL,
    ViaDeCompra,
    alerta_estate_tax,
    impuesto_dividendo,
    impuesto_ganancia_capital,
)
from src.portafolio.metricas import (  # noqa: E402
    EXPLICACION_TWR_VS_TIR,
    atribuir_retorno,
    crecimiento_real_anualizado,
    drawdown,
    resumen_desempeno,
)
from src.portafolio.rebalanceo import (  # noqa: E402
    PREFERENCIA_DINERO_NUEVO,
    Restricciones,
    capital_requerido,
    destino_de_aportacion,
    evaluar_rotacion_vs_aportacion,
    poder_adquisitivo_erosionado,
    proponer_asignacion,
    simular_aportaciones,
)
from src.portafolio.transacciones import (  # noqa: E402
    TipoTx,
    flujos_de_caja,
    procesar_libro,
    validar_transacciones,
    valor_por_fecha,
)
from src.servicio import contexto_macro, tabla_universo  # noqa: E402

configurar("Portafolio", "💼")
st.title("Portafolio")

repo = exigir_base()
asof = selector_de_corte()
macro = contexto_macro(repo, asof=asof)
universo = tabla_universo(repo, asof=asof)

pestanas = st.tabs(
    ["Meta de ingreso", "Transacciones", "Posiciones y métricas", "Señales y rotación",
     "Fiscal", "Benchmarks"]
)

# --------------------------------------------------------------------------------------
# 1. Meta de ingreso
# --------------------------------------------------------------------------------------

with pestanas[0]:
    st.header("¿Cuánto capital necesitas de verdad?")
    st.caption(
        "La fórmula es `capital = gasto anual ÷ tasa de retiro REAL`. Usar la nominal produce "
        "un plan que llega a la meta con una fracción del poder adquisitivo esperado."
    )
    c1, c2 = st.columns([1, 2])
    with c1:
        gasto = st.number_input("Meta de ingreso anual (MXN)", 0.0, value=600_000.0, step=50_000.0)
        tasa_real = st.slider("Tasa de retiro REAL", 0.020, 0.070, 0.040, 0.0025, format="%.4f")
        inflacion = st.number_input(
            "Inflación esperada", 0.0, 0.20,
            float(macro.inflacion_mx) if macro.inflacion_mx else 0.045, 0.0025, format="%.4f",
        )
        horizonte = st.slider("Horizonte (años)", 1, 40, 20)
    with c2:
        meta = capital_requerido(gasto, tasa_real, inflacion=inflacion)
        a, b = st.columns(2)
        a.metric("Capital requerido (tasa REAL)", dinero(meta.capital_requerido_real, "MXN", 0))
        b.metric(
            "Lo que sugeriría la tasa nominal", dinero(meta.capital_requerido_nominal, "MXN", 0),
            delta=dinero(-meta.brecha, "MXN", 0), delta_color="inverse",
        )
        st.error(meta.explicacion())
        supervivencia = poder_adquisitivo_erosionado(horizonte, inflacion)
        st.metric(
            f"Poder adquisitivo de un peso nominal a {horizonte} años", pct(supervivencia, 1),
            help="Cuánto compra en el futuro un peso que hoy compra uno.",
        )
        st.caption(
            f"Con inflación de {inflacion:.1%}, en {horizonte} años un ingreso nominal fijo "
            f"compra {supervivencia:.0%} de lo que compra hoy. Por eso el plan se hace en "
            "términos reales o no se hace."
        )

    st.subheader("¿Cuánto y por cuánto tiempo hay que aportar?")
    d1, d2 = st.columns([1, 2])
    with d1:
        capital_inicial = st.number_input("Capital actual (MXN)", 0.0, value=1_500_000.0, step=100_000.0)
        aportacion = st.number_input("Aportación mensual (MXN)", 0.0, value=25_000.0, step=5_000.0)
        rendimiento_real = st.slider("Rendimiento REAL esperado", -0.02, 0.10, 0.042, 0.0025, format="%.4f")
    with d2:
        plan = simular_aportaciones(
            capital_inicial, aportacion, rendimiento_real, meta.capital_requerido_real
        )
        st.info(plan.como_texto())
        figura = go.Figure()
        figura.add_scatter(x=plan.trayectoria["mes"] / 12, y=plan.trayectoria["saldo"],
                           name="Saldo", line={"color": "#0969da"})
        figura.add_scatter(x=plan.trayectoria["mes"] / 12, y=plan.trayectoria["aportado"],
                           name="Aportado", line={"color": "#57606a", "dash": "dash"})
        figura.add_hline(y=meta.capital_requerido_real, line_dash="dot", line_color="#1a7f37",
                         annotation_text="Meta")
        figura.update_layout(height=320, xaxis_title="Años", yaxis_title="MXN reales de hoy",
                             margin={"t": 20, "b": 20, "l": 10, "r": 10},
                             legend={"orientation": "h", "y": 1.12})
        st.plotly_chart(figura, width="stretch")

    st.subheader("Asignación propuesta")
    r1, r2, r3 = st.columns(3)
    max_emisor = r1.slider("Máximo por emisor", 0.05, 0.50, 0.15, 0.01)
    max_sector = r2.slider("Máximo por sector", 0.10, 1.00, 0.35, 0.05)
    min_emisores = r3.slider("Mínimo de emisores", 3, 15, 6)
    restricciones = Restricciones(max_emisor, max_sector, min_emisores, True)
    st.caption(restricciones.describir())

    if not universo.empty:
        asignacion = proponer_asignacion(universo, restricciones=restricciones)
        for a in asignacion.advertencias:
            st.warning(a)
        if not asignacion.pesos.empty:
            figura = go.Figure()
            figura.add_bar(x=asignacion.pesos.index, y=asignacion.pesos.to_numpy(),
                           marker_color="#0969da",
                           text=[f"{v:.1%}" for v in asignacion.pesos], textposition="outside")
            figura.update_layout(height=300, yaxis_tickformat=".0%",
                                 margin={"t": 20, "b": 20, "l": 10, "r": 10}, showlegend=False)
            st.plotly_chart(figura, width="stretch")
        if not asignacion.excluidos.empty:
            st.markdown("**Excluidos por la Puerta 1 de calidad:**")
            st.dataframe(asignacion.excluidos, hide_index=True, width="stretch")
            st.caption("Lo que falla no está barato: está descartado. No compite por peso.")

# --------------------------------------------------------------------------------------
# 2. Transacciones
# --------------------------------------------------------------------------------------

with pestanas[1]:
    st.header("Libro de transacciones")
    st.caption(
        "El libro es la fuente de verdad. Toda métrica se deriva de aquí, no de un saldo "
        "capturado a mano: el saldo no distingue entre «subió» y «metí más dinero», que es "
        "justo la diferencia entre TWR y TIR."
    )

    with st.form("nueva_tx"):
        c1, c2, c3, c4 = st.columns(4)
        fecha = c1.date_input("Fecha", value=dt.date.today(), max_value=dt.date.today())
        tipo = c2.selectbox(
            "Tipo",
            [TipoTx.COMPRA, TipoTx.VENTA, TipoTx.DIVIDENDO, TipoTx.APORTACION, TipoTx.RETIRO, TipoTx.SPLIT],
        )
        tickers = sorted(universo["ticker"]) if not universo.empty else []
        ticker_tx = c3.selectbox("Emisor", tickers) if tickers else c3.text_input("Emisor")
        cantidad = c4.number_input("Cantidad de títulos", 0.0, value=0.0, step=1.0)
        c5, c6, c7, c8 = st.columns(4)
        precio = c5.number_input("Precio o monto por título (USD)", 0.0, value=0.0, step=0.01)
        comision = c6.number_input("Comisión (USD)", 0.0, value=0.0, step=0.01)
        tipo_cambio = c7.number_input("Tipo de cambio USD/MXN", 0.0, value=18.0, step=0.05)
        retencion = c8.number_input("Retención EE. UU. (USD)", 0.0, value=0.0, step=0.01)
        nota = st.text_input("Nota")
        if st.form_submit_button("Registrar", type="primary"):
            fila = {
                "fecha": fecha, "ticker": (ticker_tx or "").upper(), "tipo": tipo,
                "cantidad": cantidad, "precio": precio, "comision": comision,
                "tipo_cambio": tipo_cambio, "retencion_eeuu": retencion, "nota": nota,
            }
            problemas = validar_transacciones(
                pd.concat([repo.transacciones(), pd.DataFrame([fila])], ignore_index=True)
            )
            if problemas:
                for p in problemas:
                    st.error(p)
            else:
                repo.guardar_transacciones([fila])
                st.success("Transacción registrada.")
                st.rerun()

    transacciones = repo.transacciones()
    if transacciones.empty:
        st.info("No hay transacciones todavía. Registra la primera arriba.")
    else:
        st.dataframe(transacciones, hide_index=True, width="stretch")
        borrar = st.multiselect("Borrar transacciones (por id)", list(transacciones["id"]))
        if borrar and st.button("Borrar seleccionadas"):
            repo.borrar_transacciones(borrar)
            st.rerun()

# --------------------------------------------------------------------------------------
# 3. Posiciones y métricas
# --------------------------------------------------------------------------------------

with pestanas[2]:
    transacciones = repo.transacciones(asof=asof)
    if transacciones.empty:
        st.info("Registra transacciones para ver posiciones y métricas.")
    else:
        estado = procesar_libro(transacciones, hasta=asof)
        precios_actuales = {
            t: (repo.serie_precio(t, asof=asof).iloc[-1]
                if not repo.serie_precio(t, asof=asof).empty else 0.0)
            for t in estado.posiciones
        }
        tabla = estado.tabla(precios_actuales)

        st.header("Posiciones")
        if tabla.empty:
            st.info("No hay posiciones abiertas.")
        else:
            valor_total = float(tabla["valor_mercado"].sum())
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Valor del portafolio", dinero(valor_total))
            c2.metric("Ganancia no realizada", dinero(tabla["ganancia_no_realizada"].sum()))
            c3.metric("Dividendos cobrados", dinero(tabla["dividendos_cobrados"].sum()))
            c4.metric("Ganancia realizada", dinero(tabla["ganancia_realizada"].sum()))
            st.dataframe(tabla, hide_index=True, width="stretch")

            alerta = alerta_estate_tax(valor_total)
            if alerta.activa:
                st.error(alerta.mensaje)
            else:
                st.info(alerta.mensaje)

            st.header("Desempeño")
            explicar("TWR y TIR")
            st.caption(EXPLICACION_TWR_VS_TIR)

            precios_panel = pd.DataFrame(
                {t: repo.serie_precio(t, asof=asof) for t in estado.posiciones}
            ).ffill()
            if not precios_panel.empty:
                fechas = precios_panel.resample("ME").last().index
                serie = valor_por_fecha(transacciones, precios_panel, fechas=fechas)
                flujos = flujos_de_caja(transacciones)
                resumen = resumen_desempeno(
                    serie["valor"], serie["flujo_externo"], flujos,
                    valor_final=valor_total, periodos_por_anio=12,
                    tasa_libre_riesgo=macro.ust10 or 0.0,
                )
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("TWR anualizado", pct(resumen["twr_anualizado"]))
                m2.metric("TIR (money-weighted)", pct(resumen["tir"]))
                m3.metric("Drawdown máximo", pct(resumen["drawdown_maximo"]))
                m4.metric("Sharpe", veces(resumen["sharpe"]) if resumen["sharpe"] else "—")

                if resumen.get("brecha_twr_tir") is not None:
                    brecha = resumen["brecha_twr_tir"]
                    if brecha > 0:
                        st.info(
                            f"El TWR supera a la TIR por {brecha * 10_000:,.0f} bps: aportaste "
                            "más dinero antes de los periodos malos. La selección de activos fue "
                            "mejor que tu resultado."
                        )
                    else:
                        st.success(
                            f"La TIR supera al TWR por {abs(brecha) * 10_000:,.0f} bps: tu timing "
                            "de aportaciones ayudó."
                        )

                suficiencia(len(transacciones), "transacciones")

                dd = drawdown(serie["valor"])
                figura = go.Figure()
                figura.add_scatter(x=dd.index, y=dd["drawdown"], fill="tozeroy",
                                   line={"color": "#b42318"}, name="Drawdown")
                figura.update_layout(height=260, yaxis_tickformat=".0%",
                                     margin={"t": 20, "b": 20, "l": 10, "r": 10}, showlegend=False)
                st.plotly_chart(figura, width="stretch")

            st.subheader("Atribución del retorno en tres componentes")
            st.caption(
                "Esta descomposición revela si el resultado vino del negocio o de la revaluación. "
                "Un retorno que vino todo de expansión de múltiplo es prestado: se devuelve."
            )
            objetivo = st.selectbox("Posición", sorted(estado.posiciones), key="attrib")
            panel_precios = repo.serie_precio(objetivo, asof=asof)
            hechos = repo.serie(objetivo, "affo_por_accion", asof=asof, periodo_tipo="Q")
            if len(panel_precios) > 250 and len(hechos) > 5:
                p0 = float(panel_precios.iloc[-252])
                p1 = float(panel_precios.iloc[-1])
                a0 = float(hechos.iloc[-5]) * 4
                a1 = float(hechos.iloc[-1]) * 4
                divs = repo.dividendos(objetivo, asof=asof)
                div_12m = float(
                    divs[divs["fecha_ex"] > pd.Timestamp(asof) - pd.DateOffset(years=1)]["monto"].sum()
                ) if not divs.empty else 0.0
                atribucion = atribuir_retorno(p0, p1, a0, a1, div_12m)
                if atribucion:
                    st.dataframe(atribucion.como_tabla(), hide_index=True, width="stretch",
                                 column_config={"aporte": st.column_config.NumberColumn(
                                     "Aporte", format="%.2f%%")})
                    st.caption(
                        "Los aportes están en decimal; multiplica por 100 mentalmente o mira la "
                        "gráfica. El total cierra exacto porque el término cruzado se reporta "
                        "por separado en vez de repartirse."
                    )
            else:
                st.info("Hace falta más de un año de precios y cinco trimestres de AFFO para atribuir.")

            st.subheader("Ingreso en términos reales")
            divs = repo.dividendos(list(estado.posiciones), asof=asof)
            if not divs.empty and not macro.inpc.empty:
                serie_ingreso = (
                    divs.set_index("fecha_ex")["monto"].resample("YE").sum()
                )
                real = crecimiento_real_anualizado(serie_ingreso, macro.inpc)
                a, b, c = st.columns(3)
                a.metric("Crecimiento nominal del ingreso", pct(real["nominal"]) if real["nominal"] else "—")
                b.metric("Inflación", pct(real["inflacion"]) if real["inflacion"] else "—")
                c.metric("Crecimiento REAL", pct(real["real"]) if real["real"] else "—",
                         delta_color="normal" if (real["real"] or 0) > 0 else "inverse")
                if real["real"] is not None and real["real"] <= 0.005:
                    st.error(
                        "Tu ingreso por dividendos está **plano o cayendo en poder adquisitivo**. "
                        "El dividendo nominal puede estar subiendo y aun así perder contra la "
                        "inflación. Es la métrica que de verdad importa para vivir de rentas y "
                        "casi nadie la mira."
                    )

# --------------------------------------------------------------------------------------
# 4. Señales y rotación
# --------------------------------------------------------------------------------------

with pestanas[3]:
    st.header("¿A dónde va la próxima aportación?")
    st.success(PREFERENCIA_DINERO_NUEVO)

    monto = st.number_input("Monto de la próxima aportación (USD)", 0.0, value=5_000.0, step=500.0)
    if not universo.empty and monto > 0:
        transacciones = repo.transacciones(asof=asof)
        pesos_actuales = pd.Series(dtype="float64")
        if not transacciones.empty:
            estado = procesar_libro(transacciones, hasta=asof)
            precios_actuales = {
                t: (repo.serie_precio(t, asof=asof).iloc[-1]
                    if not repo.serie_precio(t, asof=asof).empty else 0.0)
                for t in estado.posiciones
            }
            tabla = estado.tabla(precios_actuales)
            if not tabla.empty and "peso" in tabla:
                pesos_actuales = tabla.set_index("ticker")["peso"]

        destinos = destino_de_aportacion(universo, monto, pesos_actuales=pesos_actuales)
        if destinos:
            for d in destinos:
                st.markdown(f"**{d.ticker}** — {dinero(d.monto)}")
                st.caption(d.motivo)
        else:
            st.warning(
                "Ningún emisor pasa la Puerta 1 de calidad con percentil disponible. "
                "Aportar a algo que no pasa calidad no es una rotación: es un error."
            )

    st.divider()
    st.header("¿Conviene rotar vendiendo?")
    c1, c2, c3 = st.columns(3)
    p_origen = c1.slider("Percentil del emisor que tienes", 0.0, 1.0, 0.25, 0.05)
    p_destino = c2.slider("Percentil del destino", 0.0, 1.0, 0.75, 0.05)
    ganancia = c3.slider("Ganancia acumulada", 0.0, 3.0, 0.40, 0.05)
    valor_pos = st.number_input("Valor de la posición origen (USD)", 0.0, value=100_000.0, step=5_000.0)
    aport_disp = st.number_input("Aportación disponible (USD)", 0.0, value=10_000.0, step=1_000.0)

    comparacion = evaluar_rotacion_vs_aportacion(p_origen, p_destino, ganancia, aport_disp, valor_pos)
    a, b = st.columns(2)
    with a:
        st.subheader("Vender para rotar")
        r = comparacion["rotar"]
        st.metric("Costo fiscal", pct(r["costo_fiscal_pct"]))
        st.metric("Ventaja anual necesaria", f"{r['ventaja_anual_necesaria_bps']:,.0f} bps")
        (st.success if r["conviene"] else st.warning)(r["mensaje"])
    with b:
        st.subheader("Dirigir la aportación")
        r = comparacion["aportar_al_destino"]
        st.metric("Costo fiscal", pct(r["costo_fiscal_pct"]))
        st.metric("Cobertura de la posición origen", pct(r["cobertura_de_la_posicion_origen"]))
        st.success(r["mensaje"])

# --------------------------------------------------------------------------------------
# 5. Fiscal
# --------------------------------------------------------------------------------------

with pestanas[4]:
    st.header("Capa fiscal mexicana")
    st.warning(DESCARGO_FISCAL)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Dividendos")
        bruto = st.number_input("Dividendo bruto anual (USD)", 0.0, value=10_000.0, step=500.0)
        w8 = st.checkbox("W-8BEN presentado", value=True, key="w8_fiscal")
        acredita = st.checkbox(
            "Mi intermediario acredita la retención estadounidense", value=False,
            help="Muchos no lo aplican de oficio. Si no, el efectivo combinado es la suma simple.",
        )
        resultado = impuesto_dividendo(bruto, tiene_w8ben=w8, acredita_retencion=acredita)
        st.dataframe(resultado.como_tabla(), hide_index=True, width="stretch",
                     column_config={"monto": st.column_config.NumberColumn(format="$%,.2f")})
        st.metric("Tasa efectiva combinada", pct(resultado.tasa_efectiva))
        for a in resultado.advertencias:
            st.info(a)

    with c2:
        st.subheader("Ganancias de capital: la vía importa más que el activo")
        ganancia_venta = st.number_input("Ganancia realizada (MXN)", 0.0, value=200_000.0, step=10_000.0)
        sueldo = st.number_input("Ingreso acumulable previo (MXN)", 0.0, value=900_000.0, step=50_000.0)
        via_sic = impuesto_ganancia_capital(ganancia_venta, via=ViaDeCompra.SIC)
        via_ext = impuesto_ganancia_capital(
            ganancia_venta, via=ViaDeCompra.BROKER_EXTRANJERO, ingreso_acumulable_previo=sueldo
        )
        comparativa = pd.DataFrame(
            [
                {"Vía": via_sic.via, "Impuesto": via_sic.impuesto, "Tasa efectiva": via_sic.tasa_efectiva,
                 "Neto": via_sic.neto},
                {"Vía": via_ext.via, "Impuesto": via_ext.impuesto, "Tasa efectiva": via_ext.tasa_efectiva,
                 "Neto": via_ext.neto},
            ]
        )
        comparativa["Tasa efectiva"] = comparativa["Tasa efectiva"] * 100.0
        st.dataframe(
            comparativa, hide_index=True, width="stretch",
            column_config={
                "Impuesto": st.column_config.NumberColumn(format="$%,.0f"),
                "Tasa efectiva": st.column_config.NumberColumn(format="%.1f%%"),
                "Neto": st.column_config.NumberColumn(format="$%,.0f"),
            },
        )
        diferencia = via_ext.impuesto - via_sic.impuesto
        if diferencia > 0:
            st.error(
                f"La misma operación cuesta **{diferencia:,.0f} MXN más** vía bróker extranjero. "
                "Esa diferencia suele superar el rendimiento esperado de la rotación que la motivó."
            )
        for a in via_ext.advertencias:
            st.caption(a)

# --------------------------------------------------------------------------------------
# 6. Benchmarks
# --------------------------------------------------------------------------------------

with pestanas[5]:
    st.header("Contra qué se compara, en términos reales y después de impuestos")
    st.caption(
        "Es la única comparación honesta y la que cambia conclusiones. Comparar un yield bruto "
        "de REIT contra una tasa de bono es comparar peras con manzanas."
    )
    from src.fiscal.mexico import rendimiento_real_despues_de_impuestos  # noqa: E402

    yield_cartera = st.number_input("AFFO yield bruto de tu cartera", 0.01, 0.15, 0.055, 0.0025, format="%.4f")
    crecimiento = st.number_input("Crecimiento real esperado", -0.05, 0.10, 0.020, 0.0025, format="%.4f")
    inflacion = st.number_input(
        "Inflación esperada", 0.0, 0.20,
        float(macro.inflacion_mx) if macro.inflacion_mx else 0.045, 0.0025, format="%.4f",
        key="infl_bench",
    )
    detalle = rendimiento_real_despues_de_impuestos(yield_cartera, crecimiento, inflacion)

    filas = [
        {"Instrumento": "Portafolio de REITs (real, neto de impuestos)",
         "Rendimiento": detalle["real_despues_de_impuestos"], "Garantizado": "No"},
        {"Instrumento": "Udibono 10 años (real)", "Rendimiento": macro.udibono10, "Garantizado": "Sí"},
        {"Instrumento": "Cetes 28 días (nominal)",
         "Rendimiento": repo.valor_tasa("CETES28", asof=asof), "Garantizado": "Sí"},
        {"Instrumento": "Mbono 10 años (nominal)",
         "Rendimiento": repo.valor_tasa("MBONO10", asof=asof), "Garantizado": "Sí"},
        {"Instrumento": "UST 10 años (nominal, USD)", "Rendimiento": macro.ust10, "Garantizado": "Sí"},
    ]
    df = pd.DataFrame(filas)
    df["Rendimiento"] = pd.to_numeric(df["Rendimiento"], errors="coerce") * 100.0
    st.dataframe(
        df, hide_index=True, width="stretch",
        column_config={"Rendimiento": st.column_config.NumberColumn(format="%.2f%%")},
    )
    st.caption(
        "Ojo: solo la fila de REITs y la del Udibono están en términos **reales**. Las demás son "
        "nominales y hay que restarles la inflación esperada antes de compararlas."
    )
    explicar("Udibono")

st.divider()
descargo()
