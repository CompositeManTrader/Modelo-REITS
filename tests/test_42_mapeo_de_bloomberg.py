"""Prueba 42 — El mapeo del molde de Bloomberg contra lo que la SEC sí publica.

El molde quedó completo en la prueba 37: los 186 renglones, con su orden, su
sangría y su campo. Lo que faltaba revisar es la otra mitad —el MAPEO, que es
criterio y se mantiene a mano— y ahí había tres clases de error distintas, cada
una con su arreglo:

**Un concepto alimentando dos renglones que Bloomberg pide por separado.** El
deterioro de inmuebles llenaba «Real Estate Write-Downs» *y* «Provision for Loan
Losses». Son dos campos distintos —``IS_UNTAXED_RSRV`` e
``IS_PROV_FOR_LOAN_LOSS``— y la segunda no es deterioro: es provisión crediticia
sobre cuentas por cobrar, que Realty Income publica bajo
``ProvisionForLoanLossesExpensed`` y vale 39.1 millones donde el deterioro vale
129.3. El mismo número salía en los dos renglones y ninguno de los dos era el
que Bloomberg imprime en el de arriba.

**Un renglón declarado «no aplica» que sí aplica.** El EPS de operaciones
continuas estaba marcado como renglón que no corresponde a un REIT de EE. UU.
W. P. Carey lo publica en los setenta cortes y Welltower en sesenta y cinco,
hasta el trimestre vigente: aplica a cualquier emisora que haya tenido
operaciones discontinuadas, y siete de las diez las tuvieron.

**Una cadena de etiquetas que se comía otro renglón.** ``otros_no_operativos``
incluía ``NonoperatingIncomeExpense``, que es el TOTAL no operativo y tiene su
propio renglón en el molde. En Prologis eso ponía 19.2 millones —el total— en el
renglón del residuo, y de paso inflaba el subtotal de arriba, que se calcula a
partir de él: 148.1 millones donde son 128.8.

Lo que ganó y lo que perdió
---------------------------
Sobre las diez emisoras, 963 celdas ganan dato —265 en cada EPS de continuas,
152 en operaciones discontinuadas, 145 en la provisión crediticia, 103 en la
utilidad de continuas y 33 en la renta variable— y 44 lo pierden, que son las
dos correcciones: el residuo no operativo deja de imprimir el total.

Lo que NO se tocó, y por qué
---------------------------
«Other Operating Income», «Net Abnormal Losses», los EPS «Adjusted» y el
subtotal «Non-Operating (Income) Loss» quedan como estaban. Los cuatro dependen
de una CONVENCIÓN de Bloomberg —qué mete en cada cubeta— y no de una etiqueta
que se pueda leer del filing. Cambiarlos sin el export de la terminal enfrente
sería adivinar, y una cifra adivinada con formato de dato es exactamente lo que
este modelo no hace.
"""

from __future__ import annotations

import collections
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta.estados import LINEA_POR_CLAVE  # noqa: E402
from src.modelo import bloomberg as B  # noqa: E402
from src.servicio import panel_de_conceptos  # noqa: E402

HOY = dt.date.today()

# Los únicos renglones que Bloomberg imprime DOS VECES en el mismo estado, y por
# eso pueden compartir concepto: el minoritario aparece en la cascada del FFO
# además de en el estado, y el dividendo y el FAD por acción se repiten en
# «Reference Items». No son duplicados nuestros: son duplicados del molde.
REPETICIONES_DEL_MOLDE = {
    "utilidad_minoritarios": {"Minority Interest"},
    "affo_por_accion": {"FAD Per Diluted Share", "FAD per Share Diluted"},
    "dividendo_declarado_por_accion": {
        "Dividend Per Share", "Dividends/Distributions per Share/Unit",
    },
}


@pytest.fixture(scope="module")
def repo():
    r = Repositorio()
    if r.hechos(asof=HOY, tickers="O", conceptos=["ingresos_totales"]).empty:
        pytest.skip("No hay base cargada.")
    return r


