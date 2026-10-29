# Digital GIS para Odoo 19

**Versión de esta revisión:** `19.0.4.29`
**Objetivo:** inventariar, representar y documentar una red de fibra óptica desde Odoo Community.

Esta revisión toma como base funcional `19.0.3.37.31` y continúa la entrega `19.0.3.47`. Incluye las mejoras de bandejas y cartas de empalme descritas en el historial.

## 1. Qué gestiona

- Sitios y elementos de red con coordenadas, dirección, categoría, modelo, tipo de función, fotos y registro de trabajos.
- Cables entre elementos, su trazado, tipología, tubos, fibras, extremos y técnicos.
- Bandejas, fibras en punta o pendientes de anular, sangrías, fusiones y conexiones con splitters o acometidas.
- Fotos, comentarios y cartas Excel de empalme adjuntas a elementos con bandejas, con importación por matrícula.
- Splitters ópticos, sus entradas, salidas, conexiones y pérdidas nominales.
- Diagnóstico de continuidad de una fibra y generación de su informe PDF.
- Planes de despliegue con elementos, cables, estimación de metros, reserva e impresión de un plano PDF.
- Cabeceras de comunicaciones con armarios de altura configurable, editor gráfico por unidades U, biblioteca de equipos y asignación de fibras GIS a puertos de ODF/patch panel.
- Copias de datos propios del módulo desde Ajustes.

El mapa muestra la cartografía disponible y la red registrada. La precisión de un plano depende de las coordenadas y geometría introducidas; la longitud estimada no sustituye una medición de obra.

## 2. Acceso y permisos

El módulo requiere Odoo 19 y las aplicaciones técnicas `base`, `web`, `mail` y `hr`. La dependencia de Recursos Humanos se utiliza para seleccionar empleados como técnicos; no concede acceso a expedientes privados de personal.

En **Ajustes > Usuarios y compañías > Usuarios**, los usuarios internos tienen el perfil **Digital GIS / Usuario**. Pueden consultar y mantener los registros de operación permitidos. El perfil **Digital GIS / Responsable** incluye el de Usuario y permite administrar los catálogos y Ajustes.

La sección **Configuración** está reservada a responsables. Si un técnico no ve un menú o botón, primero hay que comprobar su grupo y los permisos de acceso al modelo.

La sección **Cabecera** también está reservada al perfil Responsable. Crea un armario indicando su altura (1–60 U) y vincúlalo a un elemento GIS para elegir las fibras que llegan o salen de ese nodo. Abre el diseñador para arrastrar equipos desde la biblioteca y colocarlos en unidades libres. El rack bloquea posiciones solapadas; cada fibra solo puede asignarse una vez en las cabeceras.

El diseñador permite ampliar o reducir la vista del rack entre el 60 % y el 140 %. Desde el icono de lápiz de cada entrada de Biblioteca, un responsable abre una ventana independiente y amplia para editar el nombre de plantilla, la altura, el número de bocas y la imagen frontal. En la previsualización grande, arrastra cada número hasta la toma correspondiente. La imagen y distribución de bocas se guardan como configuración compartida del tipo de equipo y se reflejan en equipos ya colocados. El número de bocas también se aplica a los equipos existentes, siempre que no se reduzcan bocas con cables o fibras conectados. El nombre de plantilla y la altura elegida se usan al añadir equipos nuevos; los nombres y alturas de equipos ya colocados se mantienen. En una misma cabecera puedes añadir varios racks con **Añadir rack**; se muestran uno al lado del otro y la zona se desplaza horizontalmente. Pulsa el selector de un rack para dirigir allí los elementos que añadas desde la biblioteca. También puedes arrastrar equipos de un rack a otro; se mantienen sus puertos y asignaciones de fibras.

Selecciona un equipo para cambiar su **Nombre del equipo** desde el panel derecho y pulsa **Guardar nombre**. En **Interconexiones**, selecciona el equipo de destino, indica el puerto de cada extremo, el tipo de cable y, si lo necesitas, una identificación. La conexión queda guardada entre esos equipos y aparece en su lista; se puede eliminar desde esa lista. Esta función registra el cableado interno entre patch panels, ODF, switches, routers y otros equipos con puertos. Para retirar un equipo, arrástralo a la zona de la izquierda del rack. Si tiene fibras o interconexiones, Odoo pide confirmación antes de eliminarlas. También puedes conectar desde el dibujo: pulsa una boca libre del frontal y luego la boca libre de otro equipo. El sistema resalta la primera selección y registra la interconexión entre los dos números de boca; las conexiones existentes se marcan y no se pueden reutilizar hasta quitar la interconexión. Cada conexión se dibuja con una línea de color resaltada y flecha desde la boca de origen a destino: por el lateral más cercano si los equipos comparten rack y por encima de los racks si une armarios distintos. El formulario manual sigue disponible.

Los frontales de equipos de la biblioteca son recortes de la lámina de elementos de rack de ConceptDraw, incluidos localmente para funcionar sin conexión.

El catálogo añade servidor de 1U y 3U, cabina RAID de 2U y 3U, conmutador KVM 1U, monitor rack de 7U y 8U, SAI gestionable 2U y regleta de alimentación 1U. Los elementos anteriores de 19 pulgadas conservan su configuración; se muestran con un frontal de switch, servidor, RAID, SAI o patch panel de la misma lámina.

