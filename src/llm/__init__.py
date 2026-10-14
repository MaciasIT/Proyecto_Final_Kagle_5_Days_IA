"""
Módulo LLM agnóstico compatible con el estándar OpenAI Chat Completions API para Doc Squad v2.
"""
from __future__ import annotations

from src.llm.client import (
    AgnosticLLMClient,
    ProviderConfig,
    extract_json_payload,
    resolve_provider_config,
)

__all__ = [
    "AgnosticLLMClient",
    "ProviderConfig",
    "resolve_provider_config",
    "extract_json_payload",
]
