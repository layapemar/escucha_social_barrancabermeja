"""Interfaz local para realizar un estudio completo sin usar la terminal."""

import csv
import json
import importlib
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import analizar_comentarios as analisis
import descargar_comentarios as facebook
import resumir_revision as revision
import informe_editorial as editorial
import streamlit.components.v1 as componentes


BASE = Path(__file__).resolve().parent
ESTUDIOS = BASE / "datos" / "privados" / "estudios"
ETIQUETAS = ["positivo", "negativo", "neutral"]


def nuevo_estudio(tema: str) -> Path:
    marca = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destino = ESTUDIOS / marca
    destino.mkdir(parents=True, exist_ok=False)
    (destino / "tema.txt").write_text(tema, encoding="utf-8")
    return destino


def escribir_csv(ruta: Path, filas: list[dict]) -> None:
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)


def estudios_anteriores() -> list[Path]:
    if not ESTUDIOS.is_dir():
        return []
    return sorted(
        (carpeta for carpeta in ESTUDIOS.iterdir()
         if carpeta.is_dir() and (carpeta / "comentarios_analizados.csv").is_file()),
        reverse=True,
    )


st.set_page_config(page_title="Escucha Social Telepetróleo", page_icon="📰", layout="wide")
st.title("Escucha Social · Canal Telepetróleo")
st.caption("De las publicaciones al informe, con una revisión editorial antes de publicar.")

for nombre, valor in {"fase": "inicio", "publicaciones": [], "estudio": None}.items():
    if nombre not in st.session_state:
        st.session_state[nombre] = valor

# Enlaces directos solo a estudios locales ya guardados.
informe_solicitado = st.query_params.get('informe', '')
if informe_solicitado and st.session_state.get('enlace_abierto') != informe_solicitado:
    disponibles = {p.name: p for p in estudios_anteriores()}
    if informe_solicitado in disponibles:
        st.session_state.estudio = disponibles[informe_solicitado]
        st.session_state.fase = 'informe'
        st.session_state.enlace_abierto = informe_solicitado

if st.session_state.estudio and not Path(st.session_state.estudio).is_dir():
    st.session_state.estudio = None
    st.session_state.fase = 'inicio'
    st.info('El estudio anterior fue retirado. Puedes comenzar un análisis nuevo.')

with st.sidebar:
    st.header("Estudios guardados")
    anteriores = estudios_anteriores()
    if anteriores:
        seleccionado = st.selectbox(
            "Retomar un estudio",
            [None] + anteriores,
            format_func=lambda ruta: "Selecciona un estudio" if ruta is None else
            f"{ruta.name[:15]} · {(ruta / 'tema.txt').read_text(encoding='utf-8') if (ruta / 'tema.txt').is_file() else 'Sin tema'}",
        )
        if seleccionado and st.button("Abrir estudio"):
            st.session_state.estudio = seleccionado
            st.session_state.fase = "revision"
            st.rerun()
        if seleccionado and (seleccionado / 'informe_editorial.html').is_file() and st.button('Ver informe actualizado'):
            st.session_state.estudio = seleccionado
            st.session_state.fase = 'informe'
            st.rerun()
    if st.button("Empezar otro tema"):
        st.session_state.fase = "inicio"
        st.session_state.publicaciones = []
        st.session_state.estudio = None
        st.session_state.pop("token", None)
        st.rerun()

if st.session_state.fase == "inicio":
    st.subheader("1. Define el tema y conecta la Página")
    tema = st.text_input(
        "Tema del estudio",
        placeholder="Por ejemplo: percepción ciudadana sobre la atención en salud",
        max_chars=180,
        help="Este texto será el título del informe. El límite amplio evita títulos cortados, pero conviene escribirlo de forma clara y concreta.",
    )
    terminos = st.text_area(
        "Palabras o frases para encontrar publicaciones",
        placeholder="hospital, urgencias, centro de salud",
        help="Sepáralas con comas. El programa busca estas expresiones en el texto de las publicaciones.",
    )
    token = st.text_input("Token de acceso de Página de Meta", type="password",
                          help="Se usa durante esta sesión y no se guarda en archivos.")
    if st.button("Buscar publicaciones", type="primary"):
        palabras = [p.strip() for p in terminos.split(",") if p.strip()]
        if not tema.strip() or not palabras or not token.strip():
            st.error("Completa el tema, al menos una palabra de búsqueda y el token.")
        else:
            try:
                with st.spinner("Verificando la Página y buscando publicaciones. Puede tardar unos minutos..."):
                    identidad = facebook.consultar("me", token.strip(), {"fields": "id,name"})
                    if str(identidad.get("id")) != facebook.PAGINA_ID_PREDETERMINADA:
                        raise ValueError("El token debe corresponder a Canal Telepetróleo.")
                    posts = facebook.buscar_publicaciones(
                        token.strip(), facebook.PAGINA_ID_PREDETERMINADA, palabras
                    )
                st.session_state.token = token.strip()
                st.session_state.tema = tema.strip()
                st.session_state.publicaciones = posts
                st.session_state.fase = "seleccion"
                st.rerun()
            except Exception as error:
                st.error(str(error).replace(token.strip(), "[token oculto]"))

