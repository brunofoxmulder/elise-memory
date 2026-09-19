import json

from elise_memory.engine_v2 import (
    AutomationDoc,
    EntityRecord,
    FactType,
    SourceFact,
    SourceKind,
    build_operational_graph,
    choose_preferred_fact,
    reconcile_automations,
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
    assert result[0]["effect"] == "set_position"


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
