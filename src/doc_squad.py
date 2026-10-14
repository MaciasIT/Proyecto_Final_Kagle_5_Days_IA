"""
src.doc_squad — Pipeline de documentación técnica con agentes de IA.

Doc Squad v2 (Agnóstico):
  1. IngestAgent: Ingesta multimedia local (audio/vídeo con faster-whisper, asciinema, logs).
  2. AnalystAgent: Extracción de hechos técnicos precisos mediante AgnosticLLMClient.
  3. ValidatorAgent: Critic de coherencia + validador determinista de sintaxis de comandos.
  4. TechWriterAgent: Generación de la documentación técnica final en Markdown.

Eliminadas todas las dependencias propietarias de Google (google-adk, google-generativeai).
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Callable, Optional

from dotenv import load_dotenv

from src.audio.transcriber import LocalTranscriber
from src.llm.client import AgnosticLLMClient
from src.validator import validate_facts

load_dotenv()

MAX_REFINEMENTS = 3


# --- PROMPTS DE AGENTES ---

ANALYST_INSTRUCTION = """\
Eres el AnalystAgent, un Ingeniero de Sistemas Senior.
Tu trabajo es analizar el contenido técnico recibido (transcripción de audio/vídeo, comandos, logs o texto) y extraer TODOS los detalles técnicos reales.
NO te preocupes por el formato final bonito ni la redacción literaria. Céntrate en la máxima precisión técnica.

Debes extraer:
- Comandos exactos ejecutados y sus parámetros.
- Mensajes de error, advertencias o logs visibles.
- Pasos de configuración realizados (ficheros editados, directivas).
- Direcciones IP, nombres de host, puertos, paquetes y versiones.

Salida esperada: Una lista cronológica y detallada de hechos técnicos crudos.
"""

VALIDATOR_INSTRUCTION = """\
Eres el ValidatorAgent, un revisor técnico senior (Critic).
Tu trabajo es revisar los hechos técnicos extraídos por el AnalystAgent y detectar problemas ANTES de redactar el documento final.
No redactas la guía, solo juzgas si los hechos son técnicamente consistentes y correctos.

Revisa:
- Inconsistencias técnicas o comandos contradictorios.
- Comandos que no corresponden a la distribución o sistema descrito.
- Comandos peligrosos que requieran advertencias.

Formato de respuesta OBLIGATORIO:
Si todo es correcto:
VEREDICTO: VÁLIDO

Si hay problemas o inconsistencias:
VEREDICTO: REVISAR
1. <problema concreto y cómo corregirlo>
2. <siguiente problema>
"""

TECH_WRITER_INSTRUCTION = """\
Eres el TechWriterAgent. Recibes una lista de hechos técnicos validados.
Tu trabajo es convertir esos hechos en un documento técnico profesional en Markdown.

Estructura requerida:
# [Título Descriptivo y Claro]

## Resumen Ejecutivo
(1 párrafo conciso explicando el objetivo y resultado del procedimiento)

## Prerrequisitos
- Requisitos de software, permisos (sudo/root), dependencias o paquetes necesarios.

## Procedimiento Paso a Paso
1. **Paso 1**: Explicación clara.
   ```bash
   comando exacto
   ```
2. **Paso 2**: Siguiente paso.

## Solución de Problemas y Consideraciones
- Errores comunes observados o advertencias (WARNING) de seguridad si aplica.

