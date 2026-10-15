# Nolimit City: contratos comunes y auditoría del corpus

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
