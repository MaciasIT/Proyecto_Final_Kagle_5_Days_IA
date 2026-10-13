"""Integración del visor con Streamlit.

Streamlit se importa *bajo demanda* dentro de cada función para que el resto
del paquete (`contract`, `viewer`) siga siendo ejecutable sin dependencias.

Expone:
- `render_agent_progress(stages)`: barra de progreso de agentes en Streamlit.
- `render_viewer(payload, stages)`: visor en dos paneles vía `components.html`.
- `make_stage_callback(...)`: convierte los mensajes de `status_callback` del
  pipeline (cadenas) en actualizaciones de estado por etapa, en tiempo real.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from .contract import AGENT_STAGES, STAGE_ORDER, STAGE_LABELS
from .viewer import render_viewer_html

# Mapa de tokens (en el mensaje del pipeline) -> etapa del agente.
# ids alineados con contracts.PipelineResult (arquitectura).
_AGENT_TOKEN_MAP = [
    ("ingest",     re.compile(r"IngestAgent|ingest(?:a|ión)|sub(?:iendo|ida)", re.I)),
    ("grounding",  re.compile(r"Ground(?:ing|er)|transcrip|segment|timestamp|ffmpeg|fotograma|vídeo", re.I)),
    ("analysis",   re.compile(r"AnalystAgent|análisis|analiz|hecho|fact", re.I)),
    ("validation", re.compile(r"Validator|Critic|validación|validar|verific|sintaxis", re.I)),
    ("document",   re.compile(r"TechWriter|redacción|redact|escri|documento", re.I)),
    ("export",     re.compile(r"export|Markdown|PDF|Obsidian", re.I)),
]


def _classify_stage(msg: str) -> Optional[str]:
    """Devuelve el id de etapa al que pertenece un mensaje de estado, o None."""
    for stage_id, pattern in _AGENT_TOKEN_MAP:
        if pattern.search(msg or ""):
            return stage_id
    return None


def make_stage_callback(
    on_update: Callable[[list], None],
    initial_stages: Optional[list] = None,
):
    """Devuelve un `status_callback` compatible con el pipeline que, ante cada
    mensaje, clasifica la etapa del agente y llama a `on_update(stages)`.

    El estado de una etapa pasa a 'running' al detectarse su mensaje de inicio
    y a 'done' al detectarse un mensaje con ✅. Las etapas anteriores quedan
    'done' (pipeline secuencial).
    """
    state = {s["id"]: {"id": s["id"], "status": "pending", "detail": ""}
             for s in AGENT_STAGES}
    if initial_stages:
        for s in initial_stages:
            if s["id"] in state:
                state[s["id"]].update(s)

    def callback(msg: str) -> None:
        stage_id = _classify_stage(msg or "")
        done = "✅" in (msg or "")
        if stage_id:
            if done:
                state[stage_id]["status"] = "done"
                state[stage_id]["detail"] = msg
            else:
                state[stage_id]["status"] = "running"
                state[stage_id]["detail"] = msg
            if stage_id in STAGE_ORDER:
                idx = STAGE_ORDER.index(stage_id)
                for prev in STAGE_ORDER[:idx]:
                    if state[prev]["status"] == "pending":
                        state[prev]["status"] = "done"
        on_update([dict(state[k]) for k in STAGE_ORDER])

    return callback


def render_agent_progress(stages: list):
    """Renderiza la barra de progreso de agentes con Streamlit nativo."""
    import streamlit as st

    cols = st.columns(len(STAGE_ORDER))
    for col, stage_id in zip(cols, STAGE_ORDER):
        s = next((x for x in stages if x["id"] == stage_id),
                 {"id": stage_id, "status": "pending", "detail": ""})
        status = s.get("status", "pending")
        label = STAGE_LABELS.get(stage_id, stage_id)
        if status == "done":
            col.success(f"✅ {label}")
        elif status == "running":
            col.warning(f"⏳ {label}…")
        elif status == "error":
            col.error(f"❌ {label}")
        else:
            col.info(f"⏸ {label}")


def render_viewer(payload: dict, stages: Optional[list] = None, height: int = 720):
    """Embebe el visor HTML en dos paneles dentro de Streamlit."""
    import streamlit.components.v1 as components

    html = render_viewer_html(payload, stages=stages)
    components.html(html, height=height, scrolling=False)
