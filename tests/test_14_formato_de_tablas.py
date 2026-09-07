"""Prueba 14 — Los números se dibujan legibles, y se escalan UNA sola vez.

Dos errores distintos viven en el formato de una tabla, y el segundo es caro:

1. **Ilegibilidad.** ``435000000.0`` obliga a contar ceros con el dedo. Molesto,
   pero visible: nadie lo confunde con un dato correcto.
2. **Escala doble o nula.** El formato ``"%.2f%%"`` de Streamlit **solo pega el
   símbolo de porcentaje, no multiplica por cien**. Un AFFO yield de ``0.0553``
   se dibuja como ``0.06%`` en vez de ``5.53%``: el número se ve razonable, la
   tabla se ve correcta, y la conclusión está mal por dos órdenes de magnitud.
   Es exactamente el mismo error que en las celdas en puntos base del Excel,
   donde una prima de 409 bps se mostraba como «0 bps» por confiar en el formato.

Por eso la escala vive en el DATO y el formato nunca convierte unidades. Estas
pruebas fijan esa regla y, sobre todo, fijan que la escala ocurre **una vez**:
las páginas que ya escalaban a mano pasan su propia configuración, y lo
explícito tiene que ganar para que no se multiplique dos veces por cien.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
for ruta in (str(RAIZ), str(RAIZ / "app")):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from comun import formato_columnas  # noqa: E402


def _formato(config: dict, columna: str) -> str:
    """El string de formato que Streamlit va a aplicar a esa columna."""
    return config[columna]["type_config"]["format"]


# --------------------------------------------------------------------------------------
# 14.1 La escala va en el dato
# --------------------------------------------------------------------------------------


def test_el_porcentaje_se_escala_en_el_dato_no_en_el_formato():
    """0.0553 tiene que salir como 5.53 con formato "%%", no como 0.0553."""
    df = pd.DataFrame({"affo_yield": [0.0553], "payout_affo": [0.7312]})
    vista, config = formato_columnas(df)

    assert vista["affo_yield"].iloc[0] == pytest.approx(5.53)
    assert vista["payout_affo"].iloc[0] == pytest.approx(73.12)
    assert _formato(config, "affo_yield").endswith("%%")
    # Y el dato original no se toca: se trabaja sobre una copia.
    assert df["affo_yield"].iloc[0] == pytest.approx(0.0553)


def test_la_columna_en_bps_no_se_vuelve_a_escalar():
    """Por convención, `*_bps` ya nace en puntos base en `servicio.py`.

    Escalarla otra vez aquí la multiplicaría por diez mil y una prima de 409 bps
    se dibujaría como 4,093,000 bps.
    """
    df = pd.DataFrame({"prima_bps": [409.3]})
    vista, config = formato_columnas(df)

    assert vista["prima_bps"].iloc[0] == pytest.approx(409.3)
    assert "bps" in _formato(config, "prima_bps")


def test_lo_explicito_manda_sobre_el_formato_pero_nunca_sobre_las_unidades():
    """El defecto que se vio en producción, fijado como prueba.

    La primera versión dejaba que una `column_config` propia se llevara también
    la escala. Resultado en la portada: la tabla del Nareit dibujaba 11.78% como
    «0.12%» y el percentil de prima dibujaba 13% como «0%», porque las dos
    pasaban configuración propia y quedaban fuera del escalado.

    La regla ahora es una sola: quien llama manda sobre la etiqueta y el formato,
    que son presentación; nunca sobre las unidades, que son el dato.
    """
    df = pd.DataFrame({"affo_yield": [0.0553]})
    mio = {"affo_yield": "Mi etiqueta"}
    vista, config = formato_columnas(df, mio)

    assert vista["affo_yield"].iloc[0] == pytest.approx(5.53), "la config propia se llevó la escala"
    assert config["affo_yield"] == "Mi etiqueta"


def test_ninguna_pagina_escala_a_mano():
    """El control del contrato: si una página multiplica por cien, se duplica.

    Con la escala centralizada, un `* 100` en una página ya no corrige nada;
    dibuja 553%. Esta prueba lo caza en el código, no en la pantalla.
    """
    culpables = []
    for pagina in sorted((RAIZ / "app").rglob("*.py")):
        if pagina.name == "comun.py":
            continue  # es el único lugar donde la escala es correcta
        for numero, linea in enumerate(pagina.read_text(encoding="utf-8").splitlines(), 1):
            if "* 100" in linea and not linea.lstrip().startswith("#"):
                culpables.append(f"{pagina.relative_to(RAIZ)}:{numero}: {linea.strip()}")
    assert not culpables, "escalan a mano y se van a duplicar:\n" + "\n".join(culpables)


def test_la_aguja_casa_por_token_completo_no_por_subcadena():
    """`tir` es una tasa; `retiro` es dinero. La segunda contiene a la primera."""
    df = pd.DataFrame({"tir_real": [0.0812], "retiro": [50_000.0], "aportacion": [10_000.0]})
    vista, config = formato_columnas(df)

    assert vista["tir_real"].iloc[0] == pytest.approx(8.12)
    assert vista["retiro"].iloc[0] == pytest.approx(50_000.0), "trató un retiro como porcentaje"
    assert _formato(config, "tir_real").endswith("%%")
    assert _formato(config, "retiro").startswith("$")


def test_las_columnas_de_porcentaje_de_la_aplicacion_se_reconocen():
    """Inventario de las que de verdad se dibujan. Una que se escape sale sin escalar."""
    columnas = (
        "affo_yield", "dividend_yield", "payout_affo", "percentil_prima",
        "crecimiento_affo_por_accion_yoy", "cap_rate_implicito", "premio_descuento_nav",
        "Tasa efectiva", "Tasa efectiva sobre renta", "Rendimiento", "rendimiento",
        "pct_renta", "cambio_pct", "caida_portafolio", "tir_nominal", "tir_real",
        "plusvalia_anualizada", "brecha_vs_reits", "yield_neto_reits",
        "rendimiento_corriente", "probabilidad_supuesta", "spread_inversion",
        "rendimiento_nominal", "rendimiento_real", "ltv", "payout_ffo",
    )
    df = pd.DataFrame({c: [0.10] for c in columnas})
    vista, _config = formato_columnas(df)
    sin_escalar = [c for c in columnas if vista[c].iloc[0] != pytest.approx(10.0)]
    assert not sin_escalar, f"no se reconocieron como porcentaje: {sin_escalar}"


def test_el_hueco_no_se_dibuja_como_la_palabra_none():
    """Siete de diez emisores no tienen AFFO todavía. La tabla se llenaba de «None».

    Streamlit escribe la palabra "None" en toda celda vacía que no sea de progreso.
    En una tabla de diez emisores donde siete no tienen historia suficiente, eso
    hace ver la tabla como si estuviera rota, y además está en inglés.
    """
    import comun

    assert comun._ACEPTA_PLACEHOLDER, (
        "esta versión de Streamlit no acepta `placeholder`; sin él las celdas "
        "vacías vuelven a decir «None»"
    )
    capturado: dict = {}
    original = comun.st.dataframe
    comun.st.dataframe = lambda datos, **kw: capturado.update(kw)
    try:
        comun.mostrar_tabla(pd.DataFrame({"affo_yield": [None]}, dtype="float64"))
    finally:
        comun.st.dataframe = original

    assert capturado.get("placeholder") not in (None, "None")


# --------------------------------------------------------------------------------------
# 14.2 Separadores de miles y unidades
# --------------------------------------------------------------------------------------


def test_los_montos_grandes_llevan_separador_de_miles():
    df = pd.DataFrame({"noi": [435_000_000.0]})
    _vista, config = formato_columnas(df)
    assert "," in _formato(config, "noi")


def test_el_monto_chico_conserva_decimales_y_el_grande_no():
    """Un precio de 60.25 sin decimales miente; un NOI con centavos estorba."""
    df = pd.DataFrame({"metrica_chica": [3.14], "metrica_grande": [435_000_000.0]})
    _vista, config = formato_columnas(df)
    assert _formato(config, "metrica_chica") == "%,.2f"
    assert _formato(config, "metrica_grande") == "%,.0f"


def test_cada_familia_de_columna_recibe_su_unidad():
    df = pd.DataFrame(
        {
            "precio": [60.25],
            "affo_por_accion": [4.19],
            "p_affo": [14.4],
            "n_observaciones": [12],
            "cap_rate_implicito": [0.0612],
        }
    )
    _vista, config = formato_columnas(df)

    assert _formato(config, "precio").startswith("$")
    assert _formato(config, "affo_por_accion").startswith("$")
    assert _formato(config, "p_affo").endswith("x")
    assert _formato(config, "n_observaciones") == "%,d"
    assert _formato(config, "cap_rate_implicito").endswith("%%")


def test_una_columna_de_texto_no_recibe_formato_numerico():
    """Formatear una columna de texto como número la rompe en Arrow.

    Sí recibe **etiqueta**, que es otra cosa: el encabezado no es el dato. Sin ella
    la tabla dibujaba la clave cruda, y una misma tabla mezclaba un "Aporte" bien
    puesto con un "explicacion" sin acento.
    """
    df = pd.DataFrame({"ticker": ["O"], "accion": ["COMPRAR"], "precio": [60.25]})
    vista, config = formato_columnas(df)

    for columna in ("ticker", "accion"):
        assert "format" not in config[columna].get("type_config", {}), (
            f"{columna} es texto y no puede llevar formato numérico"
        )
        # Y el dato no se toca: escalarlo o convertirlo es lo que rompe Arrow.
        assert list(vista[columna]) == list(df[columna])

    assert _formato(config, "precio").startswith("$")


def test_el_encabezado_se_escribe_en_espanol():
    """La clave va sin acentos porque es un identificador; el encabezado no es la clave."""
    df = pd.DataFrame({"explicacion": ["texto"], "accion": ["COMPRAR"],
                       "retencion_eeuu": [12.5], "n_observaciones": [8]})
    _vista, config = formato_columnas(df)
    etiquetas = {c: config[c]["label"] for c in config}
    assert etiquetas["explicacion"] == "Explicación"
    assert etiquetas["accion"] == "Acción"
    # Una sigla no se capitaliza como palabra, y un prefijo técnico no se lee.
    assert etiquetas["retencion_eeuu"] == "Retención EE. UU."
    assert etiquetas["n_observaciones"] == "Observaciones"


def test_la_columna_vacia_no_truena():
    """Una tabla sin filas es un caso normal: emisor sin historia al corte."""
    df = pd.DataFrame({"affo_yield": pd.Series(dtype="float64")})
    vista, config = formato_columnas(df)
    assert vista.empty
    assert _formato(config, "affo_yield").endswith("%%")


def test_la_columna_toda_nula_no_truena():
    """`max()` sobre puros NaN devuelve NaN y elegir formato con eso reventaba."""
    df = pd.DataFrame({"metrica": [None, None]}, dtype="float64")
    _vista, config = formato_columnas(df)
    assert "metrica" in config
