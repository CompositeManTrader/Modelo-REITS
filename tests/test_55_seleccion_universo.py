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


def test_un_dividendo_con_fecha_ex_en_el_cierre_cuenta_en_ese_mes():
    """La ventana es (t − 12, t]: el pago con fecha ex el mismo día del cierre ya se conocía."""
    div = pd.DataFrame({"fecha_ex": pd.to_datetime(["2020-12-31", "2021-12-31"]), "monto": [1.0, 2.0]})
    f = pd.DatetimeIndex(["2020-12-31", "2021-12-31"])
    assert sel._suma_dividendos(div, f, -12, 0).tolist() == [1.0, 2.0]
    assert sel._suma_dividendos(div, f, 0, 12).tolist() == [2.0, 0.0]


def test_un_dividendo_especial_se_reconoce_contra_los_cuatro_anteriores():
    fechas = pd.date_range("2015-03-15", periods=8, freq="QE")
    div = pd.DataFrame({"ticker": "T", "fecha_ex": fechas, "monto": [1.0, 1.0, 1.0, 1.0, 5.0, 1.0, 1.05, 2.5]})
    limpios, n = sel.sin_dividendos_especiales(div)
    # El de 5.0 es más del doble de la mediana de los cuatro anteriores (1.0); 2.5 también (mediana 1.0).
    assert n == 2
    assert limpios["monto"].tolist() == [1.0, 1.0, 1.0, 1.0, 1.0, 1.05]
    # Con menos de tres pagos previos no hay contra qué comparar: el primero nunca es especial.
    assert sel.sin_dividendos_especiales(div.head(3).assign(monto=[1.0, 9.0, 1.0]))[1] == 0


# --------------------------------------------------------------------------------------
# Sobre los datos versionados: 40 emisores, los de historia más larga
# --------------------------------------------------------------------------------------


def _sub_universo(n: int = 40) -> dict[str, pd.DataFrame]:
    from src.estudio import universo

    u = universo.cargar()
    cuantos = u["precios"].groupby("ticker").size().sort_values(ascending=False)
    capital = set(u["lista"].loc[u["lista"]["es_reit_de_capital"].astype(str) == "True", "ticker"])
    tickers = [t for t in cuantos.index if t in capital][:n]
    return {k: v[v["ticker"].isin([*tickers, universo.REFERENCIA])] for k, v in u.items()}


@pytest.fixture(scope="module")
def r_universo():
    from src.estudio import universo

    if not universo.hay_universo():
        pytest.skip("No está versionado el universo de REITs.")
    return sel.estudiar(_sub_universo(), diseno=sel.Diseno(sorteos=5))


def test_las_vistas_del_universo_ponen_cada_fraccion_en_porcentaje(r_universo):
    from comun import familia_de_columna

    from src.estudio import vistas_seleccion as vs

    problemas = []
    for nombre, construir in vs.VISTAS.items():
        tabla = construir(r_universo)
        assert len(tabla), nombre
        if list(tabla.columns) != list(vs.COLUMNAS[nombre]):
            problemas.append(f"{nombre}: columnas {list(tabla.columns)}")
        for columna in tabla.columns:
            serie = pd.to_numeric(tabla[columna], errors="coerce").dropna()
            if serie.empty or tabla[columna].dtype == object or pd.api.types.is_integer_dtype(tabla[columna]):
                continue
            if columna.startswith("correlacion") or columna.startswith("t_"):
                if familia_de_columna(columna, serie) != "numero":
                    problemas.append(f"{nombre}.{columna}: una correlación o una t no es porcentaje")
                continue
            if serie.abs().max() < 1 and familia_de_columna(columna, serie) != "porcentaje":
                problemas.append(f"{nombre}.{columna}: fracción en «{familia_de_columna(columna, serie)}»")
    # Cada cifra en su escala: una volatilidad anual de REITs, una caída máxima y una razón que
    # compara contra la mediana del sector (centrada en 1x, no en cero).
    g = vs.grupos(r_universo)
    assert g["volatilidad"].dropna().between(0.05, 0.6).all()
    assert g["caida_maxima"].dropna().between(-1, 0).all()
    assert 0.8 < vs.hoy(r_universo)["razon_contra_sector"].median() < 1.25
    # Lo que no es fracción tampoco puede caer en porcentaje.
    assert familia_de_columna("razon_contra_sector") == "veces"
    assert familia_de_columna("monto_aportado") == "moneda"
    assert not problemas, "\n".join(problemas)


