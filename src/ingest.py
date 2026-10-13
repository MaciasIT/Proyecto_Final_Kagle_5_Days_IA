"""
src.ingest — Ingesta multi-fuente (Doc Squad v2).

Implementa la etapa de ingesta del RFC-002: resuelve un ``MediaSource``
(fichero local, URL de YouTube, grabación de pantalla o sesión asciinema)
y produce un ``IngestResult`` con uno o varios ``MediaAsset`` tipados.

Esta etapa es **pura y determinista** en su núcleo: la resolución de fuentes
(descarga de YouTube, transcripción de .cast, captura de pantalla) no depende
de Gemini.  La subida a Gemini (``client.files.upload``) es un paso opcional y
explícito en :func:`upload_assets`, separado para poder testear la resolución
sin credenciales.

Alineación con ``src.contracts`` (fuente de verdad del RFC-002 — §11):

- Entrada:  ``MediaSource`` (``source_type`` + ``locator``).
- Salida:   ``IngestResult`` (lista de ``MediaAsset`` con ``kind`` y ``status``).
- ``MediaSourceType`` y ``MediaKind`` provienen de ``contracts.py``; este
  módulo **no redefine** esquemas propios.

Dependencias externas (lazy): ``yt_dlp`` (o el binario ``yt-dlp``) y
``google.genai`` (solo para subir).  ffmpeg para la captura de pantalla y las
capturas (grounding, task IA).  El parseo de asciinema es stdlib puro.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from src.contracts import (
    IngestResult,
    MediaAsset,
    MediaKind,
    MediaSource,
    MediaSourceType,
)


# --------------------------------------------------------------------------- #
#  Clasificación por extensión
# --------------------------------------------------------------------------- #

VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".flv", ".m4v", ".gif"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".opus"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def classify_kind(path_or_ext: str) -> MediaKind:
    """Clasifica un fichero en ``MediaKind`` según su extensión."""
    ext = os.path.splitext(path_or_ext)[1].lower()
    if ext in VIDEO_EXTS:
        return MediaKind.VIDEO
    if ext in AUDIO_EXTS:
        return MediaKind.AUDIO
    if ext in IMAGE_EXTS:
        return MediaKind.IMAGE
    return MediaKind.TEXT


# Regex de detección de URLs de YouTube (clásico, corto, Shorts, embed, live).
YOUTUBE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.|m\.|music\.)?"
    r"(?:youtube\.com/(?:watch\?.*v=|shorts/|embed/|live/)"
    r"|youtu\.be/)",
    re.IGNORECASE,
)

# Eliminación de secuencias de escape ANSI (CSI + OSC).
ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ANSI_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def strip_ansi(text: str) -> str:
    """Elimina secuencias de escape ANSI/OSC de una cadena."""
    text = ANSI_OSC_RE.sub("", text)
    return ANSI_CSI_RE.sub("", text)


# --------------------------------------------------------------------------- #
#  Detección de tipo de fuente
# --------------------------------------------------------------------------- #

def detect_source_type(locator: str) -> MediaSourceType:
    """Infiera el ``MediaSourceType`` de un ``locator`` dado.

    Orden: URL de YouTube -> .cast -> extensión multimedia -> fichero local
    existente -> texto crudo.
    """
    if not locator or not locator.strip():
        raise ValueError("locator vacío: no se puede inferir una fuente.")

    ref = locator.strip()

    if YOUTUBE_URL_RE.search(ref):
        return MediaSourceType.YOUTUBE_URL

    if ref.lower().endswith(".cast"):
        return MediaSourceType.ASCIINEMA

    ext = os.path.splitext(ref.split("?")[0])[1].lower()
    if ext in VIDEO_EXTS or ext in AUDIO_EXTS or ext in IMAGE_EXTS:
        return MediaSourceType.LOCAL_FILE

    if os.path.isfile(ref):
        return MediaSourceType.LOCAL_FILE

    # Sin extensión reconocible y sin fichero -> se trata como texto crudo.
    return MediaSourceType.TEXT


# --------------------------------------------------------------------------- #
#  YouTube (yt-dlp)
# --------------------------------------------------------------------------- #

def _ytdlp_binary() -> Optional[str]:
    return shutil.which("yt-dlp")


def download_youtube(url: str, out_dir: Optional[str] = None) -> Tuple[str, dict]:
    """Descarga un vídeo de YouTube y devuelve ``(ruta_local, info)``.

    Prioriza el módulo ``yt_dlp``; si no está, usa el binario ``yt-dlp`` del
    sistema.  El formato elegido es el mejor MP4 individual (audio+vídeo) para
    máxima compatibilidad con la API de archivos de Gemini.
    """
    out_dir = out_dir or tempfile.mkdtemp(prefix="doc_squad_yt_")
    os.makedirs(out_dir, exist_ok=True)

    try:
        import yt_dlp  # lazy
    except ImportError:
        return _download_youtube_cli(url, out_dir)

    ydl_opts = {
        # Video+audio separados (DASH) con merge a mp4; fallback a combinado.
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # Determinar la ruta final (tras el merge a mp4, si aplica).
        requested = info.get("requested_downloads") or []
        if requested and requested[0].get("filepath"):
            path = requested[0]["filepath"]
        else:
            path = ydl.prepare_filename(info)

    if not os.path.exists(path):
        # Fallback: localizar el fichero por id en el directorio de salida.
        vid = info.get("id")
        matches = [
            os.path.join(out_dir, f)
            for f in os.listdir(out_dir)
            if vid and f.startswith(vid)
        ]
        if matches:
            path = sorted(matches, key=lambda p: -os.path.getsize(p))[0]

    if not os.path.exists(path):
        raise FileNotFoundError(f"yt-dlp no generó el fichero esperado: {path}")
    return path, info


def _download_youtube_cli(url: str, out_dir: str) -> Tuple[str, dict]:
    binary = _ytdlp_binary()
    if not binary:
        raise RuntimeError(
            "yt-dlp no está disponible: instala `pip install yt-dlp` o el binario."
        )
    outtmpl = os.path.join(out_dir, "%(id)s.%(ext)s")
    cmd = [
        binary,
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "--output", outtmpl,
        "--no-playlist",
        "--print", "after_move:filepath",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp falló: {proc.stderr.strip()}")

    path = proc.stdout.strip().splitlines()[-1].strip()
    if not os.path.exists(path):
        raise FileNotFoundError(f"yt-dlp no generó el fichero esperado: {path}")
    return path, {"title": os.path.basename(path)}


# --------------------------------------------------------------------------- #
#  asciinema (.cast)
# --------------------------------------------------------------------------- #

def parse_cast(path: str) -> Tuple[dict, List[Tuple[float, str, str]]]:
    """Parsea un fichero asciinema (.cast, JSONL) a ``(header, events)``.

    ``events`` es una lista de ``(time, type, data)`` con ``type`` ``"o"``
    (salida) o ``"i"`` (entrada del usuario).
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()

    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        raise ValueError(f"El fichero {path} está vacío.")

    header: dict = {}
    events: List[Tuple[float, str, str]] = []

    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            header = obj.get("header", {})
            events = [(float(e[0]), e[1], e[2]) for e in obj.get("events", [])]
        elif isinstance(obj, list):
            events = [(float(e[0]), e[1], e[2]) for e in obj]
        else:
            raise ValueError("Formato .cast no reconocido (objeto JSON inesperado).")
    except json.JSONDecodeError:
        first = json.loads(lines[0])
        if isinstance(first, dict) and "version" in first:
            header, rest = first, lines[1:]
        else:
            header, rest = {}, lines
        for ln in rest:
            ev = json.loads(ln)
            events.append((float(ev[0]), ev[1], ev[2]))

    if not events:
        raise ValueError(f"No se encontraron eventos en {path}.")
    return header, events


