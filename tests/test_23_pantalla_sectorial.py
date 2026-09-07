"""Prueba 23 — Ocho defectos de la pantalla Sectorial.

Ninguno de los ocho dibuja un número falso, y por eso ninguno se ve. Cuatro son la
misma falta repetida en cuatro lugares distintos: **la pantalla calla lo que no
puede calcular**. Un percentil exige doce observaciones y casi nadie las tiene
todavía, así que el ranking se queda con dos nombres, la gráfica con dos barras y
el mapa de calor *sectorial* con una sola fila —bajo una leyenda que habla de
comparar filas entre sí—. Quien lo lee no puede distinguir «falta el dato» de «ese
sector no existe» ni de «elegiste mal».

1. **El ranking sin sus ausentes.** El respaldo solo se dispara cuando el ranking
   queda ENTERAMENTE vacío. El caso normal no es ese.
2. **La comparación sin sus ausentes.** Se eligen cuatro emisoras y salen dos
   barras, sin decir cuáles faltan ni por qué.
3. **El mapa de calor sin sus sectores.**
4. **El reloj de prima sin sus sectores**, por la misma razón y sin decirlo.
5. **El trimestre más reciente, tirado por el muestreo.** El salto posicional
   arrancaba en la primera columna: con 100 columnas y paso 2 se pierde la última,
   y este gráfico existe para decir dónde estamos hoy.
6. **El mismo percentil con dos valores.** La tabla la formatea Streamlit en
   JavaScript, que en el empate redondea hacia arriba; la gráfica la formatea
   Python, que redondea al par. Con cero decimales el mismo 0.125 salía «13%» en
   una y «12%» en la otra, separadas por dos dedos de pantalla.
7. **La cuarta métrica del sector, oculta.** ``[:3]`` truncaba la lista, y net
   lease y self storage tienen cuatro.
8. **La sigla escrita como palabra.** ``.capitalize()`` dibujaba "Affo yield" y
   "Payout affo" en una herramienta donde AFFO es un término definido.
"""

from __future__ import annotations

import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
for ruta in (str(RAIZ), str(RAIZ / "app")):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from comun import etiqueta_de_columna, formato_columnas  # noqa: E402

from src.modelo.sectorial import (  # noqa: E402
    DECIMALES_PERCENTIL,
    FORMATO_PERCENTIL_TABLA,
    MIN_OBSERVACIONES_PERCENTIL,
    cobertura_del_percentil,
    cuantizar_percentil,
    huecos_del_ranking,
    metricas_especificas,
    muestrear_columnas,
    texto_percentil,
)

PAGINA = (RAIZ / "app" / "pages" / "2_Sectorial.py").read_text(encoding="utf-8")


def _panel(por_sector: dict[str, int], *, emisoras_por_sector: int = 1) -> pd.DataFrame:
    """Panel histórico con tantas fechas por sector como se pida."""
    filas = []
    for sector, n_fechas in por_sector.items():
        fechas = pd.date_range("2020-03-31", periods=n_fechas, freq="QE")
        for i in range(emisoras_por_sector):
            for f in fechas:
                filas.append(
                    {"ticker": f"{sector[:3].upper()}{i}", "sector": sector,
                     "fecha_dato": f, "prima": 0.02}
                )
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# 23.1 y 23.2  El hueco tiene nombre: quién falta en el ranking y en la comparación
# --------------------------------------------------------------------------------------


def test_el_ranking_nombra_a_las_emisoras_que_se_quedan_fuera():
    universo = pd.DataFrame({
        "ticker": ["O", "ADC", "PLD", "EXR"],
        "sector": ["Net Lease", "Net Lease", "Industrial", "Self Storage"],
        "percentil_prima": [0.82, None, None, None],
    })
    sin_historia, sectores = huecos_del_ranking(universo)
    assert sin_historia == ["ADC", "EXR", "PLD"]
    # Net Lease NO está ausente: O sí llegó, así que el sector aparece en pantalla.
    assert sectores == ["Industrial", "Self Storage"]


def test_un_sector_no_se_reporta_ausente_si_alguna_de_sus_emisoras_si_llego():
    """La diferencia entre «faltan emisoras» y «falta el sector» no es cosmética.

    Anunciar «queda fuera Net Lease» mientras la pantalla dibuja el ranking de Net
    Lease es peor que no anunciar nada: contradice lo que se ve tres renglones
    abajo.
    """
    universo = pd.DataFrame({
        "ticker": ["O", "ADC"],
        "sector": ["Net Lease", "Net Lease"],
        "percentil_prima": [0.82, None],
    })
    sin_historia, sectores = huecos_del_ranking(universo)
    assert sin_historia == ["ADC"]
    assert sectores == []


