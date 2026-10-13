import base64
import os

from video_grounding.markdown_builder import MarkdownBuilder
from video_grounding.schemas import (
    ActionType,
    FrameCapture,
    GroundedAction,
    VideoGroundingResult,
)


def _make_result(tmp_path):
    # crea un JPEG fake minimo (2 bytes basta para el test de data-uri)
    img = os.path.join(str(tmp_path), "f.jpg")
    with open(img, "wb") as f:
        f.write(b"\xff\xd8FAKE")
    action = GroundedAction(
        index=1,
        timestamp="00:05",
        timestamp_seconds=5.0,
        title="Instalar paquete",
        description="Ejecutamos la instalacion",
        command="sudo pacman -S nginx",
        action_type=ActionType.COMMAND,
    )
    frame = FrameCapture(action_index=1, timestamp_seconds=5.0, image_path=img)
    return VideoGroundingResult(
        video_path="/tmp/video.mp4",
        duration_seconds=30.0,
        model="test",
        title="Titulo",
        summary="Resumen",
        actions=[action],
        frames=[frame],
    ), img


def test_base64_embedding(tmp_path):
    result, _ = _make_result(tmp_path)
    md = MarkdownBuilder("base64").build(result)
    assert "![Fotograma 00:05](data:image/jpeg;base64," in md
    assert "sudo pacman -S nginx" in md
    assert "`[00:05]`" in md


def test_base64_decodes_back(tmp_path):
    result, img = _make_result(tmp_path)
    md = MarkdownBuilder("base64").build(result)
    marker = "data:image/jpeg;base64,"
    start = md.index(marker) + len(marker)
    end = md.index(")", start)
    payload = md[start:end]
    decoded = base64.b64decode(payload)
    assert decoded == b"\xff\xd8FAKE"


def test_file_mode_copies_assets(tmp_path):
    result, _ = _make_result(tmp_path)
    out = os.path.join(str(tmp_path), "out.md")
    MarkdownBuilder("file").build(result, output_path=out)
    assert os.path.exists(os.path.join(str(tmp_path), "assets", "f.jpg"))
    with open(out, encoding="utf-8") as f:
        content = f.read()
    assert "](assets/f.jpg)" in content
    assert "data:" not in content


def test_error_action_adds_warning(tmp_path):
    result, _ = _make_result(tmp_path)
    result.actions[0].action_type = ActionType.ERROR
    md = MarkdownBuilder("base64").build(result)
    assert "WARNING" in md


def test_write_output(tmp_path):
    result, _ = _make_result(tmp_path)
    out = os.path.join(str(tmp_path), "doc.md")
    md = MarkdownBuilder("base64").build(result, output_path=out)
    assert os.path.exists(out)
    with open(out, encoding="utf-8") as f:
        assert f.read() == md