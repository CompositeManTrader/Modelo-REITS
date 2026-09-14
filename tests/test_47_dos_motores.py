"""Prueba 47 — Que la base pueda vivir fuera del contenedor.

El problema que resuelve
------------------------
El modelo guarda todo en un archivo SQLite dentro de la máquina que lo corre. En
Streamlit Cloud esa máquina se recicla, así que cada vez que la página se abre en
frío el archivo ya no está y hay que reconstruirlo entero: ciento setenta y seis
segundos de descargas y parseo para volver a tener lo mismo que había ayer. Lo
que cambia de verdad de un día para otro son los precios y las tasas —diecinueve
segundos—. El resto es trabajo repetido.

La salida es sacar la base de la máquina: un Postgres administrado que sobrevive
al reciclaje. El código ya estaba escrito para permitirlo —``crear_motor`` acepta
una URL desde siempre—, pero *permitirlo* y *funcionar* son cosas distintas, y la
diferencia solo aparece corriéndolo. Aparecieron tres cosas.

Las tres que aparecieron
------------------------
1. **El INSERT fila por fila.** La escritura insertaba una fila a la vez y dejaba
   que el duplicado tronara, para atraparlo con un ``except`` y seguir. SQLite
   tolera una sentencia fallida dentro de una transacción; **Postgres aborta la
   transacción entera** y todo lo que sigue contesta ``current transaction is
   aborted``. La ingesta se caía a los treinta segundos. Se arregla moviendo la
   idempotencia al motor con ``ON CONFLICT DO NOTHING``, que además vuelve la
   escritura un lote en vez de cien mil viajes —que es lo que la haría inservible
   contra una base remota, aunque no tronara—.

2. **``Path`` se come una diagonal.** ``REIT_DB`` se envolvía en ``Path``, y
   ``Path("postgresql://a@b/c")`` devuelve ``postgresql:/a@b/c``. Sin aviso: el
   error sale después, disfrazado de "no encuentro el servidor".

3. **El controlador.** Neon y Supabase entregan la cadena como ``postgresql://``
   —a veces ``postgres://``—, que SQLAlchemy lee como psycopg2, que no está
   instalado. El proyecto usa psycopg 3.

Cómo se corre contra Postgres
-----------------------------
Las pruebas de escritura corren siempre contra SQLite. Si la variable
``REIT_DB_PRUEBA`` apunta a un Postgres, **las mismas** vuelven a correr ahí. Así
la portabilidad se verifica con el mismo cuerpo de prueba en vez de con dos
suites que se desincronizan. Sin la variable se saltan, para que CI no dependa de
tener un servidor.
"""

from __future__ import annotations

import datetime as dt
import inspect
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

RAIZ = Path(__file__).resolve().parent.parent
for _ruta in (RAIZ, RAIZ / "app"):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

from src.datos import esquema  # noqa: E402
from src.datos.repositorio import (  # noqa: E402
    RegistroRechazado,
    Repositorio,
    crear_motor,
    es_servidor,
    url_del_motor,
)

PG_PRUEBA = os.environ.get("REIT_DB_PRUEBA", "")


# --------------------------------------------------------------------------------------
# 47.1 · La URL que el usuario pega
# --------------------------------------------------------------------------------------


def test_la_url_de_neon_se_acepta_tal_cual():
    """Pegar la cadena del proveedor sin editarla es el caso normal, no el raro."""
    url = url_del_motor("postgresql://u:c@ep-x.neon.tech/reits?sslmode=require")
    assert url.startswith("postgresql+psycopg://"), "quedaría en psycopg2, que no está"
    assert url.endswith("@ep-x.neon.tech/reits?sslmode=require"), "se perdió parte de la cadena"


def test_la_url_vieja_de_postgres_tambien():
    """Heroku y algunos Supabase siguen entregando ``postgres://``."""
    assert url_del_motor("postgres://u:c@db.supabase.co:5432/postgres").startswith(
        "postgresql+psycopg://"
    )


