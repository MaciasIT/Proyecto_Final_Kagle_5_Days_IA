import os
import time
import magic
import google.generativeai as genai

# Diccionario de tipos MIME soportados para evitar suposiciones
SUPPORTED_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".py": "text/x-python",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".json": "application/json",
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    # Formatos de audio
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    # Formatos de video
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    # Formatos de imagen
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
}

def ingest_multimedia_tool(file_path: str) -> str:
    """
    Sube un archivo a la API de Gemini, con detección de tipo MIME, 
    y espera a que esté listo.
    Retorna el URI del archivo o un mensaje de error.
    """
    if not os.path.exists(file_path):
        return f"ERROR: El archivo {file_path} no existe en el sistema local."

    # 1. Detección del tipo MIME
    file_extension = os.path.splitext(file_path)[1].lower()
    mime_type = SUPPORTED_MIME_TYPES.get(file_extension)

    if not mime_type:
        try:
            # Plan B: usar python-magic si el tipo no está en nuestro diccionario
            mime_type = magic.from_file(file_path, mime=True)
            print(f"[Herramienta de Ingesta] Tipo MIME detectado con python-magic: {mime_type}")
        except Exception as e:
            return f"ERROR: Tipo de archivo no soportado y no se pudo detectar con 'magic': {str(e)}"

    print(f"[Herramienta de Ingesta] Subiendo {file_path} (Tipo: {mime_type})...")
    
    try:
        # 2. Subida del archivo con el tipo MIME explícito
        file_upload = genai.upload_file(path=file_path, mime_type=mime_type)
        
        # 3. Espera activa del procesamiento
        while file_upload.state.name == "PROCESSING":
            print("[Herramienta de Ingesta] Procesando...", end=".", flush=True)
            time.sleep(10)
            file_upload = genai.get_file(file_upload.name)

        # 4. Verificación del estado final
        if file_upload.state.name == "FAILED":
            print("\\n[Herramienta de Ingesta] Falló el procesamiento del archivo.")
            return "ERROR: Falló el procesamiento en Gemini."

        print(f"\\n[Herramienta de Ingesta] Archivo listo: {file_upload.uri}")
        return file_upload.uri

    except Exception as e:
        print(f"\\n[Herramienta de Ingesta] ERROR CRÍTICO: {str(e)}")
        return f"ERROR CRÍTICO: {str(e)}"
