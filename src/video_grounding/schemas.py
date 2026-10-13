"""Contratos de datos (Pydantic) para Video Grounding.

Estos modelos son el contrato compartido entre agentes:

  * ``GroundingOutput``  -> lo que Gemini 2.0 devuelve (salida estructurada JSON).
  * ``VideoGroundingResult`` -> resultado enriquecido con las capturas generadas.
  * ``GroundedAction``   -> unidad atomica: una accion anclada a una marca [MM:SS].
  * ``FrameCapture``     -> una captura de fotograma asociada a una accion.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

# --------------------------------------------------------------------------
# Utilidades de timestamp
# --------------------------------------------------------------------------

_MMSS_RE = re.compile(r"^(?:(?P<h>\d{1,2}):)?(?P<m>\d{1,2}):(?P<s>\d{1,2}(?:\.\d+)?)$")


def parse_timestamp(value: str) -> float:
    """Convierte una marca ``MM:SS`` (o ``HH:MM:SS``) a segundos.

    Ejemplos: ``"00:12"`` -> 12.0, ``"1:23"`` -> 83.0, ``"01:02:03"`` -> 3723.0.
    """
    value = (value or "").strip()
    m = _MMSS_RE.match(value)
    if not m:
        raise ValueError(f"Marca de tiempo invalida: {value!r} (esperado MM:SS)")
    h = int(m.group("h") or 0)
    minutes = int(m.group("m"))
    seconds = float(m.group("s"))
    return h * 3600 + minutes * 60 + seconds


def format_timestamp(seconds: float) -> str:
    """Formatea segundos a ``MM:SS``. E.g. 83.0 -> ``"01:23"``."""
    seconds = max(0, int(round(seconds)))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


class ActionType(str, Enum):
    """Tipologia de accion detectada en el video."""

    COMMAND = "command"
    CONFIGURATION = "configuration"
    ERROR = "error"
    OBSERVATION = "observation"
    UNKNOWN = "unknown"


class GroundedAction(BaseModel):
    """Una accion tecnica anclada a una marca de tiempo del video."""

    index: int = Field(description="Posicion 1-based en la secuencia cronologica")
    timestamp: str = Field(description="Tiempo de inicio en formato [MM:SS]")
    timestamp_seconds: float = Field(description="Tiempo de inicio en segundos")
    end_timestamp: Optional[str] = Field(
        default=None, description="Tiempo de fin en formato [MM:SS] o null"
    )
    action_type: ActionType = Field(
        default=ActionType.UNKNOWN, description="Tipo de accion detectada"
    )
    title: str = Field(description="Titulo corto de la accion")
    description: str = Field(
        description="Descripcion tecnica de lo que ocurre en pantalla"
    )
    command: Optional[str] = Field(
        default=None, description="Comando exacto ejecutado, si aplica"
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data):
        """Normaliza la marca antes de la validacion estricta.

        - Si Gemini solo devolvio ``timestamp`` (MM:SS), deriva ``timestamp_seconds``.
        - Si ``timestamp`` llega como numero, lo convierte a MM:SS canonico.
        """
        if isinstance(data, dict):
            data = dict(data)
            ts = data.get("timestamp")
            if isinstance(ts, (int, float)):
                data["timestamp"] = format_timestamp(float(ts))
            if data.get("timestamp_seconds") is None and data.get("timestamp") is not None:
                data["timestamp_seconds"] = parse_timestamp(data["timestamp"])
        return data


class GroundingOutput(BaseModel):
    """Salida estructurada que se solicita a Gemini 2.0 (response_schema)."""

    title: str = Field(description="Titulo descriptivo del documento")
    summary: str = Field(description="Resumen ejecutivo de una frase")
    actions: List[GroundedAction] = Field(
        description="Lista cronologica de acciones con sus marcas de tiempo [MM:SS]"
    )


class FrameCapture(BaseModel):
    """Una captura de fotograma extraida para una accion."""

    action_index: int = Field(description="Indice de la accion asociada")
    timestamp_seconds: float = Field(description="Marca (segundos) del fotograma")
    image_path: str = Field(description="Ruta absoluta del JPG extraido")
    width: int = Field(default=0, description="Ancho en px del fotograma extraido")
    height: int = Field(default=0, description="Alto en px del fotograma extraido")


class VideoGroundingResult(BaseModel):
    """Resultado final del pipeline de video grounding."""

    video_path: str = Field(description="Ruta del video analizado")
    duration_seconds: float = Field(description="Duracion del video en segundos")
    model: str = Field(description="Modelo Gemini utilizado")
    title: str = Field(description="Titulo del documento")
    summary: str = Field(description="Resumen ejecutivo")
    actions: List[GroundedAction] = Field(
        default_factory=list, description="Acciones ancladas en el tiempo"
    )
    frames: List[FrameCapture] = Field(
        default_factory=list, description="Capturas extraidas por accion"
    )