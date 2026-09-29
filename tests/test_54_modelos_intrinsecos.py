"""Modelos de valor intrínseco en el tiempo (``src/estudio/intrinsecos.py``).

Primero las fórmulas, contra cuentas hechas a mano: un DCF de dos etapas con el mismo
crecimiento en las dos es exactamente un Gordon, y un Gordon valuado con el crecimiento
implícito devuelve el precio. Después los datos del NAV, que salen de XBRL versionado y
tienen que respetar la fecha de publicación de cada cifra (P1).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
for ruta in (str(RAIZ), str(RAIZ / "app")):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from src.estudio import intrinsecos as it  # noqa: E402


def test_el_ddm_es_gordon():
    assert it.ddm(1.0, 0.03, 0.08) == pytest.approx(1.03 / 0.05)
    assert np.isnan(it.ddm(1.0, 0.08, 0.08)), "con r = g no hay valor, hay división entre cero"
    assert np.isnan(it.ddm(0.0, 0.02, 0.08))


def test_dos_etapas_con_el_mismo_crecimiento_es_gordon():
    assert it.dcf_dos_etapas(2.0, 0.02, 0.02, 0.08, 5) == pytest.approx(it.ddm(2.0, 0.02, 0.08), rel=1e-12)


def test_dos_etapas_a_mano():
    r, g1, g2 = 0.08, 0.05, 0.02
    flujos = [1.05, 1.05**2, 1.05**3, 1.05**4, 1.05**5]
    esperado = sum(f / 1.08**k for k, f in enumerate(flujos, start=1)) + flujos[-1] * 1.02 / 0.06 / 1.08**5
    assert it.dcf_dos_etapas(1.0, g1, g2, r, 5) == pytest.approx(esperado, rel=1e-12)


def test_el_crecimiento_implicito_devuelve_el_precio():
    precio, flujo, r = 55.0, 4.2, 0.0817
    g = it.crecimiento_implicito_seguro(precio, flujo, r)
    assert flujo * (1 + g) / (r - g) == pytest.approx(precio, rel=1e-12)


def test_acotar_respeta_limites_y_margen():
    assert it.acotar(0.07, (0.0, 0.04)) == 0.04
    assert it.acotar(-0.02, (0.0, 0.04)) == 0.0
    assert it.acotar(0.04, (0.0, 0.04), r=0.05, margen=0.02) == pytest.approx(0.03)
    assert np.isnan(it.acotar(np.nan, (0.0, 0.04)))


def test_crecimiento_anual_compuesto():
    fechas = pd.date_range("2010-01-31", "2020-12-31", freq="ME")
    serie = pd.Series(2.0 ** ((fechas - fechas[0]).days / 365.25 / 5), index=fechas)
    g = it.crecimiento_anual(serie, fechas, 5)
    assert g.iloc[:59].isna().all(), "sin 5 años de historia no hay crecimiento"
    assert g.iloc[-1] == pytest.approx(2 ** (1 / 5) - 1, abs=1e-3)


def test_la_senal_absoluta_usa_el_margen():
    assert it.senal_absoluta(0.15, 0.15) == "barato"
    assert it.senal_absoluta(0.1499, 0.15) == "medio"
    assert it.senal_absoluta(-0.15, 0.15) == "caro"
    assert it.senal_absoluta(np.nan, 0.15) == "sin dato"


def test_el_diseno_quedo_fijado():
    """Los supuestos escritos antes de correr. Si esta prueba cambia, el cambio va en el
    historial con su motivo: moverlos después de ver resultados sería ajustar el modelo
    al pasado."""
    s = it.SUPUESTOS
    assert (s.prima, s.anios_historia, s.g_dividendo, s.g_flujo, s.g_terminal, s.anios_etapa_1,
            s.margen_r_menos_g, s.g_entregado, s.umbral_valor, s.umbral_crecimiento) == (
        0.03, 5, (0.0, 0.04), (0.0, 0.08), 0.02, 5, 0.02, (-0.05, 0.10), 0.15, 0.01)
    assert it.CLAVES == ("ddm", "dcf", "crecimiento", "nav")
