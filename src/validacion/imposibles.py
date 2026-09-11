"""Valores que no pueden ser lo que dicen ser.

El problema
===========
Un hecho puede venir de la fuente primaria, con su etiqueta estándar y su filing
detrás, y aun así ser imposible. No mal medido: **imposible**, en el sentido de
que ninguna emisora en operación pudo haber tenido ese número.

La deuda total de Prologis al cierre de 2021 vale 17,715 millones en cinco
filings consecutivos. En el sexto, publicado dos años después, vale 215. La
cifra es real —está impresa en un documento de la SEC— pero no es la deuda
total: es un instrumento suelto que cayó en la misma cadena de etiquetas. Como
el modelo toma la versión publicada más reciente, que es lo correcto para una
reexpresión, esa cifra desplaza a cinco observaciones que concuerdan entre sí.

Por qué no lo caza el detector de escala
========================================
``escala.py`` busca potencias limpias de mil, porque el error que persigue es
otro: la emisora etiquetó la cifra impresa —«en miles»— sin volverla a dólares.
Aquí los factores son 82x, 22x y 6x. No son potencias de mil y no deben serlo:
esto no es un cambio de unidad, es otra partida.

Los dos defectos que se persiguen
=================================

**1. Un saldo estructural que se hunde un corte y regresa.** Un FLUJO puede
brincar: una venta grande, un trimestre malo, un cargo extraordinario. Un SALDO
no. La deuda total no desaparece en diciembre y reaparece en marzo.

Lo que hace verificable la regla es exigir que **los vecinos concuerden entre
sí**. Un desapalancamiento de verdad mueve el saldo y lo DEJA movido, así que el
corte de antes y el de después no concuerdan, y no se marca nada. Solo se acusa
la forma de hundimiento aislado, que es la que ningún balance puede tener.

Y se limita a los totales ESTRUCTURALES a propósito. El efectivo se mueve tres
veces entre trimestres sin que nada esté mal; «otros pasivos» es un residuo y es
lumpy por construcción; la escalera de vencimientos cambia por diseño, porque lo
que este trimestre vence en el año 3 el siguiente vence en el año 2. En esos la
suavidad no es una propiedad del dato y exigirla marcaría datos buenos. En un
total del balance sí lo es.

**2. Un gasto negativo.** El gasto por intereses de Agree Realty aparece en
−1,071,858 en tres trimestres de 2011, y positivo desde 2012: los filings de
2012 lo etiquetaron con el signo de una deducción. Un gasto negativo no es un
gasto chico, es un signo al revés, y produce un costo implícito de la deuda de
−46.6%.

Esta regla ya existía en un solo lugar —``_derivar_ebitdare`` exige
``intereses > 0`` antes de emitir nada— y ahí protegía al apalancamiento. Lo que
no protegía era todo lo demás que divide entre los mismos intereses.

Por qué se marca y no se corrige
================================
Igual que en ``escala.py``: se marca la versión como ``SOSPECHOSA`` y no se
escribe una corregida. ``Repositorio.hechos`` filtra por estado ANTES de elegir
la versión vigente, así que la celda cae sola a la versión anterior —que es una
observación de verdad— cuando existe, y queda vacía cuando no. Un hueco es
honesto; una cifra inventada con formato de dato, no.

El estado NO es point-in-time
=============================
``estado`` describe la calidad de un registro, no lo que se sabía en una fecha.
Marcar no devuelve información del futuro: retira una que no debió existir.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

# Los totales del balance donde la suavidad SÍ es una propiedad del dato. Ver el
# encabezado: el efectivo, los residuales y la escalera de vencimientos se mueven
# así de forma legítima, y exigirles suavidad marcaría datos buenos.
SALDOS_ESTRUCTURALES: tuple[str, ...] = (
    "deuda_total",
    "activos_totales",
    "pasivos_totales",
    "capital_total",
    "inmuebles_brutos",
    "inmuebles_netos",
)

# Cuántos cortes de cada lado forman la referencia.
VECINOS = 2

# Qué tan parecidos tienen que ser los vecinos ENTRE SÍ para poder acusar. Es la
# condición que separa un hundimiento de un cambio real: un desapalancamiento
# deja a los vecinos en niveles distintos y no se marca.
TOLERANCIA_VECINOS = 0.25

# Cuánto tiene que apartarse el corte de sus vecinos. Sesenta por ciento es más
# de lo que mueve cualquier trimestre de financiamiento y menos que cualquiera de
# los tres casos reales del universo, que van de 6x a 82x.
FACTOR_HUNDIMIENTO = 1.6

# Los conceptos que son un GASTO y por tanto no pueden ser negativos. La lista es
# corta a propósito: solo los que alimentan un ratio del modelo. Un gasto
# negativo en un renglón que nadie divide es feo, no peligroso.
GASTOS: tuple[str, ...] = (
    "gasto_intereses",
    "depreciacion_amortizacion",
)


@dataclass(frozen=True)
class Imposible:
    """Un hecho que no puede ser lo que dice ser, con la razón por la que no."""

    id: int
    ticker: str
    concepto: str
    periodo_tipo: str
    fecha_dato: dt.date
    fecha_publicacion: dt.date
    valor: float
    motivo: str          # "saldo" | "gasto_negativo"
    referencia: float    # el nivel de los vecinos, o 0 para un gasto negativo

    def nota(self) -> str:
        if self.motivo == "gasto_negativo":
            return (
                f"Imposible: «{self.concepto}» es un GASTO y vale "
                f"{self.valor:,.0f}. Un gasto negativo no es un gasto chico: es "
                f"un signo al revés, y entra a los ratios que dividen entre él "
                f"como si fuera un número. No se corrige el signo —sería una "
                f"cifra que no aparece en ningún filing—: se descarta esta "
                f"versión y queda vigente la anterior, si la hay."
            )
        razon = (
            max(abs(self.valor), self.referencia) / min(abs(self.valor), self.referencia)
            if self.valor and self.referencia else float("inf")
        )
        return (
            f"Imposible: «{self.concepto}» vale {self.valor:,.0f} donde sus cortes "
            f"vecinos valen {self.referencia:,.0f} —{razon:,.0f} veces— y esos "
            f"vecinos concuerdan entre sí. Un saldo del balance no se hunde un "
            f"trimestre y regresa: un cambio real lo dejaría movido. La cifra "
            f"está impresa en un filing, pero no es este renglón: es una partida "
            f"suelta que cayó en la misma cadena de etiquetas. No se corrige el "
            f"número: se descarta esta versión y queda vigente la anterior, si la hay."
        )


def _hundimientos(hechos: pd.DataFrame) -> list[Imposible]:
    """Saldos estructurales que se apartan de unos vecinos que sí concuerdan."""
    hallazgos: list[Imposible] = []
    puntuales = hechos[hechos["periodo_tipo"] == "PUNTUAL"]
    if puntuales.empty:
        return hallazgos
    for concepto, serie in puntuales.groupby("concepto"):
        if concepto not in SALDOS_ESTRUCTURALES:
            continue
        serie = serie.sort_values("fecha_dato").reset_index(drop=True)
        if len(serie) < 2 * VECINOS + 1:
            continue
        valores = serie["valor"].astype(float).abs().to_numpy()
        for i in range(VECINOS, len(valores) - VECINOS):
            lado = np.concatenate([valores[i - VECINOS:i], valores[i + 1:i + 1 + VECINOS]])
            if lado.min() <= 0:
                continue
            referencia = float(np.median(lado))
            # Los vecinos tienen que concordar ENTRE SÍ; si no, el que se mueve
            # es la serie y no el corte.
            if (lado.max() - lado.min()) / referencia > TOLERANCIA_VECINOS:
                continue
            valor = float(valores[i])
            if valor <= 0:
                continue
            if max(valor / referencia, referencia / valor) < FACTOR_HUNDIMIENTO:
                continue
            fila = serie.loc[i]
            hallazgos.append(Imposible(
                id=int(fila["id"]), ticker=str(fila["ticker"]), concepto=str(concepto),
                periodo_tipo="PUNTUAL",
                fecha_dato=pd.Timestamp(fila["fecha_dato"]).date(),
                fecha_publicacion=pd.Timestamp(fila["fecha_publicacion"]).date(),
                valor=float(fila["valor"]), motivo="saldo", referencia=referencia,
            ))
    return hallazgos


def _gastos_negativos(hechos: pd.DataFrame) -> list[Imposible]:
    """Renglones de gasto con signo de ingreso."""
    sub = hechos[hechos["concepto"].isin(GASTOS) & (hechos["valor"] < 0)]
    return [
        Imposible(
            id=int(f["id"]), ticker=str(f["ticker"]), concepto=str(f["concepto"]),
            periodo_tipo=str(f["periodo_tipo"]),
            fecha_dato=pd.Timestamp(f["fecha_dato"]).date(),
            fecha_publicacion=pd.Timestamp(f["fecha_publicacion"]).date(),
            valor=float(f["valor"]), motivo="gasto_negativo", referencia=0.0,
        )
        for _, f in sub.iterrows()
    ]


def detectar_imposibles(hechos: pd.DataFrame) -> list[Imposible]:
    """Los hechos que no pueden ser lo que dicen ser.

    ``hechos`` tiene que traer la versión VIGENTE de cada celda —no todas las
    versiones—, al revés que ``escala.py``. La diferencia no es un detalle: aquí
    la evidencia es la SERIE, y una serie armada con todas las versiones tiene
    varios valores por corte y ya no es una serie.
    """
    if hechos is None or hechos.empty:
        return []
    h = hechos[hechos["valor"].notna()]
    if h.empty:
        return []
    return _hundimientos(h) + _gastos_negativos(h)


def resumir(hallazgos: list[Imposible]) -> str:
    if not hallazgos:
        return "Ningún hecho imposible."
    emisoras = sorted({h.ticker for h in hallazgos})
    saldos = sum(1 for h in hallazgos if h.motivo == "saldo")
    gastos = len(hallazgos) - saldos
    partes = []
    if saldos:
        partes.append(f"{saldos} saldo(s) hundido(s)")
    if gastos:
        partes.append(f"{gastos} gasto(s) negativo(s)")
    return f"{' y '.join(partes)} en {len(emisoras)} emisora(s): {', '.join(emisoras)}."
