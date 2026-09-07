"""Prueba 28 — Los treinta y cinco descuadres de 2008 a 2017, cerrados.

El almacén guardaba la historia completa y traía treinta y cinco cortes donde el
activo no igualaba al pasivo más el capital. La prueba del balance solo respondía
de 2018 en adelante y los viejos quedaban bajo un techo para que no crecieran.

Un techo no es una explicación. Al abrirlos uno por uno resultaron ser TRES cosas
distintas metidas bajo el mismo nombre, y el orden en que se preguntan es lo que
las separa:

* **Veintidós eran el mezzanine sin mapear.** El capital temporal va entre el
  pasivo y el capital permanente; si no se lee, el balance no cierra por su
  tamaño exacto. La taxonomía lo escribe de nueve maneras y faltaba la más
  corta, ``TemporaryEquityCarryingAmount``. Como la emisora publica un solo
  nombre por corte, las etiquetas nunca se traslapan, y el empalme verificado
  —que exige traslape para poder comprobarse— las rechazaba todas (28.1).

* **Cuatro eran reexpresiones parciales.** Cada renglón se toma en su versión más
  reciente, que es lo correcto para saber qué se sabe hoy. Pero cuando la emisora
  reexpresa uno y no vuelve a etiquetar los otros, el corte queda armado con dos
  reportes y la identidad deja de aplicar. Prologis reexpresó su activo del 1T
  2017 —29,481 MM contra 29,815— y nunca republicó el pasivo más capital de ese
  corte: compararlos es comparar dos balances (28.2).

* **Nueve eran un renglón intermedio que falta.** El total que declara la propia
  emisora sí cuadra contra el activo, así que su balance cierra y las etiquetas
  de activo y total están bien; lo que no llega es NUESTRA suma por partes. No
  invalida el estado ni toca el apalancamiento, que sale de la deuda y el
  efectivo (28.3).

Ninguno de los tres era lo que decía el nombre. Cerrarlos permitió quitar la
ventana de 2018 y el techo: la prueba del almacén responde ahora por la historia
completa, hasta 2004.
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
from src.datos.almacen import leer_crudos  # noqa: E402
from src.ingesta.estados import (  # noqa: E402
    BALANCE,
    LINEA_POR_CLAVE,
    armar_estado,
    balance_por_reporte,
    derivar_trimestres_faltantes,
    elegir_cadenas,
)
from src.validacion.estados import (  # noqa: E402
    AVISO,
    ERROR,
    verificar_balance,
)


def _crudos(filas: list[dict]) -> pd.DataFrame:
    base = {
        "ticker": "X", "taxonomia": "us-gaap", "unidad": "USD",
        "periodo_tipo": "PUNTUAL", "fecha_inicio": None,
        "fecha_publicacion": dt.date(2026, 8, 1),
        "formulario": "10-Q", "accession": "a-1", "marco": "",
    }
    df = pd.DataFrame([{**base, **f} for f in filas])
    df["fecha_dato"] = pd.to_datetime(df["fecha_dato"]).dt.date
    df["fecha_publicacion"] = pd.to_datetime(df["fecha_publicacion"]).dt.date
    return df


# --------------------------------------------------------------------------------------
# 28.1 · El mezzanine: alternativas excluyentes
# --------------------------------------------------------------------------------------


def test_el_capital_temporal_admite_empalme_sin_traslape():
    """Nueve nombres para el mismo renglón, y la emisora usa uno por corte.

    Exigir traslape para empalmarlos no protege de nada aquí —el traslape no puede
    existir por construcción— y sí garantiza el hueco: era la causa de veintidós
    de los treinta y cinco descuadres.
    """
    assert LINEA_POR_CLAVE["capital_temporal"].alternativas_excluyentes

    filas = []
    for i, f in enumerate(pd.date_range("2016-03-31", periods=12, freq="QE")):
        filas.append({"tag": "TemporaryEquityCarryingAmount",
                      "fecha_dato": f.date(), "valor": 100.0 + i})
    for i, f in enumerate(pd.date_range("2020-03-31", periods=12, freq="QE")):
        filas.append({"tag": "RedeemableNoncontrollingInterestEquityCarryingAmount",
                      "fecha_dato": f.date(), "valor": 200.0 + i})
    cadena = elegir_cadenas(_crudos(filas), "X")["capital_temporal"]

    assert len(cadena) == 2, f"no empalmó dos nombres del mismo renglón: {cadena}"


def test_un_renglon_normal_sigue_exigiendo_traslape():
    """El control. La regla es una excepción declarada, no el comportamiento nuevo.

    Sin esta prueba, "empalmar sin traslape" podría haberse aplicado a todo, y ahí
    sí cose series que no son de nadie: el gasto por intereses de Extra Space
    difiere ocho veces entre dos de sus etiquetas.
    """
    assert not LINEA_POR_CLAVE["deuda_total"].alternativas_excluyentes

    filas = []
    for i, f in enumerate(pd.date_range("2016-03-31", periods=12, freq="QE")):
        filas.append({"tag": "LongTermDebt", "fecha_dato": f.date(), "valor": 100.0 + i})
    for i, f in enumerate(pd.date_range("2020-03-31", periods=12, freq="QE")):
        filas.append({"tag": "NotesPayable", "fecha_dato": f.date(), "valor": 900.0 + i})
    cadena = elegir_cadenas(_crudos(filas), "X")["deuda_total"]

    assert len(cadena) == 1, f"empalmó sin poder comprobarlo: {cadena}"


def test_la_etiqueta_corta_del_mezzanine_esta_mapeada():
    """`TemporaryEquityCarryingAmount` es la canónica y era la que faltaba.

    Es la que usaban Public Storage y W. P. Carey antes de 2012, y su ausencia
    dejaba el balance corto por 12.3 MM y 7.7 MM — el tamaño exacto del renglón.
    """
    tags = LINEA_POR_CLAVE["capital_temporal"].tags
    assert "TemporaryEquityCarryingAmount" in tags
    # El importe EN LIBROS va antes que el valor de redención: es el que suma.
    assert tags.index("TemporaryEquityCarryingAmount") < tags.index(
        "TemporaryEquityRedemptionValue"
    )


# --------------------------------------------------------------------------------------
# 28.2 · Una reexpresión parcial no es un error de lectura
# --------------------------------------------------------------------------------------


def _balance(**lineas) -> pd.DataFrame:
    periodo = dt.date(2017, 3, 31)
    return pd.DataFrame({
        clave: {"etiqueta": clave, "tag_gaap": "x", "subtotal": True, periodo: valor}
        for clave, valor in lineas.items()
    }).T


def test_una_reexpresion_parcial_se_reporta_como_mezcla_y_no_como_error():
    """El caso de Prologis en el primer trimestre de 2017.

    Reexpresó el activo en el 10-Q del año siguiente y nunca volvió a etiquetar el
    pasivo más capital de ese corte. La vista de hoy toma cada renglón en su
    versión más reciente —que es lo correcto— y acaba comparando dos balances.
    """
    tabla = _balance(activos_totales=29_481.0, pasivo_mas_capital=29_815.0,
                     pasivos_totales=12_146.0, capital_total=17_668.0)
    por_reporte = pd.DataFrame([
        # El reporte original: ahí el balance cerraba.
        {"linea": "activos_totales", "fecha_dato": dt.date(2017, 3, 31),
         "fecha_publicacion": dt.date(2017, 4, 25), "valor": 29_815.0},
        {"linea": "pasivo_mas_capital", "fecha_dato": dt.date(2017, 3, 31),
         "fecha_publicacion": dt.date(2017, 4, 25), "valor": 29_815.0},
    ])
    incidencias = verificar_balance("PLD", tabla, por_reporte)

    assert incidencias, "una mezcla de reportes tiene que verse"
    assert all(i.severidad == AVISO for i in incidencias)
    assert any(i.prueba == "balance_de_dos_reportes" for i in incidencias)


def test_sin_ningun_reporte_que_cuadre_sigue_siendo_error():
    """El control: la excepción es "alguien lo publicó cuadrado", no "es viejo"."""
    tabla = _balance(activos_totales=100.0, pasivo_mas_capital=90.0)
    por_reporte = pd.DataFrame([
        {"linea": "activos_totales", "fecha_dato": dt.date(2017, 3, 31),
         "fecha_publicacion": dt.date(2017, 4, 25), "valor": 100.0},
        {"linea": "pasivo_mas_capital", "fecha_dato": dt.date(2017, 3, 31),
         "fecha_publicacion": dt.date(2017, 4, 25), "valor": 90.0},
    ])
    incidencias = verificar_balance("X", tabla, por_reporte)
    assert any(i.severidad == ERROR for i in incidencias)


def test_el_balance_por_reporte_no_colapsa_las_versiones():
    """Es la tabla que permite preguntar "¿alguna vez cuadró?" en vez de "¿cuadra?"."""
    filas = [
        {"tag": "Assets", "fecha_dato": dt.date(2017, 3, 31), "valor": 29_815.0,
         "fecha_publicacion": dt.date(2017, 4, 25)},
        {"tag": "Assets", "fecha_dato": dt.date(2017, 3, 31), "valor": 29_481.0,
         "fecha_publicacion": dt.date(2018, 4, 24)},
    ]
    por = balance_por_reporte(_crudos(filas), "X", asof=dt.date(2026, 9, 7))
    activos = por[por["linea"] == "activos_totales"]
    assert len(activos) == 2, "colapsó las dos versiones y perdió la reexpresión"
    assert set(activos["fecha_publicacion"]) == {dt.date(2017, 4, 25), dt.date(2018, 4, 24)}


# --------------------------------------------------------------------------------------
# 28.3 · Un renglón intermedio que falta no es un balance roto
# --------------------------------------------------------------------------------------


def test_si_el_total_declarado_cuadra_la_falla_es_de_descomposicion():
    tabla = _balance(activos_totales=100.0, pasivos_totales=60.0,
                     capital_total=35.0, pasivo_mas_capital=100.0)
    incidencias = verificar_balance("X", tabla)
    assert incidencias and all(i.prueba == "descomposicion_incompleta" for i in incidencias)
    assert all(i.severidad == AVISO for i in incidencias)


# --------------------------------------------------------------------------------------
# 28.4 · El resultado sobre el almacén real
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("emisor", UNIVERSO_INICIAL, ids=lambda e: e.ticker)
def test_ninguna_emisora_tiene_un_balance_roto_en_toda_su_historia(emisor):
    """La garantía sin asterisco, sobre las diez emisoras y hasta 2004.

    Antes había una ventana —de 2018 en adelante— y un techo de descuadres
    tolerados por emisora. Las dos cosas se quitaron porque ya no hacen falta.
    """
    crudos = leer_crudos(emisor.ticker)
    if crudos.empty:
        pytest.skip(f"{emisor.ticker} no está en el almacén.")
    cadenas = elegir_cadenas(crudos, emisor.ticker)
    completos = derivar_trimestres_faltantes(crudos, cadenas)
    balance = armar_estado(
        completos, emisor.ticker, BALANCE, asof=dt.date.today(), tags=cadenas
    )
    por_reporte = balance_por_reporte(
        completos, emisor.ticker, asof=dt.date.today(), tags=cadenas
    )
    errores = [
        i
        for i in verificar_balance(emisor.ticker, balance, por_reporte)
        if i.severidad == ERROR
    ]
    assert not errores, "\n".join(i.como_texto() for i in errores)
