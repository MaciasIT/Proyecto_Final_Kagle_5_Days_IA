"""Construccion del Markdown final con capturas incrustadas.

Soporta dos modos de incrustado:

  * ``base64`` (por defecto): las capturas se incrustan como data-URI, de
    modo que el ``.md`` resultante es 100% autocontenido. Nota: GitHub no
    renderiza data-URIs en imagenes; para exportar a GitHub usa ``file``.
  * ``file``: se copian los frames a un directorio ``assets/`` y se
    referencian por ruta relativa (compatible con GitHub / Obsidian).
"""

from __future__ import annotations

import base64
import mimetypes
import os
import shutil
from typing import List, Optional

from .schemas import ActionType, FrameCapture, GroundedAction, VideoGroundingResult, format_timestamp


class MarkdownBuilder:
    """Convierte un ``VideoGroundingResult`` en Markdown con capturas."""

    def __init__(self, image_mode: str = "base64"):
        if image_mode not in ("base64", "file"):
            raise ValueError(f"image_mode invalido: {image_mode!r}")
        self.image_mode = image_mode

    def build(
        self,
        result: VideoGroundingResult,
        output_path: Optional[str] = None,
        assets_dir: Optional[str] = None,
    ) -> str:
        """Genera el Markdown y (opcionalmente) lo escribe en ``output_path``."""
        frames_by_index = {f.action_index: f for f in result.frames}
        md = self._header(result)

        if not result.actions:
            md += "\n*No se detectaron acciones en el video.*\n"
        else:
            md += "\n## 🎬 Procedimiento paso a paso\n"
            for action in result.actions:
                frame = frames_by_index.get(action.index)
                md += self._action_section(
                    action, frame, assets_dir or self._default_assets_dir(output_path)
                )

        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as fh:
                fh.write(md)
        return md

    # --- internals ---------------------------------------------------------

    @staticmethod
    def _default_assets_dir(output_path: Optional[str]) -> str:
        return os.path.join(os.path.dirname(output_path) or ".", "assets") if output_path else "assets"

    def _header(self, result: VideoGroundingResult) -> str:
        duration = format_timestamp(result.duration_seconds)
        lines = [
            f"# {result.title}",
            "",
            f"> {result.summary}",
            "",
            f"**Fuente:** `{os.path.basename(result.video_path)}` · "
            f"**Duración:** {duration} · **Modelo:** {result.model}",
            "",
        ]
        return "\n".join(lines)

    def _action_section(
        self,
        action: GroundedAction,
        frame: Optional[FrameCapture],
        assets_dir: str,
    ) -> str:
        lines: List[str] = []
        lines.append(f"### {action.index}. `[{action.timestamp}]` {action.title}")

        if frame:
            image_ref = self._image_reference(frame, assets_dir)
            lines.append("")
            lines.append(f"![Fotograma {action.timestamp}]({image_ref})")

        lines.append("")
        lines.append(action.description)

        if action.command:
            lines.append("")
            lines.append("```bash")
            lines.append(action.command)
            lines.append("```")

        if action.action_type == ActionType.ERROR:
            lines.append("")
            lines.append("> ⚠️ **WARNING:** se detectó un error o mensaje de fallo en este paso.")

        lines.append("")
        return "\n".join(lines)

    def _image_reference(self, frame: FrameCapture, assets_dir: str) -> str:
        if self.image_mode == "base64":
            return self._to_data_uri(frame.image_path)
        return self._copiar_a_assets(frame.image_path, assets_dir)

    @staticmethod
    def _to_data_uri(image_path: str) -> str:
        mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        with open(image_path, "rb") as fh:
            payload = base64.b64encode(fh.read()).decode("ascii")
        return f"data:{mime};base64,{payload}"

    @staticmethod
    def _copiar_a_assets(image_path: str, assets_dir: str) -> str:
        os.makedirs(assets_dir, exist_ok=True)
        fname = os.path.basename(image_path)
        shutil.copy2(image_path, os.path.join(assets_dir, fname))
        return os.path.join("assets", fname).replace(os.sep, "/")