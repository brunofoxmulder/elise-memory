import pytest

from elise_memory import runtime


def test_runtime_sync_is_inert_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("ELISE_MEMORY_SYNC_ENABLED", raising=False)
    assert runtime.build_scheduler(None) is None


def test_enabled_sync_requires_credentials(monkeypatch):
    monkeypatch.setenv("ELISE_MEMORY_SYNC_ENABLED","true")
    monkeypatch.delenv("ELISE_MEMORY_GOOGLE_CREDENTIALS", raising=False)
    with pytest.raises(RuntimeError, match="google_credentials_required"):
        runtime.build_scheduler(None)
