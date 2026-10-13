import os

import pytest

from conftest import _TEST_VIDEO
from video_grounding.frames import FrameExtractor
from video_grounding.schemas import GroundedAction


@pytest.fixture
def extractor():
    return FrameExtractor(
        ffmpeg_bin=os.environ.get("FFMPEG_BIN", "ffmpeg"),
        ffprobe_bin=os.environ.get("FFPROBE_BIN", "ffprobe"),
        max_width=640,
    )


def test_probe_duration(extractor):
    duration = extractor.probe_duration(_TEST_VIDEO)
    assert duration > 0


def test_extract_single_frame(extractor, tmp_path):
    out = os.path.join(str(tmp_path), "frame.jpg")
    extractor.extract_frame(_TEST_VIDEO, 5.0, out)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0
    # Debe ser un JPEG valido (magic bytes FF D8)
    with open(out, "rb") as f:
        assert f.read(2) == b"\xff\xd8"


def test_extract_frames_multiple(extractor, tmp_path):
    actions = [
        GroundedAction(
            index=i,
            timestamp=f"00:{i:02d}",
            timestamp_seconds=float(i),
            title=f"P{i}",
            description="d",
        )
        for i in (1, 3, 5)
    ]
    frames = extractor.extract_frames(_TEST_VIDEO, actions, str(tmp_path))
    assert len(frames) == 3
    for f in frames:
        assert os.path.exists(f.image_path)


def test_extract_frame_missing_video(extractor, tmp_path):
    with pytest.raises(FileNotFoundError):
        extractor.extract_frame("/no/existe/video.mp4", 1.0, os.path.join(str(tmp_path), "x.jpg"))