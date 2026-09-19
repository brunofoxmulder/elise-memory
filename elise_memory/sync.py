"""Canonical Google Sheets -> SQLite synchronization orchestration."""

from dataclasses import dataclass

from .canonical_sources import canonical_ranges, require_canonical_source_ids
from .compiler import (
    CompiledKnowledge, compile_automations, compile_memory_ia,
    compile_metier, compile_relations, compile_scripts,
)
from .google_sheets import GoogleSheetsReader
from .knowledge import KnowledgeStore


@dataclass(frozen=True)
class SyncReport:
    source_rows: dict[str, int]
    compiled_by_source: dict[str, int]
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
    require_canonical_source_ids()
    sources = canonical_ranges()

    raw = {}
    counts = {}
    for name, source in sources.items():
        values = reader.values(source)
        header, rows = _split(values)
        raw[name] = (header, rows)
        counts[name] = sum(1 for row in rows if any(str(x).strip() for x in row))

    compiled: list[CompiledKnowledge] = []
    compiled_by_source: dict[str, int] = {}
    for name, compiler in (
        ("metier", compile_metier),
        ("memory_ia", compile_memory_ia),
        ("automations", compile_automations),
        ("scripts", compile_scripts),
    ):
        header, rows = raw[name]
        entries = compiler(header, rows)
        compiled_by_source[name] = len(entries)
        compiled.extend(entries)

    relation_header, relation_rows = raw["relations"]
    relations = compile_relations(relation_header, relation_rows)
    compiled_by_source["relations"] = len(relations)

    # A required canonical source becoming semantically empty is suspicious.
    # Fail before SQLite publication rather than silently erasing a whole source.
    empty = sorted(name for name, count in compiled_by_source.items() if count == 0)
    if empty:
        raise ValueError(f"canonical_source_compiled_empty:{','.join(empty)}")

    # No database mutation has happened before this point.
    result = store.apply_canonical_snapshot(
        [(entry.item, entry.content_hash) for entry in compiled],
        relations=relations,
        source_stats={
            name: (counts[name], compiled_by_source[name])
            for name in sources
        },
    )
    return SyncReport(
        source_rows=counts,
        compiled_by_source=compiled_by_source,
        compiled_records=result["records"],
        changed=result["changed"],
        deactivated=result["deactivated"],
        relations=len(relations),
    )
