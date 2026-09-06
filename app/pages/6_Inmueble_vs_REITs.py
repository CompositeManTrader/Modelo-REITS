"""El comparativo central: un inmueble en renta en CDMX contra un portafolio de REITs."""

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
)

from src.fiscal.mexico import comparar_modalidades_arrendamiento  # noqa: E402
from src.servicio import contexto_macro  # noqa: E402
from src.simulacion.inmueble_cdmx import (  # noqa: E402
    AVISO_INDICES,
    RIESGOS_CUALITATIVOS,
    SupuestosInmueble,
    calcular_hipoteca,
    capital_para_meta_de_ingreso,
    comparar_con_reits,
    comparar_portafolio_propio,
    diagnosticar_carry,
    evaluar_inmueble,
    operacion_anual,
    tabla_riesgos,
)

configurar("Inmueble vs REITs", "🏘️")
st.title("Un departamento en CDMX contra un portafolio de REITs")

repo = exigir_base()
asof = selector_de_corte()
macro = contexto_macro(repo, asof=asof)

st.warning(AVISO_INDICES)

# --------------------------------------------------------------------------------------
# Supuestos
# --------------------------------------------------------------------------------------

st.sidebar.divider()
st.sidebar.markdown("**El inmueble**")
precio = st.sidebar.number_input("Precio de operación (MXN)", 0.0, value=4_500_000.0, step=100_000.0,
                                 help="El precio que efectivamente se paga, no el de anuncio.")
renta = st.sidebar.number_input("Renta mensual (MXN)", 0.0, value=22_000.0, step=500.0)
anios = st.sidebar.slider("Horizonte (años)", 3, 30, 10)
plusvalia = st.sidebar.slider("Plusvalía anual esperada", -0.02, 0.12, 0.04, 0.005, format="%.3f")
crecimiento_renta = st.sidebar.slider("Crecimiento anual de la renta", 0.0, 0.10, 0.04, 0.005, format="%.3f")
sueldo = st.sidebar.number_input("Tu ingreso por sueldo (MXN/año)", 0.0, value=0.0, step=100_000.0,
                                 help="Si es mayor a cero, la renta se apila y entra en marginal de 30–35%.")

st.sidebar.markdown("**Apalancamiento**")
hipoteca = st.sidebar.number_input("Monto de hipoteca (MXN)", 0.0, value=0.0, step=100_000.0)
tasa_hipoteca = st.sidebar.slider("Tasa hipotecaria", 0.085, 0.145, 0.115, 0.0025, format="%.4f")
plazo = st.sidebar.slider("Plazo de la hipoteca (años)", 5, 30, 20)

st.sidebar.markdown("**La alternativa**")
yield_neto_reits = st.sidebar.slider(
    "Yield NETO de impuestos del portafolio de REITs", 0.01, 0.10, 0.042, 0.0025, format="%.4f",
    help="Ya después de la retención estadounidense y del ISR mexicano.",
)
crecimiento_reits = st.sidebar.slider("Crecimiento del portafolio", -0.02, 0.10, 0.030, 0.0025, format="%.4f")
descuento = st.sidebar.slider("Tasa de descuento", 0.04, 0.16, 0.09, 0.005, format="%.3f")

supuestos = SupuestosInmueble(
    precio=precio, renta_mensual=renta, anios=anios,
    plusvalia_anual=plusvalia, crecimiento_renta_anual=crecimiento_renta,
    inflacion=float(macro.inflacion_mx) if macro.inflacion_mx else 0.045,
    ingreso_por_sueldo=sueldo, monto_hipoteca=hipoteca,
    tasa_hipoteca=tasa_hipoteca, plazo_hipoteca_anios=plazo,
)

# --------------------------------------------------------------------------------------
# Veredicto
# --------------------------------------------------------------------------------------

comparativo = comparar_con_reits(
    supuestos, yield_neto_reits=yield_neto_reits,
    crecimiento_reits=crecimiento_reits, tasa_descuento=descuento,
)
resultado = evaluar_inmueble(supuestos, tasa_descuento=descuento)

