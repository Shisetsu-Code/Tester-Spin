# Tester-Spin

Aplicación de escritorio para cargar catálogos, probar demos y guardar evidencia de cada proveedor. El resumen informa compras, cantidad y antebets por juego y proveedor. Los giros normales y las continuaciones de bonus no se cuentan como compras.

## Ejecutar

En Windows, abrir `Abrir-Tester-Spin.cmd` desde el checkout. Prepara el entorno de desarrollo y abre la aplicación. Para un entorno ya instalado:

```powershell
.\.venv\Scripts\python.exe run.py
```

El ejecutable generado por `scripts/build-desktop.ps1` contiene una versión completa de la aplicación. Para incorporar cambios debe reconstruirse. El launcher generado por `scripts/build-launcher.ps1` usa un runtime actualizable: véase [autoactualización](docs/AUTOUPDATE.md).

## Versión actual

Las descargas del ejecutable completo se publican en [GitHub Releases](https://github.com/Shisetsu-Code/Tester-Spin/releases). Las capturas originales y los datos de sesión permanecen locales.

El catálogo cargado de Hacksaw tiene **187 juegos: 186 OK y uno nuevo pendiente**. La revisión del 16 de octubre recuperó los tres parciales restantes mediante primitivas compartidas del cliente; los otros 183 OK conservan su evidencia previa. Cada OK contrasta precios, débitos, premios acumulados, liquidación y dos rondas normales posteriores con IDs distintos. [Evidencia y límites](docs/HACKSAW.md).

Yggdrasil queda pausado en **137 OK, 8 parciales y 14 errores de 159 juegos**; no se presenta como catálogo terminado. [Primitivas y pendientes](docs/YGGDRASIL.md).

La grilla permite ordenar por cantidades de compras y antebets, identificar mecánicas particulares y ajustar las secciones con el mouse. [Distribución de la interfaz](docs/DESKTOP_LAYOUT.md) y [mecánicas](docs/GAME_MECHANICS.md).

Nolimit City tiene **140 demos oficiales y ejecutor Demo RC4/LZW**, con **109 OK y 31 parciales** en la última ronda documentada. Las variantes desconocidas quedan PARCIAL con HAR local. [Primitivas y alcance](docs/NOLIMIT_CITY.md).

Cada proveedor también puede ejecutarse por separado desde la PC o el workflow manual de GitHub Actions, con lotes WireGuard y máximo configurable de juegos por IP. El comando carga solo el proveedor elegido y conserva el pipeline de verificación. [Ejecutores independientes y configuración](docs/INDEPENDENT_RUNNERS.md).

El ejecutor prioriza peticiones directas y registra una política común de transporte. Playtech GPAS inicia y juega por HTTP/WebSocket sin Chromium. [Rutas y excepciones por proveedor](docs/DIRECT_TRANSPORT.md).

## Interpretar resultados

- **OK**: las operaciones requeridas y su cobertura comprobada terminaron correctamente.
- **PARCIAL**: queda una operación, transición o cobertura requerida sin demostrar; revisar el diagnóstico.
- **ERROR**: la ejecución registró un fallo; se conserva su evidencia.
- **Compras/Antebets: Sin datos**: la evidencia disponible no permite afirmar presencia o ausencia.

Una bandera del servidor no basta para contar una compra ni convertirla automáticamente en una obligación pendiente. Existencia, capacidad de ejecución y validación son estados separados. [Reglas y ejemplos](docs/FEATURE_DETECTION.md).

## Documentación vigente

- [Catálogos actualizados y OK por proveedor: 16/10/2026](docs/CATALOG_REFRESH_20261016.md)

- [Reparación compartida y resultados por proveedor: 16/10/2026](docs/PROVIDER_REPAIRS_20261016.md)

- [Operación, instalación, pruebas y compilación](docs/OPERATIONS.md)
- [Detección de compras y antebets](docs/FEATURE_DETECTION.md)
- [Contratos y cobertura de protocolos](docs/PROTOCOLS.md)
- [3 Oaks: primitivas y límites](docs/THREE_OAKS.md)
- [Red Tiger: evidencia y estado base](docs/REDTIGER.md)
- [Pragmatic: reglas y evidencia](docs/PRAGMATIC_GAME_RULES.md)
- [Nolimit City: catálogo y estado de integración](docs/NOLIMIT_CITY.md)
- [Auditoría de declaraciones por proveedor](docs/PROVIDER_CAPABILITY_AUDIT.md)
- [Hacksaw: compras, contabilidad y retorno](docs/HACKSAW.md)
- [Yggdrasil: primitivas y estado actual](docs/YGGDRASIL.md)
- [Validación y regresiones](docs/VALIDATION.md)
- [Diagnósticos por ejecución](docs/RUN_DIAGNOSTICS.md)
- [Arquitectura](docs/structural-map.md) y [adaptadores](tester_spin/providers/README.md)

Los documentos técnicos específicos de BGaming, Hacksaw, KA Gaming, RubyPlay, Spin4Win y Yggdrasil permanecen en `docs/`. Los archivos de resultados de catálogo son evidencia histórica, no certificación del catálogo actual. Los planes e informes de implementación sustituidos se retiraron; su historial sigue en Git.

## Desarrollo

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

Las pruebas usan fixtures reducidos. Las capturas HAR completas, sesiones, datos locales y ejecutables generados no se publican en Git.

Hay **24 proveedores registrados**: los 11 ejecutores existentes y 13 catálogos nuevos con ejecución pendiente. Los dos accesos del escritorio utilizan una única versión actualizable. [Catálogos, cobertura y actualización compartida](docs/SHARED_CATALOGS.md).

## Observaciones de Playtech desde Aislador

Aislador puede tomar muestras del catálogo pendiente, capturar demos frescas y
entregar `protocol-evidence.json` en `data/providers/playtech/<slug>/analysis`.
La identidad debe coincidir con el código publicado del juego y su conexión de
inicialización. No se reutilizan sesiones ni se importan estados OK.

Las primitivas `tester_spin.providers.playtech.protocol` leen los costes
declarados por ámbito, retienen opciones y elecciones anidadas, y contrastan
el cierre de ronda con sus importes. Los ámbitos `default` y `freespin` y las
listas de tamaños de apuesta no se convierten en compras ni antebets. Las
declaraciones repetidas se agrupan conservando todas sus referencias.

El adaptador incorpora ese diagnóstico cuando encuentra evidencia compatible.
El ejecutor de Playtech sigue pendiente: no se habilita una corrida ni se marca
OK por haber leído una configuración. Los contratos sin acción verificada, las
elecciones no recorridas y NGM/POP conservan ese límite. El fuzzer actual de
Pragmatic/3 Oaks no se utiliza como si fuese un explorador de Playtech.

## Opciones desconocidas con selección humana

En Detalle, **Opciones del juego** lee la pestaña activa de HardFire y muestra
controles visibles habilitados. Filtra únicamente etiquetas habituales exactas;
**Mostrar también controles habituales** permite recuperarlas. La lista no
interpreta un botón como compra ni cuenta características del juego.

Elegí una opción y pulsá **Ejecutar y capturar**: se envía un solo click y se
guarda el HAR. Las referencias vencidas no se reintentan. Para controles dibujados
en canvas, **Ver pantalla** permite marcar vos el punto y confirmar ese único
click. La imagen no pretende reconocer automáticamente todos los botones.
Si falla el guardado, **Guardar HAR pendiente** reintenta el archivo sin repetir
la acción. Si la grabación empezó tarde, el HAR puede carecer de inicialización.

Aislador filtra el archivo en segundo plano cuando está configurado. No hay
fuzzer, exploración automática, cambios de primitivas automáticos ni falsos OK.

## Capturar nuevos fallos automáticamente

Con `data/har-learning.json` configurado, cada ERROR/PARCIAL guardado inicia o
despierta el trabajador de Aislador. La interfaz y las pruebas no esperan a que
termine. El cursor evita descargar el historial: cada resultado nuevo tiene una
captura independiente, y el reinicio recupera los pendientes. Los informes están
en `data/har-learning/revision.json`, listos para revisión y nuevas primitivas.

```json
{
  "enabled": true,
  "aislador_root": "C:/Herramientas/Aislador",
  "python": "C:/Python/python.exe",
  "after_id": 100,
  "seconds": 12
}
```

El intérprete configurado necesita Playwright y Chromium para las capturas.
`after_id` es el último resultado anterior a activar la función; las consultas no
modifican la base. Configuración local, HAR y logs no se publican. La captura
pasiva obtiene inicialización y tráfico espontáneo; no pulsa menús ni reproduce
la rama que falló. Esa rama se puede capturar con la selección humana anterior.

### Configuración GPAS por contexto

El lector resuelve `scope` como el cliente capturado: deben coincidir todas sus
claves; un valor de ámbito en lista acepta los valores de esa lista. Las filas
que coinciden se combinan en el orden del servidor, conservando propiedades
anidadas y reemplazando listas completas. No se concatenan opciones antiguas.

`default` y `freespin` son contextos. Un mismo identificador de coste con la
misma declaración se agrupa como una modalidad observada en varios contextos;
si cambia cualquier parámetro, se conserva separado. Los tamaños de apuesta,
límites y capacidades quedan ligados a cada contexto. Se mantienen las filas
originales y sus referencias para auditar las sustituciones. Una configuración
con errores no aporta modalidades efectivas para ejecutar. Nada de esto prueba
por sí solo compras, antebets, cobertura de rondas ni un resultado OK.

## Playtech GPAS

El ejecutor GPAS usa sesiones demo nuevas, modalidades por nombre o UUID, compras, antebets y elecciones con estado. Los motores no reconocidos conservan PARCIAL. Véase [el contrato de ejecución y sus límites](docs/PLAYTECH_EXECUTION.md).

## Grupos de fallos

**GRUPOS / REPROBAR** prioriza causas por cantidad de juegos, muestra representantes y permite repetir sus afectados. Las corridas generan informes comparables sin cambiar estados: [uso y límites](docs/FAILURE_GROUPS.md).
