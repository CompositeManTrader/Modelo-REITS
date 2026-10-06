# Fase 5: ¿cuándo entrar al sector? Resultados

Pre-registro: `fase4_preregistro.md` (commit anterior a esta corrida). Muestra de desarrollo: FTSE Nareit All Equity REITs de 01-1972 a 12-2015. Aportar siempre da una TIR de 10.65% con una caída máxima de -69%. Generado por `python scripts/investigacion.py fase5`.

## Veredicto

**0 de 22 reglas pasan el filtro pre-registrado.** Como dice el pre-registro, la validación no se abre y la fase 5 termina en **RECHAZADO** para decidir cuándo entrar al sector con estas señales.

Pruebas múltiples sobre las 22 reglas: PBO = 0.17 (umbral 0.20) y Sharpe deflactado de la mejor por Sharpe («tendencia de 10 meses | signo») = 1.000 (umbral 0.95). El Sharpe mide el retorno por unidad de riesgo de la parte invertida; no es la TIR del inversionista.

## Lo que se escribió antes de correr

* **H0 — ninguna le gana a aportar siempre de forma robusta.** Se cumple: ninguna regla pasa el filtro (gana con retraso, con doble costo, en las dos eras y predice).
* **H1 — la valuación no sirve para salir.** Se cumple: las 8 reglas de valuación van de -490 a -43 pb al año rebalanceando, y su R² a 12 meses va de -8.9% a +1.3%, sin un Clark-West significativo.
* **H2 — el crédito reduce la caída sin llegar a +50 pb.** En parte: salir con estrés financiero extremo (NFCI en su quintil peor) dio +92 pb y una caída máxima de -39%, pero todo viene de 1993-2015 (+199 pb) y en 1972-1992 dio -15 pb. Además el NFCI se revisa: la serie de hoy no es la que se conocía entonces.
* **H3 — la tendencia protege a costo pequeño.** En parte: el promedio de 10 meses bajó la caída máxima de -69% a -21% con +15 pb al año, ejecutando al mismo cierre. Con un mes de retraso cuesta -110 pb, y en 1972-1992 costó -111 pb. No predice el retorno a 12 meses.
* **H4 — la bolsa del mes predice a un mes, no a 12.** Se cumple: R² a 1 mes de +2.3% (Clark-West p = 0.04), a 12 meses -0.5%; sus reglas quedan en -104 pb o menos: la predicción no alcanza a pagar impuestos y comisiones.
* **H5 — las combinaciones no le ganan a la mejor sola.** Se cumple: 0 pb la mejor combinación contra +92 pb la mejor señal sola.
* **H6 — decidiendo solo el dinero nuevo nada llega a +50 pb.** Se cumple: todas quedan entre -19 y +7 pb.

## Todas las reglas, en desarrollo

Mejoras en puntos base al año de TIR contra aportar siempre. «Contra mezcla fija»: contra rebalancear a una exposición constante igual a la promedio de la regla (P8). R² fuera de muestra a 12 meses con restricción de signo.

