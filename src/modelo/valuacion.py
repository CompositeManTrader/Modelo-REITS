"""Valuación individual: cap rate implícito, NAV, P/AFFO, AFFO yield y balance.

Tres cálculos concentran casi todo el error posible en la valuación de un REIT:

1. **Cap rate implícito.** Si el EV no se depura de los activos que no generan
   renta inmobiliaria (cartera de préstamos, coinversiones), el denominador se
   infla y el cap rate sale sesgado a la baja: el REIT parece más caro de lo que
   está.
2. **NAV.** El cap rate de mercado es la palanca más sensible del modelo, así que
   es input del usuario y viene con tabla de sensibilidad. El goodwill se excluye:
   no genera renta.
3. **Dilución oculta.** En estructuras UPREIT el REIT paga adquisiciones con
   unidades de la sociedad operativa que no aparecen en el conteo de acciones
   hasta convertirse. Siempre acciones totalmente diluidas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------
# Insumos
# --------------------------------------------------------------------------------------


@dataclass
class InsumosValuacion:
    """Todo lo que hace falta para valuar un REIT en una fecha.

    Los montos van en la misma unidad (dólares). ``acciones_diluidas`` debe incluir
    las unidades de Operating Partnership convertibles: es el conteo que de verdad
    reparte el flujo.
    """

    ticker: str
    precio: float
    acciones_diluidas: float
    noi_trimestral: float | None = None
    noi_anualizado: float | None = None
    affo_ttm: float | None = None
    affo_por_accion_ttm: float | None = None
    ffo_ttm: float | None = None
    utilidad_neta_ttm: float | None = None
    dividendo_ttm_por_accion: float | None = None
    deuda_total: float = 0.0
    efectivo: float = 0.0
    prestamos_por_cobrar: float = 0.0
    inversiones_no_consolidadas: float = 0.0
    goodwill: float = 0.0
    ebitdare_ttm: float | None = None
    intereses_ttm: float | None = None
    unidades_op: float = 0.0
    sector: str | None = None

    @property
    def capitalizacion(self) -> float:
        return self.precio * self.acciones_diluidas

    @property
    def deuda_neta(self) -> float:
        return self.deuda_total - self.efectivo

    @property
    def noi(self) -> float | None:
        """NOI anualizado. Se prefiere el explícito; si no, se anualiza el trimestral."""
        if self.noi_anualizado is not None:
            return self.noi_anualizado
        if self.noi_trimestral is not None:
            return self.noi_trimestral * 4.0
        return None

    @property
    def activos_sin_renta(self) -> float:
        """Activos del balance que no producen renta inmobiliaria.

        Se restan del EV para que el cap rate implícito compare el NOI contra el
        capital que efectivamente lo genera.
        """
        return self.prestamos_por_cobrar + self.inversiones_no_consolidadas


# --------------------------------------------------------------------------------------
# Métricas de valuación
# --------------------------------------------------------------------------------------


def valor_empresa_ajustado(ins: InsumosValuacion) -> float:
    """``EV ajustado = capitalización + deuda neta − activos que no generan renta``."""
    return ins.capitalizacion + ins.deuda_neta - ins.activos_sin_renta


def cap_rate_implicito(ins: InsumosValuacion) -> float | None:
    """``NOI anualizado ÷ EV ajustado``.

    Es el cap rate al que el mercado está valuando el portafolio del REIT hoy.
    Comparado contra el cap rate de transacciones privadas del mismo tipo de
    inmueble, dice si el papel cotiza con premio o descuento contra el ladrillo.
    """
    noi = ins.noi
    ev = valor_empresa_ajustado(ins)
    if noi is None or ev <= 0:
        return None
    return noi / ev


def affo_yield(ins: InsumosValuacion) -> float | None:
    """``AFFO TTM por acción ÷ precio``. El rendimiento del flujo, no del dividendo."""
    apa = ins.affo_por_accion_ttm
    if apa is None and ins.affo_ttm is not None and ins.acciones_diluidas > 0:
        apa = ins.affo_ttm / ins.acciones_diluidas
    if apa is None or ins.precio <= 0:
        return None
    return apa / ins.precio


def p_affo(ins: InsumosValuacion) -> float | None:
    """Múltiplo precio / AFFO por acción. Es el recíproco del AFFO yield."""
    y = affo_yield(ins)
    return None if not y else 1.0 / y


def dividend_yield(ins: InsumosValuacion) -> float | None:
    if ins.dividendo_ttm_por_accion is None or ins.precio <= 0:
        return None
    return ins.dividendo_ttm_por_accion / ins.precio


def payout_affo(ins: InsumosValuacion) -> float | None:
    """Payout sobre AFFO: la única cobertura que significa algo (P3)."""
    apa = ins.affo_por_accion_ttm
    if apa is None and ins.affo_ttm is not None and ins.acciones_diluidas > 0:
        apa = ins.affo_ttm / ins.acciones_diluidas
    if not apa or ins.dividendo_ttm_por_accion is None:
        return None
    return ins.dividendo_ttm_por_accion / apa


def payout_ffo(ins: InsumosValuacion) -> float | None:
    if not ins.ffo_ttm or ins.acciones_diluidas <= 0 or ins.dividendo_ttm_por_accion is None:
        return None
    return ins.dividendo_ttm_por_accion / (ins.ffo_ttm / ins.acciones_diluidas)


def payout_utilidad_neta(ins: InsumosValuacion) -> float | None:
    """Se calcula solo para contrastarlo: es el número que publican los sitios y está mal.

    Realty Income Q2 2026: payout sobre utilidad neta 222%, sobre AFFO 73%. Mismo
    dividendo, misma empresa, dos conclusiones opuestas.
    """
    if not ins.utilidad_neta_ttm or ins.acciones_diluidas <= 0 or ins.dividendo_ttm_por_accion is None:
        return None
    upa = ins.utilidad_neta_ttm / ins.acciones_diluidas
    if upa == 0:
        return None
    return ins.dividendo_ttm_por_accion / upa


def deuda_neta_ebitdare(ins: InsumosValuacion) -> float | None:
    if not ins.ebitdare_ttm or ins.ebitdare_ttm <= 0:
        return None
    return ins.deuda_neta / ins.ebitdare_ttm


def costo_implicito_deuda(ins: InsumosValuacion) -> float | None:
    """Intereses TTM sobre deuda promedio. Aproxima el cupón efectivo del pasivo."""
    if not ins.intereses_ttm or ins.deuda_total <= 0:
        return None
    return ins.intereses_ttm / ins.deuda_total


def ltv(ins: InsumosValuacion, valor_inmuebles: float | None = None) -> float | None:
    base = valor_inmuebles if valor_inmuebles else valor_empresa_ajustado(ins)
    if not base or base <= 0:
        return None
    return ins.deuda_neta / base


# --------------------------------------------------------------------------------------
# NAV
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoNAV:
    nav_total: float
    nav_por_accion: float
    cap_rate_usado: float
    valor_inmuebles: float
    premio_descuento: float | None
    componentes: dict[str, float] = field(default_factory=dict)

    def como_texto(self) -> str:
        if self.premio_descuento is None:
            return f"NAV/acción {self.nav_por_accion:,.2f} a cap rate {self.cap_rate_usado:.2%}."
        etiqueta = "premio" if self.premio_descuento > 0 else "descuento"
        return (
            f"NAV/acción {self.nav_por_accion:,.2f} a cap rate {self.cap_rate_usado:.2%}; "
            f"el precio cotiza con {etiqueta} de {abs(self.premio_descuento):.1%}."
        )


def calcular_nav(ins: InsumosValuacion, cap_rate_mercado: float) -> ResultadoNAV | None:
    """``NAV = NOI/cap rate + efectivo + préstamos + no consolidadas − deuda total``.

    El goodwill se excluye deliberadamente: no genera renta y sumarlo infla el NAV
    justo en los emisores que más han pagado por adquisiciones.
    """
    noi = ins.noi
    if noi is None or cap_rate_mercado <= 0 or ins.acciones_diluidas <= 0:
        return None

    valor_inmuebles = noi / cap_rate_mercado
    componentes = {
        "valor_inmuebles": valor_inmuebles,
        "efectivo": ins.efectivo,
        "prestamos_por_cobrar": ins.prestamos_por_cobrar,
        "inversiones_no_consolidadas": ins.inversiones_no_consolidadas,
        "deuda_total": -ins.deuda_total,
        "goodwill_excluido": 0.0,  # explícito: se ve en la interfaz que se dejó fuera
    }
    nav_total = sum(componentes.values())
    nav_por_accion = nav_total / ins.acciones_diluidas
    premio = (ins.precio / nav_por_accion - 1.0) if nav_por_accion > 0 else None

    return ResultadoNAV(
        nav_total=nav_total,
        nav_por_accion=nav_por_accion,
        cap_rate_usado=cap_rate_mercado,
        valor_inmuebles=valor_inmuebles,
        premio_descuento=premio,
        componentes=componentes,
    )


def sensibilidad_nav(
    ins: InsumosValuacion,
    cap_rates: np.ndarray | list[float] | None = None,
) -> pd.DataFrame:
    """Tabla de sensibilidad del NAV para cap rates de 5.5% a 8.0%.

    Es la tabla que hay que mirar antes de creerse un NAV puntual: mover el cap
    rate 50 puntos base cambia el NAV/acción más que casi cualquier otro supuesto.
    """
    if cap_rates is None:
        cap_rates = np.arange(0.055, 0.0801, 0.0025)
    filas = []
    for cr in cap_rates:
        nav = calcular_nav(ins, float(cr))
        if nav is None:
            continue
        filas.append(
            {
                "cap_rate": float(cr),
                "nav_por_accion": nav.nav_por_accion,
                "precio": ins.precio,
                "premio_descuento": nav.premio_descuento,
            }
        )
    return pd.DataFrame(filas)


def cap_rate_implicito_en_precio(ins: InsumosValuacion) -> float | None:
    """Cap rate al que el NAV/acción iguala el precio de mercado.

    Da vuelta a la pregunta: en vez de "¿cuál es el NAV?", responde "¿qué cap rate
    está descontando el mercado?". Ese número se compara contra transacciones
    privadas comparables sin depender de un supuesto propio.
    """
    noi = ins.noi
    if noi is None or noi <= 0 or ins.acciones_diluidas <= 0:
        return None
    # precio * acciones = NOI/cr + efectivo + préstamos + no consolidadas − deuda
    resto = ins.efectivo + ins.prestamos_por_cobrar + ins.inversiones_no_consolidadas - ins.deuda_total
    objetivo = ins.capitalizacion - resto
    if objetivo <= 0:
        return None
    return noi / objetivo


# --------------------------------------------------------------------------------------
# Motor de valor y dilución
# --------------------------------------------------------------------------------------


def spread_de_inversion(
    yield_adquisiciones: float | None,
    costo_marginal_capital: float | None,
) -> float | None:
    """``yield de adquisiciones − costo marginal de capital``.

    Es el motor de valor de un REIT que crece por adquisición. Negativo significa
    que cada compra destruye valor por acción aunque suba el AFFO agregado: se
    financia emitiendo acciones baratas para comprar activos caros.
    """
    if yield_adquisiciones is None or costo_marginal_capital is None:
        return None
    return yield_adquisiciones - costo_marginal_capital


def costo_marginal_de_capital(
    ins: InsumosValuacion,
    *,
    peso_deuda: float = 0.35,
    costo_deuda_nueva: float | None = None,
) -> float | None:
    """Costo ponderado de financiar el siguiente dólar de adquisición.

    El costo del capital accionario de un REIT es su AFFO yield: emitir una acción
    a un AFFO yield de 6% cuesta 6%. Esa es la comparación que importa contra el
    cap rate de lo que va a comprar.
    """
    ke = affo_yield(ins)
    kd = costo_deuda_nueva if costo_deuda_nueva is not None else costo_implicito_deuda(ins)
    if ke is None or kd is None:
        return None
    peso_deuda = min(max(peso_deuda, 0.0), 1.0)
    return peso_deuda * kd + (1.0 - peso_deuda) * ke


def dilucion_anual(acciones_actual: float, acciones_hace_un_anio: float) -> float | None:
    """Crecimiento del conteo de acciones totalmente diluidas.

    Se mide contra el crecimiento del AFFO total: si las acciones crecen más rápido
    que el AFFO, el AFFO por acción cae aunque la empresa "crezca".
    """
    if not acciones_hace_un_anio or acciones_hace_un_anio <= 0:
        return None
    return acciones_actual / acciones_hace_un_anio - 1.0


def acciones_totalmente_diluidas(acciones_comunes: float, unidades_op: float = 0.0) -> float:
    """Conteo que reparte el flujo de verdad, incluyendo unidades de la sociedad operativa."""
    return float(acciones_comunes) + float(unidades_op)


# --------------------------------------------------------------------------------------
# Panel consolidado
# --------------------------------------------------------------------------------------


def panel_valuacion(
    ins: InsumosValuacion,
    *,
    cap_rate_mercado: float = 0.065,
    yield_adquisiciones: float | None = None,
    tasa_libre_riesgo: float | None = None,
) -> dict[str, float | None]:
    """Todas las métricas de valuación de un emisor en una fecha, en un dict plano."""
    nav = calcular_nav(ins, cap_rate_mercado)
    cmc = costo_marginal_de_capital(ins)
    y = affo_yield(ins)
    salida: dict[str, float | None] = {
        "precio": ins.precio,
        "capitalizacion": ins.capitalizacion,
        "ev_ajustado": valor_empresa_ajustado(ins),
        "deuda_neta": ins.deuda_neta,
        "cap_rate_implicito": cap_rate_implicito(ins),
        "cap_rate_descontado_por_el_mercado": cap_rate_implicito_en_precio(ins),
        "affo_yield": y,
        "p_affo": p_affo(ins),
        "dividend_yield": dividend_yield(ins),
        "payout_affo": payout_affo(ins),
        "payout_ffo": payout_ffo(ins),
        "payout_utilidad_neta": payout_utilidad_neta(ins),
        "deuda_neta_ebitdare": deuda_neta_ebitdare(ins),
        "costo_implicito_deuda": costo_implicito_deuda(ins),
        "ltv": ltv(ins),
        "costo_marginal_capital": cmc,
        "spread_inversion": spread_de_inversion(yield_adquisiciones, cmc),
        "nav_por_accion": nav.nav_por_accion if nav else None,
        "premio_descuento_nav": nav.premio_descuento if nav else None,
    }
    if tasa_libre_riesgo is not None and y is not None:
        salida["prima_sobre_libre_riesgo"] = y - tasa_libre_riesgo
        salida["prima_bps"] = (y - tasa_libre_riesgo) * 10_000.0
    return salida
