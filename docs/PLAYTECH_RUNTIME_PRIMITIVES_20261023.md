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

## Resultados adicionales de pruebas reales — 23 de octubre de 2026

Se ejecutaron **16 juegos GPAS distintos** del catálogo oficial en cuatro jobs paralelos de GitHub Actions, siempre con sesiones demo frescas, sin replicar requests de HAR históricos y sin actualizar manualmente el estado. La primera ejecución de la muestra dio **8 OK y 8 PARCIAL** ([Actions 40023363979](https://github.com/Shisetsu-Code/Tester-Spin/actions/runs/40023363979)). La ejecución tras las nuevas primitivas dio **12 OK y 4 PARCIAL** ([Actions 40025494106](https://github.com/Shisetsu-Code/Tester-Spin/actions/runs/40025494106)). Las ramas aleatorias pueden variar entre ejecuciones; esta comparación es de la muestra, no un porcentaje global del catálogo.

**Cuatro casos con mejora verificada mediante cierre de ronda, contabilidad y cobertura:**

- `gpas_lluckmccpp_pop`: `extraFG` y `extraCollector` dejan de ser desconocidos **solo** con scope, controlador antebet y flag actual. Demo: 4 rondas cerradas, OK.
- `gpas_mgaogkol_pop`: cuando `featureBetEnabled=false` y no hay `activeBetOptions`, la compra BF no habilitada se omite en la secuencia ejecutable. Demo: 2 rondas base, OK. No se reinterpreta una compra realmente disponible como inexistente.
- `gpas_jokjac_pop`: `extra_disabled` se puede reconocer como base **únicamente** si el servidor indica `extraBetEnabled=false`, es la única opción activa y el coste/las líneas concuerdan con el default. Demo: 2 rondas, OK.
- `gpas_eemeraldspp_pop`: modo de líneas con `startingMode=Standard` y `winline` igual al nombre numérico usa el `featureType` observado **`lines-N`**, no un selector numérico desnudo. Todas las diez opciones y una ronda de retorno a base cerraron; 11 rondas, OK. Validado inicialmente con trials `lines-1`, `lines-10` y `lines-5` (esta última abrió Respin1, nunca contada terminal en el ensayo aislado).

**Casos aún parciales de la muestra:**

- `gpas_gporang_pop`: los costes 20, 40, 60, 80, 100 no contienen un selector de cliente suficientemente vinculado. Probar 20/default puede dar una ronda correcta, pero 40/default devuelve `EngineError` y 100/default llegó a devolver un UUID distinto. La inferencia por proporcionalidad de precio **se revirtió**; no se deben repetir entradas al azar.
- `gpas_aogggriffin_pop`: las rondas base ya funcionan con selector default; falta el contrato semántico de las opciones HR10/HR20/HR40. Sigue PARCIAL.
- `gpas_cashrl_pop`: la familia DOLLAR-* posee scopes explícitos y las primeras apuestas se completan; apuesta posterior devuelve EngineError. Los ensayos aislados DOLLAR-250/DOLLAR-500 también fallaron con saldo demo inicial 1.000.000; no se debe atribuir sin evidencia a falta de saldo.
- `gpas_jdice_pop`: a veces aparece un `LIST_PICK` cuya elección no está vinculada al serializador del cliente. En un ensayo aislado, el intento con formato genérico de pick fue rechazado mediante `EngineError`; ese método **no se incorporó al ejecutor**. Otras rondas que no ofrecen selección pueden cerrar, pero no demuestran que la rama pendiente esté cubierta.

**Códigos ausentes del release oficial:** `gpas_squeen_pop` y `gpas_scqueen_pop` no aparecen en el `logical_bundle.php` de la versión GPAS 26.9.7.1, aunque figuren en un catálogo histórico. El bootstrap ahora da `GPAS_GAME_NOT_IN_ACTIVE_RELEASE:<code>` en vez de `KeyError`. No se cambia silenciosamente a una edición de otro juego.

**NGM:** `ashhof` verificó dos rondas demo locales y sus contratos; `ashadv` sigue PARCIAL por contrato / manifiesto NGM no enlazados. No se interpreta un HAR con lobby sin comandos como prueba de juego.

**Seguridad del diagnóstico:** GitHub Actions solo publica resúmenes saneados; HAR, identificadores de sesión y trazas crudas se mantienen fuera del repositorio público. Los scripts de prueba de selectores envían una sola apuesta por sesión demo nueva; no se autorizaron reintentos de resultados inciertos. Se eliminó de la rama el ensayo temporal de selección `pick` cuya hipótesis falló.

**Reproducción:** el flujo `.github/workflows/playtech-gpas-family-live.yml` ejecuta los 16 juegos por grupos; `.github/workflows/ci.yml` compila y comprueba regresiones. Las correcciones siguen en la rama `fix/verify-partials-20261023` del PR #37, no en main ni en las versiones publicadas.