| Señal | Regla | Solo dinero nuevo (pb) | Rebalanceando (pb) | Contra mezcla fija (pb) | Caída máxima | Exposición | Con un mes de retraso (pb) | R² a 12 meses (%) | Clark-West p | Apuestas | Pasa |
|---|---|---|---|---|---|---|---|---|---|---|---|
| condiciones financieras | fuera en el quintil peor (20%) | -2 | +92 | +142 | -39% | 92% | +55 | -1.2 | 0.64 | 16 | no |
| tendencia de 10 meses | signo | +7 | +15 | +230 | -21% | 68% | -110 | -4.7 | 0.75 | 44 | no |
| momentum contra el efectivo | signo | -5 | +2 | +177 | -20% | 73% | -118 | -4.6 | 0.75 | 32 | no |
| compuesto de cuatro familias | continua con piso de 50% | 0 | 0 | +75 | -45% | 88% | -15 | -0.1 | 0.45 | 44 | no |
| caro y con tendencia negativa | fuera si caro y a la baja | +1 | -11 | +8 | -69% | 97% | -56 | +0.0 | — | 8 | no |
| crédito bancario a inmuebles | fuera en el quintil peor (20%) | -6 | -15 | +52 | -39% | 89% | +46 | -10.3 | 0.90 | 10 | no |
| yield contra el Treasury | fuera en el quintil peor (20%) | 0 | -43 | +49 | -68% | 85% | -72 | +1.3 | 0.12 | 12 | no |
| condiciones financieras | continua con piso de 50% | -1 | -50 | +53 | -47% | 84% | -74 | -1.2 | 0.64 | 44 | no |
| crédito bancario a inmuebles | continua con piso de 50% | 0 | -59 | +10 | -43% | 89% | -56 | -10.3 | 0.90 | 44 | no |
| yield contra bonos Baa | fuera en el quintil peor (20%) | -14 | -93 | -21 | -69% | 88% | -103 | -0.2 | 0.82 | 10 | no |
| bolsa del mes | continua con piso de 50% | 0 | -104 | +34 | -49% | 78% | -272 | -0.5 | 0.85 | 44 | no |
| cambio del spread de crédito | fuera en el quintil peor (20%) | -3 | -117 | -19 | -39% | 84% | +10 | -1.3 | 0.75 | 37 | no |
| cambio del spread de crédito | continua con piso de 50% | -2 | -119 | +27 | -44% | 77% | -115 | -1.3 | 0.75 | 44 | no |
| bolsa del mes | fuera en el quintil peor (20%) | 0 | -119 | -15 | -39% | 84% | -493 | -0.5 | 0.85 | 44 | no |
| yield contra el Treasury | continua con piso de 50% | -2 | -137 | -13 | -63% | 81% | -130 | +1.3 | 0.12 | 44 | no |
| yield contra bonos Baa | continua con piso de 50% | -2 | -150 | -12 | -57% | 79% | -127 | -0.2 | 0.82 | 44 | no |
| spread de default | continua con piso de 50% | -1 | -199 | -36 | -64% | 75% | -214 | +2.6 | 0.18 | 44 | no |
| yield contra la tasa real | fuera en el quintil peor (20%) | -19 | -225 | -82 | -63% | 78% | -204 | -0.4 | 0.81 | 35 | no |
| yield contra la tasa real | continua con piso de 50% | -2 | -239 | -59 | -62% | 72% | -237 | -0.4 | 0.81 | 44 | no |
| yield de los REITs | continua con piso de 50% | -2 | -247 | -40 | -50% | 69% | -234 | -8.9 | 0.73 | 44 | no |
| spread de default | fuera en el quintil peor (20%) | -15 | -254 | -121 | -69% | 79% | -318 | +2.6 | 0.18 | 22 | no |
| yield de los REITs | fuera en el quintil peor (20%) | +6 | -490 | -192 | -42% | 56% | -437 | -8.9 | 0.73 | 35 | no |

## Por era

| Señal | Regla | 1972-1992 (pb) | 1993-2015 (pb) |
|---|---|---|---|
| bolsa del mes | continua con piso de 50% | -81 | -91 |
| bolsa del mes | fuera en el quintil peor (20%) | -170 | -58 |
| cambio del spread de crédito | continua con piso de 50% | -224 | -10 |
| cambio del spread de crédito | fuera en el quintil peor (20%) | -317 | +9 |
| caro y con tendencia negativa | fuera si caro y a la baja | -21 | 0 |
| compuesto de cuatro familias | continua con piso de 50% | -28 | +35 |
| condiciones financieras | continua con piso de 50% | -107 | -3 |
| condiciones financieras | fuera en el quintil peor (20%) | -15 | +199 |
| crédito bancario a inmuebles | continua con piso de 50% | 0 | -56 |
| crédito bancario a inmuebles | fuera en el quintil peor (20%) | 0 | +32 |
| momentum contra el efectivo | signo | -77 | +84 |
| spread de default | continua con piso de 50% | -101 | -216 |
| spread de default | fuera en el quintil peor (20%) | -120 | -215 |
| tendencia de 10 meses | signo | -111 | +121 |
| yield contra bonos Baa | continua con piso de 50% | -204 | -99 |
| yield contra bonos Baa | fuera en el quintil peor (20%) | -241 | 0 |
| yield contra el Treasury | continua con piso de 50% | -174 | -104 |
| yield contra el Treasury | fuera en el quintil peor (20%) | -108 | +4 |
| yield contra la tasa real | continua con piso de 50% | -150 | -295 |
| yield contra la tasa real | fuera en el quintil peor (20%) | -271 | -229 |
| yield de los REITs | continua con piso de 50% | -120 | -306 |
| yield de los REITs | fuera en el quintil peor (20%) | -45 | -776 |

