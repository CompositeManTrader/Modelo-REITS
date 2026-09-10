"""Prueba 41 — El vintage de los acumulados, la columna fija y las gráficas.

41.1 · Restar dos bases distintas no despeja un trimestre
--------------------------------------------------------
``Q4 = FY − 9M`` es una identidad solo si los dos números están en la misma base
contable, y tomar la última versión de cada uno —que es lo que se hacía— no lo
garantiza: garantiza lo contrario en cuanto el emisor reexpresa un lado y no el
otro.

Agree Realty reexpresó su ejercicio 2010 tres veces al sacar operaciones
discontinuadas —33.68, 30.38 y 27.42 millones— y sus nueve meses se quedaron en
los 26.55 que publicó el 10-Q de 2011. La última de cada lado daba un cuarto
trimestre de **876 mil dólares** contra los 8.8 millones de sus hermanos, y de
ahí salía un margen operativo de **−809.7%**. La aritmética era impecable; las
bases, distintas.

Ahora se elige la pareja CO-VINTAGE: la que minimiza la distancia entre fechas de
publicación, con desempate por la más reciente. El cuarto trimestre de 2010 sale
en 7.13 millones —el que se podía calcular cuando los dos números estaban
vigentes a la vez— y las reexpresiones posteriores del año no producen un
trimestre nuevo, porque nadie reexpresó los nueve meses.

Medido sobre las diez emisoras, el año cierra mejor: los desvíos de más de 1%
entre la suma de los cuatro trimestres y su ejercicio bajan de 450 a 389, y los
de más de 5% de 390 a 331.

41.2 · La columna que no se va
------------------------------
Un estado de setenta trimestres se desplaza de lado sí o sí. Sin el renglón a la
vista, en cuanto se avanzan tres columnas los números dejan de tener sujeto.

41.3 · Cuánto, y hacia dónde
----------------------------
La tabla contesta lo primero. El apartado de gráficas contesta lo segundo, y su
regla central es la unidad del CAMBIO, que no es una sola: un porcentaje se
compara por diferencia y se dice en puntos base —entre 62% y 57% hay 500 bps, no
«−8%»—, un monto se compara por razón y se dice en por ciento, y un múltiplo se
dice en veces, que es la unidad en la que está escrito el listón de 6.5x.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
for _ruta in (str(RAIZ), str(RAIZ / "app")):
    if _ruta not in sys.path:
        sys.path.insert(0, _ruta)

from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta.estados import derivar_trimestres_faltantes  # noqa: E402
from src.servicio import (  # noqa: E402
    BLOQUES_DE_GRAFICAS,
    CAMBIO_DE_UNIDAD,
    METRICAS_DE_GRAFICA,
    cambio_de_metrica,
    panel_de_conceptos,
    ratios_propios,
    series_de_graficas,
)

HOY = dt.date.today()


def _crudos(filas: list[dict]) -> pd.DataFrame:
    base = {"tag": "Revenues", "unidad": "USD", "formulario": "10-Q",
            "accession": "acc", "marco": ""}
    salida = []
    for f in filas:
        fila = dict(base, **f)
        for campo in ("fecha_inicio", "fecha_dato", "fecha_publicacion"):
            fila[campo] = pd.Timestamp(fila[campo]).date()
        salida.append(fila)
    return pd.DataFrame(salida)


# --------------------------------------------------------------------------------------
# 41.1 · El vintage de los acumulados
# --------------------------------------------------------------------------------------


def test_no_se_resta_un_ejercicio_reexpresado_de_unos_nueve_meses_que_no_lo_estan():
    """El caso de Agree Realty, reducido a lo esencial.

    Tres versiones del año y una sola de los nueve meses. La pareja correcta es
    la que se publicó junta; las reexpresiones posteriores no tienen con qué
    restarse.
    """
    filas = [
        {"fecha_inicio": "2010-01-01", "fecha_dato": "2010-09-30", "periodo_tipo": "9M",
         "fecha_publicacion": "2011-11-04", "valor": 26_545_945.0},
        {"fecha_inicio": "2010-01-01", "fecha_dato": "2010-12-31", "periodo_tipo": "FY",
         "fecha_publicacion": "2012-03-12", "valor": 33_680_751.0},
        {"fecha_inicio": "2010-01-01", "fecha_dato": "2010-12-31", "periodo_tipo": "FY",
         "fecha_publicacion": "2012-09-25", "valor": 30_384_563.0},
        {"fecha_inicio": "2010-01-01", "fecha_dato": "2010-12-31", "periodo_tipo": "FY",
         "fecha_publicacion": "2013-03-11", "valor": 27_422_234.0},
    ]
    salida = derivar_trimestres_faltantes(_crudos(filas), {"ingresos_totales": "Revenues"})
    derivados = salida[salida["formulario"] == "DERIVADO"]
    assert len(derivados) == 1, derivados
    fila = derivados.iloc[0]
    assert pd.Timestamp(fila["fecha_dato"]).date() == dt.date(2010, 12, 31)
    assert float(fila["valor"]) == pytest.approx(7_134_806.0)
    assert float(fila["valor"]) != pytest.approx(876_289.0), (
        "restó el ejercicio de 2013 contra los nueve meses de 2011"
    )


def test_la_fecha_de_publicacion_es_la_del_ultimo_componente_de_la_pareja():
    """Antes de esa fecha el número no era deducible ni con lápiz (P1).

    Y es la del componente que se USÓ, no la del más reciente que existía: el
    ejercicio de 2013 no participa, así que no puede fechar nada.
    """
    filas = [
        {"fecha_inicio": "2010-01-01", "fecha_dato": "2010-09-30", "periodo_tipo": "9M",
         "fecha_publicacion": "2011-11-04", "valor": 26_545_945.0},
        {"fecha_inicio": "2010-01-01", "fecha_dato": "2010-12-31", "periodo_tipo": "FY",
         "fecha_publicacion": "2012-03-12", "valor": 33_680_751.0},
        {"fecha_inicio": "2010-01-01", "fecha_dato": "2010-12-31", "periodo_tipo": "FY",
         "fecha_publicacion": "2013-03-11", "valor": 27_422_234.0},
    ]
    salida = derivar_trimestres_faltantes(_crudos(filas), {"ingresos_totales": "Revenues"})
    fila = salida[salida["formulario"] == "DERIVADO"].iloc[0]
    assert pd.Timestamp(fila["fecha_publicacion"]).date() == dt.date(2012, 3, 12)


def test_cuando_las_dos_partes_se_reexpresan_juntas_gana_la_version_nueva():
    """Dos parejas igual de co-vintage: manda la información más actual.

    Es el caso sano —el emisor reexpresa el acumulado Y el tramo en el mismo
    ciclo— y ahí no hay razón para quedarse con la versión vieja.
    """
    filas = [
        {"fecha_inicio": "2020-01-01", "fecha_dato": "2020-06-30", "periodo_tipo": "H1",
         "fecha_publicacion": "2020-08-03", "valor": 100.0},
        {"fecha_inicio": "2020-01-01", "fecha_dato": "2020-03-31", "periodo_tipo": "Q",
         "fecha_publicacion": "2020-05-04", "valor": 40.0},
        {"fecha_inicio": "2020-01-01", "fecha_dato": "2020-06-30", "periodo_tipo": "H1",
         "fecha_publicacion": "2021-08-03", "valor": 130.0},
        {"fecha_inicio": "2020-01-01", "fecha_dato": "2020-03-31", "periodo_tipo": "Q",
         "fecha_publicacion": "2021-05-04", "valor": 55.0},
    ]
    salida = derivar_trimestres_faltantes(_crudos(filas), {"ingresos_totales": "Revenues"})
    fila = salida[salida["formulario"] == "DERIVADO"].iloc[0]
    assert float(fila["valor"]) == pytest.approx(75.0), "no tomó la pareja de 2021"
    assert pd.Timestamp(fila["fecha_publicacion"]).date() == dt.date(2021, 8, 3)


def test_con_una_sola_version_de_cada_lado_no_cambia_nada():
    """El caso normal. Una regla que altere lo que ya estaba bien no sirve."""
    filas = [
        {"fecha_inicio": "2020-01-01", "fecha_dato": "2020-06-30", "periodo_tipo": "H1",
         "fecha_publicacion": "2020-08-03", "valor": 100.0},
        {"fecha_inicio": "2020-01-01", "fecha_dato": "2020-03-31", "periodo_tipo": "Q",
         "fecha_publicacion": "2020-05-04", "valor": 40.0},
    ]
    salida = derivar_trimestres_faltantes(_crudos(filas), {"ingresos_totales": "Revenues"})
    fila = salida[salida["formulario"] == "DERIVADO"].iloc[0]
    assert float(fila["valor"]) == pytest.approx(60.0)


@pytest.fixture(scope="module")
def repo():
    r = Repositorio()
    if r.hechos(asof=HOY, tickers="ADC", conceptos=["ingresos_totales"]).empty:
        pytest.skip("No hay base cargada.")
    return r


def test_sobre_la_base_real_el_cuarto_trimestre_de_2010_de_adc_es_el_bueno(repo):
    serie = repo.serie("ADC", "ingresos_totales", asof=HOY, periodo_tipo="Q")
    valor = serie.get(pd.Timestamp("2010-12-31"))
    assert valor == pytest.approx(7_134_806.0), valor


def test_ningun_margen_del_universo_pasa_de_trescientos_por_ciento(repo):
    """El síntoma que destapó los dos defectos —la escala y el vintage—.

    Se mide en 300% y no más fino a propósito: Global Net Lease facturaba 245 mil
    dólares por semestre en 2013 con dos millones de gasto, así que su margen
    operativo de −820% es real y no un artefacto. Lo que este umbral caza es el
    denominador roto, no el negocio malo.
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
            if fila["formato"] != "pct" or fila["Ratio"] in ("AFFO / FFO",):
                continue
            for columna in columnas:
                valor = fila[columna]
                if valor is not None and pd.notna(valor) and abs(float(valor)) > 9:
                    absurdos.append(
                        f"{emisor.ticker} {fila['Ratio']} {columna}: {float(valor):.0%}"
                    )
    assert absurdos == [], "márgenes imposibles:\n" + "\n".join(absurdos[:10])


