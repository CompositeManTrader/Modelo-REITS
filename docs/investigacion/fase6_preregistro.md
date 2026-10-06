# Fase 6: pre-registro de «en cuáles REITs»

Fijado el 6 de octubre de 2026, con los datos de la SEC ya bajados y validados (sección
«Los datos») y **antes de calcular un solo retorno de una cartera**. Lo único que se miró de
los datos fue su calidad: precios contra Yahoo, FFO contra el publicado, cobertura de XBRL y
cuántos REITs hay cada trimestre. El código que lo ejecuta es `src/investigacion/fase6.py`, en
el mismo commit; la prueba 72 congela los números de este documento.

## La pregunta

El inversionista aporta 1,000 dólares cada mes a REITs de EE. UU. por el SIC. Las fases 5, 7 y
8 dijeron que no hay una regla que diga cuándo entrar: aportar siempre. Queda la segunda
pregunta del plan: **¿hay una manera de escoger a cuáles REITs va el dinero que le gane a
repartirlo entre todos?** Y como pregunta de defensa: **¿se pueden ver venir los recortes de
dividendo?**

## Lo que se espera, escrito antes

| # | Hipótesis | Qué se espera | Por qué |
|---|---|---|---|
| H0 | Nula | Ninguna regla le gana a aportar a todos por partes iguales por +50 pb al año después de impuestos, de forma robusta | Es lo más probable: la literatura de REITs encuentra pocas primas que sobrevivan costos y fuera de muestra ([70], [14]) |
| H1 | Momentum (S1) | Exceso positivo pequeño, inestable entre periodos | [51], [56] a favor; [70] y [14] en contra después de 2016 |
| H2 | Valor por flujo y por activos (S5, S6) | Sin exceso por sí solo; positivo **solo con filtro de calidad** | [68]: el valor funciona controlando por calidad |
| H3 | Yield de dividendo alto (S7) | **Control negativo**: sin exceso y con más recortes que el universo | El estudio del universo: el tercio barato por yield concentró los recortes (23% contra 5%) |
| H4 | Apalancamiento bajo y distancia al default (S2, S3) | Menos desplomes y recortes; exceso pequeño | [64], [66], [67] |
| H5 | Calidad (S8) | Menos recortes y menos caída; exceso cercano a cero | Es un filtro defensivo |
| H6 | **La prueba clave**: barato entre los de calidad contra todos los de calidad | Si algo funciona, es esto; pero es una inferencia de combinar estudios, no algo probado | [68] |
| H7 | Barato contra su propia historia entre los de calidad (S12) | Leve o nulo | Solo el resultado propio con O, NNN y WPC (+68 pb, INCONCLUSO) |
| H8 | Detector de recortes (D1) | AUC fuera de muestra entre 0.65 y 0.75; sacar al quintil de más riesgo baja los recortes pero apenas mueve la TIR | [75], [76]: los determinantes sí se conocen; la predicción fuera de muestra no se ha publicado |
| H9 | Vender después de un recorte (D3) | No ayuda: el exceso de los 12 meses siguientes no es negativo | [75], [78] |

## Los datos

Construidos con `python scripts/investigacion.py emisores` (pide `SEC_USER_AGENT`, que no se
escribe en ningún archivo). Detalle y validación en `data/investigacion/emisores/manifiesto.json`.

* **Universo**: los emisores con código SIC 6798 y los que en algún 10-K de 2009 a 2026 dicen
  que califican o tributan como REIT (búsqueda de texto completo de la SEC). Un emisor cuenta
  como REIT en un trimestre si un 10-K de los 24 meses anteriores lo dice (así entran las
  conversiones desde que se convirtieron).
* **De capital o hipotecario**: para los que cotizan hoy, la etiqueta del estudio del universo
  (stockanalysis); para los desaparecidos, una regla de XBRL (préstamos y valores contra
  activos, reportos, intereses contra ingresos) y una revisión a mano de los dudosos, con su
  motivo, en `data/investigacion/emisores/clasificacion_manual.csv`. La regla sola acierta 182
  de 191 contra stockanalysis; falla con hipotecarios comerciales que consolidan sus
  bursatilizaciones.
* **Tamaño**: 621 candidatos, 389 con precio en los 13F. De los 444 con estados en XBRL, 303
  son REITs de capital; 42 hipotecarios y 99 que no son REIT quedan fuera. Abiertos: 266
  emisores con precio; sellados: 202 de los 621 candidatos.
* **Precios**: formularios 13F. De 2013 en adelante, los conjuntos estructurados de la SEC
  (miles de administradores); de 2009 a marzo de 2013, los 13F en texto de 32 administradores
  grandes. El precio es la mediana de valor entre acciones; el CUSIP sale de los 13G y se
  verifica con el nombre del emisor. Reglas de limpieza: dispersión entre administradores de a
  lo más 10%, corrección de quien reportó en miles cuando eran dólares (enero de 2023), splits
  detectados por las acciones de los 13F o por cambio de CUSIP, picos que regresan y retornos
  de más de +200% sin split se descartan.
