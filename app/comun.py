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
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Los tokens visuales viven en `marca.py`, que es la fuente única. Aquí solo se
# reexportan para que las páginas sigan importándolos de un lugar.
from marca import (  # noqa: E402
    AMBAR,
    BLANCO,
    COLOR_LUZ,
    GLIFO_LUZ,
    GRIS,
    GRIS_TENUE,
    LINEA,
    MONO,
    RADIO_PILDORA,
    RADIO_TARJETA,
    SUPERFICIE,
    SUPERFICIE_2,
    TEXTO,
)
from src.config import DESCARGO, MIN_APUESTAS_EFECTIVAS, RUTA_BD, Fuente  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402

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


@st.cache_resource(show_spinner="Reconstruyendo la base desde el repositorio…")
def _reconstruir_una_sola_vez(marca: str) -> dict:
    """Carga la instantánea versionada. Sin red, y una sola vez por proceso.

    Va ANTES que la ingesta y no en su lugar: el repositorio guarda los
    fundamentales, no los precios ni las tasas, que sí hay que ir a buscar. Lo
    que ahorra es la parte cara —diez `companyfacts` y ochocientos documentos
    8-K— y de paso hace que dos arranques del mismo commit den la misma base.

    Si el almacén está vacío se devuelve así y la ingesta completa toma su lugar:
    esto acelera el camino normal, no lo reemplaza.
    """
    from src.config import asegurar_directorios
    from src.ingesta.instantanea import reconstruir

    _publicar_secretos()
    asegurar_directorios()
    try:
        resumen = reconstruir(Repositorio(ruta=RUTA_BD))
    except Exception as exc:  # noqa: BLE001 - un almacén roto no puede tumbar la app
        return {"vacia": True, "hechos": 0, "emisoras": 0, "error": str(exc)}
    return {
        "vacia": resumen.vacia,
        "hechos": resumen.hechos,
        "emisoras": len(resumen.emisoras),
        "error": "",
    }


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
        # Primero el repositorio, y solo después la red. El almacén versionado
        # trae los fundamentales de las diez emisoras en unos pocos MB; bajarlos
        # otra vez de la SEC son 810 peticiones y 128 MB, y aquí el disco es
        # efímero, así que eso pasaba en CADA reinicio del contenedor.
        instantanea = _reconstruir_una_sola_vez(str(RUTA_BD))
        if not instantanea["vacia"]:
            st.success(
                f"**Base reconstruida desde el repositorio**, sin descargar nada: "
                f"{instantanea['hechos']:,} hechos de {instantanea['emisoras']} emisoras. "
                "Los precios y las tasas sí se actualizan contra su fuente.",
                icon="📦",
            )
        st.info(
            "**Primera carga.** Completando lo que el repositorio no guarda: FRED y Banxico "
            "para las tasas, y el mercado para precios sin ajustar."
            if not instantanea["vacia"] else
            "**Primera carga.** No hay base de datos ni instantánea, así que la estoy "
            "construyendo desde la fuente primaria: SEC EDGAR para los fundamentales, FRED y "
            "Banxico para las tasas, y el mercado para precios sin ajustar. Tarda varios "
            "minutos y solo pasa una vez por arranque del servidor.",
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
    """Los emisores como fichas visibles, en el cuerpo y no en la barra lateral.

    Antes era un desplegable en la barra lateral, debajo del selector de fecha y
    de dos deslizadores. Eso tiene dos problemas y el segundo es serio: en
    pantalla angosta Streamlit arranca con la barra lateral **plegada**, así que
    el único control para cambiar de emisora quedaba fuera de la vista, y la
    pantalla parecía servir un solo nombre.

    Con fichas los diez emisores están a la vista y a un clic. Es una lista corta
    y cerrada —el universo del modelo—, que es exactamente el caso para el que
    sirven las fichas y no un desplegable.
    """
    emisores = repo.emisores()
    if emisores.empty:
        st.warning("No hay emisores en la base.")
        return None
    opciones = list(emisores.sort_values("ticker")["ticker"])
    previo = st.session_state.get(clave)
    elegido = st.pills(
        "Emisor",
        opciones,
        default=previo if previo in opciones else opciones[0],
        key=f"{clave}_fichas",
        label_visibility="collapsed",
        help="Cada ficha recarga la pantalla completa con los datos de esa emisora.",
    )
    # `st.pills` admite deselección: al volver a pulsar la ficha activa devuelve
    # `None`, y sin esta guarda la pantalla se quedaría sin emisora y se
    # detendría. Se conserva la última elegida.
    if elegido is None:
        elegido = previo if previo in opciones else opciones[0]
    st.session_state[clave] = elegido
    return elegido


def cobertura_de_emisores(repo, *, asof) -> pd.DataFrame:
    """Cuántos trimestres de fundamentales tiene cada emisor al corte.

    Sirve para que la pantalla pueda decir, ANTES de que alguien haga clic, cuál
    emisora tiene datos y cuál no. Sin esto, elegir una emisora sin fundamentales
    lleva a una pantalla en blanco con un renglón rojo, que es indistinguible de
    una aplicación descompuesta.
    """
    emisores = repo.emisores()
    if emisores.empty:
        return pd.DataFrame(columns=["ticker", "nombre", "sector", "trimestres"])
    filas = []
    for _, e in emisores.sort_values("ticker").iterrows():
        hechos = repo.hechos(asof=asof, tickers=e["ticker"], periodo_tipo="Q")
        n = 0 if hechos.empty else int(pd.to_datetime(hechos["fecha_dato"]).nunique())
        filas.append(
            {"ticker": e["ticker"], "nombre": e["nombre"], "sector": e["sector"], "trimestres": n}
        )
    return pd.DataFrame(filas)


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


# Cuántos días HÁBILES puede tener un precio y seguir siendo "el último cierre".
# Uno cubre la operación normal —hoy contra el cierre de ayer— y dos absorben un
# feriado de mercado, que es la causa más común de un rezago que no es rezago.
TOLERANCIA_LATENCIA = 2


def dias_habiles(desde: dt.date, hasta: dt.date) -> int:
    """Días de lunes a viernes entre dos fechas, sin contar el inicial.

    La latencia se medía en días NATURALES y por eso gritaba todos los lunes: el
    viernes es el último cierre y el lunes son tres días de calendario. El 8 de
    septiembre de 2026 —martes, con el lunes 7 feriado— la pantalla decía
    "latencia 4 días" sobre un precio que era el más reciente que existía.

    Un aviso que se dispara solo entrena a ignorarlo, y ese es justo el aviso que
    tiene que funcionar el día que el dato sí esté viejo.

    No conoce el calendario de feriados de la bolsa —no lo tenemos— así que un
    feriado sigue contando como un día hábil. Por eso la tolerancia es de dos y no
    de uno: absorbe ese caso sin dejar de marcar un rezago de verdad.
    """
    if hasta <= desde:
        return 0
    return int(pd.bdate_range(desde + dt.timedelta(days=1), hasta).size)


def avisar_latencia(fecha_dato: dt.date | None, asof: dt.date, que: str = "precio") -> None:
    if fecha_dato is None:
        st.warning(f"No hay {que} disponible al corte del {asof}.")
        return
    habiles = dias_habiles(fecha_dato, asof)
    if habiles <= TOLERANCIA_LATENCIA:
        st.caption(
            f"{que.capitalize()} del {fecha_dato} (cierre). "
            f"Latencia: {habiles} día{'s' if habiles != 1 else ''} hábil"
            f"{'es' if habiles != 1 else ''}."
        )
    else:
        st.warning(
            f"{que.capitalize()} del {fecha_dato}, con **{habiles} días hábiles de latencia** "
            f"respecto al corte del {asof}. No es un dato en vivo."
        )


def avisos(lista: list[str]) -> None:
    for a in lista or []:
        st.warning(a)


def suficiencia(n_apuestas: int, etiqueta: str = "episodios") -> None:
    """Toda métrica de desempeño va acompañada de su conteo de apuestas efectivas."""
    # El adjetivo concuerda con el sustantivo que le pasen. Fijarlo en masculino
    # producía "139 transacciones efectivos" en la pantalla de portafolio.
    femenino = etiqueta.endswith(("a", "as", "cion", "ciones", "sion", "siones", "dad", "dades"))
    efectivos = "efectivas" if femenino else "efectivos"
    if n_apuestas >= MIN_APUESTAS_EFECTIVAS:
        st.caption(
            f"Basado en {n_apuestas} {etiqueta} {efectivos}, arriba del umbral de "
            f"{MIN_APUESTAS_EFECTIVAS}."
        )
    else:
        st.warning(
            f"**INCONCLUSO.** Solo {n_apuestas} {etiqueta} {efectivos}, debajo del umbral de "
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
    # La atribución del retorno reparte el resultado en componentes que son
    # fracciones. Sin declararlo, la columna caía en "número" y no se escalaba,
    # y la pantalla dibujaba 0.08% donde el emisor creció 7.6%.
    "aporte",
)
_COLUMNAS_BPS = ("bps",)
_COLUMNAS_MONEDA = (
    "precio", "nav", "monto", "valor", "usd", "mxn", "dividendo", "dividendos",
    "costo", "flujo", "saldo", "capital", "interes", "renta", "aportacion",
    "retiro", "neto", "isr", "impuesto", "perdida", "ingreso", "utilidad",
    # "ganancia" faltaba, así que en la tabla de posiciones convivían un costo
    # total de "$24,000.00" y una ganancia de "1,417": la misma unidad con dos
    # formatos, en columnas contiguas. El plural de dividendo tampoco casaba,
    # porque la búsqueda es por token completo y no por subcadena.
    "ganancia", "ffo", "affo", "noi", "deuda",
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


# Un encabezado se escribe como se escribe en español. La clave de la columna va
# sin acentos porque es un identificador, pero lo que se dibuja no es la clave: en
# la tabla de atribución convivían un "Aporte" bien puesto y un "explicacion" crudo.
# La regla cubre la familia que causa casi todos los casos —toda palabra terminada
# en `-cion` o `-sion` lleva acento en singular— y el resto va declarado.
_RE_TERMINACION_ACENTUADA = re.compile(r"\b(\w+)(cion|sion)\b")
# Palabras de encabezado que llevan acento y no terminan en -ción/-sión, así que
# ninguna regla las alcanza. Es una lista corta porque son las que de verdad se
# dibujan en esta aplicación, no un diccionario del español.
_PALABRAS_ACENTUADAS = {
    "razon": "razón", "indice": "índice", "implicito": "implícito",
    "implicita": "implícita", "teorico": "teórico", "teorica": "teórica",
    "maximo": "máximo", "maxima": "máxima", "minimo": "mínimo", "minima": "mínima",
    "ultimo": "último", "ultima": "última", "unico": "único", "unica": "única",
    "numero": "número", "metrica": "métrica", "interes": "interés",
    "historico": "histórico", "historica": "histórica", "proximo": "próximo",
}
# Las que ninguna regla acierta: una sigla que no se capitaliza como palabra, un
# prefijo técnico que no se lee, y el sufijo con el que este proyecto marca los
# porcentajes.
_ETIQUETAS_EXPLICITAS = {
    "retencion_eeuu": "Retención EE. UU.",
    "n_observaciones": "Observaciones",
    "ganancia_no_realizada_pct": "Ganancia no realizada %",
    "p_affo": "P/AFFO",
    "p_ffo": "P/FFO",
}
# Una sigla no es una palabra y no se capitaliza como tal. En una herramienta donde
# AFFO es un término definido, un encabezado que dice "Affo yield" o "Payout affo"
# se lee como si el término no importara. `.capitalize()` las arruinaba todas. El
# valor es la forma dibujada y no siempre son mayúsculas: el plural de una sigla se
# escribe con minúscula ("REITs", no "REITS"), y "bps" va en minúscula por
# convención —"409 bps"— así que deliberadamente no está en esta tabla.
_SIGLAS = {
    "affo": "AFFO", "ffo": "FFO", "noi": "NOI", "nav": "NAV", "ltv": "LTV",
    "tir": "TIR", "twr": "TWR", "walt": "WALT", "ebitda": "EBITDA",
    "ebitdare": "EBITDAre", "isr": "ISR", "inpc": "INPC", "cpi": "CPI",
    "ust": "UST", "reit": "REIT", "reits": "REITs", "ipc": "IPC",
    "capex": "CapEx", "sic": "SIC", "usd": "USD", "mxn": "MXN", "udi": "UDI",
    "udis": "UDIs", "eeuu": "EE. UU.", "iva": "IVA", "irr": "IRR", "pib": "PIB",
}


def etiqueta_de_columna(columna) -> str:
    """Cómo se dibuja el nombre de una columna en un encabezado."""
    clave = str(columna).strip().lower()
    if clave in _ETIQUETAS_EXPLICITAS:
        return _ETIQUETAS_EXPLICITAS[clave]
    texto = clave.replace("_", " ")
    texto = " ".join(_PALABRAS_ACENTUADAS.get(p, p) for p in texto.split())
    texto = _RE_TERMINACION_ACENTUADA.sub(
        lambda m: m.group(1) + ("ción" if m.group(2) == "cion" else "sión"), texto
    )
    # Se capitaliza primero la frase y luego se restituyen las siglas, para que
    # "affo yield" quede "AFFO yield" y no "Affo yield" ni "AFFO Yield".
    palabras = texto.capitalize().split()
    return " ".join(_SIGLAS.get(p.lower(), p) for p in palabras)


def _config_de_familia(
    familia: str, columna, serie: pd.Series, *, fija: bool = False
) -> object:
    etiqueta = etiqueta_de_columna(columna)
    formatos = {
        "bps": "%,.0f bps",
        "porcentaje": "%.2f%%",
        "por_accion": "$%.2f",
        "veces": "%.2fx",
        "moneda": "$%,.2f",
        "entero": "%,d",
    }
    formato = formatos.get(familia)
    if formato is None:
        # Los montos grandes se leen sin decimales; los chicos los necesitan.
        magnitud = serie.abs().max()
        formato = "%,.0f" if pd.notna(magnitud) and magnitud >= 1_000 else "%,.2f"
    return st.column_config.NumberColumn(etiqueta, format=formato, pinned=fija)


def formato_columnas(
    df: pd.DataFrame, explicito: dict | None = None, *, fijar: Sequence[str] = ()
) -> tuple[pd.DataFrame, dict]:
    """Escala cada columna numérica a su unidad y deduce cómo dibujarla.

    Devuelve ``(datos_para_dibujar, column_config)``.

    La **escala** la decide la familia de la columna y se aplica siempre. Lo
    explícito que pase quien llama gana sobre la etiqueta y el formato —que es
    presentación— pero nunca sobre las unidades, que son el dato.

    ``fijar`` ancla esas columnas a la izquierda: se quedan quietas mientras el
    resto de la tabla se desplaza. Un estado financiero de setenta trimestres se
    desplaza de lado sí o sí, y sin el renglón a la vista lo que queda es una
    parrilla de números sin sujeto.
    """
    explicito = dict(explicito or {})
    fijar = set(fijar)
    vista = df.copy()
    config: dict = {}

    for columna in vista.columns:
        serie = vista[columna]
        if not pd.api.types.is_numeric_dtype(serie) or pd.api.types.is_bool_dtype(serie):
            # Una columna de texto no tiene unidad ni formato, pero sí encabezado:
            # sin esto se dibujaba con la clave cruda, y una misma tabla mezclaba
            # "Aporte" con "explicacion".
            if columna not in explicito:
                config[columna] = st.column_config.Column(
                    etiqueta_de_columna(columna), pinned=columna in fijar
                )
            continue
        familia = familia_de_columna(columna, serie)
        if familia == "porcentaje":
            # La escala va en el dato. El formato solo pega el símbolo.
            vista[columna] = serie * 100.0
        if columna not in explicito:
            config[columna] = _config_de_familia(
                familia, columna, vista[columna], fija=columna in fijar
            )

    config.update(explicito)
    return vista, config


# Streamlit dibuja las celdas vacías con la palabra "None" salvo en las columnas de
# progreso. En una tabla de diez emisores donde siete no tienen historia suficiente,
# eso llena la pantalla de "None" en inglés y hace ver la tabla como si estuviera
# rota. `placeholder` existe desde Streamlit 1.51; en versiones anteriores el
# argumento no existe y pasarlo revienta, así que se consulta la firma.
_ACEPTA_PLACEHOLDER = "placeholder" in inspect.signature(st.dataframe).parameters


def mostrar_tabla(
    df: pd.DataFrame,
    *,
    column_config: dict | None = None,
    fijar_primera: bool = False,
    **kwargs,
):
    """``st.dataframe`` con separadores de miles, unidades y huecos por omisión.

    ``fijar_primera`` ancla la primera columna —la del concepto— para que no se
    vaya con el desplazamiento horizontal. Es lo que hace legible un estado de
    setenta trimestres: sin ella, en cuanto se avanza tres columnas los números
    dejan de tener renglón y hay que volver al inicio para saber qué se está
    leyendo.
    """
    fijar = [df.columns[0]] if fijar_primera and len(df.columns) else []
    vista, config = formato_columnas(df, column_config, fijar=fijar)
    kwargs.setdefault("hide_index", True)
    kwargs.setdefault("width", "stretch")
    if _ACEPTA_PLACEHOLDER:
        kwargs.setdefault("placeholder", "—")
    return st.dataframe(vista, column_config=config, **kwargs)


def _formato_de_valor(valor: float | None, unidad: str) -> str:
    """El valor en la unidad de su métrica, o el guion largo si no hay."""
    if valor is None or pd.isna(valor):
        return "—"
    if unidad == "pct":
        return f"{valor * 100:,.1f}%"
    if unidad == "veces":
        return f"{valor:,.2f}x"
    return f"{valor / 1e6:,.1f} M"


def _formato_de_cambio(cambio: float | None, etiqueta: str) -> tuple[str, str]:
    """El cambio con su glifo de dirección. Devuelve ``(glifo, texto)``.

    El glifo va SIEMPRE y el color NUNCA: en la mitad de estas métricas subir es
    malo —el apalancamiento, el costo de la deuda, el payout— así que pintar de
    verde toda subida diría lo contrario de lo que pasa. La guía de marca reserva
    el verde y el rojo para ganancia y pérdida, y una dirección no es ninguna de
    las dos.
    """
    if cambio is None or pd.isna(cambio):
        return "·", "sin comparable"
    glifo = "▲" if cambio > 0 else ("▼" if cambio < 0 else "·")
    if etiqueta == "bps":
        return glifo, f"{cambio:+,.0f} bps"
    if etiqueta == "x":
        return glifo, f"{cambio:+,.2f}x"
    return glifo, f"{cambio:+,.1f}%"


def panel_de_metrica(
    serie: pd.Series, metrica, *, pasos_al_ano: int = 4, dominio=None
) -> None:
    """Una métrica como valor, cambio y serie: la forma de «cuánto y hacia dónde».

    Es un *stat tile*, no una gráfica suelta: el número manda y la línea es el
    contexto. Una serie por panel y un solo eje —nunca dos escalas en la misma
    caja— porque la comparación que importa es la de la métrica consigo misma a
    lo largo del tiempo, no la de dos métricas entre sí.

    El ámbar es el único acento de la marca, así que la línea va en ámbar y todo
    lo demás en tinta: no hay una paleta categórica que repartir porque no hay
    categorías que distinguir.

    ``dominio`` fija el mismo eje de tiempo en todos los paneles. No es cosmético:
    con cada panel en su propio rango, el NOI —que empieza en 2019— y el ingreso
    —que empieza en 2010— dibujan la misma rampa con el mismo ancho, y se leen
    como si hubieran crecido igual. Comparar paneles exige el mismo eje.
    """
    import plotly.graph_objects as go

    from src.servicio import cambio_de_metrica as _cambio

    limpia = serie.dropna()
    valor, cambio_periodo, unidad_cambio = _cambio(serie, metrica.unidad, pasos=1)
    _, cambio_ano, _ = _cambio(serie, metrica.unidad, pasos=pasos_al_ano)
    glifo_p, texto_p = _formato_de_cambio(cambio_periodo, unidad_cambio)
    glifo_a, texto_a = _formato_de_cambio(cambio_ano, unidad_cambio)

    st.markdown(
        f"<div style='font:600 11px {TEXTO};color:{GRIS};letter-spacing:.04em;"
        f"text-transform:uppercase'>{metrica.etiqueta}</div>"
        f"<div style='font:700 26px {MONO};color:{BLANCO};line-height:1.25'>"
        f"{_formato_de_valor(valor, metrica.unidad)}</div>"
        f"<div style='font:500 11px {MONO};color:{GRIS}'>"
        f"{glifo_p} {texto_p} <span style='color:{GRIS_TENUE}'>· periodo</span>"
        f" &nbsp; {glifo_a} {texto_a} <span style='color:{GRIS_TENUE}'>· año</span></div>",
        unsafe_allow_html=True,
    )
    if limpia.empty:
        st.caption("Sin serie para dibujar.")
        return

    escala = 100.0 if metrica.unidad == "pct" else (1 / 1e6 if metrica.unidad == "monto" else 1.0)
    sufijo = {"pct": "%", "veces": "x", "monto": " M"}[metrica.unidad]
    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            x=list(limpia.index), y=[v * escala for v in limpia],
            mode="lines", line={"color": AMBAR, "width": 2},
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.2f}" + sufijo + "<extra></extra>",
            showlegend=False,
        )
    )
    # El último punto marcado: es el que dice el número grande de arriba, y sin
    # él la línea termina en el aire y no se sabe cuál de los picos es "hoy".
    figura.add_trace(
        go.Scatter(
            x=[limpia.index[-1]], y=[float(limpia.iloc[-1]) * escala],
            mode="markers", marker={"color": AMBAR, "size": 8},
            hoverinfo="skip", showlegend=False,
        )
    )
    if float(limpia.min()) < 0 < float(limpia.max()):
        # El cero solo se dibuja cuando la serie lo cruza: en un margen que pasa
        # a negativo, esa línea es el dato.
        figura.add_hline(y=0, line={"color": GRIS_TENUE, "width": 1})
    figura.update_layout(
        height=130, margin={"t": 4, "b": 4, "l": 0, "r": 4},
        hovermode="x unified", showlegend=False,
    )
    figura.update_xaxes(showgrid=False, tickfont={"size": 9}, range=dominio)
    figura.update_yaxes(showgrid=True, nticks=3, tickfont={"size": 9})
    st.plotly_chart(figura, config={"displayModeBar": False})
    st.caption(metrica.explicacion)


