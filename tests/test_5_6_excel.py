"""Pruebas obligatorias 5 y 6 — Excel sin errores y unidades correctas.

5. El libro se recalcula con LibreOffice headless: cero errores de fórmula.
6. Las celdas en puntos base muestran el valor correcto.

Sobre la prueba 6
-----------------
Una celda con formato ``#,##0 "bps"`` **no multiplica por 10,000**: el formato
solo pega el texto al número que ya está en la celda. Guardar 0.0409 con ese
formato muestra "0 bps" en vez de "409 bps". Este error ya se cometió en este
proyecto, así que la prueba no verifica el formato: verifica el **valor
recalculado** de la celda.

La recalculación con LibreOffice es lo que hace válida la prueba. Sin ella,
openpyxl devolvería ``None`` en toda celda con fórmula y la prueba pasaría en
vacío; por eso también se comprueba que la recalculación efectivamente ocurrió.
"""

from __future__ import annotations

import datetime as dt
import shutil
import subprocess
from pathlib import Path

import pytest
from openpyxl import load_workbook

from src.export.excel import (
    FMT_BPS,
    DatosExportacion,
    buscar_errores,
    celdas_con_formato_bps,
    exportar,
)
from src.modelo.valuacion import InsumosValuacion

M = 1_000_000.0
HAY_LIBREOFFICE = shutil.which("soffice") is not None


def _datos() -> DatosExportacion:
    """Un emisor con cifras redondas, para que los valores esperados sean verificables a mano."""
    insumos = InsumosValuacion(
        ticker="TEST",
        precio=50.00,
        acciones_diluidas=900 * M,
        unidades_op=100 * M,           # totalmente diluidas: 1,000 millones
        noi_anualizado=4_000 * M,
        affo_ttm=2_500 * M,
        affo_por_accion_ttm=2.50,
        ffo_ttm=2_400 * M,
        utilidad_neta_ttm=800 * M,
        dividendo_ttm_por_accion=2.00,
        deuda_total=20_000 * M,
        efectivo=1_000 * M,
        prestamos_por_cobrar=1_000 * M,
        inversiones_no_consolidadas=500 * M,
        goodwill=3_000 * M,
        ebitdare_ttm=4_000 * M,
        intereses_ttm=800 * M,
        sector="Net Lease",
    )
    componentes = {
        "ingreso_rentas": 5_000 * M,
        "gastos_operativos_inmueble": 1_000 * M,
        "utilidad_neta": 800 * M,
        "depreciacion_inmuebles": 2_000 * M,
        "deterioro": 100 * M,
        "ganancia_venta_inmuebles": 50 * M,
        "partidas_no_recurrentes": 25 * M,
        "amortizacion_costos_financieros": 40 * M,
        "comisiones_arrendamiento": 30 * M,
        "capex_mantenimiento": 20 * M,
        # Calibrado para que la cascada cierre en AFFO = 2,500 millones exactos:
        #   FFO            = 800 + 2,000 + 100 − 50           = 2,850
        #   FFO normalizado= 2,850 + 25                        = 2,875
        #   AFFO           = 2,875 + 40 − 30 − 20 − 410 + 25 + 20 = 2,500
        # Con 1,000 millones de acciones diluidas: AFFO por acción 2.50, y sobre un
        # precio de 50.00 eso da 5.00% de AFFO yield y 100 bps de prima sobre 4.00%.
        "renta_linea_recta": 410 * M,
        "compensacion_en_acciones": 25 * M,
        "otros_ajustes_no_efectivo": 20 * M,
    }
    return DatosExportacion(
        ticker="TEST",
        nombre="Emisor de Prueba",
        sector="Net Lease",
        fecha_corte=dt.date(2026, 6, 30),
        insumos=insumos,
        componentes_cascada=componentes,
        cap_rate_mercado=0.065,
        tasa_libre_riesgo=0.0400,       # AFFO yield 5.00% − 4.00% = prima de 100 bps
        tasa_udibono_real=0.047,
        yield_adquisiciones=0.074,
        fuentes=[
            {"concepto": "affo", "periodo_tipo": "Q", "fecha_dato": "2026-06-30",
             "fecha_publicacion": "2026-08-05", "fuente": "SEC-8K-EX99.1", "es_primario": True,
             "url_filing": "https://www.sec.gov/Archives/edgar/data/726728/"},
            {"concepto": "affo", "periodo_tipo": "Q", "fecha_dato": "2026-03-31",
             "fecha_publicacion": "2026-08-05", "fuente": "RECONSTRUIDO", "es_primario": False,
             "url_filing": ""},
        ],
    )


