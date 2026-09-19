from elise_memory.operational_graph import build_operational_graph


HA_HEADER = ["Entity ID", "Domaine", "Nom", "État"]
AUTO_HEADER = [
    "Nom de l'automatisation", "Domaine", "Descriptif", "Production",
    "Statut test", "Automatisations liées", "Inventaire technique",
]


def _auto(name, yaml_text, desc=""):
    return [name, "Maison", desc, yaml_text, "Validée", "", ""]


def _graph(extra_ha, rows):
    ha = [
        ["automation.entree", "automation", "Allumer lampe entrée selon présence", "on"],
        ["automation.entree_unlock", "automation", "Allumer lampe entrée au déverrouillage", "on"],
        ["automation.sdb", "automation", "Allumer salle de bain selon présence", "on"],
        ["automation.hotte", "automation", "Allumer hotte selon présence", "on"],
        ["automation.volet_salon_open", "automation", "Ouverture volet salon par ouverture fenêtre", "on"],
        ["automation.volet_terrasse_open", "automation", "Ouverture volet terrasse par ouverture porte fenêtre", "on"],
        ["automation.volet_terrasse_weather", "automation", "Gestion volet terrasse selon météo", "on"],
        ["automation.s23", "automation", "Charge téléphone principal en heures creuses", "on"],
        ["automation.s20", "automation", "Charge téléphone secondaire en heures creuses", "on"],
        ["automation.lave_start", "automation", "Lave-linge - Début de cycle", "on"],
        ["automation.lave_rinse", "automation", "Lave-linge - Passage au rinçage", "on"],
        ["automation.lave_dry", "automation", "Lave-linge - Passage au séchage", "on"],
        ["automation.lave_end", "automation", "Lave-linge - Fin de cycle", "on"],
        ["automation.disabled", "automation", "Ancienne lampe entrée", "off"],
        ["light.entree", "light", "Lampe entrée", "off"],
        ["light.sdb", "light", "Lampe salle de bain", "off"],
        ["light.hotte", "light", "Hotte", "off"],
        ["cover.salon", "cover", "Volet salon", "open"],
        ["cover.terrasse", "cover", "Volet terrasse", "open"],
        ["binary_sensor.mvt_entree", "binary_sensor", "Mouvement entrée", "off"],
        ["binary_sensor.mvt_sdb", "binary_sensor", "Mouvement salle de bain", "off"],
        ["binary_sensor.mvt_hotte", "binary_sensor", "Mouvement cuisine", "off"],
        ["lock.porte", "lock", "Porte d'entrée", "locked"],
        ["binary_sensor.fenetre", "binary_sensor", "Fenêtre salon", "off"],
        ["binary_sensor.porte_fenetre", "binary_sensor", "Porte fenêtre", "off"],
        ["sensor.temp_ext", "sensor", "Température extérieure fiable", "20"],
        ["binary_sensor.hc", "binary_sensor", "Heures creuses", "off"],
        ["sensor.tel1_battery", "sensor", "Téléphone principal batterie", "80"],
        ["sensor.tel2_battery", "sensor", "Téléphone secondaire batterie", "70"],
        ["switch.tel1", "switch", "Chargeur téléphone", "off"],
        ["switch.tel2", "switch", "Chargeur téléphone 2", "off"],
        ["sensor.lave_power", "sensor", "Puissance prise lave-linge", "0"],
        ["input_boolean.lave", "input_boolean", "Lave-linge en cours", "off"],
        ["input_select.phase_lave", "input_select", "Phase lave-linge", "Arrêt"],
    ]
    ha.extend(extra_ha)
    return build_operational_graph(HA_HEADER, ha, AUTO_HEADER, rows)


