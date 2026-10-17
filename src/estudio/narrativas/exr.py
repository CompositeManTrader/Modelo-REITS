"""Narrativa verificada de Extra Space Storage Inc. (EXR, CIK 0001289490).

Cada hecho salió de un documento que se puede abrir: el prospecto de salida a bolsa
(424B4), los 10-K, 10-Q, 8-K y proxies de la SEC, y los comunicados de S&P Dow Jones
Indices. Lo que no se encontró en una fuente no entró: por ejemplo, en qué ciudad se
fundó el negocio en 1977 —los documentos dicen que Kenneth Woolley lo fundó ese año y
que la sede está en Salt Lake City, Utah, pero no dónde empezó—, ni el sitio de la
empresa, que no se pudo abrir.
"""

from src.estudio.historia import D, Era, HistoriaEmisor, Hito, Riesgo

SEC_EXR = "https://www.sec.gov/Archives/edgar/data/1289490/"

HISTORIA_EXR = HistoriaEmisor(
    ticker="EXR",
    nombre="Extra Space Storage Inc.",
    perfil=(
        "Dueño y operador de bodegas de autoalmacenaje (self storage) en EE. UU.: edificios con "
        "cientos de cuartos de distintos tamaños que personas y pequeños negocios rentan casi "
        "siempre mes a mes para guardar muebles, inventario o archivos. Es el mayor operador del "
        "país por número de tiendas. Al 30 de junio de 2026 operaba 4,410 tiendas en 42 estados y "
        "Washington, D.C., con unos 3.0 millones de bodegas y 341 millones de pies cuadrados "
        "rentables: 2,026 son suyas al 100%, 420 están en coinversiones con socios y 1,964 las "
        "administra para otros dueños a cambio de una comisión. Sus tiendas comparables tenían "
        "94.2% de ocupación, y paga un dividendo trimestral de 1.62 dólares, el mismo desde "
        "principios de 2023. Además tiene unos 1,500 millones de dólares prestados a dueños de "
        "tiendas que administra. Su sede está en Salt Lake City, Utah. Antes de salir a bolsa, en "
        "2004, el negocio operaba como Extra Space Storage LLC; desde entonces no ha cambiado de "
        "nombre ni de clave."
    ),
    modelo_de_negocio=(
        "El autoalmacenaje es un negocio inmobiliario que se opera, no solo se renta. A diferencia "
        "de un REIT de arrendamiento neto, que firma con un inquilino un contrato de diez años en el "
        "que este paga todos los gastos, EXR renta millones de bodegas chicas, casi todas mes a mes, "
        "a personas que se mudan, reducen su casa o todavía no se instalan en una definitiva, y a "
        "pequeños negocios. Es un negocio «operado» y no «rentado»: EXR paga a los empleados de cada "
        "tienda, la publicidad en internet, el predial y el seguro, y se queda con la diferencia (el "
        "NOI, o utilidad operativa de los inmuebles). Como los contratos vencen cada mes, el precio "
        "se ajusta todo el tiempo —desde su salida a bolsa usa un sistema propio de precios en "
        "tiempo real— y a los clientes que se quedan se les sube la renta; por eso los ingresos "
        "suben rápido cuando la demanda aprieta y se estancan cuando se enfría. Sobre sus tiendas "
        "montó negocios que piden poco capital: administra casi 2,000 tiendas de otros dueños a "
        "cambio de una comisión (la plataforma de este tipo más grande del sector), coinvierte con "
        "socios institucionales que ponen la mayor parte del capital, reasegura el seguro que sus "
        "clientes compran para lo que guardan y presta dinero puente a dueños de tiendas que "
        "administra. Esas comisiones y esos intereses le dan flujo extra y, sobre todo, una fila de "
        "tiendas que puede comprar después. A los vendedores puede pagarles con unidades de su "
        "sociedad operativa (estructura UPREIT), que les permiten diferir impuestos."
    ),
    hitos=(
        Hito(D(1977, 1, 1), "Fundación",
             "Kenneth Woolley funda la empresa. Él y Richard Tanner, en el negocio desde ese año, "
             "encabezaron dos de los primeros desarrollos de bodegas de autoalmacenaje en EE. UU. "
             "Woolley sigue como presidente del consejo en 2026.",
             "emisor", "8-K del 2-feb-2009; 10-K 2004; proxy de 2026",
             SEC_EXR + "000110465909005610/a09-4356_1ex99d1.htm", precision="anio"),
        Hito(D(2004, 8, 17), "Sale a bolsa en Nueva York",
             "Coloca 20.2 millones de acciones a 12.50 dólares con la clave EXR y recibe 234.8 "
             "millones netos. Arranca con 136 tiendas en 20 estados, 28 de ellas todavía "
             "llenándose. El dividendo inicial, 0.91 dólares al año (7.3% sobre el precio de "
             "colocación), equivalía a 146% del flujo que la empresa estimaba tener para repartir.",
             "emisor", "Prospecto 424B4 de ago-2004; 10-K 2004",
             SEC_EXR + "000119312504139148/d424b4.htm"),
        Hito(D(2005, 7, 14), "Compra Storage USA a GE",
             "Junto con Prudential Real Estate Investors le compra Storage USA a GE Commercial "
             "Finance por unos 2,300 millones de dólares en efectivo, la mayor operación de la "
             "industria hasta entonces. La parte de EXR cuesta 585.7 millones y 259 tiendas quedan "
             "en coinversiones con Prudential. Pasa a ser el segundo operador de EE. UU., con 631 "
             "tiendas propias o administradas en 34 estados (contando Washington, D.C.).",
             "emisor", "10-K 2005", SEC_EXR + "000104746906003235/a2168325z10-k.htm"),
        Hito(D(2009, 4, 1), "Spencer Kirk, director general",
             "Kenneth Woolley deja la dirección para cumplir una misión de tres años para su "
             "iglesia. Lo sucede como presidente del consejo y director general Spencer Kirk, "
             "presidente de la empresa, que trabajaba con Woolley desde 1998 y era su mayor "
             "accionista individual, con unos 3.3 millones de acciones.",
             "emisor", "8-K del 2-feb-2009 y del 23-feb-2009",
             SEC_EXR + "000110465909005610/a09-4356_1ex99d1.htm"),
        Hito(D(2009, 4, 6), "Suspende el dividendo",
             "Tras pagar 0.25 dólares en el primer trimestre —lo mismo que cada trimestre de 2008— "
             "anuncia que no pagará dividendo en el segundo ni en el tercero, para retener hasta "
             "unos 67 millones de liquidez; en marzo ya había recomprado notas canjeables por 71.5 "
             "millones pagando 44.5. En el cuarto trimestre paga 0.13 en efectivo y en 2010, 0.10 "
             "por trimestre. El dividendo de 2009 suma 0.38 dólares, contra 1.00 en 2008.",
             "emisor", "8-K del 4-may-2009 (resultados 1T-2009); 10-K 2009; 8-K del 22-feb-2010",
             SEC_EXR + "000110465909029117/a09-11226_1ex99d1.htm"),
        Hito(D(2012, 7, 1), "Regresa el fundador",
             "Woolley vuelve de su misión como presidente ejecutivo del consejo y director de "
             "inversiones; Kirk sigue como director general. Desde mayo de 2018 Woolley preside el "
             "consejo sin cargo ejecutivo.",
             "emisor", "Comunicado del 7-dic-2011 (8-K); proxy de 2026",
             SEC_EXR + "000110465911068621/a11-31367_1ex99d1.htm", precision="mes"),
        Hito(D(2012, 7, 2), "Compra a Prudential su parte de PRISA III",
             "Paga unos 300 millones —162 en efectivo y el resto con deuda asumida— por el 94.9% "
             "que no tenía de una coinversión de 36 tiendas en 18 estados formada en 2005. Es parte "
             "de un giro hacia las tiendas propias: de 279 a fines de 2008 pasa a 448 a fines de "
             "2012.",
             "emisor", "8-K del 9-jul-2012; 10-K 2008 y 2012",
             SEC_EXR + "000110465912048021/a12-16039_18k.htm"),
        Hito(D(2015, 10, 1), "Compra SmartStop",
             "Paga unos 1,310 millones de dólares en efectivo por SmartStop Self Storage, un REIT "
             "que no cotizaba en bolsa y era el séptimo operador del país; con la venta previa de "
             "algunos activos, la operación suma 1,400 millones. Agrega 122 tiendas propias y la "
             "administración de otras 43.",
             "emisor", "8-K del 15-jun-2015 y del 1-oct-2015",
             SEC_EXR + "000119312515334603/d44825dex991.htm"),
        Hito(D(2016, 1, 15), "Entra al S&P 500",
             "Sustituye a Chubb al cierre del 15 de enero de 2016. Había entrado al S&P MidCap 400 "
             "en enero de 2013.",
             "emisor", "S&P Dow Jones Indices, comunicados del 23-ene-2013 y del 13-ene-2016",
             "https://press.spglobal.com/2016-01-13-Extra-Space-Storage-Set-to-Join-the-S-P-500-EPR-Properties-to-Join-S-P-MidCap-400-U-S-Concrete-World-Wrestling-Entertainment-to-Join-S-P-SmallCap-600"),
        Hito(D(2017, 1, 1), "Joe Margolis, director general",
             "Sucede a Spencer Kirk, que se retira. Margolis trabajó en Prudential Real Estate "
             "Investors de 1992 a 2004, fue consejero de EXR de 2005 a 2015 y su director de "
             "inversiones desde julio de 2015.",
             "emisor", "8-K del 12-sep-2016", SEC_EXR + "000119312516707028/d244024dex991.htm"),
        Hito(D(2018, 12, 31), "Empieza a prestar a terceros",
             "A fines de 2018 empieza a dar préstamos puente a dueños de tiendas terminadas que EXR "
             "administra: hipotecarios y mezzanine (garantizados con las acciones de la sociedad "
             "dueña), a tres años con dos prórrogas y tasa variable, y vende parte de los "
             "hipotecarios. La cartera pasa de 13.9 millones a fines de 2018 a unos 1,500 millones "
             "a mediados de 2026.",
             "emisor", "10-K 2019; 10-Q 2T-2026",
             SEC_EXR + "000162828020002202/q4201910kexrdocument.htm", precision="anio"),
        Hito(D(2019, 7, 1), "Grado de inversión",
             "S&P le da BBB; Moody's le da Baa2 en enero de 2021. En mayo de 2021 coloca su primer "
             "bono público: 450 millones al 2.55% con vencimiento en 2031.",
             "emisor", "10-K 2020 y 2021", SEC_EXR + "000162828021003458/exr-20201231.htm",
             precision="mes"),
        Hito(D(2020, 5, 6), "Covid: cobra 93% de la renta de abril",
             "Contra 98% un año antes. Desde mediados de marzo suspende las subastas de bodegas "
             "morosas y los aumentos a clientes existentes, y retira su guía de 2020. Mantiene el "
             "dividendo en 0.90 dólares todo el año.",
             "emisor", "8-K del 6-may-2020 (resultados 1T-2020); 8-K del 22-feb-2021",
             SEC_EXR + "000162828020006689/q12020ex991earningsrel.htm"),
        Hito(D(2021, 12, 31), "Ocupación récord",
             "La ocupación de sus tiendas comparables cierra 2021 en 95.3%, la más alta de su "
             "historia, y su ingreso crece 13.8% en el año (el NOI, 19.7%). El dividendo trimestral "
             "sube de 0.90 a 1.00 dólares a principios de 2021 y llega a 1.25 al cierre del año.",
             "emisor", "8-K del 23-feb-2022 (resultados 4T-2021); 8-K del 22-feb-2021",
             SEC_EXR + "000162828022003522/q42021ex991earningsrelease.htm", precision="anio"),
        Hito(D(2022, 9, 15), "Compra Storage Express",
             "590 millones por 106 tiendas operadas a distancia y ocho terrenos en Illinois, "
             "Indiana, Kentucky y Ohio; 125 millones se pagan con unidades de la sociedad "
             "operativa. Su fundador entra al consejo.",
             "emisor", "10-K 2022; 8-K del 15-sep-2022",
             SEC_EXR + "000162828023005628/exr-20221231.htm"),
        Hito(D(2023, 3, 31), "Dividendo de 1.62",
             "El dividendo trimestral sube 8.0%, de 1.50 a 1.62 dólares. No ha vuelto a cambiar: "
             "suma 6.48 dólares en 2023, 2024 y 2025, y en el segundo trimestre de 2026 sigue en "
             "1.62.",
             "emisor", "8-K del 2-may-2023 (resultados 1T-2023); 10-K 2025; 8-K del 28-jul-2026",
             SEC_EXR + "000162828023014876/q12023ex991earningsrelease.htm"),
        Hito(D(2023, 7, 20), "Fusión con Life Storage",
             "Fusión en acciones: 0.8950 acciones de EXR por cada una de Life Storage, cuyos "
             "accionistas quedan con cerca de 35% de la empresa combinada. Suma 1,198 tiendas —758 "
             "propias, 141 en coinversiones y 299 administradas— y crea el mayor operador del país, "
             "con más de 3,500 tiendas. S&P sube su calificación a BBB+.",
             "emisor", "8-K del 3-abr-2023 y del 20-jul-2023; 10-K 2025",
             SEC_EXR + "000119312523190116/d395569dex991.htm"),
        Hito(D(2025, 12, 31), "Dos años sin crecer en tiendas comparables",
             "El ingreso de sus tiendas comparables crece 0.2% en 2024 y 0.1% en 2025, y su NOI "
             "baja 1.5% y 1.7%. El Core FFO por acción crece 0.2% y 1.1%, sostenido sobre todo por "
             "la administración para terceros y los préstamos puente.",
             "emisor", "8-K del 25-feb-2025 y del 19-feb-2026",
             SEC_EXR + "000128949026000007/q42025ex991earningsrelease.htm", precision="anio"),
        Hito(D(2026, 8, 24), "Noah Springer será director general",
             "Asumirá el 1 de enero de 2027, cuando se retire Joe Margolis. Springer entró en 2006, "
             "construyó la plataforma de administración para terceros —casi 2,000 tiendas— y es "
             "presidente de la empresa desde enero de 2026. Será el cuarto director general de su "
             "historia.",
             "emisor", "8-K del 24-ago-2026",
             SEC_EXR + "000128949026000058/aug2026ex991announcement.htm"),
    ),
    eras=(
        Era("Salida a bolsa y Storage USA", D(2004, 8, 17), D(2007, 2, 6),
            "EXR sale a bolsa con 136 tiendas, una parte todavía llenándose, y con un dividendo que "
            "al principio rebasaba el flujo disponible. En 2005 compra Storage USA junto con "
            "Prudential y de golpe se vuelve el segundo operador del país, con una plataforma "
            "nacional y una cartera de franquicias y tiendas de terceros que después puede comprar. "
            "Las tasas bajas y el crédito barato empujan los precios de todo inmueble; el periodo "
            "termina en el máximo de los REIT de febrero de 2007."),
        Era("Crisis y dividendo suspendido", D(2007, 2, 6), D(2009, 12, 31),
            "Se congela el crédito cuando EXR tiene muchas tiendas nuevas en etapa de llenado, y en "
            "2009 los ingresos de sus tiendas comparables bajan. El fundador deja la dirección y "
            "Spencer Kirk toma el mando. Para cuidar la liquidez, recompra con descuento parte de "
            "sus notas canjeables y suspende el dividendo dos trimestres; a fin de año lo retoma en "
            "un nivel mucho menor que el de 2008."),
        Era("Tasas en el piso y plataforma para terceros", D(2009, 12, 31), D(2015, 10, 1),
            "La Reserva Federal lleva las tasas a cero y la ocupación se recupera. EXR reconstruye "
            "el dividendo desde 0.10 dólares por trimestre, el fundador regresa en 2012 como "
            "presidente ejecutivo y la empresa recompra a sus socios varias coinversiones —entre "
            "ellas una con Prudential formada en 2005—: con eso y con compras pasa de 279 tiendas "
            "propias en 2008 a 448 en 2012. Se convierte en el mayor administrador de tiendas de "
            "terceros del país y en 2013 entra al S&P MidCap 400."),
        Era("SmartStop, S&P 500 y oferta nueva", D(2015, 10, 1), D(2019, 12, 31),
            "La compra de SmartStop agrega 122 tiendas y el crecimiento lleva a EXR al S&P 500 en "
            "enero de 2016. Joe Margolis, consejero desde 2005 y antes ejecutivo de Prudential Real "
            "Estate Investors, asume la dirección en 2017. Del lado del mercado, la construcción de "
            "tiendas nuevas presiona las rentas: la empresa habla de «oferta nueva significativa» en "
            "2019. A fines de 2018 empieza a prestar a los dueños de las tiendas que administra, y en "
            "2019 obtiene grado de inversión de S&P."),
        Era("Pandemia y auge del almacenaje", D(2019, 12, 31), D(2021, 12, 31),
            "El covid primero frena la cobranza: en abril de 2020 la empresa suspende subastas y "
            "aumentos a clientes y retira su guía. Después la ocupación llega a máximos históricos y "
            "EXR sube precios con fuerza; en 2021 el ingreso de sus tiendas comparables crece 13.8% "
            "y el dividendo pasa de 0.90 a 1.25 dólares por trimestre. "
            "Coloca sus primeros bonos públicos y obtiene grado de inversión de Moody's."),
        Era("Choque de tasas y Life Storage", D(2021, 12, 31), D(2023, 7, 20),
            "Las tasas suben con rapidez y encarecen el dinero con el que un REIT compra inmuebles. "
            "EXR compra Storage Express, una cadena de tiendas operadas a distancia en el medio "
            "oeste, sube el dividendo a 1.62 dólares a principios de 2023 y en abril acuerda "
            "fusionarse en acciones con Life Storage; la operación cierra en julio y la convierte en "
            "el mayor operador del país."),
        Era("La empresa combinada", D(2023, 7, 20), None,
            "Con Life Storage integrada, EXR opera más de 4,400 tiendas y S&P sube su calificación a "
            "BBB+. La dirección describe un entorno difícil: en 2024 y 2025 el ingreso de sus "
            "tiendas comparables queda prácticamente plano y su NOI baja, y el flujo por acción "
            "crece poco, gracias a la administración para terceros, los préstamos puente y el "
            "seguro. El dividendo no se mueve de 1.62 dólares desde 2023. En agosto de 2026 anuncia "
            "que Noah Springer sucederá a Joe Margolis en 2027."),
    ),
    riesgos=(
        Riesgo("Contratos de un mes",
               "Casi todas sus rentas son mes a mes. Eso le permite subir precios rápido cuando hay "
               "demanda, pero también la expone en la bajada: según la propia empresa, la demanda "
               "depende del desempleo, de las tasas y de cuántas casas se compran y venden. En 2024 "
               "y 2025 el NOI de sus tiendas comparables bajó 1.5% y 1.7%."),
        Riesgo("Oferta nueva",
               "La empresa reconoce que el desarrollo de tiendas nuevas ha aumentado y ha "
               "intensificado la competencia en sus mercados, y que puede seguir creciendo. En 2018 "
               "y 2019 la dirección atribuyó a la oferta nueva parte de la presión sobre sus "
               "resultados. Las tiendas que ella misma compra recién construidas diluyen el flujo "
               "de dos a cuatro años mientras se llenan."),
        Riesgo("Las tasas y la deuda",
               "Al cierre de 2025 debía unos 13,500 millones de dólares, 17.9% a tasa variable sin "
               "cobertura: cada punto de alza en la tasa de referencia le cuesta unos 24 millones al "
               "año. Como todo REIT, crece con deuda y acciones nuevas; con tasas altas, comprar "
               "tiendas a precios que aumenten el flujo por acción se vuelve más difícil. Su "
               "calificación es BBB+ (S&P) y Baa2 (Moody's)."),
        Riesgo("Préstamos e inversiones financieras",
               "Tiene unos 1,800 millones en préstamos e instrumentos de deuda —1,500 millones en "
               "préstamos puente a dueños de tiendas que administra, de 70% a 80% del valor del "
               "inmueble al otorgarse— y 250 millones en acciones preferentes de empresas ligadas a "
               "SmartStop. Han sostenido el crecimiento de los últimos años y la exponen al crédito "
               "de otros operadores; al cierre de 2025 ningún préstamo estaba en cartera vencida."),
        Riesgo("Regulación y desastres",
               "Las leyes que limitan los aumentos de renta durante emergencias, las reglas sobre "
               "cargos y subastas de bodegas morosas y las demandas de clientes pueden frenar sus "
               "ingresos; en 2026 registró costos por un acuerdo legal con la ciudad de Nueva York. "
               "Texas, Florida y California concentran unas 1,500 de las 4,281 tiendas que operaba "
               "a fines de 2025, y el reaseguro que da a sus clientes paga más siniestros justo "
               "cuando hay huracanes o incendios."),
        Riesgo("Divisa, para quien invierte en pesos",
               "Todas las tiendas y el dividendo están en dólares. El retorno en pesos suma la "
               "variación del tipo de cambio: una apreciación del peso resta en la misma medida."),
    ),
    fuentes_extra=(
        ("Precio y dividendos desde 2004", "Yahoo Finance (chart API)."),
        ("FFO y la operación 2004-2026", "Prospecto de salida a bolsa (424B4), 10-K, 10-Q y "
         "comunicados de resultados (8-K Ex-99.1) de la SEC, uno por uno."),
        ("Estados financieros 2008-2026", "XBRL de la SEC (companyfacts) y 8-K trimestrales."),
        ("Tasas", "Treasury a 10 años (FRED), Udibono, CETES y tipo de cambio FIX (Banxico)."),
        ("Historia corporativa", "10-K, 8-K, 10-Q y proxies de la SEC; comunicados de S&P Dow "
         "Jones Indices."),
    ),
    notas={
        "dividendos": (
            "En 2009 no hubo dividendo en el segundo ni en el tercer trimestre. El del cuarto (0.13 "
            "dólares) se pagó en efectivo, aunque en abril la empresa había previsto pagarlo 90% en "
            "acciones. El primer dividendo, de 0.1113 dólares, cubrió solo del 17 de agosto al 30 de "
            "septiembre de 2004."
        ),
    },
)