# --------------------------------------------------------------------------------------
# 42.1 · Un concepto, un renglón
# --------------------------------------------------------------------------------------


def test_ningun_concepto_llena_dos_renglones_distintos_del_mismo_estado():
    """El invariante que habría cazado el deterioro en dos cubetas.

    Dos renglones del molde con el mismo número son dos afirmaciones de que ese
    número es dos cosas distintas, y una de las dos es falsa. Las tres
    excepciones son renglones que el propio export de Bloomberg repite.
    """
    duplicados = []
    for estado in B.ESTADOS:
        cuenta = collections.defaultdict(set)
        for linea in B.PLANTILLA[estado]:
            if linea.clave:
                cuenta[linea.clave].add(linea.etiqueta)
        for clave, etiquetas in cuenta.items():
            if len(etiquetas) > 1 and REPETICIONES_DEL_MOLDE.get(clave) != etiquetas:
                duplicados.append(f"{estado}: «{clave}» llena {sorted(etiquetas)}")
    assert duplicados == [], "un concepto en dos renglones:\n" + "\n".join(duplicados)


def test_la_provision_crediticia_no_es_el_deterioro_de_inmuebles():
    """Son dos campos de Bloomberg y dos etiquetas de la SEC, no una."""
    por_etiqueta = {ln.etiqueta: ln for ln in B.PLANTILLA[B.RESULTADOS]}
    provision = por_etiqueta["Provision for Loan Losses"]
    deterioro = por_etiqueta["Real Estate Write-Downs"]
    assert provision.clave == "provision_perdidas_crediticias"
    assert deterioro.clave == "deterioro"
    assert provision.campo_bbg != deterioro.campo_bbg


def test_sobre_datos_reales_la_provision_y_el_deterioro_dan_numeros_distintos(repo):
    """Realty Income publica las dos: 39.1 millones de provisión y 129.3 de deterioro.

    Antes el renglón de arriba imprimía el de abajo.
    """
    panel = panel_de_conceptos(repo, "O", asof=HOY)
    tabla = B.armar(panel, B.RESULTADOS)
    periodos = [c for c in tabla.columns
                if c != "Renglón" and c not in B.COLUMNAS_DE_APOYO]

    def serie(etiqueta):
        fila = tabla[tabla["Renglón"].str.strip().str.endswith(etiqueta)]
        return fila[periodos].iloc[0] if not fila.empty else None

    provision, deterioro = serie("Provision for Loan Losses"), serie("Real Estate Write-Downs")
    ambos = [p for p in periodos
             if pd.notna(provision[p]) and pd.notna(deterioro[p])]
    assert ambos, "no hay un periodo con las dos cifras"
    iguales = [p for p in ambos if float(provision[p]) == float(deterioro[p])]
    assert iguales == [], f"la provisión sigue siendo el deterioro en {iguales[:3]}"


# --------------------------------------------------------------------------------------
# 42.2 · Un renglón vacío tiene que estarlo porque el dato no existe
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "clave",
    ["provision_perdidas_crediticias", "utilidad_operaciones_continuas",
     "operaciones_discontinuadas", "utilidad_por_accion_basica_continuas",
     "utilidad_por_accion_diluida_continuas"],
)
def test_las_lineas_nuevas_existen_en_el_catalogo_y_traen_etiquetas(clave):
    linea = LINEA_POR_CLAVE.get(clave)
    assert linea is not None, clave
    assert linea.tags, f"«{clave}» no puede alcanzar ningún dato"


