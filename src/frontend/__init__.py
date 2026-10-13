"""Frontend del visor sincronizado (paquete).

Subpaquete del frontend de Doc Squad v2. Sin dependencias obligatorias:
- `contract`: adapta el contrato canónico (VideoGroundingResult / PipelineResult)
  al payload que consume el visor.
- `viewer`: generador del visor HTML/JS en dos paneles.
- `streamlit_view`: integración con Streamlit (importada bajo demanda).
"""

from .contract import (
    AGENT_STAGES,
    STAGE_ORDER,
    AgentStageState,
    normalize_grounding,
    normalize_grounding_json,
)
from .viewer import render_viewer_html, render_viewer_file

__all__ = [
    "AGENT_STAGES",
    "STAGE_ORDER",
    "AgentStageState",
    "normalize_grounding",
    "normalize_grounding_json",
    "render_viewer_html",
    "render_viewer_file",
]
