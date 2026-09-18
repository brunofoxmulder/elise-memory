# Home Assistant access contract

Élise Memory dev.4 treats Home Assistant as a read-only source.

Allowed:
- HTTP GET of an explicitly configured entity state.

Forbidden by design:
- service calls;
- state writes;
- automation/script execution;
- configuration changes;
- automatic guessing of entity IDs.

The Home Assistant token is supplied at runtime and is never stored in the
memory database.