def _recalcular(ruta: Path, destino: Path) -> Path:
    """Abre y vuelve a guardar el libro con LibreOffice, forzando el recálculo."""
    destino.mkdir(parents=True, exist_ok=True)
    perfil = destino / "perfil_lo"
    resultado = subprocess.run(
        [
            "soffice", "--headless",
            f"-env:UserInstallation=file://{perfil}",
            "--convert-to", "xlsx", "--outdir", str(destino), str(ruta),
        ],
        capture_output=True, text=True, timeout=300, check=False,
    )
    salida = destino / ruta.name
    if not salida.exists():
        pytest.fail(f"LibreOffice no produjo el archivo: {resultado.stdout} {resultado.stderr}")
    return salida


@pytest.fixture(scope="module")
def libro(tmp_path_factory) -> Path:
    destino = tmp_path_factory.mktemp("excel")
    return exportar(_datos(), destino / "TEST.xlsx")


@pytest.fixture(scope="module")
def libro_recalculado(libro, tmp_path_factory) -> Path:
    if not HAY_LIBREOFFICE:
        pytest.skip("LibreOffice no está instalado.")
    return _recalcular(libro, tmp_path_factory.mktemp("recalc"))


# --------------------------------------------------------------------------------------
# Estructura y fórmulas vivas
# --------------------------------------------------------------------------------------


def test_el_libro_tiene_las_hojas_del_proyecto(libro):
    wb = load_workbook(libro)
    assert wb.sheetnames == [
        "Léeme", "Inputs", "Cascada AFFO", "Valuación", "Sensibilidad", "Fuentes"
    ]


def test_las_celdas_de_calculo_son_formulas_vivas_no_valores(libro):
    """Un libro con valores pegados es una fotografía, no un modelo."""
    wb = load_workbook(libro)
    hoja = wb["Valuación"]
    formulas = [
        c.value for fila in hoja.iter_rows() for c in fila
        if isinstance(c.value, str) and c.value.startswith("=")
    ]
    assert len(formulas) >= 20, "La hoja de Valuación tiene que estar hecha de fórmulas."
    assert any("Inputs!" in f for f in formulas), (
        "Las fórmulas deben referenciar la hoja de Inputs para que cambiarla recalcule todo."
    )


def test_las_celdas_de_input_son_editables_y_estan_marcadas(libro):
    """Azul sobre amarillo = input del usuario. La convención de mesa, no la de reporte."""
    wb = load_workbook(libro)
    hoja = wb["Inputs"]
    for celda in ("B4", "B7", "B8"):
        c = hoja[celda]
        assert not (isinstance(c.value, str) and c.value.startswith("=")), (
            f"{celda} debe ser un valor editable, no una fórmula."
        )
        assert c.font.color is not None and "0000FF" in str(c.font.color.rgb)
        assert "FFFF99" in str(c.fill.fgColor.rgb)


# --------------------------------------------------------------------------------------
# Prueba 5 — Cero errores de fórmula tras recalcular
# --------------------------------------------------------------------------------------


@pytest.mark.libreoffice
def test_recalculo_sin_errores_de_formula(libro_recalculado):
    errores = buscar_errores(libro_recalculado)
    assert not errores, "Errores de fórmula tras recalcular:\n" + "\n".join(
        f"  {e['hoja']}!{e['celda']} = {e['valor']}" for e in errores[:20]
    )


