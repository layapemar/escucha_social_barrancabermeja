"""Descarga comentarios de UNA publicación propia usando la API oficial de Meta."""

import csv
import getpass
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


VERSION_API = "v26.0"
LIMITE_COMENTARIOS = 200
PAGINA_ID_PREDETERMINADA = "124142061045473"  # Canal Telepetróleo
PALABRAS_VIAS = (
    "recuperacion vial, rehabilitacion vial, mantenimiento vial, obras viales, "
    "obra vial, pavimentacion, pavimentando, repavimentacion, malla vial, "
    "arreglo de vias, reparacion de vias, reparacion vial, mejoramiento vial, "
    "intervencion vial, mejoramiento de vias, construccion de vias, puente elevado"
)
MAX_PAGINAS_PUBLICACIONES = 20
SESION = requests.Session()
SESION.mount('https://', HTTPAdapter(max_retries=Retry(
    total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=['GET'], respect_retry_after_header=True,
)))


def consultar(ruta: str, token: str, parametros: dict | None = None) -> dict:
    url = f"https://graph.facebook.com/{VERSION_API}/{ruta.lstrip('/')}"
    respuesta = SESION.get(
        url,
        params=parametros,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    try:
        contenido = respuesta.json()
    except ValueError as error:
        tipo = respuesta.headers.get("Content-Type", "no indicado").split(";", 1)[0]
        traza = respuesta.headers.get("x-fb-trace-id", "no disponible")
        raise RuntimeError(
            f"Meta respondió sin JSON (HTTP {respuesta.status_code}; "
            f"tipo: {tipo}; tamaño: {len(respuesta.content)} bytes; "
            f"traza Meta: {traza}). "
            "No compartas el token. Verifica que copiaste únicamente el token "
            "de Página en el Explorador de la API Graph."
        ) from error
    if not respuesta.ok or "error" in contenido:
        mensaje = contenido.get("error", {}).get("message", respuesta.reason)
        raise RuntimeError(f"Meta rechazó la consulta (HTTP {respuesta.status_code}): {mensaje}")
    return contenido


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.casefold())
    return "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")


def buscar_publicaciones(token: str, pagina_id: str, palabras: list[str]) -> list[dict]:
    publicaciones = []
    siguiente = f"{pagina_id}/posts"
    parametros = {
        "fields": "id,message,created_time,comments.limit(0).summary(true)",
        "limit": 100,
    }
    paginas_revisadas = 0
    while siguiente and paginas_revisadas < MAX_PAGINAS_PUBLICACIONES:
        respuesta = consultar(siguiente, token, parametros)
        publicaciones.extend(respuesta.get("data", []))
        paginas_revisadas += 1
        url_siguiente = respuesta.get("paging", {}).get("next")
        if not url_siguiente:
            break
        partes = urlparse(url_siguiente)
        if partes.scheme != "https" or partes.hostname != "graph.facebook.com":
            raise RuntimeError("La dirección de paginación no es de Meta.")
        siguiente = partes.path.removeprefix(f"/{VERSION_API}/")
        parametros = {
            clave: valor[-1]
            for clave, valor in parse_qs(partes.query).items()
            if clave != "access_token"
        }
    coincidencias = []
    for publicacion in publicaciones:
        mensaje = normalizar(publicacion.get("message", ""))
        if any(
            re.search(rf"(?<!\w){re.escape(normalizar(palabra))}(?!\w)", mensaje)
            for palabra in palabras
        ):
            coincidencias.append(publicacion)
    return coincidencias


def interpretar_seleccion(entrada: str, cantidad: int) -> list[int]:
    partes = [parte.strip() for parte in entrada.split(",")]
    if not partes or any(not parte.isdigit() for parte in partes):
        return []
    indices = [int(parte) for parte in partes]
    if any(indice < 1 or indice > cantidad for indice in indices):
        return []
    return list(dict.fromkeys(indices))


def pedir_posts(token: str, pagina_id: str) -> list[str]:
    entrada = input(
        "Palabras para buscar publicaciones sobre vías "
        f"[{PALABRAS_VIAS}]; pulsa Enter para usar estas: "
    ).strip()
    palabras = [palabra.strip() for palabra in (entrada or PALABRAS_VIAS).split(",") if palabra.strip()]
    print("Buscando entre hasta 2.000 publicaciones recientes...")
    publicaciones = buscar_publicaciones(token, pagina_id, palabras)
    if not publicaciones:
        raise RuntimeError(
            "No se encontraron publicaciones con esas palabras entre las revisadas. "
            "Vuelve a ejecutar y prueba otras palabras."
        )
    publicaciones = publicaciones[:100]
    print("\nPublicaciones que coinciden con la búsqueda:")
    for indice, post in enumerate(publicaciones, 1):
        fragmento = post.get("message", "[publicación sin texto]").replace("\n", " ")[:150]
        total = post.get("comments", {}).get("summary", {}).get("total_count", "?")
        print(f"{indice}. [{total} comentarios] {post.get('created_time', '')}  {fragmento}")
    while True:
        opcion = input(
            "Elige uno o varios números separados por comas "
            f"(del 1 al {len(publicaciones)}): "
        ).strip()
        indices = interpretar_seleccion(opcion, len(publicaciones))
        if indices:
            return [publicaciones[indice - 1]["id"] for indice in indices]
        print("Ejemplo válido: 2 o 2,5,8")


