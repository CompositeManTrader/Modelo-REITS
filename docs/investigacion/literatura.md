# Revisión de literatura — ¿Se puede predecir el retorno de los REITs y cómo escogerlos?

**Fase 1 de una investigación pre-registrada.** Consultado en octubre de 2026. Solo literatura; no se corrió ningún backtest.

**Verificación.** Se revisaron contra la fuente original dos de las cifras centrales: el resumen de Ling, Naranjo y Ryngaert (2000) [5] y la tabla de Ghysels, Plazzi, Torous y Valkanov (2013) [9] (R² fuera de muestra del cociente dividendo/precio de −0.686 % mensual y error 15.211 % mayor al semestral). Las dos coinciden.

**Contaminación.** Las fuentes de Nareit citan retornos realizados de 2017 a 2021, que caen en la muestra de validación; ya estaba declarada como no del todo limpia en la fase 0.

---

## 0. Convenciones

**Nivel de lectura** (va entre corchetes junto a cada fuente):

- **[T]** Leí el texto completo o las secciones y tablas relevantes.
- **[R]** Leí solo el resumen (abstract) o la ficha bibliográfica. Las cifras vienen de ahí.
- **[S]** La información llegó por una fuente secundaria, que se indica en cada caso. Es la más débil.

**Fuerza de la evidencia** (la uso en la tabla de hipótesis):

- **Fuerte:** la replicaron al menos dos grupos independientes y tiene pruebas fuera de muestra (*out-of-sample*, OOS) o en varios mercados. Además sobrevive a costos.
- **Media:** está replicada o tiene alguna prueba OOS o internacional. Aun así hay dudas serias: se debilita con el tiempo, depende del régimen o nadie consideró costos.
- **Débil:** viene de un solo estudio o una sola muestra, es solo dentro de muestra (*in-sample*, IS), es una afirmación profesional sin validar o hay resultados contradictorios.

**Cobertura.** Los 8 temas pedidos están cubiertos, pero no todos con la misma profundidad. Estos quedaron **cubiertos de forma parcial**:

- **Inflación como predictor:** solo aparece en Ghysels et al. 2013 [9]. No hice una revisión específica de "REITs como cobertura de inflación".
- **Liquidez como factor de sección cruzada:** solo Goebel et al. 2013 y Chui et al. 2003. No revisé la literatura de microestructura.
- **Crecimiento de AFFO como señal predictiva:** solo una medida contemporánea (Herzberg et al.) y el factor AFFO de Tomtosov et al.
- **J-REITs, A-REITs, S-REITs y Europa:** pocas fuentes por mercado y casi solo resúmenes.
- **FIBRAs:** no hay estudios de predictibilidad.

**Cómo se buscó:** con buscador web y fichas de IDEAS/RePEc, Crossref, NBER, SSRN, repositorios institucionales, Nareit, Green Street y Cohen & Steers. SSRN, Alpha Architect, Cohen & Steers y Research Affiliates bloquearon el acceso automático (error 403). Lo que no pude abrir no se cita como evidencia y aparece en la §4.2.

---

## 1. Resumen ejecutivo (una página)

### 1.1 ¿Cuándo entrar al sector (REITs contra efectivo)?

1. **Las señales de valuación agregada lucen bien dentro de muestra y fallan fuera de muestra.** Probé con el yield de dividendo del índice REIT, la inflación, la pendiente de la curva y el T-bill. La prueba más limpia que encontré es la de Ghysels, Plazzi, Torous y Valkanov (2013) [T], con el índice CRSP/Ziman de 1980 a 2010 y pronósticos OOS de 1996 a 2010. El R² OOS del cociente dividendo/precio de los REITs fue de **−0.69 % mensual, −6.2 % trimestral y −15.2 % semestral**; la inflación dio −3.1 % y la pendiente de la curva −0.5 % mensual. Un pronóstico que promedia todas las variables apenas llega a +0.19 %. Ling, Naranjo y Ryngaert (2000) [R] llegan a lo mismo: el retorno es mucho menos predecible fuera que dentro de muestra, sobre todo en los años 90, y con costos de transacción las ganancias del timing "desaparecen en gran parte". **Esto coincide con su hallazgo (a)**: esperar a que el sector esté barato no le ganó a estar invertido.
2. **Las cifras dentro de muestra son grandes y tientan.** Chiang (2015) [T] reporta un **R² de 34.8 %** a dos años entre 1993 y 2011. Nareit (Case 2017) [T] reporta un **R² de 45 %** a cuatro años con el spread entre el yield REIT y el Treasury a 10 años. Ambas usan ventanas que se traslapan, lo que infla el R², y ninguna tiene prueba OOS formal. Un contraste anecdótico con cifras publicadas por la propia Nareit:
   - Para 2018 su modelo de spread contra Baa pronosticó cerca de **+22 %**; el índice FTSE Nareit All Equity REITs dio **−4.04 %**.
   - Para 2017–2020 su modelo contra el Treasury implicaba **cerca de 13.5 % anual**; lo realizado fue **cerca de 6.2 % anual**.

   Es un solo periodo y no prueba nada por sí mismo, pero ilustra el problema.
3. **Lo que tiene algo de respaldo fuera de muestra:**
   - **Seguimiento de tendencia** (precio contra su media móvil de 10 meses, o retorno de 12 meses contra el T-bill). Hay evidencia en EE. UU.: 20 índices REIT y 274 REITs entre 1980 y 2010 (Glabadanidis 2014 [R]). Hay evidencia global (Moss et al. 2015 [R]). Y está el periodo posterior a la publicación de Faber (2006–2012, medido a nivel de portafolio) [T]. **El beneficio está en recortar las caídas grandes (por ejemplo, evitó buena parte de 2008), no en subir el retorno.** Zakamulin (2014) [R] documenta sesgo de minería de datos en estas reglas y un desempeño "real" menor al reportado. El propio Glabadanidis señala que la regla "funciona igual con retornos generados al azar": su pago se parece al de un put protector, no a una alfa.
   - **Modelos no lineales o de regímenes** (Bianchi y Guidolin 2014; Guidolin, Pedio y Petrova 2023) [R]. Reportan ganancias OOS, pero son complejos, hay pocas réplicas y el riesgo de sobreajuste es alto.
   - **Condiciones de crédito.** Que los bancos endurezcan el crédito a inmuebles comerciales anticipa precios menores en el mercado privado y en el público (Ling, Naranjo y Scheick 2016 [R]; un estudio, dentro de muestra). En modelos de *machine learning*, el spread de crédito Baa−Aaa y la volatilidad del mercado salieron como los predictores macro más importantes (Leow y Lindenthal 2024 [T]).
4. **Los REITs se adelantan al inmueble privado, pero eso no sirve para decidir cuándo entrar a REITs.** El adelanto está muy replicado (Gyourko y Keim 1992; Barkham y Geltner 1995; Oikarinen et al. 2011; Nareit 2023): la correlación con el índice ODCE sube de 0.20 a 0.59 al rezagarla dos trimestres. El problema es la dirección: cuando REITs y privado se separan, **es el índice privado el que se ajusta** (Oikarinen, Hoesli y Serrano 2011 [R]). La brecha entre ambos no predice a los REITs.
5. **La dirección de las tasas no es una regla útil.** Los REITs tuvieron retorno positivo en el 77 % de los periodos de tasas al alza y en el 79 % de los periodos a la baja (Nareit 2026 [T]; análisis contemporáneo, no predictivo). La idea de "comprar después de la última alza de la Fed" descansa en solo 4 ciclos, y la última alza solo se conoce después de que ocurrió.

**Balance:** no encontré una manera eficiente y robusta de decidir cuándo estar en REITs y cuándo en efectivo. La candidata con mejor respaldo es el **filtro de tendencia, entendido como control de riesgo y no como fuente de retorno**. Las señales de valuación agregada deben probarse con restricciones de signo (Campbell y Thompson 2008) y con expectativas bajas.

### 1.2 ¿En cuáles REITs?

1. **El momentum de 6 a 12 meses es la señal más replicada en EE. UU. después de 1990.** La respaldan Chui, Titman y Wei (2003), Derwall et al. (2009), Goebel et al. (2013) y Letdin, Seagraves y Sirmans (2025), y aparece en cinco países (Zhang et al. 2023). **En contra:**
   - Depende del régimen: solo aparece con condiciones monetarias restrictivas (Jensen y Turner 2022) o en mercados al alza (Hung y Glascock 2008).
   - Tomtosov et al. (2025) [T] encuentran **−3.81 % anual** para momentum de 12 meses con tenencia de 12 meses entre 1998 y 2021, con una caída máxima de −78 %. Según ellos, ningún factor funciona después de la crisis de 2008.
   - Los portafolios de ML de Leow y Lindenthal pierden rentabilidad después de 2016.
2. **Calidad del balance: menos deuda y menos riesgo de quiebra.** Los REITs más endeudados que el promedio rinden menos (Giacomini, Ling y Naranjo 2017 [R]). Los REITs en dificultades rinden menos que los sanos (Shen 2021 [R]). Un portafolio largo en los sanos y corto en los de alto riesgo de impago rindió **15 % anual** (Sha et al. 2020 [R]). Letdin et al. (2025) también reportan un factor de calidad positivo. Además, el apalancamiento es justo el determinante principal de los recortes de dividendo (Case, Hardin y Wu 2012 [R]). **Evidencia media.**
3. **Baja volatilidad.** La volatilidad idiosincrática tiene precio negativo: los REITs más volátiles rinden menos (DeLisle et al. 2013; Cakici et al. 2014; Letdin et al. 2025). Ooi, Wang y Webb (2009) encontraron lo contrario. **Evidencia media a débil.**
4. **"Valor" depende de cómo se mida:**
   - **Precio contra NAV** es la versión más fuerte: alfas de **0.9 % a 1.8 % mensual** comprando los REITs con descuento y vendiendo los que cotizan con prima (Gentry, Jones y Mayer 2004 [R]). El problema es que el NAV de Green Street es un dato propietario. Con datos públicos haría falta un sustituto, como el cap rate implícito, que nadie ha validado.
   - **Valor por utilidades o dividendos** tiene evidencia mixta. A favor: Ooi, Webb y Zhou (2007) y Andronoudis et al. (2025). En contra: Tomtosov et al. (P/E: +0.10 % anual, no significativo) y Leow y Lindenthal (tamaño + valor en largo-corto: Sharpe −0.06). Letdin et al. encuentran que el valor solo funciona después de controlar por momentum, calidad y baja volatilidad.
   - **El yield de dividendo alto no tiene respaldo académico robusto** como criterio de selección. En REITs de oficinas e industriales entre 2000 y 2006, los de yield alto rindieron −6.3 % anual relativo al índice y los de yield bajo +6.0 % (Herzberg et al., c. 2008 [T]). **Esto coincide con su hallazgo (b).** Mi lectura: si se usa valor, conviene combinarlo con un filtro de calidad.
