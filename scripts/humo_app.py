#!/usr/bin/env python3
"""Prueba de humo de la interfaz: ejecuta cada página y reporta errores.

Streamlit no tiene un modo "compilar y verificar", así que se usa su propio motor
de pruebas (``AppTest``) para correr cada página de punta a punta contra la base
real. Es la única forma de cachar que una página se rompe por una columna que no
existe o un formato mal escrito, que es justo lo que un lint no ve.

    python scripts/humo_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

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


def correr(ruta: Path, timeout: int = 240) -> tuple[bool, list[str]]:
    _FALLAS_DE_DIBUJO.clear()
    prueba = AppTest.from_file(str(ruta), default_timeout=timeout)
    prueba.run()
    errores = [e.value for e in prueba.exception] + list(_FALLAS_DE_DIBUJO)
    return (not errores), errores


def main() -> int:
    fallos = 0
    for ruta in PAGINAS:
        ok, errores = correr(ruta)
        estado = "OK  " if ok else "FALLA"
        print(f"{estado} {ruta.relative_to(RAIZ)}")
        for e in errores:
            print(f"      {e}")
            fallos += 1
    if fallos:
        print(f"\n{fallos} error(es) en la interfaz.")
        return 1
    print(f"\nLas {len(PAGINAS)} páginas corren sin excepciones.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
