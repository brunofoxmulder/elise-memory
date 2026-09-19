"""Approved canonical source coordinates.

Workbook IDs are private runtime configuration. The repository only carries
sheet names and ranges; it never embeds a user's Google workbook IDs.
"""
import os

from .google_sheets import SheetRange

_ENV_BY_WORKBOOK = {
    "home_assistant": "ELISE_MEMORY_SHEET_HOME_ASSISTANT_ID",
    "index": "ELISE_MEMORY_SHEET_INDEX_ID",
    "automations": "ELISE_MEMORY_SHEET_AUTOMATIONS_ID",
    "scripts": "ELISE_MEMORY_SHEET_SCRIPTS_ID",
}


def _workbook_id(name: str) -> str:
    return os.getenv(_ENV_BY_WORKBOOK[name], "").strip()


def canonical_ranges() -> dict[str, SheetRange]:
    return {
        "metier": SheetRange(
            _workbook_id("home_assistant"),
            "Référentiel métier", "A1:P1000"),
        "memory_ia": SheetRange(
            _workbook_id("home_assistant"),
            "Mémoire IA", "A1:T1000"),
        "relations": SheetRange(
            _workbook_id("index"),
            "09_Relations fonctionnelles", "A1:O1000"),
        "automations": SheetRange(
            _workbook_id("automations"),
            "Automatisations", "A1:M500"),
        "scripts": SheetRange(
            _workbook_id("scripts"),
            "Scripts Pyscript", "A1:Q500"),
    }


def missing_canonical_source_ids() -> list[str]:
    return [
        env_name
        for env_name in _ENV_BY_WORKBOOK.values()
        if not os.getenv(env_name, "").strip()
    ]


def require_canonical_source_ids() -> None:
    missing = missing_canonical_source_ids()
    if missing:
        raise RuntimeError("canonical_sources_required:" + ",".join(missing))
