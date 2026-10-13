# Análisis de poder. Resultados

Pre-registro: `poder_preregistro.md` (commit anterior a esta corrida). ¿Las pruebas podían ver una ventaja real? Para cada prueba de cabecera, una distribución nula con placebos —reglas sin habilidad con el mismo perfil— da su error estándar (EE) y su efecto mínimo detectable (MDE ≈ 2.49 × EE, una cola al 5% y potencia de 80%). Generado por `python scripts/investigacion.py poder`.

## Veredicto


| Prueba | Muestra | Observado (pb) | Placebo promedio (pb) | EE (pb) | MDE (pb) | Observado − placebo (pb) | 100 pb pasarían inadvertidos | 200 pb pasarían inadvertidos |
|---|---|---|---|---|---|---|---|---|
| Timing: tendencia de 10 meses · signo | 1972-2015 | +15 | -302 | 174 | 432 | +317 | 82% | 67% |
| Timing: condiciones financieras · fuera en el quintil peor (20%) | 1972-2015 | +92 | -86 | 78 | 195 | +178 | 74% | 23% |
| Timing: yield contra el Treasury · fuera en el quintil peor (20%) | 1972-2015 | -43 | -127 | 81 | 203 | +84 | 45% | 11% |
| Protección por tendencia, EE. UU. | 2016 en adelante | -490 | -142 | 211 | 525 | -348 | 89% | 76% |
| Selección: momentum | 2011-2015 | +86 | 0 | 44 | 110 | +86 | 32% | 0% |
| Selección: momentum | 2016 en adelante | +57 | +1 | 24 | 59 | +56 | 0% | 0% |
| Asignación entre O, NNN y WPC: consenso | 2003-2026 | +72 | 0 | 22 | 54 | +73 | 0% | 0% |

* **Cuándo entrar al sector: las pruebas eran poco finas.** El efecto mínimo detectable va de 195 a 432 pb al año: una regla con 100 pb de habilidad verdadera habría pasado inadvertida entre 45% y 82% de las veces. «No se encontró» no descarta una ventaja de 1 punto al año. Además, salir a ciegas cuesta: el placebo promedio pierde entre 86 y 302 pb al año, así que una regla necesita esa habilidad solo para empatar con aportar siempre.
* **En cuáles REITs: la prueba sí era fina.** El MDE de momentum fue de 110 pb en desarrollo y 59 pb en validación, y momentum sí se distinguió del azar (p del placebo de 0.03 o menos). Lo que no alcanzó fue el tamaño: el criterio pedía +50 pb también en los emisores sellados.
* **Escoger entre O, NNN y WPC con la valuación: la prueba más fina y la ventaja sí se ve.** EE de 22 pb y MDE de 54 pb; el consenso ganó +72 pb al año y ninguna de las 500 elecciones al azar lo igualó. Sigue siendo INCONCLUSO por pocas decisiones y sesgo de supervivencia, pero no es una moneda al aire.

El oráculo que conoce los 12 meses siguientes ganó +379 pb al año rebalanceando (fase 3): es el techo de cualquier regla de timing. Un MDE cerca de ese techo quiere decir que la prueba solo podía ver ventajas casi imposibles.

## Curvas de potencia

Probabilidad de distinguir del azar, al 5%, una regla con una habilidad verdadera de δ al año sobre una regla sin habilidad con el mismo perfil.

| Prueba | Muestra | δ = 25 pb | δ = 50 pb | δ = 100 pb | δ = 150 pb | δ = 200 pb | δ = 300 pb |
|---|---|---|---|---|---|---|---|
| Timing: tendencia de 10 meses · signo | 1972-2015 | 8% | 10% | 18% | 22% | 33% | 52% |
| Timing: condiciones financieras · fuera en el quintil peor (20%) | 1972-2015 | 8% | 12% | 26% | 50% | 77% | 99% |
| Timing: yield contra el Treasury · fuera en el quintil peor (20%) | 1972-2015 | 13% | 25% | 55% | 79% | 89% | 97% |
| Protección por tendencia, EE. UU. | 2016 en adelante | 5% | 8% | 11% | 15% | 24% | 44% |
| Selección: momentum | 2011-2015 | 13% | 26% | 68% | 96% | 100% | 100% |
| Selección: momentum | 2016 en adelante | 28% | 69% | 100% | 100% | 100% | 100% |
| Asignación entre O, NNN y WPC: consenso | 2003-2026 | 28% | 71% | 100% | 100% | 100% | 100% |

## El Sharpe deflactado

El Sharpe anual de la mejor regla contra el que habría hecho falta para un Sharpe deflactado de 0.95, con los mismos intentos, la misma varianza de Sharpes y la misma forma de la serie.

| Prueba | Mejor regla | Periodos | Intentos | Sharpe observado | Sharpe necesario | Sharpe deflactado |
|---|---|---|---|---|---|---|
| Fase 5: la mejor regla de entrada | tendencia de 10 meses · signo | 527 | 22 | 0.72 | 0.44 | 1.00 |
| Fase 6: la mejor regla de selección | momentum | 18 | 19 | 1.52 | 2.53 | 0.39 |

## Verificación: una ventaja inyectada en la tendencia de 10 meses

Se le suma a la tendencia una habilidad conocida y se remuestrea 1972-2015 con bootstrap por bloques de 12 meses. ¿Qué fracción de las muestras pasa los criterios de retorno del filtro de la fase 5 (le gana a aportar siempre y a la mezcla fija, con un mes de retraso, con doble costo y en las dos mitades) y el +50 pb? La predictibilidad queda fuera: es un techo de la potencia real.

| Habilidad inyectada (pb) | Mejora mediana (pb) | Pasa los criterios de retorno | Pasa +50 pb | Pasa los dos |
|---|---|---|---|---|
| 0 | -4 | 20% | 40% | 20% |
| 100 | +69 | 23% | 54% | 23% |
| 200 | +195 | 38% | 77% | 38% |

## Lo que se escribió antes de correr

* **H-P1** (EE del timing entre 50 y 150 pb): No se cumple: 174 pb, 78 pb, 81 pb.
* **H-P2** (EE de la selección entre 100 y 250 pb y MDE de más de 250 pb): No se cumple: EE de 44 pb y 24 pb.
* **H-P3** (EE de la asignación entre 20 y 60 pb, el más fino de todos): Se cumple: 22 pb.
* **H-P4** (el Sharpe necesario en la fase 6 está muy arriba del observado): No se cumple: hacía falta 2.53 y se observó 1.52.

## Cómo se lee

* «Observado − placebo» es la habilidad que mostró la regla real contra reglas sin habilidad con el mismo perfil; el «placebo promedio» es lo que cuesta, en promedio, estar fuera o escoger a ciegas.
* Un resultado negativo de una prueba con un MDE de 300 pb no descarta una ventaja de 100 pb: solo descarta una ventaja grande y confiable.
* Las curvas suponen que la habilidad corre la nula sin cambiar su forma. La verificación con ventaja inyectada en la tendencia de 10 meses dice qué tan buena es esa aproximación.
* Los placebos usan la contabilidad del SIC (la línea base); con el broker el ruido es casi el mismo.
