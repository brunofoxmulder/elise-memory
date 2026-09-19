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
_TEMPLATE_DOTTED_ENTITY_RE = re.compile(
    r"\bstates\.([a-z_][a-z0-9_]*)\.([a-z0-9_]+)\b",
    re.I,
)

_STOPWORDS = {
    "a", "au", "aux", "avec", "ce", "ces", "cette", "dans", "de", "des",
    "du", "elle", "en", "est", "et", "fait", "la", "le", "les", "lors",
    "me", "mon", "ma", "mes", "ne", "par", "pour", "qu", "que", "quel",
    "quelle", "qui", "quoi", "sa", "se", "ses", "sur", "un", "une",
    "automatisation", "automatisations", "automation", "fonction",
    "fonctionne", "gerer", "gere", "gestion",
    "quand", "lorsque", "si", "alors", "je", "j", "tu", "il", "on",
    "nous", "vous", "ils", "elles", "arrive", "arrivent", "passe",
}
_ACTION_WORDS = {
    "allume", "allumer", "eteint", "eteindre", "coupe", "couper",
    "ouvre", "ouvrir", "ferme", "fermer", "active", "activer",
    "desactive", "desactiver", "demarre", "demarrer",
    "verrouille", "verrouiller", "deverrouille", "deverrouiller",
    "charge", "charger", "recharge", "recharger",
}

_TOKEN_EQUIVALENTS: dict[str, set[str]] = {
    "batterie": {"battery"},
    "battery": {"batterie"},
    "puissance": {"power"},
    "power": {"puissance"},
    "mouvement": {"motion"},
    "motion": {"mouvement"},
    "fenetre": {"window"},
    "window": {"fenetre"},
    "volet": {"shutter"},
    "shutter": {"volet"},
    "lampe": {"lamp", "light"},
    "lamp": {"lampe", "light"},
    "humidite": {"humidity"},
    "humidity": {"humidite"},
}


