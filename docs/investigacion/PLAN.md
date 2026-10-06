# Investigación: ¿cuándo entrar a los REITs y en cuáles?

Fase 0, fijada antes de tocar los datos (6 de octubre de 2026). Lo que aquí se escribe no
se mueve después de ver resultados; si algo tiene que cambiar, el cambio va en el
historial con su motivo y antes de correr lo que afecta. Los parámetros viven en
`src/investigacion/diseno.py` y la prueba 60 los congela.

## La pregunta

Un inversionista mexicano que compra REITs de EE. UU. por el SIC y aporta cada mes
quiere saber si existe una manera eficiente de decidir:

1. **Cuándo entrar al sector**: estar en REITs o en efectivo (T-bills en dólares).
2. **En cuáles**: qué REITs comprar, evitando las trampas.
3. **Cuánto y dónde cada mes**: una regla que junte las dos y que se pueda seguir.

Lo que ya se sabe (estudios anteriores de este repositorio): con O, NNN y WPC esperar a
que esté barato no pagó, porque aun «caro» el REIT le ganó al efectivo; mandar la
aportación al más barato de los tres contra su propia historia sí ayudó (+68 pb al año,
INCONCLUSO por P7). En el universo de 147 REITs, el tercil barato por yield no le ganó a
comprar todos y concentró los recortes de dividendo.

**Lo que esperamos honestamente.** Si un modelo de entrada agrega valor, lo más probable
es que sea esquivando las pocas caídas grandes (1973–74, 1990, 1998–99, 2007–09, 2020,
2022), no ganando más en los años normales. La investigación está diseñada para poder
contestar «no existe» y que esa respuesta valga tanto como un modelo.

## Decisiones del inversionista (6-oct-2026)

| Decisión | Elegido |
|---|---|
| Métrica principal | TIR money-weighted (P9) después de impuestos, aportando 1,000 dólares cada mes, contra aportar siempre al mismo activo (P6) |
| Métrica secundaria | Caída máxima de la riqueza |
| Dónde está el dinero cuando el modelo dice «no entrar» | T-bill a 3 meses en dólares (FRED DTB3) |
| Apalancamiento | Ninguno: la exposición va de 0% a 100% |
| Identificación ante la SEC | La configura el inversionista (`SEC_USER_AGENT`); sin ella, la fase 6 se queda con los emisores ya versionados |
| Precios de los REITs que ya no cotizan | Fuentes gratis primero; el sesgo se mide contra fondos e índices que sí los tuvieron |

Impuestos y costos, los del backtest de reglas: 20% al dividendo y a los intereses (10%
de retención con W-8BEN y 10% de ISR adicional), 10% cedular a la ganancia al vender, y
0.25% de comisión por compra y por venta.

## Las muestras

El error más caro de esta investigación sería encontrar un patrón que solo existe en los
datos con los que se buscó. Por eso los datos se parten antes de verlos y el código lo
hace cumplir (`src/investigacion/muestras.py`):

| Muestra | Qué | Para qué |
|---|---|---|
| **Desarrollo** | EE. UU. hasta diciembre de 2015 | Explorar, estimar, escoger. Todo cálculo se hace sobre datos ya recortados, así que un retorno «siguiente» nunca mira después de 2015 |
| **Validación** | EE. UU. de enero de 2016 en adelante | Escoger entre los candidatos finales. Cada vez que se abre queda en la bitácora |
| **Prueba final** | Los mercados que no hemos visto (Japón, Australia, Singapur, Hong Kong, Reino Unido, Europa continental, Canadá y FIBRAs de México) y un tercio de los emisores de EE. UU. escogido al azar con semilla fija | Una sola vez, con el modelo congelado. Los archivos se guardan con su huella digital al bajarlos y el cargador se niega a abrirlos sin un modelo congelado registrado |

**Contaminación declarada.** La validación de EE. UU. no está limpia del todo: los
estudios anteriores ya mostraron O, NNN, WPC y el universo hasta 2026, y el analista
conoce la historia reciente del mercado. Por eso el veredicto final descansa en los
mercados no vistos y en los emisores sellados.

## Los criterios de éxito

Un modelo se declara **APROBADO** solo si cumple todo esto en la prueba final, con los
umbrales que ya no se mueven:

1. **Le gana a aportar siempre**: al menos +50 pb al año de TIR después de impuestos, **o**
   al menos 30% menos de caída máxima con un costo de a lo más 25 pb al año.
2. **Aguanta afuera**: positivo en la prueba final en conjunto y en al menos dos de cada
   tres mercados con 60 meses o más de datos.
