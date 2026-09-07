"""Los modelos de valuación, escritos y sustituidos con los números del emisor.

Una cifra sola no se puede auditar. `6.18%` puede ser correcto o puede ser un
denominador equivocado, y desde la pantalla no hay forma de distinguirlo. Este
módulo cierra ese hueco: por cada métrica publica **la fórmula simbólica, la
misma fórmula con los números de este emisor sustituidos, y el resultado** — de
modo que la aritmética se pueda seguir con el dedo y comprobar a mano.

Tres decisiones de diseño que importan:

* **Los operandos viajan como datos, no como texto.** ``Formula.operandos`` trae
  cada insumo con su nombre. Así la sustitución que se dibuja y el número que se
  publica salen del mismo lugar, y una prueba puede rehacer la aritmética por su
  cuenta y exigir que coincidan. Si la fórmula dibujada y el resultado se
  separaran, la pantalla estaría documentando un cálculo que no ocurre.
* **Un insumo que falta se nombra.** Cuando no se puede calcular, ``falta`` dice
  qué insumo concreto bloquea el modelo. Un guion no distingue «no vale nada» de
  «me falta un dato», y esas dos cosas no se parecen en nada.
* **El anualizado se declara.** Donde el modelo multiplica un trimestre por
  cuatro —el NOI del NAV y del cap rate implícito— la fórmula lo muestra
  explícitamente con el ``\\times 4``, en vez de esconderlo en un insumo ya
  anualizado. Es una aproximación, y se ve.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.modelo.valuacion import (
    InsumosValuacion,
    prima_riesgo_sector,
)

# --------------------------------------------------------------------------------------
# La pieza
# --------------------------------------------------------------------------------------

UNIDADES = ("porcentaje", "veces", "moneda", "numero", "bps")


@dataclass(frozen=True)
class Formula:
    """Un modelo de valuación: su fórmula, sus números y su resultado."""

    clave: str
    nombre: str
    latex: str
    definicion: str
    unidad: str = "numero"
    resultado: float | None = None
    sustitucion: str | None = None
    operandos: dict[str, float] = field(default_factory=dict)
    falta: tuple[str, ...] = ()
    nota: str = ""

    @property
    def disponible(self) -> bool:
        return self.resultado is not None and not self.falta

    def texto_resultado(self) -> str:
        if self.resultado is None:
            return "—"
        v = self.resultado
        if self.unidad == "porcentaje":
            return f"{v:.2%}"
        if self.unidad == "veces":
            return f"{v:,.2f}x"
        if self.unidad == "moneda":
            return f"{v:,.2f} USD"
        if self.unidad == "bps":
            return f"{v * 10_000:,.0f} bps"
        return f"{v:,.2f}"


def _num(v: float, decimales: int = 2) -> str:
    """Un número dentro de LaTeX. Sin separador de miles: KaTeX no lo agrupa bien."""
    return f"{v:,.{decimales}f}".replace(",", r"{,}")


# --------------------------------------------------------------------------------------
# Los modelos
# --------------------------------------------------------------------------------------


def modelos_de_valuacion(
    ins: InsumosValuacion,
    *,
    cap_rate_mercado: float,
    tasa_libre_riesgo: float | None,
    medida_flujo: str = "AFFO",
    yield_adquisiciones: float | None = None,
    peso_deuda: float = 0.35,
) -> list[Formula]:
    """Todos los modelos que la pantalla usa, con los números de ``ins`` sustituidos.

    El orden es el de la lectura: primero de dónde sale el flujo, luego los
    múltiplos que salen del flujo, luego lo que depende del balance, y al final
    lo que depende de un supuesto propio —Gordon y el spread de inversión—, que
    es donde más fácil se cuela una opinión disfrazada de aritmética.
    """
    salida: list[Formula] = []
    P = ins.precio
    N = ins.acciones_diluidas
    A = ins.affo_por_accion_ttm
    if A is None and ins.affo_ttm is not None and N > 0:
        A = ins.affo_ttm / N
    D = ins.dividendo_ttm_por_accion
    F = medida_flujo  # "AFFO" o "Core FFO": la etiqueta cambia, la aritmética no

    # ── 1. El flujo por acción ─────────────────────────────────────────────────
    salida.append(
        Formula(
            clave="flujo_por_accion",
            nombre=f"{F} por acción (TTM)",
            latex=r"A_{TTM} = \sum_{i=1}^{4} A_i \quad\text{(cuatro trimestres CONSECUTIVOS)}",
            definicion=(
                f"El {F} de los últimos doce meses por acción totalmente diluida. La suma "
                "exige que los cuatro trimestres existan y sean consecutivos: un `rolling(4)` "
                "cuenta filas, no calendario, y con un hueco devuelve un «TTM» que abarca "
                "cinco trimestres sin que nada en el resultado lo delate."
            ),
            unidad="moneda",
            resultado=A,
            sustitucion=None if A is None else rf"A_{{TTM}} = {_num(A)}\ \text{{USD/acción}}",
            operandos={} if A is None else {"A_ttm": A},
            falta=() if A is not None else (f"{F} por acción TTM (faltan trimestres consecutivos)",),
        )
    )

    # ── 2. Múltiplos sobre el flujo ────────────────────────────────────────────
    y = None if (A is None or P <= 0) else A / P
    salida.append(
        Formula(
            clave="affo_yield",
            nombre=f"{F} yield",
            latex=r"y = \dfrac{A_{TTM}}{P}",
            definicion=(
                "El rendimiento del FLUJO, no del dividendo. El precio va **sin ajustar** por "
                "dividendos: ajustarlo mueve el yield histórico y lo vuelve incomparable "
                "consigo mismo."
            ),
            unidad="porcentaje",
            resultado=y,
            sustitucion=None if y is None else rf"y = \dfrac{{{_num(A)}}}{{{_num(P)}}} = {y:.4f}",
            operandos={} if y is None else {"A_ttm": A, "P": P},
            falta=() if y is not None else (f"{F} por acción TTM" if A is None else "precio",),
        )
    )

    p_a = None if not y else 1.0 / y
    salida.append(
        Formula(
            clave="p_affo",
            nombre=f"P/{F}",
            latex=r"P/A = \dfrac{P}{A_{TTM}} = \dfrac{1}{y}",
            definicion="El múltiplo. Es exactamente el recíproco del yield, no un cálculo aparte.",
            unidad="veces",
            resultado=p_a,
            sustitucion=None if p_a is None else rf"P/A = \dfrac{{{_num(P)}}}{{{_num(A)}}} = {_num(p_a)}",
            operandos={} if p_a is None else {"P": P, "A_ttm": A},
            falta=() if p_a is not None else (f"{F} por acción TTM",),
        )
    )

    dy = None if (D is None or P <= 0) else D / P
    salida.append(
        Formula(
            clave="dividend_yield",
            nombre="Dividend yield (TTM)",
            latex=r"y_D = \dfrac{D_{TTM}}{P}",
            definicion=(
                "Los dividendos con fecha ex dentro de los últimos doce meses, sobre el precio. "
                "No es el yield de flujo: uno mide lo que reparte, el otro lo que produce."
            ),
            unidad="porcentaje",
            resultado=dy,
            sustitucion=None if dy is None else rf"y_D = \dfrac{{{_num(D)}}}{{{_num(P)}}} = {dy:.4f}",
            operandos={} if dy is None else {"D_ttm": D, "P": P},
            falta=() if dy is not None else ("dividendos TTM",),
        )
    )

    payout = None if (not A or D is None) else D / A
    salida.append(
        Formula(
            clave="payout_affo",
            nombre=f"Payout sobre {F}",
            latex=r"\text{payout} = \dfrac{D_{TTM}}{A_{TTM}}",
            definicion=(
                "**La única cobertura que significa algo.** El payout sobre utilidad neta pasa "
                "de 100% en casi todo REIT sano, porque la depreciación contable no sale de la "
                "caja: es el número que publican los sitios y está mal."
            ),
            unidad="porcentaje",
            resultado=payout,
            sustitucion=(
                None if payout is None
                else rf"\text{{payout}} = \dfrac{{{_num(D)}}}{{{_num(A)}}} = {payout:.4f}"
            ),
            operandos={} if payout is None else {"D_ttm": D, "A_ttm": A},
            falta=() if payout is not None else ("dividendos TTM" if D is None else f"{F} TTM",),
        )
    )

    # Los otros dos payouts. Se publican con su fórmula justamente porque son el
    # contraste: el mismo dividendo sobre tres flujos distintos, y los tres
    # denominadores tienen que ser TTM de cuatro trimestres consecutivos. Cuando
    # el FFO se anualizaba multiplicando un trimestre por cuatro, la comparación
    # no era entre tres medidas del flujo: era entre dos ventanas de tiempo.
    for clave, etiqueta, monto in (
        ("payout_ffo", "FFO", ins.ffo_ttm),
        ("payout_utilidad_neta", "utilidad neta", ins.utilidad_neta_ttm),
    ):
        pps = None if (not monto or N <= 0) else monto / N
        valor = None if (not pps or D is None) else D / pps
        salida.append(
            Formula(
                clave=clave,
                nombre=f"Payout sobre {etiqueta}",
                latex=(
                    r"\text{payout}_{" + etiqueta.split()[0]
                    + r"} = \dfrac{D_{TTM}}{X_{TTM} / N}"
                ),
                definicion=(
                    f"El mismo dividendo sobre el {etiqueta} de los mismos doce meses. Se "
                    "publica **solo para contrastar**: el payout sobre utilidad neta pasa de "
                    "100% en casi todo REIT sano y es el número que muestran los sitios. Los "
                    "tres denominadores se calculan con la misma regla de cuatro trimestres "
                    "consecutivos, porque si no, la comparación es entre ventanas de tiempo "
                    "distintas y no entre medidas del flujo."
                ),
                unidad="porcentaje",
                resultado=valor,
                sustitucion=(
                    None if valor is None
                    else rf"= \dfrac{{{_num(D)}}}{{{_num(monto, 0)} / {_num(N, 0)}}} = {valor:.4f}"
                ),
                operandos={} if valor is None else {"D_ttm": D, "X_ttm": monto, "N": N},
                falta=() if valor is not None else (f"{etiqueta} TTM",),
            )
        )

    # ── 3. Prima sobre la libre de riesgo ──────────────────────────────────────
    prima = None if (y is None or tasa_libre_riesgo is None) else y - tasa_libre_riesgo
    salida.append(
        Formula(
            clave="prima",
            nombre="Prima sobre la libre de riesgo",
            latex=r"\pi = y - r_f",
            definicion=(
                "La única comparación de valuación válida entre emisores — pero **no como "
                "nivel, sino como percentil de su propia historia**. Un REIT de data centers "
                "con 2.5% en el percentil 95 de su historia está más barato que uno de "
                "oficinas con 9% en el percentil 20 de la suya."
            ),
            unidad="bps",
            resultado=prima,
            sustitucion=(
                None if prima is None
                else rf"\pi = {y:.4f} - {tasa_libre_riesgo:.4f} = {prima:.4f}"
            ),
            operandos={} if prima is None else {"y": y, "r_f": tasa_libre_riesgo},
            falta=() if prima is not None else (
                "UST 10 años" if tasa_libre_riesgo is None else f"{F} yield",
            ),
        )
    )

    # ── 4. Balance: cap rate implícito y NAV ───────────────────────────────────
    noi_anual = ins.noi
    ev = ins.capitalizacion + ins.deuda_neta - ins.activos_sin_renta
    cri = None if (noi_anual is None or ev <= 0) else noi_anual / ev
    salida.append(
        Formula(
            clave="cap_rate_implicito",
            nombre="Cap rate implícito",
            latex=(
                r"c_{impl} = \dfrac{NOI_{anual}}{EV_{aj}}, \quad "
                r"EV_{aj} = P \cdot N + (\text{deuda} - \text{efectivo}) - \text{activos sin renta}"
            ),
            definicion=(
                "El cap rate al que el mercado está valuando el portafolio hoy. El EV se depura "
                "de los activos que NO generan renta inmobiliaria —cartera de préstamos, "
                "coinversiones—: sin esa resta el denominador se infla y el REIT parece más "
                "caro de lo que está."
            ),
            unidad="porcentaje",
            resultado=cri,
            sustitucion=(
                None if cri is None
                else rf"c_{{impl}} = \dfrac{{{_num(noi_anual, 0)}}}{{{_num(ev, 0)}}} = {cri:.4f}"
            ),
            operandos={} if cri is None else {"NOI_anual": noi_anual, "EV_aj": ev},
            falta=() if cri is not None else ("NOI trimestral",),
            nota=(
                "El NOI anual se obtiene multiplicando el trimestral por cuatro."
                if ins.noi_anualizado is None and ins.noi_trimestral is not None else ""
            ),
        )
    )

    nav_ps = None
    if noi_anual is not None and cap_rate_mercado > 0 and N > 0:
        valor_inmuebles = noi_anual / cap_rate_mercado
        nav_total = (
            valor_inmuebles + ins.efectivo + ins.prestamos_por_cobrar
            + ins.inversiones_no_consolidadas - ins.deuda_total
        )
        nav_ps = nav_total / N
    salida.append(
        Formula(
            clave="nav_por_accion",
            nombre="NAV por acción",
            latex=(
                r"NAV = \dfrac{\frac{NOI_{anual}}{c_{mkt}} + \text{efectivo} + "
                r"\text{préstamos} + \text{no consolidadas} - \text{deuda}}{N}"
            ),
            definicion=(
                "El valor de los inmuebles capitalizando el NOI al cap rate de MERCADO, más lo "
                "que hay en el balance, menos la deuda. **El goodwill se excluye deliberadamente**: "
                "no genera renta, y sumarlo infla el NAV justo en los emisores que más han pagado "
                "por adquisiciones. El cap rate es la palanca más sensible del modelo, y por eso "
                "es tuyo y viene con curva de sensibilidad."
            ),
            unidad="moneda",
            resultado=nav_ps,
            sustitucion=(
                None if nav_ps is None
                else rf"NAV = \dfrac{{\frac{{{_num(noi_anual, 0)}}}{{{cap_rate_mercado:.4f}}} "
                     rf"+ {_num(ins.efectivo, 0)} - {_num(ins.deuda_total, 0)}}}"
                     rf"{{{_num(N, 0)}}} = {_num(nav_ps)}"
            ),
            operandos={} if nav_ps is None else {
                "NOI_anual": noi_anual, "c_mkt": cap_rate_mercado, "efectivo": ins.efectivo,
                "prestamos": ins.prestamos_por_cobrar,
                "no_consolidadas": ins.inversiones_no_consolidadas,
                "deuda": ins.deuda_total, "N": N,
            },
            falta=() if nav_ps is not None else ("NOI trimestral",),
        )
    )

    premio = None if (nav_ps is None or nav_ps <= 0) else P / nav_ps - 1.0
    salida.append(
        Formula(
            clave="premio_descuento_nav",
            nombre="Premio / descuento sobre NAV",
            latex=r"\text{premio} = \dfrac{P}{NAV} - 1",
            definicion=(
                "Positivo, el papel cotiza con premio sobre el ladrillo; negativo, con descuento. "
                "Hereda por completo el supuesto de cap rate: no es un hecho, es una lectura."
            ),
            unidad="porcentaje",
            resultado=premio,
            sustitucion=(
                None if premio is None
                else rf"\text{{premio}} = \dfrac{{{_num(P)}}}{{{_num(nav_ps)}}} - 1 = {premio:.4f}"
            ),
            operandos={} if premio is None else {"P": P, "NAV": nav_ps},
            falta=() if premio is not None else ("NAV por acción",),
        )
    )

    # ── 5. Gordon: qué crecimiento descuenta el precio ─────────────────────────
    prima_sector = prima_riesgo_sector(ins.sector)
    r = None if tasa_libre_riesgo is None else tasa_libre_riesgo + prima_sector
    salida.append(
        Formula(
            clave="tasa_descuento",
            nombre="Tasa de descuento",
            latex=r"r = r_f + \pi_{sector}",
            definicion=(
                f"Libre de riesgo más la prima del SECTOR, no una del mercado entero. Para "
                f"{ins.sector or 'este sector'} la prima es {prima_sector:.2%}."
            ),
            unidad="porcentaje",
            resultado=r,
            sustitucion=(
                None if r is None
                else rf"r = {tasa_libre_riesgo:.4f} + {prima_sector:.4f} = {r:.4f}"
            ),
            operandos={} if r is None else {"r_f": tasa_libre_riesgo, "pi_sector": prima_sector},
            falta=() if r is not None else ("UST 10 años",),
        )
    )

    g = None
    if A is not None and r is not None and P > 0 and A > 0 and (P + A) > 0:
        g = (P * r - A) / (P + A)
    salida.append(
        Formula(
            clave="crecimiento_implicito",
            nombre="Crecimiento implícito en el precio",
            latex=(
                r"P = \dfrac{A_{TTM}(1+g)}{r-g} \;\Longrightarrow\; "
                r"g = \dfrac{P \cdot r - A_{TTM}}{P + A_{TTM}}"
            ),
            definicion=(
                "Gordon despejado. **Es aritmética, no un pronóstico**: dice qué está suponiendo "
                "el mercado, no qué va a pasar. La lectura útil es contrastarlo contra el "
                "crecimiento que el emisor ha entregado de verdad."
            ),
            unidad="porcentaje",
            resultado=g,
            sustitucion=(
                None if g is None
                else rf"g = \dfrac{{{_num(P)} \times {r:.4f} - {_num(A)}}}"
                     rf"{{{_num(P)} + {_num(A)}}} = {g:.4f}"
            ),
            operandos={} if g is None else {"P": P, "r": r, "A_ttm": A},
            falta=() if g is not None else (
                f"{F} por acción TTM" if A is None else "UST 10 años",
            ),
        )
    )

    # ── 6. Spread de inversión ─────────────────────────────────────────────────
    kd = None
    if ins.intereses_ttm and ins.deuda_total > 0:
        kd = ins.intereses_ttm / ins.deuda_total
    cmc = None if (y is None or kd is None) else peso_deuda * kd + (1 - peso_deuda) * y
    salida.append(
        Formula(
            clave="costo_marginal_capital",
            nombre="Costo marginal del capital",
            latex=r"CMC = w_d \cdot k_d + (1 - w_d) \cdot k_e, \quad k_e = y",
            definicion=(
                "Lo que cuesta financiar el siguiente dólar de adquisición. **El costo del "
                "capital accionario de un REIT es su propio yield de flujo**: emitir una acción "
                f"a un yield de 6% cuesta 6%. Peso de deuda supuesto: {peso_deuda:.0%}."
            ),
            unidad="porcentaje",
            resultado=cmc,
            sustitucion=(
                None if cmc is None
                else rf"CMC = {peso_deuda:.2f} \times {kd:.4f} + {1 - peso_deuda:.2f} "
                     rf"\times {y:.4f} = {cmc:.4f}"
            ),
            operandos={} if cmc is None else {"w_d": peso_deuda, "k_d": kd, "k_e": y},
            falta=() if cmc is not None else ("intereses TTM y deuda total",),
        )
    )

    spread = None if (yield_adquisiciones is None or cmc is None) else yield_adquisiciones - cmc
    salida.append(
        Formula(
            clave="spread_inversion",
            nombre="Spread de inversión",
            latex=r"s = y_{adq} - CMC",
            definicion=(
                "El motor de valor de un REIT que crece comprando. **Negativo significa que cada "
                "compra destruye valor por acción aunque el flujo agregado suba**: se emiten "
                "acciones baratas para comprar activos caros."
            ),
            unidad="bps",
            resultado=spread,
            sustitucion=(
                None if spread is None
                else rf"s = {yield_adquisiciones:.4f} - {cmc:.4f} = {spread:.4f}"
            ),
            operandos={} if spread is None else {"y_adq": yield_adquisiciones, "CMC": cmc},
            falta=() if spread is not None else ("costo marginal del capital",),
        )
    )

    return salida


def formula_por_clave(formulas: list[Formula], clave: str) -> Formula | None:
    for f in formulas:
        if f.clave == clave:
            return f
    return None
