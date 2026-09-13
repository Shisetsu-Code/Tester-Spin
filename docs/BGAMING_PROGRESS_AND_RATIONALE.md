# BGaming — progreso, decisiones y por qué se hicieron

> Estado de esta documentación: 2026-09-13.
>
> Rama de trabajo para la política nueva de cobertura/apuesta: `feature/exhaustive-paths-wager-policy-2026-09`.
>
> PR de integración: #30, mantenida en draft mientras se compara contra corridas reales.

## 1. Objetivo real

Tester-Spin no intenta solamente comprobar que un juego responde. El objetivo es reconstruir de forma reproducible el protocolo de cada juego/proveedor hasta poder:

1. descubrir todos los modos de entrada que el cliente/proveedor demuestra;
2. recorrer todos los caminos ejecutables, aunque requieran varias sesiones/rondas independientes;
3. conservar cada request/response y la transición de estado que produjo;
4. clasificar esos caminos para repetirlos cientos o miles de veces más adelante;
5. usar esa evidencia para construir un backend local compatible con el wire y la máquina de estados;
6. mantener separado el protocolo de la matemática/RNG.

La invariante principal es:

```text
estado actual + acción recibida + outcome elegido
    -> respuesta wire
    -> próximo estado
```

Tester-Spin debe aprender la parte de protocolo/estado a partir de evidencia real. El modelo matemático que decide la frecuencia de cada outcome es otra capa y no debe inferirse automáticamente de una cantidad pequeña de observaciones.

## 2. Qué significa `OK`

`OK` no significa HTTP 200 ni "el spin respondió".

Un juego sólo puede quedar `OK` cuando todas las ramas ejecutables y finitas demostradas por el proveedor/cliente fueron recorridas. Si aparece alguna de estas situaciones, el estado correcto es `PARCIAL`:

- una acción anunciada sin wire contract demostrado;
- un selector cuyo dominio no se conoce completamente;
- una continuación que responde pero no llega a terminal;
- una rama descubierta que todavía no se ejecutó;
- un estado nuevo que el módulo no sabe clasificar;
- una compra anunciada por metadata pero sin prueba de cómo la construye el cliente.

Esta política es provider-neutral y se aplica al finalizar cada prueba mediante el gate global de cobertura.

## 3. Por qué BGaming se volvió difícil

BGaming no tiene un único runtime uniforme. En el catálogo actual aparecen varias familias que comparten marca/proveedor pero no necesariamente el mismo wire:

```text
api-v2
legacy-lines
hyperhive-jsonrpc
switchable-container
unknown
```

Además, dos juegos API-v2 pueden exponer ramas internas diferentes. Ejemplos reales observados durante esta etapa:

```text
Adventures
  purchase
    -> state=select_bonus
    -> available_actions=[init, play_bonus_game]

Alice WonderLuck
  purchase
    -> state=gamble_bonus
    -> available_actions=[gamble_bonus, init, pick_cards]

Aloha King Elvis
  freespin_buy
    -> freespins
    -> continuación freespin
    -> HTTP 400

BigTunaBonanza
  purchase level 4
    -> HTTP 422 antes de alcanzar la rama interna
```

La conclusión importante fue que no se puede mantener una lista creciente de excepciones por título ni asumir que el nombre del estado es el nombre del siguiente comando.

## 4. Deuda semántica que se eliminó

### 4.1 Estado y acción no son lo mismo

Una implementación anterior podía razonar así:

```text
flow.state == select_bonus
    -> enviar command=select_bonus
```

Eso era incorrecto. `flow.state` describe el estado actual; `flow.available_actions` describe lo que el backend permite hacer a continuación.

En Adventures vimos la prueba concreta:

```text
state = select_bonus
available_actions = [init, play_bonus_game]
```

Por lo tanto el código se limpió para que un estado nunca fabrique una acción. La acción sólo se ejecuta cuando existe evidencia de que está disponible y además conocemos su wire contract.

### 4.2 Elecciones internas dejaron de ser código específico de `select_bonus`

La primera implementación de ramas de recompensa estaba muy acoplada a `select_bonus`. Se reemplazó por un motor genérico de elecciones de flujo (`flow_choices.py`).

El modelo actual es:

```text
rama finita demostrada
  + dominio demostrado
  + contrato de request demostrado
  -> recorrer cada opción
```

Si una opción abre otra selección, el recorrido conserva el prefijo completo:

```text
A -> A1
A -> A2
B -> B1
B -> B2
B -> B3
```

Las ramas hermanas pueden requerir sesiones frescas porque una selección consume el estado/ronda. Eso es correcto y no se considera duplicación inútil.

## 5. Recorrer todos los caminos no significa minimizar requests

La optimización correcta no es "hacer menos tiradas". La prioridad es cobertura completa.

