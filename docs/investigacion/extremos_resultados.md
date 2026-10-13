# Los extremos de valuación. Resultados (exploratorio)

Pre-registro: `extremos_preregistro.md` (commit anterior a esta corrida). Se decidió después de ver todas las fases: nada de lo que sale aquí se adopta como regla. Generado por `python scripts/investigacion.py extremos`.

## Veredicto

**2 de 56 combinaciones** cumplen la regla de lectura pre-registrada (mismo signo y |t| ≥ 2 en desarrollo y validación; en las reglas, +50 pb y positiva con un mes de retraso en las dos). Las pistas, que solo una prueba nueva con datos nuevos podría confirmar:

* yield contra bonos Baa · barato 5% · 12 meses (sector): 41.8% (t +2.31) en desarrollo y 32.2% (t +11.34) en validación; detrás hay 6 meses en 2 episodios en desarrollo y 5 meses en 1 episodio(s) en validación
* yield contra el Treasury · barato 5% · 12 meses (sector): 26.9% (t +2.89) en desarrollo y 29.7% (t +9.50) en validación; detrás hay 19 meses en 3 episodios en desarrollo y 5 meses en 1 episodio(s) en validación

Cómo leerlas: una t de Newey-West con uno o dos episodios no mide la incertidumbre real —cada episodio es una sola crisis que se ve muchos meses seguidos—. Lo que sí dicen es que, en las pocas veces en que los REITs llegaron a su 5% más barato contra los bonos (1998-99, 2001-03 y 2008-09 en desarrollo, y uno después de 2016), los 12 meses siguientes fueron muy buenos. Eso no se puede convertir en una regla de timing para quien aporta siempre, porque ya está 100% invertido: a lo más dice que esos son los peores momentos para dejar de aportar y los mejores para meter dinero extra.


## Dónde está hoy

Percentil contra la propia historia (alto = barato).

| Señal | Fecha | Percentil | Corte |
|---|---|---|---|
| yield de los REITs | 09-2026 | 24% | centro |
| yield contra el Treasury | 09-2026 | 12% | centro |
| yield contra la tasa real | 09-2026 | 15% | centro |
| yield contra bonos Baa | 09-2026 | 23% | centro |
| NNN · consenso | 09-2026 | 60% | centro |
| NNN · prima_treasury | 09-2026 | 40% | centro |
| O · consenso | 09-2026 | 88% | centro |
| O · prima_treasury | 09-2026 | 41% | centro |
| WPC · consenso | 09-2026 | 28% | centro |
| WPC · prima_treasury | 09-2026 | 1% | caro 5% |

## 1. El sector

Retorno anualizado de los 60 meses siguientes, antes de impuestos. «Diferencia» es el exceso sobre el efectivo en el corte menos el del resto de los meses, con su t de Newey-West.

**1972-2015**

