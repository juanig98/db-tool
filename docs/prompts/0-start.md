--- 1 fase --- 

Debemos desarrollar una aplicación de utilidad (toolkit) para trabajar con datos
Esta aplicación debe conectarse a diferentes bases de datos recogiendo, ofuscando y cargando datos según sea necesario

Principalmente, el objetivo debe ser que esta herramienta sirva a los desarrolladores tener datos de pruebas para trabajar en bases de datos no productivas (stage, desarrollo, local) copiando datos de bases productivas (ofuscando datos sensibles, eliminando datos innecesarios y demás)
Debe ser una herramienta:
- De uso rápido, para generar datos de pruebas.
- Inteligente, que pueda reconocer datos sensibles de usuarios o clientes y ofuscarlos correctamente para proceder con mecanismos que permitan mantener la correctitud de los datos (para su uso) pero sin exponer información sensible de ningún tipo.
- Mantenible, para que podamos hacer modificaciones sobre ella a medida que se requiera.
- Intuitiva y sencilla, el objetivo es hacer una herramienta de linea de comandos y crear una tui para darle facilidad de uso

Objetivos principales:
- Crear una herramienta interfaceable para poder aceptar diferentes bases de datos y migrar datos de una a la otra. Primeramente el soporte puede darse para BigQuery y Mongo DB (Cosmos DB porque se usa en Azure).
- Completamente configurable. Se debe poder configurar: 
  - Tamaños de batches en los que se realicen las copias
  - Blacklist de tablas/colecciones que se ignoraran 
  - Que tipos de copiados se harán. Ejemplo: solo datos, toda la estructura de tabla/colección (con indices, procedimientos, etc)
  - Si es necesario ofuscar datos, si no, si es necesario activar el mecanismo de reconocimiento de datos sensibles (aquí entra en juego lo de que debe ser inteligente).
- Renocer caracteristicas y funcionamientos de las bases de datos. Por ejemplo, la base de datos de productiva que utilizo es Cosmos DB que se basa en RUs para el billing y también difiere mucho del comportamiento de una base de datos Mongo DB en local como la que usamos en desarrollo (local).

Referencias:
Para poder avanzar con nuestras tareas existen dos herramientas que estoy usando de manera parcial que se encuentran en: 
- /home/juanignaciogalarza/Projects/db-tool/database/copy-collections la cual es una herramienta de copiados de colecciones de MongoDB/CosmosDB y que sirve a los fines de hacer copias totales de dichas colecciones. La uso mucho para copiar bases de datos productivas a bases de datos no productivas o locales.
- /home/juanignaciogalarza/Projects/db-tool/database/delete-collections/main.sh es un script de limpieza. Borra las colecciones de bases de datos de MongoDB/CosmosDB para luego hacer correctamente uso de la herramienta anterior

Dime que definiciones faltan
Dime que podemos avanzar o definir primero
Arma el plan de definiciones y desarrollo de una herramienta que cumpla con lo descripto 

--- 2 fase --- 


1. Modelo de configuración
- ¿Cómo se definen los perfiles de conexión? (¿YAML por perfil, .env por proyecto, vault?)
Debe existir un archivo YAML con todas las conexiones, cada "registro" deberá tener el alias, el entorno (production, stage/uat, desarrollo o local) y el connection string. Este archivo YAML debe estar ignorado del GIT para evitar subirlo.
- ¿Una config global + override por proyecto, o configs independientes?
La configuración es global, al usar la aplicación si se requieren source (DB de entrada) y/o target (DB de salida) se leerán del archivo YAML
- ¿Cómo se guardan credenciales? (keyring del sistema, vault, .env gitignoreado, otro)
YAML gitignoreado.

Un comentario sobre esto es que debe agregarse en la herramienta que cada vez que se quieran hacer modificaciones o eliminaciones sobre conexiones que se hayan definido como productivas la herramienta deba dar un mensaje de alerta y no avanzar (fallo planificado). Por otra parte, si se quieren hacer modificaciones o eliminaciones sobre conexiones definidas como stage/uat debe solicitarse confirmación.

