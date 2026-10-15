# Nolimit City: primitivas compartidas

El objetivo es aprender operaciones del proveedor, no excepciones por juego.
La detección de una opción no depende de poder ejecutar todas sus fases.

## Separación vigente

| Componente | Evidencia que interpreta | Lo que no afirma |
|---|---|---|
| declarations.py | Tabla, selectores permitidos, precios, apuestas y habilitación de init | No certifica ejecución ni cobertura |
| state.py | Sesión nueva, catálogo, fase, menú pendiente y estado terminal | Reconocer una fase no autoriza una acción |
| operation_fields.py | Premios, modificadores y acuses de la operación | Un campo ausente no se convierte en un indicador positivo |
| runtime.py / choices.py | Transporte, continuaciones y dominios de elección contrastados con cliente/servidor | Una fase desconocida no dispara zeroBet automáticamente |
| RoundLedger | Petición actual, coste, acumulado, descuentos aprendidos y saldo | No certifica elecciones opcionales que no se recorrieron |
| protocol.py | Empareja mensajes de un HAR y utiliza el mismo RoundLedger | El análisis offline nunca concede OK de ejecución |

Una compra de tipo conocido conserva su categoría y cantidad aunque un
additionalTypes desconocido deje executable=false. Esa opción sin validar
sigue impidiendo OK. Los tipos desconocidos conservan su identidad.

## Catálogo, fase y acción

Una sesión inicial debe confirmar init=ok, isRestoreState=false, ambos modos
NORMAL, remainingFreeSpins=0, ausencia de flags activos y contadores presentes
en cero. No necesita imitar el formato monetario de otro juego.

Los catálogos se contrastan exactamente con los dominios iniciales: available,
selectores completos, compras completas o categorías derivadas. No se aceptan
subconjuntos arbitrarios como un catálogo completo. Las fases conocidas y sus
alias conservan la identidad del estado. Su observación no elimina las
condiciones de cada acción: contador positivo, precio, dominio o acuse.

El ledger puede registrar importes de una fase desconocida sin cerrarla.
La continuación automática se bloquea; solo el descubrimiento acotado del
cliente puede aportar una elección ejecutable. Sin ese contrato queda PARCIAL.

## Dinero y cierre

Los alias explícitos del premio del paso deben concordar. En respuestas sin
ese alias, totalSpinWinnings solo se resuelve dentro del ledger con la petición
actual: debe coincidir con el incremento o con el acumulado de la ronda.
Una disminución no se admite por esa regla; necesita el contrato específico
de descuento, como el giro extra previamente cotizado.

Los indicadores de modificador presentes deben concordar. Si un giro normal
carece de esos indicadores, la petición debe ser exactamente normalBet con la
apuesta declarada. Se comprueban también el débito y la liquidación; no se
fabrican acuses de compra ni de modificador.

El cierre exige NORMAL, al menos un contador restante explícito en cero,
todos los demás contadores presentes en cero, sin pendingWin ni menú/fase
sin resolver, y saldo liquidado. Se requieren dos rondas normales de retorno.
collect exige la construcción de petición demostrada por el cliente y acuse
del servidor, además de conciliar el dinero. Su alcance es cobro, no todas
las alternativas opcionales del gamble.

## Cómo medir una corrección

Antes de modificar una primitiva se reproduce el grupo con evidencia local.
Después se ejecutan esas mismas capturas, negativos de seguridad del cierre,
la suite y una tanda real del proveedor. Las capturas de sesión permanecen
locales; las fixtures publicadas se reducen y eliminan credenciales e identidad.

La primera comparación offline cubrió 134 inicializaciones disponibles de la
tanda de 140: 83 aceptadas antes y 134 después, sin regresiones en ese control.
Eso demuestra 51 bloqueos de inicialización corregidos, no 51 juegos OK.
La comparación de respuestas conservó todas las normalizaciones antes válidas
y amplió las reconocidas de 2848 a 2914. Cada OK requiere ejecución actual.

## Verificación del 14 de octubre de 2026

Se ejecutaron los 140 juegos del catálogo y luego se repitieron los 94 que
no habían obtenido OK, con las primitivas automáticas definitivas. El resultado
combinado es 52 OK, 85 PARCIAL y 3 ERROR, frente a 19/117/4 antes. Los 19 OK
anteriores se conservaron; 33 juegos adicionales obtuvieron OK. Es una tanda
completa más una repetición del grupo afectado, no una única ejecución inmutable.

Los 52 OK se reconstruyeron offline con el ledger actual: 320 rondas y 1691
pasos, sin fallos de cierre, saldo o retorno normal. Sus contratos exportados
se regeneraron y validaron con el esquema final. La suite completa pasó:
2361 pruebas y 264 subtests; hubo tres advertencias.