class SourceKind(StrEnum):
    HA_CURRENT = "ha_current"
    AUTOMATION_PRODUCTION = "automation_production"
    OBJECTS_HA = "objects_home_assistant"
    R8_RELATION = "r8_relation"
    METIER = "referentiel_metier"
    MEMORY_IA = "memory_ia"
    HISTORY = "history"
    REX = "rex"


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
        SourceKind.REX: 25
    },
    FactType.CURRENT_STATE: {
        SourceKind.HA_CURRENT: 100,
        SourceKind.AUTOMATION_PRODUCTION: 20,
        SourceKind.OBJECTS_HA: 20,
        SourceKind.R8_RELATION: 15,
        SourceKind.METIER: 10,
        SourceKind.MEMORY_IA: 10,
        SourceKind.HISTORY: 5,
        SourceKind.REX: 25
    },
    FactType.BEHAVIOR: {
        SourceKind.AUTOMATION_PRODUCTION: 100,
        SourceKind.R8_RELATION: 80,
        SourceKind.OBJECTS_HA: 60,
        SourceKind.METIER: 55,
        SourceKind.MEMORY_IA: 45,
        SourceKind.HA_CURRENT: 30,
        SourceKind.HISTORY: 15,
        SourceKind.REX: 25
    },
    FactType.RELATION: {
        SourceKind.AUTOMATION_PRODUCTION: 100,
        SourceKind.R8_RELATION: 90,
        SourceKind.OBJECTS_HA: 65,
        SourceKind.METIER: 50,
        SourceKind.MEMORY_IA: 40,
        SourceKind.HA_CURRENT: 30,
        SourceKind.HISTORY: 15,
        SourceKind.REX: 25
    },
    FactType.MEANING: {
        SourceKind.METIER: 100,
        SourceKind.MEMORY_IA: 80,
        SourceKind.R8_RELATION: 70,
        SourceKind.AUTOMATION_PRODUCTION: 60,
        SourceKind.OBJECTS_HA: 40,
        SourceKind.HA_CURRENT: 30,
        SourceKind.HISTORY: 20,
        SourceKind.REX: 25
    },
    FactType.HISTORY: {
        SourceKind.HISTORY: 100,
        SourceKind.MEMORY_IA: 60,
        SourceKind.METIER: 40,
        SourceKind.R8_RELATION: 40,
        SourceKind.AUTOMATION_PRODUCTION: 20,
        SourceKind.OBJECTS_HA: 10,
        SourceKind.HA_CURRENT: 10,
        SourceKind.REX: 25
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
class OperationalScript:
    """Executable script/Pyscript body from an explicitly trusted operational source."""

    service: str
    production: str
    source: str


@dataclass(frozen=True)
class GraphEdge:
    subject: str
    predicate: str
    object: str
    source: SourceKind
    detail: str | None = None


@dataclass(frozen=True)
class BusinessFunctionDoc:
    function: str
    reference: str
    object_type: str | None = None
    rule: str | None = None
    source_official: str | None = None
    last_validation: str | None = None


@dataclass(frozen=True)
class ReconciledBusinessFunction:
    function: str
    reference: str
    object_type: str | None
    rule: str | None
    source_official: str | None
    last_validation: str | None
    binding_entity_id: str | None
    binding_status: str


@dataclass(frozen=True)
class ObjectDependencyDoc:
    object_ref: str
    automation_name: str
    domain: str | None = None
    name: str | None = None
    observed_state: str | None = None


@dataclass(frozen=True)
class R8RelationDoc:
    relation_id: str
    chain: str
    source_type: str
    source_id: str
    relation: str
    target_type: str
    target_id: str
    role: str | None
    evidence: str | None
    confidence: str | None
    status: str
    last_verification: str | None


@dataclass(frozen=True)
class RegistryBinding:
    """Explicit proof that a HA registry reference belongs to a current entity."""

    registry_ref: str
    entity_id: str
    source: str


@dataclass(frozen=True)
class OperationalAudit:
    current_automations: int
    current_active: int
    current_disabled: int
    documented: int
    matched_active: int
    matched_disabled: int
    documented_only: int
    current_without_document: int
    parsed_active: int
    parse_errors: tuple[dict[str, str], ...]
    unresolved_registry_refs: tuple[str, ...]
    unresolved_device_refs: tuple[str, ...]
    unresolved_area_refs: tuple[str, ...]
    active_without_trigger_edge: tuple[str, ...]
    active_without_effect_edge: tuple[str, ...]
    predicate_counts: dict[str, int]

@dataclass(frozen=True)
class ScriptCatalogEntry:
    script_id: str
    file_name: str
    services: tuple[str, ...]
    domain: str | None
    role: str | None
    status: str | None
    version: str | None
    automation_links: str | None
    entities: tuple[str, ...]
    last_modified: str | None
    risks: str | None
    comments: str | None



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


def _expanded_identity_tokens(value: object) -> set[str]:
    base = set(_tokens(value))
    expanded = set(base)
    for token in base:
        expanded.update(_TOKEN_EQUIVALENTS.get(token, set()))
    return expanded


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
        match = re.search(r"(?:^|\\n)\\s*alias:\\s*([^\\n]+)", production)
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


def business_functions_from_rows(
    header: list[object],
    rows: list[list[object]],
) -> list[BusinessFunctionDoc]:
    names = [str(x or "").strip() for x in header]
    required = {
        "Fonction métier",
        "Entité Home Assistant actuelle",
        "Type",
        "Source officielle",
        "État attendu / règle",
    }
    if not required.issubset(set(names)):
        missing = sorted(required - set(names))
        raise ValueError("business_reference_missing_columns:" + ",".join(missing))
    out: list[BusinessFunctionDoc] = []
    for raw in rows:
        padded = list(raw) + [""] * (len(names) - len(raw))
        row = dict(zip(names, padded))
        function = str(row["Fonction métier"] or "").strip()
        if not function:
            continue
        out.append(
            BusinessFunctionDoc(
                function=function,
                reference=str(row["Entité Home Assistant actuelle"] or "").strip(),
                object_type=str(row["Type"] or "").strip() or None,
                rule=str(row["État attendu / règle"] or "").strip() or None,
                source_official=str(row["Source officielle"] or "").strip() or None,
                last_validation=str(row.get("Dernière validation") or "").strip() or None,
            )
        )
    return out


def reconcile_business_functions(
    entities: Iterable[EntityRecord],
    docs: Iterable[BusinessFunctionDoc],
) -> list[ReconciledBusinessFunction]:
    """Keep stable métier meaning while separately qualifying the current binding."""
    entity_list = list(entities)
    by_id = {entity.entity_id: entity for entity in entity_list}
    by_name: dict[str, list[EntityRecord]] = {}
    for entity in entity_list:
        by_name.setdefault(normalize_text(entity.name), []).append(entity)

    out: list[ReconciledBusinessFunction] = []
    for doc in docs:
        ref = doc.reference.strip()
        binding_entity_id: str | None = None
        binding_status = "semantic_only"

        if _ENTITY_ID_RE.match(ref):
            if ref in by_id:
                binding_entity_id = ref
                binding_status = "current_entity"
            else:
                binding_status = "stale_entity"
        else:
            alias_match = re.match(r"^alias\s+ha\s*:\s*(.+)$", normalize_text(ref))
            if alias_match:
                alias = alias_match.group(1).strip()
                hits = by_name.get(alias, [])
                if len(hits) == 1:
                    binding_entity_id = hits[0].entity_id
                    binding_status = "current_alias"
                elif len(hits) > 1:
                    binding_status = "ambiguous_alias"
                else:
                    binding_status = "stale_alias"

        out.append(
            ReconciledBusinessFunction(
                function=doc.function,
                reference=doc.reference,
                object_type=doc.object_type,
                rule=doc.rule,
                source_official=doc.source_official,
                last_validation=doc.last_validation,
                binding_entity_id=binding_entity_id,
                binding_status=binding_status,
            )
        )
    return out


def business_context_for_entity(
    entity_id: str,
    business_functions: Iterable[ReconciledBusinessFunction],
) -> list[ReconciledBusinessFunction]:
    """Return métier rows currently bound to this entity; stale bindings stay out."""
    return [
        item
        for item in business_functions
        if item.binding_entity_id == entity_id
        and item.binding_status in {"current_entity", "current_alias"}
    ]


def script_catalog_from_rows(
    header: list[object],
    rows: list[list[object]],
) -> list[ScriptCatalogEntry]:
    """Parse the Scripts Pyscript catalogue as documentary enrichment only."""
    names = [str(x or "").strip() for x in header]
    required = {
        "ID", "Nom du fichier", "Service HA exposé", "Domaine", "Rôle",
        "Statut", "Version actuelle", "Automatisation liée",
        "Entités HA utilisées", "Dernière modification",
        "Risques / points sensibles", "Commentaires",
    }
    if not required.issubset(set(names)):
        missing = sorted(required - set(names))
        raise ValueError("script_catalog_missing_columns:" + ",".join(missing))

    out: list[ScriptCatalogEntry] = []
    for raw in rows:
        padded = list(raw) + [""] * (len(names) - len(raw))
        row = dict(zip(names, padded))
        script_id = str(row["ID"] or "").strip()
        file_name = str(row["Nom du fichier"] or "").strip()
        if not script_id and not file_name:
            continue

        services = tuple(
            item.strip()
            for item in str(row["Service HA exposé"] or "").split(";")
            if item.strip() and "." in item
        )
        entities = tuple(
            item.strip()
            for item in str(row["Entités HA utilisées"] or "").split(";")
            if item.strip() and "." in item
        )
        out.append(
            ScriptCatalogEntry(
                script_id=script_id,
                file_name=file_name,
                services=services,
                domain=str(row["Domaine"] or "").strip() or None,
                role=str(row["Rôle"] or "").strip() or None,
                status=str(row["Statut"] or "").strip() or None,
                version=str(row["Version actuelle"] or "").strip() or None,
                automation_links=str(row["Automatisation liée"] or "").strip() or None,
                entities=entities,
                last_modified=str(row["Dernière modification"] or "").strip() or None,
                risks=str(row["Risques / points sensibles"] or "").strip() or None,
                comments=str(row["Commentaires"] or "").strip() or None,
            )
        )
    return out


def script_context_for_services(
    services: Iterable[str],
    catalog: Iterable[ScriptCatalogEntry],
) -> list[dict[str, Any]]:
    """Return exact script metadata for services already proved by Production.

    The catalogue never creates a service call. Similar names are deliberately
    ignored; only exact service identity can enrich an operational chain.
    """
    requested = {
        service.split(":", 1)[1] if service.startswith("service:") else service
        for service in services
    }
    out: list[dict[str, Any]] = []
    for item in catalog:
        matched = sorted(set(item.services) & requested)
        if not matched:
            continue
        out.append({
            "script_id": item.script_id,
            "file_name": item.file_name,
            "services": matched,
            "domain": item.domain,
            "role": item.role,
            "status": item.status,
            "version": item.version,
            "automation_links": item.automation_links,
            "entities": list(item.entities),
            "last_modified": item.last_modified,
            "risks": item.risks,
            "comments": item.comments,
        })
    out.sort(key=lambda item: (item["script_id"], item["file_name"]))
    return out


def object_dependencies_from_rows(
    header: list[object],
    rows: list[list[object]],
) -> list[ObjectDependencyDoc]:
    names = [str(x or "").strip() for x in header]
    required = {"Objet", "Automatisation liée"}
    if not required.issubset(set(names)):
        missing = sorted(required - set(names))
        raise ValueError("object_dependency_missing_columns:" + ",".join(missing))
    out: list[ObjectDependencyDoc] = []
    for raw in rows:
        padded = list(raw) + [""] * (len(names) - len(raw))
        row = dict(zip(names, padded))
        object_ref = str(row["Objet"] or "").strip()
        automation_name = str(row["Automatisation liée"] or "").strip()
        if not object_ref or not automation_name:
            continue
        out.append(
            ObjectDependencyDoc(
                object_ref=object_ref,
                automation_name=automation_name,
                domain=str(row.get("Domaine HA") or "").strip() or None,
                name=str(row.get("Nom HA") or "").strip() or None,
                observed_state=str(row.get("État HA") or "").strip() or None,
            )
        )
    return out


def dependency_edges(
    entities: Iterable[EntityRecord],
    reconciliation: ReconciliationResult,
    dependencies: Iterable[ObjectDependencyDoc],
    *,
    include_disabled: bool = False,
) -> list[GraphEdge]:
    """Build low-authority USES edges; dependencies never imply an action."""
    current_ids = {entity.entity_id for entity in entities}
    by_name = {
        normalize_text(item.name): item
        for item in reconciliation.matched
        if include_disabled or item.state == "on"
    }
    edges: list[GraphEdge] = []
    for dep in dependencies:
        automation = by_name.get(normalize_text(dep.automation_name))
        if not automation:
            continue
        ref = dep.object_ref.strip()
        if ref in current_ids:
            object_node = ref
            binding = "current_entity"
        elif ref.startswith("device_id:"):
            object_node = "device_ref:" + ref.split(":", 1)[1].strip()
            binding = "device_ref"
        elif ref.startswith("entity_id:"):
            candidate = ref.split(":", 1)[1].strip()
            object_node = candidate if candidate in current_ids else _node_for_entity_ref(candidate)
            binding = "current_entity" if candidate in current_ids else "unresolved_entity"
        else:
            object_node = f"document_ref:{ref}"
            binding = "document_only"
        edges.append(
            GraphEdge(
                automation.entity_id,
                "USES",
                object_node,
                SourceKind.OBJECTS_HA,
                _detail(
                    binding=binding,
                    domain=dep.domain,
                    name=dep.name,
                    observed_state=dep.observed_state,
                ),
            )
        )
    return list(dict.fromkeys(edges))


def _r8_status_is_current(value: object) -> bool:
    folded = normalize_text(value)
    if not folded:
        return False
    veto = (
        "historique", "obsolet", "legacy", "remplace", "retire", "archive",
        "a observer", "observation", "prevision", "hypothese",
        "requalifier", "ko",
    )
    if any(word in folded for word in veto):
        return False
    positive = (
        "valide", "production", "operationnel", "actif", "permanent",
        "obligatoire", "fonctionnel", "installe",
    )
    return any(word in folded for word in positive)


def r8_relations_from_rows(
    header: list[object],
    rows: list[list[object]],
) -> list[R8RelationDoc]:
    names = [str(x or "").strip() for x in header]
    required = {
        "Relation_ID", "Chaîne_fonctionnelle", "Source_type", "Source_ID",
        "Relation", "Cible_type", "Cible_ID", "Rôle_ou_effet",
        "Source_de_preuve", "Confiance", "Statut", "Dernière_vérification",
    }
    if not required.issubset(set(names)):
        missing = sorted(required - set(names))
        raise ValueError("r8_missing_columns:" + ",".join(missing))
    out: list[R8RelationDoc] = []
    for raw in rows:
        padded = list(raw) + [""] * (len(names) - len(raw))
        row = dict(zip(names, padded))
        relation_id = str(row["Relation_ID"] or "").strip()
        if not relation_id or not _r8_status_is_current(row["Statut"]):
            continue
        out.append(
            R8RelationDoc(
                relation_id=relation_id,
                chain=str(row["Chaîne_fonctionnelle"] or "").strip(),
                source_type=str(row["Source_type"] or "").strip(),
                source_id=str(row["Source_ID"] or "").strip(),
                relation=str(row["Relation"] or "").strip(),
                target_type=str(row["Cible_type"] or "").strip(),
                target_id=str(row["Cible_ID"] or "").strip(),
                role=str(row["Rôle_ou_effet"] or "").strip() or None,
                evidence=str(row["Source_de_preuve"] or "").strip() or None,
                confidence=str(row["Confiance"] or "").strip() or None,
                status=str(row["Statut"] or "").strip(),
                last_verification=str(row["Dernière_vérification"] or "").strip() or None,
            )
        )
    return out


def _resolve_document_node(
    value: str,
    entities: Iterable[EntityRecord],
    reconciliation: ReconciliationResult,
) -> tuple[str, str]:
    ref = value.strip()
    current_ids = {entity.entity_id for entity in entities}
    if ref in current_ids:
        return ref, "current_entity"
    by_automation_name = {
        normalize_text(item.name): item.entity_id
        for item in reconciliation.matched
    }
    automation_id = by_automation_name.get(normalize_text(ref))
    if automation_id:
        return automation_id, "current_automation"
    if _ENTITY_ID_RE.match(ref):
        return f"stale_or_external_entity:{ref}", "stale_or_external_entity"
    return f"document_ref:{ref}", "document_only"


def r8_edges(
    entities: Iterable[EntityRecord],
    reconciliation: ReconciliationResult,
    relations: Iterable[R8RelationDoc],
) -> list[GraphEdge]:
    """Preserve R8 as corroborating/documentary relations, never as ACTS_ON."""
    entity_list = list(entities)
    edges: list[GraphEdge] = []
    for relation in relations:
        source, source_binding = _resolve_document_node(
            relation.source_id, entity_list, reconciliation
        )
        target, target_binding = _resolve_document_node(
            relation.target_id, entity_list, reconciliation
        )
        predicate = "R8:" + normalize_text(relation.relation).replace(" ", "_")
        edges.append(
            GraphEdge(
                source,
                predicate,
                target,
                SourceKind.R8_RELATION,
                _detail(
                    relation_id=relation.relation_id,
                    chain=relation.chain,
                    role=relation.role,
                    evidence=relation.evidence,
                    confidence=relation.confidence,
                    status=relation.status,
                    last_verification=relation.last_verification,
                    source_binding=source_binding,
                    target_binding=target_binding,
                ),
            )
        )
    return list(dict.fromkeys(edges))


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
    # YAML can parse an all-numeric 32-character registry id as an integer.
    # Preserve it losslessly as a reference instead of silently dropping it.
    if isinstance(value, int) and not isinstance(value, bool):
        return [str(value)]
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


def _device_node(value: object) -> str | None:
    raw = str(value or "").strip()
    return f"device_ref:{raw}" if raw else None


def _area_node(value: object) -> str | None:
    raw = str(value or "").strip()
    return f"area_ref:{raw}" if raw else None


def _detail(**values: Any) -> str:
    compact = {key: value for key, value in values.items() if value not in (None, "", [], {})}
    return json.dumps(compact, ensure_ascii=False, sort_keys=True)


def _template_refs(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    refs = set(_TEMPLATE_ENTITY_RE.findall(value))
    refs.update(
        f"{domain}.{object_id}"
        for domain, object_id in _TEMPLATE_DOTTED_ENTITY_RE.findall(value)
    )
    return refs


def _template_excerpt(value: Any, limit: int = 600) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.strip().split())
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _emit_template_guard(
    value: Any,
    automation_id: str,
    edges: list[GraphEdge],
    *,
    predicate: str,
    branch_path: str,
    expected: bool | None,
) -> None:
    excerpt = _template_excerpt(value)
    if excerpt is None:
        return
    edges.append(
        GraphEdge(
            "template_condition",
            predicate,
            automation_id,
            SourceKind.AUTOMATION_PRODUCTION,
            _detail(
                condition="template",
                expression=excerpt,
                branch_path=branch_path,
                expected=expected,
            ),
        )
    )
    for ref in _template_refs(value):
        edges.append(
            GraphEdge(
                ref,
                predicate,
                automation_id,
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(
                    via="template",
                    expression=excerpt,
                    branch_path=branch_path,
                    expected=expected,
                ),
            )
        )


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

    # Preserve the user-visible intent of climate.set_hvac_mode. An explicit
    # hvac_mode=off is a proved power-off behavior, not merely a generic mode
    # change. This lets action-intent filtering answer "éteint la clim" from
    # Production without weakening identity or proof rules.
    if service == "climate.set_hvac_mode" and isinstance(data, dict):
        hvac_mode = normalize_text(data.get("hvac_mode"))
        if hvac_mode == "off":
            return "turn_off"
        if hvac_mode in {"heat", "cool", "heat_cool", "auto", "dry", "fan_only"}:
            return "turn_on"

    method = service.rsplit(".", 1)[-1]
    generic = {
        "turn_on": "turn_on",
        "turn_off": "turn_off",
        "toggle": "toggle",
        "open_cover": "open",
        "close_cover": "close",
        "stop_cover": "stop",
        "lock": "lock",
        "unlock": "unlock",
        "set_hvac_mode": "set_hvac_mode",
        "set_temperature": "set_temperature",
        "select_option": "select_option",
        "set_value": "set_value",
        "trigger": "trigger",
        "reload": "reload",
    }
    return generic.get(method)


def _walk_trigger(
    node: Any,
    automation_id: str,
    edges: list[GraphEdge],
    *,
    predicate: str = "TRIGGERS",
    branch_path: str = "root",
    step_index: int | None = None,
) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_trigger(
                item, automation_id, edges, predicate=predicate,
                branch_path=branch_path, step_index=step_index,
            )
        return
    if not isinstance(node, dict):
        return
    if node.get("enabled") is False:
        return

    detail = _detail(
        trigger=node.get("trigger") or node.get("platform"),
        from_state=node.get("from"),
        to_state=node.get("to"),
        above=node.get("above"),
        below=node.get("below"),
        duration=node.get("for"),
        trigger_id=node.get("id"),
        branch_path=branch_path,
        step_index=step_index,
    )
    entity_refs = _entity_refs(node.get("entity_id"))
    for ref in entity_refs:
        edges.append(
            GraphEdge(
                _node_for_entity_ref(ref), predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION, detail,
            )
        )
    device_node = _device_node(node.get("device_id"))
    if device_node:
        edges.append(
            GraphEdge(
                device_node, predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(
                    via="device",
                    trigger=node.get("trigger") or node.get("platform"),
                    branch_path=branch_path,
                    step_index=step_index,
                ),
            )
        )

    trigger_kind = node.get("trigger") or node.get("platform")
    if trigger_kind == "sun":
        edges.append(
            GraphEdge(
                "sun.sun", predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(
                    event=node.get("event"), offset=node.get("offset"),
                    branch_path=branch_path, step_index=step_index,
                ),
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
                _detail(
                    hours=node.get("hours"), minutes=node.get("minutes"),
                    seconds=node.get("seconds"), branch_path=branch_path,
                    step_index=step_index,
                ),
            )
        )
    elif trigger_kind == "event" and node.get("event_type"):
        edges.append(
            GraphEdge(
                f"event:{node.get('event_type')}", predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(
                    event_type=node.get("event_type"),
                    event_data=node.get("event_data"),
                    branch_path=branch_path, step_index=step_index,
                ),
            )
        )
    elif trigger_kind == "webhook" and node.get("webhook_id"):
        edges.append(
            GraphEdge(
                f"webhook:{node.get('webhook_id')}", predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(via="webhook", branch_path=branch_path, step_index=step_index),
            )
        )
    elif trigger_kind == "homeassistant" and node.get("event"):
        edges.append(
            GraphEdge(
                f"homeassistant:{node.get('event')}", predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(via="homeassistant", branch_path=branch_path, step_index=step_index),
            )
        )

    for value in node.values():
        for ref in _template_refs(value):
            edges.append(
                GraphEdge(
                    ref, predicate, automation_id,
                    SourceKind.AUTOMATION_PRODUCTION,
                    _detail(via="template", branch_path=branch_path, step_index=step_index),
                )
            )


def _walk_condition(
    node: Any,
    automation_id: str,
    edges: list[GraphEdge],
    *,
    predicate: str = "GUARDS",
    branch_path: str = "root",
    expected: bool | None = None,
) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_condition(
                item, automation_id, edges, predicate=predicate,
                branch_path=branch_path, expected=expected,
            )
        return
    if isinstance(node, str):
        _emit_template_guard(
            node, automation_id, edges, predicate=predicate,
            branch_path=branch_path, expected=expected,
        )
        return
    if not isinstance(node, dict):
        return
    if node.get("enabled") is False:
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
        branch_path=branch_path,
        expected=expected,
    )
    for ref in _entity_refs(node.get("entity_id")):
        edges.append(
            GraphEdge(
                _node_for_entity_ref(ref), predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION, detail,
            )
        )
    device_node = _device_node(node.get("device_id"))
    if device_node:
        edges.append(
            GraphEdge(
                device_node, predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(
                    via="device", condition=condition, branch_path=branch_path,
                    expected=expected,
                ),
            )
        )
    if condition == "sun":
        edges.append(
            GraphEdge(
                "sun.sun", predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(
                    after=node.get("after"), before=node.get("before"),
                    after_offset=node.get("after_offset"),
                    before_offset=node.get("before_offset"),
                    branch_path=branch_path, expected=expected,
                ),
            )
        )
    elif condition == "time":
        edges.append(
            GraphEdge(
                "time_window", predicate, automation_id,
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(
                    condition="time",
                    after=node.get("after"),
                    before=node.get("before"),
                    weekday=node.get("weekday"),
                    branch_path=branch_path,
                    expected=expected,
                ),
            )
        )
    elif condition == "trigger" and node.get("id") is not None:
        for trigger_id in _entity_refs(node.get("id")):
            edges.append(
                GraphEdge(
                    f"trigger_id:{trigger_id}", predicate, automation_id,
                    SourceKind.AUTOMATION_PRODUCTION,
                    _detail(
                        condition="trigger", trigger_id=trigger_id,
                        branch_path=branch_path, expected=expected,
                    ),
                )
            )

    if condition == "template":
        _emit_template_guard(
            node.get("value_template"),
            automation_id,
            edges,
            predicate=predicate,
            branch_path=branch_path,
            expected=expected,
        )
    else:
        for value in node.values():
            for ref in _template_refs(value):
                edges.append(
                    GraphEdge(
                        ref, predicate, automation_id,
                        SourceKind.AUTOMATION_PRODUCTION,
                        _detail(
                            via="template", branch_path=branch_path, expected=expected,
                        ),
                    )
                )

    for key in ("conditions", "and", "or", "not"):
        if key in node:
            nested_expected = expected
            if key == "not" and expected is not None:
                nested_expected = not expected
            _walk_condition(
                node[key], automation_id, edges, predicate=predicate,
                branch_path=branch_path, expected=nested_expected,
            )


