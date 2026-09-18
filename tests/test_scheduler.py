from datetime import datetime
from zoneinfo import ZoneInfo

from elise_memory.scheduler import SchedulerConfig, next_run


def test_next_run_same_night_when_time_not_passed():
    cfg=SchedulerConfig(enabled=True,hour=3,minute=30,timezone="Europe/Paris")
    now=datetime(2026,9,18,1,0,tzinfo=ZoneInfo("Europe/Paris"))
    assert next_run(now,cfg).isoformat()=="2026-09-18T03:30:00+02:00"


def test_next_run_moves_to_tomorrow_after_time():
    cfg=SchedulerConfig(enabled=True,hour=3,minute=30,timezone="Europe/Paris")
    now=datetime(2026,9,18,4,0,tzinfo=ZoneInfo("Europe/Paris"))
    assert next_run(now,cfg).date().isoformat()=="2026-09-19"


def test_invalid_time_is_rejected():
    cfg=SchedulerConfig(enabled=True,hour=25)
    try:
        cfg.validate()
        assert False
    except ValueError as exc:
        assert str(exc)=="invalid_sync_time"
