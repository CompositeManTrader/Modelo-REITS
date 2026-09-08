"""Prueba 29 — Mis propiedades contra UNA emisora, neto contra neto.

La pantalla comparaba un departamento hipotético —precio y renta en dos
deslizadores— contra un rival que no existía: un número tecleado a mano,
"yield neto de impuestos del portafolio de REITs, 4.2%".

El defecto grave no era la falta de dinamismo sino lo que ese valor por omisión
escondía. El 4.2% ya venía **neto** de impuestos, y el rendimiento del inmueble
al que se enfrentaba se miraba **bruto**. Comparar el bruto de un lado contra el
neto del otro es el error que hace ganar al ladrillo en casi todos los análisis
que circulan, y aquí estaba metido en el valor por omisión de un control.

Estas pruebas fijan que los dos lados lleguen al mismo punto —pesos en el
bolsillo, después de impuestos, sobre el valor de mercado de hoy— y que los dos
parámetros que de verdad mueven el resultado no se puedan ignorar en silencio.

* **29.1** Los dos lados pagan impuestos, y cada uno el suyo.
* **29.2** El sueldo mueve el lado del ladrillo; el W-8BEN mueve el del REIT.
* **29.3** El denominador es el valor de HOY, no el precio de compra.
* **29.4** Sin propiedades no hay veredicto inventado.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.simulacion.inmueble_cdmx import duelo_portafolio_contra_emisora  # noqa: E402


def _inmuebles(**cambios) -> pd.DataFrame:
    base = {
        "nombre": "Condesa", "tipo": "departamento", "fecha_compra": dt.date(2018, 1, 1),
        "precio_compra": 3_000_000.0, "valor_actual": 4_000_000.0,
        "renta_mensual": 20_000.0, "mantenimiento_mensual": 2_000.0,
        "predial_anual": 8_000.0, "seguro_anual": 0.0, "saldo_hipoteca": 0.0,
    }
    return pd.DataFrame([{**base, **cambios}])


# --------------------------------------------------------------------------------------
# 29.1 · Neto contra neto
# --------------------------------------------------------------------------------------


def test_los_dos_lados_llegan_netos_de_impuestos():
    """Ninguno de los dos rendimientos que se comparan puede ser el bruto."""
    duelo = duelo_portafolio_contra_emisora(
        _inmuebles(), ticker="O", yield_bruto_emisora=0.055
    )
    assert duelo.inmuebles.yield_neto < duelo.inmuebles.yield_bruto, (
        "el lado del ladrillo se está comparando bruto"
    )
    assert duelo.emisora.yield_neto < duelo.emisora.yield_bruto, (
        "el lado del REIT se está comparando bruto"
    )
    # Y la brecha se mide entre los DOS netos, no entre un bruto y un neto.
    assert duelo.brecha_bps == pytest.approx(
        (duelo.inmuebles.yield_neto - duelo.emisora.yield_neto) * 10_000
    )


def test_la_cascada_del_ladrillo_cuadra_con_su_yield():
    """La tabla que se muestra tiene que ser la misma aritmética del veredicto."""
    duelo = duelo_portafolio_contra_emisora(
        _inmuebles(), ticker="O", yield_bruto_emisora=0.055
    )
    inm = duelo.inmuebles
    assert inm.flujo_neto_anual == pytest.approx(
        inm.renta_bruta_anual - inm.gastos_anuales - inm.isr_anual
    )
    assert inm.yield_neto == pytest.approx(inm.flujo_neto_anual / inm.valor_mercado)

    tabla = inm.como_tabla()
    al_bolsillo = float(tabla.loc[tabla["concepto"] == "Al bolsillo", "monto"].iloc[0])
    assert al_bolsillo == pytest.approx(inm.flujo_neto_anual)


def test_la_cascada_del_reit_cuadra_con_su_yield():
    duelo = duelo_portafolio_contra_emisora(
        _inmuebles(), ticker="O", yield_bruto_emisora=0.055
    )
    e = duelo.emisora
    assert e.yield_neto == pytest.approx(e.yield_bruto - e.retencion_eeuu - e.isr_mexico)


# --------------------------------------------------------------------------------------
# 29.2 · Los dos parámetros que mueven el resultado
# --------------------------------------------------------------------------------------


def test_el_sueldo_encarece_el_lado_del_ladrillo():
    """La renta como único ingreso paga ~5%; apilada sobre un sueldo, marginal de 30–35%.

    Es el parámetro que más mueve el lado del inmueble, y en la pantalla anterior
    estaba en la barra lateral con valor cero por omisión: quien no lo tocara
    comparaba su renta a tasa de soltero contra un REIT ya gravado.
    """
    sin_sueldo = duelo_portafolio_contra_emisora(
        _inmuebles(), ticker="O", yield_bruto_emisora=0.055, ingreso_por_sueldo=0.0
    )
    con_sueldo = duelo_portafolio_contra_emisora(
        _inmuebles(), ticker="O", yield_bruto_emisora=0.055, ingreso_por_sueldo=1_200_000.0
    )
    assert con_sueldo.inmuebles.tasa_efectiva_isr > sin_sueldo.inmuebles.tasa_efectiva_isr
    assert con_sueldo.inmuebles.yield_neto < sin_sueldo.inmuebles.yield_neto
    # El lado del REIT no se mueve: el ISR sobre dividendo extranjero es tasa fija.
    assert con_sueldo.emisora.yield_neto == pytest.approx(sin_sueldo.emisora.yield_neto)


def test_sin_w8ben_el_reit_rinde_menos():
    """Sin el formato, la retención de EE. UU. sube de 10% a 30%."""
    con = duelo_portafolio_contra_emisora(
        _inmuebles(), ticker="O", yield_bruto_emisora=0.055, tiene_w8ben=True
    )
    sin = duelo_portafolio_contra_emisora(
        _inmuebles(), ticker="O", yield_bruto_emisora=0.055, tiene_w8ben=False
    )
    assert sin.emisora.retencion_eeuu > con.emisora.retencion_eeuu
    assert sin.emisora.yield_neto < con.emisora.yield_neto
    # Y el lado del ladrillo no se entera.
    assert sin.inmuebles.yield_neto == pytest.approx(con.inmuebles.yield_neto)


def test_el_ganador_se_declara_por_la_brecha_y_no_al_reves():
    """Control de coherencia: el rótulo y el número no pueden contradecirse."""
    for bruto in (0.02, 0.055, 0.12):
        duelo = duelo_portafolio_contra_emisora(
            _inmuebles(), ticker="NNN", yield_bruto_emisora=bruto
        )
        if duelo.brecha_bps > 0:
            assert duelo.ganador == "Tus inmuebles"
        else:
            assert duelo.ganador == "NNN"


# --------------------------------------------------------------------------------------
# 29.3 · El denominador es el valor de hoy
# --------------------------------------------------------------------------------------


def test_el_rendimiento_se_mide_sobre_el_valor_de_hoy():
    """La pregunta es hacia adelante: "¿dejo el dinero aquí o lo muevo?".

    El precio que se pagó hace ocho años ya no es una opción disponible, así que
    medir el flujo contra él infla el rendimiento de cualquier propiedad que se
    haya apreciado y hace que el ladrillo gane por construcción.
    """
    caro = duelo_portafolio_contra_emisora(
        _inmuebles(valor_actual=8_000_000.0), ticker="O", yield_bruto_emisora=0.055
    )
    barato = duelo_portafolio_contra_emisora(
        _inmuebles(valor_actual=4_000_000.0), ticker="O", yield_bruto_emisora=0.055
    )
    assert caro.inmuebles.yield_neto < barato.inmuebles.yield_neto
    assert caro.inmuebles.valor_mercado == 8_000_000.0


def test_sin_valor_de_hoy_se_usa_el_precio_pagado():
    """Es la mejor aproximación disponible, y no puede tronar."""
    sin_valor = _inmuebles()
    sin_valor["valor_actual"] = None
    duelo = duelo_portafolio_contra_emisora(
        sin_valor, ticker="O", yield_bruto_emisora=0.055
    )
    assert duelo.inmuebles.valor_mercado == 3_000_000.0


def test_el_portafolio_agrega_todas_las_propiedades():
    una = duelo_portafolio_contra_emisora(
        _inmuebles(), ticker="O", yield_bruto_emisora=0.055
    )
    dos = pd.concat([_inmuebles(), _inmuebles(nombre="Del Valle")], ignore_index=True)
    juntas = duelo_portafolio_contra_emisora(dos, ticker="O", yield_bruto_emisora=0.055)

    assert juntas.inmuebles.n_propiedades == 2
    assert juntas.inmuebles.valor_mercado == pytest.approx(2 * una.inmuebles.valor_mercado)
    # El ISR NO es lineal: dos propiedades apilan base gravable y pagan proporcionalmente
    # más que una sola. Sumar los ISR individuales habría subestimado el impuesto.
    assert juntas.inmuebles.isr_anual > 2 * una.inmuebles.isr_anual


# --------------------------------------------------------------------------------------
# 29.4 · Sin datos no hay veredicto
# --------------------------------------------------------------------------------------


def test_sin_propiedades_no_se_inventa_un_ganador():
    duelo = duelo_portafolio_contra_emisora(
        pd.DataFrame(), ticker="O", yield_bruto_emisora=0.055
    )
    assert not duelo.hay_inmuebles
    assert duelo.ganador == "—"
    assert duelo.plusvalia_necesaria is None
    # El lado del REIT sí se puede calcular sin propiedades, y sirve de referencia.
    assert duelo.emisora.yield_neto > 0


def test_la_plusvalia_necesaria_cierra_la_brecha_de_flujo():
    """Si el REIT gana en flujo, el ladrillo necesita MÁS plusvalía que la esperada."""
    duelo = duelo_portafolio_contra_emisora(
        _inmuebles(), ticker="O", yield_bruto_emisora=0.12, plusvalia_esperada=0.04
    )
    assert duelo.ganador == "O", "el armado de la prueba no produjo un REIT ganador"
    assert duelo.plusvalia_necesaria > 0.04, (
        "pide la misma plusvalía que ya se esperaba: no cierra ninguna brecha"
    )
    assert duelo.plusvalia_necesaria == pytest.approx(
        duelo.emisora.yield_neto - duelo.inmuebles.yield_neto + 0.04
    )
