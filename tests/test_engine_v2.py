import json

from elise_memory.engine_v2 import (
    AutomationDoc,
    BusinessFunctionDoc,
    EntityRecord,
    ObjectDependencyDoc,
    R8RelationDoc,
    FactType,
    SourceFact,
    SourceKind,
    build_operational_graph,
    business_context_for_entity,
    choose_preferred_fact,
    dependency_edges,
    reconcile_automations,
    reconcile_business_functions,
    r8_edges,
    r8_relations_from_rows,
    resolve_entities,
    retrieve_automation_chains,
)


def _entities():
    return [
        EntityRecord("automation.entry_main", "automation", "Entry light main", "on"),
        EntityRecord("automation.entry_unlock", "automation", "Entry light unlock", "on"),
        EntityRecord("automation.bathroom", "automation", "Bathroom light", "on"),
        EntityRecord("automation.shutter_open", "automation", "Open lounge shutter from window", "on"),
        EntityRecord("automation.shutter_night", "automation", "Close lounge shutter at night", "on"),
        EntityRecord("automation.disabled", "automation", "Legacy entry light", "off"),
        EntityRecord("light.entry", "light", "Entry lamp", "off"),
        EntityRecord("light.bathroom", "light", "Bathroom lamp", "off"),
        EntityRecord("cover.lounge", "cover", "Lounge shutter", "open"),
        EntityRecord("binary_sensor.entry_motion", "binary_sensor", "Entry motion", "off"),
        EntityRecord("binary_sensor.bathroom_motion", "binary_sensor", "Bathroom motion", "off"),
        EntityRecord("binary_sensor.window", "binary_sensor", "Lounge window", "off"),
        EntityRecord("lock.front_door", "lock", "Front door", "locked"),
        EntityRecord("switch.awake", "switch", "Awake signal", "on"),
    ]


def _docs():
    return [
        AutomationDoc(
            "Entry light main",
            """
alias: Entry light main
triggers:
  - trigger: state
    entity_id: binary_sensor.entry_motion
    from: "off"
    to: "on"
  - trigger: state
    entity_id: lock.front_door
    to: unlocked
conditions:
  - condition: state
    entity_id: switch.awake
    state: "on"
actions:
  - action: light.turn_on
    target:
      entity_id: light.entry
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.entry_motion
        to: "off"
        for: "00:02:00"
  - action: light.turn_off
    target:
      entity_id: light.entry
""",
            "Validated",
            10,
        ),
        AutomationDoc(
            "Entry light unlock",
            """
alias: Entry light unlock
triggers:
  - trigger: state
    entity_id: lock.front_door
    to: unlocked
actions:
  - action: light.turn_on
    target:
      entity_id: light.entry
""",
            "Validated",
            11,
        ),
        AutomationDoc(
            "Bathroom light",
            """
alias: Bathroom light
triggers:
  - trigger: state
    entity_id: binary_sensor.bathroom_motion
    from: "off"
    to: "on"
actions:
  - choose:
      - conditions:
          - condition: state
            entity_id: switch.awake
            state: "on"
        sequence:
          - action: light.turn_on
            target:
              entity_id: light.bathroom
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.bathroom_motion
        to: "off"
        for: "00:05:00"
  - action: light.turn_off
    target:
      entity_id: light.bathroom
""",
            "Validated",
            12,
        ),
        AutomationDoc(
            "Open lounge shutter from window",
            """
alias: Open lounge shutter from window
triggers:
  - trigger: state
    entity_id: binary_sensor.window
    from: "off"
    to: "on"
actions:
  - action: cover.set_cover_position
    target:
      entity_id: cover.lounge
    data:
      position: 100
""",
            "Installed",
            13,
        ),
        AutomationDoc(
            "Close lounge shutter at night",
            """
alias: Close lounge shutter at night
triggers:
  - trigger: sun
    event: sunset
conditions:
  - condition: state
    entity_id: binary_sensor.window
    state: "off"
actions:
  - action: cover.close_cover
    target:
      entity_id: cover.lounge
""",
            "Installed",
            14,
        ),
        AutomationDoc(
            "Legacy entry light",
            """
alias: Legacy entry light
triggers:
  - trigger: time
    at: "20:00:00"
actions:
  - action: light.turn_on
    target:
      entity_id: light.entry
""",
            "Historical",
            15,
        ),
        AutomationDoc(
            "Documented but deleted",
            """
alias: Documented but deleted
actions:
  - action: light.turn_on
    target:
      entity_id: light.entry
""",
            "Installed",
            16,
        ),
    ]


