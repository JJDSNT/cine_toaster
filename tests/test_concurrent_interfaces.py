"""The canvas, the CLI and an agent deciding on one scene at the same moment (CT-0046).

Each interface runs the same command; none may lose another's decision. The
canvas and the agent reach the runtime over HTTP, from threads; the CLI runs
the commands in a process of its own, as `toast` does beside a running
`toast serve`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from cine_toaster.index import ProjectIndex, build_index
from cine_toaster.project import load_scene
from cine_toaster.web import ProjectBrowserHandler

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
SRC = Path(__file__).parents[1] / "src"
ROUNDS = 20

#: The CLI's side: another process, the same commands.
CLI = """
import sys
from pathlib import Path
from cine_toaster.commands import dispatch
root, rounds = Path(sys.argv[1]), int(sys.argv[2])
takes = ["CUT", "ONE-BLINK"]
for index in range(rounds):
    dispatch(root, "select_take", {"scene_id": "SC-030", "shot_id": "P3", "take_id": takes[index % 2],
                                   "actor": {"id": "cli", "kind": "human"}})
"""


class ConcurrentInterfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)
        self.previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        os.environ["XDG_STATE_HOME"] = str(base / "state")
        self.addCleanup(self._restore)
        build_index(self.root)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ProjectBrowserHandler)
        self.server.project_index = ProjectIndex(self.root)
        self.server.project_root = self.root.resolve()
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._stop, thread)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def _restore(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _stop(self, thread: threading.Thread) -> None:
        self.server.shutdown()
        self.server.server_close()
        thread.join(timeout=5)

    def post(self, payload: dict) -> tuple[int, dict]:
        request = urllib.request.Request(f"{self.url}/api/commands", data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def cli(self, rounds: int) -> subprocess.Popen:
        environment = {**os.environ, "PYTHONPATH": str(SRC)}
        return subprocess.Popen([sys.executable, "-c", CLI, str(self.root), str(rounds)], env=environment,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_simultaneous_decisions_from_every_interface_are_all_kept(self) -> None:
        failures: list[str] = []

        def canvas() -> None:
            for index in range(ROUNDS):
                status, body = self.post({"command": "set_cut", "scene_id": "SC-030", "shot_id": "P2",
                                          "actor": {"id": "canvas", "kind": "human"},
                                          "cut": {"type": ["match", "action"][index % 2]}})
                if status != 200:
                    failures.append(f"canvas {status} {body}")

        def agent() -> None:
            for index in range(ROUNDS):
                status, body = self.post({"command": "select_take", "scene_id": "SC-030", "shot_id": "P1",
                                          "actor": {"id": "assistant", "kind": "agent"},
                                          "take_id": ["HARD-CUT-IN", "LONGER-HOLD"][index % 2]})
                if status != 200:
                    failures.append(f"agent {status} {body}")

        process = self.cli(ROUNDS)
        threads = [threading.Thread(target=canvas), threading.Thread(target=agent)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)
        _, errors = process.communicate(timeout=120)
        self.assertEqual(process.returncode, 0, errors)
        self.assertEqual(failures, [])

        scene = load_scene(self.root, "SC-030")
        # Every decision is in the history, each at its own revision: none was written over.
        self.assertEqual(scene["revision"], 3 * ROUNDS)
        by_actor: dict[str, int] = {}
        for entry in scene["decision_log"]:
            by_actor[entry["actor"]["id"]] = by_actor.get(entry["actor"]["id"], 0) + 1
        self.assertEqual(by_actor, {"canvas": ROUNDS, "assistant": ROUNDS, "cli": ROUNDS})
        # And the last word of each is what stands.
        shots = {shot["id"]: shot for shot in scene["shots"]}
        self.assertEqual(shots["P1"]["selected_take"], "LONGER-HOLD")
        self.assertEqual(shots["P3"]["selected_take"], "ONE-BLINK")
        self.assertEqual(shots["P2"]["cut_decision"]["type"], "action")

    def test_an_edit_made_on_a_view_older_than_another_interface_is_refused(self) -> None:
        drawn = load_scene(self.root, "SC-030")["revision"]
        process = self.cli(1)  # the CLI decides while the canvas is still showing the old revision
        _, errors = process.communicate(timeout=60)
        self.assertEqual(process.returncode, 0, errors)
        status, body = self.post({"command": "set_cut", "scene_id": "SC-030", "shot_id": "P2",
                                  "actor": {"id": "canvas", "kind": "human"}, "cut": {"type": "match"},
                                  "expected_revision": drawn})
        self.assertEqual(status, 409, body)
        self.assertEqual(body["error"]["code"], "revision_conflict")
        scene = load_scene(self.root, "SC-030")
        self.assertEqual(scene["revision"], drawn + 1)
        self.assertIsNone(next(shot for shot in scene["shots"] if shot["id"] == "P2")["cut_decision"])


if __name__ == "__main__":
    unittest.main()
