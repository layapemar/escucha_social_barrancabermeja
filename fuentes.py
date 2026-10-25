"""Conexiones de Página y trazabilidad de estudios con varias fuentes."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import descargar_comentarios as facebook

def ocultar_error(error, tokens):
    texto = str(error)
    for token in tokens:
        if token:
            texto = texto.replace(token, '[credencial oculta]')
    return texto

def buscar(tokens, palabras, progreso=lambda mensaje: None):
    conexiones, publicaciones, cobertura = {}, [], []
    for numero, token in enumerate(dict.fromkeys(t.strip() for t in tokens if t.strip()), 1):
        progreso(f'Consultando Página {numero}...')
        identidad = facebook.consultar('me', token, {'fields': 'id,name,category'})
        pagina_id = str(identidad.get('id', ''))
        if not pagina_id or not identidad.get('category'):
            raise ValueError(f'La conexión {numero} necesita un token de Página, no un token personal.')
        if pagina_id in conexiones:
            continue
        nombre = identidad.get('name', pagina_id)
        posts = facebook.buscar_publicaciones(token, pagina_id, palabras)
        conexiones[pagina_id] = token
        for post in posts:
            post.update(page_id=pagina_id, page_name=nombre)
        publicaciones.extend(posts)
        cobertura.append({'page_id': pagina_id, 'page_name': nombre, 'coincidencias': len(posts)})
    return conexiones, sorted(publicaciones, key=lambda p: p.get('created_time', ''), reverse=True), cobertura

def descargar_seleccion(posts, conexiones, limite, tema, progreso=lambda mensaje: None):
    filas, cobertura, vistos = [], [], set()
    for numero, post in enumerate(posts, 1):
        pid = post['page_id']
        token = conexiones.get(pid)
        if not token:
            raise ValueError(f'Vuelve a conectar la Página {post["page_name"]}.')
        progreso(f'Descargando {numero}/{len(posts)} · {post["page_name"]}')
        comentarios = facebook.descargar(token, post['id'], limite)
        añadidos = 0
        for fila in comentarios:
            # No se deduplican textos iguales de personas distintas.
            clave = (pid, post['id'], fila.get('comment_id'))
            if fila.get('comment_id') and clave in vistos:
                continue
            vistos.add(clave)
            fila.update(tema=tema, page_id=pid, page_name=post['page_name'])
            filas.append(fila)
            añadidos += 1
        cobertura.append({'page_id': pid, 'page_name': post['page_name'], 'post_id': post['id'],
            'comentarios_descargados': añadidos, 'limite_solicitado': limite,
            'limite_alcanzado': len(comentarios) >= limite,
            'conteo_mostrado_por_meta': post.get('comments', {}).get('summary', {}).get('total_count'),
            'extraido_utc': datetime.now(timezone.utc).isoformat()})
    return filas, cobertura

def identificar(fila):
    pid = fila.get('page_id') or fila.get('post_id', '').split('_')[0]
    nombre = fila.get('page_name') or ('Canal Telepetróleo' if pid == '124142061045473' else ('Página ' + pid if pid else 'Fuente no registrada'))
    return pid, nombre

def resumen(filas):
    grupos = defaultdict(list)
    for f in filas:
        grupos[identificar(f)].append(f)
    total = len(filas)
    resultado = []
    for (pid, nombre), grupo in grupos.items():
        cuenta = Counter(f.get('revision_humana') or f.get('interpretacion_inicial', '') for f in grupo)
        resultado.append({'page_id': pid, 'fuente': nombre, 'comentarios': len(grupo),
            'publicaciones': len({f.get('post_id') for f in grupo if f.get('post_id')}),
            'peso_muestra_pct': round(100 * len(grupo) / total, 1),
            **{c + '_pct': round(100 * cuenta[c] / len(grupo), 1) for c in ('positivo', 'negativo', 'neutral')}})
    return resultado
