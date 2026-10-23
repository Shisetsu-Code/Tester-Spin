# Verificación de parciales — 23 de octubre de 2026

## Alcance y resultado comprobado

Trabajo sobre `Shisetsu-Code/Tester-Spin`, a partir de `main` en
`50e71b76564675de9d6f68ae4a0ca7f2cd6d37c5`. Este informe acompaña las
correcciones de proveedores y sus regresiones. El inventario detallado está en
[`partial-verification-20261023.json`](partial-verification-20261023.json).

| Conjunto identificado | Verificado dentro del alcance descrito | Pendiente |
| --- | ---: | ---: |
| BGaming: 32 demos nuevas | 20 OK, 70 intentos auditados | 12 PARCIAL |
| Nolimit City: 31 parciales documentados | 3 OK | 28 PARCIAL |
| Yggdrasil: 8 casos identificados | 4 casos, con ejecución y revalidación diferenciadas | 4 pendientes |

Los recuentos describen los casos recuperables de esta investigación. **No son
una certificación de todos los parciales históricos.** El resumen del 16 de
octubre enumeraba 103 parciales, pero no se dispone de la base de datos de la
aplicación ni de todas sus capturas. La rama histórica de BGaming tiene 235 JSON:
se recuperaron 124 encabezados y 111 archivos grandes no entregaron contenido.
Su subconjunto accesible contiene 31 parciales; además se comprobó Wild Tiger
por la degradación documentada. No se equipara ese inventario al recuento antiguo
de 26.

Una sesión nueva OK sólo demuestra sus modos declarados, las opciones cubiertas,
la contabilidad y el regreso observado. No elimina una obligación histórica
desconocida, una rama natural que no apareció o una alternativa que no se ejecutó.
No se modificaron resultados antiguos para hacerlos coincidir con resultados nuevos.

## Cambios de producto

### BGaming

Se enlazan los selectores desde el control que los fija hasta la serialización de
la petición. El soporte nuevo cubre el reenvío HyperHive de dos argumentos,
compras por nivel en API-v2, variantes finitas con escala de apuesta y el
discriminador booleano de las dos compras de Red Hot Chilli Chickens. Los precios
deben proceder del contrato actual; encontrar un nombre de compra en el bundle
no basta.

El loader conserva el subdirectorio declarado por `resources_path`; esto corrige
la descarga del cliente de Wild Tiger 2. Se corrigió el análisis léxico de regex
después de una flecha. Las compras ya demostradas publican los aliases de
evidencia que consume la cobertura compartida. El cambio no convierte una compra
incompleta en una opción cubierta.

Los perfiles usan la generación de capacidades 3 y se contrastan con la fuente
actual. La caché sólo se reutiliza si la selección pertenece al dominio actual.
`init` usa los campos del bootstrap y del wire actual. Si una capacidad antes
conocida no puede demostrarse, se conserva como pendiente y se bloquean los
comandos de juego; un dominio vacío no produce un OK artificial.
La revisión añadió casos negativos para modificaciones de `payload.options`
antes de `JSON.stringify`, escapes a aliases, llamadas desconocidas y cambios del
lector de replay. Se conserva el lector real sólo cuando está enlazado y se
demuestra que no modifica el objeto enviado.

Los veinte resultados OK son: Alien Fruits 3, Blackbeard's Bounty, Book of Hidden
Tombs, Burning Chilli X, Chicken Fire, Clucking Hell, Divine Queen: Heart of Ice,
Dusty Duel, Hot Chilli Bells 100, Hot Chilli Bells, Johnny vs Chicken, Multi Rush,
Red Hot Chilli Chickens, Royal Fruits MultiLines, Temple of Power, Train Heist
Johnny Cash, Ultras, Wild Clusters, Wild Tiger 2 y Wild Tiger.

Wild Tiger 2 y Hot Chilli Bells cubren cinco configuraciones y dos modos por
configuración: diez intentos por juego. Chicken Fire cubre base, chance y tres
compras. Red Hot Chilli Chickens cubre base y ambas compras. El inventario JSON
conserva el número de intentos y la huella del archivo de evidencia de cada juego.

El diagnóstico posterior de Mystery Heist identificó un fallo de resolución del
loader: la ruta elegida por `SKIN_DIRS.basic` contiene `basic/` antes de la versión.
El bundle exacto declarado respondió HTTP 200; el resolutor y la ejecución de los
tres niveles de compra siguen pendientes en este checkpoint.

