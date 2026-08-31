# Fiber GIS para Odoo 19 Community

Modulo para gestionar una red de fibra optica desde Odoo Community con inventario tecnico, mapa GIS, cables, fibras, bandejas, trazado de averias e informes para tecnicos.

## Version 19.0.3.37.0

- Nombre del cable manual. Ya no cambia al modificar las cajas. La migracion recupera
  el nombre anterior guardado si el actual sigue siendo el generado por 3.35/3.36.
- Tipologia sustituye a Matricula en la ficha y listado de cables. Es un catalogo editable
  en Configuracion > Tipologias de cable, con nombre, tubos y fibras. Con tubos, las fibras
  son por tubo; sin tubos, el numero es el total. La ficha copia esos datos de la tipologia.
- Los cables generan sus fibras al crearse. Cambiar una tipologia actualiza sus cables;
  si una reduccion dejara fibras fuera del total, se rechaza sin borrar fibras ni conexiones.
- Tipo GIS se oculta en la ficha del cable. Su dato interno y las matriculas antiguas se
  conservan para importaciones, acometidas y filtros. Longitud pasa a Longitud estimada.
- La pestaña Fibras muestra por separado origen y destino: elemento, direccion, bandeja,
  fusion/resto/paso/splitter/puerto, fibra contraparte, tecnico y fecha conocidos.
- Tecnicos de instalacion en cables; Tecnico en los asistentes de bandejas y salidas de
  splitter, contenidos de bandeja, splitter y revision de fibra. Seleccion desde Empleados.
  El usuario que registra el trabajo queda aparte, como Registrado por en el historial.
- Dependencia nueva: `hr` (Empleados de Odoo Community). Se usa `hr.employee.public`, el
  directorio publico de empleados, sin conceder acceso a expedientes privados de RR. HH.
  En los asistentes se propone el empleado vinculado al usuario de la empresa actual,
  solo si es unico. Se puede elegir otro; los historicos sin autor conocido siguen vacios.
- No se cambian mapa, CSS, colores ni los eventos de doble clic corregidos en 3.36.

Hacer copia de seguridad, sustituir la carpeta, reiniciar y actualizar, sin desinstalar.
La copia propia del modulo incluye tipologias y referencias a empleados, no expedientes
de RR. HH.; una restauracion completa requiere la copia de la base y su filestore.
Las pruebas locales no equivalen a instalar el modulo en un servidor Odoo.

Validado localmente: 12 regresiones de cables/empleados, 10 de acciones/vistas y 14 de
geocodificacion; sintaxis Python 3.10, XML y JavaScript. Ensayo OWL con servicios simulados
en 1440, 768 y 390 px. Se incluyen 9 nuevas pruebas ORM en `test_cable_profiles.py`,
pendientes de ejecutar con Odoo 19 y PostgreSQL mediante `--test-tags /fiber_gis`.