| Señal | Corte | Meses | Frecuencia | Episodios | REITs | Efectivo | Ganó el efectivo | Diferencia (pb) | t |
|---|---|---|---|---|---|---|---|---|---|
| yield de los REITs | caro 5% | 91 | 22% | 4 | 3.4% | 2.6% | 44% | -603 | -1.78 |
| yield de los REITs | caro 10% | 118 | 29% | 5 | 5.2% | 2.7% | 36% | -555 | -1.93 |
| yield de los REITs | centro | 284 | 69% | 4 | 15.3% | 5.7% | 9% | +442 | +1.38 |
| yield de los REITs | barato 10% | 7 | 2% | 2 | 20.4% | 0.1% | 0% | +1,203 | +2.66 |
| yield de los REITs | barato 5% | 1 | 0% | 1 | 17.3% | 4.5% | 0% | — | — |
| yield contra el Treasury | caro 5% | 39 | 10% | 3 | 20.8% | 11.3% | 0% | +223 | +1.45 |
| yield contra el Treasury | caro 10% | 50 | 12% | 2 | 21.1% | 11.2% | 0% | +254 | +1.63 |
| yield contra el Treasury | centro | 320 | 78% | 3 | 10.7% | 4.7% | 21% | -652 | -3.09 |
| yield contra el Treasury | barato 10% | 39 | 10% | 4 | 18.7% | 2.9% | 0% | +971 | +5.26 |
| yield contra el Treasury | barato 5% | 19 | 5% | 3 | 19.6% | 2.8% | 0% | +1,128 | +5.05 |
| yield contra la tasa real | caro 5% | 35 | 9% | 2 | 16.9% | 7.6% | 0% | +447 | +2.26 |
| yield contra la tasa real | caro 10% | 52 | 13% | 3 | 16.3% | 7.5% | 10% | +267 | +1.82 |
| yield contra la tasa real | centro | 342 | 86% | 2 | 11.4% | 4.5% | 18% | -316 | -2.20 |
| yield contra la tasa real | barato 10% | 3 | 1% | 1 | 16.9% | 0.1% | 0% | +981 | +6.57 |
| yield contra la tasa real | barato 5% | 0 | 0% | 0 | — | — | — | — | — |
| yield contra bonos Baa | caro 5% | 31 | 8% | 1 | 20.7% | 10.9% | 0% | +282 | +1.61 |
| yield contra bonos Baa | caro 10% | 40 | 10% | 1 | 21.1% | 10.9% | 0% | +347 | +1.89 |
| yield contra bonos Baa | centro | 343 | 84% | 2 | 11.4% | 4.6% | 20% | -536 | -2.90 |
| yield contra bonos Baa | barato 10% | 26 | 6% | 5 | 17.1% | 3.1% | 0% | +703 | +2.86 |
| yield contra bonos Baa | barato 5% | 6 | 1% | 2 | 22.1% | 0.1% | 0% | +1,486 | +4.86 |


**2016 en adelante**

| Señal | Corte | Meses | Frecuencia | Episodios | REITs | Efectivo | Ganó el efectivo | Diferencia (pb) | t |
|---|---|---|---|---|---|---|---|---|---|
| yield de los REITs | caro 5% | 8 | 12% | 1 | 3.8% | 3.6% | 38% | -441 | -4.48 |
| yield de los REITs | caro 10% | 20 | 29% | 2 | 4.7% | 3.2% | 15% | -274 | -3.99 |
| yield de los REITs | centro | 49 | 71% | 1 | 6.7% | 1.4% | 0% | +274 | +3.99 |
| yield de los REITs | barato 10% | 0 | 0% | 0 | — | — | — | — | — |
| yield de los REITs | barato 5% | 0 | 0% | 0 | — | — | — | — | — |
| yield contra el Treasury | caro 5% | 0 | 0% | 0 | — | — | — | — | — |
| yield contra el Treasury | caro 10% | 0 | 0% | 0 | — | — | — | — | — |
| yield contra el Treasury | centro | 58 | 84% | 1 | 5.1% | 1.5% | 5% | +43 | +0.34 |
| yield contra el Treasury | barato 10% | 11 | 16% | 1 | 6.7% | 2.9% | 0% | -43 | -0.34 |
| yield contra el Treasury | barato 5% | 5 | 7% | 1 | 7.2% | 2.7% | 0% | +42 | +0.35 |
| yield contra la tasa real | caro 5% | 0 | 0% | 0 | — | — | — | — | — |
| yield contra la tasa real | caro 10% | 0 | 0% | 0 | — | — | — | — | — |
| yield contra la tasa real | centro | 69 | 100% | 1 | 5.6% | 1.8% | 4% | — | — |
| yield contra la tasa real | barato 10% | 0 | 0% | 0 | — | — | — | — | — |
| yield contra la tasa real | barato 5% | 0 | 0% | 0 | — | — | — | — | — |
| yield contra bonos Baa | caro 5% | 0 | 0% | 0 | — | — | — | — | — |
| yield contra bonos Baa | caro 10% | 0 | 0% | 0 | — | — | — | — | — |
| yield contra bonos Baa | centro | 54 | 78% | 2 | 4.9% | 1.5% | 6% | +29 | +0.25 |
| yield contra bonos Baa | barato 10% | 15 | 22% | 2 | 6.7% | 2.9% | 0% | -29 | -0.25 |
| yield contra bonos Baa | barato 5% | 5 | 7% | 1 | 7.0% | 3.0% | 0% | -2 | -0.01 |


