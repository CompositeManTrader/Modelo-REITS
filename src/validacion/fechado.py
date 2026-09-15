"""Saldos que llegaron con la fecha equivocada desde el propio XBRL del emisor.

El caso que lo originó
----------------------
El 10-Q de Welltower del primer trimestre de 2013 declara ``Assets =
19,549,109,000`` **dos veces**: una con fecha 2012-12-31 —que es el cierre de año
comparativo, y es correcta— y otra con fecha 2012-03-31, que no lo es. El activo
total de Welltower en marzo de 2012 fue 15,859,734,000, como lo dijo su propio
10-Q de entonces. Prologis tiene exactamente el mismo defecto en el primer
trimestre de 2017.

No es un error de lectura nuestro: viene así de ``companyfacts``, y la SEC lo
pasa tal cual porque así lo etiquetó el emisor. Se verificó contra la fuente.

Por qué el modelo se lo creía
-----------------------------
P1 dice que de cada celda se toma la versión publicada más reciente, y eso es
correcto para una serie: una reexpresión posterior es mejor información. Pero un
balance no es una serie, es una **identidad**: activos = pasivos + capital. Esa
igualdad solo existe dentro de un filing. Al tomar el activo de una cosecha y el
pasivo de otra, la identidad se rompe sin que ninguna de las dos cifras esté mal
por su cuenta.

Aquí no se está debilitando P1. Se está usando la contabilidad como evidencia
sobre CUÁL de las dos cosechas describe realmente a ese periodo.

La regla, y por qué es estrecha
-------------------------------
Dentro de un mismo filing, un saldo estructural que reporta **el mismo valor
distinto de cero en dos fechas** es sospechoso: que el activo total coincida al
dólar en dos cierres distintos no pasa por casualidad. Pero eso solo abre la
pregunta; quien la contesta es la identidad contable. Se marca la fecha donde el
valor **contradice** al pasivo más capital declarado para ESA fecha, y solo si
hay otra donde **cuadra**. Sin las dos condiciones no se toca nada: una
reexpresión de verdad mueve el activo y sus componentes juntos, y ahí la
identidad se sigue cumpliendo.

Medido sobre las diez emisoras: el patrón aparece en **dos** celdas, y las dos
están mal. Cero falsos positivos. Esa medición es lo que justifica la regla; sin
ella sería una hipótesis bonita sobre una población desconocida.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# La misma que usa `balance_cuadra`. Deliberadamente compartida: si el detector
# fuera más estricto que la verificación, marcaría celdas que nadie reporta; si
# fuera más laxo, dejaría pasar las que sí se reportan. Las dos preguntas son la
# misma pregunta.
from src.validacion.estados import TOLERANCIA_RELATIVA

# El activo total es el único saldo cuya contradicción se puede establecer con lo
# que hay: sus dos contrapartes. Para el pasivo o el capital por separado no
# existe una segunda fuente con la cual contrastarlos.
CLAVE_ACTIVO = "activos_totales"
# El emisor publica el lado derecho de la identidad como un renglón propio, y ese
# es el que manda: `LiabilitiesAndStockholdersEquity` es su cierre del balance, sin
# que nadie tenga que rearmarlo. Sumar las partes es el camino de respaldo, y no da
# lo mismo: a Welltower le falta el capital temporal —participaciones redimibles,
# 34.6 MM en 2012— y sin él la suma se desvía 0.18%, lo bastante para que el
# detector se abstuviera de un caso que sí estaba mal.
CLAVE_DECLARADO = "pasivo_mas_capital"
CLAVES_PARTES = ("pasivos_totales", "capital_total")
CLAVE_TEMPORAL = "capital_temporal"


@dataclass(frozen=True)
class MalFechado:
    """Un saldo cuya fecha no puede ser la que dice."""

    ticker: str
    clave: str
    fecha_dato: str
    fecha_publicacion: str
    accession: str
    valor: float
    contraparte: float
    fecha_correcta: str
    id_hecho: int | None = None

    def nota(self) -> str:
        return (
            f"El filing {self.accession} declara {self.valor:,.0f} para "
            f"{self.fecha_dato} y también para {self.fecha_correcta}. En "
            f"{self.fecha_correcta} cuadra con pasivo + capital; en {self.fecha_dato} "
            f"contradice a los {self.contraparte:,.0f} declarados. Es el saldo de "
            f"{self.fecha_correcta} con la fecha de otro periodo."
        )


def _cuadra(a: float, b: float) -> bool:
    escala = max(abs(a), abs(b))
    return escala == 0 or abs(a - b) / escala <= TOLERANCIA_RELATIVA


def _contrapartes(saldos: pd.DataFrame) -> dict[str, float]:
    """El lado derecho de la identidad por fecha: lo que tiene que igualar al activo.

    Se usan las versiones VIGENTES y no las del mismo filing a propósito: lo que se
    quiere saber es si el valor cabe en el balance de ese periodo tal como hoy se
    conoce, no si el filing es internamente consistente —eso ya lo sabemos, y es
    justo lo que hace sospechosa a la copia—.
    """
    ultimas = (
        saldos.sort_values("fecha_publicacion")
        .groupby(["fecha_dato", "clave"])["valor"]
        .last()
        .unstack("clave")
    )
    if ultimas.empty:
        return {}

    contra: dict[str, float] = {}
    if CLAVE_DECLARADO in ultimas.columns:
        contra.update(ultimas[CLAVE_DECLARADO].dropna().to_dict())
    if not set(CLAVES_PARTES) <= set(ultimas.columns):
        return contra
    # El respaldo solo cubre las fechas donde el emisor no declaró el total.
    suma = ultimas["pasivos_totales"] + ultimas["capital_total"]
    if CLAVE_TEMPORAL in ultimas.columns:
        suma = suma + ultimas[CLAVE_TEMPORAL].fillna(0.0)
    for fecha, valor in suma.dropna().items():
        contra.setdefault(fecha, float(valor))
    return contra


def detectar_mal_fechados(ticker: str, saldos: pd.DataFrame) -> list[MalFechado]:
    """Saldos que repiten un valor en dos fechas y contradicen el balance en una.

    ``saldos`` necesita las columnas ``clave``, ``fecha_dato``,
    ``fecha_publicacion``, ``valor`` y ``accession``; ``id`` si se quiere poder
    marcar el hecho después.
    """
    if saldos.empty:
        return []
    faltan = {"clave", "fecha_dato", "fecha_publicacion", "valor", "accession"} - set(saldos.columns)
    if faltan:
        raise ValueError(f"Faltan columnas para detectar el mal fechado: {sorted(faltan)}")

    vista = saldos.copy()
    for col in ("fecha_dato", "fecha_publicacion"):
        vista[col] = vista[col].astype(str).str.slice(0, 10)
    vista["valor"] = pd.to_numeric(vista["valor"], errors="coerce")

    contra = _contrapartes(vista)
    if not contra:
        return []

    activos = vista[(vista["clave"] == CLAVE_ACTIVO) & (vista["valor"].fillna(0) != 0)]
    hallazgos: list[MalFechado] = []
    for (accession, valor), grupo in activos.groupby(["accession", "valor"]):
        fechas = sorted(set(grupo["fecha_dato"]))
        if len(fechas) < 2:
            continue
        # Con las contrapartes en la mano, cada fecha queda de un lado o del otro.
        cuadran = [f for f in fechas if f in contra and _cuadra(valor, contra[f])]
        chocan = [f for f in fechas if f in contra and not _cuadra(valor, contra[f])]
        # Sin una fecha que cuadre no hay a dónde caer, y sin una que choque no hay
        # nada que corregir. En los dos casos la evidencia no alcanza.
        if not cuadran or not chocan:
            continue
        for fecha in chocan:
            fila = grupo[grupo["fecha_dato"] == fecha].iloc[-1]
            hallazgos.append(
                MalFechado(
                    ticker=ticker,
                    clave=CLAVE_ACTIVO,
                    fecha_dato=fecha,
                    fecha_publicacion=str(fila["fecha_publicacion"]),
                    accession=str(accession),
                    valor=float(valor),
                    contraparte=float(contra[fecha]),
                    fecha_correcta=cuadran[0],
                    id_hecho=int(fila["id"]) if "id" in fila and pd.notna(fila["id"]) else None,
                )
            )
    return hallazgos


def descartar_del_crudo(
    ticker: str, crudos: pd.DataFrame, tags: dict[str, str]
) -> tuple[pd.DataFrame, list[MalFechado]]:
    """Quita del crudo los saldos mal fechados, para armar el balance sin ellos.

    El archivo versionado NO se toca: sigue siendo el XBRL tal como lo publicó la
    SEC, con el defecto del emisor incluido, porque ese archivo es el registro de
    lo que se publicó y no el de lo que creemos. Lo que se corrige es la
    PROYECCIÓN: el balance que se arma a partir de él.

    ``tags`` es el mapeo de renglón a etiqueta GAAP que ya eligió ``elegir_tags``
    para esta emisora. Se reutiliza en lugar de codificar las etiquetas aquí
    porque cambian por emisora, y dos listas de etiquetas se separan.
    """
    claves = {CLAVE_ACTIVO, CLAVE_DECLARADO, CLAVE_TEMPORAL, *CLAVES_PARTES}
    por_tag = {tags[c]: c for c in claves if c in tags}
    if CLAVE_ACTIVO not in tags or crudos.empty:
        return crudos, []

    saldos = crudos[
        (crudos["periodo_tipo"] == "PUNTUAL") & (crudos["tag"].isin(por_tag))
    ].copy()
    if saldos.empty:
        return crudos, []
    saldos["clave"] = saldos["tag"].map(por_tag)

    hallazgos = detectar_mal_fechados(ticker, saldos)
    if not hallazgos:
        return crudos, []

    fuera = {(h.fecha_dato, h.accession, h.valor) for h in hallazgos}
    llave = list(
        zip(
            crudos["fecha_dato"].astype(str).str.slice(0, 10),
            crudos["accession"].astype(str),
            pd.to_numeric(crudos["valor"], errors="coerce"),
            strict=False,
        )
    )
    quitar = pd.Series(
        [k in fuera for k in llave], index=crudos.index
    ) & (crudos["tag"] == tags[CLAVE_ACTIVO])
    return crudos[~quitar], hallazgos


def resumir(hallazgos: list[MalFechado]) -> str:
    if not hallazgos:
        return "sin saldos mal fechados"
    return f"{len(hallazgos)} saldo(s) mal fechados: " + ", ".join(
        f"{h.ticker} {h.fecha_dato}" for h in hallazgos
    )
