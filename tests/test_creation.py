from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import io
import sys
import time
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from cine_toaster.creation import creation_view, load_creation, reference_snapshot, save_creation_draft, save_exploration_round
from cine_toaster.creation_jobs import plan_reference
from cine_toaster.errors import PersistenceError, RevisionConflictError, ValidationError
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.new_production import create_production
from cine_toaster.references import add_reference, load_references
from cine_toaster.state import Actor


class CreationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "film"
        create_production(self.root, "A new film")
        self.actor = Actor(id="director")
        self.picture = self.base / "idea.png"
        self.picture.write_bytes(b"first reference image")
        self.ref = add_reference(self.root, [self.picture], title="Initial idea", kind="made", name="initial")

    def save(self, **changes):
        values = dict(kind="concept", title="First direction", text="A girl follows the light.",
                      expected_revision=load_creation(self.root)["revision"], actor=self.actor,
                      references=[self.ref.name])
        values.update(changes)
        return save_creation_draft(self.root, **values)

    def test_handoff_pins_versions_and_never_rewrites_the_screenplay(self):
        original = (self.root / "story/screenplay.fountain").read_bytes()
        first = self.save()["draft"]
        screenplay = self.save(kind="screenplay", title="Draft one", text="Title: First\n\nEXT. MEADOW - DAY\n\nShe runs.\n",
                               concept=first["id"], references=[])["draft"]
        second = self.save(text="A different direction.", based_on=first["id"])["draft"]
        reopened = creation_view(self.root)
        self.assertEqual(len(reopened["drafts"]), 3)
        self.assertEqual(reopened["drafts"][0], first)
        self.assertEqual(screenplay["inputs"][0]["id"], first["id"])
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(screenplay["inputs"][1]["files"]["idea.png"], first["inputs"][0]["files"]["idea.png"])
        self.assertEqual((self.root / "story/screenplay.fountain").read_bytes(), original)
        self.assertEqual(reopened["findings"], [])

    def test_reference_change_is_reported_without_rewriting_pinned_inputs(self):
        saved = self.save()["draft"]
        (self.ref / "idea.png").write_bytes(b"changed externally")
        view = creation_view(self.root)
        self.assertEqual(view["drafts"][0], saved)
        self.assertEqual(view["findings"][0]["input"], self.ref.name)
        with self.assertRaises(ValidationError):
            self.save(kind="screenplay", concept=saved["id"])

    def test_two_writers_cannot_silently_save_against_the_same_revision(self):
        barrier = threading.Barrier(2)
        def save_one(label):
            barrier.wait()
            try:
                return self.save(title=label, expected_revision=0)["draft"]["id"]
            except RevisionConflictError:
                return "conflict"
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(save_one, ["One", "Two"]))
        self.assertEqual(results.count("conflict"), 1)
        self.assertEqual(load_creation(self.root)["revision"], 1)

    def test_failed_commit_leaves_the_previous_journal_readable(self):
        self.save()
        path = self.root / "creation/state.json"
        original = path.read_bytes()
        with patch("cine_toaster.creation.os.replace", side_effect=OSError("disk failure")):
            with self.assertRaises(PersistenceError):
                self.save()
        self.assertEqual(path.read_bytes(), original)

    def test_invalid_handoff_and_external_paths_are_refused(self):
        with self.assertRaises(ValidationError):
            self.save(kind="screenplay", concept="missing")
        with self.assertRaises(ValidationError):
            self.save(expected_revision="0")
        external = self.base / "external"
        external.mkdir()
        (self.root / "creation").symlink_to(external, target_is_directory=True)
        with self.assertRaises(ValidationError):
            self.save()
        self.assertEqual(list(external.iterdir()), [])

    def test_corrupt_journal_is_not_treated_as_an_empty_project(self):
        self.save()
        path = self.root / "creation/state.json"
        path.write_text('{"schema_version":999}')
        with self.assertRaises(PersistenceError):
            load_creation(self.root)

    def test_changed_generation_plan_is_refused_before_spending(self):
        with patch("cine_toaster.creation_jobs.image_providers", return_value={"codex-image": lambda: type("Maker", (), {"binary": "fake"})()}):
            plan = plan_reference(self.root, {"title": "A trial", "request": "Light", "parents": [self.ref.name]})
            (self.ref / "idea.png").write_bytes(b"changed externally")
            with self.assertRaises(ValidationError):
                plan_reference(self.root, plan)

    def test_corrective_round_is_not_a_provider_parent_or_an_approval(self):
        original = (self.root / "story/screenplay.fountain").read_bytes()
        first = save_exploration_round(self.root, title="Initial age studies", references=[self.ref.name],
            expected_revision=0, actor=self.actor, rationale="Age did not progress enough", source="Director's review")["round"]
        later = add_reference(self.root, [self.picture], title="Corrective study", kind="made", name="correction")
        second = save_exploration_round(self.root, title="Age correction", references=[later.name],
            expected_revision=1, actor=self.actor, rationale="A second pass to correct age progression", source="Director's clarification",
            follows=first["id"], corrections=[{"previous": self.ref.name, "current": later.name}])["round"]
        view = creation_view(self.root)
        nodes = {item["id"]: item for item in view["reference_history"]["nodes"]}
        self.assertEqual(view["rounds"], [first, second])
        self.assertEqual(nodes[self.ref.name]["revised_by"][0]["id"], later.name)
        self.assertEqual(nodes[later.name]["corrects"][0]["id"], self.ref.name)
        self.assertEqual(nodes[later.name]["parents"], [])
        self.assertEqual(nodes[later.name]["review"], "not_recorded")
        self.assertEqual(view["reference_history"]["summary"]["provider_input_links"], 0)
        self.assertEqual((self.root / "story/screenplay.fountain").read_bytes(), original)
        self.assertEqual((self.ref / "idea.png").read_bytes(), self.picture.read_bytes())
        with self.assertRaises(RevisionConflictError):
            save_exploration_round(self.root, title="Conflict", references=[later.name], expected_revision=1,
                actor=self.actor, rationale="Do not race", source="Test")
        with self.assertRaises(ValidationError):
            save_exploration_round(self.root, title="Invalid relation", references=[later.name], expected_revision=2,
                actor=self.actor, rationale="No inferred parents", source="Test", follows=first["id"],
                corrections=[{"previous": "missing", "current": later.name}])
        self.assertEqual(load_creation(self.root)["rounds"], [first, second])

    def test_history_distinguishes_execution_declared_direction_and_cast_designation(self):
        from cine_toaster.creation_history import reference_history
        records = [{"id": "source", "title": "Source", "files": {"picture.png": "recorded-hash"}},
                   {"id": "declared", "title": "Declared", "files": {}, "from": ["source"]},
                   {"id": "executed", "title": "Executed", "files": {}, "from": ["source"],
                    "generation": {"references": [{"file": "references/source/picture.png", "sha256": "recorded-hash"}]}},
                   {"id": "unrelated", "title": "Unrelated", "files": {}, "generation": {"composed_from": {"cast": "LIA", "style": "ink"}}}]
        cast = {"LIA": {"id": "LIA", "references": [{"path": "references/source/picture.png", "role": "master", "kind": "face"}], "variants": {}}}
        result = reference_history(records, [], cast)
        nodes = {item["id"]: item for item in result["nodes"]}
        self.assertEqual(nodes["declared"]["parents"][0]["evidence"], "declared_lineage")
        self.assertEqual(nodes["executed"]["parents"][0]["evidence"], "provider_input")
        self.assertEqual(len(nodes["source"]["uses"]), 2)
        self.assertEqual(nodes["source"]["selections"][0]["role"], "master")
        self.assertEqual(nodes["source"]["review"], "not_recorded")
        self.assertEqual(nodes["unrelated"]["parents"], [])
        self.assertEqual(result["summary"]["provider_input_links"], 1)

    def test_round_names_count_and_order_are_filmmaker_defined_and_revisions_are_retained(self):
        first = save_exploration_round(self.root, title="Costume", references=[self.ref.name], expected_revision=0,
            actor=self.actor, rationale="Explore wardrobe", source="Director")["round"]
        second = save_exploration_round(self.root, title="Lighting", references=[self.ref.name], expected_revision=1,
            actor=self.actor, rationale="Try moonlight", source="Director", follows=first["id"])["round"]
        revised = save_exploration_round(self.root, title="Night lighting", references=[self.ref.name], expected_revision=2,
            actor=self.actor, rationale="Clarify this round's label", source="Director", follows=first["id"], based_on=second["id"])["round"]
        view = creation_view(self.root)
        self.assertEqual([item["title"] for item in view["active_rounds"]], ["Costume", "Night lighting"])
        self.assertEqual(view["rounds"], [first, second, revised])
        self.assertEqual(revised["round_id"], second["round_id"])
        self.assertEqual(revised["version"], 2)
        with self.assertRaises(ValidationError):
            save_exploration_round(self.root, title="Cycle", references=[self.ref.name], expected_revision=3,
                actor=self.actor, rationale="Invalid ordering", source="Test", follows=revised["id"], based_on=first["id"])
        self.assertEqual(load_creation(self.root)["revision"], 3)

    def test_cli_and_core_share_the_same_journal_and_conflict(self):
        from cine_toaster.cli import main
        source = self.base / "concept.txt"
        source.write_text("A premise entered through the CLI.")
        args = ["creation", "save", str(self.root), "--kind", "concept", "--title", "CLI draft",
                "--text-file", str(source), "--expected-revision", "0", "--actor", "director"]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(args), 0)
        saved = json.loads(output.getvalue())
        self.assertEqual(load_creation(self.root)["drafts"][0], saved["draft"])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 2)
        self.assertEqual(load_creation(self.root)["revision"], 1)
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["creation", "round", str(self.root), "--title", "CLI round", "--reference", self.ref.name,
                                  "--why", "Explore maturity", "--source", "Director's observation", "--expected-revision", "1"]), 0)
        self.assertEqual(load_creation(self.root)["rounds"][0], json.loads(output.getvalue())["round"])

    def test_reference_job_stages_then_adopts_without_replacing_history(self):
        from cine_toaster.references import add_reference as add
        concept = self.save()["draft"]
        def fake_generate(root, **kwargs):
            picture = self.base / "generated.png"
            picture.write_bytes(b"new image")
            return add(root, [picture], title=kwargs["title"], kind="generated", name=kwargs["name"],
                       prompt=kwargs["prompt"], parents=kwargs["parents"], generation={"provider": "fake", "references": []})
        with patch("cine_toaster.creation_jobs.image_providers", return_value={"codex-image": lambda: type("Maker", (), {"binary": "fake"})()}), \
             patch("cine_toaster.creation_jobs.generate_reference", side_effect=fake_generate):
            plan = plan_reference(self.root, {"title": "New trial", "request": "Try the light", "concept": concept["id"], "parents": [self.ref.name]})
            self.assertIn(concept["text"], plan["prompt"])
            with self._manager() as manager:
                with self.assertRaises(ValidationError):
                    manager.submit("generate_reference", self.root, plan)
                before = (self.ref / "idea.png").read_bytes()
                job = manager.submit("generate_reference", self.root, {**plan, "accept_quota": True})
                result = manager.wait(job["id"], timeout=10)
                self.assertEqual(result["state"], "succeeded", result.get("error"))
                self.assertEqual(len(load_references(self.root)), 1)
                with self.assertRaises(ValidationError):
                    manager.adopt(job["id"], overwrite=True)
                manager.adopt(job["id"])
                self.assertEqual(len(load_references(self.root)), 2)
                self.assertEqual((self.ref / "idea.png").read_bytes(), before)

    def test_reference_cancellation_terminates_the_owned_child(self):
        def waiting_generator(root, **kwargs):
            kwargs["runner"]([sys.executable, "-c", "import time; time.sleep(60)"], root, 120)
            raise AssertionError("Cancelled generation must not produce a reference")
        with patch("cine_toaster.creation_jobs.image_providers", return_value={"codex-image": lambda: type("Maker", (), {"binary": "fake"})()}), \
             patch("cine_toaster.creation_jobs.generate_reference", side_effect=waiting_generator), self._manager() as manager:
            plan = plan_reference(self.root, {"title": "Cancelled trial", "request": "Wait"})
            job = manager.submit("generate_reference", self.root, {**plan, "accept_quota": True})
            pid = None
            try:
                deadline = time.monotonic() + 5
                while not pid and time.monotonic() < deadline:
                    pid = manager.get(job["id"]).get("process_pid")
                    time.sleep(.02)
                self.assertIsNotNone(pid, "The owned child did not start")
            finally:
                manager.cancel(job["id"])
            result = manager.wait(job["id"], timeout=10)
            self.assertEqual(result["state"], "cancelled", result.get("error"))
            self.assertIsNone(result["process_pid"])
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
            self.assertEqual(len(load_references(self.root)), 1)

    def _manager(self):
        from contextlib import contextmanager
        @contextmanager
        def opened():
            manager = JobManager(store=JobStore(self.base / "jobs.sqlite"))
            try:
                yield manager
            finally:
                manager.shutdown()
        return opened()