A 12 meses, solo los extremos:

| Señal | Corte | Muestra | Meses | REITs | Ganó el efectivo | Diferencia (pb) | t |
|---|---|---|---|---|---|---|---|
| yield de los REITs | caro 5% | 1972-2015 | 121 | 12.4% | 25% | -19 | -0.04 |
| yield de los REITs | caro 10% | 1972-2015 | 165 | 12.4% | 27% | -316 | -0.70 |
| yield de los REITs | barato 10% | 1972-2015 | 7 | 39.0% | 0% | +4,298 | +2.69 |
| yield de los REITs | barato 5% | 1972-2015 | 1 | 36.0% | 0% | — | — |
| yield contra el Treasury | caro 5% | 1972-2015 | 39 | 17.4% | 38% | -507 | -0.73 |
| yield contra el Treasury | caro 10% | 1972-2015 | 50 | 18.0% | 30% | -251 | -0.40 |
| yield contra el Treasury | barato 10% | 1972-2015 | 39 | 22.9% | 23% | +1,392 | +1.59 |
| yield contra el Treasury | barato 5% | 1972-2015 | 19 | 33.9% | 16% | +2,693 | +2.89 |
| yield contra la tasa real | caro 5% | 1972-2015 | 35 | 27.9% | 14% | +940 | +1.71 |
| yield contra la tasa real | caro 10% | 1972-2015 | 54 | 24.8% | 22% | +444 | +0.79 |
| yield contra la tasa real | barato 10% | 1972-2015 | 3 | 28.0% | 33% | +1,264 | +3.64 |
| yield contra la tasa real | barato 5% | 1972-2015 | 0 | — | — | — | — |
| yield contra bonos Baa | caro 5% | 1972-2015 | 31 | 14.2% | 45% | -906 | -1.45 |
| yield contra bonos Baa | caro 10% | 1972-2015 | 40 | 17.6% | 38% | -499 | -0.83 |
| yield contra bonos Baa | barato 10% | 1972-2015 | 26 | 25.5% | 31% | +1,246 | +1.25 |
| yield contra bonos Baa | barato 5% | 1972-2015 | 6 | 42.9% | 17% | +4,178 | +2.31 |
| yield de los REITs | caro 5% | 2016 en adelante | 18 | -10.2% | 78% | -1,555 | -3.03 |
| yield de los REITs | caro 10% | 2016 en adelante | 31 | -6.8% | 74% | -1,155 | -2.01 |
| yield de los REITs | barato 10% | 2016 en adelante | 0 | — | — | — | — |
| yield de los REITs | barato 5% | 2016 en adelante | 0 | — | — | — | — |
| yield contra el Treasury | caro 5% | 2016 en adelante | 0 | — | — | — | — |
| yield contra el Treasury | caro 10% | 2016 en adelante | 0 | — | — | — | — |
| yield contra el Treasury | barato 10% | 2016 en adelante | 11 | 33.4% | 0% | +3,047 | +9.70 |
| yield contra el Treasury | barato 5% | 2016 en adelante | 5 | 33.4% | 0% | +2,970 | +9.50 |
| yield contra la tasa real | caro 5% | 2016 en adelante | 0 | — | — | — | — |
| yield contra la tasa real | caro 10% | 2016 en adelante | 0 | — | — | — | — |
| yield contra la tasa real | barato 10% | 2016 en adelante | 10 | -11.2% | 100% | -2,211 | -6.78 |
| yield contra la tasa real | barato 5% | 2016 en adelante | 0 | — | — | — | — |
| yield contra bonos Baa | caro 5% | 2016 en adelante | 0 | — | — | — | — |
| yield contra bonos Baa | caro 10% | 2016 en adelante | 0 | — | — | — | — |
| yield contra bonos Baa | barato 10% | 2016 en adelante | 15 | 32.2% | 0% | +2,774 | +6.05 |
| yield contra bonos Baa | barato 5% | 2016 en adelante | 5 | 34.2% | 0% | +3,217 | +11.34 |

