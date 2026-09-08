"""Hechos que solo existen en el documento XBRL del filing, no en `companyfacts`.

Por qué hace falta un camino más
--------------------------------
`companyfacts` es la vía normal y cubre casi todo, pero tiene un límite que no
está documentado en ninguna parte visible: **solo expone taxonomías estándar**
—us-gaap, dei, srt, ifrs-full—. Las etiquetas de EXTENSIÓN que cada emisora
define para sí misma no aparecen ahí, aunque estén en el filing, aunque el
número esté impreso en el estado de resultados y aunque el renglón sea de los
importantes.

Extra Space Storage es el caso. Su gasto por intereses —146.7 millones en el
segundo trimestre de 2026, primer renglón debajo de la utilidad de operación—
vive bajo ``exr:InterestExpenseExcludingAmortizationOfDebtDiscountPremium``, una
etiqueta propia. En `companyfacts` no está, y sin ella no hay EBITDAre, ni costo
de la deuda, ni spread de inversión: la emisora se quedaba con dos criterios
medibles de cinco y el veredicto era INCONCLUSO.

Antes de escribir esto se probaron tres reconstrucciones y las tres se
descartaron MIDIENDO el error contra las emisoras que sí reportan el dato: desde
la utilidad de operación (9% a 70%), con el interés pagado del flujo de efectivo
(5% a 11% de mediana, con dos años de Extra Space arriba de 600%) y como residual
del estado de resultados (19% a 113%). Deducir no servía. Ir por el dato, sí.

Qué NO hace este módulo
-----------------------
No baja el instance de todas las emisoras ni de todos los renglones: son de uno a
tres megabytes por filing y duplicarían lo que `companyfacts` ya da bien. Solo
lee las etiquetas **declaradas explícitamente** en la ficha de la emisora, que es
el mismo mecanismo con el que ya se sobrescribe la taxonomía por emisora. Si una
emisora no declara ninguna, este módulo no hace una sola petición.

La trampa de las dimensiones
----------------------------
Un mismo hecho aparece muchas veces en el instance: una por el consolidado y una
por cada segmento, región o clase de deuda. Solo el contexto SIN dimensiones es
el total de la compañía. Tomar cualquiera es la forma más rápida de meter el
gasto por intereses de una subsidiaria como si fuera el de todo el emisor, y
nada en el resultado lo delataría.
"""

from __future__ import annotations

import datetime as dt
import re
import xml.etree.ElementTree as ET

import pandas as pd

from src.ingesta.estados import COLUMNAS_CRUDOS
from src.ingesta.xbrl import clasificar_periodo

# Cuántos reportes periódicos se leen hacia atrás. Cada 10-Q trae el trimestre y
# su acumulado, más los comparativos del año anterior, así que ocho filings
# cubren con holgura los doce trimestres que necesita cualquier TTM.
FILINGS_POR_OMISION = 8

FORMULARIOS = ("10-Q", "10-K", "10-Q/A", "10-K/A")

# El instance viene envuelto en el sobre SGML de EDGAR cuando se pide por su URL
# directa. Sin desenvolverlo, cualquier parser de XML falla en la primera línea.
_SOBRE = re.compile(r"<TEXT>(.*?)</TEXT>", re.S)


def _desenvolver(texto: str) -> str:
    encontrado = _SOBRE.search(texto)
    return encontrado.group(1) if encontrado else texto


def _sin_ns(etiqueta: str) -> str:
    return etiqueta.rsplit("}", 1)[-1]


def _contextos(raiz: ET.Element) -> dict[str, tuple[dt.date | None, dt.date | None]]:
    """Los contextos SIN dimensiones, que son los del consolidado.

    Un contexto con ``<segment>`` describe una parte —un segmento, una región,
    una clase de deuda—, no la compañía. Se descartan aquí y no más adelante,
    porque más adelante ya no se distinguen: son el mismo número con otra llave.
    """
    salida: dict[str, tuple[dt.date | None, dt.date | None]] = {}
    for ctx in raiz.iter():
        if _sin_ns(ctx.tag) != "context":
            continue
        idc = ctx.get("id")
        if not idc:
            continue
        if any(_sin_ns(h.tag) in ("segment", "scenario") for h in ctx.iter()):
            continue
        inicio = fin = None
        for hijo in ctx.iter():
            nombre = _sin_ns(hijo.tag)
            if nombre == "startDate":
                inicio = _fecha(hijo.text)
            elif nombre == "endDate":
                fin = _fecha(hijo.text)
            elif nombre == "instant":
                inicio, fin = None, _fecha(hijo.text)
        if fin is not None:
            salida[idc] = (inicio, fin)
    return salida