ROWS = [
    _auto("Allumer lampe entrée selon présence", """
alias: Allumer lampe entrée selon présence
triggers:
  - trigger: state
    entity_id: binary_sensor.mvt_entree
    to: "on"
  - trigger: state
    entity_id: lock.porte
    to: unlocked
conditions:
  - condition: state
    entity_id: input_boolean.reveil
    state: "on"
actions:
  - action: light.turn_on
    target: {entity_id: light.entree}
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.mvt_entree
        to: "off"
        for: "00:02:00"
  - action: light.turn_off
    target: {entity_id: light.entree}
mode: restart
"""),
    _auto("Allumer lampe entrée au déverrouillage", """
alias: Allumer lampe entrée au déverrouillage
triggers:
  - trigger: state
    entity_id: lock.porte
    to: unlocked
actions:
  - action: light.turn_on
    target: {entity_id: light.entree}
"""),
    _auto("Allumer salle de bain selon présence", """
alias: Allumer salle de bain selon présence
triggers:
  - trigger: state
    entity_id: binary_sensor.mvt_sdb
    to: "on"
actions:
  - action: light.turn_on
    target: {entity_id: light.sdb}
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.mvt_sdb
        to: "off"
        for: "00:05:00"
  - action: light.turn_off
    target: {entity_id: light.sdb}
"""),
    _auto("Allumer hotte selon présence", """
alias: Allumer hotte selon présence
triggers:
  - trigger: state
    entity_id: binary_sensor.mvt_hotte
    to: "on"
actions:
  - action: light.turn_on
    target: {entity_id: light.hotte}
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.mvt_hotte
        to: "off"
        for: "00:05:00"
  - action: light.turn_off
    target: {entity_id: light.hotte}
"""),
    _auto("Ouverture volet salon par ouverture fenêtre", """
alias: Ouverture volet salon par ouverture fenêtre
triggers:
  - trigger: state
    entity_id: binary_sensor.fenetre
    to: "on"
actions:
  - action: cover.set_cover_position
    target: {entity_id: cover.salon}
    data: {position: 100}
"""),
    _auto("Ouverture volet terrasse par ouverture porte fenêtre", """
alias: Ouverture volet terrasse par ouverture porte fenêtre
triggers:
  - trigger: state
    entity_id: binary_sensor.porte_fenetre
    to: "on"
actions:
  - action: cover.set_cover_position
    target: {entity_id: cover.terrasse}
    data: {position: 100}
"""),
    _auto("Gestion volet terrasse selon météo", """
alias: Gestion volet terrasse selon météo
triggers:
  - trigger: numeric_state
    entity_id: sensor.temp_ext
    below: 3
  - trigger: numeric_state
    entity_id: sensor.temp_ext
    above: 28
conditions:
  - condition: state
    entity_id: binary_sensor.porte_fenetre
    state: "off"
actions:
  - action: cover.close_cover
    target: {entity_id: cover.terrasse}
"""),
    _auto("Charge téléphone principal en heures creuses", """
alias: Charge téléphone principal en heures creuses
triggers:
  - trigger: state
    entity_id: binary_sensor.hc
    to: "on"
  - trigger: numeric_state
    entity_id: sensor.tel1_battery
    below: 95
conditions:
  - condition: state
    entity_id: binary_sensor.hc
    state: "on"
actions:
  - choose:
      - conditions:
          - condition: numeric_state
            entity_id: sensor.tel1_battery
            below: 95
        sequence:
          - delay: "00:30:00"
          - action: switch.turn_on
            target: {entity_id: switch.tel1}
      - conditions:
          - condition: numeric_state
            entity_id: sensor.tel1_battery
            above: 99
        sequence:
          - action: switch.turn_off
            target: {entity_id: switch.tel1}
"""),
    _auto("Charge téléphone secondaire en heures creuses", """
alias: Charge téléphone secondaire en heures creuses
triggers:
  - trigger: state
    entity_id: binary_sensor.hc
    to: "on"
  - trigger: numeric_state
    entity_id: sensor.tel2_battery
    below: 95
conditions:
  - condition: state
    entity_id: binary_sensor.hc
    state: "on"
actions:
  - choose:
      - conditions:
          - condition: numeric_state
            entity_id: sensor.tel2_battery
            below: 95
        sequence:
          - delay: "00:30:00"
          - action: switch.turn_on
            target: {entity_id: switch.tel2}
      - conditions:
          - condition: numeric_state
            entity_id: sensor.tel2_battery
            above: 99
        sequence:
          - action: switch.turn_off
            target: {entity_id: switch.tel2}
"""),
    _auto("Lave-linge - Début de cycle", """
alias: Lave-linge - Début de cycle
triggers:
  - trigger: numeric_state
    entity_id: sensor.lave_power
    above: 20
conditions:
  - condition: state
    entity_id: input_boolean.lave
    state: "off"
actions:
  - action: input_boolean.turn_on
    target: {entity_id: input_boolean.lave}
  - action: input_select.select_option
    target: {entity_id: input_select.phase_lave}
    data: {option: Lavage}
"""),
    _auto("Lave-linge - Passage au rinçage", """
alias: Lave-linge - Passage au rinçage
triggers:
  - trigger: state
    entity_id: input_boolean.lave
    to: "on"
    for: {minutes: 45}
conditions:
  - condition: state
    entity_id: input_select.phase_lave
    state: Lavage
actions:
  - action: input_select.select_option
    target: {entity_id: input_select.phase_lave}
    data: {option: Rinçage}
"""),
    _auto("Lave-linge - Passage au séchage", """
alias: Lave-linge - Passage au séchage
triggers:
  - trigger: numeric_state
    entity_id: sensor.lave_power
    above: 1100
    for: {minutes: 2}
conditions:
  - condition: state
    entity_id: input_boolean.lave
    state: "on"
  - condition: state
    entity_id: input_select.phase_lave
    state: Rinçage
actions:
  - action: input_select.select_option
    target: {entity_id: input_select.phase_lave}
    data: {option: Séchage}
"""),
    _auto("Lave-linge - Fin de cycle", """
alias: Lave-linge - Fin de cycle
triggers:
  - trigger: numeric_state
    entity_id: sensor.lave_power
    below: 5
    for: {minutes: 3}
conditions:
  - condition: state
    entity_id: input_boolean.lave
    state: "on"
actions:
  - action: input_boolean.turn_off
    target: {entity_id: input_boolean.lave}
  - action: input_select.select_option
    target: {entity_id: input_select.phase_lave}
    data: {option: Arrêt}
"""),
    _auto("Ancienne lampe entrée", """
alias: Ancienne lampe entrée
triggers:
  - trigger: state
    entity_id: binary_sensor.mvt_entree
actions:
  - action: light.turn_on
    target: {entity_id: light.entree}
"""),
]


