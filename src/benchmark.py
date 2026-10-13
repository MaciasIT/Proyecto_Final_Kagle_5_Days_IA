"""
Doc Squad v2 — Benchmark de hechos técnicos (F4 QA).

Suite que contrasta la tasa de alucinación y la precisión técnica del
pipeline de documentación (v1 vs v2) contra los dos vídeos de test_data:

  * test_data/sample_video.mp4          (control negativo: sin comandos)
  * test_data/sudo_pacman_update.webm   (actualización real de Arch Linux)

La idea central: el ground truth se extrae de forma DETERMINISTA (OCR sobre
fotogramas + metadatos ffprobe) y se compara con los hechos técnicos que
declara el pipeline en su salida (documento Markdown v1, o PipelineResult
estructurado v2). No se usa ningún LLM para puntuar: la comparación es
lexical y reproducible.

Métricas calculadas por vídeo y por versión (v1/v2):

  * recall           = hechos ground-truth correctamente declarados / total gt
  * precision        = hechos declarados que son correctos / total declarados
  * hallucination    = hechos declarados que NO están en ground truth / total
  * f1               = media armónica de precision y recall

Diseñado con stdlib únicamente (json, re, subprocess) para que corra sin
dependencias externas, en línea con tests/test_ingestion.py y
tests/test_validator.py.

Fecha: 2026-10-13
Autor: [caos]
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
#  Rutas y constantes
# --------------------------------------------------------------------------- #

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DATA = os.path.join(PROJECT_ROOT, "test_data")
GROUND_TRUTH_PATH = os.path.join(TEST_DATA, "ground_truth.json")

# Patrones para extraer hechos técnicos de una salida de texto libre (v1).
_COMMAND_RE = re.compile(
    r"\bsudo\s+[a-zA-Z0-9_./-]+(?:\s+[^\n`]{0,120})?"
)
_PACKAGE_RE = re.compile(
    r"\b([a-z][a-z0-9+.-]*)-(\d+(?:\.\d+)+(?:[.-][0-9a-zA-Z]+-?[0-9]*)*)\b"
)
_KERNEL_RE = re.compile(r"\b(\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?)\b")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HOST_RE = re.compile(r"\b([a-zA-Z0-9-]+)@([a-zA-Z0-9.-]+)\b")

# Hechos técnicos normalizados que extraemos de cualquier salida.
@dataclass
class ExtractedFacts:
    commands: List[str] = field(default_factory=list)
    packages: List[Tuple[str, str]] = field(default_factory=list)  # (name, version)
    kernels: List[str] = field(default_factory=list)
    ips: List[str] = field(default_factory=list)
    hosts: List[str] = field(default_factory=list)
    firmware_warnings: List[str] = field(default_factory=list)

    def declared_count(self) -> int:
        """Número total de hechos técnicos 'atómicos' declarados."""
        return (
            len(self.commands)
            + len(self.packages)
            + len(self.kernels)
            + len(self.ips)
            + len(self.hosts)
            + len(self.firmware_warnings)
        )

    def to_dict(self) -> Dict[str, List]:
        return {
            "commands": list(self.commands),
            "packages": [f"{n}-{v}" for n, v in self.packages],
            "kernels": list(self.kernels),
            "ips": list(self.ips),
            "hosts": list(self.hosts),
            "firmware_warnings": list(self.firmware_warnings),
        }


# --------------------------------------------------------------------------- #
#  Ground truth
# --------------------------------------------------------------------------- #

def load_ground_truth(path: str = GROUND_TRUTH_PATH) -> Dict:
    """Carga el fichero de ground truth (JSON) de test_data."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def ground_truth_for(video_name: str, gt: Optional[Dict] = None) -> Dict:
    """Devuelve el ground truth de un vídeo concreto."""
    gt = gt or load_ground_truth()
    for name, data in gt["videos"].items():
        if name == video_name or name in video_name:
            return data
    raise KeyError(f"No hay ground truth para {video_name!r}")


