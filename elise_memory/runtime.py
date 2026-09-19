"""Runtime wiring for optional canonical synchronization.

The feature is inert unless ELISE_MEMORY_SYNC_ENABLED=true. Google credentials
and canonical workbook IDs are private runtime configuration.
"""

import os

from .canonical_sources import require_canonical_source_ids
from .google_sheets import GoogleSheetsReader
from .knowledge import KnowledgeStore
from .scheduler import NightlyScheduler, SchedulerConfig
from .sync import synchronize_canonical


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1","true","yes","on"}


def build_scheduler(store: KnowledgeStore) -> NightlyScheduler | None:
    if not _bool("ELISE_MEMORY_SYNC_ENABLED"):
        return None
    credentials = os.getenv("ELISE_MEMORY_GOOGLE_CREDENTIALS", "").strip()
    if not credentials:
        raise RuntimeError("google_credentials_required")

    # Keep the API available after an upgrade even if the new private source
    # configuration has not yet been entered. No synchronization is scheduled.
    try:
        require_canonical_source_ids()
    except RuntimeError as exc:
        store.record_sync_failure(f"RuntimeError: {exc}")
        return None

    config = SchedulerConfig(
        enabled=True,
        hour=int(os.getenv("ELISE_MEMORY_SYNC_HOUR", "3")),
        minute=int(os.getenv("ELISE_MEMORY_SYNC_MINUTE", "0")),
        timezone=os.getenv("ELISE_MEMORY_SYNC_TIMEZONE", "Europe/Paris"),
    )
    reader = GoogleSheetsReader(credentials)

    def job() -> None:
        try:
            synchronize_canonical(store, reader)
        except Exception as exc:
            store.record_sync_failure(f"{type(exc).__name__}: {exc}")
            raise

    return NightlyScheduler(config, job)


def build_reader_from_env() -> GoogleSheetsReader:
    """Build the read-only canonical source reader for an explicit sync request."""
    credentials = os.getenv("ELISE_MEMORY_GOOGLE_CREDENTIALS", "").strip()
    if not credentials:
        raise RuntimeError("google_credentials_required")
    require_canonical_source_ids()
    return GoogleSheetsReader(credentials)