5. **Tamaño:** no hay prima confiable.
6. **Reversión de un mes:** es significativa (Letdin et al. 2025), pero rota mucho el portafolio y los costos por el SIC pesan.
7. **Recortes de dividendo:** sus determinantes son conocidos: apalancamiento de mercado alto, *market-to-book* bajo, flujo volátil, payout alto y caídas previas del precio. Pero **no encontré ningún modelo de recortes de REITs validado fuera de muestra.**

### 1.3 Lo que NO encontré (declarado explícitamente)

- Estudios arbitrados sobre la **predictibilidad de las FIBRAs**. Solo hallé una tesis de maestría descriptiva y un artículo de geografía urbana.
- Una **cuantificación del sesgo de supervivencia específica para REITs**. Solo existe la evidencia general de Shumway (1997).
- Respaldo en la literatura para **mandar la aportación del mes al REIT más barato contra su propia historia** (su hallazgo a2). Lo más cercano es la reversión del precio contra NAV, que es una comparación entre REITs y no contra la historia de cada uno.
- Un **modelo de recortes de dividendo de REITs probado fuera de muestra**.
- Documentos primarios de **Cohen & Steers, AQR y Research Affiliates** sobre REITs: estaban bloqueados o no existe nada específico de REITs. Tampoco pude abrir el reporte de S&P Global (2016) sobre factores en REITs (ver §4.2).

---

## 2. Evidencia por tema

### 2.1 Predictibilidad del retorno agregado de REITs

| # | Fuente | Muestra | Hallazgo principal (cifra) | ¿OOS? | Lectura |
|---|---|---|---|---|---|
| [1] | Liu y Mei (1992), *JREFE* 5(4) | EE. UU., mensual 1972–1989 (según [9]) | El retorno de los REITs es más predecible que el de otros activos, en parte por el cap rate. R² ajustado de 0.175, contra 0.087 del mercado (cifra vía [9]) | No | [R]+[S] |
| [2] | Mei y Liu (1994), *JREFE* 8(2) | La misma | El timing tiene "éxito moderado" en inmuebles. R² OOS de 0.083 para eREITs (vía [9]) | Sí (era previa a los 90) | [R]+[S] |
| [3] | Karolyi y Sanders (1998), *JREFE* 17(3) | EE. UU. | Hay una prima de riesgo económica en los REITs que los modelos de varios betas no captan; su predictibilidad es comparable a la de las acciones | No | [R] |
| [4] | Nelling y Gyourko (1998), *JRER* 16(3) | 1975–1995 (ficha de IDEAS) | El retorno mensual es predecible a partir de retornos pasados, pero **no alcanza para ganar después de costos**. Es más fuerte desde 1992 | Parcial | [R] |
| [5] | Ling, Naranjo y Ryngaert (2000), *JREFE* 20(2) | EE. UU., hasta los 90 | El retorno en exceso es **mucho menos predecible fuera que dentro de muestra**, sobre todo en los 90. Sin costos, el timing le gana "modestamente" a comprar y mantener; **con costos, la ganancia desaparece en gran parte** | **Sí** | [R] |
| [6] | Okunev y Wilson (2008), *IRER* 11(2) | EE. UU. | Pronosticar con variables fundamentales "rinde cada vez menos desde los 90". Proponen modelar primas de riesgo variables en el tiempo | Sí (según el resumen) | [R] |
| [7] | Ghysels, Plazzi y Valkanov (2007), *Eur. Fin. Mgmt.* 13(3) | 21 áreas metropolitanas de EE. UU. y REITs agregados | **El cap rate pronostica el retorno.** La parte del cap rate que no explican los fundamentales es la que más predice | No | [R] |
| [8] | Plazzi, Torous y Valkanov (2010), *RFS* 23(9) | Transacciones de inmuebles privados en EE. UU. | La variación del retorno esperado explica ~30 % de la variación del retorno realizado. El cap rate predice el retorno de departamentos, comercio e industria, **pero no el de oficinas** | No | [R] |
| [9] | Ghysels, Plazzi, Torous y Valkanov (2013), *Handbook of Economic Forecasting* 2A | Índice CRSP/Ziman All-Equity REIT, mensual 1980–2010. **OOS de 1996 a 2010**, con 180 meses iniciales para estimar | R² OOS del cociente dividendo/precio de REITs: **−0.686 % mensual, −6.19 % trimestral, −15.21 % semestral**. Inflación −3.1 %, T-bill relativo −2.0 %, pendiente −0.49 %. El retorno rezagado del mercado accionario fue el único positivo (**+4.02 %**). Pronóstico combinado: +0.19 %; +0.62 % con restricción de signo. Conclusión de los autores: el OOS de los REITs "imita" al de las acciones | **Sí** | [T] |
| [10] | Chiang (2015), *JRER* 37(2) | 1981–2011 | Antes de 1993 el yield predice el **crecimiento del dividendo** (43 % a 3 años) y no el retorno (R² máx. 3.69 %). De 1993 a 2011 el yield predice el **retorno**: **R² de 34.83 % a 2 años**. Regresiones traslapadas con bootstrap | No | [T] |
| [11] | Bianchi y Guidolin (2014), *JREFE* 49(1) | Portafolios de REITs de EE. UU. | Los regímenes alcista y bajista de los REITs son abruptos y persistentes. Un inversionista a 5 años pagaría **hasta 5.7 % anual** por pronósticos con cambio de régimen en lugar de lineales | **Sí** | [R] |
| [12] | Akinsomi et al. (2016), *Empirical Economics* 51(3) | 1991–2014 | Los buenos predictores cambian con el tiempo y el horizonte. Los más fuertes: indicadores de la economía, de política monetaria y de sentimiento. Las estrategias le ganan a comprar y mantener | Parcial (el resumen no es claro) | [R] |
| [13] | Guidolin, Pedio y Petrova (2023), *JREFE* 67(1) | REITs y mercado privado de EE. UU. | Modelos recursivos OOS, lineales y de cambio de régimen: mejor predicción a horizonte intermedio y Sharpe "significativamente" mayor; **resiste costos** | **Sí** | [R] |
| [14] | Leow y Lindenthal (2024 WP; *Real Estate Economics*) | 486 REITs, 1990–2021, 94 características × 8 variables macro; ~15 años de prueba | R² OOS mensual, por REIT: OLS con tamaño, valor y momentum **0.31 %**; Elastic Net 3.37 %; árboles extremos 4.52 %; red neuronal 5.01 %. Predictores macro más importantes: **volatilidad del mercado y spread Baa−Aaa**. **No encontré mención de costos en el texto** | **Sí** | [T] |
| [15] | Ling, Naranjo y Scheick (2016), *JMCB* 48(7) | Inmueble comercial privado y público de EE. UU. | **El endurecimiento del crédito anticipa caídas de precio** en el mercado privado y en el público | No (VAR, dentro de muestra) | [R] |
| [16] | Swanson, Theis y Casey (2002), *JREFE* 24(3) | Datos diarios de EE. UU. | El retorno de los REITs es más sensible a la pendiente de la curva que al spread de crédito. En los 90 hubo un cambio que los hizo más sensibles al riesgo de crédito | No (contemporáneo) | [R] |
| [17] | Clayton, Ling y Naranjo (2008, SSRN) | Cap rates nacionales | El sentimiento del inversionista afecta los cap rates aun controlando por fundamentales | No | [R] |
| [19] | Hoesli y Serrano (2010), *JREFE* 41(2) | Diario 1990–2007, 10 países | En mercados REIT maduros, los REITs son más predecibles que las acciones (modelos ARMA-EGARCH). Las estrategias superan a comprar y mantener en los 10 países; **la ganancia cubre los costos en cerca de la mitad** (dato vía [9]) | Sí (parcial) | [R]+[S] |
| [20] | Nareit, Case (2017a) | Dic. 1990–2016 | Retorno promedio a 4 años ≈ 6.61 % + 4.71 × spread (yield REIT − Treasury 10a). **R² 45 %**. Spread de 1.0–1.5 % → 12.1 % anual; de 1.5–2.0 % → 15.0 % | No ("recursivo" con ventanas rodantes de 10 años; no es retención de muestra) | [T] |
| [22] | Nareit, Case (2017c) | 1990–2016 | Exceso de retorno a 3 años contra acciones: R² 38.4 % con spreads contra Treasury, Baa y bonos de alta calidad, más prima o descuento contra NAV. Pronóstico para 2017–2019: **+6.61 pp/año sobre el mercado** | No | [T] |
| [23] | Nareit, Case (2018) | ~1990–2017 | Spread Baa−yield REIT < 80 pb → 20.81 % al año siguiente; de 80 a 180 pb → 13.47 %; > 180 pb → 6.98 %. Pronóstico para 2018: **22.18 %** | No | [T] |
| [24]–[25] | Nareit, cifras realizadas | — | 2018: **−4.04 %**. Índice All Equity REITs: 15,914.73 a fines de 2016 y 20,258.86 a fines de 2020 (≈ **6.2 % anual**). 2017–2019: REITs ≈ 10.3 % anual contra S&P 500 ≈ 15.3 % (aritmética sobre niveles publicados) | — | [T] |
| [26] | Nareit, Pierzak (2023) | 4 ciclos de alzas desde 1990 | Después del ciclo de alzas, los REITs superaron a las acciones y al inmueble privado en todos los horizontes. El texto no da la cifra a 12 meses | No (n = 4; la última alza se identifica después) | [T] |
| [27] | Nareit, Pierzak (2025) | Diario desde 2000 | La correlación entre REITs y el Treasury a 10 años fue positiva el 53.3 % de los días y negativa el 46.7 %. Depende del régimen de la curva | No | [T] |
| [28] | Nareit, Pierzak (2026) | 1T1992–1T2026 | Retorno positivo en el **77.4 %** de los periodos de tasas al alza y en el **78.7 %** de los periodos a la baja (4 trimestres). Pesa más el crecimiento del PIB | No (contemporáneo) | [T] |
| [29] | Green Street (2014) | — | Su herramienta de valuación agregada (*RMZ Forecast Tool*) "ha sido muy útil para identificar periodos de mala valuación". No hay cifras ni validación | No | [T] |

**Síntesis.** El patrón coincide con el de las acciones (Welch y Goyal 2008 [88]): hay una relación positiva entre yield y retorno futuro dentro de muestra, sobre todo después de 1993, pero no sobrevive OOS. Las excepciones con OOS positivo son modelos no lineales o de régimen, combinaciones con restricciones de signo y ML. En todas falta replicación independiente con costos realistas. Las variables de crédito (condiciones de préstamo bancario, spread de default) tienen motivación económica, pero solo evidencia dentro de muestra o dentro de modelos de ML.

**Evidencia en contra (explícita):** [5], [6], [9] y su propio hallazgo (a). También los pronósticos de Nareit de 2017 y 2018 contrastados con lo realizado ([20], [22], [23] contra [24]–[25]).

### 2.2 Prima o descuento contra el NAV

