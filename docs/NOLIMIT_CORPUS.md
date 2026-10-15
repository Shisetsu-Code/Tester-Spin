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
