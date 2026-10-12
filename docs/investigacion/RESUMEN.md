# Investigación: ¿cuándo entrar a los REITs y en cuáles? Dónde va

Plan: `PLAN.md`. Cada fase tiene su documento; todo lo que se probó está en
`data/investigacion/bitacora.csv`.

## La respuesta corta (pregunta 1: cuándo entrar al sector)

**No se encontró una manera eficiente de decidir cuándo estar en REITs y cuándo en
efectivo.** Ninguna de las 22 reglas de señales simples ni de los 5 modelos (hasta árboles y
regímenes de Markov) le ganó a aportar siempre de forma robusta, con impuestos del SIC y
comisiones. La única regla que llegó a la prueba final —la protección por tendencia— sí
reduce las caídas, pero fuera de la muestra en que se escogió cuesta de 1 a 5 puntos al año.

| Fase | Qué se hizo | Resultado |
|---|---|---|
| 0 | Reglas del juego antes de tocar datos: objetivo, muestras, criterios, candado y bitácora | `PLAN.md` |
| 1 | Literatura: 99 fuentes | La valuación del sector predice dentro de muestra y falla fuera; la tendencia reduce caídas sin subir el retorno (`literatura.md`) |
| 2 | Datos: Nareit desde 1972 (validado contra fondos), 29 series de FRED, French, Shiller, ocho mercados sellados; y de la SEC, todos los REITs de EE. UU. desde 2009, vivos y muertos (13F y XBRL) | Precios de los 13F contra Yahoo: 97% de los trimestres a menos de 2 puntos; FFO armado a ±3.5% del publicado |
| 3 | Exploración 1972-2015 | Decidiendo solo el dinero nuevo, ni un oráculo pasa de +79 pb; el valor posible está en vender y volver a entrar (`fase3_exploracion.md`) |
| 4 | Pre-registro: 11 señales, 22 reglas | `fase4_preregistro.md` |
| 5 | Las 22 reglas en desarrollo | Ninguna pasa el filtro: RECHAZADO (`fase5_resultados.md`) |
| 7 | Escalera de 5 modelos, estimados siempre con el pasado | Ninguno le gana a aportar siempre: RECHAZADO. El compuesto predice cuánto le ganan los REITs al efectivo, pero nunca que pierdan (`fase7_resultados.md`) |
| 8 | Prueba final de la protección por tendencia: EE. UU. 2016-2026 y ocho mercados | Baja la caída 32% en promedio, cuesta 127 pb al año (490 pb en EE. UU.): RECHAZADO (`fase8_resultados.md`) |
| 6 | En cuáles: 16 reglas de selección y un detector de recortes con todos los REITs de capital desde 2011; un tercio de los emisores sellado | Solo momentum pasa la validación (+57 pb) y en los sellados gana +38 pb, debajo de los +50: RECHAZADO (`fase6_resultados.md`) |
| S | Las mismas reglas con un broker de EE. UU. (dividendo al 39% o 44%, sin comisión) | Ningún veredicto cambia; aportar siempre rinde 145 a 184 pb menos al año (`sensibilidad_broker.md`) |

## La respuesta corta (pregunta 2: en cuáles)

**Tampoco hay una regla para escoger en cuáles REITs que le gane a repartir entre todos.** Con
todos los REITs de capital de EE. UU. desde 2011 —incluidos los que quebraron o fueron
comprados, con precios de los 13F de la SEC—, ninguna de 16 reglas de selección le ganó de
forma robusta. La única que llegó a la prueba final, momentum, ganó +38 pb al año en los
emisores sellados: debajo del criterio. Lo «barato» resultó trampa, aun entre los de calidad.

## Si compra con un broker de EE. UU. (sensibilidad, 12-oct-2026)

Todo lo anterior supone el SIC. Comprando directo con un broker de EE. UU., el dividendo de
un REIT paga la tasa marginal más 9 puntos (39% con marginal de 30%, 44% con 35%), los
intereses la marginal, la ganancia sigue en 10% y no hay comisión. Se repitieron las mismas
reglas y modelos congelados con ese perfil, sin escoger nada nuevo
(`sensibilidad_broker_preregistro.md`, `sensibilidad_broker.md`). **Ningún veredicto cambia.**

