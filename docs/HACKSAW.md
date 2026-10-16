# Hacksaw: validación de catálogo y ejecución

El catálogo público oficial /games/slots contiene 186 juegos y coincide con las
186 filas locales. Se añadieron Wicked Grin y Le Vampire y se actualizó el snapshot
distribuido. Esta coincidencia no autoriza borrar registros ni certifica otras
categorías del sitio.

## Contrato común de OK

La autenticación nueva declara bonusGames, sus selectores y betCostMultiplier.
El constructor FeatureBuyItem del cliente de esa versión determina el tipo;
compras y FeatureSpins permanecen separados. Se rechazan dominios ausentes,
selectores duplicados, precios inválidos y roles sin demostrar. Menús alternativos
literales se contrastan por selector: un tipo conflictivo impide certificarlo.
No hay listas de juegos ni deducción de compra por precio o por alias.

Cada ronda conserva ledger.json. El coste debe ser la apuesta base multiplicada
por el factor declarado; el saldo debe reflejar ese débito. Los eventos wa suman
el pago y awa debe coincidir con el acumulado. Los importes usan enteros exactos,
en la moneda actual. La liquidación debe conservar saldo inicial menos coste más
premio; cargos o créditos auxiliares, promociones y jackpots sin contrato quedan
pendientes. No se pretende recalcular la matemática de los símbolos del juego.

Las continuaciones no envían bets, conservan roundId y no vuelven a cargar la
compra. Cuando el cliente solicita updateBalance=false, una respuesta intermedia
puede omitir el saldo; no se inventa una observación. El saldo al pagar y al cerrar
sigue siendo obligatorio y la liquidación final debe explicar todo el importe.

Después de completar las opciones se ejecutan, en la misma sesión, dos rondas
BASIC consecutivas nuevas, cerradas y contabilizadas. Sus IDs deben ser distintos
entre sí y de la última función. Un premio natural o una elección reinicia el
contador de rondas normales; estados desconocidos detienen la comprobación.
return-to-base.json conserva las respuestas y el resultado. Los límites de pasos
y pruebas permanecen acotados. Un completed aislado ya no acredita OK.

Los contratos históricos sin hacksaw/verified-runtime/v2 y sin prueba monetaria
no se pueden promover. La suite y la auditoría anterior habían demostrado que
los OK históricos no incluían todos estos requisitos; esos resultados se han
reemplazado con una pasada nueva completa, no con una reinterpretación de la marca.

## Resultado de la repetición

Se ejecutaron los 186 juegos por el ejecutor normal en una cola automática de un
trabajador. Se aprendieron las variantes por grupos y se repitieron juntos los
pendientes afectados; no se recorrió cada juego mediante el fuzzer.

Resultado nuevo: 183 OK, 3 PARCIAL,
0 ERROR. Todos los OK tienen retorno CONFIRMED.

Una revisión independiente recalculó desde los archivos 885
rondas pagadas y 372 rondas de retorno, contrastando
dominios, precios, moneda, saldos, acumulados, cierre e identidades. Cero
discrepancias en los 183 OK revisados.

Pendientes actuales:

- Beam Boys: Hacksaw: declaración de opciones sin clasificación completa
- Mystery Motel: Hacksaw: declaración de opciones sin clasificación completa
- Tasty Treats: Hacksaw: declaración de opciones sin clasificación completa

Verificación de código: 2047 pruebas correctas y tres warnings preexistentes.
El ejecutable final del acceso directo del escritorio está actualizado y su
arranque se comprobó. SHA256: 350a0d5390964c3af9b8fa896b8d1c62d944a3f98693c9b237cf9b321df8332c.

Los HAR, sesiones y capturas originales permanecen locales. La evidencia de esta
pasada se conserva en hacksaw-final-evidence.json y en el checkpoint local.

## Compatibilidad de clientes y contexto de apuesta: 16 de octubre de 2026

Se reconocen los menús alternativos literales y las variantes del constructor
que expresan FeatureSpin mediante un booleano o un tipo nullable, únicamente
cuando el getter o consumidor de esa misma versión prueba su significado.
Los roles contradictorios y tipos desconocidos siguen sin certificar.

Algunos clientes publican customBetData durante init y cambian ese contexto
según la opción del menú. El extractor enlaza la publicación del cliente con
updateCustomBetData del SDK y bets[].customData. Conserva el contexto por
selector y el contexto base para los dos giros de regreso; no lo deduce del
nombre del juego. Sólo admite literales finitos y rechaza reasignaciones,
selectores sin contexto y sustituciones de betAmount. El contrato exportado
conserva los hashes del cliente y del SDK que sustentan esa relación.

Tres juegos pendientes se ejecutaron con sesiones nuevas: Mystery Motel,
Tasty Treats y Beam Boys pasaron a OK. El estado local quedó en 186 OK, sin
parciales ni errores. Los otros 183 OK son resultados anteriores conservados;
esta reparación no supone una nueva ejecución de todo el catálogo.
