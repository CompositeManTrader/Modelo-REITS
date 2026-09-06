"""Prueba 15 — No se valúa igual a todas las REITs, y el modelo lo dice con números.

El error más caro que se puede cometer en un NAV de REITs no se ve: es aplicar un
solo cap rate a todo el universo. El cap rate es la tasa a la que el mercado
privado capitaliza una renta, y depende de qué tan estable y duradera es esa
renta. Un net lease a veinte años con inquilino con grado de inversión se
capitaliza cerca del 6.75%; un self storage, que se renta mes a mes pero casi no
consume CapEx, cerca del 5.50%; una oficina, arriba del 8.75%.

Valuar el self storage al cap rate del net lease le quita una quinta parte del
valor **sin que ningún número del modelo se vea raro**: la aritmética sigue
cuadrando, solo el supuesto está mal. Un error así no lo atrapa una revisión de
código ni una prueba de cuadre; lo atrapa esta prueba, que exige que la
diferencia entre sectores exista y sea material.

El segundo bloque cubre la valuación por crecimiento implícito, que existe por una
razón concreta: el NAV pide NOI, el NOI es una medida no-GAAP que no está en XBRL,
y hoy la base no lo tiene para ningún emisor. Un `None` en pantalla no distingue
"no vale nada" de "me falta un dato para opinar". El diagnóstico sí.
"""

from __future__ import annotations

import pytest

from src.config import (
    CAP_RATE_POR_OMISION,
    CAP_RATE_POR_SECTOR,
    PRIMA_RIESGO_POR_OMISION,
    PRIMA_RIESGO_POR_SECTOR,
)
from src.modelo.valuacion import (
    InsumosValuacion,
    calcular_nav,
    crecimiento_implicito,
    diagnosticar,
    prima_riesgo_sector,
    rango_cap_rate,
    sensibilidad_nav_sectorial,
    tasa_de_descuento,
    valor_gordon,
    valuar_por_crecimiento,
)


def _insumos(sector: str) -> InsumosValuacion:
    """El MISMO portafolio, cambiando únicamente la etiqueta de sector.

    Todo lo demás es idéntico a propósito: si el NAV cambia, cambió por el
    sector y por nada más.
    """
    return InsumosValuacion(
        ticker="PRUEBA",
        precio=60.0,
        acciones_diluidas=100_000_000.0,
        noi_anualizado=400_000_000.0,
        affo_por_accion_ttm=4.20,
        dividendo_ttm_por_accion=3.20,
        deuda_total=2_000_000_000.0,
        efectivo=100_000_000.0,
        sector=sector,
    )


# --------------------------------------------------------------------------------------
# 15.1 El cap rate es del sector, no del universo
# --------------------------------------------------------------------------------------


def test_cada_sector_tiene_su_propio_rango():
    """Net lease, self storage y oficinas no pueden compartir cap rate."""
    net_lease = rango_cap_rate("Net Lease")
    storage = rango_cap_rate("Self Storage")
    oficinas = rango_cap_rate("Oficinas")

    # El orden económico: storage se capitaliza más barato que net lease, y las
    # oficinas exigen la prima más alta de los tres.
    assert storage[1] < net_lease[1] < oficinas[1]
    # Y la diferencia es material, no decorativa.
    assert net_lease[1] - storage[1] >= 0.0100


def test_el_sector_desconocido_cae_al_rango_por_omision():
    """Un sector nuevo no debe tronar ni heredar en silencio el de net lease."""
    assert rango_cap_rate("Criptogranjas") == CAP_RATE_POR_OMISION
    assert rango_cap_rate(None) == CAP_RATE_POR_OMISION
    assert prima_riesgo_sector("Criptogranjas") == PRIMA_RIESGO_POR_OMISION


def test_todo_rango_esta_ordenado_y_es_plausible():
    """Un rango invertido produce una tabla de sensibilidad al revés, sin avisar."""
    for sector, (minimo, base, maximo) in CAP_RATE_POR_SECTOR.items():
        assert minimo < base < maximo, f"{sector} tiene el rango desordenado"
        assert 0.02 < minimo and maximo < 0.20, f"{sector} tiene un cap rate implausible"
    for sector, prima in PRIMA_RIESGO_POR_SECTOR.items():
        assert 0.0 < prima < 0.15, f"{sector} tiene una prima de riesgo implausible"


def test_todo_sector_del_universo_tiene_cap_rate_y_prima():
    """Si un emisor del universo cae al valor por omisión, es un olvido, no una decisión."""
    from src.config import UNIVERSO_INICIAL

    for emisor in UNIVERSO_INICIAL:
        assert emisor.sector in CAP_RATE_POR_SECTOR, f"falta cap rate de {emisor.sector}"
        assert emisor.sector in PRIMA_RIESGO_POR_SECTOR, f"falta prima de {emisor.sector}"


