# Fase 6: ¿en cuáles REITs? Resultados

Pre-registro: `fase6_preregistro.md` (commit anterior a esta corrida). Generado por `python scripts/investigacion.py fase6`. Mejoras en puntos base al año de TIR después de impuestos del SIC, aportando 3,000 dólares por trimestre a los escogidos sin vender nunca, contra lo mismo a todos los elegibles. «Exceso bruto»: antes de impuestos, cohortes de 12 meses encimadas. «Recortes»: fracción que recortó el dividendo o quebró en los 12 meses siguientes. «Desplomes»: fracción que perdió 30% o más.

## Veredicto: RECHAZADO

**Desarrollo: 1 de 16 reglas pasan el filtro** (a validación: Momentum (meses 12 a 3)). PBO = 0.04 (umbral 0.20); Sharpe deflactado de la mejor por Sharpe («Momentum (meses 12 a 3)») = 0.450 (umbral 0.95), con 16 intentos en la bitácora.

## Validación (2016 en adelante, emisores no sellados)

| Regla | Hip. | Mejora TIR (pb) | Con retraso (pb) | Doble costo (pb) | Rotando (pb) | Exceso bruto | t NW | Exceso 2015-2020 | Exceso 2020-2026 | Corr. rangos | Recortes (regla / todos) | Desplomes (regla / todos) | Escogidos | Pasa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Momentum (meses 12 a 3) | S1 | +57 | +48 | +57 | +293 | 0.9% | +0.56 | 2.1% | -0.2% | +0.026 | 12% / 14% | 7% / 9% | 34 | sí |
| Sin riesgo de recorte | D1 | -18 | -18 | -18 | -65 | -0.1% | -0.60 | 0.8% | -0.9% | — | 9% / 14% | 7% / 9% | 80 | no |

## El detector de recortes, fuera de muestra (validación)

3,521 pronósticos, 508 recortes o quiebras. AUC = 0.749 (umbral 0.70); Brier 0.1029 contra 0.1251 de la frecuencia histórica (habilidad +17.8%). AUC de cada variable sola: payout 0.62, apalancamiento 0.67, distancia_al_default 0.69, momentum 0.60, yield_relativo 0.73, tamano 0.58, volatilidad 0.67, recorte_previo 0.58, crecimiento_ffo 0.61.

## ¿Vender después de un recorte? (D3)

* Desarrollo: 30 recortes nuevos; en los 12 meses siguientes rindieron -0.8% contra el universo en promedio (mediana 0.3%, t = +0.84).
* Validacion: 126 recortes nuevos; en los 12 meses siguientes rindieron 7.7% contra el universo en promedio (mediana 6.3%, t = +1.31).

## Prueba final (emisores sellados)

| Regla | Hip. | Mejora TIR (pb) | Con retraso (pb) | Doble costo (pb) | Rotando (pb) | Exceso bruto | t NW | Exceso 2013-2015 | Exceso 2015-2026 | Corr. rangos | Recortes (regla / todos) | Desplomes (regla / todos) | Escogidos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Momentum (meses 12 a 3) | S1 | +38 | +30 | +38 | +5 | 0.1% | -0.25 | 0.3% | 0.0% | -0.035 | 7% / 11% | 6% / 8% | 14 |

## Todas las reglas, en desarrollo

| Regla | Hip. | Mejora TIR (pb) | Con retraso (pb) | Doble costo (pb) | Rotando (pb) | Exceso bruto | t NW | Exceso 2011-2013 | Exceso 2013-2015 | Corr. rangos | Recortes (regla / todos) | Desplomes (regla / todos) | Escogidos | Pasa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Yield alto contra su historia | S12 | +124 | +135 | +124 | +197 | -2.9% | +3.86 | -17.2% | 6.0% | +0.217 | 8% / 10% | 1% / 1% | 12 | no |
| Momentum (meses 12 a 3) | S1 | +85 | +64 | +85 | +112 | 4.7% | +3.20 | 7.2% | 1.7% | +0.133 | 9% / 10% | 1% / 1% | 30 | sí |
| Calidad y barato contra su historia | S8 | +79 | +171 | +80 | +142 | -7.2% | +0.66 | -31.1% | 6.1% | — | 0% / 10% | 2% / 1% | 6 | no |
| Tamaño grande | S11 | +60 | +51 | +60 | +86 | -0.7% | -0.26 | -5.5% | 5.1% | -0.095 | 5% / 10% | 1% / 1% | 31 | no |
| Calidad | S8 | +9 | +84 | +9 | -94 | -6.2% | -0.62 | -16.2% | 2.4% | — | 0% / 10% | 2% / 1% | 24 | no |
| Crecimiento de activos bajo | S10 | -6 | -57 | -6 | +63 | 0.2% | +0.38 | 0.3% | 0.1% | +0.093 | 17% / 10% | 1% / 1% | 25 | no |
| Volatilidad baja | S4 | -34 | -32 | -34 | +15 | -2.3% | -1.03 | -6.7% | 3.0% | -0.113 | 11% / 10% | 1% / 1% | 29 | no |
| Lejos del default | S3 | -51 | -26 | -50 | -23 | -5.1% | +0.04 | -13.9% | 3.5% | -0.054 | 5% / 10% | 2% / 1% | 28 | no |
| Yield de dividendo alto | S7 | -86 | -72 | -86 | -98 | -1.0% | -0.33 | -0.8% | -1.2% | -0.029 | 21% / 10% | 0% / 1% | 26 | no |
| Payout bajo | S8 | -98 | -99 | -98 | -416 | -1.2% | -0.69 | 0.6% | -3.4% | +0.005 | 8% / 10% | 2% / 1% | 24 | no |
| Rentabilidad (FFO / activos) | S10 | -118 | -111 | -118 | -227 | -2.0% | -1.41 | -3.8% | 0.2% | -0.094 | 9% / 10% | 2% / 1% | 25 | no |
| Apalancamiento bajo | S2 | -136 | -132 | -136 | -149 | -3.1% | -3.47 | -4.4% | -1.6% | -0.109 | 6% / 10% | 1% / 1% | 29 | no |
| Rendimiento FFO alto | S6 | -167 | -151 | -166 | -304 | -1.0% | -0.67 | 1.1% | -3.4% | -0.024 | 14% / 10% | 2% / 1% | 25 | no |
| Crecimiento del dividendo | S13 | -168 | -145 | -168 | +60 | -3.8% | +2.65 | -25.4% | 8.5% | +0.392 | 6% / 10% | 1% / 1% | 12 | no |
| Rendimiento de la empresa (cap rate) | S5 | -172 | -155 | -172 | -321 | -0.7% | -0.34 | 2.0% | -3.7% | +0.004 | 15% / 10% | 2% / 1% | 25 | no |
| Calidad y barato (FFO) | S8 | -347 | -255 | -347 | -928 | -10.9% | -4.48 | -15.5% | -5.7% | — | 0% / 10% | 5% / 1% | 8 | no |