Las continuaciones automáticas usan estados, contadores y cotizaciones
independientes del dialecto monetario. El ejecutor actúa sobre la observación
validada por el ledger y conserva la respuesta original para exigir evidencia
explícita de que un respin no es un giro extra de pago. Reconocer una fase o
un catálogo no autoriza por sí solo una continuación.

Quedan 56 casos sin un dominio de elección único demostrado, 10 sin acuse de
compra/modificador, 9 con campos monetarios todavía no aprendidos, 6 sin
identidad/versión de cliente demostrada y 4 parciales de otros contratos.
Los tres ERROR son discrepancias entre saldo, coste y liquidación; se mantienen
como errores. Estos grupos orientan el siguiente aprendizaje por primitivas;
no justifican excepciones por nombre de juego ni convertir pendientes en OK.


## Familias adicionales y ejecución del 15 de octubre de 2026

Se eligieron cinco pendientes al azar, sin reemplazo, de 72 capturas disponibles
(semilla 461283589). Se compararon 20 intercambios de HAR con las versiones
oficiales de sus clientes; todos se correlacionaron sin advertencias.

El ejecutor ahora incorpora `client_actions.py`. Reconoce enlaces acotados del
cliente actual: mapas de flujo IDLE con continuación incondicional, controladores
registrados en ZERO_BETS y animaciones IDLE con ramas explícitas. La fase viene
del servidor; los nombres de juego no deciden la acción. Las variantes no
demostradas siguen bloqueadas. No se ejecuta JavaScript descargado.

Cada acción descubierta guarda estado, petición y SHA-256 del cliente en
`automatic-action.json`. La respuesta debe confirmar como mode la fase que se
solicitó continuar. No se permite convertir una cotización de giro extra en una
continuación gratuita. El premio cero tampoco impide una avalancha cuyo cliente
demuestre la continuación.

Se agregó el alias explícito thisAvalancheWinnings, contrastado con los demás
alias presentes. totalAvalancheRoundWinnings y totalRespinWin no se suman como
premios de paso. Una subronda conserva el contador de la ronda exterior y no
puede cerrar con respinActive pendiente. La ausencia de balance en una respuesta
intermedia no se interpreta como saldo cero.

El catálogo admite la categoría FREESPIN cuando está respaldada por el tipo de
las compras declaradas, separada de sus selectores comerciales. playerFSSelection
se interpreta como acuse de una elección únicamente en la fase de pick declarada
por el cliente; un -1 durante NORMAL no activa una elección.

| Referencia | Familia observada | Resultado de la comprobación real |
|---|---|---|
| Infectious 5 xWays | Catálogo por categoría, elección y continuación de la modalidad elegida | OK; 4/4 modos, 79 pasos |
| Loner | Compra que enruta a otra modalidad y continúa automáticamente | PARCIAL; 5/9 modos; pendiente FEATURE_TICK_TICK_BOOM |
| Fire In The Hole | Avalancha estructural con premio cero y otro alias monetario | OK; 4/4 modos, 78 pasos |
| Golden Shower | Avalancha automática y comprobación previa a oferta de giro extra | PARCIAL; 5/9 modos; pendiente decisión de pago EXTRA_SPIN |
| Harlequin Carnival | Respins dentro de tiradas gratuitas | OK; 2/2 modos, 21 pasos |

Son resultados de comprobaciones por muestra y repeticiones tras corregir las
primitivas, no una nueva tanda de todo el catálogo. Los OK exigen las compras
declaradas, las elecciones cubiertas y retorno normal. Las dos modalidades
pendientes conservan evidencia local para aprendizaje posterior. En Golden
Shower el cliente usa playerSelectedExtraSpin numérico; no se equipara al
contrato playExtraSpin yes/no sin verificar descuento, respuesta y liquidación.

Las fixtures reducidas de esta muestra están en nolimit_reference_five_2.json
y nolimit_client_action_bindings.json, dentro de tests/fixtures. No incluyen
credenciales ni HAR completos. Las pruebas contrastan los estados reales,
importes, enlaces de cliente y negativos de continuación y cierre.

Verificacion final del cambio: 2385 pruebas y 264 subpruebas correctas, con
tres advertencias. La revision independiente produjo un negativo adicional:
una condicion envolvente no reconocida en una animacion del cliente bloquea
la continuacion; no se extrae una rama interna fuera de su ciclo demostrado.

La repeticion final tambien encontro el respin del juego base durante un giro
de retorno. Se incorporo la rama demostrada del mismo cliente, con prueba
negativa de condiciones envolventes. El reconocedor final reproduce 16 estados
reales de respin normal y gratuito; Harlequin volvio a obtener OK.

