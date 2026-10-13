# Los extremos de valuación. Pre-registro (exploratorio)

Escrito el 13 de octubre de 2026, antes de correr nada. Va en el mismo commit que el código que
lo corre (`src/investigacion/extremos.py`).

## Por qué, y por qué es exploratorio

El inversionista duda de la conclusión «aportar siempre, sin importar la valuación»: las reglas
de las fases 5 y 6 usaban el quintil o el tercil, y una objeción razonable es que la valuación
solo importa en los extremos —REITs a 3% de yield en 2006 o a 10% en 2009—. Esta prueba mide qué
pasó **solo** cuando la valuación estaba en su 5% o 10% más extremo.

Se decidió **después** de ver todas las fases, así que es exploratoria: no puede aprobar nada.
Lo que salga a favor queda como «pista» para una prueba nueva con datos nuevos, nunca como regla.
Las reglas nuevas de esta prueba se anotan en la bitácora con la familia `extremos` y suben el
conteo de intentos.

## Qué se mide

**Extremo** es el percentil expandible de la señal contra su propia historia
(`percentil_expandible`, solo con el pasado), salvo en el corte transversal, donde son deciles
entre emisores cada trimestre. Todas las señales están orientadas para que **alto = barato**.

| Corte | Percentil |
|---|---|
| Caro 5% | ≤ 0.05 |
| Caro 10% | ≤ 0.10 |
| Centro | entre 0.10 y 0.90 |
| Barato 10% | ≥ 0.90 |
| Barato 5% | ≥ 0.95 |

### 1. El sector (FTSE Nareit All Equity, desde 1972)

* **Señales:** las cuatro de valuación de la fase 4: el yield de los REITs y el yield contra el
  Treasury, contra la tasa real y contra los bonos Baa. Cada percentil requiere al menos 60 meses
  de historia.
* **Retorno siguiente:** a 12 y a 60 meses, de los REITs y del efectivo (T-bill), anualizado y
  antes de impuestos. Para cada corte se reporta:
  - los meses en la condición, su frecuencia y los episodios (rachas separadas por 12 meses o más);
  - la mediana de los REITs, del efectivo y del exceso;
  - la fracción de las veces en que ganó el efectivo;
  - la diferencia del exceso promedio contra el resto de los meses, con su t de Newey-West
    (rezago igual al horizonte).
* **Reglas:** «fuera solo en el 5% más caro» y «fuera solo en el 10% más caro», con la misma
  contabilidad de la fase 5: aportando 1,000 dólares al mes y rebalanceando. Se calculan con el
  SIC (la línea base) y con el broker al 35%. Se reporta:
  - la mejora contra aportar siempre;
  - la mejora contra la mezcla fija;
  - la mejora con un mes de retraso;
  - la caída máxima.

  El lado barato no se convierte en regla: la exposición ya es 100% y no hay apalancamiento.
* **Muestras:** desarrollo (1972-2015) y, aparte, validación (2016 en adelante). La validación ya
  se abrió en las fases 6 y 8; esta apertura queda en la bitácora con su motivo.

### 2. O, NNN y WPC

* **Paneles:** los de `metodos.panel`, con el dividendo neto del broker al 35% (44%) y el efectivo
  neto del 35%.
* **Señales:** el percentil expandible del consenso de los siete métodos y el de la prima sobre el
  Treasury. Para el consenso se recalcula el percentil sobre su propio valor, porque el promedio
  de percentiles casi nunca llega a las colas.
* **Retorno:** retorno total neto a 1, 3 y 5 años en fines de trimestre, por corte, con los tres
  emisores juntos y uno por uno. Se reportan:
  - la mediana, el p10 y el p90;
  - los trimestres y las ventanas independientes (trimestres entre 4 × años);
  - el efectivo neto a 5 años.
* **Muestras:** este nivel no tiene validación separada. Se usan las dos mitades de cada emisor.

### 3. El corte transversal (fase 6, todos los REITs de capital)

* **Datos:** el panel de los emisores abiertos, nunca los sellados. Desarrollo (2011-2015) y
  validación (2016 en adelante).
* **Señales:** cada trimestre, deciles de cuatro señales de valuación: yield de dividendo, FFO
  yield, cap rate de la empresa y yield contra su propia historia.
* **Comparación:** el decil más barato y el más caro contra todos los elegibles, con las
  cohortes encimadas a 4 trimestres de la fase 6. Se reportan:
  - el exceso anual bruto con su t de Newey-West;
  - la fracción que recortó el dividendo en el año siguiente;
  - la fracción que se desplomó 30% o más;
  - la TIR del decil barato contra aportar a todos, con el broker al 35%.

## Cómo se lee

* **Pista**, solo en el sector y en el corte transversal: el mismo signo en desarrollo y en
  validación, con |t| ≥ 2 en las dos. En las reglas, mejora de +50 pb o más en las dos muestras y
  positiva con un mes de retraso.
* **O, NNN y WPC:** con tan pocas ventanas independientes no hay t válida. Este nivel solo es
  descriptivo: dice cuánto se ganó en cada corte, no si la diferencia es real.
* **Ninguna pista se adopta.** Aun con una pista, la prueba es posterior y suma intentos a la
  bitácora. Solo una prueba nueva, pre-registrada y con datos que no se hayan visto, podría
  convertirla en regla.

## Lo que esperamos (escrito antes de correr)

* **H-E1.** En el sector, el 10% más caro tiene un exceso siguiente menor que el resto, pero los
  REITs le siguen ganando al efectivo en la mayoría de las ventanas de 5 años, y salir solo en el
  10% más caro no llega a +50 pb en las dos muestras.
* **H-E2.** El 10% más barato del sector tiene un retorno siguiente más alto, pero son pocos
  episodios (de 2 a 5) y la t no llega a 2 en las dos muestras.
* **H-E3.** En O, NNN y WPC, el 10% más barato rinde varios puntos al año más que el 10% más caro
  a 5 años, con menos de 5 ventanas independientes por corte.
* **H-E4.** En el corte transversal, el decil más barato por yield de dividendo recorta más que el
  universo y no le gana; el decil más caro tampoco pierde de forma consistente en las dos muestras.
* **H-E5.** Ninguna combinación llega a pista en el sector ni en el corte transversal.

## Nota antes del commit

Para comprobar que el código corría, antes de este commit se hizo una prueba con la muestra de
desarrollo y los estudios de O, NNN y WPC, sin escribir en la bitácora y sin abrir la
validación ni los sellados. Todo lo de arriba, hipótesis incluidas, se escribió antes de esa
prueba y no se cambió después.
