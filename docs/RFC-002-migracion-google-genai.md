# RFC-002 — Migración a Google GenAI SDK (Gemini 2.0) y contratos Pydantic

- Estado: Aprobación pendiente (arquitectura)
- Fecha: 2026-10-13
- Autor: [arquitectura]
- Ámbito: Doc Squad v2 — fase F1

## 1. Contexto y problema

El pipeline v1 (`src/doc_squad.py`) se apoya en dos librerías que deben
desaparecer:

| Dependencia | Rol actual | Problema |
|---|---|---|
| `google-generativeai` | SDK legacy (Gemini 1.5) | Deprecado. API `genai.configure/upload_file` sin salida tipada. Modelos `*-1.5-*` en retirada. |
| `google-adk` | Orquestación de agentes (`Agent`, `InMemoryRunner`) | Experimental, API inestable. Añade un framework completo para un pipeline que es, en realidad, 3-6 pasos secuenciales. |

Problemas de fondo que la migración debe corregir, no solo trasladar:

1. **Relés sin tipos.** Cada agente pasa `response.text` (string libre) al
   siguiente. El acoplamiento es textual: el Analyst decide si "entiende" el
   URI, el writer parsea prosa, y cualquier cambio de formato rompe la cadena
   silenciosamente.
2. **Contratos implícitos.** No hay un modelo de datos acordado entre etapas.
   `verify_pipeline.py` reconoce explícitamente el fallo: "we don't easily
   extract the URI... we cheat slightly".
3. **Modelos obsoletos.** `gemini-1.5-flash-001` / `gemini-1.5-pro-001`
   (hardcoded en el código) debe pasar a Gemini 2.0.
4. **Carga de archivos bloqueante.** `while PROCESSING: sleep; get_file` es un
   anti-patrón sin timeout, sin reintento, sin estado.

## 2. Decisión

### 2.1 Sustituir ambas librerías por `google-genai` (SDK oficial)

```python
from google import genai
from google.genai import types
```

- Un único SDK mantenido por Google, con objetos de retorno tipados (`pydantic`
  en `google.genai.types`).
- Soporta **structured output nativo**: `response_schema` + `response_mime_type`
  para que el modelo devuelva JSON validado contra un esquema Pydantic, y el SDK
  lo convierta a instancia vía `response.parsed`.
- Carga de archivos a través de `client.files.upload(...)` y su estado
  tipificado `FileState`.

La orquestación de agentes deja de ser un framework (ADK) y pasa a ser una
**función pura de orquestación** (pipeline secuencial con contratos tipados en
las fronteras). Para un equipo pequeño y un flujo lineal, ADK es deuda: no hay
agentes autónomos, hay etapas deterministas.

### 2.2 Modelos — Gemini 2.0, con registro configurable

Regla: **nunca hardcodear el modelo**. Se introduce un registro de modelos
(véase §6) porque `gemini-2.0-pro` sigue siendo experimental y el equipo debe
poder subir a 2.5 sin tocar código.

| Etapa | Modelo propuesto | Justificación |
|---|---|---|
| Ingest (metadatos/orquestación) | `gemini-2.0-flash` | Barato, rápido, no requiere razonamiento |
| Grounding (transcripción) | API de video/audio nativa | No consume LLM salvo resumen |
| Analyst (extracción de hechos) | `gemini-2.0-pro` | Máxima precisión en extracción |
| Validator — sintaxis | `gemini-2.0-flash` | Chequeo mecánico |
| Validator — critic | `gemini-2.0-pro` | Razonamiento sobre hechos |
| TechWriter (redacción) | `gemini-2.0-pro` | Calidad de expresión |

> Nota: `gemini-2.0-pro` responde al id `gemini-2.0-pro-exp-02-05`
> (experimental). Si no está disponible en la cuenta, el registro cae a
> `gemini-2.0-flash` y lo registra como warning, sin romper el pipeline.

### 2.3 Contratos de datos: Pydantic v2 en las fronteras

Cada etapa emite un modelo Pydantic (ver `contracts.py`), obtenido vía
`response_schema`, y la siguiente etapa lo **consume tipado**. Desaparece el
relé textual.

```
MediaSource ─▶ IngestResult ─▶ GroundedTranscript ─▶ AnalysisReport
                                                          │
                    ValidationResult ◀───────────────────┘
                          │
                          ▼
                    TechnicalDocument ─▶ PipelineResult (frontera frontend/QA/export)
```

Regla de oro: **el prompt describe la tarea, no el formato.** El esquema va
solo en `response_schema`; duplicarlo en el prompt degrada la calidad (mejores
prácticas documentadas del SDK).

## 3. Modelo de datos

Modelos completos en `contracts.py`. Resumen de entidades:

