"""Profundización de un estudio sin repetir la extracción de comentarios."""
import json
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as componentes

import enfoques as enf
import observatorio as obs
import informe_editorial as informe
import resumir_revision as revision

BASE = Path(__file__).resolve().parents[1]
st.set_page_config(page_title='Personas y enfoques', layout='wide')
st.title('Personas y enfoques del estudio')
st.write('Profundiza en una persona, institución, acción o tema usando los comentarios ya descargados. Define libremente el aspecto que quieres analizar y guarda cada enfoque por separado.')
rutas = sorted((BASE / 'datos/privados/estudios').glob('*/comentarios_analizados.csv'), reverse=True)
if not rutas:
    st.info('Crea primero un estudio desde la aplicación principal.')
    st.stop()


def nombre(p):
    tema = p.parent/'tema.txt'
    return p.parent.name+' · '+(tema.read_text(encoding='utf-8') if tema.exists() else 'Sin tema')


solicitado = st.session_state.get('estudio_observatorio', '')
indice = next((i for i,p in enumerate(rutas) if str(p) == solicitado), 0)
ruta = st.selectbox('Estudio de origen', rutas, format_func=nombre, index=indice)
firma = obs.huella(ruta)
filas = enf.registros(ruta)
prefijo = ruta.parent.name
st.caption(f'Base del estudio: {len(filas)} comentarios. La selección por persona se comprueba antes de ejecutar la postura.')

with st.expander('1. Crear un análisis por persona y pregunta', expanded=True):
    with st.form('nuevo_enfoque_'+prefijo):
        persona = st.text_input('Persona, institución, acción o tema', placeholder='Por ejemplo: servicio de agua, recuperación vial o una institución', max_chars=150)
        alias = st.text_input('Nombres alternativos o expresiones para encontrar referencias, separados por comas',
                             placeholder='Por ejemplo: acueducto, suministro de agua, servicio de agua')
        enfoque = st.text_area('Qué quieres conocer',
            placeholder='Por ejemplo: valoración de la calidad del servicio, inconformidad por demoras o aceptación de una medida', max_chars=250)
        perfil = st.selectbox('Modelo para este análisis', list(obs.PERFILES_POSTURA))
        crear = st.form_submit_button('Crear análisis y buscar menciones')
    st.caption('El enfoque es libre y orienta la clasificación de postura. Los resultados son apoyo, rechazo, postura mixta, ausencia de postura o indeterminación; no responde automáticamente cualquier pregunta de investigación. Revisa las referencias encontradas y añade manualmente las alusiones indirectas.')
    if crear:
        try:
            a = enf.crear(ruta, persona, alias.split(','), enfoque, modelo=obs.PERFILES_POSTURA[perfil])
            st.session_state['enfoque_activo_'+prefijo] = a['id']
            st.rerun()
        except Exception as error:
            st.error(str(error))

catalogo = enf.cargar(ruta)
actuales = [a for a in catalogo['analisis'] if a['huella'] == firma]
historicos = len(catalogo['analisis'])-len(actuales)
if historicos:
    st.caption(f'Análisis de versiones anteriores del archivo conservados: {historicos}. Se excluyen de las comparaciones actuales.')
if not actuales:
    st.info('Crea un enfoque indicando el tema y qué aspecto quieres conocer. Puedes analizar servicios, obras, instituciones, personas o situaciones, y comparar después los resultados de preguntas equivalentes.')
    st.stop()
ids = [a['id'] for a in actuales]
activo = st.session_state.get('enfoque_activo_'+prefijo, ids[0])
id_actual = st.selectbox('Análisis guardado', ids,
    index=ids.index(activo) if activo in ids else 0,
    format_func=lambda k: next(a['persona']+' · '+a['enfoque']+' · '+a['estado']+' · '+k[:6] for a in actuales if a['id']==k))
a = enf.obtener(catalogo, id_actual)
clave = prefijo+'_'+id_actual
st.write(f'Objetivo: **{a["objetivo"]}**')

