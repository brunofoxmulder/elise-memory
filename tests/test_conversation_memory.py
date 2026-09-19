import pytest
from pydantic import ValidationError

from elise_memory.conversation_memory import (
    ConversationMemoryCapture,
    capture_conversation_memory,
)
from elise_memory.store import MemoryStore


def test_capture_requires_explicit_user_confirmation():
    with pytest.raises(ValidationError, match="explicit user confirmation"):
        ConversationMemoryCapture(
            conversation_id="conversation-1",
            turn_id="turn-1",
            category="preference",
            subject="réponses",
            value="Bruno préfère des réponses courtes",
            user_confirmed=False,
        )


def test_capture_stores_summary_with_turn_provenance(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    capture = ConversationMemoryCapture(
        conversation_id="conversation-1",
        turn_id="turn-7",
        category="preference",
        subject="réponses",
        value="Bruno préfère des réponses courtes",
        user_confirmed=True,
    )

    record = capture_conversation_memory(store, capture)

    assert record.kind == "conversation"
    assert record.key == "preference:réponses"
    assert record.value == "Bruno préfère des réponses courtes"
    assert record.source == (
        "conversation:conversation-1:turn:turn-7:user_confirmed"
    )
