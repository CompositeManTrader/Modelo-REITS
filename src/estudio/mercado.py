"""Precio y dividendos desde el IPO, SIN ajustar por dividendos (P2).

Por qué hace falta otra fuente
------------------------------
El proveedor diario de ``src.ingesta.precios`` entrega diez años de precio y cinco
de dividendos, y su rango ``MAX`` devuelve MENOS que ``10Y``. Para un estudio de
largo plazo eso corta la historia a la mitad: Realty Income cotiza desde octubre
de 1994 y lo interesante —el 2000, la crisis de 2008— queda afuera.

Esta fuente llega al primer día de cotización, pero entrega el cierre ajustado por
**eventos de capital**, que no es lo mismo que ajustado por dividendos:

* un split verdadero (2 por 1 en enero de 2005), y
* una escisión que el proveedor registra COMO SI fuera split: la de Orion Office
  REIT en noviembre de 2021, con factor 1.032.

Deshacer el ajuste es obligatorio. El AFFO por acción de los reportes está en las
acciones de cada época; si se divide un precio ajustado entre él, el P/AFFO de
antes de 2021 sale 3.2% bajo y el de antes de 2005 a la mitad, sin que ningún
número se vea raro.

Validado contra la base: en los 2,513 días de traslape (2016-2026) el cierre
desajustado coincide con el cierre crudo del proveedor diario con error de
0.0000%, antes y después de la escisión.

Por qué los eventos van en un catálogo y no se adivinan
-------------------------------------------------------
El proveedor no distingue un split de una escisión: los dos llegan como
``splitRatio``. Una regla del tipo «si el cociente es entero es split» acierta con
estos dos y falla con el siguiente spin-off que caiga en 2:1. Así que cada evento
se declara a mano, con su naturaleza y su fuente, y si el proveedor reporta uno
que no está en el catálogo la descarga se NIEGA: un factor que no se entiende no
se aplica.

Dos bases por acción
--------------------
* ``cierre_crudo`` / ``monto_pagado``: lo que de verdad cotizó y se pagó ese día.
* ``cierre_base`` / ``monto_base``: expresado en **acciones de hoy**, deshecho solo
  el split verdadero. Es la base para comparar un dividendo de 1995 con uno de 2026.

La escisión NO entra a la base: no cambió el número de acciones, así que el
dividendo por acción de antes y de después se comparan tal cual. Su valor sí
entra al retorno total, como distribución en especie (ver ``retornos``).
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd
import requests

from src.config import DIR_ESTUDIOS, TOLERANCIA_ANCLA_PRECIO

FUENTE_LARGA = "MERCADO-YAHOO"
URL_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
ENCABEZADOS = {"User-Agent": "Modelo-REITS/1.0 (plataforma de valuacion de REITs)"}

ARCHIVO_PRECIOS = "precios.csv.gz"
ARCHIVO_DIVIDENDOS = "dividendos.csv.gz"
ARCHIVO_MANIFIESTO = "manifiesto.json"

# Qué tanto puede diferir el cierre desajustado del crudo del proveedor diario en
# el traslape. Se midió 0.0000%; el umbral es el de las anclas de precio (P2)
# porque la pregunta es la misma: ¿es este el precio al que cotizó?
TOLERANCIA_TRASLAPE = TOLERANCIA_ANCLA_PRECIO


class ErrorMercadoLargo(RuntimeError):
    pass


@dataclass(frozen=True)
class EventoDeCapital:
    """Un cambio en la relación entre el precio y la acción.

    ``factor`` es el que aplica el proveedor: todo lo anterior a ``fecha`` viene
    DIVIDIDO entre él. ``tipo`` decide qué se deshace y dónde:

    * ``split``: cambió el número de acciones. Se deshace para el precio crudo y
      se conserva en la base «acciones de hoy».
    * ``escision``: se repartió valor en especie. Se deshace en las dos bases
      —el número de acciones no cambió— y entra al retorno total.
    """

    fecha: dt.date
    factor: float
    tipo: str
    descripcion: str
    fuente: str


# Catálogo verificado. Un evento que el proveedor reporte y no esté aquí detiene
# la descarga (ver el docstring del módulo).
EVENTOS_DE_CAPITAL: dict[str, tuple[EventoDeCapital, ...]] = {
    "O": (
        EventoDeCapital(
            fecha=dt.date(2005, 1, 3),
            factor=2.0,
            tipo="split",
            descripcion="Split 2 por 1 de la acción común.",
            fuente="Realty Income, comunicado del 2004-12 sobre el split; factor verificado "
                   "con el primer dividendo mensual posterior al IPO (0.15 dólares).",
        ),
        EventoDeCapital(
            fecha=dt.date(2021, 11, 15),
            factor=1.032,
            tipo="escision",
            descripcion="Escisión de Orion Office REIT (ONL): una acción de ONL por cada "
                        "diez de O. No cambió el número de acciones de O.",
            fuente="Formulario 10 de Orion Office REIT y 8-K de Realty Income (nov-2021); "
                   "factor verificado contra 1,307 cierres crudos previos, error 0.0000%.",
        ),
    ),
    # Vacío a propósito, y declarado: «sin eventos» es una afirmación verificada, no
    # la ausencia de una. Si el proveedor llega a reportar uno, la descarga se detiene.
    "NNN": (),
    "WPC": (
        EventoDeCapital(
            fecha=dt.date(2023, 11, 2),
            factor=1.021,
            tipo="escision",
            descripcion="Escisión de Net Lease Office Properties (NLOP): una acción de NLOP por "
                        "cada 15 de WPC, distribuida el 1-nov-2023. No cambió el número de "
                        "acciones de WPC.",
            fuente="8-K de W. P. Carey del 6-oct-2023 («one NLOP common share for every 15 shares "
                   "of W. P. Carey common stock») y del 2-nov-2023; NLOP cotiza «regular way» "
                   "desde el 2-nov-2023. Factor verificado contra 2,527 cierres crudos del "
                   "proveedor diario, error 0.0000%. El factor valora lo repartido en 1.12 "
                   "dólares por acción de WPC (16.74 por acción de NLOP); el Formulario 8937 de "
                   "WPC (30-ene-2024) lo valora en 11.44 por acción de NLOP, promedio ponderado "
                   "de tres días: 0.76 por acción de WPC, 1.4% del precio en vez de 2.1%. La "
                   "diferencia, una sola vez, pesa menos de 0.03 puntos al año en el retorno "
                   "desde 1998. Se usa el del proveedor porque es el que reproduce sus cierres.",
        ),
    ),
}

SPLITS_DE_TIPO = ("split", "escision")


@dataclass(frozen=True)
class CorreccionDividendo:
    """Un registro del proveedor que contradice al emisor, y cómo queda.

    Los montos van en la base PAGADA —lo que de verdad recibió el accionista ese
    día— porque así los publica el 10-K. ``proveedor`` es lo que el proveedor dice
    hoy: si deja de decirlo —porque corrigió su dato— la corrección ya no aplica y
    la descarga se detiene. Aplicarla sobre un dato ya arreglado lo rompería.
    """

    fecha_ex: dt.date
    proveedor: float
    partes: tuple[tuple[float, str], ...]   # (monto pagado, "regular" | "especial")
    fuente: str


# Medido: la suma anual del proveedor cuadra con la de los 10-K dentro de 0.8% de
# 1997 a 2007. Donde no cuadraba (1995-1996, ±17%) la causa está en estos cuatro
# registros, cada uno contrastado contra el reporte del emisor.
CORRECCIONES_DE_DIVIDENDOS: dict[str, tuple[CorreccionDividendo, ...]] = {
    "O": (
        CorreccionDividendo(
            fecha_ex=dt.date(1995, 8, 16), proveedor=0.078,
            partes=((0.155, "regular"),),
            fuente="10-Q 3T-1995: «increased its monthly distributions to $0.155 per share in "
                   "August and September». No hubo distribución prorrateada por la fusión con "
                   "el asesor; el proveedor registra la de agosto a la mitad.",
        ),
        CorreccionDividendo(
            fecha_ex=dt.date(1995, 12, 21), proveedor=0.54,
            partes=((0.155, "regular"), (0.155, "regular"), (0.23, "especial")),
            fuente="10-K 1995: en diciembre se declararon dos distribuciones de $0.155 y una "
                   "especial de $0.23 (exigida por el régimen REIT tras la fusión con el "
                   "asesor). El proveedor las suma en un registro y deja vacío enero de 1996.",
        ),
        CorreccionDividendo(
            fecha_ex=dt.date(1996, 11, 27), proveedor=0.154,
            partes=((0.1575, "regular"),),
            fuente="10-K 1996: el 4T declaró $0.470 = 0.155 + 0.1575 + 0.1575. El 0.154 del "
                   "proveedor fabricaría el único recorte de la historia de O.",
        ),
        CorreccionDividendo(
            fecha_ex=dt.date(1996, 12, 27), proveedor=0.154,
            partes=((0.1575, "regular"),),
            fuente="10-K 1996: «a distribution of $0.1575 per share had been declared» al "
                   "31-dic-1996, pagada el 15-ene-1997.",
        ),
    ),
    # WPC: el proveedor suma cada distribución especial a la regular del trimestre. Sin
    # separarlas, el yield de 2008, 2010 y 2014 sale inflado un año entero y la serie
    # dibuja «aumentos» de 57% seguidos de «recortes» que nunca ocurrieron.
    "WPC": (
        CorreccionDividendo(
            fecha_ex=dt.date(2007, 12, 27), proveedor=0.747,
            partes=((0.477, "regular"), (0.27, "especial")),
            fuente="Suplemento de resultados 2007 (8-K de 2008): distribución especial de $0.27 "
                   "pagada en enero de 2008, aparte del dividendo del 4T-2007 ($0.477). El "
                   "trimestre siguiente paga $0.482.",
        ),
        CorreccionDividendo(
            fecha_ex=dt.date(2009, 12, 29), proveedor=0.802,
            partes=((0.502, "regular"), (0.30, "especial")),
            fuente="10-K 2009: especial de $0.30 pagada en enero de 2010 a los tenedores al "
                   "31-dic-2009, «as a result of an increase in our 2009 taxable income»; el "
                   "regular del 4T-2009 fue $0.502.",
        ),
        CorreccionDividendo(
            fecha_ex=dt.date(2013, 12, 27), proveedor=0.98,
            partes=((0.87, "regular"), (0.11, "especial")),
            fuente="Comunicado del 4T-2013 (8-K): especial de $0.11 además del regular, que sube "
                   "a $0.87 («fifty-first consecutive quarterly dividend increase»).",
        ),
    ),
}

@dataclass(frozen=True)
class InicioVerificable:
    """Desde cuándo el registro del proveedor se puede contrastar con el emisor.

    Antes de esta fecha el precio existe pero los dividendos no están completos, y
    un retorno total sin dividendos no es un retorno total: es un precio. La serie
    se corta aquí, con la razón escrita, en vez de rellenar con lo que no se pudo
    comprobar.
    """

    fecha: dt.date
    motivo: str


INICIOS_VERIFICABLES: dict[str, InicioVerificable] = {
    "NNN": InicioVerificable(
        fecha=dt.date(1992, 1, 1),
        motivo=(
            "NNN cotiza desde 1984 (como Golden Corral Realty), pero el proveedor no trae los "
            "dividendos de 1984 a 1989 y le falta el de julio de 1990. El primer reporte del "
            "emisor en EDGAR es de 1995 y su tabla más antigua empieza en 1992: el prospecto de "
            "enero de 1996 da los dividendos de 1992 a 1995 trimestre por trimestre, y coinciden "
            "con el proveedor. Antes de 1992 no hay contra qué verificar."
        ),
    ),
}


# Cierres NYSE publicados por el emisor —«last reported sale price» de sus
# prospectos, «closing sales prices» de las tablas trimestrales de sus 10-K—, uno por
# renglón con su documento y la frase citada. Las anclas de ``src.ingesta.precios``
# validan la serie diaria de diez años; estas validan la historia larga, donde no
# hay otra serie contra qué comparar. Van en un archivo y no en el código porque
# cada una lleva su cita, y son decenas.
ARCHIVO_ANCLAS = "anclas.csv"


def anclas_largas(ticker: str, raiz: Path | None = None) -> pd.DataFrame:
    ruta = dir_de(ticker, raiz) / ARCHIVO_ANCLAS
    if not ruta.exists():
        return pd.DataFrame(columns=["fecha", "cierre", "fuente", "url", "cita"])
    return pd.read_csv(ruta, parse_dates=["fecha"])


@dataclass(frozen=True)
class RangoTrimestral:
    """Máximo y mínimo de un trimestre según el emisor: todo cierre debe caber."""

    anio: int
    trimestre: int
    maximo: float
    minimo: float
    fuente: str


def _rangos(fuente: str, anio: int, filas: tuple[tuple[float, float], ...]) -> tuple[RangoTrimestral, ...]:
    return tuple(RangoTrimestral(anio, i + 1, alto, bajo, fuente) for i, (alto, bajo) in enumerate(filas))


_PROSPECTO_NNN_1996 = "Prospecto 424B2 de ene-1996 (Price Range of Common Stock)"
RANGOS_TRIMESTRALES: dict[str, tuple[RangoTrimestral, ...]] = {
    "NNN": (
        *_rangos(_PROSPECTO_NNN_1996, 1992, ((10.0, 9.0), (10.25, 9.25), (12.125, 9.25), (12.5, 11.375))),
        *_rangos(_PROSPECTO_NNN_1996, 1993, ((14.0, 11.75), (15.0, 13.125), (14.375, 13.125), (14.625, 13.0))),
        *_rangos(_PROSPECTO_NNN_1996, 1994, ((14.375, 13.25), (14.5, 13.25), (14.0, 12.875), (12.625, 11.875))),
        *_rangos(_PROSPECTO_NNN_1996, 1995, ((12.5, 11.75), (13.75, 11.875), (13.625, 12.125), (13.375, 12.5))),
    ),
}


# Un cierre fuera del rango publicado detiene la descarga, salvo que esté aquí con
# su explicación. No es una tolerancia: cada excepción se revisó a mano y el
# manifiesto la lista, para que quien lea la validación sepa que existe.
EXCEPCIONES_DE_RANGO: dict[str, dict[str, str]] = {
    "NNN": {
        "1994-T3": (
            "Un solo cierre, el del viernes 30-sep-1994 (12.25), queda bajo el mínimo publicado "
            "del trimestre (12.875); el lunes 3-oct el proveedor repite 12.25, que sí cabe en el "
            "4T. Todos los demás cierres del trimestre caben. La firma es la de un desfase de un "
            "día en el dato antiguo del proveedor, no la de un precio ajustado: un precio ajustado "
            "por dividendos estaría abajo todo el año, no un día."
        ),
    },
}


# Anclas de precio que contradicen la serie más allá de la tolerancia, revisadas una
# por una y con su explicación. Igual que las de rango: no es una tolerancia más
# holgada, es un documento del emisor que se demostró equivocado con OTRO
# documento del emisor. El manifiesto las lista aparte; un ancla de esa fecha que
# sí cuadra se valida como cualquier otra.
_CUADRO_WPC_2000 = (
    "El cuadro de precios de 2000 del 10-K de ese año (repetido en los informes de 2001 y "
    "2002) no cuadra con otro documento del emisor: da 15.45 como cierre del 31-mar-2000 y "
    "16.03 como máximo del trimestre, pero el proxy de la fusión (DEFM14A, 17-may-2000) da "
    "16.625 como cierre de ese mismo día, igual que el proveedor. El 4T sí cuadra al centavo "
    "(18.10), igual que los cierres trimestrales de 1998, 1999 y 2001 a 2004. Y las opciones "
    "de 2000 se otorgaron a precios «desde 16.38»: el cierre del proveedor del 30-jun (16.375), "
    "no el del cuadro (15.60)."
)
EXCEPCIONES_DE_ANCLA: dict[str, dict[str, str]] = {
    "WPC": dict.fromkeys(("2000-03-31", "2000-06-30", "2000-09-29"), _CUADRO_WPC_2000),
}


def recortar_al_inicio(
    ticker: str, precios: pd.DataFrame, dividendos: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, InicioVerificable | None]:
    """Quita lo anterior al inicio verificable del emisor, si lo tiene."""
    inicio = INICIOS_VERIFICABLES.get(ticker.upper())
    if inicio is None:
        return precios, dividendos, None
    corte = pd.Timestamp(inicio.fecha)
    return (
        precios[precios["fecha"] >= corte].reset_index(drop=True),
        dividendos[dividendos["fecha_ex"] >= corte].reset_index(drop=True),
        inicio,
    )


# Cuánto puede bajar una mensualidad antes de llamarlo recorte. El proveedor
# redondea a tres decimales y 0.18375 le sale a veces 0.184 y a veces 0.183: esa
# «baja» de 0.5% es tinta, no política de dividendos.
TOLERANCIA_RECORTE = 0.01


def aplicar_correcciones(ticker: str, dividendos: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Sustituye los registros catalogados; devuelve también la bitácora.

    Recibe la tabla ya desajustada (con ``monto_pagado`` y ``monto_base``) y la
    devuelve con la columna ``tipo``. La base «acciones de hoy» de cada parte se
    obtiene con el mismo cociente pagado→base del registro original.
    """
    d = dividendos.copy()
    d["tipo"] = "regular"
    bitacora: list[str] = []
    filas_nuevas = []
    quitar = []
    for c in CORRECCIONES_DE_DIVIDENDOS.get(ticker.upper(), ()):
        cerca = d[(d["fecha_ex"] - pd.Timestamp(c.fecha_ex)).abs() <= pd.Timedelta(days=3)]
        if cerca.empty:
            raise ErrorMercadoLargo(
                f"La corrección de {ticker} del {c.fecha_ex} no encuentra su registro. "
                "¿Cambió el proveedor? Revísala antes de volver a descargar."
            )
        fila = cerca.iloc[0]
        if abs(fila["monto_pagado"] / c.proveedor - 1) > 0.02:
            raise ErrorMercadoLargo(
                f"El proveedor ya no dice {c.proveedor} el {c.fecha_ex} sino "
                f"{fila['monto_pagado']:.4f}. Si lo corrigió, esta corrección sobra; si cambió "
                "a otro valor, hay que volver a contrastarlo con el 10-K."
            )
        razon = fila["monto_base"] / fila["monto_pagado"]
        quitar.append(fila.name)
        for monto, tipo in c.partes:
            filas_nuevas.append({"fecha_ex": fila["fecha_ex"], "monto_proveedor": float("nan"),
                                 "monto_pagado": monto, "monto_base": monto * razon, "tipo": tipo})
        bitacora.append(f"{c.fecha_ex}: {fila['monto_pagado']:.4f} → "
                        f"{' + '.join(f'{m} ({t})' for m, t in c.partes)}. {c.fuente}")
    if filas_nuevas:
        d = pd.concat([d.drop(index=quitar), pd.DataFrame(filas_nuevas)], ignore_index=True)
    return d.sort_values(["fecha_ex", "tipo"]).reset_index(drop=True), bitacora