## Las reglas: salir solo en el extremo caro

Mejora de TIR contra aportar siempre, rebalanceando, en pb al año. El criterio de la investigación es +50 pb.

| Señal | Regla | Impuestos | 1972-2015 (pb) | Con retraso (pb) | Tiempo fuera | 2016+ (pb) | Con retraso (pb) | Tiempo fuera |
|---|---|---|---|---|---|---|---|---|
| yield de los REITs | fuera en el 5% más caro | SIC | -295 | -383 | 24% | +140 | -6 | 14% |
| yield de los REITs | fuera en el 5% más caro | Broker 35% | -251 | -344 | 24% | +161 | +16 | 14% |
| yield de los REITs | fuera en el 10% más caro | SIC | -510 | -316 | 32% | +59 | +247 | 25% |
| yield de los REITs | fuera en el 10% más caro | Broker 35% | -464 | -267 | 32% | +96 | +276 | 25% |
| yield contra el Treasury | fuera en el 5% más caro | SIC | +5 | -7 | 7% | 0 | 0 | 0% |
| yield contra el Treasury | fuera en el 5% más caro | Broker 35% | +12 | +6 | 7% | 0 | 0 | 0% |
| yield contra el Treasury | fuera en el 10% más caro | SIC | -10 | -29 | 9% | 0 | 0 | 0% |
| yield contra el Treasury | fuera en el 10% más caro | Broker 35% | +4 | -14 | 9% | 0 | 0 | 0% |
| yield contra la tasa real | fuera en el 5% más caro | SIC | -88 | -98 | 7% | 0 | 0 | 0% |
| yield contra la tasa real | fuera en el 5% más caro | Broker 35% | -80 | -87 | 7% | 0 | 0 | 0% |
| yield contra la tasa real | fuera en el 10% más caro | SIC | -141 | -125 | 11% | 0 | 0 | 0% |
| yield contra la tasa real | fuera en el 10% más caro | Broker 35% | -119 | -102 | 11% | 0 | 0 | 0% |
| yield contra bonos Baa | fuera en el 5% más caro | SIC | +19 | +18 | 6% | 0 | 0 | 0% |
| yield contra bonos Baa | fuera en el 5% más caro | Broker 35% | +29 | +27 | 6% | 0 | 0 | 0% |
| yield contra bonos Baa | fuera en el 10% más caro | SIC | -5 | +10 | 8% | 0 | 0 | 0% |
| yield contra bonos Baa | fuera en el 10% más caro | Broker 35% | +4 | +18 | 8% | 0 | 0 | 0% |

## 2. O, NNN y WPC

Retorno total anualizado de los 5 años siguientes, neto del broker al 35% (44% al dividendo), en fines de trimestre. Las ventanas independientes son trimestres entre 20.

**Señal: consenso de los siete métodos**

