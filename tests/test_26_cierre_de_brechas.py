"""Prueba 26 — Cerrar las brechas de las cinco emisoras que faltaban.

Cinco emisoras —NNN, GNL, EXR, PLD y WELL— no llegaban a un veredicto. El
diagnóstico, emisora por emisora, dio cuatro causas DISTINTAS, y confundirlas
habría llevado a parchar la equivocada:

* **PLD — la emisora se cambió de etiqueta a media serie.** Reportó su gasto por
  intereses en ``InterestExpense`` hasta el segundo trimestre de 2024 y pasó a
  ``InterestExpenseNonoperating``. Como se elegía UNA etiqueta por renglón, ganaba
  la vieja por cobertura y la valuación se quedaba sin los ocho trimestres más
  recientes. Se empalman — pero solo cuando se puede PROBAR que son el mismo
  renglón (26.1).

* **NNN — un hueco a media serie.** El primer trimestre de 2026 no está en
  `companyfacts` con ninguna etiqueta, y ese hueco mataba el TTM de los dos cortes
  siguientes. La aritmética que rescata el Q4 lo rescata igual: `Q1 = H1 − Q2`
  (26.2).

* **GNL — la deuda no se reporta junta.** Publica la hipotecaria, las notas senior
  y la línea revolvente por separado, y ningún renglón de deuda total. Se suman —
  con la revolvente adentro, que era el 20% que se iba a quedar fuera (26.3).

* **EXR y WELL — el dato no existe en la fuente.** Ninguna de las dos etiqueta su
  gasto por intereses en XBRL desde 2024. No se inventa: se nombra (26.5).

Y dos brechas que no eran de estas cinco sino de las diez: el flujo por acción
que no se deducía (26.4) y el yield de adquisiciones que nadie fijaba (26.6).
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

from src.config import CAP_RATE_POR_SECTOR  # noqa: E402
from src.ingesta.estados import (  # noqa: E402
    TOLERANCIA_EMPALME,
    _coalescer,
    derivar_trimestres_faltantes,
    elegir_cadenas,
    elegir_tags,
)
from src.servicio import (  # noqa: E402
    INSUMOS_CRITICOS,
    TRAMOS_DE_DEUDA,
    PanelEmisor,
    _deuda_compuesta,
    _yoy,
    diagnostico_de_insumos,
)


def _crudos(filas: list[dict]) -> pd.DataFrame:
    base = {
        "ticker": "X", "taxonomia": "us-gaap", "unidad": "USD",
        "periodo_tipo": "Q", "fecha_inicio": None,
        "fecha_publicacion": dt.date(2026, 8, 1),
        "formulario": "10-Q", "accession": "0000-00", "marco": "",
    }
    df = pd.DataFrame([{**base, **f} for f in filas])
    df["fecha_dato"] = pd.to_datetime(df["fecha_dato"]).dt.date
    return df


def _trimestres(tag: str, desde: dt.date, n: int, valor: float) -> list[dict]:
    """`n` trimestres consecutivos a partir de `desde`, con el mismo valor."""
    fechas = pd.date_range(desde, periods=n, freq="QE")
    return [{"tag": tag, "fecha_dato": f.date(), "valor": valor} for f in fechas]


# --------------------------------------------------------------------------------------
# 26.1 · El empalme de etiquetas se PRUEBA contra el traslape, no se supone
# --------------------------------------------------------------------------------------


def test_se_empalma_la_etiqueta_nueva_cuando_coincide_en_el_traslape():
    """El caso de Prologis, con sus dos etiquetas de intereses.

    Donde las dos reportan el mismo trimestre traen el MISMO número —181.1, 193.3
    y 208.3 millones—, y eso es la prueba de que es un renglón re-etiquetado y no
    dos conceptos. Sin empalmar, la serie se detiene en 2024 y no hay EBITDAre.
    """
    filas = [
        *_trimestres("InterestExpense", dt.date(2022, 3, 31), 10, 200.0),
        # La nueva arranca traslapada con la vieja y sigue sola después.
        *_trimestres("InterestExpenseNonoperating", dt.date(2023, 12, 31), 12, 200.0),
    ]
    cadenas = elegir_cadenas(_crudos(filas), "PLD")
    cadena = cadenas["gasto_intereses"]

    assert "InterestExpense" in cadena and "InterestExpenseNonoperating" in cadena, (
        f"no empalmó dos etiquetas idénticas en el traslape: {cadena}"
    )
    # Y la cabeza sigue siendo la de siempre: `elegir_tags` no cambia de contrato.
    assert elegir_tags(_crudos(filas), "PLD")["gasto_intereses"] == cadena[0]


def test_no_se_empalman_dos_etiquetas_que_no_son_el_mismo_renglon():
    """El caso de Extra Space, que es el que hace falta rechazar.

    Etiquetó el MISMO trimestre como ``InterestExpenseDebt`` = 5.7 MM y como
    ``InterestExpense`` = 46.9 MM. Son dos conceptos distintos, y pegarlos cose
    una serie que no es de nadie: sube ocho veces a media historia sin que ningún
    número se vea raro. Preferimos el hueco.
    """
    filas = [
        *_trimestres("InterestExpense", dt.date(2019, 3, 31), 12, 46.9),
        *_trimestres("InterestExpenseDebt", dt.date(2015, 3, 31), 20, 5.7),
    ]
    cadena = elegir_cadenas(_crudos(filas), "EXR")["gasto_intereses"]

    assert cadena == ("InterestExpense",), (
        f"empalmó dos series que difieren 8x en el traslape: {cadena}"
    )


def test_sin_traslape_no_se_empalma_porque_no_se_puede_probar():
    """Un cambio limpio de etiqueta, sin un solo periodo en común.

    Puede que sean el mismo renglón. No hay cómo saberlo, y callar la duda sale
    más caro que el hueco: el número que saldría alimenta un criterio binario.
    """
    filas = [
        *_trimestres("InterestExpense", dt.date(2016, 3, 31), 8, 100.0),
        *_trimestres("InterestExpenseNonoperating", dt.date(2024, 3, 31), 8, 250.0),
    ]
    cadena = elegir_cadenas(_crudos(filas), "PLD")["gasto_intereses"]
    assert len(cadena) == 1, f"empalmó sin un solo periodo con qué compararlas: {cadena}"


def test_el_empalme_respeta_la_tolerancia_declarada():
    """El redondeo del emisor pasa; una diferencia real, no.

    La frontera no es una opinión: está en `TOLERANCIA_EMPALME` y esta prueba la
    mide por los dos lados con el mismo armado.
    """
    def cadena_con(valor_nuevo: float) -> tuple[str, ...]:
        filas = [
            *_trimestres("InterestExpense", dt.date(2022, 3, 31), 10, 100.0),
            *_trimestres("InterestExpenseNonoperating", dt.date(2023, 12, 31), 12,
                         valor_nuevo),
        ]
        return elegir_cadenas(_crudos(filas), "PLD")["gasto_intereses"]

    dentro = 100.0 * (1 + TOLERANCIA_EMPALME / 2)
    fuera = 100.0 * (1 + TOLERANCIA_EMPALME * 3)
    assert len(cadena_con(dentro)) == 2, "rechazó una diferencia de puro redondeo"
    assert len(cadena_con(fuera)) == 1, "aceptó una diferencia que no es redondeo"


def test_la_etiqueta_principal_manda_en_el_periodo_que_ambas_reportan():
    """El empalme RELLENA, no sobrescribe: no se mezcla dentro de un mismo periodo.

    En el traslape las dos traen un número —parecido, porque si no no se habrían
    empalmado, pero no idéntico— y el renglón tiene que quedarse con el de la
    cabeza de la cadena. Si en cambio ganara la última en llegar, la serie
    cambiaría de fuente a media historia sin que nada lo dijera.
    """
    filas = [
        *_trimestres("InterestExpense", dt.date(2022, 3, 31), 10, 100.0),
        *_trimestres("InterestExpenseNonoperating", dt.date(2023, 12, 31), 12, 100.4),
    ]
    crudos = _crudos(filas)
    cadena = elegir_cadenas(crudos, "PLD")["gasto_intereses"]
    assert len(cadena) == 2, f"no empalmó dos series compatibles: {cadena}"

    resuelto = _coalescer(crudos, {"gasto_intereses": cadena})
    cabeza = crudos[crudos["tag"] == cadena[0]]
    traslape = set(cabeza["fecha_dato"]) & set(crudos[crudos["tag"] == cadena[1]]["fecha_dato"])
    assert traslape, "el armado de la prueba no produjo traslape"

    en_traslape = resuelto[resuelto["fecha_dato"].isin(traslape)]
    assert set(en_traslape["tag"]) == {cadena[0]}, (
        "en un periodo que ambas reportan ganó la etiqueta empalmada, no la principal"
    )
    # Y la cadena completa cubre más periodos que la cabeza sola: para eso se empalma.
    assert resuelto["fecha_dato"].nunique() > cabeza["fecha_dato"].nunique()


# --------------------------------------------------------------------------------------
# 26.2 · El trimestre que falta se despeja de un acumulado, si es UNO solo
# --------------------------------------------------------------------------------------


def _hecho(tipo: str, inicio, fin, valor: float, pub=dt.date(2026, 8, 5)) -> dict:
    return {
        "ticker": "X", "taxonomia": "us-gaap", "tag": "InterestExpense", "unidad": "USD",
        "periodo_tipo": tipo, "fecha_inicio": inicio, "fecha_dato": fin,
        "fecha_publicacion": pub, "valor": valor,
        "formulario": "10-Q", "accession": "a", "marco": "",
    }


TAGS = {"gasto_intereses": "InterestExpense"}


def test_el_primer_trimestre_se_despeja_del_semestre_menos_el_segundo():
    """El caso de NNN, que es el que dejó dos cortes sin EBITDAre.

    Su 10-Q del segundo trimestre de 2026 trae la columna del semestre (106.2) y
    la del trimestre (53.5). El primer trimestre no aparece con NINGUNA etiqueta,
    y sin él el TTM se cae. `H1 − Q2 = Q1`.
    """
    crudos = pd.DataFrame([
        _hecho("H1", dt.date(2026, 1, 1), dt.date(2026, 6, 30), 106.2),
        _hecho("Q", dt.date(2026, 4, 1), dt.date(2026, 6, 30), 53.5),
    ])
    salida = derivar_trimestres_faltantes(crudos, TAGS)
    nuevo = salida[salida["formulario"] == "DERIVADO"]

    assert len(nuevo) == 1, f"no despejó el trimestre faltante: {len(nuevo)} derivados"
    assert nuevo["fecha_dato"].iloc[0] == dt.date(2026, 3, 31)
    assert float(nuevo["valor"].iloc[0]) == pytest.approx(106.2 - 53.5)
    assert nuevo["periodo_tipo"].iloc[0] == "Q"


def test_no_se_despeja_nada_cuando_faltan_dos_trimestres():
    """Con dos incógnitas y una ecuación no hay solución, hay invención."""
    crudos = pd.DataFrame([
        _hecho("9M", dt.date(2026, 1, 1), dt.date(2026, 9, 30), 150.0),
        _hecho("Q", dt.date(2026, 1, 1), dt.date(2026, 3, 31), 50.0),
    ])
    salida = derivar_trimestres_faltantes(crudos, TAGS)
    assert (salida["formulario"] == "DERIVADO").sum() == 0, (
        "despejó un trimestre teniendo dos huecos en el mismo acumulado"
    )


def test_nunca_se_fabrica_algo_que_no_sea_un_trimestre():
    """De un año y un trimestre saldría un periodo de nueve meses. No se emite.

    El panel se arma con trimestres; un acumulado inventado ahí dentro se sumaría
    como si fuera uno solo y multiplicaría por tres el renglón.
    """
    crudos = pd.DataFrame([
        _hecho("FY", dt.date(2025, 1, 1), dt.date(2025, 12, 31), 200.0),
        _hecho("Q", dt.date(2025, 10, 1), dt.date(2025, 12, 31), 55.0),
    ])
    salida = derivar_trimestres_faltantes(crudos, TAGS)
    assert (salida["formulario"] == "DERIVADO").sum() == 0


def test_el_despeje_encadena_del_semestre_al_ano():
    """Punto fijo: el Q1 del semestre habilita el Q3 de los nueve meses, y ese el Q4.

    Es lo que separa despejar de parchar un caso: la misma identidad se aplica
    hasta que no queda nada que despejar.
    """
    crudos = pd.DataFrame([
        _hecho("H1", dt.date(2025, 1, 1), dt.date(2025, 6, 30), 100.0),
        _hecho("Q", dt.date(2025, 4, 1), dt.date(2025, 6, 30), 60.0),
        _hecho("9M", dt.date(2025, 1, 1), dt.date(2025, 9, 30), 170.0),
        _hecho("FY", dt.date(2025, 1, 1), dt.date(2025, 12, 31), 250.0),
    ])
    salida = derivar_trimestres_faltantes(crudos, TAGS)
    derivados = salida[salida["formulario"] == "DERIVADO"].set_index("fecha_dato")

    assert float(derivados.loc[dt.date(2025, 3, 31), "valor"]) == pytest.approx(40.0)
    assert float(derivados.loc[dt.date(2025, 9, 30), "valor"]) == pytest.approx(70.0)
    assert float(derivados.loc[dt.date(2025, 12, 31), "valor"]) == pytest.approx(80.0)


def test_el_trimestre_despejado_se_fecha_cuando_ya_era_deducible():
    """P1. El Q1 de NNN no existía hasta que salió el 10-Q del segundo trimestre."""
    crudos = pd.DataFrame([
        _hecho("H1", dt.date(2026, 1, 1), dt.date(2026, 6, 30), 106.2,
               pub=dt.date(2026, 8, 5)),
        _hecho("Q", dt.date(2026, 4, 1), dt.date(2026, 6, 30), 53.5,
               pub=dt.date(2026, 8, 5)),
    ])
    salida = derivar_trimestres_faltantes(crudos, TAGS)
    assert salida[salida["formulario"] == "DERIVADO"]["fecha_publicacion"].iloc[0] == (
        dt.date(2026, 8, 5)
    )


def test_un_ejercicio_que_no_cae_en_frontera_de_mes_no_se_despeja():
    """Un año fiscal de 52/53 semanas no es divisible en trimestres calendario.

    Restarlo como si lo fuera produce un "trimestre" de duración desconocida.
    """
    crudos = pd.DataFrame([
        _hecho("H1", dt.date(2026, 1, 4), dt.date(2026, 7, 4), 100.0),
        _hecho("Q", dt.date(2026, 4, 5), dt.date(2026, 7, 4), 55.0),
    ])
    salida = derivar_trimestres_faltantes(crudos, TAGS)
    assert (salida["formulario"] == "DERIVADO").sum() == 0


# --------------------------------------------------------------------------------------
# 26.3 · La deuda que no se reporta junta se suma — con TODOS sus tramos
# --------------------------------------------------------------------------------------


def test_la_deuda_se_compone_de_sus_tramos_cuando_no_hay_total():
    """El caso de Global Net Lease, que no publica ningún renglón de deuda total."""
    saldos = {
        "deuda_hipotecaria": 987e6, "notas_senior": 940e6, "linea_de_credito": 473e6,
        "pasivos_totales": 2_557e6,
    }
    assert _deuda_compuesta(saldos) == pytest.approx(2_400e6)


def test_la_revolvente_entra_en_la_suma():
    """Sin ella el total daba 1,927 MM contra 2,400 reales: 20% menos deuda.

    El riesgo de sumar tramos es asimétrico y por eso tiene prueba propia: si
    falta uno, el emisor se dibuja MÁS SANO de lo que está, que es exactamente el
    error que no se puede cometer en una pantalla de apalancamiento.
    """
    con = {"deuda_hipotecaria": 987e6, "notas_senior": 940e6, "linea_de_credito": 473e6}
    sin = {k: v for k, v in con.items() if k != "linea_de_credito"}
    assert _deuda_compuesta(con) > _deuda_compuesta(sin)
    assert "linea_de_credito" in TRAMOS_DE_DEUDA


def test_una_suma_que_excede_el_pasivo_total_no_se_publica():
    """Si los tramos superan el pasivo, hay doble conteo: mejor no decir nada."""
    saldos = {
        "deuda_hipotecaria": 2_000e6, "notas_senior": 2_000e6,
        "pasivos_totales": 2_557e6,
    }
    assert _deuda_compuesta(saldos) is None


def test_sin_ningun_tramo_no_se_inventa_una_deuda():
    assert _deuda_compuesta({"pasivos_totales": 1_000e6}) is None


# --------------------------------------------------------------------------------------
# 26.4 · El crecimiento anual se mide contra el calendario, no contra la fila anterior
# --------------------------------------------------------------------------------------


def _panel_trimestral(fechas: list[str], valores: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"affo_por_accion": valores}, index=pd.to_datetime(fechas)
    )


def test_el_crecimiento_anual_compara_contra_el_mismo_trimestre_del_ano_pasado():
    fechas = ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31"]
    serie = _yoy(_panel_trimestral(fechas, [1.0, 1.0, 1.0, 1.0, 1.10]), "affo_por_accion")
    assert float(serie.iloc[-1]) == pytest.approx(0.10)


def test_con_un_hueco_no_se_compara_contra_el_de_hace_cinco_trimestres():
    """`pct_change(4)` cuenta filas. Con un trimestre faltante compara mal.

    Y aquí no produce un número raro: produce un criterio binario de la Puerta 1
    con el signo equivocado, que es un veredicto equivocado.
    """
    fechas = ["2024-12-31", "2025-03-31", "2025-09-30", "2025-12-31", "2026-03-31"]
    datos = _panel_trimestral(fechas, [5.0, 1.0, 1.0, 1.0, 1.10])
    serie = _yoy(datos, "affo_por_accion")

    ingenuo = datos["affo_por_accion"].pct_change(4).iloc[-1]
    assert float(ingenuo) == pytest.approx(1.10 / 5.0 - 1), "el control no reproduce el defecto"
    assert pd.isna(serie.iloc[-1]), (
        "comparó contra un trimestre que no es el mismo del año pasado"
    )


# --------------------------------------------------------------------------------------
# 26.5 · Un insumo que falta tiene nombre, fecha y consecuencia
# --------------------------------------------------------------------------------------


def _panel_con(trimestral: pd.DataFrame) -> PanelEmisor:
    return PanelEmisor(
        ticker="X", sector="Salud", asof=dt.date(2026, 9, 7), trimestral=trimestral,
        precio=100.0, precio_fecha=dt.date(2026, 9, 4), dividendo_ttm=3.0,
        tasa_libre_riesgo=0.045,
    )


def test_una_serie_que_la_emisora_dejo_de_publicar_se_marca_rezagada():
    """El caso de Welltower: su gasto por intereses se detiene en el 3T de 2024.

    No es "no hay dato": hay sesenta y tres trimestres y se acaban en una fecha.
    La diferencia es lo que separa un hueco que se puede llenar de uno que no.
    """
    fechas = pd.date_range("2010-03-31", "2024-09-30", freq="QE")
    panel = _panel_con(pd.DataFrame({"gasto_intereses": 1.0}, index=fechas))
    diag = diagnostico_de_insumos(panel).set_index("insumo")

    assert diag.loc["gasto_intereses", "estado"] == "rezagado"
    assert diag.loc["gasto_intereses", "ultima_fecha"] == dt.date(2024, 9, 30)
    assert "EBITDAre" in diag.loc["gasto_intereses", "sin_el_no_hay"]


def test_una_serie_vigente_se_marca_completa():
    fechas = pd.date_range("2020-03-31", "2026-06-30", freq="QE")
    panel = _panel_con(pd.DataFrame({"gasto_intereses": 1.0}, index=fechas))
    diag = diagnostico_de_insumos(panel).set_index("insumo")
    assert diag.loc["gasto_intereses", "estado"] == "completo"


def test_un_insumo_que_nunca_estuvo_se_marca_ausente():
    panel = _panel_con(pd.DataFrame({"utilidad_neta": [1.0]},
                                    index=pd.to_datetime(["2026-06-30"])))
    diag = diagnostico_de_insumos(panel).set_index("insumo")
    assert diag.loc["gasto_intereses", "estado"] == "ausente"
    assert diag.loc["gasto_intereses", "trimestres"] == 0


def test_el_diagnostico_cubre_los_insumos_que_sostienen_la_puerta_1():
    """Si mañana se agrega un insumo crítico, tiene que aparecer aquí también."""
    panel = _panel_con(pd.DataFrame())
    diag = diagnostico_de_insumos(panel)
    assert set(diag["insumo"]) == {clave for clave, _ in INSUMOS_CRITICOS}
    assert (diag["estado"] == "ausente").all()


# --------------------------------------------------------------------------------------
# 26.6 · El yield de adquisiciones es un supuesto POR SECTOR, no uno para todos
# --------------------------------------------------------------------------------------


def test_el_yield_de_adquisiciones_por_omision_es_el_del_sector():
    """Sin supuesto, `spread_inversion` salía nulo para las DIEZ emisoras.

    Nadie publica el cap rate de sus adquisiciones, así que hay que suponerlo. El
    supuesto es el cap rate base de SU sector —el mismo con el que se arma el
    NAV—, y no un número único: un industrial compra cerca de 5.5% y una oficina
    arriba de 8.75%, y aplicarles el mismo número mete el sesgo del sector en un
    criterio binario.
    """
    import inspect

    from src import servicio

    codigo = inspect.getsource(servicio.construir_panel)
    assert "rango_cap_rate(sector)" in codigo, (
        "el yield de adquisiciones dejó de tomar el cap rate del sector"
    )
    assert CAP_RATE_POR_SECTOR["Industrial"][1] != CAP_RATE_POR_SECTOR["Oficinas"][1], (
        "el control no aplica: los dos sectores tendrían el mismo supuesto"
    )