def _walk_actions(
    node: Any,
    automation_id: str,
    edges: list[GraphEdge],
    *,
    branch_path: str = "root",
    step_index: int | None = None,
) -> None:
    if isinstance(node, list):
        for index, item in enumerate(node):
            _walk_actions(
                item, automation_id, edges,
                branch_path=branch_path, step_index=index,
            )
            if (
                isinstance(item, dict)
                and item.get("enabled") is not False
                and "stop" in item
            ):
                break
        return
    if not isinstance(node, dict):
        return
    if node.get("enabled") is False:
        return

    if "stop" in node:
        edges.append(
            GraphEdge(
                automation_id,
                "TERMINATES",
                "stop",
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(
                    message=node.get("stop"),
                    error=node.get("error"),
                    response_variable=node.get("response_variable"),
                    branch_path=branch_path,
                    step_index=step_index,
                ),
            )
        )
        return

    if "delay" in node:
        edges.append(
            GraphEdge(
                automation_id,
                "BARRIER",
                f"delay:{json.dumps(node['delay'], sort_keys=True)}",
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(branch_path=branch_path, step_index=step_index, kind="delay"),
            )
        )

    if "wait_for_trigger" in node:
        _walk_trigger(
            node["wait_for_trigger"], automation_id, edges,
            predicate="WAITS_FOR", branch_path=branch_path, step_index=step_index,
        )
        if node.get("timeout") is not None:
            edges.append(
                GraphEdge(
                    automation_id,
                    "BARRIER",
                    "wait_for_trigger_timeout",
                    SourceKind.AUTOMATION_PRODUCTION,
                    _detail(
                        kind="wait_for_trigger",
                        timeout=node.get("timeout"),
                        continue_on_timeout=node.get("continue_on_timeout"),
                        branch_path=branch_path,
                        step_index=step_index,
                    ),
                )
            )
    if "wait_template" in node:
        template = node.get("wait_template")
        refs = _template_refs(template)
        for ref in refs:
            edges.append(
                GraphEdge(
                    ref, "WAITS_FOR", automation_id,
                    SourceKind.AUTOMATION_PRODUCTION,
                    _detail(
                        via="wait_template", branch_path=branch_path,
                        step_index=step_index,
                    ),
                )
            )
        edges.append(
            GraphEdge(
                automation_id, "BARRIER", "wait_template",
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(
                    template=template,
                    timeout=node.get("timeout"),
                    continue_on_timeout=node.get("continue_on_timeout"),
                    branch_path=branch_path,
                    step_index=step_index,
                    kind="wait_template",
                ),
            )
        )

    service = node.get("action") or node.get("service")
    if isinstance(service, str) and "." in service:
        target = node.get("target")
        data = node.get("data")
        target_refs: list[str] = []
        device_refs: list[str] = []
        area_refs: list[str] = []
        if isinstance(target, dict):
            target_refs.extend(_entity_refs(target.get("entity_id")))
            device_refs.extend(_entity_refs(target.get("device_id")))
            area_refs.extend(_entity_refs(target.get("area_id")))
        target_refs.extend(_entity_refs(node.get("entity_id")))
        if isinstance(data, dict):
            target_refs.extend(_entity_refs(data.get("entity_id")))

        if service == "automation.trigger":
            predicate = "CALLS_AUTOMATION"
        elif service.startswith("script.") and service not in {"script.turn_on", "script.turn_off"}:
            predicate = "CALLS_SCRIPT"
        elif service.startswith("pyscript."):
            predicate = "CALLS_PYSCRIPT"
        else:
            predicate = "ACTS_ON"

        detail = _detail(
            service=service,
            effect=_effect_for_service(service, data),
            data=data,
            branch_path=branch_path,
            step_index=step_index,
        )
        emitted = False
        if predicate in {"CALLS_SCRIPT", "CALLS_PYSCRIPT"} and not target_refs:
            target_node = service if predicate == "CALLS_SCRIPT" else f"service:{service}"
            edges.append(
                GraphEdge(
                    automation_id, predicate, target_node,
                    SourceKind.AUTOMATION_PRODUCTION, detail,
                )
            )
            emitted = True

        for ref in dict.fromkeys(target_refs):
            edges.append(
                GraphEdge(
                    automation_id,
                    predicate,
                    _node_for_entity_ref(ref),
                    SourceKind.AUTOMATION_PRODUCTION,
                    detail,
                )
            )
            emitted = True
        for ref in dict.fromkeys(device_refs):
            device_node = _device_node(ref)
            if device_node:
                edges.append(
                    GraphEdge(
                        automation_id, predicate, device_node,
                        SourceKind.AUTOMATION_PRODUCTION,
                        _detail(
                            service=service,
                            effect=_effect_for_service(service, data),
                            via="device_target", branch_path=branch_path,
                            step_index=step_index,
                        ),
                    )
                )
                emitted = True
        for ref in dict.fromkeys(area_refs):
            area_node = _area_node(ref)
            if area_node:
                edges.append(
                    GraphEdge(
                        automation_id, predicate, area_node,
                        SourceKind.AUTOMATION_PRODUCTION,
                        _detail(
                            service=service,
                            effect=_effect_for_service(service, data),
                            via="area_target", branch_path=branch_path,
                            step_index=step_index,
                        ),
                    )
                )
                emitted = True
        if not emitted:
            edges.append(
                GraphEdge(
                    automation_id, "CALLS_SERVICE", f"service:{service}",
                    SourceKind.AUTOMATION_PRODUCTION, detail,
                )
            )

    if (
        isinstance(node.get("type"), str)
        and isinstance(node.get("domain"), str)
        and not (isinstance(service, str) and "." in service)
    ):
        pseudo_service = f"{node['domain']}.{node['type']}"
        refs = _entity_refs(node.get("entity_id"))
        if refs:
            for ref in refs:
                edges.append(
                    GraphEdge(
                        automation_id, "ACTS_ON", _node_for_entity_ref(ref),
                        SourceKind.AUTOMATION_PRODUCTION,
                        _detail(
                            service=pseudo_service,
                            effect=node.get("type"),
                            device_id=node.get("device_id"),
                            via="device_action", branch_path=branch_path,
                            step_index=step_index,
                        ),
                    )
                )
        else:
            device_node = _device_node(node.get("device_id"))
            if device_node:
                edges.append(
                    GraphEdge(
                        automation_id, "ACTS_ON", device_node,
                        SourceKind.AUTOMATION_PRODUCTION,
                        _detail(
                            service=pseudo_service,
                            effect=node.get("type"),
                            via="device_action_without_entity",
                            branch_path=branch_path, step_index=step_index,
                        ),
                    )
                )

    if "condition" in node and not (isinstance(service, str) and "." in service):
        _walk_condition(
            node, automation_id, edges, predicate="LOCAL_GUARD",
            branch_path=branch_path,
        )

    location = step_index if step_index is not None else "x"
    if "if" in node:
        then_path = f"{branch_path}/if@{location}:then"
        else_path = f"{branch_path}/if@{location}:else"
        _walk_condition(
            node.get("if"), automation_id, edges, predicate="LOCAL_GUARD",
            branch_path=then_path, expected=True,
        )
        _walk_actions(node.get("then"), automation_id, edges, branch_path=then_path)
        if "else" in node:
            _walk_condition(
                node.get("if"), automation_id, edges, predicate="LOCAL_GUARD",
                branch_path=else_path, expected=False,
            )
            _walk_actions(node.get("else"), automation_id, edges, branch_path=else_path)

    if "choose" in node and isinstance(node["choose"], list):
        for choice_index, choice in enumerate(node["choose"]):
            if not isinstance(choice, dict):
                continue
            choice_path = f"{branch_path}/choose@{location}:{choice_index}"
            _walk_condition(
                choice.get("conditions"), automation_id, edges,
                predicate="LOCAL_GUARD", branch_path=choice_path, expected=True,
            )
            _walk_actions(
                choice.get("sequence"), automation_id, edges,
                branch_path=choice_path,
            )
        if "default" in node:
            default_path = f"{branch_path}/choose@{location}:default"
            _walk_actions(node["default"], automation_id, edges, branch_path=default_path)
    elif "default" in node:
        _walk_actions(node["default"], automation_id, edges, branch_path=branch_path)

    if "sequence" in node:
        _walk_actions(node["sequence"], automation_id, edges, branch_path=branch_path)
    if "parallel" in node:
        parallel_path = f"{branch_path}/parallel@{location}"
        _walk_actions(node["parallel"], automation_id, edges, branch_path=parallel_path)
    if "repeat" in node:
        value = node["repeat"]
        repeat_path = f"{branch_path}/repeat@{location}"
        if isinstance(value, dict):
            _walk_condition(
                value.get("while"), automation_id, edges,
                predicate="LOCAL_GUARD", branch_path=repeat_path, expected=True,
            )
            _walk_condition(
                value.get("until"), automation_id, edges,
                predicate="LOCAL_GUARD", branch_path=repeat_path, expected=True,
            )
            _walk_actions(
                value.get("sequence"), automation_id, edges,
                branch_path=repeat_path,
            )
        else:
            _walk_actions(value, automation_id, edges, branch_path=repeat_path)


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


