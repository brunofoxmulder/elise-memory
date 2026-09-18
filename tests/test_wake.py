from datetime import datetime

import pytest

from elise_memory.ha_reader import HAHistoryState, HAState
from elise_memory.wake import WAKE_SLEEP_ENTITY_ID, WakeStateError, read_wake_sleep


class Reader:
    def __init__(self, state, history):
        self.state = state
        self.history = history

    def get_state(self, entity_id):
        assert entity_id == WAKE_SLEEP_ENTITY_ID
        return HAState(entity_id, self.state, datetime.fromisoformat("2026-09-18T07:00:00+02:00"), {})

    def get_history(self, entity_id, start):
        assert entity_id == WAKE_SLEEP_ENTITY_ID
        return self.history


def hs(state, when):
    return HAHistoryState(state, datetime.fromisoformat(when))


def test_on_means_awake_since_last_off_to_on():
    reader = Reader("on", [hs("off","2026-09-18T00:00:00+02:00"), hs("on","2026-09-18T07:15:00+02:00")])
    result = read_wake_sleep(reader, now=datetime.fromisoformat("2026-09-18T08:00:00+02:00"))
    assert result.awake is True
    assert result.since == datetime.fromisoformat("2026-09-18T07:15:00+02:00")


def test_off_means_sleep_since_last_on_to_off():
    reader = Reader("off", [hs("on","2026-09-18T07:15:00+02:00"), hs("off","2026-09-18T23:30:00+02:00")])
    result = read_wake_sleep(reader, now=datetime.fromisoformat("2026-09-18T23:45:00+02:00"))
    assert result.awake is False
    assert result.since == datetime.fromisoformat("2026-09-18T23:30:00+02:00")


def test_unknown_intermediate_state_does_not_create_transition():
    reader = Reader("on", [hs("off","2026-09-18T00:00:00+02:00"), hs("unavailable","2026-09-18T07:14:00+02:00"), hs("on","2026-09-18T07:15:00+02:00")])
    assert read_wake_sleep(reader, now=datetime.fromisoformat("2026-09-18T08:00:00+02:00")).awake is True


def test_unavailable_current_state_is_rejected():
    with pytest.raises(WakeStateError):
        read_wake_sleep(Reader("unavailable", []), now=datetime.fromisoformat("2026-09-18T08:00:00+02:00"))
