"""
Tests unitarios para el cliente LLM agnóstico (src/llm/client.py).

Cubre:
- Resolución de configuración para todos los proveedores conocidos y variables de entorno.
- Extracción y limpieza de payloads JSON en diversos formatos y contextos.
- Generación síncrona y asíncrona de texto con mock de OpenAI SDK y fallback HTTP.
- Generación estructurada con validación Pydantic v2 y ciclo de auto-reintento ante errores.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from src.contracts import FactKind, Severity, TechnicalFact
from src.llm.client import (
    AgnosticLLMClient,
    ProviderConfig,
    extract_json_payload,
    resolve_provider_config,
)


class DummyOutput(BaseModel):
    """Modelo auxiliar para verificar generación estructurada."""

    title: str
    score: float = Field(ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# 1. Tests de resolución de configuración de proveedores
# --------------------------------------------------------------------------- #

def test_resolve_provider_sambanova(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica la resolución correcta de SambaNova con su variable de entorno."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("SAMBANOVA_API_KEY", "sn-test-key-123")

    config = resolve_provider_config("sambanova")
    assert config.name == "sambanova"
    assert config.base_url == "https://api.sambanova.ai/v1"
    assert config.api_key == "sn-test-key-123"
    assert config.model == "Meta-Llama-3.3-70B-Instruct"


def test_resolve_provider_cerebras(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica la resolución correcta de Cerebras."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("CEREBRAS_API_KEY", "cbr-test-key-456")

    config = resolve_provider_config("cerebras")
    assert config.name == "cerebras"
    assert config.base_url == "https://api.cerebras.ai/v1"
    assert config.api_key == "cbr-test-key-456"
    assert config.model == "llama3.3-70b"


def test_resolve_provider_nous(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica la resolución correcta de Nous Research."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("NOUS_API_KEY", "nous-key-789")

    config = resolve_provider_config("nous")
    assert config.name == "nous"
    assert config.base_url == "https://inference-api.nousresearch.com/v1"
    assert config.api_key == "nous-key-789"
    assert config.model == "Hermes-3-Llama-3.1-70B"


def test_resolve_provider_freellmapi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica la resolución de FreeLLMAPI con su clave por defecto."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("FREELLMAPI_API_KEY", raising=False)

    config = resolve_provider_config("freellmapi")
    assert config.name == "freellmapi"
    assert config.base_url == "http://127.0.0.1:3001/v1"
    assert config.api_key == "sk-freellmapi-local"
    assert config.model == "gpt-4o-mini"


def test_resolve_provider_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica la resolución de Ollama con su configuración local por defecto."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)

    config = resolve_provider_config("ollama")
    assert config.name == "ollama"
    assert config.base_url == "http://127.0.0.1:11434/v1"
    assert config.api_key == "ollama"
    assert config.model == "qwen2.5:1.5b"


def test_resolve_provider_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica la resolución de OpenAI."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test-999")

    config = resolve_provider_config("openai")
    assert config.name == "openai"
    assert config.base_url == "https://api.openai.com/v1"
    assert config.api_key == "sk-openai-test-999"
    assert config.model == "gpt-4o-mini"


def test_resolve_provider_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que se lanza ValueError si un proveedor conocido carece de API key."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("SAMBANOVA_API_KEY", raising=False)

    with pytest.raises(ValueError, match="Falta la clave de API para el proveedor 'sambanova'"):
        resolve_provider_config("sambanova")


def test_resolve_provider_generic_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica la precedencia de variables genéricas LLM_*."""
    monkeypatch.setenv("LLM_PROVIDER", "cerebras")
    monkeypatch.setenv("LLM_API_KEY", "generic-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://custom.cerebras.proxy/v1")
    monkeypatch.setenv("LLM_MODEL", "custom-cerebras-model")

    config = resolve_provider_config()
    assert config.name == "cerebras"
    assert config.base_url == "https://custom.cerebras.proxy/v1"
    assert config.api_key == "generic-key"
    assert config.model == "custom-cerebras-model"


def test_resolve_provider_explicit_arguments_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que los argumentos explícitos sobrescriben tanto variables de entorno como defaults."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")

    config = resolve_provider_config(
        provider="cerebras",
        base_url="https://override.cerebras/v1",
        api_key="override-key",
        model="llama-override",
    )
    assert config.name == "cerebras"
    assert config.base_url == "https://override.cerebras/v1"
    assert config.api_key == "override-key"
    assert config.model == "llama-override"


