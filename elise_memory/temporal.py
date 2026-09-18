"""Deterministic temporal conversation rules.

These rules produce conversation context only. They never trigger Home Assistant
services or automations.
"""

from datetime import datetime, timezone

from pydantic import BaseModel

from .models import MemoryCreate
from .store import MemoryStore

SESSION_GREETING_KEY = "greeting_since_wake"


class GreetingDecision(BaseModel):
    should_greet: bool
    reason: str


def first_conversation_since_wake(
    store: MemoryStore,
    *,
    wake_at: datetime,
    now: datetime | None = None,
) -> GreetingDecision:
    """Return True only once for the current wake period.

    A prior greeting is relevant only when it was recorded at or after wake_at.
    The caller explicitly records the greeting after it has actually been used.
    """
    now = now or datetime.now(timezone.utc)
    if wake_at > now:
        return GreetingDecision(should_greet=False, reason="wake_time_is_in_future")

    previous = store.find("temporal", SESSION_GREETING_KEY, at=now, include_inactive=True)
    already_greeted = any(record.created_at >= wake_at for record in previous)
    if already_greeted:
        return GreetingDecision(should_greet=False, reason="already_greeted_since_wake")
    return GreetingDecision(should_greet=True, reason="first_conversation_since_wake")


def record_greeting(store: MemoryStore, *, wake_at: datetime) -> None:
    """Record that the greeting was actually emitted for this wake period."""
    store.add(
        MemoryCreate(
            kind="temporal",
            key=SESSION_GREETING_KEY,
            value="greeting_emitted",
            source="elise-memory:temporal-rule",
            valid_from=wake_at,
        )
    )
