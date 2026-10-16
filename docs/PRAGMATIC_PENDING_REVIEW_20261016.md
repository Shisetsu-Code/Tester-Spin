# Pragmatic: revisión de obligaciones pendientes — 16 de octubre de 2026

Se consultó `data/tester-spin.sqlite3` mediante SQLite `mode=ro`, seleccionando el último resultado por slug. Se inspeccionaron los artefactos de tres representantes sin ejecutar sesiones ni modificar resultados, cobertura histórica o DB.

| Representante | Evidencia de la última ejecución | Obligación que conserva PARCIAL |
| --- | --- | --- |
| Book of Monsters | PURCHASE_1 acredita las tres acciones play/sm/sp mediante `parameterized-menu-actions/v1`, con muestras 1/1/1. | Las tres obligaciones pendientes proceden de SPIN histórico, no de PURCHASE_1. No se observó esa elección natural en la ejecución actual. |
| Bubble Up! | PURCHASE_1 acredita la clase de posición oculta en niveles 0 a 4 mediante `hidden-position-structural/v1`. | Persisten niveles históricos 5 y 6 de compra, además de obligaciones SPIN. La ejecución actual no demuestra esos niveles superiores ni trigger natural. |
| Money Stacks | Las cuatro compras acreditan ambas opciones fs/bbl, con el mismo contrato y muestras suficientes. | Persisten SPIN y ANTE_BET_1 históricos; no hay elección natural actual que permita sustituirlos. |

## Causa comprobada

Los identificadores hash de cobertura no se calculan directamente desde todo el estado transitorio: `annotate_bonus_coverage` usa modo de origen, firma de contrato y hash de evidencia. El parser de menús parametrizados ya mantiene una firma estable `PRAGMATIC:parameterized-gamble:bgt=69:play-sm-sp` aunque cambien los números de sm/sp o el historial del menú, conservando separadas las acciones play, sm y sp. Por tanto, las antiguas etiquetas con números observadas en Book of Monsters no son el contrato que genera hoy el parser.

`archive_normalized_menus` exige una sustitución demostrada con el mismo modo de origen, opciones/clases, respuesta reconocida y muestras terminales con retorno confirmado. Una compra completa no satisface automáticamente una obligación SPIN histórica. La suite de migración contiene un caso negativo que cambia el modo de origen para garantizar esa conservación.

No se identificó un defecto compartido que justifique borrar las obligaciones de estos tres representantes. La presencia de elecciones en un HAR histórico permite conocer la primitiva; no acredita que reaparecieran y se cerraran en una sesión actual del modo natural. No se fuerza OK ni se aplican excepciones por juego.

## Límites

Esta revisión no certifica los 25 parciales del catálogo. Tampoco afirma que toda obligación histórica sea necesariamente vigente: una futura migración necesita la evidencia del origen y una ejecución actual del mismo contrato y modo. No se modificó código de producción.
