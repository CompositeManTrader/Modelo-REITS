"""Prueba 19 — Una lectura equivocada no puede quedarse para siempre.

La base es *append-only* porque un dato de FUENTE reexpresado tiene que convivir
con lo que se sabía antes (P1). Una conciliación no es un dato de fuente: es la
LECTURA línea por línea que el parser hizo de un filing. Cuando la ficha del
emisor mejora, el parser lee mejor el mismo documento —y la base no se entera,
porque la llave única es (emisor, tipo, fecha, publicación, línea) y no incluye
ni el estado ni el cuadre: la lectura nueva entra con la misma llave y se
descarta por duplicada, en silencio.

Public Storage lo enseñó completo. Su tabla trae la depreciación en dos renglones
—la principal y la de entidades no consolidadas—, y el parser corregido las suma:
295.6 millones. La base seguía guardando 10.9, solo el segundo renglón, de una
lectura anterior a su ficha. La pantalla mostraba un tramo descuadrado por 279.6
millones que el filing no tiene, y ninguna reingesta lo corregía.

Estas pruebas cubren el borrado selectivo que destraba ese caso. Es una operación
destructiva sobre datos derivados, así que lo que se verifica es tanto lo que
borra como lo que NO toca.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest
from sqlalchemy import select

from scripts.reparar import olvidar_descuadres
from src.datos import esquema

PUBLICACION = dt.date(2026, 7, 29)
CORTE = dt.date(2026, 6, 30)


def _fila(ticker: str, orden: int, linea: str, valor: float, *, fecha=CORTE) -> dict:
    return {
        "ticker": ticker,
        "periodo_tipo": "Q",
        "fecha_dato": fecha,
        "fecha_publicacion": PUBLICACION,
        "orden": orden,
        "linea": linea,
        "etiqueta": linea.replace("_", " ").capitalize(),
        "valor": valor,
        "signo": 1,
        "fuente": "prueba",
    }


def _conciliacion_que_cuadra(ticker: str, *, fecha=CORTE) -> list[dict]:
    """Utilidad neta + depreciación = FFO, exacto."""
    return [
        _fila(ticker, 2, "utilidad_neta", 450_301_000.0, fecha=fecha),
        _fila(ticker, 3, "depreciacion_inmuebles", 292_634_000.0, fecha=fecha),
        _fila(ticker, 19, "ffo", 742_935_000.0, fecha=fecha),
    ]


def _conciliacion_que_no_cuadra(ticker: str, *, fecha=CORTE) -> list[dict]:
    """La misma, con la depreciación incompleta: es la lectura vieja de PSA."""
    return [
        _fila(ticker, 2, "utilidad_neta", 450_301_000.0, fecha=fecha),
        _fila(ticker, 3, "depreciacion_inmuebles", 10_900_000.0, fecha=fecha),
        _fila(ticker, 19, "ffo", 742_935_000.0, fecha=fecha),
    ]


def _lineas(repo) -> pd.DataFrame:
    with repo.motor.begin() as cx:
        return pd.read_sql(select(esquema.conciliacion), cx)


def test_en_seco_no_borra_nada(repo_vacio, capsys):
    """Sin ``--aplicar`` reporta y se detiene. Un script destructivo se prueba primero."""
    repo_vacio.guardar_conciliacion(_conciliacion_que_no_cuadra("PSA"))
    antes = len(_lineas(repo_vacio))

    assert olvidar_descuadres(repo_vacio, tickers=None, aplicar=False) == 0
    assert len(_lineas(repo_vacio)) == antes

    salida = capsys.readouterr().out
    assert "1 conciliación(es) que no cuadran" in salida
    assert "En seco" in salida


def test_borra_la_que_no_cuadra_y_deja_intacta_la_que_sí(repo_vacio):
    """El criterio es el cuadre, no el emisor ni la fecha."""
    repo_vacio.guardar_conciliacion(_conciliacion_que_no_cuadra("PSA"))
    repo_vacio.guardar_conciliacion(_conciliacion_que_cuadra("O"))

    assert olvidar_descuadres(repo_vacio, tickers=None, aplicar=True) == 0

    quedan = _lineas(repo_vacio)
    assert set(quedan["ticker"]) == {"O"}, "se borró una conciliación que sí cuadraba"
    assert len(quedan) == 3


def test_solo_toca_el_periodo_descuadrado_del_mismo_emisor(repo_vacio):
    """Un trimestre malo no se lleva por delante los buenos del mismo emisor."""
    repo_vacio.guardar_conciliacion(_conciliacion_que_cuadra("PSA", fecha=dt.date(2026, 3, 31)))
    repo_vacio.guardar_conciliacion(_conciliacion_que_no_cuadra("PSA", fecha=CORTE))

    olvidar_descuadres(repo_vacio, tickers=None, aplicar=True)

    quedan = _lineas(repo_vacio)
    assert len(quedan) == 3
    assert set(pd.to_datetime(quedan["fecha_dato"]).dt.date) == {dt.date(2026, 3, 31)}


def test_el_filtro_de_emisor_acota_el_borrado(repo_vacio):
    """Con ``--tickers`` no se toca a nadie más, aunque también esté descuadrado."""
    repo_vacio.guardar_conciliacion(_conciliacion_que_no_cuadra("PSA"))
    repo_vacio.guardar_conciliacion(_conciliacion_que_no_cuadra("EXR"))

    olvidar_descuadres(repo_vacio, tickers=["PSA"], aplicar=True)

    assert set(_lineas(repo_vacio)["ticker"]) == {"EXR"}


def test_es_idempotente_cuando_todo_cuadra(repo_vacio, capsys):
    """Corrido dos veces no borra de más: la segunda no encuentra nada que hacer."""
    repo_vacio.guardar_conciliacion(_conciliacion_que_cuadra("O"))

    olvidar_descuadres(repo_vacio, tickers=None, aplicar=True)
    assert len(_lineas(repo_vacio)) == 3
    assert "Todas las conciliaciones de la base cuadran" in capsys.readouterr().out


def test_deja_constancia_en_la_bitacora(repo_vacio):
    """Borrar sin dejar rastro sería peor que no borrar."""
    repo_vacio.guardar_conciliacion(_conciliacion_que_no_cuadra("PSA"))
    olvidar_descuadres(repo_vacio, tickers=None, aplicar=True)

    with repo_vacio.motor.begin() as cx:
        bitacora = pd.read_sql(select(esquema.bitacora), cx)
    assert not bitacora.empty
    ultimo = bitacora.iloc[-1]
    assert ultimo["evento"] == "reparacion"
    assert "no" in str(ultimo["detalle"]).lower() and "cuadr" in str(ultimo["detalle"]).lower()


def test_la_reingesta_puede_volver_a_escribir_lo_borrado(repo_vacio):
    """El borrado destraba la llave: es el punto de toda la operación.

    Antes de borrar, guardar la lectura corregida con la MISMA llave no hace nada
    —se descarta por duplicada— y la base conserva la cifra vieja. Después de
    borrar, la corregida entra.
    """
    repo_vacio.guardar_conciliacion(_conciliacion_que_no_cuadra("PSA"))
    repo_vacio.guardar_conciliacion(_conciliacion_que_cuadra("PSA"))

    def depreciacion() -> float:
        filas = _lineas(repo_vacio)
        return float(filas[filas["linea"] == "depreciacion_inmuebles"]["valor"].iloc[0])

    assert depreciacion() == pytest.approx(10_900_000.0), (
        "la llave única no incluye el cuadre: la lectura corregida se descarta en silencio"
    )

    olvidar_descuadres(repo_vacio, tickers=None, aplicar=True)
    repo_vacio.guardar_conciliacion(_conciliacion_que_cuadra("PSA"))
    assert depreciacion() == pytest.approx(292_634_000.0)