# --------------------------------------------------------------------------------------
# Descarga
# --------------------------------------------------------------------------------------


@dataclass
class CrudoProveedor:
    """Lo que entrega el proveedor, sin tocar."""

    ticker: str
    precios: pd.DataFrame      # fecha, cierre_proveedor, ajustado_proveedor
    dividendos: pd.DataFrame   # fecha_ex, monto_proveedor
    eventos: list[tuple[dt.date, float]]
    primera_cotizacion: dt.date | None


def descargar(ticker: str, *, timeout: int = 60) -> CrudoProveedor:
    r = requests.get(
        URL_CHART.format(ticker=ticker.upper()),
        headers=ENCABEZADOS,
        params={"period1": 0, "period2": 4_000_000_000, "interval": "1d", "events": "div,split"},
        timeout=timeout,
    )
    if r.status_code != 200:
        raise ErrorMercadoLargo(f"El proveedor respondió HTTP {r.status_code} para {ticker}")
    if r.text.lstrip().startswith("<"):
        raise ErrorMercadoLargo("El proveedor devolvió HTML en vez de JSON (¿muro de verificación?)")
    try:
        res = r.json()["chart"]["result"][0]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ErrorMercadoLargo(f"Respuesta ilegible del proveedor para {ticker}: {exc}") from exc

    fechas = pd.to_datetime(res.get("timestamp") or [], unit="s").normalize()
    cotizacion = res["indicators"]["quote"][0]
    ajustado = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    precios = pd.DataFrame(
        {
            "fecha": fechas,
            "cierre_proveedor": pd.to_numeric(pd.Series(cotizacion.get("close")), errors="coerce").values,
            "ajustado_proveedor": pd.to_numeric(pd.Series(ajustado), errors="coerce").values
            if ajustado is not None else float("nan"),
        }
    )
    precios = precios.dropna(subset=["cierre_proveedor"])
    precios = precios[precios["cierre_proveedor"] > 0]
    # El proveedor a veces repite la última sesión con marca de hora distinta.
    precios = precios.drop_duplicates("fecha", keep="last").sort_values("fecha").reset_index(drop=True)

    eventos_crudos = res.get("events") or {}
    dividendos = pd.DataFrame(
        [
            {"fecha_ex": pd.to_datetime(d["date"], unit="s").normalize(), "monto_proveedor": float(d["amount"])}
            for d in (eventos_crudos.get("dividends") or {}).values()
            if d.get("amount") and float(d["amount"]) > 0
        ],
        columns=["fecha_ex", "monto_proveedor"],
    ).drop_duplicates("fecha_ex").sort_values("fecha_ex").reset_index(drop=True)

    eventos = sorted(
        (
            pd.to_datetime(s["date"], unit="s").date(),
            float(s["numerator"]) / float(s["denominator"]),
        )
        for s in (eventos_crudos.get("splits") or {}).values()
    )
    primera = res.get("meta", {}).get("firstTradeDate")
    return CrudoProveedor(
        ticker=ticker.upper(),
        precios=precios,
        dividendos=dividendos,
        eventos=eventos,
        primera_cotizacion=pd.to_datetime(primera, unit="s").date() if primera else None,
    )


