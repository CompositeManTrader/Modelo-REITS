"""Configuración global, rutas y catálogos del proyecto.

Todo parámetro que un analista pudiera querer discutir vive aquí, no enterrado
en la lógica. Los valores marcados como ``SUPUESTO`` son inputs del usuario con
un valor por omisión razonable, no verdades del mercado.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------------------

RAIZ = Path(__file__).resolve().parent.parent
DIR_DATOS = RAIZ / "data"
DIR_SEMILLA = DIR_DATOS / "semilla"
DIR_CACHE = DIR_DATOS / "cache"
DIR_EXPORTES = DIR_DATOS / "exportes"

RUTA_BD = Path(os.environ.get("REIT_DB", DIR_DATOS / "reit.db"))


def asegurar_directorios() -> None:
    """Crea los directorios de trabajo si no existen."""
    for d in (DIR_DATOS, DIR_SEMILLA, DIR_CACHE, DIR_EXPORTES):
        d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------------------
# SEC EDGAR
# --------------------------------------------------------------------------------------

# La SEC exige un User-Agent identificable con correo de contacto y limita a 10 req/s.
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT", "Modelo-REITS/0.1 (albertoalarcon3012@gmail.com)"
)
SEC_MAX_RPS = 10.0
SEC_TIMEOUT = 30
SEC_REINTENTOS = 4

# --------------------------------------------------------------------------------------
# Fuentes de datos: etiquetas de procedencia (P: "marca qué es primario y qué derivado")
# --------------------------------------------------------------------------------------


class Fuente:
    """Etiquetas de procedencia. Se persisten con cada dato y se muestran en la interfaz."""

    SEC_XBRL = "SEC-XBRL"  # primario: companyfacts, partidas GAAP
    SEC_8K = "SEC-8K-EX99.1"  # primario: conciliación de AFFO del comunicado de resultados
    SEC_10Q = "SEC-10Q"
    SEC_10K = "SEC-10K"
    FRED = "FRED"  # primario para tasas de EE. UU.
    BANXICO = "BANXICO-SIE"  # primario para tasas y INPC de México
    DERIVADO = "DERIVADO"  # calculado a partir de otros datos de la base
    RECONSTRUIDO = "RECONSTRUIDO"  # p. ej. Q1 = H1 − Q2, o precio = div TTM / yield TTM
    MERCADO = "MERCADO"  # precio de proveedor gratuito
    MANUAL = "MANUAL"  # capturado por el usuario
    DEMO = "DEMO"  # semilla de demostración, NO usar para decidir


FUENTES_PRIMARIAS = frozenset(
    {Fuente.SEC_XBRL, Fuente.SEC_8K, Fuente.SEC_10Q, Fuente.SEC_10K, Fuente.FRED, Fuente.BANXICO}
)


# Qué procedencia gana cuando DOS caminos producen el mismo hecho, del mismo
# periodo y publicado el mismo día. Pasa de verdad: tres rutas distintas derivan
# el Q4 —`estados.py`, `xbrl.py` y la reconstrucción desde acumulados— y en 421
# celdas del universo llegan a números que difieren entre 0.3% y 0.6%. La
# restricción única de `hechos` incluye la fuente, así que las dos filas conviven
# como debe ser: el archivo conserva todo lo que se supo.
#
# Lo que NO puede quedar al azar es cuál de las dos usa el modelo. Antes ganaba
# la de `id` más alto —la que se hubiera insertado después—, de modo que una
# cifra reconstruida le ganaba a la que reportó la SEC por el orden en que
# corrió la ingesta. El criterio correcto es la cercanía a la fuente.
PRECEDENCIA_FUENTE: dict[str, int] = {
    # Lo que publicó el emisor o el banco central. Nada le gana.
    **dict.fromkeys(FUENTES_PRIMARIAS, 40),
    Fuente.MERCADO: 30,
    # Una captura humana es una afirmación deliberada: vale más que una cuenta
    # nuestra, y menos que el documento original.
    Fuente.MANUAL: 20,
    # Calculado a partir de otros datos de la base, con su aritmética explícita.
    Fuente.DERIVADO: 10,
    # Rellenado a partir de acumulados. Es el más lejano al documento.
    Fuente.RECONSTRUIDO: 5,
    # La semilla de demostración nunca le gana a un dato real.
    Fuente.DEMO: 0,
}

# Una fuente que nadie registró en la tabla anterior no puede colarse por encima
# de un dato primario solo por ser desconocida.
PRECEDENCIA_DESCONOCIDA = 1


class Estado:
    """Estado de validación de un registro."""

    VALIDO = "valido"
    SOSPECHOSO = "sospechoso"  # no se usa en cálculos hasta revisión manual
    RECHAZADO = "rechazado"


# --------------------------------------------------------------------------------------
# Universo inicial (Hito 1). Incluye deliberadamente WPC y GNL, que recortaron dividendo:
# si el sistema solo funciona con sobrevivientes, no sirve.
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Emisor:
    ticker: str
    cik: str
    nombre: str
    sector: str
    nota: str = ""


UNIVERSO_INICIAL: tuple[Emisor, ...] = (
    Emisor("O", "0000726728", "Realty Income Corporation", "Net Lease"),
    Emisor("NNN", "0000751364", "NNN REIT, Inc.", "Net Lease"),
    Emisor("ADC", "0000917251", "Agree Realty Corporation", "Net Lease"),
    Emisor(
        "WPC",
        "0001025378",
        "W. P. Carey Inc.",
        "Net Lease",
        nota="Recortó dividendo en 2023 al salir de oficinas. Caso de prueba obligatorio.",
    ),
    Emisor("EPRT", "0001728951", "Essential Properties Realty Trust", "Net Lease"),
    Emisor(
        "GNL",
        "0001526113",
        "Global Net Lease, Inc.",
        "Net Lease",
        nota="Recortes de dividendo y dilución. Caso de prueba obligatorio.",
    ),
    Emisor("PSA", "0001393311", "Public Storage", "Self Storage"),
    Emisor("EXR", "0001289490", "Extra Space Storage Inc.", "Self Storage"),
    Emisor("PLD", "0001045609", "Prologis, Inc.", "Industrial"),
    Emisor("WELL", "0000766704", "Welltower Inc.", "Salud"),
)

CIK_POR_TICKER = {e.ticker: e.cik for e in UNIVERSO_INICIAL}
EMISOR_POR_TICKER = {e.ticker: e for e in UNIVERSO_INICIAL}

# --------------------------------------------------------------------------------------
# Sectores Nareit. Las economías son distintas: los rankings solo valen dentro del sector.
# --------------------------------------------------------------------------------------

SECTORES_NAREIT: tuple[str, ...] = (
    "Net Lease",
    "Industrial",
    "Oficinas",
    "Comercial",
    "Residencial",
    "Self Storage",
    "Salud",
    "Hoteles",
    "Bosques",
    "Data Centers",
    "Torres",
    "Vivienda Prefabricada",
    "Diversificado",
    "Especializado",
)

# Intensidad esperada de CapEx recurrente de mantenimiento como % del NOI (P3).
# En net lease puro puede ser legítimamente cero porque lo paga el inquilino.
CAPEX_ESPERADO_POR_SECTOR: dict[str, tuple[float, float]] = {
    "Net Lease": (0.00, 0.05),
    "Industrial": (0.05, 0.12),
    "Oficinas": (0.15, 0.30),
    "Comercial": (0.10, 0.20),
    "Residencial": (0.10, 0.18),
    "Self Storage": (0.04, 0.10),
    "Salud": (0.08, 0.18),
    "Hoteles": (0.15, 0.30),
    "Data Centers": (0.05, 0.15),
    "Torres": (0.03, 0.08),
    "Bosques": (0.05, 0.15),
    "Vivienda Prefabricada": (0.05, 0.12),
    "Diversificado": (0.08, 0.20),
    "Especializado": (0.05, 0.20),
}

# Sectores donde NO existe ajuste de renta en línea recta, y su ausencia no dice nada.
# El ajuste nace de promediar contablemente un contrato de varios años con escalador:
# donde el contrato dura un mes —el self storage se renta mes con mes— o una noche
# —el hotel—, no hay nada que promediar. Reclamarlo ahí es ruido, y el ruido tapa el
# caso del net lease, donde la ausencia sí significa que el AFFO puede estar inflado.
SECTORES_SIN_RENTA_EN_LINEA_RECTA: frozenset[str] = frozenset({
    "Self Storage",
    "Hoteles",
})

# Con qué medida de flujo se valúa a un emisor. No todos publican AFFO: el self
# storage y buena parte de salud terminan su conciliación en el Core FFO. El texto
# es a la vez el valor y la etiqueta que se muestra, y vive aquí —y no en la capa de
# servicio— para que el modelo pueda decidir la forma de la cascada sin importar
# hacia arriba.
MEDIDA_AFFO = "AFFO"
MEDIDA_CORE_FFO = "Core FFO"


# --------------------------------------------------------------------------------------
# Cap rate por sector: (mínimo, base, máximo)
# --------------------------------------------------------------------------------------
#
# EL CAP RATE NO ES UNA CONSTANTE UNIVERSAL, y aplicarle el mismo a todos los
# sectores es el error más caro que se puede cometer en un NAV de REITs. Es la tasa
# a la que el mercado privado capitaliza una renta, y depende de qué tan estable y
# duradera es esa renta:
#
# * Un contrato de net lease a veinte años con inquilino con grado de inversión se
#   parece a un bono: se capitaliza cerca del 6.5%.
# * Un self storage se renta mes a mes, pero casi no consume CapEx y tiene poder de
#   subir precios: el mercado lo capitaliza mucho más bajo, cerca del 5.5%.
# * Una oficina se renegocia cada cinco años y devora mejoras al inquilino: pide
#   arriba del 8% para compensar.
#
# Valuar un self storage al 6.5% de net lease le quita ~15% de valor de un plumazo,
# sin que ningún número del modelo se vea raro. Por eso el cap rate vive aquí, por
# sector, y no como una sola perilla.
#
# Estos rangos son de mercado privado y ENVEJECEN: se mueven con las tasas. Hay que
# revisarlos contra transacciones comparables, no tratarlos como constantes.

CAP_RATE_POR_SECTOR: dict[str, tuple[float, float, float]] = {
    "Net Lease": (0.0575, 0.0675, 0.0800),
    "Industrial": (0.0450, 0.0550, 0.0650),
    "Oficinas": (0.0700, 0.0875, 0.1100),
    "Comercial": (0.0600, 0.0725, 0.0875),
    "Residencial": (0.0450, 0.0525, 0.0625),
    "Self Storage": (0.0475, 0.0550, 0.0650),
    "Salud": (0.0550, 0.0675, 0.0825),
    "Hoteles": (0.0750, 0.0900, 0.1100),
    "Data Centers": (0.0475, 0.0575, 0.0700),
    "Torres": (0.0400, 0.0500, 0.0600),
    "Bosques": (0.0400, 0.0500, 0.0625),
    "Vivienda Prefabricada": (0.0425, 0.0500, 0.0600),
    "Diversificado": (0.0550, 0.0675, 0.0825),
    "Especializado": (0.0550, 0.0700, 0.0875),
}

CAP_RATE_POR_OMISION: tuple[float, float, float] = (0.0500, 0.0675, 0.0900)


# Prima de riesgo sobre la tasa libre de riesgo, por sector, para descontar el AFFO.
# Mismo principio que el cap rate: un flujo contratado a veinte años exige menos
# prima que uno que se renegocia cada año. Se usa en el modelo de crecimiento
# implícito, donde la tasa de descuento es `libre de riesgo + esta prima`.
PRIMA_RIESGO_POR_SECTOR: dict[str, float] = {
    "Net Lease": 0.030,
    "Industrial": 0.035,
    "Oficinas": 0.060,
    "Comercial": 0.045,
    "Residencial": 0.030,
    "Self Storage": 0.035,
    "Salud": 0.045,
    "Hoteles": 0.065,
    "Data Centers": 0.040,
    "Torres": 0.035,
    "Bosques": 0.040,
    "Vivienda Prefabricada": 0.030,
    "Diversificado": 0.040,
    "Especializado": 0.050,
}

PRIMA_RIESGO_POR_OMISION = 0.040


# --------------------------------------------------------------------------------------
# Umbrales del semáforo (Módulo 1.3). Son inputs discutibles, no dogma.
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class UmbralesCalidad:
    """Puerta 1 — Calidad. Binaria: lo que falla no está barato, está descartado."""

    payout_affo_max: float = 0.90
    deuda_neta_ebitdare_max: float = 6.5
    exige_grado_inversion: bool = True
    exige_crecimiento_affo: bool = True
    exige_spread_positivo: bool = True


@dataclass(frozen=True)
class UmbralesValuacion:
    """Puerta 2 — Valuación. Percentil expandible de la prima sobre su propia historia."""

    percentil_compra: float = 0.70  # prima en percentil alto = barato = comprar
    percentil_mantener: float = 0.30
    min_observaciones: int = 12  # trimestres mínimos para emitir percentil


@dataclass(frozen=True)
class UmbralesDeterioro:
    """Puerta 3 — Deterioro. La única que dispara VENTA."""

    payout_affo_critico: float = 1.00
    trimestres_consecutivos: int = 2
    deuda_neta_ebitdare_max: float = 6.5


@dataclass(frozen=True)
class Umbrales:
    calidad: UmbralesCalidad = field(default_factory=UmbralesCalidad)
    valuacion: UmbralesValuacion = field(default_factory=UmbralesValuacion)
    deterioro: UmbralesDeterioro = field(default_factory=UmbralesDeterioro)


UMBRALES = Umbrales()

# --------------------------------------------------------------------------------------
# Validación (Módulo 1.2)
# --------------------------------------------------------------------------------------

TOLERANCIA_CUADRE_AFFO = 0.01  # dólares; la conciliación debe cuadrar exactamente
TOLERANCIA_CUADRE_RELATIVA = 0.001  # 0.1% para cifras en millones con redondeo del emisor
TOLERANCIA_ANCLA_PRECIO = 0.02  # 2% máximo de error contra cierre conocido (P2)
MIN_ANCLAS_PRECIO = 3  # al menos tres cierres verificables (P2)
# La identidad ajustado/crudo = Π(1 − div/cierre) es exacta salvo redondeo del
# proveedor. Se deja 1% porque una serie ajustada disfrazada de cruda falla por
# 20% o más: el umbral no necesita ser fino para separar las dos cosas.
TOLERANCIA_COHERENCIA_AJUSTE = 0.01

RANGO_PAYOUT_AFFO = (0.0, 2.0)
RANGO_OCUPACION = (0.0, 1.0)
RANGO_LTV = (0.0, 1.0)

# --------------------------------------------------------------------------------------
# Suficiencia estadística (P7)
# --------------------------------------------------------------------------------------

MIN_APUESTAS_EFECTIVAS = 100  # debajo de esto el veredicto es INCONCLUSO, nunca GO

# --------------------------------------------------------------------------------------
# Fiscal México (Módulo 2.4)
# --------------------------------------------------------------------------------------

RETENCION_EEUU_W8BEN = 0.10  # dividendo de REIT con tratado y W-8BEN presentado
ISR_ADICIONAL_MEXICO_DIVIDENDO_EXTRANJERO = 0.10
TASA_CEDULAR_GANANCIAS_SIC = 0.10  # régimen cedular vía SIC con casa de bolsa mexicana
UMBRAL_ESTATE_TAX_USD = 60_000.0
TASA_MAXIMA_ESTATE_TAX = 0.40
DEDUCCION_CIEGA_ARRENDAMIENTO = 0.35  # deducción opcional del 35% más predial

# --------------------------------------------------------------------------------------
# Benchmark del inversionista mexicano (P10)
# --------------------------------------------------------------------------------------

SERIE_UST10 = "UST10Y"
SERIE_UDIBONO10 = "UDIBONO10"
SERIE_UDIBONO30 = "UDIBONO30"
SERIE_MBONO10 = "MBONO10"
SERIE_CETES28 = "CETES28"
SERIE_INPC = "INPC"
SERIE_CPI = "CPI"
SERIE_USDMXN = "USDMXN"

# --------------------------------------------------------------------------------------
# Contexto histórico a mostrar en la interfaz (índice FTSE Nareit All Equity).
# Fuente: series públicas de Nareit; se muestran como contexto, no como proyección.
# --------------------------------------------------------------------------------------

RENDIMIENTOS_NAREIT_HISTORICOS: tuple[tuple[str, float, float | None], ...] = (
    # (periodo, nominal, real)
    ("50 años", 0.1178, None),
    ("30 años", 0.0927, 0.0356),
    ("20 años", 0.0630, 0.0171),
    ("10 años", 0.0634, 0.0209),
    ("5 años", 0.0356, -0.0056),
)

AVISO_TITULAR_12 = (
    "El titular de «12% histórico» viene de una ventana que incluye los setenta y ochenta. "
    "No lo uses para proyectar."
)

DESCARGO = (
    "Esto es una herramienta de análisis, no asesoría de inversión. "
    "Toda métrica de desempeño va acompañada de su conteo de apuestas efectivas. "
    "Cuando las observaciones son insuficientes el veredicto es INCONCLUSO, nunca GO."
)
