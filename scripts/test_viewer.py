#!/usr/bin/env python3
"""Pruebas del frontend del visor sincronizado (sin dependencias externas).

Valida:
- ``normalize_grounding``: adapta un ``VideoGroundingResult`` (forma canónica)
  al payload del visor, uniendo capturas por ``action_index``.
- Etiquetas de timestamp y generación del HTML.
- Clasificación de mensajes del pipeline -> etapa y progreso en tiempo real.

Ejecutar:  python3 scripts/test_viewer.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.frontend.contract import (
    AGENT_STAGES, STAGE_ORDER, normalize_grounding,
)
from src.frontend.viewer import render_viewer_html
from src.frontend.streamlit_view import make_stage_callback, _classify_stage


def check(cond, label):
    print(f"[{'PASS' if cond else 'FAIL'}] {label}")
    return cond


def sample_grounding() -> dict:
    return {
        "video_path": "test_data/x.webm",
        "duration_seconds": 61.67,
        "model": "gemini-2.0-flash",
        "title": "Manual demo",
        "summary": "Resumen de demo.",
        "actions": [
            {"index": 1, "timestamp": "00:03", "timestamp_seconds": 3.0,
             "end_timestamp": "00:08", "action_type": "command",
             "title": "Paso 1", "description": "Primero", "command": "ls"},
            {"index": 2, "timestamp": "00:09", "timestamp_seconds": 9.5,
             "end_timestamp": "00:14", "action_type": "observation",
             "title": "Paso 2", "description": "Segundo", "command": None},
        ],
        "frames": [
            {"action_index": 1, "timestamp_seconds": 3.0,
             "image_path": "assets/frame_001.jpg", "width": 1280, "height": 720},
        ],
    }


def main():
    ok = True
    payload = normalize_grounding(sample_grounding())

    # 1. normalize_grounding
    ok &= check(payload["title"] == "Manual demo", "normalize: title")
    ok &= check(payload["video_src"] == "test_data/x.webm", "normalize: video_src -> video_path")
    ok &= check(len(payload["steps"]) == 2, "normalize: 2 pasos")
    ok &= check(payload["steps"][0]["timestamp_seconds"] == 3.0, "normalize: timestamp")
    ok &= check(payload["steps"][0]["command"] == "ls", "normalize: command singular")
    ok &= check(payload["steps"][1]["command"] is None, "normalize: command None")
    ok &= check(payload["steps"][0]["screenshot"] == "assets/frame_001.jpg", "normalize: une frame por action_index")
    ok &= check(payload["steps"][1]["screenshot"] is None, "normalize: paso sin captura")
    ok &= check(payload["steps"][0]["timestamp_label"] == "00:03", "normalize: conserva timestamp MM:SS")

    # 2. timestamp_label derivado cuando no hay 'timestamp' (formato h:mm:ss)
    g2 = sample_grounding()
    del g2["actions"][0]["timestamp"]
    g2["actions"][0]["timestamp_seconds"] = 3723.0
    p2 = normalize_grounding(g2)
    ok &= check(p2["steps"][0]["timestamp_label"] == "1:02:03", "normalize: deriva label h:mm:ss")

    # 3. HTML
    html = render_viewer_html(payload, stages=[{"id": "grounding", "status": "running", "detail": ""}])
    ok &= check('<video id="player"' in html, "HTML incluye <video id=player>")
    ok &= check("Paso 1" in html and "Paso 2" in html, "HTML incluye títulos de pasos")
    ok &= check('id="steps-list"' in html, "HTML incluye contenedor de pasos")
    ok &= check("setAgentStage" in html, "HTML expone setAgentStage (progreso en vivo)")
    ok &= check("seekTo" in html, "HTML expone seekTo (salto a timestamp)")
    ok &= check('src="test_data/x.webm"' in html, "HTML usa video_src correcto")
    ok &= check('data-status="running"' in html, "HTML refleja estado running")

    # 4. Barra con las 6 etapas canónicas
    for sid in STAGE_ORDER:
        ok &= check(f'data-id="{sid}"' in html, f"barra incluye etapa {sid}")
    ok &= check(len(STAGE_ORDER) == 6, "6 etapas (5 pipeline + export)")

    # 5. Clasificación de mensajes -> etapa
    ok &= check(_classify_stage("🤖 IngestAgent: Subiendo...") == "ingest", "clasifica ingest")
    ok &= check(_classify_stage("Grounding: analizando vídeo...") == "grounding", "clasifica grounding")
    ok &= check(_classify_stage("AnalystAgent: Analizando...") == "analysis", "clasifica analysis")
    ok &= check(_classify_stage("ValidatorAgent: revisando sintaxis") == "validation", "clasifica validation")
    ok &= check(_classify_stage("TechWriterAgent: Redactando") == "document", "clasifica document")
    ok &= check(_classify_stage("Exportando a PDF") == "export", "clasifica export")
    ok &= check(_classify_stage("nada") is None, "no clasifica mensaje ajeno")

    # 6. Progreso en tiempo real (mapeo secuencial)
    snap = []
    cb = make_stage_callback(snap.append)
    for m in ["🤖 IngestAgent: Subiendo...", "✅ IngestAgent: listo",
              "Grounding: analizando...", "✅ Grounding: timestamps listos"]:
        cb(m)
    by = {s["id"]: s["status"] for s in snap[-1]}
    ok &= check(by["ingest"] == "done" and by["grounding"] == "done", "etapas previas auto-done")
    ok &= check(by["analysis"] == "pending", "etapa posterior pendiente")

    print("\n" + ("TODAS LAS PRUEBAS PASARON ✅" if ok else "HAY FALLOS ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
