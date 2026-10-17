"""Narrativa verificada de Welltower Inc. (antes Health Care REIT, Inc.; CIK 766704).

Cada hecho salió de un documento de EDGAR: 10-K, 8-K (comunicados Ex-99.1 y
suplementos Ex-99.2), proxies y el informe anual de 1995. Lo que no se encontró en
un documento no entró: el split 3 por 2 de 1985 y la fecha de la oferta pública
inicial son anteriores a EDGAR y ningún documento consultado los confirma.
"""

from src.estudio.historia import D, Era, HistoriaEmisor, Hito, Riesgo

SEC_WELL = "https://www.sec.gov/Archives/edgar/data/766704/"

HISTORIA_WELL = HistoriaEmisor(
    ticker="WELL",
    nombre="Welltower Inc.",
    perfil=(
        "Dueño de vivienda para adultos mayores —residencias independientes, de vida asistida y "
        "de cuidado de la memoria— en EE. UU., el Reino Unido y Canadá, y de una cartera menor de "
        "asilos con cuidados posagudos. A diferencia de un REIT de arrendamiento, la mayor parte de "
        "su utilidad no viene de rentas fijas: viene de operar los inmuebles a través de "
        "administradores especializados. Al 30 de junio de 2026 tenía participación en 2,950 "
        "inmuebles, incluidos terrenos y obras en desarrollo, 2,667 de ellos en operación. Los "
        "inmuebles operados generaban 69.9% de su utilidad operativa neta (NOI), las residencias "
        "rentadas a operadores 12.8%, los asilos y centros posagudos 14.9% y lo que queda de "
        "consultorios médicos 2.4%; 67% del NOI venía de EE. UU., 24% del Reino Unido y 9% de "
        "Canadá. La ocupación de los inmuebles operados era de 87.6%. Paga dividendo cada "
        "trimestre —221 seguidos— y en julio de 2026 lo subió 15%, a 0.85 dólares. Se llamó "
        "Health Care REIT, Inc. hasta 2015 y cotizó con la clave HCN hasta 2018; los documentos de "
        "1995 mencionan también el nombre «Health Care Fund», que era de su asesor externo y la "
        "empresa adquirió al absorberlo."
    ),
    modelo_de_negocio=(
        "Welltower gana dinero de dos maneras con el mismo tipo de inmueble. En la clásica, renta "
        "la residencia o el asilo a un operador con un contrato triple net: el operador paga una "
        "renta fija que sube cada año, más el predial, el seguro y el mantenimiento, y el riesgo es "
        "que el operador no pueda pagar. Así funcionó durante décadas, y antes fue sobre todo "
        "prestamista: en 1994, 71% de lo invertido eran préstamos hipotecarios a operadores de "
        "asilos. En la segunda, que hoy domina, se queda con la operación: es dueño del inmueble "
        "—solo o en sociedad con el operador— y le paga al operador una comisión por "
        "administrarlo, ligada a resultados. Lo permite la ley RIDEA de 2007, que deja a un REIT "
        "tener la operación en una subsidiaria que paga impuestos siempre que la administre un "
        "tercero; el sector llama a estos inmuebles «operados» (SHO o SHOP). Ahí Welltower cobra lo "
        "que pagan los residentes cada mes y paga sueldos, comida y servicios: si suben la "
        "ocupación o la tarifa, se queda con casi todo el aumento; si bajan, absorbe la pérdida. "
        "Se parece más a un hotel que a un arrendamiento. Lo que lo distingue es la apuesta "
        "demográfica —vivienda en renta para una población que envejece, la «economía plateada», "
        "como la llama la empresa—, que 93% de esos ingresos son pago privado y no del gobierno, y "
        "la escala para escoger operadores y mercados con su propia plataforma de datos. Crece "
        "emitiendo acciones: si la acción vale mucho frente a lo que rinden los inmuebles que "
        "compra, cada compra aumenta el flujo por acción."
    ),
    hitos=(
        Hito(D(1970, 1, 1), "Fundación",
             "Nace como el primer REIT dedicado solo a inmuebles de salud. Desde ese año lo "
             "administra un asesor externo, First Toledo, cuyos dueños —Bruce Thompson y Frederic "
             "Wolfe, consejeros desde 1971— eran en 1994 su director general y su presidente.",
             "emisor", "10-K 1994, proxy de 1994 y 10-K 1999", SEC_WELL + "0000950152-95-000288.txt",
             precision="anio"),
        Hito(D(1992, 12, 1), "Cotiza en la Bolsa de Nueva York",
             "Se lista a fines de 1992 «para mejorar su visibilidad en los mercados de capital», "
             "según su informe anual de 1995. En 1993 una colocación privada de notas por 52 "
             "millones de dólares obtiene calificación de grado de inversión.",
             "emisor", "Informe anual 1995 (presentado en EDGAR en abril de 1996)",
             SEC_WELL + "0000766704-96-000008.txt", precision="anio"),
        Hito(D(1995, 11, 30), "Deja de pagarle a un asesor externo",
             "Absorbe a First Toledo Advisory Company a cambio de 282,407 acciones, unos 5 "
             "millones de dólares. En 1994 le había pagado 3.1 millones —0.1% mensual de los "
             "activos netos de deuda más un incentivo sobre la utilidad— y sus siete empleados "
             "eran del asesor.",
             "emisor", "10-K 1994 y 10-K 1995", SEC_WELL + "0000766704-96-000006.txt"),
        Hito(D(1996, 10, 14), "George Chapman, director general",
             "En la empresa desde 1992, sucede a Bruce Thompson y suma la presidencia del consejo. "
             "Dirige casi dieciocho años.",
             "emisor", "Proxy de 1997", SEC_WELL + "0000950152-97-002123.txt", precision="mes"),
        Hito(D(2000, 6, 30), "Congela el dividendo",
             "Desde 1993 lo subía medio centavo cada trimestre; del 2T-2000 al 1T-2004 lo deja en "
             "0.585 dólares, mientras los asilos y la vivienda asistida enfrentan quiebras y "
             "sobreoferta. Vuelve a "
             "subir, a 0.60, en el 2T-2004.",
             "emisor", "10-K 1999, 2001 y 2004",
             SEC_WELL + "000095015202002172/l92984ae10-k405.txt", precision="anio"),
        Hito(D(2003, 7, 23), "Grado de inversión en Moody's",
             "Moody's sube sus notas no garantizadas de Ba1 a Baa3 por su apalancamiento "
             "moderado, su poca deuda garantizada y la mejora de sus asilos y residencias. En 2005 "
             "tiene Baa3, BBB- y BBB- de Moody's, S&P y Fitch.",
             "emisor", "10-K 2003 y 10-K 2005", SEC_WELL + "000095015204001895/l05635ae10vk.txt"),
        Hito(D(2006, 12, 20), "Fusión con Windrose",
             "Compra Windrose Medical Properties Trust, de Indianápolis, por 1,018 millones de "
             "dólares, pagados con 9.7 millones de acciones valuadas en 41 dólares y con "
             "preferentes. Entra de lleno a los consultorios médicos: al cierre de 2006 tiene 89 "
             "edificios médicos entre sus 578 inmuebles.",
             "emisor", "10-K 2006", SEC_WELL + "000095015207001691/l24255ae10vk.htm"),
        Hito(D(2008, 12, 31), "La crisis: no recorta",
             "El dividendo trimestral se queda en 0.68 dólares del 2T-2008 al 1T-2010: no lo "
             "recorta, pero deja de subirlo. La acción pasa de un máximo de 53.98 dólares en el "
             "3T-2008 a un mínimo de 25.86 en el 1T-2009, y en 2009 la empresa compra apenas 68 "
             "millones en inmuebles.",
             "emisor", "10-K 2009 y 10-K 2011", SEC_WELL + "000095012310018352/l38660e10vk.htm",
             precision="anio"),
        Hito(D(2009, 1, 29), "Entra al S&P 500",
             "Entra al índice al cierre del 29 de enero y el 3 de febrero coloca 5.8 millones de "
             "acciones por 214 millones de dólares, en plena crisis.",
             "emisor", "10-K 2008", SEC_WELL + "000095015209002082/l35635ae10vk.htm"),
        Hito(D(2010, 9, 1), "Entra a los inmuebles operados (RIDEA)",
             "Forma con Merrill Gardens, que ya le rentaba residencias, una sociedad 80/20 dueña de "
             "38 comunidades, sobre todo en la costa oeste, que Merrill sigue operando: deja de "
             "cobrar solo renta "
             "y se queda con la utilidad de operación, con la estructura que permite la ley RIDEA "
             "de 2007. En diciembre repite con Senior Star (90/10, nueve comunidades).",
             "emisor", "10-K 2010", SEC_WELL + "000095012311018750/l41762e10vk.htm",
             precision="mes"),
        Hito(D(2011, 4, 1), "Compra los inmuebles de Genesis HealthCare",
             "2,400 millones de dólares por 147 asilos, centros posagudos y residencias del "
             "noreste y el Atlántico medio, que se rentan de regreso a Genesis (sale-leaseback) con "
             "un contrato triple net a 15 años. Renta inicial de 198 millones, 8.25% del precio, "
             "con aumentos de 3.5% anual los primeros cinco años.",
             "emisor", "Comunicado del 28-feb-2011; 8-K del 1-abr-2011",
             SEC_WELL + "000095012311019795/l42010exv99w1.htm"),
        Hito(D(2013, 1, 9), "Compra Sunrise Senior Living",
             "Paga 14.50 dólares por acción en efectivo y se queda con los inmuebles; el negocio de "
             "administración se vende a un grupo, con KKR y Beecken Petty O'Keefe, en el que toma "
             "20%. Son 125 residencias de lujo en mercados como Nueva York, Los Ángeles y Londres: "
             "3,400 millones al cierre y 4,300 previstos para julio de 2013. Los inmuebles operados "
             "pasan de 20% de la inversión en 2011 a 39% en 2013.",
             "emisor", "Comunicados del 22-ago-2012 y del 9-ene-2013; 8-K del 11-ene-2013; 10-K 2013",
             SEC_WELL + "000119312513010874/d465478dex992.htm"),
        Hito(D(2014, 4, 14), "Thomas DeRosa, director general",
             "Chapman se retira por motivos de salud; lo sucede DeRosa, consejero y exdirector de "
             "finanzas de The Rouse Company. Se separan los cargos: Jeffrey Donahue pasa a "
             "presidente del consejo.",
             "emisor", "8-K del 14-abr-2014", SEC_WELL + "000119312514141691/d711101dex991.htm"),
        Hito(D(2015, 9, 30), "Se llama Welltower",
             "Health Care REIT pasa a ser Welltower Inc., «una marca que enfatiza el bienestar», "
             "según DeRosa. La clave en la bolsa sigue siendo HCN.",
             "emisor", "8-K del 30-sep-2015", SEC_WELL + "000119312515333376/d41656dex991.htm"),
        Hito(D(2018, 2, 28), "Cambia la clave a WELL",
             "El comunicado de resultados del 22 de febrero todavía usa HCN; el 10-K presentado el "
             "28, ya WELL.",
             "emisor", "Comunicado del 22-feb-2018 (8-K); 10-K 2017",
             SEC_WELL + "000076670418000012/10-K.htm", precision="mes"),
        Hito(D(2018, 7, 26), "Compra Quality Care Properties con ProMedica",
             "En efectivo, a 20.75 dólares por acción, en sociedad 80/20 con el sistema de salud "
             "ProMedica, que se queda con la operadora HCR ManorCare y firma un contrato triple net "
             "a 15 años. Para Welltower son unos 2,200 millones a un rendimiento inicial cercano a "
             "8%.",
             "emisor", "Comunicado del 25-abr-2018; 8-K del 26-jul-2018",
             SEC_WELL + "000119312518132992/d577986dex991.htm"),
        Hito(D(2020, 5, 4), "Covid: recorta el dividendo",
             "De 0.87 a 0.61 dólares por trimestre (−30%), «70% del nivel previo al covid»; no lo "
             "suspende: es el 196º dividendo trimestral seguido. La ocupación de los inmuebles "
             "operados baja de 85.8% en febrero de 2020 a 74.4% en febrero de 2021.",
             "emisor", "Comunicado del 1T-2020 (8-K del 6-may-2020); 10-K 2020",
             SEC_WELL + "000076670420000029/a1q20earningsrelease991.htm"),
        Hito(D(2020, 10, 5), "Shankh Mitra, director general",
             "Sucede a DeRosa a los 40 años. Llegó en 2016 desde la administración de fondos y "
             "dirigía las inversiones; Kenneth Bacon queda como presidente del consejo. Sigue en el "
             "cargo.",
             "emisor", "8-K del 5-oct-2020", SEC_WELL + "000119312520264008/d939440dex991.htm"),
        Hito(D(2025, 10, 27), "Apuesta total por la vivienda para mayores",
             "Compra en el Reino Unido una cartera operada por Barchester por unos 5,200 millones "
             "de libras y la de HC-One por 1,200 millones, y acuerda vender 18 millones de pies "
             "cuadrados de consultorios médicos por unos 7,200 millones de dólares. En total "
             "anuncia 23,000 millones en operaciones.",
             "emisor", "Comunicado del 3T-2025 (8-K del 27-oct-2025)",
             SEC_WELL + "000076670425000037/a3q25earningsrelease991.htm"),
        Hito(D(2026, 7, 27), "Dividendo de 0.85",
             "El dividendo trimestral sube 15%: es el tercer aumento desde 2024, tras 0.67 en julio "
             "de 2024 y 0.74 en julio de 2025. Todavía queda 2% abajo de los 0.87 de antes del "
             "covid.",
             "emisor", "Comunicados del 29-jul-2024, 28-jul-2025 y 27-jul-2026 (8-K)",
             SEC_WELL + "000076670426000026/a2q26earningsrelease991.htm"),
    ),
    eras=(
        Era("Prestamista que se pasa a la vivienda asistida", D(1993, 1, 1), D(1999, 12, 31),
            "Health Care REIT es una empresa chica de Toledo que financia asilos: en 1994, 71% de "
            "lo invertido son préstamos hipotecarios a sus operadores. En 1995 absorbe a su asesor "
            "externo y en 1996 George Chapman toma la dirección. La empresa se vuelca a la vivienda "
            "asistida —«el primer REIT de salud en identificarla», dice su informe de 1995— y en "
            "cinco años ese tipo de inmueble llega a 70% de la cartera. Al final del periodo la "
            "reforma de los pagos de Medicare de 1997 empieza a quebrar a los operadores de asilos, "
            "y los REIT se vacían por la euforia tecnológica."),
        Era("Quiebras, grado de inversión y Windrose", D(1999, 12, 31), D(2007, 2, 6),
            "Entre 1999 y mediados de 2000 se declara en quiebra cerca de 11% de los asilos de EE. "
            "UU., y la vivienda asistida, construida de más, tarda en llenarse; según la empresa, "
            "eso abarató a todos los REIT de salud. Health Care REIT congela el dividendo, agrupa "
            "los contratos de cada operador en arrendamientos maestros para protegerse en una "
            "quiebra y enfrenta la de Alterra, que le rentaba 45 residencias. En 2001 vuelve a "
            "conseguir capital, en 2003 Moody's le da grado de inversión y en 2006 compra Windrose, "
            "que le da consultorios médicos y hospitales. Las tasas bajan y el crédito barato empuja "
            "los precios de todo inmueble."),
        Era("Crisis financiera", D(2007, 2, 6), D(2009, 3, 6),
            "Se congela el crédito y cae todo lo que dependa de financiamiento. Health Care REIT "
            "mantiene el dividendo en 0.68 dólares por trimestre desde mediados de 2008 —no lo "
            "recorta, pero deja de subirlo— y en 2009 casi deja de comprar inmuebles. Entra al "
            "S&P 500 en "
            "enero de 2009 y aprovecha la inclusión para colocar acciones."),
        Era("RIDEA, Genesis y Sunrise", D(2009, 3, 6), D(2014, 4, 14),
            "Con las tasas en el piso, la empresa pasa de comprar 68 millones de dólares en "
            "inmuebles en 2009 a 1,707 millones en 2010 y 4,526 millones en 2011. Cambia de modelo: "
            "desde 2010 se queda con la operación de residencias junto con operadores como Merrill "
            "Gardens, Senior Star, Benchmark y Silverado, y en 2013 compra los inmuebles de "
            "Sunrise; los operados pasan de 20% de la inversión en 2011 a 39% en 2013. Compra "
            "también los de Genesis para rentarlos y entra a Canadá y al Reino Unido. El periodo "
            "termina con el retiro de Chapman."),
        Era("DeRosa: Welltower y los sistemas de salud", D(2014, 4, 14), D(2019, 12, 31),
            "Thomas DeRosa rebautiza la empresa como Welltower, cambia la clave a WELL y busca "
            "asociarse con sistemas de salud: en 2018 compra Quality Care Properties junto con "
            "ProMedica y en 2019 consultorios médicos por 1,250 millones. También vende: en 2019, "
            "el portafolio operado por Benchmark, por 1,800 millones. El dividendo se queda en 0.87 "
            "dólares por trimestre desde 2017. En 2019 los inmuebles operados ya generan 42.8% del "
            "NOI."),
        Era("Pandemia: el riesgo de operar", D(2019, 12, 31), D(2021, 12, 31),
            "El covid golpea de lleno a los inmuebles operados, que no tienen un contrato de renta "
            "que los proteja: la ocupación baja de 85.8% en febrero de 2020 a 74.4% en febrero de "
            "2021 y suben los costos. Welltower recorta 30% el dividendo, Shankh Mitra toma la "
            "dirección y en 2021, con la ocupación todavía baja, vuelve a comprar: 4,400 millones, "
            "3,100 de ellos en inmuebles operados. Ese año los operados dan 34.7% del NOI, contra "
            "42.8% en 2019."),
        Era("Tasas altas y el auge de los inmuebles operados", D(2021, 12, 31), D(2025, 10, 27),
            "El bono a diez años pasa de 1.5% a casi 5%, pero la ocupación de las residencias se "
            "recupera y Welltower emite acciones como nunca: más de 6,000 millones en 2023 y 7,500 "
            "millones en 2024. Con ese dinero compra inmuebles por 4,200 millones en 2023 y 5,700 "
            "millones en 2024, sobre todo operados, y disuelve sus sociedades con Revera. En julio "
            "de 2024 sube el dividendo por primera vez desde el recorte."),
        Era("Solo vivienda para mayores", D(2025, 10, 27), None,
            "Welltower anuncia 23,000 millones en operaciones: compra las carteras de Barchester y "
            "HC-One en el Reino Unido, cierra la de Amica en Canadá y vende casi todos sus "
            "consultorios médicos. Al 30 de junio de 2026 los inmuebles operados generan 70% del NOI "
            "y la deuda neta es menos de tres veces el EBITDA ajustado. Los cinco principales "
            "directivos aceptan cobrar casi solo en unidades de largo plazo de Welltower OP hasta "
            "2035. En julio de 2026 el dividendo sube 15%."),
    ),
    riesgos=(
        Riesgo("Opera, no solo renta",
               "70% del NOI depende de la ocupación y de lo que cuesta operar: en el 2T-2026 los "
               "sueldos fueron 59% de los gastos de los inmuebles operados comparables. Cuando la "
               "ocupación cayó de 85.8% a 74.4% en el covid, no hubo contrato de renta que "
               "amortiguara el golpe. Es la fuente del crecimiento reciente —el NOI comparable de "
               "esos inmuebles creció 20.5% en el 2T-2026— y también su mayor riesgo."),
        Riesgo("El motor de crecimiento depende del precio de la acción",
               "Welltower crece emitiendo acciones: 8,900 millones de dólares en 2025, 7,500 en 2024 "
               "y más de 6,000 en 2023. En 2025 compró inmuebles operados a un rendimiento inicial de "
               "6.8%. Mientras la acción valga mucho frente a ese rendimiento, cada compra suma flujo "
               "por acción; si el mercado deja de pagar ese múltiplo, el motor se frena."),
        Riesgo("Oferta nueva",
               "La vivienda asistida ya tuvo un ciclo de sobreconstrucción: a fines de los noventa "
               "se construyó de más, la ocupación tardó años en recuperarse y en 2003 quebró Alterra, "
               "que le rentaba 45 residencias. Si la construcción se reactiva con la ocupación alta, "
               "el crecimiento por ocupación y tarifas se debilita."),
        Riesgo("Tamaño, integración y personas clave",
               "En 2025 compró 949 inmuebles por 19,200 millones y en lo que va de 2026 lleva 15,500 "
               "millones cerrados o por cerrar: integrar a decenas de operadores en tres países es "
               "difícil. El programa de diez años ata a la dirección de Mitra hasta 2035: alinea "
               "intereses, pero concentra el riesgo en un equipo."),
        Riesgo("Pagos del gobierno",
               "Los asilos y centros posagudos —15% del NOI— reciben 49% de sus ingresos de Medicaid "
               "y 27% de Medicare, y la ley fiscal de 2025 prevé reducir Medicaid. En el Reino Unido y "
               "Canadá, 6% de los ingresos de los inmuebles operados viene de programas públicos. Un "
               "cambio de reembolsos ya quebró a cerca de 11% de los asilos de EE. UU. entre 1999 y "
               "mediados de 2000."),
        Riesgo("Divisa, para quien invierte en pesos",
               "La acción y el dividendo están en dólares, pero un tercio del NOI está en libras "
               "esterlinas y dólares canadienses (24% Reino Unido y 9% Canadá). Para quien invierte en "
               "pesos el riesgo es doble: el dólar contra el peso, y la libra y el dólar canadiense "
               "contra el dólar. Una apreciación del peso resta en la misma medida."),
    ),
    fuentes_extra=(
        ("Precio y dividendos desde 1993", "Yahoo Finance (chart API)."),
        ("FFO y la operación 1993-2025", "10-K, informe anual de 1995 y comunicados de resultados "
         "(8-K Ex-99.1 y suplementos Ex-99.2) de la SEC, uno por uno; ver "
         "data/estudios/WELL/anuales_primarios.csv."),
        ("Estados financieros 2008-2026", "XBRL de la SEC (companyfacts) y 8-K trimestrales."),
        ("Tasas", "Treasury a 10 años (FRED), Udibono, CETES y tipo de cambio FIX (Banxico)."),
        ("Historia corporativa", "10-K, 8-K, proxies e informe anual de 1995 en EDGAR (CIK 766704); "
         "suplemento del 2T-2026 (8-K Ex-99.2) para el perfil."),
    ),
    notas={
        "dividendos": (
            "El 28-dic-2006 pagó 0.3409 dólares prorrateados por la fusión con Windrose y en febrero "
            "de 2007, 0.2991: es un solo dividendo trimestral de 0.64 partido en dos, no un recorte. "
            "El único recorte desde 1993 es el de mayo de 2020, de 0.87 a 0.61."
        ),
        "apalancamiento": (
            "El emisor reporta deuda neta ÷ EBITDA ajustado de 6.37x al cierre de 2019 y 2.99x al 30 "
            "de junio de 2026: desde 2023 financió sus compras sobre todo con acciones."
        ),
    },
)
