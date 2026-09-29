"""¿La valuación sabe escoger REITs? La prueba sobre el universo (``src/estudio/seleccion.py``)."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for ruta in (str(RAIZ), str(RAIZ / "app")):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from src.estudio import seleccion as sel  # noqa: E402


def test_el_diseno_quedo_fijado():
    """Los parámetros escritos antes de correr. Moverlos después de ver resultados sería ajustar
    la prueba al pasado: si cambian, el cambio va en el historial con su motivo."""
    d = sel.DISENO
    assert (d.meses_minimos, d.yield_maximo, d.precio_minimo, d.salto_de_datos, d.minimo_por_sector,
            d.g_dividendo, d.anios_crecimiento, d.margen_r_menos_g, d.grupos, d.meses_de_cohorte,
            d.recorte, d.desplome, d.sorteos, d.semilla) == (
        60, 0.25, 1.0, 0.50, 5, (0.0, 0.04), 5, 0.02, 3, 12, 0.90, -0.30, 200, 11)


def test_cada_industria_tiene_su_prima():
    for industria in sel.SECTOR_DE_INDUSTRIA:
        assert 0 < sel.prima_de(industria) < 0.10
    assert sel.prima_de("REIT - Retail", "Net Lease") == 0.03
