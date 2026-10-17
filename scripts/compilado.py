"""Genera el compilado del análisis: seis PDFs y un Excel en docs/compilado/.

    python scripts/compilado.py                 # todo
    python scripts/compilado.py --destino otra/carpeta
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.export import compilado  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--destino", type=Path, default=compilado.DIR_COMPILADO)
    a = ap.parse_args()
    for ruta in compilado.generar(a.destino):
        print(f"  {ruta.relative_to(RAIZ) if ruta.is_relative_to(RAIZ) else ruta}  ({ruta.stat().st_size / 1024:,.0f} KB)")


if __name__ == "__main__":
    main()