## Consolidacion del corpus

El contrato compartido, la correccion de espacios de nombres y los resultados
comparados estan en [NOLIMIT_CORPUS.md](NOLIMIT_CORPUS.md).


## Giros extra pagados y agotamiento de fondos (2026-10-15)

Las ofertas cotizadas `playExtraSpin` (yes/no) y `playerSelectedExtraSpin`
(0/1, conservando el tipo declarado por el cliente) usan una política compartida:
se prueba rechazar una vez y en otra ronda se acepta cada oferta que pueda pagarse.
Se vuelve a leer precio y fondos en cada oferta; haber cubierto ambas decisiones
no interrumpe la cadena. En estas variantes el servidor descuenta del premio
pendiente (`accumulatedRoundWin`), no del saldo general. Una oferta que ya no se
puede pagar conserva la aceptación como opción declarada y sólo permite rechazar;
no inventa evidencia de una aceptación ejecutada.

`repeat_purchase_probe` registra compras aceptadas, gasto, estado y motivo terminal.
Sólo la liquidación NORMAL reconciliada por el libro monetario completa la prueba:
`INSUFFICIENT_PENDING_PRIZE` o `SERVER_CLOSED_ROUND`. Cada cadena nueva restablece
PENDING y elimina el motivo anterior, conservando los contadores acumulados.
Cancelación, error o límite sin cierre no prueban agotamiento. La cobertura común
y la exportación verifican esta prueba además de ambas decisiones.

El límite de 500 continuaciones sin progreso pagado se renueva por cada descuento
extra comprobado. Así permite cadenas largas sin quitar el freno a ciclos sin
progreso; siguen vigentes cancelación y los tiempos de espera de transporte.
La cantidad comercial de compras del juego no aumenta por comprar giros extra.

El bootstrap FANPAGE_DEMO conocido no declara un control para reducir el saldo.
No se envían parámetros supuestos, no se falsifica el saldo local y no se gastan
fondos artificialmente sólo para agotarlo. Si se descubre un control real, su
aplicación deberá comprobarse contra el saldo devuelto por el servidor. Bajar el
saldo general no reduce el premio pendiente que financia estas ofertas. Cada
prueba de juego abre una sesión demo nueva y cierra su conexión al terminar;
reiniciar una sesión no conserva una ronda incompleta ni la convierte en OK.

Validación automatizada: política de ambas decisiones, cotizaciones sucesivas,
fondos insuficientes, cierre del servidor, interrupción, nueva cadena tras otra
completa, cobertura/exportación y ejecutor con libro monetario real sobre transporte
simulado de 501 compras (más de 1000 intercambios). No certifica por sí sola un
catálogo ni proveedores todavía no integrados con esta política.


## Selecciones vinculadas a botones y liquidación (2026-10-15)

`CLIENT_BOUND_SETTLEMENT_BUTTONS` reconstruye el dominio sin tablas por juego:
modo actual → presentación IDLE registrada → panel activo → botones → callbacks
→ literal enviado por `pickAndClickBet` → plantilla SDK `zeroBet`, apuesta cero y
`selectedIndex` convertido a string. Un predicado del modelo y el selector de la
compra actual determinan qué botones son accesibles. Los nombres del juego, fase,
selector, clase y métodos no son constantes del reconocedor.

El patrón comprobado incluye una confirmación intermedia y visibilidad condicional.
Se reconocen expresiones completas: envíos directos, habilitación efectiva, callbacks
sin reasignaciones, cronología sin cancelación y retorno de la confirmación al panel.
Una mera coincidencia textual, una llamada bajo condición falsa o un botón después
deshabilitado no declaran opciones. Otras formas de interfaz quedan sin resolver.
El alcance actual requiere una raíz PURCHASE, premio pendiente positivo y el
indicador de compra confirmado. No convierte cualquier pantalla binaria en apuesta.

La respuesta de esta familia no repite `selectedIndex`: el acuse exige entrada en
la fase solicitada y liquidación NORMAL sin contadores pendientes, con saldo
explícito; el libro monetario comprueba premio y saldo. Las pérdidas de una selección
siguen requiriendo el contrato firmado por el cliente, petición exacta y ajuste
limitado al premio pendiente. Esta elección se guarda como rama interna, sin
aumentar la cantidad de compras o antebets. La exportación requiere su descriptor
`bound_settlement_selection`.

