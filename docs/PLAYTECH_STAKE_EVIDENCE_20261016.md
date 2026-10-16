# Evidencia GPAS: selección de coste (2026-10-16)

Nota histórica de la fase del lector de HAR. El ejecutor incorporado después se documenta en [PLAYTECH_EXECUTION.md](PLAYTECH_EXECUTION.md); las menciones a ejecución pendiente y las cifras de pruebas de esta nota corresponden a esa fase anterior.

`round_evidence` conserva en `stake_selection` los campos presentes de `gameData`: `stakeCostUuid`, `stakeCostName`, `stakeCostParameters` y `baseCostMultiplier`. Copia los valores sin normalizar ni completar ausencias; un objeto vacío significa selección no observada. No enlaza automáticamente una declaración, calcula precios ni autoriza comandos.

Base: lectura estática del serializador GPAS capturado, recurso `http:25` de la muestra privada `bb37d8a224f013071fc8ff7a`. El lector y escritor de datos de ronda incluyen UUID, nombre, parámetros y multiplicador; `stakeCostId` aparece en otro objeto (saldo personal), por lo que no se trasladó al contrato de ronda. Ningún script capturado fue ejecutado.

Se obtuvieron otras tres capturas pasivas del catálogo ERROR/PARCIAL y Aislador las filtró. Una aportó configuración GPAS; dos no aportaron evidencia utilizable de protocolo. La nueva configuración vuelve a mostrar una declaración efectiva compartida entre default y freespin, con tamaños y límites diferentes. No se observaron rondas en ese informe; conserva solicitudes sin respuesta y advertencia de inicialización.

La primitiva mejora la conservación de evidencia cuando se observe una ronda. Las pruebas de sus valores son sintéticas: no demuestran una ronda real ejecutada. Compras y antebets siguen desconocidos. El ejecutor Playtech permanece pendiente; ninguna captura histórica ni lectura de configuración certifica OK.

## Verificación

Las 20 pruebas `test_playtech*.py` pasan con el entorno `.venv`, incluidas tres nuevas que primero fallaron por ausencia de `stake_selection`. `git diff --check` no reporta problemas.

La suite general no está validada. Una primera ejecución accidental con Python global terminó con 969 pruebas, 170 errores (entre ellos dependencias ausentes `pytest` y `curl_cffi`) y el fallo `test_scheduler_never_accepts_ok_with_uncovered_branch`. Se repitió con pytest del entorno correcto; se detuvo tras casi diez minutos sin resumen final. Esto no equivale a una suite general verde.
