# Línea base oficial: 74 juegos Playtech del ZIP original

Ejecutado mediante [GitHub Actions #40032293990](https://github.com/Shisetsu-Code/Tester-Spin/actions/runs/40032293990), commit `1dc682b08`.

**No es un replay ni un análisis del ZIP como prueba de apuestas**: cada juego usa una sesión demo nueva, el ejecutor actual y su propia verificación financiera. Los resultados no sustituyen el historial local del usuario.

- **GPAS:** 6 OK / 24 juegos.
- **NGM:** 0 OK / 50 juegos; 25 verificaron por lo menos dos rondas, pero siguen PARCIAL por inventario/contratos.
- **Configuraciones GPAS del ZIP:** 196 filas de coste, sin inferir qué opciones son compras o giros.

## Bloqueos por grupo (cada juego se cuenta una vez)

- NGM:NGM_FEATURE_INVENTORY_UNKNOWN: 26 juegos
- GPAS:UNBOUND_STAKE_MODE: 10 juegos
- NGM:NGM_MANIFEST_IDENTITY_MISMATCH: 8 juegos
- NGM:NGM_SPLASH_NOT_CLOSED: 6 juegos
- NGM:NGM_COMMAND_UNBOUND: 5 juegos
- NGM:NGM_INSTRUMENTATION_FAILED: 3 juegos
- GPAS:ENGINE_ERROR: 3 juegos
- GPAS:CLIENT_COMMAND_BINDING_UNKNOWN: 3 juegos
- NGM:NGM_ROUND_NOT_CLOSED: 2 juegos
- GPAS:GPAS_GAME_NOT_IN_ACTIVE_RELEASE: 2 juegos

## Resultados de los 74 juegos

| Familia | Código | Estado | Rondas verificadas | Causa prioritaria | Modos sin clasificar |
|---|---|---|---:|---|---:|
| NGM | `anwild` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `aogmt` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `aogroo` | PARCIAL | 0 | NGM_SPLASH_NOT_CLOSED | 0 |
| NGM | `ashadv` | PARCIAL | 0 | NGM_INSTRUMENTATION_FAILED | 0 |
| NGM | `ashamw` | PARCIAL | 0 | NGM_COMMAND_UNBOUND | 0 |
| NGM | `ashbob` | PARCIAL | 0 | NGM_MANIFEST_IDENTITY_MISMATCH | 0 |
| NGM | `ashhotj` | PARCIAL | 0 | NGM_COMMAND_UNBOUND | 0 |
| NGM | `ashjid` | PARCIAL | 0 | NGM_COMMAND_UNBOUND | 0 |
| NGM | `ashjut` | PARCIAL | 0 | NGM_SPLASH_NOT_CLOSED | 0 |
| NGM | `ashlcl` | PARCIAL | 0 | NGM_COMMAND_UNBOUND | 0 |
| NGM | `bigsh` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `bl` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `bs` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `bt` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `bup` | PARCIAL | 0 | NGM_ROUND_NOT_CLOSED | 0 |
| NGM | `c7` | PARCIAL | 0 | NGM_MANIFEST_IDENTITY_MISMATCH | 0 |
| NGM | `catqc` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `cbells` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `ccccny` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `cm` | PARCIAL | 0 | NGM_MANIFEST_IDENTITY_MISMATCH | 0 |
| NGM | `dvncvnoptpp` | PARCIAL | 0 | NGM_SPLASH_NOT_CLOSED | 0 |
| NGM | `esm` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `evj` | PARCIAL | 0 | NGM_SPLASH_NOT_CLOSED | 0 |
| NGM | `fbr` | PARCIAL | 0 | NGM_MANIFEST_IDENTITY_MISMATCH | 0 |
| NGM | `fcgz` | PARCIAL | 1 | NGM_ROUND_NOT_CLOSED | 0 |
| NGM | `fdt` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `fdtjg` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `fdtsl` | PARCIAL | 0 | NGM_SPLASH_NOT_CLOSED | 0 |
| NGM | `fm` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `fmjp` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `fnfrj` | PARCIAL | 0 | NGM_INSTRUMENTATION_FAILED | 0 |
| NGM | `ftsis` | PARCIAL | 0 | NGM_MANIFEST_IDENTITY_MISMATCH | 0 |
| NGM | `fxf` | PARCIAL | 0 | NGM_MANIFEST_IDENTITY_MISMATCH | 0 |
| NGM | `galst` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `gemheat` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `ges` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `ght_a` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| GPAS | `gpas_agstorm3_pop` | PARCIAL | 1 | ENGINE_ERROR | 0 |
| GPAS | `gpas_aogggriffin_pop` | PARCIAL | 2 | UNBOUND_STAKE_MODE | 3 |
| GPAS | `gpas_aogwfot_pop` | PARCIAL | 1 | ENGINE_ERROR | 0 |
| GPAS | `gpas_aogww_pop` | PARCIAL | 0 | CLIENT_COMMAND_BINDING_UNKNOWN | 0 |
| GPAS | `gpas_cashrl_pop` | PARCIAL | 4 | ENGINE_ERROR | 0 |
| GPAS | `gpas_coft_pop` | PARCIAL | 3 | UNBOUND_STAKE_MODE | 1 |
| GPAS | `gpas_crylo_pop` | PARCIAL | 0 | CLIENT_COMMAND_BINDING_UNKNOWN | 0 |
| GPAS | `gpas_dostormspp_pop` | PARCIAL | 0 | UNBOUND_STAKE_MODE | 5 |
| GPAS | `gpas_eemeraldspp_pop` | OK | 11 | — | 0 |
| GPAS | `gpas_fluffyf_pop` | PARCIAL | 0 | CLIENT_COMMAND_BINDING_UNKNOWN | 0 |
| GPAS | `gpas_goalmsnjp_pop` | PARCIAL | 0 | UNBOUND_STAKE_MODE | 15 |
| GPAS | `gpas_gotabyss_pop` | PARCIAL | 2 | UNBOUND_STAKE_MODE | 3 |
| GPAS | `gpas_gotzon_pop` | PARCIAL | 3 | UNBOUND_STAKE_MODE | 7 |
| GPAS | `gpas_gporang_pop` | PARCIAL | 0 | UNBOUND_STAKE_MODE | 5 |
| GPAS | `gpas_gstorm2_pop` | PARCIAL | 2 | UNBOUND_STAKE_MODE | 4 |
| GPAS | `gpas_jokjac_pop` | OK | 2 | — | 0 |
| GPAS | `gpas_krluprising_pop` | PARCIAL | 2 | UNBOUND_STAKE_MODE | 4 |
| GPAS | `gpas_krsqueen_pop` | PARCIAL | 2 | UNBOUND_STAKE_MODE | 4 |
| GPAS | `gpas_lluckmcc_pop` | OK | 4 | — | 0 |
| GPAS | `gpas_lluckmccpp_pop` | OK | 4 | — | 0 |
| GPAS | `gpas_mgaogkol_pop` | OK | 2 | — | 0 |
| GPAS | `gpas_scqueen_pop` | PARCIAL | 0 | GPAS_GAME_NOT_IN_ACTIVE_RELEASE | 0 |
| GPAS | `gpas_squeen_pop` | PARCIAL | 0 | GPAS_GAME_NOT_IN_ACTIVE_RELEASE | 0 |
| GPAS | `gpas_wcupcc_pop` | OK | 4 | — | 0 |
| NGM | `gtsatq` | PARCIAL | 0 | NGM_INSTRUMENTATION_FAILED | 0 |
| NGM | `gtsfc` | PARCIAL | 0 | NGM_COMMAND_UNBOUND | 0 |
| NGM | `irl` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `jbells` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `jdlo` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `jpgt` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `lumli` | PARCIAL | 0 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `mcb` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `mgstk` | PARCIAL | 0 | NGM_MANIFEST_IDENTITY_MISMATCH | 0 |
| NGM | `mobdt` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |
| NGM | `mwilds` | PARCIAL | 0 | NGM_SPLASH_NOT_CLOSED | 0 |
| NGM | `nian` | PARCIAL | 0 | NGM_MANIFEST_IDENTITY_MISMATCH | 0 |
| NGM | `tmccoy` | PARCIAL | 2 | NGM_FEATURE_INVENTORY_UNKNOWN | 0 |

Los campos de configuración y los nombres de modos provienen de un export histórico; las reglas funcionales se autorizan exclusivamente mediante el contrato, la configuración y las respuestas del demo **vigente**. Las ramas aleatorias pueden variar y el resultado no debe presentarse como cifra de parciales corregidos respecto a la máquina local.

JSON correspondiente: [playtech-original-74-baseline.json](playtech-original-74-baseline.json).
