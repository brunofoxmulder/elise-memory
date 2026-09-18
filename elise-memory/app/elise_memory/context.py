"""Deterministic context assembly.

No LLM is involved: callers request explicit keys and receive bounded,
provenance-preserving memory records.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from .models import MemoryKind, MemoryRecord
from .store import MemoryStore


class ContextKey(BaseModel):
    kind: MemoryKind
    key: str = Field(min_length=1, max_length=200)


class ContextRequest(BaseModel):
    keys: list[ContextKey] = Field(min_length=1, max_length=50)
    at: datetime | None = None
    max_per_key: int = Field(default=3, ge=1, le=20)


class ContextResult(BaseModel):
    records: list[MemoryRecord]
    missing: list[ContextKey]


def build_context(store: MemoryStore, request: ContextRequest) -> ContextResult:
    records: list[MemoryRecord] = []
    missing: list[ContextKey] = []

    for wanted in request.keys:
        found = store.find(wanted.kind, wanted.key, at=request.at)
        if not found:
            missing.append(wanted)
            continue
        records.extend(found[: request.max_per_key])

    return ContextResult(records=records, missing=missing)
