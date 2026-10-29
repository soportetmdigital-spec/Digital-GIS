# Continuidad de trabajo — Fiber GIS (Odoo 19 Community)

Actualizado: 2026-10-29  
Versión de trabajo: **19.0.4.29**  
Módulo: `fiber_gis`  
Manual funcional y fuente de verdad: `README.md`

## Cómo retomar

1. Abre la carpeta raíz `fiber_gis/` del módulo. Comprueba `__manifest__.py`, `README.md` y este archivo antes de editar.
2. Conserva las preferencias y requisitos ya fijados en el README; no elimines funciones por no tener llamadas Python directas sin revisar decoradores ORM, botones, XML, QWeb, RPC y bundles de assets.
3. Si haces cambios de código o comportamiento, incrementa la versión en el manifiesto y sincroniza `models/site.py`, las pruebas de versión, historial y continuidad del README y este archivo.
4. Ejecuta los chequeos disponibles y crea ZIP desde la raíz del módulo con `python scripts/build_release_zip.py --output-dir dist`.
5. No marques una instalación como validada sin probar en Odoo 19 Community con PostgreSQL.
6. Para CSS/SCSS, aplica la regla de compatibilidad de abajo: solo Odoo 19 Community y compilación real de assets en esa versión antes de dar por válida una corrección visual.

## Estado de esta auditoría

Se revisaron los modelos Python, inicializadores, hooks, migraciones, datos XML, vistas, informes QWeb, permisos, assets JS/XML/SCSS, imágenes, manifiesto, scripts, pruebas y las referencias cruzadas a funciones y archivos. No se detectó código o recurso sin uso que pudiera eliminarse con seguridad: varios métodos están conectados por metadatos ORM, botones o informes y los assets se cargan desde el manifiesto. La migración `19.0.3.35.0` es intencionalmente vacía para evitar repetir un renombrado histórico al saltar versiones.

### Cambio de rendimiento

La comprobación de posiciones del rack se agrupó: ordena por unidad U y detecta el primer solapamiento en una pasada; al crear varios equipos carga el conjunto de equipos del rack una sola vez por cabecera. Antes hacía una búsqueda aparte por cada equipo afectado y comprobaba solapamientos con búsquedas repetidas. Se añadió un `TransactionCase` para un lote con posiciones duplicadas.

No se cambió la carga del mapa: la UI descarga los registros y filtra por viewport en navegador. Una consulta por viewport podría reducir transferencia con redes grandes, pero hay que medir el volumen real y contemplar cables cuya geometría cruza el límite visible antes de implementarla.

## Verificaciones de entrega

Completar al generar ZIP:

- [x] Pruebas estáticas `python -m unittest discover -s tests -p 'check_*.py'` (63 comprobaciones), incluidas vista con círculos de color y resúmenes de fibras del splitter.
- [x] `node --check` en todos los JS del módulo.
- [x] Compilación Python y parseo de los 31 XML. No se modificó CSS/SCSS.
- [x] Revisión de estructura/contenido del ZIP (125 archivos, raíz `fiber_gis/`).
- [ ] Pruebas `TransactionCase` e instalación/actualización en una base Odoo 19 Community + PostgreSQL (Odoo no está instalado en este entorno).
- [ ] Compilar assets y hacer prueba visual/manual en Odoo de rack, mapa y flujos anteriores; verificar que los botones de boca coinciden con tomas de switches 24/48, patch panels y FHU. No se dispone de Odoo/Chromium en este entorno.

No declarar completadas las comprobaciones que no se hayan podido ejecutar. En este entorno de desarrollo puede no estar disponible `odoo-bin`, Chromium o una base PostgreSQL; anotar el bloqueo exacto.

## Referencias oficiales Odoo 19 Community