# --------------------------------------------------------------------------- #
#  Extracción de hechos desde salida del pipeline
# --------------------------------------------------------------------------- #

def _run_ffprobe_duration(video_path: str) -> float:
    """Duración real del vídeo vía ffprobe (0.0 si no está disponible)."""
    if not os.path.isfile(video_path):
        return 0.0
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return float(proc.stdout.strip() or 0.0)
    except (ValueError, OSError, subprocess.SubprocessError):
        return 0.0


def extract_facts_from_text(text: str) -> ExtractedFacts:
    """Extrae hechos técnicos (comandos, paquetes, kernels, IPs, hosts)
    de una salida de texto libre (documento Markdown de v1)."""
    facts = ExtractedFacts()

    if not text:
        return facts

    # Comandos: sudo ... (más comunes en documentación de sistemas).
    for m in _COMMAND_RE.finditer(text):
        cmd = " ".join(m.group(0).split())
        if cmd not in facts.commands:
            facts.commands.append(cmd)

    # Paquetes: nombre-versión (p. ej. chromium-94.0.4606.81-1).
    seen_pkgs = set()
    for m in _PACKAGE_RE.finditer(text):
        pair = (m.group(1), m.group(2))
        if pair not in seen_pkgs:
            seen_pkgs.add(pair)
            facts.packages.append(pair)

    # Kernels: X.Y.Z[-sufijo].
    for m in _KERNEL_RE.finditer(text):
        k = m.group(1)
        if k not in facts.kernels:
            facts.kernels.append(k)

    # IPs.
    for m in _IP_RE.finditer(text):
        ip = m.group(0)
        if ip not in facts.ips:
            facts.ips.append(ip)

    # Hosts (user@host).
    for m in _HOST_RE.finditer(text):
        h = m.group(2)
        if h not in facts.hosts:
            facts.hosts.append(h)

    # Firmware warnings: módulos citados tras "firmware".
    for m in re.finditer(r"firmware\s+for\s+module:\s*([a-z0-9_]+)", text, re.IGNORECASE):
        mod = m.group(1)
        if mod not in facts.firmware_warnings:
            facts.firmware_warnings.append(mod)

    return facts


def extract_facts_from_pipeline_result(result) -> ExtractedFacts:
    """Extrae hechos de un PipelineResult estructurado (v2).

    Acepta un objeto Pydantic (contracts.PipelineResult) o un dict JSON.
    Recorre analysis.facts y document.steps buscando commands, packages,
    kernels, IPs, hosts y avisos de firmware.
    """
    facts = ExtractedFacts()

    # Normalizar a dict si es un modelo Pydantic.
    d = result if isinstance(result, dict) else _model_to_dict(result)

    analysis = d.get("analysis") or {}
    for fact in analysis.get("facts", []):
        _ingest_fact(fact, facts)

    document = d.get("document") or {}
    for step in document.get("steps", []):
        code = step.get("code_snippet") or step.get("code") or ""
        if code:
            sub = extract_facts_from_text(code)
            _merge(facts, sub)
        # Los pasos pueden describir paquetes/comandos en description/title.
        desc = f"{step.get('description') or ''}\n{step.get('title') or ''}"
        if desc.strip():
            _merge(facts, extract_facts_from_text(desc))

    # Si hay snippets sueltos en analysis, también.
    for snip in analysis.get("code_snippets", []):
        code = snip.get("code") or ""
        if code:
            _merge(facts, extract_facts_from_text(code))

    return facts


