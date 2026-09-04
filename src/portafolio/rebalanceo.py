"""Construcción de la meta, asignación con restricciones y destino de aportaciones.

Dos ideas que cambian el plan por completo:

1. **La tasa de retiro tiene que ser real, no nominal.** ``capital = gasto anual ÷
   tasa de retiro real``. Usar la nominal produce un plan que llega a la meta con
   aproximadamente la mitad del poder adquisitivo esperado a 20 años de inflación
   mexicana. La diferencia no es un detalle de cálculo: es la mitad del retiro.

2. **Rotar con dinero nuevo es preferible a vender.** Dirigir la próxima aportación
   al emisor más barato da la mayor parte del beneficio del rebalanceo con cero
   costo fiscal y cero riesgo de reentrada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.modelo.kill import evaluar_rotacion, liston_de_friccion

# --------------------------------------------------------------------------------------
# Meta de ingreso y capital requerido
# --------------------------------------------------------------------------------------


@dataclass
class MetaIngreso:
    """Cuánto capital hace falta para una meta de ingreso, en términos reales."""

    gasto_anual: float
    tasa_retiro_real: float
    tasa_retiro_nominal: float
    inflacion_supuesta: float
    capital_requerido_real: float
    capital_requerido_nominal: float
    moneda: str = "MXN"

    @property
    def brecha(self) -> float:
        return self.capital_requerido_real - self.capital_requerido_nominal

    def explicacion(self) -> str:
        return (
            f"Para un gasto de {self.gasto_anual:,.0f} {self.moneda} al año, usar la tasa de "
            f"retiro REAL de {self.tasa_retiro_real:.2%} exige {self.capital_requerido_real:,.0f}. "
            f"Usar la nominal de {self.tasa_retiro_nominal:.2%} sugeriría "
            f"{self.capital_requerido_nominal:,.0f}, que son {self.brecha:,.0f} menos. "
            f"Con inflación de {self.inflacion_supuesta:.2%}, ese plan más chico llega a la meta "
            f"pero con una fracción del poder adquisitivo: el ingreso nominal se cumple y el "
            f"real no. Es el error que hace que un plan de retiro se quede corto justo cuando "
            f"ya no hay tiempo de corregirlo."
        )


def capital_requerido(
    gasto_anual: float,
    tasa_retiro_real: float,
    *,
    inflacion: float = 0.04,
    moneda: str = "MXN",
) -> MetaIngreso:
    """``capital = gasto anual ÷ tasa de retiro real``.

    La tasa real se deriva de la nominal con Fisher exacta, no restando la inflación.
    """
    if tasa_retiro_real <= 0:
        raise ValueError("La tasa de retiro real debe ser positiva.")
    nominal = (1.0 + tasa_retiro_real) * (1.0 + inflacion) - 1.0
    return MetaIngreso(
        gasto_anual=float(gasto_anual),
        tasa_retiro_real=float(tasa_retiro_real),
        tasa_retiro_nominal=float(nominal),
        inflacion_supuesta=float(inflacion),
        capital_requerido_real=float(gasto_anual) / float(tasa_retiro_real),
        capital_requerido_nominal=float(gasto_anual) / float(nominal),
        moneda=moneda,
    )


def poder_adquisitivo_erosionado(anios: int, inflacion: float) -> float:
    """Qué fracción del poder adquisitivo sobrevive tras ``anios`` de inflación."""
    return 1.0 / (1.0 + inflacion) ** anios


@dataclass
class PlanAportaciones:
    capital_inicial: float
    aportacion_mensual: float
    rendimiento_real_anual: float
    meta: float
    meses_necesarios: int | None
    trayectoria: pd.DataFrame

    def como_texto(self) -> str:
        if self.meses_necesarios is None:
            return (
                f"Con {self.aportacion_mensual:,.0f} al mes y un rendimiento real de "
                f"{self.rendimiento_real_anual:.2%}, la meta de {self.meta:,.0f} no se alcanza "
                "en el horizonte simulado. Hay que subir la aportación, bajar la meta o extender el plazo."
            )
        anios = self.meses_necesarios / 12
        return (
            f"Con {self.aportacion_mensual:,.0f} al mes y un rendimiento real de "
            f"{self.rendimiento_real_anual:.2%}, la meta de {self.meta:,.0f} se alcanza en "
            f"{anios:.1f} años ({self.meses_necesarios} meses). Todo en poder adquisitivo de hoy."
        )


def simular_aportaciones(
    capital_inicial: float,
    aportacion_mensual: float,
    rendimiento_real_anual: float,
    meta: float,
    *,
    meses_maximos: int = 600,
) -> PlanAportaciones:
    """Cuánto y por cuánto tiempo hay que aportar para llegar a la meta.

    Todo el cálculo va en **términos reales**: la aportación mensual se supone
    indizada a la inflación y el rendimiento es real. Así el resultado se lee en
    poder adquisitivo de hoy sin conversiones mentales.
    """
    tasa_mensual = (1.0 + rendimiento_real_anual) ** (1 / 12) - 1.0
    saldo = float(capital_inicial)
    filas = [{"mes": 0, "saldo": saldo, "aportado": float(capital_inicial)}]
    aportado = float(capital_inicial)
    meses = None
    for m in range(1, meses_maximos + 1):
        saldo = saldo * (1.0 + tasa_mensual) + aportacion_mensual
        aportado += aportacion_mensual
        filas.append({"mes": m, "saldo": saldo, "aportado": aportado})
        if meses is None and saldo >= meta:
            meses = m
    return PlanAportaciones(
        capital_inicial=float(capital_inicial),
        aportacion_mensual=float(aportacion_mensual),
        rendimiento_real_anual=float(rendimiento_real_anual),
        meta=float(meta),
        meses_necesarios=meses,
        trayectoria=pd.DataFrame(filas),
    )


# --------------------------------------------------------------------------------------
# Asignación con restricciones
# --------------------------------------------------------------------------------------


@dataclass
class Restricciones:
    """Límites de concentración de la cartera."""

    max_por_emisor: float = 0.15
    max_por_sector: float = 0.35
    min_emisores: int = 6
    exige_puerta_calidad: bool = True

    def describir(self) -> str:
        return (
            f"Máximo {self.max_por_emisor:.0%} por emisor, {self.max_por_sector:.0%} por sector, "
            f"al menos {self.min_emisores} emisores"
            + (", y solo emisores que pasan la Puerta 1 de calidad." if self.exige_puerta_calidad else ".")
        )


@dataclass
class Asignacion:
    pesos: pd.Series
    excluidos: pd.DataFrame
    restricciones: Restricciones
    advertencias: list[str] = field(default_factory=list)

    def tabla(self) -> pd.DataFrame:
        return (
            self.pesos.rename("peso")
            .to_frame()
            .assign(peso_pct=lambda d: d["peso"])
            .sort_values("peso", ascending=False)
        )


def proponer_asignacion(
    candidatos: pd.DataFrame,
    *,
    restricciones: Restricciones | None = None,
    columna_señal: str = "percentil_prima",
) -> Asignacion:
    """Propone pesos por percentil de prima, sujeto a las restricciones.

    ``candidatos`` requiere ``ticker``, ``sector``, la columna de señal y
    ``pasa_calidad``. Los emisores que reprueban la Puerta 1 se excluyen antes de
    ponderar: **lo que falla no está barato, está descartado**, así que no compite
    por peso aunque su percentil sea altísimo.
    """
    restricciones = restricciones or Restricciones()
    advertencias: list[str] = []

    if candidatos.empty:
        return Asignacion(pd.Series(dtype="float64"), pd.DataFrame(), restricciones,
                          ["No hay candidatos."])

    df = candidatos.copy()
    excluidos = pd.DataFrame()

    if restricciones.exige_puerta_calidad and "pasa_calidad" in df.columns:
        malos = df[df["pasa_calidad"] != True]  # noqa: E712 - None también se excluye
        excluidos = malos[["ticker", "sector"]].assign(
            motivo="No pasa la Puerta 1 de calidad (o faltan datos para evaluarla)."
        )
        df = df[df["pasa_calidad"] == True]  # noqa: E712

    df = df[df[columna_señal].notna()]
    if df.empty:
        return Asignacion(pd.Series(dtype="float64"), excluidos, restricciones,
                          ["Ningún candidato pasa el filtro de calidad con señal disponible."])

    if len(df) < restricciones.min_emisores:
        advertencias.append(
            f"Solo {len(df)} emisores pasan los filtros; la diversificación mínima pide "
            f"{restricciones.min_emisores}. La cartera queda más concentrada de lo deseable."
        )

    # Peso base proporcional a la señal, con piso para no anular a nadie que pasó.
    señal = df.set_index("ticker")[columna_señal].astype(float).clip(lower=0.01)
    pesos = señal / señal.sum()
    pesos = _aplicar_topes(pesos, df.set_index("ticker")["sector"], restricciones, advertencias)

    return Asignacion(pesos.sort_values(ascending=False), excluidos, restricciones, advertencias)


def _aplicar_topes(
    pesos: pd.Series, sectores: pd.Series, restricciones: Restricciones, advertencias: list[str]
) -> pd.Series:
    """Recorta al tope por emisor y por sector, redistribuyendo el excedente.

    Itera porque recortar a uno sube a los demás y puede volver a romper un tope.
    """
    p = pesos.copy()
    for _ in range(50):
        excedente = 0.0
        topados = p > restricciones.max_por_emisor + 1e-12
        if topados.any():
            excedente += float((p[topados] - restricciones.max_por_emisor).sum())
            p[topados] = restricciones.max_por_emisor

        por_sector = p.groupby(sectores).sum()
        sectores_topados = por_sector[por_sector > restricciones.max_por_sector + 1e-12]
        for sector, total in sectores_topados.items():
            miembros = sectores[sectores == sector].index
            factor = restricciones.max_por_sector / total
            excedente += float(p[miembros].sum() * (1 - factor))
            p[miembros] = p[miembros] * factor

        if excedente <= 1e-12:
            break

        libres = p[(p < restricciones.max_por_emisor - 1e-12)]
        libres_sector = [
            t for t in libres.index
            if p.groupby(sectores).sum().get(sectores[t], 0.0) < restricciones.max_por_sector - 1e-12
        ]
        if not libres_sector:
            advertencias.append(
                "Las restricciones no permiten colocar todo el capital: "
                f"queda {excedente:.1%} sin asignar. Amplía el universo o relaja los topes."
            )
            break
        reparto = p[libres_sector] / p[libres_sector].sum()
        p[libres_sector] += excedente * reparto

    total = p.sum()
    return p / total if total > 0 else p


# --------------------------------------------------------------------------------------
# Destino de la próxima aportación
# --------------------------------------------------------------------------------------


@dataclass
class DestinoAportacion:
    ticker: str
    monto: float
    percentil_prima: float
    motivo: str


def destino_de_aportacion(
    candidatos: pd.DataFrame,
    monto: float,
    *,
    pesos_actuales: pd.Series | None = None,
    restricciones: Restricciones | None = None,
    columna_señal: str = "percentil_prima",
    max_destinos: int = 3,
) -> list[DestinoAportacion]:
    """Reparte la próxima aportación hacia los emisores más baratos que pasan calidad.

    Prioriza doble: percentil de prima alto **y** peso actual por debajo del objetivo.
    Así la aportación hace el trabajo del rebalanceo sin generar un solo peso de
    impuesto ni exponerse a reentrar más caro.
    """
    restricciones = restricciones or Restricciones()
    if candidatos.empty or monto <= 0:
        return []

    df = candidatos.copy()
    if "pasa_calidad" in df.columns:
        df = df[df["pasa_calidad"] == True]  # noqa: E712
    df = df[df[columna_señal].notna()]
    if df.empty:
        return []

    df = df.sort_values(columna_señal, ascending=False)

    if pesos_actuales is not None and not pesos_actuales.empty:
        objetivo = proponer_asignacion(candidatos, restricciones=restricciones,
                                       columna_señal=columna_señal).pesos
        df["brecha"] = df["ticker"].map(
            lambda t: float(objetivo.get(t, 0.0)) - float(pesos_actuales.get(t, 0.0))
        )
        df = df.sort_values(["brecha", columna_señal], ascending=False)
    else:
        df["brecha"] = np.nan

    elegidos = df.head(max_destinos)
    if elegidos.empty:
        return []

    señal = elegidos[columna_señal].clip(lower=0.01)
    reparto = señal / señal.sum()

    salida = []
    for (_, fila), w in zip(elegidos.iterrows(), reparto, strict=False):
        brecha = fila.get("brecha")
        motivo = f"Prima en el percentil {fila[columna_señal]:.0%} de su propia historia."
        if brecha is not None and not pd.isna(brecha):
            motivo += (
                f" Está {abs(brecha):.1%} {'por debajo' if brecha > 0 else 'por encima'} "
                "de su peso objetivo."
            )
        salida.append(
            DestinoAportacion(
                ticker=str(fila["ticker"]),
                monto=float(monto) * float(w),
                percentil_prima=float(fila[columna_señal]),
                motivo=motivo,
            )
        )
    return salida


PREFERENCIA_DINERO_NUEVO = (
    "Rotar con dinero nuevo es preferible a vender: da la mayor parte del beneficio del "
    "rebalanceo con cero costo fiscal y cero riesgo de reentrada. Vender para rotar solo "
    "se justifica cuando la brecha de percentil supera ~40 puntos y el listón de fricción "
    "queda cubierto."
)


def evaluar_rotacion_vs_aportacion(
    percentil_origen: float,
    percentil_destino: float,
    ganancia_acumulada: float,
    monto_aportacion_disponible: float,
    valor_posicion_origen: float,
    *,
    tasa_impuesto: float = 0.10,
) -> dict:
    """Compara vender-para-rotar contra dirigir la aportación al destino.

    Devuelve ambas rutas con su costo explícito para que la decisión no dependa de
    la intuición sobre cuánto pesa el impuesto.
    """
    rotacion = evaluar_rotacion(
        percentil_origen, percentil_destino, ganancia_acumulada, tasa_impuesto=tasa_impuesto
    )
    liston = liston_de_friccion(ganancia_acumulada, tasa_impuesto=tasa_impuesto)
    cobertura = (
        monto_aportacion_disponible / valor_posicion_origen if valor_posicion_origen > 0 else 0.0
    )
    return {
        "rotar": {
            "conviene": rotacion.conviene,
            "brecha_percentil": rotacion.brecha_percentil,
            "costo_fiscal_pct": liston.costo_fiscal,
            "ventaja_anual_necesaria_bps": liston.ventaja_anual_necesaria * 10_000,
            "mensaje": rotacion.mensaje,
        },
        "aportar_al_destino": {
            "monto": monto_aportacion_disponible,
            "cobertura_de_la_posicion_origen": cobertura,
            "costo_fiscal_pct": 0.0,
            "mensaje": (
                f"Dirigir {monto_aportacion_disponible:,.0f} al destino mueve el "
                f"{cobertura:.1%} del tamaño de la posición origen sin costo fiscal. "
                + PREFERENCIA_DINERO_NUEVO
            ),
        },
    }
