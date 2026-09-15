"""Prueba 49 — Dos ceros y dos fechas que no querían decir lo que parecía.

Tres errores que la verificación de estados reportaba, y que resultaron ser dos
cosas distintas: uno era una regla demasiado estricta, los otros dos un defecto
en el XBRL del propio emisor.

1 · El cero de Global Net Lease NO era un error
------------------------------------------------
GNL reportó ingresos de CERO en los tres primeros trimestres de 2012, y es
verdad: era una REIT no listada recién formada —su primer filing es de mayo de
ese año— que todavía no compraba un solo inmueble. La regla exigía que los
ingresos totales fueran siempre positivos y ahí no detectaba un error, lo
inventaba.

El cero no significa lo mismo en los dos extremos de la historia. Antes de la
primera cifra positiva es historia; después es un hueco, porque una empresa que
ya cobró renta no deja de cobrarla de golpe y lo que casi siempre hay detrás es
un renglón que el catálogo dejó de encontrar.

2 · Las fechas de Prologis y Welltower SÍ lo eran, pero no eran nuestras
------------------------------------------------------------------------
El 10-Q de Welltower del primer trimestre de 2013 declara ``Assets =
19,549,109,000`` dos veces: con fecha 2012-12-31, que es el cierre comparativo y
es correcta, y con fecha 2012-03-31, que no. En marzo de 2012 su activo total
fue 15,859,734,000, como lo dijo su propio 10-Q de entonces. Prologis tiene el
mismo defecto en 2017. Se verificó contra ``companyfacts``: viene así de la SEC,
que lo pasa tal cual porque así lo etiquetó el emisor.

El modelo se lo creía porque P1 manda tomar la versión más reciente, y eso es
correcto para una serie. Pero un balance es una IDENTIDAD, y esa igualdad solo
existe dentro de un filing: al tomar el activo de una cosecha y el pasivo de
otra, se rompe sin que ninguna cifra esté mal por su cuenta. No se debilita P1;
se usa la contabilidad como evidencia sobre cuál cosecha describe al periodo.

Por qué la regla es estrecha, y cómo se supo
---------------------------------------------
Se midió antes de escribirla: el patrón —mismo valor, dos fechas, un mismo
filing— aparece en DOS celdas del universo, y las dos están mal. Cero falsos
positivos. Una regla más ancha ya se había rechazado antes en este proyecto por
disparar sobre reexpresiones legítimas; la diferencia aquí es que la identidad
contable decide, no una heurística de tamaño.
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
from src.validacion.estados import ERROR, verificar_signos  # noqa: E402
from src.validacion.fechado import detectar_mal_fechados  # noqa: E402

HOY = dt.date.today()


def estado_con(ingresos: dict[dt.date, float | None]) -> pd.DataFrame:
    """Un estado de resultados con una sola línea, en el orden real de columnas.

    Las columnas van del periodo MÁS RECIENTE al más antiguo, como las arma el
    modelo. No es un detalle: la regla del cero depende de qué vino antes, y
    recorrer las columnas tal como llegan pone el primer trimestre de la emisora
    al final. Ese fue un error real de la primera versión.
    """
    return pd.DataFrame({f: {"ingresos_totales": v} for f, v in sorted(ingresos.items(), reverse=True)})


# --------------------------------------------------------------------------------------
# 49.1 · El cero, según dónde caiga en la historia
# --------------------------------------------------------------------------------------


def test_cero_antes_de_la_primera_cifra_positiva_no_es_error():
    """El caso de GNL: una REIT que aún no compraba inmuebles."""
    estado = estado_con({
        dt.date(2012, 3, 31): 0.0,
        dt.date(2012, 6, 30): 0.0,
        dt.date(2012, 9, 30): 0.0,
        dt.date(2012, 12, 31): 30_000.0,
        dt.date(2013, 3, 31): 1_200_000.0,
    })
    assert verificar_signos("GNL", estado) == []


def test_cero_despues_de_operar_si_es_error():
    """Una empresa que ya cobró renta no deja de cobrarla de golpe."""
    estado = estado_con({
        dt.date(2012, 3, 31): 1_000_000.0,
        dt.date(2012, 6, 30): 0.0,
        dt.date(2012, 9, 30): 1_100_000.0,
    })
    inc = verificar_signos("X", estado)
    assert len(inc) == 1
    assert inc[0].severidad == ERROR
    assert inc[0].periodo == dt.date(2012, 6, 30)


def test_un_ingreso_negativo_siempre_es_error():
    """No depende de la historia: no existe."""
    estado = estado_con({dt.date(2012, 3, 31): -5.0, dt.date(2012, 6, 30): 10.0})
    inc = verificar_signos("X", estado)
    assert len(inc) == 1
    assert "negativo" in inc[0].detalle


def test_la_regla_se_evalua_en_orden_cronologico():
    """La regresión de la primera versión, y por qué no se veía.

    Las columnas llegan con el periodo más reciente primero. Recorrerlas tal cual
    hacía que al llegar al primer trimestre de la emisora ya se hubieran visto
    cifras positivas de años POSTERIORES, así que su cero de arranque se reportaba
    como el hueco que no es. El resultado se veía idéntico —tres errores en GNL—,
    solo cambiaba el texto del mensaje.
    """
    estado = estado_con({
        dt.date(2012, 3, 31): 0.0,
        dt.date(2020, 12, 31): 500_000.0,
    })
    assert verificar_signos("GNL", estado) == [], (
        "un cero de 2012 se juzgó con lo que pasó en 2020"
    )


# --------------------------------------------------------------------------------------
# 49.2 · El saldo con la fecha de otro periodo
# --------------------------------------------------------------------------------------


def saldos(filas: list[tuple[str, str, str, float, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        filas, columns=["clave", "fecha_dato", "fecha_publicacion", "valor", "accession"]
    )


def test_detecta_el_saldo_repetido_que_contradice_el_balance():
    """El caso de Welltower, en pequeño."""
    hallazgos = detectar_mal_fechados("WELL", saldos([
        # El cierre de año, donde el valor sí cuadra.
        ("activos_totales", "2012-12-31", "2013-05-07", 19_549.0, "acc-2013"),
        ("pasivo_mas_capital", "2012-12-31", "2013-05-07", 19_549.0, "acc-2013"),
        # El mismo valor pegado al primer trimestre, donde no cuadra.
        ("activos_totales", "2012-03-31", "2013-05-07", 19_549.0, "acc-2013"),
        ("activos_totales", "2012-03-31", "2012-05-10", 15_859.0, "acc-2012"),
        ("pasivo_mas_capital", "2012-03-31", "2012-05-10", 15_859.0, "acc-2012"),
    ]))
    assert len(hallazgos) == 1
    h = hallazgos[0]
    assert h.fecha_dato == "2012-03-31"
    assert h.fecha_correcta == "2012-12-31"
    assert "2012-12-31" in h.nota()


def test_una_reexpresion_de_verdad_no_se_toca():
    """Si el emisor mueve el activo Y su contraparte, la identidad se sigue cumpliendo.

    Esa es la diferencia entre corregir un dato y desconfiar de una reexpresión, y
    es lo que impide que esta regla se coma las correcciones legítimas.
    """
    assert detectar_mal_fechados("X", saldos([
        ("activos_totales", "2020-03-31", "2020-05-01", 100.0, "acc-1"),
        ("pasivo_mas_capital", "2020-03-31", "2020-05-01", 100.0, "acc-1"),
        ("activos_totales", "2020-03-31", "2021-05-01", 95.0, "acc-2"),
        ("pasivo_mas_capital", "2020-03-31", "2021-05-01", 95.0, "acc-2"),
    ])) == []


def test_un_valor_repetido_que_cuadra_en_las_dos_fechas_no_se_toca():
    """Sin contradicción no hay nada que corregir, por más que el valor se repita."""
    assert detectar_mal_fechados("X", saldos([
        ("activos_totales", "2020-03-31", "2020-05-01", 100.0, "acc-1"),
        ("pasivo_mas_capital", "2020-03-31", "2020-05-01", 100.0, "acc-1"),
        ("activos_totales", "2020-06-30", "2020-05-01", 100.0, "acc-1"),
        ("pasivo_mas_capital", "2020-06-30", "2020-05-01", 100.0, "acc-1"),
    ])) == []


def test_sin_una_fecha_que_cuadre_no_se_marca_nada():
    """No hay a dónde caer, así que marcar dejaría un hueco en vez de un dato.

    Un hueco silencioso es peor que una cifra que no cuadra y lo dice: la
    verificación del balance sigue reportándola, y alguien la mira.
    """
    assert detectar_mal_fechados("X", saldos([
        ("activos_totales", "2020-03-31", "2021-05-01", 100.0, "acc-2"),
        ("pasivo_mas_capital", "2020-03-31", "2020-05-01", 80.0, "acc-1"),
        ("activos_totales", "2020-12-31", "2021-05-01", 100.0, "acc-2"),
        ("pasivo_mas_capital", "2020-12-31", "2021-02-01", 90.0, "acc-1"),
    ])) == []


def test_el_capital_temporal_entra_en_la_contraparte():
    """Sin él, Welltower se escapaba.

    A Welltower le faltan 34.6 MM de participaciones redimibles entre el pasivo y
    el capital. Sumando solo esas dos, la desviación quedaba en 0.18% —arriba de
    la tolerancia— y el detector se abstenía de un caso que sí estaba mal. El
    total que declara el emisor manda; la suma de partes es el respaldo, y solo
    sirve si está completa.
    """
    filas = [
        ("activos_totales", "2012-12-31", "2013-05-07", 19_549.0, "acc"),
        ("pasivos_totales", "2012-12-31", "2013-05-07", 8_994.0, "acc"),
        ("capital_total", "2012-12-31", "2013-05-07", 10_520.0, "acc"),
        ("capital_temporal", "2012-12-31", "2013-05-07", 35.0, "acc"),
        ("activos_totales", "2012-03-31", "2013-05-07", 19_549.0, "acc"),
        ("pasivos_totales", "2012-03-31", "2012-05-10", 7_271.0, "acc0"),
        ("capital_total", "2012-03-31", "2012-05-10", 8_554.0, "acc0"),
    ]
    assert len(detectar_mal_fechados("WELL", saldos(filas))) == 1
    sin_temporal = [f for f in filas if f[0] != "capital_temporal"]
    assert detectar_mal_fechados("WELL", saldos(sin_temporal)) == [], (
        "si esto detecta algo, la prueba dejó de medir lo que dice"
    )


# --------------------------------------------------------------------------------------
# 49.3 · Sobre las diez emisoras
# --------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def repo():
    r = Repositorio()
    if r.hechos(asof=HOY, tickers="O", conceptos=["activos_totales"]).empty:
        pytest.skip("No hay base cargada.")
    return r


def test_ninguna_emisora_tiene_un_activo_que_contradiga_su_balance(repo):
    """El piso medido: después de marcar, ninguna celda vigente rompe la identidad."""
    rotos = []
    for e in UNIVERSO_INICIAL:
        h = repo.hechos(
            asof=HOY, tickers=e.ticker, periodo_tipo="PUNTUAL",
            conceptos=["activos_totales", "pasivo_mas_capital"],
        )
        if h.empty:
            continue
        ancho = h.pivot_table(index="fecha_dato", columns="concepto", values="valor")
        if not {"activos_totales", "pasivo_mas_capital"} <= set(ancho.columns):
            continue
        par = ancho.dropna()
        desvio = (par["activos_totales"] - par["pasivo_mas_capital"]).abs() / par["activos_totales"].abs()
        for fecha in par.index[desvio > 0.0005]:
            rotos.append(f"{e.ticker} {fecha:%Y-%m-%d}: {desvio[fecha]:.2%}")
    assert rotos == [], "activos que contradicen el pasivo+capital declarado:\n" + "\n".join(rotos)


def test_los_dos_saldos_conocidos_quedaron_en_su_version_buena(repo):
    """Las cifras exactas, para que nadie tenga que volver a buscarlas."""
    for ticker, fecha, esperado in (
        ("PLD", dt.date(2017, 3, 31), 29_814_958_000),
        ("WELL", dt.date(2012, 3, 31), 15_859_734_000),
    ):
        h = repo.hechos(asof=HOY, tickers=ticker, conceptos=["activos_totales"])
        fila = h[h["fecha_dato"] == pd.Timestamp(fecha)]
        if fila.empty:
            pytest.skip(f"No hay activos de {ticker}.")
        assert float(fila["valor"].iloc[0]) == pytest.approx(esperado), (
            f"{ticker} {fecha} volvió a tomar el saldo con la fecha de otro periodo"
        )
