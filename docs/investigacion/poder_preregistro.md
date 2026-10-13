# Análisis de poder. Pre-registro

Escrito el 13 de octubre de 2026, antes de correr nada. Va en el mismo commit que el código que
lo corre (`src/investigacion/poder.py`).

## La pregunta

La investigación no encontró ninguna regla que pasara. ¿Es porque no existen o porque las
pruebas no podían verlas? Este análisis mide qué tan grande tenía que ser una ventaja para que
cada prueba de cabecera la detectara. No prueba reglas nuevas ni escribe en la bitácora. La única
excepción es la apertura de la validación de EE. UU., que el candado siempre anota.

## Método

**Distribución nula por placebo.** Cada prueba se repite muchas veces con reglas sin habilidad
que conservan lo demás de la regla real: cuánto tiempo pasa dentro, cuántas veces cambia y
cuántos escoge. La semilla es fija (7). La desviación estándar de esa nula es el **error
estándar (EE)** de la prueba en puntos base al año.

* **Timing (fase 5, 1972-2015, SIC):** la exposición de la regla se desplaza en el tiempo de forma
  circular, entre 24 meses y el largo de la muestra menos 24, con 500 placebos. Se mide la mejora
  rebalanceando contra aportar siempre. Las reglas son la tendencia de 10 meses, condiciones
  financieras (fuera en el quintil peor) y el yield contra el Treasury (fuera en el quintil peor).
* **Protección (fase 8):** la tendencia de 10 meses en EE. UU. de 2016 en adelante, con el mismo
  placebo. Los mercados sellados no se abren.
* **Selección (fase 6, SIC):** cada trimestre se escoge al azar un tercio de los elegibles, con la
  misma tenencia de 4 trimestres. Son 300 placebos en desarrollo y 300 en validación; se mide la
  TIR contra aportar a todos. Además se calcula el EE de Newey-West del exceso trimestral de
  momentum.
* **Asignación entre O, NNN y WPC (SIC):** 500 elecciones al azar con las mismas rachas del
  consenso (`metodos.asignar`).
* **Sharpe deflactado:** el Sharpe mínimo que habría llevado el Sharpe deflactado a 0.95 con los
  intentos y la varianza de Sharpes de la fase 5 (22 reglas) y de la fase 6 (19 intentos). Se
  compara contra el observado.

**Efecto mínimo detectable (MDE):** con una cola al 5% y potencia de 80%,
MDE = (1.645 + 0.842) × EE ≈ 2.49 × EE.

**Curvas de potencia (corrimiento de la nula):** para una habilidad verdadera δ de 25, 50, 100,
150, 200 y 300 pb al año sobre una regla sin habilidad con el mismo perfil:

* la probabilidad de pasar el criterio de la prueba: +50 pb contra aportar siempre o contra todos;
  −25 pb de costo en la protección;
* la probabilidad de distinguirla del azar al 5%.

**Verificación con ventaja inyectada:** en la tendencia de 10 meses se suma al retorno del mes
una ventaja centrada a·(e<sub>t−1</sub> − ē), calibrada para que la habilidad sea δ = 100 y 200 pb
al año. Luego se remuestrea con bootstrap por bloques de 12 meses, 200 veces. Se reporta qué
fracción pasa:

* los criterios de retorno del filtro de la fase 5: mejora > 0, contra la mezcla fija, con retraso,
  con doble costo y en las dos mitades;
* el +50 pb.

La parte de predecir a 12 meses queda fuera, así que esa potencia es un techo.

## Cómo se lee

Por prueba se reportan el EE, el MDE, el efecto observado y la frase «una ventaja de X pb habría
pasado inadvertida Y% de las veces». Un MDE mayor que el techo del oráculo de la fase 3 (+379 pb
rebalanceando con el de 12 meses) significa que la prueba no tenía cómo ver ninguna regla
realista.

## Lo que esperamos (escrito antes de correr)

* **H-P1.** El EE de la mejora del timing en 1972-2015 está entre 50 y 150 pb al año, así que el
  MDE va de unos 125 a 375 pb. Una ventaja de 100 pb pasaría inadvertida la mayoría de las veces.
* **H-P2.** En la selección, con solo 5 años de desarrollo, el EE de la TIR está entre 100 y 250 pb
  al año: el MDE pasa de 250 pb.
* **H-P3.** En la asignación entre O, NNN y WPC el EE está entre 20 y 60 pb al año. Es la prueba
  más fina de todas, porque nunca guarda efectivo ni vende.
* **H-P4.** El Sharpe que pedía el Sharpe deflactado de la fase 6 está muy arriba del observado:
  con 18 trimestres, ninguna regla realista llegaba a 0.95.

## Nota antes del commit

Para comprobar que el código corría, antes de este commit se hizo una prueba con la muestra de
desarrollo y los estudios de O, NNN y WPC, sin escribir en la bitácora y sin abrir la
validación ni los sellados. Todo lo de arriba, hipótesis incluidas, se escribió antes de esa
prueba y no se cambió después.
