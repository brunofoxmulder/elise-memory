import pytest

from elise_memory import runtime


def test_runtime_sync_is_inert_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("ELISE_MEMORY_SYNC_ENABLED", raising=False)
    assert runtime.build_scheduler(None) is None


def test_enabled_sync_with_missing_credentials_does_not_crash(monkeypatch, tmp_path):
    from elise_memory.knowledge import KnowledgeStore

    monkeypatch.setenv("ELISE_MEMORY_SYNC_ENABLED", "true")
    monkeypatch.setenv("ELISE_MEMORY_GOOGLE_CREDENTIALS", "/missing/google-service-account.json")
    store=KnowledgeStore(tmp_path/"m.sqlite3"); store.initialize()

    assert runtime.build_scheduler(store) is None
    health=store.sync_health()
    assert health["last_sync"]["status"]=="failed"
    assert health["last_sync"]["error"]=="RuntimeError: google_credentials_missing"


def test_enabled_sync_with_missing_private_sources_stays_available(monkeypatch, tmp_path):
    from elise_memory.knowledge import KnowledgeStore

    credentials = tmp_path/"google-service-account.json"
    credentials.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("ELISE_MEMORY_SYNC_ENABLED", "true")
    monkeypatch.setenv("ELISE_MEMORY_GOOGLE_CREDENTIALS", str(credentials))
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


def test_enabled_sync_with_invalid_credentials_does_not_crash(monkeypatch, tmp_path):
    from elise_memory.knowledge import KnowledgeStore

    credentials = tmp_path/"google-service-account.json"
    credentials.write_text("not-json", encoding="utf-8")
    monkeypatch.setenv("ELISE_MEMORY_SYNC_ENABLED", "true")
    monkeypatch.setenv("ELISE_MEMORY_GOOGLE_CREDENTIALS", str(credentials))
    monkeypatch.setenv("ELISE_MEMORY_SHEET_HOME_ASSISTANT_ID", "ha")
    monkeypatch.setenv("ELISE_MEMORY_SHEET_INDEX_ID", "index")
    monkeypatch.setenv("ELISE_MEMORY_SHEET_AUTOMATIONS_ID", "automations")
    monkeypatch.setenv("ELISE_MEMORY_SHEET_SCRIPTS_ID", "scripts")

    store=KnowledgeStore(tmp_path/"m.sqlite3"); store.initialize()
    assert runtime.build_scheduler(store) is None
    health=store.sync_health()
    assert health["last_sync"]["status"]=="failed"
    assert "google_credentials_invalid_or_unreadable" in health["last_sync"]["error"]


def test_runtime_status_never_exposes_paths_or_source_ids(monkeypatch, tmp_path):
    credentials = tmp_path/"secret.json"
    credentials.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("ELISE_MEMORY_SYNC_ENABLED", "true")
    monkeypatch.setenv("ELISE_MEMORY_GOOGLE_CREDENTIALS", str(credentials))
    monkeypatch.setenv("ELISE_MEMORY_SHEET_HOME_ASSISTANT_ID", "private-ha-id")
    monkeypatch.setenv("ELISE_MEMORY_SHEET_INDEX_ID", "private-index-id")
    monkeypatch.setenv("ELISE_MEMORY_SHEET_AUTOMATIONS_ID", "private-auto-id")
    monkeypatch.setenv("ELISE_MEMORY_SHEET_SCRIPTS_ID", "private-script-id")

    status = runtime.sync_runtime_status()
    assert status == {
        "enabled": True,
        "ready": True,
        "credentials_present": True,
        "sources_configured": True,
    }
    assert "private" not in str(status)
    assert str(credentials) not in str(status)


def test_sync_failure_is_recorded_without_touching_canonical_data(monkeypatch, tmp_path):
    from elise_memory.knowledge import KnowledgeStore
    store=KnowledgeStore(tmp_path/"m.sqlite3"); store.initialize()
    store.record_sync_failure("RuntimeError: google unavailable")
    health=store.sync_health()
    assert health["last_sync"]["status"]=="failed"
    assert "google unavailable" in health["last_sync"]["error"]
    assert health["canonical_records"]==0
