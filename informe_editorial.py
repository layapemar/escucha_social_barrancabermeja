"""Informe editorial portable y análisis descriptivo sin servicios externos."""
import html
import re
import random
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

STOP = set('a al algo ante como con cual cuando de del desde donde el ella ellos en entre era es esa ese eso esta este esto fue ha hay la las le les lo los mas me mi muy no nos o para pero por porque que se si sin sobre su sus te tiene todo tu un una uno unos y ya'.split())
STOP.update('nada nadie ninguno ninguna esos esas estas estos aquel aquella aqui ahi alla asi aun tambien tampoco bien mal hacer hace hacen hecho ser estar estarian estan estaba estaban esta este son sera seran seria sido soy somos tiene tienen tener tanto tanta tantos todas todos otra otro otras otros cada siempre nunca mucho mucha muchos muchas poco poca pocos pocas dos tres cuatro cinco ahora entonces pues solo solamente vez veces gracias señor señora senor senora usted ustedes nosotros nuestro nuestra nuestros nuestras deben debe deber puede pueden poder va van ir ver dice dicen decir dar da algo alguna algun algunos algunas cual cuales cuanto quien quienes muy mismo misma mismos mismas porque'.split())

def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')

STOP = {normalizar(p) for p in STOP}
STOP.update('tan han hemos habeis habia habian habra habria hubo sea sean sea sino hacia hasta tampoco tanto mejor peor igual eso aqui alli alla donde luego antes despues mientras aunque segun durante mediante contra bajo tras suyo suya alguien ninguno ninguna ninguno muchas quienes cuyo cuya ustedes'.split())

def palabras(texto):
    texto = unicodedata.normalize('NFKC', texto).lower()
    texto = re.sub(r'https?://\S+', '', texto)
    texto = re.sub(r'\b(?:ja|je|ji|jo|ju){2,}\b', '', texto)
    return re.findall(r'[a-záéíóúñü]{3,}', texto)

def recurrencias(filas, limite=12, excluir=()):
    vacias = STOP | {normalizar(p.strip()) for p in excluir if p.strip()}
    cuenta = Counter()
    for fila in filas:
        tokens = palabras(fila.get('comentario', ''))
        expresiones = set()
        for n in (1, 2, 3):
            for i in range(len(tokens)-n+1):
                trozo = tokens[i:i+n]
                if normalizar(trozo[0]) not in vacias and normalizar(trozo[-1]) not in vacias:
                    expresiones.add(' '.join(trozo))
        cuenta.update(expresiones)
    candidatos = [(texto, n) for texto,n in cuenta.items() if n >= 2]
    candidatos.sort(key=lambda par: (-par[1], -len(par[0].split()), par[0]))
    candidatos = candidatos[:500]
    salida = []
    for texto, n in candidatos:
        if any(n == m and f' {texto} ' in f' {otro} ' for otro,m in candidatos if otro != texto):
            continue
        salida.append((texto,n))
        if len(salida) >= limite:
            break
    return salida

DOMINIOS = {
    'Tecnología y vigilancia': ['dron', 'drones', 'camaras', 'videovigilancia', 'tecnologia'],
    'Seguridad': ['seguridad', 'robo', 'robos', 'policia', 'homicidio', 'extorsion', 'atraco', 'delincuencia'],
    'Vías y movilidad': ['vias', 'via', 'huecos', 'pavimento', 'puente', 'transito', 'movilidad', 'semaforo'],
    'Salud': ['hospital', 'urgencias', 'salud', 'eps', 'medicos', 'medicamentos'],
    'Servicios públicos': ['agua', 'acueducto', 'alcantarillado', 'basura', 'aseo', 'energia', 'luz'],
    'Educación': ['colegio', 'colegios', 'educacion', 'escuela', 'estudiantes', 'docentes'],
    'Empleo y economía': ['empleo', 'desempleo', 'trabajo', 'comercio', 'impuestos', 'desempleados'],
    'Gestión pública': ['alcalde', 'alcaldia', 'gobierno', 'contratistas', 'contrato', 'presupuesto', 'concejales'],
}

def asuntos(filas):
    resultado = []
    for nombre, terminos in DOMINIOS.items():
        patron = r'\b(?:' + '|'.join(re.escape(t) for t in terminos) + r')\b'
        seleccion = [f for f in filas if re.search(patron, normalizar(f.get('comentario','')))]
        if seleccion:
            cuenta = Counter(f['revision_humana'] for f in seleccion)
            resultado.append((nombre, len(seleccion), cuenta['negativo'], cuenta['positivo'], cuenta['neutral']))
    return sorted(resultado, key=lambda r: (-r[1], r[0]))

