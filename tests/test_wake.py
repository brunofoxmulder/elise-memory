from datetime import datetime

import pytest

from elise_memory.ha_reader import HAState
from elise_memory.wake import WakeStateError, read_wake_time


class Reader:
    def __init__(self, state):
        self.state = state

    def get_state(self, entity_id):
        return HAState(
            entity_id=entity_id,
            state=self.state,
            last_changed=datetime.fromisoformat("2026-09-18T07:00:00+02:00"),
            attributes={},
        )


def test_wake_timestamp_is_read_from_configured_entity():
    value = read_wake_time(Reader("2026-09-18T07:15:00+02:00"), "sensor.wake")
    assert value == datetime.fromisoformat("2026-09-18T07:15:00+02:00")


def test_invalid_wake_timestamp_is_rejected():
    with pytest.raises(WakeStateError):
        read_wake_time(Reader("on"), "sensor.wake")