def extract_input_commands(events: List[Tuple[float, str, str]]) -> List[str]:
    """Extrae los comandos tecleados a partir de los eventos ``"i"``."""
    raw = "".join(data for _, etype, data in events if etype == "i")
    lines = re.split(r"[\r\n]+", raw)
    return [ln.rstrip() for ln in lines if ln.rstrip()]


def render_output(
    events: List[Tuple[float, str, str]],
    width: Optional[int] = None,
) -> str:
    """Reconstruye la salida visible del terminal a partir de los eventos ``"o"``.

    Emula retorno de carro (\\r), salto de línea (\\n) y retroceso (\\b); las
    secuencias ANSI se eliminan.
    """
    width = width or 80
    lines: List[str] = [""]
    col = 0

    for _, etype, data in events:
        if etype != "o":
            continue
        for ch in strip_ansi(data):
            if ch == "\r":
                col = 0
            elif ch == "\n":
                lines.append("")
                col = 0
            elif ch == "\b":
                col = max(0, col - 1)
            else:
                cur = lines[-1]
                if len(cur) < col + 1:
                    cur = cur.ljust(col + 1)
                lines[-1] = cur[:col] + ch + cur[col + 1:]
                col += 1

    return "\n".join(lines).rstrip()


def cast_to_transcript(
    path: str,
    include_commands: bool = True,
    include_output: bool = True,
) -> str:
    """Convierte un .cast en texto legible para el AnalystAgent."""
    header, events = parse_cast(path)
    width = int(header.get("width", 80))

    parts: List[str] = ["=== SESIÓN DE TERMINAL (asciinema) ==="]
    if header.get("command"):
        parts.append(f"Comando de grabación: {header['command']}")

    if include_commands:
        commands = extract_input_commands(events)
        if commands:
            parts.append("")
            parts.append("Comandos ejecutados:")
            for idx, cmd in enumerate(commands, start=1):
                parts.append(f"  {idx}. {cmd}")

    if include_output:
        output = render_output(events, width=width)
        if output.strip():
            parts.append("")
            parts.append("Salida del terminal (renderizada):")
            parts.append(output)

    return "\n".join(parts)


