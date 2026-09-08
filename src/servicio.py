"""Capa de servicio: arma los paneles que consume la interfaz.

Todo lo que la aplicación muestra pasa por aquí, y todo lo que pasa por aquí
recibe una fecha de corte. Es la última barrera antes de la pantalla: si una
página pudiera consultar el repositorio directamente sin corte, tarde o temprano
alguna lo haría.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import (
    MEDIDA_AFFO,
    MEDIDA_CORE_FFO,
    SERIE_CPI,
    SERIE_INPC,
    SERIE_UDIBONO10,
    SERIE_UST10,
    UMBRALES,
    Fuente,
)
from src.datos.repositorio import Repositorio
from src.modelo import senal as mod_senal
from src.modelo.valuacion import InsumosValuacion, panel_valuacion, rango_cap_rate

CONCEPTOS_PANEL = (
    "affo",
    "affo_por_accion",
    "ffo",
    # El FFO POR ACCIÓN, que no es un lujo: es la única forma de tener payout
    # sobre FFO en el emisor que dejó de publicar el subtotal en monto. Realty
    # Income lo hizo en septiembre de 2024 —su conciliación va de la utilidad
    # neta al FFO Normalizado sin pasar por el FFO de Nareit— pero sigue
    # imprimiendo "FFO per share" cada trimestre. El dato estaba en la base y el
    # panel no lo pedía, así que el renglón salía vacío por un hueco de código y
    # no de información.
    "ffo_por_accion",
    "ffo_normalizado",
    "noi",
    "utilidad_neta",
    "acciones_diluidas",
    "ingreso_rentas",
    # Del estado de resultados y del flujo, para armar el NOI y el EBITDAre. Sin
    # estos, tres de los cinco criterios de la Puerta 1 quedaban sin medir y el
    # veredicto era INCONCLUSO para las diez emisoras.
    "gasto_operacion_inmueble",
    "gastos_operativos_inmueble",
    "gasto_predial_seguro",
    "gasto_intereses",
    "impuestos",
    "depreciacion_amortizacion",
    "deterioro",
    "ganancia_venta_inmuebles",
    "ingresos",
)

# Rubros de BALANCE. Van aparte porque XBRL los fecha como saldo a una fecha
# —`periodo_tipo="PUNTUAL"`— y no como un flujo de un trimestre. Pedirlos junto
# con los demás, en la misma consulta de `periodo_tipo="Q"`, devolvía cero filas:
# es la segunda razón por la que la deuda nunca llegaba a la valuación.
CONCEPTOS_BALANCE = (
    "deuda_total",
    "efectivo",
    "prestamos_por_cobrar",
    "inversiones_no_consolidadas",
    "goodwill",
    "activos_totales",
    "inmuebles_neto",
    # Los tramos de deuda y el pasivo total: no se publican como métrica, entran
    # para poder ARMAR la deuda total del emisor que no la reporta junta — y para
    # DESMENTIR al que la reporta incompleta.
    "deuda_hipotecaria",
    "notas_senior",
    "linea_de_credito",
    "deuda_no_garantizada",
    "otras_notas_por_pagar",
    "prestamos_a_plazo",
    "pasivos_totales",
)

# Cuánto puede rezagarse un SALDO respecto del último balance de la emisora y
# seguir contando como vigente. Un trimestre se reporta a las seis semanas del
# cierre, así que medio año deja pasar un rezago normal —y una reexpresión que
# solo tocó algunos renglones— sin admitir un saldo de hace años.
VIGENCIA_DE_SALDO = pd.Timedelta(days=190)

# Los tramos que suman deuda, en el orden en que aparecen en un balance de REIT.
TRAMOS_DE_DEUDA = (
    "deuda_hipotecaria", "notas_senior", "linea_de_credito",
    "deuda_no_garantizada", "otras_notas_por_pagar", "prestamos_a_plazo",
)

# Cuántos días HÁBILES puede rezagarse el precio antes de dejar de ser "el último
# cierre". Tres cubren un puente largo —el mercado cierra hasta dos sesiones
# seguidas— sin dejar pasar una serie que de verdad se quedó atrás.
MAX_LATENCIA_PRECIO = 3


def _dias_habiles(desde: dt.date, hasta: dt.date) -> int:
    """Días de lunes a viernes entre dos fechas, sin contar el inicial."""
    if hasta <= desde:
        return 0
    return int(pd.bdate_range(desde + dt.timedelta(days=1), hasta).size)


# Cuánto pueden exceder los tramos al total declarado antes de creerles a ellos.
# No es una tolerancia de redondeo: es el margen que separa "los tramos y el total
# describen lo mismo" de "el total no es un total". Un 1% sobre una deuda de
# 25 mil millones son 250 MM, que ningún desfase de fechas de corte produce.
MARGEN_DE_TRAMOS = 0.01


# --------------------------------------------------------------------------------------
# Panel trimestral por emisor
# --------------------------------------------------------------------------------------


@dataclass
class PanelEmisor:
    """Todo lo que la página de valuación necesita de un emisor a una fecha."""

    ticker: str
    sector: str
    asof: dt.date
    trimestral: pd.DataFrame
    precio: float | None
    precio_fecha: dt.date | None
    dividendo_ttm: float | None
    tasa_libre_riesgo: float | None
    # Con qué medida se está valuando: "AFFO" o "Core FFO". No todos los emisores
    # publican AFFO, y presentar las dos bajo la misma etiqueta sería mentir.
    medida_flujo: str = "AFFO"
    metricas: dict[str, float | None] = field(default_factory=dict)
    prima: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))
    percentil: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))
    fuentes: pd.DataFrame = field(default_factory=pd.DataFrame)
    avisos: list[str] = field(default_factory=list)

    @property
    def percentil_actual(self) -> float | None:
        s = self.percentil.dropna()
        return float(s.iloc[-1]) if not s.empty else None

    @property
    def n_observaciones(self) -> int:
        return int(self.prima.dropna().shape[0])

    @property
    def solo_demo(self) -> bool:
        if self.fuentes.empty or "fuente" not in self.fuentes:
            return True
        return bool((self.fuentes["fuente"] == Fuente.DEMO).all())


def construir_panel(
    repo: Repositorio,
    ticker: str,
    *,
    asof: dt.date,
    cap_rate_mercado: float = 0.065,
    yield_adquisiciones: float | None = None,
    balance: dict[str, float] | None = None,
) -> PanelEmisor:
    """Arma el panel trimestral, la prima y su percentil expandible.

    El AFFO por acción se lleva a TTM antes de calcular el yield: un yield sobre
    un trimestre anualizado por cuatro es mucho más ruidoso, y en negocios con
    estacionalidad simplemente está mal.
    """
    avisos: list[str] = []
    sector = repo.sector_de(ticker) or "Diversificado"

    trimestral = repo.panel(ticker, CONCEPTOS_PANEL, asof=asof, periodo_tipo="Q")
    medida = MEDIDA_AFFO
    if not trimestral.empty:
        trimestral = trimestral.astype(float, errors="ignore")
        medida = _elegir_medida_de_flujo(trimestral)
        if medida == MEDIDA_CORE_FFO:
            avisos.append(
                f"{ticker} no publica AFFO: su conciliación termina en el Core FFO, y eso es "
                "lo que se está usando como medida de flujo. **No son lo mismo**: el AFFO "
                "resta además el CapEx recurrente y la renta en línea recta, así que el Core "
                "FFO queda por arriba del flujo realmente distribuible."
            )
        trimestral["affo_por_accion_ttm"] = _ttm(trimestral, "affo_por_accion")
        trimestral["affo_ttm"] = _ttm(trimestral, "affo")
        # El FFO y la utilidad neta se llevan a TTM con la MISMA regla que el
        # AFFO —cuatro trimestres consecutivos y verificados contra el
        # calendario—, porque los tres se comparan entre sí en la pantalla.
        trimestral["ffo_ttm"] = _ttm(trimestral, "ffo")
        trimestral["ffo_por_accion_ttm"] = _ttm(trimestral, "ffo_por_accion")
        trimestral["utilidad_neta_ttm"] = _ttm(trimestral, "utilidad_neta")
        # Si al AFFO por acción le falta un trimestre pero el monto sí está
        # completo, el TTM por acción se deduce del monto y del conteo de acciones.
        # Antes, un solo hueco en la serie por acción borraba al emisor de la
        # pantalla aunque toda la información necesaria estuviera en la base.
        acciones = pd.to_numeric(trimestral.get("acciones_diluidas"), errors="coerce")
        if acciones is not None:
            vivas = acciones.where(acciones > 0)
            deducido = trimestral["affo_ttm"] / vivas
            trimestral["affo_por_accion_ttm"] = trimestral["affo_por_accion_ttm"].fillna(deducido)
            # La misma deducción, trimestre a trimestre. Cinco emisoras —EPRT,
            # PSA, EXR, PLD y WELL— publican el MONTO del flujo pero no su cifra
            # por acción, y sin ella el criterio "AFFO por acción creciendo" no
            # era medible: tres de ellas se quedaban en dos criterios de cinco y
            # el veredicto salía INCONCLUSO teniendo el dato en la base.
            trimestral["affo_por_accion"] = pd.to_numeric(
                trimestral.get("affo_por_accion"), errors="coerce"
            ).fillna(pd.to_numeric(trimestral.get("affo"), errors="coerce") / vivas)
        trimestral["crecimiento_affo_por_accion_yoy"] = _yoy(trimestral, "affo_por_accion")
        trimestral["noi"] = _derivar_noi(trimestral)
        trimestral["ebitdare"] = _derivar_ebitdare(trimestral)
        trimestral["noi_ttm"] = _ttm(trimestral, "noi")
        trimestral["ebitdare_ttm"] = _ttm(trimestral, "ebitdare")
        trimestral["gasto_intereses_ttm"] = _ttm(trimestral, "gasto_intereses")

        # Decir por qué se cayó el apalancamiento. `_derivar_ebitdare` prefiere no
        # dar número antes que dar uno sin depreciación, y esa decisión es
        # correcta pero muda: en la pantalla el criterio aparece SIN DATOS y no
        # hay forma de saber si la emisora no reportó, si el dato viene en camino
        # o si el catálogo falló. Es el mismo hueco de siempre —un dato que falta
        # y no se anuncia— solo que ahora del lado de la explicación.
        if not _cuadro_con_depreciacion(trimestral):
            ultimo = trimestral.index[-1].date()
            avisos.append(
                f"El trimestre al {ultimo} de {ticker} trae utilidad e intereses pero no la "
                "depreciación, que en un REIT es la mayor de las partidas que se suman de "
                "vuelta. Sin ella no se calcula EBITDAre —el apalancamiento queda SIN DATOS "
                "en vez de salir subestimado— y el TTM que se usa termina en el trimestre "
                "anterior."
            )

    precios = repo.serie_precio(ticker, asof=asof)
    precio = float(precios.iloc[-1]) if not precios.empty else None
    precio_fecha = precios.index[-1].date() if not precios.empty else None
    # En días HÁBILES. Medido en días naturales, el umbral de cinco dejaba pasar
    # un rezago real de tres sesiones si caía sobre un fin de semana, y marcaba
    # como rezagado un precio que era el último cierre existente después de un
    # puente largo. La bolsa no opera en calendario.
    if precio_fecha is not None and _dias_habiles(precio_fecha, asof) > MAX_LATENCIA_PRECIO:
        avisos.append(
            f"El precio más reciente disponible es del {precio_fecha}, "
            f"{_dias_habiles(precio_fecha, asof)} días hábiles antes del corte. "
            "Latencia del dato, no dato en vivo."
        )

    dividendos = repo.dividendos(ticker, asof=asof)
    div_ttm = None
    if not dividendos.empty:
        corte = pd.Timestamp(asof)
        ventana = dividendos[
            (dividendos["fecha_ex"] <= corte)
            & (dividendos["fecha_ex"] > corte - pd.DateOffset(years=1))
        ]
        div_ttm = float(ventana["monto"].sum()) if not ventana.empty else None

    rf = repo.valor_tasa(SERIE_UST10, asof=asof)

    # Serie histórica de AFFO yield sobre precio CRUDO (P2), para la prima y su percentil.
    prima = pd.Series(dtype="float64")
    percentil = pd.Series(dtype="float64")
    if not trimestral.empty and not precios.empty:
        yield_hist = _serie_affo_yield(trimestral, precios)
        tasa_hist = repo.tasa(SERIE_UST10, asof=asof)
        if not yield_hist.empty and not tasa_hist.empty:
            prima = mod_senal.calcular_prima(yield_hist, tasa_hist)
            percentil = mod_senal.percentil_expandible(
                prima, min_observaciones=UMBRALES.valuacion.min_observaciones
            )

    # Los saldos de balance salen de la base salvo que quien llama traiga los
    # suyos: la pantalla de valuación deja mover supuestos, y lo explícito manda.
    saldos = _saldos_de_balance(repo, ticker, asof=asof)
    balance = {**saldos, **(balance or {})}

    corte_balance = _corte_de_balance(repo, ticker, asof=asof)
    corte_resultados = (
        pd.to_datetime(trimestral.index).max().date()
        if not trimestral.empty and len(trimestral.index) else None
    )
    if corte_balance is not None and corte_resultados is not None and corte_balance < corte_resultados:
        avisos.append(
            f"El balance de {ticker} es del {corte_balance} y sus resultados llegan al "
            f"{corte_resultados}: un trimestre de diferencia. El apalancamiento y el LTV "
            "de esta pantalla mezclan una deuda vieja con un flujo nuevo. Suele ser que "
            "`companyfacts` va atrasado para este emisor —el dato sí está en su 10-Q—, "
            "no que la emisora no haya reportado."
        )

    # El yield al que compra el emisor no está en XBRL: nadie publica el cap rate
    # de sus adquisiciones. Sin un supuesto, `spread_inversion` salía nulo para
    # las DIEZ emisoras y la Puerta 1 se quedaba con tres criterios medibles de
    # cinco — incluso las que tienen el balance completo. El supuesto por omisión
    # es el cap rate BASE DE SU SECTOR, el mismo con el que se arma el NAV: un
    # industrial compra cerca de 5.5% y una oficina arriba de 8.75%, y un número
    # único para todos metía un sesgo de sector en un criterio binario. Sigue
    # siendo un supuesto y la pantalla lo dice; quien lo mueva, manda.
    if yield_adquisiciones is None:
        yield_adquisiciones = rango_cap_rate(sector)[1]

    metricas = _metricas(
        trimestral, precio, div_ttm, rf, cap_rate_mercado, yield_adquisiciones, balance, ticker, sector
    )

    fuentes = repo.hechos(
        asof=asof, tickers=ticker, conceptos=[*CONCEPTOS_PANEL, *CONCEPTOS_BALANCE]
    )
    if not fuentes.empty:
        fuentes = fuentes[
            ["concepto", "periodo_tipo", "fecha_dato", "fecha_publicacion", "valor",
             "fuente", "es_primario", "url_filing", "estado"]
        ].sort_values(["fecha_dato", "concepto"], ascending=[False, True])
        if (fuentes["fuente"] == Fuente.DEMO).all():
            avisos.append(
                "Todos los fundamentales de este emisor son de DEMOSTRACIÓN. No decidas con "
                "esta pantalla: corre la ingesta de EDGAR para traer datos de fuente primaria."
            )

    sospechosos = repo.hechos(
        asof=asof, tickers=ticker, conceptos=list(CONCEPTOS_PANEL), incluir_sospechosos=True
    )
    if not sospechosos.empty and "estado" in sospechosos:
        n = int((sospechosos["estado"] != "valido").sum())
        if n:
            avisos.append(
                f"{n} registro(s) de este emisor están marcados SOSPECHOSOS por no cuadrar "
                "su conciliación. No participan en ningún cálculo de esta pantalla."
            )

    return PanelEmisor(
        ticker=ticker,
        sector=sector,
        asof=asof,
        trimestral=trimestral,
        precio=precio,
        precio_fecha=precio_fecha,
        dividendo_ttm=div_ttm,
        tasa_libre_riesgo=rf,
        medida_flujo=medida,
        metricas=metricas,
        prima=prima,
        percentil=percentil,
        fuentes=fuentes,
        avisos=avisos,
    )


def _elegir_medida_de_flujo(trimestral: pd.DataFrame) -> str:
    """Decide con qué medida de flujo se valúa a este emisor, y lo dice.

    No todos los REITs publican AFFO. El self storage y buena parte de salud
    terminan su conciliación en el **Core FFO**, y Public Storage, Extra Space y
    Welltower son de ese grupo: el suplemento no trae la línea.

    Ante eso hay dos salidas malas y una buena. Dejar al emisor en blanco borra a
    un sector entero de la pantalla. Copiar el Core FFO a la casilla del AFFO
    **miente**: el AFFO resta además el CapEx recurrente y la renta en línea recta,
    así que el Core FFO queda por arriba del flujo distribuible. La buena es usar
    el Core FFO y decir en la pantalla que es Core FFO.

    Cuando se sustituye se copia también la serie por acción, para que el TTM y el
    crecimiento se calculen sobre la misma medida y no sobre dos distintas.
    """
    hay_affo = "affo" in trimestral and pd.to_numeric(
        trimestral["affo"], errors="coerce"
    ).notna().any()
    if hay_affo:
        return MEDIDA_AFFO

    hay_core = "ffo_normalizado" in trimestral and pd.to_numeric(
        trimestral["ffo_normalizado"], errors="coerce"
    ).notna().any()
    if not hay_core:
        return MEDIDA_AFFO  # no hay ninguna de las dos: se queda como está, en blanco

    trimestral["affo"] = pd.to_numeric(trimestral["ffo_normalizado"], errors="coerce")
    if "ffo_normalizado_por_accion" in trimestral:
        trimestral["affo_por_accion"] = pd.to_numeric(
            trimestral["ffo_normalizado_por_accion"], errors="coerce"
        )
    return MEDIDA_CORE_FFO


def _ttm(trimestral: pd.DataFrame, concepto: str) -> pd.Series:
    """Suma los últimos doce meses, exigiendo que sean CUATRO TRIMESTRES SEGUIDOS.

    Un ``rolling(4)`` cuenta filas, no calendario. Si al panel le falta un
    trimestre, la ventana abarca cinco trimestres de calendario y devuelve un
    "TTM" que no son doce meses. No hay nada en el resultado que lo delate: la
    suma cuadra, el número se ve razonable, y el yield que sale de ahí está mal.

    Aquí la ventana se valida contra las fechas: solo se emite el TTM cuando los
    cuatro trimestres del periodo existen y son consecutivos.
    """
    if concepto not in trimestral:
        return pd.Series(index=trimestral.index, dtype="float64")
    serie = pd.to_numeric(trimestral[concepto], errors="coerce")
    fechas = pd.PeriodIndex(pd.to_datetime(trimestral.index), freq="Q")
    salida = pd.Series(index=trimestral.index, dtype="float64")
    for i in range(3, len(serie)):
        ventana = serie.iloc[i - 3 : i + 1]
        # Cuatro trimestres seguidos abarcan exactamente tres saltos de trimestre.
        if (fechas[i] - fechas[i - 3]).n != 3 or ventana.isna().any():
            continue
        salida.iloc[i] = float(ventana.sum())
    return salida


def _yoy(trimestral: pd.DataFrame, concepto: str) -> pd.Series:
    """Variación contra el MISMO trimestre del año pasado, verificada en calendario.

    ``pct_change(4)`` cuenta filas, no calendario — el mismo defecto que ``_ttm``
    corrige para la suma. Si al panel le falta un trimestre, compara contra el de
    hace cinco y el resultado se lee como crecimiento anual sin serlo. Y aquí
    importa doble: de este número depende un criterio binario de la Puerta 1, así
    que un año mal medido no da un número raro, da un veredicto equivocado.
    """
    if concepto not in trimestral:
        return pd.Series(index=trimestral.index, dtype="float64")
    serie = pd.to_numeric(trimestral[concepto], errors="coerce")
    fechas = pd.PeriodIndex(pd.to_datetime(trimestral.index), freq="Q")
    salida = pd.Series(index=trimestral.index, dtype="float64")
    for i in range(4, len(serie)):
        previo = serie.iloc[i - 4]
        # Cuatro trimestres atrás son exactamente cuatro saltos de trimestre.
        if (fechas[i] - fechas[i - 4]).n != 4 or pd.isna(previo) or previo == 0:
            continue
        actual = serie.iloc[i]
        if pd.isna(actual):
            continue
        salida.iloc[i] = float(actual) / float(previo) - 1.0
    return salida


def _col(df: pd.DataFrame, *nombres: str) -> pd.Series:
    """La primera columna que exista, como serie numérica; ceros si ninguna.

    Las emisoras no etiquetan igual: unas reportan los gastos del inmueble bajo
    ``gasto_operacion_inmueble`` y otras bajo ``gastos_operativos_inmueble``.
    Devolver ceros en vez de propagar ``NaN`` es deliberado **solo para las
    partidas que suman**: un deterioro ausente es un deterioro de cero, y exigirlo
    borraría el EBITDAre de media docena de emisoras por un renglón que no
    tuvieron. Las partidas sin las cuales el resultado no significa nada se
    verifican aparte, en la función que llama.
    """
    for nombre in nombres:
        if nombre in df:
            serie = pd.to_numeric(df[nombre], errors="coerce")
            if serie.notna().any():
                # Los huecos POR RENGLÓN también son ceros, y esto no es un
                # detalle: un trimestre sin deterioro —que es el trimestre
                # normal— dejaba `NaN`, el EBITDAre de ese trimestre salía nulo,
                # y con él se caía el TTM entero de cuatro trimestres seguidos.
                # Media docena de emisoras se quedaban sin apalancamiento por un
                # renglón que la emisora no tuvo que reportar.
                return serie.fillna(0.0)
    return pd.Series(0.0, index=df.index)


# Un NOI de propiedad por debajo de esta fracción del ingreso significa que la
# derivación no cubre el negocio, no que el negocio sea malo. Un REIT de renta
# pura ronda 65%–75%; uno con operación propia baja, pero no a un dígito.
PISO_NOI_SOBRE_INGRESO = 0.20


def _col_estricta(df: pd.DataFrame, *nombres: str) -> pd.Series | None:
    """Como `_col`, pero devuelve ``None`` si ninguna columna trae datos.

    Para las partidas SIN LAS CUALES el resultado no significa nada. La
    diferencia con `_col` no es de estilo: ahí un hueco es un cero legítimo
    —nadie reporta un deterioro que no tuvo— y aquí un hueco invalida el cálculo.
    """
    for nombre in nombres:
        if nombre in df:
            serie = pd.to_numeric(df[nombre], errors="coerce")
            if serie.notna().any():
                return serie.fillna(0.0)
    return None


def _derivar_noi(trimestral: pd.DataFrame) -> pd.Series:
    """``NOI = ingreso por renta − gastos operativos del inmueble``.

    Se deriva porque XBRL no tiene una etiqueta de NOI: es una medida de la
    industria inmobiliaria, no del GAAP. Si la emisora publicó un NOI propio, ese
    manda; solo se reconstruye cuando falta.

    Excluye a propósito corporativo, depreciación e intereses: el NOI mide lo que
    produce el ladrillo antes de cómo esté financiado, y meterle el corporativo lo
    convierte en otra cosa que además no es comparable entre emisores.

    Se exigen **las dos piernas**: el ingreso por renta y el gasto del inmueble.
    Derivarlo con una sola produce un número peor que el hueco, y las dos formas
    de romperlo se vieron al construir esto. Sin la pierna de gastos, el NOI sale
    igual al ingreso —margen de 100%— y el NAV se dispara. Y usar el ingreso
    TOTAL como sustituto de la renta rompe a las emisoras cuya facturación no es
    renta: Welltower, con su operación de vivienda para adultos mayores, quedaba
    con un cap rate implícito de 0.89% y un NAV de 19 dólares para una acción que
    cotiza arriba de 150. Ninguno de los dos números levanta una excepción.
    """
    reportado = (
        pd.to_numeric(trimestral["noi"], errors="coerce")
        if "noi" in trimestral else pd.Series(index=trimestral.index, dtype="float64")
    )
    renta = _col_estricta(trimestral, "ingreso_rentas")
    gastos = _col_estricta(trimestral, "gasto_operacion_inmueble", "gastos_operativos_inmueble")
    if renta is None or gastos is None:
        return reportado
    derivado = renta - gastos - _col(trimestral, "gasto_predial_seguro")
    # Un NOI no positivo no es un NOI: es una pierna que no cuadra con la otra.
    derivado = derivado.where((renta > 0) & (derivado > 0))

    # Y un NOI que es una astilla del ingreso tampoco lo es. Welltower factura la
    # mayor parte por operación de vivienda para adultos mayores, no por renta
    # triple neta: derivar su NOI de la línea de renta captura una fracción del
    # negocio y da un cap rate implícito de 0.89% con un NAV de 19 dólares para
    # una acción que cotiza arriba de 150. La aritmética es correcta; el alcance
    # no. Cuando el NOI derivado no llega a una quinta parte del ingreso, la
    # derivación no está viendo el negocio y se prefiere no publicar número.
    ingresos = _col_estricta(trimestral, "ingresos", "ingreso_rentas")
    if ingresos is not None:
        derivado = derivado.where(
            (ingresos <= 0) | (derivado / ingresos >= PISO_NOI_SOBRE_INGRESO)
        )
    return reportado.fillna(derivado)


def _cuadro_con_depreciacion(trimestral: pd.DataFrame) -> bool:
    """¿El último trimestre tiene lo que hace falta para un EBITDAre completo?

    Devuelve True también cuando el trimestre no tiene ni utilidad ni intereses:
    ahí el hueco es evidente en la propia serie y no necesita aviso. Lo que se
    quiere señalar es el caso callado —el trimestre que sí llegó, pero incompleto
    justo en la partida más grande.
    """
    if trimestral.empty:
        return True
    ultimo = trimestral.iloc[-1]
    cifras = pd.to_numeric(
        pd.Series(
            [ultimo.get(c) for c in
             ("utilidad_neta", "gasto_intereses", "depreciacion_amortizacion")]
        ),
        errors="coerce",
    )
    utilidad, intereses, depreciacion = cifras
    if pd.isna(utilidad) or pd.isna(intereses) or intereses <= 0:
        return True
    return not pd.isna(depreciacion)


def _derivar_ebitdare(trimestral: pd.DataFrame) -> pd.Series:
    """EBITDAre según Nareit, que no es el EBITDA de un industrial.

    ``utilidad neta + intereses + impuestos + depreciación y amortización
    + deterioro − ganancia por venta de inmuebles``

    Las dos últimas partidas son las que lo separan del EBITDA común y las que lo
    hacen servir para un REIT: sin quitar la ganancia por venta, un emisor que
    vendió un edificio grande aparece desapalancado un trimestre y vuelve a estar
    apalancado el siguiente, sin que su deuda se haya movido.

    Exige utilidad neta, intereses y DEPRECIACIÓN. Sin intereses el resultado no
    es EBITDAre —es utilidad operativa con otro nombre— y el apalancamiento que
    salga de ahí estaría sistemáticamente sobrestimado.

    La depreciación se exige por la razón contraria y más grande. En un REIT es
    la mayor de todas las partidas que se suman de vuelta: en Welltower vale más
    que la utilidad neta y los intereses juntos. Tratarla como opcional la
    convertía en cero, y un cero ahí no produce un EBITDAre incompleto: produce
    otro número, más chico, que entra al ratio de apalancamiento como si fuera
    el bueno.

    Pasó en el trimestre de junio de 2026 de Welltower. Su 10-Q sí trae la
    depreciación —737.8 millones— pero bajo una etiqueta que la cadena de este
    renglón no alcanza, porque las dos etiquetas que la emisora usó difieren
    hasta 24% entre 2009 y 2012 y el empalme verificado las rechaza, con razón.
    Con la depreciación en cero el trimestre daba un EBITDAre de 608.7 en vez de
    1,320.7, el TTM caía a 4,109 y el apalancamiento salía en 3.84x cuando es
    3.27x. Nada en la pantalla lo delataba.

    Que falte el dato es un problema; que falte y el número salga igual es peor.
    Cuesta cinco trimestres en todo el universo —cuatro de 2009 y el de junio de
    2026, los cinco de Welltower— y a cambio el ratio no miente nunca.
    """
    if "utilidad_neta" not in trimestral:
        return pd.Series(index=trimestral.index, dtype="float64")
    utilidad = pd.to_numeric(trimestral["utilidad_neta"], errors="coerce")
    intereses = _col(trimestral, "gasto_intereses")
    if not (intereses > 0).any():
        return pd.Series(index=trimestral.index, dtype="float64")
    depreciacion = pd.to_numeric(
        trimestral.get("depreciacion_amortizacion", pd.Series(index=trimestral.index, dtype="float64")),
        errors="coerce",
    )
    suma = (
        utilidad
        + intereses
        + _col(trimestral, "impuestos")
        + depreciacion.fillna(0.0)
        + _col(trimestral, "deterioro")
        - _col(trimestral, "ganancia_venta_inmuebles")
    )
    return suma.where(utilidad.notna() & (intereses > 0) & depreciacion.notna())


def _saldos_de_balance(repo: Repositorio, ticker: str, *, asof: dt.date) -> dict[str, float]:
    """El último saldo de cada rubro de balance conocido al corte.

    Un saldo no se anualiza ni se promedia: ya viene a una fecha. Se toma el más
    reciente **publicado** antes del corte, que es lo que un analista tendría ese
    día en la mano.
    """
    hechos = repo.hechos(
        asof=asof, tickers=ticker, conceptos=list(CONCEPTOS_BALANCE), periodo_tipo="PUNTUAL"
    )
    if hechos.empty:
        return {}
    hechos = hechos.sort_values(["fecha_dato", "fecha_publicacion"])
    ultimos = hechos.drop_duplicates("concepto", keep="last")

    # Un saldo VIEJO no es el saldo de hoy, y en un balance esa diferencia es
    # invisible. En una serie de flujo se ve que los datos se acaban; un saldo se
    # presenta como "el último conocido" y entra al ratio como si fuera actual.
    #
    # Extra Space traía su deuda total de `NotesPayable`, cuya última observación
    # es del 30 de septiembre de 2021: cinco años vieja. Con ella el
    # apalancamiento salía en 2.0x —de los más sanos del universo— cuando sus
    # tramos vigentes suman más del doble de esa deuda. Conservar la etiqueta con
    # más cobertura cuando ninguna está viva es razonable para un flujo, cuya
    # antigüedad la pantalla declara, y es peligroso para un saldo.
    #
    # El corte se mide contra el balance MÁS RECIENTE de la propia emisora, no
    # contra el calendario: quien no ha reportado en un año no tiene un saldo
    # viejo, tiene un reporte pendiente.
    corte_balance = pd.Timestamp(ultimos["fecha_dato"].max())
    saldos = {
        r["concepto"]: float(r["valor"])
        for _, r in ultimos.iterrows()
        if pd.notna(r["valor"])
        and pd.Timestamp(r["fecha_dato"]) >= corte_balance - VIGENCIA_DE_SALDO
    }
    # Un REIT con deuda cero no existe: es una etiqueta GAAP mal elegida, no un
    # balance sin apalancamiento. Global Net Lease salía con deuda de cero y un
    # apalancamiento negativo, que se dibuja como si estuviera desapalancado —
    # justo al revés de su situación real.
    if saldos.get("deuda_total", 0.0) <= 0:
        saldos.pop("deuda_total", None)

    # Sin un total vigente se arma de sus tramos. Y con él también, si los tramos
    # lo superan: un "total" al que sus propias partes le ganan no es un total,
    # es un tramo con nombre de total.
    #
    # Realty Income es el caso. `NotesPayable` se leía como su deuda total y son
    # sus notas senior: 25,092 MM de los 30,652 que debe. Faltaban los préstamos a
    # plazo (2,760) y la revolvente con el papel comercial (2,763). Nada en el
    # resultado lo delataba —el número es grande, creciente y con historia— y el
    # error empujaba el apalancamiento de 5.68x a 4.63x y el NAV de 53.54 a 59.49
    # dólares: el emisor se veía más sano y más barato de lo que está, que son las
    # dos direcciones en las que un error de balance sí cambia una decisión.
    #
    # La comparación es contra los tramos IDENTIFICADOS, así que la guarda solo
    # puede corregir hacia arriba y nunca inventa deuda: cada peso que suma salió
    # de una etiqueta del propio emisor, y `_deuda_compuesta` descarta la suma que
    # excede su pasivo total, que es la forma en que un doble conteo se delata.
    compuesta = _deuda_compuesta(saldos)
    declarada = saldos.get("deuda_total")
    if compuesta is not None and (
        declarada is None or compuesta > declarada * (1.0 + MARGEN_DE_TRAMOS)
    ):
        saldos["deuda_total"] = compuesta
    return saldos


def _corte_de_balance(repo: Repositorio, ticker: str, *, asof: dt.date) -> dt.date | None:
    """La fecha del balance más reciente que conocemos de este emisor.

    Existe para poder contrastarla contra la fecha de sus RESULTADOS. Cuando el
    balance se queda atrás y el estado de resultados no, el apalancamiento y el
    LTV combinan una deuda de un trimestre con un flujo de otro, y nada en el
    número lo delata: sale un ratio perfectamente plausible.

    Es lo que pasa hoy con Prologis y Welltower. Sus 10-Q de junio están
    presentados —el balance está impreso ahí— pero `companyfacts` todavía publica
    marzo como su último corte, mientras el AFFO y la utilidad de junio sí entran
    porque vienen del 8-K. La emisora no va tarde: la API sí.
    """
    hechos = repo.hechos(
        asof=asof, tickers=ticker, conceptos=list(CONCEPTOS_BALANCE), periodo_tipo="PUNTUAL"
    )
    if hechos.empty:
        return None
    return pd.to_datetime(hechos["fecha_dato"]).max().date()


def _deuda_compuesta(saldos: dict[str, float]) -> float | None:
    """La deuda total sumando sus tramos, para el emisor que no la reporta junta.

    Global Net Lease no publica ningún renglón de deuda total: publica la
    hipotecaria, las notas senior y la línea revolvente por separado, y sin
    sumarlas no hay apalancamiento, ni LTV, ni NAV — su Puerta 1 se quedaba con
    dos criterios medibles de cinco.

    Sumar tramos tiene un riesgo asimétrico y conviene decirlo: si falta uno, la
    deuda sale MENOR de la real y el emisor se dibuja más sano de lo que está.
    Es justo lo que iba a pasar aquí. Con la hipotecaria (987 MM) y las notas
    (940 MM) el total daba 1,927 MM; la revolvente —473 MM, otro 20%— estaba en
    ``LineOfCredit`` y no la contaba nadie. Por eso los tres tramos entran juntos
    y el resultado se contrasta contra el pasivo total: una suma que lo excede no
    es deuda, es doble conteo, y entonces vale más no publicar nada.
    """
    tramos = {k: saldos[k] for k in TRAMOS_DE_DEUDA if saldos.get(k, 0.0) > 0}
    if not tramos:
        return None
    total = float(sum(tramos.values()))
    pasivos = saldos.get("pasivos_totales")
    if pasivos is not None and total > float(pasivos):
        return None
    return total


def _serie_affo_yield(trimestral: pd.DataFrame, precios: pd.Series) -> pd.Series:
    """AFFO yield TTM por fecha de trimestre, sobre precio de cierre **sin ajustar**."""
    if "affo_por_accion_ttm" not in trimestral:
        return pd.Series(dtype="float64")
    affo = pd.to_numeric(trimestral["affo_por_accion_ttm"], errors="coerce").dropna()
    if affo.empty:
        return pd.Series(dtype="float64")
    px = precios.copy()
    px.index = pd.to_datetime(px.index)
    alineado = px.reindex(px.index.union(pd.to_datetime(affo.index))).ffill().reindex(
        pd.to_datetime(affo.index)
    )
    y = affo.to_numpy() / alineado.to_numpy()
    serie = pd.Series(y, index=pd.to_datetime(affo.index), name="affo_yield")
    return serie.replace([np.inf, -np.inf], np.nan).dropna()


def _metricas(
    trimestral: pd.DataFrame,
    precio: float | None,
    div_ttm: float | None,
    rf: float | None,
    cap_rate: float,
    yield_adq: float | None,
    balance: dict[str, float] | None,
    ticker: str,
    sector: str,
) -> dict[str, float | None]:
    if trimestral.empty or precio is None:
        return {}
    # Basta con tener el TTM por acción O el TTM del monto: `panel_valuacion` sabe
    # dividir el segundo entre las acciones. Exigir el primero borraba al emisor
    # entero de la pantalla por un hueco de un trimestre en una sola serie.
    con_ttm = trimestral.dropna(subset=["affo_por_accion_ttm", "affo_ttm"], how="all")
    if con_ttm.empty:
        return {}
    # El renglón que se usa tiene que traer con qué dividir. Sin el flujo POR ACCIÓN
    # hace falta el conteo de acciones, y a Welltower le faltaba justo en el último
    # trimestre: el respaldo de "acciones = 1" convertía un flujo de 4,000 millones
    # en 4,000 millones POR ACCIÓN, y el yield salía en 17 millones por ciento. Un
    # número absurdo es peor que ningún número; se retrocede al último renglón
    # completo en vez de inventar el denominador.
    utilizable = con_ttm[
        con_ttm["affo_por_accion_ttm"].notna()
        | (pd.to_numeric(con_ttm.get("acciones_diluidas"), errors="coerce") > 0)
    ]
    ultima = (utilizable if not utilizable.empty else con_ttm).tail(1)
    fila = ultima.iloc[0]
    balance = balance or {}
    # Un conteo de acciones no positivo no es un dato: es una fórmula equivocada
    # aguas arriba. Dividir entre él le voltea el signo a toda métrica por acción.
    acciones_reportadas = _f(fila.get("acciones_diluidas"))
    if (acciones_reportadas or 0) <= 0 and _f(fila.get("affo_por_accion_ttm")) is None:
        return {}
    acciones = acciones_reportadas if (acciones_reportadas or 0) > 0 else 1.0

    ins = InsumosValuacion(
        ticker=ticker,
        precio=precio,
        acciones_diluidas=acciones,
        noi_trimestral=_f(fila.get("noi")),
        affo_ttm=_f(fila.get("affo_ttm")),
        affo_por_accion_ttm=_f(fila.get("affo_por_accion_ttm")),
        # Los tres payouts se comparan entre sí en la misma tarjeta —"el mismo
        # dividendo, tres respuestas"— así que los tres denominadores tienen que
        # estar construidos igual. Anualizar UN trimestre por cuatro contra un
        # AFFO que sí es TTM real no comparaba tres medidas del mismo dividendo:
        # comparaba dos ventanas de tiempo distintas. En GNL el payout sobre FFO
        # salía 288% donde el TTM da 181%, y en EPRT el payout sobre utilidad
        # neta cruzaba el 100% —el umbral que pinta la barra de rojo— por el puro
        # efecto de la anualización.
        ffo_ttm=_f(fila.get("ffo_ttm")),
        ffo_por_accion_ttm=_f(fila.get("ffo_por_accion_ttm")),
        utilidad_neta_ttm=_f(fila.get("utilidad_neta_ttm")),
        # El NOI anualizado sale del TTM real cuando existe, y solo se cae al
        # trimestre por cuatro si no hay cuatro trimestres seguidos. El NAV y el
        # cap rate implícito cuelgan de este número, y anualizar un trimestre en
        # un negocio con adquisiciones desiguales mueve el NAV más que cualquier
        # otro supuesto salvo el propio cap rate.
        noi_anualizado=_f(fila.get("noi_ttm")),
        # EBITDAre de los últimos doce meses: es el denominador del apalancamiento
        # y sin él la Puerta 1 se quedaba sin uno de sus cinco criterios.
        ebitdare_ttm=_f(fila.get("ebitdare_ttm")),
        # El gasto por intereses TTM, del estado de resultados. `intereses_ttm`
        # alimenta el costo implícito de la deuda, que a su vez alimenta el costo
        # marginal del capital y con él el spread de inversión: otro criterio.
        intereses_ttm=_f(fila.get("gasto_intereses_ttm")),
        dividendo_ttm_por_accion=div_ttm,
        sector=sector,
        **{k: v for k, v in balance.items() if k in InsumosValuacion.__dataclass_fields__},
    )
    metricas = panel_valuacion(
        ins, cap_rate_mercado=cap_rate, yield_adquisiciones=yield_adq, tasa_libre_riesgo=rf
    )
    metricas["crecimiento_affo_por_accion_yoy"] = _f(fila.get("crecimiento_affo_por_accion_yoy"))

    # `InsumosValuacion` da por omisión una deuda de cero, que es razonable para
    # un supuesto pero no para un emisor cuyo balance no se pudo leer: con deuda
    # cero y efectivo positivo la deuda NETA sale negativa, y el apalancamiento
    # se dibuja en −0.87x, que se lee como «menos que desapalancado» justo en el
    # emisor más endeudado del universo. Lo que no se sabe no se publica.
    if "deuda_total" not in balance:
        for clave in ("deuda_neta", "deuda_neta_ebitdare", "ltv", "costo_implicito_deuda",
                      "costo_marginal_capital", "spread_inversion"):
            metricas[clave] = None
    return metricas


def _f(v) -> float | None:
    if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
        return None
    return float(v)


# --------------------------------------------------------------------------------------
# Estados financieros
# --------------------------------------------------------------------------------------


def estado_financiero(
    repo: Repositorio,
    ticker: str,
    estado: str,
    *,
    asof: dt.date,
    periodo_tipo: str = "Q",
    n_periodos: int = 8,
) -> pd.DataFrame:
    """Un estado financiero al corte, en formato ancho: renglones × periodos.

    Se arma desde la base y no desde EDGAR: los tres estados ya están persistidos
    como conceptos, así que dibujarlos no cuesta una descarga. El orden de los
    renglones es el de la taxonomía —ingresos arriba, utilidad neta abajo— y no el
    alfabético, porque un estado financiero desordenado no es un estado
    financiero.

    Todo pasa por ``repo.hechos``, que filtra por fecha de publicación: lo que se
    ve es lo que se sabía al corte, no la reexpresión posterior.
    """
    from src.ingesta.estados import ESTADOS_DE_SALDO, LINEA_POR_CLAVE, lineas_de

    lineas = lineas_de(estado)
    if not lineas:
        return pd.DataFrame()
    claves = [ln.clave for ln in lineas]
    tipo = "PUNTUAL" if estado in ESTADOS_DE_SALDO else periodo_tipo

    hechos = repo.hechos(asof=asof, tickers=ticker, conceptos=claves, periodo_tipo=tipo)
    if hechos.empty:
        return pd.DataFrame()

    # De cada periodo, la versión más reciente conocida al corte.
    hechos = hechos.sort_values(["fecha_dato", "concepto", "fecha_publicacion"])
    hechos = hechos.drop_duplicates(["concepto", "fecha_dato"], keep="last")

    ancho = hechos.pivot(index="concepto", columns="fecha_dato", values="valor")
    # Fuera las fechas que no son un corte contable. El conteo de acciones en
    # circulación se fecha en la PORTADA del 10-Q —un día de abril o de julio— y
    # abría una columna con un solo renglón lleno junto al balance de verdad, que
    # se lee como si al trimestre le faltara todo lo demás.
    if len(ancho.columns) > 1:
        llenado = ancho.notna().mean()
        ancho = ancho.loc[:, llenado >= 0.25]
    if ancho.empty or not len(ancho.columns):
        return pd.DataFrame()
    ancho = ancho[sorted(ancho.columns)[-n_periodos:]]
    ancho = ancho.reindex([c for c in claves if c in ancho.index])
    ancho.insert(0, "Renglón", [LINEA_POR_CLAVE[c].etiqueta for c in ancho.index])
    ancho.columns = [
        c if isinstance(c, str) else pd.Timestamp(c).date().isoformat() for c in ancho.columns
    ]
    return ancho.reset_index(drop=True)


# Qué renglón del estado financiero alimenta cada insumo del modelo. Es la tabla
# que contesta «¿de dónde salió este número?» sin abrir el código: a la izquierda
# lo que usa la valuación, a la derecha las líneas que la SEC publicó.
ORIGEN_DE_INSUMOS: tuple[tuple[str, str, str], ...] = (
    ("NOI trimestral", "ingreso_rentas − gasto_operacion_inmueble − gasto_predial_seguro",
     "XBRL no tiene etiqueta de NOI: es una medida de la industria, no del GAAP. "
     "Si la emisora publica el suyo, ese manda."),
    ("EBITDAre TTM",
     "utilidad_neta + gasto_intereses + impuestos + depreciacion_amortizacion "
     "+ deterioro − ganancia_venta_inmuebles",
     "Definición Nareit. Las dos últimas partidas son las que lo separan del "
     "EBITDA común y las que lo hacen servir para un REIT."),
    ("Deuda neta", "deuda_total − efectivo",
     "Saldos del balance a la última fecha publicada antes del corte."),
    ("Acciones diluidas", "acciones_diluidas",
     "Incluye las unidades de la sociedad operativa: es el conteo que reparte el flujo."),
    ("AFFO / Core FFO TTM", "affo (conciliación del 8-K), cuatro trimestres consecutivos",
     "No sale de XBRL: es no-GAAP y vive en el Exhibit 99.1 del comunicado."),
    ("Dividendo TTM", "dividendos con fecha ex dentro de los últimos doce meses",
     "Del calendario de dividendos, no del estado de resultados."),
    ("Precio", "cierre sin ajustar",
     "Sin ajustar por dividendos: ajustarlo mueve el yield histórico y lo vuelve "
     "incomparable consigo mismo."),
)


# Los insumos SIN LOS CUALES no hay veredicto, y qué criterio de la Puerta 1 se
# lleva cada uno al faltar. Es el mapa que convierte un INCONCLUSO en una frase
# accionable: no "faltan datos", sino "falta ESTE dato y por eso falta ESTE criterio".
INSUMOS_CRITICOS: tuple[tuple[str, str], ...] = (
    ("gasto_intereses", "EBITDAre, costo de la deuda y spread de inversión"),
    ("depreciacion_amortizacion", "EBITDAre"),
    ("utilidad_neta", "EBITDAre"),
    ("ingreso_rentas", "NOI"),
    ("acciones_diluidas", "flujo por acción"),
)

# Cuánto puede llevar una serie sin actualizarse antes de que deje de servir para
# valuar HOY. Un trimestre se publica a las seis semanas del cierre; quince meses
# deja pasar un rezago normal y marca lo que de verdad se quedó atrás.
VIGENCIA_DE_INSUMO = pd.Timedelta(days=458)


def diagnostico_de_insumos(
    panel: PanelEmisor, *, asof: dt.date | None = None
) -> pd.DataFrame:
    """Por qué este emisor no llega a un veredicto, insumo por insumo.

    "INCONCLUSO" es honesto pero no es accionable: no dice si falta un dato que se
    puede conseguir, si la emisora dejó de publicarlo, o si nunca lo publicó. Y la
    diferencia importa — dos emisoras del universo, Extra Space y Welltower, no
    tienen EBITDAre por una sola razón concreta: **ninguna etiqueta su gasto por
    intereses en XBRL**. Welltower dejó de hacerlo en el tercer trimestre de 2024 y
    Extra Space en el primero de 2024, y `companyfacts` no expone las etiquetas de
    extensión de cada emisora, así que ahí no está.

    Se probaron tres caminos para reconstruirlo y los tres se descartaron **con
    medición**, no por opinión: desde la utilidad de operación (9% a 70% de error
    contra el interés reportado), con el interés PAGADO del flujo de efectivo (5%
    a 11% de error de mediana, con dos años de Extra Space arriba de 600%) y como
    residual del estado de resultados (19% a 113%). Un apalancamiento con 60% de
    error no es un apalancamiento conservador, es uno inventado.

    Devuelve una fila por insumo con su estado —``completo``, ``rezagado`` o
    ``ausente``—, la última fecha con dato y qué se cae sin él.
    """
    corte = pd.Timestamp(asof or panel.asof)
    trimestral = panel.trimestral
    filas: list[dict] = []
    for concepto, para_que in INSUMOS_CRITICOS:
        serie = (
            pd.to_numeric(trimestral[concepto], errors="coerce").dropna()
            if concepto in trimestral
            else pd.Series(dtype="float64")
        )
        ultima = pd.Timestamp(serie.index.max()) if not serie.empty else None
        if ultima is None:
            estado = "ausente"
        elif corte - ultima > VIGENCIA_DE_INSUMO:
            estado = "rezagado"
        else:
            estado = "completo"
        filas.append({
            "insumo": concepto,
            "estado": estado,
            "trimestres": int(serie.shape[0]),
            "ultima_fecha": None if ultima is None else ultima.date(),
            "sin_el_no_hay": para_que,
        })
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# Semáforo
# --------------------------------------------------------------------------------------


def evaluar(panel: PanelEmisor) -> mod_senal.Semaforo:
    """Corre las tres puertas sobre el panel."""
    historial = panel.trimestral.copy()
    if not historial.empty:
        historial = historial.reset_index().rename(columns={"index": "fecha_dato"})
        for col in ("payout_affo", "spread_inversion", "deuda_neta_ebitdare"):
            if col not in historial and panel.metricas.get(col) is not None:
                historial[col] = panel.metricas[col]
    return mod_senal.evaluar_semaforo(
        panel.ticker,
        panel.asof,
        panel.metricas,
        panel.percentil_actual,
        panel.n_observaciones,
        historial,
    )


# --------------------------------------------------------------------------------------
# Comparativa sectorial
# --------------------------------------------------------------------------------------


def tabla_universo(
    repo: Repositorio,
    *,
    asof: dt.date,
    tickers: list[str] | None = None,
    cap_rate_mercado: float = 0.065,
) -> pd.DataFrame:
    """Una fila por emisor con su percentil de prima y el resultado de las tres puertas."""
    emisores = repo.emisores()
    if emisores.empty:
        return pd.DataFrame()
    if tickers:
        emisores = emisores[emisores["ticker"].isin(tickers)]

    filas = []
    for _, e in emisores.iterrows():
        panel = construir_panel(repo, e["ticker"], asof=asof, cap_rate_mercado=cap_rate_mercado)
        sem = evaluar(panel)
        filas.append(
            {
                "ticker": e["ticker"],
                "nombre": e["nombre"],
                "sector": e["sector"],
                "precio": panel.precio,
                # Qué medida de flujo está detrás del yield de ESTE renglón. Sin
                # esta columna, un Core FFO y un AFFO se leerían como lo mismo.
                "medida": panel.medida_flujo,
                "affo_yield": panel.metricas.get("affo_yield"),
                "prima_bps": (panel.prima.dropna().iloc[-1] * 10_000) if not panel.prima.dropna().empty else None,
                "percentil_prima": panel.percentil_actual,
                "n_observaciones": panel.n_observaciones,
                "payout_affo": panel.metricas.get("payout_affo"),
                "p_affo": panel.metricas.get("p_affo"),
                "dividend_yield": panel.metricas.get("dividend_yield"),
                "pasa_calidad": sem.calidad.pasa,
                "luz_calidad": sem.calidad.luz.value,
                "luz_valuacion": sem.valuacion.luz.value,
                "luz_deterioro": sem.deterioro.luz.value,
                "accion": sem.accion.value,
                "solo_demo": panel.solo_demo,
            }
        )
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# Contexto macro
# --------------------------------------------------------------------------------------


@dataclass
class ContextoMacro:
    ust10: float | None
    udibono10: float | None
    inpc: pd.Series
    cpi: pd.Series
    inflacion_mx: float | None
    inflacion_us: float | None
    asof: dt.date


def contexto_macro(repo: Repositorio, *, asof: dt.date) -> ContextoMacro:
    inpc = repo.tasa(SERIE_INPC, asof=asof)
    cpi = repo.tasa(SERIE_CPI, asof=asof)
    return ContextoMacro(
        ust10=repo.valor_tasa(SERIE_UST10, asof=asof),
        udibono10=repo.valor_tasa(SERIE_UDIBONO10, asof=asof),
        inpc=inpc,
        cpi=cpi,
        inflacion_mx=_inflacion_anual(inpc),
        inflacion_us=_inflacion_anual(cpi),
        asof=asof,
    )


def _inflacion_anual(indice: pd.Series) -> float | None:
    s = pd.Series(indice).dropna()
    if len(s) < 13:
        return None
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    previo = s[s.index <= s.index[-1] - pd.DateOffset(years=1)]
    if previo.empty or previo.iloc[-1] <= 0:
        return None
    return float(s.iloc[-1] / previo.iloc[-1] - 1.0)
