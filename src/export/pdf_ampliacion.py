"""El informe de la ampliación: ¿lo que se encontró con O, NNN y WPC vale para siete REITs más?

Lee los resultados que guarda ``scripts/estudio.py ampliacion`` (``data/estudios/ampliacion/``) y arma
los estudios de los diez emisores para lo que dicen hoy. Usa la misma maquinaria de impresión que el
compilado (``src/export/compilado.py``).

    python scripts/estudio.py ampliacion-pdf
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.estudio import ampliacion as am
from src.estudio.metodos import TRAMOS
from src.export import compilado as co
from src.export.pdf_estudio import _e, tabla

DESTINO = co.RAIZ / "docs" / "estudios" / "ampliacion_resultados.pdf"
SECTOR = {"ADC": "Net Lease", "EPRT": "Net Lease", "GNL": "Net Lease", "PSA": "Bodegas", "EXR": "Bodegas",
          "PLD": "Industrial", "WELL": "Salud", "O": "Net Lease", "NNN": "Net Lease", "WPC": "Net Lease"}
GRUPOS = (("originales", "O, NNN y WPC (control)"), ("siete", "Los siete nuevos"), ("diez", "Los diez"),
          ("siete_nareit", "Siete, solo FFO de Nareit"))
VEREDICTO = {True: "✓ se repite", False: "✗ no se repite", None: "sin datos"}


def _hipotesis() -> pd.DataFrame:
    h = pd.read_csv(am.DIR_RESULTADOS / "hipotesis.csv")
    h["se_repite"] = h["se_repite"].map({"True": True, "False": False, True: True, False: False})
    return h


def _esperado(grupo: str) -> pd.DataFrame:
    t = pd.read_csv(am.DIR_RESULTADOS / f"esperado_{grupo}.csv")
    return t[t["alcance"] == "juntos"].set_index("tramo")


def g_tramos():
    import plotly.graph_objects as go

    T = co.T
    fig = go.Figure()
    for grupo, nombre, color in (("originales", "O, NNN y WPC", T.contexto_2), ("siete", "Los siete nuevos", T.principal)):
        j = _esperado(grupo)
        orden = [x[0] for x in TRAMOS]
        fig.add_bar(x=[x.capitalize() for x in orden], y=[j.loc[x, "mediana"] for x in orden], name=nombre,
                    marker={"color": color, "line": {"color": T.fondo, "width": 2}},
                    text=[co.p(j.loc[x, "mediana"]) for x in orden], textposition="outside",
                    textfont={"family": T.mono, "size": 10, "color": T.texto}, cliponaxis=False)
    fig.update_layout(barmode="group", bargap=0.25, showlegend=True,
                      title={"text": "Retorno anual de los 5 años siguientes según qué tan caro estaba (mediana, neto "
                                     "con broker al 35%)", "font": {"size": 12}, "x": 0},
                      legend={"orientation": "h", "y": -0.18, "x": 0})
    fig.update_yaxes(tickformat=".0%")
    return fig


def _por_emisor() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lo que dice hoy cada uno de los diez, y una línea de su historia."""
    from src.estudio import estudio, fundamentales, intrinsecos, metodos, reglas

    tickers = (*am.ORIGINALES, *am.NUEVOS)
    estudios = {t: estudio.armar_versionado(t) for t in tickers}
    hoy = metodos.esperado(estudios).hoy.set_index("emisor")
    filas = []
    for t, e in estudios.items():
        cal = reglas.cargar_calificaciones(t)
        si = cal[cal["grado_inversion"] == "si"]
        grado = si[["fecha", "fecha_publicacion"]].max(axis=1).min() if len(si) else None
        filas.append({
            "emisor": t, "sector": SECTOR.get(t, ""), "desde": e.tabla.index[0],
            "retorno": e.total.retorno_total, "medida": fundamentales.medida_de_valuacion(t).etiqueta,
            "nav": "sí" if t in intrinsecos.RECETAS_NOI else "no", "grado": grado,
            "percentil": hoy.loc[t, "percentil"] if t in hoy.index else None,
            "tramo": hoy.loc[t, "tramo"] if t in hoy.index else None,
            "mediana": hoy.loc[t, "mediana"] if t in hoy.index else None,
        })
    return pd.DataFrame(filas).set_index("emisor"), hoy


