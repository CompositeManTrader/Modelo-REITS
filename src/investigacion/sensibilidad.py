"""Sensibilidad fiscal: las mismas reglas congeladas, con los impuestos de un broker de EE. UU.

Pre-registro: ``docs/investigacion/sensibilidad_broker_preregistro.md``. Toda la
investigación supone que el inversionista compra por el SIC (``diseno.OBJETIVO``); aquí se
repiten las fases 3, 5, 6, 7 y 8 y los estudios de O, NNN y WPC con los perfiles de
``diseno.PERFILES`` (el SIC y un broker de EE. UU. con tasa marginal de 30% y de 35%),
**sin volver a escoger nada**.

Lo que no depende de los impuestos se calcula una vez: las señales, las exposiciones de la
fase 7, la predictibilidad, el PBO, el Sharpe deflactado y el AUC del detector. Los sellados
se abren una vez por corrida, con un modelo congelado propio que repite la regla ya
congelada, y con esos datos se evalúan los tres perfiles.

Cada evaluación queda en la bitácora con la familia ``sensibilidad-fiscal``, separada de las
familias que compiten entre sí: no es una búsqueda, es la misma regla con otros impuestos.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd

from src.investigacion import bitacora, datos, exploracion, fase5, fase6, fase8, muestras, timing
from src.investigacion.diseno import MUESTRAS, NOMBRES_DE_PERFIL, PERFILES, Objetivo
from src.investigacion.exploracion import CORTE_DE_ERAS
from src.investigacion.muestras import Muestra

FAMILIA = "sensibilidad-fiscal"
MOTIVO = ("sensibilidad fiscal (12-oct-2026): las mismas reglas congeladas, con los impuestos de un broker "
          "de EE. UU.")
MODELO_FASE8 = f"{FAMILIA}: {fase8.MODELO}"
REGLA_FINAL6 = "momentum"
MODELO_FASE6 = f"{FAMILIA}: {fase6.MODELO_FINAL}: {REGLA_FINAL6}"
EMISORES = ("NNN", "O", "WPC")
REGLA_FASE7 = "dentro si el pronóstico es positivo"
VARIANTE_MODELO, VARIANTE_BENCHMARK = "Modelo completo", "Aportación fija, sin reglas"   # ``reglas.Variante``
ORDEN_VEREDICTO = {"RECHAZADO": 0, "INCONCLUSO": 1, "APROBADO": 2}


def tasas(o: Objetivo) -> dict:
    return {"dividendo": round(o.impuesto_dividendo, 4), "intereses": round(o.impuesto_intereses, 4),
            "ganancia": round(o.impuesto_ganancia, 4), "comision": round(o.comision, 4)}


def parametros_de(o: Objetivo):
    """Los parámetros del backtest de reglas de los estudios, con los impuestos de ``o``."""
    from src.estudio import reglas

    return replace(reglas.PARAMETROS, impuesto_dividendo=o.impuesto_dividendo, impuesto_ganancia=o.impuesto_ganancia,
                   impuesto_intereses=o.impuesto_intereses, comision=o.comision)


def veredicto_con_perfil(sic: str, otro: str) -> str:
    """Lo que sale mejor solo con el broker se decidió después de ver el SIC: a lo más INCONCLUSO."""
    if ORDEN_VEREDICTO.get(otro, 0) > ORDEN_VEREDICTO.get(sic, 0):
        return "INCONCLUSO (posterior)"
    return otro


def _registrar(fase: str, prueba: str, muestra: str, perfil: str, metrica: str, valor, ruta) -> None:
    v = None if valor is None or pd.isna(valor) else round(float(valor), 6)
    bitacora.registrar(fase=fase, familia=FAMILIA, prueba=prueba, muestra=muestra,
                       parametros={"perfil": perfil, **tasas(PERFILES[perfil])}, metrica=metrica, valor=v, ruta=ruta)


def _eras(x: pd.DataFrame) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    return {"1972-1992": (x.index.min(), CORTE_DE_ERAS),
            "1993-2015": (CORTE_DE_ERAS + pd.offsets.MonthEnd(1), x.index.max())}


# --------------------------------------------------------------------------------------
# Fases 3, 5 y 7: el sector en desarrollo (1972-2015)
# --------------------------------------------------------------------------------------


def fase3(x: pd.DataFrame, perfiles: dict[str, Objetivo] = PERFILES) -> pd.DataFrame:
    return pd.concat([exploracion.techo(x, objetivo=o).tabla.assign(perfil=k) for k, o in perfiles.items()],
                     ignore_index=True)


def _con_eras(senal, regla: str, e: pd.Series, x, ind, o: Objetivo, perfil: str) -> list[dict]:
    filas = []
    for era, (a, b) in _eras(x).items():
        r = timing.evaluar(senal, regla, e.loc[a:b], x.loc[a:b], ind.loc[a:b], muestra=f"desarrollo {era}",
                           registrar=False, objetivo=o, con_prediccion=False)
        filas.append({"perfil": perfil, "senal": senal.nombre, "regla": regla, "era": era,
                      "mejora_rebalanceo": r["mejora_rebalanceo"],
                      "mejora_contra_mezcla_fija": r["mejora_contra_mezcla_fija"]})
    return filas


def _filtro(d: pd.DataFrame, eras: pd.DataFrame) -> list[bool]:
    return [fase5.pasa_el_filtro(f, eras[eras["perfil"] == f["perfil"]]) for _, f in d.iterrows()]


def fase5_(x: pd.DataFrame, ind: pd.DataFrame, perfiles: dict[str, Objetivo] = PERFILES, *,
           registrar: bool = True, ruta_bitacora=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Las 22 reglas de entrada y sus eras con cada perfil. La predictibilidad se calcula una vez."""
    reglas = fase5.reglas_del_catalogo(x, ind)
    prediccion: dict[tuple[str, str], dict] = {}
    filas, eras = [], []
    for k, o in perfiles.items():
        for senal, nombre, e in reglas:
            clave = (senal.nombre, nombre)
            r = timing.evaluar(senal, nombre, e, x, ind, muestra="desarrollo", registrar=False, objetivo=o,
                               con_prediccion=clave not in prediccion)
            if clave not in prediccion:
                prediccion[clave] = {c: v for c, v in r.items() if c.startswith(("r2_", "clark_west_p_"))}
            r.update(prediccion[clave])
            r["perfil"] = k
            filas.append(r)
            eras += _con_eras(senal, nombre, e, x, ind, o, k)
            if registrar:
                _registrar("5", f"{senal.nombre} | {nombre}", "desarrollo", k, "mejora_rebalanceo",
                           r["mejora_rebalanceo"], ruta_bitacora)
    d, eras = timing.resumen(filas), pd.DataFrame(eras)
    d["pasa"] = _filtro(d, eras)
    return d, eras