def semaforo_html(luz: str, texto: str) -> str:
    """La luz con su glifo. El glifo no es adorno: es la regla daltónica de la guía.

    Ganancia y pérdida nunca se distinguen solo por color, así que la luz viaja
    siempre con ``▲``/``◆``/``▼``/``·``. Antes eran emojis de colores, que la guía
    de marca prohíbe.
    """
    color = COLOR_LUZ.get(luz, GRIS)
    return (
        f"<div style='border-left:3px solid {color};background:{SUPERFICIE};"
        f"padding:0.5rem 0.9rem;margin:0.3rem 0;border-radius:{RADIO_PILDORA}'>"
        f"<strong style='color:{color};font-family:{MONO}'>"
        f"{GLIFO_LUZ.get(luz, '·')} {luz}</strong><br>{texto}</div>"
    )


# --------------------------------------------------------------------------------------
# Sistema de diseño
# --------------------------------------------------------------------------------------
#
# Streamlit apila componentes del mismo peso visual, uno debajo de otro. Para una
# pantalla de diez secciones eso no es un estilo: es la ausencia de jerarquía, y
# obliga a leerlo todo para saber cualquier cosa.
#
# Estas piezas construyen la jerarquía que falta. No son adorno: cada una existe
# para que una zona de la pantalla se lea distinto de las demás —el veredicto
# grande, la evidencia en paralelo, el detalle cerrado— y para que el sistema sea
# el mismo en todas las páginas en vez de CSS suelto en cada una.
#
# Los tokens de color y tipografía salen de `marca.py`. Aquí solo se ensamblan.


