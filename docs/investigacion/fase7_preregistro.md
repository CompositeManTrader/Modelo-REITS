# Fases 7 y 8: pre-registro de la escalera de modelos y de la prueba final

Fijado el 6 de octubre de 2026, **después** de ver los resultados de la fase 5 en desarrollo
y **antes** de correr la escalera o de abrir cualquier dato de validación o de la prueba
final. El código es `src/investigacion/fase7.py`, en el mismo commit; la prueba 68 verifica
con datos sintéticos que ningún pronóstico usa un retorno que todavía no terminaba.

## Fase 7: la escalera

**Qué se pronostica.** El retorno de los REITs menos el del efectivo en los 12 meses
siguientes (FTSE Nareit All Equity contra el T-bill).

**Con qué.** Los percentiles expandibles (al menos 60 meses de historia) de las ocho señales
**portables** de la fase 5, orientadas para que más alto sea mejor: yield, yield contra la
tasa larga, tendencia de 10 meses, momentum contra el efectivo, spread de default, cambio
del spread de crédito, condiciones financieras (NFCI) y la bolsa del mes. Quedan fuera las
que no se pueden calcular en otros mercados (yield contra la tasa real y contra Baa,
encuesta de crédito de la Fed): así lo que salga se puede probar en la fase 8. Usar
percentiles, y no niveles, hace que un mismo modelo se pueda aplicar a otro mercado.

**Cómo se estima.** Ventana creciente; se re-estima cada 12 meses con los pares (señal,
retorno de 12 meses) cuyo retorno ya terminó; al menos 120 pares para estimar.

**Los cinco peldaños**, del más simple al más complejo:

| # | Peldaño | Qué hace |
|---|---|---|
| 1 | Mejor señal sola | Cada año escoge, con el pasado, la señal de mayor correlación de rangos con el retorno siguiente; regresión simple con pendiente no negativa |
| 2 | Compuesto | El promedio de las ocho señales; regresión simple (si la pendiente sale negativa, el promedio histórico) |
| 3 | Ridge | Regresión con las ocho; la penalización (0.1, 1, 10, 100 o 1000) se escoge por validación cruzada temporal dentro del pasado, con un hueco de 12 meses |
| 4 | Árboles | Gradient boosting con hiperparámetros fijos: profundidad 2, 150 árboles, tasa 0.03, submuestreo 0.7, semilla 7 |
| 5 | Regímenes | Markov de dos estados sobre el retorno en exceso mensual (media y varianza cambian), como Bianchi y Guidolin (2014); régimen malo = el de menor media; probabilidad **filtrada** (solo con el pasado) |

**De pronóstico a exposición, igual para todos.** Peldaños 1 a 4: dentro si el pronóstico
del retorno en exceso de 12 meses es positivo; si es negativo, en efectivo. Peldaño 5: fuera
si la probabilidad filtrada del régimen malo pasa de 50%. Antes del primer pronóstico,
dentro.

**La escalera.** Un peldaño se queda solo si su mejora de TIR rebalanceando contra aportar
siempre es mayor que la del último que se quedó (el punto de partida es aportar siempre,
mejora 0). El candidato es el último que se quedó. Los cinco peldaños se anotan en la
bitácora como intentos.

**Pasa a validación** si el candidato cumple el mismo filtro de la fase 5 (gana
rebalanceando y contra la mezcla fija, con un mes de retraso y con doble comisión, en las dos
eras, y predice a 12 meses: R² fuera de muestra del propio modelo positivo o Clark-West con
p < 0.10; para el peldaño 5, que pronostica a un mes, se usa su R² a un mes). **Pasa de la
validación a la prueba final** si en 2016 en adelante cumple el criterio 1 de la fase 0
(+50 pb, o 30% menos de caída con costo de a lo más 25 pb).

### Lo que se espera

| # | Hipótesis |
|---|---|
| H7.1 | Ningún peldaño llega a +50 pb al año en desarrollo |
| H7.2 | Ridge y árboles no le ganan a los peldaños simples fuera de muestra |
| H7.3 | Regímenes reduce la caída máxima, pero cuesta retorno después de impuestos |
| H7.4 | El pronóstico casi siempre es positivo (el retorno esperado de los REITs le gana al efectivo), así que los peldaños 1 a 4 casi nunca salen |

## Fase 8: la prueba final

Se abre **una sola vez**, con los modelos congelados en la bitácora:

1. **El candidato de la fase 7**, si pasó la validación. Se re-estima una última vez con
   todos los datos de EE. UU. (hasta el final de la validación), se congela y se aplica sin
   cambios a cada mercado con sus propias señales: las locales (yield, yield contra la tasa
   larga local, tendencia y momentum contra el efectivo local) y las globales de EE. UU.
   (spread de default, cambio del spread, NFCI y bolsa de EE. UU.), todas como percentiles
   dentro de la historia de cada mercado. Si el candidato es el de regímenes, se prueba el
   **procedimiento**: se estima dentro de cada mercado con la misma ventana creciente.
2. **Protección por tendencia** (dentro si el precio está arriba de su promedio de 10 meses).
   **Se escogió después de ver la fase 5 en desarrollo**, a petición del inversionista; se
   declara así en todo informe. No tiene parámetros que estimar. Se evalúa también en la
   validación de EE. UU. (2016 en adelante), como evidencia adicional.

**Cada mercado**: su serie principal (`mercados.py`: el ETF local con al menos 120 meses o
la canasta de pesos iguales), su tasa corta como efectivo y su tasa larga, en moneda local,
con la misma contabilidad de la fase 0 (aportación mensual, 20% al dividendo y a los
intereses, 10% a la ganancia, 0.25% de comisión). Cuenta el mercado si tiene al menos 60
meses después de que sus señales tienen historia.

**Veredicto de cada modelo** (criterios de la fase 0, sin moverlos): APROBADO si cumple el
criterio 1 en el conjunto (promedio simple de los mercados) **y** en al menos dos de cada
tres mercados, sigue cumpliéndolo con un mes de retraso y con el doble de comisión, y suma
al menos 100 apuestas efectivas. Para la protección por tendencia, el criterio 1 que aplica
es el de protección (30% menos de caída máxima con costo de a lo más 25 pb al año). El
Sharpe deflactado y la PBO son los de su familia en desarrollo. Si no: INCONCLUSO si le gana
a aportar siempre en desarrollo y validación; si no, RECHAZADO.
