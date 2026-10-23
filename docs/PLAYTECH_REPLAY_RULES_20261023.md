# Playtech: reglas reutilizables desde 111 recorridos (23-10-2026)

Base: auditoría saneada de Fuzzer-resultados-76-juegos.zip. Se registraron 111 recorridos de 76 juegos; 109 pertenecen a Playtech (82 NGM, 27 GPAS) y dos a otros proveedores.

**Alcance:** un recorrido 'replayed' registra el envío de inputs, no una apuesta completada. El análisis nunca recarga sesiones viejas, manda solicitudes del HAR ni cambia el status PARCIAL a OK sin nueva evidencia.

## Reglas agrupadas

| Regla | Recorridos | Acciones antes de probar de nuevo |
|---|---:|---|
| CAPTURE_NGM_GAME_EVENTS | 80 | Observar SpinRequest, respuesta, pago y cierre dentro del cliente NGM/iframe de una demo nueva; urlList es navegación, no juego |
| CAPTURE_GPAS_GAME_COMMAND | 14 | Capturar GameCommand por correlationId y asociar solicitud/respuesta en una demo fresca |
| REFRESH_VISUAL_TARGET | 6 | Reinspeccionar pantalla y geometría actual del iframe antes de decidir; no reproducir coordenadas vencidas |
| WAIT_FOR_DEMO_READY | 3 | Esperar bootstrap y control de juego activo antes de emitir cualquier apuesta |
| VERIFY_DECLARED_MODES | 5 | Ejecutar variantes de compra y antebet reconocidas por configuración actual, cerrando ronda y retorno a base |
| RESUME_OPEN_FREE_GAME | 1 | Resolver la continuación FreeGame del juego gpas_squeen_pop en una sesión todavía viva; de lo contrario, demo nueva |
| EXCLUDE_NON_PLAYTECH | 2 | No mezclar un juego Pragmatic ni uno BGaming en estadísticas Playtech |

Los 82 recorridos NGM se desglosan en 80 capturas incompletas y dos errores visuales. Las 21 rutas GPAS sin comandos se reparten entre 14 casos de captura, tres de preparación y cuatro de desajuste visual.

## Cambios en el runtime de Tester-Spin

- NGM: el selector de iframe ahora busca exactamente uno con el controlador __testerNgmSpin activo. Si existe un iframe inerte o desprendido, no bloquea al controlador válido. Si hay dos controles vivos, falla de forma segura.
- GPAS: el modo extraBet se clasifica como ANTE_BET únicamente cuando hay vinculación en el cliente actual (ExtraBetsModule u otro contrato ya reconocido). Sin esa fuente queda UNKNOWN_FEATURE y no se confunde con una apuesta base.
- NGM y GPAS: los resultados PARCIAL adjuntan structural_map.verification_worklist con prioridades y acciones pendientes sin automatizar un retry incierto.

## Barreras que permanecen

- GPAS: para confirmar ronda se exige gameRoundClosed=true, nextRound=BET_END_STATE_IDENTIFIER, coste y saldo conciliados.
- Si FreeGame sigue abierto, no se envía otra apuesta. Las continuaciones siguen la evidencia y protocolo actual; nunca las coordenadas de una sesión terminada.
- personalBalance nulo o cero en el export no certifica balances. El saldo se comprueba en la sesión demo nueva.
- Los nombres de opciones y botones no acreditan compras ni ausencia de bonus. La configuración y el cliente en ejecución deciden qué modalidades son válidas.
- El backend NGM de Tester-Spin tiene su propio motor demo local y su ledger. Que el fuzzer externo no haya capturado un socket NGM no invalida una ronda probada con traza local.
- La política nunca promueve casos por una mera reproducción visual; las compras/elecciones y el retorno al juego base requieren pruebas independientes.

## Uso

Ejecutar sobre el JSON SANITIZADO, no sobre el ZIP o HAR crudo:

```sh
python -m tester_spin.providers.playtech.replay_rules playtech_76_juegos_auditoria_saneada.json --out reglas_playtech.json
```

El JSON resultante contiene worklist por juego/ruta y groups por causa compartida; fija games_promoted_to_ok=0 y safe_to_auto_retry_a_wager=false.

Medir en pruebas posteriores: comandos emitidos, respuestas pareadas, modo base y modalidades de compra, saldos, rondas terminales, opciones cubiertas y retornos verificables. El histórico no permite calcular cuántos parciales pasarán a OK sin ensayos frescos.

Se agregaron pruebas de reglas, valores negativos, cobertura, semántica extraBet y selección inequívoca de iframe. CI en GitHub puede fallar antes de ejecutar sus pasos por infraestructura; no se atribuye a las pruebas sin evidencia.
