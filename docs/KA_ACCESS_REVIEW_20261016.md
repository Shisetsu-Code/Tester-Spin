# KA: acceso y firma actual, 16 de octubre de 2026

El catálogo oficial respondió HTTP 200 con 1043 entradas y conserva `gameLaunchURL=https://gamesdemo.kaga88.com`. El launcher anuncia el cliente 2080, versión 1.0.267 (2080). El extractor anterior sólo admitía nombres ofuscados de builds anteriores y rechazaba la firma antes de iniciar una sesión.

Se conserva el algoritmo observado y sus campos repetidos mediante referencias del patrón; sólo se permite variar los identificadores generados por el ofuscador. Una fixture sintética reproduce la estructura actual sin incluir el literal real. Se comprobó primero que fallaba la extracción, y después que extrae el perfil y rechaza una alteración del algoritmo.

Una sesión control de ThreeMonkeys obtuvo HTTP 200 y ec=0 en startGame y endSession con el cliente actual. El probe omitió modos de giro y terminó localmente con StopIteration después del inicio; no valida giros ni actualiza resultados. El HAR permanece local en `data/ka-access-review-20261016/threemonkeys/tests/20261016-055056-52cf65/analysis/http.har`. No se atribuye retrospectivamente la serie 404 anterior al cambio de firma, ni se cambian endpoints.

## Seis parciales históricos revisados

Se consultó la base sólo en modo lectura y se examinaron respuestas locales de las corridas del 13 de octubre:

- BangBang: resultado adicional `as` con `swu`, `fsw` y `sm`, y evento gratuito activo (`acb=1`, `fsr=10`). La estructura adicional impide continuar con el reconocedor actual.
- CaptainBlackCat: giro terminal; el probe de regreso encontró la misma familia adicional de `as`, con `swu`, `fsw` y `sm`, y no pudo confirmar regreso.
- BlazingBuffalo, CrazyWomensJail y SoccerShowdown: giros y probes terminales; declaraciones de compra/ante incompletas (`CLIENT_CAPABILITY_UNRESOLVED`). Requieren inspección de declaraciones, no suponer ausencia de características.
- TheNaughtyTattooist: HTTP 404 durante recorrido de compra. Necesita nueva ejecución controlada después de recuperar acceso.

No se añadieron primitivas para estos parciales ni se reescribieron resultados. Las respuestas, sesiones y literal actual permanecen locales.

## Validación posterior y pausa explícita del servidor

Después de recuperar firma y declaraciones, ThreeMonkeys, BangBang y RoaringEra
completaron pruebas actuales con OK. El lote pendiente pudo recorrer sus 42
entradas sin que un 404 simple cancelase el resto; dio un OK y 41 errores.
Los dos controles adicionales anteriores explican el aumento de 256 a 259 OK.

Una inspección de respuestas actuales determinó que los 404 de startGame
incluyen Retry-After. Dos respuestas consecutivas declararon 85304 y 85302
segundos: una pausa común hasta el 17 de octubre de 2026 a las 09:05:19 UTC
(06:05:19 de Argentina). No es evidencia de ausencia de compras ni de un juego
inexistente. No se enviaron nuevas consultas después de identificar ese plazo.

La pausa se conserva localmente entre procesos y se comprueba antes de enviar
peticiones. Un rechazo sin Retry-After sigue siendo un error del juego; una
pausa explícita termina el lote como RATE_LIMIT y conserva el ERROR original.
La cancelación solicitada por el usuario conserva prioridad. Los 529 registros
pendientes del catálogo no se ejecutaron durante esta reparación.