# --------------------------------------------------------------------------------------
# Desajuste
# --------------------------------------------------------------------------------------


def conciliar_eventos(
    ticker: str, reportados: list[tuple[dt.date, float]]
) -> tuple[EventoDeCapital, ...]:
    """Empareja lo que reporta el proveedor con el catálogo, o se niega.

    Se tolera un par de días de diferencia en la fecha —el proveedor fecha el
    evento en la primera sesión ajustada— y medio punto en el factor, que es
    redondeo del proveedor y no otro evento.
    """
    catalogo = EVENTOS_DE_CAPITAL.get(ticker.upper(), ())
    usados: list[EventoDeCapital] = []
    for fecha, factor in reportados:
        pareja = next(
            (
                e for e in catalogo
                if abs((e.fecha - fecha).days) <= 3 and abs(e.factor / factor - 1) <= 0.005
            ),
            None,
        )
        if pareja is None:
            raise ErrorMercadoLargo(
                f"El proveedor reporta para {ticker} un evento de capital el {fecha} con factor "
                f"{factor:.4f} que no está en el catálogo. No se sabe si es un split —cambió el "
                "número de acciones— o una escisión —se repartió valor—, y cada uno se deshace "
                "distinto. Verifícalo en los reportes del emisor y agrégalo a EVENTOS_DE_CAPITAL."
            )
        usados.append(pareja)
    faltan = [e for e in catalogo if e not in usados]
    if faltan:
        raise ErrorMercadoLargo(
            f"El catálogo de {ticker} declara eventos que el proveedor no reporta: "
            f"{[str(e.fecha) for e in faltan]}. Si el proveedor dejó de ajustar por ellos, "
            "aplicarlos de todos modos duplicaría la corrección."
        )
    return tuple(sorted(usados, key=lambda e: e.fecha))


