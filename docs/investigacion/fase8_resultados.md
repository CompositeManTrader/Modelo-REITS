# Fase 8: la prueba final. Resultados

Modelo congelado en la bitácora antes de abrir nada: **protección por tendencia** (dentro si el precio está arriba de su promedio de 10 meses; si no, en efectivo), escogido después de ver la fase 5 en desarrollo, como declara `fase7_preregistro.md`. La escalera de la fase 7 no dejó candidato. Cada mercado en su moneda y con su tasa corta como efectivo; misma contabilidad que la fase 0 (aportación mensual, impuestos del SIC, comisiones). Generado por `python scripts/investigacion.py fase8`.

## Veredicto: **RECHAZADO**

El criterio de protección pide al menos 30% menos de caída máxima con un costo de a lo más 25 pb al año. En el conjunto de los 8 mercados la caída bajó 32% en promedio, pero la TIR quedó -127 pb al año contra aportar siempre; solo 12% de los mercados cumplió el criterio, y con un mes de retraso, 0%. En la validación de EE. UU. (2016 en adelante) la caída bajó de -32% a -20%, a un costo de -490 pb al año. **La tendencia sí reduce las caídas, pero fuera de la muestra en la que se escogió cuesta mucho más de lo que el criterio tolera**: sale tarde, después de la caída, y vuelve tarde, después del rebote; y cada salida paga impuesto sobre la ganancia.


| Mercado | Periodo | TIR aportando siempre | Tendencia contra aportar (pb/año) | Caída aportando siempre | Caída con tendencia | Reducción de caída | Exposición | Con un mes de retraso (pb) | Cumple protección |
|---|---|---|---|---|---|---|---|---|---|
| EE. UU. (validación, 2016 en adelante) | 01-2016 a 09-2026 | 4.39% | -490 | -32% | -20% | 37% | 58% | -371 | — |
| Japón (etf: 1343.T) | 06-2009 a 07-2026 | 5.36% | -67 | -29% | -22% | 25% | 58% | -269 | no |
| Australia (etf: SLF.AX) | 10-2008 a 08-2026 | 5.64% | -345 | -36% | -24% | 33% | 57% | -494 | no |
| Singapur (canasta de 10) | 07-2006 a 09-2026 | 6.22% | -307 | -65% | -30% | 53% | 57% | -415 | no |
| Hong Kong (canasta de 7) | 11-2000 a 09-2026 | 8.14% | +165 | -63% | -51% | 20% | 57% | -127 | no |
| Reino Unido (etf: IUKP.L) | 10-2009 a 01-2026 | -1.28% | +347 | -45% | -19% | 58% | 58% | -13 | sí |
| Europa continental (etf: IPRP.AS) | 10-2008 a 01-2026 | 2.68% | -271 | -47% | -35% | 26% | 63% | -244 | no |
| Canadá (etf: XRE.TO) | 07-2003 a 08-2026 | 4.75% | -195 | -53% | -25% | 53% | 65% | -289 | no |
| FIBRAs (México) (canasta de 11) | 01-2012 a 08-2026 | 5.85% | -343 | -28% | -31% | -13% | 59% | -134 | no |

Apuestas efectivas (cambios de postura sumados): 312. Las canastas de Singapur, Hong Kong y las FIBRAs son de los REITs que cotizan hoy (sesgo de supervivencia, declarado en la fase 0).
