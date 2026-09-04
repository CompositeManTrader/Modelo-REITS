"""Series de precio SIN ajustar y su reconstrucción.

P2 — El precio para calcular yields debe ser SIN AJUSTAR
========================================================
Los proveedores gratuitos entregan precio ajustado por dividendos y escisiones.
Macrotrends daba 64.03 dólares para el cierre de 2021 de Realty Income; el cierre
real fue 71.56. Un yield calculado sobre precio ajustado infla sistemáticamente
todos los rendimientos históricos y hace que el modelo "compre" en fechas inventadas.

El sesgo no es aleatorio: crece hacia atrás en el tiempo, proporcional al dividendo
acumulado. En un REIT que paga 5% anual, veinte años de ajuste distorsionan el
precio histórico en más de la mitad.

Método de respaldo validado
---------------------------
Si no hay fuente confiable de precio crudo, se reconstruye::

    precio = dividendo TTM ÷ rendimiento por dividendo TTM

Validado con error de 0.25% contra el cierre real de 2021-12-31 y 0.01% contra
2023-12-29. Toda serie reconstruida se marca como ``RECONSTRUIDO``, nunca se
presenta como observada.

Sobre la fuente de mercado
--------------------------
Stooq era la fuente original y **dejó de servir**: ahora responde con una página
que exige verificación por JavaScript en vez del CSV, así que devuelve HTTP 200
con HTML. Cualquier parser ingenuo lo toma por datos. No se reintenta ni se
reemplaza por un navegador headless: se cambió de proveedor.

El proveedor actual entrega en la misma respuesta el cierre **sin ajustar** y el
**ajustado**, lo que habilita una verificación aritmética por emisor que no
depende de anclas capturadas a mano — ver ``prueba_coherencia_ajuste``.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd
import requests

from src.config import (
    MIN_ANCLAS_PRECIO,
    TOLERANCIA_ANCLA_PRECIO,
    TOLERANCIA_COHERENCIA_AJUSTE,
    Estado,
    Fuente,
)


class ErrorPrecios(RuntimeError):
    pass


# --------------------------------------------------------------------------------------
# Descarga
# --------------------------------------------------------------------------------------

URL_HISTORICO = "https://stockanalysis.com/api/symbol/s/{ticker}/history"
URL_DIVIDENDOS = "https://stockanalysis.com/api/symbol/s/{ticker}/dividend"

# Se identifica el cliente en vez de fingir un navegador. El proveedor responde
# igual con o sin encabezado; suplantar a Chrome no compraría nada y volvería el
# tráfico indistinguible del de una persona, que no es lo que somos.
ENCABEZADOS = {"User-Agent": "Modelo-REITS/1.0 (plataforma de valuacion de REITs)"}


def _pedir_json(url: str, *, timeout: int, params: dict | None = None) -> dict:
    r = requests.get(url, headers=ENCABEZADOS, params=params, timeout=timeout)
    if r.status_code != 200:
        raise ErrorPrecios(f"{url} respondió HTTP {r.status_code}")
    texto = r.text.lstrip()
    if texto.startswith("<"):
        # Es el síntoma de un muro de verificación, no de un dato faltante.
        raise ErrorPrecios(f"{url} devolvió HTML en vez de JSON (¿muro de verificación?)")
    try:
        cuerpo = r.json()
    except ValueError as exc:
        raise ErrorPrecios(f"{url} devolvió una respuesta ilegible: {exc}") from exc
    if cuerpo.get("status") != 200:
        raise ErrorPrecios(f"{url} reportó estado {cuerpo.get('status')}")
    return cuerpo


def descargar_historico(ticker: str, *, rango: str = "5Y", timeout: int = 30) -> pd.DataFrame:
    """Descarga el histórico diario con cierre crudo y ajustado.

    El campo ``c`` es el cierre **sin ajustar por dividendos** —el precio al que
    efectivamente cotizó el papel— y ``a`` el ajustado. Se guardan los dos: el
    crudo para calcular yields (P2) y el ajustado únicamente como diagnóstico,
    porque su cociente contra el crudo es lo que permite verificar que la fuente
    no nos está entregando una serie ajustada disfrazada de cruda.
    """
    cuerpo = _pedir_json(
        URL_HISTORICO.format(ticker=ticker.upper()),
        timeout=timeout,
        params={"range": rango, "period": "Daily"},
    )
    filas = cuerpo.get("data") or []
    if not filas:
        raise ErrorPrecios(f"Sin histórico de precios para {ticker}")

    df = pd.DataFrame(filas)
    faltantes = {"t", "c"} - set(df.columns)
    if faltantes:
        raise ErrorPrecios(f"Respuesta de precios de {ticker} sin columnas {sorted(faltantes)}")

    salida = pd.DataFrame(
        {
            "ticker": ticker.upper(),
            "fecha_dato": pd.to_datetime(df["t"]).dt.date,
            "cierre_crudo": pd.to_numeric(df["c"], errors="coerce"),
            "cierre_ajustado": pd.to_numeric(df.get("a"), errors="coerce"),
            "volumen": pd.to_numeric(df.get("v"), errors="coerce"),
            "fuente": Fuente.MERCADO,
            "metodo": "observado",
        }
    )
    # El precio de cierre se publica el mismo día: no hay rezago que modelar.
    salida["fecha_publicacion"] = salida["fecha_dato"]
    salida = salida.dropna(subset=["cierre_crudo"])
    salida = salida[salida["cierre_crudo"] > 0]
    return salida.sort_values("fecha_dato").reset_index(drop=True)


def _a_fecha(valor) -> dt.date | None:
    """Convierte el texto de una fecha del proveedor; ``n/a`` y vacíos dan ``None``."""
    if valor is None or str(valor).strip().lower() in {"", "n/a", "none", "-"}:
        return None
    fecha = pd.to_datetime(valor, errors="coerce")
    return None if pd.isna(fecha) else fecha.date()


def descargar_dividendos(ticker: str, *, timeout: int = 30) -> pd.DataFrame:
    """Descarga el historial de dividendos con fecha ex, de registro y de pago.

    La fecha **ex** es la que importa para el yield: es la primera sesión en que
    el papel cotiza sin derecho al dividendo, y por eso es la que aparece en la
    llave única de la tabla. La de pago llega semanas después y usarla correría
    todo el cálculo.
    """
    cuerpo = _pedir_json(URL_DIVIDENDOS.format(ticker=ticker.upper()), timeout=timeout)
    historial = (cuerpo.get("data") or {}).get("history") or []
    if not historial:
        raise ErrorPrecios(f"Sin historial de dividendos para {ticker}")

    filas = []
    for reg in historial:
        fecha_ex = _a_fecha(reg.get("dt"))
        monto = str(reg.get("amt", "")).replace("$", "").replace(",", "").strip()
        try:
            monto = float(monto)
        except ValueError:
            continue
        if fecha_ex is None or monto <= 0:
            continue
        filas.append(
            {
                "ticker": ticker.upper(),
                "fecha_ex": fecha_ex,
                "fecha_declaracion": _a_fecha(reg.get("dec")),
                "fecha_registro": _a_fecha(reg.get("record")),
                "fecha_pago": _a_fecha(reg.get("pay")),
                "monto": monto,
                "fuente": Fuente.MERCADO,
                # El dividendo se conoce al declararse; si el proveedor no da la
                # fecha de declaración, la ex es la cota superior defendible.
                "fecha_publicacion": _a_fecha(reg.get("dec")) or fecha_ex,
            }
        )
    if not filas:
        raise ErrorPrecios(f"El historial de dividendos de {ticker} no trajo montos legibles")
    return pd.DataFrame(filas).sort_values("fecha_ex").reset_index(drop=True)


# --------------------------------------------------------------------------------------
# Reconstrucción (método de respaldo validado)
# --------------------------------------------------------------------------------------


def reconstruir_precio(dividendo_ttm: float, rendimiento_ttm: float) -> float:
    """``precio = dividendo TTM ÷ rendimiento TTM``.

    Ambos insumos deben referirse a la **misma** fecha de corte. Mezclar el
    dividendo de un año con el yield de otro produce un precio plausible y falso,
    que es la peor clase de error.
    """
    if rendimiento_ttm is None or rendimiento_ttm <= 0:
        raise ErrorPrecios("El rendimiento TTM debe ser positivo para reconstruir el precio.")
    if dividendo_ttm is None or dividendo_ttm <= 0:
        raise ErrorPrecios("El dividendo TTM debe ser positivo para reconstruir el precio.")
    return float(dividendo_ttm) / float(rendimiento_ttm)


def dividendo_ttm(dividendos: pd.DataFrame, fecha: dt.date, columna_fecha: str = "fecha_ex") -> float:
    """Suma de dividendos con fecha ex en los 12 meses previos (inclusive)."""
    if dividendos.empty:
        return 0.0
    f = pd.Timestamp(fecha)
    ventana = dividendos[
        (pd.to_datetime(dividendos[columna_fecha]) <= f)
        & (pd.to_datetime(dividendos[columna_fecha]) > f - pd.DateOffset(years=1))
    ]
    return float(ventana["monto"].sum())


def serie_reconstruida(
    ticker: str,
    dividendos: pd.DataFrame,
    rendimientos_ttm: pd.Series,
) -> pd.DataFrame:
    """Reconstruye una serie de precios desde dividendo TTM y rendimiento TTM.

    ``rendimientos_ttm`` es una serie indexada por fecha con el rendimiento por
    dividendo en decimal. Toda fila sale marcada como reconstruida.
    """
    filas = []
    for fecha, rend in rendimientos_ttm.dropna().items():
        f = pd.Timestamp(fecha).date()
        div = dividendo_ttm(dividendos, f)
        if div <= 0 or rend <= 0:
            continue
        filas.append(
            {
                "ticker": ticker.upper(),
                "fecha_dato": f,
                "fecha_publicacion": f,
                "cierre_crudo": reconstruir_precio(div, float(rend)),
                "fuente": Fuente.RECONSTRUIDO,
                "metodo": "reconstruido_div_yield",
            }
        )
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# Validación contra anclas (prueba obligatoria 4)
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoAnclas:
    """Veredicto de validar una serie contra cierres verificables."""

    aprobada: bool
    n_anclas: int
    error_max: float
    detalle: pd.DataFrame
    motivo: str = ""

    def como_texto(self) -> str:
        if self.aprobada:
            return (
                f"Serie aprobada: {self.n_anclas} anclas, error máximo {self.error_max:.2%} "
                f"(tolerancia {TOLERANCIA_ANCLA_PRECIO:.0%})."
            )
        return f"Serie RECHAZADA: {self.motivo}"


def validar_contra_anclas(
    serie: pd.Series,
    anclas: pd.DataFrame,
    *,
    tolerancia: float = TOLERANCIA_ANCLA_PRECIO,
    min_anclas: int = MIN_ANCLAS_PRECIO,
) -> ResultadoAnclas:
    """Compara la serie contra cierres conocidos. Si el error supera la tolerancia, se rechaza.

    Esta es la barrera que separa una serie utilizable de una ajustada por
    dividendos disfrazada de cruda. No es opcional: una serie sin anclas
    suficientes no entra a la base.
    """
    if serie.empty:
        return ResultadoAnclas(False, 0, float("nan"), pd.DataFrame(), "La serie está vacía.")
    if anclas.empty:
        return ResultadoAnclas(
            False, 0, float("nan"), pd.DataFrame(), "No hay anclas de precio registradas."
        )

    s = serie.copy()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()

    filas = []
    for _, a in anclas.iterrows():
        f = pd.Timestamp(a["fecha_dato"])
        previos = s[s.index <= f]
        if previos.empty:
            continue
        # Se exige coincidencia en el mismo día hábil, no un valor cercano cualquiera.
        if (f - previos.index[-1]).days > 5:
            continue
        obtenido = float(previos.iloc[-1])
        esperado = float(a["cierre_crudo"])
        error = abs(obtenido - esperado) / esperado
        filas.append(
            {
                "fecha_dato": f.date(),
                "esperado": esperado,
                "obtenido": obtenido,
                "error_relativo": error,
                "dentro_de_tolerancia": error <= tolerancia,
                "fuente_ancla": a.get("fuente", ""),
            }
        )

    detalle = pd.DataFrame(filas)
    if detalle.empty:
        return ResultadoAnclas(
            False, 0, float("nan"), detalle, "Ninguna ancla cae dentro del rango de la serie."
        )

    n = len(detalle)
    error_max = float(detalle["error_relativo"].max())
    if n < min_anclas:
        return ResultadoAnclas(
            False,
            n,
            error_max,
            detalle,
            f"Solo {n} anclas verificables; se exigen al menos {min_anclas} (P2).",
        )
    if error_max > tolerancia:
        peor = detalle.loc[detalle["error_relativo"].idxmax()]
        return ResultadoAnclas(
            False,
            n,
            error_max,
            detalle,
            (
                f"Error de {error_max:.2%} en {peor['fecha_dato']} "
                f"(esperado {peor['esperado']:.2f}, obtenido {peor['obtenido']:.2f}). "
                "Casi seguro es una serie ajustada por dividendos, no cruda."
            ),
        )
    return ResultadoAnclas(True, n, error_max, detalle)


def marcar_estado(df_precios: pd.DataFrame, resultado: ResultadoAnclas) -> pd.DataFrame:
    """Estampa el veredicto de anclas en cada fila antes de persistir."""
    df = df_precios.copy()
    df["estado"] = Estado.VALIDO if resultado.aprobada else Estado.RECHAZADO
    df["error_ancla"] = resultado.error_max
    return df


# --------------------------------------------------------------------------------------
# Coherencia del ajuste (verificación por emisor, sin anclas capturadas a mano)
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoCoherencia:
    """Veredicto de la identidad que liga el cierre crudo, el ajustado y los dividendos.

    ``verificable`` y ``coherente`` son cosas distintas y el sistema no las mezcla:
    no poder comprobar algo no es lo mismo que comprobar que está mal.

    ``distribucion_no_listada`` marca el caso en que la serie ajustada refleja
    MÁS reparto del que explican los dividendos que conocemos. Eso no acusa a la
    columna cruda —al contrario, confirma que está sin ajustar—; señala que hubo
    una escisión o un dividendo extraordinario fuera del historial.
    """

    verificable: bool
    coherente: bool
    n_fechas: int
    error_max: float
    detalle: pd.DataFrame
    motivo: str = ""
    distribucion_no_listada: bool = False

    def como_texto(self) -> str:
        if not self.verificable:
            return f"Coherencia NO VERIFICABLE: {self.motivo}"
        if self.distribucion_no_listada:
            return f"Cierre crudo confirmado, con reserva: {self.motivo}"
        if self.coherente:
            return (
                f"Cierre crudo confirmado: la identidad del ajuste cuadra en "
                f"{self.n_fechas} fechas, error máximo {self.error_max:.2%}."
            )
        return f"Cierre crudo NO confirmado: {self.motivo}"


def prueba_coherencia_ajuste(
    precios: pd.DataFrame,
    dividendos: pd.DataFrame,
    *,
    tolerancia: float = TOLERANCIA_COHERENCIA_AJUSTE,
    min_fechas: int = 3,
) -> ResultadoCoherencia:
    """Verifica que la columna cruda sea de verdad cruda, usando la aritmética del ajuste.

    Si ``c`` es el cierre sin ajustar y ``a`` el ajustado por dividendos, entonces
    para cualquier fecha *t*::

        a_t / c_t  =  Π (1 − dividendo_i / cierre_i)   sobre los dividendos con ex > t

    La identidad es exacta por construcción del ajuste. Si el proveedor nos
    entregara la serie ya ajustada en la columna ``c``, el cociente sería 1 en
    todas partes y el producto no: la prueba lo detecta sin necesidad de conocer
    ningún cierre verificado de antemano.

    Es la contraparte por emisor de ``validar_contra_anclas``, que solo puede
    aplicarse donde hay anclas capturadas a mano. Ampliar las anclas es trabajo de
    analista; esto se puede correr sobre los diez emisores del universo.
    """
    vacio = pd.DataFrame()
    if precios.empty or "cierre_ajustado" not in precios.columns:
        return ResultadoCoherencia(
            False, False, 0, float("nan"), vacio, "La serie no trae cierre ajustado."
        )

    p = precios.dropna(subset=["cierre_crudo", "cierre_ajustado"]).copy()
    if p.empty:
        return ResultadoCoherencia(
            False, False, 0, float("nan"), vacio, "No hay filas con crudo y ajustado a la vez."
        )
    p["fecha_dato"] = pd.to_datetime(p["fecha_dato"])
    p = p.sort_values("fecha_dato").set_index("fecha_dato")

    if dividendos.empty:
        return ResultadoCoherencia(
            False, False, 0, float("nan"), vacio, "No hay dividendos con qué contrastar."
        )
    d = dividendos.dropna(subset=["fecha_ex", "monto"]).copy()
    d["fecha_ex"] = pd.to_datetime(d["fecha_ex"])
    d = d.sort_values("fecha_ex")

    # Un dividendo ya declarado con fecha ex futura aparece en el historial pero la
    # serie ajustada todavía no lo descuenta. Incluirlo desplaza el factor teórico
    # de TODAS las fechas por la misma proporción —la firma es una desviación
    # constante— y hace que la serie parezca poco ajustada cuando el error es
    # nuestro. Solo cuentan los dividendos que ya pasaron por su fecha ex.
    ultima_sesion = p.index.max()
    d = d[d["fecha_ex"] <= ultima_sesion]
    if d.empty:
        return ResultadoCoherencia(
            False, False, 0, float("nan"), vacio,
            "Ningún dividendo del historial tiene fecha ex dentro de la serie de precios.",
        )

    # Solo se evalúan fechas a partir del primer dividendo conocido. Antes de ese
    # punto faltarían factores del producto y el desajuste diría más de nuestro
    # historial de dividendos que de la serie de precios.
    primero = d["fecha_ex"].min()
    ultimo = d["fecha_ex"].max()
    evaluables = p.index[(p.index >= primero) & (p.index < ultimo)]
    if len(evaluables) < min_fechas:
        return ResultadoCoherencia(
            False,
            False,
            len(evaluables),
            float("nan"),
            vacio,
            f"Solo {len(evaluables)} fechas caen dentro del historial de dividendos; "
            f"se necesitan {min_fechas}.",
        )

    # Se muestrean fechas repartidas a lo largo del traslape en vez de tomar las
    # primeras: un sesgo de ajuste crece hacia atrás, así que interesa medirlo en
    # los dos extremos y en medio.
    n_muestras = max(min_fechas, min(8, len(evaluables)))
    posiciones = [round(i * (len(evaluables) - 1) / (n_muestras - 1)) for i in range(n_muestras)]
    fechas = sorted({evaluables[i] for i in posiciones})

    filas = []
    for t in fechas:
        fila = p.loc[t]
        crudo = float(fila["cierre_crudo"])
        ajustado = float(fila["cierre_ajustado"])
        if crudo <= 0:
            continue
        posteriores = d[d["fecha_ex"] > t]
        factor = 1.0
        for _, div in posteriores.iterrows():
            previos = p.index[p.index < div["fecha_ex"]]
            if len(previos) == 0:
                continue
            cierre_previo = float(p.loc[previos[-1], "cierre_crudo"])
            if cierre_previo > 0:
                factor *= 1.0 - float(div["monto"]) / cierre_previo
        observado = ajustado / crudo
        desviacion = (observado - factor) / factor if factor > 0 else float("inf")
        filas.append(
            {
                "fecha_dato": t.date(),
                "cociente_observado": observado,
                "cociente_teorico": factor,
                # El SIGNO es lo informativo, no la magnitud: ver el veredicto abajo.
                "desviacion_relativa": desviacion,
                "error_relativo": abs(desviacion),
                "n_dividendos": int(len(posteriores)),
            }
        )

    detalle = pd.DataFrame(filas)
    if detalle.empty:
        return ResultadoCoherencia(
            False, False, 0, float("nan"), detalle, "Ninguna fecha resultó evaluable."
        )

    error_max = float(detalle["error_relativo"].max())

    # El signo de la desviación separa dos causas que no se deben confundir.
    #
    # Cociente MAYOR al teórico: la serie ajustada se parece demasiado a la cruda,
    # es decir, hay MENOS ajuste del que los dividendos obligan. En el extremo, si
    # el proveedor nos diera la serie ya ajustada en la columna cruda, el cociente
    # sería 1.00 en todas partes. Esto sí acusa a la columna cruda — es P2.
    #
    # Cociente MENOR al teórico: hay MÁS ajuste del que explican los dividendos que
    # conocemos. Eso no puede venir de una serie cruda contaminada; viene de un
    # reparto que no está en el historial: una escisión o un dividendo
    # extraordinario. Realty Income escindió Orion en 2021 y W. P. Carey escindió
    # NLOP en 2023, y ambas aparecen exactamente así. La columna cruda queda
    # confirmada; lo que queda incompleto es nuestro historial de repartos.
    exceso = detalle[detalle["desviacion_relativa"] > tolerancia]
    if not exceso.empty:
        peor = exceso.loc[exceso["desviacion_relativa"].idxmax()]
        return ResultadoCoherencia(
            True,
            False,
            len(detalle),
            error_max,
            detalle,
            (
                f"En {peor['fecha_dato']} el cociente ajustado/crudo es "
                f"{peor['cociente_observado']:.4f} cuando la aritmética del dividendo "
                f"exige a lo más {peor['cociente_teorico']:.4f}. Hay menos ajuste del "
                "que los dividendos obligan: la columna cruda no se comporta como cruda."
            ),
        )

    faltante = detalle[detalle["desviacion_relativa"] < -tolerancia]
    if not faltante.empty:
        peor = faltante.loc[faltante["desviacion_relativa"].idxmin()]
        return ResultadoCoherencia(
            True,
            True,
            len(detalle),
            error_max,
            detalle,
            (
                f"desde {peor['fecha_dato']} la serie ajustada descuenta "
                f"{-peor['desviacion_relativa']:.2%} más de lo que explican los "
                "dividendos conocidos. Es la firma de una escisión o un dividendo "
                "extraordinario fuera del historial. El cierre crudo sirve para "
                "yields; el rendimiento total de ese periodo quedaría subestimado."
            ),
            distribucion_no_listada=True,
        )

    return ResultadoCoherencia(True, True, len(detalle), error_max, detalle)


# --------------------------------------------------------------------------------------
# Anclas conocidas y verificadas
# --------------------------------------------------------------------------------------
#
# Cierres de mercado verificados manualmente contra el reporte anual del emisor y
# contra el cierre publicado por la bolsa. Sirven de piedra de toque para cualquier
# serie que entre al sistema. Ampliar esta lista es trabajo de analista, no de código.

ANCLAS_VERIFICADAS: tuple[dict, ...] = (
    {
        "ticker": "O",
        "fecha_dato": dt.date(2021, 12, 31),
        "cierre_crudo": 71.56,
        "fuente": "Cierre NYSE 2021-12-31 (contraste con el 64.03 ajustado de Macrotrends)",
    },
    {
        "ticker": "O",
        "fecha_dato": dt.date(2023, 12, 29),
        "cierre_crudo": 57.42,
        "fuente": "Cierre NYSE 2023-12-29",
    },
    {
        "ticker": "O",
        "fecha_dato": dt.date(2022, 12, 30),
        "cierre_crudo": 63.43,
        "fuente": "Cierre NYSE 2022-12-30",
    },
)