- Rendimiento y operaciones agrupadas: https://www.odoo.com/documentation/19.0/developer/reference/backend/performance.html
- ORM, recordsets y restricciones: https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html
- Servicio ORM y llamadas a modelos desde Owl: https://www.odoo.com/documentation/19.0/developer/reference/frontend/javascript_reference.html
- Bundles y carga de assets: https://www.odoo.com/documentation/19.0/developer/reference/frontend/assets.html
- Hooks Owl: https://www.odoo.com/documentation/19.0/developer/reference/frontend/hooks.html
- Upgrade scripts: https://www.odoo.com/documentation/19.0/es/developer/reference/upgrades/upgrade_scripts.html
- Fuentes Community rama 19.0: https://github.com/odoo/odoo/tree/19.0

## Preferencias permanentes del proyecto

- Mantener Odoo 19 Community como objetivo y usar referencias oficiales de la versión 19.0.
- Compatibilidad exclusiva con **Odoo 19 Community**: no usar APIs, sintaxis o instrucciones asumidas de otra versión. Consultar documentación oficial/código de Odoo 19 antes de cambios sensibles.
- Evitar regresiones de CSS/SCSS: el bundle debe compilar en una instancia Odoo 19 Community y el resultado visual debe revisarse allí. En `static/src/scss/fiber_map.scss`, no reintroducir `min()` con unidades mixtas ni `aspect-ratio` sin verificarlo con el compilador real de Odoo 19. Los chequeos estáticos y el balance de llaves no prueban compilación.
- Si Odoo 19 no está disponible durante una entrega, dejar explícita como pendiente la compilación real de assets y la revisión visual; usar sintaxis SCSS conservadora y no declarar validada la corrección CSS.
- Ante errores CSS, registrar causa, corrección y prueba de regresión en README y continuidad para evitar repetirlos. La regresión del modal de 19.0.4.13 por `min()` con unidades mezcladas se corrigió en 19.0.4.14.
- Incrementar versión en cada entrega de código y mantener README completo y actualizado.
- Conservar comportamiento, permisos, datos existentes y migraciones seguras; no retirar funciones por una búsqueda textual aislada.
- El armario permite zoom, varios racks por cabecera, nombres de equipo editables e interconexiones entre puertos; mover un equipo a la zona izquierda lo elimina con aviso si hay relaciones.
- Preservar los modelos reales MikroTik/Zyxel y la vista frontal del panel FS.com con atribución y autorización previamente confirmada.
- En los campos de conexión de cable usar la etiqueta «Boca» sin «entrada/salida»; arqueta por defecto con icono cuadrado negro.
- En Gestión de bandejas, los campos de Sangría se llaman «Cable entrada» y «Cable salida»; el selector conserva el nombre/matrícula contextual del cable.
- El tubo de una fibra («T1» y su color) solo se muestra si el cable tiene más de un tubo: usar `fiber.show_tube` en cualquier vista o HTML nuevo que muestre fibras.
- Color por defecto de cables dibujados en el mapa según fibras de la tipología (`MAP_CABLE_COLOR_BY_FIBERS` en `models/cable.py`): 6 celeste, 12 rojo, 16 violeta, 24 marrón, 48 verde, 72 verde oscuro, 80 azul, 96 rosa, 128 naranja, 288 negro.
- En el mapa se dibuja un cable cada vez. «Crear y seguir trazando» se retiró en 19.0.4.28 a petición de los técnicos (no se podía desplazar el mapa al llegar al borde); no reintroducir el trazado encadenado. La continuidad entre cables se registra con Sangría en Gestión de bandejas.

## Entrega de referencia

El ZIP de esta revisión debe llamarse `fiber_gis_19.0.4.29.zip` y mantener `fiber_gis/` como carpeta raíz interna. `README.md` registra las versiones anteriores, la guía funcional, pruebas y el punto de retorno.

## Iteración 19.0.4.11 — bocas interactivas del rack

- El frontal del equipo ya usa todo el ancho y alto visible del rack; el rótulo se superpone sobre la imagen.
- Las bocas del dibujo son botones numerados. Para registrar el cable, pulsa la boca de origen y después la de destino en otro equipo. La función llama al mismo método ORM de interconexión, resalta las bocas ocupadas y elige tipo de cable fibra/Ethernet según el tipo de equipo. El formulario manual sigue disponible.
- La disposición de tomas se definió para los assets del módulo (ConceptDraw switch 24/48, patch panel y FS.com FHU). Confirmar en una instancia Odoo real que la alineación visual es correcta en todos los tamaños de rack.
- Se eliminó `visualPorts`, que quedó sin uso al generar los botones desde `equipmentPorts`. La lista usa un mapa de puertos para buscar asignaciones de fibra en tiempo lineal.
- Versión anterior: 19.0.4.10. Punto de retorno: `fiber_gis_19.0.4.10.zip`.