def test_sin_huecos_no_hay_nada_que_anunciar():
    universo = pd.DataFrame({
        "ticker": ["O", "PLD"], "sector": ["Net Lease", "Industrial"],
        "percentil_prima": [0.82, 0.31],
    })
    assert huecos_del_ranking(universo) == ([], [])
    assert huecos_del_ranking(pd.DataFrame()) == ([], [])


def test_la_comparacion_usa_el_mismo_hueco_que_el_ranking():
    """Sobre la SELECCIÓN, no sobre el universo: es la misma función, otro alcance."""
    seleccion = pd.DataFrame({
        "ticker": ["O", "ADC", "PLD", "EXR"],
        "sector": ["Net Lease", "Net Lease", "Industrial", "Self Storage"],
        "percentil_prima": [0.82, 0.44, None, None],
    })
    no_dibujadas, _ = huecos_del_ranking(seleccion)
    assert no_dibujadas == ["EXR", "PLD"], "se eligen cuatro y salen dos barras sin decirlo"


def test_la_pantalla_anuncia_los_dos_huecos_de_arriba():
    """Control de cableado: las funciones existen, pero tienen que estar llamadas."""
    assert PAGINA.count("huecos_del_ranking(") >= 2, (
        "el ranking y la comparación tienen que nombrar cada uno a sus ausentes"
    )


# --------------------------------------------------------------------------------------
# 23.3 y 23.4  El mapa de calor y el reloj, sin sus sectores
# --------------------------------------------------------------------------------------


def test_la_cobertura_dice_cuantas_fechas_tiene_cada_sector_y_cuantas_le_faltan():
    cobertura = cobertura_del_percentil(_panel({"Net Lease": 20, "Industrial": 8}))
    por_sector = cobertura.set_index("sector")

    assert bool(por_sector.loc["Net Lease", "alcanza"])
    assert int(por_sector.loc["Net Lease", "faltan"]) == 0
    assert not bool(por_sector.loc["Industrial", "alcanza"])
    assert int(por_sector.loc["Industrial", "fechas"]) == 8
    assert int(por_sector.loc["Industrial", "faltan"]) == MIN_OBSERVACIONES_PERCENTIL - 8


def test_la_cobertura_cuenta_fechas_y_no_renglones():
    """Tres emisoras en las mismas ocho fechas son ocho observaciones, no veinticuatro.

    Contar renglones haría que un sector con varias emisoras cortas pareciera tener
    historia de sobra, que es exactamente el error que el umbral existe para evitar.
    """
    cobertura = cobertura_del_percentil(_panel({"Industrial": 8}, emisoras_por_sector=3))
    assert int(cobertura.loc[0, "fechas"]) == 8
    assert not bool(cobertura.loc[0, "alcanza"])


def test_el_umbral_es_el_mismo_que_usa_el_percentil():
    """Anunciar un umbral distinto del que se aplica sería peor que no anunciarlo."""
    justo = cobertura_del_percentil(_panel({"Salud": MIN_OBSERVACIONES_PERCENTIL}))
    apenas = cobertura_del_percentil(_panel({"Salud": MIN_OBSERVACIONES_PERCENTIL - 1}))
    assert bool(justo.loc[0, "alcanza"])
    assert not bool(apenas.loc[0, "alcanza"])


def test_la_cobertura_de_un_panel_vacio_no_truena():
    """Base recién sembrada: la pantalla tiene que abrir, no reventar."""
    vacia = cobertura_del_percentil(pd.DataFrame())
    assert vacia.empty
    assert list(vacia.columns) == ["sector", "fechas", "alcanza", "faltan"]


def test_la_pantalla_anuncia_los_sectores_que_faltan_en_el_mapa_y_en_el_reloj():
    assert "cobertura_del_percentil(" in PAGINA
    assert "en el mapa y en el reloj" in PAGINA, (
        "el aviso tiene que cubrir los dos gráficos: los dos pierden los mismos sectores"
    )


# --------------------------------------------------------------------------------------
# 23.5  El muestreo tira el trimestre más reciente
# --------------------------------------------------------------------------------------


