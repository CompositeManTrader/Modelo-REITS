"""Prueba obligatoria 4 — Anclas de precio (P2).

Toda serie de precios se valida contra al menos tres cierres verificables. Si el
error supera 2%, la serie se rechaza; no se "usa con cuidado".

El objetivo específico es cachar series **ajustadas por dividendos** disfrazadas
de crudas. Ese error tiene firma: el precio queda por debajo del cierre real y la
brecha se ensancha hacia atrás en el tiempo, proporcional al dividendo acumulado.
Macrotrends daba 64.03 para el cierre de 2021 de Realty Income; el real fue 71.56.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.config import MIN_ANCLAS_PRECIO, TOLERANCIA_ANCLA_PRECIO
from src.ingesta.precios import (
    ANCLAS_VERIFICADAS,
    ErrorPrecios,
    dividendo_ttm,
    reconstruir_precio,
    validar_contra_anclas,
)
from src.validacion.anclas import auditar_serie, comparar_series, diagnosticar_ajuste_por_dividendos

ANCLAS = pd.DataFrame(list(ANCLAS_VERIFICADAS))


def _serie_desde_anclas(anclas: pd.DataFrame, factor_por_ancla=None) -> pd.Series:
    """Construye una serie diaria que pasa por las anclas, opcionalmente sesgada."""
    fechas = pd.bdate_range("2021-01-01", "2024-12-31")
    valores = pd.Series(np.nan, index=fechas)
    for _, a in anclas.iterrows():
        f = pd.Timestamp(a["fecha_dato"])
        if f not in valores.index:
            f = valores.index[valores.index <= f][-1]
        factor = 1.0 if factor_por_ancla is None else factor_por_ancla(a)
        valores.loc[f] = a["cierre_crudo"] * factor
    return valores.interpolate(method="index").bfill().ffill()


def test_serie_correcta_pasa():
    serie = _serie_desde_anclas(ANCLAS)
    resultado = validar_contra_anclas(serie, ANCLAS)
    assert resultado.aprobada, resultado.como_texto()
    assert resultado.n_anclas >= MIN_ANCLAS_PRECIO
    assert resultado.error_max <= TOLERANCIA_ANCLA_PRECIO


def test_serie_con_error_mayor_a_dos_por_ciento_se_rechaza():
    """Una desviación de 3% en una sola ancla basta para rechazar la serie."""
    def sesgo(a):
        return 0.97 if pd.Timestamp(a["fecha_dato"]).year == 2021 else 1.0

    serie = _serie_desde_anclas(ANCLAS, sesgo)
    resultado = validar_contra_anclas(serie, ANCLAS)
    assert not resultado.aprobada
    assert resultado.error_max > TOLERANCIA_ANCLA_PRECIO
    assert "ajustada por dividendos" in resultado.motivo


def test_menos_de_tres_anclas_se_rechaza():
    """Dos anclas no bastan. La regla pide al menos tres verificables (P2)."""
    serie = _serie_desde_anclas(ANCLAS)
    resultado = validar_contra_anclas(serie, ANCLAS.head(2))
    assert not resultado.aprobada
    assert "al menos" in resultado.motivo


def test_firma_del_ajuste_por_dividendos_se_diagnostica():
    """Una serie ajustada por dividendos se hunde más entre más antigua sea la fecha.

    Se simula justo eso: el error crece hacia atrás, proporcional al dividendo
    acumulado desde la fecha hasta hoy.
    """
    hoy = pd.Timestamp("2024-12-31")

    def ajuste_acumulado(a):
        anios = (hoy - pd.Timestamp(a["fecha_dato"])).days / 365.25
        return (1.0 - 0.05) ** anios  # 5% de dividendo anual acumulado hacia atrás

    serie = _serie_desde_anclas(ANCLAS, ajuste_acumulado)
    reporte = auditar_serie(serie, ANCLAS)
    assert not reporte.aprobada
    assert reporte.diagnostico.parece_ajustada, reporte.diagnostico.explicacion
    assert reporte.diagnostico.sesgo_medio < 0
    assert "ajustado por dividendos" in reporte.diagnostico.explicacion


def test_ruido_de_captura_no_se_confunde_con_ajuste():
    """Control: un error aislado y sin estructura NO debe diagnosticarse como ajuste."""
    detalle = pd.DataFrame(
        [
            {"fecha_dato": dt.date(2021, 12, 31), "esperado": 71.56, "obtenido": 71.90,
             "error_relativo": 0.005},
            {"fecha_dato": dt.date(2022, 12, 30), "esperado": 63.43, "obtenido": 63.10,
             "error_relativo": 0.005},
            {"fecha_dato": dt.date(2023, 12, 29), "esperado": 57.42, "obtenido": 57.60,
             "error_relativo": 0.003},
        ]
    )
    diagnostico = diagnosticar_ajuste_por_dividendos(detalle)
    assert not diagnostico.parece_ajustada


def test_el_caso_documentado_de_macrotrends():
    """64.03 contra 71.56 en el cierre de 2021 es un error de 10.5%: rechazo."""
    ancla_o = ANCLAS[ANCLAS["fecha_dato"] == dt.date(2021, 12, 31)].iloc[0]
    error = abs(64.03 - ancla_o["cierre_crudo"]) / ancla_o["cierre_crudo"]
    assert error > TOLERANCIA_ANCLA_PRECIO
    assert error == pytest.approx(0.105, abs=0.01)


# --------------------------------------------------------------------------------------
# Reconstrucción del precio
# --------------------------------------------------------------------------------------


def test_reconstruccion_precio_desde_dividendo_y_yield():
    """``precio = dividendo TTM ÷ rendimiento TTM``, el método de respaldo validado."""
    assert reconstruir_precio(2.83, 0.03955) == pytest.approx(71.56, rel=0.005)
    assert reconstruir_precio(3.05, 0.05312) == pytest.approx(57.42, rel=0.005)


def test_reconstruccion_rechaza_insumos_invalidos():
    with pytest.raises(ErrorPrecios):
        reconstruir_precio(2.83, 0.0)
    with pytest.raises(ErrorPrecios):
        reconstruir_precio(0.0, 0.04)


def test_dividendo_ttm_toma_doce_meses_exactos():
    dividendos = pd.DataFrame(
        {
            "fecha_ex": pd.date_range("2023-01-15", periods=24, freq="ME"),
            "monto": [0.25] * 24,
        }
    )
    ttm = dividendo_ttm(dividendos, dt.date(2024, 6, 30))
    assert ttm == pytest.approx(0.25 * 12, abs=0.26)


def test_sesgo_del_yield_por_usar_precio_ajustado():
    """Cuantifica el error: con precio ajustado, el yield sale sistemáticamente alto."""
    fechas = pd.bdate_range("2021-01-01", "2021-12-31")
    cruda = pd.Series(71.56, index=fechas)
    ajustada = pd.Series(64.03, index=fechas)
    comparacion = comparar_series(cruda, ajustada)
    assert not comparacion.empty
    # El yield es inversamente proporcional al precio.
    assert comparacion["sesgo_yield"].iloc[0] == pytest.approx(71.56 / 64.03 - 1, rel=1e-6)
    assert comparacion["sesgo_yield"].iloc[0] > 0.11, (
        "Usar precio ajustado infla el yield más de 11 puntos porcentuales relativos."
    )


def test_la_semilla_pasa_por_sus_anclas(repo_sembrado):
    """La serie de demostración de O respeta los cierres verificados."""
    serie = repo_sembrado.serie_precio("O", asof=dt.date(2026, 6, 30))
    anclas = repo_sembrado.anclas("O")
    assert len(anclas) >= MIN_ANCLAS_PRECIO
    resultado = validar_contra_anclas(serie, anclas)
    assert resultado.aprobada, resultado.como_texto()
