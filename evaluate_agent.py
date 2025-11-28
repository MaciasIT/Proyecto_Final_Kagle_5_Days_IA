import os
import asyncio
import google.generativeai as genai
from dotenv import load_dotenv
from src.doc_squad import run_documentation_pipeline, setup_logging

# Configurar logging
logger = setup_logging()

# Cargar variables de entorno
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    logger.error("GOOGLE_API_KEY no encontrada. Por favor, configúrala en el archivo .env.")
    exit(1)

genai.configure(api_key=GOOGLE_API_KEY)

async def evaluate_documentation(generated_doc: str, golden_doc: str) -> str:
    """
    Utiliza un modelo de Gemini para evaluar la calidad de la documentación generada
    comparándola con una versión "ideal".
    """
    evaluator_agent = genai.GenerativeModel('gemini-2.5-pro') # Usamos el modelo pro para la evaluación

    prompt = f"""
    Eres un Agente Evaluador de Documentación Técnica. Tu tarea es comparar dos documentos técnicos:
    1. Un documento generado automáticamente.
    2. Un documento "ideal" (golden standard).

    Evalúa la calidad del documento generado basándote en los siguientes criterios:
    - **Completitud:** ¿Contiene toda la información relevante presente en el documento ideal?
    - **Precisión:** ¿Es la información correcta y libre de errores?
    - **Formato:** ¿Está bien estructurado, usa Markdown correctamente (títulos, listas, bloques de código)?
    - **Claridad y Coherencia:** ¿Es fácil de entender y sigue un flujo lógico?

    Asigna una puntuación del 1 al 100 (donde 100 es perfecto) y proporciona un resumen detallado de la evaluación,
    incluyendo puntos fuertes y áreas de mejora.

    ---
    DOCUMENTO GENERADO:
    {generated_doc}

    ---
    DOCUMENTO IDEAL:
    {golden_doc}

    ---
    EVALUACIÓN:
    """

    logger.info("Evaluando documentación con Gemini...")
    response = await evaluator_agent.generate_content_async(prompt)
    
    if response.candidates:
        return response.candidates[0].content.parts[0].text
    else:
        logger.warning("No se recibió respuesta del agente evaluador.")
        return "No se pudo obtener una evaluación."

async def main():
    logger.info("--- INICIANDO EVALUACIÓN DEL AGENTE ---")

    # Archivo de video de prueba
    test_video_path = "test_data/sample_video.mp4"
    # Archivo de documentación "golden" (ideal)
    golden_doc_path = "test_data/golden_doc.md" # Necesitamos crear este archivo

    if not os.path.exists(test_video_path):
        logger.error(f"Archivo de video de prueba no encontrado: {test_video_path}")
        return
    if not os.path.exists(golden_doc_path):
        logger.error(f"Archivo de documentación ideal (golden) no encontrado: {golden_doc_path}")
        logger.info("Por favor, crea un archivo 'golden_doc.md' en la carpeta 'test_data' con la documentación esperada.")
        return

    # Leer la documentación "golden"
    with open(golden_doc_path, 'r', encoding='utf-8') as f:
        golden_documentation = f.read()

    logger.info(f"Generando documentación para {test_video_path}...")
    generated_documentation = await run_documentation_pipeline(
        file_path=test_video_path,
        request_context="Este es un tutorial sobre cómo usar el comando 'ls' en un terminal Linux.",
        status_callback=None # El logging ya está configurado
    )

    logger.info("Documentación generada. Iniciando evaluación...")
    evaluation_result = await evaluate_documentation(generated_documentation, golden_documentation)

    logger.info("\n--- RESULTADO DE LA EVALUACIÓN ---")
    logger.info(evaluation_result)
    logger.info("--- EVALUACIÓN FINALIZADA ---")

if __name__ == "__main__":
    asyncio.run(main())
