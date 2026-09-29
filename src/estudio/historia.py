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
         "Las operaciones se liquidan en un día en vez de dos. En los REIT que pagan cada mes, la "
         "fecha ex brincó del último día hábil del mes al primero del siguiente y un mes quedó sin "
         "fecha ex, aunque los pagos no cambiaron. Por eso el estudio suma dividendos por conteo "
         "de pagos, no por meses del calendario.",
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
        "ffo_derivado": (
            "Antes de 2015 O clasificaba las ventas de inmuebles como operaciones "
            "discontinuadas, y ni sus ganancias ni su depreciación pasan por las líneas que la "
            "fórmula toca."
        ),
    },
)

SEC_NNN = "https://www.sec.gov/Archives/edgar/data/751364/"
SITIO_NNN = "https://www.nnnreit.com/about-us/"

HISTORIA_NNN = HistoriaEmisor(
    ticker="NNN",
    nombre="NNN REIT, Inc.",
    perfil=(
        "Dueño de inmuebles comerciales de un solo inquilino en EE. UU., casi todos de comercio "
        "de servicio —talleres y lavados de autos, tiendas de conveniencia, restaurantes, "
        "entretenimiento—, rentados con contratos triple net de 10 a 20 años: el inquilino paga "
        "el predial, el seguro y el mantenimiento. Paga dividendo cada trimestre y lo ha subido "
        "37 años seguidos, desde 1990. Al 30 de junio de 2026 tenía 3,774 propiedades en los 50 "
        "estados, el Distrito de Columbia y Puerto Rico, 99.1% de ocupación y un plazo remanente "
        "promedio de 10.1 años. Se llamó Commercial Net Lease Realty hasta 2006 y National Retail "
        "Properties hasta 2023."
    ),
    modelo_de_negocio=(
        "El negocio es el mismo diferencial que el de cualquier REIT de arrendamiento neto: "
        "comprar inmuebles a un yield mayor que lo que le cuesta el dinero para comprarlos. Lo "
        "que distingue a NNN es a quién le compra. En vez de perseguir inquilinos con grado de "
        "inversión, trabaja con cadenas regionales y nacionales medianas —muchas sin "
        "calificación, evaluadas con su propio análisis de crédito— y les compra el inmueble "
        "para rentárselo de regreso (sale-leaseback). Según la empresa, cerca de 80% de sus "
        "compras vienen de esas relaciones y no de subastas. Eso le da mejores contratos y "
        "mejores yields, a cambio de más riesgo de crédito por inquilino y de una cartera más "
        "concentrada que la de Realty Income, que es cuatro veces más grande. La meta que "
        "repite la dirección es crecer POR ACCIÓN, no en tamaño."
    ),
    hitos=(
        Hito(D(1984, 1, 1), "Sale a bolsa como Golden Corral Realty",
             "Con 13 millones de dólares en activos. El estudio empieza en 1992 porque de antes no "
             "hay registro de dividendos que se pueda verificar.",
             "emisor", "NNN, «About Us»: «1984: Golden Corral Realty Corp. IPO - $13 million total "
             "assets»", SITIO_NNN, precision="anio"),
        Hito(D(1990, 1, 1), "Primer aumento de dividendo",
             "Arranca la racha de aumentos anuales que llega a 37 años en 2026.",
             "emisor", "NNN, «About Us»: «1990: Increased dividend for first time»", SITIO_NNN,
             precision="anio"),
        Hito(D(1992, 7, 10), "Llega CNL como asesor externo",
             "El grupo de James Seneff toma la administración de una empresa con 28 propiedades "
             "rentadas a un solo inquilino y abre la estrategia a todo el comercio.",
             "emisor", "Proxy de 1997 y 10-K 1997",
             "https://www.sec.gov/Archives/edgar/data/751364/0000928385-97-001865.txt"),
        Hito(D(1993, 4, 29), "Se llama Commercial Net Lease Realty",
             "Tras un año como CNL Realty Investors. En 1994 empieza a cotizar en la Bolsa de Nueva "
             "York con la clave NNN.",
             "emisor", "Encabezado EDGAR del 10-K 1997 (fecha de cambio de nombre); NNN, «About Us»",
             SEC_NNN + "000075136498000002/0000751364-98-000002.txt"),
        Hito(D(1998, 1, 1), "Deja de pagarle a un asesor externo",
             "Absorbe a CNL Realty Advisors a cambio de 220,000 acciones y hasta 1.98 millones más "
             "según el crecimiento de los activos. Las comisiones del asesor —3.7 millones de "
             "dólares en 1996— crecían con el tamaño de la cartera, no con el valor por acción.",
             "emisor", "10-K 1997", SEC_NNN + "000075136498000002/0000751364-98-000002.txt"),
        Hito(D(1998, 3, 1), "Grado de inversión y primeros bonos",
             "Coloca 100 millones de dólares en notas no garantizadas al 7.125% con vencimiento en "
             "2008: empieza a financiarse con bonos y no con hipotecas.",
             "emisor", "10-K405 1998; NNN, «About Us»",
             SEC_NNN + "0000751364-99-000006.txt", precision="mes"),
        Hito(D(2001, 12, 1), "Compra Captec Net Lease Realty",
             "135 propiedades en 26 estados, pagadas con efectivo, 4.35 millones de acciones y 2 "
             "millones de preferentes al 9%. Ese año los activos pasan de mil millones.",
             "emisor", "10-K 2001", SEC_NNN + "000075136402000031/k10_2001.htm"),
        Hito(D(2004, 2, 16), "Craig Macnab, director general",
             "Reenfoca a la empresa en el comercio y vende los inmuebles que no lo son, incluidos "
             "los rentados al gobierno de EE. UU. Dirige trece años.",
             "emisor", "10-K/A 2003; comunicado del 4T-2004",
             SEC_NNN + "000075136404000053/k10amended_2003.htm"),
        Hito(D(2006, 5, 1), "Se llama National Retail Properties",
             "La clave de pizarra sigue siendo NNN.",
             "emisor", "8-K del 1-may-2006", SEC_NNN + "000095013306002126/w20322e8vk.htm"),
        Hito(D(2008, 12, 31), "La crisis: sigue comprando y no recorta",
             "En 2008 compra 109 propiedades por 355 millones y coloca acciones a 23.05 dólares; la "
             "acción toca 10.53 en el cuarto trimestre. El dividendo trimestral se queda en 0.375 "
             "del 2T-2008 al 4T-2009, sin recorte, y el anual sigue subiendo. La ocupación baja de "
             "98% a 96%.",
             "emisor", "Comunicado del 4T-2008; 10-K 2008 y 2009",
             SEC_NNN + "000119312509016998/dex991.htm", precision="anio"),
        Hito(D(2011, 1, 1), "Entra al S&P MidCap 400", "",
             "emisor", "NNN, «About Us»", SITIO_NNN, precision="anio"),
        Hito(D(2013, 12, 31), "Año récord de compras",
             "Invierte 630 millones en 275 propiedades a un yield inicial de 7.8%.",
             "emisor", "Comunicado del 4T-2013", SEC_NNN + "000075136414000003/ex991-12312013.htm",
             precision="anio"),
        Hito(D(2017, 4, 28), "Jay Whitehurst, director general",
             "Sucede a Macnab. Su frase de la estrategia: cerca de 80% de las compras viene de "
             "relaciones directas con cadenas en crecimiento, fuera de subasta.",
             "emisor", "8-K del 29-sep-2016; Nareit (entrevista de 2018)",
             SEC_NNN + "000119312516726506/d248558dex991.htm"),
        Hito(D(2018, 9, 27), "Primer bono a 30 años",
             "300 millones al 4.80% con vencimiento en 2048. Después coloca notas a 2050, 2051 y "
             "2052, con cupones de 3.0% a 3.5%.",
             "emisor", "8-K del 27-sep-2018", SEC_NNN + "000119312518285642/d629013d8k.htm"),
        Hito(D(2020, 5, 4), "Covid: cobra la mitad de la renta de abril",
             "Cobra cerca de 52% de la renta de abril; inquilinos con 37% de la renta piden "
             "diferimientos y la empresa retira su guía. Cines, gimnasios y restaurantes de "
             "servicio completo son los giros más golpeados. Aun así, en julio sube el dividendo.",
             "emisor", "Comunicado del 1T-2020; comunicado del 15-jul-2020",
             SEC_NNN + "000075136420000065/nnn8-k20200331exhibit991.htm"),
        Hito(D(2022, 4, 29), "Stephen Horn, director general",
             "Sucede a Whitehurst; sigue en el cargo.",
             "emisor", "8-K del 21-ene-2022", SEC_NNN + "000119312522014868/d209621d8k.htm"),
        Hito(D(2023, 5, 1), "Se llama NNN REIT",
             "Sin cambio de estrategia ni de clave de pizarra.",
             "emisor", "8-K del 27-abr-2023", SEC_NNN + "000095017023015338/nnn-ex99_1.htm"),
        Hito(D(2024, 12, 31), "Dos inquilinos en problemas",
             "Recupera 64 propiedades de un operador de restaurantes del medio oeste y 32 de una "
             "mueblería en quiebra; la ocupación baja a 98.5% y se recupera después.",
             "emisor", "Comunicado del 4T-2024", SEC_NNN + "000095017025017471/nnn-ex99_1.htm",
             precision="anio"),
        Hito(D(2025, 12, 31), "Compra a 7.4% y vende lo vacío",
             "Invierte más de 900 millones a un yield inicial de 7.4% y vende 116 propiedades, 67 "
             "de ellas vacías, por 190.5 millones.",
             "emisor", "Comunicado del 4T-2025", SEC_NNN + "000119312526045612/nnn-ex99_1.htm",
             precision="anio"),
        Hito(D(2026, 7, 15), "Aumento número 37",
             "El dividendo trimestral sube 3.3%, a 0.62 dólares: 37 años seguidos de aumentos "
             "anuales. Solo otros dos REIT en bolsa tienen una racha así de larga.",
             "emisor", "Comunicado del 15-jul-2026",
             "https://www.prnewswire.com/news-releases/increased-common-dividend-declared-by-nnn-reit-inc-302823035.html"),
    ),
    eras=(
        Era("Asesor externo y la resaca de 1998-99", D(1992, 1, 1), D(1999, 12, 31),
            "Una empresa chica, administrada por un asesor externo, se convierte en un REIT de "
            "comercio diversificado: Barnes & Noble y Eckerd llegan a pesar más de 10% de la renta "
            "cada uno. En 1998 absorbe al asesor y obtiene grado de inversión. Al final del "
            "periodo los REIT se vacían por la euforia tecnológica, y NNN con ellos."),
        Era("Refugio, Captec y el reenfoque", D(1999, 12, 31), D(2007, 2, 6),
            "Revienta la burbuja tecnológica y el dinero busca flujo seguro. NNN compra Captec, "
            "cambia de director, vende lo que no es comercio y se rebautiza National Retail "
            "Properties. Las tasas bajan y el crédito barato empuja los precios de todo inmueble."),
        Era("Crisis financiera", D(2007, 2, 6), D(2009, 3, 6),
            "Se congela el crédito. NNN sigue comprando y no recorta el dividendo, pero la acción "
            "cae con todo lo que dependa de financiamiento. Los deterioros de 2008-2009 hunden el "
            "FFO que se reportó entonces; el estudio usa el FFO sin deterioros de inmuebles, como "
            "lo define Nareit desde 2011."),
        Era("Tasas en el piso", D(2009, 3, 6), D(2013, 5, 17),
            "La Reserva Federal lleva las tasas a cero y los ahorradores persiguen rendimiento. "
            "NNN pasa a publicar AFFO, entra al S&P MidCap 400 y vuelve a comprar a buen ritmo con "
            "una acción cada vez más cara."),
        Era("Crecimiento relacional", D(2013, 5, 17), D(2019, 12, 31),
            "El anuncio de que la Fed retirará estímulos corta el múltiplo; después viene la etapa "
            "madura del modelo: compras recurrentes a cadenas con las que ya tiene relación, "
            "relevo ordenado de director y los primeros bonos a 30 años. El yield inicial de sus "
            "compras baja de 7.8% en 2013 a 6.9% en 2019."),
        Era("Covid", D(2019, 12, 31), D(2021, 12, 31),
            "La pandemia golpea justo sus giros de servicio: cines, gimnasios, entretenimiento y "
            "restaurantes. Cobra la mitad de la renta de abril de 2020 —peor que Realty Income, según "
            "Motley Fool— y aun así sube el dividendo. Para fines de 2021 cobra más de 99% y recupera lo diferido."),
        Era("Choque de tasas", D(2021, 12, 31), D(2023, 10, 27),
            "El bono a diez años pasa de 1.5% a casi 5%. Cambia el director y el nombre; el "
            "negocio sigue creciendo, pero el mercado ya no necesita un REIT de arrendamiento neto "
            "para conseguir rendimiento y el múltiplo se comprime."),
        Era("Tasas altas y depuración", D(2023, 10, 27), None,
            "Con las tasas estables en niveles altos, los yields de compra suben a más de 7%. En 2023 "
            "emite solo 31 millones en acciones y crece con flujo retenido, deuda y venta de "
            "inmuebles vacíos. Resuelve dos inquilinos en problemas y en 2026 vuelve a usar su programa de "
            "colocación de acciones."),
    ),
    riesgos=(
        Riesgo("El crédito de los inquilinos",
               "Buena parte de la cartera está rentada a operadores sin calificación, evaluados con "
               "el análisis propio de NNN. Es la fuente de su mejor yield y también un riesgo real: "
               "en 2024 tuvo que recuperar 64 propiedades de un operador de restaurantes y 32 de una "
               "mueblería en quiebra."),
        Riesgo("Concentración en comercio de servicio",
               "Seis giros —servicio automotriz, conveniencia, dos tipos de restaurante, "
               "entretenimiento y agencias de autos— generan 63% de la renta; los cinco mayores "
               "inquilinos, 17.8%. El entretenimiento fue el giro más frágil en 2020: los cines "
               "pagaron 2% de su renta del segundo trimestre."),
        Riesgo("Las tasas",
               "Con contratos de diez años en promedio y rentas fijas, la acción se comporta como "
               "un bono largo: cuando el Treasury sube, su precio baja aunque el negocio no cambie. "
               "La deuda está casi toda a tasa fija y a diez años, pero las notas de 2020-2021 a "
               "cupones de 2.5% a 3.5% costarán más cuando se refinancien."),
        Riesgo("El motor de crecimiento depende del precio de la acción",
               "NNN crece emitiendo acciones y deuda para comprar inmuebles a ~7.4%. Si su acción se "
               "abarata frente a ese yield, crecer por acción se vuelve difícil: en 2023, con la "
               "acción barata, emitió solo 31 millones en acciones."),
        Riesgo("Menos escala que Realty Income",
               "Con 3,774 propiedades, todas en EE. UU. y de comercio, cada inquilino pesa más y no "
               "hay negocios fuera del comercio que compensen un mal año del sector. A cambio "
               "opera con 85 empleados."),
        Riesgo("Divisa, para quien invierte en pesos",
               "Todos los inmuebles y el dividendo están en dólares. El retorno en pesos suma la "
               "variación del tipo de cambio: una apreciación del peso resta en la misma medida."),
    ),
    fuentes_extra=(
        ("Precio y dividendos desde 1992", "Yahoo Finance (chart API), validado contra el precio "
         "crudo del proveedor diario (2,513 días, error 0.0000%), 43 cierres NYSE publicados por "
         "el emisor (1996-2024) y los rangos trimestrales de 1992 a 1995."),
        ("FFO, AFFO y la operación 1992-2025", "10-K, prospectos 424B e informes anuales de 1992 a "
         "2008; comunicados de resultados (8-K Ex-99.1) de 2009 a 2025, uno por uno; ver "
         "data/estudios/NNN/anuales_primarios.csv."),
        ("Estados financieros 2008-2026", "XBRL de la SEC (companyfacts) y 8-K trimestrales."),
        ("Tasas", "Treasury a 10 años (FRED), Udibono, CETES y tipo de cambio FIX (Banxico)."),
        ("Historia corporativa", "10-K, 8-K y proxies de la SEC; nnnreit.com («About Us»); Nareit."),
    ),
    notas={
        "mxn": "El tipo de cambio de la base empieza en noviembre de 1993; incluye la devaluación "
               "de 1994-95.",
        "ffo_derivado": (
            "Buena parte de la diferencia de 2011 a 2021 son los dividendos preferentes: en XBRL la "
            "utilidad del "
            "accionista común de NNN aparece igual a la utilidad neta, sin restarlos. En 2020, por "
            "ejemplo, la fórmula da 0.10 dólares por acción de más, lo mismo que pagó de "
            "preferentes por acción. NNN redimió sus preferentes en 2021 —el capital preferente "
            "pasa de 345 millones a cero— y desde 2022 la fórmula cuadra. El EBITDAre no resta "
            "preferentes, pero el estudio lo calcula solo desde que la fórmula cuadra, por "
            "consistencia."
        ),
        "dividendos": (
            "Los 68 dividendos trimestrales de 1992 a 2008 y los dividendos anuales de 2009 a 2025 "
            "coinciden uno por uno con los que reporta el emisor; no hizo falta corregir ninguno."
        ),
        "apalancamiento": (
            "El emisor publica su deuda neta ÷ EBITDAre desde 2011: entre 4.0x (2016) y 5.6x (2025), "
            "con una base que cambia entre el último trimestre anualizado y los últimos cuatro. "
            "Desde 2022 la cifra derivada aquí queda a una décima de la reportada."
        ),
    },
)