def _factor_posterior(fechas: pd.Series, eventos: tuple[EventoDeCapital, ...], tipos: tuple[str, ...]) -> pd.Series:
    """Producto de los factores de los eventos POSTERIORES a cada fecha."""
    factor = pd.Series(1.0, index=fechas.index)
    for e in eventos:
        if e.tipo in tipos:
            factor = factor.where(fechas >= pd.Timestamp(e.fecha), factor * e.factor)
    return factor


def desajustar(crudo: CrudoProveedor) -> tuple[pd.DataFrame, pd.DataFrame, tuple[EventoDeCapital, ...]]:
    """Lleva precio y dividendos del proveedor a las dos bases del módulo."""
    eventos = conciliar_eventos(crudo.ticker, crudo.eventos)

    p = crudo.precios.copy()
    todos = _factor_posterior(p["fecha"], eventos, SPLITS_DE_TIPO)
    escision = _factor_posterior(p["fecha"], eventos, ("escision",))
    p["cierre_crudo"] = p["cierre_proveedor"] * todos
    p["cierre_base"] = p["cierre_proveedor"] * escision

    d = crudo.dividendos.copy()
    todos_d = _factor_posterior(d["fecha_ex"], eventos, SPLITS_DE_TIPO)
    escision_d = _factor_posterior(d["fecha_ex"], eventos, ("escision",))
    d["monto_pagado"] = d["monto_proveedor"] * todos_d
    d["monto_base"] = d["monto_proveedor"] * escision_d
    return p, d, eventos


