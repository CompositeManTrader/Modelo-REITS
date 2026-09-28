"""Las frases del estudio que dependen del emisor, armadas con sus datos.

La página y el PDF decían «lo anterior al split de 2005», «la escisión de Orion» o
«mensualidad × 12» escrito a mano. Con un segundo emisor esas frases se vuelven
falsas sin que nada truene: NNN no ha hecho splits y paga cada trimestre. Aquí
cada frase sale del catálogo de eventos, de la frecuencia medida o de la
narrativa del emisor, y una prueba verifica que ningún texto de un emisor
mencione a otro.
"""

from __future__ import annotations

from src.estudio.mercado import EventoDeCapital, HistoriaMercado, pagos_por_anio

FRECUENCIA = {
    12: ("mensual", "mensualidad vigente × 12"),
    4: ("trimestral", "dividendo trimestral vigente × 4"),
    2: ("semestral", "dividendo semestral vigente × 2"),
    1: ("anual", "dividendo anual vigente"),
}


def _nombre_de_escision(e: EventoDeCapital) -> str:
    """«Escisión de Orion Office REIT (ONL): …» → «escisión de Orion Office REIT»."""
    cabeza = e.descripcion.split(":")[0].split(" (")[0].strip()
    return cabeza[:1].lower() + cabeza[1:]


def dividendo_vigente(historia: HistoriaMercado) -> str:
    """Cómo se anualiza el dividendo de hoy: «mensualidad vigente × 12», etc."""
    return FRECUENCIA.get(pagos_por_anio(historia.dividendos), FRECUENCIA[4])[1]


def frecuencia(historia: HistoriaMercado) -> str:
    return FRECUENCIA.get(pagos_por_anio(historia.dividendos), FRECUENCIA[4])[0]


def base_por_accion(historia: HistoriaMercado) -> str:
    """Qué hay que saber para comparar una cifra por acción vieja con una de hoy."""
    if not historia.splits:
        return (f"{historia.ticker} no ha hecho splits en el periodo: las cifras por acción de "
                "cualquier año se comparan tal cual.")
    partes = [f"el split de {s.fecha.year} va dividido entre {s.factor:g}" for s in historia.splits]
    return "Todo en acciones de hoy: lo anterior a " + " y a ".join(partes) + "."


def eventos_del_proveedor(historia: HistoriaMercado) -> str:
    """Qué ajustes trae el cierre del proveedor, para la metodología."""
    if not historia.eventos:
        return (f"El proveedor no reporta splits ni escisiones de {historia.ticker} en el periodo, "
                "y el catálogo del emisor dice lo mismo: su cierre ya es el precio al que cotizó. "
                "Si algún día reporta un evento, la descarga se detiene hasta verificarlo.")
    partes = []
    for e in historia.eventos:
        if e.tipo == "split":
            partes.append(f"el split de {e.fecha.year} (×{e.factor:g})")
        else:
            partes.append(f"—como si fuera split— la {_nombre_de_escision(e)} de {e.fecha.year}")
    return ("El proveedor entrega el cierre ajustado por " + " y ".join(partes)
            + "; aquí se desajusta para obtener el precio al que de verdad cotizó (P2). Cada "
            "evento de capital está en un catálogo verificado: un evento que el proveedor reporte "
            "y no esté catalogado detiene la descarga.")


def escisiones_en_el_retorno(historia: HistoriaMercado) -> str:
    """La frase del pie del retorno total: qué distribuciones en especie incluye."""
    if not historia.escisiones:
        return ""
    nombres = [f"la {_nombre_de_escision(e)} ({e.fecha.year})" for e in historia.escisiones]
    return "Incluye " + " y ".join(nombres) + " como distribución en especie reinvertida. "


def desde(historia: HistoriaMercado, inicio) -> str:
    """«desde el listado en 1994» o «desde 1992, donde empieza la historia verificable»."""
    if historia.inicio_verificable:
        return f"desde {inicio:%Y}, donde empieza la historia verificable"
    return f"desde el listado en {inicio:%Y}"


def diagnostico_ffo(d) -> str:
    """Por qué el FFO no se deriva de la contabilidad, con los errores medidos."""
    if d.tabla.empty:
        return "No hay estados XBRL suficientes para derivar el FFO y compararlo."
    if d.primer_anio_confiable is None:
        return ("La fórmula de Nareit aplicada a XBRL no cuadra con lo reportado en ningún tramo "
                "reciente completo; el estudio usa solo cifras reportadas por el emisor.")
    antiguo = d.error_max_antiguo
    frase = (f"La fórmula de Nareit aplicada a XBRL cuadra con lo reportado desde "
             f"{d.primer_anio_confiable} (error máximo {d.error_max_reciente:.1%})")
    if antiguo is not None:
        frase += (f", y antes falla por hasta {antiguo:.0%}: en esos años las ventas de inmuebles "
                  "se clasificaban como operaciones discontinuadas y no pasan por las líneas que "
                  "la fórmula toca")
    return frase + ". El estudio usa solo cifras reportadas por el emisor."


def nota(narrativa, clave: str, defecto: str = "") -> str:
    """Una nota propia del emisor (``HistoriaEmisor.notas``), o nada."""
    if narrativa is None:
        return defecto
    return narrativa.notas.get(clave, defecto)