| Emisores | Corte | Trimestres | Ventanas | Mediana | p10 a p90 | Efectivo |
|---|---|---|---|---|---|---|
| juntos | caro 5% | 6 | 0.3 | 6.6% | -0.9% a 11.9% | 0.8% |
| juntos | caro 10% | 24 | 1.2 | 4.7% | -0.7% a 11.0% | 0.8% |
| juntos | centro | 189 | 9.4 | 9.3% | 1.5% a 16.6% | 0.7% |
| juntos | barato 10% | 13 | 0.7 | 19.4% | 8.6% a 25.3% | 1.5% |
| juntos | barato 5% | 6 | 0.3 | 19.9% | 11.9% a 25.0% | 1.7% |
| NNN | caro 5% | 5 | 0.2 | 6.3% | -1.2% a 11.9% | 0.8% |
| NNN | caro 10% | 17 | 0.8 | 4.9% | -0.7% a 9.1% | 0.8% |
| NNN | centro | 68 | 3.4 | 9.7% | 1.8% a 16.6% | 0.7% |
| NNN | barato 10% | 5 | 0.2 | 18.2% | 17.5% a 20.8% | 1.7% |
| NNN | barato 5% | 3 | 0.1 | 18.2% | 17.5% a 21.0% | 1.8% |
| O | caro 5% | 1 | 0.1 | 8.6% | 8.6% a 8.6% | 0.8% |
| O | caro 10% | 5 | 0.2 | 8.6% | -0.1% a 13.9% | 0.8% |
| O | centro | 66 | 3.3 | 8.8% | 1.6% a 14.9% | 0.7% |
| O | barato 10% | 3 | 0.1 | 16.7% | 8.6% a 19.6% | 0.1% |
| O | barato 5% | 1 | 0.1 | 6.6% | 6.6% a 6.6% | 1.7% |
| WPC | caro 5% | 0 | 0.0 | — | — a — | — |
| WPC | caro 10% | 2 | 0.1 | 2.6% | 1.9% a 3.3% | 0.3% |
| WPC | centro | 55 | 2.8 | 8.9% | 0.9% a 19.4% | 0.7% |
| WPC | barato 10% | 5 | 0.2 | 24.3% | 12.3% a 26.0% | 0.1% |
| WPC | barato 5% | 2 | 0.1 | 25.0% | 24.5% a 25.5% | 0.1% |


**Señal: prima sobre el Treasury**

| Emisores | Corte | Trimestres | Ventanas | Mediana | p10 a p90 | Efectivo |
|---|---|---|---|---|---|---|
| juntos | caro 5% | 8 | 0.4 | 3.8% | 1.0% a 9.3% | 0.6% |
| juntos | caro 10% | 16 | 0.8 | 5.5% | 0.3% a 11.0% | 0.9% |
| juntos | centro | 215 | 10.8 | 8.6% | 0.3% a 16.2% | 0.7% |
| juntos | barato 10% | 30 | 1.5 | 16.6% | 5.5% a 23.8% | 1.6% |
| juntos | barato 5% | 23 | 1.1 | 17.7% | 5.9% a 24.2% | 1.5% |
| NNN | caro 5% | 0 | 0.0 | — | — a — | — |
| NNN | caro 10% | 1 | 0.1 | 6.3% | 6.3% a 6.3% | 1.3% |
| NNN | centro | 84 | 4.2 | 7.7% | 0.4% a 14.9% | 0.9% |
| NNN | barato 10% | 17 | 0.8 | 17.3% | 7.3% a 20.5% | 1.7% |
| NNN | barato 5% | 12 | 0.6 | 17.9% | 9.1% a 20.6% | 1.7% |
| O | caro 5% | 2 | 0.1 | 6.4% | 4.6% a 8.2% | 1.3% |
| O | caro 10% | 8 | 0.4 | 9.4% | 0.0% a 11.2% | 1.3% |
| O | centro | 73 | 3.6 | 10.2% | 1.8% a 16.6% | 0.7% |
| O | barato 10% | 5 | 0.2 | 13.5% | 4.3% a 22.3% | 1.6% |
| O | barato 5% | 4 | 0.2 | 16.9% | 8.6% a 22.7% | 0.8% |
| WPC | caro 5% | 6 | 0.3 | 3.4% | 0.5% a 7.8% | 0.4% |
| WPC | caro 10% | 7 | 0.3 | 3.4% | 0.7% a 8.1% | 0.4% |
| WPC | centro | 58 | 2.9 | 8.0% | -0.7% a 19.0% | 0.7% |
| WPC | barato 10% | 8 | 0.4 | 15.3% | 3.3% a 25.8% | 0.8% |
| WPC | barato 5% | 7 | 0.3 | 8.6% | 3.2% a 25.9% | 1.4% |


Las dos mitades (consenso, los tres juntos):

