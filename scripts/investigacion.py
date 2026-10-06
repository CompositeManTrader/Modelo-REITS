#!/usr/bin/env python3
"""La investigación sobre cuándo entrar a los REITs y en cuáles (``docs/investigacion/PLAN.md``).

    python scripts/investigacion.py sector     # Nareit desde 1972 y los fondos que lo validan
    python scripts/investigacion.py macro      # series de FRED, con su rezago de publicación
    python scripts/investigacion.py factores   # factores de Kenneth French y datos de Shiller
    python scripts/investigacion.py sellar     # mercados de la prueba final: se bajan y se sellan
    python scripts/investigacion.py emisores   # fase 6: todos los REITs de EE. UU. con la SEC (pide SEC_USER_AGENT)
    python scripts/investigacion.py exploracion  # fase 3: informe de la muestra de desarrollo
    python scripts/investigacion.py fase5      # fase 5: el catálogo pre-registrado de señales de entrada
    python scripts/investigacion.py fase6      # fase 6: en cuáles REITs (abre la validación y, si toca, los sellados)
    python scripts/investigacion.py fase7      # fase 7: la escalera de modelos
    python scripts/investigacion.py fase8      # fase 8: la prueba final (abre los mercados sellados)
    python scripts/investigacion.py pdf        # el informe en PDF, con los resultados guardados

Solo estos comandos tocan la red. La página de Nareit pide un navegador real: Chromium
necesita las autoridades del sistema en su almacén de certificados. En un contenedor
nuevo se cargan una vez, sin desactivar ninguna verificación:

    apt-get install -y libnss3-tools
    awk '/BEGIN CERT/{n++} {print > ("c-" n ".pem")}' /root/.ccr/ca-bundle.crt
    for f in c-*.pem; do certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n "$f" -i "$f"; done
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.investigacion import datos  # noqa: E402


def cmd_sector() -> int:
    from src.estudio import universo

    with tempfile.TemporaryDirectory() as tmp:
        xls = datos.bajar_nareit(Path(tmp) / "MonthlyHistoricalReturns.xls")
        nareit = datos.leer_nareit(xls)
        revision = datos.revisar_nareit(nareit)
        precios, _, _, fallas = universo.bajar_historias(list(datos.FONDOS), pausa=1.0)
        fondos = datos.retornos_mensuales(precios)
        validacion = datos.validar_contra_fondos(nareit, fondos)
        destino = datos.guardar_sector(nareit, fondos, revision=revision, validacion=validacion)
        (destino / "fuente").mkdir(exist_ok=True)
        (destino / "fuente" / xls.name).write_bytes(xls.read_bytes())
    print(f"Nareit: {nareit['indice'].nunique()} índices, {nareit['fecha'].min():%Y-%m} a {nareit['fecha'].max():%Y-%m}")
    print(validacion[["fondo", "meses", "correlacion", "error_de_seguimiento"]].round(3).to_string(index=False))
    if fallas:
        print("fallas:", fallas)
    return 0


def cmd_macro() -> int:
    x, fallas = datos.bajar_fred()
    datos.guardar_macro(x, fallas)
    print(f"{x['serie'].nunique()} series de FRED; fallas: {fallas or 'ninguna'}")
    return 0


def cmd_factores() -> int:
    datos.guardar_factores(datos.bajar_french(), datos.bajar_shiller())
    print("Factores de French y datos de Shiller guardados.")
    return 0


def cmd_sellar() -> int:
    for mercado, r in datos.sellar_mercados().items():
        print(f"{mercado}: {r['tickers_con_datos']} series; fallas: {r['fallas'] or 'ninguna'}")
    return 0


def cmd_emisores() -> int:
    """Universo, precios de los 13F y estados de XBRL. La identificación ante la SEC viene de la
    variable de entorno SEC_USER_AGENT y no se escribe en ningún archivo."""
    import datetime as dt

    import pandas as pd
    import requests

    from src.config import SEC_USER_AGENT
    from src.ingesta.edgar import ClienteEdgar
    from src.investigacion import emisores, sec

    cliente = ClienteEdgar(SEC_USER_AGENT)
    sesion = requests.Session()
    sesion.headers["User-Agent"] = SEC_USER_AGENT
    d = emisores.bajar(cliente, sesion)
    tickers = cliente.obtener_json("https://www.sec.gov/files/company_tickers.json")
    etiquetas = emisores.etiquetas_actuales({v["ticker"]: str(v["cik_str"]).zfill(10) for v in tickers.values()})
    manual = pd.read_csv(emisores.DIR_EMISORES / "clasificacion_manual.csv", dtype={"cik": str})
    panel, ficha = emisores.armar(d["resumen"], d["fts"], d["agregado"], d["series"], d["dividendos"], etiquetas,
                                  manual)
    yahoo = pd.read_csv(RAIZ / "data" / "estudios" / "universo" / "precios_mensuales.csv.gz", parse_dates=["fecha"])
    manifiesto = {
        "descargado_en": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "fuentes": {
            "universo": "EDGAR: empresas con SIC 6798 y búsqueda de texto completo de 10-K de 2009 a 2026 "
                        f"({', '.join(sec.FRASES_REIT)})",
            "cusip": "Portadas de los 13G y 13D presentados sobre cada emisor (dígito verificador)",
            "precios": "Formulario 13F: conjuntos estructurados de la SEC desde 2013 y 13F en texto de "
                       f"{len(emisores.GESTORES_13F_TEXTO)} administradores de 2009 a 2013",
            "estados": "XBRL companyfacts de la SEC, primera versión publicada de cada periodo",
            "etiquetas_de_clase": "Estudio del universo (stockanalysis) para los que cotizan hoy; "
                                  "clasificacion_manual.csv para los dudosos",
        },
        "emisores": {"candidatos": int(len(ficha)), "con_precio": int(ficha["con_precio"].sum()),
                     "clase_final": ficha["clase_final"].value_counts().to_dict()},
        "trimestres": [f"{panel['fecha'].min():%Y-%m-%d}", f"{panel['fecha'].max():%Y-%m-%d}"],
        "validacion_contra_yahoo": emisores.validar_contra_yahoo(panel, ficha, etiquetas, yahoo),
        "validacion_ffo": emisores.validar_ffo(d["series"]),
    }
    destino = emisores.guardar(panel, ficha, manifiesto)
    print(f"{destino.relative_to(RAIZ)}: {manifiesto['emisores']}")
    print(manifiesto["validacion_contra_yahoo"])
    print(manifiesto["validacion_ffo"])
    return 0


def cmd_exploracion() -> int:
    from src.investigacion import exploracion, resultados

    destino = RAIZ / "docs" / "investigacion" / "fase3_exploracion.md"
    destino.write_text(exploracion.informe(), encoding="utf-8")
    resultados.guardar_fase3(exploracion.sector())
    print(f"{destino.relative_to(RAIZ)}")
    return 0


def cmd_fase5() -> int:
    from src.investigacion import fase5

    r = fase5.correr_desarrollo()
    texto = fase5.informe(r)
    if not r.candidatas.empty:
        v = fase5.correr_validacion(r.candidatas, motivo="candidatas de la fase 5 según el pre-registro")
        texto += "\n## Validación (2016 en adelante)\n" + fase5.tabla_desarrollo(v.assign(pasa=True))
    from src.investigacion import resultados

    destino = RAIZ / "docs" / "investigacion" / "fase5_resultados.md"
    destino.write_text(texto, encoding="utf-8")
    resultados.guardar_fase5(r)
    print(f"{destino.relative_to(RAIZ)}: {int(r.desarrollo['pasa'].sum())} reglas pasan el filtro")
    return 0


def cmd_fase6() -> int:
    from src.investigacion import emisores, fase6, resultados

    panel, _ = emisores.cargar()
    r = fase6.correr(panel)
    resultados.guardar_fase6(r)
    destino = RAIZ / "docs" / "investigacion" / "fase6_resultados.md"
    destino.write_text(fase6.informe(r), encoding="utf-8")
    print(destino.relative_to(RAIZ))
    print(f"desarrollo: {int(r.desarrollo['pasa'].sum())} de {len(r.desarrollo)} pasan; candidatas {r.candidatas}")
    print(f"validación: {r.validacion[['regla', 'mejora', 'pasa']].to_dict('records')}")
    print(f"detector: {r.recortes}")
    print(f"veredicto: {r.veredicto}")
    return 0


def cmd_fase7() -> int:
    from src.investigacion import fase7

    r = fase7.correr_desarrollo()
    from src.investigacion import resultados

    destino = RAIZ / "docs" / "investigacion" / "fase7_resultados.md"
    destino.write_text(fase7.informe(r), encoding="utf-8")
    resultados.guardar_fase7(r)
    print(f"{destino.relative_to(RAIZ)}: candidato {r.candidato or 'ninguno'}")
    return 0


def cmd_fase8() -> int:
    from src.investigacion import fase8

    r = fase8.correr()
    from src.investigacion import resultados

    destino = RAIZ / "docs" / "investigacion" / "fase8_resultados.md"
    destino.write_text(fase8.informe(r), encoding="utf-8")
    resultados.guardar_fase8(r)
    print(f"{destino.relative_to(RAIZ)}: {r.veredicto}")
    return 0


def cmd_pdf() -> int:
    from src.export.pdf_investigacion import generar_pdf
    from src.investigacion import resultados

    destino = generar_pdf(resultados.cargar(), RAIZ / "docs" / "investigacion" / "investigacion_cuando_entrar.pdf")
    print(f"{destino.relative_to(RAIZ)} ({destino.stat().st_size / 1024:,.0f} KB)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("comando", choices=["sector", "macro", "factores", "sellar", "emisores", "exploracion", "fase5",
                                       "fase6", "fase7", "fase8", "pdf"])
    return {"sector": cmd_sector, "macro": cmd_macro, "factores": cmd_factores, "sellar": cmd_sellar,
            "emisores": cmd_emisores,
            "exploracion": cmd_exploracion, "fase5": cmd_fase5, "fase6": cmd_fase6, "fase7": cmd_fase7,
            "fase8": cmd_fase8, "pdf": cmd_pdf}[p.parse_args().comando]()


if __name__ == "__main__":
    raise SystemExit(main())
