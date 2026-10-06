#!/usr/bin/env python3
"""La investigación sobre cuándo entrar a los REITs y en cuáles (``docs/investigacion/PLAN.md``).

    python scripts/investigacion.py sector     # Nareit desde 1972 y los fondos que lo validan
    python scripts/investigacion.py macro      # series de FRED, con su rezago de publicación
    python scripts/investigacion.py factores   # factores de Kenneth French y datos de Shiller
    python scripts/investigacion.py sellar     # mercados de la prueba final: se bajan y se sellan
    python scripts/investigacion.py exploracion  # fase 3: informe de la muestra de desarrollo
    python scripts/investigacion.py fase5      # fase 5: el catálogo pre-registrado de señales de entrada

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


def cmd_exploracion() -> int:
    from src.investigacion import exploracion

    destino = RAIZ / "docs" / "investigacion" / "fase3_exploracion.md"
    destino.write_text(exploracion.informe(), encoding="utf-8")
    print(f"{destino.relative_to(RAIZ)}")
    return 0


def cmd_fase5() -> int:
    from src.investigacion import fase5

    r = fase5.correr_desarrollo()
    texto = fase5.informe(r)
    if not r.candidatas.empty:
        v = fase5.correr_validacion(r.candidatas, motivo="candidatas de la fase 5 según el pre-registro")
        texto += "\n## Validación (2016 en adelante)\n" + fase5.tabla_desarrollo(v.assign(pasa=True))
    destino = RAIZ / "docs" / "investigacion" / "fase5_resultados.md"
    destino.write_text(texto, encoding="utf-8")
    print(f"{destino.relative_to(RAIZ)}: {int(r.desarrollo['pasa'].sum())} reglas pasan el filtro")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("comando", choices=["sector", "macro", "factores", "sellar", "exploracion", "fase5"])
    return {"sector": cmd_sector, "macro": cmd_macro, "factores": cmd_factores, "sellar": cmd_sellar,
            "exploracion": cmd_exploracion, "fase5": cmd_fase5}[p.parse_args().comando]()


if __name__ == "__main__":
    raise SystemExit(main())
