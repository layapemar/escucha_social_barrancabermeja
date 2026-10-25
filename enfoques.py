"""Análisis independientes por destinatario y pregunta dentro de un estudio."""
import gc
import hashlib
import html
import json
import re
import unicodedata
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import observatorio as obs

VERSION = 1
ETIQUETAS = ['apoyo', 'rechazo', 'mixta', 'sin postura explícita', 'indeterminada']
ENFOQUES = {
    'Valoración de la gestión': 'la gestión de {persona}',
    'Respaldo a una candidatura': 'una posible candidatura de {persona}',
    'Otro enfoque específico': '{pregunta}',
}


def ahora():
    return datetime.now(timezone.utc).isoformat()


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto).lower())
                   if unicodedata.category(c) != 'Mn')


def menciones(texto, alias):
    """Coincidencias de palabras completas, sin inferir a quién aluden pronombres."""
    texto = normalizar(texto)
    return [a for a in alias if re.search(r'(?<!\w)' + r'\s+'.join(
        re.escape(t) for t in normalizar(a).split()) + r'(?!\w)', texto)]


def registros(ruta):
    filas = obs.filas_estudio(ruta)
    for i, fila in enumerate(filas):
        fila['registro'] = str(i)
    return filas


@contextmanager
def bloqueo(ruta):
    import msvcrt
    with (Path(ruta).parent / 'enfoques.lock').open('a+b') as archivo:
        archivo.seek(0, 2)
        if archivo.tell() == 0:
            archivo.write(b'0')
            archivo.flush()
        archivo.seek(0)
        try:
            msvcrt.locking(archivo.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError('Hay otro análisis por enfoque en curso en este estudio.') from error
        try:
            yield
        finally:
            archivo.seek(0)
            msvcrt.locking(archivo.fileno(), msvcrt.LK_UNLCK, 1)


def cargar(ruta):
    archivo = Path(ruta).parent / 'enfoques.json'
    return json.loads(archivo.read_text(encoding='utf-8')) if archivo.exists() else {'version': VERSION, 'analisis': []}


def guardar(ruta, catalogo):
    obs.guardar(Path(ruta).parent / 'enfoques.json', catalogo)


def obtener(catalogo, identificador):
    return next(a for a in catalogo['analisis'] if a['id'] == identificador)


def crear(ruta, persona, alias, enfoque, pregunta='', modelo=None):
    persona = persona.strip()
    pregunta = pregunta.strip()
    enfoque = enfoque.strip()
    if not persona or not enfoque:
        raise ValueError('Indica la persona, institución, acción o tema y qué quieres conocer.')
    if enfoque == 'Otro enfoque específico' and not pregunta:
        raise ValueError('Escribe el objetivo concreto de este enfoque.')
    if len(persona) > 150 or len(pregunta) > 250 or len(enfoque) > 250:
        raise ValueError('Usa un nombre de hasta 150 caracteres y un objetivo de hasta 250.')
    modelo = modelo or obs.PERFILES_POSTURA['Mayor capacidad (mDeBERTa)']
    if modelo not in obs.PERFILES_POSTURA.values():
        raise ValueError('Selecciona un perfil disponible.')
    alias = list(dict.fromkeys(a.strip() for a in [persona, *alias] if a.strip()))
    # Conserva compatibilidad con los primeros análisis y admite enfoques libres.
    objetivo = ENFOQUES[enfoque].format(persona=persona, pregunta=pregunta) if enfoque in ENFOQUES else f'{persona}: {enfoque}'
    firma = obs.huella(ruta)
    identidad = json.dumps([firma, persona, alias, enfoque, objetivo, modelo], ensure_ascii=False)
    identificador = hashlib.sha256(identidad.encode()).hexdigest()[:20]
    with bloqueo(ruta):
        catalogo = cargar(ruta)
        existente = next((a for a in catalogo['analisis'] if a['id'] == identificador), None)
        if existente:
            return existente
        filas = registros(ruta)
        coincidencias = {f['registro']: menciones(f['comentario'], alias) for f in filas}
        analisis = dict(id=identificador, huella=firma, persona=persona, alias=alias,
            enfoque=enfoque, objetivo=objetivo, modelo=modelo, creado=ahora(),
            total_estudio=len(filas), seleccion=[k for k,v in coincidencias.items() if v],
            coincidencias=coincidencias, seleccion_confirmada=False, estado='seleccion', filas=[],
            parametros={'puntuacion_minima': .60, 'margen_minimo': .15, 'max_tokens': 512,
                        'evidencia_mixta_minima': .80,
                        'ausencia_postura_maxima': .20,
                        'metodo': 'Evidencia NLI independiente de apoyo y rechazo con softmax de tres clases'})
        catalogo['analisis'].append(analisis)
        guardar(ruta, catalogo)
        return analisis


def comprobar(ruta, analisis):
    if analisis['huella'] != obs.huella(ruta):
        raise ValueError('El archivo de comentarios cambió. Crea un enfoque nuevo para este origen; el anterior se conserva como histórico.')


def seleccionar(ruta, identificador, seleccion, confirmada=False):
    with bloqueo(ruta):
        catalogo = cargar(ruta)
        analisis = obtener(catalogo, identificador)
        comprobar(ruta, analisis)
        permitidos = {f['registro'] for f in registros(ruta)}
        nueva = sorted(set(map(str, seleccion)), key=int)
        if not set(nueva) <= permitidos:
            raise ValueError('La selección contiene registros que no pertenecen al estudio.')
        if analisis['seleccion'] != nueva:
            conservar = set(nueva)
            anteriores = {f['registro']: f for f in analisis.get('resultados_excluidos', []) + analisis['filas']}
            analisis['filas'] = [anteriores[k] for k in nueva if k in anteriores]
            analisis['resultados_excluidos'] = [f for k,f in anteriores.items() if k not in conservar]
            analisis['estado'] = 'seleccion'
        analisis['seleccion'] = nueva
        analisis['seleccion_confirmada'] = bool(confirmada)
        analisis['seleccion_actualizada'] = ahora()
        guardar(ruta, catalogo)


def clasificador(modelo):
    from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
    import torch
    torch.set_num_threads(2)
    config = Path(__file__).parent / '.model_cache.json'
    cache = json.loads(config.read_text(encoding='utf-8'))['ruta'] if config.exists() else None
    tokenizador = AutoTokenizer.from_pretrained(modelo, cache_dir=cache)
    tokenizador.model_max_length = 512
    red = AutoModelForSequenceClassification.from_pretrained(modelo, cache_dir=cache)
    base = pipeline('zero-shot-classification', model=red, tokenizer=tokenizador, device=-1)
    if base.entailment_id < 0:
        raise ValueError('El modelo no identifica la etiqueta de implicación NLI.')

    class NLICompleto:
        model = red

        def __call__(self, texto, candidate_labels, **kwargs):
            entradas = tokenizador([texto]*len(candidate_labels), candidate_labels,
                padding=True, truncation='only_first', max_length=512, return_tensors='pt')
            with torch.inference_mode():
                probabilidades = red(**entradas).logits.float().softmax(dim=-1)
            # Incluye neutral: las hipótesis sin evidencia no se normalizan
            # únicamente frente a contradicción.
            scores = probabilidades[:,base.entailment_id].tolist()
            orden = sorted(range(len(scores)), key=lambda i:scores[i], reverse=True)
            return dict(labels=[candidate_labels[i] for i in orden],scores=[scores[i] for i in orden])

    return NLICompleto()


def hipotesis(analisis):
    objetivo = analisis['objetivo'].replace('{', '').replace('}', '')
    persona = analisis.get('persona', '').replace('{', '').replace('}', '')
    if analisis.get('enfoque') == 'Valoración de la gestión':
        return {'apoyo': f'La gestión de {persona} fue buena.',
                'rechazo': f'La gestión de {persona} fue mala.'}
    if analisis.get('enfoque') == 'Respaldo a una candidatura':
        return {'apoyo': f'La persona que comenta apoya una candidatura de {persona}.',
                'rechazo': f'La persona que comenta rechaza una candidatura de {persona}.'}
    return {
        'apoyo': f'El comentario expresa una valoración favorable o apoyo hacia {objetivo}.',
        'rechazo': f'El comentario expresa una valoración desfavorable o rechazo hacia {objetivo}.',
    }


def decidir(scores):
    """Reglas operativas sobre evidencia NLI independiente, sin calibración local."""
    pos, neg = (scores[k] for k in ('apoyo','rechazo'))
    if pos >= .80 and neg >= .80:
        return 'mixta'
    if pos >= .60 and pos-neg >= .15:
        return 'apoyo'
    if neg >= .60 and neg-pos >= .15:
        return 'rechazo'
    if max(pos,neg) <= .20:
        return 'sin postura explícita'
    return 'indeterminada'


def inferir(clasif, texto, analisis):
    candidatos = hipotesis(analisis)
    pred = clasif(texto, candidate_labels=list(candidatos.values()),
                  hypothesis_template='{}', multi_label=True)
    inversa = {v:k for k,v in candidatos.items()}
    scores = {inversa[k]: float(v) for k,v in zip(pred['labels'], pred['scores'])}
    orden = sorted(scores, key=scores.get, reverse=True)
    return dict(postura_modelo=decidir(scores),
                puntuaciones=scores, puntuacion=scores[orden[0]],
                margen=scores[orden[0]]-scores[orden[1]])


def ejecutar(ruta, identificador, progreso=lambda t: None, fabrica=None):
    """Reanuda resultados parciales y conserva las correcciones individuales."""
    with bloqueo(ruta):
        catalogo = cargar(ruta)
        analisis = obtener(catalogo, identificador)
        comprobar(ruta, analisis)
        if not analisis['seleccion_confirmada']:
            raise ValueError('Confirma primero los comentarios relacionados con esta persona y enfoque.')
        if not analisis['seleccion']:
            raise ValueError('No hay comentarios seleccionados para analizar.')
        originales = {f['registro']: f for f in registros(ruta)}
        resultados = {f['registro']: f for f in analisis['filas']}
        pendientes = [k for k in analisis['seleccion'] if k not in resultados]
        if pendientes:
            progreso(f'Cargando modelo. Se analizarán {len(pendientes)} comentarios nuevos.')
            modelo = (fabrica or clasificador)(analisis['modelo'])
            config = getattr(getattr(modelo, 'model', None), 'config', None)
            analisis['revision_modelo'] = getattr(config, '_commit_hash', None)
            analisis['hipotesis'] = hipotesis(analisis)
            analisis['estado'] = 'procesando'
            guardar(ruta, catalogo)
            cache = {}
            for i, clave in enumerate(pendientes):
                original = originales[clave]
                texto = original['comentario']
                if texto not in cache:
                    cache[texto] = inferir(modelo, texto, analisis)
                pred = cache[texto]
                resultado = dict(original, **pred, postura_final=pred['postura_modelo'],
                    postura_revisada=False, nota_revision='',
                    referencia=analisis['coincidencias'].get(clave) or ['Inclusión manual'])
                resultados[clave] = resultado
                analisis['filas'] = [resultados[k] for k in analisis['seleccion'] if k in resultados]
                # Checkpoint individual: una interrupción no obliga a repetir el lote.
                guardar(ruta, catalogo)
                progreso(f'{analisis["persona"]} · {analisis["enfoque"]}: {i+1}/{len(pendientes)} nuevos')
            del modelo
            gc.collect()
        analisis['estado'] = 'completo'
        analisis['terminado'] = ahora()
        guardar(ruta, catalogo)
        return analisis


def revisar(ruta, identificador, cambios):
    with bloqueo(ruta):
        catalogo = cargar(ruta)
        analisis = obtener(catalogo, identificador)
        comprobar(ruta, analisis)
        for fila in analisis['filas']:
            cambio = cambios.get(fila['registro'])
            if cambio is None:
                continue
            etiqueta = cambio['postura_final']
            if etiqueta not in ETIQUETAS:
                raise ValueError('Etiqueta de postura no válida.')
            fila['postura_revisada'] = bool(cambio.get('postura_revisada')) or etiqueta != fila['postura_final']
            fila['postura_final'] = etiqueta
            fila['nota_revision'] = str(cambio.get('nota_revision', ''))
        analisis['revisado'] = ahora()
        guardar(ruta, catalogo)


def resumen(analisis):
    filas = analisis['filas']
    n = len(filas)
    cuenta = Counter(f['postura_final'] for f in filas)
    return dict(persona=analisis['persona'], enfoque=analisis['enfoque'], comentarios=n,
        porcentaje_estudio=round(100*n/analisis['total_estudio'], 1) if analisis['total_estudio'] else 0,
        revisados=sum(bool(f.get('postura_revisada')) for f in filas),
        **{c+'_pct': round(100*cuenta[c]/n,1) if n else 0 for c in ETIQUETAS})


def contexto(ruta, analisis):
    """Dimensiones ya calculadas sobre la misma base; no se atribuyen al destinatario."""
    extra = Path(ruta).parent / 'observatorio.json'
    if not extra.exists():
        return {}
    datos = json.loads(extra.read_text(encoding='utf-8'))
    if datos.get('huella') != analisis['huella']:
        return {}
    seleccion = set(analisis['seleccion'])
    # El observatorio conserva el orden de las filas no vacías del CSV.
    filas = [f for i,f in enumerate(datos['filas']) if str(i) in seleccion]
    return {t:Counter(f.get(t+'_final') or 'Sin resultado' for f in filas)
            for t in ('emocion','ironia','asunto') if any(t+'_final' in f for f in filas)}


def vigentes(ruta):
    firma = obs.huella(ruta)
    return [a for a in cargar(ruta)['analisis'] if a['huella'] == firma and
            a['estado'] == 'completo' and a['seleccion_confirmada'] and
            len(a['filas']) == len(a['seleccion'])]


def seccion_html(ruta):
    from informe_observatorio import barras, ESTILO
    analisis = vigentes(ruta)
    if not analisis:
        return ''
    e = lambda x: html.escape(str(x), quote=True)
    partes = [ESTILO, '<section class="ob"><div class="ob-intro"><h2>Análisis por persona y enfoque</h2><p>Base específica: comentarios seleccionados y confirmados para cada destinatario. Una observación puede pertenecer a varias personas. Los porcentajes usan la base de cada análisis y no representan intención de voto poblacional.</p></div>']
    for enfoque in dict.fromkeys(a['enfoque'] for a in analisis):
        partes.append(f'<h3>{e(enfoque)}</h3><div class="ob-grid">')
        for a in [a for a in analisis if a['enfoque'] == enfoque]:
            r = resumen(a)
            partes.append(f'<article class="ob-card"><h3>{e(a["persona"])}</h3><p>Objetivo: {e(a["objetivo"])}</p><p><b>{r["comentarios"]} comentarios · {r["porcentaje_estudio"]:.1f}% del estudio</b><br>Revisión de postura registrada: {r["revisados"]}/{r["comentarios"]}</p>')
            partes.append(barras(Counter(f['postura_final'] for f in a['filas']), len(a['filas'])))
            tono = Counter(f.get('revision_humana') or f.get('interpretacion_inicial') or 'Sin resultado' for f in a['filas'])
            partes.append('<h4>Tono de los comentarios seleccionados</h4>'+barras(tono,len(a['filas'])))
            partes.append('<p class="ob-meta">Comentarios relacionados confirmados por la persona analista. Las posturas sin revisión individual permanecen provisionales. Los casos indeterminados se conservan en la base.</p>')
            if len(a['filas']) < 20:
                partes.append('<p class="ob-note">Base reducida: interpretar conjuntamente con los textos. No constituye una clasificación de popularidad.</p>')
            for etiqueta in ('apoyo', 'rechazo'):
                ejemplo = next((f for f in a['filas'] if f['postura_final'] == etiqueta), None)
                if ejemplo:
                    marca = 'Postura revisada' if ejemplo.get('postura_revisada') else 'Ejemplo automático provisional'
                    partes.append(f'<small>{etiqueta.title()} · {marca}</small><blockquote>{e(ejemplo["comentario"])}</blockquote>')
            dimensiones = contexto(ruta, a)
            if dimensiones:
                partes.append('<details><summary>Emociones, ironía y asuntos de esta selección</summary><p>Describen el texto completo. No implican que la emoción o el asunto estén dirigidos exclusivamente a esta persona.</p>')
                for tarea,cuenta in dimensiones.items():
                    partes.append(f'<h4>{e(tarea.title())}</h4>'+barras(cuenta,len(a['filas'])))
                partes.append('</details>')
            partes.append(f'<p class="ob-meta">Modelo: {e(a["modelo"])}<br>Registro: {e(a["id"])} · {e(a.get("terminado", ""))}</p></article>')
        partes.append('</div>')
    partes.append('<p>Selección inicial por nombres y expresiones completas, normalizando tildes y mayúsculas. Las alusiones indirectas requieren inclusión manual. Inferencia NLI con hipótesis independientes de apoyo y rechazo, usando las tres clases de NLI para medir evidencia. Umbrales operativos: 0.60 de evidencia y 0.15 de margen para posturas únicas; mixta cuando ambas hipótesis alcanzan 0.80. Se asigna ausencia de postura cuando ambas quedan en 0.20 o menos; el resto permanece indeterminado. Son reglas iniciales sin calibración local. Las puntuaciones de las hipótesis no suman 100%. El texto completo puede mezclar varios destinatarios: verificar la atribución. No se infieren perfiles políticos de quienes comentan.</p></section>')
    return ''.join(partes)
