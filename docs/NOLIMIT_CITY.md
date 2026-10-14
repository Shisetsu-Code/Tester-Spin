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