# --------------------------------------------------------------------------------------
# 15.2 El control: el sector mueve el NAV de verdad
# --------------------------------------------------------------------------------------


def test_valuar_un_storage_como_net_lease_le_borra_una_quinta_parte_del_valor():
    """La prueba que da sentido a todo lo anterior.

    Mismo NOI, misma deuda, mismas acciones. Solo cambia el cap rate al que se
    capitaliza la renta. Si la diferencia fuera pequeña, el cap rate por sector
    sería adorno; es enorme, y ese es exactamente el punto.
    """
    ins = _insumos("Self Storage")

    correcto = calcular_nav(ins, rango_cap_rate("Self Storage")[1])
    equivocado = calcular_nav(ins, rango_cap_rate("Net Lease")[1])
    assert correcto is not None and equivocado is not None

    perdida = 1.0 - equivocado.nav_por_accion / correcto.nav_por_accion
    assert perdida > 0.20, (
        f"usar el cap rate de net lease en un storage solo movió el NAV {perdida:.1%}; "
        "el modelo estaría tratando el cap rate como si fuera casi indiferente"
    )


def test_el_mismo_portafolio_en_oficinas_vale_mucho_menos_que_en_net_lease():
    net_lease = calcular_nav(_insumos("Net Lease"), rango_cap_rate("Net Lease")[1])
    oficinas = calcular_nav(_insumos("Oficinas"), rango_cap_rate("Oficinas")[1])
    assert net_lease is not None and oficinas is not None
    assert oficinas.nav_por_accion < net_lease.nav_por_accion


def test_la_sensibilidad_se_centra_en_el_rango_del_sector():
    """Una tabla de 5.5% a 8.0% es informativa para net lease y casi inútil para torres."""
    storage = sensibilidad_nav_sectorial(_insumos("Self Storage"), "Self Storage")
    oficinas = sensibilidad_nav_sectorial(_insumos("Oficinas"), "Oficinas")

    assert not storage.empty and not oficinas.empty
    # Los dos rangos ni siquiera se tocan: es la definición de "no es la misma tabla".
    assert storage["cap_rate"].max() < oficinas["cap_rate"].min()
    # Y el rango dibujado es el del sector, no uno fijo.
    minimo, _base, maximo = rango_cap_rate("Self Storage")
    assert storage["cap_rate"].min() == pytest.approx(minimo)
    assert storage["cap_rate"].max() == pytest.approx(maximo)


def test_el_nav_baja_cuando_sube_el_cap_rate():
    """Control de signo. Un NAV que sube con el cap rate está mal armado."""
    tabla = sensibilidad_nav_sectorial(_insumos("Net Lease"), "Net Lease")
    navs = tabla["nav_por_accion"].tolist()
    assert navs == sorted(navs, reverse=True)


# --------------------------------------------------------------------------------------
# 15.3 Crecimiento implícito: la valuación que sí corre con lo que hay
# --------------------------------------------------------------------------------------


def test_la_tasa_de_descuento_es_libre_de_riesgo_mas_la_prima_del_sector():
    assert tasa_de_descuento(0.0416, "Net Lease") == pytest.approx(0.0416 + 0.030)
    assert tasa_de_descuento(0.0416, "Oficinas") == pytest.approx(0.0416 + 0.060)
    # Una oficina se descuenta más caro que un net lease: menos valor por el mismo AFFO.
    assert tasa_de_descuento(0.0416, "Oficinas") > tasa_de_descuento(0.0416, "Net Lease")


def test_el_crecimiento_implicito_es_el_inverso_exacto_de_gordon():
    """El contrato del despeje: valuar con el `g` implícito devuelve el precio.

    Si esta identidad no se cumple, el número que se le enseña al usuario como
    "el crecimiento que descuenta el precio" no descuenta ese precio.
    """
    precio, affo, r = 60.25, 4.19, 0.0716
    g = crecimiento_implicito(precio, affo, r)
    assert g is not None
    assert valor_gordon(affo, g, r) == pytest.approx(precio)


def test_un_precio_mas_alto_exige_mas_crecimiento():
    """Control de signo. Pagar más por el mismo flujo es apostar a más crecimiento."""
    r = 0.0716
    barato = crecimiento_implicito(40.0, 4.19, r)
    caro = crecimiento_implicito(80.0, 4.19, r)
    assert barato is not None and caro is not None
    assert caro > barato


