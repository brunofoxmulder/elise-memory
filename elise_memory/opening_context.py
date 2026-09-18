"""Unified deterministic conversation opening context for Élise Memory."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .context import ContextKey, ContextRequest, ContextResult, build_context
from .ha_reader import HomeAssistantReader
from .session import ConversationOpening, conversation_opening
from .store import MemoryStore


class OpeningContextRequest(BaseModel):
    """Explicit memory keys requested for a new conversation."""

    keys: list[ContextKey] = Field(default_factory=list, max_length=50)
    at: datetime | None = None
    max_per_key: int = Field(default=3, ge=1, le=20)


class OpeningContext(BaseModel):
    """Single deterministic payload consumed by a conversation client."""

    session: ConversationOpening
    memory: ContextResult


def build_opening_context(
    store: MemoryStore,
    reader: HomeAssistantReader,
    request: OpeningContextRequest,
    *,
    now: datetime | None = None,
) -> OpeningContext:
    """Combine temporal session state and explicitly requested persistent memory.

    This is read-only with respect to Home Assistant. Opening the context never
    consumes the greeting; the caller must separately confirm an emitted
    greeting through the existing commit contract.
    """
    now = now or request.at or datetime.now(timezone.utc)
    session = conversation_opening(store, reader, now=now)

    if not request.keys:
        memory = ContextResult(records=[], missing=[])
    else:
        memory = build_context(
            store,
            ContextRequest(
                keys=request.keys,
                at=request.at or now,
                max_per_key=request.max_per_key,
            ),
        )

    return OpeningContext(session=session, memory=memory)
