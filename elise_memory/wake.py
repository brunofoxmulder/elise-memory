"""Wake-time derivation from an explicitly configured HA entity."""

from datetime import datetime

from .ha_reader import HomeAssistantReader


class WakeStateError(RuntimeError):
    pass


def read_wake_time(reader: HomeAssistantReader, entity_id: str) -> datetime:
    """Read wake time without making any Home Assistant change.

    Contract for dev.4: the configured entity's state must itself be an ISO-8601
    timestamp. No entity is guessed or discovered automatically.
    """
    state = reader.get_state(entity_id)
    try:
        return datetime.fromisoformat(state.state)
    except ValueError as exc:
        raise WakeStateError(
            f"{entity_id} does not contain an ISO-8601 wake timestamp"
        ) from exc