def _matriz(n_columnas: int) -> pd.DataFrame:
    fechas = pd.date_range("2000-03-31", periods=n_columnas, freq="QE")
    return pd.DataFrame([[0.5] * n_columnas], index=["Net Lease"], columns=fechas)


@pytest.mark.parametrize("n", [41, 60, 81, 100, 101, 120, 240])
def test_el_muestreo_conserva_siempre_la_ultima_fecha(n):
    """El defecto medido: con 100 columnas y paso 2, `::2` desde el inicio tira la última."""
    matriz = _matriz(n)
    muestreada = muestrear_columnas(matriz)
    assert muestreada.columns[-1] == matriz.columns[-1], (
        "se perdió el trimestre más reciente, que es para lo que sirve este gráfico"
    )
    assert len(muestreada.columns) <= 40


def test_el_muestreo_desde_el_inicio_es_el_que_perdia_la_ultima():
    """La forma anterior, escrita aquí para que el defecto quede documentado."""
    matriz = _matriz(100)
    anterior = matriz.loc[:, ::max(1, len(matriz.columns) // 40)]
    assert anterior.columns[-1] != matriz.columns[-1]


def test_una_matriz_corta_no_se_muestrea():
    matriz = _matriz(12)
    assert list(muestrear_columnas(matriz).columns) == list(matriz.columns)
    assert muestrear_columnas(pd.DataFrame()).empty


def test_el_muestreo_conserva_el_orden_cronologico():
    """Se muestrea desde el final, pero se dibuja de izquierda a derecha en el tiempo."""
    muestreada = muestrear_columnas(_matriz(100))
    assert list(muestreada.columns) == sorted(muestreada.columns)


# --------------------------------------------------------------------------------------
# 23.6  El mismo percentil, un solo valor
# --------------------------------------------------------------------------------------


def _como_lo_dibuja_streamlit(valor: float, decimales: int) -> str:
    """`Number.prototype.toFixed`: en el empate elige el mayor, no el par.

    Es la diferencia con Python, y es la razón por la que el mismo número salía con
    dos valores en la misma pantalla.
    """
    cuantia = Decimal(1).scaleb(-decimales)
    return str(Decimal(valor).quantize(cuantia, rounding=ROUND_HALF_UP))


def _como_lo_dibuja_python(valor: float, decimales: int) -> str:
    return f"{valor:.{decimales}f}"


def test_los_dos_motores_de_formato_discrepan_de_verdad():
    """Sin esto, todo lo demás sería una precaución contra un problema imaginario."""
    assert _como_lo_dibuja_streamlit(12.5, 0) == "13"
    assert _como_lo_dibuja_python(12.5, 0) == "12"


@pytest.mark.parametrize("n", range(8, 41))
def test_la_tabla_y_la_grafica_dibujan_el_mismo_percentil(n):
    """Todos los percentiles que un rango de n observaciones puede producir.

    El valor entra cuantizado a los decimales que se van a dibujar, así que a
    ninguno de los dos motores le queda un empate que romper: coinciden por
    construcción, no por suerte.
    """
    for k in range(n + 1):
        fraccion = cuantizar_percentil(k / n)
        # La tabla: `formato_columnas` escala el dato y Streamlit lo formatea.
        vista, _ = formato_columnas(pd.DataFrame({"percentil_prima": [fraccion]}))
        en_tabla = _como_lo_dibuja_streamlit(vista["percentil_prima"].iloc[0], DECIMALES_PERCENTIL)
        # La gráfica: el mismo dato, formateado por Python.
        en_grafica = texto_percentil(fraccion).rstrip("%")
        assert en_tabla == en_grafica, f"{k}/{n} se dibuja {en_tabla}% y {en_grafica}%"


def test_sin_cuantizar_y_con_cero_decimales_es_cuando_discrepaban():
    """El caso concreto que se veía: 1/8 en la tabla y en la gráfica de al lado."""
    vista, _ = formato_columnas(pd.DataFrame({"percentil_prima": [0.125]}))
    assert _como_lo_dibuja_streamlit(vista["percentil_prima"].iloc[0], 0) == "13"
    assert f"{0.125:.0%}" == "12%"


def test_los_decimales_del_percentil_viven_en_un_solo_lugar():
    """Cableado: mientras los dos lados salgan de la misma constante, no pueden discrepar.

    Es lo que hace que el arreglo aguante. Volver a escribir el formato a mano en
    cualquiera de los dos lados reabre el defecto sin tocar nada más.
    """
    assert FORMATO_PERCENTIL_TABLA == f"%.{DECIMALES_PERCENTIL}f%%"
    assert texto_percentil(0.125) == f"{0.125:.{DECIMALES_PERCENTIL}%}"
    assert "format=FORMATO_PERCENTIL_TABLA" in PAGINA, "la tabla volvió a un formato a mano"
    assert "texto_percentil(" in PAGINA, "la gráfica volvió a un formato a mano"
    assert PAGINA.count("cuantizar_percentil(") >= 2, (
        "los dos lados tienen que recibir el dato ya redondeado, no solo uno"
    )


def test_el_hueco_del_percentil_sigue_siendo_hueco():
    assert texto_percentil(None) == "—"
    assert texto_percentil(float("nan")) == "—"
    assert cuantizar_percentil(None) is None


# --------------------------------------------------------------------------------------
# 23.7  La cuarta métrica del sector
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("sector", ["Net Lease", "Self Storage", "Oficinas"])
def test_hay_sectores_con_mas_de_tres_metricas_especificas(sector):
    """Si ninguno pasara de tres, truncar en tres no ocultaría nada."""
    assert len(metricas_especificas(sector)) > 3


def test_el_capex_por_sector_es_la_metrica_que_se_perdia():
    """Es la última que añade `metricas_especificas`, así que es la que el corte comía.

    Y no es una nota menor: el rango de CapEx sobre NOI es la bandera roja
    específica del sector, la que dice si el emisor está reinvirtiendo lo que el
    inmueble consume.
    """
    for sector in ("Net Lease", "Self Storage", "Oficinas"):
        assert list(metricas_especificas(sector))[3:], f"{sector} no llega a la cuarta"
        assert "CapEx recurrente / NOI" in list(metricas_especificas(sector))[3:]


def test_ninguna_pantalla_trunca_las_metricas_del_sector():
    """El control del contrato: el corte era `[:3]` sobre la lista de métricas."""
    culpables = []
    for pagina in sorted((RAIZ / "app").rglob("*.py")):
        texto = pagina.read_text(encoding="utf-8")
        for numero, linea in enumerate(texto.splitlines(), 1):
            if "metricas_especificas" in linea and "[:" in linea:
                culpables.append(f"{pagina.relative_to(RAIZ)}:{numero}: {linea.strip()}")
    assert not culpables, "vuelven a ocultar métricas sin decirlo:\n" + "\n".join(culpables)


# --------------------------------------------------------------------------------------
# 23.8  Una sigla no es una palabra
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("columna", "esperado"),
    [
        ("affo_yield", "AFFO yield"),
        ("payout_affo", "Payout AFFO"),
        ("payout_ffo", "Payout FFO"),
        ("noi", "NOI"),
        ("premio_descuento_nav", "Premio descuento NAV"),
        ("tir_real", "TIR real"),
        ("yield_neto_reits", "Yield neto REITs"),
        ("cap_rate_implicito", "Cap rate implícito"),
        ("crecimiento_affo_por_accion_yoy", "Crecimiento AFFO por acción yoy"),
    ],
)
def test_la_sigla_se_dibuja_como_sigla(columna, esperado):
    assert etiqueta_de_columna(columna) == esperado


def test_el_plural_de_una_sigla_no_va_todo_en_mayusculas():
    """«REITS» no es el plural de REIT: la ese va en minúscula."""
    assert etiqueta_de_columna("brecha_vs_reits") == "Brecha vs REITs"
    assert etiqueta_de_columna("reit") == "REIT"


def test_los_bps_van_en_minuscula_por_convencion():
    """Se escribe «409 bps». Meterlo entre las siglas produciría «Prima BPS»."""
    assert etiqueta_de_columna("prima_bps") == "Prima bps"


def test_la_tabla_del_ranking_lleva_encabezados_legibles():
    """Las columnas del ranking sectorial que no traen configuración propia."""
    tabla = pd.DataFrame({
        "ticker": ["O"], "nombre": ["Realty Income"], "percentil_prima": [0.82],
        "affo_yield": [0.055], "p_affo": [14.4], "payout_affo": [0.73],
        "accion": ["MANTENER"],
    })
    _vista, config = formato_columnas(tabla)
    etiquetas = {c: config[c]["label"] for c in config}
    assert etiquetas["affo_yield"] == "AFFO yield"
    assert etiquetas["payout_affo"] == "Payout AFFO"
    assert etiquetas["p_affo"] == "P/AFFO"
    assert etiquetas["accion"] == "Acción"