def test_traducir_dos_veces_da_lo_mismo_que_una():
    """La URL pasa por la traducción en la configuración y otra vez al crear el motor.

    Sin esta propiedad, la segunda vuelta produce ``sqlite:///sqlite:////ruta`` y
    el error que sale —"unable to open database file"— no menciona la causa. Se
    descubrió corriendo el migrador, no leyendo la función.
    """
    for entrada in (
        "postgresql://u:c@ep-x.neon.tech/reits",
        "postgres://u:c@db.supabase.co:5432/postgres",
        "postgresql+psycopg://postgres@/reits",
        "/home/usuario/reit.db",
        Path("data/reit.db"),
    ):
        una = url_del_motor(entrada)
        assert url_del_motor(una) == una, f"traducir dos veces cambió {entrada!r}"


def test_un_archivo_local_sigue_siendo_sqlite():
    """El camino de siempre no puede romperse por abrirle la puerta a otro motor."""
    assert url_del_motor(Path("data/reit.db")) == "sqlite:///data/reit.db"
    assert url_del_motor("/tmp/otra.db") == "sqlite:////tmp/otra.db"


def test_envolver_la_url_en_path_la_rompe():
    """La regresión #2, escrita como prueba porque no se ve leyendo el código.

    ``Path`` colapsa la doble diagonal en silencio. Esta prueba existe para que
    nadie vuelva a poner ``Path(os.environ[...])`` alrededor de la configuración
    de la base sin enterarse de lo que hace.
    """
    url = "postgresql://u:c@ep-x.neon.tech/reits"
    assert str(Path(url)) != url, "si esto cambia, el envoltorio dejó de ser peligroso"
    assert url_del_motor(url).count("//") == 1, "la URL quedó mal formada"


def test_la_configuracion_no_envuelve_la_url(monkeypatch):
    """Lo mismo, pero sobre la variable de entorno de verdad."""
    monkeypatch.setenv("REIT_DB", "postgresql://u:c@ep-x.neon.tech/reits")
    import importlib

    from src import config

    importlib.reload(config)
    try:
        assert isinstance(config.RUTA_BD, str)
        assert config.RUTA_BD == "postgresql://u:c@ep-x.neon.tech/reits"
    finally:
        monkeypatch.delenv("REIT_DB")
        importlib.reload(config)


# --------------------------------------------------------------------------------------
# 47.2 · La escritura, en los dos motores
# --------------------------------------------------------------------------------------


@pytest.fixture(params=["sqlite", "postgresql"])
def repo_limpio(request, tmp_path):
    """El mismo repositorio vacío, una vez por motor disponible."""
    if request.param == "sqlite":
        return Repositorio(ruta=tmp_path / "prueba.db")
    if not PG_PRUEBA:
        pytest.skip("Sin REIT_DB_PRUEBA: no hay Postgres contra el cual correr.")
    motor = crear_motor(PG_PRUEBA, crear=False)
    with motor.begin() as cx:
        for tabla in reversed(esquema.metadata.sorted_tables):
            cx.execute(text(f'DROP TABLE IF EXISTS "{tabla.name}" CASCADE'))
    esquema.metadata.create_all(motor)
    return Repositorio(motor=motor)


def hecho(concepto: str, *, publicacion: dt.date | None = None, valor: float = 1.0) -> dict:
    return {
        "ticker": "O",
        "concepto": concepto,
        "periodo_tipo": "Q",
        "fecha_dato": dt.date(2024, 3, 31),
        "fecha_publicacion": publicacion or dt.date(2024, 5, 1),
        "valor": valor,
        "unidad": "USD",
        "fuente": "prueba",
        "es_primario": True,
        "estado": "valido",
    }


def test_re_correr_la_ingesta_no_inserta_nada(repo_limpio):
    """La idempotencia es de la ingesta, no del motor: tiene que darse en los dos."""
    filas = [hecho(f"c{n}") for n in range(20)]
    assert repo_limpio.guardar_hechos(filas) == 20
    assert repo_limpio.guardar_hechos(filas) == 0, "la segunda corrida duplicó la base"


def test_el_conteo_de_un_lote_mezclado_es_exacto(repo_limpio):
    """El resumen de la ingesta lo reporta al usuario: un conteo inflado miente."""
    repo_limpio.guardar_hechos([hecho(f"c{n}") for n in range(10)])
    mezclado = [hecho("c3"), hecho("nuevo_a"), hecho("c7"), hecho("nuevo_b"), hecho("c1")]
    assert repo_limpio.guardar_hechos(mezclado) == 2


