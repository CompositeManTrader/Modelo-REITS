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
    partes = [f"lo anterior al split de {s.fecha.year} va dividido entre {s.factor:g}"
              for s in historia.splits]
    return "Todo en acciones de hoy: " + "; ".join(partes) + "."


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


def diagnostico_ffo(d, narrativa=None) -> str:
    """Por qué el FFO no se deriva de la contabilidad: los errores medidos y, si se
    conoce, la causa, que es de cada emisor (``notas["ffo_derivado"]``).

    La causa NO va aquí escrita: en O son las ventas clasificadas como operaciones
    discontinuadas; en NNN, dividendos preferentes que la base no resta. Una frase
    general habría atribuido a uno la causa del otro.
    """
    if d.tabla.empty:
        return "No hay estados XBRL suficientes para derivar el FFO y compararlo."
    causa = nota(narrativa, "ffo_derivado")
    if d.primer_anio_confiable is None:
        return ("La fórmula de Nareit aplicada a XBRL no cuadra con lo reportado en ningún tramo "
                "reciente completo. " + (causa + " " if causa else "")
                + "El estudio usa solo cifras reportadas por el emisor.")
    antiguo = d.error_max_antiguo
    frase = (f"La fórmula de Nareit aplicada a XBRL cuadra con lo reportado desde "
             f"{d.primer_anio_confiable} (error máximo {d.error_max_reciente:.1%})")
    if antiguo is not None:
        frase += f", y antes falla por hasta {antiguo:.0%}"
    return frase + ". " + (causa + " " if causa else "") + \
        "El estudio usa solo cifras reportadas por el emisor."


# Con más anclas que esto, la metodología las resume en vez de listarlas: 61 renglones
# de «+0.000%» ocupaban página y media y escondían la única que no cuadraba.
ANCLAS_A_LISTAR = 6
# Lo que se considera «exacto»: medio centavo en un precio de diez dólares.
ANCLA_EXACTA = 0.0005


def anclas(validacion: dict) -> tuple[str, list[dict]]:
    """Resumen de las anclas y las que vale la pena listar una por una."""
    todas = validacion.get("anclas", [])
    if len(todas) <= ANCLAS_A_LISTAR:
        return "", todas
    peor = max(todas, key=lambda a: abs(a["error"]))
    exactas = sum(abs(a["error"]) <= ANCLA_EXACTA for a in todas)
    resumen = (f"{len(todas)} cierres NYSE publicados por el emisor, de {todas[0]['fecha'][:4]} a "
               f"{todas[-1]['fecha'][:4]}: {exactas} coinciden al centavo; el error máximo es "
               f"{peor['error']:+.2%} ({peor['fecha']}).")
    return resumen, [a for a in todas if abs(a["error"]) > ANCLA_EXACTA]


def pesos_desde(e) -> str:
    """Si la serie en pesos arranca después que la de dólares, desde cuándo y por qué."""
    from src.estudio.graficas import mes

    mxn = e.tabla["rt_mxn"].dropna()
    if mxn.empty or (mxn.index[0] - e.tabla.index[0]).days < 31:
        return ""
    return (f"La línea en pesos empieza en {mes(mxn.index[0])}, el primer día con tipo de cambio "
            "en la base. ")


def nota(narrativa, clave: str, defecto: str = "") -> str:
    """Una nota propia del emisor (``HistoriaEmisor.notas``), o nada."""
    if narrativa is None:
        return defecto
    return narrativa.notas.get(clave, defecto)