def registry_bindings_from_entries(
    entries: Iterable[dict[str, Any]],
    entities: Iterable[EntityRecord],
    *,
    source: str = "ha_entity_registry_readonly",
) -> list[RegistryBinding]:
    """Build exact opaque-id bindings from a read-only HA entity registry dump.

    Home Assistant full entity registry rows expose both the registry entry id
    and the public entity_id. Only exact current identities are accepted.
    """
    current_ids = {entity.entity_id for entity in entities}
    out: list[RegistryBinding] = []
    seen: dict[str, str] = {}
    for entry in entries:
        raw = str(entry.get("id") or "").strip()
        entity_id = str(entry.get("entity_id") or "").strip()
        if not raw or not entity_id:
            continue
        if not _OPAQUE_ENTITY_REF_RE.fullmatch(raw):
            continue
        if entity_id not in current_ids:
            continue
        previous = seen.get(raw)
        if previous and previous != entity_id:
            raise ValueError(f"conflicting_entity_registry_id:{raw}")
        seen[raw] = entity_id
        out.append(RegistryBinding(raw, entity_id, source))
    out.sort(key=lambda item: (item.registry_ref, item.entity_id))
    return out


def resolve_registry_edges(
    edges: Iterable[GraphEdge],
    entities: Iterable[EntityRecord],
    bindings: Iterable[RegistryBinding],
) -> list[GraphEdge]:
    """Resolve opaque entity-registry refs only from explicit trusted bindings.

    The resolver is fail-closed: a binding must point to a current HA entity and
    the same registry reference may not map to two different entities.
    """
    current_ids = {entity.entity_id for entity in entities}
    mapping: dict[str, RegistryBinding] = {}

    for binding in bindings:
        raw = binding.registry_ref.strip()
        if raw.startswith("registry_ref:"):
            raw = raw.split(":", 1)[1]
        if not _OPAQUE_ENTITY_REF_RE.fullmatch(raw):
            raise ValueError(f"invalid_registry_ref:{binding.registry_ref}")
        if binding.entity_id not in current_ids:
            raise ValueError(f"registry_binding_not_current:{binding.entity_id}")
        existing = mapping.get(raw)
        if existing and existing.entity_id != binding.entity_id:
            raise ValueError(f"conflicting_registry_binding:{raw}")
        mapping[raw] = RegistryBinding(raw, binding.entity_id, binding.source)

    out: list[GraphEdge] = []
    for edge in edges:
        subject = edge.subject
        obj = edge.object
        detail = _edge_detail(edge)

        if subject.startswith("registry_ref:"):
            raw = subject.split(":", 1)[1]
            binding = mapping.get(raw)
            if binding:
                subject = binding.entity_id
                detail = {
                    **detail,
                    "resolved_registry_ref": raw,
                    "identity_resolution_source": binding.source,
                }

        if obj.startswith("registry_ref:"):
            raw = obj.split(":", 1)[1]
            binding = mapping.get(raw)
            if binding:
                obj = binding.entity_id
                detail = {
                    **detail,
                    "resolved_registry_ref": raw,
                    "identity_resolution_source": binding.source,
                }

        out.append(
            GraphEdge(
                subject=subject,
                predicate=edge.predicate,
                object=obj,
                source=edge.source,
                detail=_detail(**detail) if detail else edge.detail,
            )
        )
    return list(dict.fromkeys(out))


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



