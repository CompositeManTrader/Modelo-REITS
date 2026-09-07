"""Semilla de datos para que la aplicación arranque sin depender de la red.

Regla de honestidad: **todo lo generado aquí se marca como ``DEMO``** y la
interfaz lo señala en cada pantalla. Sirve para recorrer la aplicación y para
que las pruebas corran sin red, no para decidir.

Lo que sí es real y se marca como tal:

* Las **anclas de precio** verificadas contra cierres de mercado (P2).
* Las **tasas** cuando hay acceso a FRED, marcadas ``FRED``.
* Todo lo que entra por ``ingesta.orquestador`` desde EDGAR.
"""

from __future__ import annotations

import datetime as dt
import zlib

import numpy as np
import pandas as pd

from src.config import (
    SERIE_CETES28,
    SERIE_CPI,
    SERIE_INPC,
    SERIE_MBONO10,
    SERIE_UDIBONO10,
    SERIE_UDIBONO30,
    SERIE_USDMXN,
    SERIE_UST10,
    UNIVERSO_INICIAL,
    Estado,
    Fuente,
)
from src.datos.repositorio import Repositorio
from src.ingesta.precios import ANCLAS_VERIFICADAS

# Parámetros de los emisores del universo para generar series de demostración
# coherentes entre sí. No son estimaciones: son andamios.
# "yield" es el AFFO yield objetivo (define el múltiplo al que revierte el precio) y
# "payout" la fracción del AFFO que se reparte. El dividendo se genera como fracción
# del AFFO, NO como precio × yield: derivarlo del precio produce payouts absurdos en
# cuanto el múltiplo se mueve, y con eso la puerta de deterioro dispara sobre un
# artefacto de la simulación en vez de sobre el negocio.
PERFIL_DEMO: dict[str, dict] = {
    "O":    {"yield": 0.055, "payout": 0.75, "crec_affo": 0.035, "vol": 0.18, "affo_2019": 3.32},
    "NNN":  {"yield": 0.058, "payout": 0.68, "crec_affo": 0.025, "vol": 0.19, "affo_2019": 2.75},
    "ADC":  {"yield": 0.048, "payout": 0.72, "crec_affo": 0.055, "vol": 0.20, "affo_2019": 3.10},
    "WPC":  {"yield": 0.062, "payout": 0.82, "crec_affo": 0.010, "vol": 0.22, "affo_2019": 4.95},
    "EPRT": {"yield": 0.050, "payout": 0.68, "crec_affo": 0.060, "vol": 0.24, "affo_2019": 1.10},
    # GNL arranca con un payout que no se sostiene: es el caso que tiene que hacer
    # sonar la puerta de deterioro antes de los recortes de 2023 y 2024.
    "GNL":  {"yield": 0.090, "payout": 1.02, "crec_affo": -0.030, "vol": 0.32, "affo_2019": 1.75},
    "PSA":  {"yield": 0.045, "payout": 0.62, "crec_affo": 0.050, "vol": 0.21, "affo_2019": 10.60},
    "EXR":  {"yield": 0.048, "payout": 0.68, "crec_affo": 0.055, "vol": 0.23, "affo_2019": 4.85},
    "PLD":  {"yield": 0.042, "payout": 0.65, "crec_affo": 0.090, "vol": 0.24, "affo_2019": 3.35},
    "WELL": {"yield": 0.050, "payout": 0.70, "crec_affo": 0.040, "vol": 0.26, "affo_2019": 4.10},
}

INICIO_DEMO = dt.date(2015, 1, 1)


def _semilla_estable(texto: str) -> int:
    """Semilla reproducible a partir de un texto.

    `hash()` de Python está ALEATORIZADO por proceso salvo que se fije
    `PYTHONHASHSEED`, así que `abs(hash(ticker))` producía datos de demostración
    distintos en cada corrida. Eso hizo que dos jobs de CI sobre el MISMO commit
    dieran resultados distintos —uno verde y otro rojo— y que un fallo no se
    pudiera reproducir en la máquina de nadie. `crc32` no es criptográfico, que
    aquí no hace falta, pero sí es estable entre procesos y versiones.
    """
    return zlib.crc32(texto.encode("utf-8"))


def _dias_habiles(inicio: dt.date, fin: dt.date) -> pd.DatetimeIndex:
    return pd.bdate_range(inicio, fin)


