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

OK requiere plan completo, todas las rondas solicitadas verificadas y retorno a base. El finalizador común vuelve a comprobar cobertura y muestras. Cada intento tiene su carpeta `attempt-N/response.json`; la identificación de ejecución local es alcance del resultado, no una advertencia que invalide una muestra correcta. Un bonus natural solo está verificado dinámicamente si apareció y cerró durante la prueba: OK no implica haber observado todo resultado aleatorio posible.

## Evidencia y validación

Cada ejecución conserva HAR, bootstrap, traza de eventos, contratos reconstruidos, plan, muestras financieras por intento y resultado. Las fuentes, capturas y trazas privadas quedan fuera de Git. El lector también puede ejecutarse offline:

```powershell
python -m tester_spin.providers.playtech.ngm_contracts captura.har --code CODIGO --out informe-ngm.json
```

El caso Heart of the Frontier reconstruye 13 formatos y 43 controles. La configuración declara cinco tiradas gratuitas; los avisos sí/no por cambios de apuesta con wilds persistentes no son compras. PickBonusRequest abstracto y respuestas genéricas compartidas no prueban una elección ejecutable. Las modalidades configuradas y las rutas enlazadas permiten declarar cero compras y cero antebets para este cliente, sin extender esa conclusión a todos los NGM.

La validación integrada del 2026-10-17 usó `PlaytechProvider.test_game`, una sesión oficial demo nueva y el finalizador común: dos rondas cerradas, resultado OK y conteos (0, 0). Pruebas negativas cubren hashes/manifiestos distintos, modo demo no confirmado, rondas abiertas, precios anidados, controles nuevos, calculadores desconocidos y selectores alterados. Los recorridos de bonus no observados siguen distinguiéndose de esta validación de entrada y retorno normal.
