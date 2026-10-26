# Comparación de primitivas con demos actuales

Esta prueba mide el efecto incremental del PR #38 frente a su base, el PR #37.
Ejecuta el tester habitual sobre sesiones nuevas de las demos oficiales; no
reproduce credenciales ni comandos de los HAR históricos.

## Revisiones y muestra

- Base: `fbc4258af94e31ae8db70e899d0208280df9b033`.
- Candidata: `f4e524335ae07eea2f8ad5440651bcd163fed5bc`.
- Muestra: los nueve juegos del ZIP HardFire suministrado, con sus tres familias
  observadas: Quickspin moderno, Corosin moderno y Corosin legacy.
- Definición exacta: [`playtech-family-live-manifest.json`](../scripts/playtech-family-live-manifest.json).

Las familias del manifest identifican cohortes de la captura histórica. El
ejecutor vuelve a vincular el contrato del cliente actual y descubre sus modos;
la etiqueta del manifest no autoriza ningún comando ni hace ejecutable un modo.

## Condiciones iguales

Cada juego tiene un job con dos checkouts y entornos Python 3.12 separados. Las
dependencias de la base se fijan también para la candidata y se comprueba su
igualdad antes de ejecutar. El orden base/candidata alterna entre juegos. Como
máximo hay tres jobs en paralelo.

Ambos lados usan `--spins 1 --timeout 45 --wall-timeout 600`. Es una ronda inicial
por modo reconocido y un regreso a base adicional; el ejecutor existente puede
añadir rondas cerradas para cubrir elecciones observadas. Los modos desconocidos
permanecen pendientes. El presupuesto de 600 segundos incluye bootstrap,
descubrimiento y todas las modalidades de cada juego. No se fuerzan importes
iguales: corregir el contexto monetario es parte del cambio evaluado.

Cada brazo usa su propia carpeta de datos nueva. Si el CLI interno comunica un
bloqueo o un cierre de procesos no verificado, se conserva lo obtenido y no se
inicia el otro brazo de ese job. Nunca se reenvía una operación incierta dentro
de la sesión.

## Evidencia y resultados

El colector contrasta el SHA real del checkout, la invocación, los límites, el
resumen y el resultado persistido. Publica sólo campos derivados: estados,
motivos, intentos, inventario de modos, ramas pendientes y fingerprints del
cliente y la configuración. Los HAR, las bases de datos y los logs privados
permanecen fuera de los artefactos públicos.

El comparador informa por familia y por juego:

- Estados de ambos lados y transiciones observadas, incluyendo `PARCIAL → OK`.
- Regresiones de `OK` a cualquier estado distinto de `OK`.
- Rondas verificadas, modos reconocidos, modos verificados y desconocidos.
- Elecciones pendientes, errores, timeouts y resultados ausentes.
- Coincidencia de fuentes, configuración, manifiesto y entorno, separada de la
  transición observada. Una diferencia o evidencia insuficiente impide atribuir
  automáticamente el cambio de estado a las primitivas.

Las sesiones son independientes y sus resultados aleatorios pueden diferir. Una
única pareja de ejecuciones demuestra lo observado en esa muestra; no estima
una tasa de éxito de todo el catálogo ni garantiza todas las ramas aleatorias.

El workflow genera el informe incluso si quedan parciales. El job de comparación
falla si falta evidencia, hay una regresión o la candidata conserva juegos sin
`OK`; un job verde de instalación o recolección no es un resultado de juego.

## Ejecutar e inspeccionar

Workflow: [`playtech-family-comparison.yml`](../.github/workflows/playtech-family-comparison.yml).
Se activa con cambios en su definición o manifest en la rama del PR #38 y admite
ejecución manual. Los commits del manifest están fijados: modificar el ejecutor
no cambia silenciosamente las revisiones de esta comparación.

Los nueve artefactos `family-live-<gameCode>` contienen las celdas públicas de
ambos lados. `playtech-family-live-comparison` conserva `summary.json` y
`summary.md`. El informe completo también puede reconstruirse con Python sin
dependencias del proyecto:

```bash
python scripts/playtech-family-live-compare.py compare \
  --manifest scripts/playtech-family-live-manifest.json \
  --input-dir live-evidence \
  --output comparison/summary.json \
  --markdown comparison/summary.md
```

Los resultados medidos se añadirán al finalizar la ejecución. La comparación
offline de 122/175 a 159/175 comandos sigue siendo una métrica independiente.
