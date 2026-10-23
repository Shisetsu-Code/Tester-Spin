# Games Global — contratos desde dos HAR (23-10-2026)

## Protocolo compartido

Ambos juegos envían JSON con packet.packetType=7 y packet.payload XML,
con raíz Pkt, Id y Request. La ruta de juego capturada es:
https://api32.gameassists.co.uk/casino/play/public/v1/games/module/{mid}/client/{cid}/play

La respuesta incluye context.financials, context.balances.totalInAccountCurrency
y un segundo packet.payload XML. Los dos dialectos requieren adaptadores de
estado distintos: Amazing Link Zeus utiliza Response/Slot; Gold Blitz Ultimate
utiliza Response/Core/Stage y PossibleBets/Action.

Los HAR originales pueden contener cookies, identificadores de usuario o
sesión. **No incorporarlos completos al repositorio**, no reutilizar credenciales
ni reemitir requests capturados. El analizador incluido es exclusivamente
offline y siempre devuelve PARCIAL.

## HAR 1: Amazing Link Zeus — Lume

- Módulo 18656, cliente 50300, cliente XML v5.
- 294 entradas de red; 28 llamadas a la API de juego: 1 Refresh,
  5 Spin y 22 FreeSpin.
- Cuatro giros base precedieron un bonus natural de 10 Free Spins.
  Se observaron 22 continuaciones FreeSpin, incluidos eventos de esa rama.
- Respuesta terminal: nextStage=BaseGame, freeSpins=0 y
  freeSpinTotalWin=13620 (136,20 unidades demo).
- Una nueva tirada base confirma el regreso.
- Este HAR no demuestra ninguna compra pagada ni sus alternativas.

## HAR 2: Gold Blitz Ultimate — Mahi Gaming

- Módulo 101789, cliente 40300, cliente XML v6.1.
- 337 entradas de red; 45 llamadas a la API de juego.
- Un BaseGame disponible declara **33 acciones** en PossibleBets:
  Play, PlayDouble, PlayGuarantee, y 30 variaciones de
  PlayBonus{1..5}x{3|4} con sufijo vacío, Double o Guarantee.
- De estas 33 sólo se ejecutaron 5 clases: Play, PlayDouble,
  PlayGuarantee, PlayBonus4x4Guarantee y PlayBonus5x4.
  Las otras 28 no deben tratarse como verificadas.

### Costes capturados (apuesta base de 2,00 FUN)

| Acción | Débito capturado |
| --- | ---: |
| Play | 2,00 |
| PlayDouble | 4,00 |
| PlayGuarantee | 20,00 |
| PlayBonus5x4 | 361,90 |
| PlayBonus4x4Guarantee | 2.299,62 |

En PlayDouble, wager=200 y sideBet=200 (coste total 400).
En PlayGuarantee, wager=200 y sideBet=1800 (coste total 2000).
En PlayBonus4x4Guarantee, wager=22996 y sideBet=206966
(coste total 229962). La unidad monetaria se escala por 100.
Los 7 débitos capturados con coste explícito en Core/Stage/Bet
coinciden con context.financials.betAmount.

### Opciones de tiradas y continuación

- PlayBonus4x4Guarantee pasó por FreeSpinsOptionSelect. La opción
  FreeSpinOption3 concedió 20 giros iniciales. Se observaron
  21 solicitudes FreeSpin, fin de ronda y BaseGame disponible.
  La acción siguiente fue otra compra, no un giro normal de retorno.
- PlayBonus5x4 pasó por FreeSpinsOptionSelect. La opción
  FreeSpinOption2 concedió 15 giros; se observaron 15 solicitudes
  FreeSpin, fin de ronda y un giro base posterior.
- La cantidad que concedería FreeSpinOption1 **no fue capturada**.
  Tampoco se probó que todas las compras permitan todas las elecciones.

Los campos CurrentStartingMultiplier, CurrentMultiplier y
FreeSpinsBoostMode forman parte del contrato de progreso. No inferir
la semántica exacta de los segmentos x3/x4 del nombre de acción
sin el contrato del cliente actual.

## Contabilidad

En 73 respuestas HTTP 200 de juego, las identidades de módulo y cliente
fueron consistentes. Se reconciliaron sin discrepancias las 27
transiciones de saldo consecutivas del primer HAR y las 44 del segundo.

El analizador usa decimal exacto y rechaza inconsistencia entre la
declaración de coste en el servidor y el débito observado. No extrapola
precios de compras no realizadas.

## Primitivas reutilizables para Tester-Spin

1. Identificar paquete JSON + XML y variante Slot o Core/Stage.
2. Enumerar acciones anunciadas desde PossibleBets/Action.
3. Separar compras, modificadores de apuesta y elección de Free Spins:
   Spin(BaseGame) -> FreeSpinsOptionSelect -> FreeSpinOptionN ->
   FreeSpin repetidas -> BaseGame.
4. Modelar el número de tiradas como elección posterior a la compra,
   no como una nueva compra.
5. Verificar costes en enteros, liquidación, estado terminal, opciones
   realmente cubiertas y pruebas de retorno.
6. Mantener PARCIAL ante alternativas sin ejecución o versión de cliente
   distinta de la capturada.

Herramienta offline:
python -m tester_spin.providers.games_global_har <captura1.har> <captura2.har> --out resumen-saneado.json

El JSON exportado contiene sólo evidencia estructural saneada, sin
cabeceras autenticadas, tokens, ID de jugador ni respuestas crudas.
