"""Gráficas HTML portables del observatorio, sin dependencias de red."""
import html
import json
from collections import Counter


def esc(valor):
    return html.escape(str(valor), quote=True)


COLORES = {'negativo': '#a44748', 'positivo': '#277568', 'neutral': '#738493',
           'rechazo': '#a44748', 'apoyo': '#277568', 'indeterminada': '#a2abb3',
           'Sin asunto claro': '#a2abb3', 'ironic': '#986b35', 'not ironic': '#738493'}
ROTULOS = {'ironic': 'Posible ironía', 'not ironic': 'Sin ironía detectada'}


def barras(cuenta, total):
    if not total:
        return '<p>Sin observaciones disponibles.</p>'
    partes = []
    for etiqueta, n in cuenta.most_common():
        pct = 100*n/total
        partes.append(f'<div class="ob-bar"><div class="ob-label"><span>{esc(ROTULOS.get(etiqueta, etiqueta))}</span><b>{n} · {pct:.1f}%</b></div><div class="ob-track"><div style="width:{pct:.5f}%;background:{COLORES.get(etiqueta, "#486980")}"></div></div></div>')
    return ''.join(partes)


ESTILO = '''<style>
.ob{margin:30px 0;color:#263746}.ob-intro{border-top:3px solid #283b4b;padding-top:12px}.ob h2{margin:0 0 10px;font-size:19px}.ob h3{font-size:14px;margin:0 0 8px}.ob p{font-size:11px;line-height:1.55}.ob-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}.ob-card{border:1px solid #d4dce2;padding:18px;min-width:0;break-inside:avoid}.ob-card.wide{grid-column:1/-1}.ob-label{display:flex;justify-content:space-between;gap:12px;font-size:11px;margin-bottom:4px}.ob-label b{white-space:nowrap}.ob-track{height:9px;background:#edf0f3}.ob-track>div{height:100%;print-color-adjust:exact;-webkit-print-color-adjust:exact}.ob-bar{margin:12px 0}.ob-note{border-left:3px solid #a2814f;padding:9px 12px;background:#f8f6f1}.ob-meta{color:#5d6872;font-size:10px!important;margin-top:14px}.ob blockquote{font-size:11px;line-height:1.5;margin:8px 0;padding:10px;border-left:2px solid #aab9c4}.ob .ob-period{display:grid;grid-template-columns:70px 1fr 110px;gap:12px;align-items:center;margin:12px 0;font-size:10px}.ob-stack{display:flex;height:22px;background:#edf0f3}.ob-stack span{display:block;height:100%;print-color-adjust:exact;-webkit-print-color-adjust:exact}.ob-legend{display:flex;gap:16px;font-size:10px;flex-wrap:wrap}.ob-legend i{display:inline-block;width:9px;height:9px;margin-right:5px}.ob pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:9px}.ob table{table-layout:fixed}.ob td{overflow-wrap:anywhere;vertical-align:top}.ob th{width:22%}.ob details{margin-top:12px}.ob-evidence{display:grid;grid-template-columns:1fr 1fr;gap:12px}.ob-evidence>div{min-width:0}.ob-evidence small{font-size:9px}.ob-guidance td:first-child{font-weight:bold;width:24%}
@media(max-width:700px){.ob-grid,.ob-evidence{grid-template-columns:1fr}.ob .ob-period{grid-template-columns:60px 1fr}.ob-period small{grid-column:2}.ob-card{padding:12px}}
@media print{.ob-card{box-shadow:none}.ob-grid{gap:10px}.ob-card{padding:12px}.ob h2,.ob h3{break-after:avoid}.ob tr{break-inside:avoid}.ob details pre{display:block}.ob{margin-top:20px}}
</style>'''