# --------------------------------------------------------------------------------------
# Validación
# --------------------------------------------------------------------------------------


# Holgura para que un cierre quepa en el rango trimestral publicado. Los precios de
# los noventa cotizaban en octavos y el proveedor los guarda en flotante: 1/8 de
# dólar sobre 12 es 1%, así que medio punto porcentual no deja pasar un precio
# ajustado por dividendos —que en 1992 estaría 60% abajo— y sí el redondeo.
TOLERANCIA_RANGO = 0.005


@dataclass
class Validacion:
    traslape_n: int
    traslape_error_max: float | None
    traslape_error_medio: float | None
    anclas: list[dict]
    dividendos_traslape_n: int
    dividendos_error_max: float | None
    rangos_n: int = 0
    rangos_fuera: list[dict] = field(default_factory=list)
    rangos_aceptados: list[dict] = field(default_factory=list)
    anclas_aceptadas: list[dict] = field(default_factory=list)

    @property
    def aprobada(self) -> bool:
        errores = [self.traslape_error_max, self.dividendos_error_max,
                   *(a["error"] for a in self.anclas)]
        return self.traslape_n > 0 and not self.rangos_fuera and all(
            e is None or abs(e) <= TOLERANCIA_TRASLAPE for e in errores
        )


def anclas_del_estudio(
    ticker: str, anclas_base: pd.DataFrame | None = None, raiz: Path | None = None
) -> pd.DataFrame:
    """Las anclas de la base más las de la historia larga, en un solo formato."""
    a = anclas_largas(ticker, raiz)
    largas = pd.DataFrame({"fecha_dato": pd.to_datetime(a["fecha"]).dt.date,
                           "cierre_crudo": a["cierre"].astype(float), "fuente": a["fuente"]})
    partes = [p for p in (anclas_base, largas) if p is not None and not p.empty]
    if not partes:
        return largas
    todas = pd.concat([p[["fecha_dato", "cierre_crudo", "fuente"]] for p in partes], ignore_index=True)
    todas["fecha_dato"] = pd.to_datetime(todas["fecha_dato"]).dt.date
    return todas.sort_values("fecha_dato").reset_index(drop=True)


