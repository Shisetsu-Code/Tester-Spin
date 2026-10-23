# Playtech: primitivas ejecutables — ampliación del 23/10/2026

## Evidencia que originó el cambio

Auditoría de 76 juegos/111 recorridos. Sólo 6 recorridos GPAS mostraron 15 comandos GameCommand correlacionados; 14 respuestas terminaron una ronda y una respondió con `gameRoundClosed=false`, `nextRound=FreeGame`, `playStack[{round:FreeGame,modeType:LIST_PICK,remainingPlayCount:8}]` sin `listPickPlayerPickOptions`. Los 82 recorridos NGM del fuzzer mostraron tráfico de navegación de URLs, no comandos locales de juego. Una ausencia en el HAR del fuzzer no prueba ausencia de ejecución NGM.

## Modificaciones del código

**GPAS — `runtime.py`:** el primer comando originado desde la API GLU del cliente ahora se vincula al `correlationId` del request saliente capturado. Se ignoran respuestas de otras operaciones. Una solicitud con resultado incierto deja la sesión inutilizable para nuevos comandos. Para posteriores envíos directos se exige también una respuesta inequívocamente correlacionada.

**GPAS — `gpas_continuation.py`:** `ContinuationPlanner` obtiene `nextRound`, `playIndex`, `modeType` y `remainingPlayCount` del estado vivo. Para FreeGame de modo LIST_PICK sin opciones publicadas envía una continuación sin `pick`, nunca un índice supuesto. Si el servidor ofrece opciones, se requiere el `pick` del contrato actual. Se bloquean estado no reconocido, fase ambigua, ausencia de progreso, elecciones incompatibles y agotamiento de pasos. Cada continuación queda registrada; la compra no está cerrada hasta que se verifican estado terminal y contabilidad.

**GPAS — `adapter.py` y `primitives.py`:** el planificador se usa en cada continuación y registra `continuation-plan.json`. El ledger rechaza `gameData.stake` diferente del coste comprometido o contradicciones explícitas entre `gameRoundClosed` y `nextRound`. Sigue exigiendo un giro base de retorno y cobertura de variantes.

**NGM — `ngm_hook.js`, `ngm_dispatch.py`, `ngm_runtime.py`:** cada iframe obtiene un identificador de documento efímero. El runtime empareja request/response dentro del mismo iframe mediante la pila de despachos anidados, sin confundir notificaciones auxiliares con apuestas. Cada par de giro tiene un `dispatch_id` idéntico en los artefactos de solicitud y respuesta. Se registra `dispatch-journal.json`; se impiden rounds nuevos cuando hay llamadas anteriores abiertas.

**NGM — `ngm_capture.py`:** el validador v2 coteja los identificadores y secuencias de eventos con el ledger independiente, el importe de la apuesta, premio, saldo y la evidencia por paso. Sigue leyendo trazas antiguas v1, pero las nuevas requieren integridad de los pares v2. Un clic o un mensaje de lobby nunca equivale a una apuesta verificada.

## Pruebas de regresión

Se agregaron `tests/test_playtech_gpas_continuation.py`, `tests/test_playtech_browser_correlation.py` y `tests/test_playtech_ngm_dispatch.py`; también pruebas adicionales al módulo existente `tests/test_playtech_execution_primitives.py`.

Las pruebas verifican estados reales del contrato (FreeGame LIST_PICK sin menú, 8 continuaciones pendientes), pérdida de respuesta, correlaciones erróneas, iframes simultáneos, trazas adulteradas, saldo, cierre de ronda, elecciones y anti-reintento.

Se ejecutaron **24 comprobaciones locales satisfactorias** sobre los nuevos componentes puros y el auditor offline previamente creado. **No equivale** a haber corrido la suite completa del repositorio ni a haber verificado juegos contra el servidor. El CI del PR devuelve `failure` sin pasos antes de los tests, por lo que no hay un resultado de suite integral disponible.

## Siguientes verificaciones requeridas

Reejecutar demo fresca GPAS de `gpas_squeen_pop` hasta que la secuencia FreeGame finalice, el servidor confirme BET_END_STATE_IDENTIFIER, se reconcilie saldo y una apuesta base posterior se cierre. Probar otro juego GPAS con elección de menú obligatoria y `gpas_wcupcc_pop` con default/extraBet. En NGM ejecutar dos juegos con motor local y examinar `dispatch-journal.json` y los artefactos de cada paso. Solo convertir PARCIAL→OK por cobertura real y sin regresiones.

**Precaución:** el fuzzer no conserva la sesión de la compra antigua. No retransmitir comandos del HAR ni asumir que una ronda histórica está recuperada.
