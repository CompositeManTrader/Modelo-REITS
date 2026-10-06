"""Las conclusiones de la investigación, escritas a partir de los resultados guardados.

La página y el PDF usan este mismo texto, así que no pueden decir cifras distintas.
"""

from __future__ import annotations

import pandas as pd

from src.estudio.reglas import Conclusion
from src.investigacion import bitacora


def _pb(v: float) -> str:
    x = round(v * 1e4)
    return f"{x:+,d} pb" if x else "0 pb"


def _costo(v: float) -> str:
    """Una mejora negativa dicha como costo: −0.0127 → «127 pb»."""
    return f"{abs(round(v * 1e4)):,d} pb"


def _p(v: float, d: int = 0) -> str:
    return f"{v * 100:.{d}f}%"


def conclusiones(res: dict) -> list[Conclusion]:
    f3, f5, f7, f8 = res["fase3"], res["fase5"], res["fase7"], res["fase8"]
    techo = f3["techo"]
    nunca = techo[(techo["modo"] == "nunca vende") & (techo["regla"] != "aportar siempre")]
    caidas = techo[techo["regla"].str.startswith("fuera en cada caída")].set_index("modo")
    base = techo[techo["regla"] == "aportar siempre"].iloc[0]
    fr = f3["frecuencia"].set_index("horizonte_meses")
    d5 = f5["desarrollo"]
    ev7 = f7["evaluacion"].set_index("senal")
    v, c = f8["resumen"]["validacion"], f8["resumen"]["conjunto"]
    mercados = f8["mercados"]
    from src.investigacion.graficas import NOMBRES_MERCADO

    protege = [NOMBRES_MERCADO.get(m, m) for m in mercados[mercados["protege"]]["mercado"]]
    intentos = bitacora.intentos()
    comp = ev7.loc["compuesto"]
    return [
        Conclusion(
            "No hay una señal que diga cuándo entrar",
            f"Ninguna de las {len(d5)} reglas de señales simples —valuación, crédito, condiciones financieras, la "
            f"bolsa y tendencia— ni de los {len(ev7)} modelos de la escalera —hasta árboles y regímenes de Markov— le "
            "ganó a aportar siempre de forma robusta, con impuestos del SIC y comisiones. La mejor regla de valuación "
            f"quedó en {_pb(d5[d5['familia'] == 'valuacion']['mejora_rebalanceo'].max())} al año y la peor en "
            f"{_pb(d5[d5['familia'] == 'valuacion']['mejora_rebalanceo'].min())}.",
            "desfavorable"),
        Conclusion(
            "Esperar no paga",
            f"De 1972 a 2015 el efectivo le ganó a los REITs en {_p(fr.loc[12, 'fraccion_efectivo_gana'])} de los "
            f"periodos de 12 meses y en {_p(fr.loc[60, 'fraccion_efectivo_gana'])} de los de 5 años. El modelo que "
            f"mejor distingue años buenos de malos (el compuesto: R² fuera de muestra de {comp['r2_12m'] * 100:+.1f}%) "
            "nunca pronosticó que el efectivo fuera a ganar: predice cuánto le ganan los REITs al efectivo, no si "
            "pierden contra él.",
            "neutral"),
        Conclusion(
            "Decidiendo solo el dinero nuevo, el timing casi no puede valer nada",
            "Aportando 1,000 dólares al mes, ni un oráculo que conoce el futuro agrega más de "
            f"{_pb(nunca['contra_aportar_siempre_bps'].max() / 1e4)} al año si solo decide a dónde va la aportación: la "
            "riqueza ya invertida pesa mucho más que el dinero de un mes. El valor posible está en vender antes de "
            f"una caída y volver a entrar: saber cuándo viene cada caída valdría "
            f"{_pb(caidas.loc['rebalancea', 'contra_aportar_siempre_bps'] / 1e4)} al año y bajaría la peor caída de "
            f"{_p(base['caida_maxima'])} a {_p(caidas.loc['rebalancea', 'caida_maxima'])}.",
            "neutral"),
        Conclusion(
            "La protección contra caídas existe, pero se paga",
            "Estar fuera cuando el precio está abajo de su promedio de 10 meses redujo la caída máxima "
            f"{_p(c['reduccion_de_caida'])} en promedio en los {c['mercados']} mercados de la prueba final, pero costó "
            f"{_costo(c['mejora'])} al año, y en EE. UU. desde 2016, {_costo(v['mejora'])}: sale después de la caída, vuelve "
            "después del rebote y cada salida paga impuesto sobre la ganancia. Solo "
            f"{', '.join(protege) if protege else 'ningún mercado'} cumplió el criterio (30% menos de caída con costo "
            "de a lo más 25 pb). En 1972-2015, donde se escogió, sí parecía gratis.",
            "desfavorable"),
        *_seleccion(res),
        Conclusion(
            "Qué hacer",
            "Aportar siempre, completo, sin guardar efectivo esperando el momento, y repartido entre muchos REITs de "
            "capital (o un fondo amplio): ninguna regla para escoger a cuáles le ganó a repartir entre todos. No "
            "perseguir el yield alto ni lo «barato»: concentran los recortes. No vender después de un recorte: los "
            "que recortan rindieron más que el resto el año siguiente. Si una caída grande es intolerable, la "
            "manera de reducirla es tener menos en REITs desde el principio, no intentar salir a tiempo.",
            "favorable"),
        Conclusion(
            "Qué tanto se le puede creer",
            "Cada hipótesis, señal y criterio se guardó en un commit antes de correrla; los datos se partieron antes "
            "de verlos (desarrollo hasta 2015, validación desde 2016) y los ocho mercados de la prueba final se "
            f"sellaron sin mirarlos. La bitácora registra {intentos} configuraciones probadas. Límites: de 1972 a 2015 "
            f"hubo solo {len(f3['caidas'])} caídas de 20% o más; las canastas de Singapur, Hong Kong y las FIBRAs son "
            "de los REITs que cotizan hoy; el índice de condiciones financieras se revisa después de publicarse. En la "
            "selección (fase 6), el desarrollo empieza en 2011 porque antes casi no hay estados financieros en XBRL, "
            "las escisiones no se ven en los 13F, y la primera corrida tuvo dos errores de programación que se "
            "corrigieron y se declaran sin que cambiara el veredicto.",
            "neutral"),
    ]