with st.expander('2. Confirmar comentarios relacionados', expanded=a['estado'] != 'completo'):
    st.write('La selección inicial incluye coincidencias con el nombre y los alias. Examina cada texto y ajusta la casilla Incluir. Puedes buscar el nombre de otra persona para excluirlo, o una alusión indirecta para añadirla.')
    vista = st.selectbox('Mostrar', ['Todos', 'Seleccionados', 'Sin seleccionar'], key='vista_'+clave)
    buscar = st.text_input('Buscar dentro de los comentarios', key='buscar_'+clave)
    seleccion = set(a['seleccion'])
    visibles = [f for f in filas if (not buscar.strip() or enf.normalizar(buscar) in enf.normalizar(f['comentario']))
                and (vista == 'Todos' or (f['registro'] in seleccion) == (vista == 'Seleccionados'))]
    n_pagina = st.number_input('Página de selección (50 comentarios)', min_value=1,
                              max_value=max(1, (len(visibles)+49)//50), value=1, key='pag_'+clave+'_'+vista+'_'+buscar)
    lote = visibles[(int(n_pagina)-1)*50:int(n_pagina)*50]
    tabla_seleccion = pd.DataFrame([dict(registro=f['registro'], incluir=f['registro'] in seleccion,
        comentario=f['comentario'], coincidencia=', '.join(a['coincidencias'].get(f['registro'],[])) or 'Sin nombre o alias coincidente') for f in lote],
        columns=['registro','incluir','comentario','coincidencia'])
    editada = st.data_editor(tabla_seleccion, hide_index=True, width='stretch',
        disabled=['registro','comentario','coincidencia'],
        column_config={'registro':None, 'incluir':st.column_config.CheckboxColumn('Incluir'),
                       'comentario':st.column_config.TextColumn('Comentario', width='large'),
                       'coincidencia':st.column_config.TextColumn('Referencia encontrada')},
        key='seleccion_'+clave+'_'+vista+'_'+buscar+'_'+str(n_pagina))
    if st.button('Guardar selección de esta página', key='guardar_sel_'+clave):
        for f in editada.to_dict('records'):
            if f['incluir']:
                seleccion.add(f['registro'])
            else:
                seleccion.discard(f['registro'])
        enf.seleccionar(ruta, id_actual, seleccion)
        st.rerun()
    st.caption(f'{len(a["seleccion"])} seleccionados de {len(filas)} comentarios. Guarda los cambios de cada página antes de continuar.')
    confirmar = st.checkbox('He comprobado los comentarios seleccionados y confirmo que son pertinentes para este análisis',
                            value=a['seleccion_confirmada'], key='confirmar_'+clave)
    if st.button('Confirmar selección guardada', key='confirmar_sel_'+clave):
        enf.seleccionar(ruta, id_actual, a['seleccion'], confirmada=confirmar)
        st.rerun()

st.subheader('3. Analizar y revisar la postura específica')
st.caption('Puedes ejecutar este análisis sin completar el Observatorio general. Los resultados de sentimiento del estudio original se conservan.')
if st.button('Ejecutar o continuar este enfoque', type='primary', disabled=not a['seleccion_confirmada'] or not a['seleccion']):
    estado = st.empty()
    try:
        enf.ejecutar(ruta, id_actual, estado.info)
        st.rerun()
    except Exception as error:
        st.error(f'{type(error).__name__}: {error}')
        st.info('Los comentarios procesados están guardados. Puedes continuar después.')
if a['filas']:
    st.caption(f'Estado: {a["estado"]}. Procesados: {len(a["filas"])}/{len(a["seleccion"])}. Las predicciones se refieren exclusivamente al objetivo indicado arriba.')
    pagina = st.number_input('Página de revisión (25 comentarios)', min_value=1,
        max_value=max(1,(len(a['filas'])+24)//25), value=1, key='revpag_'+clave)
    lote = a['filas'][(int(pagina)-1)*25:int(pagina)*25]
    revision_tabla = pd.DataFrame([{k:f.get(k) for k in ('registro','comentario','postura_modelo','postura_final','postura_revisada','nota_revision')} for f in lote])
    revisada = st.data_editor(revision_tabla, hide_index=True, width='stretch',
        disabled=['registro','comentario','postura_modelo'], column_config={
            'registro':None, 'comentario':st.column_config.TextColumn('Comentario',width='large'),
            'postura_modelo':st.column_config.TextColumn('Modelo'),
            'postura_final':st.column_config.SelectboxColumn('Postura final',options=enf.ETIQUETAS,required=True),
            'postura_revisada':st.column_config.CheckboxColumn('Revisada'),
            'nota_revision':st.column_config.TextColumn('Motivo o contexto')}, key='revisar_'+clave+'_'+str(pagina))
    if st.button('Guardar revisión de este enfoque', key='guardar_rev_'+clave):
        enf.revisar(ruta,id_actual,{f['registro']:f for f in revisada.to_dict('records')})
        st.rerun()
    st.caption('Corrige únicamente los errores. Una etiqueta modificada se registra como revisada; marca también las correctas que hayas comprobado. Cada enfoque conserva sus propias correcciones.')

st.subheader('4. Comparación e informe del estudio')
completos = enf.vigentes(ruta)
if completos:
    for enfoque_nombre in dict.fromkeys(x['enfoque'] for x in completos):
        st.write('**'+enfoque_nombre+'**')
        tabla = pd.DataFrame([enf.resumen(x) for x in completos if x['enfoque']==enfoque_nombre])
        st.dataframe(tabla, hide_index=True, width='stretch')
    componentes.html(enf.seccion_html(ruta), height=800, scrolling=True)
    st.caption('Cada resultado tiene su propia base. Un comentario puede pertenecer a varias personas. La selección automática de menciones no mide notoriedad fuera de las publicaciones elegidas. Las puntuaciones no están calibradas como certeza.')
    if st.button('Generar informe con todos los enfoques guardados'):
        try:
            posts = ruta.parent/'publicaciones.json'
            informe.crear_html(revision.leer_revision(ruta), ruta.parent/'informe_editorial.html',
                json.loads(posts.read_text(encoding='utf-8')) if posts.exists() else [])
            st.success('Informe actualizado con los enfoques completos de este estudio.')
        except Exception as error:
            st.error(str(error))
    reporte = ruta.parent/'informe_editorial.html'
    if reporte.exists():
        st.download_button('Descargar informe del estudio',reporte.read_bytes(),'informe_escucha_social.html','text/html')
else:
    st.info('Los análisis completos aparecerán aquí, agrupados por pregunta para facilitar su comparación.')
st.download_button('Descargar enfoques y revisiones',json.dumps(catalogo,ensure_ascii=False,indent=2),
                   'enfoques_del_estudio.json','application/json')
