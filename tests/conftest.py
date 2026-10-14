"""Asegura que ``src/`` y el root del proyecto estén en sys.path al ejecutar los tests."""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_PROJECT_ROOT, "src")
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

_TEST_VIDEO = os.path.join(_PROJECT_ROOT, "test_data", "sample_video.mp4")