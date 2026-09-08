"""Prueba 31 — Lo que encontró comparar contra Bloomberg los estados de Realty Income.

Se bajó de Bloomberg el histórico trimestral completo de O —estado de resultados
desde 1994, balance y flujo estandarizados— y se comparó renglón por renglón
contra la base. De 46 renglones mapeados, la mayoría cuadró al centavo. Lo que no
cuadró se separó en dos montones que NO son lo mismo, y confundirlos habría
llevado a "arreglar" lo que estaba bien:

**Diferencias de presentación de Bloomberg.** No son errores nuestros y no se
corrigen, porque corregirlas nos alejaría del dato tal como lo publicó el emisor:

* Bloomberg mete los arrendamientos capitalizados —operativo 414.2 MM y
  financiero 114.3— DENTRO de la deuda, y su contraparte del activo dentro de los
  inmuebles. Es lo que hacen las calificadoras; no es lo que dice el balance.
* Saca el gasto por intereses de los gastos de operación para llegar a un EBIT
  estándar. Realty Income lo reporta DENTRO de "Total expenses", y la diferencia
  entre las dos cifras es exactamente el interés del trimestre.
* Suma los dividendos por pagar (259.3 MM) a las cuentas por pagar.

**Errores nuestros.** Tres, y los tres empujaban en la misma dirección: hacían ver
a la emisora más sana y más barata de lo que está (31.1 a 31.3).

Y una advertencia sobre nombres que vale por sí sola: **el "AFFO" de Bloomberg no
es el AFFO.** Su cascada es FFO → "Adjusted FFO" → FAD, y el AFFO que reporta
Realty Income —el que usa el modelo— es el FAD de Bloomberg, no su AFFO. Nuestro
``affo_por_accion`` coincide con ``CF_FAD_PER_SH_DILUTED`` en los 26 trimestres,
con diferencia cero; contra el renglón que Bloomberg llama "AFFO Per Diluted
Share" difiere en todos. Tomar el renglón por su nombre habría metido un múltiplo
equivocado con una etiqueta convincente.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.config import Estado, Fuente  # noqa: E402
from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta.estados import (  # noqa: E402
    LINEA_POR_CLAVE,
    etiquetas_de_instancia,
    tags_de,
)
from src.ingesta.instantanea import FUENTES_DE_LA_INSTANTANEA, ResumenInstantanea  # noqa: E402
from src.servicio import (  # noqa: E402
    MARGEN_DE_TRAMOS,
    TRAMOS_DE_DEUDA,
    _saldos_de_balance,
)

# Cifras de Bloomberg al 30 de junio de 2026, en millones de dólares.
BBG_DEUDA_CON_ARRENDAMIENTOS = 31_180.19
BBG_ARRENDAMIENTOS = 414.2 + 114.3
DEUDA_REPORTADA_POR_O = 30_651.7


def _saldo(repo, concepto, fecha, valor, *, ticker="X", fuente=Fuente.SEC_XBRL):
    repo.guardar_hechos([{
        "ticker": ticker, "concepto": concepto, "periodo_tipo": "PUNTUAL",
        "periodo_inicio": None, "fecha_dato": fecha, "fecha_publicacion": fecha,
        "valor": valor, "unidad": "USD", "fuente": fuente,
        "es_primario": True, "estado": Estado.VALIDO, "url_filing": None, "accession": "a",
    }])


# --------------------------------------------------------------------------------------
# 31.1 · La deuda de Realty Income son CUATRO tramos, no uno
# --------------------------------------------------------------------------------------


def test_los_cuatro_tramos_de_realty_income_estan_declarados():
    """`NotesPayable` parecía su deuda total y son sus notas senior.

    25,092 MM contra 30,652 de deuda real. Nada en el resultado lo delataba: el
    número es grande, creciente y con quince años de historia, así que ninguna
    prueba de coherencia interna lo iba a atrapar. Hizo falta un tercero.
    """
    assert "NotesPayable" in tags_de("O", "notas_senior")
    assert "LoansPayable" in tags_de("O", "prestamos_a_plazo")
    assert "RevolvingCreditFacilityAndCommercialPaper" in tags_de("O", "linea_de_credito")
    assert "SecuredDebt" in tags_de("O", "deuda_hipotecaria")


def test_la_revolvente_de_realty_income_es_una_etiqueta_de_extension():
    """Segundo caso del mismo problema que Extra Space, en otro renglón.

    La revolvente y el papel comercial viven en
    ``o:RevolvingCreditFacilityAndCommercialPaper``, y `companyfacts` solo publica
    taxonomías estándar. Sin ir al documento XBRL del filing, 2,763 MM de deuda no
    existen para el modelo.
    """
    assert "RevolvingCreditFacilityAndCommercialPaper" in etiquetas_de_instancia("O")


def test_el_papel_comercial_solo_no_puede_hacer_las_veces_de_la_revolvente():
    """La trampa del arreglo a medias, que era el desenlace más probable.

    `CommercialPaper` SÍ es taxonomía estándar y sí está en `companyfacts`: al 30
    de junio de 2026 vale 1,400 MM. Tomarla habría cerrado la mitad de la brecha
    —de 5,560 a 4,160— y dejado la otra mitad invisible detrás de un renglón que
    ya parecía atendido. Es peor que no cerrarla.
    """
    for clave in TRAMOS_DE_DEUDA + ("deuda_total",):
        assert "CommercialPaper" not in tags_de("O", clave), (
            f"{clave} lee el papel comercial, que es un SUBCONJUNTO de la revolvente"
        )


def test_los_prestamos_a_plazo_no_traen_etiqueta_por_omision():
    """Misma razón que la deuda no garantizada: `LoansPayable` es genérica.

    En la emisora que la usa para nombrar TODA su deuda, contarla además como un
    tramo la duplicaría. Solo la declara quien la reporta aparte.
    """
    assert LINEA_POR_CLAVE["prestamos_a_plazo"].tags == ()
    assert tags_de("EXR", "prestamos_a_plazo") == ()


def test_todos_los_tramos_siguen_siendo_renglones_del_catalogo():
    for clave in TRAMOS_DE_DEUDA:
        assert clave in LINEA_POR_CLAVE, f"{clave} suma deuda y no es un renglón"


# --------------------------------------------------------------------------------------
# 31.2 · Un total al que sus propios tramos le ganan no es un total
# --------------------------------------------------------------------------------------


def test_los_tramos_le_ganan_al_total_declarado(tmp_path):
    """La guarda general, que es lo que habría atrapado esto sin Bloomberg.

    No depende de conocer a Realty Income: cualquier emisora cuyo renglón de
    "deuda total" sea superado por la suma de sus propios instrumentos está
    declarando un tramo con nombre de total.
    """
    repo = Repositorio(ruta=tmp_path / "b.db")
    hoy = dt.date(2026, 6, 30)
    _saldo(repo, "deuda_total", hoy, 25_091.6e6)      # NotesPayable, que NO es el total
    _saldo(repo, "notas_senior", hoy, 25_091.6e6)
    _saldo(repo, "prestamos_a_plazo", hoy, 2_760.4e6)
    _saldo(repo, "linea_de_credito", hoy, 2_762.6e6)
    _saldo(repo, "deuda_hipotecaria", hoy, 37.1e6)
    _saldo(repo, "pasivos_totales", hoy, 34_507.4e6)

    saldos = _saldos_de_balance(repo, "X", asof=dt.date(2026, 9, 8))
    assert saldos["deuda_total"] == pytest.approx(DEUDA_REPORTADA_POR_O * 1e6, rel=1e-6)


def test_la_deuda_armada_cuadra_con_bloomberg_salvo_los_arrendamientos():
    """El cierre de la reconciliación, y la línea que separa los dos montones.

    Bloomberg da 31,180.19. Nuestros cuatro tramos dan 30,651.7. La diferencia son
    exactamente los arrendamientos capitalizados, que Bloomberg mete a la deuda y
    el balance del emisor no. No es una brecha por cerrar: es una decisión de
    Bloomberg, y quedarnos con lo reportado es lo correcto.
    """
    assert DEUDA_REPORTADA_POR_O + BBG_ARRENDAMIENTOS == pytest.approx(
        BBG_DEUDA_CON_ARRENDAMIENTOS, abs=0.5
    )


def test_un_total_de_verdad_no_lo_mueven_sus_tramos(tmp_path):
    """El control. La guarda no puede activarse cuando el total sí es el total."""
    repo = Repositorio(ruta=tmp_path / "b.db")
    hoy = dt.date(2026, 6, 30)
    _saldo(repo, "deuda_total", hoy, 10_000e6)
    _saldo(repo, "notas_senior", hoy, 7_000e6)
    _saldo(repo, "deuda_hipotecaria", hoy, 2_900e6)   # suman 9,900: menos que el total
    _saldo(repo, "pasivos_totales", hoy, 12_000e6)
    saldos = _saldos_de_balance(repo, "X", asof=dt.date(2026, 9, 8))
    assert saldos["deuda_total"] == pytest.approx(10_000e6)


def test_un_desfase_menor_al_margen_no_dispara_la_guarda(tmp_path):
    """Entre "el total no es un total" y "las fechas de corte no coinciden".

    Medio punto porcentual sobre la deuda no es un tramo faltante; es ruido de
    presentación. La guarda tiene que distinguir los dos casos o se convierte en
    una fuente de cambios que nadie pidió.
    """
    repo = Repositorio(ruta=tmp_path / "b.db")
    hoy = dt.date(2026, 6, 30)
    _saldo(repo, "deuda_total", hoy, 10_000e6)
    _saldo(repo, "notas_senior", hoy, 10_050e6)       # 0.5%, por debajo del margen
    _saldo(repo, "pasivos_totales", hoy, 12_000e6)
    saldos = _saldos_de_balance(repo, "X", asof=dt.date(2026, 9, 8))
    assert saldos["deuda_total"] == pytest.approx(10_000e6)
    assert 0 < MARGEN_DE_TRAMOS < 0.05


def test_una_suma_que_excede_el_pasivo_total_no_reemplaza_nada(tmp_path):
    """Si los tramos superan el pasivo entero, hay doble conteo y no deuda oculta.

    Es la forma en que un mapeo mal hecho se delata solo, y por eso la guarda solo
    puede corregir hacia arriba DENTRO de lo que el emisor declara deber.
    """
    repo = Repositorio(ruta=tmp_path / "b.db")
    hoy = dt.date(2026, 6, 30)
    _saldo(repo, "deuda_total", hoy, 10_000e6)
    _saldo(repo, "notas_senior", hoy, 10_000e6)
    _saldo(repo, "linea_de_credito", hoy, 5_000e6)   # 15,000 contra un pasivo de 12,000
    _saldo(repo, "pasivos_totales", hoy, 12_000e6)
    saldos = _saldos_de_balance(repo, "X", asof=dt.date(2026, 9, 8))
    assert saldos["deuda_total"] == pytest.approx(10_000e6)


# --------------------------------------------------------------------------------------
# 31.3 · El efectivo es el efectivo, no el efectivo más el restringido
# --------------------------------------------------------------------------------------


def test_el_efectivo_no_lee_la_etiqueta_que_incluye_el_restringido():
    """Dos cantidades distintas bajo el mismo renglón, según el trimestre.

    ``CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`` estaba como
    respaldo del efectivo y no es un nombre alterno: es el efectivo MÁS el
    restringido, que por definición no se puede usar. Como la cadena se elige por
    cobertura y no por orden, la combinada le ganaba en once cierres de año. El
    efectivo RESTA en la deuda neta, así que el sesgo iba hacia menos
    apalancamiento del real.
    """
    tags = tags_de("O", "efectivo")
    assert "CashAndCashEquivalentsAtCarryingValue" in tags
    assert "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents" not in tags


def test_el_efectivo_de_realty_income_coincide_con_bloomberg_en_los_cierres_de_anio():
    """Los cinco cierres que estaban mal, contra el tercero."""
    repo = Repositorio()
    esperado = {2020: 824.48, 2021: 258.58, 2022: 171.10, 2023: 232.92, 2024: 444.96}
    hechos = repo.hechos(
        asof=dt.date.today(), tickers="O", conceptos=["efectivo"], periodo_tipo="PUNTUAL"
    )
    if hechos.empty:
        pytest.skip("No hay base cargada.")
    hechos = hechos.assign(fecha_dato=pd.to_datetime(hechos["fecha_dato"]).dt.date)
    hechos = hechos.sort_values(["fecha_dato", "fecha_publicacion"]).groupby("fecha_dato").tail(1)
    for anio, bbg in esperado.items():
        fila = hechos.loc[hechos["fecha_dato"] == dt.date(anio, 12, 31), "valor"]
        if fila.empty:
            continue
        assert fila.iloc[0] / 1e6 == pytest.approx(bbg, abs=0.02), f"cierre de {anio}"


def test_la_deuda_de_realty_income_en_la_base_ya_es_la_completa():
    """La prueba de que el arreglo llegó al dato, no solo al catálogo."""
    repo = Repositorio()
    saldos = _saldos_de_balance(repo, "O", asof=dt.date.today())
    if "deuda_total" not in saldos:
        pytest.skip("No hay base cargada.")
    assert saldos["deuda_total"] / 1e6 == pytest.approx(DEUDA_REPORTADA_POR_O, rel=0.02)
    # Y el cociente contra el pasivo total, que era el síntoma visible: Realty
    # Income salía en 72.7% cuando las otras nueve viven entre 80% y 96%.
    assert saldos["deuda_total"] / saldos["pasivos_totales"] > 0.80


# --------------------------------------------------------------------------------------
# 31.4 · La instantánea tiene que poder CORREGIR, no solo agregar
# --------------------------------------------------------------------------------------


def test_la_proyeccion_se_rehace_y_lo_capturado_a_mano_sobrevive(tmp_path):
    """Sin esto, ninguno de los arreglos de arriba llega nunca a la base.

    La tabla de hechos es append-only con llave point-in-time, así que el valor
    corregido choca con el viejo y se descarta EN SILENCIO. Reconstruir insertaba
    cero filas y terminaba bien. La promesa de la instantánea —que una mejora del
    catálogo entra sin descargar nada— solo se cumplía si AGREGABA renglones.
    """
    repo = Repositorio(ruta=tmp_path / "b.db")
    hoy = dt.date(2026, 6, 30)
    _saldo(repo, "efectivo", hoy, 495.5e6, ticker="O", fuente=Fuente.SEC_XBRL)
    _saldo(repo, "renta_propia", hoy, 42.0, ticker="O", fuente=Fuente.MANUAL)

    borrados = repo.purgar_hechos_derivados("O", FUENTES_DE_LA_INSTANTANEA)
    assert borrados == 1

    quedan = repo.hechos(asof=dt.date(2026, 9, 8), tickers="O")
    assert set(quedan["concepto"]) == {"renta_propia"}, "se borró lo capturado a mano"


def test_purgar_no_toca_a_otro_emisor(tmp_path):
    repo = Repositorio(ruta=tmp_path / "b.db")
    hoy = dt.date(2026, 6, 30)
    _saldo(repo, "efectivo", hoy, 1e6, ticker="O")
    _saldo(repo, "efectivo", hoy, 2e6, ticker="NNN")
    repo.purgar_hechos_derivados("O", FUENTES_DE_LA_INSTANTANEA)
    assert len(repo.hechos(asof=dt.date(2026, 9, 8), tickers="NNN")) == 1


def test_las_fuentes_que_se_borran_son_las_que_la_pasada_reescribe():
    """El invariante que hace segura la purga: no se borra lo que no se repone."""
    assert Fuente.MANUAL not in FUENTES_DE_LA_INSTANTANEA
    assert Fuente.MERCADO not in FUENTES_DE_LA_INSTANTANEA
    assert Fuente.DEMO not in FUENTES_DE_LA_INSTANTANEA
    assert set(FUENTES_DE_LA_INSTANTANEA) == {
        Fuente.SEC_XBRL, Fuente.SEC_8K, Fuente.DERIVADO, Fuente.RECONSTRUIDO,
    }


def test_reconstruir_sobre_una_base_al_dia_no_es_un_error():
    """«Cero filas nuevas» y «no hay instantánea» no son lo mismo.

    Medir el vacío por los hechos insertados convertía el caso normal —reconstruir
    dos veces— en un error cuyo mensaje manda a pagar 810 peticiones contra la SEC
    para arreglar algo que no está roto.
    """
    assert ResumenInstantanea(hechos=0, emisoras=["O"]).vacia is False
    assert ResumenInstantanea().vacia is True
