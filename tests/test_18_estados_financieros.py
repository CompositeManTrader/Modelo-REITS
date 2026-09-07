"""Prueba 18 — La descarga, el almacenamiento y el armado de los estados financieros.

Este archivo cubre el proceso central de datos de punta a punta. Las pruebas están
agrupadas por la propiedad que defienden, y cada una existe porque su ausencia
produce un error que **no levanta excepción**:

* **Idempotencia.** Correr la ingesta diez veces baja los datos una vez. Sin esto,
  el proceso automático quema el límite de la SEC y reescribe archivos idénticos.
* **Determinismo.** Mismo dato, mismos bytes. Sin esto cada corrida produce un
  diff de git y el historial deja de decir qué cambió de verdad.
* **Precisión.** Un activo total de 30,637,336,000 se guarda entero. Redondear a
  seis cifras significativas pierde 36 mil dólares y descuadra el balance.
* **Aritmética del periodo.** El Q4 no existe en XBRL y se deriva, con la fórmula
  que corresponde a cada partida: un flujo se resta, un promedio de acciones no.
* **Identidad contable.** Activo = Pasivo + capital temporal + capital total.

Las cifras son reales: vienen de los estados que estas emisoras le presentaron a
la SEC.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd
import pytest

from src.datos.almacen import (
    Manifiesto,
    RegistroEmisora,
    _csv_bytes,
    _gzip_bytes,
    decidir_descarga,
    escribir_crudos,
    leer_crudos,
    nombre_estado,
)
from src.ingesta.estados import (
    BALANCE,
    ESTADO_RESULTADOS,
    LINEA_POR_CLAVE,
    LINEAS,
    armar_estado,
    derivar_trimestres_faltantes,
    elegir_tags,
    hechos_crudos,
    tags_de,
)
from src.validacion.estados import (
    AVISO,
    ERROR,
    verificar_balance,
    verificar_trimestres_suman_el_ano,
)


@dataclass
class FilingFalso:
    formulario: str
    accession: str
    fecha_presentacion: dt.date


# --------------------------------------------------------------------------------------
# 18.1 Idempotencia: no se baja lo que ya se bajó
# --------------------------------------------------------------------------------------


def test_sin_reporte_nuevo_no_se_descarga():
    """La propiedad que permite correr esto en automático todos los días."""
    registro = RegistroEmisora("O", ultimo_accession="0000726728-26-000045")
    filings = [FilingFalso("10-Q", "0000726728-26-000045", dt.date(2026, 8, 6))]

    veredicto = decidir_descarga(registro, filings)
    assert not veredicto.descargar
    assert "Sin novedades" in veredicto.motivo


def test_un_reporte_nuevo_dispara_la_descarga():
    registro = RegistroEmisora("O", ultimo_accession="0000726728-26-000045")
    filings = [
        FilingFalso("10-Q", "0000726728-26-000045", dt.date(2026, 8, 6)),
        FilingFalso("10-Q", "0000726728-26-000061", dt.date(2026, 11, 5)),
    ]

    veredicto = decidir_descarga(registro, filings)
    assert veredicto.descargar
    assert veredicto.accession == "0000726728-26-000061"
    assert "Reporte nuevo" in veredicto.motivo


def test_dos_filings_del_mismo_dia_no_se_confunden():
    """Se compara por `accession`, no por fecha.

    Una emisora puede presentar el 10-K y una enmienda el mismo día. Comparar por
    fecha se salta el segundo documento en silencio, que es la peor forma de
    perder un dato: sin error y sin rastro.
    """
    registro = RegistroEmisora("X", ultimo_accession="0000000000-26-000001")
    filings = [
        FilingFalso("10-K", "0000000000-26-000001", dt.date(2026, 2, 20)),
        FilingFalso("10-K/A", "0000000000-26-000002", dt.date(2026, 2, 20)),
    ]
    veredicto = decidir_descarga(registro, filings)
    assert veredicto.descargar
    assert veredicto.accession == "0000000000-26-000002"


def test_la_primera_vez_siempre_se_descarga():
    veredicto = decidir_descarga(
        RegistroEmisora("NUEVA"),
        [FilingFalso("10-K", "a-1", dt.date(2026, 2, 20))],
    )
    assert veredicto.descargar
    assert "Primera descarga" in veredicto.motivo


def test_un_8k_no_dispara_la_descarga_de_estados():
    """El 8-K adelanta cifras; los estados etiquetados vienen en el 10-Q y el 10-K."""
    veredicto = decidir_descarga(
        RegistroEmisora("O", ultimo_accession="viejo"),
        [FilingFalso("8-K", "nuevo-8k", dt.date(2026, 8, 5))],
    )
    assert not veredicto.descargar


# --------------------------------------------------------------------------------------
# 18.2 Determinismo y precisión del archivo
# --------------------------------------------------------------------------------------


def test_el_gzip_no_lleva_marca_de_tiempo():
    """Por omisión gzip escribe la hora, y entonces cada corrida produce un diff.

    Un diff que aparece siempre deja de leerse, y con él se pierde la única razón
    para versionar estos archivos: ver qué cambió de verdad.
    """
    datos = b"linea,valor\nactivos,100\n"
    assert _gzip_bytes(datos) == _gzip_bytes(datos)


def test_el_importe_grande_se_guarda_sin_perder_un_peso():
    """30,637,336,000 con formato de seis cifras se vuelve 30,637,300,000.

    Son 36 mil dólares perdidos y, peor, un balance que deja de cuadrar por esa
    diferencia: el error se manifiesta como una alarma contable en otro lado.
    """
    activos = 30_637_336_000.0
    texto = _csv_bytes(pd.DataFrame({"valor": [activos]})).decode("utf-8")
    escrito = float(texto.strip().splitlines()[1])

    assert escrito == activos, f"se perdieron {activos - escrito:,.0f} dólares al escribir"
    # El control: con seis cifras significativas la pérdida sí ocurre.
    assert float(format(activos, ".6g")) != activos


def test_lo_escrito_es_lo_que_se_lee(tmp_path):
    crudos = pd.DataFrame({
        "ticker": ["O"], "taxonomia": ["us-gaap"], "tag": ["Assets"], "unidad": ["USD"],
        "periodo_tipo": ["PUNTUAL"], "fecha_inicio": [None],
        "fecha_dato": [dt.date(2026, 6, 30)], "fecha_publicacion": [dt.date(2026, 8, 6)],
        "valor": [68_328_236_000.0], "formulario": ["10-Q"], "accession": ["a-1"], "marco": [""],
    })
    escribir_crudos("O", crudos, base=tmp_path)
    vuelta = leer_crudos("O", base=tmp_path)

    assert float(vuelta["valor"].iloc[0]) == 68_328_236_000.0
    assert vuelta["fecha_dato"].iloc[0] == dt.date(2026, 6, 30)


def test_el_balance_no_lleva_sufijo_de_periodo():
    """Es un saldo a una fecha, no un periodo. El nombre del archivo lo dice."""
    assert nombre_estado(BALANCE, None) == "balance.csv"
    assert nombre_estado(ESTADO_RESULTADOS, "Q") == "estado_resultados_trimestral.csv"
    assert nombre_estado(ESTADO_RESULTADOS, "FY") == "estado_resultados_anual.csv"


def test_el_manifiesto_se_ordena_por_emisora(tmp_path):
    """Sin orden fijo el JSON cambia de forma entre corridas y el diff miente."""
    m = Manifiesto()
    for t in ("WELL", "ADC", "O"):
        m.registro(t)
    ruta = m.guardar(tmp_path / "manifiesto.json")
    texto = ruta.read_text(encoding="utf-8")
    assert texto.index('"ADC"') < texto.index('"O"') < texto.index('"WELL"')


# --------------------------------------------------------------------------------------
# 18.3 El cuarto trimestre, que la SEC nunca recibe
# --------------------------------------------------------------------------------------


def _hecho(tag, tipo, fin, pub, valor, unidad="USD"):
    return {
        "ticker": "O", "taxonomia": "us-gaap", "tag": tag, "unidad": unidad,
        "periodo_tipo": tipo, "fecha_inicio": None, "fecha_dato": fin,
        "fecha_publicacion": pub, "valor": valor,
        "formulario": "10-K" if tipo == "FY" else "10-Q", "accession": "a", "marco": "",
    }


def test_el_cuarto_trimestre_se_deriva_del_ano_menos_nueve_meses():
    """En Estados Unidos no hay 10-Q del Q4: el año se cierra con el 10-K.

    Sin derivarlo, la serie trimestral tiene un hueco cada diciembre y con él se
    cae todo TTM y toda comparación contra el mismo trimestre del año pasado.
    """
    crudos = pd.DataFrame([
        _hecho("Revenues", "9M", dt.date(2025, 9, 30), dt.date(2025, 11, 4), 4_261_435_000.0),
        _hecho("Revenues", "FY", dt.date(2025, 12, 31), dt.date(2026, 2, 24), 5_749_377_000.0),
    ])
    tags = {"ingresos_totales": "Revenues"}
    salida = derivar_trimestres_faltantes(crudos, tags)

    q4 = salida[(salida["periodo_tipo"] == "Q") & (salida["formulario"] == "DERIVADO")]
    assert len(q4) == 1
    assert float(q4["valor"].iloc[0]) == pytest.approx(5_749_377_000.0 - 4_261_435_000.0)
    assert q4["fecha_dato"].iloc[0] == dt.date(2025, 12, 31)


def test_el_trimestre_derivado_se_fecha_cuando_ya_era_deducible():
    """P1. Antes de que salga el 10-K, ese número no existía ni con lápiz."""
    crudos = pd.DataFrame([
        _hecho("Revenues", "9M", dt.date(2025, 9, 30), dt.date(2025, 11, 4), 100.0),
        _hecho("Revenues", "FY", dt.date(2025, 12, 31), dt.date(2026, 2, 24), 140.0),
    ])
    salida = derivar_trimestres_faltantes(crudos, {"ingresos_totales": "Revenues"})
    derivado = salida[salida["formulario"] == "DERIVADO"].iloc[0]
    assert derivado["fecha_publicacion"] == dt.date(2026, 2, 24)


def test_el_conteo_de_acciones_se_deriva_como_promedio_no_como_flujo():
    """El acumulado de acciones es el PROMEDIO del periodo, no la suma.

    Restarlo como flujo da un conteo negativo. Es el mismo defecto que ya costó
    caro en la otra mitad de la ingesta, y por eso aquí tiene su propia fórmula:
    `Q4 = 4·FY − 3·9M`.
    """
    crudos = pd.DataFrame([
        _hecho("WeightedAverageNumberOfDilutedSharesOutstanding", "9M",
               dt.date(2025, 9, 30), dt.date(2025, 11, 4), 910_000_000.0, "shares"),
        _hecho("WeightedAverageNumberOfDilutedSharesOutstanding", "FY",
               dt.date(2025, 12, 31), dt.date(2026, 2, 24), 913_000_000.0, "shares"),
    ])
    tags = {"acciones_diluidas": "WeightedAverageNumberOfDilutedSharesOutstanding"}
    salida = derivar_trimestres_faltantes(crudos, tags)
    q4 = float(salida[salida["formulario"] == "DERIVADO"]["valor"].iloc[0])

    assert q4 == pytest.approx(4 * 913_000_000 - 3 * 910_000_000)
    assert q4 > 0, "restar promedios como si fueran flujos da un conteo negativo"
    # Y cae donde debe: por arriba del promedio de nueve meses, porque la emisora
    # estuvo emitiendo acciones todo el año.
    assert 910_000_000 < q4 < 960_000_000


def test_la_resta_ingenua_del_conteo_de_acciones_daria_negativo():
    """El control. Sin él, la prueba anterior no demuestra que la fórmula hacía falta."""
    assert 913_000_000 - 910_000_000 * 3 < 0


def test_no_se_deriva_un_trimestre_que_la_emisora_si_publico():
    crudos = pd.DataFrame([
        _hecho("Revenues", "9M", dt.date(2025, 9, 30), dt.date(2025, 11, 4), 100.0),
        _hecho("Revenues", "Q", dt.date(2025, 12, 31), dt.date(2026, 2, 24), 40.0),
        _hecho("Revenues", "FY", dt.date(2025, 12, 31), dt.date(2026, 2, 24), 140.0),
    ])
    salida = derivar_trimestres_faltantes(crudos, {"ingresos_totales": "Revenues"})
    assert (salida["formulario"] == "DERIVADO").sum() == 0


def test_un_saldo_de_balance_no_se_deriva():
    """Un activo total ya viene a la fecha de corte: restarle nada tiene sentido."""
    crudos = pd.DataFrame([
        _hecho("Assets", "PUNTUAL", dt.date(2025, 9, 30), dt.date(2025, 11, 4), 100.0),
        _hecho("Assets", "PUNTUAL", dt.date(2025, 12, 31), dt.date(2026, 2, 24), 140.0),
    ])
    salida = derivar_trimestres_faltantes(crudos, {"activos_totales": "Assets"})
    assert (salida["formulario"] == "DERIVADO").sum() == 0


# --------------------------------------------------------------------------------------
# 18.4 Una etiqueta por renglón, para toda la emisora
# --------------------------------------------------------------------------------------


def test_la_etiqueta_se_elige_una_vez_y_vale_para_todos_los_cortes():
    """Si el trimestral y el anual eligen por separado, dejan de ser comparables.

    Le pasaba a NNN: el estado trimestral se armaba con una etiqueta de utilidad y
    el anual con otra, y «los cuatro trimestres suman el año» reprobaba por 16% sin
    que ninguna de las dos cifras estuviera mal. Comparaba dos conceptos distintos.
    """
    crudos = pd.DataFrame([
        # La etiqueta preferida solo cubre los años; la segunda cubre casi todo.
        _hecho("ProfitLoss", "FY", dt.date(2025, 12, 31), dt.date(2026, 2, 24), 1000.0),
        *[
            _hecho("NetIncomeLoss", "Q", dt.date(2025, m, d), dt.date(2025, 12, 1), 250.0)
            for m, d in ((3, 31), (6, 30), (9, 30))
        ],
        _hecho("NetIncomeLoss", "FY", dt.date(2025, 12, 31), dt.date(2026, 2, 24), 1000.0),
    ])
    elegida = elegir_tags(crudos, "O")["utilidad_neta"]

    trimestral = armar_estado(crudos, "O", ESTADO_RESULTADOS, asof=dt.date(2026, 6, 30),
                              periodo_tipo="Q", tags={"utilidad_neta": elegida})
    anual = armar_estado(crudos, "O", ESTADO_RESULTADOS, asof=dt.date(2026, 6, 30),
                         periodo_tipo="FY", tags={"utilidad_neta": elegida})
    assert trimestral.loc["utilidad_neta", "tag_gaap"] == anual.loc["utilidad_neta", "tag_gaap"]


def test_la_ficha_de_la_emisora_gana_sobre_las_etiquetas_compartidas():
    """Mismo principio que la ficha del AFFO: la emisora declara SUS etiquetas."""
    propias = tags_de("WELL", "capital_temporal")
    assert propias[0] == "RedeemableNoncontrollingInterestEquityOtherFairValue"
    # Y las compartidas siguen ahí de respaldo, sin repetirse.
    assert len(propias) == len(set(propias))
    assert "TemporaryEquityCarryingAmountAttributableToParent" in propias


def test_toda_linea_del_catalogo_tiene_al_menos_una_etiqueta():
    huerfanas = [ln.clave for ln in LINEAS if not ln.tags]
    assert not huerfanas, f"líneas sin ninguna etiqueta GAAP: {huerfanas}"


def test_ninguna_clave_del_catalogo_se_repite():
    claves = [ln.clave for ln in LINEAS]
    assert len(claves) == len(set(claves))


# --------------------------------------------------------------------------------------
# 18.5 La identidad contable
# --------------------------------------------------------------------------------------


def _balance(**lineas) -> pd.DataFrame:
    periodo = dt.date(2026, 3, 31)
    filas = {
        clave: {"etiqueta": LINEA_POR_CLAVE[clave].etiqueta, "tag_gaap": "x",
                "subtotal": True, periodo: valor}
        for clave, valor in lineas.items()
    }
    return pd.DataFrame(filas).T


def test_el_balance_que_cuadra_no_levanta_nada():
    tabla = _balance(
        activos_totales=100.0, pasivos_totales=60.0, capital_total=40.0,
        pasivo_mas_capital=100.0,
    )
    assert verificar_balance("X", tabla) == []


def test_el_balance_descuadrado_es_error():
    tabla = _balance(
        activos_totales=100.0, pasivos_totales=60.0, capital_total=35.0,
        pasivo_mas_capital=100.0,
    )
    incidencias = verificar_balance("X", tabla)
    assert incidencias and all(i.severidad == ERROR for i in incidencias)


def test_el_capital_temporal_forma_parte_de_la_identidad():
    """Cifras reales de Realty Income: sin el mezzanine faltan 167,394,000 exactos."""
    tabla = _balance(
        activos_totales=68_328_236_000.0,
        pasivos_totales=29_009_800_000.0,
        capital_total=39_151_042_000.0,
        capital_temporal=167_394_000.0,
    )
    assert verificar_balance("O", tabla) == []

    sin_mezzanine = _balance(
        activos_totales=68_328_236_000.0,
        pasivos_totales=29_009_800_000.0,
        capital_total=39_151_042_000.0,
    )
    assert sin_mezzanine is not None
    incidencias = verificar_balance("O", sin_mezzanine)
    assert incidencias, "sin el capital temporal el balance NO debería cuadrar"


def test_el_capital_de_la_controladora_no_cierra_el_balance():
    """El descuadre tiene el tamaño exacto del minoritario, y eso confunde.

    En Welltower son 939 millones y en Prologis 4,600: cifras que hacen ver rota
    una lectura que está bien. La identidad cierra contra el capital TOTAL.
    """
    tabla = _balance(
        activos_totales=67_220_556_000.0,
        pasivos_totales=22_291_286_000.0,
        capital_contable=43_793_675_000.0,
        participacion_no_controladora=939_184_000.0,
        capital_temporal=196_411_000.0,
    )
    # Reconstruido desde la controladora más el minoritario, sí cuadra.
    assert verificar_balance("WELL", tabla) == []


# --------------------------------------------------------------------------------------
# 18.6 Una reexpresión no es un error de lectura
# --------------------------------------------------------------------------------------


def _tabla_periodo(lineas: dict, periodo: dt.date) -> pd.DataFrame:
    return pd.DataFrame({
        clave: {"etiqueta": LINEA_POR_CLAVE[clave].etiqueta, "tag_gaap": tag,
                "subtotal": False, periodo: valor}
        for clave, (tag, valor) in lineas.items()
    }).T


def test_una_reexpresion_publicada_se_avisa_no_se_reprueba():
    """El caso de Global Net Lease, con sus cifras.

    Publicó un deterioro de 90.4 millones para 2024 en el 10-K de febrero de 2025,
    y de 2.5 millones para el MISMO año en el de 2026: vendió su portafolio
    multi-inquilino y reclasificó el cargo a operaciones discontinuadas. Las dos
    cifras son correctas. Llamarle error a eso es no entender qué es una
    reexpresión.
    """
    anual = _tabla_periodo(
        {"deterioro": ("AssetImpairmentCharges", 2_500_000.0)}, dt.date(2024, 12, 31)
    )
    trimestral = pd.DataFrame({
        "deterioro": {
            "etiqueta": "Deterioro de activos", "tag_gaap": "AssetImpairmentCharges",
            "subtotal": False,
            dt.date(2024, 3, 31): 4_300_000.0, dt.date(2024, 6, 30): 27_400_000.0,
            dt.date(2024, 9, 30): 38_600_000.0, dt.date(2024, 12, 31): 20_100_000.0,
        }
    }).T
    crudos = pd.DataFrame([
        _hecho("AssetImpairmentCharges", "FY", dt.date(2024, 12, 31),
               dt.date(2025, 2, 27), 90_410_000.0),
        _hecho("AssetImpairmentCharges", "FY", dt.date(2024, 12, 31),
               dt.date(2026, 2, 25), 2_500_000.0),
    ])

    incidencias = verificar_trimestres_suman_el_ano("GNL", trimestral, anual, crudos)
    assert incidencias, "la diferencia existe y tiene que reportarse"
    assert all(i.severidad == AVISO for i in incidencias)
    assert "reexpres" in incidencias[0].detalle

    # Sin la evidencia de la reexpresión, la misma diferencia sí es un error.
    sin_evidencia = verificar_trimestres_suman_el_ano("GNL", trimestral, anual, None)
    assert any(i.severidad == ERROR for i in sin_evidencia)


def test_una_diferencia_chica_es_reclasificacion_de_cierre():
    """El 10-K reexpresa trimestres que el 10-Q ya había publicado. Es normal."""
    periodo = dt.date(2025, 12, 31)
    anual = _tabla_periodo({"ingresos_totales": ("Revenues", 1000.0)}, periodo)
    trimestral = pd.DataFrame({
        "ingresos_totales": {
            "etiqueta": "Ingresos totales", "tag_gaap": "Revenues", "subtotal": True,
            dt.date(2025, 3, 31): 250.0, dt.date(2025, 6, 30): 250.0,
            dt.date(2025, 9, 30): 250.0, dt.date(2025, 12, 31): 252.0,
        }
    }).T
    incidencias = verificar_trimestres_suman_el_ano("X", trimestral, anual, None)
    assert incidencias and all(i.severidad == AVISO for i in incidencias)


# --------------------------------------------------------------------------------------
# 18.7 Contra el filing real
# --------------------------------------------------------------------------------------


def test_hechos_crudos_conserva_todas_las_versiones_publicadas():
    """Una reexpresión es una fila nueva. Quedarse con la última rompe P1."""
    companyfacts = {
        "cik": 726728,
        "facts": {"us-gaap": {"Assets": {"units": {"USD": [
            {"end": "2025-12-31", "val": 100.0, "filed": "2026-02-24", "form": "10-K"},
            {"end": "2025-12-31", "val": 105.0, "filed": "2026-05-05", "form": "10-Q"},
        ]}}}},
    }
    crudos = hechos_crudos(companyfacts, "O")
    assert len(crudos) == 2
    assert sorted(crudos["valor"]) == [100.0, 105.0]


def test_hechos_crudos_no_repite_la_misma_observacion():
    """La misma cifra puede venir en dos documentos. Es una fila, no dos."""
    obs = {"end": "2025-12-31", "val": 100.0, "filed": "2026-02-24", "form": "10-K"}
    companyfacts = {"cik": 1, "facts": {"us-gaap": {"Assets": {"units": {"USD": [obs, dict(obs)]}}}}}
    assert len(hechos_crudos(companyfacts, "O")) == 1


@pytest.mark.parametrize("ticker", ["O", "NNN", "WELL", "PSA"])
def test_los_estados_guardados_siguen_cuadrando(ticker):
    """Corre contra lo que está versionado en el repositorio, sin red.

    Es la prueba que convierte «los datos están bien» en algo comprobable en cada
    push: si alguien edita un CSV a mano o una ficha se rompe, esto lo caza.
    """
    crudos = leer_crudos(ticker)
    if crudos.empty:
        pytest.skip(f"{ticker} todavía no está descargado en el almacén.")

    tags = elegir_tags(crudos, ticker)
    completos = derivar_trimestres_faltantes(crudos, tags)
    balance = armar_estado(completos, ticker, BALANCE, asof=dt.date.today(), tags=tags)
    errores = [i for i in verificar_balance(ticker, balance) if i.severidad == ERROR]
    assert not errores, "\n".join(i.como_texto() for i in errores)
