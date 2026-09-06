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
pytest -q                        # las trece obligatorias y el resto
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

**El formato nunca convierte unidades, y ninguna página escala a mano.** El
`"%.2f%%"` de Streamlit solo pega el símbolo: dibujaría un AFFO yield de `0.0553`
como `0.06%`. La **familia** de cada columna se deduce de su nombre
(`familia_de_columna`, `app/comun.py`) y de ahí salen dos cosas distintas: la
**escala**, que se aplica al dato siempre, y el **formato**, que solo decide cómo
se dibuja. Quien llama manda sobre la etiqueta y el formato; nunca sobre las
unidades.

La primera versión sí dejaba que una `column_config` propia se llevara también la
escala, y el resultado fue exactamente el error que quería evitar: en la portada,
la tabla del Nareit dibujaba 11.78% como «0.12%» y el percentil de prima dibujaba
13% como «0%», porque las dos pasaban configuración propia y quedaban fuera del
escalado. Es el mismo cuidado que con las celdas en puntos base del Excel, donde
una prima de 409 bps se mostraba como «0 bps» por confiar en el formato.

Dos controles lo sostienen: una prueba que **falla si alguna página multiplica por
cien**, y una revisión en `scripts/humo_app.py` que dibuja las siete páginas y
**reprueba si alguna columna porcentual llega a la pantalla valiendo menos de 1**.
Esta segunda es la que caza una columna nueva que las agujas no reconozcan.

---

## Arquitectura