Referencia oficial: [directorio publico de empleados, Odoo 19](https://github.com/odoo/odoo/blob/19.0/addons/hr/models/hr_employee_public.py).

## Version 19.0.3.36.0

- Corrige `action.views is undefined` al abrir una fibra con doble clic. Las acciones
  del asistente de bandejas, ficha de splitter y gestion de salida incluyen ahora
  `views` con el identificador de su formulario. Se mantienen el cable y fibra seleccionados.
- No cambia el diseno, el mapa, las conexiones ni los nombres automaticos de cables.
- La llamada directa `orm.call` no pasa por `clean_action`, a diferencia de un boton de Odoo.
  El cliente necesita `views`; `view_mode` y `view_id` por si solos no completan esa lista.
- La regresion ejecuta los metodos Python con registros simulados y entrega sus respuestas
  al ensayo OWL. Verifica tambien el contrato de la accion, antes ausente de la prueba.
  Reproduce el fallo de 3.35.0 y valida la correccion en fusiones, resto, splitters y salidas.

Sustituir la carpeta del modulo, reiniciar Odoo y actualizarlo sin desinstalar.
Validacion local: `check_tray_interactions.py`, `check_tray_browser.cjs` y `check_cable_names.py`.
No se ha ejecutado una instalacion ni las pruebas ORM en un servidor Odoo en este entorno.

Referencias oficiales de Odoo 19:
[call_kw y call_button](https://github.com/odoo/odoo/blob/19.0/addons/web/controllers/dataset.py)
y [procesamiento de acciones](https://github.com/odoo/odoo/blob/19.0/addons/web/static/src/webclient/actions/action_service.js).

## Version 19.0.3.35.0

- Doble clic en una fibra de bandeja abre el asistente con ese cable y fibra seleccionados.
  Un clic no abre la ficha. Si corresponde a un splitter, abre ese splitter.
- Un clic en el numero de una salida abre su asistente de conexion: fusion, otro splitter
  o acometida. Se conserva la confirmacion para reutilizar una salida ocupada.
- Ambos diagramas usan un campo OWL propio y eventos locales. No dependen de eventos en
  document ni de la edicion HTML de Odoo. Se corrige la llamada a Record.isDirty(), que es
  un metodo asincrono en Odoo 19, para no forzar guardados de fichas sin cambios.
- Se mantienen el arrastre entre bandejas, la papelera con confirmacion y el aspecto previo.
- El nombre de cada cable sigue el formato: matricula origen, espacio, matricula destino,
  espacio y direccion del destino. Ejemplo: `A5-760 A5-761 Calle Real 5, Granada`.
  Si un extremo carece de matricula, se utiliza su nombre. No se cambia la matricula propia
  del cable, incluidas las acometidas ID-cliente, ni sus fibras, conexiones o geometria.
- Al actualizar se renombran tambien los cables existentes y archivados. El nombre anterior
  queda conservado en `previous_name`, disponible como columna opcional en el listado.
  Cambiar los extremos del cable o su matricula/direccion de elemento actualiza el nombre.

Reiniciar Odoo y actualizar el modulo existente, sin desinstalarlo. Incluye migracion
`migrations/19.0.3.35.0/post-cable-names.py`. Realizar antes una copia de seguridad de la base.

Validacion local:

```text
python -B fiber_gis/tests/check_tray_interactions.py qa
python -B fiber_gis/tests/check_cable_names.py
node fiber_gis/tests/check_tray_browser.cjs qa
```

La prueba de navegador requiere Playwright y `qa/owl.js`, descargado del
[OWL incluido en Odoo 19](https://github.com/odoo/odoo/blob/19.0/addons/web/static/lib/owl/owl.js).
`PLAYWRIGHT_CHANNEL=chrome` permite usar Chrome instalado. Monta el componente y su plantilla
con OWL real; solamente simula los servicios RPC/dialogos. Comprueba clic, doble clic, teclado,
guardado, confirmacion de borrado, arrastre y desmontaje; captura tres anchuras.
Las pruebas ORM en `tests/test_map_cable.py` y `tests/test_splitter.py` requieren Odoo 19 con
una base de pruebas y no se han ejecutado en este entorno. No se ha verificado la instalacion
en el servidor del usuario.

Referencias oficiales: [Record de Odoo 19](https://github.com/odoo/odoo/blob/19.0/addons/web/static/src/model/relational_model/record.js),
[propiedades de campos OWL](https://github.com/odoo/odoo/blob/19.0/addons/web/static/src/views/fields/standard_field_props.js)
y [scripts de actualizacion](https://www.odoo.com/documentation/19.0/developer/reference/upgrades/upgrade_scripts.html).

## Version 19.0.3.34.0

- Pulsar una fibra en el diagrama de bandejas abre el asistente con ese cable y fibra
  seleccionados. En una fusion se precargan ambos extremos, incluido el lado pulsado.
  Se muestra la situacion actual con bandeja, operacion, tubo, fibra, colores y direccion.
  Abrir el asistente no modifica conexiones; registrar un cambio conserva la confirmacion
  existente cuando afecta a fibras utilizadas. El arrastre entre bandejas se mantiene.
- Una fila de splitter abre su ficha. Las salidas del diagrama son pulsables, con las
  opciones Fusionar con una fibra, Conectar otro splitter y Conectar acometida de cliente.
  Se retira el antiguo boton de acometida de la cabecera. Observaciones esta en su pestana.
- Se puede crear un splitter secundario o conectar uno existente sin entrada. La conexion
  directa entre splitters es local al mismo elemento, en la misma u otra bandeja. Para
  llegar a otra caja se usa una fibra del cable correspondiente.
- No se permite doble ocupacion de una salida ni ciclos entre splitters. Una salida ocupada
  muestra su destino y exige confirmar su desconexion antes de reutilizarla. Desconectar no
  borra el cable, las fibras ni el splitter secundario. Se conserva el trazado hacia el origen
  atravesando la cascada y se registra el trabajo en el elemento.
- Se mantienen modelos, tipos de funcion, permisos y geocodificacion de la version anterior.
  No se cambia el renderizado ni el comportamiento de navegacion del mapa.

Actualizar el modulo existente, sin desinstalarlo, y reiniciar Odoo para cargar el Python nuevo.
No hace falta convertir los splitters existentes: la nueva entrada por salida es opcional.

Validacion local sin servidor Odoo:

```text
python -B fiber_gis/tests/check_tray_interactions.py qa
python -B fiber_gis/tests/check_local_geocoding.py
node fiber_gis/tests/check_tray_browser.cjs qa
```

La ultima prueba necesita Playwright; PLAYWRIGHT_CHANNEL=chrome permite usar Chrome instalado.
En 3.35.0 esta prueba se ha sustituido por montaje OWL real (ver requisitos arriba).
Las pruebas TransactionCase de `tests/test_splitter.py` necesitan una base de pruebas Odoo 19;
no se han ejecutado en este entorno local. No equivalen a una instalacion verificada en servidor.

Referencias: [seguridad de Odoo 19](https://www.odoo.com/documentation/19.0/developer/tutorials/restrict_data_access.html)
y [FormController oficial de Odoo 19](https://github.com/odoo/odoo/blob/19.0/addons/web/static/src/views/form/form_controller.js).

## Version 19.0.3.33.0

- En la ficha de los equipos, Categoria interna se llama Modelo y Tipo GIS se llama Tipo funcion.
  El antiguo texto libre de fabricante se identifica como Modelo del fabricante para distinguirlo.
- Configuracion > Modelos permite crear modelos, relacionar sus funciones y elegir icono y color.
  Los catalogos conservan los permisos existentes: Responsable los modifica y Usuario los consulta.
- El tipo de funcion se filtra por el modelo. Se puede crear desde su selector con Crear y editar
  o desde la ficha del modelo. Una funcion puede utilizarse en varios modelos.
- Al elegir un modelo se proponen su icono y color. Ambos se pueden cambiar en el equipo.
  Editar el catalogo no recolorea los equipos existentes. La accion explicita de actualizar
  colores de CTO por iluminacion sigue disponible.
- Se mantienen los identificadores y datos anteriores. La actualizacion relaciona las funciones
  por categoria tecnica y conserva las combinaciones que ya utilizaban los equipos.
- Las busquedas validan que el municipio sea Granada capital o Santa Fe; la provincia no basta.
  La busqueda del mapa conserva el municipio visible y permite indicar el otro en la consulta.
- Las nuevas direcciones automaticas contienen solo calle, numero cuando exista y municipio.
  No se modifica ninguna direccion ya guardada ni el boton Abrir en Google Maps.
- No se cambia el renderizado del mapa, las bandejas ni los cables.

Actualizar el modulo existente, sin desinstalarlo. Incluye migracion en
`migrations/19.0.3.33.0/post-model-functions.py` y pruebas de regresion.

Referencias: [ORM de Odoo 19](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html),
[actualizaciones de Odoo 19](https://www.odoo.com/documentation/19.0/developer/reference/upgrades/upgrade_scripts.html)
y [campos de direccion de Nominatim](https://nominatim.org/release-docs/latest/api/Output/).

## Version 19.0.3.32.0

La pestana Datos CTO pasa a llamarse Cobertura CTO y se muestra en todos los elementos de red,
sin depender de su categoria. Mantiene sus campos, datos y permisos de Usuario y Responsable.
Datos Dowisp conserva su condicion de visibilidad para CTO. No cambia el mapa.

## Version 19.0.3.31.0

El menu principal se llama Digital GIS. El nombre tecnico sigue siendo `fiber_gis`, por lo que
se actualiza el modulo existente sin desinstalarlo ni cambiar sus datos.
Las pestanas Datos Dowisp y Datos CTO estan disponibles para los grupos Usuario y Responsable
del modulo. Se muestran en elementos de categoria tecnica CTO o marcados como CTO en Dowisp,
incluidos registros importados antiguos. Se mantienen las ACL y reglas de acceso a los registros.
La presentacion del mapa no cambia.

## Funcionalidad principal

- Sitios de red y elementos: OLT, ODF, CTO, cajas, splitters, arquetas, postes, ONT/CPE y otros elementos.
- Catalogo editable de arquetas con modelos habituales de operadora e ICT y medidas interiores automaticas.
- Selector compacto de iconos de mapa: en la ficha se ve solo el icono elegido y al pulsarlo se abre una ventana con la parrilla completa.
- Cables con origen, destino, color, geometria, tramos y tipo de instalacion: fachada, aereo o subterraneo.
- Trazado guiado entre elementos de red, con seleccion del tipo GIS y sin conexiones contra otros cables.
- Fibras individuales con numeracion, color normalizado, tubo, atenuacion y estado.
- Bandejas interiores por elemento, con posiciones para fibra libre, fusion o splitter.
- Splitters opticos ligados a bandejas, con entrada individual, relaciones 1:2 a 1:64, salidas numeradas y disponibilidad.
- Acometidas de cliente creadas automaticamente desde una fibra o una salida libre de splitter, con cliente, direccion y punto final en el mapa.
- Ficha especifica y simplificada para ONT con cliente en cabecera y datos de equipo, GPON, potencia optica, red, firmware y Wi-Fi.
- Trazado de fibras para diagnostico de averias, con vista en mapa e informe PDF para campo.
- Planes de despliegue previos a obra, con elementos y cables planificados, metraje, reserva e informe PDF sobre Catastro.
- Mapa con capa catastral y herramientas de zoom, desplazamiento, busqueda y edicion.
- Historial del mapa con 30 pasos para deshacer y rehacer movimientos y cambios de trazado.
- Busqueda prioritaria en el inventario y, si no hay coincidencias, busqueda de calles limitada al municipio visible.
- Seleccion prioritaria de elementos sobre los cables, con clic separado del arrastre y filtros para clientes y acometidas.
- Coordenadas y direccion automatica mediante OpenStreetMap/Nominatim, con cache local de consultas.
- Ajustes propios del modulo sin modificar los ajustes generales de Odoo.
- Copia de seguridad descargable con codigo del modulo y datos de Fiber GIS.

## Bandejas y splitters

Las bandejas se usan dentro de cajas, CTO, ODF, arquetas y equipos para ordenar y proteger fibras. En Fiber GIS cada bandeja tiene capacidad, uso principal y una lista de posiciones. Cada posicion puede ser:

- Fibra libre: una fibra queda almacenada en la bandeja sin continuidad hacia otra fibra.
- Fusion: una fibra de entrada queda conectada a una fibra de salida.
- Splitter: una fibra de entrada alimenta un reparto optico con relacion 1:N.

Campos principales: posicion, tipo, fibra de entrada, fibra de salida, relacion de splitter, perdida en dB, fecha, tecnico, estado y observaciones.

Al instalar un splitter desde el Asistente Bandejas se crea una ficha tecnica ligada al elemento y a
la bandeja. La relacion genera automaticamente sus salidas numeradas. Cada salida puede quedar libre,
reservada, conectada a una fibra de otro cable o marcada con incidencia. La ficha muestra un diagrama
con los colores de tubo y fibra, el cable y el destino remoto.

La perdida nominal propone automaticamente un valor de referencia segun la relacion del splitter:
3,7 dB (1:2), 7,1 dB (1:4), 10,4 dB (1:8), 13,7 dB (1:16), 17,0 dB (1:32) y
20,5 dB (1:64). El campo permanece editable para registrar el valor real del fabricante.

Cada salida libre de un splitter puede crear una acometida independiente. La validacion ignora el
rango del cable principal porque una salida de splitter genera siempre su propio cable monofibra.
El cable de acometida adopta automaticamente el color normalizado de la boca del splitter y conserva
ese mismo color en el mapa. La secuencia de doce colores vuelve a comenzar a partir de la boca 13.

El Asistente Bandejas tambien permite conectar una salida libre del splitter con una fibra de un
cable que continua hacia otra caja, CTO o elemento. La operacion comprueba que el cable termine en
el elemento actual, utiliza la bandeja del splitter y muestra el destino remoto en el diagrama.

El trazado de fibra sigue la senal aguas arriba. Si llega a una salida de splitter, atraviesa el
splitter por su fibra de entrada y continua por el cable anterior hasta alcanzar el origen, sin
incluir las demas ramas de salida.

La operacion `Acometida final de cliente` del Asistente Bandejas permite elegir como origen una
fibra de cable o una salida libre de splitter y solicita el contacto de destino. El modulo reutiliza
el punto final del cliente si ya existe o crea uno con su direccion y coordenadas; despues genera
automaticamente un cable monofibra clasificado como `Acometida`. En el mapa se dibuja mas fino y
termina en un icono rectangular. La ficha del splitter ofrece el mismo flujo con un boton directo.

## Estructura del codigo

- `models/asset_type.py`: tipos GIS de elementos, cables y fibras.
- `models/node_category.py`: modelos, funciones compatibles e icono/color predeterminados.
- `models/local_geocoding.py`: validacion del municipio y formato postal breve.
- `models/manhole_type.py`: catalogo de tipos de arqueta y sus medidas interiores.
- `models/site.py`: sitios de red y geocodificacion OpenStreetMap/Nominatim.
- `models/deployment_plan.py`: planes de despliegue, estimaciones y plano PDF para campo.
- `models/node.py`: elementos de red, CTO, arquetas y equipos.
- `models/port.py`: puertos de equipos.
- `models/cable.py`: cables, geometria y tramos.
- `models/fiber.py`: fibras individuales y paleta de colores.
- `models/tray.py`: bandejas, posiciones, fibra libre, fusiones y splitters.
- `models/splitter.py`: splitters opticos, puertos de salida, disponibilidad y diagrama.
- `models/splitter_drop_wizard.py`: conexion guiada de salidas de splitter con acometidas de cliente.
- `models/trace.py`: trazado de fibra, mapa resaltado e informe PDF.
- `models/link.py`: enlaces logicos.
- `models/settings.py`: ajustes del modulo, backups y mantenimiento de fibras.

## Instalacion

1. Copiar la carpeta `fiber_gis` en el directorio de addons personalizados.
2. Reiniciar Odoo.
3. Actualizar la lista de aplicaciones.
4. Instalar o actualizar `Fiber GIS - Red de Fibra`.
5. Asignar permisos a los usuarios desde los grupos de Fiber GIS.

## Uso recomendado

1. Crear un plan desde `Fiber GIS > Operacion > Planes de despliegue`.
2. Indicar zona, responsable, tecnicos, fechas y porcentaje de reserva de cable.
3. Abrir el plano de trabajo y colocar las cajas y demas elementos previstos con el boton derecho.
4. Crear los cables del plan, elegir sus extremos y ajustar el recorrido con puntos intermedios.
5. Marcar cada tramo como fachada, aereo o subterraneo y revisar el metraje calculado.
6. Comprobar los avisos de elementos sin coordenadas y cables sin trazado detallado.
7. Imprimir el PDF con Catastro, elementos numerados, direcciones, cables y metros con reserva.
8. Enviar a revision, aprobar y pasar a ejecucion cuando el proyecto se valide.
9. Tras la obra, completar bandejas, fusiones, fotos y estados reales de los elementos.
10. Crear backups desde `Fiber GIS > Configuracion > Ajustes`.

## Geocodificacion

La obtencion de coordenadas y la direccion automatica al colocar elementos usan OpenStreetMap
mediante un servicio Nominatim configurable en `Fiber GIS > Configuracion > Ajustes`. El boton
`Abrir en Google Maps` se conserva unicamente como enlace de consulta. Los resultados se guardan
en cache para evitar solicitudes repetidas.

La instancia publica de Nominatim admite como maximo una solicitud por segundo para toda la
aplicacion, exige identificar la aplicacion y no permite busquedas masivas ni autocompletado. Para
un uso intensivo debe configurarse una instancia propia o un proveedor Nominatim compatible.
Datos de geocodificacion: OpenStreetMap contributors, licencia ODbL.

- API Nominatim: https://nominatim.org/release-docs/latest/api/Search/
- Politica de uso: https://operations.osmfoundation.org/policies/nominatim/

## Arquetas

El selector `Tipo de arqueta` usa un catalogo editable desde
`Fiber GIS > Configuracion > Tipos de arqueta`. Al seleccionar un modelo se copian sus medidas
interiores en la ficha; despues pueden corregirse para reflejar las medidas reales de campo.
La lista permite crear y modificar modelos directamente; los modelos que ya no se utilicen pueden
desactivarse con el campo `Activo` sin afectar a las arquetas existentes.

El modulo incluye como base las tipologias de operadora M (40 x 40 x 62 cm), H
(80 x 70 x 82 cm) y D (109 x 90 x 100 cm), habituales en redes subterraneas, ademas de las
arquetas de entrada y de paso definidas por el Reglamento ICT. La ubicacion anterior (acera,
calzada, jardin o interior) se conserva como un dato independiente.

## Planes de despliegue

Un plan agrupa solo el trabajo previsto. Puede conectarse a elementos existentes sin convertirlos en
elementos nuevos del plan. El mapa del plan carga unicamente sus cables, sus elementos nuevos y los
puntos existentes usados como origen o destino.

El metraje dibujado se calcula con la geometria real del cable. El metraje estimado suma el porcentaje
de reserva configurado para cocas, bobina y ajustes de instalacion. Los cables que todavia sean una
linea directa entre dos elementos aparecen señalados para evitar que se use esa distancia como
medicion definitiva.

## Mapa y Catastro

El modulo carga Catastro directamente desde el servicio WMS oficial cuando se amplia el mapa. No
almacena teselas ni imagenes de Catastro en la base de datos. Durante el zoom y el desplazamiento,
el plano, los cables y los elementos se mueven juntos mediante una transformacion grafica y solo se
recalculan al terminar el gesto. La nueva imagen de Catastro sustituye a la anterior unicamente
cuando ha terminado de cargar. Primero se solicita una vista previa ligera y, cuando el mapa queda
quieto, se carga el detalle completo. La imagen se reutiliza mientras siga cubriendo la zona visible
y conserve resolucion suficiente, evitando peticiones por desplazamientos pequenos. Los elementos
alejados de la ventana visible no se dibujan hasta que entran de nuevo en el area de trabajo; en la
vista general se simplifican sus simbolos y se muestran las matriculas al ampliar.

El arrastre de elementos y puntos intermedios actualiza directamente la previsualizacion SVG a un
maximo de un cambio por fotograma. El estado reactivo y la base de datos se actualizan una sola vez
al soltar. El trazado interactivo de cables usa el mismo mecanismo y las rutas SVG ocultas se omiten
para reducir el numero de nodos graficos cuando la red contiene muchos tramos.

Los eventos de los elementos se gestionan desde el lienzo principal en lugar de crear varios
manejadores por cada registro. Esto reduce de forma importante el trabajo del navegador al mostrar
inventarios grandes. El zoom y el desplazamiento agrupan movimientos consecutivos antes de
recalcular la ventana visible. El doble clic se detecta en el lienzo y abre la ficha del elemento.
Las ventanas informativas y la sustitucion de la imagen detallada de Catastro se actualizan de forma
aislada, sin volver a construir todos los cables, elementos y etiquetas. La imagen se precarga y se
decodifica de forma asincrona antes de sustituir el plano que ya se esta mostrando.

La busqueda consulta primero sitios, elementos y cables. Solo si no encuentra coincidencias busca
calles mediante OpenStreetMap en el municipio situado en el centro del mapa. Se puede cambiar el
municipio expresamente escribiendo, por ejemplo, `Granada: Recogidas`, `Santa Fe: Real` o
`Recogidas, Granada`. Al seleccionar una calle se encaja en el mapa su extension completa conocida.

Los botones de deshacer y rehacer guardan hasta 30 operaciones de la sesion actual del mapa. El
historial incluye movimientos de sitios y elementos, desplazamiento o insercion de puntos de cable
y cambios del tipo de instalacion por tramo. Cada paso se escribe en Odoo al aplicarlo para que el
resultado visual y los datos almacenados permanezcan sincronizados.

## Informes

El informe de trazado de fibra genera un PDF sin pie de pagina estandar, con tabla de recorrido y un plano del tramo resaltado para trabajo en campo.

El informe del plan de despliegue usa Catastro como fondo, dibuja los tramos con su estilo de
instalacion, numera los elementos y añade tablas de ubicaciones, coordenadas, cables, tipologias y
metros estimados con reserva.

Los archivos ejecutables del modulo usan escapes Unicode y entidades XML para mostrar correctamente
la ñ y los acentos incluso si el paquete atraviesa herramientas que alteran la codificacion de texto.

Desde el mapa se puede trazar un cable seleccionando el elemento de origen, los puntos intermedios
del recorrido y el elemento de destino. Si el mapa pertenece a un plan de despliegue, el cable se
crea planificado y queda asociado automaticamente a ese plan.

Un doble clic sobre un sitio o un elemento de red abre directamente su ficha y conserva la posicion
y el nivel de zoom del mapa para el regreso.

Las acometidas de cliente usan el campo `x_legacy_cliente_id` de la ficha del contacto para generar
la matricula `ID-<ID cliente>` tanto en el elemento final como en el cable. Se admite el campo
estandar Referencia como respaldo. El asistente avisa si el contacto no tiene ese dato cumplimentado.

## Referencias oficiales de Odoo 19

- Modulos y manifest: https://www.odoo.com/documentation/19.0/developer/reference/backend/module.html
- ORM: https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html
- Seguridad: https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html
- Vistas: https://www.odoo.com/documentation/19.0/developer/reference/user_interface/view_records.html
- Assets: https://www.odoo.com/documentation/19.0/developer/reference/frontend/assets.html
- Framework frontend: https://www.odoo.com/documentation/19.0/developer/reference/frontend/framework_overview.html
