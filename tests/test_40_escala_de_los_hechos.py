"""Prueba 40 — Hechos publicados en la escala equivocada.

Qué se encontró
---------------
Mostrar TODA la historia —lo que trajo la prueba 39— dejó a la vista un margen
operativo de **62,787%** en Agree Realty. No era un error de cálculo: era el dato.
Su 10-K de 2013 etiquetó los cuatro trimestres de 2011 y 2012 con la cifra que
imprimió —el estado venía «in thousands»— sin volverla a dólares. Entró un
ingreso trimestral de **8,151 dólares** donde son 8,151,000, con unidad ``USD``,
fuente primaria y filing que lo respalda. Nada truena.

No es un caso aislado. En el universo actual hay **52 hechos** así: los ocho
trimestres del estado de resultados de ADC, el conteo de acciones de NNN en tres
filings —174 mil millones de acciones para una emisora que tiene 175 millones—,
la deuda de Prologis de dos cortes de 2012 y su escalera de vencimientos, y la
deuda de ADC de junio de 2020, que salía **847 veces** su pasivo total.

Por qué es difícil
------------------
La regla ingenua —«este número es mil veces más chico que sus vecinos»— marca
tres cosas que están bien:

* **El crecimiento.** Global Net Lease facturaba 245 mil dólares por semestre en
  2013 y 245 millones en 2016. Ese mil es real.
* **El flujo casi nulo.** Agree Realty emitió 150 mil dólares de acciones en el
  primer trimestre de 2017, entre trimestres de 100 millones. También es real.
* **El saldo volátil.** El efectivo de NNN va de 1.1 a 607 millones sin que nada
  esté mal.

De ahí las tres condiciones que se exigen a la vez —serie apretada, moda
atestiguada de los dos lados, y desvío acompañado por otro renglón del mismo
filing o por una identidad contable que la corrección restaura—. Cada una de
estas pruebas fija una de ellas contra el caso real que la obligó.

Qué se hace con el hecho
------------------------
Se **marca**, no se corrige. Multiplicar por mil daría un número que no aparece
en ningún filing. Y marcar tiene un efecto que corregir no tendría: la consulta
filtra por estado ANTES de elegir la versión vigente, así que la celda cae sola a
la versión anterior cuando existe —una observación de verdad— y queda vacía
cuando no. El ingreso de ADC del primer trimestre de 2011 vuelve a ser 9,209,438,
que es lo que dijo su 10-Q; el del cuarto trimestre queda en blanco, porque nadie
lo publicó bien.
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

from src.config import Estado  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402
from src.servicio import panel_de_conceptos, ratios_propios  # noqa: E402
from src.validacion.escala import (  # noqa: E402
    FRACCION_MODA,
    POTENCIAS,
    detectar_fuera_de_escala,
)

HOY = dt.date.today()


def _hechos(filas: list[dict]) -> pd.DataFrame:
    """Una tabla de hechos mínima, con las columnas que el detector lee."""
    base = {
        "ticker": "X", "concepto": "ingresos_totales", "periodo_tipo": "Q",
        "unidad": "USD", "fuente": "SEC-XBRL", "accession": "acc-1",
    }
    completas = []
    for i, f in enumerate(filas):
        fila = dict(base, **f)
        fila.setdefault("id", i + 1)
        fila["fecha_dato"] = pd.Timestamp(fila["fecha_dato"])
        fila.setdefault("fecha_publicacion", fila["fecha_dato"] + pd.Timedelta(days=40))
        fila["fecha_publicacion"] = pd.Timestamp(fila["fecha_publicacion"])
        completas.append(fila)
    return pd.DataFrame(completas)


def _trimestres(n: int, valor: float, desde: str = "2015-03-31") -> list[dict]:
    fechas = pd.date_range(desde, periods=n, freq="QE")
    return [{"fecha_dato": f, "valor": valor * (1 + 0.01 * i), "id": 100 + i}
            for i, f in enumerate(fechas)]


# --------------------------------------------------------------------------------------
# 40.1 · El caso que lo destapó
# --------------------------------------------------------------------------------------


def test_un_renglon_en_miles_dentro_de_un_filing_en_dolares_se_marca():
    """El 10-K de 2013 de Agree Realty, reducido a lo esencial.

    Dos conceptos del MISMO filing y el MISMO corte, los dos mil veces por
    debajo de su serie. Es el testigo que convierte una sospecha en un hallazgo.
    """
    filas = _trimestres(12, 9_000_000.0)
    filas += [
        {"fecha_dato": "2016-03-31", "valor": 9_045.0, "id": 1,
         "fecha_publicacion": "2018-03-11", "accession": "10-K-2018"},
        {"fecha_dato": "2016-03-31", "concepto": "utilidad_neta", "valor": 4_700.0,
         "id": 2, "fecha_publicacion": "2018-03-11", "accession": "10-K-2018"},
    ]
    filas += [{"fecha_dato": f, "concepto": "utilidad_neta", "valor": 4_700_000.0,
               "id": 200 + i} for i, f in enumerate(pd.date_range("2015-03-31", periods=12, freq="QE"))]
    hallazgos = detectar_fuera_de_escala(_hechos(filas))
    marcados = {(h.concepto, h.id) for h in hallazgos}
    assert (("ingresos_totales", 1) in marcados
            and ("utilidad_neta", 2) in marcados), marcados
    assert all(h.desvio == -3 for h in hallazgos)
    assert all(h.factor == pytest.approx(1000.0) for h in hallazgos)


def test_la_nota_dice_qué_se_vio_y_qué_no_se_hizo():
    """Un hecho marcado sin explicación es un dato que desapareció."""
    filas = _trimestres(12, 9_000_000.0)
    filas += [
        {"fecha_dato": "2016-03-31", "valor": 9_045.0, "id": 1, "accession": "K"},
        {"fecha_dato": "2016-03-31", "concepto": "utilidad_neta", "valor": 4_700.0,
         "id": 2, "accession": "K"},
    ]
    filas += [{"fecha_dato": f, "concepto": "utilidad_neta", "valor": 4_700_000.0,
               "id": 200 + i} for i, f in enumerate(pd.date_range("2015-03-31", periods=12, freq="QE"))]
    nota = detectar_fuera_de_escala(_hechos(filas))[0].nota()
    assert "mil veces por debajo" in nota
    assert "No se corrige el número" in nota
    assert "Testigos" in nota


# --------------------------------------------------------------------------------------
# 40.2 · Las tres cosas que están bien y no se pueden marcar
# --------------------------------------------------------------------------------------


def test_un_crecimiento_de_mil_veces_no_es_una_escala_rota():
    """Global Net Lease: 245 mil por semestre en 2013, 245 millones en 2016.

    La moda de la serie solo está atestiguada DESPUÉS. Un crecimiento tiene un
    solo lado; una anomalía tiene dos.
    """
    fechas = pd.date_range("2013-03-31", periods=14, freq="QE")
    filas = [{"fecha_dato": f, "valor": 245_000.0 if i < 4 else 245_000_000.0,
              "id": 300 + i, "concepto": "ingresos_totales"}
             for i, f in enumerate(fechas)]
    filas += [{"fecha_dato": f, "valor": 100_000.0 if i < 4 else 100_000_000.0,
               "id": 400 + i, "concepto": "gastos_totales"}
              for i, f in enumerate(fechas)]
    assert detectar_fuera_de_escala(_hechos(filas)) == []


def test_los_primeros_trimestres_de_una_emisora_no_son_una_escala_rota():
    """El caso que aísla la exigencia de moda a los DOS lados.

    Aquí la serie sí está apretada —doce de catorce cortes en la misma década—,
    así que la primera condición pasa y no protege a nadie. Lo que protege es que
    la moda de la serie solo esté atestiguada DESPUÉS de esos dos trimestres: son
    el principio de la historia de la emisora, no un hoyo en medio de ella.

    Sin esta condición, los dos primeros trimestres de cualquier REIT que arrancó
    chico se marcan como error de la SEC. Está medido: se marcan los cuatro.
    """
    fechas = pd.date_range("2013-03-31", periods=14, freq="QE")
    filas = []
    for i, f in enumerate(fechas):
        chico = i < 2
        filas.append({"fecha_dato": f, "concepto": "ingresos_totales", "id": i + 1,
                      "valor": 245_000.0 if chico else 245_000_000.0,
                      "accession": f"a{i}"})
        filas.append({"fecha_dato": f, "concepto": "gastos_totales", "id": 100 + i,
                      "valor": 100_000.0 if chico else 100_000_000.0,
                      "accession": f"a{i}"})
    assert detectar_fuera_de_escala(_hechos(filas)) == []


def test_un_flujo_casi_nulo_no_es_una_escala_rota():
    """Agree Realty emitió 150 mil dólares de acciones en un trimestre. Es real.

    Lo que lo salva no es su tamaño: es que su serie NO está apretada. Una serie
    que va de 12 a 110 millones no puede acusar a nadie de estar mil veces mal.
    """
    valores = [110e6, 12e6, 104e6, 150e3, 108e6, 28e6, 86e6, 95e6, 40e6, 120e6]
    fechas = pd.date_range("2015-03-31", periods=len(valores), freq="QE")
    filas = [{"fecha_dato": f, "valor": v, "id": 500 + i, "concepto": "emision_acciones"}
             for i, (f, v) in enumerate(zip(fechas, valores, strict=True))]
    filas += [{"fecha_dato": f, "valor": v * 1.05, "id": 600 + i,
               "concepto": "flujo_financiamiento"}
              for i, (f, v) in enumerate(zip(fechas, valores, strict=True))]
    assert detectar_fuera_de_escala(_hechos(filas)) == []


def test_un_saldo_volatil_no_es_una_escala_rota():
    """El efectivo de NNN va de 1.1 a 607 millones sin que nada esté mal."""
    valores = [1.9e6, 607e6, 114e6, 80e6, 2.2e6, 353e6, 1.1e6, 217e6, 224e6, 294e6]
    fechas = pd.date_range("2018-03-31", periods=len(valores), freq="QE")
    filas = [{"fecha_dato": f, "valor": v, "id": 700 + i, "concepto": "efectivo",
              "periodo_tipo": "PUNTUAL"}
             for i, (f, v) in enumerate(zip(fechas, valores, strict=True))]
    assert detectar_fuera_de_escala(_hechos(filas)) == []


def test_un_desvio_que_viene_solo_no_alcanza():
    """Un renglón suelto mil veces abajo puede ser un trimestre raro.

    Quien etiqueta en miles etiqueta la SECCIÓN en miles. Sin un segundo testigo
    del mismo filing, se prefiere el falso negativo: marcar de más borra datos
    buenos, y un dato bueno borrado no deja rastro.
    """
    filas = _trimestres(12, 9_000_000.0)
    filas += [{"fecha_dato": "2016-03-31", "valor": 9_045.0, "id": 1, "accession": "K"}]
    assert detectar_fuera_de_escala(_hechos(filas)) == []


# --------------------------------------------------------------------------------------
# 40.3 · El testigo que no necesita a nadie más
# --------------------------------------------------------------------------------------


def test_la_deuda_que_no_cabe_en_el_pasivo_se_delata_sola():
    """La deuda de ADC de junio de 2020: 783,900 millones contra un pasivo de 926.

    847 veces el pasivo total del mismo corte y del mismo documento. No es una
    comparación con otros periodos: es contabilidad. La deuda cabe en el pasivo.
    """
    fechas = pd.date_range("2019-03-31", periods=8, freq="QE")
    filas = [{"fecha_dato": f, "valor": 1.0e9 + i * 5e7, "id": 800 + i,
              "concepto": "deuda_total", "periodo_tipo": "PUNTUAL",
              "accession": f"q{i}"}
             for i, f in enumerate(fechas)]
    filas += [{"fecha_dato": f, "valor": 1.3e9, "id": 900 + i,
               "concepto": "pasivos_totales", "periodo_tipo": "PUNTUAL",
               "accession": f"q{i}"}
              for i, f in enumerate(fechas)]
    # El corte roto: la deuda mil veces arriba, sola en su filing.
    filas[4]["valor"] = 1.2e12
    hallazgos = detectar_fuera_de_escala(_hechos(filas))
    assert len(hallazgos) == 1, hallazgos
    assert hallazgos[0].concepto == "deuda_total"
    assert hallazgos[0].desvio == 3
    assert "no cabe en" in hallazgos[0].nota()


# --------------------------------------------------------------------------------------
# 40.4 · El trimestre atípico, que el exponente solo no alcanza a ver
# --------------------------------------------------------------------------------------


def test_una_perdida_donde_la_serie_gana_se_mide_contra_su_otra_version():
    """La utilidad de ADC del tercer trimestre de 2011: −1,855 contra −1,855,345.

    La serie gana 4.7 millones y ese trimestre PIERDE 1.9, así que su década es
    seis y la de la serie siete: por exponente el desvío sale de cuatro y la regla
    no lo ve. Contra la otra versión de la MISMA celda sale exacto, y dos
    versiones que difieren por mil no las produce una reexpresión.
    """
    fechas = pd.date_range("2015-03-31", periods=12, freq="QE")
    filas = [{"fecha_dato": f, "valor": 4_700_000.0, "id": 1000 + i,
              "concepto": "utilidad_neta"} for i, f in enumerate(fechas)]
    filas += [{"fecha_dato": f, "valor": 9_000_000.0, "id": 1100 + i,
               "concepto": "ingresos_totales"} for i, f in enumerate(fechas)]
    corte = fechas[6]
    filas += [
        {"fecha_dato": corte, "valor": -1_855_345.0, "id": 1, "concepto": "utilidad_neta",
         "fecha_publicacion": "2016-11-01", "accession": "10-Q"},
        {"fecha_dato": corte, "valor": -1_855.0, "id": 2, "concepto": "utilidad_neta",
         "fecha_publicacion": "2018-03-11", "accession": "10-K"},
        {"fecha_dato": corte, "valor": 9_193.0, "id": 3, "concepto": "ingresos_totales",
         "fecha_publicacion": "2018-03-11", "accession": "10-K"},
    ]
    hallazgos = detectar_fuera_de_escala(_hechos(filas))
    ids = {h.id for h in hallazgos}
    assert 2 in ids, "no vio la pérdida en miles"
    assert 1 not in ids, "marcó la versión buena"


# --------------------------------------------------------------------------------------
# 40.5 · Los umbrales están escritos, no repartidos por el código
# --------------------------------------------------------------------------------------


def test_las_potencias_son_las_dos_que_un_filer_imprime():
    """Miles y millones. No hay encabezado que diga «in hundreds»."""
    assert POTENCIAS == (3, 6)
    assert 0 < FRACCION_MODA <= 1


# --------------------------------------------------------------------------------------
# 40.6 · Sobre la base real: el efecto en el modelo
# --------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def repo():
    r = Repositorio()
    if r.hechos(asof=HOY, tickers="ADC", conceptos=["ingresos_totales"]).empty:
        pytest.skip("No hay base cargada.")
    return r


def test_los_hechos_fuera_de_escala_quedan_marcados_en_la_base(repo):
    """La reparación corrió y dejó constancia de por qué."""
    todos = repo.hechos(asof=HOY, vigentes=False, incluir_sospechosos=True)
    escala = todos[todos["nota_validacion"].astype(str).str.startswith("Escala")]
    assert not escala.empty, "no hay hechos marcados por escala"
    assert set(escala["estado"]) == {Estado.SOSPECHOSO}
    assert set(escala["ticker"]) >= {"ADC", "NNN", "PLD"}


def test_la_celda_cae_a_la_version_anterior_cuando_existe(repo):
    """El ingreso de ADC del primer trimestre de 2011 vuelve a ser el de su 10-Q."""
    serie = repo.serie("ADC", "ingresos_totales", asof=HOY, periodo_tipo="Q")
    valor = serie.get(pd.Timestamp("2011-03-31"))
    assert valor == pytest.approx(9_209_438.0), valor


def test_y_queda_vacia_cuando_no_la_hay(repo):
    """El cuarto trimestre de 2011 solo se publicó mal. Un hueco es lo correcto."""
    serie = repo.serie("ADC", "ingresos_totales", asof=HOY, periodo_tipo="Q")
    assert pd.Timestamp("2011-12-31") not in serie.index or pd.isna(
        serie.get(pd.Timestamp("2011-12-31"))
    )


def test_ningun_ratio_de_la_vista_propia_es_absurdo(repo):
    """El margen de 62,787% era el síntoma. Se mide el síntoma.

    Un margen sobre ingresos no puede pasar de unas cuantas veces: si sale en
    miles por ciento, el denominador está mil veces mal.
    """
    from src.config import UNIVERSO_INICIAL

    absurdos = []
    for emisor in UNIVERSO_INICIAL:
        panel = panel_de_conceptos(repo, emisor.ticker, asof=HOY)
        if panel.empty:
            continue
        tabla = ratios_propios(panel)
        columnas = [c for c in tabla.columns
                    if c not in ("Ratio", "formato", "explicacion")]
        for _, fila in tabla.iterrows():
            if fila["formato"] != "pct":
                continue
            for columna in columnas:
                valor = fila[columna]
                if valor is not None and pd.notna(valor) and abs(float(valor)) > 10:
                    absurdos.append(
                        f"{emisor.ticker} {fila['Ratio']} {columna}: {float(valor):.1%}"
                    )
    assert absurdos == [], "ratios imposibles:\n" + "\n".join(absurdos[:10])


def test_reconstruir_la_base_desde_la_instantanea_vuelve_a_marcarlos(tmp_path):
    """En Streamlit Cloud el disco es efímero: la base se rearma en cada reinicio.

    Y se rearma desde el CRUDO versionado, que trae los hechos tal como la
    emisora los etiquetó —en miles incluidos—. Sin correr la revisión ahí también,
    el margen de Agree Realty volvía a 62,787% en cada arranque del contenedor,
    sin que nada en el repositorio hubiera cambiado.
    """
    from src.datos.almacen import leer_crudos
    from src.ingesta.instantanea import reconstruir

    if leer_crudos("ADC").empty:
        pytest.skip("No hay instantánea versionada de ADC.")
    otro = Repositorio(ruta=tmp_path / "rehecha.db")
    reconstruir(otro, tickers=["ADC"])
    todos = otro.hechos(asof=HOY, vigentes=False, incluir_sospechosos=True)
    escala = todos[todos["nota_validacion"].astype(str).str.startswith("Escala")]
    assert not escala.empty, "la base reconstruida trae los hechos sin marcar"
    serie = otro.serie("ADC", "ingresos_totales", asof=HOY, periodo_tipo="Q")
    assert serie.get(pd.Timestamp("2011-03-31")) == pytest.approx(9_209_438.0)


def test_la_pantalla_puede_nombrar_lo_que_se_descarto(repo):
    """Un hueco sin nombre es un olvido disfrazado de dato faltante.

    Desde afuera se ven igual: el que mira la pantalla no tiene forma de saber si
    la emisora no reportó o si nosotros retiramos la cifra. La zona de Auditoría
    lista cada registro retirado con su periodo, el valor que traía y la razón.
    """
    from src.servicio import hechos_descartados_por_escala

    tabla = hechos_descartados_por_escala(repo, "ADC", asof=HOY)
    assert not tabla.empty
    assert list(tabla.columns) == [
        "Renglón", "Periodo", "Tipo", "Publicado", "Valor que traía",
        "Por qué se descartó",
    ]
    assert all(t.startswith("Escala") for t in tabla["Por qué se descartó"])


def test_la_deuda_nunca_excede_el_pasivo_del_mismo_corte(repo):
    """La identidad que delató a ADC, medida sobre todo el universo."""
    from src.config import UNIVERSO_INICIAL

    rotas = []
    for emisor in UNIVERSO_INICIAL:
        panel = panel_de_conceptos(repo, emisor.ticker, asof=HOY)
        if panel.empty or "deuda_total" not in panel or "pasivos_totales" not in panel:
            continue
        deuda = pd.to_numeric(panel["deuda_total"], errors="coerce")
        pasivo = pd.to_numeric(panel["pasivos_totales"], errors="coerce")
        malas = panel.index[(deuda.notna()) & (pasivo.notna()) & (deuda > pasivo * 1.005)]
        rotas += [f"{emisor.ticker} {i.date()}: {deuda[i]:,.0f} > {pasivo[i]:,.0f}"
                  for i in malas]
    assert rotas == [], "la deuda no cabe en el pasivo:\n" + "\n".join(rotas[:10])
