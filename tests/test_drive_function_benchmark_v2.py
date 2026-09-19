import json

from elise_memory.engine_v2 import (
    AutomationDoc,
    EntityRecord,
    build_operational_graph,
    reconcile_automations,
    retrieve_automation_behavior,
    retrieve_automation_chains,
    retrieve_triggered_chains,
)


ENTITIES = [
    EntityRecord("automation.hotte", "automation", "Allumer hotte selon présence", "on"),
    EntityRecord("automation.tineco_on", "automation", "Allume prise tineco si utilisation", "on"),
    EntityRecord("automation.tineco_off", "automation", "Couper prise Tineco quand charge terminée", "on"),
    EntityRecord("automation.clim_fenetre", "automation", "Désactivation intelligente de la clim si fenêtre salon ouverte", "on"),
    EntityRecord("automation.yaourt", "automation", "Aaaayaourt", "on"),
    EntityRecord("automation.lave_start", "automation", "Lave-linge - Début de cycle", "on"),
    EntityRecord("automation.lave_rinse", "automation", "Lave-linge - Passage au rinçage", "on"),
    EntityRecord("automation.lave_dry", "automation", "Lave-linge - Passage au séchage", "on"),
    EntityRecord("automation.lave_end", "automation", "Lave-linge - Fin de cycle", "on"),
    EntityRecord("binary_sensor.motion_hotte", "binary_sensor", "Mouvement hotte", "off"),
    EntityRecord("switch.awake", "switch", "Prise de comptage", "on"),
    EntityRecord("input_boolean.cinema", "input_boolean", "Mode cinéma", "off"),
    EntityRecord("light.hotte", "light", "Hotte", "off"),
    EntityRecord("binary_sensor.tineco_online", "binary_sensor", "Tineco online", "off"),
    EntityRecord("sensor.tempo_color", "sensor", "Couleur Tempo", "Bleu"),
    EntityRecord("sensor.tineco_battery", "sensor", "Tineco Battery", "90"),
    EntityRecord("switch.tineco", "switch", "Tineco", "off"),
    EntityRecord("binary_sensor.fenetre", "binary_sensor", "Fenêtre salon", "off"),
    EntityRecord("climate.salon", "climate", "Clim salon", "cool"),
    EntityRecord("sensor.temp_fenetre", "sensor", "Température fenêtre salon", "20"),
    EntityRecord("sensor.temp_interieur", "sensor", "Température intérieure salon", "21"),
    EntityRecord("switch.yaourtiere", "switch", "Yaourtière", "on"),
    EntityRecord("sensor.lave_power", "sensor", "Puissance prise lave-linge", "0"),
    EntityRecord("input_boolean.lave", "input_boolean", "Lave-linge en cours", "off"),
    EntityRecord("input_select.phase", "input_select", "Phase lave-linge", "Arrêt"),
]


