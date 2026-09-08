"""Prueba 30 — Las brechas de EXR y WELL, y el saldo viejo que destaparon.

EXR y WELL se quedaban con dos criterios medibles de cinco porque no tenían
gasto por intereses. Se habían probado tres reconstrucciones y las tres se
descartaron midiendo el error. Faltaba el camino que no era deducir sino ir por
el dato — y al abrirlo resultaron ser DOS causas distintas y una tercera peor,
que estaba escondida detrás.

* **WELL: una etiqueta no mapeada.** Cambió de ``InterestExpenseDebt`` a
  ``InterestExpenseBorrowings`` en el cuarto trimestre de 2024. Es taxonomía
  estándar, está en `companyfacts` y siempre estuvo en la instantánea
  versionada: solo no la leíamos (30.1).

* **EXR: una etiqueta de EXTENSIÓN.** Su gasto por intereses vive en
  ``exr:InterestExpenseExcludingAmortizationOfDebtDiscountPremium``, y
  `companyfacts` solo publica taxonomías estándar. El dato está impreso en su
  estado de resultados y en el documento XBRL del filing, pero no en la API que
  usábamos (30.2).

* **Y lo que apareció al arreglar los dos:** el apalancamiento de EXR salía en
  2.0x, de los más sanos del universo. Su ``deuda_total`` venía de
  ``NotesPayable``, cuya última observación es del 30 de septiembre de **2021**.
  Cinco años vieja, presentada como el saldo de hoy (30.3).
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

from src.config import Estado, Fuente  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta.estados import (  # noqa: E402
    LINEA_POR_CLAVE,
    etiquetas_de_instancia,
    tags_de,
)
from src.ingesta.instancia import hechos_de_instancia  # noqa: E402
from src.servicio import (  # noqa: E402
    TRAMOS_DE_DEUDA,
    VIGENCIA_DE_SALDO,
    _deuda_compuesta,
    _saldos_de_balance,
)

# --------------------------------------------------------------------------------------
# 30.1 · WELL: la etiqueta que cambió y nadie siguió
# --------------------------------------------------------------------------------------


def test_la_etiqueta_nueva_de_welltower_esta_mapeada():
    """`InterestExpenseDebt` se detiene el 30-sep-2024; `Borrowings` sigue hasta hoy.

    Las dos son us-gaap y las dos están en `companyfacts`. No faltaba una fuente:
    faltaba leer la segunda.
    """
    assert "InterestExpenseBorrowings" in tags_de("WELL", "gasto_intereses")


def test_welltower_tiene_intereses_recientes_en_la_instantanea():
    """Y sin descargar nada: el crudo versionado guarda TODAS las etiquetas.

    Es el rédito de guardar el crudo exhaustivo en vez de solo lo que se sabía
    mapear — ampliar el catálogo no cuesta una sola petición.
    """
    from src.datos.almacen import leer_crudos

    crudos = leer_crudos("WELL")
    if crudos.empty:
        pytest.skip("WELL no está en el almacén.")
    sub = crudos[crudos["tag"] == "InterestExpenseBorrowings"]
    assert not sub.empty, "la etiqueta no está en el crudo versionado"
    assert pd.Timestamp(sub["fecha_dato"].max()) >= pd.Timestamp("2025-06-30")


# --------------------------------------------------------------------------------------
# 30.2 · EXR: la etiqueta de extensión, fuera de companyfacts
# --------------------------------------------------------------------------------------

_INSTANCIA = """<?xml version="1.0"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:exr="http://exr.com/x">
  <context id="c-5">
    <entity><identifier>0001289490</identifier></entity>
    <period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period>
  </context>
  <context id="c-9">
    <entity><identifier>0001289490</identifier></entity>
    <period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period>
    <segment><member>UnSegmento</member></segment>
  </context>
  <exr:InterestExpenseExcludingAmortizationOfDebtDiscountPremium
      contextRef="c-5" unitRef="usd">146720000</exr:InterestExpenseExcludingAmortizationOfDebtDiscountPremium>
  <exr:InterestExpenseExcludingAmortizationOfDebtDiscountPremium
      contextRef="c-9" unitRef="usd">40000000</exr:InterestExpenseExcludingAmortizationOfDebtDiscountPremium>
