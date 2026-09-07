# Design System — Spread Trading Club

> **v4 — 2026-06-28.** Aplica la *Auditoría de Identidad V3* (P0/P1/P2 cerrados). Registro: *punchy quant + educativo-profesional* (terminal Bloomberg + pertenencia de Club, anti-hype). Acompaña a `.claude/brand-voice-guidelines.md`.
> **Tagline:** *"Donde el riesgo se define." / "Where risk is defined."*
> **Estado:** lista para producción — P0 cerrado (favicon Dirección D), P1 unificados (strike, descriptor, relleno), P2 entregados (componentes, data-viz, motion, plantillas).

---

## 1. Concepto visual
Terminal financiero (registro Bloomberg): fondo negro, datos en monoespaciada, precisión geométrica y **un solo acento ámbar** — con la **pertenencia de un Club**. El símbolo es la **curva de distribución** (campana) con los dos strikes de un spread vertical. Lente de marca: **probabilidad, no predicción · riesgo definido.**

---

## 2. Color tokens — "Terminal Pro"
| Token | Hex | Rol |
|---|---|---|
| `--black` | `#0A0B0D` | Fondo base (dark, default) |
| `--surface` | `#15171A` | Tarjetas |
| `--surface-2` | `#1F2630` | Superficie elevada |
| `--line` | `#262A30` | Bordes |
| `--amber` | `#F5A623` | **Único acento de marca** |
| `--amber-dim` | `#C9821A` | Hover / pressed |
| `--white` | `#F4F5F6` | Texto (dark) |
| `--gray` | `#9AA1A9` | Texto secundario / **descriptor (oscuro)** |
| `--gray-light` | `#6B6B66` | **Descriptor (sobre claro)** |
| `--paper` | `#F7F6F3` | Fondo modo claro |
| `--paper-ink` | `#14130F` | Texto modo claro |
| `--profit` | `#16C784` | Ganancia (solo charts) |
| `--loss` | `#EA3943` | Pérdida (solo charts) |

- **Token de relleno de profit (FIJO):** ámbar **14% sobre oscuro**, **20% sobre claro**. Mismo valor en todas las piezas. *(Antes 32% = "marrón sucio" — corregido por auditoría P1·05.)*
- Contraste ámbar/negro **9.6:1** (AAA). En modo claro, ámbar solo de acento, **nunca texto**.
- Acento confirmado: **Ámbar Terminal** (el azul es genérico en fintech, el verde choca con "profit", el cian tiende a cripto).

---

## 3. Tipografía
| Uso | Tipo | Pesos |
|---|---|---|
| Display / titulares | **Space Grotesk** | 500 / 700 |
| Texto / UI / cuerpo | **Inter** | 400 / 500 / 600 |
| Datos / griegas / labels | **JetBrains Mono** | 500 / 600 |

**Escala (base 4px):** 60 · 44 · 32 · 24 · 16 (cuerpo) · 12.
**Reglas:** cuerpo 16px, interlineado 1.55; títulos 1.1–1.15. Línea máx. ~70 caracteres. Cifras y griegas **siempre en mono** (alineación). Labels: mono, mayúsculas, tracking 0.18em, **ámbar**. Stack de respaldo: `system-ui, sans-serif`.

---

## 4. Logo

- **Símbolo (detallado, ≥40px):** curva de distribución ámbar + **dos strikes blancos con punto** + zona de profit al **14%**.
- **Ícono compacto (<40px / favicon) — Dirección D (oficial):** monoline — **cúpula ámbar + strikes blancos con punto, SIN relleno**. Legible a 16px. *(Salvedad: los strikes blancos piden fondo oscuro para máximo contraste.)*
- **Wordmark = TEXTO PLANO (oficial).** Sin trucos en las letras. *El carácter lo aporta el ícono al lado, no la tipografía.* (Decisión de auditoría — descartado el detalle de la "A" con strike y los ticks.)
- **Descriptor "TRADING CLUB" = siempre gris acero** (`#9AA1A9` oscuro / `#6B6B66` claro). Sin excepciones (nunca ámbar).
- **Strike = una sola forma oficial: con punto** (evoca el marcador de un precio strike).
- **Sello = "Moneda" (oficial):** disco ámbar + ícono (Dirección D) en tinta + **"SPREAD · TRADING · CLUB" curvo, sin fecha**. Mínimo **80px**.
- **Lockups:** A·Horizontal (principal — web/firma/docs) · B·Apilado (cuadrado/avatar/portada) · C·Una línea (barras estrechas/pies) · D·En contenedor (solo para aislar sobre fondos sucios).
- **Área de protección:** mínimo la altura del ícono alrededor del lockup.
- **Tamaños mínimos:** lockup horizontal ≥120px ancho · ícono detallado ≥40px · <40px → compacto · Moneda ≥80px.

**Inventario** (`brand-assets/` SVG → `png/` PNG):
| Pieza | Archivos |
|---|---|
| Ícono detallado | `icon-color` · `icon-mono-white` · `icon-mono-black` |
| Compacto / favicon | `icon-compact` → `favicon.ico` + `favicon-16/32/48/64/180/512.png` |
| Sello | `seal` (Moneda) |
| Avatar | `avatar` |
| Lockups | `lockup-horizontal` (+`-light`, `-on-dark`) · `lockup-stacked` (+`-light`, `-on-dark`) |

---

## 5. Iconografía
Línea 2px, geométrica, esquinas redondeadas, **ámbar**. Ecoan los motivos del logo (curva, strikes, ticks). Set: distribución, strikes, payoff, escudo (riesgo), columnas (estrategia), diana (precisión).

