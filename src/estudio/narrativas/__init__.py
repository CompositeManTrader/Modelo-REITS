"""Las narrativas de los emisores de la ampliación, una por módulo.

Mismo estándar que las de O, NNN y WPC en ``historia.py``: cada hecho con su documento, eras
definidas por hechos corporativos o del mercado y sin cifras de rendimiento escritas a mano. Viven
aparte para que ``historia.py`` no crezca sin fin; ``historia.HISTORIAS`` las incluye.
"""

from __future__ import annotations

import importlib

MODULOS = ("adc", "eprt", "exr", "gnl", "pld", "psa", "well")


def cargar() -> dict:
    """Las que ya existen, por clave de pizarra."""
    salida = {}
    for nombre in MODULOS:
        try:
            m = importlib.import_module(f"{__name__}.{nombre}")
        except ModuleNotFoundError as e:
            if e.name != f"{__name__}.{nombre}":
                raise
            continue
        h = getattr(m, f"HISTORIA_{nombre.upper()}")
        salida[h.ticker] = h
    return salida
