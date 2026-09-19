"""Lightweight, truth-first entity resolution for Élise Memory.

This module helps the conversation agent resolve an intended HA target. It never
executes services and never reconstructs event causality.
"""
import re
import unicodedata
from pydantic import BaseModel, Field
from .ha_reader import HomeAssistantReader

DOMAIN_HINTS = {
    "lampe": "light", "lumiere": "light", "lumière": "light",
    "volet": "cover", "store": "cover",
    "prise": "switch", "chargeur": "switch", "recharge": "switch",
    "serrure": "lock", "verrou": "lock",
}

class EntityCandidate(BaseModel):
    entity_id: str
    name: str
    domain: str
    state: str
    score: int
    provenance: str = "ha_current"

class ResolutionResult(BaseModel):
    query: str
    candidates: list[EntityCandidate] = Field(default_factory=list)
    resolved: bool = False
    reason: str

def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    return " ".join("".join(c for c in value.lower() if not unicodedata.combining(c)).split())

def _tokens(value: str) -> set[str]:
    return {x for x in re.split(r"[^a-z0-9]+", _fold(value)) if len(x) >= 2}

def resolve_current_entity(reader: HomeAssistantReader, query: str, *, limit: int = 5) -> ResolutionResult:
    q = _fold(query)
    qtokens = _tokens(q)
    if not qtokens:
        return ResolutionResult(query=query, reason="empty_query")
    hinted = {domain for word, domain in DOMAIN_HINTS.items() if _fold(word) in qtokens}
    scored = []
    for item in reader.get_states():
        domain = item.entity_id.split(".", 1)[0]
        name = str(item.attributes.get("friendly_name") or item.entity_id)
        hay = _fold(f"{name} {item.entity_id.replace('_', ' ')}")
        tokens = _tokens(hay)
        overlap = len(qtokens & tokens)
        if not overlap:
            continue
        score = overlap * 20
        if q == _fold(name) or q == _fold(item.entity_id):
            score += 100
        elif q in hay:
            score += 30
        if hinted:
            score += 25 if domain in hinted else -25
        scored.append(EntityCandidate(
            entity_id=item.entity_id, name=name, domain=domain,
            state=item.state, score=score,
        ))
    scored.sort(key=lambda x: (-x.score, x.entity_id))
    candidates = scored[:max(1, min(limit, 10))]
    if not candidates:
        return ResolutionResult(query=query, candidates=[], resolved=False, reason="no_current_ha_match")
    top = candidates[0]
    second = candidates[1].score if len(candidates) > 1 else -1
    resolved = top.score >= 60 and top.score - second >= 20
    return ResolutionResult(
        query=query, candidates=candidates, resolved=resolved,
        reason="unique_high_confidence_match" if resolved else "ambiguous_current_ha_matches",
    )
