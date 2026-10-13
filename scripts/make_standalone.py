#!/usr/bin/env python3
"""Genera un visor HTML 100% autocontenido (vídeo embebido como data URL)."""
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.frontend.contract import AGENT_STAGES, normalize_grounding
from src.frontend.viewer import render_viewer_html

VIDEO = "test_data/sample_video.mp4"
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/viewer_standalone.html"

mime = "video/mp4"
with open(VIDEO, "rb") as f:
    b64 = base64.b64encode(f.read()).decode("ascii")
data_url = f"data:{mime};base64,{b64}"

grounding = {
    "video_path": data_url,
    "duration_seconds": 30.0,
    "model": "mock-gemini-2.0",
    "title": "Demo: Visor sincronizado paso a paso",
    "summary": "Visor autocontenido (vídeo embebido). Haz clic en un paso para saltar al timestamp.",
    "actions": [
        {"index": 1, "timestamp": "00:02", "timestamp_seconds": 2.0, "end_timestamp": "00:07",
         "action_type": "command", "title": "Iniciar el proceso",
         "description": "Primer paso del procedimiento de ejemplo.", "command": "echo 'hola doc squad'"},
        {"index": 2, "timestamp": "00:10", "timestamp_seconds": 10.0, "end_timestamp": "00:16",
         "action_type": "command", "title": "Ejecutar comando principal",
         "description": "Comando que realiza la tarea principal del tutorial.", "command": "sudo systemctl status"},
        {"index": 3, "timestamp": "00:18", "timestamp_seconds": 18.0, "end_timestamp": "00:24",
         "action_type": "observation", "title": "Revisar la salida",
         "description": "Observar la salida y verificar que no hay errores.", "command": None},
        {"index": 4, "timestamp": "00:26", "timestamp_seconds": 26.0, "end_timestamp": "00:29",
         "action_type": "configuration", "title": "Aplicar configuración final",
         "description": "Guardar cambios y concluir el procedimiento.", "command": None},
    ],
    "frames": [],
}

payload = normalize_grounding(grounding)
stages = [{"id": s["id"], "status": "done", "detail": ""} for s in AGENT_STAGES]
html = render_viewer_html(payload, stages=stages)

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Escrito {OUT} ({os.path.getsize(OUT)} bytes)")
