"""Network allowlist and fail-closed administration authentication."""

import os
import secrets
import socket

from fastapi import Header, HTTPException
from mcp.server.transport_security import TransportSecuritySettings


def transport_security() -> TransportSecuritySettings:
    """Trust loopback and the actual container name, never arbitrary hosts."""
    hostname = socket.gethostname().lower()
    hosts = ["127.0.0.1", "localhost", "[::1]", hostname]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[value for host in hosts for value in (host, f"{host}:*")],
        # MCP is server-to-server: browser origins are deliberately not allowed.
        allowed_origins=[],
    )


def require_admin(authorization: str | None = Header(default=None)) -> None:
    """Disable writes unless a separate strong administration token is configured.

    The Supervisor token is never reused. This secret is not exposed to MCP tools.
    A token authenticates a caller, not proof of a user's conversational consent.
    """
    token = os.getenv("ELISE_MEMORY_ADMIN_TOKEN", "")
    if len(token) < 32:
        raise HTTPException(status_code=503, detail="administrative writes disabled")
    expected = f"Bearer {token}".encode("utf-8")
    provided = (authorization or "").encode("utf-8")
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail="administrative authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
