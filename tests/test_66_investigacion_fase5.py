"""La mecánica de la fase 5, con indicadores sintéticos (el resultado real va en el informe)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.investigacion import fase5, senales


def _sintetico(n: int = 300):
    rng = np.random.default_rng(11)
    idx = pd.date_range("1980-01-31", periods=n, freq="ME")
    x = pd.DataFrame({"retorno_precio": rng.normal(0.006, 0.04, n), "retorno_ingreso": np.full(n, 0.005),
                      "efectivo": np.full(n, 0.003)}, index=idx)
    x["retorno_total"] = x["retorno_precio"] + x["retorno_ingreso"]
    columnas = {"yield_reit", "spread_10a", "spread_real", "spread_baa", "spread_credito", "cambio_credito_12m",
                "cambio_treasury_12m", "curva", "fed_cambio_12m", "nfci", "credito_inmuebles",
                "desempleo_cambio_12m", "tendencia_10m", "momentum_12m"}
    ind = pd.DataFrame({c: rng.normal(size=n) for c in sorted(columnas)}, index=idx)
    return x, ind


def test_el_catalogo_produce_todas_sus_reglas_con_exposicion_valida():
    x, ind = _sintetico()
    reglas = fase5.reglas_del_catalogo(x, ind)
    niveles = [s for s in senales.CATALOGO if s.familia not in senales.TENDENCIA]
    tendencia = [s for s in senales.CATALOGO if s.familia in senales.TENDENCIA]
    assert len(reglas) == 2 * len(niveles) + len(tendencia) + 2
    for senal, nombre, e in reglas:
        assert e.notna().all() and e.between(0, 1).all(), (senal.nombre, nombre)
    # Ninguna regla de nivel decide antes de tener 60 meses de historia: hasta entonces, dentro.
    for senal, nombre, e in reglas:
        if senal.familia not in senales.TENDENCIA and senal.familia != "combinada":
            assert (e.iloc[:senales.MINIMO_DE_HISTORIA - 1] == 1.0).all(), (senal.nombre, nombre)


def test_el_filtro_pide_todo_a_la_vez():
    base = pd.Series({"senal": "s", "regla": "r", "mejora_rebalanceo": 0.01, "mejora_contra_mezcla_fija": 0.005,
                      "mejora_rebalanceo_con_rezago": 0.002, "mejora_rebalanceo_doble_costo": 0.004,
                      "r2_12m": 0.01, "clark_west_p_12m": 0.3})
    eras = pd.DataFrame({"senal": ["s", "s"], "regla": ["r", "r"], "era": ["a", "b"], "mejora_rebalanceo": [0.01, 0.02]})
    def con(**cambios):
        return pd.Series({**base.to_dict(), **cambios})

    assert fase5.pasa_el_filtro(base, eras)
    assert not fase5.pasa_el_filtro(con(mejora_contra_mezcla_fija=-0.001), eras)
    assert not fase5.pasa_el_filtro(con(mejora_rebalanceo_con_rezago=-0.001), eras)
    assert not fase5.pasa_el_filtro(base, eras.assign(mejora_rebalanceo=[0.01, -0.001]))
    assert not fase5.pasa_el_filtro(con(r2_12m=-0.01, clark_west_p_12m=0.2), eras)
    assert fase5.pasa_el_filtro(con(r2_12m=-0.01, clark_west_p_12m=0.05), eras)
