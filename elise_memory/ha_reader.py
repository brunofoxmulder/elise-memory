"""Strictly read-only Home Assistant client for Élise Memory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class HomeAssistantReadError(RuntimeError):
    pass


@dataclass(frozen=True)
class HAState:
    entity_id: str
    state: str
    last_changed: datetime
    attributes: dict


@dataclass(frozen=True)
class HAHistoryState:
    state: str
    last_changed: datetime


class HomeAssistantReader:
    """Minimal client restricted to Home Assistant read-only HTTP GET calls."""

    def __init__(self, base_url: str, token: str, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _get_json(self, url: str):
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
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise HomeAssistantReadError(str(exc)) from exc

    def get_state(self, entity_id: str) -> HAState:
        payload = self._get_json(f"{self.base_url}/api/states/{entity_id}")
        try:
            return HAState(
                entity_id=payload["entity_id"],
                state=payload["state"],
                last_changed=datetime.fromisoformat(payload["last_changed"]),
                attributes=payload.get("attributes", {}),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HomeAssistantReadError("invalid Home Assistant state payload") from exc

    def get_history(self, entity_id: str, start: datetime) -> list[HAHistoryState]:
        params = urlencode(
            {
                "filter_entity_id": entity_id,
                "minimal_response": "",
                "no_attributes": "",
            }
        )
        url = f"{self.base_url}/api/history/period/{start.isoformat()}?{params}"
        payload = self._get_json(url)
        try:
            rows = payload[0] if payload else []
            return [
                HAHistoryState(
                    state=row["state"],
                    last_changed=datetime.fromisoformat(row["last_changed"]),
                )
                for row in rows
            ]
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise HomeAssistantReadError("invalid Home Assistant history payload") from exc