def generar_precios_demo(
    ticker: str, inicio: dt.date = INICIO_DEMO, fin: dt.date | None = None, semilla: int = 0
) -> pd.DataFrame:
    """Serie de precios de demostración **acoplada al AFFO**, no independiente de él.

    Es una decisión de diseño, no un detalle: si el precio se genera como una
    caminata aleatoria suelta y el AFFO como otra, las dos series se separan y la
    aplicación acaba mostrando un REIT con 16% de AFFO yield y payout de 115%.
    Eso no ejercita el modelo, lo hace ver roto.

    Aquí el precio se construye por la identidad que el modelo mismo usa::

        precio = múltiplo × AFFO por acción TTM

    con el múltiplo siguiendo un proceso de reversión a la media alrededor del
    nivel típico del sector. Así la demostración reproduce la dinámica real: el
    yield se mueve por el múltiplo en el corto plazo y por el flujo en el largo,
    que es justo la descomposición que la página de portafolio enseña.

    Se generan como precio **crudo**, sin ajustar por dividendos, que es la única
    serie que sirve para calcular yields (P2). Cuando el emisor tiene anclas
    verificadas, la trayectoria se fuerza a pasar por ellas para que la validación
    de anclas tenga algo real contra qué medir.
    """
    fin = fin or dt.date.today()
    perfil = PERFIL_DEMO.get(ticker, {"yield": 0.05, "vol": 0.20, "affo_2019": 2.5})
    fechas = _dias_habiles(inicio, fin)
    rng = np.random.default_rng(_semilla_estable(ticker) + semilla)
    n = len(fechas)

    # AFFO TTM por acción interpolado a diario, con el mismo crecimiento que la
    # serie trimestral de fundamentales.
    affo_inicial = perfil.get("affo_2019", 2.5)
    crec_diario = (1.0 + perfil.get("crec_affo", 0.03)) ** (1 / 252) - 1.0
    affo_ttm = affo_inicial * (1.0 + crec_diario) ** np.arange(n)

    # Múltiplo con reversión a la media (Ornstein-Uhlenbeck en logaritmos).
    multiplo_objetivo = 1.0 / perfil.get("yield", 0.05)
    velocidad, vol_multiplo = 0.004, perfil.get("vol", 0.20) / np.sqrt(252)
    log_m = np.empty(n)
    log_m[0] = np.log(multiplo_objetivo)
    log_objetivo = np.log(multiplo_objetivo)
    choques = rng.normal(0.0, vol_multiplo, n)
    for i in range(1, n):
        log_m[i] = log_m[i - 1] + velocidad * (log_objetivo - log_m[i - 1]) + choques[i]

    precios = pd.Series(np.exp(log_m) * affo_ttm, index=fechas)

    anclas = [a for a in ANCLAS_VERIFICADAS if a["ticker"] == ticker]
    if anclas:
        precios = _forzar_anclas(precios, anclas)

    df = pd.DataFrame(
        {
            "ticker": ticker,
            "fecha_dato": [f.date() for f in precios.index],
            "fecha_publicacion": [f.date() for f in precios.index],
            "cierre_crudo": precios.to_numpy(),
            "fuente": Fuente.DEMO,
            "metodo": "demo",
            "estado": Estado.VALIDO,
        }
    )
    return df


def _forzar_anclas(precios: pd.Series, anclas: list[dict]) -> pd.Series:
    """Deforma la trayectoria para que pase exactamente por los cierres verificados.

    Se interpola el factor de corrección en escala logarítmica, así que la serie
    conserva su textura y sus anclas quedan clavadas.
    """
    factores = pd.Series(1.0, index=precios.index)
    for a in anclas:
        f = pd.Timestamp(a["fecha_dato"])
        if f not in precios.index:
            cercanas = precios.index[precios.index <= f]
            if cercanas.empty:
                continue
            f = cercanas[-1]
        factores.loc[f] = a["cierre_crudo"] / float(precios.loc[f])
    log_f = np.log(factores.replace(1.0, np.nan))
    log_f.iloc[0] = log_f.iloc[0] if not np.isnan(log_f.iloc[0]) else 0.0
    log_f.iloc[-1] = log_f.iloc[-1] if not np.isnan(log_f.iloc[-1]) else 0.0
    return precios * np.exp(log_f.interpolate(method="index").fillna(0.0))


