from datetime import datetime

from elise_memory.ha_reader import HAHistoryState, HAState
from elise_memory.models import MemoryCreate
from elise_memory.opening_context import OpeningContextRequest, build_opening_context
from elise_memory.context import ContextKey
from elise_memory.store import MemoryStore


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


def test_opening_context_combines_memory_and_wake_cycle_without_consuming_greeting(tmp_path):
    store = MemoryStore(tmp_path / "m.sqlite3")
    store.initialize()
    store.add(MemoryCreate(kind="house", key="preferred_name", value="Bruno", source="project"))

    wake = datetime.fromisoformat("2026-09-18T07:15:00+02:00")
    now = datetime.fromisoformat("2026-09-18T08:00:00+02:00")
    reader = Reader("on", [hs("off", "2026-09-18T00:00:00+02:00"), hs("on", wake.isoformat())])
    request = OpeningContextRequest(keys=[ContextKey(kind="house", key="preferred_name")], at=now)

    first = build_opening_context(store, reader, request, now=now)
    second = build_opening_context(store, reader, request, now=now)

    assert first.session.awake is True
    assert first.session.should_greet is True
    assert first.memory.records[0].value == "Bruno"
    assert second.session.should_greet is True


def test_opening_context_can_return_temporal_state_without_memory_keys(tmp_path):
    store = MemoryStore(tmp_path / "m.sqlite3")
    store.initialize()
    now = datetime.fromisoformat("2026-09-18T23:45:00+02:00")
    reader = Reader("off", [hs("on", "2026-09-18T07:15:00+02:00"), hs("off", "2026-09-18T23:30:00+02:00")])

    result = build_opening_context(store, reader, OpeningContextRequest(at=now), now=now)

    assert result.session.awake is False
    assert result.session.should_greet is False
    assert result.memory.records == []
    assert result.memory.missing == []
