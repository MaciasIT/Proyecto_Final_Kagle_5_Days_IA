import os
import time
import asyncio
import google.generativeai as genai
from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar API Key si existe
if os.getenv("GOOGLE_API_KEY"):
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# --- TOOLS ---
def ingest_multimedia_tool(file_path: str) -> str:
    """
    Sube un archivo a la API de Gemini y espera a que esté listo.
    Retorna el URI del archivo o un mensaje de error.
    """
    if not os.path.exists(file_path):
        return f"ERROR: El archivo {file_path} no existe en el sistema local."

    print(f"[System] Subiendo {file_path}...")
    try:
        file_upload = genai.upload_file(file_path)
        
        # Esperar a que el archivo esté activo
        while file_upload.state.name == "PROCESSING":
            time.sleep(2)
            file_upload = genai.get_file(file_upload.name)

        if file_upload.state.name == "FAILED":
            return "ERROR: Falló el procesamiento en Gemini."

        return file_upload.uri
    except Exception as e:
        return f"ERROR CRÍTICO: {str(e)}"

# --- AGENTS SETUP ---
def create_squad():
    """Inicializa y retorna los runners del Doc Squad."""
    
    # 1. INGEST AGENT
    ingest_agent = Agent(
        model='gemini-1.5-flash-001',
        name='IngestAgent',
        description="Gestiona la carga de archivos.",
        instruction="""
        Eres el IngestAgent. Tu único trabajo es recibir rutas de archivos locales y subirlos usando la herramienta 'ingest_multimedia_tool'.
        Una vez tengas el URI, devuélvelo confirmando que está listo para análisis.
        Si la herramienta falla, reporta el error claramente.
        """,
        tools=[ingest_multimedia_tool]
    )
    # FIX: Especificar app_name="agents" para evitar mismatch
    ingest_runner = InMemoryRunner(agent=ingest_agent, app_name="agents")

    # 2. ANALYST AGENT
    analyst_agent = Agent(
        model='gemini-1.5-pro-001',
        name='AnalystAgent',
        description="Analiza contenido técnico y extrae hechos.",
        instruction="""
        Eres el AnalystAgent, un Ingeniero de Sistemas Senior.
        Tu trabajo es recibir un URI de archivo (video, audio, imagen) y extraer TODOS los detalles técnicos.
        NO te preocupes por el formato bonito. Céntrate en la precisión.
        
        Debes extraer:
        - Comandos exactos ejecutados.
        - Mensajes de error o logs visibles.
        - Pasos de configuración realizados.
        - Direcciones IP, nombres de host, puertos.
        
        Salida esperada: Una lista de hechos técnicos crudos y cronológicos.
        """
    )
    analyst_runner = InMemoryRunner(agent=analyst_agent, app_name="agents")

    # 3. TECH WRITER AGENT
    tech_writer_agent = Agent(
        model='gemini-1.5-pro-001',
        name='TechWriterAgent',
        description="Genera documentación final.",
        instruction="""
        Eres el TechWriterAgent. Recibes una lista de hechos técnicos de un analista.
        Tu trabajo es convertir esos hechos en un documento profesional (Markdown).
        
        Estructura requerida:
        1. Título Descriptivo.
        2. Resumen Ejecutivo (1 párrafo).
        3. Prerrequisitos (si los hay).
        4. Procedimiento Paso a Paso (numerado).
        5. Solución de Problemas (si aplica).
        
        Usa bloques de código para comandos. Añade notas de advertencia (WARNING) si ves algo peligroso.
        Tu tono debe ser formal, claro y directo.
        """
    )
    tech_writer_runner = InMemoryRunner(agent=tech_writer_agent, app_name="agents")
    
    return ingest_runner, analyst_runner, tech_writer_runner

# --- PIPELINE FUNCTION (ASYNC) ---
async def run_pipeline_async(file_path: str, request_context: str, status_callback):
    ingest_runner, analyst_runner, tech_writer_runner = create_squad()
    
    def update_status(msg):
        if status_callback:
            status_callback(msg)
        else:
            print(msg)

    update_status(f"🚀 Iniciando pipeline para: {os.path.basename(file_path)}")
    
    # PASO 1: INGESTA
    update_status("🤖 IngestAgent: Subiendo y procesando archivo...")
    # Usamos run() que devuelve la respuesta final directamente (simplificado) o run_debug para eventos
    # Para simplificar en producción usamos run() que devuelve una respuesta
    ingest_response = await ingest_runner.run(f"Sube y procesa el archivo: {file_path}")
    update_status("✅ IngestAgent: Archivo listo.")
    
    # PASO 2: ANÁLISIS
    update_status("🤖 AnalystAgent: Analizando contenido técnico...")
    analysis_prompt = f"Aquí tienes el resultado de la ingesta: {ingest_response.text}. Contexto extra: {request_context}. Analiza los hechos técnicos."
    analysis_response = await analyst_runner.run(analysis_prompt)
    update_status("✅ AnalystAgent: Hechos extraídos.")

    # PASO 3: REDACCIÓN
    update_status("🤖 TechWriterAgent: Redactando documento final...")
    writer_prompt = f"Aquí tienes los hechos técnicos extraídos: \n{analysis_response.text}\n. Genera el documento final."
    final_doc = await tech_writer_runner.run(writer_prompt)
    update_status("✅ TechWriterAgent: Documento generado.")
    
    return final_doc.text

# --- WRAPPER SÍNCRONO PARA APP.PY ---
def run_documentation_pipeline(file_path: str, request_context: str = "", status_callback=None):
    """
    Wrapper síncrono para ejecutar el pipeline async.
    """
    return asyncio.run(run_pipeline_async(file_path, request_context, status_callback))
