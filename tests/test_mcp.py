import asyncio

from elise_memory.app import consult_elise_memory, memory_mcp


def test_mcp_exposes_one_read_only_memory_tool():
    tools = asyncio.run(memory_mcp.list_tools())

    assert [tool.name for tool in tools] == ["consult_elise_memory"]
    tool = tools[0]
    assert "ne commande aucun appareil" in (tool.description or "")
    assert set(tool.inputSchema.get("required", [])) == {"query"}


def test_mcp_tool_preserves_investigator_routing(monkeypatch, tmp_path):
    from elise_memory import app as app_module
    from elise_memory.knowledge import KnowledgeStore
    from elise_memory.store import MemoryStore

    memory = MemoryStore(tmp_path / "memory.sqlite3")
    knowledge = KnowledgeStore(tmp_path / "memory.sqlite3")
    memory.initialize()
    knowledge.initialize()
    monkeypatch.setattr(app_module, "store", memory)
    monkeypatch.setattr(app_module, "knowledge_store", knowledge)

    result = consult_elise_memory("Pourquoi le volet est-il fermé ?")

    assert result.route == "investigator"
    assert result.advice_only is True
    assert result.may_execute is False