* Aportar siempre rinde de 145 a 184 pb menos al año (1972-2015) y de 123 a 168 pb menos en
  O, NNN y WPC: es lo que el broker le cuesta al que no hace timing.
* Las reglas que salen del mercado cuestan menos, porque estar fuera evita un dividendo más
  gravado y no hay comisión. La tendencia de 10 meses pasa de +15 a +93 pb en desarrollo y
  condiciones financieras de +92 a +114 pb, pero ninguna de las 22 pasa el filtro (la de
  condiciones financieras solo falla en predecir a 12 meses). En la prueba final, la
  protección por tendencia cuesta 49 a 54 pb al año en los ocho mercados (127 con el SIC) y
  386 a 387 pb en EE. UU. desde 2016 (490): sigue RECHAZADA.
* En la selección casi nada cambia: momentum gana +41 a +42 pb en los emisores sellados
  (+38 con el SIC), debajo de los +50; el yield alto pierde más (−125 pb contra −86).
* En O, NNN y WPC, mandar la aportación al más barato con el consenso de los métodos gana
  +60 a +63 pb (+72 con el SIC).
* La columna SIC reproduce exactamente lo guardado en cada fase. Los ocho mercados y los
  emisores sellados se leyeron una vez más, con un modelo congelado propio que repite la
  regla ya congelada; la bitácora guarda las 192 reevaluaciones aparte de los intentos.
* Fuera del modelo: el impuesto sucesorio de EE. UU. (más de 60 mil dólares en activos de
  EE. UU.). Las tasas deben confirmarse con un contador.

## Lo que sí se aprendió

1. **Esperar no paga.** El retorno esperado de los REITs casi siempre está arriba del
   efectivo; ningún modelo, ni el que mejor distingue años buenos de malos, pronosticó que el
   efectivo fuera a ganar.
2. **Decidiendo solo a dónde va el dinero nuevo, el timing casi no puede valer nada**: la
   riqueza ya invertida pesa mucho más que la aportación del mes.
3. **La protección contra caídas existe pero se paga**: la tendencia sale después de la caída
   y vuelve después del rebote, y cada salida paga impuesto sobre la ganancia.
4. **El yield alto y lo barato concentran los recortes** (21% de los de yield alto recortó en
   el año siguiente contra 10% del universo) y no rinden más; «barato entre los de calidad»
   fue la peor de las 16 reglas.
5. **Los recortes se ven venir, pero esquivarlos no paga**: un detector con datos públicos
   acierta (AUC 0.75 fuera de muestra), pero los que recortan rebotan el año siguiente (+7.7%
   contra el universo en 2016-2026). No conviene vender después de un recorte.
6. Para el inversionista: **aportar siempre y repartir entre muchos REITs de capital** (o un
   fondo amplio), sin guardar efectivo esperando el momento ni concentrarse en lo barato.

## Qué tan sólido es

Cada hipótesis se guardó en un commit antes de correrla, los datos se partieron antes de verlos
y las pruebas finales (ocho mercados y un tercio de los emisores de EE. UU.) se evaluaron con un
solo modelo congelado, sin cambiarlo. La bitácora registra cada lectura: los ocho mercados se
leyeron tres veces con el modelo de la fase 8 (al regenerar su informe) y una más en la
sensibilidad fiscal; los emisores sellados, una vez en la fase 6 y otra en la sensibilidad. En la fase 6, la primera corrida tuvo dos errores de programación que se corrigieron
y se declaran en su informe; el veredicto no cambió. Límites: la selección empieza en 2011
(antes casi no hay XBRL) y las escisiones no se ven en los 13F.

## Lo que falta

* **Seguimiento en vivo**: el plan lo pedía para la regla que resultara; ninguna pasó, así que
  no hay regla que vigilar. Las fases se pueden repetir con datos nuevos con los mismos
  comandos.

## La entrega (fase 9)

La página **Investigación** de la aplicación y el informe
`investigacion_cuando_entrar.pdf`, generados con los resultados guardados en
`data/investigacion/resultados/`.