| Mitad | Corte | Trimestres | Mediana |
|---|---|---|---|
| primera mitad | caro 5% | 3 | 6.9% |
| primera mitad | caro 10% | 15 | 6.3% |
| primera mitad | centro | 87 | 12.2% |
| primera mitad | barato 10% | 11 | 20.3% |
| primera mitad | barato 5% | 5 | 21.7% |
| segunda mitad | caro 5% | 3 | 0.6% |
| segunda mitad | caro 10% | 9 | 0.6% |
| segunda mitad | centro | 102 | 5.5% |
| segunda mitad | barato 10% | 2 | 6.0% |
| segunda mitad | barato 5% | 1 | 6.6% |

## 3. Todos los REITs de capital: el decil más barato y el más caro

Exceso anual bruto contra todos los elegibles (cohortes de 4 trimestres), recortes del grupo contra los de todos, y la TIR del decil barato contra aportar a todos con el broker al 35%.

| Señal | Decil | Exceso 2011-2015 | Recortes | TIR (pb) | Exceso 2016+ | Recortes | TIR (pb) |
|---|---|---|---|---|---|---|---|
| Yield de dividendo alto | barato 10% | 2.7% (t +0.75) | 39% / 10% | +59 | 0.4% (t +0.72) | 48% / 14% | +23 |
| Yield de dividendo alto | caro 10% | -5.6% (t -1.63) | 2% / 10% | — | 2.2% (t +0.72) | 11% / 14% | — |
| Rendimiento FFO alto | barato 10% | 1.7% (t +0.67) | 38% / 10% | -207 | -2.8% (t -0.06) | 32% / 14% | -114 |
| Rendimiento FFO alto | caro 10% | 6.4% (t +1.56) | 8% / 10% | — | -3.0% (t -1.85) | 22% / 14% | — |
| Rendimiento de la empresa (cap rate) | barato 10% | -2.8% (t -0.98) | 34% / 10% | -288 | -0.4% (t +0.49) | 26% / 14% | -93 |
| Rendimiento de la empresa (cap rate) | caro 10% | 1.7% (t +0.40) | 10% / 10% | — | -1.2% (t -0.92) | 18% / 14% | — |
| Yield alto contra su historia | barato 10% | 9.8% (t +3.73) | 24% / 10% | +227 | -3.1% (t -1.18) | 34% / 14% | -204 |
| Yield alto contra su historia | caro 10% | -2.9% (t —) | 42% / 10% | — | 1.1% (t +0.34) | 8% / 14% | — |

## Lo que se escribió antes de correr

* **H-E1** (el 10% más caro rinde menos, pero los REITs siguen ganándole al efectivo y salir no llega a +50 pb): No se cumple. Rinde menos que el resto con las cuatro señales: no; el efectivo gana menos de la mitad de las veces: sí; ninguna regla llega a +50 pb en las dos muestras: sí.
* **H-E2** (el 10% más barato rinde más, con pocos episodios y sin |t| ≥ 2 en las dos muestras): Se cumple. Episodios en desarrollo: 2, 4, 1, 5.
* **H-E3** (en O, NNN y WPC el 10% más barato rinde varios puntos más que el 10% más caro, con menos de 5 ventanas): Se cumple: 19.4% contra 4.7% al año.
* **H-E4** (el decil de yield más alto recorta más y no le gana; el más caro no pierde de forma consistente): No se cumple.
* **H-E5** (ninguna pista en el sector ni en el corte transversal): No se cumple (2 pistas).

## Bitácora y límites

Esta corrida abrió la validación 2 veces (sector y corte transversal) y agregó 48 evaluaciones con la familia `extremos`, que sí cuentan como intentos. Límites: con percentiles expandibles, el yield del sector, que bajó con los años, pasa más tiempo en su «extremo caro» que la frecuencia nominal; los extremos del sector son pocos episodios; en O, NNN y WPC las ventanas de 5 años se enciman y los tres emisores sobrevivieron; en el corte transversal, un decil son unos 9 emisores por trimestre (unos 4 en el yield contra su historia).
