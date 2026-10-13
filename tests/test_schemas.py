import pytest

from video_grounding.schemas import (
    GroundedAction,
    GroundingOutput,
    format_timestamp,
    parse_timestamp,
)


def test_parse_timestamp_mmss():
    assert parse_timestamp("00:12") == 12.0
    assert parse_timestamp("01:23") == 83.0
    assert parse_timestamp("1:05") == 65.0


def test_parse_timestamp_hhmmss():
    assert parse_timestamp("01:02:03") == 3723.0


def test_parse_timestamp_seconds_decimal():
    assert parse_timestamp("00:30.5") == 30.5


def test_parse_timestamp_invalid():
    with pytest.raises(ValueError):
        parse_timestamp("nope")


def test_format_timestamp():
    assert format_timestamp(12.0) == "00:12"
    assert format_timestamp(83.0) == "01:23"
    assert format_timestamp(3723.0) == "01:02:03"


def test_grounding_output_no_seconds_fills_from_timestamp():
    out = GroundingOutput.model_validate(
        {
            "title": "T",
            "summary": "S",
            "actions": [
                {"index": 1, "timestamp": "00:15", "title": "A", "description": "D"}
            ],
        }
    )
    assert out.actions[0].timestamp_seconds == 15.0


def test_grounded_action_rejects_bad_type():
    with pytest.raises(Exception):
        GroundedAction(
            index=1,
            timestamp="00:10",
            timestamp_seconds=10.0,
            action_type="no-existe",  # type: ignore[arg-type]
            title="T",
            description="D",
        )