def test_las_filas_repetidas_dentro_del_mismo_lote_se_colapsan(repo_limpio):
    """La versión fila por fila resolvía esto sin querer; la de lote, no.

    Al chocar la segunda copia contra la primera ya escrita, el INSERT uno a uno
    deduplicaba dentro de la lista por accidente. Escribir en lote solo conserva
    esa propiedad si el motor la da, así que se mide en vez de suponerse.
    """
    lote = [hecho("a"), hecho("b"), hecho("a"), hecho("c"), hecho("b")]
    assert repo_limpio.guardar_hechos(lote) == 3


def test_una_reexpresion_es_una_fila_nueva_no_un_duplicado(repo_limpio):
    """P1: cambia la fecha de publicación, así que no es la misma celda."""
    repo_limpio.guardar_hechos([hecho("ffo", valor=100.0)])
    nuevas = repo_limpio.guardar_hechos(
        [hecho("ffo", publicacion=dt.date(2024, 8, 1), valor=110.0)]
    )
    assert nuevas == 1, "la reexpresión se tomó por duplicado y se perdió"
    todas = repo_limpio.hechos(
        asof=dt.date(2024, 12, 31), tickers="O", conceptos="ffo", vigentes=False
    )
    assert len(todas) == 2


def test_un_lote_grande_entra_completo(repo_limpio):
    """Más que el tamaño de lote, para que el troceo se ejerza de verdad."""
    filas = [hecho(f"masivo_{n}") for n in range(1200)]
    assert repo_limpio.guardar_hechos(filas) == 1200
    assert repo_limpio.guardar_hechos(filas) == 0


# --------------------------------------------------------------------------------------
# 47.3 · Lo que el esquema rechaza sigue rechazándose, y dice cuál
# --------------------------------------------------------------------------------------


def test_el_esquema_sigue_rechazando_la_publicacion_imposible(repo_limpio):
    """Un filing no puede reportar un trimestre que todavía no termina."""
    with pytest.raises(RegistroRechazado):
        repo_limpio.guardar_hechos([hecho("ffo", publicacion=dt.date(2020, 1, 1))])


def test_el_rechazo_nombra_la_fila_culpable(repo_limpio):
    """Sin la fila, el error no sirve: casi siempre es el parser leyendo una guía.

    Es lo que obliga al rescate fila por fila cuando un lote truena. Escribir en
    lote es rápido pero anónimo, y un error anónimo en una ingesta de cien mil
    filas no se puede perseguir.
    """
    buenas = [hecho(f"ok_{n}") for n in range(30)]
    mala = hecho("la_mala", publicacion=dt.date(2019, 6, 30))
    with pytest.raises(RegistroRechazado) as capturado:
        repo_limpio.guardar_hechos([*buenas, mala])
    assert "la_mala" in str(capturado.value)


def test_una_fila_rechazada_no_deja_media_ingesta_escrita(repo_limpio):
    """O entra el lote o no entra: es lo que hacía la versión anterior."""
    mala = hecho("la_mala", publicacion=dt.date(2019, 6, 30))
    with pytest.raises(RegistroRechazado):
        repo_limpio.guardar_hechos([hecho("buena"), mala])
    quedaron = repo_limpio.hechos(asof=dt.date(2024, 12, 31), tickers="O", vigentes=False)
    assert quedaron.empty, "quedó escrita parte de una llamada que falló"


def test_una_base_vacia_no_tiene_hechos(repo_limpio):
    """La pregunta que decide si la aplicación reconstruye todo al abrir."""
    assert repo_limpio.hay_hechos() is False
    repo_limpio.guardar_hechos([hecho("ffo")])
    assert repo_limpio.hay_hechos() is True


