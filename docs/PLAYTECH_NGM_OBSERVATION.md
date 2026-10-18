# Motor NGM demo: análisis integrado y ejecución

NGM offline genera resultados en el cliente oficial. Tester-Spin lo ejecuta en una sesión demo nueva y aislada con `real=0`; conserva explícitamente `local-client-engine` y `server_execution=false`. GPAS mantiene su transporte HTTP/WebSocket directo. No se ejecuta JavaScript extraído de HAR ni se reutilizan sus sesiones.

## Del HAR al motor

El analizador reconstruye las clases concretas, IDs y campos serializados del cliente y el manifiesto JMM. Resuelve controles heredados `@P/#ID` y conserva fuentes, hashes, referencias y declaraciones desconocidas. Las tablas matemáticas grandes permanecen en el HAR mediante referencias; no son opciones de compra.

`ngm_plan.py` transforma esa evidencia en `execution_plan`. No contiene nombres de juegos, IDs de catálogo ni una tabla de hashes aprobados. Reconoce un subconjunto explícito del protocolo y de los calculadores ya analizados; otras familias siguen pendientes hasta incorporar sus primitivas.

La ausencia de compras o antebets requiere conjuntamente:

- Lector enlazado que itera el mapa completo de modalidades de configuración.
- Esquemas y valores de configuración, controles y calculadores reconocidos, sin declaraciones económicas adicionales o anidadas.
- Registro de handlers vinculado al mismo mapa del dispatcher offline, sin altas dinámicas omitidas.
- Todos los mensajes concretos resueltos y sus campos económicos reconocidos. Un sobre windowId/ID/umid no demuestra por sí solo que el comando sea pasivo: debe carecer de handler.
- Un único emisor y punto de llamada de SpinRequest. El selector debe proceder del argumento enlazado sin sobrescrituras, transformaciones ni accesos adicionales; las opciones enum se vinculan a los campos de su constructor, sin reasignaciones posteriores.

Un resultado vacío completo se guarda como `DECLARED_EMPTY`, con `complete=true`, fuente y referencias. Cualquier controlador, campo, precio, calculador o selector no reconocido conserva `UNKNOWN`; no se inventan compras ni se deduce cero por no encontrar una palabra.

## Ejecución y cierre

El observador se instala antes de ejecutar el cliente oficial vigente. Enlaza SpinEvent, StartEvent y los estados de modalidad activa/pendiente y botón visible/habilitado mediante la estructura del código; no fija nombres minificados. Un retorno temprano sin handler también produce su par de observación, evitando desbalancear las peticiones anidadas.

Cada intento envía un único giro inicial. Una continuación gratuita exige ronda abierta, respuestas y premios del paso anterior resueltos, modalidad pendiente declarada free-spins, control start habilitado y ausencia de modales. No se reintenta una acción incierta; hay un límite de continuaciones y cualquier cobro adicional no declarado invalida la ronda. Un precio o elección sin contrato bloquea esta continuación automática.

La verificación financiera exige débito inicial observado, petición/respuesta/premio independiente por cada paso, saldo inicial menos apuesta más premios igual al saldo final, fin de ronda y permiso de volver a girar. Una ronda fallida detiene la sesión. Se prueba otra ronda normal como retorno a base.

Al cerrar la grabación, el motor analiza automáticamente `session.har`, incluso ante un fallo. Solo consume el plan si los hashes del cliente y el manifiesto coinciden con los de la sesión demo observada. Publica los dominios canónicos `purchase` y `ante`, que usa la grilla, y guarda `execution-plan.json`. Los resultados no dependen de importar manualmente un informe privado.

OK requiere plan completo, todas las rondas solicitadas verificadas y retorno a base. El finalizador común vuelve a comprobar cobertura y muestras. Cada intento tiene su carpeta `attempt-N/` con `step-N-request.json`, `step-N-response.json`, `wire-events.json` y `summary.json`; la identificación de ejecución local es alcance del resultado, no una advertencia que invalide una muestra correcta. Un bonus natural solo está verificado dinámicamente si apareció y cerró durante la prueba: OK no implica haber observado todo resultado aleatorio posible.

## Evidencia y validación

Cada ejecución conserva HAR, bootstrap, traza de eventos, contratos reconstruidos, plan, muestras financieras por intento y resultado. Las fuentes, capturas y trazas privadas quedan fuera de Git. El lector también puede ejecutarse offline:

```powershell
python -m tester_spin.providers.playtech.ngm_contracts captura.har --code CODIGO --out informe-ngm.json
```

El caso Heart of the Frontier reconstruye 13 formatos y 43 controles. La configuración declara cinco tiradas gratuitas; los avisos sí/no por cambios de apuesta con wilds persistentes no son compras. PickBonusRequest abstracto y respuestas genéricas compartidas no prueban una elección ejecutable. Las modalidades configuradas y las rutas enlazadas permiten declarar cero compras y cero antebets para este cliente, sin extender esa conclusión a todos los NGM.

La validación integrada del 2026-10-17 usó `PlaytechProvider.test_game`, una sesión oficial demo nueva y el finalizador común: dos rondas cerradas, resultado OK y conteos (0, 0). Pruebas negativas cubren hashes/manifiestos distintos, modo demo no confirmado, rondas abiertas, precios anidados, controles nuevos, calculadores desconocidos y selectores alterados. Los recorridos de bonus no observados siguen distinguiéndose de esta validación de entrada y retorno normal.


### Entrada estructurada CommonBet

Los clientes gamelet pueden entrar mediante un mensaje StartSpinRequest con un objeto CommonBet, en lugar del SpinRequest clásico. Se reconstruyen el serializador de stake/type, su único productor, el reenvío sin modificaciones y la conversión explícita de unidades. No se inventan numCoins ni selectores ausentes. Un emisor clásico adicional impide declarar vacío el inventario económico.

