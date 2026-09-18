from elise_memory.compiler import compile_automations, compile_scripts


def test_automation_compiles_semantics_not_yaml():
    h=["Nom de l'automatisation","Domaine","Descriptif","Production","Statut test",
       "Automatisations liées","Inventaire technique","Production -1"]
    rows=[["Volet nuit","Protection","Ferme le volet","alias: secret yaml","Validé",
           "Réveil","cover.salon; sun.sun","old yaml"]]
    r=compile_automations(h,rows)
    assert len(r)==1
    assert "secret yaml" not in r[0].item.value
    assert "old yaml" not in r[0].item.value
    assert "Ferme le volet" in r[0].item.value


def test_automation_without_production_is_excluded():
    h=["Nom de l'automatisation","Domaine","Descriptif","Production","Statut test"]
    assert compile_automations(h,[["Old","X","old","","Validé"]])==[]


def test_scripts_keep_production_and_exclude_test_retired():
    h=["ID","Nom du fichier","Service HA exposé","Domaine","Rôle","Statut",
       "Version actuelle","Entités HA utilisées","Onglets lus","Onglets écrits"]
    rows=[
      ["S1","prod.py","pyscript.prod","Thermique","Analyse","Production validée","1","sensor.t","A","B"],
      ["S2","test.py","pyscript.test","Thermique","Test","TEST validé","1","","",""],
      ["S3","old.py","pyscript.old","Thermique","Old","Retiré / historique","1","","",""],
    ]
    r=compile_scripts(h,rows)
    assert [x.item.key for x in r]==["script:S1"]
