# Tabla y distribución de la ventana

La lista muestra Cantidad de compras y Cantidad de antebets. Pulsar cada encabezado alterna orden numérico ascendente y descendente. El cero representa ausencia confirmada; el guion representa datos desconocidos. Las cantidades utilizan la misma evidencia que los informes, sin contar recorridos internos de los bonos como opciones nuevas. Los resultados se actualizan durante las pruebas y al recargar el catálogo.

Arrastrar los separadores entre Programa e informes, Proveedor y catálogo, Prueba de juegos, Estado y el área de trabajo ajusta sus alturas. Dentro del área de trabajo se ajustan Juegos/Detalle horizontalmente y Registro verticalmente. Detalle permite ajustar miniatura, texto y acciones. Los bordes de los encabezados cambian el ancho de cada columna; la barra horizontal permite acceder a todas las columnas cuando no caben.

La distribución, el tamaño de ventana y los anchos se guardan localmente en data/ui-layout.json automáticamente al redimensionar la ventana, al terminar un arrastre y al cerrar. Se restauran también la posición y la maximización de la ventana. No afectan la configuración de pruebas ni la evidencia de los juegos. Eliminar ese archivo con la aplicación cerrada restaura la distribución inicial. Un archivo inexistente o inválido no impide iniciar.

## Abrir el juego en HardFire

Seleccionar un juego y pulsar **Abrir en HardFire**, o hacer doble clic en su fila, abre una pestaña nueva y visible en HardFire. Las pestañas existentes se conservan. **Abrir juego** sigue utilizando el navegador predeterminado.

Tester-Spin conecta con el MCP local de HardFire y, si hace falta, inicia su instalación local. Si HardFire no está instalado, muestra el problema sin bloquear las pruebas. Para instalaciones en otra ubicación se puede configurar `HARDFIRE_APP_PATH`; `HARDFIRE_MCP_URL` admite únicamente el servidor HTTP local.

La distribución se conserva entre actualizaciones porque pertenece al directorio de datos compartido, no a la versión del programa.
