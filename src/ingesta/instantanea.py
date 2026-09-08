"""Reconstruir la base desde el repositorio, sin tocar la red.

El almacén versionado (`src/datos/almacen.py`) existía desde hace tiempo y estaba
bien diseñado: guarda los hechos crudos de XBRL por emisora, de forma determinista
y auditable, y un manifiesto que registra el último filing visto. Lo que faltaba
era conectarlo con la ingesta. `orquestador.py` **no importaba `almacen`**, así
que el camino principal volvía a bajar todo de la SEC cada vez.

Lo que costaba, medido sobre el universo de diez emisoras:

* **810 peticiones** y **128 MB** por arranque en frío.
* **106 segundos** de proceso *aun con las 810 respuestas en caché de disco*, que
  es lo que tarda volver a parsear el JSON de `companyfacts` y los ochocientos
  documentos 8-K.
* En Streamlit Cloud el sistema de archivos es efímero: eso pasa **en cada
  reinicio del contenedor**, no una vez.

Y todo para reconstruir algo que ya estaba en el repositorio: 104,337 filas de
hechos crudos que ocupan **1.5 MB** comprimidos.

Este módulo cierra el círculo. `reconstruir()` arma la base entera desde los
archivos versionados; la red solo hace falta para lo que el repositorio todavía
no tiene —precios, tasas y los filings posteriores al último snapshot—.

Hay una consecuencia que importa más que el ahorro: reconstruir deja de depender
de que la SEC esté arriba y de cuándo se corrió la ingesta. Dos personas con el
mismo commit obtienen la misma base, bit a bit. Eso es lo que permite que un
cambio de taxonomía se pruebe contra el universo completo en segundos, y que el
resultado sea comparable.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from src.config import UNIVERSO_INICIAL, Estado, Fuente
from src.datos.almacen import leer_conciliacion, leer_crudos, leer_hechos_externos
from src.datos.repositorio import Repositorio
from src.ingesta.estados import hechos_de_crudos
from src.ingesta.orquestador import CONCEPTOS_RECONSTRUIBLES, reconstruir_desde_acumulados

# Las fuentes que esta pasada REESCRIBE por completo, y por eso puede borrar. No
# incluye MANUAL ni MERCADO: lo que el usuario capturó y lo que vino del proveedor
# de precios no se reconstruyen desde la instantánea, así que borrarlos sería
# perderlos.
FUENTES_DE_LA_INSTANTANEA = (
    Fuente.SEC_XBRL,
    Fuente.SEC_8K,
    Fuente.DERIVADO,
    Fuente.RECONSTRUIDO,
)


@dataclass
class ResumenInstantanea:
    """Qué se pudo reconstruir desde el repositorio y qué no."""

    hechos: int = 0
    conciliacion: int = 0
    emisoras: list[str] = field(default_factory=list)
    sin_datos: list[str] = field(default_factory=list)

    @property
    def vacia(self) -> bool:
        """No había instantánea que cargar. NO es «no se insertó nada nuevo».

        Los hechos son append-only con deduplicación, así que reconstruir sobre
        una base ya cargada inserta cero y termina bien. Medir el vacío por los
        hechos insertados convertía ese caso —el normal al reconstruir dos veces—
        en un error con el mensaje «corre la ingesta primero», que manda a pagar
        810 peticiones contra la SEC para arreglar algo que no está roto.
        """
        return not self.emisoras

    def como_texto(self) -> str:
        detalle = f"{self.hechos:,} hechos y {self.conciliacion:,} renglones de conciliación"
        cuerpo = f"Reconstrucción desde el repositorio: {detalle}, {len(self.emisoras)} emisoras"
        if self.sin_datos:
            cuerpo += f". Sin instantánea: {', '.join(self.sin_datos)}"
        return cuerpo + "."


def reconstruir(
    repo: Repositorio,
    *,
    tickers: list[str] | None = None,
) -> ResumenInstantanea:
    """Carga a la base los hechos y la conciliación versionados. Cero red.

    Los hechos se **rearman** desde el crudo en vez de guardarse tal cual, y esa
    es la diferencia entre una instantánea y un respaldo: si el catálogo de
    renglones mejora, la misma instantánea produce más datos sin descargar nada.
    """
    resumen = ResumenInstantanea()
    emisores = [e for e in UNIVERSO_INICIAL if tickers is None or e.ticker in set(tickers)]
    repo.registrar_emisores(emisores)

    for e in emisores:
        crudos = leer_crudos(e.ticker)
        if crudos.empty:
            resumen.sin_datos.append(e.ticker)
            continue

        # La proyección se rehace, no se acumula. Las cuatro fuentes que se borran
        # son exactamente las cuatro que esta misma pasada vuelve a escribir —el
        # crudo derivado, el 8-K, los trimestres derivados y los reconstruidos—,
        # y el crudo versionado, que es el registro que P1 protege, no se toca.
        repo.purgar_hechos_derivados(e.ticker, FUENTES_DE_LA_INSTANTANEA)

        hechos = hechos_de_crudos(crudos, e.ticker, e.cik)
        if not hechos.empty:
            filas = hechos.to_dict("records")
            for f in filas:
                f["estado"] = Estado.VALIDO
            resumen.hechos += repo.guardar_hechos(filas)

        # Lo que no se puede rearmar del crudo se carga tal cual: el AFFO y el
        # FFO normalizado viven en el 8-K, no en `companyfacts`.
        externos = leer_hechos_externos(e.ticker)
        if not externos.empty:
            filas = externos.to_dict("records")
            for f in filas:
                f["estado"] = Estado.VALIDO
            resumen.hechos += repo.guardar_hechos(filas)

        conc = leer_conciliacion(e.ticker)
        if not conc.empty:
            resumen.conciliacion += repo.guardar_conciliacion(conc.to_dict("records"))

        # La MISMA pasada que corre la ingesta completa. Sin ella la instantánea
        # quedaba 847 hechos corta, y no en cualquier lado: son los trimestres
        # que se despejan de un acumulado, justo los que sostienen el TTM.
        for concepto in CONCEPTOS_RECONSTRUIBLES:
            reconstruir_desde_acumulados(repo, e.ticker, concepto, asof=dt.date.today())

        resumen.emisoras.append(e.ticker)

    repo.registrar_bitacora("instantanea", resumen.como_texto())
    return resumen