| # | Fuente | Muestra | Hallazgo (cifra) | ¿OOS? | Lectura |
|---|---|---|---|---|---|
| [30] | Gentry, Jones y Mayer (2004), NBER WP 10850 | REITs de EE. UU. desde 1990, NAV de Green Street | Comprar los que cotizan con descuento y vender los que tienen prima da **alfas de 0.9 % a 1.8 % mensual** con poco riesgo. Ni los costos ni las restricciones a la venta en corto lo impiden. El P/NAV es "demasiado volátil" y revierte en el corto plazo | No (es sección cruzada; no hay periodo OOS separado) | [R] |
| [32] | Brounen, Ling y Porras Prado (2013), *REE* 41(3) | Jun. 2006 – sep. 2008 | La actividad de venta en corto explica al menos un tercio de la variación de la prima. **La corrección de la sobrevaluación explica el bajo rendimiento de los REITs con prima** | No | [R] |
| [31] | Clayton y MacKinnon (2001), SSRN | 1996–1999 | La prima sube con el tamaño, la deuda/capital y la liquidez. El componente común es consistente con la "teoría del ruido" | No | [R] |
| [21] | Nareit, Case (2017b) | Dic. 1990 – dic. 2016 | Retorno a 5 años ≈ 11.88 % − 18.97 × prima agregada; **R² 11 %**. Con −9 % a fines de 2016 pronosticó 14.6 % a 19.7 % anual. **Realizado 2017–2021 ≈ 12.5 % anual** (niveles de [25]): positivo, pero abajo del rango | No | [T] |
| [29] | Green Street (2014) | Ene. 1993 – oct. 2013 | Recomendaciones de su modelo basado en NAV, anualizadas: **Compra +24.5 %, Mantener +10.9 %, Venta −0.3 %, Universo +11.5 %**. Son resultados hipotéticos, con igual peso y sin costos; un despacho "Big 4" los verificó hasta oct. 2013 | Sí, en tiempo real (pero con NAV propietario y conflictos de interés) | [T] |
| [33] | Barkham y Ward (1999), *JRER* 18(2) | Inmobiliarias del Reino Unido | El descuento contra NAV se explica tanto por costos de agencia como por traders de ruido | No | [R] |
| [34] | Erol y Tyvimaa (2019), *JPIF* 38(1) | 40 A-REITs, 2008–2018 | La prima depende de la liquidez y del apalancamiento (deuda/capital) | No | [R] |
| [35] | Kumala et al. (2024), *IRFA* 93 | 11 S-REITs de infraestructura, 2017–2021 | Hay evidencia de traders de ruido cuando el precio se aleja del NAV | No | [R] |
| [36] | Letdin, Sirmans y Sirmans (2019, AEA) | EE. UU. | Una mayor dispersión entre las estimaciones de NAV de los analistas se asocia con menor valor | No | [R] |

**Síntesis.** La señal precio contra NAV tiene el mejor resultado de sección cruzada que encontré ([30]), con un mecanismo plausible ([32]). Tiene tres problemas para usted: (1) el NAV de Green Street no es público; (2) [30] es un working paper sin versión publicada que yo haya localizado; (3) a nivel agregado, el R² a 5 años es bajo (11 %) y el periodo posterior a 2016 rindió menos de lo pronosticado. **El cap rate implícito calculado con estados financieros de la SEC sería un sustituto no validado.**

### 2.3 Seguimiento de tendencia y momentum de serie de tiempo

| # | Fuente | Muestra | Hallazgo (cifra) | ¿OOS? | Lectura |
|---|---|---|---|---|---|
| [37] | Faber (2007; actualizado en 2013), *J. Wealth Mgmt.* | 5 clases de activo, NAREIT entre ellas, 1973–2012 | Regla: precio > media móvil de 10 meses → invertido; si no, T-bills. A nivel de portafolio, la caída máxima baja de 46 % a menos de 10 %. **De 2006 a 2012 (tras la publicación) le ganó por más de 2 pp/año** a comprar y mantener. *Las cifras solo de REITs están en figuras que no pude extraer* | Sí (portafolio) | [T] |
| [38] | Glabadanidis (2014), *Int. Rev. Finance* 14(2) | 20 índices REIT y 274 REITs, 1980–2010 | Alfas de **10 % a 15 % anual después de costos**; costos de equilibrio de 5 % a 7 % por operación. **Evita la caída de 2008.** "Funciona igual con retornos aleatorios" y su pago "se parece a un put protector" | No (dentro de muestra, robusto a distintos rezagos) | [R] |
| [39] | CXO Advisory (crítica a [38]) | — | Hay sesgo de *data snooping* por probar muchas ventanas y muchos índices; muestras pequeñas; costos poco realistas | — | [T] |
| [40] | Moss, Clare, Thomas y Seaton (2015), *JREPM* 21(1) | REITs globales | Tendencia más momentum: la volatilidad baja a **8–9 %**, el Sharpe sube **0.1 a 0.5** y la caída máxima queda **por debajo de 30 % (contra 43 %)** | No claro | [R] |
| [41] | Barry (2022), tesis de maestría, UCT | EE. UU., Japón, Reino Unido, Australia, Brasil y Sudáfrica, 2001–2020 | La media móvil y el momentum de serie de tiempo se comportan parecido; el momentum dual tuvo el mejor retorno con el menor riesgo | No | [R] |
| [42] | Moskowitz, Ooi y Pedersen (2012), *JFE* 104(2) | 58 futuros (sin REITs) | El momentum de serie de tiempo de 1 a 12 meses persiste y luego revierte parcialmente | No aplica | [R] |
| [43] | Zakamulin (2014), *J. Asset Mgmt.* 15(4) | Índices accionarios y de bonos de EE. UU. | El desempeño reportado de estas reglas "contiene un considerable sesgo de minería de datos". El desempeño real, con costos, es menor | **Sí** | [R] |

**Síntesis.** Que el filtro de tendencia reduce la volatilidad y las caídas grandes en REITs está razonablemente documentado en EE. UU. y otros países. Que suba el retorno no lo está. Para alguien que aporta cada mes, el costo es quedarse en efectivo durante los rebotes rápidos. **Ninguna de las fuentes que leí mide ese costo para REITs.**

### 2.4 Rezago entre REITs e inmueble privado

| # | Fuente | Muestra | Hallazgo (cifra) | ¿OOS? | Lectura |
|---|---|---|---|---|---|
| [44] | Gyourko y Keim (1992), *REE* 20(3) | NYSE/AMEX contra el índice de avalúos | **Los retornos rezagados de los REITs predicen el índice de avalúos** | No | [R] |
| [45] | Barkham y Geltner (1995), *REE* 23(1) | EE. UU. y Reino Unido | El precio se descubre en el mercado público; la información tarda **un año o más** en llegar al privado. En el Reino Unido el vínculo es más rápido | No | [R] |
| [46] | Gyourko (s.f.), Wharton WP #470 | NCREIF contra NAREIT | Confirma que los REITs de hoy predicen al NCREIF de mañana, por la poca frecuencia de los avalúos | No | [R] |
| [47] | Oikarinen, Hoesli y Serrano (2011), *JRER* 33(1) | NAREIT contra NCREIF | Están cointegrados. **Solo el índice directo se ajusta hacia el equilibrio**: NAREIT adelanta a NCREIF. Hubo una desviación grande al iniciar la "nueva era REIT" | No | [R] |
| [48] | Ling y Naranjo (2015), *REE* 43(1) | 1994–2012 | REITs sin apalancamiento, ajustados por sectores y gastos: **+49 pb/año sobre el privado**. Los REITs no traen información inmobiliaria *adicional* para predecir al privado; responden más rápido a la misma información | No | [R] |
| [49] | Hoesli y Oikarinen (2012), *JIMF* 31(7) | EE. UU., Reino Unido y Australia | A largo plazo los REITs se parecen mucho más al inmueble directo que a las acciones | No | [R] |
| [50] | Nareit, Funari (2023) | REITs contra ODCE | Correlación contemporánea de **0.20** (0.24 en los sectores tradicionales). **Con dos trimestres de rezago, 0.59 (0.64)**. CEM: **0.91** quitando el rezago, 1998–2020 | No | [T] |

**Síntesis.** Este es el resultado **más fuerte de toda la revisión**: está replicado, viene de varios grupos y de tres países. Pero apunta en la dirección equivocada para su pregunta. Sirve para anticipar el índice privado, no para decidir cuándo entrar a REITs, y según [47] la brecha entre ambos la cierra el privado.

### 2.5 Factores de sección cruzada en REITs

