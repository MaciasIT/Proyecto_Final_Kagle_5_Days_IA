"""Adaptador de contrato para el visor sincronizado (frontend).

El frontend NO define su propio esquema de datos: consume el contrato canónico
que ya definen los agentes de Arquitectura e IA:

- ``video_grounding.schemas.VideoGroundingResult``  (acciones ancladas a
  timestamps + capturas)  ->  es la entrada del visor.
- ``contracts.PipelineResult`` (arquitectura) define las etapas del pipeline
  ->  es la fuente de la barra de progreso de agentes.

Este módulo es un adaptador *sin dependencias* (stdlib puro): recibe el JSON /
dict de un ``VideoGroundingResult`` (o el propio modelo Pydantic vía
``.model_dump()``) y lo normaliza a la forma que el renderizador (`viewer.py`)
sabe dibujar. Así el visor se puede ejecutar y probar sin instalar pydantic ni
streamlit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List

# --------------------------------------------------------------------------- #
# Etapas del pipeline (alineadas con contracts.PipelineResult de arquitectura)
# --------------------------------------------------------------------------- #
# PipelineResult expone: ingest, grounding, analysis, validation, document.
# El frontend añade una etapa final "export" (exportadores Markdown/PDF/Obsidian)
# que ocurre tras el pipeline, para reflejar el flujo completo en la UI.
# --------------------------------------------------------------------------- #

AGENT_STAGES: List[dict] = [
    {"id": "ingest",     "label": "Ingesta",         "icon": "📥"},
    {"id": "grounding",  "label": "Grounding vídeo", "icon": "🎬"},
    {"id": "analysis",   "label": "Análisis",        "icon": "🧠"},
    {"id": "validation", "label": "Validación",      "icon": "✅"},
    {"id": "document",   "label": "Redacción",       "icon": "✍️"},
    {"id": "export",     "label": "Exportación",     "icon": "📦"},
]

STAGE_ORDER = [s["id"] for s in AGENT_STAGES]
STAGE_LABELS = {s["id"]: s["label"] for s in AGENT_STAGES}
STAGE_ICONS = {s["id"]: s["icon"] for s in AGENT_STAGES}


@dataclass
class AgentStageState:
    """Estado puntual de una etapa del pipeline."""
    id: str
    status: str = "pending"  # pending | running | done | error
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Normalización del VideoGroundingResult -> payload del visor
# --------------------------------------------------------------------------- #

def _timestamp_label(seconds: float) -> str:
    """Etiqueta legible ``mm:ss`` (o ``h:mm:ss``)."""
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def normalize_grounding(result) -> dict:
    """Convierte un ``VideoGroundingResult`` (dict o modelo Pydantic) en el
    payload que consume el renderizador del visor.

    Acepta indistintamente:
    - un dict JSON con la forma del esquema (``video_path``, ``duration_seconds``,
      ``title``, ``summary``, ``actions``, ``frames``);
    - un modelo Pydantic con ``.model_dump()`` (o ``.dict()`` en v1).

    Une cada captura (``frames[].image_path``) con su acción por ``action_index``.
    """
    if hasattr(result, "model_dump"):
        data = result.model_dump()
    elif hasattr(result, "dict"):
        data = result.dict()
    else:
        data = dict(result)

    actions = data.get("actions", []) or []
    frames = data.get("frames", []) or []

    # Mapa action_index -> image_path (una captura por acción).
    frame_by_action = {}
    for fr in frames:
        ai = fr.get("action_index")
        if ai is not None and fr.get("image_path"):
            frame_by_action[ai] = fr["image_path"]

    steps = []
    for a in actions:
        idx = a.get("index", len(steps) + 1)
        ts = float(a.get("timestamp_seconds", 0.0) or 0.0)
        steps.append({
            "index": idx,
            "title": a.get("title") or f"Paso {idx}",
            "description": a.get("description") or "",
            "timestamp_seconds": ts,
            "timestamp_label": a.get("timestamp") or _timestamp_label(ts),
            "action_type": a.get("action_type") or "unknown",
            "command": a.get("command"),
            "screenshot": frame_by_action.get(idx),
        })

    return {
        "title": data.get("title") or "Manual técnico",
        "summary": data.get("summary") or "",
        "video_src": data.get("video_path") or data.get("video_src") or "",
        "duration_seconds": data.get("duration_seconds"),
        "source": data.get("source"),
        "steps": steps,
    }


def normalize_grounding_json(text: str) -> dict:
    return normalize_grounding(json.loads(text))