def html(destino_figs: co.Figs | None = None) -> str:
    figs = destino_figs or co.Figs()
    h = _hipotesis()
    siete = h[h["grupo"] == "siete"].set_index("hipotesis")
    repite = int(siete["se_repite"].eq(True).sum())
    datos, _ = _por_emisor()
    kpis = [("7", "REITs nuevos, de cuatro sectores, con el mismo estudio a fondo"),
            (f"{repite} de {len(siete)}", "conclusiones de O, NNN y WPC que se repiten fuera de muestra"),
            (co.p(_esperado("siete").loc["muy barato", "mediana"]), "al año rindió el 10% más barato (siete nuevos)"),
            (co.p(_esperado("siete").loc["muy caro", "mediana"]), "al año rindió el 10% más caro")]
    c = co._portada("Estudio de largo plazo · ampliación", "¿Lo que aprendimos con O, NNN y WPC vale para otros REITs?",
                    "Repetimos el estudio completo —historia con fuente, valuación con siete métodos y DDM, DCF y "
                    "NAV, el semáforo y el retorno esperado— con ADC, EPRT, GNL, PSA, EXR, PLD y WELL, y probamos "
                    "fuera de muestra, con criterios escritos antes de ver resultados, las conclusiones de los "
                    "tres primeros.", kpis,
                    ["Quiero que ahora realices los mismos análisis que se han hecho a profundidad con O, NNN y WPC "
                     "pero con muchas otras más."])
    c += "<h2>1. La respuesta corta</h2>"
    c += co._conclusion(
        "Lo importante se sostiene", "La valuación sí dice cuánto esperar ganar: en los siete nuevos, comprar "
        f"cuando estaba barato rindió {co.p(_esperado('siete').loc['barato', 'mediana'])} al año a 5 años y cuando "
        f"estaba caro {co.p(_esperado('siete').loc['caro', 'mediana'])}, casi lo mismo que en O, NNN y WPC. "
        "Esperar en efectivo tampoco pagó: aun desde caro, el REIT le ganó al T-bill 78% de las veces. Y usar la "
        "valuación para decidir cuándo comprar no le ganó a aportar siempre en 6 de 7.", "favorable")
    c += co._conclusion(
        "Lo que no se sostiene: repartir según la valuación", "Con O, NNN y WPC, mandar la aportación del mes al "
        "más barato contra su propia historia ganaba +72 pb al año y ninguna elección al azar lo igualaba. Con "
        "los nuevos ganó +122 pb, pero 19% de las elecciones al azar le ganan y mandarla al MÁS CARO también "
        "ganó (+72 pb): la ventaja no viene de la valuación sino de concentrar en pocos papeles en un buen "
        "periodo. Esa recomendación se retira: repartir parejo —o un ETF— es igual de bueno y más simple.",
        "desfavorable")
    c += co._conclusion(
        "El semáforo: la puerta de deterioro sí sirvió una vez", "El semáforo completo le ganó a aportar siempre "
        "en GNL (+515 pb) porque lo marcó en deterioro 93% de los meses —deuda neta de más de 6.5 veces su "
        "EBITDA y AFFO por acción cayendo— y casi nunca lo compró; GNL rindió −0.1% al año desde que cotiza. Pero "
        "en PLD perdió 536 pb: lo marcó en deterioro de 2010 a 2017 por la deuda que dejó la fusión y se perdió "
        "la recuperación; en WELL perdió 257. Como regla para todo, sigue sin servir; como filtro para no entrar a "
        "un emisor en deterioro, GNL es el ejemplo de por qué existe.", "neutral")
    c += "<h2 class='salto'>2. Las ocho pruebas, con su criterio</h2>"
    c += ("<p>El pre-registro (<span class='num'>docs/estudios/ampliacion_preregistro.md</span>) se guardó en un "
          "commit antes de capturar una sola cifra de los siete. Se congeló el código del análisis y se escribió "
          "qué tenía que pasar para decir que cada conclusión «se repite». Los tres originales corrieron otra vez "
          "con el mismo código, como control.</p>")
    filas = []
    for clave in siete.index:
        f = siete.loc[clave]
        otros = [VEREDICTO[h[(h["grupo"] == g) & (h["hipotesis"] == clave)]["se_repite"].iloc[0]]
                 for g, _ in GRUPOS if g != "siete"]
        filas.append([f"<b>{clave}</b>", _e(f["conclusion"]), _e(f["criterio"]), f"<b>{VEREDICTO[f['se_repite']]}</b>",
                      _e(f["cifras"]), *otros])
    c += tabla(filas, ["#", "Conclusión de O, NNN y WPC", "Criterio", "Siete nuevos", "Cifras (siete)",
                       "Control (3)", "Los diez", "Solo Nareit"], alinear="llllllll", clase="indice")
    c += ("<p class='chico gris'>H6 tampoco se cumple en el control: con O, NNN y WPC el NAV ya mostraba la "
          "correlación más alta (+0.71, con dos ventanas), que el estudio original reportó como inconclusa. El "
          "criterio se escribió más estricto que esa conclusión y no se cambió.</p>")
    c += "<h2 class='salto'>3. Cuánto esperar ganar según qué tan caro está</h2>"
    c += figs(g_tramos(), pie="Fuente: data/estudios/ampliacion (esperado_originales.csv y esperado_siete.csv). "
              "Ventanas de 5 años encimadas, en fines de trimestre; los siete aportan 402 trimestres (unas 20 "
              "ventanas independientes).", alto=340)
    t3, t7, t10 = _esperado("originales"), _esperado("siete"), _esperado("diez")
    c += tabla([[x.capitalize(), co.p(t3.loc[x, "mediana"]), co.p(t7.loc[x, "mediana"]), co.p(t10.loc[x, "mediana"]),
                 f"{co.p(t10.loc[x, 'p10'])} a {co.p(t10.loc[x, 'p90'])}", f"{int(t10.loc[x, 'trimestres'])}"]
                for x, *_ in TRAMOS],
               ["Tramo", "O, NNN y WPC", "Siete nuevos", "Los diez", "Rango 10% a 90% (diez)", "Trimestres (diez)"])
    c += ("<p><b>La trampa del valor, con nombre: GNL.</b> De los siete, solo GNL estuvo «barato» contra su historia "
          "por varios trimestres seguidos —y en los 5 años siguientes perdió cerca de 10% al año. Barato porque el "
          "negocio se estaba deteriorando: recortó el dividendo cuatro veces. Es la misma lección de la prueba del "
          "universo: la valuación sirve entre emisores de calidad, no para rescatar a uno que se está cayendo.</p>")
    c += "<h2 class='salto'>4. Los diez, hoy</h2>"
    filas = []
    for t, f in datos.iterrows():
        filas.append([f"<b>{t}</b>", _e(f["sector"]), f"{f['desde']:%Y}", co.p(f["retorno"]), _e(f["medida"]),
                      "—" if pd.isna(f["percentil"]) else f"{f['percentil']:.0%}", _e(f["tramo"] or "—"),
                      co.p(f["mediana"]), "—" if f["grado"] is None or pd.isna(f["grado"]) else f"{f['grado']:%Y}",
                      f["nav"]])
    c += tabla(filas, ["Emisor", "Sector", "Desde", "Rindió al año", "Se valúa por", "Percentil hoy", "Tramo",
                       "Esperado a 5 años", "Grado de inversión desde", "NAV"], alinear="llrrlrlrrl")
    c += ("<p class='chico gris'>«Esperado a 5 años»: lo que rindieron los diez juntos desde ese tramo, neto con "
          "broker al 35%; es una guía, no una promesa. Percentil alto = barato contra su propia historia.</p>")
    c += "<h3>Cómo se capturó cada uno</h3>"
    c += tabla([[f"<b>{t}</b>", _e(x)] for t, x in CAPTURA.items()], ["Emisor", "Lo que costó trabajo"], alinear="ll")
    c += "<h2 class='salto'>5. Qué cambia para ti</h2><ul>" + "".join(f"<li>{x}</li>" for x in QUE_CAMBIA) + "</ul>"
    c += "<h2>Límites</h2><ul>" + "".join(f"<li>{_e(x)}</li>" for x in LIMITES) + "</ul>"
    c += co._anexos([
        ("docs/estudios/ampliacion_preregistro.md", "Las decisiones y los criterios, escritos antes de ver nada."),
        ("docs/estudios/ampliacion_resultados.md", "Las tablas de las cuatro corridas, como las genera el comando."),
        ("docs/estudios/estudio_{ADC,EPRT,EXR,GNL,PLD,PSA,WELL}.pdf", "El estudio completo de cada uno."),
        ("docs/estudios/metodos_de_valuacion.pdf, reglas_de_decision.pdf", "Métodos y semáforo con los diez."),
        ("data/estudios/<emisor>/anuales_primarios.csv", "Cada cifra con su documento, fecha y cita."),
    ])
    return co._documento("Ampliación del estudio", c, figs)


