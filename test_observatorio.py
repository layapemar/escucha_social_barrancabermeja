import tempfile
import unittest
import types
from unittest.mock import patch
from pathlib import Path
from observatorio import guardar, huella, evolucion, evaluar, seccion_html


class PruebasObservatorio(unittest.TestCase):
    def test_evaluacion_no_cuenta_etiquetas_no_revisadas(self):
        filas = [dict(emocion_modelo='enojo', emocion_final='alegría', emocion_revisada=True),
                 dict(emocion_modelo='enojo', emocion_final='enojo', emocion_revisada=False)]
        self.assertEqual(evaluar(filas, 'emocion')['revisados'], 1)
        self.assertEqual(evaluar(filas, 'emocion')['acuerdo_porcentaje'], 0)

    def test_periodos_denominadores_y_fechas_invalidas(self):
        filas = [dict(fecha='2026-01-01T12:00:00+00:00', post_id='1', revision_humana='positivo'),
                 dict(fecha='2026-01-02', post_id='1', revision_humana='negativo'),
                 dict(fecha='', revision_humana='neutral')]
        periodos, excluidas = evolucion(filas)
        self.assertEqual(excluidas, 1)
        self.assertEqual(periodos[0]['publicaciones'], 1)
        self.assertEqual(periodos[0]['positivo_porcentaje'], 50)

    def test_html_escapa_texto_de_usuarios(self):
        datos = dict(objetivo='<script>alert(1)</script>', filas=[dict(comentario='<img src=x>',
            peticion_final='petición o propuesta de acción')], modelos={}, huella='a', creado='hoy')
        html = seccion_html(datos)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img', html)

    def test_guardado_y_cambio_de_huella(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            ruta = Path(tmp)/'datos.json'
            guardar(ruta, {'revision': 'enojo'})
            anterior = huella(ruta)
            guardar(ruta, {'revision': 'alegría'})
            self.assertNotEqual(anterior, huella(ruta))

    def test_cambio_de_perfil_preserva_revision_y_archiva(self):
        import observatorio as obs
        class NLI:
            model = types.SimpleNamespace(config=types.SimpleNamespace(_commit_hash='revision-prueba'))
            def __call__(self, texto, candidate_labels, **kwargs):
                return {'labels': candidate_labels, 'scores': [.85, .1, .03, .02] if len(candidate_labels)==4 else [.85,.15]}
        transformers = types.SimpleNamespace(pipeline=lambda *a,**kw:NLI(),
            AutoTokenizer=types.SimpleNamespace(from_pretrained=lambda *a,**kw:object()),
            AutoModelForSequenceClassification=types.SimpleNamespace(from_pretrained=lambda *a,**kw:object()))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            ruta = Path(tmp)/'comentarios_analizados.csv'
            ruta.write_text('comentario\nTexto\n', encoding='utf-8')
            fila = dict(comentario='Texto', postura_modelo='apoyo', postura_final='rechazo', postura_revisada=True,
                peticion_modelo='otro tipo de comentario', peticion_final='indeterminada', ironia_modelo='not ironic')
            datos = dict(version=obs.VERSION, huella=huella(ruta), objetivo='obras', modelos=dict(obs.MODELOS),
                etapas=['emocion','ironia','postura','temas'], filas=[fila], revisiones_modelos={})
            guardar(Path(tmp)/'observatorio.json', datos)
            with patch.dict('sys.modules', {'transformers':transformers, 'torch':types.SimpleNamespace(set_num_threads=lambda n:None)}):
                salida = obs._ejecutar(ruta, 'obras', modelo_postura_id=obs.PERFILES_POSTURA['Mayor capacidad (mDeBERTa)'])
            self.assertEqual(salida['filas'][0]['postura_modelo'], 'apoyo')
            self.assertEqual(salida['filas'][0]['postura_final'], 'rechazo')
            self.assertTrue(salida['filas'][0]['postura_revisada'])
            self.assertEqual(salida['filas'][0]['peticion_final'], 'indeterminada')
            self.assertTrue(list(Path(tmp).glob('observatorio_perfil_anterior_*.json')))

    def test_asuntos_con_ambiguedad_y_revision_humana(self):
        import numpy as np
        import json
        from temas_semanticos import completar
        class Referencias:
            def encode(self, textos, **kwargs):
                return np.array([[1.,0.]] + [[0.,1.]]*(len(textos)-1))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            ruta = Path(tmp)/'comentarios_analizados.csv'
            ruta.write_text('comentario\nUno\nDos\n', encoding='utf-8')
            fila = lambda texto,g:dict(comentario=texto,grupo=str(g),tema_sugerido='yo',tema_final='yo')
            filas = [fila('Uno',0),fila('Dos',1)]
            filas[1].update(asunto_revisada=True,asunto_final='Salud y atención médica')
            guardar(Path(tmp)/'observatorio.json',dict(huella=huella(ruta),filas=filas))
            guardar(Path(tmp)/'indice_semantico.json',dict(huella=huella(ruta),textos=['Uno','Dos']))
            np.save(Path(tmp)/'representaciones.npy',np.eye(2),allow_pickle=False)
            resultado = completar(ruta,modelo=Referencias())
            self.assertEqual(resultado['filas'][0]['asunto_final'],'Seguridad y justicia')
            self.assertEqual(resultado['filas'][1]['asunto_modelo'],'Sin asunto claro')
            self.assertEqual(resultado['filas'][1]['asunto_final'],'Salud y atención médica')
            self.assertEqual(resultado['filas'][0]['tema_final'],'Grupo exploratorio 1')

if __name__ == '__main__':
    unittest.main()
