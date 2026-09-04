"""Fiscalidad mexicana de REITs estadounidenses e inmuebles en renta.

Todo lo de aquí es **indicativo**. Las distribuciones de REITs tienen reglas
propias en el tratado México–Estados Unidos, distintas de los dividendos
corporativos ordinarios, y la aplicación práctica depende de cómo las clasifique
el intermediario. Hay que confirmar con la casa de bolsa qué tasa aplica en la
práctica antes de planear con estos números.

Tres cosas que cambian el resultado más que la selección de activos:

* **Vía de compra.** SIC con casa de bolsa mexicana entra al régimen cedular del
  10% sobre ganancias. Un bróker extranjero puede caer en tarifa progresiva de
  hasta 35%.
* **Retención combinada del dividendo.** ~10% en Estados Unidos con W-8BEN más
  ~10% adicional en México: alrededor de 20% efectivo.
* **Estate tax.** Arriba de 60,000 dólares de activos con situs estadounidense, la
  exposición de los herederos llega a 40%. No hay tratado sucesorio México–EE. UU.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.config import (
    DEDUCCION_CIEGA_ARRENDAMIENTO,
    ISR_ADICIONAL_MEXICO_DIVIDENDO_EXTRANJERO,
    RETENCION_EEUU_W8BEN,
    TASA_CEDULAR_GANANCIAS_SIC,
    TASA_MAXIMA_ESTATE_TAX,
    UMBRAL_ESTATE_TAX_USD,
)

# --------------------------------------------------------------------------------------
# Tarifa anual del ISR para personas físicas (Art. 152 LISR)
# --------------------------------------------------------------------------------------
#
# ATENCIÓN: la tarifa se actualiza por inflación. Esta es la tarifa anual vigente
# para el ejercicio 2024, que sirve de referencia razonable para ejercicios
# cercanos. Antes de usarla para una declaración real, verifícala contra el DOF
# del ejercicio correspondiente y sustituye la tabla.

ANIO_TARIFA = 2024

TARIFA_ANUAL_ISR: tuple[tuple[float, float, float, float], ...] = (
    # (límite inferior, límite superior, cuota fija, % sobre excedente)
    (0.01, 8_952.49, 0.00, 0.0192),
    (8_952.50, 75_984.55, 171.88, 0.0640),
    (75_984.56, 133_536.07, 4_461.94, 0.1088),
    (133_536.08, 155_229.80, 10_723.55, 0.1600),
    (155_229.81, 185_852.57, 14_194.54, 0.1792),
    (185_852.58, 374_837.88, 19_682.13, 0.2136),
    (374_837.89, 590_795.99, 60_049.40, 0.2352),
    (590_796.00, 1_127_926.84, 110_842.74, 0.3000),
    (1_127_926.85, 1_503_902.46, 271_981.99, 0.3200),
    (1_503_902.47, 4_511_707.37, 392_294.17, 0.3400),
    (4_511_707.38, float("inf"), 1_414_947.85, 0.3500),
)


def isr_anual_personas_fisicas(base_gravable: float) -> float:
    """ISR anual según la tarifa progresiva del Art. 152 LISR."""
    base = max(0.0, float(base_gravable))
    for inferior, superior, cuota, tasa in TARIFA_ANUAL_ISR:
        if inferior <= base <= superior:
            return cuota + (base - inferior) * tasa
    return 0.0


def tasa_efectiva_isr(base_gravable: float) -> float:
    base = max(0.0, float(base_gravable))
    return isr_anual_personas_fisicas(base) / base if base > 0 else 0.0


def tasa_marginal_isr(base_gravable: float) -> float:
    """Tasa marginal aplicable al siguiente peso de ingreso."""
    base = max(0.0, float(base_gravable))
    for inferior, superior, _cuota, tasa in TARIFA_ANUAL_ISR:
        if inferior <= base <= superior:
            return tasa
    return TARIFA_ANUAL_ISR[-1][3]


# --------------------------------------------------------------------------------------
# Dividendos de REITs estadounidenses
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoDividendo:
    bruto: float
    retencion_eeuu: float
    isr_mexico: float
    neto: float
    tasa_efectiva: float
    advertencias: list[str] = field(default_factory=list)

    def como_tabla(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"concepto": "Dividendo bruto", "monto": self.bruto},
                {"concepto": "Retención EE. UU.", "monto": -self.retencion_eeuu},
                {"concepto": "ISR adicional México", "monto": -self.isr_mexico},
                {"concepto": "Neto al bolsillo", "monto": self.neto},
            ]
        )


def impuesto_dividendo(
    bruto: float,
    *,
    tiene_w8ben: bool = True,
    tasa_retencion_eeuu: float | None = None,
    tasa_mexico: float = ISR_ADICIONAL_MEXICO_DIVIDENDO_EXTRANJERO,
    acredita_retencion: bool = False,
) -> ResultadoDividendo:
    """Impuesto sobre un dividendo de REIT estadounidense cobrado por un residente mexicano.

    Sin W-8BEN la retención estadounidense sube a 30%. Con W-8BEN y tratado baja a
    10% para dividendos ordinarios; las distribuciones de REIT tienen tratamiento
    propio en el tratado y el intermediario puede aplicar una tasa distinta.

    ``acredita_retencion=True`` modela el acreditamiento del impuesto pagado en el
    extranjero contra el ISR mexicano, que la ley permite con límites. En la
    práctica muchos intermediarios no lo aplican de oficio y el efectivo combinado
    termina siendo la suma simple, alrededor de 20%.
    """
    bruto = float(bruto)
    tasa_us = (
        tasa_retencion_eeuu
        if tasa_retencion_eeuu is not None
        else (RETENCION_EEUU_W8BEN if tiene_w8ben else 0.30)
    )
    retencion = bruto * tasa_us

    if acredita_retencion:
        isr_bruto = bruto * tasa_mexico
        isr = max(0.0, isr_bruto - retencion)
    else:
        isr = bruto * tasa_mexico

    neto = bruto - retencion - isr
    advertencias = [
        "Las distribuciones de REITs tienen reglas propias en el tratado México–EE. UU., "
        "distintas de los dividendos corporativos. Confirma con tu casa de bolsa qué tasa "
        "te aplica en la práctica: la diferencia entre 10% y 30% de retención es material.",
    ]
    if not tiene_w8ben:
        advertencias.insert(
            0,
            "Sin W-8BEN la retención estadounidense es de 30%. Presentarlo es el trámite con "
            "mejor relación esfuerzo/beneficio de toda la estructura.",
        )
    if acredita_retencion:
        advertencias.append(
            "Se está modelando acreditamiento del impuesto pagado en el extranjero. Verifica "
            "que tu intermediario y tu declaración efectivamente lo apliquen; si no, el "
            "efectivo combinado es la suma simple, alrededor de 20%."
        )
    return ResultadoDividendo(
        bruto=bruto,
        retencion_eeuu=retencion,
        isr_mexico=isr,
        neto=neto,
        tasa_efectiva=(bruto - neto) / bruto if bruto else 0.0,
        advertencias=advertencias,
    )


# --------------------------------------------------------------------------------------
# Ganancias de capital
# --------------------------------------------------------------------------------------


class ViaDeCompra:
    SIC = "SIC (casa de bolsa mexicana)"
    BROKER_EXTRANJERO = "Bróker extranjero"


@dataclass
class ResultadoGanancia:
    ganancia: float
    via: str
    impuesto: float
    neto: float
    tasa_efectiva: float
    advertencias: list[str] = field(default_factory=list)


def impuesto_ganancia_capital(
    ganancia: float,
    *,
    via: str = ViaDeCompra.SIC,
    ingreso_acumulable_previo: float = 0.0,
) -> ResultadoGanancia:
    """Impuesto sobre la ganancia al vender.

    Vía SIC con casa de bolsa mexicana: régimen cedular del 10%, definitivo y
    sencillo. Vía bróker extranjero: la ganancia puede resultar acumulable y quedar
    sujeta a la tarifa progresiva, con marginal de hasta 35%. La misma operación
    puede costar 10% o 35% según dónde se ejecutó.
    """
    ganancia = float(ganancia)
    if ganancia <= 0:
        return ResultadoGanancia(ganancia, via, 0.0, ganancia, 0.0,
                                 ["Sin ganancia: no hay impuesto. Revisa las reglas de pérdidas."])

    if via == ViaDeCompra.SIC:
        impuesto = ganancia * TASA_CEDULAR_GANANCIAS_SIC
        advertencias = [
            f"Régimen cedular del {TASA_CEDULAR_GANANCIAS_SIC:.0%} sobre la ganancia, aplicable a "
            "operaciones en el SIC con intermediario mexicano."
        ]
    else:
        isr_con = isr_anual_personas_fisicas(ingreso_acumulable_previo + ganancia)
        isr_sin = isr_anual_personas_fisicas(ingreso_acumulable_previo)
        impuesto = isr_con - isr_sin
        marginal = tasa_marginal_isr(ingreso_acumulable_previo + ganancia)
        advertencias = [
            f"Vía bróker extranjero la ganancia puede resultar acumulable: marginal de "
            f"{marginal:.0%} sobre el excedente. Frente al {TASA_CEDULAR_GANANCIAS_SIC:.0%} "
            "cedular del SIC, la diferencia puede superar el rendimiento esperado de la rotación.",
        ]

    return ResultadoGanancia(
        ganancia=ganancia,
        via=via,
        impuesto=impuesto,
        neto=ganancia - impuesto,
        tasa_efectiva=impuesto / ganancia,
        advertencias=advertencias,
    )


# --------------------------------------------------------------------------------------
# Estate tax
# --------------------------------------------------------------------------------------


@dataclass
class AlertaEstateTax:
    activa: bool
    valor_situs_eeuu: float
    umbral: float
    exposicion_estimada: float
    mensaje: str


def alerta_estate_tax(valor_situs_eeuu: float) -> AlertaEstateTax:
    """Alerta permanente cuando los activos con situs estadounidense superan 60,000 dólares.

    No hay tratado sucesorio México–Estados Unidos. Para un no residente, la
    exención federal es de 60,000 dólares — no los millones que aplican a
    residentes — y el excedente puede gravarse hasta 40%. Es el riesgo que más se
    ignora en una cartera de REITs estadounidenses armada desde México.
    """
    valor = float(valor_situs_eeuu)
    excedente = max(0.0, valor - UMBRAL_ESTATE_TAX_USD)
    exposicion = excedente * TASA_MAXIMA_ESTATE_TAX
    activa = valor > UMBRAL_ESTATE_TAX_USD
    if activa:
        mensaje = (
            f"ALERTA DE ESTATE TAX: tienes {valor:,.0f} USD en activos con situs estadounidense, "
            f"arriba del umbral de {UMBRAL_ESTATE_TAX_USD:,.0f}. Para un no residente sin tratado "
            f"sucesorio, el excedente de {excedente:,.0f} USD puede gravarse hasta "
            f"{TASA_MAXIMA_ESTATE_TAX:.0%}: una exposición de hasta {exposicion:,.0f} USD para tus "
            "herederos. Consulta estructuras de mitigación con un especialista antes de seguir "
            "acumulando."
        )
    else:
        mensaje = (
            f"Activos con situs estadounidense por {valor:,.0f} USD, debajo del umbral de "
            f"{UMBRAL_ESTATE_TAX_USD:,.0f}. La alerta se activará al cruzarlo."
        )
    return AlertaEstateTax(activa, valor, UMBRAL_ESTATE_TAX_USD, exposicion, mensaje)


# --------------------------------------------------------------------------------------
# Arrendamiento de inmuebles
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoArrendamiento:
    renta_anual: float
    deducciones: float
    base_gravable: float
    isr: float
    tasa_efectiva: float
    neto: float
    modalidad: str
    detalle: dict[str, float] = field(default_factory=dict)


def isr_arrendamiento(
    renta_anual: float,
    *,
    predial_anual: float = 0.0,
    deducciones_comprobadas: float | None = None,
    ingreso_por_sueldo: float = 0.0,
) -> ResultadoArrendamiento:
    """ISR sobre ingreso por arrendamiento, con deducción opcional del 35%.

    La ley permite optar por la **deducción ciega**: 35% del ingreso más el predial,
    sin comprobar gastos. Contra deducciones comprobadas, la ciega gana casi siempre
    en un inmueble sin hipoteca.

    El parámetro que mueve el resultado casi 30% en capital requerido es
    ``ingreso_por_sueldo``: la renta como único ingreso paga una tasa efectiva
    alrededor de 5%, pero apilada sobre un sueldo entra en marginal de 30–35%.
    """
    renta = float(renta_anual)
    ciega = renta * DEDUCCION_CIEGA_ARRENDAMIENTO + float(predial_anual)

    if deducciones_comprobadas is not None and deducciones_comprobadas > ciega:
        deducciones = float(deducciones_comprobadas)
        modalidad = "Deducciones comprobadas"
    else:
        deducciones = ciega
        modalidad = f"Deducción ciega ({DEDUCCION_CIEGA_ARRENDAMIENTO:.0%}) + predial"

    base = max(0.0, renta - deducciones)
    sueldo = float(ingreso_por_sueldo)

    if sueldo > 0:
        isr = isr_anual_personas_fisicas(sueldo + base) - isr_anual_personas_fisicas(sueldo)
        modalidad += " — apilada sobre sueldo"
    else:
        isr = isr_anual_personas_fisicas(base)
        modalidad += " — renta como único ingreso"

    return ResultadoArrendamiento(
        renta_anual=renta,
        deducciones=deducciones,
        base_gravable=base,
        isr=isr,
        tasa_efectiva=isr / renta if renta else 0.0,
        neto=renta - isr,
        modalidad=modalidad,
        detalle={
            "deduccion_ciega": ciega,
            "predial": float(predial_anual),
            "marginal_aplicable": tasa_marginal_isr(sueldo + base),
        },
    )


def comparar_modalidades_arrendamiento(
    renta_anual: float, predial_anual: float, ingreso_por_sueldo: float
) -> pd.DataFrame:
    """Los dos casos que el proyecto exige modelar, lado a lado."""
    solo = isr_arrendamiento(renta_anual, predial_anual=predial_anual)
    apilada = isr_arrendamiento(
        renta_anual, predial_anual=predial_anual, ingreso_por_sueldo=ingreso_por_sueldo
    )
    return pd.DataFrame(
        [
            {
                "Caso": "Renta como único ingreso",
                "Base gravable": solo.base_gravable,
                "ISR": solo.isr,
                "Tasa efectiva sobre renta": solo.tasa_efectiva,
                "Neto": solo.neto,
            },
            {
                "Caso": f"Renta apilada sobre sueldo de {ingreso_por_sueldo:,.0f}",
                "Base gravable": apilada.base_gravable,
                "ISR": apilada.isr,
                "Tasa efectiva sobre renta": apilada.tasa_efectiva,
                "Neto": apilada.neto,
            },
        ]
    )


# --------------------------------------------------------------------------------------
# Rendimiento después de impuestos
# --------------------------------------------------------------------------------------


def yield_despues_de_impuestos(
    yield_bruto: float,
    *,
    tiene_w8ben: bool = True,
    tasa_mexico: float = ISR_ADICIONAL_MEXICO_DIVIDENDO_EXTRANJERO,
) -> float:
    """Convierte un yield bruto en yield neto al bolsillo de un residente mexicano.

    Es la conversión que hace honesta la comparación contra el Udibono: comparar un
    yield bruto de REIT contra una tasa de bono es comparar peras con manzanas.
    """
    r = impuesto_dividendo(1.0, tiene_w8ben=tiene_w8ben, tasa_mexico=tasa_mexico)
    return float(yield_bruto) * r.neto


def rendimiento_real_despues_de_impuestos(
    yield_bruto: float,
    crecimiento_esperado: float,
    inflacion: float,
    *,
    tiene_w8ben: bool = True,
) -> dict[str, float]:
    """Rendimiento total esperado, después de impuestos y en términos reales.

    Es el único número comparable contra el Udibono, que paga tasa real fija
    garantizada y no paga ISR sobre el componente inflacionario.
    """
    y_neto = yield_despues_de_impuestos(yield_bruto, tiene_w8ben=tiene_w8ben)
    nominal_neto = y_neto + float(crecimiento_esperado)
    real = (1.0 + nominal_neto) / (1.0 + float(inflacion)) - 1.0
    return {
        "yield_bruto": float(yield_bruto),
        "yield_neto": y_neto,
        "crecimiento_esperado": float(crecimiento_esperado),
        "nominal_despues_de_impuestos": nominal_neto,
        "real_despues_de_impuestos": real,
    }


DESCARGO_FISCAL = (
    "Cálculos fiscales indicativos, no asesoría. La tarifa del ISR se actualiza cada "
    f"ejercicio (aquí se usa la de {ANIO_TARIFA}) y las distribuciones de REITs tienen "
    "reglas propias en el tratado México–EE. UU. Confirma con tu casa de bolsa y con un "
    "contador antes de tomar decisiones con estos números."
)