def _fuera_de_rango(
    serie: pd.Series, rangos: tuple[RangoTrimestral, ...], excepciones: dict[str, str]
) -> tuple[int, list[dict], list[dict]]:
    """Trimestres con cierres fuera del rango publicado: los que fallan y los aceptados."""
    revisados, fuera, aceptados = 0, [], []
    for r in rangos:
        periodo = pd.Period(year=r.anio, quarter=r.trimestre, freq="Q")
        del_trimestre = serie[(serie.index >= periodo.start_time) & (serie.index <= periodo.end_time)]
        if del_trimestre.empty:
            continue
        revisados += 1
        alto, bajo = float(del_trimestre.max()), float(del_trimestre.min())
        if alto > r.maximo * (1 + TOLERANCIA_RANGO) or bajo < r.minimo * (1 - TOLERANCIA_RANGO):
            clave = f"{r.anio}-T{r.trimestre}"
            caso = {"trimestre": clave, "maximo": r.maximo, "minimo": r.minimo,
                    "cierre_max": alto, "cierre_min": bajo}
            if clave in excepciones:
                aceptados.append({**caso, "explicacion": excepciones[clave]})
            else:
                fuera.append(caso)
    return revisados, fuera, aceptados


def validar(
    precios: pd.DataFrame,
    dividendos: pd.DataFrame,
    *,
    crudo_diario: pd.Series,
    dividendos_diarios: pd.DataFrame,
    anclas: pd.DataFrame,
    rangos: tuple[RangoTrimestral, ...] = (),
    excepciones: dict[str, str] | None = None,
    excepciones_anclas: dict[str, str] | None = None,
) -> Validacion:
    """Compara contra cosas que no dependen de este proveedor.

    1. El cierre crudo del proveedor diario, día por día, en todo el traslape.
    2. Las anclas NYSE: las de la base (P2) y las de la historia larga.
    3. Los dividendos del proveedor diario, por fecha ex.
    4. Los rangos trimestrales que publicó el emisor, donde no hay traslape: todo
       cierre del trimestre tiene que caber entre su mínimo y su máximo.
    """
    serie = precios.set_index("fecha")["cierre_crudo"]
    otra = crudo_diario.copy()
    otra.index = pd.to_datetime(otra.index).normalize()
    comun = serie.to_frame("largo").join(otra.rename("diario"), how="inner").dropna()
    err = comun["largo"] / comun["diario"] - 1 if not comun.empty else pd.Series(dtype=float)

    resultados_anclas, anclas_aceptadas = [], []
    for _, a in anclas.iterrows():
        f = pd.Timestamp(a["fecha_dato"]).normalize()
        if f in serie.index:
            real = float(a["cierre_crudo"])
            caso = {"fecha": str(f.date()), "real": real, "reconstruido": float(serie.loc[f]),
                    "error": float(serie.loc[f] / real - 1)}
            explicacion = (excepciones_anclas or {}).get(caso["fecha"])
            if explicacion and abs(caso["error"]) > TOLERANCIA_TRASLAPE:
                anclas_aceptadas.append({**caso, "explicacion": explicacion})
            else:
                resultados_anclas.append(caso)

    d_err_max = None
    d_n = 0
    if not dividendos_diarios.empty:
        dd = dividendos_diarios.copy()
        dd["fecha_ex"] = pd.to_datetime(dd["fecha_ex"]).dt.normalize()
        m = dividendos.merge(dd[["fecha_ex", "monto"]], on="fecha_ex", how="inner")
        d_n = len(m)
        if d_n:
            d_err_max = float((m["monto_pagado"] / m["monto"] - 1).abs().max())

    rangos_n, rangos_fuera, rangos_aceptados = _fuera_de_rango(serie, rangos, excepciones or {})
    return Validacion(
        traslape_n=int(len(comun)),
        traslape_error_max=float(err.abs().max()) if len(err) else None,
        traslape_error_medio=float(err.mean()) if len(err) else None,
        anclas=resultados_anclas,
        dividendos_traslape_n=d_n,
        dividendos_error_max=d_err_max,
        rangos_n=rangos_n,
        rangos_fuera=rangos_fuera,
        rangos_aceptados=rangos_aceptados,
        anclas_aceptadas=anclas_aceptadas,
    )


