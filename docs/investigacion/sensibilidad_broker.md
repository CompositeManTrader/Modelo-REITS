# Sensibilidad fiscal: comprar con un broker de EE. UU. Resultados

Pre-registro: `sensibilidad_broker_preregistro.md` (commit anterior a esta corrida). Las mismas reglas y los mismos modelos congelados de las fases 3 a 8 y de los estudios de O, NNN y WPC, con los impuestos de comprar directo con un broker de EE. UU. y lado a lado con los del SIC. No se escogió nada nuevo. Generado por `python scripts/investigacion.py broker`.

## Los perfiles

| Perfil | Dividendo | Intereses del efectivo | Ganancia al vender | Comisión |
|---|---|---|---|---|
| SIC (línea base) | 20% | 20% | 10% | 0.25% |
| Broker EE. UU., marginal 30% | 39% | 30% | 10% | 0.00% |
| Broker EE. UU., marginal 35% | 44% | 35% | 10% | 0.00% |

El dividendo de un REIT comprado con un broker paga la tasa marginal más 9 puntos (Art. 142 fr. V LISR, con crédito por el 10% que retiene EE. UU. con el W-8BEN); los intereses del efectivo, la marginal; la ganancia, 10% (Art. 129 LISR y Criterio 37/ISR/N del SAT para acciones listadas en el SIC, aunque se vendan con un intermediario extranjero). La tasa marginal no se conoce: se corren 30% y 35%. Fuera del modelo: el impuesto sucesorio de EE. UU. para no residentes con más de 60 mil dólares en activos de EE. UU. Todo esto debe confirmarse con un contador.

## Veredicto

**Con el broker de EE. UU. ningún veredicto cambia.** Ninguna regla pasa un filtro o un criterio que no pasara con el SIC, con marginal de 30% ni de 35%. Lo que sí cambia es el nivel: aportar siempre rinde menos, porque el dividendo paga casi el doble, y las reglas que salen del mercado cuestan menos que con el SIC, porque estar fuera evita ese dividendo y no hay comisión.

* **Fase 5 (cuándo entrar):** 0 de 22 reglas pasan el filtro con el SIC, 0 con el broker al 30% y 0 al 35%. La mejor con el broker al 35% es «condiciones financieras | fuera en el quintil peor (20%)» con +114 pb al año; falla en: no predice a 12 meses.
* **Fase 7 (la escalera de modelos):** candidato con el SIC: ninguno; con el broker: ninguno (30%) y ninguno (35%).
* **Fase 8 (protección por tendencia en los 8 mercados sellados):** SIC: RECHAZADO (-127 pb al año, 12% de los mercados protege); Broker 30%: RECHAZADO (-54 pb al año, 12% de los mercados protege); Broker 35%: RECHAZADO (-49 pb al año, 12% de los mercados protege).
* **Fase 6 (en cuáles REITs), momentum en los emisores sellados:** SIC: +38 pb (RECHAZADO); Broker 30%: +41 pb (RECHAZADO); Broker 35%: +42 pb (RECHAZADO). El umbral es +50 pb.
* **Estudios, asignación entre O, NNN y WPC con el consenso:** SIC: +72 pb; Broker 30%: +63 pb; Broker 35%: +60 pb.

## Lo que el broker le cuesta a quien aporta siempre

TIR de aportar cada mes al índice o al emisor, sin ninguna regla, después de impuestos y comisiones.

| Muestra | SIC | Broker 30% | Broker 35% | Broker 30% contra SIC (pb) | Broker 35% contra SIC (pb) |
|---|---|---|---|---|---|
| Sector EE. UU., 1972-2015 | 10.65% | 9.20% | 8.82% | -145 | -184 |
| Sector EE. UU., 2016 en adelante | 4.39% | 3.72% | 3.52% | -67 | -87 |
| Ocho mercados sellados (promedio) | 4.67% | 3.83% | 3.60% | -84 | -107 |
| Todos los REITs de capital, 2009-2015 | 9.88% | 9.27% | 9.06% | -61 | -83 |
| REITs sellados, 2012 en adelante | 5.89% | 5.14% | 4.93% | -74 | -96 |
| NNN, aportando cada mes desde que hay datos | 8.82% | 7.53% | 7.18% | -129 | -164 |
| O, aportando cada mes desde que hay datos | 9.84% | 8.61% | 8.28% | -123 | -156 |
| WPC, aportando cada mes desde que hay datos | 9.34% | 8.02% | 7.66% | -132 | -168 |

## Las pruebas que deciden cada conclusión

