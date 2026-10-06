# Fase 4: pre-registro de la fase 5 (cuándo entrar al sector)

Fijado el 6 de octubre de 2026, después de la literatura (`literatura.md`) y de la
exploración (`fase3_exploracion.md`), y **antes de evaluar cualquier señal**. El código que
lo ejecuta es `src/investigacion/senales.py` y `src/investigacion/fase5.py`, en el mismo
commit. Lo que se pre-registre para la fase 6 (en cuáles) irá en su propio commit, antes
de correrla, cuando estén los estados financieros de la SEC.

## Lo que se espera, escrito antes

La literatura dice que las señales de valuación del sector funcionan dentro de muestra y
fallan fuera de muestra (Ghysels et al. 2013: R² fuera de muestra del yield de −0.7%
mensual; Ling, Naranjo y Ryngaert 2000: con costos, la ganancia del timing desaparece), y
que el filtro de tendencia reduce las caídas sin subir el retorno. La fase 3 mostró que,
decidiendo solo el dinero nuevo, ni un oráculo pasa de +79 pb al año.

| # | Hipótesis | Qué se espera |
|---|---|---|
| H0 | Nula de referencia | Ninguna señal le gana a aportar siempre después de impuestos y comisiones, con la contabilidad de la fase 0. Es la expectativa más probable |
| H1 | Valuación (yield y sus spreads) | Pendiente positiva dentro de muestra; R² fuera de muestra cercano a cero o negativo; reglas que salen de los REITs cuando están caros pierden contra aportar siempre |
| H2 | Crédito (spread de default, cambio del spread, condiciones financieras, crédito bancario) | Alguna reduce la caída máxima; ninguna llega a +50 pb al año |
| H3 | Tendencia (promedio de 10 meses, momentum contra el efectivo) | Reduce la caída máxima en más de 30% con un costo de retorno pequeño; es la candidata más probable al criterio de protección |
| H4 | Bolsa del mes | Si predice, es a un mes; a 12 meses no |
| H5 | Combinaciones | No le ganan a la mejor señal sola fuera de muestra |
| H6 | Decidir solo el dinero nuevo | Ninguna señal llega a +50 pb al año (techo de la fase 3) |

## El catálogo

Once señales, cada una orientada para que más alto sea mejor para los REITs, con lo que se
conocía al cierre de cada mes (P1):

| Familia | Señal | Cálculo | Fuente |
|---|---|---|---|
| Valuación | Yield de los REITs | Yield de dividendo del índice FTSE Nareit All Equity | Chiang (2015); en contra Ghysels et al. (2013) |
| Valuación | Yield contra el Treasury | Yield − Treasury a 10 años | Nareit, Case (2017a) |
| Valuación | Yield contra la tasa real | Yield − (Treasury a 10 años − inflación de 12 meses publicada) | Variante real de Case (2017a) |
| Valuación | Yield contra bonos Baa | Yield − Baa de Moody's | Nareit, Case (2018) |
| Crédito | Spread de default | Baa − Aaa (más ancho, más prima: signo de la literatura) | Leow y Lindenthal (2024) |
| Crédito | Cambio del spread de crédito | −(cambio de 12 meses de Baa − Treasury) | Leow y Lindenthal (2024) |
| Crédito | Condiciones financieras | −NFCI de la Fed de Chicago | Leow y Lindenthal (2024) |
| Crédito | Crédito bancario a inmuebles | −(bancos que endurecen el crédito a inmuebles comerciales, SLOOS), desde 1990 | Ling, Naranjo y Scheick (2016) |
| Bolsa | Bolsa del mes | Retorno total de la bolsa de EE. UU. en el mes | Ghysels et al. (2013) |
| Tendencia | Tendencia de 10 meses | Precio del índice entre su promedio de 10 meses, menos 1 | Faber (2007); Glabadanidis (2014) |
| Tendencia | Momentum contra el efectivo | Retorno total de 12 meses − retorno del T-bill de 12 meses | Moskowitz, Ooi y Pedersen (2012) |

