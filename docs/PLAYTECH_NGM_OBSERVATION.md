# Observación del motor NGM demo

NGM offline genera respuestas en el cliente oficial. No debe tratarse como GPAS ni como ejecución verificada por servidor.

`providers/playtech/ngm_observation.py` descubre puntos de observación estáticos por relaciones entre funciones, sin ejecutar JavaScript de HAR y sin listas de juegos o nombres minificados:

- Entrada y salida del despachador local, únicamente cuando hay un candidato inequívoco.
- Valor calculado en la cadena colección de pagos → suma → crédito → objeto de resultado. No se deduce el premio de un campo opaco de respuesta ni de una diferencia de saldo.
- Cadenas ausentes o ambiguas no producen un punto de premio.

Los puntos son para instrumentar un cliente oficial recién cargado en demo mediante condiciones de depuración que siempre devuelven false. No son comandos de apuesta ni un certificado del motor. La huella del recurso y las ubicaciones efectivas se conservan en las capturas privadas.

## Validación 2026-10-17

14 pruebas sintéticas y regresiones del analizador aprobadas. El cliente oficial de Heart of the Frontier permitió localizar los tres puntos sin nombres específicos. Una tirada demo real mediante Space produjo petición local, respuesta local y premio calculado 0, con notificaciones de ronda. La evidencia completa permanece fuera del repositorio.

Esta validación no cubre un premio positivo, límites de pago, rondas especiales o inventario completo de compras/antebets. El observador privado consume este módulo. El ejecutor automático NGM de Tester-Spin todavía no está habilitado: faltan las pruebas de cierre de ronda y los contratos de opciones antes de otorgar OK. Ninguna respuesta local se presenta como respuesta de servidor.
