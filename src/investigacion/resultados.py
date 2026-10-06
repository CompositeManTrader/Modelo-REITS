"""Los resultados de cada fase, guardados para que la página y el PDF los lean sin recalcular.

La prueba final se abre una sola vez y cada apertura queda en la bitácora: la pantalla no
puede volver a abrirla cada vez que alguien la visita. Por eso los comandos de
``scripts/investigacion.py`` guardan aquí lo que calcularon, y la página y el PDF solo leen.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.investigacion.datos import DIR_INVESTIGACION

DIR_RESULTADOS = DIR_INVESTIGACION / "resultados"


def _csv(d: pd.DataFrame, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(ruta, index=False, float_format="%.10g")


def _json(obj: dict, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def guardar_fase3(x: pd.DataFrame, *, raiz: Path | None = None) -> None:
    from src.investigacion import exploracion as ex

    d = (raiz or DIR_RESULTADOS) / "fase3"
    _csv(ex.descomposicion(x), d / "descomposicion.csv")
    _csv(ex.caidas(x), d / "caidas.csv")
    _csv(ex.frecuencia_efectivo_gana(x), d / "frecuencia.csv")
    _csv(ex.techo(x).tabla, d / "techo.csv")


def guardar_fase5(r, *, raiz: Path | None = None) -> None:
    d = (raiz or DIR_RESULTADOS) / "fase5"
    _csv(r.desarrollo, d / "desarrollo.csv")
    _csv(r.por_era, d / "eras.csv")
    _json({"pbo": r.pbo, "sharpe_deflactado": r.sharpe_deflactado, "mejor": r.mejor, "intentos": r.intentos,
           "pasan": int(r.desarrollo["pasa"].sum())}, d / "resumen.json")


def guardar_fase7(r, *, raiz: Path | None = None) -> None:
    d = (raiz or DIR_RESULTADOS) / "fase7"
    _csv(r.evaluacion, d / "evaluacion.csv")
    _csv(r.eras, d / "eras.csv")
    _csv(pd.DataFrame({p.nombre: p.exposicion for p in r.peldanos}).rename_axis("fecha").reset_index(),
         d / "exposiciones.csv")
    _json({"se_quedan": r.se_quedan, "candidato": r.candidato}, d / "resumen.json")


def guardar_fase8(r, *, raiz: Path | None = None) -> None:
    d = (raiz or DIR_RESULTADOS) / "fase8"
    _csv(r.mercados, d / "mercados.csv")
    _csv(r.serie_eeuu, d / "tendencia_eeuu.csv")
    _json({"validacion": r.validacion, "conjunto": r.conjunto, "veredicto": r.veredicto, "apuestas": r.apuestas},
          d / "resumen.json")


def guardar_fase6(r, *, raiz: Path | None = None) -> None:
    d = (raiz or DIR_RESULTADOS) / "fase6"
    _csv(r.desarrollo, d / "desarrollo.csv")
    _csv(r.validacion, d / "validacion.csv")
    if len(r.final):
        _csv(r.final, d / "final.csv")
    _json({"pbo": r.pbo, "sharpe_deflactado": r.sharpe_deflactado, "mejor": r.mejor, "intentos": r.intentos,
           "candidatas": r.candidatas, "detector": r.recortes, "despues_del_recorte": r.despues_del_recorte,
           "veredicto": r.veredicto}, d / "resumen.json")


def cargar(raiz: Path | None = None) -> dict:
    """Todo lo guardado; una fase que falta, simplemente no está en el diccionario."""
    base = raiz or DIR_RESULTADOS
    salida: dict = {}
    fechas = {"desde", "hasta", "maximo", "minimo", "recuperado", "fecha"}
    for fase in ("fase3", "fase5", "fase6", "fase7", "fase8"):
        d = base / fase
        if not d.exists():
            continue
        salida[fase] = {}
        for archivo in sorted(d.iterdir()):
            if archivo.suffix == ".csv":
                t = pd.read_csv(archivo)
                for c in t.columns:
                    if c in fechas:
                        t[c] = pd.to_datetime(t[c])
                salida[fase][archivo.stem] = t
            elif archivo.suffix == ".json":
                salida[fase][archivo.stem] = json.loads(archivo.read_text(encoding="utf-8"))
    return salida


def hay_resultados(raiz: Path | None = None) -> bool:
    base = raiz or DIR_RESULTADOS
    return all((base / f).exists() for f in ("fase3", "fase5", "fase7", "fase8"))
