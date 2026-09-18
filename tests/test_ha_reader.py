import io
import json

from elise_memory.ha_reader import HomeAssistantReader


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_reader_uses_get_only(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["method"] = request.get_method()
        captured["url"] = request.full_url
        payload = {
            "entity_id": "sensor.test_wake",
            "state": "2026-09-18T07:00:00+02:00",
            "last_changed": "2026-09-18T07:00:00+02:00",
            "attributes": {},
        }
        return FakeResponse(json.dumps(payload).encode())

    monkeypatch.setattr("elise_memory.ha_reader.urlopen", fake_urlopen)
    reader = HomeAssistantReader("http://homeassistant.local:8123", "secret")
    state = reader.get_state("sensor.test_wake")

    assert captured["method"] == "GET"
    assert captured["url"].endswith("/api/states/sensor.test_wake")
    assert state.entity_id == "sensor.test_wake"


def test_default_reader_uses_supervisor_token(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "secret")
    reader = HomeAssistantReader()
    assert reader.base_url == "http://supervisor/core"
    assert reader.token == "secret"


def test_default_reader_requires_supervisor_token(monkeypatch):
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    import pytest
    with pytest.raises(RuntimeError, match="SUPERVISOR_TOKEN"):
        HomeAssistantReader()
