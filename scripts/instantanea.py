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
    escribir_reportados,
)
from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta.edgar import ClienteEdgar  # noqa: E402
from src.ingesta.estados import (  # noqa: E402
    etiquetas_de_instancia,
    etiquetas_del_catalogo,
    hechos_crudos,
    hechos_de_crudos,
)
from src.ingesta.instancia import (  # noqa: E402
    descargar_instancias,
    rellenar_filing_rezagado,
)
from src.ingesta.instantanea import reconstruir  # noqa: E402
from src.ingesta.reportados import descargar_reportados  # noqa: E402

COLUMNAS_CONCILIACION = [
    "ticker", "periodo_tipo", "fecha_dato", "fecha_publicacion", "orden",
    "linea", "etiqueta", "valor", "signo", "fuente", "url_filing",
]
COLUMNAS_HECHOS = [
    "ticker", "concepto", "periodo_tipo", "periodo_inicio", "fecha_dato",
    "fecha_publicacion", "valor", "unidad", "fuente", "es_primario",
    "url_filing", "accession",
]


def armar_crudos(cliente, ticker: str, cik: str) -> pd.DataFrame:
    """Junta los tres caminos que producen hechos crudos de XBRL.

    Está aparte de `exportar` porque el orden entre los tres importa y no se ve:
    el segundo camino puede tapar al tercero, y taparlo no rompe nada visible
    —los números salen, nada más que viejos—. Aislarlo permite probarlo.
    """
    # El crudo se baja COMPLETO, sin ventana. Guardarlo desde 2019 recortaba la
    # historia de setenta trimestres a treinta, y la Puerta 2 exige doce
    # observaciones de la prima para dar un percentil confiable: la instantánea
    # corta habría cambiado velocidad por veredictos.
    del_api = hechos_crudos(cliente.companyfacts(cik), ticker, desde=None)

    # Las etiquetas de EXTENSIÓN no están en `companyfacts` y hay que leerlas del
    # documento XBRL de cada filing. Se pagan una vez, aquí, y quedan versionadas
    # junto al resto: reconstruir sigue sin tocar la red.
    extension = descargar_instancias(cliente, ticker, cik, etiquetas_de_instancia(ticker))

    # Y el filing que `companyfacts` todavía no publica. La API se atrasa POR
    # EMISOR y sin avisar: al 8 de septiembre de 2026 daba marzo como el último
    # corte de Prologis y Welltower, más de un mes después de sus 10-Q de junio.
    # El atraso es parcial ENTRE FUENTES —el AFFO del trimestre sí entra, porque
    # viene del 8-K— así que el apalancamiento mezclaba una deuda vieja con un
    # flujo nuevo y el ratio salía plausible.
    #
    # Se le pasa `del_api`, no el crudo ya concatenado: la guarda pregunta si la
    # API tiene el filing, y `descargar_instancias` acaba de leer ESE MISMO
    # documento para las extensiones de O y de EXR. Con el crudo concatenado la
    # guarda se contestaría a sí misma, y el rezago quedaría tapado justo en las
    # dos emisoras que más caminos usan.
    #
    # No cuesta una petición cuando la API está al día: la decisión se toma con el
    # índice de filings, que es barato, y solo se baja el documento XBRL de los
    # reportes que la API todavía no tiene.
    rezagado = rellenar_filing_rezagado(
        cliente, ticker, cik, del_api, etiquetas_del_catalogo(ticker)
    )

    # Los dos caminos leen el MISMO documento cuando la API va atrasada en una
    # emisora con etiquetas propias, así que el hecho de extensión llega dos
    # veces. Se deduplican entre ellos y no contra la API: contra la API no hace
    # falta —la guarda por accession garantiza que no se solapan— y hacerlo podría
    # tirar un hecho legítimo de dos filings presentados el mismo día.
    de_instancia = [p for p in (extension, rezagado) if not p.empty]
    if not de_instancia:
        return del_api
    instancia = pd.concat(de_instancia, ignore_index=True).drop_duplicates(
        ["tag", "periodo_tipo", "fecha_dato", "fecha_publicacion"]
    )
    return pd.concat([del_api, instancia], ignore_index=True)


