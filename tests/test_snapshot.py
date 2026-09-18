import hashlib
import pytest

from elise_memory.knowledge import KnowledgeCreate, KnowledgeStore


def fact(key, value, source):
    item=KnowledgeCreate(key=key,object_type="fact",value=value,origin="canonical",source_id=source)
    return item, hashlib.sha256(value.encode()).hexdigest()


def test_snapshot_is_idempotent_and_deactivates_removed_rows(tmp_path):
    s=KnowledgeStore(tmp_path/"m.sqlite3"); s.initialize()
    first=[fact("a","1","src:a"),fact("b","2","src:b")]
    assert s.apply_canonical_snapshot(first)["changed"]==2
    assert s.apply_canonical_snapshot(first)["changed"]==0
    second=[fact("a","new","src:a")]
    result=s.apply_canonical_snapshot(second, expected_min_ratio=0.5)
    assert result=={"records":1,"changed":1,"deactivated":1}
    assert [x["value"] for x in s.active("a")]==["new"]
    assert s.active("b")==[]


def test_abnormal_volume_drop_keeps_previous_snapshot(tmp_path):
    s=KnowledgeStore(tmp_path/"m.sqlite3"); s.initialize()
    baseline=[fact(str(i),str(i),f"src:{i}") for i in range(10)]
    s.apply_canonical_snapshot(baseline)
    with pytest.raises(ValueError, match="volume_drop"):
        s.apply_canonical_snapshot(baseline[:2])
    assert sum(len(s.active(str(i))) for i in range(10))==10


def test_empty_and_duplicate_snapshots_fail_closed(tmp_path):
    s=KnowledgeStore(tmp_path/"m.sqlite3"); s.initialize()
    with pytest.raises(ValueError, match="empty"):
        s.apply_canonical_snapshot([])
    a=fact("a","1","src:a")
    with pytest.raises(ValueError, match="duplicate"):
        s.apply_canonical_snapshot([a,a])


def test_canonical_snapshot_never_touches_rex(tmp_path):
    s=KnowledgeStore(tmp_path/"m.sqlite3"); s.initialize()
    rex=KnowledgeCreate(key="a",object_type="observation",value="rex",origin="rex",
                        source_id="rex:1",status="validated")
    s.replace_current(rex,"rexhash")
    s.apply_canonical_snapshot([fact("a","canonical","src:a")])
    assert {x["origin"] for x in s.active("a")}=={"canonical","rex"}
