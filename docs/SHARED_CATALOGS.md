# Catálogos compartidos y una sola actualización

La interfaz y el ejecutor independiente usan `tester_spin.providers.registry`.
Las fuentes públicas de los nuevos proveedores viven en `tester_spin.catalog_sources`;
el lector común y sus snapshots viven en `tester_spin/providers/catalogs`.
No hay listas separadas de proveedores en las interfaces ni en Actions.

## Estado al 14 de octubre de 2026

Estos proveedores tienen catálogo, pero todavía no tienen protocolo de ejecución
aprendido. No se infieren cantidades de compras, antebets ni certificaciones OK
desde el catálogo. El menú ofrece cargar su catálogo y `run` rechaza empezar un
lote de pruebas sin ejecutor. Las herramientas existentes mantienen su ejecución.

| Proveedor | Juegos guardados | Alcance de la fuente |
|---|---:|---|
| Playtech | 905 | Configuración pública del showroom; disponibilidad de demo declarada por juego |
| Games Global | 82 | Selección pública destacada, separada por estudio |
| Amusnet | 192 | Listado público; depende del mercado de la web |
| Play’n GO | 475 | Listado público oficial |
| Greentube / Novomatic | 744 | Listado público incluido en el catálogo |
| NetEnt | 238 | Listado público oficial |
| PG Soft | 155 | Listado público oficial |
| Blueprint Gaming | 265 | Listado público oficial |
| Relax Gaming | 175 | Listado público oficial |
| Playson | 53 | Listado público oficial |
| Wazdan | 265 | Listado público oficial |
| ELK Studios | 158 | Listado público oficial |
| Push Gaming | 89 | Listado público oficial |

Los conteos describen las fuentes capturadas, no un inventario mundial certificado.
Games Global conserva el estudio de origen y Relax usa únicamente Own Games.
Los lectores consumen APIs, HTML, datos de servidor o sitemaps oficiales; Playtech
consulta la API de su página una vez en Chromium, sin abrir juegos individualmente.
NetEnt obtiene el contrato público del CMS de su cliente vigente sin guardar ni
hardcodear esa credencial. Los snapshots no incluyen sesiones ni credenciales.

Un fallo de red/protección, una respuesta vacía o un lector cambiado conserva el
snapshot incluido y los datos existentes. Estos lectores no tienen autoridad para
borrar juegos. Se registra fuente, fecha, cobertura y estudio en `game.json`.

## PC y actualizaciones

Los dos accesos del escritorio usan el mismo launcher actualizable:

- **Tester-Spin** abre la interfaz.
- **Tester-Spin - Proveedores** usa ese mismo ejecutable con `--providers`.

Ambos consultan la misma configuración `%LOCALAPPDATA%/Tester-Spin/updater.json`,
misma rama y misma carpeta de datos. El código se descarga una sola vez al runtime
administrado y se fija en una carpeta de versión por commit. Una corrida ya abierta
continúa con su versión; la siguiente apertura recibe la actualización completa.
No se reemplazan ejecutables de módulos ni se modifica el checkout de desarrollo.

El canal Git predeterminado es `Shisetsu-Code/Tester-Spin`, rama
`main`. La configuración que apuntaba por error a Spin-Wire migra a Tester-Spin/main conservando sus datos. Configuraciones personalizadas se
respetan. Un ejecutable completo construido con build-desktop sigue siendo fijo;
para actualizaciones automáticas se usa el launcher de los accesos del escritorio.

Para usar la copia de desarrollo sin el updater:

```powershell
python -m tester_spin.cli providers
python -m tester_spin.cli catalog netent --data-root data
```

El workflow manual recibe la clave de proveedor, valida contra el registro y carga
su catálogo si el ejecutor está pendiente. Su resumen indica CATALOG_ONLY y cero
juegos ejecutados. Si se selecciona WireGuard también para el catálogo, exige los
perfiles y usa el túnel; nunca cambia a red directa silenciosamente.

## Agregar otro proveedor

Agregar su autoridad en catalog_sources, lector si introduce otra estructura y
snapshot validado. Registro, GUI, menú, paquete y workflow lo descubren juntos.
Si necesita dependencias nuevas, declararlas en pyproject. Aprender el ejecutor es
un paso separado: debe probar modos, importes, continuaciones y cierre real antes
de habilitar OK. No requiere una segunda copia del módulo para el ejecutor aislado.
