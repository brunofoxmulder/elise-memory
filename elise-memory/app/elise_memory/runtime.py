"""Runtime wiring for optional canonical synchronization.

Synchronization configuration errors are non-fatal: the HTTP API must remain
available even when Google credentials or source IDs are missing or invalid.
"""
import os

from .canonical_sources import missing_canonical_source_ids, require_canonical_source_ids
from .google_sheets import GoogleSheetsReader
from .knowledge import KnowledgeStore
from .scheduler import NightlyScheduler, SchedulerConfig
from .sync import synchronize_canonical


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def sync_runtime_status() -> dict:
    enabled = _bool("ELISE_MEMORY_SYNC_ENABLED")
    credentials = os.getenv("ELISE_MEMORY_GOOGLE_CREDENTIALS", "").strip()
    credentials_present = bool(credentials) and os.path.isfile(credentials)
    sources_configured = not missing_canonical_source_ids()
    return {
        "enabled": enabled,
        "ready": enabled and credentials_present and sources_configured,
        "credentials_present": credentials_present,
        "sources_configured": sources_configured,
    }


def _safe_reader(store: KnowledgeStore | None = None) -> GoogleSheetsReader | None:
    credentials = os.getenv("ELISE_MEMORY_GOOGLE_CREDENTIALS", "").strip()
    if not credentials or not os.path.isfile(credentials):
        if store is not None:
            store.record_sync_failure("RuntimeError: google_credentials_missing")
        return None

    try:
        require_canonical_source_ids()
    except RuntimeError as exc:
        if store is not None:
            store.record_sync_failure(f"RuntimeError: {exc}")
        return None

    try:
        return GoogleSheetsReader(credentials)
    except Exception as exc:
        if store is not None:
            store.record_sync_failure(
                f"RuntimeError: google_credentials_invalid_or_unreadable:{type(exc).__name__}"
            )
        return None


def build_scheduler(store: KnowledgeStore) -> NightlyScheduler | None:
    if not _bool("ELISE_MEMORY_SYNC_ENABLED"):
        return None

    reader = _safe_reader(store)
    if reader is None:
        return None

    config = SchedulerConfig(
        enabled=True,
        hour=int(os.getenv("ELISE_MEMORY_SYNC_HOUR", "3")),
        minute=int(os.getenv("ELISE_MEMORY_SYNC_MINUTE", "0")),
        timezone=os.getenv("ELISE_MEMORY_SYNC_TIMEZONE", "Europe/Paris"),
    )

    def job() -> None:
        try:
            synchronize_canonical(store, reader)
        except Exception as exc:
            store.record_sync_failure(f"{type(exc).__name__}: {exc}")
            raise

    return NightlyScheduler(config, job)


def build_reader_from_env() -> GoogleSheetsReader:
    credentials = os.getenv("ELISE_MEMORY_GOOGLE_CREDENTIALS", "").strip()
    if not credentials or not os.path.isfile(credentials):
        raise RuntimeError("google_credentials_missing")
    require_canonical_source_ids()
    try:
        return GoogleSheetsReader(credentials)
    except Exception as exc:
        raise RuntimeError(
            f"google_credentials_invalid_or_unreadable:{type(exc).__name__}"
        ) from exc