**Descartadas antes de correr** (no son intentos): cambio del Treasury (Nareit 2026: los
REITs subieron en 77% de los periodos de alza y 79% de baja), pendiente de la curva
(Ghysels et al.: R² fuera de muestra negativo), cambio de la tasa de la Fed (cuatro ciclos
y la última alza se sabe después), cambio del desempleo (sin respaldo), y el nivel del
spread de crédito con signo negativo (sustituido por el spread de default con el signo de
la literatura).

## Las reglas: de señal a exposición

Una sola regla para cada señal de tendencia y dos para las de nivel; no se prueban otras.

* **Tendencia**: dentro si la señal es positiva; si no, en efectivo.
* **Nivel, regla A**: fuera solo si la señal está en el quintil más desfavorable de su propia
  historia (percentil expandible menor a 20%, con al menos 60 meses).
* **Nivel, regla B**: exposición continua de 50% a 100% según su percentil expandible.
* Sin historia suficiente, dentro (como aportar siempre).

**Dos combinaciones**, definidas ahora:

* **Caro y a la baja**: fuera solo si el yield contra el Treasury está en su quintil más bajo
  **y** el precio está abajo de su promedio de 10 meses.
* **Compuesto de cuatro familias**: el promedio de los percentiles de yield contra el
  Treasury, cambio del spread de crédito, condiciones financieras y tendencia; exposición
  continua de 50% a 100% según su percentil.

Son 9 × 2 + 2 + 2 = **22 reglas**. Todas quedan en la bitácora.

## Qué se mide (por regla)

Con el simulador de la fase 2 (aportación de 1,000 dólares al mes, impuestos del SIC,
comisión de 0.25%):

* TIR contra aportar siempre, **decidiendo solo el dinero nuevo** y **rebalanceando**.
* Contra la **mezcla fija** con la misma exposición promedio (P8).
* Con **un mes de retraso** y con **el doble de comisión**.
* **Caída máxima** y exposición promedio.
* **R² fuera de muestra** y **Clark-West** a 1, 3 y 12 meses, con la restricción de signo de
  Campbell y Thompson (si la pendiente estimada sale con el signo contrario, el pronóstico es
  el promedio histórico), estimados con ventana creciente y 120 meses mínimos.
* Por era: 1972-1992 y 1993-2015 (la literatura recomienda partir en 1993).
* **Apuestas efectivas** (P7).

## Cuáles pasan a validación

Una regla pasa si, en desarrollo (1972-2015), cumple **todo**:

1. Le gana a aportar siempre rebalanceando.
2. Le gana a la mezcla fija con su misma exposición.
3. Sigue ganando con un mes de retraso y con el doble de comisión.
4. Gana en las dos eras por separado.
5. Predice a 12 meses: R² fuera de muestra positivo o Clark-West con p < 0.10.

Pasan **a lo más tres**, las de mayor mejora rebalanceando. Sobre las 22 se calculan la
**PBO** (16 bloques) y el **Sharpe deflactado** de la mejor con 22 intentos. La validación
(2016 en adelante) se abre **una vez**, solo para las que pasaron, con los pronósticos
estimados con toda la historia anterior. Si ninguna pasa, no se abre la validación y la fase
5 termina en RECHAZADO para el timing del sector con estas señales.

## Para la prueba final (fase 8), fijado desde ahora

Las señales que se pueden calcular en otros mercados son las de **valuación contra la tasa
larga local**, la **tendencia** y el **momentum**; las de crédito y la bolsa de EE. UU. se
aplican sin cambios como indicadores de riesgo global. La inflación local no se bajó, así
que el yield contra la tasa real no es portable, y la encuesta de crédito tampoco. Un
modelo que dependa solo de señales no portables no puede pasar la prueba final: a lo más,
INCONCLUSO.
