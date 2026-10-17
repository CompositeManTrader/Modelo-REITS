"""Narrativa verificada de Essential Properties Realty Trust (EPRT, CIK 0001728951).

Cada hecho sale de un documento de EDGAR que se puede abrir: el prospecto de la
salida a bolsa (424B4 de 2018), los 10-K, los 8-K y sus anexos (comunicados de
resultados, suplementos y presentaciones a inversionistas). Lo que no se encontró
en un documento no entró: por ejemplo, la fecha y el nivel exactos de las
calificaciones iniciales de Moody's y S&P en 2021 —el comunicado del 2T-2021 solo
dice que se obtuvieron «recientemente»— y la letra de cada agencia en 2026.
"""

from __future__ import annotations

from src.estudio.historia import D, Era, HistoriaEmisor, Hito, Riesgo

SEC_EPRT = "https://www.sec.gov/Archives/edgar/data/1728951/"

HISTORIA_EPRT = HistoriaEmisor(
    ticker="EPRT",
    nombre="Essential Properties Realty Trust, Inc.",
    perfil=(
        "Dueño de inmuebles comerciales pequeños de un solo inquilino en EE. UU. —lavados de "
        "autos, consultorios médicos y dentales, escuelas de educación inicial, restaurantes, "
        "talleres, tiendas de conveniencia, entretenimiento y gimnasios— que renta con contratos "
        "largos triple net a empresas medianas, por lo general sin calificación de las agencias. "
        "Al 30 de junio de 2026 tenía 2,493 propiedades en 48 estados (152 de ellas garantizan "
        "préstamos que la empresa otorgó a operadores), con una renta anualizada de 604.9 millones "
        "de dólares, 99.6% de ocupación, un plazo remanente promedio de 14.3 años y una cobertura "
        "de renta de 3.5 veces. 91.6% de la renta viene de negocios de servicio o de experiencia; "
        "ningún inquilino pesa más de 3.1% y los diez mayores suman 15.2%. Paga dividendo cada "
        "trimestre —0.32 dólares desde mayo de 2026, 1.28 anualizado— y lo ha subido cada año "
        "desde 2019. Cotiza en la Bolsa de Nueva York desde junio de 2018 y nunca ha cambiado de "
        "nombre: antes de la salida a bolsa el negocio era Essential Properties Realty Trust LLC, "
        "hoy su sociedad operadora, Essential Properties, L.P. No ha hecho fusiones, escisiones ni "
        "splits, y tiene el mismo director general desde que nació. Su sede está en Princeton, "
        "Nueva Jersey, con 56 empleados al cierre de 2025."
    ),
    modelo_de_negocio=(
        "El negocio es el diferencial de cualquier REIT de arrendamiento neto: comprar inmuebles a "
        "un yield mayor que lo que le cuesta el dinero para comprarlos. Lo distintivo de EPRT es el "
        "tamaño de lo que compra y a quién. Compra locales chicos —3.1 millones de dólares en "
        "promedio— directamente a los operadores que los usan y se los renta de regreso "
        "(sale-leaseback: el operador vende su inmueble para liberar capital y se queda como "
        "inquilino), con contratos triple net de 15 años o más en los que el inquilino paga el "
        "predial, el seguro y el mantenimiento. En 2025, 95% de sus compras fueron sale-leasebacks "
        "originados por su propio equipo. Sus clientes son empresas medianas —de 10 a 250 locales y "
        "de 20 a 1,000 millones de dólares de ventas—, a las que los bancos atienden cada vez menos "
        "con financiamiento de largo plazo; a cambio de ese riesgo cobra un cap rate (la renta en "
        "efectivo del primer año entre el precio pagado) de 7.7% a 8% en 2024-2026. Se protege de "
        "tres formas. Elige giros donde el cliente tiene que ir en persona y que el comercio "
        "electrónico no sustituye. Exige el estado de resultados de cada local, para medir la "
        "cobertura: cuántas veces la utilidad del local alcanza para pagar la renta. Y agrupa varios "
        "locales de un mismo inquilino en un solo contrato maestro (master lease), «todo o nada»: el "
        "inquilino no puede quedarse con los locales buenos y devolver los malos. Una parte menor la "
        "invierte en préstamos garantizados con los inmuebles del operador en vez de comprarlos. "
        "Crece emitiendo acciones —casi siempre con ventas a plazo, que fijan hoy el precio y "
        "entregan las acciones cuando hace falta el dinero— y bonos sin garantía con grado de "
        "inversión. No opera los negocios: solo los renta."
    ),
    hitos=(
        Hito(D(2016, 3, 30), "Nace con el capital de Eldridge",
             "Filiales de Eldridge Industries, la firma de inversión controlada por Todd Boehly, "
             "forman la empresa y le ponen el capital y la deuda de arranque. La dirige desde "
             "entonces Pete Mavoides, que de 2011 a 2015 fue presidente y director de operaciones de "
             "otro REIT de arrendamiento neto listado en Nueva York.",
             "emisor", "Prospecto de la salida a bolsa (424B4 del 22-jun-2018); 10-K 2018",
             SEC_EPRT + "000119312518201079/d614524d424b4.htm"),
        Hito(D(2016, 6, 16), "Primer portafolio: 262 inmuebles de GE Capital",
             "Compra 262 propiedades, casi todas restaurantes de comida rápida, familiares y "
             "casuales, que se vendían en la liquidación de General Electric Capital, por 279.8 "
             "millones de dólares con costos. Desde ahí crece con compras chicas: al salir a bolsa "
             "invertía en promedio 1.9 millones por propiedad.",
             "emisor", "Prospecto de la salida a bolsa (424B4 del 22-jun-2018)",
             SEC_EPRT + "000119312518201079/d614524d424b4.htm"),
        Hito(D(2018, 6, 21), "Cotiza en la Bolsa de Nueva York",
             "Coloca 32.5 millones de acciones a 14.00 dólares (455 millones) con la clave EPRT y "
             "empieza a operar el 21 de junio. Eldridge invierte 125 millones más al mismo precio y "
             "queda con 19% de las acciones, más unidades de la sociedad operadora. Lleva 530 "
             "propiedades rentadas a 127 inquilinos en 42 estados, 99.1% ocupadas.",
             "emisor", "Prospecto 424B4 del 22-jun-2018; 8-K del 26-jun-2018; 10-K 2018",
             SEC_EPRT + "000156459019005137/eprt-10k_20181231.htm"),
        Hito(D(2018, 9, 5), "Primer dividendo",
             "0.224 dólares: los 0.21 del tercer trimestre más 0.014 por los seis días de junio "
             "posteriores a la salida a bolsa. Los 0.21 trimestrales (0.84 al año) equivalían a 6% "
             "del precio de colocación.",
             "emisor", "8-K del 5-sep-2018; prospecto 424B4 del 22-jun-2018",
             SEC_EPRT + "000156459018022675/eprt-ex991_6.htm"),
        Hito(D(2019, 3, 13), "Primera colocación de acciones",
             "14.03 millones de acciones a 17.50 dólares, unos 246 millones con la opción de los "
             "colocadores. Es el motor que usará en adelante: emitir acciones para comprar más "
             "inmuebles.",
             "emisor", "424B4 del 15-mar-2019; 8-K del 18-mar-2019",
             SEC_EPRT + "000119312519076660/d708598d424b4.htm"),
        Hito(D(2019, 5, 14), "Empieza a dejar la deuda garantizada",
             "Con un préstamo a cinco años sin garantía por 200 millones recompra, con 0.7% de prima, "
             "200 millones de sus bonos respaldados por inmuebles que tenía una filial de Eldridge. "
             "La deuda garantizada baja de 100% a 61% del total y la tasa promedio, de 4.35% a 3.89%.",
             "emisor", "8-K del 20-may-2019", SEC_EPRT + "000156459019019769/eprt-8k_20190514.htm"),
        Hito(D(2019, 7, 22), "Eldridge vende toda su participación",
             "Sus filiales colocan 26.3 millones de acciones a 19.75 dólares (unos 519 millones); la "
             "empresa no recibe nada. Termina el convenio que le daba a Eldridge derecho a proponer "
             "consejeros, y sus dos consejeros renuncian en septiembre. Ese año la acción entra al "
             "S&P SmallCap 600.",
             "emisor", "8-K del 23-jul-2019; 424B4 del 19-jul-2019; 8-K del 3-sep-2019; "
             "presentación del 12-nov-2019",
             SEC_EPRT + "000119312519199558/d778552d8k.htm"),
        Hito(D(2019, 11, 6), "Primer grado de inversión, de Fitch",
             "En su comunicado del 3T-2019 anuncia que Fitch le asignó BBB-, el primer escalón del "
             "grado de inversión. En noviembre contrata un préstamo a siete años de 430 millones, "
             "también sin garantía.",
             "emisor", "Comunicado del 3T-2019; comunicado del 4T-2019",
             SEC_EPRT + "000156459019041098/eprt-ex991_7.htm"),
        Hito(D(2020, 5, 11), "Covid: cobra 61% de la renta de abril",
             "A mediados de abril había cobrado 53% de la renta del mes, contra cerca de 90% a la "
             "misma fecha en los meses previos; gimnasios y entretenimiento estaban cerrados por "
             "completo. Difiere rentas, retira su guía de 2020 y el AFFO por acción del año baja 3%, a "
             "1.11 dólares. No recorta: el dividendo se queda en 0.23 todo 2020 y en diciembre sube "
             "a 0.24.",
             "emisor", "Presentación del 15-abr-2020; comunicados del 1T-2020 y 4T-2020; 8-K del "
             "4-dic-2020",
             SEC_EPRT + "000156459020023796/eprt-ex991_6.htm"),
        Hito(D(2021, 6, 28), "Grado de inversión de Moody's y S&P; primer bono",
             "Con calificaciones de grado de inversión recién obtenidas de Moody's y S&P coloca su "
             "primer bono público sin garantía: 400 millones al 2.950% con vencimiento en 2031. Ese "
             "mes paga los 171.2 millones que quedaban de sus notas respaldadas por inmuebles; al "
             "cierre de 2021 ya no tiene deuda garantizada.",
             "emisor", "8-K del 28-jun-2021; comunicado del 2T-2021; 10-K 2021",
             SEC_EPRT + "000119312521202104/d128306d8k.htm"),
        Hito(D(2022, 6, 25), "Se retira Gregg Seibert",
             "Cofundador y director de operaciones; había trabajado con Mavoides en el otro REIT. Se "
             "retira al vencer su contrato; la empresa prevé contratarlo como consultor.",
             "emisor", "8-K del 28-abr-2022; prospecto 424B4 del 22-jun-2018",
             SEC_EPRT + "000172895122000053/eprt-20220426.htm"),
        Hito(D(2024, 12, 31), "Compra a 8%",
             "Invierte 1,200 millones en 297 propiedades a un cap rate en efectivo de 8.0%, el más "
             "alto de un año completo desde que cotiza; en 2021 había comprado a 7.0%.",
             "emisor", "Comunicados del 4T de 2018 a 2025",
             SEC_EPRT + "000172895125000029/earningsreleaseex991-worki.htm", precision="anio"),
        Hito(D(2025, 8, 21), "Segundo bono, a 5.40%",
             "400 millones al 5.400% con vencimiento en 2035, contra 2.950% del primero. En junio de "
             "2026 coloca otros 400 millones al 5.375% a 2036.",
             "emisor", "8-K del 21-ago-2025; 8-K del 15-jun-2026",
             SEC_EPRT + "000172895125000156/eprt-20250818.htm"),
        Hito(D(2025, 12, 31), "Año récord y un inquilino nuevo en la cima",
             "Invierte 1,300 millones a 7.9% y el AFFO por acción sube 9%, a 1.89 dólares. Su mayor "
             "inquilino es EquipmentShare, de renta de maquinaria, con 3.4% de la renta; al salir a "
             "bolsa era la cadena de restaurantes Captain D's, con 6.8%.",
             "emisor", "Comunicado del 4T-2025; 10-K 2025; prospecto 424B4 del 22-jun-2018",
             SEC_EPRT + "000172895126000008/eprt-20251231.htm", precision="anio"),
        Hito(D(2026, 4, 22), "Ninguna calificación en el piso",
             "Su presentación del 1T-2026 muestra calificaciones BBB/BBB/Baa2; la de dos semanas "
             "antes mostraba BBB/BBB-. Ya ninguna está en el escalón más bajo del grado de inversión.",
             "emisor", "Presentaciones del 7-abr-2026 y del 22-abr-2026 (8-K)",
             SEC_EPRT + "000172895126000028/suppipq12026.htm", precision="mes"),
        Hito(D(2026, 5, 29), "Dividendo de 0.32",
             "Sube 3%, a 0.32 dólares por trimestre (1.28 anualizado): 52% más que los 0.21 de "
             "2018. Lo ha subido cada año desde 2019 y nunca lo ha recortado.",
             "emisor", "8-K del 1-jun-2026 y dividendos declarados de 2018 a 2026 (8-K)",
             SEC_EPRT + "000172895126000041/ex991-dividendq22026.htm"),
        Hito(D(2026, 9, 4), "Mavoides firma por cuatro años más",
             "El único director general que ha tenido la empresa firma un contrato nuevo de unos "
             "cuatro años. Max Jenkins, director de operaciones, suma la presidencia; Rob Salisbury, "
             "director de finanzas desde enero, suma la estrategia, y sale el director de inversiones.",
             "emisor", "8-K del 9-sep-2026; 8-K del 17-dic-2025",
             SEC_EPRT + "000172895126000057/ex991-september2026.htm"),
    ),
    eras=(
        Era("Eldridge y la salida a bolsa", D(2018, 6, 21), D(2019, 12, 31),
            "Una empresa de dos años sale a bolsa con un patrocinador dueño de más de un tercio del "
            "negocio y con su deuda de largo plazo garantizada con inmuebles. En 2019 se independiza: "
            "coloca acciones por primera vez, Eldridge vende todo y deja el consejo, los bonos "
            "garantizados se cambian por préstamos bancarios sin garantía y Fitch le da grado de "
            "inversión. Compra a cap rates de 7.4% a 7.6%, sobre todo sale-leasebacks originados por "
            "su propio equipo."),
        Era("Pandemia y grado de inversión", D(2019, 12, 31), D(2021, 12, 31),
            "El cierre de la economía golpea justo sus giros: en abril de 2020 gimnasios y "
            "entretenimiento están cerrados y a mitad de mes cobra apenas la mitad de la renta. "
            "Difiere rentas, retira su guía y congela el dividendo sin recortarlo; para enero de 2021 "
            "espera cobrar 95% y en el segundo trimestre cobra 99%. Con el negocio normalizado obtiene grado de "
            "inversión de Moody's y S&P, coloca su primer bono, liquida su última deuda garantizada y "
            "en 2021 invierte un récord de 974 millones."),
        Era("Choque de tasas", D(2021, 12, 31), D(2023, 10, 27),
            "El bono a diez años pasa de 1.5% a casi 5% en menos de dos años. EPRT sigue comprando "
            "—937 millones en 2022 y unos 1,000 millones en 2023— y sube el yield que exige: de 7.0% "
            "en 2021 a 7.6% en 2023. El dividendo sigue subiendo cada año. Se retira Gregg Seibert, "
            "cofundador y director de operaciones."),
        Era("Tasas altas, compras a 8%", D(2023, 10, 27), None,
            "Con las tasas estables en niveles altos compra al mejor cap rate desde que cotiza "
            "—8.0% en 2024 y 7.9% en 2025— e invierte más que nunca. Su deuda nueva cuesta más, "
            "bonos a diez años a 5.4% contra 2.95% en 2021, pero sus calificaciones suben. Entre 2021 "
            "y 2025 la cartera se mueve hacia lavados de autos, entretenimiento e inmuebles "
            "industriales, y la comida rápida pierde peso. En 2026 empieza el relevo del equipo "
            "alrededor del fundador, que firma por cuatro años más."),
    ),
    riesgos=(
        Riesgo("El crédito de los inquilinos",
               "Le renta sobre todo a empresas medianas sin calificación de las agencias, evaluadas "
               "con su propio análisis. Es la fuente de su mejor yield y también un riesgo real: a "
               "mediados de abril de 2020 había cobrado apenas 53% de la renta del mes. La cobertura "
               "alta (3.5 veces), los contratos maestros y los reportes por local amortiguan, pero no "
               "eliminan, el golpe de una recesión larga."),
        Riesgo("Giros que dependen de que el cliente vaya",
               "Lavados de autos (13.7% de la renta), consultorios médicos y dentales (12.5%), "
               "educación inicial (11.3%), entretenimiento (9.3%) y comida rápida (8.7%) dependen de "
               "que la gente acuda en persona y gaste parte de su ingreso discrecional, como advierte "
               "el propio 10-K. En 2020 gimnasios y entretenimiento cerraron por completo. Tres de "
               "sus diez mayores inquilinos son cadenas de lavado de autos."),
        Riesgo("Las tasas",
               "Con contratos de 14 años en promedio y aumentos fijos de 1.8% a 1.9% al año, la acción "
               "se comporta como un bono largo: cuando el Treasury sube, su precio baja aunque el "
               "negocio no cambie. Su deuda nueva ya cuesta 5.4% a diez años, contra 2.95% del bono de "
               "2021. Y si la inflación supera los aumentos fijos, la renta real se erosiona: el 10-K "
               "de 2025 reconoce que ha pasado recientemente."),
        Riesgo("El motor de crecimiento depende del precio de la acción",
               "Su guía de 2026 es invertir de 1,200 a 1,500 millones, en buena parte con acciones "
               "nuevas: en la primera mitad del año vendió 455.8 millones en acciones a plazo. Si su "
               "acción se abarata frente al cap rate de 7.7% a 8% que obtiene, crecer por acción se "
               "vuelve difícil. Y el director general reconoce que la competencia por estos inmuebles "
               "aumentó al normalizarse los mercados."),
        Riesgo("Una historia corta y un relevo en marcha",
               "Empezó a invertir en 2016: no existía en la crisis de 2008-2009 y su única prueba de "
               "estrés es la pandemia, cuando muchos de sus inquilinos podían recibir los créditos "
               "federales del programa PPP. El fundador la dirige desde el inicio, pero el equipo "
               "cambia: nuevo director de finanzas en enero de 2026, presidente nuevo y salida del "
               "director de inversiones en septiembre."),
        Riesgo("Divisa, para quien invierte en pesos",
               "Todos los inmuebles y el dividendo están en dólares. El retorno en pesos suma la "
               "variación del tipo de cambio: una apreciación del peso resta en la misma medida. Con "
               "una historia que empieza en 2018, la ventana es corta y el tipo de cambio de los "
               "extremos pesa mucho."),
    ),
    fuentes_extra=(
        ("Precio y dividendos desde 2018", "Yahoo Finance (chart API)."),
        ("FFO, AFFO y la operación 2018-2025", "Prospecto de la salida a bolsa (424B4), 10-K y "
         "comunicados de resultados (8-K Ex-99.1 y suplementos Ex-99.2) de la SEC, uno por uno; ver "
         "data/estudios/EPRT/anuales_primarios.csv."),
        ("Estados financieros 2018-2026", "XBRL de la SEC (companyfacts) y 8-K trimestrales."),
        ("Tasas", "Treasury a 10 años (FRED), Udibono, CETES y tipo de cambio FIX (Banxico)."),
        ("Historia corporativa", "Prospectos 424B4 de 2018 y 2019, 8-K, 10-K, 10-Q, Schedule 13D y "
         "presentaciones a inversionistas (8-K Ex-99.1 y Ex-99.2) de la SEC."),
    ),
    notas={
        "dividendos": (
            "El primer pago, 0.224 dólares declarado el 5 de septiembre de 2018, suma el trimestral "
            "de 0.21 y 0.014 por los seis días de junio posteriores a la salida a bolsa: que después "
            "se pague 0.21 no es un recorte."
        ),
        "apalancamiento": (
            "El emisor publica deuda neta ÷ EBITDAre ajustado anualizado del trimestre, real y pro "
            "forma con las acciones vendidas a plazo aún sin liquidar como si ya se hubieran cobrado: "
            "al 30 de junio de 2026, 4.5x y 3.5x. Su meta es que la pro forma quede, con el tiempo, "
            "debajo de 5.5x."
        ),
    },
)
