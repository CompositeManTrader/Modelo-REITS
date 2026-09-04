"""Fixtures compartidas. Ninguna prueba obligatoria depende de la red."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.datos.repositorio import Repositorio  # noqa: E402
from src.datos.semilla import sembrar  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def repo_vacio(tmp_path) -> Repositorio:
    """Base limpia en disco temporal."""
    return Repositorio(ruta=tmp_path / "prueba.db")


@pytest.fixture
def repo_sembrado(tmp_path) -> Repositorio:
    """Base con datos de demostración de tres emisores."""
    repo = Repositorio(ruta=tmp_path / "sembrada.db")
    sembrar(
        repo,
        tickers=["O", "PLD", "GNL"],
        inicio=dt.date(2018, 1, 1),
        fin=dt.date(2026, 6, 30),
    )
    return repo


@pytest.fixture
def html_8k_realty() -> str:
    """Extracto real del Exhibit 99.1 del 8-K de Realty Income del 2026-08-05.

    Se versiona en el repositorio para que las pruebas del parser corran sin red
    y contra un documento que la SEC efectivamente publicó, no contra una
    maqueta que confirma lo que el parser ya hace.
    """
    ruta = FIXTURES / "o_8k_q2_2026_ex99_1.html"
    if not ruta.exists():
        pytest.skip("Falta el fixture del 8-K de Realty Income.")
    return ruta.read_text(encoding="utf-8")


@pytest.fixture
def fecha_publicacion_8k() -> dt.date:
    """Fecha de presentación del 8-K del fixture. Es su fecha_publicacion PIT."""
    return dt.date(2026, 8, 5)