| # | Fuente | Muestra | Hallazgo (cifra) | ¿OOS / costos? | Lectura |
|---|---|---|---|---|---|
| [51] | Chui, Titman y Wei (2003a), *REE* 31(3) | Antes y después de 1990 | Antes de 1990 predecían el momentum, el tamaño, la rotación y la cobertura de analistas. **Después de 1990 domina el momentum**, y es más fuerte en REITs grandes y líquidos | No | [R] |
| [52] | Chui, Titman y Wei (2003b), *J. Financial Markets* 6(3) | La misma | No hay momentum antes de 1990; después es "fuerte y prevalente" | No | [R] |
| [53] | Derwall, Huij, Brounen y Marquering (2009), *FAJ* 65(5) | REITs y fondos REIT de EE. UU. | El momentum es "fuerte y prevalente" y los modelos convencionales no lo explican. Explica buena parte de la alfa de los fondos activos | No | [R] |
| [54] | Hung y Glascock (2008), *JREFE* 37(1) | EE. UU. | El momentum es **mayor en mercados al alza** y aumenta después de 1992 | No | [R] (versión de congreso ERES 2005) |
| [55] | Hung y Glascock (2010), *JREFE* 41(2) | EE. UU. | El momentum es mayor con volatilidad alta; los perdedores tienen más riesgo idiosincrático | No | [R] (SSRN) |
| [56] | Goebel, Harrison, Mercer y Whitby (2013), *JREFE* 47(3) | 1993–2009 | Controlando por momentum, se asocian con el retorno **el book-to-market, la propiedad institucional y la iliquidez**. El tamaño y la cobertura de analistas no. Todo depende del ciclo de tasas | No | [R] |
| [57] | Jensen y Turner (2022), *JRER* 44(3) | EE. UU. | El momentum **solo aparece con condiciones monetarias restrictivas** y está ligado al dividendo | No | [R] |
| [58] | Parhizgari y Pavlova (2009), ERES | REITs globales, 2000–2008 | El momentum **no es significativo en el auge** y sí en la caída | No | [R] |
| [59] | Ooi, Webb y Zhou (2007), *JRER* 29(1) | EE. UU. | **Desde 1990 los REITs de valor rinden más** sin más riesgo; en los 80 no. La prima varía en el tiempo | No | [R] |
| [60] | Ooi, Wang y Webb (2009), *JREFE* 38(4) | EE. UU. | La volatilidad idiosincrática se relaciona **positivamente** con el retorno (contradice a [61] y [62]) | No | [R] |
| [61] | DeLisle, Price y Sirmans (2013), *JRER* 35(2) | 1996–2010 | La volatilidad idiosincrática tiene **precio negativo**; la sistemática no tiene precio | No | [R] |
| [62] | Cakici, Erol y Tirtiroglu (2014), *JREFE* 48(3) | 1981–2010 | La relación entre volatilidad idiosincrática y retorno es negativa y cambia en el tiempo. El momentum gana peso después de que el primer REIT entra al S&P 500 (oct. 2001) | No | [R] |
| [63] | Bond y Xue (2017), *JREFE* 54(3) | EE. UU. | **La inversión y la rentabilidad predicen el retorno** más allá de los modelos estándar | No | [R] |
| [64] | Giacomini, Ling y Naranjo (2017), *REE* 45(4) | EE. UU. | **Los REITs más endeudados que el promedio rinden menos.** Matiz: los que están por encima de *su propia meta* de deuda rinden mejor ajustado por riesgo; cierran la brecha a 17 % por año | No | [R] |
| [66] | Shen (2021), *JREFE* 62(3) | 1982–2017 | La frecuencia esperada de default predice las quiebras de REITs. **Los REITs en dificultades rinden menos que los sanos**, y la diferencia crece al ajustar por valor y tamaño | No | [R] |
| [67] | Sha, Wang, Bu y Mansley (2020), *IJSPM* 24(5) | EE. UU. | Largo en REITs de bajo riesgo de default y corto en los de alto: **15 % anual**. El beta del CAPM explica parte | No | [R] |
| [65] | Gyamfi-Yeboah, Ling y Naranjo (2012), *JIMF* 31(7) | 1995–2009 | **No hay deriva posterior al anuncio de utilidades** en el agregado; solo en las sorpresas positivas más grandes. Los REITs incorporan la información rápido | No | [R] |
| [68] | Letdin, Seagraves y Sirmans (2025), SSRN 5250691 | CRSP-Ziman, 1987–2023 | Seis factores. **Reversión de corto plazo, momentum, calidad y baja volatilidad** dan retornos ajustados significativos. **El tamaño rinde menos.** El valor solo funciona tras controlar por momentum, calidad y baja volatilidad. Son "robustos a costos de transacción". Probaron más de 15,000 predictores; casi todos quedan absorbidos | No dice | [S] (resumen vía Quantpedia; SSRN bloqueado) |
| [69] | Andronoudis, Guidolin y Pedio (2025), *JPM* 52(3) | 1993–2020 | Tamaño, valor, inversión y momentum funcionan; **la rentabilidad no**. Las estrategias *smart beta* superan al índice | No claro | [R] |
| [70] | Tomtosov, Rechmedina y Dobrynskaya (2025), HSE WP | 195 REITs (Bloomberg), 1998–2021; largo-corto 50/50 con igual peso | Retorno anual por factor: AFFO **−0.64 %**, tamaño 1.00 %, rentabilidad 0.46 %, valor por P/E **0.10 %**, momentum de 12 meses con tenencia de 12 **−3.81 %** (caída máx. −78 %). **Ningún factor da alfa sistemática, sobre todo después de 2008.** El "momentum de factores" da 5.68 % (t ≈ 1.9) | No. *Ojo: posible sesgo de supervivencia en el universo de Bloomberg* | [T] |
| [14] | Leow y Lindenthal (2024) | 1990–2021 | ML de solo largos: Sharpe **0.60 contra 0.49** del índice ponderado por valor. Largo-corto: árboles extremos 0.35, red neuronal 0.29, Elastic Net −0.11, **OLS tamaño + valor −0.06**. **Rentabilidad menor después de 2016** | Sí; sin costos | [T] |
| [71] | Herzberg, Bordo y Kessler (c. 2008), *Wharton Real Estate Review* | ~30 REITs de oficinas e industriales, 2000–2006 | Retorno anual relativo al índice NAREIT: **yield alto (7.8 % promedio) −6.3 %; yield bajo (4.5 %) +6.0 %**. Payout alto −5.6 %, bajo +3.3 %. Crecimiento de FFO alto +5.6 %, bajo −5.9 % (este último es contemporáneo, no predictivo). No queda claro si el yield se midió al inicio del periodo | No | [T] |
| [29] | Green Street (2014) | Ago. 2002 – ago. 2012 | 10 pp más de apalancamiento frente al sector se asocian con **5 pp menos de retorno anual** (R² 0.46) | No | [T] |
| [74] | Quantpedia (s.f.) | Sobre [53] | Advierte que "un estudio reciente (Huerta y Rivas)" encuentra que el momentum en REITs **pierde significancia**. No localicé el estudio primario | — | [S] |

**Síntesis y evidencia en contra.**

- **Momentum:** es la señal más replicada después de 1990. Pero depende del régimen ([54], [57], [58]) y fracasa en la versión de 12/12 meses desde 1998 ([70]). Tome en cuenta el decaimiento general tras la publicación (~50 %, McLean y Pontiff [91]).
- **Calidad, baja deuda y bajo riesgo de quiebra:** es la familia más coherente ([64], [66], [67], [68], [29]) y conecta con los recortes de dividendo (§2.6). Todo es dentro de muestra.
- **Baja volatilidad:** los resultados se contradicen ([60] contra [61], [62], [68]).
- **Valor:** mixto; depende de la medida ([59], [69] y [30] a favor; [70] y [14] en contra). El **yield alto como criterio** no tiene respaldo ([71] y su hallazgo b).
- **Tamaño:** no tiene prima ([56], [68]).
- **Deriva posterior a utilidades:** no hay en el agregado ([65]).

### 2.6 Predicción de recortes de dividendo y dificultades financieras

| # | Fuente | Muestra | Hallazgo (cifra) | ¿OOS? | Lectura |
|---|---|---|---|---|---|
| [75] | Case, Hardin y Wu (2012), *REE* 40(3) | REITs de EE. UU. en la crisis de liquidez 2008–2009 | Logit multinomial: **un apalancamiento de mercado mayor o un market-to-book menor aumentan la probabilidad de recortar, suspender o pagar en acciones.** Ojo: los que recortaron tuvieron **retornos anormales positivos después del anuncio** | No | [R] (vía Crossref) |
| [76] | Bradley, Capozza y Seguin (1998), *REE* 26(4) | 1985–1992 | El payout es menor cuando el flujo esperado es más volátil, medido por apalancamiento, tamaño y diversificación. Hay una penalización en el precio por recortar | No | [R] |
| [77] | Hardin y Hill (2008), *REE* 36(2) | EE. UU. | Pagar más del mínimo obligatorio se asocia con buen desempeño operativo, recompras y acceso a deuda bancaria de corto plazo | No | [R] |
| [78] | Pettenuzzo, Sabbatucci y Timmermann (2020), CEPR DP14921 | Empresas de EE. UU. (no solo REITs), COVID-19 | **Suspendieron más las empresas con mucha deuda, poca rentabilidad y la peor caída previa del precio.** Las que suspendieron tuvieron retornos anormales negativos; las que redujeron sin eliminar, positivos | No | [R] |
| [79] | Wright, Huerta y Weeks (2024), ERES | REITs de EE. UU., COVID-19 | El resumen no reporta resultados | — | [R] |
| [80] | Kallberg, Liu y Srinivasan (2003), *REE* 31(3) | Índice REIT | No se rechaza el modelo de valuación por dividendos: los precios de los REITs no son excesivamente volátiles frente a sus dividendos | No | [R] |
| [66], [67] | Shen (2021); Sha et al. (2020) | — | Las medidas de riesgo de default **predicen las quiebras de REITs** y los REITs en dificultades rinden menos | No | [R] |

**Síntesis.** Los determinantes son consistentes entre estudios y épocas: apalancamiento, market-to-book bajo (es decir, precio caído o yield alto), payout alto, flujo volátil y retornos previos negativos. **No hay un modelo específico de REITs validado fuera de muestra.** Un matiz importante para quien aporta cada mes: [75] y [78] sugieren que **vender después del recorte** puede ser peor que mantener. La trampa está en comprar antes del recorte.

### 2.7 Riesgos metodológicos

| Riesgo | Evidencia | Lectura |
|---|---|---|
| **Cambio estructural de 1990 a 1993** (era moderna de los REITs) | Después de 1992 los REITs se comportan más como acciones que como bonos ([81] Glascock, Lu y So 2000). De 1978 a 1998 pasaron de depender de acciones grandes a un factor de acciones pequeñas más uno inmobiliario ([82] Clayton y MacKinnon). Los predictores de sección cruzada cambian alrededor de 1990 ([51], [52]). El yield pasa de predecir dividendos a predecir retornos en 1993; ya es "práctica estándar" partir la muestra en la *Revenue Reconciliation Act* de 1993 ([10]). El valor no existía en los 80 ([59]). Hay más momentum después de 1992 ([54]). Más sensibilidad al crédito en los 90 ([16]). Gran desviación entre REITs y privado al inicio de la nueva era ([47]) | [R]/[T] |
| **Entrada al S&P 500 (oct. 2001)** | Al incluir REITs en índices generales sube la correlación de los REITs que quedaron fuera con el índice, por fricciones de mercado más que por sentimiento ([83] Ambrose, Lee y Peek 2007). El momentum gana peso después de 2001 ([62]) | [R] |
| **Sector GICS de bienes raíces (anunciado el 10 nov. 2014; vigente el 16 sep. 2016)** | Precio más alto, más operación y menos volatilidad en el sector nuevo ([84] Goodwin y Liu 2021). Retornos anormales en el anuncio y en la implementación, mayores en los grandes, con "efectos de encuadre" ([85] Bao, Brady y Wang 2020) | [R] |
| **Sesgo de supervivencia** | En CRSP faltan los retornos de las empresas que salieron de bolsa por malas razones, y son grandes ([86] Shumway 1997; general, no de REITs). CRSP/Ziman cubre "todos los REITs" de NYSE, NYSE American y NASDAQ desde 1980 ([87]); **la página de UCLA anuncia que la base se descontinúa el 31 de oct. de 2026**, con una última actualización hasta 3T2026. **No encontré una cuantificación específica para REITs.** El universo actual de Bloomberg de [70] puede estar sesgado | [R]/[T] |
| **Minería de datos y decaimiento tras publicar** | En la versión SSRN de 2012 de McLean y Pontiff, 56 anomalías caen **~15 % fuera de muestra** (no significativo) y **~50 % después de publicarse** ([91]). Un factor nuevo debería exigir **t > 3.0** ([92] Harvey, Liu y Zhu). El *Deflated Sharpe Ratio* corrige por número de pruebas y no normalidad ([93]). De 29 predictores nuevos del premio accionario, la mitad no es significativa ni dentro de muestra, y de los que sí, la mitad falla OOS ([90] Goyal, Welch y Zafirov). Las restricciones de signo mejoran el OOS ([89] Campbell y Thompson) | [R] |
| **Regresiones traslapadas y regresores persistentes** | Los R² de 34 % a 45 % de [10] y [20] usan horizontes traslapados. [9] corrige el sesgo de muestra pequeña (Stambaugh) y la relación queda "positiva pero en gran medida no significativa" | [T] |

### 2.8 Evidencia en otros mercados