def test_la_firma_se_mueve_con_cada_escritura(repo_limpio):
    """La llave del caché tiene que ver TODA escritura, o la pantalla miente.

    Es la falla peligrosa de la mudanza, porque no truena. La firma miraba el
    tamaño y la fecha de un archivo; sobre un servidor no hay archivo, el ``stat``
    fallaba y devolvía ``(0, 0)`` para siempre. El caché nunca se habría
    invalidado y la pantalla habría seguido sirviendo las cifras del primer
    arranque, sin un solo error en ningún lado.

    Se verifica escribiendo de verdad en cada tabla que la pantalla lee, en vez de
    razonar sobre cuáles importan.
    """
    previa = repo_limpio.firma()
    escrituras = [
        ("hechos", lambda: repo_limpio.guardar_hechos([hecho("ffo")])),
        ("precios", lambda: repo_limpio.guardar_precios([{
            "ticker": "O", "fecha_dato": dt.date(2024, 3, 28),
            "fecha_publicacion": dt.date(2024, 3, 28), "cierre_crudo": 53.4,
            "fuente": "prueba", "metodo": "cierre",
        }])),
        ("tasas", lambda: repo_limpio.guardar_tasas([{
            "serie": "DGS10", "fecha_dato": dt.date(2024, 3, 28),
            "fecha_publicacion": dt.date(2024, 3, 28), "valor": 4.2, "fuente": "prueba",
        }])),
        ("bitácora", lambda: repo_limpio.registrar_bitacora("prueba", "una escritura")),
    ]
    for nombre, escribir in escrituras:
        escribir()
        actual = repo_limpio.firma()
        assert actual != previa, f"escribir en {nombre} no movió la firma del caché"
        previa = actual


def test_marcar_un_hecho_mueve_la_firma_por_la_bitacora(repo_limpio):
    """El único caso que un identificador nuevo no delata: un UPDATE.

    Marcar un hecho como sospechoso no inserta nada, así que ningún ``max(id)``
    de las tablas de datos se mueve. La firma lo ve porque la bitácora entra en
    ella y porque toda operación que marca hechos —la ingesta, la reconstrucción,
    las reparaciones— deja ahí su registro. Esta prueba fija esa dependencia: si
    alguien deja de registrarla, aquí se entera.
    """
    repo_limpio.guardar_hechos([hecho("ffo")])
    fila = repo_limpio.hechos(asof=dt.date(2024, 12, 31), tickers="O", vigentes=False)
    id_hecho = int(fila["id"].iloc[0])

    antes = repo_limpio.firma()
    assert repo_limpio.marcar_hechos({id_hecho: "sospechoso de escala"}, estado="sospechoso") == 1
    repo_limpio.registrar_bitacora("validacion", "un hecho marcado")
    assert repo_limpio.firma() != antes


def test_despues_de_un_rechazo_la_base_sigue_usable(repo_limpio):
    """La regresión #1 en una línea.

    En Postgres, una sentencia fallida aborta la transacción entera: todo lo que
    viene después contesta ``current transaction is aborted``. Si el rescate no
    aislara cada fila en un SAVEPOINT, esta escritura de aquí abajo tronaría.
    """
    with pytest.raises(RegistroRechazado):
        repo_limpio.guardar_hechos([hecho("mala", publicacion=dt.date(2019, 6, 30))])
    assert repo_limpio.guardar_hechos([hecho("despues")]) == 1


# --------------------------------------------------------------------------------------
# 47.4 · Lo que la aplicación hace con todo esto
# --------------------------------------------------------------------------------------


def test_se_distingue_un_servidor_de_un_archivo():
    """De esta pregunta cuelgan las dos decisiones caras del arranque."""
    assert es_servidor("postgresql://u:c@ep-x.neon.tech/reits") is True
    assert es_servidor("postgres://u:c@db.supabase.co/postgres") is True
    assert es_servidor(Path("data/reit.db")) is False
    assert es_servidor("/tmp/reit.db") is False


def test_la_marca_del_cache_no_lleva_la_contrasena():
    """Una llave de caché acaba en trazas y en registros.

    La cadena de un Postgres administrado trae usuario y contraseña. Para
    distinguir una base de otra basta el servidor y su nombre, así que el
    secreto no tiene por qué viajar hasta ahí.
    """
    import comun

    cadena = "postgresql://alberto:CLAVE_SECRETA@ep-x.neon.tech/reits?sslmode=require"
    original = comun.RUTA_BD
    try:
        comun.RUTA_BD = cadena
        marca = comun.marca_de_la_base()
        assert "CLAVE_SECRETA" not in marca
        assert "alberto" not in marca
        assert "ep-x.neon.tech" in marca, "la marca ya no distingue una base de otra"
    finally:
        comun.RUTA_BD = original