Usa bloques de código con resaltado sintáctico. Tono formal, claro y directo.
"""


# --- HELPERS DE VALIDACIÓN Y REFINAMIENTO ---

def _parse_verdict(critic_text: str) -> str:
    """Extrae el veredicto del critic ('VÁLIDO' o 'REVISAR') de su respuesta."""
    match = re.search(r"VEREDICTO\s*:\s*(\S+)", critic_text, re.IGNORECASE)
    if match:
        token = match.group(1).upper()
        return "VÁLIDO" if token in {"VÁLIDO", "VALIDO", "OK", "APROBADO"} else "REVISAR"
    upper = critic_text.upper()
    if "REVISAR" in upper or "PROBLEMA" in upper or "ERROR" in upper:
        return "REVISAR"
    return "VÁLIDO"


def _build_feedback(syntax_report, critic_text: str) -> str:
    """Compone el feedback de refinamiento (sintaxis + critic)."""
    parts = []
    if not syntax_report.ok:
        parts.append(
            "ERRORES DE SINTAXIS DETECTADOS (corrígelos obligatoriamente):\n"
            + "\n".join(f"- {issue}" for issue in syntax_report.issues)
        )
    parts.append("OBSERVACIONES DEL CRÍTICO:\n" + critic_text.strip())
    return "\n\n".join(parts)


def _extract_media_text(file_path: str, transcriber: LocalTranscriber) -> str:
    """Extrae texto del archivo según su tipo (audio/vídeo vía faster-whisper o texto plano)."""
    if not os.path.exists(file_path):
        return f"[Archivo no encontrado: {file_path}]"

    ext = os.path.splitext(file_path)[1].lower()
    video_exts = {".mp4", ".webm", ".mkv", ".mov", ".avi"}
    audio_exts = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus"}
    text_exts = {".txt", ".log", ".md", ".cast", ".json"}

    if ext in video_exts:
        try:
            segments = transcriber.transcribe_video(file_path)
            lines = [f"[{s['start_ms']//1000}s] {s['text']}" for s in segments if s.get("text")]
            return "\n".join(lines) if lines else f"[Vídeo sin pista de audio legible: {os.path.basename(file_path)}]"
        except Exception as e:
            return f"[Error al transcribir vídeo: {e}]"

    elif ext in audio_exts:
        try:
            segments = transcriber.transcribe(file_path)
            lines = [f"[{s['start_ms']//1000}s] {s['text']}" for s in segments if s.get("text")]
            return "\n".join(lines) if lines else f"[Audio vacío o no legible: {os.path.basename(file_path)}]"
        except Exception as e:
            return f"[Error al transcribir audio: {e}]"

    elif ext in text_exts:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            return f"[Error al leer fichero de texto: {e}]"

    return f"[Archivo multimedia procesado: {os.path.basename(file_path)}]"


# --- PIPELINE ASÍNCRONO ---

async def run_pipeline_async(
    file_path: str,
    request_context: str = "",
    status_callback: Optional[Callable[[str], None]] = None,
    llm_client: Optional[AgnosticLLMClient] = None,
    transcriber: Optional[LocalTranscriber] = None,
) -> str:
    """Ejecuta el pipeline Doc Squad v2 de forma asíncrona y agnóstica."""
    client = llm_client or AgnosticLLMClient()
    local_transcriber = transcriber or LocalTranscriber()

    def update_status(msg: str):
        if status_callback:
            status_callback(msg)
        else:
            print(msg)

    filename = os.path.basename(file_path)
    update_status(f"🚀 Iniciando pipeline Doc Squad para: {filename}")

    # PASO 1: INGESTA MULTIMEDIA
    update_status("🤖 IngestAgent: Procesando contenido...")
    raw_content = _extract_media_text(file_path, local_transcriber)
    update_status("✅ IngestAgent: Contenido extraído.")

    # PASO 2: ANÁLISIS TÉCNICO
    update_status("🤖 AnalystAgent: Extrayendo hechos técnicos...")
    analysis_prompt = (
        f"Contenido del archivo '{filename}':\n\n{raw_content}\n\n"
        f"Contexto adicional proporcionado por el usuario:\n{request_context or 'Ninguno'}\n\n"
        "Extrae todos los hechos técnicos de manera cronológica y precisa."
    )
    facts_text = await client.generate_text(
        prompt=analysis_prompt,
        system_prompt=ANALYST_INSTRUCTION,
        temperature=0.2,
    )
    update_status("✅ AnalystAgent: Hechos extraídos.")

    # PASO 3: VALIDACIÓN Y BUCLE DE REFINAMIENTO (ValidatorAgent <-> AnalystAgent)
    final_facts = facts_text
    for iteration in range(MAX_REFINEMENTS + 1):
        update_status(f"🤖 ValidatorAgent: Validando hechos (iteración {iteration + 1}/{MAX_REFINEMENTS + 1})...")

        # 3a. Chequeo sintáctico determinista
        syntax_report = validate_facts(final_facts)

        # 3b. Critic LLM
        critic_prompt = (
            "Revisa los siguientes hechos técnicos extraídos y evalúa su coherencia técnica:\n\n"
            f"INFORME DE SINTAXIS (determinista):\n{syntax_report.to_text()}\n\n"
            f"HECHOS TÉCNICOS:\n{final_facts}\n"
        )
        critic_text = await client.generate_text(
            prompt=critic_prompt,
            system_prompt=VALIDATOR_INSTRUCTION,
            temperature=0.1,
        )
        verdict = _parse_verdict(critic_text)

        if syntax_report.ok and verdict == "VÁLIDO":
            update_status("✅ ValidatorAgent: Hechos validados, sin inconsistencias.")
            break

        update_status(
            f"🔁 ValidatorAgent: {len(syntax_report.errors)} error(es) de sintaxis o inconsistencias detectadas; refinando..."
        )

        if iteration >= MAX_REFINEMENTS:
            update_status("⚠️ ValidatorAgent: Máximo de iteraciones alcanzado; continuando con el mejor resultado.")
            break

        feedback = _build_feedback(syntax_report, critic_text)
        refine_prompt = (
            "Tu análisis previo contiene problemas o inconsistencias técnicas que debes corregir.\n\n"
            f"{feedback}\n\n"
            "Devuelve una versión CORREGIDA, COMPLETA y PRECISA de los hechos técnicos."
        )
        final_facts = await client.generate_text(
            prompt=refine_prompt,
            system_prompt=ANALYST_INSTRUCTION,
            temperature=0.2,
        )
        update_status("✅ AnalystAgent: Hechos corregidos.")

    # PASO 4: REDACCIÓN DE DOCUMENTACIÓN
    update_status("🤖 TechWriterAgent: Redactando documentación final...")
    writer_prompt = (
        f"Archivo de origen: {filename}\n"
        f"Contexto del usuario: {request_context or 'Ninguno'}\n\n"
        f"Hechos técnicos validados:\n{final_facts}\n\n"
        "Redacta el documento técnico final completo en Markdown siguiendo la estructura requerida."
    )
    final_doc = await client.generate_text(
        prompt=writer_prompt,
        system_prompt=TECH_WRITER_INSTRUCTION,
        temperature=0.3,
    )
    update_status("✅ TechWriterAgent: Documentación final generada.")

    return final_doc


# --- WRAPPER SÍNCRONO PARA STREAMLIT / SCRIPTS ---

def run_documentation_pipeline(
    file_path: str,
    request_context: str = "",
    status_callback: Optional[Callable[[str], None]] = None,
    llm_client: Optional[AgnosticLLMClient] = None,
    transcriber: Optional[LocalTranscriber] = None,
) -> str:
    """Wrapper síncrono para ejecutar el pipeline asíncrono."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # Si ya hay un event loop corriendo (ej. en ciertas versiones de Streamlit o Jupyter)
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(
            run_pipeline_async(file_path, request_context, status_callback, llm_client, transcriber)
        )
    else:
        return loop.run_until_complete(
            run_pipeline_async(file_path, request_context, status_callback, llm_client, transcriber)
        )