| # | Fuente | Mercado y muestra | Hallazgo | Lectura |
|---|---|---|---|---|
| [19] | Hoesli y Serrano (2010) | 10 países, 1990–2007 | Los REITs son más predecibles que las acciones en los regímenes REIT maduros; la ganancia cubre los costos en cerca de la mitad de los países | [R]+[S] |
| [45] | Barkham y Geltner (1995) | EE. UU. y Reino Unido | El precio se descubre en el mercado público; el vínculo es más rápido en el Reino Unido | [R] |
| [49] | Hoesli y Oikarinen (2012) | EE. UU., Reino Unido y Australia | A largo plazo, los REITs se parecen al inmueble directo | [R] |
| [94] | Hamelink y Hoesli (2004), *REE* 32(3) | Internacional, feb. 1990 – abr. 2003 | Domina el factor país. El factor valor/crecimiento es volátil y pesa mucho. El tamaño tiene efecto negativo | [R] |
| [95] | Schulte y Dechant (2011), ERES | 275 empresas de 16 países europeos, 1988–2009 | **Hay efecto valor y no hay efecto tamaño** | [R] |
| [96] | Zhang, Li y Roca (2023), *Heliyon* | Australia, Reino Unido, EE. UU., Japón y Canadá, 2000–2022 | Exposición positiva al momentum en todos los países (coeficientes de ~0.14 a 0.50). Son cargas factoriales, no portafolios ordenados | [R] |
| [40], [41] | Moss et al. (2015); Barry (2022) | Global; seis países | El filtro de tendencia reduce la volatilidad y las caídas | [R] |
| [97] | Shum y Wong (2009/2010), *J. Asia Bus. Stud.* | J-REITs | Beta positivo en mercados al alza y negativo a la baja; los inversionistas parecen poco diversificados | [R] |
| [33], [34], [35] | Barkham y Ward; Erol y Tyvimaa; Kumala et al. | Reino Unido, Australia y Singapur | Estudian los **determinantes** de la prima contra NAV, no si predice el retorno | [R] |
| [98] | Casiano Hernández (2022), tesis de maestría, UAQ | **FIBRAs**, 2016–2020 | Solo el **30 %** de las FIBRAs de la muestra superó a CETES ajustando por riesgo sistemático (CETES ≈ 6.3 %). Betas contra el S&P 500 de −0.07 a 0.48. Es descriptivo, no predictivo | [T] |
| [99] | Gasca y Castro (2021), *Revista INVI* | FIBRAs | Financiarización y geografía de los portafolios; nada sobre retornos | [R] |

**Síntesis:** la evidencia internacional apoya, débilmente, el momentum, el valor (en Europa) y los filtros de tendencia, así como el liderazgo del mercado público sobre el privado. **No hay evidencia de predictibilidad para las FIBRAs.**

---

## 3. Tabla de hipótesis candidatas para el pre-registro

**Notas de cálculo comunes:**

- **Precios y dividendos:** precios ajustados por dividendos; dividendos por fecha ex.
- **Tasas (FRED):** DGS10 (Treasury 10 años), DFII10 (TIPS 10 años, **solo desde ene. 2003**), BAA, AAA, BAA10YM (desde 1953), TB3MS, T10Y3M, FEDFUNDS, CPIAUCSL.
- **Encuesta de crédito bancario (SLOOS):** DRTSCREL cubre 1990T3–2013T3 y está descontinuada; desde 2013T4 hay que empalmarla con SUBLPDRCSC, SUBLPDRCSN y SUBLPDRCSM.
- **Estados financieros:** de los 10-K y 10-Q de la SEC (EDGAR/XBRL), usando la **fecha de presentación** y no la de cierre del periodo. FFO y AFFO no están estandarizados en XBRL; salen de los suplementos en 8-K.

### 3.1 Cuándo entrar (REITs contra efectivo)

| ID | Hipótesis / señal | Cálculo con datos públicos | Horizonte | Dirección esperada | Fuentes | Fuerza | Evidencia en contra |
|---|---|---|---|---|---|---|---|
| T1 | Filtro de tendencia por media móvil | Retorno total del universo REIT (igual peso) o de un ETF amplio. Señal = precio de fin de mes > media de 10 meses. Si no se cumple, la aportación y la posición se van a CETES o T-bill | 1 mes | **Menor volatilidad y caída máxima**, Sharpe ≥ al de comprar y mantener; el retorno total puede ser igual o **menor** | [37], [38], [40], [41] | **Media** (para riesgo) / **Débil** (para retorno) | [43] (minería de datos); [39]; [38] mismo ("funciona con retornos aleatorios"); costo de quedarse fuera en los rebotes, sin medir para REITs |
| T1b | Momentum de serie de tiempo | Retorno del índice REIT de 12 meses > retorno del T-bill de 12 meses → invertido | 1 mes | Igual que T1 | [42], [40], [41] | Débil a media | [43]; [42] no incluye REITs |
| T2 | Yield de dividendo agregado | Yield del índice: dividendos de 12 meses / precio (o su logaritmo) | 12, 24 y 36 meses | + (yield alto → retorno mayor). Probar OOS con restricción de signo | [10], [1] | **Débil** | [9] (R² OOS de −0.7 % a −15 %); [5]; [88]; su hallazgo (a) |
| T3 | Spread de valuación contra bonos | Yield REIT − DGS10; yield REIT − BAA; y yield REIT − DFII10 desde 2003 | 12 a 48 meses | + | [20], [22], [23] | **Débil** | Sin OOS formal; pronóstico de 2018 (+22 % contra −4.04 %) y de 2017–2020 (13.5 % contra ≈6.2 %) |
| T4 | Endurecimiento del crédito a inmuebles comerciales | SLOOS empalmada (porcentaje neto de bancos que endurecen), con rezago a la fecha de publicación | 1 a 4 trimestres | − (más endurecimiento → menor retorno) | [15] | **Débil a media** | Un solo estudio, VAR dentro de muestra; pocos ciclos; la serie cambia en 2013 |
| T5 | Spread de default | BAA − AAA (o BAA10YM) | 1 a 12 meses | + (spread alto → mayor retorno esperado, según la lectura de [14]) | [14] | **Débil** | Su importancia sale de un ML no lineal, no de una prueba univariada; signo no verificado en REITs |
| T6 | Rezago del mercado accionario | Retorno total del S&P 500 en el mes t | Mes t+1 | **Bilateral**: la tabla de [9] no reporta el signo | [9] (R² OOS +4.0 %, 1996–2010) | **Débil** | Una sola muestra; posiblemente dominada por 2008 |
| T7 | Pausa de la Fed | "Pausa" = FEDFUNDS sin alzas durante ≥ 6 meses después de un ciclo de alzas. Regla implementable en tiempo real | 12 meses | + (REITs sobre efectivo y acciones) | [26] | **Débil** | Solo 4 ciclos; [26] identifica la última alza después del hecho; [28] |
| T8 | Cap rate implícito agregado contra tasa real | NOI de 12 meses (10-K/10-Q) / (capitalización + deuda neta + preferentes), agregado; menos DFII10 | 12 a 36 meses | + | [7], [1], [29] | **Débil** | Sin OOS; [8] (no funciona en oficinas); el NOI no está estandarizado |
| T0 | **Hipótesis nula de referencia** | Ninguna señal supera a "aportar cada mes y mantener" en riqueza final ni en Sharpe, después de costos | — | — | [5], [9], [88], su hallazgo (a) | **Fuerte como expectativa a priori** | [11], [13] (modelos de régimen con OOS positivo) |

### 3.2 En cuáles (selección entre REITs)

| ID | Hipótesis / señal | Cálculo con datos públicos | Horizonte | Dirección esperada | Fuentes | Fuerza | Evidencia en contra |
|---|---|---|---|---|---|---|---|
| S1 | Momentum 12-1 | Retorno total de t−12 a t−1 (sin el último mes). Comprar el tercil o quintil superior. Variantes 6-1 y dentro de cada sector | 1 a 6 meses | + | [51], [52], [53], [56], [68], [96] | **Media** | [70] (12/12: −3.81 % anual, caída máx. −78 %); [57], [54], [58] (depende del régimen); [74]; [14] (decae después de 2016); [91] |
| S2 | Apalancamiento bajo frente al sector | Deuda neta / (deuda neta + capitalización) o deuda / EBITDA (10-K), comparado con la mediana de su sector inmobiliario | 12 meses | + (menos deuda → más retorno) | [64], [29], [68] | **Media** | Matiz de [64] (estar sobre la propia meta de deuda puede rendir mejor); [29] es de 10 años y dentro de muestra; [70] (rentabilidad ≈ 0) |
| S3 | Evitar riesgo de quiebra | Distancia al default tipo Merton: capitalización, volatilidad de 12 meses, deuda del 10-K. Excluir el decil o quintil de más riesgo | 12 meses | + (los sanos le ganan a los estresados) | [66], [67] | **Media** | [67] (el beta del CAPM explica parte); sin OOS; no está probado en REITs de neto arrendamiento (*net lease*) |
| S4 | Baja volatilidad | Volatilidad idiosincrática: desviación estándar de los residuales diarios contra el índice REIT, 12 meses (o volatilidad total) | 1 a 12 meses | − (más volatilidad → menos retorno) | [61], [62], [68] | **Media a débil** | [60] (relación positiva); [62] (la relación cambia en el tiempo) |
| S5 | Valor por activos (sustituto del P/NAV) | Cap rate implícito por emisor, comparado dentro de su sector | 6 a 12 meses | + (cap rate alto → más retorno) | [30], [32], [21], [29] | **Media** para el P/NAV de Green Street; **débil** para este sustituto | NAV propietario; [30] no publicado; NOI poco estandarizado; S&P (2016) no verificado |
| S6 | Valor por flujo | Yield de AFFO o FFO = FFO por acción de 12 meses / precio (8-K) | 12 meses | + | [59], [69], [56] | **Débil** | [70] (AFFO −0.64 %, P/E +0.10 %); [14] (tamaño + valor, Sharpe −0.06); [68] (el valor solo funciona con controles) |
| S7 | **Control negativo:** yield de dividendo alto sin filtro | Tercil o quintil de mayor yield de 12 meses | 12 meses | **Sin exceso de retorno; más recortes** | Su hallazgo (b); [71] | Débil como señal positiva; ya contradicha | [59] (el valor sí funcionó desde 1990 con otras medidas) |
| S8 | **Valor con filtro de calidad** | S6 o S5 aplicado solo a REITs con apalancamiento ≤ mediana del sector, payout (dividendo / AFFO) ≤ umbral fijado de antemano, sin decil de riesgo de quiebra (S3) y sin momentum muy negativo | 12 meses | + frente al universo; **menos recortes** que S7 | [68] (el valor funciona controlando por calidad, baja volatilidad y momentum); [64], [66], [75], [76] | **Débil a media** (es una inferencia de combinar estudios; no está probada así) | Riesgo de sobreajuste por cuántos filtros se elijan; fijar umbrales antes de ver los datos |
| S9 | Reversión de corto plazo | Retorno del último mes; comprar el quintil inferior | 1 mes | − (perdedores del mes rebotan) | [68] | **Débil** | Rotación alta; costos del SIC y tipo de cambio; resumen [S] |
| S10 | Inversión baja y rentabilidad alta | Crecimiento anual de activos totales (10-K); rentabilidad operativa (NOI o utilidad operativa / activos) | 12 meses | Crecimiento de activos −; rentabilidad + | [63], [69] | **Débil** | [69] (la rentabilidad no funciona); [70] (≈ 0) |
| S11 | Tamaño (control) | Capitalización de mercado | 12 meses | **Sin prima** (nula) | [56], [68], [95] | Media como nula | [51] (antes de 1990) |
| S12 | **Su hallazgo a2:** aportar al más barato contra su propia historia | Z-score del yield de cada REIT contra su historia de 36 a 60 meses; la aportación va al de z más alto. Comparar contra aportación con igual peso | 1 a 12 meses | + (leve) | Ninguna directa; lo más cercano es la reversión del P/NAV entre REITs ([30], [32]) | **Sin respaldo en la literatura** (solo su resultado propio) | Un yield alto frente a su historia puede anticipar un recorte ([75]); es probable que interactúe con S2 y S3 |