def _ingest_fact(fact: Dict, facts: ExtractedFacts) -> None:
    """Incorpora un TechnicalFact (dict) a ExtractedFacts."""
    kind = fact.get("kind")
    code = fact.get("code") or ""
    summary = fact.get("summary") or ""
    detail = fact.get("detail") or ""
    host = fact.get("host")
    ip = fact.get("ip")

    if code:
        _merge(facts, extract_facts_from_text(code))
    if kind == "command" and not code:
        # El hecho es un comando pero no vino en 'code'; intentar en summary.
        cmd = summary.strip()
        if cmd and re.match(r"^sudo\s+", cmd):
            if cmd not in facts.commands:
                facts.commands.append(cmd)
    if host and host not in facts.hosts:
        facts.hosts.append(host)
    if ip and ip not in facts.ips:
        facts.ips.append(ip)
    # Paquetes/versiones citados en summary/detail.
    _merge(facts, extract_facts_from_text(f"{summary}\n{detail}"))


def _model_to_dict(model) -> Dict:
    """Convierte un modelo Pydantic a dict (con fallback a __dict__)."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    if hasattr(model, "__dict__"):
        return model.__dict__
    return {}


def _merge(dst: ExtractedFacts, src: ExtractedFacts) -> None:
    """Fusiona src en dst evitando duplicados."""
    for c in src.commands:
        if c not in dst.commands:
            dst.commands.append(c)
    for p in src.packages:
        if p not in dst.packages:
            dst.packages.append(p)
    for k in src.kernels:
        if k not in dst.kernels:
            dst.kernels.append(k)
    for ip in src.ips:
        if ip not in dst.ips:
            dst.ips.append(ip)
    for h in src.hosts:
        if h not in dst.hosts:
            dst.hosts.append(h)
    for fw in src.firmware_warnings:
        if fw not in dst.firmware_warnings:
            dst.firmware_warnings.append(fw)


# --------------------------------------------------------------------------- #
#  Comparación con ground truth
# --------------------------------------------------------------------------- #

def _norm_cmd(cmd: str) -> str:
    """Normaliza un comando para comparación lexical tolerante."""
    return " ".join(cmd.lower().split())


@dataclass
class BenchmarkResult:
    video: str
    version: str
    recall: float
    precision: float
    hallucination: float
    f1: float
    gt_commands: List[str]
    declared_commands: List[str]
    gt_packages: List[str]
    declared_packages: List[str]
    false_positives: List[str] = field(default_factory=list)
    missed: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "video": self.video,
            "version": self.version,
            "recall": round(self.recall, 4),
            "precision": round(self.precision, 4),
            "hallucination": round(self.hallucination, 4),
            "f1": round(self.f1, 4),
            "declared_count": len(self.declared_commands) + len(self.declared_packages),
            "gt_count": len(self.gt_commands) + len(self.gt_packages),
            "false_positives": self.false_positives,
            "missed": self.missed,
        }


def score_facts(
    video_name: str,
    version: str,
    extracted: ExtractedFacts,
    gt: Optional[Dict] = None,
) -> BenchmarkResult:
    """Puntúa hechos extraídos contra ground truth.

    Se comparan dos clases de hechos: comandos y paquetes (nombre+versión).
    Un comando 'declarado' cuenta como correcto si su forma normalizada
    aparece (o es subcadena) de un comando ground-truth. Un paquete cuenta
    si el par (nombre, versión) coincide exactamente.
    """
    gtv = ground_truth_for(video_name, gt)

    gt_cmds = [c for c in gtv.get("commands", [])]
    gt_pkgs = [f"{p['name']}-{p['version']}" for p in gtv.get("packages_upgraded", [])]

    # Conjuntos normalizados de ground truth.
    gt_cmd_norm = {_norm_cmd(c) for c in gt_cmds}

    # Comandos: correctos si normalizados coinciden.
    correct_cmds: List[str] = []
    false_cmds: List[str] = []
    for c in extracted.commands:
        nc = _norm_cmd(c)
        matched = any(nc == gc or gc in nc or nc in gc for gc in gt_cmd_norm)
        # Exigencia extra: el comando debe contener la acción central (sin
        # coincidir por una palabra suelta). Usamos match exacto o subcadena.
        if matched and len(nc) >= 5:
            correct_cmds.append(c)
        else:
            false_cmds.append(c)

    # Paquetes: coincidencia exacta de nombre y versión.
    correct_pkgs: List[str] = []
    false_pkgs: List[str] = []
    for name, ver in extracted.packages:
        label = f"{name}-{ver}"
        if label in gt_pkgs:
            correct_pkgs.append(label)
        else:
            false_pkgs.append(label)

    declared_total = len(extracted.commands) + len(extracted.packages)
    correct_total = len(correct_cmds) + len(correct_pkgs)
    gt_total = len(gt_cmds) + len(gt_pkgs)

    # recall: fracción del ground truth recuperada.
    recall = correct_total / gt_total if gt_total else 1.0
    # precision: fracción de lo declarado que es correcto.
    precision = correct_total / declared_total if declared_total else 1.0
    # hallucination: fracción de lo declarado que NO está en gt.
    hallucination = 1.0 - precision
    # f1.
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    false_positives = false_cmds + false_pkgs
    # "missed": comandos y paquetes ground-truth no recuperados.
    missed = [c for c in gt_cmds if _norm_cmd(c) not in {_norm_cmd(x) for x in correct_cmds}]
    missed += [p for p in gt_pkgs if p not in correct_pkgs]

    return BenchmarkResult(
        video=video_name,
        version=version,
        recall=recall,
        precision=precision,
        hallucination=hallucination,
        f1=f1,
        gt_commands=gt_cmds,
        declared_commands=extracted.commands,
        gt_packages=gt_pkgs,
        declared_packages=[f"{n}-{v}" for n, v in extracted.packages],
        false_positives=false_positives,
        missed=missed,
    )


# --------------------------------------------------------------------------- #
#  Generación de informe
# --------------------------------------------------------------------------- #

def render_report(results: List[BenchmarkResult]) -> str:
    """Renderiza un informe Markdown comparando v1 vs v2 por vídeo."""
    lines: List[str] = [
        "# Benchmark de hechos técnicos — v1 vs v2",
        "",
        "Métricas por vídeo y versión del pipeline. El ground truth es ",
        "determinista (OCR + ffprobe), no depende de ningún LLM.",
        "",
        "| Vídeo | Versión | Recall | Precision | Alucinación | F1 |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.video} | {r.version} | {r.recall:.2%} | {r.precision:.2%} "
            f"| {r.hallucination:.2%} | {r.f1:.2%} |"
        )
    lines.append("")

    # Detalle de falsos positivos (alucinaciones) por versión.
    for r in results:
        if r.false_positives:
            lines.append(f"## {r.video} · {r.version} — falsos positivos")
            for fp in r.false_positives:
                lines.append(f"- `{fp}`")
            lines.append("")
        if r.missed:
            lines.append(f"## {r.video} · {r.version} — hechos no recuperados")
            for m in r.missed:
                lines.append(f"- `{m}`")
            lines.append("")

    return "\n".join(lines)


def compare_versions(
    video_name: str,
    v1_output,
    v2_output,
    gt: Optional[Dict] = None,
) -> List[BenchmarkResult]:
    """Compara la salida de v1 (texto) y v2 (PipelineResult) contra ground truth.

    ``v1_output`` es el string Markdown que devuelve run_documentation_pipeline.
    ``v2_output`` es un PipelineResult (Pydantic) o su dict JSON.
    Devuelve una lista con dos BenchmarkResult (v1 y v2).
    """
    results: List[BenchmarkResult] = []

    if v1_output is not None:
        v1_text = v1_output if isinstance(v1_output, str) else str(v1_output)
        facts_v1 = extract_facts_from_text(v1_text)
        results.append(score_facts(video_name, "v1", facts_v1, gt))

    if v2_output is not None:
        facts_v2 = extract_facts_from_pipeline_result(v2_output)
        results.append(score_facts(video_name, "v2", facts_v2, gt))

    return results
