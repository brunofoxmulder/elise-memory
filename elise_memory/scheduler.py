"""Small in-process scheduler for the nightly canonical sync.

No exact hour is hard-coded. Scheduling is disabled unless explicitly enabled.
"""

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class SchedulerConfig:
    enabled: bool = False
    hour: int = 3
    minute: int = 0
    timezone: str = "Europe/Paris"

    def validate(self) -> None:
        if not 0 <= self.hour <= 23 or not 0 <= self.minute <= 59:
            raise ValueError("invalid_sync_time")
        ZoneInfo(self.timezone)


def next_run(now: datetime, config: SchedulerConfig) -> datetime:
    config.validate()
    tz = ZoneInfo(config.timezone)
    local = now.astimezone(tz)
    candidate = local.replace(
        hour=config.hour, minute=config.minute, second=0, microsecond=0
    )
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate


class NightlyScheduler:
    def __init__(self, config: SchedulerConfig, job: Callable[[], None]) -> None:
        self.config = config
        self.job = job
        self._timer: threading.Timer | None = None
        self._stopped = threading.Event()

    def start(self) -> None:
        self.config.validate()
        if not self.config.enabled or self._timer is not None:
            return
        self._schedule_next()

    def stop(self) -> None:
        self._stopped.set()
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _schedule_next(self) -> None:
        if self._stopped.is_set():
            return
        now = datetime.now(ZoneInfo(self.config.timezone))
        target = next_run(now, self.config)
        self._timer = threading.Timer((target - now).total_seconds(), self._run)
        self._timer.daemon = True
        self._timer.start()

    def _run(self) -> None:
        self._timer = None
        try:
            self.job()
        finally:
            self._schedule_next()