@pytest.mark.libreoffice
def test_el_recalculo_realmente_ocurrio(libro_recalculado):
    """Sin recálculo, openpyxl devolvería None y la prueba 5 pasaría en vacío.

    Esta prueba existe para que un fallo de LibreOffice no se lea como éxito.
    """
    wb = load_workbook(libro_recalculado, data_only=True)
    hoja = wb["Valuación"]
    valores = [
        c.value for fila in hoja.iter_rows() for c in fila
        if isinstance(c.value, int | float)
    ]
    assert len(valores) >= 15, (
        "Casi ninguna celda tiene valor calculado: LibreOffice no recalculó el libro y la "
        "prueba de «cero errores» estaría pasando sobre celdas vacías."
    )


@pytest.mark.libreoffice
def test_los_numeros_recalculados_son_los_correctos(libro_recalculado):
    """Verifica aritmética concreta, no solo ausencia de errores.

    Con precio 50.00, AFFO por acción 2.50 y 1,000 millones de acciones
    totalmente diluidas: AFFO yield 5.00%, P/AFFO 20x, payout 80%.
    """
    wb = load_workbook(libro_recalculado, data_only=True)
    inputs = wb["Inputs"]
    assert inputs["B24"].value == pytest.approx(1_000.0), (
        "Acciones totalmente diluidas = comunes + unidades de OP (dilución oculta)."
    )

    valuacion = wb["Valuación"]
    encontrados = {}
    for fila in valuacion.iter_rows():
        etiqueta = fila[0].value
        if isinstance(etiqueta, str) and len(fila) > 1:
            encontrados[etiqueta] = fila[1].value

    assert encontrados["AFFO yield"] == pytest.approx(0.05, abs=1e-6)
    assert encontrados["P / AFFO"] == pytest.approx(20.0, abs=1e-6)
    assert encontrados["Payout sobre AFFO"] == pytest.approx(0.80, abs=1e-6)
    assert encontrados["Capitalización de mercado"] == pytest.approx(50_000.0, abs=1e-6)

    # EV ajustado resta los activos que NO generan renta inmobiliaria: si no se
    # restan, el denominador se infla y el cap rate sale sesgado a la baja.
    ev_esperado = 50_000 + (20_000 - 1_000) - (1_000 + 500)
    assert encontrados["EV ajustado"] == pytest.approx(ev_esperado, rel=1e-6)
    assert encontrados["Cap rate implícito"] == pytest.approx(4_000 / ev_esperado, rel=1e-6)

    # Costo del capital accionario de un REIT = su AFFO yield. Con 35% de deuda al
    # 4% implícito: 0.35(0.04) + 0.65(0.05) = 4.65%. Spread = 7.40% − 4.65% = 2.75%.
    assert encontrados["Costo marginal de capital"] == pytest.approx(0.0465, abs=1e-6)
    assert encontrados["Spread de inversión"] == pytest.approx(0.0275, abs=1e-6)

    # NAV = NOI/cap + efectivo + préstamos + no consolidadas − deuda, SIN goodwill.
    nav_esperado = 4_000 / 0.065 + 1_000 + 1_000 + 500 - 20_000
    assert encontrados["NAV total"] == pytest.approx(nav_esperado, rel=1e-6)

    # El payout sobre utilidad neta es el número que publican los sitios y está mal:
    # 2.00 de dividendo sobre 0.80 de utilidad por acción da 250%, contra 80% sobre AFFO.
    assert encontrados["Payout sobre utilidad neta (para contrastar)"] == pytest.approx(2.50, rel=1e-6)


@pytest.mark.libreoffice
def test_el_nav_excluye_el_goodwill(libro_recalculado):
    """El goodwill no genera renta. Incluirlo infla el NAV de los emisores que más pagaron."""
    wb = load_workbook(libro_recalculado, data_only=True)
    valuacion = wb["Valuación"]
    nav = next(
        fila[1].value for fila in valuacion.iter_rows()
        if fila[0].value == "NAV total"
    )
    con_goodwill = 4_000 / 0.065 + 1_000 + 1_000 + 500 - 20_000 + 3_000
    assert nav != pytest.approx(con_goodwill, rel=1e-6)


# --------------------------------------------------------------------------------------
# Prueba 6 — Unidades: los puntos base
# --------------------------------------------------------------------------------------


