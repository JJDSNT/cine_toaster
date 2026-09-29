from __future__ import annotations

import unittest
from pathlib import Path

from cine_toaster.transitions import (
    UnsupportedShader,
    list_transitions,
    public_transition,
    shader_params,
    transition_asset_path,
    upstream_root,
)

PERMISSIVE = {"MIT", "CC0-1.0", "BSD 2 Clause", "BSD 3 Clause"}


class TransitionTests(unittest.TestCase):
    def test_loads_glsl_and_webm_transitions(self) -> None:
        transitions = list_transitions()
        by_id = {transition["id"]: transition for transition in transitions}

        self.assertIn("cross-dissolve", by_id)
        self.assertIn("analog-scan", by_id)
        self.assertEqual(by_id["cross-dissolve"]["kind"], "glsl")
        self.assertEqual(by_id["analog-scan"]["kind"], "webm")
        self.assertTrue(by_id["analog-scan"]["asset_path"].is_file())

    def test_exposes_only_declared_assets(self) -> None:
        transition = next(
            item for item in list_transitions() if item["id"] == "cross-dissolve"
        )
        public = public_transition(transition)

        self.assertNotIn("asset_path", public)
        self.assertEqual(
            public["asset_url"],
            "/transition-assets/cross-dissolve/transition.glsl",
        )
        self.assertIsNotNone(
            transition_asset_path("cross-dissolve", "transition.glsl")
        )
        self.assertIsNone(
            transition_asset_path("cross-dissolve", "transition.toml")
        )

    def test_loads_a_production_owned_transition_from_the_amiga_demo(self) -> None:
        project = Path(__file__).parents[1] / "examples" / "amiga-demo-reel"
        transition = next(
            item
            for item in list_transitions(project)
            if item["id"] == "amiga-copper-bars"
        )

        self.assertEqual(transition["origin"], "project")
        self.assertEqual(transition["category"], "production")
        self.assertTrue(transition["asset_path"].is_file())


class ShaderParamTests(unittest.TestCase):
    def test_reads_the_gl_transitions_default_convention(self) -> None:
        source = """
uniform float count; // = 10.0
uniform bool opening; // = 1
uniform ivec2 size; // = ivec2(4)
uniform vec3 color /* = vec3(0.9, 0.4, 0.2) */;
uniform float phase; // = 0.4 ; // a trailing remark
uniform float progress;
"""
        params = {item["name"]: item for item in shader_params(source)}
        self.assertEqual(params["count"]["default"], 10.0)
        self.assertIs(params["opening"]["default"], True)
        self.assertEqual(params["size"]["default"], [4, 4])
        self.assertEqual(params["color"]["default"], [0.9, 0.4, 0.2])
        self.assertEqual(params["phase"]["default"], 0.4)
        self.assertNotIn("progress", params)

    def test_a_texture_or_a_missing_default_is_refused(self) -> None:
        with self.assertRaises(UnsupportedShader):
            shader_params("uniform sampler2D luma;")
        with self.assertRaises(UnsupportedShader):
            shader_params("uniform float amount;")


@unittest.skipIf(upstream_root() is None, "the gl-transitions submodule is not checked out")
class UpstreamCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = {item["id"]: item for item in list_transitions()}

    def test_upstream_shaders_are_listed_unreviewed(self) -> None:
        cube = self.catalog["cube"]
        self.assertFalse(cube["curated"])
        self.assertEqual(cube["origin"], "gl-transitions")
        self.assertEqual(cube["render"], {})
        self.assertTrue(cube["params"])

    def test_every_licence_is_permissive(self) -> None:
        """ADR 0011: nothing copyleft enters the repository, submodules included."""

        for item in self.catalog.values():
            self.assertIn(item["license"], PERMISSIVE, item["id"])

    def test_shaders_that_need_a_texture_are_left_out(self) -> None:
        self.assertNotIn("luma", self.catalog)
        self.assertNotIn("displacement", self.catalog)

    def test_a_curated_manifest_replaces_the_raw_shader(self) -> None:
        burn = self.catalog["film-burn"]
        self.assertTrue(burn["curated"])
        self.assertEqual(burn["upstream"], "gl-transitions:FilmBurn")
        self.assertEqual((burn["license"], burn["author"]), ("MIT", "Anastasia Dunbar"))
        self.assertTrue(burn["render"]["ffmpeg"])
        self.assertNotIn("film-burn-raw", self.catalog)
        self.assertEqual([i for i in self.catalog.values() if i["upstream"] == "gl-transitions:FilmBurn"], [burn])


if __name__ == "__main__":
    unittest.main()
