import pytest

from video_grounding.grounder import GeminiVideoGrounder


class _FakeResponse:
    def __init__(self, text):
        self.text = text


def test_parse_response_json():
    resp = _FakeResponse(
        '{"title": "T", "summary": "S", "actions": ['
        '{"index": 1, "timestamp": "00:10", "timestamp_seconds": 10.0, '
        '"title": "A", "description": "D"}]}'
    )
    out = GeminiVideoGrounder._parse_response(resp)
    assert out.title == "T"
    assert out.actions[0].timestamp_seconds == 10.0


def test_parse_response_fenced():
    resp = _FakeResponse(
        '```json\n{"title": "T", "summary": "S", "actions": []}\n```'
    )
    out = GeminiVideoGrounder._parse_response(resp)
    assert out.actions == []


def test_parse_response_invalid():
    with pytest.raises(RuntimeError):
        GeminiVideoGrounder._parse_response(_FakeResponse("no es json"))


def test_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    g = GeminiVideoGrounder(api_key=None)
    with pytest.raises(RuntimeError):
        _ = g.client  # sin key (o sin SDK) debe fallar de forma controlada


def test_resolve_api_key_fallback(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "abc123")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert GeminiVideoGrounder._resolve_api_key() == "abc123"