def _html(bloque: str) -> None:
    """Dibuja HTML sin que el procesador de markdown lo parta.

    Un salto de línea doble dentro del HTML hace que Streamlit lo trate como dos
    párrafos y cierre etiquetas por su cuenta. Se emite en una sola línea.
    """
    st.markdown(" ".join(bloque.split()), unsafe_allow_html=True)


def banda_emisor(
    *,
    ticker: str,
    nombre: str,
    etiquetas: Sequence[str] = (),
    precio: float | None = None,
    fecha_precio=None,
    corte=None,
    nota_derecha: str = "",
) -> None:
    """Encabezado de la pantalla: quién, a cuánto y a qué fecha.

    Va en tinta sobre fondo oscuro porque es lo único que no cambia al bajar: fija
    de qué emisor se está hablando mientras el resto de la pantalla se desplaza.
    """
    chips = "".join(
        f"<span style='font-size:11px;font-weight:600;letter-spacing:.06em;"
        f"text-transform:uppercase;color:{GRIS};background:{SUPERFICIE_2};"
        f"padding:3px 8px;border-radius:{RADIO_PILDORA};margin-right:6px'>{e}</span>"
        for e in etiquetas if e
    )
    # En días HÁBILES, y solo cuando de verdad hay rezago. Un viernes contra un
    # lunes son tres días de calendario y cero de negociación: la etiqueta decía
    # "latencia 3 días" cada lunes sobre el precio más reciente que existía.
    latencia = ""
    if fecha_precio is not None and corte is not None:
        habiles = dias_habiles(fecha_precio, corte)
        if habiles > TOLERANCIA_LATENCIA:
            latencia = f" · latencia {habiles} días hábiles"
    _html(f"""
      <div style="display:flex;align-items:flex-end;justify-content:space-between;gap:32px;
                  background:{SUPERFICIE};color:{BLANCO};border:1px solid {LINEA};
                  border-left:3px solid {AMBAR};border-radius:{RADIO_TARJETA};
                  padding:20px 28px;margin-bottom:18px">
        <div style="display:flex;align-items:flex-end;gap:18px">
          <div class="cifra" style="font-size:40px;font-weight:600;line-height:.9;
                                    letter-spacing:-.02em">{ticker}</div>
          <div style="display:flex;flex-direction:column;gap:5px;padding-bottom:2px">
            <div style="font-size:16px;font-weight:600">{nombre}</div>
            <div>{chips}</div>
          </div>
        </div>
        <div style="display:flex;gap:32px;align-items:flex-end">
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px">
            <div class="rotulo" style="color:{GRIS_TENUE}">Cierre sin ajustar</div>
            <div class="cifra" style="font-size:30px;font-weight:600;line-height:1;
                                      letter-spacing:-.02em">{dinero(precio)}</div>
            <div class="cifra" style="font-size:11px;color:{GRIS_TENUE}">{fecha_precio or '—'}{latencia}</div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px;
                      border-left:1px solid {LINEA};padding-left:32px">
            <div class="rotulo" style="color:{GRIS_TENUE}">Fecha de corte</div>
            <div class="cifra" style="font-size:18px;font-weight:500">{corte or '—'}</div>
            <div class="cifra" style="font-size:11px;color:{GRIS_TENUE}">{nota_derecha}</div>
          </div>
        </div>
      </div>
    """)


