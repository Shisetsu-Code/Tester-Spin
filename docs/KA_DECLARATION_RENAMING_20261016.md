# KA: normalización estructural de declaraciones — 16 de octubre de 2026

El cliente común 2080 cambió los nombres ofuscados de la base del descriptor, la factory, la bandera de compra, el precio, la bandera antebet, el botón, el registro del símbolo y el recorrido RMP. El parser de capacidades reconocía los nombres 2071 y por ello conservaba un dominio incompleto aunque la autenticación y los giros fueran correctos.

`declaration_names.py` coteja las implementaciones públicas con fragmentos del contrato 2071 guardados en `declaration_reference.json`. Exige igualdad de todos los literales, operadores y relaciones entre identificadores. Los miembros de objetos y los símbolos usan espacios de nombres distintos, porque el minificador puede reutilizar un nombre global como nombre de miembro. Una coincidencia ambigua, un nuevo cuerpo, una selección diferente o un literal distinto deja el dominio pendiente.

Los fragmentos incluyen la base completa del descriptor (36 miembros), el botón completo (16 miembros), el registro del descriptor, la conexión de startGame.dbf, la serialización pos, el envío [1], el precio delegado y la condición de promoción. No contienen sesiones, saldos ni credenciales. La normalización preserva cadenas y los selectores públicos; después se ejecutan todas las verificaciones previas del parser. No se ejecuta JavaScript ni se asignan capacidades por título.

Las fuentes públicas 2080 descargadas para la comprobación local dieron HTTP 200: ThreeMonkeys acredita compras vacías y antebet vacío; JadeQuest declara pos:[1] con multiplicador 80 y antebet vacío. La configuración dbf=false de esta comprobación es un argumento controlado para probar el parser; no representa una sesión nueva ni acredita ejecución, aceptación o cierre de una compra. La prueba opcional de caché reproduce esas declaraciones.

La suite focal de declaraciones y renombrado dio 26 pruebas correctas, incluyendo fuentes heredadas, replay existente de compras, selectores alterados, literales modificados, referencias ambiguas y overrides desconocidos. No se modificó la DB ni runtime.py. La distribución debe incluir `declaration_reference.json` junto al módulo.
