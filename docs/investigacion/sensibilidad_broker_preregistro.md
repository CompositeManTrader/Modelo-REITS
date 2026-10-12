# Sensibilidad fiscal: comprar con un broker de EE. UU. Pre-registro

Escrito el 12 de octubre de 2026, antes de correr nada con el perfil nuevo. Va en el mismo
commit que el código que lo corre (`src/investigacion/sensibilidad.py`), así que el commit
de este documento es anterior a cualquier resultado.

## Por qué

Toda la investigación (fases 3 a 8) y los estudios de O, NNN y WPC suponen que el
inversionista compra por el **SIC** con una casa de bolsa mexicana. El inversionista avisó
que va a comprar **directo con un broker de EE. UU.**, y con eso cambian los impuestos.
Esta sensibilidad repite **las mismas reglas y los mismos modelos congelados** con los
impuestos del broker, lado a lado con los del SIC.

**No es una búsqueda nueva.** No se escoge ninguna regla, no se cambia ningún parámetro y
no se agrega ninguna señal. `diseno.OBJETIVO` (el SIC) sigue siendo la línea base
pre-registrada, y la prueba 60 lo protege.

## Los perfiles

Tasa marginal del inversionista desconocida: se corren las dos, 30% y 35%.

| Concepto | SIC (línea base) | Broker, marginal 30% | Broker, marginal 35% |
|---|---|---|---|
| Dividendo | 20% | 39% | 44% |
| Intereses del efectivo | 20% | 30% | 35% |
| Ganancia al vender | 10% | 10% | 10% |
| Comisión por compra y por venta | 0.25% | 0% | 0% |

* **Dividendo.** El dividendo de una sociedad extranjera se acumula a la tarifa anual, con
  crédito por la retención de EE. UU. Esa retención es de 10% para una persona física
  residente en México que presenta el W-8BEN y tiene menos de 10% del REIT; así lo indica la
  tabla de Nareit de retenciones a dividendos de REIT por país (reit.com, 2024). Además se
  paga el ISR adicional de 10% sobre lo distribuido (Art. 142 fr. V LISR), neto de la
  retención. La tasa queda en marginal + 10% × 0.90, es decir, marginal + 9 puntos.
* **Intereses.** El efectivo en T-bills o en un fondo de mercado de dinero da intereses que
  se acumulan a la tasa marginal. EE. UU. no retiene a no residentes por los T-bills.
* **Ganancia.** 10% cedular (Art. 129 LISR). Según el Criterio 37/ISR/N del SAT, ese 10%
  aplica a las acciones listadas en el SIC aunque se vendan por medio de un intermediario
  extranjero. O, NNN, WPC y los REITs grandes están listados en el SIC.
* **Comisión.** 0%, como cobra un broker sin comisión.

Fuera del modelo, y declarado: el impuesto sucesorio de EE. UU. para no residentes que
tienen más de 60 mil dólares en activos de EE. UU. (`config.UMBRAL_ESTATE_TAX_USD`).
Tampoco se modelan la ganancia cambiaria, el ajuste por inflación del costo ni la tarifa
progresiva: se usa una sola tasa marginal. Todo esto debe confirmarse con un contador.

## Qué se repite

Con los tres perfiles (SIC, broker 30% y broker 35%) y **sin volver a escoger**:

| Fase | Qué se repite |
|---|---|
| 3 | El techo de los oráculos en desarrollo (1972-2015) |
| 5 | Las 22 reglas de entrada en desarrollo, con sus dos eras, y el filtro pre-registrado |
| 7 | Los cinco peldaños de la escalera en desarrollo (los modelos se estiman una sola vez; los impuestos no los cambian) |
| 8 | La protección por tendencia en la validación de EE. UU. (2016 en adelante) y en los ocho mercados sellados |
| 6 | Las 16 reglas de selección en desarrollo; las dos candidatas y el detector en validación; momentum en los emisores sellados |
| Estudios | El semáforo de O, NNN y WPC (backtest de reglas); la asignación entre los tres con cada método de valuación; el retorno largo de cada papel con el dividendo neto |