def zona(numero: str, titulo: str, nota: str = "") -> None:
    """Rótulo de sección numerado. Es lo que convierte el scroll en un recorrido."""
    _html(f"""
      <div style="display:flex;align-items:baseline;gap:12px;margin:26px 0 10px">
        <span class="cifra" style="font-size:11px;font-weight:600;color:{GRIS}">{numero}</span>
        <span class="rotulo" style="font-size:11px">{titulo}</span>
        <div style="flex-grow:1;height:1px;background:{LINEA}"></div>
        <span style="font-size:11px;color:{GRIS}">{nota}</span>
      </div>
    """)


def panel_veredicto(
    *, accion: str, color: str, explicacion: str, coda: str = "",
    avance: tuple[int, int] | None = None,
) -> None:
    """El veredicto, en el tamaño que corresponde a lo único que se lee siempre."""
    barra = ""
    if avance:
        hechas, faltan = avance
        pct_barra = min(100, round(100 * hechas / faltan)) if faltan else 100
        barra = f"""
          <div style="display:flex;gap:10px;align-items:center;padding-top:2px">
            <div style="height:6px;flex-grow:1;background:{SUPERFICIE_2};position:relative">
              <div style="position:absolute;left:0;top:0;bottom:0;width:{pct_barra}%;
                          background:{color}"></div>
            </div>
            <span class="cifra" style="font-size:12px;color:{GRIS}">{hechas} / {faltan}</span>
          </div>"""
    _html(f"""
      <div style="background:{SUPERFICIE};border:1px solid {LINEA};border-left:6px solid {color};
                  padding:24px 28px;display:flex;flex-direction:column;gap:14px;height:100%">
        <div style="display:flex;align-items:baseline;gap:14px;flex-wrap:wrap">
          <div style="font-size:44px;font-weight:800;letter-spacing:-.035em;line-height:.95;
                      color:{color}">{accion}</div>
          <div style="font-size:13px;color:{GRIS};padding-bottom:4px">{coda}</div>
        </div>
        <div style="font-size:15px;line-height:1.5;color:{BLANCO}">{explicacion}</div>
        {barra}
      </div>
    """)


