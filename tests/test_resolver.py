from datetime import datetime, timezone
from elise_memory.ha_reader import HAState
from elise_memory.resolver import resolve_current_entity

class Reader:
    def get_states(self):
        now = datetime.now(timezone.utc)
        return [
            HAState("light.hue_tento_color_panel_1_3", "off", now, {"friendly_name": "lampe salon"}),
            HAState("light.lampe_cuisine", "on", now, {"friendly_name": "lampe cuisine"}),
            HAState("cover.volet_salon_2", "open", now, {"friendly_name": "volet salon"}),
        ]

def test_exact_friendly_name_resolves_current_ha_entity():
    result = resolve_current_entity(Reader(), "lampe salon")
    assert result.resolved is True
    assert result.candidates[0].entity_id == "light.hue_tento_color_panel_1_3"
    assert result.candidates[0].provenance == "ha_current"

def test_domain_hint_prevents_lamp_cover_confusion():
    result = resolve_current_entity(Reader(), "volet salon")
    assert result.resolved is True
    assert result.candidates[0].entity_id == "cover.volet_salon_2"

def test_ambiguous_request_fails_closed():
    result = resolve_current_entity(Reader(), "salon")
    assert result.resolved is False
    assert len(result.candidates) >= 2

def test_unknown_target_fails_closed():
    result = resolve_current_entity(Reader(), "lampe garage")
    assert result.resolved is False
