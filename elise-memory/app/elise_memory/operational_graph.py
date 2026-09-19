"""Deterministic V2 operational graph for Élise Memory.

This module is deliberately additive: it does not replace the deployed V1 search path.
It reconciles Drive documentation with the current HA inventory, parses only Production
YAML, and turns behavior into atomic, provenance-preserving relations.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable

import yaml

_OPAQUE_REF = re.compile(r"^[0-9a-f]{32}$", re.I)
_ENTITY_IN_TEMPLATE = re.compile(
    r"(?:states|state_attr|is_state)\(\s*['\"]([a-z_]+\.[^'\"]+)['\"]",
    re.I,
)


def _norm(value: object) -> str:
    text = " ".join(str(value or "").strip().split())
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(c)
    )
    text = text.replace("’", "").replace("'", "")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _row_map(header: list[object], row: list[object]) -> dict[str, str]:
    names = [str(x or "").strip() for x in header]
    padded = list(row) + [""] * (len(names) - len(row))
    return {name: str(value or "").strip() for name, value in zip(names, padded)}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _entity_values(value: Any) -> list[str]:
    out: list[str] = []
    for item in _as_list(value):
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _node_for_ref(ref: str) -> tuple[str, str]:
    if _OPAQUE_REF.fullmatch(ref):
        return f"registry_ref:{ref.lower()}", "registry_ref"
    if "." in ref:
        return ref, "entity"
    return f"symbol:{ref}", "symbol"


def _service_effect(action: str | None) -> str | None:
    if not action:
        return None
    action = action.strip().lower()
    mapping = {
        "light.turn_on": "turn_on",
        "light.turn_off": "turn_off",
        "switch.turn_on": "turn_on",
        "switch.turn_off": "turn_off",
        "cover.open_cover": "open",
        "cover.close_cover": "close",
        "cover.set_cover_position": "set_position",
        "lock.lock": "lock",
        "lock.unlock": "unlock",
        "climate.set_hvac_mode": "set_hvac_mode",
        "climate.set_temperature": "set_temperature",
        "input_boolean.turn_on": "turn_on",
        "input_boolean.turn_off": "turn_off",
        "input_select.select_option": "select_option",
        "automation.trigger": "trigger_automation",
        "automation.turn_on": "enable_automation",
        "automation.turn_off": "disable_automation",
    }
    return mapping.get(action, action)


@dataclass(frozen=True)
class CurrentObject:
    entity_id: str
    domain: str
    name: str
    state: str

    @property
    def active_automation(self) -> bool:
        return self.domain == "automation" and self.state == "on"


@dataclass(frozen=True)
class AutomationDocument:
    name: str
    domain: str
    description: str
    production: str
    status: str
    source_row: int
    alias: str | None = None


@dataclass(frozen=True)
class ReconciledAutomation:
    entity_id: str
    current_name: str
    state: str
    document: AutomationDocument
    match_method: str


@dataclass(frozen=True)
class GraphEdge:
    subject: str
    relation: str
    object: str
    source: str
    role: str | None = None
    effect: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationalGraph:
    objects: dict[str, CurrentObject]
    automations: dict[str, ReconciledAutomation]
    edges: list[GraphEdge]
    aliases: dict[str, set[str]]
    unresolved_documents: list[AutomationDocument]

    def resolve_object(self, query: str) -> list[str]:
        """Resolve a natural name only against current HA identities/aliases.

        Exact normalized identity/name wins. Token matching is a fallback over current
        HA object names only; documentation text is never used to resolve an object.
        """
        raw = query.strip()
        if raw in self.objects:
            return [raw]
        nq = _norm(raw)
        direct = sorted(self.aliases.get(nq, set()))
        if direct:
            return direct

        terms = [t for t in nq.split() if len(t) >= 2]
        if not terms:
            return []
        scored: list[tuple[int, int, str]] = []
        for entity_id, obj in self.objects.items():
            hay = set((_norm(obj.name) + " " + _norm(entity_id)).split())
            matched = sum(1 for t in terms if t in hay)
            if matched:
                scored.append((matched, -len(hay), entity_id))
        if not scored:
            return []
        scored.sort(reverse=True)
        best = scored[0][0]
        return sorted(entity_id for matched, _, entity_id in scored if matched == best)

    def automation_context_for(
        self,
        target: str,
        *,
        effect: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return active automations that actually act on a resolved target."""
        candidates = []
        for edge in self.edges:
            if edge.relation != "ACTS_ON" or edge.object != target:
                continue
            if effect and edge.effect != effect:
                continue
            auto_id = edge.subject
            auto = self.automations.get(auto_id)
            if not auto or auto.state != "on":
                continue
            related = [e for e in self.edges if e.object == auto_id or e.subject == auto_id]
            candidates.append({
                "automation_id": auto_id,
                "automation_name": auto.current_name,
                "effect": edge.effect,
                "action": edge.metadata.get("action"),
                "action_metadata": edge.metadata,
                "triggers": [e for e in related if e.relation == "TRIGGERS"],
                "guards": [e for e in related if e.relation == "GUARDS"],
                "waits": [e for e in related if e.relation == "WAITS_FOR"],
                "barriers": [e for e in related if e.relation == "BARRIER"],
                "calls": [e for e in related if e.relation == "CALLS_AUTOMATION"],
                "source": edge.source,
            })
        candidates.sort(key=lambda x: (x["automation_name"].lower(), x["automation_id"]))
        return candidates


