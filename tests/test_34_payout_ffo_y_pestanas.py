"""Prueba 34 — El payout sobre FFO que faltaba, y la pantalla que se leía en un scroll.

Dos cosas que salieron del mismo repaso a Realty Income.

**El payout sobre FFO.** Salía vacío para O teniendo el dato. Su conciliación
dejó de traer el FFO de Nareit como subtotal en MONTO en septiembre de 2024 —va
de la utilidad neta al FFO Normalizado sin pasar por él— pero sigue imprimiendo
"FFO per share" cada trimestre. El cálculo exigía el monto, y el panel ni
siquiera pedía la cifra por acción: era un hueco de código, no de información
(34.1).

**La pantalla.** Sus siete zonas eran las correctas y vivían en un solo scroll de
mil líneas, así que el veredicto competía por el mismo espacio que la auditoría.
Se agrupan en cuatro pestañas por CUÁNDO se miran, y suben a la cabecera fija las
cuatro cifras del balance y del valor que decidían la Puerta 1 desde dos
pantallas más abajo (34.2).
"""

from __future__ import annotations

import ast
import datetime as dt
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.datos.repositorio import Repositorio  # noqa: E402
from src.modelo.valuacion import InsumosValuacion, payout_ffo  # noqa: E402
from src.servicio import CONCEPTOS_PANEL, construir_panel  # noqa: E402

PAGINA = RAIZ / "app" / "pages" / "1_Valuacion.py"

# Payout sobre FFO de O en el segundo trimestre de 2026 según Bloomberg
# (`FFO_PAYOUT_RATIO`), en tanto por uno. Sirve de contraste independiente.
BBG_PAYOUT_FFO = 0.7576


def _ins(**kw) -> InsumosValuacion:
    base = {"ticker": "X", "precio": 60.0, "acciones_diluidas": 1_000e6,
            "dividendo_ttm_por_accion": 3.0}
    return InsumosValuacion(**{**base, **kw})


# --------------------------------------------------------------------------------------
# 34.1 · El payout sobre FFO
# --------------------------------------------------------------------------------------


def test_el_panel_pide_el_ffo_por_accion():
    """La causa raíz, y la única línea que de verdad faltaba.

    El concepto estaba en la base con 26 trimestres y el panel no lo cargaba, así
    que el renglón salía vacío por un hueco de código. Sin esta entrada, todo lo
    demás de 34.1 es teoría.
    """
    assert "ffo_por_accion" in CONCEPTOS_PANEL


def test_prefiere_la_cifra_por_accion_sobre_el_monto():
    """Y no solo como respaldo: la de por acción es MEJOR.

    Dividir el monto entre las acciones vuelve a construir un denominador que el
    emisor ya resolvió, y los dos conteos no siempre coinciden — el flujo por
    acción de un UPREIT se reparte entre acciones más unidades de la sociedad
    operativa. Aquí los dos caminos darían resultados distintos a propósito, para
    que la prueba distinga cuál se usó.
    """
    ins = _ins(ffo_por_accion_ttm=4.00, ffo_ttm=5_000e6)  # el monto daría 5.00
    assert payout_ffo(ins) == pytest.approx(3.0 / 4.00)


def test_cae_al_monto_cuando_no_hay_cifra_por_accion():
    """El control: no se puede romper al emisor que sí publica el subtotal."""
    assert payout_ffo(_ins(ffo_ttm=5_000e6)) == pytest.approx(3.0 / 5.00)


def test_sin_ninguno_de_los_dos_no_se_inventa_un_payout():
    assert payout_ffo(_ins()) is None
    assert payout_ffo(_ins(ffo_por_accion_ttm=0.0, ffo_ttm=0.0)) is None


def test_sin_dividendo_no_hay_payout():
    ins = _ins(ffo_por_accion_ttm=4.00, dividendo_ttm_por_accion=None)
    assert payout_ffo(ins) is None


def test_realty_income_ya_tiene_payout_sobre_ffo():
    """Sobre datos reales, y contrastado contra un tercero.

    Bloomberg publica 75.76% para el mismo trimestre. Que coincidan no prueba que
    el número sea correcto —los dos podrían leer mal lo mismo— pero sí que la
    deducción por acción no introdujo un sesgo propio.
    """
    repo = Repositorio()
    panel = construir_panel(repo, "O", asof=dt.date.today())
    if panel.trimestral.empty:
        pytest.skip("No hay base cargada.")
    valor = panel.metricas.get("payout_ffo")
    assert valor is not None, "sigue vacío teniendo la cifra por acción"
    assert valor == pytest.approx(BBG_PAYOUT_FFO, abs=0.02)


