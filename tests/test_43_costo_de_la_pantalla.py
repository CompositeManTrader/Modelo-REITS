"""Prueba 43 — Lo que la pantalla cuesta abrir, y por qué se estaba trabando.

El reporte fue «no me permite abrirlo y visualizar adecuadamente, sigue
corriendo a cada rato». No era una sola falla: eran tres, y las tres se pueden
medir.

**1. El arranque en frío tardaba seis minutos y medio.** En Streamlit Cloud el
disco es efímero, así que la base se reconstruye desde el repositorio en cada
reinicio del contenedor. Esa pasada corre `revisar_escala` por emisora —tiene
que correr: la instantánea REARMA la proyección desde el crudo, y sin la
revisión el margen de Agree Realty vuelve a 62,787%—. El detector recorría la
ventana con máscaras de pandas sobre catorce mil filas, una por corte: 331 de
los 396 segundos del arranque. La misma regla sobre arreglos tarda 4.

**2. Cada clic recalculaba la pantalla entera.** Streamlit vuelve a correr el
script completo en cada interacción, y no había un solo `cache_data`: el panel,
el molde de Bloomberg de los tres estados, los as reported y —lo más caro— el
LIBRO DE EXCEL del botón de descarga, que se armaba en cada recarga aunque nadie
lo descargara. Siete segundos por clic, aquí; el triple en el contenedor.

**3. Tocar cualquier control te sacaba de la pestaña.** `st.tabs` sin `key`
vuelve a la primera pestaña en cada recarga. Quien abría «Estados financieros» y
cambiaba la frecuencia aparecía de vuelta en «Evidencia». Eso es, literalmente,
«no me permite visualizarlo».

Qué se prueba aquí
------------------
Las tres, y de la única forma que sirve: contra el comportamiento, no contra la
implementación. La escala se prueba por PARIDAD —el detector rápido tiene que
acusar exactamente a los mismos hechos que el lento, y el lento va copiado en
esta prueba— y por PRESUPUESTO, con un techo de tiempo que hace ruido si alguien
vuelve a meter una máscara por corte.
"""

from __future__ import annotations

