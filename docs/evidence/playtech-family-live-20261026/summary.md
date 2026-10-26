# Playtech: comparación live por familia

Resultado: **NO PASS**.

Las familias son cohortes del HAR histórico. El contrato live se informa sólo cuando la ejecución lo declara. Una muestra acotada no demuestra causalidad ni cobertura exhaustiva.

Baseline `fbc4258af94e31ae8db70e899d0208280df9b033` · candidato `f4e524335ae07eea2f8ad5440651bcd163fed5bc`.

Celdas: 18/18; faltantes: 0; duplicadas: 0; inválidas: 0. Pares comparables: 9/9.

| Familia histórica | Juegos | Baseline OK / PARCIAL / ERROR / MISSING | Candidato OK / PARCIAL / ERROR / MISSING | PARCIAL→OK observado / atribuible | Regresiones |
|---|---:|---|---|---:|---:|
| corosin-legacy | 1 | 0 / 1 / 0 / 0 | 0 / 1 / 0 / 0 | 0 / 0 | 0 |
| corosin-modern | 7 | 3 / 4 / 0 / 0 | 3 / 4 / 0 / 0 | 0 / 0 | 0 |
| quickspin-modern | 1 | 0 / 1 / 0 / 0 | 0 / 1 / 0 / 0 | 0 / 0 | 0 |

## Capacidades y rondas

| Familia | Modos reconocidos B→C | Verificados B→C | UNKNOWN B→C | Modos pendientes B→C | Elecciones pendientes B→C | Rondas cerradas verificadas B→C |
|---|---:|---:|---:|---:|---:|---:|
| corosin-legacy | 2→2 | 1→1 | 0→0 | 1→1 | 0→0 | 2→2 |
| corosin-modern | 19→19 | 19→19 | 20→20 | 20→20 | 0→0 | 26→26 |
| quickspin-modern | 0→5 | 0→5 | 0→3 | 0→3 | 0→0 | 0→6 |

## Juegos y evidencia

| Juego | Estado B→C | Rondas B→C | Fuentes / configuración / manifest / entorno | Atribuible |
|---|---|---:|---|---|
| Brawler's Bar Cash Collect (gpas_brwcc_pop) | PARCIAL→PARCIAL | 0→6 | MATCH / MATCH / MATCH / MATCH | sí |
| Shields of Rome (gpas_sorome_pop) | PARCIAL→PARCIAL | 2→2 | MATCH / MATCH / MATCH / MATCH | sí |
| Glorious Griffin (gpas_aogggriffin_pop) | PARCIAL→PARCIAL | 2→2 | MATCH / MATCH / MATCH / MATCH | sí |
| Oriana's Orbs (gpas_dncftnt_pop) | OK→OK | 5→5 | MATCH / MATCH / MATCH / MATCH | sí |
| God of Storms 2 (gpas_gstorm2_pop) | OK→OK | 6→6 | MATCH / MATCH / MATCH / MATCH | sí |
| King of the Barrels (gpas_kobrl_pop) | PARCIAL→PARCIAL | 3→3 | MATCH / MATCH / MATCH / MATCH | sí |
| Fish Trio (gpas_phapo_pop) | PARCIAL→PARCIAL | 3→3 | MATCH / MATCH / MATCH / MATCH | sí |
| Golden Pile: Toltec Treasure (gpas_ttreasure_pop) | PARCIAL→PARCIAL | 2→2 | MATCH / MATCH / MATCH / MATCH | sí |
| Wild Roll (gpas_wlroll_pop) | OK→OK | 5→5 | MATCH / MATCH / MATCH / MATCH | sí |

### Brawler's Bar Cash Collect

- **baseline PARCIAL**: contrato live no declarado; rondas 0/0; modos pendientes: ninguno; elecciones pendientes: 0. Motivos: ValueError: CLIENT_COMMAND_BINDING_UNKNOWN.
- **candidate PARCIAL**: contrato live quickspin-modern; rondas 6/6; modos pendientes: buyFeatureExtraBet (UNKNOWN_FEATURE), buyFeature2ExtraBet (UNKNOWN_FEATURE), buyFeature3ExtraBet (UNKNOWN_FEATURE); elecciones pendientes: 0. Motivos: UNBOUND_STAKE_MODE:buyFeatureExtraBet; UNBOUND_STAKE_MODE:buyFeature2ExtraBet; UNBOUND_STAKE_MODE:buyFeature3ExtraBet; UNBOUND_STAKE_MODE:buyFeatureExtraBet; UNBOUND_STAKE_MODE:buyFeature2ExtraBet; UNBOUND_STAKE_MODE:buyFeature3ExtraBet Cobertura de ramificaciones pendiente: PURCHASE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']; ANTE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']..

### Shields of Rome