def _fecha(valor) -> dt.date | None:
    if not valor:
        return None
    try:
        return dt.date.fromisoformat(str(valor).strip()[:10])
    except ValueError:
        return None


def hechos_de_instancia(
    xml: str,
    ticker: str,
    etiquetas: set[str],
    *,
    fecha_publicacion: dt.date,
    accession: str = "",
    formulario: str = "10-Q",
) -> pd.DataFrame:
    """Extrae del instance los hechos de las etiquetas pedidas, en forma de crudo.

    Devuelve exactamente las columnas de ``hechos_crudos``, así que el resultado
    se concatena con lo que vino de `companyfacts` y todo lo de aguas abajo
    —elección de cadena, empalme verificado, derivación de trimestres— funciona
    sin cambiar una línea.
    """
    vacio = pd.DataFrame(columns=list(COLUMNAS_CRUDOS))
    if not etiquetas:
        return vacio
    try:
        raiz = ET.fromstring(_desenvolver(xml))
    except ET.ParseError:
        return vacio

    contextos = _contextos(raiz)
    if not contextos:
        return vacio

    # De `exr:InterestExpense...` interesa el nombre; el prefijo cambia entre
    # filings y no es parte de la identidad de la etiqueta.
    buscadas = {e.split(":")[-1] for e in etiquetas}
    filas: list[dict] = []
    vistos: set[tuple] = set()

    for nodo in raiz.iter():
        nombre = _sin_ns(nodo.tag)
        if nombre not in buscadas:
            continue
        ctx = nodo.get("contextRef")
        if ctx not in contextos or not (nodo.text or "").strip():
            continue
        try:
            valor = float(nodo.text.strip())
        except ValueError:
            continue
        inicio, fin = contextos[ctx]
        # El mismo hecho aparece repetido en el documento —una vez por cada lugar
        # donde el renglón se imprime—. Es el mismo dato, no dos.
        llave = (nombre, inicio, fin, valor)
        if llave in vistos:
            continue
        vistos.add(llave)
        filas.append({
            "ticker": ticker,
            "taxonomia": nodo.tag.split("}")[0].lstrip("{") if "}" in nodo.tag else "extension",
            "tag": nombre,
            "unidad": "USD",
            "periodo_tipo": clasificar_periodo(inicio, fin),
            "fecha_inicio": inicio,
            "fecha_dato": fin,
            "fecha_publicacion": fecha_publicacion,
            "valor": valor,
            "formulario": formulario,
            "accession": accession,
            "marco": "",
        })
    return pd.DataFrame(filas, columns=list(COLUMNAS_CRUDOS))


def descargar_instancias(
    cliente,
    ticker: str,
    cik: str,
    etiquetas: set[str],
    *,
    limite: int = FILINGS_POR_OMISION,
) -> pd.DataFrame:
    """Lee las etiquetas declaradas de los últimos reportes periódicos.

    Sin etiquetas declaradas no hace una sola petición: es la garantía de que
    este camino, que es más caro que `companyfacts`, solo se paga donde se
    necesita.
    """
    vacio = pd.DataFrame(columns=list(COLUMNAS_CRUDOS))
    if not etiquetas:
        return vacio

    filings = cliente.listar_filings(cik, ticker, formularios=FORMULARIOS, limite=limite)
    partes: list[pd.DataFrame] = []
    for filing in filings:
        ruta = _ruta_instancia(cliente, filing)
        if ruta is None:
            continue
        try:
            xml = cliente.obtener(ruta)
        except Exception:  # noqa: BLE001 - un filing ilegible no tumba la ingesta
            continue
        parte = hechos_de_instancia(
            xml, ticker, etiquetas,
            fecha_publicacion=filing.fecha_presentacion,
            accession=filing.accession,
            formulario=filing.formulario,
        )
        if not parte.empty:
            partes.append(parte)
    if not partes:
        return vacio
    return pd.concat(partes, ignore_index=True).drop_duplicates(
        ["tag", "periodo_tipo", "fecha_dato", "fecha_publicacion"]
    )


# Cuántos reportes se leen para rellenar un filing rezagado. Dos cubren el caso
# normal —la API va un trimestre atrás— y el de la emisora que lleva dos sin
# aparecer, sin pagar los ocho que cuesta reconstruir una serie de flujo.
FILINGS_REZAGADOS = 2


def _accesiones(crudos: pd.DataFrame) -> set[str]:
    """Los filings que `companyfacts` ya ingirió, por su número de accession.

    Sin guiones: la API los da con ellos y el índice de filings también, pero el
    formato no es parte de la identidad y no vale la pena que una discrepancia
    de puntuación decida si se baja un documento de cinco megabytes.
    """
    if crudos is None or crudos.empty or "accession" not in crudos:
        return set()
    columna = crudos["accession"].dropna().astype(str)
    return {a.replace("-", "") for a in columna if a}


