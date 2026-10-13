"""
Tests del módulo de benchmark de hechos técnicos (F4 QA).

Verifican tres cosas de forma determinista (sin llamadas a Gemini):

  1. Que el ground truth de test_data/ground_truth.json sea coherente con
     los dos vídeos reales (control negativo vs positivo).
  2. Que la extracción de hechos (comandos, paquetes, kernels) funcione
     sobre texto libre y sobre PipelineResult estructurado.
  3. Que la puntuación detecte alucinaciones: un texto que inventa comandos
     debe obtener hallucination > 0 y precision < 1.

Ejecutar con:
    python -m unittest discover -s tests -v
"""

import json
import os
import unittest

# Garantizar que el paquete `src` sea importable desde la raíz del proyecto.
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.benchmark import (  # noqa: E402
    GROUND_TRUTH_PATH,
    ExtractedFacts,
    compare_versions,
    extract_facts_from_pipeline_result,
    extract_facts_from_text,
    ground_truth_for,
    load_ground_truth,
    score_facts,
)

TEST_DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_data"))
SAMPLE_VIDEO = os.path.join(TEST_DATA, "sample_video.mp4")
PACMAN_VIDEO = os.path.join(TEST_DATA, "sudo_pacman_update.webm")


class TestGroundTruth(unittest.TestCase):
    def test_ground_truth_file_exists(self):
        self.assertTrue(os.path.isfile(GROUND_TRUTH_PATH))

    def test_pacman_has_positive_facts(self):
        gt = ground_truth_for("sudo_pacman_update.webm")
        self.assertIn("sudo pacman -Syu", gt["commands"])
        self.assertEqual(len(gt["packages_upgraded"]), 4)
        self.assertEqual(gt["os"], "Arch Linux")
        self.assertEqual(gt["user"], "vicfic")
        self.assertEqual(gt["host"], "ALG3")
        # Versiones clave verificadas por OCR.
        pkgs = {p["name"]: p["version"] for p in gt["packages_upgraded"]}
        self.assertEqual(pkgs["chromium"], "94.0.4606.81-1")
        self.assertEqual(pkgs["appstream"], "0.14.6-1")
        self.assertEqual(gt["kernel"], "5.14.9-arch2-1")
        # Advertencias de firmware observadas.
        self.assertTrue(set(gt["firmware_warnings"]) >= {"wd719x", "aic94xx", "xhci_pci"})

    def test_sample_video_is_negative_control(self):
        gt = ground_truth_for("sample_video.mp4")
        self.assertEqual(gt["commands"], [])
        self.assertEqual(gt["packages_upgraded"], [])
        self.assertEqual(gt["expected_technical_facts"], 0)

    def test_videos_exist(self):
        self.assertTrue(os.path.isfile(SAMPLE_VIDEO))
        self.assertTrue(os.path.isfile(PACMAN_VIDEO))


class TestExtractionText(unittest.TestCase):
    def test_extract_sudo_command(self):
        facts = extract_facts_from_text(
            "## Actualización\nEjecuta `sudo pacman -Syu` para actualizar.\n"
        )
        self.assertTrue(any("pacman" in c for c in facts.commands))

    def test_extract_package_with_version(self):
        facts = extract_facts_from_text(
            "Se actualizaron chromium-94.0.4606.81-1 y appstream-0.14.6-1."
        )
        pkgs = [f"{n}-{v}" for n, v in facts.packages]
        self.assertIn("chromium-94.0.4606.81-1", pkgs)
        self.assertIn("appstream-0.14.6-1", pkgs)

    def test_extract_kernel(self):
        facts = extract_facts_from_text("kernel 5.14.9-arch2-1 reconstruido")
        self.assertIn("5.14.9-arch2-1", facts.kernels)

    def test_extract_host(self):
        facts = extract_facts_from_text("usuario vicfic@ALG3 ejecutó el comando")
        self.assertIn("ALG3", facts.hosts)

    def test_extract_firmware_warning(self):
        facts = extract_facts_from_text(
            "WARNING: Possibly missing firmware for module: wd719x"
        )
        self.assertIn("wd719x", facts.firmware_warnings)

    def test_empty_text(self):
        facts = extract_facts_from_text("")
        self.assertEqual(facts.declared_count(), 0)


