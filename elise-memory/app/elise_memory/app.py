"""HTTP API for Élise Memory."""

import os

from fastapi import FastAPI, HTTPException

from .context import ContextRequest, ContextResult, build_context
from .models import MemoryCreate, MemoryKind, MemoryRecord
from .opening_context import OpeningContext, OpeningContextRequest, build_opening_context
from .ha_reader import HomeAssistantReader
from .session import GreetingCommit, ConversationOpening, commit_greeting, conversation_opening
from .store import MemoryStore
from .knowledge import KnowledgeStore
from .runtime import build_scheduler

DB_PATH = os.getenv("ELISE_MEMORY_DB", "/data/elise_memory.sqlite3")
store = MemoryStore(DB_PATH)
knowledge_store = KnowledgeStore(DB_PATH)
scheduler = None

app = FastAPI(title="Élise Memory", version="0.1.0-dev.8")


@app.on_event("startup")
def startup() -> None:
    global scheduler
    store.initialize()
    knowledge_store.initialize()
    scheduler = build_scheduler(knowledge_store)
    if scheduler:
        scheduler.start()


@app.on_event("shutdown")
def shutdown() -> None:
    if scheduler:
        scheduler.stop()


@app.get("/v1/sync/health")
def sync_health() -> dict:
    return knowledge_store.sync_health()


@app.get("/v1/knowledge/search")
def search_knowledge(q: str, limit: int = 8) -> dict:
    """Return compact local house knowledge and matching relations."""
    if not q.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")
    return knowledge_store.search(q, limit=limit)


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


@app.post("/v1/conversation/open", response_model=OpeningContext)
def open_conversation(request: OpeningContextRequest) -> OpeningContext:
    """Return persistent memory and temporal opening state in one payload."""
    return build_opening_context(store, HomeAssistantReader(), request)


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
