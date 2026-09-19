"""Explicitly confirmed conversation-memory capture.

The voice-facing MCP tool is read-only. This module is a separate write contract
for a future trusted caller; it never stores raw transcripts or inferred facts.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .models import MemoryCreate, MemoryRecord
from .store import MemoryStore

ConversationCategory = Literal[
    "preference",
    "personal_fact",
    "household_context",
    "commitment",
]


class ConversationMemoryCapture(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=200)
    turn_id: str = Field(min_length=1, max_length=200)
    category: ConversationCategory
    subject: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=1000)
    user_confirmed: bool

    @model_validator(mode="after")
    def require_explicit_confirmation(self) -> "ConversationMemoryCapture":
        if not self.user_confirmed:
            raise ValueError("conversation memory requires explicit user confirmation")
        return self


def capture_conversation_memory(
    store: MemoryStore,
    capture: ConversationMemoryCapture,
) -> MemoryRecord:
    """Persist one confirmed summary with turn-level provenance."""
    return store.add(
        MemoryCreate(
            kind="conversation",
            key=f"{capture.category}:{capture.subject.strip()}",
            value=capture.value.strip(),
            source=(
                f"conversation:{capture.conversation_id}:"
                f"turn:{capture.turn_id}:user_confirmed"
            ),
        )
    )