st.header("Veredicto")
(st.success if comparativo.ganador == "Inmueble" else st.error)(
    f"### Gana: {comparativo.ganador}\n\n{comparativo.mensaje}"
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("NPV del inmueble", dinero(comparativo.npv_inmueble, "MXN", 0))
c2.metric("NPV del portafolio", dinero(comparativo.npv_reits, "MXN", 0))
c3.metric("TIR del inmueble", pct(comparativo.tir_inmueble) if comparativo.tir_inmueble else "—")
c4.metric("TIR del portafolio", pct(comparativo.tir_reits) if comparativo.tir_reits else "—")

if comparativo.plusvalia_necesaria is not None:
    brecha = comparativo.plusvalia_necesaria - supuestos.plusvalia_anual
    st.metric(
        "Plusvalía anual que necesita el departamento para empatar",
        pct(comparativo.plusvalia_necesaria),
        delta=f"{brecha * 10_000:,.0f} bps sobre tu supuesto",
        delta_color="inverse" if brecha > 0 else "normal",
    )
    st.caption(
        "Este número suele ser revelador: cuando sale muy por encima de la inflación, queda "
        "claro que la tesis del inmueble no es la renta sino una apuesta direccional a la "
        "apreciación. Es una tesis legítima, pero es otra tesis y tiene otro riesgo."
    )

for aviso in resultado.advertencias:
    st.info(aviso)

explicar("Udibono", "NAV")
st.divider()

# --------------------------------------------------------------------------------------
# Cascada de costos
# --------------------------------------------------------------------------------------

st.header("Adónde se va la renta")
operacion = operacion_anual(supuestos)
tabla = operacion.como_tabla()
tabla["pct_renta"] = tabla["pct_renta"] * 100.0

c1, c2 = st.columns([3, 2])
with c1:
    mostrar_tabla(
        tabla,
        column_config={
            "concepto": "Concepto",
            "monto": st.column_config.NumberColumn("MXN al año", format="$%,.0f"),
            "pct_renta": st.column_config.NumberColumn("% de la renta bruta", format="%.1f%%"),
        },
    )
with c2:
    st.metric("Rendimiento bruto sobre el precio", pct(supuestos.rendimiento_bruto))
    st.metric("Neto antes de ISR", pct(operacion.noi_antes_isr / supuestos.precio))
    st.metric("Neto después de ISR", pct(operacion.rendimiento_neto_sobre_precio))
    st.metric("Costos de entrada", pct(supuestos.costos_entrada_pct),
              help="ISAI, notario, avalúo y registro. Se pagan antes de que el inmueble produzca un peso.")
    st.metric("Fricción de transacción, ida y vuelta", pct(resultado.friccion_transaccion))
    st.caption(
        f"Más {pct(resultado.isr_salida_pct)} de ISR sobre la ganancia al salir. Se reportan "
        "separados porque la fricción de transacción se paga aunque el inmueble no suba un peso."
    )

st.subheader("El ISR cambia el resultado casi 30%")
st.caption(
    "La renta como único ingreso paga una tasa efectiva de alrededor de 5%. Apilada sobre un "
    "sueldo entra en marginal de 30–35%. Es el parámetro que más mueve el capital requerido."
)
modalidades = comparar_modalidades_arrendamiento(
    supuestos.renta_bruta_anual, supuestos.predial_anual or supuestos.renta_bruta_anual * 0.018,
    sueldo if sueldo > 0 else 900_000.0,
)
modalidades["Tasa efectiva sobre renta"] = modalidades["Tasa efectiva sobre renta"] * 100.0
mostrar_tabla(
    modalidades,
    column_config={
        "Base gravable": st.column_config.NumberColumn(format="$%,.0f"),
        "ISR": st.column_config.NumberColumn(format="$%,.0f"),
        "Tasa efectiva sobre renta": st.column_config.NumberColumn(format="%.1f%%"),
        "Neto": st.column_config.NumberColumn(format="$%,.0f"),
    },
)

st.divider()

# --------------------------------------------------------------------------------------
# Apalancamiento
# --------------------------------------------------------------------------------------

st.header("Apalancamiento: el carry es negativo")
carry = diagnosticar_carry(supuestos)
(st.error if carry.es_negativo else st.success)(carry.mensaje)

if hipoteca > 0:
    hip = calcular_hipoteca(hipoteca, tasa_hipoteca, plazo)
    c1, c2, c3 = st.columns(3)
    c1.metric("Mensualidad", dinero(hip.mensualidad, "MXN", 0))
    c2.metric("Carry (bruto − tasa)", pct(carry.carry))
    c3.metric("Valor presente de la erosión inflacionaria", dinero(carry.valor_presente_erosion, "MXN", 0))

    por_anio = hip.tabla.groupby("anio")[["interes", "capital"]].sum()
    real = por_anio.copy()
    for anio in real.index:
        real.loc[anio] = por_anio.loc[anio] / (1.0 + supuestos.inflacion) ** anio
    figura = go.Figure()
    figura.add_bar(x=por_anio.index, y=por_anio["interes"] + por_anio["capital"],
                   name="Pago nominal", marker_color="#57606a")
    figura.add_bar(x=real.index, y=real["interes"] + real["capital"],
                   name="Pago en pesos de hoy", marker_color="#1a7f37")
    figura.update_layout(height=320, barmode="overlay", xaxis_title="Año",
                         yaxis_title="MXN", margin={"t": 20, "b": 20, "l": 10, "r": 10},
                         legend={"orientation": "h", "y": 1.12})
    st.plotly_chart(figura)
    st.caption(
        "La barra gris es lo que pagas; la verde es lo que ese pago **vale** en poder "
        "adquisitivo de hoy. Esa brecha es el único argumento real del apalancamiento "
        "inmobiliario en México: la mensualidad es nominal fija y la renta se indiza, así que "
        "la deuda es una posición corta en pesos nominales. No es flujo: es una apuesta a la inflación."
    )
else:
    st.info("Sin hipoteca. Sube el monto en la barra lateral para ver el efecto del apalancamiento.")

st.divider()

# --------------------------------------------------------------------------------------
# Riesgos
# --------------------------------------------------------------------------------------

st.header("Riesgos cuantificados, no mencionados")
riesgos = tabla_riesgos(supuestos, descuento)
mostrar_tabla(
    riesgos[["riesgo", "impacto_flujo", "probabilidad_supuesta", "descripcion"]],
    column_config={
        "riesgo": "Escenario",
        "impacto_flujo": st.column_config.NumberColumn("Impacto (MXN)", format="$%,.0f"),
        "probabilidad_supuesta": st.column_config.NumberColumn("Probabilidad supuesta", format="%.0f%%"),
        "descripcion": "Detalle",
    },
)
mostrar_tabla(pd.DataFrame(RIESGOS_CUALITATIVOS))

st.divider()

# --------------------------------------------------------------------------------------
# Capital requerido y flujos
# --------------------------------------------------------------------------------------

st.header("Capital requerido para la misma meta de ingreso")
meta_ingreso = st.number_input("Meta de ingreso anual (MXN)", 0.0, value=600_000.0, step=50_000.0)
capital = capital_para_meta_de_ingreso(supuestos, meta_ingreso)
c1, c2, c3 = st.columns(3)
c1.metric("Vía inmuebles", dinero(capital["capital_requerido_inmueble"], "MXN", 0))
c2.metric("Número de departamentos", f"{capital['numero_de_inmuebles']:.1f}")
c3.metric("Vía REITs", dinero(meta_ingreso / yield_neto_reits, "MXN", 0))
st.warning(capital["nota"])

st.subheader("Flujos del proyecto inmobiliario")
detalle = resultado.detalle.copy()
mostrar_tabla(
    detalle,
    column_config={
        "anio": st.column_config.NumberColumn("Año", format="%d"),
        "renta_bruta": st.column_config.NumberColumn("Renta bruta", format="$%,.0f"),
        "flujo_operacion": st.column_config.NumberColumn("Flujo de operación", format="$%,.0f"),
        "servicio_deuda": st.column_config.NumberColumn("Servicio de deuda", format="$%,.0f"),
        "flujo_neto": st.column_config.NumberColumn("Flujo neto", format="$%,.0f"),
        "valor_inmueble": st.column_config.NumberColumn("Valor del inmueble", format="$%,.0f"),
        "saldo_hipoteca": st.column_config.NumberColumn("Saldo hipoteca", format="$%,.0f"),
    },
)

st.divider()

# --------------------------------------------------------------------------------------
# Portafolio inmobiliario propio
# --------------------------------------------------------------------------------------

st.header("Tus inmuebles reales contra un portafolio equivalente")
st.caption(
    "El corazón del proyecto: no «¿conviene comprar un departamento?» en abstracto, sino "
    "«¿los que ya tengo están rindiendo más que la alternativa?»."
)

with st.expander("Capturar un inmueble que ya tienes"), st.form("nuevo_inmueble"):
    c1, c2, c3 = st.columns(3)
    nombre = c1.text_input("Nombre", value="Departamento Condesa")
    tipo = c2.selectbox("Tipo", ["departamento", "casa", "local", "bodega", "terreno"])
    fecha_compra = c3.date_input("Fecha de compra", value=dt.date(2018, 1, 1), max_value=dt.date.today())
    c4, c5, c6 = st.columns(3)
    precio_compra = c4.number_input("Precio de compra (MXN)", 0.0, value=3_000_000.0, step=100_000.0)
    renta_actual = c5.number_input("Renta mensual actual (MXN)", 0.0, value=18_000.0, step=500.0)
    valor_actual = c6.number_input("Valor actual estimado (MXN)", 0.0, value=4_200_000.0, step=100_000.0)
    c7, c8, c9 = st.columns(3)
    mantenimiento = c7.number_input("Mantenimiento mensual (MXN)", 0.0, value=2_500.0, step=250.0)
    predial = c8.number_input("Predial anual (MXN)", 0.0, value=9_000.0, step=500.0)
    saldo = c9.number_input("Saldo de hipoteca (MXN)", 0.0, value=0.0, step=100_000.0)
    if st.form_submit_button("Guardar inmueble"):
        repo.guardar_inmuebles([{
            "nombre": nombre, "tipo": tipo, "fecha_compra": fecha_compra,
            "precio_compra": precio_compra, "renta_mensual": renta_actual,
            "mantenimiento_mensual": mantenimiento, "predial_anual": predial,
            "saldo_hipoteca": saldo, "valor_actual": valor_actual,
        }])
        st.success("Inmueble guardado.")
        st.rerun()

inmuebles = repo.inmuebles()
if inmuebles.empty:
    st.info("Captura al menos un inmueble para comparar tu portafolio real.")
else:
    comparacion = comparar_portafolio_propio(
        inmuebles, yield_neto_reits=yield_neto_reits,
        inflacion=float(macro.inflacion_mx) if macro.inflacion_mx else 0.045,
    )
    vista = comparacion.copy()
    for col in ("rendimiento_corriente", "tir_nominal", "tir_real", "plusvalia_anualizada",
                "yield_neto_reits", "brecha_vs_reits"):
        vista[col] = pd.to_numeric(vista[col], errors="coerce") * 100.0
    mostrar_tabla(
        vista,
        column_config={
            "nombre": "Inmueble",
            "valor_actual": st.column_config.NumberColumn("Valor actual", format="$%,.0f"),
            "rendimiento_corriente": st.column_config.NumberColumn("Rend. corriente", format="%.2f%%"),
            "tir_nominal": st.column_config.NumberColumn("TIR nominal", format="%.2f%%"),
            "tir_real": st.column_config.NumberColumn("TIR REAL", format="%.2f%%"),
            "plusvalia_anualizada": st.column_config.NumberColumn("Plusvalía anualizada", format="%.2f%%"),
            "yield_neto_reits": st.column_config.NumberColumn("Yield neto REITs", format="%.2f%%"),
            "brecha_vs_reits": st.column_config.NumberColumn("Brecha", format="%.2f%%"),
        },
    )
    negativas = comparacion[pd.to_numeric(comparacion["tir_real"], errors="coerce") < 0]
    if not negativas.empty:
        st.error(
            "Estos inmuebles tienen **TIR real negativa**: están perdiendo poder adquisitivo. "
            + ", ".join(negativas["nombre"])
        )
    st.caption(
        "Simplificación declarada: se supone renta constante en términos reales desde la "
        "compra. Con el histórico de rentas efectivamente cobradas el número mejora, pero "
        "esta aproximación ya basta para el contraste."
    )

st.divider()
st.info(
    "**Restricción de modelación explícita.** Las horas propias de administración van a costo "
    "cero: el NPV mide retorno sobre capital invertido, no sobre tiempo. Si valoras tu tiempo, "
    "el resultado del inmueble es peor que el que aquí se muestra."
)
descargo()
