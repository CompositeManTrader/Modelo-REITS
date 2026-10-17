"""Narrativa verificada de Global Net Lease, Inc. (GNL, CIK 1526113).

Cada hecho sale de un documento de EDGAR que se puede abrir: 10-K, 10-Q, 8-K,
prospectos, proxies y comunicados de resultados. Lo que no se encontró en una
fuente no entró. GNL se constituyó en 2011, así que no vivió la crisis de 2008-2009.
"""

from src.estudio.historia import D, Era, HistoriaEmisor, Hito, Riesgo

SEC_GNL = "https://www.sec.gov/Archives/edgar/data/1526113/"

HISTORIA_GNL = HistoriaEmisor(
    ticker="GNL",
    nombre="Global Net Lease, Inc.",
    perfil=(
        "Dueño de inmuebles de un solo inquilino —bodegas y centros de distribución, oficinas y "
        "locales comerciales— en EE. UU., Canadá y Europa, rentados con contratos de arrendamiento "
        "neto. Al 30 de junio de 2026 tenía 798 propiedades con unos 40 millones de pies cuadrados "
        "en diez países y territorios, 97% rentadas y con un plazo remanente promedio de 5.7 años. "
        "74% de la renta viene de EE. UU. y Canadá y 26% de Europa, sobre todo del Reino Unido; por "
        "tipo, 47% es industrial y distribución, 28% comercio y 25% oficinas. En agosto de 2026 "
        "compró Modiv Industrial, una cartera industrial de unos 535 millones de dólares. Paga 0.19 "
        "dólares por acción cada trimestre desde abril de 2025. Nació en 2011 como American Realty "
        "Capital Global Daily Net Asset Value Trust, se llamó American Realty Capital Global Trust "
        "de 2012 a 2015 y cotiza como Global Net Lease desde junio de 2015."
    ),
    modelo_de_negocio=(
        "Compra inmuebles que una empresa necesita para operar —un centro de distribución, unas "
        "oficinas corporativas, una tienda— y se los renta por muchos años, a menudo a la misma "
        "empresa que se los vendió (sale-leaseback: la empresa vende el inmueble y se queda como "
        "inquilina). Los contratos son de arrendamiento neto: el inquilino paga impuestos, seguro "
        "y mantenimiento, y GNL cobra una renta que sube en promedio 1.4% al año; una quinta parte "
        "de la cartera se ajusta con la inflación. Gana el diferencial entre el cap rate —la renta "
        "del primer año entre el precio— y lo que le cuesta el dinero. Lo distintivo es la mezcla: "
        "tres tipos de inmueble en dos continentes, con 63% de la renta de inquilinos que la "
        "empresa considera de grado de inversión (38% con calificación real y 25% «implícita», "
        "estimada con una herramienta de Moody's). Su historia pesa tanto como su modelo: nació "
        "como REIT no cotizado, vendido a ahorradores por medio de corredores a 10 dólares por "
        "acción, y durante doce años lo administró un asesor externo del grupo AR Global, cuyas "
        "comisiones crecían en buena parte con los activos y con cada emisión de acciones. En 2023 "
        "absorbió a ese asesor y desde entonces su negocio ha sido vender inmuebles para bajar "
        "deuda y, desde 2026, volver a comprar industria."
    ),
    hitos=(
        Hito(D(2011, 7, 13), "Nace como REIT no cotizado",
             "Se constituye en Maryland como American Realty Capital Global Daily Net Asset Value "
             "Trust, patrocinado por AR Capital, que controlan Nicholas S. Schorsch (63.6%) y William "
             "M. Kahane (13.5%). En abril de 2012 empieza a vender acciones a 10 dólares entre "
             "ahorradores, sin cotizar en bolsa; en agosto ya se llama American Realty Capital Global "
             "Trust y en octubre compra su primer inmueble: un McDonald's en Carlisle, Inglaterra, "
             "por 2.6 millones.",
             "emisor", "Prospecto (POS AM) de ago-2012; 10-Q 3T-2012; 10-K 2014",
             SEC_GNL + "000114420412046030/v321292_posam.htm"),
        Hito(D(2014, 6, 30), "Cierra la oferta",
             "Recauda 1,800 millones de dólares brutos, incluida la reinversión de dividendos. Al "
             "cierre de 2014 tiene 307 propiedades rentadas al 100% con un plazo remanente de 11.6 "
             "años: 255 en EE. UU. y Puerto Rico, 40 en el Reino Unido y 12 en Europa continental.",
             "emisor", "10-K 2014", SEC_GNL + "000152611315000002/arcg1231201410-k.htm"),
        Hito(D(2014, 10, 22), "Scott J. Bowman, director general",
             "Sucede a Schorsch, que dirigía la empresa desde su formación y pasa a presidente "
             "ejecutivo del consejo. Bowman venía de la administración de marcas de moda y comercio.",
             "emisor", "8-K del 24-oct-2014", SEC_GNL + "000114420414062866/v392056_8k.htm"),
        Hito(D(2015, 6, 2), "Cotiza en la Bolsa de Nueva York",
             "Un mes después de cambiar su nombre a Global Net Lease empieza a cotizar con la clave "
             "GNL y recompra 11.9 millones de acciones a 10.50 dólares (125 millones). El mismo día "
             "firma con su asesor externo un contrato de 20 años: 18 millones al año de comisión "
             "base, más 1.25% de cada emisión de capital y un incentivo sobre el Core AFFO por acción.",
             "emisor", "8-K del 2-jun-2015; 8-K del 7-may-2015; 10-K 2015",
             SEC_GNL + "000114420415034986/v412281_8k.htm"),
        Hito(D(2016, 12, 22), "Absorbe a Global II",
             "Fusión con American Realty Capital Global Trust II, un REIT no cotizado del mismo "
             "patrocinador: 2.27 acciones de GNL por cada una, 28.7 millones de acciones y 15 "
             "propiedades, 13 de ellas en Europa. Ese año también vende 34 inmuebles para bajar deuda.",
             "emisor", "10-K 2016", SEC_GNL + "000152611317000005/gnl1231201610-k.htm"),
        Hito(D(2017, 2, 28), "Contrasplit 1 por 3",
             "Cada tres acciones se convierten en una: de 198.8 a 66.3 millones de acciones. El "
             "dividendo mensual pasa de 0.059 a 0.1775 dólares por acción, el mismo pago. En este "
             "estudio todo lo anterior va expresado en acciones de hoy.",
             "emisor", "10-K 2016 y 2017", SEC_GNL + "000152611318000004/gnl1231201710-k.htm"),
        Hito(D(2017, 8, 15), "James L. Nelson, director general",
             "Consejero independiente desde marzo de 2017, sustituye a Bowman, que renuncia sin "
             "desacuerdos. Dirige la empresa —y a su asesor— hasta 2024.",
             "emisor", "8-K del 12-jul-2017", SEC_GNL + "000114420417036587/v470725_8k.htm",
             precision="mes"),
        Hito(D(2019, 4, 5), "El dividendo pasa a ser trimestral",
             "Hasta marzo de 2019 pagaba cada mes 0.1775 dólares; desde entonces paga 0.5325 cada "
             "trimestre. Cambia la frecuencia, no el monto: 2.13 dólares al año.",
             "emisor", "10-K 2019", SEC_GNL + "000152611320000006/gnl1231201910-k.htm"),
        Hito(D(2020, 3, 27), "Covid: recorta el dividendo una cuarta parte",
             "El consejo baja el dividendo anual de 2.13 a 1.60 dólares (−24.9%) por «prudencia» "
             "ante el entorno económico. En abril cobra 98% de la renta: 100% en el Reino Unido, 99% "
             "en el resto de Europa y 96% en EE. UU.",
             "emisor", "8-K del 30-mar-2020; comunicado del 1T-2020",
             SEC_GNL + "000110465920039775/tm2014048d1_8k.htm"),
        Hito(D(2020, 12, 16), "Primeros bonos sin garantía",
             "Coloca 500 millones de dólares al 3.75% con vencimiento en 2027. S&P les da grado de "
             "inversión (BBB-), pero la calificación de la empresa queda un escalón abajo, en BB+, "
             "con S&P y con Fitch.",
             "emisor", "8-K del 17-dic-2020", SEC_GNL + "000110465920136515/tm2038643d1_ex99-1.htm"),
        Hito(D(2022, 10, 24), "Activismo de Blackwells",
             "El fondo Blackwells Capital anuncia que propondrá dos consejeros y seis medidas de "
             "gobierno corporativo, y acusa a la empresa de pagarle a su asesor comisiones fuera de "
             "mercado. Tras demandas cruzadas, en junio de 2023 firman la paz: Blackwells retira todo, "
             "se compromete a no hacer activismo hasta 2033 y recibe 2.1 millones de acciones y la "
             "mitad de sus gastos; a GNL le cuesta 29.7 millones.",
             "emisor", "Proxy preliminar de Blackwells (1-dic-2022); 10-K 2022 y 2023; 8-K del 5-jun-2023",
             SEC_GNL + "000121390022076938/prec14a1122_blackwellscap.htm"),
        Hito(D(2023, 9, 12), "Fusión con Necessity Retail y fin del asesor externo",
             "Absorbe a The Necessity Retail REIT, otro REIT del grupo AR Global con 989 propiedades, "
             "casi todas comerciales, a 0.670 acciones de GNL por acción; el mismo día compra a sus "
             "asesores por 29.6 millones de acciones (valuadas en 325 millones) y 50 millones en "
             "efectivo. Queda con 1,306 propiedades, administración interna, un consejo que se elige "
             "cada año y sin píldora venenosa; Edward M. Weil Jr. se suma a Nelson como codirector "
             "general. En octubre el dividendo anual baja de 1.60 a 1.42 dólares.",
             "emisor", "8-K del 12-sep-2023; comunicado del 23-may-2023; 10-K 2023",
             SEC_GNL + "000110465923100026/tm2325830d1_8k.htm"),
        Hito(D(2024, 2, 26), "Recorte para bajar deuda",
             "El dividendo anual baja de 1.42 a 1.10 dólares (0.275 por trimestre) desde abril, para "
             "usar el efectivo en reducir deuda. La meta del año es vender entre 400 y 600 millones en "
             "inmuebles; vende 835 millones.",
             "emisor", "10-K 2023; comunicados del 4T-2023 y del 4T-2024",
             SEC_GNL + "000152611324000007/gnl-20231231.htm"),
        Hito(D(2024, 3, 31), "Edward M. Weil Jr., director general único",
             "Nelson se retira y Weil, codirector desde la fusión, queda solo al frente; en abril "
             "también es nombrado presidente. Weil fue director general de AR Global de 2016 a 2023.",
             "emisor", "8-K del 4-mar-2024 y del 12-abr-2024; proxy de 2026",
             SEC_GNL + "000110465924046766/tm2411751d1_8k.htm"),
        Hito(D(2025, 2, 26), "Vende los centros comerciales",
             "Acuerda vender a RCG Ventures su cartera de comercio con varios inquilinos —100 "
             "propiedades que llegaron con la fusión— por unos 1,800 millones de dólares, a un cap "
             "rate de 8.4%. Se cierra en tres partes entre marzo y el 18 de junio de 2025 (99 "
             "propiedades). El mismo día aprueba recomprar hasta 300 millones en acciones.",
             "emisor", "Comunicados del 26-feb-2025 y del 23-jun-2025; 10-K 2025",
             SEC_GNL + "000110465925017138/tm257525d1_ex99-1.htm"),
        Hito(D(2025, 2, 27), "Tercer recorte en año y medio",
             "El dividendo trimestral baja de 0.275 a 0.19 dólares (0.76 al año) desde abril de 2025; "
             "la empresa calcula que libera 78 millones de efectivo al año. Desde 2019, cuando pagaba "
             "2.13 dólares al año, el dividendo ha bajado 64%.",
             "emisor", "Comunicado del 4T-2024; 10-K 2025",
             SEC_GNL + "000152611325000005/ex991-gnlearningsrelease12.htm"),
        Hito(D(2025, 10, 17), "Grado de inversión",
             "Fitch sube la calificación de la empresa de BB+ a BBB-, el primer escalón del grado de "
             "inversión; en junio S&P había subido la de sus bonos a BBB-. La empresa lo atribuye a "
             "las ventas de cerca de 3,000 millones de 2024-2025, que bajaron la deuda.",
             "emisor", "Comunicados del 30-jun-2025 y del 17-oct-2025",
             SEC_GNL + "000110465925100198/tm2528909d1_ex99-1.htm"),
        Hito(D(2025, 12, 23), "Vende el campus de McLaren",
             "Tres edificios en Woking, Inglaterra, vendidos en 250 millones de libras a un cap rate "
             "de 7.4%; los había comprado en abril de 2021 en 170 millones a 9.5%. Con esto da por "
             "terminado su programa de ventas: unos 3,300 millones en 23 meses.",
             "emisor", "Comunicados del 8-dic-2025 y del 23-dic-2025",
             SEC_GNL + "000110465925123952/tm2534006d1_ex99-1.htm", precision="mes"),
        Hito(D(2026, 8, 12), "Compra Modiv Industrial",
             "Paga 1.975 acciones de GNL por cada acción de Modiv —unos 20.4 millones de acciones— por "
             "una cartera industrial en EE. UU. con valor empresa de unos 535 millones, a un cap rate "
             "de 7.6% y con 15 años de plazo remanente. Lo industrial pasa a ser cerca de la mitad de "
             "la renta.",
             "emisor", "8-K y comunicado del 13-ago-2026; comunicado del 4-may-2026",
             SEC_GNL + "000110465926095323/tm2622741d1_ex99-1.htm"),
    ),
    eras=(
        Era("De fondo privado a la bolsa", D(2015, 6, 2), D(2016, 12, 22),
            "GNL deja de ser un REIT no cotizado: los ahorradores que compraron a 10 dólares por "
            "acción pueden vender por primera vez, y la empresa recompra parte con una oferta a "
            "10.50. Firma con su asesor externo un contrato de 20 años cuya comisión crece con cada "
            "emisión de acciones. La cartera es joven —comprada en dos años con el dinero de la "
            "oferta—, 60% en EE. UU. y 40% en Europa, y está rentada al 100%. En 2016 vende 34 "
            "inmuebles para bajar deuda y cierra el año absorbiendo a Global II, el fondo hermano "
            "del mismo patrocinador."),
        Era("Crecer con asesor externo", D(2016, 12, 22), D(2019, 12, 31),
            "Hace un contrasplit de 1 por 3, cambia de director general y termina el contrato con "
            "Moor Park, la firma que le administraba Europa, que lo demanda. Crece con hipotecas, "
            "acciones preferentes —al 7.25% en 2017 y al 6.875% en 2019— y acciones comunes, de "
            "cuyas emisiones el asesor cobra 1.25%. En 2019 dos terceras partes de lo que compra es "
            "industrial, pero las oficinas todavía generan casi la mitad de la renta. El dividendo "
            "pasa de mensual a trimestral sin cambiar el monto."),
        Era("Pandemia", D(2019, 12, 31), D(2021, 12, 31),
            "El covid llega con casi la mitad de la renta en oficinas. GNL cobra 98% de la renta de "
            "abril de 2020 y aun así recorta el dividendo una cuarta parte, y adopta una «píldora "
            "venenosa» contra compras hostiles por la volatilidad de la acción. En diciembre de 2020 "
            "coloca sus primeros bonos sin garantía, con grado de inversión en la emisión, y en 2021 "
            "compra el campus de McLaren en Inglaterra."),
        Era("Tasas, oficinas y activismo", D(2021, 12, 31), D(2023, 9, 12),
            "Las tasas de interés suben con fuerza y las oficinas —41% de la renta a fines de 2022— "
            "pierden atractivo. Blackwells Capital, un accionista activista, intenta llevar "
            "candidatos al consejo, pide quitar la píldora venenosa y elegir a todo el consejo cada "
            "año, y critica las comisiones del asesor; GNL lo combate en tribunales. En mayo de 2023 "
            "anuncia la fusión con The Necessity Retail REIT, otro REIT del mismo grupo, y la compra "
            "de su propio asesor, con buena parte de esos cambios de gobierno; en junio firma la paz "
            "con Blackwells."),
        Era("Internalización y ventas para bajar deuda", D(2023, 9, 12), D(2025, 6, 18),
            "Ya sin asesor externo, GNL es otra empresa: más de 1,300 inmuebles, ahora también "
            "centros comerciales con muchos inquilinos, y una deuda alta. La prioridad pasa a ser "
            "vender: 835 millones en 2024 y, en 2025, la cartera multi-inquilino completa. El "
            "dividendo baja tres veces en año y medio y en febrero de 2025 arranca un programa de "
            "recompra de acciones. Nelson se retira y Edward M. Weil Jr. queda como único director "
            "general."),
        Era("Un solo inquilino y grado de inversión", D(2025, 6, 18), None,
            "Sin los centros comerciales, GNL vuelve a ser dueño de inmuebles de un solo inquilino. "
            "Obtiene grado de inversión de Fitch, vende el campus de McLaren, recompra acciones y se "
            "propone reducir las oficinas. En agosto de 2026 compra Modiv Industrial pagando con "
            "acciones: vuelve a crecer, ahora con industria en EE. UU. y contratos largos."),
    ),
    riesgos=(
        Riesgo("La deuda",
               "Es el tema de la empresa desde 2023. La deuda neta equivale a 6.6 veces el EBITDA "
               "ajustado anualizado del 2T-2026 —8.4 al cierre de 2023— y vence en solo 2.7 años en "
               "promedio: en diciembre de 2027 vencen 500 millones en bonos al 3.75%, en 2028 otros "
               "500 al 4.5% y en 2029 unos 530 millones de hipotecas. Refinanciar a tasas de hoy "
               "cuesta más. El grado de inversión de Fitch está en el escalón más bajo, BBB-."),
        Riesgo("Oficinas y contratos más cortos",
               "Un cuarto de la renta viene de oficinas, el tipo de inmueble que la propia empresa "
               "se propuso reducir en 2026; en 2019 era casi la mitad. El plazo remanente promedio "
               "es de 5.7 años (6.6 con Modiv) y una cuarta parte de la renta vence antes de que "
               "termine 2028: cada vencimiento es renovar, rerrentar o vender."),
        Riesgo("Un grado de inversión en parte «implícito»",
               "63% de la renta viene de inquilinos que la empresa considera de grado de inversión, "
               "pero solo 38% tiene esa calificación; el otro 25% es una estimación propia, hecha "
               "con una herramienta de Moody's a partir de la matriz o de la probabilidad de impago. "
               "El mayor inquilino, FedEx, paga 5.9% de la renta y los veinte mayores, 45%."),
        Riesgo("La herencia del asesor externo",
               "Doce años la administró AR Global, con un contrato que en 2015 se firmó a 20 años; "
               "salir costó 29.6 millones de acciones y 50 millones en efectivo. Bellevue Capital "
               "Partners, matriz del antiguo asesor, tenía 9.9% de las acciones en marzo de 2026, y el "
               "director general dirigió AR Global de 2016 a 2023; en julio de 2026 se desligó de "
               "Bellevue. Los vínculos se han ido cortando, pero no del todo."),
        Riesgo("Un dividendo recortado cuatro veces",
               "De 2.13 dólares al año en 2019 a 0.76: en 2020, con la fusión de 2023, en 2024 y en "
               "2025. Desde 2022 todo el dividendo común se clasifica fiscalmente como devolución de "
               "capital. Las ventas bajan la deuda, pero también el AFFO por acción —1.32 dólares en "
               "2024, 0.99 en 2025—, y delante del accionista común hay cuatro series de preferentes "
               "con cupones de 6.875% a 7.5%."),
        Riesgo("Europa: libras y euros",
               "26% de la renta está en Europa: 10% en el Reino Unido y el resto sobre todo en Países "
               "Bajos, Finlandia y Alemania. La empresa cubre una parte con deuda en euros —22% de su "
               "deuda— y con derivados, pero un dólar fuerte reduce el AFFO en dólares."),
        Riesgo("Divisa, para quien invierte en pesos",
               "El dividendo está en dólares y el retorno en pesos suma la variación del tipo de "
               "cambio: una apreciación del peso resta en la misma medida. En GNL hay una segunda "
               "capa: una cuarta parte de la renta llega en libras y euros, que se mueven contra el "
               "dólar por debajo."),
    ),
    fuentes_extra=(
        ("Precio y dividendos desde 2015", "Yahoo Finance (chart API)."),
        ("FFO, AFFO y la operación 2015-2025", "10-K y comunicados de resultados (8-K Ex-99.1), uno "
         "por uno; ver data/estudios/GNL/anuales_primarios.csv."),
        ("Estados financieros 2015-2026", "XBRL de la SEC (companyfacts) y 8-K trimestrales."),
        ("Tasas", "Treasury a 10 años (FRED), Udibono, CETES y tipo de cambio FIX (Banxico)."),
        ("Historia corporativa", "10-K, 10-Q, 8-K, proxies y prospectos de la SEC (CIK 1526113), "
         "incluidos los de la oferta no cotizada de 2012-2014 y el proxy de Blackwells de 2022."),
        ("Cartera, inquilinos y deuda", "Comunicado y suplemento del 2T-2026 (8-K Ex-99.1 y Ex-99.2); "
         "proxy de 2026."),
    ),
    notas={
        "dividendos": (
            "Para efectos fiscales de EE. UU., la empresa clasificó como devolución de capital entre "
            "64% y 78% del dividendo común de 2018 a 2021, y el 100% de 2022 a 2025: lo repartido "
            "superó la utilidad fiscal."
        ),
        "apalancamiento": (
            "El emisor publica deuda neta ÷ EBITDA ajustado del trimestre multiplicado por cuatro: "
            "8.3x en el 1T-2023, antes de la fusión; 8.4x al cierre de 2023; 7.6x en 2024; 6.7x en "
            "2025 y 6.6x en junio de 2026. La fusión de 2023 y las ventas de 2024-2025 mueven a la "
            "vez la deuda y el EBITDA, así que esos años no se comparan limpio con el anterior."
        ),
    },
)
