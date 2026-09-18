"""Maison Cognitive canonical wake/sleep reference."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from .ha_reader import HomeAssistantReader

WAKE_SLEEP_ENTITY_ID = "switch.prise_de_comptage_prise_1"

class WakeStateError(RuntimeError):
    pass

@dataclass(frozen=True)
class WakeSleepState:
    awake: bool
    since: datetime
    source_entity_id: str = WAKE_SLEEP_ENTITY_ID

def read_wake_sleep(reader: HomeAssistantReader, *, now=None, lookback=timedelta(days=2)):
    now = now or datetime.now(timezone.utc)
    current = reader.get_state(WAKE_SLEEP_ENTITY_ID)
    if current.state not in {"on", "off"}:
        raise WakeStateError(f"unsupported state: {current.state}")
    history = reader.get_history(WAKE_SLEEP_ENTITY_ID, now - lookback)
    target = current.state
    previous = None
    transition_at = None
    for item in history:
        if item.state not in {"on", "off"}:
            continue
        if previous is not None and item.state == target and previous != target:
            transition_at = item.last_changed
        previous = item.state
    if transition_at is None:
        raise WakeStateError(f"no transition to {target} found")
    return WakeSleepState(awake=target == "on", since=transition_at)
