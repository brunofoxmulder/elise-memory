from datetime import datetime

import pytest

from elise_memory.ha_reader import HAHistoryState, HAState
from elise_memory.session import commit_greeting, conversation_opening
from elise_memory.store import MemoryStore
from elise_memory.wake import WAKE_SLEEP_ENTITY_ID


class Reader:
    def __init__(self, state, history):
        self.state = state
        self.history = history

    def get_state(self, entity_id):
        return HAState(entity_id, self.state, self.history[-1].last_changed, {})

    def get_history(self, entity_id, start):
        return self.history


def hs(state, when):
    return HAHistoryState(state, datetime.fromisoformat(when))


def test_opening_does_not_consume_greeting(tmp_path):
    store = MemoryStore(tmp_path / "m.sqlite3"); store.initialize()
    wake = datetime.fromisoformat("2026-09-18T07:15:00+02:00")
    reader = Reader("on", [hs("off","2026-09-18T00:00:00+02:00"), hs("on",wake.isoformat())])
    now = datetime.fromisoformat("2026-09-18T08:00:00+02:00")
    assert conversation_opening(store, reader, now=now).should_greet is True
    assert conversation_opening(store, reader, now=now).should_greet is True


def test_commit_consumes_greeting_only_after_confirmation(tmp_path):
    store = MemoryStore(tmp_path / "m.sqlite3"); store.initialize()
    wake = datetime.fromisoformat("2026-09-18T07:15:00+02:00")
    reader = Reader("on", [hs("off","2026-09-18T00:00:00+02:00"), hs("on",wake.isoformat())])
    now = datetime.fromisoformat("2026-09-18T08:00:00+02:00")
    commit_greeting(store, reader, wake_at=wake, now=now)
    assert conversation_opening(store, reader, now=now).should_greet is False


def test_commit_rejects_stale_wake_cycle(tmp_path):
    store = MemoryStore(tmp_path / "m.sqlite3"); store.initialize()
    old_wake = datetime.fromisoformat("2026-09-18T07:15:00+02:00")
    new_wake = datetime.fromisoformat("2026-09-19T07:20:00+02:00")
    reader = Reader("on", [hs("off","2026-09-19T00:00:00+02:00"), hs("on",new_wake.isoformat())])
    with pytest.raises(ValueError, match="wake_cycle_changed"):
        commit_greeting(store, reader, wake_at=old_wake, now=datetime.fromisoformat("2026-09-19T08:00:00+02:00"))


def test_sleep_cycle_never_requests_greeting(tmp_path):
    store = MemoryStore(tmp_path / "m.sqlite3"); store.initialize()
    reader = Reader("off", [hs("on","2026-09-18T07:15:00+02:00"), hs("off","2026-09-18T23:30:00+02:00")])
    result = conversation_opening(store, reader, now=datetime.fromisoformat("2026-09-18T23:45:00+02:00"))
    assert result.awake is False
    assert result.should_greet is False
