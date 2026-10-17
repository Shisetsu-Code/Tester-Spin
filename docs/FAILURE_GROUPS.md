# Grupos de fallos y reintentos

Cada corrida de interfaz genera, junto a la revisión manual, archivos `.groups.json` y `.groups.md`. Los módulos independientes los guardan como `summary.groups.json/md` dentro de su carpeta de corrida.

Los grupos se ordenan por juegos distintos afectados, separando proveedor, causa, código estable y contrato observado. Se incluyen hasta dos representantes, afectados y enlaces a artefactos existentes. Importes, UUID de juego, sesiones y hashes de bundles no definen familias. Sin contrato observado, el grupo es una pista por causa: no prueba que todos los juegos compartan protocolo ni autoriza aplicar una primitiva automáticamente.

La comparación usa el último resultado anterior de cada juego realmente probado: corregidos, regresiones, pendientes, OK conservados y nuevos. No se compara un juego que no recibió resultado en esta corrida. Se muestran aparte pendientes sin resultado y cancelados. Las marcas manuales no convierten un fallo automático en éxito técnico. Los informes no modifican estados, catálogos, HAR ni contratos.

## Interfaz

En la barra de pruebas, **GRUPOS / REPROBAR** abre los grupos actuales del proveedor seleccionado. La ventana muestra representantes, causas y carpetas de evidencia. **REPROBAR GRUPO** ejecuta únicamente sus afectados que sigan en el catálogo, con los controles normales de concurrencia, repeticiones, timeout y DETENER. **GUARDAR INFORME** exporta el resumen sin iniciar juegos.

Al finalizar una tanda, el registro muestra la ruta del informe agrupado. El siguiente análisis debe empezar por el grupo de mayor impacto y uno o dos representantes; después se repite el grupo para medir la mejora.

## Módulo independiente

```powershell
python -m tester_spin.cli run playtech --group-report "ruta/summary.groups.json" --group-id "ID_DEL_GRUPO" --dry-run
python -m tester_spin.cli run playtech --group-report "ruta/summary.groups.json" --group-id "ID_DEL_GRUPO"
```

Ambos argumentos son obligatorios juntos. El informe debe corresponder al esquema y proveedor seleccionados. La selección se cruza contra el catálogo actual; nunca se ejecutan URLs ni comandos contenidos en el informe. En modo grupo se incluyen sus miembros aunque ahora estén OK, para poder verificar correcciones y detectar regresiones; siguen disponibles `--game`, `--offset` y `--limit` para acotar la muestra. WireGuard conserva su flujo habitual y no se activa en dry-run.

## Validación

Pruebas sintéticas: agrupación y separación de contratos/proveedores/causas, deduplicación, prioridades, comparación limitada a retestados, cancelaciones, redacción de secretos, informes compatibles con revisión manual, cruce por proveedor y selección CLI de miembros ahora OK. No se envían apuestas para validar esta función.