def test_las_conclusiones_del_universo_estan_completas(r_universo):
    import re

    c = sel.conclusiones(r_universo)
    assert [x.titulo for x in c][1:] == [
        "Los baratos concentran las trampas", "Quitar a los que ya recortaron ayuda poco",
        "Aportando cada mes sin vender nunca, cambia la foto, pero es donde más pesa el sesgo",
        "Qué tanto se le puede creer", "Lo que se escribió antes de correr", "Qué hacer con esto"]
    assert c[0].titulo.startswith("En el universo")
    for x in c:
        # Una cifra faltante se escribe «—» o «nan» donde iba un número.
        assert not re.search(r"\bnan\b|—(?: puntos|%| al año)|de — a", x.texto), x.texto
    # El veredicto de cada hipótesis está escrito, una por una.
    assert all(f"({i})" in c[5].texto for i in range(1, 6))


def test_las_senales_no_ven_el_futuro():
    """P1: cortar los datos en una fecha no cambia ninguna señal ni la elegibilidad hasta esa fecha."""
    from src.estudio import macro, universo

    if not universo.hay_universo():
        pytest.skip("No está versionado el universo de REITs.")
    u = _sub_universo(35)
    ust10 = macro.cargar("ust10")
    corte = pd.Timestamp("2012-12-31")
    cortado = {"lista": u["lista"], "precios": u["precios"][u["precios"]["fecha"] <= corte],
               "dividendos": u["dividendos"][u["dividendos"]["fecha_ex"] <= corte],
               "splits": u["splits"][u["splits"]["fecha"] <= corte]}
    columnas = ["elegible", "yield", "historia", "sector", "ddm", "recorto_antes"]
    completo = sel.panel(u, ust10).set_index(["fecha", "ticker"]).sort_index()
    parcial = sel.panel(cortado, ust10[ust10.index <= corte]).set_index(["fecha", "ticker"]).sort_index()
    a = completo.loc[completo.index.get_level_values("fecha") <= corte, columnas]
    b = parcial.loc[a.index, columnas]
    assert a["elegible"].sum() > 1_000
    pd.testing.assert_frame_equal(a, b)


def test_el_pdf_del_universo_se_arma(r_universo):
    from src.export.pdf_seleccion import html_de_seleccion

    h = html_de_seleccion(r_universo, fuentes_css="")
    for seccion in ("Lo que se encontró", "Las tres señales", "¿Predicen?", "¿Cuántos baratos eran trampa?",
                    "Aportando cada mes", "¿Aguanta?", "Qué dice hoy cada REIT", "Hipótesis escritas antes de correr"):
        assert seccion in h, seccion
    import re

    texto = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)>.*?</\1>", "", h, flags=re.S))
    assert "Yield contra su propia historia" in texto
    assert not re.search(r"\bnan\b", texto, re.I)


def test_un_mes_cuenta_solo_con_el_minimo_de_elegibles(r_universo):
    """Antes de 1998 había muy pocos para formar terciles: esos meses no cuentan."""
    x = r_universo.panel
    por_mes = x[x["elegible"]].groupby("fecha").size()
    assert por_mes.min() >= sel.DISENO.minimo_de_elegibles
    # Y sí había meses con menos, que quedaron fuera.
    crudo = x[(x["meses_de_historia"] >= 60) & (x["dividendo_12m"] > 0) & (x["precio"] >= 1)].groupby("fecha").size()
    assert (crudo.between(1, sel.DISENO.minimo_de_elegibles - 1)).any()
