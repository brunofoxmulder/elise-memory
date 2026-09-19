"""Prototype of the second-generation deterministic house-memory engine.

The current production API is intentionally not wired to this module yet.
It is a pure layer used to prove the source-precedence, reconciliation and
object->relation->automation model before any Home Assistant deployment.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

import yaml


_ENTITY_ID_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
_OPAQUE_ENTITY_REF_RE = re.compile(r"^[0-9a-f]{32}$")
_TEMPLATE_ENTITY_RE = re.compile(
    r"(?:states|state_attr|is_state)\(\s*['\"]([^'\"]+)['\"]"
)

_STOPWORDS = {
    "a", "au", "aux", "avec", "ce", "ces", "cette", "dans", "de", "des",
    "du", "elle", "en", "est", "et", "fait", "la", "le", "les", "lors",
    "me", "mon", "ma", "mes", "ne", "par", "pour", "qu", "que", "quel",
    "quelle", "qui", "quoi", "sa", "se", "ses", "sur", "un", "une",
    "automatisation", "automatisations", "automation", "fonction",
    "fonctionne", "gerer", "gere", "gestion",
}
_ACTION_WORDS = {
    "allume", "allumer", "eteint", "eteindre", "coupe", "couper",
    "ouvre", "ouvrir", "ferme", "fermer", "active", "activer",
    "desactive", "desactiver", "demarre", "demarrer",
}


class SourceKind(StrEnum):
    HA_CURRENT = "ha_current"
    AUTOMATION_PRODUCTION = "automation_production"
    OBJECTS_HA = "objects_home_assistant"
    R8_RELATION = "r8_relation"
    METIER = "referentiel_metier"
    MEMORY_IA = "memory_ia"
    HISTORY = "history"


class FactType(StrEnum):
    EXISTENCE = "existence"
    CURRENT_STATE = "current_state"
    BEHAVIOR = "behavior"
    RELATION = "relation"
    MEANING = "meaning"
    HISTORY = "history"


_AUTHORITY: dict[FactType, dict[SourceKind, int]] = {
    FactType.EXISTENCE: {
        SourceKind.HA_CURRENT: 100,
        SourceKind.AUTOMATION_PRODUCTION: 60,
        SourceKind.OBJECTS_HA: 40,
        SourceKind.R8_RELATION: 35,
        SourceKind.METIER: 30,
        SourceKind.MEMORY_IA: 20,
        SourceKind.HISTORY: 10,
    },
    FactType.CURRENT_STATE: {
        SourceKind.HA_CURRENT: 100,
        SourceKind.AUTOMATION_PRODUCTION: 20,
        SourceKind.OBJECTS_HA: 20,
        SourceKind.R8_RELATION: 15,
        SourceKind.METIER: 10,
        SourceKind.MEMORY_IA: 10,
        SourceKind.HISTORY: 5,
    },
    FactType.BEHAVIOR: {
        SourceKind.AUTOMATION_PRODUCTION: 100,
        SourceKind.R8_RELATION: 80,
        SourceKind.OBJECTS_HA: 60,
        SourceKind.METIER: 55,
        SourceKind.MEMORY_IA: 45,
        SourceKind.HA_CURRENT: 30,
        SourceKind.HISTORY: 15,
    },
    FactType.RELATION: {
        SourceKind.AUTOMATION_PRODUCTION: 100,
        SourceKind.R8_RELATION: 90,
        SourceKind.OBJECTS_HA: 65,
        SourceKind.METIER: 50,
        SourceKind.MEMORY_IA: 40,
        SourceKind.HA_CURRENT: 30,
        SourceKind.HISTORY: 15,
    },
    FactType.MEANING: {
        SourceKind.METIER: 100,
        SourceKind.MEMORY_IA: 80,
        SourceKind.R8_RELATION: 70,
        SourceKind.AUTOMATION_PRODUCTION: 60,
        SourceKind.OBJECTS_HA: 40,
        SourceKind.HA_CURRENT: 30,
        SourceKind.HISTORY: 20,
    },
    FactType.HISTORY: {
        SourceKind.HISTORY: 100,
        SourceKind.MEMORY_IA: 60,
        SourceKind.METIER: 40,
        SourceKind.R8_RELATION: 40,
        SourceKind.AUTOMATION_PRODUCTION: 20,
        SourceKind.OBJECTS_HA: 10,
        SourceKind.HA_CURRENT: 10,
    },
}


@dataclass(frozen=True)
class SourceFact:
    key: str
    fact_type: FactType
    value: Any
    source: SourceKind
    current: bool = True
    evidence: str | None = None


@dataclass(frozen=True)
class EntityRecord:
    entity_id: str
    domain: str
    name: str
    state: str | None = None


@dataclass(frozen=True)
class AutomationDoc:
    name: str
    production: str
    status: str | None = None
    source_row: int | None = None


@dataclass(frozen=True)
class ReconciledAutomation:
    entity_id: str
    name: str
    state: str
    production: str
    status: str | None
    source_row: int | None
    match_by: str


@dataclass(frozen=True)
class ReconciliationResult:
    matched: tuple[ReconciledAutomation, ...]
    documented_only: tuple[AutomationDoc, ...]
    current_without_document: tuple[EntityRecord, ...]


@dataclass(frozen=True)
class GraphEdge:
    subject: str
    predicate: str
    object: str
    source: SourceKind
    detail: str | None = None


def normalize_text(value: object) -> str:
    text = " ".join(str(value or "").strip().split())
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text).lower()
        if not unicodedata.combining(c)
    )


def _tokens(value: object) -> list[str]:
    folded = normalize_text(value)
    return re.findall(r"[a-z0-9]+", folded)


def choose_preferred_fact(facts: Iterable[SourceFact]) -> SourceFact | None:
    """Choose by authority for the fact type, never by ingestion order."""
    usable = [fact for fact in facts if fact.current]
    if not usable:
        return None

    def rank(fact: SourceFact) -> tuple[int, str]:
        return (_AUTHORITY[fact.fact_type].get(fact.source, 0), fact.source.value)

    return max(usable, key=rank)


class _HALoader(yaml.SafeLoader):
    pass


def _unknown_tag(loader: _HALoader, tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


_HALoader.add_multi_constructor("!", _unknown_tag)


def parse_automation_yaml(production: str) -> list[dict[str, Any]]:
    if not production.strip():
        return []
    loaded = yaml.load(production, Loader=_HALoader)
    if loaded is None:
        return []
    if isinstance(loaded, dict):
        return [loaded]
    if isinstance(loaded, list):
        return [item for item in loaded if isinstance(item, dict)]
    raise ValueError("automation_production_must_be_mapping_or_list")


def _production_aliases(production: str) -> tuple[str, ...]:
    aliases: list[str] = []
    try:
        for item in parse_automation_yaml(production):
            alias = item.get("alias")
            if isinstance(alias, str) and alias.strip():
                aliases.append(alias.strip())
    except Exception:
        # A broken Production row must not become authoritative. The fallback is
        # only used for reconciliation diagnostics and does not parse behavior.
        match = re.search(r"(?:^|\n)\s*alias:\s*([^\n]+)", production)
        if match:
            aliases.append(match.group(1).strip().strip("'\""))
    return tuple(dict.fromkeys(aliases))


def ha_entities_from_rows(header: list[object], rows: list[list[object]]) -> list[EntityRecord]:
    names = [str(x or "").strip() for x in header]
    required = {"Entity ID", "Domaine", "Nom", "État"}
    if not required.issubset(set(names)):
        missing = sorted(required - set(names))
        raise ValueError("ha_reference_missing_columns:" + ",".join(missing))
    out: list[EntityRecord] = []
    for raw in rows:
        padded = list(raw) + [""] * (len(names) - len(raw))
        row = dict(zip(names, padded))
        entity_id = str(row["Entity ID"] or "").strip()
        if not entity_id:
            continue
        out.append(
            EntityRecord(
                entity_id=entity_id,
                domain=str(row["Domaine"] or "").strip(),
                name=str(row["Nom"] or "").strip(),
                state=str(row["État"] or "").strip() or None,
            )
        )
    return out


def automation_docs_from_rows(header: list[object], rows: list[list[object]]) -> list[AutomationDoc]:
    names = [str(x or "").strip() for x in header]
    required = {"Nom de l'automatisation", "Production", "Statut test"}
    if not required.issubset(set(names)):
        missing = sorted(required - set(names))
        raise ValueError("automation_sheet_missing_columns:" + ",".join(missing))
    out: list[AutomationDoc] = []
    for offset, raw in enumerate(rows, start=2):
        padded = list(raw) + [""] * (len(names) - len(raw))
        row = dict(zip(names, padded))
        name = str(row["Nom de l'automatisation"] or "").strip()
        if not name:
            continue
        out.append(
            AutomationDoc(
                name=name,
                production=str(row["Production"] or ""),
                status=str(row["Statut test"] or "").strip() or None,
                source_row=offset,
            )
        )
    return out


def reconcile_automations(
    entities: Iterable[EntityRecord],
    docs: Iterable[AutomationDoc],
) -> ReconciliationResult:
    """Reconcile documentation with the current HA inventory without fuzzy guessing."""
    current = [entity for entity in entities if entity.domain == "automation"]
    index: dict[str, list[EntityRecord]] = {}
    for entity in current:
        index.setdefault(normalize_text(entity.name), []).append(entity)

    matched: list[ReconciledAutomation] = []
    documented_only: list[AutomationDoc] = []
    used_entity_ids: set[str] = set()

    for doc in docs:
        candidate_names = [(normalize_text(doc.name), "sheet_name")]
        candidate_names.extend(
            (normalize_text(alias), "production_alias")
            for alias in _production_aliases(doc.production)
        )
        hits: dict[str, tuple[EntityRecord, str]] = {}
        for candidate, match_by in candidate_names:
            for entity in index.get(candidate, []):
                hits[entity.entity_id] = (entity, match_by)

        if len(hits) != 1:
            documented_only.append(doc)
            continue

        entity, match_by = next(iter(hits.values()))
        used_entity_ids.add(entity.entity_id)
        matched.append(
            ReconciledAutomation(
                entity_id=entity.entity_id,
                name=entity.name,
                state=entity.state or "",
                production=doc.production,
                status=doc.status,
                source_row=doc.source_row,
                match_by=match_by,
            )
        )

    current_without_document = [
        entity for entity in current if entity.entity_id not in used_entity_ids
    ]
    return ReconciliationResult(
        matched=tuple(matched),
        documented_only=tuple(documented_only),
        current_without_document=tuple(current_without_document),
    )


def _entity_refs(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_entity_refs(item))
        return out
    return []


def _node_for_entity_ref(ref: str) -> str:
    ref = ref.strip()
    if _ENTITY_ID_RE.match(ref):
        return ref
    if _OPAQUE_ENTITY_REF_RE.match(ref):
        return f"registry_ref:{ref}"
    return f"unresolved_ref:{ref}"


def _detail(**values: Any) -> str:
    compact = {key: value for key, value in values.items() if value not in (None, "", [], {})}
    return json.dumps(compact, ensure_ascii=False, sort_keys=True)


def _template_refs(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return set(_TEMPLATE_ENTITY_RE.findall(value))


def _effect_for_service(service: str, data: Any = None) -> str | None:
    if service == "cover.set_cover_position" and isinstance(data, dict):
        position = data.get("position")
        try:
            numeric = float(position)
        except (TypeError, ValueError):
            numeric = None
        if numeric == 100:
            return "open"
        if numeric == 0:
            return "close"
        return "set_position"
    mapping = {
        "light.turn_on": "turn_on",
        "light.turn_off": "turn_off",
        "switch.turn_on": "turn_on",
        "switch.turn_off": "turn_off",
        "input_boolean.turn_on": "turn_on",
        "input_boolean.turn_off": "turn_off",
        "cover.open_cover": "open",
        "cover.close_cover": "close",
        "lock.lock": "lock",
        "lock.unlock": "unlock",
        "climate.set_hvac_mode": "set_hvac_mode",
        "climate.set_temperature": "set_temperature",
        "input_select.select_option": "select_option",
        "automation.trigger": "trigger",
    }
    return mapping.get(service)


def _walk_trigger(
    node: Any,
    automation_id: str,
    edges: list[GraphEdge],
    *,
    predicate: str = "TRIGGERS",
) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_trigger(item, automation_id, edges, predicate=predicate)
        return
    if not isinstance(node, dict):
        return

    detail = _detail(
        trigger=node.get("trigger") or node.get("platform"),
        from_state=node.get("from"),
        to_state=node.get("to"),
        above=node.get("above"),
        below=node.get("below"),
        duration=node.get("for"),
        trigger_id=node.get("id"),
    )
    for ref in _entity_refs(node.get("entity_id")):
        edges.append(
            GraphEdge(
                _node_for_entity_ref(ref), predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION, detail,
            )
        )

    trigger_kind = node.get("trigger") or node.get("platform")
    if trigger_kind == "sun":
        edges.append(
            GraphEdge(
                "sun.sun", predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(event=node.get("event"), offset=node.get("offset")),
            )
        )
    elif trigger_kind == "time" and node.get("at"):
        edges.append(
            GraphEdge(
                f"time:{node.get('at')}", predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION, detail,
            )
        )
    elif trigger_kind == "time_pattern":
        edges.append(
            GraphEdge(
                "time_pattern", predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(hours=node.get("hours"), minutes=node.get("minutes"), seconds=node.get("seconds")),
            )
        )
    elif trigger_kind == "event" and node.get("event_type"):
        edges.append(
            GraphEdge(
                f"event:{node.get('event_type')}", predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION, detail,
            )
        )

    for value in node.values():
        for ref in _template_refs(value):
            edges.append(
                GraphEdge(
                    ref, predicate, automation_id,
                    SourceKind.AUTOMATION_PRODUCTION,
                    _detail(via="template"),
                )
            )


def _walk_condition(
    node: Any,
    automation_id: str,
    edges: list[GraphEdge],
    *,
    predicate: str = "GUARDS",
) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_condition(item, automation_id, edges, predicate=predicate)
        return
    if not isinstance(node, dict):
        return

    condition = node.get("condition")
    detail = _detail(
        condition=condition,
        state=node.get("state"),
        above=node.get("above"),
        below=node.get("below"),
        duration=node.get("for"),
        attribute=node.get("attribute"),
        trigger_id=node.get("id"),
    )
    for ref in _entity_refs(node.get("entity_id")):
        edges.append(
            GraphEdge(
                _node_for_entity_ref(ref), predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION, detail,
            )
        )
    if condition == "sun":
        edges.append(
            GraphEdge(
                "sun.sun", predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(after=node.get("after"), before=node.get("before"),
                        after_offset=node.get("after_offset"), before_offset=node.get("before_offset")),
            )
        )

    for value in node.values():
        for ref in _template_refs(value):
            edges.append(
                GraphEdge(
                    ref, predicate, automation_id,
                    SourceKind.AUTOMATION_PRODUCTION,
                    _detail(via="template"),
                )
            )

    for key in ("conditions", "and", "or", "not"):
        if key in node:
            _walk_condition(node[key], automation_id, edges, predicate=predicate)


def _walk_actions(node: Any, automation_id: str, edges: list[GraphEdge]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_actions(item, automation_id, edges)
        return
    if not isinstance(node, dict):
        return

    if "delay" in node:
        edges.append(
            GraphEdge(
                automation_id, "BARRIER", f"delay:{json.dumps(node['delay'], sort_keys=True)}",
                SourceKind.AUTOMATION_PRODUCTION,
            )
        )

    if "wait_for_trigger" in node:
        _walk_trigger(node["wait_for_trigger"], automation_id, edges, predicate="WAITS_FOR")

    service = node.get("action") or node.get("service")
    if isinstance(service, str) and "." in service:
        target = node.get("target")
        target_refs: list[str] = []
        if isinstance(target, dict):
            target_refs.extend(_entity_refs(target.get("entity_id")))
        target_refs.extend(_entity_refs(node.get("entity_id")))

        predicate = "CALLS_AUTOMATION" if service == "automation.trigger" else "ACTS_ON"
        if target_refs:
            for ref in dict.fromkeys(target_refs):
                edges.append(
                    GraphEdge(
                        automation_id,
                        predicate,
                        _node_for_entity_ref(ref),
                        SourceKind.AUTOMATION_PRODUCTION,
                        _detail(
                            service=service,
                            effect=_effect_for_service(service, node.get("data")),
                            data=node.get("data"),
                        ),
                    )
                )
        else:
            edges.append(
                GraphEdge(
                    automation_id, "CALLS_SERVICE", f"service:{service}",
                    SourceKind.AUTOMATION_PRODUCTION,
                    _detail(service=service, effect=_effect_for_service(service, node.get("data"))),
                )
            )

    if (
        isinstance(node.get("type"), str)
        and isinstance(node.get("domain"), str)
        and node.get("entity_id")
        and not (isinstance(service, str) and "." in service)
    ):
        pseudo_service = f"{node['domain']}.{node['type']}"
        for ref in _entity_refs(node.get("entity_id")):
            edges.append(
                GraphEdge(
                    automation_id, "ACTS_ON", _node_for_entity_ref(ref),
                    SourceKind.AUTOMATION_PRODUCTION,
                    _detail(
                        service=pseudo_service,
                        effect=node.get("type"),
                        device_id=node.get("device_id"),
                        via="device_action",
                    ),
                )
            )

    if "condition" in node and not (isinstance(service, str) and "." in service):
        _walk_condition(node, automation_id, edges, predicate="LOCAL_GUARD")

    if "choose" in node and isinstance(node["choose"], list):
        for choice in node["choose"]:
            if not isinstance(choice, dict):
                continue
            _walk_condition(choice.get("conditions"), automation_id, edges, predicate="LOCAL_GUARD")
            _walk_actions(choice.get("sequence"), automation_id, edges)
    if "default" in node:
        _walk_actions(node["default"], automation_id, edges)
    for key in ("sequence", "parallel", "repeat"):
        if key in node:
            value = node[key]
            if key == "repeat" and isinstance(value, dict):
                _walk_condition(value.get("while"), automation_id, edges, predicate="LOCAL_GUARD")
                _walk_condition(value.get("until"), automation_id, edges, predicate="LOCAL_GUARD")
                _walk_actions(value.get("sequence"), automation_id, edges)
            else:
                _walk_actions(value, automation_id, edges)


def extract_automation_edges(automation: ReconciledAutomation) -> list[GraphEdge]:
    """Extract operational relations only from a reconciled current automation."""
    edges: list[GraphEdge] = []
    for config in parse_automation_yaml(automation.production):
        _walk_trigger(
            config.get("triggers", config.get("trigger")),
            automation.entity_id,
            edges,
        )
        _walk_condition(
            config.get("conditions", config.get("condition")),
            automation.entity_id,
            edges,
        )
        _walk_actions(
            config.get("actions", config.get("action")),
            automation.entity_id,
            edges,
        )
    # Stable de-duplication protects nested parsing from producing duplicates.
    return list(dict.fromkeys(edges))


def build_operational_graph(
    reconciliation: ReconciliationResult,
    *,
    include_disabled: bool = False,
) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    for automation in reconciliation.matched:
        if not include_disabled and automation.state != "on":
            continue
        if not automation.production.strip():
            continue
        edges.extend(extract_automation_edges(automation))
    return list(dict.fromkeys(edges))


def _intent(query: str) -> str | None:
    text = normalize_text(query)
    if re.search(r"\b(allum\w*|activ\w*|demarr\w*)\b", text) or re.search(
        r"\bturn(?:s|ed|ing)?\s+on\b", text
    ):
        return "turn_on"
    if re.search(r"\b(etein\w*|coup\w*|arret\w*|desactiv\w*)\b", text) or re.search(
        r"\bturn(?:s|ed|ing)?\s+off\b", text
    ):
        return "turn_off"
    if re.search(r"\b(ouvr\w*|ouverture|open\w*)\b", text):
        return "open"
    if re.search(r"\b(ferm\w*|fermeture|clos\w*)\b", text):
        return "close"
    return None


def _object_tokens(query: str) -> set[str]:
    return {
        token
        for token in _tokens(query)
        if token not in _STOPWORDS and token not in _ACTION_WORDS and len(token) >= 2
    }


def resolve_entities(
    query: str,
    entities: Iterable[EntityRecord],
    *,
    limit: int = 5,
) -> list[tuple[EntityRecord, int]]:
    """Resolve a natural object phrase against current HA identity, not Drive mentions."""
    qnorm = normalize_text(query)
    qtokens = _object_tokens(query)
    if not qtokens:
        qtokens = {token for token in _tokens(query) if token not in _STOPWORDS}
    hints: set[str] = set()
    if {"lampe", "hotte"} & qtokens:
        hints.add("light")
    if "volet" in qtokens:
        hints.add("cover")
    if {"prise", "chargeur"} & qtokens:
        hints.add("switch")
    if {"serrure"} & qtokens:
        hints.add("lock")

    scored: list[tuple[EntityRecord, int]] = []
    for entity in entities:
        name_norm = normalize_text(entity.name)
        entity_norm = normalize_text(entity.entity_id)
        name_tokens = set(_tokens(entity.name))
        score = 0
        if qnorm == name_norm or qnorm == entity_norm:
            score = 140
        elif name_norm and name_norm in qnorm:
            score = 115 + min(len(name_tokens), 10)
        elif qtokens and qtokens.issubset(name_tokens):
            score = 100 + len(qtokens)
        else:
            overlap = len(qtokens & name_tokens)
            if overlap:
                score = int(60 * overlap / max(len(qtokens), 1))
        if hints and entity.domain in hints:
            score += 15
        elif hints and entity.domain not in hints:
            score -= 20
        if score > 0:
            scored.append((entity, score))
    scored.sort(key=lambda item: (-item[1], item[0].entity_id))
    return scored[: max(1, limit)]


def retrieve_automation_chains(
    query: str,
    entities: Iterable[EntityRecord],
    reconciliation: ReconciliationResult,
    edges: Iterable[GraphEdge],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Return direct operational chains; textual mentions never compete with action edges."""
    entity_list = list(entities)
    candidates = resolve_entities(query, entity_list, limit=5)
    if not candidates:
        return []
    # Object resolution is a separate stage. Only equally-best identity
    # candidates may enter operational retrieval; lower-scored lexical matches
    # (for example another lamp elsewhere in the house) must not compete.
    best_object_score = candidates[0][1]
    candidates = [
        candidate for candidate in candidates
        if candidate[1] == best_object_score
    ]

    active = {
        item.entity_id: item
        for item in reconciliation.matched
        if item.state == "on"
    }
    edge_list = list(edges)
    intent = _intent(query)
    results: list[dict[str, Any]] = []

    for target, object_score in candidates:
        for edge in edge_list:
            if edge.predicate != "ACTS_ON" or edge.object != target.entity_id:
                continue
            automation = active.get(edge.subject)
            if not automation:
                continue
            detail = json.loads(edge.detail) if edge.detail else {}
            effect = detail.get("effect")
            if intent and effect and effect != intent:
                # An explicit action verb is a semantic filter, not merely a
                # ranking hint: an OFF edge must not answer an ON question.
                continue
            score = object_score + 100
            if intent and effect == intent:
                score += 40

            context_edges = [
                candidate
                for candidate in edge_list
                if candidate.object == automation.entity_id
                and candidate.predicate in {"TRIGGERS", "GUARDS", "WAITS_FOR", "LOCAL_GUARD"}
            ]
            results.append(
                {
                    "score": score,
                    "target_entity_id": target.entity_id,
                    "target_name": target.name,
                    "automation_entity_id": automation.entity_id,
                    "automation_name": automation.name,
                    "effect": effect,
                    "action_detail": detail,
                    "context": [
                        {
                            "subject": item.subject,
                            "predicate": item.predicate,
                            "detail": json.loads(item.detail) if item.detail else {},
                        }
                        for item in context_edges
                    ],
                }
            )

    # One result per automation/target/effect, ordered by evidence rather than row age.
    dedup: dict[tuple[str, str, str | None], dict[str, Any]] = {}
    for result in results:
        key = (
            result["automation_entity_id"],
            result["target_entity_id"],
            result["effect"],
        )
        previous = dedup.get(key)
        if previous is None or result["score"] > previous["score"]:
            dedup[key] = result
    return sorted(
        dedup.values(),
        key=lambda item: (-item["score"], item["automation_entity_id"]),
    )[: max(1, limit)]
