# Ampliación del estudio: ¿se repiten las conclusiones de O, NNN y WPC?

Resultado de la prueba fuera de muestra pre-registrada en `docs/estudios/ampliacion_preregistro.md`. Generado con `python scripts/estudio.py ampliacion`.

## Los siete emisores nuevos

| # | Conclusión de los tres | Criterio | Resultado | Cifras |
|---|---|---|---|---|
| H1 | La valuación predice el retorno de 5 años: lo barato rindió más que lo caro. | Juntos: mediana de barato (≥ 70) − mediana de caro (< 30) ≥ 3 puntos al año y ρ a 5 años positiva. | **se repite** | barato 18.3% (54 trimestres) contra caro 8.4% (148): +9.9 puntos; ρ = +0.36 con 402 trimestres (20 ventanas independientes). |
| H1b | Lo mismo, emisor por emisor. | ρ a 5 años positiva en la mayoría de los emisores con al menos 40 trimestres. | **se repite** | 4 de 5 emisores elegibles con ρ positiva (ADC +0.62, EXR -0.09, PLD +0.58, PSA +0.47, WELL +0.16). |
| H2 | Aun desde «caro», el REIT le ganó al efectivo la mayoría de las veces: esperar no paga. | Juntos, en caro + muy caro, el REIT le gana al T-bill neto en más de 50% de los trimestres. | **se repite** | le ganó en 78% de 147 trimestres. |
| H3 | El semáforo completo no le gana a aportar siempre. | El semáforo le gana a aportar siempre por +50 pb o más en a lo sumo 1 emisor. | **no se repite** | le gana por +50 pb en 2 de 7: ADC -11 pb, EPRT +67 pb, EXR +19 pb, GNL +515 pb, PLD -536 pb, PSA +4 pb, WELL -257 pb. |
| H4 | Ningún método solo, usado para decidir cuándo comprar, le gana a aportar siempre. | Con el consenso, la ventaja contra aportar siempre es menor a +50 pb en la mayoría. | **se repite** | menor a +50 pb en 6 de 7: ADC -19 pb, EPRT +0 pb, EXR -57 pb, GNL +55 pb, PLD -36 pb, PSA -9 pb, WELL -2 pb. |
| H5 | Mandar la aportación al más barato contra su propia historia le ganó a repartir parejo. | Ventaja del consenso ≥ +50 pb, a lo sumo 5% de las elecciones al azar le gana y el espejo (todo al más caro) queda abajo de partes iguales. | **no se repite** | entre ADC, EXR, PLD, PSA, WELL desde 2009-03: ventaja +122 pb; el azar le gana 19% de las veces; el espejo +72 pb; primera mitad (2009-02 a 2017-11): +388 pb; segunda mitad (2017-12 a 2026-09): +62 pb. |
| H6 | DDM, DCF, crecimiento implícito y NAV no predicen mejor que los métodos simples. | Juntos, ningún modelo de valor tiene ρ a 5 años mayor que la del mejor método simple. | **se repite** | mejor simple: Múltiplo P/FFO ρ = +0.40; modelos de valor: ddm +0.20, dcf +0.24, crecimiento +0.10, nav +nan. |
| H7 | En los extremos la valuación separa: el 10% más barato rindió mucho más que el 10% más caro. | Juntos, la mediana de muy barato (≥ 90) supera a la de muy caro (< 10). | **se repite** | muy barato 21.5% (11 trimestres) contra muy caro 4.4% (46). |

## Sensibilidad: los siete con FFO de Nareit, sin excepciones de medida

