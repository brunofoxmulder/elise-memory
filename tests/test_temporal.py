from datetime import datetime, timedelta, timezone

from elise_memory.models import MemoryCreate
from elise_memory.store import MemoryStore


def test_expired_temporal_memory_is_not_active(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    now = datetime.now(timezone.utc)

    store.add(
        MemoryCreate(
            kind="temporal",
            key="daily_greeting",
            value="already greeted",
            source="test",
            valid_from=now - timedelta(hours=2),
            valid_until=now - timedelta(hours=1),
        )
    )

    assert store.find("temporal", "daily_greeting", at=now) == []
    assert len(store.find("temporal", "daily_greeting", at=now, include_inactive=True)) == 1


def test_current_temporal_memory_is_active(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    now = datetime.now(timezone.utc)

    store.add(
        MemoryCreate(
            kind="temporal",
            key="daily_greeting",
            value="already greeted",
            source="test",
            valid_from=now - timedelta(minutes=1),
            valid_until=now + timedelta(hours=1),
        )
    )

    assert len(store.find("temporal", "daily_greeting", at=now)) == 1
