"""Verificación de los estados financieros descargados.

"Sin errores" no es una promesa: es una lista de comprobaciones que corren en cada
descarga y que pueden reprobar. Este módulo es esa lista.

Las comprobaciones se eligieron por un criterio: **que cacen errores silenciosos**,
los que no levantan excepción y dejan un número plausible en pantalla. Un balance
que no cuadra por dos millones no truena nada; simplemente significa que alguna
línea se está leyendo de la etiqueta equivocada, y todo lo que se derive de ahí
—apalancamiento, NAV, cobertura— hereda el error.

Cada incidencia tiene severidad, y la distinción importa:

* ``ERROR`` — el dato es inconsistente consigo mismo. No se debe usar.
* ``AVISO`` — algo que un analista querría saber, sin que invalide la cifra: una
  línea que cambió de etiqueta GAAP a medio camino, por ejemplo.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd

from src.ingesta.estados import (
    BALANCE,
    ESTADO_RESULTADOS,
    FLUJO_EFECTIVO,
    LINEA_POR_CLAVE,
    tags_de,
)

ERROR = "ERROR"
AVISO = "AVISO"

# Un balance de miles de millones no cuadra al centavo: las emisoras redondean a
# miles y la suma arrastra. Medio punto base sobre el activo total es holgado para
# el redondeo y estrecho para un renglón mal leído, que se desvía por órdenes de
# magnitud, no por decimales.
TOLERANCIA_RELATIVA = 0.0005

# Por encima de este desvío, la suma de los trimestres contra el año deja de ser
# una reclasificación de cierre y pasa a ser un trimestre en el año equivocado.
# Un trimestre mal asignado mueve el total en el orden de un cuarto del año.
TOLERANCIA_RECLASIFICACION = 0.05


@dataclass(frozen=True)
class Incidencia:
    """Algo que no cuadra, con lo necesario para ir a verlo al filing."""

    ticker: str
    severidad: str
    prueba: str
    detalle: str
    periodo: dt.date | None = None

    def como_texto(self) -> str:
        cuando = f" [{self.periodo}]" if self.periodo else ""
        return f"{self.severidad} {self.ticker}{cuando} · {self.prueba}: {self.detalle}"


def _cerca(a: float, b: float, referencia: float) -> bool:
    escala = max(abs(referencia), 1.0)
    return abs(a - b) / escala <= TOLERANCIA_RELATIVA


def _valor(tabla: pd.DataFrame, linea: str, periodo) -> float | None:
    if tabla.empty or linea not in tabla.index or periodo not in tabla.columns:
        return None
    v = tabla.loc[linea, periodo]
    return None if pd.isna(v) else float(v)


def _periodos(tabla: pd.DataFrame) -> list:
    return [c for c in tabla.columns if isinstance(c, dt.date)]


# --------------------------------------------------------------------------------------
# 1. El balance cuadra
# --------------------------------------------------------------------------------------


def verificar_balance(ticker: str, balance: pd.DataFrame) -> list[Incidencia]:
    """Activo = Pasivo + Capital. Es la identidad que define la partida doble.

    Si no se cumple, alguna de las tres líneas viene de una etiqueta que no es la
    que se cree. No hay forma de que la emisora la haya publicado descuadrada: la
    SEC no acepta un balance que no cierre.
    """
    incidencias: list[Incidencia] = []
    if balance.empty:
        return incidencias

    for periodo in _periodos(balance):
        activos = _valor(balance, "activos_totales", periodo)
        pasivos = _valor(balance, "pasivos_totales", periodo)
        suma_declarada = _valor(balance, "pasivo_mas_capital", periodo)
        capital = _capital_total(balance, periodo)

        if activos is not None and suma_declarada is not None and not _cerca(
            activos, suma_declarada, activos
        ):
            incidencias.append(Incidencia(
                ticker, ERROR, "balance_cuadra",
                f"activos {activos:,.0f} contra pasivo+capital declarado "
                f"{suma_declarada:,.0f} (diferencia {activos - suma_declarada:,.0f})",
                periodo,
            ))

        if None not in (activos, pasivos, capital):
            # El capital temporal va ENTRE el pasivo y el capital permanente.
            calculado = pasivos + capital + (_valor(balance, "capital_temporal", periodo) or 0.0)
            if not _cerca(activos, calculado, activos):
                incidencias.append(Incidencia(
                    ticker, ERROR, "balance_cuadra",
                    f"activos {activos:,.0f} contra pasivos {pasivos:,.0f} + capital "
                    f"{capital:,.0f} (+ temporal) = {calculado:,.0f} "
                    f"(diferencia {activos - calculado:,.0f})",
                    periodo,
                ))
    return incidencias


def _capital_total(balance: pd.DataFrame, periodo) -> float | None:
    """Capital que cierra el balance: el TOTAL, con la participación no controladora.

    La identidad de la partida doble es Activo = Pasivo + capital **total**. El
    renglón "capital contable" que publican las emisoras suele ser el de la
    controladora, y usarlo deja un descuadre del tamaño exacto del minoritario
    —1,100 millones en Welltower, 4,600 en Prologis—, que hace ver rota una lectura
    que está bien.

    Si la emisora publica el total, ese manda. Si no, se reconstruye sumando el
    minoritario, y si tampoco está, no hay contra qué comparar y no se opina.
    """
    total = _valor(balance, "capital_total", periodo)
    if total is not None:
        return total
    controladora = _valor(balance, "capital_contable", periodo)
    if controladora is None:
        return None
    minoritario = _valor(balance, "participacion_no_controladora", periodo)
    return controladora + (minoritario or 0.0)


# --------------------------------------------------------------------------------------
# 2. Los cuatro trimestres suman el año
# --------------------------------------------------------------------------------------

# Solo aplica a partidas de FLUJO. Sumar cuatro balances trimestrales no significa
# nada, y sumar cuatro cifras por acción tampoco es exacto porque cada trimestre
# tiene su propio promedio de acciones.
_NO_ADITIVAS = frozenset({
    "utilidad_por_accion_basica", "utilidad_por_accion_diluida",
    "acciones_basicas", "acciones_diluidas", "dividendo_declarado_por_accion",
})


def _fue_reexpresado(crudos: pd.DataFrame, tag: str, periodo, tipo: str) -> tuple[bool, str]:
    """¿La emisora publicó ese periodo más de una vez, con cifras distintas?

    Es la diferencia entre un error de lectura y un hecho del negocio. Global Net
    Lease publicó un deterioro de 90.4 millones para 2024 en su 10-K de febrero de
    2025, y de 2.5 millones para el MISMO año en el 10-K de 2026: vendió su
    portafolio multi-inquilino y reclasificó el cargo a operaciones discontinuadas.

    Los trimestres que ya están guardados son de la primera versión; el año, de la
    segunda. La suma no cuadra y **las dos cifras son correctas**. Llamarle error a
    eso es no entender qué es una reexpresión; ignorarlo es peor, porque la serie
    trimestral quedó vieja. Se avisa, con las dos cifras y sus fechas.
    """
    if crudos.empty or not tag:
        return False, ""
    sub = crudos[
        (crudos["tag"] == tag)
        & (crudos["periodo_tipo"] == tipo)
        & (pd.to_datetime(crudos["fecha_dato"]).dt.date == periodo)
    ]
    if len(sub) < 2:
        return False, ""
    versiones = sub.sort_values("fecha_publicacion")[["fecha_publicacion", "valor"]]
    primera, ultima = versiones.iloc[0], versiones.iloc[-1]
    if primera["valor"] == ultima["valor"]:
        return False, ""
    return True, (
        f"La emisora reexpresó el dato: publicó {primera['valor']:,.0f} el "
        f"{primera['fecha_publicacion']} y {ultima['valor']:,.0f} el "
        f"{ultima['fecha_publicacion']}. Los trimestres guardados son de la versión "
        "anterior; el año, de la nueva."
    )


def verificar_trimestres_suman_el_ano(
    ticker: str, trimestral: pd.DataFrame, anual: pd.DataFrame,
    crudos: pd.DataFrame | None = None,
) -> list[Incidencia]:
    """Q1+Q2+Q3+Q4 = FY, para las líneas que son un flujo del periodo.

    Es la comprobación que caza un trimestre asignado al año equivocado, que es un
    error invisible: cada cifra por separado es correcta y la serie completa está
    corrida.
    """
    incidencias: list[Incidencia] = []
    if trimestral.empty or anual.empty:
        return incidencias

    derivados: set = set()
    if crudos is not None and not crudos.empty and "formulario" in crudos:
        derivados = {
            pd.Timestamp(f).date()
            for f in crudos.loc[crudos["formulario"] == "DERIVADO", "fecha_dato"]
        }

    trimestres_por_anio: dict[int, list] = {}
    for periodo in _periodos(trimestral):
        trimestres_por_anio.setdefault(periodo.year, []).append(periodo)

    for anio_fin in _periodos(anual):
        trimestres = sorted(trimestres_por_anio.get(anio_fin.year, []))
        if len(trimestres) != 4:
            continue  # con menos de cuatro no hay nada que comprobar
        # Si el Q4 se derivó de `FY − 9M`, la identidad se cumple por construcción y
        # comprobarla no verifica el dato: verifica una resta propia. Lo que sí
        # queda comprobado es el resto —que los tres primeros trimestres publicados
        # más el derivado reconstruyan el año— cuando el Q4 vino del emisor.
        if derivados and pd.Timestamp(trimestres[-1]).date() in derivados:
            continue
        for linea in anual.index:
            if linea in _NO_ADITIVAS or LINEA_POR_CLAVE.get(linea) is None:
                continue
            if linea not in trimestral.index:
                continue
            total = _valor(anual, linea, anio_fin)
            partes = [_valor(trimestral, linea, q) for q in trimestres]
            if total is None or any(p is None for p in partes):
                continue
            suma = sum(partes)
            if _cerca(suma, total, total):
                continue
            # Una diferencia CHICA entre la suma de los trimestres y el año es
            # normal y no es un error de lectura: la emisora reclasifica partidas
            # al cerrar el ejercicio, y el 10-K reexpresa trimestres que el 10-Q
            # ya había publicado. Aquí se conserva la versión más reciente de cada
            # uno, así que empalmar el año reexpresado con trimestres originales
            # deja un residuo. Un trimestre asignado al año equivocado, en cambio,
            # mueve el total en el orden del propio trimestre: 25% o más.
            desvio = abs(suma - total) / max(abs(total), 1.0)
            severidad = ERROR if desvio > TOLERANCIA_RECLASIFICACION else AVISO
            explicacion = (
                "" if severidad == ERROR
                else " Es del tamaño de una reclasificación de cierre de ejercicio."
            )
            if severidad == ERROR and crudos is not None:
                tag = anual.loc[linea, "tag_gaap"] if "tag_gaap" in anual.columns else ""
                reexpresado, nota = _fue_reexpresado(crudos, tag, anio_fin, "FY")
                if reexpresado:
                    severidad, explicacion = AVISO, " " + nota
            incidencias.append(Incidencia(
                ticker, severidad, "trimestres_suman_el_ano",
                f"«{LINEA_POR_CLAVE[linea].etiqueta}»: los cuatro trimestres suman "
                f"{suma:,.0f} contra {total:,.0f} del año "
                f"(diferencia {suma - total:,.0f}, {desvio:.2%}).{explicacion}",
                anio_fin,
            ))
    return incidencias


# --------------------------------------------------------------------------------------
# 3. Nadie publica un periodo antes de que termine
# --------------------------------------------------------------------------------------


def _tags_del_catalogo(ticker: str) -> set[str]:
    """Etiquetas que algún renglón del catálogo puede usar para esta emisora."""
    return {t for clave in LINEA_POR_CLAVE for t in tags_de(ticker, clave)}


def verificar_point_in_time(ticker: str, crudos: pd.DataFrame) -> list[Incidencia]:
    """La ``fecha_publicacion`` nunca puede ser anterior al cierre del periodo.

    Si lo fuera, el modelo tendría acceso a una cifra antes de que existiera, y eso
    es lookahead puro. Es la comprobación más barata y la que protege P1 en el
    origen, antes de que el dato entre a ninguna serie.

    Se aplica **solo a las etiquetas que el catálogo usa**. XBRL también trae
    revelaciones deliberadamente prospectivas —el calendario de vencimientos de la
    deuda, los pagos mínimos de arrendamiento futuros— cuyo periodo está en el
    futuro por diseño y no son un resultado reportado. Marcarlas sería confundir
    una revelación con un dato realizado, y a la tercera falsa alarma la prueba
    deja de leerse.
    """
    if crudos.empty:
        return []
    vista = crudos[crudos["tag"].isin(_tags_del_catalogo(ticker))].copy()
    if vista.empty:
        return []
    vista["fecha_dato"] = pd.to_datetime(vista["fecha_dato"], errors="coerce")
    vista["fecha_publicacion"] = pd.to_datetime(vista["fecha_publicacion"], errors="coerce")
    malas = vista[vista["fecha_publicacion"] < vista["fecha_dato"]]
    if malas.empty:
        return []
    muestra = malas.head(3)
    detalle = "; ".join(
        f"{r.tag} del {r.fecha_dato.date()} publicado el {r.fecha_publicacion.date()}"
        for r in muestra.itertuples()
    )
    return [Incidencia(
        ticker, ERROR, "point_in_time",
        f"{len(malas)} hecho(s) con fecha de publicación anterior al cierre del periodo: {detalle}",
    )]


# --------------------------------------------------------------------------------------
# 4. Una línea no mezcla unidades ni etiquetas
# --------------------------------------------------------------------------------------


def verificar_unidades(ticker: str, crudos: pd.DataFrame) -> list[Incidencia]:
    """Una misma etiqueta GAAP reportada en dos unidades distintas es una trampa.

    Pasa de verdad: una emisora publica ``CommonStockSharesOutstanding`` en
    ``shares`` y, en otro contexto, la misma etiqueta en ``USD``. Mezclarlas suma
    acciones con dólares.
    """
    if crudos.empty:
        return []
    # Solo las etiquetas que el catálogo usa: una etiqueta que nadie lee puede
    # venir en las unidades que quiera sin consecuencia.
    vista = crudos[crudos["tag"].isin(_tags_del_catalogo(ticker))]
    if vista.empty:
        return []
    incidencias = []
    por_tag = vista.groupby("tag")["unidad"].nunique()
    for tag in por_tag[por_tag > 1].index:
        unidades = sorted(set(vista.loc[vista["tag"] == tag, "unidad"]))
        incidencias.append(Incidencia(
            ticker, AVISO, "unidades_mezcladas",
            f"«{tag}» aparece en {len(unidades)} unidades distintas: {', '.join(unidades)}. "
            "Se toma una sola por línea, pero conviene revisar cuál corresponde.",
        ))
    return incidencias


def verificar_cambio_de_etiqueta(
    ticker: str, crudos: pd.DataFrame, estado: pd.DataFrame
) -> list[Incidencia]:
    """Una línea que cambió de etiqueta GAAP a medio camino deja un salto.

    No es un error de la emisora ni del parser: la taxonomía cambia entre años y
    las emisoras migran. Pero pegar dos series distintas produce un salto que
    parece un evento del negocio, así que se avisa y se dice cuál se usó.
    """
    if estado.empty or crudos.empty or "tag_gaap" not in estado:
        return []
    incidencias = []
    periodos_por_tag = crudos.groupby("tag")["fecha_dato"].apply(set).to_dict()
    for linea, fila in estado.iterrows():
        usada = fila.get("tag_gaap")
        if not usada or usada not in periodos_por_tag:
            continue
        cubiertos = periodos_por_tag[usada]
        # Solo interesa la alterna que cubre periodos que la elegida NO tiene: esa
        # sí deja un hueco en la serie. Que exista otra etiqueta con los mismos
        # periodos es normal —la taxonomía admite sinónimos— y avisarlo en cada
        # renglón vuelve ilegible el reporte.
        aportan = [
            t for t in tags_de(ticker, linea)
            if t != usada and t in periodos_por_tag and (periodos_por_tag[t] - cubiertos)
        ]
        if aportan:
            faltan = len(periodos_por_tag[aportan[0]] - cubiertos)
            incidencias.append(Incidencia(
                ticker, AVISO, "etiqueta_alterna",
                f"«{LINEA_POR_CLAVE[linea].etiqueta}» se armó con «{usada}», y "
                f"«{aportan[0]}» cubre {faltan} periodo(s) que esa no tiene. Empalmarlas "
                "produciría un salto que parece del negocio y es de etiqueta.",
            ))
    return incidencias


# --------------------------------------------------------------------------------------
# 5. Los signos que no admiten discusión
# --------------------------------------------------------------------------------------

# Estas no son opinables: un activo total negativo o un conteo de acciones negativo
# no existen. Las utilidades sí pueden ser negativas, y por eso no están aquí.
_ESTRICTAMENTE_POSITIVAS = (
    "activos_totales",
    "acciones_basicas",
    "acciones_diluidas",
    "acciones_en_circulacion",
    "ingresos_totales",
)


def verificar_signos(ticker: str, estado: pd.DataFrame) -> list[Incidencia]:
    incidencias = []
    if estado.empty:
        return incidencias
    for linea in _ESTRICTAMENTE_POSITIVAS:
        if linea not in estado.index:
            continue
        for periodo in _periodos(estado):
            valor = _valor(estado, linea, periodo)
            if valor is not None and valor <= 0:
                incidencias.append(Incidencia(
                    ticker, ERROR, "signo_imposible",
                    f"«{LINEA_POR_CLAVE[linea].etiqueta}» vale {valor:,.0f}, y no puede ser "
                    "menor o igual a cero.",
                    periodo,
                ))
    return incidencias


# --------------------------------------------------------------------------------------
# La corrida completa
# --------------------------------------------------------------------------------------


def verificar_todo(
    ticker: str,
    crudos: pd.DataFrame,
    estados: dict[tuple[str, str | None], pd.DataFrame],
) -> list[Incidencia]:
    """Corre todas las comprobaciones y devuelve las incidencias, ordenadas.

    ``estados`` mapea ``(estado, periodo_tipo)`` a la tabla armada. El balance va
    con ``periodo_tipo=None`` porque es un saldo, no un periodo.
    """
    incidencias: list[Incidencia] = []
    incidencias += verificar_point_in_time(ticker, crudos)
    incidencias += verificar_unidades(ticker, crudos)

    balance = estados.get((BALANCE, None), pd.DataFrame())
    incidencias += verificar_balance(ticker, balance)
    incidencias += verificar_signos(ticker, balance)

    for estado_nombre in (ESTADO_RESULTADOS, FLUJO_EFECTIVO):
        trimestral = estados.get((estado_nombre, "Q"), pd.DataFrame())
        anual = estados.get((estado_nombre, "FY"), pd.DataFrame())
        incidencias += verificar_signos(ticker, trimestral)
        incidencias += verificar_trimestres_suman_el_ano(ticker, trimestral, anual, crudos)
        incidencias += verificar_cambio_de_etiqueta(ticker, crudos, trimestral)

    orden = {ERROR: 0, AVISO: 1}
    return sorted(incidencias, key=lambda i: (orden.get(i.severidad, 9), i.prueba, str(i.periodo)))


def resumir(incidencias: list[Incidencia]) -> str:
    errores = sum(1 for i in incidencias if i.severidad == ERROR)
    avisos = len(incidencias) - errores
    if not incidencias:
        return "Todas las comprobaciones pasan."
    return f"{errores} error(es) y {avisos} aviso(s)."
