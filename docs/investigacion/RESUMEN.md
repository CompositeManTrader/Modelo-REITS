# Investigación: ¿cuándo entrar a los REITs? Dónde va

Plan: `PLAN.md`. Cada fase tiene su documento; todo lo que se probó está en
`data/investigacion/bitacora.csv`.

## La respuesta corta (fases 0 a 8, pregunta 1: cuándo entrar al sector)

**No se encontró una manera eficiente de decidir cuándo estar en REITs y cuándo en
efectivo.** Ninguna de las 22 reglas de señales simples ni de los 5 modelos (hasta árboles y
regímenes de Markov) le ganó a aportar siempre de forma robusta, con impuestos del SIC y
comisiones. La única regla que llegó a la prueba final —la protección por tendencia— sí
reduce las caídas, pero fuera de la muestra en que se escogió cuesta de 1 a 5 puntos al año.

| Fase | Qué se hizo | Resultado |
|---|---|---|
| 0 | Reglas del juego antes de tocar datos: objetivo, muestras, criterios, candado y bitácora | `PLAN.md` |
| 1 | Literatura: 99 fuentes | La valuación del sector predice dentro de muestra y falla fuera; la tendencia reduce caídas sin subir el retorno (`literatura.md`) |
| 2 | Datos: Nareit desde 1972 (validado contra fondos), 29 series de FRED, French, Shiller, ocho mercados sellados | Pendiente: estados financieros del universo (requiere identificación ante la SEC) |
| 3 | Exploración 1972-2015 | Decidiendo solo el dinero nuevo, ni un oráculo pasa de +79 pb; el valor posible está en vender y volver a entrar (`fase3_exploracion.md`) |
| 4 | Pre-registro: 11 señales, 22 reglas | `fase4_preregistro.md` |
| 5 | Las 22 reglas en desarrollo | Ninguna pasa el filtro: RECHAZADO (`fase5_resultados.md`) |
| 7 | Escalera de 5 modelos, estimados siempre con el pasado | Ninguno le gana a aportar siempre: RECHAZADO. El compuesto predice cuánto le ganan los REITs al efectivo, pero nunca que pierdan (`fase7_resultados.md`) |
| 8 | Prueba final de la protección por tendencia: EE. UU. 2016-2026 y ocho mercados | Baja la caída 32% en promedio, cuesta 127 pb al año (490 pb en EE. UU.): RECHAZADO (`fase8_resultados.md`) |

## Lo que sí se aprendió

1. **Esperar no paga.** El retorno esperado de los REITs casi siempre está arriba del
   efectivo; ningún modelo, ni el que mejor distingue años buenos de malos, pronosticó que el
   efectivo fuera a ganar.
2. **Decidiendo solo a dónde va el dinero nuevo, el timing casi no puede valer nada**: la
   riqueza ya invertida pesa mucho más que la aportación del mes.
3. **La protección contra caídas existe pero se paga**: la tendencia sale después de la caída
   y vuelve después del rebote, y cada salida paga impuesto sobre la ganancia.
4. Para el inversionista: **aportar siempre**, y usar la valuación solo para escoger a cuál
   REIT de calidad va el dinero del mes (estudio de métodos de valuación), no para decidir
   si entrar.

## Lo que falta

* **Fase 6 (en cuáles REITs)**: necesita los estados financieros del universo completo, que
  la SEC solo entrega con un `SEC_USER_AGENT` configurado por el inversionista.
* **Fase 9 (entrega)**: página, PDF y seguimiento. Con un resultado negativo en la pregunta 1,
  la entrega es el informe de la investigación; la regla de seguimiento en vivo aplica solo si
  la fase 6 encuentra algo.