def _engine():
    entities = _entities()
    reconciliation = reconcile_automations(entities, _docs())
    graph = build_operational_graph(reconciliation)
    return entities, reconciliation, graph


def test_current_ha_wins_for_existence():
    facts = [
        SourceFact("automation:x", FactType.EXISTENCE, True, SourceKind.AUTOMATION_PRODUCTION),
        SourceFact("automation:x", FactType.EXISTENCE, False, SourceKind.HA_CURRENT),
    ]
    assert choose_preferred_fact(facts).value is False


def test_production_wins_for_behavior():
    facts = [
        SourceFact("automation:x", FactType.BEHAVIOR, "expected only", SourceKind.METIER),
        SourceFact("automation:x", FactType.BEHAVIOR, "actual YAML", SourceKind.AUTOMATION_PRODUCTION),
    ]
    assert choose_preferred_fact(facts).value == "actual YAML"


def test_history_never_overrides_current_fact():
    facts = [
        SourceFact("x", FactType.CURRENT_STATE, "old", SourceKind.HISTORY),
        SourceFact("x", FactType.CURRENT_STATE, "new", SourceKind.HA_CURRENT),
    ]
    assert choose_preferred_fact(facts).value == "new"


def test_reconciliation_is_exact_and_fail_closed():
    reconciliation = reconcile_automations(_entities(), _docs())
    assert {item.entity_id for item in reconciliation.matched} >= {
        "automation.entry_main",
        "automation.entry_unlock",
        "automation.bathroom",
    }
    assert [item.name for item in reconciliation.documented_only] == ["Documented but deleted"]


def test_documented_only_automation_is_not_in_operational_graph():
    _, reconciliation, graph = _engine()
    assert all(edge.subject != "automation.documented_but_deleted" for edge in graph)


def test_disabled_automation_is_not_in_operational_graph():
    _, _, graph = _engine()
    assert all(edge.subject != "automation.disabled" for edge in graph)


def test_entry_light_keeps_both_real_automations():
    entities, reconciliation, graph = _engine()
    result = retrieve_automation_chains("what manages the entry lamp", entities, reconciliation, graph)
    assert {item["automation_entity_id"] for item in result} == {
        "automation.entry_main",
        "automation.entry_unlock",
    }


def test_entry_main_chain_keeps_motion_unlock_guard_and_wait():
    _, reconciliation, graph = _engine()
    main = "automation.entry_main"
    relations = {(edge.subject, edge.predicate, edge.object) for edge in graph}
    assert ("binary_sensor.entry_motion", "TRIGGERS", main) in relations
    assert ("lock.front_door", "TRIGGERS", main) in relations
    assert ("switch.awake", "GUARDS", main) in relations
    assert ("binary_sensor.entry_motion", "WAITS_FOR", main) in relations


def test_bathroom_query_resolves_the_actual_light_not_a_room_mention():
    entities, reconciliation, graph = _engine()
    resolved = resolve_entities("what turns on the bathroom lamp", entities)
    assert resolved[0][0].entity_id == "light.bathroom"
    result = retrieve_automation_chains("what turns on the bathroom lamp", entities, reconciliation, graph)
    assert [item["automation_entity_id"] for item in result] == ["automation.bathroom"]
    assert result[0]["effect"] == "turn_on"


def test_irrelevant_textual_mentions_do_not_compete_with_action_edges():
    # The V2 retrieval has no full-text fallback in the operational path.
    entities, reconciliation, graph = _engine()
    result = retrieve_automation_chains(
        "what turns on the bathroom lamp", entities, reconciliation, graph
    )
    assert all(item["target_entity_id"] == "light.bathroom" for item in result)


def test_open_shutter_query_prefers_open_effect():
    entities, reconciliation, graph = _engine()
    result = retrieve_automation_chains(
        "what opens the lounge shutter", entities, reconciliation, graph
    )
    assert result[0]["automation_entity_id"] == "automation.shutter_open"
    assert result[0]["effect"] == "open"