def puertas_html(puertas: Sequence[tuple[str, str, str, str]], pie: str = "") -> None:
    """Las tres puertas como una tira compacta: luz, nombre, lectura y su cifra."""
    filas = []
    for i, (nombre, luz, lectura, cifra) in enumerate(puertas):
        color = COLOR_LUZ.get(luz, COLOR_LUZ["SIN DATOS"])
        if i:
            filas.append(f"<div style='height:1px;background:{SUPERFICIE_2}'></div>")
        filas.append(f"""
          <div style="display:flex;align-items:center;gap:12px">
            <div style="width:10px;height:10px;border-radius:50%;background:{color};
                        flex-shrink:0"></div>
            <div style="flex-grow:1;min-width:0">
              <div style="font-size:13px;font-weight:600">{nombre}</div>
              <div style="font-size:11px;color:{GRIS}">{lectura}</div>
            </div>
            <div class="cifra" style="font-size:11px;color:{color};font-weight:600">{cifra}</div>
          </div>""")
    cierre = (
        f"<div style='font-size:11px;line-height:1.45;color:{GRIS};"
        f"border-top:1px solid {SUPERFICIE_2};padding-top:10px'>{pie}</div>" if pie else ""
    )
    _html(f"""
      <div style="background:{SUPERFICIE};border:1px solid {LINEA};padding:18px 20px;
                  display:flex;flex-direction:column;gap:12px;height:100%">
        <div class="rotulo">Las tres puertas</div>
        <div style="display:flex;flex-direction:column;gap:10px">{''.join(filas)}</div>
        {cierre}
      </div>
    """)


