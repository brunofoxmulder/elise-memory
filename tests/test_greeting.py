from datetime import datetime, timedelta, timezone

from elise_memory.store import MemoryStore
from elise_memory.temporal import first_conversation_since_wake, record_greeting


def test_first_conversation_since_wake_greets_once(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    now = datetime.now(timezone.utc)
    wake_at = now - timedelta(hours=1)

    first = first_conversation_since_wake(store, wake_at=wake_at, now=now)
    assert first.should_greet is True
    assert first.reason == "first_conversation_since_wake"

    record_greeting(store, wake_at=wake_at)

    second = first_conversation_since_wake(
        store, wake_at=wake_at, now=now + timedelta(minutes=1)
    )
    assert second.should_greet is False
    assert second.reason == "already_greeted_since_wake"


def test_old_greeting_does_not_block_new_wake_period(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    now = datetime.now(timezone.utc)
    old_wake = now - timedelta(hours=12)
    record_greeting(store, wake_at=old_wake)

    new_wake = now + timedelta(seconds=1)
    later = now + timedelta(minutes=5)
    decision = first_conversation_since_wake(store, wake_at=new_wake, now=later)
    assert decision.should_greet is True


def test_future_wake_time_is_rejected(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    now = datetime.now(timezone.utc)
    decision = first_conversation_since_wake(
        store, wake_at=now + timedelta(minutes=5), now=now
    )
    assert decision.should_greet is False
    assert decision.reason == "wake_time_is_in_future"
