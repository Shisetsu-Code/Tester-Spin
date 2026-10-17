# Familias GPAS: ampliación del 17 de octubre de 2026

La revisión offline filtró 201 HAR de la corrida. El catálogo conserva 359 OK y 553 PARCIAL: esta ampliación no modifica estados históricos ni garantiza nuevos OK sin repetir las pruebas.

## Cambios compartidos

- Cargadores estáticos: literales, variables, concatenación y selección explícita del bundle moderno mediante el chequeo noModule. Se mantiene la restricción al directorio del juego y los límites de recursos. No se ejecuta código descargado. Expresiones dinámicas desconocidas quedan pendientes.
- Se conservan los scripts descargados aunque todavía no tengan el comando conocido. El arranque obtiene configuración demo y conserva evidencia antes de rechazar un contrato desconocido. Eso no habilita apuestas con contratos nuevos.
- Los scopes explícitos tienen prioridad al construir featureType/betType. Las variantes defaultLow/Mid/High requieren además el controlador de volatilidad; las extras se vinculan con sus controladores, incluida la variante singular ExtraBetModule.
- Los descriptores baseCostName/betParams/betType del cliente vinculan etiquetas arbitrarias a SPIN, PURCHASE o ANTE_BET. Las opciones provienen de las filas de coste y activeBetOptions de la sesión, no del inventario de clases del código.
- Las compras escaladas y BF numeradas requieren enlace de cliente y scope o declaración featureBetEnabled. Los precios y UUID nunca determinan su tipo.
- Las tablas numéricas de líneas se reconocen solo con parámetros winline y startingMode consistentes con el contrato de líneas. No se clasifican por el aspecto numérico del nombre.
- Las elecciones se acumulan por modalidad/fase. Tras cerrar y reconciliar una ronda, el ejecutor reentra por una ronda nueva y prioriza una opción pendiente. Hay un máximo de 32 reentradas por modalidad y no se repite un objetivo sin progreso. La cobertura pendiente no se convierte en OK al alcanzar el límite. Se valida otra ronda base al final.
- El enlace compilado de pick puede seguir la cadena constructor de parámetros -> continuación 48775 -> serializador playOut, con nombres extraídos del cliente. Una palabra pick aislada no autoriza comandos. Un dominio vacío permanece pendiente.

## Evidencia y límites

El contraste offline reconoce completamente las declaraciones de **55 de los 110 juegos** antes bloqueados por UNBOUND_STAKE_MODE; los otros 55 siguen requiriendo análisis. Es reconocimiento de declaraciones, no cobertura de ejecución ni 55 nuevos OK.

Demos nuevas mediante HTTP/WebSocket, sin navegador:

| Representante | Resultado observado |
| --- | --- |
| Stars Ablaze | 12 variantes y retorno normal, 13 rondas cerradas, OK |
| Egyptian Emeralds | 10 apuestas por líneas y retorno, 11 rondas cerradas, OK |
| Big Bad Towers | Base, compra BuyBonus y retorno, 3 rondas cerradas, OK |
| Taco Libre | Base, antebet, compras para recorrer elecciones y retorno, 11 rondas cerradas, 12/12 opciones declaradas, OK |
| Streak of Luck Double Dice | Avanza con pick; otra fase LIST_PICK devuelve lista vacía, PARCIAL/PICK_DOMAIN_UNKNOWN |

Son representantes de primitivas, no excepciones por título. Los resultados de validación están separados de la base del usuario en data/family-validation, sin publicar sesiones ni HAR.

## Evidencia necesaria para lo que sigue

- **Heart of the Frontier (ashhof), motor no GPAS:** HAR completo desde antes de cargar hasta una tirada cerrada. Si ofrece compras/antebets, incluir una de cada tipo y sus decisiones/cobro. La captura antigua index.html citada en el chat ya no está en su ruta del escritorio; el HAR de SlotsTemple disponible corresponde al lanzamiento y no sustituye el ciclo del motor.
- **Streak of Luck Double Dice:** HAR completo con la secuencia que muestra Continue/Collect y, si está disponible, Collect Half. El servidor anuncia una fase sin índices y hay que contrastar qué acciones habilita el cliente y cómo las serializa. Los enum del cliente existen; no basta con enviarlos indiscriminadamente.
- **Familia adicional no GPAS:** una captura completa de un juego con otra ruta de lanzamiento, por ejemplo Book of Duat si abre. La evidencia de una familia no habilita las demás ni los juegos de mesa.

No hace falta reenviar los 201 HAR actuales ni capturar cada juego. La integración de motores NGM/otras familias y los comandos de cartas/mesa sigue pendiente de contratos verificables.