def generar_dividendos_demo(
    ticker: str, inicio: dt.date = INICIO_DEMO, fin: dt.date | None = None
) -> pd.DataFrame:
    """Calendario de distribuciones de demostración, con su crecimiento anual."""
    fin = fin or dt.date.today()
    perfil = PERFIL_DEMO.get(ticker, {"affo_2019": 2.5, "payout": 0.7, "crec_affo": 0.03})
    mensual = ticker in ("O", "EPRT", "GNL")
    frecuencia = "ME" if mensual else "QE"
    fechas = pd.date_range(inicio, fin, freq=frecuencia)
    if len(fechas) == 0:
        return pd.DataFrame()

    # El dividendo sale del AFFO, no del precio: así el payout es un parámetro del
    # emisor y no un subproducto de dónde ande el múltiplo.
    base = perfil["affo_2019"] * perfil.get("payout", 0.7) / (12 if mensual else 4)
    crecimiento = perfil.get("crec_affo", 0.03)
    filas = []
    for i, f in enumerate(fechas):
        anios = i / (12 if mensual else 4)
        monto = base * (1.0 + crecimiento) ** anios
        # WPC y GNL recortaron dividendo: el sistema tiene que funcionar con ellos.
        if ticker == "WPC" and f >= pd.Timestamp("2023-10-01"):
            monto *= 0.805
        if ticker == "GNL" and f >= pd.Timestamp("2023-07-01"):
            monto *= 0.70
        if ticker == "GNL" and f >= pd.Timestamp("2024-11-01"):
            monto *= 0.67
        filas.append(
            {
                "ticker": ticker,
                "fecha_declaracion": (f - pd.Timedelta(days=20)).date(),
                "fecha_ex": f.date(),
                "fecha_registro": (f + pd.Timedelta(days=1)).date(),
                "fecha_pago": (f + pd.Timedelta(days=14)).date(),
                "monto": round(monto, 4),
                "frecuencia": "mensual" if mensual else "trimestral",
                "fuente": Fuente.DEMO,
                "fecha_publicacion": (f - pd.Timedelta(days=20)).date(),
            }
        )
    return pd.DataFrame(filas)


def generar_fundamentales_demo(
    ticker: str, inicio: dt.date = INICIO_DEMO, fin: dt.date | None = None
) -> pd.DataFrame:
    """Serie trimestral de AFFO por acción y afines, con rezago de publicación real.

    El rezago importa: el AFFO de un trimestre se publica entre 30 y 45 días
    después del cierre. La ``fecha_publicacion`` refleja eso, no el cierre contable.
    """
    fin = fin or dt.date.today()
    perfil = PERFIL_DEMO.get(ticker, {"affo_2019": 2.0, "crec_affo": 0.03})
    trimestres = pd.date_range(inicio, fin, freq="QE")
    rng = np.random.default_rng(_semilla_estable(ticker + "affo"))

    filas = []
    base = perfil.get("affo_2019", 2.0) / 4.0
    crec_trim = (1.0 + perfil.get("crec_affo", 0.03)) ** 0.25 - 1.0
    for i, f in enumerate(trimestres):
        publicacion = (f + pd.Timedelta(days=38)).date()
        if publicacion > fin:
            continue  # aún no se publica: no puede existir en la base
        ruido = 1.0 + rng.normal(0, 0.02)
        affo_pa = base * (1.0 + crec_trim) ** i * ruido
        acciones = 700e6 * (1.0 + 0.04) ** (i / 4)
        for concepto, valor in (
            ("affo_por_accion", affo_pa),
            ("affo", affo_pa * acciones),
            ("acciones_diluidas", acciones),
            ("utilidad_neta", affo_pa * acciones * 0.34),
            ("noi", affo_pa * acciones * 1.28),
            ("ffo", affo_pa * acciones * 0.97),
        ):
            filas.append(
                {
                    "ticker": ticker,
                    "concepto": concepto,
                    "periodo_tipo": "Q",
                    "fecha_dato": f.date(),
                    "fecha_publicacion": publicacion,
                    "valor": float(valor),
                    "unidad": "USD",
                    "fuente": Fuente.DEMO,
                    "es_primario": False,
                    "estado": Estado.VALIDO,
                    "nota_validacion": "Serie de demostración. NO usar para decidir.",
                }
            )
    return pd.DataFrame(filas)