| # | Resultado | Cifras |
|---|---|---|
| H1 | **se repite** | barato 19.9% (45 trimestres) contra caro 8.3% (153): +11.5 puntos; ρ = +0.39 con 402 trimestres (20 ventanas independientes). |
| H1b | **se repite** | 4 de 5 emisores elegibles con ρ positiva (ADC +0.62, EXR -0.12, PLD +0.63, PSA +0.47, WELL +0.05). |
| H2 | **se repite** | le ganó en 78% de 152 trimestres. |
| H3 | **no se repite** | le gana por +50 pb en 2 de 7: ADC -11 pb, EPRT +67 pb, EXR -821 pb, GNL +515 pb, PLD -378 pb, PSA +4 pb, WELL -553 pb. |
| H4 | **se repite** | menor a +50 pb en 7 de 7: ADC -19 pb, EPRT +0 pb, EXR -54 pb, GNL +30 pb, PLD -36 pb, PSA -9 pb, WELL -6 pb. |
| H5 | **no se repite** | entre ADC, EXR, PLD, PSA, WELL desde 2009-03: ventaja +93 pb; el azar le gana 21% de las veces; el espejo +50 pb; primera mitad (2009-02 a 2017-11): +411 pb; segunda mitad (2017-12 a 2026-09): -105 pb. |
| H6 | **se repite** | mejor simple: Prima sobre el Treasury ρ = +0.41; modelos de valor: ddm +0.20, dcf +0.24, crecimiento +0.12, nav +nan. |
| H7 | **se repite** | muy barato 21.6% (10 trimestres) contra muy caro 5.5% (48). |

## Control: los tres originales con el mismo código

| # | Resultado | Cifras |
|---|---|---|
| H1 | **se repite** | barato 18.2% (37 trimestres) contra caro 6.3% (100): +11.9 puntos; ρ = +0.43 con 264 trimestres (13 ventanas independientes). |
| H1b | **se repite** | 3 de 3 emisores elegibles con ρ positiva (NNN +0.50, O +0.34, WPC +0.52). |
| H2 | **se repite** | le ganó en 72% de 100 trimestres. |
| H3 | **se repite** | le gana por +50 pb en 0 de 3: NNN -561 pb, O -56 pb, WPC +14 pb. |
| H4 | **se repite** | menor a +50 pb en 3 de 3: NNN -8 pb, O -21 pb, WPC -11 pb. |
| H5 | **se repite** | entre NNN, O, WPC desde 2003-05: ventaja +71 pb; el azar le gana 0% de las veces; el espejo -54 pb; primera mitad (2003-04 a 2014-12): +143 pb; segunda mitad (2015-01 a 2026-09): +85 pb. |
| H6 | **no se repite** | mejor simple: Yield de dividendo ρ = +0.44; modelos de valor: ddm +0.32, dcf -0.04, crecimiento -0.10, nav +0.71. |
| H7 | **se repite** | muy barato 19.7% (12 trimestres) contra muy caro 5.2% (10). |

## Los diez juntos

| # | Resultado | Cifras |
|---|---|---|
| H1 | **se repite** | barato 18.2% (91 trimestres) contra caro 7.8% (248): +10.4 puntos; ρ = +0.38 con 666 trimestres (33 ventanas independientes). |
| H1b | **se repite** | 7 de 8 emisores elegibles con ρ positiva (NNN +0.50, O +0.34, WPC +0.52, ADC +0.62, EXR -0.09, PLD +0.58, PSA +0.47, WELL +0.16). |
| H2 | **se repite** | le ganó en 75% de 247 trimestres. |
| H3 | **no se repite** | le gana por +50 pb en 2 de 10: NNN -561 pb, O -56 pb, WPC +14 pb, ADC -11 pb, EPRT +67 pb, EXR +19 pb, GNL +515 pb, PLD -536 pb, PSA +4 pb, WELL -257 pb. |
| H4 | **se repite** | menor a +50 pb en 9 de 10: NNN -8 pb, O -21 pb, WPC -11 pb, ADC -19 pb, EPRT +0 pb, EXR -57 pb, GNL +55 pb, PLD -36 pb, PSA -9 pb, WELL -2 pb. |
| H5 | **no se repite** | entre ADC, EXR, NNN, O, PLD, PSA, WELL, WPC desde 2009-03: ventaja +264 pb; el azar le gana 1% de las veces; el espejo +130 pb; primera mitad (2009-02 a 2017-11): +581 pb; segunda mitad (2017-12 a 2026-09): +160 pb. |
| H6 | **no se repite** | mejor simple: Múltiplo P/FFO ρ = +0.42; modelos de valor: ddm +0.23, dcf +0.13, crecimiento +0.03, nav +0.71. |
| H7 | **se repite** | muy barato 19.9% (23 trimestres) contra muy caro 4.4% (56). |

