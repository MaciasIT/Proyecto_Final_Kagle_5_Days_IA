from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import re

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

@app.on_event("startup")
def startup_event():
    """
    Configura el entorno y el orquestador al iniciar la aplicación.
    """
    global orchestrator
    print("🚀 Configurando el entorno y el orquestador...")
    configure_environment()
    orchestrator = create_orchestrator()
    print("✅ Orquestador listo.")

def extract_path_from_prompt(prompt: str) -> str | None:
    """
    Extrae la primera ruta de archivo que parece válida de un prompt.
    Busca patrones como /path/to/file.ext, ./path/to/file.ext, etc.
    """
    # Regex para encontrar rutas de archivo (simplificado)
    match = re.search(r'([\.\/\w-]+\.[\w]+)', prompt)
    if match:
        return match.group(1)
    return None

# --- API Endpoints ---
@app.post("/document/run", response_model=PipelineResponse)
async def run_documentation_pipeline(request: PipelineRequest):
    """
    Recibe una ruta a un archivo y ejecuta el pipeline de documentación completo.
    """
    if not orchestrator:
        raise HTTPException(status_code=500, detail="El orquestador no está inicializado.")

    # Extraer la ruta del archivo desde el prompt del usuario
    file_path = extract_path_from_prompt(request.user_prompt)
    if not file_path:
        raise HTTPException(
            status_code=400,
            detail="No se pudo encontrar una ruta de archivo válida en el prompt. "
                   "Por favor, incluye la ruta al archivo que quieres documentar."
        )

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


@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API de Agentic Docs Squad. Usa el endpoint /document/run."}

# --- Para ejecutar localmente ---
if __name__ == "__main__":
    import uvicorn
    # Inicia la aplicación. Crea un archivo .env o exporta la variable GOOGLE_API_KEY
    # y luego ejecuta: python -m app.main
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
