"""Puentes de compatibilidad entre el contrato de grounding y ``contracts.py``.

El visor sincronizado (frontend) consume ``video_grounding.schemas.VideoGroundingResult``
directamente (véase ``src/frontend/contract.py::normalize_grounding``), que es la
salida canónica de esta etapa.  Este módulo aporta un adaptador *opcional* para
rellenar el campo ``Grounding`` de ``contracts.PipelineResult`` (que es un
``GroundedTranscript``, definido por el RFC-002) sin cambiar los nombres de
campo del contrato de grounding.

Los imports de ``contracts`` son defensivos (``src.contracts`` vs ``contracts``)
porque el paquete ``src`` es un namespace package sin ``__init__.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .schemas import VideoGroundingResult

try:
    from src.contracts import GroundedTranscript, TranscriptSegment
except ImportError:  # pragma: no cover
    from contracts import GroundedTranscript, TranscriptSegment  # type: ignore


def to_grounded_transcript(result: "VideoGroundingResult") -> "GroundedTranscript":
    """Convierte un ``VideoGroundingResult`` en el ``GroundedTranscript`` del RFC.

    Mapea cada ``GroundedAction`` a un ``TranscriptSegment`` y enlaza su captura
    (``FrameCapture.image_path``) por ``action_index``.  Los milisegundos se
    derivan de ``timestamp_seconds``.
    """
    frames_by_action = {f.action_index: f for f in result.frames}

    segments = []
    for action in result.actions:
        frame = frames_by_action.get(action.index)
        start_ms = int(round(action.timestamp_seconds * 1000))
        segments.append(
            TranscriptSegment(
                segment_id=f"seg_{action.index:04d}",
                start_ms=start_ms,
                end_ms=start_ms,  # sin marca de fin fiable en la etapa de grounding
                text=f"{action.title}: {action.description}",
                speaker=None,
                frame_path=frame.image_path if frame else None,
                frame_timestamp_ms=start_ms if frame else None,
            )
        )

    full_text = "\n".join(s.text for s in segments)

    return GroundedTranscript(
        asset_id=result.video_path,
        language=None,
        segments=segments,
        full_text=full_text,
        warnings=[],
    )


__all__ = ["to_grounded_transcript"]