def grafica(cuenta, total):
    colores = {'negativo':'#b64248','positivo':'#087c61','neutral':'#586b7b'}
    segmentos = []
    leyenda = []
    for etiqueta in ('negativo','positivo','neutral'):
        n = cuenta[etiqueta]
        porcentaje = 100*n/total
        rotulo = f'{porcentaje:.1f}%' if porcentaje >= 10 else ''
        segmentos.append(f'<div title="{etiqueta}: {n} ({porcentaje:.1f}%)" style="width:{porcentaje:.5f}%;background:{colores[etiqueta]}">{rotulo}</div>')
        leyenda.append(f'<span><i style="background:{colores[etiqueta]}"></i>{etiqueta.capitalize()} <b>{n}</b> · {porcentaje:.1f}%</span>')
    return '<figure aria-label="Distribución final de sentimientos"><div class="apilada">'+''.join(segmentos)+'</div><figcaption>'+''.join(leyenda)+'</figcaption></figure>'

def muestra_preguntas(filas, limite=10):
    """Muestra reproducible, sin repetir textos y alternando publicaciones."""
    grupos = defaultdict(list)
    vistos = set()
    for fila in filas:
        texto = fila.get('comentario', '').strip()
        clave = ' '.join(normalizar(texto).split())
        if ('?' in texto or '¿' in texto) and clave not in vistos:
            vistos.add(clave)
            grupos[fila.get('post_id', '')].append(fila)
    salida = []
    while grupos and len(salida) < limite:
        for post in list(grupos):
            salida.append(grupos[post].pop(0))
            if not grupos[post]:
                del grupos[post]
            if len(salida) == limite:
                break
    return salida

def alerta(fila):
    valores = sorted((float(fila.get(k) or 0) for k in ('p_positivo','p_negativo','p_neutral')), reverse=True)
    motivos = []
    if valores[0] < .70 or valores[0]-valores[1] < .20:
        motivos.append('predicción ambigua')
    texto = fila.get('comentario', '')
    if any(e in texto for e in ('😂','🤣','🙄','🤡','🤔')):
        motivos.append('emoji que requiere contexto')
    if len(palabras(texto)) <= 4:
        motivos.append('frase breve')
    if len(texto) > 450:
        motivos.append('texto largo: revisar posible truncamiento')
    return ', '.join(motivos)

