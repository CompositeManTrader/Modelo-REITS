"""Las conclusiones de la investigación, escritas a partir de los resultados guardados.

La página y el PDF usan este mismo texto, así que no pueden decir cifras distintas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.estudio.reglas import Conclusion
from src.investigacion import bitacora

FAMILIA_SENSIBILIDAD = "sensibilidad-fiscal"     # ``sensibilidad.FAMILIA``; no son intentos de búsqueda


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
    intentos = bitacora.intentos(excluir=(FAMILIA_SENSIBILIDAD,))
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
        *_broker(res),
        *_extremos(res),
        *_poder(res),
        Conclusion(
            "Qué hacer",
            "Aportar siempre, completo, sin guardar efectivo esperando el momento, y repartido entre muchos REITs de "
            "capital (o un fondo amplio): ninguna regla para escoger a cuáles le ganó a repartir entre todos. No "
            "perseguir el yield alto ni lo «barato»: concentran los recortes. No vender después de un recorte: los "
            "que recortan rindieron más que el resto el año siguiente. Si una caída grande es intolerable, la "
            "manera de reducirla es tener menos en REITs desde el principio, no intentar salir a tiempo."
            + _que_hacer_broker(res) + _que_hacer_extremos(res),
            "favorable"),
        Conclusion(
            "Qué tanto se le puede creer",
            "Cada hipótesis, señal y criterio se guardó en un commit antes de correrla; los datos se partieron antes "
            "de verlos (desarrollo hasta 2015, validación desde 2016) y los ocho mercados de la prueba final se "
            f"sellaron sin mirarlos. La bitácora registra {intentos} configuraciones probadas{_reevaluaciones(res)}. "
            "Límites: de 1972 a 2015 "
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


def _broker(res: dict) -> list[Conclusion]:
    """La sensibilidad fiscal, si ya corrió: las mismas reglas con un broker de EE. UU."""
    if "sensibilidad_broker" not in res:
        return []
    s = res["sensibilidad_broker"]
    b = s["bases"].iloc[0]
    perf = s["perfiles"].set_index("perfil")
    d5 = s["fase5_desarrollo"]
    pasan = d5[d5["perfil"] != "sic"].groupby("perfil")["pasa"].sum()
    w5 = d5.pivot_table(index=["senal", "regla"], columns="perfil", values="mejora_rebalanceo")
    mejor = w5["broker_35"].idxmax()
    partes = [f"{int(pasan.max())} de {len(w5)} reglas de entrada pasan el filtro (la mejor, "
              f"«{mejor[0]}», sube de {_pb(w5.loc[mejor, 'sic'])} a {_pb(w5.loc[mejor, 'broker_35'])} al año, pero no "
              "predice)"]
    cambia = bool(pasan.max() > 0)
    if "fase8_conjunto" in s:
        c = s["fase8_conjunto"].set_index("perfil")
        partes.append(f"la protección por tendencia cuesta {_costo(c.loc['broker_35', 'mejora'])} al año en los ocho "
                      f"mercados (contra {_costo(c.loc['sic', 'mejora'])} con el SIC)")
        cambia |= bool((c["veredicto"] != c.loc["sic", "veredicto"]).any())
    if "fase6_final" in s:
        f = s["fase6_final"].set_index("perfil")
        partes.append(f"momentum gana {_pb(f.loc['broker_35', 'mejora'])} en los emisores sellados (con el SIC, "
                      f"{_pb(f.loc['sic', 'mejora'])}), y el criterio pide +50 pb")
        cambia |= bool((f["veredicto"] != f.loc["sic", "veredicto"]).any())
    if "estudios_asignacion" in s:
        a = s["estudios_asignacion"].set_index(["perfil", "clave"])["ventaja"]
        partes.append(f"en O, NNN y WPC, mandar la aportación al más barato con el consenso de los métodos gana "
                      f"{_pb(a.loc[('broker_35', 'consenso')])} al año (con el SIC, {_pb(a.loc[('sic', 'consenso')])})")
    titulo = ("Con un broker de EE. UU., la conclusión no cambia" if not cambia
              else "Con un broker de EE. UU., algo cambia, pero solo después de verlo")
    return [Conclusion(
        titulo,
        "Comprando directo con un broker de EE. UU. y no por el SIC, el dividendo de un REIT paga la tasa marginal "
        f"más 9 puntos —{_p(perf.loc['broker_30', 'tasa_dividendo'])} con marginal de 30% y "
        f"{_p(perf.loc['broker_35', 'tasa_dividendo'])} con 35%, contra {_p(perf.loc['sic', 'tasa_dividendo'])} por "
        "el SIC—, los intereses del efectivo la marginal, la ganancia sigue en 10% y no hay comisión. Aportar "
        f"siempre rinde {_costo(b['broker_30'] - b['sic'])} a {_costo(b['broker_35'] - b['sic'])} menos al año "
        "(1972-2015). Con las mismas reglas, sin escoger nada nuevo: " + "; ".join(partes) + ". Las reglas que "
        "salen del mercado mejoran un poco, porque estar fuera evita un dividendo más gravado, pero ninguna llega "
        "al criterio. Las tasas deben confirmarse con un contador; el impuesto sucesorio de EE. UU. (arriba de 60 "
        "mil dólares) queda fuera del modelo.",
        "neutral")]


def _extremos(res: dict) -> list[Conclusion]:
    """La prueba exploratoria de los extremos de valuación, si ya corrió."""
    if "extremos" not in res:
        return []
    x = res["extremos"]
    e = x["emisores"]
    j = e[(e["senal"] == "consenso") & (e["anios"] == 5) & (e["alcance"] == "juntos")
          & (e["mitad"] == "completo")].set_index("corte")
    p = x["pistas"]
    pistas = p[p["pista"].astype(bool)]
    episodios = (pistas[["episodios_desarrollo", "episodios_validacion"]].sum(axis=1).max()
                 if len(pistas) and "episodios_desarrollo" in pistas else 0)
    reglas = p[p["nivel"] == "regla"]
    texto = (
        "Medido solo en los extremos, la valuación sí dice algo. En O, NNN y WPC, cuando el consenso estaba en su 10% "
        f"más barato, el papel rindió {_p(j.loc['barato 10%', 'mediana'], 1)} al año en los 5 años siguientes, contra "
        f"{_p(j.loc['caro 10%', 'mediana'], 1)} cuando estaba en su 10% más caro (neto con broker), aunque con menos de "
        "dos ventanas independientes en cada extremo. ")
    if len(pistas):
        texto += (f"En el sector, las pocas veces que los REITs quedaron en su 5% más barato contra los bonos —{int(episodios)} "
                  "crisis en 54 años— los 12 meses siguientes fueron muy buenos, antes y después de 2016. ")
    texto += (f"Pero salir solo en el 5% o 10% más caro no le ganó a aportar siempre por +50 pb en las dos muestras con "
              f"ninguna de las {len(reglas) // 2 if len(reglas) else 0} combinaciones: lo caro rinde menos, no pierde. "
              "Es una prueba exploratoria, decidida después de ver todo lo demás: nada se adopta como regla.")
    return [Conclusion("En los extremos la valuación sí dice algo, pero no cuándo salir", texto, "neutral")]


def _poder(res: dict) -> list[Conclusion]:
    """El análisis de poder, si ya corrió: qué tan grande tenía que ser una ventaja para verla."""
    if "poder" not in res:
        return []
    e, c = res["poder"]["errores"], res["poder"]["curvas"]
    t = e[e["prueba"].str.startswith("Timing")]
    s = e[e["prueba"].str.startswith("Selección")]
    a = e[e["prueba"].str.startswith("Asignación")]
    cien = c[np.isclose(c["delta"], 0.01) & c["prueba"].str.startswith("Timing")]["inadvertida"]
    texto = (
        "¿«No se encontró» quiere decir «no existe»? Para decidir cuándo entrar al sector, no del todo: lo mínimo que "
        f"las pruebas podían ver era de {_costo(t['mde'].min())} a {_costo(t['mde'].max())} al año, y una regla con "
        f"100 pb de ventaja real habría pasado inadvertida entre {_p(cien.min())} y {_p(cien.max())} de las veces. Lo "
        "que sí se descarta es una ventaja grande y confiable. Y salir a ciegas cuesta de "
        f"{_costo(t['nula_media'].max())} a {_costo(t['nula_media'].min())} al año: es la habilidad que necesita "
        "cualquier regla solo para empatar con aportar siempre.")
    if len(s):
        texto += (f" Para escoger en cuáles las pruebas sí eran finas ({_costo(s['mde'].min())} a "
                  f"{_costo(s['mde'].max())} de efecto mínimo).")
    if len(a):
        f = a.iloc[0]
        cuantas = (f"cada una de las {int(f['placebos'])}" if f["p_placebo"] == 0
                   else f"el {_p(1 - f['p_placebo'])} de las {int(f['placebos'])}")
        texto += (f" Y escoger entre O, NNN y WPC con la valuación ganó {_pb(f['observado'])} al año, más que {cuantas} "
                  "elecciones al azar: ahí la valuación no es una moneda al aire.")
    return [Conclusion("Las pruebas de timing eran poco finas; la de escoger entre REITs, no", texto, "neutral")]


def _que_hacer_extremos(res: dict) -> str:
    if "extremos" not in res or not res["extremos"]["pistas"]["pista"].astype(bool).any():
        return ""
    return (" Y en las pocas crisis en que los REITs quedan en su 5% más barato contra los bonos, no dejar de aportar: "
            "si hay dinero extra, ese ha sido el mejor momento para meterlo.")


def _que_hacer_broker(res: dict) -> str:
    if "sensibilidad_broker" not in res:
        return ""
    return (" Con un broker de EE. UU. el consejo es el mismo: el dividendo paga casi el doble de impuesto que por el "
            "SIC, así que perseguir el yield alto cuesta todavía más.")


def _reevaluaciones(res: dict) -> str:
    if "sensibilidad_broker" not in res:
        return ""
    n = bitacora.intentos(FAMILIA_SENSIBILIDAD)
    return (f", más {n} reevaluaciones de las mismas reglas con los impuestos de un broker de EE. UU. (no son "
            "intentos nuevos)") if n else ""


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
        *_fila_broker(res),
        *_filas_extremos_y_poder(res),
    ], columns=["fase", "que", "detalle", "resultado"])


def _filas_extremos_y_poder(res: dict) -> list[tuple[str, str, str, str]]:
    filas = []
    if "extremos" in res:
        n = int(res["extremos"]["pistas"]["pista"].astype(bool).sum())
        filas.append(("E", "Los extremos de valuación (exploratoria)",
                      "El 5% y 10% más caro y más barato: sector, O/NNN/WPC y todos los REITs",
                      f"{n} pistas, ninguna regla"))
    if "poder" in res:
        t = res["poder"]["errores"]
        t = t[t["prueba"].str.startswith("Timing")]
        filas.append(("P", "Análisis de poder", "Qué tan grande tenía que ser una ventaja para verla",
                      f"Timing: mínimo detectable de {_costo(t['mde'].min())} a {_costo(t['mde'].max())}"))
    return filas


def _fila_broker(res: dict) -> list[tuple[str, str, str, str]]:
    if "sensibilidad_broker" not in res:
        return []
    igual = _broker(res)[0].titulo.endswith("no cambia")
    return [("S", "Con un broker de EE. UU.", "Las mismas reglas con dividendo al 39% o 44%, intereses a la "
             "marginal, ganancia al 10% y sin comisión", "Sin cambio" if igual else "Cambia (posterior)")]