def generar_tasas_demo(inicio: dt.date = INICIO_DEMO, fin: dt.date | None = None) -> pd.DataFrame:
    """Series macro de demostración: UST10, Udibono, Mbono, Cetes, INPC, CPI y USD/MXN."""
    fin = fin or dt.date.today()
    fechas = _dias_habiles(inicio, fin)
    rng = np.random.default_rng(20240101)
    n = len(fechas)

    def camino(inicial: float, final: float, vol: float) -> np.ndarray:
        """Tendencia con reversión a la media alrededor de ella.

        Una caminata aleatoria pura acumula varianza sin límite y termina sacando
        al UST de 10 años a niveles que nunca tuvo. Las tasas revierten; el proceso
        tiene que revertir también o la demostración deja de ser plausible.
        """
        tendencia = np.linspace(inicial, final, n)
        desvio = np.zeros(n)
        choques = rng.normal(0.0, vol, n)
        for i in range(1, n):
            desvio[i] = desvio[i - 1] * 0.995 + choques[i]
        return np.maximum(tendencia + desvio, inicial * 0.2)

    series = {
        SERIE_UST10: (camino(0.021, 0.043, 0.0006), "decimal", 1),
        SERIE_UDIBONO10: (camino(0.030, 0.047, 0.0004), "decimal", 1),
        SERIE_UDIBONO30: (camino(0.034, 0.050, 0.0004), "decimal", 1),
        SERIE_MBONO10: (camino(0.060, 0.093, 0.0008), "decimal", 1),
        SERIE_CETES28: (camino(0.030, 0.078, 0.0005), "decimal", 1),
        SERIE_USDMXN: (camino(14.8, 18.6, 0.06), "tipo_cambio", 1),
    }
    filas = []
    for serie, (valores, unidad, rezago) in series.items():
        for f, v in zip(fechas, valores, strict=False):
            filas.append(
                {
                    "serie": serie,
                    "fecha_dato": f.date(),
                    "fecha_publicacion": (f + pd.Timedelta(days=rezago)).date(),
                    "valor": float(v),
                    "unidad": unidad,
                    "fuente": Fuente.DEMO,
                }
            )

    # Índices de precios mensuales, con su rezago de publicación real.
    meses = pd.date_range(inicio, fin, freq="ME")
    for serie, inicial, inflacion, rezago in (
        (SERIE_INPC, 87.0, 0.048, 9),
        (SERIE_CPI, 233.0, 0.030, 14),
    ):
        for i, f in enumerate(meses):
            valor = inicial * (1.0 + inflacion) ** (i / 12)
            filas.append(
                {
                    "serie": serie,
                    "fecha_dato": f.date(),
                    "fecha_publicacion": (f + pd.Timedelta(days=rezago)).date(),
                    "valor": float(valor),
                    "unidad": "indice",
                    "fuente": Fuente.DEMO,
                }
            )
    return pd.DataFrame(filas)


def generar_guias_demo(ticker: str) -> pd.DataFrame:
    """Historial de revisiones de guía. Cada revisión es un registro nuevo (P1).

    Reproduce el caso documentado de Realty Income: en febrero de 2026 guiaba
    4.38–4.42 dólares de AFFO por acción y en agosto subió a 4.44–4.45. Un modelo
    que use 4.445 para fechas de marzo está usando información del futuro.
    """
    if ticker != "O":
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
                "ticker": "O",
                "metrica": "affo_por_accion",
                "anio_guia": 2026,
                "valor_min": 4.38,
                "valor_max": 4.42,
                "fecha_publicacion": dt.date(2026, 2, 24),
                "fuente": Fuente.DEMO,
                "url_filing": "",
            },
            {
                "ticker": "O",
                "metrica": "affo_por_accion",
                "anio_guia": 2026,
                "valor_min": 4.44,
                "valor_max": 4.45,
                "fecha_publicacion": dt.date(2026, 8, 5),
                "fuente": Fuente.DEMO,
                "url_filing": "",
            },
        ]
    )


def sembrar(
    repo: Repositorio,
    *,
    tickers: list[str] | None = None,
    inicio: dt.date = INICIO_DEMO,
    fin: dt.date | None = None,
    con_fundamentales: bool = True,
) -> dict[str, int]:
    """Llena la base con datos de demostración. Todo queda marcado ``DEMO``."""
    fin = fin or dt.date.today()
    emisores = [e for e in UNIVERSO_INICIAL if tickers is None or e.ticker in set(tickers)]
    repo.registrar_emisores(emisores)

    conteo = {"emisores": len(emisores), "precios": 0, "dividendos": 0, "hechos": 0,
              "tasas": 0, "anclas": 0, "guias": 0}

    conteo["anclas"] = repo.guardar_anclas(list(ANCLAS_VERIFICADAS))
    conteo["tasas"] = repo.guardar_tasas(generar_tasas_demo(inicio, fin).to_dict("records"))

    for e in emisores:
        conteo["precios"] += repo.guardar_precios(
            generar_precios_demo(e.ticker, inicio, fin).to_dict("records")
        )
        conteo["dividendos"] += repo.guardar_dividendos(
            generar_dividendos_demo(e.ticker, inicio, fin).to_dict("records")
        )
        if con_fundamentales:
            conteo["hechos"] += repo.guardar_hechos(
                generar_fundamentales_demo(e.ticker, inicio, fin).to_dict("records")
            )
        guias = generar_guias_demo(e.ticker)
        if not guias.empty:
            conteo["guias"] += repo.guardar_guias(guias.to_dict("records"))

    repo.registrar_bitacora(
        "semilla",
        "Base sembrada con datos de DEMOSTRACIÓN. Corre la ingesta de EDGAR para "
        "sustituirlos por datos de fuente primaria.",
    )
    return conteo
