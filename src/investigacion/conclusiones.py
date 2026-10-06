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
        Conclusion(
            "Qué hacer",
            "Aportar siempre, completo, sin guardar efectivo esperando el momento. La valuación sirve para escoger "
            "a cuál REIT de calidad va el dinero del mes (estudio de métodos de valuación), no para decidir si "
            "entrar. Si una caída grande es intolerable, la manera de reducirla es tener menos en REITs desde el "
            "principio, no intentar salir a tiempo.",
            "favorable"),
        Conclusion(
            "Qué tanto se le puede creer",
            "Cada hipótesis, señal y criterio se guardó en un commit antes de correrla; los datos se partieron antes "
            "de verlos (desarrollo hasta 2015, validación desde 2016) y los ocho mercados de la prueba final se "
            f"sellaron sin mirarlos. La bitácora registra {intentos} configuraciones probadas. Límites: de 1972 a 2015 "
            f"hubo solo {len(f3['caidas'])} caídas de 20% o más; las canastas de Singapur, Hong Kong y las FIBRAs son "
            "de los REITs que cotizan hoy; el índice de condiciones financieras se revisa después de publicarse.",
            "neutral"),
    ]


def fases(res: dict) -> pd.DataFrame:
    """La tabla de qué se hizo en cada fase y qué salió."""
    f5, f7, f8 = res["fase5"], res["fase7"], res["fase8"]
    return pd.DataFrame([
        ("0", "Reglas del juego", "Objetivo, muestras, criterios, candado y bitácora, antes de tocar datos", "Fijado"),
        ("1", "Literatura", "99 fuentes: la valuación predice hacia atrás y falla hacia adelante; la tendencia reduce caídas",
         "Hecho"),
        ("2", "Datos", "Nareit desde 1972, FRED, French, Shiller y ocho mercados sellados", "Falta la SEC"),
        ("3", "Exploración 1972-2015", "Cuatro caídas grandes; el techo del timing", "Hecho"),
        ("4", "Pre-registro", "11 señales, 22 reglas, el filtro", "Fijado"),
        ("5", "Señales de entrada", f"{f5['resumen']['pasan']} de {f5['resumen']['intentos']} reglas pasan el filtro",
         "RECHAZADO"),
        ("7", "Escalera de modelos", f"Candidato: {f7['resumen']['candidato'] or 'ninguno'}", "RECHAZADO"),
        ("8", "Prueba final", "Protección por tendencia en EE. UU. 2016+ y ocho mercados", f8["resumen"]["veredicto"]),
        ("6", "En cuáles REITs", "Requiere los estados financieros del universo", "Pendiente"),
    ], columns=["fase", "que", "detalle", "resultado"])