### Nolimit City

Golden Genie pasó a OK tras enlazar el parser activo, su getter inmutable, el
controlador registrado y el evento `zeroBet`. Roadkill pasó a OK tras resolver
un alias de enum importado cuyo export aparece después de asignar sus campos.
Disorder pasó a OK al distinguir un método de replay mediante la API real y su
guarda, conservando la oferta pagada ejecutable.

La revisión comprueba el registro completo de plugins y las escrituras de
`options.replay`; una sesión demo nueva por sí sola no demuestra que esa propiedad
sea inmutable. No se excluye un handler si un segundo plugin puede reemplazar la
API o si se fuerza la opción de replay.

| Juego | Modos | Opciones | Retorno |
| --- | ---: | ---: | --- |
| Golden Genie | 2/2 | 3/3 | Dos normales consecutivos |
| Disorder | 8/8 | 21/21 | Dos normales consecutivos; extra spin aceptado y rechazado |
| Roadkill | 4/4 | 7/7 | Dos normales consecutivos |

Los otros 28 conservan su causa concreta en el inventario. Predominan ciclos de
presentación/continuación todavía no demostrados; también hay precios de extra
spin con múltiples opciones, catálogos terminales sin equivalencia probada,
contextos de CAP_MODE, un acuse de compra contradictorio y un error explícito del
servidor. Ninguno se convirtió en OK por ignorar la fase o el acuse.

### Yggdrasil

| Caso | Evidencia y alcance |
| --- | --- |
| Jungle Books | Demo nueva; cola host/guest reconstruida y agotada; retorno base confirmado. |
| Nice Catch DoubleMax | Cuatro modos y siete opciones; revalidación de la captura con contrato final de cash/ANTE y liquidación. |
| Nice Catch 2 DoubleMax | Captura real revalidada offline: tres modos y cobertura 5/5. El archivo original sigue PARCIAL; el nuevo registra procedencia y cero peticiones de red. |
| Pirates 2 Mutiny | Dos verificaciones que conservan el prefijo capturado, restauran la misma sesión y añaden una ronda nueva; MUTINY/CASCADE y retorno comprobados. |

Se reconstruyen las rondas a partir de la geometría, las tablas de premios, las
colas y los contadores demostrados por el cliente. El cierre exige contabilidad
y agotamiento; no depende sólo de una etiqueta terminal. El contrato de Pirates
permanece acotado: no acepta TSUNAMI, FS, CANNON ni multiplicadores activos sin
su prueba correspondiente.

La revisión independiente reprodujo cuatro falsos positivos de fuente en
Nice Catch 2: sumas añadidas a `totalFreeSpins`, `leftUpdate` y `totalWin`, y una
asignación de vidas `30` que coincidía por prefijo con `3`. Las expresiones e
inicializaciones se contrastan completas. Las cuatro mutaciones se rechazan;
la fuente oficial de 2.807.349 bytes y sus nueve rondas válidas siguen aceptándose.
Una modificación coherente de tres a cuatro vidas también sigue soportada.

**El alcance de Nice Catch 2 es el dominio de modos pagados y los controles
actuales resueltos; GAMBLE no se ejecutó.** La política de aceptar la resolución
sin coste mediante COLLECT ya existía en la base. El 5/5 suma tres opciones de
modo y dos opciones de la declaración de compras, no cinco ramas distintas de
juego ni cobertura de GAMBLE.

El contrato nuevo CommonAPI cubre peticiones tipadas, colas, progreso por apuesta,
formas de ganar y premios asociados a wilds. Está ligado a las fuentes completas
revisadas de loader, engine y extensiones; los precios siguen procediendo de la
configuración actual. Una versión distinta del cliente queda pendiente de
revisión. Las regresiones rechazan reasignaciones de funciones y cambios de tipo
en los metadatos de contadores, además de premios incompatibles con la geometría.

**Badger Miners sigue PARCIAL.** La captura nueva permitió corregir el reparto
de premios por las combinaciones que pasan por cada wild y el factor de su
columna. El prefijo capturado se revalidó y se continuó la misma sesión: C pagó
exactamente 3,10. El segundo probe BASIC activó un booster aún sin contrato,
por lo que no se confirmó el retorno de BUY. Se conserva el resultado PARCIAL
original y no se enviaron compras adicionales para buscar otra muestra.