SEC_WPC = "https://www.sec.gov/Archives/edgar/data/1025378/"

HISTORIA_WPC = HistoriaEmisor(
    ticker="WPC",
    nombre="W. P. Carey Inc.",
    perfil=(
        "Dueño de inmuebles industriales, almacenes y comercio de un solo inquilino, rentados "
        "con contratos largos de arrendamiento neto en EE. UU. y Europa. Casi la mitad de sus "
        "rentas sube con la inflación. Al 30 de junio de 2026 tenía 1,748 propiedades rentadas a "
        "384 inquilinos, 98.5% de ocupación y un plazo remanente promedio de 12.2 años; 61% de "
        "la renta viene de EE. UU. y 33% de Europa. Fue una sociedad (LLC) que además "
        "administraba fondos inmobiliarios hasta 2012, cuando se convirtió en REIT; en 2023 "
        "escindió sus oficinas y recortó el dividendo por primera vez."
    ),
    modelo_de_negocio=(
        "Hoy es un REIT de arrendamiento neto «puro»: compra inmuebles críticos para la operación "
        "de una empresa —muchas veces a la propia empresa, que se lo renta de regreso— con "
        "contratos de más de diez años en los que el inquilino paga impuestos, seguro y "
        "mantenimiento. Lo distintivo es dónde y cómo: un tercio de la renta está en Europa y "
        "casi la mitad se ajusta con la inflación, no con un porcentaje fijo. Eso lo protegió en "
        "2022 y lo expone cuando la inflación baja. Durante su primera etapa fue otra cosa: una "
        "LLC con dos negocios, sus inmuebles y la administración de los fondos no cotizados CPA, "
        "que en 2011 ganaba más que la renta propia. Esa mezcla es la razón de que su historia de "
        "valuación tenga dos épocas distintas."
    ),
    hitos=(
        Hito(D(1973, 1, 1), "Fundación",
             "Wm. Polk Carey funda W. P. Carey & Co. para agrupar a inversionistas individuales en "
             "inmuebles rentados a largo plazo.",
             "emisor", "W. P. Carey, «Our History»", "https://www.wpcarey.com/about-us/our-history",
             precision="anio"),
        Hito(D(1998, 1, 21), "Cotiza como Carey Diversified",
             "Nueve fondos CPA —los primeros programas de la empresa— se consolidan en Carey "
             "Diversified LLC, que empieza a cotizar en la Bolsa de Nueva York con la clave CDC.",
             "emisor", "10-K405 2000", SEC_WPC + "000095012301002868/y47104e10-k405.txt"),
        Hito(D(2000, 6, 28), "Nace W. P. Carey & Co. LLC",
             "Carey Diversified absorbe al administrador de los fondos a cambio de 8 millones de "
             "acciones y cambia la clave a WPC. Desde entonces tiene dos negocios: sus inmuebles y "
             "las comisiones por administrar los fondos CPA.",
             "emisor", "10-K405 2000", SEC_WPC + "000095012301002868/y47104e10-k405.txt"),
        Hito(D(2005, 3, 17), "Gordon DuGan, director general",
             "El fundador deja la dirección y se queda como presidente del consejo.",
             "emisor", "8-K de mar-2005", "https://www.sec.gov/Archives/edgar/data/0001025378/000095012305003446/y07068ae8vk.txt"),
        Hito(D(2008, 1, 1), "Primera distribución especial",
             "0.27 dólares pagados en enero, aparte del dividendo del cuarto trimestre de 2007.",
             "emisor", "Suplemento de resultados 2007 (8-K)",
             "https://www.sec.gov/Archives/edgar/data/0001025378/000095012308002344/y50348exv99w1.htm",
             precision="mes"),
        Hito(D(2009, 3, 31), "La crisis",
             "La acción cae de un máximo de 34.62 dólares en el primer trimestre de 2008 a un mínimo "
             "de 16.15 un año después. Aun así, el dividendo sube cada trimestre, y en enero de 2010 "
             "paga otra especial de 0.30.",
             "emisor", "10-K 2008 y 2009", SEC_WPC + "000095012310017973/c96713e10vk.htm",
             precision="anio"),
        Hito(D(2010, 7, 6), "Relevo abrupto en la dirección",
             "DuGan renuncia por «diferencias irreconciliables» con el presidente del consejo; "
             "Trevor Bond toma la dirección y queda en firme en septiembre.",
             "emisor", "8-K del 6-jul-2010",
             "https://www.sec.gov/Archives/edgar/data/0001025378/000095012310063605/y85458e8vk.htm"),
        Hito(D(2012, 1, 2), "Muere el fundador",
             "Wm. Polk Carey muere a los 81 años. En 2011 la administración de fondos había ganado "
             "más que los inmuebles propios: 73.4 contra 65.8 millones.",
             "emisor", "8-K del 4-ene-2012; MD&A 2012",
             SEC_WPC + "000119312512001563/d275412dex991.htm"),
        Hito(D(2012, 9, 28), "Se convierte en REIT",
             "La LLC pasa a ser W. P. Carey Inc. y absorbe el fondo CPA:15 por 2,600 millones de "
             "dólares con deuda: 1.25 dólares y 0.2326 acciones por cada acción del fondo. El "
             "dividendo sube 15%. El argumento: simplificar el reporte fiscal y atraer a los fondos "
             "que solo compran REIT.",
             "emisor", "8-K12G3 y comunicado del 14-sep-2012",
             SEC_WPC + "000119312512415552/d421099d8k12g3.htm"),
        Hito(D(2014, 1, 31), "Absorbe CPA:16 y obtiene grado de inversión",
             "Unos 4,000 millones con deuda, pagados con 0.1830 acciones por acción del fondo. "
             "Obtiene BBB y Baa2 y empieza a financiarse con bonos, en dólares y en euros.",
             "emisor", "10-K 2013; comunicado del 4T-2013",
             "https://www.sec.gov/Archives/edgar/data/0001025378/000102537814000012/wpc2013q48-kerexh991.htm"),
        Hito(D(2016, 2, 10), "Mark DeCesaris, director general",
             "Bond deja la empresa; su director de finanzas toma el cargo.",
             "emisor", "8-K del 10-feb-2016",
             "https://www.sec.gov/Archives/edgar/data/0001025378/000110465916095553/a16-4007_18k.htm"),
        Hito(D(2017, 6, 15), "Deja de levantar fondos entre ahorradores",
             "Sale de la venta de fondos no cotizados: la empresa se concentra en sus inmuebles.",
             "emisor", "8-K del 15-jun-2017",
             "https://www.sec.gov/Archives/edgar/data/0001025378/000110465917039591/a17-14610_28k.htm"),
        Hito(D(2018, 1, 1), "Jason Fox, director general",
             "En la empresa desde 2002. Sigue en el cargo.",
             "emisor", "Proxy de 2018", SEC_WPC + "000104746918002478/a2235072zdef14a.htm"),
        Hito(D(2018, 10, 31), "Absorbe CPA:17",
             "5,900 millones con deuda. La empresa dice que su utilidad queda «casi toda» en renta "
             "inmobiliaria, que el mercado paga a un múltiplo mayor que las comisiones.",
             "emisor", "8-K del 31-oct-2018; presentación del 18-jun-2018",
             SEC_WPC + "000110465918065081/a18-37294_2ex99d1.htm"),
        Hito(D(2022, 8, 1), "Absorbe CPA:18 y cierra el negocio de fondos",
             "2,700 millones. Con esta fusión termina su salida de los fondos no cotizados; al mes "
             "siguiente Moody's la sube a Baa1.",
             "emisor", "8-K del 1-ago-2022", SEC_WPC + "000110465922084447/tm2222201d1_ex99-2.htm"),
        Hito(D(2023, 9, 21), "Plan para salir de oficinas",
             "Anuncia la escisión de 59 oficinas y la venta de otras 87, y un nuevo pago de "
             "dividendo de 70-75% del AFFO. La acción cae 8% ese día.",
             "emisor", "8-K del 21-sep-2023; Commercial Property Executive",
             SEC_WPC + "000110465923102585/tm2326526d1_ex99-1.htm"),
        Hito(D(2023, 11, 1), "Escinde NLOP",
             "Una acción de Net Lease Office Properties por cada 15 de WPC. En este estudio el valor "
             "de NLOP que recibió el accionista entra al retorno total como distribución en especie.",
             "emisor", "8-K del 6-oct-2023 y del 2-nov-2023",
             SEC_WPC + "000110465923113522/tm2329364d1_ex99-1.htm"),
        Hito(D(2023, 11, 30), "Entra al S&P MidCap 400", "",
             "emisor", "S&P Dow Jones Indices",
             "https://www.prnewswire.com/news-releases/carlyle-group-and-wp-carey-set-to-join-sp-midcap-400-others-to-join-sp-smallcap-600-301998451.html"),
        Hito(D(2023, 12, 7), "Primer recorte del dividendo",
             "De 1.071 a 0.86 dólares por trimestre (−19.7%), «reflejando la salida de oficinas y "
             "un payout más bajo». Termina una racha de aumentos desde 1998. En 2023 la acción "
             "pierde 17.1%.",
             "emisor", "Comunicado del 4T-2023",
             SEC_WPC + "000102537824000034/wpc2023q48-kerexh991.htm"),
        Hito(D(2024, 10, 14), "True Value en quiebra",
             "Nueve propiedades, 1.4% de la renta; el inquilino siguió al corriente.",
             "emisor", "Comunicado del 3T-2024", SEC_WPC + "000102537824000137/wpc2024q38-kerexh991.htm"),
        Hito(D(2025, 12, 31), "Año récord de inversión",
             "2,100 millones a un cap rate inicial de ~7.6%, y ventas por 1,500 millones, sobre todo "
             "bodegas de autoalmacenaje que operaba directamente.",
             "emisor", "8-K del 7-ene-2026; comunicado del 4T-2025",
             SEC_WPC + "000102537826000005/wpc2026q1investmentvolumee.htm", precision="anio"),
        Hito(D(2026, 6, 16), "Insolvencia de Hellweg",
             "Cadena alemana de ferretería con 16 propiedades y ~15 millones de renta. En septiembre "
             "la empresa dice que espera recuperar casi toda la renta.",
             "emisor", "8-K del 16-jun-2026 y del 10-sep-2026",
             SEC_WPC + "000102537826000091/wpc-20260616.htm"),
        Hito(D(2026, 9, 15), "Dividendo de 0.95",
             "Sube cada trimestre desde el recorte: +10.5% desde 0.86, todavía 11% abajo del 1.071 "
             "de 2023 (sin contar el valor de NLOP recibido).",
             "emisor", "Comunicado de W. P. Carey",
             "https://www.prnewswire.com/news-releases/w-p-carey-increases-quarterly-dividend-to-0-950-per-share-302882645.html",
             precision="mes"),
    ),
    eras=(
        Era("Carey Diversified", D(1998, 1, 21), D(1999, 12, 31),
            "La empresa listada nace de consolidar nueve fondos CPA: una cartera de arrendamiento "
            "neto administrada por fuera. Abre oficina en Londres, su primer paso en Europa. Como "
            "a todo REIT, la euforia tecnológica le quita compradores."),
        Era("La LLC de dos motores", D(1999, 12, 31), D(2007, 2, 6),
            "Desde 2000 combina la renta de sus inmuebles con las comisiones de los fondos CPA, que "
            "crecen con lo que se recauda entre ahorradores y con las compras que hacen. Es una "
            "utilidad menos predecible que la de un REIT puro. Las tasas bajan y el crédito barato "
            "empuja los precios de todo inmueble."),
        Era("Crisis financiera", D(2007, 2, 6), D(2009, 3, 6),
            "Se seca el financiamiento, quiebran inquilinos y los fondos CPA reciben más "
            "solicitudes de retiro. WPC sigue subiendo el dividendo y paga dos especiales, pero la "
            "acción cae a la mitad."),
        Era("Recuperación y camino a REIT", D(2009, 3, 6), D(2012, 9, 28),
            "La acción se recupera y el negocio de fondos llega a su mayor peso. Hay turbulencia en "
            "la dirección y muere el fundador. En febrero de 2012 anuncia la conversión a REIT con "
            "la compra de CPA:15, para atraer a los fondos que solo invierten en REIT."),
        Era("El REIT consolidador", D(2012, 9, 28), D(2019, 12, 31),
            "Como REIT absorbe CPA:16 y CPA:17, obtiene grado de inversión, emite bonos en euros y "
            "deja de levantar fondos. La utilidad pasa a ser casi toda renta. Cambia dos veces de "
            "director."),
        Era("Pandemia", D(2019, 12, 31), D(2021, 12, 31),
            "La empresa reporta haber cobrado bien durante el Covid. Deja de administrar los fondos "
            "hoteleros y en 2021 invierte a un ritmo récord."),
        Era("Inflación y la decisión de salir de oficinas", D(2021, 12, 31), D(2023, 10, 27),
            "Las rentas ligadas a inflación aceleran el crecimiento, y con CPA:18 termina el "
            "negocio de fondos. Pero suben las tasas y las oficinas —16% de la renta— se vuelven "
            "un lastre. En septiembre de 2023 anuncia la salida de oficinas y un dividendo más bajo."),
        Era("WPC sin oficinas", D(2023, 10, 27), None,
            "Escinde NLOP, recorta el dividendo, vende el resto de las oficinas y reconstruye el "
            "AFFO. El dividendo vuelve a subir cada trimestre. Invierte a cap rates de ~7.6% y "
            "enfrenta problemas puntuales de crédito."),
    ),
    riesgos=(
        Riesgo("El crédito de los inquilinos",
               "Solo 22.7% de la renta viene de inquilinos con grado de inversión, contra 29.9% a "
               "mediados de 2023. True Value (2024) y Hellweg (2026) muestran que los problemas "
               "son puntuales pero recurrentes; la guía de 2026 ya incluye una pérdida potencial "
               "por eventos de crédito."),
        Riesgo("Europa y el tipo de cambio",
               "Un tercio de la renta está en Europa. La deuda en euros cubre una parte, pero un "
               "dólar fuerte reduce el AFFO en dólares. Para quien invierte en pesos el riesgo es "
               "doble: el dólar contra el peso, y el euro contra el dólar debajo."),
        Riesgo("Las tasas",
               "Con contratos de 12 años en promedio, la acción se comporta como un bono largo. Su "
               "deuda tiene una tasa promedio de 3.2% y vence en 4.5 años en promedio: los "
               "refinanciamientos recientes salen más caros (5.2% en dólares contra 4.25%)."),
        Riesgo("El motor de crecimiento",
               "Compra a ~7.6% inicial. Si la acción se abarata o las tasas suben, el margen contra "
               "su costo de capital se cierra. Fue justo el argumento de la salida de oficinas de "
               "2023."),
        Riesgo("La inflación, en los dos sentidos",
               "48% de las rentas sube con la inflación (30% sin tope). Eso llevó el crecimiento "
               "interno a más de 4% en 2023, pero en 2026 ya fue de 2.6%: si la inflación baja, el "
               "crecimiento se desacelera."),
        Riesgo("Ejecución después de la salida de oficinas",
               "La tesis depende de seguir vendiendo y comprando bien —1,500 millones vendidos y "
               "2,100 invertidos en 2025— y de rerrentar cuando falla un inquilino. El dividendo "
               "sigue 11% abajo del de 2023."),
    ),
    fuentes_extra=(
        ("Precio y dividendos desde 1998", "Yahoo Finance (chart API), desajustado por la escisión "
         "de NLOP y validado contra el precio crudo del proveedor diario (2,527 días, error "
         "0.0000%) y contra 63 cierres publicados por el emisor en 10-K, informes anuales, "
         "proxies y prospectos (data/estudios/WPC/anclas.csv). Las tres distribuciones "
         "especiales se separan del dividendo regular."),
        ("FFO, AFFO y la operación 1998-2025", "10-K, informes anuales, proxies y comunicados de "
         "resultados (8-K Ex-99.1), uno por uno; ver data/estudios/WPC/anuales_primarios.csv. "
         "FFO y AFFO de cada trimestre desde 2019, de su comunicado: trimestrales_primarios.csv."),
        ("Estados financieros 2008-2026", "XBRL de la SEC (companyfacts) y 8-K trimestrales."),
        ("Tasas", "Treasury a 10 años (FRED), Udibono, CETES y tipo de cambio FIX (Banxico)."),
        ("Historia corporativa", "10-K, 8-K, 8-K12G3 y proxies de la SEC; wpcarey.com; filings de "
         "NLOP; S&P Dow Jones Indices."),
    ),
    notas={
        "apalancamiento": (
            "Como LLC, de 1998 a 2011, su deuda fue de 23% a 40% de los activos en libros; como "
            "REIT, con las fusiones de los fondos CPA pagadas en parte con deuda, de 34% a 53%. La "
            "empresa publica deuda neta ÷ EBITDA ajustado desde 2012: entre 4.8x (2013) y 6.7x "
            "(2012), 5.9x en 2025. Esa cifra anualiza el último trimestre, a prorrata, y excluye "
            "las partidas que separan su FFO de su AFFO (875 contra 1,098 millones en 2025); la de "
            "aquí es EBITDAre de Nareit de doce meses y por eso queda arriba: 7.2x en 2025, con "
            "las compras del año contando solo desde que se hicieron."
        ),
        "ffo_derivado": (
            "La conciliación del emisor suma partidas que la fórmula sobre XBRL no alcanza: la parte "
            "proporcional de la depreciación de sus coinversiones y de los fondos CPA donde tenía "
            "participación (10.6 millones en 2009; 5.3 en 2011) y, en 2018, resta 47.8 millones de "
            "«ganancia por cambio de control» de inversiones al absorber CPA:17 —0.41 dólares por "
            "acción—, que no es una venta de inmuebles y la fórmula no quita."
        ),
        "dividendos": (
            "El proveedor suma cada distribución especial al dividendo del trimestre: 0.27 dólares "
            "(pagada en enero de 2008), 0.30 (enero de 2010) y 0.11 (cuarto trimestre de 2013). Se "
            "separan para que no inflen el yield ni dibujen aumentos y recortes que no ocurrieron."
        ),
    },
)

HISTORIAS: dict[str, HistoriaEmisor] = {"O": HISTORIA_O, "NNN": HISTORIA_NNN, "WPC": HISTORIA_WPC}
