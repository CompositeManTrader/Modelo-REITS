"""Arma el estudio completo de un emisor en un solo objeto.

La página y el PDF consumen ESTE objeto y nada más: si cada uno armara sus
propias cifras, tarde o temprano dirían números distintos del mismo emisor, y un
estudio que se contradice entre pantalla e impreso no se puede creer.

Las conclusiones se escriben a partir de las cifras al correr, no a mano: el texto
que dice «está caro contra el bono» sale de comparar el percentil del día, así
que cambia solo cuando cambia el dato.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import SERIE_CETES28, SERIE_UDIBONO10, SERIE_USDMXN, SERIE_UST10
from src.datos.repositorio import Repositorio
from src.estudio import fundamentales as fund
from src.estudio import historia as hist
from src.estudio import mercado, retornos
from src.fiscal.mexico import impuesto_dividendo
from src.servicio import contexto_macro


@dataclass
class Conclusion:
    titulo: str
    texto: str
    tono: str = "neutral"   # "favorable" | "desfavorable" | "neutral"


@dataclass
class Estudio:
    ticker: str
    asof: dt.date
    historia_mercado: mercado.HistoriaMercado
    narrativa: hist.HistoriaEmisor | None
    anual: pd.DataFrame
    primarios: pd.DataFrame
    diagnostico_ffo: fund.DiagnosticoFFO
    serie: retornos.SerieDiaria
    eras: list[retornos.Descomposicion]
    total: retornos.Descomposicion
    entradas: retornos.AnalisisEntradas
    hoy: retornos.RetornoHoy
    spread_inversion: pd.DataFrame
    # Contra qué flujo por acción se mide la valuación: la columna ``p_ffo`` de la
    # serie es el precio entre ESTE flujo (FFO de Nareit salvo que el emisor tenga otro
    # catalogado, ver ``fundamentales.MEDIDAS_DE_VALUACION``).
    medida: fund.MedidaDeValuacion = fund.FFO
    # FFO y AFFO por acción conocidos en cada fecha (``fundamentales.flujo_conocido``),
    # con el periodo que cubre cada cifra en ``attrs["periodo"]``.
    flujos: dict[str, pd.Series] = field(default_factory=dict)
    conclusiones: list[Conclusion] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def tabla(self) -> pd.DataFrame:
        return self.serie.tabla


def _spread_de_inversion(anual: pd.DataFrame, tabla: pd.DataFrame) -> pd.DataFrame:
    """A qué yield compró el emisor cada año contra lo que le costaba su capital ese año.

    El costo del capital accionario es el AFFO yield promedio del año (el FFO yield
    en los años en que el emisor todavía no publicaba AFFO): es lo que le «rinde» al
    comprador de la acción, y por lo tanto lo que el emisor tiene que ganar sobre
    cada dólar que levanta emitiendo. Si compra por debajo de eso con dinero de
    acciones, cada adquisición diluye.
    """
    if "cap_rate_adquisicion" not in anual:
        return pd.DataFrame()
    anios = anual.index[anual["cap_rate_adquisicion"].notna()]
    filas = []
    for a in anios:
        ventana = tabla[tabla.index.year == a]
        if ventana.empty:
            continue
        ay = ventana["affo_yield"].mean()
        fy = (1 / ventana["p_ffo"]).mean()
        costo_acciones = ay if pd.notna(ay) else fy
        filas.append({
            "anio": int(a),
            "cap_rate": float(anual.loc[a, "cap_rate_adquisicion"]),
            "costo_acciones": float(costo_acciones) if pd.notna(costo_acciones) else np.nan,
            "medida": "AFFO yield" if pd.notna(ay) else "FFO yield",
            "costo_deuda": float(anual.loc[a, "costo_deuda"]) if "costo_deuda" in anual and pd.notna(anual.loc[a, "costo_deuda"]) else np.nan,
            "ust10": float(ventana["ust10"].mean()),
            "inversion": float(anual.loc[a, "inversion_en_adquisiciones"]) if "inversion_en_adquisiciones" in anual else np.nan,
        })
    t = pd.DataFrame(filas).set_index("anio") if filas else pd.DataFrame()
    if not t.empty:
        t["spread_contra_acciones"] = t["cap_rate"] - t["costo_acciones"]
        # El costo PONDERADO: nadie compra solo con acciones. Los pesos son el valor de
        # mercado de las acciones contra la deuda al cierre del año; el costo de la
        # deuda es el promedio de la existente —intereses ÷ deuda promedio—, que va
        # detrás del marginal cuando las tasas suben. Por eso el spread contra el
        # costo ponderado se lee junto al spread contra las acciones, no en su lugar.
        acciones = anual.get("acciones_en_circulacion")
        deuda = anual.get("deuda_total")
        cierre = tabla["precio_base"].groupby(tabla.index.year).last()
        if acciones is not None and deuda is not None:
            capitalizacion = (acciones * cierre.reindex(anual.index)).reindex(t.index)
            d = deuda.reindex(t.index)
            peso_deuda = d / (d + capitalizacion)
            t["peso_deuda"] = peso_deuda
            t["costo_ponderado"] = (1 - peso_deuda) * t["costo_acciones"] + peso_deuda * t["costo_deuda"]
            t["spread_contra_ponderado"] = t["cap_rate"] - t["costo_ponderado"]
    return t


# Por debajo de esto, lo que el mercado puso o quitó en todo el periodo se lee como
# «casi se canceló»: menos de un cuarto de un retorno típico de REIT.
REVALUACION_MENOR = 0.025


def desde_cuando(e: Estudio) -> str:
    """«Desde que cotiza», o desde cuándo empieza la historia verificable si se cortó."""
    inicio = e.historia_mercado.inicio_verificable
    if inicio:
        return f"Desde {e.total.inicio.year}"
    return "Desde que cotiza"


def _pct(x: float, decimales: int = 1) -> str:
    """Porcentaje sin «-0.0%»: un crecimiento de -0.04% se lee «0.0%», no «menos cero»."""
    return f"{0.0 if round(x * 100, decimales) == 0 else x:.{decimales}%}"


def _escisiones_en(e: Estudio, nombre: str) -> list[int]:
    """Años de las escisiones que caen dentro del horizonte de un escenario («…, 10 años»)."""
    horizonte = re.search(r"(\d+) años", nombre)
    if not horizonte:
        return []
    desde = pd.Timestamp(e.asof) - pd.DateOffset(years=int(horizonte.group(1)))
    return sorted({ev.fecha.year for ev in e.historia_mercado.escisiones if pd.Timestamp(ev.fecha) > desde})


def _describir_crecimiento(nombre: str) -> str:
    """«AFFO por acción, 10 años» → «el AFFO por acción en los últimos 10 años»."""
    medida, _, horizonte = nombre.partition(", ")
    return f"el {medida} en los últimos {horizonte}" if horizonte else nombre


def _conclusiones(e: Estudio) -> list[Conclusion]:
    h, total, ent = e.hoy, e.total, e.entradas
    tk = e.ticker
    m = e.medida.etiqueta
    c: list[Conclusion] = []

    if abs(total.revaluacion) < REVALUACION_MENOR:
        mercado_txt = (f"el humor del mercado dominó cada época por separado, pero en "
                       f"{total.anios:.0f} años casi se canceló.")
    elif total.revaluacion > 0:
        mercado_txt = ("además, el mercado terminó pagando bastante más por cada dólar de "
                       "dividendo que al principio.")
    else:
        mercado_txt = ("el mercado terminó pagando bastante menos por cada dólar de dividendo "
                       "que al principio, y eso restó.")
    c.append(Conclusion(
        "Qué ha rendido",
        f"{desde_cuando(e)}, {tk} rindió {total.retorno_total:.1%} al año en dólares con los "
        f"dividendos reinvertidos. De eso, {total.ingreso:.1%} fue el dividendo cobrado, "
        f"{total.crecimiento_dividendo:.1%} el crecimiento del dividendo por acción y "
        f"{total.revaluacion:+.1%} el cambio de valuación. El negocio produjo "
        f"{(total.ingreso + total.crecimiento_dividendo) / total.retorno_total:.0%} del retorno; "
        + mercado_txt,
        "favorable" if total.retorno_total > 0.08 else "neutral",
    ))

    pffo_med = float(e.tabla["p_ffo"].median())
    primer_spread = e.tabla["spread"].first_valid_index()
    if h.p_ffo is not None and h.percentil_spread is not None:
        barato_multiplo = h.p_ffo < pffo_med
        caro_bono = h.percentil_spread < 0.30
        if barato_multiplo and caro_bono:
            texto = (
                f"Las dos lentes discrepan. Por múltiplo está BARATO contra su propia historia: "
                f"{h.p_ffo:.1f} veces {m} contra una mediana de {pffo_med:.1f}. Contra el bono "
                f"está CARO: su yield le saca {h.spread:.2%} al Treasury, más que solo el "
                f"{h.percentil_spread:.0%} de los días desde {primer_spread.year}. No se "
                "contradicen: las tasas están altas, y lo que paga el Treasury le quita "
                "atractivo a cualquier yield."
            )
            tono = "neutral"
        elif barato_multiplo:
            texto = (f"Barato por las dos lentes: {h.p_ffo:.1f} veces {m} contra una mediana de "
                     f"{pffo_med:.1f}, y un spread contra el Treasury en el percentil "
                     f"{h.percentil_spread:.0%} de su historia.")
            tono = "favorable"
        elif caro_bono:
            texto = (f"Caro por las dos lentes: {h.p_ffo:.1f} veces {m} contra una mediana "
                     f"histórica de {pffo_med:.1f}, y un spread contra el Treasury en el "
                     f"percentil {h.percentil_spread:.0%} desde {primer_spread.year}.")
            tono = "desfavorable"
        else:
            texto = (f"Las dos lentes discrepan, al revés de lo usual. Por múltiplo está CARO: "
                     f"{h.p_ffo:.1f} veces {m} contra una mediana de {pffo_med:.1f}. Contra el "
                     f"bono no: su spread está en el percentil {h.percentil_spread:.0%} desde "
                     f"{primer_spread.year}.")
            tono = "neutral"
        c.append(Conclusion("Qué tan caro está hoy", texto, tono))

    corr = ent.correlaciones.get(f"5 años (P/{m})")
    q = ent.quintiles
    if corr is not None and not q.empty:
        barato, caro = q.loc["5 · más barato"], q.loc["1 · más caro"]
        c.append(Conclusion(
            "Cuándo convenía entrar",
            f"El múltiplo al entrar explica buena parte del retorno a cinco años (correlación de "
            f"rangos {corr:.2f}). Quien compró en el quinto más barato de la historia —P/{m} de "
            f"{barato['desde']:.1f} a {barato['hasta']:.1f}— obtuvo una mediana de "
            f"{barato['rt_5a_mediana']:.1%} al año; quien compró en el más caro —de "
            f"{caro['desde']:.1f} a {caro['hasta']:.1f}—, {caro['rt_5a_mediana']:.1%}. "
            + ent.veredicto_p7,
            "neutral",
        ))

    base = next((s for s in h.escenarios if s.nombre.startswith("AFFO por acción, 10")), None) \
        or (h.escenarios[0] if h.escenarios else None)
    if base is not None:
        udi = h.udibono_real
        comparacion = ""
        tono = "neutral"
        if udi is not None:
            brecha = base.real_neto - udi
            tono = "favorable" if brecha > 0.01 else ("desfavorable" if brecha < 0 else "neutral")
            comparacion = (
                f" Contra el Udibono a 10 años ({udi:.2%} real garantizado) la prima es de "
                f"{abs(brecha) * 1e4:,.0f} puntos base"
                + (f" a favor de {tk}." if brecha > 0 else " EN CONTRA: el activo sin riesgo paga más.")
            )
        rango = ""
        if udi is not None:
            rango = (
                f" El resultado depende de hacia dónde se mueva la valuación: si el spread contra "
                f"el bono vuelve a su mediana, el real neto baja a "
                f"{base.real_neto_reversion_spread:.1%}"
                + (" —por debajo del Udibono—" if base.real_neto_reversion_spread < udi else "")
                + f"; si el P/{m} vuelve a la suya, sube a {base.real_neto_reversion_multiplo:.1%}. "
                "Lo que decide cuál de las dos pasa es, sobre todo, la tasa del Treasury."
            )
            tono = "neutral"
        escindido = ""
        if anios_esc := _escisiones_en(e, base.nombre):
            escindido = (
                f" Ese crecimiento incluye la escisión de {' y '.join(map(str, anios_esc))}: el flujo "
                "que se fue con ella lo siguió recibiendo el accionista, pero en acciones de otra "
                "empresa, que esta cifra no cuenta."
            )
        c.append(Conclusion(
            "Si paga buen retorno hoy",
            f"Al precio de hoy, {tk} paga {h.yield_actual:.2%} de dividendo. Si el flujo por acción "
            f"sigue creciendo como {_describir_crecimiento(base.nombre)} ({_pct(base.crecimiento)}), "
            f"el retorno esperado ronda {base.retorno_usd:.1%} en dólares a múltiplo constante, y "
            f"{base.real_neto:.1%} real después de impuestos para un residente mexicano."
            + escindido + comparacion + rango,
            tono,
        ))

    si = e.spread_inversion
    if not si.empty and si["spread_contra_acciones"].notna().any():
        ultimo = si["spread_contra_acciones"].dropna()
        a = int(ultimo.index[-1])
        # El mejor año se busca solo entre los que miden el costo igual que hoy: antes de
        # que el emisor publicara AFFO, el costo es el FFO yield, y comparar un margen
        # contra AFFO con uno contra FFO no es comparar lo mismo.
        mismos = si.loc[ultimo.index, "medida"] == si.loc[a, "medida"]
        mejores = ultimo[mismos]
        ponderado = ""
        if "spread_contra_ponderado" in si and pd.notna(si.loc[a].get("spread_contra_ponderado")):
            margen = si.loc[a, "spread_contra_ponderado"]
            peso_hoy = si.loc[a, "peso_deuda"]
            antes = si["peso_deuda"].dropna()
            antes = antes[antes.index <= a - 10]
            if margen <= 0:
                cierre = "negativo: ni combinando acciones y deuda cubre lo que le cuesta su capital."
            elif antes.empty:
                cierre = "positivo."
            elif peso_hoy > antes.iloc[-1] + 0.02:
                cierre = (f"positivo, pero apoyado en la deuda, que hoy pesa más en su capital que "
                          f"en {int(antes.index[-1])} ({antes.iloc[-1]:.0%} → {peso_hoy:.0%}).")
            else:
                cierre = "positivo, sin apoyarse en la deuda más que hace diez años."
            ponderado = (f" Contra su costo ponderado —acciones y deuda juntas— el margen es de "
                         f"{margen * 1e4:+,.0f} puntos base: " + cierre)
        if ultimo.iloc[-1] < 0.005:
            remate = (" Emitir acciones para comprar ya casi no suma por acción: el crecimiento "
                      "depende más de la deuda, del flujo que retiene y de vender inmuebles.")
        else:
            remate = " Emitir acciones para comprar todavía suma por acción."
        if len(mejores) < 2:
            contra_mejor = "."
        elif int(mejores.idxmax()) == a:
            contra_mejor = f", el mayor de los {len(mejores)} años con dato."
        else:
            contra_mejor = f", contra {mejores.max() * 1e4:+,.0f} en su mejor año ({int(mejores.idxmax())})."
        c.append(Conclusion(
            "El motor de crecimiento",
            f"{tk} crece comprando inmuebles a un yield mayor que lo que le cuesta su capital. En "
            f"{a} compró a {si.loc[a, 'cap_rate']:.1%} mientras su propia acción rendía "
            f"{si.loc[a, 'costo_acciones']:.1%} de {si.loc[a, 'medida']}: un margen de "
            f"{ultimo.iloc[-1] * 1e4:+,.0f} puntos base sobre el capital accionario" + contra_mejor
            + ponderado + remate,
            "desfavorable" if ultimo.iloc[-1] < 0.005 else "neutral",
        ))
    return c


def armar(
    repo: Repositorio,
    ticker: str,
    *,
    asof: dt.date,
    ajustado_proveedor: pd.Series | None = None,
) -> Estudio:
    ticker = ticker.upper()
    historia_m = mercado.cargar(
        ticker, asof=asof,
        crudo_diario=repo.serie_precio(ticker, asof=asof),
        dividendos_diarios=repo.dividendos(ticker, asof=asof),
    )
    # Solo lo publicado al corte (P1). Con el estudio siempre armado a hoy no se notaba;
    # armado a 2015 —como lo hace la prueba de las reglas— veía cap rates de 2017.
    primarios = fund.publicado_al(fund.cargar_primarios(ticker, historia_m.eventos), asof)
    anual = fund.anual(repo, ticker, asof=asof, historia=historia_m, primarios=primarios)
    trimestrales = fund.publicado_al(fund.cargar_trimestrales(ticker, historia_m.eventos), asof)
    ffo = fund.flujo_conocido(repo, ticker, "ffo_por_accion", asof=asof, primarios=primarios,
                              trimestrales=trimestrales)
    affo = fund.flujo_conocido(repo, ticker, "affo_por_accion", asof=asof, primarios=primarios,
                               trimestrales=trimestrales)
    medida = fund.medida_de_valuacion(ticker)
    flujo = affo if medida.concepto == "affo_por_accion" else ffo

    tasa_div = impuesto_dividendo(1.0).tasa_efectiva
    serie = retornos.serie_diaria(
        historia_m,
        ust10=repo.tasa(SERIE_UST10, asof=asof),
        usdmxn=repo.tasa(SERIE_USDMXN, asof=asof),
        ffo_conocido=flujo, affo_conocido=affo,
        ajustado_proveedor=ajustado_proveedor,
        fraccion_neta=1 - tasa_div,
    )
    narrativa = hist.HISTORIAS.get(ticker)
    fin = serie.tabla.index[-1]
    eras = []
    if narrativa is not None:
        for era in narrativa.eras:
            if pd.Timestamp(era.inicio) < fin:
                eras.append(retornos.descomponer(
                    serie, historia_m, era.inicio, min(pd.Timestamp(era.fin or fin), fin), era.nombre))
    inicio = historia_m.inicio_verificable
    total = retornos.descomponer(
        serie, historia_m, serie.tabla.index[0], fin,
        f"Desde {serie.tabla.index[0].year}" if inicio else "Desde que cotiza",
    )
    entradas = retornos.analizar_entradas(serie, asof=asof, medida=medida.etiqueta)

    macro = contexto_macro(repo, asof=asof)
    hoy = retornos.retorno_hoy(
        serie, anual,
        inflacion_us=macro.inflacion_us,
        udibono_real=repo.valor_tasa(SERIE_UDIBONO10, asof=asof),
        cetes=repo.valor_tasa(SERIE_CETES28, asof=asof),
        tasa_impuesto_dividendo=tasa_div,
    )

    avisos = []
    if inicio:
        avisos.append(
            f"La historia empieza el {inicio['fecha']} y no en el listado "
            f"({historia_m.manifiesto.get('primera_cotizacion')}): antes de esa fecha el registro de "
            "dividendos del proveedor está incompleto y no hay reporte del emisor contra qué "
            "verificarlo. El detalle está en la metodología."
        )
    if flujo.attrs.get("fechas_estimadas"):
        anios = flujo.attrs.get("anios_estimados")
        rezago = flujo.attrs.get("rezago_dias")
        avisos.append(
            f"{flujo.attrs['fechas_estimadas']} cifras trimestrales"
            + (f" de {anios[0]} a {anios[1]}" if anios else "")
            + " se conocen por comparativas de comunicados posteriores; su fecha de publicación "
            "original se estimó como cierre del trimestre + 60 días"
            + (f" ({ticker} publica entre {rezago[0]} y {rezago[1]} días después)." if rezago else ".")
        )
    descartadas = pd.concat(
        [x for x in (ffo.attrs.get("descartadas"), affo.attrs.get("descartadas"),
                     anual.attrs.get("descartadas")) if x is not None and not x.empty]
        or [pd.DataFrame()]
    )
    if not descartadas.empty:
        ej = descartadas.sort_values("fecha_dato").iloc[0]
        avisos.append(
            f"Se descartaron {len(descartadas)} cifras de FFO/AFFO por acción que la base leyó de "
            "los 8-K porque contradicen lo que reportó el emisor; por ejemplo, "
            f"{ej['valor']:.2f} en el {'año' if ej['periodo_tipo'] == 'FY' else 'trimestre'} al "
            f"{pd.Timestamp(ej['fecha_dato']):%d-%m-%Y}, contra "
            + (f"{ej['esperado']:.2f} en el comunicado de ese trimestre. " if pd.notna(ej.get("exacto")) and bool(ej.get("exacto"))
               else f"cerca de {ej['esperado']:.2f}. ")
            + "El estudio usa la cifra del documento."
        )
    if historia_m.dias_empalmados:
        avisos.append(
            f"Los últimos {historia_m.dias_empalmados} días de precio vienen del proveedor diario, "
            "empalmados después de la historia larga versionada."
        )
    ultimo_precio = serie.tabla.index[-1].date()
    if (asof - ultimo_precio).days > 5:
        avisos.append(f"El último precio disponible es del {ultimo_precio}.")

    e = Estudio(
        ticker=ticker, asof=asof, historia_mercado=historia_m, narrativa=narrativa,
        anual=anual, primarios=primarios,
        diagnostico_ffo=fund.diagnostico_ffo(repo, ticker, asof=asof, tabla_anual=anual),
        serie=serie, eras=eras, total=total, entradas=entradas, hoy=hoy,
        spread_inversion=_spread_de_inversion(anual, serie.tabla), avisos=avisos, medida=medida,
        flujos={"ffo_por_accion": ffo, "affo_por_accion": affo},
    )
    e.conclusiones = _conclusiones(e)
    return e
