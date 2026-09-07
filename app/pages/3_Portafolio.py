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
    mostrar_tabla,
    pct,
    selector_de_corte,
    suficiencia,
    veces,
)

from marca import AMBAR, GRIS, LOSS, PROFIT, encabezado, inyectar_estilos  # noqa: E402
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
    ingreso_anual_por_dividendos,
    resumen_desempeno,
    suma_ttm,
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
inyectar_estilos()
encabezado("Portafolio")
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
                           name="Saldo", line={"color": AMBAR})
        figura.add_scatter(x=plan.trayectoria["mes"] / 12, y=plan.trayectoria["aportado"],
                           name="Aportado", line={"color": GRIS, "dash": "dash"})
        figura.add_hline(y=meta.capital_requerido_real, line_dash="dot", line_color=PROFIT,
                         annotation_text="Meta")
        figura.update_layout(height=320, xaxis_title="Años", yaxis_title="MXN reales de hoy",
                             margin={"t": 20, "b": 20, "l": 10, "r": 10},
                             legend={"orientation": "h", "y": 1.12})
        st.plotly_chart(figura)

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
                           marker_color=AMBAR,
                           text=[f"{v:.1%}" for v in asignacion.pesos], textposition="outside")
            figura.update_layout(height=300, yaxis_tickformat=".0%",
                                 margin={"t": 20, "b": 20, "l": 10, "r": 10}, showlegend=False)
            st.plotly_chart(figura)
        if not asignacion.excluidos.empty:
            st.markdown("**Excluidos por la Puerta 1 de calidad:**")
            mostrar_tabla(asignacion.excluidos)
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
        mostrar_tabla(transacciones)
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
            mostrar_tabla(tabla)

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
                # `veces` ya dibuja el hueco si no hay dato; la guardia extra
                # convertía un Sharpe de 0.00x en un guion de dato faltante.
                m4.metric("Sharpe", veces(resumen["sharpe"]))

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
                                   line={"color": LOSS}, name="Drawdown")
                figura.update_layout(height=260, yaxis_tickformat=".0%",
                                     margin={"t": 20, "b": 20, "l": 10, "r": 10}, showlegend=False)
                st.plotly_chart(figura)

            st.subheader("Atribución del retorno en tres componentes")
            st.caption(
                "Esta descomposición revela si el resultado vino del negocio o de la revaluación. "
                "Un retorno que vino todo de expansión de múltiplo es prestado: se devuelve."
            )
            objetivo = st.selectbox("Posición", sorted(estado.posiciones), key="attrib")
            panel_precios = repo.serie_precio(objetivo, asof=asof)
            hechos = repo.serie(objetivo, "affo_por_accion", asof=asof, periodo_tipo="Q")
            hace_un_anio = panel_precios[
                panel_precios.index <= pd.Timestamp(asof) - pd.DateOffset(years=1)
            ]
            # El AFFO de cada extremo son sus CUATRO trimestres, no uno multiplicado
            # por cuatro: la descomposición compara doce meses contra doce meses.
            a0 = suma_ttm(hechos, trimestres_atras=4)
            a1 = suma_ttm(hechos)
            if not hace_un_anio.empty and a0 and a1:
                p0 = float(hace_un_anio.iloc[-1])
                p1 = float(panel_precios.iloc[-1])
                divs = repo.dividendos(objetivo, asof=asof)
                div_12m = float(
                    divs[divs["fecha_ex"] > pd.Timestamp(asof) - pd.DateOffset(years=1)]["monto"].sum()
                ) if not divs.empty else 0.0
                atribucion = atribuir_retorno(p0, p1, a0, a1, div_12m)
                if atribucion:
                    # Sin column_config: la columna `aporte` es una fracción y el
                    # formato de la casa ya la escala. Pasar aquí un formato de
                    # porcentaje sobre el decimal crudo dibujaba 0.08% donde el
                    # emisor creció 7.6%, y el pie pedía multiplicar por cien de
                    # memoria en vez de arreglarlo.
                    mostrar_tabla(atribucion.como_tabla())
                    st.caption(
                        f"AFFO por acción de los últimos doce meses ({a1:,.2f}) contra los doce "
                        f"anteriores ({a0:,.2f}). El total cierra exacto porque el término "
                        "cruzado se reporta por separado en vez de repartirse."
                    )
            else:
                st.info(
                    "Hace falta un año de precios y ocho trimestres de AFFO para atribuir: "
                    "cuatro que cierran hoy y cuatro que cierran hace un año."
                )

            st.subheader("Ingreso en términos reales")
            # Del LIBRO y por años completos. Leer la tabla de dividendos del mercado
            # sumaba el monto POR ACCIÓN de cada emisora sin ponderar por títulos:
            # un número que no es dinero ni tasa, y que sale igual con diez mil
            # títulos de una emisora que con uno.
            serie_ingreso = ingreso_anual_por_dividendos(transacciones, hasta=asof)
            if len(serie_ingreso) < 2:
                st.info(
                    "Hacen falta dos años calendario COMPLETOS de dividendos cobrados en el "
                    "libro. Un año a medias entra a la serie como una caída que nadie sufrió."
                )
            elif macro.inpc.empty:
                st.info("Falta el INPC para deflactar el ingreso.")
            else:
                real = crecimiento_real_anualizado(serie_ingreso, macro.inpc)
                a, b, c = st.columns(3)
                # `pct` ya dibuja el hueco cuando no hay dato. Poner además una
                # guardia por valor falsy convertía un crecimiento REAL de 0.00%
                # —que es el hallazgo de esta sección— en un guion de dato faltante.
                a.metric("Crecimiento nominal del ingreso", pct(real["nominal"]))
                b.metric("Inflación", pct(real["inflacion"]))
                c.metric("Crecimiento REAL", pct(real["real"]),
                         delta_color="normal" if (real["real"] or 0) > 0 else "inverse")
                st.caption(
                    f"Sobre dividendos efectivamente cobrados en {len(serie_ingreso)} años "
                    f"completos ({serie_ingreso.index[0].year}–{serie_ingreso.index[-1].year}). "
                    "El año en curso queda fuera hasta que cierre."
                )
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
        mostrar_tabla(resultado.como_tabla(),
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
        mostrar_tabla(
            comparativa,
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

    # Una columna nominal y una real, y la resta la hace la pantalla. Publicar una
    # sola columna con unos renglones reales y otros nominales, y pedir en el pie
    # que el lector le reste la inflación a unos sí y a otros no, es dejar a medias
    # justo la comparación que la sección dice ser la única honesta —teniendo el
    # insumo de inflación capturado tres renglones arriba—.
    # Fisher en las dos direcciones, no una suma en una y un cociente en la otra:
    # con 3% de inflación la diferencia entre `r + i` y `(1+r)(1+i) − 1` son 10 bps,
    # y una tabla que existe para comparar renglones no puede armarlos con dos
    # convenciones distintas.
    def _a_nominal(real: float | None) -> float | None:
        return None if real is None else (1 + real) * (1 + inflacion) - 1

    filas = [
        {"Instrumento": "Portafolio de REITs (neto de impuestos)",
         "Rendimiento nominal": _a_nominal(detalle["real_despues_de_impuestos"]),
         "Rendimiento real": detalle["real_despues_de_impuestos"], "Garantizado": "No"},
        {"Instrumento": "Udibono 10 años",
         "Rendimiento nominal": _a_nominal(macro.udibono10),
         "Rendimiento real": macro.udibono10, "Garantizado": "Sí"},
        {"Instrumento": "Cetes 28 días", "Rendimiento nominal": repo.valor_tasa("CETES28", asof=asof),
         "Garantizado": "Sí"},
        {"Instrumento": "Mbono 10 años", "Rendimiento nominal": repo.valor_tasa("MBONO10", asof=asof),
         "Garantizado": "Sí"},
        {"Instrumento": "UST 10 años (USD)", "Rendimiento nominal": macro.ust10, "Garantizado": "Sí"},
    ]
    df = pd.DataFrame(filas)
    for columna in ("Rendimiento nominal", "Rendimiento real"):
        df[columna] = pd.to_numeric(df.get(columna), errors="coerce")
    # El Udibono y los REITs nacen reales, así que su nominal se reconstruye
    # sumando la inflación; los demás nacen nominales y se deflactan aquí.
    faltan = df["Rendimiento real"].isna()
    df.loc[faltan, "Rendimiento real"] = (
        (1 + df.loc[faltan, "Rendimiento nominal"]) / (1 + inflacion) - 1
    )
    mostrar_tabla(df)
    st.caption(
        f"La columna **Rendimiento real** descuenta la inflación esperada de {inflacion:.2%} que capturaste "
        "arriba. Es la única columna comparable entre renglones: un Cete nominal y un Udibono "
        "real no se comparan de frente."
    )
    explicar("Udibono")

st.divider()
descargo()
