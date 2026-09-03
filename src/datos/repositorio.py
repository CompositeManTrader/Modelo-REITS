"""Repositorio de datos con corte point-in-time obligatorio.

Toda lectura de hechos exige una fecha de corte (``asof``). No hay una versión
"sin corte" de estas funciones: si el llamador pudiera omitir la fecha, tarde o
temprano la omitiría y el modelo leería el futuro. Ese es exactamente el error
que P1 prohíbe.

Regla de selección
------------------
Para cada celda conceptual ``(ticker, concepto, periodo_tipo, fecha_dato)`` se
devuelve la fila con la ``fecha_publicacion`` **más reciente que no exceda el
corte**. Las reexpresiones posteriores existen en la base pero son invisibles
para una consulta con corte anterior.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, create_engine, delete, insert, select, text

from src.config import RUTA_BD, Estado, asegurar_directorios
from src.datos import esquema

Fecha = dt.date | str | pd.Timestamp


class RegistroRechazado(ValueError):
    """El esquema rechazó una fila por violar una restricción de integridad.

    La más común es ``fecha_publicacion >= fecha_dato``: un filing no puede
    reportar cifras realizadas de un periodo que aún no termina. Cuando salta, casi
    siempre significa que el parser tomó una tabla de guía por una de resultados.
    """


# --------------------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------------------


def a_fecha(valor: Fecha) -> dt.date:
    """Normaliza cualquier representación razonable de fecha a ``datetime.date``."""
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    ts = pd.Timestamp(valor)
    if pd.isna(ts):
        raise ValueError(f"Fecha inválida: {valor!r}")
    return ts.date()


def exigir_corte(asof: Fecha | None) -> dt.date:
    """Convierte y valida el corte. Falla ruidosamente si falta.

    No existe un valor por omisión deliberadamente: un corte implícito de "hoy"
    es la puerta de entrada al lookahead cuando el código se reutiliza en un
    backtest.
    """
    if asof is None:
        raise ValueError(
            "Falta la fecha de corte (asof). Toda consulta de hechos es point-in-time (P1)."
        )
    return a_fecha(asof)


def crear_motor(ruta: Path | str | None = None, *, crear: bool = True) -> Engine:
    """Devuelve el motor SQLAlchemy sobre SQLite (migrable a Postgres sin cambios de API)."""
    if ruta is None:
        asegurar_directorios()
        ruta = RUTA_BD
    url = ruta if str(ruta).startswith("postgresql") else f"sqlite:///{ruta}"
    motor = create_engine(url, future=True)
    if crear:
        esquema.metadata.create_all(motor)
        with motor.begin() as cx:
            if motor.dialect.name == "sqlite":
                cx.execute(text("PRAGMA foreign_keys=ON"))
    return motor


# --------------------------------------------------------------------------------------
# Repositorio
# --------------------------------------------------------------------------------------


class Repositorio:
    """Acceso a la base. Escrituras append-only para las tablas de hechos."""

    def __init__(self, motor: Engine | None = None, ruta: Path | str | None = None):
        self.motor = motor if motor is not None else crear_motor(ruta)

    # ---------------------------------------------------------------- catálogo

    def registrar_emisores(self, emisores: Iterable) -> int:
        """Inserta o actualiza el catálogo de emisores. No es una tabla de hechos."""
        filas = [
            {
                "ticker": e.ticker,
                "cik": e.cik,
                "nombre": e.nombre,
                "sector": e.sector,
                "nota": getattr(e, "nota", "") or None,
            }
            for e in emisores
        ]
        if not filas:
            return 0
        with self.motor.begin() as cx:
            for f in filas:
                cx.execute(delete(esquema.emisores).where(esquema.emisores.c.ticker == f["ticker"]))
            cx.execute(insert(esquema.emisores), filas)
        return len(filas)

    def emisores(self) -> pd.DataFrame:
        with self.motor.connect() as cx:
            return pd.read_sql(select(esquema.emisores), cx)

    def sector_de(self, ticker: str) -> str | None:
        df = self.emisores()
        fila = df.loc[df["ticker"] == ticker, "sector"]
        return None if fila.empty else str(fila.iloc[0])

    # ---------------------------------------------------------------- escritura

    def guardar_hechos(self, filas: Sequence[dict]) -> int:
        """Inserta hechos. Append-only: una reexpresión es una fila nueva, no un UPDATE.

        Los duplicados exactos (misma llave point-in-time) se ignoran de forma
        idempotente para que la ingesta pueda re-correrse sin ensuciar la base.
        """
        return self._insertar(esquema.hechos, filas, fechas=("fecha_dato", "fecha_publicacion", "periodo_inicio"))

    def guardar_guias(self, filas: Sequence[dict]) -> int:
        return self._insertar(esquema.guias, filas, fechas=("fecha_publicacion",))

    def guardar_precios(self, filas: Sequence[dict]) -> int:
        return self._insertar(esquema.precios, filas, fechas=("fecha_dato", "fecha_publicacion"))

    def guardar_anclas(self, filas: Sequence[dict]) -> int:
        return self._insertar(esquema.anclas_precio, filas, fechas=("fecha_dato",))

    def guardar_dividendos(self, filas: Sequence[dict]) -> int:
        return self._insertar(
            esquema.dividendos,
            filas,
            fechas=(
                "fecha_declaracion",
                "fecha_ex",
                "fecha_registro",
                "fecha_pago",
                "fecha_publicacion",
            ),
        )

    def guardar_tasas(self, filas: Sequence[dict]) -> int:
        return self._insertar(esquema.tasas, filas, fechas=("fecha_dato", "fecha_publicacion"))

    def guardar_conciliacion(self, filas: Sequence[dict]) -> int:
        return self._insertar(
            esquema.conciliacion, filas, fechas=("fecha_dato", "fecha_publicacion")
        )

    def guardar_transacciones(self, filas: Sequence[dict]) -> int:
        return self._insertar(esquema.transacciones, filas, fechas=("fecha",))

    def guardar_inmuebles(self, filas: Sequence[dict]) -> int:
        return self._insertar(esquema.inmuebles, filas, fechas=("fecha_compra",))

    def guardar_decisiones(self, filas: Sequence[dict]) -> int:
        return self._insertar(esquema.decisiones, filas, fechas=("fecha",))

    def registrar_bitacora(self, evento: str, detalle: str = "", ticker: str | None = None) -> None:
        with self.motor.begin() as cx:
            cx.execute(
                insert(esquema.bitacora),
                [
                    {
                        "momento": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                        "ticker": ticker,
                        "evento": evento,
                        "detalle": detalle,
                    }
                ],
            )

    def _insertar(self, tabla, filas: Sequence[dict], fechas: tuple[str, ...] = ()) -> int:
        if not filas:
            return 0
        columnas = set(tabla.c.keys())
        limpias = []
        for f in filas:
            fila = {k: v for k, v in f.items() if k in columnas}
            for campo in fechas:
                if fila.get(campo) is not None:
                    fila[campo] = a_fecha(fila[campo])
            limpias.append(fila)
        insertadas = 0
        with self.motor.begin() as cx:
            for fila in limpias:
                try:
                    cx.execute(insert(tabla), [fila])
                    insertadas += 1
                except Exception as exc:  # noqa: BLE001 - duplicado idempotente
                    mensaje = str(exc)
                    if "UNIQUE constraint" in mensaje or "duplicate key" in mensaje.lower():
                        continue
                    if "CHECK constraint" in mensaje:
                        # El esquema rechazó la fila. Es la barrera funcionando, no un
                        # fallo del programa: se convierte en un error legible que el
                        # llamador puede registrar sin tumbar toda la ingesta.
                        raise RegistroRechazado(
                            f"El esquema rechazó la fila {fila!r}: {mensaje.splitlines()[0]}"
                        ) from exc
                    raise
        return insertadas

    # ---------------------------------------------------------------- lectura PIT

    def hechos(
        self,
        *,
        asof: Fecha,
        tickers: Sequence[str] | str | None = None,
        conceptos: Sequence[str] | str | None = None,
        periodo_tipo: str | None = None,
        desde: Fecha | None = None,
        incluir_sospechosos: bool = False,
        vigentes: bool = True,
    ) -> pd.DataFrame:
        """Hechos observables al corte ``asof``.

        Con ``vigentes=True`` (por omisión) se devuelve una fila por celda
        conceptual: la última publicada al corte. Con ``vigentes=False`` se
        devuelven todas las versiones visibles, útil para auditar reexpresiones.
        """
        corte = exigir_corte(asof)
        q = select(esquema.hechos).where(esquema.hechos.c.fecha_publicacion <= corte)
        q = _filtro_in(q, esquema.hechos.c.ticker, tickers)
        q = _filtro_in(q, esquema.hechos.c.concepto, conceptos)
        if periodo_tipo is not None:
            q = q.where(esquema.hechos.c.periodo_tipo == periodo_tipo)
        if desde is not None:
            q = q.where(esquema.hechos.c.fecha_dato >= a_fecha(desde))
        if not incluir_sospechosos:
            q = q.where(esquema.hechos.c.estado == Estado.VALIDO)
        with self.motor.connect() as cx:
            df = pd.read_sql(q, cx, parse_dates=["fecha_dato", "fecha_publicacion", "periodo_inicio"])
        if df.empty:
            return df
        if vigentes:
            df = _ultima_version(df, ["ticker", "concepto", "periodo_tipo", "fecha_dato"])
        return df.sort_values(["ticker", "concepto", "fecha_dato"]).reset_index(drop=True)

    def serie(
        self,
        ticker: str,
        concepto: str,
        *,
        asof: Fecha,
        periodo_tipo: str = "Q",
        incluir_sospechosos: bool = False,
    ) -> pd.Series:
        """Serie temporal de un concepto, indexada por ``fecha_dato``, vigente al corte."""
        df = self.hechos(
            asof=asof,
            tickers=ticker,
            conceptos=concepto,
            periodo_tipo=periodo_tipo,
            incluir_sospechosos=incluir_sospechosos,
        )
        if df.empty:
            return pd.Series(dtype="float64", name=concepto)
        s = df.set_index("fecha_dato")["valor"].astype(float)
        s.name = concepto
        return s.sort_index()

    def panel(
        self,
        ticker: str,
        conceptos: Sequence[str],
        *,
        asof: Fecha,
        periodo_tipo: str = "Q",
    ) -> pd.DataFrame:
        """Panel ancho ``fecha_dato x concepto`` vigente al corte."""
        df = self.hechos(
            asof=asof, tickers=ticker, conceptos=list(conceptos), periodo_tipo=periodo_tipo
        )
        if df.empty:
            return pd.DataFrame(columns=list(conceptos))
        ancho = df.pivot_table(
            index="fecha_dato", columns="concepto", values="valor", aggfunc="last"
        )
        for c in conceptos:
            if c not in ancho.columns:
                ancho[c] = pd.NA
        return ancho[list(conceptos)].sort_index()

    def guia_vigente(
        self, ticker: str, anio: int, *, asof: Fecha, metrica: str = "affo_por_accion"
    ) -> dict | None:
        """Guía observable al corte. La revisión de agosto no existe para marzo."""
        corte = exigir_corte(asof)
        q = (
            select(esquema.guias)
            .where(esquema.guias.c.ticker == ticker)
            .where(esquema.guias.c.metrica == metrica)
            .where(esquema.guias.c.anio_guia == anio)
            .where(esquema.guias.c.fecha_publicacion <= corte)
            .order_by(esquema.guias.c.fecha_publicacion.desc())
            .limit(1)
        )
        with self.motor.connect() as cx:
            fila = cx.execute(q).mappings().first()
        if fila is None:
            return None
        d = dict(fila)
        d["punto_medio"] = (d["valor_min"] + d["valor_max"]) / 2.0
        return d

    def historial_guias(self, ticker: str, anio: int, *, asof: Fecha) -> pd.DataFrame:
        """Todas las revisiones de guía visibles al corte, para mostrar cómo se movió."""
        corte = exigir_corte(asof)
        q = (
            select(esquema.guias)
            .where(esquema.guias.c.ticker == ticker)
            .where(esquema.guias.c.anio_guia == anio)
            .where(esquema.guias.c.fecha_publicacion <= corte)
            .order_by(esquema.guias.c.fecha_publicacion)
        )
        with self.motor.connect() as cx:
            return pd.read_sql(q, cx, parse_dates=["fecha_publicacion"])

    def precios(
        self,
        tickers: Sequence[str] | str,
        *,
        asof: Fecha,
        desde: Fecha | None = None,
        solo_validos: bool = True,
    ) -> pd.DataFrame:
        """Precios de cierre **sin ajustar** observables al corte (P2)."""
        corte = exigir_corte(asof)
        q = select(esquema.precios).where(esquema.precios.c.fecha_dato <= corte)
        q = _filtro_in(q, esquema.precios.c.ticker, tickers)
        if desde is not None:
            q = q.where(esquema.precios.c.fecha_dato >= a_fecha(desde))
        if solo_validos:
            q = q.where(esquema.precios.c.estado == Estado.VALIDO)
        with self.motor.connect() as cx:
            df = pd.read_sql(q, cx, parse_dates=["fecha_dato", "fecha_publicacion"])
        if df.empty:
            return df
        # Preferencia: observado > reconstruido. Se ordena para que 'last' tome el mejor.
        prioridad = {"observado": 2, "reconstruido_div_yield": 1, "demo": 0}
        df["_prio"] = df["metodo"].map(prioridad).fillna(0)
        df = (
            df.sort_values(["ticker", "fecha_dato", "_prio"])
            .drop_duplicates(["ticker", "fecha_dato"], keep="last")
            .drop(columns="_prio")
        )
        return df.sort_values(["ticker", "fecha_dato"]).reset_index(drop=True)

    def serie_precio(self, ticker: str, *, asof: Fecha, desde: Fecha | None = None) -> pd.Series:
        df = self.precios(ticker, asof=asof, desde=desde)
        if df.empty:
            return pd.Series(dtype="float64", name="cierre_crudo")
        s = df.set_index("fecha_dato")["cierre_crudo"].astype(float)
        s.name = "cierre_crudo"
        return s.sort_index()

    def anclas(self, ticker: str) -> pd.DataFrame:
        q = select(esquema.anclas_precio).where(esquema.anclas_precio.c.ticker == ticker)
        with self.motor.connect() as cx:
            return pd.read_sql(q, cx, parse_dates=["fecha_dato"])

    def dividendos(
        self, tickers: Sequence[str] | str, *, asof: Fecha, desde: Fecha | None = None
    ) -> pd.DataFrame:
        corte = exigir_corte(asof)
        q = select(esquema.dividendos).where(esquema.dividendos.c.fecha_publicacion <= corte)
        q = _filtro_in(q, esquema.dividendos.c.ticker, tickers)
        if desde is not None:
            q = q.where(esquema.dividendos.c.fecha_ex >= a_fecha(desde))
        with self.motor.connect() as cx:
            df = pd.read_sql(
                q,
                cx,
                parse_dates=[
                    "fecha_declaracion",
                    "fecha_ex",
                    "fecha_registro",
                    "fecha_pago",
                    "fecha_publicacion",
                ],
            )
        if df.empty:
            return df
        return df.sort_values(["ticker", "fecha_ex"]).reset_index(drop=True)

    def tasa(self, serie: str, *, asof: Fecha, desde: Fecha | None = None) -> pd.Series:
        """Serie macro observable al corte. Las tasas también se publican con rezago."""
        corte = exigir_corte(asof)
        q = (
            select(esquema.tasas)
            .where(esquema.tasas.c.serie == serie)
            .where(esquema.tasas.c.fecha_publicacion <= corte)
        )
        if desde is not None:
            q = q.where(esquema.tasas.c.fecha_dato >= a_fecha(desde))
        with self.motor.connect() as cx:
            df = pd.read_sql(q, cx, parse_dates=["fecha_dato", "fecha_publicacion"])
        if df.empty:
            return pd.Series(dtype="float64", name=serie)
        df = _ultima_version(df, ["serie", "fecha_dato"])
        s = df.set_index("fecha_dato")["valor"].astype(float).sort_index()
        s.name = serie
        return s

    def valor_tasa(self, serie: str, *, asof: Fecha, desde: Fecha | None = None) -> float | None:
        """Último valor de la serie observable al corte."""
        s = self.tasa(serie, asof=asof, desde=desde)
        s = s[s.index <= pd.Timestamp(exigir_corte(asof))]
        return None if s.empty else float(s.iloc[-1])

    def conciliacion(
        self, ticker: str, fecha_dato: Fecha, *, asof: Fecha, periodo_tipo: str = "Q"
    ) -> pd.DataFrame:
        """Cascada reportada para un periodo, en la versión vigente al corte."""
        corte = exigir_corte(asof)
        q = (
            select(esquema.conciliacion)
            .where(esquema.conciliacion.c.ticker == ticker)
            .where(esquema.conciliacion.c.fecha_dato == a_fecha(fecha_dato))
            .where(esquema.conciliacion.c.periodo_tipo == periodo_tipo)
            .where(esquema.conciliacion.c.fecha_publicacion <= corte)
        )
        with self.motor.connect() as cx:
            df = pd.read_sql(q, cx, parse_dates=["fecha_dato", "fecha_publicacion"])
        if df.empty:
            return df
        ultima = df["fecha_publicacion"].max()
        return (
            df[df["fecha_publicacion"] == ultima].sort_values("orden").reset_index(drop=True)
        )

    # ---------------------------------------------------------------- portafolio

    def transacciones(self, *, asof: Fecha | None = None) -> pd.DataFrame:
        q = select(esquema.transacciones)
        if asof is not None:
            q = q.where(esquema.transacciones.c.fecha <= a_fecha(asof))
        with self.motor.connect() as cx:
            df = pd.read_sql(q, cx, parse_dates=["fecha"])
        return df.sort_values(["fecha", "id"]).reset_index(drop=True) if not df.empty else df

    def inmuebles(self) -> pd.DataFrame:
        with self.motor.connect() as cx:
            return pd.read_sql(select(esquema.inmuebles), cx, parse_dates=["fecha_compra"])

    def decisiones(self) -> pd.DataFrame:
        with self.motor.connect() as cx:
            return pd.read_sql(select(esquema.decisiones), cx, parse_dates=["fecha"])

    def bitacora(self, limite: int = 50) -> pd.DataFrame:
        q = select(esquema.bitacora).order_by(esquema.bitacora.c.id.desc()).limit(limite)
        with self.motor.connect() as cx:
            return pd.read_sql(q, cx)

    def borrar_transacciones(self, ids: Sequence[int]) -> int:
        if not ids:
            return 0
        with self.motor.begin() as cx:
            r = cx.execute(
                delete(esquema.transacciones).where(esquema.transacciones.c.id.in_(list(ids)))
            )
        return r.rowcount or 0

    # ---------------------------------------------------------------- auditoría

    def revisiones(self, ticker: str, concepto: str, fecha_dato: Fecha) -> pd.DataFrame:
        """Todas las versiones publicadas de una misma celda. Sirve para ver el rezago."""
        q = (
            select(esquema.hechos)
            .where(esquema.hechos.c.ticker == ticker)
            .where(esquema.hechos.c.concepto == concepto)
            .where(esquema.hechos.c.fecha_dato == a_fecha(fecha_dato))
            .order_by(esquema.hechos.c.fecha_publicacion)
        )
        with self.motor.connect() as cx:
            return pd.read_sql(q, cx, parse_dates=["fecha_dato", "fecha_publicacion"])

    def fechas_publicacion(self, ticker: str | None = None) -> list[dt.date]:
        """Fechas en que entró información nueva. Útil para recorrer un backtest."""
        q = select(esquema.hechos.c.fecha_publicacion).distinct()
        if ticker:
            q = q.where(esquema.hechos.c.ticker == ticker)
        with self.motor.connect() as cx:
            filas = cx.execute(q.order_by(esquema.hechos.c.fecha_publicacion)).scalars().all()
        return [a_fecha(f) for f in filas]


# --------------------------------------------------------------------------------------
# Auxiliares
# --------------------------------------------------------------------------------------


def _filtro_in(q, columna, valores):
    if valores is None:
        return q
    if isinstance(valores, str):
        return q.where(columna == valores)
    valores = list(valores)
    return q.where(columna.in_(valores)) if valores else q


def _ultima_version(df: pd.DataFrame, llave: list[str]) -> pd.DataFrame:
    """Se queda con la fila publicada más recientemente por celda conceptual."""
    return (
        df.sort_values([*llave, "fecha_publicacion", "id"])
        .drop_duplicates(llave, keep="last")
        .reset_index(drop=True)
    )
