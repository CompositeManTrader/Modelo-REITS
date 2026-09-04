"""Extracción de la conciliación de AFFO desde el Exhibit 99.1 del 8-K.

El AFFO no está en XBRL: es una medida no-GAAP. Vive en las tablas
"Reconciliation of Net Income to FFO and AFFO" del comunicado de resultados.
Este módulo las localiza, normaliza sus etiquetas contra la taxonomía de
``modelo.cascada`` y devuelve filas listas para validar y persistir.

Reconstrucción de trimestres
----------------------------
Las tablas "HISTORICAL FFO AND AFFO" traen cinco años del **mismo** trimestre.
Un reporte de Q2 da Q2 y H1 de cinco años; uno de Q4 da Q4 y el año completo.
Con los reportes de Q2 y Q4 de un año se reconstruyen los cuatro trimestres de
cinco años::

    Q1 = H1 − Q2
    Q3 = FY − H1 − Q4

La ``fecha_publicacion`` de un trimestre reconstruido es la **más tardía** de las
publicaciones que lo componen: antes de esa fecha el número no era deducible.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from src.config import Fuente
from src.modelo.cascada import SEPARADOR_SEGMENTO, TODAS_LAS_LINEAS, clave_base

# --------------------------------------------------------------------------------------
# Normalización de etiquetas
# --------------------------------------------------------------------------------------

# Se compilan una vez. El orden importa: las claves más específicas van primero para
# que "normalized FFO" no se coma con el patrón genérico de "FFO".
_ORDEN_PRIORIDAD = (
    # Los ajustes específicos van antes que los subtotales que los contienen como
    # subcadena: "FFO adjustments allocable to noncontrolling interests" tiene que
    # resolverse a minoritarios, no a FFO.
    "no_consolidadas_y_minoritarios",
    # Antes que "ffo_normalizado": "Cumulative adjustments to calculate Normalized
    # FFO" es el puente agregado, no el subtotal.
    "ajustes_acumulados_ffo_normalizado",
    "ffo_normalizado",
    "affo",
    "ffo",
    "noi",
    "capex_mantenimiento",
    "renta_linea_recta",
    "revaluacion_valor_razonable",
    # Antes de comisiones: "Amortization of lease intangibles - in-place leases and
    # leasing costs" es un ajuste no-efectivo, no una comisión efectivamente pagada.
    "otros_ajustes_no_efectivo",
    "comisiones_arrendamiento",
    "amortizacion_costos_financieros",
    "compensacion_en_acciones",
    # "Non-real estate depreciation" contiene "real estate depreciation" como
    # subcadena, así que la clave específica tiene que evaluarse primero o la
    # depreciación de mobiliario acaba sumándose como si fuera de inmuebles.
    "depreciacion_mobiliario",
    "depreciacion_inmuebles",
    "dividendos_preferentes",
    "ganancia_venta_inmuebles",
    "deterioro",
    "partidas_no_recurrentes",
    "utilidad_neta",
    "ingreso_rentas",
    "gastos_operativos_inmueble",
)

_PATRONES: list[tuple[str, re.Pattern]] = []
for _clave in _ORDEN_PRIORIDAD:
    _linea = next((ln for ln in TODAS_LAS_LINEAS if ln.clave == _clave), None)
    if _linea is None or not _linea.patrones:
        continue
    _PATRONES.append((_clave, re.compile("|".join(f"(?:{p})" for p in _linea.patrones), re.I)))


# Filas que contienen una etiqueta reconocible pero NO son un monto de la cascada.
# Sin este filtro, "Property expenses (non-reimbursable) (% of total revenue)" entra
# como ingreso por rentas con valor 1.4, que es un porcentaje disfrazado de millones.
_RE_NO_ES_MONTO = re.compile(
    r"%\s*of\b|\(\s*%\s*\)|as\s+a\s+%|percent(?:age)?\s+of|margin\b|ratio\b|"
    r"\bcoverage\b|\byield\b|"
    # "Weighted average diluted shares outstanding - FFO, Normalized FFO" es un
    # conteo de acciones, no una línea de la conciliación.
    r"weighted\s+average\b.{0,40}\b(?:shares|units)\b|"
    r"dividends?\s+(?:paid|declared)\s+per\b|"
    # Estas van DEBAJO del subtotal de AFFO: son el puente al AFFO diluido y a la
    # cobertura del dividendo, no partidas de la conciliación.
    r"^affo\s+allocable\s+to|^diluted\s+affo|affo\s+after\s+distributions|"
    r"distributions?\s+paid\s+to",
    re.I,
)


# Conceptos que pueden venir repartidos en varias filas del reporte y hay que sumar.
# Las bases (utilidad neta, ingresos) y los subtotales se toman una sola vez.
CLAVES_ACUMULABLES: frozenset[str] = frozenset(
    ln.clave
    for ln in TODAS_LAS_LINEAS
    if ln.signo != 0
    and ln.clave not in {"utilidad_neta", "ingreso_rentas", "gastos_operativos_inmueble"}
)


def normalizar_etiqueta(texto: str) -> str | None:
    """Mapea la etiqueta del emisor a una clave de la cascada. ``None`` si no aplica."""
    limpio = re.sub(r"\s+", " ", texto or "").strip().lower()
    if not limpio or len(limpio) > 200:
        return None
    limpio = re.sub(r"^\(?\d+\)?[\.\)]\s*", "", limpio)  # numeración de notas al pie
    limpio = limpio.replace("–", "-").replace("—", "-")
    if _RE_NO_ES_MONTO.search(limpio):
        return None
    for clave, patron in _PATRONES:
        if patron.search(limpio):
            return clave
    return None


# --------------------------------------------------------------------------------------
# Parseo de números
# --------------------------------------------------------------------------------------

_GUIONES = {"-", "—", "–", "‒", "―", "n/a", "na", "nm", ""}


def parsear_numero(texto: str) -> float | None:
    """Convierte una celda de reporte financiero a float.

    Maneja las convenciones del oficio: paréntesis para negativo, símbolo de
    moneda, separador de miles, guion largo para cero, y notas al pie pegadas.
    """
    if texto is None:
        return None
    s = str(texto).strip()
    s = s.replace("\xa0", " ").replace(" ", " ").strip()
    if s.lower() in _GUIONES:
        return None
    negativo = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    s = re.sub(r"[\$\s,%]", "", s)
    s = s.replace("—", "").replace("–", "")
    if not s or not re.fullmatch(r"-?\d*\.?\d+", s):
        return None
    valor = float(s)
    return -valor if negativo else valor


# --------------------------------------------------------------------------------------
# Detección de periodos en los encabezados
# --------------------------------------------------------------------------------------

_MESES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

_RE_FECHA = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+(\d{1,2})\s*,?\s*(\d{4})",
    re.I,
)
_RE_ANIO = re.compile(r"\b(19|20)\d{2}\b")
# Mes y día sin año: "Quarter Ended June 30," con los años en la fila de abajo.
_RE_MES_DIA = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+(\d{1,2})\s*,",
    re.I,
)

_DURACIONES = (
    # "Quarter ended" es tan común como "three months ended" y no estaba: NNN lo
    # usa, y como su encabezado también dice "Six Months Ended", la única duración
    # que el parser reconocía era la del semestre. Sus cuatro columnas —dos
    # trimestres y dos semestres— quedaban las cuatro etiquetadas como semestre.
    (r"(?:three|3)\s+months|quarter\s+ended|(?:first|second|third|fourth)\s+quarter", "Q"),
    (r"(?:six|6)\s+months", "H1"),
    (r"(?:nine|9)\s+months", "9M"),
    (r"(?:twelve|12)\s+months|year\s+ended|full\s+year|annual", "FY"),
)


@dataclass(frozen=True)
class Periodo:
    tipo: str  # 'Q' | 'H1' | '9M' | 'FY'
    fin: dt.date

    @property
    def etiqueta(self) -> str:
        return f"{self.tipo} {self.fin.isoformat()}"


def _duraciones_en_orden(t: str) -> list[str]:
    """Tipos de periodo que menciona el encabezado, en el orden en que aparecen.

    Devuelve más de uno cuando la tabla pone dos grupos de columnas bajo el mismo
    encabezado, que es la forma en que NNN reporta::

        Quarter Ended June 30,        Six Months Ended June 30,
             2026   |   2025               2026   |   2025

    Las repeticiones consecutivas del mismo tipo se colapsan: "three months ended
    June 30, 2026 and three months ended June 30, 2025" es UN grupo, no dos.
    """
    encontrados: list[tuple[int, str]] = []
    for patron, etiqueta in _DURACIONES:
        for m in re.finditer(patron, t, re.I):
            encontrados.append((m.start(), etiqueta))
    encontrados.sort()

    tipos: list[str] = []
    for _, etiqueta in encontrados:
        if not tipos or tipos[-1] != etiqueta:
            tipos.append(etiqueta)
    return tipos


def detectar_periodos(texto_encabezado: str) -> list[Periodo]:
    """Extrae los periodos de un encabezado de tabla.

    Un encabezado típico dice "Three Months Ended June 30, 2026 and 2025"; de ahí
    salen dos periodos trimestrales con el mismo día y mes y distinto año.

    Cuando el encabezado menciona **dos duraciones** —trimestre y semestre, por
    ejemplo— las columnas son el producto: primero todas las del primer grupo y
    luego las del segundo, que es como se maquetan estas tablas.
    """
    t = re.sub(r"\s+", " ", texto_encabezado or "").strip()
    if not t:
        return []
    tipos = _duraciones_en_orden(t)
    tipo = tipos[0] if tipos else None
    fechas: list[dt.date] = []
    for m in _RE_FECHA.finditer(t):
        mes = _MESES[m.group(1).lower()]
        dia, anio = int(m.group(2)), int(m.group(3))
        try:
            fechas.append(dt.date(anio, mes, dia))
        except ValueError:
            continue
    if fechas and tipo:
        # El orden de las fechas en el encabezado ES el orden de las columnas, y así
        # se conserva. Ordenarlas por fecha rompe cualquier tabla que no venga de la
        # más reciente a la más vieja, y el error no se ve: las cifras entran a un
        # periodo que existe, solo que al equivocado.
        #
        # Tampoco se deduplica por AÑO. Esa era la trampa: el idioma "June 30, 2026
        # and 2025" invita a indexar por año, pero W. P. Carey publica tres columnas
        # —trimestre actual, trimestre anterior y mismo trimestre del año pasado— y
        # dos son del mismo año. Indexar por año colapsaba 30 de junio y 31 de marzo
        # de 2026 en una sola, y el corrimiento resultante le ponía al primer
        # trimestre las cifras del segundo.
        periodos: list[dt.date] = []
        for f in fechas:
            if f not in periodos:
                periodos.append(f)

        # Los años sueltos SÍ se expanden, pero solo los que ninguna fecha explícita
        # cubre ya: son el "and 2025" que sigue a una fecha completa.
        anios_cubiertos = {f.year for f in periodos}
        base = fechas[0]
        for anio in (int(a.group(0)) for a in _RE_ANIO.finditer(t)):
            if anio in anios_cubiertos:
                continue
            try:
                candidato = dt.date(anio, base.month, base.day)
            except ValueError:
                continue
            periodos.append(candidato)
            anios_cubiertos.add(anio)

        if len(tipos) > 1:
            # Dos grupos de columnas bajo el mismo encabezado. Las columnas van
            # por grupo: primero todas las fechas del primero, luego las del
            # segundo. Si la tabla trae menos columnas numéricas de las que este
            # producto implica, `_mapear_columnas` se queda con las primeras, o
            # sea con el primer grupo, que es la lectura conservadora.
            return [Periodo(tp, f) for tp in tipos for f in periodos]
        return [Periodo(tipo, f) for f in periodos]
    if tipos and not fechas:
        # El encabezado puede traer el día y el mes SEPARADOS de los años, en filas
        # distintas de la tabla: "Quarter Ended June 30," arriba y "2026 2025 2026
        # 2025" abajo. Ninguna fecha queda completa, así que la detección normal no
        # encuentra nada y la tabla se descarta entera. El mes y el día están ahí;
        # solo hay que casarlos con la lista de años.
        m = _RE_MES_DIA.search(t)
        anios = [int(a.group(0)) for a in _RE_ANIO.finditer(t)]
        if m and anios:
            mes, dia = _MESES[m.group(1).lower()], int(m.group(2))
            fines: list[dt.date] = []
            for anio in anios:
                try:
                    candidato = dt.date(anio, mes, dia)
                except ValueError:
                    continue
                if candidato not in fines:
                    fines.append(candidato)
            if fines:
                if len(tipos) > 1:
                    return [Periodo(tp, f) for tp in tipos for f in fines]
                return [Periodo(tipos[0], f) for f in fines]
    if fechas:
        return [Periodo("Q", f) for f in fechas]
    return []


# --------------------------------------------------------------------------------------
# Parseo de tablas HTML
# --------------------------------------------------------------------------------------


def _texto_celda(celda) -> str:
    return re.sub(r"\s+", " ", celda.get_text(" ", strip=True)).strip()


def _tabla_a_matriz(tabla) -> list[list[str]]:
    filas = []
    for tr in tabla.find_all("tr"):
        celdas = tr.find_all(["td", "th"])
        if not celdas:
            continue
        filas.append([_texto_celda(c) for c in celdas])
    return filas


# Varios emisores no usan la palabra "AFFO": Prologis publica "Core FFO" y Agree
# Realty escribe "Adjusted Funds from Operations" completo. Exigir la sigla literal
# descartaba sus tablas antes de siquiera intentar parsearlas.
_TERMINOS_AJUSTADO = (
    "affo",
    "adjusted funds from operations",
    "core ffo",
    "core funds from operations",
    "normalized ffo",
    "normalized funds from operations",
)


def _es_tabla_de_conciliacion(matriz: list[list[str]]) -> bool:
    texto = " ".join(" ".join(f) for f in matriz).lower()
    tiene_ffo = "ffo" in texto or "funds from operations" in texto
    tiene_ajustado = any(term in texto for term in _TERMINOS_AJUSTADO)
    return tiene_ffo and tiene_ajustado


def _numeros_de_fila(fila: list[str]) -> list[float]:
    valores = [parsear_numero(c) for c in fila[1:]]
    return [v for v in valores if v is not None]


@dataclass
class ConciliacionExtraida:
    """Resultado del parseo de una tabla de conciliación."""

    ticker: str
    periodo: Periodo
    lineas: dict[str, float]
    etiquetas: dict[str, str]
    fecha_publicacion: dt.date
    url_filing: str
    escala: float = 1.0
    advertencias: tuple[str, ...] = ()
    # Posición de cada línea dentro de la tabla del emisor. Es lo que permite
    # cuadrar respetando SU estructura en vez de imponerle la nuestra: qué partidas
    # caen entre un subtotal y el siguiente lo dice la tabla, no nuestra taxonomía.
    orden: dict[str, int] = field(default_factory=dict)

    def filas_conciliacion(self) -> list[dict]:
        """Filas listas para la tabla ``conciliacion``."""
        orden = {ln.clave: i for i, ln in enumerate(TODAS_LAS_LINEAS)}
        salida = []
        for clave, valor in self.lineas.items():
            salida.append(
                {
                    "ticker": self.ticker,
                    "periodo_tipo": self.periodo.tipo,
                    "fecha_dato": self.periodo.fin,
                    "fecha_publicacion": self.fecha_publicacion,
                    "orden": orden.get(clave, 999),
                    "linea": clave,
                    "etiqueta": self.etiquetas.get(clave, clave),
                    "valor": valor,
                    "fuente": Fuente.SEC_8K,
                    "url_filing": self.url_filing,
                }
            )
        return sorted(salida, key=lambda d: d["orden"])

    def filas_hechos(self) -> list[dict]:
        """Filas listas para la tabla ``hechos`` (los subtotales de la cascada)."""
        salida = []
        for clave in ("noi", "ffo", "ffo_normalizado", "affo", "affo_por_accion"):
            if clave not in self.lineas:
                continue
            salida.append(
                {
                    "ticker": self.ticker,
                    "concepto": clave,
                    "periodo_tipo": self.periodo.tipo,
                    "fecha_dato": self.periodo.fin,
                    "fecha_publicacion": self.fecha_publicacion,
                    "valor": self.lineas[clave],
                    "unidad": "USD",
                    "fuente": Fuente.SEC_8K,
                    "es_primario": True,
                    "url_filing": self.url_filing,
                }
            )
        return salida


def detectar_escala(html_o_texto: str) -> float:
    """Detecta si la tabla está en miles o millones. Un factor mal leído es 1000x."""
    t = html_o_texto.lower()
    if re.search(r"in\s+thousands|\(thousands\)|amounts?\s+in\s+thousands", t):
        return 1_000.0
    if re.search(r"in\s+millions|\(millions\)|amounts?\s+in\s+millions", t):
        return 1_000_000.0
    return 1.0


def parsear_conciliacion(
    html: str,
    ticker: str,
    fecha_publicacion: dt.date,
    url_filing: str = "",
    *,
    aplicar_escala: bool = True,
) -> list[ConciliacionExtraida]:
    """Encuentra y parsea todas las tablas de conciliación FFO/AFFO del documento.

    Devuelve una extracción por (tabla, columna de periodo). Cuando el encabezado
    no permite identificar el periodo, la tabla se descarta con advertencia: un
    número sin periodo es peor que ningún número.
    """
    sopa = BeautifulSoup(html, "lxml")
    escala_doc = detectar_escala(sopa.get_text(" ")) if aplicar_escala else 1.0
    salida: list[ConciliacionExtraida] = []

    for tabla in sopa.find_all("table"):
        matriz = _tabla_a_matriz(tabla)
        if len(matriz) < 3 or not _es_tabla_de_conciliacion(matriz):
            continue

        contexto = _contexto_previo(tabla)
        encabezado = " ".join(" ".join(f) for f in matriz[: min(3, len(matriz))])

        escala = detectar_escala(contexto + " " + encabezado) if aplicar_escala else 1.0
        if escala == 1.0:
            escala = escala_doc

        for periodos, filas in _secciones(matriz, contexto, encabezado):
            # Mapea cada columna numérica a un periodo, en el orden en que aparecen.
            columnas = _mapear_columnas(filas, periodos)
            if not columnas:
                continue
            salida.extend(
                _extraer_columnas(
                    filas, columnas, ticker, fecha_publicacion, url_filing, escala
                )
            )
    return salida


# La tabla "HISTORICAL FFO AND AFFO" mete el trimestre y el semestre en el MISMO
# <table>, separados por una fila de encabezado interna. Tratarla como un solo
# periodo asigna cifras semestrales a un trimestre — un error de 2x que cuadra
# consigo mismo y por eso no lo caza ninguna validación aritmética.
_RE_ENCABEZADO_PERIODO = re.compile(
    r"(?:for\s+the\s+)?(?:three|six|nine|twelve|3|6|9|12)\s+months\s+ended|"
    r"(?:for\s+the\s+)?(?:year|quarter)s?\s+ended",
    re.I,
)


def _secciones(
    matriz: list[list[str]], contexto: str, encabezado: str
) -> list[tuple[list[Periodo], list[list[str]]]]:
    """Parte la tabla en bloques, cada uno con su propio conjunto de periodos."""
    indices = [
        i for i, fila in enumerate(matriz)
        if fila and _RE_ENCABEZADO_PERIODO.search(" ".join(fila))
    ]
    if not indices:
        periodos = detectar_periodos(contexto + " " + encabezado)
        return [(periodos, matriz)] if periodos else []

    secciones: list[tuple[list[Periodo], list[list[str]]]] = []
    for k, inicio in enumerate(indices):
        fin = indices[k + 1] if k + 1 < len(indices) else len(matriz)
        # El encabezado suele venir partido en dos filas: una con la duración
        # ("Three months ended June 30,") y la siguiente con los años ("2026 2025").
        # Buscar la fecha completa en una sola fila pierde esas tablas por completo,
        # y en silencio: la tabla simplemente no aparece entre las candidatas.
        encabezado = " ".join(matriz[inicio])
        periodos = detectar_periodos(encabezado)
        for extra in range(1, 3):
            if periodos or inicio + extra >= fin:
                break
            encabezado += " " + " ".join(matriz[inicio + extra])
            periodos = detectar_periodos(encabezado)
        if not periodos:
            periodos = detectar_periodos(contexto + " " + encabezado)
        if periodos:
            secciones.append((periodos, matriz[inicio + 1 : fin]))
    return secciones


def _extraer_columnas(
    filas: list[list[str]],
    columnas: dict[int, Periodo],
    ticker: str,
    fecha_publicacion: dt.date,
    url_filing: str,
    escala: float,
) -> list[ConciliacionExtraida]:
    salida: list[ConciliacionExtraida] = []
    for idx_col, periodo in columnas.items():
        lineas: dict[str, float] = {}
        etiquetas: dict[str, str] = {}
        orden: dict[str, int] = {}
        # Un mismo concepto puede aparecer en tramos distintos de la conciliación:
        # Agree Realty amortiza intangibles de arrendamiento antes del FFO y rentas
        # sobre y bajo mercado antes del Core FFO, y ambas caen en "otros ajustes".
        # Acumularlas juntas mete el segundo monto en el tramo del primero y deja el
        # siguiente sin partidas que verificar. El segmento las mantiene separadas.
        segmento = 0
        for n_fila, fila in enumerate(filas):
            if len(fila) < 2:
                continue
            clave = normalizar_etiqueta(fila[0])
            if clave is None:
                continue
            valores = _valores_alineados(fila)
            if idx_col >= len(valores) or valores[idx_col] is None:
                continue
            # Las magnitudes por acción van a su propia clave. Mezclarlas con los
            # totales produce una "conciliación" donde el AFFO son 2.22 dólares y la
            # depreciación 644 millones, que no cuadra ni puede cuadrar.
            if _es_por_accion(fila[0]):
                clave, valor = f"{clave}_por_accion", valores[idx_col]
            else:
                valor = valores[idx_col] * escala * _signo_de_la_etiqueta(fila[0])

            es_subtotal = clave in _CLAVES_SUBTOTAL
            if not es_subtotal and segmento and clave in CLAVES_ACUMULABLES:
                clave = f"{clave}{SEPARADOR_SEGMENTO}{segmento}"

            if clave in lineas:
                # Un mismo concepto puede venir repartido en varias filas DEL MISMO
                # tramo. Realty Income reporta "Proportionate share of adjustments
                # for unconsolidated entities" y "FFO adjustments allocable to
                # noncontrolling interests" por separado, y el FFO solo cuadra si se
                # suman. Los subtotales y las bases se toman una sola vez.
                #
                # La pregunta va sobre la clave BASE, no sobre la segmentada: arriba
                # ya se le pegó el sufijo "#1", que por construcción nunca está en el
                # conjunto de acumulables. Preguntarlo con el sufijo hacía que en
                # todo tramo posterior al primero solo sobreviviera la PRIMERA fila
                # de cada concepto y las demás se perdieran en silencio. W. P. Carey
                # mete cuatro filas de "otros ajustes" y dos de participación
                # proporcional en el tramo del AFFO: se guardaba una de cada una.
                if clave_base(clave) in CLAVES_ACUMULABLES:
                    lineas[clave] += valor
                    etiquetas[clave] += f" + {fila[0]}"
                continue
            lineas[clave] = valor
            etiquetas[clave] = fila[0]
            orden[clave] = n_fila

            if es_subtotal:
                # A partir de aquí empieza otro tramo. Las partidas que sigan van a
                # un segmento nuevo aunque sean del mismo concepto que las anteriores.
                segmento += 1

        if not any(k in lineas for k in ("ffo", "ffo_normalizado", "affo", "noi")):
            continue
        if periodo.fin > fecha_publicacion:
            # Un filing no puede reportar cifras REALIZADAS de un periodo que aún
            # no termina: esa es la tabla de GUÍA. Extra Space Storage publica su
            # guía del año en el mismo comunicado que su trimestre, y tratarla como
            # realizada mete una proyección dentro de la serie histórica. La guía
            # tiene su propia tabla en la base, con su propio versionado (P1).
            continue
        advertencias = []
        if escala == 1.0:
            advertencias.append(
                "No se detectó la escala del reporte (miles/millones); se asumió unidades."
            )
        salida.append(
            ConciliacionExtraida(
                ticker=ticker,
                periodo=periodo,
                lineas=lineas,
                etiquetas=etiquetas,
                fecha_publicacion=fecha_publicacion,
                url_filing=url_filing,
                escala=escala,
                advertencias=tuple(advertencias),
                orden=orden,
            )
        )
    return salida


_RE_RESTA_EN_LA_ETIQUETA = re.compile(r"^\s*(?:less|menos|deduct)\b[:\s]", re.I)


def _signo_de_la_etiqueta(etiqueta: str) -> int:
    """Devuelve −1 cuando la etiqueta lleva el signo en la palabra, no en el número.

    Agree Realty escribe "Less Series A preferred stock dividends" con el monto en
    positivo. En una conciliación aditiva, sumar ese positivo desplaza el subtotal
    por el doble de la partida y el descuadre parece venir de otra línea.
    """
    return -1 if _RE_RESTA_EN_LA_ETIQUETA.search(etiqueta or "") else 1


_CLAVES_SUBTOTAL = ("noi", "ffo", "ffo_normalizado", "affo")

def _es_por_accion(etiqueta: str) -> bool:
    return bool(re.search(r"per\s+(?:common\s+)?share|per\s+diluted", etiqueta or "", re.I))


# --------------------------------------------------------------------------------------
# Consolidación: quedarse con la tabla que de verdad concilia
# --------------------------------------------------------------------------------------

def consolidar_extracciones(
    extracciones: list[ConciliacionExtraida],
) -> list[ConciliacionExtraida]:
    """Se queda con una extracción por periodo: la de la tabla que más concilia.

    Un comunicado de resultados repite las mismas cifras en varias tablas — el
    resumen ejecutivo en millones, la conciliación completa en miles, la tabla por
    acción. Quedarse con todas mete el mismo periodo tres veces con escalas
    distintas; quedarse con la primera es una lotería.

    El criterio es la tabla con **más líneas de detalle**: es la conciliación de
    verdad, la única contra la que el cuadre del AFFO puede correr. Las magnitudes
    por acción se recogen de las demás tablas del mismo periodo y se anexan, porque
    ahí sí viven.

    Cuando dos tablas del mismo periodo reportan el mismo subtotal con una
    diferencia de tres órdenes de magnitud, se levanta advertencia: eso es un
    problema de escala mal detectada, no un dato distinto.
    """
    if not extracciones:
        return []

    por_periodo: dict[tuple[str, dt.date], list[ConciliacionExtraida]] = {}
    for e in extracciones:
        por_periodo.setdefault((e.periodo.tipo, e.periodo.fin), []).append(e)

    salida: list[ConciliacionExtraida] = []
    for candidatas in por_periodo.values():
        def detalle(e: ConciliacionExtraida) -> int:
            return sum(
                1 for k in e.lineas
                if k not in _CLAVES_SUBTOTAL and not k.endswith("_por_accion")
            )

        mejor = max(candidatas, key=detalle)
        lineas = dict(mejor.lineas)
        etiquetas = dict(mejor.etiquetas)
        orden = dict(mejor.orden)
        advertencias = list(mejor.advertencias)

        for otra in candidatas:
            if otra is mejor:
                continue
            for clave, valor in otra.lineas.items():
                if clave.endswith("_por_accion") and clave not in lineas:
                    lineas[clave] = valor
                    etiquetas[clave] = otra.etiquetas.get(clave, clave)
                    orden[clave] = 10_000 + otra.orden.get(clave, 0)
            for clave in _CLAVES_SUBTOTAL:
                if clave not in lineas or clave not in otra.lineas:
                    continue
                a, b = lineas[clave], otra.lineas[clave]
                if a and b and 100 < abs(a / b) < 100_000:
                    advertencias.append(
                        f"Dos tablas reportan '{clave}' con {abs(a / b):,.0f}x de diferencia "
                        f"({a:,.0f} contra {b:,.0f}). La escala de alguna está mal detectada; "
                        "el cuadre del AFFO lo va a marcar."
                    )

        salida.append(
            ConciliacionExtraida(
                ticker=mejor.ticker,
                periodo=mejor.periodo,
                lineas=lineas,
                etiquetas=etiquetas,
                fecha_publicacion=mejor.fecha_publicacion,
                url_filing=mejor.url_filing,
                escala=mejor.escala,
                advertencias=tuple(dict.fromkeys(advertencias)),
                orden=orden,
            )
        )
    return sorted(salida, key=lambda e: (e.periodo.fin, e.periodo.tipo))


def reescalar_contra_referencia(
    extraccion: ConciliacionExtraida,
    clave: str,
    valor_referencia: float,
    *,
    tolerancia: float = 0.02,
) -> ConciliacionExtraida:
    """Corrige la escala de una extracción usando un valor de fuente primaria.

    Si la utilidad neta parseada del comunicado difiere de la de XBRL por un factor
    limpio de 1,000 o 1,000,000, el problema es la escala del comunicado y no el
    dato. Se reescala toda la tabla y se deja constancia. Cualquier otra diferencia
    NO se toca: reescalar por un factor arbitrario sería fabricar un número.
    """
    actual = extraccion.lineas.get(clave)
    if not actual or not valor_referencia:
        return extraccion
    razon = valor_referencia / actual
    if abs(razon - 1.0) <= tolerancia:
        return extraccion

    for factor in (1_000.0, 1_000_000.0, 0.001, 0.000001):
        if abs(razon / factor - 1.0) <= tolerancia:
            lineas = {
                k: (v if k.endswith("_por_accion") else v * factor)
                for k, v in extraccion.lineas.items()
            }
            return ConciliacionExtraida(
                ticker=extraccion.ticker,
                periodo=extraccion.periodo,
                lineas=lineas,
                etiquetas=extraccion.etiquetas,
                fecha_publicacion=extraccion.fecha_publicacion,
                url_filing=extraccion.url_filing,
                escala=extraccion.escala * factor,
                advertencias=(
                    *extraccion.advertencias,
                    f"Escala corregida por factor {factor:,.0f} al contrastar '{clave}' "
                    f"contra el valor de XBRL ({valor_referencia:,.0f}).",
                ),
            )
    return ConciliacionExtraida(
        ticker=extraccion.ticker,
        periodo=extraccion.periodo,
        lineas=extraccion.lineas,
        etiquetas=extraccion.etiquetas,
        fecha_publicacion=extraccion.fecha_publicacion,
        url_filing=extraccion.url_filing,
        escala=extraccion.escala,
        advertencias=(
            *extraccion.advertencias,
            f"'{clave}' parseado ({actual:,.0f}) no coincide con XBRL "
            f"({valor_referencia:,.0f}) y la diferencia no es un factor de escala limpio. "
            "El registro queda sospechoso: hay que revisarlo a mano.",
        ),
    )


def _contexto_previo(tabla, caracteres: int = 400) -> str:
    """Texto que precede a la tabla: ahí suele estar el periodo y la escala."""
    piezas: list[str] = []
    nodo = tabla
    for _ in range(6):
        nodo = nodo.find_previous(["p", "div", "span", "b", "font", "td"])
        if nodo is None:
            break
        t = re.sub(r"\s+", " ", nodo.get_text(" ", strip=True))
        if t:
            piezas.append(t)
        if sum(len(p) for p in piezas) > caracteres:
            break
    return " ".join(reversed(piezas))


def _valores_alineados(fila: list[str]) -> list[float | None]:
    """Extrae los numéricos de la fila descartando celdas de puro adorno.

    Los comunicados de la SEC están llenos de celdas con solo "$" o ")" por el
    formateo en columnas. Si no se filtran, las columnas se desalinean.

    Ojo con el paréntesis del negativo: EDGAR con frecuencia lo parte en celdas
    separadas — "(", "38,260", ")" — así que descartar los paréntesis a secas
    convierte una ganancia por venta de −38,260 en +38,260. En una conciliación
    aditiva eso es un error de dos veces la partida y, como el subtotal reportado
    no cambia, se manifiesta como un descuadre que parece venir de otro lado.
    """
    valores: list[float | None] = []
    negativo_pendiente = False
    for celda in fila[1:]:
        limpia = celda.strip()
        if limpia == "(":
            negativo_pendiente = True
            continue
        if limpia in {"$", ")", "%", ""}:
            continue
        # Tercera variante del mismo problema: el paréntesis de apertura viene
        # PEGADO al número y solo el de cierre queda en su propia celda —
        # "(9,105" seguido de ")"—. `parsear_numero` exige los dos para leer un
        # negativo, así que sin esto la ganancia por venta de NNN entraba en
        # positivo y desplazaba el FFO por el doble de la partida.
        abierto_sin_cerrar = limpia.startswith("(") and not limpia.endswith(")")
        valor = parsear_numero(limpia)
        if valor is not None and (negativo_pendiente or abierto_sin_cerrar):
            valor = -abs(valor)
        negativo_pendiente = False
        valores.append(valor)
    return valores


def _mapear_columnas(matriz: list[list[str]], periodos: list[Periodo]) -> dict[int, Periodo]:
    """Asocia índices de columna numérica con periodos.

    Cuenta cuántas columnas de datos tiene la fila modal y las reparte entre los
    periodos detectados. Si no cuadra, prefiere no adivinar y usa las primeras.
    """
    conteos = [len(_valores_alineados(f)) for f in matriz if len(f) > 1]
    conteos = [c for c in conteos if c > 0]
    if not conteos:
        return {}
    ancho = max(set(conteos), key=conteos.count)
    n = min(ancho, len(periodos))
    return {i: periodos[i] for i in range(n)}


# --------------------------------------------------------------------------------------
# Reconstrucción de trimestres a partir de acumulados
# --------------------------------------------------------------------------------------


def reconstruir_trimestres(
    observaciones: dict[str, tuple[float, dt.date]],
) -> dict[str, tuple[float, dt.date, str]]:
    """Reconstruye Q1 y Q3 desde acumulados.

    ``observaciones`` mapea ``'Q1'|'Q2'|'Q3'|'Q4'|'H1'|'FY'`` a ``(valor, fecha_publicacion)``.
    Devuelve solo lo reconstruido, con la fecha de publicación **máxima** de sus
    componentes y la fórmula usada.

    ``Q1 = H1 − Q2``  y  ``Q3 = FY − H1 − Q4``.
    """
    salida: dict[str, tuple[float, dt.date, str]] = {}

    if "Q1" not in observaciones and {"H1", "Q2"} <= observaciones.keys():
        (h1, f_h1), (q2, f_q2) = observaciones["H1"], observaciones["Q2"]
        salida["Q1"] = (h1 - q2, max(f_h1, f_q2), "Q1 = H1 − Q2")

    if "Q3" not in observaciones and {"FY", "H1", "Q4"} <= observaciones.keys():
        (fy, f_fy), (h1, f_h1), (q4, f_q4) = (
            observaciones["FY"],
            observaciones["H1"],
            observaciones["Q4"],
        )
        salida["Q3"] = (fy - h1 - q4, max(f_fy, f_h1, f_q4), "Q3 = FY − H1 − Q4")

    return salida


def fin_de_trimestre(anio: int, trimestre: int) -> dt.date:
    """Último día del trimestre calendario."""
    fines = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    mes, dia = fines[trimestre]
    return dt.date(anio, mes, dia)


def filas_reconstruidas(
    ticker: str,
    concepto: str,
    anio: int,
    reconstruido: dict[str, tuple[float, dt.date, str]],
    url_filing: str = "",
) -> list[dict]:
    """Convierte la salida de ``reconstruir_trimestres`` en filas de ``hechos``."""
    salida = []
    for etiqueta, (valor, publicacion, formula) in reconstruido.items():
        trimestre = int(etiqueta[1])
        salida.append(
            {
                "ticker": ticker,
                "concepto": concepto,
                "periodo_tipo": "Q",
                "fecha_dato": fin_de_trimestre(anio, trimestre),
                "fecha_publicacion": publicacion,
                "valor": valor,
                "unidad": "USD",
                "fuente": Fuente.RECONSTRUIDO,
                "es_primario": False,
                "url_filing": url_filing,
                "nota_validacion": formula,
            }
        )
    return salida
