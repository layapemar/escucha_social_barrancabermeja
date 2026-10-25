"""Análisis complementario reproducible. Las inferencias se conservan para auditar."""
import csv
import gc
import hashlib
import html
import json
import os
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
PERFILES_POSTURA = {
    'Mayor capacidad (mDeBERTa)': 'MoritzLaurer/mDeBERTa-v3-base-mnli-xnli',
    'Ligero (MiniLM)': MODELOS['postura'],
}

def huella(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()

def guardar(ruta, datos):
    ruta = Path(ruta)
    temporal = ruta.with_suffix('.tmp')
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')
    # Windows puede retener brevemente el destino mientras lo inspecciona.
    # Reintentos acotados conservan el reemplazo atómico y no ocultan errores.
    import time
    for intento in range(5):
        try:
            temporal.replace(ruta)
            break
        except PermissionError:
            if intento == 4:
                raise
            time.sleep(.05 * 2**intento)

def filas_estudio(ruta):
    with Path(ruta).open(encoding='utf-8-sig', newline='') as f:
        return [r for r in csv.DictReader(f) if r.get('comentario', '').strip()]

def ejecutar(ruta, objetivo, progreso=lambda texto: None, modelo_postura_id=None):
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
            return _ejecutar(ruta, objetivo, progreso, modelo_postura_id)
        finally:
            archivo.seek(0)
            msvcrt.locking(archivo.fileno(), msvcrt.LK_UNLCK, 1)

def _ejecutar(ruta, objetivo, progreso=lambda texto: None, modelo_postura_id=None):
    """Reanuda etapas completas, conservando correcciones si no cambia el origen."""
    # Ubicación configurable para no llenar el disco del sistema.
    config_cache = Path(__file__).parent / '.model_cache.json'
    cache_root = json.loads(config_cache.read_text(encoding='utf-8'))['ruta'] if config_cache.exists() else None
    if cache_root:
        os.environ['HF_XET_CACHE'] = str(Path(cache_root) / 'xet')
    from analizar_comentarios import ModeloLigero
    import torch
    torch.set_num_threads(2)
    ruta = Path(ruta)
    destino = ruta.parent / 'observatorio.json'
    firma = huella(ruta)
    datos = json.loads(destino.read_text(encoding='utf-8')) if destino.exists() else {}
    if (datos.get('huella'), datos.get('objetivo'), datos.get('version')) != (firma, objetivo, VERSION):
        if datos:
            guardar(ruta.parent / f'observatorio_anterior_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.json', datos)
        datos = {'version': VERSION, 'huella': firma, 'objetivo': objetivo,
                 'creado': datetime.now(timezone.utc).isoformat(), 'modelos': dict(MODELOS),
                 'etapas': [], 'filas': filas_estudio(ruta), 'revisiones_modelos': {}}
    if modelo_postura_id is not None:
        if modelo_postura_id not in PERFILES_POSTURA.values():
            raise ValueError('Perfil de postura no admitido.')
        if datos['modelos']['postura'] != modelo_postura_id:
            guardar(ruta.parent / f'observatorio_perfil_anterior_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.json', datos)
            datos['modelos']['postura'] = modelo_postura_id
            datos['etapas'] = [e for e in datos['etapas'] if e != 'postura']
            guardar(destino, datos)
    filas = datos['filas']
    if not filas:
        raise ValueError('El estudio no contiene comentarios.')
    for tarea in ('emocion', 'ironia'):
        if tarea in datos['etapas']:
            continue
        progreso(f'Cargando modelo de {tarea}. La primera descarga puede tardar varios minutos.')
        modelo = ModeloLigero(MODELOS[tarea])
        # En esta CPU float32 resultó más rápido que float16 para inferencia.
        modelo.torch.set_num_threads(2)
        modelo.modelo.float()
        cache = {}
        datos['revisiones_modelos'][tarea] = getattr(modelo.modelo.config, '_commit_hash', None)
        for i, fila in enumerate(filas):
            if fila.get(tarea + '_procesada'):
                continue
            texto = fila['comentario']
            if texto not in cache:
                cache[texto] = modelo.predict(texto)
            pred = cache[texto]
            fila[tarea + '_modelo'] = EMOCIONES.get(pred.output, pred.output) if tarea == 'emocion' else str(pred.output)
            fila[tarea + '_final'] = fila[tarea + '_modelo']
            fila[tarea + '_puntuacion'] = float(pred.probas[pred.output])
            fila[tarea + '_revisada'] = False
            fila[tarea + '_procesada'] = True
            if (i + 1) % 20 == 0:
                guardar(destino, datos)
            if i % 10 == 0:
                progreso(f'{tarea}: {i + 1}/{len(filas)}')
        del modelo
        gc.collect()
        datos['etapas'].append(tarea)
        guardar(destino, datos)
    if 'postura' not in datos['etapas']:
        from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
        progreso('Preparando clasificación contextual de postura y peticiones.')
        tokenizador = AutoTokenizer.from_pretrained(datos['modelos']['postura'], cache_dir=cache_root)
        modelo_postura = AutoModelForSequenceClassification.from_pretrained(datos['modelos']['postura'], cache_dir=cache_root)
        clasificador = pipeline('zero-shot-classification', model=modelo_postura, tokenizer=tokenizador, device=-1)
        datos['revisiones_modelos']['postura'] = getattr(clasificador.model.config, '_commit_hash', None)
        etiquetas = ['apoyo', 'rechazo', 'mixta', 'sin postura explícita']
        cache = {}
        for i, fila in enumerate(filas):
            if fila.get('modelo_postura_id') == datos['modelos']['postura']:
                continue
            texto = fila['comentario']
            if texto not in cache:
                pred = clasificador(texto, candidate_labels=etiquetas,
                    hypothesis_template='Este comentario expresa {} hacia ' + objetivo.replace('{', '').replace('}', '') + '.')
                pet = clasificador(texto, candidate_labels=['petición o propuesta de acción', 'otro tipo de comentario'],
                    hypothesis_template='Este texto contiene {}.')
                cache[texto] = (pred, pet)
            pred, pet = cache[texto]
            anterior = {k: fila.get(k) for k in ('postura_revisada', 'postura_final', 'peticion_modelo', 'peticion_final')}
            # Umbrales operativos iniciales, no calibrados con la muestra local.
            segura = pred['scores'][0] >= .60 and pred['scores'][0] - pred['scores'][1] >= .15
            fila.update(postura_modelo=pred['labels'][0] if segura else 'indeterminada',
                        postura_puntuacion=float(pred['scores'][0]), postura_revisada=False,
                        peticion_modelo=pet['labels'][0] if pet['scores'][0] >= .65 else 'indeterminada')
            fila['postura_final'] = fila['postura_modelo']
            fila['peticion_final'] = fila['peticion_modelo']
            if anterior['postura_revisada']:
                fila['postura_final'] = anterior['postura_final']
                fila['postura_revisada'] = True
            if anterior['peticion_final'] and anterior['peticion_final'] != anterior['peticion_modelo']:
                fila['peticion_final'] = anterior['peticion_final']
            fila['prioridad_revision'] = 'alta' if not segura or fila['ironia_modelo'].lower() in ('ironic', 'irony', 'ironia', '1') else 'normal'
            fila['modelo_postura_id'] = datos['modelos']['postura']
            if (i + 1) % 20 == 0:
                guardar(destino, datos)
            if i % 10 == 0:
                progreso(f'Postura frente a {objetivo}: {i + 1}/{len(filas)}')
        del clasificador, modelo_postura, tokenizador
        gc.collect()
        datos['etapas'].append('postura')
        guardar(destino, datos)
    if 'temas' not in datos['etapas']:
        from sentence_transformers import SentenceTransformer
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.cluster import MiniBatchKMeans
        from sklearn.feature_extraction.text import TfidfVectorizer
        from informe_editorial import STOP
        progreso('Agrupando comentarios por similitud de significado.')
        modelo = SentenceTransformer(MODELOS['temas'], device='cpu', cache_folder=cache_root)
        datos['revisiones_modelos']['temas'] = getattr(modelo[0].auto_model.config, '_commit_hash', None)
        textos = list(dict.fromkeys(f['comentario'] for f in filas))
        vectores = modelo.encode(textos, batch_size=16, normalize_embeddings=True, show_progress_bar=False)
        if len(textos) > 2000:
            # Evita la matriz cuadrática de distancias en estudios grandes.
            k = min(100, max(10, int(len(textos)**.5)))
            grupos = MiniBatchKMeans(n_clusters=k, batch_size=256, random_state=42, n_init=3).fit_predict(vectores)
            datos['agrupacion'] = {'metodo': 'MiniBatchKMeans', 'grupos': k, 'semilla': 42}
        else:
            grupos = AgglomerativeClustering(n_clusters=None, distance_threshold=.35,
                        metric='cosine', linkage='average').fit_predict(vectores) if len(textos) > 1 else [0]
            datos['agrupacion'] = {'metodo': 'jerárquico', 'distancia_coseno': .35}
        import numpy as np
        np.save(ruta.parent / 'representaciones.npy', vectores, allow_pickle=False)
        guardar(ruta.parent / 'indice_semantico.json', {'huella': firma, 'textos': textos, 'modelo': MODELOS['temas']})
        miembros = defaultdict(list)
        for texto, grupo in zip(textos, grupos):
            miembros[int(grupo)].append(texto)
        nombres = {}
        # El peso de cada término se calcula entre grupos, no aisladamente.
        grupos_validos = [g for g, textos_grupo in miembros.items() if len(textos_grupo) >= 2]
        etiquetas_grupos = {}
        if grupos_validos:
            from informe_editorial import normalizar, palabras
            vacias = set(STOP) | {normalizar(p) for p in palabras(objetivo)}
            vectorizador = TfidfVectorizer(stop_words=sorted(vacias), strip_accents='unicode', ngram_range=(1, 3))
            try:
                matriz = vectorizador.fit_transform([' '.join(miembros[g]) for g in grupos_validos])
                vocabulario = vectorizador.get_feature_names_out()
                for i, g in enumerate(grupos_validos):
                    terminos = []
                    for indice in matriz[i].toarray()[0].argsort()[::-1]:
                        candidato = vocabulario[indice]
                        if matriz[i, indice] <= 0:
                            break
                        if any(candidato in t or t in candidato for t in terminos):
                            continue
                        terminos.append(candidato)
                        if len(terminos) == 3:
                            break
                    etiquetas_grupos[g] = ' / '.join(terminos)
            except ValueError:
                pass
        for grupo, ejemplos in miembros.items():
            if len(ejemplos) < 2:
                nombres[grupo] = 'Sin agrupación suficiente'
                continue
            nombres[grupo] = etiquetas_grupos.get(grupo) or 'Grupo sin descripción automática'
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
    ficha_ejecucion(datos)
    guardar(destino, datos)
    if (ruta.parent / 'indice_semantico.json').exists() and not datos.get('version_asuntos'):
        from temas_semanticos import completar
        progreso('Identificando asuntos con referencias semánticas...')
        datos = completar(ruta)
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

def buscar_semantico(ruta, pregunta, limite=10):
    """Recupera comentarios por significado, sin generar respuestas inventadas."""
    import numpy as np
    from sentence_transformers import SentenceTransformer
    ruta = Path(ruta)
    indice = json.loads((ruta.parent / 'indice_semantico.json').read_text(encoding='utf-8'))
    if indice['huella'] != huella(ruta):
        raise ValueError('El índice no corresponde al estudio actual. Actualiza el análisis.')
    config = Path(__file__).parent / '.model_cache.json'
    cache_root = json.loads(config.read_text(encoding='utf-8'))['ruta'] if config.exists() else None
    modelo = SentenceTransformer(indice['modelo'], device='cpu', cache_folder=cache_root)
    consulta = modelo.encode([pregunta], normalize_embeddings=True)[0]
    vectores = np.load(ruta.parent / 'representaciones.npy', allow_pickle=False)
    puntuaciones = vectores @ consulta
    seleccion = puntuaciones.argsort()[::-1][:limite]
    return [{'comentario': indice['textos'][int(i)], 'similitud': round(float(puntuaciones[i]), 4)} for i in seleccion]

def evaluar(filas, tarea):
    pares = [(f[tarea + '_modelo'], f[tarea + '_final']) for f in filas if f.get(tarea + '_revisada')]
    if not pares:
        return {'revisados': 0}
    return {'revisados': len(pares), 'acuerdo_porcentaje': round(100 * sum(a == b for a,b in pares) / len(pares), 1),
            'confusiones': [{'modelo': a, 'humana': b, 'cantidad': n} for (a,b), n in Counter(pares).items()]}

def ficha_ejecucion(datos):
    """Añade versiones y parámetros para reproducir el análisis local."""
    import sys
    from importlib.metadata import version, PackageNotFoundError
    versiones = {}
    for paquete in ('torch', 'transformers', 'sentence-transformers', 'scikit-learn', 'pysentimiento'):
        try:
            versiones[paquete] = version(paquete)
        except PackageNotFoundError:
            versiones[paquete] = 'no instalado'
    datos['entorno'] = {'python': sys.version.split()[0], 'bibliotecas': versiones}
    datos['parametros'] = {'postura_puntuacion_minima': .60, 'postura_margen_minimo': .15,
                          'peticion_puntuacion_minima': .65, 'tokens_robertuito': 128,
                          'unidad': 'comentario', 'emociones': 'una categoría dominante por texto',
                          'agrupacion': datos.get('agrupacion', {}), 'asuntos': datos.get('metodo_asuntos', {})}
    return datos

def seccion_html(datos):
    from informe_observatorio import seccion
    return seccion(datos)
