"""Strictly read-only Home Assistant client for Élise Memory."""
import json
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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
    def __init__(self, base_url="http://supervisor/core", token=None, timeout=5.0):
        if token is None:
            import os
            token = os.environ.get("SUPERVISOR_TOKEN")
        if not token:
            raise RuntimeError("SUPERVISOR_TOKEN is required")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _get_json(self, url):
        request = Request(url, method="GET", headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"})
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def get_state(self, entity_id):
        p = self._get_json(f"{self.base_url}/api/states/{entity_id}")
        return HAState(p["entity_id"], p["state"], datetime.fromisoformat(p["last_changed"]), p.get("attributes", {}))

    def get_history(self, entity_id, start):
        q = urlencode({"filter_entity_id": entity_id, "minimal_response": "", "no_attributes": ""})
        p = self._get_json(f"{self.base_url}/api/history/period/{start.isoformat()}?{q}")
        rows = p[0] if p else []
        return [HAHistoryState(x["state"], datetime.fromisoformat(x["last_changed"])) for x in rows]