Mejora en puntos base al año de TIR contra su comparación (aportar siempre, aportar a todos o partes iguales). Veredictos en el orden SIC / broker 30% / broker 35%.

| Fase | Prueba | SIC (pb) | Broker 30% (pb) | Broker 35% (pb) | Criterio | Veredicto |
|---|---|---|---|---|---|---|
| 3 | Oráculo de 12 meses, solo dinero nuevo (techo de entrar bien) | +58 | +51 | +49 | techo, no es regla | — |
| 3 | Oráculo: fuera en cada caída de 20% o más, rebalanceando | +589 | +604 | +604 | techo, no es regla | — |
| 5 | Mejor de las 22 reglas de entrada, rebalanceando | +92 | +113 | +114 | pasar el filtro | 0 de 22 pasan / 0 de 22 pasan / 0 de 22 pasan |
| 5 | Tendencia de 10 meses (signo) | +15 | +87 | +93 | pasar el filtro | — |
| 7 | Mejor peldaño de la escalera | 0 | 0 | 0 | ganarle a aportar siempre | sin candidato (RECHAZADO) / sin candidato (RECHAZADO) / sin candidato (RECHAZADO) |
| 8 | Protección por tendencia, EE. UU. 2016 en adelante | -490 | -387 | -386 | costo ≤ 25 pb | — |
| 8 | Protección por tendencia, promedio de los 8 mercados | -127 | -54 | -49 | costo ≤ 25 pb y 30% menos caída | RECHAZADO / RECHAZADO / RECHAZADO |
| 6 | Momentum, desarrollo | +86 | +84 | +83 | pasar el filtro | 2 de 16 pasan / 2 de 16 pasan / 2 de 16 pasan |
| 6 | Yield de dividendo alto, desarrollo | -86 | -117 | -125 | pasar el filtro | — |
| 6 | Calidad y barato (FFO), desarrollo | -211 | -211 | -210 | pasar el filtro | — |
| 6 | Momentum, validación | +57 | +60 | +60 | ≥ +50 pb | — |
| 6 | Momentum, emisores sellados (prueba final) | +38 | +41 | +42 | ≥ +50 pb | RECHAZADO / RECHAZADO / RECHAZADO |
| estudios | Semáforo de NNN: modelo completo contra aportar siempre | -560 | -502 | -489 | > 0 | — |
| estudios | Semáforo de O: modelo completo contra aportar siempre | -58 | -41 | -38 | > 0 | — |
| estudios | Semáforo de WPC: modelo completo contra aportar siempre | +1 | +24 | +28 | > 0 | — |
| estudios | Asignación entre O, NNN y WPC: consenso contra partes iguales | +72 | +63 | +60 | > 0 | — |

## Fase 5: las 22 reglas de entrada, en desarrollo (1972-2015)

Mejora rebalanceando, en pb al año contra aportar siempre. La última columna dice qué criterio del filtro pre-registrado falla con el broker al 35%.

