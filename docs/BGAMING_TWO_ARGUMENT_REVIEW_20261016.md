# BGaming: forwarding de req y state_lock

La revisión de Chicken Fire confirmó una limitación del extractor: el cliente
actual pasa req y state_lock como argumentos separados a un wrapper expression
arrow, y éste reenvía req sin modificar a un transporte JSON-RPC /api. El
extractor anterior sólo reconocía un wrapper de un argumento con spread anidado.

El bundle público actual assets/index-CoAzB5sA.js devolvió HTTP 200 y su SHA-256
comienza por 3447e6d2577faf09, coincidente con engine_sha256 de la ejecución
2026-10-12_23-21-12-bgaming-hyperhive-jsonrpc. El nuevo análisis sigue la asignación
local request=builder(), la llamada play(request,state.lock), el retorno del
builder con bet y el transporte method/params. Conserva únicamente la prueba base
y el literal de bet_type normal demostrado; no autoriza campos de compra de
modificadores independientes. Rechaza cambios de alias, transporte, constructor,
comentarios, strings, reasignaciones incompatibles y sombreado. Los collectors
que incluyen dos veces exactamente la misma definición conservan la evidencia.

Las otras seis entradas CONTRACT_UNRESOLVED corresponden a árboles distintos:
Grand Patron y Keepers Of The Secret usan f/b y main versionados; Mystic Reels
usa build/platform; Recycle Riches usa main.js; Sugar Mix usa un main webpack;
Sweet Samurai usa index.js. No se declara resuelto su protocolo por semejanza.
Tampoco se han resuelto los RPC 51100 ni la escala de apuesta HTTP v2.

Validación: regresión RED antes del cambio; 24 pruebas focales y adyacentes
correctas. La extracción sobre el bundle público completo, simple y duplicado,
produce req con bet y bet_type bet. Esto demuestra descubrimiento, no una partida
validada: no se cambió SQLite ni se certificó ningún juego como OK.
