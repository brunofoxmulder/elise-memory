from elise_memory.models import MemoryCreate
from elise_memory.store import MemoryStore


def test_house_and_temporal_memories_are_separated(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()

    store.add(MemoryCreate(kind="house", key="greeting", value="house", source="test"))
    store.add(MemoryCreate(kind="temporal", key="greeting", value="temporal", source="test"))

    house = store.find("house", "greeting")
    temporal = store.find("temporal", "greeting")

    assert [item.value for item in house] == ["house"]
    assert [item.value for item in temporal] == ["temporal"]


def test_provenance_is_preserved(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    record = store.add(
        MemoryCreate(kind="house", key="kitchen", value="known fact", source="project:test")
    )
    assert record.source == "project:test"
