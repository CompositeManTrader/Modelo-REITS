"""Libro de transacciones: costo promedio, posiciones y ganancia realizada.

El libro es la fuente de verdad del portafolio. Toda métrica de desempeño se
deriva de aquí, no de un saldo capturado a mano, porque el saldo no distingue
entre "subió" y "metí más dinero" — que es justo la diferencia entre TWR y TIR.

Convención de costo: **promedio ponderado**. Es lo que aplica en la práctica
mexicana vía SIC y evita la ilusión de escoger qué lote se vende.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import pandas as pd


class TipoTx:
    COMPRA = "compra"
    VENTA = "venta"
    DIVIDENDO = "dividendo"
    APORTACION = "aportacion"
    RETIRO = "retiro"
    SPLIT = "split"


TIPOS_VALIDOS = frozenset(
    {TipoTx.COMPRA, TipoTx.VENTA, TipoTx.DIVIDENDO, TipoTx.APORTACION, TipoTx.RETIRO, TipoTx.SPLIT}
)


@dataclass
class Posicion:
    """Estado de una posición: títulos, costo promedio y ganancia realizada."""

    ticker: str
    cantidad: float = 0.0
    costo_total: float = 0.0
    ganancia_realizada: float = 0.0
    dividendos_cobrados: float = 0.0
    retencion_pagada: float = 0.0

    @property
    def costo_promedio(self) -> float:
        return self.costo_total / self.cantidad if self.cantidad > 0 else 0.0

    def valor(self, precio: float) -> float:
        return self.cantidad * precio

    def ganancia_no_realizada(self, precio: float) -> float:
        return self.valor(precio) - self.costo_total

    def ganancia_no_realizada_pct(self, precio: float) -> float | None:
        if self.costo_total <= 0:
            return None
        return self.ganancia_no_realizada(precio) / self.costo_total

    def yield_sobre_costo(self, dividendo_anual_por_accion: float) -> float | None:
        """Rendimiento sobre el costo, no sobre el precio de mercado.

        Es la métrica que le importa a quien vive de rentas: cuánto paga hoy el
        capital que efectivamente puso. No sirve para decidir compras nuevas — para
        eso está el yield de mercado — pero sí para medir si el plan va cumpliendo.
        """
        cp = self.costo_promedio
        return dividendo_anual_por_accion / cp if cp > 0 else None


@dataclass
class EstadoPortafolio:
    fecha: dt.date
    posiciones: dict[str, Posicion] = field(default_factory=dict)
    efectivo: float = 0.0
    aportado: float = 0.0
    retirado: float = 0.0
    comisiones: float = 0.0

    def valor_total(self, precios: dict[str, float]) -> float:
        return self.efectivo + sum(
            p.valor(precios.get(t, 0.0)) for t, p in self.posiciones.items()
        )

    def tabla(self, precios: dict[str, float]) -> pd.DataFrame:
        filas = []
        for t, p in sorted(self.posiciones.items()):
            if abs(p.cantidad) < 1e-9:
                continue
            precio = precios.get(t)
            filas.append(
                {
                    "ticker": t,
                    "cantidad": p.cantidad,
                    "costo_promedio": p.costo_promedio,
                    "costo_total": p.costo_total,
                    "precio": precio,
                    "valor_mercado": p.valor(precio) if precio else None,
                    "ganancia_no_realizada": p.ganancia_no_realizada(precio) if precio else None,
                    "ganancia_no_realizada_pct": p.ganancia_no_realizada_pct(precio) if precio else None,
                    "ganancia_realizada": p.ganancia_realizada,
                    "dividendos_cobrados": p.dividendos_cobrados,
                    "retencion_pagada": p.retencion_pagada,
                }
            )
        df = pd.DataFrame(filas)
        if not df.empty and df["valor_mercado"].notna().any():
            total = df["valor_mercado"].sum()
            df["peso"] = df["valor_mercado"] / total if total else None
        return df


def procesar_libro(transacciones: pd.DataFrame, *, hasta: dt.date | None = None) -> EstadoPortafolio:
    """Reproduce el libro y devuelve el estado del portafolio.

    Procesa en orden cronológico. Las ventas se descuentan a costo promedio y la
    diferencia se acumula como ganancia realizada. Un split multiplica la cantidad
    sin tocar el costo total, que es lo correcto: no hay evento fiscal.
    """
    estado = EstadoPortafolio(fecha=hasta or dt.date.today())
    if transacciones is None or transacciones.empty:
        return estado

    tx = transacciones.copy()
    tx["fecha"] = pd.to_datetime(tx["fecha"])
    if hasta is not None:
        tx = tx[tx["fecha"] <= pd.Timestamp(hasta)]
    tx = tx.sort_values(["fecha", "id"] if "id" in tx.columns else ["fecha"])

    for _, r in tx.iterrows():
        tipo = str(r["tipo"]).lower()
        ticker = str(r.get("ticker") or "").upper()
        cantidad = float(r.get("cantidad") or 0.0)
        precio = float(r.get("precio") or 0.0)
        comision = float(r.get("comision") or 0.0)
        retencion = float(r.get("retencion_eeuu") or 0.0)
        estado.comisiones += comision

        if tipo == TipoTx.APORTACION:
            estado.efectivo += precio if precio else cantidad
            estado.aportado += precio if precio else cantidad
            continue
        if tipo == TipoTx.RETIRO:
            monto = precio if precio else cantidad
            estado.efectivo -= monto
            estado.retirado += monto
            continue

        pos = estado.posiciones.setdefault(ticker, Posicion(ticker))

        if tipo == TipoTx.COMPRA:
            bruto = cantidad * precio + comision
            pos.cantidad += cantidad
            pos.costo_total += bruto
            estado.efectivo -= bruto
        elif tipo == TipoTx.VENTA:
            if cantidad > pos.cantidad + 1e-9:
                raise ValueError(
                    f"Venta de {cantidad} títulos de {ticker} con solo {pos.cantidad} en posición."
                )
            costo_unitario = pos.costo_promedio
            neto = cantidad * precio - comision
            pos.ganancia_realizada += neto - cantidad * costo_unitario
            pos.costo_total -= cantidad * costo_unitario
            pos.cantidad -= cantidad
            estado.efectivo += neto
            if abs(pos.cantidad) < 1e-9:
                pos.cantidad = 0.0
                pos.costo_total = 0.0
        elif tipo == TipoTx.DIVIDENDO:
            # 'precio' guarda el monto por acción; 'cantidad' los títulos que lo cobraron.
            bruto = cantidad * precio if cantidad else precio
            neto = bruto - retencion
            pos.dividendos_cobrados += bruto
            pos.retencion_pagada += retencion
            estado.efectivo += neto
        elif tipo == TipoTx.SPLIT:
            # 'precio' guarda la razón del split (2 = dos por una).
            razon = precio if precio > 0 else 1.0
            pos.cantidad *= razon
        else:
            raise ValueError(f"Tipo de transacción desconocido: {tipo}")

    return estado


def flujos_de_caja(transacciones: pd.DataFrame, *, en_pesos: bool = False) -> pd.Series:
    """Flujos del inversionista para la TIR: negativos al meter dinero, positivos al sacarlo.

    Se toma la perspectiva del bolsillo del usuario: una compra es salida de caja,
    un dividendo cobrado es entrada, una venta es entrada. Con ``en_pesos=True`` se
    convierte al tipo de cambio de cada operación, que es lo relevante para alguien
    cuyo gasto es en pesos.
    """
    if transacciones is None or transacciones.empty:
        return pd.Series(dtype="float64")

    tx = transacciones.copy()
    tx["fecha"] = pd.to_datetime(tx["fecha"])
    fx = tx["tipo_cambio"].fillna(1.0) if "tipo_cambio" in tx.columns else 1.0

    montos = []
    for i, (_, r) in enumerate(tx.iterrows()):
        tipo = str(r["tipo"]).lower()
        cantidad = float(r.get("cantidad") or 0.0)
        precio = float(r.get("precio") or 0.0)
        comision = float(r.get("comision") or 0.0)
        retencion = float(r.get("retencion_eeuu") or 0.0)
        if tipo == TipoTx.COMPRA:
            m = -(cantidad * precio + comision)
        elif tipo == TipoTx.VENTA:
            m = cantidad * precio - comision
        elif tipo == TipoTx.DIVIDENDO:
            m = (cantidad * precio if cantidad else precio) - retencion
        elif tipo == TipoTx.APORTACION:
            m = 0.0  # el desembolso se registra en la compra, no se cuenta dos veces
        elif tipo == TipoTx.RETIRO:
            m = 0.0
        else:
            m = 0.0
        if en_pesos:
            tc = float(fx.iloc[i]) if hasattr(fx, "iloc") else float(fx)
            m *= tc
        montos.append(m)

    s = pd.Series(montos, index=tx["fecha"].to_numpy())
    return s.groupby(level=0).sum().sort_index()


def valor_por_fecha(
    transacciones: pd.DataFrame,
    precios: pd.DataFrame,
    *,
    fechas: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    """Serie del valor del portafolio, con flujos externos por fecha.

    ``precios`` es un panel ancho ``fecha × ticker``. La salida trae ``valor``
    (marca a mercado de las posiciones) y ``flujo_externo`` (dinero que entró o
    salió del portafolio ese día), que es exactamente lo que necesita el TWR.
    """
    if transacciones is None or transacciones.empty or precios.empty:
        return pd.DataFrame(columns=["valor", "flujo_externo"])

    px = precios.copy()
    px.index = pd.to_datetime(px.index)
    px = px.sort_index()
    fechas = pd.DatetimeIndex(fechas) if fechas is not None else px.index

    tx = transacciones.copy()
    tx["fecha"] = pd.to_datetime(tx["fecha"])

    filas = []
    for f in fechas:
        estado = procesar_libro(tx, hasta=f.date())
        precios_dia = {}
        for t in estado.posiciones:
            if t in px.columns:
                serie = px[t]
                previos = serie[serie.index <= f].dropna()
                if not previos.empty:
                    precios_dia[t] = float(previos.iloc[-1])
        del_dia = tx[tx["fecha"] == f]
        flujo = 0.0
        for _, r in del_dia.iterrows():
            tipo = str(r["tipo"]).lower()
            if tipo == TipoTx.COMPRA:
                flujo += float(r.get("cantidad") or 0) * float(r.get("precio") or 0) + float(
                    r.get("comision") or 0
                )
            elif tipo == TipoTx.VENTA:
                flujo -= float(r.get("cantidad") or 0) * float(r.get("precio") or 0) - float(
                    r.get("comision") or 0
                )
        filas.append(
            {
                "fecha": f,
                "valor": sum(p.valor(precios_dia.get(t, 0.0)) for t, p in estado.posiciones.items()),
                "flujo_externo": flujo,
            }
        )
    return pd.DataFrame(filas).set_index("fecha")


def validar_transacciones(df: pd.DataFrame) -> list[str]:
    """Revisa el libro antes de guardarlo. Lista vacía significa aprobado."""
    problemas: list[str] = []
    if df is None or df.empty:
        return problemas
    requeridas = {"fecha", "ticker", "tipo", "cantidad", "precio"}
    faltantes = requeridas - set(df.columns)
    if faltantes:
        problemas.append(f"Faltan columnas obligatorias: {', '.join(sorted(faltantes))}.")
        return problemas
    tipos_malos = set(df["tipo"].str.lower()) - TIPOS_VALIDOS
    if tipos_malos:
        problemas.append(f"Tipos de transacción no reconocidos: {', '.join(sorted(tipos_malos))}.")
    if (df["cantidad"] < 0).any():
        problemas.append("Hay cantidades negativas: usa el tipo 'venta' en lugar de cantidad negativa.")
    if (df["precio"] < 0).any():
        problemas.append("Hay precios negativos.")
    try:
        procesar_libro(df)
    except ValueError as exc:
        problemas.append(str(exc))
    return problemas
