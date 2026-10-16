# Yggdrasil: acceso y parciales, 16 de octubre de 2026

Se hicieron dos bootstrap Demo nuevos con identidad aleatoria y el gate persistente del proveedor, sin ejecutar play ni escribir resultados en la base:

- Blood Moon Wilds: authenticate sigue rechazado con code=-1.
- 3 Gladiators vs Caesar, control previamente OK: authenticate/game/restore correctos; dominio BASIC y cuatro compras reconstruido sin opciones pendientes.

Los HAR privados están en `data/ygg-access-review-20261016/blood-moon-wilds/http.har` y `data/ygg-access-review-20261016/3-gladiators-vs-caesar/http.har`. La muestra demuestra disponibilidad del servicio y persistencia de al menos un rechazo específico; no demuestra recuperación de los otros doce rechazos históricos ni justifica cambiar organización/backend.

## Ocho parciales históricos

Se consultó SQLite en modo lectura y las respuestas/probes locales:

- Badger Miners, Jungle Books y Nice Catch 2 DoubleMax: diez probes cerrados clasificados CLOSED_FEATURE_ROUND, sin los dos giros ordinarios requeridos. Sus contratos de presentación son diferentes: GameActionResponse con contadores/colecciones, geometría host/guest con carretes sincronizados, y output con reelKey/bonusInfo DoubleMax. Aumentar probes o aceptar cualquier cierre no valida estas familias.
- Football Glory: el probe que paga 0.80 incluye collectionsFeature y gloryAfterSpin con gathered activo; el cierre C no basta para acreditar que esa colección volvió al estado ordinario.
- Pirates 2 Mutiny: tableros de cascada y multiplicadores antes/después, premios y nextCmds; el último resultado no fue reconocido. Necesita aprender el contrato de la cascada antes de promoverlo.
- Nice Catch DoubleMax: BASIC y antebet ya tienen retorno confirmado; BUYMAXBONUS sigue con dominio de continuación ambiguo. No se interpreta una repetición del comando como otra compra.
- Lucky Apocalypse Gigablox: identidad/bootstrap no comprobados en el registro actual; sin contrato de ejecución.
- Golden Chip Roulette: el error histórico NoneType no se reproduce al pasar la respuesta game del HAR del 13 de octubre por configuration actual. Devuelve BASIC pendiente por falta de configuración de moneda por modo. El dominio Modes y CoinsPerBet se reconocen, pero no se puede construir precio/apuesta de modo seguro. No se inventan denominaciones.

No se modificó código Yggdrasil ni se promovieron estados. No apareció una única primitiva común demostrada por estas ocho capturas. Las credenciales y respuestas completas permanecen locales.
