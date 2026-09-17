# Correcciones de proveedores — 16 de septiembre de 2026

## Cambios aplicados

- **Belatra:** compras con el selector anunciado por el juego; continuación de tiradas gratis; elecciones de doble rojo/negro y contra el crupier, con apuesta completa o media. La respuesta debe confirmar el avance y la elección. Se respetan las repeticiones solicitadas.
- **RubyPlay:** reconocimiento del dominio de elecciones a partir del cliente oficial. Se prueban los índices demostrados, en lugar de enviar siempre cero. La evidencia conserva la fuente y su hash.
- **D1 / 1spin4win:** el estado 3 se reconoce como terminal según los clientes oficiales inspeccionados. Los estados desconocidos siguen pendientes. Las comprobaciones permiten pasar entre estados terminales conocidos.
- **Pragmatic:** se completa la calibración en la misma sesión. Las selecciones de carretes incluyen el índice demostrado por el cliente; las 32 combinaciones de Chicken Chase se recorren por separado. Los bonus de selección ya inicializados usan las posiciones disponibles de la respuesta. Se alternan las menos intentadas. Los cobros de bonus se distinguen de los cobros normales. Un error dentro de una respuesta HTTP 200 ya no se acepta como éxito.
- **Red Tiger:** recuperación de enlaces antiguos sólo si el catálogo oficial devuelve una coincidencia única del mismo juego. No se sustituye un título por otro parecido.

## Evidencia y estados

Una opción sólo cuenta como cubierta con respuesta válida, ronda terminada y dos tiradas normales posteriores en la misma sesión. Si una tirada normal requiere una selección de carretes certificada, se completa esa ronda antes de contarla. Si aparece un bonus, se termina primero y se reinicia la comprobación de dos rondas normales.

Las opciones descubiertas durante la calibración también generan obligaciones de cobertura. Su ejecución durante la preparación no basta para darlas por verificadas. Una prueba posterior de la misma rama y el mismo contrato puede cubrirlas.

Los pendientes se conservan entre corridas. Que una rama no vuelva a aparecer no la elimina del informe. Los archivos de selección guardan dominio, índice elegido, política, firma de rama y fuente del contrato, junto con solicitudes y respuestas. Los estados desconocidos conservan sus registros y detienen esa continuación.

## Resultado de las pruebas demo

| Proveedor | Juego | Resultado observado |
| --- | --- | --- |
| RubyPlay | Elephant Stampede SE | Normal y dos compras completas; elecciones 0 y 1 verificadas. |
| D1 | 10 Lucky Spins | Estado terminal reconocido y dos tiradas normales confirmadas. |
| Belatra | Bear's Tricks | Normal, VIP y tres compras completas; cinco comprobaciones de regreso confirmadas. |
| Belatra | 20 Icy Fruits | Parcial. Nueve elecciones de doble verificadas; otras no aparecieron dentro del límite de búsqueda y una sesión fue cerrada por el servidor. |
| Pragmatic | Chicken Chase | Las 32 selecciones de carretes finalizaron. Un bonus natural se completó con su posición 0; posiciones 1, 2 y 3 pendientes de muestreo. |
| Red Tiger | 777 Strike | Prueba completa con enlace actual y regreso confirmado. |
| Red Tiger | 777 Money Strike | No hay coincidencia exacta en el catálogo oficial consultado. Requiere un enlace vigente del mismo juego. |

Estos resultados corresponden a los juegos indicados, no a todos los catálogos. No se garantiza que una rama aleatoria aparezca dentro de una cantidad limitada de tiradas.

## Siguiente corrida

Reiniciar la aplicación para cargar el código actualizado y ejecutar el resto de los juegos. Revisar el listado de pendientes al terminar. Para una captura manual, iniciar el HAR antes de abrir el juego, completar el evento y continuar hasta dos tiradas normales exitosas sin cerrar la sesión.

Pendientes concretos de esta validación:

1. **20 Icy Fruits:** repetir las elecciones de doble pendientes. Si vuelve a cortarse, conservar la captura de esa sesión.
2. **Chicken Chase:** observar las restantes posiciones del bonus cuando aparezca. La continuación está implementada; falta evidencia de esas opciones.
3. **777 Money Strike:** comprobar si sigue disponible y aportar su enlace actual. 777 Strike es otro título y su éxito no resuelve éste.


## Verificación final

- Suite completa: **625 tests correctos**, ejecutada después de los últimos cambios.
- Revisión de diferencias: sin errores de espacios (`git diff --check`).
- Resultados actualizados en la base de datos de la aplicación.

El listado automático también conserva avisos de respuestas distintas en Bear’s Tricks, Elephant Stampede SE y 777 Strike. Sus recorridos terminaron correctamente; estos avisos piden revisar variaciones del servidor y no equivalen a una tirada fallida. No se borraron por el solo hecho de que el resultado operativo fuese OK.