if st.session_state.fase == "seleccion":
    st.subheader("2. Elige las publicaciones")
    posts = st.session_state.publicaciones
    st.write(f"Tema: **{st.session_state.tema}** · Coincidencias: **{len(posts)}**")
    if not posts:
        st.info("No hubo coincidencias. Cambia las palabras de búsqueda e inténtalo de nuevo.")
    else:
        opciones = {
            post["id"]: f"{post.get('created_time', '')[:10]} · "
            f"{post.get('comments', {}).get('summary', {}).get('total_count', '?')} comentarios · "
            f"{' '.join(post.get('message', '[sin texto]').split())[:200]}"
            for post in posts
        }
        ids = st.multiselect("Publicaciones para analizar", list(opciones),
                             format_func=lambda clave: opciones[clave])
        limite = st.number_input('Máximo de comentarios por publicación', min_value=50, max_value=5000, value=200, step=50)
        st.caption('Solo comentarios principales accesibles por la API. Más volumen requiere más tiempo de análisis y revisión.')
        if st.button("Descargar comentarios y analizar", type="primary", disabled=not ids):
            try:
                with st.spinner("Descargando y clasificando. El modelo puede tardar al cargar..."):
                    filas = []
                    for post_id in ids:
                        filas.extend(facebook.descargar(st.session_state.token, post_id, int(limite)))
                    if not filas:
                        raise ValueError("Las publicaciones elegidas no devolvieron comentarios con texto.")
                    for fila in filas:
                        fila["tema"] = st.session_state.tema
                    destino = nuevo_estudio(st.session_state.tema)
                    (destino / 'publicaciones.json').write_text(json.dumps([p for p in posts if p['id'] in ids], ensure_ascii=False), encoding='utf-8')
                    escribir_csv(destino / "comentarios_originales.csv", filas)
                    avance = st.progress(0, text='Cargando el modelo...')
                    analizadas = analisis.analizar(filas, progreso=lambda n,total: avance.progress(n/total, text=f'Analizados {n} de {total} comentarios'))
                    escribir_csv(destino / "comentarios_analizados.csv", analizadas)
                st.session_state.estudio = destino
                st.session_state.fase = "revision"
                st.session_state.pop("token", None)
                st.rerun()
            except Exception as error:
                st.error(str(error).replace(st.session_state.get("token", ""), "[token oculto]"))

