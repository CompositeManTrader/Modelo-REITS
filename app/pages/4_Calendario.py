"""Calendario de distribuciones y el dividendo en términos reales."""

from __future__ import annotations

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
    selector_de_corte,
)
from marca import GRIS, PROFIT, encabezado, inyectar_estilos  # noqa: E402

from src.ingesta.tasas import deflactar  # noqa: E402
from src.portafolio.transacciones import procesar_libro  # noqa: E402
from src.servicio import contexto_macro  # noqa: E402
from src.simulacion.escenarios import rastrear_dividendo_real  # noqa: E402

configurar("Calendario", "📅")
inyectar_estilos()
encabezado("Calendario")
st.title("Calendario de distribuciones")

repo = exigir_base()
asof = selector_de_corte()
macro = contexto_macro(repo, asof=asof)

emisores = repo.emisores()
if emisores.empty:
    st.error("No hay emisores en la base.")
    st.stop()

seleccion = st.multiselect(
    "Emisores", sorted(emisores["ticker"]), default=list(sorted(emisores["ticker"])[:5])
)
if not seleccion:
    st.info("Elige al menos un emisor.")
    st.stop()

dividendos = repo.dividendos(seleccion, asof=asof)
if dividendos.empty:
    st.warning("No hay dividendos registrados al corte elegido.")
    st.stop()

# --------------------------------------------------------------------------------------
# Próximas fechas ex-dividendo
# --------------------------------------------------------------------------------------

st.header("Próximas fechas ex-dividendo")
st.caption(
    "La fecha ex es la que importa: quien compra ese día ya no cobra ese dividendo. "
    "La de pago es solo cuándo llega el efectivo."
)

corte = pd.Timestamp(asof)
proximos = dividendos[dividendos["fecha_ex"] >= corte - pd.Timedelta(days=7)].sort_values("fecha_ex")
if proximos.empty:
    st.info(
        "No hay fechas ex futuras registradas al corte. El calendario se llena conforme los "
        "emisores declaran, así que un calendario vacío hacia adelante es normal."
    )
else:
    vista = proximos.head(30)[
        ["ticker", "fecha_declaracion", "fecha_ex", "fecha_registro", "fecha_pago", "monto", "frecuencia"]
    ]
    mostrar_tabla(vista)

    urgentes = proximos[
        (proximos["fecha_ex"] >= corte) & (proximos["fecha_ex"] <= corte + pd.Timedelta(days=14))
    ]
    for _, r in urgentes.iterrows():
        dias = (r["fecha_ex"] - corte).days
        st.warning(
            f"**{r['ticker']}** va ex-dividendo en {dias} día(s) ({r['fecha_ex'].date()}) "
            f"por {r['monto']:.4f} USD por título."
        )

# --------------------------------------------------------------------------------------
# Proyección de flujo de caja a 12 meses
# --------------------------------------------------------------------------------------

st.divider()
st.header("Proyección de flujo de caja a 12 meses")

transacciones = repo.transacciones(asof=asof)
if transacciones.empty:
    st.info(
        "Registra transacciones en la página de Portafolio para proyectar el ingreso de tu "
        "cartera. Mientras tanto, abajo va el calendario por título."
    )
    posiciones = {}
else:
    estado = procesar_libro(transacciones, hasta=asof)
    posiciones = {t: p.cantidad for t, p in estado.posiciones.items() if p.cantidad > 0}

historico = dividendos[dividendos["fecha_ex"] <= corte]
if not historico.empty:
    ultimo_por_ticker = historico.sort_values("fecha_ex").groupby("ticker").last()
    filas = []
    for ticker, r in ultimo_por_ticker.iterrows():
        pagos_al_anio = 12 if r["frecuencia"] == "mensual" else 4
        titulos = posiciones.get(ticker, 0.0)
        for k in range(pagos_al_anio):
            fecha = corte + pd.DateOffset(months=int(12 / pagos_al_anio) * (k + 1))
            filas.append(
                {
                    "mes": fecha.strftime("%Y-%m"),
                    "ticker": ticker,
                    "monto_por_titulo": float(r["monto"]),
                    "titulos": titulos,
                    "ingreso_proyectado": float(r["monto"]) * titulos,
                }
            )
    proyeccion = pd.DataFrame(filas)
    if posiciones:
        por_mes = proyeccion.groupby("mes")["ingreso_proyectado"].sum()
        figura = go.Figure()
        figura.add_bar(x=por_mes.index, y=por_mes.to_numpy(), marker_color=PROFIT)
        figura.update_layout(height=300, yaxis_title="USD proyectados",
                             margin={"t": 20, "b": 20, "l": 10, "r": 10}, showlegend=False)
        st.plotly_chart(figura)
        st.metric("Ingreso proyectado a 12 meses", dinero(por_mes.sum()))
        st.caption(
            "Proyección con el último dividendo declarado, sin suponer aumentos. Un emisor "
            "puede recortar: la Puerta 3 existe para anticiparlo, no esta proyección."
        )
    mostrar_tabla(proyeccion.head(40))

