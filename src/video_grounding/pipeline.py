"""Orquestacion del pipeline de Video Grounding.

ground(video) -> extract frames -> build markdown.

El componente de grounding se inyecta (Gemini real o mock), por lo que el
pipeline completo es testeable sin API ni red.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Optional, Protocol

from .frames import FrameExtractor
from .markdown_builder import MarkdownBuilder
from .schemas import GroundingOutput, VideoGroundingResult


class Grounder(Protocol):
    """Contrato minimo de un componente de grounding."""

    model: str

    def ground(self, video_path: str, context: str = "") -> GroundingOutput: ...


class VideoGroundingPipeline:
    """Coordina grounding + extraccion de frames + generacion de Markdown."""

    def __init__(
        self,
        grounder: Grounder,
        frame_extractor: Optional[FrameExtractor] = None,
        markdown_builder: Optional[MarkdownBuilder] = None,
        image_mode: str = "base64",
        keep_frames: bool = False,
    ):
        self.grounder = grounder
        self.frame_extractor = frame_extractor or FrameExtractor()
        self.keep_frames = keep_frames
        if markdown_builder is not None:
            self.markdown_builder = markdown_builder
            self.image_mode = markdown_builder.image_mode
        else:
            self.image_mode = image_mode
            self.markdown_builder = MarkdownBuilder(image_mode)

    def run(
        self,
        video_path: str,
        context: str = "",
        *,
        output_path: Optional[str] = None,
        frames_dir: Optional[str] = None,
    ) -> VideoGroundingResult:
        """Ejecuta el pipeline completo y devuelve el resultado enriquecido.

        Si ``output_path`` se indica, el Markdown se escribe alli.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(video_path)

        # 1. Grounding de acciones con marcas [MM:SS].
        grounding = self.grounder.ground(video_path, context=context)

        # 2. Extraccion de fotogramas clave (ffmpeg).
        duration = self.frame_extractor.probe_duration(video_path)
        own_frames_dir = frames_dir is None
        if frames_dir is None:
            frames_dir = tempfile.mkdtemp(prefix="video_grounding_")
        try:
            frames = self.frame_extractor.extract_frames(
                video_path, grounding.actions, frames_dir
            )
        except Exception:
            if own_frames_dir:
                shutil.rmtree(frames_dir, ignore_errors=True)
            raise

        result = VideoGroundingResult(
            video_path=video_path,
            duration_seconds=duration,
            model=getattr(self.grounder, "model", "unknown"),
            title=grounding.title,
            summary=grounding.summary,
            actions=grounding.actions,
            frames=frames,
        )

        # 3. Generacion del Markdown con capturas incrustadas.
        self.markdown_builder.image_mode = self.image_mode
        self.markdown_builder.build(result, output_path=output_path)

        # 4. Limpieza de frames temporales (si no se pide conservar).
        if own_frames_dir and not self.keep_frames:
            shutil.rmtree(frames_dir, ignore_errors=True)

        return result