import ast
import datetime as dt
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
for ruta in (RAIZ, RAIZ / "app"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

from src.datos.repositorio import Repositorio  # noqa: E402
from src.validacion import escala as E  # noqa: E402

HOY = dt.date.today()


@pytest.fixture(scope="module")
def repo():
    r = Repositorio()
    if r.hechos(asof=HOY, tickers="O", conceptos=["ingresos_totales"]).empty:
        pytest.skip("No hay base cargada.")
    return r


# --------------------------------------------------------------------------------------
# 43.1 · El detector de escala, rápido, tiene que decir lo MISMO
# --------------------------------------------------------------------------------------


def _candidatos_como_antes(hechos: pd.DataFrame) -> pd.DataFrame:
    """La implementación anterior, con máscaras de pandas, copiada del commit 1b20ddf.

    Vive aquí para que la paridad sea una comparación real y no una promesa. Si
    alguien cambia la REGLA a propósito, esta copia tiene que cambiar con ella y
    el cambio se ve en el diff, que es justo lo que se quiere.
    """
    def desvio_de(fila, del_corte, moda):
        valor = abs(float(fila["valor"]))
        for otra in del_corte.itertuples():
            if otra.id == fila["id"] or abs(int(otra.exponente) - moda) >= min(E.POTENCIAS):
                continue
            razon = abs(float(otra.valor)) / valor if valor else 0.0
            for potencia in E.POTENCIAS:
                for signo in (1, -1):
                    esperado = 10.0 ** (signo * potencia)
                    if abs(razon / esperado - 1) <= E.TOLERANCIA_ENTRE_VERSIONES:
                        return -signo * potencia
        d = int(fila["exponente"]) - moda
        return d if abs(d) in E.POTENCIAS else None

    filas = []
    for (tk, con, tipo), serie in hechos.groupby(["ticker", "concepto", "periodo_tipo"]):
        cortes = sorted(serie["fecha_dato"].unique())
        if len(cortes) < E.MINIMO_CORTES + 1:
            continue
        posicion = {f: i for i, f in enumerate(cortes)}
        for corte in cortes:
            i = posicion[corte]
            vecinos = cortes[max(0, i - E.VENTANA): i] + cortes[i + 1: i + 1 + E.VENTANA]
            if len(vecinos) < E.MINIMO_CORTES:
                continue
            ventana = serie[serie["fecha_dato"].isin(vecinos)]
            cuenta = ventana["exponente"].value_counts()
            if cuenta.empty:
                continue
            moda = int(cuenta.index[0])
            por_corte = ventana.groupby("fecha_dato")["exponente"].apply(set)
            if sum(1 for e in por_corte if moda in e) / len(por_corte) < E.FRACCION_MODA:
                continue
            antes = ventana[(ventana["fecha_dato"] < corte) & (ventana["exponente"] == moda)]
            despues = ventana[(ventana["fecha_dato"] > corte) & (ventana["exponente"] == moda)]
            if antes.empty or despues.empty:
                continue
            del_corte = serie[serie["fecha_dato"] == corte]
            for _, fila in del_corte.iterrows():
                d = desvio_de(fila, del_corte, moda)
                if d is None:
                    continue
                filas.append({
                    "id": int(fila["id"]), "ticker": tk, "concepto": con,
                    "periodo_tipo": tipo, "fecha_dato": corte, "desvio": d,
                    "valor": float(fila["valor"]),
                })
    return pd.DataFrame(filas)


def _con_exponente(hechos: pd.DataFrame) -> pd.DataFrame:
    h = hechos[hechos["valor"].notna() & (hechos["valor"] != 0)].copy()
    h["exponente"] = E._exponente(h["valor"])
    return h


@pytest.mark.parametrize("ticker", ["O", "NNN", "ADC", "PLD", "WELL"])
def test_el_detector_rapido_acusa_a_los_mismos_hechos_que_el_lento(repo, ticker):
    """Paridad exacta: mismos ids y mismos desvíos, no un conteo parecido.

    Se prueban las cinco emisoras que cubren los dos lados: NNN, ADC y PLD tienen
    hechos fuera de escala; O y WELL no tienen ninguno, y esa es la mitad que
    importa —un detector más rápido que además acusa de más no sirve—.
    """
    hechos = repo.hechos(asof=HOY, tickers=ticker, vigentes=False, incluir_sospechosos=True)
    if hechos.empty:
        pytest.skip(f"No hay base de {ticker}.")
    h = _con_exponente(hechos)
    antes = _candidatos_como_antes(h)
    ahora = E._candidatos(h)

    def firma(df):
        if df.empty:
            return set()
        return {(int(r.id), int(r.desvio)) for r in df.itertuples()}

    assert firma(ahora) == firma(antes), (
        f"{ticker}: el detector rápido cambió a quién acusa.\n"
        f"  solo el viejo: {sorted(firma(antes) - firma(ahora))[:5]}\n"
        f"  solo el nuevo: {sorted(firma(ahora) - firma(antes))[:5]}"
    )


def test_la_revision_de_escala_cabe_en_el_presupuesto_del_arranque(repo):
    """Un techo de tiempo, porque este detector corre en CADA arranque en frío.

    Con máscaras por corte tardaba 33 segundos por emisora —330 del arranque— y
    ahí es donde Streamlit Cloud daba la aplicación por muerta. El listón está en
    cinco segundos para la emisora más pesada: ocho veces lo que tarda hoy, y una
    séptima parte de lo que tardaba. No mide la máquina, mide el orden de
    magnitud del algoritmo.
    """
    hechos = repo.hechos(asof=HOY, tickers="WELL", vigentes=False, incluir_sospechosos=True)
    if hechos.empty:
        pytest.skip("No hay base de WELL.")
    t = time.time()
    E.detectar_fuera_de_escala(hechos)
    tardo = time.time() - t
    assert tardo < 5.0, (
        f"la revisión de escala tardó {tardo:.1f}s sobre {len(hechos):,} filas. "
        "Con una máscara de pandas por corte esto vuelve a los 33s y el arranque "
        "en frío se va a seis minutos."
    )


def test_el_desempate_de_la_moda_es_a_la_baja_y_esta_documentado():
    """En empate manda el exponente chico: acusa al grande, que es el lado seguro.

    Antes el empate lo resolvía el orden interno de `value_counts`, que no está
    documentado ni es estable. Que ahora sea una regla explícita es la mitad del
    arreglo; que la regla sea ESTA es la otra mitad.
    """
    assert E._moda(np.array([3, 3, 6, 6])) == 3
    assert E._moda(np.array([6, 6, 3, 3])) == 3, "el desempate no puede depender del orden"
    assert E._moda(np.array([6, 6, 6, 3])) == 6, "sin empate manda la frecuencia"


def test_partir_por_corte_conserva_el_orden_dentro_del_corte():
    """`_desvio` devuelve la PRIMERA versión que explica el desvío: reordenar cambia cuál."""
    serie = pd.DataFrame({
        "id": [1, 2, 3],
        "valor": [100.0, 200.0, 300.0],
        "exponente": [2, 2, 2],
        "fecha_dato": [dt.date(2025, 3, 31), dt.date(2025, 3, 31), dt.date(2024, 12, 31)],
        "fecha_publicacion": [dt.date(2025, 5, 1)] * 3,
        "accession": ["a", "b", "c"],
        "unidad": ["USD"] * 3,
    })
    cortes, bloques = E._partir_por_corte(serie)
    assert cortes == [dt.date(2024, 12, 31), dt.date(2025, 3, 31)]
    assert list(bloques[0].id) == [3]
    assert list(bloques[1].id) == [1, 2], "el orden original dentro del corte se perdió"


# --------------------------------------------------------------------------------------
# 43.2 · La pantalla no puede recalcular lo mismo en cada clic
# --------------------------------------------------------------------------------------


def _arbol(ruta: Path) -> ast.Module:
    return ast.parse(ruta.read_text(encoding="utf-8"))


def _llamadas(arbol: ast.Module) -> list[ast.Call]:
    return [n for n in ast.walk(arbol) if isinstance(n, ast.Call)]


def _nombre_llamado(nodo: ast.Call) -> str:
    f = nodo.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


PAGINA = RAIZ / "app" / "pages" / "1_Valuacion.py"

# Lo que cuesta medio segundo o más y no puede volver a la ruta de cada recarga.
# El valor es la función cacheada que ocupa su lugar.
CAROS = {
    "panel_de_conceptos": "panel_en_cache",
    "construir_panel": "panel_del_modelo_en_cache",
    "cobertura_de_emisores": "cobertura_en_cache",
    "estados_reportados": "reportados_en_cache",
    "estado_financiero": "estado_en_cache",
}


@pytest.mark.parametrize("caro,en_cache", sorted(CAROS.items()))
def test_la_pantalla_no_llama_directo_a_lo_caro(caro, en_cache):
    """Cada uno de estos corría en CADA clic para devolver siempre lo mismo."""
    llamados = {_nombre_llamado(n) for n in _llamadas(_arbol(PAGINA))}
    assert caro not in llamados, (
        f"«{caro}» volvió a la ruta de cada recarga; usa «{en_cache}»"
    )
    assert en_cache in llamados, f"«{en_cache}» ya no se usa en la página"


def test_el_libro_de_excel_se_arma_al_descargar_y_no_en_cada_recarga():
    """`data` tiene que ser una FUNCIÓN, no bytes.

    Armar el libro cuesta cinco segundos —los tres estados en las tres vistas,
    más los ratios con sus fórmulas vivas— y se pagaban en cada interacción de la
    página, incluidas las de quien nunca descarga nada. Streamlit acepta un
    invocable en `data` justamente para esto: lo llama cuando alguien hace clic.
    """
    botones = [n for n in _llamadas(_arbol(PAGINA)) if _nombre_llamado(n) == "download_button"]
    con_libro = [
        b for b in botones
        for kw in b.keywords
        if kw.arg == "data" and "libro_de_estados" in ast.dump(kw.value)
    ]
    assert con_libro, "no se encontró el botón de descarga de los estados"
    for boton in con_libro:
        dato = next(kw.value for kw in boton.keywords if kw.arg == "data")
        assert isinstance(dato, ast.Lambda), (
            "el libro se está armando en cada recarga; pasa `data=lambda: ...`"
        )


# --------------------------------------------------------------------------------------
# 43.3 · La pestaña abierta tiene que seguir abierta
# --------------------------------------------------------------------------------------


PAGINAS_CON_PESTANAS = sorted(
    p for p in (RAIZ / "app" / "pages").glob("*.py")
    if "st.tabs(" in p.read_text(encoding="utf-8")
)


@pytest.mark.parametrize("pagina", PAGINAS_CON_PESTANAS, ids=lambda p: p.name)
def test_toda_pestana_lleva_key_para_sobrevivir_la_recarga(pagina):
    """Sin `key`, `st.tabs` vuelve a la primera pestaña en cada recarga.

    Es el defecto que se leía como «no me permite visualizarlo»: abrir «Estados
    financieros», cambiar la frecuencia y aparecer de vuelta en «Evidencia», con
    la tabla fuera de la pantalla. No era lentitud —aunque también la había—: era
    que la vista se perdía sola.
    """
    for nodo in _llamadas(_arbol(pagina)):
        if _nombre_llamado(nodo) != "tabs":
            continue
        claves = {kw.arg for kw in nodo.keywords}
        assert "key" in claves, (
            f"{pagina.name}: un `st.tabs` sin `key` en la línea {nodo.lineno}; "
            "la pestaña abierta se pierde en cada recarga"
        )
        assert "on_change" in claves, (
            f"{pagina.name}: `key` solo guarda la pestaña si `on_change` está puesto "
            f"(línea {nodo.lineno})"
        )


def test_las_llaves_de_pestana_no_se_repiten_entre_paginas():
    """Dos `st.tabs` con la misma llave comparten estado y se pisan."""
    vistas: dict[str, str] = {}
    for pagina in PAGINAS_CON_PESTANAS:
        for nodo in _llamadas(_arbol(pagina)):
            if _nombre_llamado(nodo) != "tabs":
                continue
            for kw in nodo.keywords:
                if kw.arg == "key" and isinstance(kw.value, ast.Constant):
                    clave = str(kw.value.value)
                    assert clave not in vistas, (
                        f"«{clave}» se usa en {vistas[clave]} y en {pagina.name}"
                    )
                    vistas[clave] = pagina.name
    assert len(vistas) >= 3, "se esperaban al menos tres grupos de pestañas con llave"


# --------------------------------------------------------------------------------------
# 43.4 · El caché se tira solo cuando el dato cambia
# --------------------------------------------------------------------------------------


def test_la_firma_de_la_base_cambia_cuando_la_base_cambia(tmp_path, monkeypatch):
    """La llave del caché es el tamaño y la fecha del archivo, no un TTL.

    Un TTL sirve datos viejos durante su ventana y recalcula datos frescos al
    salir de ella: se equivoca en las dos direcciones. Esto no se equivoca en
    ninguna —mientras el archivo no cambie, la respuesta es la misma— y no
    obliga a nadie a acordarse de limpiar el caché después de una ingesta.
    """
    import comun

    base = tmp_path / "reit.db"
    base.write_bytes(b"x" * 100)
    monkeypatch.setattr(comun, "RUTA_BD", str(base))
    primera = comun.firma_de_la_base()
    assert primera != (0, 0)
    assert comun.firma_de_la_base() == primera, "la firma no puede moverse sola"

    base.write_bytes(b"x" * 200)
    assert comun.firma_de_la_base() != primera, "la firma no vio crecer la base"


def test_sin_base_la_firma_no_truena(tmp_path, monkeypatch):
    """Antes de la primera carga el archivo no existe, y la página igual se dibuja."""
    import comun

    monkeypatch.setattr(comun, "RUTA_BD", str(tmp_path / "no-existe.db"))
    assert comun.firma_de_la_base() == (0, 0)
