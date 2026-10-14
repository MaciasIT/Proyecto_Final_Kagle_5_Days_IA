"""
Tests unitarios para AudioVideoGrounder (Video Grounding agnóstico con audio y LLM).
"""

import os
from unittest.mock import MagicMock, patch
import pytest

from src.video_grounding.audio_grounder import AudioVideoGrounder
from src.video_grounding.schemas import (
    ActionType,
    GroundedAction,
    GroundingOutput,
)
from src.video_grounding.pipeline import VideoGroundingPipeline


def test_audio_grounder_file_not_found():
    grounder = AudioVideoGrounder()
    with pytest.raises(FileNotFoundError):
        grounder.ground("/nonexistent/video.mp4")


def test_audio_grounder_with_transcript_and_llm(tmp_path):
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"dummy video content")

    mock_llm = MagicMock()
    mock_transcriber = MagicMock()
    mock_frame_extractor = MagicMock()

    mock_frame_extractor.probe_duration.return_value = 30.0
    mock_transcriber.transcribe_video.return_value = [
        {"start_ms": 1000, "end_ms": 5000, "text": "sudo apt-get update", "speaker": None},
        {"start_ms": 6000, "end_ms": 12000, "text": "sistema actualizado", "speaker": None},
    ]

    expected_output = GroundingOutput(
        title="Actualización de paquetes",
        summary="Tutorial de actualización de sistema.",
        actions=[
            GroundedAction(
                index=1,
                timestamp="00:01",
                timestamp_seconds=1.0,
                end_timestamp="00:05",
                action_type=ActionType.COMMAND,
                title="Actualizar repositorios",
                description="Ejecución de apt-get update.",
                command="sudo apt-get update",
            )
        ],
    )
    mock_llm.generate_structured_sync.return_value = expected_output

    grounder = AudioVideoGrounder(
        llm_client=mock_llm,
        transcriber=mock_transcriber,
        frame_extractor=mock_frame_extractor,
    )

    output = grounder.ground(str(video_file), context="Contexto de prueba")
    assert output.title == "Actualización de paquetes"
    assert len(output.actions) == 1
    assert output.actions[0].command == "sudo apt-get update"
    mock_llm.generate_structured_sync.assert_called_once()


def test_audio_grounder_fallback_no_audio(tmp_path):
    video_file = tmp_path / "silent_video.mp4"
    video_file.write_bytes(b"dummy silent video")

    mock_llm = MagicMock()
    mock_transcriber = MagicMock()
    mock_frame_extractor = MagicMock()

    mock_frame_extractor.probe_duration.return_value = 45.0
    mock_transcriber.transcribe_video.return_value = []

    grounder = AudioVideoGrounder(
        llm_client=mock_llm,
        transcriber=mock_transcriber,
        frame_extractor=mock_frame_extractor,
    )

    output = grounder.ground(str(video_file), context="pacman update")
    assert "silent_video.mp4" in output.title
    assert len(output.actions) >= 1
    # Fallback no necesita llamar al LLM si no hay audio
    mock_llm.generate_structured_sync.assert_not_called()


def test_audio_grounder_pipeline_integration(tmp_path):
    video_file = tmp_path / "sample.mp4"
    video_file.write_bytes(b"dummy video")

    mock_llm = MagicMock()
    mock_transcriber = MagicMock()
    mock_frame_extractor = MagicMock()

    mock_frame_extractor.probe_duration.return_value = 20.0
    mock_frame_extractor.extract_frames.return_value = []
    mock_transcriber.transcribe_video.return_value = []

    grounder = AudioVideoGrounder(
        llm_client=mock_llm,
        transcriber=mock_transcriber,
        frame_extractor=mock_frame_extractor,
    )

    pipeline = VideoGroundingPipeline(
        grounder=grounder,
        frame_extractor=mock_frame_extractor,
    )

    result = pipeline.run(str(video_file))
    assert result.video_path == str(video_file)
    assert result.duration_seconds == 20.0
