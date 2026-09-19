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


def test_enabled_sync_with_missing_private_sources_stays_available(monkeypatch, tmp_path):
    from elise_memory.knowledge import KnowledgeStore

    monkeypatch.setenv("ELISE_MEMORY_SYNC_ENABLED", "true")
    monkeypatch.setenv("ELISE_MEMORY_GOOGLE_CREDENTIALS", "/config/google-service-account.json")
    for name in (
        "ELISE_MEMORY_SHEET_HOME_ASSISTANT_ID",
        "ELISE_MEMORY_SHEET_INDEX_ID",
        "ELISE_MEMORY_SHEET_AUTOMATIONS_ID",
        "ELISE_MEMORY_SHEET_SCRIPTS_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    store=KnowledgeStore(tmp_path/"m.sqlite3"); store.initialize()
    assert runtime.build_scheduler(store) is None
    health=store.sync_health()
    assert health["last_sync"]["status"]=="failed"
    assert "canonical_sources_required" in health["last_sync"]["error"]


def test_sync_failure_is_recorded_without_touching_canonical_data(monkeypatch, tmp_path):
    from elise_memory.knowledge import KnowledgeStore
    store=KnowledgeStore(tmp_path/"m.sqlite3"); store.initialize()
    store.record_sync_failure("RuntimeError: google unavailable")
    health=store.sync_health()
    assert health["last_sync"]["status"]=="failed"
    assert "google unavailable" in health["last_sync"]["error"]
    assert health["canonical_records"]==0