# --------------------------------------------------------------------------------------
# Almacén versionado
# --------------------------------------------------------------------------------------


def dir_de(ticker: str, raiz: Path | None = None) -> Path:
    return (raiz or DIR_ESTUDIOS) / ticker.upper()


def guardar(
    ticker: str,
    precios: pd.DataFrame,
    dividendos: pd.DataFrame,
    eventos: tuple[EventoDeCapital, ...],
    validacion: Validacion,
    *,
    primera_cotizacion: dt.date | None,
    correcciones: list[str] | None = None,
    inicio: InicioVerificable | None = None,
    raiz: Path | None = None,
) -> Path:
    if not validacion.aprobada:
        raise ErrorMercadoLargo(
            f"La historia larga de {ticker} no pasó la validación y no se guarda: {asdict(validacion)}"
        )
    destino = dir_de(ticker, raiz)
    destino.mkdir(parents=True, exist_ok=True)
    precios[["fecha", "cierre_proveedor", "cierre_crudo", "cierre_base", "ajustado_proveedor"]].to_csv(
        destino / ARCHIVO_PRECIOS, index=False, float_format="%.6f", compression="gzip"
    )
    if "tipo" not in dividendos:
        dividendos = dividendos.assign(tipo="regular")
    dividendos[["fecha_ex", "monto_proveedor", "monto_pagado", "monto_base", "tipo"]].to_csv(
        destino / ARCHIVO_DIVIDENDOS, index=False, float_format="%.6f", compression="gzip"
    )
    manifiesto = {
        "ticker": ticker.upper(),
        "fuente": FUENTE_LARGA,
        "descargado_en": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "primera_cotizacion": str(primera_cotizacion) if primera_cotizacion else None,
        "inicio_verificable": {"fecha": str(inicio.fecha), "motivo": inicio.motivo} if inicio else None,
        "precios": {"n": int(len(precios)), "desde": str(precios["fecha"].min().date()),
                    "hasta": str(precios["fecha"].max().date())},
        "dividendos": {"n": int(len(dividendos)), "desde": str(dividendos["fecha_ex"].min().date()),
                       "hasta": str(dividendos["fecha_ex"].max().date())},
        "eventos": [{**asdict(e), "fecha": str(e.fecha)} for e in eventos],
        "correcciones_de_dividendos": correcciones or [],
        "validacion": asdict(validacion),
    }
    (destino / ARCHIVO_MANIFIESTO).write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return destino


@dataclass
class HistoriaMercado:
    """Precio y dividendos listos para el estudio, ya empalmados con lo diario."""

    ticker: str
    precios: pd.DataFrame      # índice fecha; cierre_crudo, cierre_base
    dividendos: pd.DataFrame   # fecha_ex, monto_pagado, monto_base, tipo
    eventos: tuple[EventoDeCapital, ...]
    manifiesto: dict
    dias_empalmados: int = 0

    @property
    def escisiones(self) -> tuple[EventoDeCapital, ...]:
        return tuple(e for e in self.eventos if e.tipo == "escision")

    @property
    def splits(self) -> tuple[EventoDeCapital, ...]:
        return tuple(e for e in self.eventos if e.tipo == "split")

    @property
    def inicio_verificable(self) -> dict | None:
        """Si la serie se cortó después del listado: desde cuándo y por qué."""
        return self.manifiesto.get("inicio_verificable")


def pagos_por_anio(dividendos: pd.DataFrame) -> int:
    """Frecuencia del dividendo regular, medida y no supuesta: 12, 4, 2 o 1."""
    r = dividendos[dividendos.get("tipo", "regular") == "regular"]["fecha_ex"].sort_values()
    if len(r) < 3:
        return 4
    brecha = float(r.diff().dt.days.iloc[-12:].median())
    return min((12, 4, 2, 1), key=lambda n: abs(365 / n - brecha))


