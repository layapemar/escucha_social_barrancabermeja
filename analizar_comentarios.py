"""Clasifica comentarios en español sin enviar sus textos a una API externa."""

import os

# Evita que las bibliotecas numéricas reserven muchos hilos y memoria en Windows.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


ETIQUETAS = {"POS": "positivo", "NEG": "negativo", "NEU": "neutral"}
CAMPOS_OBLIGATORIOS = {"tema", "comentario"}


class ModeloLigero:
    """Ejecuta RoBERTuito sin crear el entrenador pesado de pysentimiento."""

    def __init__(self, carpeta_modelo: Path):
        import torch
        from pysentimiento.preprocessing import preprocess_tweet
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.preprocesar = preprocess_tweet
        self.tokenizador = AutoTokenizer.from_pretrained(carpeta_modelo)
        self.modelo = AutoModelForSequenceClassification.from_pretrained(
            carpeta_modelo,
            low_cpu_mem_usage=True,
            dtype=torch.float16,
        )
        self.modelo.eval()

    def predict(self, texto: str):
        from types import SimpleNamespace

        preparado = self.preprocesar(texto, lang="es")
        entradas = self.tokenizador(
            preparado, return_tensors="pt", truncation=True, max_length=128
        )
        with self.torch.inference_mode():
            logits = self.modelo(**entradas).logits.float()
            valores = self.torch.softmax(logits, dim=-1)[0].tolist()
        etiquetas = {
            int(indice): etiqueta for indice, etiqueta in self.modelo.config.id2label.items()
        }
        probabilidades = {etiquetas[indice]: valor for indice, valor in enumerate(valores)}
        etiqueta = max(probabilidades, key=probabilidades.get)
        return SimpleNamespace(output=etiqueta, probas=probabilidades)


def cargar_modelo(carpeta_modelo: Path):
    if not (carpeta_modelo / ".modelo_verificado").is_file():
        raise RuntimeError(
            "No está disponible el modelo local verificado. Ejecuta la preparación del proyecto."
        )
    return ModeloLigero(carpeta_modelo)


def leer_comentarios(ruta: Path) -> list[dict[str, str]]:
    if not ruta.is_file():
        raise FileNotFoundError(f"No encuentro el archivo: {ruta}")
    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        faltantes = CAMPOS_OBLIGATORIOS - set(lector.fieldnames or [])
        if faltantes:
            raise ValueError("Faltan columnas: " + ", ".join(sorted(faltantes)))
        filas = []
        for numero, fila in enumerate(lector, start=2):
            texto = (fila.get("comentario") or "").strip()
            if not texto:
                continue
            fila["comentario"] = texto
            fila["tema"] = (fila.get("tema") or "Sin tema").strip() or "Sin tema"
            fila["fila_origen"] = str(numero)
            filas.append(fila)
    if not filas:
        raise ValueError("El archivo no contiene comentarios con texto.")
    return filas


def analizar(filas: list[dict[str, str]], progreso=None) -> list[dict[str, str]]:
    carpeta_modelo = Path(__file__).resolve().parent / "modelos" / "robertuito"
    print("Cargando RoBERTuito en modo de memoria reducida...")
    modelo = cargar_modelo(carpeta_modelo)
    salida = []
    cache = {}
    for indice, fila in enumerate(filas, start=1):
        texto = fila['comentario']
        if texto not in cache:
            cache[texto] = modelo.predict(texto)
        prediccion = cache[texto]
        etiqueta = str(prediccion.output)
        probabilidades = prediccion.probas
        salida.append(
            {
                "tema": fila["tema"],
                "fecha": fila.get("fecha", ""),
                "post_id": fila.get("post_id", ""),
                "comment_id": fila.get("comment_id", ""),
                "comentario": fila["comentario"],
                "etiqueta_modelo": etiqueta,
                "interpretacion_inicial": ETIQUETAS.get(etiqueta, "desconocida"),
                "p_positivo": f"{probabilidades.get('POS', 0):.4f}",
                "p_negativo": f"{probabilidades.get('NEG', 0):.4f}",
                "p_neutral": f"{probabilidades.get('NEU', 0):.4f}",
                # La predicción queda como etiqueta final provisional. La persona
                # revisora solo necesita cambiar los casos en los que discrepa.
                "revision_humana": ETIQUETAS.get(etiqueta, "neutral"),
                "observaciones": "",
            }
        )
        print(f"Analizados: {indice}/{len(filas)}", end="\r")
        if progreso:
            progreso(indice, len(filas))
    print()
    return salida


def guardar_resultados(filas: list[dict[str, str]], carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    detalle = carpeta / "comentarios_analizados.csv"
    with detalle.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)

    conteos = defaultdict(Counter)
    for fila in filas:
        conteos[fila["tema"]][fila["interpretacion_inicial"]] += 1
    resumen = carpeta / "resumen_por_tema.csv"
    with resumen.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["tema", "comentarios", "positivos", "negativos", "neutrales"])
        for tema, cuenta in sorted(conteos.items()):
            escritor.writerow(
                [tema, sum(cuenta.values()), cuenta["positivo"], cuenta["negativo"], cuenta["neutral"]]
            )
    print(f"Detalle guardado en: {detalle.resolve()}")
    print(f"Resumen guardado en: {resumen.resolve()}")
    print("Revisa manualmente las etiquetas antes de sacar conclusiones.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Análisis inicial de sentimientos con RoBERTuito")
    parser.add_argument("archivo", type=Path, help="CSV con columnas tema y comentario")
    parser.add_argument("--salida", type=Path, default=Path("resultados"))
    argumentos = parser.parse_args()
    guardar_resultados(analizar(leer_comentarios(argumentos.archivo)), argumentos.salida)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        raise SystemExit(f"Error: {error}") from error
