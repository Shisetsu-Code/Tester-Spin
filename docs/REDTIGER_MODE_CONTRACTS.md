# Red Tiger: tablas mixtas y modos pagados

La tabla `mathModes` puede contener a la vez `featureBuy`, `chanceIncrease` y
`stateSwitch`. Antes se exigía que todas sus entradas fueran compras; eso borraba
la declaración de compra cuando había otros modos. Ahora se contrasta el
subconjunto `featureBuy` con la tabla `featureBuy`, conservando precios e IDs.
Un tipo desconocido o precios de compra contradictorios no se acepta.

Los modos no normales sólo se ejecutan cuando ambas tablas actuales coinciden
exactamente en nombre, identificador `gameMode` y multiplicador de precio.
`chanceIncrease` se registra como `ANTE_BET`; `stateSwitch` se conserva aparte.
No se cuentan como compras. Los modos sin contrato quedan pendientes y no se
eliminan como metadatos para obtener OK.

Cada ejecución exige acuse del mismo `gameMode`, apuesta base concordante,
débito de apuesta por multiplicador y crédito exacto del premio. Después se
comprueban dos giros normales. El contrato exportado conserva identificador,
precio, tipo, fuente y versión del recibo.

Una respuesta con `mode={active:false}` puede ser un giro ordinario, pero sólo
se reconoce mediante débito, liquidación y avance de ronda independientes.
Otros campos en ese objeto, `active=true`, estados desconocidos o elecciones
pendientes siguen bloqueando el cierre.

La comprobación actual del modo de aumento de probabilidad devolvió el mismo
ID solicitado, stake base 2, débito 6 con multiplicador 3 y premio 2.40 pagado.
Es evidencia del contrato; el título del juego no interviene en la detección.

También se reconocen respins incluidos en una ronda pagada y liquidada con
estado persistente booleano, siempre que el resto de componentes sean conocidos
y exista avance de ronda y liquidación independiente. El NSP puede omitir stake
si game.win lo declara: sus líneas tienen esquema cerrado, sus multiplicadores
suman nsp.winMul y su pago coincide con game.win.total. El multiplicador de la
apuesta total se valida aparte con stake; no se supone que use la misma unidad
que el multiplicador de las líneas. Las opciones pendientes siguen bloqueando.

La verificación nueva recuperó 17 OK respecto del estado inicial: el proveedor
quedó en 385 OK, 8 parciales y 3 errores. Incluye una corrida de los 28 afectados
y pruebas posteriores de las familias corregidas; no equivale a repetir los
368 OK históricos. Las capturas permanecen locales.
