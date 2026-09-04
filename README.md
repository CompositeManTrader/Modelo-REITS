# Plataforma de valuación de REITs y construcción de portafolio

Valuación de REITs estadounidenses con rigor de analista, partiendo de los
estados financieros originales; construcción y monitoreo de portafolio; y el
comparativo cuantitativo contra comprar un inmueble en renta en CDMX.

Interfaz y código comentado en español de México.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

python scripts/sembrar.py        # datos de DEMOSTRACIÓN, para recorrer la app
streamlit run app/Inicio.py

python scripts/ingesta.py        # datos de fuente primaria desde la SEC
python scripts/cobertura.py      # cuánto parsea y valida el sistema, por emisor
pytest -q                        # las ocho pruebas obligatorias y el resto
```

> Esto es una herramienta de análisis, no asesoría de inversión. Los cálculos
> fiscales son indicativos: confirma con tu casa de bolsa y con un contador.

---

## Los diez principios, y dónde vive cada uno

Cada principio es una restricción de arquitectura con una prueba que falla si se
viola. No son convenciones que el código respete por buena voluntad.

| # | Principio | Dónde está codificado | Prueba |
|---|---|---|---|
| P1 | Point-in-time o nada | `datos/esquema.py`, `datos/repositorio.py` | `test_1_anti_lookahead.py` |
| P2 | Precio SIN ajustar | `ingesta/precios.py`, `validacion/anclas.py` | `test_4_anclas_precio.py` |
| P3 | El AFFO es el número | `modelo/cascada.py` | `test_2_3_cuadre_y_coherencia.py` |
| P4 | Nunca compares niveles de yield | `modelo/senal.py` | `test_principios_modelo.py` |
| P5 | Percentil con ventana expandible | `modelo/senal.py` | `test_1`, `test_principios_modelo.py` |
| P6 | El benchmark es el MISMO activo | `simulacion/backtest.py` | `test_7_8_backtest.py` |
| P7 | Cuenta apuestas efectivas | `simulacion/backtest.py` | `test_7_8_backtest.py` |
| P8 | Neutraliza beta | `simulacion/backtest.py` | `test_7_8_backtest.py` |
| P9 | TIR money-weighted | `portafolio/metricas.py` | `test_7_8`, `test_portafolio_*` |
| P10 | El benchmark real es el Udibono | `simulacion/escenarios.py`, `app/Inicio.py` | `test_principios_modelo.py` |

### Cómo se hacen imposibles algunos errores

**No existe una consulta de hechos sin fecha de corte.** `Repositorio.hechos()`
exige `asof` como argumento obligatorio y `exigir_corte()` falla ruidosamente si
falta. No hay un valor por omisión de "hoy", porque un corte implícito es la
puerta de entrada al lookahead en cuanto el código se reutiliza en un backtest.

**Comparar niveles de yield entre emisores es una excepción, no una advertencia.**
`comparar_yields_crudos()` existe únicamente para lanzar `ComparacionInvalida`.
La página de Sectorial tiene un botón que la llama y muestra el error.

**Una reexpresión es una fila nueva, jamás un `UPDATE`.** Las llaves únicas de las
tablas de hechos incluyen `fecha_publicacion`, así que ambas versiones conviven y
la consulta con corte anterior sigue viendo la vieja.

---

## Arquitectura

```
src/
├── config.py            Universo, umbrales de las tres puertas, catálogos
├── datos/               Esquema point-in-time, repositorio con corte obligatorio, semilla
├── ingesta/             EDGAR, XBRL, parser de AFFO, precios, tasas, orquestador
├── validacion/          Cuadre del AFFO, anclas de precio, prueba de truncamiento
├── modelo/              Cascada, valuación, señal, criterios de venta, sectorial
├── portafolio/          Transacciones, TWR/TIR/atribución, meta y rebalanceo
├── simulacion/          Monte Carlo, backtest, inmueble CDMX, escenarios
├── fiscal/mexico.py     Retenciones, régimen cedular, estate tax, ISR de arrendamiento
├── export/excel.py      Libro con fórmulas VIVAS
└── servicio.py          Capa que arma los paneles de la interfaz
app/                     Streamlit: Inicio + seis páginas
scripts/                 sembrar.py, ingesta.py, cobertura.py, humo_app.py
tests/                   Las ocho obligatorias, los principios, e integración
```

`src/datos/` y `src/servicio.py` no están en el esquema original del proyecto. El
primero existe porque el versionado point-in-time necesita un lugar propio; el
segundo porque sin él cada página de Streamlit consultaría el repositorio
directamente y tarde o temprano alguna olvidaría el corte.

---

## De dónde salen los datos

**Fundamentales: SEC EDGAR, siempre.** Nada de agregadores.

- La API `companyfacts` de XBRL para partidas GAAP. El campo `filed` de cada
  hecho **es** la fecha de publicación point-in-time.
- El AFFO **no está en XBRL**: es una medida no-GAAP. Se extrae del Exhibit 99.1
  de los 8-K de resultados, parseando la conciliación de utilidad neta a FFO y AFFO.
- Los exhibits se localizan por el **tipo declarado en el índice del filing**, no
  por el nombre del archivo: Realty Income nombra su Exhibit 99.1
  `o-991q22026.htm`, sin la cadena "ex99" en ningún lado.
- Límite de la SEC respetado: 10 solicitudes por segundo y User-Agent
  identificable (variable de entorno `SEC_USER_AGENT`).

**Tasas:** UST 10 años, CPI y USD/MXN desde FRED, sin llave. INPC, Cetes, Mbono y
Udibono desde el SIE de Banxico, que sí requiere un token gratuito
(`BANXICO_TOKEN`). Sin token, esas series se cargan de la semilla y se marcan como
demostración.

**Precios:** cierre **sin ajustar**. Toda serie se valida contra al menos tres
cierres verificables antes de usarse, y si el error supera 2% se rechaza.

### Lo que está marcado como demostración

`scripts/sembrar.py` genera datos para poder recorrer la aplicación sin red. Todo
queda marcado `DEMO` y la interfaz lo señala en cada pantalla. **No sirven para
decidir.**

Dos decisiones de diseño de la semilla que valen la pena:

- El precio no es una caminata aleatoria independiente del AFFO. Se construye por
  la identidad que el modelo usa — `precio = múltiplo × AFFO por acción` — con el
  múltiplo revirtiendo a la media. Generarlos por separado producía un REIT con
  16% de AFFO yield y payout de 115%: eso no ejercita el modelo, lo hace ver roto.
- El dividendo sale del AFFO por un payout objetivo, no de `precio × yield`.
  Derivarlo del precio hacía que el payout se moviera con el múltiplo y la puerta
  de deterioro disparara sobre un artefacto de la simulación.

---

## El semáforo: tres puertas, por separado

No es una caja negra. Cada puerta responde una pregunta distinta y se muestra sola.

**Puerta 1 — Calidad. Binaria.** Payout sobre AFFO menor a 90%, AFFO por acción
creciendo, deuda neta/EBITDAre bajo 6.5x, grado de inversión vigente, spread de
inversión positivo. **Lo que falla no está barato: está descartado.** Un emisor con
percentil de prima en 99 y balance roto sale DESCARTADO, no COMPRAR.

**Puerta 2 — Valuación.** Percentil expandible de la prima contra su propia
historia. Alto = comprar, medio = mantener, bajo = no comprar más. **Nunca dispara
venta por sí sola.**

**Puerta 3 — Deterioro.** La única que vende. Payout sobre AFFO arriba de 100% dos
trimestres consecutivos, spread negativo dos trimestres, AFFO por acción cayendo
dos trimestres, apalancamiento arriba de 6.5x, o pérdida del grado de inversión.
El requisito de dos trimestres no es cosmético: los recortes se anuncian después
de un patrón, no después de un dato.

Si el usuario quiere vender por valuación de todos modos, la aplicación ofrece
venta parcial de 25–30% y le muestra el costo fiscal y el listón de ventaja anual
necesario para recuperarlo en dos años.

---

## Las ocho pruebas obligatorias

```bash
pytest -q                                   # todo
pytest tests/test_1_anti_lookahead.py -q    # una en particular
pytest -q -k "not libreoffice"              # sin LibreOffice instalado
```

| # | Qué verifica | Archivo |
|---|---|---|
| 1 | Anti-lookahead: truncar en cuatro puntos, el pasado no se mueve | `test_1_anti_lookahead.py` |
| 2 | Cuadre del AFFO contra el filing real de la SEC | `test_2_3_cuadre_y_coherencia.py` |
| 3 | H1 = Q1 + Q2; FY = suma de los cuatro trimestres | `test_2_3_cuadre_y_coherencia.py` |
| 4 | Anclas de precio: error bajo 2% contra cierres conocidos | `test_4_anclas_precio.py` |
| 5 | Excel recalculado con LibreOffice: cero errores de fórmula | `test_5_6_excel.py` |
| 6 | Unidades: una prima de 100 bps se muestra como 100, no como 0 | `test_5_6_excel.py` |
| 7 | Control negativo: sobre ruido puro, nunca GO | `test_7_8_backtest.py` |
| 8 | Lag de ejecución: la señal de `t` se ejecuta en `t+1` | `test_7_8_backtest.py` |

Cada prueba obligatoria viene con su **control**, porque una prueba que no puede
fallar no prueba nada:

- La prueba 2 altera una partida y verifica que el cuadre **sí** se rompe.
- La prueba 5 verifica que LibreOffice **efectivamente recalculó**; sin eso,
  openpyxl devolvería `None` y la prueba pasaría sobre celdas vacías.
- La prueba 6 demuestra en aislamiento que el formato de bps **no** escala, para
  que quede documentado por qué la escala va en la fórmula.
- La prueba 7 corre también un **control positivo** con un edge plantado y exige
  que la maquinaria lo detecte: un sistema que siempre dice NO-GO parecería
  riguroso cuando en realidad solo está roto.

El fixture del 8-K de Realty Income (`tests/fixtures/`) es un extracto del
Exhibit 99.1 que la SEC publicó el 5 de agosto de 2026. Las pruebas del parser
corren contra él y no contra una maqueta: una maqueta confirma lo que el parser ya
hace; un documento real es lo que encuentra los errores.

---

## Cosas que el parser aprendió del filing real

Probar contra el 8-K de Realty Income encontró cinco defectos que ninguna prueba
sintética habría revelado:

1. **El exhibit no se llamaba "ex99".** La heurística por nombre de archivo lo
   perdía en silencio.
2. **Los paréntesis del negativo vienen en celdas separadas** — `(`, `38,260`, `)`.
   Descartarlos como adorno convertía una ganancia por venta de −38,260 en +38,260:
   un error del doble de la partida que, como el subtotal no cambia, se manifiesta
   como un descuadre que parece venir de otro lado.
3. **Un concepto puede venir repartido en varias filas.** El FFO solo cierra si se
   suman "Proportionate share of adjustments" y "FFO adjustments allocable to
   noncontrolling interests".
4. **La tabla histórica mete el trimestre y el semestre en el mismo `<table>`.**
   Tratarla como un periodo asigna cifras semestrales a un trimestre: un error de
   2x que cuadra consigo mismo y por eso no lo caza ninguna validación aritmética.
5. **El encabezado viene partido en dos filas** — la duración en una, los años en
   la siguiente. Buscar la fecha completa en una sola fila perdía tablas enteras.

Y probar contra los demás emisores del universo encontró tres más:

6. **El signo puede venir en la palabra, no en el número.** Agree Realty escribe
   "Less Series A preferred stock dividends" con el monto en positivo. Sumarlo
   desplaza el subtotal por el doble de la partida.
7. **Un mismo concepto aparece en tramos distintos.** Agree amortiza intangibles
   de arrendamiento antes del FFO y rentas sobre y bajo mercado antes del Core FFO;
   ambas caen en "otros ajustes no-efectivo". Acumularlas juntas mete el segundo
   monto en el tramo del primero y deja al siguiente sin nada que verificar.
8. **Las tablas de guía se colaban como resultados.** Extra Space Storage publica
   su guía del año en el mismo comunicado que su trimestre. Lo cachó la restricción
   `fecha_publicacion >= fecha_dato` del esquema — la última barrera funcionando.

De ahí salieron dos decisiones de diseño:

**Dos convenciones de signo, explícitas.** Los valores del parser vienen ya
signados para sumarse (`signos="reporte"`); los que teclea el usuario son
magnitudes positivas y el signo lo pone la línea (`signos="magnitud"`). Cuadrar con
la convención equivocada da un descuadre de exactamente el doble de cada partida
negativa, fácil de confundir con una línea faltante.

**El cuadre usa el orden de las filas del emisor, no bloques a priori.** Realty
Income pone la participación en no consolidadas y la severancia ejecutiva dentro
del tramo de AFFO; nuestra taxonomía las clasifica en bloques anteriores, y cuadrar
con esa clasificación fallaría por la suma de ambas. Además, un tramo sin partidas
itemizadas se marca **no verificable** en vez de "no cuadra": confundir "no pude
comprobarlo" con "está mal" es justo lo que este proyecto no hace.

Resultado: los diez periodos del exhibit cuadran **exacto** contra los subtotales
que el propio emisor publica.

---

## Estado por hito

| Hito | Estado |
|---|---|
| 1 — Ingesta y validación | Completo. EDGAR, XBRL, parser de AFFO validado contra filing real, esquema point-in-time, pruebas 1–4. |
| 2 — Valuación individual | Completo. Cascada, métricas, tres puertas, Excel con fórmulas vivas, pruebas 5–6. |
| 3 — Interfaz de valuación | Completo. Siete páginas de Streamlit, verificadas de punta a punta. |
| 4 — Portafolio | Completo. Transacciones, TWR/TIR/atribución, capa fiscal, benchmarks. |
| 5 — Comparativo inmobiliario | Completo. Motor CDMX, riesgos cuantificados, solver inverso de plusvalía. |
| 6 — Simulación e innovaciones | Completo. Monte Carlo, replay, reloj de prima, tracker de dividendo real, detector de sesgos, modo «¿qué hubiera pasado?». |

### Limitaciones conocidas

**Cobertura del parser: medida, no estimada.** Corriendo contra los 8-K de la SEC
de 2026 (`python scripts/cobertura.py`):

| Emisor | Periodos extraídos | Válidos | Sospechosos |
|---|---:|---:|---:|
| O | 15 | 15 | 0 |
| ADC | 4 | 4 | 0 |
| EXR | 6 | 1 | 5 |
| NNN | 5 | 0 | 5 |
| WPC | 6 | 0 | 6 |
| PSA | 2 | 0 | 2 |
| WELL | 2 | 0 | 2 |
| EPRT, GNL, PLD | 0 | 0 | 0 |

Cada emisor reporta su conciliación de AFFO con etiquetas ligeramente distintas y
con su propia estructura de tramos. Las causas que quedan **no comparten remedio**:
a W. P. Carey le faltan líneas entre FFO y AFFO, a Welltower una antes del FFO
normalizado, y NNN publica solo subtotales en la tabla que el sistema elige.
Ampliar la cobertura es trabajo de taxonomía emisor por emisor.

Lo importante es que el sistema **se comporta bien cuando no puede**: lo que no
cuadra se guarda marcado `sospechoso`, no entra a ningún cálculo, y la interfaz lo
dice. Prefiere no tener el dato a tenerlo mal.
- **Los identificadores de series del SIE de Banxico están sin verificar contra su
  catálogo.** Son configurables por variable de entorno y el ingestor valida la
  forma de la respuesta antes de escribir, pero conviene confirmarlos.
- **La tarifa del ISR es la del ejercicio 2024.** Se actualiza cada año por
  inflación; está en `fiscal/mexico.py` con la constante `ANIO_TARIFA` a la vista.
- **Las betas de estrés sectorial del replay histórico están calibradas
  cualitativamente** contra el comportamiento observado en 2008 y marzo de 2020,
  no estimadas de una regresión.
- **El suplemento de algunos emisores viene en imágenes**, así que las tablas
  "HISTORICAL FFO AND AFFO" de cinco años no siempre son parseables.
- **Las tablas de guía se descartan, no se ingieren.** Un filing no puede reportar
  cifras realizadas de un periodo que aún no termina, así que el parser filtra los
  periodos que cierran después de la fecha del filing. La guía tiene su propia
  tabla con su propio versionado, pero por ahora se captura a mano.

---

## Automatización

`.github/workflows/tests.yml` corre lint, la suite completa y la prueba de humo de
la interfaz en cada push. Instala LibreOffice Calc, sin el cual la prueba 5 no
puede recalcular el libro.

`.github/workflows/ingest.yml` corre durante las ventanas de reportes (primeras
tres semanas de febrero, mayo, agosto y noviembre), detecta 8-K nuevos, parsea,
valida y escribe. La base viaja como artefacto entre corridas, no como commit: los
datos de mercado no pertenecen al historial de git.

Secretos que hay que configurar: `SEC_USER_AGENT` (obligatorio) y `BANXICO_TOKEN`
(opcional).

---

## Advertencias que la aplicación muestra siempre

- Es una herramienta de análisis, no asesoría de inversión.
- Toda métrica de desempeño va con su conteo de apuestas efectivas.
- La latencia y la fuente de cada dato de mercado están etiquetadas.
- Cuando las observaciones son insuficientes, el veredicto es **INCONCLUSO**, con
  esa palabra, nunca GO.
- Los datos de fuente primaria (SEC, bancos centrales) se distinguen de los
  derivados y reconstruidos en cada pantalla y en la hoja de Fuentes del Excel.