def _seleccion(res: dict) -> list[Conclusion]:
    """La fase 6, si ya corrió: en cuáles REITs."""
    if "fase6" not in res:
        return []
    f6 = res["fase6"]
    d = f6["desarrollo"].set_index("regla")
    v = f6["validacion"].set_index("regla")
    fin = f6["final"].iloc[0] if "final" in f6 and len(f6["final"]) else None
    det = f6["resumen"]["detector"]
    d3 = f6["resumen"]["despues_del_recorte"].get("validacion", {})
    sin = v.loc["sin riesgo de recorte"]
    texto_final = (f"y en la prueba final, con el tercio de emisores que se selló sin mirarlo, ganó {_pb(fin['mejora'])} "
                   "al año: debajo de los +50 pb que pide el criterio." if fin is not None else "")
    return [
        Conclusion(
            "Tampoco hay una regla para escoger en cuáles",
            f"Con todos los REITs de capital de EE. UU. desde 2011, incluidos los que quebraron o fueron comprados, "
            f"ninguna de las {len(d)} reglas de selección —valor, calidad, deuda, momentum, tamaño, dividendo— le ganó "
            "de forma robusta a repartir la aportación entre todos. La única que llegó a la prueba final fue momentum "
            f"(comprar a los que más subieron): {_pb(d.loc['momentum', 'mejora'])} en desarrollo, "
            f"{_pb(v.loc['momentum', 'mejora'])} en validación, " + texto_final,
            "desfavorable"),
        Conclusion(
            "Lo barato es trampa, aun entre los de calidad",
            f"El yield de dividendo alto tuvo {_p(d.loc['rendimiento_del_dividendo', 'recortes'])} de recortes en el "
            f"año siguiente contra {_p(d.loc['rendimiento_del_dividendo', 'recortes_todos'])} del universo y perdió "
            f"{_costo(d.loc['rendimiento_del_dividendo', 'mejora'])} al año. «Barato entre los de calidad», la prueba "
            f"clave, fue la peor de las reglas ({_pb(d.loc['calidad y barato', 'mejora'])} al año). Los recortes sí se "
            f"pueden ver venir (el detector acertó con un AUC de {det['auc']:.2f}), pero sacar a los de más riesgo costó "
            f"{_costo(sin['mejora'])} al año, porque los que recortan después rebotan: en los 12 meses siguientes "
            f"rindieron {_p(d3.get('exceso_12m_promedio', float('nan')))} más que el resto.",
            "neutral"),
    ]


def _fila_fase6(res: dict) -> tuple[str, str, str, str]:
    if "fase6" not in res:
        return ("6", "En cuáles REITs", "Requiere los estados financieros del universo", "Pendiente")
    r = res["fase6"]["resumen"]
    return ("6", "En cuáles REITs", f"16 reglas de selección y un detector de recortes; a validación "
            f"{len(r['candidatas'])}, a la prueba final momentum", r["veredicto"])


def fases(res: dict) -> pd.DataFrame:
    """La tabla de qué se hizo en cada fase y qué salió."""
    f5, f7, f8 = res["fase5"], res["fase7"], res["fase8"]
    return pd.DataFrame([
        ("0", "Reglas del juego", "Objetivo, muestras, criterios, candado y bitácora, antes de tocar datos", "Fijado"),
        ("1", "Literatura", "99 fuentes: la valuación predice hacia atrás y falla hacia adelante; la tendencia reduce caídas",
         "Hecho"),
        ("2", "Datos", "Nareit desde 1972, FRED, French, Shiller, ocho mercados sellados y la SEC (13F y XBRL de "
         "todos los REITs desde 2009, vivos y muertos)", "Hecho"),
        ("3", "Exploración 1972-2015", "Cuatro caídas grandes; el techo del timing", "Hecho"),
        ("4", "Pre-registro", "11 señales, 22 reglas, el filtro", "Fijado"),
        ("5", "Señales de entrada", f"{f5['resumen']['pasan']} de {f5['resumen']['intentos']} reglas pasan el filtro",
         "RECHAZADO"),
        ("7", "Escalera de modelos", f"Candidato: {f7['resumen']['candidato'] or 'ninguno'}", "RECHAZADO"),
        ("8", "Prueba final", "Protección por tendencia en EE. UU. 2016+ y ocho mercados", f8["resumen"]["veredicto"]),
        _fila_fase6(res),
    ], columns=["fase", "que", "detalle", "resultado"])