Si un árbol necesita diez rondas independientes para visitar diez hojas, deben ejecutarse las diez. Lo que se eliminó fue otra cosa: combinaciones que no representan caminos reales.

Un error anterior trataba todas las `additionalSpinOptions` como dimensiones globales y generaba un producto cartesiano contra SPIN y todas las purchases. Esto podía producir modos conceptualmente absurdos como:

```text
SPIN + purchased_feature_level=1
PURCHASE_A + purchased_feature_level=1
PURCHASE_B + purchased_feature_level=1
```

cuando `purchased_feature_level` pertenecía en realidad sólo a una purchase específica.

La nueva política separa:

- selectores globales de spin realmente demostrados por el cliente;
- identidad de purchase;
- nivel de purchase;
- elecciones internas de una feature;
- continuaciones deterministas del state machine.

`purchased_feature` y `purchased_feature_level` ya no se usan como dimensiones cartesianas globales. Se representan dentro del camino `PURCHASE_*` que les corresponde.

## 6. Política de apuesta para cobertura

Otro problema práctico apareció porque algunos juegos arrancan con una apuesta por defecto alta. Una compra de x100, x500 o más puede consumir rápidamente el saldo demo y hacer inaccesible una rama aunque el protocolo sea perfectamente válido.

La política nueva distingue entre:

```text
default_bet   = configuración original del proveedor/UI
coverage_bet  = menor apuesta válida anunciada por el proveedor
available_bets = dominio de apuestas observado
```

Para la fase de cobertura, Tester-Spin usa la menor apuesta que el propio proveedor anuncia. No inventa una apuesta menor.

Ejemplo:

```text
default_bet   = 200
available_bets = [20, 40, 100, 200]
coverage_bet  = 20
```

El objetivo es poder comprar las features caras y recorrer el grafo completo sin perder la información original. La apuesta por defecto y el dominio completo se conservan para la futura fase de muestreo.

En HyperHive la respuesta original de `init` se preserva. La reducción de apuesta se aplica sólo a una copia de ejecución y no contamina la evidencia que después usa el contrato de emulación.

## 7. Metadata anunciada no equivale a wire ejecutable

Otra fuente de falsos fallos era tratar una purchase anunciada en metadata como si ya conociéramos exactamente cómo enviarla.

Ahora se distinguen explícitamente conceptos diferentes:

```text
SERVER/INIT ADVERTISED
CLIENT PROVEN
WIRE EXECUTABLE
VALIDATED
```

Una feature que aparece en `feature_multipliers` se cataloga, pero no se ejecuta automáticamente si el cliente no demuestra cómo serializar `purchased_feature` o la variante/nivel correspondiente.

Esto evita requests inventados y HTTP 400/422 que no enseñan nada fiable sobre el contrato real.

La excepción válida es cuando el cliente demuestra un serializer dinámico. En ese caso el nombre concreto puede venir de metadata del servidor porque el shape de la request ya está probado por el cliente.

## 8. Evidencia automática en GitHub

Copiar HARs y logs manualmente estaba frenando el ciclo de depuración. Por eso BGaming ahora publica automáticamente el resultado final de cada juego en una rama separada del mismo repositorio:

```text
tester-spin-runs
```

Ruta estable por juego:

```text
run-results/bgaming/<slug>.json
```

El documento de evidencia incluye el resultado y los artefactos textuales de la corrida, entre ellos requests/responses, coverage, perfiles y contratos de emulación. La siguiente ejecución reemplaza el archivo actual y Git conserva la historia por commits.

La publicación ocurre después del gate de cobertura y de generar los artefactos de emulación. Se ejecuta en segundo plano, no cambia la rama del checkout y un fallo de publicación no modifica el estado de la prueba.

En Windows los subprocess de Git se lanzan ocultos para evitar la aparición de múltiples ventanas CMD.

## 9. Contrato para futura emulación local

Cada corrida BGaming puede generar:

```text
emulation-contract.json
protocol-contract.json
state-machine.json
outcome-catalog.json
backend-response-plan.json
backend-conformance.json
response-schemas/
```

La pregunta que intenta responder `backend-response-plan.json` es:

```text
Dado este estado y este request válido,
¿qué familias de respuesta observadas puede devolver el backend
 y a qué estado llevan?
```

Ejemplo conceptual:

```text
READY + SPIN
  -> NORMAL_RESULT -> READY
  -> FEATURE_ENTRY -> FLOW:freespins

FLOW:freespins + FREESPIN
  -> FREESPIN_RESULT -> FLOW:freespins
  -> FEATURE_END -> READY
```

Los artefactos describen el protocolo observado. No asignan probabilidades RNG.

## 10. Separación entre cobertura y muestreo

El proyecto ahora diferencia dos fases.

### Fase 1 — discovery/coverage

Objetivo: demostrar todos los caminos ejecutables.

