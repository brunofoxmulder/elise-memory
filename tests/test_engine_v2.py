import json

from elise_memory.engine_v2 import (
    AutomationDoc,
    assemble_evidence_context,
    BusinessFunctionDoc,
    EntityRecord,
    GraphEdge,
    ObjectDependencyDoc,
    OperationalScript,
    R8RelationDoc,
    ReconciledBusinessFunction,
    RegistryBinding,
    FactType,
    SourceFact,
    SourceKind,
    script_context_for_services,
    script_catalog_from_rows,
    ScriptCatalogEntry,
    audit_operational_model,
    build_operational_graph,
    extend_graph_with_operational_scripts,
    business_context_for_entity,
    choose_preferred_fact,
    dependency_edges,
    reconcile_automations,
    reconcile_business_functions,
    registry_bindings_from_entries,
    r8_edges,
    r8_relations_from_rows,
    resolve_entities,
    resolve_registry_edges,
    retrieve_automation_behavior,
    retrieve_automation_chains,
    retrieve_operational_context,
    retrieve_triggered_chains,
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



def test_trigger_source_query_traverses_motion_to_entry_light_actions():
    entities, reconciliation, graph = _engine()
    result = retrieve_triggered_chains(
        "what happens when there is entry motion", entities, reconciliation, graph
    )
    assert {
        (item["automation_entity_id"], item["target"], item["effect"])
        for item in result
    } >= {
        ("automation.entry_main", "light.entry", "turn_on"),
        ("automation.entry_main", "light.entry", "turn_off"),
    }


def test_trigger_source_query_traverses_window_to_shutter_opening():
    entities, reconciliation, graph = _engine()
    result = retrieve_triggered_chains(
        "what happens when the lounge window opens", entities, reconciliation, graph
    )
    assert [
        (item["automation_entity_id"], item["target"], item["effect"])
        for item in result
    ] == [("automation.shutter_open", "cover.lounge", "open")]


def test_guard_is_not_mistaken_for_trigger_in_source_query():
    entities, reconciliation, graph = _engine()
    result = retrieve_triggered_chains(
        "what happens when the awake signal is on", entities, reconciliation, graph
    )
    assert all(item["automation_entity_id"] != "automation.entry_main" for item in result)


def test_if_then_else_actions_and_local_guard_are_parsed():
    entities = _entities() + [
        EntityRecord("automation.if_task", "automation", "Conditional lamp", "on"),
        EntityRecord("switch.mode", "switch", "Mode switch", "off"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Conditional lamp",
            """
alias: Conditional lamp
triggers:
  - trigger: state
    entity_id: binary_sensor.entry_motion
    to: "on"
actions:
  - if:
      - condition: state
        entity_id: switch.mode
        state: "on"
    then:
      - action: light.turn_on
        target:
          entity_id: light.entry
    else:
      - action: light.turn_off
        target:
          entity_id: light.entry
""",
            "Validated",
            40,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    assert any(
        edge.subject == "switch.mode"
        and edge.predicate == "LOCAL_GUARD"
        and edge.object == "automation.if_task"
        for edge in graph
    )
    assert {
        json.loads(edge.detail).get("effect")
        for edge in graph
        if edge.subject == "automation.if_task"
        and edge.predicate == "ACTS_ON"
        and edge.object == "light.entry"
    } == {"turn_on", "turn_off"}


def test_source_query_does_not_guess_opaque_device_trigger_identity():
    entities = _entities() + [
        EntityRecord("automation.opaque_window", "automation", "Opaque window task", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Opaque window task",
            """
alias: Opaque window task
triggers:
  - trigger: device
    domain: binary_sensor
    device_id: 11111111111111111111111111111111
    entity_id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    type: opened
actions:
  - action: cover.open_cover
    target:
      entity_id: cover.lounge
""",
            "Validated",
            41,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    result = retrieve_triggered_chains(
        "what happens when the lounge window opens", entities, reconciliation, graph
    )
    assert all(item["automation_entity_id"] != "automation.opaque_window" for item in result)
    assert any(
        edge.subject == "registry_ref:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        and edge.predicate == "TRIGGERS"
        and edge.object == "automation.opaque_window"
        for edge in graph
    )


def test_french_unlock_verb_is_removed_from_object_identity_and_hints_lock():
    entities = [
        EntityRecord("lock.porte_dentree", "lock", "Porte d'entrée", "locked"),
        EntityRecord("binary_sensor.porte_dentree", "binary_sensor", "Porte d'entrée", "off"),
    ]
    result = resolve_entities("quand je deverrouille la porte", entities)
    assert result[0][0].entity_id == "lock.porte_dentree"



def test_wait_after_turn_on_is_not_attached_to_the_earlier_turn_on_effect():
    entities, reconciliation, graph = _engine()
    result = retrieve_automation_chains(
        "what turns on the entry lamp", entities, reconciliation, graph
    )
    main = next(item for item in result if item["automation_entity_id"] == "automation.entry_main")
    assert all(item["predicate"] != "WAITS_FOR" for item in main["context"])


def test_wait_before_turn_off_is_attached_to_the_later_turn_off_effect():
    entities, reconciliation, graph = _engine()
    result = retrieve_automation_chains(
        "what turns off the entry lamp", entities, reconciliation, graph
    )
    main = next(item for item in result if item["automation_entity_id"] == "automation.entry_main")
    assert any(item["predicate"] == "WAITS_FOR" for item in main["context"])


def test_choose_branch_guards_do_not_leak_between_opposite_charge_actions():
    entities = _entities() + [
        EntityRecord("automation.charge", "automation", "Phone charge", "on"),
        EntityRecord("switch.charger", "switch", "Phone charger", "off"),
        EntityRecord("sensor.battery", "sensor", "Phone battery", "80"),
        EntityRecord("binary_sensor.offpeak", "binary_sensor", "Off peak", "on"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Phone charge",
            """
alias: Phone charge
triggers:
  - trigger: state
    entity_id: binary_sensor.offpeak
    to: "on"
conditions:
  - condition: state
    entity_id: binary_sensor.offpeak
    state: "on"
actions:
  - choose:
      - conditions:
          - condition: numeric_state
            entity_id: sensor.battery
            below: 95
        sequence:
          - delay: "00:30:00"
          - action: switch.turn_on
            target:
              entity_id: switch.charger
      - conditions:
          - condition: numeric_state
            entity_id: sensor.battery
            above: 99
        sequence:
          - action: switch.turn_off
            target:
              entity_id: switch.charger
""",
            "Validated",
            50,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)

    turn_on = retrieve_automation_chains(
        "what turns on the phone charger", entities, reconciliation, graph
    )
    charge_on = next(item for item in turn_on if item["automation_entity_id"] == "automation.charge")
    local_on = [
        item["detail"] for item in charge_on["context"]
        if item["predicate"] == "LOCAL_GUARD"
    ]
    assert any(detail.get("below") == 95 for detail in local_on)
    assert all(detail.get("above") != 99 for detail in local_on)

    turn_off = retrieve_automation_chains(
        "what turns off the phone charger", entities, reconciliation, graph
    )
    charge_off = next(item for item in turn_off if item["automation_entity_id"] == "automation.charge")
    local_off = [
        item["detail"] for item in charge_off["context"]
        if item["predicate"] == "LOCAL_GUARD"
    ]
    assert any(detail.get("above") == 99 for detail in local_off)
    assert all(detail.get("below") != 95 for detail in local_off)



def test_explicit_registry_binding_makes_opaque_device_action_queryable():
    entities = _entities() + [
        EntityRecord("automation.device_charge", "automation", "Device charge", "on"),
        EntityRecord("switch.charge_socket", "switch", "Charge socket", "off"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Device charge",
            """
alias: Device charge
triggers:
  - trigger: time
    at: "01:00:00"
actions:
  - type: turn_on
    device_id: 11111111111111111111111111111111
    entity_id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    domain: switch
""",
            "Validated",
            60,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    unresolved = retrieve_automation_chains(
        "what turns on the charge socket", entities, reconciliation, graph
    )
    assert all(item["automation_entity_id"] != "automation.device_charge" for item in unresolved)

    resolved_graph = resolve_registry_edges(
        graph,
        entities,
        [RegistryBinding(
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "switch.charge_socket",
            "ha_entity_registry_readonly",
        )],
    )
    resolved = retrieve_automation_chains(
        "what turns on the charge socket", entities, reconciliation, resolved_graph
    )
    item = next(x for x in resolved if x["automation_entity_id"] == "automation.device_charge")
    assert item["target_entity_id"] == "switch.charge_socket"
    assert item["action_detail"]["identity_resolution_source"] == "ha_entity_registry_readonly"


def test_explicit_registry_binding_makes_opaque_device_trigger_traversable():
    entities = _entities() + [
        EntityRecord("automation.opaque_trigger", "automation", "Opaque trigger", "on"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Opaque trigger",
            """
alias: Opaque trigger
triggers:
  - trigger: device
    device_id: 22222222222222222222222222222222
    entity_id: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
    domain: binary_sensor
    type: opened
actions:
  - action: cover.open_cover
    target:
      entity_id: cover.lounge
""",
            "Validated",
            61,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    resolved_graph = resolve_registry_edges(
        graph,
        entities,
        [RegistryBinding(
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "binary_sensor.window",
            "ha_entity_registry_readonly",
        )],
    )
    result = retrieve_triggered_chains(
        "what happens when the lounge window opens",
        entities,
        reconciliation,
        resolved_graph,
    )
    assert any(
        item["automation_entity_id"] == "automation.opaque_trigger"
        and item["target"] == "cover.lounge"
        and item["effect"] == "open"
        for item in result
    )


def test_registry_binding_rejects_non_current_target():
    entities, reconciliation, graph = _engine()
    import pytest
    with pytest.raises(ValueError, match="registry_binding_not_current"):
        resolve_registry_edges(
            graph,
            entities,
            [RegistryBinding(
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "switch.not_in_current_ha",
                "test",
            )],
        )


def test_registry_binding_rejects_conflicting_identity_claims():
    entities = _entities() + [
        EntityRecord("switch.one", "switch", "One", "off"),
        EntityRecord("switch.two", "switch", "Two", "off"),
    ]
    _, reconciliation, graph = _engine()
    import pytest
    with pytest.raises(ValueError, match="conflicting_registry_binding"):
        resolve_registry_edges(
            graph,
            entities,
            [
                RegistryBinding("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "switch.one", "source_a"),
                RegistryBinding("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "switch.two", "source_b"),
            ],
        )



def test_disabled_trigger_condition_and_action_are_ignored():
    entities = _entities() + [
        EntityRecord("automation.disabled_parts", "automation", "Disabled parts", "on"),
        EntityRecord("switch.blocker", "switch", "Blocker", "off"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Disabled parts",
            """
alias: Disabled parts
triggers:
  - trigger: state
    entity_id: binary_sensor.entry_motion
    to: "on"
    enabled: false
  - trigger: state
    entity_id: binary_sensor.bathroom_motion
    to: "on"
conditions:
  - condition: state
    entity_id: switch.blocker
    state: "on"
    enabled: false
actions:
  - action: light.turn_on
    target:
      entity_id: light.entry
    enabled: false
  - action: light.turn_on
    target:
      entity_id: light.bathroom
""",
            "Validated",
            60,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    rels = {(edge.subject, edge.predicate, edge.object) for edge in graph}
    assert ("binary_sensor.entry_motion", "TRIGGERS", "automation.disabled_parts") not in rels
    assert ("binary_sensor.bathroom_motion", "TRIGGERS", "automation.disabled_parts") in rels
    assert ("switch.blocker", "GUARDS", "automation.disabled_parts") not in rels
    assert ("automation.disabled_parts", "ACTS_ON", "light.entry") not in rels
    assert ("automation.disabled_parts", "ACTS_ON", "light.bathroom") in rels


def test_time_condition_is_preserved_as_guard():
    entities = _entities() + [
        EntityRecord("automation.weekly", "automation", "Weekly report", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Weekly report",
            """
alias: Weekly report
triggers:
  - trigger: time
    at: "00:35:00"
conditions:
  - condition: time
    weekday:
      - mon
actions:
  - action: pyscript.weekly_report
""",
            "Validated",
            61,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    edge = next(
        edge for edge in graph
        if edge.subject == "time_window"
        and edge.predicate == "GUARDS"
        and edge.object == "automation.weekly"
    )
    detail = json.loads(edge.detail)
    assert detail["weekday"] == ["mon"]


def test_wait_timeout_is_preserved_before_following_action():
    entities = _entities() + [
        EntityRecord("automation.charge_wait", "automation", "Charge wait", "on"),
        EntityRecord("switch.charger", "switch", "Phone charger", "off"),
        EntityRecord("sensor.power", "sensor", "Charger power", "5"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Charge wait",
            """
alias: Charge wait
triggers:
  - trigger: time
    at: "01:00:00"
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.charger
  - wait_for_trigger:
      - trigger: numeric_state
        entity_id: sensor.power
        below: 1
        for: "00:05:00"
    timeout: "04:00:00"
    continue_on_timeout: true
  - action: switch.turn_off
    target:
      entity_id: switch.charger
""",
            "Validated",
            62,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    result = retrieve_automation_chains(
        "what turns off the phone charger", entities, reconciliation, graph
    )
    item = next(x for x in result if x["automation_entity_id"] == "automation.charge_wait")
    assert any(
        barrier["detail"].get("kind") == "wait_for_trigger"
        and barrier["detail"].get("timeout") == "04:00:00"
        and barrier["detail"].get("continue_on_timeout") is True
        for barrier in item["barriers"]
    )
    assert any(
        ctx["predicate"] == "WAITS_FOR" and ctx["subject"] == "sensor.power"
        for ctx in item["context"]
    )


def test_wait_template_timeout_is_preserved():
    entities = _entities() + [
        EntityRecord("automation.secure", "automation", "Secure house", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Secure house",
            """
alias: Secure house
triggers:
  - trigger: state
    entity_id: switch.awake
    to: "off"
actions:
  - wait_template: "{{ is_state('lock.front_door', 'locked') }}"
    timeout:
      seconds: 20
    continue_on_timeout: true
  - action: light.turn_off
    target:
      entity_id: light.entry
""",
            "Validated",
            63,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    result = retrieve_automation_chains(
        "what turns off the entry lamp", entities, reconciliation, graph
    )
    item = next(x for x in result if x["automation_entity_id"] == "automation.secure")
    assert any(
        barrier["detail"].get("kind") == "wait_template"
        and barrier["detail"].get("timeout") == {"seconds": 20}
        and barrier["detail"].get("continue_on_timeout") is True
        for barrier in item["barriers"]
    )


def test_stop_makes_later_actions_in_same_sequence_unreachable():
    entities = _entities() + [
        EntityRecord("automation.stop_test", "automation", "Stop test", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Stop test",
            """
alias: Stop test
triggers:
  - trigger: state
    entity_id: binary_sensor.entry_motion
    to: "on"
actions:
  - action: light.turn_on
    target:
      entity_id: light.entry
  - stop: "do not continue"
  - action: light.turn_on
    target:
      entity_id: light.bathroom
""",
            "Validated",
            64,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    assert any(
        edge.subject == "automation.stop_test"
        and edge.predicate == "TERMINATES"
        for edge in graph
    )
    assert not any(
        edge.subject == "automation.stop_test"
        and edge.predicate == "ACTS_ON"
        and edge.object == "light.bathroom"
        for edge in graph
    )



def test_string_template_condition_is_not_dropped():
    entities = _entities() + [
        EntityRecord("automation.template_branch", "automation", "Template branch", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Template branch",
            """
alias: Template branch
triggers:
  - trigger: time
    at: "18:00:00"
actions:
  - variables:
      ready: true
  - choose:
      - conditions: "{{ ready }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: light.entry
""",
            "Validated",
            70,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    result = retrieve_automation_chains(
        "what turns on the entry lamp", entities, reconciliation, graph
    )
    item = next(x for x in result if x["automation_entity_id"] == "automation.template_branch")
    assert any(
        ctx["predicate"] == "LOCAL_GUARD"
        and ctx["subject"] == "template_condition"
        and "ready" in ctx["detail"].get("expression", "")
        for ctx in item["context"]
    )


def test_dotted_states_reference_is_extracted_from_template_guard():
    entities = _entities() + [
        EntityRecord("automation.dotted_template", "automation", "Dotted template", "on"),
        EntityRecord("sensor.outdoor_temp", "sensor", "Outdoor temp", "18"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Dotted template",
            """
alias: Dotted template
triggers:
  - trigger: time
    at: "12:00:00"
conditions:
  - condition: template
    value_template: "{{ states.sensor.outdoor_temp.state | float(0) < 20 }}"
actions:
  - action: light.turn_on
    target:
      entity_id: light.entry
""",
            "Validated",
            71,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    assert any(
        edge.subject == "sensor.outdoor_temp"
        and edge.predicate == "GUARDS"
        and edge.object == "automation.dotted_template"
        for edge in graph
    )
    assert any(
        edge.subject == "template_condition"
        and edge.predicate == "GUARDS"
        and edge.object == "automation.dotted_template"
        for edge in graph
    )


def test_dynamic_states_collection_template_remains_visible_as_guard():
    entities = _entities() + [
        EntityRecord("automation.dynamic_batteries", "automation", "Dynamic batteries", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Dynamic batteries",
            """
alias: Dynamic batteries
triggers:
  - trigger: time
    at: "18:00:00"
conditions:
  - condition: template
    value_template: >
      {% set low = namespace(found=false) %}
      {% for s in states.sensor if 'battery' in s.entity_id %}
        {% if s.state | int(100) < 20 %}{% set low.found = true %}{% endif %}
      {% endfor %}
      {{ low.found }}
actions:
  - action: notify.mobile_app_phone
    data:
      message: Batteries low
""",
            "Validated",
            72,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    guard = next(
        edge for edge in graph
        if edge.subject == "template_condition"
        and edge.predicate == "GUARDS"
        and edge.object == "automation.dynamic_batteries"
    )
    assert "states.sensor" in json.loads(guard.detail)["expression"]



def test_french_entry_lamp_question_returns_both_active_automations():
    entities = [
        EntityRecord("automation.entree_main", "automation", "Allumer lampe entrée selon présence", "on"),
        EntityRecord("automation.entree_unlock", "automation", "Allumer lampe entrée au déverrouillage", "on"),
        EntityRecord("light.entree", "light", "Lampe entrée", "off"),
        EntityRecord("binary_sensor.mouvement_entree", "binary_sensor", "Mouvement entrée", "off"),
        EntityRecord("lock.porte", "lock", "Porte d'entrée", "locked"),
    ]
    docs = [
        AutomationDoc(
            "Allumer lampe entrée selon présence",
            """
alias: Allumer lampe entrée selon présence
triggers:
  - trigger: state
    entity_id: binary_sensor.mouvement_entree
    to: "on"
actions:
  - action: light.turn_on
    target:
      entity_id: light.entree
""",
            "Validée",
            80,
        ),
        AutomationDoc(
            "Allumer lampe entrée au déverrouillage",
            """
alias: Allumer lampe entrée au déverrouillage
triggers:
  - trigger: state
    entity_id: lock.porte
    to: unlocked
actions:
  - action: light.turn_on
    target:
      entity_id: light.entree
""",
            "Validée",
            81,
        ),
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    result = retrieve_automation_chains(
        "qu'est-ce qui allume la lampe de l'entrée ?", entities, reconciliation, graph
    )
    assert {x["automation_entity_id"] for x in result} == {
        "automation.entree_main", "automation.entree_unlock"
    }


def test_french_window_question_resolves_trigger_source_before_effect():
    entities = [
        EntityRecord("automation.volet", "automation", "Ouverture volet salon par ouverture fenêtre", "on"),
        EntityRecord("binary_sensor.fenetre", "binary_sensor", "Fenêtre salon", "off"),
        EntityRecord("cover.volet", "cover", "Volet salon", "closed"),
    ]
    docs = [
        AutomationDoc(
            "Ouverture volet salon par ouverture fenêtre",
            """
alias: Ouverture volet salon par ouverture fenêtre
triggers:
  - trigger: state
    entity_id: binary_sensor.fenetre
    to: "on"
actions:
  - action: cover.set_cover_position
    target:
      entity_id: cover.volet
    data:
      position: 100
""",
            "Validée",
            82,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    result = retrieve_triggered_chains(
        "que se passe-t-il quand j'ouvre la fenêtre du salon ?",
        entities, reconciliation, graph
    )
    assert [
        (x["automation_entity_id"], x["target"], x["effect"])
        for x in result
    ] == [("automation.volet", "cover.volet", "open")]


def test_french_charge_word_resolves_switch_not_power_sensor():
    entities = [
        EntityRecord("switch.prise_aspirateur", "switch", "Prise aspirateur", "off"),
        EntityRecord("sensor.prise_aspirateur_power", "sensor", "Prise aspirateur Puissance", "0"),
    ]
    result = resolve_entities("comment fonctionne la charge de l'aspirateur ?", entities)
    assert result[0][0].entity_id == "switch.prise_aspirateur"



def test_automation_behavior_query_returns_full_main_charge_flow():
    entities = _entities() + [
        EntityRecord("automation.charge_main", "automation", "Charge aspirateur", "on"),
        EntityRecord("automation.charge_safety", "automation", "Charge aspirateur arrêt sécurité", "on"),
        EntityRecord("switch.vacuum", "switch", "Prise aspirateur", "off"),
        EntityRecord("sensor.vacuum_power", "sensor", "Prise aspirateur Puissance", "0"),
        EntityRecord("binary_sensor.docked", "binary_sensor", "Aspirateur sur base", "off"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Charge aspirateur",
            """
alias: Charge aspirateur
triggers:
  - trigger: state
    entity_id: binary_sensor.docked
    to: "on"
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.vacuum
  - delay:
      minutes: 2
  - choose:
      - conditions:
          - condition: numeric_state
            entity_id: sensor.vacuum_power
            above: 1
        sequence:
          - wait_for_trigger:
              - trigger: numeric_state
                entity_id: sensor.vacuum_power
                below: 1
                for:
                  minutes: 2
          - action: switch.turn_off
            target:
              entity_id: switch.vacuum
    default:
      - action: switch.turn_off
        target:
          entity_id: switch.vacuum
""",
            "Validée",
            90,
        ),
        AutomationDoc(
            "Charge aspirateur arrêt sécurité",
            """
alias: Charge aspirateur arrêt sécurité
triggers:
  - trigger: time
    at: "06:00:00"
actions:
  - action: switch.turn_off
    target:
      entity_id: switch.vacuum
""",
            "Validée",
            91,
        ),
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    result = retrieve_automation_behavior("comment fonctionne la charge aspirateur ?", reconciliation, graph)
    assert [x["automation_entity_id"] for x in result] == ["automation.charge_main"]
    item = result[0]
    assert {x["object"] for x in item["actions"]} == {"switch.vacuum"}
    assert {json.loads(json.dumps(x["detail"])).get("effect") for x in item["actions"]} == {
        "turn_on", "turn_off"
    }
    assert any(x["subject"] == "binary_sensor.docked" for x in item["triggers"])
    assert any(x["subject"] == "sensor.vacuum_power" for x in item["waits"])


def test_operational_router_uses_trigger_mode_for_quand_question():
    entities = [
        EntityRecord("automation.volet", "automation", "Ouverture volet salon par ouverture fenêtre", "on"),
        EntityRecord("binary_sensor.fenetre", "binary_sensor", "Fenêtre salon", "off"),
        EntityRecord("cover.volet", "cover", "Volet salon", "closed"),
    ]
    docs = [
        AutomationDoc(
            "Ouverture volet salon par ouverture fenêtre",
            """
alias: Ouverture volet salon par ouverture fenêtre
triggers:
  - trigger: state
    entity_id: binary_sensor.fenetre
    to: "on"
actions:
  - action: cover.open_cover
    target:
      entity_id: cover.volet
""",
            "Validée",
            92,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    result = retrieve_operational_context(
        "que se passe-t-il quand j'ouvre la fenêtre salon ?",
        entities, reconciliation, graph
    )
    assert result["mode"] == "trigger_to_effect"
    assert result["results"][0]["target"] == "cover.volet"


def test_operational_router_uses_automation_behavior_for_named_function():
    entities = _entities() + [
        EntityRecord("automation.charge_main", "automation", "Charge aspirateur", "on"),
        EntityRecord("switch.vacuum", "switch", "Prise aspirateur", "off"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Charge aspirateur",
            """
alias: Charge aspirateur
triggers:
  - trigger: time
    at: "01:00:00"
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.vacuum
""",
            "Validée",
            93,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    result = retrieve_operational_context(
        "comment fonctionne la charge aspirateur ?",
        entities, reconciliation, graph
    )
    assert result["mode"] == "automation_behavior"
    assert result["results"][0]["automation_entity_id"] == "automation.charge_main"


def test_operational_router_keeps_target_mode_for_generic_volet_question():
    entities = [
        EntityRecord("automation.open_volet", "automation", "Ouverture volet salon", "on"),
        EntityRecord("automation.close_volet", "automation", "Fermeture volet salon", "on"),
        EntityRecord("cover.volet", "cover", "Volet salon", "open"),
    ]
    docs = [
        AutomationDoc(
            "Ouverture volet salon",
            """
alias: Ouverture volet salon
triggers:
  - trigger: time
    at: "08:00:00"
actions:
  - action: cover.open_cover
    target:
      entity_id: cover.volet
""",
            "Validée",
            94,
        ),
        AutomationDoc(
            "Fermeture volet salon",
            """
alias: Fermeture volet salon
triggers:
  - trigger: time
    at: "22:00:00"
actions:
  - action: cover.close_cover
    target:
      entity_id: cover.volet
""",
            "Validée",
            95,
        ),
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    result = retrieve_operational_context(
        "comment fonctionne le volet salon ?",
        entities, reconciliation, graph
    )
    assert result["mode"] == "target_to_automation"
    assert {x["automation_entity_id"] for x in result["results"]} == {
        "automation.open_volet", "automation.close_volet"
    }



def test_evidence_assembly_keeps_production_as_operational_core():
    entities = [
        EntityRecord("automation.lamp", "automation", "Allumer lampe entrée", "on"),
        EntityRecord("light.entry", "light", "Lampe entrée", "off"),
        EntityRecord("binary_sensor.motion", "binary_sensor", "Mouvement entrée", "off"),
    ]
    docs = [
        AutomationDoc(
            "Allumer lampe entrée",
            """
alias: Allumer lampe entrée
triggers:
  - trigger: state
    entity_id: binary_sensor.motion
    to: "on"
actions:
  - action: light.turn_on
    target:
      entity_id: light.entry
""",
            "Validée",
            100,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    production = build_operational_graph(reconciliation)
    deps = [
        GraphEdge(
            "automation.lamp", "USES", "sensor.unrelated",
            SourceKind.OBJECTS_HA, json.dumps({"binding": "document_only"})
        )
    ]
    r8 = [
        GraphEdge(
            "document_ref:old", "R8:mentions", "automation.lamp",
            SourceKind.R8_RELATION, json.dumps({"role": "historical"})
        )
    ]
    business = [
        ReconciledBusinessFunction(
            function="Éclairage entrée",
            reference="light.entry",
            object_type="Light",
            rule="Éclairage sur présence",
            source_official="Oui",
            last_validation="2026-09-19",
            binding_entity_id="light.entry",
            binding_status="current_entity",
        )
    ]
    result = assemble_evidence_context(
        "qu'est-ce qui allume la lampe entrée ?",
        entities,
        reconciliation,
        production,
        dependency_edges_in=deps,
        r8_edges_in=r8,
        business_functions=business,
    )
    assert result["operational_answer_available"] is True
    assert result["operational"]["mode"] == "target_to_automation"
    assert result["layers"]["production"][0]["automation_entity_id"] == "automation.lamp"
    assert result["layers"]["objects_ha"][0]["predicate"] == "USES"
    assert result["layers"]["r8"][0]["predicate"] == "R8:mentions"
    assert result["layers"]["metier"][0]["function"] == "Éclairage entrée"
    assert result["precedence"][:2] == ["current_identity", "production"]


def test_documentary_layers_cannot_create_operational_answer():
    entities = [
        EntityRecord("light.entry", "light", "Lampe entrée", "off"),
    ]
    reconciliation = reconcile_automations(entities, [])
    production = build_operational_graph(reconciliation)
    deps = [
        GraphEdge(
            "document_ref:ghost_automation", "USES", "light.entry",
            SourceKind.OBJECTS_HA, None
        )
    ]
    r8 = [
        GraphEdge(
            "document_ref:ghost_automation", "R8:agit_sur", "light.entry",
            SourceKind.R8_RELATION, json.dumps({"status": "Validé"})
        )
    ]
    result = assemble_evidence_context(
        "qu'est-ce qui allume la lampe entrée ?",
        entities,
        reconciliation,
        production,
        dependency_edges_in=deps,
        r8_edges_in=r8,
    )
    assert result["operational_answer_available"] is False
    assert result["operational"]["mode"] == "unresolved"
    assert result["layers"]["production"] == []



def test_operational_audit_counts_current_reconciled_and_unresolved_layers():
    entities = _entities() + [
        EntityRecord("automation.opaque_audit", "automation", "Opaque audit", "on"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Opaque audit",
            """
alias: Opaque audit
triggers:
  - trigger: device
    device_id: 11111111111111111111111111111111
    entity_id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    domain: binary_sensor
    type: opened
actions:
  - type: turn_on
    device_id: 22222222222222222222222222222222
    entity_id: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
    domain: switch
""",
            "Validated",
            70,
        )
    ]
    audit = audit_operational_model(entities, docs)
    assert audit.current_automations == 7
    assert audit.current_active == 6
    assert audit.current_disabled == 1
    assert audit.matched_active == 6
    assert audit.matched_disabled == 1
    assert audit.documented_only == 1
    assert audit.current_without_document == 0
    assert audit.parse_errors == ()
    assert "registry_ref:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in audit.unresolved_registry_refs
    assert "registry_ref:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" in audit.unresolved_registry_refs
    assert audit.predicate_counts["TRIGGERS"] > 0
    assert audit.predicate_counts["ACTS_ON"] > 0


def test_operational_audit_isolates_one_bad_yaml_instead_of_hiding_whole_corpus():
    entities = _entities() + [
        EntityRecord("automation.broken_yaml", "automation", "Broken yaml", "on"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Broken yaml",
            "alias: Broken yaml\nactions: [ this is : not valid",
            "Validated",
            71,
        )
    ]
    audit = audit_operational_model(entities, docs)
    assert audit.matched_active == 6
    assert audit.parsed_active == 5
    assert len(audit.parse_errors) == 1
    assert audit.parse_errors[0]["automation_entity_id"] == "automation.broken_yaml"


def test_operational_audit_flags_parsed_automation_with_no_effect():
    entities = _entities() + [
        EntityRecord("automation.guard_only", "automation", "Guard only", "on"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Guard only",
            """
alias: Guard only
triggers:
  - trigger: state
    entity_id: binary_sensor.entry_motion
    to: "on"
conditions:
  - condition: state
    entity_id: switch.awake
    state: "on"
actions: []
""",
            "Validated",
            72,
        )
    ]
    audit = audit_operational_model(entities, docs)
    assert "automation.guard_only" in audit.active_without_effect_edge
    assert "automation.guard_only" not in audit.active_without_trigger_edge



def test_script_catalog_enriches_only_a_service_already_proved_by_production():
    header = [
        "ID", "Nom du fichier", "Service HA exposé", "Domaine", "Rôle",
        "Statut", "Version actuelle", "Version précédente", "Automatisation liée",
        "Onglets lus", "Onglets écrits", "Entités HA utilisées", "Prompt IA",
        "Chemin HA", "Dernière modification", "Risques / points sensibles",
        "Commentaires",
    ]
    rows = [[
        "S1", "worker.py", "pyscript.worker ; pyscript.worker_manual",
        "Maison", "Explains the worker role", "Production validée", "v1", "",
        "Main task", "", "", "sensor.one ; switch.two", "", "/config/pyscript/worker.py",
        "2026-09-19", "none", "catalogue note",
    ]]
    catalog = script_catalog_from_rows(header, rows)
    result = script_context_for_services(["service:pyscript.worker"], catalog)
    assert len(result) == 1
    assert result[0]["script_id"] == "S1"
    assert result[0]["services"] == ["pyscript.worker"]
    assert result[0]["role"] == "Explains the worker role"
    assert result[0]["entities"] == ["sensor.one", "switch.two"]


def test_script_catalog_does_not_match_similar_unproved_service_name():
    item = ScriptCatalogEntry(
        "S1", "worker.py", ("pyscript.worker",), "Maison", "role",
        "Production", "v1", "Task", (), "2026-09-19", None, None,
    )
    assert script_context_for_services(["service:pyscript.worker_old"], [item]) == []


def test_evidence_assembly_attaches_called_pyscript_after_operational_core_only():
    entities = _entities() + [
        EntityRecord("automation.pyscript_task2", "automation", "Pyscript task 2", "on")
    ]
    docs = _docs() + [
        AutomationDoc(
            "Pyscript task 2",
            """
alias: Pyscript task 2
triggers:
  - trigger: state
    entity_id: binary_sensor.entry_motion
    to: "on"
actions:
  - action: pyscript.worker
""",
            "Validated",
            80,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    catalog = [
        ScriptCatalogEntry(
            "S1", "worker.py", ("pyscript.worker",), "Maison",
            "Does the documented worker job", "Production validée", "v1",
            "Pyscript task 2", ("sensor.one",), "2026-09-19", None, None,
        )
    ]
    evidence = assemble_evidence_context(
        "Pyscript task 2",
        entities,
        reconciliation,
        graph,
        script_catalog=catalog,
    )
    assert evidence["operational"]["mode"] == "automation_behavior"
    assert evidence["layers"]["scripts"][0]["services"] == ["pyscript.worker"]
    assert evidence["layers"]["scripts"][0]["role"] == "Does the documented worker job"


def test_script_catalog_alone_cannot_create_an_operational_answer():
    entities, reconciliation, _ = _engine()
    catalog = [
        ScriptCatalogEntry(
            "S1", "worker.py", ("pyscript.worker",), "Maison", "role",
            "Production validée", "v1", "No matching automation", (),
            "2026-09-19", None, None,
        )
    ]
    evidence = assemble_evidence_context(
        "what turns on a nonexistent lamp",
        entities,
        reconciliation,
        [],
        script_catalog=catalog,
    )
    assert evidence["operational_answer_available"] is False
    assert evidence["layers"]["scripts"] == []



def test_entity_registry_dump_builds_exact_current_bindings_only():
    entities = [
        EntityRecord("binary_sensor.window", "binary_sensor", "Window", "off"),
        EntityRecord("switch.socket", "switch", "Socket", "off"),
    ]
    entries = [
        {
            "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "entity_id": "binary_sensor.window",
            "device_id": "11111111111111111111111111111111",
        },
        {
            "id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "entity_id": "switch.socket",
            "device_id": "22222222222222222222222222222222",
        },
        {
            "id": "cccccccccccccccccccccccccccccccc",
            "entity_id": "sensor.stale_not_current",
        },
        {
            "id": "not-an-opaque-id",
            "entity_id": "switch.socket",
        },
    ]
    bindings = registry_bindings_from_entries(entries, entities)
    assert [(x.registry_ref, x.entity_id) for x in bindings] == [
        ("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "binary_sensor.window"),
        ("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "switch.socket"),
    ]
    assert {x.source for x in bindings} == {"ha_entity_registry_readonly"}


def test_entity_registry_binding_then_resolves_real_device_style_trigger_and_action():
    entities = _entities() + [
        EntityRecord("automation.registry_roundtrip", "automation", "Registry roundtrip", "on"),
        EntityRecord("switch.device_socket", "switch", "Device socket", "off"),
    ]
    docs = _docs() + [
        AutomationDoc(
            "Registry roundtrip",
            """
alias: Registry roundtrip
triggers:
  - trigger: device
    device_id: 11111111111111111111111111111111
    entity_id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    domain: binary_sensor
    type: opened
actions:
  - type: turn_on
    device_id: 22222222222222222222222222222222
    entity_id: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
    domain: switch
""",
            "Validated",
            90,
        )
    ]
    reconciliation = reconcile_automations(entities, docs)
    graph = build_operational_graph(reconciliation)
    bindings = registry_bindings_from_entries(
        [
            {"id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "entity_id": "binary_sensor.window"},
            {"id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "entity_id": "switch.device_socket"},
        ],
        entities,
    )
    resolved = resolve_registry_edges(graph, entities, bindings)
    result = retrieve_triggered_chains(
        "what happens when the lounge window opens",
        entities,
        reconciliation,
        resolved,
    )
    assert any(
        item["automation_entity_id"] == "automation.registry_roundtrip"
        and item["target"] == "switch.device_socket"
        and item["effect"] == "turn_on"
        for item in result
    )


def test_proved_script_expansion_is_fail_closed_and_requires_executable_proof():
    entities = _entities() + [
        EntityRecord("automation.via_script", "automation", "Via script", "on"),
        EntityRecord("light.proved", "light", "Lampe prouvée", "off"),
    ]
    docs = _docs() + [
        AutomationDoc("Via script", """
alias: Via script
triggers:
  - trigger: state
    entity_id: binary_sensor.entry_motion
    to: "on"
actions:
  - action: script.allume_lampe_prouvee
""", "Validated", 200)
    ]
    reconciliation = reconcile_automations(entities, docs)
    base = build_operational_graph(reconciliation)
    assert any(x.predicate == "CALLS_SCRIPT" and x.object == "script.allume_lampe_prouvee" for x in base)
    assert not any(x.predicate == "ACTS_ON" and x.object == "light.proved" for x in base)

    expanded = extend_graph_with_operational_scripts(
        base,
        [OperationalScript(
            "script.allume_lampe_prouvee",
            """
actions:
  - action: light.turn_on
    target:
      entity_id: light.proved
""",
            "ha_script_config_readonly",
        )],
    )
    script_node = "operational_script:script.allume_lampe_prouvee"
    assert any(x.predicate == "CALLS_PROVED_SCRIPT" and x.object == script_node for x in expanded)
    action = next(x for x in expanded if x.subject == script_node and x.predicate == "ACTS_ON" and x.object == "light.proved")
    assert action.source == SourceKind.AUTOMATION_PRODUCTION
    assert action.detail and "ha_script_config_readonly" in action.detail


def test_unproved_script_catalog_cannot_create_operational_action():
    entities = _entities() + [
        EntityRecord("automation.via_script", "automation", "Via script", "on"),
        EntityRecord("light.proved", "light", "Lampe prouvée", "off"),
    ]
    docs = _docs() + [
        AutomationDoc("Via script", """
alias: Via script
triggers:
  - trigger: state
    entity_id: binary_sensor.entry_motion
    to: "on"
actions:
  - action: script.allume_lampe_prouvee
""", "Validated", 201)
    ]
    reconciliation = reconcile_automations(entities, docs)
    base = build_operational_graph(reconciliation)
    expanded = extend_graph_with_operational_scripts(base, [])
    assert expanded == base
    assert not any(x.predicate == "ACTS_ON" and x.object == "light.proved" for x in expanded)


def test_rex_cannot_override_exact_ha_current_identity_or_state():
    facts = [
        SourceFact("light.entry", FactType.CURRENT_STATE, "off", SourceKind.HA_CURRENT, evidence="ha_state_readonly"),
        SourceFact("light.entry", FactType.CURRENT_STATE, "on", SourceKind.REX, evidence="rex:user_correction"),
    ]
    winner = choose_preferred_fact(facts)
    assert winner is not None
    assert winner.value == "off"
    assert winner.source == SourceKind.HA_CURRENT


def test_rex_cannot_override_proved_production_behavior():
    facts = [
        SourceFact("automation.entry_main", FactType.BEHAVIOR, "motion turns entry lamp on", SourceKind.AUTOMATION_PRODUCTION, evidence="production_yaml"),
        SourceFact("automation.entry_main", FactType.BEHAVIOR, "window turns entry lamp on", SourceKind.REX, evidence="rex:field_note"),
    ]
    winner = choose_preferred_fact(facts)
    assert winner is not None
    assert winner.value == "motion turns entry lamp on"
    assert winner.source == SourceKind.AUTOMATION_PRODUCTION


def test_rex_can_override_weaker_historical_claim_for_meaning():
    facts = [
        SourceFact("object:entry", FactType.MEANING, "old label", SourceKind.HISTORY, evidence="journal:old"),
        SourceFact("object:entry", FactType.MEANING, "entrance lighting", SourceKind.REX, evidence="rex:validated"),
    ]
    winner = choose_preferred_fact(facts)
    assert winner is not None
    assert winner.value == "entrance lighting"
    assert winner.source == SourceKind.REX
