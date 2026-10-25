"""Invariantes de atribución, bases y persistencia de análisis por enfoque."""
import csv
import tempfile
import unittest
from pathlib import Path

import enfoques as e
import observatorio as obs
from informe_editorial import crear_html


class ModeloPrueba:
    def __call__(self,texto,candidate_labels,**kwargs):
        return dict(labels=candidate_labels,scores=[.85,.05,.05,.05])


class Enfoques(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.ruta=Path(self.tmp.name)/'comentarios_analizados.csv'
        self.filas=[dict(comentario=t,tema='Estudio',interpretacion_inicial='positivo',revision_humana='positivo',post_id='1_1')
                    for t in ['Kellyn hizo una buena gestión','Leonardo no hizo nada','Kellyn y Leonardo tienen opiniones distintas','Ella trabajó bien']]
        with self.ruta.open('w',encoding='utf-8',newline='') as f:
            escritor=csv.DictWriter(f,fieldnames=list(self.filas[0]))
            escritor.writeheader()
            escritor.writerows(self.filas)

    def tearDown(self):
        self.tmp.cleanup()

    def crear(self,nombre='Kellyn',enfoque='Valoración de la gestión'):
        return e.crear(self.ruta,nombre,[],enfoque)

    def ejecutar(self,a):
        e.seleccionar(self.ruta,a['id'],a['seleccion'],True)
        return e.ejecutar(self.ruta,a['id'],fabrica=lambda _:ModeloPrueba())

    def test_menciones_limites_tildes_y_ambiguedad(self):
        self.assertEqual(e.menciones('Con VÁSQUEZ sí',['Vasquez']),['Vasquez'])
        self.assertEqual(e.menciones('Kellyna no es Kelly',['Kellyn']),[])
        self.assertEqual(e.menciones('Ella trabajó bien',['Kellyn']),[])

    def test_evidencia_mixta_ausente_y_ambigua(self):
        self.assertEqual(e.decidir({'apoyo':.9,'rechazo':.8}),'mixta')
        self.assertEqual(e.decidir({'apoyo':.55,'rechazo':.5}),'indeterminada')
        self.assertEqual(e.decidir({'apoyo':.6952,'rechazo':.6282}),'indeterminada')
        self.assertEqual(e.decidir({'apoyo':.1,'rechazo':.2}),'sin postura explícita')

    def test_enfoque_libre_y_validacion(self):
        a=e.crear(self.ruta,'servicio de agua',['acueducto'],'valoración sobre continuidad del suministro')
        self.assertEqual(a['enfoque'],'valoración sobre continuidad del suministro')
        self.assertIn('servicio de agua',a['objetivo'])
        with self.assertRaises(ValueError):
            e.crear(self.ruta,'servicio de agua',[],'  ')

    def test_enfoques_independientes_y_denominadores_solapados(self):
        a=self.ejecutar(self.crear())
        b=self.ejecutar(self.crear('Kellyn','Respaldo a una candidatura'))
        c=self.ejecutar(self.crear('Leonardo'))
        self.assertNotEqual(a['id'],b['id'])
        self.assertNotEqual(e.hipotesis(a),e.hipotesis(b))
        self.assertEqual(e.resumen(a)['comentarios'],2)
        self.assertEqual(e.resumen(a)['porcentaje_estudio'],50)
        self.assertEqual(e.resumen(a)['apoyo_pct'],100)
        self.assertIn('2',set(a['seleccion']) & set(c['seleccion']))
        self.assertEqual(len(e.vigentes(self.ruta)),3)
        self.assertIn('Base específica',e.seccion_html(self.ruta))

    def test_confirmacion_revision_reanudacion_y_reinclusion(self):
        a=self.crear()
        with self.assertRaises(ValueError):
            e.ejecutar(self.ruta,a['id'],fabrica=lambda _:ModeloPrueba())
        a=self.ejecutar(a)
        e.revisar(self.ruta,a['id'],{'0':dict(postura_final='rechazo',nota_revision='ironía')})
        e.seleccionar(self.ruta,a['id'],['2'],True)
        e.seleccionar(self.ruta,a['id'],['0','2','3'],True)
        llamadas=[]
        class Modelo(ModeloPrueba):
            def __call__(self,texto,**kwargs):
                llamadas.append(texto)
                return super().__call__(texto,**kwargs)
        actualizado=e.ejecutar(self.ruta,a['id'],fabrica=lambda _:Modelo())
        self.assertEqual(llamadas,['Ella trabajó bien'])
        self.assertEqual(actualizado['filas'][0]['postura_final'],'rechazo')
        self.assertTrue(actualizado['filas'][0]['postura_revisada'])

    def test_datos_modificados_invalidan_sin_perder_historico(self):
        a=self.ejecutar(self.crear())
        with self.ruta.open('a',encoding='utf-8') as f:
            f.write('\n')
        self.assertEqual(e.vigentes(self.ruta),[])
        with self.assertRaises(ValueError):
            e.seleccionar(self.ruta,a['id'],['0'])
        self.assertEqual(len(e.cargar(self.ruta)['analisis']),1)

    def test_abstencion_informe_escapado_y_no_modifica_origen(self):
        firma=obs.huella(self.ruta)
        a=self.crear('<script>Kellyn</script>')
        e.seleccionar(self.ruta,a['id'],['0'],True)
        class Ambiguo:
            def __call__(self,texto,candidate_labels,**kwargs):
                return dict(labels=candidate_labels,scores=[.45,.4,.1,.05])
        a=e.ejecutar(self.ruta,a['id'],fabrica=lambda _:Ambiguo())
        self.assertEqual(a['filas'][0]['postura_final'],'indeterminada')
        reporte=crear_html(self.filas,self.ruta.parent/'informe.html')
        texto=reporte.read_text(encoding='utf-8')
        self.assertNotIn('<script>Kellyn</script>',texto)
        self.assertIn('Análisis por persona y enfoque',texto)
        self.assertEqual(obs.huella(self.ruta),firma)

    def test_interrupcion_reanuda_sin_repetir_procesados(self):
        a=self.crear()
        e.seleccionar(self.ruta,a['id'],a['seleccion'],True)
        class Interrumpido(ModeloPrueba):
            def __call__(self,texto,**kwargs):
                if 'y Leonardo' in texto:
                    raise RuntimeError('interrupción simulada')
                return super().__call__(texto,**kwargs)
        with self.assertRaises(RuntimeError):
            e.ejecutar(self.ruta,a['id'],fabrica=lambda _:Interrumpido())
        parcial=e.obtener(e.cargar(self.ruta),a['id'])
        self.assertEqual(len(parcial['filas']),1)
        terminado=e.ejecutar(self.ruta,a['id'],fabrica=lambda _:ModeloPrueba())
        self.assertEqual(terminado['estado'],'completo')
        self.assertEqual(len(terminado['filas']),2)


if __name__=='__main__':
    unittest.main()