def test_drive_style_reconciliation_excludes_disabled_and_unresolved_docs():
    rows = ROWS + [_auto("Documentation périmée", """
alias: Documentation périmée
triggers:
  - trigger: state
    entity_id: binary_sensor.mvt_entree
actions:
  - action: light.turn_on
    target: {entity_id: light.entree}
""")]
    graph = _graph([], rows)
    assert "automation.disabled" not in graph.automations
    assert any(x.name == "Documentation périmée" for x in graph.unresolved_documents)


def test_entry_light_returns_both_real_active_automations_not_one_arbitrary_row():
    graph = _graph([["input_boolean.reveil", "input_boolean", "Réveil", "on"]], ROWS)
    result = graph.automation_context_for("light.entree", effect="turn_on")
    assert [x["automation_id"] for x in result] == [
        "automation.entree", "automation.entree_unlock"
    ]
    main = next(x for x in result if x["automation_id"] == "automation.entree")
    assert {e.subject for e in main["triggers"]} == {"binary_sensor.mvt_entree", "lock.porte"}


def test_bathroom_light_is_resolved_by_action_target_not_room_mentions():
    graph = _graph([], ROWS)
    result = graph.automation_context_for("light.sdb", effect="turn_on")
    assert [x["automation_id"] for x in result] == ["automation.sdb"]
    assert {e.subject for e in result[0]["triggers"]} == {"binary_sensor.mvt_sdb"}


def test_hood_light_is_resolved_by_action_target():
    graph = _graph([], ROWS)
    result = graph.automation_context_for("light.hotte", effect="turn_on")
    assert [x["automation_id"] for x in result] == ["automation.hotte"]


def test_opening_window_reaches_salon_shutter_with_position_100():
    graph = _graph([], ROWS)
    result = graph.automation_context_for("cover.salon", effect="set_position")
    assert [x["automation_id"] for x in result] == ["automation.volet_salon_open"]
    assert result[0]["action_metadata"]["position"] == 100
    assert {e.subject for e in result[0]["triggers"]} == {"binary_sensor.fenetre"}


def test_opening_door_window_reaches_terrace_shutter_with_position_100():
    graph = _graph([], ROWS)
    result = graph.automation_context_for("cover.terrasse", effect="set_position")
    assert [x["automation_id"] for x in result] == ["automation.volet_terrasse_open"]
    assert result[0]["action_metadata"]["position"] == 100
    assert {e.subject for e in result[0]["triggers"]} == {"binary_sensor.porte_fenetre"}


