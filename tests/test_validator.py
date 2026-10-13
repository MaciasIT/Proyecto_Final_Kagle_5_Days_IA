"""Tests del módulo de validación (ValidatorAgent).

Ejecutar con:
    python -m unittest discover -s tests -v
o con pytest si está disponible:
    pytest tests/ -v
"""

import unittest

from src.validator import (
    check_bash_syntax,
    check_docker_syntax,
    check_python_syntax,
    extract_code_blocks,
    validate_facts,
)


class TestExtractCodeBlocks(unittest.TestCase):
    def test_fenced_blocks_with_lang(self):
        text = "```bash\nsudo pacman -Syu\n```\n```python\nimport os\n```"
        blocks = extract_code_blocks(text)
        langs = [lang for lang, _ in blocks]
        self.assertIn("bash", langs)
        self.assertIn("python", langs)

    def test_inline_command(self):
        blocks = extract_code_blocks("Ejecuta `sudo systemctl restart nginx`.")
        self.assertTrue(any("sudo systemctl" in body for _, body in blocks))

    def test_empty_text(self):
        self.assertEqual(extract_code_blocks(""), [])


class TestBashSyntax(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(check_bash_syntax("echo 'hola'\nls -la\n"), [])

    def test_invalid(self):
        issues = check_bash_syntax("if [ then\n")
        self.assertTrue(any(i.kind == "bash" and i.severity == "error" for i in issues))


class TestPythonSyntax(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(check_python_syntax("import os\nprint(os.getcwd())\n"), [])

    def test_invalid(self):
        issues = check_python_syntax("def f(:\n")
        self.assertTrue(any(i.kind == "python" for i in issues))


class TestDockerSyntax(unittest.TestCase):
    def test_dockerfile_missing_from(self):
        issues = check_docker_syntax("RUN apt-get update\n")
        self.assertTrue(any("FROM" in i.message for i in issues))

    def test_docker_cli_valid(self):
        issues = check_docker_syntax("docker run -d nginx\n")
        # Sin errores (el subcomando 'run' es conocido).
        self.assertFalse(any(i.severity == "error" for i in issues))

    def test_docker_cli_unknown_subcommand(self):
        issues = check_docker_syntax("docker foobar nginx\n")
        self.assertTrue(any(i.kind == "docker" for i in issues))


class TestValidateFacts(unittest.TestCase):
    def test_clean_text_ok(self):
        report = validate_facts(
            "Hechos:\n```bash\nsudo pacman -Syu\n```\n```python\nprint('ok')\n```"
        )
        self.assertTrue(report.ok)
        self.assertEqual(report.blocks_checked, 2)

    def test_broken_command_detected(self):
        report = validate_facts("```bash\nif [ then\n```")
        self.assertFalse(report.ok)
        self.assertGreater(len(report.errors), 0)

    def test_to_text(self):
        report = validate_facts("```bash\nif [ then\n```")
        self.assertIn("VALIDACIÓN CON PROBLEMAS", report.to_text())


if __name__ == "__main__":
    unittest.main()
