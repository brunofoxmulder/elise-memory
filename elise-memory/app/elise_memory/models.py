"""Public data contracts for Élise Memory."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MemoryKind = Literal["house", "temporal"]


class MemoryCreate(BaseModel):
    kind: MemoryKind
    key: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=10_000)
    source: str = Field(min_length=1, max_length=500)
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class MemoryRecord(MemoryCreate):
    id: int
    created_at: datetime
