# Fase 6: ¿en cuáles REITs? Resultados

Pre-registro: `fase6_preregistro.md` (commit anterior a esta corrida). Generado por `python scripts/investigacion.py fase6`. Mejoras en puntos base al año de TIR después de impuestos del SIC, aportando 3,000 dólares por trimestre a los escogidos sin vender nunca, contra lo mismo a todos los elegibles. «Exceso bruto»: antes de impuestos, cohortes de 12 meses encimadas. «Recortes»: fracción que recortó el dividendo o quebró en los 12 meses siguientes. «Desplomes»: fracción que perdió 30% o más.

## Veredicto: RECHAZADO

**Desarrollo: 2 de 16 reglas pasan el filtro** (a validación: Yield alto contra su historia, Momentum (meses 12 a 3)). PBO = 0.04 (umbral 0.20); Sharpe deflactado de la mejor por Sharpe («Momentum (meses 12 a 3)») = 0.395 (umbral 0.95), con 19 intentos en la bitácora.

## Lo que se escribió antes de correr

* **H0 — nada le gana a aportar a todos por +50 pb de forma robusta.** Se cumple. Solo momentum pasó la validación, y en los emisores sellados ganó +38 pb al año (el umbral es +50) con un exceso bruto de 0.1%; su Sharpe deflactado en desarrollo fue 0.39 (umbral 0.95).
* **H1 — momentum: exceso pequeño e inestable.** Se cumple. +86 pb en desarrollo (exceso bruto 4.7%, t = +3.2), +57 pb en validación (exceso 0.9%, t = +0.6: 2.1% en 2016-2020 y -0.2% en 2021-2026) y +38 pb en los sellados.
* **H2 — el valor solo, sin exceso; con calidad, positivo.** La primera parte se cumple: rendimiento FFO -167 pb y cap rate -172 pb. La segunda no: «barato entre los de calidad» fue la peor de las 16 (-211 pb, exceso bruto -6.0%, t = -4.5).
* **H3 — el yield alto es una trampa.** Se cumple: -86 pb y 21% de recortes en el año siguiente contra 10% del universo.
* **H4 — poca deuda y lejos del default: menos trampas, poco retorno.** Se cumple en lo defensivo: recortes de 6% y 5% contra 10%; en retorno, apalancamiento bajo perdió (-136 pb, t = -3.5) y distancia al default quedó en +59 pb.
* **H5 — calidad: menos recortes, exceso cercano a cero.** Se cumple: 0% de recortes contra 10%; +68 pb de TIR y exceso bruto de -1.4%.
* **H6 — la prueba clave: barato entre los de calidad contra todos los de calidad.** Rechazada en desarrollo: -211 pb contra +68 pb de toda la calidad. Ser barato por FFO, aun entre REITs sanos, no pagó; no llegó a validación.
* **H7 — barato contra su propia historia.** Pasó desarrollo solo (+214 pb, con una docena de emisores y desde 2013) y falló en validación (-28 pb, exceso -0.9%). Entre los de calidad tampoco pasó el filtro.
* **H8 — el detector predice, pero apenas mueve la TIR.** Se cumple: AUC fuera de muestra de 0.75 (umbral 0.70) y habilidad de Brier de +18%; sacar al quintil de más riesgo bajó los recortes de 14% a 9% pero costó 18 pb al año.
* **H9 — vender después de un recorte no ayuda.** Se cumple: en validación, los que acababan de recortar rindieron 7.7% más que el universo en los 12 meses siguientes (mediana 6.3%, t = +1.3).

## Validación (2016 en adelante, emisores no sellados)