- **baseline PARCIAL**: contrato live no declarado; rondas 2/3; modos pendientes: Buy feature (PURCHASE); elecciones pendientes: 0. Motivos: PICK_COMMAND_NOT_BOUND; PICK_COMMAND_NOT_BOUND Cobertura de ramificaciones pendiente: PURCHASE_DECLARATION -&gt; ['mode-002']..
- **candidate PARCIAL**: contrato live corosin-legacy; rondas 2/3; modos pendientes: Buy feature (PURCHASE); elecciones pendientes: 0. Motivos: PICK_COMMAND_NOT_BOUND; PICK_COMMAND_NOT_BOUND Cobertura de ramificaciones pendiente: PURCHASE_DECLARATION -&gt; ['mode-002']..

### Glorious Griffin

- **baseline PARCIAL**: contrato live no declarado; rondas 2/2; modos pendientes: HR10 (UNKNOWN_FEATURE), HR20 (UNKNOWN_FEATURE), HR40 (UNKNOWN_FEATURE); elecciones pendientes: 0. Motivos: UNBOUND_STAKE_MODE:HR10; UNBOUND_STAKE_MODE:HR20; UNBOUND_STAKE_MODE:HR40; UNBOUND_STAKE_MODE:HR10; UNBOUND_STAKE_MODE:HR20; UNBOUND_STAKE_MODE:HR40 Cobertura de ramificaciones pendiente: PURCHASE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']; ANTE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']..
- **candidate PARCIAL**: contrato live corosin-modern; rondas 2/2; modos pendientes: HR10 (UNKNOWN_FEATURE), HR20 (UNKNOWN_FEATURE), HR40 (UNKNOWN_FEATURE); elecciones pendientes: 0. Motivos: UNBOUND_STAKE_MODE:HR10; UNBOUND_STAKE_MODE:HR20; UNBOUND_STAKE_MODE:HR40; UNBOUND_STAKE_MODE:HR10; UNBOUND_STAKE_MODE:HR20; UNBOUND_STAKE_MODE:HR40 Cobertura de ramificaciones pendiente: PURCHASE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']; ANTE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']..

### Oriana's Orbs

- **baseline OK**: contrato live no declarado; rondas 5/5; modos pendientes: ninguno; elecciones pendientes: 0. Motivos: sin incidencias declaradas.
- **candidate OK**: contrato live corosin-modern; rondas 5/5; modos pendientes: ninguno; elecciones pendientes: 0. Motivos: sin incidencias declaradas.

### God of Storms 2

- **baseline OK**: contrato live no declarado; rondas 6/6; modos pendientes: ninguno; elecciones pendientes: 0. Motivos: sin incidencias declaradas.
- **candidate OK**: contrato live corosin-modern; rondas 6/6; modos pendientes: ninguno; elecciones pendientes: 0. Motivos: sin incidencias declaradas.

### King of the Barrels

- **baseline PARCIAL**: contrato live no declarado; rondas 3/3; modos pendientes: highStakes (UNKNOWN_FEATURE); elecciones pendientes: 0. Motivos: UNBOUND_STAKE_MODE:highStakes; UNBOUND_STAKE_MODE:highStakes Cobertura de ramificaciones pendiente: PURCHASE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']; ANTE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']..
- **candidate PARCIAL**: contrato live corosin-modern; rondas 3/3; modos pendientes: highStakes (UNKNOWN_FEATURE); elecciones pendientes: 0. Motivos: UNBOUND_STAKE_MODE:highStakes; UNBOUND_STAKE_MODE:highStakes Cobertura de ramificaciones pendiente: PURCHASE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']; ANTE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']..

### Fish Trio

