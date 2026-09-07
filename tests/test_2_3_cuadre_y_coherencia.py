"""Pruebas obligatorias 2 y 3 — Cuadre del AFFO y coherencia temporal.

2. El AFFO recalculado desde los componentes tiene que atar contra el reportado.
3. ``H1 = Q1 + Q2`` y ``FY = Q1 + Q2 + Q3 + Q4``.

La prueba de cuadre corre contra el **Exhibit 99.1 real** de Realty Income, no
contra una maqueta. Una maqueta confirma lo que el parser ya hace; un documento
que la SEC efectivamente publicó es lo que encuentra los errores.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.ingesta.parser_affo import parsear_conciliacion, reconstruir_trimestres
from src.modelo.cascada import MAGNITUD, REPORTE, calcular_cascada, coherencia_temporal
from src.validacion.cuadre import (
    cuadrar_affo,
    cuadrar_conciliacion,
    elegir_mejor_conciliacion,
    prueba_suavidad_consenso,
    validar_coherencia_temporal,
    validar_rangos,
)

# --------------------------------------------------------------------------------------
# Prueba 2 — Cuadre contra el filing real
# --------------------------------------------------------------------------------------


def test_cuadre_contra_el_8k_real(html_8k_realty, fecha_publicacion_8k):
    """Cada periodo del Exhibit 99.1 cuadra contra los subtotales del emisor.

    No se compara contra un número que nosotros elegimos: se compara la suma de
    las partidas contra el subtotal que Realty Income publicó. Si el parser
    pierde una fila o le cambia el signo, esto falla.
    """
    extracciones = elegir_mejor_conciliacion(
        parsear_conciliacion(html_8k_realty, "O", fecha_publicacion_8k, "fixture")
    )
    assert extracciones, "El parser no extrajo ningún periodo del filing real."

    fallidos = []
    for e in extracciones:
        resultado = cuadrar_conciliacion(e.lineas, e.orden)
        if not resultado.cuadra:
            fallidos.append(f"{e.periodo.etiqueta}: {resultado.motivo}")
    assert not fallidos, "Periodos que no cuadran:\n" + "\n".join(fallidos)


def test_el_cuadre_verifica_algo_de_verdad(html_8k_realty, fecha_publicacion_8k):
    """Un cuadre sin partidas verificables no es un cuadre.

    Sin esta prueba, ``cuadrar_conciliacion`` podría pasar siempre simplemente
    porque ningún tramo tiene partidas que sumar.
    """
    extracciones = elegir_mejor_conciliacion(
        parsear_conciliacion(html_8k_realty, "O", fecha_publicacion_8k, "fixture")
    )
    verificados = 0
    for e in extracciones:
        resultado = cuadrar_conciliacion(e.lineas, e.orden)
        verificados += len(resultado.tramos_verificados)
    assert verificados >= len(extracciones), (
        "Cada periodo debe tener al menos un tramo con partidas itemizadas; "
        "si no, el cuadre está pasando en vacío."
    )


def test_el_cuadre_detecta_una_linea_alterada(html_8k_realty, fecha_publicacion_8k):
    """Control positivo del cuadre: si se altera una partida, tiene que fallar."""
    extracciones = elegir_mejor_conciliacion(
        parsear_conciliacion(html_8k_realty, "O", fecha_publicacion_8k, "fixture")
    )
    objetivo = next(
        e for e in extracciones
        if cuadrar_conciliacion(e.lineas, e.orden).tramos_verificados
    )
    tramo = cuadrar_conciliacion(objetivo.lineas, objetivo.orden).tramos_verificados[0]
    partida = tramo.partidas[0]

    alteradas = dict(objetivo.lineas)
    alteradas[partida] = alteradas[partida] * 1.5 + 1_000_000.0
    resultado = cuadrar_conciliacion(alteradas, objetivo.orden)
    assert not resultado.cuadra, (
        f"Alterar '{partida}' no rompió el cuadre: la validación no está verificando nada."
    )


def test_razon_affo_contra_utilidad_neta_del_filing_real(html_8k_realty, fecha_publicacion_8k):
    """P3 con números reales: Q2 2026 da AFFO 1.09 contra utilidad neta 0.37.

    Es la razón de 2.97x documentada. Si el parser confundiera el trimestre con el
    semestre, o la utilidad neta con la del año, este número se movería.
    """
    extracciones = elegir_mejor_conciliacion(
        parsear_conciliacion(html_8k_realty, "O", fecha_publicacion_8k, "fixture")
    )
    q2 = [
        e for e in extracciones
        if e.periodo.tipo == "Q" and e.periodo.fin == dt.date(2026, 6, 30)
        and "affo_por_accion" in e.lineas and "utilidad_neta_por_accion" in e.lineas
    ]
    assert q2, "No se encontró el trimestre con magnitudes por acción."
    e = q2[0]
    assert e.lineas["affo_por_accion"] == pytest.approx(1.09, abs=0.01)
    assert e.lineas["utilidad_neta_por_accion"] == pytest.approx(0.37, abs=0.01)
    razon = e.lineas["affo_por_accion"] / e.lineas["utilidad_neta_por_accion"]
    assert razon == pytest.approx(2.95, abs=0.10), (
        f"La razón AFFO/utilidad neta salió {razon:.2f}; se esperaba ~2.97x."
    )


def test_cuadre_por_taxonomia_con_convenciones_de_signo():
    """Las dos convenciones de signo dan el mismo AFFO cuando se usan bien.

    Y dan resultados distintos cuando se confunden, que es el punto: el error es
    de exactamente el doble de cada partida negativa.
    """
    magnitudes = {
        "utilidad_neta": 100.0,
        "depreciacion_inmuebles": 250.0,
        "ganancia_venta_inmuebles": 40.0,      # magnitud positiva; la cascada resta
        "renta_linea_recta": 30.0,             # magnitud positiva; la cascada resta
        "amortizacion_costos_financieros": 10.0,
    }
    reporte = {
        "utilidad_neta": 100.0,
        "depreciacion_inmuebles": 250.0,
        "ganancia_venta_inmuebles": -40.0,     # como lo presenta el emisor
        "renta_linea_recta": -30.0,
        "amortizacion_costos_financieros": 10.0,
    }
    esperado = 100 + 250 - 40 - 30 + 10  # 290

    assert calcular_cascada(magnitudes, signos=MAGNITUD).affo == pytest.approx(esperado)
    assert calcular_cascada(reporte, signos=REPORTE).affo == pytest.approx(esperado)

    # Confundirlas: cada partida negativa se cuenta al revés.
    confundido = calcular_cascada(reporte, signos=MAGNITUD).affo
    assert confundido == pytest.approx(esperado + 2 * (40 + 30))


def test_registro_que_no_cuadra_queda_sospechoso():
    componentes = {
        "utilidad_neta": 100.0,
        "depreciacion_inmuebles": 250.0,
        "renta_linea_recta": 30.0,
    }
    resultado = cuadrar_affo(componentes, affo_reportado=999.0, signos=MAGNITUD)
    assert not resultado.cuadra
    assert resultado.estado == "sospechoso"
    assert "Diferencia" in resultado.motivo


def test_cuadre_tolera_el_redondeo_del_emisor():
    """En cifras de millones, el emisor redondea cada línea antes de sumar."""
    componentes = {"utilidad_neta": 100_000_000.0, "depreciacion_inmuebles": 250_000_000.0}
    resultado = cuadrar_affo(componentes, affo_reportado=350_050_000.0, signos=MAGNITUD)
    assert resultado.cuadra, "Una diferencia de 0.014% es redondeo, no un error."


# --------------------------------------------------------------------------------------
# Prueba 3 — Coherencia temporal
# --------------------------------------------------------------------------------------


def test_h1_igual_a_q1_mas_q2_y_fy_igual_a_la_suma():
    serie = pd.Series(
        [1.00, 1.05, 1.08, 1.12],
        index=pd.to_datetime(["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"]),
    )
    acumulados = {"2024-H1": 2.05, "2024-FY": 4.25}
    resultado = validar_coherencia_temporal(serie, acumulados)
    assert resultado.coherente, resultado.motivo
    assert len(resultado.verificaciones) == 2


def test_incoherencia_temporal_se_detecta():
    serie = pd.Series(
        [1.00, 1.05, 1.08, 1.12],
        index=pd.to_datetime(["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"]),
    )
    resultado = validar_coherencia_temporal(serie, {"2024-H1": 2.40})
    assert not resultado.coherente
    assert "Incoherencia temporal" in resultado.motivo


def test_coherencia_temporal_directa():
    salida = coherencia_temporal({"Q1": 1.0, "Q2": 1.1, "Q3": 1.2, "Q4": 1.3,
                                  "H1": 2.1, "FY": 4.6})
    assert salida["cuadra_h1"] and salida["cuadra_fy"]

    mala = coherencia_temporal({"Q1": 1.0, "Q2": 1.1, "H1": 2.5})
    assert not mala["cuadra_h1"]


# --------------------------------------------------------------------------------------
# Reconstrucción de trimestres
# --------------------------------------------------------------------------------------


def test_reconstruccion_q1_y_q3():
    """``Q1 = H1 − Q2`` y ``Q3 = FY − H1 − Q4``, con fecha de publicación máxima."""
    obs = {
        "Q2": (1.05, dt.date(2024, 8, 5)),
        "H1": (2.05, dt.date(2024, 8, 5)),
        "Q4": (1.12, dt.date(2025, 2, 20)),
        "FY": (4.25, dt.date(2025, 2, 20)),
    }
    salida = reconstruir_trimestres(obs)

    assert salida["Q1"][0] == pytest.approx(1.00)
    assert salida["Q1"][1] == dt.date(2024, 8, 5)
    assert salida["Q3"][0] == pytest.approx(4.25 - 2.05 - 1.12)
    assert salida["Q3"][1] == dt.date(2025, 2, 20)


def test_reconstruccion_usa_la_publicacion_mas_tardia():
    """Antes de la publicación más tardía, el trimestre derivado no era deducible."""
    obs = {"Q2": (1.05, dt.date(2024, 8, 5)), "H1": (2.05, dt.date(2024, 11, 30))}
    salida = reconstruir_trimestres(obs)
    assert salida["Q1"][1] == dt.date(2024, 11, 30)


def test_no_reconstruye_lo_que_ya_existe():
    obs = {"Q1": (0.99, dt.date(2024, 5, 5)), "Q2": (1.05, dt.date(2024, 8, 5)),
           "H1": (2.05, dt.date(2024, 8, 5))}
    assert "Q1" not in reconstruir_trimestres(obs)


# --------------------------------------------------------------------------------------
# Rangos razonables y suavidad del consenso
# --------------------------------------------------------------------------------------


def test_rangos_razonables():
    assert validar_rangos({"payout_affo": 0.73, "ocupacion": 0.98, "ltv": 0.42}) == []
    problemas = validar_rangos({"payout_affo": 2.5, "ocupacion": 1.4, "ltv": -0.1})
    assert len(problemas) == 3


def test_serie_de_consenso_sospechosamente_lisa():
    """Una serie de consenso real salta en las fechas de reporte. Si no, es la reexpresada.

    Lo que se mide es concentración: si los cambios en las fechas de reporte no
    son mayores que los de cualquier otro día, la serie no distingue el evento
    que debería moverla.
    """
    fechas = pd.date_range("2020-01-31", periods=48, freq="ME")
    reportes = pd.to_datetime(
        ["2020-05-31", "2020-08-31", "2020-11-30", "2021-02-28",
         "2021-05-31", "2021-08-31", "2021-11-30", "2022-02-28"]
    )

    # Tendencia perfectamente uniforme: no distingue los reportes de nada.
    lisa = pd.Series([3.0 + 0.01 * i for i in range(48)], index=fechas)
    resultado = prueba_suavidad_consenso(lisa, reportes)
    assert resultado.sospechosa, resultado.motivo
    assert resultado.razon_concentracion < 2.0

    # Serie realista: casi plana entre reportes, con revisión al publicarse.
    con_saltos = pd.Series(3.0, index=fechas)
    for f in reportes:
        idx = con_saltos.index.get_indexer([f], method="nearest")[0]
        con_saltos.iloc[idx:] += 0.06
    con_saltos = con_saltos + pd.Series(
        [0.0005 * ((-1) ** i) for i in range(48)], index=fechas
    )
    resultado = prueba_suavidad_consenso(con_saltos, reportes)
    assert not resultado.sospechosa, resultado.motivo
    assert resultado.razon_concentracion >= 2.0


# --------------------------------------------------------------------------------------
# Convenciones de presentación que rompen conciliaciones si se ignoran
# --------------------------------------------------------------------------------------


def test_el_signo_puede_venir_en_la_palabra_no_en_el_numero():
    """"Less Series A preferred stock dividends" trae el monto en positivo.

    Agree Realty pone el signo en la palabra "Less". Sumar ese positivo desplaza el
    subtotal por el DOBLE de la partida, y el descuadre parece venir de otra línea.
    """
    from src.ingesta.parser_affo import _signo_de_la_etiqueta

    assert _signo_de_la_etiqueta("Less Series A preferred stock dividends") == -1
    assert _signo_de_la_etiqueta("Menos: dividendos preferentes") == -1
    assert _signo_de_la_etiqueta("Depreciation and amortization") == 1
    assert _signo_de_la_etiqueta("Lessee improvements") == 1, (
        "«Lessee» empieza con «Less» pero no es una resta: el patrón exige límite de palabra."
    )


def test_un_concepto_repetido_en_dos_tramos_no_se_mezcla():
    """El mismo concepto puede aparecer antes del FFO y antes del Core FFO.

    Agree Realty amortiza intangibles de arrendamiento antes del FFO y rentas sobre
    y bajo mercado antes del Core FFO; ambas caen en "otros ajustes no-efectivo".
    Sumarlas juntas mete el segundo monto en el tramo del primero y deja al
    siguiente sin partidas que verificar.
    """
    html = """
    <html><body>
    <p>(in thousands) Three months ended June 30,</p>
    <p>2026</p>
    <table>
      <tr><td>Three months ended June 30,</td><td>2026</td></tr>
      <tr><td>Net income</td><td>100</td></tr>
      <tr><td>Depreciation of rental real estate assets</td><td>200</td></tr>
      <tr><td>Amortization of lease intangibles</td><td>50</td></tr>
      <tr><td>Funds from Operations - common unitholders</td><td>350</td></tr>
      <tr><td>Amortization of above (below) market lease intangibles, net</td><td>25</td></tr>
      <tr><td>Core Funds from Operations - common unitholders</td><td>375</td></tr>
      <tr><td>Straight-line accrued rent</td><td>(15)</td></tr>
      <tr><td>Adjusted Funds from Operations - common unitholders</td><td>360</td></tr>
    </table>
    </body></html>
    """
    extracciones = parsear_conciliacion(html, "TEST", dt.date(2026, 8, 5), "fixture")
    assert extracciones
    e = extracciones[0]

    claves = set(e.lineas)
    assert "otros_ajustes_no_efectivo" in claves
    assert any(k.startswith("otros_ajustes_no_efectivo#") for k in claves), (
        "El ajuste posterior al FFO tiene que quedar en su propio segmento."
    )

    resultado = cuadrar_conciliacion(e.lineas, e.orden)
    assert resultado.cuadra, resultado.motivo
    assert len(resultado.tramos_verificados) == 3, (
        "Los tres tramos tienen que tener partidas propias que verificar."
    )


def test_la_cascada_suma_los_segmentos_del_mismo_concepto():
    """Los segmentos son un detalle de la tabla del emisor, no conceptos distintos."""
    componentes = {
        "utilidad_neta": 100.0,
        "depreciacion_inmuebles": 200.0,
        "otros_ajustes_no_efectivo": 50.0,
        "otros_ajustes_no_efectivo#1": 25.0,
    }
    resultado = calcular_cascada(componentes, signos=REPORTE)
    assert resultado.affo == pytest.approx(375.0)


def test_una_tabla_de_guia_no_entra_como_cifra_realizada():
    """Un filing no puede reportar cifras realizadas de un periodo que no ha terminado.

    Extra Space Storage publica su guía del año en el mismo comunicado que su
    trimestre. Tratarla como realizada mete una proyección dentro de la serie
    histórica, que es lookahead disfrazado de dato.
    """
    html = """
    <html><body>
    <p>(in thousands) Twelve months ended December 31,</p>
    <table>
      <tr><td>Twelve months ended December 31,</td><td>2026</td></tr>
      <tr><td>Net income</td><td>1000</td></tr>
      <tr><td>Depreciation and amortization</td><td>2000</td></tr>
      <tr><td>FFO available to common stockholders</td><td>3000</td></tr>
      <tr><td>Straight-line rent</td><td>(100)</td></tr>
      <tr><td>AFFO available to common stockholders</td><td>2900</td></tr>
    </table>
    </body></html>
    """
    # El filing se presenta en julio; el periodo cierra en diciembre. Es guía.
    extracciones = parsear_conciliacion(html, "TEST", dt.date(2026, 7, 28), "fixture")
    assert not extracciones, (
        "Una tabla cuyo periodo termina DESPUÉS de la fecha del filing es guía, "
        "no resultados. La guía tiene su propia tabla con su propio versionado."
    )


# --------------------------------------------------------------------------------------
# El sufijo de segmento no puede volver a esconder un concepto
# --------------------------------------------------------------------------------------
#
# Un mismo concepto puede aparecer en dos tramos de la conciliación, y el parser lo
# guarda con sufijo para no mezclarlos. Todo lo que razona SOBRE el concepto tiene
# que usar la clave base. `acumular` lo hacía; dos comprobaciones de olfato no, y
# preguntaban por la clave exacta.
#
# El resultado no era un error visible sino algo peor: una alarma que se disparaba
# con los SEIS emisores que sí reportan el ajuste, porque el puente al AFFO va
# después del FFO y ahí la clave siempre llega sufijada. Una alarma que suena
# siempre deja de leerse, y tapa el caso en que de verdad falte.


def test_el_ajuste_de_renta_en_linea_recta_se_reconoce_con_sufijo_de_segmento():
    """Cifras reales de Agree Realty: su ajuste llega como `renta_linea_recta#2`."""
    from src.modelo.cascada import REPORTE, calcular_cascada

    componentes = {
        "utilidad_neta": 54_809_000.0,
        "depreciacion_inmuebles": 46_210_000.0,
        "deterioro": 5_900_000.0,
        "ganancia_venta_inmuebles": -2_526_000.0,
        "ffo": 124_722_000.0,
        "ffo_normalizado": 136_039_000.0,
        "affo": 137_983_000.0,
        "renta_linea_recta#2": -4_583_000.0,
    }
    banderas = calcular_cascada(componentes, sector="Net Lease", signos=REPORTE).banderas
    assert not [b for b in banderas if "línea recta" in b], (
        "no reconoció un ajuste que el emisor SÍ reporta, por venir en un segmento posterior"
    )


def test_sin_el_ajuste_la_alarma_sigue_sonando():
    """El control. Una alarma que nunca suena no sirve de nada."""
    from src.modelo.cascada import REPORTE, calcular_cascada

    banderas = calcular_cascada(
        {
            "utilidad_neta": 54_809_000.0,
            "depreciacion_inmuebles": 46_210_000.0,
            "ffo": 124_722_000.0,
            "affo": 137_983_000.0,
        },
        sector="Net Lease", signos=REPORTE,
    ).banderas
    assert [b for b in banderas if "línea recta" in b]


def test_valor_del_concepto_suma_todos_los_segmentos():
    """Preguntar por un concepto es sumar sus partes, no leer una llave."""
    from src.modelo.cascada import valor_del_concepto

    componentes = {
        "otros_ajustes_no_efectivo": 11_317_000.0,
        "otros_ajustes_no_efectivo#1": 22_188_000.0,
        "otros_ajustes_no_efectivo#2": 3_775_000.0,
        "renta_linea_recta#2": -4_583_000.0,
    }
    assert valor_del_concepto(componentes, "otros_ajustes_no_efectivo") == pytest.approx(
        11_317_000 + 22_188_000 + 3_775_000
    )
    assert valor_del_concepto(componentes, "renta_linea_recta") == pytest.approx(-4_583_000.0)
    assert valor_del_concepto(componentes, "capex_mantenimiento") is None


def test_ningun_emisor_del_repositorio_recibe_la_falsa_alarma(repo_sembrado):
    """Contra la base, no contra una maqueta: la alarma no puede ser universal."""
    import datetime as dt

    from src.modelo.cascada import REPORTE, calcular_cascada

    asof = dt.date(2026, 12, 31)
    con_alarma, con_conciliacion = [], []
    for ticker in repo_sembrado.emisores()["ticker"]:
        hechos = repo_sembrado.hechos(
            asof=asof, tickers=ticker, conceptos="affo", periodo_tipo="Q"
        )
        if hechos.empty:
            continue
        fecha = sorted(pd.to_datetime(hechos["fecha_dato"]).dt.date.unique())[-1]
        conc = repo_sembrado.conciliacion(ticker, fecha, asof=asof)
        if conc.empty:
            continue
        con_conciliacion.append(ticker)
        lineas = {r["linea"]: float(r["valor"]) for _, r in conc.iterrows()}
        banderas = calcular_cascada(lineas, signos=REPORTE).banderas
        if [b for b in banderas if "línea recta" in b]:
            con_alarma.append(ticker)

    if not con_conciliacion:
        pytest.skip("La semilla no trae conciliaciones línea por línea.")
    assert len(con_alarma) < len(con_conciliacion), (
        f"la alarma se dispara con TODOS los emisores ({con_alarma}): eso no es una "
        "alarma, es ruido, y tapa el caso en que de verdad falte el ajuste"
    )


# --------------------------------------------------------------------------------------
# Los escalones que la pantalla dibuja
# --------------------------------------------------------------------------------------
#
# La cascada de la pantalla no es decorativa: pone un nombre sobre cada puente, y ese
# nombre afirma DE QUÉ está hecha la diferencia entre dos cifras que el emisor publicó.
# Nombrarlo mal es atribuirle al emisor una descomposición que nunca reportó.


def test_el_puente_se_nombra_por_el_par_que_une_no_por_su_posicion():
    """Realty Income salta el FFO Nareit: ese puente trae más que depreciación.

    O va de la utilidad neta al FFO normalizado en un solo brinco —su tabla publica
    "Cumulative adjustments to calculate Normalized FFO" y nunca un subtotal de FFO
    Nareit—. Con etiquetas por posición, ese primer puente salía rotulado
    "depreciación y deterioro", callando las partidas no recurrentes que también
    lleva dentro.
    """
    from src.modelo.cascada import escalones_de_cascada

    pasos = escalones_de_cascada({
        "utilidad_neta": 344_035_000.0,
        "ffo_normalizado": 998_722_000.0,
        "affo": 1_022_055_000.0,
    })
    nombres = [n for n, _, es_subtotal in pasos if not es_subtotal]
    assert nombres == ["depreciación y<br>no recurrentes", "renta lineal<br>y CapEx"]

    # El escalón ausente no se inventa: tres subtotales, no cuatro.
    subtotales = [n for n, _, es_subtotal in pasos if es_subtotal]
    assert subtotales == ["Utilidad neta", "FFO normalizado", "AFFO"]


def test_wpc_no_normaliza_y_su_puente_lo_dice():
    """W. P. Carey va del FFO Nareit directo al AFFO, sin escalón intermedio."""
    from src.modelo.cascada import escalones_de_cascada

    pasos = escalones_de_cascada({
        "utilidad_neta": 185_404_000.0,
        "ffo": 342_518_000.0,
        "affo": 305_449_000.0,
    })
    nombres = [n for n, _, es_subtotal in pasos if not es_subtotal]
    assert nombres == ["depreciación<br>y deterioro", "no recurrentes,<br>renta y CapEx"]


def test_quien_reporta_core_ffo_no_dibuja_un_affo_que_no_publica():
    """Public Storage termina en Core FFO: repetirlo con dos nombres es un puente falso.

    El escalón final se llama como la medida que el emisor sí publica, y el FFO
    normalizado no aparece dos veces con un puente de cero entre medias.
    """
    from src.modelo.cascada import escalones_de_cascada

    componentes = {
        "utilidad_neta": 450_301_000.0,
        "ffo": 742_935_000.0,
        "ffo_normalizado": 736_117_000.0,
    }
    pasos = escalones_de_cascada(componentes, medida_flujo="Core FFO")
    subtotales = [n for n, _, es_subtotal in pasos if es_subtotal]
    assert subtotales == ["Utilidad neta", "FFO Nareit", "Core FFO"]
    assert [n for n, _, es in pasos if not es] == [
        "depreciación<br>y deterioro", "partidas no<br>recurrentes",
    ]

    # Y con AFFO como medida, el mismo insumo dibuja el FFO normalizado con su nombre.
    con_affo = escalones_de_cascada(componentes, medida_flujo="AFFO")
    assert [n for n, _, es in con_affo if es] == [
        "Utilidad neta", "FFO Nareit", "FFO normalizado",
    ]


def test_los_escalones_se_leen_con_sufijo_de_segmento():
    """Un subtotal repetido en dos tramos llega con sufijo, y sigue siendo el subtotal."""
    from src.modelo.cascada import escalones_de_cascada

    pasos = escalones_de_cascada({
        "utilidad_neta#1": 100.0,
        "ffo#2": 250.0,
        "affo#3": 300.0,
    })
    assert [n for n, _, es in pasos if es] == ["Utilidad neta", "FFO Nareit", "AFFO"]
    assert [v for _, v, es in pasos if not es] == [150.0, 50.0]


def test_el_puente_vale_la_diferencia_entre_los_subtotales_que_une():
    """Los puentes deben reconstruir la cascada: sumar todo devuelve el último escalón."""
    from src.modelo.cascada import escalones_de_cascada

    pasos = escalones_de_cascada({
        "utilidad_neta": 54_809_000.0,
        "ffo": 124_722_000.0,
        "ffo_normalizado": 135_983_000.0,
        "affo": 137_983_000.0,
    })
    inicio = next(v for _, v, es in pasos if es)
    puentes = sum(v for _, v, es in pasos if not es)
    ultimo = [v for _, v, es in pasos if es][-1]
    assert inicio + puentes == pytest.approx(ultimo)


def test_el_self_storage_no_tiene_renta_en_linea_recta_que_reclamarle():
    """Se renta mes con mes: no hay contrato de varios años que promediar.

    Public Storage y Extra Space no publican ese ajuste porque en su negocio no
    existe. Reclamárselo es la misma falsa alarma de antes con otra cara, y cada
    falsa alarma le quita peso a la que sí importa: la del net lease.
    """
    componentes = {
        "utilidad_neta": 450_301_000.0,
        "depreciacion_inmuebles": 284_729_000.0,
        "ffo": 742_935_000.0,
    }
    sin_sector = calcular_cascada(componentes, signos=REPORTE).banderas
    assert [b for b in sin_sector if "línea recta" in b], (
        "sin sector no se puede descartar: la alarma se queda"
    )

    storage = calcular_cascada(componentes, sector="Self Storage", signos=REPORTE).banderas
    assert not [b for b in storage if "línea recta" in b]

    hoteles = calcular_cascada(componentes, sector="Hoteles", signos=REPORTE).banderas
    assert not [b for b in hoteles if "línea recta" in b]

    # Y donde el contrato sí dura años con escalador, la alarma sigue sonando.
    net_lease = calcular_cascada(componentes, sector="Net Lease", signos=REPORTE).banderas
    assert [b for b in net_lease if "línea recta" in b]
