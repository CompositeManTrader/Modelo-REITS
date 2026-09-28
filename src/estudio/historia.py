"""La historia verificada: hitos con fuente, eras y riesgos.

Todo hecho de esta página salió de un documento que se puede abrir: un 10-K, un
8-K, un comunicado del emisor o Nareit. Donde la fuente no alcanzó, el hecho no
entró —por ejemplo, cuántas sociedades se consolidaron al listarse en 1994: se
repite en internet y ningún documento consultado lo confirma—.

Las eras NO llevan cifras escritas a mano. Describen qué pasó y por qué; los
números —cuánto rindió, de dónde salió— los calcula ``retornos.descomponer`` al
correr, para que el texto no envejezca cuando cambien los datos.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Hito:
    fecha: dt.date
    titulo: str
    detalle: str
    categoria: str      # "emisor" | "industria"
    fuente: str
    url: str | None = None
    # Hasta dónde se verificó la fecha. Mostrar un día que solo se confirmó por año
    # sería inventar precisión: se muestra lo que la fuente sostiene.
    precision: str = "dia"   # "dia" | "mes" | "anio"

    @property
    def fecha_texto(self) -> str:
        meses = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
        if self.precision == "anio":
            return str(self.fecha.year)
        if self.precision == "mes":
            return f"{meses[self.fecha.month - 1]}-{self.fecha.year}"
        return f"{self.fecha.day}-{meses[self.fecha.month - 1]}-{self.fecha.year}"


@dataclass(frozen=True)
class Era:
    nombre: str
    inicio: dt.date
    fin: dt.date | None
    resumen: str


@dataclass(frozen=True)
class Riesgo:
    titulo: str
    texto: str


@dataclass(frozen=True)
class HistoriaEmisor:
    ticker: str
    nombre: str
    perfil: str
    modelo_de_negocio: str
    hitos: tuple[Hito, ...]
    eras: tuple[Era, ...]
    riesgos: tuple[Riesgo, ...]
    fuentes_extra: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    # Lo que solo aplica a este emisor y la página/PDF muestran junto a una gráfica o
    # en la metodología. Claves que se usan: «apalancamiento», «dividendos», «mxn».
    # Lo que se puede decir con datos (splits, escisiones, frecuencia) NO va aquí:
    # lo arma ``textos`` para que no envejezca.
    notas: dict[str, str] = field(default_factory=dict)


D = dt.date
SEC = "https://www.sec.gov/Archives/edgar/data/726728/"

INDUSTRIA: tuple[Hito, ...] = (
    Hito(D(1960, 9, 14), "Nace la figura del REIT",
         "Eisenhower firma la Ley REIT, incluida en la extensión del impuesto a los puros. "
         "Abre a cualquier ahorrador la propiedad de inmuebles comerciales con la condición "
         "de repartir casi toda la utilidad.",
         "industria", "Nareit, «The History of REITs»", "https://www.reit.com/what-reit/history-reits"),
    Hito(D(1986, 10, 22), "Los REIT pueden operar sus inmuebles",
         "La Reforma Fiscal de 1986 les permite administrar sus propiedades en vez de solo "
         "poseerlas, y por primera vez autoadministrarse. Empieza la era moderna.",
         "industria", "Nareit, «The History of REITs»", "https://www.reit.com/what-reit/history-reits", "anio"),
    Hito(D(1999, 12, 17), "Ley de Modernización de los REIT",
         "Permite subsidiarias gravables (TRS) para dar servicios a los inquilinos.",
         "industria", "Nareit, «The History of REITs»", "https://www.reit.com/what-reit/history-reits", "anio"),
    Hito(D(2001, 10, 9), "Los REIT entran al S&P 500",
         "S&P los declara elegibles; Equity Office es el primero. Los fondos indexados empiezan "
         "a comprarlos por obligación, no por convicción.",
         "industria", "Nareit, «REITs in the S&P 500»", "https://www.reit.com/news/blog/market-commentary/reits-in-the-sp-500", "mes"),
    Hito(D(2016, 8, 31), "Sector propio en la clasificación GICS",
         "Los REIT dejan de ser «financieros» y pasan al undécimo sector, Real Estate: los "
         "administradores generalistas tienen que decidir cuánto tener en vez de ignorarlos.",
         "industria", "S&P Dow Jones Indices / Nareit",
         "https://www.reit.com/investing/investor-resources/gics-classification-real-estate"),
    Hito(D(2017, 12, 22), "Deducción 199A",
         "La reforma fiscal de 2017 permite a las personas en EE. UU. deducir 20% de los "
         "dividendos ordinarios de REIT. No aplica a un residente mexicano, pero sostiene la "
         "demanda local por la acción.",
         "industria", "Jones Day, «The One Big Beautiful Bill Becomes Law»",
         "https://www.jonesday.com/en/insights/2025/07/the-one-big-beautiful-bill-becomes-law-real-estate-tax-changes"),
    Hito(D(2024, 5, 28), "Liquidación T+1 en EE. UU.",
         "La fecha ex de los dividendos mensuales pasa del último día hábil del mes al primero "
         "del siguiente. Mayo de 2024 quedó sin fecha ex; los pagos no cambiaron.",
         "industria", "SEC, regla de liquidación T+1", "https://www.sec.gov/newsroom/press-releases/2023-29"),
    Hito(D(2025, 7, 4), "La deducción 199A se vuelve permanente",
         "La ley fiscal de 2025 elimina su vencimiento, que estaba previsto para fines de 2025.",
         "industria", "Jones Day; Troutman Pepper Locke",
         "https://www.troutman.com/insights/the-one-big-beautiful-bill-act-analysis-of-key-provisions-for-the-real-estate-industry/"),
)

HISTORIA_O = HistoriaEmisor(
    ticker="O",
    nombre="Realty Income Corporation",
    perfil=(
        "Dueño de inmuebles comerciales que renta bajo contratos de arrendamiento neto: el "
        "inquilino paga el predial, el seguro y el mantenimiento, y O cobra una renta que sube "
        "con el tiempo. Se hace llamar «The Monthly Dividend Company» porque paga cada mes "
        "desde que cotiza. Al 30 de junio de 2026 tenía 15,588 propiedades rentadas a 1,798 "
        "clientes de 92 industrias, en los 50 estados de EE. UU., el Reino Unido y otros ocho "
        "países de Europa, con 98.8% de ocupación."
    ),
    modelo_de_negocio=(
        "El negocio es un diferencial: comprar inmuebles a un yield mayor que lo que le cuesta "
        "el dinero para comprarlos. Si O compra a 7% y su capital le cuesta 6%, cada compra "
        "aumenta el flujo por acción; si le cuesta 7.5%, cada compra lo diluye aunque el "
        "negocio crezca. Por eso la valuación de la acción no es solo una consecuencia del "
        "negocio: es un insumo. Cuando la acción cotiza cara, O crece rápido y por acción; "
        "cuando cotiza barata, el motor se frena. El resto del modelo —contratos largos, "
        "ocupación cercana al 99% en todas las crisis, inquilinos diversificados— es lo que "
        "hace que ese diferencial sea predecible."
    ),
    hitos=(
        Hito(D(1969, 1, 1), "Fundación",
             "William y Joan Clark fundan la empresa en Escondido, California. Su primer inmueble "
             "es un Taco Bell en Northridge, comprado directamente al fundador de Taco Bell, "
             "Glen Bell.",
             "emisor", "Realty Income, «The Realty Income Story»",
             "https://www.realtyincome.com/who-we-are/our-story", precision="anio"),
        Hito(D(1994, 10, 18), "Cotiza en la Bolsa de Nueva York",
             "Empieza a operar con la clave «O». Cierra 1994 en 17.125 dólares, entre un mínimo de "
             "15.25 y un máximo de 18.125 en el trimestre.",
             "emisor", "10-K 1995", SEC + "000072672896000009/0000726728-96-000009.txt"),
        Hito(D(1995, 8, 17), "Deja de pagarle a un asesor externo",
             "Absorbe a su asesor (R.I.C. Advisor) a cambio de 990,704 acciones y pasa a "
             "administración interna: los intereses de la dirección quedan alineados con los del "
             "accionista. En diciembre declara una distribución especial de 0.23 dólares exigida "
             "por el régimen REIT tras la fusión.",
             "emisor", "10-K 1995", SEC + "000072672896000009/0000726728-96-000009.txt"),
        Hito(D(1996, 1, 1), "Grado de inversión",
             "Obtiene calificación de grado de inversión de Moody's, S&P y Fitch: puede financiarse "
             "con bonos en vez de hipotecas.",
             "emisor", "Realty Income, «The Realty Income Story»",
             "https://www.realtyincome.com/who-we-are/our-story", precision="anio"),
        Hito(D(1997, 1, 1), "Tom Lewis, director general",
             "Sucede al fundador William Clark. Dirige la empresa dieciséis años.",
             "emisor", "Realty Income, proxy 2012; comunicado de sucesión de 2013",
             SEC + "000110465912022678/a12-1715_1def14a.htm", precision="anio"),
        Hito(D(2005, 1, 3), "Split 2 por 1",
             "Cada acción se convierte en dos. En este estudio todo lo anterior va expresado en "
             "acciones de hoy.",
             "emisor", "Datos de mercado; verificado con el primer dividendo mensual (0.15 dólares)"),
        Hito(D(2007, 1, 1), "Entra al S&P MidCap 400", "",
             "emisor", "Realty Income, «The Realty Income Story»",
             "https://www.realtyincome.com/who-we-are/our-story", precision="anio"),
        Hito(D(2013, 1, 22), "Compra American Realty Capital Trust",
             "3,200 millones de dólares y 515 propiedades en una operación. Es la primera "
             "adquisición que cambia el tamaño de la empresa de golpe; ese año sube el dividendo "
             "pagado 21.2%.",
             "emisor", "8-K, resultados 2013", SEC + "000110465914009587/a14-5563_1ex99d1.htm", precision="mes"),
        Hito(D(2013, 9, 6), "John Case, director general",
             "Sucede a Tom Lewis, que se queda como vicepresidente del consejo.",
             "emisor", "8-K del 6-sep-2013",
             "https://fintel.io/doc/sec-o-realty-income-ex991-2013-september-06-18580-404"),
        Hito(D(2015, 4, 6), "Entra al S&P 500",
             "Y al índice S&P High Yield Dividend Aristocrats.",
             "emisor", "San Diego Business Journal; Realty Income",
             "https://sdbj.com/news/2015/mar/30/realty-income-joining-sp-500-index"),
        Hito(D(2018, 10, 16), "Sumit Roy, director general",
             "Presidente desde 2015; es apenas el cuarto director general en la historia de la "
             "empresa. Sigue en el cargo.",
             "emisor", "Comunicado de Realty Income",
             "https://www.realtyincome.com/investors/press-releases/realty-income-appoints-president-and-chief-operating-officer-sumit-roy"),
        Hito(D(2019, 5, 24), "Primera compra fuera de EE. UU.",
             "Doce tiendas de Sainsbury's en el Reino Unido por 429 millones de libras, a un cap "
             "rate inicial de 5.31% y contratos de unos 15 años, financiadas con bonos a 2.73%.",
             "emisor", "Comunicado de Realty Income",
             "https://www.realtyincome.com/investors/press-releases/realty-income-announces-closing-ps429-million-sale-leaseback-transaction", precision="mes"),
        Hito(D(2020, 1, 1), "Aristócrata del dividendo",
             "Entra al S&P 500 Dividend Aristocrats: 25 años seguidos subiendo el dividendo.",
             "emisor", "Realty Income, «The Realty Income Story»",
             "https://www.realtyincome.com/who-we-are/our-story", precision="anio"),
        Hito(D(2021, 11, 1), "Fusión con VEREIT",
             "Fusión en acciones que casi duplica el portafolio. Once días después escinde las "
             "oficinas de las dos empresas en Orion Office REIT: una acción de Orion por cada "
             "diez de O. O sale del negocio de oficinas.",
             "emisor", "Comunicados de Realty Income; 8-K de Orion Office REIT",
             "https://www.realtyincome.com/investors/press-releases/realty-income-closes-merger-vereit"),
        Hito(D(2022, 12, 31), "Primer casino",
             "Compra el inmueble de Encore Boston Harbor a Wynn Resorts por 1,700 millones, a "
             "5.9% inicial y 30 años de contrato. Primera inversión fuera del comercio y la "
             "industria.",
             "emisor", "8-K, resultados 2022", SEC + "000072672823000038/realtyincomeex991q42022.htm", precision="anio"),
        Hito(D(2023, 12, 31), "Centros de datos y tres países más",
             "Primera inversión en centros de datos y entrada a tres países europeos nuevos.",
             "emisor", "Realty Income, «The Realty Income Story»",
             "https://www.realtyincome.com/who-we-are/our-story", precision="anio"),
        Hito(D(2024, 1, 23), "Fusión con Spirit Realty",
             "9,300 millones de dólares en acciones: 0.762 acciones de O por cada una de Spirit.",
             "emisor", "10-Q 1T-2024", SEC + "000072672824000077/o-20240331.htm"),
        Hito(D(2025, 12, 31), "Capital privado y crédito",
             "800 millones de capital preferente en CityCenter Las Vegas y lanzamiento de su "
             "primer fondo para terceros («U.S. Core Plus»). En 2026 anuncia una coinversión de "
             "6,000 millones en centros de datos de hiperescala.",
             "emisor", "Realty Income; 8-K 2T-2026",
             SEC + "000072672826000044/o-991q22026.htm", precision="anio"),
        Hito(D(2026, 6, 30), "Aumento número 135",
             "El dividendo sube por 115º trimestre consecutivo y 135ª vez desde 1994. Dividendo "
             "anualizado: 3.252 dólares por acción.",
             "emisor", "8-K 2T-2026", SEC + "000072672826000044/o-991q22026.htm", precision="anio"),
    ),
    eras=(
        Era("Listado y consolidación", D(1994, 10, 18), D(1999, 12, 31),
            "O sale a bolsa, internaliza su administración y obtiene grado de inversión. Es una "
            "empresa pequeña que paga casi todo su flujo, y el retorno es sobre todo el "
            "dividendo. Al final del periodo la euforia tecnológica vacía a los REIT: nadie "
            "quiere un 10% de dividendo cuando las acciones de internet se duplican en meses."),
        Era("Refugio y auge", D(1999, 12, 31), D(2007, 2, 6),
            "Revienta la burbuja tecnológica y el dinero busca flujo seguro. Las tasas bajan, "
            "los REIT entran al S&P 500 y el crédito barato empuja los precios de todo inmueble. "
            "O pasa de cotizar a menos de nueve veces su FFO a más de dieciocho: la mitad del "
            "retorno del periodo es que el mercado decidió pagar el doble por el mismo dólar."),
        Era("Crisis financiera", D(2007, 2, 6), D(2009, 3, 6),
            "Se congela el crédito y los REIT caen con todo lo que dependa de financiamiento. El "
            "negocio de O casi no se entera —el dividendo sigue subiendo, la ocupación apenas "
            "baja— pero el precio se desploma: toda la pérdida es revaluación. En 2009 invierte "
            "apenas 58 millones, a 9.7%, porque su propio capital cuesta demasiado."),
        Era("Tasas en el piso", D(2009, 3, 6), D(2013, 5, 17),
            "La Reserva Federal lleva las tasas a cero y los ahorradores persiguen cualquier "
            "rendimiento. O se vuelve un «sustituto de bono»: el mercado paga casi 28 veces su "
            "FFO en mayo de 2013. El flujo por acción apenas crece en estos años; casi todo el "
            "retorno —uno de los mejores periodos de su historia— es revaluación. Con la acción "
            "cara, compra ARCT pagando con acciones que valen mucho."),
        Era("Taper, escala y S&P 500", D(2013, 5, 17), D(2019, 12, 31),
            "El anuncio de que la Fed retirará estímulos corta el múltiplo de golpe, y después "
            "el periodo es el más «normal» de la historia: el retorno se parece a lo que produce "
            "el negocio. O entra al S&P 500, cambia dos veces de director y en 2019 cruza al "
            "Reino Unido."),
        Era("Pandemia y VEREIT", D(2019, 12, 31), D(2021, 12, 31),
            "En cuatro semanas de 2020 el precio cae casi a la mitad por miedo a que los "
            "inquilinos no paguen; se recupera cuando pagan. O entra a los Aristócratas y cierra "
            "la fusión con VEREIT, que viene con una escisión: las oficinas salen a Orion. El "
            "valor de Orion que recibió el accionista aparece aquí como una fuente propia."),
        Era("Choque de tasas", D(2021, 12, 31), D(2023, 10, 27),
            "El bono a diez años pasa de 1.5% a casi 5% en menos de dos años. El negocio sigue "
            "creciendo —más que en ningún otro momento reciente, por VEREIT— pero el múltiplo "
            "se desploma: el mercado ya no necesita a O para conseguir rendimiento. Es la "
            "demostración de que un REIT de arrendamiento neto se valúa como un bono largo."),
        Era("Spirit, Europa y nuevos verticales", D(2023, 10, 27), None,
            "Con las tasas estables en niveles altos, el múltiplo deja de caer y el retorno "
            "vuelve a salir del dividendo. O compra Spirit, se extiende por Europa y entra a "
            "casinos, centros de datos, crédito y fondos para terceros: busca yields que el "
            "arrendamiento minorista ya no da, a cambio de un negocio más complejo."),
    ),
    riesgos=(
        Riesgo("Las tasas",
               "O se comporta como un bono largo: cuando el Treasury sube, su precio baja aunque el "
               "negocio no cambie. Entre abril de 2022 y octubre de 2023 la acción perdió 38% de su "
               "valor sin que el flujo por acción bajara. Quien compra O está comprando, entre "
               "otras cosas, una apuesta a que las tasas no suben más."),
        Riesgo("El motor de crecimiento depende del precio de la acción",
               "O crece emitiendo acciones para comprar inmuebles. Cuando su acción rinde más de lo "
               "que rinden los inmuebles que compra, crecer diluye. Hoy compra a ~7.2% con la "
               "acción rindiendo alrededor de 8% de AFFO: el margen se sostiene con deuda barata "
               "en euros y con la venta de inmuebles, no con acciones."),
        Riesgo("El tamaño",
               "Con más de quince mil propiedades, sostener 4% de crecimiento por acción exige "
               "invertir del orden de 8,000 millones al año —la guía para 2026—. La ley de los "
               "grandes números empuja a buscar operaciones más grandes y en categorías nuevas."),
        Riesgo("Inquilinos bajo presión",
               "Sus tres mayores inquilinos —7-Eleven, Dollar General y Walgreens— rondan cada uno "
               "3% de la renta. Walgreens no tiene grado de inversión y planea cerrar unas 1,200 "
               "tiendas. La diversificación limita el golpe de cualquiera, pero no lo elimina."),
        Riesgo("Negocios nuevos",
               "Casinos, centros de datos, crédito y fondos para terceros rinden más que el "
               "arrendamiento minorista clásico, y por algo: son más complejos de evaluar y más "
               "cíclicos. El historial de O en esas categorías tiene pocos años."),
        Riesgo("Divisa, para quien invierte en pesos",
               "El retorno en pesos depende del tipo de cambio. Desde 1994 el peso se depreció, y "
               "eso infló el retorno en pesos —sobre todo la devaluación de 1994-95, justo al "
               "listarse O—. Una apreciación del peso resta en la misma medida."),
    ),
    fuentes_extra=(
        ("Precio y dividendos desde 1994", "Yahoo Finance (chart API), desajustado y validado "
         "contra el precio crudo del proveedor diario (2,513 días, error 0.0000%) y tres cierres "
         "NYSE."),
        ("FFO y AFFO 1996-2018", "10-K y comunicados de resultados (8-K Ex-99.1) de la SEC, uno "
         "por uno; ver data/estudios/O/anuales_primarios.csv."),
        ("Estados financieros 2008-2026", "XBRL de la SEC (companyfacts) y 8-K trimestrales."),
        ("Tasas", "Treasury a 10 años (FRED), Udibono, CETES y tipo de cambio FIX (Banxico)."),
        ("Inquilinos principales", "Suplementos trimestrales de 2025 (8-K Ex-99.2); Globe and "
         "Mail sobre Walgreens."),
    ),
    notas={
        "apalancamiento": (
            "En 2021 el cociente salta porque la deuda al cierre ya incluye a VEREIT y el "
            "EBITDAre solo dos meses de ella; el emisor reporta 5.3x pro forma en 2021 y 5.4x al "
            "cierre de 2025."
        ),
        "dividendos": (
            "La suma anual cuadra con los 10-K dentro de 0.8% de 1997 a 2007. El dividendo "
            "anualizado del último comunicado (3.252 dólares) coincide con la serie."
        ),
        "mxn": "Incluye la devaluación de 1994-95, que coincidió con el listado.",
    },
)

HISTORIAS: dict[str, HistoriaEmisor] = {"O": HISTORIA_O}
