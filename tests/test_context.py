from elise_memory.context import ContextKey, ContextRequest, build_context
from elise_memory.models import MemoryCreate
from elise_memory.store import MemoryStore


def test_context_is_explicit_and_reports_missing_keys(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    store.add(MemoryCreate(kind="house", key="kitchen_light", value="lamp", source="project"))

    result = build_context(
        store,
        ContextRequest(
            keys=[
                ContextKey(kind="house", key="kitchen_light"),
                ContextKey(kind="house", key="unknown"),
            ]
        ),
    )

    assert [record.key for record in result.records] == ["kitchen_light"]
    assert [item.key for item in result.missing] == ["unknown"]
