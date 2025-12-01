from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import re
import os
import shutil # Para manejar archivos temporales

from app.config import configure_environment
from app.orchestrator import create_orchestrator, Orchestrator

# --- Pydantic Models for API ---
class PipelineRequest(BaseModel):
    # El prompt del usuario, e.g., "documenta el video en /path/to/my_video.mp4"
    user_prompt: str
    user_context: str | None = None

class PipelineResponse(BaseModel):
    document: str

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Agentic Docs Squad API",
    description="Una API para generar documentación técnica a partir de archivos multimedia.",
    version="1.0.0"
)

# --- Orchestrator Initialization ---
orchestrator: Orchestrator | None = None

# Directorio temporal para archivos subidos
TEMPORARY_UPLOAD_DIR = "/tmp/agentic_docs_uploads"

@app.on_event("startup")
def startup_event():
    """
    Configura el entorno y el orquestador al iniciar la aplicación.
    """
    global orchestrator
    print("🚀 Configurando el entorno y el orquestador...")
    configure_environment()
    orchestrator = create_orchestrator()
    # Asegúrate de que el directorio temporal exista
    os.makedirs(TEMPORARY_UPLOAD_DIR, exist_ok=True)
    print("✅ Orquestador y directorio temporal listos.")

def extract_path_from_prompt(prompt: str) -> str | None:
    """
    Extrae la primera ruta de archivo que parece válida de un prompt.
    Admite rutas con espacios (si están entre comillas) y caracteres variados.
    """
    # Regex mejorado: busca rutas entre comillas (opcionales) o sin ellas.
    # Soporta una gama más amplia de caracteres en nombres de archivo/directorio.
    match = re.search(r'["\']?([a-zA-Z0-9_./\\ -]+\.[a-zA-Z0-9_]+)["\']?', prompt)
    if match:
        # Devuelve el grupo de captura que contiene la ruta limpia.
        return match.group(1).strip()
    return None

# --- API Endpoints ---
@app.post("/document/run", response_model=PipelineResponse)
async def run_documentation_pipeline(request: PipelineRequest):
    """
    Recibe una ruta a un archivo (local en el servidor) y ejecuta el pipeline de documentación completo.
    """
    if not orchestrator:
        raise HTTPException(status_code=500, detail="El orquestador no está inicializado.")

    # Extraer la ruta del archivo desde el prompt del usuario
    print(f"🕵️  Buscando ruta en el prompt: '{request.user_prompt}'")
    file_path = extract_path_from_prompt(request.user_prompt)
    
    if not file_path:
        raise HTTPException(
            status_code=400,
            detail="No se pudo encontrar una ruta de archivo válida en el prompt. "
                   "Por favor, incluye la ruta al archivo que quieres documentar (ej: 'documenta /path/to/my_file.pdf')."
        )
    
    print(f"✅ Ruta extraída: '{file_path}'")


    try:
        final_document = await orchestrator.run_pipeline(
            file_path=file_path,
            user_context=request.user_context or ""
        )
        
        if "ERROR" in final_document or "Falló" in final_document:
             raise HTTPException(status_code=500, detail=final_document)

        return PipelineResponse(document=final_document)

    except Exception as e:
        print(f"💥 Error inesperado en el pipeline: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")

@app.post("/document/upload_and_run", response_model=PipelineResponse)
async def upload_and_run_documentation_pipeline(
    file: UploadFile = File(...),
    user_context: str | None = Form(None)
):
    """
    Sube un archivo directamente y ejecuta el pipeline de documentación completo.
    """
    if not orchestrator:
        raise HTTPException(status_code=500, detail="El orquestador no está inicializado.")

    # Crear una ruta temporal para guardar el archivo
    temp_file_path = os.path.join(TEMPORARY_UPLOAD_DIR, file.filename)
    
    try:
        # Guardar el archivo subido temporalmente
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print(f"💾 Archivo subido temporalmente guardado en: {temp_file_path}")

        # Ejecutar el pipeline con la ruta del archivo temporal
        final_document = await orchestrator.run_pipeline(
            file_path=temp_file_path,
            user_context=user_context or ""
        )
        
        if "ERROR" in final_document or "Falló" in final_document:
             raise HTTPException(status_code=500, detail=final_document)

        return PipelineResponse(document=final_document)

    except Exception as e:
        print(f"💥 Error inesperado en el pipeline de subida: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")
    finally:
        # Limpiar el archivo temporal
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print(f"🗑️ Archivo temporal eliminado: {temp_file_path}")

@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API de Agentic Docs Squad. Usa el endpoint /document/run o /document/upload_and_run."}

# --- Para ejecutar localmente ---
if __name__ == "__main__":
    import uvicorn
    # Inicia la aplicación. Crea un archivo .env o exporta la variable GOOGLE_API_KEY
    # y luego ejecuta: python -m app.main
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