</xbrl>
"""


def test_la_etiqueta_de_extension_se_lee_del_instance():
    df = hechos_de_instancia(
        _INSTANCIA, "EXR",
        {"InterestExpenseExcludingAmortizationOfDebtDiscountPremium"},
        fecha_publicacion=dt.date(2026, 7, 31),
    )
    assert len(df) == 1, f"esperaba un hecho consolidado, llegaron {len(df)}"
    fila = df.iloc[0]
    assert fila["valor"] == 146_720_000.0
    assert fila["periodo_tipo"] == "Q"
    assert fila["fecha_dato"] == dt.date(2026, 6, 30)
    assert fila["fecha_publicacion"] == dt.date(2026, 7, 31)


def test_un_hecho_de_segmento_no_se_confunde_con_el_consolidado():
    """La trampa del instance, y la que no se ve en el resultado.

    El mismo hecho aparece una vez por el total y una por cada segmento o clase
    de deuda. Tomar cualquiera mete el gasto por intereses de una parte como si
    fuera el de toda la emisora, y el número resultante se ve perfectamente
    razonable.
    """
    df = hechos_de_instancia(
        _INSTANCIA, "EXR",
        {"InterestExpenseExcludingAmortizationOfDebtDiscountPremium"},
        fecha_publicacion=dt.date(2026, 7, 31),
    )
    assert 40_000_000.0 not in set(df["valor"]), "entró un hecho con dimensiones"


def test_sin_etiquetas_declaradas_no_se_lee_nada():
    """El camino caro solo se paga donde hace falta.

    El control era Realty Income hasta que resultó tener su propia etiqueta de
    extensión —la revolvente con el papel comercial, ver la prueba 31—, así que
    ahora lo hace NNN. Lo que se comprueba es lo mismo: que la ausencia de
    declaración signifique cero peticiones al documento XBRL.
    """
    assert hechos_de_instancia(_INSTANCIA, "EXR", set(),
                               fecha_publicacion=dt.date(2026, 7, 31)).empty
    assert etiquetas_de_instancia("NNN") == set()
    assert etiquetas_de_instancia("EXR")


def test_un_instance_ilegible_no_tumba_la_ingesta():
    assert hechos_de_instancia("no es xml", "EXR", {"Lo"},
                               fecha_publicacion=dt.date(2026, 7, 31)).empty


# --------------------------------------------------------------------------------------
# 30.3 · Un saldo viejo no es el saldo de hoy
# --------------------------------------------------------------------------------------


def _guardar_saldo(repo, concepto, fecha, valor):
    repo.guardar_hechos([{
        "ticker": "X", "concepto": concepto, "periodo_tipo": "PUNTUAL",
        "periodo_inicio": None, "fecha_dato": fecha, "fecha_publicacion": fecha,
        "valor": valor, "unidad": "USD", "fuente": Fuente.SEC_XBRL,
        "es_primario": True, "estado": Estado.VALIDO, "url_filing": None, "accession": "a",
    }])


def test_un_saldo_de_hace_cinco_anios_no_entra_como_el_de_hoy(tmp_path):
    """El caso de Extra Space, y el más peligroso de todos los encontrados.

    Su deuda total salía de `NotesPayable`, cuya última observación es de
    septiembre de 2021. Con ella el apalancamiento daba 2.0x —de los más sanos
    del universo— cuando sus tramos vivos suman más del doble de esa deuda.

    En una serie de FLUJO la antigüedad se ve: los datos se acaban y la pantalla
    lo dice. Un SALDO se presenta como "el último conocido" y entra al ratio como
    si fuera actual, así que su antigüedad es invisible. Por eso el criterio de
    "conservar la etiqueta con más cobertura cuando ninguna está viva" es
    razonable para un flujo y no lo es para un saldo.
    """
    repo = Repositorio(ruta=tmp_path / "b.db")
    _guardar_saldo(repo, "deuda_total", dt.date(2021, 9, 30), 5_410e6)
    _guardar_saldo(repo, "activos_totales", dt.date(2026, 6, 30), 29_660e6)
    _guardar_saldo(repo, "notas_senior", dt.date(2026, 6, 30), 9_461e6)
    _guardar_saldo(repo, "linea_de_credito", dt.date(2026, 6, 30), 1_617e6)

    saldos = _saldos_de_balance(repo, "X", asof=dt.date(2026, 9, 8))
    assert saldos["deuda_total"] != pytest.approx(5_410e6), (
        "usó un saldo de 2021 como la deuda de hoy"
    )
    # Y en su lugar arma la deuda de los tramos que SÍ están vigentes.
    assert saldos["deuda_total"] == pytest.approx(9_461e6 + 1_617e6)


def test_un_saldo_del_ultimo_corte_si_entra(tmp_path):
    """El control: la guarda no puede tirar el saldo bueno."""
    repo = Repositorio(ruta=tmp_path / "b.db")
    _guardar_saldo(repo, "deuda_total", dt.date(2026, 6, 30), 17_934e6)
    _guardar_saldo(repo, "activos_totales", dt.date(2026, 6, 30), 67_221e6)
    saldos = _saldos_de_balance(repo, "X", asof=dt.date(2026, 9, 8))
    assert saldos["deuda_total"] == pytest.approx(17_934e6)


def test_la_vigencia_se_mide_contra_el_balance_del_emisor_no_contra_el_calendario(tmp_path):
    """Quien no ha reportado en un año no tiene un saldo viejo: tiene un reporte tarde.

    Medir contra la fecha de hoy castigaría a una emisora por ir retrasada en su
    presentación, que es otro problema y no el que esta guarda resuelve.
    """
    repo = Repositorio(ruta=tmp_path / "b.db")
    _guardar_saldo(repo, "deuda_total", dt.date(2024, 12, 31), 1_000e6)
    _guardar_saldo(repo, "activos_totales", dt.date(2024, 12, 31), 5_000e6)
    saldos = _saldos_de_balance(repo, "X", asof=dt.date(2026, 9, 8))
    assert saldos["deuda_total"] == pytest.approx(1_000e6)


def test_la_ventana_de_vigencia_deja_pasar_un_rezago_normal():
    """Un trimestre se reporta a las seis semanas; medio año es holgado y acotado."""
    assert dt.timedelta(days=120) < VIGENCIA_DE_SALDO < dt.timedelta(days=400)


# --------------------------------------------------------------------------------------
# 30.4 · La deuda compuesta tiene que estar completa
# --------------------------------------------------------------------------------------


def test_los_cuatro_tramos_de_extra_space_suman_su_deuda():
    """Sumar solo notas senior y revolvente dejaba fuera 2,568 MM: un 19%.

    En un ratio de apalancamiento ese error va en la dirección peligrosa — la
    emisora se ve más sana de lo que está—, que es justo la que no se puede
    cometer.
    """
    saldos = {
        "notas_senior": 9_461e6, "linea_de_credito": 1_617e6,
        "deuda_no_garantizada": 1_495e6, "otras_notas_por_pagar": 1_073e6,
        "pasivos_totales": 15_483e6,
    }
    assert _deuda_compuesta(saldos) == pytest.approx(13_646e6)


def test_la_linea_no_garantizada_no_tiene_etiqueta_por_omision():
    """Su candidata natural ya alimenta a `notas_senior`.

    Si las dos líneas leyeran `UnsecuredDebt`, la emisora que la usa como sus
    notas senior —Welltower— contaría esa deuda dos veces. Por eso solo la
    declara quien la reporta aparte.
    """
    assert LINEA_POR_CLAVE["deuda_no_garantizada"].tags == ()
    assert tags_de("EXR", "deuda_no_garantizada") == ("UnsecuredDebt",)
    assert tags_de("WELL", "deuda_no_garantizada") == ()


def test_todos_los_tramos_estan_en_el_catalogo():
    for clave in TRAMOS_DE_DEUDA:
        assert clave in LINEA_POR_CLAVE, f"{clave} suma deuda y no es un renglón"