### 3.3 Recortes de dividendo

| ID | Hipótesis / señal | Cálculo con datos públicos | Horizonte | Dirección esperada | Fuentes | Fuerza | Evidencia en contra |
|---|---|---|---|---|---|---|---|
| D1 | Logit de recorte | Probabilidad de recorte o suspensión en 12 meses con: apalancamiento de mercado, market-to-book, payout (dividendo / FFO o AFFO), retorno de 12 meses, rentabilidad, tamaño, volatilidad del flujo. Estimar en ventana expansiva y evaluar OOS con AUC y Brier | 12 meses | Más deuda, menos M/B, más payout, peor retorno previo → más probabilidad | [75], [76], [78], [77] | **Media** para los determinantes; **débil** para la predicción OOS (no hay) | Muestras de crisis (2008–09 y COVID); [78] no es de REITs |
| D2 | Yield extremo dentro del sector | Yield > percentil 90 de su sector | 12 meses | Más probabilidad de recorte | Su hallazgo (b); [75] (M/B bajo) | **Débil** | Sector y apalancamiento pueden confundir el efecto |
| D3 | ¿Vender después del recorte? | Retorno de los que recortan, de t+1 a t+12 tras el anuncio, contra sus pares | 1 a 12 meses | **No negativo** (vender después no ayuda) | [75], [78] | **Débil a media** | Distinguir reducción de suspensión ([78]) |

### 3.4 Recomendaciones para el diseño pre-registrado (derivadas de §2.7)

1. **Muestra principal desde 1993-94**, con 2001 y 2016 como pruebas de quiebre en submuestras. Los resultados previos a 1990 no se trasladan ([10], [51], [59]).
2. **Medida principal OOS:** el R² OOS de Welch y Goyal para timing y la riqueza final contra "aportar y mantener" para el inversionista mensual. Reportar también versiones con restricción de signo ([89]).
3. **Universo sin sesgo de supervivencia:** incluir REITs deslistados, fusionados o quebrados con su retorno de salida ([86]). Si se usa CRSP/Ziman, descargarlo antes de su descontinuación (31 oct. 2026, [87]).
4. **Corrección por pruebas múltiples:** hay unas 20 hipótesis en la tabla. Usar Holm o Bonferroni, o un umbral de t > 3 ([92]), y el Deflated Sharpe ([93]). Las que ya se probaron (S7 y el hallazgo a) cuentan como pruebas hechas.
5. **Costos realistas del SIC:** comisión, diferencial de compra-venta y tipo de cambio MXN/USD. Rechazar las señales de alta rotación (S9) si no los sobreviven ([4], [5]).
6. **Rezagos de publicación:** SLOOS por fecha de publicación; estados financieros por fecha de presentación en EDGAR; FFO por fecha del 8-K.

---

## 4. Bibliografía

Los números coinciden con los de las tablas.

### 4.1 Fuentes abiertas y leídas

**Predictibilidad agregada, tasas y crédito**

1. Liu, C. H. y Mei, J. (1992). *The Predictability of Returns on Equity REITs and Their Co-movement with Other Assets.* Journal of Real Estate Finance and Economics, 5(4), 401–418. https://ideas.repec.org/a/kap/jrefec/v5y1992i4p401-18.html [R; cifras vía 9]
2. Mei, J. y Liu, C. H. (1994). *The Predictability of Real Estate Returns and Market Timing.* JREFE, 8(2), 115–135. https://ideas.repec.org/a/kap/jrefec/v8y1994i2p115-35.html [R; cifras vía 9]
3. Karolyi, G. A. y Sanders, A. B. (1998). *The Variation of Economic Risk Premiums in Real Estate Returns.* JREFE, 17(3), 245–262. https://ideas.repec.org/a/kap/jrefec/v17y1998i3p245-62.html [R]
4. Nelling, E. y Gyourko, J. (1998). *The Predictability of Equity REIT Returns.* Journal of Real Estate Research, 16(3), 251–268. https://ideas.repec.org/a/taf/rjerxx/v16y1998i3p251-268.html [R]
5. Ling, D. C., Naranjo, A. y Ryngaert, M. D. (2000). *The Predictability of Equity REIT Returns: Time Variation and Economic Significance.* JREFE, 20(2), 117–136. https://ideas.repec.org/a/kap/jrefec/v20y2000i2p117-36.html [R]
6. Okunev, J. y Wilson, P. J. (2008). *Predictability of Equity REIT Returns: Implications for Property Tactical Asset Allocation.* International Real Estate Review, 11(2), 32–46. https://ideas.repec.org/a/ire/issued/v11n022008p32-46.html [R]
7. Ghysels, E., Plazzi, A. y Valkanov, R. (2007). *Valuation in US Commercial Real Estate.* European Financial Management, 13(3), 472–497. https://ideas.repec.org/a/bla/eufman/v13y2007i3p472-497.html [R]
8. Plazzi, A., Torous, W. y Valkanov, R. (2010). *Expected Returns and Expected Growth in Rents of Commercial Real Estate.* Review of Financial Studies, 23(9), 3469–3519. https://ideas.repec.org/a/oup/rfinst/v23y2010i9p3469-3519.html [R]
9. Ghysels, E., Plazzi, A., Torous, W. y Valkanov, R. (2013). *Forecasting Real Estate Prices.* En *Handbook of Economic Forecasting*, vol. 2A, 509–580. North-Holland. Versión de trabajo: https://uncipc.com/wp-content/uploads/2017/06/forecasting_real_estate_prices.pdf [T: sección 4 y tabla 7]
10. Chiang, K. C. H. (2015). *What Drives REIT Prices? The Time-Varying Informational Content of Dividend Yields.* Journal of Real Estate Research, 37(2). https://www.uvm.edu/~kcchiang/BSAD%20289/Article2.pdf [T]
11. Bianchi, D. y Guidolin, M. (2014). *Can Linear Predictability Models Time Bull and Bear Real Estate Markets? Out-of-Sample Evidence from REIT Portfolios.* JREFE, 49(1), 116–164. https://ideas.repec.org/a/kap/jrefec/v49y2014i1p116-164.html [R]
12. Akinsomi, O., Aye, G. C., Babalos, V., Economou, F. y Gupta, R. (2016). *Real Estate Returns Predictability Revisited: Novel Evidence from the US REITs Market.* Empirical Economics, 51(3), 1165–1190. https://ideas.repec.org/a/spr/empeco/v51y2016i3d10.1007_s00181-015-1037-5.html [R]
13. Guidolin, M., Pedio, M. y Petrova, M. T. (2023). *The Predictability of Real Estate Excess Returns: An Out-of-Sample Economic Value Analysis.* JREFE, 67(1), 108–149. https://ideas.repec.org/a/kap/jrefec/v67y2023i1d10.1007_s11146-020-09769-2.html [R]
14. Leow, K. y Lindenthal, T. (2024). *Enhancing Real Estate Investment Trust (REIT) Return Forecasts via Machine Learning.* Cambridge Land Economy WP 2024-02; publicado en Real Estate Economics (doi:10.1111/1540-6229.12527). WP: https://www.landecon.cam.ac.uk/sites/default/files/2024-08/CRERC_2024-02%20WP.pdf · Registro: https://www.repository.cam.ac.uk/handle/1810/380865 [T]
15. Ling, D. C., Naranjo, A. y Scheick, B. (2016). *Credit Availability and Asset Pricing Dynamics in Illiquid Markets: Evidence from Commercial Real Estate Markets.* Journal of Money, Credit and Banking, 48(7), 1321–1362. https://ideas.repec.org/a/wly/jmoncb/v48y2016i7p1321-1362.html [R]
16. Swanson, Z., Theis, J. y Casey, K. M. (2002). *REIT Risk Premium Sensitivity and Interest Rates.* JREFE, 24(3), 319–330. https://ideas.repec.org/a/kap/jrefec/v24y2002i3p319-30.html [R]
17. Clayton, J., Ling, D. C. y Naranjo, A. (2008). *Commercial Real Estate Valuation: Fundamentals Versus Investor Sentiment.* SSRN WP. https://doi.org/10.2139/ssrn.1132361 [R]
18. *(número sin usar: Lin, Rahman y Yung 2009; su resumen estaba incompleto, ver §4.2)*
19. Hoesli, M. y Serrano, C. (2010). *Are Securitized Real Estate Returns More Predictable than Stock Returns?* JREFE, 41(2), 170–192. https://archive-ouverte.unige.ch/unige:78558 [R; cifras de costos vía 9]
20. Case, B. (2017a). *Valuing REITs at the Beginning of 2017: Yield Spreads to Treasuries.* Nareit, 1 feb. 2017. https://www.reit.com/data-research/research/market-commentary/valuing-reits-beginning-2017-yield-spreads-treasuries [T]
21. Case, B. (2017b). *Valuing REITs at the Beginning of 2017: Stock Price Premium/Discount to NAV.* Nareit, 8 feb. 2017. https://www.reit.com/data-research/research/market-commentary/valuing-reits-beginning-2017-stock-price-premium-discount [T]
22. Case, B. (2017c). *Using Market Signals to Predict REIT Outperformance Relative to Non-REIT Stocks.* Nareit, 13 feb. 2017. https://www.reit.com/news/blog/market-commentary/using-market-signals-to-predict-reit-outperformance-relative-to-non-reit-stocks [T]
23. Case, B. (2018). *2018 Return Expectations for REITs.* Nareit, 4 ene. 2018. https://www.reit.com/news/blog/market-commentary/2018-return-expectations-for-reits [T]
24. Nareit (2019). *Posting Double-Digit Returns, Free-Standing Retail REITs Deliver Industry's Top Performance in 2018.* 16 ene. 2019. https://www.reit.com/news/blog/nareit-media/posting-double-digit-returns-free-standing-retail-reits-deliver-industrys-top [T]
25. Nareit (2023). *REITs by the Numbers — Media Fact Sheet, December 2022.* https://www.reit.com/sites/default/files/2023-01/MediaFactSheet_Dec-2022.pdf [T: retornos anuales y niveles del índice 2015–2022]
26. Pierzak, E. F. (2023). *2024 REIT Market Outlook.* Nareit, 4 dic. 2023. https://reit.com/news/blog/market-commentary/2024-reit-market-outlook [T]
27. Pierzak, E. F. (2025). *The Changing Relationship Between REIT Performance and the U.S. 10-Year Treasury.* Nareit, 6 mar. 2025. https://reit.com/news/blog/market-commentary/changing-relationship-between-reit-performance-and-us-10-year-treasury [T]
28. Pierzak, E. F. (2026). *REITs Typically Post Positive Returns in Rising and Falling Interest Rate Environments.* Nareit, 15 jul. 2026. https://www.reit.com/news/blog/market-commentary/reits-typically-post-positive-returns-rising-falling-interest-rate [T]
29. Green Street Advisors (2014). *REIT Valuation: The NAV-based Pricing Model* (extracto de la versión 3.0). Alojado en reit.com: https://www.reit.com/sites/default/files/meetings/REITWise15/Key%20Drivers%20Impacting%20a%20REITs%20Stock%20Price/Full%20Document(s)/Green%20Street%20Advisors%20-%20Pricing%20Model%20Report.pdf [T]