def rejilla_cifras(cifras: Sequence[tuple[str, str, str, str]]) -> None:
    """Banda de cifras de cabecera: rótulo, número grande, nota y su color."""
    celdas = "".join(
        f"""<div style="background:{SUPERFICIE};padding:14px 18px;display:flex;
                        flex-direction:column;gap:3px">
              <div class="rotulo">{rotulo}</div>
              <div class="cifra" style="font-size:24px;font-weight:600;letter-spacing:-.02em;
                                        color:{color or BLANCO}">{valor}</div>
              <div style="font-size:11px;color:{GRIS}">{nota}</div>
            </div>"""
        for rotulo, valor, nota, color in cifras
    )
    _html(f"""
      <div style="display:grid;grid-template-columns:repeat({len(cifras)},minmax(0,1fr));
                  gap:1px;background:{LINEA};border:1px solid {LINEA};margin-top:14px">
        {celdas}
      </div>
    """)


def tarjeta_abre(titulo: str, subtitulo: str) -> None:
    """Abre una tarjeta de evidencia. Cierra con `tarjeta_cierra`.

    Va en dos piezas porque en medio suele ir una gráfica de Streamlit, que no se
    puede meter dentro de una cadena de HTML.
    """
    _html(f"""
      <div style="background:{SUPERFICIE};border:1px solid {LINEA};border-bottom:none;
                  padding:18px 20px 10px">
        <div style="font-size:15px;font-weight:700;letter-spacing:-.01em">{titulo}</div>
        <div style="font-size:12px;color:{GRIS};line-height:1.45;margin-top:3px">{subtitulo}</div>
      </div>
    """)


