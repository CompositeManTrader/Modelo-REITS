"""Estudio de largo plazo de un emisor: qué le pasó, cuánto pagó y cuándo convenía.

La página de valuación contesta «¿está caro HOY?». Este paquete contesta otra
pregunta, más lenta: qué le ha pasado al negocio desde que cotiza, cuánto le
rindió a quien lo compró en cada momento, y si lo que paga hoy compensa el riesgo.

Tres capas, en el orden en que dependen una de otra:

* ``mercado``      — precio y dividendos desde el IPO, SIN ajustar (P2).
* ``fundamentales`` — el negocio por periodo, con lo que se sabía en cada fecha (P1).
* ``retornos``     — retorno total, su descomposición y el retorno por fecha de entrada.

``historia`` guarda la narrativa verificada (hechos con fuente) y ``estudio`` arma
todo en un solo objeto que consumen la página y el PDF.
"""