**NAV**

30. Gentry, W. M., Jones, C. M. y Mayer, C. J. (2004). *Do Stock Prices Really Reflect Fundamental Values? The Case of REITs.* NBER Working Paper 10850. https://www.nber.org/papers/w10850 [R]
31. Clayton, J. y MacKinnon, G. (2001). *Explaining the Discount to NAV in REIT Pricing: Noise or Information?* SSRN WP. https://doi.org/10.2139/ssrn.258268 [R]
32. Brounen, D., Ling, D. C. y Porras Prado, M. (2013). *Short Sales and Fundamental Value: Explaining the REIT Premium to NAV.* Real Estate Economics, 41(3), 481–516. https://doi.org/10.1111/reec.12004 [R]
33. Barkham, R. y Ward, C. (1999). *Investor Sentiment and Noise Traders: Discount to Net Asset Value in Listed Property Companies in the U.K.* JRER, 18(2), 291–312. https://ideas.repec.org/a/taf/rjerxx/v18y1999i2p291-312.html [R]
34. Erol, I. y Tyvimaa, T. (2019). *Explaining the Premium to NAV in Publicly Traded Australian REITs, 2008–2018.* Journal of Property Investment & Finance, 38(1), 4–30. https://ideas.repec.org/a/eme/jpifpp/jpif-06-2019-0078.html [R]
35. Kumala, C., Ye, Z., Zhu, Y. y Ke, Q. (2024). *Why Does Price Deviate from Net Asset Value? The Case of Singaporean Infrastructure REITs.* International Review of Financial Analysis, 93, 103172. https://discovery.ucl.ac.uk/id/eprint/10189888/2/Ke_1-s2.0-S1057521924001042-main.pdf [R]
36. Letdin, M., Sirmans, S. y Sirmans, S. (2019). *Agree to Disagree: NAV Dispersion in REITs.* Ponencia en las reuniones ASSA/AREUEA 2019. http://www.aeaweb.org/conference/2019/preliminary/paper/TsBfrddf [R]

**Tendencia**

37. Faber, M. T. (2007; actualizado en 2009 y 2013). *A Quantitative Approach to Tactical Asset Allocation.* Journal of Wealth Management (primavera 2007); SSRN 962461. https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf [T]
38. Glabadanidis, P. (2014). *The Market Timing Power of Moving Averages: Evidence from US REITs and REIT Indexes.* International Review of Finance, 14(2), 161–202. doi:10.1111/irfi.12018. Resumen: https://international.vlex.com/vid/the-market-timing-power-855625738 y https://doi.org/10.2139/ssrn.4360952 [R]
39. CXO Advisory (s.f.). *Moving Averages and REIT Indexes.* https://www.cxoadvisory.com/technical-trading/moving-averages-and-reit-indexes [T]
40. Moss, A., Clare, A., Thomas, S. y Seaton, J. (2015). *Trend Following and Momentum Strategies for Global REITs.* Journal of Real Estate Portfolio Management, 21(1), 21–31. https://openaccess.city.ac.uk/id/eprint/17845/ [R]
41. Barry, N. (2022). *An Investigation into the Profitability and Sustainability of Market Timing Strategies in REITs: A Global Perspective.* Tesis de maestría, University of Cape Town. https://open.uct.ac.za/items/bbb34452-f6ab-4d87-b4d4-e80c67f15472 [R]
42. Moskowitz, T. J., Ooi, Y. H. y Pedersen, L. H. (2012). *Time Series Momentum.* Journal of Financial Economics, 104(2), 228–250. https://ideas.repec.org/a/eee/jfinec/v104y2012i2p228-250.html [R]
43. Zakamulin, V. (2014). *The Real-Life Performance of Market Timing with Moving Average and Time-Series Momentum Rules.* Journal of Asset Management, 15(4), 261–278. https://ideas.repec.org/a/pal/assmgt/v15y2014i4d10.1057_jam.2014.25.html [R]

**Mercado público contra privado**

44. Gyourko, J. y Keim, D. B. (1992). *What Does the Stock Market Tell Us About Real Estate Returns?* Real Estate Economics, 20(3), 457–485. https://ideas.repec.org/a/bla/reesec/v20y1992i3p457-485.html [R]
45. Barkham, R. y Geltner, D. (1995). *Price Discovery in American and British Property Markets.* Real Estate Economics, 23(1), 21–44. https://ideas.repec.org/a/bla/reesec/v23y1995i1p21-44.html [R]
46. Gyourko, J. (s.f.). *Real Estate Returns in Public and Private Markets.* Wharton Zell/Lurie WP #470. https://realestate.wharton.upenn.edu/working-papers/real-estate-returns-in-public-and-private-markets/ [R]
47. Oikarinen, E., Hoesli, M. y Serrano, C. (2011). *The Long-Run Dynamics between Direct and Securitized Real Estate.* JRER, 33(1), 73–104. https://ideas.repec.org/a/jre/issued/v33n12011p73-104.html [R]
48. Ling, D. C. y Naranjo, A. (2015). *Returns and Information Transmission Dynamics in Public and Private Real Estate Markets.* Real Estate Economics, 43(1), 163–208. https://ideas.repec.org/a/bla/reesec/v43y2015i1p163-208.html [R]
49. Hoesli, M. y Oikarinen, E. (2012). *Are REITs Real Estate? Evidence from International Sector Level Data.* Journal of International Money and Finance, 31(7), 1823–1850. https://ideas.repec.org/a/eee/jimfin/v31y2012i7p1823-1850.html [R]
50. Funari, N. (2023). *REITs Offer Diversification and Timeliness.* Nareit, 30 mar. 2023. https://reit.com/news/blog/market-commentary/reits-offer-diversification-and-timeliness [T]

**Sección cruzada**

51. Chui, A. C. W., Titman, S. y Wei, K. C. J. (2003a). *The Cross Section of Expected REIT Returns.* Real Estate Economics, 31(3), 451–479. https://ideas.repec.org/a/bla/reesec/v31y2003i3p451-479.html [R]
52. Chui, A. C. W., Titman, S. y Wei, K. C. J. (2003b). *Intra-Industry Momentum: The Case of REITs.* Journal of Financial Markets, 6(3), 363–387. Resumen (SSRN 2001): https://doi.org/10.2139/ssrn.288217 [R]
53. Derwall, J., Huij, J., Brounen, D. y Marquering, W. (2009). *REIT Momentum and the Performance of Real Estate Mutual Funds.* Financial Analysts Journal, 65(5), 24–34. https://ideas.repec.org/a/taf/ufajxx/v65y2009i5p24-34.html [R]
54. Hung, S.-Y. K. y Glascock, J. L. (2008). *Momentum Profitability and Market Trend: Evidence from REITs.* JREFE, 37(1), 51–69. Resumen de la versión ERES 2005: https://eres.architexturez.net/node/19451 [R]
55. Hung, S.-Y. K. y Glascock, J. L. (2010). *Volatilities and Momentum Returns in Real Estate Investment Trusts.* JREFE, 41(2), 126–149. Resumen (SSRN 2008): https://doi.org/10.2139/ssrn.1090394 [R]
56. Goebel, P., Harrison, D., Mercer, J. y Whitby, R. (2013). *REIT Momentum and Characteristic-Related REIT Returns.* JREFE, 47(3), 564–581. https://ideas.repec.org/a/kap/jrefec/v47y2013i3p564-581.html [R]
57. Jensen, T. K. y Turner, T. M. (2022). *Monetary Policy Shifts, Dividends and REIT Momentum.* JRER, 44(3), 311–330. https://ideas.repec.org/a/taf/rjerxx/v44y2022i3p311-330.html [R]
58. Parhizgari, A. y Pavlova, I. (2009). *The Boom and the Lean Times in Global REITs: The 2000–2008 Period.* 16.º congreso de ERES, Estocolmo. https://eres.architexturez.net/node/16768 [R]
59. Ooi, J. T. L., Webb, J. R. y Zhou, D. (2007). *Extrapolation Theory and the Pricing of REIT Stocks.* JRER, 29(1), 27–56. https://ideas.repec.org/a/jre/issued/v29n12007p27-56.html [R]
60. Ooi, J. T. L., Wang, J. y Webb, J. R. (2009). *Idiosyncratic Risk and REIT Returns.* JREFE, 38(4), 420–442. https://ideas.repec.org/a/kap/jrefec/v38y2009i4p420-442.html [R]
61. DeLisle, R. J., Price, S. M. y Sirmans, C. F. (2013). *Pricing of Volatility Risk in REITs.* JRER, 35(2), 223–248. https://ideas.repec.org/a/taf/rjerxx/v35y2013i2p223-248.html [R]
62. Cakici, N., Erol, I. y Tirtiroglu, D. (2014). *Tracking the Evolution of Idiosyncratic Risk and Cross-Sectional Expected Returns for US REITs.* JREFE, 48(3), 415–440. https://ideas.repec.org/a/kap/jrefec/v48y2014i3p415-440.html [R]
63. Bond, S. y Xue, C. (2017). *The Cross Section of Expected Real Estate Returns: Insights from Investment-Based Asset Pricing.* JREFE, 54(3), 403–428. https://ideas.repec.org/a/kap/jrefec/v54y2017i3d10.1007_s11146-016-9573-0.html [R]
64. Giacomini, E., Ling, D. C. y Naranjo, A. (2017). *REIT Leverage and Return Performance: Keep Your Eye on the Target.* Real Estate Economics, 45(4), 930–978. Resumen: https://u-pad.unimc.it/handle/11393/236126 [R]
65. Gyamfi-Yeboah, F., Ling, D. C. y Naranjo, A. (2012). *Information, Uncertainty, and Behavioral Effects: Evidence from Abnormal Returns around REIT Earnings Announcements.* JIMF, 31(7), 1930–1952. https://ideas.repec.org/a/eee/jimfin/v31y2012i7p1930-1952.html [R]
66. Shen, J. (2021). *Distress Risk and Stock Returns on Equity REITs.* JREFE, 62(3), 455–480. https://ideas.repec.org/a/kap/jrefec/v62y2021i3d10.1007_s11146-020-09756-7.html [R]
67. Sha, Y., Wang, Z., Bu, Z. y Mansley, N. (2020). *Does Default Risk Matter for Investors in REITs.* International Journal of Strategic Property Management, 24(5), 365–378. https://journals.vilniustech.lt/index.php/IJSPM/article/view/13504 [R]
68. Letdin, M., Seagraves, C. y Sirmans, S. (2025). *REIT Factors.* SSRN WP 5250691. https://papers.ssrn.com/abstract=5250691 (bloqueado); resumen leído en https://vvv.quantpedia.com/?p=41448 [S]
69. Andronoudis, D., Guidolin, M. y Pedio, M. (2025). *Factor Investing in Real Estate: The Performance of Smart Beta Strategies.* Journal of Portfolio Management, 52(3), 129–152. https://research-information.bris.ac.uk/en/publications/factor-investing-in-real-estate-the-performance-of-smart-beta-str/ [R]
70. Tomtosov, A., Rechmedina, S. y Dobrynskaya, V. (2025). *Momentum Factor or Factor Momentum in REITs Market?* HSE Working Paper (Financial Economics). https://preprint.hse.ru/article/view/28610 · PDF: https://preprint.hse.ru/article/download/28610/23160 [T]
71. Herzberg, M. A., Bordo, J. D. y Kessler, T. R. (s.f., c. 2008). *Value Creation Opportunities for Commercial Real Estate Owners.* Wharton Real Estate Review (Zell/Lurie). https://realestate.wharton.upenn.edu/wp-content/uploads/2017/03/649.pdf [T]
72. *(número sin usar)*
73. *(número sin usar)*
74. Quantpedia (s.f.). *Momentum Factor Effect in REITs.* https://quantpedia.com/strategies/momentum-factor-effect-in-reits [T; fuente secundaria]