| Señal | Regla | SIC | Broker 30% | Broker 35% | Con el broker al 35% |
|---|---|---|---|---|---|
| condiciones financieras | fuera en el quintil peor (20%) | +92 | +113 | +114 | no predice a 12 meses |
| tendencia de 10 meses | signo | +15 | +87 | +93 | pierde con un mes de retraso; pierde en una era; no predice a 12 meses |
| momentum contra el efectivo | signo | +2 | +50 | +54 | pierde con un mes de retraso; pierde en una era; no predice a 12 meses |
| compuesto de cuatro familias | continua con piso de 50% | 0 | +22 | +24 | pierde en una era; no predice a 12 meses |
| crédito bancario a inmuebles | fuera en el quintil peor (20%) | -15 | +7 | +10 | no predice a 12 meses |
| caro y con tendencia negativa | fuera si caro y a la baja | -11 | -2 | -1 | no le gana a aportar siempre; pierde con un mes de retraso; pierde con doble costo; pierde en una era; no predice a 12 meses |
| bolsa del mes | fuera en el quintil peor (20%) | -119 | -10 | -6 | no le gana a aportar siempre; pierde con un mes de retraso; pierde con doble costo; pierde en una era; no predice a 12 meses |
| yield contra el Treasury | fuera en el quintil peor (20%) | -43 | -22 | -21 | no le gana a aportar siempre; pierde con un mes de retraso; pierde con doble costo; pierde en una era |
| condiciones financieras | continua con piso de 50% | -50 | -28 | -25 | no le gana a aportar siempre; pierde con un mes de retraso; pierde con doble costo; pierde en una era; no predice a 12 meses |
| bolsa del mes | continua con piso de 50% | -104 | -34 | -31 | no le gana a aportar siempre; pierde con un mes de retraso; pierde con doble costo; pierde en una era; no predice a 12 meses |
| crédito bancario a inmuebles | continua con piso de 50% | -59 | -43 | -40 | no le gana a aportar siempre; pierde con un mes de retraso; pierde con doble costo; pierde en una era; no predice a 12 meses |
| cambio del spread de crédito | fuera en el quintil peor (20%) | -117 | -71 | -66 | no le gana a aportar siempre; pierde con doble costo; pierde en una era; no predice a 12 meses |
| yield contra bonos Baa | fuera en el quintil peor (20%) | -93 | -74 | -72 | no le gana a aportar siempre; no le gana a la mezcla fija; pierde con un mes de retraso; pierde con doble costo; pierde en una era; no predice a 12 meses |
| cambio del spread de crédito | continua con piso de 50% | -119 | -80 | -75 | no le gana a aportar siempre; pierde con un mes de retraso; pierde con doble costo; pierde en una era; no predice a 12 meses |
| yield contra el Treasury | continua con piso de 50% | -137 | -110 | -107 | no le gana a aportar siempre; no le gana a la mezcla fija; pierde con un mes de retraso; pierde con doble costo; pierde en una era |
| yield contra bonos Baa | continua con piso de 50% | -150 | -118 | -115 | no le gana a aportar siempre; no le gana a la mezcla fija; pierde con un mes de retraso; pierde con doble costo; pierde en una era; no predice a 12 meses |
| spread de default | continua con piso de 50% | -199 | -165 | -160 | no le gana a aportar siempre; no le gana a la mezcla fija; pierde con un mes de retraso; pierde con doble costo; pierde en una era |
| yield contra la tasa real | fuera en el quintil peor (20%) | -225 | -180 | -178 | no le gana a aportar siempre; no le gana a la mezcla fija; pierde con un mes de retraso; pierde con doble costo; pierde en una era; no predice a 12 meses |
| yield contra la tasa real | continua con piso de 50% | -239 | -204 | -200 | no le gana a aportar siempre; no le gana a la mezcla fija; pierde con un mes de retraso; pierde con doble costo; pierde en una era; no predice a 12 meses |
| yield de los REITs | continua con piso de 50% | -247 | -205 | -200 | no le gana a aportar siempre; no le gana a la mezcla fija; pierde con un mes de retraso; pierde con doble costo; pierde en una era; no predice a 12 meses |
| spread de default | fuera en el quintil peor (20%) | -254 | -215 | -211 | no le gana a aportar siempre; no le gana a la mezcla fija; pierde con un mes de retraso; pierde con doble costo; pierde en una era |
| yield de los REITs | fuera en el quintil peor (20%) | -490 | -427 | -419 | no le gana a aportar siempre; no le gana a la mezcla fija; pierde con un mes de retraso; pierde con doble costo; pierde en una era; no predice a 12 meses |

## Fase 7: la escalera de modelos, en desarrollo

Los modelos no dependen de los impuestos: se usan las mismas exposiciones de la fase 7. «Compuesto» y «ridge» están siempre dentro, así que son aportar siempre (mejora cero).

| Peldaño | SIC (pb) | Broker 30% (pb) | Broker 35% (pb) | Exposición promedio |
|---|---|---|---|---|
| mejor señal sola | -35 | -31 | -31 | 98% |
| compuesto | 0 | 0 | 0 | 100% |
| ridge | 0 | 0 | 0 | 100% |
| árboles | -393 | -351 | -349 | 89% |
| regímenes | -217 | -135 | -129 | 79% |

## Fase 8: la protección por tendencia

En la validación de EE. UU. (2016 en adelante) la tendencia queda en -490 pb (SIC), -387 pb (Broker 30%), -386 pb (Broker 35%) al año contra aportar siempre.

| Mercado | SIC (pb) | Broker 30% (pb) | Broker 35% (pb) | Protege (SIC / 30% / 35%) |
|---|---|---|---|---|
| Japón | -67 | -2 | +7 | no / no / no |
| Australia | -345 | -257 | -251 | no / no / no |
| Singapur | -307 | -212 | -204 | no / no / no |
| Hong Kong | +165 | +253 | +265 | no / no / no |
| Reino Unido | +347 | +380 | +374 | sí / sí / sí |
| Europa continental | -271 | -201 | -198 | no / no / no |
| Canadá | -195 | -115 | -109 | no / no / no |
| FIBRAs (México) | -343 | -276 | -279 | no / no / no |


