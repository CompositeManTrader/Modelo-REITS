"""Hechos publicados en la escala equivocada.

El problema
===========
``companyfacts`` entrega el número tal como la emisora lo etiquetó, y a veces la
emisora etiqueta el número que IMPRIMIÓ en un estado cuyo encabezado dice «in
thousands», sin volverlo a dólares. La unidad declarada sigue diciendo ``USD``,
así que nada truena: entra un ingreso trimestral de 8,151 dólares donde son
8,151,000, y el margen operativo del trimestre sale en 62,787%.

Es el error silencioso de manual: la celda tiene número, tiene unidad, tiene
fuente primaria y tiene un filing que la respalda. Solo está mil veces mal.

Por qué no se corrige el número
===============================
Se **marca** la versión como ``SOSPECHOSA`` y no se escribe una corregida. Multiplicar
por mil daría un número que no aparece en ningún filing, y este modelo prefiere
un hueco a una cifra inventada con formato de dato. Marcarla tiene además un
efecto que corregirla no tendría: ``Repositorio.hechos`` filtra por estado ANTES
de elegir la versión vigente, así que la celda cae sola a la versión anterior
—que es una observación de verdad— cuando existe. Cuando no existe, queda vacía,
que es lo correcto.

Qué evidencia se exige
======================
Distinguir una escala rota de un dato real es difícil por una razón concreta: un
REIT chico crece mil veces en tres años, un flujo trimestral puede ser casi cero,
y el efectivo de NNN se mueve entre 1.1 y 607 millones sin que nada esté mal. Una
regla que solo mire «este número es mil veces más chico que sus vecinos» marca
los tres y no sirve.

Se piden **tres condiciones a la vez**:

1. **La serie sabe su escala.** En la ventana de cortes vecinos, una moda de
   exponente tiene que cubrir al menos el 80% de los CORTES —contados por corte y
   no por fila, porque un corte con dos versiones, una buena y una en miles,
   sigue sabiendo cuál es su escala—. Una serie suelta no acusa a nadie.
2. **La moda está atestiguada de los dos lados.** Antes y después del corte en
   duda. Es lo que separa una anomalía de un crecimiento: Global Net Lease pasó
   de facturar 245 mil dólares por semestre en 2013 a 245 millones en 2016, y ese
   mil es real. Un crecimiento solo tiene moda de un lado.
3. **El desvío viene acompañado.** Un error de escala nunca viene solo: quien
   etiqueta un renglón en miles etiqueta la SECCIÓN en miles. Se exige otro
   concepto del MISMO filing y el MISMO corte con el mismo desvío, o —lo que vale
   igual— que una identidad contable del propio filing se rompa con el número
   como está y se arregle al dividirlo entre mil. Esta condición es la que salva
   del falso positivo: la emisión de acciones de 150 mil dólares de Agree Realty
   en el primer trimestre de 2017 es real, y se sabe porque el flujo de operación
   y el pago de deuda del mismo filing están en dólares.

Lo que se deja pasar a propósito
================================
Con estas tres, tres errores reales del universo actual quedan sin marcar: la
deuda de PSA en dos portadas de 2013 y 2016 —un conteo de acciones en miles, solo
en su filing— y la emisión de ADC del cuarto trimestre de 2023. Ninguno viene
acompañado. Se prefiere el falso negativo: marcar de más borra datos buenos, y
un dato bueno borrado no deja rastro.

El estado NO es point-in-time
=============================
``estado`` describe la calidad de un registro, no lo que se sabía en una fecha, y
se decide con todo lo que hoy se conoce —igual que ``cuadrar_affo`` o
``validar_registro``, que también marcan filas viejas—. Marcar no devuelve
información del futuro: retira una que no debió existir.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

# Las dos escalas que un filer imprime en el encabezado de un estado. No hay una
# tercera: nadie publica en centenas ni en miles de millones.
POTENCIAS = (3, 6)

# Cuántos cortes vecinos forman la referencia, de cada lado.
VENTANA = 6
MINIMO_CORTES = 5

# Qué tan apretada tiene que estar la serie para poder acusar. Ocho de cada diez
# cortes en la misma década de magnitud.
FRACCION_MODA = 0.8

# Identidades del balance que valen como testigo. La deuda cabe en el pasivo y el
# pasivo cabe en el activo: no es una regla del modelo, es contabilidad. Si el
# número como está las rompe y dividido entre mil las cumple, el propio filing
# está diciendo en qué escala venía.
CONTENCIONES: tuple[tuple[str, str], ...] = (
    ("deuda_total", "pasivos_totales"),
    ("pasivos_totales", "activos_totales"),
    ("capital_total", "activos_totales"),
)

# Un punto y medio de holgura: los estados redondean a miles y la suma arrastra.
HOLGURA_CONTENCION = 0.005


@dataclass(frozen=True)
class FueraDeEscala:
    """Una versión de un hecho que no está en la escala de su propia serie."""

    id: int
    ticker: str
    concepto: str
    periodo_tipo: str
    fecha_dato: dt.date
    fecha_publicacion: dt.date
    accession: str | None
    valor: float
    unidad: str
    desvio: int                    # exponente del hecho − exponente de la serie
    testigos: tuple[str, ...]      # qué más del mismo filing lo confirma

    @property
    def factor(self) -> float:
        """Por cuánto habría que multiplicarlo para volver a la escala de la serie."""
        return 10.0 ** (-self.desvio)

    def nota(self) -> str:
        unidad = {3: "mil", 6: "un millón"}[abs(self.desvio)]
        if self.desvio < 0:
            como = (f"el filing etiquetó la cifra impresa —el estado venía "
                    f"«en {'miles' if abs(self.desvio) == 3 else 'millones'}»— "
                    f"sin volverla a dólares")
        else:
            como = f"el filing etiquetó la cifra multiplicada por {unidad}"
        return (
            f"Escala: {self.valor:,.0f} está {unidad} veces "
            f"{'por debajo' if self.desvio < 0 else 'por encima'} de la magnitud de "
            f"su propia serie. La unidad declarada sigue siendo «{self.unidad}», "
            f"así que nada truena: "
            f"{como}. Testigos del mismo filing: {'; '.join(self.testigos)}. "
            f"No se corrige el número —sería una cifra que no aparece en ningún "
            f"filing—: se descarta esta versión y queda vigente la anterior, si la hay."
        )


def _exponente(valores: pd.Series) -> pd.Series:
    """La década de magnitud, redondeada.

    Redondear y no truncar centra la banda en la mitad geométrica: dos valores
    tienen que separarse por más de 316 veces para caer en décadas distintas. Es
    justo lo que se quiere —una escala rota separa por mil— y evita que dos
    números vecinos de 999 y 1,001 salgan en décadas distintas.
    """
    return np.round(np.log10(valores.abs())).astype(int)


# Cuánto puede moverse un valor entre dos versiones y seguir siendo el MISMO
# número en otra escala. Una reexpresión mueve porcentajes; una escala, mil.
TOLERANCIA_ENTRE_VERSIONES = 0.30


@dataclass(frozen=True)
class _Corte:
    """Las versiones que una serie publicó de un mismo corte, en arreglos.

    Un corte trae normalmente una fila y a veces tres —el dato original y sus
    reexpresiones—, así que estos arreglos son diminutos. Existen para que la
    ventana deje de rebanar un DataFrame: cada máscara de pandas sobre catorce
    mil filas cuesta más que todo el trabajo que se hace con el resultado.
    """

    id: np.ndarray
    valor: np.ndarray
    exponente: np.ndarray
    fecha_publicacion: np.ndarray
    accession: np.ndarray
    unidad: np.ndarray


def _partir_por_corte(serie: pd.DataFrame) -> tuple[list, list[_Corte]]:
    """Los cortes de la serie en orden, y las filas de cada uno.

    El orden dentro del corte se conserva —``kind="stable"``— porque `_desvio`
    recorre las versiones y devuelve la primera que explica el desvío: reordenar
    ahí cambiaría cuál gana.
    """
    fechas = serie["fecha_dato"].to_numpy()
    orden = np.argsort(fechas, kind="stable")
    fechas = fechas[orden]
    if "unidad" in serie.columns:
        unidades = serie["unidad"].to_numpy()[orden]
    else:
        unidades = np.array([""] * len(serie), dtype=object)
    columnas = {
        "id": serie["id"].to_numpy()[orden],
        "valor": serie["valor"].to_numpy()[orden],
        "exponente": serie["exponente"].to_numpy()[orden],
        "fecha_publicacion": serie["fecha_publicacion"].to_numpy()[orden],
        "accession": serie["accession"].to_numpy()[orden],
        "unidad": unidades,
    }
    # Dónde empieza cada corte: el arreglo ya viene ordenado, así que un corte es
    # un tramo contiguo y basta con las fronteras.
    cortes, inicios = np.unique(fechas, return_index=True)
    fines = [*inicios[1:], len(fechas)]
    bloques = [
        _Corte(**{nombre: col[a:b] for nombre, col in columnas.items()})
        for a, b in zip(inicios, fines, strict=True)
    ]
    return list(cortes), bloques


def _desvio(bloque: _Corte, k: int, moda: int) -> int | None:
    """Por cuántas décadas se aparta el hecho ``k`` de la escala de su serie.

    Dos caminos, y el segundo no sobra. El primero compara la década del hecho
    contra la de la serie, y falla justo donde el trimestre es atípico: la
    utilidad de Agree Realty del tercer trimestre de 2011 fue una PÉRDIDA de 1.9
    millones donde la serie gana 4.7, así que su década es 6 y la de la serie 7,
    y el desvío sale de 4 en vez de 3 aunque el error sea exactamente de mil.

    El segundo camino compara contra OTRA VERSIÓN de la misma celda: −1,855 y
    −1,855,345 son el mismo número en dos escalas, y eso no lo puede producir una
    reexpresión. Cuando existe esa versión, manda ella.
    """
    valor = abs(float(bloque.valor[k]))
    for j in range(len(bloque.id)):
        # La otra versión no tiene que estar EN la moda, solo cerca: un trimestre
        # atípico —una pérdida donde la serie gana— vive una década abajo sin que
        # eso lo vuelva sospechoso. Lo que se le pide es no ser la anomalía.
        if j == k or abs(int(bloque.exponente[j]) - moda) >= min(POTENCIAS):
            continue
        razon = abs(float(bloque.valor[j])) / valor if valor else 0.0
        for potencia in POTENCIAS:
            for signo in (1, -1):
                esperado = 10.0 ** (signo * potencia)
                if abs(razon / esperado - 1) <= TOLERANCIA_ENTRE_VERSIONES:
                    return -signo * potencia
    desvio = int(bloque.exponente[k]) - moda
    return desvio if abs(desvio) in POTENCIAS else None


def _moda(exponentes: np.ndarray) -> int:
    """El exponente más frecuente de la ventana; en empate, el más chico.

    El empate se resuelve a la baja y no al azar, y no es un detalle de
    implementación: la moda es la escala que se le atribuye a la serie, y de ella
    sale a quién se acusa. Preferir el exponente CHICO acusa a los valores
    grandes —el filing que multiplicó por mil— y deja pasar a los chicos, que es
    el lado por el que este detector prefiere equivocarse.
    """
    valores, cuentas = np.unique(exponentes, return_counts=True)
    # `np.unique` devuelve los valores ordenados de menor a mayor, y `argmax` se
    # queda con el primer máximo: eso ES el desempate a la baja.
    return int(valores[int(np.argmax(cuentas))])


def _candidatos(hechos: pd.DataFrame) -> pd.DataFrame:
    """Filas cuyo exponente se aparta del de su serie por una potencia de mil.

    La ventana se recorre sobre ARREGLOS y no sobre máscaras de pandas. Es la
    misma regla —la de las tres condiciones del encabezado, sin cambio— pero
    cada serie se parte por corte UNA vez, y de ahí en adelante la ventana es
    aritmética de índices sobre listas de a lo más trece cortes.

    Importa porque este detector corre en cada arranque de la aplicación: la
    instantánea rearma la proyección desde el crudo, así que la revisión de
    escala tiene que volver a correr o el margen de Agree Realty regresa a
    62,787%. Con máscaras costaba 33 segundos por emisora —330 del arranque,
    cinco minutos y medio en los que Streamlit Cloud da por muerta a la
    aplicación y la reinicia—. Sobre arreglos son décimas.
    """
    filas = []
    for (tk, con, tipo), serie in hechos.groupby(["ticker", "concepto", "periodo_tipo"], sort=False):
        cortes, bloques = _partir_por_corte(serie)
        if len(cortes) < MINIMO_CORTES + 1:
            continue
        # El conjunto de exponentes de cada corte, una sola vez: es lo único que
        # las tres condiciones le preguntan a los vecinos.
        exponentes_de = [frozenset(b.exponente.tolist()) for b in bloques]
        for i, corte in enumerate(cortes):
            izquierda = range(max(0, i - VENTANA), i)
            derecha = range(i + 1, min(len(cortes), i + 1 + VENTANA))
            vecinos = [*izquierda, *derecha]
            if len(vecinos) < MINIMO_CORTES:
                continue
            moda = _moda(np.concatenate([bloques[j].exponente for j in vecinos]))
            # Condición 1: la serie sabe su escala. Se cuenta por CORTE, no por
            # fila: un corte con dos versiones, una buena y una en miles, sigue
            # sabiendo cuál es la suya.
            apoyo = sum(1 for j in vecinos if moda in exponentes_de[j]) / len(vecinos)
            if apoyo < FRACCION_MODA:
                continue
            # Condición 2: atestiguada de los dos lados. Los cortes están
            # ordenados, así que «antes» y «después» son las dos mitades de la
            # ventana y no hacen falta comparaciones de fecha.
            if not any(moda in exponentes_de[j] for j in izquierda):
                continue
            if not any(moda in exponentes_de[j] for j in derecha):
                continue
            bloque = bloques[i]
            for k in range(len(bloque.id)):
                desvio = _desvio(bloque, k, moda)
                if desvio is None:
                    continue
                filas.append({
                    "id": int(bloque.id[k]), "ticker": tk, "concepto": con,
                    "periodo_tipo": tipo, "fecha_dato": corte,
                    "fecha_publicacion": bloque.fecha_publicacion[k],
                    "accession": bloque.accession[k], "valor": float(bloque.valor[k]),
                    "unidad": bloque.unidad[k], "desvio": desvio,
                })
    return pd.DataFrame(filas)


def _rompe_una_identidad(hechos: pd.DataFrame, fila: pd.Series) -> str | None:
    """¿El propio filing dice que este número no cabe donde debería?

    Devuelve el nombre de la identidad rota cuando el número como está la viola y
    dividido por su potencia la cumple. Es un testigo que no necesita a nadie
    más: no es una comparación con otros periodos, es contabilidad del mismo
    corte y del mismo documento.
    """
    del_filing = hechos[
        (hechos["ticker"] == fila["ticker"])
        & (hechos["accession"] == fila["accession"])
        & (hechos["fecha_dato"] == fila["fecha_dato"])
    ]
    if del_filing.empty:
        return None
    valor_de = dict(zip(del_filing["concepto"], del_filing["valor"], strict=False))
    corregido = float(fila["valor"]) * 10.0 ** (-int(fila["desvio"]))
    for dentro, fuera in CONTENCIONES:
        if fila["concepto"] != dentro or fuera not in valor_de:
            continue
        limite = float(valor_de[fuera]) * (1 + HOLGURA_CONTENCION)
        if abs(float(fila["valor"])) > limite >= abs(corregido):
            return (f"«{dentro}» no cabe en «{fuera}» del mismo corte "
                    f"({float(valor_de[fuera]):,.0f}) y corregido sí")
    return None


def detectar_fuera_de_escala(hechos: pd.DataFrame) -> list[FueraDeEscala]:
    """Las versiones que no están en la escala de su serie, con su testigo.

    ``hechos`` tiene que traer TODAS las versiones —``vigentes=False``— porque la
    evidencia vive justamente en tener la misma celda publicada dos veces.
    """
    if hechos is None or hechos.empty:
        return []
    h = hechos[hechos["valor"].notna() & (hechos["valor"] != 0)].copy()
    if h.empty:
        return []
    h["exponente"] = _exponente(h["valor"])
    candidatos = _candidatos(h)
    if candidatos.empty:
        return []

    # Testigo 1: otro concepto del mismo filing y el mismo corte con el mismo desvío.
    llave = ["ticker", "accession", "fecha_dato", "desvio"]
    acompana = candidatos.groupby(llave)["concepto"].apply(lambda s: sorted(set(s)))

    hallazgos: list[FueraDeEscala] = []
    for _, fila in candidatos.iterrows():
        clave = tuple(fila[c] for c in llave)
        companeros = [c for c in acompana.get(clave, []) if c != fila["concepto"]]
        testigos = []
        if companeros:
            testigos.append(
                "«" + "», «".join(companeros) + "» del mismo corte, con el mismo desvío"
            )
        identidad = _rompe_una_identidad(h, fila)
        if identidad:
            testigos.append(identidad)
        if not testigos:
            continue
        hallazgos.append(FueraDeEscala(
            id=int(fila["id"]), ticker=str(fila["ticker"]), concepto=str(fila["concepto"]),
            periodo_tipo=str(fila["periodo_tipo"]),
            fecha_dato=pd.Timestamp(fila["fecha_dato"]).date(),
            fecha_publicacion=pd.Timestamp(fila["fecha_publicacion"]).date(),
            accession=fila["accession"], valor=float(fila["valor"]),
            unidad=str(fila["unidad"] or ""), desvio=int(fila["desvio"]),
            testigos=tuple(testigos),
        ))
    return hallazgos


def resumir(hallazgos: list[FueraDeEscala]) -> str:
    if not hallazgos:
        return "Ningún hecho fuera de escala."
    emisoras = sorted({h.ticker for h in hallazgos})
    return (
        f"{len(hallazgos)} hecho(s) fuera de escala en {len(emisoras)} emisora(s): "
        + ", ".join(emisoras)
    )
