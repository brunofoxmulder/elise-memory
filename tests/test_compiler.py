import pytest

from elise_memory.compiler import (
    SourceSchemaError, compile_memory_ia, compile_metier, compile_relations,
    is_validated,
)


def test_validated_status_accepts_qualified_feminine_label():
    assert is_validated("Validée — S003 production / S002 différé")
    assert is_validated("Validé")
    assert not is_validated("À vérifier")


def test_metier_ignores_empty_rows_and_keeps_non_oui_official_source():
    h = ["Domaine","Fonction métier","Entité Home Assistant actuelle","Type",
         "Valeur métier","Criticité","Source officielle","État attendu / règle",
         "Dépendance matériel","Commentaire"]
    rows = [
        ["Protection","Volet salon","cover.volet_salon_2","Cover","Position","A",
         "KLF 200","Protection solaire","KLF200","utile"],
        [""] * 10,
    ]
    result = compile_metier(h, rows)
    assert len(result) == 1
    assert result[0].item.key == "cover.volet_salon_2"


def test_memory_ia_only_compiles_validated_knowledge():
    h = ["ID connaissance","Domaine","Connaissance","Statut","Confiance (%)","Source / preuves"]
    rows = [
        ["K1","Daikin","Règle validée","Validée — production","100","Journal"],
        ["K2","Daikin","Hypothèse","À vérifier","50",""],
    ]
    result = compile_memory_ia(h, rows)
    assert [x.item.key for x in result] == ["knowledge:K1"]


def test_relations_only_keep_validated_active():
    h = ["Relation_ID","Source_ID","Relation","Cible_ID","Statut","Rôle_ou_effet","Confiance"]
    rows = [
        ["R1","cover.a","piloté par","automation.a","Validé / actif","protection","Élevée"],
        ["R2","cover.a","piloté par","automation.old","Remplacé","",""],
    ]
    result = compile_relations(h, rows)
    assert [x["relation_id"] for x in result] == ["R1"]


def test_schema_drift_fails_closed():
    with pytest.raises(SourceSchemaError):
        compile_memory_ia(["wrong"], [["x"]])
