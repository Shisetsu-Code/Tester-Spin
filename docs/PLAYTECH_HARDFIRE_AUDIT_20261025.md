# HardFire HARs del 25 de octubre de 2026 — corrección de primitivas Playtech

## Alcance de los archivos recibidos

Se analizó localmente `HardFire-HARs.7z` (SHA-256 `9b164c956aaecdd58d377685e94df0de436b061a138bf5a9942523d333d7cbfb`). Contiene **32 HAR**, ocho vacíos, 24 con tráfico. Son **capturas**, no 32 identidades de juegos: algunos HAR incluyen varias conexiones del mismo juego y otros se abrieron demasiado tarde para observar un `InitGameSession`.

La evidencia atribuible incluyó **ocho demos GPAS** (32 solicitudes de juego y 31 respuestas emparejadas por correlación) y **siete NGM** con manifiesto JMM. Otras 17 solicitudes de juego proceden de conexiones sin identidad de juego confirmable; no se les asigna un título por proximidad temporal.

Los HAR brutos son PRIVADOS: contienen URLs, mensajes de socket y datos de sesión. **Nunca subir esos HAR, tokens ni payloads al repositorio público.** Únicamente se conserva `tests/fixtures/playtech_hardfire_20261025_sanitized.json` con nombres de modalidades, conteos y estados. No es un mecanismo de reproducción ni acredita éxito sin servidor nuevo.

## GPAS: comparativa de los mismos ocho juegos

| Código | Antes, Actions 40180166097 | Después de primitivas | Cambio compartido |
|---|---|---|---|
| `gpas_ghgranny_pop` | PARCIAL | **OK, 5 rondas** | Reconoce `ultra` como antebet con ámbito y controlador actuales |
| `gpas_icave_pop` | PARCIAL | **OK, 3 rondas** | Par `default-N` / `feature-N`, selector base `default`, validación del coste 3:2 |
| `gpas_pigeonfs_pop` | PARCIAL | **OK, 3 rondas** | Base numérica + compra `BuyBonus` con selector `buy-bonus`; FreeGame automático hasta cierre |
| `gpas_twolf_pop` | PARCIAL | **OK, 3 rondas** | `Classic` como modalidad base alternativa, no compra ni antebet |
| `gpas_diamdhrbf_pop` | PARCIAL | **OK, 3 rondas** | Compra al `defaultBaseCostMultiplier=50` declarado, antes fallaba al mínimo 1 |
| `gpas_lluckmcc_pop` | OK | OK, 4 rondas | Control de regresión antebets extraFG/extraCollector |
| `gpas_krfforest_pop` | PARCIAL | PARCIAL | 6x/15x/30x: el selector supuesto devuelve UUID incorrecto; se bloquea |
| `gpas_krsqueen_pop` | PARCIAL | PARCIAL | 600/1200/1900/2700 sin contrato ejecutable verificado |

**Total observado:** 1/8 OK al principio; **6/8 OK** tras las correcciones y la ejecución aislada de compras, sin editar estados manualmente. La primera repetición completa de la matriz 8 GPAS + 7 NGM está en [Actions 40180767608](https://github.com/Shisetsu-Code/Tester-Spin/actions/runs/40180767608); la prueba definitiva de compra para Double Heat Crown / Pigeon / Granny está en [Actions 40181235636](https://github.com/Shisetsu-Code/Tester-Spin/actions/runs/40181235636).

## Reglas que se implementaron

1. **Antebet ultra:** exige `activeBetOptions`, scope `featureType=ultra`, `extraBetEnabled=true` y controlador real `ExtraBetsModule` / equivalente.
2. **Pares económicos completos de dos modos:** detecta `Classic` (base), `default-N/feature-N` (base y ante) y `N/BuyBonus` (base y compra) solo cuando las filas activas, UUID, empezadas y winlines coinciden con el contrato; configuraciones ambiguas siguen UNKNOWN.
3. **Compras y multiplicadores:** usa el multiplicador predeterminado del servidor solo para PURCHASE si está dentro de `baseCostMultipliers` y bajo el límite `maxBet`; nunca lo aplica indiscriminadamente a un giro o antebet.
4. **Contabilidad:** las rondas requieren exactamente un cargo inicial, cero cargos en la continuación, total de ganancias consistente, `gameRoundClosed=true`, estado terminal y saldo reconciliado. Si una compra es incierta, no se reenvía.

## NGM (siete capturas)

Las demos `roos`, `ub`, `ashamw`, `dvncvnoptpp`, `er`, `gemheat` y `anwild` permanecieron `PARCIAL` en la primera prueba. **Sus siete HAR con tráfico contienen JMM pero ninguno incluye el cliente `.cache.js`.** Sin el código que liga handlers, serializadores, botones y calculadores no es posible certificar inventario económico ni completar las ramas desconocidas.

Los giros normales observados que cierran siguen siendo evidencia útil, pero no equivalen a demostrar que no hay compras/antebets. Para ampliar el motor NGM harán falta capturas que preserven el cliente JavaScript ejecutado (también si llega desde caché del navegador), recursos JMM del mismo juego y señales de acciones/respuestas y cierre; no se debe desactivar el verificador para aumentar artificialmente los OK.

## Reproducción

El workflow `.github/workflows/playtech-hardfire-20261025.yml` prueba exactamente los 15 juegos atribuibles en siete lotes nuevos; `.github/workflows/playtech-hardfire-purchases-20261025.yml` prueba las tres compras prioritarias. La suite CI incluye `tests/test_playtech_hardfire_20261025_modes.py` y `tests/test_playtech_hardfire_20261025_evidence.py`.

La mejora aquí se mide sobre los ocho juegos GPAS de estos HAR; no implica convertir en OK los más de 30 parciales de otra corrida local ni los otros 50 NGM del ZIP anterior.
