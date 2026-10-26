# Comparación de primitivas con demos actuales

Esta prueba mide el efecto incremental del PR #38 frente a su base, el PR #37.
Ejecuta el tester habitual sobre sesiones nuevas de las demos oficiales; no
reproduce credenciales ni comandos de los HAR históricos.

## Resultado medido: 26 de octubre de 2026

**Se eliminaron 0 parciales en esta muestra: 6 PARCIAL y 3 OK antes y después.**
No hubo regresiones de estado, errores de ejecución ni resultados ausentes.
La [corrida 40330136716](https://github.com/Shisetsu-Code/Tester-Spin/actions/runs/40330136716)
completó los nueve pares. Las 18 celdas son válidas y los nueve pares coinciden
en fuentes del cliente, configuración proyectada, manifiesto y entorno.

| Familia histórica | Juegos | OK antes → después | PARCIAL antes → después | Modos verificados antes → después | Rondas verificadas antes → después |
|---|---:|---:|---:|---:|---:|
| Quickspin moderno | 1 | 0 → 0 | 1 → 1 | 0 → 5 | 0 → 6 |
| Corosin moderno | 7 | 3 → 3 | 4 → 4 | 19 → 19 | 26 → 26 |
| Corosin legacy | 1 | 0 → 0 | 1 → 1 | 1 → 1 | 2 → 2 |
| **Total** | **9** | **3 → 3** | **6 → 6** | **20 → 25** | **28 → 34** |

La mejora de Quickspin se ejecutó realmente: Brawler pasó de
`CLIENT_COMMAND_BINDING_UNKNOWN`, sin rondas, a verificar base, antebet y tres
compras simples. Cerró seis rondas, incluido el regreso a base, mediante seis
entradas y 39 continuaciones. Sigue PARCIAL por sus tres compras combinadas con
antebet. El descubrimiento ahora muestra esos tres pendientes; antes el fallo
de contrato impedía incluso descubrir el dominio, por lo que el aumento del
contador de modos desconocidos no representa una regresión.

Wild Roll conservó OK en ambos lados y cerró sus tres compras. Sus importes
internos BF3Cards/BF6Cards/BF9Cards cambiaron de 1000/1500/2000 a
50000/75000/100000, aplicando el factor 50 del contexto propio de cada compra.
Esto prueba la aplicación del nuevo cálculo, sin aportar una conversión de
PARCIAL a OK. God of Storms 2 y Oriana's Orbs también conservaron OK.

### Primitivas que mantienen los seis parciales

| Grupo pendiente | Juegos afectados de esta muestra | Evidencia actual |
|---|---:|---|
| Selectores Quickspin de compra combinada con antebet | 1 | Tres `buyFeature*ExtraBet` siguen como `UNKNOWN_FEATURE`. |
| Vinculación de variantes y parámetros Corosin modernos | 4 | Veinte modos sin vínculo: HR10/20/40, highStakes, siete BF_* y nueve variantes numéricas. |
| Elección de bonus Corosin legacy | 1 | La compra entra, pero su continuación falla con `PICK_COMMAND_NOT_BOUND`. |

Los cuatro casos modernos son Glorious Griffin, King of the Barrels, Fish Trio
y Golden Pile: Toltec Treasure. El legacy es Shields of Rome: una entrada de
compra quedó sin continuar por falta de vínculo de elección; se verificó después
el regreso a base en una demo nueva. Esa única ronda no verificada ocurre en
ambos lados. Los grupos identifican trabajo compartido pendiente; no garantizan
que resolver el primer bloqueo cierre todas las variantes posteriores.

El workflow quedó rojo porque el gate exige que los nueve candidatos sean OK.
Los nueve jobs de ejecución y recolección finalizaron correctamente. La
[suite CI #972](https://github.com/Shisetsu-Code/Tester-Spin/actions/runs/40330144669)
también terminó correctamente. No se hicieron reintentos adicionales de demos.

### Evidencia preservada y reproducción

- [Informe JSON de Actions](evidence/playtech-family-live-20261026/summary.json).
- [Informe completo por familia y juego](evidence/playtech-family-live-20261026/summary.md).
- [Procedencia y hashes de los diez artefactos](evidence/playtech-family-live-20261026/provenance.json).
- [Las 18 celdas públicas originales](evidence/playtech-family-live-20261026/cells/).

Se verificó el SHA256 de cada ZIP descargado contra el digest de GitHub. El
comparador local reconstruyó exactamente el JSON generado en Actions a partir
de las 18 celdas. Los pasos de protocolo Corosin variaron entre sesiones
aleatorias independientes; esa diferencia no se cuenta como una optimización.

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

La comparación offline de 122/175 a 159/175 comandos sigue siendo una métrica
independiente de las transiciones de estado medidas arriba.