- `MediaSource` / `MediaAsset` / `IngestResult` — ingesta multi-fuente (fichero
  local, YouTube, grabación, asciinema, texto). `MediaAsset.status` es una
  máquina de estados explícita que elimina el bucle `while PROCESSING`.
- `GroundedTranscript` / `TranscriptSegment` — grounding de vídeo con
  `start_ms`/`end_ms` y `frame_path` (capturas ffmpeg). Es el vínculo para el
  visor sincronizado.
- `AnalysisReport` / `TechnicalFact` / `CodeSnippet` — hechos técnicos con
  taxonomía (`FactKind`), severidad y anclaje temporal (`source_segment_id`,
  `timestamp_ms`).
- `ValidationResult` / `FactIssue` / `SyntaxIssue` — salida del Validator
  (Critic + sintaxis). Separamos explícitamente los problemas de *hechos* de
  los de *sintaxis*.
- `TechnicalDocument` / `DocStep` / `TroubleshootingItem` — documento
  estructurado (NO markdown), con `source_*` en cada paso para sincronizar con
  el medio.
- `PipelineResult` — agregado final que cruza la frontera hacia frontend,
  exportadores y QA; es el objeto que se serializa/persiste.

Relaciones y reglas:

- `TechnicalFact.code` admite código; los `CodeSnippet` son los bloques que el
  Validator chequea sintácticamente. Un `SyntaxIssue.snippet_index` apunta al
  índice en `AnalysisReport.code_snippets`.
- Trazabilidad: `fact.fact_id` es la clave de unión cuestiones de validación y
  correcciones. Un `FactIssue.fact_id` inválido → el pipeline marca `partial`.
- Anonimización: los datos de red (`ip`, `host`, `port`) son opcionales y deben
  sanitizarse antes de exportar (responsabilidad del exportador `scribe`; el
  contrato los expone, no los censura). Véase §8.

## 4. APIs y contratos

Sin API HTTP propia en el MVP: el pipeline es una biblioteca síncrona/async con
contratos en las fronteras. La "API" son:

1. **Contratos Pydantic** (`contracts.py`) — interfaz entre etapas.
2. **Fachada `run_documentation_pipeline`** — misma firma que v1 (source,
   context, status_callback) para no romper a `app.py`, pero devolviendo un
   `PipelineResult` en lugar de una string.
3. **Esquemas serializados** — `TechnicalDocument` y `PipelineResult` se
   serializan a JSON (vía `model_dump_json()`) para el frontend y QA.

Errores esperados (estado `MediaAsset.status`) y su propagación:

- `failed` en ingesta → el pipeline aborta con `PipelineResult.status="failed"`
  y `error` poblado (no un relé de string "ERROR: ...").
- `partial` cuando una etapa emite warnings o el Validator marca `WARN`.

## 5. Arquitectura de ejecución

Patrón: **pipeline secuencial tipado** (no multi-agente autónomo). Una función
orquestadora encadena etapas puras. Cada etapa es una función `(input_contract)
-> output_contract` que oculta la llamada a Gemini.

```
src/
  contracts.py          # modelos Pydantic (fuente de verdad compartida)
  models_registry.py    # mapeo stage -> model id + fallbacks
  ingest.py             # IngestSource -> IngestResult
  grounding.py          # IngestResult -> GroundedTranscript  (task IA)
  analyst.py            # GroundedTranscript -> AnalysisReport
  validator.py          # AnalysisReport -> ValidationResult  (task dev)
  writer.py             # (Analysis,Validation) -> TechnicalDocument
  pipeline.py           # orquestador + PipelineResult
  export/               # TechnicalDocument -> markdown/pdf/obsidian (task scribe)
```

Justificación: para 5-6 etapas deterministas con dependencias lineales, un
orquestador de funciones gana en testabilidad (cada etapa es unit-testable con
fixtures JSON) y en observabilidad frente a un framework de agentes.

Contraindicación: si en el futuro se necesitan agentes con memoria,
herramientas dinámicas o negociación entre pares, entonces sí reintroducir un
framework (ADK estable / ag2), **manteniendo estos contratos Pydantic** como
borde.

## 6. Configuración y secretos

- `GOOGLE_API_KEY` desde `python-dotenv` (sin cambios), inyectada como
  `genai.Client(api_key=...)`.
- `models_registry.py` centraliza los ids de modelo (nunca literales en las
  etapas):
  ```python
  MODEL_2_0 = {
      "flash": "gemini-2.0-flash",
      "pro": "gemini-2.0-pro-exp-02-05",
  }
  STAGE_DEFAULT = {
      "ingest": MODEL_2_0["flash"],
      "grounding": MODEL_2_0["flash"],
      "analyst": MODEL_2_0["pro"],
      ...
  }
  ```
- `requirements.txt` nuevo:
  ```
  google-genai>=1.0
  pydantic>=2.0
  python-dotenv
  streamlit
  # por etapa: yt-dlp (youtube), asciinema, ffmpeg (grounding), reportlab/pdf (export)
  ```
  Se eliminan `google-adk` y `google-generativeai`.

