"""Tests unitarios para el módulo de transcripción local de audio.

Verifica el comportamiento de LocalTranscriber utilizando mocks sin requerir
la descarga de modelos Whisper ni la ejecución real de inferencia pesada.
"""

from __future__ import annotations

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.audio.transcriber import LocalTranscriber


class _FakeSegment:
    """Segmento simulado que emula la estructura devuelta por faster-whisper."""

    def __init__(
        self,
        start: float,
        end: float,
        text: str,
        speaker: str | None = None,
    ) -> None:
        self.start = start
        self.end = end
        self.text = text
        self.speaker = speaker


def test_model_size_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica la resolución del tamaño del modelo mediante variable de entorno y parámetro."""
    # 1. Sin variable de entorno ni argumento -> 'base' por defecto
    monkeypatch.delenv("WHISPER_MODEL", raising=False)
    transcriber = LocalTranscriber()
    assert transcriber.model_size == "base"

    # 2. Con variable de entorno WHISPER_MODEL
    monkeypatch.setenv("WHISPER_MODEL", "tiny")
    transcriber_env = LocalTranscriber()
    assert transcriber_env.model_size == "tiny"

    # 3. Argumento explícito tiene prioridad sobre variable de entorno
    transcriber_explicit = LocalTranscriber(model_size="small")
    assert transcriber_explicit.model_size == "small"


def test_lazy_import() -> None:
    """Verifica que el módulo se puede inicializar sin faster_whisper instalado."""
    with patch.dict(sys.modules, {"faster_whisper": None}):
        transcriber = LocalTranscriber(model_size="base")
        assert transcriber._model is None

        # Al invocar transcribe o _get_model sin la librería debe elevar ImportError
        with pytest.raises(ImportError, match="faster-whisper"):
            transcriber.transcribe("dummy_audio.wav")


def test_lazy_model_caching() -> None:
    """Verifica que el modelo se instancia de forma perezosa y se cachea tras la primera carga."""
    mock_model_cls = MagicMock()
    fake_instance = MagicMock()
    mock_model_cls.return_value = fake_instance

    with patch.dict(sys.modules, {"faster_whisper": MagicMock(WhisperModel=mock_model_cls)}):
        transcriber = LocalTranscriber(model_size="base", device="cpu", compute_type="int8")
        assert transcriber._model is None

        model1 = transcriber._get_model()
        assert model1 is fake_instance
        assert transcriber._model is fake_instance
        mock_model_cls.assert_called_once_with("base", device="cpu", compute_type="int8")

        # Segunda llamada debe reutilizar la instancia cacheada
        model2 = transcriber._get_model()
        assert model2 is fake_instance
        assert mock_model_cls.call_count == 1


def test_extract_audio_calls_ffmpeg() -> None:
    """Verifica que extract_audio llama a ffmpeg con los argumentos correctos."""
    transcriber = LocalTranscriber()

    # Caso 1: Ruta de salida explícita
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        output = transcriber.extract_audio("input_video.mp4", "output_audio.wav")

        assert output == "output_audio.wav"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]

        assert cmd[0] == transcriber.ffmpeg_bin
        assert "-y" in cmd
        assert "-i" in cmd
        assert "input_video.mp4" in cmd
        assert "-vn" in cmd
        assert "-acodec" in cmd
        assert "pcm_s16le" in cmd
        assert "-ar" in cmd
        assert "16000" in cmd
        assert "-ac" in cmd
        assert "1" in cmd
        assert "output_audio.wav" in cmd

    # Caso 2: Ruta de salida por defecto (fichero temporal)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        temp_output = transcriber.extract_audio("sample.mkv")

        try:
            assert temp_output.endswith(".wav")
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "sample.mkv" in cmd
            assert temp_output in cmd
        finally:
            if os.path.exists(temp_output):
                os.remove(temp_output)

    # Caso 3: Fallo en ffmpeg lanza RuntimeError
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="Error de códec simulado")

        with pytest.raises(RuntimeError, match="Error al extraer audio con ffmpeg"):
            transcriber.extract_audio("bad_video.mp4", "fail.wav")

    # Caso 4: Binario no encontrado lanza RuntimeError
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="No se encontró el binario"):
            transcriber.extract_audio("input.mp4", "fail.wav")


def test_transcribe_parses_segments() -> None:
    """Verifica que transcribe convierte segmentos de float seconds a int milisegundos."""
    fake_segments = [
        _FakeSegment(start=0.0, end=1.5, text="  Hola a todos. "),
        _FakeSegment(start=1.543, end=3.789, text="Bienvenidos a Doc Squad.", speaker="speaker_1"),
    ]
    mock_model = MagicMock()
    mock_model.transcribe.return_value = (fake_segments, MagicMock())

    transcriber = LocalTranscriber(language="es")
    transcriber._model = mock_model

    results = transcriber.transcribe("fake_audio.wav")

    mock_model.transcribe.assert_called_once_with("fake_audio.wav", language="es")

    assert len(results) == 2

    # Primer segmento
    assert results[0]["start_ms"] == 0
    assert results[0]["end_ms"] == 1500
    assert results[0]["text"] == "Hola a todos."
    assert results[0]["speaker"] is None
    assert isinstance(results[0]["start_ms"], int)
    assert isinstance(results[0]["end_ms"], int)

    # Segundo segmento
    assert results[1]["start_ms"] == 1543
    assert results[1]["end_ms"] == 3789
    assert results[1]["text"] == "Bienvenidos a Doc Squad."
    assert results[1]["speaker"] == "speaker_1"
    assert isinstance(results[1]["start_ms"], int)
    assert isinstance(results[1]["end_ms"], int)


def test_transcribe_video_extracts_and_transcribes() -> None:
    """Verifica que transcribe_video coordina la extracción, transcripción y limpieza."""
    transcriber = LocalTranscriber()

    # Creamos un archivo temporal físico para verificar que se elimina en el bloque finally
    fd, temp_audio_file = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    assert os.path.exists(temp_audio_file)

    expected_transcript = [
        {"start_ms": 0, "end_ms": 1200, "text": "Comando ls ejecutado", "speaker": None}
    ]

    transcriber.extract_audio = MagicMock(return_value=temp_audio_file)  # type: ignore[assignment]
    transcriber.transcribe = MagicMock(return_value=expected_transcript)  # type: ignore[assignment]

    result = transcriber.transcribe_video("video_test.mp4")

    transcriber.extract_audio.assert_called_once_with("video_test.mp4")
    transcriber.transcribe.assert_called_once_with(temp_audio_file)
    assert result == expected_transcript

    # Comprobar que el fichero temporal ha sido limpiado tras finalizar
    assert not os.path.exists(temp_audio_file)


def test_to_transcript_segments_contract() -> None:
    """Verifica que to_transcript_segments produce instancias válidas de TranscriptSegment."""
    transcriber = LocalTranscriber()
    raw_segments = [
        {"start_ms": 100, "end_ms": 2500, "text": "Instalando paquetes", "speaker": "root"},
        {"start_ms": 2500, "end_ms": 5000, "text": "Completado con éxito", "speaker": None},
    ]

    segments = transcriber.to_transcript_segments(raw_segments)

    assert len(segments) == 2
    assert segments[0].segment_id == "seg_0001"
    assert segments[0].start_ms == 100
    assert segments[0].end_ms == 2500
    assert segments[0].text == "Instalando paquetes"
    assert segments[0].speaker == "root"

    assert segments[1].segment_id == "seg_0002"
    assert segments[1].start_ms == 2500
    assert segments[1].end_ms == 5000
    assert segments[1].text == "Completado con éxito"
    assert segments[1].speaker is None
