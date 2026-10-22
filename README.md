# Escucha social de una Página de Facebook

## Uso cotidiano sin terminal

La extracción de expresiones normaliza tildes para filtrar conectores y elimina
fragmentos redundantes con igual frecuencia. En revisión puedes indicar palabras
generales adicionales que quieras excluir del informe, separadas por comas.
El informe incorpora una gráfica de cantidades y porcentajes, asuntos detectados
por diccionario, evolución mensual, preguntas con signos y duplicación de textos.
Esos indicadores son exploratorios y no identifican personas ni prueban apoyo
a una autoridad, intención, coordinación o veracidad de denuncias.

El análisis reutiliza la predicción de comentarios idénticos dentro de una
ejecución y muestra progreso. La descarga reintenta errores temporales del
servidor y respuestas 429. El clasificador de sentimientos sigue siendo el mismo;
no se ha entrenado un modelo nuevo con las correcciones. Para comprobar una
mejora de precisión se necesita conservar un conjunto de evaluación humano.

Actualización editorial: la aplicación genera ahora `informe_editorial.html`,
con resultados técnicos por publicación, metodología y ejemplos. Descárgalo, ábrelo
en el navegador y usa **Imprimir o guardar como PDF** para compartirlo. Su
extensión depende de las publicaciones: no se fuerza todo a una página.
La comparación modelo/revisión se conserva en el CSV técnico, fuera del informe.

En cada página de revisión marca **Aprobar ejemplo: sí** en los comentarios que
quieras citar, después de comprobar su contexto y quitar cualquier dato personal
en una versión editorial propia. El informe conserva las citas originales;
si contienen datos sensibles no las apruebes. Muestra hasta dos ejemplos
positivos y dos negativos aprobados por publicación. Guarda antes de cambiar
de página. La columna **Revisar con atención** usa reglas orientativas, no un
modelo de sarcasmo. Las expresiones recurrentes cuentan comentarios que contienen
palabras o secuencias repetidas; no agrupan sinónimos ni detectan personas.

Los nuevos estudios guardan el texto de las publicaciones. En estudios antiguos
que no lo guardaron, el informe mostrará su identificador y explicará la ausencia.
El máximo de descarga se puede elegir entre 50 y 5.000 comentarios por publicación;
no implica que la API vaya a entregar esa cantidad ni una garantía de rendimiento.

Haz doble clic en `abrir_aplicacion.vbs`. Se abrirá una página local en el
navegador. Si Windows pregunta si deseas ejecutar el archivo, comprueba que
está dentro de esta carpeta del proyecto. La primera apertura puede tardar.

En la aplicación:

1. Escribe un tema y palabras de búsqueda separadas por comas.
2. Pega el token de **Página** de Canal Telepetróleo en el campo oculto.
3. Marca las publicaciones que realmente correspondan a la pregunta.
4. Pulsa **Descargar comentarios y analizar**.
5. Revisa la etiqueta de cada comentario. Puedes copiar las predicciones
   iniciales a las casillas vacías y corregirlas. En **Motivo del cambio**
   anota, cuando corresponda, `ironía`, `sarcasmo`, `crítica indirecta` u otro
   motivo que hayas observado. Pulsa **Guardar revisión** para continuar luego.
6. Cuando no haya pendientes, pulsa **Guardar y generar informe**. Podrás
   descargar el PNG y el resumen CSV.

Cada análisis queda en una carpeta independiente dentro de
`datos/privados/estudios`. En la barra lateral puedes retomarlo. El token solo
se utiliza en la sesión actual y no se escribe en esos archivos. La primera
vez debes haber instalado las dependencias con la Parte A de este documento.

La búsqueda examina hasta 2.000 publicaciones recientes y descarga hasta 200
comentarios principales con texto por publicación. Esos límites pertenecen a
esta primera versión. Si una publicación muestra más comentarios en Facebook,
el análisis puede abarcar solo los descargados por la API.

