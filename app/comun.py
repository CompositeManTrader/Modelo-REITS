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
import inspect
import os
import re
import sys
import unicodedata
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


def _publicar_secretos() -> None:
    """Copia los secretos de Streamlit al entorno, que es donde los leen los ingestores.

    Los módulos de ingesta se usan también desde la línea de comandos y desde la
    GitHub Action, así que leen variables de entorno y no conocen a Streamlit. Aquí
    se tiende el puente, sin que ninguna credencial toque el repositorio.
    """
    for clave in ("BANXICO_TOKEN", "SEC_USER_AGENT"):
        if os.environ.get(clave):
            continue
        try:
            valor = st.secrets[clave]
        except Exception:
            continue
        if valor:
            os.environ[clave] = str(valor)


@st.cache_resource(show_spinner=False)
def _sembrar_una_sola_vez(marca: str) -> dict:
    """Corre la ingesta real la primera vez y una sola vez por proceso.

    ``cache_resource`` da exactamente lo que hace falta: si dos personas abren la
    aplicación recién desplegada al mismo tiempo, Streamlit serializa la llamada y
    la segunda recibe el resultado de la primera en vez de lanzar una segunda
    descarga contra la SEC. ``marca`` invalida el caché cuando cambia la ruta.
    """
    from src.config import asegurar_directorios
    from src.ingesta import tasas as mod_tasas
    from src.ingesta.orquestador import correr_ingesta
    from src.ingesta.tasas import ErrorTasas

    _publicar_secretos()
    asegurar_directorios()
    repo = Repositorio(ruta=RUTA_BD)
    reporte: dict = {"tasas": {}, "emisores": [], "errores": []}

    barra = st.progress(0.0, text="Descargando tasas y macro…")
    series = list(mod_tasas.SERIES_FRED) + list(mod_tasas.SERIES_BANXICO)
    for i, serie in enumerate(series):
        barra.progress(i / (len(series) + 10), text=f"Tasas: {serie}")
        try:
            if serie in mod_tasas.SERIES_FRED:
                filas = mod_tasas.ingestar_fred(serie)
            else:
                filas = mod_tasas.ingestar_banxico(serie)
            reporte["tasas"][serie] = repo.guardar_tasas(filas)
        except (ErrorTasas, Exception) as exc:  # noqa: BLE001 - se reporta, no se traga
            reporte["errores"].append(f"{serie}: {exc}")

    def avanzar(ticker: str, indice: int, total: int) -> None:
        barra.progress(
            (len(series) + indice) / (len(series) + total),
            text=f"SEC EDGAR y mercado: {ticker} ({indice + 1} de {total})",
        )

    resumenes = correr_ingesta(repo, al_avanzar=avanzar)
    for r in resumenes:
        reporte["emisores"].append(r.como_texto())
        reporte["errores"].extend(r.errores)
    barra.progress(1.0, text="Listo.")
    barra.empty()
    return reporte


def exigir_base() -> Repositorio:
    """Devuelve el repositorio; si no existe, lo construye desde fuente primaria.

    En una computadora personal la base se crea con un comando. En Streamlit Cloud
    no hay terminal, y el sistema de archivos es efímero: cada reinicio del
    contenedor borra la base. Por eso la primera carga ingesta sola, en vez de
    mostrar un comando que ahí nadie puede correr.
    """
    if not base_existe():
        st.info(
            "**Primera carga.** No hay base de datos, así que la estoy construyendo desde "
            "la fuente primaria: SEC EDGAR para los fundamentales, FRED y Banxico para las "
            "tasas, y el mercado para precios sin ajustar. Tarda varios minutos y solo pasa "
            "una vez por arranque del servidor.",
            icon="⏳",
        )
        try:
            reporte = _sembrar_una_sola_vez(str(RUTA_BD))
        except Exception as exc:  # noqa: BLE001 - la pantalla debe decir qué pasó
            st.error(
                f"La ingesta falló y no hay datos que mostrar: `{exc}`\n\n"
                "En una computadora personal esto se resuelve corriendo "
                "`python scripts/ingesta.py` y revisando el detalle del error."
            )
            st.stop()
        if reporte["errores"]:
            st.warning(
                f"La ingesta terminó con {len(reporte['errores'])} advertencia(s). "
                "Lo que no se pudo verificar quedó marcado y no entra a ningún cálculo.",
                icon="⚠️",
            )
            with st.expander("Ver el detalle de la ingesta"):
                for linea in reporte["emisores"]:
                    st.text(linea)
                st.markdown("**Advertencias**")
                for linea in reporte["errores"]:
                    st.text(linea)
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
# Coerción numérica
# --------------------------------------------------------------------------------------


