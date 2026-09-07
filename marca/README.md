# Marca — Spread Trading Club

La fuente de verdad de la identidad, versionada junto al código para que quien
toque un color tenga la guía a la mano y no de memoria.

| Archivo | Qué es |
|---|---|
| `design-system.md` | **El documento operativo.** Tokens, tipografía, componentes, data-viz, motion. Es el que se consulta al escribir código. |
| `brand-guidelines.md` · `.docx` · `.pdf` | Las guías de identidad visual, v3. El `.md` es la extracción de texto para poder buscar y diferenciar en git; el `.docx` y el `.pdf` son los originales. |
| `guia-de-voz.md` · `.docx` | Voz de marca, posicionamiento, léxico y las reglas de cumplimiento. |
| `identidad-visual-board.pdf` | El board de identidad visual. |

## Dónde vive cada cosa en el código

La guía no se aplica a mano en cada pantalla; se aplica en dos lugares y todo lo
demás la hereda:

| Regla de la guía | Dónde se implementa |
|---|---|
| Tokens de color, tipografía, glifos, símbolo | `app/marca.py` |
| Tema de los widgets de Streamlit | `.streamlit/config.toml` |
| Estilo de todas las gráficas | `marca.registrar_plantilla_plotly()`, plantilla **por omisión** de Plotly |
| Lockup en cada pantalla | `marca.encabezado(seccion)` |

El tema va en `config.toml` y no en CSS inyectado porque Streamlit pinta sus
propios widgets: parcharlos desde fuera siempre deja una esquina sin teñir, y es
justo la que se nota. Ya pasó dos veces —un azul escrito en `rgba()` y el texto
de los avisos— y las dos están documentadas en las pruebas.

## Lo que se verifica solo

`tests/test_24_marca_y_modelos.py` falla si alguien rompe estas reglas, que son
las tres que la guía marca como no negociables:

- **Un solo acento.** Ningún color fuera de la paleta, ni en hexadecimal ni en
  `rgb()`/`rgba()`. El azul `#0969da` de la versión anterior no puede volver.
- **Nunca solo por color.** Ganancia y pérdida siempre con `▲`/`▼` — la regla
  daltónica de §8. Una captura en blanco y negro tiene que seguir siendo legible.
- **Sin emojis.** El semáforo usa `▲ ◆ ▼ ·`, que además alinean en monoespaciada.

Más: que las siete pantallas lleven el lockup, que el tema declare los tokens de
marca, que Plotly herede la plantilla, y que el símbolo dibuje sus dos strikes
**con punto** (regla P1 de la auditoría).

## Lo que la aplicación NO toma de la guía

Dos cosas, dichas para que no parezcan olvidos:

- **El modo claro.** La aplicación es una terminal y va en oscuro. Los tokens
  `PAPEL` y `PAPEL_TINTA` existen en `marca.py` porque la guía los define, pero
  ninguna pantalla los usa.
- **El sello «Moneda» y las plantillas de post.** Son piezas de contenido, no de
  producto. Viven en `brand-assets/` fuera de este repositorio.
