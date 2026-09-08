"""Los estados financieros **tal como los publicó la emisora**, sin normalizar.

Qué es esto y por qué no lo cubría nada
---------------------------------------
`estados.py` normaliza: mapea las etiquetas GAAP de cada emisora a un catálogo
común de setenta y cinco renglones para que las diez se puedan comparar entre
sí. Es lo que hace posible el modelo, y es exactamente lo que impide contestar
"¿cómo se ve el estado de resultados de Realty Income, con sus renglones y en su
orden?". Después de normalizar, ese estado ya no existe: existe el nuestro.

Este módulo trae el otro. No inventa el renderizado: lo toma del que hace la
propia SEC. Cada 10-Q y 10-K trae un `FilingSummary.xml` que nombra sus reportes
y unos archivos ``R<n>.htm`` con los estados ya armados —renglón por renglón, en
su orden, con la sangría del original y con el texto que escribió la emisora—.

Y trae algo que un PDF no tendría: **cada renglón viene con su etiqueta GAAP**,
en el atributo ``defref_``. Eso convierte la vista en algo verificable. Un
renglón "as reported" no es una foto: se puede cuadrar contra el hecho que ya
tenemos en la base, y cuando no cuadra, alguno de los dos está mal.

La trampa del estado de resultados
----------------------------------
Welltower publica UN estado, "CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME",
y ese ES su estado de resultados: fusiona los dos. Public Storage y Global Net
Lease publican ese estado **además** del suyo, y en ellos el de resultado
integral es la conciliación corta del ORI —cinco renglones— que va debajo.

Buscar "comprehensive income" por nombre le daría a PSA y a GNL esa tabla de
cinco renglones en lugar de su estado de resultados, con el título correcto
encima. Por eso el resultado integral es un RESPALDO y no una alternativa: solo
se usa cuando la emisora no publicó un estado de operaciones o de ingresos.

La trampa de la escala
----------------------
El encabezado del reporte dice la escala una vez para todo el estado —"$ in
Thousands"— y NO aplica a todos los renglones. En el 10-Q de junio de 2026 de
Realty Income, la renta se imprime ``$ 1,426,467`` y son miles; la utilidad por
acción se imprime ``$ 0.37`` y son dólares. Las dos celdas traen el signo de
pesos y la misma escala declarada arriba.

Escalar a ciegas convertía una UPA de 37 centavos en 370 dólares por acción: un
número absurdo, pero en un renglón que casi nadie mira dos veces cuando el resto
del estado cuadra. Es la misma familia del formato ``bps`` de la exportación a
Excel, que ya costó una vez.

Así que la escala no se infiere: se **verifica**. Para cada renglón con etiqueta
GAAP y periodo conocidos se compara contra el hecho que la base ya tiene, y el
cociente tiene que ser exactamente una potencia declarada. Lo que no se puede
cuadrar queda marcado como no verificado y se dice en la pantalla, en vez de
pasar por bueno.
"""

from __future__ import annotations

import datetime as dt
import re

import pandas as pd

from src.ingesta.xbrl import clasificar_periodo

COLUMNAS_REPORTADOS = (
    "ticker", "estado", "formulario", "accession", "fecha_publicacion",
    "orden", "sangria", "etiqueta", "tag", "abstracta",
    "periodo_tipo", "periodo_inicio", "fecha_dato", "valor", "escala", "verificado",
)

# Cuántos reportes periódicos se leen hacia atrás. Cada 10-K trae el año y sus
# dos comparativos, y cada 10-Q el trimestre, el acumulado y sus comparativos:
# ocho filings cubren con holgura tres años de estados en las dos frecuencias.
FILINGS_POR_OMISION = 8

FORMULARIOS = ("10-Q", "10-K", "10-Q/A", "10-K/A")

ESTADO_RESULTADOS = "resultados"
ESTADO_BALANCE = "balance"
ESTADO_FLUJO = "flujo"
ESTADOS = (ESTADO_RESULTADOS, ESTADO_BALANCE, ESTADO_FLUJO)

NOMBRE_ESTADO = {
    ESTADO_RESULTADOS: "Estado de resultados",
    ESTADO_BALANCE: "Balance general",
    ESTADO_FLUJO: "Estado de flujos de efectivo",
}

