"""Esquema de la base con versionado point-in-time.

P1 — Point-in-time o nada
=========================
Toda tabla de hechos lleva DOS fechas:

* ``fecha_dato``          — a qué periodo se refiere el número (fin del trimestre, día del precio).
* ``fecha_publicacion``   — cuándo ese número se volvió público y observable.

Ninguna consulta histórica puede devolver un valor cuya ``fecha_publicacion`` sea
posterior a la fecha consultada. Cada revisión de un dato es un **registro nuevo**;
jamás se sobrescribe. Por eso las llaves únicas incluyen ``fecha_publicacion``: dos
versiones del mismo hecho conviven y la consulta elige la vigente a la fecha de corte.

El AFFO se revisa, se reexpresa y se publica con rezago; la guía cambia a media marcha.
Un modelo que use la guía de agosto para fechas de marzo está usando información del
futuro. El esquema hace ese error imposible de cometer por descuido.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()

# --------------------------------------------------------------------------------------
# Catálogo de emisores
# --------------------------------------------------------------------------------------

emisores = Table(
    "emisores",
    metadata,
    Column("ticker", String(12), primary_key=True),
    Column("cik", String(10), nullable=False),
    Column("nombre", String(200), nullable=False),
    Column("sector", String(60), nullable=False),
    Column("subsector", String(60)),
    Column("moneda", String(3), nullable=False, server_default="USD"),
    Column("nota", Text),
    Column("activo", Boolean, nullable=False, server_default="1"),
    Index("ix_emisores_cik", "cik"),
)

# --------------------------------------------------------------------------------------
# Hechos fundamentales — el núcleo point-in-time
# --------------------------------------------------------------------------------------
#
# Un "hecho" es (emisor, concepto, periodo) observado en una fecha de publicación.
# La misma celda conceptual puede tener N versiones: la original y cada reexpresión.

hechos = Table(
    "hechos",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", String(12), nullable=False),
    # Concepto normalizado: 'affo', 'affo_por_accion', 'ffo', 'noi', 'utilidad_neta', ...
    Column("concepto", String(60), nullable=False),
    # 'Q' | 'H1' | 'FY' | 'TTM' | 'PUNTUAL' (para saldos de balance)
    Column("periodo_tipo", String(8), nullable=False),
    Column("periodo_inicio", Date),
    # fecha_dato = fin del periodo al que se refiere el número
    Column("fecha_dato", Date, nullable=False),
    # fecha_publicacion = cuándo se volvió observable. NUNCA se infiere: viene del filing.
    Column("fecha_publicacion", Date, nullable=False),
    Column("valor", Float, nullable=False),
    Column("unidad", String(20), nullable=False, server_default="USD"),
    Column("fuente", String(30), nullable=False),
    Column("es_primario", Boolean, nullable=False, server_default="0"),
    Column("url_filing", Text),
    Column("accession", String(30)),
    Column("estado", String(15), nullable=False, server_default="valido"),
    Column("nota_validacion", Text),
    # Distinguir revisiones: mismo hecho, distinta publicación => filas distintas.
    UniqueConstraint(
        "ticker",
        "concepto",
        "periodo_tipo",
        "fecha_dato",
        "fecha_publicacion",
        "fuente",
        name="uq_hecho_pit",
    ),
    CheckConstraint(
        "fecha_publicacion >= fecha_dato", name="ck_publicacion_no_anterior_al_dato"
    ),
    Index("ix_hechos_consulta", "ticker", "concepto", "fecha_publicacion"),
    Index("ix_hechos_periodo", "ticker", "concepto", "fecha_dato"),
)

# --------------------------------------------------------------------------------------
# Guía de la administración — cada revisión es un registro nuevo (P1)
# --------------------------------------------------------------------------------------
#
# Ejemplo real: en febrero de 2026 Realty Income guiaba 4.38–4.42 dólares de AFFO por
# acción y en agosto la subió a 4.44–4.45. Ambas filas conviven. Una consulta con corte
# en marzo devuelve la de febrero.

guias = Table(
    "guias",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", String(12), nullable=False),
    Column("metrica", String(60), nullable=False, server_default="affo_por_accion"),
    Column("anio_guia", Integer, nullable=False),
    Column("valor_min", Float, nullable=False),
    Column("valor_max", Float, nullable=False),
    Column("fecha_publicacion", Date, nullable=False),
    Column("fuente", String(30), nullable=False),
    Column("url_filing", Text),
    UniqueConstraint(
        "ticker", "metrica", "anio_guia", "fecha_publicacion", name="uq_guia_pit"
    ),
    CheckConstraint("valor_max >= valor_min", name="ck_guia_rango"),
    Index("ix_guias_consulta", "ticker", "anio_guia", "fecha_publicacion"),
)

# --------------------------------------------------------------------------------------
# Precios — P2: el precio para calcular yields debe ser SIN AJUSTAR
# --------------------------------------------------------------------------------------
#
# Los proveedores gratuitos entregan precio ajustado por dividendos y escisiones.
# Un yield calculado sobre precio ajustado infla sistemáticamente todos los rendimientos
# históricos. La columna que usa el motor de valuación es 'cierre_crudo'.

precios = Table(
    "precios",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", String(12), nullable=False),
    Column("fecha_dato", Date, nullable=False),
    Column("fecha_publicacion", Date, nullable=False),
    Column("cierre_crudo", Float, nullable=False),
    Column("cierre_ajustado", Float),  # se guarda solo para diagnóstico, jamás para yields
    Column("volumen", Float),
    Column("fuente", String(30), nullable=False),
    # 'observado' | 'reconstruido_div_yield' | 'demo'
    Column("metodo", String(40), nullable=False, server_default="observado"),
    Column("estado", String(15), nullable=False, server_default="valido"),
    Column("error_ancla", Float),  # error relativo máximo contra anclas verificadas
    UniqueConstraint("ticker", "fecha_dato", "fuente", "metodo", name="uq_precio"),
    CheckConstraint("cierre_crudo > 0", name="ck_precio_positivo"),
    Index("ix_precios_consulta", "ticker", "fecha_dato"),
)

# Cierres conocidos y verificados contra los que se valida cualquier serie (P2).
anclas_precio = Table(
    "anclas_precio",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", String(12), nullable=False),
    Column("fecha_dato", Date, nullable=False),
    Column("cierre_crudo", Float, nullable=False),
    Column("fuente", Text, nullable=False),
    UniqueConstraint("ticker", "fecha_dato", name="uq_ancla"),
)

# --------------------------------------------------------------------------------------
# Dividendos y calendario de distribuciones
# --------------------------------------------------------------------------------------

dividendos = Table(
    "dividendos",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", String(12), nullable=False),
    Column("fecha_declaracion", Date),
    Column("fecha_ex", Date, nullable=False),
    Column("fecha_registro", Date),
    Column("fecha_pago", Date),
    Column("monto", Float, nullable=False),
    Column("frecuencia", String(15), nullable=False, server_default="mensual"),
    Column("fuente", String(30), nullable=False),
    Column("fecha_publicacion", Date, nullable=False),
    UniqueConstraint("ticker", "fecha_ex", "fuente", name="uq_dividendo"),
    Index("ix_dividendos_consulta", "ticker", "fecha_ex"),
)

# --------------------------------------------------------------------------------------
# Tasas y macro
# --------------------------------------------------------------------------------------

tasas = Table(
    "tasas",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("serie", String(20), nullable=False),
    Column("fecha_dato", Date, nullable=False),
    Column("fecha_publicacion", Date, nullable=False),
    Column("valor", Float, nullable=False),
    Column("unidad", String(20), nullable=False, server_default="decimal"),
    Column("fuente", String(30), nullable=False),
    UniqueConstraint("serie", "fecha_dato", "fuente", name="uq_tasa"),
    Index("ix_tasas_consulta", "serie", "fecha_dato"),
)

# --------------------------------------------------------------------------------------
# Conciliación del AFFO — la cascada línea por línea, tal como la reporta el emisor
# --------------------------------------------------------------------------------------

conciliacion = Table(
    "conciliacion",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", String(12), nullable=False),
    Column("periodo_tipo", String(8), nullable=False),
    Column("fecha_dato", Date, nullable=False),
    Column("fecha_publicacion", Date, nullable=False),
    Column("orden", Integer, nullable=False),
    Column("linea", String(60), nullable=False),  # clave normalizada
    Column("etiqueta", Text, nullable=False),  # texto tal cual lo reporta el emisor
    Column("valor", Float, nullable=False),
    Column("signo", Integer, nullable=False, server_default="1"),
    Column("fuente", String(30), nullable=False),
    Column("url_filing", Text),
    UniqueConstraint(
        "ticker", "periodo_tipo", "fecha_dato", "fecha_publicacion", "linea", name="uq_concilia"
    ),
    Index("ix_concilia_consulta", "ticker", "fecha_dato", "fecha_publicacion"),
)

# --------------------------------------------------------------------------------------
# Portafolio del usuario
# --------------------------------------------------------------------------------------

transacciones = Table(
    "transacciones",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("fecha", Date, nullable=False),
    Column("ticker", String(12), nullable=False),
    # 'compra' | 'venta' | 'dividendo' | 'aportacion' | 'retiro' | 'split'
    Column("tipo", String(20), nullable=False),
    Column("cantidad", Float, nullable=False, server_default="0"),
    Column("precio", Float, nullable=False, server_default="0"),
    Column("comision", Float, nullable=False, server_default="0"),
    Column("tipo_cambio", Float, nullable=False, server_default="1"),
    Column("retencion_eeuu", Float, nullable=False, server_default="0"),
    Column("nota", Text),
    Index("ix_tx_fecha", "fecha"),
    Index("ix_tx_ticker", "ticker", "fecha"),
)

# Inmuebles reales del usuario (innovación 3.3.f)
inmuebles = Table(
    "inmuebles",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("nombre", String(120), nullable=False),
    Column("tipo", String(30), nullable=False, server_default="departamento"),
    Column("fecha_compra", Date, nullable=False),
    Column("precio_compra", Float, nullable=False),
    Column("costos_entrada", Float, nullable=False, server_default="0"),
    Column("renta_mensual", Float, nullable=False),
    Column("mantenimiento_mensual", Float, nullable=False, server_default="0"),
    Column("predial_anual", Float, nullable=False, server_default="0"),
    Column("seguro_anual", Float, nullable=False, server_default="0"),
    Column("saldo_hipoteca", Float, nullable=False, server_default="0"),
    Column("tasa_hipoteca", Float, nullable=False, server_default="0"),
    Column("mensualidad_hipoteca", Float, nullable=False, server_default="0"),
    Column("valor_actual", Float),
    Column("nota", Text),
)

# Detector de sesgos (innovación 3.3.e): qué dijo el sistema y qué hizo el usuario.
decisiones = Table(
    "decisiones",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("fecha", Date, nullable=False),
    Column("ticker", String(12), nullable=False),
    Column("senal_sistema", String(30), nullable=False),
    Column("accion_usuario", String(30), nullable=False),
    Column("monto", Float, nullable=False, server_default="0"),
    Column("precio_referencia", Float),
    Column("nota", Text),
    Index("ix_decisiones_fecha", "fecha"),
)

# Bitácora de ingesta: qué entró, cuándo, y qué cambió respecto al trimestre anterior.
bitacora = Table(
    "bitacora",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("momento", String(30), nullable=False),
    Column("ticker", String(12)),
    Column("evento", String(60), nullable=False),
    Column("detalle", Text),
    Column("leido", Boolean, nullable=False, server_default="0"),
    Index("ix_bitacora_momento", "momento"),
)

TABLAS_HECHOS_PIT = (hechos, guias, precios, dividendos, tasas, conciliacion)