Proyecto académico para clasificar comentarios en español con RoBERTuito.
No modifica el proyecto del taller de Transformers. No se necesita clonar un
repositorio ajeno: los programas de este proyecto ya están en esta carpeta.

## Qué hace y qué no hace

1. `descargar_comentarios.py` consulta la API oficial de Meta y guarda hasta 200
   comentarios con texto de una publicación de tu propia Página. Requiere un
   token de acceso de Página y el ID numérico de la Página. No extrae nombres.
2. `analizar_comentarios.py` lee el CSV y clasifica cada comentario como
   `POS`, `NEG` o `NEU`. Produce un archivo detallado y un resumen por tema.
3. Los resultados son una primera lectura del tono del texto. No miden por sí
   solos apoyo o rechazo a una política, persona o noticia, ni representan a
   todos los habitantes de Barrancabermeja.

Esta primera versión trabaja con comentarios principales, no respuestas a
comentarios, y con una publicación por descarga. Un comentario que contenga
solo una foto o video no entra en el análisis de texto.

## Parte A. Preparar VS Code en Windows

1. Abre VS Code. Ve a `File > Open Folder` y elige esta carpeta:
   `C:\Users\LAURA PEREZ\Documents\Codex\2026-10-19\quie\escucha_social_barrancabermeja`.
   Es un proyecto distinto de la carpeta anterior `Proyecto_Transformers`.
2. Abre `Terminal > New Terminal`.
3. Este proyecto ya tiene el entorno `.venv` preparado. No necesitas activar
   Conda ni instalar todo otra vez. Comprueba que VS Code está situado en esta
   carpeta y escribe:

   ```powershell
   .\.venv\Scripts\python.exe --version
   .\.venv\Scripts\python.exe -m pip show pysentimiento
   ```

   Debe aparecer Python 3.13 y la ficha de `pysentimiento`. En VS Code puedes
   pulsar `Ctrl+Shift+P`, escribir `Python: Select Interpreter` y elegir el
   Python dentro de `.venv`. Aunque no lo selecciones, los comandos de este
   documento usan directamente el intérprete correcto.

4. Si llevas esta carpeta a otro computador y `.venv` no existe, entonces sí
   crea un entorno e instala las dependencias:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   La instalación puede tardar varios minutos por PyTorch.

## Parte B. Probar primero con comentarios inventados

En la terminal, situada en esta carpeta, ejecuta:

```powershell
.\.venv\Scripts\python.exe analizar_comentarios.py datos/ejemplo_comentarios.csv
```

Este proyecto busca primero el modelo verificado en `modelos/robertuito`. Si
no está allí, intenta descargarlo desde Hugging Face y necesitas internet. El
archivo de pesos ocupa aproximadamente 435 MB.
Al terminar, abre `resultados/comentarios_analizados.csv` y
`resultados/resumen_por_tema.csv`. El ejemplo es inventado y sirve solamente
para comprobar el funcionamiento. La carpeta `resultados` no se sube a Git.

## Parte C. Obtener acceso a tu Página

1. En Facebook comprueba que tu perfil tiene acceso a la Página: entra en la
   Página, abre `Configuración > Acceso a la página`. Los nombres de menú pueden
   cambiar ligeramente. Si no tienes acceso suficiente, quien administre la
   Página debe concedértelo. Nunca entregues la contraseña a este proyecto.