OpenGame, DisplayJackpot, FinishSpin y CommonSaveState solo se clasifican por esquema completo, relación con la entrada y título fijo enlazado. El observador registra los mensajes que produce el cliente; no los fabrica ni reproduce desde el HAR. FinishSpin requiere respuesta y premio resueltos. Los objetos de datos que heredan de Object se distinguen de los comandos que heredan de RequestMessage.

Adventures Beyond Wonderland permitió comprobar esta primitiva: dos rondas normales cerradas de coste 30, premio 0 y saldo conciliado. Sus tablas ponderadas de símbolos y premios no son compras. Las modalidades gratuitas y sus elecciones mantienen los mismos límites de cobertura dinámica descritos arriba.


## Qué demuestra un HAR y cómo volver a capturar

Adjuntar un HAR a una conversación permite analizar ese archivo. No lo instala en
Tester-Spin, no cambia resultados anteriores y no acredita rondas nuevas. El
comando offline anterior reconstruye contratos y publica `capture_diagnostics`;
`request_count` cuenta **formatos declarados en el cliente**, no giros ejecutados.
Su informe conserva `certifies_game_ok=false`.

El botón **Ejecutar y capturar** de controles manuales guarda el HAR y pasa por
`har_learning.isolate_capture`. Ahora comprueba primero la estructura y los
contenidos del archivo: una captura vacía produce `HAR_EMPTY_CAPTURE`, incluso
si Aislador no está instalado. Para NGM muestra los recursos faltantes y las
necesidades de evidencia local. Si Aislador está configurado, su extracción sigue
siendo un paso externo opcional; el resultado del filtrado incluye este mismo
diagnóstico y la interfaz lo muestra. Ni el filtrado ni el análisis estático
actualizan automáticamente la cobertura de Playtech ni reproducen la sesión.
La prueba del adaptador usa una sesión demo nueva y su propio `session.har`.

Para un HAR utilizable por el analizador:

1. Iniciar la grabación antes de cargar o recargar la demo oficial, conservar el
   registro al navegar y desactivar la caché durante la captura.
2. Capturar sin filtros que excluyan JavaScript, HTML o manifiestos. Exportar con
   cuerpos de respuesta, incluyendo el `.cache.js` y el `.jmm` del juego y de la
   misma versión. Un manifiesto solo no permite reconstruir sus serializadores.
3. Capturar la acción y esperar el cierre de la ronda y que vuelva a habilitarse
   el giro. Si el juego usa red, conservar peticiones y respuestas completas y
   tramas WebSocket con dirección y orden, no solamente el handshake HTTP 101.
4. Para **NGM offline**, ejecutar también la prueba demo de Tester-Spin y
   conservar su directorio de ejecución. Los giros pueden resolverse dentro del
   cliente sin emitir una petición de red; un HAR no registra por sí mismo esa
   ejecución local. Hace falta la traza de ciclo de vida, el débito, la entrada,
   la respuesta, el premio, los saldos y el permiso de volver a girar.

La nueva salida por intento conserva las peticiones observadas al dispatcher y
sus retornos reales en pares `step-N-request.json` / `step-N-response.json`.
Las llamadas auxiliares anidadas se asocian por la pila del dispatcher y no
sustituyen la respuesta de giro. Los archivos identifican explícitamente
`official-local-demo`, `server_execution=false`, hashes del cliente y el índice
de evento. `summary.json` contiene el resumen financiero: ya no se presenta como
una respuesta del juego. `wire-events.json` guarda los valores de ciclo de vida y
financieros que aceptó el ledger durante ese intento; `ngm-events.jsonl` conserva
además la traza general de la sesión.

El árbol vuelve a comprobar el ledger a partir de esos eventos, su concordancia
con el resumen, los pares y la cantidad de pasos. Un par ausente, un saldo que no
concilia, falta de inicio/cierre o una traza ausente impiden `VALIDATED`. Esto
corrige un caso donde rondas locales correctas parecían incompletas porque el
formato anterior solo guardaba un resumen llamado `response.json`. Las capturas
anteriores no se convierten en pares inventados; requieren nueva evidencia.

### Capturas revisadas el 2026-10-18

| Captura | Evidencia disponible | Evidencia pendiente |
| --- | --- | --- |
| Adventures Beyond Wonderland, exportación 20:55 | `log.entries` vacío: 0 peticiones y 0 tramas | Recaptura completa; el archivo no permite recuperar ningún giro |
| Mighty Midas (`aogmt`, cliente 26.9.3), exportación 21:39 | 44 entradas; manifiesto del juego; cuatro tramas de lobby: conexión, consulta de enlaces, respuesta de enlaces y desconexión | No contiene `.cache.js` ni observación de rondas locales; falta fuente de la misma versión y ejecución instrumentada |

En Mighty Midas la extensión real es `_webSocketFrames` con `payloadData` y
`direction`; no `_webSocketMessages`. El diagnóstico acepta también la variante
`_webSocketMessages` con `data` y `type=send/receive`, y el formato histórico
`log._warpWebSockets`. La lectura de esas extensiones permite explicar el
contenido; no convierte conexión, navegación o keepalive en apuestas. Las
tramas desconocidas permanecen sin clasificar, sin acreditar rondas.

El HAR de Mighty Midas demuestra que falta evidencia suficiente, no que el
usuario no haya girado. Su manifiesto declara además características y
calculadores que el plan conservador aún no resuelve. Incorporar el JavaScript
faltante permite estudiarlos, pero no garantiza automáticamente cobertura total.
Los archivos originales se conservan; los tests del repositorio usan ejemplos
mínimos sintéticos, sin clientes descargados ni sesiones privadas.
