"""Bounded, advisory contract exposed to a voice agent."""

import re
from typing import Literal

from pydantic import BaseModel, Field

from .knowledge import KnowledgeStore
from .models import MemoryRecord
from .store import MemoryStore

AgentRoute = Literal["memory", "investigator"]

_CAUSAL = re.compile(
    r"^\s*(?:pourquoi|pour quelle raison|comment se fait-il|why\b|what caused\b)",
    re.IGNORECASE,
)


class AgentQuery(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=6, ge=1, le=12)


class AgentAnswer(BaseModel):
    route: AgentRoute
    advice_only: bool = True
    may_execute: bool = False
    query: str
    knowledge: list[dict] = Field(default_factory=list)
    relations: list[dict] = Field(default_factory=list)
    memories: list[MemoryRecord] = Field(default_factory=list)
    instruction: str


def query_agent_memory(
    memories: MemoryStore,
    knowledge: KnowledgeStore,
    request: AgentQuery,
) -> AgentAnswer:
    """Return evidence for deliberation, never an action or causal conclusion."""
    query = request.query.strip()
    if _CAUSAL.search(query):
        return AgentAnswer(
            route="investigator",
            query=query,
            instruction=(
                "Question causale : ne pas conclure depuis la mémoire. "
                "Utiliser Investigator avec les données Home Assistant actuelles."
            ),
        )

    house = knowledge.search(query, limit=request.limit)
    found = memories.search(query, limit=request.limit)
    return AgentAnswer(
        route="memory",
        query=query,
        knowledge=house["knowledge"],
        relations=house["relations"],
        memories=found,
        instruction=(
            "Contexte consultatif uniquement. Vérifier l'état actuel dans Home Assistant "
            "avant toute action; demander une précision si la cible reste ambiguë."
        ),
    )