def rellenar_filing_rezagado(
    cliente,
    ticker: str,
    cik: str,
    crudos_del_api: pd.DataFrame,
    etiquetas: set[str],
    *,
    limite: int = FILINGS_REZAGADOS,
) -> pd.DataFrame:
    """El filing completo del documento XBRL, cuando `companyfacts` no lo publica.

    Por qué hace falta
    ------------------
    `companyfacts` se atrasa por emisor, y el atraso no se anuncia. Al 8 de
    septiembre de 2026 publicaba marzo como el último corte de Prologis y de
    Welltower, más de un mes después de que las dos presentaran su 10-Q de junio:
    el reporte estaba en EDGAR y la API no lo tenía.

    Lo que vuelve peligroso ese atraso es que es PARCIAL entre FUENTES. El AFFO y
    la utilidad del trimestre entran igual porque vienen del 8-K, así que el
    apalancamiento y el LTV combinaban una deuda de un trimestre con un flujo de
    otro y el ratio salía perfectamente plausible. Un saldo viejo no se ve; es la
    misma invisibilidad de la prueba 30, ahora entre dos fuentes.

    Lo que NO es parcial es el filing dentro de la API: cuando `companyfacts` va
    atrasada, le falta el reporte ENTERO. A Prologis y a Welltower no les faltaba
    el balance de junio: les faltaban también el estado de resultados y el de
    flujo, y con ellos las acciones diluidas —el denominador de todo lo que se
    mide por acción—. La primera versión de esto pedía solo las etiquetas de
    balance y por eso cerró un tercio del hueco creyendo que lo cerraba todo.

    Cómo decide si vale la pena bajar algo
    --------------------------------------
    Pregunta si la API ya tiene ESE filing, por su accession. El índice de
    filings es barato y el documento XBRL no, así que el camino caro se paga solo
    donde la API se quedó corta y deja de pagarse en cuanto se pone al día.

    ``crudos_del_api`` tiene que ser lo que devolvió `companyfacts` y NADA MÁS.
    Si se le pasa el crudo ya concatenado con lo que bajó `descargar_instancias`,
    la guarda se contesta a sí misma: las etiquetas de extensión de Realty Income
    y de Extra Space se leen del mismo documento y lo marcan como presente, así
    que el rezago de la API quedaría tapado justo en las dos emisoras que más
    caminos usan. Comparar fechas de publicación en vez de accessions tenía el
    mismo agujero.
    """
    vacio = pd.DataFrame(columns=list(COLUMNAS_CRUDOS))
    if not etiquetas:
        return vacio

    filings = cliente.listar_filings(cik, ticker, formularios=FORMULARIOS, limite=limite)
    if not filings:
        return vacio

    presentes = _accesiones(crudos_del_api)
    pendientes = [f for f in filings if f.accession.replace("-", "") not in presentes]
    if not pendientes:
        return vacio

    partes: list[pd.DataFrame] = []
    for filing in pendientes:
        ruta = _ruta_instancia(cliente, filing)
        if ruta is None:
            continue
        try:
            xml = cliente.obtener(ruta)
        except Exception:  # noqa: BLE001 - un filing ilegible no tumba la ingesta
            continue
        parte = hechos_de_instancia(
            xml, ticker, etiquetas,
            fecha_publicacion=filing.fecha_presentacion,
            accession=filing.accession,
            formulario=filing.formulario,
        )
        if not parte.empty:
            partes.append(parte)
    if not partes:
        return vacio
    return pd.concat(partes, ignore_index=True).drop_duplicates(
        ["tag", "periodo_tipo", "fecha_dato", "fecha_publicacion"]
    )


def _ruta_instancia(cliente, filing) -> str | None:
    """La URL del instance del filing, buscándola en su índice.

    El nombre sigue el patrón ``<ticker>-<fecha>_htm.xml`` pero ni el ticker ni
    el formato de la fecha son estables entre emisoras, así que se lee el índice
    en vez de construirlo.
    """
    import json

    try:
        indice = json.loads(cliente.obtener(f"{filing.url_carpeta}/index.json"))
    except Exception:  # noqa: BLE001
        return None
    nombres = [i.get("name", "") for i in indice.get("directory", {}).get("item", [])]
    for nombre in nombres:
        if nombre.endswith("_htm.xml"):
            return f"{filing.url_carpeta}/{nombre}"
    return None


__all__ = ["descargar_instancias", "hechos_de_instancia", "rellenar_filing_rezagado"]