def test_close_shutter_query_prefers_close_effect():
    entities, reconciliation, graph = _engine()
    result = retrieve_automation_chains(
        "what closes the lounge shutter", entities, reconciliation, graph
    )
    assert result[0]["automation_entity_id"] == "automation.shutter_night"
    assert result[0]["effect"] == "close"


def test_nested_choose_action_is_parsed():
    _, _, graph = _engine()
    assert any(
        edge.subject == "automation.bathroom"
        and edge.predicate == "ACTS_ON"
        and edge.object == "light.bathroom"
        and json.loads(edge.detail)["effect"] == "turn_on"
        for edge in graph
    )


def test_device_action_opaque_reference_is_preserved_not_guessed():
    entities = _entities() + [
        EntityRecord("automation.device_action", "automation", "Device action", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Device action",
            """
alias: Device action
actions:
  - type: turn_on
    device_id: 11111111111111111111111111111111
    entity_id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    domain: switch
""",
            "Validated",
            20,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    assert any(
        edge.subject == "automation.device_action"
        and edge.object == "registry_ref:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        for edge in graph
    )
    assert not any(
        edge.subject == "automation.device_action" and edge.object.startswith("switch.")
        for edge in graph
    )


def test_current_automation_without_document_never_gets_invented_behavior():
    entities = _entities() + [
        EntityRecord("automation.undocumented", "automation", "Undocumented", "on")
    ]
    reconciliation = reconcile_automations(entities, _docs())
    graph = build_operational_graph(reconciliation)
    assert any(x.entity_id == "automation.undocumented" for x in reconciliation.current_without_document)
    assert all(edge.subject != "automation.undocumented" for edge in graph)


def test_business_semantics_survive_a_stale_technical_binding():
    entities = [EntityRecord("cover.current", "cover", "Lounge shutter", "open")]
    docs = [
        BusinessFunctionDoc(
            "Lounge shutter position",
            "cover.legacy",
            "Cover",
            "Protects the room from sun",
            "Official",
            "2026-07-01",
        )
    ]
    result = reconcile_business_functions(entities, docs)
    assert result[0].function == "Lounge shutter position"
    assert result[0].rule == "Protects the room from sun"
    assert result[0].binding_entity_id is None
    assert result[0].binding_status == "stale_entity"


def test_business_alias_is_bound_only_by_exact_current_ha_name():
    entities = [
        EntityRecord("automation.current", "automation", "Current shutter rule", "on")
    ]
    docs = [
        BusinessFunctionDoc(
            "Shutter rule",
            "Alias HA : Current shutter rule",
            "Automation",
            "Runs when conditions are met",
            "Official",
            "2026-08-01",
        )
    ]
    result = reconcile_business_functions(entities, docs)
    assert result[0].binding_entity_id == "automation.current"
    assert result[0].binding_status == "current_alias"


def test_business_context_excludes_stale_binding():
    entities = [
        EntityRecord("cover.current", "cover", "Lounge shutter", "open"),
    ]
    docs = [
        BusinessFunctionDoc("Old", "cover.legacy", "Cover", "old rule", "Official"),
        BusinessFunctionDoc("Current", "cover.current", "Cover", "current rule", "Official"),
    ]
    result = reconcile_business_functions(entities, docs)
    context = business_context_for_entity("cover.current", result)
    assert [item.function for item in context] == ["Current"]


def test_current_binding_and_semantics_are_not_collapsed_into_one_fact():
    entities = [
        EntityRecord("cover.new", "cover", "Shutter", "open"),
    ]
    docs = [
        BusinessFunctionDoc(
            "Position shutter", "cover.old", "Cover", "stable business rule", "Official"
        ),
        BusinessFunctionDoc(
            "Local shutter", "cover.new", "Cover", "local implementation", "Official"
        ),
    ]
    result = reconcile_business_functions(entities, docs)
    old, new = result
    assert old.rule == "stable business rule"
    assert old.binding_status == "stale_entity"
    assert new.binding_status == "current_entity"
    assert business_context_for_entity("cover.new", result) == [new]


def test_objects_ha_dependency_is_enrichment_not_behavior():
    entities, reconciliation, graph = _engine()
    deps = [
        ObjectDependencyDoc(
            object_ref="light.entry",
            automation_name="Entry light main",
            domain="light",
            name="Entry lamp",
            observed_state="off",
        )
    ]
    dep_edges = dependency_edges(entities, reconciliation, deps)
    assert dep_edges[0].predicate == "USES"
    result = retrieve_automation_chains(
        "what turns on the entry lamp",
        entities,
        reconciliation,
        dep_edges,
    )
    assert result == []


def test_objects_ha_device_reference_stays_unresolved():
    entities, reconciliation, _ = _engine()
    deps = [
        ObjectDependencyDoc(
            object_ref="device_id:11111111111111111111111111111111",
            automation_name="Entry light main",
        )
    ]
    dep_edges = dependency_edges(entities, reconciliation, deps)
    assert dep_edges[0].object == "device_ref:11111111111111111111111111111111"
    assert dep_edges[0].predicate == "USES"


def test_objects_ha_current_entity_can_enrich_a_reconciled_automation():
    entities, reconciliation, _ = _engine()
    deps = [
        ObjectDependencyDoc(
            object_ref="binary_sensor.entry_motion",
            automation_name="Entry light main",
            domain="binary_sensor",
            name="Entry motion",
            observed_state="off",
        )
    ]
    dep_edges = dependency_edges(entities, reconciliation, deps)
    assert [(edge.subject, edge.predicate, edge.object) for edge in dep_edges] == [
        ("automation.entry_main", "USES", "binary_sensor.entry_motion")
    ]


def test_r8_relation_preserves_role_confidence_and_proof_without_becoming_action():
    entities, reconciliation, _ = _engine()
    relations = [
        R8RelationDoc(
            relation_id="REL-1",
            chain="Lighting",
            source_type="Entity",
            source_id="binary_sensor.entry_motion",
            relation="déclenche",
            target_type="Automatisation HA",
            target_id="Entry light main",
            role="Start the lighting chain",
            evidence="Production YAML + HA inventory",
            confidence="Élevée",
            status="Validé / actif",
            last_verification="2026-09-19",
        )
    ]
    edges = r8_edges(entities, reconciliation, relations)
    assert len(edges) == 1
    edge = edges[0]
    assert edge.subject == "binary_sensor.entry_motion"
    assert edge.object == "automation.entry_main"
    assert edge.source == SourceKind.R8_RELATION
    assert edge.predicate.startswith("R8:")
    assert edge.predicate != "ACTS_ON"
    detail = json.loads(edge.detail)
    assert detail["role"] == "Start the lighting chain"
    assert detail["confidence"] == "Élevée"
    assert detail["evidence"] == "Production YAML + HA inventory"


def test_r8_parser_rejects_historical_or_observation_status():
    header = [
        "Relation_ID", "Chaîne_fonctionnelle", "Source_type", "Source_ID",
        "Relation", "Cible_type", "Cible_ID", "Rôle_ou_effet",
        "Source_de_preuve", "Confiance", "Statut", "Dernière_vérification",
    ]
    rows = [
        ["R1", "A", "Entity", "light.entry", "uses", "Automation", "Entry light main",
         "x", "proof", "High", "Validé / actif", "2026-09-19"],
        ["R2", "A", "Entity", "light.entry", "uses", "Automation", "Entry light main",
         "x", "proof", "High", "Actif historique / legacy", "2026-07-01"],
        ["R3", "A", "Entity", "light.entry", "uses", "Automation", "Entry light main",
         "x", "proof", "High", "Production installée / automatique à observer", "2026-09-01"],
    ]
    result = r8_relations_from_rows(header, rows)
    assert [item.relation_id for item in result] == ["R1"]


def test_r8_document_only_relation_cannot_answer_operational_question():
    entities, reconciliation, _ = _engine()
    relations = [
        R8RelationDoc(
            "REL-X", "Old chain", "Doc", "Bathroom room", "mentions",
            "Doc", "Entry lamp", "Historical note", "old doc", "Low",
            "Validé", "2026-07-01",
        )
    ]
    edges = r8_edges(entities, reconciliation, relations)
    result = retrieve_automation_chains(
        "what turns on the bathroom lamp", entities, reconciliation, edges
    )
    assert result == []


def test_webhook_trigger_is_preserved_as_a_real_trigger_source():
    entities = _entities() + [
        EntityRecord("automation.webhook", "automation", "Webhook task", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Webhook task",
            """
alias: Webhook task
triggers:
  - trigger: webhook
    webhook_id: test_hook
actions:
  - action: light.turn_on
    target:
      entity_id: light.entry
""",
            "Validated",
            30,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    assert any(
        edge.subject == "webhook:test_hook"
        and edge.predicate == "TRIGGERS"
        and edge.object == "automation.webhook"
        for edge in graph
    )


def test_wait_template_keeps_referenced_entity_as_wait_relation():
    entities = _entities() + [
        EntityRecord("automation.wait_template", "automation", "Wait template task", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Wait template task",
            """
alias: Wait template task
triggers:
  - trigger: time
    at: "12:00:00"
actions:
  - wait_template: "{{ is_state('binary_sensor.window', 'off') }}"
  - action: light.turn_on
    target:
      entity_id: light.entry
""",
            "Validated",
            31,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    assert any(
        edge.subject == "binary_sensor.window"
        and edge.predicate == "WAITS_FOR"
        and edge.object == "automation.wait_template"
        for edge in graph
    )


def test_custom_script_service_becomes_a_script_call_not_an_action_on_a_light():
    entities = _entities() + [
        EntityRecord("automation.script_call", "automation", "Call announce script", "on"),
        EntityRecord("script.announce_house", "script", "Announce house", "off"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Call announce script",
            """
alias: Call announce script
triggers:
  - trigger: time
    at: "08:00:00"
actions:
  - action: script.announce_house
    data:
      message: hello
""",
            "Validated",
            32,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    assert any(
        edge.subject == "automation.script_call"
        and edge.predicate == "CALLS_SCRIPT"
        and edge.object == "script.announce_house"
        for edge in graph
    )


def test_pyscript_service_becomes_a_pyscript_call():
    entities = _entities() + [
        EntityRecord("automation.pyscript_call", "automation", "Call pyscript", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Call pyscript",
            """
alias: Call pyscript
triggers:
  - trigger: time_pattern
    minutes: "/5"
actions:
  - action: pyscript.journal_something
""",
            "Validated",
            33,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    assert any(
        edge.subject == "automation.pyscript_call"
        and edge.predicate == "CALLS_PYSCRIPT"
        and edge.object == "service:pyscript.journal_something"
        for edge in graph
    )


def test_device_trigger_keeps_device_reference_even_without_entity_mapping():
    entities = _entities() + [
        EntityRecord("automation.device_trigger", "automation", "Device trigger", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Device trigger",
            """
alias: Device trigger
triggers:
  - trigger: device
    domain: mqtt
    device_id: 11111111111111111111111111111111
    type: action
actions:
  - action: light.turn_on
    target:
      entity_id: light.entry
""",
            "Validated",
            34,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    assert any(
        edge.subject == "device_ref:11111111111111111111111111111111"
        and edge.predicate == "TRIGGERS"
        and edge.object == "automation.device_trigger"
        for edge in graph
    )


def test_service_device_target_stays_device_scoped_until_registry_resolution():
    entities = _entities() + [
        EntityRecord("automation.device_target", "automation", "Device target service", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Device target service",
            """
alias: Device target service
triggers:
  - trigger: time
    at: "10:00:00"
actions:
  - action: homeassistant.turn_off
    target:
      device_id: 22222222222222222222222222222222
""",
            "Validated",
            35,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    assert any(
        edge.subject == "automation.device_target"
        and edge.predicate == "ACTS_ON"
        and edge.object == "device_ref:22222222222222222222222222222222"
        for edge in graph
    )


def test_generic_homeassistant_turn_off_has_semantic_effect():
    entities = _entities() + [
        EntityRecord("automation.generic_off", "automation", "Generic off", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Generic off",
            """
alias: Generic off
triggers:
  - trigger: time
    at: "10:00:00"
actions:
  - action: homeassistant.turn_off
    target:
      entity_id: light.entry
""",
            "Validated",
            36,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    result = retrieve_automation_chains(
        "what turns off the entry lamp", entities, reconciliation, graph
    )
    assert {item["automation_entity_id"] for item in result} == {
        "automation.entry_main",
        "automation.generic_off",
    }
    assert all(item["effect"] == "turn_off" for item in result)