if st.session_state.fase == "revision":
    st.subheader("3. Revisa las etiquetas")
    destino = Path(st.session_state.estudio)
    detalle = destino / "comentarios_analizados.csv"
    tabla = pd.read_csv(detalle, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    if 'ejemplo_publicar' not in tabla:
        tabla['ejemplo_publicar'] = ''
    # En esta interfaz, no modificar una etiqueta significa aceptar la
    # predicción del modelo. Esto permite concentrar el trabajo humano en los
    # errores, ironías, ambigüedades y casos sensibles.
    sin_etiqueta = ~tabla['revision_humana'].isin(revision.ETIQUETAS_VALIDAS)
    tabla.loc[sin_etiqueta, 'revision_humana'] = tabla.loc[sin_etiqueta, 'interpretacion_inicial']
    tabla['prioridad'] = [editorial.alerta(fila) for fila in tabla.to_dict('records')]
    st.write(f"**{len(tabla)} comentarios.** La etiqueta del modelo ya está aceptada como punto de partida.")
    st.info("Solo cambia **Etiqueta final** cuando consideres que el modelo se equivocó. No necesitas ratificar las etiquetas correctas.")
    st.caption('Revisa con especial atención ironías, sarcasmos, emojis y frases ambiguas. Marca «sí» únicamente en ejemplos que hayas leído y puedas publicar sin datos personales.')
    st.warning('Guarda los cambios antes de pasar a otra página de revisión.')
    por_pagina = st.selectbox('Comentarios por página', [25, 50, 100])
    pagina = st.number_input('Página de revisión', min_value=1, max_value=max(1, (len(tabla)+por_pagina-1)//por_pagina), value=1)
    indices = list(tabla.index[(int(pagina)-1)*por_pagina:int(pagina)*por_pagina])
    vista = tabla.loc[indices, ["comentario", "interpretacion_inicial", "revision_humana", "prioridad", "observaciones", "ejemplo_publicar"]].copy()
    editada = st.data_editor(
        vista, hide_index=False, width="stretch", num_rows="fixed", key=f"editor_{destino.name}_{pagina}_{por_pagina}",
        column_config={
            "comentario": st.column_config.TextColumn("Comentario", disabled=True, width="large"),
            "interpretacion_inicial": st.column_config.TextColumn("Modelo", disabled=True),
            "revision_humana": st.column_config.SelectboxColumn("Etiqueta final", options=ETIQUETAS, required=True),
            'prioridad': st.column_config.TextColumn('Alerta', disabled=True),
            "observaciones": st.column_config.TextColumn("Motivo, solo si cambió", width="medium"),
            'ejemplo_publicar': st.column_config.SelectboxColumn('Aprobar ejemplo', options=['', 'sí']),
        },
    )
    tabla.loc[indices, 'revision_humana'] = editada['revision_humana']
    tabla.loc[indices, 'observaciones'] = editada['observaciones'].fillna('')
    tabla.loc[indices, 'ejemplo_publicar'] = editada['ejemplo_publicar'].fillna('')
    cambios = sum(
        final != inicial
        for final, inicial in zip(tabla['revision_humana'], tabla['interpretacion_inicial'])
    )
    st.success(f"Cambios humanos registrados: {cambios}. Las demás etiquetas conservarán la predicción del modelo.")
    col1, col2 = st.columns(2)
    guardar = col1.button("Guardar revisión", type="primary")
    finalizar = col2.button("Guardar y generar informe")
    if guardar or finalizar:
        tabla.to_csv(detalle, index=False, encoding="utf-8-sig")
        if finalizar:
            try:
                revisadas = revision.leer_revision(detalle)
                revision.guardar_csv(destino / "resumen_revision_humana.csv", revision.resumir_por_tema(revisadas))
                revision.guardar_csv(destino / "comparacion_modelo_revision.csv", revision.comparar_etiquetas(revisadas))
                metadatos = destino / 'publicaciones.json'
                publicaciones = json.loads(metadatos.read_text(encoding='utf-8')) if metadatos.is_file() else []
                editorial.crear_html(revisadas, destino / 'informe_editorial.html', publicaciones)
                st.session_state.fase = "informe"
                st.rerun()
            except (ValueError, OSError) as error:
                st.error(str(error))
        else:
            st.success("Revisión guardada. Puedes cerrar y retomarla después.")

if st.session_state.fase == "informe":
    st.subheader("4. Informe final")
    destino = Path(st.session_state.estudio)
    documento = destino / 'informe_editorial.html'
    # Regenera desde las etiquetas guardadas con el diseño vigente, incluso
    # cuando el servidor se inició antes de actualizar el módulo editorial.
    editorial = importlib.reload(editorial)
    try:
        filas_informe = revision.leer_revision(destino / 'comentarios_analizados.csv')
        metadatos = destino / 'publicaciones.json'
        posts_informe = json.loads(metadatos.read_text(encoding='utf-8')) if metadatos.is_file() else []
        editorial.crear_html(filas_informe, documento, posts_informe)
    except (ValueError, OSError) as error:
        st.error(f'No se pudo actualizar el informe: {error}')
        st.stop()
    componentes.html(documento.read_text(encoding='utf-8'), height=1000, scrolling=True)
    st.download_button('Descargar informe editorial', documento.read_bytes(), file_name=f'informe_{destino.name}.html', mime='text/html')
    resumen = destino / "resumen_revision_humana.csv"
    st.download_button("Descargar resumen CSV", resumen.read_bytes(), file_name=f"resumen_{destino.name}.csv", mime="text/csv")
    if st.button("Volver a revisar comentarios"):
        st.session_state.fase = "revision"
        st.rerun()