CAPTURA = {
    "ADC": "FFO desde 1995 con la definición vigente de Nareit: 2010 sin los deterioros de Borders y 2014-2018 sin "
           "la amortización de rentas sobre mercado que sumaba (2017-2018 estimados con la proporción de 2016). "
           "Dividendo trimestral hasta 2020 y mensual desde 2021.",
    "EPRT": "Historia corta (2018): no tiene ninguna ventana de 5 años con percentil, aporta su estudio y no "
            "evidencia. Grado de inversión desde nov-2019.",
    "EXR": "Se valúa por Core FFO (encadenado con el de Nareit antes de 2010): en 2009 una ganancia por recompra de "
           "deuda pesó 31% del FFO y en 2015 la compra de SmartStop 21%. El dividendo del 3T-2023 se pagó en dos "
           "partes por la fusión con Life Storage.",
    "GNL": "Contrasplit 1 por 3 en 2017 y paso de dividendo mensual a trimestral en 2019 (el código ahora respeta "
           "la frecuencia de cada época). Se valúa por AFFO: su FFO cargó la salida a bolsa y la fusión de 2023.",
    "PLD": "La historia es la de AMB Property, la sociedad que en 2011 absorbió a ProLogis y tomó su nombre: los "
           "estados XBRL anteriores a 2011 son de la antigua ProLogis y se descartan. Se valúa por Core FFO.",
    "PSA": "Seis correcciones de dividendo: un registro de 1995 equivocado y cinco especiales, una de 13.15 dólares "
           "en 2022. Se valúa por FFO de Nareit: ninguna partida de la lista pasó de 10% (la mayor, 9.98%).",
    "WELL": "Sin FFO de Nareit antes de 2000. Se valúa por FFO normalizado: extinción de deuda y costos de fusiones "
            "de 12% a 17% del FFO, y en 2025 un plan de compensación de 1,497 millones (82%).",
}