def dividendo_ttm(
    dividendos: pd.DataFrame, fechas: pd.DatetimeIndex, *, columna: str = "monto_base"
) -> pd.Series:
    """Los N pagos REGULARES más recientes a cada fecha, con N = pagos por año.

    Por conteo y no por calendario, a propósito. Una ventana de 365 días se rompe
    cada vez que la fecha ex cambia de lado del fin de mes, y para O pasó en mayo
    de 2024: con la liquidación T+1 la fecha ex brincó del último día hábil del
    mes al primero del siguiente, mayo quedó sin fecha ex, 2024 tuvo once y 2025
    trece. Los pagos reales no cambiaron; una suma por calendario dibuja un
    recorte de 8% y luego un aumento de 21% que nunca ocurrieron.

    Las distribuciones especiales no entran: no se repiten, y meterlas al yield lo
    infla durante un año entero.
    """
    r = dividendos[dividendos["tipo"] == "regular"].sort_values("fecha_ex")
    n = pagos_por_anio(dividendos)
    if len(r) < n:
        return pd.Series(float("nan"), index=fechas)
    acumulado = r[columna].cumsum().to_numpy()
    posiciones = r["fecha_ex"].searchsorted(fechas, side="right") - 1
    salida = []
    for pos in posiciones:
        if pos < n - 1:
            salida.append(float("nan"))
        else:
            previo = acumulado[pos - n] if pos - n >= 0 else 0.0
            salida.append(float(acumulado[pos] - previo))
    return pd.Series(salida, index=fechas)


def dividendo_anualizado(dividendos: pd.DataFrame, fechas: pd.DatetimeIndex, *, columna: str = "monto_base") -> pd.Series:
    """La última mensualidad regular × pagos por año: lo que paga HOY la acción."""
    r = dividendos[dividendos["tipo"] == "regular"].sort_values("fecha_ex")
    n = pagos_por_anio(dividendos)
    posiciones = r["fecha_ex"].searchsorted(fechas, side="right") - 1
    valores = r[columna].to_numpy()
    return pd.Series([float(valores[p]) * n if p >= 0 else float("nan") for p in posiciones], index=fechas)


def hay_historia(ticker: str, raiz: Path | None = None) -> bool:
    return (dir_de(ticker, raiz) / ARCHIVO_MANIFIESTO).exists()


def hay_estudio(ticker: str, raiz: Path | None = None) -> bool:
    """Historia de mercado Y cifras primarias capturadas del documento del emisor.

    Sin las primarias, el FFO saldría solo de lo que la base leyó de los 8-K, y en
    NNN esa lectura trae −1.00 y trimestres guardados como años. Un estudio sin
    cifras verificadas no se ofrece.
    """
    return hay_historia(ticker, raiz) and (dir_de(ticker, raiz) / "anuales_primarios.csv").exists()


def cargar(
    ticker: str,
    *,
    asof: dt.date,
    crudo_diario: pd.Series | None = None,
    dividendos_diarios: pd.DataFrame | None = None,
    raiz: Path | None = None,
) -> HistoriaMercado:
    """Lee el archivo versionado y le pega la cola diaria de la base.

    El archivo es una foto al día de su descarga; lo que pasó después viene de la
    base, que se refresca a diario. Las dos series son precio CRUDO, así que se
    pegan sin conversión — y solo después del último día del archivo, para que un
    día nunca tenga dos precios.

    Todo se corta en ``asof`` (P1): el estudio no ve precios de después del corte.
    """
    origen = dir_de(ticker, raiz)
    manifiesto = json.loads((origen / ARCHIVO_MANIFIESTO).read_text(encoding="utf-8"))
    eventos = tuple(
        EventoDeCapital(**{**e, "fecha": dt.date.fromisoformat(e["fecha"])})
        for e in manifiesto.get("eventos", [])
    )
    p = pd.read_csv(origen / ARCHIVO_PRECIOS, parse_dates=["fecha"])
    d = pd.read_csv(origen / ARCHIVO_DIVIDENDOS, parse_dates=["fecha_ex"])
    d["tipo"] = d["tipo"].fillna("regular") if "tipo" in d else "regular"
    ultimo = p["fecha"].max()

    empalmados = 0
    if crudo_diario is not None and not crudo_diario.empty:
        cola = crudo_diario.copy()
        cola.index = pd.to_datetime(cola.index).normalize()
        cola = cola[cola.index > ultimo]
        if not cola.empty:
            # Después del último evento del catálogo las dos bases coinciden; un
            # evento nuevo posterior al archivo lo detecta la próxima descarga.
            extra = pd.DataFrame({"fecha": cola.index, "cierre_crudo": cola.values,
                                  "cierre_base": cola.values})
            p = pd.concat([p, extra], ignore_index=True)
            empalmados = len(extra)
    if dividendos_diarios is not None and not dividendos_diarios.empty:
        dd = dividendos_diarios.copy()
        dd["fecha_ex"] = pd.to_datetime(dd["fecha_ex"]).dt.normalize()
        dd = dd[dd["fecha_ex"] > d["fecha_ex"].max()]
        if not dd.empty:
            d = pd.concat(
                [d, pd.DataFrame({"fecha_ex": dd["fecha_ex"], "monto_pagado": dd["monto"],
                                  "monto_base": dd["monto"], "tipo": "regular"})],
                ignore_index=True,
            )

    corte = pd.Timestamp(asof)
    p = p[p["fecha"] <= corte].sort_values("fecha").set_index("fecha")
    d = d[d["fecha_ex"] <= corte].sort_values("fecha_ex").reset_index(drop=True)
    return HistoriaMercado(
        ticker=ticker.upper(),
        precios=p[["cierre_crudo", "cierre_base"]],
        dividendos=d[["fecha_ex", "monto_pagado", "monto_base", "tipo"]],
        eventos=eventos,
        manifiesto=manifiesto,
        dias_empalmados=empalmados,
    )
