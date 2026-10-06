"""Fase 9: la página y el PDF leen los resultados guardados y dicen lo mismo."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ / "app") not in sys.path:
    sys.path.insert(0, str(RAIZ / "app"))

from src.investigacion import bitacora, conclusiones, resultados, vistas
from src.investigacion import graficas as gi

requiere = pytest.mark.skipif(not resultados.hay_resultados(), reason="No están guardados los resultados.")


@pytest.fixture(scope="module")
def res():
    return resultados.cargar()


@requiere
def test_las_vistas_ponen_cada_fraccion_en_porcentaje(res):
    from comun import familia_de_columna

    problemas = []
    for nombre, construir in vistas.VISTAS.items():
        tabla = construir(res)
        assert len(tabla), nombre
        assert list(tabla.columns) == list(vistas.COLUMNAS[nombre]), nombre
        for c in tabla.columns:
            s = pd.to_numeric(tabla[c], errors="coerce").dropna()
            if s.empty or tabla[c].dtype == object or pd.api.types.is_integer_dtype(tabla[c]):
                continue
            familia = familia_de_columna(c, s)
            if c.startswith(("correlacion", "clark")):
                if familia != "numero":
                    problemas.append(f"{nombre}.{c}: «{familia}»")
                continue
            if s.abs().max() < 1.5 and familia != "porcentaje":
                problemas.append(f"{nombre}.{c}: fracción en «{familia}»")
            if familia == "porcentaje" and s.abs().max() > 1.5:
                problemas.append(f"{nombre}.{c}: porcentaje que ya viene multiplicado por 100")
        # Las mejoras van en puntos base enteros, ya escaladas.
        for c in tabla.columns:
            if c.endswith("_bps"):
                assert familia_de_columna(c) == "bps"
                assert tabla[c].dropna().abs().max() > 1, f"{nombre}.{c} parece fracción"
    assert not problemas, "\n".join(problemas)


@requiere
def test_las_conclusiones_estan_completas_y_cuadran_con_los_resultados(res):
    c = conclusiones.conclusiones(res)
    seleccion = (["Tampoco hay una regla para escoger en cuáles", "Lo barato es trampa, aun entre los de calidad"]
                 if "fase6" in res else [])
    assert [x.titulo for x in c] == [
        "No hay una señal que diga cuándo entrar", "Esperar no paga",
        "Decidiendo solo el dinero nuevo, el timing casi no puede valer nada",
        "La protección contra caídas existe, pero se paga", *seleccion, "Qué hacer", "Qué tanto se le puede creer"]
    for x in c:
        assert not re.search(r"\bnan\b|—(?: pb|%)", x.texto), x.texto
    # La cifra de la prueba final que dice el texto es la que está guardada.
    costo = round(-res["fase8"]["resumen"]["conjunto"]["mejora"] * 1e4)
    assert f"costó {costo:,d} pb al año" in c[3].texto
    assert str(bitacora.intentos()) in c[-1].texto
    if "fase6" in res:
        final = round(res["fase6"]["final"]["mejora"].iloc[0] * 1e4)
        assert f"ganó {final:+,d} pb al año" in c[4].texto


@requiere
def test_las_graficas_se_arman(res):
    for nombre, hacer in gi.FIGURAS.items():
        fig = hacer(res)
        assert len(fig.data) >= 1, nombre


@requiere
def test_el_pdf_trae_todas_sus_secciones(res):
    from src.export.pdf_investigacion import html_de_investigacion

    h = html_de_investigacion(res, fuentes_css="")
    texto = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)>.*?</\1>", "", h, flags=re.S))
    for seccion in ("Lo que se encontró", "Cómo se hizo", "1. El techo", "2. Las señales de entrada",
                    "3. La escalera de modelos", "4. La prueba final", "5. En cuáles REITs", "Lo que queda"):
        assert seccion in texto, seccion
    assert not re.search(r"\bnan\b", texto, re.I)
    assert res["fase8"]["resumen"]["veredicto"] in texto


def test_la_pagina_no_abre_la_prueba_final():
    """La pantalla solo lee resultados: abrir los sellados queda en la bitácora y no debe pasar al visitarla."""
    codigo = (RAIZ / "app" / "pages" / "11_Investigacion.py").read_text(encoding="utf-8")
    for prohibido in ("abrir_sellado", "fase8.correr", "fase6.correr", "Muestra.VALIDACION", "sellar_mercados"):
        assert prohibido not in codigo, prohibido
    assert "resultados.cargar" in codigo


def test_los_resultados_se_guardan_y_se_leen(tmp_path):
    from dataclasses import dataclass

    @dataclass
    class R:
        desarrollo: pd.DataFrame
        por_era: pd.DataFrame
        pbo: float
        sharpe_deflactado: float
        mejor: str
        intentos: int

    d = pd.DataFrame({"senal": ["a"], "pasa": [False], "desde": [pd.Timestamp("1972-01-31")]})
    resultados.guardar_fase5(R(d, pd.DataFrame({"senal": ["a"]}), 0.1, 0.9, "a", 1), raiz=tmp_path)
    leido = resultados.cargar(tmp_path)
    assert leido["fase5"]["resumen"]["pasan"] == 0
    assert leido["fase5"]["desarrollo"]["desde"].iloc[0] == pd.Timestamp("1972-01-31")
    assert not resultados.hay_resultados(tmp_path)
