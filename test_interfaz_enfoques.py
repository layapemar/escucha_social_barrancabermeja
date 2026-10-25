"""Recorrido completo de la interfaz con datos aislados y modelo simulado."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from test_enfoques import ModeloPrueba


class InterfazEnfoques(unittest.TestCase):
    def test_crear_confirmar_ejecutar_y_generar_informe(self):
        base=Path(__file__).parent
        with tempfile.TemporaryDirectory(dir=base) as temporal:
            estudio=Path(temporal)/'datos/privados/estudios/prueba'
            estudio.mkdir(parents=True)
            ruta=estudio/'comentarios_analizados.csv'
            with ruta.open('w',encoding='utf-8',newline='') as f:
                escritor=csv.DictWriter(f,fieldnames=['tema','comentario','interpretacion_inicial','revision_humana','post_id'])
                escritor.writeheader()
                escritor.writerow(dict(tema='Prueba aislada',comentario='Kellyn realizó una buena gestión.',
                    interpretacion_inicial='positivo',revision_humana='positivo',post_id='1_1'))
            codigo=(base/'pages/3_Personas_y_enfoques.py').read_text(encoding='utf-8')
            codigo=codigo.replace('BASE = Path(__file__).resolve().parents[1]',f'BASE = Path({temporal!r})')
            app=AppTest.from_string(codigo).run(timeout=45)
            next(t for t in app.text_input if t.label=='Persona, institución, acción o tema').set_value('Kellyn')
            next(t for t in app.text_area if t.label=='Qué quieres conocer').set_value('valoración de su gestión')
            next(b for b in app.button if b.label=='Crear análisis y buscar menciones').click().run()
            self.assertFalse(list(app.exception))
            next(c for c in app.checkbox if c.label.startswith('He comprobado')).check()
            next(b for b in app.button if b.label=='Confirmar selección guardada').click().run()
            with patch('enfoques.clasificador',return_value=ModeloPrueba()):
                next(b for b in app.button if b.label=='Ejecutar o continuar este enfoque').click().run()
            self.assertFalse(list(app.exception))
            self.assertTrue(any(b.label=='Guardar revisión de este enfoque' for b in app.button))
            next(b for b in app.button if b.label=='Generar informe con todos los enfoques guardados').click().run()
            self.assertFalse(list(app.exception))
            self.assertIn('Análisis por persona y enfoque',(estudio/'informe_editorial.html').read_text(encoding='utf-8'))


if __name__=='__main__':
    unittest.main()