| Regla | Hip. | Mejora TIR (pb) | Con retraso (pb) | Doble costo (pb) | Rotando (pb) | Exceso bruto | t NW | Exceso 2016-2020 | Exceso 2021-2026 | Corr. rangos | Recortes (regla / todos) | Desplomes (regla / todos) | Escogidos | Pasa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Momentum (meses 12 a 3) | S1 | +57 | +48 | +57 | +293 | 0.9% | +0.56 | 2.1% | -0.2% | +0.026 | 12% / 14% | 7% / 9% | 34 | sí |
| Sin riesgo de recorte | D1 | -18 | -18 | -18 | -65 | -0.1% | -0.60 | 0.8% | -0.9% | — | 9% / 14% | 7% / 9% | 80 | no |
| Yield alto contra su historia | S12 | -28 | -14 | -29 | -274 | -0.9% | -0.16 | -1.3% | -0.5% | -0.023 | 24% / 14% | 12% / 9% | 29 | no |

## El detector de recortes, fuera de muestra (validación)

3,521 pronósticos, 508 recortes o quiebras. AUC = 0.749 (umbral 0.70); Brier 0.1029 contra 0.1251 de la frecuencia histórica (habilidad +17.8%). AUC de cada variable sola: payout 0.62, apalancamiento 0.67, distancia_al_default 0.69, momentum 0.60, yield_relativo 0.73, tamano 0.58, volatilidad 0.67, recorte_previo 0.58, crecimiento_ffo 0.61.

## ¿Vender después de un recorte? (D3)

* Desarrollo: 30 recortes nuevos; en los 12 meses siguientes rindieron -0.8% contra el universo en promedio (mediana 0.3%, t = +0.84).
* Validación: 126 recortes nuevos; en los 12 meses siguientes rindieron 7.7% contra el universo en promedio (mediana 6.3%, t = +1.31).

## Prueba final (emisores sellados)

| Regla | Hip. | Mejora TIR (pb) | Con retraso (pb) | Doble costo (pb) | Rotando (pb) | Exceso bruto | t NW | Exceso 2013-2015 | Exceso 2016-2026 | Corr. rangos | Recortes (regla / todos) | Desplomes (regla / todos) | Escogidos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Momentum (meses 12 a 3) | S1 | +38 | +30 | +38 | +5 | 0.1% | -0.25 | 0.3% | 0.0% | -0.035 | 7% / 11% | 6% / 8% | 14 |

## Todas las reglas, en desarrollo

| Regla | Hip. | Mejora TIR (pb) | Con retraso (pb) | Doble costo (pb) | Rotando (pb) | Exceso bruto | t NW | Exceso 2011-2013 | Exceso 2014-2015 | Corr. rangos | Recortes (regla / todos) | Desplomes (regla / todos) | Escogidos | Pasa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Yield alto contra su historia | S12 | +214 | +199 | +214 | +754 | 6.4% | +3.86 | 7.1% | 6.0% | +0.217 | 8% / 10% | 1% / 1% | 12 | sí |
| Crecimiento del dividendo | S13 | +207 | +183 | +207 | +592 | 5.5% | +2.65 | -1.2% | 8.5% | +0.392 | 6% / 10% | 1% / 1% | 12 | no |
| Calidad y barato contra su historia | S8 | +194 | +196 | +194 | +691 | 2.0% | +0.66 | -6.8% | 6.1% | — | 0% / 10% | 2% / 1% | 6 | no |
| Momentum (meses 12 a 3) | S1 | +86 | +60 | +86 | +105 | 4.7% | +3.20 | 7.2% | 1.7% | +0.133 | 9% / 10% | 1% / 1% | 30 | sí |
| Calidad | S8 | +68 | +68 | +68 | +69 | -1.4% | -0.62 | -7.2% | 2.4% | — | 0% / 10% | 2% / 1% | 24 | no |
| Tamaño grande | S11 | +60 | +51 | +60 | +86 | -0.7% | -0.26 | -5.5% | 5.1% | -0.095 | 5% / 10% | 1% / 1% | 31 | no |
| Lejos del default | S3 | +59 | +41 | +59 | +117 | 0.1% | +0.04 | -4.2% | 3.5% | -0.054 | 5% / 10% | 2% / 1% | 28 | no |
| Crecimiento de activos bajo | S10 | -6 | -57 | -6 | +63 | 0.2% | +0.38 | 0.3% | 0.1% | +0.093 | 17% / 10% | 1% / 1% | 25 | no |
| Volatilidad baja | S4 | -34 | -32 | -34 | +15 | -2.3% | -1.03 | -6.7% | 3.0% | -0.113 | 11% / 10% | 1% / 1% | 29 | no |
| Yield de dividendo alto | S7 | -86 | -72 | -86 | -98 | -1.0% | -0.33 | -0.8% | -1.2% | -0.029 | 21% / 10% | 0% / 1% | 26 | no |
| Payout bajo | S8 | -98 | -99 | -98 | -416 | -1.2% | -0.69 | 0.6% | -3.4% | +0.005 | 8% / 10% | 2% / 1% | 24 | no |
| Rentabilidad (FFO / activos) | S10 | -118 | -111 | -118 | -227 | -2.0% | -1.41 | -3.8% | 0.2% | -0.094 | 9% / 10% | 2% / 1% | 25 | no |
| Apalancamiento bajo | S2 | -136 | -132 | -136 | -149 | -3.1% | -3.47 | -4.4% | -1.6% | -0.109 | 6% / 10% | 1% / 1% | 29 | no |
| Rendimiento FFO alto | S6 | -167 | -151 | -166 | -304 | -1.0% | -0.67 | 1.1% | -3.4% | -0.024 | 14% / 10% | 2% / 1% | 25 | no |
| Rendimiento de la empresa (cap rate) | S5 | -172 | -155 | -172 | -321 | -0.7% | -0.34 | 2.0% | -3.7% | +0.004 | 15% / 10% | 2% / 1% | 25 | no |
| Calidad y barato (FFO) | S8 | -211 | -186 | -211 | -712 | -6.0% | -4.48 | -6.5% | -5.7% | — | 0% / 10% | 5% / 1% | 8 | no |