# --------------------------------------------------------------------------------------
# 41.2 · La columna que no se va
# --------------------------------------------------------------------------------------


def test_la_columna_del_renglon_se_puede_anclar():
    from comun import formato_columnas

    tabla = pd.DataFrame({"Renglón": ["Ingresos"], "2026-03-31": [1.0], "2026-06-30": [2.0]})
    _, config = formato_columnas(tabla, fijar=["Renglón"])
    assert config["Renglón"]["pinned"] is True
    assert config["2026-03-31"]["pinned"] is False


def test_sin_pedirlo_ninguna_columna_se_ancla():
    """Anclar por omisión movería todas las tablas de la aplicación, no solo estas."""
    from comun import formato_columnas

    tabla = pd.DataFrame({"Renglón": ["Ingresos"], "2026-03-31": [1.0]})
    _, config = formato_columnas(tabla)
    assert all(c.get("pinned") is False for c in config.values())


# --------------------------------------------------------------------------------------
# 41.3 · Cuánto, y hacia dónde
# --------------------------------------------------------------------------------------


def test_un_porcentaje_cambia_en_puntos_base_y_un_monto_en_por_ciento():
    """La regla central del apartado, medida en las tres unidades."""
    fechas = pd.to_datetime(["2026-03-31", "2026-06-30"])
    margen = pd.Series([0.62, 0.57], index=fechas)
    valor, cambio, unidad = cambio_de_metrica(margen, "pct")
    assert (valor, unidad) == (0.57, "bps")
    assert cambio == pytest.approx(-500.0)

    monto = pd.Series([100.0, 109.0], index=fechas)
    valor, cambio, unidad = cambio_de_metrica(monto, "monto")
    assert unidad == "%" and cambio == pytest.approx(9.0)

    multiplo = pd.Series([5.26, 5.68], index=fechas)
    valor, cambio, unidad = cambio_de_metrica(multiplo, "veces")
    assert unidad == "x" and cambio == pytest.approx(0.42)


