import unittest
from informe_observatorio import seccion, barras
from collections import Counter


class InformeVisual(unittest.TestCase):
    def test_porcentajes_y_abstencion_no_se_ocultan(self):
        filas = [dict(comentario='Texto', postura_final=p, fecha='2026-01-01',
                      revision_humana='negativo', post_id='1') for p in ['indeterminada']*3+['apoyo']]
        documento = seccion(dict(filas=filas, objetivo='Obras', modelos={}))
        self.assertIn('Sin postura resuelta: 3 de 4, 75.0%', documento)
        self.assertIn('Neg. 100.0%', documento)
        self.assertIn('Sin evaluar', documento)

    def test_vacio_y_escapado(self):
        self.assertIn('Sin observaciones', barras(Counter(), 0))
        self.assertNotIn('<script>', barras(Counter({'<script>': 1}), 1))
        self.assertIn('Sin postura resuelta: 0 de 0, 0.0%', seccion({'filas': []}))


if __name__ == '__main__':
    unittest.main()