def tarjeta_cierra(pie: str = "") -> None:
    cuerpo = (
        f"<div style='font-size:11px;line-height:1.5;color:{GRIS};"
        f"border-top:1px solid {SUPERFICIE_2};padding-top:10px'>{pie}</div>" if pie else ""
    )
    _html(f"""
      <div style="background:{SUPERFICIE};border:1px solid {LINEA};border-top:none;
                  padding:4px 20px 16px">{cuerpo}</div>
    """)


def barra_comparativa(
    filas: Sequence[tuple[str, float | None, str, str, bool]],
    *, maximo: float = 1.0, marca: float | None = None,
) -> None:
    """Barras horizontales para comparar magnitudes del mismo tipo.

    ``marca`` dibuja el umbral —el listón de payout, por ejemplo— como una línea
    vertical: una barra sin su umbral obliga a recordar el número de memoria.
    """
    piezas = []
    for etiqueta, valor, texto, color, destacada in filas:
        ancho = 0.0 if valor is None else max(0.0, min(1.0, valor / maximo)) * 100
        alto = 9 if destacada else 6
        peso = "700" if destacada else "400"
        marca_html = (
            f"<div style='position:absolute;left:{min(100, marca / maximo * 100)}%;"
            f"top:-3px;bottom:-3px;width:2px;background:{BLANCO}'></div>"
            if marca is not None and destacada else ""
        )
        piezas.append(f"""
          <div style="display:flex;flex-direction:column;gap:4px">
            <div style="display:flex;justify-content:space-between;align-items:baseline">
              <span style="font-size:12px;font-weight:{peso};color:{BLANCO if destacada else GRIS}">{etiqueta}</span>
              <span class="cifra" style="font-size:{15 if destacada else 13}px;
                                         font-weight:{peso};color:{color}">{texto}</span>
            </div>
            <div style="height:{alto}px;background:{SUPERFICIE_2};position:relative">
              <div style="position:absolute;left:0;top:0;bottom:0;width:{ancho}%;
                          background:{color}"></div>{marca_html}
            </div>
          </div>""")
    _html(f"""
      <div style="background:{SUPERFICIE};border-left:1px solid {LINEA};border-right:1px solid {LINEA};
                  padding:4px 20px 12px;display:flex;flex-direction:column;gap:11px">
        {''.join(piezas)}
      </div>
    """)


