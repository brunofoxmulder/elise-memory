"""HTTP API for Élise Memory."""

import os

from fastapi import FastAPI, HTTPException

from .context import ContextRequest, ContextResult, build_context
from .models import MemoryCreate, MemoryKind, MemoryRecord
from .ha_reader import HomeAssistantReader
from .session import GreetingCommit, ConversationOpening, commit_greeting, conversation_opening
from .store import MemoryStore

DB_PATH = os.getenv("ELISE_MEMORY_DB", "/data/elise_memory.sqlite3")
store = MemoryStore(DB_PATH)

app = FastAPI(title="Élise Memory", version="0.1.0-dev.6")


@app.on_event("startup")
def startup() -> None:
    store.initialize()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "isolated"}


@app.post("/v1/memories", response_model=MemoryRecord, status_code=201)
def create_memory(item: MemoryCreate) -> MemoryRecord:
    return store.add(item)


@app.get("/v1/memories/{kind}/{key}", response_model=list[MemoryRecord])
def get_memories(
    kind: MemoryKind,
    key: str,
    include_inactive: bool = False,
) -> list[MemoryRecord]:
    records = store.find(kind, key, include_inactive=include_inactive)
    if not records:
        raise HTTPException(status_code=404, detail="memory not found")
    return records


@app.post("/v1/context", response_model=ContextResult)
def context(request: ContextRequest) -> ContextResult:
    return build_context(store, request)


@app.get("/v1/session/open", response_model=ConversationOpening)
def open_session() -> ConversationOpening:
    """Return deterministic opening context without consuming the greeting."""
    return conversation_opening(store, HomeAssistantReader())


@app.post("/v1/session/greeting/commit", status_code=204)
def confirm_greeting(item: GreetingCommit) -> None:
    """Record a greeting only after the caller confirms it was emitted."""
    try:
        commit_greeting(store, HomeAssistantReader(), wake_at=item.wake_at)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
