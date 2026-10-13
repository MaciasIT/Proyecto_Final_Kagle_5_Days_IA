"""Validador técnico del Doc Squad (ValidatorAgent / Critic).

Módulo autocontenido e independiente del SDK de agentes. Aporta:

1. Verificación determinista de sintaxis de comandos (bash/sh, python, docker).
2. Extracción de bloques de código desde texto libre (hechos del AnalystAgent).
3. Un ``ValidationReport`` estructurado que alimenta el bucle de refinamiento.

Diseñado para funcionar con stdlib únicamente (no depende de pydantic ni del
SDK de Gemini), de modo que la migración de SDK (tarea de arquitectura) no
afecta a esta capa de validación.
"""

from __future__ import annotations

import ast
import re
import shlex
import subprocess
import tempfile
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# --- Modelos de datos ---

# Lenguajes / sabores que sabe validar el checker.
BASH_LANGS = {"bash", "sh", "shell", "console", "zsh", "terminal"}
PYTHON_LANGS = {"python", "py", "python3"}
DOCKER_LANGS = {"docker", "dockerfile", "docker-compose", "compose"}

# Directivas válidas de un Dockerfile (subset práctico).
_DOCKERFILE_DIRECTIVES = {
    "FROM", "RUN", "CMD", "LABEL", "MAINTAINER", "EXPOSE", "ENV", "ADD",
    "COPY", "ENTRYPOINT", "VOLUME", "USER", "WORKDIR", "ARG", "ONBUILD",
    "STOPSIGNAL", "HEALTHCHECK", "SHELL",
}

# Subcomandos conocidos de la CLI de docker (para detección de typos groseros).
_DOCKER_CLI_SUBCOMMANDS = {
    "run", "exec", "build", "pull", "push", "images", "ps", "logs", "rm",
    "rmi", "stop", "start", "restart", "inspect", "network", "volume",
    "compose", "tag", "login", "logout", "search", "cp", "stats", "top",
    "commit", "export", "import", "save", "load", "info", "version", "kill",
    "pause", "unpause", "create", "attach", "events", "system", "context",
}


@dataclass
class ValidationIssue:
    """Un problema concreto detectado durante la validación."""

    severity: str  # "error" | "warning"
    kind: str  # "bash" | "python" | "docker" | "general"
    message: str
    snippet: str = ""

    def __str__(self) -> str:
        prefix = f"[{self.kind.upper()}][{self.severity.upper()}]"
        tail = f" :: {self.snippet.strip()[:80]}" if self.snippet.strip() else ""
        return f"{prefix} {self.message}{tail}"


@dataclass
class ValidationReport:
    """Resultado de la validación de un texto con hechos técnicos."""

    ok: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    blocks_checked: int = 0

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def to_text(self) -> str:
        if self.ok:
            return (
                f"VALIDACIÓN OK — {self.blocks_checked} bloque(s) de código revisados, "
                "sin errores de sintaxis."
            )
        lines = [
            f"VALIDACIÓN CON PROBLEMAS — {len(self.errors)} error(es), "
            f"{len(self.warnings)} aviso(s) sobre {self.blocks_checked} bloque(s)."
        ]
        for issue in self.issues:
            lines.append(f"- {issue}")
        return "\n".join(lines)


# --- Extracción de bloques de código ---

_FENCE_RE = re.compile(
    r"```(?P<lang>[A-Za-z0-9_+.-]*)[ \t]*\n(?P<body>.*?)```",
    re.DOTALL,
)
_INLINE_RE = re.compile(r"`([^`\n]+)`")


def _classify_lang(lang: str, body: str) -> str:
    """Determina el sabor (bash|python|docker) a partir del hint y del contenido."""
    lang = (lang or "").lower().strip()
    if lang in BASH_LANGS:
        return "bash"
    if lang in PYTHON_LANGS:
        return "python"
    if lang in DOCKER_LANGS or lang in {"yaml", "yml"}:
        return "docker"
    if lang in {"text", "txt", "plaintext", "markdown", "md"}:
        return "unknown"

    # Heurística sobre el contenido cuando no hay hint claro.
    stripped = body.lstrip()
    if re.match(r"^docker(\s|\s+compose\b)", stripped):
        return "docker"
    if re.match(r"^\s*(FROM|services:)\b", stripped, re.MULTILINE):
        return "docker"
    if re.search(r"\b(import|from)\s+\w+", body) or re.search(r"\bdef\s+\w+\s*\(", body):
        return "python"
    return "bash"


def extract_code_blocks(text: str) -> List[Tuple[str, str]]:
    """Devuelve una lista de tuplas ``(lang, body)`` de bloques de código.

    Extrae tanto bloques cercados (``` ... ```) como comandos inline
    (`` `comando` ``). Los bloques sin hint de lenguaje se clasifican por
    heurística sobre su contenido.
    """
    blocks: List[Tuple[str, str]] = []

    for match in _FENCE_RE.finditer(text):
        body = match.group("body").strip("\n")
        if body.strip():
            blocks.append((match.group("lang"), body))

    # Comandos inline: se tratan como bash salvo evidencia clara de lo contrario.
    for match in _INLINE_RE.finditer(text):
        cmd = match.group(1).strip()
        # Evita duplicar contenido que ya era un bloque cercado (heurística simple).
        if cmd and not any(cmd in body for _, body in blocks):
            blocks.append(("", cmd))

    return blocks