## Iteración 19.0.4.12 — biblioteca editable y rutas visuales

- Catálogo de equipos persistente `fiber.gis.cabinet.catalog`, con imagen frontal, nombre de plantilla, altura, cantidad de bocas y coordenadas porcentuales para los marcadores. La migración `migrations/19.0.4.12/post-migrate.py` crea filas por defecto sin sobrescribir ediciones existentes.
- El usuario Responsable edita cada tipo desde el lápiz de Biblioteca. Las posiciones se ajustan arrastrando cada marcador en la previsualización. El número de bocas se aplica a los equipos ya colocados; una reducción que quite una boca conectada por cable o fibra se rechaza.
- Las conexiones tenían que validarse visualmente; la siguiente iteración reemplaza su renderizado inicial.
- Se actualizó `README.md` con el flujo de edición y reglas de datos.
- Se actualizó `README.md` con el flujo de edición y reglas de datos.
- Referencias oficiales Odoo 19 consultadas: ORM/campo Image, Hooks Owl, componentes Owl y Upgrade scripts.
- Pruebas estáticas: 56 comprobaciones; sintaxis JS; compilación Python; parseo XML; balance de SCSS. `TransactionCase`, actualización real y revisión visual quedan pendientes de Odoo 19 + PostgreSQL, ausente en este entorno.
- Versión anterior: 19.0.4.11. Punto de retorno: `fiber_gis_19.0.4.11.zip`.


## Iteración 19.0.4.13 — ventana de edición y visibilidad del cable

- Se traslada el editor del inspector lateral a una ventana modal amplia e independiente, con formulario separado de una previsualización frontal grande; dispone de diseño adaptado a pantallas estrechas.
- Se sustituye el SVG anterior por canvas 2D. El cable se pinta con trazo de color, borde blanco, sombra y flecha visible. Conserva rutas laterales en el mismo rack y superiores entre racks; se redibuja con render, zoom y cambio de tamaño de ventana.
- Verificación local: 56 checks estáticos; sintaxis de todos los JS; compileall; parseo XML; balance de llaves SCSS; ZIP íntegro y raíz correcta.
- Sigue pendiente la prueba visual real en Odoo 19 + Chromium, que no están disponibles en este entorno.
- Punto de retorno: `fiber_gis_19.0.4.12.zip`.

## Iteración 19.0.4.14 — corrección de compilación SCSS

- La captura de Odoo mostró el error fatal de compilación de estilos y el editor sin modal. Se localizó `min()` con unidades mixtas (`px`/`vw`/`vh`) en el SCSS; se sustituyó por ancho/alto y límites máximos separados, que Sass deja como declaraciones CSS sencillas.
- Se quitó `aspect-ratio` del SCSS y el alto de previsualización se calcula en JavaScript según las unidades U del equipo, manteniendo una zona amplia para ajustar las bocas.
- Se añade regresión estática para no reintroducir `min()` ni `aspect-ratio` en esta hoja. El entorno no tiene compilador Sass/libSass, Odoo ni navegador conectado a una instancia: la compilación real del bundle y la revisión visual deben confirmarse al actualizar Odoo 19.
- La prueba estática pasa junto con sintaxis JS, compilación Python y parseo XML. No se afirma que la instalación/compilación en servidor haya sido verificada.
- Versión anterior: `19.0.4.13`; retorno conservador: `fiber_gis_19.0.4.12.zip`.

## Iteración 19.0.4.15 — selección dinámica del asistente de bandejas

