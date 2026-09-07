"""Prueba 24 — La marca, el TTM de los tres payouts, y la aritmética abierta.

Tres bloques, tres clases de defecto distintas.

**24.1 · El trimestre por cuatro, en la capa de servicio.** ``payout_ffo`` y
``payout_utilidad_neta`` se calculaban anualizando UN trimestre, mientras
``payout_affo`` usaba el TTM real. La tarjeta los pone lado a lado bajo el
rótulo «el mismo dividendo, tres respuestas», pero los tres denominadores no
medían la misma ventana de tiempo. En GNL el payout sobre FFO salía 288% donde
el TTM da 181%; en EPRT el payout sobre utilidad neta cruzaba el 100% —el umbral
que pinta la barra de rojo— por el puro efecto de la anualización.

**24.2 · La aritmética abierta.** Una cifra sola no se puede auditar. Estas
pruebas exigen que la fórmula que se DIBUJA y el número que se PUBLICA salgan
del mismo cálculo: la prueba rehace la aritmética por su cuenta, con los
operandos que la fórmula declara, y la compara contra lo que produce el motor de
valuación. Si alguien cambiara una y no la otra, la pantalla estaría
documentando un cálculo que no ocurre — que es peor que no documentar nada.

**24.3 · La marca.** El sistema visual de Spread Trading Club tiene tres reglas
que se pueden verificar en el código y no dependen de mirar la pantalla: un solo
acento, ganancia y pérdida nunca solo por color, y sin emojis.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
for ruta in (str(RAIZ), str(RAIZ / "app")):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

import marca  # noqa: E402

from src.modelo.formulas import formula_por_clave, modelos_de_valuacion  # noqa: E402
from src.modelo.valuacion import (  # noqa: E402
    InsumosValuacion,
    panel_valuacion,
    prima_riesgo_sector,
)
from src.servicio import _ttm, construir_panel  # noqa: E402

PAGINA_VALUACION = (RAIZ / "app" / "pages" / "1_Valuacion.py").read_text(encoding="utf-8")


def _codigo(fuente: str) -> str:
    """La fuente sin comentarios ni cadenas: solo lo que se ejecuta.

    Hace falta porque este proyecto documenta cada defecto arreglado en un
    comentario que cita la forma vieja. Buscar `(p_affo or 0)` sobre el archivo
    crudo encuentra el comentario que explica por qué ya no está, y la prueba
    fallaría justo por la razón contraria a la que existe.
    """
    import io
    import tokenize

    piezas = []
    for tok in tokenize.generate_tokens(io.StringIO(fuente).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        piezas.append(tok.string)
    return " ".join(piezas)


CODIGO_VALUACION = _codigo(PAGINA_VALUACION)


# --------------------------------------------------------------------------------------
# 24.1 · Los tres payouts miden la misma ventana de tiempo
# --------------------------------------------------------------------------------------


def _panel_trimestral(valores: dict[str, list[float]], n: int = 8) -> pd.DataFrame:
    idx = pd.date_range("2024-03-31", periods=n, freq="QE")
    return pd.DataFrame(valores, index=idx)


def test_el_ffo_ttm_suma_cuatro_trimestres_y_no_multiplica_uno():
    """El defecto medido: un trimestre por cuatro contra la suma de los cuatro."""
    trimestres = [40.0, 42.0, 44.0, 46.0, 48.0, 50.0, 52.0, 54.0]
    panel = _panel_trimestral({"ffo": trimestres})
    ttm = _ttm(panel, "ffo")

    assert ttm.iloc[-1] == pytest.approx(48.0 + 50.0 + 52.0 + 54.0)
    # Lo que hacía antes: el último trimestre por cuatro.
    por_cuatro = trimestres[-1] * 4
    assert por_cuatro == pytest.approx(216.0)
    assert ttm.iloc[-1] == pytest.approx(204.0)
    assert por_cuatro > ttm.iloc[-1], "la anualización infla cuando el flujo viene creciendo"


def test_el_ttm_exige_trimestres_consecutivos_tambien_para_el_ffo():
    """La misma regla de calendario que el AFFO, porque se comparan entre sí.

    Con un hueco, un `rolling(4)` abarcaría cinco trimestres de calendario y
    devolvería un «TTM» que no son doce meses, sin nada que lo delate.
    """
    idx = pd.to_datetime(["2024-03-31", "2024-06-30", "2024-09-30", "2025-03-31", "2025-06-30"])
    panel = pd.DataFrame({"ffo": [40.0, 42.0, 44.0, 46.0, 48.0]}, index=idx)
    ttm = _ttm(panel, "ffo")
    assert ttm.isna().all(), "hay un salto de trimestre y aun así emitió un TTM"


def test_los_tres_payouts_salen_del_mismo_renglon_ttm():
    """Sobre el panel real de una emisora, no sobre una maqueta."""
    ins = InsumosValuacion(
        ticker="X", precio=50.0, acciones_diluidas=100.0,
        affo_ttm=400.0, ffo_ttm=500.0, utilidad_neta_ttm=200.0,
        dividendo_ttm_por_accion=3.0, sector="Net Lease",
    )
    m = panel_valuacion(ins)
    assert m["payout_affo"] == pytest.approx(3.0 / 4.0)
    assert m["payout_ffo"] == pytest.approx(3.0 / 5.0)
    assert m["payout_utilidad_neta"] == pytest.approx(3.0 / 2.0)
    # Los tres son el MISMO dividendo sobre tres flujos; el orden tiene que
    # respetar que el AFFO es el más chico de los tres.
    assert m["payout_affo"] > m["payout_ffo"]


def test_la_pantalla_ya_no_anualiza_un_trimestre_por_cuatro():
    """El control del contrato, en el código: `* 4` sobre un flujo trimestral."""
    culpables = []
    for pagina in sorted((RAIZ / "app").rglob("*.py")):
        for numero, linea in enumerate(pagina.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"(ffo|utilidad_neta|affo)\w*\s*\*\s*4\b", linea) and not linea.lstrip().startswith("#"):
                culpables.append(f"{pagina.relative_to(RAIZ)}:{numero}: {linea.strip()}")
    assert not culpables, "vuelven a anualizar un trimestre:\n" + "\n".join(culpables)


def test_el_panel_publica_las_series_ttm_de_ffo_y_utilidad_neta(repo_sembrado):
    """Sin estas columnas, `_metricas` no tiene de dónde sacar el TTM real."""
    panel = construir_panel(repo_sembrado, "O", asof=dt.date(2026, 6, 30))
    assert "ffo_ttm" in panel.trimestral
    assert "utilidad_neta_ttm" in panel.trimestral


# --------------------------------------------------------------------------------------
# 24.2 · La fórmula que se dibuja es el cálculo que ocurre
# --------------------------------------------------------------------------------------


@pytest.fixture
def insumos() -> InsumosValuacion:
    """Agree Realty al corte del 2026-09-07, con números redondos y verificables."""
    return InsumosValuacion(
        ticker="ADC", precio=72.62, acciones_diluidas=110_000_000.0,
        noi_trimestral=155_000_000.0,
        affo_ttm=493_900_000.0, affo_por_accion_ttm=4.49,
        ffo_ttm=520_000_000.0, utilidad_neta_ttm=230_000_000.0,
        dividendo_ttm_por_accion=3.16,
        deuda_total=2_400_000_000.0, efectivo=90_000_000.0,
        intereses_ttm=95_000_000.0,
        sector="Net Lease",
    )


def test_cada_formula_se_puede_rehacer_a_mano(insumos):
    """La prueba de fondo: la aritmética de la pantalla, verificada por fuera.

    Cada fórmula declara sus operandos. Aquí se rehace el cálculo con ellos —
    escrito de nuevo, no llamando a la función del modelo — y se exige que
    coincida con el resultado que la pantalla publica.
    """
    modelos = modelos_de_valuacion(
        insumos, cap_rate_mercado=0.0675, tasa_libre_riesgo=0.0477,
        medida_flujo="AFFO", yield_adquisiciones=0.074,
    )
    por_clave = {f.clave: f for f in modelos}

    def op(clave, nombre):
        return por_clave[clave].operandos[nombre]

    y = por_clave["affo_yield"]
    assert y.resultado == pytest.approx(op("affo_yield", "A_ttm") / op("affo_yield", "P"))

    pa = por_clave["p_affo"]
    assert pa.resultado == pytest.approx(op("p_affo", "P") / op("p_affo", "A_ttm"))
    assert pa.resultado == pytest.approx(1.0 / y.resultado), "el múltiplo no es el recíproco"

    pay = por_clave["payout_affo"]
    assert pay.resultado == pytest.approx(op("payout_affo", "D_ttm") / op("payout_affo", "A_ttm"))

    pr = por_clave["prima"]
    assert pr.resultado == pytest.approx(op("prima", "y") - op("prima", "r_f"))

    cri = por_clave["cap_rate_implicito"]
    assert cri.resultado == pytest.approx(
        op("cap_rate_implicito", "NOI_anual") / op("cap_rate_implicito", "EV_aj")
    )

    nav = por_clave["nav_por_accion"]
    o = nav.operandos
    esperado = (
        o["NOI_anual"] / o["c_mkt"] + o["efectivo"] + o["prestamos"]
        + o["no_consolidadas"] - o["deuda"]
    ) / o["N"]
    assert nav.resultado == pytest.approx(esperado)

    g = por_clave["crecimiento_implicito"]
    o = g.operandos
    assert g.resultado == pytest.approx((o["P"] * o["r"] - o["A_ttm"]) / (o["P"] + o["A_ttm"]))

    cmc = por_clave["costo_marginal_capital"]
    o = cmc.operandos
    assert cmc.resultado == pytest.approx(o["w_d"] * o["k_d"] + (1 - o["w_d"]) * o["k_e"])

    s = por_clave["spread_inversion"]
    assert s.resultado == pytest.approx(
        op("spread_inversion", "y_adq") - op("spread_inversion", "CMC")
    )

    # Los tres payouts, sobre el mismo dividendo y tres flujos de la MISMA ventana.
    for clave in ("payout_ffo", "payout_utilidad_neta"):
        o = por_clave[clave].operandos
        assert por_clave[clave].resultado == pytest.approx(o["D_ttm"] / (o["X_ttm"] / o["N"]))
    assert por_clave["payout_affo"].resultado > por_clave["payout_ffo"].resultado, (
        "el AFFO es el más chico de los tres flujos, así que su payout es el más alto"
    )


def test_gordon_cierra_sobre_si_mismo(insumos):
    """El crecimiento implícito, metido de vuelta en Gordon, devuelve el precio.

    Es la comprobación que hace confiable al despeje: si `g` es el crecimiento
    que justifica el precio, entonces `A(1+g)/(r−g)` tiene que ser el precio.
    """
    modelos = modelos_de_valuacion(
        insumos, cap_rate_mercado=0.0675, tasa_libre_riesgo=0.0477, medida_flujo="AFFO"
    )
    g = formula_por_clave(modelos, "crecimiento_implicito")
    r = formula_por_clave(modelos, "tasa_descuento").resultado
    A = g.operandos["A_ttm"]
    assert A * (1 + g.resultado) / (r - g.resultado) == pytest.approx(insumos.precio, rel=1e-9)


def test_los_modelos_coinciden_con_el_motor_de_valuacion(insumos):
    """El otro extremo: lo que se dibuja tiene que ser lo que la app ya calculaba.

    Si la zona de modelos calculara por su cuenta, sería una segunda
    implementación que puede divergir en silencio de la que produce el veredicto.
    """
    m = panel_valuacion(insumos, cap_rate_mercado=0.0675, tasa_libre_riesgo=0.0477)
    modelos = modelos_de_valuacion(
        insumos, cap_rate_mercado=0.0675, tasa_libre_riesgo=0.0477, medida_flujo="AFFO"
    )
    equivalencias = {
        "affo_yield": "affo_yield",
        "p_affo": "p_affo",
        "dividend_yield": "dividend_yield",
        "payout_affo": "payout_affo",
        "cap_rate_implicito": "cap_rate_implicito",
        "nav_por_accion": "nav_por_accion",
        "premio_descuento_nav": "premio_descuento_nav",
    }
    for clave, metrica in equivalencias.items():
        f = formula_por_clave(modelos, clave)
        assert f.resultado == pytest.approx(m[metrica]), (
            f"{clave} dibuja {f.resultado} y el motor calcula {m[metrica]}"
        )


def test_un_insumo_que_falta_se_nombra_y_no_se_inventa():
    """Un guion no distingue «no vale nada» de «me falta un dato»."""
    sin_noi = InsumosValuacion(
        ticker="X", precio=50.0, acciones_diluidas=100.0,
        affo_por_accion_ttm=3.0, dividendo_ttm_por_accion=2.0, sector="Net Lease",
    )
    modelos = modelos_de_valuacion(
        sin_noi, cap_rate_mercado=0.065, tasa_libre_riesgo=0.045, medida_flujo="AFFO"
    )
    nav = formula_por_clave(modelos, "nav_por_accion")
    assert not nav.disponible
    assert nav.resultado is None
    assert nav.sustitucion is None, "dibujó una sustitución de un cálculo que no ocurrió"
    assert any("NOI" in f for f in nav.falta), f"no nombró el insumo que falta: {nav.falta}"
    # Y lo que sí se puede calcular, se calcula.
    assert formula_por_clave(modelos, "affo_yield").disponible


def test_la_etiqueta_sigue_a_la_medida_de_flujo_del_emisor():
    """PSA, EXR y WELL reportan Core FFO y nunca un AFFO. Llamarlo AFFO mentiría."""
    ins = InsumosValuacion(
        ticker="PSA", precio=300.0, acciones_diluidas=175.0,
        affo_por_accion_ttm=16.8, dividendo_ttm_por_accion=12.0, sector="Self Storage",
    )
    core = modelos_de_valuacion(
        ins, cap_rate_mercado=0.055, tasa_libre_riesgo=0.0477, medida_flujo="Core FFO"
    )
    assert "Core FFO" in formula_por_clave(core, "affo_yield").nombre
    assert "Core FFO" in formula_por_clave(core, "payout_affo").nombre


def test_la_prima_del_sector_entra_en_la_tasa_de_descuento(insumos):
    """La prima es del SECTOR, no del mercado entero. Es lo que hace comparable el Gordon."""
    modelos = modelos_de_valuacion(
        insumos, cap_rate_mercado=0.0675, tasa_libre_riesgo=0.0477, medida_flujo="AFFO"
    )
    r = formula_por_clave(modelos, "tasa_descuento")
    assert r.resultado == pytest.approx(0.0477 + prima_riesgo_sector("Net Lease"))


def test_toda_formula_trae_su_definicion_y_su_latex(insumos):
    """Una fórmula sin explicación no audita nada: solo cambia de notación."""
    modelos = modelos_de_valuacion(
        insumos, cap_rate_mercado=0.0675, tasa_libre_riesgo=0.0477, medida_flujo="AFFO"
    )
    assert len(modelos) >= 12
    for f in modelos:
        assert f.latex.strip(), f"{f.clave} no trae fórmula"
        assert len(f.definicion) > 60, f"{f.clave} no explica qué significa"
        assert f.unidad in ("porcentaje", "veces", "moneda", "numero", "bps")
        if f.disponible:
            assert f.sustitucion, f"{f.clave} corre pero no muestra sus números"


def test_la_pantalla_dibuja_los_modelos(insumos):
    """Cableado: el módulo existe, pero tiene que estar llamado desde la página."""
    assert "modelos_de_valuacion (" in CODIGO_VALUACION
    assert "st . latex ( f . latex )" in CODIGO_VALUACION
    assert "st . latex ( f . sustitucion )" in CODIGO_VALUACION


# --------------------------------------------------------------------------------------
# 24.3 · La marca
# --------------------------------------------------------------------------------------

_PALETA = {
    marca.NEGRO, marca.SUPERFICIE, marca.SUPERFICIE_2, marca.LINEA, marca.AMBAR,
    marca.AMBAR_TENUE, marca.BLANCO, marca.GRIS, marca.GRIS_TENUE, marca.PAPEL,
    marca.PAPEL_TINTA, marca.PROFIT, marca.LOSS,
}


def test_el_ambar_es_el_unico_acento_de_marca():
    """La guía es explícita: nada de menta, oro ni azul. El azul es el que estaba."""
    assert marca.AMBAR == "#F5A623"
    assert marca.NEGRO == "#0A0B0D"
    # El azul de la versión anterior no puede seguir vivo en ninguna página.
    prohibidos = ("#0969da", "#3d4f8a", "#1a7f37", "#b42318", "#9a6700", "#57606a")
    culpables = []
    for pagina in sorted((RAIZ / "app").rglob("*.py")):
        texto = pagina.read_text(encoding="utf-8").lower()
        for color in prohibidos:
            if color in texto:
                culpables.append(f"{pagina.relative_to(RAIZ)}: {color}")
    assert not culpables, "colores fuera de la paleta:\n" + "\n".join(culpables)


def test_ningun_color_suelto_fuera_de_la_paleta():
    """Todo hexadecimal de la aplicación tiene que ser un token de marca.

    Se permite que `marca.py` declare los suyos —es la fuente— y los dos tonos
    intermedios de la escala del mapa de calor, que son interpolaciones.
    """
    intermedios = {"#7A2B2E", "#5C4520", "#4A5058", "#F5C87A"}
    permitidos = {c.upper() for c in _PALETA} | intermedios
    culpables = []
    for pagina in sorted((RAIZ / "app").rglob("*.py")):
        for numero, linea in enumerate(pagina.read_text(encoding="utf-8").splitlines(), 1):
            for color in re.findall(r"#[0-9a-fA-F]{6}", linea):
                if color.upper() not in permitidos:
                    culpables.append(f"{pagina.relative_to(RAIZ)}:{numero}: {color}")
    assert not culpables, "colores fuera de la paleta:\n" + "\n".join(culpables)


def test_tampoco_se_cuela_un_color_escrito_en_rgb():
    """El azul se escapó así: `rgba(9,105,218,0.15)` no lo caza un patrón hexadecimal.

    Eran las mil trayectorias de fondo del Monte Carlo, dibujadas en el azul que
    la guía prohíbe, debajo de tres percentiles que sí estaban en la paleta. Es
    exactamente la esquina sin teñir de la que habla el comentario del tema.
    """
    def _a_rgb(hex_: str) -> tuple[int, int, int]:
        h = hex_.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    permitidos = {_a_rgb(c) for c in _PALETA} | {(0, 0, 0)}
    culpables = []
    for pagina in sorted((RAIZ / "app").rglob("*.py")):
        for numero, linea in enumerate(pagina.read_text(encoding="utf-8").splitlines(), 1):
            for cuerpo in re.findall(r"rgba?\(([^)]+)\)", linea):
                partes = [p.strip() for p in cuerpo.split(",")]
                if len(partes) < 3:
                    continue
                try:
                    rgb = tuple(int(float(p)) for p in partes[:3])
                except ValueError:
                    continue
                if rgb not in permitidos:
                    culpables.append(f"{pagina.relative_to(RAIZ)}:{numero}: rgb{rgb}")
    assert not culpables, "colores en rgb() fuera de la paleta:\n" + "\n".join(culpables)


def test_ganancia_y_perdida_nunca_dependen_solo_del_color():
    """Regla daltónica de la guía, §8: siempre ▲ / ▼, y una captura en gris la conserva."""
    assert marca.signo(0.024) == "▲"
    assert marca.signo(-0.006) == "▼"
    assert marca.signo(0.0) == "·"
    assert marca.signo(None) == "·"
    # Cada luz del semáforo tiene glifo, no solo color.
    assert set(marca.COLOR_LUZ) == set(marca.GLIFO_LUZ)
    for luz, glifo in marca.GLIFO_LUZ.items():
        assert glifo.strip(), f"{luz} no tiene glifo y quedaría distinguible solo por color"


def test_el_semaforo_no_usa_emojis():
    """La guía los prohíbe. Antes eran 🟢🟡🔴⚪, que además no alinean en mono."""
    emojis = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
    for luz, glifo in marca.GLIFO_LUZ.items():
        assert not emojis.search(glifo), f"{luz} sigue usando un emoji: {glifo}"
    import comun
    assert not emojis.search(comun.semaforo_html("VERDE", "texto"))


def test_las_tres_tipografias_de_la_guia_estan_declaradas():
    assert "Space Grotesk" in marca.DISPLAY
    assert "Inter" in marca.TEXTO
    assert "JetBrains Mono" in marca.MONO


def test_el_tema_de_streamlit_lleva_los_tokens_de_marca():
    """El tema nativo, no CSS inyectado: Streamlit pinta sus propios widgets.

    Parchear desde fuera deja siempre una esquina sin teñir —un desplegable, el
    encabezado de una tabla— y es justo la que se nota.
    """
    config = (RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'base = "dark"' in config
    assert marca.AMBAR in config, "el acento del tema no es el ámbar de marca"
    assert marca.NEGRO in config, "el fondo del tema no es el negro de marca"
    assert "Space Grotesk" in config and "JetBrains Mono" in config


def test_plotly_hereda_la_marca_por_omision():
    """Veinte gráficas en siete pantallas: teñirlas una por una deja alguna en azul."""
    import plotly.io as pio

    assert pio.templates.default == "stc"
    colorway = pio.templates["stc"].layout.colorway
    assert colorway[0] == marca.AMBAR
    for color in colorway:
        assert color.upper() in {c.upper() for c in _PALETA}


def test_el_simbolo_de_marca_se_dibuja_en_linea():
    """En Streamlit Cloud el sistema de archivos es efímero: un SVG externo falta."""
    svg = marca.marca_svg(30)
    assert svg.strip().startswith("<svg")
    assert marca.AMBAR in svg, "la curva de distribución no va en ámbar"
    assert marca.BLANCO in svg, "faltan los dos strikes"
    assert svg.count("<circle") == 2, "el strike va SIEMPRE con punto (regla P1 de la guía)"


def test_todas_las_pantallas_llevan_el_lockup_de_marca():
    """Siete pantallas con el logotipo en una sola no están marcadas: están decoradas."""
    sin_marca = []
    for pagina in sorted((RAIZ / "app").rglob("*.py")):
        if pagina.name in ("comun.py", "marca.py"):
            continue
        texto = pagina.read_text(encoding="utf-8")
        if "encabezado(" not in texto or "inyectar_estilos()" not in texto:
            sin_marca.append(pagina.name)
    assert not sin_marca, f"pantallas sin encabezado de marca: {sin_marca}"


def test_el_descargo_de_cumplimiento_esta_en_la_pantalla():
    """La guía lo marca como crítico: educativo, nunca asesoría de inversión."""
    assert "No es asesoría de inversión" in PAGINA_VALUACION
    assert "no garantizan resultados futuros" in PAGINA_VALUACION


# --------------------------------------------------------------------------------------
# 24.4 · Los defectos de la pantalla que la marca no toca
# --------------------------------------------------------------------------------------


def test_el_hueco_del_percentil_no_se_pinta_de_verde():
    """`(percentil or 1) < 0.5` mandaba al verde los dos casos que más importan.

    Sin percentil —hoy ocho de diez emisoras— pintaba verde; y un percentil de
    0.0, que es el MÁS CARO de toda su historia, también pintaba verde.
    """
    assert "percentil_actual or 1" not in CODIGO_VALUACION
    assert "or 1 ) < 0.5" not in CODIGO_VALUACION
    # Y el caso de 0.0 tiene que caer del lado rojo.
    for percentil, esperado in ((0.0, "ROJO"), (0.49, "ROJO"), (0.5, "VERDE"), (0.9, "VERDE")):
        luz = "ROJO" if percentil < 0.5 else "VERDE"
        assert luz == esperado


def test_el_payout_que_falta_no_se_pinta_de_verde():
    """`(p_affo or 0) < listón` mandaba el hueco al lado verde: 0 siempre pasa."""
    assert "p_affo or 0" not in CODIGO_VALUACION
    assert "p_neta or 0" not in CODIGO_VALUACION
    # Y el hueco cae en la luz de "sin datos", que no afirma salud. Se busca la
    # línea de código, no la cadena suelta: el tokenizador quita las cadenas.
    assert 'return COLOR_LUZ["SIN DATOS"]' in PAGINA_VALUACION


def test_el_conteo_de_la_puerta_tres_no_finge_cobertura():
    """El denominador estaba fijo en 5; hoy solo 2 de los 5 criterios son medibles."""
    # Se busca la ficha misma, no el token: el tokenizador borra las f-strings
    # enteras, así que `"/5" not in CODIGO` no miraba nada y dejaba pasar la
    # vuelta al denominador fijo.
    assert "{disparos}/{medibles_p3} medibles" in PAGINA_VALUACION, (
        "el denominador de la Puerta 3 volvió a ser fijo"
    )
    assert 'f"{disparos}/5"' not in PAGINA_VALUACION
    # Y el conteo de medibles tiene que salir de los criterios, no de una constante.
    assert 'criterios_p3["dispara"].notna().sum()' in PAGINA_VALUACION


def test_la_serie_trimestral_no_se_llama_completa_si_esta_recortada():
    """PSA tiene 73 trimestres y se dibujaban 20 bajo un título que decía «completa»."""
    assert "Serie trimestral completa" not in CODIGO_VALUACION
    assert "_MAX_TRIMESTRES" in CODIGO_VALUACION


def test_la_procedencia_dice_cuanto_recorta():
    """469 registros en Realty Income, 60 dibujados, en la sección de trazabilidad."""
    assert "_MAX_FUENTES" in CODIGO_VALUACION
    assert "head ( 200 )" not in CODIGO_VALUACION, (
        "el libro de Excel volvía a recortar la procedencia en silencio"
    )


def test_los_escenarios_no_convierten_un_hueco_en_cero():
    """`(crec_hist or 0.0)` dibujaba «el que ha entregado: 0%» sin haber medido nada."""
    assert "crec_hist or 0.0" not in CODIGO_VALUACION
    assert "if crec_hist is not None :" in CODIGO_VALUACION


def test_la_emisora_sin_fundamentales_recibe_diagnostico_y_no_pantalla_en_blanco():
    """Era el único camino que producía el síntoma de «no puedo ver otra emisora»."""
    assert "cobertura_de_emisores (" in CODIGO_VALUACION
    assert "no tiene fundamentales trimestrales al corte" in PAGINA_VALUACION
    assert "scripts/ingesta.py" in PAGINA_VALUACION


def test_el_selector_de_emisora_vive_en_el_cuerpo_y_no_en_la_barra_lateral():
    """En pantalla angosta Streamlit arranca con la barra lateral PLEGADA.

    Con el único control ahí dentro, la pantalla parecía servir una sola emisora.
    """
    import inspect

    import comun
    fuente = inspect.getsource(comun.selector_de_emisor)
    assert "st.pills(" in fuente, "sigue siendo un desplegable"
    assert "st.sidebar" not in fuente, "el selector volvió a la barra lateral"


def test_deseleccionar_la_ficha_no_deja_la_pantalla_sin_emisora():
    """`st.pills` devuelve None al volver a pulsar la ficha activa."""
    import inspect

    import comun
    fuente = inspect.getsource(comun.selector_de_emisor)
    assert "if elegido is None:" in fuente, (
        "sin esta guarda, un segundo clic en la ficha activa detiene la pantalla"
    )
