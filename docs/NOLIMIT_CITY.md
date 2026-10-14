# Nolimit City: catálogo y ejecutor Demo

Proveedor integrado: `nolimit_city` / **Nolimit City**.

El catálogo oficial de afiliados contiene 140 demos del estudio en el corte del
2026-10-13. Fuente: https://nolimitcity.com/json/games.json. El enlace documentado
https://nolimitcity.com/json/affiliateGames.json redirige a ese feed.
Página pública: https://nolimitcity.com/games.

Cada fila usa name, code, studio y url. Solo se incorporan filas studio=Nolimit City;
no se atribuyen a este proveedor los juegos de otros estudios de Playin/Evolution.
code es la identidad de lanzamiento, symbol conserva su capitalización y slug
usa su forma normalizada. El enlace oficial es playin.com/embed/v1/demo/<code>.
Cambios de título no alteran esa identidad. Duplicados, colisiones de identidad,
enlaces de otro origen, nombres vacíos y catálogos vacíos se rechazan.

El snapshot incluido permite cargar el catálogo sin red. Una actualización en
línea agrega o actualiza registros sin borrar juegos existentes; este feed no
tiene autoridad de eliminación. No se inventan URLs de miniaturas: el feed no
las suministra. Los enlaces de demo permiten abrir el juego desde la grilla.

## Estado de ejecución

El ejecutor abre una sesión Demo nueva mediante FANPAGE_DEMO, obtiene la versión
actual del cliente y la clave temporal, y usa el transporte RC4/LZW observado.
No reutiliza la sesión del HAR. Airport Security completó en una sesión nueva
las cuatro compras, las tres apuestas mejoradas y el retorno al giro normal.
Esto valida las primitivas compartidas, no certifica los otros 139 juegos.

Para cada sesión se contrastan la tabla de precios, los selectores permitidos,
las apuestas por selector y la habilitación del servidor. El programa usa la
apuesta mínima declarada; un saldo Demo insuficiente queda explicado como PARCIAL.
Las opciones FREESPIN son PURCHASE y las BOOSTED_BET son FEATURE_SPIN. Estas últimas
se muestran como apuestas mejoradas; el nombre o el precio no permiten convertirlas
en antebets ni compras. La cantidad de antebets sigue sin confirmar si no existe
una declaración de ese papel. Los tipos o additionalTypes desconocidos conservan
su identidad y bloquean OK.

Cada ronda comprueba apuesta base, coste cotizado, acumulación de premios y saldo
al pagar y liquidar. La continuación conocida es zeroBet dentro de FREESPIN,
FREESPIN_BETTER o FREESPIN_SUPER, con contador positivo y sin menú de decisiones.
El cierre exige nextMode=NORMAL, freespinsLeft=0 y features.available=[].
Tras recorrer todas las opciones, se requieren dos rondas normales consecutivas
cerradas; una activación natural reinicia ese contador. No hay excepciones por ID.

Una elección, extra spin o modo de continuación todavía desconocido queda PARCIAL,
con sus respuestas y capture.har guardados en la carpeta de prueba. La espera de
WebSocket tiene plazo y atiende Detener; una apuesta incierta nunca se reenvía.
El HAR local contiene la clave temporal necesaria para decodificar su conexión y
no se publica. Los JSON de diagnóstico y el contrato exportado eliminan credenciales.
El contrato farm exige la evidencia monetaria y de retorno de la ejecución actual.

El proveedor aparece en el selector del escritorio y en el registro del ejecutor
por lotes. El catálogo se incluye en la compilación del ejecutable completo.


## Primer protocolo observado: Airport Security

La captura suministrada incluye las jugadas en log._warpWebSockets, fuera de
log.entries. POST https://demo.nolimitcity.com/EjsFrontWeb/fs devuelve la URL
HTTPS /EjsGameWeb/gs y una clave de sesión. El cliente adjunta ?data=<clave>,
cambia https por wss y /gs por /ws/game. La clave no se fija en el programa.

Las peticiones son JSON cifrado con RC4 y expresado en hexadecimal. Las respuestas
son JSON con compresión LZW indicada por lzw:. Se contrastó la transformación
con GameCommunication y SocketAdapter del cliente incluido en el mismo HAR.
El lector valida la conexión correspondiente, los códigos LZW y sus límites de
expansión; no interpreta recursos gráficos ni peticiones de analítica como apuestas.

El sobre lleva type=normal, protocol, id y data. El comando está en content:

- normalBet: apuesta normal en bet.
- featureBet: bet es la apuesta base; featureName y playerInteraction.featureName
  seleccionan la opción. El débito real usa el multiplicador declarado.
- zeroBet: continuación de la ronda con bet=0.00; no es una compra nueva.

