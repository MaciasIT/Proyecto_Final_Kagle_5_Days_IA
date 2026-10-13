"""CLI para generar documentacion con video grounding.

Uso:
    python -m video_grounding video.mp4 -o doc.md
    python -m video_grounding video.mp4 --mock -o doc.md
    python -m video_grounding video.mp4 --image-mode file -o doc.md
"""

from __future__ import annotations

import argparse
import os
import sys

from .frames import FrameExtractor
from .grounder import GeminiVideoGrounder
from .mock import MockVideoGrounder
from .pipeline import VideoGroundingPipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="video_grounding",
        description="Indexa marcas [MM:SS] con Gemini 2.0, extrae frames con "
        "ffmpeg y genera Markdown con capturas.",
    )
    p.add_argument("video", help="Ruta al archivo de video")
    p.add_argument("-o", "--output", default=None, help="Ruta del Markdown de salida")
    p.add_argument("--context", default="", help="Contexto adicional para el analisis")
    p.add_argument(
        "--model",
        default=None,
        help="Modelo Gemini (por defecto gemini-2.0-flash; tambien gemini-2.5-flash)",
    )
    p.add_argument("--api-key", default=None, help="GEMINI_API_KEY (o usa el entorno)")
    p.add_argument(
        "--image-mode",
        choices=["base64", "file"],
        default="base64",
        help="Como incrustar las capturas (base64 autocontenido o assets/ relativo)",
    )
    p.add_argument(
        "--mock",
        action="store_true",
        help="Usa grounder deterministico (sin API) para validar el pipeline",
    )
    p.add_argument("--mock-actions", type=int, default=6, help="Acciones para --mock")
    p.add_argument("--max-width", type=int, default=1280, help="Ancho max de las capturas")
    p.add_argument("--ffmpeg", default="ffmpeg", help="Ruta del binario ffmpeg")
    p.add_argument("--ffprobe", default="ffprobe", help="Ruta del binario ffprobe")
    p.add_argument("--keep-frames", action="store_true", help="No borrar los frames temporales")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if not os.path.exists(args.video):
        print(f"ERROR: no existe el video {args.video}", file=sys.stderr)
        return 2

    extractor = FrameExtractor(
        ffmpeg_bin=args.ffmpeg,
        ffprobe_bin=args.ffprobe,
        max_width=args.max_width,
    )

    if args.mock:
        grounder = MockVideoGrounder(
            actions=args.mock_actions, frame_extractor=extractor
        )
    else:
        grounder = GeminiVideoGrounder(
            api_key=args.api_key,
            model=args.model,
        )

    pipeline = VideoGroundingPipeline(
        grounder=grounder,
        frame_extractor=extractor,
        image_mode=args.image_mode,
        keep_frames=args.keep_frames,
    )

    print(f"Analizando {args.video} con modelo {grounder.model} ...")
    result = pipeline.run(
        args.video,
        context=args.context,
        output_path=args.output,
    )

    print(f"OK: {len(result.actions)} acciones indexadas, "
          f"{len(result.frames)} capturas extraidas.")
    if args.output:
        print(f"Markdown generado: {args.output}")
    else:
        print("--- Markdown (stdout) ---")
        sys.stdout.write(
            pipeline.markdown_builder.build(result)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())