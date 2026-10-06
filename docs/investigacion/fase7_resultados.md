# Fase 7: la escalera de modelos. Resultados

Pre-registro: `fase7_preregistro.md` (commit anterior a esta corrida). Muestra de desarrollo, 1972-2015; los pronósticos empiezan cuando hay 60 meses para los percentiles y 120 pares terminados para estimar. Aportar siempre: TIR de 10.65%, caída máxima de -69%. Generado por `python scripts/investigacion.py fase7`.

## Veredicto

**Ningún peldaño le gana a aportar siempre**, así que la escalera no deja candidato: nada de la fase 7 pasa a validación ni a la prueba final. Como dice el pre-registro, la escalera termina en **RECHAZADO**.


| Peldaño | Rebalanceando (pb) | Solo dinero nuevo (pb) | Contra mezcla fija (pb) | Caída máxima | Exposición | Cambios | Con un mes de retraso (pb) | R² del modelo (%) | Clark-West p | 1972-1992 (pb) | 1993-2015 (pb) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mejor señal sola | -35 | 0 | -23 | -69% | 98% | 2 | -20 | -7.0 | 0.70 | 0 | 0 |
| compuesto | 0 | 0 | 0 | -69% | 100% | 0 | 0 | +3.5 | 0.08 | 0 | 0 |
| ridge | 0 | 0 | 0 | -69% | 100% | 0 | 0 | -2.3 | 0.73 | 0 | 0 |
| árboles | -393 | -8 | -323 | -69% | 89% | 38 | -206 | -16.8 | 0.58 | -177 | -494 |
| regímenes | -217 | -3 | -83 | -51% | 79% | 78 | -245 | -0.6 | 0.73 | -260 | -177 |

## Lo que se escribió antes de correr

* **H7.1 — ningún peldaño llega a +50 pb.** Se cumple: el mejor queda en 0 pb.
* **H7.2 — ridge y árboles no le ganan a lo simple.** Se cumple: árboles -393 pb; ridge nunca sale.
* **H7.3 — regímenes reduce la caída pero cuesta.** Se cumple: caída máxima de -51% contra -69%, a un costo de -217 pb al año; no llega al 30% de reducción con costo de 25 pb.
* **H7.4 — el pronóstico casi siempre es positivo.** Se cumple: meses fuera del mercado — mejor señal sola: 10; compuesto: 0; ridge: 0; árboles: 60; regímenes: 110. El compuesto sí distingue años mejores de peores (R² fuera de muestra de +3.5%, Clark-West p = 0.08), pero su pronóstico del retorno de los REITs contra el efectivo nunca salió negativo: **lo que predice es cuánto van a ganarle al efectivo, no si van a perder contra él**. Es la misma conclusión de los estudios de O, NNN y WPC, ahora con un modelo.