- **baseline PARCIAL**: contrato live no declarado; rondas 3/3; modos pendientes: BF_R (UNKNOWN_FEATURE), BF_G (UNKNOWN_FEATURE), BF_B (UNKNOWN_FEATURE), BF_RG (UNKNOWN_FEATURE), BF_RB (UNKNOWN_FEATURE), BF_BG (UNKNOWN_FEATURE), BF_RGB (UNKNOWN_FEATURE); elecciones pendientes: 0. Motivos: UNBOUND_STAKE_MODE:BF_R; UNBOUND_STAKE_MODE:BF_G; UNBOUND_STAKE_MODE:BF_B; UNBOUND_STAKE_MODE:BF_RG; UNBOUND_STAKE_MODE:BF_RB; UNBOUND_STAKE_MODE:BF_BG; UNBOUND_STAKE_MODE:BF_RGB; UNBOUND_STAKE_MODE:BF_R; UNBOUND_STAKE_MODE:BF_G; UNBOUND_STAKE_MODE:BF_B; UNBOUND_STAKE_MODE:BF_RG; UNBOUND_STAKE_MODE:BF_RB; UNBOUND_STAKE_MODE:BF_BG; UNBOUND_STAKE_MODE:BF_RGB Cobertura de ramificaciones pendiente: PURCHASE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']; ANTE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']..
- **candidate PARCIAL**: contrato live corosin-modern; rondas 3/3; modos pendientes: BF_R (UNKNOWN_FEATURE), BF_G (UNKNOWN_FEATURE), BF_B (UNKNOWN_FEATURE), BF_RG (UNKNOWN_FEATURE), BF_RB (UNKNOWN_FEATURE), BF_BG (UNKNOWN_FEATURE), BF_RGB (UNKNOWN_FEATURE); elecciones pendientes: 0. Motivos: UNBOUND_STAKE_MODE:BF_R; UNBOUND_STAKE_MODE:BF_G; UNBOUND_STAKE_MODE:BF_B; UNBOUND_STAKE_MODE:BF_RG; UNBOUND_STAKE_MODE:BF_RB; UNBOUND_STAKE_MODE:BF_BG; UNBOUND_STAKE_MODE:BF_RGB; UNBOUND_STAKE_MODE:BF_R; UNBOUND_STAKE_MODE:BF_G; UNBOUND_STAKE_MODE:BF_B; UNBOUND_STAKE_MODE:BF_RG; UNBOUND_STAKE_MODE:BF_RB; UNBOUND_STAKE_MODE:BF_BG; UNBOUND_STAKE_MODE:BF_RGB Cobertura de ramificaciones pendiente: PURCHASE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']; ANTE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']..

### Golden Pile: Toltec Treasure

- **baseline PARCIAL**: contrato live no declarado; rondas 2/2; modos pendientes: 20 (UNKNOWN_FEATURE), 30 (UNKNOWN_FEATURE), 40 (UNKNOWN_FEATURE), 50 (UNKNOWN_FEATURE), 60 (UNKNOWN_FEATURE), 70 (UNKNOWN_FEATURE), 80 (UNKNOWN_FEATURE), 90 (UNKNOWN_FEATURE), 100 (UNKNOWN_FEATURE); elecciones pendientes: 0. Motivos: UNBOUND_STAKE_MODE:20; UNBOUND_STAKE_MODE:30; UNBOUND_STAKE_MODE:40; UNBOUND_STAKE_MODE:50; UNBOUND_STAKE_MODE:60; UNBOUND_STAKE_MODE:70; UNBOUND_STAKE_MODE:80; UNBOUND_STAKE_MODE:90; UNBOUND_STAKE_MODE:100; UNBOUND_STAKE_MODE:20; UNBOUND_STAKE_MODE:30; UNBOUND_STAKE_MODE:40; UNBOUND_STAKE_MODE:50; UNBOUND_STAKE_MODE:60; UNBOUND_STAKE_MODE:70; UNBOUND_STAKE_MODE:80; UNBOUND_STAKE_MODE:90; UNBOUND_STAKE_MODE:100 Cobertura de ramificaciones pendiente: PURCHASE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']; ANTE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']..
- **candidate PARCIAL**: contrato live corosin-modern; rondas 2/2; modos pendientes: 20 (UNKNOWN_FEATURE), 30 (UNKNOWN_FEATURE), 40 (UNKNOWN_FEATURE), 50 (UNKNOWN_FEATURE), 60 (UNKNOWN_FEATURE), 70 (UNKNOWN_FEATURE), 80 (UNKNOWN_FEATURE), 90 (UNKNOWN_FEATURE), 100 (UNKNOWN_FEATURE); elecciones pendientes: 0. Motivos: UNBOUND_STAKE_MODE:20; UNBOUND_STAKE_MODE:30; UNBOUND_STAKE_MODE:40; UNBOUND_STAKE_MODE:50; UNBOUND_STAKE_MODE:60; UNBOUND_STAKE_MODE:70; UNBOUND_STAKE_MODE:80; UNBOUND_STAKE_MODE:90; UNBOUND_STAKE_MODE:100; UNBOUND_STAKE_MODE:20; UNBOUND_STAKE_MODE:30; UNBOUND_STAKE_MODE:40; UNBOUND_STAKE_MODE:50; UNBOUND_STAKE_MODE:60; UNBOUND_STAKE_MODE:70; UNBOUND_STAKE_MODE:80; UNBOUND_STAKE_MODE:90; UNBOUND_STAKE_MODE:100 Cobertura de ramificaciones pendiente: PURCHASE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']; ANTE_DECLARATION -&gt; ['DOMAIN_UNRESOLVED']..

### Wild Roll

- **baseline OK**: contrato live no declarado; rondas 5/5; modos pendientes: ninguno; elecciones pendientes: 0. Motivos: sin incidencias declaradas.
- **candidate OK**: contrato live corosin-modern; rondas 5/5; modos pendientes: ninguno; elecciones pendientes: 0. Motivos: sin incidencias declaradas.
