# Nolimit City: contratos comunes y auditoría del corpus

Estado vigente (2026-10-16): **95 OK, 44 PARCIAL y 1 ERROR de 140 juegos**.
La verificación más reciente figura al final; las secciones anteriores conservan
la evidencia y el alcance de sus respectivas versiones.

El ejecutor y el analizador de HAR usan el mismo contrato de estado, acción,
acuse y dinero. Las capturas documentan operaciones observadas; los dominios
ejecutables provienen de la declaración del servidor y del cliente de la sesión.
El nombre del juego no decide la operación.

## Implementación

- `contracts.py` resuelve continuaciones automáticas, elecciones finitas,
  cobros y el contrato aprendido de giro extra cotizado. Describe petición,
  fase que debe acusar el servidor, dominio y conciliación monetaria.
- `lifecycle.py` normaliza llamadas incondicionales del método activo,
  callbacks de timelines y finalizaciones de presentaciones. Rechaza condiciones
  no interpretadas, métodos inactivos, retornos anticipados y timelines pausados,
  cancelados o reasignados. No ejecuta JavaScript descargado.
- `runtime.py` consume el contrato, aplica la cobertura de elecciones y guarda
  `operation-NNNN.json` por paso. Reutiliza el cliente por nombre y versión en
  `data/providers/nolimit_city/_clients`. Los contratos incluyen la huella del
  cliente cuando interviene.
- `corpus.py` revisa los intercambios posteriores a una acción desconocida,
  separa conexiones y registra errores de importación, acuses desconocidos y
  fallos monetarios. No concede OK de ejecución.
- `protocol.py` reconoce las tramas del navegador y el formato histórico del
  escritor de Tester-Spin. Usa la misma declaración de modos del ejecutor y
  mantiene cada clave vinculada a su conexión capturada.

Se corrigió una mezcla de espacios de nombres: BONUS_BUY/BOOSTED_BET describen
capacidades comerciales; FREESPIN describe la categoría de fase de las compras.
Ahora se contrastan como dominios distintos derivados del servidor. Mezclarlos
hacía que un catálogo completo pareciera una elección pendiente.

## Repetir la auditoría

Desde la carpeta de Tester-Spin:

```powershell
.venv/Scripts/python.exe -m tester_spin.providers.nolimit_city.corpus `
  data/providers/nolimit_city `
  --client-dir data/providers/nolimit_city/_clients `
  --output data/reports/nolimit-corpus.json
