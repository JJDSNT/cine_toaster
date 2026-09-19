from __future__ import annotations

import unittest

from cine_toaster.transitions import (
    list_transitions,
    public_transition,
    transition_asset_path,
)


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


if __name__ == "__main__":
    unittest.main()