def fase7_(x: pd.DataFrame, ind: pd.DataFrame, exposiciones: pd.DataFrame, evaluacion_sic: pd.DataFrame,
           perfiles: dict[str, Objetivo] = PERFILES, *, registrar: bool = True, ruta_bitacora=None
           ) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Los cinco peldaños con las exposiciones ya guardadas (los modelos no dependen de los impuestos).

    El R² y el Clark-West del modelo, que tampoco dependen de los impuestos, vienen de la
    evaluación guardada de la fase 7.
    """
    from src.investigacion import fase7

    pred = evaluacion_sic.set_index("senal")
    filas, eras, escaleras = [], [], {}
    for k, o in perfiles.items():
        for nombre in fase7.PELDANOS:
            e = exposiciones[nombre].reindex(x.index)
            senal = timing.Senal(nombre, "fase7", lambda x_, i_, s=e: s, f"Peldaño «{nombre}» de la escalera")
            r = timing.evaluar(senal, REGLA_FASE7, e, x, ind, muestra="desarrollo", registrar=False, objetivo=o,
                               con_prediccion=False)
            for c in ("r2_12m", "clark_west_p_12m"):
                r[c] = pred.loc[nombre, c]
            r["perfil"] = k
            filas.append(r)
            eras += _con_eras(senal, REGLA_FASE7, e, x, ind, o, k)
            if registrar:
                _registrar("7", nombre, "desarrollo", k, "mejora_rebalanceo", r["mejora_rebalanceo"], ruta_bitacora)
    d, eras = timing.resumen(filas), pd.DataFrame(eras)
    d["pasa"] = _filtro(d, eras)
    for k in perfiles:
        quedan, candidato = fase7.escalera(d[d["perfil"] == k])
        escaleras[k] = {"se_quedan": quedan, "candidato": candidato}
    return d, eras, escaleras


# --------------------------------------------------------------------------------------
# Fase 8: la protección por tendencia, en la validación de EE. UU. y en los ocho mercados
# --------------------------------------------------------------------------------------


def fase8_validacion(perfiles: dict[str, Objetivo] = PERFILES, *, registrar: bool = True,
                     ruta_bitacora=None) -> pd.DataFrame:
    """La tendencia en EE. UU. de 2016 en adelante (con su historia de antes para el promedio)."""
    completo = exploracion.sector(Muestra.VALIDACION, motivo=f"{MOTIVO} (fase 8)", ruta_bitacora=ruta_bitacora)
    filas = []
    for k, o in perfiles.items():
        r = fase8._desde(completo, MUESTRAS.validacion_desde, "EE. UU. (validación, 2016 en adelante)", objetivo=o)
        filas.append({**r, "perfil": k})
        if registrar:
            _registrar("8", "proteccion-tendencia-10m | EE. UU.", "validacion", k, "mejora", r["mejora"], ruta_bitacora)
    return pd.DataFrame(filas)


def fase8_mercados(validacion: pd.DataFrame, perfiles: dict[str, Objetivo] = PERFILES, *, registrar: bool = True,
                   ruta_bitacora=None, raiz=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Los ocho mercados sellados: cada uno se abre una vez y con esos datos se evalúan los perfiles."""
    if MODELO_FASE8 not in bitacora.modelos_congelados(ruta_bitacora):
        muestras.congelar(MODELO_FASE8, {**fase8.DESCRIPCION, "motivo": MOTIVO, "perfiles": list(perfiles),
                                         "cambia": "solo los impuestos y la comisión; la regla es la misma"},
                          ruta_bitacora=ruta_bitacora)
    series = {n: fase8.serie_de_mercado(n, raiz=raiz, ruta_bitacora=ruta_bitacora, modelo=MODELO_FASE8)
              for n in datos.MERCADOS_FINALES}
    val = validacion.set_index("perfil")
    filas, conjuntos = [], []
    for k, o in perfiles.items():
        propias = []
        for n, (x, origen) in series.items():
            r = fase8.evaluar_mercado(x, n, objetivo=o)
            propias.append({**r, "serie": origen, "perfil": k})
            if registrar:
                _registrar("8", f"proteccion-tendencia-10m | {n}", "final", k, "mejora", r["mejora"], ruta_bitacora)
        conjunto, veredicto, apuestas = fase8.resumir(pd.DataFrame(propias), val.loc[k].to_dict())
        conjuntos.append({"perfil": k, **conjunto, "apuestas": apuestas, "veredicto": veredicto})
        filas += propias
    c = pd.DataFrame(conjuntos)
    sic = str(c.loc[c["perfil"] == "sic", "veredicto"].iloc[0]) if "sic" in perfiles else "RECHAZADO"
    c["veredicto_declarado"] = [veredicto_con_perfil(sic, x) for x in c["veredicto"]]
    return pd.DataFrame(filas), c