def parse_current_objects(header: list[object], rows: list[list[object]]) -> dict[str, CurrentObject]:
    required = {"Entity ID", "Domaine", "Nom", "État"}
    names = {str(x or "").strip() for x in header}
    missing = required - names
    if missing:
        raise ValueError("current_inventory_missing:" + ",".join(sorted(missing)))
    out: dict[str, CurrentObject] = {}
    for raw in rows:
        row = _row_map(header, raw)
        entity_id = row["Entity ID"]
        if not entity_id:
            continue
        out[entity_id] = CurrentObject(
            entity_id=entity_id,
            domain=row["Domaine"],
            name=row["Nom"],
            state=row["État"],
        )
    return out


def _production_root(text: str) -> dict[str, Any]:
    loaded = yaml.safe_load(text)
    if isinstance(loaded, list):
        if len(loaded) != 1 or not isinstance(loaded[0], dict):
            raise ValueError("production_yaml_requires_single_automation")
        loaded = loaded[0]
    if not isinstance(loaded, dict):
        raise ValueError("production_yaml_not_mapping")
    return loaded


def parse_automation_documents(
    header: list[object],
    rows: list[list[object]],
) -> list[AutomationDocument]:
    required = {"Nom de l'automatisation", "Domaine", "Descriptif", "Production", "Statut test"}
    names = {str(x or "").strip() for x in header}
    missing = required - names
    if missing:
        raise ValueError("automation_source_missing:" + ",".join(sorted(missing)))
    out = []
    for i, raw in enumerate(rows, start=2):
        row = _row_map(header, raw)
        name, production = row["Nom de l'automatisation"], row["Production"]
        if not name or not production:
            continue
        try:
            root = _production_root(production)
        except Exception:
            # Keep the document visible to diagnostics; it cannot enter the graph.
            alias = None
        else:
            alias = str(root.get("alias") or "").strip() or None
        out.append(AutomationDocument(
            name=name,
            domain=row["Domaine"],
            description=row["Descriptif"],
            production=production,
            status=row["Statut test"],
            source_row=i,
            alias=alias,
        ))
    return out


def reconcile_automations(
    objects: dict[str, CurrentObject],
    documents: list[AutomationDocument],
) -> tuple[dict[str, ReconciledAutomation], list[AutomationDocument]]:
    current = [o for o in objects.values() if o.domain == "automation"]
    by_name: dict[str, list[CurrentObject]] = {}
    for obj in current:
        by_name.setdefault(_norm(obj.name), []).append(obj)

    reconciled: dict[str, ReconciledAutomation] = {}
    unresolved: list[AutomationDocument] = []
    for doc in documents:
        matches = by_name.get(_norm(doc.name), [])
        method = "name"
        if len(matches) != 1 and doc.alias:
            matches = by_name.get(_norm(doc.alias), [])
            method = "yaml_alias"
        if len(matches) != 1:
            unresolved.append(doc)
            continue
        obj = matches[0]
        reconciled[obj.entity_id] = ReconciledAutomation(
            entity_id=obj.entity_id,
            current_name=obj.name,
            state=obj.state,
            document=doc,
            match_method=method,
        )
    return reconciled, unresolved