## 7. Plan de implementación (fases)

1. **Fase A — núcleo tipado (bloqueante):** `contracts.py` + `models_registry.py`
   + rewiring de las 3 etapas v1 (ingest/analyst/writer) al SDK `google-genai`
   con `response_schema`. `app.py` pasa a consumir `PipelineResult`.
   Verificación: `verify_pipeline.py` reescrito para assertar tipos, no
   strings.
2. **Fase B — Validator:** integrar `validator.py` (Critic + sintaxis) en la
   cadena. Bucle de corrección: si `ValidationResult.status == FAIL`, el writer
   regenera con las correcciones (máx. N iteraciones, para evitar bucles).
3. **Fase C — Grounding y multi-fuente:** `grounding.py` (vídeo→transcript con
   timestamps + ffmpeg) y `ingest.py` multi-fuente (YouTube/asciinema/grabación).
   Aquí entra la tarea IA y la extensión de ingesta.
4. **Fase D — Export y frontend:** exportadores multiformato consumiendo
   `TechnicalDocument`; frontend consumiendo `PipelineResult` + `GroundedTranscript`
   para el visor sincronizado.
5. **Fase E — QA/benchmark:** suite sobre `test_data` que valida hechos contra
   ground truth y mide `confidence`.

Orden intencional: los contratos primero (Fase A) desbloquean en paralelo a
dev (validator), ia (grounding), scribe (export) y caos (QA), que solo dependen
de `contracts.py`, no del pipeline completo.

## 8. Seguridad y cumplimiento

- Secretos solo vía `GOOGLE_API_KEY` + dotenv; nada en código ni en pipelines.
- Datos de red (IP/host/port) expuestos por el contrato pero **sanitizados en
  la capa de export** (scribe) antes de Markdown/PDF/Obsidian. El contrato
  documenta esta frontera.
- Uploads de archivos: `MediaAsset.local_path` no debe circular fuera del
  proceso; los exportadores usan referencias, no rutas crudas del disco del
  usuario.

## 9. Riesgos y mitigaciones

| Riesgo | Severidad | Mitigación |
|---|---|---|
| `gemini-2.0-pro` experimental inestable | Alta | `models_registry` con fallback a `gemini-2.0-flash` + warning; sin hardcode |
| `response.parsed` falla si el modelo desvía el esquema | Media | Validar en cada etapa con `model_validate`; en fallo, retry 1 vez y luego `partial` |
| Coste: `pro` en analyst+writer duplica precio vs flash | Media | Registro permite degradar a flash por entorno/flag |
| Pérdida de `run_debug`/eventos de ADK | Baja | Observabilidad se reconstruye con logs por etapa + `PipelineResult.status` |
| Regresión en `app.py` (Streamlit) | Media | Mantener firma de la fachada; adaptar solo el consumidor de retorno |

## 10. Decisiones pospuestas (necesitan input)

- Elegir `gemini-2.0-pro` vs `gemini-2.5-*` definitivo: depende de disponibilidad
  de cuota en la cuenta de Michel. El registro lo deja abierto.
- Persistencia: hoy el pipeline es efímero (en memoria). Si se quiere historial
  reutilizable por el frontend, decidir almacén (SQLite local vs Firestore) —
  queda fuera del alcance F1.

## 11. Handoff

Bloqueante para Dev/IA:
- `contracts.py` (este workspace) es la fuente de verdad — no derivar esquemas
  propios.
- Patrón de llamada con structured output documentado en la cabecera de
  `contracts.py`.

Pendiente de recepción:
- Confirmación de disponibilidad de `gemini-2.0-pro` en la cuenta (para fijar
  el fallback definitivo).

## Hallazgos clave (output-contract)

- **Severidad:** alta
- **Evidencia:** `src/doc_squad.py` usa `google.generativeai` + `google.adk`,
  modelos `gemini-1.5-*` hardcodeados, y relés de texto (`response.text`).
  `verify_pipeline.py:96` reconoce no poder extraer el URI entre etapas.
- **Confianza:** alta — ficheros revisados en `Proyecto_Final_Kagle_5_Days_IA`.
- **Acción recomendada:** aprobar RFC y arrancar Fase A (contratos + núcleo
  tipado) para desbloquear a dev/ia/scribe/caos.

## Qué no he podido comprobar

- Disponibilidad real de `gemini-2.0-pro` en la API key de Michel (requiere
  credencial viva).
- Versionado exacto de `google-genai` instalado en el entorno local (solo leído
  `requirements.txt`, no el venv del proyecto).

## Siguiente paso

Fijar el id definitivo del modelo "pro" (o confirmar fallback a flash) y que
Dev implemente la Fase A contra `contracts.py`.