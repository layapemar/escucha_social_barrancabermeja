"""Pruebas sin descargar el modelo ni conectarse a Facebook."""

import csv
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import analizar_comentarios as analisis
import descargar_comentarios as facebook
import resumir_revision as revision
import informe_editorial as editorial


class ModeloFalso:
    def predict(self, texto):
        if "bien" in texto:
            return types.SimpleNamespace(output="POS", probas={"POS": .8, "NEG": .1, "NEU": .1})
        return types.SimpleNamespace(output="NEG", probas={"POS": .1, "NEG": .7, "NEU": .2})


class PruebasProyecto(unittest.TestCase):
    def test_filtra_tildes_y_palabras_vacias(self):
        filas = [{'comentario': 'más está nada esos bien dos hacer todos drones seguridad'}] * 3
        expresiones = dict(editorial.recurrencias(filas, 50))
        for palabra in ('más', 'está', 'nada', 'esos', 'bien', 'dos', 'hacer', 'todos'):
            self.assertNotIn(palabra, expresiones)
        self.assertTrue(any('drones' in expresion for expresion in expresiones))

    def test_grafica_cantidades_y_porcentajes(self):
        from collections import Counter
        texto = editorial.grafica(Counter({'negativo': 3, 'positivo': 1}), 4)
        import re
        visible = re.sub('<[^>]+>', '', texto)
        self.assertIn('3 · 75.0%', visible)
        self.assertIn('1 · 25.0%', visible)

    def test_preguntas_sin_duplicados_y_maximo_diez(self):
        filas = [{'comentario': f'¿Cuándo inicia la obra {i}?', 'post_id': str(i % 2)} for i in range(14)]
        filas += [filas[0], {'comentario': 'Sin pregunta', 'post_id': 'a'}]
        muestra = editorial.muestra_preguntas(filas)
        self.assertEqual(len(muestra), 10)
        self.assertEqual(len({f['comentario'] for f in muestra}), 10)
        self.assertNotEqual(muestra[0]['post_id'], muestra[1]['post_id'])

    def test_recurrencias_cuenta_comentarios_no_repeticiones(self):
        filas = [{'comentario': 'hospital hospital sin atención'}, {'comentario': 'hospital sin atención'}]
        encontrados = editorial.recurrencias(filas)
        self.assertTrue(any('hospital' in texto and n == 2 for texto,n in encontrados))

    def test_informe_editorial_no_ejecuta_texto_y_exige_aprobar_ejemplos(self):
        filas = [{'tema': '<script>alert(1)</script>', 'comentario': 'Mala atención', 'post_id': 'p1', 'revision_humana': 'negativo'}]
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporal:
            ruta = editorial.crear_html(filas, Path(temporal) / 'informe.html')
            texto = ruta.read_text(encoding='utf-8')
            self.assertNotIn('<script>', texto)
            self.assertIn('Selección automática', texto)
            self.assertIn('Mala atención', texto)
            self.assertIn('Sin comentarios de esta categoría', texto)

    def test_lectura_y_resultados(self):
        ruta = Path(__file__).parent / "datos" / "ejemplo_comentarios.csv"
        filas = analisis.leer_comentarios(ruta)
        self.assertEqual(len(filas), 6)
        with patch.object(analisis, "cargar_modelo", return_value=ModeloFalso()):
            salida = analisis.analizar(filas)
        self.assertEqual(salida[0]["etiqueta_modelo"], "POS")
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporal:
            analisis.guardar_resultados(salida, Path(temporal))
            with (Path(temporal) / "resumen_por_tema.csv").open(encoding="utf-8-sig") as archivo:
                resumen = list(csv.DictReader(archivo))
        self.assertEqual(sum(int(fila["comentarios"]) for fila in resumen), 6)

    def test_descarga_con_paginacion_y_sin_autores(self):
        respuestas = [
            {"data": [{"id": "c1", "message": "Muy bien", "created_time": "hoy"}],
             "paging": {"next": "https://graph.facebook.com/v26.0/p1/comments?after=abc"}},
            {"data": [{"id": "c2", "message": "Muy mal", "created_time": "hoy"}]},
        ]
        with patch.object(facebook, "consultar", side_effect=respuestas):
            filas = facebook.descargar("secreto", "p1")
        self.assertEqual(len(filas), 2)
        self.assertNotIn("author", filas[0])

    def test_error_no_json_no_expone_token(self):
        respuesta = types.SimpleNamespace(
            status_code=400,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=b"token-secreto en respuesta inesperada",
            json=lambda: (_ for _ in ()).throw(ValueError("No es JSON")),
        )
        with patch.object(facebook.SESION, "get", return_value=respuesta):
            with self.assertRaises(RuntimeError) as captura:
                facebook.consultar("me", "token-secreto", {"fields": "id,name"})
        mensaje = str(captura.exception)
        self.assertIn("tipo: text/html", mensaje)
        self.assertNotIn("token-secreto", mensaje)

    def test_busqueda_de_publicaciones_ignora_tildes(self):
        respuesta = {
            "data": [
                {"id": "p1", "message": "Inicia la pavimentación de una vía", "created_time": "hoy"},
                {"id": "p2", "message": "Festival cultural", "created_time": "hoy"},
                {"id": "p3", "message": "La novia llegó al evento", "created_time": "hoy"},
            ]
        }
        with patch.object(facebook, "consultar", return_value=respuesta):
            publicaciones = facebook.buscar_publicaciones(
                "secreto", "pagina", ["pavimentacion", "via"]
            )
        self.assertEqual([publicacion["id"] for publicacion in publicaciones], ["p1"])

    def test_seleccion_de_varias_publicaciones(self):
        self.assertEqual(facebook.interpretar_seleccion("2, 5,2", 8), [2, 5])
        self.assertEqual(facebook.interpretar_seleccion("2,9", 8), [])

    def test_resumen_de_revision_humana(self):
        filas = [
            {
                "tema": "vías",
                "interpretacion_inicial": "neutral",
                "revision_humana": "negativo",
            },
            {
                "tema": "vías",
                "interpretacion_inicial": "positivo",
                "revision_humana": "positivo",
            },
        ]
        resumen = revision.resumir_por_tema(filas)[0]
        self.assertEqual(resumen["comentarios_revisados"], 2)
        self.assertEqual(resumen["humanos_negativos"], 1)
        self.assertEqual(resumen["correcciones_humanas"], 1)
        self.assertEqual(resumen["acuerdo_porcentaje"], "50.0")

    def test_revision_incompleta_se_detiene(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporal:
            ruta = Path(temporal) / "revision.csv"
            with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
                escritor = csv.DictWriter(
                    archivo,
                    fieldnames=["tema", "interpretacion_inicial", "revision_humana"],
                )
                escritor.writeheader()
                escritor.writerow(
                    {
                        "tema": "vías",
                        "interpretacion_inicial": "neutral",
                        "revision_humana": "",
                    }
                )
            with self.assertRaises(ValueError):
                revision.leer_revision(ruta)

if __name__ == "__main__":
    unittest.main()
