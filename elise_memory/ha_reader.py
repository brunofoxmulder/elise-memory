"""Strictly read-only Home Assistant client for Élise Memory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HomeAssistantReadError(RuntimeError):
    pass


@dataclass(frozen=True)
class HAState:
    entity_id: str
    state: str
    last_changed: datetime
    attributes: dict


class HomeAssistantReader:
    """Minimal client limited to GET /api/states/<entity_id>."""

    def __init__(self, base_url: str, token: str, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def get_state(self, entity_id: str) -> HAState:
        url = f"{self.base_url}/api/states/{entity_id}"
        request = Request(
            url,
            method="GET",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise HomeAssistantReadError(str(exc)) from exc

        try:
            return HAState(
                entity_id=payload["entity_id"],
                state=payload["state"],
                last_changed=datetime.fromisoformat(payload["last_changed"]),
                attributes=payload.get("attributes", {}),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HomeAssistantReadError("invalid Home Assistant state payload") from exc
