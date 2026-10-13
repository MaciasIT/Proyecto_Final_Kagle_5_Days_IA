import os

from conftest import _TEST_VIDEO
from video_grounding.frames import FrameExtractor
from video_grounding.mock import MockVideoGrounder
from video_grounding.pipeline import VideoGroundingPipeline


def _fe():
    return FrameExtractor(
        ffmpeg_bin=os.environ.get("FFMPEG_BIN", "ffmpeg"),
        ffprobe_bin=os.environ.get("FFPROBE_BIN", "ffprobe"),
        max_width=480,
    )


def test_pipeline_mock_end_to_end(tmp_path):
    output = os.path.join(str(tmp_path), "doc.md")
    pipeline = VideoGroundingPipeline(
        grounder=MockVideoGrounder(actions=4, frame_extractor=_fe()),
        frame_extractor=_fe(),
        image_mode="base64",
    )
    result = pipeline.run(_TEST_VIDEO, output_path=output)

    assert os.path.exists(output)
    assert result.duration_seconds > 0
    assert len(result.actions) == 4
    assert len(result.frames) == 4

    with open(output, encoding="utf-8") as f:
        md = f.read()

    assert "Procedimiento" in md
    assert md.count("![Fotograma") == 4
    assert "data:image/jpeg;base64," in md


def test_pipeline_file_mode(tmp_path):
    output = os.path.join(str(tmp_path), "doc.md")
    pipeline = VideoGroundingPipeline(
        grounder=MockVideoGrounder(actions=3, frame_extractor=_fe()),
        frame_extractor=_fe(),
        image_mode="file",
    )
    pipeline.run(_TEST_VIDEO, output_path=output)

    assets = os.path.join(str(tmp_path), "assets")
    assert os.path.isdir(assets)
    assert len(os.listdir(assets)) == 3

    with open(output, encoding="utf-8") as f:
        assert "data:" not in f.read()


def test_pipeline_missing_video(tmp_path):
    pipeline = VideoGroundingPipeline(grounder=MockVideoGrounder())
    try:
        pipeline.run("/no/existe.mp4")
    except FileNotFoundError:
        return
    raise AssertionError("deberia lanzar FileNotFoundError")