Football Glory tiene una muestra actual válida, pero no apareció la colección
natural que motivó su parcial histórico. Lucky Apocalypse carece de launcher demo
actual identificado. Golden Chip Roulette presentó un launcher de producción,
sin contrato DEMO demostrado: no se enviaron apuestas.

## Otros parciales investigados

- **Pragmatic:** Book of Monsters, Bubble Up! y Money Stacks tienen muestras
  actuales válidas. No cierran las obligaciones históricas de modos naturales o
  niveles superiores ausentes de las capturas disponibles.
- **Playtech:** Mighty Midas completó tres rondas demo locales con contabilidad
  reconciliada. Mantiene inventario de bonus/jackpot sin contrato completo.
  Adventures in Wonderland usa CommonOpen/Load/Place/Close y su contrato de
  entrada sigue sin enlazar. Se conservaron clientes y capturas actuales; no se
  confundió el motor demo local con ejecución de servidor.
- **Belatra:** la página oficial de Princess Suki responde, pero el destino demo
  declarado devuelve 503 y no entrega configuración de juego.
- **RedTiger/RubyPlay y resto de Pragmatic:** faltan los nombres y las capturas
  de los parciales del resumen histórico. No se sustituyeron por juegos elegidos
  arbitrariamente.

El diagnóstico remoto de Playtech
[`39929250805`](https://github.com/Shisetsu-Code/Tester-Spin/actions/runs/39929250805)
falló antes de iniciar pasos, sin runner ni artefactos. Ese resultado no contiene
una ejecución de tests y no demuestra un fallo del código. El diagnóstico local
posterior usó transporte TLS verificado, sin cambiar la confianza persistente del
sistema.

## Integridad de evidencia y validación

Se comprobaron independientemente las huellas de los veinte archivos BGaming y
sus setenta intentos: estado terminal, débito esperado y prueba CONFIRMED con al
menos dos probes base. Los snapshots Yggdrasil conservan hashes y distinguen
captura original, revalidación offline y continuación de la misma sesión.

Algunos archivos de retorno reaparecieron con `RUNNING/0` y fecha anterior después
de una escritura `CONFIRMED/2` leída correctamente. No se reprodujo un fallo de
la función del producto en 240 pruebas locales. Sí se reprodujo el mismo efecto
fuera del repositorio mediante recepción diferida de rsync. Eso demuestra un
mecanismo plausible del entorno, no identifica la transferencia concreta que
alteró cada archivo histórico. No se aplicó un parche especulativo ni se
reescribieron las pruebas afectadas.

Las nuevas capturas se realizan en un directorio temporal y se archivan una vez
terminadas. Para BGaming se preservó también el valor real devuelto por el
verificador, junto con requests/respuestas y hashes, sin editar su contenido.

La ejecución integrada de este checkpoint dio **4.242 pruebas aprobadas,
282 subpruebas aprobadas, 29 omitidas y un fallo de entorno**. El test de
aislamiento necesita crear un cgroup, pero `/sys/fs/cgroup` no permite hacerlo
en este entorno. No se relajó el aislamiento ni se convirtió ese fallo en un
resultado aprobado. La verificación completa debe repetirse en un runner con
cgroups delegados antes de dar por superado ese gate.

La suite completa de BGaming, tras las correcciones de revisión y caché, dio
**418 passed y 16 subtests passed**, sin fallos.

Después de la revisión se repitieron Book of Hidden Tombs y Hot Chilli Bells
con sus perfiles previos y demos nuevas. El adaptador exhaustivo completó 4/4 y
10/10 intentos, respectivamente. Se auditó el archivo final: los catorce débitos
coinciden y los catorce retornos conservan CONFIRMED con dos probes base
consecutivos. Esta ejecución conserva requests y respuestas HTTP; la captura HAR
opcional del navegador no estuvo disponible en esa invocación.

También se contrastó el bundle completo de Disorder: la fuente original permite
excluir 1.074 bytes del handler exclusivo de replay; al forzar
`window.nolimit.options.replay` dentro de `getOptions`, no se excluye ningún byte.
El normalizador completo, su consumidor de analytics y las publicaciones por
referencia tienen regresiones negativas para mutaciones y aliases.

Los contratos nuevos tienen regresiones positivas y negativas. No se desactivó
TLS, no se usaron sesiones con dinero real, no se publicaron capturas con sesiones
y no se modificó `main`.
