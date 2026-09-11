"""Prueba 45 — Una sola deuda total, y la ficha que la cobertura pisaba.

Esto empezó en un renglón de W. P. Carey y terminó en el mecanismo que lo elige.

EL SÍNTOMA
==========
La deuda total de W. P. Carey cae de 2,176 millones a 475 en el cuarto trimestre
de 2013, sigue en 498, luego en 250, y ahí se queda años. Su costo implícito de
la deuda llega a 79%. No es un hundimiento aislado —los vecinos concuerdan con
el nivel bajo, así que el detector de la prueba 44 no lo ve, y hace bien— sino
un nivel equivocado sostenido.

LA CAUSA
========
`LongTermDebt` significa DOS COSAS en sus filings: hasta el tercer trimestre de
2013 es el total consolidado, y desde el cuarto es un instrumento suelto. La
serie no se rompe: se reinterpreta, y parece un desapalancamiento de 88%.

`elegir_cadenas` elige por COBERTURA, y `LongTermDebt` aparece 110 veces contra
49 del total canónico —precisamente porque se usa para instrumentos sueltos—.

EL HUECO DE DISEÑO, QUE ERA MÁS GRANDE
======================================
Existe una ficha por emisora para decir «en esta emisora, la deuda total es ESTA
etiqueta». Alguien ya había escrito la de Realty Income. **La cobertura la
pisaba**, así que ese arreglo nunca surtió efecto: la llave de orden era
``(vigente, cobertura, -preferencia)`` y la ficha no entraba en ella.

La ficha es un juicio sobre ESTA emisora; la cobertura es una heurística. Una
heurística no puede pisar un juicio explícito. La vigencia sí sigue mandando
sobre la ficha, y a propósito: una etiqueta que la emisora dejó de reportar no
puede ganar por estar escrita.

Y TRES DEFINICIONES DE LA MISMA COSA
====================================
Al medirlo apareció que la deuda total se calculaba en tres lugares y solo uno
estaba corregido por tramos:

* `saldos_de_balance` → el MODELO. Correcto: 30,652 millones de Realty Income.
* `panel_de_conceptos` → los ratios y las GRÁFICAS. Imprimía 25,092.
* `estado_financiero` → la TABLA y el libro de EXCEL. Imprimía 25,092.

Extra Space imprimía 5,410 donde el modelo usa 13,647, y Global Net Lease
imprimía CERO donde el modelo usa 2,400, porque no publica ningún renglón de
deuda junta. La pantalla y el modelo daban números distintos para el mismo
renglón, al mismo tiempo.

La prueba 39 —que recalcula el libro con LibreOffice y lo compara contra
Python— fue la que cazó la tercera. Por eso aquí se prueban los tres caminos y
no uno.

LA GUARDA QUE FALTABA
=====================
Aplicar la suma de tramos a TODA la historia hace daño hacia atrás: a Realty
Income le faltan sus notas senior en 2017 y 2018, y la suma daba 698 millones
donde debía unos 6,000. La receta es el conjunto de tramos del corte más
reciente, y un periodo al que le falte uno no recibe número: un hueco es
honesto, una cifra menor de la real dibuja al emisor más sano de lo que está.
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
from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta.estados import (  # noqa: E402
    FICHAS_ESTADOS,
    VENTANA_DE_VIGENCIA,
    elegir_cadenas,
)
from src.servicio import (  # noqa: E402
    TRAMOS_DE_DEUDA,
    deuda_corregida,
    deuda_por_periodo,
    estado_financiero,
    panel_de_conceptos,
    saldos_de_balance,
)

HOY = dt.date.today()


@pytest.fixture(scope="module")
def repo():
    r = Repositorio()
    if r.hechos(asof=HOY, tickers="O", conceptos=["ingresos_totales"]).empty:
        pytest.skip("No hay base cargada.")
    return r


def _deuda_del_estado(repo, ticker: str) -> float:
    tabla = estado_financiero(repo, ticker, "balance", asof=HOY, periodo_tipo="Q")
    if tabla.empty:
        return float("nan")
    fila = tabla[tabla["Renglón"].str.contains("Deuda total", na=False)]
    return float(fila.iloc[0, -1]) if not fila.empty else float("nan")


# --------------------------------------------------------------------------------------
# 45.1 · La ficha le gana a la cobertura
# --------------------------------------------------------------------------------------


def test_ninguna_ficha_queda_pisada_por_la_cobertura():
    """El invariante que habría cazado el arreglo que nunca surtió efecto.

    Una ficha escrita y no aplicada es peor que no tenerla: alguien la escribió
    creyendo que arreglaba algo, y el defecto siguió ahí sin dejar rastro.
    """
    pisadas = []
    for e in UNIVERSO_INICIAL:
        ficha = FICHAS_ESTADOS.get(e.ticker)
        if not ficha or not ficha.tags:
            continue
        crudos = leer_crudos(e.ticker)
        if crudos.empty:
            continue
        cadenas = elegir_cadenas(crudos, e.ticker)
        ultima = crudos.groupby("tag")["fecha_dato"].max()
        corte = pd.Timestamp(ultima.max()) - VENTANA_DE_VIGENCIA
        for clave, propias in ficha.tags.items():
            elegida = cadenas.get(clave)
            if not elegida:
                continue
            # Solo cuenta si alguna etiqueta de la ficha está VIGENTE. Nombrar una
            # que la emisora no publica —o que dejó de publicar— no puede obligar
            # a nada: la ficha le gana a la cobertura, pero no a la vigencia, o el
            # renglón se quedaría sin los trimestres recientes. Es el caso de
            # Realty Income, cuya ficha nombra `LongTermDebt`, que abandonó en
            # 2017; su deuda la resuelve la suma de tramos, no la etiqueta.
            vivas = [t for t in propias if t in ultima.index and pd.Timestamp(ultima[t]) >= corte]
            if not vivas:
                continue
            if elegida[0] not in propias:
                pisadas.append(f"{e.ticker}/{clave}: ficha={propias} → eligió {elegida[0]}")
    assert pisadas == [], "la cobertura sigue pisando una ficha:\n" + "\n".join(pisadas)


def test_wpc_usa_el_total_canonico_y_no_el_instrumento_suelto():
    """`LongTermDebt` significa dos cosas distintas en sus filings."""
    crudos = leer_crudos("WPC")
    if crudos.empty:
        pytest.skip("No hay crudos de WPC.")
    cadena = elegir_cadenas(crudos, "WPC").get("deuda_total")
    assert cadena is not None
    assert cadena[0] == "DebtLongtermAndShorttermCombinedAmount"
    assert "LongTermDebt" not in cadena


def test_wpc_no_tiene_el_quiebre_de_2013(repo):
    """Un desapalancamiento de 88% que nunca ocurrió."""
    panel = panel_de_conceptos(repo, "WPC", asof=HOY, periodo_tipo="Q", n_periodos=None)
    if panel.empty or "deuda_total" not in panel:
        pytest.skip("No hay base de WPC.")
    serie = panel["deuda_total"].dropna()
    despues = serie[serie.index >= pd.Timestamp("2014-01-01")]
    assert not despues.empty
    assert despues.min() > 1_000_000_000, (
        f"la deuda de WPC vuelve a caer a {despues.min():,.0f} después de 2013"
    )


# --------------------------------------------------------------------------------------
# 45.2 · Una sola deuda, en los tres caminos
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("ticker", [e.ticker for e in UNIVERSO_INICIAL])
def test_el_modelo_el_panel_y_la_tabla_dicen_la_misma_deuda(repo, ticker):
    """Tres números distintos para el mismo renglón, en la misma pantalla."""
    modelo = saldos_de_balance(repo, ticker, asof=HOY).get("deuda_total")
    if modelo is None or not modelo:
        pytest.skip(f"{ticker} no tiene deuda en el modelo.")
    panel = panel_de_conceptos(repo, ticker, asof=HOY, periodo_tipo="Q", n_periodos=None)
    if panel.empty or "deuda_total" not in panel or not panel["deuda_total"].notna().any():
        pytest.skip(f"{ticker} no tiene deuda en el panel.")
    del_panel = float(panel["deuda_total"].dropna().iloc[-1])
    del_estado = _deuda_del_estado(repo, ticker)

    assert del_panel == pytest.approx(modelo, rel=0.02), (
        f"{ticker}: el panel dice {del_panel:,.0f} y el modelo {modelo:,.0f}"
    )
    assert del_estado == pytest.approx(modelo, rel=0.02), (
        f"{ticker}: la tabla dice {del_estado:,.0f} y el modelo {modelo:,.0f}"
    )


def test_gnl_deja_de_imprimir_cero(repo):
    """No publica ningún renglón de deuda junta: sin sumar tramos no hay número."""
    panel = panel_de_conceptos(repo, "GNL", asof=HOY, periodo_tipo="Q", n_periodos=None)
    if panel.empty:
        pytest.skip("No hay base de GNL.")
    serie = panel.get("deuda_total")
    assert serie is not None and serie.notna().any()
    assert float(serie.dropna().iloc[-1]) > 1_000_000_000


# --------------------------------------------------------------------------------------
# 45.3 · La receta: un tramo que falta es un hueco, no un número más chico
# --------------------------------------------------------------------------------------


def _marco(filas: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(filas, index=pd.DatetimeIndex(
        [dt.date(2024, 3 * i + 3, 28) for i in range(len(filas))]
    ))


def test_un_periodo_sin_todos_los_tramos_no_recibe_numero():
    """Sumar de menos dibuja al emisor más sano, que es la dirección peligrosa."""
    marco = _marco([
        {"notas_senior": 100.0, "prestamos_a_plazo": 50.0, "pasivos_totales": 1_000.0},
        {"notas_senior": None, "prestamos_a_plazo": 50.0, "pasivos_totales": 1_000.0},
        {"notas_senior": 120.0, "prestamos_a_plazo": 60.0, "pasivos_totales": 1_000.0},
    ])
    serie = deuda_por_periodo(marco)
    assert serie is not None
    assert serie.iloc[0] == pytest.approx(150.0)
    assert pd.isna(serie.iloc[1]), "compuso la deuda con un tramo faltante"
    assert serie.iloc[2] == pytest.approx(180.0)


def test_la_receta_sale_del_corte_mas_reciente():
    """Un tramo que la emisora ya no reporta no puede exigirse hacia atrás."""
    marco = _marco([
        {"notas_senior": 100.0, "deuda_hipotecaria": 20.0, "pasivos_totales": 1_000.0},
        {"notas_senior": 110.0, "deuda_hipotecaria": None, "pasivos_totales": 1_000.0},
    ])
    serie = deuda_por_periodo(marco)
    assert serie is not None
    # La receta vigente es solo `notas_senior`, así que los dos periodos la cumplen.
    assert serie.iloc[0] == pytest.approx(120.0)
    assert serie.iloc[1] == pytest.approx(110.0)


def test_la_correccion_solo_va_hacia_arriba():
    """Cada peso que suma salió de una etiqueta del propio emisor."""
    assert deuda_corregida({"deuda_total": 500.0, "notas_senior": 100.0}) is None
    assert deuda_corregida({"deuda_total": 100.0, "notas_senior": 500.0}) == pytest.approx(500.0)


def test_una_suma_que_excede_el_pasivo_no_es_deuda():
    """Es doble conteo, y entonces vale más no publicar nada."""
    assert deuda_corregida({
        "notas_senior": 900.0, "prestamos_a_plazo": 900.0, "pasivos_totales": 1_000.0,
    }) is None


def test_sin_tramos_no_hay_correccion():
    assert deuda_por_periodo(_marco([{"deuda_total": 100.0}])) is None
    assert all(t in TRAMOS_DE_DEUDA for t in ("notas_senior", "prestamos_a_plazo"))


# --------------------------------------------------------------------------------------
# 45.4 · El costo implícito de la deuda deja de ser imposible
# --------------------------------------------------------------------------------------


def test_ninguna_emisora_paga_mas_de_quince_por_ciento_por_su_deuda(repo):
    """Era el síntoma medible: 79% en W. P. Carey, sobre una deuda diez veces menor.

    Ninguna de las diez es un emisor en dificultades, y un REIT con grado de
    inversión no paga 15%. Cuando el ratio lo dice, lo que está mal es la deuda.
    """
    from src.servicio import series_de_graficas

    malos = []
    for e in UNIVERSO_INICIAL:
        panel = panel_de_conceptos(repo, e.ticker, asof=HOY, periodo_tipo="Q", n_periodos=None)
        if panel.empty:
            continue
        serie = series_de_graficas(panel).get("costo_deuda")
        if serie is None:
            continue
        fuera = serie.dropna()
        fuera = fuera[(fuera > 0.15) | (fuera < 0)]
        malos += [f"{e.ticker}@{f.date()}={v:.0%}" for f, v in fuera.items()]
    assert malos == [], f"costo implícito imposible en {malos[:6]}"
