# Benchmark de hechos técnicos — F4 QA (v1 vs v2)

Suite que contrasta la **tasa de alucinación** y la **precisión técnica** del
pipeline de documentación entre v1 (Markdown libre) y v2 (PipelineResult
estructurado), contra los dos vídeos de `test_data/`.

## Filosofía

El ground truth **no depende de ningún LLM**: se extrajo de forma determinista
con `tesseract` (OCR sobre fotogramas) + `ffprobe` (metadatos). Esto garantiza
que la comparación sea reproducible y no sesgue a favor de v2.

## Ficheros

| Ruta | Propósito |
|---|---|
| `test_data/ground_truth.json` | Hechos verificados de cada vídeo (comandos, paquetes, kernel, host, firmware). |
| `src/benchmark.py` | Extracción de hechos + puntuación (recall, precision, alucinación, f1). |
| `scripts/run_benchmark.py` | CLI para puntuar salidas v1/v2 contra ground truth. |
| `tests/test_benchmark.py` | 18 tests deterministas (stdlib, sin red). |

## Métricas

- **recall** = hechos ground-truth correctamente recuperados / total ground truth.
- **precision** = hechos declarados correctos / total declarados.
- **alucinación** = hechos declarados que NO están en ground truth / total (1 − precision).
- **f1** = media armónica de precision y recall.

## Uso

```bash
# Listar vídeos con ground truth
python -m scripts.run_benchmark --list

# Puntuar salidas reales (v1 = Markdown, v2 = JSON PipelineResult)
python -m scripts.run_benchmark \
    --video sudo_pacman_update.webm \
    --v1 /ruta/salida_v1.md \
    --v2 /ruta/salida_v2.json
```

```bash
# Ejecutar los tests
python -m unittest tests.test_benchmark -v
```

## Vídeos de referencia

- **`sudo_pacman_update.webm`** (control positivo): grabación real de terminal
  (1080p, 61.67 s) de un `sudo pacman -Syu` en Arch Linux. Ground truth:
  1 comando y 4 paquetes (`appstream-0.14.6-1`, `chromium-94.0.4606.81-1`,
  `flatpak-1.12.0-1`, `ostree-2021.5-1`), kernel `5.14.9-arch2-1`, host `ALG3`,
  usuario `vicfic`, y 3 avisos de firmware (`wd719x`, `aic94xx`, `xhci_pci`).
- **`sample_video.mp4`** (control negativo): clip de 30 s (854x480, 6 canales de
  audio) **sin** contenido de terminal. Cualquier comando que un pipeline le
  atribuya es alucinación (precisión 0, alucinación 100%).

## Hallazgo de integridad de datos (para el equipo)

`test_data/sample_asciinema.cast` (fixture añadido por la tarea de ingesta)
**no coincide** con el contenido real de `sudo_pacman_update.webm`:

| Hecho | `.cast` (fixture) | `sudo_pacman_update.webm` (real) |
|---|---|---|
| Kernel | `linux-6.8.1-1` | `5.14.9-arch2-1` |
| Paquetes | "Packages (1)" | "Packages (4)" |
| Usuario/host | `user@host` | `vicfic@ALG3` |

No es un bug del pipeline, pero el fixture no debe usarse como ground truth del
vídeo webm: si se comparan salidas contra él, se penalizarían hechos correctos.
El ground truth canónico es `ground_truth.json`.
