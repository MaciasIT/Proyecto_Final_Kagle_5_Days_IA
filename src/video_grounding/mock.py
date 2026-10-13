"""Grounder deterministico para pruebas offline / CI.

No requiere API ni red. Genera ``N`` acciones con marcas de tiempo
uniformemente distribuidas sobre la duracion real del video (medida con
ffprobe si esta disponible), de modo que el resto del pipeline
(extraccion de frames + Markdown) pueda validarse de extremo a extremo.
"""

from __future__ import annotations

import os
from typing import Optional

from .frames import FrameExtractor
from .schemas import ActionType, GroundedAction, GroundingOutput, format_timestamp


class MockVideoGrounder:
    """Genera acciones de forma determinista a partir de la duracion del video."""

    def __init__(
        self,
        actions: int = 6,
        *,
        seed: int = 42,
        frame_extractor: Optional[FrameExtractor] = None,
    ):
        self.actions = actions
        self.seed = seed
        self.frame_extractor = frame_extractor or FrameExtractor()
        self.model = "mock-gemini-2.0"

    def _duration(self, video_path: str) -> float:
        try:
            return self.frame_extractor.probe_duration(video_path)
        except Exception:
            return 60.0  # fallback si ffprobe no esta disponible

    def ground(self, video_path: str, context: str = "") -> GroundingOutput:
        duration = self._duration(video_path)
        if duration <= 0:
            duration = 60.0

        actions = []
        for i in range(1, self.actions + 1):
            # marca uniforme, evitando el borde 0 y el final exacto
            ts = duration * (i - 0.5) / self.actions
            is_cmd = i % 2 == 1
            actions.append(
                GroundedAction(
                    index=i,
                    timestamp=format_timestamp(ts),
                    timestamp_seconds=round(ts, 2),
                    end_timestamp=format_timestamp(min(duration, ts + 5)),
                    action_type=ActionType.COMMAND if is_cmd else ActionType.OBSERVATION,
                    title=f"Accion {i}" + (": ejecutar comando" if is_cmd else ": observar salida"),
                    description=(
                        f"Paso {i} del procedimiento (mock). "
                        f"Marca simulada en {format_timestamp(ts)}."
                    ),
                    command=f"echo 'paso {i}'" if is_cmd else None,
                )
            )

        return GroundingOutput(
            title="Procedimiento (mock)",
            summary=f"Documentacion simulada de {self.actions} pasos sobre "
            f"{os.path.basename(video_path)}.",
            actions=actions,
        )