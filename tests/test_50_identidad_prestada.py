"""Prueba 50 — Que el repositorio no traiga la identidad de nadie de fábrica.

Lo que había
-----------
``src/config.py`` traía el correo personal del dueño del repositorio como valor
por omisión del User-Agent de la SEC::

    SEC_USER_AGENT = os.environ.get(
        "SEC_USER_AGENT", "Modelo-REITS/0.1 (<el correo personal del dueño>)"
    )

Los tres flujos de GitHub ya exigían el secreto, el README ya decía que era
obligatorio y ``scripts/ingesta.py`` lo decía en su docstring. Nada de eso era
cierto: había un valor por omisión que FUNCIONABA, así que nadie tenía que
configurar nada. La documentación describía una disciplina que el código no
imponía, que es la peor combinación: se cree que está resuelto.

Por qué importa más de lo que parece
------------------------------------
Lo obvio es la privacidad, y es lo de menos: el repositorio es público y el
correo quedaba legible. Lo caro es operativo. La SEC mide y **bloquea por
User-Agent**. Con un correo real de fábrica, cualquiera que clone este
repositorio y corra la ingesta le habla a la SEC identificado como su dueño, sin
querer y sin enterarse. Si le pega fuerte —un ciclo sin limitador, una prueba a
mano— a quien la SEC bloquea es al dueño del correo, y la tubería que se cae es
la suya, por tráfico que nunca generó.

O sea: no era un descuido de privacidad, era un riesgo de disponibilidad con la
cuenta de otro.

Las dos reglas, y por qué son dos
---------------------------------
Son invariantes distintas y por eso no se juntan en una sola prueba:

1. **El valor por omisión no sirve para hablar con la SEC.** Es una regla sobre
   el COMPORTAMIENTO: lo que se prohíbe es que exista un respaldo que funcione,
   sea de quien sea el correo. Un valor por omisión utilizable es el defecto,
   aunque el correo fuera de mentiras.
2. **No hay correos de buzón personal en el árbol.** Es una regla sobre el
   CONTENIDO, y cubre el próximo pegado venga de donde venga, no solo este
   renglón.

Medido sobre el árbol versionado antes del arreglo: catorce cadenas con forma de
correo, TRECE de ellas hostnames falsos de prueba (``c@ep-x.neon.tech``,
``CLAVE@ep-x.neon.tech``) o ejemplos documentados (``tu-correo@ejemplo.com``), y
UNA real. La regla 2 marca exactamente esa. Cero falsos positivos.

Lo que la regla 2 NO cubre, dicho de frente: un correo corporativo
(``alguien@sufirma.com``) no se distingue de un hostname de servicio sin una
lista de dominios que habría que mantener a mano, y una lista así envejece mal.
Se persiguen los buzones de consumo porque es donde cae un correo personal
pegado sin pensar, que es el caso que de verdad pasó. No es una red completa y no
se presenta como tal.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.config import RAIZ, SEC_USER_AGENT
from src.ingesta.edgar import ClienteEdgar

# --------------------------------------------------------------------------------------
# Regla 1 — el valor por omisión no es utilizable
# --------------------------------------------------------------------------------------


def test_el_user_agent_por_omision_no_sirve_para_hablar_con_la_sec():
    """Sin ``SEC_USER_AGENT`` en el entorno, el valor por omisión debe ser inservible.

    Esta es la prueba que faltaba. Todo lo demás —los flujos, el README, el
    docstring del script— ya decía que el secreto era obligatorio; nadie
    verificaba que el código no tuviera una salida por atrás.
    """
    import os

    if os.environ.get("SEC_USER_AGENT"):
        pytest.skip("hay SEC_USER_AGENT en el entorno: aquí no se ve el valor por omisión")

    assert "@" not in SEC_USER_AGENT, (
        "El valor por omisión de SEC_USER_AGENT trae un correo, así que la ingesta "
        "corre sin que nadie configure nada, usando la identidad de quien lo haya "
        "escrito. Tiene que ser inservible para que falle temprano."
    )


def test_el_cliente_edgar_se_niega_a_construirse_con_el_valor_por_omision():
    """La negativa va al construir el cliente, no al pedir la primera página.

    Importa DÓNDE falla. Si fallara en la primera solicitud, ya habría corrido
    media ingesta y el error llegaría mezclado con un 403 de la SEC, que se lee
    como un problema de red. Al construirse, el mensaje es inequívoco.
    """
    with pytest.raises(ValueError) as excinfo:
        ClienteEdgar(user_agent="Modelo-REITS/0.1 (SIN CONFIGURAR)")

    mensaje = str(excinfo.value)
    # No basta con que truene: el mensaje es el único lugar donde alguien que se
    # topa con esto se entera de qué hacer, y son tres almacenes distintos.
    assert "SEC_USER_AGENT" in mensaje
    for lugar in ("Streamlit", "Actions"):
        assert lugar in mensaje, f"el mensaje no dice dónde va el secreto si corre en {lugar}"


def test_un_user_agent_con_correo_si_construye_el_cliente(tmp_path):
    """La otra mitad: la guarda no puede estar rechazando todo."""
    cliente = ClienteEdgar(
        user_agent="Modelo-REITS/0.1 (alguien@ejemplo.com)", dir_cache=tmp_path
    )
    assert cliente.sesion.headers["User-Agent"] == "Modelo-REITS/0.1 (alguien@ejemplo.com)"


# --------------------------------------------------------------------------------------
# Regla 2 — ningún buzón personal en el árbol
# --------------------------------------------------------------------------------------

# Dónde puede caer un correo pegado sin pensar. Se listan sufijos en vez de
# recorrer todo porque `data/` son CSV comprimidos de hechos de la SEC: binarios
# donde un correo no aterriza, y leerlos completos haría lenta una prueba que
# tiene que ser barata para que nadie la quite.
SUFIJOS_DE_TEXTO = (".py", ".md", ".yml", ".yaml", ".toml", ".txt", ".cfg", ".ini")

DIRECTORIOS_IGNORADOS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "data"}

# Buzones de consumo. Es donde cae un correo personal, y se distinguen sin
# ambigüedad de un hostname de servicio como `ep-x.neon.tech`.
DOMINIOS_DE_BUZON = (
    "gmail.com",
    "googlemail.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "yahoo.com",
    "yahoo.com.mx",
    "icloud.com",
    "me.com",
    "proton.me",
    "protonmail.com",
    "aol.com",
    "zoho.com",
    "yandex.com",
)

_CORREO = re.compile(
    r"[A-Za-z0-9._%+-]+@(?:" + "|".join(re.escape(d) for d in DOMINIOS_DE_BUZON) + r")\b",
    re.IGNORECASE,
)


def _archivos_de_texto() -> list[Path]:
    encontrados: list[Path] = []
    for ruta in RAIZ.rglob("*"):
        if not ruta.is_file() or ruta.suffix.lower() not in SUFIJOS_DE_TEXTO:
            continue
        if DIRECTORIOS_IGNORADOS & set(ruta.relative_to(RAIZ).parts):
            continue
        encontrados.append(ruta)
    return encontrados


def test_ningun_correo_personal_en_el_arbol():
    """Ni en el código, ni en la documentación, ni en los flujos.

    Esta prueba mira TODO el árbol y no solo `config.py`, porque el renglón que
    se arregló ya no es el riesgo: el riesgo es el próximo, y va a estar en otro
    lado.
    """
    archivos = _archivos_de_texto()
    # Si el recorrido se rompe —una ruta mal armada, un filtro de más— la prueba
    # pasaría sin mirar nada, que es el modo de falla de cualquier verificación
    # que barre archivos. Se ancla contra un piso que el repositorio ya rebasa.
    assert len(archivos) > 50, f"solo se revisaron {len(archivos)} archivos; el barrido se rompió"

    hallazgos: list[str] = []
    for ruta in archivos:
        try:
            texto = ruta.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, linea in enumerate(texto.splitlines(), start=1):
            for correo in _CORREO.findall(linea):
                hallazgos.append(f"{ruta.relative_to(RAIZ)}:{n}: {correo}")

    assert not hallazgos, (
        "Hay correos de buzón personal en el repositorio, que es público:\n  "
        + "\n  ".join(hallazgos)
        + "\nUn correo de contacto se configura por variable de entorno o por "
        "secreto, nunca escrito en un archivo versionado."
    )


def test_la_regla_de_correos_si_detecta_uno(tmp_path, monkeypatch):
    """Que la regla 2 no sea un barrido que siempre sale limpio.

    Una prueba que recorre archivos y no encuentra nada se ve idéntica a una que
    no recorrió nada. Aquí se le planta un correo y se exige que lo vea.
    """
    # El correo se arma por partes a propósito: escribirlo completo aquí lo
    # volvería un hallazgo de la prueba anterior, que barre TAMBIÉN este archivo.
    # Ese roce es la señal de que el barrido no tiene puntos ciegos, así que se
    # respeta en vez de excluir el archivo —una exclusión sería justo el lugar
    # donde después nadie mira—.
    buzon = "persona.real" + "@" + "gmail" + ".com"
    (tmp_path / "config_falso.py").write_text(
        f'CONTACTO = "Modelo-REITS/0.1 ({buzon})"\n', encoding="utf-8"
    )
    encontrados = _CORREO.findall((tmp_path / "config_falso.py").read_text(encoding="utf-8"))
    assert encontrados == [buzon]

    # Y que no se lleve entre las patas a los hostnames de prueba, que son trece
    # en este repositorio y son legítimos.
    for inocente in (
        "postgresql://u:c@ep-x.neon.tech/db",
        "postgresql://u:c@db.supabase.co/db",
        "Modelo-REITS tu-correo@ejemplo.com",
    ):
        assert not _CORREO.findall(inocente), f"falso positivo sobre {inocente}"
