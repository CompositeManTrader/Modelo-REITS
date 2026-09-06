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


def test_lo_explicito_de_quien_llama_siempre_gana():
    """La defensa contra la escala doble.

    Las páginas que ya multiplicaban por cien a mano pasan su propia
    configuración. Si el formato automático la pisara —o peor, si escalara
    encima— el 5.53% se dibujaría como 553%.
    """
    df = pd.DataFrame({"affo_yield": [5.53]})  # ya viene escalado por quien llama
    mio = {"affo_yield": "Mi etiqueta"}
    vista, config = formato_columnas(df, mio)

    assert vista["affo_yield"].iloc[0] == pytest.approx(5.53), "escaló encima de lo ya escalado"
    assert config["affo_yield"] == "Mi etiqueta"


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


def test_las_columnas_de_texto_se_dejan_en_paz():
    """Formatear una columna de texto como número la rompe en Arrow."""
    df = pd.DataFrame({"ticker": ["O"], "accion": ["COMPRAR"], "precio": [60.25]})
    _vista, config = formato_columnas(df)
    assert "ticker" not in config
    assert "accion" not in config
    assert "precio" in config


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