# El orden importa: el primero que empate gana, y el resultado integral va aparte
# porque es un RESPALDO, no un sinónimo. Ver "La trampa del estado de resultados".
_PATRONES = (
    (ESTADO_BALANCE, re.compile(
        r"(?i)balance\s+sheets?|statements?\s+of\s+financial\s+(position|condition)")),
    (ESTADO_FLUJO, re.compile(r"(?i)statements?\s+of\s+cash\s+flows?")),
    (ESTADO_RESULTADOS, re.compile(
        r"(?i)statements?\s+of\s+(operations|income(?!\s+taxes))|income\s+statements?")),
)
_RESULTADO_INTEGRAL = re.compile(r"(?i)comprehensive\s+(income|loss|\(loss\))")

# Un "(Parenthetical)" es la nota al pie del estado —valor par de la acción,
# acciones autorizadas—, no el estado. Y "(Unaudited)" sí es el estado.
_PARENTETICO = re.compile(r"(?i)\(\s*parenthetical\s*\)")


# --------------------------------------------------------------------------------------
# Qué reporte es cada quién
# --------------------------------------------------------------------------------------


def _reportes_del_filing(cliente, url_carpeta: str) -> list[dict]:
    """Los reportes que declara `FilingSummary.xml`, en su orden."""
    try:
        xml = cliente.obtener(f"{url_carpeta}/FilingSummary.xml")
    except Exception:  # noqa: BLE001 - un filing sin resumen simplemente no aporta
        return []
    salida = []
    for m in re.finditer(r"<Report[^>]*>(.*?)</Report>", xml, re.S):
        bloque = m.group(1)

        def campo(etiqueta: str, bloque: str = bloque) -> str:
            mm = re.search(rf"<{etiqueta}>(.*?)</{etiqueta}>", bloque, re.S)
            return mm.group(1).strip() if mm else ""

        archivo = campo("HtmlFileName") or campo("XmlFileName")
        if not archivo:
            continue
        salida.append({
            "nombre": campo("ShortName"),
            "archivo": archivo,
            "categoria": campo("MenuCategory"),
        })
    return salida


def clasificar_reportes(reportes: list[dict]) -> dict[str, dict]:
    """Cuál de los reportes es cada uno de los tres estados.

    El resultado integral entra SOLO si no hubo un estado de operaciones o de
    ingresos. Welltower fusiona los dos en uno y ahí es su estado de resultados;
    Public Storage y Global Net Lease publican los dos y ahí el integral es la
    conciliación corta del ORI, que no es un estado de resultados aunque su
    nombre lo parezca.
    """
    elegidos: dict[str, dict] = {}
    respaldo: dict | None = None
    for r in reportes:
        if r["categoria"] != "Statements" or _PARENTETICO.search(r["nombre"]):
            continue
        for clave, patron in _PATRONES:
            if clave not in elegidos and patron.search(r["nombre"]):
                elegidos[clave] = r
                break
        else:
            if respaldo is None and _RESULTADO_INTEGRAL.search(r["nombre"]):
                respaldo = r
    if ESTADO_RESULTADOS not in elegidos and respaldo is not None:
        elegidos[ESTADO_RESULTADOS] = respaldo
    return elegidos


# --------------------------------------------------------------------------------------
# El renderizado de la SEC, renglón por renglón
# --------------------------------------------------------------------------------------

_FILA = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELDA = re.compile(r'<t([dh])[^>]*class="([^"]*)"[^>]*>(.*?)</t\1>', re.S)
_COLSPAN = re.compile(r'colspan="(\d+)"')
_TAG = re.compile(r"defref_([A-Za-z0-9_.-]+)")
_SANGRIA = re.compile(r"padding-left:\s*(\d+)px")
_ESCALA_TITULO = re.compile(r"(?i)\$\s+in\s+(thousands|millions|billions)")
_ESCALA_ACCIONES = re.compile(r"(?i)shares\s+in\s+(thousands|millions|billions)")
_FECHA = re.compile(r"(?i)([a-z]{3})\.?\s+(\d{1,2}),\s+(\d{4})")
_DURACION = re.compile(r"(?i)(\d+)\s+months?\s+ended")

_MESES = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}

_POTENCIAS = {"thousands": 1e3, "millions": 1e6, "billions": 1e9}


def _texto(html: str) -> str:
    t = re.sub(r"<[^>]+>", " ", html)
    for entidad, reemplazo in (("&#160;", " "), ("&nbsp;", " "), ("&amp;", "&"),
                               ("&#8217;", "'"), ("&#8211;", "-")):
        t = t.replace(entidad, reemplazo)
    return re.sub(r"\s+", " ", t).strip()


def _fecha(texto: str) -> dt.date | None:
    m = _FECHA.search(texto)
    if not m:
        return None
    mes = _MESES.get(m.group(1).lower())
    if mes is None:
        return None
    try:
        return dt.date(int(m.group(3)), mes, int(m.group(2)))
    except ValueError:
        return None