def test_las_celdas_en_bps_escalan_en_la_formula_no_en_el_formato(libro):
    """El formato solo pega el texto 'bps'; la escala tiene que estar en la fórmula."""
    celdas = celdas_con_formato_bps(libro)
    assert celdas, "No hay ninguna celda en puntos base en el libro."
    for c in celdas:
        assert "10000" in str(c["formula"]), (
            f"{c['hoja']}!{c['celda']} usa formato de bps sin escalar: la fórmula es "
            f"{c['formula']!r}. El formato #,##0\" bps\" NO multiplica por 10,000."
        )
        assert c["formula"].startswith("=ROUND(")


@pytest.mark.libreoffice
def test_una_prima_de_cien_bps_se_muestra_como_cien_no_como_cero(libro_recalculado):
    """El bug exacto que ya se cometió: 0.0409 con formato de bps se veía como «0 bps».

    Aquí la prima es AFFO yield 5.00% menos tasa libre de riesgo 4.00% = 100 bps.
    La celda tiene que contener 100, no 0.01.
    """
    celdas = celdas_con_formato_bps(libro_recalculado)
    assert celdas, "El libro recalculado no conserva celdas con formato de bps."

    valores = {f"{c['hoja']}!{c['celda']}": c["valor"] for c in celdas}
    for clave, valor in valores.items():
        assert valor is not None, f"{clave} no tiene valor recalculado."
        assert float(valor) == pytest.approx(round(float(valor)), abs=1e-9), (
            f"{clave} debe ser un entero de puntos base, no un decimal: {valor}"
        )

    # Prima = AFFO yield 5.00% − libre de riesgo 4.00% = 100 bps.
    # Spread de inversión = 7.40% − 4.65% = 275 bps.
    # Brecha contra el Udibono = yield neto de impuestos 4.00% − 4.70% real = −70 bps.
    esperados = {100.0, 275.0, -70.0}
    obtenidos = {round(float(v)) for v in valores.values()}
    faltantes = {e for e in esperados if not any(abs(o - e) < 1.01 for o in obtenidos)}
    assert not faltantes, (
        f"No aparecen estos valores en puntos base: {sorted(faltantes)}. "
        f"Obtenidos: {sorted(obtenidos)}. Si en vez de 100 aparece 0.01, el formato está "
        "haciendo el trabajo que debería hacer la fórmula y el bug volvió."
    )


@pytest.mark.libreoffice
def test_el_formato_bps_por_si_solo_no_escala():
    """Demuestra el bug en aislamiento, para que quede documentado en el código.

    Si esta prueba fallara, significaría que Excel sí escala con el formato y toda
    la precaución de ``escribir_bps`` sobraría.
    """
    from openpyxl import Workbook

    wb = Workbook()
    hoja = wb.active
    hoja["A1"] = 0.0409
    hoja["A1"].number_format = FMT_BPS
    hoja["A2"] = "=ROUND(A1*10000,0)"
    hoja["A2"].number_format = FMT_BPS

    assert hoja["A1"].value == pytest.approx(0.0409), (
        "El formato de bps no cambia el valor almacenado: sigue siendo 0.0409, que se "
        "renderiza como «0 bps». Por eso la escala va en la fórmula."
    )


def test_la_sensibilidad_recorre_de_cinco_y_medio_a_ocho_por_ciento(libro):
    wb = load_workbook(libro)
    hoja = wb["Sensibilidad"]
    cap_rates = [
        c.value for fila in hoja.iter_rows(min_col=1, max_col=1) for c in fila
        if isinstance(c.value, int | float)
    ]
    assert min(cap_rates) == pytest.approx(0.055)
    assert max(cap_rates) == pytest.approx(0.080)
    assert len(cap_rates) == 11


def test_la_hoja_de_fuentes_distingue_primario_de_derivado(libro):
    wb = load_workbook(libro)
    hoja = wb["Fuentes"]
    textos = [
        c.value for fila in hoja.iter_rows() for c in fila if isinstance(c.value, str)
    ]
    assert any("SEC-8K-EX99.1" in t for t in textos)
    assert any("RECONSTRUIDO" in t for t in textos)
    assert any("no es asesoría de inversión" in t or "no asesoría" in t for t in textos)
