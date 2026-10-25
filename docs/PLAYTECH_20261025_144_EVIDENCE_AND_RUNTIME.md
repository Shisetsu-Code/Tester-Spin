# Playtech — nuevo paquete de 144 juegos (25/10/2026)

## Fuente y alcance

Material recibido: LEEME-playtech.txt, MANIFEST.json, playtech-catalogo-operaciones.json,
playtech-estado-consolidado.json, playtech-endpoints-por-juego.json,
playtech-protocol-templates.json, playtech-protocol-run.mjs,
playtech-resumen-final.json, playtech-revision-manual.json y conciliaciones.

**El repositorio es público:** los archivos crudos NO se copiaron aquí. Incluyen endpoints de sesión,
identificadores, rutas locales y trazas. Este documento solo conserva métricas y hallazgos
reproducibles; las pruebas reales producen sus propios resultados saneados.

El archivo indica 144 juegos procesados, con 15 anteriores excluidos. Son 66 GPAS y 78 NGM.
143 figuran como `recorded` en el registro histórico y uno como revisión manual. Esos estados
NO son los estados OK/PARCIAL de Tester-Spin.

## Autoridad de las pruebas

- 243 operaciones GPAS están ligadas a request/response por `correlationId`; de ellas, 235
  tienen marca de cierre protocolar y respuesta final `BET_END_STATE_IDENTIFIER` con 0 restantes;
  ocho no acreditan cierre. Aparecen en 63 juegos GPAS diferentes. Ninguna cifra sustituye
  la reconciliación financiera que exige el ejecutor de Tester-Spin.
- Para 78 NGM no se registraron mensajes `GameCommand` GPAS: se usa el motor demo local.
  Las 78 descripciones visuales no prueban por sí solas inventario ni liquidación.
- El controlador adicional documenta tres sesiones terminales: `gpas_dncftnt_pop` (38
  solicitudes), `gpas_wcupcc_pop` (21) y `gpas_wlroll_pop` (13). Su script externo
  verificó fase y restantes; el ejecutor requiere adicionalmente coste, UUID y saldo.
- `gpas_sorome_pop` conserva la compra abierta en `ChooseFG`/`LIST_PICK`: una continuación
  vacía devolvió `EngineError`. Nunca reintentar una solicitud con resultado incierto
  ni declarar el bonus cerrado por un informe visual.

## Correcciones en primitivas y pruebas reales

- `card_buy_family`: identifica `BF3Cards`, `BF6Cards`, `BF9Cards` como **compras**
  únicamente con opciones activas, client-side BuyFeatureController, coste y UUID propios,
  startingMode distinto y línea declarada coherente. [Actions #40198470016]
  (https://github.com/Shisetsu-Code/Tester-Spin/actions/runs/40198470016):
  `gpas_wlroll_pop` **OK**, 5 rondas con las 3 compras; `gpas_wcupcc_pop` **OK**, 4 rondas.
- Familia de **legado UUID**: el servidor declara base `40` y compra `Buy feature`;
  se exige cliente `GLU.game.bet` con `stakeCostUuid`, `baseCostMultiplier`, dos opciones y
  `featureBetEnabled=true`. [Actions #40199206103]
  (https://github.com/Shisetsu-Code/Tester-Spin/actions/runs/40199206103):
  `gpas_sorome_pop` **PARCIAL**, 2 rondas base cerradas; compra aceptada, falta
  serializador verificado para `ChooseFG` (`PICK_COMMAND_NOT_BOUND`).
- [Actions #40197994513](https://github.com/Shisetsu-Code/Tester-Spin/actions/runs/40197994513):
  `gpas_dncftnt_pop` **OK**, 5 rondas (incluidas 29/80/80 respuestas por intento);
  `gpas_wcupcc_pop` **OK**, 4 rondas; `gpas_efnof_pop` sigue sin vincular contrato,
  `gpas_mwilds_pop` sigue con opciones no vinculadas.
- Un ensayo aislado [Actions #40198628648]
  (https://github.com/Shisetsu-Code/Tester-Spin/actions/runs/40198628648) probó
  `gpas_mwilds_pop`: giro normal cerrado, pero `FG40` devolvió
  `STAKE_UUID_MISMATCH`. Por lo tanto, no se habilita como compra.

## Próxima superficie técnica

Para `ChooseFG` no basta con saber que el servidor lista opciones o devuelve
`LIST_PICK`: hay que demostrar con el **cliente vigente** qué serializador genera
el campo de elección, comprobar el `correlationId` y conciliar saldo terminal.
En NGM faltan vínculos cliente-código/manifiesto y contratos de calculadoras,
mientras la comprobación visual sigue siendo una evidencia distinta.

Las pruebas de regresión conservan `PARCIAL` cuando hay opciones desconocidas,
respuestas inciertas, discrepancia de UUID, ronda abierta o saldo no reconciliado.
En ningún caso estos datos importados pueden marcar un juego OK por sí solos.
