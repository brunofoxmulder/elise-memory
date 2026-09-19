"""HTTP API for Élise Memory."""

from contextlib import asynccontextmanager
import os

from fastapi import Depends, FastAPI, HTTPException
from mcp.server.fastmcp import FastMCP

from .context import ContextRequest, ContextResult, build_context
from .models import MemoryCreate, MemoryKind, MemoryRecord
from .opening_context import OpeningContext, OpeningContextRequest, build_opening_context
from .ha_reader import HomeAssistantReader
from .session import GreetingCommit, ConversationOpening, commit_greeting, conversation_opening
from .store import MemoryStore
from .knowledge import KnowledgeStore
from .sync import synchronize_canonical
from .runtime import build_reader_from_env, build_scheduler, sync_runtime_status
from .resolver import ResolutionResult, resolve_current_entity
from .agent import AgentAnswer, AgentQuery, query_agent_memory
from .security import require_admin, transport_security
from .conversation_memory import (
    ConversationMemoryCapture,
    capture_conversation_memory,
)

DB_PATH = os.getenv("ELISE_MEMORY_DB", "/data/elise_memory.sqlite3")
store = MemoryStore(DB_PATH)
knowledge_store = KnowledgeStore(DB_PATH)
scheduler = None


memory_mcp = FastMCP(
    "Élise Memory",
    instructions=(
        "Mémoire consultative de la maison et des conversations. "
        "Elle n'exécute jamais d'action. Pour toute question causale, suivre "
        "le routage Investigator retourné par l'outil."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    transport_security=transport_security(),
)


@memory_mcp.tool(
    name="consult_elise_memory",
    description=(
        "Consulter la mémoire sourcée de la maison ou des conversations lorsque "
        "la demande est ambiguë ou nécessite du contexte. Cet outil ne commande "
        "aucun appareil. Ne pas l'utiliser pour établir pourquoi un événement a eu lieu."
    ),
    structured_output=True,
)
def consult_elise_memory(query: str) -> AgentAnswer:
    """Expose the bounded advisory query through Home Assistant's MCP client."""
    return query_agent_memory(store, knowledge_store, AgentQuery(query=query))


mcp_http_app = memory_mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start stores, scheduler and the mounted MCP session manager together."""
    global scheduler
    store.initialize()
    knowledge_store.initialize()
    scheduler = build_scheduler(knowledge_store)
    if scheduler:
        scheduler.start()
    async with memory_mcp.session_manager.run():
        yield
    if scheduler:
        scheduler.stop()


app = FastAPI(
    title="Élise Memory",
    version="0.1.0-dev.17",
    lifespan=lifespan,
)


@app.post("/v1/sync/run", dependencies=[Depends(require_admin)])
def run_sync() -> dict:
    """Run one guarded canonical sync on explicit request."""
    try:
        report = synchronize_canonical(knowledge_store, build_reader_from_env())
    except Exception as exc:
        knowledge_store.record_sync_failure(f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=503, detail=f"{type(exc).__name__}: {exc}") from exc
    return {
        "source_rows": report.source_rows,
        "compiled_by_source": report.compiled_by_source,
        "compiled_records": report.compiled_records,
        "changed": report.changed,
        "deactivated": report.deactivated,
        "relations": report.relations,
    }


@app.get("/v1/sync/health")
def sync_health() -> dict:
    health = knowledge_store.sync_health()
    health["runtime"] = sync_runtime_status()
    return health


@app.get("/v1/knowledge/search")
def search_knowledge(q: str, limit: int = 8) -> dict:
    """Return compact local house knowledge and matching relations."""
    if not q.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")
    return knowledge_store.search(q, limit=limit)


@app.post("/v1/agent/query", response_model=AgentAnswer)
def agent_query(request: AgentQuery) -> AgentAnswer:
    """Give the agent bounded context or explicitly route causality elsewhere."""
    return query_agent_memory(store, knowledge_store, request)


@app.get("/health")
def health() -> dict:
    runtime = sync_runtime_status()
    sync_state = "ready" if runtime["ready"] else ("not_ready" if runtime["enabled"] else "disabled")
    return {
        "status": "ok",
        "mode": "isolated",
        "version": "0.1.0-dev.17",
        "sync": sync_state,
    }


@app.post("/v1/memories", response_model=MemoryRecord, status_code=201,
          dependencies=[Depends(require_admin)])
def create_memory(item: MemoryCreate) -> MemoryRecord:
    if item.kind == "conversation":
        raise HTTPException(
            status_code=409,
            detail="use the explicitly confirmed conversation-memory endpoint",
        )
    return store.add(item)


@app.post(
    "/v1/conversation/memories",
    dependencies=[Depends(require_admin)],
    response_model=MemoryRecord,
    status_code=201,
)
def remember_conversation(item: ConversationMemoryCapture) -> MemoryRecord:
    """Store one user-confirmed summary; never a raw transcript or inference."""
    return capture_conversation_memory(store, item)


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


@app.post("/v1/session/greeting/commit", status_code=204,
          dependencies=[Depends(require_admin)])
def confirm_greeting(item: GreetingCommit) -> None:
    """Record a greeting only after the caller confirms it was emitted."""
    try:
        commit_greeting(store, HomeAssistantReader(), wake_at=item.wake_at)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/v1/resolve/entity", response_model=ResolutionResult)
def resolve_entity(q: str, limit: int = 5) -> ResolutionResult:
    """Resolve an intended target against the current HA snapshot only."""
    if not q.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")
    return resolve_current_entity(HomeAssistantReader(), q, limit=limit)


# Keep the catch-all mount last so the existing HTTP API remains reachable.
app.mount("/mcp", mcp_http_app)