def test_sobre_un_archivo_la_firma_sigue_saliendo_del_disco(tmp_path):
    """El camino de siempre no puede volverse más caro por abrirle la puerta a otro motor.

    Sobre un archivo, el tamaño y la fecha contestan sin abrir la base ni hablar
    con nadie. Hacerlo pasar por el repositorio costaría una conexión por
    recarga a cambio de nada.
    """
    import comun

    base = tmp_path / "reit.db"
    base.write_bytes(b"x" * 100)
    original = comun.RUTA_BD
    try:
        comun.RUTA_BD = str(base)
        primera = comun.firma_de_la_base()
        assert primera != (0, 0)
        base.write_bytes(b"x" * 300)
        assert comun.firma_de_la_base() != primera
    finally:
        comun.RUTA_BD = original


def test_sobre_un_servidor_inalcanzable_la_pantalla_no_truena():
    """Una base caída tiene que dar una pantalla vacía, no una traza."""
    import comun

    original = comun.RUTA_BD
    try:
        comun.RUTA_BD = "postgresql://u:c@127.0.0.1:1/no-existe?connect_timeout=1"
        assert comun.firma_de_la_base() == (0, 0)
        assert comun.base_existe() is False
    finally:
        comun.RUTA_BD = original


def test_la_base_se_publica_antes_de_leer_la_configuracion():
    """El orden es todo el asunto, y no se ve corriendo la aplicación.

    ``src.config`` resuelve la ruta de la base en el momento en que se importa.
    Si el secreto ``REIT_DB`` se publicara después —como se publican los demás,
    que sí pueden esperar— la aplicación se conectaría al archivo local, que en
    Streamlit Cloud no existe, y reconstruiría todo en cada apertura. Sin error:
    exactamente el síntoma que la mudanza viene a quitar.

    Se verifica sobre el ORDEN DEL TEXTO porque es donde vive la garantía: una
    prueba que importe el módulo ya llega tarde para notar la diferencia.
    """
    fuente = (RAIZ / "app" / "comun.py").read_text(encoding="utf-8").splitlines()
    llamada = next(
        i for i, linea in enumerate(fuente)
        if linea.strip() == "_publicar_la_base_antes_de_configurar()"
    )
    importa = next(
        i for i, linea in enumerate(fuente) if linea.startswith("from src.config import")
    )
    assert llamada < importa, (
        "REIT_DB se publica después de importar src.config: la ruta ya se resolvió"
    )


def test_el_secreto_de_la_base_no_se_publica_junto_a_los_demas():
    """Los otros secretos pueden esperar; este no, y la lista no debe sugerir que sí."""
    import comun

    fuente = comun._publicar_secretos.__doc__ or ""
    assert "REIT_DB" not in fuente
    codigo = (RAIZ / "app" / "comun.py").read_text(encoding="utf-8")
    tardios = codigo.split('for clave in ("BANXICO_TOKEN"')[1].split(")")[0]
    assert "REIT_DB" not in tardios, "REIT_DB quedó en la publicación tardía"


# --------------------------------------------------------------------------------------
# 47.5 · Lo que la mudanza deja de traer, y hay que traer aparte
# --------------------------------------------------------------------------------------
#
# Mientras el disco era efímero la base moría con el contenedor, así que la
# aplicación ingestaba TODO en cada arranque y los precios llegaban frescos por
# accidente. Con una base que sobrevive, esa ingesta ya no corre. Si nadie trae lo
# diario, los precios se congelan el día de la mudanza y nada lo dice: la pantalla
# sigue dibujando, con las cifras de entonces.


def test_el_refresco_diario_no_toca_la_sec():
    """Lo caro de la ingesta son ochocientos 8-K y diez companyfacts.

    Eso reconstruye cifras trimestrales que no cambiaron desde el último reporte:
    pertenece a la ventana de resultados, cuatro veces al año, no a la apertura de
    una página. Si esta puerta llamara a cualquiera de esos, dejaría de ser la
    puerta barata y volveríamos al arranque de tres minutos.
    """
    import inspect

    from src.ingesta.orquestador import refrescar_diario

    cuerpo = inspect.getsource(refrescar_diario)
    for caro in ("ingestar_fundamentales", "ingestar_estados", "ingestar_xbrl", "ClienteEdgar"):
        assert caro not in cuerpo, f"el refresco diario llama a {caro}, que es la parte cara"
    for barato in ("ingestar_precios", "guardar_tasas"):
        assert barato in cuerpo, f"el refresco diario no trae {barato}"


