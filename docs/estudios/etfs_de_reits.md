# ETFs de REITs contra el índice de la investigación

Generado por `python scripts/estudio.py etfs`. Compara USRT, SCHH y VNQ contra el FTSE Nareit All Equity REITs, el índice sobre el que la investigación midió «aportar siempre». Es descriptivo: no prueba reglas. Retornos totales (con dividendos reinvertidos) en dólares, antes de impuestos, salvo la TIR neta, que aporta 1,000 dólares cada mes sin vender nunca con el perfil del broker de EE. UU. al 35% (dividendo 44%, intereses 35%, ganancia 10%, sin comisión), igual que en la investigación.

## En corto

* **El más parecido al índice de la investigación es SCHH.** Desde que sigue su índice actual (2020-07) se desvía 0.43% al año, con una diferencia de -2 pb al año y correlación de 0.9997. USRT se desvía 2.64% (+3 pb al año desde 2016-12); VNQ se desvía 1.43% (-51 pb al año desde 2018-03).
* **USRT se desvía más porque su índice deja fuera los REITs de torres de telecomunicaciones y de madera.** Contra su propio índice se desvía solo 0.38% al año (correlación 0.9998).
* **Antes de impuestos rinden casi lo mismo que el índice:** desde 2011-02, 7.7% al año el índice contra 7.4% USRT, 6.2% SCHH, 7.1% VNQ. Parte de la diferencia viene de los índices que seguían antes.
* **Ninguno te quita las caídas.** La peor de cada uno desde su inicio: USRT -65.8% (2007-05 a 2009-02, el índice -66.8%); SCHH -31.5% (2021-12 a 2023-10, el índice -31.4%); VNQ -68.3% (2007-01 a 2009-02, el índice -68.3%).
* **Aportando 1,000 dólares cada mes con el broker al 35%**, desde 2011-02, la TIR neta fue de 4.5% en el índice contra 4.8% USRT, 3.3% SCHH, 3.7% VNQ. La TIR pesa más los últimos años, cuando ya hay más dinero invertido, así que favorece al que mejor le fue al final.
* **Pagan 4 veces al año** (cada trimestre), con un yield de 2.85% USRT, 3.08% SCHH, 3.80% VNQ en los últimos 12 meses.

## Ventana común (2011-02 a 2026-09)

Los tres ETFs y el índice en los mismos meses: la comparación pareja.

| Serie | Meses | Rendimiento anual | Contra el índice (pb al año) | Error de seguimiento | Correlación | Caída máxima | Recuperación | Peor año | Volatilidad | TIR neta aportando | Yield 12m |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **USRT** | 2011-02 a 2026-09 | 7.4% | -31 | 2.53% | 0.9886 | -29.4% (2021-12 a 2023-10) | 13 meses | -24.4% (2022) | 16.8% | 4.8% | 2.85% |
| Índice (meses de USRT) | 2011-02 a 2026-09 | 7.7% | — | — | — | -31.4% (2021-12 a 2023-10) | 30 meses | -24.9% (2022) | 16.6% | 4.5% | 3.93% |
| **SCHH** | 2011-02 a 2026-09 | 6.2% | -145 | 2.03% | 0.9933 | -31.5% (2021-12 a 2023-10) | 30 meses | -25.0% (2022) | 17.2% | 3.3% | 3.08% |
| Índice (meses de SCHH) | 2011-02 a 2026-09 | 7.7% | — | — | — | -31.4% (2021-12 a 2023-10) | 30 meses | -24.9% (2022) | 16.6% | 4.5% | 3.93% |
| **VNQ** | 2011-02 a 2026-09 | 7.1% | -63 | 1.53% | 0.9962 | -32.8% (2021-12 a 2023-10) | 33 meses | -26.3% (2022) | 17.1% | 3.7% | 3.80% |
| Índice (meses de VNQ) | 2011-02 a 2026-09 | 7.7% | — | — | — | -31.4% (2021-12 a 2023-10) | 30 meses | -24.9% (2022) | 16.6% | 4.5% | 3.93% |

## Con el índice que sigue hoy cada ETF

Cada uno cambió de índice al menos una vez; desde el cambio, la desviación contra el índice de la investigación es la mejor guía de lo que se puede esperar.

* **USRT** sigue el FTSE Nareit Equity REITs (con topes) desde 2016-12.
* **SCHH** sigue el Dow Jones Equity All REIT Capped desde 2020-07.
* **VNQ** sigue el MSCI US IMI Real Estate 25/50 desde 2018-03.

| Serie | Meses | Rendimiento anual | Contra el índice (pb al año) | Error de seguimiento | Correlación | Caída máxima | Recuperación | Peor año | Volatilidad | TIR neta aportando | Yield 12m |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **USRT** | 2016-12 a 2026-09 | 6.3% | +3 | 2.64% | 0.9894 | -29.4% (2021-12 a 2023-10) | 13 meses | -24.4% (2022) | 18.0% | 4.7% | 2.85% |
| Índice (meses de USRT) | 2016-12 a 2026-09 | 6.3% | — | — | — | -31.4% (2021-12 a 2023-10) | 30 meses | -24.9% (2022) | 17.4% | 3.4% | 3.93% |
| **SCHH** | 2020-07 a 2026-09 | 6.6% | -2 | 0.43% | 0.9997 | -31.5% (2021-12 a 2023-10) | 30 meses | -25.0% (2022) | 18.1% | 3.1% | 3.08% |
| Índice (meses de SCHH) | 2020-07 a 2026-09 | 6.7% | — | — | — | -31.4% (2021-12 a 2023-10) | 30 meses | -24.9% (2022) | 18.2% | 2.9% | 3.93% |
| **VNQ** | 2018-03 a 2026-09 | 6.4% | -51 | 1.43% | 0.9971 | -32.8% (2021-12 a 2023-10) | 33 meses | -26.3% (2022) | 18.5% | 2.6% | 3.80% |
| Índice (meses de VNQ) | 2018-03 a 2026-09 | 6.9% | — | — | — | -31.4% (2021-12 a 2023-10) | 30 meses | -24.9% (2022) | 18.3% | 3.3% | 3.93% |