def exportar(repo: Repositorio, tickers: list[str] | None) -> int:
    """Escribe la instantánea al repositorio desde una base ya ingestada."""
    cliente = ClienteEdgar()
    emisores = [e for e in UNIVERSO_INICIAL if tickers is None or e.ticker in set(tickers)]

    for e in emisores:
        crudos = armar_crudos(cliente, e.ticker, e.cik)
        huella = escribir_crudos(e.ticker, crudos)

        # Los estados TAL COMO los publicó la emisora, del renderizado que la
        # propia SEC hace de su XBRL. Se versionan aquí por la misma razón que la
        # conciliación: son cuatro peticiones por filing —el resumen y los tres
        # estados— y sin guardarlos, cada arranque del contenedor las volvería a
        # pagar. La escala de cada renglón se verifica contra el crudo que se
        # acaba de armar, así que este orden importa.
        reportados = descargar_reportados(cliente, e.ticker, e.cik, crudos=crudos)
        if not reportados.empty:
            escribir_reportados(e.ticker, reportados)

        # Lo derivable del crudo NO se guarda aparte: se recalcula. Lo que se
        # guarda es exactamente su complemento — y el complemento se calcula por
        # CELDA, no por concepto.
        #
        # Excluir por nombre de concepto parecía equivalente y no lo es: la
        # utilidad neta la producen los dos caminos, pero no para los mismos
        # periodos. Descartar todas sus filas porque el nombre "es derivable"
        # tiraba 1,767 hechos que el crudo no vuelve a producir, entre ellos
        # trimestres enteros que solo aparecen en el 8-K.
        # Rehacer la proyección ANTES de leer la base, o el complemento sale mal.
        #
        # Lo que se guarda como "externo" es lo que la base tiene y el crudo no
        # reproduce. Si la base trae filas de un catálogo VIEJO —las que dejó de
        # producir el catálogo nuevo— parecen externas y se congelan en el archivo
        # versionado como si vinieran de un 8-K. Pasó al mapear la revolvente de
        # Realty Income: 87 saldos de `LineOfCredit` de 2009 a 2020 entraron al
        # archivo de externos y ahí se habrían quedado para siempre, ganándole al
        # catálogo por la llave point-in-time.
        #
        # AQUÍ SE RECONSTRUÍA ANTES DE LEER LA BASE, y se quitó. Vale la pena
        # dejar escrito por qué, porque la idea era razonable.
        #
        # Reconstruir dejaba la base en el estado que produce el catálogo vigente,
        # y con eso la exportación quedaba idempotente. El problema es que
        # reconstruir PURGA, y purgar borra todo lo que la instantánea todavía no
        # tiene. La secuencia natural —correr `scripts/ingesta.py` y exportar
        # enseguida— revertía la ingesta recién bajada: al ampliar la ventana de
        # comunicados de ocho a veinte, la historia de AFFO de NNN pasó de once
        # observaciones de prima a veinte, y la exportación siguiente la devolvió a
        # once y guardó esa versión corta como si fuera la buena.
        #
        # En silencio y perdiendo datos, que es la peor combinación. La
        # contaminación que evitaba —filas de un catálogo viejo congeladas como si
        # fueran externas— es real, pero es recuperable y ahora se DETECTA en vez
        # de prevenirse destruyendo: ver el aviso de abajo.
        #
        # Un intento intermedio también falló y conviene no repetirlo: comparar la
        # última fecha de publicación de los dos lados NO detecta este caso.
        # Profundizar la historia agrega hechos VIEJOS, así que el máximo no se
        # mueve y la guarda no dispara.

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

        # El aviso que reemplaza a la purga. Una fila SALDO —`PUNTUAL`— que sale
        # del crudo de XBRL nunca viene de un 8-K: si aparece como externa es que
        # el catálogo dejó de producirla y se va a congelar en el archivo
        # versionado, donde le ganará al catálogo por la llave point-in-time.
        #
        # No se borra, se DICE. Borrar es lo que costó una ingesta entera.
        sospechosas = (
            externos[
                (externos["periodo_tipo"] == "PUNTUAL")
                & (~externos["concepto"].isin(set(rearmados["concepto"])))
            ]
            if not externos.empty and not rearmados.empty
            else externos.iloc[:0]
        )
        if not sospechosas.empty:
            print(
                f"  {e.ticker:6} AVISO: {len(sospechosas)} saldo(s) de "
                f"{sorted(set(sospechosas['concepto']))} se guardarán como externos "
                "y el catálogo ya no los produce. Revisa si sobran."
            )

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