def test_la_aplicacion_refresca_lo_diario_cuando_la_base_ya_existe():
    """La rama nueva: base presente, ingesta completa saltada, precios igual al día.

    Se verifica sobre el texto porque es una decisión de FLUJO —qué se llama
    cuando NO se entra al `if`— y eso no se ve en el resultado de ninguna función.
    """
    import inspect

    import comun

    cuerpo = inspect.getsource(comun.exigir_base)
    assert "_refrescar_lo_diario_una_sola_vez" in cuerpo, (
        "con la base ya presente nadie trae precios ni tasas: se congelan"
    )
    despues_del_if = cuerpo.split("if not base_existe():")[1]
    assert "return obtener_repo()" in despues_del_if.split("_refrescar_lo_diario")[0], (
        "la rama de primera carga debe salir antes, para no refrescar dos veces"
    )


def test_el_refresco_caduca_con_el_dia_y_no_con_el_proceso():
    """Lo único de esta aplicación que sí debe caducar con el reloj.

    Todo lo demás se invalida por contenido —la firma de la base— y eso es
    deliberado. Los precios son la excepción porque lo que los mueve, que abra la
    bolsa, también va con el reloj: un servidor que lleva tres días arriba tiene
    que traer los de hoy.
    """
    import inspect

    import comun

    firma = inspect.signature(comun._refrescar_lo_diario_una_sola_vez)
    assert "dia" in firma.parameters, "sin el día en la llave, el refresco ocurre una sola vez"
    llamada = inspect.getsource(comun.exigir_base)
    assert "dt.date.today().isoformat()" in llamada