def extend_graph_with_operational_scripts(
    edges: Iterable[GraphEdge],
    scripts: Iterable[OperationalScript],
) -> list[GraphEdge]:
    """Expand proved script calls; documentary script catalogs are never accepted here."""
    out = list(edges)
    scripts_by_service = {item.service: item for item in scripts}
    calls = [edge for edge in out if edge.predicate in {"CALLS_SCRIPT", "CALLS_PYSCRIPT"}]
    for call in calls:
        service = call.object.removeprefix("service:")
        script = scripts_by_service.get(service)
        if not script:
            continue
        configs = parse_automation_yaml(script.production)
        script_node = f"operational_script:{service}"
        out.append(
            GraphEdge(
                call.subject,
                "CALLS_PROVED_SCRIPT",
                script_node,
                SourceKind.AUTOMATION_PRODUCTION,
                _detail(service=service, proof_source=script.source),
            )
        )
        for config in configs:
            actions = config.get("actions", config.get("action")) if isinstance(config, dict) else None
            script_edges: list[GraphEdge] = []
            _walk_actions(actions, script_node, script_edges)
            for edge in script_edges:
                detail = _edge_detail(edge)
                out.append(
                    GraphEdge(
                        edge.subject,
                        edge.predicate,
                        edge.object,
                        edge.source,
                        _detail(**detail, proof_source=script.source, called_service=service),
                    )
                )
    return list(dict.fromkeys(out))


