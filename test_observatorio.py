import tempfile
import unittest
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

if __name__ == '__main__':
    unittest.main()