2. Abre [Meta for Developers](https://developers.facebook.com/) con tu propia
   sesión de Facebook. Regístrate como desarrolladora si Meta te lo solicita.
3. En [Mis apps](https://developers.facebook.com/apps/) crea una app. La
   interfaz cambia con frecuencia: elige el caso de uso que permita acceder a
   una Página que administras o administrar Páginas. No marques permisos de
   publicación, mensajes privados ni anuncios para este ejercicio de lectura.
4. Abre el [Explorador de la API Graph](https://developers.facebook.com/tools/explorer/).
   Selecciona tu app. Añade `pages_show_list`, `pages_read_engagement` y
   `pages_read_user_content` si Meta los presenta. Genera un **token de usuario**
   y acepta únicamente la Página pertinente.
5. Para este proyecto ya se confirmó el acceso a **Canal Telepetróleo**.
   En `Usuario o página`, elige `Canal Telepetróleo` en la sección de tokens
   de acceso a la página. No elijas `Token del usuario`: para descargar
   comentarios el programa necesita el **token de Página**.
6. En el explorador, con el token de Página seleccionado, consulta
   `me?fields=id,name`. Debe aparecer `Canal Telepetróleo` y el identificador
   `124142061045473`. Ese es el ID que solicita el programa. Después puedes
   probar `me/posts?fields=id,message,created_time&limit=2` y, para una
   publicación que tenga comentarios, `ID_DEL_POST/comments?fields=id,message,created_time&limit=2`.
   El 21 de octubre de 2026 ambas lecturas se verificaron en el explorador.
7. Para ejecutar el programa, pulsa el icono de copiar junto al token de
   Página en el explorador y pégalo **solo** cuando la terminal lo solicite.
   No lo publiques, no lo pegues en el chat, no lo incluyas en capturas ni lo
   guardes en archivos del proyecto. El token puede caducar o revocarse.

Nota: en este caso `me/accounts` respondió con `data: []` usando el token de
usuario, aunque la Página estaba marcada en la autorización. La selección del
token de Página desde el menú del explorador sí funcionó. No hace falta repetir
`me/accounts` si el menú ya muestra `Canal Telepetróleo`.

Para diagnosticar el portafolio empresarial se solicitó, con autorización de
la propietaria, `business_management`. Es un permiso más amplio que los tres
de lectura iniciales. Este programa **no lo usa para modificar activos** y
solo realiza solicitudes `GET`; cuando termine el piloto, conviene revisar o
revocar la integración desde la configuración de Facebook y generar un token
nuevo para cualquier uso posterior.

Meta puede modificar nombres de botones, requisitos de revisión y permisos.
Las instrucciones de esta parte son una ruta de orientación, no garantía de
aprobación. Para una app usada solamente por sus administradores en desarrollo,
las condiciones pueden ser distintas a las de una app ofrecida al público.

## Parte D. Descargar comentarios de una noticia

En la terminal, con el entorno activo, escribe:

```powershell
.\.venv\Scripts\python.exe descargar_comentarios.py
```

El programa te pedirá, en este orden:

1. Token de Página. Al pegarlo no aparecerán caracteres; eso es normal.
2. ID numérico de la Página. Para Canal Telepetróleo, pulsa `Enter` y el
   programa usará el ID ya verificado.
3. Tema breve de la noticia, por ejemplo `movilidad`.
4. Palabras para buscar. Para el tema de vías puedes pulsar `Enter` y usar la
   lista sugerida. El programa revisa hasta 2.000 publicaciones recientes y
   muestra las que contienen expresiones concretas como recuperación vial,
   pavimentación, rehabilitación, malla vial u obras viales.
5. Uno o varios números de las publicaciones encontradas. El programa muestra
   la cantidad de comentarios y permite escribir, por ejemplo, `2,5,8` para
   reunir varias noticias del mismo tema en un solo archivo. Lee cada fragmento
   y elige solamente publicaciones que respondan a la misma pregunta de estudio.

Al terminar verás un archivo CSV dentro de `datos/privados`. Solo se solicita
texto, fecha e identificadores de publicación y comentario. Aunque no se pidan
nombres, los textos pueden contener datos personales; no compartas el CSV sin
revisión y elimina información sensible antes de citar ejemplos.

## Parte E. Analizar comentarios reales

Sustituye el nombre de archivo por el que haya creado la parte D:

```powershell
.\.venv\Scripts\python.exe analizar_comentarios.py "datos/privados/comentarios_ID-DEL-POST.csv"
```

Abre el resultado en Excel o VS Code. En `revision_humana` escribe tu criterio
para una muestra de comentarios, especialmente cuando haya ironía, ambigüedad,
negación o mezcla de sentimientos. No publiques una cifra sin indicar el
número de comentarios analizados, la publicación, el periodo y este proceso
de revisión.

Cuando termines de revisar **todas** las filas, guarda y cierra el archivo en
Excel. Después vuelve a la terminal y ejecuta:

```powershell
.\.venv\Scripts\python.exe resumir_revision.py
```

El programa comprueba que no haya revisiones vacías ni etiquetas diferentes de
`positivo`, `negativo` o `neutral`. Luego crea dos archivos nuevos sin borrar
el análisis original:

- `resultados/resumen_revision_humana.csv`: resultado final corregido,
  porcentajes y nivel de coincidencia entre el modelo y la revisión humana.
- `resultados/comparacion_modelo_revision.csv`: cantidad de comentarios que
  pasaron de cada etiqueta automática a cada etiqueta humana. Esta tabla ayuda
  a reconocer fallos repetidos, por ejemplo ironías clasificadas como neutrales.

La columna `revision_humana` es la decisión final para este piloto. Las
probabilidades y la etiqueta del modelo se conservan como evidencia de lo que
predijo originalmente, no se reemplazan.

## Parte F. Generar el informe técnico

En la aplicación local, completa las correcciones necesarias y pulsa
`Guardar y generar informe`. El sistema crea `informe_editorial.html` dentro
de la carpeta del estudio. Este es el único informe final del proyecto.

El documento presenta la fuente, la muestra, el periodo, la distribución de
sentimientos, los asuntos detectados, los resultados por publicación, ejemplos
de comentarios y la ficha metodológica. Puede descargarse como HTML o imprimirse
como PDF desde el navegador.

Si Windows muestra el error 1455 indicando que el archivo de paginación es
demasiado pequeño, el CSV no se ha perdido. Guarda tu trabajo, cierra el
navegador y otras aplicaciones que consuman memoria o reinicia el equipo. Abre
solo VS Code con este proyecto y repite el comando de análisis; no es necesario
volver a descargar los comentarios ni generar otro token.

### Si Meta todavía no concede el acceso a la API

Puedes hacer un piloto pequeño de forma manual, sin extensiones de extracción:
abre `datos/ejemplo_comentarios.csv` en Excel, guarda una copia como
`datos/privados/muestra_manual.csv` con codificación UTF-8 y reemplaza las
frases inventadas por una muestra de comentarios visibles de una noticia de
tu Página. Conserva las columnas `tema` y `comentario`. En `fecha`, `post_id`
y `comment_id` puedes dejar las celdas vacías. No copies nombres ni enlaces a
perfiles. Luego ejecuta:

```powershell
.\.venv\Scripts\python.exe analizar_comentarios.py datos/privados/muestra_manual.csv
```

Esta vía permite validar el análisis, pero no sustituye una extracción
sistemática mediante la API si el proyecto crece.

## Seguridad y límites

- El token se introduce en la terminal y solo permanece en la memoria del
  proceso. Si se filtra, revócalo desde Meta.
- `datos/privados` y `resultados` están excluidos de Git. No publiques
  comentarios identificables ni claves en GitHub.
- Usa únicamente contenido al que tu cuenta y la API oficial tengan acceso.
  No uses extensiones de extracción masiva o técnicas para evadir restricciones.
- El modelo y `pysentimiento` tienen condiciones de uso no comercial y de
  investigación; revisa la licencia antes de ampliar el uso fuera del piloto.
- Las puntuaciones del modelo no son una garantía de verdad ni una encuesta.

## Fuentes

- Modelo: https://huggingface.co/pysentimiento/robertuito-sentiment-analysis
- Código y licencia: https://github.com/pysentimiento/pysentimiento
- Explorador de Meta: https://developers.facebook.com/tools/explorer/
- Acceso a la Página: https://www.facebook.com/help/510247025775149/
