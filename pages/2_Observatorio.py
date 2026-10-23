"""Flujo complementario persistente para estudios de escucha social."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as componentes
import observatorio as obs
import informe_editorial as informe
import resumir_revision as revision

BASE = Path(__file__).resolve().parents[1]
st.set_page_config(page_title='Observatorio de conversación', layout='wide')
st.title('Observatorio de conversación')
st.write('Analiza emociones, ironía, postura, peticiones, temas y evolución de un estudio guardado.')
rutas = sorted((BASE / 'datos/privados/estudios').glob('*/comentarios_analizados.csv'), reverse=True)
if not rutas:
    st.info('Crea primero un estudio desde la aplicación principal.')
    st.stop()
def nombre(p):
    tema = p.parent / 'tema.txt'
    return p.parent.name + ' · ' + (tema.read_text(encoding='utf-8') if tema.exists() else 'Sin tema')
ruta = st.selectbox('Estudio', rutas, format_func=nombre)
destino = ruta.parent / 'observatorio.json'
datos = json.loads(destino.read_text(encoding='utf-8')) if destino.exists() else None
objetivo = st.text_input('Persona, institución o acción sobre la que quieres medir postura',
    value=datos.get('objetivo', '') if datos else '', key='objetivo_' + ruta.parent.name,
    placeholder='Por ejemplo: reparación de vías en Barrancabermeja', max_chars=200)
st.caption('Usa un objetivo concreto. La primera ejecución descarga varios modelos y puede tardar. Se guardan las etapas completas para reanudar. Los textos se procesan en este computador.')
if st.button('Ejecutar o continuar análisis completo', type='primary'):
    if not objetivo.strip():
        st.error('Escribe el objetivo de la postura.')
    else:
        estado = st.empty()
        try:
            obs.ejecutar(ruta, objetivo.strip(), estado.info)
            st.rerun()
        except Exception as error:
            st.error(f'{type(error).__name__}: {error}')
            st.info('Las etapas que alcanzaron a terminar están guardadas. Puedes continuar después de resolver el error.')
if not datos:
    st.stop()
if datos['huella'] != obs.huella(ruta) or datos['objetivo'] != objetivo.strip():
    st.warning('El origen o el objetivo cambió. Ejecuta el análisis para actualizarlo. La versión anterior se archivará.')
    st.stop()
st.caption('Etapas terminadas: ' + ', '.join(datos['etapas']))
if len(datos['etapas']) < 4:
    st.info('Continúa el análisis para completar las cuatro etapas.')
    st.stop()
filas = datos['filas']
tabla = pd.DataFrame(filas)
st.subheader('Revisión de las nuevas dimensiones')
st.write('Edita únicamente lo necesario. Marca “revisada” cuando hayas comprobado una predicción, también si es correcta. Esas marcas permiten medir el acuerdo. Sin marcar, las etiquetas quedan provisionales.')
filtro = st.selectbox('Comentarios a mostrar', ['Todos', 'Prioridad alta', 'Muestra reproducible de evaluación'])
indices = list(tabla.index)
if filtro == 'Prioridad alta':
    indices = list(tabla.index[tabla.prioridad_revision == 'alta'])
elif filtro == 'Muestra reproducible de evaluación':
    indices = list(tabla.sample(n=min(50, len(tabla)), random_state=42).index)
pagina = st.number_input('Página (25 comentarios)', min_value=1, max_value=max(1, (len(indices)+24)//25), value=1)
indices = indices[(int(pagina)-1)*25:int(pagina)*25]
campos = ['comentario', 'emocion_final', 'emocion_revisada', 'ironia_final', 'ironia_revisada', 'postura_final', 'postura_revisada', 'peticion_final', 'tema_final']
config = {'comentario': st.column_config.TextColumn('Comentario', disabled=True, width='large')}
for tarea in ('emocion', 'ironia', 'postura'):
    opciones = sorted(set(tabla[tarea + '_modelo']) | set(tabla[tarea + '_final']))
    if tarea == 'emocion':
        opciones = list(obs.EMOCIONES.values())
    if tarea == 'ironia':
        opciones = ['ironic', 'not ironic']
    if tarea == 'postura':
        opciones = ['apoyo', 'rechazo', 'mixta', 'sin postura explícita', 'indeterminada']
    config[tarea + '_final'] = st.column_config.SelectboxColumn(tarea.title(), options=opciones, required=True)
    config[tarea + '_revisada'] = st.column_config.CheckboxColumn(tarea.title() + ' revisada')
config['peticion_final'] = st.column_config.SelectboxColumn('Petición', options=['petición o propuesta de acción', 'otro tipo de comentario', 'indeterminada'], required=True)
editada = st.data_editor(tabla.loc[indices, campos], column_config=config, hide_index=True,
    key=f'revision_obs_{ruta.parent.name}_{filtro}_{pagina}', num_rows='fixed', use_container_width=True)
if st.button('Guardar revisión complementaria'):
    for indice, fila in editada.iterrows():
        for campo in campos[1:]:
            valor = fila[campo]
            datos['filas'][int(indice)][campo] = bool(valor) if campo.endswith('_revisada') else str(valor)
    obs.guardar(destino, datos)
    st.success('Revisión guardada.')
    st.rerun()
st.subheader('Resultados y evaluación')
for tarea in ('emocion', 'ironia', 'postura'):
    with st.expander(tarea.title()):
        cuenta = tabla[tarea + '_final'].value_counts().rename_axis('Categoría').reset_index(name='Comentarios')
        cuenta['Porcentaje'] = (100*cuenta.Comentarios/len(tabla)).round(1)
        st.dataframe(cuenta, hide_index=True)
        st.bar_chart(cuenta.set_index('Categoría')['Porcentaje'])
        evaluacion = obs.evaluar(datos['filas'], tarea)
        st.write(f"Casos revisados: {evaluacion['revisados']}. Acuerdo: {evaluacion.get('acuerdo_porcentaje', 'sin evaluar')} %")
        if evaluacion.get('confusiones'):
            st.dataframe(evaluacion['confusiones'], hide_index=True)
st.caption('El acuerdo en casos elegidos no es una estimación independiente de precisión. Las etiquetas sin revisión permanecen provisionales.')
st.subheader('Temas y evidencia')
st.caption('Agrupación por significado. Puedes ajustar los títulos en la revisión. Un grupo requiere al menos dos textos diferentes.')
for tema, grupo in tabla.groupby('tema_final', sort=False):
    with st.expander(f'{tema} · {len(grupo)} comentarios · {100*len(grupo)/len(tabla):.1f}%'):
        st.dataframe(grupo[['comentario', 'postura_final', 'peticion_final']].head(8), hide_index=True)
st.subheader('Evolución de la muestra')
periodos, sin_fecha = obs.evolucion(datos['filas'])
st.dataframe(periodos, hide_index=True)
if len(periodos) > 1:
    st.line_chart(pd.DataFrame(periodos).set_index('periodo')[[c+'_porcentaje' for c in ('positivo','negativo','neutral')]])
else:
    st.info('Se necesitan comentarios de al menos dos meses para mostrar evolución.')
st.caption(f'Sin fecha válida: {sin_fecha}. Los meses pueden ser parciales y tener distinta selección de publicaciones.')
if st.button('Generar informe integrado con revisión guardada'):
    posts = ruta.parent / 'publicaciones.json'
    informe.crear_html(revision.leer_revision(ruta), ruta.parent / 'informe_editorial.html',
        json.loads(posts.read_text(encoding='utf-8')) if posts.exists() else [])
    st.success('Informe integrado actualizado. Puedes verlo también en la aplicación principal.')
documento = ruta.parent / 'informe_editorial.html'
if documento.exists():
    st.download_button('Descargar informe', documento.read_bytes(), 'informe_escucha_social.html', 'text/html')
st.download_button('Descargar análisis y revisión', destino.read_bytes(), 'observatorio.json', 'application/json')
