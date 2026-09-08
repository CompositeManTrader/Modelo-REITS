#!/usr/bin/env python3
"""Instantánea versionada: exportar la base al repositorio, y reconstruirla desde él.

    python scripts/instantanea.py exportar      # de la base al repositorio (usa red)
    python scripts/instantanea.py reconstruir   # del repositorio a la base (SIN red)

Por qué existe
--------------
Reconstruir la base costaba **810 peticiones y 128 MB** contra la SEC, y 106
segundos de proceso aun con todas las respuestas en caché de disco. En Streamlit
Cloud el sistema de archivos es efímero, así que eso pasaba en **cada reinicio
del contenedor**, no una vez.

Lo caro no era el dato: era volver a pedirlo. Los hechos crudos de XBRL ya
estaban versionados en `data/emisoras/` y ocupan unos pocos MB comprimidos. Lo
que faltaba era que la ingesta los usara.

Qué se guarda, y por qué en tres archivos
-----------------------------------------
* ``hechos.csv.gz`` — el crudo de XBRL, tal como lo publicó la SEC. **Se vuelve a
  derivar** en cada reconstrucción, así que una mejora del catálogo de renglones
  entra sola, sin descargar nada.
* ``hechos_externos.csv.gz`` — los hechos que NO salen del crudo: el AFFO, el FFO
  normalizado y sus cifras por acción, que viven en el Exhibit 99.1 del 8-K.
  Rearmarlos exige parsear ochocientos documentos.
* ``conciliacion.csv.gz`` — la cascada del AFFO ya parseada, que es la evidencia
  que la pantalla muestra renglón por renglón.

La separación entre el primero y los otros dos es deliberada: si se guardara todo
junto, la instantánea le ganaría al catálogo nuevo por la llave única de la tabla
y las mejoras del modelo dejarían de verse.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import UNIVERSO_INICIAL, asegurar_directorios  # noqa: E402
from src.datos import esquema  # noqa: E402
from src.datos.almacen import (  # noqa: E402
    escribir_conciliacion,
    escribir_crudos,
    escribir_hechos_externos,
)
from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta.edgar import ClienteEdgar  # noqa: E402
from src.ingesta.estados import (  # noqa: E402
    etiquetas_de_instancia,
    hechos_crudos,
    hechos_de_crudos,
)
from src.ingesta.instancia import descargar_instancias  # noqa: E402
from src.ingesta.instantanea import reconstruir  # noqa: E402

COLUMNAS_CONCILIACION = [
    "ticker", "periodo_tipo", "fecha_dato", "fecha_publicacion", "orden",
    "linea", "etiqueta", "valor", "signo", "fuente", "url_filing",
]
COLUMNAS_HECHOS = [
    "ticker", "concepto", "periodo_tipo", "periodo_inicio", "fecha_dato",
    "fecha_publicacion", "valor", "unidad", "fuente", "es_primario",
    "url_filing", "accession",
]


def exportar(repo: Repositorio, tickers: list[str] | None) -> int:
    """Escribe la instantánea al repositorio desde una base ya ingestada."""
    cliente = ClienteEdgar()
    emisores = [e for e in UNIVERSO_INICIAL if tickers is None or e.ticker in set(tickers)]

    for e in emisores:
        # El crudo se baja COMPLETO, sin ventana. Guardarlo desde 2019 recortaba
        # la historia de setenta trimestres a treinta, y la Puerta 2 exige doce
        # observaciones de la prima para dar un percentil confiable: la
        # instantánea corta habría cambiado velocidad por veredictos.
        crudos = hechos_crudos(cliente.companyfacts(e.cik), e.ticker, desde=None)

        # Las etiquetas de EXTENSIÓN no están en `companyfacts` y hay que leerlas
        # del documento XBRL de cada filing. Se pagan una vez, aquí, y quedan
        # versionadas junto al resto: reconstruir sigue sin tocar la red.
        extension = descargar_instancias(
            cliente, e.ticker, e.cik, etiquetas_de_instancia(e.ticker)
        )
        if not extension.empty:
            crudos = pd.concat([crudos, extension], ignore_index=True)
        huella = escribir_crudos(e.ticker, crudos)

        # Lo derivable del crudo NO se guarda aparte: se recalcula. Lo que se
        # guarda es exactamente su complemento — y el complemento se calcula por
        # CELDA, no por concepto.
        #
        # Excluir por nombre de concepto parecía equivalente y no lo es: la
        # utilidad neta la producen los dos caminos, pero no para los mismos
        # periodos. Descartar todas sus filas porque el nombre "es derivable"
        # tiraba 1,767 hechos que el crudo no vuelve a producir, entre ellos
        # trimestres enteros que solo aparecen en el 8-K.
        rearmados = hechos_de_crudos(crudos, e.ticker, e.cik)
        derivables = set(
            zip(
                rearmados["concepto"], rearmados["periodo_tipo"], rearmados["fecha_dato"],
                rearmados["fecha_publicacion"], rearmados["fuente"], strict=True,
            )
        ) if not rearmados.empty else set()

        with repo.motor.connect() as cx:
            hechos = pd.read_sql(
                select(esquema.hechos).where(esquema.hechos.c.ticker == e.ticker), cx
            )
            conc = pd.read_sql(
                select(esquema.conciliacion).where(esquema.conciliacion.c.ticker == e.ticker), cx
            )

        if hechos.empty:
            externos = hechos
        else:
            llave = list(
                zip(
                    hechos["concepto"], hechos["periodo_tipo"],
                    pd.to_datetime(hechos["fecha_dato"]).dt.date,
                    pd.to_datetime(hechos["fecha_publicacion"]).dt.date,
                    hechos["fuente"], strict=True,
                )
            )
            externos = hechos[[k not in derivables for k in llave]]
        if not externos.empty:
            externos = externos[COLUMNAS_HECHOS].sort_values(
                ["concepto", "periodo_tipo", "fecha_dato", "fecha_publicacion"]
            )
            escribir_hechos_externos(e.ticker, externos)
        if not conc.empty:
            conc = conc[COLUMNAS_CONCILIACION].sort_values(
                ["fecha_dato", "fecha_publicacion", "orden", "linea"]
            )
            escribir_conciliacion(e.ticker, conc)

        print(
            f"  {e.ticker:6} crudos {len(crudos):>7,} ({huella[:10]}) · "
            f"externos {len(externos):>6,} · conciliación {len(conc):>5,}"
        )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("accion", choices=("exportar", "reconstruir"))
    p.add_argument("--tickers", help="Lista separada por comas. Por omisión, todo el universo.")
    p.add_argument("--bd", default=None, help="Ruta de la base SQLite.")
    args = p.parse_args()

    asegurar_directorios()
    repo = Repositorio(ruta=args.bd) if args.bd else Repositorio()
    tickers = args.tickers.split(",") if args.tickers else None

    if args.accion == "exportar":
        print(f"Exportando la instantánea ({dt.date.today()}):")
        return exportar(repo, tickers)

    print("Reconstruyendo desde el repositorio, sin red:")
    resumen = reconstruir(repo, tickers=tickers)
    print("  " + resumen.como_texto())
    if resumen.vacia:
        print("\nNo hay instantánea que cargar. Corre `python scripts/ingesta.py` primero.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