## Correcciones después de la primera corrida (declaradas)

La primera corrida, con el código del pre-registro, tenía dos errores de programación que se encontraron al revisar sus números, después de verlos:

1. **El exceso bruto comparaba periodos distintos**: la regla en los trimestres en que ya tenía cartera y el universo en todos. Ahora los dos se miden en los mismos trimestres.
2. **Sin escogidos, la aportación se quedaba en efectivo al 0%.** Las señales que necesitan años de historia (el yield contra su historia, el crecimiento del dividendo) no escogen a nadie antes de 2013, y el simulador guardaba ese dinero: un timing accidental que esta fase no mide. Ahora va a todos los elegibles, que es lo que dice el pre-registro («a los escogidos… contra lo mismo a todos»).

La primera corrida se guardó completa en `data/investigacion/resultados/fase6/primera_corrida/`. Las reglas que cambiaron:

| Regla | Mejora antes (pb) | Mejora corregida (pb) | Exceso antes | Exceso corregido | Pasaba | Pasa |
|---|---|---|---|---|---|---|
| Lejos del default | -51 | +59 | -5.1% | 0.1% | no | no |
| Yield alto contra su historia | +124 | +214 | -2.9% | 6.4% | no | sí |
| Crecimiento del dividendo | -168 | +207 | -3.8% | 5.5% | no | no |
| Calidad | +9 | +68 | -6.2% | -1.4% | no | no |
| Calidad y barato (FFO) | -347 | -211 | -10.9% | -6.0% | no | no |
| Calidad y barato contra su historia | +79 | +194 | -7.2% | 2.0% | no | no |

Con la corrección pasan el desarrollo Yield alto contra su historia, Momentum (meses 12 a 3); en la primera corrida solo Momentum (meses 12 a 3). En validación, «yield contra su historia» pierde y momentum vuelve a pasar con las mismas cifras: el veredicto no cambia.

**La prueba final se corrió una sola vez**, en la primera corrida, con momentum congelado. Ninguno de los dos errores la toca: momentum tuvo escogidos en todos los trimestres y su veredicto se decide por la TIR. Los sellados no se volvieron a abrir. La bitácora registra las tres aperturas de la validación (la primera se cayó antes de calcular nada por un faltante en el detector, corregido en su propio commit).