# --------------------------------------------------------------------------- #
#  Grabación de pantalla (ffmpeg x11grab)
# --------------------------------------------------------------------------- #

class ScreenRecorder:
    """Grabador de pantalla en vivo basado en ``ffmpeg`` (x11grab / XWayland).

    Ejemplo::

        rec = ScreenRecorder("sesion.mp4", size="1280x720")
        rec.start()
        # ... hacer la demo en pantalla ...
        rec.stop()   # -> "sesion.mp4"
    """

    def __init__(
        self,
        output_path: str,
        size: str = "1920x1080",
        framerate: int = 30,
        display: Optional[str] = None,
        with_audio: bool = False,
        audio_device: str = "default",
        preset: str = "ultrafast",
    ) -> None:
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg no está disponible en el PATH.")
        self.output_path = output_path
        self.size = size
        self.framerate = framerate
        self.display = display or os.environ.get("DISPLAY", ":0.0")
        self.with_audio = with_audio
        self.audio_device = audio_device
        self.preset = preset
        self._proc: Optional[subprocess.Popen] = None

    def _build_command(self) -> List[str]:
        cmd = [
            "ffmpeg", "-y",
            "-f", "x11grab",
            "-video_size", self.size,
            "-framerate", str(self.framerate),
            "-i", self.display,
        ]
        if self.with_audio:
            cmd += ["-f", "pulse", "-i", self.audio_device]
        cmd += [
            "-c:v", "libx264",
            "-preset", self.preset,
            "-pix_fmt", "yuv420p",
            self.output_path,
        ]
        return cmd

    def start(self) -> "ScreenRecorder":
        if self._proc is not None:
            raise RuntimeError("La grabación ya está en curso.")
        self._proc = subprocess.Popen(
            self._build_command(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return self

    def is_recording(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def stop(self) -> str:
        if self._proc is None:
            raise RuntimeError("No hay ninguna grabación en curso.")
        self._proc.terminate()
        try:
            self._proc.wait(timeout=15)
        finally:
            self._proc = None
        return self.output_path

    def __enter__(self) -> "ScreenRecorder":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()


def record_screen(duration_seconds: float, output_path: str, **kwargs) -> str:
    """Graba la pantalla ``duration_seconds`` y devuelve la ruta del vídeo."""
    rec = ScreenRecorder(output_path, **kwargs)
    rec.start()
    try:
        time.sleep(duration_seconds)
    finally:
        rec.stop()
    return output_path


# --------------------------------------------------------------------------- #
#  Utils internos para construir MediaAsset
# --------------------------------------------------------------------------- #

def _new_asset_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _write_text_file(text: str, suffix: str = ".txt") -> str:
    """Escribe ``text`` en un fichero temporal y devuelve su ruta."""
    fd, path = tempfile.mkstemp(prefix="doc_squad_", suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


# --------------------------------------------------------------------------- #
#  Punto de entrada: MediaSource -> IngestResult
# --------------------------------------------------------------------------- #

def ingest(source: MediaSource, work_dir: Optional[str] = None) -> IngestResult:
    """Resuelve un ``MediaSource`` a un ``IngestResult`` (sin subir a Gemini).

    - YOUTUBE_URL: descarga el vídeo -> ``MediaAsset`` VIDEO (local_path).
    - ASCIINEMA:   transcribe el .cast -> ``MediaAsset`` TEXT (local_path a un .txt).
    - LOCAL_FILE / RECORDING: resuelve el fichero -> ``MediaAsset`` con el
      ``kind`` inferido de la extensión.
    - TEXT:        texto crudo (o ruta a .txt) -> ``MediaAsset`` TEXT.

    La subida a Gemini es un paso posterior (ver :func:`upload_asset`).
    """
    warnings: List[str] = []

    # Si no se especificó el tipo, se infiere del locator.
    source_type = source.source_type
    if source_type is None:
        source_type = detect_source_type(source.locator)

    assets: List[MediaAsset] = []

    if source_type == MediaSourceType.YOUTUBE_URL:
        path, info = download_youtube(source.locator, out_dir=work_dir)
        title = (info.get("title") if isinstance(info, dict) else None) or source.title
        assets.append(
            MediaAsset(
                asset_id=_new_asset_id(),
                source_type=source_type,
                kind=classify_kind(path),
                local_path=path,
                mime_type="video/mp4",
                status="ready",
                uploaded_at=None,
            )
        )
    elif source_type == MediaSourceType.ASCIINEMA:
        transcript = cast_to_transcript(source.locator)
        txt_path = _write_text_file(transcript)
        assets.append(
            MediaAsset(
                asset_id=_new_asset_id(),
                source_type=source_type,
                kind=MediaKind.TEXT,
                local_path=txt_path,
                mime_type="text/plain",
                status="ready",
            )
        )
    elif source_type in (MediaSourceType.LOCAL_FILE, MediaSourceType.RECORDING):
        path = source.locator
        if not os.path.exists(path):
            raise FileNotFoundError(f"El fichero de ingesta no existe: {path}")
        assets.append(
            MediaAsset(
                asset_id=_new_asset_id(),
                source_type=source_type,
                kind=classify_kind(path),
                local_path=path,
                mime_type=None,
                status="ready",
            )
        )
    elif source_type == MediaSourceType.TEXT:
        # locator puede ser una ruta a un fichero de texto o texto crudo.
        if os.path.isfile(source.locator):
            txt_path = os.path.abspath(source.locator)
        else:
            txt_path = _write_text_file(source.locator)
        assets.append(
            MediaAsset(
                asset_id=_new_asset_id(),
                source_type=source_type,
                kind=MediaKind.TEXT,
                local_path=txt_path,
                mime_type="text/plain",
                status="ready",
            )
        )
    else:
        raise ValueError(f"Tipo de fuente no soportado: {source_type}")

    return IngestResult(
        assets=assets,
        request_context=None,
        warnings=warnings,
    )


# --------------------------------------------------------------------------- #
#  Subida a Gemini (opcional; requiere google-genai y GOOGLE_API_KEY)
# --------------------------------------------------------------------------- #

def upload_asset(asset: MediaAsset, api_key: Optional[str] = None) -> MediaAsset:
    """Sube un ``MediaAsset`` a Gemini y actualiza ``uri``/``status``/``uploaded_at``.

    Usa el SDK oficial ``google-genai`` (``client.files.upload``) tal como
    prescribe el RFC-002.  Solo aplica a medios (VIDEO/AUDIO/IMAGE); los
    activos TEXT no se suben (viajan como transcripción).
    """
    if asset.kind == MediaKind.TEXT:
        # El texto no se sube como archivo multimedia.
        return asset

    from google import genai  # lazy: solo aquí se necesita el SDK

    if not asset.local_path:
        raise ValueError("MediaAsset sin local_path no se puede subir.")

    client = genai.Client(api_key=api_key or os.getenv("GOOGLE_API_KEY"))
    asset.status = "processing"
    uploaded = client.files.upload(file=asset.local_path)

    # Espera activa con tope de riesgo (estado tipado FileState del SDK).
    deadline = time.monotonic() + 300  # 5 minutos máx.
    while uploaded.state.name in ("PROCESSING", "PENDING") and time.monotonic() < deadline:
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)

    if uploaded.state.name == "FAILED":
        asset.status = "failed"
        asset.error = "El procesamiento del fichero falló en Gemini."
        return asset

    asset.uri = uploaded.uri
    asset.status = "active"
    asset.uploaded_at = _now()
    return asset


def upload_assets(result: IngestResult, api_key: Optional[str] = None) -> IngestResult:
    """Sube todos los ``MediaAsset`` de un ``IngestResult`` a Gemini."""
    for asset in result.assets:
        upstream = upload_asset(asset, api_key=api_key)
        if upstream.status == "failed":
            result.warnings.append(
                f"Asset {asset.asset_id} falló al subir: {asset.error}"
            )
    return result