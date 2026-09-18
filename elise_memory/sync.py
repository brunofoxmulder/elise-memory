"""Canonical Google Sheets -> SQLite synchronization orchestration."""

from dataclasses import dataclass

from .canonical_sources import CANONICAL_RANGES
from .compiler import (
    CompiledKnowledge, compile_automations, compile_memory_ia,
    compile_metier, compile_relations, compile_scripts,
)
from .google_sheets import GoogleSheetsReader
from .knowledge import KnowledgeStore


@dataclass(frozen=True)
class SyncReport:
    source_rows: dict[str, int]
    compiled_records: int
    changed: int
    deactivated: int
    relations: int


def _split(values):
    if not values:
        raise ValueError("source_has_no_header")
    return values[0], values[1:]


def synchronize_canonical(store: KnowledgeStore, reader: GoogleSheetsReader) -> SyncReport:
    """Read every required source first; publish only after all compile successfully."""
    raw = {}
    counts = {}
    for name, source in CANONICAL_RANGES.items():
        values = reader.values(source)
        header, rows = _split(values)
        raw[name] = (header, rows)
        counts[name] = sum(1 for row in rows if any(str(x).strip() for x in row))

    compiled: list[CompiledKnowledge] = []
    for name, compiler in (
        ("metier", compile_metier),
        ("memory_ia", compile_memory_ia),
        ("automations", compile_automations),
        ("scripts", compile_scripts),
    ):
        header, rows = raw[name]
        compiled.extend(compiler(header, rows))

    relation_header, relation_rows = raw["relations"]
    relations = compile_relations(relation_header, relation_rows)

    # No database mutation has happened before this point.
    result = store.apply_canonical_snapshot(
        [(entry.item, entry.content_hash) for entry in compiled]
    )
    store.replace_canonical_relations(relations)
    return SyncReport(
        source_rows=counts,
        compiled_records=result["records"],
        changed=result["changed"],
        deactivated=result["deactivated"],
        relations=len(relations),
    )
