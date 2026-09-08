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


__all__ = ["descargar_instancias", "hechos_de_instancia"]
