"""Valuación sectorial, comparables y ranking relativo.

Los trece sectores de Nareit tienen economías completamente distintas: un contrato
de torre de telecomunicaciones dura décadas y no consume CapEx; una oficina se
renegocia cada cinco años y devora mejoras al inquilino. Los rankings de múltiplos
**solo son válidos dentro del mismo sector**.

Lo que sí cruza sectores es el percentil de la prima sobre la propia historia,
porque cada emisor se mide contra sí mismo. Aun así, la interfaz advierte: que un
sector esté barato contra su historia no significa que sustituya a otro.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.config import CAPEX_ESPERADO_POR_SECTOR
from src.modelo.senal import percentil_expandible

# Observaciones mínimas para emitir un percentil. Vive aquí, con nombre, porque la
# pantalla necesita citarlo al explicar qué sector se queda fuera y por qué.
MIN_OBSERVACIONES_PERCENTIL = 12

# El mismo percentil se dibuja dos veces en la pantalla —en la tabla del ranking y
# en la gráfica de comparación— y cada una la formatea un motor distinto: Streamlit
# formatea en JavaScript, que en el empate redondea hacia arriba, y la gráfica en
# Python, que redondea al par. Con cero decimales el mismo 0.125 salía «13%» en la
# tabla y «12%» en la gráfica, a dos dedos de distancia. Se corrige en dos pasos:
# los decimales viven aquí una sola vez, para que no puedan discrepar, y el dato se
# redondea en Python ANTES de entregarlo, para que al motor de dibujo no le quede
# nada que redondear y el empate no llegue a existir.
DECIMALES_PERCENTIL = 1
FORMATO_PERCENTIL_TABLA = f"%.{DECIMALES_PERCENTIL}f%%"

# --------------------------------------------------------------------------------------
# Características económicas por sector
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PerfilSectorial:
    sector: str
    duracion_contrato: str
    tipo_inquilino: str
    intensidad_capex: str
    quien_paga_gastos: str
    nota: str = ""


PERFILES: dict[str, PerfilSectorial] = {
    "Net Lease": PerfilSectorial(
        "Net Lease",
        "10–20 años con escalador",
        "Corporativo, muchas veces con grado de inversión",
        "Muy baja: la paga el inquilino",
        "Inquilino (triple neto)",
        "Un CapEx de mantenimiento cercano a cero es legítimo aquí y solo aquí.",
    ),
    "Industrial": PerfilSectorial(
        "Industrial", "3–7 años", "Logística y manufactura", "Baja", "Mixto",
        "Ligado al comercio electrónico y a la reconfiguración de cadenas de suministro.",
    ),
    "Oficinas": PerfilSectorial(
        "Oficinas", "5–10 años", "Corporativo", "Alta: mejoras al inquilino recurrentes", "Propietario",
        "CapEx bajo 5% del NOI es bandera roja: las oficinas requieren reinversión constante.",
    ),
    "Comercial": PerfilSectorial(
        "Comercial", "5–10 años", "Minoristas", "Media–alta", "Mixto",
        "Renta variable ligada a ventas del inquilino en algunos contratos.",
    ),
    "Residencial": PerfilSectorial(
        "Residencial", "1 año", "Personas físicas", "Media", "Propietario",
        "Se reprecia rápido con la inflación, pero la rotación cuesta.",
    ),
    "Self Storage": PerfilSectorial(
        "Self Storage", "Mensual", "Personas físicas", "Baja", "Propietario",
        "Contrato cortísimo: la renta se reprecia casi en tiempo real.",
    ),
    "Salud": PerfilSectorial(
        "Salud", "10–15 años", "Operadores de vivienda para adultos mayores y hospitales", "Media", "Mixto",
        "Riesgo de operador: el inquilino puede quebrar aunque el inmueble esté lleno.",
    ),
    "Hoteles": PerfilSectorial(
        "Hoteles", "Una noche", "Huéspedes", "Muy alta", "Propietario",
        "El más cíclico: la renta se reprecia diario en ambas direcciones.",
    ),
    "Data Centers": PerfilSectorial(
        "Data Centers", "5–15 años", "Hiperescaladores y empresas", "Media", "Mixto",
        "Obsolescencia tecnológica y consumo eléctrico son riesgos que no aparecen en el NOI.",
    ),
    "Torres": PerfilSectorial(
        "Torres", "10+ años con escalador", "Operadores de telecomunicaciones", "Muy baja", "Inquilino",
        "Economía de colocación: el tercer inquilino en la misma torre es casi todo margen.",
    ),
    "Bosques": PerfilSectorial(
        "Bosques", "Variable", "Aserraderos", "Media", "Propietario",
        "El inventario crece solo: se puede posponer la cosecha si el precio no gusta.",
    ),
    "Vivienda Prefabricada": PerfilSectorial(
        "Vivienda Prefabricada", "1 año sobre el terreno", "Personas físicas", "Baja", "Mixto",
        "El residente es dueño de la casa y renta el terreno: rotación bajísima.",
    ),
    "Diversificado": PerfilSectorial(
        "Diversificado", "Mixta", "Mixto", "Media", "Mixto",
        "Los promedios ocultan la dispersión interna; hay que abrir por tipo de activo.",
    ),
    "Especializado": PerfilSectorial(
        "Especializado", "Variable", "Nicho", "Variable", "Variable",
        "Casinos, publicidad exterior, campos de golf. Cada uno tiene su propia economía.",
    ),
}


def perfil(sector: str) -> PerfilSectorial | None:
    return PERFILES.get(sector)


def tabla_perfiles() -> pd.DataFrame:
    return pd.DataFrame([p.__dict__ for p in PERFILES.values()])


# --------------------------------------------------------------------------------------
# Contexto histórico. Se muestra para que el usuario no extrapole de un solo nombre.
# --------------------------------------------------------------------------------------

CONTEXTO_HISTORICO: tuple[dict, ...] = (
    {
        "hecho": "Self storage rindió ~17.3% anual desde 1994, contra 10.1% del S&P 500.",
        "leccion": "El mejor sector de tres décadas fue el de contratos más cortos, no el de más largos.",
    },
    {
        "hecho": "Data centers fue el mejor sector de 2023 (+25.2%) y el peor de 2025 (−14.2%).",
        "leccion": "Un sector puede pasar del primero al último lugar en dos años. No extrapoles de un nombre ni de un año.",
    },
)

# El periodo va como texto en TODAS las filas, no como año numérico en unas y rango
# en otras. Una columna que mezcla 2023 con "1994–2024" no es un año: es una etiqueta,
# y pandas la degrada a `object`, lo que revienta la serialización a Arrow al
# dibujarla. Que el tipo diga lo que la columna realmente es evita el problema en el
# origen en lugar de parcharlo en cada pantalla que la muestre.
DISPERSION_SECTORIAL = pd.DataFrame(
    [
        {"sector": "Data Centers", "periodo": "2023", "rendimiento": 0.252, "lugar": "mejor del año"},
        {"sector": "Data Centers", "periodo": "2025", "rendimiento": -0.142, "lugar": "peor del año"},
        {"sector": "Self Storage", "periodo": "1994–2024", "rendimiento": 0.173, "lugar": "anualizado"},
        {"sector": "S&P 500", "periodo": "1994–2024", "rendimiento": 0.101, "lugar": "anualizado"},
    ]
).astype({"periodo": "string"})


# --------------------------------------------------------------------------------------
# Ranking y comparables
# --------------------------------------------------------------------------------------


class AdvertenciaSectorial(UserWarning):
    pass


def validar_comparacion(sectores: list[str]) -> str | None:
    """Devuelve la advertencia a mostrar si se están mezclando sectores."""
    distintos = sorted(set(sectores))
    if len(distintos) <= 1:
        return None
    return (
        "Estás comparando emisores de sectores distintos: "
        + ", ".join(distintos)
        + ". Los múltiplos (P/AFFO, cap rate) NO son comparables entre sectores porque la "
        "duración de contrato, la intensidad de CapEx y el tipo de inquilino son distintos. "
        "Lo único comparable aquí es el percentil de la prima de cada emisor contra su propia historia."
    )


def ranking_dentro_del_sector(
    panel: pd.DataFrame,
    *,
    columna_metrica: str = "percentil_prima",
    columna_sector: str = "sector",
) -> pd.DataFrame:
    """Ordena emisores **dentro** de cada sector. Es el único ranking de múltiplos válido."""
    if panel.empty:
        return panel
    df = panel.copy()
    df["ranking_en_sector"] = (
        df.groupby(columna_sector)[columna_metrica].rank(ascending=False, method="min")
    )
    df["n_en_sector"] = df.groupby(columna_sector)[columna_metrica].transform("count")
    return df.sort_values([columna_sector, "ranking_en_sector"]).reset_index(drop=True)


def cobertura_del_percentil(
    panel_historico: pd.DataFrame,
    *,
    min_observaciones: int = MIN_OBSERVACIONES_PERCENTIL,
) -> pd.DataFrame:
    """Por sector: cuántas fechas tiene y si le alcanzan para emitir percentil.

    El umbral de doce observaciones es correcto —un percentil sobre ocho trimestres
    es una opinión, no un percentil—, pero aplicarlo en silencio deja un mapa de
    calor sectorial con una sola fila bajo una leyenda que habla de comparar filas
    entre sí. Un hueco tiene nombre: esta función lo da, para que la pantalla pueda
    decir cuáles faltan, cuántas fechas tienen y cuántas les faltan.
    """
    columnas = ["sector", "fechas", "alcanza", "faltan"]
    if panel_historico is None or panel_historico.empty:
        return pd.DataFrame(columns=columnas)

    fechas = (
        panel_historico.groupby("sector")["fecha_dato"].nunique().rename("fechas").reset_index()
    )
    fechas["alcanza"] = fechas["fechas"] >= min_observaciones
    fechas["faltan"] = (min_observaciones - fechas["fechas"]).clip(lower=0)
    return fechas.sort_values(["alcanza", "fechas"], ascending=[False, False])[
        columnas
    ].reset_index(drop=True)


def cuantizar_percentil(fraccion):
    """Deja la fracción con los decimales que se van a dibujar, y ni uno más.

    Redondear aquí, en Python, es lo que hace que la tabla y la gráfica coincidan:
    al entregar un valor que ya cabe exacto en los decimales dibujados, ninguno de
    los dos motores de formato tiene que romper un empate, y el desacuerdo entre
    ellos desaparece en vez de volverse más chico.
    """
    decimales = DECIMALES_PERCENTIL + 2  # la fracción es la centésima parte del porcentaje
    if isinstance(fraccion, pd.Series):
        return fraccion.round(decimales)
    return None if fraccion is None or pd.isna(fraccion) else round(float(fraccion), decimales)


def texto_percentil(fraccion) -> str:
    """El percentil como lo escribe la gráfica, con los decimales de la tabla."""
    valor = cuantizar_percentil(fraccion)
    return "—" if valor is None else f"{valor:.{DECIMALES_PERCENTIL}%}"


def huecos_del_ranking(
    universo: pd.DataFrame,
    *,
    columna_percentil: str = "percentil_prima",
    columna_sector: str = "sector",
) -> tuple[list[str], list[str]]:
    """Quiénes se quedan fuera del ranking y qué sectores se van enteros con ellas.

    El respaldo de la pantalla solo se dispara cuando el ranking queda *enteramente*
    vacío, y el caso normal no es ese: es que la mayoría de las emisoras todavía no
    junta historia. Sin nombrarlas, la pantalla anuncia «ranking dentro de cada
    sector» y dibuja un sector con dos nombres, sin decir dónde quedaron los demás.

    Un sector solo se reporta ausente si **ninguna** de sus emisoras llegó: con una
    que sí tenga percentil, el sector aparece y no hay hueco que anunciar.
    """
    if universo is None or universo.empty or columna_percentil not in universo.columns:
        return [], []
    falta = universo[columna_percentil].isna()
    tickers = sorted(universo.loc[falta, "ticker"])
    sectores: list[str] = []
    if columna_sector in universo.columns:
        sectores = sorted(
            set(universo.loc[falta, columna_sector]) - set(universo.loc[~falta, columna_sector])
        )
    return tickers, sectores


def muestrear_columnas(matriz: pd.DataFrame, *, maximo: int = 40) -> pd.DataFrame:
    """Reduce las columnas a lo más ``maximo``, conservando SIEMPRE la última.

    Un salto posicional desde el inicio descarta el trimestre más reciente en cuanto
    el total no es múltiplo del paso —con 100 columnas tira la última, con 120 las
    dos últimas—, y este gráfico existe justamente para decir dónde estamos hoy. Se
    muestrea desde el final hacia atrás para que la columna que nunca se pierda sea
    la de la fecha más reciente.
    """
    if matriz.empty or len(matriz.columns) <= maximo:
        return matriz
    paso = -(-len(matriz.columns) // maximo)  # techo: el resultado nunca excede `maximo`
    return matriz.iloc[:, ::-1].iloc[:, ::paso].iloc[:, ::-1]


def percentil_contra_sector(
    panel_historico: pd.DataFrame,
    *,
    columna_valor: str = "prima",
    min_observaciones: int = MIN_OBSERVACIONES_PERCENTIL,
) -> pd.DataFrame:
    """Percentil expandible del emisor contra su propia historia y contra la del sector.

    ``panel_historico`` requiere columnas ``ticker``, ``sector``, ``fecha_dato`` y la
    columna de valor. Ambos percentiles usan ventana expandible (P5).
    """
    if panel_historico.empty:
        return panel_historico

    df = panel_historico.copy().sort_values(["ticker", "fecha_dato"])
    partes = []
    for _ticker, g in df.groupby("ticker", sort=False):
        s = g.set_index("fecha_dato")[columna_valor]
        p = percentil_expandible(s, min_observaciones=min_observaciones)
        g = g.copy()
        g["percentil_propio"] = p.to_numpy()
        partes.append(g)
    df = pd.concat(partes)

    # Prima mediana del sector en cada fecha, y su percentil expandible.
    sector_mediana = (
        df.groupby(["sector", "fecha_dato"])[columna_valor].median().rename("prima_sector")
    )
    df = df.merge(sector_mediana, on=["sector", "fecha_dato"], how="left")

    partes = []
    for sector, g in df.groupby("sector", sort=False):
        serie = g.drop_duplicates("fecha_dato").set_index("fecha_dato")["prima_sector"]
        p = percentil_expandible(serie, min_observaciones=min_observaciones)
        mapa = dict(zip(p.index, p.to_numpy(), strict=False))
        g = g.copy()
        g["percentil_sector"] = pd.to_datetime(g["fecha_dato"]).map(mapa)
        partes.append(g)
        _ = sector
    df = pd.concat(partes)

    df["prima_relativa_al_sector"] = df[columna_valor] - df["prima_sector"]
    return df.sort_values(["sector", "ticker", "fecha_dato"]).reset_index(drop=True)


def mapa_de_calor(
    panel_historico: pd.DataFrame,
    *,
    columna_percentil: str = "percentil_sector",
) -> pd.DataFrame:
    """Matriz sectores × fechas con el percentil de prima. Base del mapa de calor."""
    if panel_historico.empty:
        return pd.DataFrame()
    return (
        panel_historico.pivot_table(
            index="sector", columns="fecha_dato", values=columna_percentil, aggfunc="median"
        )
        .sort_index()
    )


def reloj_de_prima(
    panel_historico: pd.DataFrame,
    *,
    columna_percentil: str = "percentil_sector",
    columna_crecimiento: str = "crecimiento_affo_por_accion_yoy",
) -> pd.DataFrame:
    """Cuadrante percentil de prima × crecimiento del AFFO, por sector y fecha.

    Innovación 3.3.c. Animado en el tiempo muestra dónde ha estado el dinero barato
    y dónde está hoy. Los cuatro cuadrantes:

    * **Barato y creciendo** — donde uno quiere estar.
    * **Barato y encogiendo** — trampa de valor: el mercado suele tener razón.
    * **Caro y creciendo** — se paga por el crecimiento; funciona hasta que deja de crecer.
    * **Caro y encogiendo** — lo peor de ambos mundos.
    """
    if panel_historico.empty:
        return pd.DataFrame()
    cols = [c for c in (columna_percentil, columna_crecimiento) if c in panel_historico.columns]
    if len(cols) < 2:
        return pd.DataFrame()
    df = (
        panel_historico.groupby(["sector", "fecha_dato"])[cols]
        .median()
        .reset_index()
        .dropna()
    )
    df["cuadrante"] = [
        _cuadrante(p, c) for p, c in zip(df[columna_percentil], df[columna_crecimiento], strict=False)
    ]
    return df


def _cuadrante(percentil: float, crecimiento: float) -> str:
    barato = percentil >= 0.5
    creciendo = crecimiento > 0
    if barato and creciendo:
        return "Barato y creciendo"
    if barato and not creciendo:
        return "Barato y encogiendo (trampa de valor)"
    if not barato and creciendo:
        return "Caro y creciendo"
    return "Caro y encogiendo"


def metricas_especificas(sector: str) -> dict[str, str]:
    """Qué mirar en cada sector más allá de las métricas comunes."""
    especificas = {
        "Net Lease": {
            "WALT": "Vida promedio ponderada del contrato. Debajo de 8 años en net lease es corto.",
            "Concentración por inquilino": "Ningún inquilino debería pesar más de 5–7% de la renta.",
            "% grado de inversión": "Proporción de la renta que viene de inquilinos con calificación.",
        },
        "Self Storage": {
            "Renta por pie cuadrado": "Se reprecia mensualmente; es el termómetro más rápido del sector.",
            "Ocupación": "Arriba de 90% en portafolio maduro.",
            "Descuentos promocionales": "Un aumento de promociones anticipa debilidad de renta.",
        },
        "Industrial": {
            "Tasa de recaptura": "Cuánto sube la renta al renovar. Es el motor de crecimiento del sector.",
            "Ocupación": "Arriba de 95% en mercados logísticos sanos.",
        },
        "Oficinas": {
            "Mejoras al inquilino por pie cuadrado": "El costo real de retener un inquilino.",
            "Vencimientos a 3 años": "Concentración de renovaciones es el riesgo principal.",
            "Ocupación física vs contratada": "La brecha revela subarrendamiento y espacio fantasma.",
        },
        "Salud": {
            "Cobertura del operador (EBITDAR/renta)": "Debajo de 1.2x el inquilino está en problemas.",
            "Mezcla triple net vs operativo": "El riesgo cambia por completo entre ambos.",
        },
        "Data Centers": {
            "MW contratados vs disponibles": "La capacidad eléctrica es el cuello de botella real.",
            "Concentración de hiperescaladores": "Pocos inquilinos enormes con poder de negociación.",
        },
    }
    base = especificas.get(sector, {})
    piso, techo = CAPEX_ESPERADO_POR_SECTOR.get(sector, (0.05, 0.20))
    base["CapEx recurrente / NOI"] = (
        f"Rango esperado {piso:.0%}–{techo:.0%} del NOI para {sector}. "
        "Fuera de rango exige explicación del emisor."
    )
    return base
