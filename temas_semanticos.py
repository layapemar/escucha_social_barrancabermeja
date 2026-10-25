"""Asuntos sugeridos por similitud con descripciones explícitas y auditables."""
import json
from pathlib import Path

DESCRIPCIONES = {
    'Seguridad y justicia': 'Robos, homicidios, extorsiones, policía, delincuencia, miedo a salir y protección de las personas.',
    'Obras, vías y movilidad': 'Reparación de calles, pavimentación, huecos, obras, puentes, tráfico, transporte, muelle y malecón.',
    'Salud y atención médica': 'Hospitales, médicos, urgencias, medicamentos, EPS, enfermos y calidad de atención en salud.',
    'Servicios públicos y ambiente': 'Agua, energía, alcantarillado, basuras, aseo, contaminación, inundaciones y cuidado ambiental.',
    'Empleo y economía': 'Empleo, desempleo, negocios, comercio, ingresos, costo de vida, oportunidades laborales e impuestos.',
    'Educación y cultura': 'Colegios, escuelas, estudiantes, docentes, universidades, becas, arte y actividades culturales.',
    'Gestión y recursos públicos': 'Administración del gobierno, presupuesto, contratos, corrupción, recursos públicos, promesas, deuda y resultados de gestión.',
    'Participación y convivencia': 'Convivencia, relaciones entre vecinos, participación comunitaria, respeto y conflictos sociales.',
}

def completar(ruta, modelo=None):
    import numpy as np
    from observatorio import huella, guardar, MODELOS
    ruta = Path(ruta)
    destino = ruta.parent / 'observatorio.json'
    datos = json.loads(destino.read_text(encoding='utf-8'))
    if datos['huella'] != huella(ruta):
        raise ValueError('Actualiza el estudio antes de clasificar asuntos.')
    if datos.get('version_asuntos') == 1:
        return datos
    indice = json.loads((ruta.parent / 'indice_semantico.json').read_text(encoding='utf-8'))
    vectores = np.load(ruta.parent / 'representaciones.npy', allow_pickle=False)
    if indice['huella'] != datos['huella'] or len(vectores) != len(indice['textos']):
        raise ValueError('El índice semántico no corresponde al estudio.')
    if modelo is None:
        from sentence_transformers import SentenceTransformer
        config = Path(__file__).parent / '.model_cache.json'
        cache = json.loads(config.read_text(encoding='utf-8'))['ruta'] if config.exists() else None
        modelo = SentenceTransformer(MODELOS['temas'], device='cpu', cache_folder=cache)
    nombres = list(DESCRIPCIONES)
    referentes = modelo.encode(list(DESCRIPCIONES.values()), normalize_embeddings=True, show_progress_bar=False)
    similitudes = vectores @ referentes.T
    asignacion = {}
    for texto, valores in zip(indice['textos'], similitudes):
        orden = valores.argsort()[::-1]
        mejor, segunda = float(valores[orden[0]]), float(valores[orden[1]])
        nombre = nombres[int(orden[0])] if mejor >= .30 and mejor - segunda >= .03 else 'Sin asunto claro'
        asignacion[texto] = (nombre, mejor)
    for fila in datos['filas']:
        nombre, puntuacion = asignacion[fila['comentario']]
        fila['asunto_modelo'] = nombre
        if not fila.get('asunto_revisada'):
            fila['asunto_final'] = nombre
            fila['asunto_revisada'] = False
        fila['asunto_similitud'] = puntuacion
        # Los títulos automáticos no se presentan como síntesis editorial.
        if not fila.get('tema_revisado') and fila['tema_final'] == fila['tema_sugerido']:
            fila['tema_final'] = 'Sin agrupación suficiente' if fila['tema_sugerido'] == 'Sin agrupación suficiente' else 'Grupo exploratorio ' + str(int(fila['grupo']) + 1)
    datos['version_asuntos'] = 1
    datos['metodo_asuntos'] = {'metodo': 'similitud coseno con descripciones de referencia',
        'umbral': .30, 'margen': .03, 'descripciones': DESCRIPCIONES,
        'nota': 'Umbrales iniciales no calibrados. Similitud no equivale a probabilidad.'}
    guardar(destino, datos)
    return datos
