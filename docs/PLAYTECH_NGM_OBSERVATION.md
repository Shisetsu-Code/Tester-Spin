# Motor NGM demo: observación y ejecución

NGM offline genera respuestas y calcula premios dentro del cliente oficial. No es GPAS ni una ejecución verificada por servidor. La ruta `ngm-offline` mantiene Chromium porque este motor local necesita ejecutarse; GPAS conserva HTTP/WebSocket directo.

## Contrato derivado

`ngm_observation.py` analiza estáticamente el cliente vigente, sin evaluar JavaScript de HAR ni conservar nombres minificados o listas de juegos:

- Vincula la clase declarada `SpinRequest`, su constructor y su serializador con los campos reales de `bet`, `numCoins` y `spinType`.
- Reconoce el despachador por la relación callback de petición → acumulación de respuestas → colección retornada. No presupone el nombre minificado del callback.
- Encuentra la cadena colección de pagos → suma → crédito → resultado para observar el premio calculado independientemente del saldo.
- Vincula el evento declarado `SpinEvent` con el despachador usado por la interfaz. Un punto de depuración sin pausa obtiene una referencia a esa acción en el cliente recién cargado; no reconstruye ni reproduce un payload histórico.
- Rechaza vínculos ausentes o ambiguos.

## Ejecutor integrado

`ngm_runtime.py` abre una sesión oficial aislada con `real=0` y `preferedmode=offline`; exige `IUserDataResponse.mode=demo`, carga terminada, escena game, saldo, apuesta y regulaciones de teclado. Si la introducción splash está declarada visible, envía una única tecla para cerrarla y espera la confirmación explícita. Cualquier giro inesperado fuera de una ronda envenena la sesión.

Cada intento envía exactamente un `SpinEvent`. No reenvía una apuesta incierta. `NGMRoundLedger` exige:

1. Inicio de ronda y petición normal con importes enteros válidos.
2. Débito de apuesta observado, respuesta local y premio calculado para cada paso.
3. Las continuaciones free observadas tienen coste cero; tipos nuevos y comandos sin contrato quedan pendientes.
4. Saldo final = saldo inicial − apuesta + premios calculados.
5. Fin de ronda, `NextGameRoundAllowed` y cliente libre antes de otra apuesta.

Al terminar las repeticiones se valida otra ronda normal. Detener, timeout, captura incompleta, comandos desconocidos y errores de sesión impiden continuar. Una ronda fallida no se reintenta. Los resultados etiquetan expresamente `local-client-engine` y `server_execution=false`.

## Estado y evidencia

El inventario completo de compras y antebets NGM todavía es UNKNOWN: no se deduce su ausencia de estas tiradas ni de cadenas ausentes. Por eso el juego conserva PARCIAL con `NGM_FEATURE_INVENTORY_UNKNOWN`, aunque sus rondas normales estén verificadas. Esto no certifica límites de pago, bonus o elecciones especiales.

En `analysis/runs/<ejecución>` se guardan `session.har`, `bootstrap.json` con hashes y vínculos, `ngm-events.jsonl`, resúmenes financieros por ronda e intento y `result.json`. Son evidencia privada, fuera de Git. El observador auxiliar usa las mismas primitivas.

Validación real 2026-10-17: Heart of the Frontier, sesión demo nueva, tres rondas normales de coste 20, premios 9 / 140 / 0 y saldos 100000 → 99989 → 100109 → 100089. Todas cerraron y permitieron el siguiente giro. Una auditoría posterior de esos eventos también pasó la exigencia explícita de débito. No equivale a una corrida del catálogo ni a validar un bonus completo.

## Reconstrucción automática desde el HAR

`ngm_contracts.py` complementa la extracción de Aislador: usa los cuerpos del cliente y del JMM que permanecen en el HAR. Funciona offline, no ejecuta los scripts capturados, no hace red y no reutiliza identificadores de sesión.

```powershell
python -m tester_spin.providers.playtech.ngm_contracts captura.har --code CODIGO --out informe-ngm.json
```

El informe vincula las clases de petición con sus constructores, identificadores y serializadores, incluidos campos escalares y listas. Conserva las declaraciones cuyo formato no se entiende como pendientes. Separa mensajes de plataforma mediante el namespace declarado de PlatformRequest y clases abstractas mediante su registro sin constructor; no los cuenta como apuestas.

El manifiesto conserva modalidades y opciones sin convertir botones o nombres en compras. Los controles relevantes incluyen referencia a su nodo original. Las tablas grandes de rodillos y pesos pasan a referencias con hash; siguen en el HAR para reconstruir la matemática cuando corresponda. Las escrituras dinámicas, las delegaciones sobre el objeto de salida y los cuerpos incompletos impiden considerar completo un serializador.

