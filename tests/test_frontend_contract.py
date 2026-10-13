"""Verifica la frontera con el visor sincronizado (frontend).

El frontend consume ``video_grounding.schemas.VideoGroundingResult`` a través de
``src/frontend/contract.py::normalize_grounding``.  Este test garantiza que la
salida real del pipeline (mock) se normaliza sin errores y con los campos que el
visor espera.
"""

import os
import sys

import pytest

from conftest import _TEST_VIDEO
from video_grounding.frames import FrameExtractor
from video_grounding.mock import MockVideoGrounder
from video_grounding.pipeline import VideoGroundingPipeline

# Asegurar que el raíz del proyecto esté en sys.path para importar src.frontend.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # noqa: F401
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _fe():
    return FrameExtractor(
        ffmpeg_bin=os.environ.get("FFMPEG_BIN", "ffmpeg"),
        ffprobe_bin=os.environ.get("FFPROBE_BIN", "ffprobe"),
        max_width=480,
    )


def test_frontend_normalize_grounding(tmp_path):
    from src.frontend.contract import normalize_grounding  # modelo canónico del visor

    pipeline = VideoGroundingPipeline(
        grounder=MockVideoGrounder(actions=3, frame_extractor=_fe()),
        frame_extractor=_fe(),
        image_mode="base64",
    )
    result = pipeline.run(_TEST_VIDEO, output_path=os.path.join(str(tmp_path), "doc.md"))

    payload = normalize_grounding(result)

    assert payload["title"] == result.title
    assert payload["summary"] == result.summary
    assert payload["video_src"] == result.video_path
    assert payload["duration_seconds"] > 0

    steps = payload["steps"]
    assert len(steps) == 3
    # orden cronológico y captura anclada por index
    assert [s["index"] for s in steps] == [1, 2, 3]
    for s in steps:
        assert s["timestamp_seconds"] > 0
        assert s["title"]
        # The mock produces a command on odd indexes (1, 3) -> screenshot always present
        assert s["screenshot"]  # la captura debe estar enlazada

    # El primer paso (impar) lleva comando; el visor lo expone.
    assert steps[0]["command"] is not None
    assert steps[1]["command"] is None


def test_adapter_to_grounded_transcript(tmp_path):
    from video_grounding.adapters import to_grounded_transcript

    pipeline = VideoGroundingPipeline(
        grounder=MockVideoGrounder(actions=2, frame_extractor=_fe()),
        frame_extractor=_fe(),
        image_mode="base64",
    )
    result = pipeline.run(_TEST_VIDEO)

    transcript = to_grounded_transcript(result)

    assert len(transcript.segments) == 2
    assert transcript.full_text  # concatena textos de segmentos
    first = transcript.segments[0]
    assert first.start_ms == int(round(result.actions[0].timestamp_seconds * 1000))
    assert first.frame_path is not None
    assert first.frame_timestamp_ms == first.start_ms