3. **Predice fuera de muestra** mejor que el promedio histórico (R² fuera de muestra
   positivo, prueba de Clark-West con p < 0.05), para las señales que predicen retornos.
4. **Sobrevive a las pruebas múltiples**: Sharpe deflactado de al menos 0.95 y
   probabilidad de sobreajuste (PBO) de a lo más 0.20, con el número de intentos que dice
   la bitácora, no el que uno recuerda.
5. **Al menos 100 apuestas efectivas independientes (P7)**, sumando mercados.
6. **Sigue cumpliendo 1 con un mes de retraso al ejecutar y con el doble de costos.**

Si cumple 1 en desarrollo y validación pero no todo lo demás: **INCONCLUSO**. Si no le gana
a aportar siempre: **RECHAZADO**.

## La bitácora de pruebas

Cada evaluación de una señal, variante o parámetro se anota en
`data/investigacion/bitacora.csv`: fase, familia, nombre, muestra, parámetros, métrica,
valor y commit. Con 100 intentos alguno siempre sale bien por azar; las correcciones por
pruebas múltiples usan el conteo de la bitácora.

## Las fases

0. **Reglas del juego** (este documento, el diseño en código y su prueba).
1. **Literatura con fuentes**: qué se sabe de predecir REITs. Sale una lista de hipótesis
   candidatas, cada una con su fuente y su credibilidad antes de probarla
   (`docs/investigacion/literatura.md`).
2. **Datos**, cada base versionada con manifiesto y validada contra una segunda fuente:
   - Sector sin sesgo de supervivencia: índices Nareit desde 1972; fondos de REITs
     (Cohen & Steers desde 1991, Vanguard desde 1996) para validarlos.
   - Macro de FRED: tasas nominales y reales, curva, crédito (Baa), inflación, empleo,
     precios de inmuebles comerciales, crédito bancario, recesiones.
   - Factores conocidos (Kenneth French) y valuación del mercado (Shiller).
   - Universo de emisores ampliado: los que cotizan hoy y los que desaparecieron, con
     sus estados financieros de la SEC desde 2009 (requiere la identificación del
     inversionista) y un FFO armado que se valida contra el publicado de O, NNN y WPC.
   - Mercados de la prueba final y FIBRAs: se bajan, se sellan y no se miran.
   - La lista de REITs que se pueden comprar desde México por el SIC.
3. **Exploración**, solo en desarrollo: la anatomía de cada caída grande, de dónde salió el
   retorno del sector, y el **techo teórico**: cuántas veces el efectivo le ganó a los
   REITs en los 12 meses siguientes y cuánto valdría saberlo de antemano. Si el techo es
   chico, ningún modelo puede superarlo.
4. **Pre-registro**: las hipótesis, señales, parámetros y pruebas de las fases 5 y 6, en
   su propio commit, antes de correrlas.
5. **Cuándo entrar al sector**: valuación (yield contra su historia, contra la tasa real
   y contra Baa, cap rate implícito), crédito y tasas, tendencia (promedio de 10 meses,
   momentum de 12) y sus combinaciones. Se mide si predicen el retorno de 1, 3, 12, 36 y
   60 meses fuera de muestra, y cuánto ganaría un inversionista: todo de golpe, aportando
   cada mes y con exposición parcial. Se compara contra una mezcla fija con la misma
   exposición promedio, para no confundir timing con estar menos invertido (P8).
6. **En cuáles**: un detector de recortes de dividendo; un filtro de calidad para todo el
   universo y la prueba clave —¿«barato entre los de calidad» le gana a «todos los de
   calidad»?—; momentum, baja volatilidad, tamaño, crecimiento del dividendo y descuento
   contra NAV, revisando que no sean factores ya conocidos con otro nombre.
7. **El modelo final**, por escalera de complejidad: una señal → un compuesto simple →
   regresión regularizada → árboles. Cada escalón se queda solo si le gana al anterior
   fuera de muestra. Se estima siempre con el pasado y se evalúa en el periodo siguiente
   (ventana creciente, al menos 120 meses para estimar, re-estimación anual); los
   hiperparámetros se escogen dentro del pasado. Sale la regla mensual: cuánto aportar y
   a cuál REIT, con impuestos del SIC, comisiones y tipo de cambio.
8. **Prueba final, una sola vez**, con el modelo congelado: APROBADO, INCONCLUSO o
   RECHAZADO según los criterios de arriba.
9. **Entrega**: página en la app, PDF, Excel con fórmulas vivas, la señal de cada mes y un
   plan de seguimiento en vivo con criterios escritos para apagar el modelo.

Al terminar cada fase se informa lo que salió, aunque no sea lo que se esperaba.