class TestExtractionPipelineResult(unittest.TestCase):
    def _sample_pipeline_result(self):
        """PipelineResult v2 de ejemplo (dict), con un comando y dos paquetes."""
        return {
            "analysis": {
                "facts": [
                    {
                        "fact_id": "f1",
                        "kind": "command",
                        "summary": "Actualizar sistema",
                        "code": "sudo pacman -Syu",
                    }
                ],
                "code_snippets": [],
            },
            "document": {
                "steps": [
                    {
                        "index": 1,
                        "title": "Actualizar",
                        "code_snippet": "sudo pacman -Syu",
                    },
                    {
                        "index": 2,
                        "title": "Paquetes",
                        "description": "chromium-94.0.4606.81-1 y flatpak-1.12.0-1",
                    },
                ]
            },
        }

    def test_extract_from_pipeline_result(self):
        facts = extract_facts_from_pipeline_result(self._sample_pipeline_result())
        self.assertTrue(any("pacman" in c for c in facts.commands))
        pkgs = [f"{n}-{v}" for n, v in facts.packages]
        self.assertIn("chromium-94.0.4606.81-1", pkgs)
        self.assertIn("flatpak-1.12.0-1", pkgs)


class TestScoring(unittest.TestCase):
    def test_perfect_match_no_hallucination(self):
        facts = ExtractedFacts(
            commands=["sudo pacman -Syu"],
            packages=[
                ("appstream", "0.14.6-1"),
                ("chromium", "94.0.4606.81-1"),
                ("flatpak", "1.12.0-1"),
                ("ostree", "2021.5-1"),
            ],
        )
        r = score_facts("sudo_pacman_update.webm", "v2", facts)
        self.assertEqual(r.precision, 1.0)
        self.assertEqual(r.hallucination, 0.0)
        self.assertEqual(r.recall, 1.0)

    def test_hallucination_detected(self):
        # El pipeline declara un comando Ubuntu (apt) sobre un vídeo de Arch.
        facts = ExtractedFacts(
            commands=["sudo apt update"],
            packages=[("apache2", "2.4.58-1")],
        )
        r = score_facts("sudo_pacman_update.webm", "v1", facts)
        self.assertGreater(r.hallucination, 0.0)
        self.assertLess(r.precision, 1.0)
        self.assertIn("sudo apt update", r.false_positives)

    def test_negative_control_any_command_is_hallucination(self):
        # sample_video.mp4 no tiene comandos ground-truth: cualquier comando
        # declarado es una alucinación.
        facts = ExtractedFacts(commands=["sudo apt install apache2 -y"])
        r = score_facts("sample_video.mp4", "v1", facts)
        self.assertEqual(r.precision, 0.0)
        self.assertEqual(r.hallucination, 1.0)
        self.assertEqual(r.false_positives, ["sudo apt install apache2 -y"])

    def test_empty_output_on_negative_control_is_correct(self):
        facts = ExtractedFacts()
        r = score_facts("sample_video.mp4", "v2", facts)
        self.assertEqual(r.precision, 1.0)
        self.assertEqual(r.hallucination, 0.0)

    def test_missed_facts_reported(self):
        facts = ExtractedFacts(commands=["sudo pacman -Syu"])
        r = score_facts("sudo_pacman_update.webm", "v1", facts)
        # Solo recuperó el comando; faltan los 4 paquetes gt.
        self.assertLess(r.recall, 1.0)
        self.assertGreater(len(r.missed), 0)


class TestCompareVersions(unittest.TestCase):
    def test_compare_v1_text_vs_v2_result(self):
        v1_text = (
            "# Documento\n## Procedimiento\n1. Ejecuta `sudo pacman -Syu`.\n"
            "Se actualizó chromium-94.0.4606.81-1.\n"
        )
        v2_result = {
            "analysis": {
                "facts": [
                    {
                        "fact_id": "f1",
                        "kind": "command",
                        "code": "sudo pacman -Syu",
                    }
                ],
                "code_snippets": [],
            },
            "document": {
                "steps": [
                    {
                        "index": 1,
                        "title": "Paquetes",
                        "description": (
                            "appstream-0.14.6-1, chromium-94.0.4606.81-1, "
                            "flatpak-1.12.0-1, ostree-2021.5-1"
                        ),
                    }
                ]
            },
        }
        results = compare_versions("sudo_pacman_update.webm", v1_text, v2_result)
        self.assertEqual(len(results), 2)
        by_ver = {r.version: r for r in results}
        self.assertIn("v1", by_ver)
        self.assertIn("v2", by_ver)
        # v2 declara los 4 paquetes + comando -> recall completo, sin alucinación.
        self.assertEqual(by_ver["v2"].hallucination, 0.0)
        self.assertEqual(by_ver["v2"].recall, 1.0)

    def test_compare_returns_empty_on_none(self):
        results = compare_versions("sudo_pacman_update.webm", None, None)
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