- Incidencia recibida desde Odoo: `ValueError` en `_work_log_text()` al hacer `dict(self._fields["operation"].selection)`. El campo `operation` declara `selection="_selection_operation"`; por tanto, `selection` contiene una referencia de método y no una lista de pares.
- Se cambia a `self._fields["operation"]._description_selection(self.env)`, que resuelve las opciones permitidas por Odoo y las etiquetas según el entorno/idioma antes de crear el diccionario.
- Se añade `tests/test_cable_tray_wizard.py` (TransactionCase) para verificar `_work_log_text()` con la operación `rest`; el test requiere Odoo + PostgreSQL. Se añade regresión estática ejecutable sin Odoo.
- Referencia: documentación oficial Odoo 19 ORM, campo `Selection` (lista, callable o nombre de método): https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html
- Pendiente de validación ORM en instancia Odoo 19 + PostgreSQL; la prueba estática y chequeos locales sí se ejecutan en esta copia.
- Versión anterior: `19.0.4.14`; punto de retorno: `fiber_gis_19.0.4.14.zip`.

## Iteración 19.0.4.16 — relaciones de splitter Casete

- Se solicitan dos nuevas opciones en **Gestión de bandejas > Instalar splitter > Relación splitter**: `1:4 Casete` y `1:8 Casete`.
- Se centralizan las relaciones para que el asistente, el modelo `fiber.gis.splitter`, la línea de bandeja y el asistente de conexión de otra salida reconozcan los mismos valores.
- `splitter_output_count()` lee el número antes del texto «Casete», generando 4 u 8 salidas. La pérdida nominal propuesta reutiliza la referencia de `1:4` (7,1 dB) y `1:8` (10,4 dB); el asistente mantiene el campo editable si la ficha del fabricante indica otro valor.
- Pruebas estáticas locales: 58. Se añade TransactionCase que crea ambos splitters desde el asistente y comprueba opciones, salidas y pérdida; requiere Odoo 19 + PostgreSQL, no disponible en este entorno.
- Versión anterior: `19.0.4.15`; punto de retorno: `fiber_gis_19.0.4.15.zip`.


## Iteración 19.0.4.17 — continuidad de bandejas y cables de paso

- Estado: versión anterior `19.0.4.17`; siguiente revisión `19.0.4.18`; Odoo objetivo exclusivamente Odoo 19 Community.
- En Sangría se selecciona un cable entrante (llega desde otra caja) y uno saliente (parte hacia la caja destino). Los selectores se filtran por sentido y el nombre muestra «Cable que viene de [caja]» o «Cable que va a [caja destino]», con boca e identificador/nombre disponibles.
- Para paso por una caja se requieren dos tramos de cable en GIS con esa caja como destino del primero y origen del segundo. Si un único trazado cruza una caja intermedia, dividirlo en esos dos tramos y conservar bocas/geometrías; no se detectan nodos intermedios automáticamente.
- Las fibras no marcadas se emparejan por número y quedan vinculadas entrada-salida en la misma bandeja. Las fibras entrantes marcadas como cortadas quedan en punta; se permite después asignarles fusión/splitter/acometida con el aviso de reemplazo. Un registro pass nuevo debe tener ambos extremos; los registros históricos incompletos se conservan legibles y no se convierten sin migración.
- Al abrir una línea de paso desde el esquema, se abre la bandeja completa para editarla sin convertir accidentalmente la continuidad en una fibra en punta.
- Cada operación exige bandeja. Si la acometida parte de un splitter, se exige la bandeja de ese splitter. Una bandeja puede combinar diferentes tipos de trabajo en fibras separadas.
- Se actualizaron el trazado, la vista visual, validaciones ORM y README. Se añadieron pruebas ORM; instalación y `TransactionCase` requieren Odoo 19 + PostgreSQL y están pendientes aquí. Las pruebas CSS siguen sujetas a la compilación real del bundle Odoo 19 si se modifican estilos; esta iteración no cambió SCSS.
- No hay migración de base necesaria: se reutiliza `tray.line.output_fiber_id`; los campos de selección nuevos son del asistente transitorio. Las líneas antiguas de Sangría sin salida se conservan y muestran que no tienen continuidad registrada.
- Referencias oficiales 19.0: ORM https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html ; restricciones https://www.odoo.com/documentation/19.0/developer/tutorials/backend.html
- Punto de retorno: `fiber_gis_19.0.4.16.zip`.


