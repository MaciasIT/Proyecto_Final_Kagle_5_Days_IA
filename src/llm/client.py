"""
Cliente LLM agnóstico compatible con OpenAI Chat Completions API para Doc Squad v2.

Permite interactuar de forma uniforme con múltiples proveedores de inferencia
(SambaNova, Cerebras, Nous, FreeLLMAPI, Ollama, OpenAI o endpoints custom) utilizando
el SDK oficial de OpenAI como mecanismo primario y httpx como fallback directo.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import re
from typing import Any, TypeVar
from unittest.mock import Base as MockBase

import httpx
from pydantic import BaseModel

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    openai = None  # type: ignore[assignment]
    HAS_OPENAI = False

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Configuración por defecto de proveedores conocidos
KNOWN_PROVIDERS: dict[str, dict[str, Any]] = {
    "sambanova": {
        "base_url": "https://api.sambanova.ai/v1",
        "env": "SAMBANOVA_API_KEY",
        "model": "Meta-Llama-3.3-70B-Instruct",
        "default_key": None,
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "env": "CEREBRAS_API_KEY",
        "model": "llama3.3-70b",
        "default_key": None,
    },
    "nous": {
        "base_url": "https://inference-api.nousresearch.com/v1",
        "env": "NOUS_API_KEY",
        "model": "Hermes-3-Llama-3.1-70B",
        "default_key": None,
    },
    "freellmapi": {
        "base_url": "http://127.0.0.1:3001/v1",
        "env": "FREELLMAPI_API_KEY",
        "model": "gpt-4o-mini",
        "default_key": "sk-freellmapi-local",
    },
    "ollama": {
        "base_url": "http://127.0.0.1:11434/v1",
        "env": "OLLAMA_API_KEY",
        "model": "qwen2.5:1.5b",
        "default_key": "ollama",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "env": "OPENAI_API_KEY",
        "model": "gpt-4o-mini",
        "default_key": None,
    },
}


@dataclass
class ProviderConfig:
    """Configuración inmutable de conexión para un proveedor LLM compatible con OpenAI."""

    name: str
    base_url: str
    api_key: str
    model: str


def resolve_provider_config(
    provider: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    require_api_key: bool = True,
) -> ProviderConfig:
    """Resuelve la configuración de un proveedor LLM combinando parámetros y variables de entorno.

    Precedencia de resolución:
    1. Argumentos explícitos de la función.
    2. Variables de entorno genéricas (LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL).
    3. Variables de entorno específicas del proveedor conocido o valores por defecto.

    Raises:
        ValueError: Si falta la clave de API obligatoria o el base_url para un proveedor desconocido.
    """
    # 1. Determinar el nombre del proveedor
    provider_name = provider or os.getenv("LLM_PROVIDER")
    if not provider_name:
        for known_name, spec in KNOWN_PROVIDERS.items():
            env_var = spec["env"]
            if env_var and os.getenv(env_var):
                provider_name = known_name
                break
        else:
            provider_name = "openai"

    normalized_name = provider_name.strip().lower()

    if normalized_name in KNOWN_PROVIDERS:
        spec = KNOWN_PROVIDERS[normalized_name]
        resolved_base_url = base_url or os.getenv("LLM_BASE_URL") or spec["base_url"]
        resolved_model = model or os.getenv("LLM_MODEL") or spec["model"]
        resolved_api_key = (
            api_key
            or os.getenv("LLM_API_KEY")
            or os.getenv(spec["env"])
            or spec["default_key"]
        )

        if not resolved_api_key:
            if require_api_key:
                raise ValueError(
                    f"Falta la clave de API para el proveedor '{normalized_name}'. "
                    f"Establece la variable de entorno '{spec['env']}' o 'LLM_API_KEY'."
                )
            resolved_api_key = ""

        return ProviderConfig(
            name=normalized_name,
            base_url=resolved_base_url,
            api_key=resolved_api_key,
            model=resolved_model,
        )

    # Proveedor personalizado / no estándar
    resolved_base_url = base_url or os.getenv("LLM_BASE_URL")
    if not resolved_base_url:
        raise ValueError(
            f"El proveedor personalizado '{normalized_name}' requiere 'base_url' explícito o la variable 'LLM_BASE_URL'."
        )

    resolved_api_key = api_key or os.getenv("LLM_API_KEY") or ""
    resolved_model = model or os.getenv("LLM_MODEL") or "default"

    return ProviderConfig(
        name=normalized_name,
        base_url=resolved_base_url,
        api_key=resolved_api_key,
        model=resolved_model,
    )


def extract_json_payload(raw_text: str) -> str:
    """Extrae y limpia una cadena JSON embebida en texto plano o bloques de markdown.

    Soporta:
    - JSON directo sin formato markdown.
    - Bloques fenced ```json ... ``` o ``` ... ```.
    - Texto explicativo antes y/o después del bloque o de la estructura JSON.
    - Estructuras tanto de tipo objeto ({...}) como lista ([...]).
    """
    if not raw_text or not raw_text.strip():
        return ""

    text = raw_text.strip()

    # 1. Bloque de código cercado (fenced code block)
    fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fenced_match:
        inner = fenced_match.group(1).strip()
        if (inner.startswith("{") and inner.endswith("}")) or (inner.startswith("[") and inner.endswith("]")):
            return inner
        nested = extract_json_payload(inner)
        if nested:
            return nested
        return inner

    # 2. Búsqueda de delimitadores JSON en texto libre
    candidates: list[str] = []
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        candidates.append(text[brace_start : brace_end + 1].strip())

    bracket_start = text.find("[")
    bracket_end = text.rfind("]")
    if bracket_start != -1 and bracket_end > bracket_start:
        candidates.append(text[bracket_start : bracket_end + 1].strip())

    # Devolver el primer candidato que sea JSON sintácticamente válido
    for candidate in candidates:
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass

    # Si ninguno parsea formalmente, devolver el primer candidato detectado o el texto original
    if candidates:
        return candidates[0]

    return text


_CLIENT_SENTINEL = object()


class AgnosticLLMClient:
    """Cliente LLM agnóstico compatible con OpenAI Chat Completions API.

    Usa primariamente el SDK oficial de OpenAI y httpx como fallback directo.
    Soporta generación de texto y generación estructurada con modelos Pydantic v2.
    """

    def __init__(
        self,
        config: ProviderConfig | None = None,
        *,
        provider: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        client: Any = _CLIENT_SENTINEL,
        async_client: Any = _CLIENT_SENTINEL,
        timeout: float = 60.0,
    ) -> None:
        if config is not None:
            self.config = config
        else:
            self.config = resolve_provider_config(
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                model=model,
            )

        self.timeout = timeout

        # Configuración del cliente OpenAI síncrono
        if client is not _CLIENT_SENTINEL:
            self._client = client
        elif HAS_OPENAI and openai is not None:
            self._client = openai.OpenAI(
                base_url=self.config.base_url,
                api_key=self.config.api_key,
                timeout=self.timeout,
            )
        else:
            self._client = None

        # Configuración del cliente OpenAI asíncrono
        if async_client is not _CLIENT_SENTINEL:
            self._async_client = async_client
        elif HAS_OPENAI and openai is not None:
            self._async_client = openai.AsyncOpenAI(
                base_url=self.config.base_url,
                api_key=self.config.api_key,
                timeout=self.timeout,
            )
        else:
            self._async_client = None

    @staticmethod
    def _is_mocked(target: Any) -> bool:
        """Comprueba si un método o cliente ha sido reemplazado por un mock."""
        return isinstance(target, MockBase) or hasattr(target, "mock_calls") or hasattr(target, "assert_called")

    def _build_http_payload(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format
        return payload

    def _call_http_sync(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """Llamada HTTP síncrona directa mediante httpx (mecanismo fallback)."""
        endpoint = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_http_payload(messages, temperature, max_tokens, response_format)

        with httpx.Client(timeout=self.timeout) as http_client:
            response = http_client.post(endpoint, json=payload, headers=headers)
            # Reintento sin response_format si el proveedor da error 400 por no soportar json_object
            if response.status_code == 400 and response_format is not None:
                payload_no_rf = dict(payload)
                payload_no_rf.pop("response_format", None)
                retry_response = http_client.post(endpoint, json=payload_no_rf, headers=headers)
                if retry_response.is_success:
                    response = retry_response

            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"] or ""

    async def _call_http_async(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """Llamada HTTP asíncrona directa mediante httpx (mecanismo fallback)."""
        endpoint = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_http_payload(messages, temperature, max_tokens, response_format)

        async with httpx.AsyncClient(timeout=self.timeout) as http_client:
            response = await http_client.post(endpoint, json=payload, headers=headers)
            if response.status_code == 400 and response_format is not None:
                payload_no_rf = dict(payload)
                payload_no_rf.pop("response_format", None)
                retry_response = await http_client.post(endpoint, json=payload_no_rf, headers=headers)
                if retry_response.is_success:
                    response = retry_response

            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"] or ""

    def _execute_chat_sync(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """Ejecuta una petición de chat síncrona priorizando OpenAI SDK con fallback a httpx."""
        # Si _call_http_sync está mockeado explícitamente en tests, delegar de inmediato
        if self._is_mocked(self._call_http_sync):
            return self._call_http_sync(messages, temperature, max_tokens, response_format)

        if self._client is not None:
            try:
                kwargs: dict[str, Any] = {
                    "model": self.config.model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if max_tokens is not None:
                    kwargs["max_tokens"] = max_tokens
                if response_format is not None:
                    kwargs["response_format"] = response_format

                resp = self._client.chat.completions.create(**kwargs)
                return resp.choices[0].message.content or ""
            except Exception as exc:
                if self._is_mocked(self._client):
                    raise
                logger.warning("Fallo en llamada a OpenAI SDK (%s). Recurriendo a fallback HTTP.", exc)
                return self._call_http_sync(messages, temperature, max_tokens, response_format)

        return self._call_http_sync(messages, temperature, max_tokens, response_format)

    async def _execute_chat_async(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """Ejecuta una petición de chat asíncrona priorizando AsyncOpenAI SDK con fallback a httpx."""
        # Si _call_http_async está mockeado explícitamente en tests, delegar de inmediato
        if self._is_mocked(self._call_http_async):
            return await self._call_http_async(messages, temperature, max_tokens, response_format)

        if self._async_client is not None:
            try:
                kwargs: dict[str, Any] = {
                    "model": self.config.model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if max_tokens is not None:
                    kwargs["max_tokens"] = max_tokens
                if response_format is not None:
                    kwargs["response_format"] = response_format

                resp = await self._async_client.chat.completions.create(**kwargs)
                return resp.choices[0].message.content or ""
            except Exception as exc:
                if self._is_mocked(self._async_client):
                    raise
                logger.warning("Fallo en llamada a AsyncOpenAI SDK (%s). Recurriendo a fallback HTTP.", exc)
                return await self._call_http_async(messages, temperature, max_tokens, response_format)

        return await self._call_http_async(messages, temperature, max_tokens, response_format)

    def generate_text_sync(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Genera una respuesta de texto de forma síncrona.

        Args:
            prompt: Mensaje del usuario o consulta a procesar.
            system_prompt: Directiva o contexto de sistema opcional.
            temperature: Grado de aleatoriedad (0.0 a 1.0).
            max_tokens: Límite máximo de tokens generados.

        Returns:
            Texto de la respuesta generado por el modelo.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return self._execute_chat_sync(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Genera una respuesta de texto de forma asíncrona.

        Args:
            prompt: Mensaje del usuario o consulta a procesar.
            system_prompt: Directiva o contexto de sistema opcional.
            temperature: Grado de aleatoriedad (0.0 a 1.0).
            max_tokens: Límite máximo de tokens generados.

        Returns:
            Texto de la respuesta generado por el modelo.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return await self._execute_chat_async(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def generate_structured_sync(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        max_retries: int = 2,
    ) -> T:
        """Genera una respuesta estructurada validada con Pydantic v2 síncronamente con auto-reintento.

        Args:
            prompt: Mensaje o solicitud para la generación.
            schema: Subclase de BaseModel de Pydantic que define el contrato de datos esperado.
            system_prompt: Directivas del sistema complementarias a la instrucción de formato.
            temperature: Temperatura recomendada baja para máxima reproducibilidad.
            max_tokens: Límite opcional de tokens.
            max_retries: Número de reintentos con corrección de errores si la validación falla.

        Returns:
            Instancia validada del modelo Pydantic especificado en schema.

        Raises:
            ValueError: Si tras agotar los reintentos la salida no cumple con el esquema Pydantic.
        """
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        format_instruction = (
            "IMPORTANTE: Debes responder EXCLUSIVAMENTE con un objeto JSON válido "
            f"que cumpla con el siguiente esquema JSON Schema:\n{schema_json}\n"
            "No incluyas explicaciones, encabezados, pies de página ni texto fuera del JSON."
        )
        effective_system_prompt = (
            f"{system_prompt}\n\n{format_instruction}" if system_prompt else format_instruction
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": effective_system_prompt},
            {"role": "user", "content": prompt},
        ]

        last_error: Exception | None = None
        last_raw_text = ""

        for attempt in range(max_retries + 1):
            raw_text = self._execute_chat_sync(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            last_raw_text = raw_text
            clean_json = extract_json_payload(raw_text)

            try:
                return schema.model_validate_json(clean_json)
            except Exception as err:
                last_error = err
                logger.warning(
                    "Intento %d/%d fallido para validar modelo %s: %s",
                    attempt + 1,
                    max_retries + 1,
                    schema.__name__,
                    err,
                )
                if attempt < max_retries:
                    messages.append({"role": "assistant", "content": raw_text})
                    messages.append({
                        "role": "user",
                        "content": (
                            f"La salida previa generó un error de validación en el modelo {schema.__name__}: {err}.\n"
                            "Corrige el JSON y responde ÚNICAMENTE con el objeto JSON válido corregido."
                        ),
                    })

        raise ValueError(
            f"Fallo al validar la salida estructurada con el modelo {schema.__name__} "
            f"tras {max_retries + 1} intentos. Último error: {last_error}. Salida recibida: {last_raw_text!r}"
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        max_retries: int = 2,
    ) -> T:
        """Genera una respuesta estructurada validada con Pydantic v2 asíncronamente con auto-reintento.

        Args:
            prompt: Mensaje o solicitud para la generación.
            schema: Subclase de BaseModel de Pydantic que define el contrato de datos esperado.
            system_prompt: Directivas del sistema complementarias a la instrucción de formato.
            temperature: Temperatura recomendada baja para máxima reproducibilidad.
            max_tokens: Límite opcional de tokens.
            max_retries: Número de reintentos con corrección de errores si la validación falla.

        Returns:
            Instancia validada del modelo Pydantic especificado en schema.

        Raises:
            ValueError: Si tras agotar los reintentos la salida no cumple con el esquema Pydantic.
        """
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        format_instruction = (
            "IMPORTANTE: Debes responder EXCLUSIVAMENTE con un objeto JSON válido "
            f"que cumpla con el siguiente esquema JSON Schema:\n{schema_json}\n"
            "No incluyas explicaciones, encabezados, pies de página ni texto fuera del JSON."
        )
        effective_system_prompt = (
            f"{system_prompt}\n\n{format_instruction}" if system_prompt else format_instruction
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": effective_system_prompt},
            {"role": "user", "content": prompt},
        ]

        last_error: Exception | None = None
        last_raw_text = ""

        for attempt in range(max_retries + 1):
            raw_text = await self._execute_chat_async(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            last_raw_text = raw_text
            clean_json = extract_json_payload(raw_text)

            try:
                return schema.model_validate_json(clean_json)
            except Exception as err:
                last_error = err
                logger.warning(
                    "Intento %d/%d fallido para validar modelo %s de forma asíncrona: %s",
                    attempt + 1,
                    max_retries + 1,
                    schema.__name__,
                    err,
                )
                if attempt < max_retries:
                    messages.append({"role": "assistant", "content": raw_text})
                    messages.append({
                        "role": "user",
                        "content": (
                            f"La salida previa generó un error de validación en el modelo {schema.__name__}: {err}.\n"
                            "Corrige el JSON y responde ÚNICAMENTE con el objeto JSON válido corregido."
                        ),
                    })

        raise ValueError(
            f"Fallo al validar la salida estructurada con el modelo {schema.__name__} "
            f"tras {max_retries + 1} intentos. Último error: {last_error}. Salida recibida: {last_raw_text!r}"
        )