La inicialización declara game.featureBuyTimesBetValue (name, type, price),
allowedFeatureBets y featureBetLevels. En esta muestra hay cuatro compras de tipo
FREESPIN (80x, 240x, 500x y LUCKY_DRAW 212x) y tres opciones de tipo BOOSTED_BET
(1.4x, 12x y 4500x). LUCKY_DRAW es una sola opción aunque otorgue distintos premios.
Los boosted bets no se cuentan como compras ni se reclasifican automáticamente
como antebets o Action Spins. Su tipo y sus precios proceden del servidor.

La respuesta confirma wasFeatureBuy/wasBoostedBet, playedBetValue, win,
accumulatedRoundWin, nextMode, freespinsLeft, features.available y balance.
El id enlaza cada petición con su respuesta; no es por sí solo un identificador
de ronda. Los saldos intermedios pueden omitirse durante las tiradas gratuitas.
El cierre observado exige nextMode=NORMAL, freespinsLeft=0 y ausencia de elecciones.

Se decodificaron 102 mensajes: 51 intercambios, incluida la inicialización.
Las 14 rondas pagadas y 36 continuaciones están cerradas y contabilizadas:
10000.00 de saldo inicial - 10273.80 de coste + 2756.05 de premios = 2482.25.
Todos los siete selectores anunciados aparecen en la muestra. Solo existe un giro
normal al final: esta captura no prueba dos rondas posteriores ni certifica OK
en una sesión nueva. La validación en vivo es independiente de esta captura.

## Analizador offline

```powershell
.\.venv\Scripts\python.exe tools/analyze_nolimit_har.py "ruta\captura.har" --output "ruta\informe.json"
```

El informe conserva precios, cargos, pagos, selecciones y cierres; no exporta
claves de sesión ni reproduce tráfico. El HAR original y las claves permanecen
locales bajo data/. Las pruebas incluyen mensajes reducidos sin credenciales y
casos negativos de precio, identidad y compresión. No hay ramas por título o ID.


## Respuesta enhancedBet y bonos de dos etapas

El HAR de Apocalypse Super xNudge (14/10/2026) prueba otra estructura de respuesta.
Se reconoce por el conjunto de campos thisSpinWinning, totalSpinWinnings,
enhancedBet, featureName, firstStage, secondStage y secondStageFsLeft; no por el
nombre del juego. El premio por paso proviene de thisSpinWinning, contrastado con
accumulatedRoundWin y el saldo de liquidación. enhancedBet confirma la categoría
de apuesta mejorada; si también existe wasBoostedBet ambos deben coincidir.

En esta estructura, features.available puede conservar exactamente el conjunto
init.allowedFeatureBets durante todas las rondas. Ese catálogo no constituye una
elección pendiente. La excepción requiere la estructura completa y coincidencia
exacta; no aplica a respuestas modernas ni a opciones nuevas/subconjuntos.

Cuando firstStage=true, secondStage=false, freespinsLeft=0 y secondStageFsLeft>0,
un zeroBet sin cargo avanza a la segunda etapa del modo free spin reconocido.
Un contador de segunda etapa pendiente impide declarar cierre en NORMAL.
SUPER_FREESPIN es una variante observada de continuación gratuita.

La captura contiene 37 rondas pagadas cerradas y 103 continuaciones. Su conexión
incompleta queda separada del análisis de la sesión con init. El lector también
acepta entry._webSocketFrames; en capturas late-attach puede leer la clave del URL
WebSocket capturado, sólo para descifrar offline, sin reutilizar esa sesión.
Los mensajes de regresión están recortados y sus identificadores anonimizados.
La nueva prueba Demo independiente completó las cuatro compras, las dos apuestas
mejoradas y los dos giros normales de retorno, y recibió OK del pipeline completo.
No se transforma un HAR por sí solo en una certificación OK.


## Detección y ejecución de las variantes de respuesta

Las opciones de init se conservan después de contrastar sus tipos, precios,
selectores y dominios de apuesta, antes de validar el estado inicial. Un estado
sin primitiva aprendida conserva el conteo y permanece PARCIAL sin apostar.
Esto evita mostrar cero compras cuando el catálogo del servidor sí las declara.

El perfil de categorías de free spins se reconoce por featureBet,
numberOfFreespinsPlayed, totalSpinWinnings, freespinTriggeredThisSpin,
wasFeatureBuy, playedBetValue, accumulatedRoundWin, mode, nextMode y freespinsLeft.
features.available=["FREESPINS"] describe una categoría que persiste en giros
normales y durante todo el bono; no es un menú de elecciones. Se admite solo
esta lista exacta y esta estructura. featureBet=false es normal o continuación;
featureBet=true se admite solo junto a wasFeatureBuy=true al entrar desde NORMAL
con cero free spins jugados. Cualquier opción adicional queda sin interpretar.

En la inicialización de este perfil, la lista de categorías no bloquea el giro
si el servidor declara isRestoreState=false, mode/nextMode=NORMAL, ningún free spin
pendiente o jugado, freespinTriggeredThisSpin=false y wasFeatureBuy=false.
Una restauración o contador pendiente sigue bloqueando el ejecutor.

