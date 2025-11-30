import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock

# Importar las funciones de creación de agentes y configuración
from app.config import configure_environment
from app.agents.ingest_agent import create_ingest_agent
from app.agents.analyst_agent import create_analyst_agent
from app.agents.writer_agent import create_writer_agent
from app.orchestrator import Orchestrator

# --- Fixtures ---

@pytest.fixture(scope="module")
def setup_env():
    """
    Fixture para asegurar que el entorno está configurado para las pruebas.
    Usa un mock para la API key para no depender de una real.
    """
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key-1234"}):
        configure_environment()

# --- Pruebas de Creación de Agentes (Unitarias) ---

def test_create_ingest_agent(setup_env):
    """Verifica que el IngestAgent se puede crear correctamente."""
    agent = create_ingest_agent()
    assert agent is not None
    assert agent.name == "IngestAgent"
    assert "ingest_multimedia_tool" in [tool.__name__ for tool in agent.tools]

def test_create_analyst_agent(setup_env):
    """Verifica que el AnalystAgent se puede crear correctamente."""
    agent = create_analyst_agent()
    assert agent is not None
    assert agent.name == "AnalystAgent"
    assert not agent.tools

def test_create_writer_agent(setup_env):
    """Verifica que el TechWriterAgent se puede crear correctamente."""
    agent = create_writer_agent()
    assert agent is not None
    assert agent.name == "TechWriterAgent"
    assert not agent.tools

# --- Prueba de Flujo del Orquestador (Integración con Mocks) ---

@pytest.mark.asyncio
async def test_orchestrator_run_pipeline(setup_env):
    """
    Prueba el método run_pipeline del Orchestrator, mockeando los runners.
    """
    # 1. Instanciar el Orquestador
    orchestrator = Orchestrator()

    # 2. Mockear los runners para que no hagan llamadas reales a la API
    # Usamos AsyncMock para los métodos `run` que son `async`
    mock_event = MagicMock()
    mock_event.text = "mock response"
    
    orchestrator.ingest_runner.run = AsyncMock(return_value=[MagicMock(text="gs://fake-uri/video.mp4")])
    orchestrator.analyst_runner.run = AsyncMock(return_value=[MagicMock(text="Hecho 1: comando 'ls -l'.")])
    orchestrator.writer_runner.run = AsyncMock(return_value=[MagicMock(text="# Documento Final")])

    # 3. Ejecutar el pipeline
    test_file_path = "/tmp/test.mp4"
    final_document = await orchestrator.run_pipeline(test_file_path)

    # 4. Verificar que el resultado final es el esperado del writer
    assert final_document == "# Documento Final"

    # 5. Verificar que los runners fueron llamados en orden
    orchestrator.ingest_runner.run.assert_awaited_once()
    orchestrator.analyst_runner.run.assert_awaited_once()
    orchestrator.writer_runner.run.assert_awaited_once()

    # 6. (Opcional) Verificar los prompts con los que fueron llamados
    ingest_call_args = orchestrator.ingest_runner.run.call_args
    assert f"Sube y procesa el siguiente archivo: {test_file_path}" in ingest_call_args.kwargs['user_messages']
    
    analyst_call_args = orchestrator.analyst_runner.run.call_args
    assert "gs://fake-uri/video.mp4" in analyst_call_args.kwargs['user_messages'][0]
    
    writer_call_args = orchestrator.writer_runner.run.call_args
    assert "Hecho 1: comando 'ls -l'." in writer_call_args.kwargs['user_messages'][0]

@pytest.mark.asyncio
async def test_orchestrator_ingest_fails(setup_env):
    """
    Prueba que el pipeline se detiene si la ingesta falla.
    """
    orchestrator = Orchestrator()
    
    # Mockear el runner de ingesta para que devuelva un error
    orchestrator.ingest_runner.run = AsyncMock(return_value=[MagicMock(text="ERROR: Ingesta fallida")])
    orchestrator.analyst_runner.run = AsyncMock() # Mock para asegurar que no se llama

    result = await orchestrator.run_pipeline("/tmp/fail.mp4")

    assert "Falló el paso de ingesta" in result
    
    # Verificar que el runner de análisis nunca fue llamado
    orchestrator.analyst_runner.run.assert_not_awaited()
