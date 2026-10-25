"""Verifica el formulario de varias fuentes sin acceder a Meta."""
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

class PruebasInterfaz(unittest.TestCase):
    def test_dos_paginas_aparecen_en_la_seleccion(self):
        app = AppTest.from_file(str(Path(__file__).parent/'app.py')).run(timeout=45)
        app.number_input[0].set_value(2).run()
        next(t for t in app.text_input if t.label == 'Tema del estudio').set_value('Obras viales')
        app.text_area[0].set_value('vias')
        next(t for t in app.text_input if t.label == 'Token de Página 1').set_value('simulado-a')
        next(t for t in app.text_input if t.label == 'Token de Página 2').set_value('simulado-b')
        posts = [{'id':'1_1','page_id':'1','page_name':'Medio A','message':'Obras viales'},
                 {'id':'2_2','page_id':'2','page_name':'Medio B','message':'Mejoramiento de vías'}]
        with patch('fuentes.buscar', return_value=({'1':'simulado-a','2':'simulado-b'}, posts, [])):
            next(b for b in app.button if b.label == 'Buscar publicaciones').click().run()
        self.assertFalse(list(app.exception))
        self.assertEqual(app.session_state['fase'], 'seleccion')
        self.assertEqual(len(app.multiselect[0].options), 2)
        self.assertIn('Medio A', app.multiselect[0].options[0])
        self.assertIn('Medio B', app.multiselect[0].options[1])

if __name__ == '__main__':
    unittest.main()