def descargar(token: str, post_id: str, limite: int = LIMITE_COMENTARIOS) -> list[dict[str, str]]:
    comentarios = []
    siguiente = f"{post_id}/comments"
    parametros = {"fields": "id,message,created_time", "limit": 100}
    vistos = set()
    while siguiente and len(comentarios) < limite:
        pagina = consultar(siguiente, token, parametros)
        for item in pagina.get("data", []):
            texto = (item.get("message") or "").strip()
            if texto and item.get('id') not in vistos:
                vistos.add(item.get('id'))
                comentarios.append(
                    {
                        "tema": "", "comentario": texto,
                        "fecha": item.get("created_time", ""),
                        "post_id": post_id, "comment_id": item.get("id", ""),
                    }
                )
            if len(comentarios) >= limite:
                break
        # Meta proporciona una URL de paginación. La usamos solo si apunta a su dominio.
        url_siguiente = pagina.get("paging", {}).get("next")
        if url_siguiente:
            partes = urlparse(url_siguiente)
            if partes.scheme != "https" or partes.hostname != "graph.facebook.com":
                raise RuntimeError("La dirección de paginación no es de Meta.")
            # No reenviamos el token por URL: se conserva únicamente en la cabecera.
            siguiente = partes.path.removeprefix(f"/{VERSION_API}/")
            parametros = {k: v[-1] for k, v in parse_qs(partes.query).items() if k != "access_token"}
        else:
            siguiente = ""
        print(f"Comentarios obtenidos: {len(comentarios)}", end="\r")
    print()
    return comentarios


def main() -> None:
    print("La clave se escribe aquí, no se guarda en archivos ni se muestra en pantalla.")
    token = getpass.getpass("Pega tu token de acceso de Página: ").strip()
    if not token:
        raise RuntimeError("No se introdujo ningún token.")
    pagina_id = input(
        f"ID de Canal Telepetróleo [{PAGINA_ID_PREDETERMINADA}]; pulsa Enter para usarlo: "
    ).strip() or PAGINA_ID_PREDETERMINADA
    if not pagina_id.isdigit():
        raise RuntimeError("El ID de Página debe contener solo números.")
    identidad = consultar("me", token, {"fields": "id,name"})
    if identidad.get("id") != pagina_id:
        raise RuntimeError(
            "El token no corresponde a esta Página. En el Explorador de Meta "
            "elige 'Canal Telepetróleo' en 'Usuario o página' y copia su token de Página."
        )
    print(f"Conexión comprobada con la Página: {identidad.get('name', pagina_id)}")
    tema = input("Tema para esta noticia (por ejemplo, movilidad): ").strip() or "Sin tema"
    post_ids = pedir_posts(token, pagina_id)
    filas = []
    for numero, post_id in enumerate(post_ids, 1):
        print(f"\nDescargando publicación {numero} de {len(post_ids)}...")
        filas.extend(descargar(token, post_id))
    if not filas:
        raise RuntimeError("No se recibieron comentarios con texto de las publicaciones elegidas.")
    for fila in filas:
        fila["tema"] = tema
    destino = Path("datos/privados")
    destino.mkdir(parents=True, exist_ok=True)
    if len(post_ids) == 1:
        nombre = f"comentarios_{post_ids[0].replace('_', '-')}.csv"
    else:
        momento = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre = f"comentarios_{len(post_ids)}_publicaciones_{momento}.csv"
    archivo = destino / nombre
    with archivo.open("w", encoding="utf-8-sig", newline="") as salida:
        escritor = csv.DictWriter(salida, fieldnames=["tema", "comentario", "fecha", "post_id", "comment_id"])
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"Guardados {len(filas)} comentarios en: {archivo.resolve()}")
    print("El programa no extrajo nombres de las personas ni sus perfiles.")


if __name__ == "__main__":
    try:
        main()
    except (requests.RequestException, RuntimeError) as error:
        sys.exit(f"Error: {error}")