## Iteración 19.0.4.18 — cable saliente compatible por defecto

- Incidencia observada en captura: dos fibras estaban registradas como Sangría y el resto como punta. La explicación probable es que el tramo saliente elegido solo tenía dos fibras disponibles; la continuidad se empareja por número.
- Al iniciar Sangría, se propone un cable saliente ya registrado en la caja solo si coincide la cantidad de fibras, tubos y fibras por tubo con el cable entrante. Se generan las fibras del cable antes de emparejarlas. Si no hay coincidencia, se deja vacío para impedir seleccionar un destino incorrecto por defecto.
- La selección inicial del cable al abrir Gestión de bandejas prioriza un cable entrante. Al cambiar el cable entrante se recalcula la propuesta; al cambiar la caja también.
- Los registros ya guardados no se cambian. Para corregir una operación histórica, repetirla con los cables correctos y confirmar el reemplazo que presente el asistente.
- Prueba ORM añadida para selección compatible y generación de fibras. Requiere Odoo 19 Community + PostgreSQL; no disponible en este entorno. Sin cambios de CSS/SCSS.
- Versión anterior: `19.0.4.17`; punto de retorno: `fiber_gis_19.0.4.17.zip`.


## Iteración 19.0.4.19 — bandejas sin límite de trabajos

- Captura de error recibida: `La bandeja Bandeja 1 no tiene posiciones libres suficientes. Libres: 30, necesarias: 43.` Se quita la comprobación de capacidad al registrar trabajos y al moverlos.
- Las bandejas aceptan cualquier número de fusiones, sangrías y splitters. El número de trabajos se muestra sin denominador/capacidad. El campo antiguo `capacity` queda preservado en el modelo por compatibilidad, pero no se usa para bloquear operaciones ni se presenta en las vistas.
- Se añade `TransactionCase` para registrar 43 fibras en una sola bandeja. Odoo 19 Community + PostgreSQL no disponible aquí; estática, sintaxis, XML y ZIP deben pasar localmente. Sin cambios CSS/SCSS.
- Versión anterior: `19.0.4.18`; punto de retorno: `fiber_gis_19.0.4.18.zip`.


## Iteración 19.0.4.20 — corregir duplicación del menú de importación

- La captura muestra repetida la opción **Importar cartas de empalme (ZIP)**. Causa localizada: `data/fiber_gis_cleanup.xml` borraba cada vez el XML ID con `name ilike 'splice'`, pero no eliminaba el registro del menú. En cada actualización se creaba un menú nuevo.
- Se quita esa eliminación amplia de `ir.model.data` para conservar los XML IDs estables. Se añade una migración que encuentra el menú canónico por su XML ID y elimina únicamente menús hermanos con el mismo nombre.
- La actualización a 19.0.4.20 ejecuta la migración y limpia duplicados existentes. Las cartas, cables y demás datos permanecen intactos.
- Prueba estática nueva: protege el XML ID y valida la exclusión del menú canónico en la migración. Odoo 19 + PostgreSQL para validar ejecución ORM; no hay estilos modificados.
- Versión anterior y punto de retorno: `19.0.4.19`.

## Iteración 19.0.4.21 — trazado encadenado y etiquetas de bandeja

- En el selector de bocas del mapa se añade **Crear y seguir trazando**. Al guardarlo, el destino pasa a ser el origen del siguiente cable y el cable recién creado se conserva como tramo anterior.
- Al guardar el siguiente segmento, el servidor comprueba que el tramo anterior termina en la caja de origen y registra continuidad de fibras con igual numeración como Sangría en la primera bandeja. Los pares ocupados no se sobrescriben; fibras/tubos incompatibles o falta de bandeja devuelven un aviso para completar la gestión manualmente.
- El asistente de bandejas muestra ahora los campos **Cable entrada** y **Cable salida**.
- Se añade prueba ORM de sangría automática por fibra y prueba estática del flujo de continuación. No se modificó CSS/SCSS.
- Referencias oficiales Odoo 19 para ORM y seguridad de escritura: https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html.
- Versión anterior y punto de retorno: `19.0.4.20`.