Tester-Spin aplica el mismo lector a la sesión oficial vigente y guarda `client-contracts.json`. Después de cerrar el contexto y terminar la grabación, analiza automáticamente `session.har`, genera `ngm-har-contracts.json` y contrasta el hash del código con el cliente observado. Esto también sucede cuando el intento termina PARCIAL o falla; una fuente ausente, incompleta o distinta queda explícita.

Solo se observan pasivamente las preferencias y el inicio de bonus con serializadores completos dentro del contrato revisado. Un inicio de bonus requiere una ronda abierta con giro previo. No se envía ese comando desde el informe ni se asume que carece de coste por no llevar un precio: el débito inicial y el saldo final siguen comprobándose, y cualquier cobro extra sin contrato impide verificar la ronda. Las peticiones anidadas se emparejan mediante una pila para no atribuir la respuesta de preferencias al giro.

La instalación de los vínculos ocurre antes de ejecutar el script del cliente, evitando depender de un evento de interfaz que ya pudo haber sucedido durante la carga.

Validación adicional: el HAR de Heart of the Frontier permitió reconstruir 11 formatos concretos sin campos de serialización pendientes; la clasificación económica y el inventario completo continúan UNKNOWN. Otra sesión demo nueva completó dos rondas, recuperó automáticamente los mismos 11 formatos y el manifiesto. Esto no prueba una compra o bonus completo ni amplía el estado OK.


## Continuación gratuita y controles heredados

El lector resuelve `@P/#ID` con procedencia de cada plantilla, límites de profundidad y pendientes explícitos para referencias ausentes o ciclos. Incluye botones heredados y variantes; no suma sus apariciones como compras. Los mensajes concretos se identifican también por su herencia de `AbstractGameRequest`, aunque su nombre no termine en Request. Los IDs indirectos exigen constructor, inicializador y tabla de enumeración inequívocos; los mensajes no resueltos siguen pendientes.

El ejecutor enlaza el evento oficial `StartEvent` mediante su clase y dispatcher. Solo lo envía dentro de una ronda abierta y financieramente resuelta hasta ese paso, cuando la cima de la misma pila de modalidades señala una modalidad pendiente declarada `free-spins` y su botón activo `start` está visible y habilitado, incluido el estado del contenedor. Un modal, una modalidad desactivada, declaraciones de precio o elecciones impiden esta continuación automática. No se usa el nombre del juego ni campos minificados fijos. Cada paso admite un único envío, sin reintentos inciertos, con máximo de 20 continuaciones por ronda y registro `continuations.json`.

Un sobre con windowId/ID/umid no demuestra que el comando sea pasivo. Para mensajes adicionales sin formato de apuesta solo se tolera la ausencia de handler observada en el propio dispatcher offline, dentro de una ronda abierta. Si existe un handler, el mensaje sigue desconocido. Se capturan tanto el retorno temprano vacío como el retorno normal para mantener el emparejamiento de peticiones y respuestas. Cualquier descenso adicional de saldo después de recibir una respuesta invalida el contrato de continuación gratuita, aunque después el saldo final se reconcilie.

En el HAR de Heart of the Frontier estas reglas recuperan 13 formatos y 43 controles, frente a los 11 formatos y 15 controles anteriores. Dos formatos adicionales son notificaciones del bonus sin datos de coste; no se cuentan como compras ni elecciones. La declaración abstracta de un selector tampoco demuestra que exista una elección ejecutable. El inventario completo de compras/antebets y las opciones con precio permanecen UNKNOWN hasta vincular su autoridad y comportamiento; estas mejoras no convierten por sí solas el resultado en OK.


La entrada al bonus puede conservar `regular` como modalidad activa hasta pulsar inicio. Por eso se distinguen modalidad activa y pendiente: ambos accesores se vinculan a la misma pila del cliente, y se conserva ese estado en `continuation-state.json`. No se deduce la entrada al bonus solo de que el botón se llame start. El estado habilitado se consulta mediante los campos derivados de las reglas de visibilidad y estilo disabled del propio cliente; no se llama por nombre a una función declarada como método, que podría no existir en el ámbito global del cliente.


Validación de esta revisión (2026-10-17): una sesión demo nueva cerró 40 rondas normales con saldo reconciliado. V8 resolvió los puntos de petición y ambos retornos en columnas distintas (58, 64 y 128). En esa sesión no apareció un bonus: el recorrido automático completo de entrada, giros gratuitos y salida todavía no queda certificado por una ejecución real. Las sesiones anteriores sirvieron para reproducir y corregir el bloqueo de entrada (regular activa, start habilitado), y no se presentan como pruebas exitosas del bonus. Pasaron 63 pruebas enfocadas en NGM y 231 de Playtech/transporte/cobertura. HAR, fuentes y trazas privadas permanecen fuera de Git.
