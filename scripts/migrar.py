#!/usr/bin/env python3
"""Mover la base de un motor a otro, casi siempre de SQLite a Postgres.

    python scripts/migrar.py --destino "postgresql://usuario:clave@host/reits"
    python scripts/migrar.py --origen data/reit.db --destino "$REIT_DB" --verificar

Por qué existe
--------------
La base vive en un archivo dentro de la máquina que corre la aplicación, y en
Streamlit Cloud esa máquina se recicla. Cada vez que la página se abre en frío el
archivo ya no está, así que hay que reconstruirlo entero: **176 segundos** de
descargas y parseo para volver a tener exactamente lo que había ayer. Lo que de
verdad cambia de un día para otro son los precios y las tasas, que son
diecinueve. El resto es trabajo repetido porque el disco no se acuerda de nada.

Un Postgres administrado se acuerda. Este script es el puente de una sola vez:
copia lo que ya se construyó en vez de volver a construirlo desde la SEC.

Qué NO hace
-----------
No toca el origen. No borra nada en el destino. Se puede correr dos veces sin
duplicar, porque la escritura del repositorio ignora la llave repetida en el
motor —la misma propiedad que hace que re-correr la ingesta sea inofensivo—. Si
se interrumpe a la mitad, se vuelve a correr y sigue donde iba.

Los identificadores
-------------------
Se copian tal cual, y al final se reacomoda el contador de cada tabla en
Postgres. Sin eso el contador seguiría en uno y el primer hecho nuevo chocaría
contra un identificador que ya existe. No hay llaves foráneas en el esquema, así
que conservarlos no es obligatorio; se hace porque una copia fiel es más fácil de
auditar que una renumerada.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from sqlalchemy import func, select, text

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.config import RUTA_BD  # noqa: E402
from src.datos import esquema  # noqa: E402
from src.datos.repositorio import Repositorio, crear_motor, url_del_motor  # noqa: E402

# Filas por viaje. Contra una base remota el costo dominante es la latencia, no
# el volumen: lotes chicos multiplican los viajes de ida y vuelta.
POR_VIAJE = 2_000


def sin_credenciales(url: str) -> str:
    """La URL sin usuario ni contraseña, para poder imprimirla."""
    if not url.startswith("postgresql"):
        return url
    return url.split("://")[0] + "://" + url.split("@")[-1].split("?")[0]


def contar(motor, tabla) -> int:
    with motor.connect() as cx:
        return int(cx.execute(select(func.count()).select_from(tabla)).scalar_one())


def copiar_tabla(origen, destino: Repositorio, tabla) -> int:
    """Copia una tabla por tramos. Devuelve cuántas filas nuevas quedaron escritas."""
    escritas = 0
    with origen.connect() as cx:
        resultado = cx.execution_options(stream_results=True).execute(select(tabla))
        while tramo := resultado.fetchmany(POR_VIAJE):
            escritas += destino.copiar_filas(tabla, [dict(f._mapping) for f in tramo])
    return escritas


def reacomodar_contadores(motor) -> None:
    """Deja el contador de cada tabla arriba del identificador más alto copiado.

    Solo aplica a Postgres: SQLite deduce el siguiente identificador del máximo
    que encuentra, así que no tiene contador que se pueda quedar atrás.
    """
    if motor.dialect.name != "postgresql":
        return
    with motor.begin() as cx:
        for tabla in esquema.metadata.sorted_tables:
            if "id" not in tabla.c:
                continue
            cx.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence(:t, 'id'), "
                    "COALESCE((SELECT MAX(id) FROM " + tabla.name + "), 1))"
                ),
                {"t": tabla.name},
            )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--origen",
        default=None,
        help="Base de partida. Por omisión, la que use REIT_DB (hoy el archivo local).",
    )
    p.add_argument("--destino", required=True, help="URL del motor de llegada.")
    p.add_argument(
        "--verificar",
        action="store_true",
        help="Al terminar, vuelve a contar las dos bases y exige que coincidan.",
    )
    args = p.parse_args()

    origen_url = url_del_motor(args.origen if args.origen else RUTA_BD)
    destino_url = url_del_motor(args.destino)
    if origen_url == destino_url:
        print("El origen y el destino son la misma base.", file=sys.stderr)
        return 2

    # Una cadena de Postgres trae usuario y contraseña, y esto se pega en chats y
    # en tickets. Se dice a dónde va, no con qué se entra. Vale para los dos
    # lados: el script sirve igual para traerse la base del servidor a la laptop.
    print(f"origen : {sin_credenciales(origen_url)}")
    print(f"destino: {sin_credenciales(destino_url)}\n")

    motor_origen = crear_motor(origen_url, crear=False)
    destino = Repositorio(motor=crear_motor(destino_url))

    t0 = time.perf_counter()
    total = 0
    for tabla in esquema.metadata.sorted_tables:
        hay = contar(motor_origen, tabla)
        if not hay:
            print(f"  {tabla.name:16s}        — vacía")
            continue
        marca = time.perf_counter()
        escritas = copiar_tabla(motor_origen, destino, tabla)
        total += escritas
        nota = "" if escritas == hay else f"  ({hay - escritas:,} ya estaban)"
        print(f"  {tabla.name:16s} {escritas:>9,} en {time.perf_counter() - marca:5.1f}s{nota}")

    reacomodar_contadores(destino.motor)
    print(f"\n{total:,} filas copiadas en {time.perf_counter() - t0:.1f}s")

    if args.verificar:
        print("\nverificación:")
        desiguales = []
        for tabla in esquema.metadata.sorted_tables:
            a, b = contar(motor_origen, tabla), contar(destino.motor, tabla)
            marca = "ok" if a == b else "NO COINCIDE"
            if a != b:
                desiguales.append(tabla.name)
            print(f"  {tabla.name:16s} origen {a:>9,}   destino {b:>9,}   {marca}")
        if desiguales:
            print(f"\nNo coinciden: {', '.join(desiguales)}", file=sys.stderr)
            return 1
        print("\nLas dos bases tienen exactamente lo mismo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