**Dividendos y dificultades financieras**

75. Case, B., Hardin, W. G. III y Wu, Z. (2012). *REIT Dividend Policies and Dividend Announcement Effects During the 2008–2009 Liquidity Crisis.* Real Estate Economics, 40(3), 387–421. doi:10.1111/j.1540-6229.2011.00324.x. Ficha: https://ideas.repec.org/a/bla/reesec/v40y2012i3p387-421.html [R; resumen vía Crossref]
76. Bradley, M., Capozza, D. R. y Seguin, P. J. (1998). *Dividend Policy and Cash-Flow Uncertainty.* Real Estate Economics, 26(4), 555–580. https://ideas.repec.org/a/bla/reesec/v26y1998i4p555-580.html [R]
77. Hardin, W. G. III y Hill, M. D. (2008). *REIT Dividend Determinants: Excess Dividends and Capital Markets.* Real Estate Economics, 36(2), 349–369. https://ideas.repec.org/a/bla/reesec/v36y2008i2p349-369.html [R]
78. Pettenuzzo, D., Sabbatucci, R. y Timmermann, A. (2020). *Dividend Suspensions and Cash Flow Risk during the Covid-19 Pandemic.* CEPR Discussion Paper 14921. https://cepr.org/publications/dp14921 [R]
79. Wright, J., Huerta, D. y Weeks, S. (2024). *REIT Capital Raising and Dividend Policies during the COVID-19 Pandemic Crisis.* 30.º congreso de ERES. https://ideas.repec.org/p/arz/wpaper/eres2024-115.html [R]
80. Kallberg, J. G., Liu, C. H. y Srinivasan, A. (2003). *Dividend Pricing Models and REITs.* Real Estate Economics, 31(3), 435–450. doi:10.1111/1540-6229.00072 [R; vía Crossref]

**Metodología**

81. Glascock, J. L., Lu, C. y So, R. W. (2000). *Further Evidence on the Integration of REIT, Bond, and Stock Returns.* JREFE, 20(2), 177–194. https://ideas.repec.org/a/kap/jrefec/v20y2000i2p177-94.html [R]
82. Clayton, J. y MacKinnon, G. (2000). *The Relative Importance of Stock, Bond and Real Estate Factors in Explaining REIT Returns.* SSRN WP (publicado después en JREFE; no verifiqué la versión publicada). https://doi.org/10.2139/ssrn.232394 [R]
83. Ambrose, B. W., Lee, D. W. y Peek, J. (2007). *Comovement After Joining an Index: Spillovers of Nonfundamental Effects.* Real Estate Economics, 35(1), 57–90. doi:10.1111/j.1540-6229.2007.00182.x [R; vía Crossref]
84. Goodwin, K. R. y Liu, S. (2021). *GICS and the Real Estate Reclassification Revolution.* Journal of Real Estate Portfolio Management, 27(2), 121–136. https://ideas.repec.org/a/taf/repmxx/v27y2021i2p121-136.html [R]
85. Bao, H. X. H., Brady, A. y Wang, Z. (2020). *Pricing Efficiency and Bounded Rationality: Evidence Based on the Responses Surrounding GICS Real Estate Category Creation.* International Real Estate Review, 23(1), 37–63. https://ideas.repec.org/a/ire/issued/v23n012020p37-63.html [R]
86. Shumway, T. (1997). *The Delisting Bias in CRSP Data.* Journal of Finance, 52(1), 327–340. https://ideas.repec.org/a/bla/jfinan/v52y1997i1p327-40.html [R]
87. UCLA Ziman Center (consultado oct. 2026). *CRSP/Ziman REIT Data Series* (con aviso de descontinuación). https://www.anderson.ucla.edu/centers/ucla-ziman-center-for-real-estate/faculty-and-research/crsp/ziman-reit-data-series · Morningstar/CRSP: https://indexes.morningstar.com/research-data-products/crsp-ziman-real-estate-database [T]
88. Welch, I. y Goyal, A. (2008). *A Comprehensive Look at the Empirical Performance of Equity Premium Prediction.* Review of Financial Studies, 21(4), 1455–1508. https://ideas.repec.org/a/oup/rfinst/v21y2008i4p1455-1508.html [R]
89. Campbell, J. Y. y Thompson, S. B. (2008). *Predicting Excess Stock Returns Out of Sample: Can Anything Beat the Historical Average?* RFS, 21(4), 1509–1531. https://ideas.repec.org/a/oup/rfinst/v21y2008i4p1509-1531.html [R]
90. Goyal, A., Welch, I. y Zafirov, A. (2021). *A Comprehensive 2022 Look at the Empirical Performance of Equity Premium Prediction.* SSRN WP. https://doi.org/10.2139/ssrn.3929119 [R]
91. McLean, R. D. y Pontiff, J. (2016). *Does Academic Research Destroy Stock Return Predictability?* Journal of Finance, 71(1), 5–32. Resumen de la versión SSRN de 2012: https://doi.org/10.2139/ssrn.2080900 [R]
92. Harvey, C. R., Liu, Y. y Zhu, H. (2014). *…and the Cross-Section of Expected Returns.* NBER WP 20592 (publicado en RFS en 2016). https://www.nber.org/papers/w20592 [R]
93. Bailey, D. H. y López de Prado, M. (2014). *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality.* Journal of Portfolio Management; SSRN. https://doi.org/10.2139/ssrn.2460551 [R]

**Otros mercados**

94. Hamelink, F. y Hoesli, M. (2004). *What Factors Determine International Real Estate Security Returns?* Real Estate Economics, 32(3), 437–462. https://ideas.repec.org/a/bla/reesec/v32y2004i3p437-462.html [R]
95. Schulte, K. y Dechant, T. (2011). *Systematic Risk Factors in European Real Estate Equity Returns.* Congreso de ERES. https://ideas.repec.org/p/arz/wpaper/eres2011_140.html [R]
96. Zhang, W., Li, B. y Roca, E. (2023). *Moments and Momentum in the Returns of Securitized Real Estate: A Cross-Country Study of Risk Factors Driving REITs before and during COVID-19.* Heliyon. https://pmc.ncbi.nlm.nih.gov/articles/PMC10388167/ [R]
97. Shum, W. C. y Wong, K. H. Y. (2009). *The Predictability of REITs Returns: Evidence from Japan.* Journal of Asia Business Studies, 4(1), 33–38. https://scholars.hkmu.edu.hk/en/publications/the-predictability-of-reits-returns-evidence-from-japan/ [R]
98. Casiano Hernández, P. (2022). *Análisis de relación riesgo y rendimientos en la inversión en FIBRAS en BMV.* Tesis de maestría, Universidad Autónoma de Querétaro. https://ri-ng.uaq.mx/bitstream/123456789/3583/1/RI006615.pdf [T: resumen y conclusiones]
99. Gasca Zamora, J. y Castro Martínez, E. de J. (2021). *Financiarización inmobiliaria en México: una mirada desde los FIBRAS.* Revista INVI, 36(103), 112–136. https://www.redalyc.org/journal/258/25869557005/25869557005.pdf [R]

**Datos (no son literatura; IDs verificados en FRED):** DRTSCREL (1990T3–2013T3, descontinuada) https://fred.stlouisfed.org/data/DRTSCREL · SUBLPDRCSC (desde 2013T4) https://fred.stlouisfed.org/data/SUBLPDRCSC.txt · SUBLPDRCSN https://fred.stlouisfed.org/series/SUBLPDRCSN · DFII10 (desde 2-ene-2003) https://fred.stlouisfed.org/data/DFII10.txt · BAA10YM (desde abr-1953) https://fred.stlouisfed.org/data/BAA10YM.txt

### 4.2 Fuentes buscadas que NO pude abrir o no localicé (no se usan como evidencia)

- **S&P Global Market Intelligence (2016), *A League of Their Own: Batting for Returns in the REIT Industry*, partes 1 y 2.** El buscador muestra cifras de un fragmento: yield de dividendo 0.95 % de retorno activo; AFFO yield 6.78 %; NAV/precio 5.95 %; cap rate implícito 6.35 %. **El documento no abrió** (error de DNS y del proxy), así que no lo verifiqué.
- **Cohen & Steers**, *Exploring the Lead-Lag Relationship of Listed and Private Real Estate*, y sus notas sobre retornos después del ciclo de la Fed: error 403.
- **Research Affiliates (Asset Allocation Interactive)**: el sitio redirige a Syzygy y RAFI; los artículos de terceros dieron error 403.
- **AQR**: no encontré investigación específica de REITs.
- **Letdin, Seagraves y Sirmans (2025)**, texto completo en SSRN (403). Solo leí el resumen vía Quantpedia.
- **"Huerta y Rivas"**, sobre la pérdida de significancia del momentum en REITs. Quantpedia lo cita y no localicé el estudio primario.
- **Pagliari, Scherer y Monopoli (2005, REE)**: no abrí el resumen.
- **Price, Gatzlaff y Sirmans (2012, JREFE, deriva posterior a utilidades)**: no hay resumen disponible.
- **Lin, Rahman y Yung (2009, JREFE, sentimiento)**: resumen incompleto.
- **Cooper, Downs y Patterson (1999, JRER, filtro de corto plazo)**: sin resumen.
- **Tesis de Aalto sobre momentum de serie de tiempo en REITs, 1991–2023** (403). El buscador reporta 9.04 % anual y nada significativo después de 2008; no lo verifiqué.
- **Alpha Architect / Swedroe** sobre [68]: error 403 en Alpha Architect. La entrada de Substack no tenía cifras.
- **FIBRAs:** no encontré estudios arbitrados sobre predictibilidad ni sobre factores. El repositorio del COLMEX pidió CAPTCHA.
