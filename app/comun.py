"""Componentes compartidos de la interfaz.

Convenciones de la aplicación, que valen para todas las páginas:

* **Cada dato lleva su procedencia y su latencia.** Nunca se presenta un dato
  rezagado como si fuera en vivo.
* **Cada métrica de desempeño lleva su conteo de apuestas efectivas.**
* **Cuando no hay observaciones suficientes, el veredicto es INCONCLUSO**, con
  esa palabra. Nunca "GO", nunca un número sin advertencia.
* Cada concepto se explica la primera vez que aparece, construyendo de lo simple
  a lo complejo.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.config import DESCARGO, MIN_APUESTAS_EFECTIVAS, RUTA_BD, Fuente  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402

COLOR_LUZ = {"VERDE": "#1a7f37", "AMARILLO": "#9a6700", "ROJO": "#b42318", "SIN DATOS": "#57606a"}
ICONO_LUZ = {"VERDE": "🟢", "AMARILLO": "🟡", "ROJO": "🔴", "SIN DATOS": "⚪"}


# --------------------------------------------------------------------------------------
# Configuración de página y estado
# --------------------------------------------------------------------------------------


def configurar(titulo: str, icono: str = "🏢") -> None:
    st.set_page_config(page_title=f"{titulo} · Modelo REITs", page_icon=icono, layout="wide")


@st.cache_resource
def obtener_repo(ruta: str | None = None) -> Repositorio:
    return Repositorio(ruta=ruta or RUTA_BD)


def base_existe() -> bool:
    return Path(RUTA_BD).exists()


def exigir_base() -> Repositorio:
    """Devuelve el repositorio o detiene la página con instrucciones claras."""
    if not base_existe():
        st.error(
            "No hay base de datos todavía. Créala con uno de estos comandos y recarga:\n\n"
            "```bash\n"
            "python scripts/sembrar.py        # datos de DEMOSTRACIÓN, para recorrer la app\n"
            "python scripts/ingesta.py        # datos de fuente primaria desde la SEC\n"
            "```"
        )
        st.stop()
    return obtener_repo()


def selector_de_corte(clave: str = "asof") -> dt.date:
    """Selector de fecha de corte, presente en toda la aplicación.

    No es un adorno: es la manifestación en pantalla de que todo el sistema es
    point-in-time. Mover esta fecha hacia atrás hace que la aplicación olvide
    literalmente lo que aún no se publicaba.
    """
    hoy = dt.date.today()
    fecha = st.sidebar.date_input(
        "Fecha de corte",
        value=st.session_state.get(clave, hoy),
        max_value=hoy,
        help=(
            "Todo lo que ves está filtrado por fecha de publicación. Mueve el corte hacia "
            "atrás y el sistema olvida lo que en esa fecha aún no se había publicado. "
            "Es la prueba de que el modelo no usa información del futuro."
        ),
        key=clave,
    )
    if fecha < hoy:
        st.sidebar.info(
            f"Corte histórico: {fecha}. Estás viendo el sistema con la información que "
            "estaba disponible ese día."
        )
    return fecha


def selector_de_emisor(repo: Repositorio, clave: str = "ticker") -> str | None:
    emisores = repo.emisores()
    if emisores.empty:
        st.sidebar.warning("No hay emisores en la base.")
        return None
    opciones = emisores.sort_values("ticker")
    etiquetas = {
        r["ticker"]: f"{r['ticker']} — {r['nombre']} ({r['sector']})" for _, r in opciones.iterrows()
    }
    return st.sidebar.selectbox(
        "Emisor", list(etiquetas), format_func=lambda t: etiquetas[t], key=clave
    )


# --------------------------------------------------------------------------------------
# Avisos y procedencia
# --------------------------------------------------------------------------------------


def descargo() -> None:
    st.caption(DESCARGO)


def avisar_procedencia(fuentes: pd.DataFrame) -> None:
    """Muestra de dónde vienen los datos que alimentan la pantalla."""
    if fuentes is None or fuentes.empty:
        st.warning("No hay datos con procedencia registrada para este emisor al corte elegido.")
        return
    conteo = fuentes["fuente"].value_counts()
    primarias = int(fuentes.get("es_primario", pd.Series(dtype=bool)).sum())
    total = len(fuentes)

    if Fuente.DEMO in conteo.index and conteo.get(Fuente.DEMO, 0) == total:
        st.error(
            "**Todos los datos de esta pantalla son de DEMOSTRACIÓN.** Sirven para recorrer "
            "la aplicación, no para decidir. Corre `python scripts/ingesta.py` para traer "
            "datos de fuente primaria desde la SEC."
        )
    elif primarias < total:
        st.info(
            f"{primarias} de {total} registros son de **fuente primaria** (SEC o banco central). "
            f"El resto son derivados o reconstruidos: heredan el error de sus componentes. "
            "El detalle está en la sección de Fuentes al final de la página."
        )
    else:
        st.success(f"Los {total} registros de esta pantalla son de fuente primaria (SEC).")


def avisar_latencia(fecha_dato: dt.date | None, asof: dt.date, que: str = "precio") -> None:
    if fecha_dato is None:
        st.warning(f"No hay {que} disponible al corte del {asof}.")
        return
    dias = (asof - fecha_dato).days
    if dias <= 1:
        st.caption(f"{que.capitalize()} del {fecha_dato} (cierre). Latencia: {dias} día.")
    else:
        st.warning(
            f"{que.capitalize()} del {fecha_dato}, con **{dias} días de latencia** respecto al "
            f"corte del {asof}. No es un dato en vivo."
        )


def avisos(lista: list[str]) -> None:
    for a in lista or []:
        st.warning(a)


def suficiencia(n_apuestas: int, etiqueta: str = "episodios") -> None:
    """Toda métrica de desempeño va acompañada de su conteo de apuestas efectivas."""
    if n_apuestas >= MIN_APUESTAS_EFECTIVAS:
        st.caption(
            f"Basado en {n_apuestas} {etiqueta} efectivos, arriba del umbral de "
            f"{MIN_APUESTAS_EFECTIVAS}."
        )
    else:
        st.warning(
            f"**INCONCLUSO.** Solo {n_apuestas} {etiqueta} efectivos, debajo del umbral de "
            f"{MIN_APUESTAS_EFECTIVAS}. Cualquier métrica de desempeño calculada sobre esta "
            "muestra es ruido con decimales. El veredicto correcto es INCONCLUSO, no GO."
        )


# --------------------------------------------------------------------------------------
# Glosario progresivo
# --------------------------------------------------------------------------------------

GLOSARIO: dict[str, str] = {
    "NOI": (
        "**NOI (Net Operating Income).** Ingreso por rentas, incluyendo los reembolsos que "
        "paga el inquilino, menos los gastos operativos del inmueble. No incluye corporativo, "
        "ni depreciación, ni intereses. Es lo que produce el ladrillo antes de cómo esté financiado."
    ),
    "FFO": (
        "**FFO (Funds From Operations).** Utilidad neta más la depreciación de inmuebles, menos "
        "las ganancias por venta. La depreciación se suma de vuelta porque un inmueble no se "
        "consume económicamente como lo hace en libros; las ventas se eliminan porque el FFO "
        "mide el negocio de rentar, no el de vender. Es la definición de Nareit."
    ),
    "AFFO": (
        "**AFFO (Adjusted FFO).** El FFO normalizado menos lo que el inmueble efectivamente "
        "consume para seguir produciendo: CapEx recurrente de mantenimiento, comisiones de "
        "arrendamiento, mejoras al inquilino, y el ajuste de renta en línea recta. **Este es el "
        "número que paga el dividendo**, no la utilidad neta ni el FFO."
    ),
    "renta en línea recta": (
        "**Renta en línea recta.** La contabilidad promedia toda la renta del contrato a lo largo "
        "de su vida, así que en los primeros años reconoce ingreso que todavía no se cobra. Es "
        "papel, no efectivo, y por eso se resta para llegar al AFFO."
    ),
    "CapEx de mantenimiento": (
        "**CapEx recurrente de mantenimiento.** Lo que hay que reinvertir para que el inmueble "
        "siga rentando. Es donde más se manipula: reclasificarlo como desarrollo sube el AFFO sin "
        "que nada cambie en el inmueble. Regla de olfato: 10%–20% del NOI en portafolio "
        "estabilizado, bajo en industrial y net lease, alto en oficinas y comercial. En net lease "
        "puro puede ser legítimamente cero porque lo paga el inquilino."
    ),
    "cap rate implícito": (
        "**Cap rate implícito.** NOI anualizado entre el valor de empresa ajustado. El ajuste "
        "consiste en restar los activos que NO generan renta inmobiliaria — cartera de préstamos, "
        "coinversiones — porque si no, el denominador se infla y el cap rate sale sesgado a la baja."
    ),
    "NAV": (
        "**NAV (Net Asset Value).** El valor de los inmuebles capitalizando el NOI al cap rate de "
        "mercado, más efectivo, préstamos y coinversiones, menos deuda total. **Excluye el "
        "goodwill**: no genera renta. El cap rate es la palanca más sensible del modelo, así que "
        "es tuyo y viene con tabla de sensibilidad."
    ),
    "prima": (
        "**Prima.** AFFO yield menos la tasa libre de riesgo del emisor. Es la única forma válida "
        "de comparar valuación entre emisores, pero no como nivel: como **percentil de su propia "
        "historia**. Un REIT de data centers con 2.5% en el percentil 95 de su historia está más "
        "barato que uno de oficinas con 9% en el percentil 20 de la suya."
    ),
    "percentil expandible": (
        "**Percentil expandible.** En cada fecha, el percentil se calcula usando **solo la "
        "historia hasta esa fecha**. Nunca la muestra completa: usarla sería fijar umbrales con "
        "información que en su momento nadie tenía."
    ),
    "spread de inversión": (
        "**Spread de inversión.** Yield de las adquisiciones menos el costo marginal del capital. "
        "Es el motor de valor de un REIT que crece comprando. Negativo significa que cada compra "
        "destruye valor por acción aunque el AFFO agregado suba: se emiten acciones baratas para "
        "comprar activos caros."
    ),
    "dilución oculta": (
        "**Dilución oculta.** En estructuras UPREIT el REIT paga adquisiciones con unidades de la "
        "sociedad operativa, que no aparecen en el conteo de acciones hasta convertirse. Por eso "
        "siempre se usan acciones totalmente diluidas."
    ),
    "TWR y TIR": (
        "**TWR** (ponderado por tiempo) quita el efecto del *timing* de tus aportaciones: mide la "
        "selección de activos. **TIR** (ponderado por dinero) lo incluye: mide tu resultado real. "
        "Si el TWR es mayor que la TIR, aportaste más antes de los periodos malos."
    ),
    "Udibono": (
        "**Udibono.** Bono del gobierno mexicano indizado a la inflación: paga una tasa **real** "
        "fija garantizada. Es el benchmark honesto de un inversionista mexicano, no el S&P ni el "
        "índice Nareit. Cualquier REIT tiene que superarlo después de impuestos para justificar "
        "su riesgo de mercado, divisa y emisor."
    ),
    "apuestas efectivas": (
        "**Apuestas efectivas.** Cuántas decisiones independientes hay realmente detrás de una "
        "métrica. Una señal de valuación lenta produce 10 a 20 episodios de posición en veinte "
        "años, no 240 observaciones mensuales. Debajo de ~100 apuestas efectivas, el veredicto es "
        "INCONCLUSO."
    ),
}


def explicar(*conceptos: str, expandido: bool = False) -> None:
    """Explica conceptos la primera vez que aparecen, de lo simple a lo complejo."""
    faltantes = [c for c in conceptos if c in GLOSARIO]
    if not faltantes:
        return
    with st.expander("¿Qué significa cada término de esta pantalla?", expanded=expandido):
        for c in faltantes:
            st.markdown(GLOSARIO[c])


# --------------------------------------------------------------------------------------
# Formato
# --------------------------------------------------------------------------------------


def pct(v, decimales: int = 2) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:.{decimales}%}"


def bps(v) -> str:
    """Formatea una cantidad decimal como puntos base. El decimal se escala aquí, no en el formato."""
    return "—" if v is None or pd.isna(v) else f"{v * 10_000:,.0f} bps"


def dinero(v, moneda: str = "USD", decimales: int = 2) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.{decimales}f} {moneda}"


def veces(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:,.2f}x"


def semaforo_html(luz: str, texto: str) -> str:
    color = COLOR_LUZ.get(luz, "#57606a")
    return (
        f"<div style='border-left:4px solid {color};padding:0.4rem 0.8rem;margin:0.3rem 0;'>"
        f"<strong style='color:{color}'>{ICONO_LUZ.get(luz, '⚪')} {luz}</strong><br>{texto}</div>"
    )


def tabla_metricas(metricas: dict, formato: dict[str, str] | None = None) -> pd.DataFrame:
    """Convierte un dict de métricas en tabla formateada para mostrar."""
    formato = formato or {}
    filas = []
    for k, v in metricas.items():
        f = formato.get(k, "num")
        if v is None or (isinstance(v, float) and pd.isna(v)):
            texto = "—"
        elif f == "pct":
            texto = pct(v)
        elif f == "bps":
            texto = bps(v)
        elif f == "veces":
            texto = veces(v)
        elif f == "dinero":
            texto = dinero(v)
        else:
            texto = f"{v:,.2f}" if isinstance(v, int | float) else str(v)
        filas.append({"Métrica": k.replace("_", " ").capitalize(), "Valor": texto})
    return pd.DataFrame(filas)