def crear_html(filas, salida, publicaciones=None, excluir=()):
    if not filas:
        raise ValueError('No hay comentarios para generar el informe.')
    if any(f.get('revision_humana') not in {'positivo','negativo','neutral'} for f in filas):
        raise ValueError('Completa las etiquetas finales antes de generar el informe.')
    e = lambda valor: html.escape(str(valor), quote=True)
    total = len(filas)
    cuenta = Counter(f['revision_humana'] for f in filas)
    grupos = defaultdict(list)
    for f in filas:
        grupos[f.get('post_id') or 'sin_id'].append(f)
    metadata = {p['id']: p for p in (publicaciones or [])}
    fechas = sorted(f.get('fecha','')[:10] for f in filas if f.get('fecha'))
    periodo = f'{fechas[0]} al {fechas[-1]}' if fechas else 'Sin fecha registrada'
    tarjetas = ''.join(f'<div class="dato"><span>{c.capitalize()}</span><strong>{100*cuenta[c]/total:.1f}<em>%</em></strong><small>{cuenta[c]} comentarios</small></div>' for c in ('negativo','positivo','neutral'))
    tabla_asuntos = ''.join(f'<tr><td>{e(nombre)}</td><td>{n}</td><td>{100*n/total:.1f}%</td><td>{neg}</td><td>{pos}</td><td>{neu}</td></tr>' for nombre,n,neg,pos,neu in asuntos(filas))
    temas_html = '<table><thead><tr><th>Asunto mencionado</th><th>Comentarios</th><th>% muestra</th><th>Neg.</th><th>Pos.</th><th>Neu.</th></tr></thead><tbody>'+tabla_asuntos+'</tbody></table>' if tabla_asuntos else '<p>No se identificaron coincidencias con el diccionario de asuntos.</p>'
    preguntas = sum('?' in f.get('comentario','') or '¿' in f.get('comentario','') for f in filas)
    textos = Counter(' '.join(unicodedata.normalize('NFKC',f.get('comentario','')).lower().split()) for f in filas)
    duplicados = sum(n-1 for n in textos.values())
    seleccion_preguntas = muestra_preguntas(filas, limite=4)
    preguntas_html = ''.join(
        f'<li><span class="numero">{i}</span><div>{e(f["comentario"][:240])}{"…" if len(f["comentario"])>240 else ""}<small>Publicación {list(grupos).index(f.get("post_id") or "sin_id")+1} · {e(f["revision_humana"].capitalize())}</small></div></li>'
        for i,f in enumerate(seleccion_preguntas, 1)
    ) or '<li>No se encontraron comentarios con signos de interrogación.</li>'
    principal = max(grupos, key=lambda p: len(grupos[p]))
    foco = list(grupos).index(principal)+1
    lectura = f'La publicación {foco} reúne {len(grupos[principal])} de los {total} comentarios, el {100*len(grupos[principal])/total:.1f}% de la muestra. Prioriza su lectura para entender qué está impulsando la conversación.'
    meses = defaultdict(Counter)
    for f in filas:
        if re.fullmatch(r'\d{4}-\d{2}',f.get('fecha','')[:7]):
            meses[f['fecha'][:7]][f['revision_humana']] += 1
    evolucion = ''.join(f'<tr><td>{mes}</td><td>{sum(c.values())}</td><td>{c["negativo"]}</td><td>{c["positivo"]}</td><td>{c["neutral"]}</td></tr>' for mes,c in sorted(meses.items()))
    bloques = []
    for indice,(post,comentarios) in enumerate(grupos.items(),1):
        p = metadata.get(post,{})
        c = Counter(f['revision_humana'] for f in comentarios)
        citas = []
        for categoria in ('negativo','positivo'):
            unicos = {}
            for f in sorted(comentarios, key=lambda f: f.get('ejemplo_publicar') != 'sí'):
                if f['revision_humana'] == categoria:
                    unicos.setdefault(' '.join(normalizar(f.get('comentario', '')).split()), f)
            aprobados = [f for f in unicos.values() if f.get('ejemplo_publicar') == 'sí']
            candidatos = [f for f in unicos.values() if f.get('ejemplo_publicar') != 'sí']
            # Semilla reproducible: los ejemplos no cambian con cada recarga.
            azar = random.Random(str(filas[0].get('tema', '')) + str(post) + categoria)
            ejemplos = aprobados[:3]
            ejemplos += azar.sample(candidatos, min(3-len(ejemplos), len(candidatos)))
            if ejemplos:
                contenido = ''.join(
                    f'<div style="margin-bottom:14px"><blockquote>{e(f["comentario"][:300])}{"…" if len(f["comentario"])>300 else ""}</blockquote><small>'
                    + ('Ejemplo aprobado en revisión' if f.get('ejemplo_publicar') == 'sí' else 'Selección automática aleatoria')
                    + '</small></div>' for f in ejemplos
                )
                if len(ejemplos) < 3:
                    contenido += f'<small>Solo hay {len(ejemplos)} comentarios distintos de esta categoría.</small>'
            else:
                contenido = '<p class="muted">Sin comentarios de esta categoría.</p>'
            citas.append(f'<div><h4>{categoria.capitalize()}</h4>{contenido}</div>')
        titulo = p.get('message') or f'Publicación {post} · texto no guardado en este estudio anterior'
        enlace = f'https://www.facebook.com/{post}' if re.fullmatch(r'[0-9_]+',post) else ''
        porcentajes = ' · '.join(f'{100*c[k]/len(comentarios):.1f}% {k}' for k in ('negativo','positivo','neutral'))
        bloques.append(f'<section class="publicacion"><h3>{indice}. {e(titulo[:150])}{"…" if len(titulo)>150 else ""}</h3><p class="muted">{e(p.get("created_time","")[:10])} · {len(comentarios)} comentarios</p><p class="distribucion">{porcentajes}</p><div class="citas">{"".join(citas)}</div>'+ (f'<a href="{e(enlace)}">Consultar publicación ↗</a>' if enlace else '')+'</section>')
    documento = f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Escucha social</title><style>
    body{{font-family:Arial,sans-serif;background:#f2f5f8;color:#17212b;margin:0;line-height:1.5}}main{{max-width:1050px;margin:35px auto;padding:35px;background:white}}h1{{font-size:36px;line-height:1.15}}h2{{margin-top:38px;color:#176b87}}.datos,.citas{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}}.citas{{grid-template-columns:1fr 1fr}}.dato{{padding:18px;background:#edf3f6}}strong{{display:block;font-size:38px}}.muted{{color:#526273}}li{{display:flex;justify-content:space-between;gap:20px;padding:8px;border-bottom:1px solid #ddd}}.publicacion{{break-inside:avoid;border-top:2px solid #dce5ea;margin-top:25px;padding-top:15px}}blockquote{{margin:0 0 15px;padding:14px;background:#f2f5f8;white-space:pre-wrap;overflow-wrap:anywhere}}button{{padding:10px}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{text-align:left;border-bottom:1px solid #ddd;padding:10px}}.barra{{display:grid;grid-template-columns:90px 1fr 110px;align-items:center;gap:12px;margin:15px 0}}figure{{margin:15px 0}}@media(max-width:650px){{main{{margin:0;padding:20px}}.datos,.citas{{grid-template-columns:1fr}}.barra{{grid-template-columns:75px 1fr 95px;font-size:13px}}table{{font-size:12px}}}}@media print{{body{{background:white}}main{{margin:0;padding:0}}button{{display:none}}}}</style><main>
    <header class="cabecera"><p class="serie">INFORME TÉCNICO · ANÁLISIS DE SENTIMIENTOS</p><h1>{e(filas[0]['tema'])}</h1><p class="subtitulo">Procesamiento de lenguaje natural aplicado a escucha social<br>Inferencia con RoBERTuito · Clasificación supervisada basada en Transformers</p><p class="fuente"><b>Fuente de información:</b> fanpage de Facebook Canal Telepetróleo · Extracción mediante Meta Graph API</p></header>
    <section class="muestra"><div><span>UNIDAD DE ANÁLISIS</span><strong>{total}</strong><small>comentarios con texto</small></div><div><span>COBERTURA OBSERVADA</span><strong>{len(grupos)}</strong><small>publicaciones con comentarios analizados</small></div><div><span>PERIODO DE LOS COMENTARIOS</span><b>{e(periodo)}</b><small>Muestra no probabilística de publicaciones seleccionadas</small></div></section>
    <section class="resultado"><div class="eyebrow">RESULTADO CENTRAL · TONO DE LA CONVERSACIÓN</div><h2>Distribución de la percepción en la muestra</h2><div class="datos">{tarjetas}</div>{grafica(cuenta,total)}<p class="muted">Base: {total} comentarios · Etiquetas finales con correcciones humanas. El tono no equivale automáticamente a aprobación de una persona.</p></section>
    <aside class="lectura"><h2>Concentración de la muestra</h2><p>{lectura}</p></aside>
    <h2>Asuntos presentes en la conversación</h2>{temas_html}<p class="muted">Clasificación descriptiva por un diccionario de términos, no por comprensión semántica. Un comentario puede mencionar varios asuntos: los porcentajes no suman necesariamente 100%. El sentimiento corresponde al comentario completo, no a cada asunto por separado.</p>
    <h2>Comentarios interrogativos</h2><p><b>{preguntas} de {total} comentarios · {100*preguntas/total:.1f}% de la muestra.</b> Identificación por signos de interrogación. Se presentan hasta cuatro ejemplos distintos alternando publicaciones; pueden incluir preguntas retóricas.</p><ol class="preguntas">{preguntas_html}</ol><div class="nota"><b>Repetición textual:</b> {duplicados} registros adicionales con texto idéntico normalizado, equivalentes al {100*duplicados/total:.1f}% del total. Se conservan en las cifras. Esta coincidencia no permite inferir coordinación.</div>
    <h2>Distribución temporal de esta muestra</h2><table><tr><th>Mes</th><th>Total</th><th>Negativos</th><th>Positivos</th><th>Neutrales</th></tr>{evolucion}</table><p class="muted">Refleja las fechas de los comentarios seleccionados. Cambios de volumen o sentimiento pueden deberse a la selección de publicaciones.</p>
    <h2>Qué se dijo en cada publicación</h2><div class="publicaciones">{''.join(bloques)}</div>
    <h2>Ficha técnica y alcance metodológico</h2>
    <table class="metodo"><tbody>
    <tr><th>Diseño del análisis</th><td>Estudio descriptivo y exploratorio de comentarios en publicaciones seleccionadas. Muestreo no probabilístico, condicionado por la búsqueda, selección y disponibilidad en la API.</td></tr>
    <tr><th>Unidad y denominador</th><td>Un comentario con texto constituye una observación. Los porcentajes globales se calculan sobre n = {total}; los porcentajes por publicación usan el total de esa publicación. No se estiman personas únicas.</td></tr>
    <tr><th>Modelo utilizado</th><td>RoBERTuito, arquitectura RobertaForSequenceClassification. Modelo preentrenado de aprendizaje profundo basado en Transformers, utilizado para inferencia local en tres clases: negativo, neutral y positivo. Este estudio no incluye entrenamiento ni ajuste de pesos.</td></tr>
    <tr><th>Procesamiento</th><td>Preprocesamiento de texto con pysentimiento y tokenización con el tokenizador del modelo. Secuencias limitadas a 128 tokens; los textos más largos pueden truncarse. Cálculo de probabilidades mediante softmax y selección de la clase con mayor puntuación.</td></tr>
    <tr><th>Intervención humana</th><td>Las etiquetas finales combinan predicciones conservadas y modificaciones manuales. Conservar una predicción no acredita una validación individual. Las correcciones no reentrenan el modelo.</td></tr>
    <tr><th>Análisis complementario</th><td>Asuntos identificados mediante diccionario de términos; preguntas mediante signos de interrogación. Son reglas descriptivas independientes del clasificador de sentimiento. La categoría asignada corresponde al comentario completo.</td></tr>
    <tr><th>Validación y límites</th><td>No se ha medido exactitud ni F1 con un conjunto independiente etiquetado para esta muestra. Las puntuaciones del modelo no constituyen certeza estadística. Ironía, sarcasmo, referencias implícitas y contexto local pueden producir errores. No se reporta margen de error poblacional.</td></tr>
    <tr><th>Cobertura y ejemplos</th><td>Comentarios principales con texto accesibles mediante la API; no incluye respuestas. Se priorizan ejemplos aprobados y se identifican los seleccionados automáticamente. Los fragmentos abreviados llevan puntos suspensivos. Los resultados describen la muestra y no representan una encuesta de Barrancabermeja ni una medición directa de aprobación de gobierno.</td></tr>
    </tbody></table>
    <footer class="firma"><b>Laura Pérez</b><span>Analista y científica de datos</span><small>Elaboración y análisis · Informe de escucha social</small></footer>
    <button onclick="window.print()">Imprimir o guardar como PDF</button></main></html>'''
    estilo = '''<style>
    body{font-family:Segoe UI,Arial,sans-serif;background:#eaf0f4;color:#203343}
    main{max-width:1060px;border-radius:22px;padding:48px;box-shadow:0 12px 48px #142d4012}
    h1{font-size:clamp(28px,4vw,44px);letter-spacing:-1px;overflow-wrap:anywhere;color:#102e44}
    h2{font-size:23px;letter-spacing:-.4px;margin:38px 0 14px}
    main>p:first-child{font-size:12px;font-weight:750;letter-spacing:2px;color:#14768b}
    .dato{border-radius:14px;border:1px solid #e1e8ee;background:#f7fafc;padding:22px}
    .dato:nth-child(1) strong{color:#b64248}.dato:nth-child(2) strong{color:#087c61}.dato:nth-child(3) strong{color:#586b7b}
    .dato span{font-size:14px}.dato strong{font-size:42px;line-height:1.2;margin-bottom:8px}
    .apilada{display:flex;height:42px;border-radius:12px;overflow:hidden;margin:25px 0 15px;background:#edf1f4}
    figcaption{display:flex;gap:24px;flex-wrap:wrap;font-size:14px}
    figcaption i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:7px}
    .lectura{padding:22px 26px;border-radius:14px;background:#eaf5f6;border-left:5px solid #16778a;margin-top:28px}
    .lectura h2{margin:0 0 10px}.lectura p:last-child{margin-bottom:0}
    .preguntas{padding:0;list-style:none}.preguntas li{justify-content:flex-start;align-items:flex-start;padding:17px 0;border-color:#e4ebf0}
    .numero{background:#eaf2f7;border-radius:50%;min-width:28px;height:28px;text-align:center;font-weight:700;color:#176b87}
    small{display:block;font-size:12px;color:#647887;margin-top:8px}
    .nota{padding:16px 20px;background:#f4f7fa;border-radius:12px;font-size:14px}
    .publicacion{padding:22px;border:1px solid #dfe8ee;border-radius:14px;margin:20px 0;background:#fff}
    h3{font-size:18px;line-height:1.5;margin-top:0}h4{margin:12px 0;color:#526273}
    blockquote{border-radius:10px;border-left:3px solid #b9cbd7;font-size:15px}
    th{background:#edf4f7;color:#23495d;font-size:12px}td{padding:13px 10px}tr:nth-child(even){background:#f8fafc}
    a{color:#116c88;text-decoration:none;font-weight:600}button{background:#146e86;color:#fff;border:0;border-radius:9px;padding:13px 22px;cursor:pointer}
    .muted{font-size:13px;line-height:1.6;color:#617482}
    @media(max-width:650px){main{padding:22px;border-radius:0}.datos{gap:10px}.citas{grid-template-columns:1fr}.publicacion{padding:15px}figcaption{gap:12px}}
    @media print{main{box-shadow:none;border-radius:0;padding:0}h2,h3{break-after:avoid}.datos,.lectura,figure{break-inside:avoid}body{background:#fff}}
    </style>'''
    ejecutivo = '''<style>
    body{font-size:13px;line-height:1.45;background:#e6ebef;color:#273747}
    main{max-width:1120px;padding:32px 40px;margin:24px auto;border-radius:4px;box-shadow:0 5px 24px #172b4014;border-top:6px solid #14364a}
    h1{font-size:28px;line-height:1.2;letter-spacing:-.6px;margin:12px 0 16px;max-width:950px}
    h2{font-size:17px;color:#193e53;margin:24px 0 10px;border-bottom:1px solid #dfe6eb;padding-bottom:7px}
    .resultado{background:#f3f7fa;border:1px solid #d5e1e9;border-radius:8px;padding:24px;margin:20px 0}
    .eyebrow{font-size:10px;letter-spacing:1.6px;font-weight:800;color:#476273}
    .resultado h2{font-size:22px;border:0;margin:5px 0 20px;padding:0}
    .datos{grid-template-columns:repeat(3,1fr);gap:0}.dato{background:none;border:0;border-radius:0;padding:0 20px;border-right:1px solid #d5e1e9}.dato:first-child{padding-left:0}.dato:last-child{border:0}
    .dato span{text-transform:uppercase;font-size:11px;font-weight:700;letter-spacing:1px}.dato strong{font-size:54px;font-weight:750;letter-spacing:-2px;margin:4px 0}.dato em{font-style:normal;font-size:25px;margin-left:3px}.dato small{font-size:12px;margin:0}
    .apilada{height:58px;margin:22px 0 12px;border-radius:5px}.apilada>div{display:flex;align-items:center;justify-content:center;color:white;font-size:20px;font-weight:700;overflow:hidden}
    figcaption{font-size:11px;gap:22px}.resultado .muted{margin-bottom:0;font-size:11px}
    .lectura{padding:12px 16px;margin:12px 0;border-radius:4px;border-left-width:3px}.lectura h2{font-size:14px;border:0;padding:0}.lectura p{margin:6px 0}.lectura p:last-child{font-size:12px}
    .preguntas{display:grid;grid-template-columns:1fr 1fr;gap:0 22px;margin:8px 0}.preguntas li{font-size:12px;line-height:1.4;padding:10px 0;gap:8px;min-width:0;overflow-wrap:anywhere}.numero{min-width:21px;height:21px;font-size:11px}.preguntas small{font-size:10px;margin-top:4px}
    .publicaciones{display:grid;grid-template-columns:1fr 1fr;gap:14px}.publicacion{margin:0;padding:15px;border-radius:5px;min-width:0}.publicacion h3{font-size:14px;line-height:1.4;margin-bottom:7px}.publicacion p{margin:6px 0}.publicacion .distribucion{font-size:11px;font-weight:700;background:#f0f4f6;padding:6px}
    .citas{gap:12px}.citas h4{font-size:11px;text-transform:uppercase;margin:8px 0}.citas>div:first-child h4{color:#b64248}.citas>div:last-child h4{color:#087c61}blockquote{font-size:12px;padding:8px;margin:0;line-height:1.45;border-radius:3px}.citas small{font-size:9px;margin-top:5px}.publicacion a{display:inline-block;font-size:11px;margin-top:10px}
    th,td{padding:7px 9px;font-size:12px}.muted{font-size:11px;line-height:1.4}.nota{font-size:11px;padding:10px;border-radius:4px}small{font-size:11px}
    @media(max-width:700px){main{padding:20px;margin:0}h1{font-size:24px}.resultado{padding:16px}.dato{padding:0 10px}.dato strong{font-size:36px}.dato em{font-size:18px}.publicaciones,.preguntas{grid-template-columns:1fr}.apilada{height:44px}.apilada>div{font-size:14px}}
    @media print{body{font-size:10px}main{padding:0;margin:0;border:0;max-width:none}.resultado{padding:16px;print-color-adjust:exact;-webkit-print-color-adjust:exact}.dato strong{font-size:40px}.publicaciones{display:block}.publicacion{margin-bottom:10px;break-inside:avoid}.preguntas li{break-inside:avoid}h2{margin-top:17px}button{display:none}}
    </style>'''
    tecnico = '''<style>
    body{font-family:Arial,Helvetica,sans-serif;color:#242a30;background:#e8eaed;font-size:12px;line-height:1.5}
    main{border-top:3px solid #283b4b;border-radius:0;box-shadow:0 2px 12px #0000000c;padding:34px 42px}
    .cabecera{border-bottom:1px solid #8b969f;padding-bottom:16px}.serie{font-size:10px;font-weight:700;letter-spacing:1.2px;color:#47545f;margin:0 0 14px}
    h1{font-family:Georgia,'Times New Roman',serif;font-size:29px;font-weight:normal;letter-spacing:0;line-height:1.25;color:#172f42;margin:0 0 12px}
    .subtitulo{font-size:12px;color:#52606a;margin:8px 0}.fuente{font-size:11px;margin:12px 0 0}
    h2{font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;color:#283b4b;letter-spacing:0}
    .muestra{display:grid;grid-template-columns:1fr 1fr 1.6fr;border-bottom:2px solid #283b4b;padding:18px 0;gap:20px;margin-bottom:20px}
    .muestra span{font-size:9px;letter-spacing:.8px;display:block;color:#57636c;font-weight:700}.muestra strong{font-family:Arial,sans-serif;font-size:32px;color:#263c4e;font-weight:600;line-height:1.3}.muestra b{font-size:14px;display:block;margin:10px 0}.muestra small{font-size:10px;color:#57636c;margin:0}
    .resultado{border:1px solid #cbd2d8;border-radius:0;background:#f7f8f9;padding:22px}.resultado h2{font-size:19px}.dato strong{font-family:Arial,sans-serif;font-size:48px;letter-spacing:-1px}.dato span{letter-spacing:.4px}
    .apilada{border-radius:0;height:48px}.apilada>div{font-size:17px}.lectura{border-radius:0;border-left-color:#687c8d;background:#f2f4f6}.lectura h2{font-size:13px}
    .publicacion,.nota,blockquote{border-radius:0}.publicacion{border-color:#d2d8dd}.numero{border-radius:0;background:#edf0f3;color:#344c60}.publicacion h3{font-family:Arial,sans-serif;font-size:13px;font-weight:600}
    th{background:#eef1f4;color:#334754}th,td{font-size:11px}.metodo th{width:22%;vertical-align:top}.metodo td{line-height:1.55}.firma{border-top:1px solid #8b969f;margin:26px 0 16px;padding-top:15px}.firma b{font-family:Georgia,serif;font-size:19px;font-weight:normal;display:block;color:#223b50}.firma span{display:block;font-size:12px;margin-top:3px}.firma small{font-size:10px;color:#64717c}
    @media(max-width:650px){main{padding:20px}.muestra{grid-template-columns:1fr 1fr}.muestra>div:last-child{grid-column:1/-1}h1{font-size:25px}.dato strong{font-size:34px}}
    @media print{main{padding:0;box-shadow:none}.cabecera,.muestra,.firma{break-inside:avoid}body{font-size:10px}.metodo tr{break-inside:avoid}}
    </style>'''
    documento = documento.replace('</style><main>', '</style>'+estilo+ejecutivo+tecnico+'<main>')
    Path(salida).write_text(documento, encoding='utf-8')
    return Path(salida)
