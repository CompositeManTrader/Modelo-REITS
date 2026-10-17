"""La ampliación del estudio a siete emisores más: narrativas, prima por sector y elegibles para asignar."""

from __future__ import annotations

import pandas as pd
import pytest

from src.estudio import ampliacion as am
from src.estudio import historia as hist
from src.estudio import intrinsecos as it
from src.estudio import metodos as mt

# Lo que pertenece a un emisor nuevo y no puede aparecer en la narrativa de otro.
PROPIO = {
    "ADC": ("Agree", "Borders"),
    "EPRT": ("Eldridge", "Essential Properties"),
    "GNL": ("Necessity Retail", "AR Global", "Global Net Lease"),
    "PSA": ("Public Storage", "Shurgard", "PS Business Parks"),
    "EXR": ("Extra Space", "Storage USA"),   # Life Storage no: PSA también la quiso comprar en 2023
    "PLD": ("Prologis", "ProLogis", "AMB Property"),
    "WELL": ("Welltower", "Health Care REIT"),
    "O": ("Realty Income", "VEREIT", "Orion"),
    "NNN": ("NNN REIT", "National Retail", "Golden Corral"),
    "WPC": ("W. P. Carey", "NLOP"),
}


def _textos(h) -> str:
    partes = [h.perfil, h.modelo_de_negocio]
    partes += [f"{x.titulo} {x.detalle}" for x in h.hitos]
    partes += [e.resumen for e in h.eras] + [f"{r.titulo} {r.texto}" for r in h.riesgos]
    partes += list(h.notas.values())
    return " ".join(partes)


@pytest.mark.parametrize("ticker", am.NUEVOS)
def test_la_narrativa_nueva_tiene_fuentes_y_eras_contiguas(ticker):
    h = hist.HISTORIAS.get(ticker)
    assert h is not None, f"falta la narrativa de {ticker}"
    assert h.ticker == ticker
    assert len(h.hitos) >= 10 and len(h.riesgos) >= 4
    for x in h.hitos:
        assert x.fuente.strip(), f"«{x.titulo}» no dice de dónde salió"
        assert x.precision in ("dia", "mes", "anio")
        assert x.categoria == "emisor"
    assert [x.fecha for x in h.hitos] == sorted(x.fecha for x in h.hitos)
    for a, b in zip(h.eras, h.eras[1:], strict=False):
        assert a.fin == b.inicio, f"hueco o encime entre «{a.nombre}» y «{b.nombre}»"
    assert h.eras[-1].fin is None
    assert "pesos" in h.riesgos[-1].titulo.lower()


@pytest.mark.parametrize("ticker", am.NUEVOS)
def test_la_narrativa_nueva_no_habla_de_otro_emisor(ticker):
    texto = _textos(hist.HISTORIAS[ticker])
    for otro, palabras in PROPIO.items():
        if otro == ticker:
            continue
        for palabra in palabras:
            assert palabra not in texto, f"la narrativa de {ticker} menciona «{palabra}», que es de {otro}"


def test_la_prima_es_la_del_sector():
    assert it.prima_de("O") == it.prima_de("NNN") == it.prima_de("WPC") == it.SUPUESTOS.prima == 0.03
    assert it.prima_de("PSA") == it.prima_de("EXR") == it.prima_de("PLD") == 0.035
    assert it.prima_de("WELL") == 0.045
    assert it.prima_de("NO_EXISTE") == it.SUPUESTOS.prima


def test_solo_entran_a_asignar_los_que_tienen_percentil_desde_2008():
    def panel(desde: str) -> pd.DataFrame:
        idx = pd.date_range("2000-01-31", "2026-09-30", freq="ME")
        return pd.DataFrame({"p_consenso": [0.5 if f >= pd.Timestamp(desde) else None for f in idx]}, index=idx)

    paneles = {"A": panel("2001-12-31"), "B": panel("2008-12-31"), "C": panel("2009-01-31"), "D": panel("2030-01-31")}
    assert mt.para_asignar(paneles) == ["A", "B"]


def test_los_grupos_del_preregistro():
    assert set(am.ORIGINALES).isdisjoint(am.NUEVOS)
    assert len(am.NUEVOS) == 7
    assert am.MEJORA_MINIMA == 0.005 and am.DIFERENCIA_BARATO_CARO == 0.03 and am.AZAR_MAXIMO == 0.05