def test_resolve_provider_custom(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica la configuración de un proveedor personalizado."""
    config = resolve_provider_config(
        provider="custom-llm",
        base_url="https://llm.internal.corp/v1",
        api_key="corp-secret",
        model="custom-engine",
    )
    assert config.name == "custom-llm"
    assert config.base_url == "https://llm.internal.corp/v1"
    assert config.api_key == "corp-secret"
    assert config.model == "custom-engine"


def test_resolve_provider_custom_missing_base_url_raises() -> None:
    """Verifica que un proveedor personalizado sin base_url lance ValueError."""
    with pytest.raises(ValueError, match="requiere 'base_url' explícito"):
        resolve_provider_config(provider="unknown-provider")


# --------------------------------------------------------------------------- #
# 2. Tests de extract_json_payload
# --------------------------------------------------------------------------- #

def test_extract_json_payload_clean() -> None:
    """Verifica la extracción de un JSON plano directo."""
    raw = '{"name": "DocSquad", "version": 2}'
    assert extract_json_payload(raw) == raw


def test_extract_json_payload_fenced_markdown() -> None:
    """Verifica la extracción desde un bloque ```json ... ```."""
    raw = """
```json
{
  "status": "success",
  "items": [1, 2, 3]
}
```
"""
    expected = '{\n  "status": "success",\n  "items": [1, 2, 3]\n}'
    assert extract_json_payload(raw) == expected


def test_extract_json_payload_fenced_without_language() -> None:
    """Verifica la extracción desde un bloque ``` ... ``` sin indicador 'json'."""
    raw = """
```
{"code": 200, "message": "OK"}
```
"""
    assert extract_json_payload(raw) == '{"code": 200, "message": "OK"}'


def test_extract_json_payload_surrounded_text() -> None:
    """Verifica la extracción cuando hay texto explicativo antes y después del bloque."""
    raw = """
Estimado usuario,
A continuación se detallan los resultados de la auditoría técnica solicitada:

```json
{
  "finding": "Puerto 22 abierto",
  "severity": "high"
}
```

Por favor revise las recomendaciones adjuntas.
"""
    extracted = extract_json_payload(raw)
    assert json.loads(extracted) == {"finding": "Puerto 22 abierto", "severity": "high"}


def test_extract_json_payload_unfenced_with_surrounding_text() -> None:
    """Verifica la extracción de un JSON embebido en texto sin marcas markdown."""
    raw = 'El diagnóstico final es: {"healthy": true, "latency_ms": 42.5}. Fin del reporte.'
    extracted = extract_json_payload(raw)
    assert extracted == '{"healthy": true, "latency_ms": 42.5}'
    assert json.loads(extracted)["healthy"] is True


def test_extract_json_payload_array() -> None:
    """Verifica la extracción de una lista JSON."""
    raw = 'Resultados: [{"id": "cmd-1"}, {"id": "cmd-2"}] - Proceso completado.'
    extracted = extract_json_payload(raw)
    parsed = json.loads(extracted)
    assert isinstance(parsed, list)
    assert len(parsed) == 2


def test_extract_json_payload_empty_and_whitespace() -> None:
    """Verifica que una cadena vacía o con solo espacios devuelva una cadena vacía."""
    assert extract_json_payload("") == ""
    assert extract_json_payload("   \n\t  ") == ""


# --------------------------------------------------------------------------- #
# 3. Tests de generate_text_sync y generate_text (async)
# --------------------------------------------------------------------------- #

def test_generate_text_sync_with_mock_client() -> None:
    """Verifica generate_text_sync inyectando un mock del cliente SDK de OpenAI."""
    mock_choice = MagicMock()
    mock_choice.message.content = "Respuesta técnica procesada correctamente."
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_sdk_client = MagicMock()
    mock_sdk_client.chat.completions.create.return_value = mock_response

    config = ProviderConfig(
        name="sambanova",
        base_url="https://api.sambanova.ai/v1",
        api_key="dummy-key",
        model="Meta-Llama-3.3-70B-Instruct",
    )

    client = AgnosticLLMClient(config=config, client=mock_sdk_client)
    result = client.generate_text_sync(
        prompt="Analiza este comando",
        system_prompt="Eres un analista de sistemas.",
        temperature=0.3,
        max_tokens=150,
    )

    assert result == "Respuesta técnica procesada correctamente."
    mock_sdk_client.chat.completions.create.assert_called_once_with(
        model="Meta-Llama-3.3-70B-Instruct",
        messages=[
            {"role": "system", "content": "Eres un analista de sistemas."},
            {"role": "user", "content": "Analiza este comando"},
        ],
        temperature=0.3,
        max_tokens=150,
    )


def test_generate_text_sync_with_patch_http_sync() -> None:
    """Verifica generate_text_sync mediante patch.object sobre _call_http_sync."""
    config = ProviderConfig(
        name="cerebras",
        base_url="https://api.cerebras.ai/v1",
        api_key="test-key",
        model="llama3.3-70b",
    )

    client = AgnosticLLMClient(config=config)

    with patch.object(client, "_call_http_sync", return_value="Salida HTTP directa") as mock_http:
        output = client.generate_text_sync(prompt="Hola")
        assert output == "Salida HTTP directa"
        mock_http.assert_called_once()


def test_generate_text_async_with_mock_async_client() -> None:
    """Verifica generate_text asíncrono con mock de AsyncOpenAI usando asyncio.run."""
    async def _run() -> None:
        mock_choice = MagicMock()
        mock_choice.message.content = "Salida asíncrona validada."
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_async_client = MagicMock()
        mock_async_client.chat.completions.create = AsyncMock(return_value=mock_response)

        config = ProviderConfig(
            name="nous",
            base_url="https://inference-api.nousresearch.com/v1",
            api_key="nous-key",
            model="Hermes-3-Llama-3.1-70B",
        )

        client = AgnosticLLMClient(config=config, async_client=mock_async_client)
        res = await client.generate_text(
            prompt="Test prompt",
            system_prompt="Directiva del sistema",
            temperature=0.5,
        )

        assert res == "Salida asíncrona validada."
        mock_async_client.chat.completions.create.assert_awaited_once()

    asyncio.run(_run())


def test_generate_text_sync_fallback_on_sdk_error() -> None:
    """Verifica que si el cliente OpenAI SDK lanza una excepción, se recurre al fallback HTTP."""
    mock_sdk_client = MagicMock()
    # Simular fallo en el SDK oficial
    mock_sdk_client.chat.completions.create.side_effect = RuntimeError("Conexión SDK fallida")

    config = ProviderConfig(
        name="freellmapi",
        base_url="http://127.0.0.1:3001/v1",
        api_key="sk-local",
        model="gpt-4o-mini",
    )

    client = AgnosticLLMClient(config=config, client=mock_sdk_client)

    # Verificamos que cae en _call_http_sync
    with patch.object(client, "_call_http_sync", return_value="Respuesta recuperada por HTTP fallback"):
        output = client.generate_text_sync(prompt="Consulta con fallback")
        assert output == "Respuesta recuperada por HTTP fallback"


# --------------------------------------------------------------------------- #
# 4. Tests de generate_structured_sync y generate_structured (async)
# --------------------------------------------------------------------------- #

def test_generate_structured_sync_valid_json() -> None:
    """Verifica generate_structured_sync con respuesta JSON válida y modelo Pydantic v2."""
    valid_payload = json.dumps({
        "title": "Informe de despliegue",
        "score": 0.95,
        "tags": ["deploy", "k8s", "producción"],
    })

    mock_choice = MagicMock()
    mock_choice.message.content = f"```json\n{valid_payload}\n```"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    config = ProviderConfig(
        name="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4o-mini",
    )

    client = AgnosticLLMClient(config=config, client=mock_client)
    parsed: DummyOutput = client.generate_structured_sync(
        prompt="Genera el reporte",
        schema=DummyOutput,
        system_prompt="Sistema base",
    )

    assert isinstance(parsed, DummyOutput)
    assert parsed.title == "Informe de despliegue"
    assert parsed.score == 0.95
    assert parsed.tags == ["deploy", "k8s", "producción"]


def test_generate_structured_sync_with_contracts_model() -> None:
    """Verifica generate_structured_sync utilizando un contrato real de Doc Squad (TechnicalFact)."""
    fact_payload = json.dumps({
        "fact_id": "fact-001",
        "kind": "command",
        "summary": "Ejecución de systemctl restart nginx",
        "code": "systemctl restart nginx",
        "severity": "medium",
        "timestamp_ms": 14500,
    })

    mock_choice = MagicMock()
    mock_choice.message.content = fact_payload
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    config = ProviderConfig(
        name="sambanova",
        base_url="https://api.sambanova.ai/v1",
        api_key="sn-key",
        model="Meta-Llama-3.3-70B-Instruct",
    )

    client = AgnosticLLMClient(config=config, client=mock_client)
    fact: TechnicalFact = client.generate_structured_sync(
        prompt="Extrae el hecho técnico",
        schema=TechnicalFact,
    )

    assert isinstance(fact, TechnicalFact)
    assert fact.fact_id == "fact-001"
    assert fact.kind == FactKind.COMMAND
    assert fact.severity == Severity.MEDIUM
    assert fact.code == "systemctl restart nginx"
    assert fact.timestamp_ms == 14500


def test_generate_structured_sync_retry() -> None:
    """Verifica que generate_structured_sync reintenta cuando el primer intento es inválido y el segundo es válido."""
    invalid_payload = "Lo siento, aquí tienes el informe pero no es JSON:\ntítulo: error, score: alto"
    valid_payload = json.dumps({
        "title": "Informe Corregido",
        "score": 0.88,
        "tags": ["corregido"],
    })

    resp_1 = MagicMock()
    resp_1.choices = [MagicMock(message=MagicMock(content=invalid_payload))]

    resp_2 = MagicMock()
    resp_2.choices = [MagicMock(message=MagicMock(content=valid_payload))]

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [resp_1, resp_2]

    config = ProviderConfig(
        name="cerebras",
        base_url="https://api.cerebras.ai/v1",
        api_key="cbr-key",
        model="llama3.3-70b",
    )

    client = AgnosticLLMClient(config=config, client=mock_client)
    result = client.generate_structured_sync(
        prompt="Genera métricas",
        schema=DummyOutput,
        max_retries=2,
    )

    assert isinstance(result, DummyOutput)
    assert result.title == "Informe Corregido"
    assert result.score == 0.88
    assert mock_client.chat.completions.create.call_count == 2


def test_generate_structured_sync_max_retries_exceeded() -> None:
    """Verifica que se lanza ValueError si se agotan todos los reintentos sin obtener JSON válido."""
    bad_resp = MagicMock()
    bad_resp.choices = [MagicMock(message=MagicMock(content="Texto arbitrario sin ningún formato JSON"))]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = bad_resp

    config = ProviderConfig(
        name="ollama",
        base_url="http://127.0.0.1:11434/v1",
        api_key="ollama",
        model="qwen2.5:1.5b",
    )

    client = AgnosticLLMClient(config=config, client=mock_client)

    with pytest.raises(ValueError, match="Fallo al validar la salida estructurada con el modelo DummyOutput tras 3 intentos"):
        client.generate_structured_sync(
            prompt="Genera datos",
            schema=DummyOutput,
            max_retries=2,
        )

    assert mock_client.chat.completions.create.call_count == 3


def test_generate_structured_async_with_retry() -> None:
    """Verifica la versión asíncrona generate_structured con un fallo inicial y éxito en reintento."""
    async def _run() -> None:
        bad_json = '{"title": "Incompleto"}'  # falta campo score obligatorio
        good_json = '{"title": "Completo", "score": 1.0, "tags": ["async"]}'

        resp_1 = MagicMock()
        resp_1.choices = [MagicMock(message=MagicMock(content=bad_json))]

        resp_2 = MagicMock()
        resp_2.choices = [MagicMock(message=MagicMock(content=good_json))]

        mock_async_client = MagicMock()
        mock_async_client.chat.completions.create = AsyncMock(side_effect=[resp_1, resp_2])

        config = ProviderConfig(
            name="nous",
            base_url="https://inference-api.nousresearch.com/v1",
            api_key="nous-key",
            model="Hermes-3-Llama-3.1-70B",
        )

        client = AgnosticLLMClient(config=config, async_client=mock_async_client)
        res = await client.generate_structured(
            prompt="Reporte asíncrono",
            schema=DummyOutput,
            max_retries=1,
        )

        assert isinstance(res, DummyOutput)
        assert res.title == "Completo"
        assert res.score == 1.0
        assert mock_async_client.chat.completions.create.await_count == 2

    asyncio.run(_run())
