# Frontend — Visor interactivo sincronizado paso a paso

Subsistema de interfaz (perfil `frontend`) de **Doc Squad v2**: un visor en dos
paneles que sincroniza el manual técnico generado con el vídeo fuente.

```
┌──────────────────────────────────────────────────────────────────────┐
│  Barra de progreso de agentes: Ingesta → Grounding → Análisis →      │
│  Validación → Redacción → Exportación (actualizable en tiempo real)  │
├────────────────────────────────┬─────────────────────────────────────┤
│  Visor multimedia (vídeo)      │  Manual paso a paso                  │
│                                │  clic en un paso ⇒ salta al          │
│                                │  timestamp del vídeo y reproduce     │
└────────────────────────────────┴─────────────────────────────────────┘
```

## Relación con los contratos canónicos

El frontend **no define su propio esquema**. Consume los contratos que ya
establecen Arquitectura e IA:

- **Entrada del visor**: `video_grounding.schemas.VideoGroundingResult`
  (`video_path`, `duration_seconds`, `title`, `summary`, `actions[]`,
  `frames[]`). Cada `GroundedAction` aporta `timestamp_seconds`, `title`,
  `description`, `command` y `action_type`; cada `FrameCapture` aporta el
  `image_path` por `action_index`.
- **Barra de progreso**: `contracts.PipelineResult` (etapas `ingest`,
  `grounding`, `analysis`, `validation`, `document`) + una etapa final
  `export` (exportadores Markdown/PDF/Obsidian).

`contract.normalize_grounding` adapta el modelo (dict o Pydantic vía
`.model_dump()`) al payload que dibuja el visor, **sin depender de pydantic**.
Así el visor se ejecuta y prueba con stdlib puro.

## Componentes

| Módulo                    | Rol                                                  | Dependencias |
|---------------------------|------------------------------------------------------|--------------|
| `contract.py`             | Adapta `VideoGroundingResult` → payload del visor    | stdlib       |
| `viewer.py`               | Genera el visor HTML/JS autocontenido                | stdlib       |
| `streamlit_view.py`       | Integración con Streamlit (import perezoso)          | streamlit    |
| `scripts/demo_viewer.py`  | Genera un visor HTML de demostración (+ ffmpeg)      | stdlib       |
| `scripts/test_viewer.py`  | Pruebas del adaptador, HTML y progreso               | stdlib       |

## Uso (verificación sin instalar nada)

```bash
# Generar visor de demostración (datos de muestra + capturas reales)
python3 scripts/demo_viewer.py --out viewer_demo.html --frames

# Servir el repo y abrir en el navegador
python3 -m http.server 8123   # → http://localhost:8123/viewer_demo.html

# Pruebas
python3 scripts/test_viewer.py
```

## Integración en Streamlit

```python
from src.frontend.contract import normalize_grounding
from src.frontend.streamlit_view import render_viewer, make_stage_callback, render_agent_progress

# 1) Progreso en tiempo real: envolver el status_callback del pipeline
def on_update(stages):
    render_agent_progress(stages)   # o guardar en st.session_state

callback = make_stage_callback(on_update)

# 2) Renderizar el visor con el resultado del grounding
payload = normalize_grounding(grounding_result)   # VideoGroundingResult
render_viewer(payload, stages, height=720)
```

> Nota: `app.py` (v1) está siendo migrado por Arquitectura/Dev. La integración
> del visor se documenta aquí para no colisionar con esa migración en curso.

## API JS expuesta por el visor

El documento generado expone `window.__viewer` con:

- `seekTo(seconds)` — salta el vídeo a un instante y reproduce.
- `setAgentStage(id, status, detail)` — actualiza una etapa de la barra de
  progreso en vivo (útil para componentes bi-direccionales de Streamlit).
