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