class CreationHttpTests(unittest.TestCase):
    def test_save_reopen_conflict_and_screenplay_handoff(self):
        from http.server import ThreadingHTTPServer
        from cine_toaster.web import ProjectBrowserHandler
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "film"
            create_production(root, "HTTP film")
            original = (root / "story/screenplay.fountain").read_bytes()
            server = ThreadingHTTPServer(("127.0.0.1", 0), ProjectBrowserHandler)
            server.project_root = root
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f"http://127.0.0.1:{server.server_address[1]}"
            def post(payload):
                request = urllib.request.Request(origin + "/api/creation", data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(request) as response:
                        return response.status, json.loads(response.read())
                except urllib.error.HTTPError as error:
                    return error.code, json.loads(error.read())
            try:
                payload = {"kind": "concept", "title": "Idea", "text": "A first direction.", "expected_revision": 0}
                status, saved = post(payload)
                self.assertEqual(status, 200)
                self.assertEqual(saved["draft"]["actor"]["id"], "creation-gui")
                self.assertEqual(post(payload)[0], 409)
                status, screenplay = post({**payload, "kind": "screenplay", "concept": saved["draft"]["id"],
                                           "text": "Title: Trial\n\nA start.", "expected_revision": 1})
                self.assertEqual(status, 200)
                with urllib.request.urlopen(origin + "/api/creation") as response:
                    self.assertEqual(len(json.loads(response.read())["drafts"]), 2)
                self.assertEqual(screenplay["draft"]["inputs"][0]["id"], saved["draft"]["id"])
                self.assertEqual((root / "story/screenplay.fountain").read_bytes(), original)
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
