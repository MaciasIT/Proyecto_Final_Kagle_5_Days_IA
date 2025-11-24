import os
import datetime
from google.adk.runners import InMemoryRunner
from app.agents.ingest_agent import create_ingest_agent
from app.agents.analyst_agent import create_analyst_agent
from app.agents.writer_agent import create_writer_agent
from app.agents.saver_agent import create_saver_agent

class Orchestrator:
    """
    Orquesta el flujo de trabajo entre los agentes especializados.
    No es un agente en sí mismo, sino una clase que gestiona los runners.
    """
    def __init__(self):
        print("🤖 Creando y configurando agentes especializados...")
        self.ingest_agent = create_ingest_agent()
        self.analyst_agent = create_analyst_agent()
        self.writer_agent = create_writer_agent()
        self.saver_agent = create_saver_agent()

        # Cada agente tiene su propio runner
        self.ingest_runner = InMemoryRunner(agent=self.ingest_agent)
        self.analyst_runner = InMemoryRunner(agent=self.analyst_agent)
        self.writer_runner = InMemoryRunner(agent=self.writer_agent)
        self.saver_runner = InMemoryRunner(agent=self.saver_agent)
        print("✅ Agentes y runners listos.")

    async def run_pipeline(self, file_path: str, user_context: str = "") -> str:
        """
        Ejecuta el pipeline completo de documentación.
        
        1. Ingesta el archivo.
        2. Analiza el contenido.
        3. Escribe la documentación.
        4. Guarda la documentación.
        """
        print(f"--- INICIANDO PIPELINE PARA: {file_path} ---")

        # --- PASO 1: Ingesta ---
        print("1️⃣  Llamando a IngestAgent...")
        ingest_prompt = f"Sube y procesa el siguiente archivo: {file_path}"
        ingest_events = await self.ingest_runner.run_debug(ingest_prompt)
        ingest_response = "".join(part.text for part in ingest_events[-1].content.parts) if ingest_events and ingest_events[-1].content else None

        if not ingest_response or "ERROR" in ingest_response:
            error_message = f"Falló el paso de ingesta: {ingest_response}"
            print(f"❌ {error_message}")
            return error_message
        
        file_uri = ingest_response
        print(f"✅ Ingesta completada. URI del archivo: {file_uri}")

        # --- PASO 2: Análisis ---
        print("2️⃣  Llamando a AnalystAgent...")
        analysis_prompt = f"""
        Analiza el contenido del archivo ubicado en el siguiente URI y extrae 
        los hechos técnicos clave. 
        Contexto proporcionado por el usuario: '{user_context}'
        URI del archivo: {file_uri}
        """
        analysis_events = await self.analyst_runner.run_debug(analysis_prompt)
        technical_facts = "".join(part.text for part in analysis_events[-1].content.parts) if analysis_events and analysis_events[-1].content else None

        if not technical_facts or "ERROR" in technical_facts:
            error_message = f"Falló el paso de análisis: {technical_facts}"
            print(f"❌ {error_message}")
            return error_message

        print("✅ Análisis completado. Hechos extraídos.")
        print(f"🗒️ Hechos: {technical_facts}")

        # --- PASO 3: Redacción ---
        print("3️⃣  Llamando a TechWriterAgent...")
        writer_prompt = f"""
        Toma los siguientes hechos técnicos y genera un documento profesional en Markdown.
        Hechos:
        ---
        {technical_facts}
        ---
        """
        writer_events = await self.writer_runner.run_debug(writer_prompt)
        final_document = "".join(part.text for part in writer_events[-1].content.parts) if writer_events and writer_events[-1].content else None

        if not final_document:
            error_message = "Falló el paso de redacción: no se generó ningún documento."
            print(f"❌ {error_message}")
            return error_message
            
        print("✅ Redacción completada. Documento final generado.")

        # --- PASO 4: Guardado ---
        print("4️⃣  Llamando a SaverAgent...")
        base_filename = os.path.splitext(os.path.basename(file_path))[0]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{base_filename}_doc_{timestamp}.md"

        saver_prompt = f"""
        Guarda el siguiente documento en el archivo '{output_filename}'.

        Contenido:
        ---
        {final_document}
        ---
        """
        saver_events = await self.saver_runner.run_debug(saver_prompt)
        save_confirmation = "".join(part.text for part in saver_events[-1].content.parts) if saver_events and saver_events[-1].content else None
        
        if not save_confirmation or "ERROR" in save_confirmation:
            error_message = f"Falló el paso de guardado: {save_confirmation}"
            print(f"❌ {error_message}")
            return error_message

        print(f"✅ Pipeline completado. {save_confirmation}")
        return save_confirmation

def create_orchestrator() -> Orchestrator:
    """Función factory para crear una instancia del orquestador."""
    return Orchestrator()