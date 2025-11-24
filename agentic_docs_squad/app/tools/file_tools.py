import os
import time
import google.generativeai as genai

def ingest_multimedia_tool(file_path: str) -> str:
    """
    Sube un archivo a la API de Gemini y espera a que esté listo.
    Retorna el URI del archivo o un mensaje de error.
    """
    if not os.path.exists(file_path):
        return f"ERROR: El archivo {file_path} no existe en el sistema local."

    print(f"[Herramienta de Ingesta] Subiendo {file_path}...")
    try:
        # Subimos el archivo.
        file_upload = genai.upload_file(file_path)
        
        # Esperamos a que el procesamiento termine.
        while file_upload.state.name == "PROCESSING":
            print("[Herramienta de Ingesta] Procesando...", end=".", flush=True)
            time.sleep(10)
            file_upload = genai.get_file(file_upload.name)

        # Verificamos el estado final.
        if file_upload.state.name == "FAILED":
            print("\\n[Herramienta de Ingesta] Falló el procesamiento del archivo.")
            return "ERROR: Falló el procesamiento en Gemini."

        print(f"\\n[Herramienta de Ingesta] Archivo listo: {file_upload.uri}")
        return file_upload.uri
    except Exception as e:
        print(f"\\n[Herramienta de Ingesta] ERROR CRÍTICO: {str(e)}")
        return f"ERROR CRÍTICO: {str(e)}"
