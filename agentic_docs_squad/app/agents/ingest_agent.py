from google.adk.agents.llm_agent import Agent
from app.tools.file_tools import ingest_multimedia_tool

def create_ingest_agent() -> Agent:
    """Crea y retorna el IngestAgent."""
    return Agent(
        model='gemini-flash-latest',
        name='IngestAgent',
        description="Gestiona la carga de archivos multimedia.",
        instruction="""
        Eres el IngestAgent. Tu único trabajo es recibir rutas de archivos locales 
        y subirlos usando la herramienta 'ingest_multimedia_tool'.
        Una vez tengas el URI del archivo, devuélvelo confirmando que está listo 
        para el análisis. Si la herramienta falla, reporta el error claramente.
        """,
        tools=[ingest_multimedia_tool]
    )
