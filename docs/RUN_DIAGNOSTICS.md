# Tester-Spin: pruebas, diagnóstico y árbol de tiradas

## Flujo de trabajo

1. Abrí **C:\Proyectos\Tester-Spin\Abrir-Tester-Spin.cmd**. Reiniciá el programa después de recibir cambios de código.
2. Elegí un proveedor. Los protocolos y las compras se ejecutan dentro de su propio módulo.
3. Para la primera revisión, seleccioná 1–5 juegos y configurá **1 repetición por modo**, **1 juego simultáneo** y **1 segundo de separación entre juegos**. El timeout inicial puede mantenerse en 30 segundos. La separación entre juegos no equivale a un límite entre cada request.
4. Pulsá **PROBAR SELECCIONADOS**. El ejecutor existente recorre SPIN y los modos que ese proveedor puede ejecutar; no interpreta una compra desconocida como válida.
5. Seleccioná un juego y pulsá **Árbol y diagnóstico**. Se abre el informe más reciente de ese juego.
6. Cuando termine, indicame el proveedor y los juegos que fallaron. Voy a leer sus diagnósticos y capturas locales. No hace falta pegar megabytes de logs.

Después analizamos la última request, la response, las opciones pendientes y las diferencias con un intento válido del mismo juego. Sólo entonces decidimos una corrección y qué caso repetir. Ampliar a 20–50 tiradas tiene sentido cuando hace falta observar una transición natural; un error de arranque no se resuelve aumentando la muestra.

## Qué guarda el programa

En la carpeta del juego:

```text
diagnostics/<identificador>/events.jsonl
tests/<corrida>/
  diagnostic.md
  diagnostic.json
  run-tree.html
  run-tree.json
  sample-catalog.json
  path-coverage.json
  <capturas originales del proveedor>
```

`events.jsonl` empieza antes de ejecutar el protocolo y se escribe de forma incremental. Incluye fecha, tiempo transcurrido, configuración de prueba, mensajes y excepciones capturadas. Si no se llega a crear una corrida del proveedor, los informes quedan junto a ese registro. Si el proceso termina abruptamente, puede quedar un registro sin evento `END`; eso no es una prueba completada.

`diagnostic.md` es el punto de entrada para analizar fallos. Muestra el error observado, el último intercambio cuyo orden puede demostrarse, estados informados por el ejecutor, acciones probadas y huecos de evidencia. `diagnostic.json` añade hashes, metadatos originales de los modos, cobertura y comparación entre la primera request SPIN y las primeras requests de otros modos.

No se reemplazan las capturas originales. Los resúmenes ocultan credenciales comunes; los originales mantienen las reglas de sanitización del módulo que los produjo. No compartir toda la carpeta RAW sin revisar esos archivos.

## Árbol y origen de las funciones

Cada intento conserva una identidad distinta y su modo de entrada:

```text
Juego
├─ SPIN → intento A → intercambio 0 → intercambio 1
├─ ANTE_BET_1 → intento B → intercambio 0 → intercambio 1
└─ PURCHASE_0 → intento C → intercambio 0 → intercambio 1
```

Dos respuestas similares no fusionan los orígenes. Si una función aparece tras un antebet, la captura queda en ese recorrido; si aparece después de una compra, queda en el otro. El árbol conserva los campos de request/response y las opciones de cobertura anunciadas. No asigna el nombre “super spin”, “bonus” o “pick” a un estado cuyo significado todavía no está demostrado.

El orden se obtiene de índices de paso explícitos, de una secuencia declarada por el proveedor o de un array de frames registrado en orden. Los archivos de bootstrap no se mezclan con las tiradas. Cuando faltan índices, asociación o dominio de una elección, el árbol conserva el hueco como pendiente; no inventa una secuencia para permitir replay.

## Reproducción

**Reproducción offline:** vuelve a leer la secuencia guardada y comprueba los hashes de todas sus capturas. No contacta al servidor ni hace apuestas. El HTML muestra el identificador de cada recorrido.

Desde la carpeta del proyecto:

```powershell
.\.venv\Scripts\python.exe -m tester_spin.run_tree "RUTA\run-tree.json" "ID_DEL_RECORRIDO"
```

**Repetir el protocolo en vivo:** requiere una sesión nueva, parámetros válidos y todas las continuaciones demostradas. El replay offline no reenvía tokens ni convierte una captura vieja en una sesión válida.

**Repetir exactamente el premio:** no está garantizado. Requiere que el proveedor permita reproducir la semilla o el estado de cálculo. La aparición de un campo llamado `seed` por sí sola no lo demuestra.

## Cómo leer los estados

