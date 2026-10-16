# Belatra: comprobación pública de acceso — 16 de octubre de 2026

La comprobación usó peticiones GET públicas con verificación TLS habilitada, sin sesiones históricas ni escritura a la base de datos. No se ejecutó ninguna apuesta ni se certificó ningún juego.

## Evidencia actual

- El catálogo oficial `https://belatragames.com/es/games/category/2` respondió HTTP 200.
- Las fichas de `princess-suki` y `coins-blast`, seleccionadas del catálogo actual, respondieron HTTP 200 y declararon respectivamente `https://demo.bltr-static.com/belatra/demo?game=princess_suki` y `https://demo.bltr-static.com/belatra/demo?game=coins_blast`.
- Ambos launches, usando el idioma de la ficha (`language=es`), fallaron durante TLS con `TLSV1_UNRECOGNIZED_NAME`. No hubo respuesta HTTP de juego ni petición POST `/game`.
- El sitio público `https://free-slot.belatragames.com/` respondió HTTP 200 y enlazó `play/coins-blast`. Esa página respondió HTTP 200 y anunció un iframe en `https://demo.bltrm.com/belatra/demo?language=en&return_url=https://free-slot.belatragames.com/&game=coins_blast&c=1` (entidades HTML decodificadas).
- El iframe alternativo anunciado respondió HTTP 403 con una página HTML titulada `Just a moment...`, sin `var config`. No ofrece un bootstrap válido en este entorno.

## Clasificación y alcance

El host anunciado por el catálogo sigue siendo el mismo que usa el proveedor. El problema reproducido está antes del protocolo: rechazo TLS del host público y rechazo HTTP de la alternativa oficial. No hay evidencia para sustituir el host, omitir la comprobación TLS, inventar rutas o repetir launches indefinidamente.

El ejecutor existente conserva `ERROR`, cero giros satisfactorios y `spin_validated=false` cuando falla el bootstrap. La expansión exhaustiva retorna inmediatamente para `ERROR`, sin convertir el acceso fallido en éxito ni intentar compras. No se modifica código de transporte o primitivas por este bloqueo externo. Los OK históricos no se vuelven a certificar con esta comprobación.