---

## 6. Espaciado y forma
Escala **4px** (4/8/12/16/24/32/48). Radios 10/14/4px. Planas, sin gradientes ni sombras pesadas; separación por `--line` o elevación `--surface`→`--surface-2`.

---

## 7. Componentes UI (construidos en auditoría §8)
- **Botones** — Primario (ámbar, texto tinta `#1A1303`) · Secundario (outline `--line`) · Ghost (texto gris). **Alto interactivo ≥44px.**
- **Campos** — estados default / foco (borde ámbar) / error (borde `--loss` + mensaje). Label mono mayúsculas.
- **Badges & tiers** — `◆ CLUB MEMBER`, `FOUNDER`, `FREE`; estados de dato `▲ +2.4%` / `▼ −0.6%` (símbolo, no solo color).
- **Navegación** — tabs (Distribución / Payoff / P&L), filtros (Abiertas/Cerradas/Historial), alertas push.

---

## 8. Estilo de gráficos / Data-viz (los gráficos SON la marca)
- **Payoff (spread vertical):** línea ámbar capada; profit zona verde, pérdida con **textura** (no solo rojo); strikes K1/K2 punteados + breakeven; etiquetas `▲ máx` / `▼ máx`.
- **Distribución (POP):** la campana de marca + zona de profit entre strikes + **POP %** etiquetada.
- **P&L:** barras; ganancia sólida `▲`, pérdida con textura `▼`.
- **Regla daltónica (obligatoria):** ganancia/pérdida **nunca solo por color** — siempre `▲/+` o `▼/−` y textura en pérdida. Ejes y grid en gris discreto; el ámbar marca lo que importa.

---

## 9. Motion (propuesta de auditoría §10)
Movimiento de **terminal**: preciso y contenido, sin rebotes.
| Token | Uso | Duración |
|---|---|---|
| Micro | hover, toggle, foco | 120ms |
| Base | tabs, dropdowns, tooltips | 200ms |
| Entrada | modales, paneles, sheets | 320ms |
| Trazo de gráfico | dibujar curva / payoff | 600ms |

**Easing estándar:** `cubic-bezier(0.4, 0, 0.2, 1)` (sin overshoot/bounce).
**Principios:** (1) el dato **entra, no salta** (fundido + subida 8px, nunca escalando); (2) **la curva se dibuja** (`stroke-dashoffset`, 600ms — gesto de marca); (3) **una cosa a la vez** (stagger 40ms en listas); (4) **respeta `prefers-reduced-motion`** (deja solo fundidos).

---

## 10. Plantillas (propuesta de auditoría §11)
- **Post 1080×1080** — logo + label "ESTRATEGIA DE LA SEMANA" + titular + métricas (POP / DTE / credit).
- **Open Graph 1200×630** — lockup + tagline.
- **Firma de email** — lockup (ícono ≥46px) + nombre/rol + dominio; disclaimer legal al pie, separado.

---

## 11. Tokens a código
```css
:root{
  --black:#0A0B0D; --surface:#15171A; --surface-2:#1F2630; --line:#262A30;
  --amber:#F5A623; --amber-dim:#C9821A; --white:#F4F5F6; --gray:#9AA1A9; --gray-light:#6B6B66;
  --paper:#F7F6F3; --paper-ink:#14130F; --profit:#16C784; --loss:#EA3943;
  --profit-fill-dark: rgba(245,166,35,0.14); --profit-fill-light: rgba(245,166,35,0.20);
  --radius-card:10px; --radius-container:14px; --radius-pill:4px;
  --dur-micro:120ms; --dur-base:200ms; --dur-enter:320ms; --dur-stroke:600ms;
  --ease:cubic-bezier(0.4,0,0.2,1);
}
```

---

## 12. Reglas de uso / mal uso
| ✅ Hacer | ❌ Evitar |
|---|---|
| Ícono compacto (Dirección D) <40px | Ícono detallado en favicon |
| Ámbar como único color de marca | Más colores (menta, oro, azul) |
| Strike siempre con punto · descriptor gris acero | Variar strike/descriptor entre piezas |
| Ámbar solo de acento sobre claro | Ámbar como texto sobre claro (falla AA) |
| Wordmark en texto plano | "Trucos" en las letras |
| Números con `▲/▼` + textura | Profit/loss solo por color |
| Sello (Moneda) ≥80px | Logo sobre fondos sucios sin contenedor |

---

## 13. Producción / outlining
Lockups con texto → convertir a curvas antes de distribuir (Inkscape: *Objeto a trazado*). Web: las fuentes cargan vía Google Fonts (no requiere outline). PNG/favicon ya exportados (`png/`).

---

## 14. Estado
**Resuelto (auditoría V3):**
- [x] P0 — Favicon: Dirección D, exportado 16–512px + `.ico`.
- [x] P1 — Strike unificado (con punto) · descriptor gris acero · relleno profit token 14/20%.
- [x] P2 — Sello = Moneda · componentes (§7) · data-viz (§8) · motion (§9) · plantillas (§10).
- [x] Gobernanza — wordmark plano oficial; quitado el detalle de la "A"; estado alineado a los archivos reales.

**Pendiente (llevar a código cuando se construya el producto):**
- [ ] Componentes §7 y data-viz §8 como código (no solo specs).
- [ ] Tokens de motion §9 a CSS real.
- [ ] Plantillas §10 como archivos editables (Canva/Figma).