```
src/
├── config.py            Universo, umbrales de las tres puertas, catálogos
├── datos/               Esquema point-in-time, repositorio con corte obligatorio, semilla
├── ingesta/             EDGAR, XBRL, parser de AFFO, precios, tasas, orquestador
│   └── taxonomia.py     Ficha por emisor: SUS etiquetas y SU estructura de tramos
├── validacion/          Cuadre del AFFO, anclas de precio, prueba de truncamiento
├── modelo/              Cascada, valuación, señal, criterios de venta, sectorial
├── portafolio/          Transacciones, TWR/TIR/atribución, meta y rebalanceo
├── simulacion/          Monte Carlo, backtest, inmueble CDMX, escenarios
├── fiscal/mexico.py     Retenciones, régimen cedular, estate tax, ISR de arrendamiento
├── export/excel.py      Libro con fórmulas VIVAS
└── servicio.py          Capa que arma los paneles de la interfaz
app/                     Streamlit: Inicio + seis páginas
scripts/                 sembrar.py, ingesta.py, cobertura.py, ficha.py, humo_app.py
tests/                   Las trece obligatorias, los principios, e integración
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

Cada identificador del SIE se verifica **contra el catálogo**, no contra los datos,
antes de bajar nada. Un identificador equivocado no falla: entrega una serie
perfectamente válida de otro instrumento. Tres de los identificadores originales de
este proyecto estaban mal, y el peor traía la **TIIE a 91 días bajo el nombre de
Udibono** — es decir, P10 comparaba contra una tasa interbancaria nominal en lugar
de contra una tasa real a 10 años. Ningún dato lo habría delatado: 6.8% es creíble
para las dos cosas. Solo el título de la serie lo dice.

| Serie | Identificador | Qué es realmente |
|---|---|---|
| INPC | `SP1` | Índice nacional de precios al consumidor |
| Cetes 28d | `SF43936` | Tasa de rendimiento, subasta semanal |
| Mbono 10a | `SF44071` | Bono tasa fija 10 años, nominal |
| Udibono 10a | `SF43924` | Udibonos 10 años, tasa **real** |
| Udibono 30a | `SF60639` | Udibonos 30 años, tasa **real** |

**Precios:** cierre **sin ajustar**, con dos verificaciones complementarias.

1. *Contra anclas capturadas a mano.* Al menos tres cierres verificables, con
   tolerancia de 2%. Es la más fuerte, pero solo existe donde hay anclas.
2. *Contra la aritmética de la propia respuesta.* El proveedor entrega el cierre
   crudo y el ajustado en la misma fila, y eso permite exigir la identidad

   ```
   ajustado_t / crudo_t  =  Π (1 − dividendo_i / cierre_i)   sobre los dividendos con ex > t
   ```

   que es exacta por construcción del ajuste. Si la columna cruda viniera ya
   ajustada, el cociente sería 1.00 en todas partes y el producto no. Se corre
   sobre los diez emisores sin depender de ninguna ancla.

El **signo** de la desviación separa dos causas que no se deben confundir. Menos
ajuste del que los dividendos obligan acusa a la columna cruda, y eso es P2. Más
ajuste del que explican los dividendos conocidos no la acusa: confirma que está
cruda y señala un reparto fuera del historial. Realty Income (escisión de Orion,
2021) y W. P. Carey (NLOP, 2023) salen exactamente así, y sus series se usan.

> **Stooq, la fuente original, dejó de servir.** Ahora responde con una página que
> exige verificación por JavaScript, así que devuelve HTTP 200 con HTML donde antes
> había CSV. Un parser ingenuo lo toma por datos. No se reintenta ni se resuelve con
> un navegador headless: se cambió de proveedor, y el detector de "esto es HTML, no
> datos" quedó como prueba.

### Sí, todo lo que se baja se guarda

Nada se recalcula al vuelo desde la red. Cada corrida de ingesta **escribe a
SQLite** (`data/reit.db`) y desde ahí lee toda la aplicación: la SEC se consulta
para traer lo que falta, no para dibujar una pantalla.

| Tabla | Qué guarda |
|---|---|
| `emisores` | Universo, CIK y sector |
| `hechos` | Partidas XBRL y del suplemento, por emisor, concepto y periodo |
| `conciliacion` | La cascada NOI → FFO → FFO normalizado → AFFO, renglón por renglón |
| `precios` | Cierres **sin ajustar**, diarios |
| `dividendos` | Fecha ex, fecha de pago y monto por acción |
| `tasas` | UST, CPI, INPC, Cetes, Mbono y Udibono |
| `guias` | Guías de la administración, con la fecha en que se emitió cada una |
| `anclas_precio` | Cierres capturados a mano para la verificación de P2 |
| `bitacora` | Qué entró a la base, cuándo y de dónde |
| `transacciones`, `decisiones`, `inmuebles` | Lo que captura el usuario |

Guardar es **append-only**: una reexpresión entra como fila nueva con su propia
`fecha_publicacion`, nunca como `UPDATE`. Por eso la base crece y por eso una
consulta con corte de hace un año sigue viendo lo que se sabía entonces, no lo que
se sabe hoy. Esa es la mitad de P1.

La excepción es **Streamlit Cloud**, donde el disco es efímero y cada reinicio del
contenedor borra la base: ahí se reconstruye sola en el primer arranque. Ver
"Despliegue en Streamlit Cloud" más abajo.

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

## Las dieciséis pruebas obligatorias

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
| 9 | La serie de precios es cruda y cada serie del SIE es el instrumento declarado | `test_9_precios_y_series_macro.py` |
| 10 | Cada columna del filing cae en su propio periodo, y la conciliación cuadra | `test_10_parser_wpc.py` |
| 11 | La aplicación no truena con la base vacía ni con celdas faltantes | `test_11_arranque_sin_datos.py` |
| 12 | Dos duraciones en un encabezado dan dos tipos de periodo, no uno | `test_12_parser_nnn.py` |
| 13 | La ficha de un emisor lo aísla de los patrones de los demás | `test_13_taxonomia_por_emisor.py` |
| 14 | El porcentaje se escala en el dato una sola vez, nunca en el formato | `test_14_formato_de_tablas.py` |
| 15 | El cap rate es del sector: cambiarlo mueve el NAV de verdad | `test_15_valuacion_por_sector.py` |
| 16 | Un acumulado no siempre es una suma: el promedio se lleva a total | `test_16_derivacion_de_trimestres.py` |

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
- La prueba 9 entrega la serie **ajustada en la columna cruda** y exige que se
  detecte. Es el error de Macrotrends reproducido a propósito: sin ese control, la
  verificación de coherencia podría estar aprobando cualquier cosa. Su gemela le da
  a `verificar_series_banxico` una TIIE bajo el nombre de Udibono y exige que
  repruebe.
- La prueba 14 recorre `app/` y **falla si alguna página multiplica por cien**, que
  con la escala centralizada ya no corrige nada: duplica. Y verifica que la aguja
  case por token completo, para que `tir` no se coma a `retiro`.
- La prueba 15 valúa el mismo portafolio con el cap rate del sector equivocado y
  exige que la diferencia supere el 20%. Si fuera pequeña, el cap rate por sector
  sería adorno.
- La prueba 16 verifica que la resta ingenua **sí** habría dado negativo, y
  reproduce con la fórmula corregida un trimestre que el emisor sí publicó. Sin lo
  primero no demuestra que el arreglo hacía falta; sin lo segundo, solo demuestra
  que el signo quedó bien.

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
| 2 — Valuación individual | Completo. Cascada, métricas, tres puertas, cap rate y prima de riesgo **por sector**, crecimiento implícito, diagnóstico de insumos faltantes, Excel con fórmulas vivas, pruebas 5–6 y 15. |
| 3 — Interfaz de valuación | Completo. Siete páginas de Streamlit, verificadas de punta a punta. |
| 4 — Portafolio | Completo. Transacciones, TWR/TIR/atribución, capa fiscal, benchmarks. |
| 5 — Comparativo inmobiliario | Completo. Motor CDMX, riesgos cuantificados, solver inverso de plusvalía. |
| 6 — Simulación e innovaciones | Completo. Monte Carlo, replay, reloj de prima, tracker de dividendo real, detector de sesgos, modo «¿qué hubiera pasado?». |

### La taxonomía es por emisor, no compartida

La primera versión resolvía las etiquetas con **un solo juego de expresiones
regulares** para los diez emisores. Funciona hasta que dos usan palabras parecidas
para cosas distintas, y entonces cada arreglo es un riesgo para los demás:

- `Non-real estate depreciation` contiene `real estate depreciation` como subcadena.
- `FFO adjustments allocable to noncontrolling interests` empieza con `FFO`.
- `Amortization of lease intangibles` es un ajuste no-efectivo en un emisor y una
  comisión efectivamente pagada en otro.

Cada vez, ampliar un patrón podía romper a otro emisor **sin que nada lo avisara**:
su conciliación seguía cuadrando, con las cifras en la línea equivocada.

Ahora cada emisor tiene una **ficha** en `src/ingesta/taxonomia.py` que declara, en
su propio vocabulario, qué es cada línea y qué subtotales publica. La ficha manda;
los patrones compartidos quedan como red para lo que la ficha aún no declara, y eso
se reporta como hueco en las advertencias del registro.

Las etiquetas se comparan en **forma canónica**, no literal, porque el mismo emisor
cambia la redacción entre trimestres. La canonización quita lo que nunca distingue
una línea de otra —notas al pie, paréntesis aclaratorios, tipo de guion— y deja lo
que sí:

```
Tax expense - deferred and other            ┐
Tax expense (benefit) - deferred and other  ├─→  una sola entrada en la ficha
Tax (benefit) expense - deferred and other  ┘
```

**Agregar un emisor es llenar una ficha**, no tocar expresiones regulares:

```bash
python scripts/ficha.py --ticker EXR    # borrador leyendo su filing real
```

El script recorre sus tablas de conciliación, junta todas las etiquetas y marca las
que nadie resuelve. Con eso, Extra Space pasó de 2 periodos válidos a 5 sin tocar un
solo patrón compartido: su ganancia por venta se llama `gain on real estate assets
held for sale and sold`, que no contiene `gain on sale`, y esa línea faltante era
todo el descuadre.

La prueba 13 verifica el aislamiento de verdad: **corrompe a propósito todos los
patrones compartidos** y exige que un emisor con ficha siga cuadrando igual. Con su
contraprueba: sin ficha, el mismo sabotaje sí lo rompe.

### La valuación no es la misma para todas las REITs

Un REIT no es una empresa: es un portafolio de inmuebles con una estructura de
capital encima. Lo que se valúa es la **renta**, y el mercado privado no paga lo
mismo por rentas distintas. La tasa a la que capitaliza una renta —el cap rate—
depende de qué tan estable y duradera sea:

| Sector | Cap rate base | Por qué |
|---|---:|---|
| Torres | 5.00% | Contratos a 10+ años con escaladores, casi sin CapEx. |
| Self Storage | 5.50% | Se renta mes a mes, pero casi no consume CapEx y sube precios. |
| Industrial | 5.50% | Naves con demanda estructural y mantenimiento barato. |
| Net Lease | 6.75% | Contrato a 20 años, el inquilino paga todo. Se parece a un bono. |
| Salud | 6.75% | Operador de por medio; el riesgo es de quien opera, no del ladrillo. |
| Oficinas | 8.75% | Se renegocia cada 5 años y devora mejoras al inquilino. |
| Hoteles | 9.00% | El contrato dura una noche. |

Aplicarle a todos el mismo cap rate es el error más caro y el más invisible del
modelo: valuar un self storage al 6.75% de net lease le borra **más de una quinta
parte del valor sin que ningún número se vea raro**, porque la aritmética sigue
cuadrando. Solo el supuesto está mal. Por eso el cap rate vive en
`CAP_RATE_POR_SECTOR` (`src/config.py`), la perilla del NAV arranca en el rango del
sector del emisor, y la prueba 15 exige que la diferencia exista y sea material.

El mismo principio gobierna la tasa de descuento: `libre de riesgo + prima del
sector`, no una prima única de mercado (`PRIMA_RIESGO_POR_SECTOR`).

**Estos rangos envejecen.** Se mueven con las tasas y hay que revisarlos contra
transacciones comparables. Son supuestos discutibles puestos donde se ven, no
constantes.

### Cuando no se puede calcular el NAV, el modelo lo dice

El NAV exige NOI. El NOI es una medida **no-GAAP** —igual que el AFFO— y **no está
en XBRL**: vive en el suplemento, tabla por tabla, emisor por emisor. Hoy la base
no lo tiene para ningún emisor del universo, así que `nav_por_accion`,
`cap_rate_implicito` y `premio_descuento_nav` salen vacíos para todos.

Un `None` en pantalla no distingue *"no vale nada"* de *"me falta un dato para
opinar"*, y esas dos cosas no se parecen. Por eso hay dos piezas:

1. **`diagnosticar()`** — por emisor, qué método se puede correr y **qué insumo
   exacto le falta al que no**, con el nombre que ese insumo tiene en la base.
2. **Valuación por crecimiento implícito** — la que sí corre hoy, porque usa solo
   lo verificado: precio, AFFO por acción TTM, tasa libre de riesgo y sector.

La segunda le da vuelta a la pregunta, y eso es lo que la vuelve útil en una mesa.
En vez de *"¿cuánto vale?"* responde ***"¿qué crecimiento está descontando este
precio?"***. De Gordon, `P = AFFO₀(1+g)/(r − g)`, despejando:

```
g = (P·r − AFFO₀) / (P + AFFO₀)
```

Es aritmética, no un pronóstico: dice qué está suponiendo el mercado. La lectura
útil es contrastar ese `g` contra el que el emisor **ha entregado de verdad**, sin
tener que defender un valor intrínseco. La prueba 15 fija el contrato del despeje:
valuar con el `g` implícito tiene que devolver exactamente el precio.

`valor_gordon` devuelve `None` cuando `r − g < 0.5%`: ahí el múltiplo pasa de 100x
y el resultado es una división por casi cero, no una valuación.

### Limitaciones conocidas

**Cobertura del parser: medida, no estimada.** Corriendo contra los 8-K de la SEC
desde junio de 2025 (`python scripts/cobertura.py --desde 2025-06-01 --max-filings 4`):

| Emisor | Ficha | Periodos | Válidos | Sospechosos |
|---|:--:|---:|---:|---:|
| O | ✅ | 30 | 30 | 0 |
| NNN | ✅ | 14 | 14 | 0 |
| WPC | ✅ | 11 | 11 | 0 |
| ADC | ✅ | 10 | 10 | 0 |
| EPRT | ✅ | 6 | 6 | 0 |
| GNL | ✅ | 5 | 5 | 0 |
| EXR | ✅ | 21 | 7 | 14 |
| WELL | — | 10 | 0 | 10 |
| PSA | — | 4 | 0 | 4 |
| PLD | — | 0 | 0 | 0 |

**Seis de los diez emisores llegan completos a la pantalla.** Faltan PSA, EXR,
WELL y PLD, y cada uno por su propia razón: a los tres primeros les descuadra un
tramo de su conciliación —les falta ficha— y de PLD el parser no extrae ni una
tabla.

Cada emisor reporta su conciliación de AFFO con etiquetas ligeramente distintas y
con su propia estructura de tramos. Ampliar la cobertura es trabajo de taxonomía
emisor por emisor.

W. P. Carey pasó de cero a los once periodos, y las cuatro causas resultaron
distintas. Solo una era suya; las otras tres afectaban a todos los emisores y
estaban tapadas porque el descuadre aparecía siempre en el AFFO, lejos de su
origen. La peor no era un descuadre:

1. **Corrimiento de columnas.** El encabezado de W. P. Carey trae tres trimestres
   y dos son del mismo año. La detección de periodos deduplicaba por AÑO —para
   resolver el idioma "June 30, 2026 and 2025"— y colapsaba dos columnas en una,
   asignándole al primer trimestre las cifras del segundo. **Ninguna suma lo
   delata**: los números son internamente consistentes, solo están en el periodo
   equivocado. Se ve comparando el encabezado con lo extraído, y por eso ahora hay
   una prueba que lo hace.
2. **La acumulación se rompía tras el primer tramo.** Al entrar a un tramo
   posterior, la clave recibe un sufijo de segmento; la pregunta "¿es acumulable?"
   se hacía con la clave ya sufijada, que nunca está en el conjunto. De la segunda
   fila en adelante, todo concepto repetido se descartaba en silencio.
3. **El subtotal de FFO no se reconocía** cuando la sigla trae un paréntesis
   intermedio ("FFO (as defined by NAREIT) Attributable to..."). Sin ese subtotal
   no hay frontera de tramo, así que toda la conciliación quedaba en uno solo.
4. **Etiquetas no mapeadas**, entre ellas una que el mismo emisor escribe de tres
   formas distintas en tres trimestres consecutivos: "Tax expense –",
   "Tax expense (benefit) –" y "Tax (benefit) expense –". Eso no se descubre
   leyendo un solo filing.

NNN pasó de dos a diez, y el defecto de fondo era otra vez de periodos, no de
aritmética. Publica **cuatro columnas bajo un solo encabezado con dos duraciones
distintas**:

```
Quarter Ended June 30,        Six Months Ended June 30,
     2026   |   2025               2026   |   2025
