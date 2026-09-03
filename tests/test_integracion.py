"""Integración: del filing a la señal, y de la base a la interfaz.

Estas pruebas no verifican una función: verifican que las piezas encajan. Es lo
que un conjunto de pruebas unitarias verdes no garantiza.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.config import Estado, Fuente
from src.datos.repositorio import Repositorio
from src.ingesta.parser_affo import parsear_conciliacion
from src.servicio import construir_panel, contexto_macro, evaluar, tabla_universo
from src.validacion.cuadre import cuadrar_conciliacion, elegir_mejor_conciliacion


def test_del_filing_a_la_base_y_de_vuelta(repo_vacio, html_8k_realty, fecha_publicacion_8k):
    """Parsear un 8-K real, validarlo, guardarlo y volver a leerlo con corte."""
    from src.config import UNIVERSO_INICIAL

    repo_vacio.registrar_emisores([e for e in UNIVERSO_INICIAL if e.ticker == "O"])

    extracciones = elegir_mejor_conciliacion(
        parsear_conciliacion(html_8k_realty, "O", fecha_publicacion_8k, "https://sec.gov/fixture")
    )
    assert extracciones

    guardados = 0
    for e in extracciones:
        veredicto = cuadrar_conciliacion(e.lineas, e.orden)
        estado = Estado.VALIDO if veredicto.cuadra else Estado.SOSPECHOSO
        filas = [
            {
                "ticker": "O", "concepto": clave, "periodo_tipo": e.periodo.tipo,
                "fecha_dato": e.periodo.fin, "fecha_publicacion": e.fecha_publicacion,
                "valor": float(e.lineas[clave]), "unidad": "USD",
                "fuente": Fuente.SEC_8K, "es_primario": True, "estado": estado,
                "url_filing": e.url_filing,
            }
            for clave in ("affo", "affo_por_accion", "ffo_normalizado")
            if clave in e.lineas
        ]
        guardados += repo_vacio.guardar_hechos(filas)
        repo_vacio.guardar_conciliacion(e.filas_conciliacion())

    assert guardados > 0

    # El filing se presentó el 5 de agosto: un día antes nada de esto existía.
    vispera = repo_vacio.serie("O", "affo_por_accion", asof=dt.date(2026, 8, 4))
    assert vispera.empty, "El filing no puede verse antes de presentarse."

    despues = repo_vacio.serie("O", "affo_por_accion", asof=dt.date(2026, 8, 6))
    assert not despues.empty
    q2 = despues[despues.index == pd.Timestamp("2026-06-30")]
    assert float(q2.iloc[0]) == pytest.approx(1.09, abs=0.01)

    # La conciliación queda disponible línea por línea para la interfaz.
    detalle = repo_vacio.conciliacion("O", dt.date(2026, 6, 30), asof=dt.date(2026, 8, 6))
    assert not detalle.empty
    assert "affo" in set(detalle["linea"])
    assert detalle["url_filing"].iloc[0].startswith("https://sec.gov")


def test_el_panel_completo_se_arma_desde_la_base(repo_sembrado):
    """De la base a la señal: panel, prima, percentil y semáforo."""
    corte = dt.date(2026, 6, 30)
    panel = construir_panel(repo_sembrado, "O", asof=corte)

    assert not panel.trimestral.empty
    assert panel.precio is not None and panel.precio > 0
    assert panel.dividendo_ttm is not None and panel.dividendo_ttm > 0
    assert panel.tasa_libre_riesgo is not None
    assert panel.n_observaciones >= 12
    assert panel.percentil_actual is not None
    assert 0.0 <= panel.percentil_actual <= 1.0

    semaforo = evaluar(panel)
    assert semaforo.accion.value in {
        "COMPRAR", "MANTENER", "NO COMPRAR MÁS", "VENDER", "DESCARTADO", "INCONCLUSO"
    }
    assert semaforo.explicacion


def test_el_panel_avisa_que_los_datos_son_de_demostracion(repo_sembrado):
    """No se puede decidir con datos DEMO sin que la pantalla lo diga."""
    panel = construir_panel(repo_sembrado, "O", asof=dt.date(2026, 6, 30))
    assert panel.solo_demo
    assert any("DEMOSTRACIÓN" in a for a in panel.avisos)


def test_la_tabla_del_universo_no_ordena_por_yield(repo_sembrado):
    """El universo se presenta con percentil de prima, no con nivel de yield."""
    tabla = tabla_universo(repo_sembrado, asof=dt.date(2026, 6, 30))
    assert not tabla.empty
    assert "percentil_prima" in tabla.columns
    assert "pasa_calidad" in tabla.columns
    assert set(tabla["ticker"]) == {"O", "PLD", "GNL"}


def test_el_corte_historico_produce_una_señal_distinta(repo_sembrado):
    """Retroceder el corte cambia la señal, porque cambia lo que se sabía."""
    reciente = construir_panel(repo_sembrado, "O", asof=dt.date(2026, 6, 30))
    antiguo = construir_panel(repo_sembrado, "O", asof=dt.date(2022, 6, 30))

    assert antiguo.n_observaciones < reciente.n_observaciones
    assert len(antiguo.trimestral) < len(reciente.trimestral)
    if antiguo.precio and reciente.precio:
        assert antiguo.precio_fecha <= dt.date(2022, 6, 30)


def test_el_contexto_macro_se_lee_con_corte(repo_sembrado):
    macro = contexto_macro(repo_sembrado, asof=dt.date(2026, 6, 30))
    assert macro.ust10 is not None
    assert macro.udibono10 is not None
    assert macro.inflacion_mx is not None
    assert 0.0 < macro.inflacion_mx < 0.25


def test_el_emisor_que_recorto_dividendo_no_rompe_el_sistema(repo_sembrado: Repositorio):
    """GNL está en el universo a propósito: si solo funciona con sobrevivientes, no sirve."""
    panel = construir_panel(repo_sembrado, "GNL", asof=dt.date(2026, 6, 30))
    semaforo = evaluar(panel)
    assert semaforo.explicacion

    dividendos = repo_sembrado.dividendos("GNL", asof=dt.date(2026, 6, 30))
    anual = dividendos.set_index("fecha_ex")["monto"].resample("YE").sum()
    assert (anual.pct_change().dropna() < -0.10).any(), (
        "La serie de GNL tiene que incluir sus recortes de dividendo."
    )


def test_la_exportacion_a_excel_corre_desde_el_panel(repo_sembrado, tmp_path):
    """La cadena completa: base → panel → libro con fórmulas vivas."""
    from src.export.excel import DatosExportacion, exportar
    from src.modelo.valuacion import InsumosValuacion

    corte = dt.date(2026, 6, 30)
    panel = construir_panel(repo_sembrado, "O", asof=corte)
    ultima = panel.trimestral.dropna(subset=["affo_por_accion_ttm"]).tail(1)
    assert not ultima.empty
    fila = ultima.iloc[0]

    datos = DatosExportacion(
        ticker="O", nombre="Realty Income", sector=panel.sector, fecha_corte=corte,
        insumos=InsumosValuacion(
            ticker="O", precio=panel.precio,
            acciones_diluidas=float(fila.get("acciones_diluidas") or 1.0),
            noi_trimestral=float(fila.get("noi") or 0.0) or None,
            affo_por_accion_ttm=float(fila["affo_por_accion_ttm"]),
            dividendo_ttm_por_accion=panel.dividendo_ttm,
            sector=panel.sector,
        ),
        componentes_cascada={},
        fuentes=panel.fuentes.head(20).to_dict("records"),
    )
    ruta = exportar(datos, tmp_path / "O.xlsx")
    assert ruta.exists() and ruta.stat().st_size > 5_000


def test_la_ingesta_es_idempotente(repo_vacio, html_8k_realty, fecha_publicacion_8k):
    """Re-correr la ingesta no duplica filas ni ensucia la base."""
    extracciones = elegir_mejor_conciliacion(
        parsear_conciliacion(html_8k_realty, "O", fecha_publicacion_8k, "fixture")
    )
    filas = [
        {
            "ticker": "O", "concepto": "affo", "periodo_tipo": e.periodo.tipo,
            "fecha_dato": e.periodo.fin, "fecha_publicacion": e.fecha_publicacion,
            "valor": float(e.lineas["affo"]), "unidad": "USD",
            "fuente": Fuente.SEC_8K, "es_primario": True, "estado": Estado.VALIDO,
        }
        for e in extracciones if "affo" in e.lineas
    ]
    primera = repo_vacio.guardar_hechos(filas)
    segunda = repo_vacio.guardar_hechos(filas)

    assert primera > 0
    assert segunda == 0, "Re-correr la ingesta no debe insertar nada nuevo."

    total = repo_vacio.hechos(asof=dt.date(2026, 12, 31), tickers="O", conceptos="affo",
                              vigentes=False)
    assert len(total) == primera
