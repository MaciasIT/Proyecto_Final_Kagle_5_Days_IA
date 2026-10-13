# Video Grounding — Core IA (F2)

Módulo que explota la capacidad multimodal nativa de **Gemini 2.0** para
indexar marcas de tiempo `[MM:SS]` por cada acción detectada en un vídeo,
extraer el fotograma clave de cada marca con **ffmpeg** e incrustar esas
capturas directamente en el **Markdown** generado.

## Arquitectura

```
video.mp4
   │
   ▼
┌──────────────────────────┐     ┌──────────────────────────┐     ┌───────────────────────┐
│  Grounder (Gemini 2.0)  │ ──▶ │  FrameExtractor (ffmpeg) │ ──▶ │  MarkdownBuilder      │
│  acciones + [MM:SS]     │     │  fotogramas JPG por marca │     │  capturas incrustadas │
└──────────────────────────┘     └──────────────────────────┘     └───────────────────────┘
```

El contrato de datos entre componentes usa **Pydantic** (`schemas.py`),
alineado con la migración a `google-genai` del hito F1.

### Componentes

| Módulo | Responsabilidad |
| --- | --- |
| `schemas.py` | Contratos Pydantic: `GroundedAction`, `GroundingOutput`, `FrameCapture`, `VideoGroundingResult`, utilidades de timestamp. |
| `grounder.py` | `GeminiVideoGrounder`: sube el vídeo, solicita a Gemini 2.0 salida JSON estructurada de acciones con marcas `[MM:SS]` (`response_schema` = modelo Pydantic). |
| `frames.py` | `FrameExtractor`: extrae un JPG por marca con ffmpeg/ffprobe (escala solo a la baja, seek rápido por keyframes). |
| `markdown_builder.py` | `MarkdownBuilder`: monta el `.md` final. Modo `base64` (autocontenido) o `file` (carpeta `assets/`). |
| `pipeline.py` | `VideoGroundingPipeline`: orquesta los tres pasos e inyecta el grounder (real o mock). |
| `mock.py` | `MockVideoGrounder`: grounder determinista sin API, para tests/CI. |
| `cli.py` | CLI. |

## Uso

### CLI

```bash
# Requiere GOOGLE_API_KEY / GEMINI_API_KEY en el entorno
PYTHONPATH=src python -m video_grounding video.mp4 -o doc.md

# Modo offline (valida el pipeline completo sin API)
PYTHONPATH=src python -m video_grounding video.mp4 --mock --mock-actions 6 -o doc.md

# Capturas como archivos (compatible GitHub/Obsidian) en vez de base64
PYTHONPATH=src python -m video_grounding video.mp4 --image-mode file -o doc.md
```

Opciones relevantes: `--context`, `--model` (por defecto `gemini-2.0-flash`;
también vale `gemini-2.5-flash`), `--api-key`, `--max-width`,
`--ffmpeg` / `--ffprobe`, `--keep-frames`.

### Programático

```python
from video_grounding import (
    GeminiVideoGrounder, FrameExtractor, VideoGroundingPipeline
)

grounder = GeminiVideoGrounder(model="gemini-2.0-flash")
pipeline = VideoGroundingPipeline(
    grounder=grounder,
    image_mode="base64",       # o "file"
)
result = pipeline.run("video.mp4", context="Tutorial de Nginx",
                      output_path="doc.md")
```

## Contrato de datos (resumen)

`GroundingOutput` (lo que devuelve Gemini):

```json
{
  "title": "...",
  "summary": "...",
  "actions": [
    {
      "index": 1,
      "timestamp": "00:12",
      "timestamp_seconds": 12.0,
      "end_timestamp": "00:17",
      "action_type": "command",
      "title": "Instalar nginx",
      "description": "...",
      "command": "sudo pacman -S nginx"
    }
  ]
}
```

Cada acción produce una sección de Markdown con su `[MM:SS]`, su captura
incrustada, la descripción y (si aplica) el bloque de comando. Las acciones
de tipo `error` añaden automáticamente una nota `WARNING`.

## Contrato y frontera con otros agentes

- **Contrato canónico del visor**: el frontend (`t_d110ce31`) consume
  `video_grounding.schemas.VideoGroundingResult` directamente vía
  `src/frontend/contract.py::normalize_grounding` (adaptador sin pydantic).
  **Los nombres de campo son la frontera del visor sincronizado**: no cambiar
  `GroundedAction` (`index`, `timestamp`, `timestamp_seconds`, `action_type`,
  `title`, `description`, `command`), `FrameCapture` (`image_path`,
  `action_index`) ni `VideoGroundingResult` (`video_path`, `duration_seconds`,
  `title`, `summary`, `actions`, `frames`) sin avisar.
- **Puente al RFC-002**: `video_grounding.adapters.to_grounded_transcript`
  convierte un `VideoGroundingResult` en el `contracts.GroundedTranscript`
  (sin cambiar los nombres de campo de grounding) para rellenar
  `PipelineResult.grounding`. Es una función de compatibilidad, no un cambio
  de contrato.

## Notas y decisiones

- **Modelo por defecto**: `gemini-2.0-flash` (estable, multimodal con vídeo).
  `gemini-2.0-pro-exp` / `gemini-2.5-flash` son alternativas configurables.
  El nombre se puede fijar con la variable de entorno `GEMINI_MODEL`.
- **Precisión de timestamp**: Gemini 2.0 segmenta por contenido visual; las
  marcas son aproximadas. ffmpeg extrae el fotograma *real* en esa marca con
  seek rápido (`-ss` antes de `-i`). Para captura frame-exacta usar
  `FrameExtractor(accurate_seek=True)` (más lento).
- **Escalado**: `max_width` (por defecto 1280) solo reduce escala, nunca
  amplía (`min(width, iw)`), para que las data-URIs no engorden el `.md`.
- **Limitación conocida**: GitHub no renderiza imágenes `data:image/*` en
  Markdown. Para exportar a GitHub/Obsidian usa `--image-mode file`, que
  escribe las capturas en una carpeta `assets/` y las referencia por ruta.
- **Sin API key**: el import no falla (SDK lazy). Solo `GeminiVideoGrounder`
  la exige al ejecutar. Para CI/offline existe `MockVideoGrounder`.

## Requisitos

```bash
pip install google-genai pydantic          # core
```

- `ffmpeg` / `ffprobe` en el `PATH` (o rutas explícitas via CLI).
- Python ≥ 3.9.

## Tests

```bash
pip install pytest
PYTHONPATH=src python -m pytest tests/ -q
```

Suite cubre: parseo/normalización de timestamps, validación Pydantic,
extracción real de frames con ffmpeg (sobre `test_data/`), ambos modos de
Markdown, y el pipeline completo end-to-end vía `MockVideoGrounder`.