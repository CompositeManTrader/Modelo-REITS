"""Modelos de valor intrínseco en el tiempo: DDM, DCF, crecimiento implícito y NAV.

Complementa a ``metodos``. Aquellos siete miden «caro o barato» contra la historia
propia; estos cuatro estiman cuánto VALE la acción y lo comparan contra el precio. Se
prueban igual que los otros —percentil contra su historia, backtest de aportación y
asignación entre emisores, con los mismos controles— y además con su señal ABSOLUTA,
que es como se usan en la práctica: comprar si el valor supera al precio.

Diseño fijado antes de correr (commit «Diseño de los modelos intrínsecos»)
---------------------------------------------------------------------------
Todo con lo publicado a cada fin de mes (P1). La tasa de descuento es la de la
aplicación: ``r = Treasury a 10 años + prima del sector`` (``PRIMA_RIESGO_POR_SECTOR``;
3.0% en net lease). Ningún parámetro se mueve después de ver resultados; la prima se
reporta además con 2% y 4% para la señal absoluta, completa.

1. **DDM (Gordon sobre el dividendo).** ``V = D₀(1+g)/(r−g)``. ``D₀`` es el dividendo
   regular vigente anualizado; ``g`` es el crecimiento anual del dividendo en los 5
   años previos, acotado entre 0% y 4% (no hay crecimiento perpetuo por encima del
   nominal de la economía) y a que ``r − g`` sea al menos 2%.
2. **DCF del flujo en dos etapas.** El flujo es el AFFO por acción de 12 meses (FFO
   donde no hay AFFO), como flujo libre al accionista. Cinco años al crecimiento del
   flujo por acción de los 5 años previos, acotado entre 0% y 8%; después, 2% perpetuo
   (la meta de inflación de la Fed), también con ``r − g ≥ 2%``.
3. **Crecimiento implícito contra el entregado.** El crecimiento perpetuo del flujo
   que justifica el precio (Gordon despejado, ``modelo.valuacion.crecimiento_implicito``)
   contra el que el emisor entregó en los 5 años previos, acotado entre −5% y 10%. La
   señal es la diferencia: el mercado descuenta menos de lo que el emisor ha hecho.
4. **NAV aproximado.** ``(NOI anualizado ÷ cap rate − deuda neta − preferentes) ÷
   acciones``, de los estados XBRL versionados (``data/emisoras``), cada cifra con la
   fecha en que se publicó:

   * NOI anualizado = el último trimestre conocido × 4, con NOI = ingresos totales −
     gastos de inmuebles − ingresos por administración de fondos (WPC hasta 2017). En
     net lease el inquilino paga casi todo; la diferencia contra el NOI del suplemento
     es de unos puntos.
   * Cap rate = el de las adquisiciones del propio emisor en su último año reportado
     (cifra primaria, vigente 18 meses): lo que el mercado privado cobró por inmuebles
     parecidos. Existe desde 2006 (NNN), 2009 (O) y 2014 (WPC).
   * Deuda = la mayor entre la deuda total etiquetada y la suma de sus componentes
     (XBRL a veces etiqueta como total solo los bonos); menos el efectivo.
   * Acciones = las de la portada del último reporte (``dei``), o las del balance.

   Antes de mirar retornos, el NAV se valida contra el apalancamiento que reportó cada
   emisor: deuda neta ÷ (NOI − gastos de administración) contra su deuda neta ÷ EBITDAre.

Señales
-------
* **Absoluta.** DDM, DCF y NAV: barato si el valor supera al precio en 15% o más, caro
  si el precio supera al valor en 15% o más (``V/P − 1 ≤ −15%``), medio en medio.
  Crecimiento: barato si el entregado supera al implícito por 1 punto o más, caro si
  queda 1 punto o más abajo.
* **Percentil** contra la historia propia, como los otros métodos (≥ 70 barato, < 30 caro).

Cada una se prueba con el backtest de aportación de ``metodos`` (barato compra todo y la
reserva, medio la mitad, caro nada; nunca vende; nada espera más de 12 meses) y con la
asignación entre emisores: por percentil, y por la señal absoluta, que en un modelo de
valor sí se puede comparar entre emisores (el crecimiento ya está en el valor).

Hipótesis escritas antes de correr
----------------------------------
* El DDM y el DCF en percentil se parecerán mucho a la prima sobre el Treasury y al
  yield de dividendo, porque con ``r`` = Treasury + prima fija el valor entre el precio
  depende casi solo del yield contra la tasa; lo nuevo es ``g``, y ``g`` es ruido.
* En absoluto, el DDM y el DCF dirán «barato» la mayor parte del tiempo en O y NNN
  (crecieron rápido): una señal que casi siempre compra es aportar sin reglas.
* El NAV y el crecimiento implícito son los que podrían aportar información nueva. El
  NAV tiene poca historia: la asignación por NAV con los tres empieza en 2015.
* La regla recomendada sigue siendo el consenso de los siete de ``metodos``: si un modelo
  de valor sale mejor, se reporta, pero adoptarlo sería escoger por resultado.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.config import PRIMA_RIESGO_POR_SECTOR
from src.estudio.metodos import Metodo
from src.modelo.valuacion import crecimiento_implicito


@dataclass(frozen=True)
class Supuestos:
    prima: float = PRIMA_RIESGO_POR_SECTOR["Net Lease"]
    anios_historia: int = 5              # de dónde sale el crecimiento «entregado»
    g_dividendo: tuple[float, float] = (0.0, 0.04)
    g_flujo: tuple[float, float] = (0.0, 0.08)
    g_terminal: float = 0.02
    anios_etapa_1: int = 5
    margen_r_menos_g: float = 0.02
    g_entregado: tuple[float, float] = (-0.05, 0.10)
    umbral_valor: float = 0.15           # V/P − 1 para barato (≥) y caro (≤ −)
    umbral_crecimiento: float = 0.01     # entregado − implícito
    vigencia_cap_rate_meses: int = 18
    primas_de_sensibilidad: tuple[float, ...] = (0.02, 0.03, 0.04)


SUPUESTOS = Supuestos()

INTRINSECOS: tuple[Metodo, ...] = (
    Metodo("ddm", "DDM (Gordon sobre el dividendo)",
           "Dividendo vigente × (1 + g) ÷ (r − g); g = crecimiento del dividendo de los 5 años previos, "
           "entre 0% y 4%; r = Treasury a 10 años + 3%. La señal es valor ÷ precio − 1."),
    Metodo("dcf", "DCF del flujo en dos etapas",
           "AFFO por acción (FFO donde no hay) creciendo 5 años a su ritmo de los 5 previos (0% a 8%) "
           "y después 2% perpetuo, descontado a r. La señal es valor ÷ precio − 1."),
    Metodo("crecimiento", "Crecimiento entregado contra implícito",
           "El crecimiento del flujo por acción de los 5 años previos menos el crecimiento perpetuo "
           "que justifica el precio con r. Positivo: el mercado descuenta menos de lo que el emisor ha hecho."),
    Metodo("nav", "NAV aproximado",
           "NOI anualizado del último trimestre ÷ el cap rate de las compras del propio emisor, menos "
           "deuda neta y preferentes, por acción. La señal es NAV ÷ precio − 1."),
)
CLAVES = tuple(m.clave for m in INTRINSECOS)


# --------------------------------------------------------------------------------------
# Fórmulas
# --------------------------------------------------------------------------------------


def acotar(g: float, limites: tuple[float, float], r: float | None = None, margen: float = 0.0) -> float:
    """``g`` dentro de ``limites`` y, si se da ``r``, con ``r − g ≥ margen``."""
    if g is None or pd.isna(g):
        return np.nan
    x = min(max(float(g), limites[0]), limites[1])
    if r is not None and not pd.isna(r):
        x = min(x, float(r) - margen)
    return x


def ddm(dividendo: float, g: float, r: float) -> float:
    """Gordon: ``D₀(1+g)/(r−g)``. NaN si falta algo o ``r ≤ g``."""
    if any(pd.isna(x) for x in (dividendo, g, r)) or dividendo <= 0 or r <= g:
        return np.nan
    return dividendo * (1 + g) / (r - g)


def dcf_dos_etapas(flujo: float, g1: float, g2: float, r: float, anios: int = 5) -> float:
    """Valor presente de ``anios`` flujos creciendo a ``g1`` y un terminal de Gordon a ``g2``."""
    if any(pd.isna(x) for x in (flujo, g1, g2, r)) or flujo <= 0 or r <= g2:
        return np.nan
    k = np.arange(1, anios + 1)
    flujos = flujo * (1 + g1) ** k
    presente = float(np.sum(flujos / (1 + r) ** k))
    terminal = flujos[-1] * (1 + g2) / (r - g2)
    return presente + terminal / (1 + r) ** anios


def crecimiento_anual(serie: pd.Series, fechas: pd.DatetimeIndex, anios: int) -> pd.Series:
    """Crecimiento anual compuesto de ``serie`` en los ``anios`` previos a cada fecha."""
    s = serie.dropna()
    if s.empty:
        return pd.Series(np.nan, index=fechas)
    hoy = s.reindex(s.index.union(fechas)).ffill().reindex(fechas)
    antes = s.reindex(s.index.union(fechas - pd.DateOffset(years=anios))).ffill().reindex(
        fechas - pd.DateOffset(years=anios))
    antes.index = fechas
    positivo = (hoy > 0) & (antes > 0)
    return ((hoy / antes) ** (1 / anios) - 1).where(positivo)


def senal_absoluta(valor: float, umbral: float) -> str:
    if valor is None or pd.isna(valor):
        return "sin dato"
    return "barato" if valor >= umbral else ("caro" if valor <= -umbral else "medio")


def crecimiento_implicito_seguro(precio: float, flujo: float, r: float) -> float:
    if any(pd.isna(x) for x in (precio, flujo, r)):
        return np.nan
    g = crecimiento_implicito(float(precio), float(flujo), float(r))
    return np.nan if g is None else g
