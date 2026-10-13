#!/usr/bin/env python3
"""Genera un visor HTML de demostración a partir de un ``VideoGroundingResult``.

Los timestamps de ejemplo son DATOS DE MUESTRA para validar la UI (el grounding
real lo produce el agente de Core IA / Video Grounding). Opcionalmente extrae
capturas reales con ffmpeg para demostrar la sincronización paso ↔ fotograma.

Uso:
    python scripts/demo_viewer.py [--out viewer_demo.html] [--video ruta] [--frames]

Sin dependencias: solo stdlib + ffmpeg (opcional). Sirve el repo con
`python3 -m http.server` y abre el HTML para ver el visor en dos paneles.
"""

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.frontend.contract import AGENT_STAGES, normalize_grounding
from src.frontend.viewer import render_viewer_html


def _fmt(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m:02d}:{s:02d}"


def build_grounding(video_path: str) -> dict:
    """Construye un dict con la forma canónica de ``VideoGroundingResult``."""
    actions = [
        dict(index=1, timestamp="00:02", timestamp_seconds=2.0, end_timestamp="00:07",
             action_type="command", title="Abrir la terminal",
             description="Abrir una terminal con permisos para administrar paquetes del sistema.",
             command="Ctrl+Alt+T"),
        dict(index=2, timestamp="00:08", timestamp_seconds=8.0, end_timestamp="00:17",
             action_type="command", title="Sincronizar repositorios",
             description="Actualizar la base de datos de paquetes antes de actualizar.",
             command="sudo pacman -Sy"),
        dict(index=3, timestamp="00:18", timestamp_seconds=18.0, end_timestamp="00:44",
             action_type="command", title="Actualizar el sistema completo",
             description="Aplicar todas las actualizaciones disponibles a los paquetes instalados.",
             command="sudo pacman -Syu"),
        dict(index=4, timestamp="00:45", timestamp_seconds=45.0, end_timestamp="00:58",
             action_type="observation", title="Revisar el resultado",
             description="Verificar que no hay errores y que el sistema quedó actualizado.",
             command=None),
    ]
    return {
        "video_path": video_path,
        "duration_seconds": 61.67,
        "model": "mock-gemini-2.0",
        "title": "Actualización de paquetes con pacman (Arch Linux)",
        "summary": "Procedimiento para mantener actualizado un sistema Arch Linux con pacman.",
        "actions": actions,
        "frames": [],
    }


def extract_frames(grounding: dict, output_dir: str) -> None:
    """Extrae un fotograma por acción con ffmpeg (opcional, mejor esfuerzo)."""
    video = grounding["video_path"]
    if not os.path.exists(video) or subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        return
    os.makedirs(output_dir, exist_ok=True)
    frames = []
    for a in grounding["actions"]:
        fname = f"frame_{a['index']:03d}.jpg"
        out = os.path.join(output_dir, fname)
        cmd = ["ffmpeg", "-y", "-ss", f"{a['timestamp_seconds']:.3f}", "-i", video,
               "-frames:v", "1", "-q:v", "3", "-f", "image2", out]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0 and os.path.exists(out):
            # Referencia relativa al HTML para que http.server la sirva.
            frames.append({"action_index": a["index"],
                           "timestamp_seconds": a["timestamp_seconds"],
                           "image_path": os.path.relpath(out, os.path.dirname(os.path.abspath(output_dir))) or out,
                           "width": 0, "height": 0})
    grounding["frames"] = frames


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera el visor HTML de demo.")
    parser.add_argument("--out", default="viewer_demo.html")
    parser.add_argument("--video", default="test_data/sudo_pacman_update.webm")
    parser.add_argument("--frames", action="store_true", help="extraer capturas reales con ffmpeg")
    args = parser.parse_args()

    grounding = build_grounding(args.video)
    if args.frames:
        extract_frames(grounding, "assets")

    payload = normalize_grounding(grounding)

    # Estado de agentes ilustrativo: todo 'done' (resultado final).
    stages = [{"id": s["id"], "status": "done", "detail": ""} for s in AGENT_STAGES]

    html = render_viewer_html(payload, stages=stages)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Visor generado en: {os.path.abspath(args.out)}")
    print(f"  Vídeo: {payload['video_src']}")
    print(f"  Pasos: {len(payload['steps'])}")
    print(f"  Capturas: {len(grounding['frames'])}")
    print(f"\nPara verlo: python3 -m http.server 8123  ->  http://localhost:8123/{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