@pytest.mark.parametrize(
    "etiqueta,clave",
    [("Provision for Loan Losses", "provision_perdidas_crediticias"),
     ("Discontinued Operations", "operaciones_discontinuadas"),
     ("Basic EPS from Cont Ops, GAAP", "utilidad_por_accion_basica_continuas"),
     ("Diluted EPS from Cont Ops, GAAP", "utilidad_por_accion_diluida_continuas")],
)
def test_los_renglones_que_decian_no_aplica_ya_estan_mapeados(etiqueta, clave):
    """«No aplica a un REIT» era un juicio, y estaba equivocado."""
    linea = {ln.etiqueta: ln for ln in B.PLANTILLA[B.RESULTADOS]}[etiqueta]
    assert linea.clave == clave
    assert not linea.nota.startswith("Renglón del molde de Bloomberg que no aplica")


def test_el_eps_de_continuas_llega_al_trimestre_vigente_en_quien_lo_publica(repo):
    """W. P. Carey lo publica en los setenta cortes; el molde lo daba por perdido."""
    panel = panel_de_conceptos(repo, "WPC", asof=HOY)
    if panel.empty:
        pytest.skip("No hay base de WPC.")
    tabla = B.armar(panel, B.RESULTADOS)
    periodos = [c for c in tabla.columns
                if c != "Renglón" and c not in B.COLUMNAS_DE_APOYO]
    fila = tabla[tabla["Renglón"].str.strip() == "Diluted EPS from Cont Ops, GAAP"]
    assert not fila.empty
    assert pd.notna(fila[periodos[-1]].iloc[0]), "vacío justo en el trimestre vigente"


# --------------------------------------------------------------------------------------
# 42.3 · El total no operativo no va en el renglón del residuo
# --------------------------------------------------------------------------------------


def test_el_residuo_no_operativo_no_lee_la_etiqueta_del_total():
    """Son dos renglones del molde: el subtotal y lo que le queda debajo.

    Con la etiqueta del total en la cadena del residuo, Prologis imprimía 19.2
    millones en el renglón de abajo Y los volvía a contar en el de arriba.
    """
    tags = LINEA_POR_CLAVE["otros_no_operativos"].tags
    assert "NonoperatingIncomeExpense" not in tags
    assert "OtherNonoperatingIncomeExpense" in tags


# --------------------------------------------------------------------------------------
# 42.4 · Lo reportado le gana a lo derivado
# --------------------------------------------------------------------------------------


def test_la_utilidad_de_continuas_prefiere_el_dato_publicado():
    """Derivarla teniendo el dato es cambiar una cifra por una cuenta."""
    fila = pd.Series({
        "utilidad_operaciones_continuas": 1_000.0,
        "utilidad_antes_impuestos": 900.0,
        "impuestos": 50.0,
    })
    panel = pd.DataFrame([fila], index=pd.DatetimeIndex([dt.date(2026, 6, 30)]))
    valor = B._derivar("utilidad_continuas", fila, panel, panel.index[0])
    assert valor == pytest.approx(1_000.0), "derivó teniendo el reportado"


def test_y_lo_deriva_cuando_la_emisora_no_lo_publica():
    """La derivación no desaparece: pasa a ser el respaldo."""
    fila = pd.Series({"utilidad_antes_impuestos": 900.0, "impuestos": 50.0})
    panel = pd.DataFrame([fila], index=pd.DatetimeIndex([dt.date(2026, 6, 30)]))
    valor = B._derivar("utilidad_continuas", fila, panel, panel.index[0])
    assert valor == pytest.approx(850.0)


# --------------------------------------------------------------------------------------
# 42.5 · La cobertura sube, y lo que baja es a propósito
# --------------------------------------------------------------------------------------


def test_la_cobertura_del_molde_no_retrocede(repo):
    """Un piso medido, para que una limpieza de mapeo no cueste renglones en silencio."""
    from src.config import UNIVERSO_INICIAL

    total = 0
    for emisor in UNIVERSO_INICIAL:
        panel = panel_de_conceptos(repo, emisor.ticker, asof=HOY)
        if panel.empty:
            continue
        total += sum(B.cobertura(panel, estado)[0] for estado in B.ESTADOS)
    assert total >= 810, f"la cobertura del universo cayó a {total}"