```

`--har-root` agrega archivos o carpetas de HAR. También admite un corpus NDJSON
decodificado. El comando es offline: no reenvía tráfico ni apuesta con sesiones
capturadas. Si falta el cliente exacto, conserva la acción sin resolver. Los HAR
originales y los clientes completos permanecen locales.

Los pendientes se agrupan por fase y las acciones por familia, para corregir una
primitiva y repetir todo su grupo. Un bloqueo no impide examinar los pasos
posteriores que sí quedaron grabados.

## Comparación del 15 de octubre de 2026

Se fijó un conjunto de 1141 capturas locales y 135 versiones de clientes oficiales.
La comparación usa las primitivas de 5f25922 y las actuales, con la misma auditoría,
archivos y clientes. Se pudieron vincular 1136 capturas con su cliente exacto.
Siete no conservaban init y ocho tenían una declaración todavía no entendida;
estas limitaciones permanecen registradas.

| Medida offline | Primitivas anteriores | Contratos consolidados |
|---|---:|---:|
| Pasos revisados | 9565 | 9565 |
| Pasos aceptados por el ledger | 9385 | 9499 |
| Rondas reconstruidas con cierre | 1749 | 1869 |
| Acciones con contrato y acuse | 6773 | 7279 |
| Acciones sin contrato o acuse entendido | 561 | 55 |
| Fallos registrados por el ledger | 178 | 66 |

No hubo capturas con menos pasos monetarios aceptados ni menos rondas cerradas.
Estas cifras describen pasos y rondas históricas, no juegos OK. No cuentan ramas
que no se alcanzaron en esas capturas. Los 55 pasos
pendientes se concentran en FREESPIN_AVALANCHE (51), GAMBLE_FIFTY_FIFTY (2),
SUPER_FREESPIN_END (1) y NORMAL_AVALANCHE (1). Los fallos de declaración y dinero
se registran por separado.

## Prueba real del grupo afectado

Se repitieron 11 juegos cuyo primer bloqueo anterior ahora tiene contrato.
Cinco obtuvieron OK: Bonus Bunnies, Deadwood, DJ Psycho, Pearl Harbor y Tanked.
Los otros seis avanzaron pero conservan PARCIAL:

- Duck Hunters y True Grit 2: decisión de giro extra de pago.
- Roadkill y Space Donkey: otra modalidad de tiradas gratuitas.
- The Border: avalancha de una modalidad superior.
- xWays Hoarder 2: discrepancia de saldo, coste y liquidación.

Los OK incluyen modos declarados y retorno normal. Esta prueba no representa
una nueva ejecución del catálogo entero. Los pendientes conservan su evidencia.

La suite completa pasó con 2412 pruebas, 264 subpruebas y tres advertencias.
La revisión independiente añadió un caso negativo para impedir que un callback
de un timeline pausado se interprete como continuación ejecutable.

El resumen para herramientas está en `nolimit-corpus-comparison-20261015.json`.
No contiene credenciales ni HAR completos.


## Descuentos de premio y cobertura de elecciones (15 de octubre de 2026)

Una elección declarada puede devolver un premio de paso negativo: representa la
reducción del premio pendiente, no una apuesta negativa. El ledger solo acepta
este resultado si recibe el contrato de elección del cliente actual, la petición
pertenece a su dominio, el servidor confirma la fase y la opción y la ronda
termina con saldo explícito. El descuento no puede superar el premio acumulado;
se mantienen las comprobaciones de acumulado, coste y saldo. Sin ese contrato,
los negativos siguen rechazados. El ejecutor, la auditoría de corpus y el
analizador HAR (con `client_source` explícito) comparten la comprobación.

La captura reducida `tests/fixtures/nolimit_selection_loss.json` conserva una
ronda cuyo premio pasa de 43,26 a 0 tras la elección 2. Se eliminan identificadores
de sesión y matrices gráficas; la inicialización del segmento usa su saldo de
entrada. Las pruebas alteran opción, acuse, fase, saldo, acumulado, cargo y estado
pendiente para comprobar que no se certifiquen resultados inconsistentes.

La cobertura neutral ahora incluye `choice_domains` dentro de cada modo. Por eso
una compra ejecutada no produce el mensaje de cobertura completa si falta alguna
opción interna. Los dominios se sincronizan al finalizar una ejecución, también
cuando se interrumpe por error.

El lector de cliente reconoce enlaces IDLE con una instancia directa, el último
valor de una expresión formada por constructores, alias estáticos de GameMode y
callbacks `onComplete` de timelines activos sin asignación. No ejecuta código ni
agrega excepciones por nombre de juego.

En sesiones demo nuevas, Beheaded, Dead Canary y Bounty Hunters obtuvieron OK.
Dead Men Walking superó el respin anterior y conserva pendiente EXTRA_SPIN;
Dead, Dead Or Deader conserva RESPIN. Esto es una muestra dirigida de cinco
juegos, no una nueva tanda completa del proveedor.

Sobre las mismas 1141 capturas congeladas, el ledger acepta 9505 pasos y cierra
1875 rondas (antes 9499 y 1869). Los fallos monetarios bajan de 66 a 60 y las
acciones sin contrato de 55 a 54. Ninguna captura pierde pasos monetarios
aceptados ni rondas cerradas respecto de cdeabc4. Los resultados históricos no conceden OK de
ejecución. El resumen está en `nolimit-selection-adjustment-validation-20261015.json`.

Verificación final: 2434 pruebas y 264 subpruebas correctas, con tres advertencias.
La revisión independiente añadió negativos para propiedades de timeline colocadas
después de onComplete; las configuraciones pausadas o con otros callbacks no
autorizan una continuación.


## Bloqueos compartidos de la siguiente tanda (15 de octubre de 2026)

El registro recibido inicia una tanda de 72 pendientes y contiene nueve juegos
terminados antes de comenzar el décimo. No permite dar un resultado de los 72.
Se corrigieron estas familias, sin reglas basadas en nombres de juegos:

- Acuse de apuesta mejorada omitido: cuando hay selector y precio declarados en
  init, petición exacta y sobrecoste superior al giro normal, un débito conciliado
  confirma la operación. Un indicador explícitamente falso sigue rechazado.
  `ledger.json` distingue `DECLARED_PRICE_AND_DEBIT` de los acuses por indicador.
- Etiqueta activa después de pagar: el ledger puede conservarla como anotación
  si no hay menú desconocido, todos los contadores terminales están a cero,
  no hay pendingWin y el saldo acredita exactamente el premio positivo.
  La etiqueta no autoriza continuaciones; el retorno normal sigue siendo obligatorio.
- Presentaciones locales: se reconoce un callback incondicional habilitado en
  la lista que usa su runner. Las listas mutadas, referenciadas desde su propio
  inicializador, no recorridas o bloqueadas por otro callback desconocido no
  conceden permiso. Se respeta el alcance de parámetros que ocultan el nombre
  de la lista. La variante importada `default.timeline` usa las mismas reglas.
- Giro extra numérico: se descubren ambos literales de playerSelectedExtraSpin
  en el cliente de la sesión, preservando número o texto según su construcción.
  El 0 rechaza; el 1 solo se acepta con precio vigente, premio suficiente,
  descuento exacto, acuse de giro extra y transición a una familia gratuita
  conocida. Si la oferta anuncia destino debe coincidir; si lo omite se usa
  la modalidad confirmada por la respuesta, sin adivinarla antes.

Dos sesiones demo de descubrimiento contrastaron el rechazo (premio intacto y
saldo liquidado) y la aceptación (win negativo igual al coste cotizado).
Las fixtures reducidas `nolimit_numeric_extra.json`, `nolimit_modifier_debits.json`
y `nolimit_paid_annotation.json` eliminan credenciales, identidades de sesión y
matrices gráficas. El descubrimiento queda separado de una certificación de OK.

Después del débito confirmado, una continuación gratuita consume el giro pagado
incluso si el contador de giros regulares es cero. Los pasos posteriores con
indicadores persistentes de ese extra requieren enlaces actuales e incondicionales
del cliente. La fase EXTRA_SPIN se excluye de ese permiso: toda nueva decisión
necesita una cotización nueva. Los marcadores internos se eliminan de la entrada
del servidor y no se aceptan si aparecen en la respuesta original del HAR.

Pruebas demo nuevas: Breakout obtuvo OK con 8/8 modos; Dead Men Walking con 9/9;
Das xBoot con 3/3. Catfish Hunters avanzó a 8/10 y conserva una variante yes/no
pendiente; Das xBoot 2wei conservó un respin de torpedo pendiente en el giro normal.
Las otras familias del registro no se convierten en OK por estos cambios.


La comparación con dacf0eb usa las mismas 1141 capturas y clientes exactos:
9526 pasos aceptados y 1894 rondas cerradas (antes 9505 y 1875); 39 fallos
monetarios (antes 60); 3 acciones todavía sin contrato (antes 54). Ninguna captura
pierde pasos aceptados ni rondas cerradas. Los tres pasos de acción pendientes
son dos GAMBLE_FIFTY_FIFTY y un SUPER_FREESPIN_END; otros problemas de dinero o
inicialización se cuentan por separado. Son resultados históricos, no cobertura
de todas las ramas de todos los juegos. El resumen sin sesiones está en
`nolimit-followup-validation-20261015.json`.

Verificación final de esta tanda: 2471 pruebas y 264 subpruebas correctas, con
tres advertencias. La revisión independiente agregó negativos para callbacks
que modifican su propia lista o impiden llegar a la acción posterior.


## Ofertas yes/no repetidas y respin de torpedo (15 de octubre de 2026)

La captura playin.com-2026-10-15T09-19-11-551Z.har se identifica por los recursos
DasxBoot2/1.0.440. Contiene 73 intercambios correlacionados, diez raíces pagadas,
seis aceptaciones playExtraSpin=yes y un rechazo playExtraSpin=no. No contiene
init. El analizador conserva MISSING_INIT y no concede OK offline. Para las
pruebas del ledger se usa una declaración de otra demo de la misma versión;
el saldo de entrada de la primera ronda se deriva como contexto de prueba,
sin presentarlo como un saldo inicial grabado. Las siguientes rondas sí enlazan
con los saldos de cierre observados. La fixture reducida está en
`tests/fixtures/nolimit_literal_extra.json`; no incluye identidades ni credenciales.

Se incorporó el dialecto yes/no cuyo destino es la fase que ofrece el giro:
la aceptación exige precio vigente, descuento exacto del premio, EXTRA_SPIN,
isExtraSpin=true, un giro restante y retorno a esa fase. Una nueva oferta obtiene
una cotización nueva. En el rechazo puede persistir isExtraSpin=true si ya había
un giro extra en la historia; por sí solo ese indicador no significa aceptación.
El rechazo exige delta cero, NORMAL, acumulado consistente y saldo liquidado.
No se inventa un destino si la oferta carece de una fase de retorno demostrada.

La continuación pagada y sus pasos posteriores usan la misma prueba monetaria
y los enlaces actuales del cliente, separados de futuras decisiones EXTRA_SPIN.
El contrato exportado incluye literal_extra_spin_monetary_contract; un contrato
antiguo sin esa regla no valida las elecciones nuevas.

El reconocedor de efectos admite una condición solo cuando ambos brazos prueban
la misma acción sin argumentos, además de callbacks onComplete de timelines
activos asignados. No ejecuta ni adivina el valor de la condición. Excluye cuerpos
de funciones diferidas, accesos encadenados/computados/desconocidos al timeline,
pausas y escalas de tiempo dinámicas o no positivas.

En una sesión demo nueva, Das xBoot 2wei obtuvo OK con 9/9 modos, elecciones,
liquidaciones y retorno normal. Su contrato exportado pasó la validación común
y la del proveedor. Una comprobación adicional de Catfish Hunters conservó
PARCIAL al ofrecer un extra sin fase de retorno demostrada; no se fuerza ese caso.

Verificación final: 2494 pruebas y 264 subpruebas correctas, con tres
advertencias. La revisión independiente añadió negativos para ternarios
dentro de funciones no invocadas y cancelaciones encadenadas u opcionales
de timelines; todos quedaron rechazados antes de publicar.


## Giros extra repetidos (2026-10-15)

El ejecutor prueba rechazar y después acepta cada oferta asequible hasta cierre
normal monetario, usando la cotización actual y los fondos del premio pendiente.
Las dos opciones cubiertas no bastan para dar la cadena por completa.
Ver política, evidencia y límites en [NOLIMIT_PRIMITIVES.md](NOLIMIT_PRIMITIVES.md#giros-extra-pagados-y-agotamiento-de-fondos-2026-10-15).
La regresión de transporte simulado recorre 501 descuentos con libro monetario
real; no se presenta como una ejecución remota del catálogo.


### Captura BRICK SNAKE 2000 de 2026-10-15 16:37 UTC

Primitiva nueva: `CLIENT_BOUND_SETTLEMENT_BUTTONS`; dominio derivado de enlaces
cliente, botones y predicado de accesibilidad de la raíz. El formato usa `zeroBet`
con apuesta cero y `selectedIndex` string. Tres decisiones de la conexión sin init
quedan como evidencia contextual; la otra conexión valida 17 pasos y cinco cierres.
Dos demos nuevas finalizaron OK con exportación lista; el detalle y los límites
figuran en [NOLIMIT_PRIMITIVES.md](NOLIMIT_PRIMITIVES.md#selecciones-vinculadas-a-botones-y-liquidación-2026-10-15).


## Aprendizaje con Aislador (2026-10-15)

La extracción, las nuevas primitivas, la comparación de 1141 capturas y la
muestra de once sesiones nuevas están documentadas en
[NOLIMIT_PRIMITIVES.md](NOLIMIT_PRIMITIVES.md#familias-extraídas-con-aislador-2026-10-15).
El libro monetario conserva prioridad para los premios de paso ya contrastados;
un total del panel no sustituye automáticamente esa interpretación.


## Comparación y ejecuciones del 16 de octubre de 2026

La tanda de los 58 pendientes y dos repeticiones por familias (once y cuatro)
dejaron el catálogo en **95 OK, 44 PARCIAL y un ERROR**, frente a 82/57/1.
Los OK anteriores se conservaron. Catfish, las variantes Duck Hunters,
Disturbed, Gator Hunters 2, Jingle Balls, Walk of Shame, Home of the Brave y
Serial forman parte de los nuevos OK; la lista completa está en el resumen.

Las mismas 1141 capturas congeladas no muestran regresiones monetarias o de
cierre con las primitivas finales. El análisis offline no cambia estados OK.
Las capturas siguen privadas y las nuevas fixtures son reducidas o sintéticas;
los tests de fuentes públicas usan un caché opcional, sin publicar los bundles.

La interpretación vigente de contadores, extras, señales fijas, contexto demo
verificado y exportación de acciones está en
[NOLIMIT_PRIMITIVES.md](NOLIMIT_PRIMITIVES.md#cobertura-por-familias-y-verificación-del-16-de-octubre-de-2026).
El resumen verificable está en
[nolimit-bulk-validation-20261016.json](nolimit-bulk-validation-20261016.json).
Los ejemplos y límites fechados anteriormente documentan sus versiones; no
sustituyen las condiciones actuales ni certifican juegos pendientes.
