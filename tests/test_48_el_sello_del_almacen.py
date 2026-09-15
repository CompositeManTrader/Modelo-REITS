"""Prueba 48 — Que el sello del almacén diga la verdad.

El almacén versionado guarda una huella de cada archivo que escribe, y
``estados.py --revisar`` la compara contra el disco. La idea es detectar un
archivo cambiado fuera del proceso de ingesta —corrupción, una edición a mano,
una descarga a medias—.

Lo que había pasado
-------------------
Dos scripts escribían el mismo ``hechos.csv.gz``. Solo uno mantenía el
manifiesto:

* ``estados.py`` escribía y sellaba.
* ``instantanea.py exportar`` escribía y **no** sellaba: guardaba la huella en
  una variable local que nada más imprimía.

Así que cada exportación dejaba el manifiesto apuntando a bytes que ya no
existían, y la verificación reportaba «cambió fuera del proceso de ingesta»
—literalmente cierto y completamente inútil, porque el cambio venía de adentro—.
Las diez emisoras fallaban, y el flujo de estados llevaba así desde que los
crudos se regeneraron.

Una alarma que siempre suena no protege de nada: enseña a ignorarla. Ese es el
daño real, y es peor que no tener alarma, porque la de verdad también se ignora.

Las dos mitades del arreglo
---------------------------
1. **Quien escribe, sella.** Es la regla, y aquí se verifica sobre el código: si
   un script llama a ``escribir_crudos`` tiene que registrar la huella.
2. **Resellar cuando ya se desfasó**, con una guarda que lo mantiene honesto:
   ``--resellar`` se NIEGA si el archivo perdió hechos. Un archivo que creció es
   el crudo ampliado con más filings; uno que encogió perdió datos, y eso no se
   sella, se investiga. Sin esa guarda, resellar sería la forma de callar
   cualquier corrupción y la huella dejaría de valer.
"""

from __future__ import annotations

import gzip
import inspect
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.datos import almacen  # noqa: E402
from src.datos.almacen import (  # noqa: E402
    ARCHIVO_CRUDOS,
    Manifiesto,
    huella_de,
    verificar_huellas,
)

CRUDOS = pd.DataFrame(
    {
        "ticker": ["O"] * 3,
        "taxonomia": ["us-gaap"] * 3,
        "tag": ["Assets", "Liabilities", "Revenues"],
        "unidad": ["USD"] * 3,
        "periodo_tipo": ["PUNTUAL", "PUNTUAL", "Q"],
        "fecha_inicio": ["", "", "2024-01-01"],
        "fecha_dato": ["2024-03-31"] * 3,
        "fecha_publicacion": ["2024-05-01"] * 3,
        "valor": [100.0, 40.0, 12.0],
        "formulario": ["10-Q"] * 3,
        "accession": ["0000726728-24-000001"] * 3,
        "marco": ["CY2024Q1I"] * 3,
    }
)


@pytest.fixture
def almacen_temporal(tmp_path, monkeypatch):
    """Un almacén vacío, aislado del repositorio de verdad."""
    monkeypatch.setattr(almacen, "DIR_EMISORAS", tmp_path)
    monkeypatch.setattr(almacen, "RUTA_MANIFIESTO", tmp_path / "manifiesto.json")
    return tmp_path


def sembrar(base: Path, ticker: str, crudos: pd.DataFrame) -> Manifiesto:
    """Escribe los crudos y los sella, que es el estado sano del que se parte."""
    huella = almacen.escribir_crudos(ticker, crudos)
    m = Manifiesto.cargar()
    registro = m.registro(ticker)
    registro.huellas[ARCHIVO_CRUDOS] = huella
    registro.n_hechos_crudos = len(crudos)
    m.guardar()
    return m


# --------------------------------------------------------------------------------------
# 48.1 · Quien escribe un archivo sellado, lo sella
# --------------------------------------------------------------------------------------


def test_todo_script_que_escribe_crudos_registra_su_huella():
    """La regla, verificada sobre el código de los scripts.

    Es una prueba de TEXTO a propósito. La alternativa —correr cada script y
    comparar el manifiesto— exigiría red y una base cargada, así que en la
    práctica no se correría nunca; y el defecto que persigue es justo el que no
    se nota corriendo: el archivo queda bien escrito y el manifiesto viejo.
    """
    culpables = []
    for script in sorted((RAIZ / "scripts").glob("*.py")):
        fuente = script.read_text(encoding="utf-8")
        if "escribir_crudos(" not in fuente:
            continue
        sella = "huellas[ARCHIVO_CRUDOS]" in fuente or "huellas = {ARCHIVO_CRUDOS" in fuente
        guarda = "manifiesto.guardar()" in fuente or ".guardar()" in fuente
        if not (sella and guarda):
            culpables.append(script.name)
    assert culpables == [], (
        f"escriben hechos.csv.gz sin sellarlo en el manifiesto: {culpables}. "
        "La huella quedaría apuntando a bytes que ya no existen."
    )


def test_la_huella_tiene_una_sola_definicion():
    """Dos copias de una definición de huella se separan en cuanto una cambia."""
    assert almacen._huella is huella_de


# --------------------------------------------------------------------------------------
# 48.2 · Resellar, y lo que resellar NO puede hacer
# --------------------------------------------------------------------------------------