Fuente de imágenes: [ConceptDraw — Rack Diagrams, lámina «Design Elements»](https://www.conceptdraw.com/solution-park/computer-networks-rack-diagrams). Los recortes se conservan sin redibujar y se atribuyen a ConceptDraw/CS Odessa en `static/src/img/ATTRIBUTION.txt`; su inclusión en este módulo se realiza con la autorización indicada por la usuaria.

El catálogo incluye el **Panel FHU 1U 48F SC/UPC** (SKU FS.com 35529), con 24 adaptadores dúplex y 24 puertos asignables. Su vista frontal usa la fotografía de producto de la [galería oficial FS.com](https://www.fs.com/es/products/35529.html?now_cid=1050), incluida con la autorización escrita confirmada por la usuaria. La ficha identifica el producto como 1U, 48 fibras y 24 adaptadores SC/UPC dúplex. La imagen está empaquetada localmente y atribuida en `static/src/img/ATTRIBUTION.txt`.

## 3. Preparación inicial

Antes de inventariar la red, un responsable debe revisar los catálogos de **Digital GIS > Configuración**:

1. **Modelos de elemento:** nombre del modelo, categoría, icono, color, bocas de cable y si los elementos de ese modelo tienen bandejas por defecto. El modelo **Arqueta** se llama así y propone un cuadrado negro en el mapa; puedes cambiar icono y color en la ficha. Las arquetas ya existentes conservan sus valores. CTO, CTO interna, Caja terminal y Caja de registro se configuran con bandejas; cada ficha permite ajustar su caso particular. La CTO general tiene 4 bocas; «CTO interna» tiene 2. El modelo describe la familia del equipo; el tipo de función concreta el uso del elemento.
2. **Tipos GIS:** opciones de clasificación que aparecen en la ficha y en los filtros.
3. **Tipologías de cable:** nombre, Tipo GIS, número de tubos y fibras. Sin tubos, el valor de fibras es el total del cable. Con tubos, es el número de fibras por tubo; el total se calcula como tubos por fibras por tubo. Ejemplo: 4 tubos x 6 fibras = 24 fibras.
4. **Tipos de arqueta:** comprobar nombre y medidas interiores. Se pueden ajustar a los criterios de la red local.
5. **Ajustes:** configurar el umbral de zoom para mostrar iconos y nombres completos; revisar el servicio de geocodificación y el correo de contacto requerido por el proveedor.

Los catálogos iniciales son editables. Comprueba que las tipologías necesarias existen antes de dar de alta cables.

## 4. Inventariar el mapa

1. Abre **Digital GIS > Mapa**.
2. Usa los filtros para mostrar sitios, elementos o cables y limitar el estado visible.
3. Busca un elemento por su nombre o matrícula. Para una dirección, introduce la calle y la población para acotar el resultado.
4. Pulsa **Elemento** para crear un equipo. Indica nombre, matrícula, modelo, tipo de función, coordenadas y dirección. Si la geocodificación devuelve una dirección larga, corrígela en la ficha para guardar la forma corta usada por el equipo.
5. Coloca el elemento en su ubicación real y confirma las coordenadas antes de guardar. El mapa permite abrir la ficha del elemento desde su marcador.
6. Completa en la ficha los datos técnicos, fotos, puertos, bandejas, fabricante, observaciones y trabajos que correspondan.

Los iconos y colores predeterminados se toman del modelo/categoría, pero se pueden ajustar en el propio elemento cuando el perfil lo permite.

Para desplazar el mapa, arrastra desde el fondo o desde un cable; un clic sin mover sigue seleccionando el cable y el doble clic abre su ficha. Arrastrar un elemento o sitio lo mueve, y arrastrar un vértice del cable seleccionado cambia su trazado.

Si mueves un sitio, elemento o cable, puedes usar **Deshacer** y **Rehacer** en el mapa. Se conserva un historial de hasta 30 cambios recientes durante la sesión; no es un sustituto de la copia de seguridad.

## 5. Crear y dibujar un cable

### Desde una ficha

1. Abre el elemento de origen y selecciona **Cables** o inicia el asistente de trazado desde el mapa.
2. Elige el elemento de origen y el de destino. Los extremos de un cable son elementos de red, no otros cables.
3. Al pulsar el destino, elige la boca de cada elemento. El mapa consulta las bocas disponibles aunque el cable existente quede fuera del plan visible.
4. Pulsa **Crear cable** y selecciona la tipología. El cable recibe un color según su número de fibras: 6 FO celeste, 12 FO rojo, 16 FO violeta, 24 FO marrón, 48 FO verde, 72 FO verde oscuro, 80 FO azul, 96 FO rosa, 128 FO naranja y 288 FO negro; otras cantidades usan el color por defecto. Puedes cambiarlo en la ficha del cable. Al elegir la tipología se actualizan el número de tubos y las fibras por tubo o el total, y se regeneran las fibras con la codificación de colores establecida. Si las fibras ya se han usado, elige **Dejar tipología actual** para conservar esos datos. El trazado termina con cada cable: desplaza o amplía el mapa si lo necesitas y empieza el siguiente cable desde su caja de origen.
5. Dibuja el recorrido en el mapa cuando se conozca. Revisa el tipo de instalación y la geometría antes de guardar.
6. En la ficha del cable completa el nombre manual, la fecha, la longitud medida si ya se conoce y los técnicos que lo instalaron.
7. Revisa las pestañas **Tramos**, **Fibras**, **Geometría** y **Notas**. La ficha de fibras separa la información de los dos extremos cuando está registrada.

La longitud estimada procede de la geometría y puede diferir de la longitud real de tendido. Registra la medida real en su campo cuando se haga la instalación.

### Desde la ficha de un elemento

En la pestaña **Cables**, revisa cables de entrada y salida. La columna que indica el número de boca se llama únicamente **Boca**, sin añadir «de entrada» o «de salida»; la dirección se reconoce por la sección y los extremos del cable. Un cable puede tener un nombre manual: el sistema no debe reconstruirlo usando los nombres de los elementos.

## 6. Bandejas y empalmes

En la ficha del elemento, activa **Tiene bandejas** e indica su número. La pestaña **Bandejas** presenta las bandejas y las operaciones ya registradas. Pulsa **Asistente Bandejas** para registrar una operación sobre uno o varios cables.

1. Elige la **Operación** y el cable. Para una fusión, selecciona también el segundo cable.
2. Selecciona la bandeja de destino. Si la operación afecta al segundo cable, se puede indicar su bandeja.
3. Marca las fibras concretas en cada cable. Una fusión une una fibra de un cable con una fibra del otro; no fusiona el cable entero.
4. Revisa el color del tubo, el número de tubo cuando exista, el color/número de fibra, el estado actual y los extremos conocidos.
5. Selecciona el técnico responsable y registra la operación. Si se selecciona una fibra ocupada, el sistema muestra una confirmación antes de reemplazar su asignación.

Operaciones disponibles en el asistente:

- **Fibra en punta:** deja fibras cortadas sin continuidad en una bandeja. No consume una posición de fusión.
- **Fibra pendiente de anular:** deja una marca visual roja y destacada para fibras que se retirarán o anularán. No consume una posición de fusión y sigue visible en el esquema y los selectores.
- **Fusionar con otro cable:** enlaza una fibra elegida de cada cable. Las bandejas no tienen límite de trabajos; las fibras en punta y las pendientes de anular se contabilizan aparte.
- **Sangría / cable de paso:** selecciona **Cable entrada** y **Cable salida**. Los selectores muestran la caja vecina y el identificador o nombre del cable; si la caja no tiene nombre, muestran su matrícula o su ID. Las fibras no marcadas se enlazan por su mismo número entre ambos tramos y continúan. Marca las fibras cortadas para dejarlas en punta en la bandeja; después puedes aplicarles otra operación, como una fusión o un splitter, confirmando el reemplazo de su estado anterior.
- **Instalar splitter:** registra un splitter en la bandeja. En **Relación splitter** están disponibles, además de las relaciones habituales, **1:4 Casete** y **1:8 Casete**. Al instalarlos se crean cuatro u ocho salidas y se propone la pérdida nominal de referencia de su relación; puedes ajustarla según la ficha técnica del equipo. Las conexiones a una salida se gestionan desde la ficha del splitter.
- **Acometida final de cliente:** vincula la salida a un cliente y registra el cable de acometida cuando se proporcionan los datos requeridos.

Cada operación requiere seleccionar la bandeja donde se hará el trabajo. Una misma bandeja puede contener continuidad de paso, fibras en punta, fusiones y splitters en fibras distintas. Si se cambia el tratamiento de una fibra que ya tiene un registro, Odoo muestra una confirmación antes de reemplazarlo. Cuando una acometida parte de un splitter, se selecciona la misma bandeja donde está instalado ese splitter. Al abrir una línea de paso en el esquema, se abre la bandeja para editarla sin convertir por accidente la continuidad en una fibra en punta.

Para registrar un cable que atraviesa una caja, dibuja un cable hasta esa caja y otro desde ella, y registra la continuidad con **Sangría / cable de paso** en el **Asistente Bandejas** de la caja. El mapa no infiere cajas intermedias a partir de la geometría de un único cable dibujado de extremo a extremo.

La ficha del splitter permite revisar sus entradas y salidas. Al gestionar una salida con una fusión, el selector del cable identifica la caja del otro extremo y la boca correspondiente. Al elegirlo aparece el listado completo de fibras con los colores de tubo y fibra en círculos, el cable, el extremo remoto y el resumen de conexiones en origen y destino; así puedes comprobar si están libres, en punta, fusionadas, en paso o vinculadas a una salida de splitter/acometida antes de escoger una. Confirma que la relación y el técnico sean correctos antes de guardar.

### Cartas de empalme

En elementos con **Tiene bandejas** activado aparece la pestaña **Cartas de Empalme**. La sección **Cartas Excel** aparece primero e incluye el comentario del técnico para anotar cambios hechos a la hoja; debajo está **Fotos**, donde se suben imágenes y comentarios. Cada registro conserva el técnico asociado y la fecha de carga.

Para adjuntar una hoja a un equipo, pulsa **Subir carta Excel** y elige el archivo; el formulario ya queda asociado al elemento. Para importar una carpeta completa, conserva su estructura de subdirectorios al comprimirla en un ZIP y usa **Digital GIS > Configuración > Importar cartas de empalme (ZIP)**. Se aceptan `.xls`, `.xlsx`, `.xlsm`, `.xlsb` y `.ods`. El importador busca la matrícula completa en el nombre base de cada hoja de cálculo (por ejemplo, `Carta CTO-123.ods` se asigna al elemento `CTO-123`, no a `CTO-12`); conserva la ruta interna como comentario. Se admiten hasta 5.000 entradas ZIP, con un máximo de 50 MB comprimidos, 20 MB por archivo y 200 MB descomprimidos en total. Los duplicados se omiten y el resultado ofrece un TXT descargable con los nombres y motivos de todos los archivos no importados. El ZIP se procesa en memoria en Odoo; el servidor no puede leer directamente una carpeta del disco local del técnico.

Para cambiar una operación existente, usa las acciones disponibles en su línea de bandeja. Al mover una línea, el sistema reordena ambas bandejas por tubo y número lógico de fibra. La papelera elimina la línea seleccionada y solicita confirmación; comprueba antes que no estés borrando la única referencia del empalme.

### Historial técnico

Las fichas de elementos de red, sitios, cables y splitters incluyen la pestaña **Técnico**. Añade una línea por trabajo e indica día y hora, técnico, tipo de trabajo y descripción. Para guardar una línea manual hay que indicar técnico y descripción. La fecha se propone automáticamente; el técnico se propone si Odoo puede asociar de forma inequívoca el usuario conectado con un empleado. Ambos datos se pueden revisar antes de guardar.

El historial de elementos de red conserva además sus registros automáticos de creación, modificación y operaciones de bandeja. En las otras fichas, la pestaña sirve para registrar los trabajos realizados por el equipo; no genera una entrada genérica en cada cambio de campo.

## 7. Diagnosticar una fibra

1. Abre el asistente de trazado desde el elemento o la fibra que quieres comprobar.
2. Selecciona el cable y la fibra de interés.
3. Ejecuta el trazado. El resultado enumera los elementos, cables, bandejas y conexiones que constan en la red.
4. Revisa los puntos donde el recorrido se interrumpe o los datos son incompletos.
5. Usa **Imprimir PDF** para generar el informe del recorrido.

El informe representa los datos almacenados en Odoo: una fusión inexistente, un extremo sin conectar o una coordenada incorrecta se reflejarán como tal. No interpreta conexiones que no se hayan registrado.

## 8. Preparar un despliegue y su plano

1. En **Digital GIS > Operación > Planes de despliegue**, crea un plan con nombre, zona, responsable, técnicos previstos, fechas y porcentaje de reserva.
2. Añade los elementos existentes que formarán parte del trabajo y crea o asocia sus cables planificados.
3. Completa coordenadas y recorridos de cable. Anota permisos, accesos, riesgos y trabajos previstos en **Alcance y observaciones**.
4. Comprueba los contadores de elementos, cables, metros dibujados, metros con reserva, elementos sin coordenadas y cables sin trazado detallado.
5. Abre el plano de trabajo para revisar posiciones y recorridos. Corrige los datos de origen si falta algo.
6. Usa **Imprimir PDF** para entregar el plano y la estimación. Tramita el plan con los botones de revisión, aprobación, inicio y finalización.

Los metros con reserva se calculan a partir de los recorridos dibujados y el porcentaje configurado. Si faltan coordenadas o geometría, la estimación será parcial; revisa los avisos antes de imprimir.

## 9. Copias de seguridad

En **Digital GIS > Configuración > Ajustes**, utiliza **Crear copia de seguridad** y descarga el ZIP generado. Para recuperar esos datos, selecciona el archivo en **Restaurar copia** y ejecuta la restauración. Ambas acciones están reservadas al perfil Responsable.

La copia incluye sitios, elementos, fotos, cartas de empalme (Excel y fotos), puertos, cables con sus tramos y fibras, enlaces lógicos, bandejas y sus operaciones, splitters y salidas, planes de despliegue, cabeceras con racks, equipos, puertos e interconexiones, la biblioteca de equipos, el historial técnico y los catálogos. La restauración sustituye esos datos por los de la copia y vuelve a enlazar todas sus relaciones; no genera bandejas, fibras, salidas ni puertos adicionales. Si algo falla, Odoo deshace la restauración completa y los datos actuales quedan intactos.

Las copias creadas antes de la versión `19.0.4.26` no contienen cartas de empalme, cabeceras ni planes de despliegue. Para no borrar esos datos, Odoo rechaza restaurar una copia antigua si existen cartas de empalme, fibras asignadas en cabeceras o planes de despliegue; crea una copia nueva antes de restaurar. Las fotos de las copias antiguas se recuperan.

Esta copia del módulo no sustituye una copia completa de la base PostgreSQL ni del filestore de Odoo. Para un plan de recuperación completo, el administrador debe respaldar ambos con las herramientas de infraestructura y probar periódicamente la restauración en una base separada.

Antes de actualizar el módulo, realiza como mínimo una copia completa de la base y del filestore. No desinstales el módulo para actualizarlo: usa la actualización de aplicaciones de Odoo para conservar los registros.

## 10. Instalación y actualización

1. Copia la carpeta `fiber_gis` dentro de una ruta de addons incluida en `addons_path`.
2. Confirma que el usuario del servicio Odoo puede leer sus archivos y que están presentes las dependencias de Odoo 19.
3. Reinicia Odoo para que detecte código Python nuevo.
4. En **Aplicaciones**, actualiza la lista de aplicaciones, busca **Digital GIS** e instala el módulo. Para actualizar una instalación existente, pulsa **Actualizar**; no lo desinstales.
5. Comprueba los registros de Odoo durante la carga y abre el mapa, una ficha, el asistente de bandejas y un informe.

En instalaciones administradas por consola, el administrador puede actualizar con el procedimiento normal de Odoo 19 para la base seleccionada, por ejemplo `odoo-bin -d NOMBRE_BASE -u fiber_gis --stop-after-init`, ajustando ruta, usuario y configuración al servicio real.

## 11. Resolución de problemas

| Síntoma | Comprobaciones |
|---|---|
| No aparece Digital GIS | Actualiza la lista de aplicaciones, comprueba `addons_path`, permisos de archivos y registros del servidor. |
| Un usuario no ve Configuración | Asigna el grupo **Digital GIS / Responsable** y vuelve a iniciar sesión. |
| No aparece una tipología de cable | Comprueba que esté activa y que el usuario tenga permiso de lectura. |
| El total de fibras no coincide | Sin tubos, fibras es el total; con tubos, fibras es la cantidad por tubo. Total = tubos x fibras por tubo. |
| Un plano sale sin cartografía | Verifica acceso HTTPS saliente al servicio WMS del Catastro; los datos vectoriales y las medidas pueden seguir disponibles. |
| Un PDF no muestra el recorrido esperado | Revisa coordenadas, extremos del cable, geometría, bandejas y conexiones de cada extremo. |
| El mapa no encuentra una dirección | Comprueba población, acentos y servicio de geocodificación configurado. Confirma la ubicación manualmente antes de guardar. |
| Error al actualizar | Lee el primer error Python/XML del registro, no solo el RPC del navegador. Corrige la causa y vuelve a actualizar conservando la base. |

## 12. Pruebas y mantenimiento técnico

Las pruebas aisladas incluidas en `tests/check_*.py` y `tests/check_*.cjs` cubren flujos concretos sin desplegar una instancia completa de Odoo. Las pruebas ORM `test_*.py` requieren Odoo 19 y PostgreSQL; deben ejecutarse en una base de pruebas antes de instalar una nueva compilación en producción.

La revisión estática no sustituye una prueba funcional con los permisos, datos, cartografía y configuración de la instalación real.

### Comprobaciones recomendadas

- Pruebas Python aisladas: `python -m unittest discover -s tests -p "check_*.py"`. Requieren las dependencias usadas por las pruebas, entre ellas `lxml`.
- Sintaxis JavaScript: `node --check static/src/js/fiber_map.js` y repetir para los demás JavaScript modificados.
- Interacción visual de bandejas: `node tests/check_tray_browser.cjs`; requiere Playwright y el navegador configurado para esa prueba.
- Pruebas ORM y carga del módulo: en una base desechable de Odoo 19, actualizar con `odoo-bin -d BASE_PRUEBAS -u fiber_gis --test-enable --stop-after-init --test-tags /fiber_gis` y revisar el registro completo.
- Regresión manual: abrir mapa, ficha de elemento, ficha de cable, asistente de bandejas, splitter y los dos informes; verificar también un usuario técnico sin permisos de configuración.
- Paquete reproducible: desde la carpeta raíz del módulo, ejecutar `python scripts/build_release_zip.py --output-dir dist`. El script toma la versión del manifiesto, conserva `fiber_gis/` como carpeta raíz del ZIP y excluye cachés, archivos compilados y ZIP previos.

No se debe declarar una prueba superada si no se ejecutó en un entorno que tenga sus dependencias. Las pruebas de navegador, Odoo y PostgreSQL no se sustituyen con una comprobación de sintaxis.

### Compatibilidad de CSS/SCSS con Odoo 19

- El único objetivo de compatibilidad de este módulo es **Odoo 19 Community**. Antes de cambiar APIs, sintaxis o carga de assets, consultar la documentación oficial y, cuando haga falta, el código fuente de la rama 19.0. No copiar soluciones de otras versiones sin verificar que existan y funcionen en Odoo 19.
- Las hojas SCSS pasan por el compilador de assets de Odoo. Mantener la sintaxis conservadora y no introducir funciones CSS que Sass pueda intentar evaluar con valores incompatibles. En particular, no reintroducir `min()` con unidades mezcladas (`px`, `vw`, `vh`) ni `aspect-ratio` en `static/src/scss/fiber_map.scss` sin probarlo primero con el compilador del Odoo 19 objetivo.
- Puerta obligatoria antes de dar por corregido un problema de estilos: actualizar los assets en una instancia de **Odoo 19 Community**, comprobar que compila el bundle y revisar visualmente el modal/rack afectado. Un balance de llaves, una prueba estática o la sintaxis XML no equivalen a compilar SCSS.
- Si no se dispone de una instancia Odoo 19, conservar una solución SCSS sencilla, ejecutar las comprobaciones locales disponibles y dejar anotado que la compilación real y la revisión visual siguen pendientes; no afirmar que CSS quedó validado.
- La regresión de la ventana de edición de 19.0.4.13 se debió al uso de `min()` con unidades CSS distintas y quedó corregida conservadoramente en 19.0.4.14. Mantener la prueba que evita reintroducir `min()`/`aspect-ratio` en esa hoja y ampliar la cobertura si se añaden nuevos estilos sensibles al compilador.

## 13. Estructura para desarrollo

| Ruta | Responsabilidad |
|---|---|
| `models/` | Modelos ORM, reglas de negocio, asistentes y servicios de mapa. |
| `views/` | Vistas, acciones, menús y formularios de Odoo. |
| `security/` | Grupos y permisos de acceso a modelos. |
| `data/` | Catálogos y datos iniciales actualizables. |
| `static/src/js/fiber_map.js` | Componente OWL principal del mapa, interacción, filtros, búsqueda y carga de datos. |
| `static/src/xml/fiber_map.xml` | Plantilla del mapa y controles de interacción. |
| `static/src/scss/fiber_map.scss` | Estilos del mapa, elementos de red y asistentes asociados. |
| `reports/` | Plantillas de impresión PDF. |
| `migrations/` | Cambios de datos asociados a versiones; deben ser idempotentes y probados sobre una copia. |
| `tests/` | Pruebas aisladas y pruebas integradas que requieren Odoo. |

### Reglas para mantener el mapa

- La carga inicial de sitios, elementos, cables, catálogos y configuración se realiza en paralelo. Los registros se indexan por ID para resolver selecciones y relaciones sin recorrer listas repetidamente.
- Los cables fuera de la zona visible se filtran por su extensión geográfica. Sus puntos y extensión se almacenan en caché; la clave depende de los extremos y de la geometría para invalidar el dato al cambiar cualquiera de ellos.
- El desplazamiento y el zoom deben conservar el flujo de interacción actual. La cartografía catastral WMS se solicita aparte y se actualiza con espera para no pedir una imagen por cada evento del ratón.
- La ficha del cable debe conservar separados `type_id` (Tipología del GIS) y `profile_id` (Tipología del cable). Esta última procede del catálogo de configuración y se muestra debajo de la primera; no se debe sustituir una relación por un cambio de etiqueta.
- Los extremos de un cable son elementos de red, no cables. El nombre del cable es manual; no reconstruirlo al cambiar origen o destino.
- Esta entrega no incluye una capa vectorial propia ni un trazado automático que siga fachadas. No confundir la imagen catastral WMS ni la geometría dibujada con esa futura funcionalidad.

La carga actual obtiene los registros del mapa en cada apertura y realiza el filtrado espacial en el navegador. Si el volumen de producción causa lentitud, medir primero tiempos y cantidad de registros; una consulta espacial del lado servidor requiere diseñar paginación/recarga por viewport y comprobar que no oculte cables que cruzan el límite visible.

## 14. Referencia de entrega y continuidad

- Versión de referencia: `19.0.4.29`, declarada en `__manifest__.py`. El identificador del agente de geocodificación debe mantenerse sincronizado con esa versión.
- Estado: candidata `19.0.4.29`, probada en Odoo 19 Community + PostgreSQL 16; falta la revisión visual en un navegador de escritorio.
- Paquete de esta entrega: `fiber_gis_19.0.4.29.zip`. Punto de retorno: `fiber_gis_19.0.4.28.zip`.
- Al retomar: comprobar primero la versión del manifiesto y el contenido instalado; conservar las modificaciones locales existentes, crear un nuevo punto de retorno, modificar solo lo solicitado y actualizar este README junto con las referencias de versión.
- Si una versión futura cambia el esquema, añadir una migración bajo `migrations/<version>/`, probarla sobre una copia reciente y documentar el procedimiento de actualización y retorno. No editar directamente la base real para suplir una migración ausente.
- Crear el ZIP desde una única copia validada del módulo; incluir la carpeta superior `fiber_gis/` y no mezclar archivos de otra revisión. Ejecutar las pruebas disponibles, documentar las que no se pudieron ejecutar y conservar el paquete anterior.

## Historial de esta entrega

- Base funcional tomada de `19.0.3.37.31`; paquete identificado como `19.0.3.40`.
- La ficha del cable muestra la tipología seleccionada en Configuración, inmediatamente debajo de «Tipología del GIS», en un campo independiente.
- Se documentan los procedimientos Python de modelos, hooks y migraciones en español.
- Se centraliza la proyección cartográfica, la petición WMS y la acción de Google Maps usadas en varias fichas e informes.
- Se corrige el recorrido de cascadas de splitters para detenerlo en una entrada de fibra raíz y detectar ciclos sin acceder a relaciones vacías.
- Se optimizan las búsquedas de registros seleccionados mediante los índices por ID ya cargados.
- Se cachea la extensión geográfica de cada cable junto a sus puntos y se invalida cuando cambian extremos o geometría.
- Se retira el código inactivo de una capa vectorial y sus etiquetas; se conserva la capa catastral WMS funcional.
- Se actualiza a `19.0.3.40` el identificador enviado al servicio de geocodificación.
- La versión `19.0.3.41` muestra «Total de fibras» inmediatamente debajo de «N.º de tubos», como dato calculado de solo lectura.
- La pestaña «Fibras» etiqueta por separado los colores del tubo y de la fibra; al cambiar la tipología se completa la relación con todas las fibras y se recalculan sus colores sin sustituir registros existentes.
- Se actualizan el manifiesto, el agente de geocodificación y esta guía a `19.0.3.41`.
- Se añade una pestaña «Técnico» para registrar empleado, fecha y hora, tipo de trabajo y descripción en sitios, elementos de red, cables y splitters; se reutiliza el modelo existente de historial.
- Se amplían los tipos de trabajo con instalación, mantenimiento, reparación y revisión, y se mantienen las categorías históricas.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.42`.
- En la ficha y el modelo de elemento se define el número de bocas para entrada de cable; se incluye el modelo de CTO interna con 2 bocas y se mantiene la CTO general con 4.
- La migración `migrations/19.0.3.43/post-migrate.py` completa el valor de bocas en registros anteriores, conserva los valores válidos y es idempotente.
- El trazado de cables en mapa pide elegir las bocas libres de ambos elementos y valida de nuevo su disponibilidad antes de crear el cable.
- Los selectores del asistente de bandejas muestran los colores almacenados de tubo y fibra como círculos y ocultan fibras ya utilizadas en el elemento actual, salvo la fibra que se está editando.
- Al mover una operación entre bandejas, las posiciones de ambas bandejas se recalculan en orden de tubo y número de fibra.
- En el asistente, «Cable de paso» pasa a llamarse «Sangría» y «Dejar fibras en resto» pasa a «Dejar fibra en Bandeja (Cortados)».
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.43`.
- Se recupera la vista de lista compacta en el asistente de bandejas, conservando los círculos de colores de tubo y fibra y mostrando cada fibra en una fila sin recuadro.
- En los selectores solo se ocultan las fibras que ya están fusionadas; las fibras en resto, sangría y otras operaciones permanecen visibles. La fibra abierta para editar conserva su selección.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.44`.
- También se ocultan las fibras que alimentan directamente la entrada de un splitter, igual que una fusión; resto, sangría y demás asignaciones siguen visibles.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.45`.
- En la pestaña «Cables» de cada elemento, las entradas muestran la boca usada en ese extremo y permiten editarla; lo mismo para las salidas. El resto de los datos queda de solo lectura y no se permite crear ni borrar cables desde esas listas.
- Los cambios de boca siguen sujetos a la validación de rango y a la comprobación de que no esté ocupada.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.46`.
- Los selectores de cable del asistente de bandejas indican la boca de entrada o salida en el elemento activo, junto con la matrícula y el nombre del cable; los cables sin boca configurada se identifican como tales.
- Esta etiqueta es contextual al asistente y no altera los nombres visibles en otras partes del módulo.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.47`.
- En el asistente, «Dejar fibra en Bandeja (Cortados)» pasa a llamarse «Fibra en punta» y se añade «Fibra pendiente de anular».
- Las fibras pendientes de anular no consumen posiciones de empalme; aparecen en rojo en la bandeja y en los selectores, y conservan el estado al reabrir el asistente.
- Se añade «Cartas de Empalme» a elementos con bandejas, con fotos, comentarios, Excel, técnico y fecha de carga.
- Se añade importación en lote por ZIP: se asocia cada Excel a la matrícula completa encontrada en su nombre, se omiten duplicados y se informa de archivos ambiguos o sin asignar.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.48`.
- La importación de cartas admite ahora también `.ods` de LibreOffice Calc y hasta 5.000 entradas ZIP, manteniendo los límites de tamaño para el contenido.
- La creación en lote reutiliza el técnico predeterminado, evitando una consulta repetida por cada carta importada.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.49`.
- Se mueve la importación ZIP de cartas al menú de **Configuración**, disponible para responsables.
- La pestaña de cada elemento sustituye ese acceso por **Subir carta Excel**, que abre un formulario asociado al elemento actual.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.50`.
- En «Cartas de Empalme», las secciones «Fotos» y «Cartas Excel» se muestran una debajo de la otra, ocupando el ancho de la ficha.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.51`.
- La opción «Tiene bandejas por defecto» se configura en los modelos. Se activa inicialmente para CTO, CTO interna, Caja terminal y Caja de registro, y se hereda al crear un elemento o cambiar su modelo.
- La migración única `migrations/19.0.3.52/post-migrate.py` activa bandejas en los elementos existentes de esos tipos y crea una bandeja inicial cuando falta, conservando cantidades ya configuradas. Actualiza directamente solo las columnas de bandejas, sin pasar por la escritura de ficha que puede recalcular matrículas antiguas duplicadas.
- El importador coteja la matrícula y el nombre del elemento; diferencia un código no encontrado de un elemento encontrado sin bandejas.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.52`.
- Se corrige la migración única para no ejecutar `node.write()` ni modificar nombres/matrículas; la activación de bandejas evita el error con matrículas antiguas duplicadas.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.53`.
- En «Cartas de Empalme», «Cartas Excel» pasa encima de «Fotos» y se oculta la etiqueta redundante del campo de documentos.
- Cada carta dispone de un campo independiente «Comentario del técnico» para registrar las modificaciones realizadas en el Excel; las notas de importación se mantienen separadas.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.54`.
- El resultado de importación genera `archivos_no_importados.txt` con la ruta interna de cada archivo omitido y su motivo, incluidos los duplicados.
- La migración única `migrations/19.0.3.55/post-migrate.py` elimina menús repetidos de importación bajo Configuración y conserva el menú canónico.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.3.55`.
- Se añade Cabecera: armarios editables de 1–60 U, biblioteca de ODF/patch panels, switches, routers, OLT, estantes, SAI y paneles ciegos; asignación manual de fibras a puertos con validación de solapes y unicidad.
- Se actualizan el manifiesto y esta guía a `19.0.3.56`.
- Se sincroniza el número de puertos de los paneles con su diseño, evitando eliminar puertos que aún tienen fibras conectadas.
- La opción «Conectar fibra a splitter» desaparece del selector general de Gestión de bandejas; se mantiene disponible únicamente en el flujo interno abierto desde el splitter.
- El menú Cabecera se carga después de declarar su acción en el manifiesto, para resolver correctamente su ID externo durante una actualización.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.4`.
- Se simplifica el SCSS del editor de Cabecera para reducir construcciones CSS modernas que pudieran fallar en el compilador de assets del servidor.
- Se ajusta el cálculo de las unidades U para alinear correctamente los equipos y mantener el rack completo visible al desplazarse.
- Se actualizan el manifiesto, el identificador de geocodificación y esta guía a `19.0.4.1`.
- Se amplía el catálogo de Cabecera con ODF 96F, switches 24/48 puertos, firewall, servidor, NAS, bandeja extraíble, organizador, PDU y ventilación; los frontales tienen detalles visuales por familia.
- Cada equipo muestra un control directo para retirarlo; el lienzo alinea el scroll al inicio y deja visible la barra y controles para subir/bajar.
- Los ODF de alta densidad crean puertos y mantienen la unicidad de asignación de fibras.
- La asignación de fibras usa una búsqueda bajo demanda limitada a 50 resultados por consulta y deja de cargar miles de opciones al abrir el diseñador.
- La revisión `19.0.4.2` amplía el catálogo gráfico y la búsqueda de fibras de Cabecera.
- Los registros técnicos del mapa omiten la etiqueta si nombre y matrícula están vacíos; nunca se muestra el literal `False`.
- Las arquetas nuevas se crean con icono cuadrado y color negro predeterminados; no se sobrescriben los estilos de arquetas existentes.
- En los selectores de Gestión de bandejas, la boca se presenta como «Boca N» sin indicar entrada o salida. Los campos de dirección y validación del cable no cambian.
- Se actualizan manifiesto, agente de geocodificación y manual a `19.0.4.3`.
- La categoría **Arqueta** se sincroniza mediante una migración limitada: nombre «Arqueta», icono cuadrado y color negro. No cambia el nombre ni el estilo de elementos ya creados.
- Se actualizan manifiesto, agente de geocodificación y manual a `19.0.4.4`.
- En las columnas de boca de la ficha de elemento, la etiqueta visible es únicamente «Boca»; se elimina la dirección redundante del encabezado.
- Se actualizan manifiesto, agente de geocodificación y manual a `19.0.4.5`.
- Se amplía el rack del diseñador y se permite editar y guardar el nombre de cada equipo desde su panel de detalle.
- Se elimina la papelera y el botón de retirada; los equipos se retiran arrastrándolos a la zona izquierda. Si hay fibras conectadas, se pide confirmación antes de liberarlas.
- Se incorporan imágenes frontales oficiales para los modelos MikroTik CRS326-24G-2S+RM y Zyxel GS1920-24HPv2, empaquetadas localmente.
- Se actualizan manifiesto, agente de geocodificación y manual a `19.0.4.6`.
- Se sustituyen las fotografías anteriores por frontales recortados de la lámina de ConceptDraw y se añade atribución de origen.
- El catálogo incorpora servidores 1U/3U, RAID 2U/3U, conmutador KVM, monitores rack 7U/8U, SAI gestionable y regleta; se reutilizan los frontales ConceptDraw de switches, servidores, RAID, SAI y paneles.
- Se actualizan manifiesto, agente de geocodificación y manual a `19.0.4.7`.
- Se añade el Panel FHU 1U 48F SC/UPC con 24 puertos asignables y una vista frontal vectorial original. No se copia el archivo gráfico de FS.com porque sus condiciones requieren autorización escrita para reproducirlo o distribuirlo.
- Se documentan SKU, características, fuente y la limitación de reutilización de imágenes.
- Se actualizan manifiesto, agente de geocodificación y manual a `19.0.4.8`.

## Cambios de la versión 19.0.4.9

- El Panel FHU 1U 48F SC/UPC muestra la vista frontal fotográfica del SKU FS.com 35529, con atribución y autorización escrita confirmada por la usuaria.
- El diseñador de Cabecera incorpora zoom entre 60 % y 140 %.
- Una cabecera puede contener varios racks colocados en paralelo; se pueden añadir desde el diseñador y arrastrar equipos de uno a otro.
- Se pueden registrar interconexiones entre equipos indicando puertos, tipo de cable e identificación opcional. Se muestran en el inspector y se eliminan de forma explícita; al retirar equipos se avisa de las conexiones y fibras que se borrarán.
- Se actualizan manifiesto, agente de geocodificación y manual a `19.0.4.9`.

## Memoria de continuidad

Actualizado: 2026-10-29 — candidata local 19.0.4.28

### Identidad y fuentes de verdad

- Proyecto: módulo Fiber GIS para Odoo 19 Community. Fuente local: `work/fiber_gis/`.
- Guía funcional e historial canónicos: este `README.md`; decisiones de relevo: `CONTINUIDAD_CODEX_CHATGPT.md`.
- Entrega anterior: `fiber_gis_19.0.4.28.zip`.

### Objetivo actual

Presentación clara de las líneas de bandeja, tubo oculto en cables de un solo tubo y color por defecto de los cables dibujados según sus fibras.

### Versión y entrega más reciente

- Versión `19.0.4.29`: rejilla de bandejas corregida, «T» solo con varios tubos y colores por número de fibras.
- Versión `19.0.4.28`: retirado **Crear y seguir trazando**; cada cable termina al crearlo.
- Versión `19.0.4.27`: mapa con menos elementos SVG, áreas de clic que no se pintan, proyección de vértices en caché y arrastre del mapa también desde un cable.
- Versión `19.0.4.26`, declarada en el manifiesto y sincronizada en el agente de geocodificación.
- Menús de Configuración y Ajustes restringidos a Responsable; copia de seguridad completa y restauración sin duplicados; nombre de tipología con su Tipo GIS.
- Probada en Odoo 19 Community + PostgreSQL 16: instalación, actualización desde 19.0.4.25 y `TestBackupRestore`. Quedan 25 fallos anteriores en otras pruebas ORM (ver cambios de 19.0.4.26).

### Estado comprobado

- Pruebas estáticas, sintaxis Python/JavaScript y parseo XML comprobados localmente (resultados de esta entrega anotados en el changelog).
- Sin cambios CSS/SCSS.
- No se ha ejecutado el `TransactionCase`, ni instalación/actualización o revisión visual en Odoo 19 Community + PostgreSQL.

### Decisiones vigentes

- Mantener compatibilidad exclusiva con Odoo 19 Community y consultar documentación oficial 19.0.
- Seguir elevando versión, actualizar manual/continuidad y crear un ZIP en cada entrega de código.
- Evitar regresiones CSS: no cambiar SCSS sin compilar los assets y revisar visualmente en Odoo 19.
- La revisión anterior de bandejas quitó el número lateral y ordenó splitter, fusión, punta y sangría; no altera posiciones internas.

### Forma eficiente de continuar

- Revisar primero manifiesto, memoria e historial. Ejecutar `python -m unittest discover -s tests -p 'check_*.py'`, `python -m compileall -q .`, `node --check` para los JS y parseo XML; después construir ZIP con `python scripts/build_release_zip.py --output-dir dist`.
- Mantener `cable_ids` en el orden del trazado al finalizar para que el servidor valide continuidad y registre las sangrías en las cajas correctas.

### Pendientes y bloqueos

- Ejecutar prueba ORM de aplicación de tipología y sangría en Odoo 19 Community + PostgreSQL; el runtime no está disponible aquí.
- Probar visualmente el modal final de tipología y el trazado con varias cajas en una instancia Odoo 19.

### Siguiente paso exacto

Actualizar a 19.0.4.27 y revisar el mapa en un navegador de escritorio con la red real: arrastre desde fondo y desde cable, clic y doble clic en cable, mover elemento y vértice, zoom con rueda y trazado de cable nuevo.

## Auditoría y cambios de la versión 19.0.4.10

- Se revisaron modelos, vistas XML, plantillas QWeb, assets, datos, permisos, hooks, migraciones, pruebas y referencias cruzadas a los métodos y archivos estáticos. No se eliminaron archivos ni callbacks: los métodos aparentemente sin llamadas directas están registrados como decoradores ORM, botones/vistas o plantillas QWeb; los assets declarados en el manifiesto son cargados por el sistema de bundles de Odoo. La migración `19.0.3.35.0` vacía conserva su intención documentada de no volver a renombrar datos al saltar versiones.
- Se simplificó la comprobación de solapamientos: el recorrido ahora ordena equipos por posición y detecta conflictos en una pasada, en lugar de comparar cada pareja. Al validar un lote de equipos se consulta el conjunto del rack una vez por cabecera, no una vez por equipo.
- Se añadió una prueba ORM para la creación de equipos en lote con posiciones solapadas. Su ejecución requiere Odoo 19 y PostgreSQL.
- La auditoría no encontró una base segura para reducir las cargas del mapa: hoy descarga los registros de mapa y filtra por viewport en el navegador. Cambiar a consultas paginadas por viewport requiere mediciones con el volumen real y verificar cables que cruzan el borde; queda documentado como mejora futura, no se hizo una modificación especulativa.
- Referencia técnica: [buenas prácticas de rendimiento de Odoo 19](https://www.odoo.com/documentation/19.0/developer/reference/backend/performance.html), [ORM de Odoo 19](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html) y [assets frontend de Odoo 19](https://www.odoo.com/documentation/19.0/developer/reference/frontend/assets.html).
- Se actualizan manifiesto, User-Agent de geocodificación, pruebas estáticas y manual a `19.0.4.10`.

### Estado de continuidad

- Archivo de traspaso para Codex y ChatGPT web: `CONTINUIDAD_CODEX_CHATGPT.md`. Este README sigue siendo el manual funcional y la guía canónica del módulo.
- Verificaciones ejecutadas para la entrega: se enumeran en el archivo de continuidad y en el resultado de esta revisión.

## Cambios de la versión 19.0.4.11

- El frontal del equipo ocupa ahora toda la superficie visible del elemento colocado en el rack; el nombre, unidades y número de bocas permanecen legibles sobre la imagen.
- Las tomas visibles tienen objetivos clicables, número y estado. En switches de 24 y 48 bocas, la posición sigue la disposición de las tomas del frontal. Las bocas de paneles de fibra muestran también asignación de fibra e interconexión.
- Para cablear desde el dibujo, pulsa primero una boca libre y luego una boca libre de otro equipo. El sistema registra una interconexión por esos extremos, la marca visualmente y elige fibra o Ethernet según los equipos. Los puertos ocupados avisan antes de intentar crear otra conexión. Se conserva el formulario manual de interconexiones.
- Se retira el generador decorativo de hasta 24 indicadores que ya no se usa; los controles visuales ahora se generan desde el número real de bocas del equipo. La generación utiliza un mapa de puertos de fibra para evitar búsquedas repetidas al renderizar cada toma.
- Se actualizan manifiesto, User-Agent, comprobaciones y manual a `19.0.4.11`.
- Comprobaciones de esta entrega: 56 pruebas estáticas, sintaxis de todos los JS, compilación Python, parseo XML y estructura SCSS. La alineación visual de las bocas y la actualización funcional siguen pendientes en una instancia Odoo 19 con navegador.


## Cambios de la versión 19.0.4.12

- Se convierte la biblioteca de equipos del rack en un catálogo persistente de base de datos. Incluye migración idempotente y permisos de edición para responsables.
- Desde cada elemento de la biblioteca se puede cambiar nombre de plantilla, altura, imagen frontal y número de bocas; los marcadores numerados se arrastran sobre la vista previa y sus coordenadas se guardan. La imagen y las posiciones de las bocas se aplican al tipo compartido.
- El cambio de número de bocas se propaga a equipos ya colocados. Si la reducción afecta una boca con fibra asignada o una interconexión, se impide el guardado para conservar el cableado existente.
- Las interconexiones se dibujan sobre el rack con flecha de origen a destino. Se enrutan por el lateral izquierdo o derecho más cercano dentro del mismo rack, o por encima de los armarios cuando conectan racks diferentes.
- Manual actualizado con el flujo de edición, el alcance de los cambios y las reglas para reducir bocas.
- Referencias oficiales Odoo 19: [ORM y campos Image](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html), [Hooks Owl](https://www.odoo.com/documentation/19.0/developer/reference/frontend/hooks.html), [componentes Owl](https://www.odoo.com/documentation/19.0/developer/howtos/frontend_owl_components.html), [migraciones](https://www.odoo.com/documentation/19.0/es/developer/reference/upgrades/upgrade_scripts.html).
- La instalación/actualización y prueba visual en Odoo 19 Community con PostgreSQL sigue pendiente porque este entorno no incluye una instancia Odoo.


## Cambios de la versión 19.0.4.13

- La edición de la biblioteca deja el panel lateral y se abre en una ventana modal amplia e independiente, con los campos de configuración en una columna y la vista frontal ampliada en otra. En móvil, la ventana se adapta a una sola columna.
- Se reemplaza el SVG anterior por un canvas 2D redibujado tras renderizar, cambiar el zoom o redimensionar la ventana. Los cables usan una línea de color con contorno blanco grueso, sombra y flecha en la boca de destino para distinguir el recorrido sobre el equipo. Se conserva el enrutado lateral dentro de un rack y superior entre racks.
- Se actualiza la comprobación estática del editor y del canvas, el manifiesto, el User-Agent, el README y la memoria de continuidad.
- Pruebas locales: 56 comprobaciones estáticas, sintaxis JS, compilación Python, parseo XML y balance SCSS. La visualización todavía requiere validación en Odoo 19 con navegador.

## Cambios de la versión 19.0.4.14

- Se corrige la hoja SCSS del editor: el tamaño de la ventana usa `width`/`height` con límites `max-width`/`max-height`, en lugar de `min()` con unidades CSS distintas que Sass podía intentar evaluar durante la compilación. La captura del usuario mostraba la notificación fatal de compilación y el modal sin estilos.
- La vista previa del frontal conserva una altura amplia para mover las bocas con precisión; su altura se ajusta por unidades U desde JavaScript. Se elimina `aspect-ratio` del SCSS para mantener la hoja más compatible con el compilador de assets de Odoo.
- Se añade una comprobación estática de regresión que impide reintroducir las expresiones `min()`/`aspect-ratio` en estos estilos. En este entorno no hay Sass/libSass ni Odoo instalado; no se declara compilación real verificada. La actualización del bundle y validación visual final requieren Odoo 19.
- Referencia oficial: [Assets frontend de Odoo 19](https://www.odoo.com/documentation/19.0/developer/reference/frontend/assets.html), que documenta el procesamiento de hojas SCSS en los bundles de assets.
- Se actualizan manifiesto, User-Agent, pruebas, manual y continuidad a `19.0.4.14`. Retorno recomendado: `19.0.4.12`.

## Cambios de la versión 19.0.4.15

- Se corrige el error RPC de `fiber.gis.cable.tray.wizard` al registrar una operación en el historial. El campo `operation` usa una selección definida mediante el nombre del método `_selection_operation`; `_work_log_text()` ahora obtiene las opciones resueltas y traducidas con `_description_selection(self.env)` antes de formar el diccionario de etiquetas.
- Se añade un `TransactionCase` que llama `_work_log_text()` en una operación «Fibra en punta» y verifica la etiqueta resultante; también hay una comprobación estática para evitar volver a tratar la referencia del método como una lista.
- Referencia oficial: [ORM de Odoo 19 — Selection](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html), que admite listas, funciones y nombres de método como fuentes de opciones.
- Comprobaciones locales: pruebas estáticas, sintaxis y compilación Python, XML. El `TransactionCase` requiere Odoo 19 + PostgreSQL y queda pendiente de ejecución en una base de pruebas.
- Se actualizan manifiesto, User-Agent, README y continuidad a `19.0.4.15`. Punto de retorno: `fiber_gis_19.0.4.14.zip`.

## Cambios de la versión 19.0.4.16

- Se añaden las relaciones **1:4 Casete** y **1:8 Casete** al desplegable de instalación del asistente de bandejas. Las mismas opciones quedan reconocidas en la ficha del splitter, los registros de bandeja y el asistente para crear splitters conectados a otra salida.
- Se centralizan las opciones y cálculos de relaciones. El recuento interpreta «Casete» y crea 4 u 8 salidas; la pérdida nominal de referencia usa los valores estándar de 1:4 y 1:8, y sigue siendo ajustable según el fabricante.
- Se añaden pruebas estáticas de relaciones, salidas y pérdidas, y un `TransactionCase` que instala ambos tipos desde el asistente. La ejecución ORM requiere Odoo 19 + PostgreSQL.
- Se actualizan manifiesto, User-Agent, manual y continuidad a `19.0.4.16`. Punto de retorno: `fiber_gis_19.0.4.15.zip`.


## Cambios de la versión 19.0.4.17

- La operación Sangría ahora pregunta por el cable que viene de la caja anterior y el cable que va a la caja destino. Los selectores indican la caja adyacente, la boca y el identificador/nombre del cable; los cables disponibles se filtran según el sentido de su conexión al elemento.
- Las fibras no cortadas se emparejan por número como continuidad entre ambos tramos y se muestran como recorrido en bandeja y en el trazado. Las fibras de entrada marcadas como cortadas quedan en punta en la misma bandeja y pueden recibir otra operación mediante la confirmación de reemplazo existente.
- Se hace obligatorio elegir una bandeja también en acometidas conectadas desde un splitter, y debe coincidir con la bandeja del splitter. Una bandeja admite distintos trabajos para fibras diferentes.
- Se añaden pruebas ORM para continuidad, etiquetas direccionales, mezcla de sangrías/puntas/splitter y bandeja obligatoria, además de comprobaciones estáticas de la vista.
- No se requiere migración: el campo existente `output_fiber_id` de una línea de bandeja representa la fibra del tramo saliente; los nuevos campos de selección pertenecen al asistente transitorio. Las sangrías históricas sin fibra de salida se conservan y se etiquetan como continuidad sin registrar.
- Referencias oficiales Odoo 19: [ORM API](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html) y [restricciones de modelos](https://www.odoo.com/documentation/19.0/developer/tutorials/backend.html). No se modificaron estilos; las reglas de compilación CSS/SCSS establecidas en 19.0.4.16 siguen vigentes.
- Pruebas ORM e instalación visual deben ejecutarse en Odoo 19 Community + PostgreSQL; ese entorno no está disponible aquí. Punto de retorno: `fiber_gis_19.0.4.16.zip`.


## Cambios de la versión 19.0.4.18

- En la operación **Sangría**, el cable entrante inicial prioriza un tramo que llega a la caja. Al elegir la operación, el asistente busca un cable saliente registrado y real cuya cantidad de fibras, número de tubos y fibras por tubo coincidan con el entrante; genera sus fibras antes de mostrarlo. Al cambiar el cable entrante o la caja, actualiza esa propuesta.
- Si no hay un cable saliente compatible, el selector queda vacío y se debe elegir o crear el tramo correcto. Así se evita proponer un cable de dos fibras para una continuidad de doce fibras y que el resto se registre por error como fibras en punta.
- Las asignaciones existentes se conservan. Si la prueba anterior guardó fibras como punta por haber elegido un cable incompatible, hay que repetir Sangría con los tramos correctos y confirmar el reemplazo de asignaciones cuando el asistente lo solicite; no se reinterpretan automáticamente los registros guardados.
- Se añade una prueba ORM para verificar que el valor inicial elige el cable saliente real con la misma distribución de tubos y genera las fibras de sus tubos. La prueba requiere Odoo 19 Community y PostgreSQL.
- No se modificó CSS/SCSS. Versión anterior y punto de retorno: `19.0.4.17`.


## Cambios de la versión 19.0.4.19

- Se elimina el límite de 30 trabajos por bandeja en fusiones, sangrías y splitters, tanto al registrar operaciones como al mover líneas de una bandeja a otra. El mensaje «posiciones libres suficientes» deja de aparecer.
- La ficha y el esquema muestran el número de trabajos registrados sin una capacidad máxima. El campo de capacidad antiguo se conserva por compatibilidad de datos, pero ya no restringe operaciones ni aparece en la interfaz.
- Se añade una prueba ORM con 43 fibras continuas en una sola bandeja, superando el antiguo límite de 30. Requiere Odoo 19 Community y PostgreSQL.
- No se modificó CSS/SCSS. Versión anterior y punto de retorno: `19.0.4.18`.


## Cambios de la versión 19.0.4.20

- Se corrige la causa de las entradas duplicadas **Importar cartas de empalme (ZIP)**: el XML de limpieza borraba en cada actualización el identificador externo (`ir.model.data`) del menú canónico, pero dejaba el registro del menú. Al cargar de nuevo los datos, Odoo creaba otra entrada. La limpieza ya no elimina identificadores XML del módulo.
- La migración `migrations/19.0.4.20/post-migrate.py` conserva el menú canónico y elimina sus duplicados con el mismo nombre y padre.
- Se añade una comprobación estática para impedir que la limpieza vuelva a borrar los XML IDs y verificar que la migración excluye expresamente el menú canónico.
- Para aplicar la limpieza de los duplicados actuales, actualiza el módulo a esta versión. No modifica las cartas de empalme ni otros datos del GIS. Referencia oficial: [scripts de actualización de Odoo 19](https://www.odoo.com/documentation/19.0/es/developer/reference/upgrades/upgrade_scripts.html).
- Sin cambios CSS/SCSS. Versión anterior y punto de retorno: `19.0.4.19`.


## Cambios de la versión 19.0.4.21

- El selector de bocas para dibujar cables añade **Crear y seguir trazando**. Tras guardar un tramo, permite iniciar el siguiente desde la caja de destino y seguir encadenando cajas.
- Cuando se crea un tramo a continuación de otro, se registra automáticamente una Sangría en la primera bandeja de la caja intermedia, emparejando fibras por número. La operación queda editable desde Gestión de bandejas. Las fibras ocupadas se preservan; si los tramos no comparten distribución compatible de tubos/fibras o falta una bandeja, aparece un aviso y se puede resolver manualmente.
- En el asistente de bandejas, los campos se muestran como **Cable entrada** y **Cable salida**; el selector sigue indicando la caja y el nombre o matrícula del cable.
- Se añade prueba ORM para la continuidad automática y una comprobación estática del botón/flujo de trazado. Las pruebas ORM requieren Odoo 19 Community y PostgreSQL.
- Referencias oficiales Odoo 19: [servicio ORM de JavaScript](https://www.odoo.com/documentation/19.0/developer/reference/frontend/javascript_reference.html) y [ORM Python](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html).
- Sin cambios CSS/SCSS. No requiere migración ni altera asignaciones previas. Versión anterior y punto de retorno: `19.0.4.20`.


## Cambios de la versión 19.0.4.29

- **Líneas de bandeja legibles.** La rejilla de cada línea conservaba una primera columna de 22 px para el número de posición retirado en 19.0.4.23, de modo que «Splitter», «Fibra en punta» o «1/4 salidas ocupadas» quedaban comprimidos, partidos en varias líneas o superpuestos con la relación del splitter. Ahora la rejilla tiene seis columnas (tipo, entrada, flecha, salida, relación y papelera) y cada línea emite siempre las seis casillas, aunque estén vacías, para que no se desplacen. Los textos de tipo, relación y salida vacía no se parten y se recortan con puntos suspensivos.
- **Tubo solo con varios tubos.** Si el cable tiene un único tubo (o ninguno), no se muestra «T1» ni su color: en la ficha de la caja (Bandejas), el diagrama del splitter, los asistentes de bandeja y de salidas, el selector de fibras con casillas, el nombre de la fibra en los desplegables, la lista de fibras del cable, la ficha de la fibra y las listas de líneas de bandeja y salidas de splitter. Nuevo campo calculado `show_tube` en la fibra (y related en línea de bandeja, splitter y salida). Los datos de tubo no cambian.
- **Color por defecto de los cables dibujados en el mapa** según el total de fibras de la tipología: 6 FO celeste `#38bdf8`, 12 FO rojo `#dc2626`, 16 FO violeta `#7c3aed`, 24 FO marrón `#8b4513`, 48 FO verde `#16a34a`, 72 FO verde oscuro `#14532d`, 80 FO azul `#2563eb`, 96 FO rosa `#ec4899`, 128 FO naranja `#f97316` y 288 FO negro `#111111`. Otras cantidades usan el color por defecto `#0f766e`. Se aplica al crear el cable y de nuevo al elegir la tipología final; los cables existentes no cambian.
- **Corrección: cambiar un cable ya no le reasigna la tipología «12 fibras».** `write()` del cable buscaba una tipología con 0 tubos × 12 fibras en cualquier escritura que no incluyera la tipología (renombrar, cambiar el tipo de trazado, mover un vértice en el mapa) y se la asignaba. En cables de 24 fibras o más fallaba con «No se puede reducir la tipología»; en cables de 1 tubo × 12 fibras los dejaba sin tubos. Ahora la tipología solo se resuelve cuando cambian la tipología o las cantidades de tubos y fibras. Los cables que ya se hubieran convertido así conservan su valor actual: revisa su tipología en la ficha si hace falta.
- Pruebas: `tests/check_tray_layout.py` (3 comprobaciones estáticas) y en `TestMapCable` colores por número de fibras, tubo oculto con un solo tubo y escritura que conserva la tipología. En la batería ORM bajan de 25 a 21 los fallos anteriores (la corrección de `write()` resuelve 4) y no aparece ninguno nuevo. SCSS compilado en Odoo 19 Community. Sin migración: los campos nuevos no se almacenan. Punto de retorno: `19.0.4.28`.

## Cambios de la versión 19.0.4.28

- Se retira **Crear y seguir trazando**. Mientras se dibuja un cable, pulsar en el mapa añade esquinas, así que al llegar al borde de la vista no había forma de desplazarlo para seguir encadenando cajas. Ahora el trazado termina al crear cada cable: se elige la tipología, el mapa vuelve a poder desplazarse y el siguiente cable se empieza desde su caja de origen.
- El servidor deja de aceptar `previous_cable_id` en `create_from_map` y ya no crea sangrías automáticas entre tramos. `finalize_map_cable_chain` se sustituye por `finalize_map_cable(cable_id, profile_id)`, que aplica la tipología a un único cable planificado sin fibras usadas. La continuidad entre dos cables en una caja se registra con **Sangría / cable de paso** en el Asistente Bandejas.
- Las sangrías creadas antes por el trazado encadenado se conservan. No hay cambios de esquema ni migración; sin cambios CSS/SCSS.
- Pruebas: `TestMapCable.test_finalize_map_cable_applies_final_profile` sustituye a la prueba de cadena; la comprobación estática verifica que no quedan el botón, el estado de cadena ni los métodos retirados. Punto de retorno: `19.0.4.27`.

## Cambios de la versión 19.0.4.27

- **Arrastre del mapa.** Pulsar sobre un cable bloqueaba el desplazamiento: en zonas densas el área de clic de los cables (16 px) cubre casi todo el fondo y el mapa parecía no responder. Ahora se arrastra también desde un cable. El puntero se captura solo cuando empieza el movimiento, de modo que un clic sin mover selecciona el cable y el doble clic abre su ficha. En modo de trazado de cable se mantiene el aviso anterior.
- **Menos elementos SVG.** Cada cable tiene una sola área de clic en lugar de una por tramo. En una red de prueba de 2.500 elementos y 3.000 cables, la vista general pasa de 34.048 a 25.026 elementos SVG. Los tramos visibles siguen siendo un `<path>` de una sola línea, porque así el navegador solo genera los guiones visibles de los cables discontinuos; agruparlos multiplicaba el coste con zoom alto.
- **Áreas de clic sin pintar.** `.o_fiber_gis_cable_hit` usa `visibility: hidden` y `pointer-events: stroke`: recibe el puntero y no se pinta.
- **Menos cálculo por redibujado.** La proyección Mercator de los vértices de cada cable se guarda junto a su geometría; las coordenadas se escriben con una décima de píxel; la comprobación de cables del plan usa un conjunto en lugar de buscar en una lista por cable.
- **Medición** (Odoo 19 Community + PostgreSQL 16, Chromium sin GPU, misma secuencia en ambas versiones): zoom de 6 pasos en la vista general de 5,8 s a 4,6 s de bloqueo y peor fotograma de 933 a 633 ms; zoom intermedio de 1,4 a 1,2 s; arrastre con zoom alto de 5,4 s a 2,5 s de bloqueo y de 54 a 21 fotogramas lentos. Con GPU los tiempos absolutos serán menores; falta revisarlo en un navegador de escritorio.
- **Descartado tras medir.** Aplicar la transformación de vista previa al `<svg>` completo como capa compuesta (`will-change` y `overflow: visible`) costaba 266 ms por fotograma frente a 37 ms en el grupo interno; se mantiene la transformación en `.o_fiber_gis_scene`.
- Comprobaciones: `tests/check_map_render.py` (5 comprobaciones estáticas) y prueba funcional en Chromium: clic y doble clic en cable, arrastre desde cable, arrastre de vértice con guardado, sin errores JavaScript. El SCSS se compiló en Odoo 19 Community. Sin cambios de modelo ni migración. Punto de retorno: `19.0.4.26`.

## Cambios de la versión 19.0.4.26

- **Permisos.** Los menús **Configuración** y **Ajustes** usaban `groups="-fiber_gis.group_fiber_gis_manager"`. En Odoo 19 el prefijo `-` quita el grupo del menú (`Command.unlink` en `odoo/tools/convert.py`), por lo que quedaban visibles para todos. Ahora usan `groups="fiber_gis.group_fiber_gis_manager"`. El asistente de Ajustes deja de tener permiso para el perfil Usuario y sus acciones (guardar, colores CTO, recalcular fibras, crear y restaurar copia) comprueban el perfil Responsable en el servidor.
- **Copia de seguridad.** Se añaden planes de despliegue, cartas de empalme, cabeceras, equipos, puertos, interconexiones y la biblioteca de equipos. Los binarios (fotos, cartas Excel, imágenes de biblioteca) se guardan en base64 y se restauran; antes se omitían y la restauración fallaba con cualquier foto.
- **Restauración.** Con el contexto `fiber_gis_restore` no se generan automáticamente bandejas, fibras, tramos, salidas de splitter, líneas de bandeja ni puertos de panel, que vienen en la copia (antes se duplicaban). Solo se borran y restauran los modelos incluidos en la copia. Las relaciones many2many entre modelos del módulo se escriben cuando existen ambos extremos. Los campos calculados de solo lectura y los related almacenados no se escriben: se recalculan (antes se escribían, por ejemplo, las coordenadas related del cable sobre el elemento). Se desactiva el seguimiento de mail durante la restauración.
- **Copias antiguas.** Se aceptan y se recuperan sus fotos (`b'...'`). Si contienen elementos o fibras pero no cartas, cabeceras o planes, y la base actual sí los tiene, se rechaza la restauración para no borrarlos.
- **Tipologías.** `name_get` ya no se utiliza en Odoo 19; se sustituye por `_compute_display_name` para mostrar «Nombre - Tipo GIS: X».
- Pruebas: 7 comprobaciones estáticas nuevas (`tests/check_backup_restore.py`) y `tests/test_backup_restore.py` (TransactionCase: copia y restauración sin duplicados con fotos, carta Excel, splitter, plan, cabecera, panel con fibra e interconexión; permisos; nombre de tipología). Sin cambios CSS/SCSS ni migración: los menús y permisos se actualizan con el módulo.
- Ejecutado en Odoo 19 Community (rama `19.0` oficial) + PostgreSQL 16: instalación, actualización desde `19.0.4.25` (los menús pasan de 0 a 1 grupo y desaparece el permiso de Usuario sobre Ajustes) y `TestBackupRestore` en verde. El resto de la batería tiene 25 fallos que ya existían en `19.0.4.25` sin estos cambios (17 en `TestCabinet` por `_check_manager` al ejecutarse sin el grupo Responsable, 3 en `TestSplitterManagement`, 2 en `TestMapCable`, 2 en `TestCableProfilesAndTechnicians` y 1 de geocodificación sin red).
- Referencias oficiales Odoo 19: [ORM](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html), [seguridad](https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html), [`convert.py` 19.0](https://github.com/odoo/odoo/blob/19.0/odoo/tools/convert.py). Punto de retorno: `19.0.4.25`.

## Cambios de la versión 19.0.4.25

- La relación de fibras del cable en el asistente de splitter pasa a usar el componente HTML de fibra ya empleado por el diagrama del splitter: círculos de color para tubo/fibra, nombre del cable y extremo remoto.
- Se mantienen los resúmenes de conexión de origen y destino junto a cada fibra. Se reutiliza SCSS existente; no se añaden reglas CSS/SCSS. Se añadió comprobación estática y se amplía la prueba ORM. Punto de retorno: `19.0.4.24`.

## Cambios de la versión 19.0.4.24

- En la gestión de salidas del splitter, el selector de cable recibe el contexto de caja y boca para mostrar la dirección y el elemento del otro extremo en lugar del genérico “Cable”.
- Al elegir un cable, el panel enumera todas sus fibras con tubo/color y el resumen de conexiones registrado en ambos extremos. Se distinguen operaciones de bandeja, conexiones con splitters y salidas de splitter que alimentan acometidas.
- Se añadió una prueba ORM para validar el nombre direccional y el listado completo de fibras. Sin cambios CSS/SCSS ni migración; queda pendiente ejecutar ORM y revisar el diálogo en Odoo 19 Community.
- Punto de retorno: `19.0.4.23`.

## Cambios de la versión 19.0.4.23

- En la lista visual de la pestaña Bandejas de la ficha de la caja se quitó el número interno que aparecía al principio de cada fila.
- Las filas se ordenan por tipo de trabajo: primero splitters, después fusiones, luego fibras en punta (incluidas las pendientes de anular) y al final sangrías. Dentro de cada grupo se conserva el orden interno de posición.
- El cambio afecta solo a la presentación: no renumera ni modifica las asignaciones guardadas. No cambia CSS/SCSS ni requiere migración. Pruebas estáticas locales; ORM y revisión visual en Odoo 19 Community + PostgreSQL pendientes. Punto de retorno: `19.0.4.22`.

## Cambios de la versión 19.0.4.22

- La tipología de cable deja de solicitarse antes del trazado. Se puede dibujar un tramo o encadenar varias cajas y elegir una sola tipología al finalizar.
- La tipología elegida se aplica a todos los cables de la cadena. Se regeneran sus fibras con los tubos, cantidades y colores correspondientes; después se crean las sangrías entre segmentos consecutivos en la primera bandeja de cada caja intermedia.
- Se valida que la cadena esté conectada y que las fibras provisionales no se hayan usado antes de cambiar la tipología. Si falta una bandeja o hay fibras ocupadas, el mapa informa del problema.
- El panel de trazado muestra que la tipología se selecciona al final; la ventana final exige seleccionar una antes de confirmar.
- Se añade prueba ORM para la selección final de tipología con cambio de cantidad de fibras y tubos, y comprobación estática de que el selector no interrumpe el trazado.
- No se modificó CSS/SCSS ni se requiere migración. La actualización y las pruebas ORM siguen pendientes en Odoo 19 Community + PostgreSQL. Punto de retorno: `19.0.4.21`.