## Iteración 19.0.4.22 — tipología de cable al finalizar

- Se elimina el selector de tipología del panel inicial para que no interrumpa el trazado. **Crear y seguir trazando** guarda cada tramo con una tipología provisional y continúa desde la caja de destino.
- Al pulsar **Crear cable** o **Finalizar trazado**, se solicita la tipología definitiva. El método ORM valida el orden y continuidad de los cables, comprueba que sus fibras no tengan usos y actualiza perfil, tubos y fibras para toda la cadena.
- Tras regenerar las fibras, se registran las sangrías consecutivas en la primera bandeja de cada nodo intermedio. Si hay usos previos, el servidor rechaza el cambio de tipología para evitar alterar conexiones existentes.
- Se añadió prueba ORM para pasar de una tipología provisional de 2 fibras a una final de 2 tubos x 4 fibras y comprobar ocho líneas de sangría. Pruebas ORM y revisión visual requieren Odoo 19 Community + PostgreSQL y quedan pendientes.
- No se modificó CSS/SCSS; el panel conserva su estructura de columnas y muestra una indicación de que la tipología se elige al final.
- Versión anterior y punto de retorno: `19.0.4.21`.

## Iteración 19.0.4.23 — presentación y orden de bandejas

- La ficha de la caja ya no muestra el número interno de posición al inicio de cada fila de bandeja.
- La lista visual ordena splitter, fusión, fibra en punta (incluidas las pendientes de anular) y sangría; se conserva el orden de posición dentro de cada tipo. No se modifican los registros ni sus asignaciones.
- Sin cambios CSS/SCSS ni migración. Se añadió una comprobación estática; validar ORM y representación en Odoo 19 Community + PostgreSQL.
- Punto de retorno: `19.0.4.22`.

## Iteración 19.0.4.24 — información de cable y fibras en splitters

- El selector del cable en el asistente contextual de salida pasa `fiber_gis_node_id` y `fiber_gis_show_boca`; ahora debe mostrar “Cable que va a/de [elemento] · Boca N · identificador”.
- Al elegir cable, el panel informa todas sus fibras con número, tubo, color y conexiones de los extremos de origen y destino. Lee resúmenes de bandeja, splitter y puerto; las conexiones de salida vinculadas a acometidas figuran como salida del splitter en el extremo del elemento.
- Añadida prueba ORM para etiqueta direccional y listado completo. No CSS/SCSS ni migración. Pendiente ejecutar TransactionCase y verificar el formulario en Odoo 19 Community + PostgreSQL.
- Punto de retorno: `19.0.4.23`.

## Iteración 19.0.4.25 — vista visual de fibras del splitter

- El listado de fibras del cable reutiliza el fragmento visual ya utilizado en el diagrama de splitter: círculos de color para tubo/fibra, nombre del cable y extremo remoto.
- Conserva los resúmenes de conexión de origen y destino al lado de cada fibra. No se añaden estilos nuevos; se reaprovecha el SCSS actual de Odoo 19 del módulo.
- Actualizar la prueba ORM y estática. Pendiente ejecutar ORM y revisar el diálogo en Odoo 19 Community + PostgreSQL.
- Punto de retorno: `19.0.4.24`.

## Iteración 19.0.4.26 — permisos de Configuración y copia de seguridad completa