QUE_CAMBIA = [
    "<b>Sigue igual:</b> aportar cada mes sin esperar el momento, y diversificado (SCHH). La valuación te dice "
    "cuánto esperar ganar, no cuándo entrar.",
    "<b>Cambia:</b> ya no hay evidencia para repartir la aportación entre REITs según cuál está más barato contra su "
    "historia. Con más emisores, la ventaja desapareció de los controles.",
    "<b>Se refuerza:</b> la calidad primero. GNL estuvo «barato» y perdió; el semáforo lo dejó fuera por deterioro. "
    "Si algún día compras un REIT individual, que pase la puerta de calidad antes de mirar si está barato.",
    "<b>Hoy:</b> la tabla de la sección 4 dice en qué tramo está cada uno y cuánto rindió ese tramo en la historia de "
    "los diez; la app (página Valuación en el tiempo) lo actualiza con los datos nuevos.",
]

LIMITES = [
    "Los siete también sobrevivieron: están en la plataforma porque existen hoy. GNL es lo más cercano a un mal "
    "caso; no hay quiebras.",
    "EPRT no aporta ninguna ventana de 5 años y GNL muy pocas: la evidencia nueva sale sobre todo de ADC, PSA, PLD, "
    "WELL y EXR.",
    "Con ~20 ventanas independientes en los siete y ~33 en los diez, las pruebas siguen siendo poco finas: «se repite» "
    "no vuelve segura una conclusión y «no se repite» no prueba que sea falsa.",
    "Las cifras primarias se capturaron a mano de los 10-K con cita, y algunas son estimadas o calculadas (ADC "
    "2017-2018, AFFO de GNL 2015-2018); cada una lo dice en su renglón.",
]


def generar(destino: Path | None = None) -> Path:
    destino = destino or DESTINO
    return co.a_pdf(html(), destino, "Ampliación del estudio")
