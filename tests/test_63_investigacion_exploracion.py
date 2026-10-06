"""Fase 3: la exploración solo ve la muestra de desarrollo y no mira el futuro."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.investigacion import datos, exploracion

requiere_datos = pytest.mark.skipif(not (datos.DIR_SECTOR / "nareit_mensual.csv.gz").exists()
                                    or datos.cargar_macro().empty, reason="Faltan los datos versionados.")


def test_las_caidas_se_cuentan_del_maximo_al_minimo():
    v = [100, 110, 90, 80, 100, 111, 120, 95, 121]
    x = pd.DataFrame({"indice_total": v}, index=pd.date_range("2000-01-31", periods=len(v), freq="ME"))
    c = exploracion.caidas(x, umbral=-0.20)
    assert len(c) == 2
    assert c.iloc[0]["caida"] == pytest.approx(80 / 110 - 1)
    assert (c.iloc[0]["maximo"], c.iloc[0]["minimo"]) == (x.index[1], x.index[3])
    assert c.iloc[0]["recuperado"] == x.index[5]
    assert c.iloc[1]["caida"] == pytest.approx(95 / 120 - 1) and c.iloc[1]["recuperado"] == x.index[8]


def test_el_retorno_siguiente_empieza_el_mes_que_sigue():
    r = pd.Series([0.10, 0.20, 0.30, 0.40])
    a = exploracion._adelante(r, 2)
    assert a.iloc[0] == pytest.approx(1.2 * 1.3 - 1)
    assert a.iloc[-2:].isna().all()


@requiere_datos
def test_la_exploracion_no_ve_2016():
    x = exploracion.sector()
    assert x.index.max() == pd.Timestamp("2015-12-31")
    assert x["efectivo"].notna().all() and x["efectivo"].between(0, 0.02).all()
    f = exploracion.frecuencia_efectivo_gana(x)
    # Las ventanas de 12 meses terminan en diciembre de 2015: la última empieza en diciembre de 2014.
    assert f.set_index("horizonte_meses").loc[12, "ventanas"] == len(x) - 12


@requiere_datos
def test_los_indicadores_no_miran_el_futuro():
    """Cortar los datos en 2005 no cambia ningún indicador hasta 2005."""
    x = exploracion.sector()
    completo = exploracion.indicadores(x)
    corte = pd.Timestamp("2005-12-31")
    parcial = exploracion.indicadores(x.loc[:corte])
    pd.testing.assert_frame_equal(completo.loc[:corte], parcial, check_freq=False)


@requiere_datos
def test_los_oraculos_marcan_el_techo():
    x = exploracion.sector()
    t = exploracion.techo(x).tabla.set_index(["regla", "modo"])
    base = t.loc[("aportar siempre", "nunca vende"), "tir"]
    # Conocer el futuro siempre ayuda, y equivocarse siempre cuesta.
    assert t.loc[("oráculo de los 12 meses siguientes", "rebalancea"), "tir"] > base
    assert t.loc[("anti-oráculo de 12 meses", "rebalancea"), "tir"] < base
    assert np.isfinite(t["tir"]).all()