- `groups="-fiber_gis.group_fiber_gis_manager"` en los menús Configuración y Ajustes quitaba el grupo (Odoo 19 `convert.py`: prefijo `-` = `Command.unlink`) y los dejaba visibles para todos. Corregido a `groups="fiber_gis.group_fiber_gis_manager"`. No volver a usar `-` para restringir.
- Ajustes solo para Responsable: se quita la fila ACL de Usuario del asistente y cada `action_*` llama a `_check_fiber_gis_manager()`.
- La copia incluye todos los modelos persistentes (planes, cartas, cabeceras, equipos, puertos, interconexiones, biblioteca) y los binarios. La restauración usa el contexto `fiber_gis_restore`, comprobado en `create()` de elemento, cable, splitter, salida de splitter y equipo de armario para no regenerar hijos que vienen en la copia. Si se añade un modelo nuevo o un `create()` que genere registros hijos, incluirlo en `_backup_model_names()` y respetar ese contexto.
- `cable_profile.name_get` sustituido por `_compute_display_name` (Odoo 19 no usa `name_get`).
- Verificación: 70 comprobaciones estáticas, `node --check`, compileall y parseo XML. En Odoo 19 Community (rama oficial `19.0`) + PostgreSQL 16 se ejecutaron instalación, actualización desde 19.0.4.25 y `TestBackupRestore` (3/3 en verde). Sin CSS/SCSS ni migración.
- Pendiente: 25 fallos ORM que ya existían en 19.0.4.25 (17 `TestCabinet` por `_check_manager` sin grupo Responsable en el usuario de prueba, 3 `TestSplitterManagement`, 2 `TestMapCable`, 2 `TestCableProfilesAndTechnicians`, 1 geocodificación sin red). No son de esta iteración; revisarlos en la siguiente.
- Punto de retorno: `19.0.4.25`.

## Iteración 19.0.4.27 — fluidez del mapa

- Medido con red sintética de 2.500 elementos y 3.000 cables en Odoo 19 Community + PostgreSQL 16 y Chromium sin GPU (Playwright). El coste del arrastre y el zoom está en el pintado del SVG (raster y paint), no en JavaScript.
- Cambios: una única área de clic por cable, que no se pinta (`visibility: hidden` + `pointer-events: stroke`); tramos visibles de una sola línea; vértices proyectados en caché; coordenadas con una décima; arrastre del mapa también desde un cable, con captura del puntero diferida al primer movimiento para conservar clic y doble clic.
- No reintroducir: agrupar varios tramos en un `<path>` (con zoom alto los guiones de cables largos se disparan) ni mover la transformación de vista previa al `<svg>` con `will-change`/`overflow: visible` (266 ms por fotograma frente a 37 ms).
- Resultado: zoom en la vista general de 5,8 a 4,6 s de bloqueo; arrastre con zoom alto de 5,4 a 2,5 s. Más margen requeriría recortar los tramos al área visible con `stroke-dashoffset`, o dibujar en canvas; no se ha hecho.
- Pendiente: revisión visual en navegador de escritorio con GPU y con la red real.
- Punto de retorno: `19.0.4.26`.

## Iteración 19.0.4.28 — retirada del trazado encadenado

- Petición de usuario: el técnico no podía desplazar el mapa al llegar al borde mientras encadenaba cajas con «Crear y seguir trazando», porque en modo trazado cada pulsación añade una esquina.
- Retirados el botón, el estado `cableDraftChainIds`, `previous_cable_id` de `create_from_map`, `_create_map_default_sangria` y `finalize_map_cable_chain`. Nuevo `finalize_map_cable(cable_id, profile_id)` para elegir la tipología al crear cada cable.
- Las sangrías ya registradas se conservan. Sin migración ni CSS/SCSS.
- Punto de retorno: `19.0.4.27`.

## Iteración 19.0.4.29 — presentación de bandejas, tubo y colores de cable

- Causa del texto amontonado en Bandejas: la rejilla `.o_fiber_tray_line` conservaba la columna de 22 px de la posición retirada en 19.0.4.23 y las líneas sin flecha o salida desplazaban el resto. Rejilla de 6 columnas y casillas siempre presentes en `_tray_line_visual_html`. Si se añade o quita una casilla, ajustar a la vez la rejilla y el HTML (`tests/check_tray_layout.py`).
- `show_tube` (no almacenado) en la fibra y related en línea de bandeja, splitter y salida; vistas con `invisible`/`column_invisible`.
- Colores por número de fibras al crear el cable desde el mapa y al finalizar la tipología.
- Corregido `FiberGisCable.write`: solo llama a `_prepare_profile_values` si cambian `profile_id`, `tube_count` o `fiber_count`. Antes cualquier escritura asignaba la tipología de 0 tubos × 12 fibras. Resuelve 4 fallos ORM previos (quedan 21 de los 25 anotados).
- Punto de retorno: `19.0.4.28`.
