from google.adk.agents import Agent
from app.tools.writer_tools import save_document_tool

def create_saver_agent() -> Agent:
    """
    Función factory para crear y configurar el SaverAgent.
    """
    return Agent(
        model='gemini-flash-latest',
        name="SaverAgent",
        description="Agente especializado en guardar contenido de texto en archivos.",
        instruction="""
        Tu única tarea es tomar el contenido y el nombre de archivo proporcionados
        y usar la herramienta 'save_document_tool' para guardarlos en el disco.
        Responde únicamente con el mensaje de confirmación que te devuelve la herramienta.
        """,
        tools=[save_document_tool],
    )
