"""Pure compiler for canonical Maison Cognitive rows.

This module does not access Google Drive. It turns already-read rows into compact,
validated house knowledge. Network/authentication is deliberately a separate layer.
"""

import hashlib
import json
import unicodedata
from dataclasses import dataclass

from .knowledge import KnowledgeCreate


class SourceSchemaError(ValueError):
    pass


@dataclass(frozen=True)
class CompiledKnowledge:
    item: KnowledgeCreate
    content_hash: str


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _fold(value: object) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", _norm(value)).lower()
        if not unicodedata.combining(c)
    )


def is_validated(value: object) -> bool:
    return _fold(value).startswith("valide")


def is_active_relation(value: object) -> bool:
    """Accept current/usable relations and reject explicit historical/uncertain ones.

    The canonical sheet uses several legitimate status labels, not a single enum.
    We therefore fail closed on explicit negative/uncertain semantics, then accept
    statuses that positively express validation, production, operation or permanence.
    """
    folded = _fold(value)
    if not folded:
        return False
    veto = (
        "historique", "obsolet", "legacy", "remplace", "retire", "archive",
        "a observer", "observation", "prevision", "prudente", "hypothese",
        "requalifier", "ko",
    )
    if any(word in folded for word in veto):
        return False
    positive = (
        "valide", "production", "operationnel", "actif", "permanent",
        "obligatoire", "fonctionnel", "installe",
    )
    return any(word in folded for word in positive)


