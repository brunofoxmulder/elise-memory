"""Deterministic relevance selection for conversation memory.

Selection is explicit and key-based. No LLM, embedding, fuzzy search, or implicit
profile sweep is performed by Élise Memory.
"""

from pydantic import BaseModel, Field

from .context import ContextKey


class ConversationMemoryRequest(BaseModel):
    """Memory keys a conversation client says are relevant to the current turn."""

    house_keys: list[str] = Field(default_factory=list, max_length=50)
    temporal_keys: list[str] = Field(default_factory=list, max_length=50)


def context_keys_for_conversation(request: ConversationMemoryRequest) -> list[ContextKey]:
    """Return stable, deduplicated context keys while preserving caller order."""
    result: list[ContextKey] = []
    seen: set[tuple[str, str]] = set()

    for kind, keys in (("house", request.house_keys), ("temporal", request.temporal_keys)):
        for key in keys:
            clean = key.strip()
            if not clean:
                continue
            marker = (kind, clean)
            if marker in seen:
                continue
            seen.add(marker)
            result.append(ContextKey(kind=kind, key=clean))

    return result