def _numero(texto: str) -> float | None:
    """El número de una celda, con el paréntesis contable como signo negativo."""
    limpio = texto.replace("$", "").replace(",", "").replace("%", "").strip()
    negativo = limpio.startswith("(") and limpio.endswith(")")
    limpio = limpio.strip("()").strip()
    if not limpio or limpio in {"-", "—", "–"}:
        return None
    try:
        valor = float(limpio)
    except ValueError:
        return None
    return -valor if negativo else valor


def _columnas(html: str) -> list[tuple[str, dt.date | None, dt.date | None]]:
    """Las columnas del reporte: (periodo_tipo, inicio, fin), en su orden.

    El encabezado trae hasta dos renglones: uno con las duraciones agrupadas
    —"3 Months Ended" con ``colspan``— y otro con las fechas de corte. Un balance
    no trae el primero, porque un saldo no dura: ahí cada columna es PUNTUAL.
    """
    duraciones: list[int] = []
    fechas: list[dt.date] = []
    for m in _FILA.finditer(html):
        encabezados = list(re.finditer(r"<th[^>]*>(.*?)</th>", m.group(1), re.S))
        if not encabezados:
            break  # se acabó el encabezado; lo que sigue son renglones
        for celda in encabezados:
            bruto = celda.group(0)
            if 'class="tl"' in bruto:
                continue  # la esquina con el título y la escala, no es una columna
            ancho = int(s.group(1)) if (s := _COLSPAN.search(bruto)) else 1
            texto = _texto(celda.group(1))
            if d := _DURACION.search(texto):
                duraciones.extend([int(d.group(1))] * ancho)
            elif (f := _fecha(texto)) is not None:
                fechas.extend([f] * ancho)
        if fechas:
            break
    salida: list[tuple[str, dt.date | None, dt.date | None]] = []
    for i, fin in enumerate(fechas):
        meses = duraciones[i] if i < len(duraciones) else None
        if meses is None:
            salida.append(("PUNTUAL", None, fin))
            continue
        # El día siguiente PRIMERO y los meses después. Al revés —restarle los
        # meses al cierre y sumarle un día— un trimestre que cierra el 30 de
        # junio empieza el 31 de marzo, y ese día pertenece al trimestre
        # anterior. La duración sale igual y la fecha queda mal, así que el
        # periodo se clasifica bien y no cuadra contra ningún hecho nuestro.
        inicio = (pd.Timestamp(fin) + pd.Timedelta(days=1) - pd.DateOffset(months=meses)).date()
        salida.append((clasificar_periodo(inicio, fin), inicio, fin))
    return salida


def _escalas(html: str) -> tuple[float, float]:
    """(escala del dinero, escala de las acciones) que declara el encabezado."""
    m = re.search(r'<th class="tl"[^>]*>(.*?)</th>', html, re.S)
    titulo = _texto(m.group(1)) if m else ""
    dinero = _ESCALA_TITULO.search(titulo)
    acciones = _ESCALA_ACCIONES.search(titulo)
    return (
        _POTENCIAS.get(dinero.group(1).lower(), 1.0) if dinero else 1.0,
        _POTENCIAS.get(acciones.group(1).lower(), 1.0) if acciones else 1.0,
    )


# Renglones a los que la escala del encabezado NO aplica, aunque traigan el signo
# de pesos. Es la trampa de la UPA: `$ 0.37` con "$ in Thousands" arriba son 37
# centavos, no 370 dólares.
_POR_ACCION = re.compile(r"(?i)per\s+(common\s+|diluted\s+|basic\s+)?(share|unit)")
_TAG_POR_ACCION = re.compile(r"(?i)PerShare|PerUnit|PerBasicShare|PerDilutedShare")
_TAG_ACCIONES = re.compile(
    r"(?i)WeightedAverageNumberOf|SharesOutstanding|SharesIssued|CommonStockShares")


def _escala_de_renglon(etiqueta: str, tag: str, dinero: float, acciones: float) -> float:
    if _POR_ACCION.search(etiqueta) or _TAG_POR_ACCION.search(tag):
        return 1.0
    if _TAG_ACCIONES.search(tag):
        return acciones
    return dinero