# --- Verificadores de sintaxis ---

def _run_check(args: List[str], stdin_text: Optional[str] = None) -> Tuple[bool, str]:
    """Ejecuta un validador externo y devuelve (ok, stderr)."""
    try:
        proc = subprocess.run(
            args,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0, (proc.stderr or "").strip()
    except FileNotFoundError:
        return False, "validador no disponible en el sistema"
    except subprocess.TimeoutExpired:
        return False, "timeout durante la validación"
    except Exception as exc:  # pragma: no cover - defensivo
        return False, f"error interno: {exc}"


def check_bash_syntax(script: str) -> List[ValidationIssue]:
    """Valida un script/orden de shell con ``bash -n``."""
    issues: List[ValidationIssue] = []
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
        fh.write(script)
        tmp_path = fh.name
    try:
        ok, err = _run_check(["bash", "-n", tmp_path])
        if not ok:
            issues.append(
                ValidationIssue("error", "bash", f"sintaxis de shell inválida: {err}", script)
            )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return issues


def check_python_syntax(code: str) -> List[ValidationIssue]:
    """Valida código Python con ``ast.parse`` + ``compile``."""
    issues: List[ValidationIssue] = []
    try:
        tree = ast.parse(code)
        compile(tree, "<validator>", "exec")
    except SyntaxError as exc:
        issues.append(
            ValidationIssue(
                "error",
                "python",
                f"sintaxis Python inválida (línea {exc.lineno}): {exc.msg}",
                code,
            )
        )
    return issues


def _check_dockerfile(body: str) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    has_from = False
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        directive = line.split()[0].upper()
        if directive not in _DOCKERFILE_DIRECTIVES:
            issues.append(
                ValidationIssue(
                    "warning",
                    "docker",
                    f"directiva desconocida: {directive}",
                    raw_line,
                )
            )
        if directive == "FROM":
            has_from = True
    if not has_from:
        issues.append(
            ValidationIssue("error", "docker", "Dockerfile sin directiva FROM", body)
        )
    return issues


def _check_docker_cli(body: str) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    first_line = body.splitlines()[0].strip()
    try:
        parts = shlex.split(first_line)
    except ValueError as exc:
        return [ValidationIssue("error", "docker", f"comillas desbalanceadas: {exc}", first_line)]
    if not parts or parts[0] != "docker":
        return [ValidationIssue("error", "docker", "el comando no empieza por 'docker'", first_line)]
    if len(parts) >= 2 and parts[1] not in _DOCKER_CLI_SUBCOMMANDS:
        issues.append(
            ValidationIssue(
                "warning",
                "docker",
                f"subcomando desconocido: {parts[1]}",
                first_line,
            )
        )
    return issues


def _check_compose(body: str) -> List[ValidationIssue]:
    """Valida un docker-compose.yml con ``docker compose config`` (solo cliente)."""
    issues: List[ValidationIssue] = []
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as fh:
        fh.write(body)
        tmp_path = fh.name
    try:
        ok, err = _run_check(["docker", "compose", "-f", tmp_path, "config", "--quiet"])
        if not ok:
            issues.append(
                ValidationIssue("error", "docker", f"compose inválido: {err}", body)
            )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return issues


def check_docker_syntax(body: str) -> List[ValidationIssue]:
    """Despacha a la validación adecuada según el tipo de contenido docker."""
    stripped = body.lstrip()
    if re.search(r"^services\s*:", stripped, re.MULTILINE):
        return _check_compose(body)
    lines = stripped.splitlines()
    first_token = lines[0].strip().split()[0].upper() if lines else ""
    if first_token in _DOCKERFILE_DIRECTIVES:
        return _check_dockerfile(body)
    return _check_docker_cli(body)


def _check_block(lang: str, body: str) -> List[ValidationIssue]:
    flavor = _classify_lang(lang, body)
    if flavor == "bash":
        return check_bash_syntax(body)
    if flavor == "python":
        return check_python_syntax(body)
    if flavor == "docker":
        return check_docker_syntax(body)
    # "unknown": no lo validamos, no contamos como problema.
    return []


# --- Punto de entrada público ---

def validate_facts(text: str) -> ValidationReport:
    """Valida la sintaxis de todos los bloques de código de un texto de hechos.

    Devuelve un :class:`ValidationReport` listo para alimentar el critic y el
    bucle de refinamiento del pipeline.
    """
    issues: List[ValidationIssue] = []
    blocks = extract_code_blocks(text)
    for lang, body in blocks:
        issues.extend(_check_block(lang, body))

    errors = [i for i in issues if i.severity == "error"]
    report = ValidationReport(ok=len(errors) == 0, issues=issues, blocks_checked=len(blocks))
    return report


# Tool que expone el checker al ValidatorAgent (firma simple str -> str).
def validate_syntax_tool(text: str) -> str:
    """Tool del ValidatorAgent: devuelve el informe de validación como texto."""
    return validate_facts(text).to_text()
