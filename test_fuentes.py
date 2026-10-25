import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import fuentes
import informe_editorial

class PruebasFuentes(unittest.TestCase):
    def test_cada_pagina_usa_su_token(self):
        identidades = [{'id':'1','name':'Medio A','category':'News'}, {'id':'2','name':'Medio B','category':'News'}]
        with patch.object(fuentes.facebook, 'consultar', side_effect=identidades), patch.object(fuentes.facebook, 'buscar_publicaciones', side_effect=[[{'id':'1_10'}],[{'id':'2_20'}]]) as buscar:
            conexiones, posts, cobertura = fuentes.buscar(['token-a','token-b'], ['obras'])
        self.assertEqual([c.args[:2] for c in buscar.call_args_list], [('token-a','1'),('token-b','2')])
        self.assertEqual([p['page_name'] for p in posts], ['Medio A','Medio B'])
        self.assertNotIn('token-a', json.dumps(cobertura))
        with patch.object(fuentes.facebook, 'descargar', side_effect=[[{'comment_id':'x','comentario':'igual','post_id':'1_10'}],[{'comment_id':'x','comentario':'igual','post_id':'2_20'}]]) as descargar:
            filas, cobertura = fuentes.descargar_seleccion(posts, conexiones, 200, 'Obras')
        self.assertEqual(len(filas), 2)
        self.assertEqual([c.args[0] for c in descargar.call_args_list], ['token-a','token-b'])
        self.assertEqual({f['page_id'] for f in filas}, {'1','2'})
        self.assertNotIn('token-b', json.dumps(filas+cobertura))

    def test_token_personal_rechazado(self):
        with patch.object(fuentes.facebook, 'consultar', return_value={'id':'1','name':'Persona'}):
            with self.assertRaises(ValueError):
                fuentes.buscar(['personal'], ['obras'])

    def test_repetir_pagina_no_duplica_muestra(self):
        with patch.object(fuentes.facebook, 'consultar', return_value={'id':'1','name':'Medio','category':'News'}), patch.object(fuentes.facebook, 'buscar_publicaciones', return_value=[{'id':'1_1'}]):
            _, posts, _ = fuentes.buscar(['t1','t2'], ['obras'])
        self.assertEqual(len(posts), 1)

    def test_porcentajes_por_fuente_e_informe(self):
        filas = [{'tema':'Obras','comentario':'Opinión','page_id':pid,'page_name':nombre,'post_id':pid+'_1','revision_humana':etiqueta,'interpretacion_inicial':etiqueta} for pid,nombre,etiqueta in [('1','Medio A','positivo'),('2','Medio B','negativo'),('2','Medio B','neutral')]]
        resumen = fuentes.resumen(filas)
        self.assertEqual(resumen[0]['positivo_pct'], 100)
        self.assertEqual(resumen[1]['negativo_pct'], 50)
        self.assertEqual(resumen[1]['peso_muestra_pct'], 66.7)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            ruta = informe_editorial.crear_html(filas, Path(tmp)/'informe.html')
            html = ruta.read_text(encoding='utf-8')
        self.assertIn('Medio A, Medio B', html)
        self.assertNotIn('Canal Telepetróleo', html)

    def test_ocultar_error_no_destruye_texto_sin_tokens(self):
        self.assertEqual(fuentes.ocultar_error('Error de conexión', ['']), 'Error de conexión')
        self.assertNotIn('secreto', fuentes.ocultar_error('token secreto falló', ['secreto']))

if __name__ == '__main__':
    unittest.main()