def parsear_reporte(
    html: str,
    ticker: str,
    estado: str,
    *,
    fecha_publicacion: dt.date,
    accession: str = "",
    formulario: str = "10-Q",
) -> pd.DataFrame:
    """Un reporte ``R<n>.htm`` de la SEC, en forma larga: un renglón por celda.

    Los renglones sin cifras —los encabezados de sección, que la SEC marca como
    ``Abstract``— se conservan con valor nulo en todas las columnas. Sin ellos el
    estado se leería como una lista de partidas sueltas: la sangría y los títulos
    SON el estado tanto como los números.
    """
    vacio = pd.DataFrame(columns=list(COLUMNAS_REPORTADOS))
    columnas = _columnas(html)
    if not columnas:
        return vacio
    dinero, acciones = _escalas(html)

    filas: list[dict] = []
    orden = 0
    for m in _FILA.finditer(html):
        celdas = _CELDA.findall(m.group(1))
        if not celdas or celdas[0][0] == "h":
            continue
        _, clase, cuerpo = celdas[0]
        if "pl" not in clase.split():
            continue
        etiqueta = _texto(cuerpo)
        if not etiqueta:
            continue
        tag_encontrado = _TAG.search(cuerpo)
        tag = tag_encontrado.group(1) if tag_encontrado else ""
        # `defref_us-gaap_LeaseIncome` y `defref_o_SomeExtension`: el prefijo es
        # la taxonomía y el resto la etiqueta. Solo interesa la etiqueta.
        if "_" in tag:
            tag = tag.split("_", 1)[1]
        sangria = _SANGRIA.search(m.group(1))
        escala = _escala_de_renglon(etiqueta, tag, dinero, acciones)

        # Las celdas de valor se cuentan DESDE LA DERECHA, y no desde la etiqueta.
        #
        # Entre la etiqueta y los números puede haber celdas de relleno que no son
        # columnas: el balance de Prologis mete un `<td class="th"><sup></sup>`
        # para las notas al pie, y su esquina del encabezado declara `colspan=2`.
        # Contando desde la izquierda, esa celda ocupaba el lugar de la primera
        # columna y TODO el estado se recorría un periodo: el efectivo de junio
        # de 2026 —1,765 millones— aparecía bajo diciembre de 2025, y el de
        # diciembre desaparecía.
        #
        # Lo que hace peligroso ese error es que se recorre PAREJO. El balance
        # seguía cuadrando consigo mismo, los totales seguían sumando y el estado
        # se leía impecable; solo estaba fechado mal. Desde la derecha el relleno
        # sobra por el lado que no importa.
        valores = [(cl, cu) for tipo, cl, cu in celdas[1:] if tipo == "d"]
        if len(valores) > len(columnas):
            valores = valores[-len(columnas):]
        crudas = [_numero(_texto(cu)) if "num" in cl else None for cl, cu in valores]
        orden += 1
        for i, (periodo_tipo, inicio, fin) in enumerate(columnas):
            bruto = crudas[i] if i < len(crudas) else None
            filas.append({
                "ticker": ticker,
                "estado": estado,
                "formulario": formulario,
                "accession": accession,
                "fecha_publicacion": fecha_publicacion,
                "orden": orden,
                "sangria": int(sangria.group(1)) if sangria else 0,
                "etiqueta": etiqueta,
                "tag": tag,
                "abstracta": all(v is None for v in crudas),
                "periodo_tipo": periodo_tipo,
                "periodo_inicio": inicio,
                "fecha_dato": fin,
                "valor": None if bruto is None else bruto * escala,
                "escala": escala,
                "verificado": False,
            })
    return pd.DataFrame(filas, columns=list(COLUMNAS_REPORTADOS))


# --------------------------------------------------------------------------------------
# La verificación de la escala contra lo que ya sabemos
# --------------------------------------------------------------------------------------

# Potencias admisibles entre lo que imprime el reporte y lo que dice el hecho. Si
# el cociente no es una de estas, no es un problema de escala: es otro número.
_POTENCIAS_ADMISIBLES = (1.0, 1e3, 1e6, 1e9)
_TOLERANCIA = 0.005


