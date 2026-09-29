"""A person's screenplay edit is written byte for byte, or not at all (ADR 0016)."""

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

from cine_toaster.errors import ValidationError
from cine_toaster.events import tail_events
from cine_toaster.index import ProjectIndex, build_index
from cine_toaster.project import load_production
from cine_toaster.screenplay_edit import (
    ScreenplayConflictError, ScreenplayReadOnlyError, digest, edit_screenplay, screenplay_files,
)
from cine_toaster.web import ProjectBrowserHandler

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
SCRIPT = "story/screenplay.fountain"


class EditTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.previous = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = str(self.base / "cache")
        self.addCleanup(self._restore)
        self.root = self.base / "film"
        shutil.copytree(DEMO, self.root)
        self.path = self.root / SCRIPT

    def _restore(self) -> None:
        if self.previous is None:
            os.environ.pop("XDG_CACHE_HOME", None)
        else:
            os.environ["XDG_CACHE_HOME"] = self.previous

    def opened(self) -> dict:
        return next(item for item in screenplay_files(self.root, load_production(self.root))["files"] if item["path"] == SCRIPT)


class WriteTests(EditTestCase):
    def test_only_the_edited_bytes_change(self) -> None:
        opened = self.opened()
        before = self.path.read_bytes()
        text = opened["text"].replace("Radio static.", "Radio static. A kettle ticks.")
        result = edit_screenplay(self.root, SCRIPT, text, opened["revision"], actor="writer")
        after = self.path.read_bytes()
        self.assertTrue(result["changed"])
        self.assertEqual(after, before.replace(b"Radio static.", b"Radio static. A kettle ticks."))
        self.assertEqual(result["revision"], digest(after))
        event = tail_events(self.root)[-1]
        self.assertEqual((event["type"], event["payload"]["path"], event["payload"]["actor"]),
                         ("screenplay.edited", SCRIPT, "writer"))

    def test_an_unchanged_text_writes_nothing(self) -> None:
        opened = self.opened()
        stat = self.path.stat()
        result = edit_screenplay(self.root, SCRIPT, opened["text"], opened["revision"])
        self.assertFalse(result["changed"])
        self.assertEqual(self.path.stat().st_mtime_ns, stat.st_mtime_ns)

    def test_a_file_changed_since_it_was_opened_is_not_overwritten(self) -> None:
        opened = self.opened()
        self.path.write_text(opened["text"] + "\nSomeone else was here.\n", encoding="utf-8")
        someone_else = self.path.read_bytes()
        with self.assertRaises(ScreenplayConflictError):
            edit_screenplay(self.root, SCRIPT, "My version.\n", opened["revision"])
        self.assertEqual(self.path.read_bytes(), someone_else)

    def test_only_screenplay_files_can_be_written(self) -> None:
        manifest = (self.root / "project.yaml").read_bytes()
        for path in ("project.yaml", "../escape.fountain", "scenes/030-echo-chamber/scene.yaml"):
            with self.assertRaises(ValidationError):
                edit_screenplay(self.root, path, "x", digest(b""))
        self.assertEqual((self.root / "project.yaml").read_bytes(), manifest)
        self.assertFalse((self.base / "escape.fountain").exists())

    def test_a_generated_screenplay_is_read_only(self) -> None:
        with open(self.root / "project.yaml", "a", encoding="utf-8") as handle:
            handle.write("screenplay_generated_by: tools/assemble.py\n")
        opened = self.opened()
        self.assertFalse(screenplay_files(self.root, load_production(self.root))["editable"])
        with self.assertRaises(ScreenplayReadOnlyError) as caught:
            edit_screenplay(self.root, SCRIPT, opened["text"] + "x", opened["revision"])
        self.assertIn("tools/assemble.py", str(caught.exception))

    def test_line_endings_and_byte_order_mark_survive(self) -> None:
        text = self.path.read_text(encoding="utf-8")
        self.path.write_bytes(("﻿" + text.replace("\n", "\r\n")).encode("utf-8"))
        opened = self.opened()
        self.assertEqual(opened["line_endings"], "crlf")
        # An editor hands back LF and no BOM.
        edited = opened["text"].replace("\r\n", "\n").replace("Radio static.", "Radio hiss.")
        edit_screenplay(self.root, SCRIPT, edited, opened["revision"])
        raw = self.path.read_bytes()
        self.assertTrue(raw.startswith("﻿".encode("utf-8")))
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
        self.assertIn(b"Radio hiss.", raw)


class ImpactTests(EditTestCase):
    def test_breaking_a_quoted_line_is_reported(self) -> None:
        opened = self.opened()
        text = opened["text"].replace("The speaker stack wakes", "The speakers stir")
        result = edit_screenplay(self.root, SCRIPT, text, opened["revision"])
        codes = [finding["code"] for finding in result["impact"]["new"]]
        self.assertIn("script_anchor_missing", codes)
        self.assertEqual(result["impact"]["new"][codes.index("script_anchor_missing")]["scene_id"], "SC-030")


class HttpTests(EditTestCase):
    def setUp(self) -> None:
        super().setUp()
        build_index(self.root)
        server = ThreadingHTTPServer(("127.0.0.1", 0), ProjectBrowserHandler)
        server.project_index = ProjectIndex(self.root)
        server.project_root = self.root.resolve()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(5)))
        self.url = f"http://127.0.0.1:{server.server_address[1]}/api/screenplay"

    def post(self, body: dict) -> tuple[int, dict]:
        request = urllib.request.Request(self.url, data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_open_edit_and_conflict_over_http(self) -> None:
        with urllib.request.urlopen(self.url, timeout=30) as response:
            opened = json.load(response)
        self.assertTrue(opened["editable"])
        file = opened["files"][0]
        status, result = self.post({"path": file["path"], "text": file["text"] + "\nFADE OUT.\n",
                                    "revision": file["revision"], "actor": {"id": "writer"}})
        self.assertEqual((status, result["changed"]), (200, True))
        status, stale = self.post({"path": file["path"], "text": "x", "revision": file["revision"]})
        self.assertEqual((status, stale["error"]["code"]), (409, "revision_conflict"))


if __name__ == "__main__":
    unittest.main()
