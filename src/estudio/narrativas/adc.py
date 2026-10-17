"""Narrativa verificada de Agree Realty Corporation (ADC, CIK 0000917251).

Cada hecho sale de un 10-K, 8-K o comunicado del emisor en EDGAR. Lo que no se encontró en un
documento no entró: por ejemplo, la fecha exacta en que S&P le dio BBB en 2020 o en que Moody's
la subió a Baa1 (solo se sabe que ya las tenía en agosto de 2020 y en agosto de 2022).
"""

from src.estudio.historia import D, Era, HistoriaEmisor, Hito, Riesgo

SEC_ADC = "https://www.sec.gov/Archives/edgar/data/917251/"

HISTORIA_ADC = HistoriaEmisor(
    ticker="ADC",
    nombre="Agree Realty Corporation",
    perfil=(
        "Dueño de inmuebles comerciales de un solo inquilino en EE. UU., rentados con contratos de "
        "arrendamiento neto a cadenas nacionales: el inquilino paga el predial, el seguro y el "
        "mantenimiento. Al 30 de junio de 2026 tenía 2,825 propiedades en los 50 estados y el "
        "Distrito de Columbia, 59.6 millones de pies cuadrados rentables, 99.8% rentado y un plazo "
        "remanente promedio de 7.7 años; 65.8% de la renta viene de inquilinos con grado de "
        "inversión. Los mayores son Walmart (5.8%), Tractor Supply (4.7%) y Dollar General (3.7%). "
        "268 de los contratos son de terreno (ground leases) y dan 10.2% de la renta. Paga dividendo "
        "cada mes desde 2021 —antes, cada trimestre—; en julio de 2026 declaró 0.267 dólares por "
        "acción, 3.204 anualizados. Siempre se ha llamado Agree Realty Corporation y cotiza con la "
        "clave ADC; antes de 1994 el negocio eran 17 sociedades inmobiliarias y una desarrolladora de "
        "la familia Agree, agrupadas como Agree Realty Group."
    ),
    modelo_de_negocio=(
        "Gana dinero con el mismo diferencial que cualquier REIT de arrendamiento neto: compra o "
        "construye inmuebles a un yield mayor que lo que le cuesta el dinero. La propia empresa calcula "
        "ese costo en 5.6% —75% acciones y 25% deuda— contra un cap rate de compra de 7.0% en 2026. Lo "
        "que la distingue es a quién le renta: solo comercio, y casi todo cadenas grandes con grado de "
        "inversión en giros que resisten el comercio electrónico y las recesiones —supermercados, "
        "mejoras para el hogar, tiendas de conveniencia, servicio automotriz—, evitando inquilinos "
        "comprados con deuda por fondos de capital privado. Crece por tres vías: compra inmuebles ya "
        "rentados a terceros (no tanto sale-leaseback, en el que la cadena le vende su tienda y se la "
        "renta de regreso), los desarrolla a la medida de una cadena que firmó antes de construir "
        "—el oficio original de la familia desde 1971— y financia proyectos de otros desarrolladores "
        "que al terminar quedan en su poder. Una parte creciente son ground leases: ADC es dueño del "
        "terreno y el inquilino pagó el edificio, así que tiene mucho que perder si deja de pagar. Se "
        "financia sobre todo con acciones vendidas a plazo (forward): fija hoy el precio y recibe el "
        "dinero cuando cierra la compra. Al cierre de 2025 tenía 90 empleados."
    ),
    hitos=(
        Hito(D(1971, 1, 1), "Fundación",
             "Richard Agree funda el negocio de desarrollo comercial: construye tiendas "
             "para cadenas nacionales y regionales que firman su contrato de renta antes de que "
             "empiece la obra.",
             "emisor", "10-K 1996", SEC_ADC + "0000950009-97-000182.txt", precision="anio"),
        Hito(D(1994, 4, 22), "Sale a bolsa en Nueva York",
             "Completa su oferta inicial: 2.5 millones de acciones a 19.50 dólares, 45.4 millones netos "
             "que usa sobre todo para pagar deuda. Recibe 17 propiedades con 2.4 millones de pies "
             "cuadrados y cotiza en la Bolsa de Nueva York con la clave ADC.",
             "emisor", "10-K 1996", SEC_ADC + "0000950009-97-000182.txt"),
        Hito(D(1996, 12, 31), "Dos anclas, más de la mitad de la renta",
             "32 propiedades en 12 estados: 13 centros comerciales de barrio y 19 tiendas "
             "independientes, casi todas desarrolladas por la empresa. Kmart aporta 31% de la renta y "
             "Borders 26%; a Borders le renta 14 inmuebles, incluida su sede en Ann Arbor.",
             "emisor", "10-K 1996", SEC_ADC + "0000950009-97-000182.txt", precision="anio"),
        Hito(D(2002, 1, 22), "Kmart, su mayor inquilino, quiebra",
             "Kmart, con 24% de la renta y 16 contratos —13 como ancla de sus centros comerciales—, "
             "se acoge al capítulo 11. En 2003, como parte de su reorganización, cierra la tienda de "
             "Lakeland, Florida (unos "
             "480,000 dólares de renta al año), y ADC acepta rebajas por 300,000 al año en otras dos. "
             "El dividendo trimestral se queda en 0.46 y en 2003 vuelve a subir.",
             "emisor", "10-K 2001 y 2002", SEC_ADC + "000095012403000809/k74282e10vk.txt"),
        Hito(D(2008, 12, 31), "La crisis: no recorta",
             "Termina 2008 con 99.2% rentado y el dividendo trimestral en 0.50; en el tercer "
             "trimestre de 2009 lo sube a 0.51. La acción, que en 2007 llegó a 36 dólares, toca 9.31 "
             "en el primer trimestre de 2009. Borders, Walgreens y Kmart suman 68% de la renta.",
             "emisor", "10-K 2008 y 2009", SEC_ADC + "000114420410013162/v177141_10k.htm",
             precision="anio"),
        Hito(D(2009, 6, 8), "Joey Agree, presidente",
             "El hijo del fundador, de 30 años y en la empresa desde 2005, es nombrado presidente y "
             "director de operaciones y entra al consejo. Richard Agree sigue como director general.",
             "emisor", "8-K del 9-jun-2009", SEC_ADC + "000114420409031713/v151928_ex99-1.htm"),
        Hito(D(2010, 4, 1), "Empieza a comprar, no solo a construir",
             "Arranca un programa para comprar inmuebles ya rentados a cadenas nacionales: nueve en "
             "2010 por unos 37 millones de dólares, a un cap rate promedio de 8.0%.",
             "emisor", "10-K 2010 y 2011", SEC_ADC + "000114420412014138/v303805_10k.htm",
             precision="mes"),
        Hito(D(2011, 2, 16), "Borders en quiebra",
             "Le rentaba 14 inmuebles, 7.4 millones al año, 20% de la renta. Borders se liquida entre "
             "julio y septiembre y rechaza todos sus contratos con ADC; en 2012 la empresa entrega "
             "al acreedor cuatro de esos inmuebles para saldar 9.2 millones de hipotecas.",
             "emisor", "8-K del 16-feb-2011; 10-K 2011", SEC_ADC + "000114420411009266/v211774_8k.htm"),
        Hito(D(2011, 4, 12), "Recorta el dividendo",
             "El dividendo trimestral baja de 0.51 a 0.40 dólares (−21.6%), con un pago de 63% del FFO "
             "del trimestre. Desde 1995 nunca había bajado. Se queda en 0.40 hasta 2012.",
             "emisor", "Comunicado del 1T-2011 (8-K del 29-abr-2011); 10-K 2011 y 2012",
             SEC_ADC + "000114420411025175/v220359_ex99-1.htm"),
        Hito(D(2013, 1, 7), "Joey Agree, director general",
             "Sucede a su padre, que dirigía la empresa desde antes de la salida a bolsa y pasa a "
             "presidente ejecutivo del consejo. Sigue en el cargo.",
             "emisor", "8-K del 8-ene-2013", SEC_ADC + "000114420413001196/v331601_8k.htm"),
        Hito(D(2015, 12, 31), "Vende los centros comerciales",
             "En 2014 y 2015 vende seis centros comerciales «no estratégicos» en Michigan, Wisconsin y "
             "Florida. Al cierre de 2017 quedan tres, con 1.5% de la renta, y en el informe de 2018 ya "
             "no aparecen como categoría aparte: queda solo el arrendamiento neto.",
             "emisor", "10-K 2016 y 2017", SEC_ADC + "000114420417010652/v459492_10k.htm",
             precision="anio"),
        Hito(D(2017, 6, 30), "Walgreens baja de 10%",
             "La farmacia, que en 2012 aportaba 30% de la renta, cae a 8.8%. Hoy pesa menos de 1%.",
             "emisor", "Presentación del 2T-2026 (8-K del 30-jul-2026)",
             SEC_ADC + "000091725126000061/adc20260630-ex992.htm", precision="mes"),
        Hito(D(2018, 3, 1), "Primera venta de acciones a plazo",
             "3.45 millones de acciones con contrato forward, liquidadas en septiembre por 160.2 "
             "millones netos. La empresa dice que fue el primer REIT de arrendamiento neto en usar "
             "este mecanismo, que desde entonces repite casi cada año.",
             "emisor", "10-K 2018; presentación del 2T-2026",
             SEC_ADC + "000155837019000849/adc-20181231x10k.htm", precision="mes"),
        Hito(D(2018, 5, 31), "Grado de inversión",
             "Moody's le asigna Baa2 con perspectiva estable. La empresa lo presenta como acceso a "
             "dinero más barato y más flexible.",
             "emisor", "8-K del 1-jun-2018", SEC_ADC + "000114420418032375/tv495725_ex99-1.htm"),
        Hito(D(2018, 10, 22), "Los ground leases, cartera aparte",
             "Empieza a reportar por separado sus terrenos rentados: 44 propiedades en 18 estados, "
             "89.2% de la renta de inquilinos con grado de inversión. A mediados de 2026 son 268 "
             "contratos y 10.2% de la renta.",
             "emisor", "Comunicado del 3T-2018; comunicado del 2T-2026",
             SEC_ADC + "000114420418054748/tv505210_ex99-1.htm"),
        Hito(D(2020, 4, 20), "Covid: cobra 87% de la renta de abril",
             "Al 17 de abril había cobrado la renta de abril de más de 87% de su cartera y de todos "
             "sus inquilinos con grado de inversión; de septiembre a diciembre cobra 99%. Sube el "
             "dividendo dos veces en el año y invierte 1,340 millones, el doble que en 2018.",
             "emisor", "Comunicado del 1T-2020; 8-K del 4-ene-2021; 10-K 2020",
             SEC_ADC + "000110465920048415/tm2016338d1_ex99-1.htm"),
        Hito(D(2020, 8, 17), "Primer bono público",
             "350 millones de dólares al 2.900% con vencimiento en 2030; hasta entonces sus bonos eran "
             "colocaciones privadas. Para entonces tenía también BBB de S&P.",
             "emisor", "8-K del 17-ago-2020; presentación del 12-ago-2020",
             SEC_ADC + "000110465920096208/tm2026156d72_8k.htm"),
        Hito(D(2021, 1, 1), "Pasa al dividendo mensual",
             "Tras 107 dividendos trimestrales seguidos desde 1994, anuncia que pagará cada mes. El "
             "primero, de 0.207 dólares, se paga el 12 de febrero: 2.484 anualizados, 6.2% más que en "
             "el primer trimestre de 2020.",
             "emisor", "Comunicado del 4T-2020 (8-K del 18-feb-2021); 10-K 2025",
             SEC_ADC + "000110465921025206/tm217034d3_ex99-1.htm", precision="mes"),
        Hito(D(2025, 9, 30), "A- de Fitch",
             "Fitch le asigna A- con perspectiva estable. Ya tenía Baa1 de Moody's y BBB+ de S&P, que "
             "la subió a fines de 2024. En marzo de 2025 había abierto un programa de papel comercial.",
             "emisor", "Comunicado del 3T-2025 (8-K del 21-oct-2025); 8-K del 6-ene-2025; 10-K 2025",
             SEC_ADC + "000110465925101229/adc-20251021xex99d1.htm", precision="anio"),
        Hito(D(2026, 7, 30), "Trimestre récord de inversión",
             "502 millones en 102 propiedades en el segundo trimestre de 2026, a un cap rate de 7.0% en "
             "las compras. El dividendo mensual de 0.267 dólares es 4.3% mayor que un año antes.",
             "emisor", "Comunicado del 2T-2026 (8-K del 30-jul-2026)",
             SEC_ADC + "000091725126000061/adc20260630-ex991.htm"),
    ),
    eras=(
        Era("Desarrollador con dos anclas", D(1994, 4, 22), D(2002, 1, 22),
            "Sale a bolsa la desarrolladora de la familia Agree: centros comerciales de barrio "
            "anclados por Kmart, sobre todo en Michigan, y tiendas construidas a la medida de "
            "Borders, incluida su sede. Solo construye lo que ya está rentado. Kmart y Borders pesan "
            "más de la mitad de la renta y el dividendo apenas se mueve. La euforia tecnológica de "
            "fines de los noventa vacía a los REIT, y en enero de 2002 quiebra Kmart."),
        Era("Kmart en quiebra y las farmacias", D(2002, 1, 22), D(2007, 2, 6),
            "ADC pierde una tienda Kmart y concede rebajas en otras dos, sin recortar el dividendo. "
            "Sigue desarrollando, cada vez más farmacias Walgreens —de 17% de la renta en 2001 a 23% "
            "en 2007—, pero la dependencia cambia de nombre más que de tamaño: Borders, Walgreens y "
            "Kmart suman dos tercios de la renta. Las "
            "tasas bajan y el crédito barato empuja los precios de todo inmueble."),
        Era("Crisis financiera", D(2007, 2, 6), D(2009, 3, 6),
            "Se congela el crédito y los REIT caen con todo lo que dependa de financiamiento. ADC "
            "sigue casi llena y no recorta el dividendo, pero su mayor inquilino, Borders —30% de la "
            "renta—, ya pierde dinero: 157 millones en su año fiscal 2007."),
        Era("Relevo y la caída de Borders", D(2009, 3, 6), D(2013, 1, 7),
            "La Reserva Federal lleva las tasas a cero. Joey Agree, hijo del fundador, toma la "
            "presidencia en 2009 y en 2010 arranca la compra de inmuebles ya rentados. En 2011 Borders "
            "quiebra y se liquida: ADC pierde una quinta parte de la renta, recorta el dividendo 22% y "
            "entrega cuatro inmuebles hipotecados al acreedor."),
        Era("Diversificación", D(2013, 1, 7), D(2018, 5, 31),
            "Con Joey Agree como director general, ADC pasa de desarrollador a comprador: de 18 "
            "propiedades adquiridas en 2013 a 79 en 2017. Vende los centros comerciales, baja "
            "Walgreens de 30% a menos de 10% de la renta, y Michigan, donde estaban 47 de sus 109 "
            "propiedades en 2012, queda en 12% de la renta en 2017. En 2013 el "
            "anuncio de que la Fed retirará estímulos sacude a los REIT."),
        Era("Grado de inversión y pandemia", D(2018, 5, 31), D(2021, 12, 31),
            "Moody's le da grado de inversión y ADC empieza a financiarse con acciones vendidas a "
            "plazo y, desde 2020, con bonos públicos. La inversión pasa de 654 millones en 2018 a "
            "1,340 millones en 2020, a cap rates que bajan de 7.0% a 6.4%. En la pandemia cobra 87% "
            "de la renta de abril de 2020 y 99% desde septiembre, y sube el dividendo; en 2021 lo "
            "paga cada mes y emite preferentes al 4.25%."),
        Era("Choque de tasas", D(2021, 12, 31), D(2023, 10, 27),
            "El bono a diez años pasa de 1.5% a casi 5%. ADC invierte 1,620 millones en 2022 a un cap "
            "rate de 6.2% y 1,280 millones en 2023 a 6.9%: el yield de compra sube con las tasas, pero "
            "mucho menos que el costo del dinero, y el mercado ya no necesita un REIT de arrendamiento "
            "neto para conseguir rendimiento."),
        Era("Tasas altas", D(2023, 10, 27), None,
            "Con las tasas estables en niveles altos, el cap rate de compra sube a 7.5% en 2024 y la "
            "inversión baja a 939 millones; en 2025 vuelve a 1,570 millones y en 2026 marca récords "
            "trimestrales. Abre papel comercial, obtiene A- de Fitch y BBB+ de S&P y sigue creciendo "
            "con acciones vendidas a plazo. Desde fines de 2025 el dividendo mensual crece entre 3.6% "
            "y 4.3% al año."),
    ),
    riesgos=(
        Riesgo("Las tasas",
               "Con contratos de casi ocho años en promedio y rentas casi fijas, la acción se comporta "
               "como un bono largo: cuando el Treasury sube, su precio baja aunque el negocio no cambie. "
               "Los bonos de 2020 y 2021, con cupones de 2.0% a 2.9%, costarán más al refinanciarse: el "
               "de septiembre de 2026 salió a 5.650%."),
        Riesgo("El motor de crecimiento depende del precio de la acción",
               "ADC crece vendiendo acciones: tres cuartas partes de su costo de capital, según su "
               "propio cálculo, y 686 millones colocados a plazo solo en el primer semestre de 2026. "
               "Compra a ~7.0%; si su acción se abarata, ese margen se cierra y crecer por acción se "
               "vuelve difícil."),
        Riesgo("Todo es comercio",
               "Toda la cartera es comercio minorista. La empresa eligió giros que resisten el comercio "
               "electrónico —supermercados 10.1%, mejoras para el hogar 9.0%, conveniencia 8.3%—, pero "
               "un cambio de hábitos de compra, aranceles o una recesión pegan a toda la cartera a la "
               "vez; no hay oficinas, industria ni otros países que compensen."),
        Riesgo("El crédito de los inquilinos",
               "ADC ya vivió la quiebra de sus dos grandes anclas: Kmart en 2002 y Borders en 2011, "
               "que le costó una quinta parte de la renta y el único recorte de su dividendo desde 1995. "
               "Hoy el "
               "mayor pesa 5.8% y dos tercios de la renta tienen grado de inversión, pero 14% viene de "
               "inquilinos por debajo de ese grado y 20% de inquilinos sin calificación."),
        Riesgo("Contratos más cortos",
               "El plazo remanente promedio bajó de 10.2 años en 2018 a 7.7 a mediados de 2026. Los "
               "vencimientos de 2026 son apenas 0.4% de la renta, pero cada año más contratos llegan a "
               "su fin y hay que renovarlos o rerrentarlos."),
        Riesgo("Una empresa de familia",
               "Joey Agree dirige la empresa desde 2013 y su padre, el fundador, preside el consejo. La "
               "estrategia de compras desde 2010 es de él, y el propio 10-K cuenta la pérdida de "
               "directivos clave entre los riesgos."),
        Riesgo("Divisa, para quien invierte en pesos",
               "Todos los inmuebles y el dividendo están en dólares. El retorno en pesos suma la "
               "variación del tipo de cambio: una apreciación del peso resta en la misma medida."),
    ),
    fuentes_extra=(
        ("Precio y dividendos desde 1994", "Yahoo Finance (chart API)."),
        ("FFO, AFFO y la operación 1996-2025", "10-K y comunicados de resultados (8-K Ex-99.1) de la "
         "SEC, uno por uno."),
        ("Estados financieros 2008-2026", "XBRL de la SEC (companyfacts) y 8-K trimestrales."),
        ("Tasas", "Treasury a 10 años (FRED), Udibono, CETES y tipo de cambio FIX (Banxico)."),
        ("Historia corporativa", "10-K, 8-K, comunicados y presentaciones a inversionistas (8-K "
         "Ex-99.2) de la SEC."),
    ),
    notas={
        "apalancamiento": (
            "El emisor publica deuda neta ÷ EBITDA recurrente «proforma»: resta de la deuda el dinero "
            "que recibirá por las acciones ya vendidas a plazo y todavía no entregadas. Al 30 de junio "
            "de 2026 era 3.7x, y 5.2x sin restarlo. La cifra de aquí no hace ese ajuste."
        ),
    },
)