```text
juego
  -> SPIN
  -> ANTE/MODE
  -> PURCHASE_A
       -> continuation...
       -> terminal
  -> PURCHASE_B
       -> CHOICE_A
       -> CHOICE_B
       -> CHOICE_C
  -> etc.
```

Se usan todas las sesiones/rondas necesarias. La apuesta puede reducirse al mínimo válido para mantener las ramas caras accesibles.

### Fase 2 — high-volume sampling

Cuando el camino ya está demostrado, podremos repetir cada camino normalizado de forma independiente:

```text
SPIN                         x N
ANTE_BET                     x N
PURCHASE_A                   x N
PURCHASE_B -> CHOICE_A       x N
PURCHASE_B -> CHOICE_B       x N
PURCHASE_B -> CHOICE_C       x N
```

La unidad de muestreo será el camino normalizado, no un producto cartesiano de selectores no relacionados.

Para preparar esta fase, todos los proveedores generan `sampling-plan.json`. Cada entrada indica, entre otras cosas:

- `path_id` / `mode_id`;
- si el camino es ejecutable;
- opciones requeridas/cubiertas/faltantes;
- si está `sampling_ready`;
- intentos observados;
- terminales correctos;
- fallos;
- cantidad de pasos wire;
- rutas a la evidencia.

Los conteos futuros serán frecuencias observadas. No se convertirán automáticamente en probabilidades matemáticas oficiales.

## 11. Artefactos nuevos de BGaming

La rama de política nueva añade la capa de clasificación para esta transición hacia muestreo/emulación:

```text
wager-catalog.json
path-catalog.json
sampling-plan.json
```

`wager-catalog.json` conserva la configuración de apuesta, dominio anunciado y coste estimado de purchases a la apuesta de cobertura.

`path-catalog.json` resume los caminos BGaming descubiertos, cobertura, intentos terminales, pasos wire y artefactos asociados.

`sampling-plan.json` es provider-neutral y marca qué caminos están listos para la futura campaña de cientos/miles de muestras.

## 12. Qué fallos reales quedan abiertos

Los resultados publicados muestran que todavía hay gaps reales y distintos. No deben resolverse con hardcode por juego.

### API-v2

- `play_bonus_game`: observado como acción disponible en Adventures, todavía requiere contrato de request demostrado.
- `gamble_bonus` / `pick_cards`: observados en Alice WonderLuck, todavía no deben enviarse sin derivar su shape/dominio.
- algunas continuaciones `freespin` responden 400 en títulos concretos, señal de que falta contexto/opciones wire y no de que `freespin` sea universalmente incorrecto.
- algunas purchases levelled devuelven 422 antes de entrar a la feature; hay que aprender el request correcto, no saltar directamente al selector posterior.

### HyperHive

Hay juegos donde no se logra reconstruir todavía el contrato base `play`, otros donde el base funciona pero una purchase produce error RPC, y otros donde el shape parece descubierto pero la ejecución real no valida. Estas familias deben seguir tratándose de forma independiente dentro del módulo BGaming.

## 13. Reglas de diseño que quedan fijadas

1. No routing por nombre/slug/título del juego.
2. No asumir `state == command`.
3. No inventar valores para completar un selector.
4. No considerar metadata anunciada como autorización de wire por sí sola.
5. No mezclar selectores de scopes diferentes en un producto cartesiano global.
6. Sí recorrer todos los caminos reales, aunque requieran muchas sesiones.
7. Sí usar la apuesta mínima anunciada para cobertura cuando haga accesibles purchases caras.
8. Sí preservar la configuración original y todas las respuestas RAW/JSON necesarias para reproducibilidad.
9. `OK` sólo con cobertura completa de lo ejecutable/demostrado.
10. Protocolo/state machine y matemática/RNG son capas separadas.
11. Observed count no es RNG probability.
12. Cada proveedor mantiene autonomía de wire; el core sólo comparte contratos neutrales como cobertura y sampling plan.

## 14. Estado de la rama actual

La política descrita en las secciones de scope/apuesta/sampling está implementada en:

```text
tester_spin/providers/bgaming_path_policy.py
tester_spin/providers/bgaming_paths_v2.py
tester_spin/providers/sampling_plan.py
```

La rama se mantiene separada de `main` para poder comparar contra corridas reales antes de integrar. El CI de la versión documentada compila y pasa 389 tests.

La prioridad siguiente no es añadir más excepciones. Es usar las nuevas corridas publicadas para transformar cada `PARCIAL` real en uno de estos casos bien definidos:

```text
contrato demostrado -> executor provider-local
selector demostrado -> expansión exhaustiva
metadata sin wire -> catalogado, no ejecutado
estado/acción desconocidos -> evidencia preservada + PARCIAL
camino terminal demostrado -> sampling_ready
```

Eso mantiene Tester-Spin útil tanto para testing inmediato como para la futura reconstrucción local del backend.