# --------------------------------------------------------------------------------------
# El dividendo en términos reales
# --------------------------------------------------------------------------------------

st.divider()
st.header("El dividendo en términos reales")
st.info(
    "Es la métrica que de verdad importa para vivir de rentas y casi nadie la mira. "
    "Realty Income creció su dividendo 3.2% anual de 2021 a 2025 contra inflación de ~3.3%: "
    "el ingreso quedó **plano en poder adquisitivo** mientras el papel se veía sano."
)

ticker_real = st.selectbox("Emisor", sorted(seleccion), key="div_real")
serie = dividendos[dividendos["ticker"] == ticker_real].set_index("fecha_ex")["monto"]
anual = serie.resample("YE").sum()

if len(anual) >= 3 and not macro.inpc.empty:
    real = deflactar(anual, macro.inpc)
    figura = go.Figure()
    figura.add_scatter(x=anual.index, y=anual.to_numpy(), name="Dividendo nominal",
                       line={"color": GRIS})
    figura.add_scatter(x=real.index, y=real.to_numpy(), name="Dividendo REAL (pesos de hoy)",
                       line={"color": PROFIT, "width": 3})
    figura.update_layout(height=340, yaxis_title="USD por título",
                         margin={"t": 20, "b": 20, "l": 10, "r": 10},
                         legend={"orientation": "h", "y": 1.12})
    st.plotly_chart(figura)

    alerta = rastrear_dividendo_real(ticker_real, serie, macro.inpc)
    if alerta.dispara_alerta:
        st.error(alerta.mensaje)
    else:
        st.success(alerta.mensaje)

    st.caption(
        "La alerta de estancamiento real es una razón de venta **distinta** de la valuación y "
        "del deterioro: la posición puede tener balance impecable y cotizar barata, y aun así "
        "haber dejado de servir a tu objetivo."
    )
else:
    st.info("Hace falta más historia de dividendos y del índice de precios para deflactar.")

# --------------------------------------------------------------------------------------
# Historial de aumentos y recortes
# --------------------------------------------------------------------------------------

st.divider()
st.header("Historial de aumentos y recortes")

filas = []
for ticker in seleccion:
    s = dividendos[dividendos["ticker"] == ticker].sort_values("fecha_ex")
    if len(s) < 2:
        continue
    cambios = s["monto"].pct_change()
    aumentos = int((cambios > 0.001).sum())
    recortes = int((cambios < -0.001).sum())

    racha = 0
    anual = s.set_index("fecha_ex")["monto"].resample("YE").sum()
    for i in range(len(anual) - 1, 0, -1):
        if anual.iloc[i] > anual.iloc[i - 1] * 1.001:
            racha += 1
        else:
            break

    ultimo_recorte = None
    if recortes:
        idx = cambios[cambios < -0.001].index
        ultimo_recorte = s.loc[idx[-1], "fecha_ex"].date()

    filas.append(
        {
            "ticker": ticker,
            "aumentos": aumentos,
            "recortes": recortes,
            "racha_de_años_al_alza": racha,
            "ultimo_recorte": ultimo_recorte,
            "dividendo_actual": float(s["monto"].iloc[-1]),
        }
    )

if filas:
    historial = pd.DataFrame(filas)
    mostrar_tabla(historial)
    con_recorte = historial[historial["recortes"] > 0]
    if not con_recorte.empty:
        st.warning(
            "Emisores con recortes en su historia: "
            + ", ".join(con_recorte["ticker"])
            + ". Están en el universo a propósito: un sistema que solo funciona con "
            "sobrevivientes no sirve."
        )

explicar("AFFO", "Udibono")
st.divider()
st.caption(
    f"Calendario al corte del {asof}. Las fechas futuras son proyección con el último "
    "dividendo declarado, no compromiso del emisor."
)
descargo()
