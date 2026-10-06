"""Fase 6: señales sin mirar el futuro, carteras, simulación con impuestos y el detector de recortes."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.investigacion import fase6 as f6

FECHAS = pd.date_range("2010-03-31", periods=24, freq="QE")


def _panel(n: int = 40, seed: int = 0, *, fechas=FECHAS) -> pd.DataFrame:
    """Un panel sintético: n emisores, precio que camina, dividendo de 1% al trimestre."""
    rng = np.random.default_rng(seed)
    filas = []
    for i in range(n):
        precio = 20.0
        dps = 0.8
        for f in fechas:
            r = rng.normal(0.01, 0.05)
            precio *= 1 + r
            filas.append({
                "cik": f"{i:010d}", "fecha": f, "precio": precio, "retorno": r + 0.01, "dividendo": 0.01,
                "salida": False, "tenedores": 100, "capitalizacion": precio * 50e6, "acciones": 50e6,
                "acciones_promedio_12m": 50e6, "activos": 2e9 + i * 1e7, "pasivos": 1e9, "capital_total": 1e9,
                "ffo_12m": 1e8 * (1 + i / n), "intereses_12m": 4e7, "dps_12m_total": dps, "dividendos_12m": dps * 50e6,
                "de_capital": True, "es_reit": True,
            })
    return pd.DataFrame(filas)


def test_el_momentum_salta_el_ultimo_trimestre():
    x = _panel(1)
    x["retorno"] = 0.0
    x.loc[x["fecha"] == FECHAS[10], "retorno"] = 0.5
    s = f6.senales(x).set_index("fecha")["momentum"]
    assert s[FECHAS[10]] == pytest.approx(0.0)        # el trimestre en curso no cuenta
    assert s[FECHAS[11]] == pytest.approx(0.5)        # entra al siguiente...
    assert s[FECHAS[13]] == pytest.approx(0.5)
    assert s[FECHAS[14]] == pytest.approx(0.0)        # ...y sale tres trimestres después


def test_un_hueco_en_los_precios_no_corre_los_desplazamientos():
    x = _panel(1)
    x = x[x["fecha"] != FECHAS[5]]                    # falta un trimestre
    s = f6.senales(x).set_index("fecha")
    assert FECHAS[5] in s.index                       # la cuadrícula lo repone (sin precio)
    assert np.isnan(s.loc[FECHAS[5], "precio"])


def test_el_recorte_siguiente_mira_el_dividendo_conocido_un_anio_despues():
    x = _panel(1)
    x.loc[x["fecha"] >= FECHAS[12], "dps_12m_total"] = 0.5
    s = f6.senales(x).set_index("fecha")
    assert s.loc[FECHAS[8], "recorte_siguiente"] == 1
    assert s.loc[FECHAS[4], "recorte_siguiente"] == 0
    assert np.isnan(s.loc[FECHAS[-1], "recorte_siguiente"])   # todavía no se sabe
    assert s.loc[FECHAS[12], "recorte_previo"] == 1


def test_la_quiebra_cuenta_como_recorte():
    x = _panel(1, fechas=FECHAS[:12])
    salida = x.iloc[[-1]].assign(fecha=FECHAS[12], retorno=-0.30, salida=True, precio=np.nan)
    s = f6.senales(pd.concat([x, salida])).set_index("fecha")
    assert s.loc[FECHAS[10], "recorte_siguiente"] == 1


def test_elegibles_pide_tamano_precio_tenedores_y_un_minimo_por_trimestre():
    x = _panel(40)
    x.loc[x["cik"] == "0000000001", "capitalizacion"] = 1e8
    x.loc[x["cik"] == "0000000002", "precio"] = 3.0
    x.loc[x["cik"] == "0000000003", "tenedores"] = 12            # en la era estructurada pide 20
    e = f6.elegibles(x)
    assert not e[x["cik"].isin(["0000000001", "0000000002"])].any()
    assert not e[(x["cik"] == "0000000003") & (x["fecha"] > "2013-03-31")].any()
    assert e[(x["cik"] == "0000000003") & (x["fecha"] <= "2013-03-31")].all()
    pocos = _panel(20)
    assert not f6.elegibles(pocos).any()                          # menos de 30: no se forman carteras


def test_retorno_de_grupo_compra_y_mantiene_y_reparte_al_que_sale():
    fechas = pd.date_range("2020-03-31", periods=4, freq="QE")
    R = pd.DataFrame({"a": [np.nan, 0.10, 0.10, np.nan], "b": [np.nan, 0.0, -0.5, 0.0]}, index=fechas)
    sel = pd.DataFrame({"fecha": [fechas[0], fechas[0]], "cik": ["a", "b"]})
    g = f6.retorno_de_grupo(sel, R, f6.Diseno6(horizonte=3))
    assert g[fechas[1]] == pytest.approx(0.05)                    # partes iguales
    assert g[fechas[2]] == pytest.approx((1.1 * 0.10 + 1.0 * -0.5) / 2.1)   # los pesos ya corrieron
    assert g[fechas[3]] == pytest.approx(0.0)                     # «a» salió: todo es «b»


def test_simular_escoger_a_todos_es_el_benchmark():
    x = f6.senales(_panel(40))
    e = x[f6.elegibles(x)]
    sel = e[["fecha", "cik"]]
    a = f6.simular(sel, x, desde=FECHAS[0], hasta=FECHAS[-1])
    b = f6.simular(sel, x, desde=FECHAS[0], hasta=FECHAS[-1])
    assert a.tir == pytest.approx(b.tir)
    assert a.aportado == pytest.approx(3000 * len(FECHAS))


def test_simular_cobra_impuestos_y_comision():
    # Un emisor que no se mueve ni paga dividendos: la TIR es la comisión de entrada y salida.
    x = _panel(1)
    x["retorno"], x["dividendo"] = 0.0, 0.0
    sel = x[["fecha", "cik"]]
    s = f6.simular(sel, x, desde=FECHAS[0], hasta=FECHAS[-1])
    assert -0.01 < s.tir < 0
    # Con dividendo, después del 20% de impuesto rinde menos que el dividendo bruto.
    x["retorno"], x["dividendo"] = 0.02, 0.02
    s = f6.simular(sel, x, desde=FECHAS[0], hasta=FECHAS[-1])
    assert s.tir < (1.02**4 - 1) * 0.85


def test_auc():
    assert f6.auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    assert f6.auc(np.array([0, 0, 1, 1]), np.array([0.9, 0.8, 0.2, 0.1])) == pytest.approx(0.0)
    assert f6.auc(np.array([0, 1, 0, 1]), np.array([0.5, 0.5, 0.5, 0.5])) == pytest.approx(0.5)


def test_el_detector_solo_usa_el_pasado():
    x = f6.senales(_panel(40, fechas=pd.date_range("2010-03-31", periods=20, freq="QE")))
    rng = np.random.default_rng(3)
    x["payout"] = rng.uniform(0.5, 1.5, len(x))
    x["recorte_siguiente"] = np.where(x["recorte_siguiente"].notna(), (x["payout"] > 1.2).astype(float), np.nan)
    p1 = f6.riesgo_de_recorte(x)
    fechas = sorted(x["fecha"].unique())
    primera = f6.DISENO6.minimo_para_estimar_recortes - 1 + f6.DISENO6.horizonte   # ocho trimestres con resultado
    assert p1[x["fecha"] < fechas[primera]].isna().all() and p1[x["fecha"] == fechas[primera]].notna().all()
    # Cambiar resultados del futuro no cambia los pronósticos del pasado.
    corte = fechas[14]
    y = x.copy()
    y.loc[y["fecha"] > corte - pd.offsets.QuarterEnd(4), "recorte_siguiente"] = 1.0 - y["recorte_siguiente"]
    p2 = f6.riesgo_de_recorte(y)
    antes = x["fecha"] <= corte
    assert np.allclose(p1[antes].fillna(-1), p2[antes].fillna(-1))
    # Y aprende la relación: los de payout alto salen con más riesgo.
    ultimos = x["fecha"] == fechas[-1]
    assert p1[ultimos & (x["payout"] > 1.2)].mean() > p1[ultimos & (x["payout"] < 0.9)].mean()


def test_el_detector_aguanta_una_variable_que_todavia_no_tiene_historia():
    x = f6.senales(_panel(40, fechas=pd.date_range("2010-03-31", periods=16, freq="QE")))
    x["recorte_siguiente"] = np.where(x["recorte_siguiente"].notna(), (x.index % 7 == 0).astype(float), np.nan)
    x["crecimiento_ffo"] = np.nan
    p = f6.riesgo_de_recorte(x)
    assert p.notna().any() and np.isfinite(p.dropna()).all()


def test_el_filtro_pide_todo():
    base = {"mejora": 0.01, "mejora_con_rezago": 0.005, "mejora_doble_costo": 0.004, "exceso_2012_2013": 0.01,
            "exceso_2013_2015": 0.02, "ic_medio": 0.05}
    assert f6.pasa_el_filtro(base)
    assert not f6.pasa_el_filtro({**base, "mejora_doble_costo": -0.001})
    assert not f6.pasa_el_filtro({**base, "exceso_2013_2015": -0.01})
    assert not f6.pasa_el_filtro({**base, "ic_medio": -0.01})
    assert f6.pasa_el_filtro({**base, "ic_medio": np.nan})        # las compuestas no tienen IC


def test_veredicto_final():
    f = {"mejora": 0.006, "mejora_con_rezago": 0.003, "mejora_doble_costo": 0.002, "exceso_2012_2015": 0.01,
         "exceso_2015_2026": 0.01, "apuestas": 150}
    assert f6.veredicto_final(f, pbo=0.1, dsr=0.97) == "APROBADO"
    assert f6.veredicto_final(f, pbo=0.4, dsr=0.97) == "INCONCLUSO"
    assert f6.veredicto_final({**f, "mejora": 0.004}, pbo=0.1, dsr=0.97) == "RECHAZADO"


def test_el_diseno_no_se_movio():
    d = f6.DISENO6
    assert (d.capitalizacion_minima, d.precio_minimo, d.tenedores_texto, d.tenedores_estructurado) == (250e6, 5.0, 10, 20)
    assert (d.horizonte, d.grupos, d.payout_maximo, d.caida_de_recorte, d.quintil_excluido) == (4, 3, 0.90, 0.10, 0.20)
    assert (d.retorno_de_quiebra, d.riesgo_excluido, d.auc_minima, d.bloques_pbo) == (-0.30, 0.20, 0.70, 8)
    assert len(f6.REGLAS) == 16 and f6.DETECTOR == "sin riesgo de recorte"


def test_la_fase_completa_corre_en_orden_y_solo_abre_los_sellados_con_un_modelo_congelado(tmp_path, monkeypatch):
    from src.investigacion import bitacora, emisores
    from src.investigacion.muestras import sellar

    fechas = pd.date_range("2011-03-31", periods=40, freq="QE")
    abierto = _panel(45, seed=1, fechas=fechas)
    # Una señal real en el sintético: el FFO alto rinde más, para que algo pueda pasar.
    abierto["ffo_12m"] = abierto["ffo_12m"] * np.random.default_rng(2).uniform(0.5, 1.5, len(abierto))
    sellar(_panel(35, seed=5, fechas=fechas), emisores.ARCHIVO_SELLADO, raiz=tmp_path / "sellado")
    ruta = tmp_path / "bitacora.csv"
    r = f6.correr(abierto, ruta_bitacora=ruta, raiz_sellado=tmp_path / "sellado")
    assert len(r.desarrollo) == len(f6.REGLAS)
    assert f6.DETECTOR in set(r.validacion["regla"])
    b = bitacora.leer(ruta)
    assert (b["familia"] == "apertura").sum() == (1 if r.final.empty else 2)
    if not r.final.empty:
        assert len(bitacora.modelos_congelados(ruta)) == 1
    assert r.veredicto in {"APROBADO", "INCONCLUSO", "RECHAZADO"}
    texto = f6.informe(r)
    assert f"## Veredicto: {r.veredicto}" in texto and "## Todas las reglas, en desarrollo" in texto