def test_resellar_acepta_un_archivo_que_crecio(almacen_temporal):
    """El caso legítimo: el crudo se amplió con más filings."""
    from scripts.estados import resellar

    sembrar(almacen_temporal, "O", CRUDOS)
    crecido = pd.concat([CRUDOS, CRUDOS.assign(tag="Cash", valor=7.0)], ignore_index=True)
    almacen.escribir_crudos("O", crecido)

    m = Manifiesto.cargar()
    assert verificar_huellas(m.registro("O"), base=almacen_temporal), "debía estar desfasado"
    assert resellar(m, ["O"]) == 0

    m2 = Manifiesto.cargar()
    assert verificar_huellas(m2.registro("O"), base=almacen_temporal) == []
    assert m2.registro("O").n_hechos_crudos == len(crecido)


def test_resellar_se_niega_si_el_archivo_perdio_hechos(almacen_temporal):
    """La guarda que hace honesto al resellado.

    Sin ella, `--resellar` sería el botón para callar cualquier corrupción: un
    archivo truncado a la mitad quedaría sellado como bueno y la verificación
    nunca volvería a decir nada. Un archivo que ENCOGIÓ no se sella.
    """
    from scripts.estados import resellar

    sembrar(almacen_temporal, "O", CRUDOS)
    almacen.escribir_crudos("O", CRUDOS.iloc[:1])  # perdió dos hechos

    m = Manifiesto.cargar()
    assert resellar(m, ["O"]) > 0, "reselló una emisora que perdió datos"

    # Y no guardó nada: la huella vieja sigue ahí para que la alarma siga sonando.
    m2 = Manifiesto.cargar()
    assert verificar_huellas(m2.registro("O"), base=almacen_temporal), (
        "el desajuste se borró: la corrupción quedaría sellada como buena"
    )


def test_un_archivo_corrompido_sin_perder_filas_tambien_se_detecta(almacen_temporal):
    """La guarda es por conteo, así que hay que decir qué NO cubre.

    Cambiar un valor sin cambiar el número de filas pasa la guarda y se resella.
    Lo que sigue protegiendo ahí es `--revisar`, que corre las verificaciones de
    balance sobre el contenido: un activo alterado deja de cuadrar. La huella
    detecta el cambio; las verificaciones dicen si el cambio está mal.
    """
    from scripts.estados import resellar

    sembrar(almacen_temporal, "O", CRUDOS)
    alterado = CRUDOS.copy()
    alterado.loc[0, "valor"] = 999_999.0
    almacen.escribir_crudos("O", alterado)

    m = Manifiesto.cargar()
    assert verificar_huellas(m.registro("O"), base=almacen_temporal), "la huella no lo vio"
    assert resellar(m, ["O"]) == 0, "mismo conteo: la guarda por filas no aplica"


def test_resellar_no_toca_lo_que_no_cambio(almacen_temporal):
    """Un resellado sobre un almacén sano no debe mover una sola huella."""
    from scripts.estados import resellar

    sembrar(almacen_temporal, "O", CRUDOS)
    antes = json.loads((almacen_temporal / "manifiesto.json").read_text(encoding="utf-8"))
    assert resellar(Manifiesto.cargar(), ["O"]) == 0
    despues = json.loads((almacen_temporal / "manifiesto.json").read_text(encoding="utf-8"))
    assert antes["emisoras"] == despues["emisoras"], "movió algo sin haber nada que mover"


def test_resellar_no_toca_la_red():
    """Es lo que permite correrlo en CI y sobre un almacén ya descargado."""
    from scripts.estados import resellar

    cuerpo = inspect.getsource(resellar)
    for red in ("ClienteEdgar", "companyfacts", "requests", "listar_filings"):
        assert red not in cuerpo, f"el resellado llama a {red}"


# --------------------------------------------------------------------------------------
# 48.3 · Sobre el almacén de verdad
# --------------------------------------------------------------------------------------


def test_el_manifiesto_del_repositorio_cuadra_con_sus_archivos():
    """El piso medido: ninguna emisora con la huella desfasada.

    Si esta prueba falla, el flujo `Estados financieros` está rojo en GitHub por
    la misma razón, y el arreglo es `python scripts/estados.py --resellar`
    DESPUÉS de averiguar quién escribió sin sellar.
    """
    m = Manifiesto.cargar()
    if not m.emisoras:
        pytest.skip("No hay manifiesto en este árbol.")
    desfasadas = {
        tk: problemas
        for tk, reg in m.emisoras.items()
        if (problemas := verificar_huellas(reg))
    }
    assert desfasadas == {}, f"huellas desfasadas: {desfasadas}"


def test_el_conteo_sellado_coincide_con_el_archivo():
    """`n_hechos_crudos` es lo que hace posible la guarda del resellado.

    Si se queda viejo, la guarda compara contra un número que no significa nada y
    deja de proteger. Va junto con la huella, siempre.
    """
    m = Manifiesto.cargar()
    if not m.emisoras:
        pytest.skip("No hay manifiesto en este árbol.")
    malas = []
    for tk, reg in m.emisoras.items():
        ruta = almacen.dir_emisora(tk) / ARCHIVO_CRUDOS
        if not ruta.exists():
            continue
        with gzip.open(ruta, "rt", encoding="utf-8") as f:
            filas = sum(1 for _ in f) - 1
        if filas != reg.n_hechos_crudos:
            malas.append(f"{tk}: manifiesto {reg.n_hechos_crudos:,} contra archivo {filas:,}")
    assert malas == [], "\n".join(malas)