El HAR de BRICK SNAKE 2000 (cliente 1.1.9) muestra opciones 0/1 en la compra normal:
0 conserva el premio y las aceptaciones 1 capturadas lo duplican. En la compra
Deluxe el cliente oculta 0 y sólo se exige 1. Esto se deriva del predicado del cliente,
no del nombre del selector. La captura tiene dos conexiones: la primera carece de
inicialización; sus tres decisiones se validan en rondas contextualizadas, sin
certificar toda esa sesión. La segunda contiene init y reconcilia 17 pasos, cinco
rondas y 12 continuaciones sin fallos. Dos ejecuciones remotas con sesión nueva
terminaron OK; en ambas apareció y se cubrió la elección Deluxe [1]. La cobertura
normal [0,1] procede del HAR y las pruebas, no de esas dos ejecuciones remotas.


## Familias extraídas con Aislador (2026-10-15)

Se usó [Aislador](https://github.com/Shisetsu-Code/Aislador) sobre capturas
pendientes guardadas. Una incompatibilidad de transporte dejaba opacos los
mensajes cuyo escritor declaraba `encoding: utf8`: se corrigió en Aislador y se
repitió la extracción. No se importó Aislador como dependencia del ejecutor.
Las capturas no se reenviaron: la verificación remota usó sesiones demo nuevas.

Las primitivas incorporadas son compartidas por el proveedor:

- Identidad de cliente: se conserva literalmente la versión oficial con sufijos
  publicados, tanto en transporte como auditoría. Nombre solicitado y nombre
  publicado deben coincidir; rutas, consultas e identidades ambiguas se rechazan.
- Mapa de flujo: una fase puede estar escrita como literal o enumeración.
  La clase activa y su ciclo deben seguir demostrando el envío incondicional.
- Dinero: `client_money.py` lee campos de premio y total del objeto retornado
  directamente por el parser de la misma versión del cliente. Rechaza callbacks
  anidados, claves duplicadas y mutaciones desconocidas. El campo elegido se
  contrasta con el acumulado independiente; nunca se deduce del saldo.
  Los campos de paso ya conocidos tienen prioridad si explican el acumulado:
  el total de un panel puede resumir otra subronda. El cliente sólo aporta la
  alternativa cuando esa interpretación conocida falta o no concilia.
  La vista normalizada distingue el total de sus componentes base, conservados
  en la respuesta original. El ejecutor y ambos lectores offline usan el mismo
  libro monetario con el cliente exacto explícito.
- Extra yes/no: la fase que ofrece el extra no determina necesariamente su
  retorno. Si el servidor cotiza un destino, el acuse debe coincidir. Si no lo
  cotiza, la respuesta de aceptación debe declarar un destino cuyo siguiente
  zeroBet esté demostrado en los enlaces del cliente actual. Se contrastan
  precio, descuento, acumulado, indicador y contador; el recibo guarda el destino
  realmente confirmado. No se eliminan sufijos de fases para adivinarlo.
  La variante anterior conserva su contrato cuando no hay enlaces alternativos.
- Contador: `game.freespinsRemaining` puede normalizarse sólo con el total
  exterior `remainingFreeSpins` explícito, entero y coincidente. Ausencia o
  contradicción no significan cero.

### Comprobaciones

Se compararon las mismas 1141 capturas congeladas con b1ba3f0 y estos cambios,
con cliente exacto para 1136. Se revisaron 9565 pasos en ambas versiones:
9534 pasos aceptados frente a 9526; 1901 cierres frente a 1894; 31 fallos
monetarios frente a 39. Ninguna captura perdió pasos aceptados ni cierres.
Persisten dos acciones sin contrato y las limitaciones previas de importación.
Son pasos históricos, no juegos certificados OK.

En sesiones nuevas de una muestra de once juegos, siete obtuvieron OK:

| Juego | Modos comprobados |
|---|---:|
| Fire in the Hole 2 | 7/7 |
| Mental 2 | 10/10 |
| Gator Hunters | 9/9 |
| Highway to Hell | 9/9 |
| Kitchen Drama: Sushi Mania | 1/1 |
| Monkey's Gold | 2/2 |
| Outsourced 2 | 11/11 |

Crazy Ex Girlfriend y Flight Mode siguen con acciones sin dominio demostrado.
The Border conserva una discrepancia entre premio de paso y acumulado en otra
modalidad; Gator Hunters 2 conserva una discrepancia monetaria de liquidación.
No se certifican por haber resuelto su bloqueo anterior. Las herencias complejas
de Mental, Dead Dead Or Deader y Duck Hunters 2 tampoco se autorizan por nombre.
No se ejecutó otra vez el catálogo completo.

Verificación: 2622 pruebas y 264 subpruebas correctas, tres advertencias previas;
71 pruebas correctas de Aislador. La revisión independiente contrastó negativos
de campos anidados, mutaciones y destino cotizado contradictorio. El resumen
sin sesiones está en `nolimit-aislador-validation-20261015.json`.
