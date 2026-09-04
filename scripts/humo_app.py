#!/usr/bin/env python3
"""Prueba de humo de la interfaz: ejecuta cada página y reporta errores.

Streamlit no tiene un modo "compilar y verificar", así que se usa su propio motor
de pruebas (``AppTest``) para correr cada página de punta a punta contra la base
real. Es la única forma de cachar que una página se rompe por una columna que no
existe o un formato mal escrito, que es justo lo que un lint no ve.

    python scripts/humo_app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "app"))

import pyarrow as pa  # noqa: E402
from streamlit import dataframe_util  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

PAGINAS = [
    RAIZ / "app" / "Inicio.py",
    *sorted((RAIZ / "app" / "pages").glob("*.py")),
]


# --------------------------------------------------------------------------------------
# Fallas que Streamlit se traga
# --------------------------------------------------------------------------------------
#
# Cuando una tabla no se puede serializar a Arrow —basta una columna que mezcle
# números con texto— Streamlit lo anota en un `logger.info`, aplica una conversión
# de respaldo y sigue. La página termina, `prueba.exception` viene vacía y la
# prueba de humo diría OK mientras el usuario ve una tabla con los tipos
# cambiados o no la ve.
#
# No se detecta leyendo el registro (depende del nivel configurado) ni mirando la
# tabla dibujada (ya viene convertida). Se detecta en el único lugar donde el
# error existe: la función que lo captura. Se le pone una envoltura que intenta la
# conversión original, anota si falla, y luego delega para no cambiar el
# comportamiento de la aplicación.

_FALLAS_DE_DIBUJO: list[str] = []
_convertir_original = dataframe_util.convert_pandas_df_to_arrow_table


def _convertir_vigilado(df, *, preserve_index=None):
    try:
        pa.Table.from_pandas(df, preserve_index=preserve_index)
    except (pa.ArrowInvalid, pa.ArrowTypeError, pa.ArrowNotImplementedError) as exc:
        columnas = ", ".join(str(c) for c in df.columns)
        _FALLAS_DE_DIBUJO.append(
            f"una tabla no serializa a Arrow y Streamlit la convirtió por su cuenta "
            f"[columnas: {columnas}] · {str(exc).splitlines()[0][:150]}"
        )
    return _convertir_original(df, preserve_index=preserve_index)


dataframe_util.convert_pandas_df_to_arrow_table = _convertir_vigilado


def _selector_de_emisor(prueba):
    for s in prueba.selectbox:
        if s.label == "Emisor":
            return s
    return None


def correr(ruta: Path, timeout: int = 240) -> tuple[bool, list[str]]:
    """Corre la página y, si tiene selector de emisor, la corre con TODOS.

    Recorrer un solo emisor no prueba la página: prueba el emisor que le tocó ser
    el primero de la lista. Los emisores no están en el mismo estado —a unos les
    cuadra el AFFO y a otros no, unos tienen NOI y otros lo traen vacío— y las
    fallas viven justo en esas diferencias. Un defecto real llegó a producción
    porque el emisor por omisión sí tenía el dato que a los demás les falta.
    """
    _FALLAS_DE_DIBUJO.clear()
    prueba = AppTest.from_file(str(ruta), default_timeout=timeout)
    prueba.run()
    errores = [f"{e.value}" for e in prueba.exception] + list(_FALLAS_DE_DIBUJO)

    selector = _selector_de_emisor(prueba)
    if selector is not None:
        for opcion in list(selector.options):
            _FALLAS_DE_DIBUJO.clear()
            actual = _selector_de_emisor(prueba)
            if actual is None:
                break
            actual.set_value(opcion).run()
            for e in prueba.exception:
                errores.append(f"[{opcion.split(' —')[0]}] {e.value}")
            for f in _FALLAS_DE_DIBUJO:
                errores.append(f"[{opcion.split(' —')[0]}] {f}")
    return (not errores), errores


def _recorrer(titulo: str) -> int:
    fallos = 0
    print(f"\n{titulo}")
    print("-" * len(titulo))
    for ruta in PAGINAS:
        ok, errores = correr(ruta)
        print(f"{'OK  ' if ok else 'FALLA'} {ruta.relative_to(RAIZ)}")
        for e in errores:
            print(f"      {e}")
            fallos += 1
    return fallos


def _con_base_vacia() -> int:
    """Segundo recorrido contra una base creada pero SIN datos.

    Es el estado real del primer arranque en la nube: el esquema existe, la
    ingesta va a medias o falló, y varias series vienen vacías. Dos defectos
    llegaron a producción por no probar esto: una serie vacía nace con índice
    entero y truena al rebanarla por fecha, y una celda ``pd.NA`` no tiene valor
    de verdad, así que ``float(celda or 0.0)`` tumba la página. Ninguno se ve con
    la base llena, que es contra lo que se probaba.

    Corre en un PROCESO APARTE, y no por prolijidad. Cambiar ``REIT_DB`` en
    caliente no basta: ``comun`` ya tiene enlazada la ruta por ``from ... import``,
    y ``obtener_repo`` está detrás de ``st.cache_resource``, así que el segundo
    recorrido seguía leyendo la base real y reportaba OK con el defecto puesto.
    Se comprobó reintroduciéndolo: solo el subproceso lo caza.
    """
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "vacia.db"
        # La base tiene que EXISTIR y estar vacía: si no existiera, la aplicación
        # arrancaría la ingesta real y esto tocaría la red.
        from src.datos.repositorio import Repositorio

        Repositorio(ruta=ruta)

        entorno = {**os.environ, "REIT_DB": str(ruta), "HUMO_UN_SOLO_RECORRIDO": "1"}
        proceso = subprocess.run(
            [sys.executable, str(Path(__file__).resolve())],
            env=entorno, capture_output=True, text=True,
        )
        print(proceso.stdout.replace("Primer recorrido: base real",
                                     "Segundo recorrido: base vacía (primer arranque)"), end="")
        return 0 if proceso.returncode == 0 else 1


def main() -> int:
    fallos = _recorrer("Primer recorrido: base real")
    # El subproceso corre esta misma función con la bandera puesta: sin ella se
    # llamaría a sí mismo sin fin.
    if not os.environ.get("HUMO_UN_SOLO_RECORRIDO"):
        fallos += _con_base_vacia()
    if fallos:
        print(f"\n{fallos} error(es) en la interfaz.")
        return 1
    if os.environ.get("HUMO_UN_SOLO_RECORRIDO"):
        return 0
    print(f"\nLas {len(PAGINAS)} páginas corren sin excepciones, con base llena y vacía.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
