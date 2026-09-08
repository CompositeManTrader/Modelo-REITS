"""Modelo de inmueble en renta en CDMX, con honestidad brutal sobre sus costos.

El comparativo central del proyecto. La mayoría de los análisis de "invertir en un
departamento" comparan la renta bruta contra el yield de un instrumento financiero
y concluyen que el ladrillo gana. Este módulo cobra todo lo que el ladrillo cobra:

Entrada
    ISAI, notario, avalúo y registro suman 6–8% del valor **antes** de que el
    inmueble genere un solo peso.

Operación (como porcentaje de la renta bruta)
    Mantenimiento condominal −13%, vacancia −4% (un mes cada dos años),
    predial y seguro −3%, reserva de CapEx −13%. Neto antes de ISR ≈ 4.0%
    sobre el precio.

Salida
    Comisión de 3–5% más ISR sobre la ganancia. La fricción de ida y vuelta
    ronda 12% del valor del activo.

Advertencia sobre los índices
-----------------------------
Los índices que reportan 7.6% de rendimiento bruto se calculan sobre **precios de
anuncio**, no de operación. El anuncio no es el precio: en CDMX la diferencia
entre lo que se pide y lo que se paga es material, y el rendimiento se calcula
sobre el denominador equivocado.

Restricción de modelación explícita
-----------------------------------
Las horas propias del operador van a **costo cero**. El NPV mide retorno sobre
capital invertido, no sobre tiempo. La autoadministración del inmueble no resta
nada al modelo — y tampoco suma.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from scipy import optimize

from src.fiscal.mexico import impuesto_dividendo, isr_arrendamiento
from src.portafolio.metricas import tir

# --------------------------------------------------------------------------------------
# Supuestos por omisión, con su rango típico documentado
# --------------------------------------------------------------------------------------

COSTOS_ENTRADA_TIPICOS = (0.06, 0.08)
COMISION_VENTA_TIPICA = (0.03, 0.05)
TASA_HIPOTECA_TIPICA = (0.095, 0.125)
RENDIMIENTO_BRUTO_CDMX = (0.05, 0.07)
RENDIMIENTO_NETO_CDMX = (0.040, 0.055)

AVISO_INDICES = (
    "Los índices que reportan 7.6% de rendimiento bruto en CDMX se calculan sobre precios "
    "de anuncio, no de operación. El rendimiento real sobre el precio efectivamente pagado "
    "queda entre 5% y 7% bruto, y entre 4% y 5.5% neto."
)


@dataclass
class SupuestosInmueble:
    """Todos los parámetros del inmueble. Cada uno es discutible; ninguno es opcional."""

    precio: float
    renta_mensual: float

    # Entrada
    isai: float = 0.03  # impuesto sobre adquisición de inmuebles
    notario: float = 0.02
    avaluo_y_registro: float = 0.015

    # Operación, como fracción de la renta BRUTA anual
    mantenimiento_pct_renta: float = 0.13
    vacancia_pct_renta: float = 0.04  # un mes cada dos años
    predial_seguro_pct_renta: float = 0.03
    reserva_capex_pct_renta: float = 0.13

    # Fiscal
    predial_anual: float = 0.0  # si es 0 se estima desde predial_seguro_pct_renta
    ingreso_por_sueldo: float = 0.0  # apila la renta sobre el sueldo si es > 0

    # Salida
    comision_venta: float = 0.04
    isr_ganancia_venta: float = 0.20  # tasa efectiva estimada sobre la ganancia

    # Trayectoria
    plusvalia_anual: float = 0.04
    crecimiento_renta_anual: float = 0.04
    inflacion: float = 0.04
    anios: int = 10

    # Apalancamiento
    monto_hipoteca: float = 0.0
    tasa_hipoteca: float = 0.115
    plazo_hipoteca_anios: int = 20

    @property
    def costos_entrada_pct(self) -> float:
        return self.isai + self.notario + self.avaluo_y_registro

    @property
    def costos_entrada(self) -> float:
        return self.precio * self.costos_entrada_pct

    @property
    def renta_bruta_anual(self) -> float:
        return self.renta_mensual * 12.0

    @property
    def rendimiento_bruto(self) -> float:
        return self.renta_bruta_anual / self.precio if self.precio else 0.0

    @property
    def gastos_pct_renta(self) -> float:
        return (
            self.mantenimiento_pct_renta
            + self.vacancia_pct_renta
            + self.predial_seguro_pct_renta
            + self.reserva_capex_pct_renta
        )

    @property
    def capital_propio(self) -> float:
        return self.precio + self.costos_entrada - self.monto_hipoteca


# --------------------------------------------------------------------------------------
# Operación anual
# --------------------------------------------------------------------------------------


@dataclass
class OperacionAnual:
    renta_bruta: float
    mantenimiento: float
    vacancia: float
    predial_seguro: float
    reserva_capex: float
    noi_antes_isr: float
    isr: float
    flujo_neto: float
    rendimiento_neto_sobre_precio: float

    def como_tabla(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"concepto": "Renta bruta", "monto": self.renta_bruta,
                 "pct_renta": 1.0},
                {"concepto": "Cuota de mantenimiento condominal", "monto": -self.mantenimiento,
                 "pct_renta": -self.mantenimiento / self.renta_bruta if self.renta_bruta else 0},
                {"concepto": "Vacancia (1 mes cada 2 años)", "monto": -self.vacancia,
                 "pct_renta": -self.vacancia / self.renta_bruta if self.renta_bruta else 0},
                {"concepto": "Predial y seguro", "monto": -self.predial_seguro,
                 "pct_renta": -self.predial_seguro / self.renta_bruta if self.renta_bruta else 0},
                {"concepto": "Reserva de CapEx", "monto": -self.reserva_capex,
                 "pct_renta": -self.reserva_capex / self.renta_bruta if self.renta_bruta else 0},
                {"concepto": "NETO ANTES DE ISR", "monto": self.noi_antes_isr,
                 "pct_renta": self.noi_antes_isr / self.renta_bruta if self.renta_bruta else 0},
                {"concepto": "ISR sobre arrendamiento", "monto": -self.isr,
                 "pct_renta": -self.isr / self.renta_bruta if self.renta_bruta else 0},
                {"concepto": "FLUJO NETO", "monto": self.flujo_neto,
                 "pct_renta": self.flujo_neto / self.renta_bruta if self.renta_bruta else 0},
            ]
        )


def operacion_anual(sup: SupuestosInmueble, *, renta_bruta: float | None = None) -> OperacionAnual:
    """Flujo de un año de operación, después de todos los costos y del ISR."""
    renta = renta_bruta if renta_bruta is not None else sup.renta_bruta_anual
    mantenimiento = renta * sup.mantenimiento_pct_renta
    vacancia = renta * sup.vacancia_pct_renta
    predial_seguro = renta * sup.predial_seguro_pct_renta
    capex = renta * sup.reserva_capex_pct_renta
    noi = renta - mantenimiento - vacancia - predial_seguro - capex

    predial = sup.predial_anual if sup.predial_anual > 0 else predial_seguro * 0.6
    # La renta efectivamente cobrada es la base gravable, no el NOI.
    renta_cobrada = renta - vacancia
    res_isr = isr_arrendamiento(
        renta_cobrada, predial_anual=predial, ingreso_por_sueldo=sup.ingreso_por_sueldo
    )

    flujo = noi - res_isr.isr
    return OperacionAnual(
        renta_bruta=renta,
        mantenimiento=mantenimiento,
        vacancia=vacancia,
        predial_seguro=predial_seguro,
        reserva_capex=capex,
        noi_antes_isr=noi,
        isr=res_isr.isr,
        flujo_neto=flujo,
        rendimiento_neto_sobre_precio=flujo / sup.precio if sup.precio else 0.0,
    )


# --------------------------------------------------------------------------------------
# Hipoteca
# --------------------------------------------------------------------------------------


@dataclass
class Hipoteca:
    monto: float
    tasa_anual: float
    plazo_anios: int
    mensualidad: float
    tabla: pd.DataFrame

    @property
    def pago_anual(self) -> float:
        return self.mensualidad * 12.0


def calcular_hipoteca(monto: float, tasa_anual: float, plazo_anios: int) -> Hipoteca:
    """Amortización a mensualidad fija nominal.

    Esa fijeza nominal es el único argumento real del apalancamiento inmobiliario en
    México: la mensualidad no se indiza y la renta sí, así que la deuda es una
    posición corta en pesos nominales que la inflación va licuando. El carry, en
    cambio, es negativo desde el día uno.
    """
    if monto <= 0:
        return Hipoteca(0.0, tasa_anual, plazo_anios, 0.0, pd.DataFrame())
    i = tasa_anual / 12.0
    n = plazo_anios * 12
    mensualidad = monto * i / (1.0 - (1.0 + i) ** -n) if i > 0 else monto / n

    saldo = monto
    filas = []
    for mes in range(1, n + 1):
        interes = saldo * i
        capital = mensualidad - interes
        saldo = max(0.0, saldo - capital)
        filas.append(
            {"mes": mes, "anio": (mes - 1) // 12 + 1, "interes": interes,
             "capital": capital, "saldo": saldo}
        )
    return Hipoteca(monto, tasa_anual, plazo_anios, mensualidad, pd.DataFrame(filas))


@dataclass
class DiagnosticoCarry:
    rendimiento_bruto: float
    tasa_hipoteca: float
    carry: float
    es_negativo: bool
    erosion_real_deuda_anual: float
    valor_presente_erosion: float
    mensaje: str


def diagnosticar_carry(sup: SupuestosInmueble) -> DiagnosticoCarry:
    """Contrasta el rendimiento bruto contra el costo de la hipoteca.

    Con hipotecas al 9.5–12.5% (promedio ~11.5%) contra un rendimiento bruto de 6%,
    **el carry es negativo**: el inmueble no paga su propia deuda. Quien apalanca
    está pagando por sostener la posición, no cobrando por ella.

    El argumento a favor no es el flujo sino la erosión inflacionaria: la
    mensualidad es nominal fija a 20 años mientras la renta se indiza. Aquí se
    cuantifica cuánto vale esa erosión en vez de invocarla.
    """
    carry = sup.rendimiento_bruto - sup.tasa_hipoteca
    hip = calcular_hipoteca(sup.monto_hipoteca, sup.tasa_hipoteca, sup.plazo_hipoteca_anios)

    # Valor presente del ahorro real: la mensualidad nominal fija vale cada año menos.
    erosion_vp = 0.0
    for anio in range(1, sup.plazo_hipoteca_anios + 1):
        nominal = hip.pago_anual
        real = nominal / (1.0 + sup.inflacion) ** anio
        erosion_vp += (nominal - real) / (1.0 + sup.inflacion) ** anio
    erosion_anual = sup.monto_hipoteca * sup.inflacion

    mensaje = (
        f"Rendimiento bruto {sup.rendimiento_bruto:.2%} contra tasa hipotecaria "
        f"{sup.tasa_hipoteca:.2%}: carry de {carry:+.2%}. "
    )
    if carry < 0:
        mensaje += (
            "El carry es NEGATIVO. El inmueble no paga su propia deuda; la diferencia sale "
            "de tu bolsillo cada mes. El argumento a favor del apalancamiento no es el flujo: "
            f"es que la mensualidad es nominal fija y la inflación de {sup.inflacion:.1%} la va "
            f"licuando. Esa erosión vale aproximadamente {erosion_vp:,.0f} en valor presente "
            "sobre la vida del crédito. Es una apuesta a la inflación, no una inversión de renta."
        )
    else:
        mensaje += "El carry es positivo, situación poco común en el mercado hipotecario mexicano."

    return DiagnosticoCarry(
        rendimiento_bruto=sup.rendimiento_bruto,
        tasa_hipoteca=sup.tasa_hipoteca,
        carry=carry,
        es_negativo=carry < 0,
        erosion_real_deuda_anual=erosion_anual,
        valor_presente_erosion=erosion_vp,
        mensaje=mensaje,
    )


# --------------------------------------------------------------------------------------
# Flujo completo del proyecto
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoInmueble:
    flujos: pd.Series
    npv: float
    tir_proyecto: float | None
    flujo_neto_anual_promedio: float
    rendimiento_neto_sobre_precio: float
    valor_salida_neto: float
    friccion_transaccion: float
    isr_salida_pct: float
    detalle: pd.DataFrame
    carry: DiagnosticoCarry
    supuestos: SupuestosInmueble
    advertencias: list[str] = field(default_factory=list)

    def como_texto(self) -> str:
        return (
            f"Rendimiento neto sobre precio {self.rendimiento_neto_sobre_precio:.2%} "
            f"sobre el precio de operación, no de anuncio. "
            f"TIR del proyecto a {self.supuestos.anios} años: "
            f"{'n/d' if self.tir_proyecto is None else format(self.tir_proyecto, '.2%')}. "
            f"Fricción de transacción de ida y vuelta {self.friccion_transaccion:.1%} del valor "
            f"del activo, más {self.isr_salida_pct:.1%} de ISR sobre la ganancia al salir."
        )

    @property
    def friccion_total(self) -> float:
        return self.friccion_transaccion + self.isr_salida_pct


def evaluar_inmueble(
    sup: SupuestosInmueble, *, tasa_descuento: float = 0.09
) -> ResultadoInmueble:
    """Flujo completo: entrada, operación, servicio de deuda y salida.

    Devuelve NPV, TIR y el flujo neto anual, con la fricción de ida y vuelta
    explícita. Todos los flujos son **nominales** y la tasa de descuento también,
    para que la comparación con un portafolio nominal sea consistente.
    """
    hip = calcular_hipoteca(sup.monto_hipoteca, sup.tasa_hipoteca, sup.plazo_hipoteca_anios)
    fechas = pd.date_range("2025-12-31", periods=sup.anios + 1, freq="YE")

    inversion_inicial = -(sup.precio + sup.costos_entrada - sup.monto_hipoteca)
    flujos = [inversion_inicial]
    filas = [
        {
            "anio": 0,
            "renta_bruta": 0.0,
            "flujo_operacion": 0.0,
            "servicio_deuda": 0.0,
            "flujo_neto": inversion_inicial,
            "valor_inmueble": sup.precio,
            "saldo_hipoteca": sup.monto_hipoteca,
        }
    ]

    for anio in range(1, sup.anios + 1):
        renta = sup.renta_bruta_anual * (1.0 + sup.crecimiento_renta_anual) ** (anio - 1)
        op = operacion_anual(sup, renta_bruta=renta)
        servicio = hip.pago_anual if anio <= sup.plazo_hipoteca_anios else 0.0
        flujo = op.flujo_neto - servicio
        valor = sup.precio * (1.0 + sup.plusvalia_anual) ** anio
        saldo = (
            float(hip.tabla.loc[hip.tabla["anio"] == anio, "saldo"].iloc[-1])
            if not hip.tabla.empty and (hip.tabla["anio"] == anio).any()
            else 0.0
        )

        if anio == sup.anios:
            comision = valor * sup.comision_venta
            ganancia = max(0.0, valor - sup.precio)
            isr_venta = ganancia * sup.isr_ganancia_venta
            valor_salida = valor - comision - isr_venta - saldo
            flujo += valor_salida
        filas.append(
            {
                "anio": anio,
                "renta_bruta": renta,
                "flujo_operacion": op.flujo_neto,
                "servicio_deuda": -servicio,
                "flujo_neto": flujo,
                "valor_inmueble": valor,
                "saldo_hipoteca": saldo,
            }
        )
        flujos.append(flujo)

    serie = pd.Series(flujos, index=fechas)
    npv = float(sum(f / (1.0 + tasa_descuento) ** i for i, f in enumerate(flujos)))

    valor_final = sup.precio * (1.0 + sup.plusvalia_anual) ** sup.anios
    comision = valor_final * sup.comision_venta
    ganancia = max(0.0, valor_final - sup.precio)
    isr_venta = ganancia * sup.isr_ganancia_venta
    valor_salida_neto = valor_final - comision - isr_venta

    # Se separan a propósito. La fricción de transacción (entrada + comisión de venta)
    # ronda 12% del valor y se paga siempre; el ISR sobre la ganancia depende de cuánto
    # se apreció el inmueble y del plazo de tenencia. Sumarlos en un solo número esconde
    # que el primero se paga aunque el inmueble no suba un peso.
    friccion_transaccion = sup.costos_entrada_pct + sup.comision_venta
    isr_salida_pct = (isr_venta / valor_final) if valor_final else 0.0

    op_base = operacion_anual(sup)
    detalle = pd.DataFrame(filas)
    operativos = detalle[detalle["anio"] > 0]["flujo_operacion"]

    advertencias = [
        AVISO_INDICES,
        "Las horas propias de administración van a costo cero por decisión de modelación: "
        "el NPV mide retorno sobre capital invertido, no sobre tiempo. Si valoras tu tiempo, "
        "el resultado real es peor que este.",
    ]
    carry = diagnosticar_carry(sup)
    if carry.es_negativo and sup.monto_hipoteca > 0:
        advertencias.append(carry.mensaje)

    return ResultadoInmueble(
        flujos=serie,
        npv=npv,
        tir_proyecto=tir(serie),
        flujo_neto_anual_promedio=float(operativos.mean()) if not operativos.empty else 0.0,
        rendimiento_neto_sobre_precio=op_base.rendimiento_neto_sobre_precio,
        valor_salida_neto=valor_salida_neto,
        friccion_transaccion=friccion_transaccion,
        isr_salida_pct=isr_salida_pct,
        detalle=detalle,
        carry=carry,
        supuestos=sup,
        advertencias=advertencias,
    )


# --------------------------------------------------------------------------------------
# Riesgos cuantificados, no mencionados
# --------------------------------------------------------------------------------------


@dataclass
class EscenarioRiesgo:
    nombre: str
    impacto_flujo: float
    impacto_npv: float
    probabilidad_supuesta: float
    descripcion: str


def escenario_inquilino_moroso(
    sup: SupuestosInmueble,
    *,
    meses_sin_ingreso: int = 18,
    costos_legales: float = 80_000.0,
    tasa_descuento: float = 0.09,
) -> EscenarioRiesgo:
    """Inquilino moroso: 12–24 meses sin ingreso más costos legales.

    En CDMX el desalojo por la vía judicial toma de uno a dos años y durante ese
    tiempo el inmueble no produce, pero el mantenimiento, el predial y — si hay —
    la hipoteca se siguen pagando. Es el riesgo que más veces convierte un
    rendimiento de 4% en uno negativo.
    """
    renta_perdida = sup.renta_mensual * meses_sin_ingreso
    gastos_que_siguen = (
        sup.renta_bruta_anual * (sup.mantenimiento_pct_renta + sup.predial_seguro_pct_renta)
    ) * (meses_sin_ingreso / 12.0)
    hip = calcular_hipoteca(sup.monto_hipoteca, sup.tasa_hipoteca, sup.plazo_hipoteca_anios)
    servicio = hip.mensualidad * meses_sin_ingreso

    impacto = -(renta_perdida + gastos_que_siguen + costos_legales + servicio)
    return EscenarioRiesgo(
        nombre=f"Inquilino moroso ({meses_sin_ingreso} meses)",
        impacto_flujo=impacto,
        impacto_npv=impacto / (1.0 + tasa_descuento),
        probabilidad_supuesta=0.10,
        descripcion=(
            f"Pérdida de {renta_perdida:,.0f} de renta, {gastos_que_siguen:,.0f} de gastos que "
            f"siguen corriendo, {costos_legales:,.0f} de costos legales"
            + (f" y {servicio:,.0f} de servicio de deuda" if servicio > 0 else "")
            + f". Impacto total {impacto:,.0f}, equivalente a "
            f"{abs(impacto) / sup.renta_bruta_anual:.1f} años de renta bruta."
        ),
    )


def escenario_sismo(
    sup: SupuestosInmueble, *, meses_reconstruccion: int = 12, deducible: float = 0.02
) -> EscenarioRiesgo:
    """Riesgo sísmico: pérdida del ingreso durante la reconstrucción.

    El seguro cubre la estructura; no cubre bien el ingreso perdido ni el deducible,
    y la CDMX está sobre un lago en zona sísmica. Es un riesgo de concentración
    geográfica que un portafolio de REITs diversificado no tiene.
    """
    renta_perdida = sup.renta_mensual * meses_reconstruccion
    costo_deducible = sup.precio * deducible
    impacto = -(renta_perdida + costo_deducible)
    return EscenarioRiesgo(
        nombre=f"Sismo con {meses_reconstruccion} meses de reconstrucción",
        impacto_flujo=impacto,
        impacto_npv=impacto,
        probabilidad_supuesta=0.05,
        descripcion=(
            f"{renta_perdida:,.0f} de ingreso perdido más {costo_deducible:,.0f} de deducible. "
            "El seguro cubre estructura, no lucro cesante completo."
        ),
    )


RIESGOS_CUALITATIVOS: tuple[dict, ...] = (
    {
        "riesgo": "Concentración",
        "inmueble": "Un inmueble, una colonia, un inquilino.",
        "reit": "Cientos de inquilinos corporativos con contratos de 5 a 15 años.",
        "cuantificacion": "La quiebra del único inquilino cuesta 100% del ingreso; en un REIT, menos de 1%.",
    },
    {
        "riesgo": "Iliquidez",
        "inmueble": "3 a 9 meses para vender, sin posibilidad de vender parcialmente.",
        "reit": "Liquidez diaria y venta parcial en cualquier proporción.",
        "cuantificacion": "Vender rápido implica descuento de 10–15% sobre el precio de lista.",
    },
    {
        "riesgo": "Sísmico",
        "inmueble": "Pérdida del ingreso durante la reconstrucción; deducible a cargo del dueño.",
        "reit": "Diversificado geográficamente; el evento local no mueve el portafolio.",
        "cuantificacion": "Ver escenario_sismo().",
    },
    {
        "riesgo": "Regulatorio",
        "inmueble": "Límites a renta corta y propuestas de tope a incrementos de renta.",
        "reit": "Expuesto a regulación, pero diversificado entre jurisdicciones.",
        "cuantificacion": "Un tope de incrementos a la inflación menos 1% recorta el crecimiento real a negativo.",
    },
    {
        "riesgo": "Tiempo de administración",
        "inmueble": "Búsqueda de inquilino, cobranza, reparaciones, trato con la administración.",
        "reit": "Cero.",
        "cuantificacion": "Va a costo cero por decisión de modelación. El NPV mide capital, no tiempo.",
    },
)


def tabla_riesgos(sup: SupuestosInmueble, tasa_descuento: float = 0.09) -> pd.DataFrame:
    """Riesgos cuantificados y cualitativos en una sola tabla."""
    cuantificados = [
        escenario_inquilino_moroso(sup, tasa_descuento=tasa_descuento),
        escenario_sismo(sup),
    ]
    filas = [
        {
            "riesgo": e.nombre,
            "impacto_flujo": e.impacto_flujo,
            "impacto_npv": e.impacto_npv,
            "probabilidad_supuesta": e.probabilidad_supuesta,
            "descripcion": e.descripcion,
        }
        for e in cuantificados
    ]
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# Comparativo contra portafolio de REITs
# --------------------------------------------------------------------------------------


@dataclass
class Comparativo:
    npv_inmueble: float
    npv_reits: float
    tir_inmueble: float | None
    tir_reits: float | None
    flujo_anual_inmueble: float
    flujo_anual_reits: float
    capital_inmueble: float
    capital_reits_equivalente: float
    plusvalia_necesaria: float | None
    ganador: str
    mensaje: str


def comparar_con_reits(
    sup: SupuestosInmueble,
    *,
    yield_neto_reits: float,
    crecimiento_reits: float = 0.03,
    tasa_descuento: float = 0.09,
) -> Comparativo:
    """Compara el inmueble contra un portafolio de REITs con el **mismo capital**.

    Ambos reciben el mismo desembolso inicial y el mismo horizonte, y ambos se
    miden por NPV y TIR. El ``yield_neto_reits`` debe venir ya después de
    impuestos mexicanos, o la comparación no es honesta.
    """
    res_inm = evaluar_inmueble(sup, tasa_descuento=tasa_descuento)
    capital = sup.precio + sup.costos_entrada

    fechas = pd.date_range("2025-12-31", periods=sup.anios + 1, freq="YE")
    flujos_reits = [-capital]
    valor = capital
    for anio in range(1, sup.anios + 1):
        ingreso = valor * yield_neto_reits
        valor *= 1.0 + crecimiento_reits
        flujo = ingreso
        if anio == sup.anios:
            flujo += valor
        flujos_reits.append(flujo)
    serie_reits = pd.Series(flujos_reits, index=fechas)
    npv_reits = float(sum(f / (1.0 + tasa_descuento) ** i for i, f in enumerate(flujos_reits)))

    plusvalia = plusvalia_necesaria_para_empatar(
        sup, yield_neto_reits=yield_neto_reits, crecimiento_reits=crecimiento_reits,
        tasa_descuento=tasa_descuento,
    )

    ganador = "Inmueble" if res_inm.npv > npv_reits else "Portafolio de REITs"
    mensaje = (
        f"Con el mismo capital de {capital:,.0f}, el NPV del inmueble es {res_inm.npv:,.0f} y "
        f"el del portafolio de REITs es {npv_reits:,.0f}. Gana {ganador.lower()}. "
    )
    if plusvalia is not None:
        mensaje += (
            f"Para empatar, el departamento necesita {plusvalia:.2%} de plusvalía anual "
            f"(supuesto actual: {sup.plusvalia_anual:.2%}). "
        )
        if plusvalia > sup.plusvalia_anual + 0.02:
            mensaje += (
                "Esa plusvalía está muy por encima del supuesto y de la inflación: la tesis "
                "del inmueble depende casi por completo de la apreciación, no de la renta."
            )

    return Comparativo(
        npv_inmueble=res_inm.npv,
        npv_reits=npv_reits,
        tir_inmueble=res_inm.tir_proyecto,
        tir_reits=tir(serie_reits),
        flujo_anual_inmueble=res_inm.flujo_neto_anual_promedio,
        flujo_anual_reits=capital * yield_neto_reits,
        capital_inmueble=capital,
        capital_reits_equivalente=capital,
        plusvalia_necesaria=plusvalia,
        ganador=ganador,
        mensaje=mensaje,
    )


def plusvalia_necesaria_para_empatar(
    sup: SupuestosInmueble,
    *,
    yield_neto_reits: float,
    crecimiento_reits: float = 0.03,
    tasa_descuento: float = 0.09,
) -> float | None:
    """Solver inverso: ¿cuánta plusvalía anual necesita el departamento para empatar?

    Este número suele ser revelador. Cuando sale muy por encima de la inflación,
    queda claro que la tesis del inmueble no es la renta sino una apuesta
    direccional a la apreciación — que es una tesis legítima, pero distinta y con
    otro perfil de riesgo.
    """
    capital = sup.precio + sup.costos_entrada
    flujos_reits = [-capital]
    valor = capital
    for anio in range(1, sup.anios + 1):
        ingreso = valor * yield_neto_reits
        valor *= 1.0 + crecimiento_reits
        flujos_reits.append(ingreso + (valor if anio == sup.anios else 0.0))
    npv_reits = float(sum(f / (1.0 + tasa_descuento) ** i for i, f in enumerate(flujos_reits)))

    def brecha(plusvalia: float) -> float:
        s = SupuestosInmueble(**{**sup.__dict__, "plusvalia_anual": float(plusvalia)})
        return evaluar_inmueble(s, tasa_descuento=tasa_descuento).npv - npv_reits

    try:
        return float(optimize.brentq(brecha, -0.20, 0.50, xtol=1e-6, maxiter=200))
    except ValueError:
        return None


def capital_para_meta_de_ingreso(
    sup: SupuestosInmueble, meta_ingreso_anual: float
) -> dict[str, float]:
    """Cuánto capital hace falta en cada vehículo para la misma meta de ingreso."""
    op = operacion_anual(sup)
    rend_inmueble = op.rendimiento_neto_sobre_precio
    capital_inmueble = meta_ingreso_anual / rend_inmueble if rend_inmueble > 0 else float("inf")
    return {
        "rendimiento_neto_inmueble": rend_inmueble,
        "capital_requerido_inmueble": capital_inmueble,
        "numero_de_inmuebles": capital_inmueble / sup.precio if sup.precio else float("inf"),
        "nota": (
            "El número de inmuebles es indivisible: no puedes comprar 2.7 departamentos. "
            "Esa granularidad es un costo real de concentración que el portafolio no tiene."
        ),
    }


# --------------------------------------------------------------------------------------
# Portafolio inmobiliario propio del usuario (innovación 3.3.f)
# --------------------------------------------------------------------------------------


def tir_real_de_inmueble_propio(
    precio_compra: float,
    fecha_compra,
    renta_mensual_actual: float,
    gastos_anuales: float,
    valor_actual: float,
    *,
    saldo_hipoteca: float = 0.0,
    inflacion_acumulada: float = 1.0,
) -> dict[str, float | None]:
    """TIR real de un inmueble que el usuario ya tiene.

    Simplificación deliberada: se asume renta constante en términos reales desde la
    compra. Con el histórico de rentas efectivamente cobradas el número mejora, pero
    esta aproximación ya basta para el contraste que interesa.
    """
    fecha = pd.Timestamp(fecha_compra)
    hoy = pd.Timestamp.today().normalize()
    anios = max(1, int((hoy - fecha).days / 365.25))

    flujo_anual = renta_mensual_actual * 12.0 - gastos_anuales
    fechas = pd.date_range(fecha, periods=anios + 1, freq="YE")
    flujos = [-precio_compra] + [flujo_anual] * anios
    flujos[-1] += valor_actual - saldo_hipoteca
    serie = pd.Series(flujos[: len(fechas)], index=fechas)

    tir_nominal = tir(serie)
    inflacion_anual = inflacion_acumulada ** (1.0 / anios) - 1.0 if anios > 0 else 0.0
    tir_real = (
        (1.0 + tir_nominal) / (1.0 + inflacion_anual) - 1.0 if tir_nominal is not None else None
    )
    return {
        "anios_tenencia": float(anios),
        "flujo_anual_neto": flujo_anual,
        "rendimiento_corriente": flujo_anual / valor_actual if valor_actual else None,
        "tir_nominal": tir_nominal,
        "tir_real": tir_real,
        "plusvalia_anualizada": (valor_actual / precio_compra) ** (1.0 / anios) - 1.0
        if precio_compra > 0
        else None,
    }


def comparar_portafolio_propio(
    inmuebles: pd.DataFrame, *, yield_neto_reits: float, inflacion: float = 0.045
) -> pd.DataFrame:
    """Compara cada inmueble real del usuario contra un REIT equivalente.

    Es el corazón del objetivo del proyecto: no "¿conviene comprar un departamento?"
    en abstracto, sino "¿los departamentos que ya tengo están rindiendo más que la
    alternativa?".
    """
    if inmuebles.empty:
        return pd.DataFrame()
    filas = []
    for _, r in inmuebles.iterrows():
        valor = float(r.get("valor_actual") or r["precio_compra"])
        gastos = (
            float(r.get("mantenimiento_mensual") or 0) * 12
            + float(r.get("predial_anual") or 0)
            + float(r.get("seguro_anual") or 0)
        )
        anios = max(1, int((pd.Timestamp.today() - pd.Timestamp(r["fecha_compra"])).days / 365.25))
        res = tir_real_de_inmueble_propio(
            float(r["precio_compra"]),
            r["fecha_compra"],
            float(r["renta_mensual"]),
            gastos,
            valor,
            saldo_hipoteca=float(r.get("saldo_hipoteca") or 0),
            inflacion_acumulada=(1.0 + inflacion) ** anios,
        )
        filas.append(
            {
                "nombre": r["nombre"],
                "valor_actual": valor,
                "rendimiento_corriente": res["rendimiento_corriente"],
                "tir_nominal": res["tir_nominal"],
                "tir_real": res["tir_real"],
                "plusvalia_anualizada": res["plusvalia_anualizada"],
                "yield_neto_reits": yield_neto_reits,
                "brecha_vs_reits": (
                    (res["rendimiento_corriente"] or 0) - yield_neto_reits
                ),
            }
        )
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# Mi portafolio contra UNA emisora concreta
# --------------------------------------------------------------------------------------
#
# Es la pregunta que el usuario hace de verdad, y la que la pantalla no contestaba:
# no "¿conviene un departamento?" en abstracto contra un yield inventado en un
# deslizador, sino "¿mis departamentos rinden más que Realty Income?".
#
# La comparación solo vale si los dos lados llegan al mismo punto: pesos en el
# bolsillo, después de impuestos, sobre el valor de mercado de hoy. Los dos lados
# pagan, y pagan distinto:
#
#   El inmueble  renta bruta − gastos − ISR de arrendamiento. Y el ISR depende de
#                si tienes sueldo: como único ingreso la tasa efectiva ronda 5%,
#                apilado sobre un sueldo entra en marginal de 30–35%.
#   El REIT      dividendo bruto − retención de EE. UU. − ISR mexicano. Con W-8BEN
#                la combinada ronda 20%; sin él, 40%.
#
# Comparar el yield BRUTO del inmueble contra el NETO del REIT —o al revés— es el
# error que hace ganar al ladrillo en casi todos los análisis que circulan.


@dataclass
class LadoInmuebles:
    """El lado del ladrillo, del bruto al bolsillo."""

    n_propiedades: int
    valor_mercado: float
    renta_bruta_anual: float
    gastos_anuales: float
    isr_anual: float
    flujo_neto_anual: float
    yield_bruto: float
    yield_neto: float
    tasa_efectiva_isr: float

    def como_tabla(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"concepto": "Renta bruta", "monto": self.renta_bruta_anual},
            {"concepto": "Gastos de operación", "monto": -self.gastos_anuales},
            {"concepto": "ISR de arrendamiento", "monto": -self.isr_anual},
            {"concepto": "Al bolsillo", "monto": self.flujo_neto_anual},
        ])


@dataclass
class LadoEmisora:
    """El lado del REIT, del bruto al bolsillo."""

    ticker: str
    yield_bruto: float
    retencion_eeuu: float
    isr_mexico: float
    yield_neto: float
    crecimiento: float | None

    def como_tabla(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"concepto": "Dividendo bruto", "monto": self.yield_bruto},
            {"concepto": "Retención EE. UU.", "monto": -self.retencion_eeuu},
            {"concepto": "ISR adicional México", "monto": -self.isr_mexico},
            {"concepto": "Al bolsillo", "monto": self.yield_neto},
        ])


@dataclass
class Duelo:
    """El resultado del duelo, con lo necesario para explicarlo sin abrir el código."""

    inmuebles: LadoInmuebles
    emisora: LadoEmisora
    brecha_bps: float
    ganador: str
    mensaje: str
    plusvalia_necesaria: float | None

    @property
    def hay_inmuebles(self) -> bool:
        return self.inmuebles.n_propiedades > 0


def _agregado_de_inmuebles(inmuebles: pd.DataFrame) -> tuple[float, float, float]:
    """Valor de mercado, renta bruta anual y gastos anuales del portafolio."""
    valor = renta = gastos = 0.0
    for _, r in inmuebles.iterrows():
        valor += float(r.get("valor_actual") or r.get("precio_compra") or 0.0)
        renta += float(r.get("renta_mensual") or 0.0) * 12.0
        gastos += (
            float(r.get("mantenimiento_mensual") or 0.0) * 12.0
            + float(r.get("predial_anual") or 0.0)
            + float(r.get("seguro_anual") or 0.0)
        )
    return valor, renta, gastos


def duelo_portafolio_contra_emisora(
    inmuebles: pd.DataFrame,
    *,
    ticker: str,
    yield_bruto_emisora: float,
    crecimiento_emisora: float | None = None,
    plusvalia_esperada: float = 0.04,
    ingreso_por_sueldo: float = 0.0,
    tiene_w8ben: bool = True,
) -> Duelo:
    """Mi portafolio de inmuebles contra una emisora, neto de impuestos de los dos lados.

    El único número comparable es el yield NETO sobre el valor de mercado de hoy:
    lo que cada peso invertido pone en el bolsillo este año. Sobre el valor de HOY
    y no sobre el precio de compra, porque la pregunta es hacia adelante —"¿dejo el
    dinero aquí o lo muevo?"— y el precio que pagaste hace ocho años ya no es una
    opción disponible.

    La ``plusvalia_necesaria`` cierra la pregunta que sigue: si el REIT gana en
    flujo, cuánto tiene que apreciarse el ladrillo cada año para empatar. Cuando
    ese número sale muy por encima de la inflación, la tesis del inmueble no es la
    renta sino una apuesta direccional a la apreciación — que es legítima, pero es
    otra tesis y tiene otro riesgo.
    """
    valor, renta_bruta, gastos = _agregado_de_inmuebles(inmuebles)
    predial = float(pd.to_numeric(inmuebles.get("predial_anual"), errors="coerce").fillna(0).sum()) \
        if "predial_anual" in inmuebles else 0.0

    fiscal = isr_arrendamiento(
        renta_bruta, predial_anual=predial, ingreso_por_sueldo=ingreso_por_sueldo
    )
    flujo_neto = renta_bruta - gastos - fiscal.isr
    lado_inmuebles = LadoInmuebles(
        n_propiedades=int(len(inmuebles)),
        valor_mercado=valor,
        renta_bruta_anual=renta_bruta,
        gastos_anuales=gastos,
        isr_anual=fiscal.isr,
        flujo_neto_anual=flujo_neto,
        yield_bruto=renta_bruta / valor if valor else 0.0,
        yield_neto=flujo_neto / valor if valor else 0.0,
        tasa_efectiva_isr=fiscal.isr / renta_bruta if renta_bruta else 0.0,
    )

    dividendo = impuesto_dividendo(float(yield_bruto_emisora), tiene_w8ben=tiene_w8ben)
    lado_emisora = LadoEmisora(
        ticker=ticker,
        yield_bruto=float(yield_bruto_emisora),
        retencion_eeuu=dividendo.retencion_eeuu,
        isr_mexico=dividendo.isr_mexico,
        yield_neto=dividendo.neto,
        crecimiento=crecimiento_emisora,
    )

    brecha = lado_inmuebles.yield_neto - lado_emisora.yield_neto
    if lado_inmuebles.n_propiedades == 0:
        ganador, mensaje = "—", "Captura al menos una propiedad para poder comparar."
    elif brecha > 0:
        ganador = "Tus inmuebles"
        mensaje = (
            f"Tus propiedades ponen {brecha * 10_000:,.0f} puntos base más en el bolsillo cada "
            f"año que {ticker}, ya con el ISR de arrendamiento descontado y con la retención "
            "de EE. UU. descontada del otro lado. Eso es sobre el FLUJO; falta el riesgo de "
            "concentración, la iliquidez y las horas que te cuesta administrarlos."
        )
    else:
        ganador = ticker
        mensaje = (
            f"{ticker} pone {abs(brecha) * 10_000:,.0f} puntos base más en el bolsillo cada año "
            "que tus propiedades, ya neto de impuestos de los dos lados. Para que el ladrillo "
            "empate hace falta plusvalía, y abajo está cuánta."
        )

    # Cuánta apreciación anual necesita el ladrillo para cerrar la brecha de flujo.
    plusvalia_necesaria = (
        lado_emisora.yield_neto - lado_inmuebles.yield_neto + plusvalia_esperada
        if lado_inmuebles.n_propiedades
        else None
    )
    return Duelo(
        inmuebles=lado_inmuebles,
        emisora=lado_emisora,
        brecha_bps=brecha * 10_000,
        ganador=ganador,
        mensaje=mensaje,
        plusvalia_necesaria=plusvalia_necesaria,
    )
