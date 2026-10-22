# Rendimiento de la interfaz

La carga inicial consulta los últimos resultados solamente del proveedor seleccionado.
El constructor carga el catálogo una sola vez. Los filtros de compras y antebets
actualizan la vista sin consultar SQLite ni reconstruir sus filas.

Las miniaturas se decodifican después de crear la grilla, en tandas de hasta 12
imágenes con un presupuesto de 8 ms por callback y pausas de 15 ms entre tandas.
Una imagen individual puede superar ese presupuesto. Cambiar de proveedor invalida
las tandas anteriores. Las imágenes se conservan para las siguientes recargas del
mismo catálogo; se invalidan cuando cambia el tamaño o la fecha del archivo y se
liberan cuando dejan de pertenecer al proveedor mostrado.

## Medición local del 2026-10-22

Con la base local de 110 MB, 4.153 resultados recientes y el catálogo inicial de
Pragmatic, cProfile midió 8,713 s antes y 2,661 s después para construir
HARToolTesterSpinApp. La versión anterior cargaba el catálogo dos veces y hacía
1.320 cargas de miniaturas. La medición termina al construir la ventana: las
miniaturas ahora continúan cargando después. No incluye el launcher, las descargas
del actualizador ni una corrida de juegos. Los tiempos dependen del equipo y la caché
del sistema operativo; no representan una garantía de velocidad.

No se requiere migrar a Rust para eliminar estas cargas redundantes de disco y Tk.
Las primitivas y los criterios de validación de los juegos no cambian.

Pruebas de regresión: tests/test_startup_performance.py, junto con las pruebas de
filtros, exportación, ordenamiento y validación manual de resultados.