def numero(valor, defecto: float | None = None) -> float | None:
    """Convierte a float lo que venga de un DataFrame, o devuelve ``defecto``.

    Existe porque ``float(fila.get("noi") or 0.0)`` es una trampa: cuando la celda
    trae ``pd.NA`` —que es lo normal en una columna que quedó sin datos— evaluar su
    valor de verdad lanza «boolean value of NA is ambiguous» y tumba la página. Y
    el ``or`` además convierte un cero legítimo en el valor por omisión, que es un
    error distinto y más silencioso.

    ``defecto`` se devuelve tal cual, incluido ``None``: la diferencia entre «no
    hay dato» y «el dato es cero» importa en todo este sistema.
    """
    if valor is None:
        return defecto
    try:
        if pd.isna(valor):
            return defecto
    except (TypeError, ValueError):
        pass
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def positivo(valor, defecto: float | None = None) -> float | None:
    """Como ``numero``, pero un cero también cuenta como ausencia.

    Para magnitudes donde el cero no es un valor plausible sino la huella de un
    dato faltante: un NOI de cero o un número de acciones de cero no existen.
    """
    v = numero(valor, None)
    return defecto if v is None or v == 0 else v


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


# --------------------------------------------------------------------------------------
# Formato automático de tablas
# --------------------------------------------------------------------------------------
#
# Sin esto, una tabla dibuja 435000000.0 y el lector tiene que contar ceros con el
# dedo. La FAMILIA de unidad de cada columna se deduce de su nombre, y de ahí salen
# dos cosas distintas que conviene no confundir:
#
#   * la ESCALA, que se aplica al dato, y
#   * el FORMATO, que solo decide cómo se dibuja.
#
# El formato "%.2f%%" de Streamlit **solo pega el símbolo de porcentaje: no
# multiplica por cien**. Un AFFO yield de 0.0553 se dibuja como "0.06%": se ve
# plausible y está mal por dos órdenes de magnitud. Es el mismo error que en las
# celdas en puntos base del Excel.
#
# Por eso la escala la decide la familia y se aplica SIEMPRE, aunque quien llama
# traiga su propia `column_config`. La primera versión dejaba que lo explícito se
# llevara también la escala, y el resultado fue justo el error que quería evitar:
# en la portada, la tabla del Nareit dibujaba 11.78% como "0.12%" y el percentil de
# prima dibujaba 13% como "0%", porque ambas pasaban configuración propia. La regla
# ahora es una sola y no tiene excepciones: **ninguna página escala a mano**; lo
# explícito manda sobre la etiqueta y el formato, nunca sobre las unidades.

_COLUMNAS_PORCENTAJE = (
    "yield", "payout", "percentil", "premio", "descuento", "crecimiento", "tasa",
    "rendimiento", "ocupacion", "cap_rate", "rate", "prima", "inflacion", "ltv",
    "peso", "fraccion", "spread", "dilucion", "error", "diferencia_relativa",
    "pct", "caida", "tir", "plusvalia", "brecha", "probabilidad", "cagr",
)
_COLUMNAS_BPS = ("bps",)
_COLUMNAS_MONEDA = (
    "precio", "nav", "monto", "valor", "usd", "mxn", "dividendo", "costo", "flujo",
    "saldo", "capital", "interes", "renta", "aportacion", "retiro", "neto", "isr",
    "impuesto", "perdida", "ingreso", "utilidad", "ffo", "affo", "noi", "deuda",
)
_COLUMNAS_POR_ACCION = ("por_accion", "per_share")
_COLUMNAS_VECES = ("p_affo", "veces", "multiplo", "ebitdare", "cobertura", "razon")

_NO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")


def _canonizar_columna(columna) -> str:
    """`"Tasa efectiva (%)"` y `tasa_efectiva` son la misma columna. Con guiones al borde.

    Los guiones bajos de los extremos permiten buscar la aguja como token completo:
    así ``tir`` casa con ``tir_real`` pero no con ``retiro``.
    """
    texto = unicodedata.normalize("NFKD", str(columna).lower())
    texto = texto.encode("ascii", "ignore").decode("ascii")
    return "_" + _NO_ALFANUMERICO.sub("_", texto).strip("_") + "_"