def audit_operational_model(
    entities: Iterable[EntityRecord],
    docs: Iterable[AutomationDoc],
) -> OperationalAudit:
    """Audit the whole current automation corpus without inventing missing links.

    Unlike the query path, this function is intentionally exhaustive. Each
    reconciled active Production is parsed independently so one malformed row
    cannot hide the state of the remaining corpus.
    """
    entity_list = list(entities)
    doc_list = list(docs)
    reconciliation = reconcile_automations(entity_list, doc_list)
    current = [item for item in entity_list if item.domain == "automation"]
    matched_active = [item for item in reconciliation.matched if item.state == "on"]
    matched_disabled = [item for item in reconciliation.matched if item.state != "on"]

    edges: list[GraphEdge] = []
    parse_errors: list[dict[str, str]] = []
    parsed_ids: set[str] = set()
    for automation in matched_active:
        try:
            extracted = extract_automation_edges(automation)
        except Exception as exc:
            parse_errors.append({
                "automation_entity_id": automation.entity_id,
                "automation_name": automation.name,
                "error": f"{type(exc).__name__}:{exc}",
            })
            continue
        parsed_ids.add(automation.entity_id)
        edges.extend(extracted)

    predicate_counts: dict[str, int] = {}
    for edge in edges:
        predicate_counts[edge.predicate] = predicate_counts.get(edge.predicate, 0) + 1

    unresolved_registry = sorted({
        node
        for edge in edges
        for node in (edge.subject, edge.object)
        if node.startswith("registry_ref:")
    })
    unresolved_device = sorted({
        node
        for edge in edges
        for node in (edge.subject, edge.object)
        if node.startswith("device_ref:")
    })
    unresolved_area = sorted({
        node
        for edge in edges
        for node in (edge.subject, edge.object)
        if node.startswith("area_ref:")
    })

    incoming_trigger_ids = {
        edge.object for edge in edges if edge.predicate == "TRIGGERS"
    }
    effect_ids = {
        edge.subject
        for edge in edges
        if edge.predicate in {
            "ACTS_ON", "CALLS_AUTOMATION", "CALLS_SCRIPT", "CALLS_PYSCRIPT",
            "CALLS_SERVICE", "TERMINATES"
        }
    }
    active_without_trigger = tuple(sorted(
        automation.entity_id
        for automation in matched_active
        if automation.entity_id in parsed_ids
        and automation.entity_id not in incoming_trigger_ids
    ))
    active_without_effect = tuple(sorted(
        automation.entity_id
        for automation in matched_active
        if automation.entity_id in parsed_ids
        and automation.entity_id not in effect_ids
    ))

    return OperationalAudit(
        current_automations=len(current),
        current_active=sum(1 for item in current if item.state == "on"),
        current_disabled=sum(1 for item in current if item.state != "on"),
        documented=len(doc_list),
        matched_active=len(matched_active),
        matched_disabled=len(matched_disabled),
        documented_only=len(reconciliation.documented_only),
        current_without_document=len(reconciliation.current_without_document),
        parsed_active=len(parsed_ids),
        parse_errors=tuple(parse_errors),
        unresolved_registry_refs=tuple(unresolved_registry),
        unresolved_device_refs=tuple(unresolved_device),
        unresolved_area_refs=tuple(unresolved_area),
        active_without_trigger_edge=active_without_trigger,
        active_without_effect_edge=active_without_effect,
        predicate_counts=dict(sorted(predicate_counts.items())),
    )


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
        for token in _expanded_identity_tokens(query)
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
    if {"prise", "chargeur"} & qtokens or re.search(
        r"\b(?:re)?charg\w*\b", normalize_text(query)
    ):
        hints.add("switch")
    if {"serrure"} & qtokens or re.search(r"\b(?:de)?verrouill\w*\b", normalize_text(query)):
        hints.add("lock")

    scored: list[tuple[EntityRecord, int]] = []
    for entity in entities:
        name_norm = normalize_text(entity.name)
        entity_norm = normalize_text(entity.entity_id)
        name_tokens = _expanded_identity_tokens(entity.name)
        score = 0
        if qnorm == name_norm or qnorm == entity_norm:
            score = 140
        elif name_norm and name_norm in qnorm:
            # A generic one-token object name (for example "Tineco") must not
            # beat a more specific entity such as "Tineco Battery" merely
            # because the short name is a substring of the question.
            if len(name_tokens) == 1 and len(qtokens) > 1:
                overlap = len(qtokens & name_tokens)
                score = int(60 * overlap / max(len(qtokens), 1))
            else:
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



def resolve_automations(
    query: str,
    reconciliation: ReconciliationResult,
    *,
    limit: int = 5,
) -> list[tuple[ReconciledAutomation, int]]:
    """Resolve a natural automation name against reconciled current automations."""
    qnorm = normalize_text(query)
    qtokens = _object_tokens(query)
    if not qtokens:
        qtokens = {token for token in _tokens(query) if token not in _STOPWORDS}

    scored: list[tuple[ReconciledAutomation, int]] = []
    for automation in reconciliation.matched:
        if automation.state != "on":
            continue
        name_norm = normalize_text(automation.name)
        name_tokens = set(_tokens(automation.name))
        score = 0
        if qnorm == name_norm or qnorm == normalize_text(automation.entity_id):
            score = 170
        elif name_norm and name_norm in qnorm:
            score = 145 + min(len(name_tokens), 10)
        elif qtokens and qtokens.issubset(name_tokens):
            score = 100 + len(qtokens)
        else:
            overlap = len(qtokens & name_tokens)
            if overlap:
                score = int(55 * overlap / max(len(qtokens), 1))
        if score > 0:
            scored.append((automation, score))
    scored.sort(key=lambda item: (-item[1], item[0].entity_id))
    return scored[: max(1, limit)]