def cascada_html(
    pasos: Sequence[tuple[str, float | None, bool]],
    *, unidad: str = "millones de USD", pie: str = "", color_pie: str = "",
) -> None:
    """La cascada como cascada: barras y puentes, no una lista de renglones.

    ``pasos`` alterna subtotales (``es_subtotal=True``) y puentes. Un puente
    positivo suma al subtotal siguiente y uno negativo lo resta; el color lo dice
    sin necesidad de leer el signo.
    """
    montos = [abs(v) for _, v, sub in pasos if sub and v is not None]
    tope = max(montos) if montos else 1.0
    piezas = []
    tonos = ["#4A5058", "#6B6B66", "#9AA1A9", BLANCO]
    i_sub = 0
    for etiqueta, valor, es_subtotal in pasos:
        if es_subtotal:
            alto = 0 if valor is None else max(4, round(abs(valor) / tope * 100))
            tono = tonos[min(i_sub, len(tonos) - 1)]
            grande = i_sub == len(tonos) - 1
            piezas.append(f"""
              <div style="flex-grow:1;display:flex;flex-direction:column;align-items:center;
                          gap:6px;height:100%;justify-content:flex-end">
                <div class="cifra" style="font-size:{14 if grande else 12}px;
                                          font-weight:{700 if grande else 600}">{_millones(valor)}</div>
                <div style="width:100%;height:{alto}%;background:{tono}"></div>
                <div style="font-size:{12 if grande else 11}px;
                            font-weight:{700 if grande else 600};text-align:center">{etiqueta}</div>
              </div>""")
            i_sub += 1
        else:
            color = COLOR_LUZ["VERDE"] if (valor or 0) >= 0 else COLOR_LUZ["ROJO"]
            signo = "+" if (valor or 0) >= 0 else "−"
            piezas.append(f"""
              <div style="width:92px;flex-shrink:0;display:flex;flex-direction:column;
                          align-items:center;gap:5px;padding-bottom:40px">
                <div class="cifra" style="font-size:11px;color:{color};font-weight:600">
                  {signo}{_millones(abs(valor) if valor is not None else None)}</div>
                <div style="width:100%;height:2px;background:{color}"></div>
                <div style="font-size:10px;color:{GRIS};text-align:center;
                            line-height:1.25;overflow-wrap:anywhere">{etiqueta}</div>
              </div>""")
    cierre = f"""
      <div style="display:flex;justify-content:space-between;align-items:center;
                  border-top:1px solid {SUPERFICIE_2};margin-top:16px;padding-top:12px">
        <span style="font-size:13px;font-weight:600;color:{color_pie or GRIS}">{pie}</span>
        <span class="cifra" style="font-size:11px;color:{GRIS_TENUE}">{unidad}</span>
      </div>""" if pie else ""
    _html(f"""
      <div style="background:{SUPERFICIE};border:1px solid {LINEA};padding:22px 26px 18px">
        <div style="display:flex;align-items:flex-end;gap:0;height:190px">{''.join(piezas)}</div>
        {cierre}
      </div>
    """)


def _millones(valor: float | None) -> str:
    if valor is None or pd.isna(valor):
        return "—"
    return f"{valor / 1e6:,.1f}"


def filas_metodo(metodos: Sequence[tuple[str, str, bool, str]]) -> None:
    """Los métodos de valuación, con el nombre de lo que le falta al que no corre.

    Un guion en pantalla no distingue «no vale nada» de «me falta un dato para
    opinar», y esas dos cosas no se parecen en nada.
    """
    filas = []
    for i, (nombre, descripcion, disponible, cifra_o_falta) in enumerate(metodos):
        color = COLOR_LUZ["VERDE"] if disponible else COLOR_LUZ["AMARILLO"]
        fondo = SUPERFICIE if disponible else SUPERFICIE_2
        borde = f"border-top:1px solid {SUPERFICIE_2};" if i else ""
        derecha = (
            f"<div class='cifra' style='font-size:13px;font-weight:600'>{cifra_o_falta}</div>"
            if disponible else
            f"<div class='cifra' style='font-size:12px;font-weight:600;color:{color}'>bloqueado</div>"
        )
        detalle = (
            f"<div style='font-size:12px;color:{GRIS};line-height:1.5;margin-top:2px'>"
            f"{cifra_o_falta}</div>" if not disponible else ""
        )
        filas.append(f"""
          <div style="{borde}background:{fondo};display:flex;align-items:flex-start;gap:12px;
                      padding:14px 20px">
            <div style="width:8px;height:8px;border-radius:50%;background:{color};
                        margin-top:5px;flex-shrink:0"></div>
            <div style="flex-grow:1;min-width:0">
              <div style="font-size:14px;font-weight:700;
                          color:{BLANCO if disponible else color}">{nombre}</div>
              <div style="font-size:12px;color:{GRIS}">{descripcion}</div>
              {detalle}
            </div>
            {derecha}
          </div>""")
    _html(f"<div style='background:{SUPERFICIE};border:1px solid {LINEA}'>{''.join(filas)}</div>")


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
