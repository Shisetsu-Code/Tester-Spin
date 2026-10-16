# BGaming HTTP v2: apuesta nominal y efectiva

Burning Chilli X y Royal Fruits MultiLines comparten una conversión cliente
explícita: additionalSpinOptions.mode recibe this.linesCount; una tabla numérica
mapea 20/40/60/80/100 a 1/2/3/4/5. El cliente compara outcome.bet con getBet()
multiplicado por esa tabla y divide outcome.bet por la misma tabla para restaurar
la apuesta nominal. Los bundles públicos versionados de profile.json respondieron
HTTP 200. El init tiene cien líneas; el factor tres no procede de contar líneas.

El análisis ahora reconoce exclusivamente esa relación, conserva la apuesta wire
nominal y pasa el selector demostrado al perfil. No infiere dominios exhaustivos
ni costos a partir del balance. Los RAW existentes con bet=20 y mode=60 declaran
outcome.bet=60; el perfil corregido espera 60 para apuesta efectiva y validación.
No se repitieron partidas ni se modificó SQLite. Tres regresiones nuevas más
runtime/profile: 56 pruebas correctas; el caso de extracción falló antes del fix.

Big Boat Big Catch, Kraken's Hunger y Loki Loot comparten otra declaración
cliente comprobada en sus bundles públicos actuales (HTTP 200): initBuyFeatures
lee options.feature_options.feature_multipliers y divide los valores por
base_bet || 100. El extractor ahora sigue esa relación exacta, no presume un 100
global. Pasa el fallback demostrado por wire/profile (también persistido) al
cálculo de compras del ejecutor. Rechaza defaults contradictorios y reasignaciones.
El init conserva autoridad: base_bet positivo publicado gana al fallback; sólo
ausencia/null/cero permite el default probado; negativos permanecen desconocidos.

Combinando cliente con los RAW de init existentes se demuestran multiplicadores:
Big Boat 100 y 1.5; Kraken 120/200/300 y 1.4/3/6; Loki 75 y 1.5. No se deducen de
débitos ni se declara una compra validada. Las sesiones actuales, errores 422 y
los selectores de nivel necesitan su verificación separada.
