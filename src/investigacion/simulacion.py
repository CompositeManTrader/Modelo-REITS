"""El simulador de la investigación: aportar cada mes a un activo riesgoso con una regla.

Una sola máquina para todo lo que se compare en las fases 3 a 8, así que dos reglas
nunca difieren por la contabilidad.

Cada fin de mes ``t``:

1. El activo rinde el mes: su valor cambia con el retorno de precio y paga el retorno de
   ingreso como dividendo, del que se retiene 20% (P2: el dividendo es efectivo, no
   precio). El efectivo rinde la tasa del mes, menos 20% de impuesto.
2. Llega la aportación del mes.
3. Se aplica la exposición decidida con lo conocido en ``t`` (``e[t]``; con ``rezago`` 1,
   la de ``t − 1``). Dos maneras de aplicarla:

   * ``Modo.APORTACION`` — nunca se vende. Del dinero disponible (la aportación, los
     dividendos netos y la reserva) se compra activo por la fracción ``e[t]``; el resto
     espera en efectivo. Con ``e = 1`` siempre, es aportar sin reglas: el benchmark (P6).
   * ``Modo.EXPOSICION`` — se rebalancea toda la riqueza a ``e[t]`` en el activo. Vender
     paga 10% sobre la ganancia (costo promedio); una pérdida se acumula y compensa
     ganancias posteriores.

Cada compra y cada venta paga la comisión. Al final se vende todo, con su comisión y su
impuesto, y la TIR es money-weighted (P9) sobre las aportaciones y ese valor final.

La caída máxima se mide sobre el retorno ponderado en el tiempo de la cartera, no sobre
la riqueza: con aportaciones la riqueza casi nunca cae, aunque la cartera sí.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
import pandas as pd

from src.investigacion.diseno import OBJETIVO, Objetivo
from src.portafolio.metricas import tir


class Modo(StrEnum):
    APORTACION = "aportacion"
    EXPOSICION = "exposicion"


@dataclass(frozen=True)
class Mercado:
    """Los insumos mensuales, alineados: el retorno del mes ``t`` ocurre entre ``t − 1`` y ``t``."""

    fechas: pd.DatetimeIndex
    retorno_precio: np.ndarray
    retorno_ingreso: np.ndarray
    tasa_efectivo: np.ndarray

    def __post_init__(self) -> None:
        n = len(self.fechas)
        for nombre in ("retorno_precio", "retorno_ingreso", "tasa_efectivo"):
            v = np.asarray(getattr(self, nombre), dtype=float)
            if len(v) != n:
                raise ValueError(f"{nombre} tiene {len(v)} meses y las fechas {n}")
            object.__setattr__(self, nombre, v)

    @property
    def retorno_total(self) -> np.ndarray:
        return self.retorno_precio + self.retorno_ingreso

    def tramo(self, desde: pd.Timestamp | None = None, hasta: pd.Timestamp | None = None) -> Mercado:
        sel = np.ones(len(self.fechas), dtype=bool)
        if desde is not None:
            sel &= self.fechas >= desde
        if hasta is not None:
            sel &= self.fechas <= hasta
        return Mercado(self.fechas[sel], self.retorno_precio[sel], self.retorno_ingreso[sel], self.tasa_efectivo[sel])


@dataclass
class Resultado:
    tir: float
    aportado: float
    valor_final: float
    exposicion_promedio: float
    caida_maxima: float
    cambios: int
    impuestos: float
    comisiones: float
    mensual: pd.DataFrame = field(repr=False)


def simular(m: Mercado, exposicion: np.ndarray | pd.Series | float = 1.0, *, modo: Modo | str = Modo.APORTACION,
            objetivo: Objetivo = OBJETIVO, rezago: int = 0, multiplicador_de_costos: float = 1.0,
            aportaciones: np.ndarray | None = None) -> Resultado:
    """Simula la regla. ``exposicion`` es la fracción decidida al cierre de cada mes, en [0, 1]."""
    modo = Modo(modo)
    n = len(m.fechas)
    if n < 2:
        raise ValueError("Hacen falta al menos dos meses.")
    e = np.broadcast_to(np.asarray(exposicion, dtype=float), (n,)).copy()
    if np.isnan(e).any():
        raise ValueError("La exposición tiene meses sin decisión: la regla debe decir algo cada mes.")
    e = np.clip(e, objetivo.exposicion_minima, objetivo.exposicion_maxima)
    if rezago:
        # Decidir con lo de un mes y ejecutar al siguiente; el primer mes, sin decisión previa, no compra.
        e = np.concatenate([np.zeros(rezago), e[:-rezago]])
    c = np.full(n, objetivo.aportacion_mensual) if aportaciones is None else np.asarray(aportaciones, float)
    c = c.copy()
    c[-1] = 0.0    # el último mes solo se liquida
    comision = objetivo.comision * multiplicador_de_costos
    td, ti, tg = objetivo.impuesto_dividendo, objetivo.impuesto_intereses, objetivo.impuesto_ganancia

    activo = base = efectivo = 0.0
    perdida_acumulada = impuestos = comisiones = 0.0
    filas = []
    riqueza_previa = None
    for t in range(n):
        dividendo = interes = 0.0
        if t > 0:
            bruto = activo * m.retorno_ingreso[t]
            dividendo = bruto * (1 - td)
            impuestos += bruto * td
            activo *= 1 + m.retorno_precio[t]
            bruto_i = efectivo * m.tasa_efectivo[t]
            interes = bruto_i * (1 - ti)
            impuestos += bruto_i * ti
            efectivo += interes
        riqueza_antes = activo + efectivo + dividendo
        retorno_cartera = riqueza_antes / riqueza_previa - 1 if riqueza_previa else np.nan
        efectivo += dividendo + c[t]

        def comprar(monto: float) -> None:
            nonlocal activo, base, efectivo, comisiones
            if monto <= 0:
                return
            costo = monto * comision
            activo += monto - costo
            base += monto
            efectivo -= monto
            comisiones += costo

        def vender(monto: float) -> None:
            nonlocal activo, base, efectivo, comisiones, impuestos, perdida_acumulada
            if monto <= 0 or activo <= 0:
                return
            monto = min(monto, activo)
            fraccion = monto / activo
            base_vendida = base * fraccion
            costo = monto * comision
            ganancia = monto - costo - base_vendida
            if ganancia > 0:
                gravable = max(0.0, ganancia - perdida_acumulada)
                perdida_acumulada = max(0.0, perdida_acumulada - ganancia)
                impuesto = gravable * tg
            else:
                perdida_acumulada += -ganancia
                impuesto = 0.0
            activo -= monto
            base -= base_vendida
            efectivo += monto - costo - impuesto
            comisiones += costo
            impuestos += impuesto

        if t < n - 1:
            if modo is Modo.APORTACION:
                comprar(e[t] * efectivo)
            else:
                riqueza = activo + efectivo
                meta = e[t] * riqueza
                if activo < meta:
                    comprar(min(meta - activo, efectivo))
                elif activo > meta:
                    vender(activo - meta)
        else:
            vender(activo)
        riqueza_previa = activo + efectivo
        filas.append({"fecha": m.fechas[t], "aportacion": c[t], "activo": activo, "efectivo": efectivo,
                      "exposicion": activo / riqueza_previa if riqueza_previa > 0 else np.nan,
                      "retorno_cartera": retorno_cartera})

    mensual = pd.DataFrame(filas).set_index("fecha")
    flujos = pd.Series(-c, index=m.fechas)
    flujos.iloc[-1] += activo + efectivo
    rc = mensual["retorno_cartera"].dropna()
    acumulado = (1 + rc).cumprod()
    caida = float((acumulado / acumulado.cummax() - 1).min()) if len(acumulado) else np.nan
    decision = e[:-1]
    return Resultado(tir=tir(flujos) or np.nan, aportado=float(c.sum()), valor_final=float(activo + efectivo),
                     exposicion_promedio=float(mensual["exposicion"].iloc[:-1].mean()), caida_maxima=caida,
                     cambios=int((np.diff(decision) != 0).sum()), impuestos=impuestos, comisiones=comisiones,
                     mensual=mensual)


def benchmark(m: Mercado, **kw) -> Resultado:
    """Aportar siempre todo al activo (P6)."""
    return simular(m, 1.0, modo=Modo.APORTACION, **kw)