* **Validación de precios** (emisores que cotizan hoy y no están sellados): correlación de los
  retornos trimestrales contra Yahoo de 0.89 (0.996 en la era de texto), 97% de los trimestres a
  menos de 2 puntos, diferencia anual mediana de 0.1 puntos y promedio de −0.46 puntos (las
  escisiones no se ven en los 13F).
* **Estados financieros**: XBRL de la SEC, la primera versión publicada de cada periodo, a la
  fecha en que se publicó. El FFO se arma con la definición de Nareit (utilidad de los comunes
  + depreciación − ganancia por venta + deterioros) y queda a ±3% del publicado por O, NNN y WPC.
* **Dividendo** de cada trimestre: el por acción de XBRL; si falta, la cuarta parte del de 12
  meses; si es negativo o mayor que 10% del precio, la mediana de los vecinos.
* **Salida**: el trimestre después del último precio. Retorno 0% si lo compraron o se fue de
  bolsa; −30% si presentó un 8-K de quiebra en el último año (Shumway 1997). Sensibilidad con
  −100%.

**Límites conocidos, declarados antes de correr.** Antes de 2011 casi no hay XBRL (la SEC lo
exigió por etapas), así que las carteras empiezan cuando hay al menos 30 elegibles con FFO:
marzo de 2011 entre los emisores abiertos (contados antes de calcular cualquier retorno).
Entre 2012 y 2015 falta el FFO o el dividendo de XBRL a 10-20% de los elegibles (REITs que reportan junto con su sociedad operadora y etiquetan con dimensiones);
desde 2016, a 2-7%. Las escisiones restan su valor al trimestre en que ocurren. Los 13F no
traen REITs con menos de tres tenedores grandes.

## Las muestras

| Muestra | Qué | Emisores |
|---|---|---|
| **Desarrollo** | Carteras desde la primera fecha con 30 elegibles con FFO; datos recortados a diciembre de 2015 antes de calcular | Los no sellados |
| **Validación** | Carteras formadas de diciembre de 2015 en adelante; retornos de 2016 a 2026 | Los no sellados |
| **Prueba final** | Desde el primer trimestre con 30 elegibles con FFO (hacia 2012) hasta 2026, una sola vez, con el modelo congelado | Los **sellados**: un tercio, por la función de dispersión de la fase 0 sobre el ticker (o el CIK de los que ya no cotizan). Su panel se guardó con huella digital y no se ha abierto |

## Quién es elegible cada trimestre

REIT de capital y REIT ese año, capitalización de al menos **250 millones de dólares**, precio
de al menos **5 dólares**, y al menos **10 tenedores** en la era de texto o **20** en la
estructurada (los REITs no listados aparecen en los 13F con menos de diez). Un trimestre con
menos de **30** elegibles no forma carteras. No se piden estados financieros: quien no los tiene
sigue en el universo contra el que se compara, pero ninguna señal lo puede escoger.

## Las señales (todas con lo conocido al cierre del trimestre)

| Señal | Cálculo | Mejor | Hipótesis |
|---|---|---|---|
| Momentum | Retorno de los meses 12 a 3 (tres trimestres, saltando el último: con precios trimestrales no hay 12-1) | Alto | S1 |
| Apalancamiento | Pasivos / (pasivos + capitalización) | Bajo | S2 |
| Distancia al default | Ingenua de Bharath y Shumway (2008): capitalización, pasivos, volatilidad de 12 trimestres y retorno de 12 meses | Alta | S3 |
| Volatilidad | Desviación de los retornos trimestrales de 12 trimestres (mínimo 8) | Baja | S4 |
| Rendimiento de la empresa | (FFO + intereses) / (capitalización + pasivos): el sustituto del cap rate | Alto | S5 |
| Rendimiento FFO | FFO de 12 meses / capitalización | Alto | S6 |
| Rendimiento del dividendo | Dividendo de 12 meses / precio | Alto | S7, control negativo |
| Crecimiento de activos | Activos contra un año antes | Bajo | S10 |
| Rentabilidad | FFO / activos | Alta | S10 |
| Tamaño | Logaritmo de la capitalización | Grande | S11, nula |
| Yield contra su historia | Z del yield contra sus 20 trimestres anteriores (mínimo 12) | Alto | S12 |
| Crecimiento del dividendo | Anual de tres años | Alto | S13 |
| Payout | Dividendos / FFO (sin FFO positivo, el peor) | Bajo | S8 |

**Descartadas antes de correr** (no son intentos): la reversión de corto plazo (S9), por
rotación y costos del SIC y porque con precios trimestrales no hay retorno de un mes; los
cortes por sector, porque los REITs desaparecidos no tienen sector en la SEC (las señales se
comparan entre todos los REITs de capital; es una limitación).

