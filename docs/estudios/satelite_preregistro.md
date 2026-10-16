# Núcleo y satélite contra SCHH: pre-registro

Escrito el 16 de octubre de 2026, en el mismo commit que `src/estudio/satelite.py` y antes de
correrlo con datos reales (las pruebas usan datos sintéticos). Lo que dice aquí no se cambia
después del commit; si se cambia, la prueba en papel vuelve a empezar con fecha nueva.

## La pregunta

Con un núcleo de SCHH y un satélite de REITs escogidos por una regla, ¿se le gana a tener todo en
SCHH? La investigación (fase 6) ya dijo que ninguna regla de selección le ganó a comprar todos por
partes iguales por +50 pb de forma robusta; la que más se acercó fue momentum (+57 pb en
validación, +38 pb en los emisores sellados). Aquí se pregunta lo mismo, pero contra SCHH, que es
lo que el inversionista compra.

Hay dos partes, y solo la segunda puede confirmar algo.

## A. Exploratoria, con datos ya vistos

No confirma nada: el panel de la fase 6 ya se usó para escoger momentum. Sirve para ver de qué
tamaño sería la diferencia contra SCHH y qué tan estable fue.

* **Universo:** los emisores abiertos de la fase 6 (dos tercios de los REITs de capital de
  EE. UU., vivos y muertos, `data/investigacion/emisores/panel.csv.gz`). Los sellados no se
  vuelven a abrir.
* **Elegibles, señales y reglas:** exactamente las de la fase 6 (`fase6.senales`,
  `fase6.elegibles`, `fase6.miembros`, con `DISENO6`).
* **Cuatro satélites**, fijados aquí:
  1. todos los elegibles por partes iguales (separa el efecto de pesar igual del de escoger);
  2. momentum (S1, tercil superior de los meses 12 a 3);
  3. calidad (S8);
  4. calidad y barato contra su historia.
* **Dos referencias:**
  1. SCHH real, con los índices que siguió antes de 2020;
  2. el índice que SCHH sigue hoy, aproximado con el FTSE Nareit All Equity REITs menos 0.07% al
     año (desde 2020, SCHH se desvía de él 0.43% al año y −2 pb; `docs/estudios/etfs_de_reits.md`).
* **Periodo:** carteras desde el 31 de marzo de 2011 (primer trimestre completo de SCHH) hasta
  el último trimestre del panel.
* **El inversionista:** 3,000 dólares por trimestre, sin vender nunca, con el simulador de la
  fase 6 (`fase6.simular`) y los impuestos del broker de EE. UU. al 35% (dividendo 44%,
  intereses 35%, ganancia 10%, sin comisión). La referencia se simula con la misma máquina.
* **Métricas:**
  * la TIR neta del satélite y de la referencia;
  * la TIR de la cartera completa con 85% en la referencia y 15% en el satélite;
  * el exceso bruto anual de las cohortes de un año contra la referencia, en total y en
    2011-2015, 2016-2020 y 2021 en adelante;
  * cuántos años calendario ganó el satélite;
  * la caída máxima.
* **Bitácora:** cada satélite contra cada referencia queda registrado con la familia
  `satelite` (ocho intentos), además de las aperturas de los datos posteriores a 2016.

## B. En papel, hacia adelante: la prueba que vale

La única muestra que nadie ha visto es el futuro. Se congela una regla hoy y se sigue sin dinero
real.

* **Regla congelada:** momentum S1 de la fase 6, sin cambios.
  * Entre los elegibles de los emisores abiertos, el tercil con mejor retorno de los meses 12 a 3.
  * Partes iguales entre los escogidos.
  * Se aporta solo dinero nuevo y nunca se vende, salvo que el emisor deje de cotizar.
* **Por qué esta:** es la única regla de la investigación que pasó la validación. No se escoge
  por el resultado de la parte A, que se corre después de este commit.
* **Referencia:** SCHH.
* **Calendario:**
  * Las aportaciones teóricas son de 3,000 dólares al satélite y 3,000 a SCHH, en cuentas
    separadas.
  * Se hacen al cierre de febrero, mayo, agosto y noviembre.
  * Cada una usa el panel del trimestre que cerró dos meses antes, cuando ya se presentaron los
    13F: el de diciembre para febrero, el de marzo para mayo, y así.
  * La primera es el 30 de noviembre de 2026, con el panel al 30 de septiembre de 2026.
  * Son doce aportaciones, hasta agosto de 2029.
* **Precio:** el cierre de fin de mes de Yahoo Finance del mes de la aportación, con
  dividendos.
* **Contabilidad:** la de la fase 6 con el perfil del broker al 35%. Un emisor que deja de
  cotizar se vende a su último precio y lo recibido se reinvierte con la siguiente aportación.
* **Veredicto, solo al 30 de noviembre de 2029:**
  * **Éxito:** la TIR neta del satélite queda al menos 50 pb al año arriba de la de SCHH (el
    criterio de la investigación) y el exceso bruto es positivo. Solo así tendría sentido poner
    dinero real en un satélite.
  * **Si no:** todo en SCHH.
* **Abandono anticipado:** después de la octava aportación (agosto de 2028), si el satélite va
  200 pb al año o más abajo de SCHH, la prueba se detiene con veredicto negativo.
* **Lo intermedio:** las evaluaciones de cada trimestre son informativas y no cambian la regla.
* **Universo:** solo los emisores abiertos. Es una muestra al azar de dos tercios del mercado;
  basta para una prueba en papel y no toca la muestra sellada.

### Lo que se hace cada trimestre

1. Después del día 15 de febrero, mayo, agosto y noviembre, actualizar el panel:
   `SEC_USER_AGENT="…" python scripts/investigacion.py emisores`.
2. `python scripts/estudio.py satelite elegir`: anota los escogidos y la aportación a SCHH en
   `data/estudios/satelite/papel.csv`. Se niega a anotar fuera del calendario, dos veces el mismo
   mes, o si el panel no llega al trimestre que toca.
3. `python scripts/estudio.py satelite evaluar`: baja de Yahoo los precios de lo anotado, los
   guarda sin borrar lo anterior (un emisor que deja de cotizar desaparece de Yahoo) y escribe
   `docs/estudios/satelite_en_papel.md`.
