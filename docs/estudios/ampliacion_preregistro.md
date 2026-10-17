# Ampliación del estudio de largo plazo: pre-registro

Escrito y guardado en un commit **antes** de capturar las cifras de los siete emisores
nuevos y antes de correr cualquier análisis sobre ellos (17-oct-2026).

## Qué se hace y por qué

Las conclusiones de los estudios de O, NNN y WPC salieron de **tres emisores**, los tres de
arrendamiento neto y los tres sobrevivientes. Repetir el mismo estudio con los otros siete
REITs de la plataforma sirve para dos cosas:

1. **Darle a cada uno su estudio completo**, igual que a los tres originales. Eso incluye
   historia con fuente, eras, descomposición del retorno, entradas, métodos de valuación
   (también DDM, DCF y NAV), el semáforo puesto a prueba y el retorno esperado por tramo.
2. **Comprobar fuera de muestra las conclusiones de los tres.** Los siete no se usaron
   para llegar a ellas, y cuatro son de otros sectores: bodegas (PSA y EXR), industrial
   (PLD) y salud (WELL).

| Emisor | Sector | Cotiza desde | Notas |
|---|---|---|---|
| ADC | Net Lease | 1994 | |
| EPRT | Net Lease | 2018 | Muy poca historia |
| GNL | Net Lease | 2015 | Antes no cotizaba. Contrasplit 1 por 3 en 2017. Fusión con RTL en 2023. Recortes de dividendo. |
| PSA | Self Storage | ~1980 | |
| EXR | Self Storage | 2004 | |
| PLD | Industrial | 1997 | Como AMB Property; la fusión con ProLogis de 2011 conservó la entidad legal de AMB. |
| WELL | Salud | ~1979 | Antes Health Care REIT (HCN). Split 3 por 2 en 1985. Recorte en 2020. |

## Qué NO cambia

* **El código del análisis queda congelado en este commit**: `metodos`, `reglas`,
  `intrinsecos`, `retornos` y `estudio`. Eso incluye umbrales (barato ≥ 70, caro < 30),
  tramos, supuestos de DDM/DCF/NAV, parámetros del semáforo y número de elecciones al azar.
  Lo único que se agrega por emisor son **datos y su catálogo**:
  * eventos de capital;
  * correcciones de dividendos;
  * inicio verificable;
  * anclas;
  * cifras primarias;
  * calificaciones;
  * narrativa;
  * receta del NOI;
  * medida de valuación.
* **Las reglas de captura son las de siempre.** Va la cifra que el emisor publicó primero
  (P1), con su documento, URL y frase citada. Si algo no se pudo verificar, no entra.
* **Los resultados de O, NNN y WPC no se tocan.** Las corridas nuevas se reportan aparte
  («los siete») y juntas («los diez»).

## Decisiones fijadas ahora (antes de ver retornos)

1. **Medida de valuación.**
   * **Regla general:** FFO de Nareit por acción diluida con la definición vigente de
     Nareit, es decir, sin deterioros de inmuebles depreciables, como se hizo con NNN en
     2009-2010.
   * **Excepción:** se usa la serie «core», «normalized» o AFFO que el emisor publica como
     principal cuando se cumplen las dos condiciones siguientes. Esa serie se usa desde que
     existe y se encadena con el FFO de Nareit antes.
     * El FFO de Nareit de algún año carga una partida que no se repite y que pesa más de
       10% del FFO: gastos de fusión, cambiario sobre deuda, extinción de deuda, *promotes*
       o ganancias de desarrollo.
     * El emisor publica de forma continua una serie que la quita.
   * **Expectativa al escribir esto:**
     * GNL por AFFO, igual que WPC (su FFO carga gastos de adquisición y de fusión);
     * PLD por Core FFO;
     * WELL por Normalized FFO;
     * PSA por Core FFO (su FFO de Nareit trae el cambiario de su deuda en euros);
     * ADC, EPRT y EXR por FFO de Nareit.

     La captura trae **las dos series**. La decisión final de cada emisor se escribe en el
     commit que agrega sus datos, antes de correr `metodos`, citando la partida que la
     justifica.
   * **Sensibilidad obligatoria:** todo se corre también con FFO de Nareit para los siete y
     se reporta junto al resultado principal.
2. **Prima de riesgo del DDM, DCF y crecimiento implícito.** Es la del sector de cada emisor
   en `PRIMA_RIESGO_POR_SECTOR`:
   * Net Lease, 3.0%;
   * Self Storage, 3.5%;
   * Industrial, 3.5%;
   * Salud, 4.5%.

   Hoy el código fija la de Net Lease para todos, que solo es correcta para los tres
   originales. Este es el único cambio al código del análisis, y no mueve ninguna cifra de
   O, NNN ni WPC.
