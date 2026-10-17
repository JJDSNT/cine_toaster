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

    def creation(self) -> dict[str, Any]:
        return self._call("/api/creation")

    def save_inception_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call("/api/creation/agent-draft", payload)

    def assess_inception(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call("/api/creation/assessment", payload)

    def generation(self, recipe: str = "", jobs: int = 0) -> dict[str, Any]:
        query = urllib.parse.urlencode({"recipe": recipe, "jobs": jobs}) if recipe else ""
        return self._call("/api/generation" + ("?" + query if query else ""))

    def ask_intake(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call("/api/creation/intake-questions", payload)

    def save_art_brief(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call("/api/creation/art-brief", payload)

    def visual_images(self, references: list[str]) -> dict[str, Any]:
        return self._call("/api/creation/art-images", {"references": references})

    def save_visual_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call("/api/creation/visual-review", payload)

    def planning(self) -> dict[str, Any]:
        return self._call("/api/planning-context")

    def save_direction_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call("/api/creation/direction-plan", payload)

    def save_continuity_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call("/api/creation/continuity-review", payload)

    def plan_reference(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call("/api/creation/reference-plan", payload)

    def start_reference(self, plan: dict[str, Any]) -> dict[str, Any]:
        return self._call("/api/jobs", {"kind": "generate_reference", "params": {**plan, "accept_quota": True}})

    def job(self, job_id: str) -> dict[str, Any]:
        return self._call("/api/jobs/" + urllib.parse.quote(job_id, safe=""))

    def reference_jobs(self) -> list[dict]:
        return [{key: job.get(key) for key in ('id', 'state', 'adopted_at', 'result', 'error')}
                | {'art_brief': job.get('params', {}).get('art_brief')}
                for job in self._call('/api/jobs') if job.get('kind') == 'generate_reference'][:8]

    def keep_reference(self, job_id: str) -> dict[str, Any]:
        return self._call("/api/jobs/" + urllib.parse.quote(job_id, safe="") + "/adopt", {"overwrite": False})

    def storyboard(self, scene: str = "") -> dict[str, Any]:
        return self._call("/api/storyboard?scene=" + urllib.parse.quote(scene))

    def publish_storyboard(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call('/api/creation/publish-storyboard', payload)

    def budget(self) -> dict[str, Any]:
        return self._call("/api/budget")

    def scene(self, scene_id: str) -> dict[str, Any]:
        return self._call("/api/scene?id=" + urllib.parse.quote(scene_id))

    def command(self, command: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call("/api/commands", {"command": command, "actor": ACTOR, **payload})