def test_gordon_se_niega_a_dar_numero_cuando_el_crecimiento_alcanza_a_la_tasa():
    """Con `r − g` cerca de cero el múltiplo pasa de 100x: eso es aritmética, no valuación."""
    assert valor_gordon(4.19, 0.0716, 0.0716) is None  # r == g: división por cero
    assert valor_gordon(4.19, 0.080, 0.0716) is None  # g > r: valor negativo, absurdo
    assert valor_gordon(4.19, 0.0680, 0.0716) is None  # 36 bps de margen: aún no es valuación
    assert valor_gordon(4.19, 0.0200, 0.0716) is not None


def test_sin_affo_no_hay_valuacion_por_crecimiento():
    """Es la razón por la que ADC, EXR y PSA salen en blanco: les falta el TTM completo."""
    assert valuar_por_crecimiento(60.0, None, 0.0416, "Net Lease") is None
    assert valuar_por_crecimiento(60.0, 0.0, 0.0416, "Net Lease") is None
    assert valuar_por_crecimiento(0.0, 4.19, 0.0416, "Net Lease") is None
    assert crecimiento_implicito(60.0, -1.0, 0.0716) is None


def test_la_brecha_compara_lo_que_el_precio_pide_contra_lo_que_el_emisor_entrego():
    """La lectura útil: no "cuánto vale", sino "cuánto tiene que crecer para valer esto"."""
    v = valuar_por_crecimiento(60.25, 4.19, 0.0416, "Net Lease", crecimiento_historico=0.0403)
    assert v is not None
    assert v.tasa_descuento == pytest.approx(0.0416 + 0.030)
    assert v.brecha == pytest.approx(v.crecimiento_implicito - 0.0403)
    # El precio pide MENOS de lo entregado, así que el texto tiene que decir eso.
    assert v.brecha < 0
    assert "MENOS" in v.como_texto()

    exigente = valuar_por_crecimiento(60.25, 4.19, 0.0416, "Net Lease", crecimiento_historico=-0.02)
    assert exigente is not None and exigente.brecha > 0
    assert "MÁS" in exigente.como_texto()


def test_sin_historia_el_texto_lo_dice_en_vez_de_inventar_una_brecha():
    v = valuar_por_crecimiento(60.25, 4.19, 0.0416, "Net Lease")
    assert v is not None
    assert v.brecha is None
    assert "No hay historia suficiente" in v.como_texto()


def test_el_sector_cambia_el_crecimiento_implicito_del_mismo_precio():
    """Mismo precio y mismo AFFO en dos sectores no descuentan el mismo crecimiento.

    La oficina se descuenta más caro, así que para justificar el mismo precio el
    mercado tiene que estar suponiendo más crecimiento.
    """
    net_lease = valuar_por_crecimiento(60.25, 4.19, 0.0416, "Net Lease")
    oficinas = valuar_por_crecimiento(60.25, 4.19, 0.0416, "Oficinas")
    assert net_lease is not None and oficinas is not None
    assert oficinas.crecimiento_implicito > net_lease.crecimiento_implicito


# --------------------------------------------------------------------------------------
# 15.4 El diagnóstico: qué se puede valuar y qué le falta al que no
# --------------------------------------------------------------------------------------


def test_el_diagnostico_nombra_el_insumo_que_falta_en_vez_de_devolver_none():
    """Un `None` no distingue "no vale nada" de "me falta un dato". Esto sí."""
    ins = InsumosValuacion(
        ticker="O", precio=60.25, acciones_diluidas=900_000_000.0, affo_por_accion_ttm=4.19
    )
    metodos = {m.nombre: m for m in diagnosticar(ins, tasa_libre_riesgo=0.0416)}

    multiplos = metodos["Múltiplos (AFFO yield, P/AFFO)"]
    assert multiplos.disponible and multiplos.faltantes == ()

    crecimiento = metodos["Crecimiento implícito en el precio"]
    assert crecimiento.disponible

    nav = metodos["NAV (NOI ÷ cap rate del sector)"]
    assert not nav.disponible
    assert any("NOI" in f for f in nav.faltantes)
    assert any("deuda_total" in f for f in nav.faltantes)


def test_el_diagnostico_reconoce_al_emisor_completo():
    ins = _insumos("Net Lease")
    metodos = diagnosticar(ins, tasa_libre_riesgo=0.0416)
    assert all(m.disponible for m in metodos), [m.faltantes for m in metodos if not m.disponible]


def test_sin_tasa_libre_de_riesgo_solo_se_cae_el_metodo_que_la_necesita():
    """El múltiplo no depende de la macro; el descuento sí. No se caen juntos."""
    ins = _insumos("Net Lease")
    metodos = {m.nombre: m for m in diagnosticar(ins, tasa_libre_riesgo=None)}
    assert metodos["Múltiplos (AFFO yield, P/AFFO)"].disponible
    assert not metodos["Crecimiento implícito en el precio"].disponible
    assert metodos["NAV (NOI ÷ cap rate del sector)"].disponible