def stable_hash(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _rows(header: list[object], rows: list[list[object]], required: set[str]):
    names = [_norm(x) for x in header]
    missing = required - set(names)
    if missing:
        raise SourceSchemaError(f"missing columns: {', '.join(sorted(missing))}")
    for raw in rows:
        padded = list(raw) + [""] * (len(names) - len(raw))
        row = dict(zip(names, padded))
        if any(_norm(v) for v in row.values()):
            yield row


def compile_metier(header, rows) -> list[CompiledKnowledge]:
    required = {"Domaine", "Fonction métier", "Entité Home Assistant actuelle",
                "Type", "Valeur métier", "Source officielle"}
    out = []
    for row in _rows(header, rows, required):
        function = _norm(row["Fonction métier"])
        entity = _norm(row["Entité Home Assistant actuelle"])
        if not function:
            continue
        # Curated métier rows are useful only when they declare an official source.
        source = _norm(row["Source officielle"])
        if not source:
            continue
        key = entity or f"metier:{_fold(function).replace(' ', '-')}"
        payload = {
            "function": function,
            "entity_id": entity or None,
            "business_value": _norm(row.get("Valeur métier")) or None,
            "rule": _norm(row.get("État attendu / règle")) or None,
            "hardware": _norm(row.get("Dépendance matériel")) or None,
            "criticality": _norm(row.get("Criticité")) or None,
            "comment": _norm(row.get("Commentaire")) or None,
        }
        item = KnowledgeCreate(
            key=key, object_type=_norm(row["Type"]) or "business_function",
            domain=_norm(row["Domaine"]) or None,
            value=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            origin="canonical",
            source_id=f"home-assistant:referentiel-metier:{_fold(function)}",
            source_locator=f"Home Assistant / Référentiel métier / {function}",
            evidence=source,
        )
        out.append(CompiledKnowledge(item, stable_hash(payload)))
    return out


def compile_memory_ia(header, rows) -> list[CompiledKnowledge]:
    required = {"ID connaissance", "Domaine", "Connaissance", "Statut"}
    out = []
    for row in _rows(header, rows, required):
        kid = _norm(row["ID connaissance"])
        knowledge = _norm(row["Connaissance"])
        if not kid or not knowledge or not is_validated(row["Statut"]):
            continue
        payload = {"knowledge": knowledge, "status": _norm(row["Statut"])}
        confidence = _norm(row.get("Confiance (%)"))
        item = KnowledgeCreate(
            key=f"knowledge:{kid}", object_type="validated_knowledge",
            domain=_norm(row["Domaine"]) or None, value=knowledge,
            origin="canonical", source_id=f"home-assistant:memoire-ia:{kid}",
            source_locator=f"Home Assistant / Mémoire IA / {kid}",
            evidence=_norm(row.get("Source / preuves")) or None,
            confidence=float(confidence) if confidence else None,
        )
        out.append(CompiledKnowledge(item, stable_hash(payload)))
    return out


def compile_relations(header, rows) -> list[dict]:
    required = {"Relation_ID", "Source_ID", "Relation", "Cible_ID", "Statut"}
    out = []
    for row in _rows(header, rows, required):
        if not is_active_relation(row["Statut"]):
            continue
        rid, source, relation, target = map(_norm, (
            row["Relation_ID"], row["Source_ID"], row["Relation"], row["Cible_ID"]))
        if not all((rid, source, relation, target)):
            continue
        out.append({
            "relation_id": rid, "subject_key": source, "relation": relation,
            "object_key": target, "source_id": f"index:relations:{rid}",
            "role": _norm(row.get("Rôle_ou_effet")) or None,
            "confidence": _norm(row.get("Confiance")) or None,
        })
    return out


def _is_production_status(value: object) -> bool:
    folded = _fold(value)
    return ("production" in folded or "actif" in folded) and not any(
        bad in folded for bad in ("test", "retire", "archive", "historique")
    )


def compile_automations(header, rows) -> list[CompiledKnowledge]:
    required = {"Nom de l'automatisation", "Domaine", "Descriptif", "Production", "Statut test"}
    out = []
    for row in _rows(header, rows, required):
        name = _norm(row["Nom de l'automatisation"])
        production = _norm(row["Production"])
        status = _norm(row["Statut test"])
        if not name or not production:
            continue
        # Test/Production-1 are never compiled. Status is used only as a safety veto.
        if any(bad in _fold(status) for bad in ("ko", "retire", "archive")):
            continue
        payload = {
            "name": name,
            "description": _norm(row["Descriptif"]) or None,
            "technical_inventory": _norm(row.get("Inventaire technique")) or None,
            "linked_automations": _norm(row.get("Automatisations liées")) or None,
        }
        item = KnowledgeCreate(
            key=f"automation:{_fold(name).replace(' ', '-')}",
            object_type="automation", domain=_norm(row["Domaine"]) or None,
            value=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            origin="canonical", source_id=f"automations:production:{_fold(name)}",
            source_locator=f"Automatisations / Automatisations / {name}",
            evidence="Production présente; Test et Production -1 exclus",
        )
        out.append(CompiledKnowledge(item, stable_hash(payload)))
    return out


def compile_scripts(header, rows) -> list[CompiledKnowledge]:
    required = {"ID", "Nom du fichier", "Service HA exposé", "Domaine", "Rôle", "Statut"}
    out = []
    for row in _rows(header, rows, required):
        sid, name, status = map(_norm, (row["ID"], row["Nom du fichier"], row["Statut"]))
        if not sid or not name or not _is_production_status(status):
            continue
        payload = {
            "file": name,
            "service": _norm(row["Service HA exposé"]) or None,
            "role": _norm(row["Rôle"]) or None,
            "entities": _norm(row.get("Entités HA utilisées")) or None,
            "reads": _norm(row.get("Onglets lus")) or None,
            "writes": _norm(row.get("Onglets écrits")) or None,
            "version": _norm(row.get("Version actuelle")) or None,
        }
        item = KnowledgeCreate(
            key=f"script:{sid}", object_type="pyscript",
            domain=_norm(row["Domaine"]) or None,
            value=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            origin="canonical", source_id=f"scripts:pyscript:{sid}",
            source_locator=f"Scripts - Maison Cognitive / Scripts Pyscript / {sid}",
            evidence=status,
        )
        out.append(CompiledKnowledge(item, stable_hash(payload)))
    return out
