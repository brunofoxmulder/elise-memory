"""Runtime wiring for optional canonical synchronization.

The feature is inert unless ELISE_MEMORY_SYNC_ENABLED=true and a credentials
file path is explicitly provided.
"""

import os

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
