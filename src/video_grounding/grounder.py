"""Grounding multimodal con Gemini 2.0 (SDK oficial ``google-genai``).

Flujo:
  1. Sube el video a la API de Gemini y espera a que este ACTIVE.
  2. Solicita a Gemini 2.0 una lista JSON de acciones ancladas a marcas
     [MM:SS], usando salida estructurada (``response_schema`` = Pydantic).
  3. Valida y normaliza la respuesta a ``GroundingOutput``.

El import del SDK es lazy: el modulo y los demas componentes (frames,
markdown, mock) funcionan sin ``google-genai`` instalado; solo fallara al
instanciar un ``GeminiVideoGrounder`` real.
"""

from __future__ import annotations

import os
import time
from typing import Optional

from .schemas import GroundingOutput

# Prompt que solicita marcas de tiempo por accion.
GROUNDING_PROMPT = """\
Eres un ingeniero de sistemas senior encargado de documentar un video \
tutorial tecnico.

Analiza el video y segmenta el procedimiento en acciones discretas y \
ordenadas cronologicamente.

Para CADA accion debes devolver:
- ``index``: entero 1-based.
- ``timestamp``: marca de inicio en formato [MM:SS] (ej. "00:12").
- ``timestamp_seconds``: esa misma marca en segundos.
- ``end_timestamp``: marca de fin aproximada [MM:SS] o null.
- ``action_type``: "command" (comando ejecutado), "configuration" (cambio \
de configuracion), "error" (error/mensaje de error visible), \
"observation" (observacion en pantalla) o "unknown".
- ``title``: titulo corto (max 8 palabras).
- ``description``: descripcion tecnica precisa de lo que ocurre.
- ``command``: el comando exacto ejecutado si aplica, si no null.

Reglas:
- Las marcas de tiempo deben corresponder REALMENTE a lo que se ve en el \
video (grounding visual).
- Extrae TODOS los comandos exactos y los mensajes de error/log visibles.
- Ignora contenido irrelevante o transiciones sin valor tecnico.
- No inventes comandos ni timestamps que no aparezcan en el video.
"""


class GeminiVideoGrounder:
    """Cliente de grounding de video usando Gemini 2.0."""

    DEFAULT_MODEL = "gemini-2.0-flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        *,
        temperature: float = 0.1,
        seed: int = 42,
        timeout_seconds: int = 600,
    ):
        self.api_key = api_key or self._resolve_api_key()
        self.model = model or os.getenv("GEMINI_MODEL", self.DEFAULT_MODEL)
        self.temperature = temperature
        self.seed = seed
        self.timeout_seconds = timeout_seconds
        self._client = None

    @staticmethod
    def _resolve_api_key() -> Optional[str]:
        return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    @property
    def client(self):
        """Devuelve (e inicializa lazy) el cliente genai."""
        if self._client is None:
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "google-genai no esta instalado. Ejecuta "
                    "'pip install google-genai' o usa MockVideoGrounder "
                    "para pruebas offline."
                ) from exc
            if not self.api_key:
                raise RuntimeError(
                    "No hay GEMINI_API_KEY / GOOGLE_API_KEY configurada."
                )
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def ground(self, video_path: str, context: str = "") -> GroundingOutput:
        """Sube el video, lo analiza con Gemini 2.0 y devuelve acciones ancladas."""
        from google.genai import types

        if not os.path.exists(video_path):
            raise FileNotFoundError(video_path)

        video_file = self._upload_and_wait(video_path)
        prompt = GROUNDING_PROMPT
        if context:
            prompt += f"\n\nContexto adicional del usuario: {context}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=[video_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GroundingOutput,
                temperature=self.temperature,
                seed=self.seed,
            ),
        )

        return self._parse_response(response)

    async def ground_async(self, video_path: str, context: str = "") -> GroundingOutput:
        """Variante asincrona (usa ``client.aio``)."""
        from google.genai import types

        if not os.path.exists(video_path):
            raise FileNotFoundError(video_path)

        video_file = self._upload_and_wait(video_path)
        prompt = GROUNDING_PROMPT
        if context:
            prompt += f"\n\nContexto adicional del usuario: {context}"

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=[video_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GroundingOutput,
                temperature=self.temperature,
                seed=self.seed,
            ),
        )
        return self._parse_response(response)

    def _upload_and_wait(self, video_path: str):
        """Sube el archivo y espera a que Gemini lo marque ACTIVE."""
        from google.genai import types

        upload = self.client.files.upload(file=video_path)
        deadline = time.monotonic() + self.timeout_seconds
        while upload.state in (types.FileState.PROCESSING, types.FileState.STATE_UNSPECIFIED):
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"El video no quedo ACTIVE en {self.timeout_seconds}s (ultimo "
                    f"estado: {upload.state})."
                )
            time.sleep(2)
            upload = self.client.files.get(name=upload.name)

        if upload.state == types.FileState.FAILED:
            raise RuntimeError(
                f"Gemini no pudo procesar el video: {upload.error or 'error desconocido'}"
            )
        return upload

    @staticmethod
    def _parse_response(response) -> GroundingOutput:
        """Convierte la respuesta JSON de Gemini en un ``GroundingOutput``."""
        text = getattr(response, "text", None) or ""
        text = text.strip()
        # Defensivo: si viene en fences markdown, quitarlos.
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            return GroundingOutput.model_validate_json(text)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                f"No se pudo parsear la respuesta de Gemini como JSON: {text[:200]!r}"
            ) from exc