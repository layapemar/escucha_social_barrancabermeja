# Proyecto de escucha social para Canal Telepetróleo


## Presentación

Desarrollé este proyecto para explorar cómo se pueden aplicar el procesamiento de lenguaje natural y el aprendizaje automático al análisis de conversaciones en redes sociales. La fuente de información es el fanpage de Facebook de Canal Telepetróleo, un medio de comunicación de Barrancabermeja.

La aplicación permite estudiar los comentarios publicados por la audiencia frente a temas de interés local, como la gestión pública, las vías, la movilidad, la seguridad, la salud o los servicios públicos. Mi propósito es organizar esa conversación y obtener una lectura descriptiva de su tono, sin presentar los resultados como una encuesta ni como la opinión de toda la ciudad.

El proyecto comenzó como un ejercicio académico con modelos preentrenados. Después lo amplié hasta convertirlo en una aplicación local hecha con Streamlit. Todo el proceso se ejecuta desde una interfaz y los comentarios se analizan en el computador.

## Qué hace la aplicación

El flujo de trabajo reúne seis pasos:

1. Definir el tema del estudio y las palabras utilizadas para buscar publicaciones.
2. Conectar la aplicación con la Página mediante un token de acceso de Meta.
3. Seleccionar las publicaciones relacionadas con la pregunta de análisis.
4. Descargar los comentarios principales disponibles mediante Meta Graph API.
5. Clasificar cada comentario como positivo, negativo o neutral.
6. Revisar los casos necesarios y generar un informe técnico en HTML.

El informe presenta la fuente, el tamaño de la muestra, el periodo observado, la distribución de sentimientos, los asuntos mencionados, algunos comentarios interrogativos, los resultados por publicación, ejemplos de comentarios y una ficha metodológica.

## Modelo utilizado

El análisis de sentimiento utiliza **RoBERTuito**, un modelo preentrenado para textos en español de redes sociales. Su arquitectura corresponde a `RobertaForSequenceClassification` y se ejecuta mediante Transformers y PyTorch.

En este proyecto realizo inferencia. El modelo recibe textos nuevos y asigna una de tres categorías: positivo, negativo o neutral. No entrené el modelo desde cero y las correcciones humanas no modifican automáticamente sus parámetros.

El resultado del modelo es una primera clasificación. El lenguaje de redes sociales contiene ironía, sarcasmo, emojis, expresiones locales y mensajes ambiguos. Por esa razón incorporé una revisión humana antes de generar el informe.

## Cómo abrir la aplicación

La forma más sencilla es hacer doble clic en:

`abrir_aplicacion.vbs`

Después de unos segundos se abrirá la dirección local:

`http://127.0.0.1:8501`

La primera carga puede tardar mientras Python prepara las bibliotecas. La aplicación funciona de manera local y debe permanecer abierta durante el análisis.

## Cómo realizar un estudio

### 1. Definir el tema

Escribo un título que identifique con claridad la pregunta del estudio. 

Luego agrego palabras o frases que puedan aparecer en las publicaciones relacionadas. Conviene incluir variantes con y sin tilde y evitar términos demasiado generales.

### 2. Conectar la Página

Pego el token de acceso de Página generado en el Explorador de la API Graph. El token debe corresponder a Canal Telepetróleo. La aplicación lo utiliza durante la sesión.


### 3. Seleccionar las publicaciones

La aplicación muestra las publicaciones que coinciden con las palabras indicadas. Reviso el texto, la fecha y la cantidad de comentarios antes de seleccionar.

Puedo elegir varias publicaciones cuando responden a la misma pregunta. La interfaz permite solicitar entre 50 y 5.000 comentarios por publicación. El valor inicial es 200. La cantidad recibida depende de lo que Meta permita consultar.

### 4. Ejecutar el análisis

Al pulsar **Descargar comentarios y analizar**, la aplicación guarda los textos disponibles y ejecuta el modelo local. El tiempo depende de la cantidad de comentarios y de la capacidad del computador.

El proyecto no solicita nombres ni enlaces a perfiles. Cada registro conserva el texto, la fecha y los identificadores técnicos de la publicación y del comentario.

### 5. Realizar la revisión humana

La predicción del modelo aparece como etiqueta inicial y también como etiqueta final provisional. Si estoy de acuerdo, no necesito hacer ningún cambio. Solo modifico la etiqueta cuando mi lectura es diferente.

Puedo registrar el motivo del cambio, por ejemplo ironía, sarcasmo, negación, crítica indirecta o contexto local. También puedo aprobar comentarios para utilizarlos como ejemplos en el informe.

Si no apruebo suficientes ejemplos, el informe selecciona de forma automática hasta tres comentarios positivos y tres negativos por publicación. Estos ejemplos se identifican para que puedan revisarse antes de compartir el documento.

### 6. Generar el informe

Al pulsar **Guardar y generar informe**, la aplicación crea un archivo llamado `informe_editorial.html` dentro de la carpeta del estudio.

