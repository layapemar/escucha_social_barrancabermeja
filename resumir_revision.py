"""Valida la revisión humana y genera el resumen final del análisis."""

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


ETIQUETAS_VALIDAS = {"positivo", "negativo", "neutral"}
ALIASES = {
    "positiva": "positivo",
    "negativa": "negativo",
    "neutro": "neutral",
}


def normalizar_etiqueta(valor: str) -> str:
    etiqueta = (valor or "").strip().lower()
    return ALIASES.get(etiqueta, etiqueta)


def leer_revision(ruta: Path) -> list[dict[str, str]]:
    if not ruta.is_file():
        raise FileNotFoundError(f"No encuentro el archivo: {ruta}")

    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        requeridas = {"tema", "interpretacion_inicial", "revision_humana"}
        faltantes = requeridas - set(lector.fieldnames or [])
        if faltantes:
            raise ValueError("Faltan columnas: " + ", ".join(sorted(faltantes)))
        filas = list(lector)

    if not filas:
        raise ValueError("El archivo no contiene comentarios.")

    errores = []
    for numero, fila in enumerate(filas, start=2):
        etiqueta = normalizar_etiqueta(fila.get("revision_humana", ""))
        if not etiqueta:
            errores.append(f"fila {numero}: revisión vacía")
        elif etiqueta not in ETIQUETAS_VALIDAS:
            errores.append(f"fila {numero}: etiqueta '{etiqueta}' no reconocida")
        fila["revision_humana"] = etiqueta
        fila["interpretacion_inicial"] = normalizar_etiqueta(
            fila.get("interpretacion_inicial", "")
        )
        fila["tema"] = (fila.get("tema") or "Sin tema").strip() or "Sin tema"

    if errores:
        muestra = "; ".join(errores[:10])
        adicional = "" if len(errores) <= 10 else f"; y {len(errores) - 10} más"
        raise ValueError(
            "Completa o corrige la columna revision_humana antes de continuar: "
            + muestra
            + adicional
        )
    return filas


def resumir_por_tema(filas: list[dict[str, str]]) -> list[dict[str, str | int]]:
    grupos = defaultdict(list)
    for fila in filas:
        grupos[fila["tema"]].append(fila)

    resumen = []
    for tema, grupo in sorted(grupos.items()):
        humanas = Counter(fila["revision_humana"] for fila in grupo)
        modelo = Counter(fila["interpretacion_inicial"] for fila in grupo)
        coincidencias = sum(
            fila["revision_humana"] == fila["interpretacion_inicial"] for fila in grupo
        )
        total = len(grupo)
        resumen.append(
            {
                "tema": tema,
                "comentarios_revisados": total,
                "humanos_positivos": humanas["positivo"],
                "humanos_negativos": humanas["negativo"],
                "humanos_neutrales": humanas["neutral"],
                "porcentaje_positivo": f"{100 * humanas['positivo'] / total:.1f}",
                "porcentaje_negativo": f"{100 * humanas['negativo'] / total:.1f}",
                "porcentaje_neutral": f"{100 * humanas['neutral'] / total:.1f}",
                "modelo_positivos": modelo["positivo"],
                "modelo_negativos": modelo["negativo"],
                "modelo_neutrales": modelo["neutral"],
                "coincidencias_modelo_humano": coincidencias,
                "correcciones_humanas": total - coincidencias,
                "acuerdo_porcentaje": f"{100 * coincidencias / total:.1f}",
            }
        )
    return resumen


def comparar_etiquetas(filas: list[dict[str, str]]) -> list[dict[str, str | int]]:
    conteos = Counter(
        (fila["interpretacion_inicial"], fila["revision_humana"]) for fila in filas
    )
    return [
        {
            "etiqueta_modelo": modelo,
            "revision_humana": humana,
            "comentarios": cantidad,
        }
        for (modelo, humana), cantidad in sorted(conteos.items())
    ]


def guardar_csv(ruta: Path, filas: list[dict[str, str | int]]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resume las etiquetas corregidas por una persona"
    )
    parser.add_argument(
        "archivo",
        nargs="?",
        type=Path,
        default=Path("resultados/comentarios_analizados.csv"),
    )
    parser.add_argument("--salida", type=Path, default=Path("resultados"))
    argumentos = parser.parse_args()

    filas = leer_revision(argumentos.archivo)
    resumen = resumir_por_tema(filas)
    comparacion = comparar_etiquetas(filas)
    ruta_resumen = argumentos.salida / "resumen_revision_humana.csv"
    ruta_comparacion = argumentos.salida / "comparacion_modelo_revision.csv"
    guardar_csv(ruta_resumen, resumen)
    guardar_csv(ruta_comparacion, comparacion)

    total = len(filas)
    humanas = Counter(fila["revision_humana"] for fila in filas)
    coincidencias = sum(
        fila["revision_humana"] == fila["interpretacion_inicial"] for fila in filas
    )
    print(f"Revisión humana validada: {total}/{total} comentarios.")
    print(
        "Resultado corregido: "
        f"{humanas['positivo']} positivos, "
        f"{humanas['negativo']} negativos y "
        f"{humanas['neutral']} neutrales."
    )
    print(
        f"Modelo y revisión coincidieron en {coincidencias}/{total} "
        f"({100 * coincidencias / total:.1f}%)."
    )
    print(f"Resumen final guardado en: {ruta_resumen.resolve()}")
    print(f"Comparación guardada en: {ruta_comparacion.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(f"Error: {error}") from error