def test_el_refresco_se_puede_apagar_para_ci():
    """En CI la pregunta es si las páginas dibujan, no si FRED está arriba.

    Sin el interruptor, un tropiezo de la red durante la prueba de humo se leería
    como una falla de la interfaz, que es el peor tipo de falso positivo: manda a
    buscar el error donde no está.
    """
    import comun

    cuerpo = inspect.getsource(comun._refrescar_lo_diario_una_sola_vez)
    assert "REIT_SIN_REFRESCO" in cuerpo
    flujo = (RAIZ / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "REIT_SIN_REFRESCO" in flujo, "CI no lo apaga: la prueba de humo depende de la red"


def test_el_migrador_no_imprime_la_contrasena():
    """El script se corre a mano y su salida se pega en chats y en tickets.

    La cadena de un Postgres administrado trae usuario y contraseña. Vale para
    los dos lados: el mismo script sirve para traerse la base del servidor a la
    laptop, así que el origen puede ser el que tiene el secreto.
    """
    from scripts.migrar import sin_credenciales

    limpia = sin_credenciales("postgresql+psycopg://alberto:CLAVE@ep-x.neon.tech/reits?ssl=on")
    assert "CLAVE" not in limpia
    assert "alberto" not in limpia
    assert "ep-x.neon.tech/reits" in limpia, "ya no se sabe a qué base va"
    ruta = "sqlite:////home/usuario/reit.db"
    assert sin_credenciales(ruta) == ruta


# --------------------------------------------------------------------------------------
# 47.6 · Armar la base en un servidor que no se puede ver
# --------------------------------------------------------------------------------------
#
# Cuando la base vive afuera, quien la arma no la tiene enfrente: corre un trabajo
# en GitHub y lee un reporte. Eso cambia qué cuenta como terminar bien. Un trabajo
# que sale en verde con una tabla vacía es peor que uno que truena, porque el que
# lo corrió se va tranquilo y el error aparece días después, al abrir la página.


def test_los_conteos_cubren_todas_las_tablas(repo_limpio):
    """El reporte tiene que poder decir «esta quedó vacía», y para eso debe nombrarlas."""
    conteos = repo_limpio.conteos()
    assert set(conteos) == {t.name for t in esquema.metadata.sorted_tables}
    assert all(v == 0 for v in conteos.values()), "la base de prueba no estaba limpia"
    repo_limpio.guardar_hechos([hecho("ffo")])
    assert repo_limpio.conteos()["hechos"] == 1


def test_el_refresco_diario_siembra_las_anclas(repo_limpio, monkeypatch):
    """La regresión que destapó armar una base desde cero.

    Las anclas son cierres capturados a mano y la verificación más fuerte de P2.
    Viven en el código, no en una fuente externa, y `correr_ingesta` las sembraba;
    la puerta diaria no. En una base recién creada `anclas_precio` quedaba en 0 y
    `ingestar_precios` caía a la prueba de coherencia aritmética —más débil— SIN
    DECIRLO: la serie se guardaba aprobada igual. Se vio contando filas, no
    leyendo el código.
    """
    from src.ingesta import tasas as mod_tasas
    from src.ingesta.orquestador import refrescar_diario

    monkeypatch.setattr(mod_tasas, "ingestar_fred", lambda *a, **k: [])
    monkeypatch.setattr(mod_tasas, "ingestar_banxico", lambda *a, **k: [])

    assert repo_limpio.conteos()["anclas_precio"] == 0
    refrescar_diario(repo_limpio, tickers=[])  # sin emisoras: no sale a la red
    conteos = repo_limpio.conteos()
    assert conteos["anclas_precio"] > 0, "los precios se validarían con la prueba floja"
    assert conteos["emisores"] > 0, "una base nueva quedaría sin catálogo de emisoras"


def test_las_anclas_se_siembran_ANTES_de_pedir_precios():
    """El orden es el bug, no la presencia.

    Sembrarlas después del ciclo de precios deja la base correcta al final y aun
    así valida la primera pasada con la prueba débil. Una prueba de resultado no
    nota la diferencia; el orden del texto, sí.
    """
    import inspect

    from src.ingesta.orquestador import refrescar_diario

    cuerpo = inspect.getsource(refrescar_diario)
    # Se buscan las LLAMADAS, no los nombres: el comentario que explica esto
    # menciona `ingestar_precios` más arriba, y buscar el nombre suelto encontraba
    # el comentario en vez del código.
    assert cuerpo.index("repo.guardar_anclas(") < cuerpo.index("= ingestar_precios("), (
        "las anclas se siembran después de pedir precios: la primera pasada se "
        "validaría sin ellas"
    )


def test_existe_la_puerta_de_linea_de_comandos_para_lo_diario():
    """Es lo que corre el trabajo de GitHub; sin ella el flujo no tiene qué llamar."""
    fuente = (RAIZ / "scripts" / "ingesta.py").read_text(encoding="utf-8")
    assert "--solo-diario" in fuente
    assert "refrescar_diario" in fuente


def test_el_flujo_de_github_exige_que_el_secreto_apunte_al_servidor():
    """El modo de falla real es el secreto VACÍO, no el ausente.

    `REIT_DB: ${{ secrets.REIT_DB }}` define la variable como cadena vacía cuando
    el secreto no existe, y entonces el código cae calladamente al archivo local:
    el trabajo llenaría una base del runner que se borra al apagarse y terminaría
    EN VERDE. Es exactamente el error que tiene hoy `estados.yml` con
    SEC_USER_AGENT, y es la razón de que esta prueba exista.
    """
    flujo = (RAIZ / ".github" / "workflows" / "base_en_el_servidor.yml").read_text(
        encoding="utf-8"
    )
    assert '-z "$REIT_DB"' in flujo, "no verifica que el secreto venga vacío"
    assert "postgresql://*" in flujo, "no verifica que apunte a un servidor"
    assert "conteos()" in flujo, "el trabajo no reporta qué dejó en la base"
    assert flujo.count("exit 1") >= 2, "las verificaciones no tumban el trabajo"


def test_el_flujo_de_github_no_imprime_la_cadena_de_conexion():
    """La cadena trae usuario y contraseña, y los registros de Actions se comparten.

    Lo que se persigue es imprimir el VALOR (``$REIT_DB``), no mencionar el
    nombre: los mensajes de error tienen que poder decir «falta el secreto
    REIT_DB» o no sirven de nada. La primera versión de esta prueba marcaba
    cualquier ``echo`` que tuviera el nombre y señalaba justo ese mensaje.
    """
    flujo = (RAIZ / ".github" / "workflows" / "base_en_el_servidor.yml").read_text(
        encoding="utf-8"
    )
    for linea in flujo.splitlines():
        limpia = linea.strip()
        if limpia.startswith("#"):
            continue
        expande = "$REIT_DB" in limpia or "${REIT_DB" in limpia
        if expande and limpia.startswith(("echo ", "printf ", "cat ")):
            raise AssertionError(f"esta línea imprimiría la cadena completa: {limpia}")
