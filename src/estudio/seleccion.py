"""¿La valuación sabe escoger REITs? La prueba sobre el universo de REITs que cotizan hoy.

Las pruebas con O, NNN y WPC dijeron que la valuación no sirve para esperar pero sí para
escoger entre esos tres. Tres emisores de calidad, escogidos hoy, no dicen si un modelo
separa una oportunidad de una trampa. Aquí se prueba con todos los REITs de capital que
cotizan hoy en Estados Unidos, incluidos los que se desplomaron y siguen cotizando.

Diseño fijado antes de correr (commit «Diseño de la prueba del universo»)
------------------------------------------------------------------------
**Universo.** REITs de capital que cotizan hoy en NYSE o Nasdaq: industria «Real Estate
Investment Trusts» en el listado de Nasdaq o en las listas de REITs de stockanalysis, con
industria «REIT - …» distinta de «REIT - Mortgage» en stockanalysis; sin preferentes, notas
ni warrants. Precio y dividendos de Yahoo desde que cotizan (el mismo proveedor del estudio
largo), con el Treasury a 10 años de FRED y el ETF VNQ como referencia externa.

**Sesgo declarado.** No están los REITs que quebraron o fueron comprados: ninguno de los
datos disponibles aquí trae su precio. Los que se desplomaron y siguen cotizando (GNL, MPW,
SVC…) sí están. La dirección del sesgo no se puede firmar: los quebrados seguramente se veían
baratos antes de caer (su ausencia favorece a «barato»), y los comprados a menudo eran baratos
y recibieron una prima (su ausencia lo perjudica). Como indicio se compara el universo contra
VNQ, que sí los tuvo mientras existieron.

**Elegibles cada fin de mes.** Al menos 60 meses de precio, dividendo de los últimos 12 meses
mayor que cero, yield de hasta 25% (arriba es error de datos o un dividendo que ya no existe) y
precio de al menos 1 dólar. Un mes con un salto de precio de más de 50% sin evento que lo
explique se marca como error de datos y ese emisor sale ese mes.

**Tres señales, todas con precio y dividendos conocidos a esa fecha (P1):**

1. *Yield contra su propia historia*: percentil expandible del yield de dividendo de 12 meses
   del emisor contra sus propios meses anteriores (P4, P5). Es el método que funcionó con O,
   NNN y WPC.
2. *Yield contra su sector*: el yield entre la mediana del yield de su sector ese mes (industria
   de stockanalysis; sector con menos de 5 elegibles, sin señal). Pone a prueba la premisa de P4:
   si comparar yields entre emisores, aun dentro del sector, informa o engaña.
3. *DDM entre emisores*: valor de Gordon entre precio menos uno, con el dividendo de 12 meses, g
   = crecimiento del dividendo de 5 años acotado entre 0% y 4% y a r − g ≥ 2%, y r = Treasury a
   10 años + la prima del sector de la aplicación (``PRIMA_RIESGO_POR_SECTOR``; net lease para
   los emisores que la aplicación ya clasifica así).

**Grupos y carteras.** Cada fin de mes, terciles de cada señal entre los elegibles: barato,
medio y caro. Cada tercil es una cartera de pesos iguales que se mantiene 12 meses, con 12
cohortes encimadas (una formada cada mes), y el benchmark es lo mismo con TODOS los elegibles:
comprar el universo completo por partes iguales. Retorno total con dividendos reinvertidos
(precio ajustado de Yahoo), antes de impuestos, igual para todos.

**Qué se mide.**

* Retorno anual de cada tercil contra el universo, y barato menos caro, con error estándar
  Newey-West (rezago 12, por las cohortes encimadas).
* Correlación de rangos, cada mes, entre la señal y el retorno de los 12 meses siguientes: su
  promedio, qué fracción de los meses es positiva y su t de Newey-West.
* Trampas: de cada tercil, qué fracción recortó su dividendo en los 12 meses siguientes (los
  dividendos de esos 12 meses menos de 90% de los 12 anteriores) y qué fracción se desplomó
  (retorno total de 12 meses de −30% o peor).
* Variante con filtro de calidad mínimo: fuera los que recortaron el dividendo en los 12 meses
  previos. Es lo más parecido a la Puerta 1 que permiten precio y dividendos.
* Aportación mensual de 1,000 dólares repartida entre los baratos, sin vender nunca, contra la
  misma aportación repartida entre todos los elegibles: TIR money-weighted (P9).

**Controles.** 200 sorteos que reparten a los elegibles de cada mes en tres grupos del mismo
tamaño (semilla fija) para ver qué tan raro es el barato menos caro; cada mitad del periodo por
separado; la correlación dentro de cada sector.

Hipótesis escritas antes de correr
----------------------------------
1. El yield contra su propia historia predice en el universo como predijo en O, NNN y WPC:
   correlación positiva y el tercil barato arriba del universo.
2. El yield contra su sector tiene más trampas en su tercil barato —recortes y desplomes— que
   los otros grupos; si le gana al universo, le gana por menos que la señal 1.
3. El DDM entre emisores se porta como el yield contra su sector: es yield más crecimiento.
4. El filtro de dividendo intacto ayuda más a las señales 2 y 3 que a la 1.
5. El universo de pesos iguales le gana a VNQ en el periodo común: el sesgo de supervivencia
   existe, y las cifras de las señales 2 y 3 hay que leerlas como un techo.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import PRIMA_RIESGO_POR_SECTOR


@dataclass(frozen=True)
class Diseno:
    meses_minimos: int = 60
    yield_maximo: float = 0.25
    precio_minimo: float = 1.0
    salto_de_datos: float = 0.50         # un mes con +50% o −50% sin evento: error de datos
    minimo_por_sector: int = 5
    g_dividendo: tuple[float, float] = (0.0, 0.04)
    anios_crecimiento: int = 5
    margen_r_menos_g: float = 0.02
    grupos: int = 3                      # terciles
    meses_de_cohorte: int = 12
    recorte: float = 0.90                # dividendos de 12 meses < 90% de los 12 previos
    desplome: float = -0.30
    aportacion: float = 1_000.0
    sorteos: int = 200
    semilla: int = 11
    rezago_newey_west: int = 12


DISENO = Diseno()

# Industria de stockanalysis → sector de la aplicación, para la prima del DDM.
SECTOR_DE_INDUSTRIA: dict[str, str] = {
    "REIT - Retail": "Comercial",
    "REIT - Residential": "Residencial",
    "REIT - Industrial": "Industrial",
    "REIT - Office": "Oficinas",
    "REIT - Healthcare Facilities": "Salud",
    "REIT - Hotel & Motel": "Hoteles",
    "REIT - Diversified": "Diversificado",
    "REIT - Specialty": "Especializado",
}


def prima_de(industria: str, sector_aplicacion: str | None = None) -> float:
    """La prima de la aplicación: la del sector con que ya clasifica al emisor, o la de su industria."""
    if sector_aplicacion in PRIMA_RIESGO_POR_SECTOR:
        return PRIMA_RIESGO_POR_SECTOR[sector_aplicacion]
    return PRIMA_RIESGO_POR_SECTOR[SECTOR_DE_INDUSTRIA[industria]]