def test_un_monto_que_parte_de_cero_no_tiene_cambio_porcentual():
    """Dividir entre cero da infinito; dividir entre un negativo da un signo al revés.

    Las dos cosas se dibujan como una flecha, y una flecha equivocada es peor que
    ninguna.
    """
    fechas = pd.to_datetime(["2026-03-31", "2026-06-30"])
    for previo in (0.0, -50.0):
        _, cambio, _ = cambio_de_metrica(pd.Series([previo, 100.0], index=fechas), "monto")
        assert cambio is None, previo


def test_sin_comparable_no_se_inventa_un_cambio():
    fechas = pd.to_datetime(["2026-06-30"])
    valor, cambio, _ = cambio_de_metrica(pd.Series([0.57], index=fechas), "pct")
    assert valor == 0.57 and cambio is None
    valor, cambio, _ = cambio_de_metrica(pd.Series(dtype="float64"), "pct")
    assert valor is None and cambio is None


def test_cada_metrica_declara_una_unidad_y_un_bloque_conocidos():
    for metrica in METRICAS_DE_GRAFICA:
        assert metrica.unidad in CAMBIO_DE_UNIDAD, metrica.clave
        assert metrica.bloque in BLOQUES_DE_GRAFICAS, metrica.clave
        assert metrica.origen in ("ratio", "concepto", "insumo"), metrica.clave
        assert metrica.etiqueta and metrica.explicacion, metrica.clave


def test_las_graficas_salen_del_mismo_panel_que_la_tabla(repo):
    """Una gráfica que no cuadre con la tabla de al lado es peor que no tenerla."""
    panel = panel_de_conceptos(repo, "O", asof=HOY)
    if panel.empty:
        pytest.skip("No hay base cargada.")
    series = series_de_graficas(panel)
    assert not series.empty
    assert list(series.index) == list(panel.index)

    tabla = ratios_propios(panel)
    fila = tabla[tabla["Ratio"] == "Deuda neta / EBITDAre"].iloc[0]
    for periodo in series.index:
        de_tabla = fila.get(periodo.date().isoformat())
        de_grafica = series["apalancamiento"].get(periodo)
        if de_tabla is None or pd.isna(de_tabla):
            assert de_grafica is None or pd.isna(de_grafica), periodo
        else:
            assert de_grafica == pytest.approx(float(de_tabla)), periodo


def test_hay_metricas_de_los_tres_bloques_con_datos_reales(repo):
    panel = panel_de_conceptos(repo, "O", asof=HOY)
    if panel.empty:
        pytest.skip("No hay base cargada.")
    series = series_de_graficas(panel)
    bloques = {
        m.bloque for m in METRICAS_DE_GRAFICA
        if m.clave in series.columns and series[m.clave].notna().any()
    }
    assert bloques == set(BLOQUES_DE_GRAFICAS), bloques
