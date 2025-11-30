import os
import time
import asyncio
import logging
import google.generativeai as genai
from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner
from dotenv import load_dotenv
from google.genai import types
import nest_asyncio

nest_asyncio.apply()

# --- LOGGING SETUP ---
def setup_logging():
    """Configura un logging dual: a consola y a un archivo."""
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
    
    # Logger principal
    logger = logging.getLogger("DocSquad")
    logger.setLevel(logging.INFO)
    
    # Evitar duplicación de handlers si se llama varias veces
    if not logger.handlers:
        # Handler para el archivo
        file_handler = logging.FileHandler("doc_squad.log")
        file_handler.setFormatter(log_formatter)
        logger.addHandler(file_handler)
        
        # Handler para la consola
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        logger.addHandler(console_handler)
        
    return logger

logger = setup_logging()

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
        logger.error(f"El archivo {file_path} no existe en el sistema local.")
        return f"ERROR: El archivo {file_path} no existe en el sistema local."

    logger.info(f"Subiendo {file_path} a la API de Gemini...")
    try:
        file_upload = genai.upload_file(file_path)
        
        while file_upload.state.name == "PROCESSING":
            logger.info(f"Esperando procesamiento del archivo: {file_upload.name}...")
            time.sleep(2)
            file_upload = genai.get_file(file_upload.name)

        if file_upload.state.name == "FAILED":
            logger.error(f"Falló el procesamiento del archivo en Gemini: {file_upload.name}")
            return "ERROR: Falló el procesamiento en Gemini."

        logger.info(f"Archivo {file_upload.name} procesado y listo con URI: {file_upload.uri}")
        return file_upload.uri
    except Exception as e:
        logger.critical(f"Error crítico durante la subida del archivo: {str(e)}")
        return f"ERROR CRÍTICO: {str(e)}"

# --- AGENTS SETUP ---
def create_agents():
    """Inicializa y retorna los objetos Agent."""
    
    ingest_agent = Agent(
        model='gemini-2.5-flash',
        name='IngestAgent',
        description="Gestiona la carga de archivos.",
        instruction="""
        Eres el IngestAgent. Tu único trabajo es recibir rutas de archivos locales y subirlos usando la herramienta 'ingest_multimedia_tool'.
        Una vez tengas el URI, devuélvelo confirmando que está listo para análisis.
        Si la herramienta falla, reporta el error claramente.
        """,
        tools=[ingest_multimedia_tool]
    )

    analyst_agent = Agent(
        model='gemini-2.5-pro',
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
        """,
    )

    tech_writer_agent = Agent(
        model='gemini-2.5-pro',
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
        """,
    )
    
    return ingest_agent, analyst_agent, tech_writer_agent

# --- PIPELINE FUNCTION (ASYNC) ---
async def run_pipeline_async(file_path: str, request_context: str, status_callback=None):
    user_id = "default_user" # Define a user_id
    session_id = f"session_{int(time.time())}" # Generate a unique session_id
    
    ingest_agent, analyst_agent, tech_writer_agent = create_agents()
    
    # Create a single InMemoryRunner instance
    # The initial agent doesn't matter much as it will be dynamically updated
    runner = InMemoryRunner(agent=ingest_agent, app_name="agents")
    
    # Explicitly create a session for the runner
    session = await runner.session_service.create_session(
        app_name="agents", user_id=user_id, session_id=session_id
    )
    
    session_history = {
        "IngestAgent": [],
        "AnalystAgent": [],
        "TechWriterAgent": [],
    }

    def update_status(msg):
        logger.info(msg)
        if status_callback:
            status_callback(msg)

    async def run_agent_with_memory(current_agent, agent_name, prompt):
        # Dynamically update the agent for the single runner instance
        runner.agent = current_agent

        history = "\n".join([f"Historial anterior:\n- Pregunta: {h['prompt']}\n- Respuesta: {h['response']}" for h in session_history[agent_name]])
        full_prompt = f"{history}\n\nTarea actual: {prompt}"
        
        update_status(f"Iniciando tarea para {agent_name}...")
        
        collected_events = []
        # Wrap the prompt in types.Content
        new_message_content = types.Content(role='user', parts=[types.Part(text=full_prompt)])

        async for event in runner.run_async(new_message=new_message_content, user_id=session.user_id, session_id=session.id):
            collected_events.append(event)
            logger.debug(f"Evento de {agent_name}: {event}")
        
        # Asumimos que el último evento contiene la respuesta final del agente
        if collected_events:
            final_response_event = collected_events[-1]
            response_text = ""
            if final_response_event.content and final_response_event.content.parts:
                # Concatenar todas las partes de texto si hay varias
                response_text = "".join([part.text for part in final_response_event.content.parts if part.text])
            else:
                logger.warning(f"El evento final del agente {agent_name} no contiene contenido de texto esperado.")
                response_text = str(final_response_event) # Fallback
            
            session_history[agent_name].append({"prompt": prompt, "response": response_text})
            update_status(f"Tarea para {agent_name} completada.")
            logger.debug(f"Respuesta de {agent_name}: {response_text}")
            
            # Devolver un objeto con un atributo 'text' para mantener la compatibilidad
            class AgentResponse:
                def __init__(self, text):
                    self.text = text
            return AgentResponse(response_text)
        else:
            logger.error(f"No se recibieron eventos del agente {agent_name}.")
            raise Exception(f"No se recibió respuesta del agente {agent_name}.")

    update_status(f"🚀 Iniciando pipeline para: {os.path.basename(file_path)} (Sesión: {session_id})")
    
    # PASO 1: INGESTA
    ingest_response = await run_agent_with_memory(
        current_agent=ingest_agent, 
        agent_name="IngestAgent", 
        prompt=f"Sube y procesa el archivo: {file_path}"
    )
    
    # PASO 2: ANÁLISIS
    analysis_prompt = f"Aquí tienes el resultado de la ingesta: {ingest_response.text}. Contexto extra: {request_context}. Analiza los hechos técnicos."
    analysis_response = await run_agent_with_memory(
        current_agent=analyst_agent,
        agent_name="AnalystAgent",
        prompt=analysis_prompt
    )

    # PASO 3: REDACCIÓN
    writer_prompt = f"Aquí tienes los hechos técnicos extraídos: \n{analysis_response.text}\n. Genera el documento final."
    final_doc_response = await run_agent_with_memory(
        current_agent=tech_writer_agent,
        agent_name="TechWriterAgent",
        prompt=writer_prompt
    )
    
    update_status("Pipeline finalizado con éxito.")
    return final_doc_response.text

# --- WRAPPER SÍNCRONO PARA APP.PY ---
def run_documentation_pipeline(file_path: str, request_context: str = "", status_callback=None):
    """
    Wrapper síncrono para ejecutar el pipeline async.
    """
    try:
        return asyncio.run(run_pipeline_async(file_path, request_context, status_callback))
    except Exception as e:
        logger.critical(f"El pipeline falló con una excepción no controlada: {e}", exc_info=True)
        # Propagar la excepción para que el llamador sepa que algo salió mal
        raise