- `DISCOVERED`: hay una acción anunciada sin ejecución demostrada en esta corrida.
- `VALIDATED`: los intentos revisados tienen evidencia y terminal válido, sin advertencias ni opciones pendientes y con los índices de cobertura/muestreo disponibles.
- `INCOMPLETE`: hubo un intento pero faltan cierre, opciones, orden o evidencia suficiente.
- `UNCLASSIFIED_WIRE_VARIANT_<hash>`: observación pendiente comunicada por el proveedor. El hash identifica la observación, no le asigna significado.
- `UNDETERMINED` en causa: todavía no se probó qué produjo el fallo. No significa que la captura haya fallado.

El informe es conservador cuando una observación desconocida no está asociada a un modo concreto. El estado histórico del adaptador se conserva por separado. Un `OK` de una corrida corta no demuestra que el juego no tenga más compras o resultados naturales.

## Qué necesitamos para corregir un caso

- Juego, proveedor, modo e identificador de corrida.
- Request exacta y response correspondiente, con sus hashes.
- Último estado observado y opciones anunciadas/elegidas.
- Si faltan datos: distinguir ausencia de captura, error de transporte y contrato todavía desconocido.
- Comparación con un caso válido del mismo juego/proveedor o con el serializer del cliente.
- Prueba de regresión basada en esa evidencia y una nueva corrida manual del caso afectado.

Las comparaciones muestran diferencias literales, incluyendo campo ausente frente a `null`, valores repetidos y tipos. Una diferencia no demuestra por sí sola la causa del fallo. No se incorporan excepciones por nombre de juego sin evidencia concreta.

## Catálogo actualizado

El catálogo del checkout C:\Proyectos\Tester-Spin contiene 1.797 títulos: Pragmatic 649, 1spin4win 227, Belatra 104, BGaming 234, RubyPlay 191 y Red Tiger 392. RubyPlay devolvió 67 en la consulta actual; se conservaron los otros 124 para investigar su disponibilidad. Los conteos no certifican disponibilidad de demo ni cobertura de compras.

La actualización conservó historial y exclusiones. El respaldo y el detalle están en `audit-2026-09-15/catalog-before-update.sqlite3` y `audit-2026-09-15/catalog-update.json` dentro de los entregables de esta tarea.

## Alcance de esta mejora

Se reutilizaron los ejecutores existentes y lo aprendido en las conversaciones de Gambling, especialmente **Tester Spin V2** y **Bgaming depurado**. Esta mejora añade observación, diagnóstico y reproducción de capturas; no modifica los contratos de juego ni demuestra que las compras pendientes ya funcionen.

La interfaz puede iniciar tareas propias de los módulos existentes, como preparación de HAR o publicación configurada de resultados. Esas conductas anteriores no se reescribieron como parte del árbol. Las corridas automáticas iniciadas por esta tarea fueron detenidas; las siguientes pruebas las inicia el usuario.


## Respuestas distintas y comprobación de regreso (2026-09-15)

El scheduler activa `audit_scope(stop_event)` dentro de cada worker. El estado del observador y de detención queda aislado por juego/hilo. Las llamadas directas de bajo nivel fuera del scheduler conservan su comportamiento anterior; las herramientas que usen esa vía deben activar explícitamente `audit_scope` para estas comprobaciones.

Los límites por defecto de `verify_return_to_base` son `required=2` y `max_probes=10`. El contrato de cada proveedor permanece en su ejecutor y en `provider_return_checks.py`, sin listas de nombres de juegos. La comprobación se ejecuta antes de cerrar o renovar la conexión del intento. No reutiliza resultados de otra sesión. Las muestras auxiliares están separadas de las tiradas solicitadas y de su contador de intercambios.

`server-responses.jsonl` se escribe al recibir la respuesta, antes de validar HTTP o el cuerpo. `server-observations.json` y `.md` agrupan firmas por juego y acción, conservando origen, campos distintos y referencia al registro. Se distinguen BASELINE, SEEN, NEW_RESPONSE y UNPARSED. BASELINE no certifica un contrato. Los valores de campos de estado se comparan; importes y símbolos se comparan por estructura/tipo. El registro es por corrida, no una aprobación persistente de firmas entre corridas.

`return-to-base.json` guarda incrementalmente cada comprobación. CONFIRMED exige dos respuestas base consecutivas; un evento conocido reinicia el contador. Una acción sin resolver termina REVIEW_REQUIRED, un error ERROR y el límite LIMIT_REACHED. Se liberan recursos al abortar, dejando explícito que no se confirmó el cierre. D1 conserva OBSERVED_RETURN separado: repetir un st desconocido no demuestra su significado terminal y mantiene el resultado pendiente.

Los árboles incluyen la comprobación ligada al origen. La reproducción offline valida también el hash del archivo de comprobación. La numeración RubyPlay `request/response` seguida por `step-002` se reconoce como secuencia completa. No se envían solicitudes desde los informes o la reproducción offline.