def fase8_(perfiles: dict[str, Objetivo] = PERFILES, *, abrir: bool = True, registrar: bool = True,
           ruta_bitacora=None, raiz=None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    v = fase8_validacion(perfiles, registrar=registrar, ruta_bitacora=ruta_bitacora)
    if not abrir:
        return v, pd.DataFrame(), pd.DataFrame()
    return (v, *fase8_mercados(v, perfiles, registrar=registrar, ruta_bitacora=ruta_bitacora, raiz=raiz))


# --------------------------------------------------------------------------------------
# Fase 6: en cuáles REITs
# --------------------------------------------------------------------------------------


def fase6_desarrollo(panel: pd.DataFrame, perfiles: dict[str, Objetivo] = PERFILES, *, candidatas_sic: list[str],
                     registrar: bool = True, ruta_bitacora=None) -> pd.DataFrame:
    """Las 16 reglas en desarrollo (2009-2015) con cada perfil y el filtro pre-registrado."""
    x = fase6.senales(muestras.recortar(panel, Muestra.DESARROLLO, columna="fecha"))
    desde, hasta = fase6.primera_fecha(x), MUESTRAS.desarrollo_hasta
    filas = []
    for k, o in perfiles.items():
        for regla in fase6.REGLAS:
            f = fase6.evaluar(regla, x, desde=desde, hasta=hasta, muestra="desarrollo", registrar=False,
                              mitades=(fase6.MITAD_DE_DESARROLLO,), objetivo=o)
            f["pasa"], f["perfil"] = fase6.pasa_el_filtro(f), k
            filas.append(f)
            if registrar:
                _registrar("6", regla, "desarrollo", k, "mejora_aportacion", f["mejora"], ruta_bitacora)
    dev = fase6._tabla(filas)
    dev["posterior"] = dev["pasa"] & ~dev["regla"].isin(candidatas_sic)
    return dev


def fase6_validacion(panel: pd.DataFrame, a_validar: list[str], perfiles: dict[str, Objetivo] = PERFILES, *,
                     candidatas_sic: list[str], registrar: bool = True, ruta_bitacora=None) -> pd.DataFrame:
    """Las candidatas del SIC, el detector y lo que pase solo con el broker (posterior), de 2016 en adelante."""
    completo = muestras.recortar(panel, Muestra.VALIDACION, columna="fecha", ruta_bitacora=ruta_bitacora,
                                 motivo=f"{MOTIVO} (fase 6)")
    xv = fase6.senales(completo)
    riesgo = fase6.riesgo_de_recorte(xv)
    hasta = pd.Timestamp(xv["fecha"].max())
    detector = fase6.evaluar_detector(xv, riesgo, desde=MUESTRAS.desarrollo_hasta, hasta=hasta)
    filas = []
    for k, o in perfiles.items():
        for regla in dict.fromkeys([*a_validar, fase6.DETECTOR]):
            f = fase6.evaluar(regla, xv, desde=MUESTRAS.desarrollo_hasta, hasta=hasta, muestra="validacion",
                              riesgo=riesgo, registrar=False, mitades=(fase6.MITAD_DE_VALIDACION,), objetivo=o)
            f["pasa"] = (fase6.pasa_la_validacion_el_detector(f, detector) if regla == fase6.DETECTOR
                         else fase6.pasa_la_validacion(f))
            f["perfil"] = k
            filas.append(f)
            if registrar:
                _registrar("6", regla, "validacion", k, "mejora_aportacion", f["mejora"], ruta_bitacora)
    val = fase6._tabla(filas)
    val["posterior"] = ~val["regla"].isin([*candidatas_sic, fase6.DETECTOR])
    return val


def fase6_final(perfiles: dict[str, Objetivo] = PERFILES, *, pbo: float, dsr: float, registrar: bool = True,
                ruta_bitacora=None, raiz_sellado=None) -> pd.DataFrame:
    """Momentum en los emisores sellados: se abren una vez y se evalúan los tres perfiles.

    El PBO y el Sharpe deflactado usan retornos antes de impuestos: vienen de la corrida
    guardada de la fase 6.
    """
    if MODELO_FASE6 not in bitacora.modelos_congelados(ruta_bitacora):
        muestras.congelar(MODELO_FASE6, {"regla": REGLA_FINAL6, "diseno": repr(fase6.DISENO6), "motivo": MOTIVO,
                                         "perfiles": list(perfiles),
                                         "cambia": "solo los impuestos y la comisión; la regla es la misma"},
                          ruta_bitacora=ruta_bitacora)
    sellado = fase6.abrir_sellados(MODELO_FASE6, raiz_sellado=raiz_sellado, ruta_bitacora=ruta_bitacora)
    filas = []
    for k, o in perfiles.items():
        f = fase6.evaluar_final(sellado, REGLA_FINAL6, registrar=False, objetivo=o)
        f["perfil"], f["veredicto"] = k, fase6.veredicto_final(f, pbo=pbo, dsr=dsr)
        filas.append(f)
        if registrar:
            _registrar("6", REGLA_FINAL6, "final", k, "mejora_aportacion", f["mejora"], ruta_bitacora)
    fin = fase6._tabla(filas)
    sic = str(fin.loc[fin["perfil"] == "sic", "veredicto"].iloc[0]) if "sic" in perfiles else "RECHAZADO"
    fin["veredicto_declarado"] = [veredicto_con_perfil(sic, v) for v in fin["veredicto"]]
    return fin


# --------------------------------------------------------------------------------------
# Estudios de O, NNN y WPC
# --------------------------------------------------------------------------------------


def con_dividendo_neto(e, tasa: float):
    """El estudio con el retorno total neto de ``tasa`` al dividendo (en lugar del 20% del SIC)."""
    from src.estudio import retornos

    t = e.tabla.copy()
    t["rt_usd_neto"] = retornos.indice_retorno_total(e.historia_mercado, fraccion_neta=1 - tasa).reindex(t.index)
    t["rt_mxn_neto"] = t["rt_usd_neto"] * t["usdmxn"]
    return replace(e, serie=replace(e.serie, tabla=t))


def retorno_largo(e, tasa: float) -> dict:
    """Comprar al inicio y reinvertir el dividendo neto: retorno anual en dólares de toda la historia."""
    from src.estudio import retornos

    rt = retornos.indice_retorno_total(e.historia_mercado, fraccion_neta=1 - tasa).dropna()
    anios = (rt.index[-1] - rt.index[0]).days / 365.25
    return {"desde": rt.index[0], "hasta": rt.index[-1], "retorno_anual": float((rt.iloc[-1] / rt.iloc[0]) ** (1 / anios) - 1)}


def estudios_(perfiles: dict[str, Objetivo] = PERFILES, *, construidos: dict | None = None, n_azar: int = 200,
              registrar: bool = True, ruta_bitacora=None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """El semáforo de cada emisor, la asignación entre los tres con cada método y el retorno largo."""
    from src.estudio import estudio, macro, metodos, reglas

    construidos = construidos or {t: estudio.armar_versionado(t) for t in EMISORES}
    tbill, baa, cpi = reglas.cargar_tbill(), macro.cargar("baa"), macro.cargar("cpi")
    # Los percentiles de los métodos no dependen de los impuestos.
    paneles = {t: metodos.panel(e, baa=baa, cpi=cpi, tbill=tbill) for t, e in construidos.items()}
    m = metodos.mercado_comun(construidos)
    semaforo, asignacion, largo = [], [], []
    for k, o in perfiles.items():
        p = parametros_de(o)
        for t, e in construidos.items():
            r = reglas.backtest(con_dividendo_neto(e, o.impuesto_dividendo), tbill=tbill, parametros=p)
            for variante, f in r.tabla.iterrows():
                semaforo.append({"perfil": k, "emisor": t, "variante": variante, "tir_usd": f["tir_usd"],
                                 "ventaja_tir_usd": f["ventaja_tir_usd"], "desde": r.desde, "hasta": r.hasta})
            largo.append({"perfil": k, "emisor": t, **retorno_largo(e, o.impuesto_dividendo)})
            if registrar:
                _registrar("estudios", f"semaforo | {t}", "historia", k, "ventaja_tir_usd",
                           r.tabla.loc[VARIANTE_MODELO, "ventaja_tir_usd"], ruta_bitacora)
        for x in metodos.METODOS:
            a = metodos.asignar(m, paneles, x.clave, n_azar=n_azar, parametros=p)
            asignacion.append({"perfil": k, "clave": x.clave, "metodo": a.metodo, "desde": a.desde, "hasta": a.hasta,
                               "tir_usd": a.tir_usd, "tir_partes_iguales": a.tir_partes_iguales, "ventaja": a.ventaja,
                               "ventaja_el_mas_caro": a.ventaja_el_mas_caro, "azar_que_le_gana": a.azar_que_le_gana,
                               **{f"ventaja_{n.split(' (')[0].replace(' ', '_')}": v for n, v in a.mitades}})
            if registrar:
                _registrar("estudios", f"asignacion | {x.clave}", "historia", k, "ventaja", a.ventaja, ruta_bitacora)
    return pd.DataFrame(semaforo), pd.DataFrame(asignacion), pd.DataFrame(largo)


# --------------------------------------------------------------------------------------
# Todo junto
# --------------------------------------------------------------------------------------


@dataclass
class ResultadoSensibilidad:
    tablas: dict[str, pd.DataFrame]
    escaleras: dict = field(default_factory=dict)
    notas: dict = field(default_factory=dict)

    def __getitem__(self, nombre: str) -> pd.DataFrame:
        return self.tablas.get(nombre, pd.DataFrame())


def _aperturas(ruta_bitacora, desde: int) -> dict:
    b = bitacora.leer(ruta_bitacora).iloc[desde:]
    a = b[b["familia"] == "apertura"]
    return {"validacion": int((a["prueba"] == "abrir validacion").sum()),
            "sellados": int(a["prueba"].str.startswith("abrir ").sum() - (a["prueba"] == "abrir validacion").sum()),
            "congelados": sorted(b.loc[b["familia"] == "congelado", "prueba"])}


def correr(*, abrir_sellados: bool = True, con_estudios: bool = True, perfiles: dict[str, Objetivo] = PERFILES,
           ruta_bitacora=None, raiz_sellado=None, resultados_guardados: dict | None = None, panel=None,
           construidos: dict | None = None, n_azar: int = 200) -> ResultadoSensibilidad:
    from src.investigacion import emisores, resultados

    guardado = resultados_guardados if resultados_guardados is not None else resultados.cargar()
    inicio = len(bitacora.leer(ruta_bitacora))
    t: dict[str, pd.DataFrame] = {}
    x = exploracion.sector(Muestra.DESARROLLO)
    ind = exploracion.indicadores(x)
    t["fase3_techo"] = fase3(x, perfiles)
    t["fase5_desarrollo"], t["fase5_eras"] = fase5_(x, ind, perfiles, ruta_bitacora=ruta_bitacora)
    expo = guardado["fase7"]["exposiciones"].set_index("fecha")
    t["fase7_evaluacion"], t["fase7_eras"], escaleras = fase7_(x, ind, expo, guardado["fase7"]["evaluacion"], perfiles,
                                                               ruta_bitacora=ruta_bitacora)
    if panel is None:
        panel, _ = emisores.cargar()
    r6 = guardado["fase6"]["resumen"]
    dev = t["fase6_desarrollo"] = fase6_desarrollo(panel, perfiles, candidatas_sic=r6["candidatas"],
                                                   ruta_bitacora=ruta_bitacora)
    a_validar = list(dict.fromkeys([*r6["candidatas"], *dev.loc[dev["pasa"], "regla"]]))
    t["fase6_validacion"] = fase6_validacion(panel, a_validar, perfiles, candidatas_sic=r6["candidatas"],
                                             ruta_bitacora=ruta_bitacora)
    t["fase8_validacion"] = fase8_validacion(perfiles, ruta_bitacora=ruta_bitacora)
    if con_estudios:
        t["estudios_semaforo"], t["estudios_asignacion"], t["estudios_retorno_largo"] = estudios_(
            perfiles, construidos=construidos, n_azar=n_azar, ruta_bitacora=ruta_bitacora)
    # Los sellados, al final: se abren una vez y no hay nada después que pueda obligar a repetir.
    if abrir_sellados:
        t["fase6_final"] = fase6_final(perfiles, pbo=r6["pbo"], dsr=r6["sharpe_deflactado"],
                                       ruta_bitacora=ruta_bitacora, raiz_sellado=raiz_sellado)
        t["fase8_mercados"], t["fase8_conjunto"] = fase8_mercados(t["fase8_validacion"], perfiles,
                                                                  ruta_bitacora=ruta_bitacora, raiz=raiz_sellado)
    t["perfiles"] = pd.DataFrame([{"perfil": k, "nombre": NOMBRES_DE_PERFIL.get(k, k),
                                   **{f"tasa_{c}" if c != "comision" else "comision_pct": v
                                      for c, v in tasas(o).items()}} for k, o in perfiles.items()])
    r = ResultadoSensibilidad(t, escaleras)
    t["resumen"], t["bases"] = resumen(r), bases(r)
    r.notas = {"aperturas": _aperturas(ruta_bitacora, inicio), "sellados_abiertos": abrir_sellados,
               "con_estudios": con_estudios, "pbo_fase6": r6["pbo"], "sharpe_deflactado_fase6": r6["sharpe_deflactado"],
               "candidatas_fase6_sic": r6["candidatas"], "reevaluaciones": bitacora.intentos(FAMILIA, ruta=ruta_bitacora)}
    return r


# --------------------------------------------------------------------------------------
# El resumen: una fila por prueba de cabecera, un valor por perfil
# --------------------------------------------------------------------------------------


def _valor(d: pd.DataFrame, columna: str, **filtro) -> dict[str, float]:
    if d.empty:
        return {}
    m = pd.Series(True, index=d.index)
    for c, v in filtro.items():
        m &= d[c] == v
    return d[m].set_index("perfil")[columna].astype(float).to_dict()


def resumen(r: ResultadoSensibilidad) -> pd.DataFrame:
    """Las pruebas que deciden cada conclusión, con su mejora (pb al año) en cada perfil."""
    filas = []

    def fila(fase: str, prueba: str, valores: dict, criterio: str = "", veredictos: dict | None = None) -> None:
        if valores:
            filas.append({"fase": fase, "prueba": prueba, "criterio": criterio,
                          **{f"{k}_pb": v * 1e4 for k, v in valores.items()},
                          **{f"veredicto_{k}": v for k, v in (veredictos or {}).items()}})

    t3 = r["fase3_techo"]
    if not t3.empty:
        base = _valor(t3, "tir", regla="aportar siempre")
        for prueba, regla, modo in (
                ("Oráculo de 12 meses, solo dinero nuevo (techo de entrar bien)",
                 "oráculo de los 12 meses siguientes", "nunca vende"),
                ("Oráculo: fuera en cada caída de 20% o más, rebalanceando",
                 "fuera en cada caída de 20% o más (del máximo al mínimo)", "rebalancea")):
            fila("3", prueba, {k: v - base[k] for k, v in _valor(t3, "tir", regla=regla, modo=modo).items()},
                 "techo, no es regla")
    d5 = r["fase5_desarrollo"]
    if not d5.empty:
        pasan = d5.groupby("perfil")["pasa"].sum().to_dict()
        fila("5", "Mejor de las 22 reglas de entrada, rebalanceando", d5.groupby("perfil")["mejora_rebalanceo"].max()
             .to_dict(), "pasar el filtro", {k: _cuantas(n, 22, pasan.get("sic", 0)) for k, n in pasan.items()})
        fila("5", "Tendencia de 10 meses (signo)",
             _valor(d5, "mejora_rebalanceo", senal="tendencia de 10 meses", regla="signo"), "pasar el filtro")
    d7 = r["fase7_evaluacion"]
    if not d7.empty:
        fila("7", "Mejor peldaño de la escalera", d7.groupby("perfil")["mejora_rebalanceo"].max().to_dict(),
             "ganarle a aportar siempre",
             {k: f"candidato: {e['candidato']}" if e["candidato"] else "sin candidato (RECHAZADO)"
              for k, e in r.escaleras.items()})
    fila("8", "Protección por tendencia, EE. UU. 2016 en adelante", _valor(r["fase8_validacion"], "mejora"),
         "costo ≤ 25 pb")
    c8 = r["fase8_conjunto"]
    if not c8.empty:
        fila("8", "Protección por tendencia, promedio de los 8 mercados", _valor(c8, "mejora"),
             "costo ≤ 25 pb y 30% menos caída", c8.set_index("perfil")["veredicto_declarado"].to_dict())
    d6, v6, f6 = r["fase6_desarrollo"], r["fase6_validacion"], r["fase6_final"]
    if not d6.empty:
        pasan = d6.groupby("perfil")["pasa"].sum().to_dict()
        fila("6", "Momentum, desarrollo", _valor(d6, "mejora", regla="momentum"), "pasar el filtro",
             {k: _cuantas(n, 16, pasan.get("sic", 0)) for k, n in pasan.items()})
        fila("6", "Yield de dividendo alto, desarrollo", _valor(d6, "mejora", regla="rendimiento_del_dividendo"),
             "pasar el filtro")
        fila("6", "Calidad y barato (FFO), desarrollo", _valor(d6, "mejora", regla="calidad y barato"),
             "pasar el filtro")
    if not v6.empty:
        fila("6", "Momentum, validación", _valor(v6, "mejora", regla="momentum"), "≥ +50 pb")
    if not f6.empty:
        fila("6", "Momentum, emisores sellados (prueba final)", _valor(f6, "mejora"), "≥ +50 pb",
             f6.set_index("perfil")["veredicto_declarado"].to_dict())
    s = r["estudios_semaforo"]
    if not s.empty:
        for t in sorted(s["emisor"].unique()):
            fila("estudios", f"Semáforo de {t}: modelo completo contra aportar siempre",
                 _valor(s, "ventaja_tir_usd", emisor=t, variante=VARIANTE_MODELO), "> 0")
    a = r["estudios_asignacion"]
    if not a.empty:
        fila("estudios", "Asignación entre O, NNN y WPC: consenso contra partes iguales",
             _valor(a, "ventaja", clave="consenso"), "> 0")
    return pd.DataFrame(filas)


def _cuantas(n: int, total: int, en_el_sic: int) -> str:
    texto = f"{int(n)} de {total} pasan"
    return texto + " (posterior)" if n > en_el_sic else texto


def bases(r: ResultadoSensibilidad) -> pd.DataFrame:
    """La TIR de aportar siempre (o de aportar a todos) en cada muestra y perfil: lo que el broker
    le quita o le da al inversionista que no hace timing."""
    filas = []

    def agregar(muestra: str, valores: dict) -> None:
        for k, v in valores.items():
            filas.append({"muestra": muestra, "perfil": k, "tir": v})

    if not r["fase3_techo"].empty:
        agregar("Sector EE. UU., 1972-2015", _valor(r["fase3_techo"], "tir", regla="aportar siempre"))
    if not r["fase8_validacion"].empty:
        agregar("Sector EE. UU., 2016 en adelante", _valor(r["fase8_validacion"], "tir_aportar_siempre"))
    if not r["fase8_mercados"].empty:
        m = r["fase8_mercados"]
        agregar("Ocho mercados sellados (promedio)", m[m["cuenta"]].groupby("perfil")["tir_aportar_siempre"].mean()
                .to_dict())
    for nombre, muestra in (("fase6_desarrollo", "Todos los REITs de capital, 2009-2015"),
                            ("fase6_final", "REITs sellados, 2012 en adelante")):
        d = r[nombre]
        if not d.empty:
            agregar(muestra, d.groupby("perfil")["tir_todos"].first().to_dict())
    s = r["estudios_semaforo"]
    if not s.empty:
        for t in sorted(s["emisor"].unique()):
            agregar(f"{t}, aportando cada mes desde que hay datos", _valor(s, "tir_usd", emisor=t, variante=VARIANTE_BENCHMARK))
    d = pd.DataFrame(filas)
    if d.empty:
        return d
    d = d.pivot_table(index="muestra", columns="perfil", values="tir", sort=False).reset_index()
    d.columns.name = None
    return d


def guardar(r: ResultadoSensibilidad, *, raiz: Path | None = None) -> Path:
    from src.investigacion.resultados import DIR_RESULTADOS, _csv, _json

    d = (raiz or DIR_RESULTADOS) / "sensibilidad_broker"
    for nombre, tabla in r.tablas.items():
        if not tabla.empty:
            _csv(tabla, d / f"{nombre}.csv")
    _json({"escaleras": r.escaleras, **r.notas}, d / "notas.json")
    return d


def cargar(raiz: Path | None = None) -> ResultadoSensibilidad | None:
    from src.investigacion.resultados import DIR_RESULTADOS

    d = (raiz or DIR_RESULTADOS) / "sensibilidad_broker"
    if not d.exists():
        return None
    tablas = {a.stem: pd.read_csv(a) for a in sorted(d.glob("*.csv"))}
    notas = json.loads((d / "notas.json").read_text(encoding="utf-8")) if (d / "notas.json").exists() else {}
    return ResultadoSensibilidad(tablas, notas.pop("escaleras", {}), notas)



# --------------------------------------------------------------------------------------
# El informe
# --------------------------------------------------------------------------------------

PERFILES_EN_ORDEN = ("sic", "broker_30", "broker_35")
CORTO = {"sic": "SIC", "broker_30": "Broker 30%", "broker_35": "Broker 35%"}


def _pb(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    x = round(float(v) * 1e4)
    return f"{x:+,d}" if x else "0"


def _p(v, d: int = 1) -> str:
    return "—" if v is None or pd.isna(v) else f"{float(v) * 100:.{d}f}%"


def _md(filas: list[list[str]], encabezado: list[str]) -> str:
    return ("\n| " + " | ".join(encabezado) + " |\n|" + "|".join("---" for _ in encabezado) + "|\n"
            + "".join("| " + " | ".join(str(c) for c in f) + " |\n" for f in filas) + "\n")


def fallas_fase5(f: pd.Series, eras: pd.DataFrame, filtro: fase5.Filtro = fase5.FILTRO) -> list[str]:
    """Qué criterios del filtro de la fase 5 no cumple una regla (vacío si pasa)."""
    fallas = []
    if not f["mejora_rebalanceo"] > filtro.mejora_minima:
        fallas.append("no le gana a aportar siempre")
    if not f["mejora_contra_mezcla_fija"] > filtro.contra_mezcla_fija_minima:
        fallas.append("no le gana a la mezcla fija")
    if not f["mejora_rebalanceo_con_rezago"] > 0:
        fallas.append("pierde con un mes de retraso")
    if not f["mejora_rebalanceo_doble_costo"] > 0:
        fallas.append("pierde con doble costo")
    e = eras[(eras["perfil"] == f["perfil"]) & (eras["senal"] == f["senal"]) & (eras["regla"] == f["regla"])]
    if not (len(e) == 2 and bool((e["mejora_rebalanceo"] > 0).all())):
        fallas.append("pierde en una era")
    if not ((f["r2_12m"] > 0) or (f["clark_west_p_12m"] < filtro.alfa_predictivo)):
        fallas.append("no predice a 12 meses")
    return fallas


def _ancho(d: pd.DataFrame, indice, valor: str) -> pd.DataFrame:
    return d.pivot_table(index=indice, columns="perfil", values=valor, sort=False)


def _perfiles_md() -> str:
    filas = [[NOMBRES_DE_PERFIL.get(k, k), _p(o.impuesto_dividendo, 0), _p(o.impuesto_intereses, 0),
              _p(o.impuesto_ganancia, 0), _p(o.comision, 2)] for k, o in PERFILES.items()]
    return _md(filas, ["Perfil", "Dividendo", "Intereses del efectivo", "Ganancia al vender", "Comisión"])


def informe(r: ResultadoSensibilidad) -> str:
    """La sensibilidad en Markdown, con el veredicto de cada fase en cada perfil."""
    o = ["# Sensibilidad fiscal: comprar con un broker de EE. UU. Resultados\n\n",
         "Pre-registro: `sensibilidad_broker_preregistro.md` (commit anterior a esta corrida). Las mismas reglas y "
         "los mismos modelos congelados de las fases 3 a 8 y de los estudios de O, NNN y WPC, con los impuestos de "
         "comprar directo con un broker de EE. UU. y lado a lado con los del SIC. No se escogió nada nuevo. "
         "Generado por `python scripts/investigacion.py broker`.\n\n"]
    o.append("## Los perfiles\n" + _perfiles_md())
    o.append("El dividendo de un REIT comprado con un broker paga la tasa marginal más 9 puntos (Art. 142 fr. V "
             "LISR, con crédito por el 10% que retiene EE. UU. con el W-8BEN); los intereses del efectivo, la "
             "marginal; la ganancia, 10% (Art. 129 LISR y Criterio 37/ISR/N del SAT para acciones listadas en el "
             "SIC, aunque se vendan con un intermediario extranjero). La tasa marginal no se conoce: se corren 30% y "
             "35%. Fuera del modelo: el impuesto sucesorio de EE. UU. para no residentes con más de 60 mil dólares "
             "en activos de EE. UU. Todo esto debe confirmarse con un contador.\n\n")
    o.append(_veredicto(r))
    o.append(_bases_md(r))
    o.append(_resumen_md(r))
    o.append(_fase5_md(r))
    o.append(_fase7_md(r))
    o.append(_fase8_md(r))
    o.append(_fase6_md(r))
    o.append(_estudios_md(r))
    o.append(_hipotesis_md(r))
    o.append(_bitacora_md(r))
    o.append("## Límites\n\n"
             "* Una sola tasa marginal para todo el ingreso; la tarifa real es progresiva.\n"
             "* Todo lo que reparte un REIT se trata como dividendo. Parte puede ser devolución de capital o "
             "ganancia de capital, con otro trato.\n"
             "* No se modelan la ganancia cambiaria, el ajuste por inflación del costo ni el impuesto sucesorio.\n"
             "* Los mercados fuera de EE. UU. de la fase 8 usan el mismo perfil, como en la línea base: un REIT de "
             "Japón o de Australia tiene otra retención.\n"
             "* En la fase 6 el efectivo no cobra intereses (es transitorio y afecta igual a la regla y a todos), "
             "así que la tasa de los intereses no cambia nada ahí.\n"
             "* Con comisión de 0%, la prueba de doble costo no cambia nada con el broker.\n")
    return "".join(o)


def _veredicto(r: ResultadoSensibilidad) -> str:
    o = ["## Veredicto\n\n"]
    d5 = r["fase5_desarrollo"]
    if not d5.empty:
        pasan = d5.groupby("perfil")["pasa"].sum()
        o.append(f"* **Fase 5 (cuándo entrar):** {int(pasan.get('sic', 0))} de 22 reglas pasan el filtro con el SIC, "
                 f"{int(pasan.get('broker_30', 0))} con el broker al 30% y {int(pasan.get('broker_35', 0))} al 35%. ")
        mejor = d5.loc[d5[d5["perfil"] == "broker_35"]["mejora_rebalanceo"].idxmax()]
        o.append(f"La mejor con el broker al 35% es «{mejor['senal']} | {mejor['regla']}» con "
                 f"{_pb(mejor['mejora_rebalanceo'])} pb al año; falla en: {', '.join(fallas_fase5(mejor, r['fase5_eras']))}.\n")
    if r.escaleras:
        cand = {k: e["candidato"] or "ninguno" for k, e in r.escaleras.items()}
        o.append(f"* **Fase 7 (la escalera de modelos):** candidato con el SIC: {cand.get('sic')}; con el broker: "
                 f"{cand.get('broker_30')} (30%) y {cand.get('broker_35')} (35%).\n")
    c8 = r["fase8_conjunto"]
    if not c8.empty:
        c = c8.set_index("perfil")
        o.append("* **Fase 8 (protección por tendencia en los 8 mercados sellados):** "
                 + "; ".join(f"{CORTO[k]}: {c.loc[k, 'veredicto_declarado']} ({_pb(c.loc[k, 'mejora'])} pb al año, "
                             f"{c.loc[k, 'fraccion_protege']:.0%} de los mercados protege)" for k in PERFILES_EN_ORDEN
                             if k in c.index) + ".\n")
    f6 = r["fase6_final"]
    if not f6.empty:
        f = f6.set_index("perfil")
        o.append("* **Fase 6 (en cuáles REITs), momentum en los emisores sellados:** "
                 + "; ".join(f"{CORTO[k]}: {_pb(f.loc[k, 'mejora'])} pb ({f.loc[k, 'veredicto_declarado']})"
                             for k in PERFILES_EN_ORDEN if k in f.index) + ". El umbral es +50 pb.\n")
    a = r["estudios_asignacion"]
    if not a.empty:
        v = _valor(a, "ventaja", clave="consenso")
        o.append("* **Estudios, asignación entre O, NNN y WPC con el consenso:** "
                 + "; ".join(f"{CORTO[k]}: {_pb(v[k])} pb" for k in PERFILES_EN_ORDEN if k in v) + ".\n")
    o.append("\n")
    return "".join(o)


def _bases_md(r: ResultadoSensibilidad) -> str:
    b = r["bases"]
    if b.empty:
        return ""
    filas = [[f["muestra"], *[_p(f.get(k), 2) for k in PERFILES_EN_ORDEN],
              _pb(f.get("broker_30") - f.get("sic")), _pb(f.get("broker_35") - f.get("sic"))] for _, f in b.iterrows()]
    return ("## Lo que el broker le cuesta a quien aporta siempre\n\nTIR de aportar cada mes al índice o al emisor, "
            "sin ninguna regla, después de impuestos y comisiones.\n"
            + _md(filas, ["Muestra", "SIC", "Broker 30%", "Broker 35%", "Broker 30% contra SIC (pb)",
                          "Broker 35% contra SIC (pb)"]))


def _resumen_md(r: ResultadoSensibilidad) -> str:
    s = r["resumen"]
    if s.empty:
        return ""
    filas = []
    for _, f in s.iterrows():
        ver = " / ".join(str(f.get(f"veredicto_{k}")) for k in PERFILES_EN_ORDEN
                         if pd.notna(f.get(f"veredicto_{k}", np.nan)))
        filas.append([f["fase"], f["prueba"], *[_pb(f.get(f"{k}_pb", np.nan) / 1e4) for k in PERFILES_EN_ORDEN],
                      f["criterio"], ver or "—"])
    return ("## Las pruebas que deciden cada conclusión\n\nMejora en puntos base al año de TIR contra su "
            "comparación (aportar siempre, aportar a todos o partes iguales). Veredictos en el orden SIC / broker "
            "30% / broker 35%.\n"
            + _md(filas, ["Fase", "Prueba", "SIC (pb)", "Broker 30% (pb)", "Broker 35% (pb)", "Criterio",
                          "Veredicto"]))


def _fase5_md(r: ResultadoSensibilidad) -> str:
    d, eras = r["fase5_desarrollo"], r["fase5_eras"]
    if d.empty:
        return ""
    w = _ancho(d, ["senal", "regla"], "mejora_rebalanceo")
    b35 = {(f["senal"], f["regla"]): f for _, f in d[d["perfil"] == "broker_35"].iterrows()}
    filas = []
    for (s, rg), f in w.sort_values("broker_35", ascending=False).iterrows():
        filas.append([s, rg, *[_pb(f.get(k)) for k in PERFILES_EN_ORDEN],
                      "pasa" if b35[(s, rg)]["pasa"] else "; ".join(fallas_fase5(b35[(s, rg)], eras))])
    return ("## Fase 5: las 22 reglas de entrada, en desarrollo (1972-2015)\n\nMejora rebalanceando, en pb al año "
            "contra aportar siempre. La última columna dice qué criterio del filtro pre-registrado falla con el "
            "broker al 35%.\n" + _md(filas, ["Señal", "Regla", "SIC", "Broker 30%", "Broker 35%",
                                              "Con el broker al 35%"]))


def _fase7_md(r: ResultadoSensibilidad) -> str:
    d = r["fase7_evaluacion"]
    if d.empty:
        return ""
    w = _ancho(d, "senal", "mejora_rebalanceo")
    ex = d[d["perfil"] == "sic"].set_index("senal")["exposicion_rebalanceo"]
    filas = [[s, *[_pb(f.get(k)) for k in PERFILES_EN_ORDEN], _p(ex.get(s), 0)] for s, f in w.iterrows()]
    return ("## Fase 7: la escalera de modelos, en desarrollo\n\nLos modelos no dependen de los impuestos: se "
            "usan las mismas exposiciones de la fase 7. «Compuesto» y «ridge» están siempre dentro, así que son "
            "aportar siempre (mejora cero).\n"
            + _md(filas, ["Peldaño", "SIC (pb)", "Broker 30% (pb)", "Broker 35% (pb)", "Exposición promedio"]))


def _fase8_md(r: ResultadoSensibilidad) -> str:
    v, m = r["fase8_validacion"], r["fase8_mercados"]
    o = ["## Fase 8: la protección por tendencia\n\n"]
    if not v.empty:
        vv = v.set_index("perfil")
        o.append("En la validación de EE. UU. (2016 en adelante) la tendencia queda en "
                 + ", ".join(f"{_pb(vv.loc[k, 'mejora'])} pb ({CORTO[k]})" for k in PERFILES_EN_ORDEN
                             if k in vv.index) + " al año contra aportar siempre.\n")
    if not m.empty:
        w = _ancho(m, "mercado", "mejora")
        pr = _ancho(m.assign(protege=m["protege"].astype(float)), "mercado", "protege")
        filas = [[fase8.NOMBRES.get(n, n), *[_pb(f.get(k)) for k in PERFILES_EN_ORDEN],
                  " / ".join("sí" if pr.loc[n, k] else "no" for k in PERFILES_EN_ORDEN)] for n, f in w.iterrows()]
        o.append(_md(filas, ["Mercado", "SIC (pb)", "Broker 30% (pb)", "Broker 35% (pb)",
                             "Protege (SIC / 30% / 35%)"]))
    return "".join(o) + "\n"


def _fase6_md(r: ResultadoSensibilidad) -> str:
    d, v, f = r["fase6_desarrollo"], r["fase6_validacion"], r["fase6_final"]
    if d.empty:
        return ""
    o = ["## Fase 6: en cuáles REITs\n\n"]
    w = _ancho(d, "regla", "mejora")
    pasa = _ancho(d.assign(pasa=d["pasa"].astype(float)), "regla", "pasa")
    filas = [[fase6.NOMBRES.get(rg, rg), *[_pb(x.get(k)) for k in PERFILES_EN_ORDEN],
              " / ".join("sí" if pasa.loc[rg, k] else "no" for k in PERFILES_EN_ORDEN)]
             for rg, x in w.sort_values("broker_35", ascending=False).iterrows()]
    o.append("Desarrollo (2009-2015), mejora contra aportar a todos los elegibles:\n"
             + _md(filas, ["Regla", "SIC (pb)", "Broker 30% (pb)", "Broker 35% (pb)", "Pasa (SIC / 30% / 35%)"]))
    if not v.empty:
        w = _ancho(v, "regla", "mejora")
        pasa = _ancho(v.assign(pasa=v["pasa"].astype(float)), "regla", "pasa")
        post = v.groupby("regla")["posterior"].first()
        filas = [[fase6.NOMBRES.get(rg, rg) + (" (posterior)" if post.get(rg) else ""),
                  *[_pb(x.get(k)) for k in PERFILES_EN_ORDEN],
                  " / ".join("sí" if pasa.loc[rg, k] else "no" for k in PERFILES_EN_ORDEN)] for rg, x in w.iterrows()]
        o.append("Validación (2016 en adelante):\n" + _md(filas, ["Regla", "SIC (pb)", "Broker 30% (pb)",
                                                                  "Broker 35% (pb)", "Pasa (SIC / 30% / 35%)"]))
    if not f.empty:
        ff = f.set_index("perfil")
        filas = [[CORTO[k], _pb(ff.loc[k, "mejora"]), _pb(ff.loc[k, "mejora_con_rezago"]),
                  _pb(ff.loc[k, "mejora_doble_costo"]), _p(ff.loc[k, "tir_todos"], 2), ff.loc[k, "veredicto"],
                  ff.loc[k, "veredicto_declarado"]] for k in PERFILES_EN_ORDEN if k in ff.index]
        o.append("Momentum en los emisores sellados (2012 en adelante), con el código corregido de la fase 6:\n"
                 + _md(filas, ["Perfil", "Mejora (pb)", "Con retraso (pb)", "Doble costo (pb)",
                               "TIR de aportar a todos", "Veredicto del criterio", "Veredicto declarado"]))
        o.append(f"El PBO ({r.notas.get('pbo_fase6', np.nan):.2f}) y el Sharpe deflactado "
                 f"({r.notas.get('sharpe_deflactado_fase6', np.nan):.2f}, umbral 0.95) usan retornos antes de "
                 "impuestos: son los de la fase 6 y no cambian con el perfil.\n\n")
    return "".join(o)


def _estudios_md(r: ResultadoSensibilidad) -> str:
    s, a, lg = r["estudios_semaforo"], r["estudios_asignacion"], r["estudios_retorno_largo"]
    if s.empty:
        return ""
    o = ["## Estudios de O, NNN y WPC\n\n"]
    w = _ancho(s[s["variante"] != VARIANTE_BENCHMARK], ["emisor", "variante"], "ventaja_tir_usd")
    filas = [[t, v, *[_pb(f.get(k)) for k in PERFILES_EN_ORDEN]] for (t, v), f in w.iterrows()]
    o.append("Semáforo (backtest de reglas): ventaja de TIR en dólares contra aportar cada mes al mismo papel.\n"
             + _md(filas, ["Emisor", "Variante", "SIC (pb)", "Broker 30% (pb)", "Broker 35% (pb)"]))
    if not a.empty:
        w = _ancho(a, ["clave", "metodo"], "ventaja")
        filas = [[mt, *[_pb(f.get(k)) for k in PERFILES_EN_ORDEN]] for (_, mt), f in w.iterrows()]
        o.append("Asignación entre los tres: toda la aportación al más barato contra su historia, contra partes "
                 "iguales.\n" + _md(filas, ["Método", "SIC (pb)", "Broker 30% (pb)", "Broker 35% (pb)"]))
    if not lg.empty:
        w = _ancho(lg, "emisor", "retorno_anual")
        desde = lg.groupby("emisor")["desde"].first()
        filas = [[t, f"{pd.Timestamp(desde[t]):%Y}", *[_p(f.get(k), 2) for k in PERFILES_EN_ORDEN]]
                 for t, f in w.iterrows()]
        o.append("Comprar y mantener reinvirtiendo el dividendo neto: retorno anual en dólares de toda la historia.\n"
                 + _md(filas, ["Emisor", "Desde", "SIC", "Broker 30%", "Broker 35%"]))
    return "".join(o)


def _si(c: bool) -> str:
    return "Se cumple" if c else "No se cumple"


def _hipotesis_md(r: ResultadoSensibilidad) -> str:
    o = ["## Lo que se escribió antes de correr\n\n"]
    b = r["bases"]
    if not b.empty:
        f = b.set_index("muestra").iloc[0]
        dif = [f["sic"] - f[k] for k in ("broker_30", "broker_35")]
        o.append(f"* **H-B1, aportar siempre pierde de 120 a 180 pb al año en 1972-2015.** "
                 f"{_si(all(0.012 <= x <= 0.018 for x in dif))}: pierde {_pb(dif[0])[1:]} y {_pb(dif[1])[1:]} pb.\n")
    d5 = r["fase5_desarrollo"]
    if not d5.empty:
        w = _ancho(d5, ["senal", "regla"], "mejora_rebalanceo")
        mejoran = int((w["broker_35"] > w["sic"]).sum())
        pasan = int(d5[d5["perfil"] != "sic"]["pasa"].sum())
        cand = [e["candidato"] for k, e in r.escaleras.items() if k != "sic" and e["candidato"]]
        o.append(f"* **H-B2, el timing mejora un poco pero no cambia el veredicto.** {_si(pasan == 0 and not cand)}: "
                 f"{mejoran} de {len(w)} reglas salen mejor con el broker al 35% que con el SIC, pero ninguna pasa el "
                 f"filtro{' y la escalera no deja candidato' if not cand else ''}.\n")
    c8 = r["fase8_conjunto"]
    if not c8.empty:
        c = c8.set_index("perfil")
        rech = all(c.loc[k, "veredicto"] == "RECHAZADO" for k in c.index if k != "sic")
        o.append(f"* **H-B3, la protección por tendencia sigue RECHAZADA y cuesta menos.** "
                 f"{_si(rech and c.loc['broker_35', 'mejora'] > c.loc['sic', 'mejora'])}: "
                 f"{_pb(c.loc['sic', 'mejora'])} pb con el SIC contra {_pb(c.loc['broker_35', 'mejora'])} con el "
                 f"broker al 35%.\n")
    f6 = r["fase6_final"]
    if not f6.empty:
        f = f6.set_index("perfil")
        o.append(f"* **H-B4, momentum mejora en los sellados; si cruza +50 pb, queda INCONCLUSO posterior.** "
                 f"{_si(f.loc['broker_35', 'mejora'] > f.loc['sic', 'mejora'])}: {_pb(f.loc['sic', 'mejora'])} pb con "
                 f"el SIC y {_pb(f.loc['broker_35', 'mejora'])} con el broker al 35% "
                 f"({f.loc['broker_35', 'veredicto_declarado']}).\n")
    d6 = r["fase6_desarrollo"]
    if not d6.empty:
        w = _ancho(d6, "regla", "mejora")
        peor = [rg for rg in ("rendimiento_del_dividendo", "calidad y barato") if w.loc[rg, "broker_35"] < w.loc[rg, "sic"]]
        o.append(f"* **H-B5, el yield alto y «calidad y barato» salen peor.** {_si(len(peor) == 2)}: yield alto "
                 f"{_pb(w.loc['rendimiento_del_dividendo', 'sic'])} → {_pb(w.loc['rendimiento_del_dividendo', 'broker_35'])}"
                 f" pb; calidad y barato {_pb(w.loc['calidad y barato', 'sic'])} → "
                 f"{_pb(w.loc['calidad y barato', 'broker_35'])} pb.\n")
    a = r["estudios_asignacion"]
    if not a.empty:
        v = _valor(a, "ventaja", clave="consenso")
        o.append(f"* **H-B6, la ventaja del consenso baja.** {_si(v['broker_35'] < v['sic'])}: {_pb(v['sic'])} pb con "
                 f"el SIC y {_pb(v['broker_35'])} con el broker al 35%.\n")
    s = r["estudios_semaforo"]
    if not s.empty:
        w = _ancho(s[s["variante"] == VARIANTE_MODELO], "emisor", "ventaja_tir_usd")
        cambio = (w[["broker_30", "broker_35"]].sub(w["sic"], axis=0)).abs().max(axis=1)
        o.append(f"* **H-B7, el semáforo cambia menos de 20 pb en cada emisor.** {_si(bool((cambio < 0.002).all()))}: "
                 + ", ".join(f"{t} {_pb(c)[1:] if _pb(c) != '0' else '0'} pb" for t, c in cambio.items())
                 + " de cambio máximo.\n")
    return "".join(o) + "\n"


def _bitacora_md(r: ResultadoSensibilidad) -> str:
    a = r.notas.get("aperturas", {})
    return ("## Aperturas y bitácora\n\n"
            f"Esta corrida abrió la validación {a.get('validacion', 0)} veces (fases 6 y 8) y los archivos sellados "
            f"{a.get('sellados', 0)} veces: los tres archivos de cada uno de los ocho mercados y los emisores "
            "sellados, una vez cada uno, con los tres perfiles evaluados sobre los mismos datos. Modelos congelados "
            "antes de abrir: " + ", ".join(f"`{c}`" for c in a.get("congelados", [])) + ". Los ocho mercados ya se "
            "habían abierto tres veces con el modelo de la fase 8 y los emisores sellados una vez con el de la fase "
            f"6. La bitácora guarda {r.notas.get('reevaluaciones', 0)} reevaluaciones con la familia "
            f"`{FAMILIA}`; no cuentan como intentos de búsqueda.\n\n")
