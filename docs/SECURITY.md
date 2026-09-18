# Home Assistant access contract

Élise Memory treats Home Assistant as a strictly read-only source.

Allowed:
- HTTP GET of entity state;
- HTTP GET of entity history.

Canonical Maison Cognitive wake/sleep reference:
- `switch.prise_de_comptage_prise_1`;
- `off -> on` = wake / awake cycle starts;
- `on -> off` = sleep / night cycle starts;
- the switch state is authoritative over clock-based assumptions.

Forbidden by design:
- service calls;
- state writes;
- automation/script execution;
- configuration changes;
- automatic guessing of entity IDs;
- mounting `/config`.

The Home Assistant token is supplied at runtime and is never stored in the
memory database.