Contra su propio índice, cuando ese índice también lo publica Nareit:

| ETF | Su índice | Meses | Correlación | Diferencia (pb al año) | Error de seguimiento |
|---|---|---|---|---|---|
| USRT | FTSE Nareit Equity REITs | 2016-12 a 2026-09 | 0.9998 | -20 | 0.38% |

## Desde el inicio de cada ETF

Más historia (VNQ y USRT pasaron por 2008-2009), pero con índices distintos al de hoy: USRT seguía a los 50 REITs más grandes hasta 2016 y VNQ solo REITs hasta 2018.

| Serie | Meses | Rendimiento anual | Contra el índice (pb al año) | Error de seguimiento | Correlación | Caída máxima | Recuperación | Peor año | Volatilidad | TIR neta aportando | Yield 12m |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **USRT** | 2007-06 a 2026-09 | 5.0% | -35 | 3.35% | 0.9884 | -65.8% (2007-05 a 2009-02) | 40 meses | -37.2% (2008) | 21.4% | 5.5% | 2.85% |
| Índice (meses de USRT) | 2007-06 a 2026-09 | 5.4% | — | — | — | -66.8% (2007-05 a 2009-02) | 38 meses | -37.7% (2008) | 22.0% | 5.4% | 3.93% |
| **SCHH** | 2011-02 a 2026-09 | 6.2% | -145 | 2.03% | 0.9933 | -31.5% (2021-12 a 2023-10) | 30 meses | -25.0% (2022) | 17.2% | 3.3% | 3.08% |
| Índice (meses de SCHH) | 2011-02 a 2026-09 | 7.7% | — | — | — | -31.4% (2021-12 a 2023-10) | 30 meses | -24.9% (2022) | 16.6% | 4.5% | 3.93% |
| **VNQ** | 2004-10 a 2026-09 | 7.2% | -39 | 1.46% | 0.9977 | -68.3% (2007-01 a 2009-02) | 40 meses | -37.0% (2008) | 21.5% | 4.5% | 3.80% |
| Índice (meses de VNQ) | 2004-10 a 2026-09 | 7.6% | — | — | — | -68.3% (2007-01 a 2009-02) | 41 meses | -37.7% (2008) | 21.2% | 5.2% | 3.93% |

## Año por año

| Año | Índice | USRT | SCHH | VNQ |
|---|---|---|---|---|
| 2011 (a 11 meses) | 4.0% | 4.9% | 5.5% | 5.2% |
| 2012 | 19.7% | 16.7% | 16.8% | 17.6% |
| 2013 | 2.9% | -1.0% | 1.2% | 2.3% |
| 2014 | 28.0% | 29.1% | 31.9% | 30.4% |
| 2015 | 2.8% | 3.9% | 4.4% | 2.4% |
| 2016 | 8.6% | 7.2% | 6.5% | 8.6% |
| 2017 | 8.7% | 5.3% | 3.7% | 4.9% |
| 2018 | -4.0% | -4.7% | -4.2% | -6.0% |
| 2019 | 28.7% | 26.0% | 22.9% | 28.9% |
| 2020 | -5.1% | -8.1% | -14.8% | -4.6% |
| 2021 | 41.3% | 43.3% | 41.1% | 40.5% |
| 2022 | -24.9% | -24.4% | -25.0% | -26.3% |
| 2023 | 11.4% | 13.6% | 11.2% | 11.9% |
| 2024 | 4.9% | 8.6% | 5.0% | 4.8% |
| 2025 | 2.3% | 2.4% | 2.2% | 3.2% |
| 2026 (a 9 meses) | 7.9% | 9.9% | 7.6% | 4.2% |

## Qué no mide y límites

* El costo publicado por cada emisor (consulta de octubre de 2026) es USRT 0.08%, SCHH 0.07%, VNQ 0.13% al año; la diferencia contra el índice ya lo incluye, junto con lo que el fondo no replica.
* Precios y dividendos de Yahoo Finance (cierre ajustado de fin de mes). El índice no tiene costos, así que parte de la diferencia es por construcción.
* Los impuestos son los del modelo de la investigación; la retención real del broker y el acreditamiento en México los confirma un contador.
* No incluye el impuesto sucesorio de EE. UU. (activos de EE. UU. arriba de 60 mil dólares): los tres ETFs son de EE. UU.; los UCITS domiciliados en Irlanda quedan fuera de ese impuesto.
* Esta comparación mira los datos del índice posteriores a 2016 y lo deja en la bitácora de la investigación; no suma intentos porque no prueba reglas.
