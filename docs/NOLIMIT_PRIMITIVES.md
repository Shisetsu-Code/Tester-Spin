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
