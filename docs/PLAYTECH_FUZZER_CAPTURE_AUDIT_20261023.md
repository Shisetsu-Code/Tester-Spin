# Auditoría de 76 juegos del Fuzzer Manual Cloud

Fuente: `Fuzzer-resultados-76-juegos.zip`, exportación del 23 de octubre de 2026. Se comprobaron los cinco checksums SHA-256 incluidos en el paquete.

## Resumen de evidencia

| Indicador | Valor |
|---|---:|
| Juegos distintos en ZIP | 76 |
| Juegos Playtech | 74 |
| Recorridos | 111 |
| Recorridos Playtech | 109 |
| Recorridos marcados `replayed` | 101 |
| Recorridos marcados `partial` | 10 |
| Requests HTTP | 19.707 |
| Requests con payload | 356 |
| Respuestas con cuerpo incluido | 3.073 |
| Frames WebSocket | 1.853 |
| GPAS con respuestas `GameCommand` pareadas | 6 recorridos |
| Comandos GPAS request/response pareados | 15 |
| Respuestas terminales de ronda GPAS | 14 |
| Rondas GPAS sin terminar | 1 |

**Importante:** `replayed` significa que se enviaron acciones, no que se haya ejecutado una apuesta ni que un bonus se completara. El informe nunca promociona juegos a `OK`.

## Dos cuellos de botella compartidos

**NGM (82 recorridos):** la evidencia WebSocket incluida muestra negociación de directorio de URLs (`urlTypeList` / `urlList`) y no registra comandos de juego. Antes de repetir clics, instrumentar la captura de la conexión real del juego/iframe y vincular cada entrada con su respuesta. Los 82 recorridos no acreditan apuestas.

**GPAS (27 recorridos):** 21 no capturaron ningún comando `GameCommand`. En 6 sí hay comandos y respuestas de servidor, pero lo documentado son fundamentalmente apuestas base. El nombre de un modo o un `input-sent` no acredita compras y tampoco su retorno.

## GPAS con comandos confirmados

| Juego | Ruta | Comandos pareados | Terminales | No terminales |
|---|---:|---:|---:|---:|
| `gpas_aogggriffin_pop` | 4 | 2 | 2 | 0 |
| `gpas_eemeraldspp_pop` | 35 | 4 | 4 | 0 |
| `gpas_scqueen_pop` | 39 | 3 | 3 | 0 |
| `gpas_squeen_pop` | 40 | 2 | 1 | 1 |
| `gpas_jokjac_pop` | 84 | 2 | 2 | 0 |
| `gpas_wcupcc_pop` | 88 | 2 | 2 | 0 |

**Caso pendiente prioritario:** `gpas_squeen_pop`, ruta 40. El último `GameCommand` contestó `gameRoundClosed=false` y `nextRound=FreeGame`; falta capturar y ejecutar su continuación. No reiniciar como si la ronda hubiera terminado.

**Comprobación de costes:** los 15 comandos pareados tienen `stakeAmount`, `betCost` y `gameData.stake` consistentes en unidades internas. Esto no equivale a certificar el balance contable: `personalBalance` aparece nulo o cero en diversas respuestas.

En `gpas_wcupcc_pop` se registró el modificador `extraBet` (600 unidades internas) y la modalidad base `default` (500). Son dos apuestas distintas, no compras de bonus demostradas.

## Recorridos parciales por el exportador

| Juego | Ruta | Motivo | WebSocket | Acciones enviadas |
|---|---:|---|---:|---:|
| `gpas_mgaogkol_pop` | 9 | VISUAL_STATE_MISMATCH | 51 | 1 |
| `gpas_aogwfot_pop` | 11 | VISUAL_STATE_MISMATCH | 39 | 0 |
| `bup` | 21 | VISUAL_STATE_MISMATCH | 4 | 2 |
| `gpas_cashrl_pop` | 23 | VISUAL_STATE_MISMATCH | 3 | 0 |
| `gpas_squeen_pop` | 40 | VISUAL_STATE_MISMATCH | 50 | 3 |
| `fdtsl` | 45 | VISUAL_STATE_MISMATCH | 4 | 1 |
| `gpas_gporang_pop` | 89 | GAME_NOT_READY | 127 | 2 |
| `gpas_gporang_pop` | 90 | GAME_NOT_READY | 126 | 2 |
| `gpas_gotzon_pop` | 91 | GAME_NOT_READY | 175 | 1 |
| `gpas_lluckmccpp_pop` | 104 | VISUAL_STATE_MISMATCH | 28 | 0 |

## Primitivas recomendadas

1. **NGM:** instrumentar todos los sockets del juego, también los de iframes, y guardar comprobantes de ejecución de `SpinRequest` / `FreeSpinsBonusRequest` o del protocolo realmente observado. No avanzar por un clic si no hay transición comprobable.
2. **GPAS:** correlacionar comandos con respuestas; cerrar una ronda solo con `gameRoundClosed=true` y `nextRound=BET_END_STATE_IDENTIFIER`. Ante `FreeGame`, continuar el bonus con un contrato demostrado y nuevas capturas.
3. **Contabilidad:** cotejar débitos y premios con fuentes de balance autoritativas. `personalBalance` nulo o cero no proporciona esa prueba por sí solo.
4. **Cobertura:** descubrir y registrar familias de modalidades desde la configuración y el código actual del cliente, y distinguir `observado`, `ejecutado`, `cerrado` y `OK`.

## Límites del paquete

El ZIP preserva las solicitudes y respuestas disponibles, pero no duplica cuerpos binarios ni todos los recursos estáticos de sus HAR de origen. La ausencia de un comando de juego en la exportación puede significar que no ocurrió **o** que esa conexión no quedó grabada. No atribuir automáticamente los 404 de branding opcional a la falla de juego.

## Herramientas reproducibles

`playtech_fuzzer_evidence.py` permite volver a examinar exportaciones con el mismo esquema sin realizar tráfico de red. Entrega JSON saneado y tiene siete pruebas unitarias locales. No publica cookies, tokens, IDs de sesión, URL queries, paquetes XML completos ni payloads WebSocket.

El informe estructurado por cada una de las 111 rutas está en `playtech_76_juegos_auditoria_saneada.json`.