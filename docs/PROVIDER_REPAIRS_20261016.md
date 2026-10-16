# Reparaciones compartidas de proveedores: 16 de octubre de 2026

La revisión separa declaración de opciones, capacidad para enviarlas y evidencia de ejecución. No añade listas por juego, no deduce compras de giros normales y no convierte estados desconocidos en OK. Los totales incluyen resultados históricos conservados; las verificaciones nuevas se describen aparte.

| Proveedor | OK anteriores | OK al corte | Parciales | Errores | Otros estados |
|---|---:|---:|---:|---:|---|
| hacksaw | 183 | 186 | 0 | 0 | — |
| redtiger | 368 | 385 | 8 | 3 | — |
| ka_gaming | 256 | 259 | 0 | 41 | PENDIENTE: 529 |
| bgaming | 192 | 189 | 26 | 11 | SIN_DEMO: 6 |
| rubyplay | 178 | 179 | 4 | 6 | SIN_DEMO: 2 |
| belatra | 81 | 81 | 1 | 22 | — |
| yggdrasil | 137 | 137 | 8 | 14 | — |
| pragmatic | 630 | 630 | 25 | 1 | CANCELADO: 1 |
| 3oaks | 110 | 110 | 0 | 0 | — |
| 1spin4win | 229 | 229 | 0 | 0 | — |
| nolimit_city | 109 | 109 | 31 | 0 | — |

## Cambios y pruebas actuales

- **Hacksaw:** menús alternativos y variantes del constructor se vinculan con su consumidor público. El contexto customData se demuestra entre cliente y SDK, por selector y para el regreso al giro normal. Se rechazan cambios del alias o bandera y literales no finitos. Los tres pendientes completaron sesiones nuevas; los otros 183 OK conservan pruebas anteriores. [Contrato](HACKSAW.md).
- **Red Tiger:** compras, aumentos de probabilidad y cambios de estado se separan por las tablas actuales. Los modos pagados requieren acuse, precio y liquidación exactos y dos giros normales. Se reconocen formas cerradas de respin y NSP, con unidades de multiplicadores separadas. Una corrida de 28 afectados y repeticiones de familias corregidas recuperaron 17 OK. [Primitivas](REDTIGER_MODE_CONTRACTS.md).
- **KA:** firma y declaraciones toleran exclusivamente renombres que preservan estructura. ThreeMonkeys, BangBang y RoaringEra completaron pruebas actuales. El lote restante terminó con 1 OK y 41 errores; las respuestas examinadas incluyen Retry-After en HTTP 404. Se conserva esa pausa entre procesos y se comprueba antes del túnel, cuota, worker y solicitudes. La pausa observada vence el 17/10 a las 06:05:19 de Argentina. Los 529 pendientes no se ejecutaron. [Acceso](KA_ACCESS_REVIEW_20261016.md), [declaraciones](KA_DECLARATION_RENAMING_20261016.md).
- **BGaming:** wrapper de dos argumentos, conversión explícita de apuesta nominal/efectiva y denominador de precios demostrado por el cliente. Los wrappers de política propagan el nuevo contexto. El resultado OK y el contrato exportado exigen la misma evidencia de modos requeridos. Cinco OK anteriores se degradaron mediante auditoría sin nueva ejecución: Aztecs Claw Wild Dice, Chicken Fire, Red Hot Chilli Chickens y Wild Tiger 1/2. No se borró su evidencia. [Apuestas y precios](BGAMING_LINE_STAKE_REVIEW_20261016.md), [wrapper](BGAMING_TWO_ARGUMENT_REVIEW_20261016.md).
- **RubyPlay:** la recuperación desde el contrato público del navegador también cubre el fallo de descubrimiento de v_math. Sugar Rush Fever pasó a OK; los otros diez afectados se repitieron y quedaron 4 parciales y 6 errores. Seis launchers actuales no declaran gameName; no se los marca como ausencia de demo sin prueba. [Contrato](RUBYPLAY.md).

## Límites pendientes

Belatra sigue bloqueado antes de las apuestas: el dominio demo anunciado falla TLS y la alternativa oficial devuelve una comprobación de acceso. No se desactiva TLS. Firetrace no estaba conectado para contrastar esa alternativa en navegador. [Revisión](BELATRA_DEMO_ACCESS_20261016.md).

Yggdrasil conserva errores actuales de autenticación y familias de continuación o moneda aún desconocidas; un control de bootstrap correcto no acredita cierre de rondas. Pragmatic conserva obligaciones de giros naturales y niveles no observados; una compra terminada no demuestra esos recorridos. [Yggdrasil](YGG_ACCESS_REVIEW_20261016.md), [Pragmatic](PRAGMATIC_PENDING_REVIEW_20261016.md).

Amusnet, Blueprint, ELK, Games Global, Greentube, NetEnt, PG Soft, Play’n GO, Playson, Playtech, Push Gaming, Relax y Wazdan siguen con catálogo y sin ejecutor implementado. Esta reparación no los presenta como proveedores ejecutables.

## Validación y exportación

Suite completa de publicación: `3239 passed, 3 warnings, 276 subtests passed in 108.83s (0:01:48)`.

Los contratos listos se reconstruyen y validan contra sus resultados originales, con respaldo local y sin generar nuevas pruebas. KA mantiene su ejecutor, pero todavía no implementa el contrato Farm estable; no se inventa esa exportación. Capturas, bundles públicos descargados, sesiones y SQLite quedan fuera del repositorio.

Corrida nueva de BGaming al corte: **11/33**, estado **RUNNING**, resultados: PARCIAL 8, OK 1, ERROR 2. No se atribuye validación a los juegos aún no intentados.
