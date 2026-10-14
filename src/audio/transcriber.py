"""Módulo de transcripción local de audio mediante faster-whisper y ffmpeg.

Permite transcribir ficheros de audio y vídeo sin dependencias externas de API,
con cuantización int8 optimizada para ejecución en CPU.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from src.contracts import TranscriptSegment


class LocalTranscriber:
    """Transcriptor local basado en faster-whisper y extracción con ffmpeg."""

    def __init__(
        self,
        model_size: str | None = None,
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "es",
        ffmpeg_bin: str | None = None,
    ) -> None:
        """Inicializa la configuración del transcriptor local.

        La carga de faster-whisper se pospone (lazy import) hasta la llamada
        a `transcribe` para permitir importar el módulo sin la dependencia instalada.

        Args:
            model_size: Tamaño del modelo Whisper ('tiny', 'base', 'small', etc.).
                Si es None, se lee de la variable de entorno WHISPER_MODEL o 'base'.
            device: Dispositivo de cómputo ('cpu', 'cuda', 'auto').
            compute_type: Tipo de cuantización ('int8', 'float16', 'float32', etc.).
            language: Código de idioma por defecto ('es', 'en', etc.).
            ffmpeg_bin: Ruta al ejecutable de ffmpeg. Si es None, busca en FFMPEG_BIN o 'ffmpeg'.
        """
        if model_size is None:
            self.model_size = os.environ.get("WHISPER_MODEL", "base")
        else:
            self.model_size = model_size

        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.ffmpeg_bin = ffmpeg_bin or os.environ.get("FFMPEG_BIN", "ffmpeg")

        self._model: Any = None

    def _get_model(self) -> Any:
        """Obtiene o carga en memoria el modelo Whisper de forma perezosa (lazy).

        Returns:
            Instancia cargada de WhisperModel.

        Raises:
            ImportError: Si faster-whisper no se encuentra instalado en el entorno.
        """
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise ImportError(
                    "La librería 'faster-whisper' no está instalada. "
                    "Instálala con 'pip install faster-whisper' para utilizar LocalTranscriber."
                ) from exc

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def extract_audio(self, video_path: str, output_path: str | None = None) -> str:
        """Extrae la pista de audio de un fichero de vídeo en formato WAV 16kHz mono.

        Args:
            video_path: Ruta al archivo de vídeo de entrada.
            output_path: Ruta de destino para el archivo WAV generado. Si es None,
                se crea un archivo temporal.

        Returns:
            Ruta absoluta o relativa al archivo de audio generado.

        Raises:
            RuntimeError: Si ffmpeg no se encuentra disponible o si la ejecución falla.
        """
        if output_path is None:
            fd, temp_path = tempfile.mkstemp(suffix=".wav", prefix="whisper_audio_")
            os.close(fd)
            output_path = temp_path
        else:
            parent_dir = os.path.dirname(os.path.abspath(output_path))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_path),
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"No se encontró el binario '{self.ffmpeg_bin}'. "
                "Asegúrate de tener ffmpeg instalado y accesible en el PATH."
            ) from exc

        if proc.returncode != 0:
            raise RuntimeError(
                f"Error al extraer audio con ffmpeg: {proc.stderr.strip()}"
            )

        return output_path

    def transcribe(self, audio_path: str) -> list[dict]:
        """Transcribe un fichero de audio y devuelve los segmentos temporizados.

        Args:
            audio_path: Ruta al fichero de audio soportado (WAV, MP3, etc.).

        Returns:
            Lista de diccionarios, donde cada elemento contiene:
                - start_ms (int): Inicio del segmento en milisegundos.
                - end_ms (int): Fin del segmento en milisegundos.
                - text (str): Texto transcrito del segmento.
                - speaker (str | None): Identificador de interlocutor, si existe.
        """
        model = self._get_model()

        kwargs: dict[str, Any] = {}
        if self.language is not None:
            kwargs["language"] = self.language

        segments, _ = model.transcribe(str(audio_path), **kwargs)

        results: list[dict] = []
        for segment in segments:
            start_ms = int(round(segment.start * 1000))
            end_ms = int(round(segment.end * 1000))
            results.append({
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": segment.text.strip(),
                "speaker": getattr(segment, "speaker", None),
            })

        return results

    def transcribe_video(self, video_path: str) -> list[dict]:
        """Wrapper de conveniencia: extrae el audio de un vídeo y lo transcribe.

        El fichero de audio temporal generado durante la extracción es eliminado
        al concluir la transcripción.

        Args:
            video_path: Ruta al archivo de vídeo.

        Returns:
            Lista de segmentos transcritos en milisegundos.
        """
        audio_path = self.extract_audio(video_path)
        try:
            return self.transcribe(audio_path)
        finally:
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except OSError:
                    pass

    def to_transcript_segments(self, raw_segments: list[dict]) -> list[TranscriptSegment]:
        """Convierte segmentos crudos en modelos Pydantic TranscriptSegment.

        Args:
            raw_segments: Lista de diccionarios devuelta por `transcribe`.

        Returns:
            Lista de instancias `TranscriptSegment` conformes a los contratos del proyecto.
        """
        from src.contracts import TranscriptSegment

        return [
            TranscriptSegment(
                segment_id=f"seg_{idx + 1:04d}",
                start_ms=seg["start_ms"],
                end_ms=seg["end_ms"],
                text=seg["text"],
                speaker=seg.get("speaker"),
            )
            for idx, seg in enumerate(raw_segments)
        ]
