from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from cine_toaster.index import build_index, ProjectIndex
from cine_toaster.project import load_scene
from cine_toaster.web import ProjectBrowserHandler


DEMO_PROJECT = Path(__file__).parents[1] / "examples" / "demo-project"
SCENE = "SC-030"
SHOT = "P1"


class HttpCommandTests(unittest.TestCase):
    """The HTTP surface must reach the same command as the CLI, or the two drift."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        base = Path(self.directory.name)
        self.root = base / "production"
        shutil.copytree(DEMO_PROJECT, self.root)

        self.previous_cache = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        self.addCleanup(self._restore_cache)

        build_index(self.root)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ProjectBrowserHandler)
        self.server.project_index = ProjectIndex(self.root)
        self.server.project_root = self.root.resolve()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def _restore_cache(self) -> None:
        if self.previous_cache is None:
            os.environ.pop("XDG_CACHE_HOME", None)
        else:
            os.environ["XDG_CACHE_HOME"] = self.previous_cache

    def _stop_server(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def post(self, payload: dict) -> tuple[int, dict]:
        request = urllib.request.Request(
            f"{self.base_url}/api/commands",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def get(self, path: str):
        with urllib.request.urlopen(f"{self.base_url}{path}", timeout=10) as response:
            return json.loads(response.read())

    def test_selection_through_http_commits_the_same_state(self) -> None:
        status, body = self.post(
            {
                "command": "select_take",
                "scene_id": SCENE,
                "shot_id": SHOT,
                "take_id": "HARD-CUT-IN",
                "actor": {"id": "director", "kind": "human"},
                "rationale": "Chosen in the browser.",
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(body["revision"], 1)
        scene = load_scene(self.root, SCENE)
        shot = next(item for item in scene["shots"] if item["id"] == SHOT)
        self.assertEqual(shot["selected_take"], "HARD-CUT-IN")

    def test_conflict_is_reported_as_409(self) -> None:
        self.post(
            {
                "command": "select_take",
                "scene_id": SCENE,
                "shot_id": SHOT,
                "take_id": "HARD-CUT-IN",
                "actor": {"id": "director"},
            }
        )
        status, body = self.post(
            {
                "command": "select_take",
                "scene_id": SCENE,
                "shot_id": SHOT,
                "take_id": "CUT",
                "expected_revision": 0,
                "actor": {"id": "director"},
            }
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "revision_conflict")

    def test_unknown_take_is_reported_as_404(self) -> None:
        status, body = self.post(
            {
                "command": "select_take",
                "scene_id": SCENE,
                "shot_id": SHOT,
                "take_id": "T99",
                "actor": {"id": "director"},
            }
        )
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "not_found")

    def test_rejected_take_is_reported_as_409(self) -> None:
        status, body = self.post(
            {
                "command": "select_take",
                "scene_id": SCENE,
                "shot_id": "P2",
                "take_id": "LOOKS-AT-CAMERA",
                "actor": {"id": "director"},
            }
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "take_not_eligible")

    def test_malformed_body_is_reported_as_422(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/commands",
            data=b"not json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(caught.exception.code, 422)

    def test_events_endpoint_reports_the_commit(self) -> None:
        self.post(
            {
                "command": "select_take",
                "scene_id": SCENE,
                "shot_id": SHOT,
                "take_id": "LONGER-HOLD",
                "actor": {"id": "director"},
            }
        )
        events = self.get("/api/events")
        self.assertEqual(events[-1]["type"], "take.selected")
        self.assertEqual(events[-1]["payload"]["take_id"], "LONGER-HOLD")

    def test_unknown_post_route_is_404(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/nope", data=b"{}", method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(caught.exception.code, 404)

    def test_static_assets_cannot_escape_the_asset_root(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(f"{self.base_url}/static/../../../etc/passwd", timeout=10)
        self.assertIn(caught.exception.code, (400, 404))


if __name__ == "__main__":
    unittest.main()
