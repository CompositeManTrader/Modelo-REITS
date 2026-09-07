"""Prueba 22 — Siete defectos de la pantalla de Portafolio.

Cuatro daban un número equivocado y tres lo escondían o lo confundían. Los cuatro
primeros comparten una firma que este proyecto ya conoce: **cifras internamente
consistentes que responden a otra pregunta.** Ninguno levanta excepción.

1. **La atribución a 1/100.** La columna ``aporte`` no caía en la familia de
   porcentaje, así que no se escalaba, y la página le pasaba un formato ``%%``
   encima del decimal crudo: Agree Realty aparecía creciendo su AFFO **0.08%**
   donde creció 7.6%. El pie de la tabla lo admitía —"multiplica por 100
   mentalmente"— y remitía a una gráfica que no existe en esa sección.

2. **El ingreso que no era el tuyo.** "Ingreso en términos reales" leía la tabla
   de dividendos del MERCADO y sumaba el monto POR ACCIÓN de cada emisora en
   cartera. Sumar 0.269 de Realty Income con 1.03 de Prologis da un número que no
   es dinero ni tasa, y que sale idéntico con diez mil títulos de una que con uno.

3. **Los años a medias.** La misma sección agrupaba por año calendario sin exigir
   que el año estuviera completo, y el crecimiento anualizado se calculaba entre
   dos muñones: el primer año suele empezar a mitad y el último es el año en curso.

4. **El trimestre por cuatro.** La atribución anualizaba UN trimestre en vez de
   sumar cuatro. En NNN eso reporta un crecimiento de AFFO de +5.88% donde el TTM
   da +3.55%, y mueve el cambio de múltiplo de −2.77% a −0.58% — el término que
   dice cuánto del retorno fue prestado.

5. **El dinero sin forma de dinero.** ``ganancia_no_realizada`` no caía en la
   familia de moneda, así que en la tabla de posiciones convivían un costo total
   de "$24,000.00" y una ganancia de "1,417", en columnas contiguas.

6. **El cero dibujado como hueco.** ``pct(v) if v else "—"`` convierte un 0.00%
   real en un guion de dato faltante. Es el inverso del principio de la casa: aquí
   un dato que existe se presenta como ausente, y justo el 0% es el hallazgo.

7. **La resta que la pantalla le pedía al lector.** Benchmarks publicaba una sola
   columna con renglones reales y nominales mezclados y pedía en el pie restar la
   inflación a unos sí y a otros no —teniendo el insumo de inflación capturado
   tres renglones arriba—.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ / "app") not in sys.path:
    sys.path.insert(0, str(RAIZ / "app"))

from comun import familia_de_columna, formato_columnas, pct, veces  # noqa: E402

from src.portafolio.metricas import (  # noqa: E402
    atribuir_retorno,
    crecimiento_real_anualizado,
    ingreso_anual_por_dividendos,
    suma_ttm,
)
from src.portafolio.transacciones import TipoTx  # noqa: E402

# --------------------------------------------------------------------------------------
# 22.1 La atribución a 1/100
# --------------------------------------------------------------------------------------


def test_el_aporte_de_la_atribucion_se_escala_como_porcentaje():
    """Es una fracción del retorno, y la escala la decide la familia de la columna."""
    assert familia_de_columna("aporte", pd.Series([0.076])) == "porcentaje"

    tabla = pd.DataFrame({"componente": ["Crecimiento del AFFO"], "aporte": [0.0762]})
    vista, _ = formato_columnas(tabla)
    assert vista["aporte"].iloc[0] == pytest.approx(7.62), (
        "la pantalla dibujaría 0.08% donde el emisor creció 7.6%"
    )


def test_la_atribucion_completa_se_dibuja_en_puntos_porcentuales():
    """Contra la descomposición real de Agree Realty, no contra una maqueta."""
    atribucion = atribuir_retorno(
        precio_inicial=66.0, precio_final=72.62,
        affo_por_accion_inicial=4.19, affo_por_accion_final=4.49,
        dividendos_cobrados_por_accion=3.10,
    )
    vista, _ = formato_columnas(atribucion.como_tabla())
    aportes = dict(zip(vista["componente"], vista["aporte"], strict=True))
    # Todos por encima de 1 en valor absoluto salvo el término cruzado: son puntos
    # porcentuales, no fracciones.
    assert aportes["Dividendo cobrado"] == pytest.approx(4.70, abs=0.05)
    assert aportes["Crecimiento del AFFO por acción"] == pytest.approx(7.16, abs=0.05)


# --------------------------------------------------------------------------------------
# 22.2 y 22.3 El ingreso: de quién es, y de qué años
# --------------------------------------------------------------------------------------


def _libro(anios: range, *, titulos_o: int, titulos_pld: int, meses_ultimo: int = 12):
    """Un libro con dividendos mensuales de O y trimestrales de PLD."""
    filas = [{"fecha": dt.date(min(anios), 1, 2), "ticker": "O", "tipo": TipoTx.COMPRA,
              "cantidad": titulos_o, "precio": 60.0, "comision": 0.0,
              "tipo_cambio": 18.0, "retencion_eeuu": 0.0, "nota": ""}]
    for anio in anios:
        meses = 12 if anio != max(anios) else meses_ultimo
        for m in range(1, meses + 1):
            filas.append({"fecha": dt.date(anio, m, 15), "ticker": "O",
                          "tipo": TipoTx.DIVIDENDO, "cantidad": titulos_o, "precio": 0.26,
                          "comision": 0.0, "tipo_cambio": 18.0, "retencion_eeuu": 0.0,
                          "nota": ""})
        for q in range(4 if anio != max(anios) else max(1, meses_ultimo // 3)):
            filas.append({"fecha": dt.date(anio, 3 + 3 * q, 20), "ticker": "PLD",
                          "tipo": TipoTx.DIVIDENDO, "cantidad": titulos_pld, "precio": 1.03,
                          "comision": 0.0, "tipo_cambio": 18.0, "retencion_eeuu": 0.0,
                          "nota": ""})
    return pd.DataFrame(filas)


def test_el_ingreso_depende_de_cuantos_titulos_tienes():
    """Dos carteras con las mismas emisoras y distinto tamaño no cobran lo mismo.

    Es lo que el promedio por acción de la tabla de mercado no puede ver: sumaba el
    dividendo unitario de cada emisora y daba el mismo número para las dos.
    """
    grande = ingreso_anual_por_dividendos(
        _libro(range(2022, 2025), titulos_o=1000, titulos_pld=500), hasta=dt.date(2024, 12, 31)
    )
    chica = ingreso_anual_por_dividendos(
        _libro(range(2022, 2025), titulos_o=10, titulos_pld=5), hasta=dt.date(2024, 12, 31)
    )
    assert grande.iloc[-1] == pytest.approx(chica.iloc[-1] * 100)
    # Y es dinero de verdad: 1000 títulos × 0.26 × 12 meses + 500 × 1.03 × 4 trimestres.
    assert grande.iloc[-1] == pytest.approx(1000 * 0.26 * 12 + 500 * 1.03 * 4)


def test_el_ano_en_curso_no_entra_hasta_que_cierra():
    """Un año a medias es una caída del 25% que nadie sufrió."""
    libro = _libro(range(2022, 2027), titulos_o=1000, titulos_pld=500, meses_ultimo=8)
    serie = ingreso_anual_por_dividendos(libro, hasta=dt.date(2026, 9, 7))
    assert [f.year for f in serie.index] == [2022, 2023, 2024, 2025], (
        "2026 va a la mitad y no puede compararse contra años cerrados"
    )


def test_el_primer_ano_tampoco_entra_si_empezo_a_mitad():
    """El otro muñón: la serie arranca cuando arranca el libro, no en enero."""
    libro = _libro(range(2022, 2026), titulos_o=1000, titulos_pld=500)
    libro.loc[libro.index[0], "fecha"] = dt.date(2022, 7, 1)   # se abre a mitad de 2022
    libro = libro[~((libro["fecha"].map(lambda f: f.year) == 2022)
                    & (libro["fecha"].map(lambda f: f.month) < 7))]
    serie = ingreso_anual_por_dividendos(libro, hasta=dt.date(2025, 12, 31))
    assert [f.year for f in serie.index] == [2023, 2024, 2025]


def test_los_munones_inflaban_el_crecimiento():
    """El efecto medido: con los extremos truncados el crecimiento sale de más."""
    libro = _libro(range(2022, 2027), titulos_o=1000, titulos_pld=500, meses_ultimo=8)
    inpc = pd.Series(
        [100 * 1.04 ** (a - 2021) for a in range(2021, 2027)],
        index=pd.to_datetime([f"{a}-12-31" for a in range(2021, 2027)]),
    )
    completos = ingreso_anual_por_dividendos(libro, hasta=dt.date(2026, 9, 7))
    limpio = crecimiento_real_anualizado(completos, inpc)

    # Lo que hacía la página: agrupar por año sin exigir que estuviera completo.
    tx = libro[libro["tipo"] == TipoTx.DIVIDENDO].copy()
    tx["fecha"] = pd.to_datetime(tx["fecha"])
    crudo_serie = (tx["cantidad"] * tx["precio"]).groupby(tx["fecha"].dt.year).sum()
    crudo_serie.index = pd.to_datetime([f"{a}-12-31" for a in crudo_serie.index])
    crudo = crecimiento_real_anualizado(crudo_serie, inpc)

    # El ingreso del libro es PLANO: el crecimiento honesto es cero.
    assert limpio["nominal"] == pytest.approx(0.0, abs=1e-9)
    assert crudo["nominal"] < -0.05, (
        "con el año en curso dentro, un ingreso plano aparenta desplomarse"
    )


# --------------------------------------------------------------------------------------
# 22.4 El trimestre por cuatro
# --------------------------------------------------------------------------------------


def test_suma_ttm_toma_cuatro_trimestres_y_no_uno_por_cuatro():
    trimestres = pd.Series([1.00, 1.10, 1.20, 1.30, 1.40])
    assert suma_ttm(trimestres) == pytest.approx(1.10 + 1.20 + 1.30 + 1.40)
    assert suma_ttm(trimestres, trimestres_atras=1) == pytest.approx(1.00 + 1.10 + 1.20 + 1.30)
    # Menos de cuatro trimestres no es un año: no se inventa.
    assert suma_ttm(pd.Series([1.0, 2.0, 3.0])) is None
    assert suma_ttm(trimestres, trimestres_atras=4) is None


def test_el_trimestre_por_cuatro_desplaza_la_atribucion():
    """Los ocho trimestres reales de NNN, con y sin la corrección.

    El ×4 reporta +5.88% de crecimiento del AFFO donde los cuatro trimestres dan
    +3.55%. Y el error no se queda ahí: como la identidad reparte el retorno del
    precio entre crecimiento y múltiplo, inflar uno desinfla el otro. El cambio de
    múltiplo —el término que dice cuánto del retorno fue prestado— **cambia de
    signo**: el ×4 lo reporta negativo y los cuatro trimestres, positivo.
    """
    nnn = pd.Series([0.84, 0.82, 0.87, 0.85, 0.86, 0.87, 0.87, 0.90])
    p0, p1 = 40.0, 42.0

    por_cuatro = atribuir_retorno(p0, p1, float(nnn.iloc[-5]) * 4, float(nnn.iloc[-1]) * 4, 0.0)
    ttm = atribuir_retorno(p0, p1, suma_ttm(nnn, trimestres_atras=4), suma_ttm(nnn), 0.0)

    assert por_cuatro.crecimiento_affo == pytest.approx(0.0588, abs=0.0005)
    assert ttm.crecimiento_affo == pytest.approx(0.0355, abs=0.0005)
    assert por_cuatro.cambio_multiplo < 0 < ttm.cambio_multiplo

    # Los dos siguen cerrando contra el mismo retorno de precio: la identidad no se
    # rompe, solo se reparte distinto. Por eso ninguna suma delataba el error.
    for a in (por_cuatro, ttm):
        assert a.crecimiento_affo + a.cambio_multiplo + a.termino_cruzado == pytest.approx(
            a.retorno_precio
        )


# --------------------------------------------------------------------------------------
# 22.5 El dinero con forma de dinero
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "columna",
    ["ganancia_no_realizada", "ganancia_realizada", "dividendos_cobrados",
     "costo_total", "valor_mercado", "precio"],
)
def test_toda_columna_de_dinero_de_la_tabla_de_posiciones_es_moneda(columna):
    """En la misma tabla no pueden convivir "$24,000.00" y "1,417"."""
    assert familia_de_columna(columna, pd.Series([1417.0])) == "moneda"


def test_la_tabla_de_posiciones_no_mezcla_formatos_de_dinero():
    """Control sobre la tabla completa, con las columnas que no son dinero incluidas."""
    tabla = pd.DataFrame({
        "ticker": ["ADC"], "cantidad": [350.0], "costo_total": [24_000.0],
        "valor_mercado": [25_417.0], "ganancia_no_realizada": [1_417.0],
        "ganancia_no_realizada_pct": [0.059], "dividendos_cobrados": [4_900.0],
        "peso": [0.31],
    })
    _, config = formato_columnas(tabla)
    formatos = {c: getattr(config[c], "format", None) for c in config}
    dinero = {"costo_total", "valor_mercado", "ganancia_no_realizada", "dividendos_cobrados"}
    assert len({formatos[c] for c in dinero}) == 1, f"formatos distintos para dinero: {formatos}"
    # Y los porcentajes siguen siendo porcentajes.
    assert familia_de_columna("ganancia_no_realizada_pct", tabla["ganancia_no_realizada_pct"]) == (
        "porcentaje"
    )


# --------------------------------------------------------------------------------------
# 22.6 El cero es un dato
# --------------------------------------------------------------------------------------


def test_un_cero_real_se_dibuja_como_cero():
    """`pct` y `veces` ya distinguen el hueco del cero; la guardia extra los confundía."""
    assert pct(0.0) == "0.00%"
    assert veces(0.0) == "0.00x"
    assert pct(None) == "—"
    assert veces(None) == "—"
    # La forma que tenía la página convertía el cero en hueco.
    assert (pct(0.0) if 0.0 else "—") == "—"


# --------------------------------------------------------------------------------------
# 22.7 La concordancia del conteo
# --------------------------------------------------------------------------------------


def test_el_conteo_concuerda_con_su_sustantivo():
    """"139 transacciones efectivos" era el texto que salía en pantalla."""
    from unittest.mock import patch

    import comun

    capturado: list[str] = []
    with patch.object(comun.st, "caption", lambda t: capturado.append(t)):
        comun.suficiencia(139, "transacciones")
        comun.suficiencia(139, "episodios")
    assert "transacciones efectivas" in capturado[0]
    assert "episodios efectivos" in capturado[1]
