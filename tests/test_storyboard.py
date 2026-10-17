from __future__ import annotations

import base64
import io
import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from cine_toaster.creation import creation_view
from cine_toaster.errors import PersistenceError, ResourceNotFoundError, RevisionConflictError, ValidationError
from cine_toaster.references import add_reference
from cine_toaster.state import Actor
from cine_toaster.storyboard import load_storyboard, register_storyboard_candidate, storyboard_view

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a81sAAAAASUVORK5CYII=")
DEMO = Path(__file__).parents[1] / "examples/demo-project"


class StoryboardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "film"
        shutil.copytree(DEMO, self.root)
        self.image = self.base / "draft.png"
        self.image.write_bytes(PNG)
        self.ref = add_reference(self.root, [self.image], title="Idea", kind="made", name="idea")

    def save(self, **changes):
        values = dict(scene="SC-010", shot="P1", image=self.image, title="Opening", actor=Actor(id="test"),
                      expected_revision=load_storyboard(self.root)["revision"], references=[self.ref.name])
        values.update(changes)
        return register_storyboard_candidate(self.root, **values)

    def test_versions_preserve_sources_authored_files_and_input_hashes(self):
        authored = {path: path.read_bytes() for pattern in ("**/*.yaml", "**/*.fountain") for path in self.root.glob(pattern)}
        first = self.save(provenance={"prompt": "An opening drawing", "execution_inputs": []})["candidate"]
        second = self.save(based_on=first["id"])["candidate"]
        self.assertEqual(second["version"], 2)
        self.assertEqual(load_storyboard(self.root)["candidates"], [first, second])
        self.assertEqual((self.root / first["image"]["path"]).read_bytes(), PNG)
        self.assertEqual(self.image.read_bytes(), PNG)
        self.assertTrue(all(path.read_bytes() == original for path, original in authored.items()))
        view = storyboard_view(self.root)
        self.assertEqual(view["candidates"][0]["findings"], [])
        self.assertEqual(view["candidates"][0]["review"], "not_recorded")
        self.assertEqual(view["coverage"][0]["with_candidates"], 1)
        node = creation_view(self.root)["reference_history"]["nodes"][0]
        self.assertEqual(node["uses"][0]["kind"], "storyboard")

    def test_concurrent_writers_conflict(self):
        barrier = threading.Barrier(2)
        def write(title):
            barrier.wait()
            try:
                return self.save(title=title, expected_revision=0)["revision"]
            except RevisionConflictError:
                return "conflict"
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(list(pool.map(write, ["One", "Two"])).count("conflict"), 1)

    def test_failed_commit_retains_old_journal_and_images(self):
        self.save()
        journal = self.root / "storyboard/state.json"
        original = journal.read_bytes()
        images = list((self.root / "storyboard/images").iterdir())
        with patch("cine_toaster.storyboard.os.replace", side_effect=OSError("disk failure")):
            with self.assertRaises(PersistenceError):
                self.save()
        self.assertEqual(journal.read_bytes(), original)
        self.assertEqual(list((self.root / "storyboard/images").iterdir()), images)

    def test_changed_inputs_story_and_image_are_reported_not_replaced(self):
        first = self.save()["candidate"]
        (self.ref / "draft.png").write_bytes(PNG + b"changed")
        (self.root / first["image"]["path"]).write_bytes(PNG + b"changed")
        scene = self.root / "scenes/010-last-broadcast/scene.yaml"
        scene.write_text(scene.read_text().replace("Black screen. Radio static.", "Changed action."))
        findings = storyboard_view(self.root)["candidates"][0]["findings"]
        self.assertEqual({item["code"] for item in findings}, {"image_changed", "input_changed", "story_changed"})
        self.assertEqual(load_storyboard(self.root)["candidates"][0], first)

    def test_invalid_plan_parent_title_and_image_are_refused(self):
        for values, error in [({"shot": "missing"}, ResourceNotFoundError), ({"title": " "}, ValidationError),
                              ({"expected_revision": "0"}, ValidationError), ({"based_on": "missing"}, ValidationError),
                              ({"references": ["missing"]}, ResourceNotFoundError)]:
            with self.subTest(values=values), self.assertRaises(error):
                self.save(**values)
        self.image.write_bytes(b"not an image")
        with self.assertRaises(ValidationError):
            self.save()
        self.assertEqual(load_storyboard(self.root)["revision"], 0)

    def test_symlink_escape_and_corrupt_journal_do_not_become_empty_state(self):
        external = self.base / "external"
        external.mkdir()
        (self.root / "storyboard").symlink_to(external, target_is_directory=True)
        with self.assertRaises(ValidationError):
            self.save()
        self.assertEqual(list(external.iterdir()), [])
        (self.root / "storyboard").unlink()
        self.save()
        (self.root / "storyboard/state.json").write_text('{"schema_version": 999}')
        with self.assertRaises(PersistenceError):
            load_storyboard(self.root)

    def test_cli_add_and_read_use_shared_journal(self):
        from cine_toaster.cli import main
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["storyboard", "add", str(self.root), "SC-010", "P1", "--image", str(self.image),
                                   "--title", "CLI drawing", "--expected-revision", "0"]), 0)
        self.assertEqual(json.loads(output.getvalue())["revision"], 1)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["storyboard", "candidates", str(self.root), "--scene", "SC-010"]), 0)
        self.assertEqual(len(json.loads(output.getvalue())["candidates"]), 1)

    def test_http_shared_import_conflict_and_path_boundary(self):
        from cine_toaster.web import ProjectBrowserHandler
        server = ThreadingHTTPServer(("127.0.0.1", 0), ProjectBrowserHandler)
        server.project_root = self.root
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        def post(payload):
            request = urllib.request.Request(origin + "/api/storyboard", data=json.dumps(payload).encode(),
                                             headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)
        values = {"scene": "SC-010", "shot": "P1", "title": "HTTP drawing", "expected_revision": 0,
                  "image": f"references/{self.ref.name}/draft.png", "references": [self.ref.name]}
        status, saved = post(values)
        self.assertEqual(status, 200)
        self.assertEqual(saved["candidate"]["actor"]["id"], "storyboard-gui")
        self.assertEqual(post(values)[0], 409)
        self.assertEqual(post({**values, "image": "../draft.png", "expected_revision": 1})[0], 422)
        with urllib.request.urlopen(origin + "/api/storyboard?scene=SC-010") as response:
            self.assertEqual(json.load(response)["revision"], 1)


if __name__ == "__main__":
    unittest.main()