En el perfil boostedBet se contrastan sus valores booleanos con wasBoostedBet si
ambos están presentes. En estos dos perfiles probados, totalSpinWinnings es premio
por paso y sustituye win; si ambos están presentes deben coincidir. La suma debe
coincidir siempre con accumulatedRoundWin. wasExtraSpin es un acuse opcional en
estas estructuras; su ausencia no inventa un extra spin. Un valor explícito distinto
de false se rechaza. Fuera de los perfiles aprendidos no se completan estos campos.

Además de las continuaciones free spin conocidas, el perfil boostedBet usa zeroBet
para RESPIN con respinsLeft entero positivo, y para FREESPIN_MINIGAME con
freespinsLeft entero positivo. No se avanza con contadores inexistentes o cero.
Un contador respinsLeft pendiente impide certificar cierre en NORMAL.

La comprobación del 14/10/2026 recorrió las dos compras de Bushido Ways, las tres
compras y tres apuestas mejoradas de Bangkok Hilton, y las tres compras y cuatro
apuestas mejoradas de Brute Force, con cargos, premios acumulados, liquidación y
dos giros normales de retorno. Las muestras reducidas de regresión no contienen
sesiones ni credenciales. Son primitivas por estructura, sin excepciones por ID.


## Registro de la tanda del 14/10/2026

La tanda suministrada fue detenida al iniciar el juego 30 de 135; no era una prueba
terminada del catálogo. Varios PARCIAL eran errores de interpretación compartidos.
En perfiles monetarios reconocidos, features={} o features.active="" sin available
no constituye una elección. available puede ser el catálogo completo de selectores,
el catálogo completo de compras o las categorías BONUS_BUY/BOOSTED_BET derivadas
de los tipos de las opciones permitidas en init. La comparación es exacta, sin
duplicados; subconjuntos arbitrarios y elementos nuevos siguen bloqueados.
Las categorías y selectores se exportan como parte del contrato de cada modo.

Se reconocen enhancedBet booleano o enum entero no negativo, boostedBetPlayed y
las variantes del contador freeSpinsPlayed/numberOfFreespinsPlayed. Los acuses
coexistentes deben concordar. El premio por paso usa thisSpinWinning o
thisSpinWinnings cuando aparecen; totalSpinWinnings puede ser acumulado por giro,
por lo que no sustituye esos campos. La conciliación acumulada y de saldo permanece.

features.active describe una fase. FREE/SUPER identificados por el servidor y
STACKED_RESPIN_FS/RESPIN solo se aceptan en su contexto de continuación aprendido.
Las avalanchas con premio pendiente y estado de carretes conocido usan zeroBet;
las fases de respin de avalanche también requieren coste adicional cero y ausencia
confirmada de extra spin. Una fase o decisión nueva sigue PARCIAL.

### Elecciones declaradas por cliente y confirmadas por servidor

Ante una fase sin continuación automática, el ejecutor consulta una sola vez el
game.js de la versión que abrió la Demo. Solo extrae configuraciones acotadas:
ASBonusPickOptions.PICK_MODE con IDs estáticos, o automaticPickGame con selectPick
que elige posiciones de un array del servidor cuyo valor -1 significa pendiente.
No ejecuta JavaScript ni deduce IDs por nombre del juego. En el array se contrasta
el límite literal de randomIntInRange(0,N) con su longitud N+1.

El comando aprendido es zeroBet, bet=0.00 y playerInteraction.selectedIndex como
cadena. La respuesta debe confirmar playerSelect, o modificar la posición pendiente
del array manteniendo su longitud y las posiciones anteriormente seleccionadas.
Además, el ledger debe aceptar el resultado monetario. Se registran dominios y
opciones cubiertas por compra; se repite la raíz si faltan elecciones, con límite
de 16 repeticiones adicionales, presupuesto Demo y límite global de tiempo.
El contrato exporta el comando de selección y no está listo con elecciones pendientes.

Las nuevas pruebas completas dieron OK para Barbarian Fury, Beheaded, DDay,
Dead Canary y Deadwood R.I.P. La verificación original de Bushido, Bangkok y
Brute Force permanece cubierta por regresiones de rondas cerradas. Esto no
certifica automáticamente los otros juegos del catálogo.

### Pendientes reales

BrickSnake 2000 tiene una decisión GAMBLE_FIFTY_FIFTY. El cliente publica una política
automática constante, que no es un dominio completo de elecciones ni un contrato
de cobro. No se asume que esa selección sea collect: la muestra observada duplicó
el premio. Hace falta una primitiva explícita para su menú completo y el ledger
del gamble antes de certificar esa fase.
Disorder llega a EXTRA_SPIN_CHECK. No se acepta ni se cancela un extra spin sin
su contrato de precio y decisión. Casino Win Spin/Coins of Fortune y las identidades
o versiones de cliente no reconocidas también conservan sus diagnósticos propios.
No se necesita repetir un HAR para diagnosticar estos estados: las respuestas
de las pruebas Demo quedan guardadas en data/providers/nolimit_city.
