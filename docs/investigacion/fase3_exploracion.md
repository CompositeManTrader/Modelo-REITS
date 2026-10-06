# Fase 3: exploración de la muestra de desarrollo

FTSE Nareit All Equity REITs, 01-1972 a 12-2015 (528 meses), contra el T-bill a 3 meses. Nada de esto mira 2016 en adelante. Generado por `python scripts/investigacion.py exploracion`.

## 1. De dónde salió el retorno

| Periodo | REITs | del ingreso | del precio | Efectivo | Inflación | Bolsa (EE. UU.) | Volatilidad REITs | Correlación con bolsa |
|---|---|---|---|---|---|---|---|---|
| completo | 12.0% | 7.2% | 4.2% | 5.0% | 4.1% | 10.4% | 17.1% | 0.59 |
| 1972-1992 | 13.0% | 9.0% | 3.4% | 7.7% | 6.1% | 11.7% | 14.1% | 0.68 |
| 1993-2015 | 11.1% | 5.6% | 5.1% | 2.6% | 2.3% | 9.2% | 19.4% | 0.55 |

El ingreso (el dividendo) explica más de la mitad del retorno; el precio, el resto. El T-bill de 1972-1992 rindió 7.7% al año: en esa era el efectivo sí era una alternativa seria.

## 2. Las caídas de 20% o más

| Máximo | Mínimo | Caída | Meses cayendo | Meses para recuperar |
|---|---|---|---|---|
| 09-1972 | 12-1974 | -37% | 27 | 22 |
| 08-1989 | 10-1990 | -24% | 14 | 6 |
| 12-1997 | 11-1999 | -24% | 23 | 14 |
| 01-2007 | 02-2009 | -68% | 25 | 41 |

4 caídas en 44 años. **Cualquier regla para esquivarlas se apoya en muy pocos eventos**: con tres o cuatro casos es fácil encontrar algo que «los hubiera visto venir» por casualidad. Por eso la prueba final usa mercados que no se han visto.

### Qué decía cada indicador en el máximo y seis meses antes

Percentil contra su propia historia hasta ese día (0% = el valor más bajo visto hasta entonces). La caída de 1972 no tiene historia previa suficiente.

| Indicador | 08-1989 (máximo) | 08-1989 (6 meses antes) | 12-1997 (máximo) | 12-1997 (6 meses antes) | 01-2007 (máximo) | 01-2007 (6 meses antes) |
|---|---|---|---|---|---|---|
| yield reit | 39% | 73% | 0% | 3% | 0% | 0% |
| treasury 10a | 43% | 63% | 3% | 13% | 14% | 14% |
| spread 10a | 53% | 43% | 43% | 41% | 18% | 24% |
| baa | 31% | 54% | 1% | 13% | 4% | 8% |
| spread baa | 61% | 56% | 50% | 45% | 23% | 24% |
| inflacion 12m | 44% | 37% | 4% | 5% | 11% | 56% |
| tasa real | 50% | 65% | 54% | 62% | 45% | 19% |
| spread credito | 40% | 24% | 25% | 17% | 26% | 27% |
| curva | 32% | 28% | 27% | 39% | 11% | 16% |
| fed cambio 12m | 63% | 75% | 56% | 57% | 68% | 79% |
| desempleo cambio 12m | 55% | 52% | 19% | 29% | 28% | 36% |
| nfci | 45% | 52% | 30% | 24% | 24% | 35% |
| credito inmuebles | — | — | 0% | 19% | 60% | 40% |
| tendencia 10m | 67% | 29% | 83% | 79% | 99% | 77% |
| momentum 12m | 40% | 26% | 63% | 89% | 92% | 46% |

Lo que se ve: en 1997 y 2007 el yield de los REITs estaba en el mínimo de su historia (caros) y la tendencia y el momentum, arriba (por definición, cerca de un máximo). En 1989 no había ninguna alarma de valuación. Tres casos no alcanzan para concluir nada.

### Qué tan seguido sonaría cada alarma

| Condición | Meses | Conteo |
|---|---|---|
| yield del REIT abajo del Treasury a 10 años | 40% | 197 de 492 |
| yield en el 10% más bajo de su propia historia | 35% | 170 de 492 |
| precio abajo de su promedio de 10 meses | 30% | 146 de 492 |
| retorno de los últimos 12 meses negativo | 17% | 84 de 492 |

El yield de los REITs estuvo abajo del Treasury 40% de los meses —casi toda la década de 1980, cuando las tasas eran altísimas y los REITs rindieron bien—. Una alarma que suena tanto no puede ser una regla de salida tal cual; tendría que medirse contra su propia historia.

## 3. El techo teórico

### ¿Qué tan seguido le ganó el efectivo a los REITs?

| Meses hacia adelante | El efectivo ganó | Ventanas independientes | REITs (mediana anual) | Efectivo (mediana anual) |
|---|---|---|---|---|
| 1 | 41% | 527 | 16.5% | 5.1% |
| 3 | 38% | 175 | 15.5% | 5.1% |
| 12 | 27% | 43 | 15.7% | 5.2% |
| 36 | 22% | 13 | 14.3% | 5.1% |
| 60 | 16% | 7 | 13.2% | 5.1% |

### Cuánto valdría conocer el futuro

Aportando 1,000 dólares al mes, con impuestos de residente mexicano vía SIC y comisiones. «Nunca vende» solo decide a dónde va el dinero nuevo; «rebalancea» puede vender y volver a comprar (pagando 10% sobre la ganancia).

| Regla | Modo | TIR | Contra aportar siempre (pb/año) | Caída máxima | Exposición | Cambios |
|---|---|---|---|---|---|---|
| aportar siempre | nunca vende | 10.65% | +0 | -69% | 100% | 0 |
| oráculo del mes siguiente | nunca vende | 10.95% | +29 | -68% | 99% | 228 |
| oráculo del mes siguiente | rebalancea | 27.94% | +1,729 | 0% | 59% | 228 |
| oráculo de los 12 meses siguientes | nunca vende | 11.24% | +58 | -66% | 95% | 32 |
| oráculo de los 12 meses siguientes | rebalancea | 14.45% | +379 | -35% | 73% | 32 |
| fuera en cada caída de 20% o más (del máximo al mínimo) | nunca vende | 11.44% | +79 | -65% | 96% | 8 |
| fuera en cada caída de 20% o más (del máximo al mínimo) | rebalancea | 16.54% | +589 | -18% | 83% | 8 |
| anti-oráculo de 12 meses | nunca vende | 8.77% | -188 | -69% | 88% | 32 |
| anti-oráculo de 12 meses | rebalancea | -1.92% | -1,258 | -64% | 27% | 32 |

**La conclusión más importante de esta fase.** Si solo se decide a dónde va el dinero nuevo, ni un oráculo perfecto agrega más de +79 pb al año: la riqueza ya invertida pesa mucho más que la aportación de un mes. Una regla real captura una fracción del oráculo, así que por esa vía no se llega al criterio de +50 pb. **Si existe valor en saber cuándo entrar, está en poder salir**: vender antes de una caída grande y volver a entrar. Con esa libertad, el oráculo de 12 meses agrega cientos de puntos base y esquivar las cuatro caídas reduce la caída máxima de −69% a −18%, aun pagando impuestos. La fase 5 se concentra ahí, sin perder de vista que son muy pocas caídas para aprender de ellas.