3. **Asignación entre emisores.** Entran solo los emisores con percentil del consenso desde
   2008 o antes. La asignación usa los meses comunes a todos, y un emisor joven acortaría la
   ventana de los demás. EPRT y GNL quedan fuera de la asignación. Sí tienen todo lo demás
   del estudio.
   * **Asignación de «los siete»:** ADC, PSA, EXR, PLD y WELL, si los cinco tienen
     percentil desde 2008.
   * **Asignación de «los diez»:** O, NNN, WPC, ADC, PSA, EXR, PLD y WELL.
   * Si a alguno le falta percentil en 2008, se reporta con la ventana que haya, sin
     sustituirlo.
4. **Unidad de prueba.** La unidad son los fines de trimestre, como en el estudio original.
   Las ventanas independientes de 5 años son trimestres ÷ 20. Para las hipótesis «emisor por
   emisor» solo cuentan los emisores con al menos 40 trimestres con percentil y retorno a 5
   años (2 ventanas independientes).

## Hipótesis y criterio para decir que la conclusión de los tres SE REPITE

Todas se miden con el código congelado, neto con broker de EE. UU. al 35% donde aplica
(como el retorno esperado de la app).

| # | Conclusión de O, NNN y WPC | Se repite en los siete si… |
|---|---|---|
| H1 | La valuación predice el retorno de 5 años: lo barato rindió más que lo caro (~20% contra ~8% al año). | Juntos, la mediana a 5 años de «barato + muy barato» (percentil del consenso ≥ 70) supera a la de «caro + muy caro» (< 30) por **3 puntos al año o más**, Y la ρ de Spearman a 5 años del consenso, juntos, es **positiva**. |
| H1b | Lo mismo, emisor por emisor. | La ρ a 5 años del consenso es positiva en **la mayoría** de los emisores elegibles (regla de 40 trimestres). |
| H2 | Aun desde «caro», el REIT le ganó al efectivo la mayoría de las veces: esperar no paga. | Juntos, en «caro + muy caro», el REIT le gana al T-bill neto en **más de 50%** de los trimestres. |
| H3 | El semáforo completo no le gana a aportar siempre (NNN −560 pb, O −58, WPC +1). | El semáforo le gana a aportar siempre por **+50 pb de TIR o más en a lo sumo 1** de los siete. |
| H4 | Ningún método solo, usado para decidir cuándo comprar (comprar menos o nada cuando dice caro), le gana a aportar siempre. | Con el consenso, la ventaja contra aportar siempre es **menor a +50 pb en la mayoría** de los siete. |
| H5 | Mandar la aportación al más barato contra su propia historia le ganó a repartir parejo (+72 pb entre O, NNN y WPC; mejor que 500 elecciones al azar). | En «los siete» (decisión 3): ventaja del consenso **≥ +50 pb** Y **a lo sumo 5%** de las elecciones al azar le gana Y el espejo (todo al más caro) queda **abajo** de partes iguales. Si no cumple las tres, el +72 pb de los tres originales **no se repite**. |
| H6 | DDM, DCF, crecimiento implícito y NAV no predicen mejor que los métodos simples. | Juntos, **ningún** modelo de valor tiene una ρ a 5 años mayor que la del mejor de los siete métodos simples. |
| H7 | En los extremos la valuación sí separa: el 10% más barato rindió 19.4% contra 4.7% del 10% más caro. | Juntos, la mediana de «muy barato» (≥ 90) **supera** a la de «muy caro» (< 10). |

Cada hipótesis se reporta con su número, aunque falle. Si una conclusión no se repite, el
compilado y la app la matizan; no se busca otra versión de la prueba que sí la repita.

## Límites que se saben de antemano

* **Los siete también sobrevivieron.** Están en la plataforma porque existen hoy. GNL es
  el más cercano a un mal caso (recortes, dilución y fusión), pero no hay quiebras. La
  prueba es fuera de muestra en emisores, no en sesgo de supervivencia.
* **No los vimos nunca de esta manera, pero ya vimos algo de ellos.** Sus precios
  aparecieron en el estudio del universo (sección transversal) y PLD, PSA, EXR, WELL y ADC
  están en el panel de la fase 6. Nunca se miró su percentil de valuación contra su retorno
  a 5 años, que es lo que se prueba aquí.
* **EPRT** (salida a bolsa en 2018) no tiene ninguna ventana de 5 años con percentil: su
  percentil necesita 36 meses de historia. Aporta su estudio, no evidencia.
* **GNL** aporta muy poca evidencia por la misma razón.
* Con 5 a 7 emisores las pruebas siguen siendo poco finas. Un «no se repite» con estas
  ventanas no prueba que la conclusión original sea falsa, y un «se repite» no la vuelve
  segura.
