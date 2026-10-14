# Ejecutores independientes por proveedor

Los proveedores usan el mismo núcleo de Tester-Spin; hay 24 registrados, de los cuales 13 tienen catálogo y ejecutor pendiente. El registro carga solo
el módulo seleccionado. Las comprobaciones de declaración, dinero, cobertura,
cierre, retorno y contratos siguen pasando por el scheduler y los finalizadores
del programa. Separar la ejecución no convierte juegos PARCIAL en OK.

## En Windows

El acceso directo **Tester-Spin - Proveedores** abre un menú: proveedor, cantidad
total, uso de WireGuard, carpeta de perfiles y cantidad máxima por IP. Para usar
WireGuard, abrir ese acceso directo como administrador. Conserva la base de datos
y las capturas de `C:\Proyectos\Tester-Spin\data`.

También se puede instalar desde un checkout y ejecutar sin interfaz:

```powershell
python -m pip install -e ".[nolimit_city]"
python -m tester_spin.cli providers
python -m tester_spin.cli catalog nolimit_city --data-root data
python -m tester_spin.cli run nolimit_city --data-root data --limit 20
```

Cada extra instala las dependencias del proveedor: pragmatic, 1spin4win, belatra,
bgaming, ka_gaming, rubyplay, redtiger, 3oaks, yggdrasil, hacksaw, nolimit_city.
El extra `all` mantiene disponible todo el programa. Los proveedores con navegador
requieren instalar Chromium con `python -m playwright install chromium`.

Ejemplo de lote VPN; los números son argumentos configurables:

```powershell
python -m tester_spin.cli run nolimit_city --data-root data --limit 60 --wg-dir "C:\VPN\perfiles" --games-per-ip 20
```

Se puede usar `--wg-config "ruta\perfil.conf"` varias veces en lugar de una carpeta.
`--statuses ALL` incluye los juegos que ya tienen OK; por defecto se procesan
PENDIENTE, PARCIAL, ERROR y SIN_DEMO. `--game` selecciona un slug o código exacto;
`--offset` salta juegos al inicio de la selección y `--spins` configura muestras.
`--dry-run` muestra la selección almacenada sin ejecutar ni cambiar la conexión.
Un checkout vacío carga el catálogo automáticamente al ejecutar; si se solicita
VPN, esa carga también usa el túnel. `--refresh-catalog` actualiza el catálogo.

## Qué cuenta como un juego por IP

La cuota se aplica a **juegos intentados dentro de una corrida**, incluidos ERROR
y PARCIAL. Las continuaciones de una ronda no se cuentan como juegos separados.
La IP IPv4 de salida se consulta al activar la conexión y se contrasta antes y
después de cada juego. Dos perfiles que salen por la misma IP comparten cuota.
Al llegar al límite se termina el juego y se pasa al perfil siguiente, con una
sesión nueva. No se reciclan perfiles para reiniciar su cuota; si faltan IPs se
conservan pendientes y la corrida informa IP_QUOTA_EXHAUSTED. La cuota no se
presenta como un límite global entre distintas corridas, cuentas o equipos.

El túnel requiere un perfil de cliente exportado `.conf`, un peer, rutas completas
IPv4 e IPv6, tabla automática y ausencia de hooks personalizados. No se modifican
archivos originales ni túneles preexistentes. Windows usa servicios WireGuard;
Linux usa wg-quick con sudo. Ambos reservan la conexión para evitar superposición.
En Windows las rutas afectan al equipo completo: no corresponde usar dos IPs
simultáneas para dos lotes en el mismo sistema. Los runners cloud son separados.

Una conexión no verificada detiene el trabajo sin fallback a red directa. Un 429
detiene la corrida; no provoca una rotación para continuar el bloqueo. Cada juego
queda en un grupo de procesos propio: Job Object en Windows y cgroup v2 en Linux.
Esto incluye navegadores y drivers aunque lancen descendientes separados. El
proceso espera autorización del supervisor antes de abrir la sesión. No se cambia
de IP hasta comprobar que el grupo está vacío. Si ese cierre no puede comprobarse,
se aborta la corrida y se conserva el túnel activo para no cambiar la conexión de
los procesos vivos; hay que revisar ese fallo antes de iniciar otro lote.

## En GitHub Actions

En el repositorio, Actions → **Ejecutar un proveedor** → Run workflow. Elegir
proveedor, cantidad, desplazamiento, muestras, uso de VPN y máximo por IP.
Es manual: subir código no inicia apuestas. Las corridas de este workflow no se
cancelan entre sí para interrumpir sesiones. El runner instala solo el proveedor
seleccionado y sus dependencias; los que usan navegador reciben Chromium/Xvfb.
Linux requiere cgroup v2 y sudo para cerrar el árbol completo de cada juego.

Para habilitar WireGuard, guardar los perfiles en el Secret de Actions
**WG_CONFIGS_JSON**, como objeto JSON que asigna nombres a textos `.conf`.
El helper puede cargarlos desde archivos sin pasarlos como argumentos ni mostrarlos:

```powershell
python scripts/configure-wireguard-secret.py "C:\VPN\perfiles" --repo Shisetsu-Code/Tester-Spin
```

Requiere una sesión de `gh` con permisos para actualizar Secrets. No se debe pegar
ninguna clave en issues, logs, archivos del repositorio ni mensajes. El workflow
materializa los perfiles en una carpeta temporal privada y el gestor mantiene
copias propias. El límite de tamaño de un Secret también se comprueba al cargarlo.

El artefacto descargable contiene **solo public-summary.json**: proveedor, juegos,
estados y motivo de detención. No publica HAR, claves, IPs, sesiones ni registros
privados. Los resultados se guardan durante la corrida y no solo al final. En la
PC los detalles siguen bajo `data/independent/runs/<run_id>` y en las carpetas de
cada juego. En GitHub la base de datos es nueva para cada job; el desplazamiento
permite elegir otro tramo del catálogo sin importar resultados antiguos como OK.

## Comprobación y límites

Hay pruebas de carga independiente, cuotas compartidas, ausencia de fallback,
conservación de túneles ajenos, limpieza, cancelación, plazos, protección de
configuraciones y cierre de descendientes. La CLI instalada completó Airport
Security en una Demo nueva usando el mismo pipeline de validación.

La verificación de WireGuard con servidores reales requiere perfiles suministrados
por el usuario. No se certifica una conexión VPN a partir de pruebas simuladas.
El lanzador independiente no cambia por sí mismo la configuración de la GUI.

La interfaz y el menú independiente se actualizan desde el mismo runtime y commit. Véase [catálogos y actualización compartida](SHARED_CATALOGS.md).
