"""Deterministic conversation-session contract for Élise Memory."""

from datetime import datetime, timezone

from pydantic import BaseModel

from .ha_reader import HomeAssistantReader
from .store import MemoryStore
from .temporal import first_conversation_since_wake, record_greeting
from .wake import WakeSleepState, read_wake_sleep


class ConversationOpening(BaseModel):
    awake: bool
    cycle_since: datetime
    should_greet: bool
    greeting_reason: str
    source_entity_id: str


class GreetingCommit(BaseModel):
    wake_at: datetime


def conversation_opening(
    store: MemoryStore,
    reader: HomeAssistantReader,
    *,
    now: datetime | None = None,
) -> ConversationOpening:
    """Build opening context without consuming the greeting."""
    now = now or datetime.now(timezone.utc)
    cycle: WakeSleepState = read_wake_sleep(reader, now=now)

    if not cycle.awake:
        return ConversationOpening(
            awake=False,
            cycle_since=cycle.since,
            should_greet=False,
            greeting_reason="sleep_cycle",
            source_entity_id=cycle.source_entity_id,
        )

    decision = first_conversation_since_wake(store, wake_at=cycle.since, now=now)
    return ConversationOpening(
        awake=True,
        cycle_since=cycle.since,
        should_greet=decision.should_greet,
        greeting_reason=decision.reason,
        source_entity_id=cycle.source_entity_id,
    )


def commit_greeting(store: MemoryStore, reader: HomeAssistantReader, *, wake_at: datetime, now: datetime | None = None) -> None:
    """Commit only after the caller confirms the greeting was actually emitted.

    The current authoritative HA cycle must still be the same awake cycle.
    """
    now = now or datetime.now(timezone.utc)
    cycle = read_wake_sleep(reader, now=now)
    if not cycle.awake or cycle.since != wake_at:
        raise ValueError("wake_cycle_changed")
    decision = first_conversation_since_wake(store, wake_at=wake_at, now=now)
    if decision.should_greet:
        record_greeting(store, wake_at=wake_at)
