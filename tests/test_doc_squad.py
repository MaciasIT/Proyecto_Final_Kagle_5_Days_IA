"""
Tests unitarios para src.doc_squad (Pipeline agnóstico de agentes).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.doc_squad import (
    _build_feedback,
    _parse_verdict,
    run_documentation_pipeline,
    run_pipeline_async,
)
from src.validator import ValidationReport, ValidationIssue


def test_parse_verdict():
    assert _parse_verdict("VEREDICTO: VÁLIDO") == "VÁLIDO"
    assert _parse_verdict("VEREDICTO: Valido\nTodo bien") == "VÁLIDO"
    assert _parse_verdict("VEREDICTO: REVISAR\n1. Error") == "REVISAR"
    assert _parse_verdict("Hay un problema en el comando") == "REVISAR"
    assert _parse_verdict("Todo parece correcto") == "VÁLIDO"


def test_build_feedback():
    report = ValidationReport(
        ok=False,
        issues=[ValidationIssue(severity="error", kind="bash", message="syntax error", snippet="rm -rf /")],
    )
    fb = _build_feedback(report, "El comando rm es peligroso.")
    assert "ERRORES DE SINTAXIS" in fb
    assert "syntax error" in fb
    assert "OBSERVACIONES DEL CRÍTICO" in fb
    assert "El comando rm es peligroso." in fb


import asyncio

def test_run_pipeline_async_mock(tmp_path):
    test_file = tmp_path / "test_log.txt"
    test_file.write_text("sudo pacman -Syu\nPackage updated successfully.")

    mock_llm = MagicMock()
    # Responses for:
    # 1. AnalystAgent -> Facts
    # 2. ValidatorAgent (Critic) -> Veredicto Válido
    # 3. TechWriterAgent -> Markdown final
    mock_llm.generate_text = AsyncMock(
        side_effect=[
            "- Comando ejecutado: sudo pacman -Syu",
            "VEREDICTO: VÁLIDO\nLos comandos son coherentes con Arch Linux.",
            "# Guía de Actualización Pacman\n\n## Procedimiento\n1. Ejecutar pacman",
        ]
    )

    statuses = []
    def callback(msg):
        statuses.append(msg)

    doc = asyncio.run(
        run_pipeline_async(
            file_path=str(test_file),
            request_context="Actualizar Arch",
            status_callback=callback,
            llm_client=mock_llm,
        )
    )

    assert "# Guía de Actualización Pacman" in doc
    assert any("IngestAgent" in s for s in statuses)
    assert any("AnalystAgent" in s for s in statuses)
    assert any("ValidatorAgent" in s for s in statuses)
    assert any("TechWriterAgent" in s for s in statuses)


def test_run_documentation_pipeline_sync_wrapper(tmp_path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("echo 'hello world'")

    mock_llm = MagicMock()
    mock_llm.generate_text = AsyncMock(
        side_effect=[
            "- Hecho: echo hello world",
            "VEREDICTO: VÁLIDO",
            "# Documento Generado",
        ]
    )

    result = run_documentation_pipeline(
        file_path=str(test_file),
        llm_client=mock_llm,
    )
    assert result == "# Documento Generado"
