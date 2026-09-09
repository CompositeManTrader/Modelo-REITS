"""Valuación individual: una cabecera que se lee siempre y cuatro pestañas.

Las siete zonas de esta pantalla eran las correctas y el problema era otro:
vivían en un solo scroll de mil líneas, así que el veredicto —lo único que se
mira cada vez— competía por el mismo espacio que la auditoría, que se abre
cuando uno duda de una cifra concreta. Todo estaba, y encontrarlo costaba.

LO QUE SE VE SIEMPRE, sin abrir nada:

    El veredicto y sus tres puertas.
    Nueve cifras en dos bandas: el FLUJO y el PRECIO arriba —yield, prima,
    payout, múltiplo, dividendo— y el BALANCE y el VALOR abajo —apalancamiento,
    spread de inversión, percentil de la prima y premio sobre NAV—.

Esa segunda banda es la que faltaba. El apalancamiento y el spread DECIDEN la
Puerta 1, y estaban a dos pantallas de scroll del veredicto que explican: se
podía leer «DESCARTADO por calidad» sin ver, en la misma vista, cuál de los dos
criterios lo descartó.

EL DETALLE, agrupado por CUÁNDO se mira y no por qué es:

    Evidencia            cuando el veredicto sorprende      (zonas 02 y 05)
    Estados financieros  cuando se quiere ver el renglón    (zonas 03 y 04)
    Modelos              cuando se quiere mover un supuesto (zona 06)
    Auditoría            cuando no se le cree a una cifra   (zona 07)

La cadena de evidencia no cambió y sigue siendo completa: de los estados
financieros salen el NOI y el EBITDAre; de la conciliación del 8-K sale el AFFO;
de los dos juntos salen los modelos. La pestaña «Modelos» es la que hace
auditable a todo lo demás — una cifra sola no se puede comprobar: `6.18%` puede
ser correcto o puede ser un denominador equivocado, y ahí está la fórmula con
los números de ESTA emisora sustituidos.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from comun import (  # noqa: E402
    avisar_procedencia,
    avisos,
    banda_emisor,
    barra_comparativa,
    bps,
    cascada_html,
    cobertura_de_emisores,
    configurar,
    descargo,
    dinero,
    exigir_base,
    explicar,
    filas_metodo,
    mostrar_tabla,
    numero,
    panel_veredicto,
    pct,
    positivo,
    puertas_html,
    rejilla_cifras,
    selector_de_corte,
    selector_de_emisor,
    tarjeta_abre,
    tarjeta_cierra,
    veces,
    zona,
)

from marca import (  # noqa: E402
    AMBAR,
    COLOR_LUZ,
    GRIS,
    GRIS_TENUE,
    LINEA,
    MONO,
    encabezado,
    inyectar_estilos,
    plantilla_plotly,
)
from src.config import DIR_EXPORTES, UMBRALES  # noqa: E402
from src.export.excel import (  # noqa: E402
    DatosExportacion,
    estados_para_libro,
    exportar,
    libro_de_estados,
)
from src.ingesta import reportados  # noqa: E402
from src.modelo import bloomberg  # noqa: E402
from src.modelo.cascada import (  # noqa: E402
    CLAVES_TRAMPA,
    REPORTE,
    calcular_cascada,
    clave_base,
    escalones_de_cascada,
)
from src.modelo.formulas import modelos_de_valuacion  # noqa: E402
from src.modelo.kill import (  # noqa: E402
    ETIQUETAS_FRICCION,
    tabla_liston_friccion,
    venta_parcial_sugerida,
)
from src.modelo.sectorial import metricas_especificas, perfil  # noqa: E402
from src.modelo.senal import sesgo_por_ventana_completa  # noqa: E402
from src.modelo.valuacion import (  # noqa: E402
    InsumosValuacion,
    diagnosticar,
    rango_cap_rate,
    sensibilidad_nav_sectorial,
    valuar_por_crecimiento,
)
from src.servicio import (  # noqa: E402
    MEDIDA_AFFO,
    ORIGEN_DE_INSUMOS,
    RATIOS_PROPIOS,
    construir_panel,
    contexto_macro,
    diagnostico_de_insumos,
    estado_financiero,
    estados_reportados,
    evaluar,
    panel_de_conceptos,
    ratios_propios,
    saldos_de_balance,
)
from src.validacion.cuadre import cuadrar_conciliacion  # noqa: E402

# ── Presentación de las tres vistas ──────────────────────────────────────────
#
# Las tres tablas se dibujan igual y por eso comparten estos tres ayudantes. Lo
# único que cambia entre vistas es de dónde salen los renglones.

_NO_NUMERICAS = frozenset(
    {"Renglón", "Ratio", "tag", "verificado", "sangria", "explicacion",
     *bloomberg.COLUMNAS_DE_APOYO}
)


def _a_millones(tabla: pd.DataFrame) -> pd.DataFrame:
    """Los montos en millones, y las cifras por acción intactas.

    Un balance en unidades obliga a contar ceros y estas tablas existen para
    leerse de un vistazo. La excepción son los renglones por acción: dividir
    `$1.09` entre un millón lo desaparece de la pantalla. Se detectan por la
    magnitud de la propia serie, que es lo único que funciona para las tres
    vistas: la de Bloomberg no tiene nuestras claves y la as reported no tiene
    ninguna.
    """
    if tabla.empty:
        return tabla
    vista = tabla.copy()
    columnas = [c for c in vista.columns if c not in _NO_NUMERICAS]
    if not columnas:
        return vista
    numericas = vista[columnas].apply(pd.to_numeric, errors="coerce")
    # Un renglón cuyo máximo absoluto no llega a mil no es un monto: es una
    # cifra por acción, un múltiplo o un porcentaje.
    escala = numericas.abs().max(axis=1)
    factor = pd.Series(1.0, index=vista.index).where(escala < 1_000, 1e6)
    for columna in columnas:
        vista[columna] = numericas[columna] / factor
    return vista


def _marcar_ajustes(tabla: pd.DataFrame) -> pd.DataFrame:
    """Le pone ⚙ al renglón que Bloomberg construye con una convención propia."""
    if tabla.empty:
        return tabla
    vista = tabla.copy()
    vista["Renglón"] = [
        f"{renglon}  ⚙" if ajuste else renglon
        for renglon, ajuste in zip(vista["Renglón"], vista["ajuste"], strict=True)
    ]
    # Se quedan fuera de la tabla las columnas de apoyo; el ajuste ya viajó al
    # renglón como ⚙ y su texto completo va en el desplegable de abajo.
    return vista.drop(columns=list(bloomberg.COLUMNAS_DE_APOYO))


def _formatear_ratios(tabla: pd.DataFrame) -> pd.DataFrame:
    """Cada ratio con su unidad. Un margen y un múltiplo no se leen igual."""
    if tabla.empty:
        return tabla
    # Con `iterrows` y no con `itertuples`: los encabezados son fechas y
    # `itertuples` renombra a `_1`, `_2` cualquier columna que no sea un
    # identificador válido, así que la columna se pierde en silencio.
    columnas = [c for c in tabla.columns if c not in _NO_NUMERICAS]
    filas = []
    for _, fila in tabla.iterrows():
        salida = {"Ratio": fila["Ratio"]}
        for columna in columnas:
            crudo = fila.get(columna)
            # Con los ayudantes de `comun` y no a mano: `f"{x * 100:.1f}%"`
            # duplica una escala que ya vive en un solo lugar, y es la misma
            # familia del formato de bps que ya costó una vez. Hay una prueba
            # que lo prohíbe en las páginas.
            salida[columna] = pct(crudo, 1) if fila["formato"] == "pct" else veces(crudo)
        filas.append(salida)
    return pd.DataFrame(filas)

configurar("Valuación", "📊")
inyectar_estilos()

repo = exigir_base()
asof = selector_de_corte()

# ══════════════════════════════════════════════════════════════════════════════
# Encabezado de marca y elección de emisora
# ══════════════════════════════════════════════════════════════════════════════

encabezado("Valuación")

# La emisora se elige AQUÍ, en el cuerpo y con los diez nombres a la vista. En la
# barra lateral quedaba debajo del corte y de dos deslizadores, y en pantalla
# angosta Streamlit arranca con la barra plegada: el único control para cambiar
# de emisora quedaba fuera de la vista y la pantalla parecía servir un nombre.
ticker = selector_de_emisor(repo)
if ticker is None:
    st.stop()

cobertura = cobertura_de_emisores(repo, asof=asof)
sin_datos = cobertura[cobertura["trimestres"] == 0]
if not sin_datos.empty:
    st.info(
        f"**{len(sin_datos)} de {len(cobertura)} emisoras no tienen fundamentales al corte**: "
        f"{', '.join(sin_datos['ticker'])}. Elegirlas no rompe nada, pero la pantalla no "
        "puede valuar lo que no está en la base."
    )

sector_del_emisor = repo.sector_de(ticker)
cr_min, cr_base, cr_max = rango_cap_rate(sector_del_emisor)

st.sidebar.divider()
st.sidebar.markdown("**Supuestos del modelo**")
st.sidebar.caption(
    f"Sector: **{sector_del_emisor}**. El cap rate arranca en el rango de SU sector "
    f"({cr_min:.2%}–{cr_max:.2%}), no en uno solo para todos."
)
cap_rate = st.sidebar.slider(
    "Cap rate de mercado para el NAV",
    min_value=round(cr_min - 0.01, 4), max_value=round(cr_max + 0.01, 4),
    value=round(cr_base, 4), step=0.0025, format="%.4f",
    help=(
        "La palanca MÁS sensible del modelo, y la que NO puede ser la misma para todos: "
        "un self storage se capitaliza cerca de 5.5% y una oficina arriba de 8.5%. "
        "Aplicarle a un storage el cap rate de una oficina le quita un tercio del valor "
        "sin que ningún número se vea raro."
    ),
)
yield_adq = st.sidebar.slider(
    "Yield de adquisiciones del emisor", 0.03, 0.12, round(cr_base, 4), 0.0025, format="%.4f",
    help=(
        "A qué cap rate está comprando activos. Contra el costo del capital da el spread "
        "de inversión. Arranca en el cap rate base de SU sector —el mismo del NAV—, no en "
        "un número único: nadie publica el cap rate de sus adquisiciones, así que esto es "
        "un supuesto, y uno solo para todos metía el sesgo del sector en un criterio binario."
    ),
)

panel = construir_panel(
    repo, ticker, asof=asof, cap_rate_mercado=cap_rate, yield_adquisiciones=yield_adq
)
macro = contexto_macro(repo, asof=asof)
semaforo = evaluar(panel)
m = panel.metricas

emisores = repo.emisores()
fila_emisor = emisores.loc[emisores["ticker"] == ticker, "nombre"]
nombre_emisor = str(fila_emisor.iloc[0]) if not fila_emisor.empty else ticker

banda_emisor(
    ticker=ticker,
    nombre=nombre_emisor,
    etiquetas=(panel.sector, panel.medida_flujo),
    precio=panel.precio,
    fecha_precio=panel.precio_fecha,
    corte=asof,
    nota_derecha=f"{panel.n_observaciones} observaciones",
)

# Un emisor sin fundamentales terminaba en un renglón rojo y `st.stop()`: la
# pantalla entera en blanco, sin decir qué falta ni cómo traerlo. Es el único
# camino de esta pantalla que produce exactamente el síntoma de "no puedo ver
# otra emisora", y es también el menos informativo. Ahora diagnostica.
if panel.trimestral.empty:
    st.error(
        f"**{ticker} no tiene fundamentales trimestrales al corte del {asof}.** "
        "No es un error de la aplicación: la base no tiene qué valuar para esta emisora."
    )
    con_datos = cobertura[cobertura["trimestres"] > 0]
    izq, der = st.columns([1, 1], gap="medium")
    with izq:
        st.markdown("**Qué sí hay en la base, al corte elegido**")
        mostrar_tabla(cobertura, column_config={"trimestres": st.column_config.NumberColumn(
            "Trimestres", format="%d")})
    with der:
        st.markdown("**Cómo se llena**")
        st.markdown(
            "La conciliación del AFFO se extrae del Exhibit 99.1 de los 8-K de resultados, "
            "emisora por emisora. Es una medida **no-GAAP**: no está en XBRL, así que no se "
            "puede pedir a una API.\n\n"
            "```\npython scripts/ingesta.py\n```\n"
            "En Streamlit Cloud el sistema de archivos es efímero: **cada reinicio del "
            "contenedor borra la base** y la primera carga vuelve a ingestar. Si la ingesta "
            "se corta a la mitad —la SEC limita la frecuencia de las peticiones— quedan "
            "emisoras sin fundamentales, y esta pantalla es donde se nota."
        )
        if not con_datos.empty:
            st.caption(
                "Con datos ahora mismo: " + ", ".join(
                    f"{r['ticker']} ({int(r['trimestres'])} trimestres)"
                    for _, r in con_datos.iterrows()
                )
            )
    avisos(panel.avisos)
    descargo()
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# 01 · EL VEREDICTO
# ══════════════════════════════════════════════════════════════════════════════

zona("01", "El veredicto", "Tres puertas independientes. Solo la tercera vende.")

_COLOR_ACCION = {
    "COMPRAR": COLOR_LUZ["VERDE"],
    "MANTENER": COLOR_LUZ["VERDE"],
    "NO COMPRAR MÁS": COLOR_LUZ["AMARILLO"],
    "INCONCLUSO": COLOR_LUZ["AMARILLO"],
    "VENDER": COLOR_LUZ["ROJO"],
    "DESCARTADO": COLOR_LUZ["ROJO"],
}
_CODA = {
    "INCONCLUSO": "no es lo mismo que MANTENER",
    "DESCARTADO": "lo que falla no está barato: está descartado",
    "VENDER": "tesis rota, no precio caro",
    "NO COMPRAR MÁS": "modula compras nuevas, no dispara venta",
}


def _recorte(texto: str, largo: int = 52) -> str:
    """Recorta sin fingir que el texto terminaba ahí.

    Cortar en seco a 52 caracteres dejaba frases mutiladas que se leían como
    completas. Los puntos suspensivos dicen que hay más, y el texto íntegro
    sigue estando en la Zona 06.
    """
    texto = str(texto or "")
    return texto if len(texto) <= largo else texto[: largo - 1].rstrip() + "…"


minimo_obs = UMBRALES.valuacion.min_observaciones
izq, der = st.columns([2, 1], gap="medium")
with izq:
    panel_veredicto(
        accion=semaforo.accion.value,
        color=_COLOR_ACCION.get(semaforo.accion.value, COLOR_LUZ["SIN DATOS"]),
        explicacion=semaforo.explicacion,
        coda=_CODA.get(semaforo.accion.value, ""),
        avance=(
            (panel.n_observaciones, minimo_obs)
            if panel.n_observaciones < minimo_obs else None
        ),
    )
with der:
    percentil_txt = (
        f"{panel.percentil_actual:.0%}" if panel.percentil_actual is not None else "—"
    )
    # Cuántos criterios DISPARARON, sobre cuántos se pudieron MEDIR. El
    # denominador estaba fijo en 5, y hoy solo 2 de los 5 son medibles en las
    # diez emisoras: "0/5" se leía como "medí cinco y ninguno disparó", que es
    # una afirmación de cobertura que nadie hizo. La puerta ya distingue —pone
    # luz SIN DATOS cuando no hay nada medible—; la ficha tiraba esa distinción.
    criterios_p3 = semaforo.deterioro.criterios
    if criterios_p3.empty or "dispara" not in criterios_p3:
        medibles_p3 = disparos = 0
    else:
        medibles_p3 = int(criterios_p3["dispara"].notna().sum())
        disparos = int(criterios_p3["dispara"].fillna(False).sum())
    puertas_html(
        [
            ("1 · Calidad", semaforo.calidad.luz.value, _recorte(semaforo.calidad.mensaje), ""),
            ("2 · Valuación", semaforo.valuacion.luz.value,
             _recorte(semaforo.valuacion.mensaje), percentil_txt),
            ("3 · Deterioro", semaforo.deterioro.luz.value,
             _recorte(semaforo.deterioro.mensaje), f"{disparos}/{medibles_p3} medibles"),
        ],
        pie="La Puerta 2 modula compras nuevas. <strong>Nunca dispara venta por sí sola.</strong>",
    )

# Las salvedades van DEBAJO del veredicto, no encima. Encima empujan hacia abajo
# lo único que se lee siempre; debajo lo califican, que es su trabajo. La latencia
# del precio ya está en la banda del emisor y no se repite aquí.
avisar_procedencia(panel.fuentes)
avisos(panel.avisos)

prima_actual = panel.prima.dropna().iloc[-1] if not panel.prima.dropna().empty else None
payout = m.get("payout_affo")
etiqueta_flujo = panel.medida_flujo
rejilla_cifras([
    ("Yield de flujo", pct(m.get("affo_yield")),
     f"{etiqueta_flujo} TTM ÷ precio crudo", ""),
    ("Prima sobre UST 10a", bps(prima_actual),
     f"contra {pct(macro.ust10)} libre de riesgo", ""),
    ("Payout", pct(payout),
     f"el listón son {UMBRALES.calidad.payout_affo_max:.0%}",
     "" if payout is None else
     (COLOR_LUZ["VERDE"] if payout < UMBRALES.calidad.payout_affo_max else COLOR_LUZ["ROJO"])),
    ("Precio / flujo", veces(m.get("p_affo")), f"veces el {etiqueta_flujo} TTM", ""),
    ("Dividendo TTM", pct(m.get("dividend_yield")),
     f"{dinero(panel.dividendo_ttm)} por acción", ""),
])

# Segunda banda: el BALANCE y el VALOR. Las cinco cifras de arriba contestan
# "¿cuánto rinde y cuánto reparte?", que es media pregunta. Las cuatro de aquí
# contestan la otra media —"¿aguanta, crece y a qué precio?"— y hasta ahora
# vivían dentro de las zonas, a dos o tres pantallas de scroll del veredicto que
# ayudan a explicar. Un criterio que decide la Puerta 1 no puede estar escondido.
_apalanc = m.get("deuda_neta_ebitdare")
_spread = m.get("spread_inversion")
_premio = m.get("premio_descuento_nav")
_percentil = panel.percentil_actual
rejilla_cifras([
    ("Apalancamiento", veces(_apalanc),
     f"deuda neta ÷ EBITDAre · listón {UMBRALES.calidad.deuda_neta_ebitdare_max:.1f}x",
     "" if _apalanc is None else
     (COLOR_LUZ["VERDE"] if _apalanc < UMBRALES.calidad.deuda_neta_ebitdare_max
      else COLOR_LUZ["ROJO"])),
    ("Spread de inversión", bps(_spread),
     "yield de compra − costo del capital",
     "" if _spread is None else
     (COLOR_LUZ["VERDE"] if _spread > 0 else COLOR_LUZ["ROJO"])),
    ("Percentil de la prima", "—" if _percentil is None else f"{_percentil:.0%}",
     f"de su propia historia · {panel.n_observaciones} obs.",
     "" if _percentil is None else
     (COLOR_LUZ["VERDE"] if _percentil >= UMBRALES.valuacion.percentil_compra
      else COLOR_LUZ["ROJO"] if _percentil < UMBRALES.valuacion.percentil_mantener
      else COLOR_LUZ["AMARILLO"])),
    # El premio/descuento se pinta al revés que los demás: aquí ROJO es «caro»,
    # no «roto». Cotizar sobre NAV no descalifica a nadie —modula compras, como
    # la Puerta 2— y por eso no lleva el color de un criterio reprobado.
    ("Precio vs NAV", "—" if _premio is None else f"{_premio:+.1%}",
     f"NAV {dinero(m.get('nav_por_accion'))} a cap rate {pct(cap_rate)}",
     "" if _premio is None else
     (COLOR_LUZ["AMARILLO"] if _premio > 0 else COLOR_LUZ["VERDE"])),
])

# ══════════════════════════════════════════════════════════════════════════════
# EL DETALLE, EN CUATRO PESTAÑAS
# ══════════════════════════════════════════════════════════════════════════════
#
# Las siete zonas seguían siendo las correctas y el problema era otro: vivían en
# un solo scroll, así que el veredicto —lo único que se lee siempre— competía por
# el mismo espacio que la auditoría, que se abre cuando uno duda de una cifra.
#
# Se agrupan por CUÁNDO se miran, no por qué son:
#
#     Evidencia   cuando el veredicto sorprende  (zonas 02 y 05)
#     Estados     cuando se quiere ver el renglón (zonas 03 y 04)
#     Modelos     cuando se quiere mover un supuesto (zona 06)
#     Auditoría   cuando no se le cree a una cifra (zona 07)
#
# El orden del archivo no cambia. Streamlit permite reentrar a una pestaña, así
# que la zona 05 vuelve a «Evidencia» sin mover código: las asignaciones siguen
# ocurriendo en el mismo orden y ningún bloque posterior se queda sin su variable.

tab_evidencia, tab_estados, tab_modelos, tab_auditoria = st.tabs(
    ["Evidencia", "Estados financieros", "Modelos", "Auditoría"]
)

with tab_evidencia:
    # ══════════════════════════════════════════════════════════════════════════════
    # 02 · LA EVIDENCIA
    # ══════════════════════════════════════════════════════════════════════════════

    zona("02", "La evidencia", "Tres preguntas distintas. Ninguna se contesta con las otras.")

    affo_ps_ttm = positivo(m.get("affo_por_accion_ttm"))
    if affo_ps_ttm is None and "affo_por_accion_ttm" in panel.trimestral:
        serie_ps = panel.trimestral["affo_por_accion_ttm"].dropna()
        affo_ps_ttm = positivo(serie_ps.iloc[-1]) if not serie_ps.empty else None

    crec_serie = panel.trimestral.get("crecimiento_affo_por_accion_yoy")
    crec_hist = (
        float(pd.to_numeric(crec_serie, errors="coerce").dropna().tail(4).mean())
        if crec_serie is not None and pd.to_numeric(crec_serie, errors="coerce").notna().any()
        else None
    )
    valuacion_g = valuar_por_crecimiento(
        panel.precio, affo_ps_ttm, macro.ust10, panel.sector, crec_hist
    )

    ev_a, ev_b, ev_c = st.columns(3, gap="medium")

    # A · ¿Barato contra su propia historia?
    with ev_a:
        tarjeta_abre(
            "¿Barato contra sí mismo?",
            "Percentil de la prima en ventana expandible, nunca contra otros emisores.",
        )
        serie_prima = panel.prima.dropna()
        if serie_prima.empty:
            st.caption("Sin historia de prima al corte.")
        else:
            # El color de la última barra dice si HOY está barato o caro. La forma
            # anterior era `(percentil or 1) < 0.5`, y el `or` convertía los dos
            # casos que más importan en el color equivocado: sin percentil pintaba
            # verde —hoy son ocho de diez emisoras—, y un percentil de 0.0, que es
            # el más caro de toda su historia, también pintaba verde.
            pa = panel.percentil_actual
            if pa is None:
                color_ultima = COLOR_LUZ["SIN DATOS"]
            else:
                color_ultima = COLOR_LUZ["ROJO"] if pa < 0.5 else COLOR_LUZ["VERDE"]
            figura = go.Figure()
            figura.add_bar(
                x=serie_prima.index, y=serie_prima * 10_000,
                marker_color=[GRIS_TENUE] * (len(serie_prima) - 1) + [color_ultima],
            )
            figura.update_layout(**plantilla_plotly())
            figura.update_layout(
                height=150, margin={"t": 6, "b": 6, "l": 4, "r": 4}, showlegend=False,
                xaxis={"showgrid": False, "showticklabels": False},
                yaxis={"showgrid": False, "title": None, "gridcolor": LINEA,
                       "tickfont": {"size": 9, "color": GRIS, "family": MONO}},
                bargap=0.25,
            )
            st.plotly_chart(figura, key="prima_sparkline")
            if pa is None:
                st.caption(
                    f"La última barra va en gris: con {panel.n_observaciones} observaciones "
                    f"todavía no hay percentil, y pintarla de verde afirmaría que está barata."
                )
        tarjeta_cierra(
            f"<strong>{percentil_txt}</strong> de su propia historia estuvo <em>más</em> barato. "
            f"{panel.n_observaciones} observaciones; el umbral para opinar son {minimo_obs}."
        )

    # B · ¿Alcanza el flujo?
    with ev_b:
        tarjeta_abre(
            "¿Alcanza el flujo?",
            f"El mismo dividendo, tres respuestas. La única que importa es la del {etiqueta_flujo}.",
        )
        p_affo = m.get("payout_affo")
        p_ffo = m.get("payout_ffo")
        p_neta = m.get("payout_utilidad_neta")

        def _color_payout(valor, listón) -> str:
            """Un payout que falta no es un payout sano.

            La forma anterior, `(p_affo or 0) < listón`, mandaba el hueco al lado
            verde: `None` se volvía 0 y 0 siempre pasa el listón. En esta aplicación
            el verde significa «lo medí y está sano», y aquí no se midió nada.
            """
            if valor is None:
                return COLOR_LUZ["SIN DATOS"]
            return COLOR_LUZ["VERDE"] if valor < listón else COLOR_LUZ["ROJO"]

        barra_comparativa(
            [
                (f"sobre {etiqueta_flujo}", p_affo, pct(p_affo),
                 _color_payout(p_affo, UMBRALES.calidad.payout_affo_max), True),
                ("sobre FFO", p_ffo, pct(p_ffo), GRIS_TENUE, False),
                ("sobre utilidad neta", p_neta, pct(p_neta),
                 COLOR_LUZ["SIN DATOS"] if p_neta is None
                 else (COLOR_LUZ["ROJO"] if p_neta > 1 else GRIS_TENUE), False),
            ],
            maximo=1.2,
            marca=UMBRALES.calidad.payout_affo_max,
        )
        razon_txt = ""
        if p_neta and p_affo:
            razon_txt = (
                f" Aquí es <strong>{p_neta / p_affo:.1f} veces</strong> el correcto: ese es el "
                "tamaño del error que comete quien usa el número equivocado."
            )
        tarjeta_cierra(
            "El payout sobre utilidad neta pasa de 100% en casi todo REIT sano: la depreciación "
            "contable no sale de la caja." + razon_txt
            + " Los tres se calculan sobre TTM de cuatro trimestres consecutivos, para que los "
              "tres denominadores midan la misma ventana de tiempo."
        )

    # C · ¿Qué descuenta el precio?
    with ev_c:
        tarjeta_abre(
            "¿Qué descuenta el precio?",
            "Gordon despejado. Es aritmética, no un pronóstico.",
        )
        if valuacion_g is None:
            st.caption(
                "Falta un insumo. En la Zona 04 dice cuál: casi siempre el flujo por "
                "acción TTM, que necesita cuatro trimestres válidos seguidos."
            )
            tarjeta_cierra()
        else:
            c_izq, c_der = st.columns(2)
            c_izq.metric("El precio pide", pct(valuacion_g.crecimiento_implicito))
            c_der.metric(
                "Ha entregado",
                pct(valuacion_g.crecimiento_historico)
                if valuacion_g.crecimiento_historico is not None else "—",
            )
            tarjeta_cierra(valuacion_g.como_texto())


with tab_estados:
    # ══════════════════════════════════════════════════════════════════════════════
    # 03 · LOS ESTADOS FINANCIEROS
    # ══════════════════════════════════════════════════════════════════════════════

    zona("03", "Los estados financieros", "El mismo trimestre, en las tres formas de verlo.")

    st.markdown(
        f"<div style='font-size:13px;line-height:1.55;color:{GRIS};margin-bottom:10px'>"
        "Un estado financiero admite <strong>tres lecturas</strong>, y las tres son legítimas. "
        "<strong>As reported</strong> es lo que la emisora imprimió, con sus renglones y su orden: "
        "es la referencia, y es incomparable entre emisoras porque cada una agrupa distinto. "
        "<strong>Bloomberg</strong> es el molde estandarizado que sí compara, a cambio de aplicar "
        "ajustes que se alejan del filing — y aquí cada ajuste queda marcado. "
        "<strong>Propia</strong> es nuestro catálogo, el que alimenta el modelo. "
        "Todas están filtradas por <strong>fecha de publicación</strong>: lo que ves es lo que se "
        "sabía al corte, no la reexpresión posterior."
        "</div>",
        unsafe_allow_html=True,
    )

    col_freq, col_hist, col_desc = st.columns([1, 1, 2])
    with col_freq:
        frecuencia = st.radio(
            "Frecuencia", ("Trimestral", "Anual"), horizontal=True, key="freq_estados",
        )
    _ANUAL = frecuencia == "Anual"
    _TIPO = "FY" if _ANUAL else "Q"

    # La historia COMPLETA por omisión. Realty Income tiene setenta trimestres y
    # dieciocho ejercicios; mostrar seis era recortar el 90% sin decirlo. Las
    # tablas se desplazan de lado, así que el costo de traerlo todo es un scroll.
    with col_hist:
        _HISTORIAS = {"Todo": None, "Últimos 20": 20, "Últimos 8": 8}
        historia = st.selectbox(
            "Historia", list(_HISTORIAS), key="hist_estados",
            help="Por omisión, todos los periodos que hay. La descarga siempre los lleva todos.",
        )
    _N = _HISTORIAS[historia]

    panel_estados = panel_de_conceptos(
        repo, ticker, asof=asof, periodo_tipo=_TIPO, n_periodos=_N
    )

    with col_desc:
        libro = libro_de_estados(repo, ticker, asof=asof, periodo_tipo=_TIPO)
        st.download_button(
            "Descargar los tres en Excel",
            data=libro,
            file_name=f"{ticker}_estados_{'anual' if _ANUAL else 'trimestral'}_{asof}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help=(
                "Una hoja por vista y por estado, más los ratios. Las columnas son las "
                "mismas que la pantalla, así que las fórmulas del modelo de valuación "
                "apuntan a celdas que existen."
            ),
        )

    v_bbg, v_reportado, v_propia = st.tabs(
        ["Visualización Bloomberg", "Visualización as reported", "Visualización propia"]
    )

    # ── Bloomberg ─────────────────────────────────────────────────────────────
    with v_bbg:
        st.caption(
            "Nuestros datos de EDGAR en el molde de Bloomberg. **No son los datos de "
            "Bloomberg**: son los del filing, ordenados y ajustados como Bloomberg los "
            "presenta. Los renglones que Bloomberg construye a partir de una convención "
            "propia llevan el aviso ⚙ y se explican abajo."
        )
        if panel_estados.empty:
            st.info(f"No hay estados para {ticker} al corte del {asof}.")
        else:
            for estado_bbg in bloomberg.ESTADOS:
                con, piden = bloomberg.cobertura(panel_estados, estado_bbg)
                tabla_bbg = bloomberg.armar(panel_estados, estado_bbg)
                st.markdown(f"**{bloomberg.NOMBRE_ESTADO[estado_bbg]}**")
                st.caption(
                    f"{con} de {piden} renglones del molde se pueden llenar con lo que "
                    "publica la SEC. Los demás quedan en blanco a propósito: un cero ahí "
                    "sería una cifra inventada con formato de dato."
                )
                mostrar_tabla(_a_millones(_marcar_ajustes(tabla_bbg)))
            with st.expander("Los ajustes de Bloomberg, uno por uno"):
                for nombre, texto in bloomberg.AJUSTES.items():
                    st.markdown(f"**{nombre.capitalize()}** — {texto}")
                st.caption(
                    "El molde se leyó del export real de Realty Income. Es la plantilla REIT "
                    "estándar de Bloomberg, así que aplica a las diez, pero solo está "
                    "verificada contra O — que es la única emisora de la que hay un export."
                )

    # ── As reported ───────────────────────────────────────────────────────────
    with v_reportado:
        st.caption(
            "El estado **tal como lo publicó la emisora**, tomado del renderizado que la "
            "propia SEC hace de su XBRL. Mismos renglones, mismo orden, misma sangría y "
            "mismo texto que el 10-Q o el 10-K. Aquí no normalizamos nada."
        )
        formulario = "10-K" if _ANUAL else "10-Q"
        vacias = 0
        for clave_rep in reportados.ESTADOS:
            tabla_rep = estados_reportados(
                ticker, clave_rep, asof=asof, formulario=formulario
            )
            st.markdown(f"**{reportados.NOMBRE_ESTADO[clave_rep]}**")
            if tabla_rep.empty:
                vacias += 1
                st.info(
                    f"No hay {reportados.NOMBRE_ESTADO[clave_rep].lower()} de {ticker} en un "
                    f"{formulario} publicado antes del {asof}."
                )
                continue
            sin_verificar = int((~tabla_rep["verificado"]).sum())
            st.caption(
                f"Del {formulario} publicado más reciente. {len(tabla_rep)} renglones; "
                f"{sin_verificar} sin poder cuadrarse contra nuestra base — casi siempre "
                "etiquetas de extensión que `companyfacts` no publica."
            )
            mostrar_tabla(_a_millones(tabla_rep.drop(columns=["sangria"])))
        if vacias == len(reportados.ESTADOS):
            st.info(
                "Los estados as reported se bajan del renderizado de la SEC. "
                "Corre `python scripts/instantanea.py exportar` para traerlos."
            )

    # ── Propia ────────────────────────────────────────────────────────────────
    with v_propia:
        st.caption(
            "Nuestro catálogo: setenta y cinco renglones comunes a las diez emisoras, que "
            "es lo que hace posible compararlas y lo que alimenta el modelo. Debajo, los "
            "ratios que se leen junto al estado y no en la cabecera."
        )
        _ESTADOS = (
            ("estado_resultados", "Estado de resultados",
             "Cuatro trimestres seguidos son el TTM." if not _ANUAL else "Ejercicio completo."),
            ("balance", "Balance general", "Saldos a la fecha de corte. No se anualizan."),
            ("flujo_efectivo", "Flujo de efectivo",
             "Derivado de los acumulados que publica la SEC."),
        )
        for clave_estado, nombre_estado, nota_estado in _ESTADOS:
            tabla = estado_financiero(
                repo, ticker, clave_estado, asof=asof, periodo_tipo=_TIPO,
                n_periodos=_N,
            )
            st.markdown(f"**{nombre_estado}**")
            if tabla.empty:
                st.info(
                    f"No hay {nombre_estado.lower()} para {ticker} al corte del {asof}. "
                    "Se arma desde companyfacts de la SEC: corre `python scripts/ingesta.py`."
                )
                continue
            st.caption(nota_estado)
            mostrar_tabla(_a_millones(tabla))

        st.markdown("**Ratios**")
        tabla_ratios = ratios_propios(panel_estados)
        if tabla_ratios.empty:
            st.info("No hay suficientes renglones para calcular ratios al corte.")
        else:
            st.caption(
                "Calculados sobre el periodo que se está viendo, no sobre el TTM del modelo: "
                "quien lee el estado de un trimestre quiere el margen de ese trimestre."
            )
            mostrar_tabla(_formatear_ratios(tabla_ratios))
            with st.expander("De qué renglones sale cada ratio"):
                mostrar_tabla(
                    pd.DataFrame(
                        [{"Ratio": e, "Se calcula así": x}
                         for e, _, _, x in RATIOS_PROPIOS]
                    )
                )
    st.caption("Cifras en millones de USD, salvo las de por acción y el conteo de acciones.")

    with st.expander("De qué renglón sale cada insumo del modelo"):
        st.caption(
            "La tabla que contesta «¿de dónde salió este número?» sin abrir el código. A la "
            "izquierda lo que consume la valuación; a la derecha, las líneas que la SEC publicó."
        )
        mostrar_tabla(
            pd.DataFrame(
                [{"Insumo del modelo": a, "Se arma con": b, "Por qué así": c}
                 for a, b, c in ORIGEN_DE_INSUMOS]
            ),
        )
        st.markdown(
            "**Lo que NO se puede sacar de aquí**, dicho para que no parezca un olvido: el "
            "**grado de inversión** es una calificación crediticia y no existe en XBRL, así que "
            "ese criterio de la Puerta 1 se queda sin medir para todas las emisoras. Se puede "
            "capturar a mano; no se puede ingerir."
        )

    # ══════════════════════════════════════════════════════════════════════════════
    # 04 · LA CASCADA
    # ══════════════════════════════════════════════════════════════════════════════

    # Los trimestres que se pueden ofrecer son los de la medida que este emisor sí
    # publica: pedir siempre "affo" dejaba sin cascada a PSA, EXR y WELL, que reportan
    # Core FFO y nunca un AFFO, aunque su conciliación esté completa en la base.
    concepto_flujo = "affo" if panel.medida_flujo == MEDIDA_AFFO else "ffo_normalizado"
    periodos = repo.hechos(asof=asof, tickers=ticker, conceptos=concepto_flujo, periodo_tipo="Q")
    opciones = (
        sorted(pd.to_datetime(periodos["fecha_dato"]).dt.date.unique(), reverse=True)
        if not periodos.empty else []
    )
    fecha_cascada = opciones[0] if opciones else None

    zona(
        "04", "La cascada",
        "De dónde sale el flujo, y si cuadra contra el subtotal que publica el emisor.",
    )
    if opciones:
        fecha_cascada = st.selectbox(
            "Trimestre", opciones, format_func=str, label_visibility="collapsed"
        )

    conciliacion = (
        repo.conciliacion(ticker, fecha_cascada, asof=asof) if fecha_cascada else pd.DataFrame()
    )

    if conciliacion.empty:
        st.info(
            "No hay conciliación línea por línea para este trimestre. Se extrae del Exhibit 99.1 "
            "de los 8-K de resultados: corre `python scripts/ingesta.py` para traerla."
        )
    else:
        lineas = {r["linea"]: float(r["valor"]) for _, r in conciliacion.iterrows()}
        orden_lineas = {r["linea"]: int(r["orden"]) for _, r in conciliacion.iterrows()}
        resultado = calcular_cascada(lineas, sector=panel.sector, signos=REPORTE)
        # Dos preguntas distintas, y confundirlas fue un error mío del rediseño: el
        # CUADRE es aritmético —¿las partidas reproducen el subtotal que el emisor
        # publica?— y las BANDERAS son cualitativas —¿falta una de las tres trampas,
        # el CapEx se ve raro contra el NOI?—. Poner el conteo de banderas bajo la
        # etiqueta "tramos sin cuadrar" decía que una conciliación exacta no cuadraba.
        veredicto = cuadrar_conciliacion(lineas, orden_lineas)

        pasos = escalones_de_cascada(lineas, medida_flujo=panel.medida_flujo)

        verificables = [t for t in veredicto.tramos if t.verificable]
        no_verificables = [t for t in veredicto.tramos if not t.verificable]
        cuadrando = sum(1 for t in verificables if t.cuadra)
        cascada_html(
            pasos,
            pie=(
                f"La conciliación cuadra en sus {cuadrando} tramo(s) verificables, contra los "
                "subtotales que el propio emisor publica"
                if veredicto.cuadra else
                f"{len(verificables) - cuadrando} de {len(verificables)} tramo(s) no cuadran"
            ),
            color_pie=COLOR_LUZ["VERDE"] if veredicto.cuadra else COLOR_LUZ["ROJO"],
            unidad=f"millones de USD · {len(conciliacion)} renglones",
        )
        if not veredicto.cuadra:
            st.error(veredicto.motivo)

        # Qué NO se verificó. Un "cuadra" en verde, sin esta salvedad, afirma más de
        # lo que se comprobó: en las diez emisoras el tramo hacia el AFFO llega SIN
        # desglosar en la tabla del emisor, así que es justo el tramo que la pantalla
        # existe para auditar el que no se verifica. Y las partidas que caen después
        # del último subtotal no entran en ninguna suma: entre ellas, la renta en
        # línea recta y el CapEx de mantenimiento, dos de las tres trampas que esta
        # misma pantalla marca con ⚠️ tres renglones más abajo.
        if no_verificables or veredicto.partidas_ignoradas:
            partes = []
            if no_verificables:
                partes.append(
                    "**Sin verificar: " + ", ".join(t.subtotal for t in no_verificables)
                    + "** — el emisor publica el subtotal pero no desglosa ese tramo, así que se "
                    "toma como lo reporta y no se comprueba."
                )
            if veredicto.partidas_ignoradas:
                partes.append(
                    f"**{len(veredicto.partidas_ignoradas)} partida(s) fuera de todo tramo**, por "
                    "quedar después del último subtotal: "
                    + ", ".join(sorted(veredicto.partidas_ignoradas)) + "."
                )
            st.warning(" ".join(partes) + " El cuadre de arriba **no las cubre**.")

        for bandera in resultado.banderas:
            st.warning(bandera)

        with st.expander("Ver la conciliación renglón por renglón"):
            detalle = conciliacion.copy()
            # Con la clave base: el ajuste de renta en línea recta vive DESPUÉS del
            # primer subtotal y llega con sufijo de segmento, así que compararlo tal
            # cual contra el catálogo nunca lo marcaba.
            detalle["trampa"] = detalle["linea"].map(lambda k: clave_base(k) in CLAVES_TRAMPA)
            ignoradas = set(veredicto.partidas_ignoradas)
            detalle["Línea"] = detalle.apply(
                lambda r: ("⚠️ " if r["trampa"] else "")
                + ("○ " if r["linea"] in ignoradas else "")
                + str(r["etiqueta"]),
                axis=1,
            )
            mostrar_tabla(
                detalle[["Línea", "valor", "linea"]].rename(
                    columns={"valor": "Monto (USD)", "linea": "Concepto normalizado"}
                ),
                column_config={"Monto (USD)": st.column_config.NumberColumn(format="$%,.0f")},
            )
            st.caption(
                "⚠️ marca las tres trampas del AFFO: renta en línea recta, CapEx de mantenimiento y "
                "revaluación a valor razonable. **○ marca las partidas que no entran en ningún tramo "
                "verificado.** Los montos vienen con el signo del reporte, listos para sumarse: así "
                "se reproduce exactamente el subtotal que publica el emisor."
            )
            explicar("NOI", "FFO", "renta en línea recta", "CapEx de mantenimiento")


with tab_evidencia:
    # ══════════════════════════════════════════════════════════════════════════════
    # 05 · QUÉ SE PUEDE VALUAR
    # ══════════════════════════════════════════════════════════════════════════════

    zona("05", "Qué se puede valuar, y qué falta", "Un hueco tiene nombre, no es un cero.")

    fila_ultima = (
        panel.trimestral.tail(1).iloc[0] if not panel.trimestral.empty else pd.Series(dtype="float64")
    )
    insumos_diag = InsumosValuacion(
        ticker=ticker,
        precio=numero(panel.precio, 0.0),
        acciones_diluidas=positivo(fila_ultima.get("acciones_diluidas"), 1.0),
        affo_por_accion_ttm=affo_ps_ttm,
        noi_trimestral=positivo(fila_ultima.get("noi")),
        deuda_total=positivo(fila_ultima.get("deuda_total"), 0.0),
        sector=panel.sector,
    )
    diagnostico = diagnosticar(insumos_diag, tasa_libre_riesgo=macro.ust10)

    _CIFRA_METODO = {
        "Múltiplos (AFFO yield, P/AFFO)": f"{pct(m.get('affo_yield'))} · {veces(m.get('p_affo'))}",
        "Crecimiento implícito en el precio": (
            pct(valuacion_g.crecimiento_implicito) if valuacion_g else "—"
        ),
        "NAV (NOI ÷ cap rate del sector)": (
            f"{dinero(m.get('nav_por_accion'))} · {pct(m.get('premio_descuento_nav'), 1)}"
        ),
    }

    met_izq, met_der = st.columns([1.35, 1], gap="medium")
    with met_izq:
        filas_metodo([
            (
                met.nombre,
                met.explicacion,
                met.disponible,
                _CIFRA_METODO.get(met.nombre, "—") if met.disponible
                else f"Le falta <strong>{', '.join(met.faltantes)}</strong>. "
                     "Es una medida no-GAAP: no está en XBRL, vive en el suplemento y hay que "
                     "extraerla emisora por emisora, como el AFFO.",
            )
            for met in diagnostico
        ])

    with met_der:
        tarjeta_abre(
            f"Cap rate de {panel.sector}",
            "No es una constante universal: es la tasa a la que el mercado privado capitaliza "
            "<em>esta</em> renta.",
        )
        ultima_completa = panel.trimestral.dropna(subset=["affo_por_accion_ttm"]).tail(1)
        tabla_sens = pd.DataFrame()
        if not ultima_completa.empty:
            fila = ultima_completa.iloc[0]
            ins_sens = InsumosValuacion(
                ticker=ticker,
                precio=numero(panel.precio, 0.0),
                acciones_diluidas=positivo(fila.get("acciones_diluidas"), 1.0),
                noi_trimestral=positivo(fila.get("noi")),
                affo_por_accion_ttm=positivo(fila.get("affo_por_accion_ttm")),
                dividendo_ttm_por_accion=panel.dividendo_ttm,
                sector=panel.sector,
            )
            tabla_sens = sensibilidad_nav_sectorial(ins_sens, panel.sector)

        if tabla_sens.empty:
            st.caption(
                f"El rango de {panel.sector} va de {cr_min:.2%} a {cr_max:.2%}, con base en "
                f"{cr_base:.2%}. La curva de sensibilidad necesita el NOI, que todavía falta."
            )
        else:
            figura = go.Figure()
            figura.add_scatter(
                x=tabla_sens["cap_rate"], y=tabla_sens["nav_por_accion"],
                line={"color": AMBAR, "width": 2.5}, name="NAV por acción",
            )
            if panel.precio:
                figura.add_hline(
                    y=panel.precio, line_dash="dash", line_color=COLOR_LUZ["ROJO"],
                    annotation_text="Precio", annotation_position="right",
                )
            figura.update_layout(**plantilla_plotly())
            figura.update_layout(
                height=190, margin={"t": 8, "b": 8, "l": 4, "r": 4}, showlegend=False,
                xaxis={"tickformat": ".2%", "gridcolor": LINEA,
                       "tickfont": {"size": 9, "color": GRIS, "family": MONO}},
                yaxis={"gridcolor": LINEA,
                       "tickfont": {"size": 9, "color": GRIS, "family": MONO}},
            )
            st.plotly_chart(figura, key="sensibilidad_nav")
        tarjeta_cierra(
            "Valuar un self storage al cap rate de net lease le borra <strong>más de una quinta "
            "parte del valor</strong> sin que ningún número se vea raro: la aritmética sigue "
            "cuadrando, solo el supuesto está mal."
        )

    # Un insumo que falta tiene nombre, fecha y consecuencia. Decir "INCONCLUSO" es
    # honesto pero no sirve para actuar: no distingue el dato que se puede conseguir
    # del que la emisora dejó de publicar.
    diag_insumos = diagnostico_de_insumos(panel)
    _ESTADO_INSUMO = {
        "completo": ("VERDE", "Al corriente"),
        "rezagado": ("AMBAR", "Se dejó de publicar"),
        "ausente": ("ROJO", "Nunca se publicó"),
    }
    pendientes = diag_insumos[diag_insumos["estado"] != "completo"]
    if not pendientes.empty:
        st.markdown("###### Insumos que le faltan a este emisor")
        st.dataframe(
            pd.DataFrame({
                "Insumo": pendientes["insumo"],
                "Estado": [_ESTADO_INSUMO[e][1] for e in pendientes["estado"]],
                "Último trimestre": [
                    "—" if f is None else str(f) for f in pendientes["ultima_fecha"]
                ],
                "Trimestres en la base": pendientes["trimestres"],
                "Sin él no hay": pendientes["sin_el_no_hay"],
            }),
            hide_index=True, use_container_width=True,
        )
        st.caption(
            "**Se dejó de publicar** significa que la emisora usó esa etiqueta de XBRL y la "
            "abandonó: el dato existe hasta esa fecha y de ahí en adelante no. Es el caso del "
            "gasto por intereses de Extra Space y de Welltower, y es la razón —la única— de "
            "que las dos se queden sin EBITDAre. `companyfacts` no expone las etiquetas de "
            "extensión de cada emisora, así que ahí no está. Reconstruirlo se probó por tres "
            "caminos y los tres se descartaron midiendo el error contra las emisoras que sí lo "
            "reportan: desde la utilidad de operación (9% a 70%), con el interés pagado del "
            "flujo de efectivo (5% a 11% de mediana, con dos años de Extra Space arriba de "
            "600%) y como residual del estado de resultados (19% a 113%). Un apalancamiento "
            "con ese error no es conservador, es inventado."
        )

    if valuacion_g is not None:
        with st.expander("Escenarios de crecimiento y su valor por acción"):
            # `(crec_hist or 0.0)` convertía "no sé cuánto ha crecido" en "ha crecido
            # 0%", y desarmaba el filtro `if g is not None` que estaba justo para
            # eso: en cinco de diez emisoras la tabla dibujaba tres renglones con el
            # MISMO valor, y uno de ellos se llamaba "El que ha entregado".
            candidatos = [("Sin crecimiento", 0.0)]
            if crec_hist is not None:
                candidatos += [
                    ("Mitad del entregado", crec_hist / 2),
                    ("El que ha entregado", crec_hist),
                ]
            candidatos.append(("Implícito en el precio", valuacion_g.crecimiento_implicito))
            escenarios = pd.DataFrame([
                {
                    "escenario": etiqueta,
                    "crecimiento": g,
                    "valor_por_accion": valuacion_g.valor_con(g),
                    "premio_descuento": (
                        None if not valuacion_g.valor_con(g)
                        else panel.precio / valuacion_g.valor_con(g) - 1.0
                    ),
                }
                for etiqueta, g in candidatos
            ])
            mostrar_tabla(escenarios)
            if crec_hist is None:
                st.caption(
                    "No aparecen los escenarios «mitad del entregado» ni «el que ha entregado»: "
                    "este emisor todavía no tiene historia de crecimiento del flujo por acción. "
                    "Dibujarlos en cero diría que ha crecido 0%, que es otra afirmación."
                )
            st.caption(
                f"Tasa de descuento: UST 10 años {valuacion_g.tasa_libre_riesgo:.2%} más la prima "
                f"de {panel.sector}, {valuacion_g.prima_riesgo:.2%}. El premio/descuento se lee "
                "contra el precio actual: negativo significa que el precio está **por debajo** "
                "del valor que implica ese crecimiento."
            )


with tab_modelos:
    # ══════════════════════════════════════════════════════════════════════════════
    # 06 · LOS MODELOS, CON SUS NÚMEROS
    # ══════════════════════════════════════════════════════════════════════════════

    zona("06", "Los modelos", "La aritmética abierta: cada fórmula con los números de esta emisora.")

    st.markdown(
        f"<div style='font-size:13px;line-height:1.55;color:{GRIS};margin-bottom:10px'>"
        "Una cifra sola no se puede auditar: <span class='cifra'>6.18%</span> puede ser correcto "
        "o puede ser un denominador equivocado, y desde la pantalla no hay forma de distinguirlo. "
        "Aquí está la fórmula, están los números de <strong>esta</strong> emisora sustituidos, y "
        "está el resultado — para que la aritmética se pueda seguir con el dedo."
        "</div>",
        unsafe_allow_html=True,
    )

    fila_modelos = panel.trimestral.tail(1).iloc[0]
    ins_modelos = InsumosValuacion(
        ticker=ticker,
        precio=numero(panel.precio, 0.0),
        acciones_diluidas=positivo(fila_modelos.get("acciones_diluidas"), 1.0),
        noi_trimestral=positivo(fila_modelos.get("noi")),
        affo_ttm=positivo(fila_modelos.get("affo_ttm")),
        affo_por_accion_ttm=affo_ps_ttm,
        ffo_ttm=positivo(fila_modelos.get("ffo_ttm")),
        utilidad_neta_ttm=positivo(fila_modelos.get("utilidad_neta_ttm")),
        dividendo_ttm_por_accion=panel.dividendo_ttm,
        deuda_total=positivo(fila_modelos.get("deuda_total"), 0.0),
        sector=panel.sector,
    )
    modelos = modelos_de_valuacion(
        ins_modelos,
        cap_rate_mercado=cap_rate,
        tasa_libre_riesgo=macro.ust10,
        medida_flujo=panel.medida_flujo,
        yield_adquisiciones=yield_adq,
    )

    corren = [f for f in modelos if f.disponible]
    st.caption(
        f"**{len(corren)} de {len(modelos)} modelos corren** con los insumos que hay para "
        f"{ticker} al corte del {asof}. Los que no, dicen qué insumo les falta."
    )

    for f in modelos:
        color = AMBAR if f.disponible else GRIS
        with st.container(border=True):
            cab, val = st.columns([3, 1])
            with cab:
                st.markdown(
                    f"<span class='rotulo' style='color:{color}'>{f.nombre}</span>",
                    unsafe_allow_html=True,
                )
            with val:
                st.markdown(
                    f"<div class='cifra' style='text-align:right;font-size:19px;font-weight:600;"
                    f"color:{color}'>{f.texto_resultado()}</div>",
                    unsafe_allow_html=True,
                )
            st.latex(f.latex)
            if f.sustitucion:
                st.latex(f.sustitucion)
            else:
                st.markdown(
                    f"<div style='font-size:12px;color:{COLOR_LUZ['AMARILLO']}'>"
                    f"No se puede calcular: le falta <strong>{', '.join(f.falta)}</strong>.</div>",
                    unsafe_allow_html=True,
                )
            st.caption(f.definicion + (f" · {f.nota}" if f.nota else ""))

    with st.expander("El percentil, que no es una fórmula cerrada"):
        st.markdown(
            "El percentil de la prima no se calcula con una fórmula: es una **posición dentro de "
            "una muestra que crece**. En cada fecha $t$:"
        )
        st.latex(
            r"\text{percentil}_t = \frac{\#\{\,\pi_s \le \pi_t \;:\; s \le t\,\}}"
            r"{\#\{\,s \le t\,\}}, \qquad \#\{s \le t\} \ge "
            + str(UMBRALES.valuacion.min_observaciones)
        )
        st.markdown(
            f"La condición de la derecha es la que hace honesto al número: **solo la historia "
            f"hasta $t$**, nunca la muestra completa. Usar la muestra completa sería fijar "
            f"umbrales con información del futuro — el modelo «sabría» en 2019 que el yield iba a "
            f"llegar a su máximo en 2023. Y con menos de "
            f"{UMBRALES.valuacion.min_observaciones} observaciones no se emite: no es un percentil, "
            f"es una opinión. Aquí hay **{panel.n_observaciones}**."
        )


with tab_auditoria:
    # ══════════════════════════════════════════════════════════════════════════════
    # 07 · AUDITORÍA
    # ══════════════════════════════════════════════════════════════════════════════

    zona("07", "Auditoría", "Cerrado por omisión. Cada cifra rastreable hasta su documento.")

    with st.expander("Las tres puertas, criterio por criterio"):
        for puerta, titulo in (
            (semaforo.calidad, "Puerta 1 — Calidad"),
            (semaforo.valuacion, "Puerta 2 — Valuación"),
            (semaforo.deterioro, "Puerta 3 — Deterioro"),
        ):
            st.markdown(f"**{titulo}** — {puerta.mensaje}")
            if not puerta.criterios.empty:
                mostrar_tabla(
                    puerta.criterios[[
                        c for c in ("criterio", "valor", "umbral", "persistencia",
                                    "cumple", "racha", "dispara")
                        if c in puerta.criterios
                    ]],
                )
        explicar("AFFO", "prima", "percentil expandible", "spread de inversión")

    with st.expander("Por qué el percentil usa ventana expandible y no la muestra completa"):
        if panel.prima.dropna().empty:
            st.caption("Sin serie de prima al corte.")
        else:
            sesgo = sesgo_por_ventana_completa(panel.prima.dropna())
            fig2 = go.Figure()
            fig2.add_scatter(x=sesgo.index, y=sesgo["expandible"], name="Expandible (lo correcto)",
                             line={"color": AMBAR})
            fig2.add_scatter(x=sesgo.index, y=sesgo["muestra_completa"],
                             name="Muestra completa (usa el futuro)",
                             line={"color": COLOR_LUZ["ROJO"], "dash": "dash"})
            fig2.update_layout(**plantilla_plotly())
            fig2.update_layout(height=260, yaxis_tickformat=".0%",
                               legend={"orientation": "h", "y": 1.15})
            st.plotly_chart(fig2, key="sesgo_ventana")
            brecha = sesgo["diferencia"].abs().mean()
            st.markdown(
                f"La diferencia media entre ambas es de **{brecha:.0%} de percentil**. La curva roja "
                "sabe, en 2019, que el yield iba a llegar a su máximo en 2023. Nadie lo sabía. "
                "Fijar umbrales con esa curva es fijarlos con información del futuro."
            )

    with st.expander("Quiero vender por valuación de todos modos"):
        st.caption(
            "Vender por precio caro es distinto de vender por tesis rota. La Puerta 2 nunca "
            "dispara venta por sí sola. Si aun así quieres, este es el costo."
        )
        valor_posicion = st.number_input("Valor de tu posición (USD)", 0.0, value=100_000.0, step=5_000.0)
        ganancia = st.slider("Ganancia acumulada sobre el costo", 0.0, 3.0, 0.40, 0.05, format="%.2f")
        sugerencia = venta_parcial_sugerida(valor_posicion, ganancia_acumulada=ganancia)
        a, b, c, d = st.columns(4)
        a.metric("Venta parcial sugerida", f"{sugerencia['fraccion_sugerida']:.0%}")
        # La parte gravable va a la vista porque es el paso que el cálculo se
        # saltaba: con 40% de ganancia SOBRE EL COSTO, la posición vale 1.4 veces lo
        # que costó, así que solo 40/140 = 28.6% de lo que vendes es ganancia.
        b.metric("Parte gravable de lo vendido", pct(sugerencia["fraccion_gravable"], 1),
                 help="El ISR se paga sobre la ganancia embebida en lo que vendes, no sobre el valor.")
        c.metric("Costo fiscal estimado", dinero(sugerencia["costo_fiscal_estimado"]))
        d.metric("Ventaja anual necesaria", f"{sugerencia['ventaja_anual_necesaria_bps']:,.0f} bps",
                 help="Cuánto más tiene que rendir el destino, al año, para recuperar el costo fiscal en dos años.")
        st.warning(sugerencia["advertencia"])
        mostrar_tabla(tabla_liston_friccion(), column_config=ETIQUETAS_FRICCION)
        st.caption(
            "El ISR cedular de 10% se paga sobre la **ganancia**, no sobre el valor vendido. "
            "Por eso la columna de en medio: con 100% de ganancia sobre el costo, la mitad de lo "
            "que vendes es ganancia y el costo fiscal es 5% del valor — no 10%, como reportaba "
            "la versión anterior de esta tabla. El cálculo ignora el efecto del tipo de cambio "
            "sobre la ganancia en pesos, que es una simplificación y no un olvido."
        )

    with st.expander(f"Qué mirar en un REIT de {panel.sector}"):
        perfil_sector = perfil(panel.sector)
        if perfil_sector:
            s1, s2 = st.columns(2)
            s1.markdown(
                f"- **Duración de contrato:** {perfil_sector.duracion_contrato}\n"
                f"- **Tipo de inquilino:** {perfil_sector.tipo_inquilino}\n"
                f"- **Intensidad de CapEx:** {perfil_sector.intensidad_capex}\n"
                f"- **Quién paga los gastos:** {perfil_sector.quien_paga_gastos}"
            )
            s2.info(perfil_sector.nota)
        for metrica, explicacion in metricas_especificas(panel.sector).items():
            st.markdown(f"- **{metrica}** — {explicacion}")

    # Un título que dice "completa" sobre una tabla recortada es una afirmación
    # falsa, y esta pantalla vive de que sus afirmaciones se puedan verificar. PSA
    # tiene 73 trimestres y se dibujaban 20.
    _MAX_TRIMESTRES = 20
    _n_tri = len(panel.trimestral)
    _titulo_tri = (
        f"Serie trimestral completa ({_n_tri} trimestres)" if _n_tri <= _MAX_TRIMESTRES
        else f"Serie trimestral — últimos {_MAX_TRIMESTRES} de {_n_tri} trimestres"
    )
    with st.expander(_titulo_tri):
        mostrar_tabla(panel.trimestral.tail(_MAX_TRIMESTRES))
        if _n_tri > _MAX_TRIMESTRES:
            st.caption(
                f"Se dibujan los {_MAX_TRIMESTRES} más recientes de {_n_tri}. La serie íntegra sale "
                "en el libro de Excel de abajo."
            )

    _MAX_FUENTES = 60
    _n_fuentes = len(panel.fuentes)
    _titulo_fuentes = (
        f"Procedencia de cada cifra ({_n_fuentes} registros)" if _n_fuentes <= _MAX_FUENTES
        else f"Procedencia — {_MAX_FUENTES} de {_n_fuentes} registros"
    )
    with st.expander(_titulo_fuentes):
        st.caption(
            "Primario significa que viene directo de la SEC o de un banco central. Derivado o "
            "reconstruido significa que lo calculó el modelo y hereda el error de sus componentes."
        )
        if not panel.fuentes.empty:
            mostrar_tabla(panel.fuentes.head(_MAX_FUENTES))
            if _n_fuentes > _MAX_FUENTES:
                st.caption(
                    f"**Se dibujan {_MAX_FUENTES} de {_n_fuentes} registros**, los más recientes. "
                    "Una sección de trazabilidad que recorta en silencio deja de servir para "
                    "trazar: el libro de Excel lleva la lista íntegra."
                )

    with st.expander("Exportar a Excel con fórmulas vivas"):
        st.caption(
            "El libro sale con **fórmulas vivas**, no valores pegados: cambia el cap rate o el precio "
            "en la hoja de Inputs y todo recalcula. Azul sobre amarillo es tuyo; negro es fórmula."
        )
        if st.button("Generar libro de Excel", type="primary"):
            ultima = panel.trimestral.dropna(subset=["affo_por_accion_ttm"]).tail(1)
            if ultima.empty:
                st.error("No hay un trimestre completo para exportar.")
            else:
                fila = ultima.iloc[0]
                _saldos = saldos_de_balance(repo, ticker, asof=asof)
                # El FFO y la utilidad neta van en TTM real, con la misma regla de
                # cuatro trimestres consecutivos que el AFFO. Antes se anualizaba un
                # trimestre por cuatro, y el libro exportado llevaba ese error a la
                # hoja de cálculo del usuario.
                ins = InsumosValuacion(
                    ticker=ticker,
                    precio=numero(panel.precio, 0.0),
                    acciones_diluidas=positivo(fila.get("acciones_diluidas"), 1.0),
                    noi_trimestral=positivo(fila.get("noi")),
                    affo_ttm=positivo(fila.get("affo_ttm")),
                    affo_por_accion_ttm=positivo(fila.get("affo_por_accion_ttm")),
                    ffo_ttm=positivo(fila.get("ffo_ttm")),
                    utilidad_neta_ttm=positivo(fila.get("utilidad_neta_ttm")),
                    dividendo_ttm_por_accion=panel.dividendo_ttm,
                    # El balance y los dos TTM que la hoja de Inputs pide por
                    # renglón. Sin esto el libro los escribía en CERO —los cinco
                    # saldos, el EBITDAre y los intereses— y su hoja de Valuación
                    # calculaba apalancamiento, LTV y NAV sobre nada. En la
                    # pantalla los números salían bien, así que el error solo
                    # existía en el archivo que el usuario se lleva.
                    deuda_total=positivo(_saldos.get("deuda_total"), 0.0),
                    efectivo=positivo(_saldos.get("efectivo"), 0.0),
                    prestamos_por_cobrar=positivo(_saldos.get("prestamos_por_cobrar"), 0.0),
                    inversiones_no_consolidadas=positivo(
                        _saldos.get("inversiones_no_consolidadas"), 0.0
                    ),
                    goodwill=positivo(_saldos.get("goodwill"), 0.0),
                    ebitdare_ttm=positivo(fila.get("ebitdare_ttm")),
                    intereses_ttm=positivo(fila.get("gasto_intereses_ttm")),
                    sector=panel.sector,
                )
                componentes = (
                    {r["linea"]: float(r["valor"]) for _, r in conciliacion.iterrows()}
                    if not conciliacion.empty
                    else {}
                )
                datos = DatosExportacion(
                    ticker=ticker,
                    nombre=nombre_emisor,
                    sector=panel.sector,
                    fecha_corte=asof,
                    insumos=ins,
                    componentes_cascada=componentes,
                    cap_rate_mercado=cap_rate,
                    tasa_libre_riesgo=panel.tasa_libre_riesgo or 0.042,
                    yield_adquisiciones=yield_adq,
                    # La procedencia va íntegra al libro. Recortarla a 200 dejaba
                    # fuera 269 registros de Realty Income sin decirlo, ni en la
                    # pantalla ni en el archivo.
                    fuentes=panel.fuentes.to_dict("records") if not panel.fuentes.empty else [],
                    # Las tres vistas entran al MISMO libro, y los insumos que
                    # salen de un estado se vuelven fórmula que apunta a su
                    # renglón. Es lo que separa un libro con dos secciones de un
                    # modelo cableado: cambiar la deuda en el balance mueve el
                    # apalancamiento, el LTV y el NAV.
                    # Sin tope de periodos: el libro se lleva TODA la historia, aunque
                    # la pantalla esté mostrando un recorte.
                    estados=estados_para_libro(repo, ticker, asof=asof),
                )
                ruta = exportar(datos, DIR_EXPORTES / f"{ticker}_{asof}.xlsx")
                st.success(f"Libro generado: `{ruta}`")
                with open(ruta, "rb") as fh:
                    st.download_button(
                        "Descargar", fh.read(), file_name=ruta.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )


st.markdown(
    f"<div style='font-size:11px;line-height:1.6;color:{GRIS};margin-top:18px;"
    f"border-top:1px solid {LINEA};padding-top:12px'>"
    "Contenido educativo y de análisis. <strong>No es asesoría de inversión.</strong> Toda "
    "métrica de desempeño va acompañada de su conteo de apuestas efectivas. Cuando las "
    "observaciones son insuficientes el veredicto es <strong>INCONCLUSO</strong>, nunca GO. "
    "Resultados pasados no garantizan resultados futuros.</div>",
    unsafe_allow_html=True,
)
descargo()
