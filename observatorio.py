"""Análisis complementario reproducible. Las inferencias se conservan para auditar."""
import csv
import gc
import hashlib
import html
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

VERSION = 1
MODELOS = {
    'emocion': 'pysentimiento/robertuito-emotion-analysis',
    'ironia': 'pysentimiento/robertuito-irony',
    'postura': 'MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli',
    'temas': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
}
EMOCIONES = {'others': 'otras', 'joy': 'alegría', 'sadness': 'tristeza',
            'anger': 'enojo', 'surprise': 'sorpresa', 'disgust': 'disgusto', 'fear': 'miedo'}

def huella(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()

def guardar(ruta, datos):
    ruta = Path(ruta)
    temporal = ruta.with_suffix('.tmp')
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')
    temporal.replace(ruta)

def filas_estudio(ruta):
    with Path(ruta).open(encoding='utf-8-sig', newline='') as f:
        return [r for r in csv.DictReader(f) if r.get('comentario', '').strip()]

def ejecutar(ruta, objetivo, progreso=lambda texto: None):
    """Impide dos ejecuciones simultáneas sobre el mismo estudio en Windows."""
    import msvcrt
    bloqueo = Path(ruta).parent / 'observatorio.lock'
    with bloqueo.open('a+b') as archivo:
        archivo.seek(0, 2)
        if archivo.tell() == 0:
            archivo.write(b'0')
            archivo.flush()
        archivo.seek(0)
        try:
            msvcrt.locking(archivo.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError('Ya se está procesando este estudio. Espera a que termine.') from error
        try:
            return _ejecutar(ruta, objetivo, progreso)
        finally:
            archivo.seek(0)
            msvcrt.locking(archivo.fileno(), msvcrt.LK_UNLCK, 1)

def _ejecutar(ruta, objetivo, progreso=lambda texto: None):
    """Reanuda etapas completas, conservando correcciones si no cambia el origen."""
    from analizar_comentarios import ModeloLigero
    ruta = Path(ruta)
    destino = ruta.parent / 'observatorio.json'
    firma = huella(ruta)
    datos = json.loads(destino.read_text(encoding='utf-8')) if destino.exists() else {}
    if (datos.get('huella'), datos.get('objetivo'), datos.get('version')) != (firma, objetivo, VERSION):
        if datos:
            guardar(ruta.parent / f'observatorio_anterior_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.json', datos)
        datos = {'version': VERSION, 'huella': firma, 'objetivo': objetivo,
                 'creado': datetime.now(timezone.utc).isoformat(), 'modelos': MODELOS,
                 'etapas': [], 'filas': filas_estudio(ruta), 'revisiones_modelos': {}}
    filas = datos['filas']
    if not filas:
        raise ValueError('El estudio no contiene comentarios.')
    for tarea in ('emocion', 'ironia'):
        if tarea in datos['etapas']:
            continue
        progreso(f'Cargando modelo de {tarea}. La primera descarga puede tardar varios minutos.')
        modelo = ModeloLigero(MODELOS[tarea])
        cache = {}
        datos['revisiones_modelos'][tarea] = getattr(modelo.modelo.config, '_commit_hash', None)
        for i, fila in enumerate(filas):
            texto = fila['comentario']
            if texto not in cache:
                cache[texto] = modelo.predict(texto)
            pred = cache[texto]
            fila[tarea + '_modelo'] = EMOCIONES.get(pred.output, pred.output) if tarea == 'emocion' else str(pred.output)
            fila[tarea + '_final'] = fila[tarea + '_modelo']
            fila[tarea + '_puntuacion'] = float(pred.probas[pred.output])
            fila[tarea + '_revisada'] = False
            if i % 10 == 0:
                progreso(f'{tarea}: {i + 1}/{len(filas)}')
        del modelo
        gc.collect()
        datos['etapas'].append(tarea)
        guardar(destino, datos)
    if 'postura' not in datos['etapas']:
        from transformers import pipeline
        progreso('Preparando clasificación contextual de postura y peticiones.')
        clasificador = pipeline('zero-shot-classification', model=MODELOS['postura'], device=-1)
        datos['revisiones_modelos']['postura'] = getattr(clasificador.model.config, '_commit_hash', None)
        etiquetas = ['apoyo', 'rechazo', 'mixta', 'sin postura explícita']
        cache = {}
        for i, fila in enumerate(filas):
            texto = fila['comentario']
            if texto not in cache:
                pred = clasificador(texto, candidate_labels=etiquetas,
                    hypothesis_template='Este comentario expresa {} hacia ' + objetivo.replace('{', '').replace('}', '') + '.')
                pet = clasificador(texto, candidate_labels=['petición o propuesta de acción', 'otro tipo de comentario'],
                    hypothesis_template='Este texto contiene {}.')
                cache[texto] = (pred, pet)
            pred, pet = cache[texto]
            # Umbrales operativos iniciales, no calibrados con la muestra local.
            segura = pred['scores'][0] >= .60 and pred['scores'][0] - pred['scores'][1] >= .15
            fila.update(postura_modelo=pred['labels'][0] if segura else 'indeterminada',
                        postura_puntuacion=float(pred['scores'][0]), postura_revisada=False,
                        peticion_modelo=pet['labels'][0] if pet['scores'][0] >= .65 else 'indeterminada')
            fila['postura_final'] = fila['postura_modelo']
            fila['peticion_final'] = fila['peticion_modelo']
            fila['prioridad_revision'] = 'alta' if not segura or fila['ironia_modelo'].lower() in ('ironic', 'irony', 'ironia', '1') else 'normal'
            if i % 10 == 0:
                progreso(f'Postura frente a {objetivo}: {i + 1}/{len(filas)}')
        del clasificador
        gc.collect()
        datos['etapas'].append('postura')
        guardar(destino, datos)
    if 'temas' not in datos['etapas']:
        from sentence_transformers import SentenceTransformer
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.feature_extraction.text import TfidfVectorizer
        from informe_editorial import STOP
        progreso('Agrupando comentarios por similitud de significado.')
        modelo = SentenceTransformer(MODELOS['temas'], device='cpu')
        textos = list(dict.fromkeys(f['comentario'] for f in filas))
        vectores = modelo.encode(textos, batch_size=16, normalize_embeddings=True, show_progress_bar=False)
        grupos = AgglomerativeClustering(n_clusters=None, distance_threshold=.35,
                    metric='cosine', linkage='average').fit_predict(vectores) if len(textos) > 1 else [0]
        miembros = defaultdict(list)
        for texto, grupo in zip(textos, grupos):
            miembros[int(grupo)].append(texto)
        nombres = {}
        for grupo, ejemplos in miembros.items():
            if len(ejemplos) < 2:
                nombres[grupo] = 'Sin agrupación suficiente'
                continue
            try:
                vectorizador = TfidfVectorizer(stop_words=sorted(STOP), strip_accents='unicode', ngram_range=(1, 2))
                matriz = vectorizador.fit_transform(ejemplos)
                indices = matriz.mean(axis=0).A1.argsort()[-3:][::-1]
                nombres[grupo] = ' / '.join(vectorizador.get_feature_names_out()[indices])
            except ValueError:
                nombres[grupo] = 'Grupo sin descripción automática'
        asignacion = dict(zip(textos, map(int, grupos)))
        for fila in filas:
            grupo = asignacion[fila['comentario']]
            fila['grupo'] = str(grupo)
            fila['tema_sugerido'] = nombres[grupo]
            fila['tema_final'] = nombres[grupo]
        del modelo
        gc.collect()
        datos['etapas'].append('temas')
        guardar(destino, datos)
    return datos

def evolucion(filas):
    periodos = defaultdict(list)
    sin_fecha = 0
    for fila in filas:
        try:
            fecha = datetime.fromisoformat(fila.get('fecha', '').replace('Z', '+00:00'))
            clave = fecha.strftime('%Y-%m')
            periodos[clave].append(fila)
        except (ValueError, TypeError):
            sin_fecha += 1
    resultado = []
    for periodo, grupo in sorted(periodos.items()):
        cuenta = Counter(f.get('revision_humana') or f.get('interpretacion_inicial') for f in grupo)
        resultado.append({'periodo': periodo, 'comentarios': len(grupo),
            'publicaciones': len({f.get('post_id') for f in grupo if f.get('post_id')}),
            **{c + '_porcentaje': round(100 * cuenta[c] / len(grupo), 1) for c in ('positivo', 'negativo', 'neutral')}})
    return resultado, sin_fecha

def evaluar(filas, tarea):
    pares = [(f[tarea + '_modelo'], f[tarea + '_final']) for f in filas if f.get(tarea + '_revisada')]
    if not pares:
        return {'revisados': 0}
    return {'revisados': len(pares), 'acuerdo_porcentaje': round(100 * sum(a == b for a,b in pares) / len(pares), 1),
            'confusiones': [{'modelo': a, 'humana': b, 'cantidad': n} for (a,b), n in Counter(pares).items()]}

def seccion_html(datos):
    esc = lambda x: html.escape(str(x))
    filas = datos['filas']
    partes = ['<section><h2>Análisis complementario de conversación</h2>',
        f'<p>Objetivo de la postura: {esc(datos["objetivo"])}. Base: {len(filas)} comentarios. Inferencias experimentales con revisión registrada.</p>']
    for tarea in ('emocion', 'ironia', 'postura', 'tema'):
        if not all(tarea + '_final' in f for f in filas):
            continue
        cuenta = Counter(f[tarea + '_final'] for f in filas)
        partes.append(f'<h3>{esc(tarea.title())}</h3><table><tr><th>Categoría</th><th>Comentarios</th><th>%</th></tr>')
        for etiqueta, cantidad in cuenta.most_common(12):
            partes.append(f'<tr><td>{esc(etiqueta)}</td><td>{cantidad}</td><td>{100*cantidad/len(filas):.1f}%</td></tr>')
        partes.append('</table>')
        if tarea == 'tema':
            for etiqueta, cantidad in cuenta.most_common(6):
                if etiqueta == 'Sin agrupación suficiente':
                    continue
                partes.append(f'<h4>{esc(etiqueta)}</h4>')
                ejemplos = list(dict.fromkeys(f['comentario'] for f in filas if f['tema_final'] == etiqueta))[:2]
                partes.extend(f'<blockquote>{esc(texto)}</blockquote>' for texto in ejemplos)
        if tarea != 'tema':
            evaluacion = evaluar(filas, tarea)
            partes.append(f'<p>Revisados explícitamente: {evaluacion["revisados"]}. Acuerdo modelo/persona en esos casos: {evaluacion.get("acuerdo_porcentaje", "sin evaluar")}.</p>')
    peticiones = [f for f in filas if f.get('peticion_final') == 'petición o propuesta de acción']
    partes.append(f'<h3>Peticiones y propuestas</h3><p>{len(peticiones)} comentarios clasificados. Ejemplos para revisión:</p>')
    for f in peticiones[:4]:
        partes.append(f'<blockquote>{esc(f["comentario"])}</blockquote>')
    periodos, sin_fecha = evolucion(filas)
    partes.append('<h3>Evolución mensual de la muestra</h3><table><tr><th>Mes</th><th>Comentarios</th><th>Publicaciones</th><th>Positivo %</th><th>Negativo %</th><th>Neutral %</th></tr>')
    for p in periodos:
        partes.append('<tr>' + ''.join(f'<td>{esc(v)}</td>' for v in p.values()) + '</tr>')
    partes.append(f'</table><p>Sin fecha válida: {sin_fecha}. Los periodos dependen de las publicaciones seleccionadas y pueden estar incompletos. Sus diferencias no demuestran un cambio poblacional ni causalidad.</p>')
    partes.append('<p>Los grupos semánticos son exploratorios y sus títulos requieren revisión. Las emociones describen expresiones del texto. La postura puede quedar indeterminada. El acuerdo sobre casos seleccionados no estima la precisión general.</p>')
    partes.append('<details><summary>Modelos y trazabilidad</summary><pre>' + esc(json.dumps({'modelos': datos['modelos'], 'revisiones': datos.get('revisiones_modelos'), 'huella': datos['huella'], 'creado': datos['creado']}, ensure_ascii=False, indent=2)) + '</pre></details></section>')
    return ''.join(partes)
