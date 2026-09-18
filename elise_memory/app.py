"""HTTP API for Élise Memory."""

import os

from fastapi import FastAPI, HTTPException

from .models import MemoryCreate, MemoryKind, MemoryRecord
from .store import MemoryStore

DB_PATH = os.getenv("ELISE_MEMORY_DB", "/data/elise_memory.sqlite3")
store = MemoryStore(DB_PATH)

app = FastAPI(title="Élise Memory", version="0.1.0-dev.1")


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
def get_memories(kind: MemoryKind, key: str) -> list[MemoryRecord]:
    records = store.find(kind, key)
    if not records:
        raise HTTPException(status_code=404, detail="memory not found")
    return records
