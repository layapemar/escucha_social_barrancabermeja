"""Pruebas de modelos complementarios sobre estudios existentes."""
import csv
import io
from pathlib import Path

import pandas as pd
import streamlit as st

from analizar_comentarios import ModeloLigero

BASE = Path(__file__).resolve().parents[1]
MODELOS = {
    "Emociones": "pysentimiento/robertuito-emotion-analysis",
    "Ironía": "pysentimiento/robertuito-irony",
}
TRADUCCION = {"others": "otras / sin emoción específica", "joy": "alegría",
              "sadness": "tristeza", "anger": "enojo", "surprise": "sorpresa",
              "disgust": "disgusto", "fear": "miedo"}

st.set_page_config(page_title="Laboratorio de escucha social", layout="wide")
st.title("Laboratorio de emociones e ironía")
st.write("Explora nuevas dimensiones de los comentarios. Son predicciones experimentales, pendientes de evaluación con lenguaje local.")
st.caption("Los resultados no cambian tus etiquetas de sentimiento ni el informe aprobado. Una emoción expresada no es un diagnóstico de la persona.")
archivos = sorted((BASE / "datos/privados/estudios").glob("*/comentarios_analizados.csv"), reverse=True)
if not archivos:
    st.info("Primero crea un estudio desde la aplicación principal.")
    st.stop()

def nombre(ruta):
    tema = ruta.parent / "tema.txt"
    return f"{ruta.parent.name} · {tema.read_text(encoding='utf-8') if tema.exists() else 'Sin tema'}"

ruta = st.selectbox("Estudio guardado", archivos, format_func=nombre)
tarea = st.radio("Análisis complementario", list(MODELOS), horizontal=True)
st.caption(f"Modelo: {MODELOS[tarea]}. La primera ejecución descarga sus archivos de Hugging Face; los textos se procesan localmente.")
limite = st.number_input("Comentarios para esta prueba (en orden del archivo)", min_value=1, max_value=5000, value=30)
st.write("Prueba primero con 30 comentarios y compara las etiquetas con tu lectura. La ironía sirve para señalar casos que requieren contexto; no invierte automáticamente el sentimiento.")
if st.button("Ejecutar prueba", type="primary"):
    st.session_state.pop("laboratorio_resultado", None)
    try:
        with ruta.open(encoding="utf-8-sig", newline="") as archivo:
            filas = [f for f in csv.DictReader(archivo) if (f.get("comentario") or "").strip()][:int(limite)]
        if not filas:
            raise ValueError("No hay comentarios con texto en este estudio.")
        with st.spinner("Preparando modelo y procesando comentarios..."):
            modelo = ModeloLigero(MODELOS[tarea])
            barra = st.progress(0)
            salida, cache = [], {}
            for i, fila in enumerate(filas):
                texto = fila["comentario"]
                if texto not in cache:
                    cache[texto] = modelo.predict(texto)
                pred = cache[texto]
                salida.append({"comentario": texto,
                    "sentimiento_guardado": fila.get("revision_humana", ""),
                    "prediccion": TRADUCCION.get(pred.output, pred.output),
                    "etiqueta_original": pred.output,
                    "puntuacion": pred.probas[pred.output],
                    "modelo": MODELOS[tarea],
                    "revision_modelo": getattr(modelo.modelo.config, "_commit_hash", "") or "no disponible",
                    "comment_id": fila.get("comment_id", ""),
                    "post_id": fila.get("post_id", "")})
                barra.progress((i + 1) / len(filas))
            del modelo
        st.session_state.laboratorio_resultado = (str(ruta), tarea, int(limite), salida)
    except Exception as error:
        st.error(f"No se completó la prueba: {type(error).__name__}: {error}")

resultado = st.session_state.get("laboratorio_resultado")
if resultado and resultado[:3] == (str(ruta), tarea, int(limite)):
    df = pd.DataFrame(resultado[3])
    st.caption(f"Base del resultado: {len(df)} comentarios. Puntuación es la salida del modelo, no una precisión validada.")
    cuenta = df["prediccion"].value_counts().rename_axis("Categoría").reset_index(name="Comentarios")
    cuenta["Porcentaje"] = (100 * cuenta["Comentarios"] / len(df)).round(1)
    st.dataframe(cuenta, hide_index=True)
    st.dataframe(df[["comentario", "sentimiento_guardado", "prediccion", "puntuacion"]], hide_index=True, use_container_width=True)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    st.download_button("Descargar resultados experimentales", buffer.getvalue().encode("utf-8-sig"), "laboratorio_resultados.csv", "text/csv")