def seccion(datos):
    from observatorio import evolucion, evaluar
    filas = datos.get('filas', [])
    total = len(filas)
    partes = [ESTILO, '<section class="ob"><div class="ob-intro"><h2>Dimensiones de la conversación</h2>',
              f'<p>Objetivo de la postura: <b>{esc(datos.get("objetivo", "Sin definir"))}</b>. Base: {total} comentarios. Cada dimensión responde una pregunta distinta; sus porcentajes no se suman entre sí.</p></div><div class="ob-grid">']
    tareas = [('emocion', '¿Qué emociones expresa el texto?', 'Emoción expresada, no estado psicológico de quien comenta.'),
              ('ironia', '¿Hay señales de ironía?', 'Detección automática susceptible a errores, especialmente con contexto local y emojis.'),
              ('postura', '¿Qué postura se expresa hacia el objetivo?', 'El tono negativo no implica rechazo al objetivo. Los casos indeterminados permanecen en el denominador.'),
              ('asunto', '¿Sobre qué asuntos se conversa?', 'Una categoría por comentario, sugerida por similitud semántica con descripciones de referencia. No es una clasificación temática validada.')]
    for tarea, titulo, nota in tareas:
        cuenta = Counter(f.get(tarea+'_final') or 'Sin resultado' for f in filas)
        partes.append(f'<article class="ob-card"><h3>{titulo}</h3><p>{nota}</p>{barras(cuenta,total)}')
        revisados = sum(bool(f.get(tarea+'_revisada')) for f in filas)
        partes.append(f'<p class="ob-meta">Base: {total} · Revisión individual registrada: {revisados}/{total}. Las etiquetas restantes son provisionales.</p>')
        if tarea == 'postura':
            n = cuenta['indeterminada'] + cuenta['Sin resultado']
            partes.append(f'<p class="ob-note">Sin postura resuelta: {n} de {total}, {100*n/total if total else 0:.1f}%. Esta distribución no mide aprobación ciudadana.</p>')
        partes.append('</article>')
    partes.append('</div>')
    peticiones = [f for f in filas if f.get('peticion_final') == 'petición o propuesta de acción']
    partes.append(f'<article class="ob-card"><h3>Peticiones y propuestas de acción</h3><p><b>{len(peticiones)} de {total} comentarios · {100*len(peticiones)/total if total else 0:.1f}%</b>. Hasta cuatro textos distintos como evidencia; pueden requerir interpretación contextual.</p><div class="ob-evidence">')
    textos = list(dict.fromkeys(f.get('comentario','') for f in peticiones))[:4]
    partes.extend(f'<blockquote>{esc(t)}</blockquote>' for t in textos)
    if not textos:
        partes.append('<p>No se identificaron peticiones en las etiquetas finales.</p>')
    partes.append('</div></article>')
    periodos, sin_fecha = evolucion(filas)
    partes.append('<article class="ob-card"><h3>Composición del sentimiento por mes</h3><p>Cada barra representa el 100% de los comentarios del mes. El volumen y las publicaciones se indican al lado para interpretar diferencias.</p><div class="ob-legend">')
    partes.extend(f'<span><i style="background:{COLORES[c]}"></i>{c.title()}</span>' for c in ('negativo','positivo','neutral'))
    partes.append('</div>')
    for p in periodos:
        segmentos = ''.join(f'<span title="{c}: {p[c+"_porcentaje"]:.1f}%" style="width:{p[c+"_porcentaje"]}%;background:{COLORES[c]}"></span>' for c in ('negativo','positivo','neutral'))
        partes.append(f'<div class="ob-period"><b>{esc(p["periodo"])}</b><div><div class="ob-stack">{segmentos}</div><small>Neg. {p["negativo_porcentaje"]:.1f}% · Pos. {p["positivo_porcentaje"]:.1f}% · Neu. {p["neutral_porcentaje"]:.1f}%</small></div><small>{p["comentarios"]} comentarios<br>{p["publicaciones"]} publicaciones</small></div>')
    partes.append(f'<p class="ob-meta">Sin fecha válida: {sin_fecha}. Meses sin observaciones no se representan como cero. Los periodos pueden estar incompletos; diferencias de fuentes, publicaciones y volumen impiden atribuir por sí solas un cambio a la población.</p></article>')
    asuntos = Counter(f.get('asunto_final','Sin asunto claro') for f in filas)
    partes.append('<article class="ob-card"><h3>Evidencia de los asuntos detectados</h3><p>Hasta cuatro asuntos y un texto por asunto. Selección reproducible por orden del archivo; no representa una cita típica ni verifica lo afirmado.</p><div class="ob-evidence">')
    for nombre, n in [(k,n) for k,n in asuntos.most_common() if k != 'Sin asunto claro'][:4]:
        fila = next(f for f in filas if f.get('asunto_final') == nombre)
        partes.append(f'<div><b>{esc(nombre)}</b><small> · {n} comentarios</small><blockquote>{esc(fila.get("comentario", ""))}</blockquote><small>Publicación: {esc(fila.get("post_id", "Sin identificador"))}</small></div>')
    partes.append('</div></article><article class="ob-card"><h3>Validación y trazabilidad del análisis</h3><table><tr><th>Dimensión</th><td>Casos revisados explícitamente</td><td>Acuerdo modelo / revisión</td></tr>')
    for tarea in ('emocion','ironia','postura'):
        ev = evaluar(filas,tarea)
        acuerdo = f'{ev["acuerdo_porcentaje"]:.1f}%' if ev['revisados'] else 'Sin evaluar'
        partes.append(f'<tr><th>{esc(tarea.title())}</th><td>{ev["revisados"]}/{total}</td><td>{acuerdo}</td></tr>')
    partes.append('</table><p>El acuerdo en casos seleccionados no estima exactitud general. No se presenta F1 sin un conjunto independiente etiquetado. Las correcciones humanas no entrenan de nuevo los modelos.</p><table>')
    for tarea, modelo in datos.get('modelos',{}).items():
        partes.append(f'<tr><th>{esc(tarea)}</th><td>{esc(modelo)}</td></tr>')
    partes.append(f'</table><p class="ob-meta">Registro de ejecución: {esc(datos.get("creado", "No disponible"))}<br>Huella de los datos: {esc(datos.get("huella", "No disponible"))}</p><details><summary>Parámetros y versiones reproducibles</summary><pre>{esc(json.dumps({k:datos.get(k,{}) for k in ("revisiones_modelos","entorno","parametros","metodo_asuntos")},ensure_ascii=False,indent=2))}</pre></details></article></section>')
    return ''.join(partes)
