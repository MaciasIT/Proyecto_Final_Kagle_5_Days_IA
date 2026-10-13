"""Extraccion de fotogramas clave con ffmpeg.

Ancla las marcas de tiempo [MM:SS] devueltas por Gemini a capturas reales
del video, listas para incrustarse en el Markdown.

Seleccion de seek: se coloca ``-ss`` ANTES de ``-i`` (seek acelarado por
keyframes). Es rapido; la precision es suficiente para documentacion
(margen < 1s en codecs tipicos). Para captura frame-exacta puede activarse
``accurate_seek`` (decodifica desde el inicio, mas lento).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from .schemas import FrameCapture, GroundedAction


@dataclass
class FrameExtractor:
    """Extrae fotogramas de un video mediante ffmpeg/ffprobe."""

    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    image_format: str = "jpg"
    max_width: Optional[int] = 1280
    accurate_seek: bool = False
    image_quality: int = 2  # q:v (2-31, menor = mejor)

    def _require(self, binary: str) -> None:
        if shutil.which(binary) is None:
            raise RuntimeError(
                f"No se encontro el binario '{binary}'. "
                "Instala ffmpeg o pásalo via FrameExtractor(ffmpeg_bin=...)."
            )

    def probe_duration(self, video_path: str) -> float:
        """Devuelve la duracion del video en segundos usando ffprobe."""
        self._require(self.ffprobe_bin)
        cmd = [
            self.ffprobe_bin,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"ffprobe fallo: {proc.stderr.strip()[:300]}")
        duration = proc.stdout.strip()
        try:
            return float(duration)
        except ValueError:
            return 0.0

    def extract_frame(
        self,
        video_path: str,
        timestamp_seconds: float,
        output_path: str,
    ) -> str:
        """Extrae un unico fotograma y devuelve ``output_path``.

        Si se configura ``max_width``, el fotograma se escala manteniendo
        proporcion (evita data-URIs gigantes en el Markdown).
        """
        self._require(self.ffmpeg_bin)
        if not os.path.exists(video_path):
            raise FileNotFoundError(video_path)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        timestamp_seconds = max(0.0, timestamp_seconds)
        cmd = [self.ffmpeg_bin, "-y"]
        if self.accurate_seek:
            # Seek frame-exacto: '-ss' despues de '-i' (decodifica desde 0).
            cmd += ["-i", video_path, "-ss", f"{timestamp_seconds:.3f}"]
        else:
            # Seek rapido por keyframes: '-ss' antes de '-i'.
            cmd += ["-ss", f"{timestamp_seconds:.3f}", "-i", video_path]
        cmd += self._video_filter()
        cmd += ["-frames:v", "1", "-q:v", str(self.image_quality)]
        cmd += ["-f", "image2", output_path]

        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(
                f"ffmpeg no pudo extraer el fotograma en t={timestamp_seconds:.2f}s: "
                f"{proc.stderr.strip()[:300]}"
            )
        return output_path

    def _video_filter(self) -> List[str]:
        if self.max_width:
            # Solo reduce escala, nunca amplia (``min(max_width, iw)``).
            # La coma del ``min(...)`` se escapa como ``\\,`` (sintaxis de filtro).
            return ["-vf", f"scale=min({self.max_width}\\,iw):-2"]
        return []

    def extract_frames(
        self,
        video_path: str,
        actions: List[GroundedAction],
        output_dir: str,
    ) -> List[FrameCapture]:
        """Extrae el fotograma clave de cada accion anclada."""
        os.makedirs(output_dir, exist_ok=True)
        captures: List[FrameCapture] = []
        for action in actions:
            ts = action.timestamp_seconds
            fname = f"frame_{action.index:03d}_{action.timestamp.replace(':', '-')}.{self.image_format}"
            out_path = os.path.join(output_dir, fname)
            self.extract_frame(video_path, ts, out_path)
            width, height = self._read_dimensions(out_path)
            captures.append(
                FrameCapture(
                    action_index=action.index,
                    timestamp_seconds=ts,
                    image_path=out_path,
                    width=width,
                    height=height,
                )
            )
        return captures

    def _read_dimensions(self, image_path: str) -> tuple[int, int]:
        """Lee ancho/alto reales del frame generado (mejor esfuerzo)."""
        self._require(self.ffprobe_bin)
        cmd = [
            self.ffprobe_bin,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            image_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0 and "x" in proc.stdout:
            try:
                w, h = proc.stdout.strip().split("x", 1)
                return int(w), int(h)
            except ValueError:
                pass
        return 0, 0