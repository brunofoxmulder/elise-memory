import pytest
import hashlib

from elise_memory.knowledge import KnowledgeCreate, KnowledgeStore


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def test_unchanged_canonical_fact_is_not_duplicated(tmp_path):
    store = KnowledgeStore(tmp_path / "memory.sqlite3")
    store.initialize()
    item = KnowledgeCreate(
        key="cover.salon", object_type="cover", value="VELUX KLF200",
        origin="canonical", source_id="SRC-HA-001:referentiel-metier:volet-salon"
    )
    assert store.replace_current(item, _hash(item.value)) is not None
    assert store.replace_current(item, _hash(item.value)) is None
    assert len(store.active("cover.salon")) == 1


def test_changed_fact_supersedes_previous_version(tmp_path):
    store = KnowledgeStore(tmp_path / "memory.sqlite3")
    store.initialize()
    first = KnowledgeCreate(
        key="cover.salon", object_type="cover", value="old",
        origin="canonical", source_id="source:row"
    )
    second = first.model_copy(update={"value": "new"})
    store.replace_current(first, _hash(first.value))
    store.replace_current(second, _hash(second.value))
    active = store.active("cover.salon")
    assert [x["value"] for x in active] == ["new"]


def test_rex_and_canonical_are_distinct_layers(tmp_path):
    store = KnowledgeStore(tmp_path / "memory.sqlite3")
    store.initialize()
    canonical = KnowledgeCreate(
        key="thermal.salon", object_type="rule", value="canonical",
        origin="canonical", source_id="canonical:1"
    )
    rex = KnowledgeCreate(
        key="thermal.salon", object_type="observation", value="observed",
        origin="rex", source_id="rex:1", status="validated", confidence=100
    )
    store.replace_current(canonical, _hash(canonical.value))
    store.replace_current(rex, _hash(rex.value))
    assert {x["origin"] for x in store.active("thermal.salon")} == {"canonical", "rex"}


def test_per_source_volume_drop_rejects_whole_snapshot(tmp_path):
    store = KnowledgeStore(tmp_path / "memory.db")
    store.initialize()
    def item(key, source):
        return KnowledgeCreate(key=key, object_type="fact", value=key,
                               origin="canonical", source_id=source)
    first = [(item(f"a{i}", f"a:{i}"), f"ha{i}") for i in range(10)]
    first += [(item(f"b{i}", f"b:{i}"), f"hb{i}") for i in range(10)]
    store.apply_canonical_snapshot(
        first,
        source_stats={"a": (10, 10), "b": (10, 10)},
    )
    before = store.sync_health()
    second = [(item(f"a{i}", f"a:{i}"), f"ha{i}") for i in range(6)]
    second += [(item(f"b{i}", f"b:{i}"), f"hb{i}") for i in range(10)]
    with pytest.raises(ValueError, match="canonical_source_volume_drop:a"):
        store.apply_canonical_snapshot(
            second,
            source_stats={"a": (6, 6), "b": (10, 10)},
        )
    after = store.sync_health()
    assert after["canonical_records"] == before["canonical_records"] == 20
