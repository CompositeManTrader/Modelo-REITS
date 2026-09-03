"""Criterios de venta por deterioro (Puerta 3).

Vender por precio caro es distinto de vender por tesis rota. Esta es la única
puerta que dispara VENTA, y dispara solo con patrones sostenidos, no con un
trimestre malo:

* Payout sobre AFFO arriba de 100% dos trimestres consecutivos.
* Spread de inversión negativo dos trimestres consecutivos.
* AFFO por acción cayendo YoY dos trimestres consecutivos.
* Apalancamiento arriba de 6.5x.
* Pérdida del grado de inversión.

El requisito de dos trimestres no es cosmético: los recortes de dividendo de
W. P. Carey y Global Net Lease vinieron precedidos de varios trimestres de
deterioro medible, no de una sorpresa de un día.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import UMBRALES, UmbralesDeterioro


@dataclass
class ResultadoKill:
    dispara_venta: bool
    disparadores: list[str] = field(default_factory=list)
    criterios: pd.DataFrame = field(default_factory=pd.DataFrame)
    mensaje: str = ""


def _racha_final(condicion: pd.Series) -> int:
    """Cuántos periodos consecutivos, terminando en el último, cumple la condición."""
    if condicion.empty:
        return 0
    valores = condicion.fillna(False).to_numpy(dtype=bool)
    racha = 0
    for v in valores[::-1]:
        if not v:
            break
        racha += 1
    return racha


def evaluar_kill(
    historial: pd.DataFrame,
    *,
    umbrales: UmbralesDeterioro = UMBRALES.deterioro,
) -> ResultadoKill:
    """Evalúa los criterios de deterioro sobre el panel trimestral del emisor.

    ``historial`` debe venir ordenado por fecha ascendente, con el trimestre más
    reciente al final. Las columnas ausentes simplemente no se evalúan: es
    preferible declarar que un criterio no se pudo medir a inventarlo.
    """
    if historial is None or historial.empty:
        return ResultadoKill(
            False,
            [],
            pd.DataFrame(),
            "Sin historial suficiente para evaluar deterioro. No se dispara venta por falta de datos.",
        )

    h = historial.copy()
    if "fecha_dato" in h.columns:
        h = h.sort_values("fecha_dato")
    n = umbrales.trimestres_consecutivos

    filas: list[dict] = []
    disparadores: list[str] = []

    def evaluar(nombre: str, condicion: pd.Series | None, umbral, explicacion: str, consecutivos: bool = True):
        if condicion is None:
            filas.append(
                {
                    "criterio": nombre,
                    "racha": None,
                    "umbral": umbral,
                    "dispara": None,
                    "explicacion": f"{explicacion} (sin datos)",
                }
            )
            return
        racha = _racha_final(condicion) if consecutivos else int(bool(condicion.iloc[-1]))
        requerida = n if consecutivos else 1
        dispara = racha >= requerida
        if dispara:
            disparadores.append(nombre)
        filas.append(
            {
                "criterio": nombre,
                "racha": racha,
                "umbral": f"{requerida} trimestre(s)" if consecutivos else "inmediato",
                "dispara": dispara,
                "explicacion": explicacion,
            }
        )

    evaluar(
        f"Payout sobre AFFO > {umbrales.payout_affo_critico:.0%}",
        (h["payout_affo"] > umbrales.payout_affo_critico) if "payout_affo" in h else None,
        umbrales.payout_affo_critico,
        "El dividendo dejó de caber en el flujo. A este nivel el recorte es cuestión de tiempo.",
    )
    evaluar(
        "Spread de inversión negativo",
        (h["spread_inversion"] < 0) if "spread_inversion" in h else None,
        0.0,
        "Cada adquisición destruye valor por acción: se emite capital caro para comprar activos baratos.",
    )
    evaluar(
        "AFFO por acción cayendo YoY",
        (h["crecimiento_affo_por_accion_yoy"] < 0)
        if "crecimiento_affo_por_accion_yoy" in h
        else None,
        0.0,
        "El flujo por acción se contrae: o el negocio encoge o la dilución se lo come.",
    )
    evaluar(
        f"Deuda neta / EBITDAre > {umbrales.deuda_neta_ebitdare_max}x",
        (h["deuda_neta_ebitdare"] > umbrales.deuda_neta_ebitdare_max)
        if "deuda_neta_ebitdare" in h
        else None,
        umbrales.deuda_neta_ebitdare_max,
        "Apalancamiento que obliga a emitir acciones en el peor momento del ciclo.",
        consecutivos=False,
    )
    evaluar(
        "Pérdida del grado de inversión",
        (~h["grado_inversion"].astype(bool)) if "grado_inversion" in h else None,
        True,
        "El costo de la deuda salta justo cuando hay que refinanciar. Cambia la tesis, no el precio.",
        consecutivos=False,
    )

    criterios = pd.DataFrame(filas)
    dispara = bool(disparadores)
    if dispara:
        mensaje = (
            "VENTA por deterioro. Disparadores: " + "; ".join(disparadores) + ". "
            "Esto es tesis rota, no valuación: la posición se vende aunque el precio esté barato."
        )
    else:
        evaluados = criterios["dispara"].notna().sum()
        mensaje = (
            f"Sin deterioro: {evaluados} criterio(s) evaluados, ninguno disparado. "
            "La tesis sigue en pie."
        )
    return ResultadoKill(dispara, disparadores, criterios, mensaje)


# --------------------------------------------------------------------------------------
# Venta parcial por valuación
# --------------------------------------------------------------------------------------


@dataclass
class CostoDeRotacion:
    """Cuánto cuesta rotar y cuánta ventaja anual hace falta para recuperarlo."""

    ganancia_acumulada: float
    tasa_impuesto: float
    costo_fiscal: float
    anios_recuperacion: float
    ventaja_anual_necesaria: float
    comisiones: float = 0.0

    def como_texto(self) -> str:
        return (
            f"Con {self.ganancia_acumulada:.0%} de ganancia acumulada y tasa de "
            f"{self.tasa_impuesto:.0%}, el costo fiscal es {self.costo_fiscal:.1%} del valor. "
            f"Para recuperarlo en {self.anios_recuperacion:.0f} años, el destino tiene que "
            f"rendir {self.ventaja_anual_necesaria * 10_000:,.0f} bps más al año."
        )


def liston_de_friccion(
    ganancia_acumulada: float,
    *,
    tasa_impuesto: float = 0.10,
    anios: float = 2.0,
    comisiones: float = 0.0,
) -> CostoDeRotacion:
    """Calcula el listón que el destino debe superar para que rotar valga la pena.

    Reproduce la tabla del proyecto: 20% de ganancia cuesta 2.0% y exige 100 bps de
    ventaja anual a dos años; 100% de ganancia cuesta 10% y exige 500 bps.

    Es el cálculo que casi nadie hace antes de rotar y el que más veces evita la
    rotación. Rotar con dinero nuevo da la mayor parte del beneficio con cero costo
    fiscal y cero riesgo de reentrada.
    """
    costo_fiscal = max(0.0, float(ganancia_acumulada)) * float(tasa_impuesto) + float(comisiones)
    ventaja = costo_fiscal / anios if anios > 0 else float("inf")
    return CostoDeRotacion(
        ganancia_acumulada=float(ganancia_acumulada),
        tasa_impuesto=float(tasa_impuesto),
        costo_fiscal=costo_fiscal,
        anios_recuperacion=float(anios),
        ventaja_anual_necesaria=ventaja,
        comisiones=float(comisiones),
    )


def tabla_liston_friccion(
    ganancias: tuple[float, ...] = (0.20, 0.40, 0.60, 1.00),
    *,
    tasa_impuesto: float = 0.10,
    anios: float = 2.0,
) -> pd.DataFrame:
    """La tabla de fricción del proyecto, lista para mostrar en la interfaz."""
    filas = []
    for g in ganancias:
        c = liston_de_friccion(g, tasa_impuesto=tasa_impuesto, anios=anios)
        filas.append(
            {
                "Ganancia acumulada": g,
                f"Costo fiscal ({tasa_impuesto:.0%} cedular)": c.costo_fiscal,
                f"Ventaja anual necesaria a {anios:.0f} años (bps)": round(
                    c.ventaja_anual_necesaria * 10_000
                ),
            }
        )
    return pd.DataFrame(filas)


BRECHA_PERCENTIL_MINIMA = 0.40
"""Regla sugerida: solo rotar si la brecha de percentil supera ~40 puntos."""


@dataclass
class RecomendacionRotacion:
    conviene: bool
    brecha_percentil: float
    liston: CostoDeRotacion
    mensaje: str


def evaluar_rotacion(
    percentil_origen: float,
    percentil_destino: float,
    ganancia_acumulada: float,
    *,
    tasa_impuesto: float = 0.10,
    anios: float = 2.0,
    brecha_minima: float = BRECHA_PERCENTIL_MINIMA,
) -> RecomendacionRotacion:
    """Decide si rotar de un emisor a otro compensa la fricción fiscal.

    Nota importante: la alternativa siempre disponible es dirigir la **próxima
    aportación** al destino en vez de vender el origen. Da la mayor parte del
    beneficio con cero costo fiscal y cero riesgo de reentrada.
    """
    brecha = float(percentil_destino) - float(percentil_origen)
    liston = liston_de_friccion(ganancia_acumulada, tasa_impuesto=tasa_impuesto, anios=anios)
    conviene = brecha >= brecha_minima

    if conviene:
        mensaje = (
            f"La brecha de percentil es de {brecha * 100:.0f} puntos, arriba del mínimo de "
            f"{brecha_minima * 100:.0f}. Aun así, {liston.como_texto()} "
            "Antes de vender, considera dirigir la próxima aportación al destino: mismo efecto "
            "direccional, cero costo fiscal."
        )
    else:
        mensaje = (
            f"La brecha de percentil es de solo {brecha * 100:.0f} puntos, debajo del mínimo de "
            f"{brecha_minima * 100:.0f}. No rotar. {liston.como_texto()}"
        )
    return RecomendacionRotacion(conviene, brecha, liston, mensaje)


def venta_parcial_sugerida(
    valor_posicion: float,
    *,
    fraccion: float = 0.275,
    ganancia_acumulada: float = 0.0,
    tasa_impuesto: float = 0.10,
) -> dict[str, float | str]:
    """Venta parcial de 25–30% cuando el usuario quiere vender por valuación.

    La puerta 2 no vende. Si el usuario insiste, esta es la respuesta honesta:
    vender una fracción, ver el costo fiscal explícito y el listón de ventaja anual
    necesario para recuperarlo.
    """
    monto = valor_posicion * fraccion
    liston = liston_de_friccion(ganancia_acumulada, tasa_impuesto=tasa_impuesto, anios=2.0)
    return {
        "fraccion_sugerida": fraccion,
        "monto_venta": monto,
        "costo_fiscal_estimado": monto * liston.costo_fiscal,
        "ventaja_anual_necesaria_bps": liston.ventaja_anual_necesaria * 10_000,
        "advertencia": (
            "La puerta de valuación no dispara venta. Esta venta parcial es una decisión "
            "discrecional tuya, no una señal del sistema. El costo fiscal es inmediato y "
            "cierto; la ventaja del destino es esperada e incierta."
        ),
    }


def racha_deterioro(historial: pd.DataFrame, columna: str, condicion) -> int:
    """Utilidad para la interfaz: cuántos trimestres lleva un criterio en rojo."""
    if historial.empty or columna not in historial:
        return 0
    serie = historial[columna]
    return _racha_final(serie.apply(condicion).astype(bool).replace({np.nan: False}))
