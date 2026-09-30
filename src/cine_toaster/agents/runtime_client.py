"""The assistant's only way into the production: the runtime's own HTTP API."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..errors import CineToasterError, ValidationError

ACTOR = {"id": "assistant", "kind": "agent"}


class RuntimeClient:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")

    def _call(self, path: str, body: dict[str, Any] | None = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + path, data=data,
                                         headers={"Content-Type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            detail = json.loads(error.read() or b"{}").get("error") or {}
            message = detail.get("message") if isinstance(detail, dict) else str(detail)
            raise ValidationError(message or f"The runtime answered {error.code}") from error
        except urllib.error.URLError as error:
            raise CineToasterError(f"The runtime at {self.url} is not reachable: {error.reason}") from error

    def production(self) -> dict[str, Any]:
        return self._call("/api/production")

    def screenplay(self) -> dict[str, Any]:
        return self._call("/api/screenplay")

    def budget(self) -> dict[str, Any]:
        return self._call("/api/budget")

    def scene(self, scene_id: str) -> dict[str, Any]:
        return self._call("/api/scene?id=" + urllib.parse.quote(scene_id))

    def command(self, command: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call("/api/commands", {"command": command, "actor": ACTOR, **payload})
