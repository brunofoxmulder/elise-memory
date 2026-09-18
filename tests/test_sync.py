import hashlib
import pytest

from elise_memory.google_sheets import SheetRange
from elise_memory.knowledge import KnowledgeCreate, KnowledgeStore
from elise_memory.sync import synchronize_canonical


class FakeReader:
    def __init__(self, by_sheet):
        self.by_sheet=by_sheet
    def values(self, source: SheetRange):
        value=self.by_sheet[source.sheet_name]
        if isinstance(value, Exception):
            raise value
        return value


def sources():
    return {
      "Référentiel métier":[
        ["Domaine","Fonction métier","Entité Home Assistant actuelle","Type","Valeur métier","Criticité","Source officielle"],
        ["Protection","Volet salon","cover.volet_salon_2","Cover","Position","A","Oui"]],
      "Mémoire IA":[
        ["ID connaissance","Domaine","Connaissance","Statut"],
        ["K1","Maison","Connaissance validée","Validé"]],
      "09_Relations fonctionnelles":[
        ["Relation_ID","Source_ID","Relation","Cible_ID","Statut"],
        ["R1","cover.volet_salon_2","piloté par","automation.nuit","Validé / actif"]],
      "Automatisations":[
        ["Nom de l'automatisation","Domaine","Descriptif","Production","Statut test"],
        ["Nuit","Protection","Ferme volet","yaml","Validé"]],
      "Scripts Pyscript":[
        ["ID","Nom du fichier","Service HA exposé","Domaine","Rôle","Statut"],
        ["S1","script.py","pyscript.s1","Maison","Service actif","Production validée"]],
    }


def test_full_sync_publishes_only_after_all_sources_compile(tmp_path):
    store=KnowledgeStore(tmp_path/"m.sqlite3"); store.initialize()
    report=synchronize_canonical(store,FakeReader(sources()))
    assert report.compiled_records==4
    assert report.relations==1
    assert store.active("cover.volet_salon_2")


def test_reader_failure_preserves_previous_snapshot(tmp_path):
    store=KnowledgeStore(tmp_path/"m.sqlite3"); store.initialize()
    old=KnowledgeCreate(key="old",object_type="fact",value="safe",origin="canonical",source_id="old:1")
    store.apply_canonical_snapshot([(old,hashlib.sha256(b"safe").hexdigest())])
    broken=sources(); broken["Automatisations"]=RuntimeError("google unavailable")
    with pytest.raises(RuntimeError):
        synchronize_canonical(store,FakeReader(broken))
    assert store.active("old")[0]["value"]=="safe"


def test_relation_failure_rolls_back_knowledge_snapshot(tmp_path):
    store=KnowledgeStore(tmp_path/"m.sqlite3"); store.initialize()
    old=KnowledgeCreate(key="old",object_type="fact",value="safe",origin="canonical",source_id="old:1")
    store.apply_canonical_snapshot([(old,hashlib.sha256(b"safe").hexdigest())])
    bad=sources()
    bad["09_Relations fonctionnelles"].append(
        ["R1","cover.other","piloté par","automation.other","Validé / actif"]
    )
    with pytest.raises(ValueError, match="duplicate_canonical_relation"):
        synchronize_canonical(store,FakeReader(bad))
    assert store.active("old")[0]["value"]=="safe"
    assert store.active("cover.volet_salon_2")==[]


def test_sync_rejects_semantically_empty_required_source_before_publish(tmp_path):
    from elise_memory.canonical_sources import CANONICAL_RANGES
    from elise_memory.sync import synchronize_canonical

    class EmptyRelationsReader(FakeReader):
        def values(self, source):
            values = super().values(source)
            if source == CANONICAL_RANGES["relations"]:
                return [values[0]]
            return values

    db = tmp_path / "memory.db"
    store = KnowledgeStore(db)
    store.initialize()
    reader = EmptyRelationsReader(sources())
    with pytest.raises(ValueError, match="canonical_source_compiled_empty:relations"):
        synchronize_canonical(store, reader)
    assert store.sync_health()["canonical_records"] == 0
