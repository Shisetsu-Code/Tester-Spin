# Ejecución GPAS de Playtech

Tester-Spin usa ahora un adaptador GPAS ejecutable desde la interfaz y los módulos independientes. El catálogo existente se conserva. La implementación no depende de nombres de juegos ni de HAR históricos y no usa Firetrace, HardFire o fuzzer.

## Contratos soportados

- Ruta GPAS activa por HTTP/WebSocket directo, sesión demo nueva con real=0 y resume=false. Véase [transporte directo](DIRECT_TRANSPORT.md). La implementación antigua con Chromium queda como referencia.
- Configuración efectiva del contexto default: merge ordenado de scopes y sustitución de listas. No contar de nuevo modalidades repetidas en freespin ni tratar multiplicadores como opciones.
- Manifiesto y código descargados en esa sesión para vincular las APIs, comandos y modalidades. Hash SHA256 del contenido; el nombre compartido de un bundle no prueba que su código sea igual.
- Ruta moderna: playMoney con betCost y featureType según el selector del cliente. La modalidad base modular puede usar alias default aunque la declaración se llame Default. El servidor debe devolver el UUID declarado.
- Ruta antigua: gameData.bet, stakeCostUuid y baseCostMultiplier, por GLU.game.bet. La API se decide usando usesLegacyBetApi/useExtendedBetApi y el constructor del cliente.
- Declaraciones Base/default, BF/BuyFeature y extra se clasifican únicamente dentro de los contratos de cliente revisados. Un precio, un UUID, startingMode o featureBetEnabled por sí solos no clasifican una compra. Los nombres nuevos quedan pendientes.
- Continuaciones con ID 48775 sin cobros; parámetros como lista key/value. Las elecciones LIST_PICK usan pick textual solo con vinculación en el cliente. Se excluyen uiIndex consumidos que devuelve listPickData; la lista anunciada puede seguir incluyendo índices usados.
- Respuestas gpas:packed:zlib se decodifican con Base64 y zlib, límite de salida 8 MiB y rechazo de datos truncados, residuos o estructuras inválidas.

## Resultado y artefactos

Cada modalidad se ejecuta con el multiplicador mínimo declarado y tantas repeticiones como se configuraron. Al terminar se prueba de nuevo el giro base. Se comprueban identidad de modalidad, coste inicial, continuaciones de coste cero, premio acumulado, saldo y cierre BET_END_STATE_IDENTIFIER/gameRoundClosed.

La grilla recibe los dominios purchase y ante y sus UUID sin duplicar contextos. La marca validated enlaza las rondas realmente completadas con el verificador común. El cierre de una compra no equivale a cubrir todas sus elecciones: las opciones sin recorrer conservan PARCIAL y quedan en choice_domains/pending_choice_branches. No se declaran cubiertas ramas solo por aparecer en una respuesta.

NGM offline valida rondas normales en un ejecutor local separado y conserva PARCIAL mientras el inventario de opciones sea desconocido; véase [NGM](PLAYTECH_NGM_OBSERVATION.md). Los demás motores y contratos desconocidos siguen como PARCIAL con causa explícita. También quedan pendientes inicializaciones incompletas, errores del servidor, opciones desconocidas, decisiones no vinculadas, falta de conciliación o límite de 200 comandos por ronda. Se respeta DETENER y el timeout configurado. Concurrencia GPAS máxima: dos sesiones.

En la carpeta HAR del juego se guardan analysis/runs/<ejecución>/session.har (HTTP de inicialización y código más WebSocket), bootstrap.json, result.json y los request/response/summary de cada intento. Los HAR son privados y pueden contener sesiones; no se incluyen en Git. Los fallos permanecen disponibles para Aislador y revisión posterior.

## Validación

Pruebas sintéticas de ambos formatos, scopes, alias default, compresión y límites, dominios desconocidos, elecciones consumidas, dinero acumulado, registro y verificador común. Pruebas reales limitadas de integración en demo; los resultados locales no actualizan el catálogo del usuario. La prueba masiva la realiza el usuario desde la aplicación.


## Catálogo de slots

La disponibilidad de demo y el motor NGM/GPAS no identifican una slot. El catálogo cruza getGamesConfiguration con getGamesFeed("casino-2026") y solo admite códigos de la categoría oficial `slots` para escritorio. Conserva motor y clasificación como campos separados. La actualización completa reemplaza el conjunto anterior; no lo mezcla con juegos de mesa o títulos sin clasificación. El respaldo incluido contiene únicamente slots con categoría verificada. Si falta la categoría, está vacía o falla la consulta, se conserva ese respaldo sin autoridad de eliminación. Los resultados históricos y HAR permanecen al retirar una fila de la grilla.


### Clientes GLU6 y resultados externos

Cuando `manifest.env.glu6` es true, las rutas javascript se resuelven contra `game/`, no `packs/`. La descarga mantiene los controles de origen, identidad y límites; resolver una ruta no autoriza un contrato de comandos desconocido. Epic Fish Net of Fortune y Marlin Madness superaron el 404 de carga, pero su vínculo de comandos continúa pendiente (`CLIENT_COMMAND_BINDING_UNKNOWN`). No se reclasifican como OK por descargar el cliente.

La interfaz vuelve a leer el historial compartido al recuperar el foco si no hay una corrida activa, conservando selección y posición. Esto permite reflejar pruebas ejecutadas desde el analizador o la CLI sin reiniciar ni cambiar manualmente estados.


### Variantes compiladas de apuestas y elecciones

La modalidad base puede llamarse un número o Standard. El lector admite una única entrada con startingMode=Standard y startingPlays=1 si el cliente contiene el contraste explícito de Standard y los campos de selección de apuesta; no se permiten parámetros económicos adicionales. Su selector base de protocolo es default. Varias entradas Standard siguen exigiendo el contrato de líneas. ExtraBetWidget también se reconoce como evidencia de interfaz de antebet, pero las opciones y costes siguen procediendo de costConfiguration.

El cliente compilado puede escribir la clave literal pick en un mapa y reenviarlo mediante callbacks. El lector enlaza esa construcción, el setter del mapa, reenvíos sin transformación y el comando de continuación 48775 hasta playOut. El ejecutor sigue eligiendo únicamente índices ofrecidos por el servidor, registra los resultados y exige cierre, conciliación y cobertura de ramas. No se amplía el dominio a partir de nombres de juegos ni se cambia un estado guardado sin ejecutar la prueba.


### Cargadores DOM y mapas JMM modernos

Los cargadores que crean un elemento script y asignan una ruta literal a `.src` se siguen igual que `setAttribute`; no se evalúan expresiones dinámicas. Se mantienen identidad, origen, límite de recursos y registro HAR.

Cuando el constructor del cliente declara un proyecto `jmm/*.jmp`, el ejecutor descarga sus JMM de escritorio en orden y fusiona únicamente `config.game_adapter.bet_features` y `bet_feature_types`. Proyectos condicionales añadidos con push no se mezclan como autoridad permanente. Los mapas se vinculan a los lectores presentes en el código y se cruzan con cada opción del costConfiguration vigente. Las categorías conocidas son regular, extra_bet, buy_feature y lucky_box. Patrones ambiguos o fuera de la gramática acotada conservan UNKNOWN. Estas declaraciones clasifican opciones, pero OK sigue exigiendo ejecutar y conciliar todas las rondas y ramas.

Los nombres BuyFeatureNPot solo se reconocen si el cliente declara el patrón correspondiente y los ámbitos y opciones activos del servidor lo confirman. No se construyen opciones a partir del número ni se mantiene una lista de títulos.
