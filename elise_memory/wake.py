"""Maison Cognitive wake/sleep reference.

Canonical reference:
- switch.prise_de_comptage_prise_1 off -> on: wake / awake cycle starts
- switch.prise_de_comptage_prise_1 on -> off: sleep / night cycle starts

The switch state is authoritative over clock-based assumptions.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .ha_reader import HAHistoryState, HomeAssistantReader

WAKE_SLEEP_ENTITY_ID = "switch.prise_de_comptage_prise_1"


class WakeStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class WakeSleepState:
    awake: bool
    since: datetime
    source_entity_id: str = WAKE_SLEEP_ENTITY_ID


def derive_wake_sleep(
    current_state: str,
    history: list[HAHistoryState],
) -> WakeSleepState:
    if current_state not in {"on", "off"}:
        raise WakeStateError(f"unsupported wake/sleep state: {current_state}")

    target = current_state
    previous = None
    transition_at = None
    for item in history:
        if item.state not in {"on", "off"}:
            continue
        if previous is not None and item.state == target and previous != target:
            transition_at = item.last_changed
        previous = item.state

    if transition_at is None:
        raise WakeStateError(f"no transition to {target} found in history")

    return WakeSleepState(awake=(target == "on"), since=transition_at)


def read_wake_sleep(
    reader: HomeAssistantReader,
    *,
    now: datetime | None = None,
    lookback: timedelta = timedelta(days=2),
) -> WakeSleepState:
    now = now or datetime.now(timezone.utc)
    current = reader.get_state(WAKE_SLEEP_ENTITY_ID)
    history = reader.get_history(WAKE_SLEEP_ENTITY_ID, now - lookback)
    return derive_wake_sleep(current.state, history)
