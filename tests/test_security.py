import asyncio

import pytest
from fastapi.testclient import TestClient
from mcp.server.transport_security import TransportSecurityMiddleware
from starlette.requests import Request

from elise_memory.app import app
from elise_memory.security import transport_security


@pytest.mark.parametrize("host,origin,status", [
    ("test-memory:8099", None, None),
    ("localhost:8099", None, None),
    ("attacker.example:8099", None, 421),
    ("test-memory.attacker.example:8099", None, 421),
    ("test-memory:8099", "https://attacker.example", 403),
])
def test_transport_allowlist(monkeypatch, host, origin, status):
    monkeypatch.setattr("elise_memory.security.socket.gethostname", lambda: "test-memory")
    headers = [(b"host", host.encode()), (b"content-type", b"application/json")]
    if origin:
        headers.append((b"origin", origin.encode()))
    request = Request({"type": "http", "method": "POST", "path": "/mcp/",
                       "headers": headers})
    response = asyncio.run(TransportSecurityMiddleware(transport_security()).validate_request(
        request, is_post=True))
    assert (response.status_code if response else None) == status


@pytest.mark.parametrize("path", ["/v1/memories", "/v1/conversation/memories",
                                  "/v1/session/greeting/commit", "/v1/sync/run"])
def test_all_writes_fail_closed(monkeypatch, path):
    monkeypatch.delenv("ELISE_MEMORY_ADMIN_TOKEN", raising=False)
    client = TestClient(app)
    assert client.post(path, json={}).status_code == 503
    monkeypatch.setenv("ELISE_MEMORY_ADMIN_TOKEN", "test-token-" * 4)
    assert client.post(path, json={}).status_code == 401
    assert client.post(path, json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_authorized_write_and_unauthorized_no_mutation(monkeypatch, tmp_path):
    from elise_memory import app as module
    from elise_memory.store import MemoryStore

    store = MemoryStore(tmp_path / "test.sqlite3")
    store.initialize()
    monkeypatch.setattr(module, "store", store)
    token = "test-token-" * 4
    monkeypatch.setenv("ELISE_MEMORY_ADMIN_TOKEN", token)
    payload = {"kind": "house", "key": "test", "value": "fact", "source": "test"}
    client = TestClient(app)
    assert client.post("/v1/memories", json=payload).status_code == 401
    assert store.find("house", "test") == []
    assert client.post("/v1/memories", json=payload,
                       headers={"Authorization": f"Bearer {token}"}).status_code == 201
    assert len(store.find("house", "test")) == 1
