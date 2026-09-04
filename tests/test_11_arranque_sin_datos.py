"""Prueba 11 — La aplicación no truena cuando todavía no hay datos.

Los dos defectos de este archivo aparecieron en el primer despliegue real y
comparten forma: el código funcionaba con la base llena y tronaba con la base a
medias. Es el estado normal de un arranque en la nube —la ingesta va corriendo,
una serie macro todavía no llega, una columna quedó sin cuadrar— y es justo el
momento en que el usuario abre la página por primera vez.

Ninguno se veía en desarrollo, porque en desarrollo la base ya estaba sembrada.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.config import SERIE_UDIBONO10, SERIE_UST10
from src.datos.repositorio import serie_vacia

# --------------------------------------------------------------------------------------
# 11.1 Una serie vacía se puede rebanar por fecha
# --------------------------------------------------------------------------------------


def test_la_serie_vacia_esta_indexada_por_fecha():
    """Una ``pd.Series`` vacía nace con índice entero, y eso rompe todo lo demás.

    ``s[s.index <= corte]`` es el modismo de este sistema entero: es como se hace
    cumplir el point-in-time. Contra un índice entero lanza «'<=' not supported
    between instances of 'numpy.ndarray' and 'Timestamp'», que no se parece en
    nada a "no hay datos".
    """
    s = serie_vacia("cualquiera")
    assert isinstance(s.index, pd.DatetimeIndex)
    # La operación que tronaba, ahora inofensiva.
    assert s[s.index <= pd.Timestamp("2026-01-01")].empty


def test_valor_tasa_sin_datos_devuelve_none_en_vez_de_tronar(repo_vacio):
    """Preguntar por una serie que no existe todavía es normal, no un error.

    Pasa en cada arranque: sin token de Banxico no hay Udibono, y la portada lo
    pregunta antes de dibujar nada. Tiene que responder "no hay", no tumbar la
    página con un TypeError de pandas.
    """
    assert repo_vacio.valor_tasa(SERIE_UDIBONO10, asof=dt.date(2026, 9, 4)) is None
    assert repo_vacio.valor_tasa(SERIE_UST10, asof=dt.date(2026, 9, 4)) is None


def test_las_series_del_repositorio_vacio_se_pueden_rebanar(repo_vacio):
    """Las tres series con índice de fechas que devuelve el repositorio."""
    corte = dt.date(2026, 9, 4)
    series = [
        repo_vacio.serie("FANTASMA", "affo", asof=corte),
        repo_vacio.serie_precio("FANTASMA", asof=corte),
        repo_vacio.tasa(SERIE_UST10, asof=corte),
    ]
    for s in series:
        assert s.empty
        assert isinstance(s.index, pd.DatetimeIndex), (
            "Una serie vacía sin índice de fechas es una bomba de tiempo: solo "
            "explota cuando no hay datos."
        )
        assert s[s.index <= pd.Timestamp(corte)].empty


def test_con_datos_valor_tasa_sigue_respetando_el_corte(repo_vacio):
    """Control: el arreglo no volvió permisiva la consulta point-in-time."""
    repo_vacio.guardar_tasas(
        [
            {"serie": SERIE_UST10, "fecha_dato": dt.date(2026, 1, 15),
             "fecha_publicacion": dt.date(2026, 1, 15), "valor": 0.041, "fuente": "FRED"},
            {"serie": SERIE_UST10, "fecha_dato": dt.date(2026, 6, 15),
             "fecha_publicacion": dt.date(2026, 6, 15), "valor": 0.047, "fuente": "FRED"},
        ]
    )
    assert repo_vacio.valor_tasa(SERIE_UST10, asof=dt.date(2026, 3, 1)) == pytest.approx(0.041)
    assert repo_vacio.valor_tasa(SERIE_UST10, asof=dt.date(2026, 9, 1)) == pytest.approx(0.047)
    assert repo_vacio.valor_tasa(SERIE_UST10, asof=dt.date(2025, 12, 1)) is None


# --------------------------------------------------------------------------------------
# 11.2 Una celda faltante no es un cero, y no tiene valor de verdad
# --------------------------------------------------------------------------------------


def _comun():
    """Importa el módulo de la interfaz sin arrastrar el resto de la aplicación."""
    return pytest.importorskip("app.comun", reason="requiere streamlit")


def test_pd_na_no_se_puede_evaluar_como_booleano():
    """El porqué de todo esto, aislado: `float(celda or 0.0)` es una trampa.

    Con ``pd.NA`` —lo normal en una columna que quedó sin datos— evaluar el ``or``
    lanza «boolean value of NA is ambiguous» y tumba la página entera. Este caso
    documenta el comportamiento de pandas para que el arreglo no se "simplifique"
    de vuelta al modismo original.
    """
    with pytest.raises(TypeError, match="ambiguous"):
        bool(pd.NA or 0.0)


@pytest.mark.parametrize("faltante", [None, pd.NA, float("nan"), pd.NaT])
def test_numero_convierte_lo_faltante_en_el_valor_por_omision(faltante):
    comun = _comun()
    assert comun.numero(faltante) is None
    assert comun.numero(faltante, 0.0) == 0.0


def test_numero_conserva_el_cero_legitimo():
    """El modismo del ``or`` confundía un cero real con un dato faltante."""
    comun = _comun()
    assert comun.numero(0.0, 99.0) == 0.0
    assert comun.numero(0, 99.0) == 0.0


def test_numero_lee_celdas_de_un_dataframe_con_faltantes():
    """El caso real: una fila donde solo algunas columnas tienen dato."""
    comun = _comun()
    fila = pd.DataFrame(
        [{"affo": 1.09, "noi": None, "acciones": 232_000_000}]
    ).astype({"noi": "Float64"}).iloc[0]

    assert comun.numero(fila.get("affo")) == pytest.approx(1.09)
    assert comun.numero(fila.get("noi")) is None
    assert comun.numero(fila.get("inexistente"), 0.0) == 0.0


def test_positivo_trata_el_cero_como_ausencia():
    """Para magnitudes donde el cero no existe: un NOI de cero o cero acciones."""
    comun = _comun()
    assert comun.positivo(0.0) is None
    assert comun.positivo(0.0, 1.0) == 1.0
    assert comun.positivo(pd.NA, 1.0) == 1.0
    assert comun.positivo(232_000_000.0) == pytest.approx(232_000_000.0)
    assert comun.positivo(-5.0) == pytest.approx(-5.0), (
        "Un valor negativo sí es un dato: solo el cero se lee como ausencia."
    )
