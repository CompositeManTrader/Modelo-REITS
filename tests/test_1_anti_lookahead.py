"""Prueba obligatoria 1 — Anti-lookahead (P1).

Truncar las series en varios puntos y verificar que los valores pasados no
cambian. Si cambian sin una reexpresión que lo justifique, hay lookahead.

Se prueba en tres niveles, del más débil al más fuerte:

1. La consulta al repositorio filtra por ``fecha_publicacion``.
2. La respuesta a un corte no se mueve cuando llega información posterior.
3. La señal completa — prima y percentil expandible — es estable bajo
   truncamiento en cuatro puntos.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.config import Estado, Fuente
from src.datos.repositorio import Repositorio, exigir_corte
from src.modelo.senal import percentil_expandible
from src.validacion.pit import (
    constructor_reexpresion,
    cortes_uniformes,
    prueba_pureza,
    prueba_truncamiento,
)


def _hecho(fecha_dato, fecha_publicacion, valor, ticker="TEST", concepto="affo"):
    return {
        "ticker": ticker,
        "concepto": concepto,
        "periodo_tipo": "Q",
        "fecha_dato": fecha_dato,
        "fecha_publicacion": fecha_publicacion,
        "valor": valor,
        "unidad": "USD",
        "fuente": Fuente.MANUAL,
        "es_primario": False,
        "estado": Estado.VALIDO,
    }


# --------------------------------------------------------------------------------------
# Nivel 0: no existe una consulta sin corte
# --------------------------------------------------------------------------------------


def test_no_existe_consulta_sin_corte(repo_vacio: Repositorio):
    """Omitir el corte tiene que fallar ruidosamente, no asumir 'hoy'.

    Un corte implícito de hoy es la puerta de entrada al lookahead en cuanto el
    código se reutiliza dentro de un backtest.
    """
    with pytest.raises(TypeError):
        repo_vacio.hechos()  # type: ignore[call-arg]

    with pytest.raises(ValueError, match="point-in-time"):
        exigir_corte(None)


# --------------------------------------------------------------------------------------
# Nivel 1: el filtro por fecha de publicación
# --------------------------------------------------------------------------------------


def test_dato_publicado_despues_del_corte_es_invisible(repo_vacio: Repositorio):
    repo_vacio.guardar_hechos(
        [
            _hecho(dt.date(2025, 3, 31), dt.date(2025, 5, 5), 1.00),
            _hecho(dt.date(2025, 6, 30), dt.date(2025, 8, 5), 1.05),
            _hecho(dt.date(2025, 9, 30), dt.date(2025, 11, 4), 1.08),
        ]
    )

    # Al 1 de agosto, el trimestre de junio todavía no se publicaba.
    serie = repo_vacio.serie("TEST", "affo", asof=dt.date(2025, 8, 1))
    assert list(serie.index.date) == [dt.date(2025, 3, 31)]

    # Al 6 de agosto ya sí.
    serie = repo_vacio.serie("TEST", "affo", asof=dt.date(2025, 8, 6))
    assert list(serie.index.date) == [dt.date(2025, 3, 31), dt.date(2025, 6, 30)]


def test_reexpresion_no_reescribe_el_pasado(repo_vacio: Repositorio):
    """Una reexpresión es una FILA NUEVA. Ambas versiones conviven en la base."""
    repo_vacio.guardar_hechos(
        [
            _hecho(dt.date(2025, 3, 31), dt.date(2025, 5, 5), 1.00),
            _hecho(dt.date(2025, 3, 31), dt.date(2025, 11, 4), 0.97),  # reexpresado
        ]
    )
    revisiones = repo_vacio.revisiones("TEST", "affo", dt.date(2025, 3, 31))
    assert len(revisiones) == 2, "La reexpresión debe conservar la versión original."

    antes = repo_vacio.serie("TEST", "affo", asof=dt.date(2025, 6, 1))
    despues = repo_vacio.serie("TEST", "affo", asof=dt.date(2025, 12, 1))
    assert float(antes.iloc[0]) == pytest.approx(1.00)
    assert float(despues.iloc[0]) == pytest.approx(0.97)


def test_guia_no_usa_la_revision_del_futuro(repo_sembrado: Repositorio):
    """El caso documentado: guía de febrero contra guía de agosto.

    En febrero de 2026 Realty Income guiaba 4.38–4.42 de AFFO por acción y en
    agosto la subió a 4.44–4.45. Un modelo que use 4.445 para fechas de marzo
    está usando información del futuro.
    """
    en_marzo = repo_sembrado.guia_vigente("O", 2026, asof=dt.date(2026, 3, 15))
    assert en_marzo is not None
    assert en_marzo["valor_max"] == pytest.approx(4.42)
    assert en_marzo["punto_medio"] == pytest.approx(4.40)

    en_septiembre = repo_sembrado.guia_vigente("O", 2026, asof=dt.date(2026, 9, 15))
    assert en_septiembre["valor_max"] == pytest.approx(4.45)

    antes_de_la_primera = repo_sembrado.guia_vigente("O", 2026, asof=dt.date(2026, 1, 10))
    assert antes_de_la_primera is None, "Antes de publicarse, la guía no existe."


# --------------------------------------------------------------------------------------
# Nivel 2: pureza — información nueva no mueve la respuesta a un corte viejo
# --------------------------------------------------------------------------------------


def test_pureza_de_la_consulta(repo_vacio: Repositorio):
    repo_vacio.guardar_hechos(
        [
            _hecho(dt.date(2024, 3, 31), dt.date(2024, 5, 5), 1.00),
            _hecho(dt.date(2024, 6, 30), dt.date(2024, 8, 5), 1.02),
        ]
    )
    corte = dt.date(2024, 9, 1)

    def evaluar(asof):
        return repo_vacio.serie("TEST", "affo", asof=asof)

    def agregar():
        repo_vacio.guardar_hechos(
            [
                _hecho(dt.date(2024, 9, 30), dt.date(2024, 11, 4), 1.06),
                _hecho(dt.date(2024, 12, 31), dt.date(2025, 2, 20), 1.09),
            ]
        )

    resultado = prueba_pureza(evaluar, corte, agregar)
    assert resultado.sin_lookahead, resultado.como_texto()


# --------------------------------------------------------------------------------------
# Nivel 3: truncamiento en cuatro puntos sobre la señal completa
# --------------------------------------------------------------------------------------


def test_truncamiento_en_cuatro_puntos_sobre_la_senal(repo_sembrado: Repositorio):
    """La prueba obligatoria: cuatro cortes, y el pasado no se mueve.

    Se evalúa la señal completa — AFFO por acción TTM sobre precio crudo, prima
    contra el UST de 10 años, y su percentil expandible — que es la cadena entera
    de la que cuelga cualquier decisión.
    """
    from src.servicio import construir_panel

    def evaluar(asof: dt.date) -> pd.Series:
        panel = construir_panel(repo_sembrado, "O", asof=asof)
        return panel.percentil.dropna()

    cortes = cortes_uniformes(dt.date(2021, 1, 1), dt.date(2026, 6, 30), n=4)
    assert len(cortes) == 4

    resultado = prueba_truncamiento(
        evaluar,
        cortes,
        hubo_reexpresion=constructor_reexpresion(repo_sembrado, "O", "affo_por_accion"),
    )
    assert resultado.n_comparaciones > 0, "La prueba no comparó nada: revisa los cortes."
    assert resultado.sin_lookahead, resultado.como_texto()


def test_percentil_expandible_es_estable_bajo_truncamiento():
    """El percentil de una fecha no puede cambiar porque llegaron datos después.

    Es la propiedad que define la ventana expandible y la razón por la que existe:
    con la muestra completa, el percentil de 2019 cambiaría cada vez que llega un
    trimestre nuevo.
    """
    fechas = pd.date_range("2015-03-31", periods=40, freq="QE")
    serie = pd.Series(
        [0.02 + 0.001 * i + 0.004 * ((-1) ** i) for i in range(40)], index=fechas
    )

    completa = percentil_expandible(serie, min_observaciones=12)
    for corte in (20, 26, 33):
        truncada = percentil_expandible(serie.iloc[:corte], min_observaciones=12)
        comun = truncada.dropna().index
        pd.testing.assert_series_equal(
            truncada.loc[comun], completa.loc[comun], check_names=False,
            obj=f"Percentil expandible truncado en {corte}",
        )


def test_percentil_de_muestra_completa_si_cambia_con_el_futuro():
    """Control: el método prohibido SÍ cambia el pasado. Por eso está prohibido.

    Si esta prueba fallara, significaría que la distinción entre ventana
    expandible y muestra completa no importa, y la mitad de P5 sobraría.
    """
    from src.modelo.senal import percentil_ventana_completa

    fechas = pd.date_range("2015-03-31", periods=40, freq="QE")
    serie = pd.Series([0.02 + 0.001 * i for i in range(40)], index=fechas)

    corto = percentil_ventana_completa(serie.iloc[:20])
    largo = percentil_ventana_completa(serie)
    assert not corto.iloc[:20].equals(largo.iloc[:20]), (
        "Con muestra completa el pasado DEBE moverse al llegar datos nuevos. "
        "Si no se movió, la prueba no está midiendo lo que cree."
    )


def test_precio_no_se_ve_antes_de_su_fecha(repo_sembrado: Repositorio):
    """Los precios también son point-in-time: no hay cierre del futuro."""
    corte = dt.date(2023, 6, 30)
    serie = repo_sembrado.serie_precio("O", asof=corte)
    assert not serie.empty
    assert serie.index.max().date() <= corte


def test_tasa_macro_respeta_su_rezago_de_publicacion(repo_sembrado: Repositorio):
    """El INPC de un mes se publica a mediados del siguiente; el modelo lo respeta."""
    from src.config import SERIE_INPC

    serie = repo_sembrado.tasa(SERIE_INPC, asof=dt.date(2024, 3, 5))
    assert not serie.empty
    # Con rezago de 9 días, el dato de febrero (28) se publica el 8 de marzo:
    # al 5 de marzo el último observable es el de enero.
    assert serie.index.max().date() <= dt.date(2024, 2, 28)
