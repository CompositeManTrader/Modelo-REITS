"""Prueba 46 — Que el pico no se coma el panel, y que tampoco se esconda.

El problema que quedaba después de arreglar los datos: diez de los ciento
cincuenta y cuatro paneles seguían ilegibles, pero ya no por cifras imposibles
sino por picos REALES. El de Public Storage es el ejemplo: la utilidad neta del
tercer trimestre de 2022 vale 2,712 millones contra una mediana de 353, porque
vendió PS Business Parks. Ese dato es verdadero y el panel lo dibujaba entero,
así que quince años de historia quedaban en una raya plana debajo de un pico.

Las dos salidas fáciles están mal
---------------------------------
Recortar el eje y ya, es esconder un dato: el lector ve una serie tranquila y no
se entera de que hubo un trimestre cinco veces mayor. Dejarlo como estaba es no
poder leer la serie. Las dos pierden información.

Lo que se hace
--------------
El eje cubre el CUERPO de la serie —del percentil 2 al 98—, el punto que se sale
se ancla al borde con un triángulo en vez de un círculo, y su valor y su fecha
se dicen en el texto de abajo: «Fuera del eje: 2,712.2 M el 2022-09-30». El
lector ve los quince años Y sabe que hay un punto afuera, cuánto vale y cuándo
fue.

Las tres condiciones para recortar
----------------------------------
1. **Que haga falta.** Si el rango natural ya deja leer la serie, no se toca.
2. **Que sean pocos.** A lo más un 10% de los puntos puede quedar fuera; más que
   eso no es un pico, es la serie, y comprimirla la falsearía. El tope va en
   FRACCIÓN y no en número fijo, y eso es lo que lo hace funcionar: la banda del
   percentil 2 al 98 deja por construcción un 4% afuera, que con setenta cortes
   son cuatro puntos, así que un tope fijo de tres no recortaba NUNCA. La primera
   versión de esto tenía ese tope y no servía para nada; se vio midiendo, no
   leyendo el código.
3. **Que el último valor quede DENTRO.** Es el que dice el número grande del
   encabezado: si quedara fuera del eje, el panel contradiría a su propio título.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
for ruta in (RAIZ, RAIZ / "app"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

from comun import (  # noqa: E402
    FRACCION_CUERPO_MINIMA,
    FRACCION_FUERA_MAXIMA,
    MINIMO_FUERA_DEL_EJE,
    _eje_del_cuerpo,
)

from src.config import UNIVERSO_INICIAL  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402
from src.servicio import (  # noqa: E402
    METRICAS_DE_GRAFICA,
    panel_de_conceptos,
    series_de_graficas,
)

HOY = dt.date.today()


@pytest.fixture(scope="module")
def repo():
    r = Repositorio()
    if r.hechos(asof=HOY, tickers="O", conceptos=["ingresos_totales"]).empty:
        pytest.skip("No hay base cargada.")
    return r


def _serie_tranquila(n: int = 60) -> np.ndarray:
    """Una serie que se lee bien con su rango natural."""
    return np.linspace(100.0, 140.0, n)


# --------------------------------------------------------------------------------------
# 46.1 · Cuándo recortar y cuándo no
# --------------------------------------------------------------------------------------


def test_una_serie_legible_no_se_toca():
    """Recortar lo que ya se lee solo agrega una regla que el lector no pidió."""
    assert _eje_del_cuerpo(_serie_tranquila()) is None


def test_un_pico_aislado_recorta_el_eje():
    """El caso de Public Storage: un trimestre cinco veces la mediana."""
    valores = _serie_tranquila()
    valores[30] = 2_000.0
    eje = _eje_del_cuerpo(valores)
    assert eje is not None
    bajo, alto = eje
    assert alto < 2_000.0, "el eje sigue abarcando el pico"
    assert bajo <= valores[0] and alto >= valores[-1], "el cuerpo quedó fuera del eje"


def test_el_punto_que_se_sale_queda_identificable():
    """No se borra: se cuenta, para poder decirlo debajo de la gráfica."""
    valores = _serie_tranquila()
    valores[30] = 2_000.0
    bajo, alto = _eje_del_cuerpo(valores)
    afuera = (valores < bajo) | (valores > alto)
    assert afuera.sum() == 1
    assert valores[afuera][0] == pytest.approx(2_000.0)


def test_una_serie_dispersa_no_se_comprime():
    """Cuando la dispersión ES la serie, comprimirla la falsearía."""
    dispersa = np.array([10.0, 900.0] * 30)
    assert _eje_del_cuerpo(dispersa) is None


def test_el_ultimo_valor_siempre_queda_dentro_del_eje():
    """Es el que dice el número grande de arriba: el panel se contradiría.

    Se cumple ESTIRANDO el eje, no renunciando a recortar. Renunciar fue el
    primer intento y estaba mal: en una serie creciente —los ingresos, la deuda,
    el flujo— el último valor está por construcción arriba del percentil 98, así
    que esa regla dejaba sin recortar justo a las series con tendencia.
    """
    valores = _serie_tranquila()
    valores[30] = 2_000.0
    bajo, alto = _eje_del_cuerpo(valores)
    assert bajo <= valores[-1] <= alto


def test_una_serie_creciente_con_un_pico_si_se_recorta():
    """La regresión del primer intento: la tendencia no puede impedir el recorte."""
    creciente = np.linspace(100.0, 900.0, 60)
    creciente[20] = 40_000.0
    eje = _eje_del_cuerpo(creciente)
    assert eje is not None, "una serie con tendencia y un pico se quedó sin recortar"
    assert eje[1] < 40_000.0
    assert eje[0] <= creciente[-1] <= eje[1]


def test_una_serie_corta_no_se_recorta():
    """Con pocos puntos, el percentil 98 no describe nada."""
    corta = np.array([100.0, 101.0, 102.0, 2_000.0, 103.0])
    assert _eje_del_cuerpo(corta) is None


def test_una_serie_plana_no_truena():
    assert _eje_del_cuerpo(np.full(40, 7.0)) is None


# --------------------------------------------------------------------------------------
# 46.2 · El tope tiene que ser una fracción, no un número
# --------------------------------------------------------------------------------------


def test_el_tope_de_puntos_fuera_escala_con_la_serie():
    """La regresión que hizo inútil la primera versión.

    La banda del percentil 2 al 98 deja por construcción un 4% afuera. Con
    setenta cortes son cuatro puntos, así que un tope FIJO de tres impedía
    recortar cualquier serie larga —las diez del universo tenían exactamente
    cuatro— y la función no hacía nada. Con el tope en fracción, sí.
    """
    assert FRACCION_FUERA_MAXIMA > 0.04, (
        "el tope tiene que dejar pasar el 4% que la propia banda produce"
    )
    assert MINIMO_FUERA_DEL_EJE == 3, "el piso es para series cortas, no para las largas"


def test_sobre_datos_reales_el_tope_fijo_habria_bloqueado_todo(repo):
    """La medición que destapó la regresión, hecha prueba.

    Los diez paneles que necesitan recorte tienen EXACTAMENTE cuatro puntos
    fuera de la banda, y el tope fijo de tres los bloqueaba a los diez: la
    función existía y no recortaba nada. No se ve leyendo el código —cuatro
    contra tres no salta— sino midiendo sobre las diez emisoras.
    """
    candidatos = 0
    for e in UNIVERSO_INICIAL:
        panel = panel_de_conceptos(repo, e.ticker, asof=HOY, periodo_tipo="Q", n_periodos=None)
        if panel.empty:
            continue
        series = series_de_graficas(panel)
        for metrica in METRICAS_DE_GRAFICA:
            if metrica.clave not in series.columns:
                continue
            serie = series[metrica.clave].dropna()
            if len(serie) < 12:
                continue
            escala = (
                100.0 if metrica.unidad == "pct"
                else (1 / 1e6 if metrica.unidad == "monto" else 1.0)
            )
            valores = np.asarray([float(v) * escala for v in serie])
            if _eje_del_cuerpo(valores) is None:
                continue
            candidatos += 1
            bajo, alto = (float(x) for x in np.nanpercentile(valores, [2, 98]))
            bajo, alto = min(bajo, valores[-1]), max(alto, valores[-1])
            fuera = int(((valores < bajo) | (valores > alto)).sum())
            assert fuera <= round(FRACCION_FUERA_MAXIMA * valores.size), (
                f"{e.ticker}/{metrica.etiqueta}: {fuera} puntos fuera de {len(valores)}"
            )
    assert candidatos >= 5, (
        f"solo {candidatos} paneles se recortan: revisa que el tope no los esté bloqueando"
    )


def test_demasiados_puntos_fuera_no_recorta():
    """Un 10% es un pico; un 30% es un tramo de la serie."""
    valores = _serie_tranquila(60)
    valores[:20] = 2_000.0
    assert _eje_del_cuerpo(valores) is None


# --------------------------------------------------------------------------------------
# 46.3 · Sobre las diez emisoras
# --------------------------------------------------------------------------------------


def test_ningun_panel_del_universo_queda_ilegible(repo):
    """El piso medido: ninguna serie dibujada en una raya plana bajo un pico."""
    ilegibles = []
    for e in UNIVERSO_INICIAL:
        panel = panel_de_conceptos(repo, e.ticker, asof=HOY, periodo_tipo="Q", n_periodos=None)
        if panel.empty:
            continue
        series = series_de_graficas(panel)
        for metrica in METRICAS_DE_GRAFICA:
            if metrica.clave not in series.columns:
                continue
            serie = series[metrica.clave].dropna()
            if len(serie) < 10:
                continue
            escala = (
                100.0 if metrica.unidad == "pct"
                else (1 / 1e6 if metrica.unidad == "monto" else 1.0)
            )
            valores = np.asarray([float(v) * escala for v in serie])
            rango = float(valores.max() - valores.min())
            if rango <= 0:
                continue
            if _eje_del_cuerpo(valores) is not None:
                continue  # se recorta, así que se lee
            bajo, alto = (float(x) for x in np.nanpercentile(valores, [2, 98]))
            if (alto - bajo) / rango < FRACCION_CUERPO_MINIMA:
                ilegibles.append(f"{e.ticker}/{metrica.etiqueta}: cuerpo en "
                                 f"{(alto - bajo) / rango:.0%} del panel")
    assert ilegibles == [], "paneles ilegibles:\n" + "\n".join(ilegibles)


def test_el_panel_de_psa_recorta_y_nombra_su_venta(repo):
    """El caso que originó todo, de punta a punta."""
    panel = panel_de_conceptos(repo, "PSA", asof=HOY, periodo_tipo="Q", n_periodos=None)
    if panel.empty:
        pytest.skip("No hay base de PSA.")
    serie = series_de_graficas(panel).get("utilidad_neta")
    if serie is None:
        pytest.skip("PSA no tiene la serie.")
    valores = np.asarray([float(v) / 1e6 for v in serie.dropna()])
    eje = _eje_del_cuerpo(valores)
    assert eje is not None, "el panel de la utilidad neta de PSA no se recorta"
    bajo, alto = eje
    afuera = valores[(valores < bajo) | (valores > alto)]
    assert afuera.size >= 1
    assert afuera.max() > 2_000, "el trimestre de la venta ya no está en la serie"


def test_recortar_no_cambia_el_numero_del_encabezado(repo):
    """El eje acomoda la vista; el valor que se reporta es el mismo."""
    from src.servicio import cambio_de_metrica

    panel = panel_de_conceptos(repo, "PSA", asof=HOY, periodo_tipo="Q", n_periodos=None)
    if panel.empty:
        pytest.skip("No hay base de PSA.")
    serie = series_de_graficas(panel).get("utilidad_neta")
    if serie is None:
        pytest.skip("PSA no tiene la serie.")
    valor, _, _ = cambio_de_metrica(serie, "monto", pasos=1)
    assert valor == pytest.approx(float(serie.dropna().iloc[-1]))
