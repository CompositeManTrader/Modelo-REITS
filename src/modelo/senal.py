"""Prima, percentil expandible y semáforo de tres puertas.

P4 — Nunca compares niveles de yield entre emisores
===================================================
Rotar hacia "el que paga más" es rotar hacia el deterioro: el yield tiene el
precio en el denominador, así que un precio que se desploma lo infla
mecánicamente. Así se llega a W. P. Carey justo antes de que recorte, o a Global
Net Lease en plena dilución.

La comparación válida es la **prima de cada emisor sobre su propia tasa libre de
riesgo, expresada como percentil de su propia historia**. Un REIT de data centers
con 2.5% en el percentil 95 de su historia está más barato que uno de oficinas
con 9% en el percentil 20 de la suya.

P5 — El percentil se calcula con ventana EXPANDIBLE
===================================================
En la fecha ``t`` el percentil usa solo la historia hasta ``t`` inclusive. Jamás la
distribución completa de la muestra. Usar la distribución completa es fijar
umbrales con información del futuro: el modelo "sabe" que el yield llegó a 8% en
2023 cuando evalúa 2019.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
import pandas as pd

from src.config import UMBRALES, UmbralesCalidad, UmbralesDeterioro, UmbralesValuacion

# --------------------------------------------------------------------------------------
# Prima
# --------------------------------------------------------------------------------------


def calcular_prima(
    affo_yield: pd.Series,
    tasa_libre_riesgo: pd.Series,
    *,
    metodo: str = "ffill",
) -> pd.Series:
    """``prima = AFFO yield − tasa libre de riesgo``, alineadas por fecha.

    La tasa se propaga hacia adelante (nunca hacia atrás): en la fecha del dato de
    AFFO se usa la última tasa **ya publicada**, no la siguiente. Rellenar hacia
    atrás sería meter el futuro por la puerta de servicio.
    """
    if affo_yield.empty:
        return pd.Series(dtype="float64", name="prima")
    y = affo_yield.copy()
    y.index = pd.to_datetime(y.index)
    y = y.sort_index()

    if tasa_libre_riesgo.empty:
        return pd.Series(dtype="float64", index=y.index, name="prima")
    r = tasa_libre_riesgo.copy()
    r.index = pd.to_datetime(r.index)
    r = r.sort_index()

    if metodo != "ffill":
        raise ValueError("Solo se permite propagación hacia adelante: rellenar hacia atrás es lookahead.")
    alineada = r.reindex(r.index.union(y.index)).ffill().reindex(y.index)
    prima = y - alineada
    prima.name = "prima"
    return prima


# --------------------------------------------------------------------------------------
# Percentil expandible (P5)
# --------------------------------------------------------------------------------------


def percentil_expandible(
    serie: pd.Series,
    *,
    min_observaciones: int = 12,
    metodo: str = "promedio",
) -> pd.Series:
    """Percentil de cada observación dentro de la historia **hasta esa fecha**.

    Para la observación ``t``, la muestra de referencia es ``serie[:t]`` inclusive.
    Devuelve ``NaN`` mientras no haya ``min_observaciones``: un percentil calculado
    sobre cuatro trimestres no es un percentil, es una opinión.

    ``metodo='promedio'`` promedia el rango de los empates, que es la convención de
    ``scipy.stats.percentileofscore(kind='mean')``.
    """
    if serie.empty:
        return pd.Series(dtype="float64", name="percentil")
    s = pd.Series(serie).astype(float).copy()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()

    valores = s.to_numpy()
    salida = np.full(len(valores), np.nan)

    for i in range(len(valores)):
        n = i + 1
        if n < min_observaciones or np.isnan(valores[i]):
            continue
        ventana = valores[: i + 1]
        ventana = ventana[~np.isnan(ventana)]
        if len(ventana) < min_observaciones:
            continue
        x = valores[i]
        menores = np.sum(ventana < x)
        iguales = np.sum(ventana == x)
        if metodo == "promedio":
            rango = menores + 0.5 * iguales
        elif metodo == "estricto":
            rango = menores
        else:
            raise ValueError(f"Método desconocido: {metodo}")
        salida[i] = rango / len(ventana)

    resultado = pd.Series(salida, index=s.index, name="percentil")
    return resultado


def percentil_expandible_por_grupo(
    df: pd.DataFrame,
    columna_valor: str,
    columna_grupo: str,
    *,
    min_observaciones: int = 12,
) -> pd.Series:
    """Percentil expandible calculado por separado dentro de cada emisor o sector.

    Nunca se mezclan emisores en la misma distribución: eso es exactamente el error
    que P4 prohíbe.
    """
    partes = []
    for _, grupo in df.groupby(columna_grupo, sort=False):
        s = grupo.set_index("fecha_dato")[columna_valor]
        p = percentil_expandible(s, min_observaciones=min_observaciones)
        p.index = grupo.index
        partes.append(p)
    return pd.concat(partes).sort_index() if partes else pd.Series(dtype="float64")


def percentil_ventana_completa(serie: pd.Series) -> pd.Series:
    """Percentil con la distribución completa. **Solo para demostrar el sesgo.**

    Existe para que la interfaz pueda enseñar lado a lado cuánto cambia la señal
    cuando se usa el futuro. No debe alimentar ninguna decisión ni backtest.
    """
    s = pd.Series(serie).astype(float)
    return s.rank(pct=True, method="average")


def sesgo_por_ventana_completa(serie: pd.Series, *, min_observaciones: int = 12) -> pd.DataFrame:
    """Compara percentil expandible contra percentil de muestra completa."""
    exp = percentil_expandible(serie, min_observaciones=min_observaciones)
    comp = percentil_ventana_completa(serie)
    comp.index = exp.index
    df = pd.DataFrame({"expandible": exp, "muestra_completa": comp})
    df["diferencia"] = df["muestra_completa"] - df["expandible"]
    return df


# --------------------------------------------------------------------------------------
# Semáforo de tres puertas
# --------------------------------------------------------------------------------------


class Luz(StrEnum):
    VERDE = "VERDE"
    AMARILLO = "AMARILLO"
    ROJO = "ROJO"
    SIN_DATOS = "SIN DATOS"


class Accion(StrEnum):
    COMPRAR = "COMPRAR"
    MANTENER = "MANTENER"
    NO_COMPRAR_MAS = "NO COMPRAR MÁS"
    VENDER = "VENDER"
    DESCARTADO = "DESCARTADO"
    INCONCLUSO = "INCONCLUSO"


# Mínimo de criterios de calidad que tienen que ser medibles para que la Puerta 1
# emita un veredicto. Con menos, dice SIN DATOS: un criterio que no falla porque no
# se pudo medir no es un criterio aprobado.
UMBRALES_CALIDAD_MIN_EVALUABLES = 3


@dataclass
class ResultadoPuerta:
    """Una puerta evaluada, con el detalle de cada criterio."""

    nombre: str
    pasa: bool | None
    luz: Luz
    criterios: pd.DataFrame = field(default_factory=pd.DataFrame)
    mensaje: str = ""

    @property
    def fallidos(self) -> list[str]:
        if self.criterios.empty or "cumple" not in self.criterios:
            return []
        return self.criterios.loc[~self.criterios["cumple"].fillna(True), "criterio"].tolist()


def numero_o_nulo(valor) -> float | None:
    """Normaliza una celda de tabla a número o vacío, nunca a booleano ni a texto.

    Las tablas de criterios mezclan magnitudes con condiciones binarias: el payout
    trae 0.95 y el grado de inversión trae ``True``. En una misma columna eso
    degrada el tipo a ``object``, y una columna ``object`` no se puede serializar
    a Arrow: Streamlit no truena, aplica su propia conversión y sigue, así que la
    tabla que ve el usuario no es la que se construyó y nada lo avisa.

    Los criterios binarios no pierden nada: su veredicto vive en ``cumple``, que es
    donde corresponde.
    """
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float)):
        return None if pd.isna(valor) else float(valor)
    return None


def _criterio(nombre: str, valor, umbral, cumple: bool | None, explicacion: str) -> dict:
    return {
        "criterio": nombre,
        "valor": numero_o_nulo(valor),
        "umbral": numero_o_nulo(umbral),
        "cumple": cumple,
        "explicacion": explicacion,
    }


def puerta_calidad(
    metricas: dict[str, float | None],
    *,
    umbrales: UmbralesCalidad = UMBRALES.calidad,
) -> ResultadoPuerta:
    """Puerta 1 — Calidad. Binaria: lo que falla no está barato, está descartado.

    Ningún descuento de valuación compensa un payout insostenible o un balance
    apalancado. Esta puerta se evalúa primero y su salida no se pondera con nada.
    """
    filas = [
        _criterio(
            "Payout sobre AFFO",
            metricas.get("payout_affo"),
            umbrales.payout_affo_max,
            _menor_que(metricas.get("payout_affo"), umbrales.payout_affo_max),
            "El dividendo tiene que caber en el flujo ajustado, no en la utilidad contable.",
        ),
        _criterio(
            "Deuda neta / EBITDAre",
            metricas.get("deuda_neta_ebitdare"),
            umbrales.deuda_neta_ebitdare_max,
            _menor_que(metricas.get("deuda_neta_ebitdare"), umbrales.deuda_neta_ebitdare_max),
            "Apalancamiento arriba de este nivel limita la capacidad de crecer sin diluir.",
        ),
    ]
    if umbrales.exige_crecimiento_affo:
        cre = metricas.get("crecimiento_affo_por_accion_yoy")
        filas.append(
            _criterio(
                "AFFO por acción creciendo YoY",
                cre,
                0.0,
                None if cre is None else bool(cre > 0),
                "Si el AFFO por acción no crece, el dividendo futuro depende del múltiplo.",
            )
        )
    if umbrales.exige_spread_positivo:
        spr = metricas.get("spread_inversion")
        filas.append(
            _criterio(
                "Spread de inversión positivo",
                spr,
                0.0,
                None if spr is None else bool(spr > 0),
                "Comprar activos a un yield menor que el costo del capital destruye valor por acción.",
            )
        )
    if umbrales.exige_grado_inversion:
        gi = metricas.get("grado_inversion")
        filas.append(
            _criterio(
                "Grado de inversión vigente",
                gi,
                True,
                None if gi is None else bool(gi),
                "La pérdida del grado de inversión encarece la deuda justo cuando hay que refinanciar.",
            )
        )

    criterios = pd.DataFrame(filas)
    evaluables = criterios["cumple"].dropna()
    faltan = int(criterios["cumple"].isna().sum())

    # Un criterio que no falla porque no se pudo medir no es un criterio aprobado.
    # Si la mayoría no es evaluable, la puerta no dice "pasa": dice que no sabe.
    # Es la misma regla que en todo el sistema — sin evidencia suficiente el
    # veredicto es INCONCLUSO — aplicada donde más tienta el atajo contrario.
    if len(evaluables) < UMBRALES_CALIDAD_MIN_EVALUABLES:
        return ResultadoPuerta(
            "Calidad",
            None,
            Luz.SIN_DATOS,
            criterios,
            f"Solo {len(evaluables)} de {len(criterios)} criterios de calidad son evaluables "
            f"({faltan} sin datos). INCONCLUSO: no hay base para decir que pasa ni que falla. "
            "Consigue el balance del emisor antes de tomar esta pantalla como aprobación.",
        )

    # Con datos suficientes, un solo criterio reprobado descarta al emisor.
    pasa = bool(evaluables.all())
    mensaje = (
        "Pasa todos los criterios de calidad."
        if pasa
        else "DESCARTADO por calidad: " + "; ".join(
            criterios.loc[criterios["cumple"] == False, "criterio"].tolist()  # noqa: E712
        )
    )
    if faltan:
        mensaje += f" ({faltan} criterio(s) sin datos.)"
    return ResultadoPuerta("Calidad", pasa, Luz.VERDE if pasa else Luz.ROJO, criterios, mensaje)


def puerta_valuacion(
    percentil_prima: float | None,
    n_observaciones: int,
    *,
    umbrales: UmbralesValuacion = UMBRALES.valuacion,
) -> ResultadoPuerta:
    """Puerta 2 — Valuación. Modula compras nuevas; **nunca dispara venta por sí sola**.

    Percentil alto de la prima significa que el emisor está pagando más spread que
    en su propia historia, es decir, está barato contra sí mismo.
    """
    criterios = pd.DataFrame(
        [
            _criterio(
                "Percentil expandible de la prima",
                percentil_prima,
                f"≥{umbrales.percentil_compra:.0%} comprar / <{umbrales.percentil_mantener:.0%} no comprar",
                None if percentil_prima is None else True,
                "Percentil de la prima del emisor contra su propia historia, ventana expandible.",
            ),
            _criterio(
                "Observaciones en la historia",
                n_observaciones,
                umbrales.min_observaciones,
                n_observaciones >= umbrales.min_observaciones,
                "Con pocos trimestres el percentil no es informativo.",
            ),
        ]
    )
    if percentil_prima is None or n_observaciones < umbrales.min_observaciones:
        return ResultadoPuerta(
            "Valuación",
            None,
            Luz.SIN_DATOS,
            criterios,
            f"Historia insuficiente ({n_observaciones} observaciones; se piden "
            f"{umbrales.min_observaciones}). Veredicto de valuación: INCONCLUSO.",
        )
    if percentil_prima >= umbrales.percentil_compra:
        luz, msg = Luz.VERDE, (
            f"Prima en el percentil {percentil_prima:.0%} de su propia historia: barato contra sí mismo."
        )
    elif percentil_prima >= umbrales.percentil_mantener:
        luz, msg = Luz.AMARILLO, (
            f"Prima en el percentil {percentil_prima:.0%}: zona media, mantener sin agregar agresivamente."
        )
    else:
        luz, msg = Luz.ROJO, (
            f"Prima en el percentil {percentil_prima:.0%}: caro contra su propia historia. "
            "No comprar más. Esto NO es una señal de venta."
        )
    return ResultadoPuerta("Valuación", luz != Luz.ROJO, luz, criterios, msg)


def puerta_deterioro(
    historial: pd.DataFrame,
    *,
    umbrales: UmbralesDeterioro = UMBRALES.deterioro,
) -> ResultadoPuerta:
    """Puerta 3 — Deterioro. La **única** que dispara VENTA.

    ``historial`` es un panel trimestral con las columnas ``payout_affo``,
    ``spread_inversion``, ``crecimiento_affo_por_accion_yoy``,
    ``deuda_neta_ebitdare`` y ``grado_inversion``, ordenado por fecha.

    Los criterios de dos trimestres consecutivos existen para no vender por un
    trimestre malo: un recorte de dividendo se anuncia después de un patrón, no
    después de un dato.
    """
    from src.modelo.kill import evaluar_kill  # import local para evitar ciclo

    resultado = evaluar_kill(historial, umbrales=umbrales)

    # No disparar venta por falta de datos es correcto: nadie vende porque le falte
    # información. Pintar esa misma falta de VERDE no lo es. VERDE significa "lo
    # medí y está sano", y aquí no se midió nada. La luz reporta la evidencia; el
    # veredicto de venta sigue siendo negativo, que es lo prudente.
    if resultado.criterios.empty:
        evaluables = 0
    else:
        evaluables = int(resultado.criterios["dispara"].notna().sum())

    if resultado.dispara_venta:
        luz = Luz.ROJO
    elif evaluables == 0:
        luz = Luz.SIN_DATOS
    else:
        luz = Luz.VERDE

    mensaje = resultado.mensaje
    if luz is Luz.SIN_DATOS:
        # Se agrega siempre, no solo cuando el mensaje viene vacío: el texto de
        # `evaluar_kill` explica por qué no se vende, que es la mitad del asunto.
        # La otra mitad —que tampoco se está afirmando nada bueno— hay que decirla.
        mensaje = (
            f"{mensaje} Ningún criterio resultó medible, así que tampoco hay base "
            "para declarar sano al emisor."
        ).strip()

    return ResultadoPuerta(
        "Deterioro",
        not resultado.dispara_venta,
        luz,
        resultado.criterios,
        mensaje,
    )


@dataclass
class Semaforo:
    """Las tres puertas por separado. No es una caja negra: cada puerta se ve sola."""

    ticker: str
    fecha: pd.Timestamp
    calidad: ResultadoPuerta
    valuacion: ResultadoPuerta
    deterioro: ResultadoPuerta
    accion: Accion
    explicacion: str

    def como_tabla(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"puerta": p.nombre, "luz": p.luz.value, "mensaje": p.mensaje}
                for p in (self.calidad, self.valuacion, self.deterioro)
            ]
        )


def evaluar_semaforo(
    ticker: str,
    fecha,
    metricas: dict[str, float | None],
    percentil_prima: float | None,
    n_observaciones: int,
    historial: pd.DataFrame,
) -> Semaforo:
    """Combina las tres puertas con la regla de venta explícita del proyecto.

    Regla que debe quedar clara en la interfaz: **vender por precio caro es distinto
    de vender por tesis rota**. La puerta 2 nunca dispara venta por sí sola; modula
    compras nuevas. Solo la puerta 3 vende.
    """
    p1 = puerta_calidad(metricas)
    p2 = puerta_valuacion(percentil_prima, n_observaciones)
    p3 = puerta_deterioro(historial)

    if p3.luz == Luz.ROJO:
        accion = Accion.VENDER
        explicacion = (
            "Puerta 3 (deterioro) disparada: la tesis está rota, no es un tema de precio. "
            + p3.mensaje
        )
    elif p1.pasa is False:
        accion = Accion.DESCARTADO
        explicacion = "Puerta 1 (calidad) reprobada. Lo que falla no está barato: está descartado. " + p1.mensaje
    elif p1.pasa is None:
        accion = Accion.INCONCLUSO
        explicacion = "Faltan datos para evaluar la calidad. INCONCLUSO, que no es lo mismo que MANTENER."
    elif p2.luz == Luz.SIN_DATOS:
        accion = Accion.INCONCLUSO
        explicacion = (
            "La calidad pasa, pero la historia de prima es insuficiente para emitir un "
            "percentil confiable. INCONCLUSO. " + p2.mensaje
        )
    elif p2.luz == Luz.VERDE:
        accion = Accion.COMPRAR
        explicacion = "Calidad aprobada y prima en percentil alto de su propia historia. " + p2.mensaje
    elif p2.luz == Luz.AMARILLO:
        accion = Accion.MANTENER
        explicacion = "Calidad aprobada, valuación en zona media. " + p2.mensaje
    else:
        accion = Accion.NO_COMPRAR_MAS
        explicacion = (
            "Calidad aprobada pero valuación cara contra su propia historia. "
            "Se detienen compras nuevas; esto NO justifica vender. " + p2.mensaje
        )

    return Semaforo(
        ticker=ticker,
        fecha=pd.Timestamp(fecha),
        calidad=p1,
        valuacion=p2,
        deterioro=p3,
        accion=accion,
        explicacion=explicacion,
    )


# --------------------------------------------------------------------------------------
# Guardas contra la comparación prohibida (P4)
# --------------------------------------------------------------------------------------


class ComparacionInvalida(ValueError):
    """Se intentó comparar niveles de yield entre emisores."""


def comparar_emisores(
    percentiles: dict[str, float],
    *,
    sectores: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Compara emisores por **percentil de su propia prima**, nunca por nivel de yield.

    Es la única comparación válida entre emisores. Si se pasan sectores, se marca
    cuáles comparaciones cruzan sectores distintos para que la interfaz lo advierta.
    """
    filas = [
        {"ticker": t, "percentil_prima": p, "sector": (sectores or {}).get(t, "—")}
        for t, p in percentiles.items()
    ]
    df = pd.DataFrame(filas).sort_values("percentil_prima", ascending=False)
    if sectores and df["sector"].nunique() > 1:
        df.attrs["advertencia"] = (
            "La tabla incluye sectores distintos. El percentil de prima sí es comparable "
            "entre sectores porque cada emisor se mide contra su propia historia, pero las "
            "economías subyacentes no lo son: no infieras del ranking que un sector sustituye a otro."
        )
    return df.reset_index(drop=True)


def comparar_yields_crudos(*_args, **_kwargs):
    """Existe únicamente para fallar. Comparar niveles de yield entre emisores es P4.

    El yield tiene el precio en el denominador: un precio que se desploma lo infla
    mecánicamente. Ordenar emisores por yield es ordenarlos por deterioro reciente.
    """
    raise ComparacionInvalida(
        "Comparar niveles de yield entre emisores está prohibido por P4. "
        "Usa comparar_emisores() con percentiles de prima sobre la propia historia."
    )


def _menor_que(valor, umbral) -> bool | None:
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return None
    return bool(valor < umbral)
