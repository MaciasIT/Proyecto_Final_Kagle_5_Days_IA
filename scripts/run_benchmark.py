"""
Runner del benchmark F4: compara v1 vs v2 contra ground truth.

Uso (desde la raíz del proyecto):

    python -m scripts.run_benchmark \
        --video sudo_pacman_update.webm \
        --v1 /ruta/salida_v1.md \
        --v2 /ruta/salida_v2.json

Sin argumentos, imprime el ground truth y un ejemplo de cómo invocarlo.
Las salidas v1/v2 son las que producen los pipelines (v1 = Markdown de
run_documentation_pipeline; v2 = PipelineResult serializado a JSON). Este
script NO llama a Gemini: solo puntúa salidas ya generadas.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.benchmark import (
    compare_versions,
    ground_truth_for,
    load_ground_truth,
    render_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark F4 v1 vs v2")
    parser.add_argument("--video", help="Nombre del vídeo (p. ej. sudo_pacman_update.webm)")
    parser.add_argument("--v1", help="Ruta al Markdown de salida de v1")
    parser.add_argument("--v2", help="Ruta al JSON (PipelineResult) de v2")
    parser.add_argument("--list", action="store_true", help="Listar vídeos con ground truth")
    args = parser.parse_args()

    gt = load_ground_truth()

    if args.list or not args.video:
        print("Vídeos con ground truth disponible:")
        for name, data in gt["videos"].items():
            n_cmd = len(data.get("commands", []))
            n_pkg = len(data.get("packages_upgraded", []))
            print(f"  - {name}: {n_cmd} comando(s), {n_pkg} paquete(s)")
        print("\nUsa --video <nombre> --v1 <ruta.md> --v2 <ruta.json> para puntuar.")
        return 0

    v1_output = None
    v2_output = None
    if args.v1:
        with open(args.v1, "r", encoding="utf-8") as fh:
            v1_output = fh.read()
    if args.v2:
        with open(args.v2, "r", encoding="utf-8") as fh:
            v2_output = json.load(fh)

    results = compare_versions(args.video, v1_output, v2_output, gt)
    if not results:
        print("No se proporcionó salida de v1 ni de v2.", file=sys.stderr)
        return 2

    print(render_report(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
