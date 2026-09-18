import os

from elise_memory.__main__ import main


def test_main_uses_safe_runtime_defaults(monkeypatch):
    seen = {}
    monkeypatch.delenv("ELISE_MEMORY_HOST", raising=False)
    monkeypatch.delenv("ELISE_MEMORY_PORT", raising=False)
    monkeypatch.setattr("uvicorn.run", lambda app, host, port: seen.update(app=app, host=host, port=port))
    main()
    assert seen == {"app": "elise_memory.app:app", "host": "0.0.0.0", "port": 8099}