## Fase 6: en cuáles REITs

Desarrollo (2009-2015), mejora contra aportar a todos los elegibles:

| Regla | SIC (pb) | Broker 30% (pb) | Broker 35% (pb) | Pasa (SIC / 30% / 35%) |
|---|---|---|---|---|
| Yield alto contra su historia | +214 | +213 | +213 | sí / sí / sí |
| Crecimiento del dividendo | +207 | +207 | +207 | no / no / no |
| Calidad y barato contra su historia | +194 | +194 | +195 | no / no / no |
| Momentum (meses 12 a 3) | +86 | +84 | +83 | sí / sí / sí |
| Calidad | +68 | +69 | +69 | no / no / no |
| Tamaño grande | +60 | +66 | +68 | no / no / no |
| Lejos del default | +59 | +59 | +59 | no / no / no |
| Crecimiento de activos bajo | -6 | -4 | -3 | no / no / no |
| Volatilidad baja | -34 | -33 | -32 | no / no / no |
| Payout bajo | -98 | -90 | -88 | no / no / no |
| Rentabilidad (FFO / activos) | -118 | -116 | -116 | no / no / no |
| Yield de dividendo alto | -86 | -117 | -125 | no / no / no |
| Apalancamiento bajo | -136 | -135 | -135 | no / no / no |
| Rendimiento FFO alto | -167 | -173 | -175 | no / no / no |
| Rendimiento de la empresa (cap rate) | -172 | -179 | -181 | no / no / no |
| Calidad y barato (FFO) | -211 | -211 | -210 | no / no / no |

Validación (2016 en adelante):

| Regla | SIC (pb) | Broker 30% (pb) | Broker 35% (pb) | Pasa (SIC / 30% / 35%) |
|---|---|---|---|---|
| Yield alto contra su historia | -28 | -29 | -29 | no / no / no |
| Momentum (meses 12 a 3) | +57 | +60 | +60 | sí / sí / sí |
| Sin riesgo de recorte | -18 | -15 | -14 | no / no / no |

Momentum en los emisores sellados (2012 en adelante), con el código corregido de la fase 6:

| Perfil | Mejora (pb) | Con retraso (pb) | Doble costo (pb) | TIR de aportar a todos | Veredicto del criterio | Veredicto declarado |
|---|---|---|---|---|---|---|
| SIC | +38 | +30 | +38 | 5.89% | RECHAZADO | RECHAZADO |
| Broker 30% | +41 | +32 | +41 | 5.14% | RECHAZADO | RECHAZADO |
| Broker 35% | +42 | +33 | +42 | 4.93% | RECHAZADO | RECHAZADO |

El PBO (0.04) y el Sharpe deflactado (0.39, umbral 0.95) usan retornos antes de impuestos: son los de la fase 6 y no cambian con el perfil.

## Estudios de O, NNN y WPC

Semáforo (backtest de reglas): ventaja de TIR en dólares contra aportar cada mes al mismo papel.

| Emisor | Variante | SIC (pb) | Broker 30% (pb) | Broker 35% (pb) |
|---|---|---|---|---|
| NNN | Modelo completo | -560 | -502 | -489 |
| NNN | Modelo, reinversión en 12 meses | -191 | -168 | -163 |
| NNN | Solo compras (nunca vende) | -92 | -74 | -70 |
| NNN | Solo compras, reinversión en 12 meses | -28 | -22 | -21 |
| NNN | Solo tesis rota (compra fija) | -98 | -84 | -81 |
| O | Modelo completo | -58 | -41 | -38 |
| O | Modelo, reinversión en 12 meses | -31 | -25 | -23 |
| O | Solo compras (nunca vende) | -58 | -41 | -38 |
| O | Solo compras, reinversión en 12 meses | -31 | -25 | -23 |
| O | Solo tesis rota (compra fija) | 0 | 0 | 0 |
| WPC | Modelo completo | +1 | +24 | +28 |
| WPC | Modelo, reinversión en 12 meses | -197 | -182 | -181 |
| WPC | Solo compras (nunca vende) | -6 | -1 | 0 |
| WPC | Solo compras, reinversión en 12 meses | -5 | -2 | -2 |
| WPC | Solo tesis rota (compra fija) | -189 | -178 | -177 |

Asignación entre los tres: toda la aportación al más barato contra su historia, contra partes iguales.