2. Modelo de ofuscación
- ¿Qué nivel de "inteligencia" se requiere? ¿Solo detección por nombre de campo (email, phone, name) o detección semántica del contenido del documento?
En principio empecemos con Nombres propios, correos, telefonos y lo básico de contacto de cualquier usuario.
- ¿Las reglas de ofuscación son fijas o configurables por proyecto/colección?
Debe haber 2 instancias de "ofuscación". La primera sería una sección fija (nombres propios, correos, telefonos). La segunda debe ser dinamica, debe disponibilizarse un archivo txt dentro del mismo proyecto para configurar reglas (regex) de ofuscación para el contenido (configurable desde la tui).
- ¿Qué algoritmos de ofuscación: hash, fake data (Faker), nullify, tokenización reversible?
Fake data.
- ¿Necesitás consistencia referencial? (si el mismo email aparece en 3 colecciones, ¿debe ofuscarse al mismo valor en todas?)
Si esto sería un requisito fundamental

3. Scope de soporte de bases de datos
- MongoDB/CosmosDB: ya cubierto parcialmente
Estas bases de datos son principalmente el foco dado que son las de lectura/escritura para desarrollo local. BigQuery actualmente es solo lectura.
- BigQuery: ¿solo lectura de datos, o también escritura/creación de tablas?
De momento es solo lectura
- ¿CosmosDB API for MongoDB (actual) o también CosmosDB API for NoSQL?
Vamos con CosmosDB API por consistencia.
- ¿Considerás soporte futuro para Postgres/MySQL?
De momento no. Pero dejemos la puerta abierta

4. Modelo de operaciones
- ¿Las operaciones básicas son: copy, delete, obfuscate-in-place, export-to-file?
Vamos con esas de momento. Documentemos cada operación para proceder con la extensión luego.
- ¿Se puede encadenar: delete-destination → copy-from-prod → obfuscate? ¿O son siempre pasos manuales?
La idea es que se peudan seleccionar siempre ambas (origen y destino)
- ¿Se necesita un "sync" (delta, solo lo que cambió) o siempre full-copy?
Dame ejemplos de uso de sync. Y las ventajas y desventajas de ambos.

5. Comportamiento de CosmosDB
- ¿Hay limitaciones de RU que debés respetar en las lecturas de producción? ¿Necesitás throttling configurable?
Agregemoslo por las dudas
- ¿El rate limiting actual del script (batch de 1000) es suficiente o causa problemas de RU?
Que sea configurable.


Todos los valores que se determinen como configurables deberán estar en un archivo .env (como variables de entorno) y la tui debe tener una vista de configuración que permita modificar TODOS los valores configurables (y modificar el .env).

Avancemos con el desarrollo en Python usando Textual para la TUI.
Cada proceso debe tener un test definido para validar su correctitud.
Debe existir el modo --dry-run para las operaciones destructivas 

Dime que más falta definición luego de esto, en caso de que nada falte prosigamos con el plan. 
No definamos un plan hasta tener las definiciones 100% hechas

--- 3 fase --- 

1. Implementemos Sync. Usemos _id y updatedAt como valores de comparación, si alguno no existe se copia el dato.
2. Persistencia entre ejecuciones. Guardemos en archivos de mapeo que permanezcan en tmp y se borren posteriomente
3. JSONL
4. Siempre sobre destinos NO PRODUCTIVOS. JAMAS en conexiones definidas como productivas. Cuando se hace copy se debe hacer la ofuscación en memoria.
5. De momento que sean comandos separados. En la tui si quiere hacerse los 3 procesos el usuario debera acceder a los 3 botones (por ejemplo) y seleccionar cada uno de ellos.

--- 4 fase --- 

1. Hagamos un conector para MySQL que permita volcar los datos de BigQuery y trabajar en local.
2. Opcional. Si la base seleccionada es productiva se solicita confirmación en caso de que el usuario no haya "seleccionado" la opción de ofuscación.
3. Que esté en el YAML dentro del mismo grupo de la configuración de "alias", "entorno", "connection_string"
4. Mapeo de ofuscacion con comando especial (también desde la tui que permita limpiar)
4. Estado de sync: decide que es lo mejor.
5. Usemos regex para esto para mantener la uniformidad en toda la lógica

--- 5 fase ---

1. Todos los conectores deberían poder ser source o target. La implementación debe estar. No debe haber relaciones especificas de uno a otro.
2. Opción C.
3. El copy puede ser configurable. En la tui sería importante que todas las opciones se muestren al usuario antes de empezar a copiar.