def _es(columna, agujas: tuple[str, ...]) -> bool:
    canon = _canonizar_columna(columna)
    return any(f"_{aguja}_" in canon for aguja in agujas)


def familia_de_columna(columna, serie: pd.Series | None = None) -> str:
    """Unidad a la que pertenece la columna. Es lo que decide escala y formato."""
    if _es(columna, _COLUMNAS_BPS):
        # Por convención de este proyecto, una columna `*_bps` YA viene en puntos
        # base: la escala se hace en `servicio.py`, donde nace el dato. Escalarla
        # otra vez aquí la multiplicaría por diez mil.
        return "bps"
    if _es(columna, _COLUMNAS_PORCENTAJE):
        return "porcentaje"
    if _es(columna, _COLUMNAS_POR_ACCION):
        return "por_accion"
    if _es(columna, _COLUMNAS_VECES):
        return "veces"
    if _es(columna, _COLUMNAS_MONEDA):
        return "moneda"
    if serie is not None and pd.api.types.is_integer_dtype(serie):
        return "entero"
    return "numero"


def _config_de_familia(familia: str, columna, serie: pd.Series) -> object:
    etiqueta = str(columna).replace("_", " ").strip().capitalize()
    if familia == "bps":
        return st.column_config.NumberColumn(etiqueta, format="%,.0f bps")
    if familia == "porcentaje":
        return st.column_config.NumberColumn(etiqueta, format="%.2f%%")
    if familia == "por_accion":
        return st.column_config.NumberColumn(etiqueta, format="$%.2f")
    if familia == "veces":
        return st.column_config.NumberColumn(etiqueta, format="%.2fx")
    if familia == "moneda":
        return st.column_config.NumberColumn(etiqueta, format="$%,.2f")
    if familia == "entero":
        return st.column_config.NumberColumn(etiqueta, format="%,d")
    # Los montos grandes se leen sin decimales; los chicos los necesitan.
    magnitud = serie.abs().max()
    formato = "%,.0f" if pd.notna(magnitud) and magnitud >= 1_000 else "%,.2f"
    return st.column_config.NumberColumn(etiqueta, format=formato)


def formato_columnas(df: pd.DataFrame, explicito: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Escala cada columna numérica a su unidad y deduce cómo dibujarla.

    Devuelve ``(datos_para_dibujar, column_config)``.

    La **escala** la decide la familia de la columna y se aplica siempre. Lo
    explícito que pase quien llama gana sobre la etiqueta y el formato —que es
    presentación— pero nunca sobre las unidades, que son el dato.
    """
    explicito = dict(explicito or {})
    vista = df.copy()
    config: dict = {}

    for columna in vista.columns:
        serie = vista[columna]
        if not pd.api.types.is_numeric_dtype(serie) or pd.api.types.is_bool_dtype(serie):
            continue
        familia = familia_de_columna(columna, serie)
        if familia == "porcentaje":
            # La escala va en el dato. El formato solo pega el símbolo.
            vista[columna] = serie * 100.0
        if columna not in explicito:
            config[columna] = _config_de_familia(familia, columna, vista[columna])

    config.update(explicito)
    return vista, config


# Streamlit dibuja las celdas vacías con la palabra "None" salvo en las columnas de
# progreso. En una tabla de diez emisores donde siete no tienen historia suficiente,
# eso llena la pantalla de "None" en inglés y hace ver la tabla como si estuviera
# rota. `placeholder` existe desde Streamlit 1.51; en versiones anteriores el
# argumento no existe y pasarlo revienta, así que se consulta la firma.
_ACEPTA_PLACEHOLDER = "placeholder" in inspect.signature(st.dataframe).parameters


def mostrar_tabla(df: pd.DataFrame, *, column_config: dict | None = None, **kwargs):
    """``st.dataframe`` con separadores de miles, unidades y huecos por omisión."""
    vista, config = formato_columnas(df, column_config)
    kwargs.setdefault("hide_index", True)
    kwargs.setdefault("width", "stretch")
    if _ACEPTA_PLACEHOLDER:
        kwargs.setdefault("placeholder", "—")
    return st.dataframe(vista, column_config=config, **kwargs)


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
