import json

from elise_memory.engine_v2 import (
    AutomationDoc,
    EntityRecord,
    RegistryBinding,
    build_operational_graph,
    reconcile_automations,
    retrieve_automation_behavior,
    retrieve_automation_chains,
    retrieve_triggered_chains,
    resolve_registry_edges,\n    resolve_entities,
)


ENTITIES = [
    EntityRecord("automation.hotte", "automation", "Allumer hotte selon présence", "on"),
    EntityRecord("automation.entree_presence", "automation", "Allumer lampe entrée selon l\'heure et la présence", "on"),
    EntityRecord("automation.entree_unlock", "automation", "Allumer lampe entrée lors déverrouillage porte", "on"),
    EntityRecord("automation.sdb_presence", "automation", "Allumer salle de bain selon l\'heure et la présence", "on"),
    EntityRecord("automation.tineco_on", "automation", "Allume prise tineco si utilisation", "on"),
    EntityRecord("automation.tineco_off", "automation", "Couper prise Tineco quand charge terminée", "on"),
    EntityRecord("automation.clim_fenetre", "automation", "Désactivation intelligente de la clim si fenêtre salon ouverte", "on"),
    EntityRecord("automation.yaourt", "automation", "Aaaayaourt", "on"),
    EntityRecord("automation.lave_start", "automation", "Lave-linge - Début de cycle", "on"),
    EntityRecord("automation.lave_rinse", "automation", "Lave-linge - Passage au rinçage", "on"),
    EntityRecord("automation.lave_dry", "automation", "Lave-linge - Passage au séchage", "on"),
    EntityRecord("automation.lave_end", "automation", "Lave-linge - Fin de cycle", "on"),
    EntityRecord("binary_sensor.motion_hotte", "binary_sensor", "Mouvement hotte", "off"),
    EntityRecord("binary_sensor.entree_motion", "binary_sensor", "Mouvement entrée", "off"),
    EntityRecord("binary_sensor.sdb_motion", "binary_sensor", "Mouvement salle de bain", "off"),
    EntityRecord("lock.porte_dentree", "lock", "Porte d\'entrée", "locked"),
    EntityRecord("light.entree", "light", "Lampe entrée", "off"),
    EntityRecord("light.sdb", "light", "Lampe salle de bain", "off"),
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
        "Allumer lampe entrée selon l'heure et la présence",
        """
alias: Allumer lampe entrée selon l'heure et la présence
triggers:
  - trigger: state
    entity_id: binary_sensor.entree_motion
    from: "off"
    to: "on"
  - trigger: state
    entity_id: lock.porte_dentree
    from: locked
    to: unlocked
conditions:
  - condition: state
    entity_id: switch.awake
    state: "on"
  - condition: state
    entity_id: input_boolean.cinema
    state: "off"
actions:
  - action: light.turn_on
    target:
      entity_id: light.entree
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.entree_motion
        to: "off"
        for: "00:02:00"
  - action: light.turn_off
    target:
      entity_id: light.entree
mode: restart
""",
        "Validée",
        18,
    ),
    AutomationDoc(
        "Allumer lampe entrée lors déverrouillage porte",
        """
alias: Allumer lampe entrée lors déverrouillage porte
triggers:
  - trigger: state
    entity_id: lock.porte_dentree
    to: unlocked
actions:
  - action: light.turn_on
    target:
      entity_id: light.entree
mode: single
""",
        "Validée",
        57,
    ),
    AutomationDoc(
        "Allumer salle de bain selon l'heure et la présence",
        """
alias: Allumer salle de bain selon l'heure et la présence
triggers:
  - trigger: state
    entity_id: binary_sensor.sdb_motion
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
  - action: light.turn_on
    target:
      entity_id: light.sdb
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.sdb_motion
        to: "off"
        for: "00:05:00"
  - action: light.turn_off
    target:
      entity_id: light.sdb
mode: restart
""",
        "Validée",
        19,
    ),
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


