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

DISPERSION_SECTORIAL = pd.DataFrame(
    [
        {"sector": "Data Centers", "anio": 2023, "rendimiento": 0.252, "lugar": "mejor del año"},
        {"sector": "Data Centers", "anio": 2025, "rendimiento": -0.142, "lugar": "peor del año"},
        {"sector": "Self Storage", "anio": "1994–2024", "rendimiento": 0.173, "lugar": "anualizado"},
        {"sector": "S&P 500", "anio": "1994–2024", "rendimiento": 0.101, "lugar": "anualizado"},
    ]
)


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


def percentil_contra_sector(
    panel_historico: pd.DataFrame,
    *,
    columna_valor: str = "prima",
    min_observaciones: int = 12,
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