Lo que no depende de los impuestos se calcula una vez y se reutiliza: las señales, los
modelos de la fase 7, la predictibilidad (R² y Clark-West), el PBO y el Sharpe deflactado
(los dos usan retornos antes de impuestos) y el AUC del detector.

## Los sellados

Los ocho mercados de la fase 8 y los emisores sellados de la fase 6 se abren **una vez en
esta corrida**, y con esos mismos datos se evalúan los tres perfiles. Antes de abrirlos se
congela en la bitácora un modelo con el prefijo `sensibilidad-fiscal`, que repite la regla
ya congelada sin cambiarla:

* `sensibilidad-fiscal: proteccion-tendencia-10m`
* `sensibilidad-fiscal: seleccion-fase6: momentum`

Es otra mirada a la misma regla congelada, que solo cambia la contabilidad de impuestos.
Cada apertura queda en la bitácora y se reporta. Los ocho mercados ya se habían abierto tres
veces con el modelo de la fase 8, y los emisores sellados una vez con el de la fase 6.

La corrida con el perfil SIC sobre los emisores sellados usa el código corregido de la fase
6 (`fase6_resultados.md`, «Correcciones»); la prueba final original corrió con la primera
versión. Si la mejora con el SIC no da los +38 pb guardados, se reporta la diferencia.

## Bitácora

Una fila por fase, regla, muestra y perfil, con la familia `sensibilidad-fiscal` y el
perfil y sus tasas en los parámetros. Esa familia no cuenta en los intentos de las familias
originales ni en el Sharpe deflactado ya calculado: no es una búsqueda, es la misma regla
medida con otros impuestos. El total de configuraciones que se muestra al lector la deja
fuera y la reporta aparte.

## Cómo se lee el resultado

* **Mismo veredicto con los tres perfiles:** la conclusión no depende de comprar por el SIC
  o con un broker.
* **Mejor solo con el broker** (una regla que pasa un filtro o un umbral solo con el perfil
  nuevo): se marca como **posterior**. A lo más llega a INCONCLUSO y no se adopta, porque el
  perfil se decidió después de ver todos los resultados con el SIC.
* **Peor con el broker:** se reporta tal cual; es lo que el inversionista enfrenta.

## Lo que esperamos (escrito antes de correr)

* **H-B1: aportar siempre pierde entre 120 y 180 pb al año** de TIR en 1972-2015 contra
  el SIC. El dividendo es casi todo el retorno de un REIT (un yield de 6% a 8% en esos
  años) y paga de 19 a 24 puntos más de impuesto; la comisión de 0% compensa poco.
* **H-B2: el timing sale un poco mejor contra aportar siempre, pero no cambia el veredicto.**
  Quien está fuera deja de cobrar un dividendo que paga 39% o 44% y cobra intereses que
  pagan 30% o 35%. Ninguna regla de la fase 5 pasa el filtro con el broker, y la fase 7
  sigue sin candidato.
* **H-B3: la protección por tendencia sigue RECHAZADA** en los ocho mercados, aunque cuesta
  menos que con el SIC.
* **H-B4: momentum mejora en los emisores sellados**, porque escoge REITs que suben más de
  precio y pagan menos dividendo. Si cruza los +50 pb, queda como INCONCLUSO posterior: su
  Sharpe deflactado de 0.39 no cambia con los impuestos y está lejos de 0.95.
* **H-B5: el yield alto y «calidad y barato» salen peor** que con el SIC, porque escogen a
  los que más dividendo pagan.
* **H-B6: la ventaja del consenso en la asignación entre O, NNN y WPC (+68 pb con el SIC)
  baja**, porque el más barato suele ser el de yield más alto.
* **H-B7: la ventaja del semáforo contra aportar siempre cambia menos de 20 pb** en cada
  emisor. La reserva cobra intereses más gravados que con el SIC, pero deja de cobrar parte
  del dividendo.
