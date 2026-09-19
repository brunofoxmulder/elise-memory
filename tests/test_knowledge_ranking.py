import hashlib
import json

from elise_memory.knowledge import KnowledgeCreate, KnowledgeStore


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _automation(name: str, description: str, inventory: str = "") -> KnowledgeCreate:
    payload = {
        "name": name,
        "description": description,
        "technical_inventory": inventory or None,
        "linked_automations": None,
    }
    key = "automation:" + (
        name.lower()
        .replace("'", "")
        .replace("’", "")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("ç", "c")
        .replace(" ", "-")
    )
    return KnowledgeCreate(
        key=key,
        object_type="automation",
        domain="Éclairage",
        value=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        origin="canonical",
        source_id=f"automations:production:{key}",
    )


def _store(tmp_path, items):
    store = KnowledgeStore(tmp_path / "memory.sqlite3")
    store.initialize()
    compiled = [(item, _hash(item.value)) for item in items]
    store.apply_canonical_snapshot(compiled)
    return store


def test_lampe_entree_prefers_complete_behavior_over_narrow_unlock_only(tmp_path):
    """Terrain regression: the main entrance-light automation must rank first."""
    main = _automation(
        "Allumer lampe entrée selon l'heure et la présence",
        "Allume l’éclairage d’entrée sur mouvement ou déverrouillage, selon horaire "
        "et mode cinéma. Elle s’éteint après deux minutes sans mouvement.",
        "binary_sensor.eclairement_entree_mouvement lock.porte_dentree "
        "light.hue_tento_color_panel_1_2",
    )
    narrow = _automation(
        "Allumer lampe entrée lors déverrouillage porte",
        "Allume la lampe de l’entrée en blanc chaud quand la porte d’entrée se déverrouille.",
        "lock.porte_dentree light.hue_tento_color_panel_1_2",
    )
    # Narrow entry is deliberately newer, matching the current canonical row order.
    store = _store(tmp_path, [main, narrow])

    result = store.search("lampe entrée", limit=8)

    assert result["knowledge"][0]["key"] == main.key


def test_lampe_salle_de_bain_beats_unrelated_mentions_of_room(tmp_path):
    """Terrain regression: bathroom motion lighting must not disappear behind SDB mentions."""
    bathroom = _automation(
        "Allumer salle de bain selon l'heure et la présence",
        "Allume la salle de bain sur mouvement selon horaire, puis éteint après absence.",
        "binary_sensor.salle_de_bain_mouvement switch.prise_de_comptage_prise_1 "
        "input_boolean.mode_cinema light.hue_tento_color_panel_1",
    )
    leak = _automation(
        "Alerte fuite d'eau si Bruno est là",
        "Annonce une fuite sur les téléphones, la télévision et l’Echo de la salle de bain.",
        "binary_sensor.fuite_baignoire_water_leak notify.echo_dot_sdb_annoncer",
    )
    shutter = _automation(
        "Gestion volet salon avec soleil et saison",
        "Aucune annonce sur la télévision ou l'Echo de la salle de bain.",
        "cover.volet_salon_2",
    )
    store = _store(tmp_path, [bathroom, leak, shutter])

    result = store.search("lampe salle de bain", limit=8)

    assert result["knowledge"][0]["key"] == bathroom.key


def test_volet_salon_prefers_named_automation_over_generic_analysis(tmp_path):
    """Exact object/name intent must outrank a generic record merely mentioning the object."""
    shutter = _automation(
        "Gestion volet salon avec soleil et saison",
        "Ajuste le volet salon selon température, soleil, azimut, élévation, lux et saison.",
        "cover.volet_salon_2 sensor.temperature_exterieure_fiable",
    )
    analysis = _automation(
        "Analyse IA - Confort thermique",
        "Analyse le confort thermique avec le volet salon, le volet terrasse et les ouvrants.",
        "cover.volet_salon_2 cover.volet_terrasse_2",
    )
    store = _store(tmp_path, [shutter, analysis])

    result = store.search("volet salon", limit=8)

    assert result["knowledge"][0]["key"] == shutter.key


def test_phrase_and_all_terms_rank_before_partial_matches(tmp_path):
    """A phrase/all-term match must beat rows matching only one query term."""
    target = _automation(
        "Ouverture volet terrasse lors de l'ouverture de la porte fenetre",
        "Ouvre le volet terrasse à 100 % quand la porte-fenêtre est ouverte.",
        "binary_sensor.porte_fenetre_contact cover.volet_terrasse_2",
    )
    only_port = _automation(
        "Déverrouillage porte d'entrée",
        "Déverrouille la porte d’entrée par un bouton Hue.",
        "lock.porte_dentree",
    )
    only_window = _automation(
        "Protection fenêtre salon",
        "Surveille la fenêtre du salon.",
        "binary_sensor.fenetre_porte_contact",
    )
    store = _store(tmp_path, [target, only_port, only_window])

    result = store.search("porte fenetre", limit=8)

    assert result["knowledge"][0]["key"] == target.key
