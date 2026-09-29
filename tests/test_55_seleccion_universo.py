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
    # Agregado antes de correr, viendo solo cuántos elegibles había por mes (commit del motor).
    assert d.minimo_de_elegibles == 30


def test_cada_industria_tiene_su_prima():
    for industria in sel.SECTOR_DE_INDUSTRIA:
        assert 0 < sel.prima_de(industria) < 0.10
    assert sel.prima_de("REIT - Retail", "Net Lease") == 0.03


# --------------------------------------------------------------------------------------
# El motor, sobre escenarios sintéticos
# --------------------------------------------------------------------------------------

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402


def test_cada_cohorte_pesa_lo_mismo_y_vive_su_plazo():
    """Con cohortes de 2 meses: la cartera de un mes es la mitad de la formada ese mes y la mitad
    de la del mes anterior, cada una de pesos iguales entre sus miembros."""
    miembros = np.array([[1, 0, 0], [0, 1, 1], [0, 0, 0]], dtype=float)
    w = sel._pesos(miembros, 2)
    assert w[0].tolist() == pytest.approx([0.5, 0, 0])            # solo vive la del mes 0 (media)
    assert w[1].tolist() == pytest.approx([0.5, 0.25, 0.25])
    assert w[2].tolist() == pytest.approx([0, 0.25, 0.25])


def test_el_retorno_usa_los_pesos_del_mes_anterior():
    """La cartera formada al cierre de un mes gana el retorno del mes siguiente, no el del mismo mes."""
    miembros = np.array([[1, 0], [1, 0], [1, 0]], dtype=float)
    r = np.array([[0.50, -0.5], [0.10, 0.9], [0.20, 0.9]])
    ret = sel.retornos_de_grupo(miembros, r, 1)
    assert np.isnan(ret[0])
    assert ret[1:].tolist() == pytest.approx([0.10, 0.20])


def _x_sintetico(n: int = 9, meses: int = 30) -> pd.DataFrame:
    fechas = pd.date_range("2010-01-31", periods=meses, freq="ME")
    filas = []
    for i in range(n):
        for k, f in enumerate(fechas):
            filas.append({"fecha": f, "ticker": f"T{i}", "retorno": 0.01 * (i + 1), "elegible": True,
                          "historia": float(i), "sector": float(i), "ddm": float(i),
                          "recorto_antes": i == 8, "recorto_despues": float(i == 7),
                          "retorno_12m_siguiente": (1.01 * (i + 1)) ** 0 * 0.12 * (i + 1) if k < meses - 12 else np.nan})
    return pd.DataFrame(filas)


def test_los_terciles_van_de_la_senal_mas_alta_a_la_mas_baja():
    x = _x_sintetico()
    g = sel.grupos(x, "historia")
    ultimo = x["fecha"].max()
    por_ticker = dict(zip(x.loc[x["fecha"] == ultimo, "ticker"], g[x["fecha"] == ultimo], strict=True))
    assert [por_ticker[f"T{i}"] for i in range(9)] == ["caro"] * 3 + ["medio"] * 3 + ["barato"] * 3
    # El filtro saca a quien recortó antes (T8) y recalcula los terciles con los demás.
    gf = sel.grupos(x, "historia", filtro=True)
    assert gf[(x["ticker"] == "T8")].isna().all()


def test_la_correlacion_y_las_trampas_se_cuentan_bien():
    """La correlación pide al menos 10 emisores en el mes; con 12, los terciles son de 4."""
    x = _x_sintetico(n=12)
    x["recorto_despues"] = (x["ticker"] == "T10").astype(float)
    c = sel.correlacion(x, "historia")
    assert len(c) > 0 and c.min() == pytest.approx(1.0)
    t = sel.trampas(x, "historia")
    # T10 recorta después y está en el tercil barato (T8–T11): una cuarta parte de sus observaciones.
    assert t.loc["barato", "recorto_despues"] == pytest.approx(1 / 4)
    assert t.loc["todos", "recorto_despues"] == pytest.approx(1 / 12)


def test_la_cartera_barata_gana_lo_de_sus_miembros():
    """Cada emisor rinde fijo cada mes: la cartera barata (T6–T8) rinde su promedio, 8%."""
    x = _x_sintetico()
    c = sel.carteras(x, "historia", diseno=sel.Diseno(meses_de_cohorte=3))
    assert c.mensual["barato"].dropna().to_numpy() == pytest.approx(0.08)
    assert c.mensual["caro"].dropna().to_numpy() == pytest.approx(0.02)
    assert c.mensual["todos"].dropna().to_numpy() == pytest.approx(0.05)


def test_la_aportacion_a_uno_que_rinde_fijo_tiene_esa_tir():
    x = _x_sintetico(n=3, meses=40)
    x["retorno"] = 0.01
    a = sel.aportacion(x, None)
    assert a["tir"] == pytest.approx(1.01 ** 12 - 1, abs=1e-3)


def test_los_dividendos_se_suman_en_su_ventana():
    div = pd.DataFrame({"fecha_ex": pd.to_datetime(["2020-01-15", "2020-06-15", "2021-01-15"]), "monto": [1.0, 2.0, 4.0]})
    f = pd.DatetimeIndex(["2020-12-31", "2021-06-30"])
    assert sel._suma_dividendos(div, f, -12, 0).tolist() == [3.0, 4.0]   # el de junio de 2020 ya salió
    assert sel._suma_dividendos(div, f, 0, 12).tolist() == [4.0, 0.0]
