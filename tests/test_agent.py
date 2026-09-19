import sqlite3

from elise_memory.agent import AgentQuery, query_agent_memory
from elise_memory.knowledge import KnowledgeStore
from elise_memory.models import MemoryCreate
from elise_memory.store import MemoryStore


def stores(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    knowledge = KnowledgeStore(tmp_path / "memory.sqlite3")
    memory.initialize()
    knowledge.initialize()
    return memory, knowledge


def test_agent_returns_house_and_conversation_memory_as_advice(tmp_path):
    memory, knowledge = stores(tmp_path)
    memory.add(MemoryCreate(
        kind="house", key="volet_chambre", value="volet de la chambre", source="canonical",
    ))
    memory.add(MemoryCreate(
        kind="conversation", key="volet_chambre", value="Bruno souhaite le fermer", source="conversation:test",
    ))

    result = query_agent_memory(memory, knowledge, AgentQuery(query="volet chambre"))

    assert result.route == "memory"
    assert result.advice_only is True
    assert result.may_execute is False
    assert {item.kind for item in result.memories} == {"house", "conversation"}


def test_agent_routes_why_to_investigator_without_memory_results(tmp_path):
    memory, knowledge = stores(tmp_path)
    memory.add(MemoryCreate(
        kind="house", key="chauffage", value="pilotage", source="canonical",
    ))

    result = query_agent_memory(
        memory, knowledge, AgentQuery(query="Pourquoi le chauffage s'est arrêté ?")
    )

    assert result.route == "investigator"
    assert result.memories == []
    assert result.knowledge == []
    assert result.may_execute is False


def test_store_migrates_existing_schema_for_conversation_memory(tmp_path):
    database = tmp_path / "memory.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK(kind IN ('house', 'temporal')),
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                source TEXT NOT NULL,
                valid_from TEXT,
                valid_until TEXT,
                created_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """INSERT INTO memories
               (kind, key, value, source, valid_from, valid_until, created_at)
               VALUES ('house', 'existing', 'preserved', 'dev17', NULL, NULL,
                       '2026-09-19T00:00:00+00:00')"""
        )
    memory = MemoryStore(database)
    memory.initialize()
    created = memory.add(MemoryCreate(
        kind="conversation", key="preference", value="réponse courte", source="conversation:test",
    ))
    assert created.kind == "conversation"
    assert memory.find("house", "existing")[0].value == "preserved"
