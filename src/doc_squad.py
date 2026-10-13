import os
import re
import time
import asyncio
import google.generativeai as genai
from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner
from dotenv import load_dotenv

from src.validator import validate_facts, validate_syntax_tool

# Número máximo de iteraciones del bucle de refinamiento (Analyst <-> Validator).
MAX_REFINEMENTS = 3

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

    # 4. VALIDATOR AGENT (Critic & Code Syntax Check)
    validator_agent = Agent(
        model='gemini-1.5-flash-001',
        name='ValidatorAgent',
        description="Crítico técnico que valida hechos y sintaxis de comandos.",
        instruction="""
        Eres el ValidatorAgent, un revisor técnico senior (Critic).

        Tu trabajo es revisar los hechos técnicos extraídos por el AnalystAgent y
        detectar problemas ANTES de que se redacte el documento final. No redactas
        documentación: solo juzgas si los hechos son correctos y consistentes.

        Debes revisar:
        - Sintaxis de comandos (bash, docker, python): usa la herramienta
          'validate_syntax_tool' pasándole el texto completo de los hechos.
        - Inconsistencias técnicas: comandos que no corresponden al sistema
          operativo descrito, pasos faltantes, órdenes contradictorias o
          referencias a recursos inexistentes.
        - Comandos peligrosos que merezcan una advertencia.

        Formato de respuesta OBLIGATORIO (respeta la primera línea al pie de la letra):
        VEREDICTO: VÁLIDO
        (si todo es correcto)

        VEREDICTO: REVISAR
        1. <problema concreto y accionable>
        2. <otro problema>
        (si hay algo que corregir; enumera cada problema de forma específica para
        que el AnalystAgent pueda corregirlo sin ambigüedad)
        """,
        tools=[validate_syntax_tool]
    )
    validator_runner = InMemoryRunner(agent=validator_agent, app_name="agents")

    return ingest_runner, analyst_runner, tech_writer_runner, validator_runner


# --- HELPERS DE VALIDACIÓN Y REFINAMIENTO ---

def _parse_verdict(critic_text: str) -> str:
    """Extrae el veredicto del critic ('VÁLIDO' o 'REVISAR') de su respuesta."""
    match = re.search(r"VEREDICTO\s*:\s*(\S+)", critic_text, re.IGNORECASE)
    if match:
        token = match.group(1).upper()
        return "VÁLIDO" if token in {"VÁLIDO", "VALIDO", "OK", "APROBADO"} else "REVISAR"
    # Fallback: si menciona problemas, asumimos que hay que revisar.
    upper = critic_text.upper()
    if "REVISAR" in upper or "PROBLEMA" in upper or "ERROR" in upper:
        return "REVISAR"
    return "VÁLIDO"


def _build_feedback(syntax_report, critic_text: str) -> str:
    """Compone el feedback de refinamiento (sintaxis + observaciones del critic)."""
    parts = []
    if not syntax_report.ok:
        parts.append(
            "ERRORES DE SINTAXIS DETECTADOS (corrígelos obligatoriamente):\n"
            + "\n".join(f"- {issue}" for issue in syntax_report.issues)
        )
    parts.append("OBSERVACIONES DEL CRÍTICO:\n" + critic_text.strip())
    return "\n\n".join(parts)

# --- PIPELINE FUNCTION (ASYNC) ---
async def run_pipeline_async(file_path: str, request_context: str, status_callback):
    ingest_runner, analyst_runner, tech_writer_runner, validator_runner = create_squad()
    
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
    facts = await analyst_runner.run(analysis_prompt)
    update_status("✅ AnalystAgent: Hechos extraídos.")

    # PASO 3: VALIDACIÓN + BUCLE DE REFINAMIENTO (ValidatorAgent <-> AnalystAgent)
    final_facts = facts.text
    for iteration in range(MAX_REFINEMENTS + 1):
        update_status(f"🤖 ValidatorAgent: Validando hechos (iteración {iteration + 1}/{MAX_REFINEMENTS + 1})...")

        # 3a. Verificación determinista de sintaxis de comandos.
        syntax_report = validate_facts(final_facts)

        # 3b. Crítico LLM: detección de inconsistencias técnicas.
        critic_prompt = (
            "Revisa los siguientes hechos técnicos extraídos por el AnalystAgent y "
            "detecta inconsistencias técnicas o errores.\n\n"
            f"INFORME DE SINTAXIS (ya comprobado de forma determinista):\n{syntax_report.to_text()}\n\n"
            f"HECHOS TÉCNICOS:\n{final_facts}\n"
        )
        critic_response = await validator_runner.run(critic_prompt)
        verdict = _parse_verdict(critic_response.text)

        if syntax_report.ok and verdict == "VÁLIDO":
            update_status("✅ ValidatorAgent: Hechos validados, sin problemas.")
            break

        update_status(
            f"🔁 ValidatorAgent: {len(syntax_report.errors)} error(es) de sintaxis y/o "
            f"inconsistencias detectadas; refinando..."
        )

        if iteration >= MAX_REFINEMENTS:
            update_status("⚠️ ValidatorAgent: máximo de iteraciones alcanzado; se continúa con el mejor resultado.")
            break

        feedback = _build_feedback(syntax_report, critic_response.text)
        refined = await analyst_runner.run(
            "Tu análisis previo tiene problemas que debes corregir. Devuelve una "
            "versión CORREGIDA y COMPLETA de los hechos técnicos.\n\n"
            f"{feedback}\n"
        )
        final_facts = refined.text
        update_status("✅ AnalystAgent: Hechos refinados.")

    # PASO 4: REDACCIÓN
    update_status("🤖 TechWriterAgent: Redactando documento final...")
    writer_prompt = f"Aquí tienes los hechos técnicos extraídos: \n{final_facts}\n. Genera el documento final."
    final_doc = await tech_writer_runner.run(writer_prompt)
    update_status("✅ TechWriterAgent: Documento generado.")
    
    return final_doc.text

# --- WRAPPER SÍNCRONO PARA APP.PY ---
def run_documentation_pipeline(file_path: str, request_context: str = "", status_callback=None):
    """
    Wrapper síncrono para ejecutar el pipeline async.
    """
    return asyncio.run(run_pipeline_async(file_path, request_context, status_callback))
