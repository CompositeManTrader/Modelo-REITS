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
from src.modelo.senal import numero_o_nulo


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

    # `umbral` y `persistencia` van separados a propósito. Antes eran la misma
    # columna con dos significados —el nivel numérico cuando faltaban datos, y el
    # texto "2 trimestre(s)" cuando sí había— y una columna que cambia de sentido
    # según la fila no se puede leer ni tipar: pandas la degrada a `object` y la
    # tabla revienta al dibujarse.
    def evaluar(nombre: str, condicion: pd.Series | None, umbral, explicacion: str, consecutivos: bool = True):
        requerida = n if consecutivos else 1
        persistencia = f"{requerida} trimestre(s)" if consecutivos else "inmediato"
        if condicion is None:
            filas.append(
                {
                    "criterio": nombre,
                    "racha": None,
                    "umbral": numero_o_nulo(umbral),
                    "persistencia": persistencia,
                    "dispara": None,
                    "explicacion": f"{explicacion} (sin datos)",
                }
            )
            return
        racha = _racha_final(condicion) if consecutivos else int(bool(condicion.iloc[-1]))
        dispara = racha >= requerida
        if dispara:
            disparadores.append(nombre)
        filas.append(
            {
                "criterio": nombre,
                "racha": racha,
                "umbral": numero_o_nulo(umbral),
                "persistencia": persistencia,
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
    # Qué proporción de lo que vendes es ganancia gravable. Va explícita porque
    # es justo el paso que se saltaba el cálculo anterior.
    fraccion_gravable: float = 0.0
    base: str = "costo"

    def como_texto(self) -> str:
        return (
            f"Con {self.ganancia_acumulada:.0%} de ganancia acumulada sobre el {self.base} y "
            f"tasa de {self.tasa_impuesto:.0%}, la parte gravable de lo que vendes es "
            f"{self.fraccion_gravable:.1%} y el costo fiscal es {self.costo_fiscal:.1%} del "
            f"valor. Para recuperarlo en {self.anios_recuperacion:.0f} años, el destino tiene "
            f"que rendir {self.ventaja_anual_necesaria * 10_000:,.0f} bps más al año."
        )


def liston_de_friccion(
    ganancia_acumulada: float,
    *,
    tasa_impuesto: float = 0.10,
    anios: float = 2.0,
    comisiones: float = 0.0,
    base: str = "costo",
) -> CostoDeRotacion:
    """Calcula el listón que el destino debe superar para que rotar valga la pena.

    ``base`` dice contra qué está medida la ganancia, y no es un detalle:

    * ``"costo"`` (por omisión, y lo que dicen todos los controles de la
      aplicación) — una posición con 40% de ganancia sobre el costo vale 1.4
      veces lo que costó, así que **la parte gravable de lo que vendes es
      40/140 = 28.6%, no 40%**. El impuesto se paga sobre la ganancia, no sobre
      el valor.
    * ``"valor"`` — la lectura anterior, donde la ganancia ya venía expresada
      como fracción del valor de mercado. Se conserva para reproducir la tabla
      vieja del proyecto, pero no es lo que piden los deslizadores.

    La versión anterior multiplicaba la ganancia sobre el COSTO por la tasa y
    llamaba al resultado «% del valor». Con 40% sobreestimaba el impuesto en 40%;
    con 100%, en el doble; y con 300% —el tope del deslizador— en cuatro veces.
    El sesgo era conservador, en el sentido de desanimar la rotación, pero el
    número era falso y el listón en puntos base lo heredaba entero.

    Es el cálculo que casi nadie hace antes de rotar y el que más veces evita la
    rotación. Rotar con dinero nuevo da la mayor parte del beneficio con cero costo
    fiscal y cero riesgo de reentrada.
    """
    g = max(0.0, float(ganancia_acumulada))
    if base == "valor":
        fraccion_gravable = min(g, 1.0)
    elif base == "costo":
        fraccion_gravable = g / (1.0 + g)
    else:
        raise ValueError(f"base desconocida: {base!r}. Usa 'costo' o 'valor'.")

    costo_fiscal = fraccion_gravable * float(tasa_impuesto) + float(comisiones)
    ventaja = costo_fiscal / anios if anios > 0 else float("inf")
    return CostoDeRotacion(
        ganancia_acumulada=float(ganancia_acumulada),
        tasa_impuesto=float(tasa_impuesto),
        costo_fiscal=costo_fiscal,
        anios_recuperacion=float(anios),
        ventaja_anual_necesaria=ventaja,
        comisiones=float(comisiones),
        fraccion_gravable=fraccion_gravable,
        base=base,
    )


def tabla_liston_friccion(
    ganancias: tuple[float, ...] = (0.20, 0.40, 0.60, 1.00),
    *,
    tasa_impuesto: float = 0.10,
    anios: float = 2.0,
    base: str = "costo",
) -> pd.DataFrame:
    """La tabla de fricción, con la fracción gravable a la vista.

    La columna de en medio es la que explica por qué los números cambiaron
    respecto de la tabla vieja: el impuesto se paga sobre la ganancia embebida en
    lo que vendes, no sobre el valor completo.
    """
    filas = []
    for g in ganancias:
        c = liston_de_friccion(g, tasa_impuesto=tasa_impuesto, anios=anios, base=base)
        filas.append(
            {
                # Los nombres llevan su unidad —`_pct`, `_bps`, `fraccion`— porque
                # es así como la interfaz decide la escala y el formato. Con
                # encabezados en prosa, «Ganancia acumulada» y «Costo fiscal»
                # caían en la familia de MONEDA y la tabla dibujaba "$0.20" y
                # "$0.02" donde son 20% y 2%.
                "ganancia_acumulada_pct": g,
                "fraccion_gravable": c.fraccion_gravable,
                "costo_fiscal_pct": c.costo_fiscal,
                "ventaja_anual_bps": round(c.ventaja_anual_necesaria * 10_000),
            }
        )
    return pd.DataFrame(filas)


ETIQUETAS_FRICCION = {
    "ganancia_acumulada_pct": "Ganancia acumulada sobre el costo",
    "fraccion_gravable": "Parte gravable de lo que vendes",
    "costo_fiscal_pct": "Costo fiscal (10% cedular)",
    "ventaja_anual_bps": "Ventaja anual necesaria a 2 años",
}
"""Encabezados legibles de la tabla de fricción, para pasarlos como `column_config`.

Van aparte de las claves porque la clave decide la UNIDAD y el encabezado decide
la PRESENTACIÓN; mezclarlos es lo que rompía el formato.
"""


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
    # `costo_fiscal` es fracción del VALOR vendido, así que multiplicar por el
    # monto da el impuesto en pesos: la ganancia embebida en lo que vendes ya
    # está descontada dentro de `fraccion_gravable`.
    return {
        "fraccion_sugerida": fraccion,
        "monto_venta": monto,
        "fraccion_gravable": liston.fraccion_gravable,
        "ganancia_gravable": monto * liston.fraccion_gravable,
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