**Cada señal** forma el **mejor tercio** de los elegibles con la señal. **Tres reglas
compuestas**:

* **Calidad (S8)**: FFO positivo, payout de a lo más **90%**, apalancamiento de a lo más la
  mediana del trimestre, sin recorte en los 12 meses anteriores, y fuera del **peor quintil**
  de distancia al default y de momentum.
* **Calidad y barato** (la prueba clave, H6): el tercio de mayor rendimiento FFO entre los de
  calidad.
* **Calidad y barato contra su historia** (H7): el tercio de mayor yield contra su historia
  entre los de calidad.

Son **16 reglas**. El detector de recortes es la 17.ª (abajo).

## Qué se mide (por regla)

* **La métrica principal**: TIR después de impuestos aportando 3,000 dólares por trimestre
  (los 1,000 al mes de la fase 0) a los escogidos por partes iguales, **sin vender nunca**:
  20% al dividendo, 10% a la ganancia al salir un emisor o al final, 0.25% de comisión. Contra
  lo mismo aportado a **todos los elegibles**. La mejora es la diferencia de TIR.
* La misma mejora con **un trimestre de retraso** y con **el doble de comisión**.
* La variante que **rota cada año** (vende a los que ya no están escogidos), como secundaria.
* Antes de impuestos: el exceso anual de la cartera (cohortes de 4 trimestres encimadas,
  comprar y mantener) contra el universo, su t de Newey-West con rezago 4, y por mitades.
* Para las señales, la **correlación de rangos** con el retorno de los 12 meses siguientes.
* **Trampas**: qué fracción de los escogidos recortó el dividendo (cayó más de 10% el de 12
  meses) o quebró en el año siguiente, y qué fracción perdió 30% o más, contra el universo.
* **Apuestas efectivas** (P7 para muchos emisores): por cada año que no se encima, los
  escogidos entre 1 + (n − 1)·ρ, con ρ la correlación promedio de sus excesos.

## Cuáles pasan a validación

Una regla pasa si en desarrollo cumple **todo**:

1. Su TIR le gana a aportar a todos.
2. Sigue ganando con un trimestre de retraso y con el doble de comisión.
3. Su exceso antes de impuestos es positivo en las dos mitades (2011-2013 y 2014-2015).
4. Si es una señal, su correlación de rangos promedio es positiva.

Pasan **a lo más tres**, las de mayor mejora. Sobre las 16 se calculan la **PBO** (8 bloques,
porque el desarrollo tiene 19 trimestres) y el **Sharpe deflactado** de la mejor con el
número de intentos de la bitácora.

## El detector de recortes (D1) y vender después (D3)

* **D1**: un logit (L2, C = 1) de la probabilidad de recorte o quiebra en 12 meses con payout,
  apalancamiento, distancia al default, momentum, yield contra la mediana del trimestre,
  tamaño, volatilidad, recorte previo y crecimiento del FFO; recortadas al 1% y 99% y
  estandarizadas con el pasado. En cada trimestre se estima solo con pares cuyo resultado ya
  se conocía (formados cuatro trimestres antes o más), con al menos **8** trimestres de ellos.
  Con eso el desarrollo apenas deja dos trimestres de pronósticos, así que el detector **no
  pasa por el filtro de desarrollo** (declarado ahora) y va directo a validación como regla 17:
  **sin riesgo de recorte** = los elegibles fuera del **quintil** de mayor probabilidad.
  Se califica con el AUC y la habilidad de Brier contra la frecuencia histórica; para servir
  necesita **AUC de al menos 0.70** en validación y en los sellados.
* **D3**: el retorno de los 12 meses siguientes de quien acaba de recortar, menos el del
  universo, en desarrollo y validación. Es descriptivo: dice si vender después de un recorte
  ayuda.

## Validación y prueba final

La validación se abre **una vez**, con motivo, para las candidatas y el detector, con los
emisores no sellados de 2016 en adelante. Una regla la pasa si gana **al menos +50 pb al año**
de TIR (el criterio 1 de la fase 0), sigue ganando con retraso y doble costo, y su exceso antes
de impuestos es positivo.

El detector, además, necesita su AUC de al menos 0.70 en validación. Solo si alguna regla pasa,
la de **mayor mejora en validación** (una sola: los sellados se abren una vez) se **congela** en
la bitácora y se abren los **sellados**. Es
**APROBADO** si en los sellados gana al menos +50 pb, sigue ganando con retraso y doble costo,
su exceso es positivo hasta 2015 y en 2016-2026, el Sharpe deflactado es de al menos 0.95, la
PBO de a lo más 0.20 y las apuestas efectivas al menos 100. Si gana pero falla otra cosa,
**INCONCLUSO**; si no gana, **RECHAZADO**. Si ninguna pasa la validación, la fase termina en
RECHAZADO para la selección con estas señales y los sellados no se abren.
