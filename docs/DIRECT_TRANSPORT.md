# Transporte directo y política común

Tester-Spin prefiere iniciar una demo nueva y enviar HTTP/WebSocket sin renderizar el juego. Los contratos, selectores, firmas y cierres siguen siendo propios del proveedor: compartir el transporte no autoriza inventar payloads ni compras.

`tester_spin/transport_policy.py` define la política común y los perfiles de los proveedores ejecutables. El finalizador incorpora `structural_map.transport_policy` a los resultados nuevos. Describe la ruta implementada, no demuestra que una ronda haya funcionado. Los proveedores futuros sin contrato quedan explícitamente sin implementación.

Reglas compartidas:

- Identidad y sesión demo nuevas; nunca reutilizar credenciales de un HAR.
- No repetir una apuesta enviada cuando su aceptación es incierta.
- El respaldo de arranque necesita un contrato conocido y ocurre antes de las apuestas. La selección del respaldo no depende del nombre del juego.
- Las opciones proceden de configuración y respuestas actuales. Un transporte nuevo no cambia los requisitos de cobertura, balance, cierre y retorno al modo normal.
- HTTP/WebSocket conservan evidencia local. Los archivos con sesiones no se publican.

## Rutas actuales

| Proveedor | Ejecución de apuestas | Uso del navegador |
| --- | --- | --- |
| Pragmatic | HTTP | Compatibilidad de arranque si corresponde |
| 1Spin4Win | WebSocket | Compatibilidad de arranque si corresponde |
| Belatra | HTTP | Descubrimiento/compatibilidad; ejecutor directo conservado |
| BGaming | HTTP | Captura de evidencia cuando corresponde |
| KA Gaming | WebSocket y HTTP RMP | No requiere navegador en el ejecutor |
| RubyPlay | HTTP | Respaldo de arranque cuando corresponde |
| Red Tiger | HTTP | Arranque oficial; se cierra antes de ejecutar apuestas |
| 3 Oaks | HTTP | Solo ante login bloqueado por challenge; ese respaldo conserva browser-fetch |
| Yggdrasil | HTTP | No requiere navegador en el ejecutor |
| Hacksaw | HTTP | No requiere navegador en el ejecutor |
| Nolimit City | WebSocket RC4/LZW | No requiere navegador en el ejecutor |
| Playtech GPAS | WebSocket | Eliminado del ejecutor activo |

La descarga de catálogos y la captura auxiliar pueden seguir usando navegador. Esto no convierte en ejecutables a proveedores que solo tienen catálogo. Red Tiger y el respaldo de 3 Oaks siguen teniendo una dependencia explícita del navegador; no se afirma que toda ejecución sea completamente libre de Chromium.

## Playtech GPAS

El arranque HTTP consulta la versión y el mapa de juegos actuales, descarga el manifiesto y sus scripts, y sigue cargadores estáticos literales dentro del directorio del juego. Hay límites de tamaño y cantidad; no se ejecuta JavaScript descargado. No se fija una versión ni un archivo de un juego concreto.

La configuración vigente indica el servidor demo permitido. El handshake Socket.IO v1 crea una conexión nueva. `InitGameSession` lleva `real=0`, `resume=false` e identidad UUID nueva, siguiendo la rama demo del cliente. Se solicita configuración con scopes aunque el manifiesto antiguo omita esa bandera: sin scopes el servidor puede devolver una estructura distinta.

El transporte compartido `CorrelatedSocket` tiene cancelación, plazo por respuesta, observación de tramas y cierre garantizado. Los controles de heartbeat/desconexión los declara el contrato GPAS; el transporte no los presupone para otros proveedores. Cada comando se envía una sola vez y se contrasta su correlación. No se inicia Chromium como reintento después de un timeout.

Los motores Playtech no GPAS conservan PARCIAL hasta contar con contrato. La implementación anterior de navegador queda como referencia, sin ser seleccionada por el adaptador activo.

## Validación del cambio

Pruebas unitarias de envío único, timeout, cancelación, heartbeat configurable, identidad nueva, configuración con scopes, seguimiento estático de módulos y limpieza de recursos. Pruebas reales en demos nuevas: Blazing Bells (dos rondas cerradas, OK), Lunar Link Nile Moon (base, antebet y retorno, OK), Taco (base, antebet, compra y retorno cerrados; PARCIAL por elecciones restantes). No equivalen a una corrida completa del catálogo ni a una medición del ahorro de memoria.
