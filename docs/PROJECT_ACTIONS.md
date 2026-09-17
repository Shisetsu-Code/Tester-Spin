# Programa e informes

La barra superior ofrece tres acciones. Se ejecutan en segundo plano con avance en el registro y quedan deshabilitadas durante las pruebas.

- **Subir programa a GitHub:** crea un commit con código, pruebas, documentación, scripts y archivos de inicio. Hace push a `origin` en la rama actual. Usa Git y las credenciales configuradas en el equipo.
- **Borrar historial del proveedor:** afecta al proveedor seleccionado. Archiva sus corridas, pendientes de cobertura y contratos generados; elimina sus resultados de la base y devuelve los juegos a PENDIENTE. Conserva catálogo y HAR manuales. Los informes de lotes anteriores se archivan porque pueden mezclar proveedores. Guarda copia de la base y los archivos en `data/history-backups/`. Pide confirmación. No elimina commits ni datos ya publicados en GitHub.
- **Subir reportes a GitHub:** genera `test-evidence/` con el último resultado guardado de cada juego y sus informes JSON, aplicando el filtro de claves de sesión. Reemplaza la exportación anterior, conservando una copia local. No incluye HAR ni capturas originales. Crea el commit y hace push.

Los dos botones de publicación avisan que también se enviarán los commits locales pendientes de la rama. No hacen pull, force push ni resuelven conflictos automáticamente. Si hay cambios preparados previamente en Git, piden resolverlos antes de continuar. Si el commit se creó pero falló el push, volver a pulsar permite reintentar el envío. Git debe estar instalado y el remoto `origin` configurado.

La limpieza se prueba con datos temporales; no se ejecuta automáticamente al instalar esta mejora. Las copias locales pueden contener sesiones originales: se guardan bajo `data/`, ignorado por Git. Para un nuevo conjunto completo de resultados, limpiar cada proveedor antes de ejecutar sus pruebas y después usar el botón de reportes.