def test_drive_entry_light_unlock_is_a_real_trigger_not_window_opening():
    reconciliation, graph = _engine()
    result = retrieve_triggered_chains(
        "quand la porte d'entrée se déverrouille", ENTITIES, reconciliation, graph
    )
    entry = [x for x in result if x["target"] == "light.entree" and x["effect"] == "turn_on"]
    assert {x["automation_entity_id"] for x in entry} == {
        "automation.entree_presence",
        "automation.entree_unlock",
    }
    assert all(x["source_entity_id"] == "lock.porte_dentree" for x in entry)


def test_drive_entry_light_does_not_invent_window_opening_as_trigger():
    reconciliation, graph = _engine()
    result = retrieve_triggered_chains(
        "quand la fenêtre s'ouvre", ENTITIES, reconciliation, graph
    )
    assert not any(x["target"] == "light.entree" for x in result)


def test_drive_bathroom_light_is_motion_driven_and_has_no_unlock_trigger():
    reconciliation, graph = _engine()
    motion = retrieve_triggered_chains(
        "quand il y a du mouvement dans la salle de bain", ENTITIES, reconciliation, graph
    )
    assert any(
        x["automation_entity_id"] == "automation.sdb_presence"
        and x["target"] == "light.sdb"
        and x["effect"] == "turn_on"
        for x in motion
    )
    unlock = retrieve_triggered_chains(
        "quand la porte d'entrée se déverrouille", ENTITIES, reconciliation, graph
    )
    assert not any(x["target"] == "light.sdb" for x in unlock)


def test_drive_climate_window_rule_answers_explicit_power_off_question():
    reconciliation, graph = _engine()
    result = retrieve_automation_chains(
        "qu'est-ce qui éteint la clim salon",
        ENTITIES,
        reconciliation,
        graph,
    )
    item = next(
        x for x in result
        if x["automation_entity_id"] == "automation.clim_fenetre"
    )
    assert item["target_entity_id"] == "climate.salon"
    assert item["effect"] == "turn_off"
    assert item["action_detail"]["data"]["hvac_mode"] == "off"


