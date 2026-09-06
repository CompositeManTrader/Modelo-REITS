"""Portada: la comparación que decide todo lo demás.

La pantalla principal no muestra el rendimiento del portafolio: muestra si el
activo con riesgo le está ganando al activo sin riesgo. El Udibono a 10 años
paga una tasa real fija garantizada. Si un portafolio de REITs ofrece menos que
eso después de impuestos, el modelo lo dice con esas palabras (P10).
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comun import (  # noqa: E402
    configurar,
    descargo,
    exigir_base,
    explicar,
    mostrar_tabla,
    pct,
    selector_de_corte,
)

from src.config import AVISO_TITULAR_12, RENDIMIENTOS_NAREIT_HISTORICOS  # noqa: E402
from src.fiscal.mexico import DESCARGO_FISCAL, rendimiento_real_despues_de_impuestos  # noqa: E402
from src.servicio import contexto_macro, tabla_universo  # noqa: E402
from src.simulacion.escenarios import comparar_contra_udibono, tabla_contexto_nareit  # noqa: E402

configurar("Inicio")
st.title("Plataforma de valuación de REITs")
st.caption(
    "Valuación con rigor de analista desde estados financieros originales, construcción de "
    "portafolio, y el comparativo contra comprar un inmueble en renta en CDMX."
)

repo = exigir_base()
asof = selector_de_corte()
macro = contexto_macro(repo, asof=asof)

# --------------------------------------------------------------------------------------
# P10 — La comparación que va siempre en la pantalla principal
# --------------------------------------------------------------------------------------

universo = tabla_universo(repo, asof=asof)


def _yield_sugerido() -> float:
    """Mediana del AFFO yield del universo al corte, acotada a un rango razonable."""
    if universo.empty or "affo_yield" not in universo:
        return 0.055
    mediana = universo["affo_yield"].dropna().median()
    if mediana is None or not (0.01 <= float(mediana) <= 0.15):
        return 0.055
    return round(float(mediana), 4)


st.header("Lo primero: ¿le ganas al activo sin riesgo?")

col_a, col_b = st.columns([2, 1])
with col_b:
    st.markdown("**Tus supuestos**")
    yield_bruto = st.number_input(
        "AFFO yield bruto esperado del portafolio",
        min_value=0.010, max_value=0.150,
        value=_yield_sugerido(),
        step=0.0025, format="%.4f",
        help=(
            "Rendimiento del flujo ajustado sobre el precio, antes de impuestos. El valor "
            "sugerido es la mediana del universo al corte."
        ),
    )
    crecimiento = st.number_input(
        "Crecimiento real esperado del AFFO por acción",
        min_value=-0.05, max_value=0.10, value=0.020, step=0.0025, format="%.4f",
        help="Contra la historia del sector, no contra la esperanza. Ver la página de Sectorial.",
    )
    inflacion = st.number_input(
        "Inflación mexicana esperada",
        min_value=0.0, max_value=0.20,
        value=float(macro.inflacion_mx) if macro.inflacion_mx else 0.045,
        step=0.0025, format="%.4f",
    )
    udibono = st.number_input(
        "Udibono 10 años (tasa REAL)",
        min_value=0.0, max_value=0.12,
        value=float(macro.udibono10) if macro.udibono10 else 0.047,
        step=0.0005, format="%.4f",
    )
    tiene_w8 = st.checkbox("Tengo W-8BEN presentado", value=True)

with col_a:
    comparacion = comparar_contra_udibono(
        yield_bruto, crecimiento, inflacion, udibono, tiene_w8ben=tiene_w8
    )
    detalle = rendimiento_real_despues_de_impuestos(
        yield_bruto, crecimiento, inflacion, tiene_w8ben=tiene_w8
    )

    if comparacion.el_sin_riesgo_gana:
        st.error(f"### El activo sin riesgo paga más que el activo con riesgo\n\n{comparacion.mensaje}")
    else:
        st.success(f"### El portafolio de REITs paga una prima sobre el activo sin riesgo\n\n{comparacion.mensaje}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Yield bruto", pct(detalle["yield_bruto"]))
    m2.metric(
        "Yield neto de impuestos", pct(detalle["yield_neto"]),
        delta=pct(detalle["yield_neto"] - detalle["yield_bruto"]), delta_color="inverse",
        help="Retención de 10% en EE. UU. con W-8BEN más 10% adicional en México: ~20% combinado.",
    )
    m3.metric("REITs, real después de impuestos", pct(comparacion.real_reits_despues_impuestos))
    m4.metric(
        "Udibono 10 años, real garantizado", pct(comparacion.real_udibono),
        delta=f"{comparacion.brecha * 10_000:,.0f} bps de brecha",
        delta_color="normal" if comparacion.brecha > 0 else "inverse",
    )

    figura = go.Figure()
    figura.add_bar(
        x=["Udibono 10a (real, garantizado)", "REITs (real, esperado, neto de impuestos)"],
        y=[comparacion.real_udibono, comparacion.real_reits_despues_impuestos],
        marker_color=["#57606a", "#1a7f37" if comparacion.brecha > 0 else "#b42318"],
        text=[pct(comparacion.real_udibono), pct(comparacion.real_reits_despues_impuestos)],
        textposition="outside",
    )
    figura.update_layout(
        height=280, margin={"t": 20, "b": 20, "l": 10, "r": 10},
        yaxis_tickformat=".1%", yaxis_title="Rendimiento real anual",
        showlegend=False,
    )
    st.plotly_chart(figura)

st.caption(DESCARGO_FISCAL)
explicar("Udibono", "AFFO", "prima")

st.divider()

# --------------------------------------------------------------------------------------
# Semáforo del universo
# --------------------------------------------------------------------------------------

st.header("El universo, al corte")
st.caption(
    "El percentil de prima es de cada emisor contra **su propia historia**. Comparar niveles "
    "de yield entre emisores es rotar hacia el deterioro: el yield tiene el precio en el "
    "denominador, así que un precio que se desploma lo infla mecánicamente."
)

if universo.empty:
    st.warning("No hay emisores con datos al corte elegido.")
else:
    if universo["solo_demo"].all():
        st.error(
            "**Todos los emisores tienen datos de DEMOSTRACIÓN.** Corre "
            "`python scripts/ingesta.py` para traer datos de fuente primaria desde la SEC."
        )
    vista = universo[
        ["ticker", "nombre", "sector", "precio", "affo_yield", "dividend_yield",
         "percentil_prima", "n_observaciones", "payout_affo", "p_affo", "accion"]
    ].copy()
    mostrar_tabla(
        vista,
        column_config={
            "ticker": "Emisor",
            "nombre": "Nombre",
            "sector": "Sector",
            "precio": st.column_config.NumberColumn("Precio", format="$%.2f"),
            "affo_yield": st.column_config.NumberColumn("AFFO yield", format="%.2f%%"),
            "dividend_yield": st.column_config.NumberColumn("Div. yield", format="%.2f%%"),
            # `mostrar_tabla` ya trajo el percentil a escala 0–100, así que la barra
            # se acota ahí. Con max_value=1.0 la barra saldría llena desde el 1%.
            "percentil_prima": st.column_config.ProgressColumn(
                "Percentil de prima", min_value=0.0, max_value=100.0, format="%.0f%%",
                help="Alto = barato contra su propia historia. Ventana expandible.",
            ),
            "n_observaciones": st.column_config.NumberColumn("Obs.", format="%d"),
            "payout_affo": st.column_config.NumberColumn("Payout AFFO", format="%.1f%%"),
            "p_affo": st.column_config.NumberColumn("P/AFFO", format="%.1fx"),
            "accion": "Acción",
        },
    )
    st.caption(
        "Un guion largo es «no hay dato suficiente», no un cero. Siete de los diez emisores "
        "todavía no tienen cuatro trimestres válidos consecutivos de AFFO: eso es cobertura "
        "del parser, y se ve en la columna de observaciones."
    )

    with st.expander("Cómo leer la columna de Acción"):
        st.markdown(
            "El semáforo no es una caja negra: son **tres puertas independientes** y cada una "
            "responde una pregunta distinta.\n\n"
            "- **DESCARTADO** — reprueba la Puerta 1 (calidad). Lo que falla no está barato: "
            "está descartado. Ningún descuento compensa un payout insostenible.\n"
            "- **COMPRAR / MANTENER / NO COMPRAR MÁS** — es la Puerta 2 (valuación). Modula "
            "compras nuevas. **Nunca dispara venta por sí sola.**\n"
            "- **VENDER** — solo la dispara la Puerta 3 (deterioro): payout sobre AFFO arriba de "
            "100% dos trimestres seguidos, spread de inversión negativo dos trimestres, AFFO por "
            "acción cayendo dos trimestres, apalancamiento arriba de 6.5x, o pérdida del grado de "
            "inversión. Eso es tesis rota, no precio caro.\n"
            "- **INCONCLUSO** — no hay historia suficiente para emitir un percentil confiable. "
            "No es lo mismo que MANTENER."
        )

st.divider()

# --------------------------------------------------------------------------------------
# Contexto histórico
# --------------------------------------------------------------------------------------

st.header("Contexto histórico, para no extrapolar")
c1, c2 = st.columns([1, 1])
with c1:
    st.subheader("Índice FTSE Nareit All Equity")
    contexto = tabla_contexto_nareit()
    mostrar_tabla(
        contexto,
        column_config={
            "periodo": "Ventana",
            "rendimiento_nominal": st.column_config.NumberColumn("Nominal", format="%.2f%%"),
            "rendimiento_real": st.column_config.NumberColumn("Real", format="%.2f%%"),
        },
    )
    st.warning(AVISO_TITULAR_12)
with c2:
    st.subheader("La diferencia entre nominal y real")
    figura = go.Figure()
    periodos = [p for p, _, r in RENDIMIENTOS_NAREIT_HISTORICOS if r is not None]
    nominales = [n for p, n, r in RENDIMIENTOS_NAREIT_HISTORICOS if r is not None]
    reales = [r for p, n, r in RENDIMIENTOS_NAREIT_HISTORICOS if r is not None]
    figura.add_bar(x=periodos, y=nominales, name="Nominal", marker_color="#57606a")
    figura.add_bar(x=periodos, y=reales, name="Real", marker_color="#1a7f37")
    figura.update_layout(
        height=300, barmode="group", yaxis_tickformat=".1%",
        margin={"t": 20, "b": 20, "l": 10, "r": 10}, legend={"orientation": "h", "y": 1.1},
    )
    st.plotly_chart(figura)
    st.caption(
        "En la ventana de 5 años el rendimiento real fue **negativo**. El promedio de largo "
        "plazo no describe ninguna década en particular."
    )

# --------------------------------------------------------------------------------------
# Macro y bitácora
# --------------------------------------------------------------------------------------

st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("UST 10 años", pct(macro.ust10) if macro.ust10 else "—")
c2.metric("Udibono 10 años (real)", pct(macro.udibono10) if macro.udibono10 else "—")
c3.metric("Inflación México (INPC)", pct(macro.inflacion_mx) if macro.inflacion_mx else "—")
c4.metric("Inflación EE. UU. (CPI)", pct(macro.inflacion_us) if macro.inflacion_us else "—")

bitacora = repo.bitacora(limite=12)
if not bitacora.empty:
    with st.expander("Qué entró a la base recientemente"):
        for _, r in bitacora.iterrows():
            st.markdown(f"- `{r['momento'][:16]}` **{r['evento']}** {r.get('ticker') or ''} — {r['detalle']}")

st.divider()
descargo()
