"""Prueba 27 — Reconstruir sin red, y que un hecho tenga UN valor.

Dos quejas distintas del operador, que resultaron ser la misma historia: los
datos se sentían incompletos porque refrescarlos costaba tanto que no se hacía.

**La descarga.** Reconstruir la base costaba 810 peticiones y 128 MB contra la
SEC, y 106 segundos aun con las 810 respuestas en caché de disco. En Streamlit
Cloud el disco es efímero, así que eso pasaba en cada reinicio del contenedor.
Todo para rearmar algo que ya estaba versionado en el repositorio. El almacén
(`src/datos/almacen.py`) llevaba tiempo escrito y bien diseñado —crudo
determinista por emisora, manifiesto con el último filing visto— pero
`orquestador.py` **no lo importaba**: el camino principal lo ignoraba.

**El valor.** Al conectar las dos mitades apareció un defecto que llevaba tiempo
escondido: `xbrl.py` y `estados.py` mapean quince conceptos en común y eligen la
etiqueta GAAP con criterios distintos. Cuando difieren escriben la MISMA llave
con la MISMA procedencia, así que la restricción única deja una sola fila y
ganaba la que se hubiera insertado antes. Eran 2,067 celdas cuyo valor dependía
del orden de dos líneas de código.

* **27.1** La procedencia decide, no el orden de inserción.
* **27.2** Lo derivable del crudo se REARMA; lo demás se guarda. La separación
  es la que deja que una mejora del catálogo entre sin descargar nada.
* **27.3** Las fechas vacías del almacén son ``None``, como en el camino en vivo.
* **27.4** Los dos caminos comparten la lista de conceptos reconstruibles.
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

from src.config import (  # noqa: E402
    PRECEDENCIA_DESCONOCIDA,
    PRECEDENCIA_FUENTE,
    Estado,
    Fuente,
)
from src.datos.almacen import (  # noqa: E402
    escribir_conciliacion,
    escribir_crudos,
    escribir_hechos_externos,
    leer_conciliacion,
    leer_crudos,
    leer_hechos_externos,
)
from src.datos.repositorio import Repositorio  # noqa: E402
from src.ingesta.orquestador import CONCEPTOS_RECONSTRUIBLES  # noqa: E402


def _hecho(**kw) -> dict:
    base = {
        "ticker": "X", "concepto": "utilidad_neta", "periodo_tipo": "Q",
        "periodo_inicio": dt.date(2025, 10, 1), "fecha_dato": dt.date(2025, 12, 31),
        "fecha_publicacion": dt.date(2026, 2, 10), "valor": 100.0, "unidad": "USD",
        "fuente": Fuente.SEC_XBRL, "es_primario": True, "estado": Estado.VALIDO,
        "url_filing": None, "accession": "a-1",
    }
    return {**base, **kw}


# --------------------------------------------------------------------------------------
# 27.1 · Ante el mismo hecho, manda la procedencia
# --------------------------------------------------------------------------------------


def test_un_dato_de_la_sec_le_gana_a_uno_reconstruido(tmp_path):
    """El caso que se encontró en la base: el mismo trimestre por dos caminos.

    Antes ganaba el ``id`` más alto —el que se hubiera insertado después—, así
    que una cifra reconstruida podía desplazar a la que reportó el emisor solo
    porque la ingesta corrió en otro orden.
    """
    repo = Repositorio(ruta=tmp_path / "b.db")
    repo.guardar_hechos([
        # El reconstruido entra PRIMERO, para que ganar por `id` sea ganar por orden.
        _hecho(valor=90.0, fuente=Fuente.RECONSTRUIDO, es_primario=False),
        _hecho(valor=100.0, fuente=Fuente.SEC_XBRL, es_primario=True),
    ])
    df = repo.hechos(asof=dt.date(2026, 9, 7), tickers="X")

    assert len(df) == 1, "debería quedar una sola fila vigente por celda"
    assert float(df["valor"].iloc[0]) == 100.0
    assert df["fuente"].iloc[0] == Fuente.SEC_XBRL


def test_el_orden_de_insercion_ya_no_decide(tmp_path):
    """El control: invertir el orden de escritura no cambia el resultado."""
    valores = []
    for orden in ([Fuente.SEC_XBRL, Fuente.RECONSTRUIDO], [Fuente.RECONSTRUIDO, Fuente.SEC_XBRL]):
        repo = Repositorio(ruta=tmp_path / f"b{orden[0]}.db")
        repo.guardar_hechos([
            _hecho(valor=100.0 if f == Fuente.SEC_XBRL else 90.0, fuente=f,
                   es_primario=f == Fuente.SEC_XBRL)
            for f in orden
        ])
        df = repo.hechos(asof=dt.date(2026, 9, 7), tickers="X")
        valores.append(float(df["valor"].iloc[0]))

    assert valores[0] == valores[1] == 100.0, (
        f"el valor sigue dependiendo del orden de inserción: {valores}"
    )


def test_una_reexpresion_posterior_si_le_gana_a_un_primario_viejo(tmp_path):
    """La procedencia desempata, pero NO le gana a una publicación más reciente.

    Sin esta prueba, "el primario manda" se podría implementar de una forma que
    congela el dato original y se salta las reexpresiones, que es un error peor.
    """
    repo = Repositorio(ruta=tmp_path / "b.db")
    repo.guardar_hechos([
        _hecho(valor=100.0, fuente=Fuente.SEC_XBRL, fecha_publicacion=dt.date(2026, 2, 10)),
        _hecho(valor=111.0, fuente=Fuente.DERIVADO, es_primario=False,
               fecha_publicacion=dt.date(2026, 5, 1)),
    ])
    df = repo.hechos(asof=dt.date(2026, 9, 7), tickers="X")
    assert float(df["valor"].iloc[0]) == 111.0, "se quedó con la versión vieja"


def test_la_tabla_de_precedencia_ordena_de_la_fuente_hacia_la_cuenta_propia():
    assert PRECEDENCIA_FUENTE[Fuente.SEC_XBRL] > PRECEDENCIA_FUENTE[Fuente.MANUAL]
    assert PRECEDENCIA_FUENTE[Fuente.MANUAL] > PRECEDENCIA_FUENTE[Fuente.DERIVADO]
    assert PRECEDENCIA_FUENTE[Fuente.DERIVADO] > PRECEDENCIA_FUENTE[Fuente.RECONSTRUIDO]
    assert PRECEDENCIA_FUENTE[Fuente.RECONSTRUIDO] > PRECEDENCIA_FUENTE[Fuente.DEMO]
    # Una fuente que nadie registró no puede colarse por encima de un primario.
    assert PRECEDENCIA_DESCONOCIDA < min(
        PRECEDENCIA_FUENTE[f] for f in (Fuente.SEC_XBRL, Fuente.DERIVADO, Fuente.RECONSTRUIDO)
    )


def test_la_semilla_de_demostracion_nunca_le_gana_a_un_dato_real(tmp_path):
    repo = Repositorio(ruta=tmp_path / "b.db")
    repo.guardar_hechos([
        _hecho(valor=100.0, fuente=Fuente.SEC_XBRL),
        _hecho(valor=7.0, fuente=Fuente.DEMO, es_primario=False),
    ])
    df = repo.hechos(asof=dt.date(2026, 9, 7), tickers="X")
    assert float(df["valor"].iloc[0]) == 100.0


# --------------------------------------------------------------------------------------
# 27.2 · El almacén va y viene sin pérdida
# --------------------------------------------------------------------------------------


def _crudos_min() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ticker": "X", "taxonomia": "us-gaap", "tag": "Revenues", "unidad": "USD",
            "periodo_tipo": "Q", "fecha_inicio": dt.date(2025, 10, 1),
            "fecha_dato": dt.date(2025, 12, 31), "fecha_publicacion": dt.date(2026, 2, 10),
            "valor": 100.0, "formulario": "10-K", "accession": "a-1", "marco": "",
        },
        {
            # Un saldo PUNTUAL: sin fecha de inicio. Es el caso normal del balance
            # y el que reventaba al releer el almacén.
            "ticker": "X", "taxonomia": "us-gaap", "tag": "Assets", "unidad": "USD",
            "periodo_tipo": "PUNTUAL", "fecha_inicio": None,
            "fecha_dato": dt.date(2025, 12, 31), "fecha_publicacion": dt.date(2026, 2, 10),
            "valor": 900.0, "formulario": "10-K", "accession": "a-1", "marco": "",
        },
    ])


def test_el_crudo_vuelve_del_almacen_igual_a_como_entro(tmp_path):
    escribir_crudos("X", _crudos_min(), base=tmp_path)
    vuelta = leer_crudos("X", base=tmp_path)
    assert len(vuelta) == 2
    assert set(vuelta["tag"]) == {"Revenues", "Assets"}


def test_una_fecha_vacia_vuelve_como_none_y_no_como_nat(tmp_path):
    """``NaT`` y ``None`` no son lo mismo cuando la fila va a la base.

    El camino en vivo produce ``None``; el CSV producía ``NaT``, y escribir eso
    reventaba con "cannot convert float NaN to integer" justo en los saldos de
    balance, que son los que nunca traen fecha de inicio. Dos caminos que dicen
    producir lo mismo tienen que coincidir hasta en el tipo del vacío.
    """
    escribir_crudos("X", _crudos_min(), base=tmp_path)
    vuelta = leer_crudos("X", base=tmp_path)
    puntual = vuelta[vuelta["periodo_tipo"] == "PUNTUAL"].iloc[0]

    assert puntual["fecha_inicio"] is None, f"volvió como {puntual['fecha_inicio']!r}"
    assert not isinstance(puntual["fecha_inicio"], float), "un NaT disfrazado"


def test_los_hechos_externos_y_la_conciliacion_dan_la_vuelta(tmp_path):
    externos = pd.DataFrame([_hecho(concepto="affo", fuente=Fuente.SEC_8K)]).drop(
        columns="estado"
    )
    escribir_hechos_externos("X", externos, base=tmp_path)
    assert len(leer_hechos_externos("X", base=tmp_path)) == 1

    conc = pd.DataFrame([{
        "ticker": "X", "periodo_tipo": "Q", "fecha_dato": dt.date(2025, 12, 31),
        "fecha_publicacion": dt.date(2026, 2, 10), "orden": 1, "linea": "utilidad_neta",
        "etiqueta": "Net income", "valor": 100.0, "signo": 1,
        "fuente": Fuente.SEC_8K, "url_filing": None,
    }])
    escribir_conciliacion("X", conc, base=tmp_path)
    assert len(leer_conciliacion("X", base=tmp_path)) == 1


def test_el_almacen_vacio_devuelve_vacio_y_no_truena(tmp_path):
    assert leer_crudos("NOEXISTE", base=tmp_path).empty
    assert leer_hechos_externos("NOEXISTE", base=tmp_path).empty
    assert leer_conciliacion("NOEXISTE", base=tmp_path).empty


def test_escribir_el_mismo_crudo_dos_veces_da_los_mismos_bytes(tmp_path):
    """Determinismo: sin él, el `git diff` del almacén deja de decir nada."""
    a = escribir_crudos("X", _crudos_min(), base=tmp_path)
    b = escribir_crudos("X", _crudos_min(), base=tmp_path)
    assert a == b


# --------------------------------------------------------------------------------------
# 27.3 · Reconstruir desde el repositorio no toca la red
# --------------------------------------------------------------------------------------


def test_reconstruir_no_abre_una_sola_conexion(tmp_path, monkeypatch):
    """La prueba que define el objetivo: cero red.

    Se rompe el cliente de EDGAR a propósito. Si la reconstrucción lo tocara,
    reventaría; que termine es la evidencia de que el repositorio se basta.
    """
    import src.ingesta.instantanea as mod

    def explota(*_a, **_k):
        raise AssertionError("la reconstrucción intentó salir a la red")

    monkeypatch.setattr("src.ingesta.edgar.ClienteEdgar.obtener", explota)
    monkeypatch.setattr("src.ingesta.edgar.ClienteEdgar.obtener_json", explota)

    repo = Repositorio(ruta=tmp_path / "b.db")
    resumen = mod.reconstruir(repo, tickers=["O"])
    assert resumen.hechos > 0, "no cargó nada desde el repositorio"


def test_la_reconstruccion_trae_la_historia_completa(tmp_path, monkeypatch):
    """La instantánea corta era una trampa: rápida y con la mitad de la historia.

    Guardada desde 2019 dejaba treinta trimestres en vez de setenta, y la Puerta 2
    exige doce observaciones de la prima para dar un percentil. Habría cambiado
    velocidad por veredictos, que es el peor trueque posible aquí.
    """
    import src.ingesta.instantanea as mod

    repo = Repositorio(ruta=tmp_path / "b.db")
    mod.reconstruir(repo, tickers=["O"])
    df = repo.hechos(asof=dt.date(2026, 9, 7), tickers="O", periodo_tipo="Q")

    trimestres = df["fecha_dato"].nunique()
    assert trimestres >= 60, f"solo {trimestres} trimestres: la instantánea quedó corta"
    assert pd.to_datetime(df["fecha_dato"]).min() < pd.Timestamp("2015-01-01")


# --------------------------------------------------------------------------------------
# 27.4 · Los dos caminos comparten la misma lista
# --------------------------------------------------------------------------------------


def test_la_lista_de_conceptos_reconstruibles_es_una_sola():
    """Si se duplicara, uno de los dos caminos se quedaría atrás sin avisar.

    Y la diferencia aparecería como "faltan datos" en la pantalla, sin nada que
    la explicara — que es exactamente de donde salió este trabajo.
    """
    import inspect

    from src.ingesta import instantanea

    assert "CONCEPTOS_RECONSTRUIBLES" in inspect.getsource(instantanea.reconstruir)
    assert "affo" in CONCEPTOS_RECONSTRUIBLES
    assert len(CONCEPTOS_RECONSTRUIBLES) == len(set(CONCEPTOS_RECONSTRUIBLES))


def test_los_estados_se_escriben_antes_que_el_mapeo_viejo():
    """Quince conceptos los producen los dos caminos, con criterios distintos.

    Escriben la misma llave con la misma procedencia, así que la llave única deja
    una sola fila y gana quien escribió primero. `estados.py` es la ruta con el
    criterio explícito —vigencia, cobertura y empalme verificado— y por eso va
    antes. Sin este orden, el deterioro de 2012 de Realty Income vale 5.1 MM o
    3.6 MM según cómo estén puestas dos líneas de código.
    """
    import inspect

    from src.ingesta import orquestador

    codigo = inspect.getsource(orquestador.correr_ingesta)
    assert codigo.index("ingestar_estados(") < codigo.index("ingestar_xbrl("), (
        "el mapeo viejo volvió a escribir antes que los estados completos"
    )


@pytest.mark.parametrize(
    "clave",
    ["vencimiento_12m", "vencimiento_ano_2", "pasivo_arrendamiento",
     "terreno", "edificios", "efectivo_restringido"],
)
def test_los_renglones_nuevos_estan_en_el_catalogo(clave):
    """Las etiquetas que las emisoras publican y el catálogo ignoraba.

    La escalera de vencimientos es la que dice cuánta deuda hay que refinanciar y
    cuándo: el apalancamiento total no distingue entre deber a doce meses y deber
    a diez años, y para un REIT esa es media tesis.
    """
    from src.ingesta.estados import LINEA_POR_CLAVE

    assert clave in LINEA_POR_CLAVE
    assert LINEA_POR_CLAVE[clave].tags, f"{clave} no tiene ninguna etiqueta GAAP"


def test_reconstruir_dos_veces_da_exactamente_lo_mismo(tmp_path):
    """Determinismo del camino sin red.

    Es la mitad que hace verificable a la otra: se comprobó a mano que la
    instantánea reproduce la ingesta con red celda por celda —102,763 hechos,
    cero faltantes, cero sobrantes, cero valores distintos—. Esa comparación
    necesita red y no cabe en CI; lo que sí cabe es garantizar que el lado
    reproducible no se mueve, porque si se moviera, aquella verificación dejaría
    de valer para el commit siguiente.
    """
    import src.ingesta.instantanea as mod

    huellas = []
    for i in (1, 2):
        repo = Repositorio(ruta=tmp_path / f"b{i}.db")
        mod.reconstruir(repo, tickers=["EPRT"])
        df = repo.hechos(asof=dt.date(2026, 9, 7), tickers="EPRT", vigentes=False)
        columnas = ["concepto", "periodo_tipo", "fecha_dato", "fecha_publicacion", "valor"]
        huellas.append(
            pd.util.hash_pandas_object(
                df[columnas].sort_values(columnas).astype(str), index=False
            ).sum()
        )
    assert huellas[0] == huellas[1], "dos reconstrucciones del mismo commit difieren"


def test_el_almacen_cubre_a_las_diez_emisoras():
    """Si a una emisora le falta su instantánea, su arranque vuelve a costar red."""
    from src.config import UNIVERSO_INICIAL

    faltan = [e.ticker for e in UNIVERSO_INICIAL if leer_crudos(e.ticker).empty]
    assert not faltan, f"sin instantánea versionada: {', '.join(faltan)}"


def test_la_instantanea_guarda_lo_que_no_se_puede_rearmar():
    """El AFFO no está en `companyfacts`: sale del 8-K y hay que guardarlo.

    Sin este archivo la reconstrucción quedaba sin la medida de flujo con la que
    se valúa, que es tanto como no reconstruir nada.
    """
    from src.config import UNIVERSO_INICIAL

    for e in UNIVERSO_INICIAL:
        externos = leer_hechos_externos(e.ticker)
        assert not externos.empty, f"{e.ticker} no tiene hechos externos versionados"
        assert "affo" in set(externos["concepto"]) or "ffo_normalizado" in set(
            externos["concepto"]
        ), f"{e.ticker}: la instantánea no trae la medida de flujo"