```

El parser detectaba una sola duración por encabezado. Y como `Quarter Ended` ni
siquiera figuraba entre los patrones, la que ganaba era la del semestre: los dos
trimestres entraban a la base como semestres. El síntoma eran etiquetas
imposibles —un "semestre" que cierra el 31 de marzo— que ninguna validación
aritmética podía cazar, porque cada columna es internamente consistente.

Con eso venían tres cosas más:

- **El paréntesis del negativo, tercera variante.** NNN maqueta `"(9,105"` y
  `")"` en celdas contiguas: el de apertura pegado al número y solo el de cierre
  suelto. El parser manejaba el paréntesis completo y el de apertura suelto, pero
  no este. Una ganancia por venta leída en positivo desplaza el subtotal por el
  doble de la partida.
- **El día y el mes separados de los años**, en filas distintas de la tabla.
  Ninguna fecha quedaba completa y la tabla se descartaba entera, en silencio.
- **`Net earnings`** no era utilidad neta: el FFO descuadraba por su monto exacto.

Lo importante es que el sistema **se comporta bien cuando no puede**: lo que no
cuadra se guarda marcado `sospechoso`, no entra a ningún cálculo, y la interfaz lo
dice. Prefiere no tener el dato a tenerlo mal.
**Reparar un dato derivado necesita un paso explícito.** La base es append-only y
la llave única de `hechos` no incluye el estado, así que volver a correr la
ingesta **no** reemplaza una fila mala: la descarta por duplicada, en silencio.
Eso es correcto para los datos de fuente y equivocado para los derivados. De ahí
`scripts/reparar.py`, que solo borra filas derivadas o marcadas `sospechoso`,
deja constancia en la bitácora, y exige `--aplicar`:

```bash
python scripts/reparar.py                                   # dice qué haría
python scripts/reparar.py --aplicar                         # conteos de acciones imposibles
python scripts/reparar.py --olvidar-sospechosos --tickers EPRT,GNL --aplicar
python scripts/ingesta.py                                   # y vuelve a leerlos
```

Sin el segundo comando, corregir una ficha no cambia nada: los periodos ya
guardados como `sospechoso` se quedan así para siempre.

**El NAV no se puede calcular para ningún emisor todavía.** Falta el NOI, que es
no-GAAP y no está en XBRL. Extraerlo es trabajo de taxonomía por emisor, igual que
el AFFO: el suplemento lo publica en su propia tabla, con sus propias etiquetas.
Mientras tanto la valuación corre por múltiplos y por crecimiento implícito, y la
página lo dice con nombre y apellido en vez de dejar celdas vacías.

**El AFFO por acción TTM exige cuatro trimestres válidos consecutivos**, y son
cuatro trimestres de CALENDARIO, no cuatro renglones del panel. Un `rolling(4)`
sobre las filas devuelve, cuando falta un trimestre, un "TTM" que abarca cinco:
la suma cuadra, el número se ve razonable y nada lo delata. `_ttm` valida la
ventana contra las fechas y prefiere no emitir el dato.

Si a la serie por acción le falta un trimestre pero el monto sí está completo, el
TTM por acción se deduce del monto entre el conteo de acciones. Sin ese respaldo,
un hueco de un solo trimestre borraba al emisor **entero** de la pantalla: le
pasaba a Agree Realty, que salía en blanco teniendo siete trimestres de AFFO en
la base.

**La cobertura de precios sí es completa.** Los diez emisores traen cinco años de
cierres sin ajustar y su historial de dividendos, y los diez pasan la verificación
de coherencia del ajuste (ocho con error 0.00%; O y W. P. Carey con la reserva por
escisión descrita arriba). Es un eje independiente del de fundamentales: se puede
tener precio verificado y AFFO sospechoso, y en ocho de los diez es justo el caso.

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

La prueba de humo (`scripts/humo_app.py`) dibuja las siete páginas con la base
llena y con la base vacía, y reprueba por **tres** cosas, no solo por excepciones:
una página que truena, una tabla que no serializa a Arrow —que Streamlit se traga
y convierte por su cuenta— y una columna porcentual que llega a la pantalla en
fracciones. Las tres son fallas que la aplicación no reporta sola.

`.github/workflows/ingest.yml` corre durante las ventanas de reportes (primeras
tres semanas de febrero, mayo, agosto y noviembre), detecta 8-K nuevos, parsea,
valida y escribe. La base viaja como artefacto entre corridas, no como commit: los
datos de mercado no pertenecen al historial de git.

Secretos que hay que configurar: `SEC_USER_AGENT` (obligatorio) y `BANXICO_TOKEN`
(opcional, gratuito, se obtiene en el portal del SIE).

---

## Despliegue en Streamlit Cloud

Archivo principal: **`app/Inicio.py`**. Python **3.11**, que es la versión con la
que corre CI.

En **Settings → Secrets**:

```toml
SEC_USER_AGENT = "Modelo-REITS tu-correo@ejemplo.com"
BANXICO_TOKEN  = "tu-token-del-SIE"
```

Sin `BANXICO_TOKEN` la aplicación levanta igual, pero la portada —la comparación
contra el Udibono, que es P10— se queda sin su serie de referencia.

**La primera carga ingesta sola.** En una computadora personal la base se crea con
`python scripts/ingesta.py`; en Streamlit Cloud no hay terminal, y el sistema de
archivos es efímero, así que cada reinicio del contenedor la borra. Por eso
`exigir_base()` construye la base desde fuente primaria en el primer arranque, con
barra de progreso. Tarda alrededor de dos minutos y ocurre una vez por arranque del
servidor, no por visita: la ingesta está detrás de `st.cache_resource`, así que dos
personas que abran la aplicación recién desplegada al mismo tiempo comparten la
misma corrida en vez de lanzar dos descargas contra la SEC.

Si la ingesta falla, la pantalla dice qué falló. Si termina con advertencias, las
muestra desglosadas: lo que no se pudo verificar queda marcado y no entra a ningún
cálculo.

---

## Advertencias que la aplicación muestra siempre

- Es una herramienta de análisis, no asesoría de inversión.
- Toda métrica de desempeño va con su conteo de apuestas efectivas.
- La latencia y la fuente de cada dato de mercado están etiquetadas.
- Cuando las observaciones son insuficientes, el veredicto es **INCONCLUSO**, con
  esa palabra, nunca GO.
- Los datos de fuente primaria (SEC, bancos centrales) se distinguen de los
  derivados y reconstruidos en cada pantalla y en la hoja de Fuentes del Excel.
