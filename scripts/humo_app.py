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

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGINAS = [
    RAIZ / "app" / "Inicio.py",
    *sorted((RAIZ / "app" / "pages").glob("*.py")),
]


def correr(ruta: Path, timeout: int = 240) -> tuple[bool, list[str]]:
    prueba = AppTest.from_file(str(ruta), default_timeout=timeout)
    prueba.run()
    errores = [e.value for e in prueba.exception]
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
