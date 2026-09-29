"""The production canvas projects records; it holds none of its own (plan step 7)."""

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

from cine_toaster import web
from cine_toaster.graph import load_graph
from cine_toaster.index import ProjectIndex, build_index

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


class GraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = load_graph(DEMO)
        cls.nodes = {node["id"]: node for node in cls.graph["nodes"]}
        cls.edges = {edge["id"]: edge for edge in cls.graph["edges"]}

    def test_scenes_shots_and_takes_are_nodes(self) -> None:
        kinds = [node["type"] for node in self.graph["nodes"]]
        self.assertEqual((kinds.count("scene"), kinds.count("shot"), kinds.count("take")), (2, 5, 8))

    def test_the_view_carries_no_positions(self) -> None:
        self.assertFalse(any("position" in node for node in self.graph["nodes"]))

    def test_cuts_are_edges_with_their_record(self) -> None:
        l_cut = self.edges["cut:SC-010/P1-P2"]
        self.assertEqual((l_cut["source"], l_cut["target"]), ("shot:SC-010/P1", "shot:SC-010/P2"))
        self.assertEqual(l_cut["data"]["cut"], "l")
        self.assertTrue(l_cut["data"]["reason"])
        self.assertEqual(self.edges["cut:SC-030/P2-P3"]["data"]["cut"], "j")

    def test_scenes_follow_each_other_without_a_cut_record(self) -> None:
        order = self.edges["next:SC-010-SC-030"]
        self.assertEqual((order["type"], order["source"], order["target"]),
                         ("scene-order", "shot:SC-010/P2", "shot:SC-030/P1"))

    def test_each_card_shows_the_best_picture_it_has(self) -> None:
        self.assertEqual(self.nodes["shot:SC-030/P2"]["data"]["picture"]["level"], "blocking")
        self.assertIn("/api/blocking-frame?scene=SC-030&shot=P2", self.nodes["shot:SC-030/P2"]["data"]["picture"]["image"])
        self.assertEqual(self.nodes["shot:SC-010/P1"]["data"]["picture"]["level"], "none")

    def test_a_shot_knows_who_speaks_and_how_it_moves(self) -> None:
        p3 = self.nodes["shot:SC-030/P3"]["data"]
        self.assertEqual(p3["speakers"], ["MARA", "SPEAKER STACK"])
        self.assertTrue(self.nodes["shot:SC-030/P2"]["data"]["walks"])

    def test_takes_hang_from_their_shot(self) -> None:
        takes = [edge for edge in self.graph["edges"] if edge["type"] == "take" and edge["source"] == "shot:SC-030/P3"]
        self.assertEqual(len(takes), 2)


class ServingTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        root = base / "production"
        shutil.copytree(DEMO, root)
        previous = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        self.addCleanup(lambda: os.environ.pop("XDG_CACHE_HOME") if previous is None else os.environ.__setitem__("XDG_CACHE_HOME", previous))
        build_index(root)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), web.ProjectBrowserHandler)
        self.server.project_index = ProjectIndex(root)
        self.server.project_root = root.resolve()
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(5)))
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def get(self, path: str) -> tuple[int, bytes]:
        try:
            with urllib.request.urlopen(self.base + path, timeout=30) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def test_the_graph_is_served(self) -> None:
        status, body = self.get("/api/graph")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["production"]["id"], "the-last-signal")

    def test_an_unbuilt_canvas_says_how_to_build_it(self) -> None:
        original = web.ASSET_ROOT
        empty = tempfile.TemporaryDirectory()
        self.addCleanup(empty.cleanup)
        web.ASSET_ROOT = Path(empty.name)
        self.addCleanup(setattr, web, "ASSET_ROOT", original)
        status, body = self.get("/canvas/")
        self.assertEqual(status, 404)
        self.assertIn(b"make ui", body)

    @unittest.skipUnless((web.ASSET_ROOT / "canvas" / "index.html").is_file(), "the canvas is not built (make ui)")
    def test_the_built_canvas_and_its_routes_are_served(self) -> None:
        status, body = self.get("/canvas/")
        self.assertEqual(status, 200)
        self.assertIn(b'id="root"', body)
        self.assertEqual(self.get("/canvas/some/route")[1], body)  # client routes fall back to the app
        self.assertEqual(self.get("/canvas/../../pyproject.toml")[0] in (200, 404), True)
        self.assertNotIn(b"[project]", self.get("/canvas/../../pyproject.toml")[1])


if __name__ == "__main__":
    unittest.main()
