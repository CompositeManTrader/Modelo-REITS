"""Narrativa verificada de Prologis, Inc. (antes AMB Property Corporation), CIK 1045609.

La sociedad listada desde 1997 es AMB: en la fusión de 2011 AMB sobrevivió, tomó el nombre y la
clave de ProLogis y quedó como Prologis, Inc. Por eso la historia de precio y de dividendos es la
de AMB hasta junio de 2011. Cada hecho sale de un documento de la SEC (10-K, 8-K, 8-K/A,
prospectos 424B y suplementos trimestrales); lo que no se encontró en una fuente no entró.
"""

from src.estudio.historia import D, Era, HistoriaEmisor, Hito, Riesgo

SEC_PLD = "https://www.sec.gov/Archives/edgar/data/1045609/"

HISTORIA_PLD = HistoriaEmisor(
    ticker="PLD",
    nombre="Prologis, Inc.",
    perfil=(
        "Dueño, desarrollador y administrador de bodegas y centros de distribución —lo que el "
        "sector llama inmuebles logísticos— en 20 países. Al 30 de septiembre de 2026 tenía, por "
        "su cuenta o en sus fondos de coinversión, 5,941 edificios y proyectos por unos 1,300 "
        "millones de pies cuadrados (123 millones de m²), rentados a unos 6,500 clientes de dos "
        "tipos: empresas que se abastecen entre sí y comercio minorista o en línea. Amazon es el "
        "mayor, con 5.6% de la renta; Mercado Libre está entre los 15 primeros. La cartera en "
        "operación estaba 95.6% ocupada y sus contratos vencen, en promedio, en 3.9 años. EE. UU. "
        "aporta 84% del NOI de su participación; Europa, 9%; el resto de América, 5%, y Asia, 2%. "
        "En México opera 359 edificios con 68.5 millones de pies cuadrados (unos 6.4 millones de "
        "m²) y patrocina y administra FIBRA Prologis, que cotiza en la Bolsa Mexicana y de la que "
        "tenía 34.6% al cierre de 2025. Paga dividendo cada trimestre: 1.07 dólares por acción en "
        "2026, contra 1.01 en 2025. Su deuda tiene calificación A2 de Moody's y A de S&P. Se llamó "
        "AMB Property Corporation, con la clave AMB, desde su salida a bolsa en 1997 hasta junio "
        "de 2011, cuando absorbió a ProLogis y tomó su nombre y su clave."
    ),
    modelo_de_negocio=(
        "Prologis gana dinero de tres maneras. La principal es la renta: empresas de logística, "
        "comercio y manufactura le pagan por bodegas cerca de grandes ciudades, puertos y "
        "aeropuertos, y le reembolsan casi todos los gastos de operación. Sus contratos duran unos "
        "seis años —70 meses en promedio los que empezaron en 2025—, mucho menos que los de un "
        "REIT de arrendamiento neto, así que cada renovación lleva la renta al nivel del mercado: "
        "esa es la palanca que más mueve su crecimiento, para bien y para mal. La segunda es el "
        "desarrollo: compra terreno, construye y renta; un edificio estabilizado vale más de lo "
        "que costó, y esa «creación de valor» la cobra al venderlo o aportarlo a uno de sus "
        "fondos. La tercera es el capital estratégico, el negocio con el que nació AMB en 1983: "
        "administra fondos con grandes inversionistas institucionales —por ejemplo, el fondo "
        "soberano de Noruega—, pone de 15% a 55% del dinero y cobra comisiones por administrar y, "
        "si el fondo supera ciertas metas, comisiones de desempeño («promotes»). Ese negocio da "
        "de 5% a 10% de los ingresos y la utilidad, pero le permite crecer con dinero ajeno, "
        "reducir su exposición a otras monedas y tener a quién venderle lo que construye. Lo que "
        "la distingue es la escala: se presenta como el líder mundial del sector y la usa para "
        "atender a clientes que están en muchos mercados, comprar materiales más baratos y, "
        "ahora, convertir terrenos en centros de datos."
    ),
    hitos=(
        Hito(D(1983, 1, 1), "Fundación de AMB",
             "Douglas Abbey, Hamid Moghadam y T. Robert Burke fundan AMB como administrador de "
             "inversiones inmobiliarias para instituciones. En 1997 administra 2,800 millones de "
             "dólares de más de 70 inversionistas institucionales.",
             "emisor", "Prospecto de salida a bolsa (424B1) de nov-1997",
             SEC_PLD + "0000950150-97-001737.txt", precision="anio"),
        Hito(D(1997, 11, 21), "Cotiza en la Bolsa de Nueva York",
             "Empieza a operar con la clave AMB; Hamid Moghadam es su director general. Coloca "
             "16.1 millones de acciones a 21 dólares (338 millones brutos) y, con los inmuebles "
             "que aportan sus clientes, arranca con 43.5 millones de pies cuadrados: 37.3 millones "
             "en bodegas (95.7% rentadas) y 6.2 millones en centros comerciales con supermercado.",
             "emisor", "10-K 1997", SEC_PLD + "0000950149-98-000586.txt"),
        Hito(D(1998, 6, 1), "Grado de inversión y primeros bonos",
             "Coloca 400 millones de dólares en notas no garantizadas a 2008, 2015 y 2018, a 7.18% "
             "en promedio, y recibe Baa1 de Moody's, BBB de S&P y BBB+ de Duff & Phelps. Su línea "
             "de crédito baja 0.20 puntos de tasa.",
             "emisor", "10-K 1998", SEC_PLD + "0000950149-99-000495.txt", precision="mes"),
        Hito(D(1999, 3, 9), "Sale de los centros comerciales",
             "Firma la venta de 28 centros comerciales a BPP Retail (Burnham Pacific con CalPERS) "
             "por 663.4 millones de dólares, con la idea de reinvertir unos 520 millones en "
             "bodegas. Al cierre de 1999 ya vendió 30 y le quedan nueve.",
             "emisor", "10-K 1998 y 10-K 1999", SEC_PLD + "0000950149-00-000578.txt"),
        Hito(D(2002, 12, 31), "Primeros inmuebles fuera de EE. UU.",
             "2002 es su primer año con operación internacional: cobra renta en Ciudad de México, "
             "Guadalajara y París. Se fija la meta de tener de 10% a 15% de sus activos fuera de "
             "EE. UU. en tres a cinco años, con Monterrey, Europa y Asia entre sus mercados.",
             "emisor", "10-K 2002", SEC_PLD + "000095014903000562/f87871e10vk.htm",
             precision="anio"),
        Hito(D(2008, 11, 17), "La crisis: suspende y recorta el dividendo",
             "Suspende el dividendo del cuarto trimestre de 2008 —ya había cumplido el reparto "
             "mínimo del año— y fija el de 2009 en 1.12 dólares anuales: 0.28 por trimestre contra "
             "0.52 en 2008 (−46%). Solo construye lo ya comprometido y recorta 22% de su plantilla.",
             "emisor", "8-K del 17-nov-2008; 10-K 2008",
             SEC_PLD + "000095014908000101/f50598exv99w1.htm"),
        Hito(D(2009, 3, 25), "Coloca acciones a 12.15 dólares",
             "41.25 millones de acciones nuevas, por debajo de los 21 dólares de su salida a bolsa, "
             "por unos 480 millones netos que usa para pagar sus líneas de crédito.",
             "emisor", "8-K del 26-mar-2009; prospecto 424B5 del 26-mar-2009",
             SEC_PLD + "000095013409006103/f51936exv99w1.htm"),
        Hito(D(2011, 1, 31), "Anuncia la fusión con ProLogis",
             "«Fusión de iguales» en acciones con ProLogis, de Denver, formada en 1991 y llamada "
             "antes Security Capital Industrial Trust: cada acción de ProLogis se cambia por 0.4464 "
             "acciones nuevas de AMB. Los accionistas de ProLogis quedan con 60% y los de AMB con 40%, en una empresa "
             "de unos 600 millones de pies cuadrados en 22 países.",
             "emisor", "8-K del 31-ene-2011; 10-K 2008 de ProLogis; EDGAR (CIK 899881)",
             SEC_PLD + "000095012311006931/y89358exv99w1.htm"),
        Hito(D(2011, 6, 3), "AMB se convierte en Prologis",
             "Cierra la fusión: AMB, la sociedad que sobrevive, se renombra Prologis, Inc. y cotiza "
             "con la clave PLD. Sus accionistas conservan sus acciones una por una; el canje solo "
             "aplica a los de ProLogis, que contablemente es la adquirente. Moghadam y Walter "
             "Rakowich, de ProLogis, quedan como codirectores generales.",
             "emisor", "8-K del 8-jun-2011; 10-K 2011",
             SEC_PLD + "000095012311057596/y91585ae8vk.htm"),
        Hito(D(2013, 1, 1), "Moghadam, director general único",
             "Rakowich se retira el 31 de diciembre de 2012, como se pactó en la fusión, y Moghadam "
             "queda como director general y presidente del consejo.",
             "emisor", "8-K del 28-dic-2012", SEC_PLD + "000119312512518242/d459525d8k.htm"),
        Hito(D(2014, 1, 1), "Primer aumento del dividendo desde 2008",
             "En el primer trimestre de 2014 el dividendo trimestral pasa de 0.28 a 0.33 dólares. "
             "Llevaba en 0.28 desde 2009: los años de la crisis y de la integración.",
             "emisor", "10-K 2014 (tabla de precios y dividendos)",
             SEC_PLD + "000119312515062622/d834674d10k.htm", precision="anio"),
        Hito(D(2014, 6, 1), "Nace FIBRA Prologis",
             "Sale a la Bolsa Mexicana de Valores con 177 inmuebles y 29.7 millones de pies "
             "cuadrados (2.8 millones de m²) que le compra a Prologis y a dos de sus fondos. "
             "Prologis se queda con 45% de los certificados, colocados a 27 pesos.",
             "emisor", "10-K 2014", SEC_PLD + "000119312515062622/d834674d10k.htm",
             precision="mes"),
        Hito(D(2015, 6, 1), "Compra KTR",
             "5,900 millones de dólares por la cartera y la plataforma de KTR Capital Partners: unos "
             "60 millones de pies cuadrados en EE. UU. Compra a través de un fondo 55-45 con Norges "
             "Bank Investment Management, que administra el fondo soberano de Noruega; la parte de "
             "Prologis vale unos 3,200 millones.",
             "emisor", "8-K del 1-jun-2015", SEC_PLD + "000119312515207873/d933474dex991.htm"),
        Hito(D(2018, 8, 22), "Compra DCT Industrial",
             "8,500 millones de dólares con deuda incluida, pagados en acciones: 1.02 acciones de "
             "Prologis por cada una de DCT.",
             "emisor", "8-K del 22-ago-2018", SEC_PLD + "000119312518254515/d612993dex991.htm"),
        Hito(D(2020, 2, 4), "Compra Liberty Property Trust",
             "13,000 millones de dólares con deuda incluida, en acciones (0.675 de Prologis por cada "
             "una de Liberty): 108 millones de pies cuadrados de bodegas. Un mes antes, con dos de "
             "sus fondos, compró Industrial Property Trust por unos 4,000 millones en efectivo.",
             "emisor", "8-K del 4-feb-2020 y del 8-ene-2020",
             SEC_PLD + "000110465920010125/tm203336d9_ex99-1.htm"),
        Hito(D(2020, 12, 31), "Covid: casi no se nota en la renta",
             "En 2020 difiere 45 millones de dólares de renta, menos de 1% de la renta anual de la "
             "cartera administrada, y a enero de 2021 ya cobró 98% de lo vencido. La empresa ve dos "
             "motores nuevos de demanda: más inventario, porque las cadenas de suministro priorizan "
             "la resiliencia sobre la eficiencia, y la aceleración del comercio electrónico.",
             "emisor", "10-K 2020", SEC_PLD + "000156459021005312/pld-10k_20201231.htm",
             precision="anio"),
        Hito(D(2022, 10, 3), "Compra Duke Realty",
             "Unos 23,000 millones de dólares con deuda al cierre (26,000 millones al anunciarse en "
             "junio), en acciones: 0.475 de Prologis por cada una de Duke. Suma 142 millones de pies "
             "cuadrados en 19 mercados de EE. UU. y más de 500 clientes nuevos.",
             "emisor", "8-K del 13-jun-2022 y del 3-oct-2022",
             SEC_PLD + "000110465922105238/tm2227221d1_ex99-1.htm"),
        Hito(D(2024, 8, 1), "FIBRA Prologis toma Terrafina",
             "Con ofertas públicas en certificados y efectivo, FIBRA Prologis compra 89.9% de "
             "Terrafina, otra FIBRA industrial, con 41 millones de pies cuadrados. La participación "
             "de Prologis en FIBRA Prologis baja a 34.6%; a fines de 2025 la FIBRA ya tiene más de "
             "99% de Terrafina.",
             "emisor", "10-K 2024 y 10-K 2025", SEC_PLD + "000095017025021272/pld-20241231.htm",
             precision="mes"),
        Hito(D(2026, 1, 1), "Dan Letter, director general",
             "Sucede a Hamid Moghadam, director general desde la salida a bolsa de 1997, que se "
             "queda como presidente ejecutivo del consejo. Letter entró a Prologis en 2004 y era "
             "presidente desde 2023.",
             "emisor", "8-K del 19-feb-2025; 8-K/A del 22-ene-2026",
             SEC_PLD + "000119312525029178/d874222d8k.htm"),
        Hito(D(2026, 8, 4), "Oferta por SEGRO",
             "Tras un rechazo en junio, el consejo de la británica SEGRO recomienda una oferta de "
             "unos 14,000 millones de libras: 0.0920 acciones de Prologis por cada una de SEGRO, con "
             "una opción parcial en efectivo. Prologis buscaría cotizar también en Londres y espera "
             "cerrar en el primer semestre de 2027. Ese día vende 15 millones de acciones nuevas "
             "(17.25 millones con la opción de los colocadores) para, entre otros fines, pagarla.",
             "emisor", "8-K del 24-jun-2026, del 4-ago-2026 y del 6-ago-2026; prospecto 424B3 del "
             "4-ago-2026", SEC_PLD + "000110465926089980/tm2621154d2_8k.htm"),
    ),
    eras=(
        Era("Listado y salida del comercio", D(1997, 11, 21), D(1999, 12, 31),
            "AMB, que administraba inmuebles para instituciones, se vuelve su dueña en bolsa: ofrece "
            "a sus más de 70 clientes cambiar sus bodegas y centros comerciales por acciones. En "
            "1998 obtiene grado de inversión y en 1999 decide quedarse solo con lo industrial: vende "
            "casi todos sus centros comerciales. Al final del periodo la euforia tecnológica le "
            "quita compradores a todos los REIT."),
        Era("Industrial puro, fondos y salida al mundo", D(1999, 12, 31), D(2007, 2, 6),
            "Ya sin centros comerciales, AMB se concentra en bodegas cerca de aeropuertos, puertos y "
            "carreteras —lo que llama «High Throughput Distribution»— y hace crecer sus fondos de "
            "coinversión con instituciones. En 2002 empieza a operar en México y en Europa, con la "
            "meta de llevar de 10% a 15% de sus activos fuera de EE. UU. Revienta la burbuja "
            "tecnológica, las tasas bajan y el crédito barato empuja los precios de todo inmueble."),
        Era("Crisis financiera", D(2007, 2, 6), D(2009, 3, 6),
            "Se congela el crédito y los REIT caen con todo lo que depende de financiamiento. AMB, "
            "que a fines de 2008 ya está en 15 países y tiene 1,600 millones de dólares en "
            "desarrollo, frena la construcción, recorta 22% de su plantilla, suspende el dividendo "
            "del cuarto trimestre de 2008 y baja casi a la mitad el de 2009 para quedarse con "
            "efectivo."),
        Era("Recapitalización y fusión", D(2009, 3, 6), D(2011, 6, 3),
            "En marzo de 2009, en plena crisis, AMB coloca acciones nuevas para pagar deuda y "
            "mantiene el dividendo en 0.28 dólares por trimestre. ProLogis, de Denver, había salido "
            "más golpeada: en noviembre de 2008 cambió de director y recortó a menos de la mitad el "
            "dividendo que tenía previsto. En enero de 2011 las dos anuncian una «fusión de "
            "iguales» que cierra en junio."),
        Era("La nueva Prologis", D(2011, 6, 3), D(2019, 12, 31),
            "Con el nombre y la clave de ProLogis, la empresa combinada integra dos plataformas y se "
            "propone salir de los mercados que no considera estratégicos. Lleva a bolsa vehículos "
            "propios en Japón (2013) y México (2014), y en 2014 vuelve a subir el dividendo, "
            "congelado desde 2009. Desde 2015 compra carteras grandes en EE. UU. —KTR, DCT y, al "
            "cierre del periodo, el acuerdo por Liberty—, pagando con acciones o con socios. La "
            "empresa atribuye la demanda a la reconfiguración de las cadenas de suministro, muy "
            "influida por el comercio electrónico."),
        Era("Pandemia y auge logístico", D(2019, 12, 31), D(2021, 12, 31),
            "Cierra las compras de Industrial Property Trust y Liberty semanas antes de que se "
            "declare la pandemia. El covid apenas toca la renta —difiere menos de 1% y cobra casi "
            "todo— y la empresa identifica dos motores nuevos de demanda: más inventario y la "
            "aceleración del comercio electrónico. A fines de 2020 calcula que sus contratos están "
            "13% por debajo de la renta de mercado. Las tasas están en el piso."),
        Era("Choque de tasas y Duke Realty", D(2021, 12, 31), D(2023, 10, 27),
            "El bono a diez años pasa de 1.5% a casi 5% en menos de dos años: sube el costo del "
            "dinero con que se compran y se valúan los inmuebles. La operación sigue fuerte: en "
            "octubre de 2022 cierra la compra de Duke Realty, la más grande de su historia, y en "
            "2023 las renovaciones salen 76% arriba de la renta anterior y la cartera administrada "
            "cierra el año 97.6% ocupada."),
        Era("Rentas planas, centros de datos y SEGRO", D(2023, 10, 27), None,
            "Con las tasas estables en niveles altos, las rentas de mercado crecen poco o bajan "
            "varios trimestres y la ocupación de la cartera administrada baja a 95.6% en septiembre "
            "de 2026; las renovaciones siguen saliendo arriba porque los contratos viejos quedaron "
            "por debajo del mercado. Los aranceles anunciados en abril de 2025 agregan "
            "incertidumbre. Prologis empuja los centros de datos, Moghadam deja la dirección a Dan "
            "Letter en 2026 y la empresa lanza la oferta por SEGRO, en el Reino Unido."),
    ),
    riesgos=(
        Riesgo("Las rentas de mercado dejaron de subir",
               "El crecimiento interno de Prologis sale de renovar contratos a la renta de mercado, "
               "y ese colchón se está gastando: a fines de 2025 sus contratos estaban 18% por "
               "debajo del mercado, y las renovaciones subieron 50% en 2025 contra 76% en 2023. Las "
               "rentas de mercado llevan varios trimestres planas o a la baja, y la ocupación de la "
               "cartera administrada pasó de 97.6% a fines de 2023 a 95.6% en septiembre de 2026."),
        Riesgo("Las tasas y el valor de los inmuebles",
               "Parte de la utilidad depende de lo que valen los inmuebles, no solo de la renta: las "
               "ganancias por vender o aportar a sus fondos lo que construye —la guía de 2026 prevé "
               "de 600 a 700 millones de dólares— y las comisiones de los fondos, que se cobran "
               "sobre el valor de sus activos. Si las tasas suben, esos valores bajan y las dos "
               "fuentes se encogen al mismo tiempo."),
        Riesgo("Comercio exterior y aranceles",
               "La demanda de bodegas sigue al comercio y al consumo. La empresa reporta que las "
               "propuestas de aranceles de abril de 2025 causaron una perturbación económica, "
               "aunque el arrendamiento se recuperó durante el año. Para la cartera mexicana, "
               "cualquier cambio en las reglas del comercio con EE. UU. pesa de forma directa."),
        Riesgo("Amazon y el comercio electrónico",
               "Amazon es el mayor cliente, con 5.6% de la renta, y los 25 mayores suman 21.8%. La "
               "empresa atribuye buena parte de su demanda al comercio electrónico, y en octubre de "
               "2026 dice que el exceso de capacidad que tenían sus clientes en sus redes «se ha "
               "absorbido en buena medida»: la demanda depende de que no vuelvan a rentar de más."),
        Riesgo("Apuestas grandes: centros de datos y SEGRO",
               "Prologis está convirtiendo terrenos en centros de datos —tiene 5.8 gigawatts de "
               "energía asegurada o en etapa avanzada— y ofrece unos 14,000 millones de libras por "
               "SEGRO, pagados sobre todo con acciones nuevas. Los centros de datos exigen mucho "
               "capital y dependen de conseguir energía y equipo escaso; SEGRO agrega exposición a "
               "Europa y a la libra, riesgo de integración y la posibilidad de que la operación no "
               "cierre en los términos previstos."),
        Riesgo("Divisa, para quien invierte en pesos",
               "El dividendo y casi todo el valor están en dólares: 96% del capital de Prologis está "
               "en dólares y de 97% a 99% de sus utilidades previstas de 2026 a 2028 están en dólares "
               "o cubiertas. El retorno en pesos suma la variación del tipo de cambio: una "
               "apreciación del peso resta en la misma medida. La cartera mexicana no compensa ese "
               "riesgo, porque Prologis la maneja en dólares."),
    ),
    fuentes_extra=(
        ("Precio y dividendos desde 1997", "Yahoo Finance (chart API). Hasta junio de 2011 es la "
         "acción de AMB Property Corporation, la misma sociedad con otro nombre."),
        ("FFO y la operación 1997-2025", "10-K y comunicados de resultados (8-K Ex-99.1) de AMB "
         "Property Corporation hasta 2010 y de Prologis desde 2011, uno por uno; ver "
         "data/estudios/PLD/anuales_primarios.csv."),
        ("Estados financieros", "XBRL de la SEC (companyfacts), 8-K trimestrales y suplementos "
         "trimestrales de Prologis (8-K Ex-99.1)."),
        ("Tasas", "Treasury a 10 años (FRED), Udibono, CETES y tipo de cambio FIX (Banxico)."),
        ("Historia corporativa", "Prospecto de salida a bolsa de 1997, 10-K, 8-K, 8-K/A y "
         "prospectos 424B de AMB Property Corporation y Prologis (CIK 1045609); 8-K y 10-K 2008 de "
         "ProLogis (CIK 899881)."),
    ),
    notas={
        "dividendos": (
            "AMB no pagó dividendo en el cuarto trimestre de 2008: el consejo lo suspendió porque "
            "ya había repartido el mínimo que exige el régimen REIT para ese año, y bajó el de 2009 "
            "de 0.52 a 0.28 dólares por trimestre. El primer pago, de 0.134 dólares en diciembre de "
            "1997, cubrió solo del 26 de noviembre al 31 de diciembre. En los estados financieros "
            "de 2011 en adelante, los dividendos por acción de antes de la fusión son los de "
            "ProLogis; los de AMB están en la tabla de precios y dividendos del 10-K (Item 5)."
        ),
        "apalancamiento": (
            "En la fusión de 2011 AMB fue la adquirente legal y ProLogis la contable: los estados "
            "financieros de los 10-K posteriores —y por lo tanto su XBRL— presentan los años "
            "anteriores con las cifras de ProLogis. Hasta 2010, las cifras de este emisor son las "
            "que publicó AMB; desde 2011, las de la empresa combinada, en la que los accionistas de "
            "AMB quedaron con 40%."
        ),
    },
)
