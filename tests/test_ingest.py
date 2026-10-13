"""
Tests de la etapa de ingesta multi-fuente (``src.ingest``).

Se ejecutan con stdlib ``unittest`` (sin pytest ni SDK de Gemini)::

    python -m unittest discover -s tests -p "test_ingest.py" -v

Cubren la resolución pura de fuentes (detección de tipo, clasificación de
media, transcripción de asciinema y mapeo ``MediaSource -> IngestResult``).
La descarga real de YouTube y la subida a Gemini se verifican aparte (red /
API key).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.contracts import (  # noqa: E402
    IngestResult,
    MediaAsset,
    MediaKind,
    MediaSource,
    MediaSourceType,
)
from src.ingest import (  # noqa: E402
    cast_to_transcript,
    classify_kind,
    detect_source_type,
    extract_input_commands,
    ingest,
    parse_cast,
    render_output,
    strip_ansi,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SAMPLE_CAST = os.path.join(ROOT, "test_data", "sample_asciinema.cast")
SAMPLE_VIDEO = os.path.join(ROOT, "test_data", "sample_video.mp4")


class TestDetectSourceType(unittest.TestCase):
    def test_youtube_classic(self):
        self.assertEqual(
            detect_source_type("https://www.youtube.com/watch?v=abc123"),
            MediaSourceType.YOUTUBE_URL,
        )

    def test_youtube_short(self):
        self.assertEqual(
            detect_source_type("https://youtu.be/abc123"),
            MediaSourceType.YOUTUBE_URL,
        )

    def test_youtube_shorts(self):
        self.assertEqual(
            detect_source_type("https://www.youtube.com/shorts/xyz"),
            MediaSourceType.YOUTUBE_URL,
        )

    def test_asciinema(self):
        self.assertEqual(
            detect_source_type("/tmp/sesion.cast"), MediaSourceType.ASCIINEMA
        )

    def test_local_media(self):
        self.assertEqual(
            detect_source_type("video.mp4"), MediaSourceType.LOCAL_FILE
        )
        self.assertEqual(
            detect_source_type("audio.mp3"), MediaSourceType.LOCAL_FILE
        )

    def test_raw_text(self):
        self.assertEqual(
            detect_source_type("esto es texto sin extension"), MediaSourceType.TEXT
        )

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            detect_source_type("")


class TestClassifyKind(unittest.TestCase):
    def test_video(self):
        self.assertEqual(classify_kind("x.mp4"), MediaKind.VIDEO)
        self.assertEqual(classify_kind("x.webm"), MediaKind.VIDEO)

    def test_audio(self):
        self.assertEqual(classify_kind("x.mp3"), MediaKind.AUDIO)

    def test_image(self):
        self.assertEqual(classify_kind("x.png"), MediaKind.IMAGE)

    def test_text_default(self):
        self.assertEqual(classify_kind("x.cast"), MediaKind.TEXT)
        self.assertEqual(classify_kind("x.txt"), MediaKind.TEXT)


class TestAsciinema(unittest.TestCase):
    def test_parse_cast(self):
        header, events = parse_cast(SAMPLE_CAST)
        self.assertEqual(header["version"], 2)
        self.assertEqual(header["width"], 80)
        kinds = {e[1] for e in events}
        self.assertIn("o", kinds)
        self.assertIn("i", kinds)

    def test_extract_input_commands(self):
        _, events = parse_cast(SAMPLE_CAST)
        commands = extract_input_commands(events)
        self.assertIn("sudo pacman -Syu", commands)
        self.assertIn("Y", commands)
        self.assertTrue(all("\r" not in c and "\n" not in c for c in commands))

    def test_render_output_strips_ansi(self):
        _, events = parse_cast(SAMPLE_CAST)
        output = render_output(events, width=80)
        self.assertNotIn("\x1b", output)
        self.assertIn("core is up to date", output)

    def test_render_output_carriage_return(self):
        events = [(0.0, "o", "aaa\rb")]
        self.assertEqual(render_output(events, width=10), "baa")

    def test_render_output_backspace(self):
        events = [(0.0, "o", "ab\bc")]
        self.assertEqual(render_output(events, width=10), "ac")

    def test_cast_to_transcript(self):
        transcript = cast_to_transcript(SAMPLE_CAST)
        self.assertIn("sudo pacman -Syu", transcript)
        self.assertIn("Total Installed Size", transcript)

    def test_strip_ansi(self):
        self.assertEqual(strip_ansi("\x1b[32mgreen\x1b[0m"), "green")


class TestIngest(unittest.TestCase):
    def test_asciinema_to_text_asset(self):
        src = MediaSource(source_type=MediaSourceType.ASCIINEMA, locator=SAMPLE_CAST)
        result = ingest(src)
        self.assertIsInstance(result, IngestResult)
        self.assertEqual(len(result.assets), 1)
        asset = result.assets[0]
        self.assertIsInstance(asset, MediaAsset)
        self.assertEqual(asset.kind, MediaKind.TEXT)
        self.assertEqual(asset.status, "ready")
        self.assertIsNotNone(asset.local_path)
        self.assertTrue(os.path.exists(asset.local_path))
        # El contenido local debe contener la transcripción (comando + salida).
        with open(asset.local_path, encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn("sudo pacman -Syu", content)

    def test_local_video_asset(self):
        if not os.path.exists(SAMPLE_VIDEO):
            self.skipTest("sample_video.mp4 no disponible")
        src = MediaSource(source_type=MediaSourceType.LOCAL_FILE, locator=SAMPLE_VIDEO)
        result = ingest(src)
        self.assertEqual(len(result.assets), 1)
        self.assertEqual(result.assets[0].kind, MediaKind.VIDEO)
        self.assertEqual(result.assets[0].local_path, SAMPLE_VIDEO)

    def test_text_source_to_text_asset(self):
        src = MediaSource(
            source_type=MediaSourceType.TEXT, locator="un comando: sudo reboot"
        )
        result = ingest(src)
        self.assertEqual(result.assets[0].kind, MediaKind.TEXT)
        self.assertTrue(os.path.exists(result.assets[0].local_path))

    def test_missing_local_file_raises(self):
        src = MediaSource(
            source_type=MediaSourceType.LOCAL_FILE, locator="/no/existe.mp4"
        )
        with self.assertRaises(FileNotFoundError):
            ingest(src)


if __name__ == "__main__":
    unittest.main(verbosity=2)