def test_drive_real_salon_window_device_trigger_requires_exact_registry_binding():
    entities = [
        EntityRecord("automation.salon_window_open", "automation", "Ouverture volet salon par ouverture de la fenetre", "on"),
        EntityRecord("binary_sensor.fenetre_porte_contact", "binary_sensor", "Fenêtre salon", "off"),
        EntityRecord("cover.volet_salon_2", "cover", "Volet salon", "closed"),
    ]
    docs = [
        AutomationDoc(
            "Ouverture volet salon par ouverture de la fenetre",
            """
alias: Ouverture volet salon par ouverture de la fenetre
triggers:
  - type: opened
    device_id: 772d73c850b0f8ccebc9955a857c0947
    entity_id: bf61804c3ebdbc2f9832e66344ec19d8
    domain: binary_sensor
    trigger: device
conditions: []
actions:
  - action: cover.set_cover_position
    target:
      entity_id: cover.volet_salon_2
    data:
      position: 100
mode: single
""",
            "Installée",
            7,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)

    unresolved = retrieve_triggered_chains(
        "quand la fenêtre salon s'ouvre", entities, reconciliation, graph
    )
    assert unresolved == []

    resolved = resolve_registry_edges(
        graph,
        entities,
        [
            RegistryBinding(
                "bf61804c3ebdbc2f9832e66344ec19d8",
                "binary_sensor.fenetre_porte_contact",
                "ha_entity_registry_readonly",
            )
        ],
    )
    result = retrieve_triggered_chains(
        "quand la fenêtre salon s'ouvre", entities, reconciliation, resolved
    )
    item = next(x for x in result if x["automation_entity_id"] == "automation.salon_window_open")
    assert item["source_entity_id"] == "binary_sensor.fenetre_porte_contact"
    assert item["target"] == "cover.volet_salon_2"
    assert item["effect"] == "open"
    assert item["action_detail"]["data"]["position"] == 100


def test_drive_real_entry_unlock_is_a_trigger_not_a_textual_association():
    entities = [
        EntityRecord("automation.entree", "automation", "Allumer lampe entrée selon l'heure et la présence", "on"),
        EntityRecord("lock.porte_dentree", "lock", "Porte d'entrée", "locked"),
        EntityRecord("binary_sensor.eclairement_entree_mouvement", "binary_sensor", "Mouvement entrée", "off"),
        EntityRecord("switch.prise_de_comptage_prise_1", "switch", "Prise de comptage", "on"),
        EntityRecord("input_boolean.mode_cinema", "input_boolean", "Mode cinéma", "off"),
        EntityRecord("light.hue_tento_color_panel_1_2", "light", "Lampe entrée", "off"),
    ]
    docs = [
        AutomationDoc(
            "Allumer lampe entrée selon l'heure et la présence",
            """
alias: Allumer lampe entrée selon l'heure et la présence
triggers:
  - trigger: state
    entity_id: binary_sensor.eclairement_entree_mouvement
    from: "off"
    to: "on"
  - trigger: state
    entity_id: lock.porte_dentree
    from: locked
    to: unlocked
conditions:
  - condition: state
    entity_id: switch.prise_de_comptage_prise_1
    state: "on"
  - condition: state
    entity_id: input_boolean.mode_cinema
    state: "off"
actions:
  - action: light.turn_on
    target:
      entity_id: light.hue_tento_color_panel_1_2
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.eclairement_entree_mouvement
        to: "off"
        for: "00:02:00"
  - action: light.turn_off
    target:
      entity_id: light.hue_tento_color_panel_1_2
mode: restart
""",
            "Installée",
            18,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    result = retrieve_triggered_chains(
        "quand la porte d'entrée est déverrouillée", entities, reconciliation, graph
    )
    on = next(
        x for x in result
        if x["automation_entity_id"] == "automation.entree"
        and x["effect"] == "turn_on"
    )
    assert on["source_entity_id"] == "lock.porte_dentree"
    assert on["target"] == "light.hue_tento_color_panel_1_2"


def test_drive_real_bathroom_motion_keeps_delayed_off_separate():
    entities = [
        EntityRecord("automation.sdb", "automation", "Allumer salle de bain selon l'heure et la présence", "on"),
        EntityRecord("binary_sensor.salle_de_bain_mouvement", "binary_sensor", "Mouvement salle de bain", "off"),
        EntityRecord("switch.prise_de_comptage_prise_1", "switch", "Prise de comptage", "on"),
        EntityRecord("input_boolean.mode_cinema", "input_boolean", "Mode cinéma", "off"),
        EntityRecord("light.hue_tento_color_panel_1", "light", "Lampe salle de bain", "off"),
    ]
    docs = [
        AutomationDoc(
            "Allumer salle de bain selon l'heure et la présence",
            """
alias: Allumer salle de bain selon l'heure et la présence
triggers:
  - trigger: state
    entity_id: binary_sensor.salle_de_bain_mouvement
    from: "off"
    to: "on"
conditions:
  - condition: state
    entity_id: switch.prise_de_comptage_prise_1
    state: "on"
  - condition: state
    entity_id: input_boolean.mode_cinema
    state: "off"
actions:
  - action: light.turn_on
    target:
      entity_id: light.hue_tento_color_panel_1
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.salle_de_bain_mouvement
        to: "off"
        for: "00:05:00"
  - action: light.turn_off
    target:
      entity_id: light.hue_tento_color_panel_1
mode: restart
""",
            "Validée",
            19,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    on = retrieve_automation_chains(
        "qu'est-ce qui allume la lampe salle de bain", entities, reconciliation, graph
    )[0]
    off = retrieve_automation_chains(
        "qu'est-ce qui éteint la lampe salle de bain", entities, reconciliation, graph
    )[0]
    assert on["effect"] == "turn_on"
    assert all(x["predicate"] != "WAITS_FOR" for x in on["context"])
    assert off["effect"] == "turn_off"
    assert any(x["predicate"] == "WAITS_FOR" for x in off["context"])


def test_drive_toothbrush_device_refs_fail_closed_without_registry_binding():
    entities = [
        EntityRecord("automation.brosse", "automation", "Charge brosse a dents", "on"),
        EntityRecord("switch.prise_brosse_a_dents", "switch", "Prise brosse à dents", "off"),
    ]
    docs = [
        AutomationDoc(
            "Charge brosse a dents",
            """
alias: Charge brosse a dents
triggers:
  - type: turned_on
    device_id: 4701856ed53837e3faad630b61748b34
    entity_id: cf345283d35e599d1ff60b259fb0feea
    domain: binary_sensor
    trigger: device
actions:
  - type: turn_on
    device_id: 88487e31d9bc6603ca82290260a2b744
    entity_id: ecc064f6a122f211021b5f6d6149dbfe
    domain: switch
  - delay:
      hours: 1
      seconds: 1
  - type: turn_off
    device_id: 88487e31d9bc6603ca82290260a2b744
    entity_id: ecc064f6a122f211021b5f6d6149dbfe
    domain: switch
mode: single
""",
            "Validée",
            43,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    # The Drive production uses opaque registry refs. A friendly-name match must
    # never fabricate the missing trigger/target binding.
    assert retrieve_triggered_chains(
        "quand la brosse à dents est utilisée", entities, reconciliation, graph
    ) == []
    assert retrieve_automation_chains(
        "qu'est-ce qui allume la prise brosse à dents", entities, reconciliation, graph
    ) == []


def test_drive_toothbrush_exact_registry_bindings_restore_on_and_delayed_off():
    entities = [
        EntityRecord("automation.brosse", "automation", "Charge brosse a dents", "on"),
        EntityRecord("binary_sensor.brosse_utilisee", "binary_sensor", "Brosse utilisée", "off"),
        EntityRecord("switch.prise_brosse_a_dents", "switch", "Prise brosse à dents", "off"),
    ]
    docs = [
        AutomationDoc(
            "Charge brosse a dents",
            """
alias: Charge brosse a dents
triggers:
  - type: turned_on
    device_id: 4701856ed53837e3faad630b61748b34
    entity_id: cf345283d35e599d1ff60b259fb0feea
    domain: binary_sensor
    trigger: device
actions:
  - type: turn_on
    device_id: 88487e31d9bc6603ca82290260a2b744
    entity_id: ecc064f6a122f211021b5f6d6149dbfe
    domain: switch
  - delay:
      hours: 1
      seconds: 1
  - type: turn_off
    device_id: 88487e31d9bc6603ca82290260a2b744
    entity_id: ecc064f6a122f211021b5f6d6149dbfe
    domain: switch
mode: single
""",
            "Validée",
            43,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    resolved = resolve_registry_edges(
        graph,
        entities,
        [
            RegistryBinding(
                "cf345283d35e599d1ff60b259fb0feea",
                "binary_sensor.brosse_utilisee",
                "ha_entity_registry_readonly",
            ),
            RegistryBinding(
                "ecc064f6a122f211021b5f6d6149dbfe",
                "switch.prise_brosse_a_dents",
                "ha_entity_registry_readonly",
            ),
        ],
    )
    on = retrieve_automation_chains(
        "qu'est-ce qui allume la prise brosse à dents", entities, reconciliation, resolved
    )[0]
    off = retrieve_automation_chains(
        "qu'est-ce qui éteint la prise brosse à dents", entities, reconciliation, resolved
    )[0]
    assert on["effect"] == "turn_on"
    assert any(x["subject"] == "binary_sensor.brosse_utilisee" and x["predicate"] == "TRIGGERS" for x in on["context"])
    assert on["barriers"] == []
    assert off["effect"] == "turn_off"
    assert any(x["detail"].get("kind") == "delay" and x["detail"].get("duration", {}).get("hours") == 1 for x in off["barriers"])


def test_drive_salon_window_opening_requires_exact_opaque_trigger_identity():
    entities = [
        EntityRecord("automation.salon_window_open", "automation", "Ouverture volet salon par ouverture de la fenetre", "on"),
        EntityRecord("binary_sensor.fenetre_porte_contact", "binary_sensor", "Fenêtre salon", "off"),
        EntityRecord("cover.volet_salon_2", "cover", "Volet salon", "closed"),
    ]
    docs = [
        AutomationDoc(
            "Ouverture volet salon par ouverture de la fenetre",
            """
alias: Ouverture volet salon par ouverture de la fenetre
triggers:
  - type: opened
    device_id: 772d73c850b0f8ccebc9955a857c0947
    entity_id: bf61804c3ebdbc2f9832e66344ec19d8
    domain: binary_sensor
    trigger: device
conditions: []
actions:
  - action: cover.set_cover_position
    target:
      entity_id: cover.volet_salon_2
    data:
      position: 100
mode: single
""",
            "Installée",
            7,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    # Drive's production trigger is opaque. The visible friendly window entity
    # is not enough evidence to bind it.
    assert retrieve_triggered_chains(
        "quand la fenêtre salon s'ouvre", entities, reconciliation, graph
    ) == []
    resolved = resolve_registry_edges(
        graph,
        entities,
        [
            RegistryBinding(
                "bf61804c3ebdbc2f9832e66344ec19d8",
                "binary_sensor.fenetre_porte_contact",
                "ha_entity_registry_readonly",
            )
        ],
    )
    result = retrieve_triggered_chains(
        "quand la fenêtre salon s'ouvre", entities, reconciliation, resolved
    )
    item = next(x for x in result if x["automation_entity_id"] == "automation.salon_window_open")
    assert item["target"] == "cover.volet_salon_2"
    assert item["effect"] == "open"
    assert item["action_detail"]["data"]["position"] == 100


def test_drive_salon_window_closing_at_night_is_close_not_open():
    entities = [
        EntityRecord("automation.salon_night_close", "automation", "Fermer volet salon si fenêtre fermée et nuit entre coucher+40min et lever soleil", "on"),
        EntityRecord("binary_sensor.fenetre_porte_contact", "binary_sensor", "Fenêtre salon", "off"),
        EntityRecord("cover.volet_salon_2", "cover", "Volet salon", "open"),
    ]
    docs = [
        AutomationDoc(
            "Fermer volet salon si fenêtre fermée et nuit entre coucher+40min et lever soleil",
            """
alias: Fermer volet salon si fenêtre fermée et nuit entre coucher+40min et lever soleil
triggers:
  - trigger: state
    entity_id: binary_sensor.fenetre_porte_contact
    from: "on"
    to: "off"
conditions:
  - condition: sun
    after: sunset
    after_offset: "00:40:00"
    before: sunrise
actions:
  - action: cover.close_cover
    target:
      entity_id: cover.volet_salon_2
mode: single
""",
            "Installée",
            2,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    result = retrieve_triggered_chains(
        "quand la fenêtre salon se ferme", entities, reconciliation, graph
    )
    item = next(x for x in result if x["automation_entity_id"] == "automation.salon_night_close")
    assert item["target"] == "cover.volet_salon_2"
    assert item["effect"] == "close"
    assert item["trigger_detail"]["from_state"] == "on"
    assert item["trigger_detail"]["to_state"] == "off"
    assert not any(x["effect"] in {"open_cover", "set_cover_position"} for x in result)


def test_drive_terrace_door_opening_is_distinct_from_night_closing():
    entities = [
        EntityRecord("automation.terrace_open", "automation", "Ouverture volet terrasse lors de l'ouverture de la porte fenetre", "on"),
        EntityRecord("automation.terrace_night_close", "automation", "Fermer volet terrasse si porte-fenêtre fermée et nuit entre coucher+40min et lever soleil", "on"),
        EntityRecord("binary_sensor.porte_fenetre_contact", "binary_sensor", "Porte-fenêtre terrasse", "off"),
        EntityRecord("cover.volet_terrasse_2", "cover", "Volet terrasse", "closed"),
    ]
    docs = [
        AutomationDoc(
            "Ouverture volet terrasse lors de l'ouverture de la porte fenetre",
            """
alias: Ouverture volet terrasse lors de l'ouverture de la porte fenetre
triggers:
  - type: opened
    device_id: f545c717df97e81c69c8428f548ff253
    entity_id: 1a4de6d440f46c93928edd5ccab04c4d
    domain: binary_sensor
    trigger: device
conditions: []
actions:
  - action: cover.set_cover_position
    target:
      entity_id: cover.volet_terrasse_2
    data:
      position: 100
mode: single
""",
            "Installée",
            8,
        ),
        AutomationDoc(
            "Fermer volet terrasse si porte-fenêtre fermée et nuit entre coucher+40min et lever soleil",
            """
alias: Fermer volet terrasse si porte-fenêtre fermée et nuit entre coucher+40min et lever soleil
triggers:
  - trigger: state
    entity_id: binary_sensor.porte_fenetre_contact
    from: "on"
    to: "off"
conditions:
  - condition: sun
    after: sunset
    after_offset: "00:40:00"
    before: sunrise
  - condition: numeric_state
    entity_id: cover.volet_terrasse_2
    attribute: current_position
    above: 2
actions:
  - action: cover.close_cover
    target:
      entity_id: cover.volet_terrasse_2
mode: single
""",
            "Installée",
            3,
        ),
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)

    # The open path is opaque in Drive and must remain unresolved until an exact
    # read-only registry binding is supplied.
    open_unresolved = retrieve_triggered_chains(
        "quand la porte-fenêtre terrasse s'ouvre", entities, reconciliation, graph
    )
    assert not any(x["automation_entity_id"] == "automation.terrace_open" for x in open_unresolved)

    resolved = resolve_registry_edges(
        graph,
        entities,
        [
            RegistryBinding(
                "1a4de6d440f46c93928edd5ccab04c4d",
                "binary_sensor.porte_fenetre_contact",
                "ha_entity_registry_readonly",
            )
        ],
    )
    opened = retrieve_triggered_chains(
        "quand la porte-fenêtre terrasse s'ouvre", entities, reconciliation, resolved
    )
    opened_item = next(x for x in opened if x["automation_entity_id"] == "automation.terrace_open")
    assert opened_item["target"] == "cover.volet_terrasse_2"
    assert opened_item["effect"] == "open"
    assert opened_item["action_detail"]["data"]["position"] == 100

    closed = retrieve_triggered_chains(
        "quand la porte-fenêtre terrasse se ferme", entities, reconciliation, resolved
    )
    close_item = next(x for x in closed if x["automation_entity_id"] == "automation.terrace_night_close")
    assert close_item["effect"] == "close"
    assert close_item["trigger_detail"]["from_state"] == "on"
    assert close_item["trigger_detail"]["to_state"] == "off"
    assert close_item["target"] == "cover.volet_terrasse_2"


def test_drive_terrace_weather_guards_are_not_promoted_to_triggers():
    entities = [
        EntityRecord("automation.terrace_weather", "automation", "Gestion volet terrasse selon la météo", "on"),
        EntityRecord("sensor.temperature_exterieure_fiable", "sensor", "Température extérieure fiable", "20"),
        EntityRecord("binary_sensor.porte_fenetre_contact", "binary_sensor", "Porte-fenêtre terrasse", "off"),
        EntityRecord("cover.volet_terrasse_2", "cover", "Volet terrasse", "open"),
    ]
    docs = [
        AutomationDoc(
            "Gestion volet terrasse selon la météo",
            """
alias: Gestion volet terrasse selon la météo
triggers:
  - trigger: numeric_state
    entity_id: sensor.temperature_exterieure_fiable
    below: 3
    id: froid
  - trigger: numeric_state
    entity_id: sensor.temperature_exterieure_fiable
    above: 28
    id: chaud
conditions:
  - condition: state
    entity_id: binary_sensor.porte_fenetre_contact
    state: "off"
  - condition: numeric_state
    entity_id: cover.volet_terrasse_2
    attribute: current_position
    above: 2
actions:
  - choose:
      - conditions:
          - condition: trigger
            id: froid
        sequence:
          - action: cover.close_cover
            target:
              entity_id: cover.volet_terrasse_2
      - conditions:
          - condition: trigger
            id: chaud
        sequence:
          - action: cover.close_cover
            target:
              entity_id: cover.volet_terrasse_2
mode: single
""",
            "Installée",
            6,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    behavior = retrieve_automation_behavior(
        "Gestion volet terrasse selon la météo", reconciliation, graph
    )[0]
    assert {x["subject"] for x in behavior["triggers"]} == {"sensor.temperature_exterieure_fiable"}
    assert {x["subject"] for x in behavior["guards"]} == {
        "binary_sensor.porte_fenetre_contact",
        "cover.volet_terrasse_2",
    }
    # Merely opening/closing the door-window is a guard change here, not a
    # causal trigger for the weather automation.
    door = retrieve_triggered_chains(
        "quand la porte-fenêtre terrasse se ferme", entities, reconciliation, graph
    )
    assert not any(x["automation_entity_id"] == "automation.terrace_weather" for x in door)


def test_drive_tineco_on_and_off_have_different_real_causes():
    entities = [
        EntityRecord("automation.tineco_on", "automation", "Allume prise tineco si utilisation", "on"),
        EntityRecord("automation.tineco_off", "automation", "Couper prise Tineco quand charge terminée", "on"),
        EntityRecord("binary_sensor.tineco_online", "binary_sensor", "Tineco Device Tineco Online", "off"),
        EntityRecord("sensor.tineco_battery", "sensor", "Tineco Device Tineco Battery", "80"),
        EntityRecord("sensor.rte_tempo_couleur_actuelle", "sensor", "Couleur Tempo actuelle", "Bleu"),
        EntityRecord("switch.0xa4c1387da600c253", "switch", "Tineco", "off"),
    ]
    docs = [
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
    entity_id: sensor.rte_tempo_couleur_actuelle
    state:
      - Bleu
      - Blanc
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.0xa4c1387da600c253
mode: single
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
conditions: []
actions:
  - action: switch.turn_off
    target:
      entity_id: switch.0xa4c1387da600c253
mode: single
""",
            "Validée / production",
            55,
        ),
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)

    on = retrieve_automation_chains(
        "qu'est-ce qui allume la prise Tineco", entities, reconciliation, graph
    )
    on_item = next(x for x in on if x["automation_entity_id"] == "automation.tineco_on")
    assert on_item["effect"] == "turn_on"
    on_triggers = [x for x in on_item["context"] if x["predicate"] == "TRIGGERS"]\n    on_guards = [x for x in on_item["context"] if x["predicate"] == "GUARDS"]\n    assert {x["subject"] for x in on_triggers} == {"binary_sensor.tineco_online"}\n    assert {x["subject"] for x in on_guards} == {"sensor.rte_tempo_couleur_actuelle"}

    off = retrieve_automation_chains(
        "qu'est-ce qui éteint la prise Tineco", entities, reconciliation, graph
    )
    off_item = next(x for x in off if x["automation_entity_id"] == "automation.tineco_off")
    assert off_item["effect"] == "turn_off"
    off_triggers = [x for x in off_item["context"] if x["predicate"] == "TRIGGERS"]\n    assert {x["subject"] for x in off_triggers} == {"sensor.tineco_battery"}\n    assert off_triggers[0]["detail"]["above"] == 99.9


def test_drive_tineco_battery_query_prefers_precise_sensor_over_generic_switch():
    entities = [
        EntityRecord("sensor.tineco_battery", "sensor", "Tineco Device Tineco Battery", "80"),
        EntityRecord("switch.0xa4c1387da600c253", "switch", "Tineco", "off"),
        EntityRecord("sensor.tineco_model", "sensor", "Tineco Device Tineco Model", "S7 Pro"),
    ]
    ranked = resolve_entities("batterie Tineco", entities)\n    assert ranked[0][0].entity_id == "sensor.tineco_battery"\n    assert ranked[0][0].entity_id != "switch.0xa4c1387da600c253"
