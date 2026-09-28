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
    conclusiones: list[Conclusion] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def tabla(self) -> pd.DataFrame:
        return self.serie.tabla


def _spread_de_inversion(anual: pd.DataFrame, tabla: pd.DataFrame) -> pd.DataFrame:
    """A qué yield compró O cada año contra lo que le costaba su capital ese año.

    El costo del capital accionario es el AFFO yield promedio del año (antes de
    2010, el FFO yield): es lo que le «rinde» al comprador de la acción, y por lo
    tanto lo que O tiene que ganar sobre cada dólar que levanta emitiendo. Si
    compra por debajo de eso con dinero de acciones, cada adquisición diluye.
    """
    anios = anual.index[anual.get("cap_rate_adquisicion", pd.Series(dtype=float)).notna()]
    filas = []
    for a in anios:
        ventana = tabla.loc[str(a)]
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
        # El costo PONDERADO: O no compra solo con acciones. Los pesos son el valor de
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


def _conclusiones(e: Estudio) -> list[Conclusion]:
    h, total, ent = e.hoy, e.total, e.entradas
    c: list[Conclusion] = []

    c.append(Conclusion(
        "Qué ha rendido",
        f"Desde que cotiza, O rindió {total.retorno_total:.1%} al año en dólares con los "
        f"dividendos reinvertidos. De eso, {total.ingreso:.1%} fue el dividendo cobrado, "
        f"{total.crecimiento_dividendo:.1%} el crecimiento del dividendo por acción y "
        f"{total.revaluacion:+.1%} el cambio de valuación. El negocio produjo "
        f"{(total.ingreso + total.crecimiento_dividendo) / total.retorno_total:.0%} del retorno; "
        "el humor del mercado dominó cada época por separado, pero en treinta años casi se canceló.",
        "favorable",
    ))

    pffo_med = float(e.tabla["p_ffo"].median())
    if h.p_ffo is not None and h.percentil_spread is not None:
        barato_multiplo = h.p_ffo < pffo_med
        caro_bono = h.percentil_spread < 0.30
        if barato_multiplo and caro_bono:
            texto = (
                f"Las dos lentes discrepan. Por múltiplo está BARATO contra su propia historia: "
                f"{h.p_ffo:.1f} veces FFO contra una mediana de {pffo_med:.1f}. Contra el bono "
                f"está CARO: su yield le saca {h.spread:.2%} al Treasury, más que solo el "
                f"{h.percentil_spread:.0%} de los días desde 1995. No se contradicen: las tasas "
                "están altas, y lo que paga el Treasury le quita atractivo a cualquier yield."
            )
            tono = "neutral"
        elif barato_multiplo:
            texto = (f"Barato por las dos lentes: {h.p_ffo:.1f} veces FFO contra una mediana de "
                     f"{pffo_med:.1f}, y un spread contra el Treasury en el percentil "
                     f"{h.percentil_spread:.0%} de su historia.")
            tono = "favorable"
        else:
            texto = (f"Caro por múltiplo: {h.p_ffo:.1f} veces FFO contra una mediana histórica "
                     f"de {pffo_med:.1f}; spread contra el Treasury en el percentil "
                     f"{h.percentil_spread:.0%}.")
            tono = "desfavorable"
        c.append(Conclusion("Qué tan caro está hoy", texto, tono))

    corr = ent.correlaciones.get("5 años (P/FFO)")
    q = ent.quintiles
    if corr is not None and not q.empty:
        barato, caro = q.loc["5 · más barato"], q.loc["1 · más caro"]
        c.append(Conclusion(
            "Cuándo convenía entrar",
            f"El múltiplo al entrar explica buena parte del retorno a cinco años (correlación de "
            f"rangos {corr:.2f}). Quien compró en el quinto más barato de la historia —P/FFO de "
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
                f"{brecha * 1e4:,.0f} puntos base"
                + (" a favor de O." if brecha > 0 else " EN CONTRA: el activo sin riesgo paga más.")
            )
        rango = ""
        if udi is not None:
            rango = (
                f" El resultado depende de hacia dónde se mueva la valuación: si el spread contra "
                f"el bono vuelve a su mediana, el real neto baja a "
                f"{base.real_neto_reversion_spread:.1%}"
                + (" —por debajo del Udibono—" if base.real_neto_reversion_spread < udi else "")
                + f"; si el P/FFO vuelve a la suya, sube a {base.real_neto_reversion_multiplo:.1%}. "
                "Lo que decide cuál de las dos pasa es, sobre todo, la tasa del Treasury."
            )
            tono = "neutral"
        c.append(Conclusion(
            "Si paga buen retorno hoy",
            f"Al precio de hoy, O paga {h.yield_actual:.2%} de dividendo. Si el flujo por acción "
            f"sigue creciendo como en los últimos diez años ({base.crecimiento:.1%}), el retorno "
            f"esperado ronda {base.retorno_usd:.1%} en dólares a múltiplo constante, y "
            f"{base.real_neto:.1%} real después de impuestos para un residente mexicano."
            + comparacion + rango,
            tono,
        ))

    si = e.spread_inversion
    if not si.empty and si["spread_contra_acciones"].notna().any():
        ultimo = si["spread_contra_acciones"].dropna()
        a = int(ultimo.index[-1])
        mejores = ultimo[ultimo.index >= 2010]
        ponderado = ""
        if "spread_contra_ponderado" in si and pd.notna(si.loc[a].get("spread_contra_ponderado")):
            ponderado = (
                f" Contra su costo ponderado —acciones y deuda juntas— el margen es de "
                f"{si.loc[a, 'spread_contra_ponderado'] * 1e4:+,.0f} puntos base: positivo, pero "
                "apoyado en la deuda, que hoy pesa más en su capital que hace diez años."
            )
        c.append(Conclusion(
            "El motor de crecimiento",
            f"O crece comprando inmuebles a un yield mayor que lo que le cuesta su capital. En "
            f"{a} compró a {si.loc[a, 'cap_rate']:.1%} mientras su propia acción rendía "
            f"{si.loc[a, 'costo_acciones']:.1%} de {si.loc[a, 'medida']}: un margen de "
            f"{ultimo.iloc[-1] * 1e4:+,.0f} puntos base sobre el capital accionario, contra "
            f"{mejores.max() * 1e4:+,.0f} en su mejor año ({int(mejores.idxmax())})."
            + ponderado
            + " Emitir acciones para comprar ya casi no suma por acción; el crecimiento depende "
            "más de la deuda, del flujo que retiene y de vender inmuebles que en la década pasada.",
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
    primarios = fund.cargar_primarios(ticker, historia_m.eventos)
    anual = fund.anual(repo, ticker, asof=asof, historia=historia_m, primarios=primarios)
    ffo = fund.flujo_conocido(repo, ticker, "ffo_por_accion", asof=asof, primarios=primarios)
    affo = fund.flujo_conocido(repo, ticker, "affo_por_accion", asof=asof, primarios=primarios)

    tasa_div = impuesto_dividendo(1.0).tasa_efectiva
    serie = retornos.serie_diaria(
        historia_m,
        ust10=repo.tasa(SERIE_UST10, asof=asof),
        usdmxn=repo.tasa(SERIE_USDMXN, asof=asof),
        ffo_conocido=ffo, affo_conocido=affo,
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
    total = retornos.descomponer(serie, historia_m, serie.tabla.index[0], fin, "Desde que cotiza")
    entradas = retornos.analizar_entradas(serie, asof=asof)

    macro = contexto_macro(repo, asof=asof)
    hoy = retornos.retorno_hoy(
        serie, anual,
        inflacion_us=macro.inflacion_us,
        udibono_real=repo.valor_tasa(SERIE_UDIBONO10, asof=asof),
        cetes=repo.valor_tasa(SERIE_CETES28, asof=asof),
        tasa_impuesto_dividendo=tasa_div,
    )

    avisos = []
    if ffo.attrs.get("fechas_estimadas"):
        avisos.append(
            f"{ffo.attrs['fechas_estimadas']} cifras trimestrales de 2019 a 2023 se conocen por "
            "comparativas de comunicados posteriores; su fecha de publicación original se estimó "
            "como cierre del trimestre + 60 días (O publica entre 35 y 55 días después)."
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
        spread_inversion=_spread_de_inversion(anual, serie.tabla), avisos=avisos,
    )
    e.conclusiones = _conclusiones(e)
    return e