def test_el_payout_sobre_ffo_no_reemplaza_al_de_affo():
    """P3 no cambia: el AFFO es el número, y el de FFO se publica para contrastar.

    El FFO no resta el CapEx recurrente ni la renta en línea recta, así que su
    payout siempre se ve mejor. Tenerlo sirve para comparar, no para decidir.
    """
    from src.config import UMBRALES
    from src.modelo.senal import puerta_calidad
    criterios = puerta_calidad({"payout_affo": 0.95, "payout_ffo": 0.50}).criterios
    fila = criterios[criterios["criterio"] == "Payout sobre AFFO"].iloc[0]
    assert fila["cumple"] is False or not fila["cumple"], (
        "la Puerta 1 se dejó salvar por el payout sobre FFO"
    )
    assert UMBRALES.calidad.payout_affo_max < 1.0


# --------------------------------------------------------------------------------------
# 34.2 · La pantalla: una cabecera y cuatro pestañas
# --------------------------------------------------------------------------------------


def _arbol() -> ast.Module:
    return ast.parse(PAGINA.read_text(encoding="utf-8"))


def _zonas_de(cuerpo) -> list[str]:
    """Los números de zona invocados directamente en este nivel del árbol."""
    salida = []
    for nodo in cuerpo:
        if (
            isinstance(nodo, ast.Expr)
            and isinstance(nodo.value, ast.Call)
            and isinstance(nodo.value.func, ast.Name)
            and nodo.value.func.id == "zona"
            and nodo.value.args
            and isinstance(nodo.value.args[0], ast.Constant)
        ):
            salida.append(nodo.value.args[0].value)
    return salida


def test_la_pantalla_declara_cuatro_pestanas_con_esos_nombres():
    fuente = PAGINA.read_text(encoding="utf-8")
    assert "tab_evidencia, tab_estados, tab_modelos, tab_auditoria = st.tabs(" in fuente
    for nombre in ("Evidencia", "Estados financieros", "Modelos", "Auditoría"):
        assert f'"{nombre}"' in fuente


def test_solo_el_veredicto_vive_fuera_de_las_pestanas():
    """La guarda contra la reincidencia.

    El problema original no fue que las zonas estuvieran mal, sino que estaban
    TODAS al mismo nivel. Sin esta prueba, agregar una zona nueva al final del
    archivo la devuelve al scroll infinito sin que nadie lo note.
    """
    assert _zonas_de(_arbol().body) == ["01"], (
        "hay zonas fuera de las pestañas; solo el veredicto va en la cabecera fija"
    )


def test_cada_zona_esta_en_la_pestana_que_le_toca():
    """Y el reparto es el que se decidió, no el que quedó.

    Las zonas 02 y 05 comparten pestaña sin ser contiguas en el archivo: Streamlit
    permite reentrar a una pestaña, y eso evitó reordenar código del que dependen
    bloques posteriores.
    """
    esperado = {
        "tab_evidencia": ["02", "05"],
        "tab_estados": ["03", "04"],
        "tab_modelos": ["06"],
        "tab_auditoria": ["07"],
    }
    encontrado: dict[str, list[str]] = {k: [] for k in esperado}
    for nodo in _arbol().body:
        if not isinstance(nodo, ast.With):
            continue
        for item in nodo.items:
            if isinstance(item.context_expr, ast.Name) and item.context_expr.id in encontrado:
                encontrado[item.context_expr.id] += _zonas_de(nodo.body)
    assert encontrado == esperado


def test_la_cabecera_muestra_las_cifras_del_balance_y_del_valor():
    """Las cuatro que decidían la Puerta 1 desde dos pantallas más abajo.

    Se podía leer «DESCARTADO por calidad» sin ver, en la misma vista, cuál de
    los criterios lo descartó. Ahora el apalancamiento y el spread están junto al
    veredicto que explican.
    """
    fuente = PAGINA.read_text(encoding="utf-8")
    cabecera = fuente[: fuente.index("st.tabs(")]
    for etiqueta in ("Apalancamiento", "Spread de inversión",
                     "Percentil de la prima", "Precio vs NAV"):
        assert f'"{etiqueta}"' in cabecera, f"«{etiqueta}» no está en la cabecera fija"


def test_las_pestanas_se_crean_una_sola_vez_y_antes_de_usarse():
    """Un `st.tabs` por rama duplicaría la barra de pestañas en pantalla."""
    fuente = PAGINA.read_text(encoding="utf-8")
    assert fuente.count("tab_evidencia, tab_estados, tab_modelos, tab_auditoria = st.tabs(") == 1
    assert fuente.index("= st.tabs(") < fuente.index("with tab_evidencia:")