DOCS = [
    AutomationDoc(
        "Allumer hotte selon présence",
        """
alias: Allumer hotte selon présence
triggers:
  - trigger: state
    entity_id: binary_sensor.motion_hotte
    from: "off"
    to: "on"
conditions:
  - condition: state
    entity_id: switch.awake
    state: "on"
  - condition: state
    entity_id: input_boolean.cinema
    state: "off"
actions:
  - variables:
      heure: "{{ now().hour }}"
  - choose:
      - conditions:
          - condition: template
            value_template: "{{ 10 <= heure < 21 }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: light.hotte
            data:
              brightness_pct: 100
              color_temp_kelvin: 4500
      - conditions:
          - condition: template
            value_template: "{{ heure >= 21 or heure < 10 }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: light.hotte
            data:
              brightness_pct: 50
              color_temp_kelvin: 6500
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.motion_hotte
        to: "off"
        for: "00:05:00"
  - action: light.turn_off
    target:
      entity_id: light.hotte
mode: restart
""",
        "Validée",
        58,
    ),
    AutomationDoc(
        "Allume prise tineco si utilisation",
        """
alias: Allume prise tineco si utilisation
triggers:
  - trigger: state
    entity_id: binary_sensor.tineco_online
    to: "on"
conditions:
  - condition: state
    entity_id: sensor.tempo_color
    state: [Bleu, Blanc]
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.tineco
""",
        "Validée",
        52,
    ),
    AutomationDoc(
        "Couper prise Tineco quand charge terminée",
        """
alias: Couper prise Tineco quand charge terminée
triggers:
  - trigger: numeric_state
    entity_id: sensor.tineco_battery
    above: 99.9
actions:
  - action: switch.turn_off
    target:
      entity_id: switch.tineco
  - action: notify.mobile_app_phone
    data:
      message: "Chargé"
""",
        "Validée",
        55,
    ),
    AutomationDoc(
        "Désactivation intelligente de la clim si fenêtre salon ouverte",
        """
alias: Désactivation intelligente de la clim si fenêtre salon ouverte
triggers:
  - trigger: state
    entity_id: binary_sensor.fenetre
    to: "on"
actions:
  - choose:
      - conditions:
          - condition: template
            value_template: "{{ states('climate.salon') == 'cool' and states('sensor.temp_fenetre') | float(0) > states('sensor.temp_interieur') | float(0) }}"
        sequence:
          - action: climate.set_hvac_mode
            target:
              entity_id: climate.salon
            data:
              hvac_mode: "off"
      - conditions:
          - condition: template
            value_template: "{{ states('climate.salon') == 'heat' and states('sensor.temp_fenetre') | float(0) < states('sensor.temp_interieur') | float(0) }}"
        sequence:
          - action: climate.set_hvac_mode
            target:
              entity_id: climate.salon
            data:
              hvac_mode: "off"
""",
        "À vérifier",
        87,
    ),
    AutomationDoc(
        "Aaaayaourt",
        """
alias: Aaaayaourt
triggers:
  - trigger: state
    entity_id: switch.yaourtiere
    from: "off"
    to: "on"
actions:
  - delay: "12:00:00"
  - action: switch.turn_off
    target:
      entity_id: switch.yaourtiere
mode: restart
""",
        "Installée",
        54,
    ),
    AutomationDoc(
        "Lave-linge - Début de cycle",
        """
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
    target:
      entity_id: input_boolean.lave
  - action: input_select.select_option
    target:
      entity_id: input_select.phase
    data:
      option: Lavage
""",
        "Validé terrain",
        189,
    ),
    AutomationDoc(
        "Lave-linge - Passage au rinçage",
        """
alias: Lave-linge - Passage au rinçage
triggers:
  - trigger: state
    entity_id: input_boolean.lave
    to: "on"
    for:
      minutes: 45
conditions:
  - condition: state
    entity_id: input_select.phase
    state: Lavage
actions:
  - action: input_select.select_option
    target:
      entity_id: input_select.phase
    data:
      option: Rinçage
""",
        "Validé terrain",
        190,
    ),
    AutomationDoc(
        "Lave-linge - Passage au séchage",
        """
alias: Lave-linge - Passage au séchage
triggers:
  - trigger: numeric_state
    entity_id: sensor.lave_power
    above: 1100
    for:
      minutes: 2
conditions:
  - condition: state
    entity_id: input_boolean.lave
    state: "on"
  - condition: state
    entity_id: input_select.phase
    state: Rinçage
actions:
  - action: input_select.select_option
    target:
      entity_id: input_select.phase
    data:
      option: Séchage
""",
        "Validé terrain",
        191,
    ),
    AutomationDoc(
        "Lave-linge - Fin de cycle",
        """
alias: Lave-linge - Fin de cycle
triggers:
  - trigger: numeric_state
    entity_id: sensor.lave_power
    below: 5
    for:
      minutes: 3
conditions:
  - condition: state
    entity_id: input_boolean.lave
    state: "on"
actions:
  - action: input_boolean.turn_off
    target:
      entity_id: input_boolean.lave
  - action: input_select.select_option
    target:
      entity_id: input_select.phase
    data:
      option: Arrêt
""",
        "Validé terrain",
        192,
    ),
]


def _engine():
    reconciliation = reconcile_automations(ENTITIES, DOCS)
    graph = build_operational_graph(reconciliation)
    return reconciliation, graph


def test_drive_hotte_turn_on_and_delayed_turn_off_are_separate_effects():
    reconciliation, graph = _engine()
    on = retrieve_automation_chains("qu'est-ce qui allume la hotte", ENTITIES, reconciliation, graph)
    off = retrieve_automation_chains("qu'est-ce qui éteint la hotte", ENTITIES, reconciliation, graph)
    assert [x["automation_entity_id"] for x in on] == ["automation.hotte"]
    assert [x["automation_entity_id"] for x in off] == ["automation.hotte"]
    assert all(c["predicate"] != "WAITS_FOR" for c in on[0]["context"])
    assert any(c["predicate"] == "WAITS_FOR" for c in off[0]["context"])


