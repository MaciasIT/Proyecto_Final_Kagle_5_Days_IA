"""Doc Squad v2 — Video Grounding core IA.

Capacidad multimodal que:
  1. Usa Gemini 2.0 (SDK ``google-genai``) para indexar marcas de tiempo
     ``[MM:SS]`` por cada accion detectada en un video.
  2. Extrae el fotograma clave de cada marca con ffmpeg.
  3. Incrusta las capturas directamente en el Markdown generado
     (data-URI base64 o referencia relativa a un directorio ``assets/``).

Exposicion publica estable:

    from video_grounding import VideoGroundingPipeline, GeminiVideoGrounder
    from video_grounding.schemas import GroundedAction, VideoGroundingResult
"""

from .schemas import (
    ActionType,
    GroundedAction,
    GroundingOutput,
    FrameCapture,
    VideoGroundingResult,
    parse_timestamp,
    format_timestamp,
)
from .frames import FrameExtractor
from .grounder import GeminiVideoGrounder
from .mock import MockVideoGrounder
from .pipeline import VideoGroundingPipeline

__all__ = [
    "ActionType",
    "GroundedAction",
    "GroundingOutput",
    "FrameCapture",
    "VideoGroundingResult",
    "parse_timestamp",
    "format_timestamp",
    "FrameExtractor",
    "GeminiVideoGrounder",
    "MockVideoGrounder",
    "VideoGroundingPipeline",
]

__version__ = "2.0.0"