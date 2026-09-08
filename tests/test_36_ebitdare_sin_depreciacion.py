"""Prueba 36 — Una partida que falta no puede valer cero.

De dónde salió
--------------
La prueba 33 cerró el rezago de `companyfacts` trayendo del documento XBRL el
FILING completo y no nada más el balance. Con eso el trimestre de junio de 2026
de Welltower entró a la base… incompleto: su 10-Q reporta la depreciación bajo
``DepreciationDepletionAndAmortization`` y hasta marzo la venía reportando bajo
``DepreciationAndAmortization``. Las dos etiquetas difieren hasta 24% entre 2009
y 2012, así que el empalme verificado las rechaza —y hace bien—.

El resultado fue peor que el hueco que arreglaba. ``_derivar_ebitdare`` sumaba la
depreciación con ``_col``, que rellena los faltantes con cero, y en un REIT la
depreciación es la MAYOR de las partidas que se suman de vuelta: en Welltower
vale más que la utilidad neta y los intereses juntos. El trimestre daba un
EBITDAre de 608.7 millones en vez de 1,320.7, el TTM caía de 4,821 a 4,109 y el
apalancamiento salía en 3.84x cuando es 3.27x.

Un número, no un hueco. Plausible, en el rango de siempre, y equivocado. Es la
misma invisibilidad de la prueba 30 —un dato que falta y no se nota— movida a la
aritmética: ahí el saldo era viejo, aquí el sumando es cero.

Qué se decidió
--------------
1. El EBITDAre exige depreciación, igual que ya exigía intereses (36.1). Cuesta
   cinco trimestres en todo el universo, los cinco de Welltower, cuatro de ellos
   de 2009.
2. Y lo dice (36.2). Que el criterio aparezca SIN DATOS es correcto pero mudo, y
   mudo no distingue entre "la emisora no lo reportó" y "el catálogo no lo
   alcanzó".
3. La tolerancia del empalme NO se tocó (36.3). Aflojarla para recuperar este
   dato admitía ocho empalmes más en el universo, y entre ellos la utilidad neta
   común pegada a la utilidad neta, y la deuda total pegada a la deuda con
   arrendamientos financieros. Recuperar un trimestre no vale eso.
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

from src.config import UNIVERSO_INICIAL  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta import estados as mod_estados  # noqa: E402
from src.servicio import (  # noqa: E402
    _cuadro_con_depreciacion,
    _derivar_ebitdare,
    construir_panel,
)


def _trimestre(**valores) -> pd.DataFrame:
    base = {"utilidad_neta": 463.0, "gasto_intereses": 181.9, "impuestos": -62.0,
            "depreciacion_amortizacion": 737.8}
    base.update(valores)
    return pd.DataFrame([base], index=pd.DatetimeIndex([dt.date(2026, 6, 30)]))


# --------------------------------------------------------------------------------------
# 36.1 · Sin depreciación no hay EBITDAre
# --------------------------------------------------------------------------------------


def test_con_depreciacion_da_el_ebitdare_completo():
    """El caso normal, para que el de abajo signifique algo."""
    serie = _derivar_ebitdare(_trimestre())
    assert float(serie.iloc[0]) == pytest.approx(463.0 + 181.9 - 62.0 + 737.8)


def test_sin_depreciacion_no_da_numero():
    """Y en particular no da la suma sin ella, que es lo que daba antes.

    El valor equivocado era 582.9 sobre estos números —el de Welltower en junio,
    a escala—: un EBITDAre creíble que habría entrado al ratio de apalancamiento
    sin que nada lo delatara.
    """
    serie = _derivar_ebitdare(_trimestre(depreciacion_amortizacion=None))
    assert pd.isna(serie.iloc[0])


def test_la_columna_ausente_se_trata_como_faltante_no_como_cero():
    """No es lo mismo que la emisora reporte cero a que no reporte."""
    df = _trimestre()
    serie = _derivar_ebitdare(df.drop(columns=["depreciacion_amortizacion"]))
    assert pd.isna(serie.iloc[0])
    # Un cero REPORTADO sí es un dato y sí da número.
    assert float(_derivar_ebitdare(_trimestre(depreciacion_amortizacion=0.0)).iloc[0]) == (
        pytest.approx(463.0 + 181.9 - 62.0)
    )


def test_sigue_exigiendo_utilidad_e_intereses():
    """La guarda vieja no se perdió al agregar la nueva."""
    assert pd.isna(_derivar_ebitdare(_trimestre(utilidad_neta=None)).iloc[0])
    assert pd.isna(_derivar_ebitdare(_trimestre(gasto_intereses=0.0)).iloc[0])


# --------------------------------------------------------------------------------------
# 36.2 · Y se dice por qué
# --------------------------------------------------------------------------------------


def test_el_aviso_distingue_el_hueco_callado_del_evidente():
    """Solo se avisa del trimestre que llegó incompleto.

    Si tampoco hay utilidad ni intereses, el trimestre entero está vacío y eso ya
    se ve en la serie: un aviso ahí sería ruido, no información.
    """
    assert _cuadro_con_depreciacion(_trimestre()) is True
    assert _cuadro_con_depreciacion(_trimestre(depreciacion_amortizacion=None)) is False
    # Sin utilidad o sin intereses tampoco hay EBITDAre, pero eso no se avisa: la
    # serie ya se ve cortada. Falta la depreciación en los dos casos, a propósito
    # —es la única forma de distinguir "no aviso porque está completo" de "no
    # aviso porque el trimestre entero está vacío"—.
    assert _cuadro_con_depreciacion(
        _trimestre(utilidad_neta=None, depreciacion_amortizacion=None)
    ) is True
    assert _cuadro_con_depreciacion(
        _trimestre(gasto_intereses=None, depreciacion_amortizacion=None)
    ) is True
    assert _cuadro_con_depreciacion(
        _trimestre(gasto_intereses=0.0, depreciacion_amortizacion=None)
    ) is True
    assert _cuadro_con_depreciacion(pd.DataFrame()) is True


def test_welltower_trae_el_aviso_y_nadie_mas():
    repo = Repositorio()
    hoy = dt.date.today()
    con_aviso = []
    for e in UNIVERSO_INICIAL:
        panel = construir_panel(repo, e.ticker, asof=hoy)
        if panel.trimestral.empty:
            pytest.skip("No hay base cargada.")
        if any("no la depreciación" in a for a in panel.avisos):
            con_aviso.append(e.ticker)
    assert con_aviso == ["WELL"], f"el aviso cambió de emisoras: {con_aviso}"


def test_ninguna_otra_emisora_perdio_su_apalancamiento():
    """El precio del arreglo, medido: una emisora, no nueve."""
    repo = Repositorio()
    hoy = dt.date.today()
    sin_ratio = []
    for e in UNIVERSO_INICIAL:
        tr = construir_panel(repo, e.ticker, asof=hoy).trimestral
        if tr.empty:
            pytest.skip("No hay base cargada.")
        if "ebitdare_ttm" not in tr or pd.isna(tr["ebitdare_ttm"].iloc[-1]):
            sin_ratio.append(e.ticker)
    assert sin_ratio == ["WELL"], f"emisoras sin EBITDAre en el último trimestre: {sin_ratio}"


# --------------------------------------------------------------------------------------
# 36.3 · La tolerancia del empalme se queda donde está
# --------------------------------------------------------------------------------------


def test_el_empalme_de_la_depreciacion_de_welltower_sigue_rechazado():
    """La prueba que impide "arreglar" esto por el lado equivocado.

    Recuperar el dato aflojando ``_empalma`` habría admitido ocho empalmes más en
    el universo. Entre ellos, en Realty Income y EPRT, la utilidad neta común
    pegada detrás de la utilidad neta —que difieren en los dividendos
    preferentes— y en Prologis la deuda total pegada a la deuda con
    arrendamientos financieros. Ocho números que no son de nadie a cambio de un
    trimestre.
    """
    crudos = pd.read_csv(
        RAIZ / "data/emisoras/WELL/hechos.csv.gz",
        parse_dates=["fecha_inicio", "fecha_dato", "fecha_publicacion"],
    )
    for col in ("fecha_inicio", "fecha_dato", "fecha_publicacion"):
        crudos[col] = crudos[col].dt.date

    series = mod_estados._series_por_tag(crudos)
    a, b = series["DepreciationAndAmortization"], series["DepreciationDepletionAndAmortization"]
    comunes = a.index.intersection(b.index)
    assert len(comunes) > 20, "sin traslape la prueba no dice nada"

    desvio = ((a.loc[comunes] - b.loc[comunes]).abs() / b.loc[comunes].abs()).max()
    assert desvio > mod_estados.TOLERANCIA_EMPALME
    assert not mod_estados._empalma(a, b, excluyentes=False)

    cadena = mod_estados.elegir_cadenas(crudos, "WELL")["depreciacion_amortizacion"]
    assert cadena == ("DepreciationAndAmortization",)


def test_la_depreciacion_de_junio_si_esta_en_el_crudo():
    """Lo que hace de esto un hueco de catálogo y no del emisor.

    El dato existe, viene del 10-Q y está guardado. Lo que no existe es una
    cadena que pueda llegar a él sin pegar dos series que no son la misma.
    """
    crudos = pd.read_csv(RAIZ / "data/emisoras/WELL/hechos.csv.gz")
    junio = crudos[
        (crudos["tag"] == "DepreciationDepletionAndAmortization")
        & (crudos["fecha_dato"] == "2026-06-30")
        & (crudos["periodo_tipo"] == "Q")
    ]
    assert len(junio) == 1
    assert float(junio.iloc[0]["valor"]) == pytest.approx(737_764_000)
    assert junio.iloc[0]["fecha_publicacion"] == "2026-07-28"
