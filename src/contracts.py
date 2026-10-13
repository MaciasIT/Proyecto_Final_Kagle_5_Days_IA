"""
doc_squad.contracts — Contratos de datos tipados (Pydantic v2) para Doc Squad v2.

Estos modelos SON el contrato entre las etapas del pipeline y entre el pipeline
y la capa de transporte (frontend, exportadores, QA). Ningún agente recibe ni
devuelve texto crudo: cada etapa emite una instancia de uno de estos modelos.

Uso con google-genai (SDK oficial):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=...)
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[...],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AnalysisReport,   # <- pasa el modelo Pydantic
        ),
    )
    analysis: AnalysisReport = resp.parsed   # SDK lo convierte automáticamente

Regla de oro del RFC-002: no duplicar el esquema en el prompt. El sistema
prompt solo describe la TAREA; la forma la impone response_schema.

Fecha: 2026-10-13
Autor: [arquitectura]
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# --------------------------------------------------------------------------- #
# Enumeraciones
# --------------------------------------------------------------------------- #

class MediaSourceType(str, Enum):
    """Tipo de fuente de entrada aceptada por la etapa de ingesta."""
    LOCAL_FILE = "local_file"     # fichero en disco (video/audio/imagen)
    YOUTUBE_URL = "youtube_url"   # URL de YouTube a resolver
    RECORDING = "recording"       # grabación de pantalla/terminal
    ASCIINEMA = "asciinema"       # cast de asciinema (texto)
    TEXT = "text"                 # log / transcript crudo


class MediaKind(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    TEXT = "text"


class FactKind(str, Enum):
    """Taxonomía de hechos técnicos que extrae el AnalystAgent."""
    COMMAND = "command"
    ERROR = "error"
    CONFIG = "config"
    NETWORK = "network"   # IPs, hosts, puertos, DNS
    STEP = "step"         # paso de procedimiento
    WARNING = "warning"   # acción peligrosa a señalizar


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ValidationStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


class SnippetKind(str, Enum):
    SHELL = "shell"
    PYTHON = "python"
    CONFIG = "config"
    OTHER = "other"


# --------------------------------------------------------------------------- #
# Etapa 1 — Ingesta (multi-fuente)
# --------------------------------------------------------------------------- #

class MediaSource(BaseModel):
    """Descriptor de entrada que recibe la etapa de ingesta."""
    model_config = ConfigDict(extra="forbid")

    source_type: MediaSourceType
    locator: str = Field(..., description="Ruta local, URL, contenido de texto o id de recurso.")
    title: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MediaAsset(BaseModel):
    """Recurso resuelto, subido y/o transcrito tras la ingesta."""
    asset_id: str
    source_type: MediaSourceType
    kind: MediaKind
    uri: Optional[str] = Field(
        default=None,
        description="URI de archivo en Gemini (client.files.upload) si aplica.",
    )
    mime_type: Optional[str] = None
    local_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: Literal["pending", "processing", "active", "failed", "ready"] = "pending"
    uploaded_at: Optional[datetime] = None
    error: Optional[str] = None


class IngestResult(BaseModel):
    """Contrato de salida de la etapa de ingesta."""
    assets: list[MediaAsset] = Field(default_factory=list)
    request_context: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Etapa 2 — Grounding (video -> transcript con timestamps + capturas)
# --------------------------------------------------------------------------- #

class TranscriptSegment(BaseModel):
    """Fragmento de transcripción anclado temporalmente al medio."""
    segment_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str
    speaker: Optional[str] = None
    # Referencia a captura extraída con ffmpeg (opcional)
    frame_path: Optional[str] = None
    frame_timestamp_ms: Optional[int] = None


class GroundedTranscript(BaseModel):
    """Contrato de salida de la etapa de grounding (task IA)."""
    asset_id: str
    language: Optional[str] = None
    segments: list[TranscriptSegment] = Field(default_factory=list)
    full_text: str = ""
    warnings: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Etapa 3 — Análisis (extracción de hechos técnicos)
# --------------------------------------------------------------------------- #

class CodeSnippet(BaseModel):
    """Fragmento de código/comando con su sintaxis validada."""
    kind: SnippetKind = SnippetKind.SHELL
    language: Optional[str] = None
    code: str
    # Vínculo con el segmento de origen para el visor sincronizado frontend
    source_segment_id: Optional[str] = None


class TechnicalFact(BaseModel):
    """Hecho técnico atómico extraído del medio analizado."""
    fact_id: str
    kind: FactKind
    summary: str
    detail: Optional[str] = None
    code: Optional[str] = None
    # Datos típicos de NETWORK
    ip: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    severity: Severity = Severity.INFO
    # Anclaje temporal/no cronológico (para el visor sincronizado)
    source_segment_id: Optional[str] = None
    timestamp_ms: Optional[int] = None


class AnalysisReport(BaseModel):
    """Contrato de salida de la etapa de análisis (AnalystAgent)."""
    asset_id: str
    summary: str
    facts: list[TechnicalFact] = Field(default_factory=list)
    code_snippets: list[CodeSnippet] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    # Vínculo al grounding para trazabilidad
    transcript_ref: Optional[str] = None


# --------------------------------------------------------------------------- #
# Etapa 4 — Validación (Critic + chequeo de sintaxis)
# --------------------------------------------------------------------------- #

class SyntaxIssue(BaseModel):
    """Problema de sintaxis detectado en un fragmento de código.

    kind: missing_cmd | invalid_flag | invalid_syntax | best_practice ...
    """
    fact_id: Optional[str] = None
    snippet_index: Optional[int] = None
    kind: str = "unknown"
    message: str
    suggestion: Optional[str] = None


class FactIssue(BaseModel):
    """Discrepancia o problema detectado por el Critic sobre hechos."""
    fact_id: str
    kind: str
    message: str
    severity: Severity = Severity.MEDIUM
    suggested_correction: Optional[str] = None


class ValidationResult(BaseModel):
    """Veredicto de la etapa de validación sobre un AnalysisReport."""
    status: ValidationStatus
    fact_issues: list[FactIssue] = Field(default_factory=list)
    syntax_issues: list[SyntaxIssue] = Field(default_factory=list)
    verdict_summary: str
    confidence: float = Field(ge=0.0, le=1.0)


# --------------------------------------------------------------------------- #
# Etapa 5 — Redacción (documento estructurado, no markdown crudo)
# --------------------------------------------------------------------------- #

class DocStep(BaseModel):
    """Paso numerado del procedimiento. Referencia opcional al segmento origen."""
    index: int
    title: str
    description: str
    code_snippet: Optional[str] = None
    source_segment_id: Optional[str] = None
    source_timestamp_ms: Optional[int] = None


class TroubleshootingItem(BaseModel):
    problem: str
    cause: Optional[str] = None
    solution: str


class TechnicalDocument(BaseModel):
    """Contrato de salida de la etapa de redacción (TechWriterAgent).

    Es un grafo de documento estructurado (NO markdown plano). Los exportadores
    (Markdown/PDF/Obsidian) lo serializan; el visor frontend lo sincroniza con
    el transcript usando los source_* de cada paso.
    """
    title: str
    executive_summary: str
    prerequisites: list[str] = Field(default_factory=list)
    steps: list[DocStep] = Field(default_factory=list)
    troubleshooting: list[TroubleshootingItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # Enlaces para trazabilidad y sincronización con el medio original
    asset_id: Optional[str] = None
    transcript_ref: Optional[str] = None


# --------------------------------------------------------------------------- #
# Resultado final del pipeline (contrato de transporte hacia frontend/QA)
# --------------------------------------------------------------------------- #

class PipelineResult(BaseModel):
    """Producto final agregado que atraviesa la frontera del pipeline."""
    run_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    ingest: IngestResult
    grounding: Optional[GroundedTranscript] = None
    analysis: Optional[AnalysisReport] = None
    validation: Optional[ValidationResult] = None
    document: Optional[TechnicalDocument] = None
    status: Literal["running", "ok", "failed", "partial"] = "running"
    error: Optional[str] = None