El informe se puede consultar en la aplicación, descargar como HTML o guardar como PDF desde la opción de impresión del navegador. También se puede descargar un resumen en CSV para continuar el análisis en Excel.

## Cómo se organizan los archivos

Los componentes principales son:

- `app.py`: contiene la interfaz de Streamlit y coordina el proceso completo.
- `descargar_comentarios.py`: consulta las publicaciones y comentarios mediante Meta Graph API.
- `analizar_comentarios.py`: ejecuta el modelo de sentimiento.
- `resumir_revision.py`: valida las etiquetas finales y calcula los resúmenes.
- `informe_editorial.py`: genera el informe técnico en HTML.
- `test_proyecto.py`: reúne las pruebas automáticas del proyecto.
- `requirements.txt`: contiene las dependencias necesarias.
- `modelos/robertuito`: almacena el modelo utilizado para la inferencia local.
- `datos/privados/estudios`: guarda cada estudio, sus comentarios y el informe correspondiente.

La carpeta `.venv` contiene el entorno virtual de Python. No debe editarse manualmente.

## Preparación en otro computador

Si el proyecto se copia a otro equipo y no existe la carpeta `.venv`, se puede preparar desde PowerShell con:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Después se abre la aplicación con `abrir_aplicacion.vbs`.

La primera descarga del modelo requiere internet. Cuando el modelo está guardado en `modelos/robertuito`, el análisis puede ejecutarse localmente.

## Acceso a Meta

La aplicación necesita un token de acceso de Página con permisos de lectura. Para este proyecto se utilizaron los permisos `pages_show_list`, `pages_read_engagement` y `pages_read_user_content`.

El token se obtiene en el Explorador de la API Graph. Allí selecciono la aplicación registrada y luego Canal Telepetróleo en la opción de usuario o Página. La consulta `me?fields=id,name` permite comprobar que el token corresponde a la Página correcta.

No guardo el token en el código, en capturas, en documentos ni en repositorios. Si se expone o deja de funcionar, debe revocarse y generarse uno nuevo.

Meta puede cambiar los permisos, la versión de la API y los nombres de las opciones de su plataforma. Por eso esta parte del proceso puede requerir ajustes posteriores.

## Criterios para interpretar los resultados

Este es un análisis descriptivo de una muestra seleccionada. Los porcentajes se calculan sobre los comentarios descargados y no representan a todos los seguidores de la Página ni a toda la población de Barrancabermeja.

Un comentario corresponde a una observación. El proyecto no identifica personas únicas. Una misma persona podría escribir más de un comentario.

La categoría de sentimiento describe el tono general del texto. Un mensaje negativo no significa necesariamente rechazo al tema de la publicación. Puede expresar inconformidad con otra persona, recordar un hecho o responder con ironía.

Los asuntos del informe se identifican mediante un diccionario de términos. Un comentario puede mencionar varios asuntos. Esta parte es descriptiva y se encuentra separada del modelo de sentimiento.

La confianza del modelo expresa la puntuación más alta entre las tres categorías. No equivale a certeza estadística ni prueba que la interpretación sea correcta.

Para medir formalmente el desempeño del modelo en el lenguaje local sería necesario construir una muestra etiquetada por personas, separar un conjunto de evaluación y calcular métricas como exactitud, precisión, exhaustividad y F1.

## Privacidad y manejo de la información

Los comentarios pueden incluir nombres, teléfonos u otros datos escritos voluntariamente por sus autores. Antes de compartir un ejemplo, reviso su contenido y evito divulgar información sensible.

Los archivos de trabajo permanecen en `datos/privados`. Esta carpeta está excluida de Git para reducir el riesgo de publicar comentarios o identificadores por error.

La herramienta utiliza solicitudes de lectura. No publica contenido, no envía mensajes, no administra anuncios y no modifica la Página.

## Comprobación del proyecto

Las pruebas se ejecutan con:

```powershell
.\.venv\Scripts\python.exe -m unittest -q
```

Estas pruebas revisan las funciones principales sin conectarse a Facebook ni descargar nuevamente el modelo.

## Alcance académico

Este proyecto forma parte de mi proceso de aprendizaje en la Maestría en Ciencia de Datos. Me permitió integrar acceso a datos, procesamiento de texto, uso de un modelo preentrenado, revisión humana, visualización de resultados y desarrollo de una aplicación local.

La versión actual funciona como un piloto. Mi siguiente reto es evaluar el modelo con una muestra local etiquetada, estudiar con mayor detalle la ironía y el sarcasmo y mejorar la identificación de temas recurrentes.

## Referencias

- Modelo RoBERTuito: https://huggingface.co/pysentimiento/robertuito-sentiment-analysis
- Librería pysentimiento: https://github.com/pysentimiento/pysentimiento
- Explorador de Meta Graph API: https://developers.facebook.com/tools/explorer/

Laura Pérez  
Analista y científica de datos  