def _template_refs(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return sorted(set(_ENTITY_IN_TEMPLATE.findall(value)))


def _collect_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "entity_id":
                refs.extend(_entity_values(item))
            refs.extend(_collect_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.extend(_collect_refs(item))
    elif isinstance(value, str):
        refs.extend(_template_refs(value))
    return refs


def _emit_ref_edge(
    edges: list[GraphEdge],
    *,
    ref: str,
    relation: str,
    auto_id: str,
    source: str,
    role: str | None = None,
    effect: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    node, node_type = _node_for_ref(ref)
    payload = dict(metadata or {})
    payload.setdefault("node_type", node_type)
    if relation in {"TRIGGERS", "GUARDS", "WAITS_FOR", "READS"}:
        subject, obj = node, auto_id
    else:
        subject, obj = auto_id, node
    edges.append(GraphEdge(
        subject=subject, relation=relation, object=obj, source=source,
        role=role, effect=effect, metadata=payload,
    ))


def _walk_conditions(value: Any, auto_id: str, source: str, edges: list[GraphEdge], relation="GUARDS") -> None:
    for ref in sorted(set(_collect_refs(value))):
        _emit_ref_edge(edges, ref=ref, relation=relation, auto_id=auto_id, source=source)


def _walk_actions(value: Any, auto_id: str, source: str, edges: list[GraphEdge]) -> None:
    for step in _as_list(value):
        if not isinstance(step, dict):
            continue

        if "delay" in step:
            edges.append(GraphEdge(
                subject=auto_id, relation="BARRIER", object=auto_id, source=source,
                role="delay", metadata={"delay": step.get("delay")},
            ))

        if "wait_for_trigger" in step:
            _walk_conditions(step.get("wait_for_trigger"), auto_id, source, edges, relation="WAITS_FOR")

        if "condition" in step and "action" not in step and "service" not in step:
            _walk_conditions(step, auto_id, source, edges, relation="GUARDS")

        action = step.get("action") or step.get("service")
        effect = _service_effect(str(action)) if action else None

        # HA service-style action.
        if action:
            target = step.get("target") or {}
            refs = _entity_values(target.get("entity_id")) if isinstance(target, dict) else []
            # Some actions put entity_id directly under data or the step.
            refs.extend(_entity_values(step.get("entity_id")))
            data = step.get("data") if isinstance(step.get("data"), dict) else {}
            refs.extend(_entity_values(data.get("entity_id")))
            for ref in sorted(set(refs)):
                if effect == "trigger_automation" and ref.startswith("automation."):
                    edges.append(GraphEdge(
                        subject=auto_id, relation="CALLS_AUTOMATION", object=ref,
                        source=source, effect=effect,
                        metadata={"action": str(action)},
                    ))
                else:
                    meta = {"action": str(action)}
                    if "position" in data:
                        meta["position"] = data["position"]
                    if "option" in data:
                        meta["option"] = data["option"]
                    _emit_ref_edge(
                        edges, ref=ref, relation="ACTS_ON", auto_id=auto_id,
                        source=source, effect=effect, metadata=meta,
                    )

        # HA device-style action: type + device_id + entity_id + domain.
        if "type" in step and "entity_id" in step and step.get("domain"):
            dtype = str(step.get("type"))
            for ref in _entity_values(step.get("entity_id")):
                _emit_ref_edge(
                    edges, ref=ref, relation="ACTS_ON", auto_id=auto_id, source=source,
                    effect=dtype, metadata={
                        "action": f"device:{step.get('domain')}:{dtype}",
                        "device_id": step.get("device_id"),
                    },
                )

        # Branches.
        if "choose" in step:
            for branch in _as_list(step.get("choose")):
                if not isinstance(branch, dict):
                    continue
                _walk_conditions(branch.get("conditions"), auto_id, source, edges, relation="GUARDS")
                _walk_actions(branch.get("sequence"), auto_id, source, edges)
            _walk_actions(step.get("default"), auto_id, source, edges)

        # Nested sequence/parallel are legitimate action containers.
        if "sequence" in step and "choose" not in step:
            _walk_actions(step.get("sequence"), auto_id, source, edges)
        if "parallel" in step:
            _walk_actions(step.get("parallel"), auto_id, source, edges)

        # Template reads inside variables/data are contextual reads, not causal actions.
        for ref in sorted(set(_template_refs(str(step.get("variables") or "")))):
            _emit_ref_edge(edges, ref=ref, relation="READS", auto_id=auto_id, source=source)


def compile_automation_edges(auto: ReconciledAutomation) -> list[GraphEdge]:
    root = _production_root(auto.document.production)
    source = f"Automatisations/Automatisations/row:{auto.document.source_row}"
    edges: list[GraphEdge] = []

    triggers = root.get("triggers", root.get("trigger"))
    for ref in sorted(set(_collect_refs(triggers))):
        _emit_ref_edge(edges, ref=ref, relation="TRIGGERS", auto_id=auto.entity_id, source=source)

    conditions = root.get("conditions", root.get("condition"))
    _walk_conditions(conditions, auto.entity_id, source, edges, relation="GUARDS")

    actions = root.get("actions", root.get("action"))
    _walk_actions(actions, auto.entity_id, source, edges)

    return edges


def build_operational_graph(
    ha_header: list[object],
    ha_rows: list[list[object]],
    automation_header: list[object],
    automation_rows: list[list[object]],
) -> OperationalGraph:
    objects = parse_current_objects(ha_header, ha_rows)
    documents = parse_automation_documents(automation_header, automation_rows)
    reconciled, unresolved = reconcile_automations(objects, documents)

    aliases: dict[str, set[str]] = {}
    for entity_id, obj in objects.items():
        for alias in {_norm(entity_id), _norm(obj.name)}:
            if alias:
                aliases.setdefault(alias, set()).add(entity_id)

    edges: list[GraphEdge] = []
    active: dict[str, ReconciledAutomation] = {}
    for entity_id, auto in reconciled.items():
        if auto.state != "on":
            continue
        active[entity_id] = auto
        edges.extend(compile_automation_edges(auto))

    # Deduplicate exact atomic facts without merging provenance or inventing semantics.
    unique: dict[tuple[Any, ...], GraphEdge] = {}
    for edge in edges:
        key = (
            edge.subject, edge.relation, edge.object, edge.source,
            edge.role, edge.effect, repr(sorted(edge.metadata.items())),
        )
        unique[key] = edge

    return OperationalGraph(
        objects=objects,
        automations=active,
        edges=list(unique.values()),
        aliases=aliases,
        unresolved_documents=unresolved,
    )