def verificar_escala(reportados: pd.DataFrame, crudos: pd.DataFrame) -> pd.DataFrame:
    """Cuadra la MAGNITUD de cada celda contra el hecho de XBRL que ya tenemos.

    Devuelve el mismo cuadro con ``valor`` corregido donde la escala declarada no
    era la del renglón, y con ``verificado`` en verdadero donde se pudo cuadrar.

    El signo se respeta y no se corrige, aunque difiera del hecho
    ---------------------------------------------------------------
    De 267 celdas que no cuadraban en la primera medición, 245 diferían por un
    factor de **−1000**: la magnitud era la misma a una potencia de diez y el
    signo era el contrario. No es un error de ninguno de los dos lados. XBRL
    guarda ``PaymentsOfDividends`` en positivo porque el elemento ya significa
    una salida, y el estado la imprime entre paréntesis porque ahí resta. La
    taxonomía tiene un rol para eso, ``negatedLabel``, y este es su efecto.

    Corregir el signo para que cuadre destruiría exactamente lo que esta vista
    existe para dar: el estado **como lo presentó la emisora**. Un flujo de
    financiamiento donde los dividendos aparecen sumando no es su estado de
    flujos, es otro. Así que la verificación es de escala y de nada más.

    No se descarta lo que no cuadra: se marca. Un renglón sin verificar puede ser
    una etiqueta de extensión que `companyfacts` no publica —que es la mitad de
    la razón por la que existe la vista— y tirarlo sería tirar justo lo que no se
    puede ver por otro lado.
    """
    if reportados.empty or crudos.empty:
        return reportados
    referencia = crudos.dropna(subset=["tag", "fecha_dato", "valor"]).copy()
    referencia["fecha_dato"] = pd.to_datetime(referencia["fecha_dato"]).dt.date
    # Ordenar ANTES de quedarse con una versión por periodo. Sin el orden, `last`
    # es la fila que quedó al final del archivo, no la reexpresión más reciente,
    # y la verificación compararía contra una versión vieja del mismo hecho.
    referencia = referencia.sort_values("fecha_publicacion").drop_duplicates(
        ["tag", "periodo_tipo", "fecha_dato"], keep="last"
    )
    conocido = {
        (r.tag, r.periodo_tipo, r.fecha_dato): float(r.valor)
        for r in referencia.itertuples()
    }

    salida = reportados.copy()
    valores = salida["valor"].tolist()
    verificados = salida["verificado"].tolist()
    for i, fila in enumerate(salida.itertuples()):
        if fila.valor is None or pd.isna(fila.valor) or not fila.tag:
            continue
        esperado = conocido.get((fila.tag, fila.periodo_tipo, fila.fecha_dato))
        if esperado is None or esperado == 0:
            continue
        crudo = fila.valor / (fila.escala or 1.0)
        if crudo == 0:
            continue
        # En valor absoluto: el signo es una decisión de presentación del emisor
        # y no se toca. Ver el porqué en la docstring.
        factor = abs(esperado / crudo)
        for potencia in _POTENCIAS_ADMISIBLES:
            if abs(factor - potencia) <= _TOLERANCIA * potencia:
                valores[i] = crudo * potencia
                verificados[i] = True
                break
    salida["valor"] = valores
    salida["verificado"] = verificados
    return salida


# --------------------------------------------------------------------------------------
# La descarga
# --------------------------------------------------------------------------------------


def descargar_reportados(
    cliente,
    ticker: str,
    cik: str,
    *,
    limite: int = FILINGS_POR_OMISION,
    crudos: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Los tres estados, tal como los publicó la emisora, de sus últimos filings.

    Cuesta cuatro peticiones por filing —el resumen y los tres estados— y todas
    entran a la caché de disco, así que reconstruir sigue sin tocar la red.
    """
    vacio = pd.DataFrame(columns=list(COLUMNAS_REPORTADOS))
    filings = cliente.listar_filings(cik, ticker, formularios=FORMULARIOS, limite=limite)
    partes: list[pd.DataFrame] = []
    for filing in filings:
        elegidos = clasificar_reportes(_reportes_del_filing(cliente, filing.url_carpeta))
        for estado, reporte in elegidos.items():
            try:
                html = cliente.obtener(f"{filing.url_carpeta}/{reporte['archivo']}")
            except Exception:  # noqa: BLE001 - un reporte ilegible no tumba la corrida
                continue
            parte = parsear_reporte(
                html, ticker, estado,
                fecha_publicacion=filing.fecha_presentacion,
                accession=filing.accession,
                formulario=filing.formulario,
            )
            if not parte.empty:
                partes.append(parte)
    if not partes:
        return vacio
    salida = pd.concat(partes, ignore_index=True)
    if crudos is not None:
        salida = verificar_escala(salida, crudos)
    return salida



__all__ = [
    "COLUMNAS_REPORTADOS",
    "ESTADOS",
    "ESTADO_BALANCE",
    "ESTADO_FLUJO",
    "ESTADO_RESULTADOS",
    "NOMBRE_ESTADO",
    "clasificar_reportes",
    "descargar_reportados",
    "parsear_reporte",
    "verificar_escala",
]