| Método | SIC (pb) | Broker 30% (pb) | Broker 35% (pb) |
|---|---|---|---|
| Múltiplo P/FFO | +69 | +59 | +57 |
| Prima sobre el Treasury | +53 | +45 | +43 |
| Prima sobre la tasa real | +45 | +38 | +37 |
| Prima sobre bonos Baa | +65 | +56 | +53 |
| Yield de dividendo | +54 | +43 | +41 |
| Dividendo sobre el Treasury | +43 | +34 | +32 |
| Múltiplo contra sus últimos 5 años | +55 | +52 | +51 |
| Consenso de los siete | +72 | +63 | +60 |

Comprar y mantener reinvirtiendo el dividendo neto: retorno anual en dólares de toda la historia.

| Emisor | Desde | SIC | Broker 30% | Broker 35% |
|---|---|---|---|---|
| NNN | 1992 | 10.01% | 8.62% | 8.26% |
| O | 1994 | 11.65% | 10.37% | 10.03% |
| WPC | 1998 | 9.49% | 8.16% | 7.81% |

## Lo que se escribió antes de correr

* **H-B1, aportar siempre pierde de 120 a 180 pb al año en 1972-2015.** No se cumple: pierde 145 y 184 pb.
* **H-B2, el timing mejora un poco pero no cambia el veredicto.** Se cumple: 22 de 22 reglas salen mejor con el broker al 35% que con el SIC, pero ninguna pasa el filtro y la escalera no deja candidato.
* **H-B3, la protección por tendencia sigue RECHAZADA y cuesta menos.** Se cumple: -127 pb con el SIC contra -49 con el broker al 35%.
* **H-B4, momentum mejora en los sellados; si cruza +50 pb, queda INCONCLUSO posterior.** Se cumple: +38 pb con el SIC y +42 con el broker al 35% (RECHAZADO).
* **H-B5, el yield alto y «calidad y barato» salen peor.** Se cumple a medias: yield alto -86 → -125 pb; calidad y barato -211 → -210 pb.
* **H-B6, la ventaja del consenso baja.** Se cumple: +72 pb con el SIC y +60 con el broker al 35%.
* **H-B7, el semáforo cambia menos de 20 pb en cada emisor.** No se cumple: NNN 71 pb, O 19 pb, WPC 27 pb de cambio máximo.

## La línea base no se movió

La columna SIC de esta corrida contra los resultados que cada fase ya tenía guardados. La prueba final de momentum en los emisores sellados corrió con el código corregido de la fase 6 y da lo mismo que la original.

| Fase | Qué se compara | Cifras | Diferencia máxima (pb) |
|---|---|---|---|
| 3 | TIR del techo | 9 | 0.0e+00 |
| 5 | Mejora de las 22 reglas | 22 | 0.0e+00 |
| 7 | Mejora de los 5 peldaños | 5 | 0.0e+00 |
| 8 | Tendencia en EE. UU., 2016 en adelante | 1 | 4.3e-08 |
| 8 | Tendencia en los 8 mercados | 8 | 0.0e+00 |
| 6 | Mejora de las 16 reglas, desarrollo | 16 | 0.0e+00 |
| 6 | Mejora en validación | 3 | 0.0e+00 |
| 6 | Momentum en los emisores sellados | 1 | 0.0e+00 |

## Aperturas y bitácora

Esta corrida abrió la validación 2 veces (fases 6 y 8) y los archivos sellados 25 veces: los tres archivos de cada uno de los ocho mercados y los emisores sellados, una vez cada uno, con los tres perfiles evaluados sobre los mismos datos. Modelos congelados antes de abrir: `sensibilidad-fiscal: proteccion-tendencia-10m`, `sensibilidad-fiscal: seleccion-fase6: momentum`. Los ocho mercados ya se habían abierto tres veces con el modelo de la fase 8 y los emisores sellados una vez con el de la fase 6. La bitácora guarda 192 reevaluaciones con la familia `sensibilidad-fiscal`; no cuentan como intentos de búsqueda.

## Límites

* Una sola tasa marginal para todo el ingreso; la tarifa real es progresiva.
* Todo lo que reparte un REIT se trata como dividendo. Parte puede ser devolución de capital o ganancia de capital, con otro trato.
* No se modelan la ganancia cambiaria, el ajuste por inflación del costo ni el impuesto sucesorio.
* Los mercados fuera de EE. UU. de la fase 8 usan el mismo perfil, como en la línea base: un REIT de Japón o de Australia tiene otra retención.
* En la fase 6 el efectivo no cobra intereses (es transitorio y afecta igual a la regla y a todos), así que la tasa de los intereses no cambia nada ahí.
* Con comisión de 0%, la prueba de doble costo no cambia nada con el broker.
