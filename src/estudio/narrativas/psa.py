"""Narrativa verificada de Public Storage (PSA).

Cada hecho sale de un documento de la SEC que se puede abrir. Hasta mayo de 2007 el
emisor presentó con el CIK 318380 (Storage Equities, Inc. y después Public Storage,
Inc., de California); desde la reorganización en Maryland, con el CIK 1393311.
"""

from src.estudio.historia import D, Era, HistoriaEmisor, Hito, Riesgo

SEC_PSI = "https://www.sec.gov/Archives/edgar/data/318380/"
SEC_PSA = "https://www.sec.gov/Archives/edgar/data/1393311/"

HISTORIA_PSA = HistoriaEmisor(
    ticker="PSA",
    nombre="Public Storage",
    perfil=(
        "Dueño y operador de bodegas de autoalmacenaje (self-storage): cuartos cerrados de "
        "distintos tamaños que renta mes a mes a personas y negocios para guardar sus cosas, "
        "con la marca Public Storage y sus puertas naranjas. Es el mayor dueño de bodegas de "
        "EE. UU. Al 30 de junio de 2026 tenía participación en 3,196 bodegas con 231.4 "
        "millones de pies cuadrados rentables (unos 21.5 millones de m²) en 40 estados, "
        "administraba otras 388 de terceros y era dueño de 35% de Shurgard, que tiene 335 "
        "bodegas en siete países de Europa occidental y cotiza en Bruselas. La ocupación "
        "promedio de sus 2,755 bodegas comparables fue 92.5% en el segundo trimestre. En julio "
        "de 2026 cerró la compra de National Storage Affiliates —con la que dijo operar más de "
        "4,500 locales con su marca— y en septiembre sumó las 68 bodegas de PS Canada. Paga "
        "3.00 dólares de dividendo por trimestre (12.00 al año) desde 2023. Se llamó Storage "
        "Equities, Inc. de 1980 a 1995 y Public Storage, Inc. hasta 2007, cuando se reorganizó "
        "como fideicomiso de Maryland con su nombre actual."
    ),
    modelo_de_negocio=(
        "Es un inmueble operado, no rentado. En un REIT de arrendamiento neto (triple net) un "
        "solo inquilino firma por 10 o 20 años y paga el predial, el seguro y el mantenimiento; "
        "aquí Public Storage renta miles de cuartos, casi siempre mes a mes, paga ella todos "
        "esos gastos y gana o pierde con la ocupación y el precio de cada mes, como un hotel de "
        "estancias largas. Atrae clientes con promociones y ajusta seguido las rentas de nuevos "
        "y de existentes: a quien se queda le sube la renta con el tiempo, y por eso quien llega "
        "paga mucho menos que quien se va —13.10 contra 18.98 dólares por pie cuadrado al año "
        "entre abril y mayo de 2026—. Con contratos tan cortos puede subir precios rápido (sus "
        "ingresos comparables crecieron 14.8% en 2022), pero también resiente rápido los años "
        "flojos y las bodegas nuevas de la competencia (bajaron 0.7% en 2024). Lo que la "
        "distingue es la escala: es la más grande del país, centraliza precios, mercadotecnia "
        "y mantenimiento, y reporta márgenes operativos directos de 78% en sus bodegas "
        "comparables, contra 70% de NSA, la empresa que acaba de comprar. Gana además con el "
        "seguro de lo almacenado —una subsidiaria lo reasegura—, la venta de candados y cajas, "
        "la administración de bodegas de terceros y, desde 2024, préstamos puente a otros "
        "dueños; también construye y amplía bodegas. Y se financia distinto: durante décadas "
        "usó flujo retenido y acciones preferentes —más caras que la deuda, pero sin "
        "vencimientos que refinanciar— y colocó su primer bono público apenas en 2017."
    ),
    hitos=(
        Hito(D(1972, 1, 1), "Fundación",
             "B. Wayne Hughes funda la organización Public Storage, que construye y opera "
             "mini-bodegas en EE. UU. y Canadá. Hasta 1995 esa organización asesora y opera, a "
             "cambio de comisiones, al REIT que hoy es Public Storage.",
             "emisor", "10-K 2002 y 10-K 1994", SEC_PSI + "000031838003000004/q402psi.txt",
             precision="anio"),
        Hito(D(1984, 10, 19), "Cotiza en la Bolsa de Nueva York",
             "Storage Equities, Inc., constituida en California el 10 de julio de 1980 como REIT "
             "de mini-bodegas, paga dividendos trimestrales desde 1981, su primer año completo. "
             "En 1995 su clave todavía es SEQ.",
             "emisor", "10-K 1994; prospecto 424B5 de mayo de 1995",
             SEC_PSI + "0000898430-95-000361.txt"),
        Hito(D(1995, 11, 16), "Absorbe a su operador y se llama Public Storage",
             "Se fusiona con Public Storage Management, la empresa de Hughes que la asesoraba y "
             "operaba, por unos 549 millones de dólares en acciones: deja de pagar comisiones "
             "(6% de los ingresos por operar sus bodegas, más la del asesor), se queda con la "
             "marca y duplica su tamaño. Pasa a llamarse Public Storage, Inc. y su clave cambia "
             "de SEQ a PSA; según la empresa, al poco tiempo mejora su calificación crediticia.",
             "emisor", "8-K del 29-nov-1995; 10-K 1995; prospecto 424B5 de dic-1995",
             SEC_PSI + "0000898430-95-002503.txt"),
        Hito(D(1998, 3, 17), "Nace PS Business Parks",
             "Sus locales comerciales y de oficinas, reunidos desde enero de 1997 en un REIT "
             "privado, se fusionan con un REIT afiliado que cotiza y que se rebautiza PS Business "
             "Parks. Al cierre de 1998 Public Storage tiene cerca de 40% de PSB, dueña de 106 "
             "inmuebles en 11 estados.",
             "emisor", "10-K 1998", SEC_PSI + "0000318380-99-000007.txt"),
        Hito(D(1999, 3, 12), "Compra Storage Trust Realty",
             "Fusión con un REIT de bodegas que cotizaba y no era afiliado: 215 bodegas en 16 "
             "estados, pagadas con 0.86 acciones de Public Storage por cada una de Storage Trust. "
             "Valor empresa de unos 600 millones de dólares, deuda incluida.",
             "emisor", "10-K 1999", SEC_PSI + "0000318380-00-000005.txt"),
        Hito(D(2002, 11, 7), "Ron Havner, director general",
             "Sucede a B. Wayne Hughes, que se queda como presidente del consejo. Havner llegó en "
             "1986, fue director de finanzas de 1991 a 1996 y dirigía PS Business Parks.",
             "emisor", "10-K 2002", SEC_PSI + "000031838003000004/q402psi.txt"),
        Hito(D(2006, 8, 22), "Fusión con Shurgard",
             "Compra Shurgard Storage Centers —487 bodegas en EE. UU. y participación en 160 de "
             "Europa— por unos 5,300 millones de dólares: 0.82 acciones por acción, más la deuda "
             "asumida. Con ella entra a siete países de Europa occidental.",
             "emisor", "10-K 2006", SEC_PSI + "000031838007000012/psi10k1206.txt"),
        Hito(D(2007, 6, 1), "Fideicomiso de Maryland",
             "Deja de ser una sociedad de California y se reorganiza como fideicomiso de "
             "inversión inmobiliaria de Maryland, con el nombre Public Storage. Presenta sus "
             "reportes con un registro nuevo en la SEC, como sucesora; la clave sigue siendo PSA.",
             "emisor", "8-K12G3 del 4-jun-2007; 10-K 2009", SEC_PSA + "000119312507128949/d8k12g3.htm"),
        Hito(D(2008, 3, 31), "Vende 51% de Shurgard Europe",
             "Un fondo de pensiones del estado de Nueva York paga unos 383 millones de euros "
             "(605.6 millones de dólares) por 51% de la operación europea; Public Storage conserva "
             "49%, la sigue administrando y deja de consolidarla. En octubre de 2018 Shurgard "
             "sale a la bolsa de Bruselas y la participación baja a 35.2% sin que venda acciones.",
             "emisor", "8-K del 4-abr-2008; 10-K 2018", SEC_PSA + "000139331108000070/ps8k_33108.txt"),
        Hito(D(2008, 12, 31), "La crisis: no recorta y recompra con descuento",
             "En 2008 sube el dividendo trimestral de 0.50 a 0.55 dólares, paga una especial de "
             "0.60 en diciembre y en 2009 sostiene 0.55 cada trimestre. Con solo 644 millones de "
             "deuda, recompra preferentes con valor nominal de 103.2 millones por 66.9 millones, "
             "en febrero de 2009 compra 110.2 millones de sus bonos y frena casi todo su "
             "desarrollo. La acción cotiza entre 105.87 y 52.52 dólares en el cuarto trimestre de "
             "2008 y toca 45.35 en el primero de 2009.",
             "emisor", "10-K 2008, 2009 y 2011", SEC_PSA + "000139331110000004/ps10k_123109.htm",
             precision="anio"),
        Hito(D(2015, 11, 3), "Primera deuda en euros",
             "Coloca 242 millones de euros con inversionistas institucionales, y 100 millones más "
             "en 2016, como cobertura de su inversión en Shurgard Europe; después emite bonos "
             "públicos en euros: 500 millones al 0.875% a 2032 (enero de 2020) y 700 millones al "
             "0.500% a 2030 (septiembre de 2021). El efecto cambiario de esa deuda pasa por la "
             "utilidad y por el FFO de Nareit —ganancia de 111.8 millones en 2021, pérdida de 98.0 "
             "millones en 2020—; el Core FFO de la empresa lo excluye.",
             "emisor", "10-K 2017 y 10-K 2021", SEC_PSA + "000139331122000010/psa-20211231.htm"),
        Hito(D(2017, 9, 18), "Primera emisión pública de bonos",
             "1,000 millones de dólares en dos tramos: 2.370% a 2022 y 3.094% a 2027. Hasta "
             "entonces se financiaba con flujo retenido y acciones preferentes, que le costaban "
             "más que la deuda pero no había que refinanciar. Su deuda senior tiene A de S&P y A2 "
             "de Moody's; sus preferentes ya tenían grado de inversión (Baa2 y BBB+) en 1996.",
             "emisor", "10-K 2017; 10-K 2013; 10-K 1996",
             SEC_PSA + "000139331118000004/psa-20171231x10k.htm"),
        Hito(D(2019, 1, 1), "Joe Russell, director general",
             "Presidente desde 2016 y antes director general de PS Business Parks; sucede a "
             "Havner, que sigue como presidente del consejo. Ese mismo día Tom Boyle se vuelve "
             "director de finanzas.",
             "emisor", "8-K del 21-feb-2018", SEC_PSA + "000119312518050794/d533849d8k.htm"),
        Hito(D(2020, 12, 31), "Covid: el dividendo no se mueve",
             "La demanda cae en el primer semestre, algunas localidades limitan aumentos de "
             "renta, cobros y desalojos, y la empresa recorta los aumentos a sus clientes; sus "
             "bodegas, clasificadas como negocio esencial, no cierran, y lanza la renta por "
             "internet («eRental»). Los ingresos de sus bodegas comparables bajan 0.8% en el año "
             "y suben 10.6% en 2021; el dividendo se queda en 2.00 dólares por trimestre.",
             "emisor", "10-K 2020 y 10-K 2021", SEC_PSA + "000156276221000058/psa-20201231x10k.htm",
             precision="anio"),
        Hito(D(2021, 4, 28), "ezStorage y All Storage",
             "Compra el portafolio de ezStorage —48 propiedades— por 1,800 millones de dólares y, "
             "en el cuarto trimestre, el de All Storage —56 propiedades— por 1,500 millones. De "
             "2021 a 2023 compra en total 470 bodegas por 8,500 millones.",
             "emisor", "10-K 2021; 10-K 2023", SEC_PSA + "000139331122000010/psa-20211231.htm"),
        Hito(D(2022, 7, 20), "Vende PS Business Parks",
             "Blackstone compra PS Business Parks a 187.50 dólares por acción. Public Storage "
             "cobra 2,700 millones por su 41%, con una ganancia de 2,100 millones, y el 4 de agosto "
             "reparte un dividendo especial de 13.15 dólares por acción (unos 2,300 millones).",
             "emisor", "10-K 2022", SEC_PSA + "000139331123000012/psa-20221231.htm"),
        Hito(D(2023, 2, 4), "Sube el dividendo 50%",
             "El trimestral pasa de 2.00 dólares, donde estaba desde fines de 2016, a 3.00 (12.00 "
             "al año). A mediados de 2026 sigue en 3.00.",
             "emisor", "10-K 2022; 10-K 2017; 10-Q 2T-2026",
             SEC_PSA + "000139331123000012/psa-20221231.htm"),
        Hito(D(2023, 9, 13), "Compra Simply Self Storage",
             "Paga a un fondo de Blackstone 2,200 millones de dólares en efectivo por 127 bodegas "
             "en 18 estados, financiados con 2,200 millones de bonos colocados en julio. Un mes "
             "antes adopta la estructura UPREIT: los inmuebles quedan en una sociedad operadora, "
             "Public Storage OP, con cuyas unidades pagará en 2026 buena parte de PS Canada.",
             "emisor", "10-K 2023; 8-K del 1-sep-2026", SEC_PSA + "000139331124000043/psa-20231231.htm"),
        Hito(D(2026, 4, 1), "Tom Boyle, director general",
             "Sucede a Joe Russell, que se retira; era director de finanzas desde 2019 y de "
             "inversiones desde 2023. La empresa presenta «PS4.0», un plan centrado en crecer la "
             "utilidad y el flujo por acción, muda su sede de Glendale, California, a Frisco, "
             "Texas, y nombra un presidente del consejo independiente; Havner sigue de consejero.",
             "emisor", "8-K del 12-feb-2026", SEC_PSA + "000119312526048660/d793613dex991.htm"),
        Hito(D(2026, 7, 22), "Compra National Storage Affiliates",
             "Fusión en acciones —0.14 de Public Storage por cada una de NSA— con valor empresa de "
             "unos 10,500 millones de dólares, casi el doble de lo que costó Shurgard. De más de "
             "mil propiedades se queda con 488 en directo y con 20% de una coinversión de otras "
             "313, que administra. El 1 de septiembre cierra además PS Canada: 68 bodegas por unos "
             "1,200 millones en unidades y efectivo, de la familia Hughes, que usaban la marca con "
             "licencia.",
             "emisor", "8-K del 16-mar-2026, del 22-jul-2026 y del 1-sep-2026; 10-Q 2T-2026",
             SEC_PSA + "000119312526312563/d137665d8k.htm"),
    ),
    eras=(
        Era("De Storage Equities a Public Storage", D(1993, 1, 1), D(1999, 12, 31),
            "Al empezar, Storage Equities es un REIT de mini-bodegas sin operación propia: la "
            "organización de B. Wayne Hughes la asesora y la opera a cambio de comisiones sobre "
            "sus ingresos. En noviembre de 1995 la absorbe, se queda con la marca, duplica su "
            "tamaño y cambia la clave a PSA. Siguen años de consolidación: absorbe REIT y "
            "sociedades afiliadas, pasa sus locales comerciales a PS Business Parks y en 1999 "
            "compra Storage Trust. Al final del periodo la euforia tecnológica le quita "
            "compradores a todos los REIT."),
        Era("Refugio, preferentes y relevo", D(1999, 12, 31), D(2006, 8, 22),
            "Revienta la burbuja tecnológica y el dinero busca flujo estable. Public Storage crece "
            "casi sin deuda: paga sus compras con flujo retenido y acciones preferentes, que le "
            "cuestan más que un crédito pero no vencen. Para cumplir la regla de reparto del "
            "régimen REIT paga especiales en 1999, 2000 y 2001, y en 2001 duplica el dividendo "
            "trimestral regular, de 0.22 a 0.45 dólares. En 2002 Ron Havner sucede a Hughes como "
            "director general. El periodo cierra con la compra de Shurgard."),
        Era("Shurgard, Europa y la crisis", D(2006, 8, 22), D(2009, 3, 6),
            "Shurgard le suma 487 bodegas en EE. UU. y la operación europea. En 2007 se "
            "reorganiza como fideicomiso de Maryland y en 2008 vende 51% de Shurgard Europe a un "
            "fondo de pensiones de Nueva York. Cuando se congela el crédito tiene poca deuda y la "
            "intención de amortizarla, no de refinanciarla: frena el desarrollo, recompra con "
            "descuento preferentes y bonos, sube el dividendo y paga una especial. Aun así la "
            "acción cae con todo lo inmobiliario."),
        Era("Tasas en el piso", D(2009, 3, 6), D(2013, 5, 17),
            "La Reserva Federal lleva las tasas a cero. Sin vencimientos que refinanciar, Public "
            "Storage compra participaciones de sus sociedades afiliadas —en 2011, las de la "
            "familia Hughes en cinco de ellas— y sube el dividendo trimestral de 0.55 a 1.25 "
            "dólares entre 2009 y 2013. En agosto de 2011 Hughes deja la presidencia del consejo "
            "y Havner la suma a la dirección general."),
        Era("Desarrollo, oferta nueva y primeros bonos", D(2013, 5, 17), D(2019, 12, 31),
            "El anuncio de que la Fed retirará estímulos sube las tasas largas. De 2013 a 2018 "
            "Public Storage compra 296 bodegas a terceros por unos 2,700 millones y abre espacio "
            "nuevo y ampliaciones por 1,200 millones; otros también construyen, y la oferta nueva "
            "presiona la ocupación y las rentas en varias ciudades. El dividendo trimestral llega "
            "a 2.00 dólares a fines de 2016 y ahí se queda seis años. Empieza a usar deuda —en "
            "euros desde 2015, bonos públicos en dólares desde 2017—, Shurgard sale a bolsa en "
            "2018 y en 2019 Joe Russell toma la dirección."),
        Era("Pandemia y compras", D(2019, 12, 31), D(2021, 12, 31),
            "La pandemia frena la demanda en el primer semestre de 2020 y algunas localidades "
            "limitan aumentos de renta y desalojos; la empresa recorta los aumentos a sus "
            "clientes, pero sus bodegas no cierran. Los ingresos comparables bajan en 2020 y "
            "repuntan con fuerza en 2021. Con bonos en euros a menos de 1%, compra ezStorage y "
            "All Storage por 3,300 millones; el dividendo no se mueve."),
        Era("Choque de tasas: sale PSB, entra Simply", D(2021, 12, 31), D(2023, 10, 27),
            "El bono a diez años pasa de 1.5% a casi 5%. Los ingresos comparables todavía suben "
            "en 2022 y 2023, por precio, mientras la ocupación baja. Public Storage vende su 41% "
            "de PS Business Parks y reparte un dividendo especial, sube el regular 50%, propone "
            "comprar Life Storage con acciones y en septiembre de 2023 compra Simply con deuda "
            "nueva. En agosto adopta la estructura UPREIT."),
        Era("Ciclo débil, PS4.0 y NSA", D(2023, 10, 27), None,
            "Con las tasas estables en niveles altos, los ingresos de sus bodegas comparables "
            "bajan en 2024 y quedan planos en 2025. Public Storage empieza a prestar a otros "
            "dueños, muda su sede a Texas y en abril de 2026 cambia de director general: Tom "
            "Boyle lanza «PS4.0», con la meta explícita de crecer la utilidad y el flujo por "
            "acción. En 2026 compra National Storage Affiliates con acciones y PS Canada con "
            "unidades y efectivo. La dirección dice que la industria sale del fondo del ciclo; el "
            "resultado depende de integrar NSA."),
    ),
    riesgos=(
        Riesgo("El ciclo de demanda y la oferta nueva",
               "Sin contratos largos, el ingreso se mueve con la economía: los ingresos de sus "
               "bodegas comparables subieron 14.8% en 2022, bajaron 0.7% en 2024 y la guía de 2026 "
               "va de −0.7% a +0.3%. La demanda depende del empleo, del ingreso de los hogares y "
               "de las mudanzas, y cuando otros construyen cerca bajan la ocupación y las rentas: "
               "en 2018 la empresa reportó ese efecto en Atlanta, Austin, Charlotte, Chicago, "
               "Dallas, Denver, Houston, Nueva York y Portland."),
        Riesgo("Integrar NSA con un equipo nuevo",
               "NSA cuesta casi el doble que Shurgard y llega en plena transición: director "
               "general desde abril de 2026, director de finanzas que viene de fuera, el de "
               "operaciones se fue en julio y la sede se mudó a Texas. La empresa espera de 110 a "
               "130 millones de sinergias en tres o cuatro años llevando esas bodegas a sus "
               "márgenes; 313 de ellas quedan en una coinversión con cerca de 70% de deuda, de la "
               "que tiene 20%."),
        Riesgo("Límites a las rentas en California",
               "Los Ángeles y San Francisco generaron 21% de los ingresos de sus bodegas "
               "comparables en 2025 (Los Ángeles sola, casi 15%). Tras los incendios de 2018, 2019 "
               "y principios de 2025 y las inundaciones de 2023, California y algunas localidades "
               "limitaron temporalmente sus rentas y los aumentos a clientes existentes; también "
               "regulan sus métodos de precios, comisiones y promociones."),
        Riesgo("Más deuda, y más cara",
               "Durante décadas usó poca deuda —839 millones a fines de 2013—; al 30 de junio de "
               "2026 debía 10,300 millones, además de 4,350 millones en preferentes. Su "
               "apalancamiento sigue bajo (2.9 veces deuda neta ÷ EBITDA; 4.2 veces con las "
               "preferentes) y tiene calificación A2 y A, pero refinancia más caro: sus bonos en "
               "euros de 2020 y 2021 pagan 0.875% y 0.500%; los de dólares de 2026 salieron a "
               "5.00% y, en promedio, a 4.855%."),
        Riesgo("Europa, Canadá y la deuda en euros",
               "Tiene 35% de Shurgard —acciones con valor de mercado de unos 1,050 millones de "
               "dólares en junio de 2026— y desde septiembre de 2026 bodegas propias en Canadá. La "
               "deuda en euros cubre parte de la inversión europea, pero su efecto cambiario pasa "
               "por la utilidad y el FFO de Nareit (+111.8 millones en 2021, −98.0 millones en "
               "2020); el Core FFO de la empresa lo excluye."),
        Riesgo("Divisa, para quien invierte en pesos",
               "El dividendo y casi todo el negocio están en dólares. El retorno en pesos suma la "
               "variación del tipo de cambio: desde 1993 la depreciación del peso —sobre todo la "
               "de 1994-95— infló el retorno en pesos, y una apreciación del peso resta en la "
               "misma medida."),
    ),
    fuentes_extra=(
        ("Precio y dividendos desde 1993", "Yahoo Finance (chart API)."),
        ("Core FFO, FFO y la operación 1993-2025", "10-K, prospectos 424B y comunicados de "
         "resultados (8-K Ex-99.1) de la SEC, uno por uno; ver "
         "data/estudios/PSA/anuales_primarios.csv."),
        ("Estados financieros 2008-2026", "XBRL de la SEC (companyfacts) y 8-K trimestrales."),
        ("Tasas", "Treasury a 10 años (FRED), Udibono, CETES y tipo de cambio FIX (Banxico)."),
        ("Historia corporativa", "10-K, 8-K, 8-K12G3, prospectos 424B5 y proxies de la SEC: CIK "
         "318380 (Storage Equities / Public Storage, Inc., hasta 2007) y CIK 1393311 (Public "
         "Storage, desde 2007)."),
    ),
    notas={
        "apalancamiento": (
            "Public Storage se financió sobre todo con flujo retenido y acciones preferentes, que "
            "no cuentan como deuda: a fines de 2013 debía 839 millones y su primera emisión "
            "pública de bonos fue en 2017. Por eso la deuda neta ÷ EBITDAre sale baja; al 30 de "
            "junio de 2026 tenía 4,350 millones en preferentes, y el emisor reporta 2.9x de deuda "
            "neta ÷ EBITDA y 4.2x sumando las preferentes."
        ),
        "mxn": "El tipo de cambio de la base empieza en noviembre de 1993; incluye la devaluación "
               "de 1994-95.",
    },
)