def retrieve_automation_behavior(
    query: str,
    reconciliation: ReconciliationResult,
    edges: Iterable[GraphEdge],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return the complete proved behavior of the best matching active automation."""
    candidates = resolve_automations(query, reconciliation, limit=limit)
    if not candidates:
        return []
    best = candidates[0][1]
    candidates = [item for item in candidates if item[1] == best]
    edge_list = list(edges)
    out: list[dict[str, Any]] = []

    def serialized(edge: GraphEdge) -> dict[str, Any]:
        detail = _edge_detail(edge)
        return {
            "subject": edge.subject,
            "predicate": edge.predicate,
            "object": edge.object,
            "source": edge.source.value,
            "detail": detail,
        }

    for automation, score in candidates:
        incoming = [
            edge for edge in edge_list
            if edge.object == automation.entity_id
            and edge.predicate in {"TRIGGERS", "GUARDS", "WAITS_FOR", "LOCAL_GUARD"}
        ]
        outgoing = [
            edge for edge in edge_list
            if edge.subject == automation.entity_id
            and edge.predicate in {
                "ACTS_ON", "CALLS_AUTOMATION", "CALLS_SCRIPT", "CALLS_PYSCRIPT",
                "CALLS_SERVICE", "BARRIER", "TERMINATES"
            }
        ]
        if not incoming and not outgoing:
            continue

        unresolved = sorted({
            node
            for edge in incoming + outgoing
            for node in (edge.subject, edge.object)
            if node.startswith(("registry_ref:", "device_ref:", "area_ref:", "unresolved_ref:"))
        })

        out.append({
            "score": score,
            "automation_entity_id": automation.entity_id,
            "automation_name": automation.name,
            "match_by": automation.match_by,
            "source_row": automation.source_row,
            "triggers": [serialized(e) for e in incoming if e.predicate == "TRIGGERS"],
            "guards": [serialized(e) for e in incoming if e.predicate == "GUARDS"],
            "local_guards": [serialized(e) for e in incoming if e.predicate == "LOCAL_GUARD"],
            "waits": [serialized(e) for e in incoming if e.predicate == "WAITS_FOR"],
            "actions": [serialized(e) for e in outgoing if e.predicate == "ACTS_ON"],
            "calls": [
                serialized(e) for e in outgoing
                if e.predicate in {
                    "CALLS_AUTOMATION", "CALLS_SCRIPT", "CALLS_PYSCRIPT", "CALLS_SERVICE"
                }
            ],
            "barriers": [serialized(e) for e in outgoing if e.predicate == "BARRIER"],
            "terminates": [serialized(e) for e in outgoing if e.predicate == "TERMINATES"],
            "unresolved_refs": unresolved,
        })
    return out


def retrieve_operational_context(
    query: str,
    entities: Iterable[EntityRecord],
    reconciliation: ReconciliationResult,
    edges: Iterable[GraphEdge],
) -> dict[str, Any]:
    """Route a natural house question to the deterministic operational view.

    Routing is based on identity scores and event-language, never on Drive row
    ordering. This function remains prototype-only and is not wired to the live API.
    """
    entity_list = list(entities)
    edge_list = list(edges)
    normalized = normalize_text(query)

    event_language = bool(
        re.search(r"\b(quand|lorsque)\b", normalized)
        or re.search(r"\bwhat happens when\b", normalized)
    )
    if event_language:
        triggered = retrieve_triggered_chains(
            query, entity_list, reconciliation, edge_list
        )
        if triggered:
            return {"mode": "trigger_to_effect", "results": triggered}

    automation_candidates = resolve_automations(query, reconciliation, limit=3)
    entity_candidates = resolve_entities(query, entity_list, limit=3)
    automation_score = automation_candidates[0][1] if automation_candidates else 0
    entity_score = entity_candidates[0][1] if entity_candidates else 0

    if automation_score >= 120 and automation_score > entity_score:
        behavior = retrieve_automation_behavior(query, reconciliation, edge_list)
        if behavior:
            return {"mode": "automation_behavior", "results": behavior}

    target = retrieve_automation_chains(
        query, entity_list, reconciliation, edge_list
    )
    if target:
        return {"mode": "target_to_automation", "results": target}

    if automation_candidates:
        behavior = retrieve_automation_behavior(query, reconciliation, edge_list)
        if behavior:
            return {"mode": "automation_behavior", "results": behavior}

    return {"mode": "unresolved", "results": []}

def _edge_detail(edge: GraphEdge) -> dict[str, Any]:
    return json.loads(edge.detail) if edge.detail else {}


def _branch_is_ancestor(context_path: str, action_path: str) -> bool:
    return (
        context_path == "root"
        or context_path == action_path
        or action_path.startswith(context_path + "/")
    )


def _branch_entry_step(parent_path: str, child_path: str) -> int | None:
    """Return the step that entered the first child branch below parent_path."""
    if parent_path == child_path or not child_path.startswith(parent_path + "/"):
        return None
    rest = child_path[len(parent_path) + 1 :]
    first = rest.split("/", 1)[0]
    match = re.match(r"(?:choose|if|parallel|repeat)@(\d+)", first)
    return int(match.group(1)) if match else None


def _sequence_edge_precedes_action(
    context_detail: dict[str, Any],
    action_detail: dict[str, Any],
) -> bool:
    context_path = str(context_detail.get("branch_path") or "root")
    action_path = str(action_detail.get("branch_path") or "root")
    if not _branch_is_ancestor(context_path, action_path):
        return False

    context_step = context_detail.get("step_index")
    action_step = action_detail.get("step_index")
    if not isinstance(context_step, int):
        return True

    if context_path == action_path:
        return not isinstance(action_step, int) or context_step < action_step

    entry_step = _branch_entry_step(context_path, action_path)
    return entry_step is None or context_step < entry_step


def _context_for_action(
    automation_id: str,
    action_detail: dict[str, Any],
    edge_list: list[GraphEdge],
) -> list[GraphEdge]:
    """Keep only trigger/guard/wait context that can apply to this action path."""
    action_path = str(action_detail.get("branch_path") or "root")
    selected: list[GraphEdge] = []
    for edge in edge_list:
        if edge.object != automation_id:
            continue
        if edge.predicate not in {"TRIGGERS", "GUARDS", "WAITS_FOR", "LOCAL_GUARD"}:
            continue
        detail = _edge_detail(edge)
        context_path = str(detail.get("branch_path") or "root")
        if not _branch_is_ancestor(context_path, action_path):
            continue
        if edge.predicate == "WAITS_FOR" and not _sequence_edge_precedes_action(detail, action_detail):
            continue
        selected.append(edge)
    return selected


def _barriers_before_action(
    automation_id: str,
    action_detail: dict[str, Any],
    edge_list: list[GraphEdge],
) -> list[GraphEdge]:
    selected: list[GraphEdge] = []
    for edge in edge_list:
        if edge.subject != automation_id or edge.predicate != "BARRIER":
            continue
        detail = _edge_detail(edge)
        if _sequence_edge_precedes_action(detail, action_detail):
            selected.append(edge)
    return selected


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
    # Keep the strongest current-identity candidate for each domain hinted by
    # the user's object phrase. A generic device-family sensor may score
    # lexically above the actual controllable switch (for example "Tineco
    # Online" vs "prise Tineco"). Domain hints are operational evidence and
    # must be allowed to select the best switch/cover/light candidate without
    # opening the door to unrelated lower-scored objects.
    qtokens = _object_tokens(query)
    hinted_domains: set[str] = set()
    if {"lampe", "hotte"} & qtokens:
        hinted_domains.add("light")
    if "volet" in qtokens:
        hinted_domains.add("cover")
    if {"prise", "chargeur"} & qtokens or re.search(
        r"\b(?:re)?charg\w*\b", normalize_text(query)
    ):
        hinted_domains.add("switch")
    if "serrure" in qtokens or re.search(
        r"\b(?:de)?verrouill\w*\b", normalize_text(query)
    ):
        hinted_domains.add("lock")

    if hinted_domains:
        hinted = [candidate for candidate in candidates if candidate[0].domain in hinted_domains]
        if hinted:
            hinted_best = hinted[0][1]
            candidates = [candidate for candidate in hinted if candidate[1] == hinted_best]
        else:
            candidates = [candidate for candidate in candidates if candidate[1] == best_object_score]
    else:
        candidates = [candidate for candidate in candidates if candidate[1] == best_object_score]

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

            context_edges = _context_for_action(
                automation.entity_id, detail, edge_list
            )
            barriers = _barriers_before_action(
                automation.entity_id, detail, edge_list
            )
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
                            "detail": _edge_detail(item),
                        }
                        for item in context_edges
                    ],
                    "barriers": [
                        {
                            "object": item.object,
                            "detail": _edge_detail(item),
                        }
                        for item in barriers
                    ],
                }
            )

    # One result per automation/target. A generic question may legitimately
    # encounter several actions (for example ON then OFF after a wait); keep
    # the full effect set without duplicating the automation in the answer.
    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for result in results:
        key = (
            result["automation_entity_id"],
            result["target_entity_id"],
        )
        previous = dedup.get(key)
        if previous is None:
            result["effects"] = [result["effect"]] if result["effect"] else []
            dedup[key] = result
            continue
        effects = set(previous.get("effects", []))
        if result["effect"]:
            effects.add(result["effect"])
        previous["effects"] = sorted(effects)
        if result["score"] > previous["score"]:
            previous["score"] = result["score"]
            previous["effect"] = result["effect"]
            previous["action_detail"] = result["action_detail"]
    return sorted(
        dedup.values(),
        key=lambda item: (-item["score"], item["automation_entity_id"]),
    )[: max(1, limit)]




def assemble_evidence_context(
    query: str,
    entities: Iterable[EntityRecord],
    reconciliation: ReconciliationResult,
    production_edges: Iterable[GraphEdge],
    *,
    dependency_edges_in: Iterable[GraphEdge] = (),
    r8_edges_in: Iterable[GraphEdge] = (),
    business_functions: Iterable[ReconciledBusinessFunction] = (),
    script_catalog: Iterable[ScriptCatalogEntry] = (),
) -> dict[str, Any]:
    """Assemble Drive evidence without letting lower layers invent behavior.

    The operational core comes only from current identity + reconciled Production.
    Objects HA, R8 and métier are attached afterwards as enrichment/corroboration.
    """
    entity_list = list(entities)
    production = list(production_edges)
    deps = list(dependency_edges_in)
    r8 = list(r8_edges_in)
    business = list(business_functions)
    script_catalog_list = list(script_catalog)

    core = retrieve_operational_context(
        query, entity_list, reconciliation, production
    )

    relevant_nodes: set[str] = set()
    relevant_automations: set[str] = set()
    for item in core.get("results", []):
        for key in (
            "target_entity_id", "target", "source_entity_id",
            "automation_entity_id",
        ):
            value = item.get(key)
            if isinstance(value, str):
                relevant_nodes.add(value)
                if value.startswith("automation."):
                    relevant_automations.add(value)

        if core.get("mode") == "automation_behavior":
            auto_id = item.get("automation_entity_id")
            if isinstance(auto_id, str):
                relevant_automations.add(auto_id)
                relevant_nodes.add(auto_id)
            for group in ("triggers", "guards", "local_guards", "waits", "actions", "calls"):
                for edge in item.get(group, []):
                    for key in ("subject", "object"):
                        value = edge.get(key)
                        if isinstance(value, str):
                            relevant_nodes.add(value)

    entity_index = {entity.entity_id: entity for entity in entity_list}
    current_identity = [
        {
            "entity_id": entity_id,
            "domain": entity_index[entity_id].domain,
            "name": entity_index[entity_id].name,
            "snapshot_state": entity_index[entity_id].state,
        }
        for entity_id in sorted(relevant_nodes)
        if entity_id in entity_index
    ]

    dependency_context = [
        {
            "subject": edge.subject,
            "predicate": edge.predicate,
            "object": edge.object,
            "source": edge.source.value,
            "detail": _edge_detail(edge),
        }
        for edge in deps
        if edge.subject in relevant_automations
        or edge.subject in relevant_nodes
        or edge.object in relevant_nodes
    ]

    r8_context = [
        {
            "subject": edge.subject,
            "predicate": edge.predicate,
            "object": edge.object,
            "source": edge.source.value,
            "detail": _edge_detail(edge),
        }
        for edge in r8
        if edge.subject in relevant_nodes
        or edge.object in relevant_nodes
        or edge.subject in relevant_automations
        or edge.object in relevant_automations
    ]

    business_context: list[dict[str, Any]] = []
    for entity_id in sorted(relevant_nodes):
        for item in business_context_for_entity(entity_id, business):
            business_context.append(
                {
                    "entity_id": entity_id,
                    "function": item.function,
                    "rule": item.rule,
                    "object_type": item.object_type,
                    "source_official": item.source_official,
                    "last_validation": item.last_validation,
                    "binding_status": item.binding_status,
                }
            )

    script_services = sorted({
        edge.object
        for edge in production
        if edge.subject in relevant_automations
        and edge.predicate in {"CALLS_PYSCRIPT", "CALLS_SCRIPT"}
    })
    script_context = script_context_for_services(
        script_services, script_catalog_list
    )

    unresolved = sorted({
        node
        for edge in production
        if edge.subject in relevant_automations
        or edge.object in relevant_automations
        or edge.subject in relevant_nodes
        or edge.object in relevant_nodes
        for node in (edge.subject, edge.object)
        if node.startswith(("registry_ref:", "device_ref:", "area_ref:", "unresolved_ref:"))
    })

    return {
        "query": query,
        "operational": core,
        "operational_answer_available": core.get("mode") != "unresolved",
        "layers": {
            "current_identity": current_identity,
            "production": core.get("results", []),
            "objects_ha": dependency_context,
            "r8": r8_context,
            "metier": business_context,
            "scripts": script_context,
        },
        "unresolved_refs": unresolved,
        "precedence": [
            "current_identity",
            "production",
            "objects_ha",
            "r8",
            "metier",
            "scripts",
        ],
    }

def retrieve_triggered_chains(
    query: str,
    entities: Iterable[EntityRecord],
    reconciliation: ReconciliationResult,
    edges: Iterable[GraphEdge],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Traverse source object -> trigger -> active automation -> concrete effects.

    This is the inverse operational question to retrieve_automation_chains.
    It is deliberately strict: only a current HA entity that appears as an
    actual TRIGGERS edge may start the traversal. Opaque registry/device
    references are not guessed from names.
    """
    entity_list = list(entities)
    candidates = resolve_entities(query, entity_list, limit=5)
    if not candidates:
        return []

    best_object_score = candidates[0][1]
    sources = [
        candidate for candidate in candidates
        if candidate[1] == best_object_score
    ]
    active = {
        item.entity_id: item
        for item in reconciliation.matched
        if item.state == "on"
    }
    edge_list = list(edges)
    results: list[dict[str, Any]] = []

    for source, object_score in sources:
        triggers = [
            edge for edge in edge_list
            if edge.subject == source.entity_id and edge.predicate == "TRIGGERS"
        ]
        for trigger in triggers:
            automation = active.get(trigger.object)
            if not automation:
                continue

            actions = [
                edge for edge in edge_list
                if edge.subject == automation.entity_id and edge.predicate == "ACTS_ON"
            ]
            calls = [
                edge for edge in edge_list
                if edge.subject == automation.entity_id
                and edge.predicate in {
                    "CALLS_AUTOMATION", "CALLS_SCRIPT", "CALLS_PYSCRIPT", "CALLS_SERVICE"
                }
            ]
            for action in actions:
                detail = _edge_detail(action)
                context_edges = _context_for_action(
                    automation.entity_id, detail, edge_list
                )
                barriers = _barriers_before_action(
                    automation.entity_id, detail, edge_list
                )
                results.append(
                    {
                        "score": object_score + 100,
                        "source_entity_id": source.entity_id,
                        "source_name": source.name,
                        "automation_entity_id": automation.entity_id,
                        "automation_name": automation.name,
                        "target": action.object,
                        "effect": detail.get("effect"),
                        "action_detail": detail,
                        "trigger_detail": json.loads(trigger.detail) if trigger.detail else {},
                        "context": [
                            {
                                "subject": item.subject,
                                "predicate": item.predicate,
                                "detail": _edge_detail(item),
                            }
                            for item in context_edges
                        ],
                        "barriers": [
                            {
                                "object": item.object,
                                "detail": _edge_detail(item),
                            }
                            for item in barriers
                        ],
                    }
                )

            if not actions and calls:
                for call in calls:
                    results.append(
                        {
                            "score": object_score + 80,
                            "source_entity_id": source.entity_id,
                            "source_name": source.name,
                            "automation_entity_id": automation.entity_id,
                            "automation_name": automation.name,
                            "target": call.object,
                            "effect": call.predicate.lower(),
                            "action_detail": json.loads(call.detail) if call.detail else {},
                            "trigger_detail": json.loads(trigger.detail) if trigger.detail else {},
                            "context": [
                                {
                                    "subject": item.subject,
                                    "predicate": item.predicate,
                                    "detail": _edge_detail(item),
                                }
                                for item in context_edges
                            ],
                        }
                    )

    dedup: dict[tuple[str, str, str | None], dict[str, Any]] = {}
    for result in results:
        key = (
            result["automation_entity_id"],
            result["target"],
            result["effect"],
        )
        previous = dedup.get(key)
        if previous is None or result["score"] > previous["score"]:
            dedup[key] = result
    return sorted(
        dedup.values(),
        key=lambda item: (-item["score"], item["automation_entity_id"], item["target"]),
    )[: max(1, limit)]