def test_terrace_weather_close_is_distinct_from_opening_rule():
    graph = _graph([], ROWS)
    close = graph.automation_context_for("cover.terrasse", effect="close")
    assert [x["automation_id"] for x in close] == ["automation.volet_terrasse_weather"]
    assert {e.subject for e in close[0]["triggers"]} == {"sensor.temp_ext"}
    assert {e.subject for e in close[0]["guards"]} == {"binary_sensor.porte_fenetre"}


def test_primary_phone_charge_keeps_delay_guard_and_target():
    graph = _graph([], ROWS)
    result = graph.automation_context_for("switch.tel1", effect="turn_on")
    assert [x["automation_id"] for x in result] == ["automation.s23"]
    assert result[0]["barriers"]
    assert "binary_sensor.hc" in {e.subject for e in result[0]["guards"]}


def test_secondary_phone_charge_does_not_cross_with_primary_phone():
    graph = _graph([], ROWS)
    result = graph.automation_context_for("switch.tel2", effect="turn_on")
    assert [x["automation_id"] for x in result] == ["automation.s20"]
    assert "sensor.tel2_battery" in {e.subject for e in result[0]["triggers"]}
    assert "sensor.tel1_battery" not in {e.subject for e in result[0]["triggers"]}


def test_laundry_start_sets_running_and_wash_phase():
    graph = _graph([], ROWS)
    running = graph.automation_context_for("input_boolean.lave", effect="turn_on")
    phase = graph.automation_context_for("input_select.phase_lave", effect="select_option")
    assert [x["automation_id"] for x in running] == ["automation.lave_start"]
    start = next(x for x in phase if x["automation_id"] == "automation.lave_start")
    assert start["action_metadata"]["option"] == "Lavage"


def test_laundry_rinse_is_45_min_state_trigger_with_lavage_guard():
    graph = _graph([], ROWS)
    phase = graph.automation_context_for("input_select.phase_lave", effect="select_option")
    rinse = next(x for x in phase if x["automation_id"] == "automation.lave_rinse")
    assert {e.subject for e in rinse["triggers"]} == {"input_boolean.lave"}
    assert {e.subject for e in rinse["guards"]} == {"input_select.phase_lave"}


def test_laundry_dry_uses_power_trigger_and_two_guards():
    graph = _graph([], ROWS)
    phase = graph.automation_context_for("input_select.phase_lave", effect="select_option")
    dry = next(x for x in phase if x["automation_id"] == "automation.lave_dry")
    assert {e.subject for e in dry["triggers"]} == {"sensor.lave_power"}
    assert {e.subject for e in dry["guards"]} == {
        "input_boolean.lave", "input_select.phase_lave"
    }
    assert dry["action_metadata"]["option"] == "Séchage"


def test_laundry_end_stops_running_and_sets_arret():
    graph = _graph([], ROWS)
    stopped = graph.automation_context_for("input_boolean.lave", effect="turn_off")
    assert [x["automation_id"] for x in stopped] == ["automation.lave_end"]
    phase = graph.automation_context_for("input_select.phase_lave", effect="select_option")
    end = next(x for x in phase if x["automation_id"] == "automation.lave_end")
    assert end["action_metadata"]["option"] == "Arrêt"


def test_natural_name_resolution_is_limited_to_current_ha_objects():
    graph = _graph([], ROWS)
    assert graph.resolve_object("lampe salle de bain") == ["light.sdb"]
    assert graph.resolve_object("volet salon") == ["cover.salon"]


def test_opaque_registry_reference_stays_unresolved_and_is_never_guessed():
    rows = [_auto("Charge appareil", """
alias: Charge appareil
triggers:
  - type: turned_on
    device_id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    entity_id: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
    domain: binary_sensor
    trigger: device
actions:
  - type: turn_on
    device_id: cccccccccccccccccccccccccccccccc
    entity_id: dddddddddddddddddddddddddddddddd
    domain: switch
""")]
    graph = build_operational_graph(
        HA_HEADER,
        [
            ["automation.charge", "automation", "Charge appareil", "on"],
            ["switch.appareil", "switch", "Prise appareil", "off"],
        ],
        AUTO_HEADER,
        rows,
    )
    assert graph.automation_context_for("switch.appareil", effect="turn_on") == []
    assert any(
        e.relation == "ACTS_ON" and e.object.startswith("registry_ref:")
        for e in graph.edges
    )
