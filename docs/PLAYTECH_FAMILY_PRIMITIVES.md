# Evaluación de primitivas GPAS por familia

El comando `families` evalúa capturas guardadas con las mismas primitivas de
construcción, continuación y contabilidad que utiliza el ejecutor. Agrupa por
envoltorio de protocolo, clase de comando y dialecto de apuesta; el código o
nombre del juego no participa en la identidad de la familia.

## Uso

Desde una instalación del proyecto:

```bash
tester-spin families playtech HardFire-HARs.zip --output familias.json
```

Desde el repositorio:

```bash
python -m tester_spin.cli families playtech captura1.har captura2.har --output familias.json
```

Se admiten varios HAR y ZIP. Los fragmentos de una misma conexión se reconstruyen
juntos. La entrada original se conserva; la salida no puede sobrescribir una
captura. El análisis no abre sesiones ni escribe resultados de juegos en SQLite.
El código de salida `0` significa que se generó el informe; los estados de
cobertura están dentro de `families[].capabilities`.

## Qué mide

| Capacidad | Comprobación |
|---|---|
| `recognition` | Si hay evidencia del contrato del cliente. El wire histórico por sí solo no certifica la fuente vigente. |
| `entry` | Si el constructor reproduce los campos semánticos de las entradas observadas. Los parámetros no reproducidos quedan pendientes. |
| `configuration_scope` | Si coste, multiplicador y límites monetarios pertenecen al contexto capturado de la operación. |
| `continuation` | Si el planificador y constructor reproducen la siguiente acción desde el estado anterior, con enlace causal comprobado. Se desglosa por fase. |
| `settlement` | Si la ronda cierra, mantiene su identidad y sus cargos/premios concuerdan con los saldos anteriores y posteriores. |

`VERIFIED_OFFLINE` se limita a las observaciones indicadas. `PARTIAL` señala una
diferencia o una cobertura incompleta; `INCONSISTENT` indica una contradicción
contable/protocolaria; `MISSING_EVIDENCE` indica que falta una prueba necesaria.
El informe conserva `certifies_live_ok=false` y nunca convierte una captura en
un `OK` de ejecución actual.

## Primitivas compartidas

### Configuración por operación

El adaptador pasa las filas originales de configuración a `discover_modes`,
también cuando abre una nueva demo. Cada modo resuelve su contexto completo
`betType` + `featureType`, conserva su dominio de multiplicadores y aplica la
intersección de límites relevantes. Un scope inválido o una identidad económica
contradictoria bloquea ese modo; un modo deshabilitado queda registrado como tal.

Esta regla se aplica a familias de costes con ámbitos distintos sin depender
del título, el UUID concreto ni una tabla de precios por juego.

### Familias de comandos

- **Corosin moderno:** API extendida con selector de modalidad e importe en el
  envoltorio. Conserva su comprobación de fuente anterior; los mapas de
  parámetros globales requieren un contrato de valores adicional.
- **Corosin legacy:** importe, UUID de coste y multiplicador dentro del comando.
- **Quickspin moderno:** constructor y continuación con `parameters: null`.
  Su reconocimiento nuevo vincula la policy al registro y bootstrap activos;
  compra y antebet requieren además el recorrido actual de opciones y selector.

Los prefijos numéricos Quickspin se obtienen del contrato del cliente y del
dominio declarado por el servidor. El recorrido exige el prefijo base y se
detiene en el primer hueco. Los selectores compuestos de compra más antebet
siguen pendientes de su propio contrato.

`continuation_command` centraliza la serialización para el ejecutor y el auditor.
La familia de parámetros nulos rechaza una selección `pick` no vinculada.

## Evidencia y límites

### Comparación sobre el ZIP HardFire suministrado

Se evaluaron las mismas 175 operaciones con las primitivas de
`fbc4258af94e31ae8db70e899d0208280df9b033` y con las actualizadas. El auditor y
sus reglas de validación se mantuvieron constantes durante la comparación.

| Familia observada | Comandos reproducidos antes | Después | Alcance observado |
|---|---:|---:|---|
| Quickspin moderno | 0/37 | **37/37** | Cuatro entradas y 33 continuaciones FreeSpin; cuatro rondas conciliadas. |
| Corosin legacy | 32/32 | **32/32** | Entradas base; no hay continuación ni elección capturada de esta familia. |
| Corosin moderno | 90/106 | **90/106** | 36/40 entradas y 54/66 continuaciones; quedan parámetros globales de cuatro entradas y 12 Respins. |
| Total | 122/175 | **159/175** | 37 comandos adicionales reproducidos por la familia compartida. |

Las 74 rondas con cierre y saldo correctos permanecen verificadas; las otras dos
siguen abiertas al finalizar sus capturas. La comprobación separada con la
fuente Quickspin íntegra vigente pasa de `CLIENT_COMMAND_BINDING_UNKNOWN` a un
contrato de clase, policy, selector y dominios vinculado.

La regresión de configuración, usando filas reales y el binder sintético
existente de la familia de cartas, cambia `BF3Cards` de 1000 a 50000,
`BF6Cards` de 1500 a 75000 y `BF9Cards` de 2000 a 100000 unidades internas.
Los importes provienen del contexto propio de cada modalidad. Esa comparación
no demuestra cierre de compras ausentes del corpus ni causalidad sobre un
intento fallido concreto.

Datos y referencias:

- [Comparación y hashes de las implementaciones](playtech-family-comparison-20261025.json).
- [Auditoría con primitivas anteriores](playtech-family-audit-before-20261025.json).
- [Auditoría con primitivas actualizadas](playtech-family-audit-after-20261025.json).

La fuente pública revisada, su hash y la reconstrucción estructural de prueba
están documentados en
[`playtech_command_sources.json`](../tests/fixtures/playtech_command_sources.json).
Las fixtures de rondas usan identificadores sintéticos; los HAR originales y las
credenciales de sesión no se publican.

El informe antes/después mantiene fijas las reglas del auditor y cambia las
primitivas evaluadas. El reconocimiento de la fuente actual y el descubrimiento
de importes por scope se comprueban aparte. Ningún número de comandos compatibles
equivale automáticamente a un número de juegos que pasan de `PARCIAL` a `OK`.

Continúan pendientes las variantes de parámetros globales Corosin no vinculadas,
las elecciones no observadas, los finales ausentes y las modalidades que el
corpus no ejecutó. Las pruebas nuevas conservan esos límites explícitos.