def test_drive_tineco_online_turns_on_only_tineco_switch():
    reconciliation, graph = _engine()
    result = retrieve_triggered_chains(
        "quand Tineco online passe à on", ENTITIES, reconciliation, graph
    )
    item = next(x for x in result if x["automation_entity_id"] == "automation.tineco_on")
    assert item["target"] == "switch.tineco"
    assert item["effect"] == "turn_on"


def test_drive_tineco_full_battery_turns_socket_off():
    reconciliation, graph = _engine()
    result = retrieve_triggered_chains(
        "quand la batterie Tineco atteint 100", ENTITIES, reconciliation, graph
    )
    item = next(x for x in result if x["automation_entity_id"] == "automation.tineco_off")
    assert item["target"] == "switch.tineco"
    assert item["effect"] == "turn_off"
    assert item["trigger_detail"]["above"] == 99.9


def test_drive_climate_window_rule_keeps_template_guard_entities_in_branch():
    reconciliation, graph = _engine()
    behavior = retrieve_automation_behavior(
        "Désactivation intelligente de la clim si fenêtre salon ouverte",
        reconciliation,
        graph,
    )[0]
    assert {x["subject"] for x in behavior["triggers"]} == {"binary_sensor.fenetre"}
    assert {x["object"] for x in behavior["actions"]} == {"climate.salon"}
    local_subjects = {x["subject"] for x in behavior["local_guards"]}
    assert {"climate.salon", "sensor.temp_fenetre", "sensor.temp_interieur"} <= local_subjects


def test_drive_yaourt_waits_12_hours_before_power_off():
    reconciliation, graph = _engine()
    result = retrieve_automation_chains(
        "qu'est-ce qui éteint la yaourtière", ENTITIES, reconciliation, graph
    )
    item = next(x for x in result if x["automation_entity_id"] == "automation.yaourt")
    assert item["effect"] == "turn_off"
    assert any("12:00:00" in b["object"] for b in item["barriers"])


def test_drive_laundry_start_flow_is_power_to_running_and_lavage():
    reconciliation, graph = _engine()
    behavior = retrieve_automation_behavior("Lave-linge - Début de cycle", reconciliation, graph)[0]
    assert behavior["triggers"][0]["subject"] == "sensor.lave_power"
    assert behavior["triggers"][0]["detail"]["above"] == 20
    actions = {(x["object"], x["detail"].get("effect")) for x in behavior["actions"]}
    assert ("input_boolean.lave", "turn_on") in actions
    assert ("input_select.phase", "select_option") in actions


def test_drive_laundry_rinse_keeps_45_min_trigger_duration():
    reconciliation, graph = _engine()
    behavior = retrieve_automation_behavior("Lave-linge - Passage au rinçage", reconciliation, graph)[0]
    assert behavior["triggers"][0]["detail"]["duration"] == {"minutes": 45}
    assert behavior["guards"][0]["subject"] == "input_select.phase"


def test_drive_laundry_dry_keeps_power_threshold_duration_and_phase_guard():
    reconciliation, graph = _engine()
    behavior = retrieve_automation_behavior("Lave-linge - Passage au séchage", reconciliation, graph)[0]
    trigger = behavior["triggers"][0]
    assert trigger["subject"] == "sensor.lave_power"
    assert trigger["detail"]["above"] == 1100
    assert trigger["detail"]["duration"] == {"minutes": 2}
    assert {x["subject"] for x in behavior["guards"]} == {"input_boolean.lave", "input_select.phase"}


def test_drive_laundry_end_keeps_below_5_for_3min_and_two_final_actions():
    reconciliation, graph = _engine()
    behavior = retrieve_automation_behavior("Lave-linge - Fin de cycle", reconciliation, graph)[0]
    trigger = behavior["triggers"][0]
    assert trigger["detail"]["below"] == 5
    assert trigger["detail"]["duration"] == {"minutes": 3}
    actions = {(x["object"], x["detail"].get("effect")) for x in behavior["actions"]}
    assert ("input_boolean.lave", "turn_off") in actions
    assert ("input_select.phase", "select_option") in actions
