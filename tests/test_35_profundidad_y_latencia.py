"""Prueba 35 — Tres límites que dejaban a la Puerta 2 sin veredicto.

Al rastrear de dónde sale cada insumo de la pantalla de valuación aparecieron
tres topes que no eran decisiones, sino valores por omisión que nadie había
vuelto a mirar. Los tres son de una línea y entre los tres la Puerta 2 pasó de
emitir veredicto en TRES emisoras a hacerlo en SIETE.

* **El precio se pedía a cinco años.** La prima se percentila contra la historia
  del propio emisor, y esa historia no puede empezar antes que el precio. El
  proveedor entrega diez años por el mismo precio (35.1).
* **Se parseaban ocho comunicados de resultados.** Cuatro emisoras se quedaban en
  catorce trimestres de flujo, a UNO del mínimo que exige el percentil (35.2).
* **La latencia se medía en días naturales.** El 8 de septiembre de 2026 —martes,
  con el lunes feriado— la pantalla decía "latencia 4 días" sobre el precio más
  reciente que existía. Un aviso que se dispara solo entrena a ignorarlo (35.3).
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
if str(RAIZ / "app") not in sys.path:
    sys.path.insert(0, str(RAIZ / "app"))

from src.config import UMBRALES, UNIVERSO_INICIAL  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta.orquestador import MAX_COMUNICADOS, MAX_EXAMINADOS, ingestar_precios  # noqa: E402
from src.ingesta.precios import RANGO_HISTORICO, descargar_historico  # noqa: E402
from src.servicio import MAX_LATENCIA_PRECIO, _dias_habiles, construir_panel  # noqa: E402

# --------------------------------------------------------------------------------------
# 35.1 · El precio, a diez años
# --------------------------------------------------------------------------------------


def test_el_rango_de_precio_es_de_diez_anios():
    assert RANGO_HISTORICO == "10Y"


def test_el_rango_max_del_proveedor_no_se_usa():
    """La trampa que hay que dejar escrita.

    "MAX" suena a "todo lo que haya" y devuelve MENOS que "10Y": al 8 de
    septiembre de 2026 daba 253 observaciones —un año— contra 2,513. Quien
    "mejore" esto poniendo MAX recorta la historia a la quinta parte y nada avisa,
    porque una serie corta no se ve rota: solo produce menos observaciones.
    """
    assert RANGO_HISTORICO != "MAX"


def test_el_orquestador_no_impone_su_propio_rango():
    """El bypass que casi deja el arreglo sin efecto.

    `ingestar_precios` traía su propio `rango="5Y"` como valor por omisión, así
    que cambiar el de `descargar_historico` no habría servido de nada: el que
    manda es el de quien llama.
    """
    import inspect
    assert inspect.signature(ingestar_precios).parameters["rango"].default == RANGO_HISTORICO
    assert inspect.signature(descargar_historico).parameters["rango"].default == RANGO_HISTORICO


def test_la_serie_de_precio_ya_cubre_mas_de_cinco_anios():
    repo = Repositorio()
    serie = repo.serie_precio("O", asof=dt.date.today())
    if serie.empty:
        pytest.skip("No hay base cargada.")
    anios = (serie.index.max() - serie.index.min()).days / 365.25
    assert anios > 6, f"la serie solo cubre {anios:.1f} años"


# --------------------------------------------------------------------------------------
# 35.2 · Los comunicados de resultados, y el presupuesto de peticiones
# --------------------------------------------------------------------------------------


def test_se_parsean_suficientes_comunicados_para_el_percentil():
    """Doce observaciones de prima exigen quince trimestres contiguos de flujo.

    El TTM se come tres —necesita cuatro trimestres seguidos— así que el mínimo
    de la Puerta 2 no se alcanza con menos. Con ocho comunicados, cuatro emisoras
    se quedaban en catorce.
    """
    assert MAX_COMUNICADOS >= UMBRALES.valuacion.min_observaciones + 3


def test_hay_un_presupuesto_de_peticiones_ademas_del_limite_de_comunicados():
    """Los dos topes son distintos y hacen falta los dos.

    Averiguar si un 8-K trae resultados cuesta una petición: hay que pedir su
    índice. Realty Income presenta 226 formularios 8-K y solo seis de sus cuarenta
    más recientes son comunicados —el resto son declaraciones de dividendo
    mensual—, así que sin este tope buscar veinte comunicados costaría más de cien
    peticiones en la emisora que menos las necesita.
    """
    assert MAX_EXAMINADOS > MAX_COMUNICADOS
    assert MAX_EXAMINADOS <= 100, "un presupuesto que no acota no es un presupuesto"


def test_la_puerta_dos_ya_emite_veredicto_en_la_mayoria():
    """El resultado medible de 35.1 y 35.2 juntos: de TRES a SIETE.

    Un modelo cuya puerta central decía SIN DATOS en siete de diez no estaba
    midiendo, estaba callando. Quedan tres fuera y por causas distintas: Essential
    Properties y Global Net Lease no publican más historia de AFFO, y Prologis
    tiene el flujo pero no el conteo de acciones del último trimestre —su
    `acciones_diluidas` se detiene en marzo porque `companyfacts` va atrasado—.
    """
    repo = Repositorio()
    hoy = dt.date.today()
    con_veredicto = 0
    for e in UNIVERSO_INICIAL:
        panel = construir_panel(repo, e.ticker, asof=hoy)
        if panel.trimestral.empty:
            pytest.skip("No hay base cargada.")
        if panel.n_observaciones >= UMBRALES.valuacion.min_observaciones:
            con_veredicto += 1
    assert con_veredicto >= 7, f"solo {con_veredicto} de 10 tienen historia suficiente"


# --------------------------------------------------------------------------------------
# 35.3 · La latencia se mide en días de mercado, no de calendario
# --------------------------------------------------------------------------------------


def test_un_lunes_no_es_un_rezago():
    """El caso que disparaba el aviso todas las semanas.

    El viernes es el último cierre y el lunes son tres días de calendario. Cero de
    negociación.
    """
    assert _dias_habiles(dt.date(2026, 9, 4), dt.date(2026, 9, 7)) == 1


def test_un_feriado_de_mercado_tampoco():
    """El caso real: martes 8 de septiembre de 2026, con el lunes 7 feriado.

    Cuatro días de calendario, dos hábiles. El precio del viernes era el más
    reciente que existía y la pantalla lo marcaba como rezagado.
    """
    habiles = _dias_habiles(dt.date(2026, 9, 4), dt.date(2026, 9, 8))
    assert habiles == 2
    assert habiles <= MAX_LATENCIA_PRECIO, "sigue avisando sobre el último cierre"


def test_un_rezago_de_verdad_si_se_marca():
    """El control. Una guarda que nunca dispara no es una guarda."""
    assert _dias_habiles(dt.date(2026, 9, 4), dt.date(2026, 9, 18)) > MAX_LATENCIA_PRECIO


def test_el_dia_inicial_no_cuenta():
    """La fecha del cierre no es latencia: es el dato."""
    assert _dias_habiles(dt.date(2026, 9, 4), dt.date(2026, 9, 4)) == 0
    assert _dias_habiles(dt.date(2026, 9, 8), dt.date(2026, 9, 4)) == 0


def test_la_interfaz_usa_la_misma_regla_que_el_servicio():
    """Dos definiciones de "latencia" en la misma pantalla es peor que una mala."""
    from comun import TOLERANCIA_LATENCIA
    from comun import dias_habiles as dias_habiles_ui

    for a, b in ((dt.date(2026, 9, 4), dt.date(2026, 9, 8)),
                 (dt.date(2026, 9, 4), dt.date(2026, 9, 18)),
                 (dt.date(2026, 1, 2), dt.date(2026, 1, 5))):
        assert dias_habiles_ui(a, b) == _dias_habiles(a, b)
    assert TOLERANCIA_LATENCIA <= MAX_LATENCIA_PRECIO


def test_ninguna_emisora_marca_latencia_sobre_el_ultimo_cierre():
    """Sobre datos reales: hoy el aviso no debe salir en ninguna."""
    repo = Repositorio()
    hoy = dt.date.today()
    con_aviso = []
    for e in UNIVERSO_INICIAL:
        panel = construir_panel(repo, e.ticker, asof=hoy)
        if panel.precio is None:
            pytest.skip("No hay base cargada.")
        if any("días hábiles antes del corte" in a for a in panel.avisos):
            con_aviso.append(e.ticker)
    assert con_aviso == [], f"marcan latencia sobre el último cierre: {con_aviso}"
